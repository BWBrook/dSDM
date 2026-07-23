"""Count-only ALA query-scope preflight and offline evidence validation."""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QueryScopeValidationError(ValueError):
    """Raised when the query-scope contract or evidence is unsafe/incomplete."""


OCCURRENCE_SEARCH_URL = "https://api.ala.org.au/occurrences/occurrences/search"
LEGACY_OCCURRENCE_SEARCH_URL = "https://biocache.ala.org.au/ws/occurrences/search"
DOCUMENTED_OCCURRENCE_SEARCH_URL = OCCURRENCE_SEARCH_URL
OPENAPI_SPEC_URL = "https://docs.ala.org.au/openapi/specs/biocache.json"
BIE_SPECIES_URL = "https://bie.ala.org.au/ws/species/"
BIE_CHILDREN_URL = "https://bie.ala.org.au/ws/childConcepts/"
FIELDS_METADATA_URL = "https://api.ala.org.au/occurrences/index/fields"
BIOCACHE_REPO_URL = "https://github.com/AtlasOfLivingAustralia/biocache-service"
BIOCACHE_COMMIT = "bcfb37661008dce5d3e532258458eb72d03e7530"
BIOCACHE_COMMIT_URL = f"{BIOCACHE_REPO_URL}/commit/{BIOCACHE_COMMIT}"
BIOCACHE_SOURCE_URLS = [
    f"https://raw.githubusercontent.com/AtlasOfLivingAustralia/biocache-service/{BIOCACHE_COMMIT}/src/main/java/au/org/ala/biocache/util/SearchUtils.java",
    f"https://raw.githubusercontent.com/AtlasOfLivingAustralia/biocache-service/{BIOCACHE_COMMIT}/src/main/java/au/org/ala/biocache/util/QueryFormatUtils.java",
]
SCOPE_FQ = ["stateProvince:Tasmania", "year:[2001 TO 2025]"]
PARENT_CONCEPTS = {
    "thylogale_billardierii": "https://biodiversity.org.au/afd/taxa/82e69509-af63-4502-86f7-43362b777865",
    "notamacropus_rufogriseus": "https://biodiversity.org.au/afd/taxa/c4dfafef-5192-4a3d-815c-040c393e9bca",
    "macropus_giganteus": "https://biodiversity.org.au/afd/taxa/f2f43ef9-89fd-4f89-8b06-0842e86cfe06",
    "trichosurus_vulpecula": "https://biodiversity.org.au/afd/taxa/ee2cb6a9-e17c-4ca7-8aef-76d69eb969ed",
    "pseudocheirus_peregrinus": "https://biodiversity.org.au/afd/taxa/003decd6-ec3d-468e-909d-da396a6dd1f6",
    "vombatus_ursinus": "https://biodiversity.org.au/afd/taxa/66d42847-c556-4fa3-902c-a91d9f517286",
    "sarcophilus_harrisii": "https://biodiversity.org.au/afd/taxa/c6b5ff5a-a991-4972-b5b0-4214141d5bd6",
    "dasyurus_maculatus": "https://biodiversity.org.au/afd/taxa/73c23669-c491-42d0-83b3-6fd84a03689a",
    "dasyurus_viverrinus": "https://biodiversity.org.au/afd/taxa/1e9f1b49-78b5-409d-91f2-21615ce88e9d",
}
MACROPUS_SYNONYM = "https://biodiversity.org.au/afd/taxa/6cfeb6de-600b-425e-9e8d-3cea25f8ef84"
MACROPUS_SYNONYM_NAME = "Macropus giganteus tasmaniensis"
VOMBATUS_CHILDREN = {
    "vombatus_ursinus_hirsutus": "https://biodiversity.org.au/afd/taxa/e4b74750-7541-4c67-89d1-5b5718b30ea7",
    "vombatus_ursinus_tasmaniensis": "https://biodiversity.org.au/afd/taxa/3e53b354-2b48-4a2a-af29-acd8ecdfe1e6",
    "vombatus_ursinus_ursinus": "https://biodiversity.org.au/afd/taxa/76b2b77b-6092-47dd-8de1-00e504b1e383",
}
REQUIRED_FOCAL_IDS = tuple(PARENT_CONCEPTS)
REQUIRED_RELATIONS = {
    "macropus_giganteus:macropus_giganteus_tasmaniensis",
    *(f"vombatus_ursinus:{name}" for name in VOMBATUS_CHILDREN),
}
NATIONAL_CHILD_RELATIONS = {f"national:{name}" for name in VOMBATUS_CHILDREN}
REQUIRED_RECORD_FIELDS = [
    "occurrenceID", "dataResourceUid", "dataResourceName", "datasetID", "datasetName",
    "eventDate", "year", "decimalLatitude", "decimalLongitude",
    "coordinateUncertaintyInMeters", "coordinatePrecision", "raw_scientificName",
    "raw_taxonConceptID", "scientificName", "taxonConceptID", "acceptedNameUsage",
    "acceptedNameUsageID", "taxonRank", "assertions", "license",
]
RECORD_FIELD_MAPPING = [
    {"project_field": "occurrence_id", "ala_fields": ["occurrenceID"], "required": True, "derivation": "direct", "null_rule": "reject null because occurrenceID is the deduplication key"},
    {"project_field": "source_resource_id", "ala_fields": ["dataResourceUid"], "required": True, "derivation": "direct", "null_rule": "retain null only if source is explicitly unavailable"},
    {"project_field": "source_resource_name", "ala_fields": ["dataResourceName"], "required": False, "derivation": "direct", "null_rule": "preserve null"},
    {"project_field": "source_dataset_id", "ala_fields": ["datasetID", "dataResourceUid"], "required": False, "derivation": "datasetID then dataResourceUid fallback", "null_rule": "preserve null"},
    {"project_field": "source_dataset_name", "ala_fields": ["datasetName", "dataResourceName"], "required": False, "derivation": "datasetName then dataResourceName fallback", "null_rule": "preserve null"},
    {"project_field": "event_date", "ala_fields": ["eventDate"], "required": False, "derivation": "direct", "null_rule": "preserve null; do not fabricate dates"},
    {"project_field": "year", "ala_fields": ["year", "eventDate"], "required": False, "derivation": "year direct, otherwise parse four-digit eventDate year", "null_rule": "preserve null"},
    {"project_field": "decimal_latitude", "ala_fields": ["decimalLatitude"], "required": True, "derivation": "direct", "null_rule": "exclude from spatial analysis when null or invalid"},
    {"project_field": "decimal_longitude", "ala_fields": ["decimalLongitude"], "required": True, "derivation": "direct", "null_rule": "exclude from spatial analysis when null or invalid"},
    {"project_field": "coordinate_uncertainty_m", "ala_fields": ["coordinateUncertaintyInMeters"], "required": False, "derivation": "direct", "null_rule": "preserve null as unknown"},
    {"project_field": "coordinate_precision_basis", "ala_fields": ["coordinatePrecision"], "required": False, "derivation": "reported coordinatePrecision only; otherwise unknown", "null_rule": "never infer precision from decimal digits"},
    {"project_field": "submitted_name", "ala_fields": ["raw_scientificName"], "required": False, "derivation": "direct", "null_rule": "preserve null"},
    {"project_field": "submitted_concept_id", "ala_fields": ["raw_taxonConceptID"], "required": False, "derivation": "direct", "null_rule": "preserve null"},
    {"project_field": "matched_name", "ala_fields": ["scientificName"], "required": True, "derivation": "direct", "null_rule": "reject when accepted identity is needed and null"},
    {"project_field": "matched_concept_id", "ala_fields": ["taxonConceptID"], "required": True, "derivation": "direct", "null_rule": "reject when accepted identity is needed and null"},
    {"project_field": "accepted_name", "ala_fields": ["acceptedNameUsage", "scientificName"], "required": True, "derivation": "acceptedNameUsage then scientificName fallback", "null_rule": "reject when accepted identity is needed and both null"},
    {"project_field": "accepted_concept_id", "ala_fields": ["acceptedNameUsageID", "taxonConceptID"], "required": True, "derivation": "acceptedNameUsageID then taxonConceptID fallback", "null_rule": "reject when accepted identity is needed and both null"},
    {"project_field": "accepted_rank", "ala_fields": ["taxonRank"], "required": True, "derivation": "direct", "null_rule": "reject when accepted identity is needed and null"},
    {"project_field": "assertions", "ala_fields": ["assertions"], "required": False, "derivation": "direct", "null_rule": "preserve null"},
    {"project_field": "license", "ala_fields": ["license"], "required": False, "derivation": "direct", "null_rule": "preserve null and record provenance"},
    {"project_field": "provenance", "ala_fields": [], "required": True, "derivation": "run metadata: retrieval timestamp, profile ID, canonical request, response checksum", "null_rule": "never null"},
]
FUTURE_FL = REQUIRED_RECORD_FIELDS.copy()
PROFILE_ROOT_KEYS = {
    "schema_version", "profile_id", "status", "occurrence_search_endpoint", "documented_gateway_endpoint",
    "method", "page_size", "start", "disable_all_quality_filters", "default_query_mode", "query_template",
    "future_fl", "scope", "focal_species_ids", "fallback", "containment_rule", "record_field_mapping",
}
REQUIRED_SEARCH_PARAMETER_SPECS = {
    "q": {"name": "q", "in": "query", "required": False, "schema": {"type": "string"}},
    "fq": {"name": "fq", "in": "query", "required": False, "schema": {"type": "array", "items": {"type": "string"}}},
    "fl": {"name": "fl", "in": "query", "required": False, "schema": {"type": "string"}},
    "start": {"name": "start", "in": "query", "required": False, "schema": {"type": "integer", "format": "int32"}},
    "pageSize": {"name": "pageSize", "in": "query", "required": False, "schema": {"type": "integer", "format": "int32"}},
    "facet": {"name": "facet", "in": "query", "required": False, "schema": {"type": "boolean"}},
    "disableAllQualityFilters": {"name": "disableAllQualityFilters", "in": "query", "required": False, "schema": {"type": "boolean"}},
}


