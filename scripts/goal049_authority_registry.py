"""Goal 049 Stage A: acquire authorities and build a response-blind registry.

This module deliberately stops at ecological eligibility.  ALA concepts and
record evidence are a later, separately audited stage.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen


CONFIG_PATH = Path("config/goal049_seawfb_canonical_response.json")
PRIVATE_ROOT = Path("data/processed/dsdm/goal049-seawfb-canonical-response")
AUTHORITY_DIRNAME = "authorities"
AUTHORITY_FILES = {
    "birdlife_working_list": "WLAB_v4.3.xlsx",
    "australian_bird_data": "australian_bird_data_v1.csv",
    "australian_bird_data_metadata": "australian_bird_data_v1_metadata.csv",
}
ABD_NAME_FIELD = 7
ABD_FAMILY_FIELD = 10
ABD_SOURCE_ID_FIELD = 229
ABD_REQUIRED_FIELDS = (10, 17, 30, 32, 33, 34, 67, 68, 70, 71, 72, 73, *range(115, 126), 196, 197, 229)
WLAB_REQUIRED_FIELDS = ("TaxonLevel", "SpID", "TaxonScientificName", "FamilyScientificName")


class Goal049Error(RuntimeError):
    """Raised when a frozen Stage A contract cannot be satisfied."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("goal_id") != "049":
        raise Goal049Error("wrong Goal 049 configuration")
    if config["registry"]["source_rank"] != "species_only_australian_bird_data_field_17_equals_1":
        raise Goal049Error("source-rank rule drift")
    return config


def _authority_spec(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    authorities = config["authorities"]
    return {
        "birdlife_working_list": {
            **authorities["birdlife_working_list"],
            "filename": AUTHORITY_FILES["birdlife_working_list"],
            "md5": None,
        },
        "australian_bird_data": {
            **authorities["australian_bird_data"],
            "filename": AUTHORITY_FILES["australian_bird_data"],
            "md5": authorities["australian_bird_data"]["data_md5"],
            "sha256": authorities["australian_bird_data"]["data_sha256"],
            "url": authorities["australian_bird_data"]["data_url"],
        },
        "australian_bird_data_metadata": {
            **authorities["australian_bird_data"],
            "filename": AUTHORITY_FILES["australian_bird_data_metadata"],
            "md5": authorities["australian_bird_data"]["metadata_md5"],
            "sha256": authorities["australian_bird_data"]["metadata_sha256"],
            "url": authorities["australian_bird_data"]["metadata_url"],
        },
    }


def _download(path: Path, url: str, expected_sha256: str, expected_md5: str | None = None, *, opener=None) -> dict[str, Any]:
    """Download atomically and verify both configured digests before publish."""
    opener = opener or urlopen
    if path.is_file() and _sha256(path) == expected_sha256 and (expected_md5 is None or _md5(path) == expected_md5):
        return {"sha256": expected_sha256, "md5": _md5(path), "bytes": path.stat().st_size, "downloaded": False}
    temporary = path.with_suffix(path.suffix + ".part")
    request = Request(url, headers={"Accept": "*/*", "User-Agent": "dSDM-Goal049/1.0"})
    try:
        with opener(request, timeout=180) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        actual_sha = _sha256(temporary)
        actual_md5 = _md5(temporary)
        if actual_sha != expected_sha256 or (expected_md5 is not None and actual_md5 != expected_md5):
            raise Goal049Error(f"authority hash mismatch for {path.name}: sha256={actual_sha} md5={actual_md5}")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"sha256": expected_sha256, "md5": _md5(path), "bytes": path.stat().st_size, "downloaded": True}


