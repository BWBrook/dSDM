"""Independent replay for the post hoc Tasmania survey-only evaluation.

The command authenticates the frozen plan, accepted sensitivity assessment,
independent assessment audit, response-free prediction closure, minimal held
snapshot and eight normalized prediction files before reading any held row.
It then computes the survey-supported-absence panel without importing the
production survey-only implementation or the project's metric helpers.

No model fitting, threshold selection, canonical response access, or row-level
public output occurs here.  The public receipt is written only after an exact
inventory comparison and numerical comparison with the production aggregates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PLAN_REL = Path("docs/plan/TasmaniaSurveyOnlyEvaluation-20261011.md")
EVIDENCE_20261009_REL = Path("evidence/tasmania_pseudoabsence/20261009")
OUTPUT_REL = Path("evidence/tasmania_pseudoabsence/20261011/survey-only")
PRIVATE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/assessment")

PLAN_SHA256 = "b7c57ba7d6c554027fc7c5a37c69af0dca4db9d511e52fa296a7910d16a9e8d8"
ASSESSMENT_FILE_SHA256 = "514b574a046d3773c707adc77143e2072d90ffbb6187ccffd83248ac2603dde7"
ASSESSMENT_RECEIPT_DIGEST = "08915652195df252b062163df189f892b72ccdf1e66dab29cb4908d3b696ab56"
AUDIT_FILE_SHA256 = "3c176093ecfd47e166c5ab99ad007e3107b082c2cc9bb8136ab69d2e96cb091f"
AUDIT_RECEIPT_DIGEST = "d90a01ad2ac08ef36ff2c40bf7bce9223589011111cc2c67c124e399481ac3be"
PREDICTION_CLOSURE_DIGEST = "428ea31c0147b315280eaee8181ce2ebb4808762e4facaf1decd5a5d01462f62"
RESPONSE_ACCESS_DIGEST = "166d6163392271aca7156637d385b7506858424e4c5e4fe273bc3db90b64681b"
SNAPSHOT_DIGEST = "3fa5a5acbb7481e9d69ae4a65d5aaf7df41d830e9af811788d1b90765ce5f310"
RESPONSE_SHA256 = "b93fbdfa4df2b2d8617dd890cdb7fc4c3aa54ed10c72eed9c9ebc93df18edafc"

SPECIES = (
    "thylogale_billardierii",
    "notamacropus_rufogriseus",
    "trichosurus_vulpecula",
    "pseudocheirus_peregrinus",
    "vombatus_ursinus",
    "sarcophilus_harrisii",
    "dasyurus_maculatus",
    "dasyurus_viverrinus",
)
ENDPOINTS = (
    "fraction25/ladder00",
    "fraction25/ladder01",
    "fraction25/ladder02",
    "fraction50/ladder00",
    "fraction50/ladder01",
    "fraction50/ladder02",
    "fraction100/full",
)
METHODS = (
    "target_only_resmlp",
    "multihead_full_finetune",
    "selected_conventional",
)
PHASES = ("primary", "sensitivity")
PANELS = ("original_mixed", "survey_only")
METRICS = (
    "roc_auc",
    "tss",
    "mcc",
    "balanced_accuracy",
    "sensitivity",
    "specificity",
)
CONTRAST_METRICS = ("roc_auc", "tss", "mcc")
CONTRASTS = (
    ("multihead_full_finetune_minus_target_only_resmlp", "multihead_full_finetune", "target_only_resmlp"),
    ("multihead_full_finetune_minus_selected_conventional", "multihead_full_finetune", "selected_conventional"),
)
EXPECTED_HELD_ROWS = 1672
FLOAT_TOLERANCE = 1e-12


class AuditError(RuntimeError):
    """Raised when any provenance or numerical audit condition fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    require(target.is_file() and not target.is_symlink(), f"json_missing:{target}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"json_invalid:{target}") from exc
    require(isinstance(value, dict), f"json_object_required:{target}")
    return value


def validate_receipt(value: Mapping[str, Any], *, label: str) -> None:
    body = dict(value)
    claimed = body.pop("receipt_digest", None)
    require(isinstance(claimed, str) and len(claimed) == 64, f"{label}_receipt_digest_missing")
    require(digest_value(body) == claimed, f"{label}_receipt_digest_mismatch")


def read_receipt(path: str | Path, *, label: str) -> dict[str, Any]:
    value = read_json(path)
    validate_receipt(value, label=label)
    return value


def bound_file(root: Path, relative: Any, *, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"{label}_path_invalid")
    unresolved = root / relative
    require(unresolved.is_file() and not unresolved.is_symlink(), f"{label}_missing:{relative}")
    resolved_root = root.resolve()
    target = unresolved.resolve()
    require(target != resolved_root and resolved_root in target.parents, f"{label}_outside_root:{relative}")
    return target


def verify_bound_records(root: Path, records: Any, *, label: str) -> dict[str, str]:
    require(isinstance(records, list) and records, f"{label}_inventory_invalid")
    observed: dict[str, str] = {}
    for row in records:
        require(isinstance(row, dict), f"{label}_record_invalid")
        role = row.get("role")
        require(isinstance(role, str) and role and role not in observed, f"{label}_role_invalid")
        target = bound_file(root, row.get("path"), label=f"{label}:{role}")
        actual = sha256_file(target)
        require(actual == row.get("sha256"), f"{label}_sha256_mismatch:{role}")
        observed[role] = actual
    return observed


def read_npz(path: str | Path) -> dict[str, np.ndarray]:
    target = Path(path)
    require(target.is_file() and not target.is_symlink(), f"npz_missing:{target}")
    try:
        with np.load(target, allow_pickle=False) as archive:
            return {name: np.array(archive[name], copy=True) for name in archive.files}
    except (OSError, ValueError) as exc:
        raise AuditError(f"npz_invalid:{target}") from exc


def as_unique_ids(values: Any, *, label: str) -> np.ndarray:
    result = np.asarray(values)
    require(result.ndim == 1 and result.dtype.kind in "US", f"{label}_invalid")
    require(len(set(result.tolist())) == len(result), f"{label}_duplicate")
    return result


def authenticate_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Authenticate all public and response-free gates before snapshot parsing."""
    plan_path = root / PLAN_REL
    evidence = root / EVIDENCE_20261009_REL
    private = root / PRIVATE_REL
    assessment_path = evidence / "assessment.json"
    audit_path = evidence / "independent-assessment-verification.json"
    closure_path = private / "prediction-closure.json"
    access_path = private / "response-access.json"
    snapshot_path = private / "held-response-snapshot.json"

    require(sha256_file(plan_path) == PLAN_SHA256, "frozen_plan_sha256_mismatch")
    require(sha256_file(assessment_path) == ASSESSMENT_FILE_SHA256, "accepted_assessment_file_sha256_mismatch")
    require(sha256_file(audit_path) == AUDIT_FILE_SHA256, "accepted_audit_file_sha256_mismatch")

    assessment = read_receipt(assessment_path, label="assessment")
    audit = read_receipt(audit_path, label="accepted_audit")
    require(assessment.get("receipt_digest") == ASSESSMENT_RECEIPT_DIGEST, "accepted_assessment_receipt_changed")
    require(audit.get("receipt_digest") == AUDIT_RECEIPT_DIGEST, "accepted_audit_receipt_changed")
    require(audit.get("assessment_receipt_digest") == assessment["receipt_digest"], "audit_assessment_link_invalid")
    require(assessment.get("success") is True and audit.get("status") == "pass", "accepted_assessment_not_passed")

    expected_receipt_hashes = audit.get("verified_hashes", {}).get("receipts", {})
    require(isinstance(expected_receipt_hashes, dict), "accepted_audit_receipt_hashes_missing")
    require(sha256_file(closure_path) == expected_receipt_hashes.get("prediction_closure.json"), "closure_file_sha256_mismatch")
    require(sha256_file(access_path) == expected_receipt_hashes.get("response-access.json"), "response_access_file_sha256_mismatch")
    # Hash the snapshot before parsing any of its row payload.
    require(sha256_file(snapshot_path) == expected_receipt_hashes.get("held-response-snapshot.json"), "snapshot_file_sha256_mismatch")

    closure = read_receipt(closure_path, label="prediction_closure")
    access = read_receipt(access_path, label="response_access")
    require(closure.get("receipt_digest") == PREDICTION_CLOSURE_DIGEST, "prediction_closure_receipt_changed")
    require(access.get("receipt_digest") == RESPONSE_ACCESS_DIGEST, "response_access_receipt_changed")
    require(closure.get("schema_version") == "tasmania-pseudoabsence-prediction-closure-v1", "closure_schema_invalid")
    require(closure.get("status") == "accepted" and closure.get("outer_held_response_labels_read") == 0, "closure_boundary_invalid")
    require(assessment.get("prediction_closure_digest") == closure["receipt_digest"], "assessment_closure_link_invalid")
    require(audit.get("prediction_closure_digest") == closure["receipt_digest"], "audit_closure_link_invalid")
    require(access.get("prediction_closure_digest") == closure["receipt_digest"], "access_closure_link_invalid")
    require(access.get("response_sha256") == RESPONSE_SHA256, "access_response_source_invalid")
    require(access.get("private_snapshot_receipt_digest") == SNAPSHOT_DIGEST, "access_snapshot_link_invalid")
    require(access.get("held_rows_parsed") == EXPECTED_HELD_ROWS and access.get("training_rows_parsed") == 0, "access_row_accounting_invalid")
    require(access.get("response_parses") == 1, "access_parse_accounting_invalid")

    current_bindings = verify_bound_records(root, closure.get("source_bindings"), label="source_binding")
    current_closures = verify_bound_records(root, closure.get("source_closures"), label="source_closure")
    require(current_bindings == audit["verified_hashes"]["source_bindings"], "audit_source_binding_inventory_mismatch")
    require(current_closures == audit["verified_hashes"]["source_closures"], "audit_source_closure_inventory_mismatch")
    leaf_inventory = bound_file(root, closure.get("source_leaf_inventory_path"), label="source_leaf_inventory")
    threshold_details = bound_file(root, closure.get("threshold_details_path"), label="threshold_details")
    require(sha256_file(leaf_inventory) == closure.get("source_leaf_inventory_sha256"), "source_leaf_inventory_sha256_mismatch")
    require(sha256_file(threshold_details) == closure.get("threshold_details_sha256"), "threshold_details_sha256_mismatch")

    # Only after all preceding gates pass is the minimal snapshot parsed.
    snapshot = read_receipt(snapshot_path, label="held_snapshot")
    require(snapshot.get("receipt_digest") == SNAPSHOT_DIGEST, "snapshot_receipt_changed")
    require(snapshot.get("schema_version") == "tasmania-sensitivity-held-response-snapshot-v1", "snapshot_schema_invalid")
    require(snapshot.get("prediction_closure_digest") == closure["receipt_digest"], "snapshot_closure_link_invalid")
    require(snapshot.get("response_sha256") == RESPONSE_SHA256, "snapshot_response_source_invalid")
    require(assessment.get("private_response_snapshot_digest") == snapshot["receipt_digest"], "assessment_snapshot_link_invalid")
    require(audit.get("private_response_snapshot_digest") == snapshot["receipt_digest"], "audit_snapshot_link_invalid")
    rows = snapshot.get("rows")
    required_keys = {"species_id", "grid_cell_id", "microcluster", "pa", "pa_type"}
    require(isinstance(rows, list) and len(rows) == EXPECTED_HELD_ROWS, "snapshot_row_inventory_invalid")
    require(all(isinstance(row, dict) and set(row) == required_keys for row in rows), "snapshot_not_minimal")
    return assessment, audit, closure, access, snapshot


def load_prediction_panels(root: Path, closure: Mapping[str, Any], audit: Mapping[str, Any]) -> dict[str, dict[str, np.ndarray]]:
    private = root / PRIVATE_REL
    records = closure.get("files")
    require(isinstance(records, list) and len(records) == len(SPECIES), "prediction_file_inventory_invalid")
    by_species = {row.get("species"): row for row in records if isinstance(row, dict)}
    require(set(by_species) == set(SPECIES), "prediction_species_inventory_invalid")
    expected_hashes = audit["verified_hashes"]["normalized_predictions"]
    expected_fields = {
        "grid_cell_id", "patch", "primary_scores", "sensitivity_scores",
        "primary_thresholds", "sensitivity_thresholds", "map_grid_cell_id",
        "primary_map_scores", "sensitivity_map_scores",
    }
    result: dict[str, dict[str, np.ndarray]] = {}
    total = 0
    for species in SPECIES:
        path = private / "predictions" / f"{species}.npz"
        actual_hash = sha256_file(path)
        require(actual_hash == by_species[species].get("sha256"), f"prediction_closure_hash_mismatch:{species}")
        require(actual_hash == expected_hashes.get(species), f"prediction_audit_hash_mismatch:{species}")
        arrays = read_npz(path)
        require(set(arrays) == expected_fields, f"prediction_field_inventory_invalid:{species}")
        ids = as_unique_ids(arrays["grid_cell_id"], label=f"prediction_ids:{species}")
        require(arrays["patch"].shape == ids.shape and arrays["patch"].dtype.kind in "US", f"prediction_patch_invalid:{species}")
        require(arrays["primary_scores"].shape == arrays["sensitivity_scores"].shape == (7, 3, len(ids)), f"prediction_score_shape_invalid:{species}")
        require(arrays["primary_scores"].dtype == arrays["sensitivity_scores"].dtype == np.float64, f"prediction_score_dtype_invalid:{species}")
        require(np.isfinite(arrays["primary_scores"]).all() and np.isfinite(arrays["sensitivity_scores"]).all(), f"prediction_score_nonfinite:{species}")
        require(np.all((arrays["primary_scores"] >= 0) & (arrays["primary_scores"] <= 1)), f"primary_score_range_invalid:{species}")
        require(np.all((arrays["sensitivity_scores"] >= 0) & (arrays["sensitivity_scores"] <= 1)), f"sensitivity_score_range_invalid:{species}")
        require(arrays["primary_thresholds"].shape == arrays["sensitivity_thresholds"].shape == (7, 3), f"threshold_shape_invalid:{species}")
        require(arrays["primary_thresholds"].dtype == arrays["sensitivity_thresholds"].dtype == np.float64, f"threshold_dtype_invalid:{species}")
        require(np.isfinite(arrays["primary_thresholds"]).all() and np.isfinite(arrays["sensitivity_thresholds"]).all(), f"threshold_nonfinite:{species}")
        total += len(ids)
        result[species] = arrays
    require(total == EXPECTED_HELD_ROWS, "prediction_held_row_total_invalid")
    return result


def rank_u_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    """ROC AUC from one-based average tie ranks and the Mann-Whitney U."""
    y = np.asarray(labels, dtype=np.int8)
    s = np.asarray(scores, dtype=np.float64)
    require(y.ndim == s.ndim == 1 and y.shape == s.shape and len(y) > 0, "auc_shape_invalid")
    require(set(y.tolist()) == {0, 1} and np.isfinite(s).all(), "auc_input_invalid")
    order = np.argsort(s, kind="mergesort")
    sorted_scores = s[order]
    ranks = np.empty(len(s), dtype=np.float64)
    start = 0
    while start < len(s):
        stop = start + 1
        while stop < len(s) and sorted_scores[stop] == sorted_scores[start]:
            stop += 1
        ranks[order[start:stop]] = ((start + 1) + stop) / 2.0
        start = stop
    n_positive = int(np.sum(y == 1))
    n_negative = int(np.sum(y == 0))
    u = float(np.sum(ranks[y == 1]) - n_positive * (n_positive + 1) / 2.0)
    return u / (n_positive * n_negative)


def threshold_metrics(labels: Sequence[int], scores: Sequence[float], threshold: float) -> dict[str, float | int]:
    """Manual confusion metrics; zero MCC denominator follows accepted zero rule."""
    y = np.asarray(labels, dtype=np.int8)
    s = np.asarray(scores, dtype=np.float64)
    require(y.ndim == s.ndim == 1 and y.shape == s.shape and len(y) > 0, "threshold_shape_invalid")
    require(set(y.tolist()) == {0, 1} and np.isfinite(s).all() and math.isfinite(float(threshold)), "threshold_input_invalid")
    predicted = s >= float(threshold)
    positive = y == 1
    negative = ~positive
    tp = int(np.sum(predicted & positive))
    fn = int(np.sum(~predicted & positive))
    tn = int(np.sum(~predicted & negative))
    fp = int(np.sum(predicted & negative))
    sensitivity = tp / (tp + fn)
    specificity = tn / (tn + fp)
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ((tp * tn - fp * fn) / denominator) if denominator else 0.0
    return {
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "tss": sensitivity + specificity - 1.0,
        "balanced_accuracy": (sensitivity + specificity) / 2.0,
        "mcc": mcc,
    }


def membership_index(
    snapshot: Mapping[str, Any], panels: Mapping[str, Mapping[str, np.ndarray]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], list[dict[str, Any]]]:
    rows = snapshot["rows"]
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        species = str(row["species_id"])
        cell = str(row["grid_cell_id"])
        key = (species, cell)
        require(species in SPECIES and key not in index, "snapshot_identity_invalid")
        require(str(row["pa"]) in {"0", "1"}, "snapshot_pa_invalid")
        require(row["pa_type"] in {"presence", "survey_supported_absence", "pseudoabsence"}, "snapshot_source_invalid")
        require((str(row["pa"]) == "1") == (row["pa_type"] == "presence"), "snapshot_class_source_disagreement")
        index[key] = row
    expected = {(species, str(cell)) for species in SPECIES for cell in panels[species]["grid_cell_id"]}
    require(set(index) == expected, "snapshot_prediction_membership_mismatch")

    selected: dict[str, dict[str, list[dict[str, Any]]]] = {panel: {} for panel in PANELS}
    count_rows: list[dict[str, Any]] = []
    for species in SPECIES:
        panel = panels[species]
        ordered = [index[species, str(cell)] for cell in panel["grid_cell_id"]]
        require(all(str(row["microcluster"]) == str(patch) for row, patch in zip(ordered, panel["patch"], strict=True)), f"snapshot_patch_mismatch:{species}")
        presences = [row for row in ordered if row["pa_type"] == "presence"]
        survey = [row for row in ordered if row["pa_type"] == "survey_supported_absence"]
        pseudo = [row for row in ordered if row["pa_type"] == "pseudoabsence"]
        kept = [row for row in ordered if row["pa_type"] in {"presence", "survey_supported_absence"}]
        require(len(presences) > 0 and len(survey) > 0, f"survey_panel_lacks_both_classes:{species}")
        require(len(kept) + len(pseudo) == len(ordered), f"survey_panel_partition_invalid:{species}")
        require(sum(row["pa_type"] == "presence" for row in kept) == len(presences), f"held_presence_dropped:{species}")
        survey_membership_payload = [
            [str(row["grid_cell_id"]), str(row["microcluster"]), str(row["pa"]), str(row["pa_type"])]
            for row in kept
        ]
        original_membership_payload = [
            [str(row["grid_cell_id"]), str(row["microcluster"]), str(row["pa"]), str(row["pa_type"])]
            for row in ordered
        ]
        held_identities = sorted([[species, str(row["grid_cell_id"])] for row in ordered])
        retained_identities = sorted([[species, str(row["grid_cell_id"])] for row in kept])
        excluded_identities = sorted([[species, str(row["grid_cell_id"])] for row in pseudo])
        selected["original_mixed"][species] = ordered
        selected["survey_only"][species] = kept
        count_rows.append({
            "species": species,
            "n_original": len(ordered),
            "n_retained": len(kept),
            "n_positive": len(presences),
            "n_survey_supported_absence": len(survey),
            "n_excluded_pseudoabsence": len(pseudo),
            "original_membership_sha256": digest_value(original_membership_payload),
            "survey_membership_sha256": digest_value(survey_membership_payload),
            "held_identity_sha256": digest_value(held_identities),
            "retained_identity_sha256": digest_value(retained_identities),
            "excluded_identity_sha256": digest_value(excluded_identities),
        })
    return selected, count_rows


def read_csv(path: Path) -> list[dict[str, str]]:
    require(path.is_file() and not path.is_symlink(), f"csv_missing:{path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_source_counts(root: Path, count_rows: Sequence[Mapping[str, Any]]) -> None:
    accepted = read_csv(root / EVIDENCE_20261009_REL / "held-source-counts.csv")
    by_species = {row["species"]: row for row in accepted}
    require(set(by_species) == set(SPECIES), "accepted_source_count_species_invalid")
    for observed in count_rows:
        expected = by_species[str(observed["species"])]
        require(int(expected["rows"]) == observed["n_original"], f"source_count_rows_mismatch:{observed['species']}")
        require(int(expected["positive"]) == observed["n_positive"], f"source_count_positive_mismatch:{observed['species']}")
        require(int(expected["survey_supported_absence"]) == observed["n_survey_supported_absence"], f"source_count_survey_mismatch:{observed['species']}")
        require(int(expected["pseudoabsence"]) == observed["n_excluded_pseudoabsence"], f"source_count_pseudo_mismatch:{observed['species']}")


def compute_independent(
    panels: Mapping[str, Mapping[str, np.ndarray]],
    selected: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    count_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    counts = {str(row["species"]): row for row in count_rows}
    performance: list[dict[str, Any]] = []
    phase_panel_count = 0
    for panel_name in PANELS:
        for species in SPECIES:
            panel = panels[species]
            kept = selected[panel_name][species]
            kept_ids = [str(row["grid_cell_id"]) for row in kept]
            id_to_position = {str(cell): index for index, cell in enumerate(panel["grid_cell_id"])}
            positions = np.asarray([id_to_position[cell] for cell in kept_ids], dtype=np.int64)
            labels = np.asarray([int(str(row["pa"])) for row in kept], dtype=np.int8)
            require(int(np.sum(labels == 1)) == counts[species]["n_positive"], f"selected_presence_count_mismatch:{panel_name}:{species}")
            expected_negative = (
                counts[species]["n_survey_supported_absence"]
                + (counts[species]["n_excluded_pseudoabsence"] if panel_name == "original_mixed" else 0)
            )
            require(int(np.sum(labels == 0)) == expected_negative, f"selected_negative_count_mismatch:{panel_name}:{species}")
            for endpoint_index, endpoint in enumerate(ENDPOINTS):
                for method_index, method in enumerate(METHODS):
                    row: dict[str, Any] = {
                        "panel": panel_name,
                        "species": species,
                        "endpoint": endpoint,
                        "method": method,
                        "n": len(labels),
                        "n_positive": int(np.sum(labels == 1)),
                        "n_negative": int(np.sum(labels == 0)),
                        "n_excluded_pseudoabsence": counts[species]["n_excluded_pseudoabsence"],
                        "membership_sha256": counts[species][f"{'original' if panel_name == 'original_mixed' else 'survey'}_membership_sha256"],
                    }
                    for phase in PHASES:
                        scores = panel[f"{phase}_scores"][endpoint_index, method_index, positions]
                        threshold = float(panel[f"{phase}_thresholds"][endpoint_index, method_index])
                        metrics = threshold_metrics(labels, scores, threshold)
                        metrics["roc_auc"] = rank_u_auc(labels, scores)
                        row[f"{phase}_threshold"] = threshold
                        for name, value in metrics.items():
                            row[f"{phase}_{name}"] = value
                        phase_panel_count += 1
                    for name in METRICS:
                        row[f"delta_{name}"] = float(row[f"sensitivity_{name}"]) - float(row[f"primary_{name}"])
                    performance.append(row)
    require(phase_panel_count == 672 and len(performance) == 336, "performance_inventory_incomplete")

    lookup = {(row["panel"], row["species"], row["endpoint"], row["method"]): row for row in performance}
    contrasts: list[dict[str, Any]] = []
    for panel_name in PANELS:
        for species in SPECIES:
            for endpoint in ENDPOINTS:
                for contrast_name, left, right in CONTRASTS:
                    for metric in CONTRAST_METRICS:
                        primary = float(lookup[panel_name, species, endpoint, left][f"primary_{metric}"]) - float(lookup[panel_name, species, endpoint, right][f"primary_{metric}"])
                        sensitivity = float(lookup[panel_name, species, endpoint, left][f"sensitivity_{metric}"]) - float(lookup[panel_name, species, endpoint, right][f"sensitivity_{metric}"])
                        contrasts.append({
                            "panel": panel_name,
                            "species": species,
                            "endpoint": endpoint,
                            "contrast": contrast_name,
                            "metric": metric,
                            "primary_contrast": primary,
                            "sensitivity_contrast": sensitivity,
                            "change_in_contrast": sensitivity - primary,
                        })
    require(len(contrasts) == 672, "contrast_inventory_incomplete")

    method_summary: list[dict[str, Any]] = []
    for panel_name in PANELS:
        for endpoint in ENDPOINTS:
            for method in METHODS:
                rows = [lookup[panel_name, species, endpoint, method] for species in SPECIES]
                summary: dict[str, Any] = {"panel": panel_name, "endpoint": endpoint, "method": method, "n_species": len(rows)}
                for phase in PHASES:
                    for metric in METRICS:
                        summary[f"mean_{phase}_{metric}"] = float(np.mean([float(row[f"{phase}_{metric}"]) for row in rows]))
                for metric in METRICS:
                    summary[f"mean_delta_{metric}"] = float(np.mean([float(row[f"delta_{metric}"]) for row in rows]))
                method_summary.append(summary)
    require(len(method_summary) == 42, "method_summary_inventory_incomplete")

    contrast_lookup = {(row["panel"], row["species"], row["endpoint"], row["contrast"], row["metric"]): row for row in contrasts}
    contrast_summary: list[dict[str, Any]] = []
    for panel_name in PANELS:
        for endpoint in ENDPOINTS:
            for contrast_name, _left, _right in CONTRASTS:
                for metric in CONTRAST_METRICS:
                    rows = [contrast_lookup[panel_name, species, endpoint, contrast_name, metric] for species in SPECIES]
                    contrast_summary.append({
                        "panel": panel_name,
                        "endpoint": endpoint,
                        "contrast": contrast_name,
                        "metric": metric,
                        "n_species": len(rows),
                        "mean_primary_contrast": float(np.mean([float(row["primary_contrast"]) for row in rows])),
                        "mean_sensitivity_contrast": float(np.mean([float(row["sensitivity_contrast"]) for row in rows])),
                        "mean_change_in_contrast": float(np.mean([float(row["change_in_contrast"]) for row in rows])),
                    })
    require(len(contrast_summary) == 84, "contrast_summary_inventory_incomplete")
    return {
        "count_rows": list(count_rows),
        "performance": performance,
        "contrasts": contrasts,
        "method_summary": method_summary,
        "contrast_summary": contrast_summary,
    }


def close_enough(actual: Any, expected: Any, *, exact: bool = False) -> bool:
    if exact:
        return actual == expected
    try:
        a, e = float(actual), float(expected)
    except (TypeError, ValueError):
        return actual == expected
    return math.isfinite(a) and math.isfinite(e) and math.isclose(a, e, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE)


def verify_original_mixed_reconciliation(root: Path, independent: Mapping[str, Any]) -> None:
    """Reproduce all accepted mixed-panel performance rows independently."""
    accepted = read_csv(root / EVIDENCE_20261009_REL / "paired-performance.csv")
    accepted_index = {(row["species"], row["endpoint"], row["method"]): row for row in accepted}
    observed = [row for row in independent["performance"] if row["panel"] == "original_mixed"]
    require(len(observed) == len(accepted_index) == 168, "original_mixed_reconciliation_inventory_invalid")
    for row in observed:
        key = (row["species"], row["endpoint"], row["method"])
        expected = accepted_index[key]
        for field in ("n", "n_positive", "n_negative"):
            require(row[field] == int(expected[field]), f"original_mixed_count_mismatch:{key}:{field}")
        for field in ("primary_threshold", "sensitivity_threshold"):
            require(row[field] == float(expected[field]), f"original_mixed_threshold_mismatch:{key}:{field}")
        for phase in PHASES:
            for metric in ("roc_auc", "tss", "mcc"):
                require(
                    close_enough(row[f"{phase}_{metric}"], expected[f"{phase}_{metric}"]),
                    f"original_mixed_metric_mismatch:{key}:{phase}:{metric}",
                )


def verify_thylogale_control(root: Path, independent: Mapping[str, Any]) -> None:
    counts = {row["species"]: row for row in independent["count_rows"]}
    thy = counts["thylogale_billardierii"]
    require(thy["n_excluded_pseudoabsence"] == 0 and thy["n_original"] == thy["n_retained"], "thylogale_membership_control_failed")
    accepted = read_csv(root / EVIDENCE_20261009_REL / "paired-performance.csv")
    accepted_index = {
        (row["species"], row["endpoint"], row["method"]): row
        for row in accepted if row["species"] == "thylogale_billardierii"
    }
    observed = [row for row in independent["performance"] if row["species"] == "thylogale_billardierii"]
    require(len(observed) == 42 and len(accepted_index) == 21, "thylogale_control_inventory_invalid")
    for row in observed:
        key = (row["species"], row["endpoint"], row["method"])
        expected = accepted_index[key]
        require(row["primary_threshold"] == row["sensitivity_threshold"], f"thylogale_threshold_phase_mismatch:{key}")
        for metric in ("roc_auc", "tss", "mcc"):
            require(close_enough(row[f"primary_{metric}"], expected[f"primary_{metric}"]), f"thylogale_primary_metric_mismatch:{key}:{metric}")
            require(close_enough(row[f"sensitivity_{metric}"], expected[f"sensitivity_{metric}"]), f"thylogale_sensitivity_metric_mismatch:{key}:{metric}")
            require(close_enough(row[f"primary_{metric}"], row[f"sensitivity_{metric}"]), f"thylogale_phase_metric_mismatch:{key}:{metric}")


def headline(independent: Mapping[str, Any]) -> dict[str, Any]:
    endpoint = "fraction100/full"
    methods = {
        row["method"]: row for row in independent["method_summary"]
        if row["panel"] == "survey_only" and row["endpoint"] == endpoint
    }
    contrasts = {
        (row["contrast"], row["metric"]): row
        for row in independent["contrast_summary"]
        if row["panel"] == "survey_only" and row["endpoint"] == endpoint
    }
    ft_species_auc = [
        {
            "species": row["species"],
            "primary_roc_auc": row["primary_roc_auc"],
            "sensitivity_roc_auc": row["sensitivity_roc_auc"],
            "delta_roc_auc": row["delta_roc_auc"],
        }
        for row in independent["performance"]
        if row["panel"] == "survey_only"
        and row["endpoint"] == endpoint
        and row["method"] == "multihead_full_finetune"
    ]
    return {
        "panel": "survey_only",
        "endpoint": endpoint,
        "methods": methods,
        "contrasts": {f"{key[0]}::{key[1]}": value for key, value in contrasts.items()},
        "fine_tuning_species_auc": ft_species_auc,
    }


def self_test() -> None:
    require(rank_u_auc([0, 1], [0.0, 1.0]) == 1.0, "self_test_auc_perfect")
    require(rank_u_auc([0, 1], [1.0, 0.0]) == 0.0, "self_test_auc_reverse")
    require(rank_u_auc([0, 1], [0.5, 0.5]) == 0.5, "self_test_auc_tie")
    metrics = threshold_metrics([1, 1, 0, 0], [0.9, 0.1, 0.8, 0.2], 0.5)
    require(metrics["tp"] == metrics["fn"] == metrics["tn"] == metrics["fp"] == 1, "self_test_confusion")
    require(metrics["tss"] == metrics["mcc"] == 0.0 and metrics["balanced_accuracy"] == 0.5, "self_test_threshold_metrics")
    body = {"status": "pass"}
    receipt = {**body, "receipt_digest": digest_value(body)}
    validate_receipt(receipt, label="self_test")
    tampered = dict(receipt)
    tampered["status"] = "fail"
    try:
        validate_receipt(tampered, label="self_test_tamper")
    except AuditError:
        pass
    else:
        raise AuditError("self_test_tamper_not_detected")


def build_independent(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    assessment, audit, closure, access, snapshot = authenticate_inputs(root)
    panels = load_prediction_panels(root, closure, audit)
    selected, count_rows = membership_index(snapshot, panels)
    verify_source_counts(root, count_rows)
    independent = compute_independent(panels, selected, count_rows)
    verify_original_mixed_reconciliation(root, independent)
    verify_thylogale_control(root, independent)
    provenance = {
        "plan_sha256": PLAN_SHA256,
        "assessment_file_sha256": ASSESSMENT_FILE_SHA256,
        "assessment_receipt_digest": assessment["receipt_digest"],
        "accepted_audit_file_sha256": AUDIT_FILE_SHA256,
        "accepted_audit_receipt_digest": audit["receipt_digest"],
        "prediction_closure_digest": closure["receipt_digest"],
        "response_access_digest": access["receipt_digest"],
        "private_snapshot_receipt_digest": snapshot["receipt_digest"],
        "normalized_prediction_sha256": audit["verified_hashes"]["normalized_predictions"],
        "source_bindings": audit["verified_hashes"]["source_bindings"],
        "source_closures": audit["verified_hashes"]["source_closures"],
        "accepted_performance_file_sha256": sha256_file(root / EVIDENCE_20261009_REL / "paired-performance.csv"),
        "independent_source_sha256": sha256_file(Path(__file__)),
    }
    return independent, provenance


def compare_production(
    root: Path, independent: Mapping[str, Any], provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Authenticate and numerically reconcile every production aggregate."""
    output_dir = root / OUTPUT_REL
    receipt_path = output_dir / "receipt.json"
    receipt = read_receipt(receipt_path, label="production")
    require(receipt.get("schema_version") == "tasmania-survey-only-receipt-v1", "production_receipt_schema_invalid")
    require(receipt.get("status") == "pass", "production_receipt_not_passed")

    expected_digests = {
        "assessment_receipt_digest": provenance["assessment_receipt_digest"],
        "independent_audit_receipt_digest": provenance["accepted_audit_receipt_digest"],
        "prediction_closure_digest": provenance["prediction_closure_digest"],
        "response_access_digest": provenance["response_access_digest"],
        "snapshot_digest": provenance["private_snapshot_receipt_digest"],
    }
    for key, expected in expected_digests.items():
        require(receipt.get(key) == expected, f"production_receipt_binding_mismatch:{key}")
    require(receipt.get("reporting_plan_sha256") == PLAN_SHA256, "production_plan_binding_mismatch")

    output_hashes = receipt.get("outputs")
    require(isinstance(output_hashes, dict) and set(output_hashes) == {"performance.csv", "contrasts.csv", "summary.json"}, "production_output_inventory_invalid")
    for name, claimed in output_hashes.items():
        target = output_dir / name
        require(target.is_file() and not target.is_symlink(), f"production_output_missing:{name}")
        require(sha256_file(target) == claimed, f"production_output_sha256_mismatch:{name}")

    source_hashes = receipt.get("source_hashes")
    require(isinstance(source_hashes, dict), "production_source_hashes_invalid")
    expected_source_hashes = {
        "reporting_plan_sha256": PLAN_SHA256,
        "assessment_source_sha256": sha256_file(root / "scripts/tasmania_survey_only_assessment.py"),
        "audit_source_sha256": sha256_file(root / "scripts/tasmania_pseudoabsence_audit.py"),
        "metrics_source_sha256": sha256_file(root / "scripts/tasmania_pseudoabsence_metrics.py"),
        "accepted_assessment_file_sha256": ASSESSMENT_FILE_SHA256,
        "independent_audit_file_sha256": AUDIT_FILE_SHA256,
        "prediction_closure_file_sha256": sha256_file(root / PRIVATE_REL / "prediction-closure.json"),
        "response_access_file_sha256": sha256_file(root / PRIVATE_REL / "response-access.json"),
        "snapshot_file_sha256": sha256_file(root / PRIVATE_REL / "held-response-snapshot.json"),
        "normalized_prediction_file_sha256": provenance["normalized_prediction_sha256"],
        "accepted_performance_file_sha256": provenance["accepted_performance_file_sha256"],
        "independent_audit_source_closures": provenance["source_closures"],
        "independent_audit_source_bindings": provenance["source_bindings"],
    }
    require(source_hashes == expected_source_hashes, "production_source_hash_inventory_mismatch")

    expected_privacy = {
        "aggregate_only": True,
        "response_rows_emitted": False,
        "coordinates_emitted": False,
        "membership_identifiers_emitted": False,
    }
    require(receipt.get("privacy") == expected_privacy, "production_receipt_privacy_invalid")
    expected_counts = {
        "species": len(SPECIES),
        "endpoints": len(ENDPOINTS),
        "methods": len(METHODS),
        "performance_rows": len(independent["performance"]),
        "contrast_rows": len(independent["contrasts"]),
        "held_rows": sum(int(row["n_original"]) for row in independent["count_rows"]),
        "retained_rows": sum(int(row["n_retained"]) for row in independent["count_rows"]),
        "excluded_pseudoabsence_rows": sum(int(row["n_excluded_pseudoabsence"]) for row in independent["count_rows"]),
    }
    require(receipt.get("counts") == expected_counts, "production_receipt_counts_mismatch")

    production_membership = receipt.get("membership_hashes")
    independent_counts = {str(row["species"]): row for row in independent["count_rows"]}
    expected_membership = {
        species: {
            "held_membership_sha256": independent_counts[species]["held_identity_sha256"],
            "retained_membership_sha256": independent_counts[species]["retained_identity_sha256"],
            "excluded_membership_sha256": independent_counts[species]["excluded_identity_sha256"],
        }
        for species in SPECIES
    }
    require(production_membership == expected_membership, "production_membership_hash_mismatch")

    max_differences = {"performance": 0.0, "contrasts": 0.0, "summaries": 0.0}

    def compare_float(actual: Any, expected: Any, *, label: str, group: str) -> None:
        try:
            a, e = float(actual), float(expected)
        except (TypeError, ValueError) as exc:
            raise AuditError(f"production_numeric_invalid:{label}") from exc
        require(math.isfinite(a) and math.isfinite(e), f"production_numeric_nonfinite:{label}")
        difference = abs(a - e)
        max_differences[group] = max(max_differences[group], difference)
        require(difference <= FLOAT_TOLERANCE, f"production_numeric_mismatch:{label}:{difference}")

    performance = read_csv(output_dir / "performance.csv")
    performance_fields = {
        "evaluation_panel", "species", "endpoint", "method", "selected_conventional_family",
        "n", "n_positive", "n_negative", "primary_threshold", "sensitivity_threshold", "delta_threshold",
        *{f"{phase}_{metric}" for phase in PHASES for metric in METRICS},
        *{f"delta_{metric}" for metric in METRICS},
        *{f"{phase}_{field}" for phase in PHASES for field in ("tp", "tn", "fp", "fn")},
    }
    require(len(performance) == 336 and performance and set(performance[0]) == performance_fields, "production_performance_schema_invalid")
    production_index = {
        (row["evaluation_panel"], row["species"], row["endpoint"], row["method"]): row
        for row in performance
    }
    independent_index = {
        (row["panel"], row["species"], row["endpoint"], row["method"]): row
        for row in independent["performance"]
    }
    require(len(production_index) == len(performance) and set(production_index) == set(independent_index), "production_performance_inventory_mismatch")
    accepted = read_csv(root / EVIDENCE_20261009_REL / "paired-performance.csv")
    accepted_families = {
        (row["species"], row["endpoint"]): row["selected_conventional_family"]
        for row in accepted if row["method"] == "selected_conventional"
    }
    require(len(accepted_families) == len(SPECIES) * len(ENDPOINTS), "accepted_conventional_family_inventory_invalid")
    for key, observed in production_index.items():
        expected = independent_index[key]
        family = accepted_families[observed["species"], observed["endpoint"]] if observed["method"] == "selected_conventional" else "NA"
        require(observed["selected_conventional_family"] == family, f"production_conventional_family_mismatch:{key}")
        for field in ("n", "n_positive", "n_negative"):
            require(int(observed[field]) == int(expected[field]), f"production_count_mismatch:{key}:{field}")
        for field in ("primary_threshold", "sensitivity_threshold"):
            compare_float(observed[field], expected[field], label=f"{key}:{field}", group="performance")
        compare_float(
            observed["delta_threshold"],
            float(expected["sensitivity_threshold"]) - float(expected["primary_threshold"]),
            label=f"{key}:delta_threshold", group="performance",
        )
        for phase in PHASES:
            for metric in METRICS:
                compare_float(observed[f"{phase}_{metric}"], expected[f"{phase}_{metric}"], label=f"{key}:{phase}_{metric}", group="performance")
            for field in ("tp", "tn", "fp", "fn"):
                require(int(observed[f"{phase}_{field}"]) == int(expected[f"{phase}_{field}"]), f"production_confusion_mismatch:{key}:{phase}_{field}")
        for metric in METRICS:
            compare_float(observed[f"delta_{metric}"], expected[f"delta_{metric}"], label=f"{key}:delta_{metric}", group="performance")

    contrasts = read_csv(output_dir / "contrasts.csv")
    contrast_fields = {
        "contrast_scope", "evaluation_panel", "species", "endpoint", "contrast", "metric",
        "primary_contrast", "sensitivity_contrast", "change_in_contrast",
    }
    require(len(contrasts) == 672 and contrasts and set(contrasts[0]) == contrast_fields, "production_contrast_schema_invalid")
    contrast_index = {
        (row["evaluation_panel"], row["species"], row["endpoint"], row["contrast"], row["metric"]): row
        for row in contrasts
    }
    independent_contrasts = {
        (row["panel"], row["species"], row["endpoint"], row["contrast"], row["metric"]): row
        for row in independent["contrasts"]
    }
    require(len(contrast_index) == len(contrasts) and set(contrast_index) == set(independent_contrasts), "production_contrast_inventory_mismatch")
    for key, observed in contrast_index.items():
        require(observed["contrast_scope"] == "species_endpoint", f"production_contrast_scope_invalid:{key}")
        expected = independent_contrasts[key]
        for field in ("primary_contrast", "sensitivity_contrast", "change_in_contrast"):
            compare_float(observed[field], expected[field], label=f"{key}:{field}", group="contrasts")

    summary = read_json(output_dir / "summary.json")
    require(summary.get("schema_version") == "tasmania-survey-only-summary-v1", "production_summary_schema_invalid")
    require(summary.get("accepted_digests") == expected_digests, "production_summary_binding_mismatch")
    require(summary.get("source_hashes") == source_hashes, "production_summary_source_hash_mismatch")
    require(summary.get("privacy") == expected_privacy, "production_summary_privacy_invalid")
    require(summary.get("estimand") == receipt.get("estimand"), "production_estimand_disagreement")

    summary_counts = summary.get("counts")
    require(isinstance(summary_counts, dict) and set(summary_counts) == set(SPECIES), "production_summary_counts_inventory_invalid")
    for species in SPECIES:
        observed = summary_counts[species]
        expected = independent_counts[species]
        count_map = {
            "held_rows": "n_original",
            "retained_rows": "n_retained",
            "retained_presence": "n_positive",
            "retained_survey_supported_absence": "n_survey_supported_absence",
            "excluded_pseudoabsence": "n_excluded_pseudoabsence",
            "excluded_rows": "n_excluded_pseudoabsence",
        }
        for observed_name, expected_name in count_map.items():
            require(int(observed[observed_name]) == int(expected[expected_name]), f"production_summary_count_mismatch:{species}:{observed_name}")
        require(
            {name: observed[name] for name in expected_membership[species]} == expected_membership[species],
            f"production_summary_membership_mismatch:{species}",
        )

    method_summary = {
        (row["evaluation_panel"], row["endpoint"], row["method"]): row
        for row in summary.get("all_endpoint_method_means", []) if isinstance(row, dict)
    }
    independent_method_summary = {
        (row["panel"], row["endpoint"], row["method"]): row
        for row in independent["method_summary"]
    }
    require(len(method_summary) == 42 and set(method_summary) == set(independent_method_summary), "production_method_summary_inventory_mismatch")
    for key, observed in method_summary.items():
        expected = independent_method_summary[key]
        require(observed.get("species") == expected["n_species"], f"production_method_summary_species_mismatch:{key}")
        for metric in METRICS:
            values = observed.get(metric)
            require(isinstance(values, dict) and set(values) == {"primary", "sensitivity", "delta"}, f"production_method_summary_metric_invalid:{key}:{metric}")
            for phase in ("primary", "sensitivity", "delta"):
                compare_float(values[phase], expected[f"mean_{phase}_{metric}"], label=f"{key}:{metric}:{phase}", group="summaries")

    comparator_to_contrast = {
        "target_only_resmlp": "multihead_full_finetune_minus_target_only_resmlp",
        "selected_conventional": "multihead_full_finetune_minus_selected_conventional",
    }
    contrast_summary = {
        (row["evaluation_panel"], row["endpoint"], comparator_to_contrast.get(row["comparator"], "invalid"), row["metric"]): row
        for row in summary.get("all_endpoint_method_contrasts", []) if isinstance(row, dict) and "comparator" in row
    }
    independent_contrast_summary = {
        (row["panel"], row["endpoint"], row["contrast"], row["metric"]): row
        for row in independent["contrast_summary"]
    }
    require(len(contrast_summary) == 84 and set(contrast_summary) == set(independent_contrast_summary), "production_contrast_summary_inventory_mismatch")
    for key, observed in contrast_summary.items():
        expected = independent_contrast_summary[key]
        require(observed.get("species") == expected["n_species"], f"production_contrast_summary_species_mismatch:{key}")
        for observed_name, expected_name in (
            ("species_mean_primary", "mean_primary_contrast"),
            ("species_mean_sensitivity", "mean_sensitivity_contrast"),
            ("species_mean_change", "mean_change_in_contrast"),
        ):
            compare_float(observed[observed_name], expected[expected_name], label=f"{key}:{observed_name}", group="summaries")

    full_means = summary.get("full_endpoint_original_vs_survey_means")
    require(isinstance(full_means, dict) and set(full_means) == set(PANELS), "production_full_summary_inventory_invalid")
    for panel in PANELS:
        require(set(full_means[panel]) == set(METHODS), f"production_full_summary_method_inventory_invalid:{panel}")
        for method in METHODS:
            expected = independent_method_summary[panel, ENDPOINTS[-1], method]
            for metric in METRICS:
                values = full_means[panel][method][metric]
                for phase in ("primary", "sensitivity", "delta"):
                    compare_float(values[phase], expected[f"mean_{phase}_{metric}"], label=f"full:{panel}:{method}:{metric}:{phase}", group="summaries")

    reconciliation = summary.get("original_mixed_reconciliation")
    require(
        reconciliation == {
            "accepted_file_sha256": provenance["accepted_performance_file_sha256"],
            "accepted_rows": 168,
            "reconciled_rows": 168,
        },
        "production_original_reconciliation_invalid",
    )
    return {
        "production_receipt_digest": receipt["receipt_digest"],
        "production_receipt_file_sha256": sha256_file(receipt_path),
        "production_output_sha256": dict(output_hashes),
        "max_abs_difference": max_differences,
        "counts": {
            **expected_counts,
            "method_summary_rows": len(method_summary),
            "contrast_summary_rows": len(contrast_summary),
            "membership_hashes_reconciled": len(SPECIES) * 3,
        },
        "membership_hashes": expected_membership,
    }


def independent_receipt(
    independent: Mapping[str, Any], provenance: Mapping[str, Any], comparison: Mapping[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "tasmania-survey-only-independent-audit-v1",
        "status": "pass",
        "estimand": "post hoc source-conditional descriptive performance on original held presences plus survey_supported_absence rows, with pseudoabsence rows excluded from evaluation only; frozen scores and phase-specific inner-derived thresholds",
        "scope": "independent aggregate recomputation and production reconciliation; no fitting, threshold selection, canonical response access, population extrapolation, or inferential testing",
        "method": "Mann-Whitney rank-U ROC AUC plus manual confusion-matrix metrics, implemented without importing production survey-only or shared metric code",
        "provenance": dict(provenance),
        "production": dict(comparison),
        "checks": {
            "authenticated_frozen_plan_and_receipt_chain": True,
            "authenticated_all_eight_prediction_files": True,
            "held_presence_rows_preserved": True,
            "survey_only_panel_has_both_classes_for_all_species": True,
            "all_original_mixed_rows_reconciled_to_accepted_assessment": 168,
            "all_production_performance_rows_reconciled": 336,
            "all_production_contrast_rows_reconciled": 672,
            "all_production_method_summary_rows_reconciled": 42,
            "all_production_contrast_summary_rows_reconciled": 84,
            "thylogale_zero_exclusion_control_rows_reconciled": 42,
        },
        "headline": headline(independent),
        "privacy": {
            "aggregate_only": True,
            "response_rows_emitted": False,
            "coordinates_emitted": False,
            "membership_identifiers_emitted": False,
        },
        "limitations": [
            "post hoc descriptive evaluation",
            "survey nondetection does not establish true absence or occupancy",
            "species means have no inferential intervals and endpoints are nested rather than independent replications",
            "the panel conditions on surveyed held cells and does not identify population-wide or causal performance",
        ],
    }
    return {**body, "receipt_digest": digest_value(body)}


def write_receipt(root: Path, receipt: Mapping[str, Any]) -> Path:
    target = root / OUTPUT_REL / "independent-audit.json"
    text = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    if target.exists():
        require(target.is_file() and not target.is_symlink(), "independent_receipt_target_invalid")
        require(target.read_text(encoding="utf-8") == text, "independent_receipt_exists_with_different_content")
    else:
        target.write_text(text, encoding="utf-8")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("verify", "self-test"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--compare-production", action="store_true")
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        self_test()
        print(json.dumps({"status": "pass", "tests": 7}, sort_keys=True))
        return 0
    require(args.execute, "verify_requires_execute")
    require(not args.write_receipt or args.compare_production, "write_receipt_requires_production_comparison")
    self_test()
    independent, provenance = build_independent(ROOT)
    comparison = compare_production(ROOT, independent, provenance) if args.compare_production else None
    receipt = independent_receipt(independent, provenance, comparison) if comparison is not None else None
    receipt_path = write_receipt(ROOT, receipt) if args.write_receipt and receipt is not None else None
    output = {
        "status": "pass" if comparison is not None else "independent_results_ready_production_comparison_pending",
        "counts": {
            "species": len(SPECIES),
            "endpoints": len(ENDPOINTS),
            "methods": len(METHODS),
            "phases": len(PHASES),
            "panels": len(PANELS),
            "phase_panels": 672,
            "paired_performance_rows": len(independent["performance"]),
            "contrast_rows": len(independent["contrasts"]),
            "method_summary_rows": len(independent["method_summary"]),
            "contrast_summary_rows": len(independent["contrast_summary"]),
        },
        "held_counts": independent["count_rows"],
        "headline": headline(independent),
        "provenance": provenance,
    }
    if comparison is not None:
        output["production_comparison"] = comparison
        output["independent_audit_receipt_digest"] = receipt["receipt_digest"]
    if receipt_path is not None:
        output["independent_audit_path"] = str(receipt_path.relative_to(ROOT))
        output["independent_audit_file_sha256"] = sha256_file(receipt_path)
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
