from __future__ import annotations

import json
from pathlib import Path

import pytest

from dsdm_phase1 import goal051_nectar_execution as nectar
from dsdm_phase1 import goal051_seawfb_conventional as science
from dsdm_phase1.seawfb_modeling import SeawfbModelingError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    plan = json.loads((ROOT / nectar.CONFIG_PATH).read_text())
    for path in (nectar.CONFIG_PATH, nectar.SOURCE_PATH, Path(plan['previous_route']['path'])):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes((ROOT / path).read_bytes())
    config = science._config(ROOT)
    monkeypatch.setattr(science, '_identity', lambda root: plan['scientific_identity'])
    monkeypatch.setattr(science, '_config', lambda root: config)
    _, execution = nectar.execution_context(tmp_path)
    host = {'hostname': 'deep-vm', 'system': 'Linux', 'instance_id': plan['host']['instance_id'],
            'platform': 'Linux-test-platform', 'cpus': 64, 'memory_bytes': 125 * 1024**3}
    monkeypatch.setattr(nectar, 'actual_host', lambda: host.copy())
    spec = config['execution']['canary']
    prediction = {'finite': True, 'converged': True, 'prediction_count': 4,
                  'prediction_range': [0.1, 0.9], 'prediction_digest': 'a' * 64}
    for tag in nectar.expected_tags(plan):
        mode, index = tag.split('-')[1:]
        index = int(index)
        start = index * 1_000_000_000 if mode == 'serial' else 10_000_000_000 + index
        end = start + 500_000_000 if mode == 'serial' else 20_000_000_000
        path = nectar.receipt_path(tmp_path, plan, tag)
        receipt = {
            'schema_version': 'goal051-nectar-canary-v1', 'status': 'metric_free_complete',
            'identity': plan['scientific_identity'], 'execution_identity': execution, 'host_attestation': host,
            'host': host['hostname'], 'system': host['system'], 'platform': host['platform'],
            'receipt_tag': tag, 'receipt_path': str(path.relative_to(tmp_path)),
            'host_key': 'nectar', 'run_mode': mode, 'run_index': index,
            'target': spec['target'], 'held_fold': 0, 'focal_block': 6,
            'metrics_computed': False, 'outer_response_rows_read': 0, 'outer_predictor_rows_used': 0,
            'start_epoch_ns': start, 'end_epoch_ns': end, 'total_wall_seconds': (end-start)/1e9,
            'process_peak_rss_bytes': 2048,
            'entries': [{**prediction, 'candidate_id': candidate,
                         'family': science.CANONICAL_CANDIDATES[candidate]['family']} for candidate in spec['candidate_ids']],
            'q_linear': [{**prediction, 'auxiliary_size': str(auxiliary),
                          'expanded_rows': 20, 'collapsed_rows': 10, 'head_count': 2,
                          'parameter_digest': 'b'*64,
                          'attempts': [{'attempt': 'primary', 'max_iter': 5000, 'tol': 1e-5,
                                        'n_iter': 25, 'warning': False, 'warning_types': [],
                                        'numerical_warning': False, 'converged': True}],
                          'accepted_attempt': 'primary', 'k': 2.0, 'canonical_C': 0.1, 'solver_C': 0.2,
                          'representation': 'collapsed_weight_divided_by_k_solver_C_multiplied_by_k',
                          'downstream_family': 'hist_gradient_boosting', 'downstream_candidate_id': 'hgb04',
                          'downstream_fit': {'converged': True}} for auxiliary in (20, 'full')],
        }
        science._atomic_json(path, receipt)
    return tmp_path, plan, host


def change_receipt(evidence, mutate, tag='nectar-mixed-16'):
    root, plan, _ = evidence
    path = nectar.receipt_path(root, plan, tag)
    value = json.loads(path.read_text())
    mutate(value)
    science._atomic_json(path, value)


def test_gate_replays_all_evidence_and_preserves_old_route(evidence):
    root, plan, _ = evidence
    previous = (root / plan['previous_route']['path']).read_bytes()
    result = nectar.canary_summary(root)
    assert result['receipt_count'] == 18
    assert result['mixed_batch']['interval_peak_concurrency'] == 16
    nectar.select_route(root, 16)
    assert nectar.gate(root, 16)['status'] == 'nectar_production_gate_passed'
    assert (root / plan['previous_route']['path']).read_bytes() == previous
    with pytest.raises(SeawfbModelingError, match='workers_invalid'):
        nectar.select_route(root, 17)
    change_receipt(evidence, lambda v: v['entries'][0].update(converged=False))
    with pytest.raises(SeawfbModelingError, match='fit_invalid'):
        nectar.gate(root, 16)


