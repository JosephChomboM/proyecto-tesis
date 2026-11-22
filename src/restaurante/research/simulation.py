"""Paired raw-ingredient expiry simulation. Policies cannot read future demand."""

from dataclasses import asdict, dataclass
from math import ceil

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class InventoryConfig:
    empirical_days: int = 28
    safety_days: float = .2
    initial_days: float = 1.


def simulate(demand, forecasts, ingredients, config=InventoryConfig()):
    """Daily review, fixed lead times, pack rounding and earliest-expiry consumption.

    At day's start: expire lots, place order, receive due orders, serve requests.
    Orders target demand through delivery day plus a past-mean reserve. No emergency
    replenishment. Same-day expiry is usable. Waste excludes prepared leftovers.
    """
    if not 1 <= config.empirical_days <= 90 or not 0 <= config.safety_days <= 7 or not 0 <= config.initial_days <= 7:
        raise ValueError("Revisa ventana empírica, reserva e inventario inicial.")
    data, predictions = demand.copy(), forecasts.copy()
    if not {"date", "profile", "ingredient", "demand", "is_open"} <= set(data) or data.empty:
        raise ValueError("El inventario necesita demanda diaria completa por perfil e insumo.")
    if not {"date", "origin", "profile", "ingredient", "predicted"} <= set(predictions):
        raise ValueError("Faltan columnas de los pronósticos de compra.")
    if not {"ingredient", "unit", "cost", "pack_size", "shelf_life_days", "lead_days"} <= set(ingredients):
        raise ValueError("Falta la configuración de compra y conservación de los insumos.")
    if ingredients.ingredient.duplicated().any() or not set(data.ingredient) <= set(ingredients.ingredient):
        raise ValueError("Insumos duplicados o ausentes en el catálogo.")
    for column in ("cost", "pack_size", "shelf_life_days", "lead_days"):
        values = pd.to_numeric(ingredients[column], errors="raise")
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("Los parámetros del inventario deben ser finitos y no negativos.")
    if (ingredients.pack_size <= 0).any() or (ingredients.shelf_life_days < 1).any() or (ingredients.shelf_life_days % 1).any() or (ingredients.lead_days % 1).any():
        raise ValueError("Presentación positiva, vida útil positiva y plazos enteros.")
    data["date"] = pd.to_datetime(data.date)
    predictions["date"] = pd.to_datetime(predictions.date)
    predictions["origin"] = pd.to_datetime(predictions.origin)
    if predictions.empty or predictions.duplicated(["origin", "date", "profile", "ingredient"]).any():
        raise ValueError("Se necesitan pronósticos únicos por origen, fecha e insumo.")
    if (predictions.date < predictions.origin).any() or not np.isfinite(predictions.predicted).all() or (predictions.predicted < 0).any():
        raise ValueError("Pronósticos inválidos.")
    if data.duplicated(["date", "profile", "ingredient"]).any() or not np.isfinite(data.demand).all() or (data.demand < 0).any():
        raise ValueError("La demanda debe ser finita, no negativa y única por insumo-día.")
    first, last = predictions.origin.min(), data.date.max()
    lookup = {(r.origin, r.date, r.profile, r.ingredient): r.predicted for r in predictions.itertuples()}
    catalog = ingredients.set_index("ingredient")
    rows = []
    for (profile, ingredient), group in data.groupby(["profile", "ingredient"]):
        item = catalog.loc[ingredient]
        cost, pack = float(item.cost), float(item.pack_size)
        shelf, lead = int(item.shelf_life_days), int(item.lead_days)
        prior = group[group.date < first].tail(config.empirical_days)
        initial_mean = float(prior.loc[prior.is_open.astype(bool), "demand"].mean()) if prior.is_open.any() else 0.
        if not np.isfinite(initial_mean):
            raise ValueError("Falta historial anterior a la simulación.")
        for policy in ("empirical", "forecast"):
            # Initial stock has the same quantity and remaining shelf life in both arms.
            lots = [{"quantity": initial_mean*config.initial_days,
                     "expires": first+pd.Timedelta(days=shelf-1)}]
            pipeline = []
            for day in group[group.date >= first].itertuples():
                date = day.date
                expired = sum(lot["quantity"] for lot in lots if lot["expires"] < date)
                lots = [lot for lot in lots if lot["expires"] >= date]
                historical = group[group.date < date].tail(config.empirical_days)
                mean = float(historical.loc[historical.is_open.astype(bool), "demand"].mean()) if historical.is_open.any() else 0.
                arrival = date+pd.Timedelta(days=lead)
                ordered = 0.
                if arrival <= last:
                    future_days = pd.date_range(date, arrival)
                    if policy == "forecast":
                        keys = [(date, future, profile, ingredient) for future in future_days]
                        if any(key not in lookup for key in keys):
                            raise ValueError("El horizonte de los pronósticos no cubre el plazo de entrega.")
                        needs = [lookup[key] for key in keys]
                    else:
                        # Closure schedules are known in advance; future request quantities are not.
                        opened = group.set_index("date").is_open
                        needs = [mean if opened.loc[future] else 0. for future in future_days]
                    # Project depletion and expiry before delivery using this policy's own forecast.
                    virtual = [lot.copy() for lot in lots]
                    for future, need in zip(future_days[:-1], needs[:-1], strict=True):
                        virtual.extend({"quantity": q, "expires": delivery+pd.Timedelta(days=shelf-1)}
                                       for delivery, q in pipeline if delivery == future)
                        for lot in sorted(virtual, key=lambda lot: lot["expires"]):
                            if lot["expires"] < future:
                                lot["quantity"] = 0.
                            used = min(need, lot["quantity"])
                            need -= used
                            lot["quantity"] -= used
                    available = sum(lot["quantity"] for lot in virtual if lot["expires"] >= arrival)
                    available += sum(q for delivery, q in pipeline if delivery == arrival)
                    safety = config.safety_days*mean if needs[-1] > 0 else 0.
                    ordered = max(0, ceil((needs[-1]+safety-available)/pack-1e-10))*pack
                    if ordered:
                        pipeline.append((arrival, ordered))
                received = sum(q for delivery, q in pipeline if delivery == date)
                pipeline = [(delivery, q) for delivery, q in pipeline if delivery != date]
                if received:
                    lots.append({"quantity": received, "expires": date+pd.Timedelta(days=shelf-1)})
                outstanding = float(day.demand)
                for lot in sorted(lots, key=lambda lot: lot["expires"]):
                    used = min(outstanding, lot["quantity"])
                    outstanding -= used
                    lot["quantity"] -= used
                rows.append({"date": date, "profile": profile, "ingredient": ingredient,
                             "unit": item.unit, "policy": policy, "demand": day.demand,
                             "served": day.demand-outstanding, "unmet": outstanding,
                             "stockout": int(outstanding > 1e-8), "ordered": ordered,
                             "received": received, "expired": expired, "waste_cost": expired*cost,
                             "purchase_cost": received*cost,
                             "closing_stock": sum(lot["quantity"] for lot in lots),
                             "initial_stock": initial_mean*config.initial_days if date == first else 0.})
    detail = pd.DataFrame(rows)
    summaries = []
    for key, group in detail.groupby(["profile", "ingredient", "unit", "policy"]):
        totals = group[["demand", "served", "unmet", "stockout", "received", "expired",
                        "waste_cost", "purchase_cost", "initial_stock"]].sum().to_dict()
        summaries.append(dict(zip(["profile", "ingredient", "unit", "policy"], key, strict=True)) |
                         totals | {"waste_percent": totals["expired"]/totals["received"]*100 if totals["received"] else None,
                                   "service_percent": totals["served"]/totals["demand"]*100 if totals["demand"] else None,
                                   "final_stock": float(group.iloc[-1].closing_stock)})
    return {"inventory_daily": detail, "inventory_summary": pd.DataFrame(summaries),
            "inventory_protocol": {"config": asdict(config),
                                   "scope": "Insumos crudos; vencimiento; demanda atendida por insumo, no platos servibles",
                                   "empirical": f"Media de jornadas abiertas en los {config.empirical_days} días previos; supuesto pendiente de expertos",
                                   "waste_denominator": "Recepciones del periodo; inventario inicial informado por separado",
                                   "terminal": "Saldo final no se considera merma; sin compras que lleguen fuera del periodo"}}


