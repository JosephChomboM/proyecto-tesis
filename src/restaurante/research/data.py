"""Small editable configuration tables and explicitly uncalibrated example scenarios."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .calendar import HOLIDAY_SOURCES, national_holidays


@dataclass(frozen=True)
class GenerationConfig:
    start: str = "2024-01-01"
    end: str = "2025-12-31"
    seed: int = 42
    noise: float = 0.18
    shock_probability: float = 0.03
    calibration_status: str = "Supuestos de ejemplo; pendiente de fuentes y juicio de expertos"


def example_tables():
    """Amounts are illustrative raw-input recipes, not nutritional or safety advice."""
    profiles = pd.DataFrame([
        ["menu", "Menú criollo", "Arroz con pollo", 40, "0,1,2,3,4,5", .75, 1., .0],
        ["menu", "Menú criollo", "Lentejas con arroz", 25, "0,1,2,3,4,5", .75, 1., .0],
        ["cevicheria", "Cevichería", "Ceviche", 35, "0,1,2,3,4,5,6", 1.35, 1.15, .035],
        ["cevicheria", "Cevichería", "Arroz con mariscos", 20, "0,1,2,3,4,5,6", 1.25, 1.1, .015],
        ["polleria", "Pollería", "Cuarto de pollo", 65, "0,1,2,3,4,5,6", 1.5, 1.2, .0],
        ["polleria", "Pollería", "Medio pollo", 20, "0,1,2,3,4,5,6", 1.5, 1.2, .0],
    ], columns=["profile", "restaurant", "dish", "daily_portions", "weekdays",
                "weekend_factor", "holiday_factor", "heat_effect"])
    recipes = pd.DataFrame([
        ["Arroz con pollo", "arroz", .12], ["Arroz con pollo", "pollo", .25],
        ["Lentejas con arroz", "arroz", .10], ["Lentejas con arroz", "lenteja", .10],
        ["Ceviche", "pescado", .25], ["Ceviche", "limon", .10],
        ["Arroz con mariscos", "arroz", .12], ["Arroz con mariscos", "mariscos", .20],
        ["Cuarto de pollo", "pollo", .35], ["Cuarto de pollo", "papa", .25],
        ["Medio pollo", "pollo", .70], ["Medio pollo", "papa", .50],
    ], columns=["dish", "ingredient", "quantity"])
    ingredients = pd.DataFrame([
        ["arroz", "Arroz", "kg", 4., 5., 90, 1],
        ["pollo", "Pollo", "kg", 11., 1., 2, 1],
        ["lenteja", "Lenteja", "kg", 8., 1., 90, 1],
        ["pescado", "Pescado", "kg", 18., 1., 1, 0],
        ["limon", "Limón", "kg", 5., 1., 5, 1],
        ["mariscos", "Mariscos", "kg", 22., 1., 1, 0],
        ["papa", "Papa", "kg", 3., 5., 7, 1],
    ], columns=["ingredient", "name", "unit", "cost", "pack_size", "shelf_life_days",
                "lead_days"])
    for frame in (profiles, recipes, ingredients):
        frame["source"] = "Supuesto ilustrativo pendiente de validación"
    return profiles, recipes, ingredients


def _numeric(frame, columns, positive=True):
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        values = frame[column].to_numpy(float)
        if not np.isfinite(values).all() or (values < 0).any() or (positive and (values == 0).any()):
            raise ValueError(f"{column}: usa cantidades finitas {'positivas' if positive else 'no negativas'}.")


def validate_tables(profiles, recipes, ingredients):
    defaults = example_tables()
    tables = [frame.copy() for frame in (profiles, recipes, ingredients)]
    for table, template in zip(tables, defaults, strict=True):
        missing = set(template.columns) - set(table.columns)
        if missing or table.empty or table.isna().any().any():
            raise ValueError(f"Tabla vacía, valores incompletos o columnas ausentes: {sorted(missing)}")
        if len(table) > 100:
            raise ValueError("Máximo 100 filas por tabla de configuración.")
        if table["source"].astype(str).str.strip().eq("").any():
            raise ValueError("Documenta una fuente o supuesto para cada fila.")
    p, r, i = tables
    if p["dish"].duplicated().any() or i["ingredient"].duplicated().any() or r.duplicated(["dish", "ingredient"]).any():
        raise ValueError("Platos, códigos de insumo y componentes de receta deben ser únicos.")
    if not set(r.dish) == set(p.dish) or not set(r.ingredient).issubset(set(i.ingredient)):
        raise ValueError("Cada plato necesita receta y los insumos deben existir en el catálogo.")
    _numeric(p, ["daily_portions", "weekend_factor", "holiday_factor"])
    _numeric(p, ["heat_effect"], positive=False)
    _numeric(r, ["quantity"])
    _numeric(i, ["cost"], positive=False)
    _numeric(i, ["pack_size", "shelf_life_days"])
    _numeric(i, ["lead_days"], positive=False)
    if (i.shelf_life_days % 1).any() or (i.lead_days % 1).any() or (i.lead_days > 7).any():
        raise ValueError("Vida útil y plazo deben ser días enteros; el plazo máximo es siete días.")
    for value in p.weekdays:
        try:
            days = {int(x.strip()) for x in str(value).split(",")}
        except ValueError as exc:
            raise ValueError("Días de atención: escribe 0,1,2…6 (lunes a domingo).") from exc
        if not days or not days <= set(range(7)):
            raise ValueError("Los días de atención van de 0 (lunes) a 6 (domingo).")
    return p, r, i


def make_context(dates, context=None):
    """Future temperature is an assumed climatology, never observed future weather."""
    frame = pd.DataFrame({"date": pd.DatetimeIndex(dates)})
    frame["expected_temperature"] = 21 + 4 * np.cos(2 * np.pi * (frame.date.dt.day_of_year - 45) / 365.25)
    holidays = national_holidays()
    frame["holiday"] = frame.date.isin(holidays).astype(int)
    frame["context_source"] = frame.date.dt.year.map(
        lambda year: f"Climatología sintética ilustrativa; feriados: {HOLIDAY_SOURCES.get(year, 'NO DISPONIBLES para este año')}")
    if context is not None:
        required = {"date", "expected_temperature", "holiday", "context_source"}
        if not required <= set(context):
            raise ValueError(f"El contexto necesita {sorted(required)}.")
        supplied = context.copy()
        supplied["date"] = pd.to_datetime(supplied.date, errors="raise")
        if supplied.date.duplicated().any():
            raise ValueError("El contexto contiene fechas duplicadas.")
        frame = frame[["date"]].merge(supplied[list(required)], on="date", how="left", validate="1:1")
        if frame.isna().any().any():
            raise ValueError("El contexto debe cubrir todos los días, sin valores vacíos.")
        temps = pd.to_numeric(frame.expected_temperature, errors="raise")
        if not np.isfinite(temps).all() or not frame.holiday.isin([0, 1]).all():
            raise ValueError("Temperaturas finitas y feriados como 0/1.")
        frame["expected_temperature"] = temps
    frame["payday"] = frame.date.dt.day.isin([15, 30, 31]).astype(int)
    return frame


def generate(config=GenerationConfig(), tables=None, context=None):
    p, r, i = validate_tables(*(tables if tables is not None else example_tables()))
    start, end = pd.Timestamp(config.start), pd.Timestamp(config.end)
    if pd.isna(start) or pd.isna(end) or not 59 <= (end-start).days <= 1095:
        raise ValueError("Genera entre 60 y 1096 días.")
    dates = pd.date_range(start, end)
    if not isinstance(config.seed, int) or not 0 <= config.seed < 2**32:
        raise ValueError("La semilla debe ser un entero entre 0 y 4294967295.")
    if not 0 <= config.noise <= 1 or not 0 <= config.shock_probability <= .2:
        raise ValueError("Variación entre 0 y 1; probabilidad de imprevisto entre 0 y 0.2.")
    calendar = make_context(dates, context)
    rows = []
    for profile, group in p.groupby("profile", sort=True):
        # Independent stable stream per profile: adding a profile cannot change the others.
        key = int.from_bytes(hashlib.sha256(str(profile).encode()).digest()[:4], "little")
        rng = np.random.default_rng(np.random.SeedSequence([config.seed, key]))
        shared_noise = rng.lognormal(-config.noise**2 / 2, config.noise, len(dates))
        shocks = np.where(rng.random(len(dates)) < config.shock_probability,
                          rng.choice([.5, 1.5], len(dates)), 1.)
        for dish in group.to_dict("records"):
            weekdays = {int(x) for x in str(dish["weekdays"]).split(",")}
            for offset, day in enumerate(calendar.to_dict("records")):
                date = day["date"]
                opened = date.weekday() in weekdays
                mean = dish["daily_portions"] * shared_noise[offset] * shocks[offset]
                mean *= dish["weekend_factor"] if date.weekday() >= 5 else 1.
                mean *= dish["holiday_factor"] if day["holiday"] else 1.
                mean *= 1 + .05 * day["payday"]
                mean *= max(.2, 1 + dish["heat_effect"] * (day["expected_temperature"] - 21))
                if not np.isfinite(mean) or mean > 100000:
                    raise ValueError("Los parámetros generan una demanda fuera del límite de 100000 porciones/día.")
                rows.append({"date": date, "profile": profile, "dish": dish["dish"],
                             "is_open": opened, "demand_portions": int(rng.poisson(mean)) if opened else 0})
    dishes = pd.DataFrame(rows)
    needs = dishes.merge(r[["dish", "ingredient", "quantity"]], on="dish", validate="m:m")
    needs["demand"] = needs.demand_portions * needs.quantity
    demand = needs.groupby(["date", "profile", "ingredient"], as_index=False).demand.sum()
    demand = demand.merge(calendar, on="date", validate="m:1")
    status = dishes.groupby(["date", "profile"], as_index=False).is_open.max()
    demand = demand.merge(status, on=["date", "profile"], validate="m:1")
    metadata = {"schema_version": 1, "generation": asdict(config),
                "configuration": {"profiles": p.to_dict("records"), "recipes": r.to_dict("records"),
                                  "ingredients": i.to_dict("records")},
                "context_sha256": hashlib.sha256(calendar.to_csv(index=False).encode()).hexdigest(),
                "national_holiday_sources": HOLIDAY_SOURCES if context is None else "Contexto aportado por el usuario",
                "demand_sha256": hashlib.sha256(demand.to_csv(index=False).encode()).hexdigest(),
                "scope": "Demanda sintética de insumos crudos; no ventas reales ni sobrantes preparados",
                "assumptions": ["Se conocen todas las solicitudes, incluso las no atendidas",
                                "Recetas constantes; costos y plazos constantes",
                                "Temperatura esperada disponible al emitir el pronóstico",
                                "Vida útil supuesta bajo conservación adecuada; validar con expertos"],
                "sources_validated": False, "experts_completed": False}
    return {"profiles": p, "recipes": r, "ingredients": i, "context": calendar,
            "dish_demand": dishes, "demand": demand, "metadata": metadata}


def bundle_zip(bundle):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in bundle.items():
            if isinstance(value, pd.DataFrame):
                archive.writestr(f"{name}.csv", value.to_csv(index=False).encode("utf-8-sig"))
            else:
                archive.writestr(f"{name}.json", json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    return output.getvalue()


def read_bundle(content):
    """Read only the bounded research dataset format; verify and regenerate its contents."""
    csv_names = {"profiles", "recipes", "ingredients", "context", "dish_demand", "demand"}
    if not isinstance(content, bytes) or len(content) > 20_000_000:
        raise ValueError("Carga un ZIP de dataset de hasta 20 MB.")
    loaded, payloads = {}, {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        expected = {name+".csv" for name in csv_names} | {"metadata.json"}
        if set(names) != expected or len(names) != len(expected):
            raise ValueError("Carga dataset-SEMILLA.zip: no el paquete de resultados ni el ZIP general.")
        if sum(info.file_size for info in archive.infolist()) > 60_000_000:
            raise ValueError("Dataset descomprimido demasiado grande.")
        for name in csv_names:
            payloads[name] = archive.read(name+".csv").decode("utf-8-sig")
            loaded[name] = pd.read_csv(io.StringIO(payloads[name]), keep_default_na=False)
        metadata = json.loads(archive.read("metadata.json"))
    if not isinstance(metadata, dict) or not isinstance(metadata.get("generation"), dict):
        raise ValueError("El dataset no contiene su configuración de generación.")
    for name in ("demand", "context"):
        digest = hashlib.sha256(payloads[name].encode()).hexdigest()
        if metadata.get(name+"_sha256") != digest:
            raise ValueError(f"La huella de {name} no coincide: el archivo fue alterado.")
    config = GenerationConfig(**metadata["generation"])
    regenerated = generate(config, (loaded["profiles"], loaded["recipes"], loaded["ingredients"]), loaded["context"])
    for name in csv_names:
        actual, expected = loaded[name].copy(), regenerated[name].copy()
        if "date" in actual:
            actual["date"] = pd.to_datetime(actual.date)
        for column in actual.columns:
            if column == "is_open":
                if not actual[column].isin([True, False]).all():
                    raise ValueError("Atención debe ser verdadero o falso.")
        try:
            if set(actual.columns) == set(expected.columns):
                actual = actual[expected.columns]
            pd.testing.assert_frame_equal(actual.reset_index(drop=True), expected.reset_index(drop=True),
                                          check_dtype=False, check_exact=False, rtol=1e-10, atol=1e-10)
        except AssertionError as exc:
            raise ValueError(f"La tabla {name} no reproduce la configuración y semilla declaradas.") from exc
        regenerated[name] = regenerated[name][loaded[name].columns]
    regenerated["metadata"] = metadata
    return regenerated
