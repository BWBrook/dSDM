from __future__ import annotations

import numpy as np
import pytest

from dsdm_phase1.goal052_outer_scoring import (
    ALL_ARMS,
    EXISTING_ARMS,
    aggregate_regions,
    matched_inner_attenuation,
    score_target_region,
)


def _scores(n: int, shift: float = 0.0) -> dict[str, np.ndarray]:
    base = np.linspace(0.05, 0.95, n, dtype=np.float64)
    values = {
        "target_only_random_init_resmlp": np.clip(base + shift, 0, 1),
        "target_plus_q_linear_resmlp": np.clip(base + 0.01 + shift, 0, 1),
        "multihead_frozen_trunk": np.clip(base + 0.02 + shift, 0, 1),
        "multihead_full_finetune": np.clip(base + 0.03 + shift, 0, 1),
        "selected_conventional": np.clip(base + 0.04 + shift, 0, 1),
        "selected_conventional_plus_q": np.clip(base + 0.05 + shift, 0, 1),
    }
    values["fixed_ensemble"] = 0.5 * (
        values["multihead_full_finetune"] + values["selected_conventional"]
    )
    return values


def _thresholds() -> dict[str, float]:
    return {name: 0.5 for name in EXISTING_ARMS}


def _large_case(target: str = "sp", region: str = "NCP", shift: float = 0.0):
    # Forty presences and 120 backgrounds.  The background bins are 40 cells
    # each; twenty presences and forty backgrounds are in the >=100 subset.
    y = np.r_[np.ones(40, dtype=np.int8), np.zeros(120, dtype=np.int8)]
    richness = np.r_[np.r_[np.repeat(5, 20), np.repeat(100, 20)],
                     np.repeat([10, 25, 100], 40)]
    blocks = np.tile(np.arange(4), 40)
    return score_target_region(
        target, region, y, richness, blocks, _scores(len(y), shift), _thresholds(),
        primary=True, regional=True,
    )


def test_scoring_preserves_x10_presences_and_reports_expected_x20_na():
    result = _large_case()

    assert result["masks"]["x10"]["presence_cells"] == 40
    assert result["masks"]["x10"]["background_cells"] == 120
    assert result["masks"]["x20"]["presence_cells"] == 40
    assert result["masks"]["x20"]["background_cells"] == 80
    assert result["support"]["x10"]["passes"] is True
    assert result["support"]["x20"]["passes"] is False
    assert result["x20"]["metrics"]["multihead_full_finetune"]["roc_auc"] is None
    assert result["x20"]["metrics"]["multihead_full_finetune"]["na_reason"] == "x20_support_failure"
    assert result["x10"]["metrics"]["multihead_full_finetune"]["threshold"] == 0.5
    assert result["x10"]["metrics"]["multihead_full_finetune"]["roc_auc"] is not None
    assert set(result["x10"]["metrics"]["fixed_ensemble"]) == {
        "n", "n_positive", "n_negative", "roc_auc", "auc", "na_reason"
    }
    assert result["richness"]["weighted_auc_identity"]["fixed_ensemble"]["absolute_error"] <= 1e-12
    assert result["richness"]["high_recording_richness_subset"]["reportable"] is True
    assert result["background_composition"]["background_cells_total"] == 120


def test_x10_support_failure_is_visible_and_does_not_delete_cells():
    y = np.r_[np.ones(2, dtype=np.int8), np.zeros(3, dtype=np.int8)]
    richness = np.r_[np.zeros(2), np.repeat(10, 3)]
    result = score_target_region(
        "s", "R", y, richness, np.arange(5), _scores(5), _thresholds(),
        primary=True, regional=False,
    )
    assert result["x10"]["support"]["passes"] is False
    assert "fewer_than_30_presences" in result["x10"]["support"]["failure_reasons"]
    assert result["x10"]["metrics"]["multihead_full_finetune"]["n"] == 5
    assert result["x10"]["metrics"]["multihead_full_finetune"]["roc_auc"] is not None