def request_parameters(query: str, *, extra_fq: tuple[str, ...] = (), scope_fq: tuple[str, ...] = tuple(SCOPE_FQ)) -> list[list[str]]:
    """Return deterministic count-only parameters for one taxon concept."""

    return [
        ["q", query],
        *[["fq", value] for value in extra_fq],
        *[["fq", value] for value in scope_fq],
        ["pageSize", "0"],
        ["start", "0"],
        ["facet", "false"],
        ["disableAllQualityFilters", "true"],
    ]


def request_url(query: str, *, extra_fq: tuple[str, ...] = (), scope_fq: tuple[str, ...] = tuple(SCOPE_FQ)) -> str:
    return OCCURRENCE_SEARCH_URL + "?" + urllib.parse.urlencode(
        [tuple(item) for item in request_parameters(query, extra_fq=extra_fq, scope_fq=scope_fq)]
    )


def canonical_probe_specs() -> list[dict[str, Any]]:
    """Return the immutable 24-row probe matrix and its exact request bindings."""
    concepts: list[tuple[str, str, str, str, tuple[str, ...], tuple[str, ...], str]] = [
        (key, "parent", concept, f'taxonConceptID:"{concept}"', (), tuple(SCOPE_FQ), "tasmania_2001_2025")
        for key, concept in PARENT_CONCEPTS.items()
    ]
    concepts += [("macropus_giganteus_tasmaniensis_id", "synonym_id", MACROPUS_SYNONYM, f'taxonConceptID:"{MACROPUS_SYNONYM}"', (), tuple(SCOPE_FQ), "tasmania_2001_2025")]
    concepts += [("macropus_giganteus_tasmaniensis_name", "synonym_name", MACROPUS_SYNONYM, f'taxa:"{MACROPUS_SYNONYM_NAME}"', (), tuple(SCOPE_FQ), "tasmania_2001_2025")]
    concepts += [(key, "child", concept, f'taxonConceptID:"{concept}"', (), tuple(SCOPE_FQ), "tasmania_2001_2025") for key, concept in VOMBATUS_CHILDREN.items()]
    concepts += [
        ("macropus_giganteus:macropus_giganteus_tasmaniensis_intersection", "intersection", MACROPUS_SYNONYM, f'taxa:"{MACROPUS_SYNONYM_NAME}"', (f'taxonConceptID:"{PARENT_CONCEPTS["macropus_giganteus"]}"',), tuple(SCOPE_FQ), "tasmania_2001_2025"),
        *[(f"vombatus_ursinus:{key}_intersection", "intersection", concept, f'taxonConceptID:"{concept}"', (f'taxonConceptID:"{PARENT_CONCEPTS["vombatus_ursinus"]}"',), tuple(SCOPE_FQ), "tasmania_2001_2025") for key, concept in VOMBATUS_CHILDREN.items()],
        *[(f"national:{key}", "national_control_child", concept, f'taxonConceptID:"{concept}"', (), (), "national_control") for key, concept in VOMBATUS_CHILDREN.items()],
        *[(f"national:{key}_intersection", "national_control_intersection", concept, f'taxonConceptID:"{concept}"', (f'taxonConceptID:"{PARENT_CONCEPTS["vombatus_ursinus"]}"',), (), "national_control") for key, concept in VOMBATUS_CHILDREN.items()],
    ]
    specs = []
    for key, kind, concept, query, extra_fq, scope_fq, scope in concepts:
        params = request_parameters(query, extra_fq=extra_fq, scope_fq=scope_fq)
        specs.append({
            "key": key, "kind": kind, "concept_id": concept, "query": query,
            "extra_fq": list(extra_fq), "scope": scope, "scope_fq": list(scope_fq),
            "endpoint": OCCURRENCE_SEARCH_URL, "method": "GET", "http_status": 200,
            "request": params, "request_url": request_url(query, extra_fq=extra_fq, scope_fq=scope_fq),
        })
    return specs


