"""Synthetic checks for response-free Tasmania prediction collection."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "tasmania_pseudoabsence_collect", SCRIPTS / "tasmania_pseudoabsence_collect.py",
)
assert SPEC and SPEC.loader
collect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)


def test_seed_average_joins_by_identity_and_uses_float64():
    expected_ids = np.asarray(["a", "b", "c"])
    records = [
        (7, np.asarray(["c", "a", "b"]), np.asarray([0.9, 0.1, 0.5], dtype=np.float32)),
        (3, np.asarray(["b", "c", "a"]), np.asarray([0.3, 0.7, 0.2], dtype=np.float32)),
    ]
    result = collect.mean_seed_predictions(records, (3, 7), expected_ids, label="synthetic")
    expected = np.mean(np.asarray([
        np.asarray([0.2, 0.3, 0.7], dtype=np.float32),
        np.asarray([0.1, 0.5, 0.9], dtype=np.float32),
    ], dtype=np.float64), axis=0)
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, expected)


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([(1, np.asarray(["a"]), np.asarray([0.1])), (1, np.asarray(["a"]), np.asarray([0.2]))], "duplicate_seed"),
        ([(1, np.asarray(["a"]), np.asarray([0.1]))], "seed_count_mismatch"),
        ([(1, np.asarray(["b"]), np.asarray([0.1])), (2, np.asarray(["b"]), np.asarray([0.2]))], "membership_mismatch"),
    ],
)
def test_seed_average_refuses_duplicate_missing_or_misaligned_sources(records, message):
    with pytest.raises(collect.CollectionError, match=message):
        collect.mean_seed_predictions(records, (1, 2), np.asarray(["a"]), label="synthetic")


def test_identity_join_refuses_duplicate_cells():
    with pytest.raises(collect.CollectionError, match="duplicate"):
        collect.align_vector(
            np.asarray(["a", "b"]), np.asarray(["a", "a"]),
            np.asarray([0.1, 0.2]), label="synthetic",
        )


def test_deterministic_npz_is_byte_stable_and_pickle_free(tmp_path):
    arrays = {
        "grid_cell_id": np.asarray(["b", "a"]),
        "scores": np.asarray([0.25, 0.75], dtype=np.float64),
    }
    first = collect.deterministic_npz_bytes(arrays)
    second = collect.deterministic_npz_bytes(arrays)
    assert first == second
    path = tmp_path / "predictions.npz"
    path.write_bytes(first)
    with np.load(path, allow_pickle=False) as loaded:
        assert loaded.files == ["grid_cell_id", "scores"]
        np.testing.assert_array_equal(loaded["grid_cell_id"], arrays["grid_cell_id"])
        np.testing.assert_array_equal(loaded["scores"], arrays["scores"])


def test_receipt_tamper_is_refused(tmp_path):
    path = tmp_path / "receipt.json"
    value = {"status": "accepted"}
    value["receipt_digest"] = collect.digest_value(value)
    path.write_text(json.dumps(value))
    assert collect.read_receipt(path)["status"] == "accepted"
    value["status"] = "rejected"
    path.write_text(json.dumps(value))
    with pytest.raises(collect.CollectionError, match="digest_mismatch"):
        collect.read_receipt(path)


def test_collection_gate_refuses_before_source_access(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("source access occurred without execute gate")

    monkeypatch.setattr(collect, "validate_input_manifest", prohibited)
    with pytest.raises(collect.CollectionError, match="explicit_execute_gate"):
        collect.collect(execute=False)


def test_incomplete_closure_refuses_before_any_source_or_response_access(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("source access occurred before closure gate")

    monkeypatch.setattr(collect, "validate_input_manifest", prohibited)
    with pytest.raises(collect.CollectionError, match="not_response_free"):
        collect.verify_closed_sources(
            {"status": "incomplete", "outer_held_response_labels_read": 0},
            private=collect.ROOT / collect.ASSESSMENT_REL,
            require_closure_digest=False,
        )


def test_collector_has_no_canonical_response_reader():
    source = (SCRIPTS / "tasmania_pseudoabsence_collect.py").read_text()
    assert "response_partitioned.csv" not in source
    assert "open_held_response" not in source
    assert "y_held" in source  # inner OOF labels are the only evaluation labels read


@pytest.mark.parametrize(
    ("lane", "marker", "accepted"),
    [
        ("inner", False, True),
        ("inner", True, False),
        ("inner", None, False),
        ("inner", 0, False),
        ("inner", "false", False),
        ("outer", False, True),
        ("outer", True, False),
        ("outer", None, False),
        ("outer", 0, False),
        ("outer", "false", False),
    ],
)
def test_neural_scope_boundary_lane_specific_marker(lane, marker, accepted):
    value = {"outer_held_response_labels_read": 0, "smoke_non_promotable": marker}
    if accepted:
        collect._validate_neural_scope_boundary(value, lane, f"neural_{lane}")
    else:
        with pytest.raises(collect.CollectionError, match="scope_boundary_invalid"):
            collect._validate_neural_scope_boundary(value, lane, f"neural_{lane}")


def test_neural_outer_scope_boundary_accepts_only_omitted_production_default():
    collect._validate_neural_scope_boundary(
        {"outer_held_response_labels_read": 0}, "outer", "neural_outer",
    )
    with pytest.raises(collect.CollectionError, match="scope_boundary_invalid"):
        collect._validate_neural_scope_boundary(
            {"outer_held_response_labels_read": 0}, "inner", "neural_inner",
        )
    with pytest.raises(collect.CollectionError, match="scope_boundary_invalid"):
        collect._validate_neural_scope_boundary(
            {"outer_held_response_labels_read": False}, "outer", "neural_outer",
        )


def test_live_task_crossproducts_match_approved_scope():
    neural, conventional, _assessment = collect.module_bundle(ROOT)
    n_inner, n_outer, c_inner, c_outer, selection = collect._validate_task_sets(
        ROOT, neural, conventional,
    )
    assert (len(n_inner), len(n_outer), len(c_inner), len(c_outer), len(selection)) == (
        2800, 560, 1200, 240, 56,
    )


def test_completed_neural_inner_and_outer_leaf_scope_contracts_validate_response_free():
    neural, conventional, _assessment = collect.module_bundle(ROOT)
    closures, preparations, caps, _source_closures, _source_bindings, _fit_counts = (
        collect.validate_source_receipts(ROOT, neural, conventional)
    )
    n_inner, n_outer, _c_inner, _c_outer, _selection = collect._validate_task_sets(
        ROOT, neural, conventional,
    )
    for role, task in (("neural_inner", n_inner[0]), ("neural_outer", n_outer[0])):
        lane = role.removeprefix("neural_")
        task_digest = neural._task_digest(task, lane)
        closure_row = collect._closure_rows(closures[role])[task_digest]
        receipt, arrays, inventory, starts = collect.validate_leaf(
            ROOT, role, task, neural, closure_row, preparations["neural"],
            caps["neural"]["receipt_digest"],
        )
        assert receipt["outer_held_response_labels_read"] == 0
        assert arrays["grid_cell_id"].size > 0
        assert inventory["task_digest"] == task_digest
        assert starts == receipt["physical_fits"]


def test_lane_directory_inventory_rejects_extra_and_wrong_kind(tmp_path):
    base = tmp_path / collect.NEURAL_REL / "inner"
    (base / "leaves/task-a").mkdir(parents=True)
    (base / "attempts/task-a").mkdir(parents=True)
    (base / "intents").mkdir(parents=True)
    (base / "intents/task-a.json").write_text("{}")
    runner = SimpleNamespace(_task_digest=lambda task, lane: task)
    collect.validate_lane_directory_inventory(tmp_path, "neural_inner", ("task-a",), runner)

    (base / "leaves/extra").mkdir()
    with pytest.raises(collect.CollectionError, match="leaves_directory_inventory_mismatch"):
        collect.validate_lane_directory_inventory(tmp_path, "neural_inner", ("task-a",), runner)
    (base / "leaves/extra").rmdir()

    (base / "intents/task-a.json").unlink()
    (base / "intents/task-a.json").mkdir()
    with pytest.raises(collect.CollectionError, match="intents_directory_inventory_mismatch"):
        collect.validate_lane_directory_inventory(tmp_path, "neural_inner", ("task-a",), runner)
