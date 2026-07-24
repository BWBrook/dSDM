"""Offline, aggregate-only calibration of the ALA occurrence field contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ALAFieldContractError(ValueError):
    """Raised when Goal 016 evidence fails closed."""


GOAL_ID = "goal016-ala-field-contract-calibration-2026-07-24"
RAW_SHA256 = "af89c756dc911602f657cf27622dc1585340983a114c211559fee1762be1dd13"
RAW_BYTES = 24335
RAW_ROWS = 17
RAW_COLUMNS = 144
REQUEST_PROFILE_SHA256 = (
    "60082efbebde02558ce3f0ef45b0676f21332e11b16796207e91eee19b18155f"
)
CONTRACT_SHA256 = (
    "98cd67c17dbe5a9c55b4f17c8a4f6e383010d9d8724dff23bc9c3911051b9159"
)
UPSTREAM_PASS = "galah_route_usable_for_later_acquisition_design"
TRACKED_ONLY = "ala_field_contract_tracked_evidence_valid_raw_replay_required"
RAW_DECISION = (
    "count_census_ready_full_row_acquisition_blocked_on_provider_identity"
)
TRACKED_FILENAMES = ["profile.json", "contract.json", "review.json"]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EMAIL_RE = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
YEAR_RE = re.compile(r"^\d{4}(?:\.0)?$")
BOOLEAN_TOKENS = {"true", "false", "1", "0", "yes", "no"}
QA_FIELDS_SHA256 = (
    "311fd0f0167194b886420e4636d7edb33bed584d290135c398e993e7677fd038"
)
EXPECTED_FIELD_STATS = {
    "occurrenceID": (0, 0, 0),
    "dataResourceUid": (17, 1, 17),
    "dataResourceName": (17, 1, 17),
    "datasetID": (0, 0, 0),
    "datasetName": (0, 0, 0),
    "eventDate": (17, 16, 17),
    "year": (17, 1, 17),
    "decimalLatitude": (17, 17, 17),
    "decimalLongitude": (17, 17, 17),
    "coordinateUncertaintyInMeters": (17, 4, 17),
    "coordinatePrecision": (0, 0, 0),
    "raw_scientificName": (17, 2, 17),
    "raw_taxonConceptID": (0, 0, 0),
    "scientificName": (17, 1, 17),
    "taxonConceptID": (17, 1, 17),
    "acceptedNameUsage": (0, 0, 0),
    "acceptedNameUsageID": (0, 0, 0),
    "taxonRank": (17, 1, 17),
    "assertions": (17, 2, 17),
    "dcterms:license": (17, 1, 17),
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ALAFieldContractError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ALAFieldContractError(f"cannot load JSON: {path}") from error
    _require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def _exact_keys(value: Any, expected: set[str], label: str) -> None:
    _require(
        isinstance(value, dict) and set(value) == expected,
        f"{label} shape drifted",
    )


def _resolved(root: Path, value: str) -> Path:
    _require(isinstance(value, str) and value, "configured path is invalid")
    path = Path(value)
    return path if path.is_absolute() else root / path


def _regular_file(path: Path, label: str) -> None:
    _require(path.exists(), f"{label} is missing")
    _require(not path.is_symlink() and path.is_file(), f"{label} is unsafe")


def validate_contract(contract: dict[str, Any]) -> None:
    """Validate the reusable contract without study-region assumptions."""

    _exact_keys(
        contract,
        {
            "schema_version",
            "contract_id",
            "scope",
            "record_identity",
            "provenance",
            "temporal",
            "spatial",
            "taxonomy",
            "licence",
            "quality_assertions",
            "readiness_gates",
        },
        "field contract",
    )
    _require(
        contract["schema_version"] == "1.0"
        and contract["contract_id"] == "ala-occurrence-field-contract-v1",
        "field contract identity drifted",
    )
    _require(
        contract["scope"]
        == {
            "source_namespace": "ala_occurrence",
            "generic_across_study_regions": True,
            "normalization_performed": False,
        },
        "field contract scope drifted",
    )
    identity = contract["record_identity"]
    _require(
        identity
        == {
            "canonical_field": "provider_record_id",
            "provider_candidates": ["recordID", "occurrenceID"],
            "selection": "first_complete_unique_candidate_in_configured_order",
            "content_fallback_allowed": False,
            "snapshot_row_id": (
                "sha256(source_namespace + raw_artifact_sha256 + "
                "one_based_row_ordinal)"
            ),
            "snapshot_row_id_scope": "frozen_artifact_only",
            "content_fingerprint_role": (
                "diagnostic_only_not_identity_or_deduplication"
            ),
        },
        "record identity contract drifted",
    )
    _require(
        contract["provenance"]["dataset_resource_fallback_allowed"] is False,
        "dataset and resource provenance must remain separate",
    )
    spatial = contract["spatial"]
    _require(
        spatial["reported_uncertainty_exclusion_threshold_m"] == 1000
        and spatial["missing_uncertainty_action"]
        == "preserve_unknown_and_retain"
        and spatial["decimal_place_precision_inference"] == "forbidden",
        "coordinate uncertainty or precision policy drifted",
    )
    licence = contract["licence"]
    _require(
        licence["requested_field"] == "license"
        and licence["returned_candidates"] == ["dcterms:license", "license"],
        "licence alias contract drifted",
    )
    qa = contract["quality_assertions"]
    _require(
        qa["any_flag_rejects"] is False
        and qa["hard_exclusions_require_explicit_configuration"] is True
        and qa["unknown_extra_field_action"] == "fail_schema_review",
        "quality-assertion policy drifted",
    )
    gates = contract["readiness_gates"]
    _require(
        gates
        == {
            "count_census_requires_provider_identity": False,
            "full_row_acquisition_requires_provider_identity": True,
            "branch_count_union_without_provider_identity": "forbidden",
        },
        "readiness gates drifted",
    )
    serialized = json.dumps(contract, sort_keys=True).lower()
    _require(
        "tasmania" not in serialized and "2001" not in serialized,
        "generic contract contains study-specific scope",
    )


def validate_plan(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    """Validate and bind the exact offline Goal 016 calibration inputs."""

    _exact_keys(
        plan,
        {
            "schema_version",
            "goal_id",
            "mode",
            "network_calls_allowed",
            "source",
            "calibration",
            "evidence",
        },
        "calibration plan",
    )
    _require(
        plan["schema_version"] == "1.0"
        and plan["goal_id"] == GOAL_ID
        and plan["mode"] == "offline_exact_raw_replay"
        and plan["network_calls_allowed"] == 0,
        "calibration plan identity or offline boundary drifted",
    )
    source = plan["source"]
    _exact_keys(
        source,
        {"occurrence_csv", "goal015", "request_profile", "field_contract"},
        "calibration sources",
    )
    raw = source["occurrence_csv"]
    _require(
        raw
        == {
            "path": (
                "data/raw/ala/goal015-galah-pilot/2026-07-24/"
                "galah-occurrences.csv"
            ),
            "sha256": RAW_SHA256,
            "bytes": RAW_BYTES,
            "rows": RAW_ROWS,
            "columns": RAW_COLUMNS,
            "tracked": False,
        },
        "frozen occurrence binding drifted",
    )
    goal015 = source["goal015"]
    _exact_keys(
        goal015,
        {
            "plan_path",
            "evidence_directory",
            "raw_directory",
            "required_raw_backed_readiness",
        },
        "Goal 015 binding",
    )
    _require(
        goal015["required_raw_backed_readiness"] == UPSTREAM_PASS,
        "Goal 015 readiness binding drifted",
    )
    request_profile = source["request_profile"]
    field_contract = source["field_contract"]
    _require(
        request_profile
        == {
            "path": "config/ala_acquisition_request_profile.json",
            "sha256": REQUEST_PROFILE_SHA256,
        },
        "request-profile binding drifted",
    )
    _require(
        field_contract
        == {
            "path": "config/ala_field_contract.json",
            "sha256": CONTRACT_SHA256,
        },
        "field-contract binding drifted",
    )
    for binding, label in (
        (request_profile, "request profile"),
        (field_contract, "field contract"),
    ):
        path = _resolved(root, binding["path"])
        _regular_file(path, label)
        _require(sha256(path) == binding["sha256"], f"{label} checksum drifted")
    contract = _load_json(_resolved(root, field_contract["path"]))
    validate_contract(contract)

    calibration = plan["calibration"]
    _exact_keys(
        calibration,
        {
            "returned_core_fields",
            "expanded_qa_fields",
            "expanded_qa_basis",
            "content_fingerprint_fields",
            "content_fingerprint_role",
            "primary_year_window",
            "count_census_estimand",
            "count_census_not_estimands",
        },
        "calibration settings",
    )
    core = calibration["returned_core_fields"]
    _require(
        isinstance(core, list)
        and len(core) == 20
        and len(set(core)) == 20
        and "dcterms:license" in core
        and "license" not in core
        and "assertions" in core,
        "returned core-field inventory drifted",
    )
    qa_fields = calibration["expanded_qa_fields"]
    _require(
        isinstance(qa_fields, list)
        and len(qa_fields) == 124
        and len(set(qa_fields)) == 124
        and all(isinstance(field, str) and field for field in qa_fields)
        and set(qa_fields).isdisjoint(core)
        and hashlib.sha256(
            json.dumps(qa_fields, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        == QA_FIELDS_SHA256,
        "expanded QA allowlist drifted",
    )
    _require(
        calibration["expanded_qa_basis"].startswith(
            "all_non_core_columns_from_the_exact_goal015"
        )
        and calibration["content_fingerprint_fields"]
        == [
            "dataResourceUid",
            "taxonConceptID",
            "eventDate",
            "decimalLatitude",
            "decimalLongitude",
        ]
        and calibration["content_fingerprint_role"]
        == "aggregate_duplicate_diagnostic_only",
        "QA or duplicate-diagnostic calibration drifted",
    )
    _require(
        calibration["primary_year_window"]
        == {"start": 2001, "end": 2025, "inclusive": True}
        and calibration["count_census_estimand"]
        == (
            "ALA indexed records matching each separately manifested "
            "canonical query at retrieval time"
        )
        and calibration["count_census_not_estimands"]
        == ["independent observations", "animals", "occupancy", "abundance"],
        "count-census estimand drifted",
    )
    evidence = plan["evidence"]
    _require(
        evidence
        == {
            "directory": "evidence/ala_field_contract/2026-07-24",
            "files": TRACKED_FILENAMES,
            "tracked_rows": 0,
            "raw_replay_required_for_decision": True,
        },
        "evidence contract drifted",
    )
    return contract


def _is_nonblank(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _format_valid(field: str, value: str) -> bool:
    if field == "eventDate":
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return bool(re.match(r"^\d{4}-\d{2}-\d{2}", value))
        except ValueError:
            return False
    if field == "year":
        return YEAR_RE.fullmatch(value) is not None
    if field in {
        "decimalLatitude",
        "decimalLongitude",
        "coordinateUncertaintyInMeters",
        "coordinatePrecision",
    }:
        if NUMBER_RE.fullmatch(value) is None:
            return False
        number = float(value)
        if field == "decimalLatitude":
            return -90 <= number <= 90
        if field == "decimalLongitude":
            return -180 <= number <= 180
        return number >= 0
    if field in {
        "taxonConceptID",
        "raw_taxonConceptID",
        "acceptedNameUsageID",
    }:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    return True


def _semantic_type(field: str) -> str:
    if field == "eventDate":
        return "iso_date_or_datetime_text"
    if field == "year":
        return "four_digit_year"
    if field in {"decimalLatitude", "decimalLongitude"}:
        return "bounded_numeric"
    if field in {"coordinateUncertaintyInMeters", "coordinatePrecision"}:
        return "nonnegative_numeric"
    if field in {
        "taxonConceptID",
        "raw_taxonConceptID",
        "acceptedNameUsageID",
    }:
        return "uri_text"
    return "text"


def _read_bound_csv(
    path: Path, binding: dict[str, Any]
) -> tuple[list[str], list[dict[str, str]]]:
    _regular_file(path, "frozen occurrence CSV")
    _require(path.stat().st_size == binding["bytes"], "raw byte size drifted")
    _require(sha256(path) == binding["sha256"], "raw checksum drifted")
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, csv.Error) as error:
        raise ALAFieldContractError("cannot parse frozen occurrence CSV") from error
    _require(
        len(fields) == binding["columns"]
        and len(set(fields)) == len(fields)
        and len(rows) == binding["rows"]
        and all(set(row) == set(fields) for row in rows),
        "raw dimensions, headers, or row shape drifted",
    )
    return fields, rows


def _field_metric(
    field: str, fields: list[str], rows: list[dict[str, str]]
) -> dict[str, Any]:
    if field not in fields:
        return {
            "field": field,
            "present": False,
            "nonblank_count": 0,
            "blank_count": len(rows),
            "distinct_nonblank_count": 0,
            "semantic_type": _semantic_type(field),
            "format_valid_nonblank_count": 0,
        }
    nonblank = [row[field].strip() for row in rows if _is_nonblank(row[field])]
    return {
        "field": field,
        "present": True,
        "nonblank_count": len(nonblank),
        "blank_count": len(rows) - len(nonblank),
        "distinct_nonblank_count": len(set(nonblank)),
        "semantic_type": _semantic_type(field),
        "format_valid_nonblank_count": sum(
            _format_valid(field, value) for value in nonblank
        ),
    }


def _profile(
    plan: dict[str, Any],
    fields: list[str],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    binding = plan["source"]["occurrence_csv"]
    core = plan["calibration"]["returned_core_fields"]
    _require(set(core).issubset(fields), "configured core fields are missing")
    extras = [field for field in fields if field not in core]
    _require(
        extras == plan["calibration"]["expanded_qa_fields"],
        "expanded QA field allowlist drifted",
    )

    metrics = [_field_metric(field, fields, rows) for field in core]
    candidates = [
        _field_metric(field, fields, rows)
        for field in ["recordID", "occurrenceID"]
    ]
    selected = next(
        (
            item["field"]
            for item in candidates
            if item["present"]
            and item["nonblank_count"] == len(rows)
            and item["distinct_nonblank_count"] == len(rows)
        ),
        None,
    )

    qa_columns: list[list[str]] = [
        [row[field].strip().lower() for row in rows] for field in extras
    ]
    boolean_cells = sum(
        value in BOOLEAN_TOKENS for column in qa_columns for value in column
    )
    _require(
        boolean_cells == len(extras) * len(rows),
        "non-core field is not Boolean-compatible QA evidence",
    )
    always_false = sum(
        set(column).issubset({"false", "0", "no"}) for column in qa_columns
    )
    always_true = sum(
        set(column).issubset({"true", "1", "yes"}) for column in qa_columns
    )
    mixed = len(extras) - always_false - always_true
    true_per_row = [
        sum(
            rows[index][field].strip().lower() in {"true", "1", "yes"}
            for field in extras
        )
        for index in range(len(rows))
    ]

    dates = [
        row["eventDate"].strip()
        for row in rows
        if _is_nonblank(row["eventDate"])
    ]
    year_consistent = 0
    for row in rows:
        if not (_is_nonblank(row["eventDate"]) and _is_nonblank(row["year"])):
            continue
        try:
            date_year = datetime.fromisoformat(
                row["eventDate"].strip().replace("Z", "+00:00")
            ).year
            year_consistent += date_year == int(float(row["year"].strip()))
        except ValueError:
            continue

    valid_coordinates = 0
    uncertainty_over_threshold = 0
    for row in rows:
        latitude = row["decimalLatitude"].strip()
        longitude = row["decimalLongitude"].strip()
        if (
            _is_nonblank(latitude)
            and _is_nonblank(longitude)
            and _format_valid("decimalLatitude", latitude)
            and _format_valid("decimalLongitude", longitude)
        ):
            valid_coordinates += 1
        uncertainty = row["coordinateUncertaintyInMeters"].strip()
        if (
            _is_nonblank(uncertainty)
            and _format_valid("coordinateUncertaintyInMeters", uncertainty)
            and float(uncertainty) > 1000
        ):
            uncertainty_over_threshold += 1

    full_rows = [tuple(row[field] for field in fields) for row in rows]
    fingerprint_fields = plan["calibration"]["content_fingerprint_fields"]
    fingerprints = [
        tuple(row[field].strip() for field in fingerprint_fields) for row in rows
    ]
    complete_fingerprints = [
        value for value in fingerprints if all(_is_nonblank(item) for item in value)
    ]
    return {
        "schema_version": "1.0",
        "source_type": "goal016_offline_csv_aggregate_profile",
        "source_artifact": {
            "path": binding["path"],
            "sha256": binding["sha256"],
            "bytes": binding["bytes"],
            "rows": len(rows),
            "columns": len(fields),
            "unique_headers": len(set(fields)),
        },
        "csv_semantics": {
            "population_measure": "nonblank_and_blank_serialized_csv_cells",
            "original_provider_or_pandas_types_recoverable": False,
            "original_null_distinguishable_from_empty_string": False,
        },
        "field_population": metrics,
        "provider_identity": {
            "candidates": candidates,
            "selected_field": selected,
            "complete_unique_provider_identity": selected is not None,
            "content_fallback_used": False,
        },
        "temporal_checks": {
            "event_date_parseable_nonblank_count": sum(
                _format_valid("eventDate", value) for value in dates
            ),
            "date_year_consistent_count": year_consistent,
        },
        "spatial_checks": {
            "valid_coordinate_pair_count": valid_coordinates,
            "reported_uncertainty_over_1000_m_count": (
                uncertainty_over_threshold
            ),
            "decimal_place_precision_inference_performed": False,
        },
        "quality_assertions": {
            "expanded_field_count": len(extras),
            "expanded_cell_count": len(extras) * len(rows),
            "boolean_compatible_cell_count": boolean_cells,
            "always_false_field_count": always_false,
            "always_true_field_count": always_true,
            "mixed_field_count": mixed,
            "minimum_true_flags_per_row": min(true_per_row),
            "maximum_true_flags_per_row": max(true_per_row),
            "unknown_extra_field_count": 0,
        },
        "duplicate_diagnostics": {
            "full_row_distinct_count": len(set(full_rows)),
            "full_row_duplicate_count": len(rows) - len(set(full_rows)),
            "content_fingerprint_component_count": len(fingerprint_fields),
            "complete_content_fingerprint_count": len(complete_fingerprints),
            "distinct_complete_content_fingerprint_count": len(
                set(complete_fingerprints)
            ),
            "content_fingerprint_used_as_identity": False,
        },
    }


def _contract_evidence(
    plan: dict[str, Any],
    contract: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    identity = profile["provider_identity"]
    return {
        "schema_version": "1.0",
        "source_type": "goal016_calibrated_field_contract",
        "contract_id": contract["contract_id"],
        "config_binding": {
            "path": plan["source"]["field_contract"]["path"],
            "sha256": plan["source"]["field_contract"]["sha256"],
        },
        "record_identity": {
            "provider_candidates": contract["record_identity"][
                "provider_candidates"
            ],
            "selected_provider_field": identity["selected_field"],
            "provider_identity_status": (
                "calibrated_complete_unique"
                if identity["complete_unique_provider_identity"]
                else "unresolved_no_complete_unique_candidate"
            ),
            "recordID_status": "uncalibrated_absent_from_frozen_projection",
            "snapshot_row_id_scope": "frozen_artifact_only",
            "content_fingerprint_role": (
                "diagnostic_only_not_identity_or_deduplication"
            ),
        },
        "canonical_mappings": {
            "resource_and_dataset_provenance": (
                "separate_without_cross_level_fallback"
            ),
            "event_year": (
                "year_then_eventDate_with_conflict_exclusion_and_flag"
            ),
            "coordinates": (
                "numeric_global_range_for_spatial_eligibility"
            ),
            "uncertainty": (
                "reported_value_over_1000_m_excludes_spatial_use; "
                "missing_remains_unknown"
            ),
            "coordinate_precision": (
                "reported_only; no_decimal_place_inference"
            ),
            "accepted_taxon_identity": (
                "pinned_focal_species_and_concept_configuration"
            ),
            "licence": "requested_license_returned_as_dcterms:license",
            "quality_assertions": (
                "preserve_summary_and_boolean_flags; "
                "only_configured_hard_exclusions_reject"
            ),
        },
        "legacy_request_profile_compatibility": {
            "path": plan["source"]["request_profile"]["path"],
            "sha256": plan["source"]["request_profile"]["sha256"],
            "count_only_query_surface": "usable",
            "future_full_row_mapping": "incompatible",
            "material_reasons": [
                "occurrenceID is required there but empty in the frozen sample",
                "returned licence uses the explicit dcterms:license alias",
                "dataset fallback to resource fields conflates provenance levels",
            ],
        },
    }


def _review(
    plan: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    unresolved = not profile["provider_identity"][
        "complete_unique_provider_identity"
    ]
    _require(unresolved, "frozen sample unexpectedly resolved provider identity")
    return {
        "schema_version": "1.0",
        "source_type": "goal016_field_contract_review",
        "outcome": "completed",
        "readiness": TRACKED_ONLY,
        "raw_replay": "required_for_goal016_readiness_decision",
        "decisions": {
            "nine_species_2001_2025_count_census": "ready",
            "full_row_acquisition": (
                "blocked_unresolved_provider_record_identity"
            ),
            "cross_download_deduplication": (
                "blocked_unresolved_provider_record_identity"
            ),
            "branch_count_union_without_provider_identity": "forbidden",
        },
        "count_census_estimand": plan["calibration"]["count_census_estimand"],
        "limitations": [
            (
                "The sample covers one species, one year, and one source "
                "resource; it cannot establish nine-species field completeness."
            ),
            (
                "recordID is an uncalibrated candidate absent from the frozen "
                "projection; occurrenceID is present but empty."
            ),
            (
                "CSV replay measures serialized nonblank cells and formats, "
                "not original provider or pandas types."
            ),
        ],
        "next_step": (
            "Run separately manifested canonical-query counts for the nine "
            "species; calibrate a provider identifier before any full row "
            "acquisition or branch union."
        ),
    }


def _scan_tracked(value: Any, path: str = "root") -> None:
    forbidden_keys = {
        "email",
        "contact",
        "token",
        "jwt",
        "authorization",
        "rowpayload",
        "rowvalues",
        "coordinatevalues",
        "eventdatevalues",
        "identifiervalues",
        "snapshotrowids",
        "contentfingerprints",
        "samples",
        "examples",
        "values",
        "joburl",
        "downloadurl",
        "statusurl",
    }
    if isinstance(value, str):
        _require(not EMAIL_RE.search(value), f"contact leakage at {path}")
        _require(
            re.search(r"(?i)\bBearer\s+\S{20,}", value) is None,
            f"authorization leakage at {path}",
        )
        _require(
            re.search(r"\beyJ[A-Za-z0-9_-]{12,}\.", value) is None,
            f"JWT-like leakage at {path}",
        )
    elif isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            _require(
                normalized not in forbidden_keys,
                f"row-level or private key at {path}.{key}",
            )
            _scan_tracked(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_tracked(item, f"{path}[{index}]")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _scan_tracked(value)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_evidence(
    evidence_dir: Path,
    profile: dict[str, Any],
    contract: dict[str, Any],
    review: dict[str, Any],
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    documents = {
        "profile.json": profile,
        "contract.json": contract,
        "review.json": review,
    }
    for filename in TRACKED_FILENAMES:
        _write_json(evidence_dir / filename, documents[filename])
    manifest = {
        "schema_version": "1.0",
        "files": [
            {
                "path": filename,
                "sha256": sha256(evidence_dir / filename),
                "bytes": (evidence_dir / filename).stat().st_size,
            }
            for filename in TRACKED_FILENAMES
        ],
    }
    _write_json(evidence_dir / "manifest.json", manifest)


def _validate_upstream(
    plan: dict[str, Any],
    root: Path,
    validator: Callable[..., dict[str, Any]] | None,
) -> None:
    if validator is None:
        from dsdm_phase1.ala_galah_pilot import (
            validate_evidence_package as validator,
        )

    source = plan["source"]["goal015"]
    result = validator(
        _resolved(root, source["evidence_directory"]),
        _load_json(_resolved(root, source["plan_path"])),
        raw_dir=_resolved(root, source["raw_directory"]),
    )
    _require(
        isinstance(result, dict)
        and result.get("readiness")
        == source["required_raw_backed_readiness"],
        "Goal 015 raw-backed route gate is not usable",
    )


def _load_evidence(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    expected = {*TRACKED_FILENAMES, "manifest.json"}
    _require(evidence_dir.is_dir(), "evidence directory is missing")
    entries = list(evidence_dir.iterdir())
    _require(
        {path.name for path in entries} == expected,
        "tracked evidence footprint drifted",
    )
    _require(
        all(path.is_file() and not path.is_symlink() for path in entries),
        "tracked evidence contains unsafe entry",
    )
    manifest = _load_json(evidence_dir / "manifest.json")
    _exact_keys(manifest, {"schema_version", "files"}, "manifest")
    _require(
        manifest["schema_version"] == "1.0"
        and isinstance(manifest["files"], list)
        and len(manifest["files"]) == len(TRACKED_FILENAMES),
        "manifest identity drifted",
    )
    for entry, filename in zip(manifest["files"], TRACKED_FILENAMES):
        _exact_keys(entry, {"path", "sha256", "bytes"}, "manifest entry")
        path = evidence_dir / filename
        _require(
            entry["path"] == filename
            and SHA256_RE.fullmatch(entry["sha256"]) is not None
            and entry["sha256"] == sha256(path)
            and entry["bytes"] == path.stat().st_size,
            "manifest binding drifted",
        )
    documents = {name: _load_json(evidence_dir / name) for name in TRACKED_FILENAMES}
    for document in documents.values():
        _scan_tracked(document)
    return documents


def _validate_tracked(
    documents: dict[str, dict[str, Any]],
    plan: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    profile = documents["profile.json"]
    contract_evidence = documents["contract.json"]
    review = documents["review.json"]
    _exact_keys(
        profile,
        {
            "schema_version",
            "source_type",
            "source_artifact",
            "csv_semantics",
            "field_population",
            "provider_identity",
            "temporal_checks",
            "spatial_checks",
            "quality_assertions",
            "duplicate_diagnostics",
        },
        "profile",
    )
    _require(
        profile["schema_version"] == "1.0"
        and profile["source_type"]
        == "goal016_offline_csv_aggregate_profile",
        "profile identity drifted",
    )
    source = profile["source_artifact"]
    binding = plan["source"]["occurrence_csv"]
    _require(
        source
        == {
            "path": binding["path"],
            "sha256": binding["sha256"],
            "bytes": binding["bytes"],
            "rows": RAW_ROWS,
            "columns": RAW_COLUMNS,
            "unique_headers": RAW_COLUMNS,
        },
        "profile source binding drifted",
    )
    _require(
        profile["csv_semantics"]
        == {
            "population_measure": "nonblank_and_blank_serialized_csv_cells",
            "original_provider_or_pandas_types_recoverable": False,
            "original_null_distinguishable_from_empty_string": False,
        },
        "CSV semantics drifted",
    )
    expected_population = []
    for field in plan["calibration"]["returned_core_fields"]:
        nonblank, distinct, valid = EXPECTED_FIELD_STATS[field]
        expected_population.append(
            {
                "field": field,
                "present": True,
                "nonblank_count": nonblank,
                "blank_count": RAW_ROWS - nonblank,
                "distinct_nonblank_count": distinct,
                "semantic_type": _semantic_type(field),
                "format_valid_nonblank_count": valid,
            }
        )
    _require(
        profile["field_population"] == expected_population,
        "field-population aggregate evidence drifted",
    )
    identity = profile["provider_identity"]
    _exact_keys(
        identity,
        {
            "candidates",
            "selected_field",
            "complete_unique_provider_identity",
            "content_fallback_used",
        },
        "provider identity",
    )
    expected_candidates = [
        {
            "field": "recordID",
            "present": False,
            "nonblank_count": 0,
            "blank_count": RAW_ROWS,
            "distinct_nonblank_count": 0,
            "semantic_type": "text",
            "format_valid_nonblank_count": 0,
        },
        expected_population[0],
    ]
    _require(
        identity["candidates"] == expected_candidates
        and identity["selected_field"] is None
        and identity["complete_unique_provider_identity"] is False
        and identity["content_fallback_used"] is False,
        "tracked profile falsely resolved provider identity",
    )
    qa = profile["quality_assertions"]
    _require(
        qa
        == {
            "expanded_field_count": 124,
            "expanded_cell_count": 2108,
            "boolean_compatible_cell_count": 2108,
            "always_false_field_count": 114,
            "always_true_field_count": 8,
            "mixed_field_count": 2,
            "minimum_true_flags_per_row": 9,
            "maximum_true_flags_per_row": 9,
            "unknown_extra_field_count": 0,
        },
        "QA aggregate evidence drifted",
    )
    _require(
        profile["temporal_checks"]
        == {
            "event_date_parseable_nonblank_count": 17,
            "date_year_consistent_count": 17,
        }
        and profile["spatial_checks"]
        == {
            "valid_coordinate_pair_count": 17,
            "reported_uncertainty_over_1000_m_count": 0,
            "decimal_place_precision_inference_performed": False,
        },
        "temporal or spatial aggregate evidence drifted",
    )
    _require(
        profile["duplicate_diagnostics"]
        == {
            "full_row_distinct_count": 17,
            "full_row_duplicate_count": 0,
            "content_fingerprint_component_count": 5,
            "complete_content_fingerprint_count": 17,
            "distinct_complete_content_fingerprint_count": 17,
            "content_fingerprint_used_as_identity": False,
        },
        "duplicate diagnostics drifted",
    )
    expected_contract = _contract_evidence(plan, contract, profile)
    _require(
        contract_evidence == expected_contract,
        "calibrated contract evidence drifted",
    )
    expected_review = _review(plan, profile)
    _require(review == expected_review, "Goal 016 review drifted")
    _require(
        review["readiness"] == TRACKED_ONLY,
        "tracked evidence claimed a raw-backed decision",
    )


def build_evidence(
    plan_path: Path,
    evidence_dir: Path,
    *,
    raw_file: Path | None = None,
    upstream_validator: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build deterministic tracked evidence from the exact ignored raw CSV."""

    plan_path = Path(plan_path)
    root = plan_path.parent.parent
    plan = _load_json(plan_path)
    contract = validate_plan(plan, root)
    _validate_upstream(plan, root, upstream_validator)
    raw_path = raw_file or _resolved(root, plan["source"]["occurrence_csv"]["path"])
    fields, rows = _read_bound_csv(raw_path, plan["source"]["occurrence_csv"])
    profile = _profile(plan, fields, rows)
    contract_evidence = _contract_evidence(plan, contract, profile)
    review = _review(plan, profile)
    _write_evidence(Path(evidence_dir), profile, contract_evidence, review)
    return validate_evidence_package(
        plan_path,
        evidence_dir,
        raw_file=raw_path,
        upstream_validator=upstream_validator,
    )


