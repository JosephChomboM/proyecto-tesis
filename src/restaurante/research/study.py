"""Frozen, resumable thesis simulation protocol. No claim of empirical calibration."""

import argparse
import hashlib
import importlib.metadata
import json
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .data import GenerationConfig, bundle_zip, generate, read_bundle
from .models import ExperimentConfig, available_models
from .runner import run_experiment
from .simulation import InventoryConfig


def study_tables():
    assumption = "Supuesto experimental fijado antes de las pruebas; sin calibración con ventas reales ni expertos"
    profiles = pd.DataFrame([
        ["menu", "Menú criollo", "Arroz con pollo menu", 40, "0,1,2,3,4,5", .75, 1., 0.],
        ["menu", "Menú criollo", "Lentejas con bistec menu", 25, "0,1,2,3,4,5", .75, 1., 0.],
        ["menu", "Menú criollo", "Estofado de pollo menu", 20, "0,1,2,3,4,5", .75, 1., 0.],
        ["cevicheria", "Cevichería", "Ceviche personal", 35, "0,1,2,3,4,5,6", 1.35, 1.15, .035],
        ["cevicheria", "Cevichería", "Arroz con mariscos", 20, "0,1,2,3,4,5,6", 1.25, 1.1, .015],
        ["cevicheria", "Cevichería", "Chicharron de pescado", 15, "0,1,2,3,4,5,6", 1.3, 1.1, .02],
        ["polleria", "Pollería", "Cuarto de pollo", 65, "0,1,2,3,4,5,6", 1.5, 1.2, 0.],
        ["polleria", "Pollería", "Medio pollo", 20, "0,1,2,3,4,5,6", 1.5, 1.2, 0.],
        ["polleria", "Pollería", "Ensalada personal", 15, "0,1,2,3,4,5,6", 1.2, 1.05, 0.],
    ], columns=["profile", "restaurant", "dish", "daily_portions", "weekdays", "weekend_factor", "holiday_factor", "heat_effect"])
    components = {
        "Arroz con pollo menu": {"arroz": .12, "pollo": .25, "cebolla": .03, "aceite": .015, "cilantro": .01},
        "Lentejas con bistec menu": {"arroz": .10, "lenteja": .10, "res": .15, "cebolla": .03, "aceite": .012},
        "Estofado de pollo menu": {"pollo": .25, "papa": .18, "arroz": .10, "cebolla": .04, "aceite": .015, "cilantro": .005},
        "Ceviche personal": {"pescado": .25, "limon": .10, "cebolla": .06, "camote": .08, "maiz": .06},
        "Arroz con mariscos": {"arroz": .12, "mariscos": .20, "cebolla": .03, "aceite": .015, "limon": .02},
        "Chicharron de pescado": {"pescado": .22, "aceite": .025, "camote": .10, "maiz": .05, "limon": .03},
        "Cuarto de pollo": {"pollo": .35, "papa": .25, "aceite": .02, "lechuga": .025, "tomate": .03, "pepino": .02, "aji": .01, "sal": .003},
        "Medio pollo": {"pollo": .70, "papa": .50, "aceite": .04, "lechuga": .05, "tomate": .06, "pepino": .04, "aji": .02, "sal": .006},
        "Ensalada personal": {"lechuga": .10, "tomate": .10, "pepino": .10, "aceite": .005, "sal": .002, "aji": .005},
    }
    recipes = pd.DataFrame([{"dish": dish, "ingredient": ingredient, "quantity": quantity}
                            for dish, recipe in components.items() for ingredient, quantity in recipe.items()])
    ingredients = pd.DataFrame([
        ["arroz", "Arroz", 4., 5., 90, 1], ["pollo", "Pollo", 11., 1., 2, 1],
        ["cebolla", "Cebolla", 3., 1., 7, 1], ["aceite", "Aceite", 9., 1., 90, 1],
        ["cilantro", "Culantro", 8., .25, 2, 0], ["lenteja", "Lenteja", 8., 1., 90, 1],
        ["res", "Carne de res", 24., 1., 3, 1], ["papa", "Papa", 3., 5., 7, 1],
        ["pescado", "Pescado", 18., 1., 1, 0], ["limon", "Limón", 5., 1., 5, 1],
        ["camote", "Camote", 3., 1., 7, 1], ["maiz", "Choclo", 5., 1., 3, 1],
        ["mariscos", "Mariscos", 22., 1., 1, 0], ["lechuga", "Lechuga", 5., .5, 2, 0],
        ["tomate", "Tomate", 4., 1., 4, 1], ["pepino", "Pepino", 3., 1., 4, 1],
        ["aji", "Ají", 8., .25, 3, 1], ["sal", "Sal", 2., 1., 180, 1],
    ], columns=["ingredient", "name", "cost", "pack_size", "shelf_life_days", "lead_days"])
    ingredients["unit"] = "kg"
    for frame in (profiles, recipes, ingredients):
        frame["source"] = assumption
    return profiles, recipes, ingredients


