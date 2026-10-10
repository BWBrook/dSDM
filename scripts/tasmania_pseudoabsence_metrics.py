"""Deterministic descriptive summaries for the approved paired sensitivity.

These functions do no I/O, fitting, or response access. Threshold candidates
and the lower-median tie rule reproduce Goal036. Map percentile ranks use
100 * (midrank - 1) / (N - 1); displacement is in percentile points.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import rankdata
from sklearn.metrics import matthews_corrcoef, roc_auc_score


def require(condition, message):
    if not condition:
        raise ValueError(message)


def vectors(y, score):
    labels = np.asarray(y)
    values = np.asarray(score, dtype=np.float64)
    require(labels.ndim == values.ndim == 1 and len(labels) == len(values) > 0,
            "response/prediction alignment failed")
    require(np.isin(labels, [0, 1]).all(), "nonbinary response")
    require(np.isfinite(values).all() and ((0 <= values) & (values <= 1)).all(),
            "invalid probability")
    return labels.astype(np.int8), values


def tss(y, score, threshold):
    predicted = score >= threshold
    return float(np.mean(predicted[y == 1]) + np.mean(~predicted[y == 0]) - 1.0)


def select_threshold(y, score):
    labels, values = vectors(y, score)
    require(set(labels.tolist()) == {0, 1}, "threshold requires both classes")
    unique = np.unique(values)
    candidates = [float(np.nextafter(unique[0], -np.inf)),
                  float(np.nextafter(unique[-1], np.inf))]
    for low, high in zip(unique[:-1], unique[1:]):
        midpoint = float(low + (high - low) / 2.0)
        if not low < midpoint < high:
            midpoint = float(high)
        if np.isfinite(midpoint):
            candidates.append(midpoint)
    candidates = sorted(set(candidates))
    metrics = [tss(labels, values, threshold) for threshold in candidates]
    maximum = max(metrics)
    maximizers = [threshold for threshold, metric in zip(candidates, metrics)
                  if metric == maximum]
    return {"threshold": maximizers[(len(maximizers) - 1) // 2],
            "maximizer_count": len(maximizers), "maximum_oof_tss": maximum,
            "candidate_count": len(candidates)}


def binary_metrics(y, score, threshold):
    labels, values = vectors(y, score)
    require(np.isfinite(threshold), "nonfinite threshold")
    predicted = values >= threshold
    positive = labels == 1
    tp = int(np.sum(predicted & positive))
    tn = int(np.sum(~predicted & ~positive))
    fp = int(np.sum(predicted & ~positive))
    fn = int(np.sum(~predicted & positive))
    require(tp + fn > 0 and tn + fp > 0, "pooled metrics require both classes")
    return {"n": len(labels), "n_positive": tp + fn, "n_negative": tn + fp,
            "threshold": float(threshold), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "roc_auc": float(roc_auc_score(labels, values)),
            "tss": float(tp / (tp + fn) + tn / (tn + fp) - 1),
            "mcc": float(matthews_corrcoef(labels, predicted)),
            "sensitivity": float(tp / (tp + fn)), "specificity": float(tn / (tn + fp))}


def source_specificity(y, sources, score, threshold):
    labels, values = vectors(y, score)
    require(np.isfinite(threshold), "nonfinite threshold")
    source = np.asarray(sources)
    require(source.shape == labels.shape, "source alignment failed")
    require(set(source.tolist()) <= {"presence", "survey_supported_absence", "pseudoabsence"},
            "unknown response source")
    require(np.array_equal(labels == 1, source == "presence"), "source/class disagreement")
    rows = {}
    for name in ("survey_supported_absence", "pseudoabsence"):
        mask = source == name
        denominator = int(mask.sum())
        numerator = int(np.sum(values[mask] < threshold))
        rows[name] = {"true_negative": numerator, "denominator": denominator,
                      "specificity": float(numerator / denominator) if denominator else None,
                      "na_reason": None if denominator else "no_absences_of_this_source"}
    return rows


def map_summary(cells, primary, sensitivity, *, top_count=7103, expected_cells=71023):
    ids = np.asarray(cells)
    before = np.asarray(primary, dtype=np.float64)
    after = np.asarray(sensitivity, dtype=np.float64)
    require(ids.ndim == before.ndim == after.ndim == 1 and len(ids) == len(before) == len(after) == expected_cells,
            "map domain mismatch")
    require(ids.dtype.kind in "US" and len(set(ids.tolist())) == len(ids), "invalid map identity")
    require(np.isfinite(before).all() and np.isfinite(after).all() and
            ((before >= 0) & (before <= 1)).all() and ((after >= 0) & (after <= 1)).all(),
            "invalid map probability")
    require(0 < top_count <= len(ids) and len(ids) > 1, "invalid top-decile size")
    rank_before = rankdata(before, method="average")
    rank_after = rankdata(after, method="average")
    displacement = 100.0 * (rank_after - rank_before) / (len(ids) - 1)
    constant = np.ptp(rank_before) == 0 or np.ptp(rank_after) == 0
    correlation = None if constant else float(np.corrcoef(rank_before, rank_after)[0, 1])
    top_before = np.lexsort((ids, -before))[:top_count]
    top_after = np.lexsort((ids, -after))[:top_count]
    intersection = len(set(ids[top_before].tolist()) & set(ids[top_after].tolist()))
    quantiles = np.quantile(displacement, [0.025, 0.5, 0.975], method="linear")
    return {"domain_cells": len(ids), "spearman_rho": correlation,
            "spearman_na_reason": "constant_probability_map" if constant else None,
            "rank_displacement_q025_percentile_points": float(quantiles[0]),
            "rank_displacement_median_percentile_points": float(quantiles[1]),
            "rank_displacement_q975_percentile_points": float(quantiles[2]),
            "top_decile_intersection": intersection, "top_decile_denominator": top_count,
            "top_decile_retention": float(intersection / top_count),
            "probability_difference_min": float(np.min(after - before)),
            "probability_difference_max": float(np.max(after - before)),
            "probability_difference_mean": float(np.mean(after - before))}
