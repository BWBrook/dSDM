"""Synthetic acquisition-manifest dry-run helpers."""

from __future__ import annotations

import copy
from typing import Any

from .contracts import (
    ValidationError,
    validate_source_contracts,
    validate_source_rows,
    validate_species_contract,
    validate_phase1_decision_bundle,
)


ALA_REQUEST_DECISIONS = (
    "P1-D003",
    "P1-D004",
    "P1-D005",
    "P1-D006",
    "P1-D007",
)
CAMERA_REQUEST_DECISIONS = ("P1-D008", "P1-D009", "P1-D010")


def build_acquisition_dry_run_summary(
    *,
    run_id: str,
    species_contract: dict[str, Any],
    source_contracts: dict[str, Any],
    decision_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Validate synthetic gates and return deterministic preflight summary data."""

    if not isinstance(run_id, str) or not run_id:
        raise ValidationError("dry-run summary requires a non-empty run_id")

    bundle = _validated_decision_bundle(decision_bundle)

    species = validate_species_contract(species_contract)
    validate_source_contracts(source_contracts)

    source_summaries = [
        _source_summary(contract)
        for contract in sorted(
            source_contracts["contracts"], key=lambda item: item["source_id"]
        )
    ]

    return {
        "run_id": run_id,
        "stage": "synthetic_acquisition_manifest_dry_run",
        "status": "ready_for_mocked_acquisition",
        "species_count": species["species_count"],
        "included_species_ids": species["included_species_ids"],
        "source_ids": [source["source_id"] for source in source_summaries],
        "source_types": sorted({source["source_type"] for source in source_summaries}),
        "source_checksums": {
            source["source_id"]: source["checksum"]["value"]
            for source in source_summaries
        },
        "licenses": {
            source["source_id"]: source["license"] for source in source_summaries
        },
        "sensitivities": {
            source["source_id"]: source["sensitivity"] for source in source_summaries
        },
        "sources": source_summaries,
        **_bundle_provenance(bundle),
    }


def build_mocked_acquisition_request_manifest(
    *,
    run_id: str,
    species_contract: dict[str, Any],
    source_contracts: dict[str, Any],
    decision_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Return deterministic, non-executed synthetic request-manifest records."""

    dry_run = build_acquisition_dry_run_summary(
        run_id=run_id,
        species_contract=species_contract,
        source_contracts=source_contracts,
        decision_bundle=decision_bundle,
    )
    bundle = _validated_decision_bundle(decision_bundle)

    requests = [
        _mocked_request_record(source, run_id=run_id, bundle=bundle)
        for source in dry_run["sources"]
    ]

    return {
        "run_id": run_id,
        "stage": "mocked_acquisition_request_dry_run",
        "status": "ready_for_mocked_request_review",
        "dry_run_status": dry_run["status"],
        "source_ids": dry_run["source_ids"],
        "source_types": dry_run["source_types"],
        "request_count": len(requests),
        "requests": requests,
        **_bundle_provenance(bundle),
    }


def build_normalized_source_row_gate_summary(
    *,
    run_id: str,
    species_contract: dict[str, Any],
    source_contracts: dict[str, Any],
    source_rows: list[dict[str, Any]],
    decision_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Validate synthetic normalized rows and return row-readiness summary data."""

    request_manifest = build_mocked_acquisition_request_manifest(
        run_id=run_id,
        species_contract=species_contract,
        source_contracts=source_contracts,
        decision_bundle=decision_bundle,
    )
    row_validation = validate_source_rows(
        source_rows,
        source_contracts=source_contracts,
        decision_bundle=decision_bundle,
    )
    rows = sorted(source_rows, key=lambda row: row["row_id"])

    return {
        "run_id": run_id,
        "stage": "synthetic_normalized_source_row_gate",
        "status": "ready_for_synthetic_normalized_row_review",
        "mocked_request_status": request_manifest["status"],
        "row_count": row_validation["row_count"],
        "row_ids": [row["row_id"] for row in rows],
        "species_ids": _sorted_unique(rows, "species_id"),
        "sources": _sorted_unique(rows, "source"),
        "source_dataset_ids": _sorted_unique(rows, "source_dataset_id"),
        "source_dataset_names": _sorted_unique(rows, "source_dataset_name"),
        "pa_types": row_validation["pa_types"],
        "sources_by_pa_type": row_validation["sources_by_pa_type"],
        "required_provenance_fields": row_validation["required_provenance_fields"],
        "survey_supported_absence_rule_ids": _sorted_optional_unique(
            rows, "survey_supported_absence_rule_id"
        ),
        "pseudoabsence_rule_ids": _sorted_optional_unique(
            rows, "pseudoabsence_rule_id"
        ),
        "rows": [_row_summary(row) for row in rows],
        "policy_provenance": request_manifest["policy_provenance"],
        "decision_bundle_id": request_manifest["decision_bundle_id"],
        "decision_bundle_schema_version": request_manifest["decision_bundle_schema_version"],
        "decision_consolidation_status": request_manifest["decision_consolidation_status"],
        "live_acquisition_status": request_manifest["live_acquisition_status"],
        "blocked_prerequisites": request_manifest["blocked_prerequisites"],
    }


def _source_summary(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": contract["source_id"],
        "source_type": contract["source_type"],
        "decision_references": list(contract["decision_references"]),
        "checksum": {
            "algorithm": contract["checksum"]["algorithm"],
            "value": contract["checksum"]["value"],
        },
        "license": contract["license"],
        "sensitivity": contract["sensitivity"],
        "local_path": contract["local_path"],
    }


def _row_summary(row: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "row_id": row["row_id"],
        "species_id": row["species_id"],
        "scientific_name": row["scientific_name"],
        "source": row["source"],
        "source_type": row["source_type"],
        "source_contract_id": row["source_contract_id"],
        "source_record_id": row["source_record_id"],
        "source_dataset_id": row["source_dataset_id"],
        "source_dataset_name": row["source_dataset_name"],
        "pa": row["pa"],
        "pa_type": row["pa_type"],
        "grid_cell_id": row.get("grid_cell_id"),
    }
    if "pseudoabsence_rule_id" in row:
        summary["pseudoabsence_rule_id"] = row["pseudoabsence_rule_id"]
    if "survey_supported_absence_rule_id" in row:
        summary["survey_supported_absence_rule_id"] = row[
            "survey_supported_absence_rule_id"
        ]
    if "camera_resolution_degree" in row:
        summary["camera_resolution_degree"] = row["camera_resolution_degree"]
    if row["source_type"] == "ala_occurrence":
        summary["ala_taxon_identity"] = copy.deepcopy(row["ala_taxon_identity"])
    return summary


def _mocked_request_record(
    source: dict[str, Any], *, run_id: str, bundle: dict[str, Any]
) -> dict[str, Any]:
    source_type = source["source_type"]
    if source_type == "ala_occurrence":
        decision_references = list(ALA_REQUEST_DECISIONS)
        intent = _ala_request_intent(bundle)
        _validate_ala_request_intent(intent, bundle)
    elif source_type == "camera_trap":
        decision_references = list(CAMERA_REQUEST_DECISIONS)
        intent = _camera_request_intent(bundle)
    else:
        raise ValidationError(f"unsupported mocked request source_type: {source_type}")

    return {
        "request_id": f"{run_id}:{source['source_id']}",
        "source_contract_id": source["source_id"],
        "source_id": source["source_id"],
        "source_type": source_type,
        "execution_status": "not_executed",
        "mocked": True,
        "decision_references": decision_references,
        "checksum": dict(source["checksum"]),
        "license": source["license"],
        "sensitivity": source["sensitivity"],
        "intent": intent,
    }


def _ala_request_intent(bundle: dict[str, Any]) -> dict[str, Any]:
    resolution = bundle["policies"]["species"]["ala_resolution"]
    return {
        "kind": "synthetic_ala_request",
        "query_resolution_status": "resolved",
        "policy_references": ["P1-D003", "P1-D004", "P1-D005", "P1-D006", "P1-D007"],
        "primary_window": bundle["policies"]["temporal"]["primary_window"],
        "species_queries": [
            {
                "species_id": species["species_id"],
                "accepted_name": species["accepted_name"],
                "ala_taxon_concept_id": species["ala_taxon_concept_id"],
                "historical_aliases": list(species["historical_aliases"]),
            }
            for species in bundle["species"]
        ],
        "synonym_normalization": resolution["synonym_normalization"],
        "accepted_descendants": resolution["accepted_descendants"],
        "pre_acquisition_scope_assertion_required": resolution["pre_acquisition_scope_assertion_required"],
        "taxon_identity_retention": dict(resolution["taxon_identity_retention"]),
        "expansion_failure_fallback": resolution["expansion_failure_fallback"],
        "subtaxon_policy": copy.deepcopy(resolution["subtaxon_policy"]),
    }


def _validate_ala_request_intent(intent: dict[str, Any], bundle: dict[str, Any]) -> None:
    """Fail closed if the executable ALA request plan loses resolved scope metadata."""

    resolution = bundle["policies"]["species"]["ala_resolution"]
    required = {
        "kind", "query_resolution_status", "policy_references", "primary_window",
        "species_queries", "synonym_normalization", "accepted_descendants",
        "pre_acquisition_scope_assertion_required", "taxon_identity_retention",
        "expansion_failure_fallback", "subtaxon_policy",
    }
    if set(intent) != required:
        raise ValidationError("ALA request intent scope plan is incomplete")
    if intent["kind"] != "synthetic_ala_request" or intent["query_resolution_status"] != "resolved":
        raise ValidationError("ALA request intent is not resolved")
    if intent["policy_references"] != list(ALA_REQUEST_DECISIONS):
        raise ValidationError("ALA request intent policy references are incomplete")
    if intent["primary_window"] != bundle["policies"]["temporal"]["primary_window"]:
        raise ValidationError("ALA request intent temporal scope does not match bundle")
    if intent["species_queries"] != [
        {
            "species_id": species["species_id"],
            "accepted_name": species["accepted_name"],
            "ala_taxon_concept_id": species["ala_taxon_concept_id"],
            "historical_aliases": list(species["historical_aliases"]),
        }
        for species in bundle["species"]
    ]:
        raise ValidationError("ALA request intent species scope does not match bundle")
    expected = {
        "synonym_normalization": resolution["synonym_normalization"],
        "accepted_descendants": resolution["accepted_descendants"],
        "pre_acquisition_scope_assertion_required": resolution["pre_acquisition_scope_assertion_required"],
        "taxon_identity_retention": resolution["taxon_identity_retention"],
        "expansion_failure_fallback": resolution["expansion_failure_fallback"],
        "subtaxon_policy": resolution["subtaxon_policy"],
    }
    for key, value in expected.items():
        if intent.get(key) != value:
            raise ValidationError(f"ALA request intent {key} does not match bundle")


def _camera_request_intent(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "synthetic_camera_ingest_request",
        "authority_status": "blocked_pending_P1-D008",
        "survey_supported_absence_rule_id": "P1-D009",
        "policy_references": ["P1-D008", "P1-D009", "P1-D010"],
        "absence_label": bundle["policies"]["camera"]["absence"]["label"],
    }


def _sorted_unique(rows: list[dict[str, Any]], field: str) -> list[Any]:
    return sorted({row[field] for row in rows})


def _sorted_optional_unique(rows: list[dict[str, Any]], field: str) -> list[Any]:
    return sorted({row[field] for row in rows if row.get(field)})


def _validated_decision_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValidationError("authoritative decision_bundle input is required")
    validate_phase1_decision_bundle(bundle)
    return bundle


def _bundle_provenance(bundle: dict[str, Any]) -> dict[str, Any]:
    readiness = validate_phase1_decision_bundle(bundle)
    return {
        "decision_bundle_id": readiness["bundle_id"],
        "decision_bundle_schema_version": readiness["schema_version"],
        "decision_consolidation_status": readiness["decision_consolidation_status"],
        "live_acquisition_status": readiness["live_acquisition_status"],
        "blocked_prerequisites": readiness["blocked_prerequisites"],
        "policy_provenance": {
            "accepted_presence_dominates": bundle["policies"]["source_combination"]["accepted_presence_dominates"],
            "camera_absence_label": bundle["policies"]["camera"]["absence"]["label"],
            "coordinate_assignment": bundle["policies"]["coordinate_assignment"]["assignment"],
            "nearest_land_cell_rescue": bundle["policies"]["coordinate_assignment"]["nearest_land_cell_rescue"],
            "source_collapse_executed": False,
            "spatial_assignment_executed": False,
            "ala_resolution_status": bundle["policies"]["species"]["ala_resolution"]["status"],
            "ala_resolution_evidence_package": bundle["policies"]["species"]["ala_resolution"]["evidence_package"],
        },
    }