def paired_replica_summary(replications, indicators=("waste_cost", "stockout")):
    """Seeds are paired experimental replicas; days are not treated as independent."""
    frame = pd.DataFrame(replications)
    output = []
    for indicator in indicators:
        pivot = frame.pivot(index="seed", columns="policy", values=indicator).dropna()
        difference = (pivot.empirical-pivot.forecast).to_numpy(float)
        n = len(difference)
        base, treatment = float(pivot.empirical.mean()), float(pivot.forecast.mean())
        row = {"indicator": indicator, "replications": n, "empirical_mean": base,
               "forecast_mean": treatment,
               "relative_reduction_percent": (base-treatment)/base*100 if base else None,
               "mean_paired_reduction": float(difference.mean()), "p_value": None,
               "paired_standardized_difference": float(difference.mean()/difference.std(ddof=1))
               if n > 1 and difference.std(ddof=1) > 0 else None,
               "ci95_low": None, "ci95_high": None, "test": "Sin inferencia: mínimo 5 réplicas"}
        if n >= 5:
            if np.allclose(difference, 0):
                row.update(p_value=1., test="Diferencias nulas")
            else:
                row.update(p_value=float(stats.wilcoxon(difference).pvalue), test="Wilcoxon pareado bilateral por semilla")
            rng = np.random.default_rng(42)
            boot = rng.choice(difference, size=(3000, n), replace=True).mean(axis=1)
            row["ci95_low"], row["ci95_high"] = map(float, np.quantile(boot, [.025, .975]))
        output.append(row)
    return pd.DataFrame(output)
