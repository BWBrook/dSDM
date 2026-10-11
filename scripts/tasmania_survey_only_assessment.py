"""Score the post hoc Tasmania survey-supported-absence evaluation panel.

This module only evaluates already-opened, minimal response snapshots against
closed, identity-aligned prediction bundles.  It does not read the canonical
response table, fit models, select learners, or select thresholds.  The CLI is
deliberately inert unless ``--execute`` is supplied.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/assessment")
EVIDENCE_REL = Path("evidence/tasmania_pseudoabsence/20261011/survey-only")
AUDIT_REL = Path("evidence/tasmania_pseudoabsence/20261009/independent-assessment-verification.json")
PLAN_REL = Path("docs/plan/TasmaniaSurveyOnlyEvaluation-20261011.md")
PLAN_SHA256 = "b7c57ba7d6c554027fc7c5a37c69af0dca4db9d511e52fa296a7910d16a9e8d8"
ACCEPTED_ASSESSMENT_DIGEST = "08915652195df252b062163df189f892b72ccdf1e66dab29cb4908d3b696ab56"
INDEPENDENT_AUDIT_DIGEST = "d90a01ad2ac08ef36ff2c40bf7bce9223589011111cc2c67c124e399481ac3be"
SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
ENDPOINTS = (
    "fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02",
    "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02",
    "fraction100/full",
)
METHODS = ("target_only_resmlp", "multihead_full_finetune", "selected_conventional")
CONTRASTS = ("target_only_resmlp", "selected_conventional")
METRICS = ("roc_auc", "tss", "mcc", "balanced_accuracy", "sensitivity", "specificity")
CONTRAST_METRICS = ("roc_auc", "tss", "mcc")
SOURCE_LABELS = {"presence", "survey_supported_absence", "pseudoabsence"}
SNAPSHOT_KEYS = {"species_id", "grid_cell_id", "microcluster", "pa", "pa_type"}


class SurveyOnlyError(ValueError):
    """Raised when the survey-only assessment must fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SurveyOnlyError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_receipt(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    require(target.is_file() and not target.is_symlink(), f"receipt_missing:{target}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SurveyOnlyError(f"receipt_invalid:{target}") from exc
    require(isinstance(value, dict), f"receipt_object_required:{target}")
    body = dict(value)
    claimed = body.pop("receipt_digest", None)
    require(isinstance(claimed, str) and digest_value(body) == claimed, f"receipt_digest_mismatch:{target}")
    return value


def _load_audit_module():
    """Load the existing independent replay helpers without duplicating them."""
    try:
        import tasmania_pseudoabsence_audit as audit  # type: ignore
        return audit
    except ImportError:
        path = Path(__file__).with_name("tasmania_pseudoabsence_audit.py")
        spec = importlib.util.spec_from_file_location("tasmania_pseudoabsence_audit", path)
        require(spec is not None and spec.loader is not None, "audit_source_unloadable")
        audit = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = audit
        spec.loader.exec_module(audit)
        return audit


def validate_independent_audit(root: Path = ROOT) -> dict[str, Any]:
    """Authenticate the accepted assessment, actual replay, and source hashes."""
    root = Path(root).resolve()
    audit_path = root / AUDIT_REL
    audit = read_receipt(audit_path)
    require(audit["receipt_digest"] == INDEPENDENT_AUDIT_DIGEST, "independent_audit_digest_changed")
    require(audit.get("schema_version") == "tasmania-pseudoabsence-independent-assessment-verification-v1", "independent_audit_schema_invalid")
    require(audit.get("status") == "pass", "independent_audit_not_passed")
    require(audit.get("assessment_receipt_digest") == ACCEPTED_ASSESSMENT_DIGEST, "independent_audit_assessment_binding_invalid")
    require(audit.get("verified_counts", {}).get("species") == 8, "independent_audit_species_inventory_invalid")
    require(audit.get("verified_counts", {}).get("endpoints") == 7, "independent_audit_endpoint_inventory_invalid")
    require(audit.get("verified_counts", {}).get("methods") == 3, "independent_audit_method_inventory_invalid")
    require(audit.get("verified_counts", {}).get("held_rows") == 1672, "independent_audit_held_inventory_invalid")
    return audit


def validate_startup(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run all response-free startup gates before metric calculation."""
    root = Path(root).resolve()
    plan = root / PLAN_REL
    require(plan.is_file() and sha256_file(plan) == PLAN_SHA256, "reporting_plan_changed")
    audit_receipt = validate_independent_audit(root)
    audit = _load_audit_module()
    private = root / PRIVATE_REL
    evidence = root / "evidence/tasmania_pseudoabsence/20261009"
    closure, access, snapshot, assessment = audit.validate_post_assessment_gate(root, private, evidence)
    require(assessment.get("receipt_digest") == ACCEPTED_ASSESSMENT_DIGEST, "accepted_assessment_digest_changed")
    require(audit_receipt.get("prediction_closure_digest") == closure.get("receipt_digest"), "independent_audit_closure_binding_invalid")
    require(audit_receipt.get("private_response_snapshot_digest") == snapshot.get("receipt_digest"), "independent_audit_snapshot_binding_invalid")

    normalized_hashes = audit_receipt.get("verified_hashes", {}).get("normalized_predictions")
    require(isinstance(normalized_hashes, dict) and set(normalized_hashes) == set(SPECIES), "independent_audit_normalized_inventory_invalid")
    closure_hashes = {str(row.get("species")): row.get("sha256") for row in closure.get("files", []) if isinstance(row, dict)}
    require(closure_hashes == normalized_hashes, "independent_audit_normalized_hash_binding_invalid")
    for species, claimed in normalized_hashes.items():
        path = private / "predictions" / f"{species}.npz"
        require(path.is_file() and sha256_file(path) == claimed, f"normalized_prediction_hash_changed:{species}")
    return audit_receipt, closure, access, snapshot, assessment


def validate_prediction_panels(root: Path, closure: Mapping[str, Any]) -> dict[str, dict[str, np.ndarray]]:
    """Load only normalized closed predictions through the existing validator."""
    audit = _load_audit_module()
    private = Path(root).resolve() / PRIVATE_REL
    panels = audit.prediction_panels(Path(root).resolve(), private, closure)
    require(set(panels) == set(SPECIES), "normalized_prediction_species_inventory_invalid")
    for species, panel in panels.items():
        validate_panel(species, panel)
    return panels


def validate_panel(species: str, panel: Mapping[str, Any]) -> None:
    expected = {"grid_cell_id", "patch", "primary_scores", "sensitivity_scores", "primary_thresholds", "sensitivity_thresholds", "map_grid_cell_id", "primary_map_scores", "sensitivity_map_scores"}
    require(set(panel) == expected, f"panel_inventory_invalid:{species}")
    ids = validate_ids(panel["grid_cell_id"], f"panel_ids:{species}")
    patch = np.asarray(panel["patch"])
    require(patch.ndim == 1 and patch.shape == ids.shape and patch.dtype.kind in "US", f"panel_patch_invalid:{species}")
    n = len(ids)
    for name in ("primary_scores", "sensitivity_scores"):
        values = np.asarray(panel[name])
        require(values.shape == (len(ENDPOINTS), len(METHODS), n) and values.dtype == np.float64, f"panel_scores_invalid:{species}:{name}")
        require(np.isfinite(values).all() and ((values >= 0) & (values <= 1)).all(), f"panel_probabilities_invalid:{species}:{name}")
    for name in ("primary_thresholds", "sensitivity_thresholds"):
        thresholds = np.asarray(panel[name])
        require(thresholds.shape == (len(ENDPOINTS), len(METHODS)) and thresholds.dtype == np.float64 and np.isfinite(thresholds).all(), f"panel_thresholds_invalid:{species}:{name}")


def validate_ids(values: Any, label: str) -> np.ndarray:
    result = np.asarray(values)
    require(result.ndim == 1 and result.dtype.kind in "US" and len(result) > 0, f"{label}_invalid")
    require(len(set(result.tolist())) == len(result), f"{label}_duplicate")
    return result


def _pa_value(value: Any) -> str:
    if isinstance(value, (bool, np.bool_)):
        raise SurveyOnlyError("source_label_pa_invalid")
    if str(value) in {"0", "1"}:
        return str(value)
    raise SurveyOnlyError("source_label_pa_invalid")


def validate_source_labels(rows: Sequence[Mapping[str, Any]], expected_keys: set[tuple[str, str]] | None = None) -> dict[tuple[str, str], Mapping[str, Any]]:
    """Validate source/class semantics and build an identity index."""
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        require(isinstance(row, Mapping) and set(row) == SNAPSHOT_KEYS, "snapshot_row_schema_invalid")
        species, cell = str(row["species_id"]), str(row["grid_cell_id"])
        require(species in SPECIES and species and cell, "snapshot_identity_invalid")
        key = (species, cell)
        require(key not in result, "snapshot_duplicate_identity")
        source = str(row["pa_type"])
        pa = _pa_value(row["pa"])
        require(source in SOURCE_LABELS, "snapshot_source_invalid")
        require((pa == "1") == (source == "presence"), "snapshot_source_class_disagreement")
        require(str(row["microcluster"]), "snapshot_patch_invalid")
        result[key] = row
    if expected_keys is not None:
        require(set(result) == set(expected_keys), "snapshot_membership_mismatch")
    return result


def membership_digest(keys: Sequence[tuple[str, str]]) -> str:
    """Hash canonical identities while keeping them out of public evidence."""
    return digest_value(sorted([[str(species), str(cell)] for species, cell in set(keys)]))


def build_evaluation_mask(rows: Sequence[Mapping[str, Any]], expected_keys: set[tuple[str, str]] | None = None) -> dict[str, Any]:
    indexed = validate_source_labels(rows, expected_keys)
    ordered = sorted(indexed)
    sources = np.asarray([str(indexed[key]["pa_type"]) for key in ordered])
    retained = np.isin(sources, ("presence", "survey_supported_absence"))
    excluded = sources == "pseudoabsence"
    require(np.array_equal(retained | excluded, np.ones(len(ordered), dtype=bool)), "source_mask_inventory_invalid")
    require(np.any(sources == "presence"), "survey_panel_has_no_presences")
    require(np.any(sources == "survey_supported_absence"), "survey_panel_has_no_survey_absences")
    return {
        "keys": ordered, "retained_keys": [key for key, keep in zip(ordered, retained, strict=True) if keep],
        "excluded_keys": [key for key, drop in zip(ordered, excluded, strict=True) if drop],
        "sources": sources, "retained": retained, "excluded": excluded,
    }


def _panel_records(species: str, panel: Mapping[str, Any], snapshot: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict[str, Any]:
    ids = validate_ids(panel["grid_cell_id"], f"panel_ids:{species}")
    keys = {(species, str(cell)) for cell in ids}
    require(keys <= set(snapshot), f"snapshot_missing_identity:{species}")
    records = [snapshot[species, str(cell)] for cell in ids]
    require(all(str(row["microcluster"]) == str(patch) for row, patch in zip(records, panel["patch"], strict=True)), f"snapshot_patch_mismatch:{species}")
    sources = np.asarray([str(row["pa_type"]) for row in records])
    labels = np.asarray([int(_pa_value(row["pa"])) for row in records], dtype=np.int8)
    require(np.array_equal(labels == 1, sources == "presence"), f"snapshot_labels_invalid:{species}")
    keep = np.isin(sources, ("presence", "survey_supported_absence"))
    require(np.any(keep) and np.any(labels[keep] == 1) and np.any(labels[keep] == 0), f"survey_panel_class_support_invalid:{species}")
    return {"ids": ids, "records": records, "labels": labels, "sources": sources, "keep": keep}


def extended_metrics(labels: Any, score: Any, threshold: float) -> dict[str, Any]:
    audit = _load_audit_module()
    try:
        result = dict(audit.confusion(labels, score, threshold))
    except (ValueError, RuntimeError) as exc:
        raise SurveyOnlyError(str(exc)) from exc
    sensitivity = float(result["tp"] / result["n_positive"])
    specificity = float(result["tn"] / result["n_negative"])
    result["sensitivity"] = sensitivity
    result["specificity"] = specificity
    result["balanced_accuracy"] = float((sensitivity + specificity) / 2.0)
    return result


def _metric_row(species: str, endpoint: str, method: str, evaluation_panel: str, panel: Mapping[str, Any], indices: np.ndarray, labels: np.ndarray, selected_family: str | None = None) -> dict[str, Any]:
    endpoint_index, method_index = ENDPOINTS.index(endpoint), METHODS.index(method)
    primary = extended_metrics(labels, panel["primary_scores"][endpoint_index, method_index, indices], panel["primary_thresholds"][endpoint_index, method_index])
    sensitivity = extended_metrics(labels, panel["sensitivity_scores"][endpoint_index, method_index, indices], panel["sensitivity_thresholds"][endpoint_index, method_index])
    row: dict[str, Any] = {
        "evaluation_panel": evaluation_panel, "species": species, "endpoint": endpoint, "method": method,
        "selected_conventional_family": selected_family if method == "selected_conventional" else None,
        "n": int(len(labels)), "n_positive": int(labels.sum()), "n_negative": int(len(labels) - labels.sum()),
        "primary_threshold": float(panel["primary_thresholds"][endpoint_index, method_index]),
        "sensitivity_threshold": float(panel["sensitivity_thresholds"][endpoint_index, method_index]),
        "delta_threshold": float(panel["sensitivity_thresholds"][endpoint_index, method_index] - panel["primary_thresholds"][endpoint_index, method_index]),
    }
    for metric in METRICS:
        row[f"primary_{metric}"] = primary[metric]
        row[f"sensitivity_{metric}"] = sensitivity[metric]
        row[f"delta_{metric}"] = sensitivity[metric] - primary[metric]
    for field in ("tp", "tn", "fp", "fn"):
        row[f"primary_{field}"] = primary[field]
        row[f"sensitivity_{field}"] = sensitivity[field]
    return row


def compute_performance(panels: Mapping[str, Mapping[str, Any]], snapshot: Mapping[tuple[str, str], Mapping[str, Any]], selected_families: Mapping[tuple[str, str], str] | None = None) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Compute original and survey-only rows from identity-aligned arrays."""
    performance: list[dict[str, Any]] = []
    counts: dict[str, dict[str, Any]] = {}
    for species in SPECIES:
        require(species in panels, f"panel_species_missing:{species}")
        panel = panels[species]
        validate_panel(species, panel)
        records = _panel_records(species, panel, snapshot)
        all_indices = np.arange(len(records["ids"]), dtype=np.int64)
        survey_indices = np.flatnonzero(records["keep"])
        all_keys = [(species, str(cell)) for cell in records["ids"]]
        survey_keys = [key for key, keep in zip(all_keys, records["keep"], strict=True) if keep]
        excluded_keys = [key for key, keep in zip(all_keys, records["keep"], strict=True) if not keep]
        counts[species] = {
            "held_rows": len(all_keys), "retained_rows": len(survey_keys),
            "retained_presence": int(np.sum(records["sources"] == "presence")),
            "retained_survey_supported_absence": int(np.sum(records["sources"] == "survey_supported_absence")),
            "excluded_pseudoabsence": int(np.sum(records["sources"] == "pseudoabsence")),
            "excluded_rows": len(excluded_keys),
            "held_membership_sha256": membership_digest(all_keys),
            "retained_membership_sha256": membership_digest(survey_keys),
            "excluded_membership_sha256": membership_digest(excluded_keys),
        }
        for endpoint in ENDPOINTS:
            for method in METHODS:
                family = selected_families.get((species, endpoint)) if selected_families else None
                performance.append(_metric_row(species, endpoint, method, "original_mixed", panel, all_indices, records["labels"], family))
                performance.append(_metric_row(species, endpoint, method, "survey_only", panel, survey_indices, records["labels"][survey_indices], family))
    require(len(performance) == len(SPECIES) * len(ENDPOINTS) * len(METHODS) * 2, "performance_inventory_invalid")
    return performance, counts


def compute_contrasts(performance: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    index = {(row["evaluation_panel"], row["species"], row["endpoint"], row["method"]): row for row in performance}
    require(len(index) == len(performance), "performance_duplicate_key")
    rows: list[dict[str, Any]] = []
    for evaluation_panel in ("original_mixed", "survey_only"):
        for species in SPECIES:
            for endpoint in ENDPOINTS:
                ft = index[evaluation_panel, species, endpoint, "multihead_full_finetune"]
                for comparator in CONTRASTS:
                    other = index[evaluation_panel, species, endpoint, comparator]
                    for metric in CONTRAST_METRICS:
                        primary = float(ft[f"primary_{metric}"]) - float(other[f"primary_{metric}"])
                        sensitivity = float(ft[f"sensitivity_{metric}"]) - float(other[f"sensitivity_{metric}"])
                        rows.append({
                            "contrast_scope": "species_endpoint", "evaluation_panel": evaluation_panel,
                            "species": species, "endpoint": endpoint,
                            "contrast": f"multihead_full_finetune_minus_{comparator}", "metric": metric,
                            "primary_contrast": primary, "sensitivity_contrast": sensitivity,
                            "change_in_contrast": sensitivity - primary,
                        })
    require(len(rows) == 2 * len(SPECIES) * len(ENDPOINTS) * len(CONTRASTS) * len(CONTRAST_METRICS), "contrast_inventory_invalid")
    return rows


def _mean(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    require(rows, "empty_mean_rows")
    return float(np.mean(np.asarray([float(row[field]) for row in rows], dtype=np.float64), dtype=np.float64))


def summarize(performance: Sequence[Mapping[str, Any]], contrasts: Sequence[Mapping[str, Any]], counts: Mapping[str, Mapping[str, Any]], *, source_hashes: Mapping[str, Any], accepted_digests: Mapping[str, str]) -> dict[str, Any]:
    full_means: dict[str, Any] = {}
    for evaluation_panel in ("original_mixed", "survey_only"):
        full_means[evaluation_panel] = {}
        for method in METHODS:
            subset = [row for row in performance if row["evaluation_panel"] == evaluation_panel and row["endpoint"] == ENDPOINTS[-1] and row["method"] == method]
            full_means[evaluation_panel][method] = {metric: {phase: _mean(subset, f"{phase}_{metric}") for phase in ("primary", "sensitivity", "delta")} for metric in METRICS}
    endpoint_method_means = []
    for evaluation_panel in ("original_mixed", "survey_only"):
        for endpoint in ENDPOINTS:
            for method in METHODS:
                subset = [row for row in performance if row["evaluation_panel"] == evaluation_panel and row["endpoint"] == endpoint and row["method"] == method]
                endpoint_method_means.append({
                    "evaluation_panel": evaluation_panel, "endpoint": endpoint, "method": method,
                    **{metric: {phase: _mean(subset, f"{phase}_{metric}") for phase in ("primary", "sensitivity", "delta")} for metric in METRICS},
                    "species": len(subset),
                })
            for comparator in CONTRASTS:
                for metric in CONTRAST_METRICS:
                    subset = [row for row in contrasts if row["evaluation_panel"] == evaluation_panel and row["endpoint"] == endpoint and row["contrast"] == f"multihead_full_finetune_minus_{comparator}" and row["metric"] == metric]
                    endpoint_method_means.append({
                        "evaluation_panel": evaluation_panel, "endpoint": endpoint, "comparator": comparator, "metric": metric,
                        "species_mean_primary": _mean(subset, "primary_contrast"),
                        "species_mean_sensitivity": _mean(subset, "sensitivity_contrast"),
                        "species_mean_change": _mean(subset, "change_in_contrast"), "species": len(subset),
                    })
    return {
        "schema_version": "tasmania-survey-only-summary-v1",
        "accepted_digests": dict(accepted_digests), "source_hashes": dict(source_hashes),
        "estimand": "post hoc source-conditional descriptive performance on original held presences plus survey_supported_absence rows, with pseudoabsence rows excluded from evaluation only; model scores and phase-specific inner-derived thresholds are frozen",
        "weighting": "equal species means within each endpoint; endpoints are retained as nested descriptive panels and are not independent replications",
        "counts": {species: dict(value) for species, value in counts.items()},
        "full_endpoint_original_vs_survey_means": full_means,
        "all_endpoint_method_means": [row for row in endpoint_method_means if "method" in row],
        "all_endpoint_method_contrasts": [row for row in endpoint_method_means if "comparator" in row],
        "privacy": {"aggregate_only": True, "response_rows_emitted": False, "coordinates_emitted": False, "membership_identifiers_emitted": False},
        "limitations": ["post hoc evaluation", "survey nondetection does not establish true absence or occupancy", "no inferential intervals or tests", "no population extrapolation or independent-species claim"],
    }


def _csv_scalar(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, (float, np.floating)):
        return repr(float(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return str(value)


def csv_text(rows: Sequence[Mapping[str, Any]]) -> str:
    require(rows, "empty_csv")
    fields = list(rows[0])
    from io import StringIO
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_scalar(row.get(field)) for field in fields})
    return buffer.getvalue()


def json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def write_exact(path: Path, text: str) -> None:
    if path.exists():
        require(path.is_file() and not path.is_symlink() and path.read_text(encoding="utf-8") == text, f"existing_output_differs:{path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def accepted_performance_table(assessment: Mapping[str, Any], root: Path) -> tuple[list[dict[str, Any]], str]:
    """Read the already-public aggregate once and bind its file hash."""
    files = {Path(str(row["path"])).name: row for row in assessment.get("files", []) if isinstance(row, Mapping)}
    record = files.get("paired-performance.csv")
    require(record is not None, "accepted_performance_file_missing")
    path = root / str(record["path"])
    require(sha256_file(path) == record.get("sha256"), "accepted_performance_hash_changed")
    audit = _load_audit_module()
    accepted = audit.read_csv(path)
    require(len(accepted) == 168, "accepted_performance_inventory_invalid")
    return accepted, str(record["sha256"])


def selected_families_from_accepted(accepted: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], str]:
    """Recover the already-accepted conventional selections from public rows."""
    selected: dict[tuple[str, str], str] = {}
    for row in accepted:
        if row.get("method") != "selected_conventional":
            continue
        key = (str(row.get("species")), str(row.get("endpoint")))
        family = row.get("selected_conventional_family")
        require(key not in selected and isinstance(family, str) and family not in {"", "NA"}, "accepted_selection_inventory_invalid")
        selected[key] = family
    require(len(selected) == len(SPECIES) * len(ENDPOINTS), "accepted_selection_inventory_incomplete")
    return selected


def reconcile_original(performance: Sequence[Mapping[str, Any]], accepted: Sequence[Mapping[str, Any]], accepted_sha256: str) -> dict[str, Any]:
    """Check the original mixed rows against the accepted published aggregate."""
    audit = _load_audit_module()
    observed = {(row["species"], row["endpoint"], row["method"]): row for row in performance if row["evaluation_panel"] == "original_mixed"}
    require(len(accepted) == len(observed) == 168, "accepted_performance_inventory_invalid")
    checked = 0
    for row in accepted:
        key = (row.get("species"), row.get("endpoint"), row.get("method"))
        require(key in observed, "accepted_performance_key_mismatch")
        ours = observed[key]
        for field in ("n", "n_positive", "n_negative", "primary_threshold", "sensitivity_threshold", "delta_threshold", "primary_roc_auc", "sensitivity_roc_auc", "delta_roc_auc", "primary_tss", "sensitivity_tss", "delta_tss", "primary_mcc", "sensitivity_mcc", "delta_mcc"):
            require(audit.equal_value(ours[field], row.get(field), exact=field in {"n", "n_positive", "n_negative", "primary_threshold", "sensitivity_threshold", "delta_threshold"}), f"accepted_performance_reconciliation_failed:{key}:{field}")
        checked += 1
    return {"accepted_rows": len(accepted), "reconciled_rows": checked, "accepted_file_sha256": accepted_sha256}


def evaluate(root: Path = ROOT, *, execute: bool = False) -> dict[str, Any]:
    require(execute, "survey_only_requires_explicit_execute_gate")
    root = Path(root).resolve()
    out = root / EVIDENCE_REL
    names = ("performance.csv", "contrasts.csv", "summary.json", "receipt.json")
    existing = [out / name for name in names if (out / name).exists()]
    require(not existing or len(existing) == len(names), "partial_survey_only_output_exists")
    audit_receipt, closure, access, snapshot_receipt, assessment = validate_startup(root)
    panels = validate_prediction_panels(root, closure)
    audit = _load_audit_module()
    snapshot = audit.snapshot_index(snapshot_receipt, panels)
    accepted_performance, accepted_performance_sha256 = accepted_performance_table(assessment, root)
    selected = selected_families_from_accepted(accepted_performance)
    performance, counts = compute_performance(panels, snapshot, selected)
    reconciliation = reconcile_original(performance, accepted_performance, accepted_performance_sha256)
    contrasts = compute_contrasts(performance)
    source_hashes: dict[str, Any] = {
        "reporting_plan_sha256": sha256_file(root / PLAN_REL),
        "assessment_source_sha256": sha256_file(Path(__file__).resolve()),
        "audit_source_sha256": sha256_file(root / "scripts/tasmania_pseudoabsence_audit.py"),
        "metrics_source_sha256": sha256_file(root / "scripts/tasmania_pseudoabsence_metrics.py"),
        "accepted_assessment_file_sha256": sha256_file(root / "evidence/tasmania_pseudoabsence/20261009/assessment.json"),
        "independent_audit_file_sha256": sha256_file(root / AUDIT_REL),
        "prediction_closure_file_sha256": sha256_file(root / PRIVATE_REL / "prediction-closure.json"),
        "response_access_file_sha256": sha256_file(root / PRIVATE_REL / "response-access.json"),
        "snapshot_file_sha256": sha256_file(root / PRIVATE_REL / "held-response-snapshot.json"),
        "normalized_prediction_file_sha256": {species: sha256_file(root / PRIVATE_REL / "predictions" / f"{species}.npz") for species in SPECIES},
        "accepted_performance_file_sha256": reconciliation["accepted_file_sha256"],
        "independent_audit_source_closures": audit_receipt.get("verified_hashes", {}).get("source_closures", {}),
        "independent_audit_source_bindings": audit_receipt.get("verified_hashes", {}).get("source_bindings", {}),
    }
    accepted_digests = {
        "assessment_receipt_digest": assessment["receipt_digest"],
        "independent_audit_receipt_digest": audit_receipt["receipt_digest"],
        "prediction_closure_digest": closure["receipt_digest"],
        "response_access_digest": access["receipt_digest"],
        "snapshot_digest": snapshot_receipt["receipt_digest"],
    }
    summary = summarize(performance, contrasts, counts, source_hashes=source_hashes, accepted_digests=accepted_digests)
    summary["original_mixed_reconciliation"] = reconciliation
    summary_body = json_text(summary)
    summary_sha = hashlib.sha256(summary_body.encode("utf-8")).hexdigest()
    performance_body = csv_text(performance)
    contrasts_body = csv_text(contrasts)
    receipt_body: dict[str, Any] = {
        "schema_version": "tasmania-survey-only-receipt-v1", "status": "pass",
        "assessment_receipt_digest": assessment["receipt_digest"], "independent_audit_receipt_digest": audit_receipt["receipt_digest"],
        "prediction_closure_digest": closure["receipt_digest"], "response_access_digest": access["receipt_digest"], "snapshot_digest": snapshot_receipt["receipt_digest"],
        "reporting_plan_sha256": PLAN_SHA256, "source_hashes": source_hashes,
        "outputs": {"performance.csv": hashlib.sha256(performance_body.encode()).hexdigest(), "contrasts.csv": hashlib.sha256(contrasts_body.encode()).hexdigest(), "summary.json": summary_sha},
        "counts": {"species": 8, "endpoints": 7, "methods": 3, "performance_rows": len(performance), "contrast_rows": len(contrasts), "held_rows": sum(int(value["held_rows"]) for value in counts.values()), "retained_rows": sum(int(value["retained_rows"]) for value in counts.values()), "excluded_pseudoabsence_rows": sum(int(value["excluded_pseudoabsence"]) for value in counts.values())},
        "membership_hashes": {species: {key: value[key] for key in ("held_membership_sha256", "retained_membership_sha256", "excluded_membership_sha256")} for species, value in counts.items()},
        "estimand": summary["estimand"], "privacy": summary["privacy"],
    }
    receipt_body["receipt_digest"] = digest_value(receipt_body)
    receipt_body_text = json_text(receipt_body)
    write_exact(out / "performance.csv", performance_body)
    write_exact(out / "contrasts.csv", contrasts_body)
    write_exact(out / "summary.json", summary_body)
    write_exact(out / "receipt.json", receipt_body_text)
    return receipt_body


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="explicitly execute the closed evaluation")
    args = parser.parse_args(argv)
    result = evaluate(execute=args.execute)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
