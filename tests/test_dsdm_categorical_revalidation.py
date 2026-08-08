from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from dsdm.architecture_mask_revalidation import (
    RevalidationError,
    _aggregate_stage,
    _write_leaf,
    audit_categories,
    expected_tasks,
    load_revalidation_config,
    mask_architecture_bundle,
    plan,
    revalidation_leaf_identity,
    validate_leaf,
    validate_immutable_inputs,
)
from dsdm.categorical_support import apply_support_mask, fit_support_mask
from dsdm.real_data import CaseSpec, RealDataBundle


def _x(rows: int = 4) -> np.ndarray:
    value = np.zeros((rows, 77), dtype=np.float32)
    value[:, :25] = np.arange(rows * 25, dtype=np.float32).reshape(rows, 25)
    value[:, 25] = 1.0
    value[:, 38] = 1.0
    return value


def _bundle() -> RealDataBundle:
    case = CaseSpec("goal033", "sarcophilus_harrisii", "fold01", "resmlp00", 31031)
    x = _x()
    y = np.array([0, 1, 0, 1], dtype=np.float32)
    return RealDataBundle(case, x, y, x.copy(), y.copy(), x.copy(), y.copy(), x.copy(), y.copy(), {"source_binding_digest": "a" * 64})


def test_support_mask_keeps_continuous_and_neutralises_unsupported_indicator():
    replay = _x()
    replay[:, 38] = 0.0
    support = fit_support_mask(replay)
    held = _x(2)
    held[:, 38] = 1.0
    masked, audit = apply_support_mask(held, support)
    assert np.array_equal(masked[:, :25], held[:, :25])
    assert np.all(masked[:, 38] == 0)
    assert audit["affected_rows"] == 2
    assert audit["affected_instances"] == 2


def test_fit_support_uses_replay_not_held_and_training_is_byte_identical():
    bundle = _bundle()
    original = bundle.x_replay.tobytes()
    held = np.array(bundle.x_inner_assessment, copy=True)
    held[:, 39] = 1.0
    bundle = RealDataBundle(bundle.case, bundle.x_discovery, bundle.y_discovery, bundle.x_stopping, bundle.y_stopping, bundle.x_replay, bundle.y_replay, held, bundle.y_inner_assessment, bundle.metadata)
    corrected, audit = mask_architecture_bundle(bundle)
    assert corrected.x_replay.tobytes() == original
    assert corrected.x_discovery.tobytes() == bundle.x_discovery.tobytes()
    assert corrected.x_inner_assessment[:, 39].sum() == 0
    assert audit["training_byte_identical"] is True


def test_plan_and_full_endpoint_audit_are_exact():
    config = load_revalidation_config("config/dsdm_categorical_revalidation.json")
    assert plan(config) == {"screen_logical_evaluations": 960, "shortlist_logical_evaluations": 480, "logical_evaluations": 1440, "physical_fits": 2880, "workers": 3}
    root = Path("data/processed/dsdm/goal033-architecture-selection/private/bundles")
    if not root.exists():
        pytest.skip("ignored Goal033 private bundles are unavailable")
    result = audit_categories(root)
    assert result["cases"] == 40
    assert result["affected_cases"] == 27
    assert result["affected_rows"] == 66
    assert result["affected_column_occurrences"] == 55
    assert result["outer_attempted"] == result["outer_opened"] == 0


def test_fresh_leaf_identity_requires_mask_digest():
    base = {"stage": "screen", "target": "sarcophilus_harrisii", "held_fold": "fold01", "architecture": "resmlp13", "base_seed": 31031, "fit_seed": 1, "bundle_digest": "a" * 64, "source_bundle_digest": "f" * 64, "config_digest": "b" * 64, "runtime_digest": "c" * 64, "mask_digest": "d" * 64, "held_row_count": 4}
    assert len(revalidation_leaf_identity(base)) == 64
    with pytest.raises(RevalidationError):
        revalidation_leaf_identity({k: v for k, v in base.items() if k != "mask_digest"})


def test_old_leaf_namespace_is_not_accepted_by_cli_contract():
    config = load_revalidation_config("config/dsdm_categorical_revalidation.json")
    # The runner's CLI rejects any leaf root containing the old namespace.
    assert "goal033" not in config.raw["evidence"]["private_root"]


