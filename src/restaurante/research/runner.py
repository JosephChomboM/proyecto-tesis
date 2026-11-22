"""Local experiment entry point; no remote services or paid infrastructure required."""

import argparse
import importlib.metadata
import json
import platform
from pathlib import Path

import pandas as pd

from .data import GenerationConfig, bundle_zip, example_tables, generate
from .models import ExperimentConfig, compare_models
from .simulation import InventoryConfig, paired_replica_summary, simulate
from .validation import paired_forecast_tests


def run_experiment(bundle, config=ExperimentConfig(), inventory=InventoryConfig(), progress=None):
    if int(bundle["ingredients"].lead_days.max()) >= config.horizon:
        raise ValueError("El horizonte debe superar el mayor plazo de entrega.")
    results = compare_models(bundle["demand"], config, progress)
    if results["experiment"]["winner"] is None:
        raise ValueError("No se ejecutó ningún modelo.")
    results.update(simulate(bundle["demand"], results["decision_predictions"], bundle["ingredients"], inventory))
    results["forecast_tests"] = paired_forecast_tests(results["predictions"], config.horizon)
    stability = []
    from restaurante.evaluation import error_metrics
    for key, group in results["predictions"].groupby(["model", "external", "profile", "ingredient", "origin"]):
        stability.append(dict(zip(["model", "external", "profile", "ingredient", "origin"], key, strict=True)) |
                         error_metrics(group.actual, group.predicted))
    results["forecast_blocks"] = pd.DataFrame(stability)
    versions = {"python": platform.python_version()}
    for package in ("numpy", "pandas", "scikit-learn", "scipy", "xgboost", "tensorflow"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "no instalado"
    results["environment"] = versions
    results["metadata"] = bundle["metadata"]
    results["metadata"] = dict(results["metadata"], result_scope="Experimento sintético; no valida impacto en negocios reales")
    return results


def main():
    parser = argparse.ArgumentParser(description="Genera datos y ejecuta experimentos locales de la tesis.")
    parser.add_argument("--output", default="data/research")
    parser.add_argument("--config-dir", help="Carpeta con profiles.csv, recipes.csv, ingredients.csv y context.csv opcional")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--templates", action="store_true")
    parser.add_argument("--models", default="seasonal,random_forest,xgboost,lstm")
    parser.add_argument("--seeds", default="42", help="Ejemplo: 42,43,44,45,46")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--train-end", default="2025-05-31")
    parser.add_argument("--validation-end", default="2025-09-15")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--empirical-days", type=int, default=28)
    parser.add_argument("--safety-days", type=float, default=.2)
    parser.add_argument("--initial-days", type=float, default=1.)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    tables = example_tables()
    if args.templates:
        for name, frame in zip(("profiles", "recipes", "ingredients"), tables, strict=True):
            frame.to_csv(output/f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"Plantillas de ejemplo guardadas en {output.resolve()}")
        return
    context = None
    if args.config_dir:
        folder = Path(args.config_dir)
        tables = tuple(pd.read_csv(folder/f"{name}.csv", keep_default_na=False)
                       for name in ("profiles", "recipes", "ingredients"))
        if (folder/"context.csv").exists():
            context = pd.read_csv(folder/"context.csv")
    config = ExperimentConfig(train_end=args.train_end, validation_end=args.validation_end,
                              models=tuple(args.models.split(",")), lstm_epochs=args.epochs)
    replications, series_replications = [], []
    seeds = [int(value) for value in args.seeds.split(",")]
    if len(seeds) != len(set(seeds)):
        parser.error("Las semillas de las réplicas deben ser distintas.")
    for seed in seeds:
        print(f"Semilla {seed}", flush=True)
        bundle = generate(GenerationConfig(args.start, args.end, seed), tables, context)
        (output/f"dataset-{seed}.zip").write_bytes(bundle_zip(bundle))
        if args.generate_only:
            continue
        results = run_experiment(bundle, config,
            InventoryConfig(args.empirical_days, args.safety_days, args.initial_days),
            progress=lambda message: print(message, flush=True))
        (output/f"results-{seed}.zip").write_bytes(bundle_zip(results))
        for name, value in results.items():
            if isinstance(value, pd.DataFrame):
                value.to_csv(output/f"{name}-{seed}.csv", index=False, encoding="utf-8-sig")
        for policy, group in results["inventory_summary"].groupby("policy"):
            replications.append({"seed": seed, "policy": policy,
                                 "waste_cost": float(group.waste_cost.sum()),
                                 "stockout": int(group.stockout.sum())})
        series_replications.extend(dict(row, seed=seed) for row in results["inventory_summary"].to_dict("records"))
        print(json.dumps(results["experiment"], ensure_ascii=False), flush=True)
    if replications:
        paired_replica_summary(replications).to_csv(output/"paired_replications.csv", index=False)
        pd.DataFrame(replications).to_csv(output/"replications.csv", index=False)
        series_frame = pd.DataFrame(series_replications)
        paired_series = []
        for (profile, ingredient, unit), group in series_frame.groupby(["profile", "ingredient", "unit"]):
            scores = paired_replica_summary(group, indicators=("expired", "waste_cost", "stockout"))
            scores["profile"], scores["ingredient"], scores["unit"] = profile, ingredient, unit
            paired_series.append(scores)
        pd.concat(paired_series, ignore_index=True).to_csv(output/"paired_replications_by_ingredient.csv", index=False)
        series_frame.to_csv(output/"replications_by_ingredient.csv", index=False)
    print(f"Archivos guardados en {output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
