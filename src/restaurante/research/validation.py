"""Scores are computed only from explicitly supplied, anonymous human responses."""

import numpy as np
import pandas as pd


def sus_scores(responses):
    columns = [f"q{i}" for i in range(1, 11)]
    if not {"participant", *columns} <= set(responses) or responses.empty:
        raise ValueError("SUS necesita participant y q1 a q10.")
    if responses.participant.isna().any() or responses.participant.duplicated().any():
        raise ValueError("Usa un código anónimo único por participante.")
    values = responses[columns].apply(pd.to_numeric, errors="raise")
    if not values.isin(range(1, 6)).all().all():
        raise ValueError("Cada respuesta SUS debe ser un entero entre 1 y 5.")
    contribution = values.copy()
    contribution.iloc[:, ::2] = values.iloc[:, ::2]-1
    contribution.iloc[:, 1::2] = 5-values.iloc[:, 1::2]
    return pd.DataFrame({"participant": responses.participant, "sus": contribution.sum(axis=1)*2.5})


def aiken_scores(responses):
    if not {"expert", "item", "rating"} <= set(responses) or responses.empty:
        raise ValueError("Aiken necesita expert, item y rating (escala de 1 a 5).")
    if responses[["expert", "item"]].isna().any().any() or responses.duplicated(["expert", "item"]).any():
        raise ValueError("Usa un código único por experto y criterio.")
    frame = responses.copy()
    frame["rating"] = pd.to_numeric(frame.rating, errors="raise")
    if not frame.rating.isin(range(1, 6)).all():
        raise ValueError("Las valoraciones deben ser enteros entre 1 y 5.")
    experts = set(frame.expert)
    if any(set(group.expert) != experts for _, group in frame.groupby("item")):
        raise ValueError("Todos los expertos deben evaluar todos los criterios.")
    return frame.groupby("item").rating.agg(experts="count", mean="mean").reset_index().assign(
        aiken_v=lambda df: (df["mean"]-1)/4)


def paired_forecast_tests(predictions, horizon=7):
    """Approximate Diebold-Mariano, squared loss, Bartlett HAC through h-1 lags.

    Per-series, exploratory p values; no claim of family-wise error control.
    Constant loss differences do not receive a spurious significant result.
    """
    from scipy.stats import norm
    baseline = predictions[predictions.model == "seasonal"]
    keys = ["date", "origin", "profile", "ingredient"]
    rows = []
    for (model, external, profile, ingredient), group in predictions[predictions.model != "seasonal"].groupby(
            ["model", "external", "profile", "ingredient"]):
        paired = group.merge(baseline[keys+["predicted"]], on=keys, suffixes=("", "_baseline"), validate="1:1")
        if paired.empty:
            continue
        paired = paired.sort_values("date")
        difference = ((paired.actual-paired.predicted_baseline)**2 - (paired.actual-paired.predicted)**2).to_numpy()
        centered, n = difference-difference.mean(), len(difference)
        lag = min(horizon-1, n-1)
        variance = float(centered@centered/n)
        for offset in range(1, lag+1):
            variance += 2*(1-offset/(lag+1))*float(centered[offset:]@centered[:-offset]/n)
        statistic = float(difference.mean()/np.sqrt(variance/n)) if variance > 1e-12 else None
        rows.append({"model": model, "external": external, "profile": profile,
                     "ingredient": ingredient, "observations": n, "hac_lags": lag,
                     "dm_approx": statistic,
                     "p_value_exploratory": float(2*norm.sf(abs(statistic))) if statistic is not None else None,
                     "mean_squared_loss_improvement": float(difference.mean())})
    return pd.DataFrame(rows)
