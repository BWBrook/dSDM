"""Fail-closed, raw-replayable validation for the Goal 014 ALA gate.

The live operation was bounded to one count selector and one operator-reported
GET attempt.  This module performs no network calls and never interprets the
HTTP 403 causally.  A blocked result is the only possible outcome.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

from .ala_query_scope import OCCURRENCE_SEARCH_URL, PARENT_CONCEPTS, REQUIRED_RECORD_FIELDS


class OfflineDownloadValidationError(ValueError):
    """Raised when the Goal 014 package is incomplete or unsafe."""


DOWNLOAD_ENDPOINT = "https://api.ala.org.au/occurrences/offline/download"
STATUS_ENDPOINT_TEMPLATE = "https://api.ala.org.au/occurrences/offline/status/{id}"
OPENAPI_URL = "https://docs.ala.org.au/openapi/specs/biocache.json"
OFFICIAL_HOSTS = ["api.ala.org.au", "www.ala.org.au", "ala.org.au"]
TERMINAL_STATES = ["cancelled", "finished", "tooLarge"]
NONTERMINAL_STATES = ["inQueue", "running"]
EXPECTED_SELECTOR_MAX = 3
EXPECTED_JOB_MAX = 1
EXPECTED_POLL_MAX = 60
MAX_RECORDS = 100
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
RAW_FILENAME = "count-pseudocheirus-2001.json"
RAW_SHA256 = "5e763af2e2d603dd3c2c9dc6e01cd5bb4c43a8cfdb5f938eee89dafde3bcd5f8"
RAW_BYTES = 1142
BLOCKED = "blocked_submission_http_403_no_job_handle_observed"
TRACKED_ONLY = "blocked_package_structurally_valid_selector_raw_replay_required"
EMAIL_RE = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
PRIVATE_KEY_FORMS = {
    "email", "userid", "jobid", "statusurl", "downloadurl", "cancelurl",
    "apikey", "jwt", "token", "authorization",
}
PUBLIC_FIELD_NAMES = set(REQUIRED_RECORD_FIELDS)
EXPECTED_STATUS_SCHEMA_FIELDS = ["status", "totalRecords", "records", "queueSize", "message", "error", "startDate"]
EXPECTED_PROJECTION_DECISION = {"fields": "exact frozen 20-field download projection", "fl": "omitted; OpenAPI defines it as search-response fields", "includeMultivalues": False, "extra": "omitted", "qa": "none", "dwcHeaders": False, "includeMisc": False}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OfflineDownloadValidationError(message)


def _normal_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _scan_private(value: Any, *, path: str = "root", allow_public_fields: bool = False) -> None:
    """Reject private identifiers, row payloads, and unsafe URLs in evidence."""
    if isinstance(value, str):
        _require(not EMAIL_RE.search(value), f"email-like value at {path}")
        if allow_public_fields and value in PUBLIC_FIELD_NAMES:
            return
        lower = value.lower()
        for token in ("userid", "jobid", "statusurl", "downloadurl", "cancelurl", "coordinates", "eventtimestamp"):
            _require(token not in _normal_key(lower), f"private token at {path}")
    elif isinstance(value, dict):
        for key, item in value.items():
            normalized = _normal_key(key)
            _require(normalized not in PRIVATE_KEY_FORMS, f"private key at {path}.{key}")
            _require(normalized != "occurrences" or path.endswith("contract.json"), f"payload key at {path}.{key}")
            _scan_private(item, path=f"{path}.{key}", allow_public_fields=allow_public_fields or normalized in {"fields", "alafields"})
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _scan_private(item, path=f"{path}[{i}]", allow_public_fields=allow_public_fields)


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate exact immutable request, lifecycle, archive, and source controls."""
    root = {"schema_version", "goal_id", "endpoint", "method", "selector", "max_selector_calls", "max_jobs", "scope", "quality", "projection", "submission", "lifecycle", "archive", "route_cap_evidence"}
    _require(set(plan) == root, "plan root shape drifted")
    _require(plan["schema_version"] == "1.0" and plan["goal_id"] == "goal014-ala-offline-download-gate-2026-07-24", "plan identity drifted")
    _require(plan["endpoint"] == DOWNLOAD_ENDPOINT and plan["method"] == "GET", "download route/method drifted")
    _require(plan["max_selector_calls"] == 3 and plan["max_jobs"] == 1, "global caps drifted")
    selector = plan["selector"]
    _require(set(selector) == {"species_id", "accepted_parent_concept", "accepted_concept_query", "candidate_years", "max_calls", "pageSize", "start", "facet", "disableAllQualityFilters"}, "selector schema drifted")
    _require(selector["species_id"] == "pseudocheirus_peregrinus" and selector["accepted_parent_concept"] == PARENT_CONCEPTS["pseudocheirus_peregrinus"], "selector concept drifted")
    _require(selector["candidate_years"] == [2001, 2002, 2003] and selector["max_calls"] == 3, "selector call order/cap drifted")
    _require(selector["pageSize"] == 0 and selector["start"] == 0 and selector["facet"] is False and selector["disableAllQualityFilters"] is True, "selector controls drifted")
    _require(plan["scope"] == {"stateProvince": "Tasmania", "year": {"start": 2001, "end": 2001, "inclusive": True}}, "scope drifted")
    _require(plan["quality"] == {"disableAllQualityFilters": True, "qa": "none"}, "quality policy drifted")
    projection = plan["projection"]
    _require(set(projection) == {"fields", "fl", "includeMultivalues", "extra", "field_semantics"}, "projection schema drifted")
    _require(projection["fields"] == REQUIRED_RECORD_FIELDS and projection["fl"] is None and projection["includeMultivalues"] is False and projection["extra"] is None, "projection drifted")
    submission = plan["submission"]
    _require(set(submission) == {"email_runtime_env", "emailNotify", "mintDoi", "dwcHeaders", "includeMisc", "fileType", "sep", "reason_code", "auth", "allow_post"}, "submission schema drifted")
    _require(submission == {"email_runtime_env": "ALA_DOWNLOAD_EMAIL", "emailNotify": False, "mintDoi": False, "dwcHeaders": False, "includeMisc": False, "fileType": "csv", "sep": ",", "reason_code": "scientific-research-validation", "auth": "none", "allow_post": False}, "submission controls drifted")
    lifecycle = plan["lifecycle"]
    _require(set(lifecycle) == {"status_endpoint_template", "terminal_states", "nonterminal_states", "max_polls", "cancel_policy"}, "lifecycle schema drifted")
    _require(lifecycle["status_endpoint_template"] == STATUS_ENDPOINT_TEMPLATE and lifecycle["terminal_states"] == TERMINAL_STATES and lifecycle["nonterminal_states"] == NONTERMINAL_STATES and lifecycle["max_polls"] == EXPECTED_POLL_MAX, "lifecycle controls drifted")
    archive = plan["archive"]
    _require(archive == {"max_bytes": MAX_ARCHIVE_BYTES, "allowed_hosts": OFFICIAL_HOSTS, "expected_format": "zip-containing-csv", "rows_retained_in_tracked_evidence": 0}, "archive controls drifted")
    cap = plan["route_cap_evidence"]
    _require(set(cap) == {"status", "search_depth_cap", "offline_source_default_maximum", "production_operability", "deployed_offline_maximum", "openapi_source", "source_commit", "source_anchors", "interpretation"}, "route-cap evidence schema drifted")
    _require(cap["status"] == "documented_architecture_unverified_operability" and cap["search_depth_cap"] == 5000 and cap["offline_source_default_maximum"] == 100000000 and cap["production_operability"] == "unverified_http_403" and cap["deployed_offline_maximum"] == "unknown", "route-cap evidence drifted")
    _require(cap["openapi_source"] == OPENAPI_URL and cap["source_commit"] == "bcfb37661008dce5d3e532258458eb72d03e7530", "official source anchors drifted")
    return {"selector_calls_max": 3, "jobs_max": 1, "polls_max": EXPECTED_POLL_MAX, "field_count": 20}


