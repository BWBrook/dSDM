"""Independent post-assessment replay for the Tasmania sensitivity.

This command is deliberately inert until both immutable prediction closure and
the public assessment exist.  It never fits a model, opens the canonical outer
response table, or runs the assessment.  After those gates pass it authenticates
the private minimal response snapshot, asks the collector to revalidate every
source leaf, and independently recomputes normalization, OOF thresholds,
metrics, source denominators, contrasts, and map summaries.

Run only after the production owner confirms closure and assessment::

    .venv/bin/python scripts/tasmania_pseudoabsence_audit.py verify --execute
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/assessment")
EVIDENCE_REL = Path("evidence/tasmania_pseudoabsence/20261009")
OUTPUT_NAME = "independent-assessment-verification.json"
BASELINE_REL = Path("data/processed/dsdm/tasmania-outer-assessment-20261005/private")
RESPONSE_SHA256 = "b93fbdfa4df2b2d8617dd890cdb7fc4c3aa54ed10c72eed9c9ebc93df18edafc"
BASELINE_RECEIPT_DIGEST = "6b1240538079be2219a22502625e34c473fce4c56c1030f5a302b4cacd6cb77e"
BASELINE_CLOSURE_DIGEST = "a160318d5cc627ff5a724256ee4a008ad4f13038b9419ba7e809cf01bd6a4e6e"
SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
FOLDS = tuple(f"fold{index:02d}" for index in range(5))
ENDPOINTS = (
    "fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02",
    "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02",
    "fraction100/full",
)
METHODS = ("target_only_resmlp", "multihead_full_finetune", "selected_conventional")
NEURAL_METHODS = METHODS[:2]
BASE_NEURAL = (
    "target_only_resmlp", "legacy_pooled_finetune", "multihead_frozen_trunk",
    "multihead_full_finetune", "target_plus_q_linear", "target_plus_q_deep",
)
BASE_CONVENTIONAL = (
    "intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann",
)
NEURAL_SEEDS = (31031, 31032, 31033, 31034, 31035)
CONVENTIONAL_SEEDS = {
    "elastic_net": tuple(f"seed{index:02d}" for index in range(5)),
    "random_forest": tuple(f"seed{index:02d}" for index in range(5)),
    "hist_gradient_boosting": ("seed00",),
    "shallow_ann": tuple(f"seed{index:02d}" for index in range(5)),
}
EXPECTED_HELD_ROWS = 1672
EXPECTED_MAP_ROWS = 71023
TOP_COUNT = 7103
FLOAT_TOLERANCE = 1e-12


class AuditError(ValueError):
    """Raised when the independent replay must fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    require(target.is_file() and not target.is_symlink(), f"json_missing:{target}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"json_invalid:{target}") from exc
    require(isinstance(value, dict), f"json_object_required:{target}")
    return value


def read_receipt(path: str | Path) -> dict[str, Any]:
    value = read_json(path)
    body = dict(value)
    claimed = body.pop("receipt_digest", None)
    require(
        isinstance(claimed, str) and len(claimed) == 64 and digest_value(body) == claimed,
        f"receipt_digest_mismatch:{Path(path)}",
    )
    return value


def safe_bound_path(root: Path, relative: Any) -> Path:
    require(isinstance(relative, str) and relative, "bound_path_invalid")
    unresolved = root / relative
    require(unresolved.is_file() and not unresolved.is_symlink(), f"bound_file_missing:{relative}")
    target = unresolved.resolve()
    require(target != root.resolve() and root.resolve() in target.parents, f"bound_path_outside_root:{relative}")
    return target


def validate_bound_records(root: Path, records: Any, *, label: str) -> dict[str, Path]:
    require(isinstance(records, list) and records, f"{label}_inventory_missing")
    result: dict[str, Path] = {}
    for row in records:
        require(isinstance(row, dict), f"{label}_record_invalid")
        role = row.get("role")
        require(isinstance(role, str) and role and role not in result, f"{label}_role_invalid")
        target = safe_bound_path(root, row.get("path"))
        require(sha256_file(target) == row.get("sha256"), f"{label}_sha256_mismatch:{role}")
        result[role] = target
    return result


def read_npz(path: str | Path, expected: set[str] | None = None) -> dict[str, np.ndarray]:
    target = Path(path)
    require(target.is_file() and not target.is_symlink(), f"npz_missing:{target}")
    try:
        with np.load(target, allow_pickle=False) as loaded:
            if expected is not None:
                require(set(loaded.files) == expected, f"npz_inventory_mismatch:{target}")
            return {name: np.array(loaded[name], copy=True) for name in loaded.files}
    except AuditError:
        raise
    except (OSError, ValueError) as exc:
        raise AuditError(f"npz_invalid:{target}") from exc


def validate_ids(values: Any, *, label: str, expected_length: int | None = None) -> np.ndarray:
    result = np.asarray(values)
    require(result.ndim == 1 and result.dtype.kind in "US", f"{label}_invalid")
    require(len(set(result.tolist())) == len(result), f"{label}_duplicate")
    if expected_length is not None:
        require(len(result) == expected_length, f"{label}_length_mismatch")
    return result


def align_values(expected_ids: Any, observed_ids: Any, values: Any, *, label: str) -> np.ndarray:
    expected = validate_ids(expected_ids, label=f"{label}_expected_ids")
    observed = validate_ids(observed_ids, label=f"{label}_observed_ids")
    vector = np.asarray(values)
    require(vector.ndim == 1 and vector.shape == observed.shape, f"{label}_shape_mismatch")
    require(set(expected.tolist()) == set(observed.tolist()), f"{label}_membership_mismatch")
    index = {str(cell): position for position, cell in enumerate(observed)}
    return vector[np.asarray([index[str(cell)] for cell in expected], dtype=np.int64)]


def seed_mean(
    records: Sequence[tuple[Any, np.ndarray, np.ndarray]],
    expected_seeds: Sequence[Any],
    expected_ids: np.ndarray,
    *,
    label: str,
) -> np.ndarray:
    """Independent identity-aligned float64 seed average."""
    require(len(records) == len(expected_seeds), f"{label}_seed_count_mismatch")
    by_seed: dict[Any, tuple[np.ndarray, np.ndarray]] = {}
    for seed, ids, scores in records:
        require(seed not in by_seed, f"{label}_duplicate_seed")
        by_seed[seed] = (ids, scores)
    require(set(by_seed) == set(expected_seeds), f"{label}_seed_inventory_mismatch")
    aligned = [
        np.asarray(align_values(expected_ids, *by_seed[seed], label=f"{label}:{seed}"), dtype=np.float64)
        for seed in expected_seeds
    ]
    result = np.mean(np.stack(aligned), axis=0, dtype=np.float64)
    require(result.dtype == np.float64 and np.isfinite(result).all(), f"{label}_mean_invalid")
    return result


def binary_vectors(y: Any, score: Any) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(y)
    values = np.asarray(score, dtype=np.float64)
    require(labels.ndim == values.ndim == 1 and len(labels) == len(values) > 0, "binary_alignment_invalid")
    require(np.isin(labels, (0, 1)).all(), "binary_labels_invalid")
    require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "probability_invalid")
    return labels.astype(np.int8), values