@pytest.mark.parametrize('mutation,error', [
    (lambda v: v['host_attestation'].update(hostname='wrong'), 'actual_host_mismatch'),
    (lambda v: v['host_attestation'].update(instance_id='wrong'), 'actual_host_mismatch'),
    (lambda v: v['host_attestation'].update(cpus=2), 'cpu_capacity_insufficient'),
    (lambda v: v['execution_identity'].update(source_sha256='wrong'), 'provenance_drift'),
    (lambda v: v['entries'][0].update(converged=False), 'fit_invalid'),
    (lambda v: v['q_linear'][0]['attempts'][0].update(numerical_warning=True), 'q_attempt_record_drift'),
    (lambda v: v['q_linear'][0].update(parameter_digest='c'*64), 'q_parameter_digest_instability'),
    (lambda v: v['entries'][0].update(prediction_digest='c'*64), 'prediction_digest_instability'),
    (lambda v: v.update(total_wall_seconds=100), 'wall_interval_mismatch'),
    (lambda v: v.update(start_epoch_ns=21_000_000_000, end_epoch_ns=22_000_000_000, total_wall_seconds=1), 'concurrency_not_proven'),
    (lambda v: v.update(outer_response_rows_read=1), 'firewall_drift'),
    (lambda v: v['entries'][0].update(metrics={'auc': 0.8}), 'metric_payload_forbidden'),
])
def test_summary_rejects_invalid_or_unproven_runs(evidence, mutation, error):
    change_receipt(evidence, mutation)
    with pytest.raises(SeawfbModelingError, match=error):
        nectar.summarize(evidence[0])


def test_summary_rejects_missing_receipt(evidence):
    root, plan, _ = evidence
    nectar.receipt_path(root, plan, 'nectar-mixed-16').unlink()
    with pytest.raises(SeawfbModelingError, match='receipt_missing'):
        nectar.summarize(root)


def test_execution_source_mutation_cannot_reuse_receipts(evidence):
    root, _, _ = evidence
    with (root / nectar.SOURCE_PATH).open('a') as handle:
        handle.write('\n# changed execution adapter\n')
    with pytest.raises(SeawfbModelingError, match='provenance_drift'):
        nectar.summarize(root)


def test_scientific_identity_drift_is_not_rebound(evidence, monkeypatch):
    root, plan, _ = evidence
    changed = {**plan['scientific_identity'], 'source_sha256': 'f'*64}
    monkeypatch.setattr(science, '_identity', lambda root: changed)
    with pytest.raises(SeawfbModelingError, match='scientific_identity_drift'):
        nectar.execution_context(root)


def test_new_adapter_preserves_frozen_scientific_identity():
    plan = json.loads((ROOT / nectar.CONFIG_PATH).read_text())
    assert science._identity(ROOT) == plan['scientific_identity']
    assert nectar.SOURCE_PATH not in science.SOURCE_PATHS
    assert nectar.CONFIG_PATH not in (science.CONFIG_PATH, science.GOAL052_CONFIG_PATH)


def test_batch_uses_two_serial_then_sixteen_spawned_workers(evidence, monkeypatch):
    root, _, _ = evidence
    events = []
    monkeypatch.setattr(science, 'validate_inputs', lambda root: None)
    monkeypatch.setattr(nectar, 'probe', lambda root, tag: events.append(tag))
    monkeypatch.setattr(nectar, 'canary_summary', lambda root: {'complete': True})
    class Pool:
        def __init__(self, max_workers, mp_context):
            assert max_workers == 16
            assert mp_context.get_start_method() == 'spawn'
        def __enter__(self):
            assert events == ['nectar-serial-1', 'nectar-serial-2']
            return self
        def __exit__(self, *args):
            pass
        def map(self, function, roots, tags):
            assert len(roots) == len(tags) == 16
            return tags
    monkeypatch.setattr(nectar, 'ProcessPoolExecutor', Pool)
    assert nectar.canary_batch(root) == {'complete': True}


def test_probe_writes_original_scientific_identity_and_execution_provenance(evidence, monkeypatch):
    import numpy as np
    root, plan, host = evidence
    template = json.loads(nectar.receipt_path(root, plan, 'nectar-serial-1').read_text())
    calls = []
    class Store:
        def __init__(self, root):
            self.crossfit = {'focal_blocks': {template['target']: 6}}
        def target_rows(self, target, fold, fraction, side):
            calls.append(side)
            return object()
        def batch(self, *args):
            return object()
    monkeypatch.setattr(nectar, 'SeawfbStore', Store)
    monkeypatch.setattr(science, 'validate_inputs', lambda root: None)
    monkeypatch.setattr(nectar.platform, 'node', lambda: host['hostname'])
    monkeypatch.setattr(nectar.platform, 'system', lambda: host['system'])
    monkeypatch.setattr(nectar.platform, 'platform', lambda: host['platform'])
    monkeypatch.setattr(nectar, '_fit_predict', lambda *args: (np.array([0.2, 0.8]),
                        {'physical_fits': 1, 'converged': True, 'best_epoch': None}))
    q_fit = {**template['q_linear'][0], 'iterations': 25}
    monkeypatch.setattr(nectar, 'fit_q_linear', lambda *args, **kwargs: (object(), q_fit))
    monkeypatch.setattr(nectar, 'standardized_q', lambda *args: (object(), object(), {}))
    result = nectar.probe(root, 'nectar-serial-1')
    assert result['identity'] == plan['scientific_identity']
    assert result['execution_identity'] == nectar.execution_context(root)[1]
    assert len(result['entries']) == 5 and len(result['q_linear']) == 2
    assert calls == ['train', 'validation']
    assert json.loads(nectar.receipt_path(root, plan, 'nectar-serial-1').read_text()) == result
