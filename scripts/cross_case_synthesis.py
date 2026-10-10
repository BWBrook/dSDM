"""Build manuscript tables from accepted aggregate evidence, without row data.

Run after the original Tasmania outer assessment has completed. This is a
reporting script: it neither fits models nor opens response payloads.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import fmean, median, quantiles

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/cross_case_synthesis/20261005/revision-01'
FT = 'multihead_full_finetune'
TO = 'target_only_random_init_resmlp'
BINDINGS = {
    'tasmania_inner': ('evidence/dsdm_inner_evaluation/goal036/stratum_metrics.csv', '2065ca48895af50036da90ad3e945096c6190594000527056309d78c5ee2bdc6'),
    'tasmania_selection': ('evidence/dsdm_inner_evaluation/goal036/conventional_selection.csv', '3e05784670f58e88144dcbda43819c3811e8303c59cd15c36f23fdf38736a561'),
    'mainland_transfer': ('evidence/tasmania_transfer/goal047/summary.json', '99fea9eb10fce97985ff3ebe8bf6f1679b707980b18124f04f24c3d9a1c041cc'),
    'mainland_inner': ('evidence/mainland_dsdm/goal046/summary.json', '868a2083036d7b5f14cde9137621977e06405033252551b80fd0d5107627c10b'),
    'bird_inner': ('evidence/seawfb_dsdm/goal052/summary.json', 'ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3'),
    'bird_conventional': ('evidence/seawfb_conventional/goal051/summary.json', '9c1bf1ff8884fae35fe7ebe6f8d19e2aae46ab7eedee252b398c0c74705dd2d8'),
    'bird_outer': ('data/processed/dsdm/goal052-seawfb-dsdm-experiment/outer-assessment-20261003-r2/scores.json', '3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41'),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def summarize(values: list[float | None]) -> dict:
    defined = [float(v) for v in values if v is not None]
    quartiles = quantiles(defined, n=4, method='inclusive') if len(defined) > 1 else [None] * 3
    deletion_means = [fmean(defined[:i] + defined[i + 1:]) for i in range(len(defined))] if len(defined) > 1 else []
    return {'n': len(defined), 'undefined': len(values) - len(defined),
            'mean': fmean(defined) if defined else None,
            'median': median(defined) if defined else None,
            'q25': quartiles[0], 'q75': quartiles[2],
            'leave_one_species_out_mean_min': min(deletion_means) if deletion_means else None,
            'leave_one_species_out_mean_max': max(deletion_means) if deletion_means else None,
            'positive': sum(v > 0 for v in defined),
            'negative': sum(v < 0 for v in defined), 'zero': sum(v == 0 for v in defined)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasmania-summary', type=Path, required=True)
    args = parser.parse_args()
    inputs = {}
    for name, (relative, expected) in BINDINGS.items():
        path = ROOT / relative
        require(sha(path) == expected, f'accepted input changed: {name}')
        inputs[name] = {'path': relative, 'sha256': expected}
    tas_path = args.tasmania_summary.resolve()
    require(tas_path.is_relative_to(ROOT / 'evidence'), 'Tasmania input must be aggregate evidence')
    tas = json.loads(tas_path.read_text())
    require(tas['success'] is True and tas['outer_opened'] == 1 and tas['schema_version'] == 'tasmania-outer-assessment-v1', 'Tasmania outer incomplete')
    inputs['tasmania_outer'] = {'path': str(tas_path.relative_to(ROOT)), 'sha256': sha(tas_path)}
    tas_digest_payload = {key: value for key, value in tas.items() if key != 'receipt_digest'}
    tas_digest = hashlib.sha256(json.dumps(tas_digest_payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    require(tas_digest == tas['receipt_digest'], 'Tasmania receipt digest mismatch')
    cases: dict[str, dict] = {}

    def add(case: str, label: str, unit: str, rows: list[dict], expected: int) -> None:
        require(len(rows) == expected and len({r['species'] for r in rows}) == expected, f'case inventory: {case}')
        require(all(set(r) == {'species', 'fine_tuned', 'target_only', 'conventional'} for r in rows), 'row schema drift')
        cases[case] = {'label': label, 'within_species_aggregation': unit, 'species': rows}

    inner_rows = read_csv(ROOT / BINDINGS['tasmania_inner'][0])
    selection = read_csv(ROOT / BINDINGS['tasmania_selection'][0])
    selected = {(r['species'], r['endpoint']): r['selected_family'] for r in selection}
    full = {(r['species'], r['method']): r for r in inner_rows if r['endpoint'] == 'fraction100/full'}
    species = sorted({key[0] for key in full})
    add('tasmania_inner', 'Tasmania inner', 'equal-fold mean ROC AUC', [
        {'species': sp, 'fine_tuned': float(full[(sp, FT)]['mean_fold_roc_auc']),
         'target_only': float(full[(sp, 'target_only_resmlp')]['mean_fold_roc_auc']),
         'conventional': float(full[(sp, 'conventional/' + selected[(sp, 'fraction100/full')])]['mean_fold_roc_auc'])} for sp in species], 8)
    outer = {(r['species'], r['model']): r for r in tas['metrics'] if r['endpoint'] == 'fraction100/full' and r['scope'] == 'pooled'}
    add('tasmania_outer', 'Tasmania held patches', 'pooled held-patch ROC AUC', [
        {'species': sp, 'fine_tuned': outer[(sp, FT)]['roc_auc'],
         'target_only': outer[(sp, 'target_only_resmlp')]['roc_auc'],
         'conventional': outer[(sp, 'conventional/' + selected[(sp, 'fraction100/full')])]['roc_auc']} for sp in species], 8)
    mainland_inner = json.loads((ROOT / BINDINGS['mainland_inner'][0]).read_text())
    require(mainland_inner['status'] == 'goal046_ready', 'mainland inner incomplete')
    add('mainland_inner', 'Mainland inner', 'equal-fold mean ROC AUC', [
        {'species': r['target'], 'fine_tuned': r['arms'][FT]['metrics']['mean_fold_roc_auc'],
         'target_only': r['arms'][TO]['metrics']['mean_fold_roc_auc'],
         'conventional': r['goal044_best_conventional']['metrics']['mean_fold_roc_auc']}
        for r in mainland_inner['results'] if r['endpoint'] == 'fraction100/full'], 5)
    mainland = json.loads((ROOT / BINDINGS['mainland_transfer'][0]).read_text())['surfaces']['primary']
    add('mainland_to_tasmania', 'Mainland to Tasmania', 'camera-supported primary ROC AUC', [
        {'species': r['target'], 'fine_tuned': r['methods'][FT]['metrics']['roc_auc'],
         'target_only': r['methods'][TO]['metrics']['roc_auc'],
         'conventional': r['methods']['selected_conventional']['metrics']['roc_auc']} for r in mainland['results']], 5)
    require({r['species'] for r in cases['mainland_inner']['species']} ==
            {r['species'] for r in cases['mainland_to_tasmania']['species']}, 'mainland panels differ')
    bird_inner = json.loads((ROOT / BINDINGS['bird_inner'][0]).read_text())
    bird_conventional = json.loads((ROOT / BINDINGS['bird_conventional'][0]).read_text())
    conventional_index = {r['target']: r for r in bird_conventional['endpoints'] if r['target_fraction'] == 100}
    baseline_rows = []
    for r in bird_inner['conditions']:
        if r['fraction'] != 100 or r['auxiliary'] != 'full':
            continue
        target_auc = r['arm_metrics'][TO]['mean_fold_roc_auc']
        ann_auc = conventional_index[r['target']]['families']['shallow_ann']['selected']['metrics']['mean_fold_roc_auc']
        baseline_rows.append({'species': r['target'], 'primary': r['selection_target'],
                              'target_only_minus_ann': target_auc - ann_auc,
                              'target_only_minus_conventional': target_auc - r['conventional_metrics']['mean_fold_roc_auc']})
    require(len(baseline_rows) == 157, 'bird baseline inventory')
    baseline = {'metric': 'equal_fold_mean_auc_then_equal_species_mean', 'species': baseline_rows, 'panels': {}}
    for name, rows, expected in [('all157', baseline_rows, 157),
                                 ('primary73', [r for r in baseline_rows if r['primary']], 73),
                                 ('other84', [r for r in baseline_rows if not r['primary']], 84)]:
        require(len(rows) == expected, 'bird baseline panel')
        baseline['panels'][name] = {'n': len(rows), **{key: fmean(r[key] for r in rows) for key in ('target_only_minus_ann', 'target_only_minus_conventional')}}
    bird_rows = [r for r in bird_inner['conditions'] if r['fraction'] == 100 and r['auxiliary'] == 'full' and r['selection_target']]
    add('birds_inner', 'Birds inner: common 73', 'equal-fold mean ROC AUC', [
        {'species': r['target'], 'fine_tuned': r['arm_metrics'][FT]['mean_fold_roc_auc'],
         'target_only': r['arm_metrics'][TO]['mean_fold_roc_auc'],
         'conventional': r['conventional_metrics']['mean_fold_roc_auc']} for r in bird_rows], 73)
    bird_outer = json.loads((ROOT / BINDINGS['bird_outer'][0]).read_text())
    primary = sorted(r['target'] for r in bird_rows)
    outer_index = {(r['target'], r['region']): r for r in bird_outer['targets']}
    for region in ('NCP', 'SEH', 'NNC'):
        add('birds_' + region, 'Birds outer: ' + region, 'regional X10 ROC AUC', [
            {'species': sp, 'fine_tuned': outer_index[(sp, region)]['x10']['metrics'][FT]['roc_auc'],
             'target_only': outer_index[(sp, region)]['x10']['metrics'][TO]['roc_auc'],
             'conventional': outer_index[(sp, region)]['x10']['metrics']['selected_conventional']['roc_auc']} for sp in primary], 73)
    add('birds_outer', 'Birds outer: equal regions', 'equal-region mean ROC AUC over NCP, SEH, NNC', [
        {'species': sp, **{method: fmean(next(r[method] for r in cases['birds_' + region]['species'] if r['species'] == sp) for region in ('NCP', 'SEH', 'NNC')) for method in ('fine_tuned', 'target_only', 'conventional')}} for sp in primary], 73)

    metric_rows = []
    contrast_rows = []
    for case, value in cases.items():
        value['metrics'] = {method: summarize([r[method] for r in value['species']]) for method in ('fine_tuned', 'target_only', 'conventional')}
        value['contrasts'] = {}
        for comparator in ('target_only', 'conventional'):
            differences = [None if r['fine_tuned'] is None or r[comparator] is None else r['fine_tuned'] - r[comparator] for r in value['species']]
            value['contrasts'][comparator] = summarize(differences)
            for r, difference in zip(value['species'], differences, strict=True):
                contrast_rows.append({'case': case, 'species': r['species'], 'comparator': comparator, 'difference': difference})
        for r in value['species']:
            metric_rows.append({'case': case, **r})
    native_macro = bird_outer['aggregate']['common73']['contrasts'][FT + '_minus_' + TO]['mean']
    require(abs(cases['birds_outer']['contrasts']['target_only']['mean'] - native_macro) < 2e-15, 'accepted outer macro mismatch')
    extent_path = ROOT / 'evidence/seawfb_dsdm/goal052/extent-review-20261005.json'
    extent = json.loads(extent_path.read_text())
    require(extent['checks']['published_mean_fold_matches'] is True, 'bird inner replay incomplete')
    replay = extent['checks']['accepted_arm_replay']
    require(replay['status'] == 'pass' and replay['targets'] == 157
            and sum(replay['numeric_comparisons'].values()) == 2870
            and max(replay['maximum_absolute_error'].values()) <= 1e-12,
            'bird outer saved-arm replay incomplete')
    require(all(summary['contrasts']['ft_minus_to']['n'] == 73
                for summary in extent['outer']['primary73']['region_pooled_x10_by_region'].values()),
            'bird primary regional panel incomplete')
    inputs['bird_extent_posthoc'] = {'path': str(extent_path.relative_to(ROOT)), 'sha256': sha(extent_path)}
    inner_extent = extent['inner']['primary73']
    scopes = {
        'published_mean_fold': inner_extent['published_mean_fold'],
        'pooled_whole_domain': inner_extent['pooled_whole_domain'],
        'region_pooled': inner_extent['region_pooled_equal_eligible_strata_per_target'],
        'region_fold': inner_extent['region_fold_equal_eligible_strata_per_target'],
        'outer_equal_regions': extent['outer']['primary73']['equal_region_then_species'],
    }
    def mean_value(value):
        return value['mean'] if isinstance(value, dict) else value
    plot_rows = []
    for scope, summary in scopes.items():
        for series, arm in [('fine_tuned', FT), ('target_only', TO), ('conventional', 'conventional')]:
            plot_rows.append({'scope': scope, 'measure': 'auc', 'series': series, 'value': mean_value(summary['metrics'][arm])})
        for series, contrast in [('fine_tuned_minus_target_only', 'ft_minus_to'), ('ft_ensemble_minus_conventional', 'ft_conv_ensemble_minus_conv'), ('to_ensemble_minus_conventional', 'to_conv_ensemble_minus_conv')]:
            plot_rows.append({'scope': scope, 'measure': 'contrast', 'series': series, 'value': mean_value(summary['contrasts'][contrast])})
    require(abs(mean_value(scopes['outer_equal_regions']['contrasts']['ft_minus_to']) - native_macro) < 2e-12, 'post hoc outer background/aggregation mismatch')
    output = {'schema_version': 'dsdm-cross-case-synthesis-v2', 'analysis': 'descriptive_reporting_of_accepted_aggregates',
              'inputs': inputs, 'source_sha256': sha(Path(__file__)), 'cases': cases,
              'bird_target_only_baseline': baseline,
              'bird_extent_plot': plot_rows,
              'dispersion': {'quartiles': 'linear interpolation, inclusive endpoints (R type 7)',
                             'composition_sensitivity': 'range of means after deleting each species once; not a confidence interval'},
              'limits': ['Case means do not imply independent species or equal sampling domains.', 'No cross-case grand mean or inferential test is calculated.', 'Tasmania outer pooled patches differ from bird equal-region aggregation.', 'IQR describes observed species dispersion; single-species deletion does not represent joint species dependence or population uncertainty.']}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'summary.json').write_text(json.dumps(output, sort_keys=True, indent=2) + '\n')
    for filename, rows in [('case_metrics.csv', metric_rows), ('case_contrasts.csv', contrast_rows), ('bird_extent_plot.csv', plot_rows)]:
        with (OUTPUT / filename).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    lines = ['| Assessment | Comparator | Mean | Median [Q1, Q3] | Positive | Mean after single-species deletion |',
             '|---|---|---:|---:|---:|---:|']
    for case in ('tasmania_inner', 'tasmania_outer', 'mainland_inner', 'mainland_to_tasmania', 'birds_inner', 'birds_outer'):
        value = cases[case]; a = value['contrasts']['target_only']; b = value['contrasts']['conventional']
        fmt = lambda v: 'NA' if v is None else f'{v:+.4f}'
        for name, stats in [('Target-only', a), ('Conventional', b)]:
            lines.append(f"| {value['label']} | {name} | {fmt(stats['mean'])} | {fmt(stats['median'])} [{fmt(stats['q25'])}, {fmt(stats['q75'])}] | {stats['positive']}/{stats['n']} | [{fmt(stats['leave_one_species_out_mean_min'])}, {fmt(stats['leave_one_species_out_mean_max'])}] |")
    (OUTPUT / 'comparison-table.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
