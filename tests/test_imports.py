"""Imports preserve stock, chronology, auditability and all-or-nothing semantics."""

from datetime import timedelta

import pandas as pd
import pytest

from restaurante.db import connect
from restaurante.imports import (
    apply_import,
    prepare,
    preview_import,
    read_csv,
    suggest_mapping,
    templates,
)
from restaurante.reports import operation_report
from restaurante.service import RestaurantService, business_today


@pytest.fixture
def kitchen(tmp_path):
    service = RestaurantService(tmp_path/"restaurant.sqlite3")
    ingredient = service.save_ingredient("Pollo", "kg", 11, 1, 2, 1)
    dish = service.save_dish("Arroz con pollo", 15)
    service.set_recipe(dish, {ingredient: .25})
    return service, ingredient, dish


def prepared(kind, rows=None):
    frame = templates()[kind] if rows is None else pd.DataFrame(rows)
    return prepare(frame.astype(str), kind, date_format="AAAA-MM-DD")


def test_csv_accepts_excel_encoding_separator_decimal_and_mapped_columns():
    content = "Nombre;Unidad;Costo;Empaque;Vida útil;Reserva\nAjí;kg;12,50;1;3;0,5\n".encode("cp1252")
    frame = read_csv(content)
    mapping = suggest_mapping(frame, "insumos")
    result = prepare(frame, "insumos", mapping, decimal=",")
    assert result.insumo.iloc[0] == "Ají"
    assert result.costo_unitario.iloc[0] == 12.5
    assert result.stock_seguridad.iloc[0] == .5
    with pytest.raises(ValueError, match="decimal"):
        prepare(frame, "insumos", mapping, decimal=".")
    dates = read_csv(b"Dia,Comida,Vendidos\n15/01/2025,Arroz con pollo,30\n")
    result = prepare(dates, "ventas_historicas", {"fecha": "Dia", "plato": "Comida", "porciones": "Vendidos"})
    assert result.fecha.iloc[0] == "2025-01-15"


def test_csv_rejects_duplicate_headers_rows_and_nonfinite_values():
    with pytest.raises(ValueError, match="encabezados"):
        read_csv(b"plato,Plato\na,b\n")
    with pytest.raises(ValueError, match="duplicadas"):
        prepared("platos", [{"plato": "Menú", "precio": "15"}, {"plato": "MENÚ", "precio": "16"}])
    for bad in ("nan", "inf", "-1"):
        with pytest.raises(ValueError, match="Fila 2"):
            prepared("platos", [{"plato": "Menú", "precio": bad}])
    with pytest.raises(ValueError, match="50000|5 MB"):
        read_csv(b"x"*5_000_001)


def test_catalog_failure_rolls_back_every_row_and_audit(kitchen):
    service, _, _ = kitchen
    rows = templates()["insumos"].to_dict("records")
    rows = [dict(rows[0], insumo="Arroz"), dict(rows[0], costo_unitario=99)]
    with pytest.raises(ValueError, match="Fila 3"):
        apply_import(service, "insumos", prepared("insumos", rows))
    assert service.ingredients().name.tolist() == ["Pollo"]
    assert service.imports().empty


def test_preview_never_changes_real_database_and_reupload_is_idempotent(kitchen):
    service, _, _ = kitchen
    rows = prepared("platos", [{"plato": "Lentejas", "precio": "12"}])
    preview = preview_import(service, "platos", rows)
    assert preview["created"] == 1
    assert service.dishes().name.tolist() == ["Arroz con pollo"]
    assert service.imports().empty
    result = apply_import(service, "platos", rows, filename="original.csv")
    again = apply_import(service, "platos", rows, filename="copia.csv")
    assert result["created"] == 1 and again["already_imported"]
    assert len(service.dishes()) == 2 and len(service.imports()) == 1


def test_stock_initial_is_a_balance_not_a_purchase(kitchen):
    service, ingredient, _ = kitchen
    rows = prepared("stock_inicial")
    preview_import(service, "stock_inicial", rows)
    assert service.lots().empty
    apply_import(service, "stock_inicial", rows)
    assert service.stock(business_today()).available.iloc[0] == 10
    assert service.lots().origin.tolist() == ["Stock inicial"]
    assert service.purchases().empty
    report = operation_report(service, business_today(), business_today())
    assert report["purchase_amount"] == 0
    assert apply_import(service, "stock_inicial", rows)["already_imported"]
    changed = rows.copy()
    changed["cantidad"] = 20
    with pytest.raises(ValueError, match="una sola vez"):
        apply_import(service, "stock_inicial", changed)
    assert service.stock(business_today()).available.iloc[0] == 10
    assert service.stock(business_today()).ingredient_id.iloc[0] == ingredient


def test_stock_file_with_bad_last_row_rolls_back_all_lots(kitchen):
    service, _, _ = kitchen
    service.save_ingredient("Arroz", "kg", 4, 5, 90, 0)
    rows = templates()["stock_inicial"].to_dict("records")
    rows.append(dict(rows[0], insumo="Arroz", vencimiento=(business_today()-timedelta(days=1)).isoformat()))
    with pytest.raises(ValueError, match="Fila 3"):
        apply_import(service, "stock_inicial", prepared("stock_inicial", rows))
    assert service.lots().empty and service.imports().empty


