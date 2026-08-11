"""Resumable raw ALA occurrence acquisition for the frozen Goal 040 cohort."""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import os
import re
import signal
import tempfile
import unicodedata
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .goal040_count_census import (
    BBOX,
    CONFIG_PATH,
    LEDGER_PATH,
    MANIFEST_PATH as COUNT_MANIFEST_PATH,
    PACKAGE,
    YEARS,
    build_branch_matrix,
    build_taxon_union_matrix,
    validate_count_census,
)


DOMAIN_PATH = Path("metadata/goal040_domain_boundary_manifest.json")
MANIFEST_PATH = Path("metadata/goal040_acquisition_manifest.json")
RAW_ROOT = Path("data/raw/goal040/acquisition")
EXPECTED_TOTAL = 1_258_883
TIMEOUT_SECONDS = 7_200
REQUEST_FIELDS = [
    "recordID", "occurrenceID", "dataResourceUid", "dataResourceName",
    "datasetID", "datasetName", "basisOfRecord", "establishmentMeans",
    "occurrenceStatus", "eventDate", "year", "decimalLatitude",
    "decimalLongitude", "coordinateUncertaintyInMeters", "coordinatePrecision",
    "raw_scientificName", "raw_taxonConceptID", "scientificName",
    "taxonConceptID", "acceptedNameUsage", "acceptedNameUsageID", "taxonRank",
    "assertions", "license",
]
ESSENTIAL_RETURNED = {
    *REQUEST_FIELDS[:-1], "dcterms:license",
}
KNOWN_ASSERTION_FIELDS = {"COORDINATE_INVALID", "temporalIssue", "taxonomicIssue"}
EMAIL_RE = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
URL_RE = re.compile(r"https?://", re.I)


