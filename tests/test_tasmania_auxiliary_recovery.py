from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path
import sys

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tasmania_auxiliary_recovery", ROOT / "scripts/tasmania_auxiliary_recovery.py"
)
assert SPEC and SPEC.loader
recovery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recovery
SPEC.loader.exec_module(recovery)


def _digest(char: str = "a") -> str:
    return char * 64


def _record(seed: int = 31031) -> dict[str, object]:
    return {
        "artifact_id": f"aux/multihead/seed{seed}",
        "kind": "auxiliary",
        "fit_seed": seed,
        "logical_artifacts": 1,
        "physical_fits": 2,
        "finite": True,
        "selected_epoch": 4,
        "replay_epochs": 4,
        "initial_model_digest": _digest("a"),
        "replay_initial_model_digest": _digest("a"),
        "initial_shared_digest": _digest("b"),
        "final_shared_digest": _digest("c"),
        "model_digest": _digest("d"),
        "prediction_digest": _digest("e"),
        "runtime_digest": _digest("f"),
    }


def test_model_hash_mismatch_is_rejected():
    expected = {key: value for key, value in _record().items() if key in recovery.SEMANTIC_DIGEST_KEYS}
    actual = dict(expected)
    actual["model_digest"] = _digest("0")

    with pytest.raises(recovery.RecoveryError, match="model_digest mismatch"):
        recovery._check_replay_digests(expected, actual, "synthetic/fold00/31031")


def test_auxiliary_record_input_hash_shape_is_rejected():
    record = _record()
    record["prediction_digest"] = "tampered"

    with pytest.raises(recovery.RecoveryError, match="auxiliary digest missing"):
        recovery._auxiliary_record(
            {"artifacts": [record]}, "synthetic_target", "fold00", 31031
        )


def test_input_mask_tamper_is_rejected(monkeypatch: pytest.MonkeyPatch):
    class FakeMask:
        digest = _digest("a")

    class FakeData:
        @staticmethod
        def prepare_case(_bundle):
            return {
                "auxiliary_mask": FakeMask(),
                "auxiliary": {
                    role: np.zeros((2, 3), dtype=np.float32)
                    for role in ("discovery", "stopping", "replay")
                },
            }

        validate_case_payload = object()

    class FakeBundle:
        target = "thylogale_billardierii"
        held_fold = "fold00"
        source_digest = _digest("b")
        arrays = {
            f"aux_x_{role}": np.zeros((2, 3), dtype=np.float32)
            for role in ("discovery", "stopping", "replay")
        } | {
            f"aux_species_{role}": np.array([0, 1], dtype=np.int32)
            for role in ("discovery", "stopping", "replay")
        }

    metadata = {"auxiliary_mask_digest": _digest("0")}
    with pytest.raises(recovery.RecoveryError, match="auxiliary mask digest mismatch"):
        recovery._validate_input_binding(FakeData, FakeBundle, metadata)


def test_missing_state_count_is_rejected():
    records = [
        {"target": target, "held_fold": fold, "seed": seed}
        for target in recovery.SPECIES
        for fold in recovery.FOLDS
        for seed in recovery.SEEDS
    ][:-1]

    with pytest.raises(recovery.RecoveryError, match="expected 200 auxiliary records"):
        recovery._validate_state_inventory(records)


def test_run_requires_explicit_execution_gate(tmp_path: Path):
    with pytest.raises(recovery.RecoveryError, match="fit-gated"):
        recovery.run_recovery(
            stage_root=tmp_path / "stage",
            private_root=tmp_path / "private",
            execute=False,
        )


def test_serialized_state_digest_is_recomputed_from_tensors(tmp_path: Path):
    forged = tmp_path / "forged.pt"
    torch.save(
        {"state_dict": {"not_a_model_weight": torch.zeros(1)}, "semantic_model_digest": _digest("a")},
        forged,
    )

    with pytest.raises(recovery.RecoveryError, match="serialized semantic digest mismatch"):
        recovery._validate_serialized_state(forged, _digest("a"), "synthetic/fold00/31031")


def test_serialized_state_with_matching_tensor_digest_is_accepted(tmp_path: Path):
    state = {"weight": torch.tensor([[1.0, -2.0]], dtype=torch.float32)}
    digest = hashlib.sha256(b"weight" + state["weight"].contiguous().numpy().tobytes()).hexdigest()
    valid = tmp_path / "valid.pt"
    torch.save({"state_dict": state, "semantic_model_digest": digest}, valid)

    recovery._validate_serialized_state(valid, digest, "synthetic/fold00/31031")
