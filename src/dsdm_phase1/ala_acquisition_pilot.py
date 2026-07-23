"""Bounded direct-ALA acquisition pilot with raw-backed sanitized evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .ala_query_scope import (
    MACROPUS_SYNONYM,
    MACROPUS_SYNONYM_NAME,
    OCCURRENCE_SEARCH_URL,
    PARENT_CONCEPTS,
    REQUIRED_RECORD_FIELDS,
    SCOPE_FQ,
    VOMBATUS_CHILDREN,
    validate_request_profile,
)


class PilotValidationError(ValueError):
    """Raised when the bounded row pilot or its evidence fails closed."""


EXPECTED_PROFILE_SHA256 = (
    "60082efbebde02558ce3f0ef45b0676f21332e11b16796207e91eee19b18155f"
)
EXPECTED_CONFIG_KEYS = {
    "schema_version",
    "plan_id",
    "profile_id",
    "profile_sha256",
    "endpoint",
    "method",
    "page_size",
    "parent_starts",
    "fallback_start",
    "sort",
    "direction",
    "facet",
    "disable_all_quality_filters",
    "future_fl",
    "max_record_requests",
    "max_returned_rows",
    "polite_delay_seconds",
    "max_transient_retries",
    "raw_relative_path",
    "evidence_relative_path",
}
REQUEST_ENTRY_KEYS = {
    "ordinal",
    "key",
    "branch",
    "focal_species_id",
    "concept_id",
    "endpoint",
    "method",
    "ordered_parameters",
    "canonical_url",
    "http_status",
    "retrieved_at_utc",
    "retrieval_timestamp_basis",
    "attempt_count",
    "retry_events",
    "returned_rows",
    "raw_file",
    "raw_sha256",
    "raw_bytes",
    "response_controls",
    "query_binding",
    "field_stats",
    "unrequested_field_stats",
    "validation",
}
REQUEST_ROOT_KEYS = {
    "schema_version",
    "goal_id",
    "profile_id",
    "plan_id",
    "collection_started_at_utc",
    "collection_completed_at_utc",
    "endpoint",
    "method",
    "planned_record_requests",
    "successful_record_requests",
    "http_attempts",
    "max_returned_rows",
    "returned_rows",
    "records_retained_in_tracked_evidence",
    "coordinates_retained_in_tracked_evidence",
    "requests",
}
FIELD_STAT_KEYS = {
    "presence_count",
    "non_null_count",
    "null_count",
    "missing_count",
    "types",
}
RESPONSE_CONTROL_KEYS = {
    "page_size",
    "start_index",
    "total_records",
    "expected_returned_rows",
    "returned_rows_match_expected",
    "sort",
    "direction",
    "occurrence_ids_strictly_ascending",
    "facet_result_count",
}
QUERY_BINDING_KEYS = {
    "echoes_checked",
    "matched_echoes",
    "q_values_per_echo",
    "fq_values_per_echo",
    "quality_values_per_echo",
}
LEGACY_REQUEST_ENTRY_KEYS = REQUEST_ENTRY_KEYS - {"query_binding"}
LEGACY_RESPONSE_CONTROL_KEYS = {
    "page_size",
    "start_index",
    "sort",
    "direction",
    "facet_result_count",
}
ROW_VALIDATION_KEYS = {
    "occurrence_id_non_null_count",
    "occurrence_id_duplicate_count",
    "critical_identity_ready_count",
    "date_scope_violation_count",
    "event_date_unparseable_count",
    "extra_field_count",
}
REVIEW_KEYS = {
    "schema_version",
    "goal_id",
    "profile_id",
    "plan_id",
    "reviewed_at_utc",
    "successful_record_requests",
    "http_attempts",
    "returned_rows",
    "max_returned_rows",
    "stable_pagination",
    "search_route_limitation",
    "response_projection",
    "pagination",
    "field_behavior",
    "fallback_behavior",
    "deduplication",
    "assertions",
    "unresolved_assertions",
    "observations",
    "inference",
    "readiness",
    "not_ready_for",
}
READINESS = "pilot_pass_ready_for_bounded_full_acquisition_design"
TRACKED_ONLY_READINESS = "tracked_package_structurally_valid_raw_replay_required"
INTERPRETATION_LIMITS = [
    "complete_occurrence_acquisition",
    "snapshot_consistent_pagination",
    "camera_readiness",
    "normalization_readiness",
    "ecological_totals_or_full_query_coverage",
    "complete_descendant_or_synonym_coverage",
]
SEARCH_ROUTE_LIMITATION = {
    "maximum_accessible_results": 5000,
    "snapshot_consistent_pagination_documented": False,
    "implication": (
        "Species queries above 5000 results require a later supported "
        "download/export design; this search pilot cannot establish complete "
        "acquisition."
    ),
}
OBSERVATIONS = (
    "All counts are returned rows from capped pilot pages, not ecological "
    "totals or complete query coverage."
)
INFERENCE = (
    "The bounded pilot validates the direct row request, field, provenance, "
    "sampled order/overlap, and deduplication contract. It does not prove "
    "snapshot consistency or complete descendant coverage. Species queries "
    "above 5000 results require a later supported download/export design."
)
EVIDENCE_FILENAMES = ("requests.json", "review.json")
ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
RAW_SERVER_ADDED_FIELDS = {"otherProperties"}


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotValidationError(f"cannot load JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PilotValidationError(f"JSON root must be an object: {path}")
    return value


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise PilotValidationError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not ISO_Z_RE.fullmatch(value):
        raise PilotValidationError("timestamp must use canonical ISO-8601 Z form")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise PilotValidationError("timestamp is invalid") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_pilot_config(
    config: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    """Validate the immutable Goal 013 plan before constructing any URL."""

    try:
        validate_request_profile(profile)
    except ValueError as exc:
        raise PilotValidationError("Goal 012 request profile is invalid") from exc
    if not isinstance(config, dict) or set(config) != EXPECTED_CONFIG_KEYS:
        raise PilotValidationError("pilot config root shape drifted")
    exact = {
        "schema_version": "1.0",
        "plan_id": "goal013-ala-row-pilot-2026-07-23",
        "profile_id": profile["profile_id"],
        "profile_sha256": EXPECTED_PROFILE_SHA256,
        "endpoint": OCCURRENCE_SEARCH_URL,
        "method": "GET",
        "page_size": 25,
        "parent_starts": [0, 25],
        "fallback_start": 0,
        "sort": "occurrenceID",
        "direction": "asc",
        "facet": False,
        "disable_all_quality_filters": True,
        "future_fl": REQUIRED_RECORD_FIELDS,
        "max_record_requests": 23,
        "max_returned_rows": 575,
        "polite_delay_seconds": 0.25,
        "max_transient_retries": 1,
        "raw_relative_path": "data/raw/ala/goal013-pilot/2026-07-23",
        "evidence_relative_path": (
            "evidence/ala_acquisition_pilot/2026-07-23"
        ),
    }
    if config != exact:
        raise PilotValidationError("pilot config drifted from the frozen bounded plan")
    if profile["future_fl"] != REQUIRED_RECORD_FIELDS:
        raise PilotValidationError("pilot field list drifted from Goal 012")
    planned_requests = len(PARENT_CONCEPTS) * len(config["parent_starts"]) + 5
    planned_rows = planned_requests * config["page_size"]
    if (
        planned_requests != config["max_record_requests"]
        or planned_rows != config["max_returned_rows"]
        or planned_requests != 23
        or planned_rows != 575
    ):
        raise PilotValidationError("pilot request or row ceiling is not exact")
    return {
        "planned_request_count": planned_requests,
        "planned_row_ceiling": planned_rows,
    }


def _request_parameters(
    query: str, start: int, config: dict[str, Any]
) -> list[list[str]]:
    return [
        ["q", query],
        *[["fq", value] for value in SCOPE_FQ],
        ["fl", ",".join(REQUIRED_RECORD_FIELDS)],
        ["pageSize", str(config["page_size"])],
        ["start", str(start)],
        ["facet", "false"],
        ["disableAllQualityFilters", "true"],
        ["sort", config["sort"]],
        ["dir", config["direction"]],
    ]


def _request_spec(
    ordinal: int,
    key: str,
    branch: str,
    focal_species_id: str,
    concept_id: str,
    query: str,
    start: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    parameters = _request_parameters(query, start, config)
    slug = key.replace("__", "-").replace("_", "-")
    raw_file = f"{ordinal:03d}-{slug}.json"
    return {
        "ordinal": ordinal,
        "key": key,
        "branch": branch,
        "focal_species_id": focal_species_id,
        "concept_id": concept_id,
        "query": query,
        "page_size": config["page_size"],
        "start": start,
        "sort": config["sort"],
        "direction": config["direction"],
        "ordered_parameters": parameters,
        "canonical_url": config["endpoint"]
        + "?"
        + urllib.parse.urlencode([tuple(item) for item in parameters]),
        "raw_file": raw_file,
    }


def build_request_plan(
    profile: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return the exact 18-parent plus 5-fallback request matrix."""

    validate_pilot_config(config, profile)
    specs: list[dict[str, Any]] = []
    ordinal = 1
    for species_id, concept_id in PARENT_CONCEPTS.items():
        for start in config["parent_starts"]:
            specs.append(
                _request_spec(
                    ordinal,
                    f"parent__{species_id}__start_{start:03d}",
                    "parent",
                    species_id,
                    concept_id,
                    f'taxonConceptID:"{concept_id}"',
                    start,
                    config,
                )
            )
            ordinal += 1
    fallback_rows = [
        (
            "fallback__macropus_synonym_id__start_000",
            "fallback_macropus_synonym_id",
            "macropus_giganteus",
            MACROPUS_SYNONYM,
            f'taxonConceptID:"{MACROPUS_SYNONYM}"',
        ),
        (
            "fallback__macropus_synonym_name__start_000",
            "fallback_macropus_synonym_name",
            "macropus_giganteus",
            MACROPUS_SYNONYM,
            f'taxa:"{MACROPUS_SYNONYM_NAME}"',
        ),
        *[
            (
                f"fallback__{child_id}__start_000",
                "fallback_vombatus_child",
                "vombatus_ursinus",
                concept_id,
                f'taxonConceptID:"{concept_id}"',
            )
            for child_id, concept_id in VOMBATUS_CHILDREN.items()
        ],
    ]
    for key, branch, focal_species_id, concept_id, query in fallback_rows:
        specs.append(
            _request_spec(
                ordinal,
                key,
                branch,
                focal_species_id,
                concept_id,
                query,
                config["fallback_start"],
                config,
            )
        )
        ordinal += 1
    if len(specs) != 23 or sum(item["page_size"] for item in specs) != 575:
        raise PilotValidationError("constructed request plan exceeds hard ceiling")
    if len({item["key"] for item in specs}) != 23:
        raise PilotValidationError("constructed request keys are not unique")
    return specs


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise PilotValidationError("record field contains unsupported JSON type")