class Goal040AcquisitionError(ValueError):
    """Sanitised fail-closed acquisition or validation error."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal040AcquisitionError(reason)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal040AcquisitionError("invalid_json_input") from exc
    _require(isinstance(value, dict), "json_input_not_object")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_bytes(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")
    temporary.replace(path)


def _clean_id(value: Any) -> bool:
    text = "" if value is None else str(value)
    return bool(text.strip()) and not any(
        unicodedata.category(character).startswith("C") for character in text
    )


def _contains(path: Path, value: str) -> bool:
    needle = value.encode()
    if not needle:
        return False
    carry = b""
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            block = carry + chunk
            if needle in block:
                return True
            carry = block[-len(needle) + 1:] if len(needle) > 1 else b""
    return False


def _alarm(call: Callable[[], Any], seconds: int) -> Any:
    def handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError

    previous = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return call()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _paths(root: Path, query_id: str) -> tuple[Path, Path, Path]:
    stem = query_id.removesuffix("__taxon_union")
    raw = root / RAW_ROOT
    return raw / f"{stem}.partial.csv", raw / f"{stem}.csv", raw / f"{stem}.receipt.json"


def _load_plan(root: Path) -> dict[str, Any]:
    result = validate_count_census(root, require_raw=False)
    _require(result["result"] == "pass_acquisition_authorised", "count_gate_not_passed")
    _require(result["conservative_bbox_prefilter_rows"] == EXPECTED_TOTAL, "count_total_drift")
    count_manifest = _json(root / COUNT_MANIFEST_PATH)
    branches = build_branch_matrix(root)
    unions = build_taxon_union_matrix(branches)
    matrix_sha = hashlib.sha256(_canonical(unions)).hexdigest()
    _require(
        count_manifest["bindings"].get("ordered_taxon_union_matrix_sha256") == matrix_sha,
        "taxon_union_matrix_binding_drift",
    )
    counts = {
        item["query_id"]: item["conservative_bbox_prefilter_rows"]
        for item in count_manifest["taxon_queries"]
    }
    _require(set(counts) == {item["branch_id"] for item in unions}, "taxon_count_coverage_drift")
    ordered = sorted(
        [dict(item, expected_rows=counts[item["branch_id"]]) for item in unions],
        key=lambda item: (item["expected_rows"], item["taxon"]),
    )
    bindings = {
        "contract": {"path": str(CONFIG_PATH), "sha256": _sha(root / CONFIG_PATH)},
        "taxon_ledger": {"path": str(LEDGER_PATH), "sha256": _sha(root / LEDGER_PATH)},
        "domain_manifest": {"path": str(DOMAIN_PATH), "sha256": _sha(root / DOMAIN_PATH)},
        "count_manifest": {"path": str(COUNT_MANIFEST_PATH), "sha256": _sha(root / COUNT_MANIFEST_PATH)},
        "ordered_taxon_union_matrix_sha256": matrix_sha,
    }
    return {"queries": ordered, "bindings": bindings, "total": EXPECTED_TOTAL}


def _validate_csv(path: Path, expected_rows: int) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), "raw_csv_missing_or_unsafe")
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            raw_reader = csv.reader(stream)
            header = next(raw_reader, [])
        _require(bool(header) and len(header) == len(set(header)), "raw_header_not_unique")
        _require(ESSENTIAL_RETURNED <= set(header), "raw_header_missing_essential_fields")
        _require(KNOWN_ASSERTION_FIELDS <= set(header), "raw_header_missing_expanded_assertions")
        rows = record_populated = occurrence_populated = 0
        identifiers: set[str] = set()
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            _require(list(reader.fieldnames or []) == header, "raw_header_drift")
            for row in reader:
                rows += 1
                _require(set(row) == set(header), "raw_row_schema_drift")
                record_id = row.get("recordID")
                _require(_clean_id(record_id), "recordID_blank_or_control")
                record_populated += 1
                identifiers.add(str(record_id))
                occurrence_populated += bool((row.get("occurrenceID") or "").strip())
    except (OSError, csv.Error, UnicodeError) as exc:
        raise Goal040AcquisitionError("raw_csv_invalid") from exc
    _require(rows == expected_rows, "raw_row_count_mismatch")
    return {
        "rows": rows,
        "recordID_populated": record_populated,
        "occurrenceID_populated": occurrence_populated,
        "identifiers": identifiers,
        "header": header,
        "header_sha256": hashlib.sha256(_canonical(header)).hexdigest(),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _expected_receipt(query: dict[str, Any], stats: dict[str, Any], completed_at: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "stage": "goal040_raw_occurrence_acquisition",
        "completed_at": completed_at,
        "query": {
            "query_id": query["branch_id"],
            "taxon": query["taxon"],
            "query_identity_sha256": query["query_identity_sha256"],
            "identifier_union_sha256": hashlib.sha256(_canonical(query["selector_value"])).hexdigest(),
            "identifier_count": len(query["selector_value"]),
            "alias_downloads": 0,
        },
        "call": {
            "package": PACKAGE,
            "function": "atlas_occurrences",
            "filters": ["year>=2001", "year<=2025"],
            "bbox": BBOX,
            "use_data_profile": False,
            "mint_doi": False,
            "calls": 1,
        },
        "raw": {
            "rows": stats["rows"],
            "bytes": stats["bytes"],
            "sha256": stats["sha256"],
            "header": stats["header"],
            "header_sha256": stats["header_sha256"],
            "recordID_populated": stats["recordID_populated"],
            "occurrenceID_populated": stats["occurrenceID_populated"],
        },
        "runtime_contact_retained": False,
    }


def _validate_pair(root: Path, query: dict[str, Any]) -> dict[str, Any]:
    partial, final, receipt_path = _paths(root, query["branch_id"])
    _require(not partial.exists(), "partial_conflicts_with_completed_pair")
    _require(final.exists() and receipt_path.exists(), "completed_pair_incomplete")
    receipt = _json(receipt_path)
    _require(
        bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", receipt.get("completed_at", ""))),
        "completion_receipt_time_drift",
    )
    stats = _validate_csv(final, query["expected_rows"])
    expected = _expected_receipt(query, stats, receipt.get("completed_at", ""))
    _require(receipt == expected and bool(receipt["completed_at"]), "completion_receipt_drift")
    return stats | {"completed_at": receipt["completed_at"]}


def _download_one(
    root: Path,
    query: dict[str, Any],
    galah_module: Any,
    config_path: Path,
    runtime_contact: str,
    alarm_fn: Callable[[Callable[[], Any], int], Any],
) -> dict[str, Any]:
    partial, final, receipt = _paths(root, query["branch_id"])
    partial.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame = alarm_fn(
            lambda: galah_module.atlas_occurrences(
                identifiers=query["selector_value"],
                filters=["year>=2001", "year<=2025"],
                fields=REQUEST_FIELDS,
                bbox=BBOX,
                use_data_profile=False,
                mint_doi=False,
                print_doi=False,
                config_file=str(config_path),
            ),
            TIMEOUT_SECONDS,
        )
        frame.to_csv(partial, index=False, lineterminator="\n")
    except Exception:
        raise Goal040AcquisitionError("occurrence_download_or_serialization_failed") from None
    if _contains(partial, runtime_contact):
        partial.unlink()
        raise Goal040AcquisitionError("runtime_contact_leaked_to_raw")
    stats = _validate_csv(partial, query["expected_rows"])
    partial.replace(final)
    _write_json_atomic(receipt, _expected_receipt(query, stats, _now()))
    return _validate_pair(root, query)


def _prepare_state(root: Path, query: dict[str, Any]) -> bool:
    partial, final, receipt = _paths(root, query["branch_id"])
    if partial.exists() and not final.exists() and not receipt.exists():
        _require(partial.is_file() and not partial.is_symlink(), "partial_file_unsafe")
        partial.unlink()
    _require(not partial.exists(), "partial_state_ambiguous")
    _require(final.exists() == receipt.exists(), "completed_pair_orphaned")
    return final.exists()


def _validate_raw_footprint(root: Path, queries: list[dict[str, Any]]) -> None:
    raw = root / RAW_ROOT
    expected = set()
    for query in queries:
        _, final, receipt = _paths(root, query["branch_id"])
        expected.update({final.name, receipt.name})
    observed = {path.name for path in raw.iterdir()} if raw.exists() else set()
    _require(observed == expected, "raw_acquisition_footprint_drift")


def _manifest(root: Path, plan: dict[str, Any], completed: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    header_hashes = {stats["header_sha256"] for _, stats in completed}
    _require(len(header_hashes) == 1, "raw_headers_not_identical")
    seen: set[str] = set()
    cross_union_duplicates: set[str] = set()
    entries = []
    occurrence_populated = 0
    for query, stats in completed:
        cross_union_duplicates.update(seen.intersection(stats["identifiers"]))
        seen.update(stats["identifiers"])
        occurrence_populated += stats["occurrenceID_populated"]
        _, final, _ = _paths(root, query["branch_id"])
        entries.append({
            "query_id": query["branch_id"], "taxon": query["taxon"],
            "query_identity_sha256": query["query_identity_sha256"],
            "expected_rows": query["expected_rows"], "actual_rows": stats["rows"],
            "raw_path": str(final.relative_to(root)), "raw_bytes": stats["bytes"],
            "raw_sha256": stats["sha256"], "header_sha256": stats["header_sha256"],
            "recordID_populated": stats["recordID_populated"],
            "occurrenceID_populated": stats["occurrenceID_populated"],
        })
    total = sum(item["actual_rows"] for item in entries)
    return {
        "schema_version": "1.0", "goal_id": "goal040-se-mammal-acquisition-feasibility",
        "stage": "occurrence-acquisition", "status": "complete_raw_replay_required",
        "completed_at": _now(), "package": PACKAGE,
        "bindings": plan["bindings"],
        "scope": {
            "taxa": 21, "years_inclusive": YEARS,
            "bbox_prefilter_sha256": hashlib.sha256(_canonical(BBOX)).hexdigest(),
            "one_worker_sequential": True, "taxon_order": "ascending_frozen_count_then_taxon",
            "use_data_profile": False, "mint_doi": False, "alias_downloads": 0,
            "sampling_or_additional_taxon_screen": False,
        },
        "projection": {
            "request_fields_sha256": hashlib.sha256(_canonical(REQUEST_FIELDS)).hexdigest(),
            "expanded_assertions_required": True,
            "identical_actual_header_sha256": next(iter(header_hashes)),
        },
        "taxon_downloads": entries,
        "summary": {
            "files": len(entries), "rows": total,
            "recordID_populated": sum(item["recordID_populated"] for item in entries),
            "recordID_distinct": len(seen),
            "occurrenceID_populated": occurrence_populated,
            "occurrenceID_blank": total - occurrence_populated,
            "cross_union_duplicate_recordID_distinct": len(cross_union_duplicates),
        },
        "privacy": {
            "tracked_row_payload": False, "runtime_contact_retained": False,
            "recordID_values_retained": False, "coordinates_retained": False,
            "event_dates_retained": False, "raw_files_tracked": False,
        },
    }


def _validate_tracked(manifest: dict[str, Any], plan: dict[str, Any]) -> None:
    _require(set(manifest) == {
        "schema_version", "goal_id", "stage", "status", "completed_at", "package",
        "bindings", "scope", "projection", "taxon_downloads", "summary", "privacy",
    }, "acquisition_manifest_shape_drift")
    _require(
        manifest.get("schema_version") == "1.0"
        and manifest.get("goal_id") == "goal040-se-mammal-acquisition-feasibility"
        and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest.get("completed_at", ""))),
        "acquisition_manifest_provenance_drift",
    )
    _require(manifest.get("stage") == "occurrence-acquisition", "acquisition_manifest_identity_drift")
    _require(manifest.get("status") == "complete_raw_replay_required", "acquisition_status_drift")
    _require(manifest.get("package") == PACKAGE and manifest.get("bindings") == plan["bindings"], "acquisition_binding_drift")
    _require(manifest.get("scope") == {
        "taxa": 21, "years_inclusive": YEARS,
        "bbox_prefilter_sha256": hashlib.sha256(_canonical(BBOX)).hexdigest(),
        "one_worker_sequential": True, "taxon_order": "ascending_frozen_count_then_taxon",
        "use_data_profile": False, "mint_doi": False, "alias_downloads": 0,
        "sampling_or_additional_taxon_screen": False,
    }, "acquisition_scope_drift")
    entries = manifest.get("taxon_downloads")
    _require(isinstance(entries, list) and len(entries) == 21, "acquisition_taxon_coverage_drift")
    expected = plan["queries"]
    entry_keys = {
        "query_id", "taxon", "query_identity_sha256", "expected_rows", "actual_rows",
        "raw_path", "raw_bytes", "raw_sha256", "header_sha256",
        "recordID_populated", "occurrenceID_populated",
    }
    _require(all(set(item) == entry_keys for item in entries), "acquisition_entry_shape_drift")
    _require(
        [(item.get("query_id"), item.get("expected_rows")) for item in entries]
        == [(item["branch_id"], item["expected_rows"]) for item in expected],
        "acquisition_order_or_count_drift",
    )
    _require(all(item.get("actual_rows") == item.get("expected_rows") for item in entries), "acquisition_row_arithmetic_drift")
    _require(
        all(
            item.get("query_identity_sha256") == query["query_identity_sha256"]
            and item.get("taxon") == query["taxon"]
            and item.get("raw_path") == str(_paths(Path("."), query["branch_id"])[1])
            and isinstance(item.get("raw_bytes"), int) and item["raw_bytes"] > 0
            and item.get("recordID_populated") == query["expected_rows"]
            and isinstance(item.get("occurrenceID_populated"), int)
            and 0 <= item["occurrenceID_populated"] <= query["expected_rows"]
            and re.fullmatch(r"[0-9a-f]{64}", item.get("raw_sha256", ""))
            and re.fullmatch(r"[0-9a-f]{64}", item.get("header_sha256", ""))
            for item, query in zip(entries, expected)
        ),
        "acquisition_query_or_hash_drift",
    )
    header_hashes = {item.get("header_sha256") for item in entries}
    _require(len(header_hashes) == 1 and manifest.get("projection") == {
        "request_fields_sha256": hashlib.sha256(_canonical(REQUEST_FIELDS)).hexdigest(),
        "expanded_assertions_required": True,
        "identical_actual_header_sha256": next(iter(header_hashes)),
    }, "acquisition_projection_drift")
    summary = manifest.get("summary", {})
    _require(set(summary) == {
        "files", "rows", "recordID_populated", "recordID_distinct",
        "occurrenceID_populated", "occurrenceID_blank",
        "cross_union_duplicate_recordID_distinct",
    }, "acquisition_summary_shape_drift")
    _require(summary.get("files") == 21 and summary.get("rows") == plan["total"], "acquisition_summary_drift")
    _require(
        summary.get("recordID_populated") == sum(item["recordID_populated"] for item in entries) == plan["total"],
        "recordID_completeness_drift",
    )
    _require(
        summary.get("occurrenceID_populated") == sum(item["occurrenceID_populated"] for item in entries)
        and summary.get("occurrenceID_blank") == plan["total"] - summary["occurrenceID_populated"],
        "occurrenceID_arithmetic_drift",
    )
    _require(
        isinstance(summary.get("recordID_distinct"), int)
        and 0 <= summary["recordID_distinct"] <= plan["total"]
        and isinstance(summary.get("cross_union_duplicate_recordID_distinct"), int)
        and 0 <= summary["cross_union_duplicate_recordID_distinct"] <= summary["recordID_distinct"],
        "recordID_diagnostic_arithmetic_drift",
    )
    _require(manifest.get("privacy") == {
        "tracked_row_payload": False, "runtime_contact_retained": False,
        "recordID_values_retained": False, "coordinates_retained": False,
        "event_dates_retained": False, "raw_files_tracked": False,
    }, "acquisition_privacy_drift")
    text = json.dumps(manifest, sort_keys=True)
    _require(not EMAIL_RE.search(text) and not URL_RE.search(text), "tracked_manifest_private_material")


def validate_acquisition(
    root: Path,
    *,
    require_raw: bool = False,
    _plan_loader: Callable[[Path], dict[str, Any]] = _load_plan,
) -> dict[str, Any]:
    root = Path(root)
    plan = _plan_loader(root)
    manifest = _json(root / MANIFEST_PATH)
    _validate_tracked(manifest, plan)
    if not require_raw:
        return {"status": "tracked_acquisition_manifest_valid_raw_replay_required", "raw_replay_required": True}
    _validate_raw_footprint(root, plan["queries"])
    completed = [(query, _validate_pair(root, query)) for query in plan["queries"]]
    replay = _manifest(root, plan, completed)
    for key in ("bindings", "scope", "projection", "taxon_downloads", "summary", "privacy"):
        _require(manifest.get(key) == replay.get(key), "raw_replay_disagrees_with_manifest")
    return {"status": "acquisition_complete_raw_replay_validated", "raw_replay_required": False, **manifest["summary"]}


def run_acquisition(
    root: Path,
    *,
    galah_module: Any | None = None,
    environ: Mapping[str, str] | None = None,
    alarm_fn: Callable[[Callable[[], Any], int], Any] = _alarm,
    _plan_loader: Callable[[Path], dict[str, Any]] = _load_plan,
) -> dict[str, Any]:
    root = Path(root)
    plan = _plan_loader(root)
    if (root / MANIFEST_PATH).exists():
        return validate_acquisition(root, require_raw=True, _plan_loader=_plan_loader)
    complete = {}
    common_header_sha256 = None
    for query in plan["queries"]:
        present = _prepare_state(root, query)
        if present:
            stats = _validate_pair(root, query)
            if common_header_sha256 is None:
                common_header_sha256 = stats["header_sha256"]
            _require(stats["header_sha256"] == common_header_sha256, "raw_headers_not_identical")
        complete[query["branch_id"]] = present
    missing = [query for query in plan["queries"] if not complete[query["branch_id"]]]
    if missing:
        contact = (os.environ if environ is None else environ).get("ALA_DOWNLOAD_EMAIL", "").strip()
        _require(bool(contact), "runtime_download_contact_missing")
        if galah_module is None:
            try:
                galah_module = importlib.import_module("galah")
            except ImportError as exc:
                raise Goal040AcquisitionError("galah_dependency_unavailable") from exc
        _require(getattr(galah_module, "__version__", None) == PACKAGE["version"], "galah_version_drift")
        with tempfile.TemporaryDirectory(prefix="dsdm-goal040-galah-") as temporary:
            config_path = Path(temporary) / "config.ini"
            try:
                galah_module.galah_config(
                    atlas="Australia", email=contact, email_notify=False, reason=4,
                    authenticate=False, data_profile=None, verbose=False, timeout=600,
                    config_file=str(config_path),
                )
            except Exception:
                raise Goal040AcquisitionError("galah_runtime_configuration_failed") from None
            for query in missing:
                stats = _download_one(root, query, galah_module, config_path, contact, alarm_fn)
                if common_header_sha256 is None:
                    common_header_sha256 = stats["header_sha256"]
                _require(stats["header_sha256"] == common_header_sha256, "raw_headers_not_identical")
    completed = [(query, _validate_pair(root, query)) for query in plan["queries"]]
    _validate_raw_footprint(root, plan["queries"])
    manifest = _manifest(root, plan, completed)
    _write_json_atomic(root / MANIFEST_PATH, manifest)
    return validate_acquisition(root, require_raw=True, _plan_loader=_plan_loader)
