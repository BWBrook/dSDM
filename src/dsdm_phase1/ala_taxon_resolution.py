"""Offline validation and bounded retrieval for official ALA taxon evidence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .contracts import ValidationError, load_phase1_decision_bundle


NAME_MATCHING_BASE = "https://namematching-ws.ala.org.au"
BIE_BASE = "https://bie-ws.ala.org.au/ws"
OPENAPI_URL = "https://docs.ala.org.au/openapi/specs/namematching.json"
EXPECTED_SPECIES_COUNT = 9
EXPECTED_PACKAGE_ID = "ala_taxon_resolution_evidence"
EXPECTED_OFFICIAL_SURFACES = {"name_matching": NAME_MATCHING_BASE, "bie": BIE_BASE}
EXPECTED_FAMILIES = {
    "thylogale_billardierii": "Macropodidae",
    "notamacropus_rufogriseus": "Macropodidae",
    "macropus_giganteus": "Macropodidae",
    "trichosurus_vulpecula": "Phalangeridae",
    "pseudocheirus_peregrinus": "Pseudocheiridae",
    "vombatus_ursinus": "Vombatidae",
    "sarcophilus_harrisii": "Dasyuridae",
    "dasyurus_maculatus": "Dasyuridae",
    "dasyurus_viverrinus": "Dasyuridae",
}
_AFD_CONCEPT_RE = re.compile(r"https://biodiversity\.org\.au/afd/taxa/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def retrieve_ala_taxon_evidence(
    *, output_dir: Path | str, bundle_path: Path | str
) -> dict[str, Any]:
    """Retrieve compact official metadata evidence and write a manifest.

    Only name-matching, taxon-ID round-trip, BIE GUID, and BIE species-detail
    requests are made. No occurrence endpoint is used.
    """

    out = Path(output_dir)
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    bundle = load_phase1_decision_bundle(bundle_path)
    timestamp = _utc_now()
    records: list[dict[str, Any]] = []

    openapi = _request_json(OPENAPI_URL)
    openapi_path = raw / "namematching_openapi.json"
    _write_json(openapi_path, openapi["body"])
    openapi_sha = _sha256(openapi_path)

    for species in bundle["species"]:
        species_id = species["species_id"]
        query = species["scientific_name"]
        params = {"scientificName": query, "kingdom": "Animalia", "class": "Mammalia", "rank": "species"}
        search = _request_json(f"{NAME_MATCHING_BASE}/api/searchByClassification?{urlencode(params)}")
        simple_params = {"q": query}
        simple = _request_json(f"{NAME_MATCHING_BASE}/api/search?{urlencode(simple_params)}")
        selected = search["body"]
        concept_id = selected.get("taxonConceptID")
        if not concept_id:
            raise ValidationError(f"ALA classification response lacks concept ID for {species_id}")
        roundtrip_url = f"{NAME_MATCHING_BASE}/api/getByTaxonID?{urlencode({'taxonID': concept_id})}"
        roundtrip = _request_json(roundtrip_url)
        guid = _request_json(f"{BIE_BASE}/guid/{quote(query, safe='')}")
        bie_guid = guid["body"]
        detail_guid = bie_guid[0].get("acceptedIdentifier") if isinstance(bie_guid, list) and bie_guid else None
        if detail_guid != concept_id:
            raise ValidationError(f"BIE accepted concept mismatch for {species_id}")
        detail = _request_json(f"{BIE_BASE}/species/{quote(concept_id, safe='')}")
        detail_body = detail["body"]

        alias_evidence: list[dict[str, Any]] = []
        if species_id == "notamacropus_rufogriseus":
            alias = "Macropus rufogriseus"
            alias_response = _request_json(f"{BIE_BASE}/guid/{quote(alias, safe='')}")
            _write_json(raw / species_id / "alias_macropus_rufogriseus.json", alias_response["body"])
            alias_sha = _sha256(raw / species_id / "alias_macropus_rufogriseus.json")
            alias_body = alias_response["body"]
            alias_match = alias_body[0] if isinstance(alias_body, list) and alias_body else {}
            alias_evidence.append({
                "alias": alias,
                "accepted_identifier": alias_match.get("acceptedIdentifier"),
                "path": str((raw / species_id / "alias_macropus_rufogriseus.json").relative_to(out)),
                "response_sha256": alias_sha,
                "method": "GET",
                "url": alias_response["url"],
                "status": alias_response["status"],
                "content_type": alias_response.get("content_type"),
            })

        species_dir = raw / species_id
        species_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "classification": (search, "classification.json"),
            "simple_search": (simple, "simple_search.json"),
            "taxon_roundtrip": (roundtrip, "taxon_roundtrip.json"),
            "bie_guid": (guid, "bie_guid.json"),
            "bie_species": (detail, "bie_species.json"),
        }
        file_meta: dict[str, Any] = {}
        for label, (response, filename) in files.items():
            path = species_dir / filename
            _write_json(path, response["body"])
            file_meta[label] = {
                "path": str(path.relative_to(out)),
                "sha256": _sha256(path),
                "method": "GET",
                "status": response["status"],
                "url": response["url"],
                "content_type": response.get("content_type"),
            }

        records.append({
            "species_id": species_id,
            "query": query,
            "classification_file": file_meta["classification"],
            "simple_search_file": file_meta["simple_search"],
            "taxon_roundtrip_file": file_meta["taxon_roundtrip"],
            "bie_guid_file": file_meta["bie_guid"],
            "bie_species_file": file_meta["bie_species"],
            "alias_evidence": alias_evidence,
            "retrieved_at": timestamp,
        })

    manifest = {
        "package_id": EXPECTED_PACKAGE_ID,
        "retrieved_at": timestamp,
        "species_count": len(records),
        "openapi": {
            "url": OPENAPI_URL,
            "path": str(openapi_path.relative_to(out)),
            "sha256": openapi_sha,
            "method": "GET",
            "status": openapi["status"],
            "content_type": openapi.get("content_type"),
        },
        "official_surfaces": {"name_matching": NAME_MATCHING_BASE, "bie": BIE_BASE},
        "records": records,
    }
    _write_json(out / "manifest.json", manifest)
    candidates = build_candidate_contract(out, bundle)
    _write_json(out / "candidates.json", candidates)
    return validate_evidence_package(out, bundle=bundle)


def build_candidate_contract(package_dir: Path | str, bundle: dict[str, Any]) -> dict[str, Any]:
    """Build normalized candidates from stored raw snapshots, without network."""

    package = Path(package_dir)
    manifest = _load_json(package / "manifest.json")
    candidates: list[dict[str, Any]] = []
    for record in manifest.get("records", []):
        species = next((s for s in bundle["species"] if s["species_id"] == record["species_id"]), None)
        if species is None:
            raise ValidationError(f"unknown species in evidence: {record.get('species_id')}")
        candidates.append(_reconstruct_candidate(package, record, species))
    return {"contract_version": "1.0", "bundle_id": bundle["bundle_id"], "candidates": candidates}


def validate_evidence_package(package_dir: Path | str, *, bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate manifest, checksums, candidate contract, and nine-species gate offline."""

    package = Path(package_dir)
    manifest = _load_json(package / "manifest.json")
    candidates = _load_json(package / "candidates.json")
    if manifest.get("package_id") != EXPECTED_PACKAGE_ID:
        raise ValidationError("evidence package identity mismatch")
    if manifest.get("species_count") != EXPECTED_SPECIES_COUNT or len(manifest.get("records", [])) != EXPECTED_SPECIES_COUNT:
        raise ValidationError("evidence package must contain exactly nine species records")
    if manifest.get("official_surfaces") != EXPECTED_OFFICIAL_SURFACES:
        raise ValidationError("official ALA surface identity mismatch")
    retrieved_at = manifest.get("retrieved_at")
    if not _valid_utc_timestamp(retrieved_at):
        raise ValidationError("manifest retrieval timestamp is not UTC")
    if candidates.get("bundle_id") != bundle.get("bundle_id"):
        raise ValidationError("candidate bundle identity mismatch")
    if candidates.get("contract_version") != "1.0":
        raise ValidationError("candidate contract version mismatch")
    expected_ids = {s["species_id"] for s in bundle["species"]}
    observed_ids = {c.get("species_id") for c in candidates.get("candidates", [])}
    if len(candidates.get("candidates", [])) != EXPECTED_SPECIES_COUNT or observed_ids != expected_ids:
        raise ValidationError("candidate species IDs do not match authoritative nine")
    record_ids = [record.get("species_id") for record in manifest.get("records", [])]
    if record_ids != [s["species_id"] for s in bundle["species"]]:
        raise ValidationError("manifest species IDs do not match authoritative nine")
    openapi = manifest.get("openapi")
    if not isinstance(openapi, dict):
        raise ValidationError("OpenAPI metadata missing")
    _validate_response_metadata(
        package,
        openapi,
        expected_url=OPENAPI_URL,
        label="OpenAPI",
        retrieved_at=retrieved_at,
    )
    openapi_body = _load_json(_safe_path(package, openapi["path"]))
    if not isinstance(openapi_body, dict) or not openapi_body or not isinstance(openapi_body.get("paths"), dict):
        raise ValidationError("OpenAPI response is empty or malformed")
    required_paths = {"/api/search", "/api/searchByClassification", "/api/getByTaxonID"}
    if not required_paths.issubset(openapi_body["paths"]):
        raise ValidationError("OpenAPI response lacks an endpoint used by this package")
    seen_concepts: set[str] = set()
    for record in manifest["records"]:
        species = next(s for s in bundle["species"] if s["species_id"] == record["species_id"])
        _validate_record_metadata(package, manifest, record, species)
        rebuilt = _reconstruct_candidate(package, record, species)
        candidate = next(c for c in candidates["candidates"] if c["species_id"] == record["species_id"])
        concept = candidate.get("taxon_concept_id")
        if not concept or concept in seen_concepts:
            raise ValidationError("missing or duplicate selected concept ID")
        seen_concepts.add(concept)
        if candidate != rebuilt:
            raise ValidationError(f"candidate contract is not reconstructable for {record['species_id']}")
    return {"status": "validated", "species_count": len(candidates["candidates"]), "recommendable_count": sum(c["recommendation"] == "recommendable" for c in candidates["candidates"])}


