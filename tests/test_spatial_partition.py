import csv
import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsdm_phase1 import spatial_partition as sp  # noqa: E402


PLAN = ROOT / "config/spatial_partition_plan.json"
RECEIPT = ROOT / "config/spatial_partition_visual_review.json"
EVIDENCE = ROOT / "evidence/spatial_partition/2026-07-26"
PRIVATE = (
    ROOT
    / "data/processed/partitions/goal025-spatial-partition/2026-07-26"
)
GOAL025_PRIVATE_REPLAY_ENABLED = (
    platform.python_version() == "3.14.4"
    and os.environ.get("DSDM_RUN_GOAL025_PRIVATE_REPLAY") == "1"
)
GOAL025_PRIVATE_REPLAY_SKIP_REASON = (
    "Goal025 private replay requires CPython 3.14.4 and "
    "DSDM_RUN_GOAL025_PRIVATE_REPLAY=1"
)


def _rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_maximin_ties_nearest_ties_and_canonical_hierarchy():
    points = np.array(
        [[0.0, 0.0], [0.0, 2.0], [2.0, 0.0], [2.0, 2.0]],
        dtype=np.float64,
    )
    assert sp.maximin_centers(points, ["b", "a", "d", "c"], 2) == [1, 2]
    assert sp.nearest_center(
        np.array([[1.0, 1.0]]), points[[1, 2]], ["a", "d"]
    ).tolist() == [0]

    rows = [
        {"grid_cell_id": f"g{i}", "centroid_lon": 145 + x, "centroid_lat": -43 + y}
        for i, (x, y) in enumerate(
            [(0, 0), (0, 0.1), (0.1, 0), (0.1, 0.1), (0.2, 0), (0.2, 0.1)]
        )
    ]
    geometry = sp.geometry(rows, n_micro=4, n_macro=2)
    centres = geometry["micro_centers"]
    assert [
        (float(y), float(x), grid_id)
        for (x, y), grid_id in zip(
            centres, geometry["micro_center_grid_ids"], strict=True
        )
    ] == sorted(
        (float(y), float(x), grid_id)
        for (x, y), grid_id in zip(
            centres, geometry["micro_center_grid_ids"], strict=True
        )
    )
    expected_macro_raw = sp.maximin_centers(
        centres, [f"{index:02d}" for index in range(4)], 2
    )
    assert set(geometry["macro_center_microclusters"]) == set(expected_macro_raw)


def test_geometry_uses_only_map_identity_and_coordinates():
    rows = [
        {
            "grid_cell_id": f"g{i}",
            "centroid_lon": 145 + i * 0.01,
            "centroid_lat": -43 + (i % 3) * 0.01,
            "pa": i % 2,
            "response_origin": "must_not_influence_geometry",
            "annmeantemp": i * 1000,
        }
        for i in range(12)
    ]
    stripped = [
        {
            "grid_cell_id": row["grid_cell_id"],
            "centroid_lon": row["centroid_lon"],
            "centroid_lat": row["centroid_lat"],
        }
        for row in rows
    ]
    first = sp.geometry(rows, n_micro=6, n_macro=2)
    second = sp.geometry(stripped, n_micro=6, n_macro=2)
    assert first["micro_center_grid_ids"] == second["micro_center_grid_ids"]
    assert first["micro_assignments"].tolist() == second["micro_assignments"].tolist()
    assert first["micro_macro"].tolist() == second["micro_macro"].tolist()


def test_sha_serialization_priority_and_fold_canonicalisation():
    assert sp.priority(7, 3) == (
        "111c309fc0cfd2b772a26b9c6f05c0e3b19eaa2ccf302881b9eed7faeab435f0"
    )
    expected = sorted(
        [0, 1, 2, 3],
        key=lambda cluster: hashlib.sha256(f"9:{cluster}".encode("utf-8")).digest(),
    )
    assert sp.priority_order(9, [0, 1, 2, 3]) == expected
    assert sp.canonical_fold_tuples([[5, 1], [4, 3]]) == ((1, 5), (3, 4))
    first = sp.folds_for_seed(9, [0, 1, 2, 3], n_folds=2)
    second = sp.folds_for_seed(9, [0, 1, 2, 4], n_folds=2)
    assert first == sp.canonical_fold_tuples([expected[:2], expected[2:]])
    assert first != second


