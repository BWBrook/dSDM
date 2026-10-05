from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsdm_phase1 import goal052_outer_artifacts
from dsdm_phase1 import goal052_outer as native_outer
from dsdm_phase1 import goal052_outer_response as native_response
from scripts import goal052_outer_score_recovery as recovery


def _parquet(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"species": [s for s, _ in rows], "cell_id": [c for _, c in rows]}), path)


def test_zero_row_species_is_excluded_without_changing_native_arrays(tmp_path: Path) -> None:
    path = tmp_path / "canonical.parquet"
    _parquet(path, [("a", "c0"), ("a", "c1"), ("b", "c1")])
    present, richness, rows, species, donors = native_response._read_canonical_rows(
        path, {"c0": 0, "c1": 1}, ["a"], None, 2, 2
    )
    assert rows == 3
    assert species == donors == ["a", "b"]
    np.testing.assert_array_equal(present["a"], np.array([True, True]))
    np.testing.assert_array_equal(richness, np.array([1, 2], dtype=np.int32))
    # Independent reconstruction of y and focal-excluded richness.
    np.testing.assert_array_equal(present["a"].astype(np.int8), [1, 1])
    np.testing.assert_array_equal(richness - present["a"].astype(np.int32), [0, 1])


@pytest.mark.parametrize(
    "active_count, donor_count, expected",
    [(3, 2, "active_species_count_drift"), (2, 3, "effort_donor_species_count_drift")],
)
def test_serialized_inventory_counts_are_required(tmp_path: Path, active_count: int, donor_count: int, expected: str) -> None:
    path = tmp_path / "canonical.parquet"
    _parquet(path, [("a", "c0"), ("b", "c1")])
    with pytest.raises(ValueError, match=expected):
        native_response._read_canonical_rows(path, {"c0": 0, "c1": 1}, [], None, active_count, donor_count)


def test_unknown_serialized_species_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "canonical.parquet"
    _parquet(path, [("a", "c0"), ("z", "c1")])
    with pytest.raises(ValueError, match="active_species_count_drift"):
        native_response._read_canonical_rows(path, {"c0": 0, "c1": 1}, [], None, 1, 1)


def test_prior_access_identity_and_hash_are_immutable(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    closure_path = run / "closure.json"
    closure = {"closure_digest": "closure", "plan_digest": "plan", "domain": {"rows": 0}}
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    access = {
        "schema_version": "goal052-outer-response-access-v1",
        "status": "response_access_started",
        "immutable": True,
        "closure_file_sha256": hashlib.sha256(closure_path.read_bytes()).hexdigest(),
        "closure_digest": "closure",
        "plan_digest": "plan",
        "canonical_species_cells_sha256": "canonical",
        "target_inventory_sha256": "targets",
        "domain_rows": 0,
        "response_rows_read": None,
        "success_receipt": "response-access-success.json",
    }
    access_path = run / "response-access.json"
    access_path.write_text(json.dumps(access), encoding="utf-8")
    expected = hashlib.sha256(access_path.read_bytes()).hexdigest()
    assert recovery.validate_prior_access(run, closure, expected, "canonical", "targets") == access_path
    access["plan_digest"] = "drift"
    access_path.write_text(json.dumps(access), encoding="utf-8")
    with pytest.raises(recovery.RecoveryError, match="prior response-access hash mismatch"):
        recovery.validate_prior_access(run, closure, expected, "canonical", "targets")


def test_cli_requires_inventory_certificate() -> None:
    args = recovery.parse_args(
        [
            "--root", ".", "--run", "run", "--control", "control",
            "--inventory-proof", "proof.json", "--inventory-proof-sha256", "p" * 64,
            "--inventory-certificate", "certificate.json", "--inventory-certificate-sha256", "c" * 64,
            "--prior-access-sha", "a" * 64, "--expected-plan-sha256", "p" * 64,
            "--expected-closure-sha256", "c" * 64,
        ]
    )
    assert args.inventory_certificate.name == "certificate.json"


class _RecoveryResponseStub:
    def __init__(self, root: Path, *, species_seen: list[str], row_count: int,
                 targets: list[str]) -> None:
        self.canonical = root / "canonical.parquet"
        self.canonical.write_bytes(b"certified-canonical-fixture")
        self.completion = root / "completion.json"
        self.completion.write_text("{}", encoding="utf-8")
        self.panel = root / "panel.json"
        self.panel.write_text("{}", encoding="utf-8")
        self.species_seen = species_seen
        self.row_count = row_count
        self.targets = targets

    def _metadata_before_response_read(self, root: Path, closure: dict):
        digest = hashlib.sha256(self.canonical.read_bytes()).hexdigest()
        return ({}, {}, self.completion, self.panel, self.canonical, digest, "targets", self.targets, None)

    def _read_domain(self, run: Path, closure: dict):
        return np.asarray(["c0", "c1", "c2"]), "domain-digest"

    def _read_canonical_rows(self, *args):
        return (
            {"target": np.asarray([True, False, True]), "a": np.asarray([False, True, False])},
            np.asarray([2, 1, 2], dtype=np.int32), self.row_count,
            self.species_seen, self.species_seen,
        )

    _array_digest = staticmethod(native_response._array_digest)


def _reconstruction_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                            *, species_seen: list[str] | None = None,
                            row_count: int = 3, targets: list[str] | None = None):
    monkeypatch.setattr(recovery, "CANONICAL_ROWS", 3)
    monkeypatch.setattr(recovery, "OBSERVED_SPECIES", 2)
    run = tmp_path / "run"
    run.mkdir()
    closure = {"closure_digest": "closure", "plan_digest": "plan"}
    (run / "closure.json").write_text(json.dumps(closure), encoding="utf-8")
    stub = _RecoveryResponseStub(tmp_path, species_seen=species_seen or ["a", "b"],
                                 row_count=row_count, targets=targets or ["a"])
    metadata = {
        "canonical_sha256": hashlib.sha256(stub.canonical.read_bytes()).hexdigest(),
        "empty": ["empty"], "nonempty": ["a", "b"],
    }
    return run, closure, stub, metadata


