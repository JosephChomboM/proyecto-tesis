"""Recalculate final study summaries only from completed, hash-verified archives."""

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from restaurante.research.simulation import paired_replica_summary


def read_archive(path):
    result = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            key, suffix = name.rsplit('.', 1)
            payload = archive.read(name)
            result[key] = pd.read_csv(io.BytesIO(payload)) if suffix == 'csv' else json.loads(payload)
    return result


def holm(values):
    values = np.asarray(values, float)
    order = np.argsort(values)
    adjusted = np.maximum.accumulate((len(values)-np.arange(len(values)))*values[order])
    result = np.empty(len(values))
    result[order] = np.minimum(1., adjusted)
    return result


def paired_effect(difference):
    difference = np.asarray(difference, float)
    rng = np.random.default_rng(42)
    boot = rng.choice(difference, size=(3000, len(difference)), replace=True).mean(axis=1)
    return {'n': len(difference), 'mean_reduction': float(difference.mean()),
        'ci95_low': float(np.quantile(boot, .025)), 'ci95_high': float(np.quantile(boot, .975)),
        'p_value': 1. if np.allclose(difference, 0) else float(stats.wilcoxon(difference).pvalue)}


def summarize(root):
    root = Path(root)
    plan = json.loads((root/'protocolo_congelado.json').read_text(encoding='utf-8'))
    metrics, inventory, statuses, quality, winning, block_metrics, portions = [], [], [], [], [], [], []
    for phase, seeds in [('pilot', plan['pilot_seeds']), ('final', plan['final_seeds'])]:
        for seed in seeds:
            folder = root/phase
            checkpoint = json.loads((folder/f'completed-{seed}.json').read_text(encoding='utf-8'))
            for prefix in ['dataset', 'results']:
                assert hashlib.sha256((folder/f'{prefix}-{seed}.zip').read_bytes()).hexdigest() == checkpoint[prefix+'_sha256']
            dataset, results = read_archive(folder/f'dataset-{seed}.zip'), read_archive(folder/f'results-{seed}.zip')
            assert dataset['metadata']['generation']['seed'] == seed
            assert results['metadata']['generation']['seed'] == seed
            assert results['experiment']['config'] == plan['experiment']
            demand, dishes = dataset['demand'], dataset['dish_demand']
            assert len(demand) == 17544 and len(dishes) == 6579
            assert not demand.duplicated(['date', 'profile', 'ingredient']).any()
            assert not dishes.duplicated(['date', 'profile', 'dish']).any()
            assert demand.demand.ge(0).all() and np.isfinite(demand.demand).all()
            assert demand.loc[~demand.is_open, 'demand'].eq(0).all()
            assert demand.date.nunique() == 731
            assert results['model_status'].status.eq('Ejecutado').all()
            ledger = results['inventory_summary']
            np.testing.assert_allclose(ledger.initial_stock+ledger.received,
                ledger.served+ledger.expired+ledger.final_stock, atol=1e-7)
            np.testing.assert_allclose(ledger.demand, ledger.served+ledger.unmet, atol=1e-7)
            quality.append({'phase': phase, 'seed': seed, 'dish_rows': len(dishes), 'demand_rows': len(demand),
                'days': demand.date.nunique(), 'series': len(demand[['profile','ingredient']].drop_duplicates()),
                'closed_rows': int((~demand.is_open).sum()), 'holiday_days': int(dataset['context'].holiday.sum()),
                'missing_cells': int(demand.isna().sum().sum()),
                'mass_balance_max_error': float(abs(ledger.initial_stock+ledger.received-ledger.served-ledger.expired-ledger.final_stock).max()),
                'seconds': checkpoint['seconds']})
            if phase == 'pilot':
                continue
            daily_portions = dishes.groupby(['date','profile'], as_index=False).agg(
                demand_portions=('demand_portions','sum'), is_open=('is_open','max'))
            portions.append(daily_portions.assign(seed=seed))
            for container, key in [(metrics,'metrics'), (inventory,'inventory_summary'),
                    (statuses,'model_status'), (block_metrics,'forecast_blocks')]:
                container.append(results[key].assign(seed=seed))
            winner = checkpoint['winner']
            selected = results['metrics'][(results['metrics'].model == winner['model']) &
                (results['metrics'].external == winner['external'])]
            winning.append(selected.assign(seed=seed))
    out = root/'resumen'
    out.mkdir(exist_ok=True)
    frames = {'calidad_datasets': pd.DataFrame(quality), 'metricas_por_serie': pd.concat(metrics, ignore_index=True),
        'inventario_por_serie': pd.concat(inventory, ignore_index=True), 'seleccion_validacion': pd.concat(statuses, ignore_index=True),
        'metricas_modelo_seleccionado': pd.concat(winning, ignore_index=True), 'metricas_por_bloque': pd.concat(block_metrics, ignore_index=True)}
    daily = pd.concat(portions, ignore_index=True)
    frames['solicitudes_diarias_por_perfil'] = daily
    descriptive = []
    for profile, group in daily.groupby('profile'):
        opened = group.loc[group.is_open, 'demand_portions']
        descriptive.append({'profile': profile, 'replications': group.seed.nunique(),
            'days_per_replication': group.date.nunique(), 'closed_days_total': int((~group.is_open).sum()),
            'mean_all_days': float(group.demand_portions.mean()), 'mean_open_days': float(opened.mean()),
            'std_open_days': float(opened.std()), 'median_open_days': float(opened.median()),
            'p95_open_days': float(opened.quantile(.95)), 'min_open_days': int(opened.min()),
            'max_open_days': int(opened.max())})
    frames['descriptivos_solicitudes'] = pd.DataFrame(descriptive)
    m = frames['metricas_por_serie']
    indicators = ['mae','rmse','mape_percent','wape_percent','r2']
    # Average the 24 series within each seed first; sampling unit remains the seed.
    per_seed = m.groupby(['seed','model','external'])[indicators].mean().reset_index()
    frames['metricas_promedio_por_replica'] = per_seed
    frames['metricas_por_modelo'] = per_seed.groupby(['model','external'])[indicators].agg(['mean','std']).reset_index()
    frames['metricas_por_modelo'].columns = ['_'.join(c).strip('_') if isinstance(c, tuple) else c for c in frames['metricas_por_modelo'].columns]
    frames['metricas_por_perfil'] = m.groupby(['model','external','profile'])[indicators].mean().reset_index()
    frames['mape_umbral_por_serie'] = m.groupby(['model','external','profile','ingredient']).mape_percent.agg(['mean','min','max']).reset_index()
    inv = frames['inventario_por_serie']
    sums = ['demand','served','unmet','stockout','received','expired','waste_cost','purchase_cost','initial_stock','final_stock']
    totals = inv.groupby(['seed','policy'])[sums].sum().reset_index()
    totals['service_percent'] = totals.served/totals.demand*100
    frames['inventario_total_por_replica'] = totals
    frames['comparacion_politicas_total'] = paired_replica_summary(totals, ('expired','waste_cost','stockout','unmet','purchase_cost'))
    paired_series = []
    for (profile, ingredient, unit), group in inv.groupby(['profile','ingredient','unit']):
        paired_series.append(paired_replica_summary(group, ('expired','waste_cost','stockout','unmet')).assign(
            profile=profile, ingredient=ingredient, unit=unit))
    paired = pd.concat(paired_series, ignore_index=True)
    # Holm within each endpoint across 24 profile-ingredient comparisons.
    paired['p_holm_24_series'] = paired.groupby('indicator').p_value.transform(holm)
    frames['comparacion_politicas_por_insumo'] = paired
    frames['inventario_por_perfil'] = inv.groupby(['seed','policy','profile'])[sums].sum().groupby(['policy','profile']).mean().reset_index()
    comparisons = []
    base = per_seed[per_seed.model == 'seasonal'].set_index('seed')
    for (model, external), group in per_seed[per_seed.model != 'seasonal'].groupby(['model','external']):
        joined = group.set_index('seed').join(base[indicators].add_suffix('_base'), validate='1:1')
        comparisons.append({'model': model, 'external': bool(external), 'indicator': 'wape_percent',
            **paired_effect(joined.wape_percent_base-joined.wape_percent)})
    compare = pd.DataFrame(comparisons)
    compare['p_holm_6_variants'] = holm(compare.p_value)
    frames['comparacion_pronosticos'] = compare
    ablations = []
    for model, group in per_seed[per_seed.model != 'seasonal'].groupby('model'):
        wide = group.pivot(index='seed', columns='external', values='wape_percent')
        ablations.append({'model': model, 'indicator': 'wape_percent', **paired_effect(wide[False]-wide[True])})
    ablations = pd.DataFrame(ablations)
    ablations['p_holm_3_models'] = holm(ablations.p_value)
    frames['aporte_contexto'] = ablations
    selected = frames['metricas_modelo_seleccionado']
    selected_seeds = selected.groupby('seed')[indicators].mean()
    frames['comparacion_modelo_seleccionado'] = pd.DataFrame([paired_effect(base.wape_percent-selected_seeds.wape_percent)])
    for name, frame in frames.items():
        frame.to_csv(out/f'{name}.csv', index=False, encoding='utf-8-sig')
    info = {'final_replications': len(plan['final_seeds']), 'pilot_replications': len(plan['pilot_seeds']),
        'selected_mape_mean': float(selected_seeds.mape_percent.mean()),
        'selected_wape_mean': float(selected_seeds.wape_percent.mean()),
        'selected_series_mape_under20': int((selected.mape_percent < 20).sum()),
        'selected_series_total': len(selected),
        'seeds_macro_mape_under20': int((selected_seeds.mape_percent < 20).sum()),
        'winners': selected[['seed','model','external']].drop_duplicates().groupby(['model','external']).size().reset_index(name='count').to_dict('records'),
        'scope': 'Resultados computacionales condicionados al generador no calibrado; Aiken y SUS pendientes'}
    (out/'conclusiones_calculadas.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return frames, info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='data/estudio-tesis-2026-11-26')
    summarize(parser.parse_args().output)
