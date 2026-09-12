"""Pure Goal 052 OOF aggregation and descriptive panel summaries."""

from __future__ import annotations

from numbers import Integral, Real
from typing import Any, Mapping, Sequence

import numpy as np

from .goal052_design import endpoint_grid
from .mainland_modeling import summarize_oof


ARMS = (
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
)
SEEDS = tuple(f"seed{i:02d}" for i in range(5))
FOLDS = tuple(range(5))
PRIMARY_CONTRASTS = {
    "multihead_full_finetune_minus_target_only_random_init_resmlp": "target_only_random_init_resmlp",
    "multihead_full_finetune_minus_target_plus_q_linear_resmlp": "target_plus_q_linear_resmlp",
    "multihead_full_finetune_minus_goal051_selected_conventional": "selected_conventional",
    "multihead_full_finetune_minus_goal051_q_augmented_conventional": "q_conventional",
}
MECHANISTIC_CONTRASTS = {
    "multihead_frozen_trunk_minus_target_only_random_init_resmlp": (
        "multihead_frozen_trunk",
        "target_only_random_init_resmlp",
    ),
    "multihead_full_finetune_minus_multihead_frozen_trunk": (
        "multihead_full_finetune",
        "multihead_frozen_trunk",
    ),
}
POOLED_SUPPLEMENTARY = ("balanced_accuracy", "mcc", "sensitivity", "specificity", "prevalence")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite_scores(values: Any, name: str) -> np.ndarray:
    scores = np.asarray(values, dtype=np.float64)
    _require(scores.ndim == 1 and len(scores) > 0, f"{name}_invalid")
    _require(
        np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)),
        f"{name}_invalid",
    )
    return scores


def _labels(values: Any, name: str) -> np.ndarray:
    labels = np.asarray(values)
    _require(
        labels.ndim == 1 and len(labels) > 0 and np.isin(labels, (0, 1)).all(),
        f"{name}_invalid",
    )
    return labels.astype(np.int8, copy=False)


def _cell_ids(values: Any, name: str) -> tuple[Any, ...]:
    try:
        cells = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name}_invalid") from exc
    _require(len(cells) > 0, f"{name}_invalid")
    return cells


def _fold_rows(folds: Sequence[Mapping[str, Any]], name: str) -> list[dict[str, Any]]:
    _require(
        isinstance(folds, Sequence) and not isinstance(folds, (str, bytes)),
        f"{name}_invalid",
    )
    _require(len(folds) == 5, f"{name}_fold_count_invalid")
    rows: list[dict[str, Any]] = []
    observed: list[int] = []
    for position, row in enumerate(folds):
        _require(isinstance(row, Mapping), f"{name}_fold_invalid")
        _require("fold" in row, f"{name}_fold_id_missing")
        fold = row["fold"]
        _require(
            isinstance(fold, Integral) and not isinstance(fold, bool),
            f"{name}_fold_id_invalid",
        )
        fold = int(fold)
        observed.append(fold)
        labels = _labels(row.get("y"), f"{name}_y")
        scores = _finite_scores(row.get("score"), f"{name}_score")
        cells = _cell_ids(row.get("cell_id"), f"{name}_cell_id")
        _require(len(labels) == len(scores) == len(cells), f"{name}_row_alignment_invalid")
        rows.append({"fold": fold, "y": labels, "score": scores, "cell_id": cells})
    _require(observed == list(FOLDS), f"{name}_fold_inventory_invalid")
    return rows


