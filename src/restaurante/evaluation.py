"""Reproducible rolling-origin evaluation on complete observations, never random splits."""

import numpy as np
import pandas as pd

from .forecast import forecast_demand


def error_metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if not len(actual) or actual.shape != predicted.shape:
        raise ValueError("Se necesitan pares de observaciones y pronósticos.")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all() \
            or (actual < 0).any() or (predicted < 0).any():
        raise ValueError("Las cantidades deben ser finitas y no negativas.")
    error = predicted - actual
    nonzero = actual > 0
    return {
        "observations": len(actual),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "bias": float(error.mean()),
        "wape_percent": float(np.abs(error).sum() / actual.sum() * 100)
        if actual.sum() else None,
        "mape_percent": float(np.mean(np.abs(error[nonzero]) / actual[nonzero]) * 100)
        if nonzero.any() else None,
        "mape_excluded_zeros": int((~nonzero).sum()),
    }


def rolling_evaluation(history, ingredients, horizon=7, folds=3, min_train_days=56,
                       events=None, compare_context=False):
    """Fixed non-overlapping test blocks; report errors by ingredient and strategy.

    Folds use only known target days. Missing target days are excluded, not scored as zero.
    Predictions for later days in each block cannot see earlier test-block observations.
    """
    if not isinstance(folds, int) or isinstance(folds, bool) or not 1 <= folds <= 10:
        raise ValueError("Usa entre 1 y 10 bloques temporales.")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 7:
        raise ValueError("Usa un horizonte entre 1 y 7 días.")
    if history.empty:
        return pd.DataFrame(), pd.DataFrame()
    data = history.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.date
    last = max(data["date"])
    rows = []
    for fold in range(folds):
        origin = last - pd.Timedelta(days=(fold + 1) * horizon - 1)
        training = data[data["date"] < origin]
        counts = training.groupby("ingredient_id")["date"].nunique()
        eligible = ingredients[ingredients["id"].isin(counts[counts >= min_train_days].index)]
        if eligible.empty:
            continue
        truth = data.groupby(["date", "ingredient_id"], as_index=False)["quantity"].sum()
        strategies = ("auto", "auto_no_context", "mean", "seasonal") if compare_context else ("auto", "mean", "seasonal")
        for strategy in strategies:
            predictions = forecast_demand(training, eligible, origin, horizon, strategy=strategy,
                                          events=events)
            predictions["date"] = pd.to_datetime(predictions["date"]).dt.date
            scored = predictions.merge(truth, on=["date", "ingredient_id"], how="inner")
            scored["strategy"] = strategy
            scored["origin"] = origin.isoformat()
            rows.extend(scored.to_dict("records"))
    detail = pd.DataFrame(rows)
    summaries = []
    if not detail.empty:
        for (ingredient_id, strategy), group in detail.groupby(["ingredient_id", "strategy"]):
            summaries.append({"ingredient_id": ingredient_id, "strategy": strategy,
                              **error_metrics(group["quantity"], group["predicted"])})
    return pd.DataFrame(summaries), detail