def _non_blank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _date_scope(row: dict[str, Any]) -> tuple[int, int]:
    violations = 0
    unparseable = 0
    year = row.get("year")
    year_value: int | None = None
    if year is not None:
        if isinstance(year, bool):
            violations += 1
        elif isinstance(year, int):
            year_value = year
            violations += int(not 2001 <= year <= 2025)
        elif isinstance(year, str) and year.isdigit():
            year_value = int(year)
            violations += int(not 2001 <= year_value <= 2025)
        else:
            violations += 1
    event_date = row.get("eventDate")
    if event_date is not None:
        event_year: int | None = None
        if isinstance(event_date, bool):
            unparseable += 1
            violations += 1
        elif isinstance(event_date, int):
            try:
                event_year = datetime.fromtimestamp(
                    event_date / 1000, tz=timezone.utc
                ).year
            except (OverflowError, OSError, ValueError):
                unparseable += 1
                violations += 1
        elif isinstance(event_date, str) and re.match(r"^\d{4}", event_date):
            event_year = int(event_date[:4])
        else:
            unparseable += 1
            violations += 1
        if event_year is not None and not 2001 <= event_year <= 2025:
            violations += 1
        if (
            event_year is not None
            and year_value is not None
            and event_year != year_value
        ):
            violations += 1
    return violations, unparseable


def _validate_query_binding_echo(
    value: Any, spec: dict[str, Any], label: str
) -> None:
    if not isinstance(value, str) or not value.startswith("?"):
        raise PilotValidationError(f"{label} query binding echo is missing")
    try:
        pairs = urllib.parse.parse_qsl(
            value[1:], keep_blank_values=True, strict_parsing=True
        )
    except ValueError as exc:
        raise PilotValidationError(
            f"{label} query binding echo is malformed"
        ) from exc
    grouped: dict[str, list[str]] = {}
    for key, item in pairs:
        grouped.setdefault(key, []).append(item)
    if (
        grouped.get("q") != [spec["query"]]
        or grouped.get("fq") != SCOPE_FQ
        or grouped.get("disableAllQualityFilters") != ["true"]
    ):
        raise PilotValidationError(
            f"{label} query binding drifted from the planned q/fq/quality scope"
        )


def _analyze_response(
    spec: dict[str, Any], body: bytes, http_status: int
) -> dict[str, Any]:
    if http_status != 200:
        raise PilotValidationError("record response HTTP status is not 200")
    try:
        response = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PilotValidationError("record response is not valid JSON") from exc
    if not isinstance(response, dict):
        raise PilotValidationError("record response root is not an object")
    if response.get("status") != "OK":
        raise PilotValidationError("record response status is not OK")
    if response.get("pageSize") != spec["page_size"]:
        raise PilotValidationError("record response pageSize drifted")
    if response.get("startIndex") != spec["start"]:
        raise PilotValidationError("record response startIndex drifted")
    if response.get("sort") != spec["sort"] or response.get("dir") != spec["direction"]:
        raise PilotValidationError(
            "explicit occurrenceID pagination order was not accepted and echoed"
        )
    _validate_query_binding_echo(response.get("query"), spec, "query")
    _validate_query_binding_echo(
        response.get("urlParameters"), spec, "urlParameters"
    )
    facets = response.get("facetResults")
    if not isinstance(facets, list) or facets:
        raise PilotValidationError("facet=false did not yield an empty facet payload")
    rows = response.get("occurrences")
    if not isinstance(rows, list):
        raise PilotValidationError("record response occurrences is not a list")
    if len(rows) > spec["page_size"]:
        raise PilotValidationError("record response exceeded the planned page ceiling")
    total_records = response.get("totalRecords")
    if (
        not isinstance(total_records, int)
        or isinstance(total_records, bool)
        or total_records < 0
    ):
        raise PilotValidationError("record response totalRecords is malformed")
    expected_returned_rows = min(
        spec["page_size"], max(total_records - spec["start"], 0)
    )
    if len(rows) != expected_returned_rows:
        raise PilotValidationError(
            "returned row count does not match totalRecords pagination"
        )

    field_counters = {
        field: {
            "presence_count": 0,
            "non_null_count": 0,
            "null_count": 0,
            "missing_count": 0,
            "types": set(),
        }
        for field in REQUIRED_RECORD_FIELDS
    }
    occurrence_ids: list[str] = []
    coordinate_values: list[int | float | str] = []
    unrequested_stats = {
        "otherProperties": {
            "presence_count": 0,
            "non_null_count": 0,
            "types": set(),
        }
    }
    identity_ready = 0
    date_violations = 0
    event_date_unparseable = 0
    extra_fields = 0
    for row in rows:
        if not isinstance(row, dict):
            raise PilotValidationError("occurrence row is not an object")
        extras = set(row) - set(REQUIRED_RECORD_FIELDS)
        forbidden_extras = extras - RAW_SERVER_ADDED_FIELDS
        extra_fields += len(forbidden_extras)
        if forbidden_extras:
            raise PilotValidationError("occurrence row contains fields outside frozen fl")
        if "otherProperties" in row:
            other = row["otherProperties"]
            stats = unrequested_stats["otherProperties"]
            stats["presence_count"] += 1
            if other is not None:
                stats["non_null_count"] += 1
                value_type = _value_type(other)
                if value_type != "object":
                    raise PilotValidationError(
                        "server-added otherProperties is not an object"
                    )
                stats["types"].add(value_type)
        projected = {
            field: row[field]
            for field in REQUIRED_RECORD_FIELDS
            if field in row
        }
        for field in REQUIRED_RECORD_FIELDS:
            stats = field_counters[field]
            if field not in projected:
                stats["missing_count"] += 1
                continue
            stats["presence_count"] += 1
            value = projected[field]
            if value is None:
                stats["null_count"] += 1
            else:
                stats["non_null_count"] += 1
                stats["types"].add(_value_type(value))
        occurrence_id = projected.get("occurrenceID")
        if not _non_blank_string(occurrence_id):
            raise PilotValidationError("occurrenceID is null, blank, or malformed")
        occurrence_ids.append(occurrence_id)
        for field in ("decimalLatitude", "decimalLongitude"):
            value = projected.get(field)
            if value is not None:
                coordinate_values.append(value)
        accepted_name = projected.get("acceptedNameUsage") or projected.get(
            "scientificName"
        )
        accepted_id = projected.get("acceptedNameUsageID") or projected.get(
            "taxonConceptID"
        )
        if not (
            _non_blank_string(projected.get("scientificName"))
            and _non_blank_string(projected.get("taxonConceptID"))
            and _non_blank_string(accepted_name)
            and _non_blank_string(accepted_id)
            and _non_blank_string(projected.get("taxonRank"))
        ):
            raise PilotValidationError(
                "matched/accepted identity or rank is null or malformed"
            )
        identity_ready += 1
        row_violations, row_unparseable = _date_scope(projected)
        date_violations += row_violations
        event_date_unparseable += row_unparseable
    duplicates = len(occurrence_ids) - len(set(occurrence_ids))
    if duplicates:
        raise PilotValidationError("duplicate occurrenceID creates page ambiguity")
    strictly_ascending = all(
        left < right
        for left, right in zip(occurrence_ids, occurrence_ids[1:])
    )
    if not strictly_ascending:
        raise PilotValidationError(
            "occurrenceIDs are not strictly ascending under the echoed order"
        )
    if date_violations:
        raise PilotValidationError("record date falls outside the frozen scope")
    field_stats = {
        field: {
            **{key: value for key, value in stats.items() if key != "types"},
            "types": sorted(stats["types"]),
        }
        for field, stats in field_counters.items()
    }
    return {
        "returned_rows": len(rows),
        "response_controls": {
            "page_size": response["pageSize"],
            "start_index": response["startIndex"],
            "total_records": total_records,
            "expected_returned_rows": expected_returned_rows,
            "returned_rows_match_expected": True,
            "sort": response["sort"],
            "direction": response["dir"],
            "occurrence_ids_strictly_ascending": True,
            "facet_result_count": len(facets),
        },
        "query_binding": {
            "echoes_checked": 2,
            "matched_echoes": 2,
            "q_values_per_echo": 1,
            "fq_values_per_echo": 2,
            "quality_values_per_echo": 1,
        },
        "field_stats": field_stats,
        "unrequested_field_stats": {
            field: {
                **{
                    key: value
                    for key, value in stats.items()
                    if key != "types"
                },
                "types": sorted(stats["types"]),
            }
            for field, stats in unrequested_stats.items()
        },
        "validation": {
            "occurrence_id_non_null_count": len(occurrence_ids),
            "occurrence_id_duplicate_count": duplicates,
            "critical_identity_ready_count": identity_ready,
            "date_scope_violation_count": date_violations,
            "event_date_unparseable_count": event_date_unparseable,
            "extra_field_count": extra_fields,
        },
        "_occurrence_ids": occurrence_ids,
        "_coordinate_values": coordinate_values,
    }


