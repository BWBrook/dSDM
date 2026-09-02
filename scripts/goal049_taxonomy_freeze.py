"""Count-free Goal 049 ALA taxonomy freeze.

The registry is prepared from the versioned biological authorities by the
Stage-A registry step.  This module deliberately only resolves names and
concept relationships; it never asks ALA for occurrence data or counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

import galah
import pandas as pd


class Goal049TaxonomyError(RuntimeError):
    """A taxonomy or provenance invariant failed."""


PRIVATE_RELATIVE = Path("data/processed/dsdm/goal049-seawfb-canonical-response")
FREEZE_RELATIVE = Path("metadata/goal049_registry_taxonomy_freeze.json")
REGISTRY_RECEIPT_RELATIVE = Path("metadata/goal049_registry_receipt.json")
AUTHORITY_RECEIPT_RELATIVE = Path("metadata/goal049_authority_receipt.json")
GOAL048_RECEIPT_RELATIVE = Path("metadata/goal048_prerequisite_freeze.json")
CONFIG_RELATIVE = Path("config/goal049_seawfb_canonical_response.json")
BIE_SPECIES = "https://bie-ws.ala.org.au/ws/species/"
BIE_CHILDREN = "https://bie.ala.org.au/ws/childConcepts/"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _private(root: Path) -> Path:
    return root / PRIVATE_RELATIVE


def _get_json(url: str) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "dSDM-Goal049/1.0"})
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read())


def _registry_rows(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    path = _private(root) / "registry.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049TaxonomyError("private Goal 049 registry is unreadable") from error
    rows = payload.get("rows") if isinstance(payload, dict) else payload if isinstance(payload, list) else None
    if rows is None and isinstance(payload, dict):
        rows = payload.get("species") or payload.get("registry")
        if isinstance(rows, dict):
            rows = rows.get("rows") or rows.get("species")
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise Goal049TaxonomyError("private Goal 049 registry has no row ledger")
    names = [_stable_name(row) for row in rows]
    if any(not name for name in names) or len(names) != len(set(names)):
        raise Goal049TaxonomyError("registry source species names are empty or duplicated")
    return payload, rows, path


def _bound_receipt(root: Path, relative: Path, label: str) -> tuple[dict[str, Any], Path]:
    path = Path(root) / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049TaxonomyError(f"{label} receipt is unreadable") from error
    if not isinstance(value, dict):
        raise Goal049TaxonomyError(f"{label} receipt is malformed")
    return value, path


def _exception_binding(root: Path, registry: dict[str, Any], registry_receipt: dict[str, Any]) -> tuple[str, str | None]:
    """Return a checksum for the exception ledger, whether embedded or private."""
    candidate = registry_receipt.get("exception_ledger") or registry.get("exception_ledger")
    if isinstance(candidate, str):
        path = Path(root) / candidate
        if path.is_file():
            return _sha(path), str(path.relative_to(root))
    if isinstance(candidate, dict):
        return _digest(candidate), None
    path = _private(root) / "exception_ledger.json"
    if path.is_file():
        return _sha(path), str(path.relative_to(root))
    # A registry receipt may explicitly attest that no exceptions were needed.
    if candidate in (None, [], {}):
        return _digest([]), None
    raise Goal049TaxonomyError("exception ledger is unreadable")


def _source_name(row: dict[str, Any]) -> str:
    for key in ("source_name", "source_species", "abd_name", "seed_name", "scientific_name"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _stable_name(row: dict[str, Any]) -> str:
    for key in ("name", "canonical_name", "species", "scientific_name", "source_name", "source_species", "seed_name"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _active(row: dict[str, Any]) -> bool:
    if "active" in row:
        return bool(row["active"])
    role_values = [row.get(key) for key in ("effort", "auxiliary", "target", "effort_donor", "focal_target_candidate")]
    present = [value for value in role_values if value is not None]
    return bool(any(value is True for value in present)) if present else True


def _goal048_seed_names(root: Path) -> list[str]:
    # The seed authority is the frozen Goal 048 configuration, not an
    # occurrence-derived ledger.
    config_path = Path(root) / "config/goal048_seawfb_bioregional_freeze.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        seeds = config["species_universes"]["ecological_candidate_names"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise Goal049TaxonomyError("Goal 048 seed configuration is unreadable") from error
    if not isinstance(seeds, list) or not seeds or any(not isinstance(seed, str) or not seed.strip() for seed in seeds):
        raise Goal049TaxonomyError("Goal 048 seed configuration is malformed")
    if len(seeds) != len(set(seeds)):
        raise Goal049TaxonomyError("Goal 048 seed configuration contains duplicates")
    return seeds


def _row_seed_names(row: dict[str, Any]) -> list[str]:
    values = row.get("seed_names", [])
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        values = []
    names = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    if len(names) != len(set(names)):
        raise Goal049TaxonomyError("registry row contains duplicate Goal 048 seed names")
    if bool(row.get("goal048_seed")) and not names:
        names = [_stable_name(row)]
    return names


def _selected_registry_rows(root: Path, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    selected = [row for row in rows if _active(row) or bool(row.get("goal048_seed"))]
    seeds = _goal048_seed_names(root)
    occurrences = {seed: [] for seed in seeds}
    for index, row in enumerate(selected):
        labels = set(_row_seed_names(row))
        for seed in seeds:
            if seed in labels:
                occurrences[seed].append(index)
    invalid = {seed: indexes for seed, indexes in occurrences.items() if len(indexes) != 1}
    if invalid:
        raise Goal049TaxonomyError(f"Goal 048 seed representation is not unique: {invalid}")
    return selected, seeds


def _as_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("results", "data", "children", "synonyms", "records"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
    return []


def _value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _concept_id(record: dict[str, Any]) -> str:
    return _value(record, "taxonConceptID", "guid", "nameGuid", "conceptID", "id") or _value(_taxon_concept(record), "taxonConceptID", "guid", "nameGuid", "conceptID", "id")


def _accepted_concept_id(record: dict[str, Any]) -> str:
    return _value(record, "acceptedConceptID", "acceptedConceptId", "acceptedGuid") or _value(_taxon_concept(record), "acceptedConceptID", "acceptedConceptId", "acceptedGuid")


def _taxon_concept(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("taxonConcept")
    return value if isinstance(value, dict) else record


def _status(record: dict[str, Any]) -> str:
    return _value(_taxon_concept(record), "taxonomicStatus", "status").lower()


def _rank(record: dict[str, Any]) -> str:
    return _value(_taxon_concept(record), "rank", "rankString", "taxonRank").lower()


def _accepted_name(record: dict[str, Any], fallback: str) -> str:
    return _value(_taxon_concept(record), "scientificName", "nameString", "name", "Species Name") or fallback


def _explicit_name_resolutions(config_path: Path) -> dict[str, str]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049TaxonomyError("Goal 049 config is unreadable") from error
    taxonomy = config.get("taxonomy", {})
    mapping = taxonomy.get("explicit_name_resolutions", {}) if isinstance(taxonomy, dict) else {}
    if mapping is None:
        return {}
    if not isinstance(mapping, dict):
        raise Goal049TaxonomyError("taxonomy.explicit_name_resolutions must be an object")
    result: dict[str, str] = {}
    for input_name, lookup_name in mapping.items():
        if not isinstance(input_name, str) or not input_name.strip() or not isinstance(lookup_name, str) or not lookup_name.strip():
            raise Goal049TaxonomyError("taxonomy.explicit_name_resolutions contains an invalid mapping")
        result[input_name.strip()] = lookup_name.strip()
    return result


def _classification(record: dict[str, Any]) -> dict[str, Any]:
    for container in (record, _taxon_concept(record)):
        value = container.get("classification")
        if isinstance(value, dict):
            return value
    return {}


def _identifier_url(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return "https://biodiversity.org.au/afd/taxa/" + value


def _species_parent_evidence(record: dict[str, Any]) -> tuple[str, str]:
    concept = _taxon_concept(record)
    classification = _classification(record)
    species_guid = _value(classification, "speciesGuid", "speciesConceptID", "speciesTaxonConceptID")
    parent_guid = _value(concept, "parentGuid", "parentConceptID", "parentTaxonConceptID")
    if species_guid and parent_guid and _identifier_url(species_guid) != _identifier_url(parent_guid):
        raise Goal049TaxonomyError("BIE subspecies has inconsistent species parent evidence")
    candidate = species_guid or parent_guid
    if not candidate:
        raise Goal049TaxonomyError("BIE subspecies has no species parent evidence")
    return candidate, "classification.speciesGuid" if species_guid else "parentGuid"


def _validated_parent_detail(parent: str, name: str) -> dict[str, Any]:
    try:
        detail = _get_json(BIE_SPECIES + quote(parent, safe=""))
    except Exception as error:
        raise Goal049TaxonomyError(f"BIE parent detail failed: {name}") from error
    concept = _taxon_concept(detail)
    detail_id = _concept_id(concept) or parent
    accepted = _accepted_concept_id(concept)
    detail_status = _status(detail)
    detail_rank = _rank(detail)
    if accepted and _identifier_url(accepted) != _identifier_url(parent):
        raise Goal049TaxonomyError(f"ALA parent does not round-trip to itself: {name}")
    if _identifier_url(detail_id) != _identifier_url(parent) and not accepted:
        raise Goal049TaxonomyError(f"ALA parent identifier is unstable: {name}")
    if detail_status not in {"accepted", "valid"}:
        raise Goal049TaxonomyError(f"ALA parent is not accepted: {name}")
    if detail_rank != "species":
        raise Goal049TaxonomyError(f"ALA parent is not species rank: {name}")
    return detail


def _resolve_parent(name: str, lookup_name: str | None = None, *, explicit_mapping: bool = False) -> tuple[str, str, dict[str, Any], tuple[str, str, dict[str, Any]] | None, str]:
    lookup_name = lookup_name or name
    try:
        matches = _as_records(galah.search_taxa(taxa=lookup_name))
    except Exception as error:
        raise Goal049TaxonomyError(f"ALA taxonomy search failed: {lookup_name}") from error
    if not matches:
        raise Goal049TaxonomyError(f"unresolved ALA parent: {lookup_name}")
    if len(matches) != 1:
        raise Goal049TaxonomyError(f"ALA parent is unresolved or ambiguous: {lookup_name}")

    candidates: dict[str, dict[str, Any]] = {}
    for match in matches:
        identifier = _concept_id(match)
        accepted = _accepted_concept_id(match) or identifier
        if not accepted:
            continue
        status = _status(match)
        rank = _rank(match)
        if status and status not in {"accepted", "valid"} and not _accepted_concept_id(match):
            continue
        if rank and rank not in {"species", "subspecies"} and not _accepted_concept_id(match):
            continue
        candidates[accepted] = match
    if len(candidates) != 1:
        raise Goal049TaxonomyError(f"ALA parent is unresolved or ambiguous: {lookup_name}")
    parent = next(iter(candidates))
    match = candidates[parent]
    rank = _rank(match)
    matched_descendant: tuple[str, str, dict[str, Any]] | None = None
    basis = "explicit_name_resolution" if explicit_mapping else "registry_name"
    if rank == "subspecies":
        identifier = _concept_id(match)
        if not identifier or _value(match, "matchType", "match_type").lower() not in {"", "exactmatch"}:
            raise Goal049TaxonomyError(f"ALA subspecies match is not an exact accepted concept: {lookup_name}")
        try:
            matched_detail = _get_json(BIE_SPECIES + quote(identifier, safe=""))
        except Exception as error:
            raise Goal049TaxonomyError(f"BIE matched subspecies detail failed: {lookup_name}") from error
        matched_concept = _taxon_concept(matched_detail)
        if _status(matched_detail) not in {"accepted", "valid"} or _rank(matched_detail) == "species":
            raise Goal049TaxonomyError(f"ALA subspecies match is not accepted: {lookup_name}")
        if (_concept_id(matched_concept) or identifier) != identifier or _accepted_concept_id(matched_concept) not in {"", identifier}:
            raise Goal049TaxonomyError(f"ALA subspecies identifier is unstable: {lookup_name}")
        parent, evidence = _species_parent_evidence(matched_detail)
        detail = _validated_parent_detail(parent, lookup_name)
        matched_descendant = (identifier, _accepted_name(matched_detail, lookup_name), matched_detail)
        basis = f"{basis}+{evidence}"
    else:
        detail = _validated_parent_detail(parent, lookup_name)
    return parent, _accepted_name(detail, lookup_name), detail, matched_descendant, basis


def _child_records(payload: Any) -> list[dict[str, Any]]:
    records = _as_records(payload)
    # Some BIE responses nest descendants rather than returning a flat list.
    output: list[dict[str, Any]] = []
    pending = list(records)
    while pending:
        record = pending.pop(0)
        output.append(record)
        for key in ("children", "descendants"):
            if isinstance(record.get(key), list):
                pending.extend(item for item in record[key] if isinstance(item, dict))
    return output


def _descendants(parent: str, detail: dict[str, Any], *, include_details: bool = False) -> Any:
    try:
        payload = _get_json(BIE_CHILDREN + quote(parent, safe=""))
    except Exception as error:
        raise Goal049TaxonomyError(f"BIE descendant lookup failed: {parent}") from error
    descendants: dict[str, str] = {}
    descendant_payloads: dict[str, dict[str, Any]] = {}
    candidates: list[tuple[dict[str, Any], str, str, str]] = []
    for child in _child_records(payload):
        identifier = _concept_id(child)
        if not identifier or identifier == parent:
            continue
        status = _status(child)
        if status and status not in {"accepted", "valid"}:
            continue
        accepted = _accepted_concept_id(child)
        if accepted and accepted != identifier:
            continue
        rank = _rank(child)
        if rank == "species":
            continue
        try:
            roundtrip = _get_json(BIE_SPECIES + quote(identifier, safe=""))
        except Exception as error:
            raise Goal049TaxonomyError(f"BIE descendant detail failed: {identifier}") from error
        roundtrip_concept = _taxon_concept(roundtrip)
        roundtrip_status = _status(roundtrip)
        roundtrip_parent = _value(roundtrip_concept, "parentGuid", "parentConceptID", "parentTaxonConceptID")
        if roundtrip_status not in {"accepted", "valid"} or not roundtrip_parent or _rank(roundtrip) == "species":
            raise Goal049TaxonomyError(f"descendant does not round-trip to an accepted parent: {identifier}")
        if _accepted_concept_id(roundtrip_concept) not in {"", identifier}:
            continue
        parent_id = roundtrip_parent
        candidates.append((roundtrip, identifier, parent_id, _accepted_name(roundtrip, _value(child, "name", "scientificName", "nameString"))))
    included = {parent}
    remaining = candidates
    while remaining:
        next_remaining: list[tuple[dict[str, Any], str, str, str]] = []
        progressed = False
        for child, identifier, parent_id, name in remaining:
            if not parent_id or parent_id in included:
                descendants[identifier] = name
                descendant_payloads[identifier] = child
                included.add(identifier)
                progressed = True
            else:
                next_remaining.append((child, identifier, parent_id, name))
        if not progressed:
            break
        remaining = next_remaining
    result = sorted((name, identifier) for identifier, name in descendants.items())
    if include_details:
        return result, [descendant_payloads[identifier] for _, identifier in result]
    return result


def _aliases(details: Iterable[dict[str, Any]], accepted_ids: set[str]) -> tuple[list[tuple[str, str]], int]:
    aliases: dict[str, str] = {}
    excluded = 0
    for detail in details:
        for synonym in _as_records(detail.get("synonyms", [])):
            identifier = _concept_id(synonym)
            name = _value(synonym, "nameString", "name", "scientificName")
            if not identifier or not name:
                raise Goal049TaxonomyError("ALA synonym record is unresolved")
            if "/" in name:
                excluded += 1
                continue
            try:
                roundtrip = _get_json(BIE_SPECIES + quote(identifier, safe=""))
            except Exception as error:
                raise Goal049TaxonomyError(f"BIE synonym detail failed: {identifier}") from error
            target = _accepted_concept_id(roundtrip)
            if not target:
                raise Goal049TaxonomyError(f"ALA synonym has no acceptedConceptID: {identifier}")
            if target not in accepted_ids:
                continue
            status = _status(roundtrip) or _status(synonym)
            if status and status not in {"synonym", "accepted", "valid"}:
                continue
            previous = aliases.get(identifier)
            if previous is not None and previous != name:
                raise Goal049TaxonomyError(f"conflicting synonym identifier: {identifier}")
            aliases[identifier] = name
    return sorted((name, identifier) for identifier, name in aliases.items()), excluded


def taxonomy_one(row: dict[str, Any], explicit_name_resolutions: dict[str, str] | None = None) -> dict[str, Any]:
    name = _stable_name(row)
    mapping = explicit_name_resolutions or {}
    lookup_name = mapping.get(name, name)
    if not isinstance(lookup_name, str) or not lookup_name.strip():
        raise Goal049TaxonomyError(f"explicit ALA lookup name is empty: {name}")
    parent, accepted_name, detail, matched_descendant, resolution_basis = _resolve_parent(name, lookup_name, explicit_mapping=name in mapping)
    descendants, descendant_details = _descendants(parent, detail, include_details=True)
    if matched_descendant is not None:
        identifier, descendant_name, descendant_detail = matched_descendant
        detail_by_id = {value: detail_item for (_, value), detail_item in zip(descendants, descendant_details)}
        existing = set(detail_by_id)
        if identifier not in existing:
            detail_by_id[identifier] = descendant_detail
            descendants = sorted([*descendants, (descendant_name, identifier)])
            descendant_details = [detail_by_id[value] for _, value in descendants]
        elif not any(value == identifier and descendant_name == name_value for name_value, value in descendants):
            raise Goal049TaxonomyError(f"ALA matched subspecies name conflicts with descendants: {name}")
    accepted_ids = {parent} | {identifier for _, identifier in descendants}
    aliases, excluded_aliases = _aliases([detail, *descendant_details], accepted_ids)
    identifiers = [parent] + [identifier for _, identifier in descendants] + [identifier for _, identifier in aliases]
    if len(identifiers) != len(set(identifiers)):
        raise Goal049TaxonomyError(f"duplicate identifier within union: {name}")
    return {
        "seed_name": name,
        "species": name,
        "source_name": _source_name(row) or name,
        "seed_names": _row_seed_names(row),
        "name_resolution": {"input_name": name, "lookup_name": lookup_name, "basis": resolution_basis},
        "accepted_name": accepted_name,
        "parent": parent,
        "descendants": descendants,
        "aliases": aliases,
        "ordered_identifiers": identifiers,
        "active": _active(row),
        "roles": {key: bool(row[key]) for key in ("effort", "auxiliary", "target") if key in row},
        "excluded_composite_alias_count": excluded_aliases,
        "unresolved_alias_count": 0,
    }


def freeze_taxonomy(root: Path) -> dict[str, Any]:
    root = Path(root)
    config_path = root / CONFIG_RELATIVE
    registry, registry_rows, registry_path = _registry_rows(root)
    if not config_path.is_file():
        raise Goal049TaxonomyError("Goal 049 config is missing")
    explicit_name_resolutions = _explicit_name_resolutions(config_path)
    registry_receipt, registry_receipt_path = _bound_receipt(root, REGISTRY_RECEIPT_RELATIVE, "registry")
    authority_receipt, authority_receipt_path = _bound_receipt(root, AUTHORITY_RECEIPT_RELATIVE, "authority")
    goal048_receipt, goal048_receipt_path = _bound_receipt(root, GOAL048_RECEIPT_RELATIVE, "Goal 048 prerequisite")
    registry_status = registry_receipt.get("status") or registry.get("status")
    if registry_status not in {"frozen_response_blind", "frozen_count_free", "passed", "complete_count_free"}:
        raise Goal049TaxonomyError("registry receipt is not genuinely frozen or passed")
    registry_receipt_sha = registry_receipt.get("private_registry_sha256") or registry_receipt.get("registry_private_sha256") or registry_receipt.get("registry_sha256")
    registry_reference = registry_receipt.get("private_registry") or registry_receipt.get("registry_private")
    if registry_reference and Path(root, registry_reference) != registry_path:
        raise Goal049TaxonomyError("registry receipt points to a different private registry")
    if registry_receipt_sha and registry_receipt_sha != _sha(registry_path):
        raise Goal049TaxonomyError("registry receipt private hash drift")
    exception_sha, exception_path = _exception_binding(root, registry, registry_receipt)
    selected_registry_rows, seed_names = _selected_registry_rows(root, registry_rows)
    galah.galah_config(atlas="Australia", authenticate=False, verbose=False)
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(partial(taxonomy_one, explicit_name_resolutions=explicit_name_resolutions), selected_registry_rows))
    parents = [row["parent"] for row in rows]
    identifiers = [identifier for row in rows for identifier in row["ordered_identifiers"]]
    if len(parents) != len(set(parents)):
        raise Goal049TaxonomyError("source species parent collision")
    if len(identifiers) != len(set(identifiers)):
        raise Goal049TaxonomyError("taxonomy identifier collision across species")
    payload = {
        "schema_version": "goal049-taxonomy-freeze-v1",
        "status": "frozen_count_free",
        "galah_version": getattr(galah, "__version__", "unknown"),
        "registry_sha256": _sha(registry_path),
        "registry_semantic_sha256": _digest(registry),
        "registry_receipt_sha256": _sha(registry_receipt_path),
        "authority_receipt_sha256": _sha(authority_receipt_path),
        "goal048_prerequisite_sha256": _sha(goal048_receipt_path),
        "exception_ledger_sha256": exception_sha,
        **({"exception_ledger": exception_path} if exception_path else {}),
        "species_count": len(rows),
        "active_species_count": sum(row["active"] for row in rows),
        "goal048_seed_count": len(seed_names),
        "goal048_seed_names": seed_names,
        "explicit_name_resolutions": explicit_name_resolutions,
        "name_resolution_sha256": _digest([row["name_resolution"] for row in rows]),
        "name_resolutions": [row["name_resolution"] for row in rows],
        "parent_count": len(parents),
        "descendant_count": sum(len(row["descendants"]) for row in rows),
        "alias_count": sum(len(row["aliases"]) for row in rows),
        "excluded_composite_alias_count": sum(row["excluded_composite_alias_count"] for row in rows),
        "unresolved_alias_count": sum(row["unresolved_alias_count"] for row in rows),
        "rows": rows,
        "ledger_sha256": _digest(rows),
        "occurrence_support_queried": False,
    }
    taxonomy_path = _private(root) / "taxonomy_freeze.json"
    _atomic_write(taxonomy_path, payload)
    receipt = {
        "schema_version": "goal049-registry-taxonomy-freeze-receipt-v1",
        "status": "passed",
        "stage": "stage_a",
        "config_sha256": _sha(config_path),
        "registry_sha256": _sha(registry_path),
        "registry_semantic_sha256": _digest(registry),
        "registry_receipt": str(registry_receipt_path.relative_to(root)),
        "registry_receipt_sha256": _sha(registry_receipt_path),
        "authority_receipt": str(authority_receipt_path.relative_to(root)),
        "authority_receipt_sha256": _sha(authority_receipt_path),
        "goal048_prerequisite": str(goal048_receipt_path.relative_to(root)),
        "goal048_prerequisite_sha256": _sha(goal048_receipt_path),
        "exception_ledger_sha256": exception_sha,
        **({"exception_ledger": exception_path} if exception_path else {}),
        "taxonomy_private_receipt": str(taxonomy_path.relative_to(root)),
        "taxonomy_private_sha256": _sha(taxonomy_path),
        "species_count": len(rows),
        "active_species_count": sum(row["active"] for row in rows),
        "goal048_seed_count": len(seed_names),
        "goal048_seed_names": seed_names,
        "explicit_name_resolutions": explicit_name_resolutions,
        "name_resolution_sha256": _digest([row["name_resolution"] for row in rows]),
        "name_resolutions": [row["name_resolution"] for row in rows],
        "parent_count": len(parents),
        "descendant_count": sum(len(row["descendants"]) for row in rows),
        "alias_count": sum(len(row["aliases"]) for row in rows),
        "unresolved_alias_count": sum(row["unresolved_alias_count"] for row in rows),
        "source_species_sha256": _digest([row["source_name"] for row in rows]),
        "occurrence_support_queried": False,
        "occurrence_rows_downloaded": 0,
        "model_outcome_counter": 0,
    }
    _atomic_write(root / FREEZE_RELATIVE, receipt)
    return receipt


def validate_taxonomy_freeze(root: Path) -> dict[str, Any]:
    root = Path(root)
    receipt_path = root / FREEZE_RELATIVE
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        taxonomy_path = root / receipt["taxonomy_private_receipt"]
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        registry_payload, registry_rows, registry_path = _registry_rows(root)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise Goal049TaxonomyError("Goal 049 taxonomy receipt is unreadable") from error
    config_path = root / CONFIG_RELATIVE
    explicit_name_resolutions = _explicit_name_resolutions(config_path)
    if receipt.get("status") not in {"passed", "passed_stage_a", "frozen_count_free"} or taxonomy.get("status") != "frozen_count_free":
        raise Goal049TaxonomyError("Goal 049 Stage A taxonomy freeze is not passed")
    registry_receipt, registry_receipt_path = _bound_receipt(root, REGISTRY_RECEIPT_RELATIVE, "registry")
    authority_receipt, authority_receipt_path = _bound_receipt(root, AUTHORITY_RECEIPT_RELATIVE, "authority")
    goal048_receipt, goal048_receipt_path = _bound_receipt(root, GOAL048_RECEIPT_RELATIVE, "Goal 048 prerequisite")
    exception_sha, exception_path = _exception_binding(root, json.loads(registry_path.read_text(encoding="utf-8")), registry_receipt)
    registry_reference = registry_receipt.get("private_registry") or registry_receipt.get("registry_private")
    registry_receipt_sha = registry_receipt.get("private_registry_sha256") or registry_receipt.get("registry_private_sha256") or registry_receipt.get("registry_sha256")
    if (registry_reference and Path(root, registry_reference) != registry_path) or (registry_receipt_sha and registry_receipt_sha != _sha(registry_path)):
        raise Goal049TaxonomyError("registry receipt private binding drift")
    registry_status = registry_receipt.get("status") or registry_payload.get("status")
    if registry_status not in {"frozen_response_blind", "frozen_count_free", "passed", "complete_count_free"}:
        raise Goal049TaxonomyError("registry receipt is not genuinely frozen or passed")
    if receipt.get("taxonomy_private_sha256") != _sha(taxonomy_path) or receipt.get("registry_sha256") != _sha(registry_path) or receipt.get("config_sha256") != _sha(config_path) or receipt.get("registry_receipt_sha256") != _sha(registry_receipt_path) or receipt.get("authority_receipt_sha256") != _sha(authority_receipt_path) or receipt.get("goal048_prerequisite_sha256") != _sha(goal048_receipt_path) or receipt.get("exception_ledger_sha256") != exception_sha or taxonomy.get("registry_sha256") != _sha(registry_path) or taxonomy.get("ledger_sha256") != _digest(taxonomy.get("rows")):
        raise Goal049TaxonomyError("Goal 049 taxonomy provenance checksum drift")
    expected_name_resolutions = [row.get("name_resolution") for row in taxonomy.get("rows", [])]
    if taxonomy.get("explicit_name_resolutions") != explicit_name_resolutions or receipt.get("explicit_name_resolutions") != explicit_name_resolutions or taxonomy.get("name_resolution_sha256") != _digest(expected_name_resolutions) or receipt.get("name_resolution_sha256") != _digest(expected_name_resolutions) or receipt.get("name_resolutions") != expected_name_resolutions:
        raise Goal049TaxonomyError("Goal 049 taxonomy name-resolution provenance drift")
    rows = taxonomy.get("rows")
    selected_registry_rows, seed_names = _selected_registry_rows(root, registry_rows)
    if not isinstance(rows, list) or len(rows) != len(selected_registry_rows) or [row.get("species") for row in rows] != [_stable_name(row) for row in selected_registry_rows] or [row.get("source_name") for row in rows] != [_source_name(row) or _stable_name(row) for row in selected_registry_rows]:
        raise Goal049TaxonomyError("Goal 049 taxonomy row count drift")
    for registry_row, taxonomy_row in zip(selected_registry_rows, rows):
        input_name = _stable_name(registry_row)
        lookup_name = explicit_name_resolutions.get(input_name, input_name)
        base = "explicit_name_resolution" if input_name in explicit_name_resolutions else "registry_name"
        resolution = taxonomy_row.get("name_resolution")
        if not isinstance(resolution, dict) or resolution.get("input_name") != input_name or resolution.get("lookup_name") != lookup_name:
            raise Goal049TaxonomyError("Goal 049 taxonomy name-resolution row drift")
        allowed_bases = {base, f"{base}+classification.speciesGuid", f"{base}+parentGuid"}
        if resolution.get("basis") not in allowed_bases:
            raise Goal049TaxonomyError("Goal 049 taxonomy name-resolution basis drift")
    parents = [row.get("parent") for row in rows]
    identifiers = [identifier for row in rows for identifier in row.get("ordered_identifiers", [])]
    if len(parents) != len(set(parents)) or len(identifiers) != len(set(identifiers)):
        raise Goal049TaxonomyError("Goal 049 taxonomy uniqueness failed")
    observed_seed_names = [seed for row in rows for seed in row.get("seed_names", [])]
    if taxonomy.get("goal048_seed_count") != len(seed_names) or taxonomy.get("goal048_seed_names") != seed_names or sorted(observed_seed_names) != sorted(seed_names) or len(observed_seed_names) != len(set(observed_seed_names)):
        raise Goal049TaxonomyError("Goal 048 seed representation is missing or duplicated")
    if any("/" in name for row in rows for name, _ in row.get("aliases", [])):
        raise Goal049TaxonomyError("composite alias entered taxonomy freeze")
    if taxonomy.get("occurrence_support_queried") is not False or receipt.get("occurrence_support_queried") is not False:
        raise Goal049TaxonomyError("taxonomy freeze is not count-free")
    return {"status": receipt["status"], "species_count": len(rows), "active_species_count": sum(bool(row.get("active")) for row in rows), "taxonomy_private_sha256": receipt["taxonomy_private_sha256"]}


# Short aliases are useful to callers and keep the command surface explicit.
Goal049Error = Goal049TaxonomyError
_taxonomy_one = taxonomy_one
_taxonomy_freeze = freeze_taxonomy
build_taxonomy_freeze = freeze_taxonomy
validate = validate_taxonomy_freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("freeze", "validate"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = freeze_taxonomy(args.root) if args.stage == "freeze" else validate_taxonomy_freeze(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
