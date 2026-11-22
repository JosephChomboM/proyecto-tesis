"""Context must change model inputs without hardcoded uplifts or retrospective leakage."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from restaurante.calendar import daily_context, holidays_for_year
from restaurante.evaluation import rolling_evaluation
from restaurante.forecast import forecast_demand, purchase_plan
from restaurante.service import RestaurantService


def catalog():
    return pd.DataFrame([dict(id=1, name="Pollo", unit="kg", cost=10., pack_size=1.,
                              shelf_life_days=2, safety_stock=2., active=True)])


def event(day, kind="promotion", name="Almuerzo especial", recorded_on="2025-01-01", id=1):
    return dict(id=id, day=day, kind=kind, name=name, recorded_on=recorded_on)


def test_peruvian_holidays_current_year_and_unknown_coverage():
    for year in (2024, 2025, 2026):
        assert len(holidays_for_year(year)) == 16
        assert date(year, 7, 28) in holidays_for_year(year)
    context = daily_context(["2026-04-02", "2026-04-03", "2026-01-02", "2027-01-01"])
    assert context.is_holiday.tolist() == [True, True, False, False]
    assert context.calendar_known.tolist() == [True, True, True, False]
    assert context.holiday_name.iloc[0] == "Jueves Santo"


def test_event_revisions_are_point_in_time_and_holidays_survive_cancellation():
    events = pd.DataFrame([event("2025-07-28", recorded_on="2025-07-01"),
                           event("2025-07-28", "cancelled", recorded_on="2025-07-20", id=2)])
    early = daily_context(["2025-07-28"], events, "2025-07-10").iloc[0]
    late = daily_context(["2025-07-28"], events, "2025-07-25").iloc[0]
    assert early.event_type == "promotion"
    assert late.event_type == ""
    assert early.is_holiday and late.is_holiday
    assert daily_context(["2025-07-28"], events, "2025-06-30").event_type.iloc[0] == ""


def test_local_holiday_does_not_certify_an_unknown_national_calendar():
    events = pd.DataFrame([event("2027-03-01", "holiday", "Fiesta local", "2026-11-22")])
    info = daily_context(["2027-03-01"], events, "2026-11-22").iloc[0]
    assert info.is_holiday and not info.calendar_known
    assert info.holiday_name == "Fiesta local"


def test_event_persistence_and_cancellation_do_not_touch_operations(tmp_path):
    service = RestaurantService(tmp_path/"restaurant.sqlite3")
    service.save_ingredient("Pollo", "kg", 10, 1, 2, 1)
    service.save_event("2026-12-01", "reservation", "Reserva para almuerzo")
    reopened = RestaurantService(service.db_path)
    assert reopened.events().iloc[0]["name"] == "Reserva para almuerzo"
    reopened.save_event("2026-12-01", "closure", "Cierre")
    assert len(reopened.events()) == 1
    assert len(reopened.events(include_history=True)) == 2
    reopened.save_event("2026-12-01", "cancelled", "Evento retirado")
    assert reopened.events().empty
    assert len(reopened.events(include_history=True)) == 3
    assert reopened.sales().empty and reopened.purchases().empty
    assert reopened.stock(date(2026, 12, 1)).available.sum() == 0
    with pytest.raises(ValueError):
        reopened.save_event("2026-12-01", "arbitrario", "Evento")


def test_holiday_flag_is_learned_from_history_not_fixed_multiplier():
    origin = date(2025, 7, 28)
    days = pd.date_range("2024-01-01", origin-timedelta(days=1))
    context = daily_context(days)
    history = pd.DataFrame({"date": days, "ingredient_id": 1,
                            "quantity": np.where(context.is_holiday, 60., 10.)})
    with_context = forecast_demand(history, catalog(), origin, 1)
    without_context = forecast_demand(history, catalog(), origin, 1, strategy="auto_no_context")
    assert with_context.context_used.iloc[0]
    assert with_context.comparable_days.iloc[0] >= 16
    assert with_context.predicted.iloc[0] > without_context.predicted.iloc[0] + 15
    # Sparse history does not gain a made-up uplift merely because it is a holiday.
    short = history.tail(3)
    baseline = forecast_demand(short, catalog(), origin, 1)
    assert baseline.predicted.iloc[0] == 10
    assert not baseline.context_used.iloc[0]


def test_known_event_can_change_forecast_but_not_rewrite_past_origins():
    origin = date(2025, 5, 1)
    days = pd.date_range("2025-01-01", origin-timedelta(days=1))
    special = [day for day in days if day.day % 11 == 0]
    events = pd.DataFrame([event(str(day.date()), id=index+1) for index, day in enumerate(special)] +
                          [event(str(origin), id=100)])
    history = pd.DataFrame({"date": days, "ingredient_id": 1,
                            "quantity": [70. if day in special else 10. for day in days]})
    expected = forecast_demand(history, catalog(), origin, 1, events=events)
    no_future_event = forecast_demand(history, catalog(), origin, 1, events=events[events.id != 100])
    assert expected.predicted.iloc[0] > no_future_event.predicted.iloc[0] + 15
    events.loc[events.id == 100, "recorded_on"] = str(origin)
    too_late = forecast_demand(history, catalog(), origin, 1, events=events)
    pd.testing.assert_frame_equal(no_future_event, too_late)


def test_closure_zeroes_demand_and_reserve_even_with_short_history():
    history = pd.DataFrame([dict(date="2026-11-20", ingredient_id=1, quantity=10.)])
    events = pd.DataFrame([event("2026-11-23", "closure", "Mantenimiento", "2026-11-22")])
    prediction = forecast_demand(history, catalog(), "2026-11-23", 1, events=events)
    assert not prediction.is_open.iloc[0]
    assert prediction.predicted.iloc[0] == 0
    plan = purchase_plan(prediction, pd.DataFrame(), catalog())
    assert plan.suggested_quantity.iloc[0] == 0
    assert plan.context_label.iloc[0] == "Mantenimiento"


def test_evaluation_filters_late_event_annotations_and_compares_context():
    days = pd.date_range("2025-01-01", periods=84)
    history = pd.DataFrame({"date": days, "ingredient_id": 1, "quantity": 10.})
    future_annotations = pd.DataFrame([event(str(day.date()), "closure", recorded_on="2025-12-01", id=n+1)
                                       for n, day in enumerate(days[-7:])])
    summary, expected = rolling_evaluation(history, catalog(), folds=1, compare_context=True)
    _, actual = rolling_evaluation(history, catalog(), folds=1, compare_context=True, events=future_annotations)
    assert set(summary.strategy) == {"auto", "auto_no_context", "mean", "seasonal"}
    pd.testing.assert_series_equal(expected.predicted, actual.predicted)
