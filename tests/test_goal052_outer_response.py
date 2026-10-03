from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dsdm_phase1 import goal052_outer_response as response


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _panel() -> tuple[list[str], dict]:
    primary = [f"target_{index:03d}" for index in range(73)]
    regional = {
        "NCP": primary + [f"target_{index:03d}" for index in range(73, 88)],
        "SEH": primary + [f"target_{index:03d}" for index in range(73, 122)],
        "NNC": primary + [f"target_{index:03d}" for index in range(73, 99)] + [f"target_{index:03d}" for index in range(122, 157)],
    }
    targets = sorted(set(primary).union(*regional.values()))
    summary = {
        "schema_version": "goal049-panel-summary-v1",
        "status": "frozen",
        "regions": ["NCP", "SEH", "NNC"],
        "primary_common": {"count": len(primary), "species": primary},
        "secondary_region_specific": {
            region: {"count": len(names), "species": names} for region, names in regional.items()
        },
        "bindings": {},
        "privacy": {
            "coordinates_written": False,
            "private_lists_written": False,
            "raw_occurrence_rows": 0,
            "model_outcomes": 0,
        },
        "two_of_three_panel": False,
        "x20_changes_membership": False,
    }
    return targets, summary


def _fixture(tmp_path: Path, *, duplicate: bool = False) -> tuple[Path, Path, dict]:
    root = tmp_path
    run = root / "run"
    run.mkdir(parents=True)
    targets, panel = _panel()
    config = {
        "schema_version": "1.0",
        "goal_id": "049",
        "tracked_outputs": {
            "completion": "evidence/completion.json",
            "panel_summary": "evidence/panel.json",
        },
        "private_outputs": {
            "root": "data",
            "canonical_memberships": "canonical_species_cells.parquet",
            "panel_ledger": "panel_ledger.parquet",
        },
    }
    config_path = root / "config/goal049_seawfb_canonical_response.json"
    _write_json(config_path, config)
    panel_path = root / "evidence/panel.json"
    _write_json(panel_path, panel)
    rows = [
        (targets[0], "cell-0"),
        (targets[0], "cell-1"),
        (targets[0], "cell-retained"),
        (targets[1], "cell-1"),
        (targets[1], "cell-2"),
        (targets[1], "cell-buffer"),
    ]
    if duplicate:
        rows.append(rows[-1])
    canonical_path = root / config["private_outputs"]["root"] / config["private_outputs"]["canonical_memberships"]
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"species": [row[0] for row in rows], "cell_id": [row[1] for row in rows]}), canonical_path)
    canonical_hash = _sha(canonical_path)
    panel["bindings"] = {
        "canonical_species_cells_sha256": canonical_hash,
        "panel_ledger_sha256": "synthetic-panel-ledger",
        "completion_config_sha256": _sha(config_path),
    }
    _write_json(panel_path, panel)
    completion = {
        "schema_version": "goal049-canonical-response-completion-v1",
        "status": "complete",
        "regions": ["NCP", "SEH", "NNC"],
        "privacy": {
            "coordinates_written": False,
            "private_species_cell_lists_written": False,
            "raw_occurrence_rows": 0,
            "model_outcomes": 0,
        },
        "scientific_invariants": {
            "focal_excluded_from_donor_richness": True,
            "focal_absent_richness_identity_verified": True,
            "richness_used_as_predictor": False,
        },
        "counts": {"active_species": 2, "effort_donors": 2, "canonical_memberships": len(rows), "common_primary_targets": 73},
        "bindings": {
            "config_sha256": _sha(config_path),
            "panel_summary_sha256": _sha(panel_path),
            "canonical_species_cells_sha256": canonical_hash,
            "panel_ledger_sha256": "synthetic-panel-ledger",
        },
        "private_outputs": {
            "canonical_species_cells": str(Path(config["private_outputs"]["root"]) / config["private_outputs"]["canonical_memberships"]),
            "panel_ledger": str(Path(config["private_outputs"]["root"]) / config["private_outputs"]["panel_ledger"]),
        },
    }
    completion_path = root / config["tracked_outputs"]["completion"]
    _write_json(completion_path, completion)
    panel["bindings"]["completion_config_sha256"] = _sha(config_path)
    _write_json(panel_path, panel)
    cell_ids = np.asarray(["cell-0", "cell-1", "cell-2", "cell-3"], dtype="U")
    np.savez_compressed(run / "domain.npz", cell_ids=cell_ids)
    closure = {
        "closure_digest": "synthetic-closure",
        "plan_digest": "synthetic-plan",
        "files": {"domain.npz": _sha(run / "domain.npz")},
        "domain": {"rows": len(cell_ids)},
    }
    _write_json(run / "closure.json", closure)
    return root, run, closure


