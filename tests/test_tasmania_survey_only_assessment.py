"""Synthetic, response-free tests for the Tasmania survey-only panel."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "scripts/tasmania_survey_only_assessment.py"
SPEC = importlib.util.spec_from_file_location("tasmania_survey_only_assessment", SOURCE)
assert SPEC and SPEC.loader
survey = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = survey
SPEC.loader.exec_module(survey)


@pytest.fixture
def small_scope(monkeypatch):
    monkeypatch.setattr(survey, "SPECIES", ("sp",))
    monkeypatch.setattr(survey, "ENDPOINTS", ("ep",))
    return survey


def rows(*sources):
    values = []
    for index, source in enumerate(sources):
        values.append({
            "species_id": "sp", "grid_cell_id": f"g{index}", "microcluster": "mc0",
            "pa": "1" if source == "presence" else "0", "pa_type": source,
        })
    return values


def panel(scores=None, sensitivity=None, thresholds=None):
    scores = np.asarray(scores or [[0.9, 0.8, 0.2, 0.1]] * 3, dtype=np.float64).T
    # The rows above are methods; normalize to endpoint x method x cell.
    scores = np.asarray([scores.T], dtype=np.float64)
    sensitivity = np.asarray(sensitivity if sensitivity is not None else scores[0] * 0.9, dtype=np.float64)
    if sensitivity.shape == (3, 4):
        sensitivity = sensitivity[None, ...]
    thresholds = np.asarray(thresholds if thresholds is not None else [[0.5, 0.5, 0.5]], dtype=np.float64)
    return {
        "grid_cell_id": np.asarray(["g0", "g1", "g2", "g3"]),
        "patch": np.asarray(["mc0"] * 4),
        "primary_scores": scores,
        "sensitivity_scores": sensitivity,
        "primary_thresholds": thresholds,
        "sensitivity_thresholds": thresholds.copy(),
        "map_grid_cell_id": np.asarray(["m0", "m1"]),
        "primary_map_scores": np.zeros((3, 2), dtype=np.float64),
        "sensitivity_map_scores": np.zeros((3, 2), dtype=np.float64),
    }


def test_source_mask_retains_presences_and_survey_absences_only(small_scope):
    source_rows = rows("presence", "presence", "survey_supported_absence", "pseudoabsence")
    snapshot = small_scope.validate_source_labels(source_rows)
    performance, counts = small_scope.compute_performance({"sp": panel()}, snapshot)
    assert counts["sp"]["retained_rows"] == 3
    assert counts["sp"]["retained_presence"] == 2
    assert counts["sp"]["retained_survey_supported_absence"] == 1
    assert counts["sp"]["excluded_pseudoabsence"] == 1
    survey_rows = [row for row in performance if row["evaluation_panel"] == "survey_only"]
    assert len(survey_rows) == 3
    assert {row["n"] for row in survey_rows} == {3}


def test_source_class_validation_rejects_mismatch_and_unknown_source(small_scope):
    bad = rows("presence", "survey_supported_absence")
    bad[0]["pa"] = "0"
    with pytest.raises(survey.SurveyOnlyError, match="source_class_disagreement"):
        small_scope.validate_source_labels(bad)
    bad = rows("presence", "survey_supported_absence")
    bad[1]["pa_type"] = "unknown"
    with pytest.raises(survey.SurveyOnlyError, match="source_invalid"):
        small_scope.validate_source_labels(bad)


def test_row_order_invariance_and_no_positional_join(small_scope):
    panel_value = panel()
    ordered = small_scope.validate_source_labels(rows("presence", "presence", "survey_supported_absence", "survey_supported_absence"))
    shuffled_rows = [rows("presence", "presence", "survey_supported_absence", "survey_supported_absence")[i] for i in (2, 0, 3, 1)]
    shuffled = small_scope.validate_source_labels(shuffled_rows)
    first, _ = small_scope.compute_performance({"sp": panel_value}, ordered)
    second, _ = small_scope.compute_performance({"sp": panel_value}, shuffled)
    assert first == second


def test_missing_and_duplicate_identities_refuse(small_scope):
    source_rows = rows("presence", "presence", "survey_supported_absence", "survey_supported_absence")
    expected = {("sp", f"g{i}") for i in range(4)}
    with pytest.raises(survey.SurveyOnlyError, match="membership_mismatch"):
        small_scope.validate_source_labels(source_rows[:-1], expected)
    duplicate = list(source_rows)
    duplicate[-1] = dict(duplicate[0])
    with pytest.raises(survey.SurveyOnlyError, match="duplicate_identity"):
        small_scope.validate_source_labels(duplicate)


def test_frozen_thresholds_are_reused_exactly_by_compute(small_scope):
    value = panel()
    value["primary_thresholds"] = np.asarray([[0.35, 0.45, 0.55]], dtype=np.float64)
    value["sensitivity_thresholds"] = np.asarray([[0.65, 0.75, 0.85]], dtype=np.float64)
    snapshot = small_scope.validate_source_labels(rows("presence", "presence", "survey_supported_absence", "survey_supported_absence"))
    performance, _ = small_scope.compute_performance({"sp": value}, snapshot)
    row = next(row for row in performance if row["evaluation_panel"] == "survey_only" and row["method"] == "target_only_resmlp")
    assert row["primary_threshold"] == 0.35
    assert row["sensitivity_threshold"] == 0.65
    assert row["delta_threshold"] == 0.30000000000000004


def test_auc_ties_and_extended_confusion_metrics_are_deterministic(small_scope):
    result = small_scope.extended_metrics([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.9], 0.5)
    assert result["roc_auc"] == pytest.approx(0.75)
    assert result["tp"] == 2 and result["tn"] == 0 and result["fp"] == 2 and result["fn"] == 0
    assert result["sensitivity"] == 1.0 and result["specificity"] == 0.0
    assert result["balanced_accuracy"] == 0.5


def test_zero_removal_control_reproduces_original_metrics(small_scope):
    snapshot = small_scope.validate_source_labels(rows("presence", "presence", "survey_supported_absence", "survey_supported_absence"))
    performance, counts = small_scope.compute_performance({"sp": panel()}, snapshot)
    assert counts["sp"]["excluded_pseudoabsence"] == 0
    for row in performance:
        if row["evaluation_panel"] == "original_mixed":
            counterpart = next(other for other in performance if other["evaluation_panel"] == "survey_only" and other["endpoint"] == row["endpoint"] and other["method"] == row["method"])
            assert {key: value for key, value in row.items() if key != "evaluation_panel"} == {key: value for key, value in counterpart.items() if key != "evaluation_panel"}


def test_receipt_and_hash_tampering_are_rejected(tmp_path):
    path = tmp_path / "receipt.json"
    body = {"status": "pass"}
    path.write_text(json.dumps({**body, "receipt_digest": survey.digest_value(body)}))
    assert survey.read_receipt(path)["status"] == "pass"
    path.write_text(json.dumps({"status": "tampered", "receipt_digest": survey.digest_value(body)}))
    with pytest.raises(survey.SurveyOnlyError, match="receipt_digest_mismatch"):
        survey.read_receipt(path)


def test_missing_independent_audit_refuses_before_any_panel_work(tmp_path):
    with pytest.raises(survey.SurveyOnlyError, match="receipt_missing"):
        survey.validate_independent_audit(tmp_path)
    with pytest.raises(survey.SurveyOnlyError, match="explicit_execute_gate"):
        survey.evaluate(tmp_path)
