"""Count-only ALA census and conservative resource gate for Goal 040."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import galah
import requests


PACKAGE = {"name": "galah-python", "version": "0.13.3"}
SERVICE = {
    "name": "ALA Occurrence REST services",
    "version": "3.0",
    "endpoint": "https://api.ala.org.au/occurrences/occurrences/search",
    "version_basis": "Goal012 official OpenAPI preflight",
}
YEARS = [2001, 2025]
BBOX = {"xmin": 135.375, "xmax": 153.625, "ymin": -43.6275, "ymax": -23.7775}
MAX_TOTAL = 2_000_000
MAX_TAXON = 500_000
BYTES_PER_ROW = 2_048
WORKING_MULTIPLIER = 5
MIN_FREE_AFTER = 30 * 1024**3
CANONICAL_RETAINED_ESTIMATES = 22
SUPERSEDED_EXPLORATORY_ESTIMATES = 44
TOTAL_UNIQUE_LIVE_REQUESTS = 66
MANIFEST_PATH = Path("metadata/goal040_count_census_manifest.json")
LEDGER_PATH = Path("metadata/goal040_taxon_query_ledger.csv")
BOUNDARY_PATH = Path("metadata/goal040_domain_boundary_manifest.json")
CONFIG_PATH = Path("config/goal040_se_mammal_feasibility.json")
RAW_ROOT = Path("data/raw/goal040/count_census")


class Goal040CountError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def build_branch_matrix(root: Path) -> list[dict[str, Any]]:
    with (root / LEDGER_PATH).open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["query_roles"]]
    if len(rows) != 21:
        raise Goal040CountError("count census requires exactly 21 frozen query-role taxa")
    branches: list[dict[str, Any]] = []
    for row in rows:
        taxon = row["scientific_name"]
        concepts = json.loads(row["query_concepts"])
        descendants = json.loads(row["accepted_descendants"])
        aliases = json.loads(row["evidence_backed_aliases"])
        if not concepts or concepts[0] != row["ala_accepted_concept_id"]:
            raise Goal040CountError(f"{taxon} parent concept is not ledger-bound")
        if concepts[1:] != [item["concept_id"] for item in descendants]:
            raise Goal040CountError(f"{taxon} reviewed descendant union drifted")
        taxon_slug = _slug(taxon)
        for index, concept in enumerate(concepts):
            kind = "parent" if index == 0 else "reviewed_descendant"
            branch = {
                "branch_id": f"{taxon_slug}__{kind}_{index:02d}",
                "taxon": taxon,
                "branch_kind": kind,
                "selector_type": "identifier",
                "selector_value": concept,
                "expected_resolved_concept_id": concept,
                "years_inclusive": YEARS,
                "bbox_prefilter": BBOX,
                "disableAllQualityFilters": True,
                "exact_domain_application": "after_occurrence_acquisition_before_QA_cell_collapse",
            }
            branch["query_identity_sha256"] = hashlib.sha256(_canonical(branch)).hexdigest()
            branches.append(branch)
        for index, alias in enumerate(aliases, start=1):
            match = re.fullmatch(r'taxa:"([^"]+)"', alias.get("query", ""))
            if match is None:
                raise Goal040CountError(f"{taxon} alias query is not an approved taxa-name branch")
            branch = {
                "branch_id": f"{taxon_slug}__evidence_alias_{index:02d}",
                "taxon": taxon,
                "branch_kind": "evidence_backed_alias",
                "selector_type": "taxa_name",
                "selector_value": match.group(1),
                "expected_resolved_concept_id": row["ala_accepted_concept_id"],
                "years_inclusive": YEARS,
                "bbox_prefilter": BBOX,
                "disableAllQualityFilters": True,
                "exact_domain_application": "after_occurrence_acquisition_before_QA_cell_collapse",
            }
            branch["query_identity_sha256"] = hashlib.sha256(_canonical(branch)).hexdigest()
            branches.append(branch)
    if len({branch["branch_id"] for branch in branches}) != len(branches):
        raise Goal040CountError("count branch identity is duplicated")
    return branches


def build_taxon_union_matrix(branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    taxa = sorted({branch["taxon"] for branch in branches})
    unions = []
    for taxon in taxa:
        selected = [branch for branch in branches if branch["taxon"] == taxon]
        concepts = [
            branch["selector_value"] for branch in selected
            if branch["selector_type"] == "identifier"
        ]
        aliases = [branch for branch in selected if branch["selector_type"] == "taxa_name"]
        union = {
            "branch_id": f"{_slug(taxon)}__taxon_union",
            "taxon": taxon,
            "branch_kind": "accepted_parent_and_reviewed_descendant_OR_union",
            "selector_type": "identifier_union",
            "selector_value": concepts,
            "expected_resolved_concept_ids": concepts,
            "logical_branch_ids": [branch["branch_id"] for branch in selected],
            "alias_branch_ids": [branch["branch_id"] for branch in aliases],
            "years_inclusive": YEARS,
            "bbox_prefilter": BBOX,
            "disableAllQualityFilters": True,
            "exact_domain_application": "after_occurrence_acquisition_before_QA_cell_collapse",
        }
        union["query_identity_sha256"] = hashlib.sha256(_canonical(union)).hexdigest()
        unions.append(union)
    if len(unions) != 21:
        raise Goal040CountError("count census requires exactly 21 taxon unions")
    return unions


def _validate_service_envelope(response: requests.Response) -> dict[str, Any]:
    if response.status_code != 200:
        raise Goal040CountError(f"ALA count request failed with HTTP {response.status_code}")
    value = response.json()
    if not isinstance(value, dict) or value.get("status") != "OK":
        raise Goal040CountError("ALA count response status/shape drifted")
    if value.get("pageSize") != 0 or value.get("startIndex") != 0:
        raise Goal040CountError("ALA count response did not enforce zero-row pagination")
    if value.get("occurrences") not in ([], None):
        raise Goal040CountError("ALA count response contains occurrence rows")
    if value.get("facetResults") not in ([], None):
        raise Goal040CountError("ALA count response contains facets")
    count = value.get("totalRecords")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise Goal040CountError("ALA totalRecords is malformed")
    serialized = json.dumps(value).lower()
    for forbidden in ("decimallatitude", "decimallongitude", "occurrenceid", "recordid", "@"):
        if forbidden in serialized:
            raise Goal040CountError(f"ALA count response leaked forbidden structure: {forbidden}")
    return {"count": count, "envelope_sha256": hashlib.sha256(response.content).hexdigest()}


def _validate_actual_request(url: str, branch: dict[str, Any]) -> None:
    parsed = urlparse(url)
    if f"{parsed.scheme}://{parsed.netloc}{parsed.path}" != SERVICE["endpoint"]:
        raise Goal040CountError("galah count endpoint drifted")
    if "email" in url.lower() or "@" in url:
        raise Goal040CountError("count request URL contains email material")
    params = parse_qs(parsed.query)
    if params.get("disableAllQualityFilters") != ["true"] or params.get("pageSize") != ["0"]:
        raise Goal040CountError("galah count request did not disable profiles or enforce pageSize=0")
    query = " ".join(params.get("q", []))
    expected = branch.get(
        "expected_resolved_concept_ids", [branch.get("expected_resolved_concept_id")]
    )
    if any(not concept or concept not in query for concept in expected):
        raise Goal040CountError("galah resolved count selector to an unexpected concept")
    filters = " ".join(params.get("fq", []))
    if "year:[2001 TO *]" not in filters or "year:[* TO 2025]" not in filters:
        raise Goal040CountError("galah count request temporal scope drifted")
    wkt = " ".join(params.get("wkt", []))
    if not all(str(value) in wkt for value in BBOX.values()):
        raise Goal040CountError("galah count request bbox scope drifted")


def _live_branch_count(branch: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    captured: list[dict[str, Any]] = []
    original = requests.request

    def recording_request(method: str, url: str, **kwargs: Any) -> requests.Response:
        response = original(method, url, **kwargs)
        if url.startswith(SERVICE["endpoint"]):
            validated = _validate_service_envelope(response)
            captured.append({"method": method.upper(), "url": url, **validated})
        return response

    requests.request = recording_request
    try:
        kwargs = (
            {"identifiers": branch["selector_value"]}
            if branch["selector_type"] in {"identifier", "identifier_union"}
            else {"taxa": branch["selector_value"]}
        )
        frame = galah.atlas_counts(
            **kwargs,
            filters=["year>=2001", "year<=2025"],
            bbox=BBOX,
            use_data_profile=False,
        )
    finally:
        requests.request = original
    if len(captured) != 1:
        raise Goal040CountError("galah count call did not yield exactly one count response")
    call = captured[0]
    _validate_actual_request(call["url"], branch)
    if list(frame.columns) != ["totalRecords"] or len(frame) != 1:
        raise Goal040CountError("galah count projection contains non-count columns or rows")
    count = int(frame.iloc[0]["totalRecords"])
    if count != call["count"]:
        raise Goal040CountError("galah projection disagrees with service count")
    request_receipt = {
        "schema_version": "1.0", "branch": branch,
        "method": call["method"], "actual_count_url": call["url"],
        "package": PACKAGE, "service": SERVICE,
        "email_transmitted": False, "authentication": False,
    }
    response_projection = {
        "schema_version": "1.0", "source": "galah.atlas_counts totalRecords projection",
        "totalRecords": count, "http_status": 200,
        "service_envelope_sha256": call["envelope_sha256"],
        "occurrence_rows_retained": 0, "coordinate_fields_retained": 0,
        "record_id_fields_retained": 0, "facet_rows_retained": 0,
        "email_retained": False,
    }
    return request_receipt, response_projection


def _validate_raw_pair(request: dict[str, Any], response: dict[str, Any], branch: dict[str, Any]) -> int:
    if request.get("branch") != branch or request.get("package") != PACKAGE or request.get("service") != SERVICE:
        raise Goal040CountError("raw count request is not branch/package/service bound")
    if request.get("email_transmitted") is not False or request.get("authentication") is not False:
        raise Goal040CountError("raw count request violates email/auth boundary")
    _validate_actual_request(request.get("actual_count_url", ""), branch)
    expected_response_keys = {
        "schema_version", "source", "totalRecords", "http_status",
        "service_envelope_sha256", "occurrence_rows_retained",
        "coordinate_fields_retained", "record_id_fields_retained",
        "facet_rows_retained", "email_retained",
    }
    if set(response) != expected_response_keys:
        raise Goal040CountError("raw count projection shape drifted")
    if response["schema_version"] != "1.0" or response["http_status"] != 200:
        raise Goal040CountError("raw count projection identity/status drifted")
    if any(response[key] != 0 for key in (
        "occurrence_rows_retained", "coordinate_fields_retained",
        "record_id_fields_retained", "facet_rows_retained",
    )) or response["email_retained"] is not False:
        raise Goal040CountError("raw count projection retained forbidden material")
    count = response["totalRecords"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise Goal040CountError("raw count projection totalRecords is malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", response["service_envelope_sha256"]):
        raise Goal040CountError("raw service-envelope checksum is malformed")
    return count


def _raw_paths(root: Path, branch_id: str) -> tuple[Path, Path]:
    raw = root / RAW_ROOT
    return raw / f"{branch_id}.request.json", raw / f"{branch_id}.response.json"


def run_count_census(root: Path) -> dict[str, Any]:
    branches = build_branch_matrix(root)
    unions = build_taxon_union_matrix(branches)
    previous = None
    if (root / MANIFEST_PATH).exists():
        previous = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    galah.galah_config(
        atlas="Australia", authenticate=False, verbose=False,
        data_profile="None", reason=4,
    )
    entries = []
    for union in unions:
        request_path, response_path = _raw_paths(root, union["branch_id"])
        if request_path.exists() != response_path.exists():
            raise Goal040CountError(f"partial resumable raw pair: {union['branch_id']}")
        if not request_path.exists():
            request, response = _live_branch_count(union)
            _write_json(request_path, request)
            _write_json(response_path, response)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        count = _validate_raw_pair(request, response, union)
        entries.append({
            "query_id": union["branch_id"], "taxon": union["taxon"],
            "logical_branch_ids": union["logical_branch_ids"],
            "query_identity_sha256": union["query_identity_sha256"],
            "conservative_bbox_prefilter_rows": count,
            "raw_request_sha256": _sha(request_path),
            "raw_response_sha256": _sha(response_path),
            "service_envelope_sha256": response["service_envelope_sha256"],
        })

    alias_probes = []
    for branch in [item for item in branches if item["branch_kind"] == "evidence_backed_alias"]:
        request_path, response_path = _raw_paths(root, branch["branch_id"])
        if not request_path.exists():
            request, response = _live_branch_count(branch)
            _write_json(request_path, request)
            _write_json(response_path, response)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        count = _validate_raw_pair(request, response, branch)
        parent_count = next(item["conservative_bbox_prefilter_rows"] for item in entries if item["taxon"] == branch["taxon"])
        if count != parent_count:
            raise Goal040CountError("alias did not resolve to the already-counted accepted-parent query")
        alias_probes.append({
            "branch_id": branch["branch_id"], "taxon": branch["taxon"],
            "query_identity_sha256": branch["query_identity_sha256"],
            "resolved_parent_bbox_prefilter_rows": count,
            "deduplication": "not_added_to_taxon_union_because_galah_resolved_the_alias_to_the_same_accepted_parent_LSID",
            "raw_request_sha256": _sha(request_path),
            "raw_response_sha256": _sha(response_path),
            "service_envelope_sha256": response["service_envelope_sha256"],
        })

    taxon_counts = {entry["taxon"]: entry["conservative_bbox_prefilter_rows"] for entry in entries}
    total = sum(taxon_counts.values())
    projected = total * BYTES_PER_ROW * WORKING_MULTIPLIER
    same_count_snapshot = previous is not None and previous.get("summary", {}).get(
        "conservative_bbox_prefilter_rows"
    ) == total and previous.get("summary", {}).get("maximum_single_taxon_rows") == max(
        taxon_counts.values()
    )
    free = (
        previous["resource_criteria"]["free_bytes_after_projection"]["free_bytes_at_gate"]
        if same_count_snapshot else shutil.disk_usage(root).free
    )
    free_after = free - projected
    criteria = {
        "total_rows": {"observed": total, "maximum": MAX_TOTAL, "pass": total <= MAX_TOTAL},
        "single_taxon_rows": {
            "maximum_observed": max(taxon_counts.values()), "maximum": MAX_TAXON,
            "pass": max(taxon_counts.values()) <= MAX_TAXON,
        },
        "projected_working_bytes": {
            "rows": total, "bytes_per_row": BYTES_PER_ROW,
            "working_space_multiplier": WORKING_MULTIPLIER, "observed": projected,
            "pass": projected == total * BYTES_PER_ROW * WORKING_MULTIPLIER,
        },
        "free_bytes_after_projection": {
            "free_bytes_at_gate": free, "projected_working_bytes": projected,
            "observed": free_after, "minimum": MIN_FREE_AFTER,
            "pass": free_after >= MIN_FREE_AFTER,
        },
    }
    passed = all(item["pass"] for item in criteria.values())
    manifest = {
        "schema_version": "1.0", "goal_id": "goal040-se-mammal-acquisition-feasibility",
        "stage": "count-census",
        "retrieved_at": previous["retrieved_at"] if same_count_snapshot else _now(),
        "result": "pass_acquisition_authorised" if passed else "stop_resource_route_decision",
        "count_interpretation": "bbox_prefilter_unique_indexed_rows_from_each_taxon_OR_union_before_exact_IBRA_ASGS_Geofabric_mask_and_local_QA",
        "union_policy": "one_galah_OR_LSID_count_per_taxon_for_parent_plus_reviewed_descendants; verified_alias_resolving_to_same_parent_not_double_added",
        "record_identity_policy": {
            "canonical_deduplication_key": "recordID_required",
            "auxiliary_field": "occurrenceID_optional_not_a_deduplication_key",
            "cross_union_rule": "duplicate_recordID_values_across_materialised_parent_descendant_alias_queries_collapse_once",
            "evidence": "Goal017 public ALA snapshot had recordID complete and unique in 50,834/50,834 rows while occurrenceID was materially incomplete, including 10,240/33,442 populated devil rows",
        },
        "package": PACKAGE, "service": SERVICE,
        "scope": {
            "years_inclusive": YEARS, "bbox_prefilter": BBOX,
            "disableAllQualityFilters": True,
            "exact_domain_cell_id_sha256": json.loads((root / BOUNDARY_PATH).read_text())["exact_study_domain"]["grid"]["eligible_cell_id_sha256"],
            "local_QA_after_acquisition": True,
        },
        "bindings": {
            "taxon_ledger": {"path": str(LEDGER_PATH), "sha256": _sha(root / LEDGER_PATH)},
            "domain_manifest": {"path": str(BOUNDARY_PATH), "sha256": _sha(root / BOUNDARY_PATH)},
            "contract": {"path": str(CONFIG_PATH), "sha256": _sha(root / CONFIG_PATH)},
            "ordered_branch_matrix_sha256": hashlib.sha256(_canonical(branches)).hexdigest(),
            "ordered_taxon_union_matrix_sha256": hashlib.sha256(_canonical(unions)).hexdigest(),
        },
        "taxa": [
            {"taxon": taxon, "conservative_bbox_prefilter_rows": taxon_counts[taxon]}
            for taxon in sorted(taxon_counts)
        ],
        "taxon_queries": entries,
        "alias_probes": alias_probes,
        "request_accounting": {
            "canonical_retained_count_estimates": CANONICAL_RETAINED_ESTIMATES,
            "superseded_exploratory_branch_estimates": SUPERSEDED_EXPLORATORY_ESTIMATES,
            "total_unique_live_metadata_only_count_requests": TOTAL_UNIQUE_LIVE_REQUESTS,
            "superseded_receipts_retained_ignored": True,
            "pageSize_for_every_request": 0,
            "occurrence_rows_returned_across_all_requests": 0,
            "accounting_note": "45 initial branch calls included the Macropus alias retained canonically; adding 21 taxon-union calls yields 22 canonical estimates, 44 superseded estimates, and 66 unique live requests",
        },
        "branch_coverage": [
            {"branch_id": branch["branch_id"], "taxon": branch["taxon"], "branch_kind": branch["branch_kind"], "query_identity_sha256": branch["query_identity_sha256"]}
            for branch in branches
        ],
        "summary": {
            "taxa": len(taxon_counts), "branches": len(branches),
            "service_count_requests": len(entries) + len(alias_probes),
            "conservative_bbox_prefilter_rows": total,
            "maximum_single_taxon_rows": max(taxon_counts.values()),
        },
        "resource_criteria": criteria,
        "privacy": {
            "occurrence_rows_retained": 0, "coordinates_retained": 0,
            "record_ids_retained": 0, "facets_retained": 0,
            "email_retained": False, "raw_files_tracked": False,
        },
    }
    _write_json(root / MANIFEST_PATH, manifest)
    validate_count_census(root, require_raw=True)
    return {"result": manifest["result"], **manifest["summary"], "resource_criteria": criteria}


def validate_count_census(root: Path, *, require_raw: bool = True) -> dict[str, Any]:
    manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    branches = build_branch_matrix(root)
    unions = build_taxon_union_matrix(branches)
    if manifest.get("stage") != "count-census" or manifest.get("package") != PACKAGE or manifest.get("service") != SERVICE:
        raise Goal040CountError("count manifest identity/package/service drifted")
    bindings = manifest.get("bindings", {})
    for key, path in (("taxon_ledger", LEDGER_PATH), ("domain_manifest", BOUNDARY_PATH), ("contract", CONFIG_PATH)):
        if bindings.get(key) != {"path": str(path), "sha256": _sha(root / path)}:
            raise Goal040CountError(f"count manifest {key} binding drifted")
    if bindings.get("ordered_branch_matrix_sha256") != hashlib.sha256(_canonical(branches)).hexdigest():
        raise Goal040CountError("count manifest branch-matrix binding drifted")
    if bindings.get("ordered_taxon_union_matrix_sha256") != hashlib.sha256(_canonical(unions)).hexdigest():
        raise Goal040CountError("count manifest taxon-union binding drifted")
    coverage = manifest.get("branch_coverage")
    expected_coverage = [
        {"branch_id": branch["branch_id"], "taxon": branch["taxon"], "branch_kind": branch["branch_kind"], "query_identity_sha256": branch["query_identity_sha256"]}
        for branch in branches
    ]
    if coverage != expected_coverage:
        raise Goal040CountError("count manifest branch coverage is incomplete")
    entries = manifest.get("taxon_queries")
    if not isinstance(entries, list) or len(entries) != 21:
        raise Goal040CountError("count manifest taxon-query coverage is incomplete")
    expected = {union["branch_id"]: union for union in unions}
    observed_counts: dict[str, int] = {}
    for entry in entries:
        union = expected.pop(entry.get("query_id"), None)
        if union is None or entry.get("taxon") != union["taxon"] or entry.get("logical_branch_ids") != union["logical_branch_ids"] or entry.get("query_identity_sha256") != union["query_identity_sha256"]:
            raise Goal040CountError("count manifest taxon-query identity drifted")
        count = entry.get("conservative_bbox_prefilter_rows")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise Goal040CountError("count manifest branch count is malformed")
        if require_raw:
            request_path, response_path = _raw_paths(root, union["branch_id"])
            if not request_path.exists() or not response_path.exists() or _sha(request_path) != entry.get("raw_request_sha256") or _sha(response_path) != entry.get("raw_response_sha256"):
                raise Goal040CountError("raw count receipt/response binding drifted")
            request = json.loads(request_path.read_text(encoding="utf-8"))
            response = json.loads(response_path.read_text(encoding="utf-8"))
            if _validate_raw_pair(request, response, union) != count or response["service_envelope_sha256"] != entry.get("service_envelope_sha256"):
                raise Goal040CountError("raw count replay disagrees with tracked branch")
        observed_counts[union["taxon"]] = count
    if expected or len(observed_counts) != 21:
        raise Goal040CountError("count manifest omits frozen branches or taxa")
    aliases = [branch for branch in branches if branch["branch_kind"] == "evidence_backed_alias"]
    probes = manifest.get("alias_probes")
    if not isinstance(probes, list) or len(probes) != len(aliases):
        raise Goal040CountError("count manifest alias-probe coverage drifted")
    for probe, branch in zip(probes, aliases):
        if probe.get("branch_id") != branch["branch_id"] or probe.get("taxon") != branch["taxon"] or probe.get("query_identity_sha256") != branch["query_identity_sha256"]:
            raise Goal040CountError("count manifest alias identity drifted")
        if probe.get("resolved_parent_bbox_prefilter_rows") != observed_counts[branch["taxon"]]:
            raise Goal040CountError("alias count differs from resolved accepted-parent union")
        if require_raw:
            request_path, response_path = _raw_paths(root, branch["branch_id"])
            if _sha(request_path) != probe.get("raw_request_sha256") or _sha(response_path) != probe.get("raw_response_sha256"):
                raise Goal040CountError("raw alias probe binding drifted")
            request = json.loads(request_path.read_text(encoding="utf-8"))
            response = json.loads(response_path.read_text(encoding="utf-8"))
            if _validate_raw_pair(request, response, branch) != probe["resolved_parent_bbox_prefilter_rows"]:
                raise Goal040CountError("raw alias replay disagrees with tracked probe")
    if manifest.get("request_accounting") != {
        "canonical_retained_count_estimates": CANONICAL_RETAINED_ESTIMATES,
        "superseded_exploratory_branch_estimates": SUPERSEDED_EXPLORATORY_ESTIMATES,
        "total_unique_live_metadata_only_count_requests": TOTAL_UNIQUE_LIVE_REQUESTS,
        "superseded_receipts_retained_ignored": True,
        "pageSize_for_every_request": 0,
        "occurrence_rows_returned_across_all_requests": 0,
        "accounting_note": "45 initial branch calls included the Macropus alias retained canonically; adding 21 taxon-union calls yields 22 canonical estimates, 44 superseded estimates, and 66 unique live requests",
    }:
        raise Goal040CountError("historical live-request accounting drifted")
    taxa = {item["taxon"]: item["conservative_bbox_prefilter_rows"] for item in manifest.get("taxa", [])}
    if taxa != observed_counts:
        raise Goal040CountError("count manifest taxon aggregation drifted")
    total = sum(observed_counts.values())
    maximum = max(observed_counts.values())
    if manifest.get("summary") != {
        "taxa": 21, "branches": len(branches),
        "service_count_requests": 21 + len(aliases),
        "conservative_bbox_prefilter_rows": total,
        "maximum_single_taxon_rows": maximum,
    }:
        raise Goal040CountError("count manifest summary arithmetic drifted")
    criteria = manifest.get("resource_criteria", {})
    projected = total * BYTES_PER_ROW * WORKING_MULTIPLIER
    if criteria.get("total_rows") != {"observed": total, "maximum": MAX_TOTAL, "pass": total <= MAX_TOTAL}:
        raise Goal040CountError("total-row resource criterion drifted")
    if criteria.get("single_taxon_rows") != {"maximum_observed": maximum, "maximum": MAX_TAXON, "pass": maximum <= MAX_TAXON}:
        raise Goal040CountError("single-taxon resource criterion drifted")
    if criteria.get("projected_working_bytes") != {"rows": total, "bytes_per_row": BYTES_PER_ROW, "working_space_multiplier": WORKING_MULTIPLIER, "observed": projected, "pass": True}:
        raise Goal040CountError("projected-working-byte arithmetic drifted")
    disk = criteria.get("free_bytes_after_projection", {})
    if disk.get("projected_working_bytes") != projected or disk.get("observed") != disk.get("free_bytes_at_gate") - projected or disk.get("minimum") != MIN_FREE_AFTER or disk.get("pass") != (disk.get("observed") >= MIN_FREE_AFTER):
        raise Goal040CountError("free-space resource criterion drifted")
    passed = all(item["pass"] for item in criteria.values())
    expected_result = "pass_acquisition_authorised" if passed else "stop_resource_route_decision"
    if manifest.get("result") != expected_result:
        raise Goal040CountError("count resource decision drifted")
    if manifest.get("privacy") != {"occurrence_rows_retained": 0, "coordinates_retained": 0, "record_ids_retained": 0, "facets_retained": 0, "email_retained": False, "raw_files_tracked": False}:
        raise Goal040CountError("count manifest privacy boundary drifted")
    text = (root / MANIFEST_PATH).read_text(encoding="utf-8")
    if "@" in text or re.search(r'"(?:decimalLatitude|decimalLongitude)"', text, re.I):
        raise Goal040CountError("tracked count manifest contains forbidden row/email material")
    if manifest.get("record_identity_policy") != {
        "canonical_deduplication_key": "recordID_required",
        "auxiliary_field": "occurrenceID_optional_not_a_deduplication_key",
        "cross_union_rule": "duplicate_recordID_values_across_materialised_parent_descendant_alias_queries_collapse_once",
        "evidence": "Goal017 public ALA snapshot had recordID complete and unique in 50,834/50,834 rows while occurrenceID was materially incomplete, including 10,240/33,442 populated devil rows",
    }:
        raise Goal040CountError("record identity/deduplication contract drifted")
    return {"result": expected_result, **manifest["summary"], "resource_criteria": criteria}
