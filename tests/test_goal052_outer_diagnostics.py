import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from dsdm_phase1.goal052_outer_diagnostics import (
    evaluate_richness_diagnostics,
    fixed_probability_ensemble,
)


def test_sparse_bins_keep_identity_and_positives_below_ten():
    # Includes ties, a sparse first bin, an empty middle bin, and presences
    # below the background richness threshold. All remain in the identity.
    y = np.array([1, 1, 0, 0, 0])
    richness = np.array([0, 120, 12, 100, 150])
    score = np.array([0.5, 0.8, 0.5, 0.3, 0.9])
    result = evaluate_richness_diagnostics(y, {"arm": score}, richness, np.arange(5))
    assert result["background_strata"]["25_99"]["background_cells"] == 0
    assert result["background_strata"]["10_24"]["presence_cells"] == 2
    assert all(item["auc"]["arm"] is None for item in result["background_strata"].values())
    identity = result["weighted_auc_identity"]["arm"]
    assert identity["full_x10_auc"] == roc_auc_score(y, score)
    assert identity["absolute_error"] < 1e-12


def test_high_richness_restricts_both_classes_and_twenty_is_inclusive():
    y = np.r_[np.ones(40), np.zeros(60)]
    richness = np.r_[np.repeat(5, 20), np.repeat(100, 20),
                     np.repeat(10, 20), np.repeat(25, 20), np.repeat(100, 20)]
    score = np.linspace(0, 1, len(y))
    result = evaluate_richness_diagnostics(y, {"arm": score}, richness, np.arange(100) // 10)
    high = result["high_recording_richness_subset"]
    mask = richness >= 100
    assert high["presence_cells"] == high["background_cells"] == 20
    assert high["presence_tiles"] == high["background_tiles"] == 2
    assert high["reportable"] is True
    assert high["auc"]["arm"] == roc_auc_score(y[mask], score[mask])
    assert all(item["presence_cells"] == 40 for item in result["background_strata"].values())


@pytest.mark.parametrize("fault", ["missing_class", "outside_x10", "nonfinite", "misaligned", "fractional_richness"])
def test_invalid_primary_data_fail_instead_of_becoming_diagnostic_na(fault):
    y = np.array([1, 1, 0, 0])
    richness = np.array([0., 100., 10., 100.])
    score = np.array([0.9, 0.7, 0.2, 0.4])
    if fault == "missing_class":
        y[:] = 1
    elif fault == "outside_x10":
        richness[2] = 9
    elif fault == "nonfinite":
        score[2] = np.nan
    elif fault == "misaligned":
        score = score[:-1]
    else:
        richness[2] = 10.5
    with pytest.raises(ValueError):
        evaluate_richness_diagnostics(y, {"arm": score}, richness, np.arange(4))


def test_ensemble_uses_probabilities_and_rejects_invalid_component():
    ft, conv = np.array([0.1, 0.8]), np.array([0.5, 0.6])
    np.testing.assert_array_equal(fixed_probability_ensemble(ft, conv), [0.3, 0.7])
    with pytest.raises(ValueError):
        fixed_probability_ensemble(ft, np.array([0.5]))
    with pytest.raises(ValueError):
        fixed_probability_ensemble(ft, np.array([0.5, np.nan]))
