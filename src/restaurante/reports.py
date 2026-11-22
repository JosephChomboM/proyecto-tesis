"""Period reports from recorded operations, keeping amounts and ingredient units separate."""

from datetime import date
from html import escape

import pandas as pd


def period_rows(frame, column, start, end):
    start, end = date.fromisoformat(str(start)), date.fromisoformat(str(end))
    if end < start:
        raise ValueError("La fecha final debe ser igual o posterior a la inicial.")
    if frame.empty:
        return frame.copy()
    days = pd.to_datetime(frame[column]).dt.date
    return frame.loc[(days >= start) & (days <= end)].copy()


def operation_report(service, start, end):
    sales = period_rows(service.sales(), "sold_on", start, end)
    purchases = period_rows(service.purchases(), "received_on", start, end)
    # Remaining stock is current, not the balance at the selected period's end.
    purchases = purchases.drop(columns="remaining", errors="ignore")
    waste = period_rows(service.waste(), "occurred_on", start, end)
    unmet = period_rows(service.unmet(), "date", start, end)
    closures = period_rows(service.closures(), "day", start, end)
    daily = pd.DataFrame({"date": pd.date_range(start, end).strftime("%Y-%m-%d")})
    if sales.empty:
        daily["total"] = 0.0
    else:
        totals = sales.groupby("sold_on", as_index=False)["total"].sum()
        daily = daily.merge(totals, left_on="date", right_on="sold_on", how="left").drop(
            columns="sold_on")
        daily["total"] = daily["total"].fillna(0.0)
    return {
        "sales": sales, "purchases": purchases, "waste": waste, "unmet": unmet,
        "closures": closures, "daily": daily,
        "sales_amount": float(sales["total"].sum()),
        "purchase_amount": float(purchases["total"].sum()),
        "waste_amount": float(waste["cost"].sum()),
        "sold_portions": int(sales["portions"].sum()),
        "unmet_portions": int(unmet["portions"].sum()),
        "complete_days": int(closures["status"].eq("complete").sum()),
    }


def printable_report(report, start, end, workspace, labels):
    """Self-contained HTML: escaped data, no remote assets, printable using the browser."""
    sections = []
    for key, title in [("sales", "Ventas registradas"), ("purchases", "Compras recibidas"),
                       ("waste", "Mermas registradas"), ("unmet", "Pedidos no atendidos")]:
        frame = report[key]
        content = ("<p>Sin registros en el periodo.</p>" if frame.empty else
                   frame.rename(columns=labels).to_html(index=False, escape=True,
                                                        float_format=lambda x: f"{x:.2f}"))
        sections.append(f"<h2>{title}</h2>{content}")
    return (
        '<!doctype html><html lang="es"><meta charset="utf-8"><title>Reporte Mise</title>'
        '<style>body{font:15px system-ui;color:#19354a;max-width:1100px;margin:40px auto;padding:20px}'
        'h1{color:#087f8c}h2{margin-top:32px}table{border-collapse:collapse;width:100%;font-size:12px}'
        'td,th{border:1px solid #dce5ee;padding:8px;text-align:left}th{background:#e8f7f6}'
        '.summary{background:#edf7ff;padding:20px;border-radius:12px;line-height:2}'
        '@media print{body{margin:0;padding:0}table{break-inside:auto}tr{break-inside:avoid}}</style>'
        f'<h1>Mise · Reporte de operaciones</h1><p>{escape(str(workspace))} · '
        f'{escape(str(start))} al {escape(str(end))}</p><div class="summary">'
        f'Ventas registradas: <strong>S/ {report["sales_amount"]:,.2f}</strong><br>'
        f'Compras recibidas: <strong>S/ {report["purchase_amount"]:,.2f}</strong><br>'
        f'Costo de mermas: <strong>S/ {report["waste_amount"]:,.2f}</strong><br>'
        f'Porciones vendidas: {report["sold_portions"]} · '
        f'Porciones no atendidas: {report["unmet_portions"]} · '
        f'Jornadas completas: {report["complete_days"]}</div>'
        '<p>Importes basados en registros. Compras no equivalen a costo de ventas; este reporte '
        'no calcula utilidad. Las mermas incluyen ajustes por conteo identificados por su motivo. '
        'Los días sin registros no acreditan ausencia de actividad. En demostración, los datos '
        'son ilustrativos y los movimientos registrados pertenecen a esta sesión.</p>'
        + "".join(sections) + "</html>"
    )