def download_authorities(root: Path, *, opener=None, force: bool = False) -> dict[str, Any]:
    """Fetch configured authorities into the ignored private Stage A directory."""
    config = _config(root)
    directory = root / PRIVATE_ROOT / AUTHORITY_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    receipt_path = root / "metadata/goal049_authority_receipt.json"
    if not force and opener is None and receipt_path.is_file():
        try:
            previous = json.loads(receipt_path.read_text(encoding="utf-8"))
            specs = _authority_spec(config)
            if all(
                (directory / spec["filename"]).is_file()
                and _sha256(directory / spec["filename"]) == spec["sha256"]
                for spec in specs.values()
            ) and previous.get("source_sha256") == {
                name: _sha256(directory / spec["filename"]) for name, spec in specs.items()
            } and previous.get("retrieved_utc") and all(row.get("citation") and row.get("license") for row in previous.get("sources", {}).values()):
                return previous
        except (OSError, TypeError, json.JSONDecodeError):
            pass
    receipt: dict[str, Any] = {"status": "downloaded_and_hashed", "sources": {}}
    for name, spec in _authority_spec(config).items():
        path = directory / spec["filename"]
        # The default helper is injectable in tests; the production path uses
        # the same streaming/atomic checks as _download.
        observed = _download(path, spec["url"], spec["sha256"], spec["md5"], opener=opener)
        receipt["sources"][name] = {
            "url": spec["url"], "version": spec.get("version"), "filename": str(path.relative_to(root)),
            "expected_sha256": spec["sha256"], "observed_sha256": observed["sha256"],
            "expected_md5": spec.get("md5"), "observed_md5": observed["md5"], "bytes": observed["bytes"],
            "published": spec.get("published"),
            "citation": spec.get("citation") or spec.get("name"),
            "doi": spec.get("doi"),
            "license": spec.get("license") or "BirdLife Australia source page; no stated machine-readable reuse licence",
        }
    receipt["retrieved_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipt["source_sha256"] = {name: item["observed_sha256"] for name, item in receipt["sources"].items()}
    receipt["authority_sha256"] = _digest(receipt["sources"])
    _write_json(receipt_path, receipt)
    return receipt


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _csv_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("cp1252")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise Goal049Error(f"empty authority file: {path.name}") from exc
    return header, [row for row in reader if any(_clean(cell) for cell in row)]


def read_wlab(path: Path) -> list[dict[str, str]]:
    """Read WLAB with openpyxl; CSV is accepted only as a test fixture."""
    if path.suffix.lower() == ".csv":
        header, rows = _csv_rows(path)
        missing = sorted(set(WLAB_REQUIRED_FIELDS) - set(header))
        if missing:
            raise Goal049Error(f"WLAB schema missing required columns: {missing}")
        return [dict(zip(header, row)) for row in rows]
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise Goal049Error("WLAB XLSX parsing requires maintained dependency openpyxl; install it in the project environment") from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        header_values = next(iterator, None)
        if header_values is None:
            raise Goal049Error("empty WLAB workbook")
        header = [_clean(value) for value in header_values]
        missing = sorted(set(WLAB_REQUIRED_FIELDS) - set(header))
        if missing:
            raise Goal049Error(f"WLAB schema missing required columns: {missing}")
        rows = []
        for values in iterator:
            if any(_clean(value) for value in values):
                rows.append({key: _clean(value) for key, value in zip(header, values)})
        return rows
    finally:
        workbook.close()


def _abd_header_numbers(header: Iterable[str]) -> dict[int, int]:
    positions: dict[int, int] = {}
    for position, value in enumerate(header):
        match = re.match(r"^\s*(\d+)[_-]", value)
        if not match:
            match = re.match(r"^\s*field[_-]?(\d+)\s*$", value, re.I)
        if match:
            number = int(match.group(1))
            if number in positions:
                raise Goal049Error(f"duplicate ABD field number: {number}")
            positions[number] = position
    missing = sorted(set(ABD_REQUIRED_FIELDS) - set(positions))
    if missing:
        raise Goal049Error(f"ABD schema missing required fields: {missing}")
    return positions


def read_abd(path: Path) -> list[dict[int, str]]:
    """Read ABD rows keyed by their stable numeric field number."""
    header, raw_rows = _csv_rows(path)
    positions = _abd_header_numbers(header)
    rows = []
    for raw in raw_rows:
        if len(raw) < max(positions.values()) + 1:
            raise Goal049Error("ABD row shorter than its header")
        rows.append({number: _clean(raw[position]) for number, position in positions.items()})
    return rows


def _is_one(value: Any) -> bool:
    return _clean(value).lower() in {"1", "1.0", "true", "yes"}


def _is_zero(value: Any) -> bool:
    return _clean(value).lower() in {"0", "0.0", "false", "no"}


def _is_core(value: Any) -> bool:
    return _clean(value).lower() in {"core", "1", "1.0", "true", "yes"}


def _source_name(row: Mapping[int, str]) -> str:
    name = _clean(row.get(ABD_NAME_FIELD))
    if name and name.lower() != "na":
        return name
    genus, species = _clean(row.get(4)), _clean(row.get(5))
    if genus and species and genus.lower() != "na" and species.lower() != "na":
        return f"{genus} {species}"
    return "unresolved source species"


def _spid(value: Any) -> str:
    text = _clean(value)
    if text.endswith(".0"):
        text = text[:-2]
    return "" if text.lower() in {"", "na", "nav", "nan", "none"} else text


def _canonical_source_rows(rows: list[dict[int, str]], exceptions: list[dict[str, Any]]) -> list[dict[int, str]]:
    grouped: dict[str, list[dict[int, str]]] = defaultdict(list)
    missing_id_rows: list[dict[int, str]] = []
    for row in rows:
        source_id = _spid(row.get(ABD_SOURCE_ID_FIELD))
        if source_id:
            grouped[source_id].append(row)
        else:
            missing_id_rows.append(row)
    selected = []
    for row in missing_id_rows:
        exceptions.append({"type": "missing_source_id", "source_name": _source_name(row), "source_id": None})
        selected.append(row)
    for source_id, candidates in grouped.items():
        # ABD contains a species row and, for some taxa, a separate
        # non-breeding population row. Prefer the species/core row while
        # recording the collapse; never merge conflicting source names.
        names = {_source_name(row) for row in candidates}
        if len(names) > 1:
            exceptions.append({"type": "duplicate_source_id_conflicting_name", "source_name": sorted(names)[0], "source_id": source_id, "names": sorted(names)})
            continue
        ranked = sorted(candidates, key=lambda row: (not _is_one(row.get(30)), _is_one(row.get(31)), _source_name(row)))
        selected.append(ranked[0])
        if len(candidates) > 1:
            exceptions.append({"type": "duplicate_source_population_collapsed", "source_name": _source_name(ranked[0]), "source_id": source_id, "rows_collapsed": len(candidates)})
    return selected


def _wlab_species(rows: list[dict[str, str]], exceptions: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if _clean(row.get("TaxonLevel")).lower() == "sp":
            by_id[_spid(row.get("SpID"))].append(row)
    index: dict[str, dict[str, str]] = {}
    for source_id, matches in by_id.items():
        if not source_id:
            continue
        if len(matches) != 1:
            # Duplicate IDs are resolved later by exact ABD scientific name;
            # unresolved duplicates are recorded as blocking exceptions.
            continue
        else:
            index[source_id] = matches[0]
    return index


def _base_candidate(row: Mapping[int, str]) -> bool:
    jurisdiction = any(_is_core(row.get(field)) for field in (67, 68, 70, 71, 72, 73))
    return _is_one(row.get(30)) and _is_zero(row.get(32)) and _is_zero(row.get(33)) and _is_zero(row.get(34)) and jurisdiction


def _roles(row: Mapping[int, str], wlab: Mapping[str, str], base: bool, role_config: Mapping[str, Any]) -> tuple[bool, bool, str]:
    if not base:
        return False, False, "not_base_candidate"
    effort_fields = role_config["effort_donor"]["australian_bird_data_fields_any_one"]
    forest_fields = role_config["auxiliary_head"]["forest_feeding_fields_any_one"]
    if not any(_is_one(row.get(field)) for field in effort_fields):
        return False, False, "no_nontrivial_terrestrial_feeding_habitat"
    effort = True
    if not any(_is_one(row.get(field)) for field in forest_fields):
        return effort, False, "no_forest_feeding_use"
    if _is_one(row.get(196)) or _is_one(row.get(197)):
        return effort, False, "nomadic_or_irruptive"
    family = _clean(wlab.get("FamilyScientificName")) or _clean(row.get(ABD_FAMILY_FIELD))
    excluded = set(role_config["auxiliary_head"]["scale_detection_excluded_families"])
    if family in excluded:
        return effort, False, "scale_detection_excluded_family"
    return effort, True, "eligible_under_frozen_ecological_rules"


def _normal_name(value: Any) -> str:
    """Normalise scientific names only for the frozen subgenus convention."""
    text = re.sub(r"\([^)]*\)", "", _clean(value))
    return " ".join(text.split()).lower()


def _goal048_taxonomy(root: Path) -> tuple[dict[str, dict[str, Any]], str | None]:
    path = root / "data/processed/dsdm/goal048-seawfb-bioregional-freeze/taxonomy_freeze.json"
    if not path.is_file():
        return {}, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["rows"]
        if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get("seed_name") for row in rows):
            raise ValueError("invalid rows")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise Goal049Error("Goal 048 taxonomy evidence is unreadable") from exc
    return {str(row["seed_name"]): row for row in rows}, _sha256(path)


def _seed_rank(item: Mapping[str, Any], seed: str, evidence: Mapping[str, Any]) -> int | None:
    """Return deterministic identity priority, or None when unattributable."""
    current = _clean(item.get("wlab_current_name"))
    if current and current == seed:
        return 0
    accepted = _clean(evidence.get("accepted_name"))
    if current and accepted and _normal_name(current) == _normal_name(accepted):
        return 1
    labels = {_normal_name(name) for name, _ in evidence.get("aliases", [])}
    labels.update(_normal_name(name) for name, _ in evidence.get("descendants", []))
    if current and _normal_name(current) in labels:
        return 2
    # A source row with no WLAB match can only be used as a last-resort name
    # hint. It never outranks a current WLAB identity and prevents the known
    # Malurus pre-split source name from being assigned to M. assimilis.
    if not current and _normal_name(item.get("source_name")) in {_normal_name(seed), *labels}:
        return 3
    return None


def _name_evidence(source_name: str, current_name: str, source_family: str, current_family: str, seeds: Iterable[str], evidence: Mapping[str, Any]) -> str | None:
    """Classify a legacy-SpID match without inventing fuzzy taxonomy."""
    if _normal_name(source_name) == _normal_name(current_name):
        return "exact_scientific_name"
    for seed in seeds:
        item = {"wlab_current_name": current_name, "source_name": source_name}
        if _seed_rank(item, seed, evidence[seed]) is not None:
            return "goal048_frozen_name_evidence"
    if source_family and current_family and source_family == current_family:
        return "reviewed_same_family_legacy_name_transition"
    return None


def _crosswalk_match(source_row: Mapping[int, str], wlab_index: Mapping[str, dict[str, str]], wlab_by_name: Mapping[str, list[dict[str, str]]], source_ids_by_name: Mapping[str, str | None], duplicate_wlab_ids: set[str], resolved_duplicate_ids: set[str], seeds: Iterable[str], evidence: Mapping[str, Any], exceptions: list[dict[str, Any]]) -> dict[str, str] | None:
    """Resolve a legacy SpID candidate only with explicit name evidence."""
    source_id = _spid(source_row.get(ABD_SOURCE_ID_FIELD))
    source_name = _source_name(source_row)
    source_family = _clean(source_row.get(ABD_FAMILY_FIELD))
    match = wlab_index.get(source_id)
    if match is not None:
        current_name = _clean(match.get("TaxonScientificName"))
        current_family = _clean(match.get("FamilyScientificName"))
        current_name_key = _normal_name(current_name)
        reciprocal_source_id = source_ids_by_name.get(current_name_key)
        reciprocal_conflict = current_name_key in source_ids_by_name and reciprocal_source_id != source_id
        evidence_kind = None if reciprocal_conflict else _name_evidence(source_name, current_name, source_family, current_family, seeds, evidence)
        if evidence_kind is not None:
            if evidence_kind != "exact_scientific_name":
                exceptions.append({"type": "resolved_authority_exception", "reason": evidence_kind, "source_name": source_name, "source_id": source_id, "resolved_name": current_name, "birdlife_spid": _spid(match.get("SpID"))})
            return match
        exceptions.append({"type": "incongruent_crosswalk", "reason": "legacy_spid_reciprocal_name_reuse" if reciprocal_conflict else "legacy_spid_name_and_family_mismatch", "source_name": source_name, "source_id": source_id, "candidate_name": current_name, "candidate_family": current_family, "source_family": source_family, "candidate_source_id": reciprocal_source_id})
    exact_name_matches = wlab_by_name.get(_normal_name(source_name), [])
    if len(exact_name_matches) == 1:
        match = exact_name_matches[0]
        resolved_id = _spid(match.get("SpID"))
        if resolved_id in duplicate_wlab_ids:
            resolved_duplicate_ids.add(resolved_id)
        reason = "exact_name_fallback_after_legacy_spid_conflict" if source_id in duplicate_wlab_ids or match is not wlab_index.get(source_id) else "exact_name_fallback"
        for item in reversed(exceptions):
            if item.get("type") == "incongruent_crosswalk" and item.get("source_name") == source_name and item.get("source_id") == source_id:
                item["resolution"] = "exact_name_fallback"
                break
        exceptions.append({"type": "resolved_authority_exception", "reason": reason, "source_name": source_name, "source_id": source_id, "resolved_name": _clean(match.get("TaxonScientificName")), "resolved_spid": resolved_id})
        return match
    return None


def _apply_split_inheritances(rows: list[dict[str, Any]], config: Mapping[str, Any], exceptions: list[dict[str, Any]]) -> None:
    """Retain a mandatory seed when an old broad source row was split."""
    for rule in config["registry"].get("split_inheritances", []):
        source_name = rule["source_name"]
        target_seed = rule["target_seed"]
        sources = [row for row in rows if row["source_name"] == source_name]
        if not sources:
            continue
        if len(sources) != 1:
            exceptions.append({"type": "split_inheritance_source_missing_or_ambiguous", "source_name": source_name, "source_id": None, "target_seed": target_seed})
            continue
        if any(row["name"] == target_seed for row in rows):
            continue
        inherited = dict(sources[0])
        inherited.update({"name": target_seed, "wlab_current_name": None, "birdlife_spid": None, "goal048_seed": False, "reason": f"{sources[0]['reason']};split_derived_trait_inheritance"})
        inherited.pop("seed_names", None)
        rows.append(inherited)
        exceptions.append({"type": "resolved_authority_exception", "reason": "split_derived_trait_inheritance", "source_name": source_name, "source_id": sources[0].get("source_id"), "target_seed": target_seed, "disposition": rule["disposition"]})


def _apply_explicit_reconciliations(rows: list[dict[str, Any]], config: Mapping[str, Any], exceptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply only the name-specific, config-frozen authority dispositions."""
    for rule in config["registry"].get("explicit_reconciliations", []):
        source_name = rule["source_name"]
        canonical_name = rule["canonical_name"]
        sources = [row for row in rows if row["name"] == source_name or row["source_name"] == source_name]
        targets = [row for row in rows if row["name"] == canonical_name]
        if not sources:
            continue
        if len(targets) != 1:
            exceptions.append({"type": "reconciliation_target_missing_or_ambiguous", "source_name": source_name, "source_id": None, "canonical_name": canonical_name})
            continue
        target = targets[0]
        if not rule.get("merge_roles", False):
            raise Goal049Error(f"explicit reconciliation lacks frozen merge_roles permission: {source_name}")
        for source in sources:
            target["effort"] = bool(target["effort"] or source["effort"])
            target["auxiliary"] = bool(target["auxiliary"] or source["auxiliary"])
            target["target"] = bool(target["target"] or source["target"])
            target["base_candidate"] = bool(target["base_candidate"] or source["base_candidate"])
            target.setdefault("merged_source_names", [target["source_name"]]).append(source["source_name"])
            target.setdefault("merged_source_ids", [target["source_id"]]).append(source["source_id"])
            target["reason"] = f"{target['reason']};explicit_reconciliation:{source_name}->{canonical_name}"
            rows.remove(source)
        exceptions[:] = [item for item in exceptions if not (item.get("type") == "unmatched_crosswalk" and item.get("source_name") == source_name)]
        exceptions.append({"type": "resolved_authority_exception", "reason": "explicit_config_reconciliation", "source_name": source_name, "source_id": sources[0].get("source_id"), "canonical_name": canonical_name, "disposition": rule["disposition"]})
    return rows


def build_registry(root: Path, *, wlab_path: Path | None = None, abd_path: Path | None = None, strict: bool = False) -> dict[str, Any]:
    """Build the private registry and count-free exception ledger.

    ``strict=True`` is the production gate: conflicting authorities, missing
    mandatory seeds, or excessive unmatched crosswalks stop Stage A.
    """
    config = _config(root)
    private = root / PRIVATE_ROOT
    authorities = private / AUTHORITY_DIRNAME
    wlab_path = wlab_path or authorities / AUTHORITY_FILES["birdlife_working_list"]
    abd_path = abd_path or authorities / AUTHORITY_FILES["australian_bird_data"]
    metadata_path = authorities / AUTHORITY_FILES["australian_bird_data_metadata"]
    if not wlab_path.is_file() or not abd_path.is_file():
        raise Goal049Error("authority files are absent; run download_authorities first")
    exceptions: list[dict[str, Any]] = []
    wlab_rows = read_wlab(wlab_path)
    abd_rows = [row for row in read_abd(abd_path) if _is_one(row.get(17))]
    source_rows = _canonical_source_rows(abd_rows, exceptions)
    wlab_index = _wlab_species(wlab_rows, exceptions)
    wlab_species_rows = [row for row in wlab_rows if _clean(row.get("TaxonLevel")).lower() == "sp"]
    wlab_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in wlab_species_rows:
        wlab_by_name[_normal_name(row.get("TaxonScientificName"))].append(row)
    source_ids_by_name = {_normal_name(_source_name(row)): _spid(row.get(ABD_SOURCE_ID_FIELD)) or None for row in source_rows}
    duplicate_wlab_ids = {
        _spid(row.get("SpID")) for row in wlab_species_rows
        if _spid(row.get("SpID")) and sum(_spid(other.get("SpID")) == _spid(row.get("SpID")) for other in wlab_species_rows) > 1
    }
    resolved_duplicate_ids: set[str] = set()
    goal048 = json.loads((root / "config/goal048_seawfb_bioregional_freeze.json").read_text(encoding="utf-8"))
    transitions = goal048["species_universes"].get("accepted_name_transitions", {})
    seeds = list(goal048["species_universes"]["ecological_candidate_names"])
    taxonomy_rows, taxonomy_sha = _goal048_taxonomy(root)
    evidence = {
        seed: dict(taxonomy_rows.get(seed, {"seed_name": seed, "accepted_name": transitions.get(seed, seed), "aliases": [], "descendants": []}))
        for seed in seeds
    }
    rows: list[dict[str, Any]] = []
    for source_row in source_rows:
        source_id = _spid(source_row.get(ABD_SOURCE_ID_FIELD)) or None
        base = _base_candidate(source_row)
        source_name = _source_name(source_row)
        match = _crosswalk_match(source_row, wlab_index, wlab_by_name, source_ids_by_name, duplicate_wlab_ids, resolved_duplicate_ids, seeds, evidence, exceptions)
        if match is None:
            if base:
                exceptions.append({"type": "unmatched_crosswalk", "source_name": source_name, "source_id": source_id})
                effort, auxiliary, reason = _roles(source_row, {"FamilyScientificName": source_row.get(ABD_FAMILY_FIELD, "")}, base, config["roles"])
                rows.append({
                    "name": source_name, "source_name": source_name, "source_id": source_id,
                    "birdlife_spid": None, "wlab_current_name": None, "family": _clean(source_row.get(ABD_FAMILY_FIELD)), "base_candidate": base,
                    "effort": effort, "auxiliary": auxiliary, "target": auxiliary,
                    "reason": f"{reason};unmatched_crosswalk_requires_ala_resolution", "goal048_seed": False,
                })
            continue
        current_name = _clean(match.get("TaxonScientificName"))
        seed_candidates = [seed for seed in seeds if _seed_rank({"wlab_current_name": current_name, "source_name": source_name}, seed, evidence[seed]) is not None]
        if not base and not seed_candidates:
            continue
        effort, auxiliary, reason = _roles(source_row, match, base, config["roles"])
        rows.append({
            "name": current_name or source_name,
            "source_name": _source_name(source_row), "source_id": source_id,
            "birdlife_spid": _spid(match.get("SpID")) or None, "wlab_current_name": current_name, "family": _clean(match.get("FamilyScientificName")) or _clean(source_row.get(ABD_FAMILY_FIELD)),
            "base_candidate": base, "effort": effort, "auxiliary": auxiliary, "target": auxiliary,
            "reason": reason, "goal048_seed": False,
        })
    rows = _apply_explicit_reconciliations(rows, config, exceptions)
    _apply_split_inheritances(rows, config, exceptions)
    # Assign each seed once: exact current name, accepted current name after
    # subgenus normalisation, then an attributable alias/descendant.
    seed_assignments: dict[str, str] = {}
    for seed in seeds:
        candidates = [(priority, index, item) for index, item in enumerate(rows) if (priority := _seed_rank(item, seed, evidence[seed])) is not None]
        if not candidates:
            exceptions.append({"type": "mandatory_seed_requires_ala_resolution", "source_name": seed, "source_id": None})
            rows.append({"name": seed, "source_name": seed, "source_id": None, "birdlife_spid": None, "wlab_current_name": None, "family": None, "base_candidate": False, "effort": False, "auxiliary": False, "target": False, "reason": "mandatory_seed_requires_ala_resolution", "goal048_seed": True, "seed_names": [seed]})
            seed_assignments[seed] = seed
            continue
        best_priority = min(priority for priority, _, _ in candidates)
        best = [(index, item) for priority, index, item in candidates if priority == best_priority]
        if len(best) != 1:
            exceptions.append({"type": "mandatory_seed_ambiguous", "source_name": seed, "source_id": None, "candidate_names": [item["name"] for _, item in best]})
            rows.append({"name": seed, "source_name": seed, "source_id": None, "birdlife_spid": None, "wlab_current_name": None, "family": None, "base_candidate": False, "effort": False, "auxiliary": False, "target": False, "reason": "mandatory_seed_ambiguous", "goal048_seed": True, "seed_names": [seed]})
            seed_assignments[seed] = seed
            continue
        _, item = best[0]
        item["goal048_seed"] = True
        item["seed_names"] = [seed]
        seed_assignments[seed] = item["name"]
    # Canonical order is authority order, with any unresolved mandatory seeds
    # appended in the Goal 048 order.
    seen = set()
    ordered_rows = []
    for item in rows:
        key = (item["source_id"], item["name"])
        if key not in seen:
            seen.add(key); ordered_rows.append(item)
    duplicate_names = [name for name, n in Counter(item["name"] for item in ordered_rows).items() if n > 1]
    if duplicate_names:
        for name in duplicate_names:
            candidates = [item for item in ordered_rows if item["name"] == name]
            preferred = next((item for item in candidates if item.get("wlab_current_name")), candidates[0])
            ordered_rows = [item for item in ordered_rows if item["name"] != name or item is preferred]
            exceptions.append({"type": "resolved_authority_exception", "reason": "duplicate_registry_name_prefer_current_wlab", "source_name": name, "source_id": None, "candidate_source_ids": [item.get("source_id") for item in candidates]})
    for duplicate_id in sorted(duplicate_wlab_ids - resolved_duplicate_ids):
        names = sorted(_clean(row.get("TaxonScientificName")) for row in wlab_species_rows if _spid(row.get("SpID")) == duplicate_id)
        exceptions.append({"type": "duplicate_wlab_species_spid", "source_id": duplicate_id, "source_name": names[0], "names": names})
    marked_seed_rows = [item for item in ordered_rows if item.get("goal048_seed")]
    multiple_seed_rows = [item["name"] for item in marked_seed_rows if len(item.get("seed_names", [])) != 1]
    duplicate_seed_targets = [name for name, n in Counter(seed_assignments.values()).items() if n > 1]
    if len(seed_assignments) != len(seeds) or len(marked_seed_rows) != len(seeds) or multiple_seed_rows or duplicate_seed_targets:
        exceptions.append({"type": "seed_assignment_invariant", "source_name": "Goal 048 seed ledger", "source_id": None, "seed_count": len(seeds), "assigned_count": len(seed_assignments), "marked_row_count": len(marked_seed_rows), "multiple_seed_rows": multiple_seed_rows, "duplicate_seed_targets": duplicate_seed_targets})
    exception_path = private / "exception_ledger.json"
    ledger = {
        "status": "count_free", "exceptions": exceptions,
        "exception_types": dict(sorted(Counter(item["type"] for item in exceptions).items())),
        "source_names_retained": True, "occurrence_queries": 0, "model_outcomes": 0,
    }
    blocking_exception_types = {"mandatory_seed_ambiguous", "seed_assignment_invariant", "duplicate_source_id_conflicting_name", "duplicate_wlab_species_spid", "duplicate_registry_name"}
    unresolved_incongruent = any(item["type"] == "incongruent_crosswalk" and item.get("resolution") != "exact_name_fallback" for item in exceptions)
    registry = {
        "status": "frozen_response_blind" if not unresolved_incongruent and not any(item["type"] in blocking_exception_types for item in exceptions) else "requires_count_free_exception_review",
        "schema_version": "1.0", "goal_id": "049", "source_rank": config["registry"]["source_rank"],
        "config_sha256": _sha256(root / CONFIG_PATH),
        "authority_sha256": {"wlab": _sha256(wlab_path), "australian_bird_data": _sha256(abd_path), "australian_bird_data_metadata": _sha256(metadata_path) if metadata_path.is_file() else None},
        "rows": ordered_rows, "row_count": len(ordered_rows),
        "role_counts": {role: sum(bool(item[role]) for item in ordered_rows) for role in ("effort", "auxiliary", "target")},
        "goal048_seed_count": len(seeds), "goal048_seed_names": seeds,
        "marked_seed_row_count": len(marked_seed_rows),
        "goal048_seed_assignment": seed_assignments,
        "goal048_seed_assignment_sha256": _digest(seed_assignments),
        "goal048_taxonomy_source_sha256": taxonomy_sha,
        "exception_ledger": str(exception_path.relative_to(root)),
        "occurrence_queries": 0, "model_outcomes": 0,
    }
    _write_json(exception_path, ledger)
    _write_json(private / "registry.json", registry)
    tracked = {
        "status": registry["status"], "goal_id": "049", "schema_version": "1.0",
        "config_sha256": registry["config_sha256"],
        "private_registry": str((private / "registry.json").relative_to(root)),
        "private_registry_sha256": _sha256(private / "registry.json"),
        "authority_sha256": registry["authority_sha256"],
        "private_exception_ledger_sha256": _sha256(exception_path),
        "goal048_taxonomy_source_sha256": taxonomy_sha,
        "goal048_seed_assignment_sha256": _digest(seed_assignments),
        "row_count": len(ordered_rows), "goal048_seed_count": len(seeds),
        "role_counts": registry["role_counts"], "exception_types": ledger["exception_types"],
        "privacy": {"coordinates_written": False, "private_species_cell_lists_written": False, "raw_occurrence_rows": 0, "model_outcomes": 0},
    }
    _write_json(root / "metadata/goal049_registry_receipt.json", tracked)
    if strict:
        blocking = [item for item in exceptions if item["type"] in {"mandatory_seed_ambiguous", "seed_assignment_invariant", "duplicate_source_id_conflicting_name", "duplicate_wlab_species_spid", "duplicate_registry_name"} or (item["type"] == "incongruent_crosswalk" and item.get("resolution") != "exact_name_fallback")]
        crosswalk_exceptions = sum(item["type"] in {"unmatched_crosswalk", "missing_source_id"} for item in exceptions)
        unmatched_fraction = crosswalk_exceptions / max(len(ordered_rows), 1)
        if blocking:
            raise Goal049Error(f"blocking count-free registry exceptions: {len(blocking)}")
        if unmatched_fraction > float(config["registry"]["manual_exception_stop_fraction"]):
            raise Goal049Error("manual exception fraction exceeds frozen stop threshold")
    return {"registry": registry, "exception_ledger": ledger, "tracked_receipt": tracked}


def run_stage_a(root: Path, *, strict: bool = True) -> dict[str, Any]:
    download_authorities(root)
    return build_registry(root, strict=strict)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("download", "registry", "all"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--allow-exceptions", action="store_true", help="write the receipt without passing the production stop gate")
    parser.add_argument("--refresh", action="store_true", help="deliberately reacquire and timestamp authorities")
    args = parser.parse_args()
    if args.stage == "download":
        result = download_authorities(args.root, force=args.refresh)
    elif args.stage == "registry":
        result = build_registry(args.root, strict=not args.allow_exceptions)
    else:
        if args.refresh:
            download_authorities(args.root, force=True)
        result = build_registry(args.root, strict=not args.allow_exceptions)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
