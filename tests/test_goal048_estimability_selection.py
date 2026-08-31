from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import goal048_estimability_selection as selection


def _thresholds() -> dict[str, int]:
    return {
        "evaluation_minimum_presence_cells_per_target_region": 2,
        "evaluation_minimum_x10_background_cells_per_target_region": 2,
        "evaluation_minimum_50km_tiles_per_class": 2,
        "training_minimum_presence_cells_per_target": 2,
        "training_minimum_x10_background_cells_per_target": 2,
        "training_minimum_spatial_folds_per_class": 2,
    }


def test_background_excludes_focal_presence_even_when_richness_reaches_x10():
    presence = np.array([True, False, False])
    richness = np.array([10, 10, 9])
    np.testing.assert_array_equal(selection.x_background_mask(presence, richness, 10), [False, True, False])


def test_x20_background_is_subset_of_x10_and_focal_exclusion_is_reapplied():
    presence = np.array([True, False, False, False])
    richness = np.array([20, 20, 10, 19])
    x10 = selection.x_background_mask(presence, richness, 10)
    x20 = selection.x_background_mask(presence, richness, 20)
    np.testing.assert_array_equal(x10, [False, True, True, True])
    np.testing.assert_array_equal(x20, [False, True, False, False])
    assert np.all(~x20 | x10)


def test_anchored_tiles_are_fixed_at_projected_origin_and_deduplicated():
    xy = np.array([[0.0, 0.0], [49_999.9, 49_999.9], [50_000.0, 0.0], [-1.0, -1.0]])
    tiles = selection.anchored_tiles(xy, np.ones(4, dtype=bool))
    assert tiles == {(0, 0), (1, 0), (-1, -1)}


def test_simultaneous_buffer_complement_is_union_of_official_region_buffers():
    region_masks = {"AUA": np.array([True, False, False]), "BBS": np.array([False, True, False])}
    buffer_masks = {"AUA": np.array([True, False, False]), "BBS": np.array([False, True, False])}
    _, training = selection._region_masks(region_masks, buffer_masks, ("AUA", "BBS"))
    np.testing.assert_array_equal(training, [False, False, True])


def test_region_gate_uses_training_complement_and_separate_evaluation_masks():
    xy = np.array([[0.0, 0.0], [50_000.0, 0.0], [100_000.0, 0.0], [150_000.0, 0.0]])
    region = np.array([True, True, False, False])
    presence = np.array([True, False, False, True])
    background = np.array([False, True, True, False])
    result = selection.region_gate_metrics(region, presence, background, background, xy, np.array([False, False, True, True]), _thresholds())
    assert result["evaluation_presence_cells"] == 1
    assert result["evaluation_x10_background_cells"] == 1
    assert result["training_presence_cells"] == 1
    assert result["training_x10_background_cells"] == 1
    assert result["evaluation_pass"] is False
    assert result["training_pass"] is False


def test_immutable_filter_preserves_input_order_and_scores():
    ranked = [
        {"regions": ["BBS", "KAN", "AUA"], "minimum_role_score": 0.9, "sum_role_scores": 2.2},
        {"regions": ["NAN", "NCP", "NET"], "minimum_role_score": 0.8, "sum_role_scores": 2.0},
        {"regions": ["NSS", "SCP", "SEC"], "minimum_role_score": 0.7, "sum_role_scores": 1.9},
    ]
    result = selection.filter_immutable_ranked(
        ranked,
        {("AUA", "BBS", "KAN"): {"passes": True}, ("NAN", "NCP", "NET"): {"passes": False}, ("NSS", "SCP", "SEC"): {"passes": True}},
    )
    assert [row["regions"] for row in result] == [["BBS", "KAN", "AUA"], ["NSS", "SCP", "SEC"]]
    assert [row["immutable_rank"] for row in result] == [1, 3]
    assert result[0]["minimum_role_score"] == 0.9