def validate_request_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict) or set(profile) != PROFILE_ROOT_KEYS:
        raise QueryScopeValidationError("request profile root shape drifted")
    if profile.get("schema_version") != "1.0" or profile.get("profile_id") != "ala-tasmania-2001-2025-count-only-preflight" or profile.get("status") != "preflight_ready_pending_live_acquisition":
        raise QueryScopeValidationError("request profile identity or state drifted")
    if profile.get("occurrence_search_endpoint") != OCCURRENCE_SEARCH_URL:
        raise QueryScopeValidationError("request profile endpoint is not the approved public count-only surface")
    if profile.get("documented_gateway_endpoint") != DOCUMENTED_OCCURRENCE_SEARCH_URL:
        raise QueryScopeValidationError("request profile documented endpoint drifted")
    if profile.get("method") != "GET" or profile.get("page_size") != 0 or profile.get("start") != 0 or profile.get("disable_all_quality_filters") is not True:
        raise QueryScopeValidationError("request profile must enforce GET pageSize=0 start=0")
    if profile.get("scope") != {
        "temporal": {"field": "year", "start": 2001, "end": 2025, "inclusive": True},
        "spatial": {"field": "stateProvince", "value": "Tasmania", "role": "broad_indexed_prefilter_before_canonical_grid_boundary"},
    }:
        raise QueryScopeValidationError("request profile scope is not the approved inclusive Tasmania prefilter")
    if profile.get("focal_species_ids") != list(REQUIRED_FOCAL_IDS):
        raise QueryScopeValidationError("request profile must cover the ordered nine focal species")
    fallback = profile.get("fallback")
    if not isinstance(fallback, dict) or fallback.get("mode") != "explicit_parent_plus_required_alias_and_child_union" or fallback.get("deduplication_key") != "occurrenceID":
        raise QueryScopeValidationError("explicit union fallback and occurrenceID deduplication are mandatory")
    if fallback.get("parent_concepts") != PARENT_CONCEPTS or fallback.get("macropus_synonym") != MACROPUS_SYNONYM or fallback.get("macropus_synonym_name") != MACROPUS_SYNONYM_NAME or fallback.get("vombatus_children") != VOMBATUS_CHILDREN:
        raise QueryScopeValidationError("fallback concept set is incomplete or drifted")
    if profile.get("default_query_mode") != "parent_species_expansion":
        raise QueryScopeValidationError("default query mode must be the runtime-proven parent species expansion")
    if "facets" in profile or "facet_limit" in profile:
        raise QueryScopeValidationError("facet controls are forbidden in the count-only profile")
    if profile.get("query_template") != {
        "endpoint": OCCURRENCE_SEARCH_URL, "method": "GET", "q": "<taxon_query>",
        "fq": ["<extra_parent_filter>", *SCOPE_FQ], "pageSize": 0, "start": 0,
        "facet": False, "disableAllQualityFilters": True,
    }:
        raise QueryScopeValidationError("future query template drifted")
    if profile.get("future_fl") != FUTURE_FL:
        raise QueryScopeValidationError("future retrieval field set drifted")
    if profile.get("record_field_mapping") != RECORD_FIELD_MAPPING:
        raise QueryScopeValidationError("structured occurrence field mapping is incomplete or drifted")
    if profile.get("containment_rule") != {
        "method": "direct_descendant_count_vs_parent_filtered_intersection_count",
        "positive_relation_requires_exact_count_equality": True,
        "zero_scoped_relation_requires_positive_national_control": True,
        "facets_retained": False,
    }:
        raise QueryScopeValidationError("containment rule is weak or incomplete")
    return {"focal_species_count": len(REQUIRED_FOCAL_IDS), "query_mode": profile["default_query_mode"], "fallback_mode": fallback["mode"]}