def test_ensemble_is_validated_and_thresholds_are_not_applied_to_it():
    result = _large_case()
    assert "threshold" not in result["x10"]["metrics"]["fixed_ensemble"]
    bad = _scores(160)
    bad["fixed_ensemble"] = bad["fixed_ensemble"].copy()
    bad["fixed_ensemble"][0] += 1e-6
    with pytest.raises(ValueError, match="fixed_ensemble_mismatch"):
        score_target_region(
            "sp", "NCP", np.r_[np.ones(40), np.zeros(120)],
            np.r_[np.repeat(5, 20), np.repeat(100, 20), np.repeat([10, 25, 100], 40)],
            np.tile(np.arange(4), 40), bad, _thresholds(), primary=True, regional=True,
        )


def _small_case(target: str, region: str, shift: float):
    y = np.array([1, 1, 0, 0, 0, 0], dtype=np.int8)
    richness = np.array([0, 0, 10, 25, 100, 100], dtype=np.int64)
    return score_target_region(
        target, region, y, richness, np.arange(6), _scores(6, shift), _thresholds(),
        primary=target in {"a", "b"}, regional=True,
    )


def test_aggregate_uses_equal_target_and_region_weights_and_keeps_membership():
    results = []
    for region, targets in {"R1": ["a", "b", "c"], "R2": ["a", "b", "c", "d"]}.items():
        for index, target in enumerate(targets):
            results.append(_small_case(target, region, index * 0.01))
    aggregated = aggregate_regions(results, ["a", "b"], {"R1": ["a", "b", "c"], "R2": ["a", "b", "c", "d"]})

    assert aggregated["regional"]["R1"]["target_count"] == 3
    assert aggregated["regional"]["R2"]["target_count"] == 4
    assert aggregated["common"]["target_count"] == 2
    contrast = "multihead_full_finetune_minus_target_only_random_init_resmlp"
    assert aggregated["regional"]["R1"]["contrasts"][contrast]["denominator"] == 3
    assert aggregated["regional"]["R2"]["contrasts"][contrast]["denominator"] == 4
    assert aggregated["common"]["contrasts"][contrast]["denominator"] == 2
    assert aggregated["background_composition"]["R2"]["target_count"] == 4


def test_aggregate_missing_target_region_is_an_error():
    result = _small_case("a", "R1", 0)
    with pytest.raises(ValueError, match="missing_target_region_result"):
        aggregate_regions([result], ["a"], {"R1": ["a"], "R2": ["a"]})


def test_reportable_richness_contrasts_reach_regional_and_macro_summaries():
    results = [_large_case(target, region) for region in ("NCP", "SEH", "NNC") for target in ("a", "b")]
    summary = aggregate_regions(results, ["a"], {region: ["a", "b"] for region in ("NCP", "SEH", "NNC")})
    contrast = "multihead_full_finetune_minus_target_only_random_init_resmlp"
    for item in results:
        for label in ("10_24", "25_99", "100_plus"):
            assert item["richness"]["background_strata"][label]["contrasts"][contrast] == 0.0
    for label in ("10_24", "25_99", "100_plus"):
        assert summary["richness"]["regional"]["NCP"]["bins"][label]["common_support"][contrast]["denominator"] == 2
        assert summary["richness"]["supplementary_three_region_macro"]["bins"][label]["contrasts"][contrast]["denominator"] == 1
    assert summary["richness"]["regional"]["NCP"]["high_recording_richness_subset"]["contrasts"][contrast]["denominator"] == 2
    assert summary["richness"]["supplementary_three_region_macro"]["high_recording_richness_subset"]["contrasts"][contrast]["denominator"] == 1
    assert summary["primary_by_region"]["NCP"]["target_count"] == 1
    assert summary["primary_background_composition"]["NCP"]["target_count"] == 1
    assert summary["headline_decomposition"]["regional"]["NCP"]["contrasts"][contrast]["absolute_error"] <= 1e-12


