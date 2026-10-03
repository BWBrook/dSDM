"""Pure scoring and panel aggregation for the Goal052 outer assessment.

The outer orchestrator owns prediction closure, response access, and panel
membership.  This module accepts only arrays and already closed predictions;
it performs no fitting, file I/O, threshold selection, or target deletion.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from dsdm.inner_evaluation import binary_metrics

from .goal052_outer_diagnostics import (
    BACKGROUND_BINS,
    evaluate_richness_diagnostics,
    summarize_background_composition,
)


NEURAL_ARMS = (
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
)
EXISTING_ARMS = NEURAL_ARMS + (
    "selected_conventional",
    "selected_conventional_plus_q",
)
ALL_ARMS = EXISTING_ARMS + ("fixed_ensemble",)

# ``q_conventional`` is the historical Goal052 source/config spelling.  The
# score-side API uses the explicit name so the fixed ensemble is unambiguous.
ARM_ALIASES = {"q_conventional": "selected_conventional_plus_q"}

PRIMARY_CONTRASTS = {
    "multihead_full_finetune_minus_target_only_random_init_resmlp": (
        "multihead_full_finetune",
        "target_only_random_init_resmlp",
    ),
    "multihead_full_finetune_minus_target_plus_q_linear_resmlp": (
        "multihead_full_finetune",
        "target_plus_q_linear_resmlp",
    ),
    "multihead_full_finetune_minus_goal051_selected_conventional": (
        "multihead_full_finetune",
        "selected_conventional",
    ),
    "multihead_full_finetune_minus_goal051_q_augmented_conventional": (
        "multihead_full_finetune",
        "selected_conventional_plus_q",
    ),
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
ENSEMBLE_CONTRASTS = {
    "fixed_ensemble_minus_multihead_full_finetune": (
        "fixed_ensemble",
        "multihead_full_finetune",
    ),
    "fixed_ensemble_minus_selected_conventional": (
        "fixed_ensemble",
        "selected_conventional",
    ),
}
DEFAULT_CONTRASTS = {**PRIMARY_CONTRASTS, **MECHANISTIC_CONTRASTS, **ENSEMBLE_CONTRASTS}
METRIC_ARMS = frozenset(EXISTING_ARMS)
X10_RICHNESS = 10
X20_RICHNESS = 20
MIN_PRESENCES = 30
MIN_BACKGROUNDS = 100
MIN_ANCHORED_TILES = 4


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _vector(values: Any, name: str, *, dtype: Any = None) -> np.ndarray:
    result = np.asarray(values if dtype is None else values, dtype=dtype)
    _require(result.ndim == 1 and len(result) > 0, f"{name}_invalid")
    return result


def _labels(values: Any) -> np.ndarray:
    raw = _vector(values, "y")
    _require(np.isin(raw, (0, 1)).all(), "y_invalid")
    return raw.astype(np.int8, copy=False)


def _probabilities(values: Any, n: int, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    _require(
        result.ndim == 1 and len(result) == n and np.isfinite(result).all()
        and np.all((result >= 0) & (result <= 1)),
        f"{name}_invalid",
    )
    return result


def _normalise_arms(values: Mapping[str, Any], n: int) -> dict[str, np.ndarray]:
    _require(isinstance(values, Mapping), "scores_invalid")
    source: dict[str, Any] = dict(values)
    for alias, canonical in ARM_ALIASES.items():
        if alias in source:
            _require(canonical not in source, "duplicate_arm_alias")
            source[canonical] = source.pop(alias)
    _require(set(source) == set(ALL_ARMS), "arm_inventory_invalid")
    return {name: _probabilities(source[name], n, f"score_{name}") for name in ALL_ARMS}


def _normalise_thresholds(values: Mapping[str, Any]) -> dict[str, float]:
    _require(isinstance(values, Mapping), "thresholds_invalid")
    source = dict(values)
    for alias, canonical in ARM_ALIASES.items():
        if alias in source:
            _require(canonical not in source, "duplicate_threshold_alias")
            source[canonical] = source.pop(alias)
    _require(set(source) == set(EXISTING_ARMS), "threshold_inventory_invalid")
    result: dict[str, float] = {}
    for name in EXISTING_ARMS:
        value = source[name]
        _require(isinstance(value, Real) and not isinstance(value, bool), f"threshold_{name}_invalid")
        value = float(value)
        _require(np.isfinite(value) and 0 <= value <= 1, f"threshold_{name}_invalid")
        result[name] = value
    return result


def _missing_block(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)):
        return bool(np.isnan(value))
    return False


def _tile_count(values: np.ndarray, mask: np.ndarray) -> int:
    selected = values[mask]
    _require(not any(_missing_block(value) for value in selected), "spatial_blocks_missing")
    try:
        return len({value.item() if isinstance(value, np.generic) else value for value in selected})
    except TypeError as exc:
        raise ValueError("spatial_blocks_invalid") from exc


def _support(y: np.ndarray, blocks: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    presence = mask & (y == 1)
    background = mask & (y == 0)
    n_presence = int(np.sum(presence))
    n_background = int(np.sum(background))
    presence_tiles = _tile_count(blocks, presence)
    background_tiles = _tile_count(blocks, background)
    failures: list[str] = []
    if n_presence < MIN_PRESENCES:
        failures.append("fewer_than_30_presences")
    if n_background < MIN_BACKGROUNDS:
        failures.append("fewer_than_100_backgrounds")
    if presence_tiles < MIN_ANCHORED_TILES:
        failures.append("fewer_than_4_anchored_50km_presence_tiles")
    if background_tiles < MIN_ANCHORED_TILES:
        failures.append("fewer_than_4_anchored_50km_background_tiles")
    return {
        "passes": not failures,
        "presence_cells": n_presence,
        "background_cells": n_background,
        "presence_tiles": presence_tiles,
        "background_tiles": background_tiles,
        "minimums": {
            "presence_cells": MIN_PRESENCES,
            "background_cells": MIN_BACKGROUNDS,
            "distinct_anchored_50km_tiles_per_class": MIN_ANCHORED_TILES,
        },
        "failure_reasons": failures,
    }


def _null_metric(n: int, positive: int, negative: int, threshold: float | None, reason: str | None) -> dict[str, Any]:
    return {
        "n": int(n),
        "n_positive": int(positive),
        "n_negative": int(negative),
        "prevalence": float(positive / n) if n else None,
        "roc_auc": None,
        "auc": None,
        "average_precision": None,
        "pr_auc": None,
        "tss": None,
        "balanced_accuracy": None,
        "mcc": None,
        "kappa": None,
        "sensitivity": None,
        "specificity": None,
        "threshold": threshold,
        "tp": None,
        "fn": None,
        "tn": None,
        "fp": None,
        "na_reason": reason,
    }


def _thresholded_metrics(y: np.ndarray, score: np.ndarray, threshold: float) -> dict[str, Any]:
    raw = binary_metrics(y, score, threshold)
    predicted = score >= threshold
    positive = y == 1
    negative = ~positive
    n = len(y)
    tp = int(np.sum(predicted & positive))
    fn = int(np.sum(~predicted & positive))
    tn = int(np.sum(~predicted & negative))
    fp = int(np.sum(predicted & negative))
    observed = (tp + tn) / n
    expected = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    kappa = 1.0 if expected == 1 and observed == 1 else (0.0 if expected == 1 else (observed - expected) / (1 - expected))
    result = {key: (float(value) if isinstance(value, (float, np.floating)) else value) for key, value in raw.items()}
    result.update({
        "auc": result["roc_auc"],
        "pr_auc": result["average_precision"],
        "balanced_accuracy": (
            (result["sensitivity"] + result["specificity"]) / 2
            if result["sensitivity"] is not None and result["specificity"] is not None else None
        ),
        "kappa": float(kappa) if raw["roc_auc"] is not None else None,
        "threshold": float(threshold),
        "na_reason": None if raw["roc_auc"] is not None else "single_response_class",
    })
    return result


def _auc_only(y: np.ndarray, score: np.ndarray) -> dict[str, Any]:
    positive = int(np.sum(y == 1))
    negative = int(np.sum(y == 0))
    auc = float(roc_auc_score(y, score)) if positive and negative else None
    return {
        "n": int(len(y)),
        "n_positive": positive,
        "n_negative": negative,
        "roc_auc": auc,
        "auc": auc,
        "na_reason": None if auc is not None else "single_response_class",
    }


def _score_mask(y: np.ndarray, scores: Mapping[str, np.ndarray], thresholds: Mapping[str, float], mask: np.ndarray) -> dict[str, Any]:
    masked_y = y[mask]
    result: dict[str, Any] = {}
    for name in ALL_ARMS:
        values = scores[name][mask]
        if name == "fixed_ensemble":
            result[name] = _auc_only(masked_y, values)
        else:
            result[name] = _thresholded_metrics(masked_y, values, thresholds[name]) if len(masked_y) else _null_metric(0, 0, 0, thresholds[name], "empty_mask")
    return result


def _auc_contrasts(arm_metrics: Mapping[str, Mapping[str, Any]]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for name, (left, right) in DEFAULT_CONTRASTS.items():
        left_auc = arm_metrics[left].get("roc_auc")
        right_auc = arm_metrics[right].get("roc_auc")
        result[name] = None if left_auc is None or right_auc is None else float(left_auc) - float(right_auc)
    return result


def _background_detail(y: np.ndarray, richness: np.ndarray) -> dict[str, Any]:
    # This is the frozen headline X10 background composition.  Presences are
    # always retained separately; only nonpresence cells carry the richness
    # eligibility rule.
    background = (y == 0) & (richness >= X10_RICHNESS)
    total = int(np.sum(background))
    strata: dict[str, Any] = {}
    for low, high, label in BACKGROUND_BINS:
        mask = background & (richness >= low) & (True if high is None else richness < high)
        count = int(np.sum(mask))
        strata[label] = {
            "presence_cells": int(np.sum(y == 1)),
            "background_cells": count,
            "background_share": float(count / total) if total else None,
            "auc": {},
            "reportable": None,
            "na_reason": None,
        }
    return {"background_cells_total": total, "background_strata": strata}


def _diagnostic_contrasts(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    def augmented(item: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(item)
        aucs = item.get("auc", {})
        item["contrasts"] = {
            name: (None if aucs.get(left) is None or aucs.get(right) is None else float(aucs[left]) - float(aucs[right]))
            for name, (left, right) in DEFAULT_CONTRASTS.items()
        }
        return item
    result = dict(diagnostic)
    result["background_strata"] = {
        label: augmented(item) for label, item in diagnostic["background_strata"].items()
    }
    high = diagnostic.get("high_recording_richness_subset")
    if isinstance(high, Mapping):
        result["high_recording_richness_subset"] = augmented(high)
    return result


def _headline_decomposition(y: np.ndarray, richness: np.ndarray,
                            scores: Mapping[str, np.ndarray], diagnostics: Mapping) -> dict:
    """Mechanical terms include sparse bins; they are not reportable bin AUCs."""
    positive = y == 1
    background = (y == 0) & (richness >= 10)
    bins = {}
    for low, high, label in BACKGROUND_BINS:
        absent = background & (richness >= low) & (True if high is None else richness < high)
        weight = float(absent.sum() / background.sum())
        aucs = dict(diagnostics["background_strata"][label]["auc"])
        if absent.any() and any(value is None for value in aucs.values()):
            selected = positive | absent
            aucs = {arm: float(roc_auc_score(y[selected], values[selected])) for arm, values in scores.items()}
        bins[label] = {name: 0.0 if not absent.any() else weight * (aucs[left] - aucs[right])
                       for name, (left, right) in DEFAULT_CONTRASTS.items()}
    terms = {}
    for name, (left, right) in DEFAULT_CONTRASTS.items():
        contributions = {label: values[name] for label, values in bins.items()}
        total = float(sum(contributions.values()))
        expected = diagnostics["weighted_auc_identity"][left]["full_x10_auc"] - diagnostics["weighted_auc_identity"][right]["full_x10_auc"]
        _require(abs(total - expected) <= 1e-12, "headline_bin_decomposition_failure")
        terms[name] = {"weighted_bin_contributions": contributions, "sum": total, "absolute_error": abs(total - expected)}
    return {"mechanical_only_includes_sparse_bins": True, "contrasts": terms}


def _validate_spatial_blocks(values: Any, n: int) -> np.ndarray:
    result = np.asarray(values)
    _require(result.ndim == 1 and len(result) == n, "spatial_blocks_invalid")
    _require(not any(_missing_block(value) for value in result), "spatial_blocks_missing")
    return result


def score_target_region(
    target: str,
    region: str,
    y: np.ndarray,
    richness_minus_f: np.ndarray,
    spatial_blocks: np.ndarray,
    scores: Mapping[str, np.ndarray],
    thresholds: Mapping[str, float],
    *,
    primary: bool,
    regional: bool,
) -> dict[str, Any]:
    """Score one target on one complete frozen region domain.

    X10 and X20 masks are made from all supplied cells.  Presences are never
    filtered by richness.  X10 support failures remain in the returned
    object for the caller's acceptance gate; X20 class/support failures are
    explicit NA diagnostics.
    """
    _require(isinstance(target, str) and bool(target), "target_invalid")
    _require(isinstance(region, str) and bool(region), "region_invalid")
    labels = _labels(y)
    n = len(labels)
    richness = np.asarray(richness_minus_f, dtype=np.float64)
    _require(richness.ndim == 1 and len(richness) == n and np.isfinite(richness).all() and np.all(richness >= 0) and np.all(richness == np.floor(richness)), "richness_minus_f_invalid")
    blocks = _validate_spatial_blocks(spatial_blocks, n)
    arm_scores = _normalise_arms(scores, n)
    threshold_values = _normalise_thresholds(thresholds)
    expected_ensemble = 0.5 * arm_scores["multihead_full_finetune"] + 0.5 * arm_scores["selected_conventional"]
    _require(np.allclose(arm_scores["fixed_ensemble"], expected_ensemble, rtol=0, atol=1e-12), "fixed_ensemble_mismatch")

    x10 = (labels == 1) | ((labels == 0) & (richness >= X10_RICHNESS))
    x20 = (labels == 1) | ((labels == 0) & (richness >= X20_RICHNESS))
    masks = {"x10": x10, "x20": x20}
    supports = {name: _support(labels, blocks, mask) for name, mask in masks.items()}
    metric_sets: dict[str, Any] = {}
    contrast_sets: dict[str, Any] = {}
    for name, mask in masks.items():
        metric_sets[name] = _score_mask(labels, arm_scores, threshold_values, mask)
        # X20 is the prespecified sensitivity panel.  A target that misses
        # its native fixed support gate remains in the result, but its X20
        # performance is an explicit NA rather than an apparently reportable
        # sparse-panel score.  X10 failures stay scored and flagged so the
        # caller can stop primary acceptance without deleting the target.
        if name == "x20" and not supports[name]["passes"]:
            reason = "x20_support_failure"
            n_cells = int(np.sum(mask))
            n_positive = int(np.sum(mask & (labels == 1)))
            n_background = int(np.sum(mask & (labels == 0)))
            for arm in EXISTING_ARMS:
                metric_sets[name][arm] = _null_metric(
                    n_cells, n_positive, n_background, threshold_values[arm], reason
                )
            metric_sets[name]["fixed_ensemble"] = {
                **_auc_only(labels[mask], arm_scores["fixed_ensemble"][mask]),
                "roc_auc": None,
                "auc": None,
                "na_reason": reason,
            }
        contrast_sets[name] = _auc_contrasts(metric_sets[name])

    composition = _background_detail(labels, richness)
    if supports["x10"]["presence_cells"] and supports["x10"]["background_cells"]:
        x10_y = labels[x10]
        x10_richness = richness[x10]
        x10_blocks = blocks[x10]
        diagnostics = evaluate_richness_diagnostics(
            x10_y,
            {name: values[x10] for name, values in arm_scores.items()},
            x10_richness,
            x10_blocks,
        )
        diagnostics = _diagnostic_contrasts(diagnostics)
        diagnostics["headline_decomposition"] = _headline_decomposition(labels, richness, arm_scores, diagnostics)
        composition = {
            "background_cells_total": diagnostics["background_cells_total"],
            "background_strata": diagnostics["background_strata"],
        }
    else:
        diagnostics = {
            "reportable": False,
            "na_reason": "x10_missing_response_class",
            "background_cells_total": composition["background_cells_total"],
            "background_strata": composition["background_strata"],
            "high_recording_richness_subset": None,
            "weighted_auc_identity": None,
        }

    # Keep both the compact panel-facing fields and the explicit mask fields;
    # the latter make the X10/X20 distinction auditable by callers.
    return {
        "target": target,
        "region": region,
        "panel": {"primary": bool(primary), "regional": bool(regional)},
        "masks": {
            name: {
                "cells": int(np.sum(mask)),
                "presence_cells": int(np.sum(mask & (labels == 1))),
                "background_cells": int(np.sum(mask & (labels == 0))),
                "support": supports[name],
            }
            for name, mask in masks.items()
        },
        "support": supports,
        "metrics": metric_sets,
        "contrasts": contrast_sets,
        "x10": {"metrics": metric_sets["x10"], "arms": metric_sets["x10"], "contrasts": contrast_sets["x10"], "support": supports["x10"]},
        "x20": {"metrics": metric_sets["x20"], "arms": metric_sets["x20"], "contrasts": contrast_sets["x20"], "support": supports["x20"]},
        "richness": diagnostics,
        "background_composition": composition,
        "thresholds": threshold_values,
    }


def _result_inventory(results: Any) -> dict[tuple[str, str], Mapping[str, Any]]:
    inventory: dict[tuple[str, str], Mapping[str, Any]] = {}
    if isinstance(results, Mapping):
        if all(isinstance(key, tuple) and len(key) == 2 for key in results):
            pairs = ((key, value) for key, value in results.items())
        elif all(isinstance(value, Mapping) and "target" in value and "region" in value for value in results.values()):
            pairs = (((value["region"], value["target"]), value) for value in results.values())
        else:
            pairs = (( (region, target), value) for region, region_values in results.items() for target, value in region_values.items())
    else:
        _require(isinstance(results, Sequence) and not isinstance(results, (str, bytes)), "results_invalid")
        pairs = (((value.get("region"), value.get("target")), value) for value in results)
    for key, value in pairs:
        _require(isinstance(key, tuple) and len(key) == 2 and all(isinstance(item, str) and item for item in key), "result_identity_invalid")
        _require(isinstance(value, Mapping), "result_invalid")
        _require(key not in inventory, "duplicate_target_region_result")
        inventory[key] = value
    return inventory


def _normalise_contrasts(contrasts: Mapping[str, Any] | None) -> dict[str, tuple[str, str]]:
    if contrasts is None:
        return dict(DEFAULT_CONTRASTS)
    _require(isinstance(contrasts, Mapping) and bool(contrasts), "contrasts_invalid")
    result: dict[str, tuple[str, str]] = {}
    for name, value in contrasts.items():
        _require(isinstance(name, str) and name, "contrast_name_invalid")
        if isinstance(value, Mapping):
            left, right = value.get("left"), value.get("right")
        else:
            _require(isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2, f"contrast_{name}_invalid")
            left, right = value
        _require(left in ALL_ARMS and right in ALL_ARMS, f"contrast_{name}_arms_invalid")
        result[name] = (left, right)
    return result


def _contrast_value(result: Mapping[str, Any], name: str, pair: tuple[str, str], metric: str = "x10") -> float | None:
    section = result.get(metric)
    if isinstance(section, Mapping):
        values = section.get("contrasts")
        if isinstance(values, Mapping) and name in values:
            value = values[name]
            return None if value is None else float(value)
        metrics = section.get("metrics", section.get("arms"))
    else:
        metrics = None
    if not isinstance(metrics, Mapping):
        return None
    left = metrics.get(pair[0], {}).get("roc_auc")
    right = metrics.get(pair[1], {}).get("roc_auc")
    return None if left is None or right is None else float(left) - float(right)


def _stats(values: Mapping[str, float | None], members: Sequence[str]) -> dict[str, Any]:
    ordered_members = list(members)
    finite = {target: float(value) for target, value in values.items() if value is not None and np.isfinite(float(value))}
    vector = np.asarray(list(finite.values()), dtype=np.float64)
    denominator = len(vector)
    positive = int(np.sum(vector > 0))
    mean = float(np.mean(vector)) if denominator else None
    median = float(np.median(vector)) if denominator else None
    label = None if denominator == 0 else (
        "consistent positive direction" if mean > 0 and positive > denominator / 2
        else "consistent nonpositive direction" if mean <= 0 and positive <= denominator / 2
        else "mixed direction"
    )
    return {
        "members": ordered_members,
        "evaluated_members": list(finite),
        "missing_members": [target for target in ordered_members if target not in finite],
        "values": {target: (finite[target] if target in finite else None) for target in ordered_members},
        "mean": mean,
        "median": median,
        "positive_count": positive,
        "denominator": denominator,
        "denom": denominator,
        "positive_fraction": float(positive / denominator) if denominator else None,
        "label": label,
    }


def _panel_stats(inventory: Mapping[tuple[str, str], Mapping[str, Any]], region: str, targets: Sequence[str], contrast_map: Mapping[str, tuple[str, str]], metric: str = "x10") -> dict[str, Any]:
    targets = list(targets)
    output = {"region": region, "target_count": len(targets), "targets": targets, "contrasts": {}}
    for name, pair in contrast_map.items():
        output["contrasts"][name] = _stats(
            {target: _contrast_value(inventory[(region, target)], name, pair, metric) for target in targets},
            targets,
        )
    output["arm_metrics"] = _panel_metric_stats(inventory, [region], targets, contrast_map, metric)
    return output


def _panel_metric_stats(inventory: Mapping, regions: Sequence[str], targets: Sequence[str],
                        contrast_map: Mapping, mask: str) -> dict:
    fields = ("roc_auc", "tss", "balanced_accuracy", "mcc", "sensitivity", "specificity", "prevalence")
    output = {"absolute": {}, "paired_differences": {}}
    def value(target: str, arm: str, field: str) -> float | None:
        values = [inventory[(region, target)][mask]["metrics"][arm].get(field) for region in regions]
        return float(np.mean(values)) if values and all(v is not None for v in values) else None
    for field in fields:
        arms = ALL_ARMS if field == "roc_auc" else EXISTING_ARMS
        output["absolute"][field] = {arm: _stats({target: value(target, arm, field) for target in targets}, targets) for arm in arms}
        paired = {}
        for name, (left, right) in contrast_map.items():
            if left not in arms or right not in arms:
                continue
            differences = {}
            for target in targets:
                a, b = value(target, left, field), value(target, right, field)
                differences[target] = None if a is None or b is None else a - b
            paired[name] = _stats(differences, targets)
        output["paired_differences"][field] = paired
    return output


def _common_panel_stats(inventory: Mapping[tuple[str, str], Mapping[str, Any]], regions: Sequence[str], targets: Sequence[str], contrast_map: Mapping[str, tuple[str, str]], metric: str = "x10") -> dict[str, Any]:
    regions = list(regions)
    targets = list(targets)
    output = {"regions": regions, "region_count": len(regions), "target_count": len(targets), "targets": targets, "contrasts": {}}
    for name, pair in contrast_map.items():
        values: dict[str, float | None] = {}
        for target in targets:
            regional_values = [_contrast_value(inventory[(region, target)], name, pair, metric) for region in regions]
            values[target] = float(np.mean(regional_values)) if regional_values and all(value is not None for value in regional_values) else None
        item = _stats(values, targets)
        item["equal_region_macro_mean"] = item["mean"]
        item["regional_means"] = {
            region: _stats({target: _contrast_value(inventory[(region, target)], name, pair, metric) for target in targets}, targets)["mean"]
            for region in regions
        }
        output["contrasts"][name] = item
    output["arm_metrics"] = _panel_metric_stats(inventory, regions, targets, contrast_map, metric)
    return output


def _richness_stats(inventory: Mapping[tuple[str, str], Mapping[str, Any]], region: str, targets: Sequence[str], contrast_map: Mapping[str, tuple[str, str]]) -> dict[str, Any]:
    labels = [item[2] for item in BACKGROUND_BINS]
    result: dict[str, Any] = {"region": region, "target_count": len(targets), "targets": list(targets), "bins": {}}
    for label in labels:
        common: dict[str, Any] = {}
        all_available: dict[str, Any] = {}
        for name, pair in contrast_map.items():
            target_values: dict[str, float | None] = {}
            for target in targets:
                diagnostic = inventory[(region, target)].get("richness", {})
                stratum = diagnostic.get("background_strata", {}).get(label, {})
                value = stratum.get("contrasts", {}).get(name) if isinstance(stratum, Mapping) else None
                target_values[target] = None if value is None else float(value)
            all_available[name] = _stats(target_values, targets)
            available_targets = [target for target in targets if all(
                inventory[(region, target)].get("richness", {}).get("background_strata", {}).get(other, {}).get("contrasts", {}).get(name) is not None
                for other in labels
            )]
            common[name] = _stats({target: target_values[target] for target in available_targets}, available_targets)
            common[name]["panel_members"] = list(targets)
        result["bins"][label] = {"common_support": common, "all_available": all_available}
    result["high_recording_richness_subset"] = _high_richness_stats(inventory, [region], targets, contrast_map)
    return result


def _high_richness_stats(inventory: Mapping, regions: Sequence[str], targets: Sequence[str], contrasts: Mapping) -> dict:
    result = {"regions": list(regions), "panel_members": list(targets), "contrasts": {}}
    for name in contrasts:
        values = {}
        for target in targets:
            per_region = []
            for region in regions:
                subset = inventory[(region, target)].get("richness", {}).get("high_recording_richness_subset") or {}
                per_region.append(subset.get("contrasts", {}).get(name))
            values[target] = float(np.mean(per_region)) if per_region and all(value is not None for value in per_region) else None
        evaluated = [target for target in targets if values[target] is not None]
        summary = _stats({target: values[target] for target in evaluated}, evaluated)
        summary["panel_members"] = list(targets)
        summary["nonevaluable_panel_members"] = [target for target in targets if target not in evaluated]
        result["contrasts"][name] = summary
    return result


def _richness_macro(inventory: Mapping[tuple[str, str], Mapping[str, Any]], regions: Sequence[str], targets: Sequence[str], contrast_map: Mapping[str, tuple[str, str]]) -> dict[str, Any]:
    labels = [item[2] for item in BACKGROUND_BINS]
    result: dict[str, Any] = {"regions": list(regions), "targets": list(targets), "bins": {}}
    for label in labels:
        contrasts: dict[str, Any] = {}
        for name, pair in contrast_map.items():
            values: dict[str, float | None] = {}
            for target in targets:
                per_region = []
                for region in regions:
                    value = inventory[(region, target)].get("richness", {}).get("background_strata", {}).get(label, {}).get("contrasts", {}).get(name)
                    per_region.append(value)
                values[target] = float(np.mean(per_region)) if per_region and all(value is not None for value in per_region) else None
            item = _stats(values, targets)
            item["equal_region_macro_mean"] = item["mean"]
            contrasts[name] = item
        result["bins"][label] = {"contrasts": contrasts}
    for label in labels:
        common_support = {}
        for name in contrast_map:
            members = [target for target in targets if all(
                inventory[(region, target)].get("richness", {}).get("background_strata", {}).get(other, {}).get("contrasts", {}).get(name) is not None
                for region in regions for other in labels)]
            common_support[name] = _stats({target: result["bins"][label]["contrasts"][name]["values"][target] for target in members}, members)
            common_support[name]["panel_members"] = list(targets)
        result["bins"][label]["three_bin_common_support"] = common_support
    result["high_recording_richness_subset"] = _high_richness_stats(inventory, regions, targets, contrast_map)
    return result


def _panel_decomposition(inventory: Mapping, region: str, targets: Sequence[str], contrasts: Mapping) -> dict:
    result = {"targets": list(targets), "target_count": len(targets), "contrasts": {}}
    for name, pair in contrasts.items():
        terms = {target: inventory[(region, target)].get("richness", {}).get("headline_decomposition", {}).get("contrasts", {}).get(name) for target in targets}
        if not targets or any(value is None for value in terms.values()):
            result["contrasts"][name] = {"mean_weighted_bin_contributions": None, "sum": None, "absolute_error": None}
            continue
        means = {label: float(np.mean([terms[target]["weighted_bin_contributions"][label] for target in targets])) for _, _, label in BACKGROUND_BINS}
        total = sum(means.values())
        expected = float(np.mean([_contrast_value(inventory[(region, target)], name, pair) for target in targets]))
        _require(abs(total - expected) <= 1e-12, "panel_decomposition_failure")
        result["contrasts"][name] = {"mean_weighted_bin_contributions": means, "sum": total, "absolute_error": abs(total - expected)}
    return result


def aggregate_regions(
    results: Any,
    primary_targets: Sequence[str],
    regional_targets: Mapping[str, Sequence[str]],
    contrasts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate target-region scores with equal target and region weights.

    The common panel is summarized target-wise after averaging each target's
    regional contrasts, which is equivalent to equal species and equal region
    weights.  Cell rows are never pooled.
    """
    primary = list(primary_targets)
    _require(len(primary) == len(set(primary)), "primary_targets_duplicate")
    _require(isinstance(regional_targets, Mapping) and bool(regional_targets), "regional_targets_invalid")
    region_names = [region for region in ("NCP", "SEH", "NNC") if region in regional_targets]
    region_names += [region for region in regional_targets if region not in region_names]
    panel_targets = {region: list(regional_targets[region]) for region in region_names}
    for region, targets in panel_targets.items():
        _require(len(targets) == len(set(targets)), f"regional_targets_duplicate:{region}")
    inventory = _result_inventory(results)
    for region, targets in panel_targets.items():
        for target in targets:
            _require((region, target) in inventory, f"missing_target_region_result:{region}:{target}")
    for region in region_names:
        _require(set(primary) <= set(panel_targets[region]), f"primary_target_missing_from_region:{region}")
    contrast_map = _normalise_contrasts(contrasts)

    regional_panels = {
        region: _panel_stats(inventory, region, targets, contrast_map)
        for region, targets in panel_targets.items()
    }
    primary_by_region = {region: _panel_stats(inventory, region, primary, contrast_map) for region in region_names}
    common = _common_panel_stats(inventory, region_names, primary, contrast_map)
    richness = {
        "regional": {
            region: _richness_stats(inventory, region, targets, contrast_map)
            for region, targets in panel_targets.items()
        },
        "primary_by_region": {region: _richness_stats(inventory, region, primary, contrast_map) for region in region_names},
        "supplementary_three_region_macro": _richness_macro(inventory, region_names, primary, contrast_map),
    }
    composition = {
        region: summarize_background_composition({
            target: inventory[(region, target)]["background_composition"]
            for target in targets
        })
        for region, targets in panel_targets.items()
    }
    primary_composition = {region: summarize_background_composition({
        target: inventory[(region, target)]["background_composition"] for target in primary
    }) for region in region_names}
    decomposition = {
        "primary_by_region": {region: _panel_decomposition(inventory, region, primary, contrast_map) for region in region_names},
        "regional": {region: _panel_decomposition(inventory, region, targets, contrast_map) for region, targets in panel_targets.items()},
    }
    x20 = {
        "primary_by_region": {region: _panel_stats(inventory, region, primary, contrast_map, "x20") for region in region_names},
        "regional": {region: _panel_stats(inventory, region, targets, contrast_map, "x20") for region, targets in panel_targets.items()},
        "common_three_region_intersection": _common_panel_stats(inventory, region_names, primary, contrast_map, "x20"),
    }
    # X20 retains each region's prospectively frozen eligible subset. Unlike
    # supplementary richness diagnostics, its main macro uses 72/73/73
    # common-panel targets rather than requiring the same 72 in every region.
    x20["common_equal_region_macro"] = {
        "weighting": "equal eligible target weight within each region; equal region weight",
        "contrasts": {
            name: {
                "mean": float(np.mean([x20["primary_by_region"][region]["contrasts"][name]["mean"] for region in region_names]))
                if all(x20["primary_by_region"][region]["contrasts"][name]["mean"] is not None for region in region_names) else None,
                "regional_means": {region: x20["primary_by_region"][region]["contrasts"][name]["mean"] for region in region_names},
                "regional_denominators": {region: x20["primary_by_region"][region]["contrasts"][name]["denominator"] for region in region_names},
                "regional_evaluated_members": {region: x20["primary_by_region"][region]["contrasts"][name]["evaluated_members"] for region in region_names},
            } for name in contrast_map
        },
    }
    frozen_panels: dict[str, Any] = {"common73": common}
    for region, panel in regional_panels.items():
        frozen_panels[f"regional{panel['target_count']}"] = panel
    return {
        "common": common,
        "common73": common,
        "primary_by_region": primary_by_region,
        "regional": regional_panels,
        "regional_panels": regional_panels,
        "frozen_panels": frozen_panels,
        "richness": richness,
        "richness_diagnostics": richness,
        "background_composition": composition,
        "primary_background_composition": primary_composition,
        "headline_decomposition": decomposition,
        "x20": x20,
        "contrasts": list(contrast_map),
        "primary_targets": primary,
        "regional_targets": panel_targets,
    }


