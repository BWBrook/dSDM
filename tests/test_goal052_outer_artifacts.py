"""Exercise the real closure/file verifier with a small synthetic fit envelope.

Numerical fitting has its own native-equivalence tests. These fixtures replace
only its receipt validator and the production-sized plan loader, not file,
coverage, seed-average, threshold or closure validation.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from dsdm_phase1 import goal052_outer_artifacts as artifacts


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


@pytest.fixture
def synthetic_run(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    with (run / "domain.npz").open("wb") as stream:
        np.savez_compressed(stream, cell_ids=np.array(["c0", "c1"]))
    plan = {"plan_digest": "synthetic-plan", "targets": ["species"], "tasks": [],
            "domain": {"rows": 2}, "domain_file_sha256": artifacts.sha256_file(run / "domain.npz"),
            "thresholds": {"species": {arm: .42 for arm in artifacts.ARMS}}}
    _json(run / "qualification/canary.json", {"synthetic": "numerical evidence"})
    _json(run / "qualification/profile.json", {"synthetic": "resource evidence"})
    qualification = {"status": "outer_runtime_qualified", "plan_digest": plan["plan_digest"],
                     "files": {name: artifacts.sha256_file(run / name) for name in ("qualification/canary.json", "qualification/profile.json")}}
    _json(run / "qualification/test.json", qualification)
    for arm_index, arm in enumerate(artifacts.ARMS):
        for seed in range(2):
            task = {"kind": "conventional", "target": "species", "block": 0, "arm": arm,
                    "family": "random_forest", "candidate_id": "rf02", "seed_label": f"seed{seed:02d}", "seed": seed,
                    "epochs": None}
            task["id"] = artifacts.task_id(task)
            plan["tasks"].append(task)
            directory = artifacts.leaf_dir(run, task)
            directory.mkdir(parents=True)
            (directory / "model.json").write_text("synthetic fitted payload\n")
            with (directory / "scores.npz").open("wb") as stream:
                np.savez_compressed(stream, scores=np.array([.1 + .05 * arm_index + .1 * seed, .9 - .05 * arm_index - .1 * seed], dtype=np.float64))
            fit_input = {"plan_digest": plan["plan_digest"], "task": task, "data": {}, "dependencies": {}}
            _json(directory / "fit-input.json", fit_input)
            receipt = {"status": "outer_fit_complete", **fit_input, "fit": {}, "outer_response_rows_read": 0,
                       "qualification": "qualification/test.json", "qualification_sha256": artifacts.sha256_file(run / "qualification/test.json"),
                       "files": {name: artifacts.sha256_file(directory / name) for name in ("model.json", "scores.npz", "fit-input.json")}}
            _json(directory / "receipt.json", receipt)
    _json(run / "plan.json", plan)
    monkeypatch.setattr(artifacts, "load_plan", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(artifacts, "validate_fit_receipt", lambda *_args: None)
    return tmp_path, run, plan


def test_closure_covers_models_seed_means_thresholds_and_qualification(synthetic_run):
    root, run, plan = synthetic_run
    closure = artifacts.close_predictions(root, run)
    assert closure["thresholds"] == plan["thresholds"]
    assert closure["fit_counts"] == {"conventional": 12}
    assert "qualification/profile.json" in closure["files"]
    with np.load(run / closure["predictions"]["species"]) as data:
        assert set(data.files) == set(artifacts.ALL_ARMS)
        for index, arm in enumerate(artifacts.ARMS):
            assert data[arm] == pytest.approx([.15 + .05 * index, .85 - .05 * index])
    assert artifacts.verify_closure(root, run) == closure


def test_partial_leaf_and_missing_model_cannot_close(synthetic_run):
    root, run, plan = synthetic_run
    path = artifacts.leaf_dir(run, plan["tasks"][-1]) / "model.json"
    path.unlink()
    with pytest.raises(ValueError, match="artifact_hash_mismatch"):
        artifacts.close_predictions(root, run)
    assert not (run / "closure.json").exists()


def test_changed_seed_scores_break_existing_closure(synthetic_run):
    root, run, plan = synthetic_run
    artifacts.close_predictions(root, run)
    with (artifacts.leaf_dir(run, plan["tasks"][0]) / "scores.npz").open("wb") as stream:
        np.savez_compressed(stream, scores=np.array([.2, .8]))
    with pytest.raises(ValueError, match="artifact_hash_mismatch"):
        artifacts.verify_closure(root, run)


def test_self_consistent_closed_hashes_cannot_hide_wrong_seed_averaging(synthetic_run):
    root, run, _ = synthetic_run
    closure = artifacts.close_predictions(root, run)
    relative = closure["predictions"]["species"]
    with np.load(run / relative) as data:
        arrays = {key: data[key] for key in data.files}
    arrays[artifacts.ARMS[0]] += .01
    with (run / relative).open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    closure["files"][relative] = artifacts.sha256_file(run / relative)
    closure["closure_digest"] = artifacts.digest({k: v for k, v in closure.items() if k != "closure_digest"})
    _json(run / "closure.json", closure)
    with pytest.raises(ValueError, match="closed_seed_average_drift"):
        artifacts.verify_closure(root, run)


def test_qualification_tampering_cannot_close(synthetic_run):
    root, run, _ = synthetic_run
    (run / "qualification/test.json").write_text('{}\n')
    with pytest.raises(ValueError, match="artifact_hash_mismatch"):
        artifacts.close_predictions(root, run)


def test_real_metadata_enumerates_all_recovered_budgets_and_paired_seeds():
    root = Path(__file__).resolve().parents[1]
    if not (root / "data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json").is_file():
        pytest.skip("private retained crossfit metadata is not installed")
    inventory = artifacts.read_json(root / artifacts.INVENTORY)
    recovery = artifacts.read_json(root / artifacts.RECOVERY)
    crossfit = artifacts.read_json(root / "data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json")
    tasks, thresholds = artifacts.enumerate_tasks(inventory, recovery, crossfit, artifacts.baseline._config(root))
    assert len(tasks) == len({task["id"] for task in tasks}) == 4242
    assert len(thresholds) == 157
    ann = [task for task in tasks if task.get("family") == "shallow_ann"]
    assert len(ann) == 400 and all(type(task["epochs"]) is int and 1 <= task["epochs"] <= 300 for task in ann)
    for item in inventory["conventional_target100"]["records"]:
        ordinary = {task["seed_label"]: task["seed"] for task in tasks if task.get("target") == item["target"] and task.get("arm") == artifacts.CONVENTIONAL[0]}
        augmented = {task["seed_label"]: task["seed"] for task in tasks if task.get("target") == item["target"] and task.get("arm") == artifacts.CONVENTIONAL[1]}
        assert ordinary == augmented


def test_neural_receipt_rejects_discovery_or_changed_epoch_budget():
    task = {"kind": "neural", "target": "species", "arm": artifacts.native.ARMS[0], "seed": 11, "epochs": 3}
    data = {"row_digest": "r", "cell_id_digest": "c", "rows": 10, "folds_digest": "f", "q_scaling": None}
    plan = {"target_rows": {"species": data}}
    receipt = {"data": data, "dependencies": {}, "fit": {
        "seed": 11, "replay_shuffle_seed": 100011, "epochs": 3, "completed_epochs": 3, "batch_size": 128,
        "fit_mode": "fixed_budget", "early_stopping": False, "discovery_rows": 0, "stopping_rows": 0,
        "state_finite": True, "head_initialization_seed": 28, "transferred": False, "freeze_trunk": False,
        "save_reload_predictions_exact": True,
    }}
    artifacts.validate_fit_receipt(plan, task, receipt)
    changed = copy.deepcopy(receipt)
    changed["fit"]["completed_epochs"] = 2
    with pytest.raises(ValueError, match="outer_neural_budget_drift"):
        artifacts.validate_fit_receipt(plan, task, changed)
    changed = copy.deepcopy(receipt)
    changed["fit"]["stopping_rows"] = 3
    with pytest.raises(ValueError, match="outer_neural_discovery_forbidden"):
        artifacts.validate_fit_receipt(plan, task, changed)