def _aggregate_fields(entries: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in REQUIRED_RECORD_FIELDS:
        types: set[str] = set()
        totals = {
            "presence_count": 0,
            "non_null_count": 0,
            "null_count": 0,
            "missing_count": 0,
        }
        for entry in entries:
            stats = entry["field_stats"][field]
            for key in totals:
                totals[key] += stats[key]
            types.update(stats["types"])
        result[field] = {**totals, "types": sorted(types)}
    return result


def _aggregate_unrequested_fields(
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    types: set[str] = set()
    presence_count = 0
    non_null_count = 0
    for entry in entries:
        stats = entry["unrequested_field_stats"]["otherProperties"]
        presence_count += stats["presence_count"]
        non_null_count += stats["non_null_count"]
        types.update(stats["types"])
    return {
        "otherProperties": {
            "presence_count": presence_count,
            "non_null_count": non_null_count,
            "types": sorted(types),
        }
    }


def _build_review(
    entries: list[dict[str, Any]],
    private: dict[str, list[str]],
    reviewed_at_utc: str,
    profile_id: str,
    plan_id: str,
    max_returned_rows: int,
) -> dict[str, Any]:
    by_key = {entry["key"]: entry for entry in entries}
    pagination_pairs = []
    for species_id in PARENT_CONCEPTS:
        first_key = f"parent__{species_id}__start_000"
        second_key = f"parent__{species_id}__start_025"
        first_ids = private[first_key]
        second_ids = private[second_key]
        overlap = set(first_ids) & set(second_ids)
        first_total = by_key[first_key]["response_controls"]["total_records"]
        second_total = by_key[second_key]["response_controls"]["total_records"]
        totals_equal = first_total == second_total
        boundary_ascending = (
            not first_ids
            or not second_ids
            or first_ids[-1] < second_ids[0]
        )
        pagination_pairs.append(
            {
                "focal_species_id": species_id,
                "first_page_rows": by_key[first_key]["returned_rows"],
                "second_page_rows": by_key[second_key]["returned_rows"],
                "total_records_equal": totals_equal,
                "overlap_count": len(overlap),
                "boundary_strictly_ascending": boundary_ascending,
            }
        )
        if not totals_equal:
            raise PilotValidationError(
                "parent page-pair totalRecords disagreement"
            )
        if overlap:
            raise PilotValidationError(
                "occurrenceID overlap creates pagination ambiguity"
            )
        if not boundary_ascending:
            raise PilotValidationError(
                "parent page boundary is not strictly ascending"
            )
    parent_totals = {
        species_id: (
            by_key[f"parent__{species_id}__start_000"]["returned_rows"]
            + by_key[f"parent__{species_id}__start_025"]["returned_rows"]
        )
        for species_id in PARENT_CONCEPTS
    }
    if any(total <= 0 for total in parent_totals.values()):
        raise PilotValidationError("a focal parent returned no bounded pilot rows")

    mac_id_key = "fallback__macropus_synonym_id__start_000"
    mac_name_key = "fallback__macropus_synonym_name__start_000"
    mac_parent_ids = {
        *private["parent__macropus_giganteus__start_000"],
        *private["parent__macropus_giganteus__start_025"],
    }
    mac_id_rows = by_key[mac_id_key]["returned_rows"]
    mac_name_rows = by_key[mac_name_key]["returned_rows"]
    if mac_name_rows <= 0:
        raise PilotValidationError(
            "Macropus normalized synonym-name fallback returned no pilot rows"
        )
    vombatus_parent_ids = {
        *private["parent__vombatus_ursinus__start_000"],
        *private["parent__vombatus_ursinus__start_025"],
    }
    vombatus_children = {}
    for child_id in VOMBATUS_CHILDREN:
        key = f"fallback__{child_id}__start_000"
        vombatus_children[child_id] = {
            "returned_rows": by_key[key]["returned_rows"],
            "parent_sample_overlap_count": len(
                set(private[key]) & vombatus_parent_ids
            ),
        }
    for child_id in (
        "vombatus_ursinus_tasmaniensis",
        "vombatus_ursinus_ursinus",
    ):
        if vombatus_children[child_id]["returned_rows"] <= 0:
            raise PilotValidationError(
                "a positive Goal 012 Vombatus child branch returned no pilot rows"
            )

    all_occurrence_ids = [
        occurrence_id
        for entry in entries
        for occurrence_id in private[entry["key"]]
    ]
    unique_count = len(set(all_occurrence_ids))
    duplicate_references = len(all_occurrence_ids) - unique_count
    unresolved = []
    if mac_id_rows == 0:
        mac_status = "unresolved_id_zero_name_path_positive"
        unresolved.append(
            "macropus_synonym_concept_id_returned_zero_rows_in_bounded_pilot"
        )
    else:
        mac_status = "established_id_and_name_positive_in_bounded_pilot"
    hirsutus_rows = vombatus_children["vombatus_ursinus_hirsutus"][
        "returned_rows"
    ]
    if hirsutus_rows == 0:
        hirsutus_status = "unresolved_scoped_zero"
        unresolved.append(
            "vombatus_ursinus_hirsutus_returned_zero_rows_in_bounded_pilot"
        )
    else:
        hirsutus_status = "established_positive_in_bounded_pilot"

    total_rows = sum(entry["returned_rows"] for entry in entries)
    total_attempts = sum(entry["attempt_count"] for entry in entries)
    nonempty_pages = sum(entry["returned_rows"] > 0 for entry in entries)
    return {
        "schema_version": "1.0",
        "goal_id": "013",
        "profile_id": profile_id,
        "plan_id": plan_id,
        "reviewed_at_utc": reviewed_at_utc,
        "successful_record_requests": len(entries),
        "http_attempts": total_attempts,
        "returned_rows": total_rows,
        "max_returned_rows": max_returned_rows,
        "stable_pagination": {
            "field": "occurrenceID",
            "direction": "asc",
            "explicit_order_accepted_and_echoed_requests": len(entries),
            "expected_length_requests": len(entries),
            "nonempty_page_count": nonempty_pages,
            "strictly_ascending_nonempty_pages": nonempty_pages,
            "sampled_parent_page_overlap_count": sum(
                pair["overlap_count"] for pair in pagination_pairs
            ),
            "equal_total_parent_pairs": sum(
                pair["total_records_equal"] for pair in pagination_pairs
            ),
            "ascending_boundary_parent_pairs": sum(
                pair["boundary_strictly_ascending"]
                for pair in pagination_pairs
            ),
            "scope": (
                "bounded order and overlap behaviour only; not "
                "snapshot-consistent pagination"
            ),
        },
        "search_route_limitation": SEARCH_ROUTE_LIMITATION,
        "response_projection": {
            "frozen_requested_field_count": len(REQUIRED_RECORD_FIELDS),
            "server_added_raw_allowlist": ["otherProperties"],
            "server_added_field_stats": _aggregate_unrequested_fields(entries),
            "handling": (
                "otherProperties values remain quarantined in ignored raw "
                "responses and are dropped from the canonical projection"
            ),
        },
        "pagination": {
            "pair_count": len(pagination_pairs),
            "pairs": pagination_pairs,
        },
        "field_behavior": _aggregate_fields(entries),
        "fallback_behavior": {
            "macropus_synonym": {
                "concept_id_rows": mac_id_rows,
                "normalized_name_rows": mac_name_rows,
                "concept_id_parent_sample_overlap_count": len(
                    set(private[mac_id_key]) & mac_parent_ids
                ),
                "normalized_name_parent_sample_overlap_count": len(
                    set(private[mac_name_key]) & mac_parent_ids
                ),
            },
            "vombatus_children": vombatus_children,
        },
        "deduplication": {
            "key": "occurrenceID",
            "rows_before_deduplication": len(all_occurrence_ids),
            "unique_rows_after_deduplication": unique_count,
            "duplicate_references_across_query_branches": duplicate_references,
            "duplicates_within_page_or_parent_pagination": 0,
        },
        "assertions": {
            "parent_expansion_runtime_coverage": (
                "established_for_bounded_pilot_only"
            ),
            "macropus_giganteus_tasmaniensis_synonym_id_coverage": mac_status,
            "vombatus_ursinus_hirsutus_scope_coverage": hirsutus_status,
            "occurrenceID_deduplication": "established_for_bounded_pilot_only",
        },
        "unresolved_assertions": unresolved,
        "observations": OBSERVATIONS,
        "inference": INFERENCE,
        "readiness": READINESS,
        "not_ready_for": INTERPRETATION_LIMITS,
    }


def _default_fetcher(
    url: str, headers: dict[str, str]
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(response.status), response.read()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def collect_pilot(
    profile_path: str | Path,
    config_path: str | Path,
    raw_dir: str | Path,
    evidence_dir: str | Path,
    *,
    fetcher: Callable[[str, dict[str, str]], tuple[int, bytes]] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Execute the exact pilot once and write raw plus sanitized evidence."""

    profile_path = Path(profile_path)
    config_path = Path(config_path)
    raw_dir = Path(raw_dir)
    evidence_dir = Path(evidence_dir)
    profile_bytes = profile_path.read_bytes()
    if _sha256_bytes(profile_bytes) != EXPECTED_PROFILE_SHA256:
        raise PilotValidationError("Goal 012 profile file checksum drifted")
    profile = json.loads(profile_bytes)
    config = _load_json(config_path)
    validation = validate_pilot_config(config, profile)
    plan = build_request_plan(profile, config)
    if (
        validation["planned_request_count"] > config["max_record_requests"]
        or validation["planned_row_ceiling"] > config["max_returned_rows"]
    ):
        raise PilotValidationError("hard pilot ceiling cannot be enforced")
    if evidence_dir.exists():
        raise PilotValidationError(
            "tracked pilot output already exists; refusing an ambiguous rerun"
        )
    reuse_first_raw = False
    if raw_dir.exists():
        if not raw_dir.is_dir():
            raise PilotValidationError("raw pilot path is not a directory")
        observed_raw = sorted(path.name for path in raw_dir.iterdir())
        if observed_raw != [plan[0]["raw_file"]]:
            raise PilotValidationError(
                "only the exact first raw response may be recovered"
            )
        reuse_first_raw = True
    else:
        raw_dir.mkdir(parents=True)
    fetch = fetcher or _default_fetcher
    headers = {
        "Accept": "application/json",
        "User-Agent": "dSDM-Goal013-bounded-pilot/1.0",
    }
    start_time = now_fn()
    recovered_first_time: datetime | None = None
    if reuse_first_raw:
        recovered_first_time = datetime.fromtimestamp(
            (raw_dir / plan[0]["raw_file"]).stat().st_mtime,
            tz=timezone.utc,
        )
        if recovered_first_time < start_time:
            start_time = recovered_first_time
    started = _utc_text(start_time)
    entries: list[dict[str, Any]] = []
    private: dict[str, list[str]] = {}
    returned_total = 0
    http_attempts = 0
    for index, spec in enumerate(plan):
        if len(entries) >= config["max_record_requests"]:
            raise PilotValidationError("record request cap reached before plan end")
        if returned_total + spec["page_size"] > config["max_returned_rows"]:
            raise PilotValidationError("next request could exceed row ceiling")
        raw_path = raw_dir / spec["raw_file"]
        retry_events: list[dict[str, Any]] = []
        attempt_count = 0
        if index == 0 and reuse_first_raw:
            body = raw_path.read_bytes()
            status = 200
            attempt_count = 1
            http_attempts += 1
            if recovered_first_time is None:
                raise PilotValidationError("recovered raw timestamp is unavailable")
            retrieved = _utc_text(recovered_first_time)
            retrieval_timestamp_basis = "recovered_raw_file_write_mtime"
        else:
            while True:
                attempt_count += 1
                http_attempts += 1
                try:
                    status, body = fetch(spec["canonical_url"], headers)
                    if status >= 500:
                        raise urllib.error.HTTPError(
                            spec["canonical_url"],
                            status,
                            "transient server error",
                            hdrs=None,
                            fp=None,
                        )
                    break
                except urllib.error.HTTPError as exc:
                    if (
                        500 <= exc.code <= 599
                        and len(retry_events)
                        < config["max_transient_retries"]
                    ):
                        retry_events.append(
                            {"attempt": attempt_count, "reason": "http_5xx"}
                        )
                        sleep_fn(config["polite_delay_seconds"])
                        continue
                    raise PilotValidationError(
                        f"ALA request failed with HTTP {exc.code}"
                    ) from exc
                except (urllib.error.URLError, TimeoutError, OSError) as exc:
                    if len(retry_events) < config["max_transient_retries"]:
                        retry_events.append(
                            {
                                "attempt": attempt_count,
                                "reason": "transport_error",
                            }
                        )
                        sleep_fn(config["polite_delay_seconds"])
                        continue
                    raise PilotValidationError(
                        "ALA request transport failed"
                    ) from exc
            raw_path.write_bytes(body)
            retrieved = _utc_text(now_fn())
            retrieval_timestamp_basis = "network_response_completed"
        analysis = _analyze_response(spec, body, status)
        returned_total += analysis["returned_rows"]
        if returned_total > config["max_returned_rows"]:
            raise PilotValidationError("returned rows exceeded hard ceiling")
        entry = {
            "ordinal": spec["ordinal"],
            "key": spec["key"],
            "branch": spec["branch"],
            "focal_species_id": spec["focal_species_id"],
            "concept_id": spec["concept_id"],
            "endpoint": config["endpoint"],
            "method": config["method"],
            "ordered_parameters": spec["ordered_parameters"],
            "canonical_url": spec["canonical_url"],
            "http_status": status,
            "retrieved_at_utc": retrieved,
            "retrieval_timestamp_basis": retrieval_timestamp_basis,
            "attempt_count": attempt_count,
            "retry_events": retry_events,
            "returned_rows": analysis["returned_rows"],
            "raw_file": spec["raw_file"],
            "raw_sha256": _sha256_bytes(body),
            "raw_bytes": len(body),
            "response_controls": analysis["response_controls"],
            "query_binding": analysis["query_binding"],
            "field_stats": analysis["field_stats"],
            "unrequested_field_stats": analysis[
                "unrequested_field_stats"
            ],
            "validation": analysis["validation"],
        }
        entries.append(entry)
        private[spec["key"]] = analysis["_occurrence_ids"]
        if index < len(plan) - 1:
            sleep_fn(config["polite_delay_seconds"])
    if len(entries) != 23 or returned_total > 575:
        raise PilotValidationError("post-retrieval request or row ceiling failed")

    completed = _utc_text(now_fn())
    requests = {
        "schema_version": "1.0",
        "goal_id": "013",
        "profile_id": profile["profile_id"],
        "plan_id": config["plan_id"],
        "collection_started_at_utc": started,
        "collection_completed_at_utc": completed,
        "endpoint": config["endpoint"],
        "method": config["method"],
        "planned_record_requests": len(plan),
        "successful_record_requests": len(entries),
        "http_attempts": http_attempts,
        "max_returned_rows": config["max_returned_rows"],
        "returned_rows": returned_total,
        "records_retained_in_tracked_evidence": False,
        "coordinates_retained_in_tracked_evidence": False,
        "requests": entries,
    }
    review = _build_review(
        entries,
        private,
        _utc_text(now_fn()),
        profile["profile_id"],
        config["plan_id"],
        config["max_returned_rows"],
    )
    evidence_dir.mkdir(parents=True)
    _write_json(evidence_dir / "requests.json", requests)
    _write_json(evidence_dir / "review.json", review)
    manifest = {
        "schema_version": "1.0",
        "files": [
            {
                "path": filename,
                "sha256": _sha256_bytes((evidence_dir / filename).read_bytes()),
                "bytes": (evidence_dir / filename).stat().st_size,
            }
            for filename in EVIDENCE_FILENAMES
        ],
    }
    _write_json(evidence_dir / "manifest.json", manifest)
    result = validate_evidence_package(
        evidence_dir, profile, config, raw_dir=raw_dir
    )
    if not result["raw_reconstruction"]:
        raise PilotValidationError("post-collection raw reconstruction did not run")
    return {
        "readiness": review["readiness"],
        "successful_record_requests": len(entries),
        "http_attempts": http_attempts,
        "returned_rows": returned_total,
    }


def _validate_manifest(evidence_dir: Path) -> dict[str, Any]:
    manifest = _load_json(evidence_dir / "manifest.json")
    if set(manifest) != {"schema_version", "files"}:
        raise PilotValidationError("evidence manifest shape drifted")
    if manifest["schema_version"] != "1.0":
        raise PilotValidationError("evidence manifest version drifted")
    files = manifest["files"]
    if not isinstance(files, list) or len(files) != len(EVIDENCE_FILENAMES):
        raise PilotValidationError("evidence manifest file set is incomplete")
    if [entry.get("path") for entry in files] != list(EVIDENCE_FILENAMES):
        raise PilotValidationError("evidence manifest paths drifted")
    for entry in files:
        if set(entry) != {"path", "sha256", "bytes"}:
            raise PilotValidationError("evidence manifest entry shape drifted")
        path = evidence_dir / entry["path"]
        if (
            not isinstance(entry["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
            or not isinstance(entry["bytes"], int)
            or isinstance(entry["bytes"], bool)
            or entry["bytes"] <= 0
            or not path.is_file()
            or _sha256_bytes(path.read_bytes()) != entry["sha256"]
            or path.stat().st_size != entry["bytes"]
        ):
            raise PilotValidationError("evidence checksum or byte size is invalid")
    return manifest


def _validate_field_stats(stats: Any, returned_rows: int) -> None:
    if not isinstance(stats, dict) or list(stats) != REQUIRED_RECORD_FIELDS:
        raise PilotValidationError("field statistics do not cover exact frozen fl")
    for value in stats.values():
        if not isinstance(value, dict) or set(value) != FIELD_STAT_KEYS:
            raise PilotValidationError("field statistic shape drifted")
        for key in (
            "presence_count",
            "non_null_count",
            "null_count",
            "missing_count",
        ):
            if (
                not isinstance(value[key], int)
                or isinstance(value[key], bool)
                or not 0 <= value[key] <= returned_rows
            ):
                raise PilotValidationError("field statistic count is malformed")
        if (
            value["presence_count"] + value["missing_count"] != returned_rows
            or value["non_null_count"] + value["null_count"]
            != value["presence_count"]
        ):
            raise PilotValidationError("field statistic counts are inconsistent")
        if (
            not isinstance(value["types"], list)
            or value["types"] != sorted(set(value["types"]))
            or not set(value["types"])
            <= {"boolean", "integer", "number", "string", "array", "object"}
        ):
            raise PilotValidationError("field representation types are malformed")


def _validate_unrequested_field_stats(
    stats: Any, returned_rows: int
) -> None:
    if (
        not isinstance(stats, dict)
        or set(stats) != {"otherProperties"}
        or not isinstance(stats["otherProperties"], dict)
        or set(stats["otherProperties"])
        != {"presence_count", "non_null_count", "types"}
    ):
        raise PilotValidationError(
            "server-added field statistics broadened or drifted"
        )
    other = stats["otherProperties"]
    for key in ("presence_count", "non_null_count"):
        if (
            not isinstance(other[key], int)
            or isinstance(other[key], bool)
            or not 0 <= other[key] <= returned_rows
        ):
            raise PilotValidationError(
                "server-added field count is malformed"
            )
    if other["non_null_count"] > other["presence_count"]:
        raise PilotValidationError(
            "server-added field counts are inconsistent"
        )
    expected_types = ["object"] if other["non_null_count"] else []
    if other["types"] != expected_types:
        raise PilotValidationError(
            "server-added otherProperties representation drifted"
        )


def _validate_request_evidence(
    requests: dict[str, Any],
    plan: list[dict[str, Any]],
    profile: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if set(requests) != REQUEST_ROOT_KEYS:
        raise PilotValidationError("request evidence root shape drifted")
    if (
        requests["schema_version"] != "1.0"
        or requests["goal_id"] != "013"
        or requests["profile_id"] != profile["profile_id"]
        or requests["plan_id"] != config["plan_id"]
        or requests["endpoint"] != config["endpoint"]
        or requests["method"] != "GET"
        or requests["planned_record_requests"] != 23
        or requests["successful_record_requests"] != 23
        or requests["max_returned_rows"] != 575
        or requests["records_retained_in_tracked_evidence"] is not False
        or requests["coordinates_retained_in_tracked_evidence"] is not False
    ):
        raise PilotValidationError("request evidence identity or ceiling drifted")
    started = _parse_utc(requests["collection_started_at_utc"])
    completed = _parse_utc(requests["collection_completed_at_utc"])
    if completed < started:
        raise PilotValidationError("collection chronology is impossible")
    entries = requests["requests"]
    if not isinstance(entries, list) or len(entries) != len(plan):
        raise PilotValidationError("request evidence matrix is incomplete")
    returned_total = 0
    attempt_total = 0
    previous_time = started
    for entry, spec in zip(entries, plan, strict=True):
        if not isinstance(entry, dict) or set(entry) != REQUEST_ENTRY_KEYS:
            raise PilotValidationError(
                "request evidence contains raw rows, coordinates, or shape drift"
            )
        immutable = {
            "ordinal": spec["ordinal"],
            "key": spec["key"],
            "branch": spec["branch"],
            "focal_species_id": spec["focal_species_id"],
            "concept_id": spec["concept_id"],
            "endpoint": config["endpoint"],
            "method": "GET",
            "ordered_parameters": spec["ordered_parameters"],
            "canonical_url": spec["canonical_url"],
            "raw_file": spec["raw_file"],
        }
        if any(entry[key] != value for key, value in immutable.items()):
            raise PilotValidationError("request evidence drifted from exact plan")
        if entry["http_status"] != 200:
            raise PilotValidationError("request evidence retained non-200 response")
        retrieved = _parse_utc(entry["retrieved_at_utc"])
        if retrieved < previous_time or retrieved > completed:
            raise PilotValidationError("request retrieval chronology is impossible")
        previous_time = retrieved
        expected_timestamp_bases = {"network_response_completed"}
        if spec["ordinal"] == 1:
            expected_timestamp_bases.add("recovered_raw_file_write_mtime")
        if entry["retrieval_timestamp_basis"] not in expected_timestamp_bases:
            raise PilotValidationError(
                "retrieval timestamp provenance is invalid"
            )
        if (
            not isinstance(entry["attempt_count"], int)
            or isinstance(entry["attempt_count"], bool)
            or not 1 <= entry["attempt_count"] <= 2
            or not isinstance(entry["retry_events"], list)
            or len(entry["retry_events"]) != entry["attempt_count"] - 1
        ):
            raise PilotValidationError("retry count is malformed or unbounded")
        for retry in entry["retry_events"]:
            if (
                not isinstance(retry, dict)
                or set(retry) != {"attempt", "reason"}
                or retry["attempt"] != 1
                or retry["reason"] not in {"transport_error", "http_5xx"}
            ):
                raise PilotValidationError("retry evidence is unsafe or malformed")
        if (
            not isinstance(entry["returned_rows"], int)
            or isinstance(entry["returned_rows"], bool)
            or not 0 <= entry["returned_rows"] <= 25
        ):
            raise PilotValidationError("returned-row count exceeds page ceiling")
        if (
            not isinstance(entry["raw_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["raw_sha256"])
            or not isinstance(entry["raw_bytes"], int)
            or isinstance(entry["raw_bytes"], bool)
            or entry["raw_bytes"] <= 0
        ):
            raise PilotValidationError("raw checksum or byte size is missing")
        controls = entry["response_controls"]
        if (
            not isinstance(controls, dict)
            or set(controls) != RESPONSE_CONTROL_KEYS
        ):
            raise PilotValidationError("response pagination controls drifted")
        total_records = controls["total_records"]
        if (
            not isinstance(total_records, int)
            or isinstance(total_records, bool)
            or total_records < 0
        ):
            raise PilotValidationError("sanitized totalRecords is malformed")
        expected_rows = min(25, max(total_records - spec["start"], 0))
        if controls != {
            "page_size": 25,
            "start_index": spec["start"],
            "total_records": total_records,
            "expected_returned_rows": expected_rows,
            "returned_rows_match_expected": True,
            "sort": "occurrenceID",
            "direction": "asc",
            "occurrence_ids_strictly_ascending": True,
            "facet_result_count": 0,
        } or entry["returned_rows"] != expected_rows:
            raise PilotValidationError("response pagination proof drifted")
        query_binding = entry["query_binding"]
        if (
            not isinstance(query_binding, dict)
            or set(query_binding) != QUERY_BINDING_KEYS
            or query_binding
            != {
                "echoes_checked": 2,
                "matched_echoes": 2,
                "q_values_per_echo": 1,
                "fq_values_per_echo": 2,
                "quality_values_per_echo": 1,
            }
        ):
            raise PilotValidationError("sanitized query binding proof drifted")
        _validate_field_stats(entry["field_stats"], entry["returned_rows"])
        _validate_unrequested_field_stats(
            entry["unrequested_field_stats"], entry["returned_rows"]
        )
        row_validation = entry["validation"]
        if (
            not isinstance(row_validation, dict)
            or set(row_validation) != ROW_VALIDATION_KEYS
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in row_validation.values()
            )
            or row_validation["occurrence_id_non_null_count"]
            != entry["returned_rows"]
            or row_validation["critical_identity_ready_count"]
            != entry["returned_rows"]
            or row_validation["occurrence_id_duplicate_count"] != 0
            or row_validation["date_scope_violation_count"] != 0
            or row_validation["extra_field_count"] != 0
        ):
            raise PilotValidationError("row validation evidence is inconsistent")
        returned_total += entry["returned_rows"]
        attempt_total += entry["attempt_count"]
    if (
        returned_total != requests["returned_rows"]
        or returned_total > 575
        or attempt_total != requests["http_attempts"]
        or attempt_total > 46
    ):
        raise PilotValidationError("request totals or hard ceiling are inconsistent")
    return entries


def _validate_review_shape(
    review: dict[str, Any],
    requests: dict[str, Any],
    profile: dict[str, Any],
    config: dict[str, Any],
) -> None:
    if set(review) != REVIEW_KEYS:
        raise PilotValidationError("review shape drifted or contains payload leakage")
    if (
        review["schema_version"] != "1.0"
        or review["goal_id"] != "013"
        or review["profile_id"] != profile["profile_id"]
        or review["plan_id"] != config["plan_id"]
        or review["successful_record_requests"]
        != requests["successful_record_requests"]
        or review["http_attempts"] != requests["http_attempts"]
        or review["returned_rows"] != requests["returned_rows"]
        or review["max_returned_rows"] != 575
        or review["readiness"] != READINESS
        or review["not_ready_for"] != INTERPRETATION_LIMITS
        or review["search_route_limitation"] != SEARCH_ROUTE_LIMITATION
    ):
        raise PilotValidationError("review identity, limits, or readiness drifted")
    reviewed = _parse_utc(review["reviewed_at_utc"])
    if reviewed < _parse_utc(requests["collection_completed_at_utc"]):
        raise PilotValidationError("review predates collection completion")
    entries = requests["requests"]
    by_key = {entry["key"]: entry for entry in entries}
    nonempty_pages = sum(entry["returned_rows"] > 0 for entry in entries)
    stable = review["stable_pagination"]
    if (
        not isinstance(stable, dict)
        or stable
        != {
            "field": "occurrenceID",
            "direction": "asc",
            "explicit_order_accepted_and_echoed_requests": 23,
            "expected_length_requests": 23,
            "nonempty_page_count": nonempty_pages,
            "strictly_ascending_nonempty_pages": nonempty_pages,
            "sampled_parent_page_overlap_count": 0,
            "equal_total_parent_pairs": 9,
            "ascending_boundary_parent_pairs": 9,
            "scope": (
                "bounded order and overlap behaviour only; not "
                "snapshot-consistent pagination"
            ),
        }
    ):
        raise PilotValidationError("review overclaims or weakens pagination evidence")
    pagination = review["pagination"]
    if (
        not isinstance(pagination, dict)
        or set(pagination) != {"pair_count", "pairs"}
        or pagination["pair_count"] != 9
        or not isinstance(pagination["pairs"], list)
        or len(pagination["pairs"]) != 9
    ):
        raise PilotValidationError("sanitized pagination pair evidence drifted")
    expected_pairs = []
    for species_id in PARENT_CONCEPTS:
        first = by_key[f"parent__{species_id}__start_000"]
        second = by_key[f"parent__{species_id}__start_025"]
        if (
            first["response_controls"]["total_records"]
            != second["response_controls"]["total_records"]
        ):
            raise PilotValidationError(
                "sanitized parent totalRecords disagree across pages"
            )
        expected_pairs.append(
            {
                "focal_species_id": species_id,
                "first_page_rows": first["returned_rows"],
                "second_page_rows": second["returned_rows"],
                "total_records_equal": True,
                "overlap_count": 0,
                "boundary_strictly_ascending": True,
            }
        )
    if pagination["pairs"] != expected_pairs:
        raise PilotValidationError("sanitized pagination pair evidence drifted")
    if review["observations"] != OBSERVATIONS or review["inference"] != INFERENCE:
        raise PilotValidationError("review makes an overbroad acquisition claim")
    _validate_field_stats(review["field_behavior"], review["returned_rows"])
    if review["field_behavior"] != _aggregate_fields(entries):
        raise PilotValidationError("aggregate field behavior drifted")
    response_projection = review["response_projection"]
    expected_server_stats = _aggregate_unrequested_fields(
        requests["requests"]
    )
    if (
        not isinstance(response_projection, dict)
        or response_projection
        != {
            "frozen_requested_field_count": 20,
            "server_added_raw_allowlist": ["otherProperties"],
            "server_added_field_stats": expected_server_stats,
            "handling": (
                "otherProperties values remain quarantined in ignored raw "
                "responses and are dropped from the canonical projection"
            ),
        }
    ):
        raise PilotValidationError(
            "server-added response projection is unsafe or overbroad"
        )
    fallback = review["fallback_behavior"]
    if (
        not isinstance(fallback, dict)
        or set(fallback) != {"macropus_synonym", "vombatus_children"}
    ):
        raise PilotValidationError("fallback behavior shape drifted")
    mac = fallback["macropus_synonym"]
    mac_parent_rows = sum(
        by_key[f"parent__macropus_giganteus__start_{start:03d}"][
            "returned_rows"
        ]
        for start in (0, 25)
    )
    mac_id_rows = by_key[
        "fallback__macropus_synonym_id__start_000"
    ]["returned_rows"]
    mac_name_rows = by_key[
        "fallback__macropus_synonym_name__start_000"
    ]["returned_rows"]
    if (
        not isinstance(mac, dict)
        or set(mac)
        != {
            "concept_id_rows",
            "normalized_name_rows",
            "concept_id_parent_sample_overlap_count",
            "normalized_name_parent_sample_overlap_count",
        }
        or mac["concept_id_rows"] != mac_id_rows
        or mac["normalized_name_rows"] != mac_name_rows
        or not isinstance(mac["concept_id_parent_sample_overlap_count"], int)
        or isinstance(mac["concept_id_parent_sample_overlap_count"], bool)
        or not 0
        <= mac["concept_id_parent_sample_overlap_count"]
        <= min(mac_id_rows, mac_parent_rows)
        or not isinstance(
            mac["normalized_name_parent_sample_overlap_count"], int
        )
        or isinstance(
            mac["normalized_name_parent_sample_overlap_count"], bool
        )
        or not 0
        <= mac["normalized_name_parent_sample_overlap_count"]
        <= min(mac_name_rows, mac_parent_rows)
    ):
        raise PilotValidationError("Macropus fallback evidence drifted")
    children = fallback["vombatus_children"]
    if (
        not isinstance(children, dict)
        or list(children) != list(VOMBATUS_CHILDREN)
    ):
        raise PilotValidationError("Vombatus fallback evidence drifted")
    vombatus_parent_rows = sum(
        by_key[f"parent__vombatus_ursinus__start_{start:03d}"][
            "returned_rows"
        ]
        for start in (0, 25)
    )
    for child_id in VOMBATUS_CHILDREN:
        child = children[child_id]
        child_rows = by_key[f"fallback__{child_id}__start_000"][
            "returned_rows"
        ]
        if (
            not isinstance(child, dict)
            or set(child)
            != {"returned_rows", "parent_sample_overlap_count"}
            or child["returned_rows"] != child_rows
            or not isinstance(child["parent_sample_overlap_count"], int)
            or isinstance(child["parent_sample_overlap_count"], bool)
            or not 0
            <= child["parent_sample_overlap_count"]
            <= min(child_rows, vombatus_parent_rows)
        ):
            raise PilotValidationError("Vombatus fallback evidence drifted")
    dedup = review["deduplication"]
    if (
        not isinstance(dedup, dict)
        or set(dedup)
        != {
            "key",
            "rows_before_deduplication",
            "unique_rows_after_deduplication",
            "duplicate_references_across_query_branches",
            "duplicates_within_page_or_parent_pagination",
        }
        or dedup["key"] != "occurrenceID"
        or dedup["rows_before_deduplication"] != review["returned_rows"]
        or not isinstance(dedup["unique_rows_after_deduplication"], int)
        or isinstance(dedup["unique_rows_after_deduplication"], bool)
        or not isinstance(
            dedup["duplicate_references_across_query_branches"], int
        )
        or isinstance(
            dedup["duplicate_references_across_query_branches"], bool
        )
        or dedup["unique_rows_after_deduplication"]
        + dedup["duplicate_references_across_query_branches"]
        != review["returned_rows"]
        or dedup["duplicates_within_page_or_parent_pagination"] != 0
    ):
        raise PilotValidationError("deduplication evidence drifted")
    expected_unresolved = []
    mac_status = "established_id_and_name_positive_in_bounded_pilot"
    if mac_id_rows == 0:
        mac_status = "unresolved_id_zero_name_path_positive"
        expected_unresolved.append(
            "macropus_synonym_concept_id_returned_zero_rows_in_bounded_pilot"
        )
    hirsutus_rows = children["vombatus_ursinus_hirsutus"][
        "returned_rows"
    ]
    hirsutus_status = "established_positive_in_bounded_pilot"
    if hirsutus_rows == 0:
        hirsutus_status = "unresolved_scoped_zero"
        expected_unresolved.append(
            "vombatus_ursinus_hirsutus_returned_zero_rows_in_bounded_pilot"
        )
    expected_assertions = {
        "parent_expansion_runtime_coverage": (
            "established_for_bounded_pilot_only"
        ),
        "macropus_giganteus_tasmaniensis_synonym_id_coverage": mac_status,
        "vombatus_ursinus_hirsutus_scope_coverage": hirsutus_status,
        "occurrenceID_deduplication": "established_for_bounded_pilot_only",
    }
    if (
        review["assertions"] != expected_assertions
        or review["unresolved_assertions"] != expected_unresolved
    ):
        raise PilotValidationError("acquisition-time assertions drifted")


def _validate_raw_reconstruction(
    raw_dir: Path,
    entries: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    review: dict[str, Any],
    profile: dict[str, Any],
    config: dict[str, Any],
) -> None:
    expected_files = [spec["raw_file"] for spec in plan]
    try:
        observed_files = sorted(path.name for path in raw_dir.iterdir())
    except OSError as exc:
        raise PilotValidationError("raw pilot directory is unavailable") from exc
    if observed_files != sorted(expected_files):
        raise PilotValidationError("raw pilot file set is incomplete or broadened")
    private: dict[str, list[str]] = {}
    coordinate_values: list[int | float | str] = []
    for entry, spec in zip(entries, plan, strict=True):
        path = raw_dir / spec["raw_file"]
        body = path.read_bytes()
        if (
            _sha256_bytes(body) != entry["raw_sha256"]
            or len(body) != entry["raw_bytes"]
        ):
            raise PilotValidationError("raw response checksum or byte size drifted")
        reconstructed = _analyze_response(spec, body, entry["http_status"])
        for key in (
            "returned_rows",
            "response_controls",
            "query_binding",
            "field_stats",
            "unrequested_field_stats",
            "validation",
        ):
            if entry[key] != reconstructed[key]:
                raise PilotValidationError(
                    "tracked request evidence does not reconstruct from raw"
                )
        private[spec["key"]] = reconstructed["_occurrence_ids"]
        coordinate_values.extend(reconstructed["_coordinate_values"])
        if (
            entry["retrieval_timestamp_basis"]
            == "recovered_raw_file_write_mtime"
            and entry["retrieved_at_utc"]
            != _utc_text(
                datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            )
        ):
            raise PilotValidationError(
                "recovered raw mtime provenance does not reconstruct"
            )
    rebuilt_review = _build_review(
        entries,
        private,
        review["reviewed_at_utc"],
        profile["profile_id"],
        config["plan_id"],
        config["max_returned_rows"],
    )
    if review != rebuilt_review:
        raise PilotValidationError(
            "tracked review does not reconstruct from sanitized request evidence"
        )
    tracked_payload = json.dumps({"entries": entries, "review": review})
    for occurrence_ids in private.values():
        for occurrence_id in occurrence_ids:
            if occurrence_id in tracked_payload:
                raise PilotValidationError(
                    "tracked evidence leaks an occurrenceID payload value"
                )
    for value in coordinate_values:
        encoded = json.dumps(value)
        if len(encoded) >= 4 and encoded in tracked_payload:
            raise PilotValidationError(
                "tracked evidence leaks a coordinate payload value"
            )


def validate_evidence_package(
    evidence_dir: str | Path,
    profile: dict[str, Any],
    config: dict[str, Any],
    *,
    raw_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate tracked evidence, optionally reconstructing it from raw bytes."""

    evidence_dir = Path(evidence_dir)
    validate_pilot_config(config, profile)
    plan = build_request_plan(profile, config)
    try:
        observed = sorted(path.name for path in evidence_dir.iterdir())
    except OSError as exc:
        raise PilotValidationError("evidence directory is unavailable") from exc
    if observed != ["manifest.json", "requests.json", "review.json"]:
        raise PilotValidationError("tracked evidence file set drifted")
    _validate_manifest(evidence_dir)
    requests = _load_json(evidence_dir / "requests.json")
    review = _load_json(evidence_dir / "review.json")
    entries = _validate_request_evidence(requests, plan, profile, config)
    _validate_review_shape(review, requests, profile, config)
    if raw_dir is None:
        return {
            "readiness": TRACKED_ONLY_READINESS,
            "successful_record_requests": requests[
                "successful_record_requests"
            ],
            "http_attempts": requests["http_attempts"],
            "returned_rows": requests["returned_rows"],
            "raw_reconstruction": False,
            "unresolved_assertions": review["unresolved_assertions"],
        }
    _validate_raw_reconstruction(
        Path(raw_dir), entries, plan, review, profile, config
    )
    return {
        "readiness": review["readiness"],
        "successful_record_requests": requests["successful_record_requests"],
        "http_attempts": requests["http_attempts"],
        "returned_rows": requests["returned_rows"],
        "raw_reconstruction": True,
        "unresolved_assertions": review["unresolved_assertions"],
    }


def _validate_rebuild_provenance(
    requests: dict[str, Any],
    review: dict[str, Any],
    plan: list[dict[str, Any]],
    profile: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate immutable provenance while accepting the pre-repair schema."""

    if set(requests) != REQUEST_ROOT_KEYS:
        raise PilotValidationError("rebuild request evidence root drifted")
    if (
        requests["schema_version"] != "1.0"
        or requests["goal_id"] != "013"
        or requests["profile_id"] != profile["profile_id"]
        or requests["plan_id"] != config["plan_id"]
        or requests["endpoint"] != config["endpoint"]
        or requests["method"] != "GET"
        or requests["planned_record_requests"] != 23
        or requests["successful_record_requests"] != 23
        or requests["max_returned_rows"] != 575
        or requests["records_retained_in_tracked_evidence"] is not False
        or requests["coordinates_retained_in_tracked_evidence"] is not False
    ):
        raise PilotValidationError("rebuild request provenance drifted")
    started = _parse_utc(requests["collection_started_at_utc"])
    completed = _parse_utc(requests["collection_completed_at_utc"])
    if completed < started:
        raise PilotValidationError("rebuild collection chronology is impossible")
    entries = requests["requests"]
    if not isinstance(entries, list) or len(entries) != len(plan):
        raise PilotValidationError("rebuild request matrix is incomplete")
    previous_time = started
    for entry, spec in zip(entries, plan, strict=True):
        if (
            not isinstance(entry, dict)
            or frozenset(entry)
            not in {frozenset(REQUEST_ENTRY_KEYS), frozenset(LEGACY_REQUEST_ENTRY_KEYS)}
        ):
            raise PilotValidationError("rebuild request entry shape drifted")
        immutable = {
            "ordinal": spec["ordinal"],
            "key": spec["key"],
            "branch": spec["branch"],
            "focal_species_id": spec["focal_species_id"],
            "concept_id": spec["concept_id"],
            "endpoint": config["endpoint"],
            "method": "GET",
            "ordered_parameters": spec["ordered_parameters"],
            "canonical_url": spec["canonical_url"],
            "raw_file": spec["raw_file"],
        }
        if any(entry[key] != value for key, value in immutable.items()):
            raise PilotValidationError("rebuild request plan binding drifted")
        if entry["http_status"] != 200:
            raise PilotValidationError("rebuild request HTTP status drifted")
        retrieved = _parse_utc(entry["retrieved_at_utc"])
        if retrieved < previous_time or retrieved > completed:
            raise PilotValidationError("rebuild retrieval chronology is impossible")
        previous_time = retrieved
        allowed_bases = {"network_response_completed"}
        if spec["ordinal"] == 1:
            allowed_bases.add("recovered_raw_file_write_mtime")
        if entry["retrieval_timestamp_basis"] not in allowed_bases:
            raise PilotValidationError("rebuild timestamp provenance drifted")
        retries = entry["retry_events"]
        if (
            not isinstance(entry["attempt_count"], int)
            or isinstance(entry["attempt_count"], bool)
            or not 1 <= entry["attempt_count"] <= 2
            or not isinstance(retries, list)
            or len(retries) != entry["attempt_count"] - 1
        ):
            raise PilotValidationError("rebuild retry provenance drifted")
        for retry in retries:
            if (
                not isinstance(retry, dict)
                or set(retry) != {"attempt", "reason"}
                or retry["attempt"] != 1
                or retry["reason"] not in {"transport_error", "http_5xx"}
            ):
                raise PilotValidationError("rebuild retry event drifted")
        if (
            not isinstance(entry["raw_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["raw_sha256"])
            or not isinstance(entry["raw_bytes"], int)
            or isinstance(entry["raw_bytes"], bool)
            or entry["raw_bytes"] <= 0
        ):
            raise PilotValidationError("rebuild raw provenance is malformed")
        controls = entry["response_controls"]
        if (
            not isinstance(controls, dict)
            or frozenset(controls)
            not in {
                frozenset(RESPONSE_CONTROL_KEYS),
                frozenset(LEGACY_RESPONSE_CONTROL_KEYS),
            }
        ):
            raise PilotValidationError("rebuild response controls drifted")
    if (
        not isinstance(review, dict)
        or set(review) != REVIEW_KEYS
        or review["schema_version"] != "1.0"
        or review["goal_id"] != "013"
        or review["profile_id"] != profile["profile_id"]
        or review["plan_id"] != config["plan_id"]
        or _parse_utc(review["reviewed_at_utc"]) < completed
    ):
        raise PilotValidationError("rebuild review provenance drifted")
    return entries


def rebuild_evidence_from_raw(
    profile_path: str | Path,
    config_path: str | Path,
    raw_dir: str | Path,
    evidence_dir: str | Path,
    *,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Recompute only sanitized evidence from the immutable raw pilot files."""

    profile_path = Path(profile_path)
    config_path = Path(config_path)
    raw_dir = Path(raw_dir)
    evidence_dir = Path(evidence_dir)
    profile_bytes = profile_path.read_bytes()
    if _sha256_bytes(profile_bytes) != EXPECTED_PROFILE_SHA256:
        raise PilotValidationError("Goal 012 profile file checksum drifted")
    profile = json.loads(profile_bytes)
    config = _load_json(config_path)
    validate_pilot_config(config, profile)
    plan = build_request_plan(profile, config)
    _validate_manifest(evidence_dir)
    previous_requests = _load_json(evidence_dir / "requests.json")
    previous_review = _load_json(evidence_dir / "review.json")
    previous_entries = _validate_rebuild_provenance(
        previous_requests, previous_review, plan, profile, config
    )
    try:
        observed_raw = sorted(path.name for path in raw_dir.iterdir())
    except OSError as exc:
        raise PilotValidationError("raw pilot directory is unavailable") from exc
    if observed_raw != sorted(spec["raw_file"] for spec in plan):
        raise PilotValidationError("raw pilot file set is incomplete or broadened")

    rebuilt_entries: list[dict[str, Any]] = []
    private: dict[str, list[str]] = {}
    for entry, spec in zip(previous_entries, plan, strict=True):
        raw_path = raw_dir / spec["raw_file"]
        body = raw_path.read_bytes()
        if (
            _sha256_bytes(body) != entry["raw_sha256"]
            or len(body) != entry["raw_bytes"]
        ):
            raise PilotValidationError(
                "raw response changed before evidence-only rebuild"
            )
        analysis = _analyze_response(spec, body, entry["http_status"])
        rebuilt = dict(entry)
        for key in (
            "returned_rows",
            "response_controls",
            "query_binding",
            "field_stats",
            "unrequested_field_stats",
            "validation",
        ):
            rebuilt[key] = analysis[key]
        if (
            rebuilt["retrieval_timestamp_basis"]
            == "recovered_raw_file_write_mtime"
            and rebuilt["retrieved_at_utc"]
            != _utc_text(
                datetime.fromtimestamp(raw_path.stat().st_mtime, tz=timezone.utc)
            )
        ):
            raise PilotValidationError(
                "recovered raw mtime changed before evidence-only rebuild"
            )
        rebuilt_entries.append(rebuilt)
        private[spec["key"]] = analysis["_occurrence_ids"]

    rebuilt_requests = dict(previous_requests)
    rebuilt_requests["requests"] = rebuilt_entries
    rebuilt_requests["returned_rows"] = sum(
        entry["returned_rows"] for entry in rebuilt_entries
    )
    rebuilt_requests["successful_record_requests"] = len(rebuilt_entries)
    rebuilt_requests["http_attempts"] = sum(
        entry["attempt_count"] for entry in rebuilt_entries
    )
    review_time = max(
        now_fn().astimezone(timezone.utc),
        _parse_utc(previous_review["reviewed_at_utc"]),
        _parse_utc(rebuilt_requests["collection_completed_at_utc"]),
    )
    rebuilt_review = _build_review(
        rebuilt_entries,
        private,
        _utc_text(review_time),
        profile["profile_id"],
        config["plan_id"],
        config["max_returned_rows"],
    )
    _write_json(evidence_dir / "requests.json", rebuilt_requests)
    _write_json(evidence_dir / "review.json", rebuilt_review)
    manifest = {
        "schema_version": "1.0",
        "files": [
            {
                "path": filename,
                "sha256": _sha256_bytes((evidence_dir / filename).read_bytes()),
                "bytes": (evidence_dir / filename).stat().st_size,
            }
            for filename in EVIDENCE_FILENAMES
        ],
    }
    _write_json(evidence_dir / "manifest.json", manifest)
    replay = validate_evidence_package(
        evidence_dir, profile, config, raw_dir=raw_dir
    )
    return {
        **replay,
        "http_requests_made": 0,
    }


def _resolve_cli_path(path: Path, expected_relative: str) -> None:
    expected = (Path.cwd() / expected_relative).resolve()
    if path.resolve() != expected:
        raise PilotValidationError(
            f"CLI output path must be exactly {expected_relative}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument(
        "--rebuild-evidence",
        action="store_true",
        help="recompute sanitized evidence from existing raw files; no HTTP",
    )
    args = parser.parse_args(argv)
    config = _load_json(args.plan)
    _resolve_cli_path(args.raw_dir, config.get("raw_relative_path", ""))
    _resolve_cli_path(
        args.evidence_dir, config.get("evidence_relative_path", "")
    )
    if args.rebuild_evidence:
        result = rebuild_evidence_from_raw(
            args.profile,
            args.plan,
            args.raw_dir,
            args.evidence_dir,
        )
    else:
        result = collect_pilot(
            args.profile,
            args.plan,
            args.raw_dir,
            args.evidence_dir,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
