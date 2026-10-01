from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import dsdm_phase1.goal051_seawfb_conventional as goal051
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/goal052_ann_epoch_recovery.py"
SPEC = importlib.util.spec_from_file_location("goal052_ann_epoch_recovery", SCRIPT)
recovery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(recovery)


SEEDS = [f"seed0{i}" for i in range(5)]


def _inventory(identity, target="Target bird"):
    record = {
        "target": target,
        "ordinary": {
            "family": "shallow_ann",
            "candidate_id": "ann02",
            "seed_labels": SEEDS,
            "best_epoch_range": [2, 24],
        },
        "q_full": {
            "family": "shallow_ann",
            "candidate_id": "ann02",
            "seed_labels": SEEDS,
            "best_epoch_range": [2, 24],
        },
    }
    return {
        "schema_version": "goal052-outer-inventory-v1",
        "outer_response_rows_read": 0,
        "inputs": {
            "sha256": {"goal051_summary": "unused"},
            "accepted_goal052_identity": {"goal051_identity": identity},
        },
        "conventional_target100": {"records": [record]},
    }


def _prepared_and_evaluated():
    prepared = []
    folds = []
    fit_records = []
    for fold in range(5):
        cells = tuple(f"f{fold}c{i}" for i in range(3))
        y = np.array([0, 1, 0], dtype=np.int8)
        prepared.append({"fold": fold, "validation_rows": SimpleNamespace(cell_ids=cells, y=y)})
        scores_by_seed = {seed: np.array([0.2 + 0.01 * fold, 0.7, 0.1], dtype=np.float64) for seed in SEEDS}
        folds.append({"fold": fold, "cell_ids": cells, "y": y, "score": np.mean(list(scores_by_seed.values()), axis=0), "scores_by_seed": scores_by_seed})
        for seed_index, seed in enumerate(SEEDS):
            fit_records.append({"fold": fold, "seed_label": seed, "best_epoch": fold * 5 + seed_index + 1, "physical_fits": 2, "converged": True})
    return prepared, {"folds": folds, "fit_records": fit_records}


def _binding(frame, method="ordinary"):
    return {
        "prediction_path": Path("accepted.parquet"),
        "result": {"target": "Target bird"},
        "method_spec": {"candidate_id": "ann02", "seed_labels": SEEDS},
    }


def _accepted_frame(method="ordinary"):
    rows = []
    prepared, evaluated = _prepared_and_evaluated()
    for fold in evaluated["folds"]:
        for cell, y, score in zip(fold["cell_ids"], fold["y"], fold["score"]):
            rows.append({
                "target": "Target bird", "target_fraction": 100, "method": "family_selected" if method == "ordinary" else "q_linear",
                "family": "shallow_ann", "candidate_id": "ann02", "auxiliary_size": "none" if method == "ordinary" else "full",
                "fold": fold["fold"], "cell_id": cell, "y": y, "score": score,
            })
    return pd.DataFrame(rows)


