"""Scientific edge cases; no model fitting or real response access."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest


spec = importlib.util.spec_from_file_location("sensitivity_metrics", Path(__file__).parents[1] / "scripts/tasmania_pseudoabsence_metrics.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_threshold_lower_median_of_disjoint_optima():
    # Two maximizers (0.3 and 0.7) bracket a worse intermediate classifier.
    result = m.select_threshold([0, 1, 0, 1], [0.2, 0.4, 0.6, 0.8])
    assert result["threshold"] == (0.2 + (0.4 - 0.2) / 2)
    assert result["maximizer_count"] == 2
    assert result["maximum_oof_tss"] == 0.5


def test_adjacent_floats_keep_exact_threshold_partition():
    a = 0.5
    b = np.nextafter(a, np.inf)
    result = m.select_threshold([0, 1], [a, b])
    assert result["threshold"] == b
    assert result["maximum_oof_tss"] == 1


def test_constant_prediction_and_absent_source():
    threshold = m.select_threshold([0, 1], [0.5, 0.5])["threshold"]
    result = m.binary_metrics([0, 1], [0.5, 0.5], threshold)
    assert result["roc_auc"] == 0.5 and result["tss"] == result["mcc"] == 0
    source = m.source_specificity([0, 1], ["survey_supported_absence", "presence"], [0.5, 0.5], threshold)
    assert source["pseudoabsence"]["specificity"] is None
    assert source["pseudoabsence"]["denominator"] == 0


def test_source_class_mismatch_rejected():
    with pytest.raises(ValueError, match="source/class"):
        m.source_specificity([1, 0], ["pseudoabsence", "presence"], [0.5, 0.5], 0.5)
    with pytest.raises(ValueError, match="nonfinite threshold"):
        m.source_specificity([0, 1], ["survey_supported_absence", "presence"], [0.5, 0.5], np.nan)


def test_map_tie_boundary_is_canonical_id_and_permutation_invariant():
    ids = np.array(["d", "b", "a", "c"])
    before = np.array([0.1, 0.7, 0.7, 0.7])
    after = np.array([0.1, 0.6, 0.5, 0.9])
    result = m.map_summary(ids, before, after, top_count=2, expected_cells=4)
    assert result["top_decile_intersection"] == 1
    reorder = np.array([3, 0, 2, 1])
    assert result == m.map_summary(ids[reorder], before[reorder], after[reorder], top_count=2, expected_cells=4)


def test_unchanged_map_and_duplicate_identity():
    cells = ["a", "b", "c"]
    values = [0.1, 0.1, 0.9]
    row = m.map_summary(cells, values, values, top_count=1, expected_cells=3)
    assert row["top_decile_retention"] == 1 and row["spearman_rho"] == 1
    assert row["rank_displacement_q975_percentile_points"] == 0
    with pytest.raises(ValueError, match="identity"):
        m.map_summary(["a", "a", "c"], values, values, top_count=1, expected_cells=3)


def test_threshold_refuses_single_class():
    with pytest.raises(ValueError, match="both classes"):
        m.select_threshold([0, 0], [0.1, 0.9])