def _expected_selector_query(plan: dict[str, Any]) -> str:
    concept = plan["selector"]["accepted_parent_concept"]
    params = [("q", f'taxonConceptID:"{concept}"'), ("disableAllQualityFilters", "true"), ("fq", "stateProvince:Tasmania"), ("fq", "year:[2001 TO 2001]")]
    return "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def _replay_selector_raw(raw_dir: Path, plan: dict[str, Any], count_doc: dict[str, Any]) -> None:
    _require(raw_dir.is_dir(), "raw selector directory missing")
    entries = list(raw_dir.iterdir())
    _require(len(entries) == 1 and entries[0].name == RAW_FILENAME, "raw selector directory footprint drifted")
    raw = entries[0]
    _require(raw.is_file() and not raw.is_symlink() and raw.stat().st_size == RAW_BYTES and sha256(raw) == RAW_SHA256, "raw selector checksum/size drifted")
    payload = json.loads(raw.read_text(encoding="utf-8"))
    expected_keys = {"pageSize", "startIndex", "totalRecords", "sort", "dir", "status", "occurrences", "facetResults", "query", "urlParameters", "queryTitle", "activeFacetMap", "activeFacetObj"}
    _require(set(payload) == expected_keys, "raw selector schema drifted")
    _require(payload["status"] == "OK" and payload["pageSize"] == 0 and payload["startIndex"] == 0 and payload["totalRecords"] == 17, "raw selector controls/count drifted")
    _require(payload["occurrences"] == [] and payload["facetResults"] == [], "raw selector contains rows/facets")
    expected_query = _expected_selector_query(plan)
    _require(payload["query"] == expected_query and payload["urlParameters"] == expected_query, "raw selector query binding drifted")
    _require(count_doc["selected_count"] == 17 and count_doc["raw_sha256"] == RAW_SHA256 and count_doc["raw_bytes"] == RAW_BYTES, "tracked selector evidence does not bind raw")