def test_impossible_all_five_gate_and_stratified_generator_invariants():
    macro = np.empty(50, dtype=np.int64)
    memberships = {
        0: list(range(0, 9)),
        1: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 27, 28, 30, 31, 32, 33, 34, 37, 39],
        2: [22, 26, 29, 35, 36, 38, 41, 43, 45],
        3: [40, 42, 44, 47, 48],
        4: [46, 49],
    }
    for macroregion, clusters in memberships.items():
        macro[clusters] = macroregion
    outer = (0, 9, 22, 40, 46)
    remaining_counts = [
        sum(macro[cluster] == value for cluster in set(range(50)) - set(outer))
        for value in range(5)
    ]
    assert remaining_counts == [8, 24, 8, 4, 1]
    assert not sp.literal_all_macroregions_per_fold_possible(remaining_counts)

    folds = sp.stratified_folds_for_seed(7, outer, macro)
    assert len(folds) == 5
    assert all(len(fold) == 9 for fold in folds)
    assert set().union(*(set(fold) for fold in folds)) == set(range(50)) - set(outer)
    per_macro = np.array(
        [
            [sum(macro[cluster] == value for cluster in fold) for value in range(5)]
            for fold in folds
        ]
    )
    assert np.all(np.sum(per_macro > 0, axis=1) == 4)
    assert np.all(per_macro.max(axis=0) - per_macro.min(axis=0) <= 1)


def test_outer_gates_are_inclusive_and_fail_each_material_boundary():
    aggregate = {
        "map_count": np.array([20] * 5 + [180] * 5, dtype=np.int64),
        "response_cell_count": np.array([20] * 5 + [180] * 5, dtype=np.int64),
        "class_count": np.array([[2] * 16] * 5 + [[10] * 16] * 5, dtype=np.int64),
        "class_total": np.array([60] * 16, dtype=np.int64),
        "map_total": 1000,
        "response_cell_total": 1000,
    }
    macro = np.array([0, 1, 2, 3, 4, 0, 1, 2, 3, 4], dtype=np.int64)
    passed = sp.evaluate_outer((0, 1, 2, 3, 4), macro, aggregate)
    assert passed["outer_viable"] is True
    assert passed["map_share"] == pytest.approx(0.1)
    assert passed["response_cell_share"] == pytest.approx(0.1)
    assert passed["minimum_cluster_response_cells"] == 20
    assert passed["minimum_test_species_binary_rows"] == 10
    assert passed["minimum_complement_species_binary_rows"] == 50

    each_gate = {
        "macro_gate": macro.copy(),
        "map_gate": aggregate["map_count"].copy(),
        "response_share_gate": aggregate["response_cell_count"].copy(),
        "cluster_response_gate": aggregate["response_cell_count"].copy(),
        "test_class_gate": aggregate["class_count"].copy(),
        "complement_class_gate": aggregate["class_total"].copy(),
    }
    each_gate["macro_gate"][4] = 0
    each_gate["map_gate"][:3] = 0
    each_gate["response_share_gate"][:3] = 0
    each_gate["cluster_response_gate"][0] = 19
    each_gate["cluster_response_gate"][5] += 1
    each_gate["test_class_gate"][0, 0] = 1
    each_gate["complement_class_gate"][0] = 59

    for name, changed in each_gate.items():
        candidate = {
            key: (value.copy() if isinstance(value, np.ndarray) else value)
            for key, value in aggregate.items()
        }
        changed_macro = macro
        if name == "macro_gate":
            changed_macro = changed
        elif name == "map_gate":
            candidate["map_count"] = changed
        elif name in {"response_share_gate", "cluster_response_gate"}:
            candidate["response_cell_count"] = changed
        elif name == "test_class_gate":
            candidate["class_count"] = changed
        else:
            candidate["class_total"] = changed
        assert (
            sp.evaluate_outer((0, 1, 2, 3, 4), changed_macro, candidate)[
                "outer_viable"
            ]
            is False
        ), name