def protocol():
    return {"version": 1, "study": "Estudio computacional de insumos en tres escenarios de restaurante",
            "pilot_seeds": list(range(1001, 1006)), "final_seeds": list(range(2001, 2031)),
            "generation": asdict(GenerationConfig()), "experiment": asdict(ExperimentConfig()),
            "inventory": asdict(InventoryConfig()), "tables": [frame.to_dict("records") for frame in study_tables()],
            "scope": "3 perfiles, 3 platos y 8 insumos seleccionados por perfil; 731 días; sin representatividad empírica",
            "replication_justification": "30 réplicas fijadas como presupuesto exploratorio; no estudio de potencia ni garantía de precisión o significancia",
            "pilot_rule": "Pilotos excluidos del contraste definitivo; no seleccionar semillas o parámetros por desempeño",
            "human_validation": "Aiken y SUS pendientes; no generar respuestas de participantes",
            "missing_components": "Recetas limitadas a los ocho insumos seleccionados; sin sobrantes preparados, aforo ni variación de costos",
            "mass_oil": "Aceite contabilizado en kg, no litros; costos supuestos por kg",
            "temperature": "Climatología sintética conocida; sin uso de tiempo futuro observado",
            "inventory_primary_endpoint": "Cantidad vencida por insumo; costo en soles y quiebres como medidas complementarias",
            "claims": "Cualquier conclusión queda condicionada a estos supuestos no calibrados"}


def implementation_hash():
    folder = Path(__file__).parent
    paths = [folder/name for name in ("study.py", "data.py", "models.py", "simulation.py", "validation.py", "runner.py", "calendar.py")]
    paths += [folder.parent/"evaluation.py"]
    return {str(path.relative_to(folder.parent)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def atomic_json(path, value):
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def run_study(output, phases=("pilot", "final")):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plan = protocol()
    plan["implementation_sha256"] = implementation_hash()
    # JSON roundtrip normalizes tuple/list representation for safe resume comparisons.
    plan = json.loads(json.dumps(plan, ensure_ascii=False))
    frozen_path = output/"protocolo_congelado.json"
    if frozen_path.exists() and json.loads(frozen_path.read_text(encoding="utf-8")) != plan:
        raise ValueError("El protocolo o la implementación cambió. Usa otra carpeta para otro estudio.")
    atomic_json(frozen_path, plan)
    if not all(available_models().values()):
        raise ValueError("Instala todos los modelos: pip install -e .[research]")
    config_folder = output/"configuracion"
    config_folder.mkdir(exist_ok=True)
    for name, frame in zip(("profiles", "recipes", "ingredients"), study_tables(), strict=True):
        frame.to_csv(config_folder/f"{name}.csv", index=False, encoding="utf-8-sig")
    config = ExperimentConfig()
    for phase in phases:
        seeds = plan["pilot_seeds" if phase == "pilot" else "final_seeds"]
        folder = output/phase
        folder.mkdir(exist_ok=True)
        for seed in seeds:
            dataset_path, result_path, status_path = (folder/f"dataset-{seed}.zip", folder/f"results-{seed}.zip", folder/f"completed-{seed}.json")
            if status_path.exists():
                saved = json.loads(status_path.read_text(encoding="utf-8"))
                for name, path in (("dataset_sha256", dataset_path), ("results_sha256", result_path)):
                    if hashlib.sha256(path.read_bytes()).hexdigest() != saved[name]:
                        raise ValueError(f"Los archivos de la semilla {seed} fueron alterados.")
                print(f"{phase} {seed}: ya verificado", flush=True)
                continue
            start = time.monotonic()
            print(f"INICIO {phase} {seed}", flush=True)
            bundle = generate(GenerationConfig(seed=seed), study_tables())
            dataset_path.write_bytes(bundle_zip(bundle))
            restored = read_bundle(dataset_path.read_bytes())
            pd.testing.assert_frame_equal(bundle["demand"], restored["demand"])
            results = run_experiment(bundle, config, progress=lambda message: print(f"{phase} {seed}: {message}", flush=True))
            if set(results["model_status"].model) != {"seasonal", "random_forest", "xgboost", "lstm"} or not results["model_status"].status.eq("Ejecutado").all():
                raise ValueError("Una ejecución no completó los cuatro modelos.")
            summary = results["inventory_summary"]
            import numpy as np
            np.testing.assert_allclose(summary.initial_stock+summary.received,
                                       summary.served+summary.expired+summary.final_stock, atol=1e-7)
            np.testing.assert_allclose(summary.demand, summary.served+summary.unmet, atol=1e-7)
            result_path.write_bytes(bundle_zip(results))
            complete = {"phase": phase, "seed": seed, "seconds": time.monotonic()-start,
                        "dish_rows": len(bundle["dish_demand"]), "demand_rows": len(bundle["demand"]),
                        "winner": results["experiment"]["winner"],
                        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
                        "results_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()}
            atomic_json(status_path, complete)
            atomic_json(output/"progreso.json", complete)
            print(f"TERMINADO {phase} {seed}: {complete['seconds']:.1f}s", flush=True)
    versions = {}
    for package in ("numpy", "pandas", "scikit-learn", "tensorflow", "xgboost", "scipy"):
        versions[package] = importlib.metadata.version(package)
    atomic_json(output/"versiones.json", versions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/estudio-tesis-2026-11-26")
    parser.add_argument("--phase", choices=["pilot", "final", "all"], default="all")
    args = parser.parse_args()
    run_study(args.output, ("pilot", "final") if args.phase == "all" else (args.phase,))


if __name__ == "__main__":
    main()
