"""Chronological tuning and rolling seven-day forecasts with past-only demand features."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from restaurante.evaluation import error_metrics


@dataclass(frozen=True)
class ExperimentConfig:
    train_end: str = "2025-05-31"
    validation_end: str = "2025-09-15"
    horizon: int = 7
    seed: int = 42
    models: tuple = ("seasonal", "random_forest", "xgboost", "lstm")
    external_variants: tuple = (False, True)
    lstm_epochs: int = 12


MODEL_NAMES = {"seasonal": "Ingenuo estacional", "random_forest": "Random Forest",
               "xgboost": "XGBoost", "lstm": "LSTM"}
WINDOW = 14


def available_models():
    return {"seasonal": True, "random_forest": True,
            "xgboost": importlib.util.find_spec("xgboost") is not None,
            "lstm": importlib.util.find_spec("tensorflow") is not None}


def validate_demand(demand, config):
    data = demand.copy()
    required = {"date", "profile", "ingredient", "demand", "is_open",
                "expected_temperature", "holiday", "payday"}
    if not required <= set(data) or data.empty:
        raise ValueError("El dataset no tiene el esquema insumo-día requerido.")
    data["date"] = pd.to_datetime(data.date)
    if data.duplicated(["profile", "ingredient", "date"]).any():
        raise ValueError("Hay registros insumo-día duplicados.")
    for column in ("demand", "expected_temperature", "holiday", "payday"):
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not np.isfinite(data[column]).all():
            raise ValueError("El dataset contiene valores no finitos.")
    if (data.demand < 0).any() or not data.is_open.isin([True, False, 0, 1]).all():
        raise ValueError("Demanda no negativa y atención como verdadero/falso.")
    if (data.loc[~data.is_open.astype(bool), "demand"] != 0).any():
        raise ValueError("Un día cerrado no puede tener demanda.")
    if not data.holiday.isin([0, 1]).all() or not data.payday.isin([0, 1]).all():
        raise ValueError("Feriados y quincena deben ser 0/1.")
    train_end, val_end = pd.Timestamp(config.train_end), pd.Timestamp(config.validation_end)
    if not train_end < val_end or not 1 <= config.horizon <= 7:
        raise ValueError("Revisa las fechas y el horizonte (1 a 7 días).")
    if not config.models or not set(config.models) <= set(MODEL_NAMES):
        raise ValueError("Selecciona modelos válidos.")
    if not config.external_variants or not set(config.external_variants) <= {False, True}:
        raise ValueError("Selecciona variantes con/sin variables externas.")
    if not 1 <= config.lstm_epochs <= 100:
        raise ValueError("Usa entre 1 y 100 épocas para LSTM.")
    expected_dates = pd.date_range(data.date.min(), data.date.max())
    for _, group in data.groupby(["profile", "ingredient"]):
        if not pd.DatetimeIndex(group.date.sort_values()).equals(expected_dates):
            raise ValueError("Cada serie necesita todos los días; no conviertas faltantes en ceros.")
    counts = [int((expected_dates <= train_end).sum()),
              int(((expected_dates > train_end) & (expected_dates <= val_end)).sum()),
              int((expected_dates > val_end).sum())]
    if counts[0] < 56 or min(counts[1:]) < 14:
        raise ValueError("Se necesitan al menos 56 días de entrenamiento, 14 de validación y 14 de prueba.")
    return data.sort_values(["profile", "ingredient", "date"]).reset_index(drop=True)


class Forecaster:
    """A pooled model, with series identities and training-only target scales."""

    def __init__(self, model, external, size, config):
        self.kind, self.external, self.size, self.config = model, external, size, config

    def _window(self, values, row, series):
        scale = self.scales[series]
        past = np.asarray(values[-WINDOW:], float) / scale
        identity = np.zeros(len(self.keys))
        identity[self.keys.index(series)] = 1
        day = row.date
        known = [np.sin(2*np.pi*day.day_of_week/7), np.cos(2*np.pi*day.day_of_week/7),
                 np.sin(2*np.pi*day.day_of_year/365.25), np.cos(2*np.pi*day.day_of_year/365.25),
                 float(row.is_open)]
        if self.external:
            known += [row.expected_temperature / 30, row.holiday, row.payday]
        return np.column_stack([past, np.tile(np.r_[known, identity], (WINDOW, 1))])

    def fit(self, data):
        groups = list(data.groupby(["profile", "ingredient"], sort=True))
        self.keys = [key for key, _ in groups]
        self.scales = {key: max(float(group.demand.mean()), .01) for key, group in groups}
        x, y = [], []
        for key, group in groups:
            values = group.demand.to_numpy()
            for position, row in enumerate(group.itertuples(index=False)):
                if position >= WINDOW:
                    x.append(self._window(values[:position], row, key))
                    y.append(row.demand / self.scales[key])
        x, y = np.asarray(x, np.float32), np.asarray(y, np.float32)
        if self.kind == "random_forest":
            self.model = RandomForestRegressor(n_estimators=70, max_depth=self.size,
                                              min_samples_leaf=3, n_jobs=1,
                                              random_state=self.config.seed)
        elif self.kind == "xgboost":
            from xgboost import XGBRegressor
            self.model = XGBRegressor(n_estimators=90, max_depth=self.size, learning_rate=.06,
                                      objective="reg:squarederror", tree_method="hist", n_jobs=1,
                                      random_state=self.config.seed)
        elif self.kind == "lstm":
            os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "1")
            os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")
            import tensorflow as tf
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(self.config.seed)
            self.model = tf.keras.Sequential([
                tf.keras.Input(shape=x.shape[1:]), tf.keras.layers.LSTM(self.size),
                tf.keras.layers.Dense(1)])
            self.model.compile(optimizer=tf.keras.optimizers.Adam(.005), loss="mse")
            # Explicit batches avoid background tf.data pools on constrained local machines.
            for _ in range(self.config.lstm_epochs):
                for start in range(0, len(y), 64):
                    self.model.train_on_batch(x[start:start+64], y[start:start+64])
            return self
        else:
            raise ValueError("Modelo no entrenable.")
        self.model.fit(x.reshape(len(x), -1), y)
        return self

    def predict(self, history, targets):
        """Demand inside a block is predicted recursively, never read from targets."""
        values = {key: group.demand.tolist() for key, group in history.groupby(["profile", "ingredient"])}
        rows = []
        for _, day in targets.groupby("date", sort=True):
            features, keys, records = [], [], []
            for row in day.itertuples(index=False):
                key = (row.profile, row.ingredient)
                features.append(self._window(values[key], row, key))
                keys.append(key)
                records.append(row)
            x = np.asarray(features, np.float32)
            estimates = (np.asarray(self.model(x, training=False)).reshape(-1)
                         if self.kind == "lstm" else self.model.predict(x.reshape(len(x), -1)))
            for key, row, estimate in zip(keys, records, estimates, strict=True):
                prediction = max(0., float(estimate) * self.scales[key]) if row.is_open else 0.
                if not np.isfinite(prediction):
                    raise ValueError("El modelo produjo un pronóstico no finito.")
                values[key].append(prediction)
                rows.append({"date": row.date, "profile": row.profile, "ingredient": row.ingredient,
                             "actual": row.demand, "predicted": prediction})
        return pd.DataFrame(rows)


def rolling_predict(data, model, start, horizon, stride=None):
    results = []
    last = data.date.max()
    for origin in pd.date_range(start, last, freq=f"{stride or horizon}D"):
        history = data[data.date < origin]
        targets = data[(data.date >= origin) & (data.date < origin + pd.Timedelta(days=horizon))]
        if model is not None:
            block = model.predict(history, targets)
        else:
            lookup = {(r.profile, r.ingredient, r.date): r.demand for r in history.itertuples()}
            rows = []
            for row in targets.sort_values("date").itertuples():
                prediction = lookup[(row.profile, row.ingredient, row.date-pd.Timedelta(days=7))] if row.is_open else 0.
                lookup[(row.profile, row.ingredient, row.date)] = prediction
                rows.append({"date": row.date, "profile": row.profile, "ingredient": row.ingredient,
                             "actual": row.demand, "predicted": prediction})
            block = pd.DataFrame(rows)
        block["origin"] = origin
        results.append(block)
    return pd.concat(results, ignore_index=True)


def metrics_by_series(predictions):
    rows = []
    for key, group in predictions.groupby(["model", "external", "profile", "ingredient"]):
        actual, predicted = group.actual.to_numpy(), group.predicted.to_numpy()
        denominator = float(np.sum((actual-actual.mean())**2))
        rows.append(dict(zip(["model", "external", "profile", "ingredient"], key, strict=True)) |
                    error_metrics(actual, predicted) |
                    {"r2": 1-float(np.sum((actual-predicted)**2))/denominator if denominator else None})
    return pd.DataFrame(rows)


def compare_models(demand, config=ExperimentConfig(), progress=None):
    data = validate_demand(demand, config)
    train_end, val_end = pd.Timestamp(config.train_end), pd.Timestamp(config.validation_end)
    training, development = data[data.date <= train_end], data[data.date <= val_end]
    validation_start, test_start = train_end + pd.Timedelta(days=1), val_end + pd.Timedelta(days=1)
    details, tuning, statuses = [], [], []
    winner_model = None
    winner_score = float("inf")
    availability = available_models()
    for kind in config.models:
        if not availability[kind]:
            statuses.append({"model": kind, "status": "No ejecutado: instala el extra research localmente"})
            continue
        variants = (False,) if kind == "seasonal" else config.external_variants
        for external in variants:
            if progress:
                progress(f"{MODEL_NAMES[kind]} · {'con' if external else 'sin'} variables externas")
            best_score, best_size = float("inf"), None
            sizes = {"seasonal": [None], "random_forest": [4, 8], "xgboost": [2, 4], "lstm": [8, 16]}[kind]
            for size in sizes:
                model = None if kind == "seasonal" else Forecaster(kind, external, size, config).fit(training)
                validation = rolling_predict(development, model, validation_start, config.horizon)
                validation["model"], validation["external"] = kind, external
                scores = metrics_by_series(validation)
                score = float(scores.wape_percent.dropna().mean()) if scores.wape_percent.notna().any() else float(scores.mae.mean())
                tuning.append({"model": kind, "external": external, "size": size,
                               "validation_score": score, "score_definition": "Media WAPE por serie; MAE si todas son cero"})
                if score < best_score:
                    best_score, best_size = score, size
            model = None if kind == "seasonal" else Forecaster(kind, external, best_size, config).fit(development)
            prediction = rolling_predict(data, model, test_start, config.horizon)
            prediction["model"], prediction["external"] = kind, external
            details.append(prediction)
            statuses.append({"model": kind, "external": external, "status": "Ejecutado",
                             "chosen_size": best_size, "validation_score": best_score})
            if best_score < winner_score:
                winner_model, winner_score = model, best_score
    detail = pd.concat(details, ignore_index=True) if details else pd.DataFrame()
    metrics = metrics_by_series(detail) if len(detail) else pd.DataFrame()
    completed = [row for row in statuses if row["status"] == "Ejecutado"]
    # Winner fixed on validation, never selected on held-out test scores.
    winner = min(completed, key=lambda row: row["validation_score"]) if completed else None
    decisions = rolling_predict(data, winner_model, test_start, config.horizon, stride=1) if winner else pd.DataFrame()
    return {"metrics": metrics, "predictions": detail, "decision_predictions": decisions,
            "tuning": pd.DataFrame(tuning),
            "model_status": pd.DataFrame(statuses),
            "experiment": {"config": asdict(config), "winner": winner,
                           "selection": "Media WAPE de validación; prueba reservada para informar resultados",
                           "protocol": "Modelo fijo tras entrenamiento+validación; bloques recursivos sin observar demanda interna; historial actualizado entre bloques",
                           "weather": "Temperatura esperada conocida; no temperatura futura observada"}}