@pytest.fixture(scope="module")
def real_search():
    plan = json.loads(PLAN.read_text())
    bindings = sp.validate_bindings(ROOT, plan)
    maps = _rows(bindings["goal024_map"])
    cells = _rows(bindings["goal024_response_cells"])
    responses = _rows(bindings["goal024_response"])
    geometry = sp.geometry(maps)
    aggregate = sp.build_cluster_arrays(geometry, cells, responses)
    return geometry, aggregate, sp.search_candidates(geometry, aggregate)


def test_real_search_matches_corrected_exact_oracle(real_search):
    _, _, result = real_search
    expected = {
        (2, 16, 29, 40, 49): [3105],
        (2, 16, 36, 40, 49): [1092],
        (4, 26, 28, 40, 46): [1810],
        (8, 20, 35, 40, 49): [422, 2831],
        (8, 20, 40, 41, 46): [422, 2036, 2694],
        (8, 26, 32, 42, 46): [422],
    }
    assert result["unique_outer_count"] == 3694
    assert result["outer_viable_count"] == 166
    assert result["joint_feasible_count"] == 6
    assert set(result["joint_feasible"]) == set(expected)
    assert sum(len(value) for value in result["viable_cv"].values()) == 9
    for outer, expected_seeds in expected.items():
        viable = result["viable_cv"][outer]
        assert [candidate["cv_seed"] for candidate in viable] == expected_seeds
        for candidate in viable:
            folds = candidate["folds"]
            assert len(folds) == 5
            assert all(len(fold) == 9 for fold in folds)
            union = set().union(*(set(fold) for fold in folds))
            assert union == set(range(50)) - set(outer)
            assert not set(outer) & union
            assert candidate["fold_macroregion_counts"] == (4, 4, 4, 4, 4)


def test_distance_metrics_midranks_and_equal_third_tie_order():
    assert sp.ks_distance([0, 1], [0, 1]) == 0
    assert sp.ks_distance([0, 0], [1, 1]) == 1
    assert sp.tv_distance(["a", "b"], ["a", "b"]) == 0
    assert sp.tv_distance(["a", "a"], ["b", "b"]) == 1
    assert sp.midrank_scores([5, 5, 1], higher_is_better=True) == pytest.approx(
        [0.75, 0.75, 0.0]
    )

    records = [
        {
            "outer_tuple": (0, 1, 2, 3, 4),
            "seed": 4,
            "geography_min_m": 30,
            "geography_mean_m": 30,
            "environment_loss": 3,
            "representation_mean_loss": 2,
            "representation_worst_loss": 2,
        },
        {
            "outer_tuple": (0, 1, 2, 3, 5),
            "seed": 3,
            "geography_min_m": 20,
            "geography_mean_m": 20,
            "environment_loss": 1,
            "representation_mean_loss": 3,
            "representation_worst_loss": 3,
        },
        {
            "outer_tuple": (0, 1, 2, 3, 6),
            "seed": 2,
            "geography_min_m": 10,
            "geography_mean_m": 10,
            "environment_loss": 2,
            "representation_mean_loss": 1,
            "representation_worst_loss": 1,
        },
    ]
    ranked = sp.rank_outer_candidates(records)
    assert ranked[0]["outer_tuple"] == (0, 1, 2, 3, 4)
    assert len({record["equal_third_score"] for record in ranked}) == 1