def test_purchase_references_prevent_partial_file_duplicates(kitchen):
    service, _, _ = kitchen
    rows = templates()["compras"].to_dict("records")
    apply_import(service, "compras", prepared("compras", rows))
    rows[0]["referencia"] = rows[0]["referencia"].lower()
    rows[0]["insumo"] = "POLLO"
    rows.append(dict(rows[0], referencia="COMPRA-002-LINEA-1", cantidad=2))
    result = apply_import(service, "compras", prepared("compras", rows))
    assert result["unchanged"] == 1 and result["created"] == 1
    assert len(service.purchases()) == 2
    assert service.stock(business_today()).available.iloc[0] == 7
    conflicting = [dict(rows[0], cantidad=100)]
    with pytest.raises(ValueError, match="referencia"):
        apply_import(service, "compras", prepared("compras", conflicting))
    assert service.stock(business_today()).available.iloc[0] == 7


def test_historical_sales_feed_forecasts_without_consuming_stock_or_revenue(kitchen):
    service, ingredient, dish = kitchen
    apply_import(service, "stock_inicial", prepared("stock_inicial"))
    day = business_today()-timedelta(days=7)
    rows = [{"fecha": day.isoformat(), "plato": "Arroz con pollo", "porciones": 30, "no_atendidas": 2},
            {"fecha": (day+timedelta(days=2)).isoformat(), "plato": "Arroz con pollo", "porciones": 0, "no_atendidas": 0}]
    with pytest.raises(ValueError, match="Confirma"):
        apply_import(service, "ventas_historicas", prepared("ventas_historicas", rows))
    assert len(service.imports()) == 1
    apply_import(service, "ventas_historicas", prepared("ventas_historicas", rows), complete_days=True)
    assert service.sales().empty
    assert service.stock(business_today()).available.iloc[0] == 10
    history = service.forecast_history()
    assert history.quantity.tolist() == [8., 0.]
    assert history.source.tolist() == ["imported_sales_complete"]*2
    assert len(service.imported_sales()) == 2
    assert len(history) == 2  # The missing calendar day is not filled with zero.
    service.set_recipe(dish, {ingredient: .5})
    assert service.forecast_history().quantity.tolist() == [8., 0.]
    report = operation_report(service, day, business_today())
    assert report["sales_amount"] == 0 and report["purchase_amount"] == 0
    with pytest.raises(ValueError, match="cerrado"):
        service.record_sale({dish: 1}, day.isoformat(), "cannot-double-count-history")
    with pytest.raises(ValueError, match="ya fue importada"):
        apply_import(service, "ventas_historicas", prepared("ventas_historicas", [dict(rows[0], porciones=31)]), complete_days=True)


def test_history_after_operations_or_future_is_rejected(kitchen):
    service, ingredient, _ = kitchen
    today = business_today()
    receipt_day = today-timedelta(days=5)
    service.receive_purchase(ingredient, 10, 11, receipt_day, today, "old-purchase")
    row = {"fecha": (today-timedelta(days=3)).isoformat(), "plato": "Arroz con pollo", "porciones": 30}
    with pytest.raises(ValueError, match="anterior al primer"):
        apply_import(service, "ventas_historicas", prepared("ventas_historicas", [row]), complete_days=True)
    with pytest.raises(ValueError, match="anteriores a hoy"):
        apply_import(service, "ventas_historicas", prepared("ventas_historicas", [dict(row, fecha=today.isoformat())]), complete_days=True)
    assert service.imported_sales().empty and service.imports().empty


def test_recipe_conflict_cannot_overwrite_existing_recipe(kitchen):
    service, ingredient, dish = kitchen
    rows = prepared("recetas")
    assert apply_import(service, "recetas", rows)["unchanged"] == 1
    rows["cantidad"] = .9
    with pytest.raises(ValueError, match="ya existe"):
        apply_import(service, "recetas", rows)
    assert service.recipe(dish).quantity.iloc[0] == .25
    assert service.recipe(dish).ingredient_id.iloc[0] == ingredient


def test_historical_import_is_in_backup(kitchen, tmp_path):
    service, _, _ = kitchen
    apply_import(service, "ventas_historicas", prepared("ventas_historicas"), complete_days=True)
    path = tmp_path/"backup.sqlite3"
    path.write_bytes(service.backup())
    restored = RestaurantService(path)
    assert len(restored.imported_sales()) == 1
    assert len(restored.imports()) == 1
    connection = connect(path)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_preview_is_revalidated_if_database_changes_before_confirmation(kitchen):
    service, _, _ = kitchen
    rows = prepared("platos", [{"plato": "Lentejas", "precio": "12"}, {"plato": "Sopa", "precio": "8"}])
    preview_import(service, "platos", rows)
    service.save_dish("Sopa", 99)
    with pytest.raises(ValueError, match="otros datos"):
        apply_import(service, "platos", rows)
    assert "Lentejas" not in service.dishes().name.tolist()
    assert service.imports().empty


def test_imported_history_keeps_ingredient_unit_even_after_recipe_changes(kitchen):
    service, ingredient, dish = kitchen
    apply_import(service, "ventas_historicas", prepared("ventas_historicas"), complete_days=True)
    other = service.save_ingredient("Papa", "kg", 3, 1, 7, 0)
    service.set_recipe(dish, {other: .1})
    with pytest.raises(ValueError, match="unidad"):
        service.save_ingredient("Pollo", "g", 11, 1, 2, 1, ingredient)
