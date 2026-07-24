"""Fail-closed execution and raw replay for the Goal 015 Galah pilot.

The validator surface is standard-library only. Galah and pandas are imported
only by ``run_pilot`` so tracked-only evidence checks do not require runtime
acquisition dependencies.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import os
import re
import signal
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GalahPilotValidationError(ValueError):
    """Raised when Goal 015 execution or evidence fails closed."""


class _PilotStop(Exception):
    """Internal sanitized stop signal."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


GALAH_VERSION = "0.13.3"
CORRECT_DOWNLOAD_ENDPOINT = (
    "https://api.ala.org.au/occurrences/occurrences/offline/download"
)
MALFORMED_GOAL014_ENDPOINT = (
    "https://api.ala.org.au/occurrences/offline/download"
)
SPECIES_ID = "pseudocheirus_peregrinus"
SCIENTIFIC_NAME = "Pseudocheirus peregrinus"
ACCEPTED_CONCEPT = (
    "https://biodiversity.org.au/afd/taxa/"
    "003decd6-ec3d-468e-909d-da396a6dd1f6"
)
FILTERS = ["stateProvince=Tasmania", "year=2001"]
PROJECTION_FIELDS = [
    "occurrenceID",
    "dataResourceUid",
    "dataResourceName",
    "datasetID",
    "datasetName",
    "eventDate",
    "year",
    "decimalLatitude",
    "decimalLongitude",
    "coordinateUncertaintyInMeters",
    "coordinatePrecision",
    "raw_scientificName",
    "raw_taxonConceptID",
    "scientificName",
    "taxonConceptID",
    "acceptedNameUsage",
    "acceptedNameUsageID",
    "taxonRank",
    "assertions",
    "license",
]
CORE_FIELDS = [field for field in PROJECTION_FIELDS if field != "assertions"]
RETURNED_FIELD_ALIASES = {"license": "dcterms:license"}
RETURNED_CORE_FIELDS = [
    RETURNED_FIELD_ALIASES.get(field, field) for field in CORE_FIELDS
]
EXPECTED_COUNT = 17
MAX_RECORDS = 100
OCCURRENCE_TIMEOUT_SECONDS = 15 * 60
COUNT_RAW_FILENAME = "galah-count.csv"
OCCURRENCE_RAW_FILENAME = "galah-occurrences.csv"
TRACKED_FILENAMES = [
    "support_resolution.json",
    "run_summary.json",
    "review.json",
]
TRACKED_ONLY = "galah_pilot_tracked_evidence_valid_raw_replay_required"
PASS = "galah_route_usable_for_later_acquisition_design"
EMAIL_RE = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GalahPilotValidationError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exact_keys(value: Any, expected: set[str], label: str) -> None:
    _require(isinstance(value, dict) and set(value) == expected, f"{label} shape drifted")


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact bounded, unauthenticated Goal 015 execution plan."""

    _exact_keys(
        plan,
        {
            "schema_version",
            "goal_id",
            "package",
            "query",
            "caps",
            "configuration",
            "projection",
            "raw",
            "evidence",
        },
        "plan root",
    )
    _require(
        plan["schema_version"] == "1.0"
        and plan["goal_id"] == "goal015-ala-galah-route-gate-2026-07-24",
        "plan identity drifted",
    )
    package = plan["package"]
    _exact_keys(
        package, {"name", "version", "download_endpoint"}, "package contract"
    )
    _require(
        package
        == {
            "name": "galah-python",
            "version": GALAH_VERSION,
            "download_endpoint": CORRECT_DOWNLOAD_ENDPOINT,
        },
        "package version or route drifted",
    )
    _require(
        package["download_endpoint"] != MALFORMED_GOAL014_ENDPOINT,
        "single-occurrences download endpoint is forbidden",
    )

    query = plan["query"]
    _exact_keys(
        query,
        {
            "species_id",
            "scientific_name",
            "accepted_concept",
            "filters",
            "use_data_profile",
        },
        "query contract",
    )
    _require(
        query
        == {
            "species_id": SPECIES_ID,
            "scientific_name": SCIENTIFIC_NAME,
            "accepted_concept": ACCEPTED_CONCEPT,
            "filters": FILTERS,
            "use_data_profile": False,
        },
        "species, scope, or broad-intake query drifted",
    )

    caps = plan["caps"]
    _exact_keys(
        caps,
        {
            "max_count_calls",
            "max_occurrence_calls",
            "expected_count",
            "max_records",
            "occurrence_timeout_seconds",
        },
        "call caps",
    )
    _require(
        caps
        == {
            "max_count_calls": 1,
            "max_occurrence_calls": 1,
            "expected_count": EXPECTED_COUNT,
            "max_records": MAX_RECORDS,
            "occurrence_timeout_seconds": OCCURRENCE_TIMEOUT_SECONDS,
        },
        "live call, count, or timeout cap drifted",
    )

    configuration = plan["configuration"]
    _exact_keys(
        configuration,
        {
            "email_env",
            "atlas",
            "email_notify",
            "reason",
            "authenticate",
            "data_profile",
            "verbose",
            "timeout",
            "config_storage",
        },
        "configuration",
    )
    _require(
        configuration
        == {
            "email_env": "ALA_DOWNLOAD_EMAIL",
            "atlas": "Australia",
            "email_notify": False,
            "reason": 4,
            "authenticate": False,
            "data_profile": None,
            "verbose": False,
            "timeout": 600,
            "config_storage": "temporary_explicit_file",
        },
        "authentication, verbosity, or temporary config controls drifted",
    )

    projection = plan["projection"]
    _exact_keys(
        projection,
        {
            "fields",
            "mint_doi",
            "dwc_headers",
            "qa",
            "returned_field_aliases",
            "field_semantics",
        },
        "projection",
    )
    _require(
        projection
        == {
            "fields": PROJECTION_FIELDS,
            "mint_doi": False,
            "dwc_headers": True,
            "qa": "includeall_due_to_assertions_request",
            "returned_field_aliases": RETURNED_FIELD_ALIASES,
            "field_semantics": (
                "galah returns requested license as dcterms:license under "
                "dwcHeaders=true, may expand assertion columns, and sets "
                "qa=includeall when assertions are requested"
            ),
        },
        "projection or package field semantics drifted",
    )

    raw = plan["raw"]
    _exact_keys(
        raw,
        {
            "directory",
            "files",
            "representation",
            "provider_zip_retained",
            "tracked",
        },
        "raw contract",
    )
    _require(
        raw
        == {
            "directory": (
                "data/raw/ala/goal015-galah-pilot/2026-07-24"
            ),
            "files": [COUNT_RAW_FILENAME, OCCURRENCE_RAW_FILENAME],
            "representation": (
                "immediate_csv_serializations_of_galah_returned_dataframes"
            ),
            "provider_zip_retained": False,
            "tracked": False,
        },
        "raw footprint or representation drifted",
    )

    evidence = plan["evidence"]
    _exact_keys(
        evidence,
        {
            "directory",
            "files",
            "raw_replay_required_for_pass",
            "tracked_rows",
        },
        "evidence contract",
    )
    _require(
        evidence
        == {
            "directory": "evidence/ala_galah_pilot/2026-07-24",
            "files": TRACKED_FILENAMES,
            "raw_replay_required_for_pass": True,
            "tracked_rows": 0,
        },
        "evidence footprint or raw replay rule drifted",
    )
    return {
        "expected_count": EXPECTED_COUNT,
        "max_records": MAX_RECORDS,
        "projection_fields": len(PROJECTION_FIELDS),
    }


def _required_core_fields_present(columns: list[str]) -> bool:
    """Require every literal core header except the one explicit DWC alias."""

    return (
        set(RETURNED_CORE_FIELDS).issubset(columns)
        and "license" not in columns
        and "dcterms:license" in columns
    )


def _assertion_columns(columns: list[str]) -> list[str]:
    """Return package-expanded assertion headers without alias heuristics."""

    return [
        column
        for column in columns
        if column == "assertions" or column not in RETURNED_CORE_FIELDS
    ]


def _utc(value: datetime) -> str:
    _require(
        value.tzinfo is not None and value.utcoffset() is not None,
        "runtime clock must be timezone-aware",
    )
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _frame_metadata(
    frame: Any, path: Path, acquired_at_utc: str
) -> dict[str, Any]:
    columns = [str(column) for column in frame.columns]
    dtypes = {str(name): str(dtype) for name, dtype in frame.dtypes.items()}
    return {
        "path": path.name,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "rows": len(frame),
        "columns": len(columns),
        "column_names": columns,
        "parsed_dtypes": dtypes,
        "acquired_at_utc": acquired_at_utc,
    }


def _write_frame(
    frame: Any,
    path: Path,
    *,
    acquired_at_utc: str,
    runtime_account: str,
) -> dict[str, Any]:
    if path.exists() or path.is_symlink():
        raise _PilotStop("raw_footprint_conflict")
    try:
        frame.to_csv(path, index=False, lineterminator="\n")
    except Exception:
        raise _PilotStop("raw_serialization_error") from None
    if not path.is_file() or path.is_symlink():
        raise _PilotStop("raw_serialization_error")
    payload = path.read_bytes()
    if runtime_account.encode("utf-8") in payload:
        path.unlink()
        raise _PilotStop("runtime_account_leak")
    return _frame_metadata(frame, path, acquired_at_utc)


def _call_with_alarm(call: Callable[[], Any], seconds: int) -> Any:
    """Bound Galah's polling loop outside the package implementation."""

    if (
        not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        raise _PilotStop("external_timeout_unavailable")

    def handle_timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return call()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _support_resolution() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "source_type": "user_reported_external_ala_support_reply",
        "reported_facts": [
            (
                "A registered account email is sufficient for ordinary "
                "occurrence downloads."
            ),
            (
                "API token, JWT, or Bearer authentication is not required "
                "for ordinary occurrence downloads."
            ),
            (
                "Authentication is relevant only to separately approved "
                "sensitive or unobfuscated access."
            ),
            "The supported occurrence-download endpoint is current.",
            (
                "ALA support recommended galah-python, and the reply author "
                "maintains that client."
            ),
        ],
        "inference": (
            "Goal 014's malformed single-occurrences URL likely caused its "
            "HTTP 403."
        ),
        "causal_limit": (
            "That route explanation is an inference, not an independently "
            "reproduced causal diagnosis of the historical response."
        ),
    }