def test_assignments_are_cell_shared_and_outer_never_enters_cv():
    geometry = {
        "ids": [f"g{index:02d}" for index in range(50)],
        "micro_assignments": np.arange(50, dtype=np.int64),
        "micro_macro": np.repeat(np.arange(5), 10),
        "rows": [{"grid_cell_id": f"g{index:02d}"} for index in range(50)],
    }
    cells = [{"grid_cell_id": "g00"}, {"grid_cell_id": "g01"}]
    responses = [
        {"species_id": "a", "grid_cell_id": "g01"},
        {"species_id": "b", "grid_cell_id": "g01"},
    ]
    outer = (0, 10, 20, 30, 40)
    folds = sp.canonical_fold_tuples(
        np.array(sorted(set(range(50)) - set(outer))).reshape(5, 9)
    )
    assignments = sp.build_assignments(geometry, cells, responses, outer, folds)
    by_cell = {row["grid_cell_id"]: row for row in assignments["map_assignments"]}
    response_assignments = assignments["response_partitioned"]
    assert response_assignments[0]["microcluster"] == by_cell["g01"]["microcluster"]
    assert response_assignments[0]["cv_fold"] == response_assignments[1]["cv_fold"]
    assert {row["cv_fold"] for row in assignments["map_assignments"] if row["outer_role"] == "test"} == {""}
    assert {
        sum(row["cv_fold"] == f"fold{fold:02d}" for row in assignments["map_assignments"])
        for fold in range(5)
    } == {9}


def test_support_is_fit_from_species_training_response_rows_only():
    maps = [
        {"grid_cell_id": "a", "x": "1", "cat": "A"},
        {"grid_cell_id": "b", "x": "2", "cat": "A"},
        {"grid_cell_id": "training_map_only", "x": "100", "cat": "C"},
        {"grid_cell_id": "assessment", "x": "3", "cat": "B"},
    ]
    responses = [
        {
            "species_id": "sp",
            "grid_cell_id": "a",
            "pa": "1",
            "pa_type": "presence",
            "response_origin": "x",
            "source_combination": "x",
        },
        {
            "species_id": "sp",
            "grid_cell_id": "b",
            "pa": "0",
            "pa_type": "survey_supported_absence",
            "response_origin": "x",
            "source_combination": "x",
        },
        {
            "species_id": "sp",
            "grid_cell_id": "assessment",
            "pa": "1",
            "pa_type": "presence",
            "response_origin": "x",
            "source_combination": "x",
        },
    ]
    result = sp.support_for_split(
        "synthetic",
        {"a", "b", "training_map_only"},
        {"assessment"},
        maps,
        responses,
        active=("x", "cat"),
        categorical=("cat",),
        species=("sp",),
    )
    species = result["species"]["sp"]
    assert species["continuous"]["x"]["training_min"] == 1
    assert species["continuous"]["x"]["training_max"] == 2
    assert species["continuous"]["x"]["assessment_above"] == 1
    assert species["continuous"]["x"]["map_above"] == 2
    assert species["categorical"]["cat"]["training_levels"] == ["A"]
    assert species["categorical"]["cat"]["assessment_unseen"] == 1
    assert species["categorical"]["cat"]["map_unseen"] == 2
    assert result["out_of_dictionary_count"] == 0


def test_exclusions_are_nearest_assigned_and_cannot_influence_search(real_search):
    geometry, aggregate, result = real_search
    x, y = geometry["micro_centers"][7]
    lon, lat = sp.unproject_xy([x], [y])
    excluded_cells = [
        {
            "grid_cell_id": "audit_only",
            "centroid_lon": str(lon[0]),
            "centroid_lat": str(lat[0]),
        }
    ]
    excluded_rows = [
        {
            "species_id": "audit_species",
            "grid_cell_id": "audit_only",
            "centroid_lon": str(lon[0]),
            "centroid_lat": str(lat[0]),
        }
    ]
    audited = sp.assign_excluded_audit(geometry, excluded_cells, excluded_rows)
    assert audited["excluded_cell_audit"][0]["microcluster"] == "mc07"
    assert audited["excluded_row_audit"][0]["microcluster"] == "mc07"
    repeated = sp.search_candidates(geometry, aggregate)
    assert repeated["joint_feasible"] == result["joint_feasible"]


