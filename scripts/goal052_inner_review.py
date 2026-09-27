"""Reproduce descriptive review checks from the accepted tracked inner summary.

This reads no private or outer observations and changes no fitting protocol.
Cross-endpoint, composition, presence-tertile and block summaries are post hoc.
"""
from pathlib import Path
import hashlib
import json
import statistics as stats

from dsdm_phase1.goal050_seawfb_foundation import species_blocks

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'evidence/seawfb_dsdm/goal052/summary.json'
OUTPUT = ROOT / 'evidence/seawfb_dsdm/goal052/fable-review-20260927.json'
EXPECTED = 'ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3'
FT = 'multihead_full_finetune'
FZ = 'multihead_frozen_trunk'
TO = 'target_only_random_init_resmlp'
Q = 'target_plus_q_linear_resmlp'


def describe(values):
    return {'n': len(values), 'mean': stats.mean(values),
            'median': stats.median(values), 'positive': sum(v > 0 for v in values),
            'min': min(values), 'max': max(values)}


def metric(condition, arm):
    if arm == 'conventional':
        return condition['conventional_metrics']
    if arm == 'q_conventional':
        return condition['q_metrics']
    return condition['arm_metrics'][arm]


def contrast(rows, left, right):
    return {key: describe([metric(c, left)[key] - metric(c, right)[key] for c in rows])
            for key in ('mean_fold_roc_auc', 'mean_fold_tss')}


def panel(rows):
    return {'targets': len(rows), 'ft_minus_conventional': contrast(rows, FT, 'conventional'),
            'ft_minus_target_only': contrast(rows, FT, TO),
            'frozen_minus_target_only': contrast(rows, FZ, TO),
            'ft_minus_frozen': contrast(rows, FT, FZ),
            'q_minus_target_only': contrast(rows, Q, TO),
            'q_conventional_minus_conventional': contrast(rows, 'q_conventional', 'conventional'),
            'conventional_auc': describe([metric(c, 'conventional')['mean_fold_roc_auc'] for c in rows]),
            'pooled_presence_cells': describe([metric(c, TO)['pooled']['presence_n'] for c in rows]),
            'pooled_prevalence': describe([metric(c, TO)['pooled']['prevalence'] for c in rows])}


def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
    summary = json.loads(SOURCE.read_text())
    rows = summary['conditions']
    by_key = {(c['target'], c['fraction'], c['auxiliary']): c for c in rows}
    assert len(rows) == len(by_key) == 449
    primary = sorted({c['target'] for c in rows if c['selection_target']})
    full = [c for c in rows if c['fraction'] == 100 and c['auxiliary'] == 'full']
    assert len(primary) == 73 and len(full) == 157
    panels = {}
    for fraction in (25, 50, 100):
        panels[f'primary73_{fraction}_full'] = panel([by_key[t, fraction, 'full'] for t in primary])
    for auxiliary in ('20', '80'):
        panels[f'primary73_100_{auxiliary}'] = panel([by_key[t, 100, auxiliary] for t in primary])
    panels['other84_100_full'] = panel([c for c in full if not c['selection_target']])
    cross = {
        'ft50_minus_conventional100': describe([
            metric(by_key[t, 50, 'full'], FT)['mean_fold_roc_auc'] -
            metric(by_key[t, 100, 'full'], 'conventional')['mean_fold_roc_auc'] for t in primary]),
        'ft25_minus_target_only100': describe([
            metric(by_key[t, 25, 'full'], FT)['mean_fold_roc_auc'] -
            metric(by_key[t, 100, 'full'], TO)['mean_fold_roc_auc'] for t in primary]),
        'frozen_full_minus_frozen20': describe([
            metric(by_key[t, 100, 'full'], FZ)['mean_fold_roc_auc'] -
            metric(by_key[t, 100, '20'], FZ)['mean_fold_roc_auc'] for t in primary]),
    }
    cross['ft20_fraction_of_full_mean_gain'] = (
        panels['primary73_100_20']['ft_minus_target_only']['mean_fold_roc_auc']['mean'] /
        panels['primary73_100_full']['ft_minus_target_only']['mean_fold_roc_auc']['mean'])
    assert cross['ft50_minus_conventional100']['positive'] == 56
    assert cross['frozen_full_minus_frozen20']['positive'] == 73
    assert panels['primary73_100_full']['frozen_minus_target_only']['mean_fold_roc_auc']['positive'] == 57
    ordered = sorted(full, key=lambda c: (metric(c, TO)['pooled']['presence_n'], c['target']))
    tertiles = {name: panel(group) for name, group in zip(
        ('low', 'middle', 'high'), (ordered[:53], ordered[53:105], ordered[105:]))}
    blocks = species_blocks([c['target'] for c in full])
    for block, stability in summary['selection']['stability']['leave_one_focal_block_out'].items():
        assert set(stability['omitted_targets']) == {t for t in primary if blocks[t] == int(block)}
    block_means = {str(block): panel([c for c in full if blocks[c['target']] == block])
                   for block in range(10)}
    selected = summary['selection']['selected_architecture']
    auc = summary['selection']['mean_target_roc_auc']
    selection = {'winner': selected, 'mean_auc': auc,
                 'winner_minus_candidate_mean': auc[selected] - stats.mean(auc.values()),
                 'winner_minus_best_alternative': auc[selected] - max(v for k, v in auc.items() if k != selected),
                 'block_deletion_winner_agreement': summary['selection']['stability']['diagnostic_winner_agreement_count'],
                 'selection_optimism_bound': None,
                 'note': 'Observed candidate score gaps do not bound out-of-sample selection bias.'}
    c = by_key['Climacteris erythrops', 100, 'full']
    species = {'pooled_presence_cells': metric(c, TO)['pooled']['presence_n'],
               'pooled_prevalence': metric(c, TO)['pooled']['prevalence'],
               'fold_presence_cells': [f['presence_n'] for f in metric(c, TO)['folds']],
               'ft_minus_frozen': contrast([c], FT, FZ),
               'fold3': {arm: metric(c, arm)['folds'][3] for arm in (TO, FT, FZ, 'conventional')},
               'thresholds': {arm: metric(c, arm)['threshold'] for arm in (TO, FT, FZ, 'conventional')}}
    result = {'status': 'tracked_inner_descriptive_review', 'board_message': 566,
              'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': EXPECTED,
              'analysis_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Descriptive review after inner results; not new prespecified inference or outer evidence.',
              'outer_rows_read': 0, 'panels': panels, 'cross_endpoint': cross,
              'presence_tertiles': tertiles, 'block_means': block_means,
              'selection': selection, 'climacteris_erythrops': species}
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'cross_endpoint': cross, 'selection': selection,
                      'full_frozen_vs_target_only_positive': 57,
                      'low_tertile_ft_minus_conventional_auc': tertiles['low']['ft_minus_conventional']['mean_fold_roc_auc'],
                      'output': str(OUTPUT.relative_to(ROOT))}, indent=2))


if __name__ == '__main__':
    main()
