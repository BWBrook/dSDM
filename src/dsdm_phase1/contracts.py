"""Small validators for Phase 1 synthetic contract fixtures.

These functions enforce scaffold-level rules only. They do not choose species,
ALA filters, camera-trap interpretation, spatial rules, pseudoabsence rules, or
real QA tolerances.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    """Raised when a Phase 1 contract fixture violates a required rule."""


STAGE_REQUIRED_DECISIONS: dict[str, tuple[str, ...]] = {
    "species_contract": ("P1-D001", "P1-D002"),
    "source_contracts": ("P1-D007", "P1-D008", "P1-D009"),
    "mocked_acquisition_requests": (
        "P1-D003",
        "P1-D004",
        "P1-D005",
        "P1-D006",
        "P1-D007",
        "P1-D008",
        "P1-D009",
        "P1-D010",
    ),
}

REQUIRED_SPECIES_FIELDS = (
    "species_id",
    "scientific_name",
    "accepted_name",
    "common_name",
    "class",
    "include_phase1",
    "decision_status",
    "decision_reference",
)

REQUIRED_ROW_PROVENANCE_FIELDS = (
    "run_id",
    "row_id",
    "species_id",
    "scientific_name",
    "source",
    "source_record_id",
    "source_dataset_id",
    "source_dataset_name",
    "pa",
    "pa_type",
    "decision_manifest_id",
    "input_manifest_id",
)

ALLOWED_PA_TYPES = {"presence", "true_absence", "pseudoabsence"}

ALLOWED_SOURCE_TYPES = {"ala_occurrence", "camera_trap"}

REQUIRED_SOURCE_CONTRACT_FIELDS = (
    "source_id",
    "source_type",
    "decision_references",
    "local_path",
    "checksum",
    "license",
    "sensitivity",
    "provenance",
)

SOURCE_TYPE_DECISIONS = {
    "ala_occurrence": ("P1-D007",),
    "camera_trap": ("P1-D008", "P1-D009"),
}

SOURCE_TYPE_REQUIRED_BLOCKS = {
    "ala_occurrence": ("versioning",),
    "camera_trap": ("authority", "true_absence"),
}


def validate_decision_manifest(
    manifest: dict[str, Any], *, stage: str
) -> dict[str, Any]:
    """Validate that all decisions required for a stage are resolved."""

    if stage not in STAGE_REQUIRED_DECISIONS:
        known = ", ".join(sorted(STAGE_REQUIRED_DECISIONS))
        raise ValidationError(f"Unknown stage {stage!r}; known stages: {known}")

    decisions = manifest.get("decisions")
    if not isinstance(decisions, list):
        raise ValidationError("decision manifest requires a decisions list")

    by_id: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValidationError("each decision must be an object")
        decision_id = decision.get("id")
        if not isinstance(decision_id, str) or not decision_id:
            raise ValidationError("each decision requires a non-empty id")
        by_id[decision_id] = decision

    missing: list[str] = []
    unresolved: list[str] = []
    for decision_id in STAGE_REQUIRED_DECISIONS[stage]:
        decision = by_id.get(decision_id)
        if decision is None:
            missing.append(decision_id)
        elif decision.get("status") != "resolved":
            unresolved.append(decision_id)

    if missing or unresolved:
        details: list[str] = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unresolved:
            details.append("unresolved: " + ", ".join(unresolved))
        raise ValidationError(
            f"Stage {stage!r} blocked by required decisions; " + "; ".join(details)
        )

    return {
        "stage": stage,
        "required_decisions": list(STAGE_REQUIRED_DECISIONS[stage]),
        "manifest_id": manifest.get("manifest_id"),
    }


def validate_species_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate a synthetic focal-species contract."""

    species = contract.get("species")
    if not isinstance(species, list) or not species:
        raise ValidationError("species contract requires a non-empty species list")

    included_ids: list[str] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(species, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"species row {index} must be an object")
        missing = [field for field in REQUIRED_SPECIES_FIELDS if field not in row]
        if missing:
            raise ValidationError(
                f"species row {index} missing required fields: {', '.join(missing)}"
            )
        species_id = row["species_id"]
        if not isinstance(species_id, str) or not species_id:
            raise ValidationError(f"species row {index} requires a non-empty species_id")
        if species_id in seen_ids:
            raise ValidationError(f"duplicate species_id: {species_id}")
        seen_ids.add(species_id)
        if row["include_phase1"] is True:
            if row["decision_status"] != "resolved":
                raise ValidationError(
                    f"included species {species_id} has unresolved decision status"
                )
            included_ids.append(species_id)

    return {
        "included_species_ids": included_ids,
        "species_count": len(species),
        "contract_kind": contract.get("fixture_kind"),
    }


