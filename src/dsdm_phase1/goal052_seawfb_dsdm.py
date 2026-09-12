"""Frozen, retained-only SEAWFB neural experiment with atomic resumable leaves."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import platform
import time
from typing import Any, Mapping, Sequence

# Required for deterministic CUDA linear algebra; applies before CUDA initialization.
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')

import numpy as np
import torch

from . import goal051_seawfb_conventional as baseline
from .goal052_checkpoints import load_leaf, load_pretraining, save_leaf, save_pretraining
from .goal052_design import ARCHITECTURE_IDS, base_endpoints, endpoint_grid, select_architecture
from .goal052_results import seed_average_folds, summarize_condition, summarize_panels
from .mainland_dsdm import architecture_spec, state_digest
from .mainland_modeling import summarize_oof
from .seawfb_dsdm_data import IndexedRows, _roles, auxiliary_data, target_data
from .seawfb_dsdm_training import fit_pretraining_lifecycle, fit_target_lifecycle
from .seawfb_modeling import CROSSFIT_PATH, CURVES_PATH, SeawfbStore, digest, require, sha256_file, stable_seed

CONFIG = Path('config/goal052_seawfb_dsdm.json')
ACCEPTANCE = Path('evidence/seawfb_conventional/goal051/completion_review.json')
BASE_SUMMARY = Path('evidence/seawfb_conventional/goal051/summary.json')
SOURCE_PATHS = tuple(Path(p) for p in (
    'src/dsdm_phase1/goal052_seawfb_dsdm.py', 'src/dsdm_phase1/goal052_checkpoints.py',
    'src/dsdm_phase1/goal052_design.py', 'src/dsdm_phase1/goal052_results.py',
    'src/dsdm_phase1/goal052_profile.py',
    'src/dsdm_phase1/seawfb_dsdm_data.py', 'src/dsdm_phase1/seawfb_dsdm_training.py',
    'src/dsdm_phase1/mainland_dsdm.py', 'src/dsdm_phase1/mainland_modeling.py',
    'src/dsdm/models.py', 'src/dsdm/contracts.py',
))
ARMS = ('target_only_random_init_resmlp', 'target_plus_q_linear_resmlp',
        'multihead_frozen_trunk', 'multihead_full_finetune')
SEEDS = tuple(f'seed{i:02d}' for i in range(5))
read_json = baseline._read_json
atomic_json = baseline._atomic_json


def config_at(root: Path) -> dict[str, Any]:
    config = read_json(root / CONFIG)
    baseline._validate_goal052(config)
    return config


def private_root(root: Path, config: Mapping[str, Any]) -> Path:
    return root / config['execution']['private_root']


def identity_at(root: Path) -> dict[str, Any]:
    return {'goal051_identity': baseline._identity(root),
            'acceptance_sha256': sha256_file(root / ACCEPTANCE),
            'baseline_summary_sha256': sha256_file(root / BASE_SUMMARY),
            'source_sha256': digest({str(p): sha256_file(root / p) for p in SOURCE_PATHS})}


def validate_inputs(root: Path) -> dict[str, Any]:
    inputs = baseline.validate_inputs(root)
    config_at(root)
    accepted, summary = read_json(root / ACCEPTANCE), read_json(root / BASE_SUMMARY)
    require(accepted['status'] == 'goal051_accepted_with_documented_candidate_failure_limitation', 'goal051_acceptance_required')
    require(accepted['identity'] == summary['identity'] == baseline._identity(root), 'goal051_acceptance_identity_drift')
    require(accepted['summary_sha256'] == sha256_file(root / BASE_SUMMARY), 'accepted_summary_hash_drift')
    require(summary['status'] == 'complete' and summary['target_endpoints'] == 303 and summary['q_conditions'] == 449, 'baseline_incomplete')
    provenance = baseline.q_provenance(root, baseline._config(root), require_complete=True)
    require(provenance == summary['q_surface_provenance'], 'accepted_q_provenance_drift')
    return {'status': 'goal052_inputs_valid', 'identity': identity_at(root),
            'goal050_inputs': inputs, 'q_surfaces': provenance['ready'], 'outer_response_rows_read': 0}


def target_seed(target: str, fraction: int, fold: int, architecture: str, seed: str) -> int:
    return stable_seed('goal052-target-v1', target, fraction, fold, architecture, seed)


def pretraining_key(identity: Mapping, block: int, fold: int, auxiliary: str, architecture: str, seed: str) -> dict:
    return {'identity': dict(identity), 'block': int(block), 'fold': fold, 'auxiliary': auxiliary,
            'architecture': architecture, 'seed_label': seed}


def leaf_key(identity: Mapping, target: str, fraction: int, auxiliary: str, arm: str,
             architecture: str, seed: str, fold: int) -> dict:
    require(arm in ARMS and fold in range(5) and seed in SEEDS and architecture in ARCHITECTURE_IDS, 'leaf_scope_invalid')
    return {'identity': dict(identity), 'target': target, 'fraction': fraction,
            'auxiliary': 'none' if arm == ARMS[0] else auxiliary, 'arm': arm,
            'architecture': architecture, 'seed_label': seed, 'fold': fold}


def fit_options(config: Mapping, device: str) -> dict:
    constants = config['architectures']['constants']
    return {'device_name': device, 'batch_size': constants['batch_size'],
            'max_epochs': constants['max_epochs'], 'patience': constants['patience'],
            'min_delta': constants['min_improvement']}


def spec_for(config: Mapping, architecture: str):
    return architecture_spec(next(row for row in config['architectures']['candidates'] if row['id'] == architecture))


def verify_fit(receipt: Mapping, config: Mapping, seed: int, *, transferred: bool, frozen: bool, device: str = "cpu") -> None:
    expected = fit_options(config, device)
    require(receipt.get('adamw_implementation') == ('foreach' if device == 'cpu' else 'library_default'), 'adamw_implementation_drift')
    require(all(receipt[k] == v for k, v in expected.items() if k != 'device_name'), 'fit_budget_drift')
    require(receipt['seed'] == seed and receipt['replay_shuffle_seed'] == seed + 100000, 'fit_seed_drift')
    require(receipt['state_finite'] and receipt['stopping_history_finite'], 'fit_nonfinite')
    require(receipt['initial_model_digest'] == receipt['replay_initial_model_digest'], 'replay_initialization_drift')
    require(receipt['transferred'] == transferred and receipt['freeze_trunk'] == frozen, 'transfer_mode_drift')
    require(receipt['replay_epochs'] == receipt['selected_epoch'] and 1 <= receipt['selected_epoch'] <= receipt['completed_epochs'] <= expected['max_epochs'], 'epoch_contract_drift')
    if frozen:
        require(receipt['freeze_shared_state_invariant'] and receipt['initial_shared_digest'] == receipt['final_shared_digest'], 'frozen_trunk_drift')


def run_pretraining(root: Path, store: SeawfbStore, config: Mapping, identity: Mapping,
                    block: int, fold: int, auxiliary: str, architecture: str, seed: str, device: str):
    key = pretraining_key(identity, block, fold, auxiliary, architecture, seed)
    output = private_root(root, config)
    cached = load_pretraining(output, key)
    numeric_seed = stable_seed('goal052-pretraining-v1', block, fold, auxiliary, architecture, seed)
    if cached is not None:
        verify_fit(cached[1]['fit'], config, numeric_seed, transferred=False, frozen=False, device=cached[1]['device'])
        return cached
    data = auxiliary_data(store, block, fold, auxiliary)
    state, fit = fit_pretraining_lifecycle(spec_for(config, architecture), data.discovery, data.stopping,
                                         data.replay, data.heads, seed=numeric_seed, **fit_options(config, device))
    verify_fit(fit, config, numeric_seed, transferred=False, frozen=False, device=device)
    receipt = save_pretraining(output, key, state, {'data': dict(data.metadata), 'fit': fit, 'device': device})
    return state, receipt


def run_target(root: Path, store: SeawfbStore, config: Mapping, identity: Mapping,
               target: str, fraction: int, auxiliary: str, arm: str, architecture: str,
               seed: str, fold: int, device: str):
    key = leaf_key(identity, target, fraction, auxiliary, arm, architecture, seed, fold)
    output = private_root(root, config)
    held = store.target_rows(target, fold, fraction, 'validation')
    cached = load_leaf(output, key, held.cell_ids, held.y)
    numeric_seed = target_seed(target, fraction, fold, architecture, seed)
    if cached is not None:
        verify_fit(cached[1]['fit'], config, numeric_seed, transferred=arm in ARMS[2:], frozen=arm == ARMS[2], device=cached[1]['device'])
        return cached[1]
    block = int(store.crossfit['focal_blocks'][target])
    q, q_receipt, state, pre_receipt = None, None, None, None
    if arm == ARMS[1]:
        loaded = baseline._load_q(root, baseline._config(root), identity['goal051_identity'], block, fold, auxiliary)
        require(loaded is not None, 'accepted_q_missing')
        q, q_receipt = loaded
    elif arm in ARMS[2:]:
        pre_key = pretraining_key(identity, block, fold, auxiliary, architecture, seed)
        loaded = load_pretraining(output, pre_key)
        require(loaded is not None, 'pretraining_missing')
        state, pre_receipt = loaded
    data = target_data(store, target, fold, fraction, q)
    scores, fit = fit_target_lifecycle(spec_for(config, architecture), data.discovery, data.stopping,
                                      data.replay, data.held_x, seed=numeric_seed,
                                      transferred_state=state, freeze_trunk=arm == ARMS[2], **fit_options(config, device))
    verify_fit(fit, config, numeric_seed, transferred=arm in ARMS[2:], frozen=arm == ARMS[2], device=device)
    receipt = {'data': dict(data.metadata), 'fit': fit, 'device': device,
               'q_receipt_digest': None if q_receipt is None else digest(q_receipt),
               'pretraining_receipt_digest': None if pre_receipt is None else digest(pre_receipt)}
    return save_leaf(output, key, data.held_cells, data.held_y, scores, receipt)


def selection_pretraining_tasks(blocks: Sequence[int]) -> list[tuple]:
    return [('pretrain', b, h, 'full', a, 'seed00') for b in sorted(set(blocks)) for h in range(5) for a in ARCHITECTURE_IDS]


def selection_tasks(primary: Sequence[str]) -> list[tuple]:
    return [('target', t, 100, 'full', ARMS[3], a, 'seed00', h) for t in primary for a in ARCHITECTURE_IDS for h in range(5)]


def remaining_pretraining_tasks(blocks: Sequence[int], architecture: str) -> list[tuple]:
    return [('pretrain', b, h, aux, architecture, s) for b in sorted(set(blocks)) for h in range(5)
            for aux in ('20', '80', 'full') for s in SEEDS if (aux, s) != ('full', 'seed00')]


def final_tasks(primary: Sequence[str], focal: Sequence[str], architecture: str) -> list[tuple]:
    bases = [('target', t, f, 'none', ARMS[0], architecture, s, h)
             for t, f in base_endpoints(primary, focal) for s in SEEDS for h in range(5)]
    return bases + [('target', t, f, aux, arm, architecture, s, h)
                    for t, f, aux in endpoint_grid(primary, focal) for arm in ARMS[1:] for s in SEEDS for h in range(5)]


_WORKER = None


def worker_init(root: str, device: str, identity: Mapping) -> None:
    global _WORKER
    torch.set_num_threads(1)
    root_path = Path(root)
    require(identity_at(root_path) == identity, 'worker_source_drift')
    _WORKER = (root_path, SeawfbStore(root_path), config_at(root_path), identity, device)


def worker(task: tuple) -> str:
    require(_WORKER is not None, 'worker_uninitialized')
    root, store, config, identity, device = _WORKER
    # A persistent store is shared by tasks, but target response caches are bounded.
    store._response_cache.clear()
    if task[0] == 'pretrain':
        _, receipt = run_pretraining(root, store, config, identity, *task[1:], device)
    else:
        receipt = run_target(root, store, config, identity, *task[1:], device)
    return digest(receipt['key'])


def execute(pool: ProcessPoolExecutor, stage: str, tasks: Sequence[tuple]) -> None:
    futures = {pool.submit(worker, task): task for task in tasks}
    for i, future in enumerate(as_completed(futures), 1):
        try:
            result = future.result()
        except BaseException:
            for pending in futures:
                pending.cancel()
            raise
        print(json.dumps({'stage': stage, 'done': i, 'total': len(tasks), 'checkpoint': result}), flush=True)


def read_folds(root: Path, store: SeawfbStore, config: Mapping, identity: Mapping,
               target: str, fraction: int, auxiliary: str, arm: str, architecture: str,
               seeds: Sequence[str]) -> tuple[dict, list[int]]:
    seed_folds, epochs = {}, []
    for seed in seeds:
        folds = []
        for fold in range(5):
            held = store.target_rows(target, fold, fraction, 'validation')
            key = leaf_key(identity, target, fraction, auxiliary, arm, architecture, seed, fold)
            loaded = load_leaf(private_root(root, config), key, held.cell_ids, held.y)
            require(loaded is not None, 'incomplete_neural_seed_fold_group')
            scores, receipt = loaded
            train = store.target_rows(target, fold, fraction, 'train')
            roles = _roles(train.indices, train.y, train.source_folds, fold)
            require(all(receipt['data'][k] == v for k, v in roles.items()), 'target_training_roles_drift')
            require(receipt['data']['target_subset_digest'] == digest(list(train.cell_ids)), 'target_subset_binding_drift')
            verify_fit(receipt['fit'], config, target_seed(target, fraction, fold, architecture, seed), transferred=arm in ARMS[2:], frozen=arm == ARMS[2], device=receipt['device'])
            if arm in ARMS[2:]:
                pre_key = pretraining_key(identity, int(store.crossfit['focal_blocks'][target]), fold, auxiliary, architecture, seed)
                pre = load_pretraining(private_root(root, config), pre_key)
                require(pre is not None and receipt['pretraining_receipt_digest'] == digest(pre[1]), 'pretraining_leaf_binding_drift')
                require(receipt['fit']['transfer_digest'] == state_digest(pre[0]) == receipt['fit']['initial_shared_digest'], 'transfer_state_drift')
            elif arm == ARMS[1]:
                q = baseline._load_q(root, baseline._config(root), identity['goal051_identity'], int(store.crossfit['focal_blocks'][target]), fold, auxiliary)
                require(q is not None and digest(q[1]) == receipt['q_receipt_digest'], 'q_leaf_binding_drift')
            folds.append({'fold': fold, 'cell_id': held.cell_ids, 'y': held.y, 'score': scores})
            epochs.append(receipt['fit']['selected_epoch'])
        seed_folds[seed] = folds
    return seed_folds, epochs


def aggregate_selection(root: Path, store: SeawfbStore, config: Mapping, identity: Mapping) -> dict:
    metrics = {}
    for architecture in ARCHITECTURE_IDS:
        metrics[architecture] = {}
        for target in store.primary_targets:
            store._response_cache.clear()
            folds, _ = read_folds(root, store, config, identity, target, 100, 'full', ARMS[3], architecture, ('seed00',))
            metrics[architecture][target] = summarize_oof(folds['seed00'])
    result = select_architecture(metrics, store.crossfit['focal_blocks'])
    result['identity'] = dict(identity)
    return result


def aggregate_final(root: Path, store: SeawfbStore, config: Mapping, identity: Mapping, selection: Mapping) -> dict:
    baseline_summary = read_json(root / BASE_SUMMARY)
    controls = {(e['target'], e['target_fraction']): e for e in baseline_summary['endpoints']}
    architecture = selection['selected_architecture']
    conditions, epoch_summaries, target_only = [], {}, {}
    for target, fraction, auxiliary in sorted(endpoint_grid(store.primary_targets, store.focal_targets)):
        if (target, fraction) not in target_only:
            target_only.clear()
        store._response_cache.clear()
        arm_folds = {}
        for arm in ARMS:
            cache_key = (target, fraction)
            if arm == ARMS[0] and cache_key in target_only:
                arm_folds[arm] = target_only[cache_key]
                continue
            seed_folds, epochs = read_folds(root, store, config, identity, target, fraction, auxiliary, arm, architecture, SEEDS)
            arm_folds[arm] = seed_average_folds(seed_folds)
            epoch_key = '|'.join((target, str(fraction), 'none' if arm == ARMS[0] else auxiliary, arm))
            epoch_summaries[epoch_key] = {'selected_epochs': epochs, 'median_rounded': int(np.rint(np.median(epochs)))}
            if arm == ARMS[0]:
                target_only[cache_key] = arm_folds[arm]
        control = controls[(target, fraction)]
        family = control['best_non_null_family']
        conventional = control['families'][family]['selected']['metrics']
        q_metrics = control['q_linear'][auxiliary]['metrics']
        condition = summarize_condition(target, fraction, auxiliary, arm_folds, conventional, q_metrics,
                                        selection_target=target in store.primary_targets)
        conditions.append(condition)
    return {'schema_version': 'goal052-summary-v1', 'status': 'complete_pending_validation',
            'identity': dict(identity), 'selected_architecture': architecture,
            'selection': dict(selection), 'conditions': conditions,
            'panels': summarize_panels(conditions, store.primary_targets),
            'selected_epochs': epoch_summaries, 'outer_response_rows_read': 0,
            'interpretation': 'relative_habitat_suitability_inner_spatial_generalisation',
            'conventional_seed_pairing': False, 'neural_seed_pairing': True}


def validate_pretraining(root: Path, store: SeawfbStore, config: Mapping, identity: Mapping, architecture: str) -> int:
    tasks = selection_pretraining_tasks(list(store.crossfit['focal_blocks'].values()))
    tasks += remaining_pretraining_tasks(list(store.crossfit['focal_blocks'].values()), architecture)
    grouped = {}
    for _, block, fold, auxiliary, candidate, seed in tasks:
        grouped.setdefault((block, fold, auxiliary), []).append((candidate, seed))
    checked = 0
    for (block, fold, auxiliary), variants in sorted(grouped.items()):
        # Rebuild each of the 150 row contracts once, independently of saved fits.
        data = auxiliary_data(store, block, fold, auxiliary)
        expected_metadata = dict(data.metadata)
        del data
        for candidate, seed in variants:
            key = pretraining_key(identity, block, fold, auxiliary, candidate, seed)
            loaded = load_pretraining(private_root(root, config), key)
            require(loaded is not None, 'pretraining_inventory_incomplete')
            state, receipt = loaded
            require(receipt['data'] == expected_metadata, 'auxiliary_training_roles_drift')
            numeric = stable_seed('goal052-pretraining-v1', block, fold, auxiliary, candidate, seed)
            verify_fit(receipt['fit'], config, numeric, transferred=False, frozen=False, device=receipt['device'])
            require(receipt['fit']['final_shared_digest'] == state_digest(state), 'pretraining_final_state_drift')
            checked += 1
    require(checked == 900, 'pretraining_inventory_drift')
    return checked


def validate_outputs(root: Path) -> dict:
    validated = validate_inputs(root)
    config, identity = config_at(root), validated['identity']
    store = SeawfbStore(root)
    output = private_root(root, config)
    selection = aggregate_selection(root, store, config, identity)
    require(digest(selection) == digest(read_json(output / 'selection.json')), 'selection_replay_drift')
    validate_pretraining(root, store, config, identity, selection['selected_architecture'])
    replay = aggregate_final(root, store, config, identity, selection)
    require(digest(replay) == digest(read_json(root / config['execution']['tracked_summary'])), 'summary_replay_drift')
    return {'status': 'goal052_complete_valid', 'identity': identity,
            'summary_sha256': sha256_file(root / config['execution']['tracked_summary']),
            'unique_target_lifecycles': 42345, 'target_task_submissions': 42710,
            'selection_leaves_reused': 365, 'pretraining_lifecycles': 900,
            'conditions': 449, 'outer_response_rows_read': 0}


def host_runtime(device: str) -> dict:
    return {'host': platform.node(), 'system': platform.system(), 'machine': platform.machine(),
            'torch': torch.__version__, 'device': device,
            'device_name': torch.cuda.get_device_name(0) if device == 'cuda' else platform.processor()}


def run_all(root: Path, workers: int, device: str) -> dict:
    validated = validate_inputs(root)
    config, identity = config_at(root), validated['identity']
    require(workers >= 1 and (device == 'cpu' or workers == 1), 'worker_device_budget_invalid')
    canary = read_json(root / config['execution']['canary_receipt'])
    require(canary['status'] == 'goal052_canary_valid' and canary['identity'] == identity and canary['runtime'] == host_runtime(device), 'current_host_canary_required')
    require(workers <= canary['qualified_workers'], 'worker_budget_exceeds_canary')
    profile = read_json(root / 'metadata/goal052_full_epoch_profile.json')
    require(profile['status'] == 'goal052_full_epoch_profile_valid' and profile['identity'] == identity
            and profile['runtime'] == host_runtime(device), 'current_host_full_epoch_profile_required')
    output = private_root(root, config)
    output.mkdir(parents=True, exist_ok=True)
    # Kernel-held lock survives scheduler crashes without a stale-lock recovery gate.
    lock_path = output / 'run.lock'
    lock = lock_path.open('a+')
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise ValueError('goal052_scheduler_already_running') from None
    lock.seek(0)
    lock.truncate()
    json.dump({'pid': os.getpid(), 'runtime': host_runtime(device), 'identity': identity}, lock)
    lock.flush()
    try:
        store = SeawfbStore(root)
        blocks = list(store.crossfit['focal_blocks'].values())
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'), initializer=worker_init, initargs=(str(root), device, identity)) as pool:
            execute(pool, 'selection_pretraining', selection_pretraining_tasks(blocks))
            execute(pool, 'selection_targets', selection_tasks(store.primary_targets))
            selection = aggregate_selection(root, store, config, identity)
            atomic_json(output / 'selection.json', selection)
            architecture = selection['selected_architecture']
            execute(pool, 'remaining_pretraining', remaining_pretraining_tasks(blocks, architecture))
            execute(pool, 'final_targets', final_tasks(store.primary_targets, store.focal_targets, architecture))
        summary = aggregate_final(root, store, config, identity, selection)
        atomic_json(root / config['execution']['tracked_summary'], summary)
        complete = validate_outputs(root)
        atomic_json(output / 'complete.json', complete)
        return complete
    finally:
        lock.seek(0)
        lock.truncate()
        json.dump({'status': 'idle'}, lock)
        lock.close()


def _bounded_rows(rows: IndexedRows, per_head: int = 128) -> IndexedRows:
    """Deterministic row caps used only for a metric-free engineering canary."""
    rng = np.random.default_rng(52001)
    if rows.head_index is None:
        selected = np.sort(rng.choice(len(rows.y), min(4096, len(rows.y)), replace=False))
        return rows.subset(selected)
    selected = np.concatenate([rng.choice(np.flatnonzero(rows.head_index == head),
                                         min(per_head, int(np.sum(rows.head_index == head))), replace=False)
                               for head in np.unique(rows.head_index)])
    bounded = rows.subset(np.sort(selected))
    counts = np.bincount(bounded.head_index)
    weights = len(selected) / (len(counts) * counts[bounded.head_index])
    return IndexedRows(bounded.features, bounded.indices, bounded.y, bounded.head_index, weights)


_CANARY_STORE = None


def _canary_worker(root_name: str, device: str, identity: Mapping, block: int, fold: int, target: str) -> dict:
    started = time.monotonic()
    root = Path(root_name)
    require(identity_at(root) == identity, 'canary_source_drift')
    global _CANARY_STORE
    config = config_at(root)
    if _CANARY_STORE is None:
        _CANARY_STORE = SeawfbStore(root)
    store = _CANARY_STORE
    require(store.root == root, 'canary_store_root_drift')
    store._response_cache.clear()
    data = auxiliary_data(store, block, fold, 'full')
    # Construct every full-auxiliary row and retain its memory throughout the fit.
    # Optimization is explicitly capped and never promoted to production leaves.
    memory_after_full_data = baseline._peak_rss_bytes()
    discovery, stopping, replay = [_bounded_rows(rows) for rows in (data.discovery, data.stopping, data.replay)]
    options = fit_options(config, device)
    options.update(max_epochs=1, patience=1)
    spec = spec_for(config, 'seawfb_scale')
    pre_seed = stable_seed('goal052-canary-pretraining-v1', block, fold)
    state, pre_fit = fit_pretraining_lifecycle(spec, discovery, stopping, replay, data.heads, seed=pre_seed, **options)
    repeated, repeat_fit = fit_pretraining_lifecycle(spec, discovery, stopping, replay, data.heads, seed=pre_seed, **options)
    require(state_digest(state) == state_digest(repeated), 'canary_pretraining_not_deterministic')
    loaded = baseline._load_q(root, baseline._config(root), identity['goal051_identity'], block, fold, 'full')
    require(loaded is not None, 'canary_q_missing')
    q, _ = loaded
    fits, predictions = {}, {}
    for arm in ARMS:
        target_rows = target_data(store, target, fold, 100, q if arm == ARMS[1] else None)
        scores, receipt = fit_target_lifecycle(spec, _bounded_rows(target_rows.discovery),
                _bounded_rows(target_rows.stopping), _bounded_rows(target_rows.replay), target_rows.held_x[:1024],
                seed=target_seed(target, 100, fold, 'seawfb_scale', 'seed00'),
                transferred_state=state if arm in ARMS[2:] else None, freeze_trunk=arm == ARMS[2], **options)
        fits[arm] = receipt
        predictions[arm] = digest(scores.tolist())
    require(len({fits[a]['initial_head_digest'] for a in ARMS}) == 1, 'canary_paired_head_drift')
    require(fits[ARMS[2]]['initial_model_digest'] == fits[ARMS[3]]['initial_model_digest'], 'canary_transfer_initialization_drift')
    return {'pid': os.getpid(), 'runtime_seconds': time.monotonic() - started,
            'full_auxiliary_data': dict(data.metadata), 'memory_after_full_data_bytes': memory_after_full_data,
            'peak_rss_bytes': baseline._peak_rss_bytes(),
            'peak_cuda_allocated_bytes': int(torch.cuda.max_memory_allocated()) if device == 'cuda' else None,
            'pretraining_fit': pre_fit,
            'repeat_pretraining_digest': state_digest(repeated), 'target_fits': fits,
            'prediction_digests': predictions, 'q_model_sha256': loaded[1]['model_sha256'],
            'bounded_pretraining_rows': {role: len(rows.y) for role, rows in zip(('discovery', 'stopping', 'replay'), (discovery, stopping, replay))}}


def canary(root: Path, device: str, workers: int = 1) -> dict:
    validated = validate_inputs(root)
    identity, config = validated['identity'], config_at(root)
    require(1 <= workers <= 2 and (device == 'cpu' or workers == 1), 'canary_worker_limit')
    crossfit = read_json(root / CROSSFIT_PATH)
    curves = read_json(root / CURVES_PATH)
    # Select the largest accepted full-q expanded row count, without using scores.
    q_config = baseline._config(root)
    candidates = []
    for block, fold, auxiliary in baseline.q_surface_specs(crossfit):
        if auxiliary == 'full':
            loaded = baseline._load_q(root, q_config, identity['goal051_identity'], block, fold, auxiliary)
            require(loaded is not None, 'canary_q_missing')
            candidates.append((loaded[1]['expanded_rows'], block, fold))
    _, block, fold = max(candidates)
    primary = curves['applies_to']['primary_targets']
    target = sorted(t for t in primary if int(crossfit['focal_blocks'][t]) == block)[0]
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        # Two jobs per worker also exercise repeated tasks in persistent processes.
        futures = [pool.submit(_canary_worker, str(root), device, identity, block, fold, target) for _ in range(2 * workers)]
        results = [future.result() for future in futures]
    require(len({r['pid'] for r in results}) == workers, 'canary_concurrency_not_exercised')
    require(len({digest(r['prediction_digests']) for r in results}) == 1, 'canary_spawn_predictions_differ')
    require(len({r['repeat_pretraining_digest'] for r in results}) == 1, 'canary_spawn_trunks_differ')
    receipt = {'status': 'goal052_canary_valid', 'identity': identity, 'runtime': host_runtime(device),
               'qualified_workers': workers, 'scope': 'full_auxiliary_memory_bounded_one_epoch_optimization',
               'production_epoch_throughput_measured': False, 'architecture': 'seawfb_scale',
               'block': block, 'fold': fold, 'target': target, 'results': results,
               'ecological_metrics_computed': False, 'outer_response_rows_read': 0,
               'created_utc': datetime.now(timezone.utc).isoformat()}
    atomic_json(root / config['execution']['canary_receipt'], receipt)
    return receipt


def status(root: Path) -> dict:
    config = config_at(root)
    output = private_root(root, config)
    complete = output / 'complete.json'
    return {'status': 'complete' if complete.exists() else 'incomplete',
            'completion': read_json(complete) if complete.exists() else None,
            'pretraining_receipts': len(list((output / 'pretraining').glob('*.json'))),
            'target_leaf_receipts': len(list((output / 'leaves').glob('*.json'))),
            'run_lock': read_json(output / 'run.lock') if (output / 'run.lock').exists() else None,
            'outer_response_rows_read': 0}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate-inputs', 'canary', 'profile', 'run', 'aggregate', 'validate', 'status'))
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--device', choices=('cpu', 'cuda', 'mps'), default='cpu')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == 'validate-inputs':
        result = validate_inputs(root)
    elif args.command == 'run':
        result = run_all(root, args.workers, args.device)
    elif args.command == 'canary':
        result = canary(root, args.device, args.workers)
    elif args.command == 'profile':
        from .goal052_profile import profile
        with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context('spawn')) as pool:
            result = pool.submit(profile, root, args.device).result()
    elif args.command == 'validate':
        result = validate_outputs(root)
    elif args.command == 'status':
        result = status(root)
    else:
        validated = validate_inputs(root)
        config, store = config_at(root), SeawfbStore(root)
        selection = aggregate_selection(root, store, config, validated['identity'])
        atomic_json(private_root(root, config) / 'selection.json', selection)
        result = aggregate_final(root, store, config, validated['identity'], selection)
        atomic_json(root / config['execution']['tracked_summary'], result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