def _reconstruct_candidate(package: Path, record: dict[str, Any], species: dict[str, Any]) -> dict[str, Any]:
    """Rebuild one candidate solely from the five stored responses and aliases."""

    classification = _load_json(_safe_path(package, record["classification_file"]["path"]))
    simple = _load_json(_safe_path(package, record["simple_search_file"]["path"]))
    roundtrip = _load_json(_safe_path(package, record["taxon_roundtrip_file"]["path"]))
    bie_guid = _load_json(_safe_path(package, record["bie_guid_file"]["path"]))
    bie = _load_json(_safe_path(package, record["bie_species_file"]["path"]))
    expected_name = species["scientific_name"]
    expected_family = EXPECTED_FAMILIES[species["species_id"]]
    concept = _validate_name_matching_surface(classification, expected_name, expected_family, "classification", "exactMatch")
    simple_concept = _validate_name_matching_surface(simple, expected_name, expected_family, "simple search", "exactMatch")
    if simple_concept != concept:
        raise ValidationError(f"simple search concept mismatch for {species['species_id']}")
    roundtrip_concept = _validate_name_matching_surface(
        roundtrip, expected_name, expected_family, "taxon round-trip", "taxonIdMatch", require_name_type=False
    )
    if roundtrip_concept != concept:
        raise ValidationError(f"taxon round-trip concept mismatch for {species['species_id']}")
    _validate_bie_guid(bie_guid, expected_name, concept, species["species_id"])
    accepted = _validate_bie_species(bie, expected_name, expected_family, concept, classification, species["species_id"])
    raw_synonyms = [item.get("nameString") for item in bie.get("synonyms", []) if isinstance(item, dict)]
    aliases = _validate_alias_evidence(package, record, species, concept, accepted, raw_synonyms)
    issues = classification["issues"]
    return {
        "species_id": species["species_id"],
        "query": expected_name,
        "returned_scientific_name": classification["scientificName"],
        "authorship": classification.get("scientificNameAuthorship"),
        "taxon_concept_id": concept,
        "species_id_returned": classification["speciesID"],
        "rank": classification["rank"],
        "match_type": classification["matchType"],
        "name_type": classification["nameType"],
        "synonym_type": accepted.get("taxonomicStatus"),
        "kingdom": classification["kingdom"],
        "class": classification["classs"],
        "family": classification["family"],
        "issues": issues,
        "raw_synonyms": raw_synonyms,
        "evidence_backed_aliases": aliases,
        "recommendation": "recommendable",
        "flag": None,
    }


