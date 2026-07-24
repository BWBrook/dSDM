"""Fail-closed Goal 017 ALA count/canary/full-acquisition runner.

The module is deliberately standard-library-only when imported.  ``galah`` and
``pandas`` are imported lazily by :func:`run` (and can be dependency-injected
for tests).  Raw rows are written immediately and are never normalised.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import os
import operator
import signal
import tempfile
import re
import unicodedata
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ala_query_scope import PARENT_CONCEPTS

GALAH_VERSION = "0.13.3"
OCCURRENCE_TIMEOUT_SECONDS = 3600
MAX_SPECIES_COUNT = 1_000_000
MAX_TOTAL_COUNT = 5_000_000
GOAL_ID = "goal017-ala-nine-species-acquisition-2026-07-24"
TRACKED_ONLY = "goal017_tracked_evidence_valid_raw_replay_required"
PASS = "goal017_nine_species_acquisition_complete"
BLOCKED = "goal017_acquisition_blocked"
CORE_FIELDS = ["recordID", "occurrenceID", "dataResourceUid", "dataResourceName", "datasetID", "datasetName", "eventDate", "year", "decimalLatitude", "decimalLongitude", "coordinateUncertaintyInMeters", "coordinatePrecision", "raw_scientificName", "raw_taxonConceptID", "scientificName", "taxonConceptID", "acceptedNameUsage", "acceptedNameUsageID", "taxonRank", "assertions", "dcterms:license"]
QA_BOOLEAN_TOKENS = {"true", "false", "1", "0", "yes", "no"}
EMAIL_RE = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
FORBIDDEN_EVIDENCE_KEYS = {
    "recordID",
    "occurrenceID",
    "decimalLatitude",
    "decimalLongitude",
    "eventDate",
    "ALA_DOWNLOAD_EMAIL",
    "email",
}


class AcquisitionValidationError(ValueError):
    """Sanitised fail-closed validation failure."""


class _Stop(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise AcquisitionValidationError(reason)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcquisitionValidationError("invalid_json") from exc
    _require(isinstance(value, dict), "json_root_not_object")
    return value


def _root_for_plan(plan_path: Path) -> Path:
    return plan_path.parent.parent


def _resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _regular(path: Path, reason: str = "unsafe_artifact") -> None:
    _require(path.exists() and not path.is_symlink() and path.is_file(), reason)


def _read_goal016(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    decision = plan["goal016"]["decision_plan"]
    contract = plan["goal016"]["field_contract"]
    dp = _resolved(root, decision["path"])
    cp = _resolved(root, contract["path"])
    _regular(dp, "goal016_decision_missing")
    _regular(cp, "goal016_contract_missing")
    _require(sha256(dp) == decision["sha256"] and sha256(cp) == contract["sha256"], "goal016_binding_drift")
    d = _load(dp)
    c = _load(cp)
    _require(d.get("mode") == "offline_exact_raw_replay", "goal016_mode_drift")
    _require(d.get("calibration", {}).get("expanded_qa_fields"), "goal016_qa_missing")
    _require(d.get("calibration", {}).get("returned_core_fields"), "goal016_core_missing")
    _require(c.get("contract_id") == "ala-occurrence-field-contract-v1", "goal016_contract_drift")
    _require(d.get("calibration", {}).get("returned_core_fields", [])[-1:] == ["dcterms:license"], "goal016_license_alias_drift")
    return d


def validate_plan(plan: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    """Validate immutable plan identity and bindings; no network or imports."""
    expected = {"schema_version", "goal_id", "package", "scope", "limits", "configuration", "goal016", "decision_bundle", "species", "canary", "projection", "raw", "evidence"}
    _require(isinstance(plan, dict) and set(plan) == expected, "plan_shape_drift")
    _require(plan["schema_version"] == "1.0" and plan["goal_id"] == GOAL_ID, "plan_identity_drift")
    _require(plan["package"] == {"name": "galah-python", "version": GALAH_VERSION, "download_endpoint": "https://api.ala.org.au/occurrences/occurrences/offline/download"}, "package_drift")
    _require(plan["scope"] == {"filters": ["stateProvince=Tasmania", "year>=2001", "year<=2025"], "use_data_profile": False, "canonical_query_only": True}, "scope_drift")
    limits = plan["limits"]
    _require(limits == {"count_calls": 10, "occurrence_calls": 10, "max_species_count": 1000000, "max_total_count": 5000000, "disk_bytes_per_row": 2048, "disk_multiplier": 5, "disk_reserve_bytes": 10000000000, "occurrence_timeout_seconds": 3600}, "limits_drift")
    _require(plan["configuration"] == {"email_env": "ALA_DOWNLOAD_EMAIL", "atlas": "Australia", "authenticate": False, "email_notify": False, "reason": 4, "verbose": False, "data_profile": None, "timeout": 600}, "configuration_drift")
    _require(
        plan["raw"]
        == {
            "relative_directory": "data/raw/ala/goal017-nine-species/2026-07-24",
            "subdirectories": ["counts", "calibration", "occurrences"],
        },
        "raw_layout_drift",
    )
    _require(
        set(plan["goal016"]) == {"decision_plan", "field_contract", "required_raw_decision"}
        and plan["goal016"]["required_raw_decision"]
        == "count_census_ready_full_row_acquisition_blocked_on_provider_identity",
        "goal016_binding_shape_drift",
    )
    _require(
        set(plan["goal016"]["decision_plan"]) == {"path", "sha256"}
        and set(plan["goal016"]["field_contract"]) == {"path", "sha256"}
        and set(plan["decision_bundle"]) == {"path", "sha256"},
        "binding_shape_drift",
    )
    species = plan["species"]
    _require(isinstance(species, list) and len(species) == 9 and all(set(x) == {"species_id", "scientific_name", "accepted_concept"} for x in species), "species_shape_drift")
    _require(len({x["species_id"] for x in species}) == 9, "species_identity_duplicate")
    _require([s["species_id"] for s in species] == list(PARENT_CONCEPTS), "species_order_drift")
    _require([s["accepted_concept"] for s in species] == list(PARENT_CONCEPTS.values()), "species_concept_drift")
    _require(plan["canary"] == {"species_id": "pseudocheirus_peregrinus", "filters": ["stateProvince=Tasmania", "year=2001"], "min_count": 1, "max_count": 100}, "canary_drift")
    projection = plan["projection"]
    _require(projection["mint_doi"] is False and projection["fields"] == ["recordID", "occurrenceID", "dataResourceUid", "dataResourceName", "datasetID", "datasetName", "eventDate", "year", "decimalLatitude", "decimalLongitude", "coordinateUncertaintyInMeters", "coordinatePrecision", "raw_scientificName", "raw_taxonConceptID", "scientificName", "taxonConceptID", "acceptedNameUsage", "acceptedNameUsageID", "taxonRank", "assertions", "license"], "projection_drift")
    _require(
        plan["evidence"]
        == {"filenames": ["counts.json", "identity.json", "acquisition.json", "review.json", "manifest.json"]},
        "evidence_names_drift",
    )
    if root is not None:
        _read_goal016(root, plan)
        bundle = plan["decision_bundle"]
        bp = _resolved(root, bundle["path"])
        _regular(bp, "decision_bundle_missing")
        _require(sha256(bp) == bundle["sha256"], "decision_bundle_binding_drift")
        b = _load(bp)
        bound_species = [s for s in b.get("species", []) if s.get("include_phase1")]
        _require(len(bound_species) == 9, "species_bundle_drift")
        expected_species = [{"species_id": s.get("species_id"), "scientific_name": s.get("accepted_name"), "accepted_concept": s.get("ala_taxon_concept_id")} for s in bound_species]
        _require(species == expected_species, "species_bundle_drift")
    return {"species_count": 9, "goal_id": GOAL_ID}


def _utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _frame_rows(frame: Any) -> tuple[list[str], list[dict[str, Any]]]:
    columns = [str(x) for x in list(getattr(frame, "columns", []))]
    _require(columns and len(columns) == len(set(columns)), "frame_schema_failure")
    try:
        rows = frame.to_dict(orient="records")
    except Exception as exc:
        raise AcquisitionValidationError("frame_serialization_failure") from exc
    _require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), "frame_return_shape_failure")
    return columns, rows


def _file_contains(path: Path, needle: bytes) -> bool:
    if not needle:
        return False
    carry = b""
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            block = carry + chunk
            if needle in block:
                return True
            carry = block[-(len(needle) - 1):] if len(needle) > 1 else b""
    return False


def _write_frame(frame: Any, path: Path, *, private_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame.to_csv(path, index=False, lineterminator="\n")
    except Exception as exc:
        raise AcquisitionValidationError("raw_serialization_failure") from exc
    _regular(path, "raw_serialization_missing")
    if _file_contains(path, private_value.encode("utf-8")):
        path.unlink()
        raise AcquisitionValidationError("runtime_account_in_raw")


def _count_value(frame: Any) -> int:
    columns, rows = _frame_rows(frame)
    _require(columns == ["totalRecords"] and len(rows) == 1, "count_schema_failure")
    value = rows[0].get("totalRecords")
    _require(not isinstance(value, bool), "count_type_failure")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise AcquisitionValidationError("count_type_failure") from exc
    _require(result >= 0, "count_type_failure")
    return result


def _clean_id(value: Any) -> bool:
    text = "" if value is None else str(value)
    return bool(text.strip()) and not any(unicodedata.category(ch).startswith("C") for ch in text)


def _validate_occurrence_csv(path: Path, expected_rows: int, qa_fields: list[str], prior_ids: set[str]) -> set[str]:
    _regular(path, "occurrence_raw_missing")
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or [])
            _require(fields == CORE_FIELDS + qa_fields, "occurrence_header_failure")
            ids: list[str] = []
            row_count = 0
            for row in reader:
                row_count += 1
                _require(set(row) == set(fields), "row_schema_failure")
                value = row.get("recordID", "")
                _require(_clean_id(value), "record_id_blank_or_control")
                ids.append(str(value))
                for field in qa_fields:
                    _require(
                        (row.get(field) or "").strip().lower() in QA_BOOLEAN_TOKENS,
                        "qa_boolean_failure",
                    )
    except (OSError, csv.Error) as exc:
        raise AcquisitionValidationError("occurrence_csv_invalid") from exc
    _require(row_count == expected_rows, "row_count_mismatch")
    _require(len(set(ids)) == len(ids), "record_id_duplicate_within_species")
    _require(not prior_ids.intersection(ids), "record_id_duplicate_across_species")
    return set(ids)


def _safe_exception(_exc: BaseException) -> str:
    return "runtime_or_access_error"


def _assert_evidence_private(value: Any) -> None:
    def walk(item: Any) -> None:
        if isinstance(item, dict):
            _require(not FORBIDDEN_EVIDENCE_KEYS.intersection(item), "privacy_key_failure")
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    _require(not EMAIL_RE.search(json.dumps(value, sort_keys=True)), "privacy_email_failure")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _assert_evidence_private(value)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest(evidence_dir: Path, raw_dir: Path) -> dict[str, Any]:
    files = []
    for name in ("counts.json", "identity.json", "acquisition.json", "review.json"):
        path = evidence_dir / name
        _regular(path, "evidence_missing")
        files.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    raw = []
    if raw_dir.exists() and not raw_dir.is_symlink():
        for path in sorted(p for p in raw_dir.rglob("*") if p.is_file()):
            raw.append({"path": str(path.relative_to(raw_dir)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"schema_version": "1.0", "files": files, "raw_files": raw}


def _write_evidence(evidence_dir: Path, raw_dir: Path, counts: dict[str, Any], identity: dict[str, Any], acquisition: dict[str, Any], review: dict[str, Any]) -> None:
    _write_json(evidence_dir / "counts.json", counts)
    _write_json(evidence_dir / "identity.json", identity)
    _write_json(evidence_dir / "acquisition.json", acquisition)
    _write_json(evidence_dir / "review.json", review)
    _write_json(evidence_dir / "manifest.json", _manifest(evidence_dir, raw_dir))


def _base_evidence(
    plan: dict[str, Any],
    outcome: str,
    reason: str | None,
    *,
    plan_sha256: str,
    started_at_utc: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    counts = {"schema_version": "1.0", "goal_id": GOAL_ID, "outcome": outcome, "species": [], "count_calls": 0, "total_count": 0}
    identity = {"schema_version": "1.0", "outcome": outcome, "canary": {"attempted": False, "passed": False}, "record_id": {"policy": "recordID_required_unique_control_clean", "observed": False}}
    acquisition = {"schema_version": "1.0", "outcome": outcome, "occurrence_calls": 0, "species": [], "stop_before_next_species": True}
    review = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "plan_sha256": plan_sha256,
        "started_at_utc": started_at_utc,
        "completed_at_utc": None,
        "outcome": outcome,
        "readiness": PASS if outcome == "completed" else BLOCKED,
        "stop_reason": reason,
        "rows": 0,
        "privacy": {
            "row_values_retained": False,
            "email_retained": False,
            "network_errors_retained": False,
        },
    }
    return counts, identity, acquisition, review


def run(plan_path: Path, raw_dir: Path, evidence_dir: Path, *, galah_module: Any | None = None, pandas_module: Any | None = None, environ: Mapping[str, str] | None = None, now_fn: Callable[[], datetime] | None = None, clock: Callable[[], datetime] | None = None, alarm_fn: Callable[[Callable[[], Any], int], Any] | None = None, alarm: Callable[[Callable[[], Any], int], Any] | None = None, disk_free_fn: Callable[[Path], int] | None = None) -> dict[str, Any]:
    plan_path, raw_dir, evidence_dir = Path(plan_path), Path(raw_dir), Path(evidence_dir)
    root = _root_for_plan(plan_path)
    plan = _load(plan_path)
    validate_plan(plan, root=root)
    _require(not raw_dir.exists() and not raw_dir.is_symlink(), "raw_directory_must_be_new")
    _require(not evidence_dir.exists() and not evidence_dir.is_symlink(), "evidence_directory_must_be_new")
    env = os.environ if environ is None else environ
    email = env.get(plan["configuration"]["email_env"], "")
    _require(isinstance(email, str) and bool(email.strip()), "missing_runtime_account")
    email = email.strip()
    try:
        if galah_module is None:
            galah_module = importlib.import_module("galah")
        if pandas_module is None:
            pandas_module = importlib.import_module("pandas")
    except ImportError as exc:
        raise AcquisitionValidationError("dependency_unavailable") from exc
    _require(getattr(galah_module, "__version__", None) == GALAH_VERSION, "galah_version_drift")
    frame_type = getattr(pandas_module, "DataFrame", None)
    _require(frame_type is not None, "pandas_dataframe_type_unavailable")
    raw_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    now_fn = now_fn or clock or (lambda: datetime.now(timezone.utc))
    alarm_fn = alarm_fn or alarm or _alarm
    disk_free_fn = disk_free_fn or (lambda path: __import__("shutil").disk_usage(path).free)
    counts, identity, acquisition, review = _base_evidence(
        plan,
        "blocked",
        None,
        plan_sha256=sha256(plan_path),
        started_at_utc=_utc(now_fn()),
    )
    qa_fields = _read_goal016(root, plan)["calibration"]["expanded_qa_fields"]
    prior_ids: set[str] = set()
    stop_reason: str | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="dsdm-goal017-galah-") as temp:
            config_path = Path(temp) / "config.ini"
            config_path.touch()
            try:
                galah_module.galah_config(atlas=plan["configuration"]["atlas"], email=email, email_notify=False, reason=4, authenticate=False, data_profile=None, verbose=False, timeout=600, config_file=str(config_path))
            except Exception as exc:
                raise _Stop(_safe_exception(exc)) from None
            by_id = {s["species_id"]: s for s in plan["species"]}
            for species in plan["species"]:
                args = {"identifiers": species["accepted_concept"], "filters": list(plan["scope"]["filters"]), "use_data_profile": False, "config_file": str(config_path)}
                try:
                    frame = galah_module.atlas_counts(**args)
                except Exception as exc:
                    raise _Stop(_safe_exception(exc)) from None
                counts["count_calls"] += 1
                if not isinstance(frame, frame_type):
                    raise _Stop("wrong_return_type")
                value = _count_value(frame)
                path = raw_dir / "counts" / f"{species['species_id']}.csv"
                _write_frame(frame, path, private_value=email)
                if not (1 <= value <= plan["limits"]["max_species_count"]):
                    raise _Stop("count_capacity_failure")
                counts["species"].append({"species_id": species["species_id"], "count": value, "query": "canonical_parent"})
                counts["total_count"] += value
            _require(counts["total_count"] <= plan["limits"]["max_total_count"], "count_capacity_failure")
            required_disk = counts["total_count"] * plan["limits"]["disk_bytes_per_row"] * plan["limits"]["disk_multiplier"] + plan["limits"]["disk_reserve_bytes"]
            _require(disk_free_fn(raw_dir) >= required_disk, "disk_capacity_failure")
            pseudo = by_id[plan["canary"]["species_id"]]
            canary_args = {"identifiers": pseudo["accepted_concept"], "filters": list(plan["canary"]["filters"]), "use_data_profile": False, "config_file": str(config_path)}
            try:
                canary_frame = galah_module.atlas_counts(**canary_args)
            except Exception as exc:
                raise _Stop(_safe_exception(exc)) from None
            counts["count_calls"] += 1
            if not isinstance(canary_frame, frame_type):
                raise _Stop("wrong_return_type")
            canary_count = _count_value(canary_frame)
            _write_frame(
                canary_frame,
                raw_dir / "calibration" / "pseudocheirus_peregrinus-2001-count.csv",
                private_value=email,
            )
            identity["canary"] = {"attempted": True, "count": canary_count, "passed": plan["canary"]["min_count"] <= canary_count <= plan["canary"]["max_count"]}
            if not identity["canary"]["passed"]:
                raise _Stop("canary_count_gate_failure")
            fields = list(plan["projection"]["fields"])
            # A separate, bounded canary occurrence call calibrates provider
            # identity before any full download.  Its IDs are not included in
            # the cross-species full-acquisition duplicate set.
            canary_args = {"identifiers": pseudo["accepted_concept"], "filters": list(plan["canary"]["filters"]), "use_data_profile": False, "config_file": str(config_path), "fields": fields, "mint_doi": False}
            try:
                canary_occurrences = alarm_fn(lambda: galah_module.atlas_occurrences(**canary_args), plan["limits"]["occurrence_timeout_seconds"])
            except TimeoutError:
                raise _Stop("timeout") from None
            except Exception as exc:
                raise _Stop(_safe_exception(exc)) from None
            acquisition["occurrence_calls"] += 1
            if not isinstance(canary_occurrences, frame_type):
                raise _Stop("wrong_return_type")
            canary_path = raw_dir / "calibration" / "pseudocheirus_peregrinus-2001-occurrences.csv"
            _write_frame(canary_occurrences, canary_path, private_value=email)
            del canary_occurrences
            _validate_occurrence_csv(canary_path, canary_count, qa_fields, set())
            identity["record_id"] = {"policy": "recordID_required_unique_control_clean", "observed": True, "canary_rows": canary_count}
            for item in sorted(counts["species"], key=lambda x: (x["count"], [s["species_id"] for s in plan["species"]].index(x["species_id"]))):
                species = by_id[item["species_id"]]
                args = {"identifiers": species["accepted_concept"], "filters": list(plan["scope"]["filters"]), "use_data_profile": False, "config_file": str(config_path), "fields": fields, "mint_doi": False}
                try:
                    frame = alarm_fn(lambda: galah_module.atlas_occurrences(**args), plan["limits"]["occurrence_timeout_seconds"])
                except TimeoutError:
                    raise _Stop("timeout") from None
                except Exception as exc:
                    raise _Stop(_safe_exception(exc)) from None
                acquisition["occurrence_calls"] += 1
                if not isinstance(frame, frame_type):
                    raise _Stop("wrong_return_type")
                path = raw_dir / "occurrences" / f"{species['species_id']}.csv"
                _write_frame(frame, path, private_value=email)
                del frame
                ids = _validate_occurrence_csv(path, item["count"], qa_fields, prior_ids)
                prior_ids.update(ids)
                acquisition["species"].append({"species_id": species["species_id"], "expected_rows": item["count"], "returned_rows": item["count"], "record_ids_unique": True})
            review["readiness"] = PASS
            review["rows"] = 0
            review["aggregate_rows"] = sum(item["expected_rows"] for item in acquisition["species"])
            acquisition["stop_before_next_species"] = False
            counts["outcome"] = identity["outcome"] = acquisition["outcome"] = review["outcome"] = "completed"
    except _Stop as exc:
        stop_reason = exc.reason
    except AcquisitionValidationError as exc:
        stop_reason = str(exc)
    except Exception as exc:
        stop_reason = _safe_exception(exc)
    review["stop_reason"] = stop_reason
    review["completed_at_utc"] = _utc(now_fn())
    if stop_reason is None:
        review["readiness"] = PASS
    _write_evidence(evidence_dir, raw_dir, counts, identity, acquisition, review)
    if stop_reason is not None:
        raise AcquisitionValidationError(stop_reason)
    return {"outcome": "completed", "readiness": PASS, "count_calls": counts["count_calls"], "occurrence_calls": acquisition["occurrence_calls"]}


def _parse_utc(value: Any) -> datetime:
    _require(isinstance(value, str) and value.endswith("Z"), "timestamp_failure")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AcquisitionValidationError("timestamp_failure") from exc
    _require(parsed.tzinfo is not None, "timestamp_failure")
    return parsed.astimezone(timezone.utc)


def _validate_evidence_semantics(
    plan: dict[str, Any],
    plan_path: Path,
    documents: dict[str, dict[str, Any]],
) -> None:
    counts = documents["counts"]
    identity = documents["identity"]
    acquisition = documents["acquisition"]
    review = documents["review"]
    _assert_evidence_private(documents)
    _require(
        set(counts)
        == {"schema_version", "goal_id", "outcome", "species", "count_calls", "total_count"},
        "counts_shape_failure",
    )
    _require(
        set(identity) == {"schema_version", "outcome", "canary", "record_id"},
        "identity_shape_failure",
    )
    _require(
        set(acquisition)
        == {"schema_version", "outcome", "occurrence_calls", "species", "stop_before_next_species"},
        "acquisition_shape_failure",
    )
    review_keys = {
        "schema_version",
        "goal_id",
        "plan_sha256",
        "started_at_utc",
        "completed_at_utc",
        "readiness",
        "stop_reason",
        "rows",
        "privacy",
        "outcome",
    }
    if review.get("readiness") == PASS:
        review_keys.add("aggregate_rows")
    _require(set(review) == review_keys, "review_shape_failure")
    _require(
        all(doc.get("schema_version") == "1.0" for doc in documents.values()),
        "evidence_schema_failure",
    )
    _require(
        counts.get("goal_id") == GOAL_ID
        and review.get("goal_id") == GOAL_ID
        and review.get("plan_sha256") == sha256(plan_path),
        "evidence_binding_failure",
    )
    started = _parse_utc(review.get("started_at_utc"))
    completed = _parse_utc(review.get("completed_at_utc"))
    _require(completed >= started, "timestamp_order_failure")
    _require(
        review.get("rows") == 0
        and review.get("privacy")
        == {
            "row_values_retained": False,
            "email_retained": False,
            "network_errors_retained": False,
        },
        "privacy_evidence_failure",
    )
    species_rows = counts.get("species")
    _require(isinstance(species_rows, list), "counts_evidence_failure")
    _require(
        all(
            isinstance(item, dict)
            and set(item) == {"species_id", "count", "query"}
            and item.get("species_id") in {species["species_id"] for species in plan["species"]}
            and isinstance(item.get("count"), int)
            and not isinstance(item.get("count"), bool)
            and 1 <= item["count"] <= plan["limits"]["max_species_count"]
            and item.get("query") == "canonical_parent"
            for item in species_rows
        ),
        "counts_evidence_failure",
    )
    _require(
        len({item["species_id"] for item in species_rows}) == len(species_rows)
        and counts.get("total_count") == sum(item["count"] for item in species_rows),
        "counts_evidence_failure",
    )
    _require(
        isinstance(counts.get("count_calls"), int)
        and 0 <= counts["count_calls"] <= plan["limits"]["count_calls"],
        "counts_evidence_failure",
    )
    _require(
        isinstance(acquisition.get("occurrence_calls"), int)
        and 0 <= acquisition["occurrence_calls"] <= plan["limits"]["occurrence_calls"]
        and isinstance(acquisition.get("species"), list),
        "acquisition_evidence_failure",
    )
    _require(
        all(
            isinstance(item, dict)
            and set(item)
            == {
                "species_id",
                "expected_rows",
                "returned_rows",
                "record_ids_unique",
            }
            and isinstance(item.get("expected_rows"), int)
            and item.get("expected_rows") == item.get("returned_rows")
            and item.get("record_ids_unique") is True
            for item in acquisition["species"]
        ),
        "acquisition_evidence_failure",
    )
    _require(
        isinstance(identity.get("canary"), dict)
        and isinstance(identity.get("record_id"), dict)
        and identity["record_id"].get("policy")
        == "recordID_required_unique_control_clean",
        "identity_evidence_failure",
    )
    if review.get("readiness") == PASS:
        canonical_ids = [species["species_id"] for species in plan["species"]]
        _require(
            [item["species_id"] for item in species_rows] == canonical_ids
            and counts.get("count_calls") == plan["limits"]["count_calls"]
            and counts.get("total_count") <= plan["limits"]["max_total_count"],
            "counts_evidence_failure",
        )
        _require(
            set(identity["canary"]) == {"attempted", "count", "passed"}
            and identity["canary"].get("attempted") is True
            and identity["canary"].get("passed") is True
            and plan["canary"]["min_count"]
            <= identity["canary"].get("count", 0)
            <= plan["canary"]["max_count"],
            "identity_evidence_failure",
        )
        _require(
            identity["record_id"]
            == {
                "policy": "recordID_required_unique_control_clean",
                "observed": True,
                "canary_rows": identity["canary"]["count"],
            },
            "identity_evidence_failure",
        )
        count_by_id = {item["species_id"]: item["count"] for item in species_rows}
        order_index = {species_id: index for index, species_id in enumerate(canonical_ids)}
        expected_order = sorted(
            canonical_ids, key=lambda species_id: (count_by_id[species_id], order_index[species_id])
        )
        _require(
            acquisition.get("occurrence_calls") == plan["limits"]["occurrence_calls"]
            and acquisition.get("stop_before_next_species") is False
            and [item["species_id"] for item in acquisition["species"]] == expected_order
            and all(
                item["expected_rows"] == count_by_id[item["species_id"]]
                for item in acquisition["species"]
            ),
            "acquisition_evidence_failure",
        )
        _require(
            counts.get("outcome")
            == identity.get("outcome")
            == acquisition.get("outcome")
            == review.get("outcome")
            == "completed"
            and review.get("stop_reason") is None
            and review.get("aggregate_rows") == counts.get("total_count"),
            "review_evidence_failure",
        )
    else:
        _require(
            review.get("readiness") == BLOCKED
            and counts.get("outcome")
            == identity.get("outcome")
            == acquisition.get("outcome")
            == review.get("outcome")
            == "blocked"
            and isinstance(review.get("stop_reason"), str)
            and bool(review["stop_reason"])
            and review.get("stop_before_next_species", True) is True
            and acquisition.get("stop_before_next_species") is True,
            "blocked_evidence_failure",
        )


def validate_evidence(plan_path: Path, evidence_dir: Path, raw_dir: Path | None = None) -> dict[str, Any]:
    plan_path, evidence_dir = Path(plan_path), Path(evidence_dir)
    plan = _load(plan_path)
    validate_plan(plan, root=_root_for_plan(plan_path))
    _require(not evidence_dir.is_symlink() and evidence_dir.is_dir(), "evidence_directory_invalid")
    expected = set(plan["evidence"]["filenames"])
    actual = {p.name for p in evidence_dir.iterdir() if p.is_file() or p.is_symlink()}
    _require(actual == expected, "evidence_footprint_drift")
    documents = {Path(name).stem: _load(evidence_dir / name) for name in expected if name != "manifest.json"}
    manifest = _load(evidence_dir / "manifest.json")
    _assert_evidence_private(manifest)
    _require(isinstance(manifest, dict) and manifest.get("schema_version") == "1.0", "manifest_schema_failure")
    _require(set(manifest) == {"schema_version", "files", "raw_files"}, "manifest_shape_failure")
    _require(isinstance(manifest.get("files"), list) and isinstance(manifest.get("raw_files"), list), "manifest_entry_shape_failure")
    _require(all(isinstance(entry, dict) and set(entry) == {"path", "bytes", "sha256"} for entry in manifest.get("files", []) + manifest.get("raw_files", [])), "manifest_entry_shape_failure")
    all_entries = manifest.get("files", []) + manifest.get("raw_files", [])
    _require(len({entry["path"] for entry in all_entries}) == len(all_entries), "manifest_duplicate_path")
    _require(all(isinstance(entry["path"], str) and isinstance(entry["bytes"], int) and entry["bytes"] >= 0 and isinstance(entry["sha256"], str) and len(entry["sha256"]) == 64 and not Path(entry["path"]).is_absolute() and ".." not in Path(entry["path"]).parts for entry in all_entries), "manifest_entry_invalid")
    _require(
        [entry["path"] for entry in manifest.get("files", [])]
        == ["counts.json", "identity.json", "acquisition.json", "review.json"],
        "manifest_evidence_footprint_failure",
    )
    for entry in manifest.get("files", []):
        path = evidence_dir / entry.get("path", "")
        _regular(path, "evidence_manifest_missing")
        _require(path.stat().st_size == entry.get("bytes") and sha256(path) == entry.get("sha256"), "evidence_checksum_failure")
    _validate_evidence_semantics(plan, plan_path, documents)
    if raw_dir is None:
        readiness = TRACKED_ONLY if documents["review"].get("readiness") == PASS else BLOCKED
        return {"readiness": readiness, "raw_replay_required": True}
    raw_dir = Path(raw_dir)
    _require(raw_dir.is_dir() and not raw_dir.is_symlink(), "raw_directory_invalid")
    listed_raw = {entry.get("path") for entry in manifest.get("raw_files", [])}
    observed_raw = {str(path.relative_to(raw_dir)) for path in raw_dir.rglob("*") if path.is_file() or path.is_symlink()}
    _require(observed_raw == listed_raw, "raw_footprint_drift")
    for entry in manifest.get("raw_files", []):
        path = raw_dir / entry.get("path", "")
        _regular(path, "raw_manifest_missing")
        _require(path.stat().st_size == entry.get("bytes") and sha256(path) == entry.get("sha256"), "raw_checksum_failure")
    # Replay the compact semantic contract from raw CSVs.  This catches an
    # altered/rechecksummed artifact rather than relying on manifest hashes
    # alone, while retaining no row values in tracked evidence.
    if documents["counts"].get("species"):
        for item in documents["counts"]["species"]:
            cp = raw_dir / "counts" / f"{item['species_id']}.csv"
            _regular(cp, "count_raw_missing")
            with cp.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                _require(list(reader.fieldnames or []) == ["totalRecords"] and len(rows) == 1, "count_raw_schema_failure")
                _require(rows[0].get("totalRecords") == str(item["count"]), "count_raw_replay_failure")
        replay_ids: set[str] = set()
        canary_count = documents["identity"].get("canary", {}).get("count")
        if canary_count is not None:
            canary_count_path = raw_dir / "calibration" / "pseudocheirus_peregrinus-2001-count.csv"
            _regular(canary_count_path, "canary_count_raw_missing")
            with canary_count_path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                _require(
                    list(reader.fieldnames or []) == ["totalRecords"]
                    and len(rows) == 1
                    and rows[0].get("totalRecords") == str(canary_count),
                    "canary_count_raw_replay_failure",
                )
            canary_path = raw_dir / "calibration" / "pseudocheirus_peregrinus-2001-occurrences.csv"
            _validate_occurrence_csv(canary_path, int(canary_count), _read_goal016(_root_for_plan(plan_path), plan)["calibration"]["expanded_qa_fields"], set())
        for item in documents["acquisition"].get("species", []):
            op = raw_dir / "occurrences" / f"{item['species_id']}.csv"
            replay_ids.update(_validate_occurrence_csv(op, int(item["expected_rows"]), _read_goal016(_root_for_plan(plan_path), plan)["calibration"]["expanded_qa_fields"], replay_ids))
    if documents["review"].get("readiness") == PASS:
        _require(documents["acquisition"].get("occurrence_calls") == 10, "acquisition_evidence_failure")
    return {"readiness": documents["review"].get("readiness", BLOCKED), "raw_replay_required": False}


# Naming compatible with earlier Goal 015 validators and convenient for callers.
validate_evidence_package = validate_evidence
run_acquisition = run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Goal 017 ALA acquisition")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "validate"):
        p = sub.add_parser(name)
        p.add_argument("--plan", type=Path, required=True)
        p.add_argument("--evidence-dir", type=Path, required=True)
        p.add_argument("--raw-dir", type=Path, required=(name == "run"))
    args = parser.parse_args(argv)
    try:
        result = run(args.plan, args.raw_dir, args.evidence_dir) if args.command == "run" else validate_evidence(args.plan, args.evidence_dir, args.raw_dir)
    except (AcquisitionValidationError, OSError) as exc:
        print(json.dumps({"outcome": "blocked", "reason": str(exc) if isinstance(exc, AcquisitionValidationError) else "filesystem_error"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