def _run_summary(
    plan: dict[str, Any],
    *,
    outcome: str,
    stop_reason: str | None,
    started_at_utc: str,
    completed_at_utc: str,
    elapsed_seconds: float,
    count_calls: int,
    occurrence_calls: int,
    selected_count: int | None,
    returned_rows: int | None,
    raw_artifacts: list[dict[str, Any]],
    required_core_fields_present: bool,
    assertion_information_identifiable: bool,
    offline_repair: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "goal_id": plan["goal_id"],
        "source_type": "galah_python_parsed_dataframes",
        "outcome": outcome,
        "stop_reason": stop_reason,
        "started_at_utc": started_at_utc,
        "completed_at_utc": completed_at_utc,
        "elapsed_seconds": elapsed_seconds,
        "package": {
            "name": plan["package"]["name"],
            "version": plan["package"]["version"],
        },
        "route": {
            "endpoint": plan["package"]["download_endpoint"],
            "method": "GET",
            "ownership": "galah_python_node_config",
        },
        "query": {
            "species_id": plan["query"]["species_id"],
            "scientific_name": plan["query"]["scientific_name"],
            "accepted_concept": plan["query"]["accepted_concept"],
            "filters": plan["query"]["filters"],
            "expected_count": plan["caps"]["expected_count"],
            "selected_count": selected_count,
        },
        "settings": {
            "runtime_account_supplied": True,
            "email_notify": plan["configuration"]["email_notify"],
            "reason": plan["configuration"]["reason"],
            "authenticate": plan["configuration"]["authenticate"],
            "mint_doi": plan["projection"]["mint_doi"],
            "use_data_profile": plan["query"]["use_data_profile"],
            "data_profile": plan["configuration"]["data_profile"],
            "verbose": plan["configuration"]["verbose"],
            "timeout": plan["configuration"]["timeout"],
            "config_storage": plan["configuration"]["config_storage"],
            "temporary_config_destroyed": True,
        },
        "package_semantics": {
            "disable_all_quality_filters_expected": True,
            "dwc_headers": plan["projection"]["dwc_headers"],
            "qa": plan["projection"]["qa"],
            "assertions_requested": True,
            "returned_field_aliases": plan["projection"][
                "returned_field_aliases"
            ],
            "provider_zip_retained": False,
            "raw_representation": plan["raw"]["representation"],
        },
        "offline_repair": offline_repair
        or {
            "performed": False,
            "initial_stop_reason": None,
            "basis": "not_required",
            "second_live_attempt": False,
            "completed_at_utc": None,
        },
        "calls": {
            "atlas_counts": count_calls,
            "atlas_occurrences": occurrence_calls,
        },
        "returned_rows": returned_rows,
        "required_core_fields_present": required_core_fields_present,
        "assertion_information_identifiable": (
            assertion_information_identifiable
        ),
        "raw_artifacts": raw_artifacts,
    }


