"""Synthetic acquisition-manifest dry-run helpers."""

from __future__ import annotations

from typing import Any

from .contracts import (
    ValidationError,
    validate_decision_manifest,
    validate_source_contracts,
    validate_species_contract,
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
    species_decision_manifest: dict[str, Any],
    species_contract: dict[str, Any],
    source_decision_manifest: dict[str, Any],
    source_contracts: dict[str, Any],
) -> dict[str, Any]:
    """Validate synthetic gates and return deterministic preflight summary data."""

    if not isinstance(run_id, str) or not run_id:
        raise ValidationError("dry-run summary requires a non-empty run_id")

    species_decisions = validate_decision_manifest(
        species_decision_manifest, stage="species_contract"
    )
    source_decisions = validate_decision_manifest(
        source_decision_manifest, stage="source_contracts"
    )
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
        "decision_manifest_ids": {
            "species_contract": species_decisions["manifest_id"],
            "source_contracts": source_decisions["manifest_id"],
        },
        "required_decisions": _dedupe(
            species_decisions["required_decisions"]
            + source_decisions["required_decisions"]
        ),
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
    }


def build_mocked_acquisition_request_manifest(
    *,
    run_id: str,
    species_decision_manifest: dict[str, Any],
    species_contract: dict[str, Any],
    source_decision_manifest: dict[str, Any],
    source_contracts: dict[str, Any],
    request_decision_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Return deterministic, non-executed synthetic request-manifest records."""

    dry_run = build_acquisition_dry_run_summary(
        run_id=run_id,
        species_decision_manifest=species_decision_manifest,
        species_contract=species_contract,
        source_decision_manifest=source_decision_manifest,
        source_contracts=source_contracts,
    )
    request_decisions = validate_decision_manifest(
        request_decision_manifest, stage="mocked_acquisition_requests"
    )
    decision_values = _decision_values_by_id(request_decision_manifest)

    requests = [
        _mocked_request_record(source, run_id=run_id, decision_values=decision_values)
        for source in dry_run["sources"]
    ]

    return {
        "run_id": run_id,
        "stage": "mocked_acquisition_request_dry_run",
        "status": "ready_for_mocked_request_review",
        "dry_run_status": dry_run["status"],
        "decision_manifest_ids": {
            **dry_run["decision_manifest_ids"],
            "request_manifest": request_decisions["manifest_id"],
        },
        "required_decisions": _sort_decision_ids(
            dry_run["required_decisions"] + request_decisions["required_decisions"]
        ),
        "source_ids": dry_run["source_ids"],
        "source_types": dry_run["source_types"],
        "request_count": len(requests),
        "requests": requests,
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


def _mocked_request_record(
    source: dict[str, Any], *, run_id: str, decision_values: dict[str, Any]
) -> dict[str, Any]:
    source_type = source["source_type"]
    if source_type == "ala_occurrence":
        decision_references = list(ALA_REQUEST_DECISIONS)
        intent = _ala_request_intent(decision_values)
    elif source_type == "camera_trap":
        decision_references = list(CAMERA_REQUEST_DECISIONS)
        intent = _camera_request_intent(decision_values)
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


def _ala_request_intent(decision_values: dict[str, Any]) -> dict[str, Any]:
    query_names = _required_string_list(decision_values, "P1-D003", "query_names")
    return {
        "kind": "synthetic_ala_request",
        "query_names": query_names,
        "alias_policy_id": _required_string(
            decision_values, "P1-D003", "alias_policy_id"
        ),
        "date_filter_policy_id": _required_string(
            decision_values, "P1-D004", "date_filter_policy_id"
        ),
        "data_resource_filter_policy_id": _required_string(
            decision_values, "P1-D005", "data_resource_filter_policy_id"
        ),
        "quality_filter_policy_id": _required_string(
            decision_values, "P1-D006", "quality_filter_policy_id"
        ),
        "versioning_policy_id": _required_string(
            decision_values, "P1-D007", "versioning_policy_id"
        ),
    }


def _camera_request_intent(decision_values: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "synthetic_camera_ingest_request",
        "camera_authority_id": _required_string(
            decision_values, "P1-D008", "camera_authority_id"
        ),
        "true_absence_rule_id": _required_string(
            decision_values, "P1-D009", "true_absence_rule_id"
        ),
        "effort_policy_id": _required_string(
            decision_values, "P1-D010", "effort_policy_id"
        ),
    }


def _decision_values_by_id(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        decision["id"]: decision.get("value")
        for decision in manifest["decisions"]
    }


def _required_mapping(
    decision_values: dict[str, Any], decision_id: str
) -> dict[str, Any]:
    value = decision_values.get(decision_id)
    if not isinstance(value, dict):
        raise ValidationError(
            f"mocked request decision {decision_id} requires object value"
        )
    return value


def _required_string(
    decision_values: dict[str, Any], decision_id: str, field: str
) -> str:
    value = _required_mapping(decision_values, decision_id).get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(
            f"mocked request decision {decision_id} requires non-empty {field}"
        )
    return value


def _required_string_list(
    decision_values: dict[str, Any], decision_id: str, field: str
) -> list[str]:
    value = _required_mapping(decision_values, decision_id).get(field)
    if not isinstance(value, list) or not value:
        raise ValidationError(
            f"mocked request decision {decision_id} requires non-empty {field}"
        )
    if not all(isinstance(item, str) and item for item in value):
        raise ValidationError(
            f"mocked request decision {decision_id} {field} must contain strings"
        )
    return list(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _sort_decision_ids(values: list[str]) -> list[str]:
    return sorted(set(values), key=_decision_sort_key)


def _decision_sort_key(decision_id: str) -> tuple[str, int | str]:
    prefix, separator, number = decision_id.rpartition("D")
    if separator:
        try:
            return (prefix, int(number))
        except ValueError:
            pass
    return (decision_id, decision_id)
