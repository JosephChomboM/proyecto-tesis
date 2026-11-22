"""Scientific invariants: reproducibility, no target leakage and stock conservation."""

import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from restaurante.research.calendar import national_holidays
from restaurante.research.data import GenerationConfig, bundle_zip, example_tables, generate
from restaurante.research.models import (
    ExperimentConfig,
    Forecaster,
    available_models,
    compare_models,
    validate_demand,
)
from restaurante.research.report import cost_comparison, printable_experiment
from restaurante.research.runner import run_experiment
from restaurante.research.simulation import InventoryConfig, paired_replica_summary, simulate
from restaurante.research.ui import read_results
from restaurante.research.validation import aiken_scores, sus_scores


@pytest.fixture
def small_bundle():
    profiles, recipes, ingredients = example_tables()
    profiles = profiles[profiles.dish == "Arroz con pollo"]
    recipes = recipes[recipes.dish.isin(profiles.dish)]
    return generate(GenerationConfig("2024-01-01", "2024-04-29", 7),
                    (profiles, recipes, ingredients))


def small_config(**kwargs):
    return ExperimentConfig("2024-03-01", "2024-03-31", models=("seasonal", "random_forest"),
                            external_variants=(False,), **kwargs)


def test_generator_reproducible_recipes_closures_and_independent_profiles():
    full = generate()
    repeat = generate()
    pd.testing.assert_frame_equal(full["demand"], repeat["demand"])
    p, r, i = example_tables()
    p = p[p.profile == "menu"]
    r = r[r.dish.isin(p.dish)]
    single = generate(tables=(p, r, i))
    pd.testing.assert_frame_equal(full["demand"].query("profile == 'menu'").reset_index(drop=True),
                                  single["demand"].reset_index(drop=True))
    assert full["demand"].date.nunique() == 731
    assert not full["metadata"]["sources_validated"]
    assert (single["demand"].loc[~single["demand"].is_open, "demand"] == 0).all()
    # Chicken in the menu profile belongs only to arroz con pollo, at .25 kg/portion.
    dish = single["dish_demand"].query("dish == 'Arroz con pollo'").set_index("date")
    chicken = single["demand"].query("ingredient == 'pollo'").set_index("date")
    np.testing.assert_allclose(chicken.demand, dish.demand_portions*.25)


def test_generator_rejects_unlinked_recipe_and_incomplete_context():
    p, r, i = example_tables()
    r.loc[0, "ingredient"] = "inventado"
    with pytest.raises(ValueError, match="insumos"):
        generate(tables=(p, r, i))
    context = pd.DataFrame({"date": ["2024-01-01"], "expected_temperature": [22],
                            "holiday": [0], "context_source": ["prueba"]})
    with pytest.raises(ValueError, match="cubrir"):
        generate(context=context)


def test_recursive_forecasts_do_not_read_targets(small_bundle):
    data = validate_demand(small_bundle["demand"], small_config())
    history = data[data.date <= "2024-03-31"]
    targets = data[(data.date > "2024-03-31") & (data.date <= "2024-04-07")]
    model = Forecaster("random_forest", True, 4, small_config()).fit(history)
    first = model.predict(history, targets)
    modified = targets.copy()
    modified["demand"] = 999999
    second = model.predict(history, modified)
    np.testing.assert_allclose(first.predicted, second.predicted)


@pytest.mark.parametrize("kind,size", [("xgboost", 2), ("lstm", 8)])
def test_optional_models_train_real_estimators_and_forecast(small_bundle, kind, size):
    if not available_models()[kind]:
        pytest.skip("Dependencia de investigación opcional no instalada")
    config = small_config(lstm_epochs=1)
    data = validate_demand(small_bundle["demand"], config)
    history = data[data.date <= "2024-03-31"]
    targets = data[(data.date > "2024-03-31") & (data.date <= "2024-04-07")]
    model = Forecaster(kind, True, size, config).fit(history)
    prediction = model.predict(history, targets)
    assert len(prediction) == len(targets)
    assert np.isfinite(prediction.predicted).all()
    assert (prediction.predicted >= 0).all()


def test_changing_test_demand_does_not_select_hyperparameters(small_bundle):
    config = small_config()
    first = compare_models(small_bundle["demand"], config)
    modified = small_bundle["demand"].copy()
    mask = (modified.date > "2024-03-31") & modified.is_open
    modified.loc[mask, "demand"] *= 4
    second = compare_models(modified, config)
    pd.testing.assert_frame_equal(first["tuning"], second["tuning"])
    assert first["experiment"]["winner"] == second["experiment"]["winner"]
    assert first["predictions"].date.min() == pd.Timestamp("2024-04-01")
    pd.testing.assert_series_equal(first["decision_predictions"].query("origin == '2024-04-01'").predicted.reset_index(drop=True),
                                  second["decision_predictions"].query("origin == '2024-04-01'").predicted.reset_index(drop=True))