def seed_average_folds(
    seed_folds: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Average five paired seed predictions after validating row identity."""

    _require(isinstance(seed_folds, Mapping) and set(seed_folds) == set(SEEDS), "seed_inventory_invalid")
    validated = {seed: _fold_rows(seed_folds[seed], seed) for seed in SEEDS}
    averaged: list[dict[str, Any]] = []
    for fold_index in FOLDS:
        reference = validated[SEEDS[0]][fold_index]
        scores = []
        for seed in SEEDS:
            row = validated[seed][fold_index]
            _require(row["fold"] == reference["fold"], "seed_fold_alignment_invalid")
            _require(row["cell_id"] == reference["cell_id"], "seed_cell_alignment_invalid")
            _require(np.array_equal(row["y"], reference["y"]), "seed_label_alignment_invalid")
            scores.append(row["score"])
        mean_score = np.mean(
            np.stack(scores, axis=0, dtype=np.float64), axis=0, dtype=np.float64
        )
        _require(np.isfinite(mean_score).all(), "averaged_score_nonfinite")
        averaged.append({
            "fold": reference["fold"],
            "y": reference["y"].copy(),
            "score": mean_score.astype(np.float64, copy=False),
            "cell_id": reference["cell_id"],
        })
    return averaged


def _validate_summary(summary: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    _require(isinstance(summary, Mapping), f"{name}_invalid")
    for field in ("mean_fold_roc_auc", "mean_fold_tss"):
        value = summary.get(field)
        _require(
            isinstance(value, Real)
            and not isinstance(value, bool)
            and np.isfinite(float(value)),
            f"{name}_{field}_invalid",
        )
    pooled = summary.get("pooled")
    _require(isinstance(pooled, Mapping), f"{name}_pooled_invalid")
    for field in ("roc_auc", "tss", *POOLED_SUPPLEMENTARY):
        if field in pooled:
            value = pooled[field]
            _require(
                isinstance(value, Real)
                and not isinstance(value, bool)
                and np.isfinite(float(value)),
                f"{name}_pooled_{field}_invalid",
            )
    return summary


def _contrast(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left = _validate_summary(left, "left_metric")
    right = _validate_summary(right, "right_metric")
    pooled_left, pooled_right = left["pooled"], right["pooled"]
    pooled_delta = {
        field: float(pooled_left[field]) - float(pooled_right[field])
        for field in ("roc_auc", "tss", *POOLED_SUPPLEMENTARY)
        if field in pooled_left and field in pooled_right
    }
    result: dict[str, Any] = {
        "delta_mean_fold_roc_auc": float(left["mean_fold_roc_auc"]) - float(right["mean_fold_roc_auc"]),
        "delta_mean_fold_tss": float(left["mean_fold_tss"]) - float(right["mean_fold_tss"]),
        "delta_pooled_metrics": pooled_delta,
        "delta_pooled_supplementary": {
            field: pooled_delta[field]
            for field in POOLED_SUPPLEMENTARY
            if field in pooled_delta
        },
    }
    left_folds, right_folds = left.get("folds"), right.get("folds")
    if (
        isinstance(left_folds, Sequence)
        and isinstance(right_folds, Sequence)
        and len(left_folds) == len(right_folds) == 5
    ):
        per_fold = []
        for left_fold, right_fold in zip(left_folds, right_folds):
            _require(left_fold.get("fold") == right_fold.get("fold"), "contrast_fold_alignment_invalid")
            per_fold.append({
                "fold": int(left_fold["fold"]),
                "delta_roc_auc": float(left_fold["roc_auc"]) - float(right_fold["roc_auc"]),
                "delta_tss": float(left_fold["tss"]) - float(right_fold["tss"]),
            })
        result["per_fold"] = per_fold
    return result


def summarize_condition(
    target: str,
    fraction: int,
    auxiliary: str,
    arm_folds: Mapping[str, Sequence[Mapping[str, Any]]],
    conventional_metrics: Mapping[str, Any],
    q_metrics: Mapping[str, Any],
    selection_target: bool,
) -> dict[str, Any]:
    """Summarize one condition and its prespecified descriptive contrasts."""

    _require(isinstance(target, str) and target, "condition_target_invalid")
    _require(fraction in (25, 50, 100) and auxiliary in ("20", "80", "full"), "condition_endpoint_invalid")
    _require(isinstance(arm_folds, Mapping) and set(arm_folds) == set(ARMS), "arm_inventory_invalid")
    arms: dict[str, dict[str, Any]] = {}
    reference_cells: list[tuple[Any, ...]] | None = None
    reference_y: list[np.ndarray] | None = None
    for arm in ARMS:
        rows = _fold_rows(arm_folds[arm], arm)
        if reference_cells is None:
            reference_cells = [row["cell_id"] for row in rows]
            reference_y = [row["y"] for row in rows]
        else:
            _require([row["cell_id"] for row in rows] == reference_cells, "arm_cell_alignment_invalid")
            _require(
                all(
                    np.array_equal(row["y"], expected)
                    for row, expected in zip(rows, reference_y)
                ),
                "arm_label_alignment_invalid",
            )
        arms[arm] = summarize_oof(rows)
    conventional = _validate_summary(conventional_metrics, "conventional_metrics")
    q_summary = _validate_summary(q_metrics, "q_metrics")
    full = arms["multihead_full_finetune"]
    comparator_summaries = {
        "target_only_random_init_resmlp": arms["target_only_random_init_resmlp"],
        "target_plus_q_linear_resmlp": arms["target_plus_q_linear_resmlp"],
        "selected_conventional": conventional,
        "q_conventional": q_summary,
    }
    primary = {
        name: _contrast(full, comparator_summaries[comparator])
        for name, comparator in PRIMARY_CONTRASTS.items()
    }
    mechanistic = {
        name: _contrast(arms[left], arms[right])
        for name, (left, right) in MECHANISTIC_CONTRASTS.items()
    }
    return {
        "target": target,
        "fraction": fraction,
        "auxiliary": auxiliary,
        "selection_target": bool(selection_target),
        "arm_metrics": arms,
        "arms": arms,
        "conventional_metrics": conventional,
        "q_metrics": q_summary,
        "primary_contrasts": primary,
        "mechanistic_contrasts": mechanistic,
    }


def _panel_summary(rows: Sequence[Mapping[str, Any]], contrast_names: Sequence[str]) -> dict[str, Any]:
    targets = [str(row["target"]) for row in rows]
    contrasts: dict[str, Any] = {}
    for name in contrast_names:
        values = {
            "delta_mean_fold_roc_auc": [
                float(row["primary_contrasts"][name]["delta_mean_fold_roc_auc"])
                for row in rows
            ],
            "delta_mean_fold_tss": [float(row["primary_contrasts"][name]["delta_mean_fold_tss"]) for row in rows],
        }
        contrasts[name] = {
            field: {
                "mean": float(np.mean(items)),
                "sd": float(np.std(items, ddof=1)) if len(items) > 1 else 0.0,
                "values": items,
            }
            for field, items in values.items()
        }
    return {"target_count": len(rows), "targets": targets, "contrasts": contrasts}


def summarize_panels(
    conditions: Sequence[Mapping[str, Any]], primary_targets: Sequence[str]
) -> dict[str, Any]:
    """Aggregate prespecified equal-target panels with means and descriptive SDs."""

    _require(isinstance(conditions, Sequence) and not isinstance(conditions, (str, bytes)), "conditions_invalid")
    primary = tuple(primary_targets)
    _require(len(primary) == 73 and len(set(primary)) == 73, "primary_target_inventory_invalid")
    by_identity: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for condition in conditions:
        _require(isinstance(condition, Mapping), "condition_invalid")
        identity = (condition.get("target"), condition.get("fraction"), condition.get("auxiliary"))
        _require(identity not in by_identity, "condition_duplicate")
        by_identity[identity] = condition
    focal = tuple(dict.fromkeys(identity[0] for identity in by_identity))
    expected = endpoint_grid(primary, focal)
    _require(set(by_identity) == set(expected) and len(by_identity) == len(expected), "condition_inventory_invalid")
    names = tuple(PRIMARY_CONTRASTS)
    primary_set = set(primary)
    panel_specs = {
        "all157_100_full": {(target, 100, "full") for target in focal},
        "primary73_100_full": {(target, 100, "full") for target in primary},
        "nonselection84_100_full": {(target, 100, "full") for target in focal if target not in primary_set},
        "primary25_full_aux": {(target, 25, "full") for target in primary},
        "primary50_full_aux": {(target, 50, "full") for target in primary},
        "primary100_aux20": {(target, 100, "20") for target in primary},
        "primary100_aux80": {(target, 100, "80") for target in primary},
    }
    panels = {
        name: _panel_summary([by_identity[key] for key in expected if key in identities], names)
        for name, identities in panel_specs.items()
    }
    return {"panels": panels, "groups": panels, "primary_contrasts": list(names)}
