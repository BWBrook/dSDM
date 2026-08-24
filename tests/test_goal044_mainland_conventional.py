from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dsdm_phase1.mainland_modeling import (
    EncodedFeatures,
    ResponseRows,
    binary_metrics,
    endpoint_indices,
    fit_q_linear,
    hierarchical_indices,
    make_batch,
    select_threshold,
    summarize_oof,
)


ROOT = Path(__file__).resolve().parents[1]


def _rows(n_per_stratum: int = 10) -> ResponseRows:
    cells, y, folds = [], [], []
    for response in (0, 1):
        for fold in range(5):
            for index in range(n_per_stratum):
                cells.append(f"c_{response}_{fold}_{index:02d}")
                y.append(response)
                folds.append(fold)
    return ResponseRows(tuple(cells), np.asarray(y), np.asarray(folds))


def test_target_ladders_are_deterministic_nested_and_prevalence_preserving():
    rows = _rows()
    first = hierarchical_indices(rows, "ladder00", "seed")
    second = hierarchical_indices(rows, "ladder00", "seed")
    assert np.array_equal(first, second)
    assert set(first.tolist()) == set(range(len(rows.cell_ids)))

    i25 = endpoint_indices(rows, 25, "ladder00", "seed")
    i50 = endpoint_indices(rows, 50, "ladder00", "seed")
    i100 = endpoint_indices(rows, 100, "ladder00", "seed")
    assert len(i25) == 25
    assert len(i50) == 50
    assert len(i100) == 100
    assert set(i25) < set(i50) < set(i100)
    assert rows.y[i25].sum() in {12, 13}
    assert rows.y[i50].sum() == 25


def test_threshold_and_oof_metrics_are_consistent():
    folds = []
    for fold in range(5):
        y = np.asarray([0, 0, 1, 1], dtype=np.int8)
        score = np.asarray([0.1, 0.3, 0.7, 0.9], dtype=np.float64) + fold * 1e-4
        folds.append({"fold": fold, "y": y, "score": score})
    summary = summarize_oof(folds)
    assert summary["mean_fold_roc_auc"] == 1.0
    assert summary["pooled"]["tss"] == 1.0
    assert summary["pooled"]["mcc"] == 1.0
    threshold = select_threshold(
        np.concatenate([fold["y"] for fold in folds]),
        np.concatenate([fold["score"] for fold in folds]),
    )
    assert threshold == summary["threshold"]
    assert binary_metrics([0, 1], [0.1, 0.9], 0.5)["balanced_accuracy"] == 1.0


def test_q_feature_is_continuous_and_precedes_categorical_columns():
    rows = ResponseRows(("a", "b"), np.asarray([0, 1]), np.asarray([1, 2]))
    features = EncodedFeatures(
        np.asarray([[0.2, 0.0, 1.0], [0.8, 1.0, 0.0]]),
        ("q_linear", "land=a", "land=b"),
        ("continuous", "categorical", "categorical"),
        1,
        "fold00",
        "a" * 64,
        "b" * 64,
    )
    batch = make_batch("target", rows, features)
    assert batch.continuous_count == 1
    assert batch.feature_names[0] == "q_linear"
    assert batch.feature_kinds == ("continuous", "categorical", "categorical")


class _FakeStore:
    def __init__(self, heads):
        self.heads = heads

    def response_rows(self, target, held_fold, role):
        prefix = f"{target.replace(' ', '_')}_{role}"
        cells = tuple(f"{prefix}_{i}" for i in range(6))
        return ResponseRows(cells, np.asarray([0, 0, 0, 1, 1, 1]), np.asarray([1] * 6))

    def encoded(self, cells, held_fold, q_scores=None):
        x = []
        for index, cell in enumerate(cells):
            response_hint = 1.0 if int(cell.rsplit("_", 1)[1]) >= 3 else 0.0
            x.append([response_hint, (index % 3) / 2])
        return EncodedFeatures(
            np.asarray(x, dtype=np.float64),
            ("x1", "x2"),
            ("continuous", "continuous"),
            2,
            f"fold{held_fold:02d}",
            "c" * 64,
            "d" * 64,
        )


def test_q_linear_excludes_target_and_equalizes_head_totals():
    config = json.loads((ROOT / "config/goal044_mainland_conventional.json").read_text())
    target = config["scope"]["targets"][0]
    scores, receipt = fit_q_linear(_FakeStore(config["scope"]["response_heads"]), config, target, 0)
    assert target not in receipt["auxiliary_heads"]
    assert receipt["auxiliary_head_count"] == 19
    assert receipt["within_head_class_balancing"] is False
    assert np.isclose(receipt["head_total_weight_range"][0], receipt["head_total_weight_range"][1])
    assert len(scores) == 12
    assert all(0 <= value <= 1 for value in scores.values())


def test_goal044_freezes_goal045_but_forbids_dsdm_and_tasmania_work():
    config = json.loads((ROOT / "config/goal044_mainland_conventional.json").read_text())
    frozen = config["goal045_frozen_design"]
    assert frozen["status"] == "prespecified_before_goal044_results"
    assert len(frozen["architecture_candidates"]) == 3
    assert frozen["pretraining_heads"] == "exact_other_19"
    assert frozen["target_excluded_from_pretraining"] is True
    assert frozen["within_head_class_balancing"] is False
    assert "dsdm_model_fitting" in config["stopping_boundary"]
    assert "tasmania_evaluation_access" in config["stopping_boundary"]
    source = (ROOT / "src/dsdm_phase1/goal044_mainland_conventional.py").read_text()
    assert "tasmania_evaluation_response" not in source
