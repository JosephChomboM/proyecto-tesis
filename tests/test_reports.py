from datetime import timedelta

import pytest

from restaurante import RestaurantService, business_today
from restaurante.reports import operation_report, printable_report


def test_report_filters_dates_and_distinguishes_purchases_adjustments_and_sales(tmp_path):
    service = RestaurantService(tmp_path / "report.sqlite3")
    today = business_today()
    rice = service.save_ingredient("Arroz", "kg", 4, 1, 30, 0)
    dish = service.save_dish("Menú", 15)
    service.set_recipe(dish, {rice: 0.2})
    service.receive_purchase(rice, 10, 4, today - timedelta(days=1), today, "p")
    service.record_sale({dish: 2}, today, "s")
    service.record_unmet(dish, 3, today, "Sin capacidad para atender", "u")
    service.record_waste(rice, 1, "Deterioro", today, "w")
    service.close_day(today)
    report = operation_report(service, today, today)
    assert report["sales_amount"] == 30
    assert report["purchase_amount"] == 0
    assert "remaining" not in report["purchases"].columns
    assert report["waste_amount"] == 4
    assert report["sold_portions"] == 2
    assert report["unmet_portions"] == 3
    assert report["complete_days"] == 1
    assert report["daily"].total.tolist() == [30]


def test_report_empty_period_and_invalid_range(tmp_path):
    service = RestaurantService(tmp_path / "report.sqlite3")
    today = business_today()
    report = operation_report(service, today, today)
    assert report["sales_amount"] == 0
    assert report["daily"].total.tolist() == [0]
    with pytest.raises(ValueError, match="fecha final"):
        operation_report(service, today, today - timedelta(days=1))


def test_printable_report_escapes_untrusted_names(tmp_path):
    service = RestaurantService(tmp_path / "report.sqlite3")
    today = business_today()
    rice = service.save_ingredient('<script>alert("x")</script>', "kg", 4, 1, 30, 0)
    service.receive_purchase(rice, 1, 4, today, today, "p")
    report = operation_report(service, today, today)
    html = printable_report(report, today, today, "Demostración", {"name": "Nombre"})
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "no calcula utilidad" in html