def test_regular_file_set_rejects_missing_extra_symlink_and_byte_drift(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir()
    (directory / "a.csv").write_bytes(b"x\n")
    expected = {
        "a.csv": {
            "bytes": 2,
            "sha256": hashlib.sha256(b"x\n").hexdigest(),
        }
    }
    sp.validate_regular_file_set(directory, expected)

    (directory / "extra").write_text("x")
    with pytest.raises(sp.SpatialPartitionError, match="footprint"):
        sp.validate_regular_file_set(directory, expected)
    (directory / "extra").unlink()

    (directory / "a.csv").write_bytes(b"y\n")
    with pytest.raises(sp.SpatialPartitionError, match="byte_or_sha"):
        sp.validate_regular_file_set(directory, expected)
    (directory / "a.csv").unlink()
    (directory / "target").write_text("x")
    (directory / "a.csv").symlink_to(directory / "target")
    with pytest.raises(sp.SpatialPartitionError, match="symlink"):
        sp.validate_regular_file_set(
            directory,
            {
                "a.csv": {
                    "bytes": 1,
                    "sha256": hashlib.sha256(b"x").hexdigest(),
                },
                "target": {
                    "bytes": 1,
                    "sha256": hashlib.sha256(b"x").hexdigest(),
                },
            },
        )


def _refresh_manifest(directory):
    payload = sp.manifest_payload(directory, sp.EVIDENCE_FILES)
    (directory / "manifest.json").write_text(sp.json_text(payload))


def test_refreshed_manifest_cannot_hide_semantic_or_privacy_tampering(tmp_path):
    evidence = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, evidence)
    summary_path = evidence / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["centroid_lon"] = 147.12
    summary_path.write_text(sp.json_text(summary))
    _refresh_manifest(evidence)
    with pytest.raises(sp.SpatialPartitionError, match="privacy|semantic"):
        sp.validate_evidence(PLAN, evidence, root=ROOT, mode="pending")

    shutil.rmtree(evidence)
    shutil.copytree(EVIDENCE, evidence)
    summary = json.loads((evidence / "summary.json").read_text())
    summary["counts"]["map_cells"] -= 1
    (evidence / "summary.json").write_text(sp.json_text(summary))
    _refresh_manifest(evidence)
    with pytest.raises(sp.SpatialPartitionError, match="semantic"):
        sp.validate_evidence(PLAN, evidence, root=ROOT, mode="pending")

    shutil.rmtree(evidence)
    shutil.copytree(EVIDENCE, evidence)
    summary = json.loads((evidence / "summary.json").read_text())
    summary["topology"]["outer_union_queen_components"] = 10
    (evidence / "summary.json").write_text(sp.json_text(summary))
    _refresh_manifest(evidence)
    with pytest.raises(sp.SpatialPartitionError, match="semantic"):
        sp.validate_evidence(PLAN, evidence, root=ROOT, mode="final")


def test_privacy_walk_allows_false_contract_declarations_only():
    sp._privacy_walk({"privacy": sp.PRIVACY})
    with pytest.raises(sp.SpatialPartitionError, match="tracked_privacy_key"):
        sp._privacy_walk({"tracked_site_or_camera_ids": ["camera-1"]})
    with pytest.raises(sp.SpatialPartitionError, match="tracked_privacy_key"):
        sp._privacy_walk({"site_id": "site-1"})


def test_pending_and_passed_receipts_are_distinct_modes():
    passed = json.loads(RECEIPT.read_text())
    evidence_review = json.loads((EVIDENCE / "review.json").read_text())
    assert passed["criteria_version"] == "goal025-v2"
    assert passed["checklist"] == [
        (
            "dominant components spatially coherent; island and D_struct "
            "fragmentation quantified and accepted"
        ),
        "plausible islands/coast",
        "five-region outer coverage",
        "no empty/effectively empty test patch",
        (
            "aggregate class imbalance visible; split-specific source/class "
            "concentrations checked from diagnostics"
        ),
        "no site IDs, timing, activity, or finer-than-0.01 source detail",
    ]
    assert sp.validate_receipt(passed, evidence_review, mode="final")["status"] == "passed"
    with pytest.raises(sp.SpatialPartitionError, match="pending_review_state_drift"):
        sp.validate_receipt(passed, evidence_review, mode="pending")

    pending = {
        **passed,
        "receipt_status": "pending_orchestrator",
        "reviewer": "orchestrator_pending",
        "reviewed_at": None,
    }
    pending_evidence = {
        **evidence_review,
        "receipt_status": "pending_orchestrator",
        "reviewer": "orchestrator_pending",
        "reviewed_at": None,
    }
    assert sp.validate_receipt(pending, pending_evidence, mode="pending")["status"] == (
        "pending_orchestrator"
    )
    with pytest.raises(sp.SpatialPartitionError, match="final_review_not_passed"):
        sp.validate_receipt(pending, pending_evidence, mode="final")