def validate_evidence_package(package: Path, plan: dict[str, Any], *, raw_dir: Path | None = None) -> dict[str, Any]:
    """Validate tracked evidence, optionally replaying the exact raw selector."""
    validate_plan(plan)
    package = Path(package)
    manifest_path = package / "manifest.json"
    _require(manifest_path.is_file(), "evidence manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(set(manifest) == {"schema_version", "files"} and manifest["schema_version"] == "1.0", "manifest shape drifted")
    expected_names = {"contract.json", "count_selection.json", "submission.json", "review.json"}
    _require({str(item.get("path")) for item in manifest["files"]} == expected_names and len(manifest["files"]) == 4, "evidence file set drifted")
    for item in manifest["files"]:
        _require(set(item) == {"path", "sha256", "bytes"} and isinstance(item["sha256"], str) and isinstance(item["bytes"], int), "manifest entry schema drifted")
        path = package / item["path"]
        _require(path.is_file() and not path.is_symlink() and path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"], "evidence checksum/size mismatch")
    docs = {name: json.loads((package / name).read_text(encoding="utf-8")) for name in expected_names}
    exact_keys = {
        "contract.json": {"schema_version", "source_type", "openapi_url", "openapi_sha256", "download_endpoint_template", "download_method", "documented_security_note", "status_endpoint_template", "status_schema_fields", "terminal_states", "nonterminal_states", "projection_decision", "route_cap_evidence"},
        "count_selection.json": {"schema_version", "source_type", "selector_calls", "selector_calls_allowed_max", "species", "accepted_parent_concept", "accepted_concept_query", "year_attempted", "scope", "pageSize", "start", "facet", "facet_basis", "disableAllQualityFilters", "http_status", "http_status_basis", "selected_count", "occurrence_rows_retained", "facet_rows_retained", "coordinates_retained", "raw_file", "raw_sha256", "raw_bytes"},
        "submission.json": {"schema_version", "source_type", "request_ledger_basis", "request_ledger", "attempted_get_requests", "jobs_created", "status_polls", "cancellations", "archives_downloaded", "archive_rows", "http_status", "http_status_basis", "raw_request_retained", "raw_response_body_retained", "raw_response_headers_retained", "status_handle_retained", "credential_mode", "post_requests", "retry_requests", "alternate_host_requests", "notification_requested", "doi_requested", "auth_or_jwt_used", "api_key_used", "scope_match_verified", "interpretation"},
        "review.json": {"schema_version", "source_type", "readiness", "route_above_5000", "production_operability", "selector", "lifecycle", "archive_inventory", "raw_replay", "documented_fact", "observed_fact", "inference", "not_complete"},
    }
    for name, doc in docs.items():
        _require(set(doc) == exact_keys[name], f"{name} schema drifted")
        _scan_private(doc, path=name, allow_public_fields=name == "contract.json")
    contract, count, submission, review = (docs[n] for n in ("contract.json", "count_selection.json", "submission.json", "review.json"))
    _require(contract["openapi_url"] == OPENAPI_URL and contract["openapi_sha256"] == "4d90c83d21122c482a5ed97344033e8aaa47e3a3c6315eaeac5303bdecc9407c" and contract["download_endpoint_template"] == DOWNLOAD_ENDPOINT and contract["status_endpoint_template"] == STATUS_ENDPOINT_TEMPLATE, "contract source/endpoint drifted")
    _require(contract["status_schema_fields"] == EXPECTED_STATUS_SCHEMA_FIELDS and contract["projection_decision"] == EXPECTED_PROJECTION_DECISION, "contract schema/projection drifted")
    _require(contract["terminal_states"] == TERMINAL_STATES and contract["nonterminal_states"] == NONTERMINAL_STATES and contract["route_cap_evidence"] == {"status": "documented_architecture_unverified_operability", "search_depth_cap": 5000, "offline_source_default_maximum": 100000000, "production_operability": "unverified_http_403", "deployed_offline_maximum": "unknown", "openapi_source": OPENAPI_URL, "source_commit": "bcfb37661008dce5d3e532258458eb72d03e7530", "source_anchors": ["https://raw.githubusercontent.com/AtlasOfLivingAustralia/biocache-service/bcfb37661008dce5d3e532258458eb72d03e7530/src/main/java/au/org/ala/biocache/web/OccurrenceController.java#L874-L900", "https://raw.githubusercontent.com/AtlasOfLivingAustralia/biocache-service/bcfb37661008dce5d3e532258458eb72d03e7530/src/main/java/au/org/ala/biocache/service/DownloadService.java#L232-L239"], "interpretation": "Offline architecture is documented separately from search, but the deployed maximum and production operability remain unverified."}, "contract lifecycle/cap drifted")
    _require(count["selector_calls"] == 1 and count["selector_calls_allowed_max"] == 3 and count["selected_count"] == 17 and count["http_status"] == 200 and count["http_status_basis"] == "operator_reported_not_independently_reconstructible", "selector evidence drifted")
    _require(count["species"] == "pseudocheirus_peregrinus" and count["accepted_parent_concept"] == PARENT_CONCEPTS["pseudocheirus_peregrinus"] and count["accepted_concept_query"] == "taxonConceptID:<accepted-parent-concept>" and count["year_attempted"] == 2001 and count["scope"] == {"stateProvince": "Tasmania", "year": 2001} and count["pageSize"] == 0 and count["start"] == 0 and count["facet"] is False and count["facet_basis"] == "operator_reported_request_parameter_not_echoed_by_raw" and count["disableAllQualityFilters"] is True and count["raw_sha256"] == RAW_SHA256 and count["raw_bytes"] == RAW_BYTES, "selector identity/scope/raw binding drifted")
    _require(submission["request_ledger_basis"] == "operator_reported_sanitized_after_fact" and submission["attempted_get_requests"] == 1 and submission["jobs_created"] == 0 and submission["status_polls"] == 0 and submission["cancellations"] == 0 and submission["archives_downloaded"] == 0 and submission["archive_rows"] == 0 and submission["http_status"] == 403 and submission["http_status_basis"] == "operator_reported_causality_unexplained", "submission lifecycle/status drifted")
    _require(submission["post_requests"] == 0 and submission["retry_requests"] == 0 and submission["alternate_host_requests"] == 0 and submission["auth_or_jwt_used"] is False and submission["api_key_used"] is False and submission["notification_requested"] is False and submission["doi_requested"] is False and submission["raw_request_retained"] is False and submission["raw_response_body_retained"] is False and submission["raw_response_headers_retained"] is False and submission["status_handle_retained"] is False and submission["credential_mode"] == "runtime_registered_email_only" and submission["scope_match_verified"] is False, "submission safety totals drifted")
    _require(submission["request_ledger"] == {"endpoint_template": DOWNLOAD_ENDPOINT, "method": "GET", "query": "accepted parent concept", "filters": ["stateProvince:Tasmania", "year:[2001 TO 2001]"], "quality": {"disableAllQualityFilters": True, "qa": "none"}, "projection": {"fields": REQUIRED_RECORD_FIELDS, "fl": None, "includeMultivalues": False, "extra": None}, "format": {"fileType": "csv", "sep": ",", "dwcHeaders": False, "includeMisc": False}, "reason_code": "scientific-research-validation", "runtime_registered_email_supplied": True}, "request ledger drifted")
    _require(review["readiness"] == BLOCKED and review["route_above_5000"] == "documented_architecture_unverified_operability" and review["production_operability"] == "unverified_http_403", "review state drifted")
    _require(review["lifecycle"] == {"jobs": 0, "polls": 0, "cancellations": 0, "archives": 0, "rows": 0} and review["archive_inventory"] == {"downloaded": False, "members": 0, "csv_rows": 0}, "review lifecycle drifted")
    if raw_dir is None:
        return {"readiness": TRACKED_ONLY, "raw_replay_required": True, "selected_count": 17, "jobs_created": 0}
    _replay_selector_raw(Path(raw_dir), plan, count)
    return {"readiness": BLOCKED, "raw_replay_required": False, "selected_count": 17, "jobs_created": 0}


def validate_archive_path(path: Path, *, expected_host: str = "api.ala.org.au") -> None:
    """Fail closed on archive path, symlink, size, and host hazards."""
    _require(path.is_file() and not path.is_symlink(), "archive missing, symlinked, or not a file")
    _require(path.stat().st_size <= MAX_ARCHIVE_BYTES, "archive exceeds 20 MB safety cap")
    _require(expected_host in OFFICIAL_HOSTS, "unexpected archive host")