def average_ranks(values: Any) -> np.ndarray:
    """One-based average ranks with exact tie blocks; no SciPy dependency."""
    array = np.asarray(values, dtype=np.float64)
    require(array.ndim == 1 and len(array) > 0 and np.isfinite(array).all(), "rank_input_invalid")
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(len(array), dtype=np.float64)
    start = 0
    while start < len(array):
        stop = start + 1
        while stop < len(array) and array[order[stop]] == array[order[start]]:
            stop += 1
        ranks[order[start:stop]] = (start + 1 + stop) / 2.0
        start = stop
    return ranks


def auc_rank_u(y: Any, score: Any) -> float:
    labels, values = binary_vectors(y, score)
    positive = labels == 1
    n_positive = int(positive.sum())
    n_negative = len(labels) - n_positive
    require(n_positive > 0 and n_negative > 0, "auc_requires_both_classes")
    rank_sum = float(average_ranks(values)[positive].sum())
    return (rank_sum - n_positive * (n_positive + 1) / 2.0) / (n_positive * n_negative)


def threshold_candidates(score: Any) -> list[float]:
    values = np.asarray(score, dtype=np.float64)
    require(values.ndim == 1 and len(values) > 0 and np.isfinite(values).all(), "threshold_scores_invalid")
    unique = np.unique(values)
    candidates = [float(np.nextafter(unique[0], -np.inf)), float(np.nextafter(unique[-1], np.inf))]
    for low, high in zip(unique[:-1], unique[1:], strict=True):
        midpoint = float(low + (high - low) / 2.0)
        if not low < midpoint < high:
            midpoint = float(high)
        if np.isfinite(midpoint):
            candidates.append(midpoint)
    return sorted(set(candidates))


def confusion(y: Any, score: Any, threshold: float) -> dict[str, Any]:
    labels, values = binary_vectors(y, score)
    require(np.isfinite(threshold), "threshold_nonfinite")
    predicted = values >= threshold
    positive = labels == 1
    tp = int(np.sum(predicted & positive))
    tn = int(np.sum(~predicted & ~positive))
    fp = int(np.sum(predicted & ~positive))
    fn = int(np.sum(~predicted & positive))
    require(tp + fn > 0 and tn + fp > 0, "metrics_require_both_classes")
    denominator = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    mcc = 0.0 if denominator == 0 else (tp * tn - fp * fn) / math.sqrt(denominator)
    return {
        "n": len(labels), "n_positive": tp + fn, "n_negative": tn + fp,
        "threshold": float(threshold), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "roc_auc": float(auc_rank_u(labels, values)),
        "tss": float(tp / (tp + fn) + tn / (tn + fp) - 1.0),
        "mcc": float(mcc),
    }


def select_threshold(y: Any, score: Any) -> dict[str, Any]:
    labels, values = binary_vectors(y, score)
    require(set(labels.tolist()) == {0, 1}, "threshold_requires_both_classes")
    candidates = threshold_candidates(values)
    results = [confusion(labels, values, threshold)["tss"] for threshold in candidates]
    maximum = max(results)
    maximizers = [threshold for threshold, result in zip(candidates, results, strict=True) if result == maximum]
    return {
        "threshold": maximizers[(len(maximizers) - 1) // 2],
        "maximizer_count": len(maximizers), "maximum_oof_tss": float(maximum),
        "candidate_count": len(candidates),
    }


def source_specificity(y: Any, sources: Any, score: Any, threshold: float) -> dict[str, dict[str, Any]]:
    labels, values = binary_vectors(y, score)
    require(np.isfinite(threshold), "threshold_nonfinite")
    source = np.asarray(sources)
    require(source.shape == labels.shape, "source_alignment_invalid")
    require(set(source.tolist()) <= {"presence", "survey_supported_absence", "pseudoabsence"}, "source_invalid")
    require(np.array_equal(labels == 1, source == "presence"), "source_class_disagreement")
    result: dict[str, dict[str, Any]] = {}
    for name in ("survey_supported_absence", "pseudoabsence"):
        mask = source == name
        denominator = int(mask.sum())
        true_negative = int(np.sum(values[mask] < threshold))
        result[name] = {
            "true_negative": true_negative, "denominator": denominator,
            "specificity": None if denominator == 0 else float(true_negative / denominator),
        }
    return result


def linear_quantile(values: Any, probability: float) -> float:
    ordered = np.sort(np.asarray(values, dtype=np.float64))
    require(ordered.ndim == 1 and len(ordered) > 0 and 0 <= probability <= 1, "quantile_input_invalid")
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return float(ordered[lower] + fraction * (ordered[upper] - ordered[lower]))


def pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    x_centered = x - np.mean(x, dtype=np.float64)
    y_centered = y - np.mean(y, dtype=np.float64)
    denominator = math.sqrt(float(np.dot(x_centered, x_centered) * np.dot(y_centered, y_centered)))
    if denominator == 0:
        return None
    return float(np.dot(x_centered, y_centered) / denominator)


def map_summary(
    cells: Any, primary: Any, sensitivity: Any, *, top_count: int = TOP_COUNT,
    expected_cells: int = EXPECTED_MAP_ROWS,
) -> dict[str, Any]:
    ids = validate_ids(cells, label="map_ids", expected_length=expected_cells)
    before = np.asarray(primary, dtype=np.float64)
    after = np.asarray(sensitivity, dtype=np.float64)
    require(before.shape == after.shape == ids.shape, "map_shape_invalid")
    require(np.isfinite(before).all() and np.isfinite(after).all(), "map_probability_nonfinite")
    require(np.all((before >= 0) & (before <= 1)) and np.all((after >= 0) & (after <= 1)), "map_probability_invalid")
    require(0 < top_count <= len(ids) and len(ids) > 1, "map_top_count_invalid")
    rank_before = average_ranks(before)
    rank_after = average_ranks(after)
    displacement = 100.0 * (rank_after - rank_before) / (len(ids) - 1)
    rho = pearson(rank_before, rank_after)
    top_before = sorted(range(len(ids)), key=lambda index: (-before[index], str(ids[index])))[:top_count]
    top_after = sorted(range(len(ids)), key=lambda index: (-after[index], str(ids[index])))[:top_count]
    intersection = len({str(ids[index]) for index in top_before} & {str(ids[index]) for index in top_after})
    difference = after - before
    return {
        "domain_cells": len(ids), "spearman_rho": rho,
        "spearman_na_reason": "constant_probability_map" if rho is None else None,
        "rank_displacement_q025_percentile_points": linear_quantile(displacement, 0.025),
        "rank_displacement_median_percentile_points": linear_quantile(displacement, 0.5),
        "rank_displacement_q975_percentile_points": linear_quantile(displacement, 0.975),
        "top_decile_intersection": intersection, "top_decile_denominator": top_count,
        "top_decile_retention": float(intersection / top_count),
        "probability_difference_min": float(np.min(difference)),
        "probability_difference_max": float(np.max(difference)),
        "probability_difference_mean": float(np.mean(difference, dtype=np.float64)),
    }


def parse_scalar(value: str) -> Any:
    if value == "NA":
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def read_csv(path: Path) -> list[dict[str, Any]]:
    require(path.is_file() and not path.is_symlink(), f"csv_missing:{path}")
    with path.open(newline="", encoding="utf-8") as stream:
        return [{key: parse_scalar(value) for key, value in row.items()} for row in csv.DictReader(stream)]


def equal_value(actual: Any, expected: Any, *, exact: bool = False) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, (int, np.integer)) and isinstance(expected, (int, np.integer)):
        return int(actual) == int(expected)
    if isinstance(actual, (float, np.floating)) and isinstance(expected, (float, np.floating)):
        if exact:
            return float(actual) == float(expected)
        return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=FLOAT_TOLERANCE)
    return actual == expected


