"""Human-readable research exports, explicitly marked as synthetic experiments."""

from html import escape

import pandas as pd


def cost_comparison(summary):
    """Only money and counts are comparable across ingredients with different units."""
    totals = summary.groupby("policy")[["waste_cost", "purchase_cost", "stockout"]].sum()
    baseline, forecast = totals.loc["empirical"], totals.loc["forecast"]
    return {"empirical_waste_cost": float(baseline.waste_cost),
            "forecast_waste_cost": float(forecast.waste_cost),
            "relative_waste_reduction": float((baseline.waste_cost-forecast.waste_cost)/baseline.waste_cost*100)
            if baseline.waste_cost else None,
            "empirical_stockouts": int(baseline.stockout), "forecast_stockouts": int(forecast.stockout)}


def printable_experiment(results, labels):
    experiment = results["experiment"]
    winner = experiment.get("winner") or {}
    config = experiment.get("config", {})
    text = ("Resultados sintéticos de prueba. No demuestran impacto observado en restaurantes reales. "
            "Parámetros pendientes de calibración y juicio de expertos; usabilidad pendiente de participantes reales.")
    tables = []
    for name, title in (("metrics", "Errores por insumo y modelo"),
                        ("inventory_summary", "Inventario: insumos crudos, merma por vencimiento"),
                        ("model_status", "Modelos ejecutados y selección en validación")):
        frame = results.get(name, pd.DataFrame())
        tables.append(f"<h2>{escape(title)}</h2>"+frame.rename(columns=labels).to_html(index=False, escape=True, na_rep="No definido", float_format=lambda value: f"{value:.3f}"))
    return ("<!doctype html><html lang='es'><meta charset='utf-8'><title>Experimento Mise</title>"
            "<style>body{font:14px Arial;color:#19364a;margin:32px}h1,h2{color:#087f8c}"
            "aside{padding:16px;background:#fff3d6;border-left:4px solid #ef9233}"
            "table{border-collapse:collapse;width:100%;font-size:11px;margin:18px 0}"
            "th,td{border:1px solid #ddd;padding:6px;text-align:left}th{background:#e0f5f2}"
            "@media print{body{margin:10mm}table{font-size:8px}tr{break-inside:avoid}}</style>"
            f"<h1>Experimento de demanda e inventario</h1><aside>{escape(text)}</aside>"
            f"<p>Modelo seleccionado por validación: {escape(str(winner.get('model', 'Sin selección')))}.</p>"
            f"<p>Entrenamiento hasta {escape(str(config.get('train_end', '')))}; "
            f"validación hasta {escape(str(config.get('validation_end', '')))}.</p>"
            "<p>MAPE excluye demanda cero; WAPE es error absoluto sobre demanda total. "
            "Los errores y el servicio se informan por insumo. Un solo experimento no establece "
            "significancia del impacto. Saldo final conservado; sin sobrantes de comida preparada.</p>"
            + "".join(tables)+"</html>")
