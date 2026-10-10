from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SRC = ROOT / "data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1/src"
sys.path.insert(0, str(ARCHIVE_SRC))
SPEC = importlib.util.spec_from_file_location(
    "tasmania_pseudoabsence_neural", ROOT / "scripts/tasmania_pseudoabsence_neural.py",
)
assert SPEC and SPEC.loader
neural = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = neural
SPEC.loader.exec_module(neural)


def _role(n: int = 4) -> dict[str, np.ndarray]:
    x = np.zeros((n, 77), dtype=np.float32)
    x[:, :25] = np.arange(n * 25, dtype=np.float32).reshape(n, 25)
    x[:, 25] = 1.0
    return {
        "x": x,
        "y": np.asarray([0, 1] * (n // 2), dtype=np.float32),
        "cells": np.asarray([f"c{i}" for i in range(n)]),
    }


def _inner_arrays() -> dict[str, np.ndarray]:
    held = np.zeros((3, 77), dtype=np.float32)
    held[:, 26] = 1.0
    arrays = {"x_held": held, "held_cells": np.asarray(["h0", "h1", "h2"])}
    for endpoint in neural.ENDPOINTS:
        prefix = f"target_{neural.SLUGS[endpoint]}"
        for role in ("discovery", "stopping", "replay"):
            row = _role()
            arrays.update({
                f"{prefix}_x_{role}": row["x"],
                f"{prefix}_y_{role}": row["y"],
                f"{prefix}_cells_{role}": row["cells"],
            })
    return arrays


def _outer_arrays() -> dict[str, np.ndarray]:
    held = np.zeros((3, 77), dtype=np.float32)
    held[:, 26] = 1.0
    arrays = {
        "x_held": held,
        "held_cells": np.asarray(["h0", "h1", "h2"]),
        "held_patch": np.asarray([0, 1, 0], dtype=np.int32),
    }
    for endpoint in neural.ENDPOINTS:
        prefix = f"target_{neural.SLUGS[endpoint]}"
        row = _role()
        arrays.update({
            f"{prefix}_x": row["x"],
            f"{prefix}_y": row["y"],
            f"{prefix}_cells": row["cells"],
        })
    return arrays


def _write_prediction_npz(path: Path, *, maps: bool = False, shift: float = 0.0) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {
        "grid_cell_id": np.asarray(["h0", "h1", "h2"]),
        "scores": np.asarray([0.1, 0.5, 0.9], dtype=np.float32) + np.float32(shift),
    }
    if maps:
        arrays.update({
            "map_grid_cell_id": np.asarray([f"m{i:05d}" for i in range(71023)]),
            "sensitivity_map_scores": np.linspace(0, 1, 71023, dtype=np.float32),
            "accepted_primary_map_scores": np.linspace(1, 0, 71023, dtype=np.float32),
        })
    np.savez_compressed(path, **arrays)
    return arrays


def _prediction_receipt(path: Path, arrays: dict[str, np.ndarray], *, maps: bool = False) -> dict[str, object]:
    receipt: dict[str, object] = {
        "prediction_sha256": neural.sha256_file(path),
        "prediction_digest": neural.array_digest(arrays["scores"]),
    }
    if maps:
        receipt["map"] = {"prediction_digest": neural.array_digest(arrays["sensitivity_map_scores"])}
        receipt["accepted_primary_map"] = {"prediction_digest": neural.array_digest(arrays["accepted_primary_map_scores"])}
    return receipt


def test_inventory_scope_and_five_fold_epoch_policy_are_closed():
    assert neural.inventory_counts() == {
        "inner_logical_tasks": 2800,
        "inner_physical_fits": 5600,
        "outer_logical_tasks": 560,
        "outer_physical_fits": 560,
        "total_logical_tasks": 3360,
        "total_physical_fits": 6160,
    }
    assert neural.lower_median([9, 1, 5, 7, 3]) == 5
    with pytest.raises(neural.NeuralSensitivityError, match="five_folds"):
        neural.lower_median([1, 2, 3, 4])
    records = [
        {
            "target": target, "endpoint": endpoint, "method": method, "seed": seed,
            "fold_epochs": [1, 3, 5, 7, 9], "full_training_epochs": 5,
        }
        for target in neural.SPECIES for endpoint in neural.ENDPOINTS
        for method in neural.METHODS for seed in neural.SEEDS
    ]
    assert len(neural.validate_epoch_completeness(records, expected=560)) == 560
    with pytest.raises(neural.NeuralSensitivityError, match="inventory_incomplete"):
        neural.validate_epoch_completeness(records[:-1], expected=560)

    closure_records = [
        {
            "task": {
                "target": task.target, "held_fold": task.held_fold,
                "endpoint": task.endpoint, "method": task.method, "seed": task.seed,
            },
            "selected_epoch": neural.FOLDS.index(task.held_fold) + 1,
        }
        for task in neural.build_inner_inventory()
    ]
    closure = {
        "schema_version": "tasmania-pseudoabsence-neural-inner-closure-v2",
        "success": True, "records": closure_records,
    }
    policy = neural._inner_epoch_policy(closure)
    assert len(policy) == 560
    assert {tuple(values) for values, _median in policy.values()} == {(1, 2, 3, 4, 5)}
    assert set(median for _values, median in policy.values()) == {3}
    closure["records"] = closure_records[:-1]
    with pytest.raises(neural.NeuralSensitivityError, match="inventory_incomplete"):
        neural._inner_epoch_policy(closure)


def test_class_support_cell_identity_and_outer_label_boundary_are_enforced():
    assert neural.validate_inner_arrays(_inner_arrays())["held_rows"] == 3
    assert neural.validate_outer_arrays(_outer_arrays())["held_rows"] == 3
    bad = _inner_arrays()
    bad["target_fraction100_full_y_replay"] = np.zeros(4, dtype=np.float32)
    with pytest.raises(neural.NeuralSensitivityError, match="class_support"):
        neural.validate_inner_arrays(bad)
    bad = _outer_arrays()
    bad["target_fraction25_ladder00_cells"][1] = bad["target_fraction25_ladder00_cells"][0]
    with pytest.raises(neural.NeuralSensitivityError, match="cell_support"):
        neural.validate_outer_arrays(bad)
    bad = _outer_arrays()
    bad["y_held"] = np.ones(3, dtype=np.float32)
    with pytest.raises(neural.NeuralSensitivityError, match="outer_held_response_labels_prohibited"):
        neural.validate_outer_arrays(bad)


def test_target_support_mask_is_fit_from_filtered_replay_and_applied_to_held():
    arrays = _inner_arrays()
    result = neural._mask_inner_case(arrays, "fraction100/full")
    assert result["support"].columns[25]
    assert not result["support"].columns[26]
    assert np.array_equal(result["views"]["replay"], arrays["target_fraction100_full_x_replay"])
    assert np.all(result["views"]["held"][:, 26] == 0)
    assert result["audits"]["held"]["affected_rows"] == 3
    outer = neural._mask_outer_case(_outer_arrays(), "fraction100/full")
    assert not outer["support"].columns[26]
    assert np.all(outer["held"][:, 26] == 0)


def test_predictor_dtype_tampering_is_rejected_before_training():
    bad = _inner_arrays()
    bad["target_fraction25_ladder00_x_replay"] = bad["target_fraction25_ladder00_x_replay"].astype(np.float64)
    with pytest.raises(neural.NeuralSensitivityError, match="predictor_array_invalid"):
        neural.validate_inner_arrays(bad)


def test_closed_prediction_file_tampering_is_rejected(tmp_path: Path):
    path = tmp_path / "predictions.npz"
    arrays = _write_prediction_npz(path)
    receipt = _prediction_receipt(path, arrays)
    checked = neural._validate_prediction_file(path, receipt, expect_map=False)
    assert np.array_equal(checked["scores"], arrays["scores"])
    _write_prediction_npz(path, shift=0.01)
    with pytest.raises(neural.NeuralSensitivityError, match="prediction_file_mismatch"):
        neural._validate_prediction_file(path, receipt, expect_map=False)


def test_map_payload_is_full_endpoint_only_and_binds_primary_scores(tmp_path: Path):
    reduced = tmp_path / "reduced.npz"
    reduced_arrays = _write_prediction_npz(reduced)
    neural._validate_prediction_file(reduced, _prediction_receipt(reduced, reduced_arrays), expect_map=False)
    with pytest.raises(neural.NeuralSensitivityError, match="prediction_inventory"):
        neural._validate_prediction_file(reduced, _prediction_receipt(reduced, reduced_arrays), expect_map=True)
    full = tmp_path / "full.npz"
    full_arrays = _write_prediction_npz(full, maps=True)
    receipt = _prediction_receipt(full, full_arrays, maps=True)
    neural._validate_prediction_file(full, receipt, expect_map=True)
    missing_map_receipt = dict(receipt)
    missing_map_receipt.pop("map")
    with pytest.raises(neural.NeuralSensitivityError, match="map_receipt_missing"):
        neural._validate_prediction_file(full, missing_map_receipt, expect_map=True)
    receipt["accepted_primary_map"] = {"prediction_digest": "0" * 64}
    with pytest.raises(neural.NeuralSensitivityError, match="primary_map_prediction_digest"):
        neural._validate_prediction_file(full, receipt, expect_map=True)


def test_auxiliary_mutation_is_detected_by_actual_bytes(tmp_path: Path):
    state = tmp_path / "aux.pt"
    state.write_bytes(b"accepted-state")
    expected = neural.sha256_file(state)
    neural._require_file_sha(state, expected, "auxiliary_mutated")
    state.write_bytes(b"changed-state")
    with pytest.raises(neural.NeuralSensitivityError, match="auxiliary_mutated"):
        neural._require_file_sha(state, expected, "auxiliary_mutated")


def test_attempt_intent_is_durable_and_refuses_orphan_retry(tmp_path: Path):
    task = neural.InnerTask(neural.SPECIES[0], neural.FOLDS[0], neural.ENDPOINTS[0], neural.METHODS[0], neural.SEEDS[0])
    output = tmp_path / "results"
    destination = output / "inner/leaves" / neural._task_digest(task, "inner")
    preparation = {"bindings": {"runner_sha256": "a" * 64}}
    attempt = neural._begin_fit_attempt(
        tmp_path, output, "inner", task, destination, ("discovery", "replay"), preparation,
    )
    assert (attempt / "intent.json").is_file()
    with pytest.raises(neural.NeuralSensitivityError, match="orphan_or_failed_fit_intent"):
        neural._begin_fit_attempt(
            tmp_path, output, "inner", task, destination, ("discovery", "replay"), preparation,
        )


def test_worker_failure_is_persisted_at_the_attempt_before_propagation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    task = neural.InnerTask(neural.SPECIES[0], neural.FOLDS[0], neural.ENDPOINTS[0], neural.METHODS[0], neural.SEEDS[0])
    attempt = tmp_path / "attempt"
    attempt.mkdir()

    def fail(**_kwargs: object) -> None:
        raise RuntimeError("synthetic worker failure")

    monkeypatch.setattr(neural, "_fit_inner_task", fail)
    with pytest.raises(RuntimeError, match="synthetic worker failure"):
        neural._worker_inner({"task": task, "attempt": attempt})
    record = json.loads((attempt / "failed.json").read_text(encoding="utf-8"))
    assert record["lane"] == "inner"
    assert record["task_digest"] == neural._task_digest(task, "inner")
    assert record["error_type"] == "RuntimeError"


def test_preparation_requires_the_complete_200_state_recovery_index():
    records = [
        {"target": target, "held_fold": fold, "seed": seed, "state_sha256": "a" * 64}
        for target in neural.SPECIES for fold in neural.FOLDS for seed in neural.SEEDS
    ]
    preparation = {"auxiliary_recovery": {"records": records}}
    assert len(neural._preparation_recovery_index(preparation)) == 200
    preparation["auxiliary_recovery"]["records"] = records[:-1]
    with pytest.raises(neural.NeuralSensitivityError, match="recovery_inventory_drift"):
        neural._preparation_recovery_index(preparation)


def test_exact_lane_inventory_rejects_unexpected_leaf_intent_or_attempt(tmp_path: Path):
    task = neural.InnerTask(neural.SPECIES[0], neural.FOLDS[0], neural.ENDPOINTS[0], neural.METHODS[0], neural.SEEDS[0])
    digest = neural._task_digest(task, "inner")
    (tmp_path / "inner/leaves" / digest).mkdir(parents=True)
    (tmp_path / "inner/attempts" / digest).mkdir(parents=True)
    (tmp_path / "inner/intents").mkdir(parents=True)
    (tmp_path / "inner/intents" / f"{digest}.json").write_text("{}", encoding="utf-8")
    assert neural._lane_artifact_inventory_complete(tmp_path, "inner", [task])
    (tmp_path / "inner/leaves/unexpected").mkdir()
    with pytest.raises(neural.NeuralSensitivityError, match="inventory_has_extra"):
        neural._lane_artifact_inventory_complete(tmp_path, "inner", [task])


def test_completed_attempt_requires_running_and_every_physical_stage(tmp_path: Path):
    task = neural.InnerTask(neural.SPECIES[0], neural.FOLDS[0], neural.ENDPOINTS[0], neural.METHODS[0], neural.SEEDS[0])
    output = tmp_path / "results"
    destination = output / "inner/leaves" / neural._task_digest(task, "inner")
    preparation = {"bindings": {"runner_sha256": "a" * 64}}
    attempt = neural._begin_fit_attempt(
        tmp_path, output, "inner", task, destination, ("discovery", "replay"), preparation,
    )
    running = {
        "schema_version": "tasmania-pseudoabsence-neural-fit-running-v2",
        "lane": "inner", "task": task.__dict__, "task_digest": neural._task_digest(task, "inner"),
        "fit_started": True, "physical_stages_entered": ["discovery", "replay"],
        "physical_fits_started": 2,
    }
    (attempt / "running.json").write_bytes(neural._canonical(running) + b"\n")
    receipt = {
        "task_digest": neural._task_digest(task, "inner"), "receipt_digest": "b" * 64,
        "physical_stages_completed": ["discovery", "replay"], "physical_fits": 2,
    }
    completed = {
        "schema_version": "tasmania-pseudoabsence-neural-fit-complete-v2",
        "task_digest": receipt["task_digest"], "receipt_digest": receipt["receipt_digest"],
    }
    (attempt / "completed.json").write_bytes(neural._canonical(completed) + b"\n")
    neural._validate_completed_attempt(
        output, output / "inner/intents" / f"{receipt['task_digest']}.json",
        attempt, destination, "inner", task, receipt, preparation,
    )
    running["physical_fits_started"] = 1
    (attempt / "running.json").write_bytes(neural._canonical(running) + b"\n")
    with pytest.raises(neural.NeuralSensitivityError, match="physical_stage_evidence"):
        neural._validate_completed_attempt(
            output, output / "inner/intents" / f"{receipt['task_digest']}.json",
            attempt, destination, "inner", task, receipt, preparation,
        )


def test_non_thylogale_null_negative_control_is_not_counted():
    assert not neural._has_exact_negative_control({"thylogale_negative_control": None})
    assert neural._has_exact_negative_control({"thylogale_negative_control": {"status": "exact"}})


def test_live_thylogale_inner_fixture_uses_metadata_hash_not_absent_receipt_digest():
    leaf = next(
        path.parent
        for path in (ROOT / neural.GOAL035_LEAF_REL).glob("*/metadata.json")
        if (metadata := json.loads(path.read_text(encoding="utf-8"))).get("target") == neural.THYLOGALE
        and metadata.get("held_fold") == neural.FOLDS[0]
    )
    metadata = json.loads((leaf / "metadata.json").read_text(encoding="utf-8"))
    assert "receipt_digest" not in metadata
    task = neural.InnerTask(neural.THYLOGALE, neural.FOLDS[0], neural.ENDPOINTS[0], neural.METHODS[0], neural.SEEDS[0])
    artifact_id = f"target/{task.endpoint}/seed{task.seed}/{task.method}"
    artifact = next(row for row in metadata["artifacts"] if row["artifact_id"] == artifact_id)
    semantic = {
        "selected_epoch": artifact["selected_epoch"],
        "discovery_executed_epochs": artifact["discovery_executed_epochs"],
        "stopping_status": artifact["stopping_status"],
        "initial_model_digest": artifact["initial_model_digest"],
        "replay_initial_model_digest": artifact["replay_initial_model_digest"],
        "initial_shared_digest": artifact["initial_shared_digest"],
        "final_shared_digest": artifact["final_shared_digest"],
        "initial_head_digest": artifact["initial_head_digest"],
        "model_digest": artifact["model_digest"],
        "lifecycle_prediction_digest": artifact["prediction_digest"],
    }
    method_order = (
        "target_only_resmlp", "legacy_pooled_finetune", "multihead_frozen_trunk",
        "multihead_full_finetune", "target_plus_q_linear", "target_plus_q_deep",
    )
    original = np.load(leaf / "predictions.npy", allow_pickle=False)
    scores = original[
        neural.SEEDS.index(task.seed), neural.ENDPOINTS.index(task.endpoint),
        method_order.index(task.method),
    ]
    authority = {
        "leaf_path": str(leaf.relative_to(ROOT)),
        "metadata_sha256": neural.sha256_file(leaf / "metadata.json"),
        "predictions_sha256": neural.sha256_file(leaf / "predictions.npy"),
    }
    result = neural._original_inner_comparison(
        ROOT, task, semantic, scores, authority, int(artifact["fit_seed"]),
    )
    assert result["original_leaf_metadata_sha256"] == authority["metadata_sha256"]
    assert result["original_leaf_metadata_digest"] == neural.digest_value(metadata)


def test_single_thread_scope_attests_live_pools():
    from threadpoolctl import threadpool_limits

    with threadpool_limits(limits=1):
        records = neural._attest_live_thread_pools()
    assert isinstance(records, list)
    assert all(row["num_threads"] == 1 for row in records)


def test_worker_hard_termination_does_not_wait_for_overrunning_processes():
    class Process:
        pid = 43210

        def __init__(self) -> None:
            self.alive = True
            self.terminated = False

        def is_alive(self) -> bool:
            return self.alive

        def terminate(self) -> None:
            self.terminated = True
            self.alive = False

        def join(self, timeout: float) -> None:
            assert timeout >= 0

        def kill(self) -> None:
            self.alive = False

    process = Process()

    class Pool:
        _processes = {process.pid: process}

    assert neural._terminate_pool_workers(Pool()) == [process.pid]
    assert process.terminated and not process.is_alive()


def test_staged_source_import_refuses_manifest_not_bound_to_recovery(tmp_path: Path):
    aggregate_source = ROOT / neural.RECOVERY_AGGREGATE_REL
    aggregate_target = tmp_path / neural.RECOVERY_AGGREGATE_REL
    aggregate_target.parent.mkdir(parents=True)
    aggregate_target.write_bytes(aggregate_source.read_bytes())
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "reconstruction-manifest.json").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(neural.NeuralSensitivityError, match="stage_manifest_binding"):
        neural._load_staged(tmp_path, stage)


def test_caps_must_be_smoke_bound_measured_and_explicitly_approved(tmp_path: Path):
    preparation = {"receipt_digest": "a" * 64}
    smoke = {
        "receipt_digest": "b" * 64,
        "observed": {
            "maximum_leaf_wall_seconds": 10.0,
            "maximum_worker_peak_rss_bytes": 1000,
            "private_storage_bytes": 2000,
        },
    }
    value = {
        "schema_version": "tasmania-pseudoabsence-neural-production-caps-v2",
        "status": "approved", "preparation_receipt_digest": preparation["receipt_digest"],
        "smoke_receipt_digest": smoke["receipt_digest"], "source_sha256": neural._source_sha(),
        "caps": {
            "max_workers": 3, "threads_per_worker": 1, "maximum_in_flight": 3,
            "max_leaf_wall_seconds": 20.0, "max_stage_wall_seconds": 1000.0,
            "max_worker_peak_rss_bytes": 2000, "max_private_storage_bytes": 4000,
        },
    }
    value["receipt_digest"] = neural.digest_value(value)
    tmp_path.joinpath("production-caps.json").write_bytes(neural._canonical(value) + b"\n")
    assert neural._load_production_caps(tmp_path, preparation, smoke)["status"] == "approved"
    value["caps"]["max_leaf_wall_seconds"] = 5.0
    value["receipt_digest"] = neural.digest_value({k: v for k, v in value.items() if k != "receipt_digest"})
    tmp_path.joinpath("production-caps.json").write_bytes(neural._canonical(value) + b"\n")
    with pytest.raises(neural.NeuralSensitivityError, match="wall_cap_below_smoke"):
        neural._load_production_caps(tmp_path, preparation, smoke)


def test_smoke_semantic_equivalence_excludes_timing_and_serialization_only():
    base = {
        "task": {"target": neural.SMOKE_TARGET}, "model_digest": "a" * 64,
        "prediction_digest": "b" * 64, "selected_epoch": 17,
        "process_id": 1, "wall_seconds": 1.0, "peak_rss_bytes": 100,
        "prediction_sha256": "c" * 64, "receipt_digest": "d" * 64,
        "model_receipt": {"model_sha256": "e" * 64},
    }
    repeat = {**base, "process_id": 2, "wall_seconds": 2.0, "peak_rss_bytes": 200, "prediction_sha256": "f" * 64, "receipt_digest": "0" * 64, "model_receipt": {"model_sha256": "1" * 64}}
    assert neural._semantic_smoke_receipt(base) == neural._semantic_smoke_receipt(repeat)
    repeat["selected_epoch"] = 18
    assert neural._semantic_smoke_receipt(base) != neural._semantic_smoke_receipt(repeat)
    assert len(neural.METHODS) * 2 * 2 == 8


def test_live_thylogale_zero_removal_control_and_outer_authority_inventory():
    control = neural._thylogale_zero_policy(ROOT)
    assert control["roles"] == 112
    packages = neural._goal037_package_index(ROOT)
    assert set(packages) == set(neural.SPECIES)


def test_forged_self_consistent_manifest_is_rejected(tmp_path: Path):
    manifest = {
        "schema_version": "tasmania-sensitivity-neural-inputs-v1", "success": True,
        "fits": 0, "outer_response_labels_read": 0, "role_filter_checks": 896,
        "files": [], "script_sha256": neural.DATA_HELPER_SHA256,
    }
    manifest["digest"] = neural.digest_value(manifest)
    path = tmp_path / neural.MANIFEST_REL
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(neural.NeuralSensitivityError, match="manifest_digest"):
        neural._manifest(tmp_path)