def test_summary_freezes_audited_design_topology_and_limitations():
    summary = json.loads((EVIDENCE / "summary.json").read_text())
    assert set(summary["design"]) == {
        "design_label",
        "geometry_and_fold_allocation_response_independent",
        "feasibility_gates_response_conditioned",
        "ranking_response_and_covariate_conditioned",
        "prediction_or_performance_input",
        "unbiased_confirmatory_transfer",
        "isolated_regional_extrapolation",
        "buffer_m",
        "search_scope",
    }
    assert summary["design"]["design_label"] == (
        "pre-model-frozen held-patch interpolation"
    )
    assert summary["design"]["geometry_and_fold_allocation_response_independent"] is True
    assert summary["design"]["feasibility_gates_response_conditioned"] is True
    assert summary["design"]["ranking_response_and_covariate_conditioned"] is True
    assert summary["design"]["prediction_or_performance_input"] is False
    assert summary["design"]["unbiased_confirmatory_transfer"] is False
    assert summary["design"]["isolated_regional_extrapolation"] is False
    assert summary["design"]["buffer_m"] == 0
    assert summary["design"]["search_scope"] == {
        "seed_schedule": [0, 4095],
        "scheduled_seeds": 4096,
        "distinct_outer_tuples_scanned": 3694,
        "possible_one_per_macro_tuples": 20250,
        "scheduled_outer_tuple_fraction": 3694 / 20250,
        "scope": (
            "complete prescribed seed schedule; not combinatorially exhaustive"
        ),
    }

    topology = summary["topology"]
    assert topology["microclusters_not_queen_contiguous"] == 19
    assert topology["selected_outer_microclusters"] == {
        "mc08": {
            "queen_components": 6,
            "dominant_component_cells": 1522,
            "total_cells": 1677,
            "dominant_component_share": 1522 / 1677,
        },
        "mc20": {
            "queen_components": 1,
            "dominant_component_cells": 2475,
            "total_cells": 2475,
            "dominant_component_share": 1.0,
        },
        "mc35": {
            "queen_components": 1,
            "dominant_component_cells": 895,
            "total_cells": 895,
            "dominant_component_share": 1.0,
        },
        "mc40": {
            "queen_components": 2,
            "dominant_component_cells": 1167,
            "total_cells": 1168,
            "dominant_component_share": 1167 / 1168,
        },
        "mc49": {
            "queen_components": 1,
            "dominant_component_cells": 538,
            "total_cells": 538,
            "dominant_component_share": 1.0,
        },
    }
    assert topology["outer_union_queen_components"] == 11
    assert topology["outer_cells_rook_touching_training"] == 484
    assert topology["outer_cells"] == 6753
    assert topology["outer_rook_touch_share"] == 484 / 6753
    assert topology["buffer_m"] == 0
    assert topology["cv_fold_cluster_adjacency_components"] == [8, 6, 7, 7, 8]
    assert topology["interpretation"] == (
        "five dispersed outer held patches and scattered multi-patch CV folds"
    )

    limitations = summary["limitations"]
    assert limitations["sarcophilus_harrisii"] == {
        "overall_presences": 3460,
        "overall_rows": 3573,
        "presence_fraction": 3460 / 3573,
        "presence_percent_2dp": 96.84,
        "outer_absences": 10,
        "outer_absence_microclusters": 3,
        "outer_camera_survey_supported_absences": 9,
        "outer_pseudoabsences": 1,
    }
    assert limitations["thylogale_billardierii"] == {
        "overall_presences": 1360,
        "overall_rows": 1485,
        "presence_fraction": 1360 / 1485,
        "presence_percent_2dp": 91.58,
        "outer_absences": 19,
        "outer_absence_microcluster": "mc49",
        "outer_camera_survey_supported_absences": 19,
        "minimum_cv_validation_absences": 10,
        "cv_folds_at_minimum_absences": 1,
    }
    assert limitations["outer_support"] == {
        "training_unseen_categorical_instances": 12,
        "continuous_out_of_range_instances": 174,
        "global_dictionary_out_of_dictionary_count": 0,
        "global_dictionary_interpretation": (
            "integrity check only; not evidence of split-specific support"
        ),
    }
    assert limitations["gate_interpretation"] == (
        "computability only; not stable discrimination or calibration"
    )
    assert limitations["required_downstream"] == [
        "prevalence-aware metrics",
        "spatial-block uncertainty",
        "per-cluster and source reporting",
        "sensitivity interpretation",
    ]