def test_reconstruct_response_matches_independent_y_and_focal_richness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, closure, stub, metadata = _reconstruction_fixture(tmp_path, monkeypatch)
    result = recovery.reconstruct_response(tmp_path, run, closure, object(), stub, metadata)
    np.testing.assert_array_equal(result["by_target"]["a"]["y"], [0, 1, 0])
    np.testing.assert_array_equal(result["by_target"]["a"]["richness_minus_f"], [2, 0, 2])
    assert result["response_provenance"]["registered_active_species_count"] == 505


@pytest.mark.parametrize("species_seen", [["a", "wrong"], ["a", "empty"]])
def test_reconstruct_response_rejects_same_count_wrong_observed_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, species_seen: list[str]
) -> None:
    run, closure, stub, metadata = _reconstruction_fixture(tmp_path, monkeypatch, species_seen=species_seen)
    with pytest.raises(recovery.RecoveryError, match="observed species identity mismatch"):
        recovery.reconstruct_response(tmp_path, run, closure, object(), stub, metadata)


@pytest.mark.parametrize("targets, expected", [
    (["empty"], "frozen target is an empty species"),
    (["target", "empty"], "frozen target is an empty species"),
])
def test_reconstruct_response_rejects_empty_scoring_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                           targets: list[str], expected: str) -> None:
    run, closure, stub, metadata = _reconstruction_fixture(tmp_path, monkeypatch, targets=targets)
    with pytest.raises(recovery.RecoveryError, match=expected):
        recovery.reconstruct_response(tmp_path, run, closure, object(), stub, metadata)


def test_reconstruct_response_rejects_wrong_expected_row_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, closure, stub, metadata = _reconstruction_fixture(tmp_path, monkeypatch, row_count=2)
    with pytest.raises(recovery.RecoveryError, match="canonical row count mismatch"):
        recovery.reconstruct_response(tmp_path, run, closure, object(), stub, metadata)


@pytest.mark.parametrize("artifact", [recovery.RESPONSE_SUCCESS, recovery.FIT_FAILURE, recovery.SCORES])
def test_prior_access_rejects_existing_recovery_outputs(tmp_path: Path, artifact: str) -> None:
    run = tmp_path / "run"
    run.mkdir()
    closure = {"closure_digest": "closure", "plan_digest": "plan", "domain": {"rows": 0}}
    closure_path = run / "closure.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    (run / artifact).write_text("{}", encoding="utf-8")
    with pytest.raises(recovery.RecoveryError, match="already exists"):
        recovery.validate_prior_access(run, closure, "unused", "canonical", "targets")


def test_recover_reaches_artifact_verifier_before_response_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[1]
    calls: list[tuple[Path, Path]] = []

    def sentinel_verify_closure(actual_root: Path, actual_run: Path) -> dict:
        calls.append((actual_root, actual_run))
        raise recovery.RecoveryError("verifier sentinel")

    monkeypatch.setattr(goal052_outer_artifacts, "verify_closure", sentinel_verify_closure)
    args = type("Args", (), {
        "root": root,
        "run": tmp_path / "run",
        "control": tmp_path / "control",
    })()
    with pytest.raises(recovery.RecoveryError, match="verifier sentinel"):
        recovery.recover(args)
    assert calls == [(root, (tmp_path / "run").resolve())]


def test_score_response_reaches_native_plan_loader_before_prediction_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Path, Path]] = []

    def sentinel_load_plan(actual_root: Path, actual_run: Path) -> dict:
        calls.append((actual_root, actual_run))
        raise recovery.RecoveryError("native plan sentinel")

    monkeypatch.setattr(native_outer, "load_plan", sentinel_load_plan)
    run = tmp_path / "run"
    with pytest.raises(recovery.RecoveryError, match="native plan sentinel"):
        recovery.score_response(tmp_path, run, {}, native_outer, {})
    assert calls == [(tmp_path, run)]