def matched_inner_attenuation(aggregate: Mapping, inner_summary: Mapping) -> dict:
    """Outer-minus-inner AUC difference under identical target identities."""
    inner = {}
    for item in inner_summary["conditions"]:
        if item["fraction"] == 100 and item["auxiliary"] == "full":
            _require(item["target"] not in inner, "duplicate_matched_inner_target")
            inner[item["target"]] = {**item["primary_contrasts"], **item["mechanistic_contrasts"]}
    names = (*PRIMARY_CONTRASTS, *MECHANISTIC_CONTRASTS)
    def comparison(panel: Mapping) -> dict:
        members = panel["targets"]
        _require(all(target in inner for target in members), "matched_inner_target_missing")
        output = {}
        for name in names:
            inner_values = {target: float(inner[target][name]["delta_mean_fold_roc_auc"]) for target in members}
            outer = panel["contrasts"][name]
            _require(outer["denominator"] == len(members), "matched_outer_panel_incomplete")
            mean = float(np.mean(list(inner_values.values()))) if members else None
            output[name] = {"targets": list(members), "target_count": len(members),
                            "inner_mean_difference": mean, "outer_mean_difference": outer["mean"],
                            "outer_minus_inner": None if mean is None else outer["mean"] - mean,
                            "inner_target_differences": inner_values}
        return output
    return {"reference": "accepted target100/full inner mean-fold ROC AUC differences; equal target weights",
            "primary_by_region": {region: comparison(panel) for region, panel in aggregate["primary_by_region"].items()},
            "regional": {region: comparison(panel) for region, panel in aggregate["regional"].items()},
            "common_equal_region_macro": comparison(aggregate["common"])}
