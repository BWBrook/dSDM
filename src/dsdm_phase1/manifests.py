"""Synthetic acquisition-manifest dry-run helpers."""

from __future__ import annotations

from typing import Any

from .contracts import (
    ValidationError,
    validate_decision_manifest,
    validate_source_contracts,
    validate_species_contract,
)


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


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