def _validate_name_matching_surface(
    payload: Any,
    expected_name: str,
    expected_family: str,
    label: str,
    expected_match_type: str,
    *,
    require_name_type: bool = True,
) -> str:
    if not isinstance(payload, dict) or not payload:
        raise ValidationError(f"{label} response is empty or malformed")
    required = {
        "success": True,
        "scientificName": expected_name,
        "species": expected_name,
        "rank": "species",
        "kingdom": "Animalia",
        "classs": "Mammalia",
        "family": expected_family,
        "matchType": expected_match_type,
        "issues": ["noIssue"],
    }
    if require_name_type:
        required["nameType"] = "SCIENTIFIC"
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ValidationError(f"{label} field {key!r} disagrees with canonical evidence")
    concept = payload.get("taxonConceptID")
    if not isinstance(concept, str) or not _AFD_CONCEPT_RE.fullmatch(concept):
        raise ValidationError(f"{label} concept is not a unique HTTPS AFD UUID")
    if payload.get("speciesID") != concept:
        raise ValidationError(f"{label} speciesID disagrees with taxonConceptID")
    if not payload.get("scientificNameAuthorship"):
        raise ValidationError(f"{label} authorship is missing")
    return concept


def _validate_bie_guid(payload: Any, expected_name: str, concept: str, species_id: str) -> None:
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ValidationError(f"BIE GUID response is not one exact result for {species_id}")
    result = payload[0]
    expected = {
        "name": expected_name,
        "acceptedName": expected_name,
        "identifier": concept,
        "acceptedIdentifier": concept,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValidationError(f"BIE GUID field {key!r} disagrees for {species_id}")


def _validate_bie_species(
    payload: Any,
    expected_name: str,
    expected_family: str,
    concept: str,
    classification: dict[str, Any],
    species_id: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("taxonConcept"), dict):
        raise ValidationError(f"BIE species response lacks accepted taxon concept for {species_id}")
    accepted = payload["taxonConcept"]
    expected_accepted = {
        "guid": concept,
        "taxonConceptID": concept,
        "nameString": expected_name,
        "nameAuthority": "AFD",
        "rankString": "species",
        "taxonomicStatus": "accepted",
    }
    for key, value in expected_accepted.items():
        if accepted.get(key) != value:
            raise ValidationError(f"BIE accepted concept field {key!r} disagrees for {species_id}")
    detail_classification = payload.get("classification")
    if not isinstance(detail_classification, dict):
        raise ValidationError(f"BIE species classification missing for {species_id}")
    expected_detail = {
        "guid": concept,
        "speciesGuid": concept,
        "scientificName": expected_name,
        "species": expected_name,
        "kingdom": "ANIMALIA",
        "class": "MAMMALIA",
        "family": expected_family.upper(),
    }
    for key, value in expected_detail.items():
        if detail_classification.get(key) != value:
            raise ValidationError(f"BIE classification field {key!r} disagrees for {species_id}")
    identifiers = payload.get("identifiers")
    if not isinstance(identifiers, list) or not any(
        isinstance(item, dict)
        and item.get("identifier") == concept
        and isinstance(item.get("identifier"), str)
        and _AFD_CONCEPT_RE.fullmatch(item["identifier"])
        for item in identifiers
    ):
        raise ValidationError(f"BIE identifiers lack the accepted AFD concept for {species_id}")
    if accepted.get("nameComplete") != f"{expected_name} {classification.get('scientificNameAuthorship')}":
        raise ValidationError(f"BIE accepted name authorship disagrees for {species_id}")
    return accepted


def _validate_alias_evidence(
    package: Path,
    record: dict[str, Any],
    species: dict[str, Any],
    concept: str,
    accepted: dict[str, Any],
    raw_synonyms: list[Any],
) -> list[str]:
    expected_aliases = ["Macropus rufogriseus"] if species["species_id"] == "notamacropus_rufogriseus" else []
    entries = record.get("alias_evidence", [])
    if len(entries) != len(expected_aliases):
        raise ValidationError(f"alias evidence cardinality mismatch for {species['species_id']}")
    aliases: list[str] = []
    for expected_alias, entry in zip(expected_aliases, entries):
        expected_url = f"{BIE_BASE}/guid/{quote(expected_alias, safe='')}"
        if (
            entry.get("alias") != expected_alias
            or entry.get("url") != expected_url
            or entry.get("accepted_identifier") != concept
        ):
            raise ValidationError("alias metadata is not bound to its exact official query")
        metadata = dict(entry)
        metadata["sha256"] = metadata.get("response_sha256")
        _validate_response_metadata(package, metadata, expected_url=expected_url, label="alias", retrieved_at=record["retrieved_at"])
        body = _load_json(_safe_path(package, entry["path"]))
        _validate_bie_alias_result(body, expected_alias, accepted, concept)
        if expected_alias not in raw_synonyms:
            raise ValidationError("promoted alias is absent from raw synonym evidence")
        aliases.append(expected_alias)
    return aliases


def _validate_bie_alias_result(payload: Any, alias: str, accepted: dict[str, Any], concept: str) -> None:
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ValidationError("alias BIE GUID response is not unique")
    result = payload[0]
    if (
        result.get("name") != alias
        or result.get("identifier") == concept
        or not _AFD_CONCEPT_RE.fullmatch(result.get("identifier", ""))
    ):
        raise ValidationError("alias BIE result is not a distinct name accepted by the selected concept")
    if result.get("acceptedIdentifier") != concept or result.get("acceptedName") != accepted.get("nameComplete"):
        raise ValidationError("alias BIE result accepted concept/name mismatch")


def _validate_record_metadata(package: Path, manifest: dict[str, Any], record: dict[str, Any], species: dict[str, Any]) -> None:
    retrieved_at = manifest["retrieved_at"]
    if record.get("query") != species["scientific_name"] or record.get("retrieved_at") != retrieved_at:
        raise ValidationError(f"record query or timestamp mismatch for {species['species_id']}")
    expected_urls = _expected_urls(species["scientific_name"], _classification_concept(package, record))
    for key, expected_url in expected_urls.items():
        metadata = record.get(f"{key}_file")
        if not isinstance(metadata, dict):
            raise ValidationError(f"missing {key} response metadata for {species['species_id']}")
        _validate_response_metadata(package, metadata, expected_url=expected_url, label=key, retrieved_at=retrieved_at)
    _validate_alias_metadata_paths(package, record, retrieved_at)


def _classification_concept(package: Path, record: dict[str, Any]) -> str:
    classification = _load_json(_safe_path(package, record["classification_file"]["path"]))
    concept = classification.get("taxonConceptID")
    if not isinstance(concept, str) or not _AFD_CONCEPT_RE.fullmatch(concept):
        raise ValidationError("classification concept is missing or malformed")
    return concept


def _expected_urls(query: str, concept: str) -> dict[str, str]:
    return {
        "classification": f"{NAME_MATCHING_BASE}/api/searchByClassification?{urlencode({'scientificName': query, 'kingdom': 'Animalia', 'class': 'Mammalia', 'rank': 'species'})}",
        "simple_search": f"{NAME_MATCHING_BASE}/api/search?{urlencode({'q': query})}",
        "taxon_roundtrip": f"{NAME_MATCHING_BASE}/api/getByTaxonID?{urlencode({'taxonID': concept})}",
        "bie_guid": f"{BIE_BASE}/guid/{quote(query, safe='')}",
        "bie_species": f"{BIE_BASE}/species/{quote(concept, safe='')}",
    }


def _validate_alias_metadata_paths(package: Path, record: dict[str, Any], retrieved_at: str) -> None:
    for entry in record.get("alias_evidence", []):
        if not isinstance(entry, dict) or "path" not in entry:
            raise ValidationError("alias evidence metadata is incomplete")
        _safe_path(package, entry["path"])


def _validate_response_metadata(
    package: Path,
    metadata: dict[str, Any],
    *,
    expected_url: str,
    label: str,
    retrieved_at: str,
) -> None:
    if metadata.get("method") != "GET" or metadata.get("status") != 200:
        raise ValidationError(f"{label} request method/status is not GET/200")
    if metadata.get("url") != expected_url:
        raise ValidationError(f"{label} request URL is not the expected official endpoint")
    content_type = metadata.get("content_type")
    if not isinstance(content_type, str) or not content_type.lower().startswith("application/json"):
        raise ValidationError(f"{label} response content type is not JSON")
    path = _safe_path(package, metadata.get("path"))
    if not path.exists() or not isinstance(metadata.get("sha256"), str) or _sha256(path) != metadata["sha256"]:
        raise ValidationError(f"{label} response checksum/missing response failure")


def _safe_path(package: Path, relative_path: Any) -> Path:
    if not isinstance(relative_path, str) or not relative_path or Path(relative_path).is_absolute():
        raise ValidationError("evidence path must be a package-relative path")
    root = package.resolve()
    candidate = (package / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError("evidence path escapes package root") from exc
    return candidate


def _valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _request_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "dSDM-Goal010-evidence/1.0"})
    with urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
        return {
            "url": url,
            "status": response.status,
            "body": body,
            "content_type": response.headers.get("Content-Type"),
        }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read evidence JSON: {path}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