def validate_evidence_package(
    plan_path: Path,
    evidence_dir: Path,
    *,
    raw_file: Path | None = None,
    upstream_validator: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate tracked evidence and optionally reconstruct it from exact raw."""

    plan_path = Path(plan_path)
    root = plan_path.parent.parent
    plan = _load_json(plan_path)
    contract = validate_plan(plan, root)
    documents = _load_evidence(Path(evidence_dir))
    _validate_tracked(documents, plan, contract)
    if raw_file is None:
        return {"readiness": TRACKED_ONLY, "raw_replay_required": True}
    _validate_upstream(plan, root, upstream_validator)
    fields, rows = _read_bound_csv(
        Path(raw_file), plan["source"]["occurrence_csv"]
    )
    profile = _profile(plan, fields, rows)
    expected = {
        "profile.json": profile,
        "contract.json": _contract_evidence(plan, contract, profile),
        "review.json": _review(plan, profile),
    }
    _require(documents == expected, "tracked evidence differs from raw replay")
    return {
        "readiness": RAW_DECISION,
        "count_census_ready": True,
        "full_row_acquisition_ready": False,
        "provider_identity_resolved": False,
        "rows_profiled": len(rows),
        "columns_profiled": len(fields),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate Goal 016.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "validate"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--plan", type=Path, required=True)
        command_parser.add_argument("--evidence-dir", type=Path, required=True)
        command_parser.add_argument("--raw-file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_evidence(
                args.plan, args.evidence_dir, raw_file=args.raw_file
            )
        else:
            result = validate_evidence_package(
                args.plan, args.evidence_dir, raw_file=args.raw_file
            )
    except ALAFieldContractError as error:
        print(
            json.dumps({"outcome": "stopped", "reason": str(error)}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