@pytest.mark.real_scope
@pytest.mark.skipif(
    not GOAL025_PRIVATE_REPLAY_ENABLED,
    reason=GOAL025_PRIVATE_REPLAY_SKIP_REASON,
)
def test_goal024_replays_once_and_goal025_recomputes_in_final_mode(monkeypatch):
    calls = []

    def goal024_validator(*args, **kwargs):
        calls.append((args, kwargs))
        return {"tracked_valid": True, "full_replay": True}

    result = sp.validate_evidence(
        PLAN,
        EVIDENCE,
        root=ROOT,
        mode="final",
        full=True,
        goal024_validator=goal024_validator,
    )
    assert result == {
        "tracked_valid": True,
        "private_valid": True,
        "full_replay": True,
        "review_status": "passed",
    }
    assert len(calls) == 1
    assert calls[0][1]["full"] is True


def test_publish_pair_blocks_existing_destination_and_rolls_back_second_rename(
    tmp_path, monkeypatch
):
    private = tmp_path / "private"
    evidence = tmp_path / "evidence"
    stage_parent = tmp_path / "staging"

    def writer(stage_private, stage_evidence):
        (stage_private / "private.txt").write_text("private")
        (stage_evidence / "evidence.txt").write_text("evidence")

    private.mkdir()
    with pytest.raises(sp.SpatialPartitionError, match="publication_destination_exists"):
        sp.publish_staged_pair(private, evidence, stage_parent, writer)
    private.rmdir()

    original = Path.rename
    rename_count = 0

    def fail_second_rename(path, target):
        nonlocal rename_count
        rename_count += 1
        if rename_count == 2:
            raise OSError("injected second rename failure")
        return original(path, target)

    monkeypatch.setattr(Path, "rename", fail_second_rename)
    with pytest.raises(sp.SpatialPartitionError, match="publication_second_rename"):
        sp.publish_staged_pair(private, evidence, stage_parent, writer)
    assert not private.exists()
    assert not evidence.exists()


@pytest.mark.real_scope
@pytest.mark.skipif(
    not GOAL025_PRIVATE_REPLAY_ENABLED,
    reason=GOAL025_PRIVATE_REPLAY_SKIP_REASON,
)
def test_current_private_and_evidence_footprints_and_final_full_replay():
    result = sp.validate_evidence(
        PLAN, EVIDENCE, root=ROOT, mode="final", full=True
    )
    assert result["tracked_valid"] is True
    assert result["private_valid"] is True
    assert result["full_replay"] is True
    assert result["review_status"] == "passed"
    assert {path.name for path in PRIVATE.iterdir()} == set(sp.PRIVATE_NAMES)
    assert not list(PRIVATE.rglob("*/*"))
    assert not [path for path in PRIVATE.iterdir() if path.is_symlink()]
    assert not [path for path in EVIDENCE.iterdir() if path.is_symlink()]