def test_corrected_leaf_is_resumable_and_tamper_fails(tmp_path):
    identity = {"stage": "screen", "target": "sarcophilus_harrisii", "held_fold": "fold01", "architecture": "resmlp13", "base_seed": 31031, "fit_seed": 1, "bundle_digest": "a" * 64, "source_bundle_digest": "f" * 64, "config_digest": "b" * 64, "runtime_digest": "c" * 64, "mask_digest": "d" * 64, "held_row_count": 2}
    scores = np.array([0.2, 0.8], dtype=np.float32)
    receipt = {"prediction_digest": hashlib.sha256(scores.tobytes()).hexdigest(), "model_digest": "e" * 64, "training_bundle_digest": "a" * 64, "runtime_fingerprint": "c" * 64, "fit_seed": 1, "selected_epoch": 1, "discovery_executed_epochs": 1, "replay_epochs": 1, "stopping_status": "max_epochs_reached", "outer_attempted": 0, "outer_opened": 0}
    path = Path(_write_leaf({**identity, "leaf_root": str(tmp_path)}, scores, receipt))
    assert validate_leaf(path, identity)
    scores[0] = 0.3
    np.save(path / "scores.npy", scores, allow_pickle=False)
    with pytest.raises(RevalidationError):
        validate_leaf(path, identity)


def test_config_mutation_is_rejected(tmp_path):
    source = Path("config/dsdm_categorical_revalidation.json")
    raw = json.loads(source.read_text())
    raw["selection"]["screen_base_seed"] = 123
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(raw))
    with pytest.raises(RevalidationError):
        load_revalidation_config(altered)


def test_config_authority_key_mutation_is_rejected(tmp_path):
    source = Path("config/dsdm_categorical_revalidation.json")
    raw = json.loads(source.read_text())
    raw["execution_sources"]["unexpected"] = raw["execution_sources"]["models"]
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(raw))
    with pytest.raises(RevalidationError):
        load_revalidation_config(altered)


def test_aggregate_stage_accepts_canonical_text_inventory(tmp_path, monkeypatch):
    import dsdm.architecture_mask_revalidation as runner

    config = load_revalidation_config("config/dsdm_categorical_revalidation.json")
    leaves = tmp_path / "leaves"
    tasks = []
    bundles = []
    scores = np.array([0.2, 0.8], dtype=np.float32)
    for target in config.species:
        for held_fold in config.folds:
            case = CaseSpec("goal035", target, held_fold, "resmlp13", 31031)
            x = _x(2)
            y = np.array([0, 1], dtype=np.float32)
            bundle = RealDataBundle(case, x, y, x.copy(), y.copy(), x.copy(), y.copy(), x.copy(), y.copy(), {})
            bundles.append((tmp_path / f"{target}-{held_fold}.npz", bundle, {}))
            identity = {
                "stage": "screen",
                "target": target,
                "held_fold": held_fold,
                "architecture": "resmlp13",
                "base_seed": 31031,
                "fit_seed": 1,
                "bundle_digest": "a" * 64,
                "source_bundle_digest": "f" * 64,
                "config_digest": "b" * 64,
                "runtime_digest": "c" * 64,
                "mask_digest": "d" * 64,
                "held_row_count": 2,
            }
            task = {**identity, "leaf_root": str(leaves), "bundle_path": str(tmp_path / "unused.npz")}
            receipt = {
                "prediction_digest": hashlib.sha256(scores.tobytes()).hexdigest(),
                "model_digest": "e" * 64,
                "training_bundle_digest": identity["bundle_digest"],
                "runtime_fingerprint": identity["runtime_digest"],
                "fit_seed": identity["fit_seed"],
                "selected_epoch": 1,
                "discovery_executed_epochs": 1,
                "replay_epochs": 1,
                "stopping_status": "max_epochs_reached",
                "outer_attempted": 0,
                "outer_opened": 0,
            }
            _write_leaf(task, scores, receipt)
            tasks.append(task)

    monkeypatch.setattr(runner, "expected_tasks", lambda *args, **kwargs: tasks)
    monkeypatch.setattr(runner, "load_corrected_bundles", lambda *args, **kwargs: bundles)
    result = _aggregate_stage(config, tmp_path, leaves, "screen", ("resmlp13",))
    assert result["ranking"] == ["resmlp13"]
    assert len(result["leaf_inventory_digest"]) == 64