def test_gate_is_first_and_raw_reader_is_not_called_on_failed_closure(tmp_path, monkeypatch):
    root, run, _ = _fixture(tmp_path)
    calls: list[str] = []

    def fail_gate(*_args, **_kwargs):
        calls.append("gate")
        raise ValueError("closure incomplete")

    monkeypatch.setattr(response, "verify_closure", fail_gate)
    monkeypatch.setattr(response, "_read_canonical_rows", lambda *_args, **_kwargs: calls.append("raw"))
    with pytest.raises(ValueError, match="closure incomplete"):
        response.load_closed_outer_responses(root, run)
    assert calls == ["gate"]
    assert not (run / "response-access.json").exists()


def test_loader_aligns_domain_and_subtracts_focal_only_on_donor_presence(tmp_path, monkeypatch):
    root, run, closure = _fixture(tmp_path)
    monkeypatch.setattr(response, "verify_closure", lambda *_args, **_kwargs: closure)
    loaded = response.load_closed_outer_responses(root, run)
    assert len(loaded["by_target"]) == 157
    np.testing.assert_array_equal(loaded["by_target"]["target_000"]["y"], [1, 1, 0, 0])
    np.testing.assert_array_equal(loaded["by_target"]["target_000"]["richness_minus_f"], [0, 1, 1, 0])
    np.testing.assert_array_equal(loaded["by_target"]["target_001"]["y"], [0, 1, 1, 0])
    np.testing.assert_array_equal(loaded["by_target"]["target_001"]["richness_minus_f"], [1, 1, 0, 0])
    assert loaded["response_provenance"]["domain_rows"] == 4
    assert loaded["response_provenance"]["canonical_membership_rows"] == 6
    assert loaded["response_provenance"]["target_count"] == 157
    assert json.loads((run / "response-access.json").read_text())["status"] == "response_access_started"
    assert json.loads((run / "response-access-success.json").read_text())["status"] == "response_access_complete"


def test_duplicate_canonical_cells_fail_after_start_log_without_success(tmp_path, monkeypatch):
    root, run, closure = _fixture(tmp_path, duplicate=True)
    monkeypatch.setattr(response, "verify_closure", lambda *_args, **_kwargs: closure)
    with pytest.raises(ValueError, match="canonical_duplicate_or_order_drift"):
        response.load_closed_outer_responses(root, run)
    assert (run / "response-access.json").is_file()
    assert not (run / "response-access-success.json").exists()


def test_retained_or_buffer_memberships_outside_outer_domain_are_skipped_from_outer_arrays(tmp_path, monkeypatch):
    # These are valid Goal048 retained/buffer cells.  The full canonical-file
    # hash binds their membership before the outer-domain projection runs.
    root, run, closure = _fixture(tmp_path)
    monkeypatch.setattr(response, "verify_closure", lambda *_args, **_kwargs: closure)
    loaded = response.load_closed_outer_responses(root, run)
    assert loaded["response_provenance"]["canonical_membership_rows"] == 6
    np.testing.assert_array_equal(loaded["by_target"]["target_000"]["y"], [1, 1, 0, 0])
    np.testing.assert_array_equal(loaded["by_target"]["target_001"]["y"], [0, 1, 1, 0])


def test_non_donor_target_presence_is_not_subtracted_from_effort_richness(tmp_path, monkeypatch):
    root, run, closure = _fixture(tmp_path)
    completion_path = root / "evidence/completion.json"
    completion = json.loads(completion_path.read_text())
    completion["counts"]["effort_donors"] = 1
    completion["effort_species"] = ["target_000"]
    _write_json(completion_path, completion)
    monkeypatch.setattr(response, "verify_closure", lambda *_args, **_kwargs: closure)
    loaded = response.load_closed_outer_responses(root, run)
    np.testing.assert_array_equal(loaded["by_target"]["target_001"]["richness_minus_f"], [1, 1, 0, 0])