def validate_source_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate row-level provenance and presence/absence category separation."""

    if not rows:
        raise ValidationError("source row fixture requires at least one row")

    pa_types: set[str] = set()
    sources_by_pa_type: dict[str, set[str]] = {}

    for index, row in enumerate(rows, start=1):
        missing = [field for field in REQUIRED_ROW_PROVENANCE_FIELDS if field not in row]
        if missing:
            raise ValidationError(
                f"source row {index} missing required fields: {', '.join(missing)}"
            )
        pa_type = row["pa_type"]
        if pa_type not in ALLOWED_PA_TYPES:
            allowed = ", ".join(sorted(ALLOWED_PA_TYPES))
            raise ValidationError(f"source row {index} has invalid pa_type {pa_type!r}; allowed: {allowed}")
        pa = row["pa"]
        if pa_type == "presence" and pa != 1:
            raise ValidationError(f"source row {index} has presence pa_type but pa != 1")
        if pa_type in {"true_absence", "pseudoabsence"} and pa != 0:
            raise ValidationError(f"source row {index} has absence pa_type but pa != 0")
        if pa_type == "true_absence" and not row.get("true_absence_rule_id"):
            raise ValidationError(f"source row {index} true_absence requires true_absence_rule_id")
        if pa_type == "pseudoabsence" and not row.get("pseudoabsence_rule_id"):
            raise ValidationError(f"source row {index} pseudoabsence requires pseudoabsence_rule_id")
        pa_types.add(pa_type)
        sources_by_pa_type.setdefault(pa_type, set()).add(row["source"])

    return {
        "row_count": len(rows),
        "pa_types": sorted(pa_types),
        "sources_by_pa_type": {
            pa_type: sorted(sources)
            for pa_type, sources in sorted(sources_by_pa_type.items())
        },
        "required_provenance_fields": list(REQUIRED_ROW_PROVENANCE_FIELDS),
    }


def validate_manifest_checksums(
    manifest: dict[str, Any], *, base_dir: Path | str
) -> dict[str, Any]:
    """Validate SHA-256 checksums for files listed in a synthetic manifest."""

    base = Path(base_dir).resolve()
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValidationError("manifest requires a non-empty files list")

    checked: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValidationError("manifest file entries must be objects")
        path_text = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(path_text, str) or not path_text:
            raise ValidationError("manifest file entry requires path")
        _validate_sha256_hex_digest(
            expected, label=f"manifest file {path_text}"
        )
        _validate_safe_relative_path(path_text, label="manifest file")

        path = (base / path_text).resolve()
        if base != path and base not in path.parents:
            raise ValidationError(f"manifest file path escapes base directory: {path_text}")
        if not path.exists():
            raise ValidationError(f"manifest file does not exist: {path_text}")

        actual = _sha256(path)
        if actual != expected:
            raise ValidationError(
                f"checksum mismatch for {path_text}: expected {expected}, got {actual}"
            )
        checked.append(path_text)

    return {
        "manifest_id": manifest.get("manifest_id"),
        "checked_files": checked,
    }


def validate_source_contracts(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate synthetic source-contract metadata without reading sources."""

    contracts = bundle.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        raise ValidationError("source-contract bundle requires a non-empty contracts list")

    source_ids: list[str] = []
    source_types: set[str] = set()
    decision_references: set[str] = set()

    for index, contract in enumerate(contracts, start=1):
        if not isinstance(contract, dict):
            raise ValidationError(f"source contract {index} must be an object")
        missing = [
            field
            for field in REQUIRED_SOURCE_CONTRACT_FIELDS
            if field not in contract
        ]
        if missing:
            raise ValidationError(
                f"source contract {index} missing required fields: {', '.join(missing)}"
            )

        source_id = contract["source_id"]
        if not isinstance(source_id, str) or not source_id:
            raise ValidationError(f"source contract {index} requires a non-empty source_id")
        if source_id in source_ids:
            raise ValidationError(f"duplicate source_id: {source_id}")

        source_type = contract["source_type"]
        if source_type not in ALLOWED_SOURCE_TYPES:
            allowed = ", ".join(sorted(ALLOWED_SOURCE_TYPES))
            raise ValidationError(
                f"source contract {source_id} has invalid source_type {source_type!r}; allowed: {allowed}"
            )

        references = contract["decision_references"]
        if not isinstance(references, list) or not references:
            raise ValidationError(f"source contract {source_id} requires decision_references")
        if not all(isinstance(item, str) and item for item in references):
            raise ValidationError(f"source contract {source_id} decision_references must be non-empty strings")
        for decision_id in SOURCE_TYPE_DECISIONS[source_type]:
            if decision_id not in references:
                raise ValidationError(
                    f"source contract {source_id} missing decision reference {decision_id}"
                )

        _validate_safe_relative_path(
            contract["local_path"], label=f"source contract {source_id}"
        )
        _validate_checksum_block(contract["checksum"], label=f"source contract {source_id}")
        _require_non_empty_string(contract, "license", source_id)
        _require_non_empty_string(contract, "sensitivity", source_id)
        _require_non_empty_mapping(contract, "provenance", source_id)
        for block_name in SOURCE_TYPE_REQUIRED_BLOCKS[source_type]:
            block = _require_non_empty_mapping(contract, block_name, source_id)
            expected_decision = {
                "versioning": "P1-D007",
                "authority": "P1-D008",
                "true_absence": "P1-D009",
            }[block_name]
            if block.get("decision_id") != expected_decision:
                raise ValidationError(
                    f"source contract {source_id} {block_name} must reference {expected_decision}"
                )

        source_ids.append(source_id)
        source_types.add(source_type)
        decision_references.update(references)

    return {
        "source_ids": source_ids,
        "source_types": sorted(source_types),
        "decision_references": sorted(decision_references),
        "contract_count": len(contracts),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_safe_relative_path(path_text: Any, *, label: str) -> None:
    if not isinstance(path_text, str) or not path_text:
        raise ValidationError(f"{label} requires a path")
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationError(f"{label} path is not a safe relative path: {path_text}")
    if path.parts and path.parts[0] in {"data", "temp"}:
        raise ValidationError(f"{label} path cannot target real payload directory: {path_text}")


def _validate_checksum_block(block: Any, *, label: str) -> None:
    if not isinstance(block, dict):
        raise ValidationError(f"{label} requires checksum metadata")
    algorithm = block.get("algorithm")
    value = block.get("value")
    if algorithm != "sha256":
        raise ValidationError(f"{label} checksum algorithm must be sha256")
    _validate_sha256_hex_digest(value, label=f"{label} checksum value")


def _validate_sha256_hex_digest(value: Any, *, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValidationError(f"{label} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValidationError(f"{label} must be a SHA-256 hex digest") from exc


def _require_non_empty_string(
    contract: dict[str, Any], field: str, source_id: str
) -> str:
    value = contract.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"source contract {source_id} requires non-empty {field}")
    return value


def _require_non_empty_mapping(
    contract: dict[str, Any], field: str, source_id: str
) -> dict[str, Any]:
    value = contract.get(field)
    if not isinstance(value, dict) or not value:
        raise ValidationError(f"source contract {source_id} requires {field}")
    return value