def test_signed_ambiguity_margins_use_frozen_and_rule():
    config = {"joint_selection": {"ambiguity": {"minimum_role_score_margin_below": 0.01, "summed_role_score_margin_below": 0.02}}}
    feasible = [
        {"regions": ["NCP", "NET", "SEH"], "minimum_role_score": 0.700, "sum_role_scores": 2.100},
        {"regions": ["NCP", "SEH", "NNC"], "minimum_role_score": 0.695, "sum_role_scores": 2.090},
    ]
    result = selection.ambiguity_summary(feasible, config)
    assert result["minimum_margin"] == pytest.approx(0.005)
    assert result["sum_margin"] == pytest.approx(0.010)
    assert result["ambiguous"] is True


def test_signed_sum_margin_can_be_negative_but_ambiguity_uses_both_thresholds():
    config = {"joint_selection": {"ambiguity": {"minimum_role_score_margin_below": 0.01, "summed_role_score_margin_below": 0.02}}}
    feasible = [
        {"regions": ["AUA", "BBS", "KAN"], "minimum_role_score": 0.705, "sum_role_scores": 2.0},
        {"regions": ["NAN", "NCP", "NET"], "minimum_role_score": 0.700, "sum_role_scores": 2.1},
    ]
    result = selection.ambiguity_summary(feasible, config)
    assert result["minimum_margin"] == pytest.approx(0.005)
    assert result["sum_margin"] == pytest.approx(-0.1)
    assert result["ambiguous"] is True


def test_gate_vector_validator_rejects_mismatched_lengths():
    with pytest.raises(selection.SelectionError, match="gate vector length drift"):
        selection.region_gate_metrics(
            np.array([True]), np.array([False, True]), np.array([True]), np.array([True]), np.zeros((1, 2)), np.array([True]), _thresholds()
        )


def test_immutable_filter_validator_rejects_missing_gate_result():
    with pytest.raises(selection.SelectionError, match="missing gate result"):
        selection.filter_immutable_ranked([{"regions": ["AUA", "BBS", "KAN"]}], {})


def test_empty_immutable_result_is_a_non_ambiguous_stop():
    config = {"joint_selection": {"ambiguity": {"minimum_role_score_margin_below": 0.01, "summed_role_score_margin_below": 0.02}}}
    result = selection.ambiguity_summary([], config)
    assert result == {"feasible_count": 0, "first": None, "second": None, "minimum_margin": None, "sum_margin": None, "ambiguous": False}


def test_x20_diagnostic_is_scoped_to_common_x10_panel():
    target_metrics = {
        "target_a": {
            "NCP": {"x20_evaluation_pass_diagnostic": True, "evaluation_x20_background_cells": 12},
            "NET": {"x20_evaluation_pass_diagnostic": True, "evaluation_x20_background_cells": 14},
            "SEH": {"x20_evaluation_pass_diagnostic": True, "evaluation_x20_background_cells": 16},
        },
        "target_b": {
            "NCP": {"x20_evaluation_pass_diagnostic": True, "evaluation_x20_background_cells": 18},
            "NET": {"x20_evaluation_pass_diagnostic": False, "evaluation_x20_background_cells": 20},
            "SEH": {"x20_evaluation_pass_diagnostic": True, "evaluation_x20_background_cells": 22},
        },
        "nonpanel": {
            "NCP": {"x20_evaluation_pass_diagnostic": False, "evaluation_x20_background_cells": 1},
            "NET": {"x20_evaluation_pass_diagnostic": False, "evaluation_x20_background_cells": 1},
            "SEH": {"x20_evaluation_pass_diagnostic": False, "evaluation_x20_background_cells": 1},
        },
    }
    result = selection.x20_panel_diagnostic_summary(target_metrics, ["target_a", "target_b"], ["NCP", "NET", "SEH"])
    assert result == {
        "common_x10_panel_target_region_count": 6,
        "common_x10_panel_x20_diagnostic_pass_count": 1,
        "common_x10_panel_x20_background_cells_min": 12,
        "common_x10_panel_x20_background_cells_max": 22,
    }