def test_headline_decomposition_preserves_within_target_weight_contrast_products():
    cases = []
    for target, counts, flip in (("a", [80, 20, 20], False), ("b", [20, 20, 80], True)):
        y = np.r_[np.ones(40, dtype=np.int8), np.zeros(sum(counts), dtype=np.int8)]
        richness = np.r_[np.repeat(120, 40), np.repeat([10, 25, 100], counts)]
        scores = {arm: np.full(len(y), 0.5, dtype=np.float64) for arm in EXISTING_ARMS}
        full = np.r_[np.full(40, 0.5), np.repeat([0.2, 0.5, 0.8] if not flip else [0.8, 0.5, 0.2], counts)]
        scores["multihead_full_finetune"] = full
        scores["fixed_ensemble"] = .5 * full + .5 * scores["selected_conventional"]
        cases.append(score_target_region(target, "R", y, richness, np.arange(len(y)) % 4, scores, _thresholds(), primary=True, regional=True))
    summary = aggregate_regions(cases, ["a", "b"], {"R": ["a", "b"]})
    contrast = "multihead_full_finetune_minus_target_only_random_init_resmlp"
    decomposition = summary["headline_decomposition"]["regional"]["R"]["contrasts"][contrast]
    assert decomposition["sum"] == pytest.approx(.25)
    assert summary["regional"]["R"]["contrasts"][contrast]["mean"] == pytest.approx(.25)
    # Marginal means of both bin contrasts are zero, although the headline is
    # positive because each target's easier bin has the larger weight.
    wrong = sum(summary["background_composition"]["R"]["bins"][label]["mean_target_share"] *
                summary["richness"]["regional"]["R"]["bins"][label]["all_available"][contrast]["mean"]
                for label in ("10_24", "25_99", "100_plus"))
    assert wrong == pytest.approx(0.0)


def test_x20_macro_uses_region_specific_denominators_and_attenuation_matches_members():
    from dsdm_phase1.goal052_outer_scoring import PRIMARY_CONTRASTS, MECHANISTIC_CONTRASTS
    results = [_large_case(target, region) for region in ("NCP", "SEH", "NNC") for target in ("a", "b")]
    # Start from real scored objects, then prescribe simple X20 diagnostic
    # contrasts to isolate the aggregation arithmetic and one expected NA.
    contrast = "multihead_full_finetune_minus_target_only_random_init_resmlp"
    for item in results:
        value = None if (item["region"], item["target"]) == ("NCP", "b") else (0.2 if item["target"] == "a" else .8)
        item["x20"]["contrasts"][contrast] = value
    summary = aggregate_regions(results, ["a", "b"], {region: ["a", "b"] for region in ("NCP", "SEH", "NNC")})
    macro = summary["x20"]["common_equal_region_macro"]["contrasts"][contrast]
    assert macro["regional_denominators"] == {"NCP": 1, "SEH": 2, "NNC": 2}
    assert macro["mean"] == pytest.approx(.4)
    assert summary["x20"]["common_three_region_intersection"]["contrasts"][contrast]["mean"] == pytest.approx(.2)
    inner = {"conditions": [{"target": target, "fraction": 100, "auxiliary": "full",
        "primary_contrasts": {name: {"delta_mean_fold_roc_auc": value} for name in PRIMARY_CONTRASTS},
        "mechanistic_contrasts": {name: {"delta_mean_fold_roc_auc": value} for name in MECHANISTIC_CONTRASTS},
    } for target, value in (("a", .1), ("b", .3))]}
    attenuation = matched_inner_attenuation(summary, inner)
    assert attenuation["common_equal_region_macro"][contrast]["inner_mean_difference"] == pytest.approx(.2)
    assert attenuation["common_equal_region_macro"][contrast]["outer_minus_inner"] == pytest.approx(-.2)