def compare_rows(
    actual: list[dict[str, Any]], expected: list[dict[str, Any]], keys: Sequence[str],
    *, exact_fields: Iterable[str] = (), label: str,
) -> None:
    def index(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
        result = {tuple(row.get(key) for key in keys): row for row in rows}
        require(len(result) == len(rows), f"{label}_duplicate_key")
        return result

    actual_index, expected_index = index(actual), index(expected)
    require(set(actual_index) == set(expected_index), f"{label}_key_inventory_mismatch")
    exact = set(exact_fields)
    for key in expected_index:
        a, e = actual_index[key], expected_index[key]
        require(set(a) == set(e), f"{label}_field_inventory_mismatch:{key}")
        for field in e:
            require(equal_value(a[field], e[field], exact=field in exact), f"{label}_value_mismatch:{key}:{field}")


def validate_post_assessment_gate(root: Path, private: Path, evidence: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Authenticate public completion before parsing any private response row."""
    required = [
        private / "prediction-closure.json", private / "response-access.json",
        private / "held-response-snapshot.json", evidence / "assessment.json",
    ]
    for path in required:
        require(path.is_file() and not path.is_symlink(), f"post_assessment_gate_missing:{path.name}")
    # Read only the response-free closure and public assessment first.  A
    # malformed or failed assessment must refuse before private response
    # access evidence or snapshot rows are parsed.
    closure = read_receipt(required[0])
    assessment = read_receipt(required[3])
    require(closure.get("schema_version") == "tasmania-pseudoabsence-prediction-closure-v1" and closure.get("status") == "accepted", "prediction_closure_not_accepted")
    require(closure.get("outer_held_response_labels_read") == 0, "prediction_closure_response_boundary_invalid")
    require(closure.get("target_physical_fits") == 8125 and closure.get("smoke_physical_fits") == 14 and closure.get("recovery_physical_fits") == 200, "prediction_closure_fit_inventory_invalid")
    require(closure.get("baseline_receipt_digest") == BASELINE_RECEIPT_DIGEST, "prediction_closure_baseline_binding_invalid")
    require(assessment.get("schema_version") == "tasmania-pseudoabsence-sensitivity-assessment-v1" and assessment.get("success") is True, "assessment_not_complete")
    require(assessment.get("prediction_closure_digest") == closure["receipt_digest"], "assessment_closure_link_invalid")
    require(assessment.get("baseline_receipt_digest") == BASELINE_RECEIPT_DIGEST, "assessment_baseline_binding_invalid")
    require(assessment.get("outer_held_response_parses") == 1 and assessment.get("canonical_response_file_opens") == 3 and assessment.get("canonical_response_integrity_hash_passes") == 2, "assessment_response_accounting_invalid")
    require(assessment.get("privacy") == {"aggregate_only": True, "tracked_response_rows": False, "tracked_coordinates": False}, "assessment_privacy_contract_invalid")
    expected_counts = {"species": 8, "endpoints": 7, "methods": 3, "paired_performance_rows": 168, "map_pairs": 24, "held_rows": 1672}
    require(assessment.get("counts") == expected_counts, "assessment_declared_counts_invalid")
    expected_files = {"paired-performance.csv", "source-specificity.csv", "paired-contrasts.csv", "map-comparison.csv", "held-source-counts.csv"}
    file_rows = assessment.get("files")
    require(isinstance(file_rows, list) and len(file_rows) == len(expected_files), "assessment_file_inventory_invalid")
    observed_names: set[str] = set()
    for row in file_rows:
        require(isinstance(row, dict) and set(row) == {"path", "sha256"}, "assessment_file_record_invalid")
        path = safe_bound_path(root, row["path"])
        require(path.parent == evidence.resolve(), "assessment_file_location_invalid")
        observed_names.add(path.name)
        require(sha256_file(path) == row["sha256"], f"assessment_file_sha256_mismatch:{path.name}")
    require(observed_names == expected_files, "assessment_file_set_invalid")

    access = read_receipt(required[1])
    require(access.get("schema_version") == "tasmania-sensitivity-response-access-intent-v1", "response_access_schema_invalid")
    require(access.get("prediction_closure_digest") == closure["receipt_digest"], "response_access_closure_link_invalid")
    require(access.get("response_sha256") == RESPONSE_SHA256, "response_access_source_binding_invalid")
    require(access.get("held_rows_parsed") == EXPECTED_HELD_ROWS and access.get("training_rows_parsed") == 0, "response_access_row_inventory_invalid")
    require(access.get("response_parses") == 1 and access.get("canonical_file_opens") == 3 and access.get("integrity_hash_passes") == 2, "response_access_accounting_invalid")
    require(assessment.get("response_access_digest") == access["receipt_digest"], "assessment_access_link_invalid")

    snapshot = read_receipt(required[2])
    require(snapshot.get("schema_version") == "tasmania-sensitivity-held-response-snapshot-v1", "response_snapshot_schema_invalid")
    require(snapshot.get("prediction_closure_digest") == closure["receipt_digest"], "response_snapshot_closure_link_invalid")
    require(snapshot.get("receipt_digest") == access.get("private_snapshot_receipt_digest"), "response_snapshot_access_link_invalid")
    require(snapshot.get("response_sha256") == access.get("response_sha256") == RESPONSE_SHA256, "response_snapshot_source_link_invalid")
    rows = snapshot.get("rows")
    require(isinstance(rows, list) and len(rows) == EXPECTED_HELD_ROWS, "response_snapshot_row_inventory_invalid")
    expected_keys = {"species_id", "grid_cell_id", "microcluster", "pa", "pa_type"}
    require(all(isinstance(row, dict) and set(row) == expected_keys for row in rows), "response_snapshot_not_minimal")
    require(assessment.get("private_response_snapshot_digest") == snapshot["receipt_digest"], "assessment_snapshot_link_invalid")
    return closure, access, snapshot, assessment


def prediction_panels(root: Path, private: Path, closure: Mapping[str, Any]) -> dict[str, dict[str, np.ndarray]]:
    records = closure.get("files")
    require(isinstance(records, list) and len(records) == 8, "prediction_file_inventory_invalid")
    index = {row.get("species"): row for row in records if isinstance(row, dict)}
    require(set(index) == set(SPECIES), "prediction_species_inventory_invalid")
    expected = {
        "grid_cell_id", "patch", "primary_scores", "sensitivity_scores", "primary_thresholds",
        "sensitivity_thresholds", "map_grid_cell_id", "primary_map_scores", "sensitivity_map_scores",
    }
    result: dict[str, dict[str, np.ndarray]] = {}
    held_total = 0
    for species in SPECIES:
        path = private / "predictions" / f"{species}.npz"
        require(sha256_file(path) == index[species].get("sha256"), f"prediction_sha256_mismatch:{species}")
        arrays = read_npz(path, expected)
        ids = validate_ids(arrays["grid_cell_id"], label=f"held_ids:{species}")
        require(arrays["patch"].shape == ids.shape and arrays["patch"].dtype.kind == "U", f"held_patch_invalid:{species}")
        require(arrays["primary_scores"].shape == arrays["sensitivity_scores"].shape == (7, 3, len(ids)), f"held_score_shape_invalid:{species}")
        require(arrays["primary_scores"].dtype == arrays["sensitivity_scores"].dtype == np.float64, f"held_score_dtype_invalid:{species}")
        require(
            np.isfinite(arrays["primary_scores"]).all() and np.isfinite(arrays["sensitivity_scores"]).all()
            and np.all((arrays["primary_scores"] >= 0) & (arrays["primary_scores"] <= 1))
            and np.all((arrays["sensitivity_scores"] >= 0) & (arrays["sensitivity_scores"] <= 1)),
            f"held_score_probability_invalid:{species}",
        )
        require(arrays["primary_thresholds"].shape == arrays["sensitivity_thresholds"].shape == (7, 3), f"threshold_shape_invalid:{species}")
        require(arrays["primary_thresholds"].dtype == arrays["sensitivity_thresholds"].dtype == np.float64, f"threshold_dtype_invalid:{species}")
        require(np.isfinite(arrays["primary_thresholds"]).all() and np.isfinite(arrays["sensitivity_thresholds"]).all(), f"threshold_nonfinite:{species}")
        validate_ids(arrays["map_grid_cell_id"], label=f"map_ids:{species}", expected_length=EXPECTED_MAP_ROWS)
        require(arrays["primary_map_scores"].shape == arrays["sensitivity_map_scores"].shape == (3, EXPECTED_MAP_ROWS), f"map_score_shape_invalid:{species}")
        require(arrays["primary_map_scores"].dtype == arrays["sensitivity_map_scores"].dtype == np.float64, f"map_score_dtype_invalid:{species}")
        require(
            np.isfinite(arrays["primary_map_scores"]).all() and np.isfinite(arrays["sensitivity_map_scores"]).all()
            and np.all((arrays["primary_map_scores"] >= 0) & (arrays["primary_map_scores"] <= 1))
            and np.all((arrays["sensitivity_map_scores"] >= 0) & (arrays["sensitivity_map_scores"] <= 1)),
            f"map_score_probability_invalid:{species}",
        )
        held_total += len(ids)
        result[species] = arrays
    require(held_total == EXPECTED_HELD_ROWS, "prediction_held_row_total_invalid")
    return result


def load_primary_authority(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, np.ndarray]], dict[tuple[str, str], str]]:
    """Authenticate and reconstruct the accepted primary held panel."""
    receipt_path = root / "evidence/tasmania_outer_assessment/20261005/receipt.json"
    closure_path = root / BASELINE_REL / "prediction-closure.json"
    receipt = read_receipt(receipt_path)
    closure = read_receipt(closure_path)
    require(receipt.get("receipt_digest") == BASELINE_RECEIPT_DIGEST, "accepted_baseline_receipt_changed")
    require(closure.get("receipt_digest") == BASELINE_CLOSURE_DIGEST, "accepted_baseline_closure_changed")
    require(receipt.get("prediction_closure_digest") == closure["receipt_digest"], "baseline_receipt_closure_link_invalid")
    require(
        closure.get("schema_version") == "tasmania-prediction-closure-v1"
        and closure.get("status") == "predictions_closed_before_response" and closure.get("success") is True
        and closure.get("labels_read") == 0 and closure.get("response_rows_read") == 0,
        "baseline_prediction_closure_invalid",
    )
    files = closure.get("files")
    require(isinstance(files, list) and len(files) == 32 and digest_value(files) == closure.get("file_inventory_digest"), "baseline_file_inventory_invalid")
    observed: set[tuple[str, str]] = set()
    for row in files:
        require(isinstance(row, dict) and {"role", "sha256", "species"} <= set(row), "baseline_file_record_invalid")
        role, species = row["role"], row["species"]
        require(role in {"input", "neural", "conventional", "averaged"} and species in SPECIES, "baseline_file_identity_invalid")
        expected_fields = {"role", "sha256", "species"}
        if role == "averaged":
            expected_fields |= {"neural_mean_digest", "conventional_mean_digest"}
        require(set(row) == expected_fields, "baseline_file_record_invalid")
        path = root / BASELINE_REL / ("inputs" if role == "input" else f"predictions/{role}") / f"{species}.npz"
        require(path.is_file() and not path.is_symlink() and sha256_file(path) == row["sha256"], f"baseline_file_sha256_mismatch:{role}:{species}")
        observed.add((role, species))
    require(observed == {(role, species) for role in ("input", "neural", "conventional", "averaged") for species in SPECIES}, "baseline_file_crossproduct_invalid")

    config_path = root / "config/tasmania_outer_assessment.json"
    require(sha256_file(config_path) == receipt.get("config_digest") == closure.get("config_digest"), "baseline_config_binding_invalid")
    config = read_json(config_path)
    tables: dict[str, list[dict[str, Any]]] = {}
    for name in ("goal036_stratum_metrics", "goal036_conventional_selection"):
        binding = config.get("authorities", {}).get(name)
        require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}, f"baseline_authority_binding_invalid:{name}")
        table_path = safe_bound_path(root, binding["path"])
        require(sha256_file(table_path) == binding["sha256"], f"baseline_authority_sha256_mismatch:{name}")
        tables[name] = read_csv(table_path)
    thresholds = {
        (row["species"], row["endpoint"], row["method"]): float(row["threshold"])
        for row in tables["goal036_stratum_metrics"]
    }
    selected = {
        (row["species"], row["endpoint"]): str(row["selected_family"])
        for row in tables["goal036_conventional_selection"]
    }
    require(len(selected) == 56, "baseline_conventional_selection_invalid")

    primary: dict[str, dict[str, np.ndarray]] = {}
    for species in SPECIES:
        input_path = root / BASELINE_REL / "inputs" / f"{species}.npz"
        try:
            with np.load(input_path, allow_pickle=False) as loaded:
                require({"grid_cell_id", "patch"} <= set(loaded.files), f"baseline_input_arrays_missing:{species}")
                ids = validate_ids(np.array(loaded["grid_cell_id"], copy=True), label=f"baseline_ids:{species}")
                patch = np.array(loaded["patch"], copy=True)
        except AuditError:
            raise
        except (OSError, ValueError) as exc:
            raise AuditError(f"baseline_input_invalid:{species}") from exc
        require(patch.shape == ids.shape and patch.dtype.kind == "U", f"baseline_patch_invalid:{species}")
        means = read_npz(
            root / BASELINE_REL / "predictions/averaged" / f"{species}.npz",
            {"neural_mean", "conventional_mean"},
        )
        require(means["neural_mean"].shape == (7, 6, len(ids)) and means["neural_mean"].dtype == np.float64, f"baseline_neural_mean_invalid:{species}")
        require(means["conventional_mean"].shape == (7, 5, len(ids)) and means["conventional_mean"].dtype == np.float64, f"baseline_conventional_mean_invalid:{species}")
        scores = np.empty((7, 3, len(ids)), dtype=np.float64)
        threshold_array = np.empty((7, 3), dtype=np.float64)
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            family = selected[species, endpoint]
            require(family in BASE_CONVENTIONAL, f"baseline_selected_family_invalid:{species}:{endpoint}")
            for method_index, method in enumerate(METHODS):
                if method in NEURAL_METHODS:
                    scores[endpoint_index, method_index] = means["neural_mean"][endpoint_index, BASE_NEURAL.index(method)]
                    threshold_method = method
                else:
                    scores[endpoint_index, method_index] = means["conventional_mean"][endpoint_index, BASE_CONVENTIONAL.index(family)]
                    threshold_method = f"conventional/{family}"
                key = (species, endpoint, threshold_method)
                require(key in thresholds, f"baseline_threshold_missing:{species}:{endpoint}:{method}")
                threshold_array[endpoint_index, method_index] = thresholds[key]
        primary[species] = {
            "grid_cell_id": ids, "patch": patch,
            "primary_scores": scores, "primary_thresholds": threshold_array,
        }
    return receipt, closure, primary, selected


def validate_primary_panels(
    panels: Mapping[str, Mapping[str, np.ndarray]],
    primary: Mapping[str, Mapping[str, np.ndarray]],
) -> None:
    for species in SPECIES:
        panel, accepted = panels[species], primary[species]
        panel_ids = validate_ids(panel["grid_cell_id"], label=f"primary_panel_ids:{species}")
        accepted_ids = validate_ids(accepted["grid_cell_id"], label=f"accepted_primary_ids:{species}")
        require(set(panel_ids.tolist()) == set(accepted_ids.tolist()) and len(panel_ids) == len(accepted_ids), f"primary_membership_changed:{species}")
        lookup = {str(cell): index for index, cell in enumerate(accepted_ids)}
        indices = np.asarray([lookup[str(cell)] for cell in panel_ids], dtype=np.int64)
        require(np.array_equal(panel["patch"], accepted["patch"][indices]), f"primary_patch_changed:{species}")
        require(np.array_equal(panel["primary_scores"], accepted["primary_scores"][:, :, indices]), f"primary_scores_changed:{species}")
        require(np.array_equal(panel["primary_thresholds"], accepted["primary_thresholds"]), f"primary_thresholds_changed:{species}")


def validate_thylogale_negative_control(
    closure: Mapping[str, Any], panels: Mapping[str, Mapping[str, np.ndarray]],
) -> None:
    require(
        closure.get("thylogale_exact_negative_controls")
        == {"held_scores": 21, "thresholds": 21, "maps": 3},
        "thylogale_negative_control_inventory_invalid",
    )
    arrays = panels["thylogale_billardierii"]
    for suffix in ("scores", "thresholds", "map_scores"):
        require(
            np.array_equal(arrays[f"primary_{suffix}"], arrays[f"sensitivity_{suffix}"]),
            f"thylogale_negative_control_failed:{suffix}",
        )


def snapshot_index(snapshot: Mapping[str, Any], panels: Mapping[str, Mapping[str, np.ndarray]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    rows = snapshot["rows"]
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (str(row["species_id"]), str(row["grid_cell_id"]))
        require(key not in result, "response_snapshot_duplicate_identity")
        require(row["species_id"] in SPECIES and str(row["pa"]) in {"0", "1"}, "response_snapshot_value_invalid")
        require(row["pa_type"] in {"presence", "survey_supported_absence", "pseudoabsence"}, "response_snapshot_source_invalid")
        require((str(row["pa"]) == "1") == (row["pa_type"] == "presence"), "response_snapshot_source_class_disagreement")
        result[key] = row
    expected = {(species, str(cell)) for species, arrays in panels.items() for cell in arrays["grid_cell_id"]}
    require(set(result) == expected, "response_snapshot_prediction_membership_mismatch")
    for species, arrays in panels.items():
        for cell, patch in zip(arrays["grid_cell_id"], arrays["patch"], strict=True):
            require(result[species, str(cell)]["microcluster"] == str(patch), "response_snapshot_patch_mismatch")
    return result


def validate_primary_metrics_and_response_counts(
    baseline_receipt: Mapping[str, Any],
    panels: Mapping[str, Mapping[str, np.ndarray]],
    snapshot: Mapping[tuple[str, str], Mapping[str, Any]],
    selected_families: Mapping[tuple[str, str], str],
) -> None:
    """Anchor snapshot labels and primary replay to the accepted assessment."""
    accepted_counts_rows = baseline_receipt.get("response_counts")
    require(isinstance(accepted_counts_rows, list), "baseline_response_counts_missing")
    accepted_counts = {row.get("species"): row for row in accepted_counts_rows if isinstance(row, dict)}
    require(set(accepted_counts) == set(SPECIES) and len(accepted_counts) == len(accepted_counts_rows), "baseline_response_count_inventory_invalid")
    accepted_metrics_rows = baseline_receipt.get("metrics")
    require(isinstance(accepted_metrics_rows, list), "baseline_metrics_missing")
    pooled = [row for row in accepted_metrics_rows if isinstance(row, dict) and row.get("scope") == "pooled"]
    accepted_metrics = {
        (row.get("species"), row.get("endpoint"), row.get("model")): row for row in pooled
    }
    require(len(accepted_metrics) == len(pooled), "baseline_pooled_metric_duplicate")

    checked = 0
    for species in SPECIES:
        panel = panels[species]
        records = [snapshot[species, str(cell)] for cell in panel["grid_cell_id"]]
        labels = np.asarray([int(row["pa"]) for row in records], dtype=np.int8)
        accepted_patch_counts = accepted_counts[species].get("patch_counts")
        require(isinstance(accepted_patch_counts, dict), f"baseline_patch_counts_invalid:{species}")
        patch_counts: dict[str, int] = {str(patch): 0 for patch in accepted_patch_counts}
        for row in records:
            patch = str(row["microcluster"])
            require(patch in patch_counts, f"baseline_patch_unexpected:{species}:{patch}")
            patch_counts[patch] += 1
        observed_counts = {
            "species": species, "n": len(labels), "n_positive": int(labels.sum()),
            "n_negative": int(len(labels) - labels.sum()), "patch_counts": patch_counts,
        }
        require(observed_counts == accepted_counts[species], f"baseline_response_counts_mismatch:{species}")
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            for method_index, method in enumerate(METHODS):
                model = method if method in NEURAL_METHODS else f"conventional/{selected_families[species, endpoint]}"
                key = (species, endpoint, model)
                require(key in accepted_metrics, f"baseline_pooled_metric_missing:{species}:{endpoint}:{method}")
                accepted = accepted_metrics[key]
                replay = confusion(
                    labels, panel["primary_scores"][endpoint_index, method_index],
                    panel["primary_thresholds"][endpoint_index, method_index],
                )
                for field in ("n", "tp", "tn", "fp", "fn", "threshold"):
                    require(equal_value(replay[field], accepted.get(field), exact=True), f"baseline_primary_metric_mismatch:{species}:{endpoint}:{method}:{field}")
                for field in ("roc_auc", "tss", "mcc"):
                    require(equal_value(replay[field], accepted.get(field)), f"baseline_primary_metric_mismatch:{species}:{endpoint}:{method}:{field}")
                checked += 1
    require(checked == len(SPECIES) * len(ENDPOINTS) * len(METHODS), "baseline_primary_metric_inventory_invalid")


def group_inventory(rows: Sequence[Mapping[str, Any]], role: str) -> dict[tuple[Any, ...], list[Mapping[str, Any]]]:
    selected = [row for row in rows if row.get("role") == role]
    result: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in selected:
        task = row.get("task")
        require(isinstance(task, dict), f"source_task_invalid:{role}")
        if role.startswith("neural"):
            species = task.get("target")
            method = task.get("method")
        else:
            species = task.get("species")
            method = "selected_conventional"
        key_parts: list[Any] = [species, task.get("endpoint"), method]
        if role.endswith("inner"):
            key_parts.append(task.get("held_fold"))
        result.setdefault(tuple(key_parts), []).append(row)
    return result


def leaf_prediction(root: Path, row: Mapping[str, Any]) -> dict[str, np.ndarray]:
    path = safe_bound_path(root, row.get("prediction_path"))
    require(sha256_file(path) == row.get("prediction_sha256"), "source_leaf_prediction_sha256_mismatch")
    arrays = read_npz(path)
    require("grid_cell_id" in arrays and "scores" in arrays, "source_leaf_prediction_arrays_missing")
    return arrays


def expected_group_seeds(rows: Sequence[Mapping[str, Any]], *, neural: bool) -> tuple[Any, ...]:
    if neural:
        return NEURAL_SEEDS
    tasks = [row["task"] for row in rows]
    families = {task.get("family") for task in tasks}
    candidates = {task.get("candidate") for task in tasks}
    require(len(families) == len(candidates) == 1, "conventional_group_selection_drift")
    family = next(iter(families))
    require(family in CONVENTIONAL_SEEDS, "conventional_family_invalid")
    return CONVENTIONAL_SEEDS[family]


def reaggregate_sources(
    root: Path, private: Path, closure: Mapping[str, Any],
    panels: Mapping[str, Mapping[str, np.ndarray]],
) -> tuple[list[dict[str, Any]], dict[str, int], dict[tuple[str, str], str]]:
    """Replay normalized panels and 168 thresholds directly from source leaves."""
    inventory_path = safe_bound_path(root, closure.get("source_leaf_inventory_path"))
    require(inventory_path == (private / "source-leaf-inventory.json").resolve(), "source_inventory_location_invalid")
    require(sha256_file(inventory_path) == closure.get("source_leaf_inventory_sha256"), "source_inventory_sha256_mismatch")
    inventory = read_receipt(inventory_path)
    require(inventory.get("receipt_digest") == closure.get("source_leaf_inventory_receipt_digest"), "source_inventory_receipt_link_invalid")
    rows = inventory.get("leaves")
    require(isinstance(rows, list) and len(rows) == 4800, "source_leaf_inventory_count_invalid")
    require(digest_value(rows) == inventory.get("inventory_digest"), "source_leaf_inventory_digest_invalid")
    inner_groups = {
        **group_inventory(rows, "neural_inner"),
        **group_inventory(rows, "conventional_inner"),
    }
    outer_groups = {
        **group_inventory(rows, "neural_outer"),
        **group_inventory(rows, "conventional_outer"),
    }
    require(len(inner_groups) == 8 * 7 * 3 * 5 and len(outer_groups) == 8 * 7 * 3, "source_group_inventory_invalid")
    threshold_rows: list[dict[str, Any]] = []
    selected_families: dict[tuple[str, str], str] = {}
    manifest_path = root / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private/neural/input-manifest.json"
    manifest = read_json(manifest_path)
    manifest_body = dict(manifest)
    manifest_digest = manifest_body.pop("digest", None)
    require(
        manifest_digest == closure.get("input_manifest_digest")
        and digest_value(manifest_body) == manifest_digest,
        "input_manifest_digest_mismatch",
    )
    manifest_records = manifest.get("files")
    require(isinstance(manifest_records, list), "input_manifest_file_inventory_invalid")
    input_hashes = {row.get("path"): row.get("sha256") for row in manifest_records if isinstance(row, dict)}
    require(len(input_hashes) == len(manifest_records), "input_manifest_duplicate_path")
    inner_inputs: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    inner_root = root / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private/neural/inputs/inner"
    for species in SPECIES:
        for fold in FOLDS:
            input_path = inner_root / f"{species}--{fold}.npz"
            require(input_path.is_file() and not input_path.is_symlink(), f"inner_input_missing:{species}:{fold}")
            relative_input = str(input_path.relative_to(root))
            require(sha256_file(input_path) == input_hashes.get(relative_input), f"inner_input_sha256_mismatch:{species}:{fold}")
            try:
                with np.load(input_path, allow_pickle=False) as loaded:
                    require({"held_cells", "y_held"} <= set(loaded.files), "inner_input_arrays_missing")
                    held_ids = validate_ids(np.array(loaded["held_cells"], copy=True), label=f"inner_input_ids:{species}:{fold}")
                    labels = np.array(loaded["y_held"], copy=True)
            except AuditError:
                raise
            except (OSError, ValueError) as exc:
                raise AuditError(f"inner_input_invalid:{species}:{fold}") from exc
            require(labels.shape == held_ids.shape and np.isin(labels, (0, 1)).all(), "inner_input_labels_invalid")
            inner_inputs[species, fold] = held_ids, labels.astype(np.int8)

    for species in SPECIES:
        panel = panels[species]
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            for method_index, method in enumerate(METHODS):
                neural = method in NEURAL_METHODS
                folds_scores: list[np.ndarray] = []
                folds_labels: list[np.ndarray] = []
                for fold in FOLDS:
                    group = inner_groups.get((species, endpoint, method, fold), [])
                    seeds = expected_group_seeds(group, neural=neural)
                    held_ids, labels = inner_inputs[species, fold]
                    records = []
                    for row in group:
                        payload = leaf_prediction(root, row)
                        seed = row["task"].get("seed" if neural else "seed_label")
                        records.append((seed, payload["grid_cell_id"], payload["scores"]))
                    folds_scores.append(seed_mean(records, seeds, held_ids, label=f"oof:{species}:{endpoint}:{method}:{fold}"))
                    folds_labels.append(labels)
                pooled_scores = np.concatenate(folds_scores).astype(np.float64, copy=False)
                pooled_labels = np.concatenate(folds_labels).astype(np.int8, copy=False)
                threshold = select_threshold(pooled_labels, pooled_scores)
                require(threshold["threshold"] == panel["sensitivity_thresholds"][endpoint_index, method_index], f"normalized_threshold_mismatch:{species}:{endpoint}:{method}")
                threshold_rows.append({
                    "species": species, "endpoint": endpoint, "method": method,
                    **threshold, "oof_rows": len(pooled_labels),
                })
                group = outer_groups.get((species, endpoint, method), [])
                seeds = expected_group_seeds(group, neural=neural)
                if not neural:
                    families = {row["task"].get("family") for row in group}
                    require(len(families) == 1, "conventional_outer_family_drift")
                    selected_families[species, endpoint] = str(next(iter(families)))
                held_records = []
                outer_payloads = []
                for row in group:
                    payload = leaf_prediction(root, row)
                    outer_payloads.append((row, payload))
                    seed = row["task"].get("seed" if neural else "seed_label")
                    held_records.append((seed, payload["grid_cell_id"], payload["scores"]))
                held_mean = seed_mean(held_records, seeds, panel["grid_cell_id"], label=f"outer:{species}:{endpoint}:{method}")
                require(np.array_equal(held_mean, panel["sensitivity_scores"][endpoint_index, method_index]), f"normalized_held_mean_mismatch:{species}:{endpoint}:{method}")

                if endpoint == "fraction100/full":
                    sensitivity_name = "sensitivity_map_scores" if neural else "map_scores"
                    primary_name = "accepted_primary_map_scores" if neural else "baseline_map_scores"
                    sensitivity_records, primary_records = [], []
                    for row, payload in outer_payloads:
                        seed = row["task"].get("seed" if neural else "seed_label")
                        require("map_grid_cell_id" in payload and sensitivity_name in payload and primary_name in payload, "source_map_arrays_missing")
                        sensitivity_records.append((seed, payload["map_grid_cell_id"], payload[sensitivity_name]))
                        primary_records.append((seed, payload["map_grid_cell_id"], payload[primary_name]))
                    map_ids = panel["map_grid_cell_id"]
                    sensitivity_mean = seed_mean(sensitivity_records, seeds, map_ids, label=f"sensitivity_map:{species}:{method}")
                    primary_mean = seed_mean(primary_records, seeds, map_ids, label=f"primary_map:{species}:{method}")
                    require(np.array_equal(sensitivity_mean, panel["sensitivity_map_scores"][method_index]), f"normalized_sensitivity_map_mismatch:{species}:{method}")
                    require(np.array_equal(primary_mean, panel["primary_map_scores"][method_index]), f"normalized_primary_map_mismatch:{species}:{method}")
    require(len(threshold_rows) == 168, "independent_threshold_inventory_invalid")
    threshold_path = safe_bound_path(root, closure.get("threshold_details_path"))
    require(threshold_path == (private / "threshold-details.csv").resolve(), "threshold_details_location_invalid")
    threshold_table = read_csv(threshold_path)
    require(sha256_file(threshold_path) == closure.get("threshold_details_sha256"), "threshold_details_sha256_mismatch")
    compare_rows(
        threshold_table, threshold_rows, ("species", "endpoint", "method"),
        exact_fields=("threshold", "maximizer_count", "candidate_count", "oof_rows"), label="threshold_details",
    )
    require(len(selected_families) == 56, "conventional_selection_inventory_invalid")
    return threshold_rows, {"source_leaves": len(rows), "normalized_held_panels": 168, "normalized_map_pairs": 24, "oof_thresholds": 168}, selected_families


def recompute_aggregates(
    panels: Mapping[str, Mapping[str, np.ndarray]],
    snapshot: Mapping[tuple[str, str], Mapping[str, Any]],
    selected_families: Mapping[tuple[str, str], str],
) -> dict[str, list[dict[str, Any]]]:
    performance: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    contrast_rows: list[dict[str, Any]] = []
    maps: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []
    for species in SPECIES:
        panel = panels[species]
        records = [snapshot[species, str(cell)] for cell in panel["grid_cell_id"]]
        labels = np.asarray([int(row["pa"]) for row in records], dtype=np.int8)
        sources = np.asarray([row["pa_type"] for row in records])
        counts.append({
            "species": species, "rows": len(labels), "positive": int(labels.sum()),
            "survey_supported_absence": int(np.sum(sources == "survey_supported_absence")),
            "pseudoabsence": int(np.sum(sources == "pseudoabsence")),
        })
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            metric_cache: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
            for method_index, method in enumerate(METHODS):
                primary = confusion(labels, panel["primary_scores"][endpoint_index, method_index], panel["primary_thresholds"][endpoint_index, method_index])
                sensitivity = confusion(labels, panel["sensitivity_scores"][endpoint_index, method_index], panel["sensitivity_thresholds"][endpoint_index, method_index])
                metric_cache[method] = (primary, sensitivity)
                row: dict[str, Any] = {
                    "species": species, "endpoint": endpoint, "method": method,
                    "selected_conventional_family": selected_families[species, endpoint] if method == "selected_conventional" else None,
                    "n": len(labels), "n_positive": int(labels.sum()), "n_negative": int(len(labels) - labels.sum()),
                }
                for metric in ("threshold", "roc_auc", "tss", "mcc"):
                    row[f"primary_{metric}"] = primary[metric]
                    row[f"sensitivity_{metric}"] = sensitivity[metric]
                    row[f"delta_{metric}"] = sensitivity[metric] - primary[metric]
                performance.append(row)
                primary_source = source_specificity(labels, sources, panel["primary_scores"][endpoint_index, method_index], primary["threshold"])
                sensitivity_source = source_specificity(labels, sources, panel["sensitivity_scores"][endpoint_index, method_index], sensitivity["threshold"])
                for source in ("survey_supported_absence", "pseudoabsence"):
                    before, after = primary_source[source], sensitivity_source[source]
                    source_rows.append({
                        "species": species, "endpoint": endpoint, "method": method, "absence_source": source,
                        "denominator": before["denominator"], "primary_true_negative": before["true_negative"],
                        "sensitivity_true_negative": after["true_negative"], "primary_specificity": before["specificity"],
                        "sensitivity_specificity": after["specificity"],
                        "delta_specificity": None if before["denominator"] == 0 else after["specificity"] - before["specificity"],
                    })
            for comparator in ("target_only_resmlp", "selected_conventional"):
                for metric in ("roc_auc", "tss", "mcc"):
                    primary_contrast = metric_cache["multihead_full_finetune"][0][metric] - metric_cache[comparator][0][metric]
                    sensitivity_contrast = metric_cache["multihead_full_finetune"][1][metric] - metric_cache[comparator][1][metric]
                    contrast_rows.append({
                        "species": species, "endpoint": endpoint,
                        "contrast": f"multihead_full_finetune_minus_{comparator}", "metric": metric,
                        "primary_contrast": primary_contrast, "sensitivity_contrast": sensitivity_contrast,
                        "change_in_contrast": sensitivity_contrast - primary_contrast,
                    })
        for method_index, method in enumerate(METHODS):
            maps.append({
                "species": species, "endpoint": "fraction100/full", "method": method,
                **map_summary(panel["map_grid_cell_id"], panel["primary_map_scores"][method_index], panel["sensitivity_map_scores"][method_index]),
            })
    require(len(performance) == 168 and len(source_rows) == 336 and len(contrast_rows) == 336 and len(maps) == 24 and len(counts) == 8, "recomputed_aggregate_inventory_invalid")
    return {
        "paired-performance.csv": performance, "source-specificity.csv": source_rows,
        "paired-contrasts.csv": contrast_rows, "map-comparison.csv": maps,
        "held-source-counts.csv": counts,
    }


def compare_aggregates(evidence: Path, expected: Mapping[str, list[dict[str, Any]]]) -> None:
    specifications = {
        "paired-performance.csv": (("species", "endpoint", "method"), {"n", "n_positive", "n_negative", "primary_threshold", "sensitivity_threshold", "delta_threshold"}),
        "source-specificity.csv": (("species", "endpoint", "method", "absence_source"), {"denominator", "primary_true_negative", "sensitivity_true_negative"}),
        "paired-contrasts.csv": (("species", "endpoint", "contrast", "metric"), set()),
        "map-comparison.csv": (("species", "endpoint", "method"), {"domain_cells", "top_decile_intersection", "top_decile_denominator"}),
        "held-source-counts.csv": (("species",), {"rows", "positive", "survey_supported_absence", "pseudoabsence"}),
    }
    for name, rows in expected.items():
        keys, exact_fields = specifications[name]
        actual = read_csv(evidence / name)
        compare_rows(actual, rows, keys, exact_fields=exact_fields, label=name)


def default_source_validator(closure: Mapping[str, Any], private: Path, root: Path) -> Mapping[str, Any]:
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from tasmania_pseudoabsence_collect import verify_closed_sources

    return verify_closed_sources(closure, private=private, root=root)


def write_receipt(path: Path, body: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(body)
    value["receipt_digest"] = digest_value(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
    except FileExistsError as exc:
        raise AuditError(f"independent_output_exists:{path}") from exc
    return value


def verify(
    root: Path = ROOT, *, execute: bool = False,
    source_validator: Callable[[Mapping[str, Any], Path, Path], Mapping[str, Any]] = default_source_validator,
) -> dict[str, Any]:
    """Run the post-assessment replay.  No canonical response path is accepted."""
    require(execute, "independent_audit_requires_explicit_execute_gate")
    root = root.resolve()
    private = root / PRIVATE_REL
    evidence = root / EVIDENCE_REL
    output = evidence / OUTPUT_NAME
    require(not output.exists(), "independent_output_already_exists")

    # These four immutable artifacts are the startup gate.  In particular, an
    # absent assessment refuses before importing the collector or reading any
    # source leaf, snapshot row, or prediction payload.
    closure, access, snapshot_receipt, assessment = validate_post_assessment_gate(root, private, evidence)
    source_closure_paths = validate_bound_records(root, closure.get("source_closures"), label="source_closure")
    source_binding_paths = validate_bound_records(root, closure.get("source_bindings"), label="source_binding")
    require(
        set(source_closure_paths) == {
            "neural_inner", "neural_outer", "conventional_inner", "conventional_outer",
            "neural_smoke", "conventional_smoke", "recovery",
        },
        "source_closure_role_inventory_invalid",
    )
    require(
        set(source_binding_paths) == {
            "neural_complete", "neural_preparation", "neural_caps",
            "conventional_preparation", "conventional_caps", "neural_runner",
            "conventional_runner", "input_manifest", "input_helper",
            "assessment_source", "metrics_source", "collector_source",
        },
        "source_binding_role_inventory_invalid",
    )
    source_result = source_validator(closure, private, root)
    require(source_result.get("status") == "pass" and source_result.get("outer_held_response_labels_read") == 0, "collector_source_validation_failed")
    require(
        source_result.get("source_leaves") == 4800
        and source_result.get("smoke_leaves") == 8
        and source_result.get("verified_map_pairs") == 24
        and source_result.get("verified_held_panels") == 168
        and source_result.get("verified_thresholds") == 168,
        "collector_source_validation_inventory_invalid",
    )

    panels = prediction_panels(root, private, closure)
    baseline_receipt, baseline_closure, primary, baseline_selected = load_primary_authority(root)
    validate_primary_panels(panels, primary)
    validate_thylogale_negative_control(closure, panels)
    _thresholds, reaggregation, selected_families = reaggregate_sources(root, private, closure, panels)
    require(selected_families == baseline_selected, "conventional_selection_changed_from_baseline")
    snapshot = snapshot_index(snapshot_receipt, panels)
    validate_primary_metrics_and_response_counts(
        baseline_receipt, panels, snapshot, selected_families,
    )
    aggregates = recompute_aggregates(panels, snapshot, selected_families)
    compare_aggregates(evidence, aggregates)

    body = {
        "schema_version": "tasmania-pseudoabsence-independent-assessment-verification-v1",
        "status": "pass", "completed_at": datetime.now(timezone.utc).isoformat(),
        "prediction_closure_digest": closure["receipt_digest"],
        "assessment_receipt_digest": assessment["receipt_digest"],
        "response_access_digest": access["receipt_digest"],
        "private_response_snapshot_digest": snapshot_receipt["receipt_digest"],
        "audit_source_sha256": sha256_file(Path(__file__).resolve()),
        "verified_counts": {
            "target_physical_fits": 8125, "smoke_physical_fits": 14,
            "recovery_physical_fits": 200, "source_closure_files": len(source_closure_paths),
            "source_binding_files": len(source_binding_paths), "source_leaves": 4800,
            "smoke_leaves": 8, "normalized_prediction_files": 8,
            "species": 8, "endpoints": 7, "methods": 3,
            "held_rows": EXPECTED_HELD_ROWS, "map_domain_cells": EXPECTED_MAP_ROWS,
        },
        "verified_hashes": {
            "receipts": {
                "prediction_closure.json": sha256_file(private / "prediction-closure.json"),
                "response-access.json": sha256_file(private / "response-access.json"),
                "held-response-snapshot.json": sha256_file(private / "held-response-snapshot.json"),
                "assessment.json": sha256_file(evidence / "assessment.json"),
                "source-leaf-inventory.json": closure["source_leaf_inventory_sha256"],
                "threshold-details.csv": closure["threshold_details_sha256"],
                "accepted-baseline-receipt.json": sha256_file(root / "evidence/tasmania_outer_assessment/20261005/receipt.json"),
                "accepted-baseline-prediction-closure.json": sha256_file(root / BASELINE_REL / "prediction-closure.json"),
            },
            "public_aggregates": {
                Path(row["path"]).name: row["sha256"] for row in assessment["files"]
            },
            "normalized_predictions": {
                row["species"]: row["sha256"] for row in closure["files"]
            },
            "source_closures": {
                role: sha256_file(path) for role, path in source_closure_paths.items()
            },
            "source_bindings": {
                role: sha256_file(path) for role, path in source_binding_paths.items()
            },
        },
        "collector_source_validation": {
            "status": source_result["status"],
            "source_leaves": source_result.get("source_leaves"),
            "smoke_leaves": source_result.get("smoke_leaves"),
            "verified_map_pairs": source_result.get("verified_map_pairs"),
            "verified_held_panels": source_result.get("verified_held_panels"),
            "verified_thresholds": source_result.get("verified_thresholds"),
            "actual_physical_fit_starts": source_result.get("actual_physical_fit_starts"),
        },
        "accepted_primary_replay": {
            "baseline_receipt_digest": baseline_receipt["receipt_digest"],
            "baseline_prediction_closure_digest": baseline_closure["receipt_digest"],
            "held_score_panels": 168, "thresholds": 168,
            "conventional_selections": 56, "pooled_metrics": 168,
            "species_response_count_rows": 8,
        },
        "independent_reaggregation": reaggregation,
        "independent_numerical_replay": {
            "paired_performance_rows": 168, "source_specificity_rows": 336,
            "paired_contrast_rows": 336, "map_summary_rows": 24,
            "held_source_count_rows": 8, "oof_thresholds": 168,
            "integer_and_threshold_comparison": "exact",
            "thylogale_exact_negative_controls": {"held_scores": 21, "thresholds": 21, "maps": 3},
            "independent_float_absolute_tolerance": FLOAT_TOLERANCE,
            "auc": "rank-U with one-based average tie ranks",
            "mcc": "manual confusion-count formula; zero denominator returns zero",
            "map_rank": "average ties",
            "rank_displacement": "100 * (midrank_after - midrank_before) / (71023 - 1)",
            "quantiles": "linear interpolation",
            "top_cells": "7103 by descending mean probability then ascending canonical cell ID",
            "seed_aggregation": "identity-aligned float64 mean",
            "threshold_rule": "Goal036 candidates, exact maximum TSS, lower median maximizer",
        },
        "privacy": {"aggregate_only": True, "response_rows_emitted": False, "coordinates_emitted": False},
        "interpretation": "noncausal post hoc paired sensitivity on a fixed held panel; no inferential interval or independent-species claim",
    }
    return write_receipt(output, body)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify",))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    result = verify(execute=args.execute)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