def test_full_experiment_conservation_and_roundtrip(small_bundle):
    result = run_experiment(small_bundle, small_config())
    summary = result["inventory_summary"]
    np.testing.assert_allclose(summary.initial_stock+summary.received,
                               summary.served+summary.expired+summary.final_stock, atol=1e-8)
    np.testing.assert_allclose(summary.demand, summary.served+summary.unmet)
    assert (summary.service_percent.between(0, 100)).all()
    assert not result["metrics"].empty
    imported = read_results(bundle_zip(result))
    assert imported["experiment"]["winner"] == result["experiment"]["winner"]
    assert len(imported["metrics"]) == len(result["metrics"])
    comparison = cost_comparison(summary)
    assert comparison["forecast_waste_cost"] >= 0
    result["metrics"].loc[0, "ingredient"] = "<script>alert(1)</script>"
    html = printable_experiment(result, {})
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_simulation_respects_lead_time_and_expiry():
    dates = pd.date_range("2024-01-01", periods=35)
    demand = pd.DataFrame({"date": dates, "profile": "p", "ingredient": "a", "demand": 2., "is_open": True})
    predictions = pd.DataFrame([{"origin": day, "date": target, "profile": "p", "ingredient": "a", "predicted": 2.}
                                for day in dates[28:] for target in pd.date_range(day, min(day+pd.Timedelta(days=1), dates[-1]))])
    catalog = pd.DataFrame([{"ingredient": "a", "unit": "kg", "cost": 3, "pack_size": 5, "shelf_life_days": 1, "lead_days": 1}])
    result = simulate(demand, predictions, catalog, InventoryConfig(initial_days=0, safety_days=0))
    detail = result["inventory_daily"]
    first = detail[detail.date == dates[28]]
    assert (first.served == 0).all()  # No same-day emergency purchase with one-day lead.
    second = detail[detail.date == dates[29]]
    assert (second.received == 5).all()
    third = detail[detail.date == dates[30]]
    assert (third.expired == 3).all()


def test_missing_days_are_not_silently_zero_filled(small_bundle):
    with pytest.raises(ValueError, match="todos los días"):
        validate_demand(small_bundle["demand"].iloc[1:], small_config())


def test_sus_and_aiken_require_actual_valid_responses():
    frame = pd.DataFrame([{"participant": "P01", **{f"q{i}": 5 if i % 2 else 1 for i in range(1, 11)}}])
    assert sus_scores(frame).sus.iloc[0] == 100
    frame["q1"] = 0
    with pytest.raises(ValueError):
        sus_scores(frame)
    ratings = pd.DataFrame({"expert": ["E1", "E2", "E3"], "item": "plausibilidad", "rating": [5, 4, 4]})
    assert aiken_scores(ratings).aiken_v.iloc[0] == pytest.approx(5/6)


def test_no_significance_claim_from_one_seed():
    rows = [{"seed": 42, "policy": "empirical", "waste_cost": 10, "stockout": 3},
            {"seed": 42, "policy": "forecast", "waste_cost": 8, "stockout": 2}]
    score = paired_replica_summary(rows)
    assert score.p_value.isna().all()
    assert score.relative_reduction_percent.iloc[0] == 20


def test_paired_replicas_keep_zero_denominator_undefined():
    rows = [{"seed": seed, "policy": policy, "waste_cost": 0, "stockout": 2}
            for seed in range(5) for policy in ("empirical", "forecast")]
    score = paired_replica_summary(rows)
    assert score.p_value.tolist() == [1., 1.]
    assert score.relative_reduction_percent.isna().iloc[0]


def test_peruvian_calendar_has_national_not_compensable_days():
    holidays = national_holidays()
    assert len(holidays) == 32
    assert pd.Timestamp("2024-03-28") in holidays
    assert pd.Timestamp("2025-04-17") in holidays
    assert pd.Timestamp("2024-07-26") not in holidays


def test_results_import_rejects_paths_and_non_result_archives():
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("../metadata.json", "{}")
    with pytest.raises(ValueError, match="Estructura"):
        read_results(content.getvalue())
    with pytest.raises(ValueError):
        read_results(bundle_zip(generate()))