def _review(
    *,
    outcome: str,
    stop_reason: str | None,
    selected_count: int | None,
    returned_rows: int | None,
    returned_columns: int | None,
    required_core_fields_present: bool,
    assertion_information_identifiable: bool,
) -> dict[str, Any]:
    completed = outcome == "completed"
    return {
        "schema_version": "1.0",
        "source_type": "goal015_route_gate_review",
        "outcome": outcome,
        "readiness": (
            TRACKED_ONLY if completed else f"blocked_{stop_reason}"
        ),
        "raw_replay": (
            "required_for_usable_route_decision"
            if completed
            else "required_to_interpret_any_preserved_raw_artifacts"
        ),
        "observations": {
            "count": selected_count,
            "returned_rows": returned_rows,
            "returned_columns": returned_columns,
            "required_core_fields_present": required_core_fields_present,
            "assertion_information_identifiable": (
                assertion_information_identifiable
            ),
        },
        "conclusion": (
            "The route-correct unauthenticated Galah pilot completed; an "
            "exact local raw replay is required before the route is judged "
            "usable for later acquisition design."
            if completed
            else (
                "The single bounded Galah pilot stopped without a second "
                "live attempt."
            )
        ),
        "limitations": [
            (
                "Galah exposes a pandas-parsed table rather than the "
                "provider ZIP; the ignored CSV files are the earliest "
                "artifacts available to this pilot."
            ),
            (
                "Requesting assertions sets qa=includeall and may expand "
                "assertion columns; galah also sets dwcHeaders=true."
            ),
            (
                "Under dwcHeaders=true, the requested license field is "
                "returned under the one explicit alias dcterms:license."
            ),
        ],
        "not_complete": [
            "full nine-species acquisition",
            "normalization or modelling",
            "camera-data work",
            "DOI minting",
            "sensitive or unobfuscated access",
        ],
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _write_evidence(
    evidence_dir: Path,
    support: dict[str, Any],
    summary: dict[str, Any],
    review: dict[str, Any],
) -> None:
    values = {
        "support_resolution.json": support,
        "run_summary.json": summary,
        "review.json": review,
    }
    for name in TRACKED_FILENAMES:
        _write_json(evidence_dir / name, values[name])
    manifest = {
        "schema_version": "1.0",
        "files": [
            {
                "path": name,
                "sha256": sha256(evidence_dir / name),
                "bytes": (evidence_dir / name).stat().st_size,
            }
            for name in TRACKED_FILENAMES
        ],
    }
    _write_json(evidence_dir / "manifest.json", manifest)


def run_pilot(
    plan_path: Path,
    raw_dir: Path,
    evidence_dir: Path,
    *,
    galah_module: Any | None = None,
    pandas_module: Any | None = None,
    environ: Mapping[str, str] | None = None,
    now_fn: Callable[[], datetime] | None = None,
    occurrence_call_runner: Callable[[Callable[[], Any], int], Any] | None = None,
) -> dict[str, Any]:
    """Execute the single bounded count and conditional occurrence calls."""

    plan_path = Path(plan_path)
    raw_dir = Path(raw_dir)
    evidence_dir = Path(evidence_dir)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validate_plan(plan)
    environ = os.environ if environ is None else environ
    runtime_account = environ.get(plan["configuration"]["email_env"], "")
    _require(
        isinstance(runtime_account, str) and bool(runtime_account.strip()),
        "missing_runtime_account",
    )

    if galah_module is None:
        galah_module = importlib.import_module("galah")
    if pandas_module is None:
        pandas_module = importlib.import_module("pandas")
    _require(
        getattr(galah_module, "__version__", None) == GALAH_VERSION,
        "galah_version_drift",
    )
    dataframe_type = getattr(pandas_module, "DataFrame", None)
    _require(dataframe_type is not None, "pandas_dataframe_type_unavailable")

    _require(
        not raw_dir.exists() and not raw_dir.is_symlink(),
        "raw_directory_must_be_new",
    )
    _require(
        not evidence_dir.exists() and not evidence_dir.is_symlink(),
        "evidence_directory_must_be_new",
    )
    raw_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    occurrence_call_runner = occurrence_call_runner or _call_with_alarm
    started = now_fn()
    started_at_utc = _utc(started)
    count_calls = 0
    occurrence_calls = 0
    selected_count: int | None = None
    returned_rows: int | None = None
    raw_artifacts: list[dict[str, Any]] = []
    required_core_fields_present = False
    assertion_information_identifiable = False
    stop_reason: str | None = None

    try:
        with tempfile.TemporaryDirectory(prefix="dsdm-goal015-galah-") as temp:
            config_path = Path(temp) / "config.ini"
            config_path.touch(exist_ok=False)
            try:
                galah_module.galah_config(
                    atlas=plan["configuration"]["atlas"],
                    email=runtime_account,
                    email_notify=plan["configuration"]["email_notify"],
                    reason=plan["configuration"]["reason"],
                    authenticate=plan["configuration"]["authenticate"],
                    data_profile=plan["configuration"]["data_profile"],
                    verbose=plan["configuration"]["verbose"],
                    timeout=plan["configuration"]["timeout"],
                    config_file=str(config_path),
                )
            except Exception:
                raise _PilotStop("runtime_or_access_error") from None

            query_args = {
                "identifiers": plan["query"]["accepted_concept"],
                "filters": list(plan["query"]["filters"]),
                "use_data_profile": plan["query"]["use_data_profile"],
                "config_file": str(config_path),
            }
            count_calls += 1
            try:
                count_table = galah_module.atlas_counts(**query_args)
            except Exception:
                raise _PilotStop("runtime_or_access_error") from None
            if not isinstance(count_table, dataframe_type):
                raise _PilotStop("wrong_return_type")
            count_acquired = _utc(now_fn())
            raw_artifacts.append(
                _write_frame(
                    count_table,
                    raw_dir / COUNT_RAW_FILENAME,
                    acquired_at_utc=count_acquired,
                    runtime_account=runtime_account,
                )
            )
            if list(count_table.columns) != ["totalRecords"] or len(count_table) != 1:
                raise _PilotStop("material_schema_failure")
            count_records = count_table.to_dict(orient="records")
            count_value = count_records[0]["totalRecords"]
            if isinstance(count_value, bool):
                raise _PilotStop("material_schema_failure")
            try:
                selected_count = int(count_value)
            except (TypeError, ValueError, OverflowError):
                raise _PilotStop("material_schema_failure") from None
            if count_value != selected_count:
                raise _PilotStop("material_schema_failure")
            if not (
                selected_count == EXPECTED_COUNT
                and 1 <= selected_count <= plan["caps"]["max_records"]
            ):
                raise _PilotStop("count_drift")

            occurrence_calls += 1
            try:
                occurrences = occurrence_call_runner(
                    lambda: galah_module.atlas_occurrences(
                        **query_args,
                        fields=list(plan["projection"]["fields"]),
                        mint_doi=plan["projection"]["mint_doi"],
                    ),
                    plan["caps"]["occurrence_timeout_seconds"],
                )
            except TimeoutError:
                raise _PilotStop("timeout") from None
            except _PilotStop:
                raise
            except Exception:
                raise _PilotStop("runtime_or_access_error") from None
            if not isinstance(occurrences, dataframe_type):
                raise _PilotStop("wrong_return_type")
            occurrence_acquired = _utc(now_fn())
            raw_artifacts.append(
                _write_frame(
                    occurrences,
                    raw_dir / OCCURRENCE_RAW_FILENAME,
                    acquired_at_utc=occurrence_acquired,
                    runtime_account=runtime_account,
                )
            )
            returned_rows = len(occurrences)
            if returned_rows != selected_count:
                raise _PilotStop("row_count_mismatch")
            returned_columns = [str(column) for column in occurrences.columns]
            if len(returned_columns) != len(set(returned_columns)):
                raise _PilotStop("material_schema_failure")
            required_core_fields_present = _required_core_fields_present(
                returned_columns
            )
            assertion_information_identifiable = bool(
                _assertion_columns(returned_columns)
            )
            if (
                not required_core_fields_present
                or not assertion_information_identifiable
            ):
                raise _PilotStop("material_schema_failure")
    except _PilotStop as error:
        stop_reason = error.reason

    completed = now_fn()
    completed_at_utc = _utc(completed)
    elapsed_seconds = max(0.0, (completed - started).total_seconds())
    outcome = "blocked" if stop_reason is not None else "completed"
    returned_columns_count = (
        raw_artifacts[-1]["columns"]
        if len(raw_artifacts) == 2
        else None
    )
    summary = _run_summary(
        plan,
        outcome=outcome,
        stop_reason=stop_reason,
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        elapsed_seconds=elapsed_seconds,
        count_calls=count_calls,
        occurrence_calls=occurrence_calls,
        selected_count=selected_count,
        returned_rows=returned_rows,
        raw_artifacts=raw_artifacts,
        required_core_fields_present=required_core_fields_present,
        assertion_information_identifiable=(
            assertion_information_identifiable
        ),
    )
    review = _review(
        outcome=outcome,
        stop_reason=stop_reason,
        selected_count=selected_count,
        returned_rows=returned_rows,
        returned_columns=returned_columns_count,
        required_core_fields_present=required_core_fields_present,
        assertion_information_identifiable=(
            assertion_information_identifiable
        ),
    )
    _write_evidence(evidence_dir, _support_resolution(), summary, review)
    if stop_reason is not None:
        raise GalahPilotValidationError(stop_reason)
    return validate_evidence_package(evidence_dir, plan, raw_dir=raw_dir)


def _scan_tracked(value: Any, *, path: str = "root") -> None:
    forbidden_keys = {
        "email",
        "contact",
        "userid",
        "jobid",
        "statusurl",
        "downloadurl",
        "cancelurl",
        "token",
        "jwt",
        "authorization",
        "occurrences",
        "rowpayload",
        "rowsretained",
        "coordinatevalues",
        "eventdates",
        "eventtimestamps",
    }
    if isinstance(value, str):
        _require(not EMAIL_RE.search(value), f"contact leakage at {path}")
        _require(
            not re.search(r"(?i)\bBearer\s+\S{20,}", value),
            f"authorization leakage at {path}",
        )
        _require(
            not re.search(r"\beyJ[A-Za-z0-9_-]{12,}\.", value),
            f"JWT-like leakage at {path}",
        )
    elif isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            _require(
                normalized not in forbidden_keys,
                f"private or row-level key at {path}.{key}",
            )
            _scan_tracked(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_tracked(item, path=f"{path}[{index}]")


def _validate_artifact_metadata(
    artifact: dict[str, Any], expected_path: str
) -> None:
    _exact_keys(
        artifact,
        {
            "path",
            "sha256",
            "bytes",
            "rows",
            "columns",
            "column_names",
            "parsed_dtypes",
            "acquired_at_utc",
        },
        f"raw artifact {expected_path}",
    )
    _require(artifact["path"] == expected_path, "raw artifact path drifted")
    _require(
        isinstance(artifact["sha256"], str)
        and SHA256_RE.fullmatch(artifact["sha256"]) is not None
        and isinstance(artifact["bytes"], int)
        and artifact["bytes"] > 0,
        "raw artifact checksum or size malformed",
    )
    _require(
        isinstance(artifact["rows"], int)
        and artifact["rows"] >= 0
        and isinstance(artifact["columns"], int)
        and artifact["columns"] > 0
        and isinstance(artifact["column_names"], list)
        and artifact["columns"] == len(artifact["column_names"])
        and len(set(artifact["column_names"])) == artifact["columns"],
        "raw artifact dimensions or columns malformed",
    )
    _require(
        isinstance(artifact["parsed_dtypes"], dict)
        and set(artifact["parsed_dtypes"]) == set(artifact["column_names"])
        and all(
            isinstance(name, str) and isinstance(dtype, str)
            for name, dtype in artifact["parsed_dtypes"].items()
        ),
        "parsed dtype inventory drifted",
    )
    _require(
        isinstance(artifact["acquired_at_utc"], str)
        and artifact["acquired_at_utc"].endswith("Z"),
        "acquisition UTC missing",
    )


def _validate_tracked_docs(
    support: dict[str, Any],
    summary: dict[str, Any],
    review: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    _require(support == _support_resolution(), "support resolution drifted")
    _exact_keys(
        summary,
        {
            "schema_version",
            "goal_id",
            "source_type",
            "outcome",
            "stop_reason",
            "started_at_utc",
            "completed_at_utc",
            "elapsed_seconds",
            "package",
            "route",
            "query",
            "settings",
            "package_semantics",
            "offline_repair",
            "calls",
            "returned_rows",
            "required_core_fields_present",
            "assertion_information_identifiable",
            "raw_artifacts",
        },
        "run summary",
    )
    _require(
        summary["schema_version"] == "1.0"
        and summary["goal_id"] == plan["goal_id"]
        and summary["source_type"] == "galah_python_parsed_dataframes",
        "run identity drifted",
    )
    _require(
        summary["package"]
        == {"name": "galah-python", "version": GALAH_VERSION},
        "run package drifted",
    )
    _require(
        summary["route"]
        == {
            "endpoint": CORRECT_DOWNLOAD_ENDPOINT,
            "method": "GET",
            "ownership": "galah_python_node_config",
        },
        "run route drifted",
    )
    _require(
        summary["query"]
        == {
            "species_id": SPECIES_ID,
            "scientific_name": SCIENTIFIC_NAME,
            "accepted_concept": ACCEPTED_CONCEPT,
            "filters": FILTERS,
            "expected_count": EXPECTED_COUNT,
            "selected_count": summary["query"]["selected_count"],
        },
        "run query identity drifted",
    )
    _require(
        summary["settings"]
        == {
            "runtime_account_supplied": True,
            "email_notify": False,
            "reason": 4,
            "authenticate": False,
            "mint_doi": False,
            "use_data_profile": False,
            "data_profile": None,
            "verbose": False,
            "timeout": 600,
            "config_storage": "temporary_explicit_file",
            "temporary_config_destroyed": True,
        },
        "run settings drifted",
    )
    _require(
        summary["package_semantics"]
        == {
            "disable_all_quality_filters_expected": True,
            "dwc_headers": True,
            "qa": "includeall_due_to_assertions_request",
            "assertions_requested": True,
            "returned_field_aliases": RETURNED_FIELD_ALIASES,
            "provider_zip_retained": False,
            "raw_representation": plan["raw"]["representation"],
        },
        "package semantics drifted",
    )
    _exact_keys(
        summary["offline_repair"],
        {
            "performed",
            "initial_stop_reason",
            "basis",
            "second_live_attempt",
            "completed_at_utc",
        },
        "offline repair ledger",
    )
    repair = summary["offline_repair"]
    _require(
        repair["second_live_attempt"] is False
        and (
            repair
            == {
                "performed": False,
                "initial_stop_reason": None,
                "basis": "not_required",
                "second_live_attempt": False,
                "completed_at_utc": None,
            }
            or (
                repair["performed"] is True
                and repair["initial_stop_reason"]
                == "material_schema_failure"
                and repair["basis"]
                == (
                    "frozen_raw_header_replay_of_explicit_"
                    "dwc_license_alias"
                )
                and isinstance(repair["completed_at_utc"], str)
                and repair["completed_at_utc"].endswith("Z")
            )
        ),
        "offline repair ledger drifted",
    )
    _exact_keys(
        summary["calls"], {"atlas_counts", "atlas_occurrences"}, "call ledger"
    )
    _require(
        0 <= summary["calls"]["atlas_counts"] <= 1
        and 0 <= summary["calls"]["atlas_occurrences"] <= 1,
        "live call cap exceeded",
    )
    _require(
        isinstance(summary["elapsed_seconds"], (int, float))
        and not isinstance(summary["elapsed_seconds"], bool)
        and summary["elapsed_seconds"] >= 0
        and summary["started_at_utc"].endswith("Z")
        and summary["completed_at_utc"].endswith("Z"),
        "run timing evidence malformed",
    )
    _require(
        isinstance(summary["raw_artifacts"], list)
        and len(summary["raw_artifacts"]) <= 2,
        "raw artifact ledger malformed",
    )
    for index, artifact in enumerate(summary["raw_artifacts"]):
        _validate_artifact_metadata(
            artifact, plan["raw"]["files"][index]
        )

    _exact_keys(
        review,
        {
            "schema_version",
            "source_type",
            "outcome",
            "readiness",
            "raw_replay",
            "observations",
            "conclusion",
            "limitations",
            "not_complete",
        },
        "review",
    )
    _require(
        review["schema_version"] == "1.0"
        and review["source_type"] == "goal015_route_gate_review"
        and review["outcome"] == summary["outcome"],
        "review identity drifted",
    )
    _exact_keys(
        review["observations"],
        {
            "count",
            "returned_rows",
            "returned_columns",
            "required_core_fields_present",
            "assertion_information_identifiable",
        },
        "review observations",
    )
    _require(
        review["observations"]["count"] == summary["query"]["selected_count"]
        and review["observations"]["returned_rows"] == summary["returned_rows"]
        and review["observations"]["required_core_fields_present"]
        == summary["required_core_fields_present"]
        and review["observations"]["assertion_information_identifiable"]
        == summary["assertion_information_identifiable"],
        "review observations do not bind run summary",
    )
    if summary["outcome"] == "completed":
        _require(summary["stop_reason"] is None, "completed run has stop reason")
        _require(
            summary["calls"]
            == {"atlas_counts": 1, "atlas_occurrences": 1}
            and summary["query"]["selected_count"] == EXPECTED_COUNT
            and summary["returned_rows"] == EXPECTED_COUNT
            and summary["required_core_fields_present"] is True
            and summary["assertion_information_identifiable"] is True
            and len(summary["raw_artifacts"]) == 2,
            "completed run controls or dimensions drifted",
        )
        count_artifact, occurrence_artifact = summary["raw_artifacts"]
        _require(
            count_artifact["rows"] == 1
            and count_artifact["column_names"] == ["totalRecords"],
            "count artifact schema drifted",
        )
        _require(
            occurrence_artifact["rows"] == EXPECTED_COUNT
            and _required_core_fields_present(
                occurrence_artifact["column_names"]
            )
            and bool(
                _assertion_columns(occurrence_artifact["column_names"])
            ),
            "occurrence core or assertion schema drifted",
        )
        _require(
            review["readiness"] == TRACKED_ONLY
            and review["raw_replay"]
            == "required_for_usable_route_decision",
            "tracked evidence claimed pass without raw replay",
        )
    else:
        _require(
            summary["outcome"] == "blocked"
            and isinstance(summary["stop_reason"], str)
            and review["readiness"]
            == f"blocked_{summary['stop_reason']}",
            "blocked run state drifted",
        )


def _replay_raw(
    raw_dir: Path,
    summary: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    _require(raw_dir.is_dir() and not raw_dir.is_symlink(), "raw directory missing")
    entries = list(raw_dir.iterdir())
    _require(
        {entry.name for entry in entries} == set(plan["raw"]["files"])
        and len(entries) == 2,
        "raw directory footprint drifted",
    )
    artifacts = {
        artifact["path"]: artifact for artifact in summary["raw_artifacts"]
    }
    for entry in entries:
        artifact = artifacts.get(entry.name)
        _require(
            artifact is not None
            and entry.is_file()
            and not entry.is_symlink()
            and entry.stat().st_size == artifact["bytes"]
            and sha256(entry) == artifact["sha256"],
            "raw file checksum, size, or file type drifted",
        )

    count_path = raw_dir / COUNT_RAW_FILENAME
    with count_path.open("r", encoding="utf-8", newline="") as stream:
        count_rows = list(csv.reader(stream))
    _require(
        count_rows == [["totalRecords"], [str(EXPECTED_COUNT)]],
        "raw count table drifted",
    )

    occurrence_artifact = artifacts[OCCURRENCE_RAW_FILENAME]
    occurrence_path = raw_dir / OCCURRENCE_RAW_FILENAME
    with occurrence_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        rows = list(reader)
    _require(
        header == occurrence_artifact["column_names"]
        and len(rows) == EXPECTED_COUNT
        and all(len(row) == len(header) for row in rows),
        "raw occurrence table dimensions or columns drifted",
    )
    _require(
        _required_core_fields_present(header)
        and bool(_assertion_columns(header)),
        "raw occurrence core or assertion information missing",
    )
    return {
        "readiness": PASS,
        "raw_replay_required": False,
        "count": EXPECTED_COUNT,
        "returned_rows": EXPECTED_COUNT,
        "returned_columns": len(header),
        "galah_version": GALAH_VERSION,
        "endpoint": CORRECT_DOWNLOAD_ENDPOINT,
    }


def _load_bound_tracked_docs(package: Path) -> dict[str, dict[str, Any]]:
    package = Path(package)
    _require(package.is_dir() and not package.is_symlink(), "evidence package missing")
    entries = list(package.iterdir())
    expected_files = {*TRACKED_FILENAMES, "manifest.json"}
    _require(
        {entry.name for entry in entries} == expected_files
        and len(entries) == len(expected_files),
        "tracked evidence footprint drifted",
    )
    _require(
        all(entry.is_file() and not entry.is_symlink() for entry in entries),
        "tracked evidence contains non-file or symlink",
    )
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    _exact_keys(manifest, {"schema_version", "files"}, "manifest")
    _require(
        manifest["schema_version"] == "1.0"
        and isinstance(manifest["files"], list)
        and len(manifest["files"]) == len(TRACKED_FILENAMES),
        "manifest identity or length drifted",
    )
    manifest_paths = []
    for entry in manifest["files"]:
        _exact_keys(entry, {"path", "sha256", "bytes"}, "manifest entry")
        path = package / str(entry["path"])
        _require(
            entry["path"] in TRACKED_FILENAMES
            and path.is_file()
            and not path.is_symlink()
            and isinstance(entry["sha256"], str)
            and SHA256_RE.fullmatch(entry["sha256"]) is not None
            and isinstance(entry["bytes"], int)
            and path.stat().st_size == entry["bytes"]
            and sha256(path) == entry["sha256"],
            "tracked manifest binding drifted",
        )
        manifest_paths.append(entry["path"])
    _require(
        manifest_paths == TRACKED_FILENAMES,
        "tracked manifest order or paths drifted",
    )
    docs = {
        name: json.loads((package / name).read_text(encoding="utf-8"))
        for name in TRACKED_FILENAMES
    }
    for name, value in docs.items():
        _scan_tracked(value, path=name)
    return docs


def validate_evidence_package(
    package: Path,
    plan: dict[str, Any],
    *,
    raw_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate tracked evidence and optionally replay both ignored raw CSVs."""

    validate_plan(plan)
    package = Path(package)
    docs = _load_bound_tracked_docs(package)
    support = docs["support_resolution.json"]
    summary = docs["run_summary.json"]
    review = docs["review.json"]
    _validate_tracked_docs(support, summary, review, plan)
    if raw_dir is None:
        return {
            "readiness": review["readiness"],
            "raw_replay_required": summary["outcome"] == "completed",
            "outcome": summary["outcome"],
        }
    _require(
        summary["outcome"] == "completed",
        "blocked run cannot claim pass through raw replay",
    )
    return _replay_raw(Path(raw_dir), summary, plan)


def rebuild_evidence_from_raw(
    plan_path: Path,
    raw_dir: Path,
    evidence_dir: Path,
    *,
    now_fn: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Resolve the one known DWC license alias from the frozen raw package."""

    plan = _load_plan(Path(plan_path))
    validate_plan(plan)
    raw_dir = Path(raw_dir)
    evidence_dir = Path(evidence_dir)
    docs = _load_bound_tracked_docs(evidence_dir)
    support = docs["support_resolution.json"]
    summary = docs["run_summary.json"]
    review = docs["review.json"]
    _require(support == _support_resolution(), "support resolution drifted")
    _require(
        "offline_repair" not in summary
        and summary.get("outcome") == "blocked"
        and summary.get("stop_reason") == "material_schema_failure"
        and summary.get("calls")
        == {"atlas_counts": 1, "atlas_occurrences": 1}
        and summary.get("query", {}).get("selected_count") == EXPECTED_COUNT
        and summary.get("returned_rows") == EXPECTED_COUNT
        and summary.get("required_core_fields_present") is False
        and summary.get("assertion_information_identifiable") is True
        and review.get("readiness") == "blocked_material_schema_failure",
        "evidence is not the exact pre-repair schema false negative",
    )
    semantics = summary.get("package_semantics")
    _require(
        isinstance(semantics, dict)
        and "returned_field_aliases" not in semantics,
        "pre-repair package semantics drifted",
    )
    semantics["returned_field_aliases"] = RETURNED_FIELD_ALIASES
    summary["offline_repair"] = {
        "performed": False,
        "initial_stop_reason": None,
        "basis": "not_required",
        "second_live_attempt": False,
        "completed_at_utc": None,
    }
    _validate_tracked_docs(support, summary, review, plan)

    raw_result = _replay_raw(raw_dir, summary, plan)
    _require(
        raw_result["readiness"] == PASS
        and raw_result["count"] == EXPECTED_COUNT
        and raw_result["returned_rows"] == EXPECTED_COUNT,
        "frozen raw package did not prove the repaired schema",
    )

    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    summary["outcome"] = "completed"
    summary["stop_reason"] = None
    summary["required_core_fields_present"] = True
    summary["offline_repair"] = {
        "performed": True,
        "initial_stop_reason": "material_schema_failure",
        "basis": (
            "frozen_raw_header_replay_of_explicit_dwc_license_alias"
        ),
        "second_live_attempt": False,
        "completed_at_utc": _utc(now_fn()),
    }
    review["outcome"] = "completed"
    review["readiness"] = TRACKED_ONLY
    review["raw_replay"] = "required_for_usable_route_decision"
    review["observations"]["required_core_fields_present"] = True
    review["conclusion"] = (
        "Both permitted live calls completed. The initial schema gate stopped "
        "on the exact dwcHeaders license alias; frozen raw replay resolved "
        "that false negative without a second live attempt. Exact local raw "
        "replay remains required for the usability decision."
    )
    alias_limit = (
        "Under dwcHeaders=true, the requested license field is returned "
        "under the one explicit alias dcterms:license."
    )
    if alias_limit not in review["limitations"]:
        review["limitations"].append(alias_limit)
    _write_evidence(evidence_dir, support, summary, review)
    return validate_evidence_package(
        evidence_dir, plan, raw_dir=raw_dir
    )


def _load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or replay Goal 015.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--plan", type=Path, required=True)
    run_parser.add_argument("--raw-dir", type=Path, required=True)
    run_parser.add_argument("--evidence-dir", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--plan", type=Path, required=True)
    validate_parser.add_argument("--evidence-dir", type=Path, required=True)
    validate_parser.add_argument("--raw-dir", type=Path)
    rebuild_parser = subparsers.add_parser("rebuild")
    rebuild_parser.add_argument("--plan", type=Path, required=True)
    rebuild_parser.add_argument("--evidence-dir", type=Path, required=True)
    rebuild_parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run_pilot(args.plan, args.raw_dir, args.evidence_dir)
        elif args.command == "rebuild":
            result = rebuild_evidence_from_raw(
                args.plan, args.raw_dir, args.evidence_dir
            )
        else:
            result = validate_evidence_package(
                args.evidence_dir,
                _load_plan(args.plan),
                raw_dir=args.raw_dir,
            )
    except GalahPilotValidationError as error:
        print(
            json.dumps({"outcome": "stopped", "reason": str(error)}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
