from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from restaurante.forecast import forecast_demand, purchase_plan


def ingredients(**changes):
    row = dict(
        id=1,
        name="Arroz",
        unit="kg",
        cost=4.0,
        pack_size=1.0,
        shelf_life_days=30,
        safety_stock=0.0,
        active=True,
    )
    row.update(changes)
    return pd.DataFrame([row])


def history(days=84, ingredient_id=1):
    start = date(2026, 1, 1)
    return pd.DataFrame(
        [
            dict(
                date=(start + timedelta(days=i)).isoformat(),
                ingredient_id=ingredient_id,
                quantity=10 + (i % 7),
                source="synthetic",
            )
            for i in range(days)
        ]
    )


def predictions(values):
    return pd.DataFrame(
        [
            dict(date=f"2026-04-{i + 1:02}", ingredient_id=1, predicted=value)
            for i, value in enumerate(values)
        ]
    )


def lots(*records):
    return pd.DataFrame(
        [
            dict(id=i + 1, ingredient_id=1, remaining=qty, received_on=received, expires_on=expires)
            for i, (qty, received, expires) in enumerate(records)
        ]
    )


def test_random_forest_uses_only_prior_data_and_is_deterministic():
    origin = "2026-03-26"
    data = history(90)
    expected = forecast_demand(data, ingredients(), origin)
    data.loc[data.date >= origin, "quantity"] = 1_000_000
    actual = forecast_demand(data, ingredients(), origin)
    pd.testing.assert_frame_equal(expected, actual)
    assert len(actual) == 7
    assert set(actual.method) == {"Random Forest"}
    assert actual.history_days.eq(84).all()
    assert actual.predicted.between(9, 17).all()


def test_no_cross_ingredient_demand_leakage():
    data = history()
    other = history(84, ingredient_id=2)
    other["quantity"] = 100_000
    catalog = pd.concat([ingredients(), ingredients(id=2, name="Pollo")])
    expected = forecast_demand(data, ingredients(), "2026-03-26")
    actual = forecast_demand(pd.concat([data, other]), catalog, "2026-03-26")
    pd.testing.assert_frame_equal(
        expected, actual[actual.ingredient_id == 1].reset_index(drop=True)
    )


def test_empty_history_is_explicit_zero_placeholder():
    result = forecast_demand(pd.DataFrame(), ingredients(), "2026-04-01", 3)
    assert result.predicted.eq(0).all()
    assert result.history_days.eq(0).all()
    assert result.method.str.contains("Sin historial").all()


def test_short_history_baselines_and_recursive_week():
    short = forecast_demand(history(3), ingredients(), "2026-01-04", 2)
    assert short.predicted.eq(11).all()
    assert short.method.str.contains("Promedio").all()
    week = forecast_demand(history(7), ingredients(), "2026-01-08", 8)
    assert week.predicted.tolist() == [10, 11, 12, 13, 14, 15, 16, 10]


def test_missing_calendar_days_are_zero_and_disabled_items_omitted():
    data = history(7).iloc[[0, 6]]
    result = forecast_demand(data, ingredients(), "2026-01-08", 1)
    assert result.predicted.iloc[0] == pytest.approx(26 / 7)
    assert forecast_demand(data, ingredients(active=False), "2026-01-08").empty


@pytest.mark.parametrize("horizon", [0, -1, 91, 1.5, True])
def test_invalid_horizon_rejected(horizon):
    with pytest.raises(ValueError):
        forecast_demand(history(), ingredients(), "2026-04-01", horizon)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1])
def test_nonfinite_history_and_predictions_rejected(bad):
    data = history(3).astype({"quantity": float})
    data.loc[0, "quantity"] = bad
    with pytest.raises(ValueError):
        forecast_demand(data, ingredients(), "2026-01-04")
    with pytest.raises(ValueError):
        purchase_plan(predictions([bad]), pd.DataFrame(), ingredients())


def test_stock_allocated_once_with_carryover_and_pack_rounding():
    existing = lots((5, "2026-03-31", "2026-04-30"))
    original = existing.copy(deep=True)
    result = purchase_plan(predictions([5, 5, 5]), existing, ingredients(pack_size=6))
    assert result.eligible_stock.tolist() == [5, 0, 1]
    assert result.suggested_quantity.tolist() == [0, 6, 6]
    assert result.closing_stock.tolist() == [0, 1, 2]
    assert result.estimated_cost.tolist() == [0, 24, 24]
    pd.testing.assert_frame_equal(existing, original)


def test_expiring_stock_and_same_day_expiry():
    existing = lots((8, "2026-03-31", "2026-04-01"))
    result = purchase_plan(predictions([3, 3]), existing, ingredients())
    assert result.suggested_quantity.tolist() == [0, 3]
    assert result.expired_quantity.tolist() == [0, 5]


def test_virtual_receipts_expire_and_safety_is_not_consumed():
    result = purchase_plan(
        predictions([2, 2]),
        pd.DataFrame(),
        ingredients(pack_size=5, shelf_life_days=1, safety_stock=1),
    )
    assert result.suggested_quantity.tolist() == [5, 5]
    assert result.closing_stock.tolist() == [3, 3]
    assert result.expired_quantity.tolist() == [0, 3]


def test_fifo_planning_preserves_later_lot_when_old_lot_consumed():
    existing = lots((3, "2026-03-30", "2026-04-01"), (3, "2026-03-31", "2026-04-30"))
    result = purchase_plan(predictions([3, 3]), existing, ingredients())
    assert result.suggested_quantity.eq(0).all()
    assert result.expired_quantity.eq(0).all()


def test_future_receipt_is_not_available_early():
    result = purchase_plan(
        predictions([2, 2]), lots((5, "2026-04-02", "2026-04-30")), ingredients()
    )
    assert result.suggested_quantity.tolist() == [2, 0]
    assert result.eligible_stock.tolist() == [0, 5]


def test_safety_factor_and_inactive_catalog():
    result = purchase_plan(predictions([2]), pd.DataFrame(), ingredients(safety_stock=3), 2)
    assert result.suggested_quantity.iloc[0] == 8
    assert result.closing_stock.iloc[0] == 6
    assert purchase_plan(predictions([2]), pd.DataFrame(), ingredients(active=False)).empty


@pytest.mark.parametrize(
    "field,value",
    [("pack_size", 0), ("cost", np.inf), ("safety_stock", -1), ("shelf_life_days", 1.5)],
)
def test_invalid_planning_catalog_rejected(field, value):
    with pytest.raises(ValueError):
        purchase_plan(predictions([2]), pd.DataFrame(), ingredients(**{field: value}))


def test_duplicate_forecasts_and_unknown_ingredients_rejected():
    with pytest.raises(ValueError):
        purchase_plan(pd.concat([predictions([2])] * 2), pd.DataFrame(), ingredients())
    unknown = predictions([2])
    unknown["ingredient_id"] = 99
    with pytest.raises(ValueError):
        purchase_plan(unknown, pd.DataFrame(), ingredients())


def test_fifo_uses_lot_id_for_same_receipt_date_despite_input_order():
    existing = lots((3, "2026-03-31", "2026-04-01"), (3, "2026-03-31", "2026-04-30"))
    result = purchase_plan(predictions([3, 3]), existing.iloc[::-1], ingredients())
    assert result.suggested_quantity.eq(0).all()
    assert result.expired_quantity.eq(0).all()
