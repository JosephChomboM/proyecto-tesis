from datetime import timedelta

import pandas as pd
import pytest

from restaurante import DomainError, RestaurantService, business_today
from restaurante.db import connect
from restaurante.evaluation import error_metrics, rolling_evaluation
from restaurante.forecast import forecast_demand, purchase_plan


@pytest.fixture
def kitchen(tmp_path):
    service = RestaurantService(tmp_path / "restaurant.sqlite3")
    rice = service.save_ingredient("Arroz", "kg", 4, 5, 30, 1)
    dish = service.save_dish("Menú", 15)
    service.set_recipe(dish, {rice: 0.2})
    return service, rice, dish


def test_pvps_consumes_earliest_expiry_not_oldest_receipt(kitchen):
    service, rice, dish = kitchen
    today = business_today()
    service.receive_purchase(rice, 2, 4, today - timedelta(days=1),
                             today + timedelta(days=10), "old")
    service.receive_purchase(rice, 2, 5, today, today, "new")
    service.record_sale({dish: 5}, today, "sale")
    assert service.lots().remaining.tolist() == [2, 1]
    prediction = pd.DataFrame([dict(date=today.isoformat(), ingredient_id=rice, predicted=1)])
    plan = purchase_plan(prediction, service.lots(), service.ingredients(), lead_time_days=2)
    assert plan.closing_stock.iloc[0] == 2
    assert plan.order_on.iloc[0] == (today - timedelta(days=2)).isoformat()


def test_closed_day_has_known_zeros_and_unrecorded_days_do_not(kitchen):
    service, rice, dish = kitchen
    today = business_today()
    service.close_day(today - timedelta(days=2))
    assert service.forecast_history().quantity.tolist() == [0]
    service.close_day(today, "closed")
    assert len(service.forecast_history()) == 1
    assert len(service.closures()) == 2
    with pytest.raises(DomainError, match="cerrado"):
        service.record_unmet(dish, 1, today, "Sin arroz", "late")


def test_unmet_demand_is_idempotent_snapshot_and_never_stock_or_revenue(kitchen):
    service, rice, dish = kitchen
    today = business_today()
    first = service.record_unmet(dish, 3, today, "Sin arroz", "lost")
    assert service.record_unmet(dish, 3, today, "Sin arroz", "lost") == first
    with pytest.raises(DomainError):
        service.record_unmet(dish, 4, today, "Sin arroz", "lost")
    service.set_recipe(dish, {rice: 1})
    assert service.sales().empty and service.purchases().empty
    assert service.stock(today).available.iloc[0] == 0
    service.close_day(today)
    assert service.forecast_history().quantity.iloc[0] == pytest.approx(0.6)
    service.close_day(today)
    assert len(service.forecast_history()) == 1


def test_sale_and_unmet_combined_only_after_day_complete(kitchen):
    service, rice, dish = kitchen
    today = business_today()
    service.receive_purchase(rice, 2, 4, today, today, "p")
    service.record_sale({dish: 2}, today, "s")
    service.record_unmet(dish, 3, today, "Sin stock para más pedidos", "u")
    assert service.forecast_history().empty
    with pytest.raises(DomainError, match="jornada completa"):
        service.close_day(today, "closed")
    service.close_day(today)
    assert service.forecast_history().quantity.iloc[0] == pytest.approx(1)
    with pytest.raises(DomainError, match="cerrado"):
        service.receive_purchase(rice, 1, 4, today, today, "p2")


def test_count_corrections_are_audited_and_excess_is_not_a_purchase(kitchen):
    service, rice, _ = kitchen
    today = business_today()
    service.adjust_stock(rice, 5, today, "Saldo inicial contado", today, "a1")
    assert service.purchases().empty
    assert service.lots().origin.tolist() == ["Ajuste de conteo"]
    service.adjust_stock(rice, 3, today, "Error de conteo anterior", today, "a2")
    service.adjust_stock(rice, 3, today, "Error de conteo anterior", today, "a2")
    assert service.stock(today).available.iloc[0] == 3
    assert len(service.adjustments()) == 2
    assert service.waste().cost.iloc[0] == 8


def test_backup_contains_committed_data_and_opens_independently(kitchen, tmp_path):
    service, rice, _ = kitchen
    today = business_today()
    service.receive_purchase(rice, 2, 4, today, today, "p")
    service.close_day(today)
    backup = tmp_path / "backup.sqlite3"
    backup.write_bytes(service.backup())
    reopened = RestaurantService(backup)
    assert reopened.stock(today).available.iloc[0] == 2
    assert reopened.forecast_history().quantity.tolist() == [0]


def test_existing_database_migration_keeps_records(kitchen):
    service, _, _ = kitchen
    connection = connect(service.db_path)
    try:
        connection.execute("UPDATE metadata SET value='1' WHERE key='schema_version'")
    finally:
        connection.close()
    reopened = RestaurantService(service.db_path)
    assert len(reopened.ingredients()) == 1
    connection = connect(service.db_path)
    try:
        assert connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "2"
    finally:
        connection.close()


def test_recipe_unit_cannot_silently_change(kitchen):
    service, rice, _ = kitchen
    with pytest.raises(DomainError, match="unidad"):
        service.save_ingredient("Arroz", "g", 4, 5, 30, 1, rice)


def test_unknown_days_do_not_dilute_average_and_closed_weekdays_zero(kitchen):
    service, rice, _ = kitchen
    h = pd.DataFrame([dict(date="2026-11-01", ingredient_id=rice, quantity=10)])
    result = forecast_demand(h, service.ingredients(), "2026-11-09", 2,
                             operating_weekdays=[0])
    assert result.predicted.tolist() == [10, 0]
    assert result.missing_days.tolist() == [7, 7]
    plan = purchase_plan(result, pd.DataFrame(), service.ingredients())
    assert plan.suggested_quantity.iloc[1] == 0


def test_metrics_explicitly_handle_zero_demand():
    metrics = error_metrics([0, 10], [2, 8])
    assert metrics["wape_percent"] == 40
    assert metrics["mape_percent"] == 20
    assert metrics["mape_excluded_zeros"] == 1
    assert error_metrics([0], [2])["wape_percent"] is None


def test_temporal_evaluation_does_not_train_on_test_block(kitchen):
    service, rice, _ = kitchen
    start = business_today() - timedelta(days=83)
    h = pd.DataFrame([dict(date=(start + timedelta(days=i)).isoformat(),
                           ingredient_id=rice, quantity=10 + i % 7) for i in range(84)])
    summary, detail = rolling_evaluation(h, service.ingredients(), folds=1)
    assert len(summary) == 3
    assert set(summary.strategy) == {"auto", "mean", "seasonal"}
    assert summary.observations.eq(7).all()
    changed = h.copy()
    changed.loc[changed.index >= 77, "quantity"] = 10000
    _, new_detail = rolling_evaluation(changed, service.ingredients(), folds=1)
    pd.testing.assert_series_equal(detail.predicted, new_detail.predicted)
