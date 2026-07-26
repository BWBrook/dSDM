"""Goal018 deterministic offline ALA spatial normalisation.

The implementation uses the locked GeoPandas/Shapely/PyProj stack for spatial
contracts and standard-library CSV/JSON handling. It reads the frozen CSV
snapshot, validates the Goal017 raw manifest and canonical grid/coast bindings,
writes private row-level products to ignored directories, and writes
aggregate-only evidence suitable for tracking.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
import unicodedata
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
import geopandas as gpd
from pyproj import Geod
from pathlib import Path
from typing import Any, Iterable, Mapping

GOAL_ID = "goal018-ala-spatial-normalization-2026-07-24"
RAW_EXPECTED_ROWS = 50834
SPECIES = {
    "thylogale_billardierii": ("Thylogale billardierii", "https://biodiversity.org.au/afd/taxa/82e69509-af63-4502-86f7-43362b777865", ()),
    "notamacropus_rufogriseus": ("Notamacropus rufogriseus", "https://biodiversity.org.au/afd/taxa/c4dfafef-5192-4a3d-815c-040c393e9bca", ("Macropus rufogriseus",)),
    "macropus_giganteus": ("Macropus giganteus", "https://biodiversity.org.au/afd/taxa/f2f43ef9-89fd-4f89-8b06-0842e86cfe06", ()),
    "trichosurus_vulpecula": ("Trichosurus vulpecula", "https://biodiversity.org.au/afd/taxa/ee2cb6a9-e17c-4ca7-8aef-76d69eb969ed", ()),
    "pseudocheirus_peregrinus": ("Pseudocheirus peregrinus", "https://biodiversity.org.au/afd/taxa/003decd6-ec3d-468e-909d-da396a6dd1f6", ()),
    "vombatus_ursinus": ("Vombatus ursinus", "https://biodiversity.org.au/afd/taxa/66d42847-c556-4fa3-902c-a91d9f517286", ()),
    "sarcophilus_harrisii": ("Sarcophilus harrisii", "https://biodiversity.org.au/afd/taxa/c6b5ff5a-a991-4972-b5b0-4214141d5bd6", ()),
    "dasyurus_maculatus": ("Dasyurus maculatus", "https://biodiversity.org.au/afd/taxa/73c23669-c491-42d0-83b3-6fd84a03689a", ()),
    "dasyurus_viverrinus": ("Dasyurus viverrinus", "https://biodiversity.org.au/afd/taxa/1e9f1b49-78b5-409d-91f2-21615ce88e9d", ()),
}
PARENTS = {v[1]: (k, v[0]) for k, v in SPECIES.items()}
GEOD = Geod(ellps="WGS84")
CHILD_CONCEPTS = {
    "https://biodiversity.org.au/afd/taxa/e4b74750-7541-4c67-89d1-5b5718b30ea7": "vombatus_ursinus",
    "https://biodiversity.org.au/afd/taxa/3e53b354-2b48-4a2a-af29-acd8ecdfe1e6": "vombatus_ursinus",
    "https://biodiversity.org.au/afd/taxa/76b2b77b-6092-47dd-8de1-00e504b1e383": "vombatus_ursinus",
}
PRIMARY_REASONS = ("taxon_mismatch", "temporal_missing_or_invalid", "temporal_conflict", "outside_primary_window", "coordinates_missing", "coordinates_invalid", "coordinate_uncertainty_invalid", "coordinate_uncertainty_over_1000_m", "outside_land_boundary", "ineligible_grid_cell")
AUDIT_FIELDS = ("snapshot_row_id", "source_species_id", "source_file", "source_row_ordinal", "provider_record_id", "occurrence_id", "resource_uid", "dataset_id", "licence", "assertions", "accepted_species_id", "submitted_name", "matched_name", "matched_concept_id", "accepted_name", "accepted_concept_id", "accepted_rank", "year", "event_date_raw", "event_date_precision_basis", "longitude", "latitude", "coordinate_uncertainty_m", "coordinate_precision", "uncertainty_band", "coordinate_basis", "grid_cell_id", "candidate_centroid_lon", "candidate_centroid_lat", "centroid_distance_m", "cell_half_diagonal_m", "taxon_basis", "taxon_descendant_collapsed", "taxon_gate", "temporal_gate", "coordinate_gate", "uncertainty_gate", "coast_gate", "grid_gate", "row_state", "reason_codes", "primary_reason", "ordered_flags", "qa_flag_names", "qa_flag_count", "provider_record_id_control_clean")
PRESENCE_FIELDS = ("species_id", "grid_cell_id", "centroid_lon", "centroid_lat", "presence", "source_row_count", "unique_provider_record_count", "resource_count", "dataset_count", "unknown_uncertainty_count", "qa_flag_count", "low_cell_certainty_only")
EVIDENCE_PAYLOAD_FILES = (
    "source_inventory.json",
    "normalization_summary.json",
    "spatial_summary.json",
    "outputs.json",
    "review.json",
)
EVIDENCE_FILES = (*EVIDENCE_PAYLOAD_FILES, "manifest.json")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class NormalizationError(ValueError):
    pass


def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or plan.get("goal_id") != GOAL_ID or plan.get("schema_version") != "1.0":
        raise NormalizationError("plan_identity_drift")
    required = {"raw_directory", "raw_manifest", "grid", "coast_shp", "coast_shx", "coast_dbf", "coast_prj", "ala_plan", "field_contract", "decision_bundle"}
    bindings = plan.get("bindings")
    if not isinstance(bindings, Mapping) or set(bindings) != required:
        raise NormalizationError("plan_binding_shape_drift")
    for key, item in bindings.items():
        if not isinstance(item, Mapping) or (key != "raw_directory" and not item.get("sha256")):
            raise NormalizationError("plan_binding_hash_missing")
    expected_hashes = {"raw_manifest": "6abe4520fc8a35fbf94a6cf3c1632079770795cd75253732ab12440b1d16fe33", "grid": "91c7e0158ee8a808e9345d4bca28ec3e3fd7468dc3b7b1c1268e33e2da9499da", "coast_shp": "015270fc146045bd78c13586642630d50715fe15c759c817706e398bf0a0a00a", "coast_shx": "3bb02b6e7eaa3535b01c72c2faead97551a76bd5c5b0bf0c40fc85c225c9089d", "coast_dbf": "96859dc4e261fe28c41ba1f10570b9ce0cb3489614a9413c697b0b373bb83adb", "coast_prj": "a02a27b1d1982c8516d83398e85a3c8b1aef1713c13ef4d84d7bde17430c07c4", "ala_plan": "d447e1dfe536f25b1ea0126dbf9e7420024f774491e1670503ed0ea4895df632", "field_contract": "98cd67c17dbe5a9c55b4f17c8a4f6e383010d9d8724dff23bc9c3911051b9159", "decision_bundle": "ccccbb2e56e101b1a53421f8016699bfb500f4356861e10c1213a398aabe04a2"}
    if any(bindings[k].get("sha256") != v for k, v in expected_hashes.items()):
        raise NormalizationError("plan_binding_literal_drift")
    spatial = plan.get("spatial_bindings")
    if not isinstance(spatial, Mapping) or spatial.get("grid", {}).get("row_count") != 74073 or spatial.get("grid", {}).get("columns") != ["lon", "lat"] or spatial.get("grid", {}).get("crs") != "EPSG:4326":
        raise NormalizationError("grid_contract_drift")
    if spatial.get("coast", {}).get("feature_count") != 1 or spatial.get("coast", {}).get("geometry_type") != "MultiPolygon" or spatial.get("coast", {}).get("crs") != "EPSG:4326":
        raise NormalizationError("coast_contract_drift")
    if plan.get("expected_input_rows") != RAW_EXPECTED_ROWS or plan.get("outputs", {}).get("directory") != "data/processed/ala/goal018-spatial-normalization/2026-07-24" or plan.get("evidence", {}).get("directory") != "evidence/ala_spatial_normalization/2026-07-24":
        raise NormalizationError("production_contract_drift")
    if plan.get("temporal") != {"start_year": 2001, "end_year": 2025, "inclusive": True} or plan.get("uncertainty", {}).get("max_m") != 1000 or plan.get("lattice", {}).get("nearest_rescue") is not False:
        raise NormalizationError("eligibility_contract_drift")
    if plan.get("evidence", {}).get("files") != ["source_inventory.json", "normalization_summary.json", "spatial_summary.json", "outputs.json", "review.json", "manifest.json"]:
        raise NormalizationError("evidence_contract_drift")
    return {"goal_id": GOAL_ID, "species_count": 9}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snapshot_row_id(raw_file_sha256: str, one_based_row_ordinal: int) -> str:
    return hashlib.sha256(f"ala_occurrence\0{raw_file_sha256}\0{one_based_row_ordinal}".encode()).hexdigest()


def grid_cell_id(lon: float, lat: float) -> str:
    return f"g_{round(float(lon) * 10000):d}_{round(float(lat) * 10000):d}"


def candidate_centroid(lon: float, lat: float) -> tuple[float, float] | None:
    if not (math.isfinite(lon) and math.isfinite(lat)):
        return None
    if not (143.84 <= lon < 151.0 and -43.6425 <= lat < -39.0):
        return None
    i = int((Decimal(str(lon)) - Decimal("143.84")) / Decimal("0.01")).__floor__()
    j = int((Decimal(str(lat)) + Decimal("43.6425")) / Decimal("0.01")).__floor__()
    return (float(Decimal("143.845") + Decimal("0.01") * i), float(Decimal("-43.6375") + Decimal("0.01") * j))


def _point_ring_covers(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-12 and min(x1, x2) - 1e-12 <= x <= max(x1, x2) + 1e-12 and min(y1, y2) - 1e-12 <= y <= max(y1, y2) + 1e-12:
            return True
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _shapefile_polygons(path: Path):
    """Read and validate the canonical coast bundle with GeoPandas."""
    try:
        coast = gpd.read_file(path)
    except Exception as exc:
        raise NormalizationError("coast_shapefile_invalid") from exc
    if coast.empty or coast.crs is None or coast.crs.to_epsg() != 4326:
        raise NormalizationError("coast_geometry_contract_failure")
    if not all(g.geom_type in {"Polygon", "MultiPolygon"} for g in coast.geometry):
        raise NormalizationError("coast_geometry_type_invalid")
    return coast.geometry


def _coast_covers(x: float, y: float, polygons) -> bool:
    from shapely.geometry import Point
    point = Point(x, y)
    return bool(polygons.covers(point).any())


def _num(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "": return None
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def _parent_species_name_matches(
    name: str, canonical_name: str, aliases: tuple[str, ...]
) -> bool:
    for candidate in (canonical_name, *aliases):
        if name == candidate or re.fullmatch(
            re.escape(candidate) + r" \([^()\r\n]+\)", name
        ):
            return True
    return False


def _taxon(row: Mapping[str, str], species_id: str) -> tuple[str | None, str, bool, str]:
    target_name, target_concept, aliases = SPECIES[species_id]
    matched = (row.get("scientificName") or "").strip()
    matched_concept = (row.get("taxonConceptID") or "").strip()
    accepted = (row.get("acceptedNameUsage") or "").strip()
    accepted_concept = (row.get("acceptedNameUsageID") or "").strip()
    rank = (row.get("taxonRank") or "").strip().lower()
    concepts = tuple(c for c in (matched_concept, accepted_concept) if c)
    known_owner = {
        **{concept: owner[0] for concept, owner in PARENTS.items()},
        **CHILD_CONCEPTS,
    }
    if any(
        concept in known_owner and known_owner[concept] != species_id
        for concept in concepts
    ):
        return None, "taxon_mismatch", False, rank
    if accepted_concept and accepted_concept not in known_owner:
        return None, "taxon_mismatch", False, rank

    controlling = accepted or matched
    descendant_name = bool(controlling) and (
        controlling.startswith(target_name + " ")
        or any(controlling.startswith(alias + " ") for alias in aliases)
    )

    if rank == "species":
        if (
            not _parent_species_name_matches(controlling, target_name, aliases)
            or target_concept not in concepts
        ):
            return None, "taxon_mismatch", False, rank
        return species_id, "pinned_parent_concept", False, rank

    if rank != "subspecies" or not descendant_name:
        return None, "taxon_mismatch", False, rank

    if any(
        concept in CHILD_CONCEPTS and CHILD_CONCEPTS[concept] == species_id
        for concept in concepts
    ):
        return species_id, "configured_child_concept", True, rank
    return species_id, "accepted_subspecies_name", True, rank


def _temporal(row: Mapping[str, str]) -> tuple[int | None, str, str | None]:
    raw_year = (row.get("year") or "").strip()
    year = None
    try:
        if raw_year and str(int(raw_year)) == raw_year: year = int(raw_year)
    except ValueError: pass
    event = (row.get("eventDate") or "").strip()
    derived = None
    if event:
        if re.fullmatch(r"\d{4}", event):
            derived = int(event)
        else:
            try:
                datetime.fromisoformat(event.replace("Z", "+00:00"))
                derived = int(event[:4]) if re.match(r"^\d{4}-", event) else None
            except ValueError:
                if year is not None: return year, "reported", "event_date_invalid_flag"
                return None, "unknown", "temporal_missing_or_invalid"
    if year is not None and derived is not None and year != derived:
        return year, "reported", "temporal_conflict"
    if year is None and derived is not None:
        return derived, "eventDate_leading_year", None
    if year is None:
        return None, "unknown", "temporal_missing_or_invalid"
    return year, "reported", ("event_date_missing_flag" if not event else None)


def _uncertainty(row: Mapping[str, str]) -> tuple[float | None, str, str | None]:
    raw = (row.get("coordinateUncertaintyInMeters") or "").strip()
    if not raw: return None, "unknown", None
    value = _num(raw)
    if value is None or value < 0: return None, "invalid", "coordinate_uncertainty_invalid"
    if value > 1000: return value, "reported", "coordinate_uncertainty_over_1000_m"
    return value, "reported", None


def _read_grid(path: Path) -> dict[str, tuple[float, float]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or set(rows[0]) != {"lon", "lat"}: raise NormalizationError("grid_schema_failure")
    cells = {}
    for r in rows:
        lon, lat = _num(r["lon"]), _num(r["lat"])
        if lon is None or lat is None: raise NormalizationError("grid_coordinate_failure")
        cells[grid_cell_id(lon, lat)] = (lon, lat)
    if len(cells) != len(rows): raise NormalizationError("grid_duplicate_cells")
    return cells


def _raw_manifest(raw_root: Path, manifest_path: Path) -> list[dict[str, Any]]:
    try:
        m = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise NormalizationError("raw_manifest_schema_failure") from exc
    entries = m.get("raw_files")
    if not isinstance(entries, list) or not entries:
        raise NormalizationError("raw_manifest_schema_failure")
    listed: set[str] = set()
    for e in entries:
        if (
            not isinstance(e, Mapping)
            or set(e) != {"path", "bytes", "sha256"}
            or not isinstance(e.get("path"), str)
            or Path(e["path"]).is_absolute()
            or ".." in Path(e["path"]).parts
            or not isinstance(e.get("bytes"), int)
            or isinstance(e.get("bytes"), bool)
            or e["bytes"] < 0
            or not isinstance(e.get("sha256"), str)
            or SHA256_RE.fullmatch(e["sha256"]) is None
            or e["path"] in listed
        ):
            raise NormalizationError("raw_manifest_schema_failure")
        listed.add(e["path"])
        p = raw_root / e["path"]
        if (
            not p.is_file()
            or p.is_symlink()
            or p.stat().st_size != e["bytes"]
            or sha256(p) != e["sha256"]
        ):
            raise NormalizationError("raw_manifest_binding_drift")
    observed = {
        str(path.relative_to(raw_root))
        for path in raw_root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if observed != listed:
        raise NormalizationError("raw_manifest_footprint_drift")
    return entries


def _bound_inputs(
    plan_path: Path,
    plan: Mapping[str, Any],
    *,
    raw_root: Path | None = None,
    raw_manifest_path: Path | None = None,
    grid_path: Path | None = None,
    coast_path: Path | None = None,
) -> dict[str, Path]:
    root = Path(plan_path).resolve().parents[1]
    bindings = plan["bindings"]
    overrides = {
        "raw_directory": raw_root,
        "raw_manifest": raw_manifest_path,
        "grid": grid_path,
        "coast_shp": coast_path,
    }
    paths: dict[str, Path] = {}
    for key, binding in bindings.items():
        relative = Path(binding["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise NormalizationError("bound_input_path_unsafe")
        bound = (root / relative).resolve()
        override = overrides.get(key)
        if override is not None and Path(override).resolve() != bound:
            raise NormalizationError("bound_input_override_drift")
        paths[key] = bound
        if key == "raw_directory":
            if not bound.is_dir() or bound.is_symlink():
                raise NormalizationError("raw_directory_invalid")
            continue
        if (
            not bound.is_file()
            or bound.is_symlink()
            or sha256(bound) != binding["sha256"]
        ):
            raise NormalizationError("bound_input_hash_drift")
    return paths


def _validate_goal017(paths: Mapping[str, Path], validator=None) -> None:
    if validator is None:
        from .ala_full_acquisition import validate_evidence as validator
    try:
        result = validator(
            paths["ala_plan"],
            paths["raw_manifest"].parent,
            paths["raw_directory"],
        )
    except Exception as exc:
        raise NormalizationError("goal017_raw_validation_failure") from exc
    if (
        not isinstance(result, Mapping)
        or result.get("readiness") != "goal017_nine_species_acquisition_complete"
    ):
        raise NormalizationError("goal017_raw_validation_failure")


def _load_source_rows(
    raw_root: Path,
    raw_manifest_path: Path,
    expected_rows: int,
) -> tuple[
    list[tuple[str, Path, int, dict[str, str]]],
    list[dict[str, Any]],
    dict[Path, str],
]:
    entries = _raw_manifest(raw_root, raw_manifest_path)
    occurrence = sorted(
        (entry for entry in entries if entry["path"].startswith("occurrences/")),
        key=lambda entry: entry["path"],
    )
    if (
        len(occurrence) != len(SPECIES)
        or {Path(entry["path"]).stem for entry in occurrence} != set(SPECIES)
    ):
        raise NormalizationError("raw_replay_species_footprint")

    rows: list[tuple[str, Path, int, dict[str, str]]] = []
    seen_ids: set[str] = set()
    source_columns: list[str] | None = None
    raw_hashes: dict[Path, str] = {}
    for entry in occurrence:
        source_species = Path(entry["path"]).stem
        path = raw_root / entry["path"]
        raw_hashes[path] = entry["sha256"]
        try:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                fields = list(reader.fieldnames or [])
                if (
                    len(fields) != 145
                    or len(set(fields)) != 145
                    or "recordID" not in fields
                ):
                    raise NormalizationError("occurrence_schema_failure")
                if source_columns is None:
                    source_columns = fields
                elif fields != source_columns:
                    raise NormalizationError("occurrence_schema_drift")
                for ordinal, row in enumerate(reader, 1):
                    if set(row) != set(fields) or None in row:
                        raise NormalizationError("occurrence_row_schema_failure")
                    provider_id = row.get("recordID", "")
                    if (
                        not provider_id.strip()
                        or any(
                            unicodedata.category(character).startswith("C")
                            for character in provider_id
                        )
                        or provider_id in seen_ids
                    ):
                        raise NormalizationError("provider_record_id_duplicate_or_invalid")
                    seen_ids.add(provider_id)
                    rows.append((source_species, path, ordinal, row))
        except (OSError, csv.Error) as exc:
            raise NormalizationError("occurrence_csv_invalid") from exc
    if len(rows) != expected_rows:
        raise NormalizationError("raw_row_count_mismatch")
    return rows, occurrence, raw_hashes


def normalize_rows(rows: Iterable[tuple[str, Path, int, Mapping[str, str]]], grid: Mapping[str, tuple[float, float]], polygons, *, raw_hashes: Mapping[Path, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    audit, accepted = [], []
    raw_hashes = dict(raw_hashes or {})
    for source_species, raw_path, ordinal, row in rows:
        if raw_path not in raw_hashes:
            raw_hashes[raw_path] = sha256(raw_path)
        raw_sha = raw_hashes[raw_path]
        sid = snapshot_row_id(raw_sha, ordinal)
        accepted_sid, taxon_basis, descendant, rank = _taxon(row, source_species)
        reasons: list[str] = []
        if accepted_sid is None: reasons.append("taxon_mismatch")
        year, date_basis, temporal_reason = _temporal(row)
        temporal_flag = temporal_reason if temporal_reason in {"event_date_invalid_flag", "event_date_missing_flag"} else ""
        if temporal_reason in {"temporal_missing_or_invalid", "temporal_conflict"}: reasons.append(temporal_reason)
        if year is not None and not 2001 <= year <= 2025: reasons.append("outside_primary_window")
        raw_lon, raw_lat = (row.get("decimalLongitude") or "").strip(), (row.get("decimalLatitude") or "").strip()
        lon, lat = _num(raw_lon), _num(raw_lat)
        if not raw_lon or not raw_lat: reasons.append("coordinates_missing")
        elif lon is None or lat is None: reasons.append("coordinates_invalid")
        elif not (-180 <= lon <= 180 and -90 <= lat <= 90): reasons.append("coordinates_invalid")
        uncertainty, uncertainty_basis, uncertainty_reason = _uncertainty(row)
        if uncertainty_reason: reasons.append(uncertainty_reason)
        centroid = candidate_centroid(lon, lat) if lon is not None and lat is not None else None
        cell_id = grid_cell_id(*centroid) if centroid else ""
        if lon is not None and lat is not None and -180 <= lon <= 180 and -90 <= lat <= 90 and centroid is None:
            reasons.append("outside_land_boundary")
        if centroid and not _coast_covers(lon, lat, polygons): reasons.append("outside_land_boundary")
        if centroid and _coast_covers(lon, lat, polygons) and cell_id not in grid: reasons.append("ineligible_grid_cell")
        cell_half_m = (float(GEOD.inv(centroid[0], centroid[1], centroid[0] + 0.005, centroid[1] + 0.005)[2]) if centroid else None)
        distance_m = None
        if centroid and lon is not None and lat is not None:
            distance_m = abs(float(GEOD.inv(centroid[0], centroid[1], lon, lat)[2]))
        qa_names = [str(k) for k, v in row.items() if k not in {"assertions"} and (str(k).isupper() or k in {"detectedOutlier", "geospatialIssue", "habitatMismatch", "identificationIncorrect", "taxonomicIssue", "temporalIssue"}) and str(v).strip().lower() in {"true", "1", "yes"}]
        qa = len(qa_names)
        control = bool((row.get("recordID") or "").strip()) and all(not unicodedata.category(c).startswith("C") for c in (row.get("recordID") or ""))
        if not control: raise NormalizationError("provider_record_id_control_failure")
        primary = next((r for r in PRIMARY_REASONS if r in reasons), "")
        ordered_flags = [r for r in PRIMARY_REASONS if r in reasons]
        if temporal_flag: ordered_flags.append(temporal_flag)
        if uncertainty is None: ordered_flags.append("coordinate_uncertainty_missing")
        if date_basis == "eventDate_leading_year": ordered_flags.append("event_year_fallback")
        if descendant: ordered_flags.append("descendant_collapsed")
        if centroid and _coast_covers(lon, lat, polygons): ordered_flags.append("boundary_covers")
        if centroid and (uncertainty is None or (isinstance(uncertainty, (int, float)) and cell_half_m is not None and uncertainty > cell_half_m)): ordered_flags.append("low_cell_certainty")
        ordered_flags.extend(qa_names)
        row_state = "accepted_presence" if not reasons and accepted_sid and cell_id and centroid and cell_id in grid else "excluded"
        if row_state == "accepted_presence" and not (_coast_covers(lon, lat, polygons) and cell_id in grid):
            raise NormalizationError("accepted_cell_invariant")
        audit.append({"snapshot_row_id": sid, "source_species_id": source_species, "source_file": "/".join(Path(raw_path).parts[-2:]), "source_row_ordinal": ordinal, "provider_record_id": row.get("recordID", ""), "accepted_species_id": accepted_sid or "", "submitted_name": row.get("raw_scientificName", ""), "matched_name": row.get("scientificName", ""), "matched_concept_id": row.get("taxonConceptID", ""), "accepted_name": row.get("acceptedNameUsage", ""), "accepted_concept_id": row.get("acceptedNameUsageID", ""), "accepted_rank": rank, "year": "" if year is None else year, "event_date_raw": row.get("eventDate", ""), "event_date_precision_basis": date_basis, "longitude": "" if lon is None else lon, "latitude": "" if lat is None else lat, "coordinate_uncertainty_m": "" if uncertainty is None else uncertainty, "coordinate_precision": row.get("coordinatePrecision", ""), "uncertainty_band": "unknown" if uncertainty is None else ("1000m" if uncertainty == 1000 else ("0-1000m" if uncertainty < 1000 else ">1000m")), "coordinate_basis": uncertainty_basis, "grid_cell_id": cell_id if cell_id in grid else "", "candidate_centroid_lon": "" if not centroid else centroid[0], "candidate_centroid_lat": "" if not centroid else centroid[1], "centroid_distance_m": "" if distance_m is None else round(distance_m, 6), "cell_half_diagonal_m": "" if cell_half_m is None else round(cell_half_m, 6), "taxon_basis": taxon_basis, "taxon_descendant_collapsed": str(descendant).lower(), "taxon_gate": "pass" if accepted_sid else "fail", "temporal_gate": "pass" if temporal_reason is None and year is not None and 2001 <= year <= 2025 else "fail", "coordinate_gate": "pass" if lon is not None and lat is not None and -180 <= lon <= 180 and -90 <= lat <= 90 else "fail", "uncertainty_gate": "pass" if uncertainty_reason is None else "fail", "coast_gate": "pass" if centroid and _coast_covers(lon, lat, polygons) else "fail", "grid_gate": "pass" if cell_id in grid else "fail", "row_state": row_state, "reason_codes": ";".join(sorted(set(reasons))), "primary_reason": primary, "ordered_flags": ";".join(ordered_flags), "qa_flag_names": ";".join(qa_names), "qa_flag_count": qa, "provider_record_id_control_clean": "true"})
        audit[-1].update({"temporal_gate": "not_evaluated" if not accepted_sid else ("pass" if temporal_reason not in {"temporal_missing_or_invalid", "temporal_conflict"} and year is not None and 2001 <= year <= 2025 else "fail"), "coordinate_gate": "not_evaluated" if not accepted_sid or temporal_reason in {"temporal_missing_or_invalid", "temporal_conflict"} else ("pass" if lon is not None and lat is not None and -180 <= lon <= 180 and -90 <= lat <= 90 else "fail"), "uncertainty_gate": "not_evaluated" if lon is None or lat is None else ("pass" if uncertainty_reason is None else "fail"), "coast_gate": "not_evaluated" if not centroid else ("pass" if _coast_covers(lon, lat, polygons) else "fail"), "grid_gate": "not_evaluated" if not centroid else ("pass" if cell_id in grid else "fail")})
        audit[-1].update({"occurrence_id": row.get("occurrenceID", ""), "resource_uid": row.get("dataResourceUid", ""), "dataset_id": row.get("datasetID", ""), "licence": row.get("dcterms:license", row.get("license", "")), "assertions": row.get("assertions", "")})
        if not reasons:
            accepted.append({"audit": audit[-1], "row": row, "source_path": raw_path})
    return audit, accepted


def collapse_presence(accepted: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in accepted:
        a, row = item["audit"], item["row"]
        groups[(a["accepted_species_id"], a["grid_cell_id"])].append(item)
    out = []
    for (species_id, cell), items in sorted(groups.items()):
        a0 = items[0]["audit"]
        out.append({"species_id": species_id, "grid_cell_id": cell, "centroid_lon": a0["candidate_centroid_lon"], "centroid_lat": a0["candidate_centroid_lat"], "presence": 1, "source_row_count": len(items), "unique_provider_record_count": len({i["row"].get("recordID", "") for i in items}), "resource_count": len({i["row"].get("dataResourceUid", "") for i in items if i["row"].get("dataResourceUid", "")}), "dataset_count": len({i["row"].get("datasetID", "") for i in items if i["row"].get("datasetID", "")}), "unknown_uncertainty_count": sum(i["audit"]["uncertainty_band"] == "unknown" for i in items), "qa_flag_count": sum(int(i["audit"]["qa_flag_count"]) for i in items), "low_cell_certainty_only": str(all(i["audit"]["uncertainty_band"] == "unknown" or (isinstance(i["audit"]["coordinate_uncertainty_m"], (int, float)) and i["audit"]["coordinate_uncertainty_m"] > i["audit"]["cell_half_diagonal_m"]) for i in items)).lower()})
    return out


def _write_csv(path: Path, fields: tuple[str, ...], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), lineterminator="\n", extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _build_evidence_payloads(
    plan: Mapping[str, Any],
    paths: Mapping[str, Path],
    rows: list[tuple[str, Path, int, dict[str, str]]],
    audit: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    presence: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    counts = Counter(item["primary_reason"] or "accepted" for item in audit)
    taxon = Counter(item["taxon_basis"] for item in audit)
    uncertainty = Counter(item["uncertainty_band"] for item in audit)
    accepted_audit = [
        item for item in audit if item["row_state"] == "accepted_presence"
    ]
    per_species: dict[str, dict[str, int]] = {}
    for species_id in SPECIES:
        subset = [item for item in audit if item["source_species_id"] == species_id]
        per_species[species_id] = {
            "input_rows": len(subset),
            "accepted_rows": sum(
                item["row_state"] == "accepted_presence" for item in subset
            ),
            "excluded_rows": sum(item["row_state"] == "excluded" for item in subset),
            "presence_cells": len(
                {
                    item["grid_cell_id"]
                    for item in subset
                    if item["row_state"] == "accepted_presence"
                }
            ),
        }
    return {
        "source_inventory.json": {
            "goal_id": GOAL_ID,
            "raw_rows": len(rows),
            "raw_manifest_sha256": sha256(paths["raw_manifest"]),
            "species_count": len(SPECIES),
            "spatial_inputs": {
                "grid_sha256": sha256(paths["grid"]),
                "coast_sha256": sha256(paths["coast_shp"]),
            },
        },
        "normalization_summary.json": {
            "input_rows": len(rows),
            "accepted_rows": len(accepted),
            "excluded_rows": len(rows) - len(accepted),
            "quarantined_contract": 0,
            "by_species": per_species,
            "by_reason": dict(sorted(counts.items())),
            "by_taxon_basis": dict(sorted(taxon.items())),
            "by_uncertainty_band": dict(sorted(uncertainty.items())),
            "privacy": {"aggregate_only": True},
        },
        "spatial_summary.json": {
            "accepted_cells": len(presence),
            "centroid_distance_m": {
                "max": max(
                    (
                        float(item["centroid_distance_m"])
                        for item in accepted_audit
                        if item["centroid_distance_m"] != ""
                    ),
                    default=0.0,
                ),
                "n": len(accepted_audit),
            },
            "low_cell_certainty_rows": sum(
                1
                for item in accepted_audit
                if "low_cell_certainty"
                in str(item["ordered_flags"]).split(";")
            ),
        },
        "outputs.json": {
            "row_audit_rows": len(audit),
            "presence_rows": len(presence),
            "row_audit_sha256": sha256(output_dir / "row_audit.csv"),
            "presence_sha256": sha256(output_dir / "presence.csv"),
            "schemas": {
                "row_audit": list(AUDIT_FIELDS),
                "presence": list(PRESENCE_FIELDS),
            },
        },
        "review.json": {
            "readiness": "goal018_spatial_normalization_complete",
            "raw_replay_required": True,
            "privacy": {
                "row_values_retained": False,
                "coordinates_retained": False,
                "record_ids_retained": False,
                "coordinates": False,
                "dates": False,
                "account_values": False,
                "resource_values": False,
                "dataset_values": False,
            },
        },
    }


def _write_evidence_bundle(
    evidence_dir: Path, payloads: Mapping[str, Mapping[str, Any]]
) -> None:
    for name in EVIDENCE_PAYLOAD_FILES:
        (evidence_dir / name).write_text(
            json.dumps(payloads[name], indent=2, sort_keys=True) + "\n"
        )
    files = [
        {
            "path": name,
            "bytes": (evidence_dir / name).stat().st_size,
            "sha256": sha256(evidence_dir / name),
        }
        for name in EVIDENCE_PAYLOAD_FILES
    ]
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {"schema_version": "1.0", "files": files},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _read_evidence_bundle(
    evidence_dir: Path,
) -> dict[str, dict[str, Any]]:
    if not evidence_dir.is_dir() or evidence_dir.is_symlink():
        raise NormalizationError("evidence_directory_invalid")
    observed = {
        path.name
        for path in evidence_dir.iterdir()
        if path.is_file() or path.is_symlink()
    }
    if observed != set(EVIDENCE_FILES):
        raise NormalizationError("evidence_footprint_drift")
    try:
        manifest = json.loads((evidence_dir / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise NormalizationError("evidence_manifest_schema_failure") from exc
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema_version", "files"}
        or manifest.get("schema_version") != "1.0"
        or not isinstance(manifest.get("files"), list)
        or [entry.get("path") for entry in manifest["files"] if isinstance(entry, dict)]
        != list(EVIDENCE_PAYLOAD_FILES)
    ):
        raise NormalizationError("evidence_manifest_schema_failure")
    for entry in manifest["files"]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"path", "bytes", "sha256"}
            or not _is_int(entry.get("bytes"))
            or entry["bytes"] < 0
            or not isinstance(entry.get("sha256"), str)
            or SHA256_RE.fullmatch(entry["sha256"]) is None
        ):
            raise NormalizationError("evidence_manifest_schema_failure")
        path = evidence_dir / entry["path"]
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != entry["bytes"]
            or sha256(path) != entry["sha256"]
        ):
            raise NormalizationError("evidence_manifest_tamper")
    payloads: dict[str, dict[str, Any]] = {}
    for name in EVIDENCE_PAYLOAD_FILES:
        try:
            value = json.loads((evidence_dir / name).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise NormalizationError("evidence_payload_schema_failure") from exc
        if not isinstance(value, dict):
            raise NormalizationError("evidence_payload_schema_failure")
        serialized = json.dumps(value, sort_keys=True)
        if any(
            forbidden in serialized
            for forbidden in (
                "recordID",
                "decimalLatitude",
                "decimalLongitude",
                "eventDate",
                "occurrenceID",
            )
        ):
            raise NormalizationError("aggregate_evidence_privacy_failure")
        payloads[name] = value
    return payloads


def _nonnegative_counts(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and all(isinstance(key, str) and key for key in value)
        and all(_is_int(count) and count >= 0 for count in value.values())
    )


def _validate_tracked_payloads(
    plan: Mapping[str, Any], payloads: Mapping[str, dict[str, Any]]
) -> None:
    expected_rows = int(plan["expected_input_rows"])
    source = payloads["source_inventory.json"]
    if (
        set(source)
        != {
            "goal_id",
            "raw_rows",
            "raw_manifest_sha256",
            "species_count",
            "spatial_inputs",
        }
        or source.get("goal_id") != GOAL_ID
        or source.get("raw_rows") != expected_rows
        or source.get("species_count") != len(SPECIES)
        or source.get("raw_manifest_sha256")
        != plan["bindings"]["raw_manifest"]["sha256"]
        or not isinstance(source.get("spatial_inputs"), dict)
        or source["spatial_inputs"]
        != {
            "grid_sha256": plan["bindings"]["grid"]["sha256"],
            "coast_sha256": plan["bindings"]["coast_shp"]["sha256"],
        }
    ):
        raise NormalizationError("source_inventory_semantic_failure")

    summary = payloads["normalization_summary.json"]
    summary_keys = {
        "input_rows",
        "accepted_rows",
        "excluded_rows",
        "quarantined_contract",
        "by_species",
        "by_reason",
        "by_taxon_basis",
        "by_uncertainty_band",
        "privacy",
    }
    if (
        set(summary) != summary_keys
        or not all(
            _is_int(summary.get(key)) and summary[key] >= 0
            for key in (
                "input_rows",
                "accepted_rows",
                "excluded_rows",
                "quarantined_contract",
            )
        )
        or summary["input_rows"] != expected_rows
        or summary["accepted_rows"] + summary["excluded_rows"]
        != summary["input_rows"]
        or summary["quarantined_contract"] != 0
        or summary.get("privacy") != {"aggregate_only": True}
        or not isinstance(summary.get("by_species"), dict)
        or set(summary["by_species"]) != set(SPECIES)
    ):
        raise NormalizationError("normalization_summary_semantic_failure")

    species_totals = Counter()
    for species_summary in summary["by_species"].values():
        if (
            not isinstance(species_summary, dict)
            or set(species_summary)
            != {"input_rows", "accepted_rows", "excluded_rows", "presence_cells"}
            or not all(
                _is_int(species_summary.get(key)) and species_summary[key] >= 0
                for key in species_summary
            )
            or species_summary["accepted_rows"] + species_summary["excluded_rows"]
            != species_summary["input_rows"]
            or species_summary["presence_cells"] > species_summary["accepted_rows"]
        ):
            raise NormalizationError("normalization_species_semantic_failure")
        species_totals.update(species_summary)
    if (
        species_totals["input_rows"] != summary["input_rows"]
        or species_totals["accepted_rows"] != summary["accepted_rows"]
        or species_totals["excluded_rows"] != summary["excluded_rows"]
    ):
        raise NormalizationError("normalization_species_reconciliation_failure")

    for key in ("by_reason", "by_taxon_basis", "by_uncertainty_band"):
        if not _nonnegative_counts(summary.get(key)):
            raise NormalizationError("normalization_count_map_failure")
    if (
        sum(summary["by_reason"].values()) != summary["input_rows"]
        or summary["by_reason"].get("accepted", 0) != summary["accepted_rows"]
        or not set(summary["by_reason"]).issubset({"accepted", *PRIMARY_REASONS})
        or sum(summary["by_taxon_basis"].values()) != summary["input_rows"]
        or sum(summary["by_uncertainty_band"].values()) != summary["input_rows"]
    ):
        raise NormalizationError("normalization_count_reconciliation_failure")

    spatial_summary = payloads["spatial_summary.json"]
    distance = spatial_summary.get("centroid_distance_m")
    if (
        set(spatial_summary)
        != {"accepted_cells", "centroid_distance_m", "low_cell_certainty_rows"}
        or not _is_int(spatial_summary.get("accepted_cells"))
        or spatial_summary["accepted_cells"] < 0
        or not _is_int(spatial_summary.get("low_cell_certainty_rows"))
        or not isinstance(distance, dict)
        or set(distance) != {"max", "n"}
        or not isinstance(distance.get("max"), (int, float))
        or isinstance(distance.get("max"), bool)
        or not math.isfinite(float(distance["max"]))
        or distance["max"] < 0
        or distance.get("n") != summary["accepted_rows"]
        or spatial_summary["low_cell_certainty_rows"] > summary["accepted_rows"]
    ):
        raise NormalizationError("spatial_summary_semantic_failure")

    outputs = payloads["outputs.json"]
    if (
        set(outputs)
        != {
            "row_audit_rows",
            "presence_rows",
            "row_audit_sha256",
            "presence_sha256",
            "schemas",
        }
        or outputs.get("row_audit_rows") != summary["input_rows"]
        or outputs.get("presence_rows") != spatial_summary["accepted_cells"]
        or outputs["presence_rows"] != species_totals["presence_cells"]
        or not isinstance(outputs.get("row_audit_sha256"), str)
        or SHA256_RE.fullmatch(outputs["row_audit_sha256"]) is None
        or not isinstance(outputs.get("presence_sha256"), str)
        or SHA256_RE.fullmatch(outputs["presence_sha256"]) is None
        or outputs.get("schemas")
        != {
            "row_audit": list(AUDIT_FIELDS),
            "presence": list(PRESENCE_FIELDS),
        }
    ):
        raise NormalizationError("outputs_semantic_failure")

    review = payloads["review.json"]
    if (
        set(review) != {"readiness", "raw_replay_required", "privacy"}
        or review.get("readiness") != "goal018_spatial_normalization_complete"
        or review.get("raw_replay_required") is not True
        or review.get("privacy")
        != {
            "row_values_retained": False,
            "coordinates_retained": False,
            "record_ids_retained": False,
            "coordinates": False,
            "dates": False,
            "account_values": False,
            "resource_values": False,
            "dataset_values": False,
        }
    ):
        raise NormalizationError("review_semantic_failure")


def _recompute(
    plan: Mapping[str, Any], paths: Mapping[str, Path]
) -> dict[str, Any]:
    rows, _occurrence, raw_hashes = _load_source_rows(
        paths["raw_directory"],
        paths["raw_manifest"],
        int(plan["expected_input_rows"]),
    )
    grid = _read_grid(paths["grid"])
    polygons = _shapefile_polygons(paths["coast_shp"])
    audit, accepted = normalize_rows(
        rows, grid, polygons, raw_hashes=raw_hashes
    )
    return {
        "rows": rows,
        "audit": audit,
        "accepted": accepted,
        "presence": collapse_presence(accepted),
    }


def _validate_output_replay(
    output_dir: Path, audit: list[dict[str, Any]], presence: list[dict[str, Any]]
) -> None:
    if not output_dir.is_dir() or output_dir.is_symlink():
        raise NormalizationError("output_directory_invalid")
    observed = {
        path.name
        for path in output_dir.iterdir()
        if path.is_file() or path.is_symlink()
    }
    if observed != {"row_audit.csv", "presence.csv"}:
        raise NormalizationError("output_footprint_drift")
    with tempfile.TemporaryDirectory(prefix="goal018-replay-") as directory:
        expected = Path(directory)
        _write_csv(expected / "row_audit.csv", AUDIT_FIELDS, audit)
        _write_csv(expected / "presence.csv", PRESENCE_FIELDS, presence)
        for name in ("row_audit.csv", "presence.csv"):
            actual_path = output_dir / name
            if (
                not actual_path.is_file()
                or actual_path.is_symlink()
                or actual_path.read_bytes() != (expected / name).read_bytes()
            ):
                raise NormalizationError("output_semantic_replay_failure")


def validate_evidence(
    plan_path: Path,
    evidence_dir: Path,
    raw_root: Path | None = None,
    output_dir: Path | None = None,
    *,
    goal017_validator=None,
) -> dict[str, Any]:
    try:
        plan = json.loads(Path(plan_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise NormalizationError("plan_json_invalid") from exc
    validate_plan(plan)
    payloads = _read_evidence_bundle(Path(evidence_dir))
    _validate_tracked_payloads(plan, payloads)
    if raw_root is None:
        if output_dir is not None:
            raise NormalizationError("full_validation_inputs_required")
        return {
            "readiness": "goal018_tracked_evidence_valid_raw_replay_required",
            "raw_replay_required": True,
        }
    if output_dir is None:
        raise NormalizationError("full_validation_inputs_required")

    paths = _bound_inputs(plan_path, plan, raw_root=Path(raw_root))
    _validate_goal017(paths, goal017_validator)
    recomputed = _recompute(plan, paths)
    _validate_output_replay(
        Path(output_dir), recomputed["audit"], recomputed["presence"]
    )
    expected_payloads = _build_evidence_payloads(
        plan,
        paths,
        recomputed["rows"],
        recomputed["audit"],
        recomputed["accepted"],
        recomputed["presence"],
        Path(output_dir),
    )
    if payloads != expected_payloads:
        raise NormalizationError("aggregate_evidence_semantic_replay_failure")
    return {
        "readiness": "goal018_spatial_normalization_complete",
        "raw_replay_required": False,
    }


def run(plan_path: Path, *, raw_root: Path | None = None, raw_manifest_path: Path | None = None, grid_path: Path | None = None, coast_path: Path | None = None, output_dir: Path | None = None, evidence_dir: Path | None = None, goal017_validator=None) -> dict[str, Any]:
    try:
        plan = json.loads(Path(plan_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise NormalizationError("plan_json_invalid") from exc
    validate_plan(plan)
    root = Path(plan_path).resolve().parents[1]
    paths = _bound_inputs(
        plan_path,
        plan,
        raw_root=raw_root,
        raw_manifest_path=raw_manifest_path,
        grid_path=grid_path,
        coast_path=coast_path,
    )
    _validate_goal017(paths, goal017_validator)
    recomputed = _recompute(plan, paths)
    rows = recomputed["rows"]
    audit = recomputed["audit"]
    accepted = recomputed["accepted"]
    presence = recomputed["presence"]

    output_dir = output_dir or root / plan["outputs"]["directory"]
    evidence_dir = evidence_dir or root / plan["evidence"]["directory"]
    output_dir = Path(output_dir); evidence_dir = Path(evidence_dir)
    if output_dir.exists() or evidence_dir.exists(): raise NormalizationError("output_directory_exists")
    parent = output_dir.parent; parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="goal018-stage-", dir=parent))
    try:
        _write_csv(stage / "row_audit.csv", AUDIT_FIELDS, audit); _write_csv(stage / "presence.csv", PRESENCE_FIELDS, presence)
        evidence_dir.parent.mkdir(parents=True, exist_ok=True); evstage = Path(tempfile.mkdtemp(prefix="goal018-evidence-", dir=evidence_dir.parent))
        payloads = _build_evidence_payloads(
            plan, paths, rows, audit, accepted, presence, stage
        )
        _write_evidence_bundle(evstage, payloads)
        validate_evidence(
            Path(plan_path),
            evstage,
            raw_root=paths["raw_directory"],
            output_dir=stage,
            goal017_validator=goal017_validator,
        )
        stage.rename(output_dir)
        try:
            evstage.rename(evidence_dir)
        except Exception:
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
            raise
    except Exception:
        import shutil; shutil.rmtree(stage, ignore_errors=True); raise
    return {"readiness": "goal018_spatial_normalization_complete", "input_rows": len(rows), "accepted_rows": len(accepted), "presence_rows": len(presence)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Goal018 offline ALA spatial normalization")
    sub = ap.add_subparsers(dest="command", required=True)
    rp = sub.add_parser("run"); rp.add_argument("--plan", type=Path, required=True)
    vp = sub.add_parser("validate"); vp.add_argument("--plan", type=Path, required=True); vp.add_argument("--evidence-dir", type=Path, required=True); vp.add_argument("--raw-dir", type=Path); vp.add_argument("--output-dir", type=Path)
    args = ap.parse_args(argv)
    try:
        result = run(args.plan) if args.command == "run" else validate_evidence(args.plan, args.evidence_dir, raw_root=args.raw_dir, output_dir=args.output_dir)
    except (NormalizationError, OSError) as exc:
        print(json.dumps({"readiness": "blocked", "reason": str(exc)})); return 2
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