def _sanitize_response(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise QueryScopeValidationError("occurrence response must be an object")
    allowed_keys = {
        "pageSize", "startIndex", "totalRecords", "sort", "dir", "status",
        "occurrences", "facetResults", "query", "urlParameters", "queryTitle",
        "activeFacetMap", "activeFacetObj",
    }
    if set(response) - allowed_keys:
        raise QueryScopeValidationError("occurrence response contains unapproved payload fields")
    if response.get("status") != "OK":
        raise QueryScopeValidationError("occurrence response status is not OK")
    if response.get("pageSize") != 0 or response.get("startIndex") != 0:
        raise QueryScopeValidationError("occurrence response did not enforce zero-row pagination")
    occurrences = response.get("occurrences")
    if not isinstance(occurrences, list) or occurrences:
        raise QueryScopeValidationError("occurrence response contains record rows")
    total = response.get("totalRecords")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise QueryScopeValidationError("occurrence response totalRecords is malformed")
    facets = response.get("facetResults")
    if not isinstance(facets, list):
        raise QueryScopeValidationError("occurrence response facetResults is malformed")
    if facets:
        raise QueryScopeValidationError("count-only response retained unexpected facet payload")
    return {
        "status": "OK",
        "pageSize": 0,
        "startIndex": 0,
        "totalRecords": total,
        "occurrences": [],
        "facetResults": [],
        "query": response.get("query"),
    }


def _validate_query_echo(response: dict[str, Any], spec: dict[str, Any]) -> None:
    echo = response.get("query")
    if not isinstance(echo, str) or not echo.startswith("?"):
        raise QueryScopeValidationError("response query echo is missing")
    observed = urllib.parse.parse_qsl(echo[1:], keep_blank_values=True)
    expected = [("q", spec["query"]), *[("fq", value) for value in [*spec["extra_fq"], *spec["scope_fq"]]], ("disableAllQualityFilters", "true")]
    allowed_optional = {"pageSize", "start", "facet"}
    if any(key not in {item[0] for item in expected} | allowed_optional for key, _ in observed):
        raise QueryScopeValidationError("response query echo contains unapproved parameters")
    optional_expected = {"pageSize": "0", "start": "0", "facet": "false"}
    for key, value in observed:
        if key in optional_expected and value != optional_expected[key]:
            raise QueryScopeValidationError(f"response query echo optional control {key} drifted")
    observed_required = [(key, value) for key, value in observed if key not in allowed_optional]
    if sorted(observed_required) != sorted(expected):
        raise QueryScopeValidationError("response query echo drifted from canonical q/fq/quality semantics")


def validate_evidence_package(package_dir: Path | str, profile: dict[str, Any]) -> dict[str, Any]:
    """Validate the checksummed, record-free package and all semantic bindings."""
    validate_request_profile(profile)
    package = Path(package_dir)
    manifest = _load(package / "manifest.json")
    files = manifest.get("files") if isinstance(manifest, dict) else None
    expected_files = {"metadata.json", "probes.json", "review.json"}
    if not isinstance(files, list) or {entry.get("path") for entry in files if isinstance(entry, dict)} != expected_files:
        raise QueryScopeValidationError("evidence manifest must checksum metadata, probes, and review exactly")
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise QueryScopeValidationError("evidence manifest entry is malformed")
        relative = entry["path"]
        path = (package / relative).resolve()
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts or package.resolve() not in path.parents:
            raise QueryScopeValidationError("evidence manifest path is unsafe")
        if not path.exists() or _sha256(path) != entry["sha256"]:
            raise QueryScopeValidationError(f"evidence checksum mismatch: {relative}")
    probes = _load(package / "probes.json")
    if not isinstance(probes, dict) or set(probes) != {"retrieved_at_utc", "probes", "relations", "national_relations"}:
        raise QueryScopeValidationError("probe evidence shape is incomplete")
    if not isinstance(probes["retrieved_at_utc"], str) or not probes["retrieved_at_utc"].endswith("Z"):
        raise QueryScopeValidationError("probe evidence timestamp is missing")
    rows = probes["probes"]
    specs = canonical_probe_specs()
    if not isinstance(rows, list) or len(rows) != len(specs):
        raise QueryScopeValidationError("required canonical probe matrix is incomplete")
    by_key: dict[str, dict[str, Any]] = {}
    for probe, spec in zip(rows, specs):
        required_shape = {"key", "kind", "concept_id", "query", "extra_fq", "scope", "scope_fq", "endpoint", "method", "http_status", "request", "request_url", "response", "total_records"}
        if not isinstance(probe, dict) or set(probe) != required_shape:
            raise QueryScopeValidationError("probe row shape is incomplete")
        for field in ("key", "kind", "concept_id", "query", "extra_fq", "scope", "scope_fq", "endpoint", "method", "http_status", "request", "request_url"):
            if probe[field] != spec[field]:
                raise QueryScopeValidationError(f"probe {probe.get('key')} canonical {field} binding drifted")
        if probe["key"] in by_key:
            raise QueryScopeValidationError("probe identity is duplicated")
        response = probe["response"]
        if _sanitize_response(response) != response or probe["total_records"] != response["totalRecords"]:
            raise QueryScopeValidationError("probe summary does not match its record-free response")
        _validate_query_echo(response, spec)
        by_key[probe["key"]] = probe
    if {key for key, probe in by_key.items() if probe["kind"] == "parent"} != set(REQUIRED_FOCAL_IDS):
        raise QueryScopeValidationError("all nine focal parent probes are required")
    relations = probes["relations"]
    if by_key["macropus_giganteus_tasmaniensis_id"]["total_records"] != 0:
        raise QueryScopeValidationError("Macropus synonym-ID zero coverage control drifted")
    if not isinstance(relations, list) or {relation.get("key") for relation in relations} != REQUIRED_RELATIONS:
        raise QueryScopeValidationError("required parent/descendant containment relations are incomplete")
    expected_relations = []
    scoped_zeros = []
    for relation in relations:
        if set(relation) != {"key", "parent_key", "descendant_key", "direct_count", "intersection_count", "status", "method", "national_control_key"}:
            raise QueryScopeValidationError("containment relation shape is incomplete")
        direct = by_key.get(relation["descendant_key"])
        intersection = by_key.get(relation["key"] + "_intersection")
        if direct is None or intersection is None or direct["total_records"] != relation["direct_count"] or intersection["total_records"] != relation["intersection_count"]:
            raise QueryScopeValidationError("containment relation does not link to direct/intersection counts")
        if relation["method"] != "direct_descendant_count_vs_parent_filtered_intersection_count":
            raise QueryScopeValidationError("containment method is not decisive")
        if relation["direct_count"] > 0:
            status = "contained_in_scope" if relation["direct_count"] == relation["intersection_count"] else "unresolved_positive_mismatch"
            expected_control = None
            if status != "contained_in_scope":
                raise QueryScopeValidationError("positive descendant count is not fully contained in parent intersection")
        else:
            expected_control = f"national:{relation['descendant_key']}"
            scoped_zeros.append(relation["key"])
            status = "contained_via_national_control"
        expected_relations.append((relation["key"], status, expected_control))
        if relation["status"] != status or relation["national_control_key"] != expected_control:
            raise QueryScopeValidationError("containment relation status/control drifted")
    national_relations = probes.get("national_relations")
    if not isinstance(national_relations, list) or {relation.get("key") for relation in national_relations} != NATIONAL_CHILD_RELATIONS:
        raise QueryScopeValidationError("national Vombatus containment controls are incomplete")
    for relation in national_relations:
        if set(relation) != {"key", "child_key", "direct_count", "intersection_count", "status", "method"}:
            raise QueryScopeValidationError("national containment relation shape is incomplete")
        direct = by_key.get(relation["key"]); intersection = by_key.get(relation["key"] + "_intersection")
        if direct is None or intersection is None or direct["total_records"] != relation["direct_count"] or intersection["total_records"] != relation["intersection_count"] or relation["method"] != "direct_descendant_count_vs_parent_filtered_intersection_count" or relation["direct_count"] <= 0 or relation["direct_count"] != relation["intersection_count"] or relation["status"] != "contained_in_national_control":
            raise QueryScopeValidationError("national control does not prove positive containment")
    metadata = _load(package / "metadata.json")
    _validate_metadata(metadata, profile)
    review = _load(package / "review.json")
    probe_time = _parse_utc(probes["retrieved_at_utc"])
    metadata_time = _parse_utc(metadata["retrieved_at_utc"])
    fields_time = _parse_utc(metadata["fields_metadata"]["retrieved_at_utc"])
    review_time = _parse_utc(review.get("reviewed_at_utc"))
    if review.get("scope_snapshot") != probes["retrieved_at_utc"] or review_time < max(probe_time, metadata_time, fields_time):
        raise QueryScopeValidationError("evidence chronology or scope snapshot is impossible")
    expected_parent_counts = {key: by_key[key]["total_records"] for key in REQUIRED_FOCAL_IDS}
    expected_observations = {relation["key"]: {"descendant_count": relation["direct_count"], "parent_intersection_count": relation["intersection_count"], "status": relation["status"], "national_control_key": relation["national_control_key"]} for relation in relations}
    expected_national = {relation["key"]: {"direct_count": relation["direct_count"], "intersection_count": relation["intersection_count"], "status": relation["status"]} for relation in national_relations}
    if review.get("query_mode") != "parent_species_expansion" or review.get("containment_unresolved") is not False or review.get("parent_counts") != expected_parent_counts or review.get("required_relation_observations") != expected_observations or review.get("national_control_observations") != expected_national or review.get("scoped_zero_count_relations") != scoped_zeros or review.get("record_rows_retained") != 0 or review.get("coordinates_retained") is not False or review.get("facets_retained") is not False or review.get("bulk_execution") is not False or review.get("endpoint") != OCCURRENCE_SEARCH_URL or review.get("method") != "GET" or review.get("disable_all_quality_filters") is not True or review.get("fallback_mode") != profile["fallback"]["mode"] or review.get("deduplication_key") != "occurrenceID" or review.get("probe_count") != len(rows):
        raise QueryScopeValidationError("review does not match the canonical probe-derived decision")
    expected_readiness_caveat = "Preflight is complete and ready for bounded acquisition design/execution. No occurrence rows, coordinates, facets, or bulk records were retained. P1-D008 remains a separate camera prerequisite; the zero Tasmania hirsutus and synonym-ID probes remain acquisition-time assertions rather than stable ecological results."
    if review.get("readiness_status") != "preflight_complete_ready_for_bounded_acquisition_design_execution" or review.get("readiness_caveat") != expected_readiness_caveat or "later_bulk_acquisition_ready_apart_from_P1_D008" in review:
        raise QueryScopeValidationError("review readiness status is not honest")
    if set(review.get("acquisition_time_assertions", [])) != {"vombatus_ursinus_hirsutus_scope_coverage", "macropus_giganteus_tasmaniensis_synonym_id_coverage", "parent_expansion_runtime_coverage", "occurrenceID_deduplication"}:
        raise QueryScopeValidationError("acquisition-time assertions are incomplete")
    return {"probe_count": len(rows), "relation_count": len(relations), "national_relation_count": len(national_relations), "containment_unresolved": False, "query_mode": review["query_mode"]}


def _validate_metadata(metadata: dict[str, Any], profile: dict[str, Any]) -> None:
    if not isinstance(metadata, dict) or not isinstance(metadata.get("retrieved_at_utc"), str):
        raise QueryScopeValidationError("metadata retrieval timestamp is missing")
    official = metadata.get("official_sources")
    exact_official = {
        "openapi_spec_url": OPENAPI_SPEC_URL, "openapi_http_status": 200,
        "openapi_title": "Occurrence REST services", "openapi_version": "3.0",
        "openapi_server_base": "https://api.ala.org.au/occurrences", "openapi_operation_path": "/occurrences/search",
        "documented_gateway_occurrence_search": DOCUMENTED_OCCURRENCE_SEARCH_URL,
        "supported_route_probe_status": 200, "legacy_occurrence_search_endpoint": LEGACY_OCCURRENCE_SEARCH_URL,
        "public_occurrence_search_endpoint": OCCURRENCE_SEARCH_URL, "bie_species_endpoint": BIE_SPECIES_URL,
        "bie_child_concepts_endpoint": BIE_CHILDREN_URL,
    }
    if official != exact_official:
        raise QueryScopeValidationError("OpenAPI/current-route metadata drifted")
    parameters = metadata.get("occurrence_search_parameters")
    if not isinstance(parameters, list) or {p.get("name") for p in parameters if isinstance(p, dict)} != set(REQUIRED_SEARCH_PARAMETER_SPECS) or any(p != REQUIRED_SEARCH_PARAMETER_SPECS.get(p.get("name")) for p in parameters):
        raise QueryScopeValidationError("occurrence-search parameter metadata drifted, including fl")
    if metadata.get("scope") != {"temporal_filter": SCOPE_FQ[1], "spatial_filter": SCOPE_FQ[0], "spatial_uncertainty": "stateProvince is a broad indexed prefilter; canonical grid/coast boundary remains a later normalization gate"}:
        raise QueryScopeValidationError("metadata scope drifted")
    bie = metadata.get("bie_metadata")
    expected_synonym = {"guid": MACROPUS_SYNONYM, "nameString": MACROPUS_SYNONYM_NAME, "taxonomicStatus": "synonym", "rankString": "unranked", "acceptedConceptID": PARENT_CONCEPTS["macropus_giganteus"], "acceptedConceptName": "Macropus giganteus Shaw, 1790"}
    expected_children = [{"guid": concept, "parentGuid": PARENT_CONCEPTS["vombatus_ursinus"], "name": f"Vombatus ursinus {key.rsplit('_', 1)[-1]}", "rank": "subspecies"} for key, concept in VOMBATUS_CHILDREN.items()]
    if not isinstance(bie, dict) or bie.get("macropus_synonym") != expected_synonym or bie.get("vombatus_children") != expected_children:
        raise QueryScopeValidationError("BIE synonym/child mapping drifted")
    fields = metadata.get("fields_metadata")
    if not isinstance(fields, dict) or fields.get("url") != FIELDS_METADATA_URL or fields.get("http_status") != 200 or set(fields.get("available_fields", {})) != set(REQUIRED_RECORD_FIELDS):
        raise QueryScopeValidationError("metadata-only index field evidence is incomplete")
    for key, field in fields["available_fields"].items():
        if not isinstance(field, dict) or field.get("name") != key or field.get("indexed") is not True or field.get("stored") is not True:
            raise QueryScopeValidationError(f"metadata-only field flags drifted for {key}")
    mapping_union = {field for item in profile["record_field_mapping"] for field in item["ala_fields"]}
    if mapping_union != set(profile["future_fl"]):
        raise QueryScopeValidationError("structured mapping source-field union does not equal frozen future fl")
    lft = metadata.get("biocache_lft_expansion")
    if lft != {"repository": BIOCACHE_REPO_URL, "commit": BIOCACHE_COMMIT, "commit_url": BIOCACHE_COMMIT_URL, "source_urls": BIOCACHE_SOURCE_URLS, "implementation": "taxonConceptID is expanded through NameUsageMatch lft/rgt subtree as lft:[lft TO rgt], with taxonConceptID fallback when no subtree is available"}:
        raise QueryScopeValidationError("biocache lft/rgt source provenance drifted")
    if profile.get("future_fl") != FUTURE_FL:
        raise QueryScopeValidationError("future fl set is not frozen")


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise QueryScopeValidationError("timestamp must be ISO-8601 UTC with Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise QueryScopeValidationError("timestamp is not valid ISO-8601 UTC") from exc


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QueryScopeValidationError(f"cannot read evidence file: {path}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch_json(url: str) -> tuple[int, dict[str, str], Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "dSDM-Goal012-count-only/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.status, dict(response.headers), json.loads(response.read().decode("utf-8"))


def collect_live_package(output_dir: Path | str) -> dict[str, Any]:
    """Collect only sanitized public metadata/count-only responses."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    probes: list[dict[str, Any]] = []
    for spec in canonical_probe_specs():
        status, _, raw = _fetch_json(spec["request_url"])
        if status != 200:
            raise QueryScopeValidationError(f"count-only probe failed for {spec['key']}: HTTP {status}")
        response = _sanitize_response(raw)
        _validate_query_echo(response, spec)
        probes.append({
            **{key: spec[key] for key in ("key", "kind", "concept_id", "query", "extra_fq", "scope", "scope_fq", "endpoint", "method", "http_status", "request", "request_url")},
            "response": response,
            "total_records": response["totalRecords"],
        })
    by_key = {probe["key"]: probe for probe in probes}
    relations = []
    relation_pairs = [
        ("macropus_giganteus", "macropus_giganteus_tasmaniensis_name"),
        *(('vombatus_ursinus', child) for child in VOMBATUS_CHILDREN),
    ]
    for parent_key, child_key in relation_pairs:
        parent, child = by_key[parent_key], by_key[child_key]
        relation_descendant = child_key.removesuffix("_name") if child_key.endswith("_name") else child_key
        intersection = by_key[f"{parent_key}:{relation_descendant}_intersection"]
        relations.append({
            "key": f"{parent_key}:{relation_descendant}",
            "parent_key": parent_key,
            "descendant_key": child_key,
            "direct_count": child["total_records"],
            "intersection_count": intersection["total_records"],
            "status": "contained_in_scope" if child["total_records"] > 0 and child["total_records"] == intersection["total_records"] else "contained_via_national_control",
            "method": "direct_descendant_count_vs_parent_filtered_intersection_count",
            "national_control_key": None if child["total_records"] > 0 else f"national:{relation_descendant}",
        })
    national_relations = []
    for child_key in VOMBATUS_CHILDREN:
        direct = by_key[f"national:{child_key}"]
        intersection = by_key[f"national:{child_key}_intersection"]
        national_relations.append({
            "key": f"national:{child_key}",
            "child_key": child_key,
            "direct_count": direct["total_records"],
            "intersection_count": intersection["total_records"],
            "status": "contained_in_national_control" if direct["total_records"] > 0 and direct["total_records"] == intersection["total_records"] else "unresolved_zero_count",
            "method": "direct_descendant_count_vs_parent_filtered_intersection_count",
        })
    national_status = {r["key"]: r for r in national_relations}
    for relation in relations:
        if relation["direct_count"] == 0:
            control = national_status[relation["national_control_key"]]
            if control["status"] != "contained_in_national_control":
                relation["status"] = "unresolved_zero_count"
                relation["national_control_key"] = None
    payload = {"retrieved_at_utc": retrieved, "probes": probes, "relations": relations, "national_relations": national_relations}
    (output / "probes.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def collect_metadata(output_dir: Path | str) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    status, headers, spec = _fetch_json(OPENAPI_SPEC_URL)
    params = spec["paths"]["/occurrences/search"]["get"]["parameters"]
    status_probe, _, status_response = _fetch_json(request_url("*:*"))
    if status_probe != 200 or _sanitize_response(status_response)["occurrences"] != []:
        raise QueryScopeValidationError("supported occurrence endpoint failed the zero-row status probe")
    _, _, synonym_raw = _fetch_json(BIE_SPECIES_URL + MACROPUS_SYNONYM)
    _, _, children_raw = _fetch_json(BIE_CHILDREN_URL + PARENT_CONCEPTS["vombatus_ursinus"])
    fields_status, _, fields_raw = _fetch_json(FIELDS_METADATA_URL)
    if fields_status != 200 or not isinstance(fields_raw, list):
        raise QueryScopeValidationError("ALA index field metadata endpoint failed")
    available_fields = {field.get("name"): field for field in fields_raw if isinstance(field, dict) and field.get("name") in REQUIRED_RECORD_FIELDS}
    if set(available_fields) != set(REQUIRED_RECORD_FIELDS):
        raise QueryScopeValidationError("ALA index field metadata lacks required acquisition fields")
    synonym = synonym_raw.get("taxonConcept", {})
    if not isinstance(synonym, dict) or not isinstance(children_raw, list):
        raise QueryScopeValidationError("BIE metadata response is malformed")
    bie_metadata = {
        "macropus_synonym": {
            key: synonym.get(key)
            for key in ("guid", "nameString", "taxonomicStatus", "rankString", "acceptedConceptID", "acceptedConceptName")
        },
        "vombatus_children": [
            {key: child.get(key) for key in ("guid", "parentGuid", "name", "rank")}
            for child in children_raw
            if isinstance(child, dict)
        ],
    }
    if bie_metadata["macropus_synonym"]["acceptedConceptID"] != PARENT_CONCEPTS["macropus_giganteus"] or {child["guid"] for child in bie_metadata["vombatus_children"]} != set(VOMBATUS_CHILDREN.values()):
        raise QueryScopeValidationError("BIE metadata does not reconcile to Goal 011 concepts")
    metadata = {
        "retrieved_at_utc": retrieved,
        "official_sources": {
            "openapi_spec_url": OPENAPI_SPEC_URL,
            "openapi_http_status": status,
            "openapi_title": spec["info"]["title"],
            "openapi_version": spec["info"]["version"],
            "openapi_server_base": "https://api.ala.org.au/occurrences",
            "openapi_operation_path": "/occurrences/search",
            "documented_gateway_occurrence_search": DOCUMENTED_OCCURRENCE_SEARCH_URL,
            "supported_route_probe_status": 200,
            "legacy_occurrence_search_endpoint": LEGACY_OCCURRENCE_SEARCH_URL,
            "public_occurrence_search_endpoint": OCCURRENCE_SEARCH_URL,
            "bie_species_endpoint": BIE_SPECIES_URL,
            "bie_child_concepts_endpoint": BIE_CHILDREN_URL,
        },
        "occurrence_search_parameters": [
            {"name": p["name"], "in": p["in"], "required": p.get("required", False), "schema": p.get("schema", {})}
            for p in params
            if p["name"] in set(REQUIRED_SEARCH_PARAMETER_SPECS)
        ],
        "bie_metadata": bie_metadata,
        "scope": {"temporal_filter": SCOPE_FQ[1], "spatial_filter": SCOPE_FQ[0], "spatial_uncertainty": "stateProvince is a broad indexed prefilter; canonical grid/coast boundary remains a later normalization gate"},
        "fields_metadata": {"url": FIELDS_METADATA_URL, "http_status": fields_status, "retrieved_at_utc": retrieved, "available_fields": available_fields},
        "biocache_lft_expansion": {"repository": BIOCACHE_REPO_URL, "commit": BIOCACHE_COMMIT, "commit_url": BIOCACHE_COMMIT_URL, "source_urls": BIOCACHE_SOURCE_URLS, "implementation": "taxonConceptID is expanded through NameUsageMatch lft/rgt subtree as lft:[lft TO rgt], with taxonConceptID fallback when no subtree is available"},
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 2 or args[0] not in {"--collect", "--metadata"}:
        print("usage: python -m dsdm_phase1.ala_query_scope (--collect|--metadata) OUTPUT_DIR", file=sys.stderr)
        return 2
    if args[0] == "--collect":
        collect_live_package(args[1])
    else:
        collect_metadata(args[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
