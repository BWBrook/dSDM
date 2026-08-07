from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dsdm.architecture_runner import (
    RunnerError,
    atomic_write_leaf,
    leaf_identity,
    validate_leaf,
    validate_resume_leaf,
)
from dsdm.real_data import CaseSpec, RealDataBundle


def _bundle(target="thylogale_billardierii", held_fold="fold00"):
    case = CaseSpec("goal033", target, held_fold, "resmlp00", 31031)
    x = np.zeros((4, 77), dtype=np.float32)
    y = np.array([0, 1, 0, 1], dtype=np.float32)
    return RealDataBundle(case, x, y, x.copy(), y.copy(), x.copy(), y.copy(), x.copy(), y.copy(), {
        "source_binding_digest": "a" * 64,
        "goal032_config_digest": "b" * 64,
        "authority_digests": {"goal029_config": "c" * 64, "goal026_feature_contract": "d" * 64, "goal026_fit_parameters": "e" * 64},
    })


def _identity(target="thylogale_billardierii", held_fold="fold00", rows=2):
    return {
        "stage": "screen", "target": target, "held_fold": held_fold,
        "architecture": "resmlp00", "base_seed": 31031, "fit_seed": 123,
        "bundle_digest": "a" * 64, "config_digest": "b" * 64,
        "runtime_digest": "c" * 64, "held_row_count": rows,
    }


def test_identity_addressed_leaf_is_atomic_and_resume_revalidates(tmp_path):
    identity = _identity(rows=2)
    scores = np.array([0.1, 0.9], dtype=np.float32)
    path = atomic_write_leaf(tmp_path, identity, scores)
    assert path == tmp_path / leaf_identity(identity)
    assert validate_leaf(path, identity)
    assert validate_resume_leaf(path, identity)

    path.joinpath("scores.npy").write_bytes(np.array([0.2, 0.9], dtype=np.float32).tobytes())
    with pytest.raises(RunnerError):
        validate_resume_leaf(path, identity)


def test_partial_leaf_is_not_resumable(tmp_path):
    identity = _identity(rows=2)
    leaf = tmp_path / leaf_identity(identity)
    leaf.mkdir()
    (leaf / "scores.npy").write_bytes(b"partial")
    with pytest.raises(RunnerError):
        validate_resume_leaf(leaf, identity)


def test_leaf_identity_rejects_extra_or_missing_authority_fields():
    base = {
        **_identity(rows=4),
    }
    assert len(leaf_identity(base)) == 64
    with pytest.raises(RunnerError):
        leaf_identity({k: v for k, v in base.items() if k != "held_row_count"})
    with pytest.raises(RunnerError):
        leaf_identity({**base, "unexpected": 1})


def test_bundle_export_rejects_duplicate_cross_product_and_malformed_roles(tmp_path):
    with pytest.raises(RunnerError):
        from dsdm.architecture_runner import export_private_bundles
        export_private_bundles([_bundle()] * 40, tmp_path)
    bad = _bundle()
    object.__setattr__(bad, "x_discovery", np.zeros((4, 76), dtype=np.float32))
    with pytest.raises(Exception):
        from dsdm.architecture_runner import export_private_bundles
        export_private_bundles([bad], tmp_path / "bad")


def test_receipt_metadata_tamper_is_rejected(tmp_path):
    identity = {
        **_identity(rows=2),
    }
    path = atomic_write_leaf(tmp_path, identity, np.array([0.1, 0.9], dtype=np.float32), metadata={
        "prediction_digest": __import__("hashlib").sha256(np.array([0.1, 0.9], dtype=np.float32).tobytes()).hexdigest(), "model_digest": "e" * 64,
        "training_bundle_digest": "a" * 64, "fit_seed": 123,
            "selected_epoch": 1, "discovery_executed_epochs": 1, "replay_epochs": 1,
            "stopping_status": "max_epochs_reached", "runtime_fingerprint": "c" * 64,
            "outer_attempted": 0, "outer_opened": 0,
    })
    metadata = json.loads((path / "metadata.json").read_text())
    metadata["receipt"]["fit_seed"] = 999
    (path / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(RunnerError):
        validate_leaf(path, identity)
