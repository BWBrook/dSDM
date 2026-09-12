from __future__ import annotations

import numpy as np
import pytest

from dsdm_phase1.goal052_design import endpoint_grid
from dsdm_phase1.goal052_results import (
    ARMS,
    PRIMARY_CONTRASTS,
    seed_average_folds,
    summarize_condition,
    summarize_panels,
)
from dsdm_phase1.mainland_modeling import summarize_oof


def _seed_rows(scores_by_fold):
    rows = []
    for fold, scores in enumerate(scores_by_fold):
        rows.append({
            "fold": fold,
            "cell_id": (f"cell-{fold}-0", f"cell-{fold}-1"),
            "y": np.asarray([0, 1], dtype=np.int8),
            "score": np.asarray(scores, dtype=np.float64),
        })
    return rows


def _five_seeds(scores_by_fold):
    return {f"seed{seed:02d}": _seed_rows(scores_by_fold) for seed in range(5)}


def _identity_folds(scores_by_fold):
    return seed_average_folds(_five_seeds(scores_by_fold))


def test_seed_average_is_float64_first_and_preserves_fold_rows():
    seed_scores = (
        ([0.2, 0.8], [0.4, 0.6], [0.6, 0.4], [0.8, 0.2], [0.4, 0.6])
    )
    rows = {
        f"seed{seed:02d}": _seed_rows([
            seed_scores[seed]
            for _ in range(5)
        ])
        for seed in range(5)
    }
    averaged = seed_average_folds(rows)

    assert [row["fold"] for row in averaged] == list(range(5))
    assert averaged[0]["cell_id"] == ("cell-0-0", "cell-0-1")
    np.testing.assert_array_equal(averaged[0]["y"], [0, 1])
    np.testing.assert_allclose(averaged[0]["score"], [0.48, 0.52])
    assert averaged[0]["score"].dtype == np.float64
    summary = summarize_oof(averaged)
    assert summary["mean_fold_roc_auc"] == 1.0
    assert summary["pooled"]["tss"] == 1.0
    # Averaging each seed's nonlinear AUC would give 0.6; averaging scores
    # first correctly gives perfect ordering and AUC 1.
    assert np.mean(
        [summarize_oof(seed_rows)["mean_fold_roc_auc"] for seed_rows in rows.values()]
    ) == pytest.approx(0.6)


@pytest.mark.parametrize("mutation", ["missing_seed", "cell_order", "label_order", "nonfinite"])
def test_seed_average_rejects_missing_or_misaligned_predictions(mutation):
    rows = _five_seeds([([0.2, 0.8]) for _ in range(5)])
    if mutation == "missing_seed":
        del rows["seed04"]
    elif mutation == "cell_order":
        rows["seed01"][0]["cell_id"] = ("cell-0-1", "cell-0-0")
    elif mutation == "label_order":
        rows["seed01"][0]["y"] = np.asarray([1, 0], dtype=np.int8)
    else:
        rows["seed01"][0]["score"][0] = np.nan

    with pytest.raises(ValueError):
        seed_average_folds(rows)


def test_summarize_condition_reports_paired_primary_and_mechanistic_contrasts():
    target_scores = [([0.2, 0.8] if fold else [0.8, 0.2]) for fold in range(5)]
    q_scores = [([0.1, 0.9]) for _ in range(5)]
    frozen_scores = [([0.15, 0.85]) for _ in range(5)]
    full_scores = [([0.05, 0.95]) for _ in range(5)]
    arm_folds = {
        "target_only_random_init_resmlp": _identity_folds(target_scores),
        "target_plus_q_linear_resmlp": _identity_folds(q_scores),
        "multihead_frozen_trunk": _identity_folds(frozen_scores),
        "multihead_full_finetune": _identity_folds(full_scores),
    }
    conventional = summarize_oof(_identity_folds([([0.25, 0.75]) for _ in range(5)]))
    q_conventional = summarize_oof(_identity_folds([([0.3, 0.7]) for _ in range(5)]))

    result = summarize_condition("target", 100, "full", arm_folds, conventional, q_conventional, True)

    assert set(result["arm_metrics"]) == set(ARMS)
    assert set(result["primary_contrasts"]) == set(PRIMARY_CONTRASTS)
    assert set(result["mechanistic_contrasts"]) == {
        "multihead_frozen_trunk_minus_target_only_random_init_resmlp",
        "multihead_full_finetune_minus_multihead_frozen_trunk",
    }
    full = result["arm_metrics"]["multihead_full_finetune"]
    target = result["arm_metrics"]["target_only_random_init_resmlp"]
    contrast = result["primary_contrasts"]["multihead_full_finetune_minus_target_only_random_init_resmlp"]
    assert contrast["delta_mean_fold_roc_auc"] == pytest.approx(full["mean_fold_roc_auc"] - target["mean_fold_roc_auc"])
    assert contrast["per_fold"][0]["delta_roc_auc"] == pytest.approx(1.0)
    assert full["pooled"]["tp"] == 5
    assert full["pooled"]["tn"] == 5
    assert result["selection_target"] is True
    assert "p_value" not in result


def test_summarize_condition_rejects_missing_arm_and_misaligned_arm_rows():
    folds = _identity_folds([([0.2, 0.8]) for _ in range(5)])
    arms = {arm: folds for arm in ARMS}
    conventional = summarize_oof(folds)
    del arms["multihead_frozen_trunk"]
    with pytest.raises(ValueError, match="arm_inventory"):
        summarize_condition("target", 100, "full", arms, conventional, conventional, False)

    arms = {arm: _identity_folds([([0.2, 0.8]) for _ in range(5)]) for arm in ARMS}
    arms["multihead_full_finetune"][0]["cell_id"] = ("wrong", "cells")
    with pytest.raises(ValueError, match="arm_cell_alignment"):
        summarize_condition("target", 100, "full", arms, conventional, conventional, False)


def test_summarize_panels_enforces_frozen_inventory_and_reports_equal_target_descriptives():
    primary = tuple(f"target-{i:03d}" for i in range(73))
    focal = tuple(f"target-{i:03d}" for i in range(157))
    template = {
        "primary_contrasts": {
            name: {
                "delta_mean_fold_roc_auc": 0.01,
                "delta_mean_fold_tss": 0.02,
            }
            for name in PRIMARY_CONTRASTS
        }
    }
    conditions = [
        {**template, "target": target, "fraction": fraction, "auxiliary": auxiliary}
        for target, fraction, auxiliary in endpoint_grid(primary, focal)
    ]
    result = summarize_panels(conditions, primary)

    assert set(result["panels"]) == {
        "all157_100_full",
        "primary73_100_full",
        "nonselection84_100_full",
        "primary25_full_aux",
        "primary50_full_aux",
        "primary100_aux20",
        "primary100_aux80",
    }
    assert result["panels"]["all157_100_full"]["target_count"] == 157
    assert result["panels"]["primary73_100_full"]["target_count"] == 73
    assert result["panels"]["nonselection84_100_full"]["target_count"] == 84
    metric = result["panels"]["primary100_aux20"]["contrasts"][next(iter(PRIMARY_CONTRASTS))]
    assert metric["delta_mean_fold_roc_auc"]["mean"] == pytest.approx(0.01)
    assert metric["delta_mean_fold_roc_auc"]["sd"] == pytest.approx(0.0)
    assert "p_value" not in str(result)