def _ambiguous_alternatives() -> tuple[list[dict], dict]:
    feasible = [
        {
            "immutable_rank": 3,
            "regions": ["NCP", "NET", "SEH"],
            "roles": {"edge": "NET", "mosaic": "SEH", "supported": "NCP"},
            "minimum_role_score": 0.6906158357771262,
            "sum_role_scores": 2.288332635106829,
        },
        {
            "immutable_rank": 4,
            "regions": ["NCP", "NNC", "SEH"],
            "roles": {"edge": "SEH", "mosaic": "NNC", "supported": "NCP"},
            "minimum_role_score": 0.6851173020527859,
            "sum_role_scores": 2.362327188940092,
        },
    ]
    config = {"joint_selection": {"ambiguity": {"minimum_role_score_margin_below": 0.01, "summed_role_score_margin_below": 0.02}}}
    return feasible, selection.ambiguity_summary(feasible, config)


def test_authorised_resolution_is_validated_against_both_immutable_alternatives(tmp_path):
    feasible, summary = _ambiguous_alternatives()
    path = tmp_path / "design_resolution.json"
    path.write_text(json.dumps(selection._expected_resolution()), encoding="utf-8")
    original = selection.RESOLUTION_PATH
    selection.RESOLUTION_PATH = Path(path.name)
    try:
        assert selection._load_resolution(tmp_path, feasible, summary)["selected_immutable_rank"] == 4
    finally:
        selection.RESOLUTION_PATH = original


def test_resolution_rejects_tampered_or_non_candidate_selection(tmp_path):
    feasible, summary = _ambiguous_alternatives()
    payload = selection._expected_resolution()
    payload["selected_regions"] = ["AUA", "NCP", "SEH"]
    path = tmp_path / "design_resolution.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    original = selection.RESOLUTION_PATH
    selection.RESOLUTION_PATH = Path(path.name)
    try:
        with pytest.raises(selection.SelectionError, match="authorised decision"):
            selection._load_resolution(tmp_path, feasible, summary)
    finally:
        selection.RESOLUTION_PATH = original


def test_boundary_map_is_boundary_only_and_contains_selected_roles(tmp_path, monkeypatch):
    ibra = Path(__file__).parents[1] / selection.scoring.IBRA_PATH
    monkeypatch.setattr(selection.scoring, "IBRA_PATH", ibra)
    monkeypatch.setattr(selection, "SVG_PATH", Path("map.svg"))
    out = selection.write_selected_holdouts_svg(tmp_path, selection._expected_resolution())
    text = out.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    paths = root.findall(".//{http://www.w3.org/2000/svg}path")
    selected = [path for path in paths if path.get("data-role")]
    assert len(selected) == 3
    assert {path.get("data-region-code") for path in selected} == {"NCP", "SEH", "NNC"}
    assert {path.get("data-role") for path in selected} == {"supported", "edge", "mosaic"}
    assert "Display-only cartography" in text
    assert out.stat().st_size < 500_000
    assert not any(token in text.lower() for token in ("occurrence", "species", "response", "longitude", "latitude", "cell_id"))
    assert all(path.get("d") for path in paths)


def test_production_receipt_has_final_status_and_hash_bound_map():
    root = Path(__file__).parents[1]
    receipt_path = root / selection.RECEIPT_PATH
    svg_path = root / selection.SVG_PATH
    if not receipt_path.is_file() or not svg_path.is_file():
        pytest.skip("Goal 048 production artifacts have not been generated")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(svg_path.read_bytes()).hexdigest()
    assert receipt["status"] == "selected_after_explicit_resolution"
    assert receipt["final_resolution"]["selected_immutable_rank"] == 4
    assert receipt["selected_design"]["boundary_map"]["sha256"] == digest
    assert receipt["input_sha256"]["selected_holdouts_svg"] == digest
    assert receipt["selected_design"]["evaluation"]["outer_model_outcomes_unopened"] is True
    assert receipt["selected_design"]["evaluation"]["aggregate_support_used_for_estimability_gates_only"] is True
    assert "outer_holdouts_unopened" not in receipt["selected_design"]["evaluation"]
    assert receipt["selected_design"]["evaluation"]["diagnostics"] == ["balanced_accuracy", "TSS", "MCC", "sensitivity", "specificity"]
