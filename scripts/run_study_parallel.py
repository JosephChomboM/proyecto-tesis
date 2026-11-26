"""Execute fixed final seeds in independent processes; same frozen scientific protocol."""

import argparse
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from restaurante.research.data import GenerationConfig, bundle_zip, generate, read_bundle
from restaurante.research.models import ExperimentConfig
from restaurante.research.runner import run_experiment
from restaurante.research.study import atomic_json, implementation_hash, protocol, study_tables


def execute(output, seed):
    root = Path(output)
    frozen = json.loads((root/'protocolo_congelado.json').read_text(encoding='utf-8'))
    expected = protocol() | {'implementation_sha256': implementation_hash()}
    if frozen != json.loads(json.dumps(expected)):
        raise ValueError('Protocolo distinto al congelado')
    folder = root/'final'
    folder.mkdir(exist_ok=True)
    dataset, result, status = (folder/f'dataset-{seed}.zip', folder/f'results-{seed}.zip', folder/f'completed-{seed}.json')
    if status.exists():
        saved = json.loads(status.read_text(encoding='utf-8'))
        assert hashlib.sha256(dataset.read_bytes()).hexdigest() == saved['dataset_sha256']
        assert hashlib.sha256(result.read_bytes()).hexdigest() == saved['results_sha256']
        return saved
    start = time.monotonic()
    print(f'INICIO final {seed}', flush=True)
    bundle = generate(GenerationConfig(seed=seed), study_tables())
    dataset.write_bytes(bundle_zip(bundle))
    pd.testing.assert_frame_equal(bundle['demand'], read_bundle(dataset.read_bytes())['demand'])
    results = run_experiment(bundle, ExperimentConfig(),
        progress=lambda message: print(f'final {seed}: {message}', flush=True))
    assert set(results['model_status'].model) == {'seasonal', 'random_forest', 'xgboost', 'lstm'}
    assert results['model_status'].status.eq('Ejecutado').all()
    totals = results['inventory_summary']
    np.testing.assert_allclose(totals.initial_stock+totals.received,
        totals.served+totals.expired+totals.final_stock, atol=1e-7)
    np.testing.assert_allclose(totals.demand, totals.served+totals.unmet, atol=1e-7)
    result.write_bytes(bundle_zip(results))
    saved = {'phase': 'final', 'seed': seed, 'seconds': time.monotonic()-start,
        'dish_rows': len(bundle['dish_demand']), 'demand_rows': len(bundle['demand']),
        'winner': results['experiment']['winner'],
        'dataset_sha256': hashlib.sha256(dataset.read_bytes()).hexdigest(),
        'results_sha256': hashlib.sha256(result.read_bytes()).hexdigest()}
    atomic_json(status, saved)
    print(f'TERMINADO final {seed}: {saved["seconds"]:.1f}s', flush=True)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='data/estudio-tesis-2026-11-26')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error('Entre 1 y 4 procesos según la memoria disponible')
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(execute, args.output, seed) for seed in protocol()['final_seeds']]
        for future in as_completed(pending):
            future.result()


if __name__ == '__main__':
    main()