def test_wrong_source_identity_fails_closed(tmp_path, monkeypatch):
    accepted = {"source_sha256": "accepted", "config_sha256": "config"}
    inventory = _inventory(accepted)
    summary_path = tmp_path / "evidence/seawfb_conventional/goal051/summary.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(json.dumps({"identity": accepted, "outer_response_rows_read": 0, "outer_predictor_rows_used": 0, "private_outputs": []}))
    inventory["inputs"]["sha256"]["goal051_summary"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    monkeypatch.setattr(goal051, "_config", lambda root: {})
    monkeypatch.setattr(goal051, "_identity", lambda root: {"source_sha256": "changed", "config_sha256": "config"})
    with pytest.raises(recovery.RecoveryError, match="current_identity_mismatch"):
        recovery._accepted_binding(tmp_path, inventory, "Target bird", "ordinary")


def test_wrong_input_identity_fails_closed(tmp_path, monkeypatch):
    accepted = {"source_sha256": "accepted", "config_sha256": "config"}
    inventory = _inventory({"source_sha256": "other", "config_sha256": "config"})
    summary_path = tmp_path / "evidence/seawfb_conventional/goal051/summary.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(json.dumps({"identity": accepted, "outer_response_rows_read": 0, "outer_predictor_rows_used": 0, "private_outputs": []}))
    inventory["inputs"]["sha256"]["goal051_summary"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    with pytest.raises(recovery.RecoveryError, match="accepted_identity_inventory_mismatch"):
        recovery._accepted_binding(tmp_path, inventory, "Target bird", "ordinary")


def test_wrong_cell_coverage_fails_closed(monkeypatch):
    prepared, evaluated = _prepared_and_evaluated()
    frame = _accepted_frame()
    frame.loc[0, "cell_id"] = "wrong-cell"
    monkeypatch.setattr(recovery, "_accepted_prediction_frame", lambda binding, method: frame)
    with pytest.raises(recovery.RecoveryError, match="accepted_cell_coverage:0"):
        recovery._compare_predictions(_binding(frame), "ordinary", prepared, evaluated)


def test_prediction_mismatch_fails_closed(monkeypatch):
    prepared, evaluated = _prepared_and_evaluated()
    frame = _accepted_frame()
    frame.loc[0, "score"] = 0.999
    monkeypatch.setattr(recovery, "_accepted_prediction_frame", lambda binding, method: frame)
    with pytest.raises(recovery.RecoveryError, match="prediction_mismatch:0"):
        recovery._compare_predictions(_binding(frame), "ordinary", prepared, evaluated)


def test_exact_25_epoch_median_and_seed_receipts(monkeypatch):
    prepared, evaluated = _prepared_and_evaluated()
    frame = _accepted_frame()
    monkeypatch.setattr(recovery, "_accepted_prediction_frame", lambda binding, method: frame)
    result, predictions = recovery._compare_predictions(_binding(frame), "ordinary", prepared, evaluated)
    assert len(result["fit_receipts"]) == 25
    assert result["median_rounded_epoch"] == 13
    assert set(predictions) == set(SEEDS)
    assert all(len(values) == 15 for values in predictions.values())
    assert recovery.rounded_median_epochs(range(1, 26)) == 13
    with pytest.raises(recovery.RecoveryError, match="epoch_count:24"):
        recovery.rounded_median_epochs(range(1, 25))


def test_procedure_lock_excludes_overlap_and_allows_later_resume(tmp_path):
    lock = tmp_path / "procedure.lock"
    with recovery._procedure_lock(lock):
        with pytest.raises(recovery.RecoveryError, match="procedure_locked"):
            with recovery._procedure_lock(lock):
                pytest.fail("overlapping procedure acquired the lock")
    with recovery._procedure_lock(lock):
        assert lock.is_file()


def test_corrupted_successful_payload_is_rejected(tmp_path):
    base = recovery._checkpoint_base(tmp_path, "Target bird", "ordinary")
    payload = base.with_suffix(".predictions.npz")
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"payload")
    identity = {"config_sha256": "config", "source_sha256": "source"}
    checkpoint = {
        "status": "success", "target": "Target bird", "target_fraction": 100, "method": "ordinary", "family": "shallow_ann",
        "candidate_id": "ann02", "seed_labels": SEEDS, "identity": identity,
        "recovery_script_sha256": recovery._script_hash(),
        "accepted_prediction_sha256": "accepted",
        "recovered_predictions_npz": str(payload.relative_to(tmp_path)),
        "recovered_predictions_sha256": recovery.sha256_file(payload),
    }
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_text(json.dumps(checkpoint))
    payload.write_bytes(b"corrupted")
    binding = {"prediction_sha256": "accepted", "identity": identity, "result": {"target": "Target bird"}, "method_spec": {"candidate_id": "ann02", "seed_labels": SEEDS}}
    with pytest.raises(recovery.RecoveryError, match="successful_checkpoint_payload_mismatch"):
        recovery._successful_checkpoint(tmp_path, base, binding, "ordinary")


def test_failed_replay_preserves_payload_and_diagnostics(tmp_path, monkeypatch):
    identity = {"config_sha256": "config", "source_sha256": "source"}
    binding = {
        "identity": identity, "prediction_sha256": "accepted", "config": {},
        "result": {"target": "Target bird"}, "method_spec": {"candidate_id": "ann02", "seed_labels": SEEDS},
    }
    monkeypatch.setattr(recovery, "_accepted_binding", lambda *args, **kwargs: binding)
    _, evaluated = _prepared_and_evaluated()
    monkeypatch.setattr(goal051, "_fit_seed", lambda *args: 100 + int(args[-1][-1]))
    def fail_compare(*args, **kwargs):
        raise recovery.PredictionMismatch("prediction_mismatch:0", {"fold": 0, "max_abs_score_delta": 0.25, "mismatch_count": 1})
    monkeypatch.setattr(recovery, "_compare_predictions", fail_compare)
    with pytest.raises(recovery.PredictionMismatch):
        recovery.recover_one(tmp_path, "Target bird", "ordinary", inventory={"conventional_target100": {"records": []}}, store=object(), prepared_folds=lambda *args: [], evaluator=lambda *args: evaluated)
    checkpoints = list((tmp_path / recovery.RECOVERY_DIR.relative_to(recovery.ROOT)).glob("*.json"))
    assert len(checkpoints) == 1
    failure = json.loads(checkpoints[0].read_text())
    assert failure["status"] == "failed"
    assert failure["diagnostics"]["max_abs_score_delta"] == 0.25
    assert len(failure["evaluated_fit_records"]) == 25
    payload = tmp_path / failure["evaluated_predictions_npz"]
    assert payload.is_file()
    assert recovery.sha256_file(payload) == failure["evaluated_predictions_sha256"]
