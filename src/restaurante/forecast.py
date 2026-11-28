"""Past-only ingredient forecasts and an isolated virtual purchasing ledger.

Missing days remain unknown; only explicit complete-day records may supply zeros.
Forecasts estimate consumption recorded by sales; unrecorded lost sales are unknown.
"""

from __future__ import annotations

import math
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

try:  # Optional research dependency: the study's selected model.
    from xgboost import XGBRegressor
except ImportError:  # pragma: no cover - depends on installed extras
    XGBRegressor = None

from .calendar import CONTEXT_FEATURES, daily_context

FORECAST_COLUMNS = ["date", "ingredient_id", "predicted", "method", "history_days",
                    "missing_days", "is_open", "is_holiday", "holiday_name", "calendar_known",
                    "event_name", "event_type", "context_used", "comparable_days", "context_label"]
PLAN_COLUMNS = [
    "date",
    "ingredient_id",
    "name",
    "unit",
    "demand",
    "eligible_stock",
    "safety",
    "suggested_quantity",
    "estimated_cost",
    "closing_stock",
    "expired_quantity",
    "order_on",
    "context_label",
]


def _number(value, name: str, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: ingresa un número válido.") from exc
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError(
            f"{name}: debe ser {'mayor que cero' if positive else 'no negativo'} y finito."
        )
    return number


def _day(value):
    try:
        result = pd.Timestamp(value)
        if pd.isna(result):
            raise ValueError
        return result.date()
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Ingresa una fecha válida.") from exc


def _catalog(ingredients: pd.DataFrame) -> pd.DataFrame:
    if ingredients.empty:
        return ingredients.copy()
    if "id" not in ingredients:
        raise ValueError("El catálogo necesita la columna id.")
    result = ingredients.copy()
    if result["id"].duplicated().any():
        raise ValueError("El catálogo tiene insumos duplicados.")
    if "active" in result:
        result = result[result["active"].astype(bool)]
    return result


MODEL_NAME = "XGBoost" if XGBRegressor is not None else "Random Forest"


def _regressor():
    """XGBoost with the configuration selected in the 2026-11-26 study (depth 4,
    90 trees, rate 0.06). Falls back to Random Forest when xgboost is not installed."""
    if XGBRegressor is not None:
        return XGBRegressor(n_estimators=90, max_depth=4, learning_rate=0.06,
                            objective="reg:squarederror", tree_method="hist",
                            random_state=42, n_jobs=1)
    return RandomForestRegressor(n_estimators=80, max_depth=8, min_samples_leaf=2,
                                 random_state=42, n_jobs=1)


def _features(values: list[float], day, start, context=None) -> list[float]:
    """Every demand feature ends strictly before the target day."""
    features = [
        values[-1],
        values[-7],
        values[-14],
        float(np.mean(values[-7:])),
        float(np.mean(values[-28:])),
        math.sin(2 * math.pi * day.weekday() / 7),
        math.cos(2 * math.pi * day.weekday() / 7),
        math.sin(2 * math.pi * day.timetuple().tm_yday / 365.25),
        math.cos(2 * math.pi * day.timetuple().tm_yday / 365.25),
        (day - start).days,
    ]
    if context is not None:
        features.extend(float(context[key]) for key in CONTEXT_FEATURES)
    return features


def forecast_demand(history, ingredients, origin, horizon=7, operating_weekdays=None,
                    strategy="auto", events=None):
    """Predict from ``origin`` inclusively, recursively, without future observations.

    RF requires 56 distinct observed days. Otherwise use last-week demand, a
    historical mean, or an explicit zero placeholder for an ingredient with no
    history. No method exposes an unmeasured accuracy score.
    """
    if (
        isinstance(horizon, bool)
        or not isinstance(horizon, (int, np.integer))
        or not 1 <= horizon <= 90
    ):
        raise ValueError("El horizonte debe ser un entero entre 1 y 90 días.")
    origin = _day(origin)
    if strategy not in {"auto", "auto_no_context", "mean", "seasonal"}:
        raise ValueError("Método de pronóstico inválido.")
    weekdays = set(range(7) if operating_weekdays is None else operating_weekdays)
    if not weekdays.issubset(set(range(7))):
        raise ValueError("Los días de atención deben estar entre 0 y 6.")
    catalog = _catalog(ingredients)
    if catalog.empty:
        return pd.DataFrame(columns=FORECAST_COLUMNS)
    data = history.copy()
    if not data.empty:
        required = {"date", "ingredient_id", "quantity"}
        if not required.issubset(data.columns):
            raise ValueError("El historial necesita date, ingredient_id y quantity.")
        data["date"] = data["date"].map(_day)
        data = data[data["date"] < origin].copy()
        data["quantity"] = data["quantity"].map(lambda x: _number(x, "Demanda"))
    context_start = min(data["date"]) if not data.empty else origin
    context = daily_context(pd.date_range(context_start, origin + timedelta(days=horizon-1)),
                            events, as_of=origin-timedelta(days=1))
    context_lookup = context.set_index("date").to_dict("index")
    use_context = strategy == "auto"
    rows = []
    for ingredient in catalog.to_dict("records"):
        ingredient_id = int(ingredient["id"])
        subset = data[data["ingredient_id"] == ingredient_id] if not data.empty else data
        observed_days = subset["date"].nunique() if not subset.empty else 0
        model = None
        missing_days = 0
        if observed_days:
            daily = subset.groupby("date")["quantity"].sum()
            start = daily.index.min()
            index = pd.date_range(start, origin - timedelta(days=1), freq="D")
            calendar = daily.reindex(index.date).astype(float)
            missing_days = int(calendar.isna().sum())
            # Carry the last known consumption for lag features, never invent zero targets.
            values = calendar.ffill().tolist()
            if strategy in {"auto", "auto_no_context"} and observed_days >= 56 and len(values) >= 56:
                x, y = [], []
                for offset in range(28, len(values)):
                    if pd.isna(calendar.iloc[offset]):
                        continue
                    target_day = start + timedelta(days=offset)
                    x.append(_features(values[:offset], target_day, start,
                                       context_lookup[target_day] if use_context else None))
                    y.append(values[offset])
                model = _regressor().fit(x, y) if x else None
                method = MODEL_NAME if model is not None else "Promedio histórico"
            elif strategy != "mean" and len(values) >= 7 and observed_days >= 7:
                method = "Ingenuo estacional (historial limitado)"
            else:
                method = "Promedio histórico (historial limitado)"
        else:
            start, values = origin, []
            method = "Sin historial: registrar ventas"
        short_mean = float(daily.mean()) if observed_days else 0.0
        for offset in range(horizon):
            day = origin + timedelta(days=offset)
            info = context_lookup[day]
            if model is not None:
                predicted = float(model.predict([_features(values, day, start,
                    info if use_context else None)])[0])
            elif method.startswith("Ingenuo"):
                reference = day - timedelta(days=7)
                if reference >= origin:
                    predicted = values[-7]
                elif reference in daily.index:
                    predicted = float(daily.loc[reference])
                else:
                    same_weekday = daily[[d.weekday() == day.weekday() for d in daily.index]]
                    predicted = float(same_weekday.mean()) if len(same_weekday) else short_mean
            else:
                predicted = short_mean
            predicted = max(0.0, predicted)
            is_open = day.weekday() in weekdays and not info["forced_closed"]
            if not is_open:
                predicted = 0.0
            observed_context = context[context.date.isin(daily.index)] if observed_days else context.iloc[:0]
            if info["event_type"]:
                comparable = int(observed_context.event_type.eq(info["event_type"]).sum())
            elif info["is_holiday"]:
                comparable = int(observed_context.is_holiday.sum())
            else:
                comparable = observed_days
            label = " · ".join(dict.fromkeys(value for value in (info["holiday_name"], info["event_name"])
                                             if value))
            if not info["calendar_known"]:
                label = " · ".join(filter(None, [label, "Calendario nacional por verificar"]))
            rows.append(
                {
                    "date": day.isoformat(),
                    "ingredient_id": ingredient_id,
                    "predicted": predicted,
                    "method": method,
                    "history_days": int(observed_days),
                    "missing_days": missing_days,
                    "is_open": is_open,
                    "is_holiday": info["is_holiday"], "holiday_name": info["holiday_name"],
                    "calendar_known": info["calendar_known"], "event_name": info["event_name"],
                    "event_type": info["event_type"], "context_used": model is not None and use_context,
                    "comparable_days": comparable, "context_label": label or "Día habitual",
                }
            )
            values.append(predicted)
    return pd.DataFrame(rows, columns=FORECAST_COLUMNS)


def purchase_plan(predictions, lots, ingredients, safety_factor=1.0, lead_time_days=0):
    """Plan dated receipts using a virtual FIFO ledger, never changing input data.

    Same-day expiry is usable. Planned packs arrive on their suggested date and
    expire after the ingredient's configured shelf life. Fixed safety stock is a
    planning target, not a claim about a statistical service level.
    """
    safety_factor = _number(safety_factor, "Factor de seguridad")
    if isinstance(lead_time_days, bool) or not isinstance(lead_time_days, (int, np.integer)) \
            or not 0 <= lead_time_days <= 30:
        raise ValueError("El plazo de entrega debe ser un entero entre 0 y 30 días.")
    catalog = _catalog(ingredients)
    if predictions.empty or catalog.empty:
        return pd.DataFrame(columns=PLAN_COLUMNS)
    if not {"date", "ingredient_id", "predicted"}.issubset(predictions.columns):
        raise ValueError("El pronóstico necesita date, ingredient_id y predicted.")
    demand = predictions.copy()
    demand["date"] = demand["date"].map(_day)
    demand["predicted"] = demand["predicted"].map(lambda x: _number(x, "Pronóstico"))
    if demand.duplicated(["date", "ingredient_id"]).any():
        raise ValueError("El pronóstico tiene fechas e insumos duplicados.")
    all_ids = set(ingredients["id"])
    if not set(demand["ingredient_id"]).issubset(all_ids):
        raise ValueError("El pronóstico contiene un insumo desconocido.")
    if not lots.empty and not {"ingredient_id", "remaining", "received_on", "expires_on"}.issubset(
        lots.columns
    ):
        raise ValueError("Los lotes necesitan ingredient_id, remaining, received_on y expires_on.")
    rows = []
    for ingredient in catalog.to_dict("records"):
        ingredient_id = int(ingredient["id"])
        targets = demand[demand["ingredient_id"] == ingredient_id].sort_values("date")
        if targets.empty:
            continue
        pack = _number(ingredient.get("pack_size", 1), "Tamaño de empaque", positive=True)
        cost = _number(ingredient.get("cost", 0), "Costo")
        safety = _number(ingredient.get("safety_stock", 0), "Stock de seguridad") * safety_factor
        shelf_life = _number(ingredient.get("shelf_life_days", 1), "Vida útil", positive=True)
        if not shelf_life.is_integer():
            raise ValueError("La vida útil debe ser un número entero de días.")
        ledger = []
        if not lots.empty:
            for order, lot in enumerate(
                lots[lots["ingredient_id"] == ingredient_id].to_dict("records")
            ):
                received, expires = _day(lot["received_on"]), _day(lot["expires_on"])
                if expires < received:
                    raise ValueError("Un lote no puede vencer antes de su recepción.")
                ledger.append(
                    {
                        "remaining": _number(lot["remaining"], "Stock"),
                        "received": received,
                        "expires": expires,
                        "order": int(lot.get("id", order)),
                    }
                )
        for target in targets.to_dict("records"):
            day, needed = target["date"], target["predicted"]
            target_safety = safety if target.get("is_open", True) else 0.0
            expired = 0.0
            for lot in ledger:
                if lot["expires"] < day:
                    expired += lot["remaining"]
                    lot["remaining"] = 0.0
            eligible = [lot for lot in ledger if lot["received"] <= day <= lot["expires"]]
            available = sum(lot["remaining"] for lot in eligible)
            shortage = max(0.0, needed + target_safety - available)
            suggested = max(0, math.ceil(shortage / pack - 1e-12)) * pack
            if suggested:
                lot = {
                    "remaining": suggested,
                    "received": day,
                    "expires": day + timedelta(days=int(shelf_life) - 1),
                    "order": max((item["order"] for item in ledger), default=-1) + 1,
                }
                ledger.append(lot)
                eligible.append(lot)
            outstanding = needed
            for lot in sorted(eligible, key=lambda x: (x["expires"], x["received"], x["order"])):
                taken = min(outstanding, lot["remaining"])
                lot["remaining"] -= taken
                outstanding -= taken
                if outstanding <= 1e-10:
                    break
            closing = sum(lot["remaining"] for lot in eligible)
            rows.append(
                {
                    "date": day.isoformat(),
                    "ingredient_id": ingredient_id,
                    "name": ingredient.get("name", str(ingredient_id)),
                    "unit": ingredient.get("unit", ""),
                    "demand": needed,
                    "eligible_stock": available,
                    "safety": target_safety,
                    "suggested_quantity": suggested,
                    "estimated_cost": suggested * cost,
                    "closing_stock": closing,
                    "expired_quantity": expired,
                    "order_on": (day - timedelta(days=int(lead_time_days))).isoformat(),
                    "context_label": target.get("context_label", ""),
                }
            )
    return (
        pd.DataFrame(rows, columns=PLAN_COLUMNS)
        .sort_values(["date", "ingredient_id"])
        .reset_index(drop=True)
    )
