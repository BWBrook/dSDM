"""Goal019 deterministic, privacy-safe camera spatial normalisation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

from shapely.geometry import MultiPolygon, Point, Polygon

from .ala_spatial_normalization import (
    GEOD,
    _coast_covers,
    _read_grid,
    _shapefile_polygons,
    candidate_centroid,
    grid_cell_id,
    sha256,
)
from .contracts import validate_phase1_decision_bundle


GOAL_ID = "goal019-camera-spatial-normalization-2026-07-24"
ACTIVE_SPECIES = (
    "thylogale_billardierii",
    "notamacropus_rufogriseus",
    "trichosurus_vulpecula",
    "pseudocheirus_peregrinus",
    "vombatus_ursinus",
    "sarcophilus_harrisii",
    "dasyurus_maculatus",
    "dasyurus_viverrinus",
)
ISLAND_CODES = ("KI", "FI", "CBI", "CI", "THI", "HI", "MI", "BI")
OUTPUT_FILES = (
    "observation_audit.csv",
    "site_audit.csv",
    "site_species.csv",
    "grid_evidence.csv",
)
EVIDENCE_PAYLOAD_FILES = (
    "source_inventory.json",
    "normalization_summary.json",
    "spatial_summary.json",
    "outputs.json",
    "review.json",
)
EVIDENCE_FILES = (*EVIDENCE_PAYLOAD_FILES, "manifest.json")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
CANONICAL_OUTPUT_DIRECTORY = (
    "data/processed/camera/goal019-spatial-normalization/2026-07-24"
)
CANONICAL_EVIDENCE_DIRECTORY = (
    "evidence/camera_spatial_normalization/2026-07-24"
)
PLAN_PRIVACY = {
    "tracked_private_paths": False,
    "tracked_source_codes": False,
    "tracked_site_or_survey_ids": False,
    "tracked_coordinates_or_grid_ids": False,
    "tracked_dates_or_media_ids": False,
    "tracked_row_values": False,
}
REVIEW_PRIVACY = {
    "row_values_retained": False,
    "site_or_survey_ids_retained": False,
    "coordinates_or_grid_ids_retained": False,
    "dates_or_media_ids_retained": False,
    "source_codes_retained": False,
    "private_paths_retained": False,
}
SITE_DISPOSITION_KEYS = (
    "eligible",
    "invalid_site_location",
    "unreferenced_site",
)
SITE_EXCLUSION_REASON_KEYS = (
    "outside_land_boundary",
    "ineligible_grid_cell",
    "unreferenced_site",
)
OBSERVATION_DISPOSITION_KEYS = (
    "accepted_focal_presence",
    "accepted_operational_witness",
)
SPECIES_SUMMARY_KEYS = {
    "detection_sites",
    "presence_site_species_rows",
    "survey_supported_absence_rows",
    "island_absence_suppressions",
    "presence_grid_rows",
    "survey_supported_absence_grid_rows",
}
SOURCE_INVENTORY_KEYS = {
    "goal_id",
    "private_source_manifest_sha256",
    "private_input_roles",
    "frozen_bindings",
    "species_count",
    "excluded_downstream_species",
}
NORMALIZATION_SUMMARY_KEYS = {
    "observation_rows",
    "observation_rows_reconciled",
    "unique_observation_id_count",
    "observation_dispositions",
    "distinct_survey_count",
    "species_lookup_rows",
    "species_lookup_distinct_codes",
    "species_lookup_ambiguous_nonfocal_codes",
    "location_rows",
    "location_sites",
    "observation_bearing_sites",
    "eligible_sites",
    "site_dispositions",
    "site_species_rows_before_suppression",
    "expected_site_species_rows",
    "species_island_absence_suppressions",
    "retained_site_species_rows",
    "classification_counts",
    "grid_classification_counts",
    "grid_evidence_rows",
    "by_species",
    "privacy",
}
SPATIAL_SUMMARY_KEYS = {
    "canonical_grid_rows",
    "location_rows",
    "location_sites",
    "repeated_coordinate_sites",
    "repeated_coordinate_rows",
    "site_dispositions",
    "site_exclusion_reason_counts",
    "eligible_sites",
    "observation_bearing_island_site_counts",
    "eligible_island_site_counts",
    "max_centroid_distance_m",
    "ambiguous_site_locations",
    "matrix_conflicting_presences",
}
OUTPUTS_PAYLOAD_KEYS = {"private_output_roles", "private_outputs_ignored"}
REVIEW_PAYLOAD_KEYS = {
    "readiness",
    "private_raw_replay_required",
    "matrix_conflicting_presences",
    "privacy",
    "classification",
    "stopped_before",
}

OBSERVATION_FIELDS = (
    "observation_row_id",
    "source_row_ordinal",
    "raw_observation_id",
    "survey_id",
    "site_id",
    "observed_datetime",
    "flash",
    "count",
    "source_code",
    "source_filename",
    "image_id",
    "focal_species_id",
    "observation_state",
    "reason_code",
)
SITE_FIELDS = (
    "site_id",
    "coordinate_row_count",
    "raw_coordinate_pairs",
    "grid_cell_id",
    "centroid_lon",
    "centroid_lat",
    "island_code",
    "centroid_distance_max_m",
    "observation_row_count",
    "in_window_observation_row_count",
    "site_state",
    "reason_code",
)
SITE_SPECIES_FIELDS = (
    "site_id",
    "species_id",
    "grid_cell_id",
    "centroid_lon",
    "centroid_lat",
    "island_code",
    "classification",
    "pa",
    "pa_type",
    "survey_supported_absence_rule_id",
    "positive_source_row_count",
)
GRID_FIELDS = (
    "species_id",
    "grid_cell_id",
    "centroid_lon",
    "centroid_lat",
    "pa",
    "pa_type",
    "survey_supported_absence_rule_id",
    "site_count",
    "presence_site_count",
    "survey_supported_absence_site_count",
    "positive_source_row_count",
    "source_conflict",
)
OUTPUT_SCHEMAS = {
    "observation_audit": OBSERVATION_FIELDS,
    "site_audit": SITE_FIELDS,
    "site_species": SITE_SPECIES_FIELDS,
    "grid_evidence": GRID_FIELDS,
}

EXPECTED_BINDING_HASHES = {
    "goal018_plan": "6dff937876ea572babdc0f74944edb5d9311af0d6295c58cee1923ace587c5c7",
    "decision_bundle": "5af1f76c58bd24fe61a741a42a4df4531ba21e08c0d8ce9b953ba0ff769668ae",
    "grid": "91c7e0158ee8a808e9345d4bca28ec3e3fd7468dc3b7b1c1268e33e2da9499da",
    "coast_shp": "015270fc146045bd78c13586642630d50715fe15c759c817706e398bf0a0a00a",
    "coast_shx": "3bb02b6e7eaa3535b01c72c2faead97551a76bd5c5b0bf0c40fc85c225c9089d",
    "coast_dbf": "96859dc4e261fe28c41ba1f10570b9ce0cb3489614a9413c697b0b373bb83adb",
    "coast_prj": "a02a27b1d1982c8516d83398e85a3c8b1aef1713c13ef4d84d7bde17430c07c4",
    "offshore_islands": "98ca7bf213f0760894d9ad329681e2f2c9e491a8255577fae20fd31c73685d92",
}
EXPECTED_PRIVATE = {
    "site_locations": {
        "sha256": "566654a6a3ce6fe004649455b04fe3c1be35df19f208dbe89c29b0a766f8d2e0",
        "bytes": 42687,
        "data_rows": 1388,
        "schema_sha256": "37f4d3815f42ad077ce41881f1b69d63e2bad8ecfa06b1b1784b090cbc72c7d6",
    },
    "species_lookup": {
        "sha256": "f2e9cee22a7321e9f5c3985289ffb1876e8396816d4ee63e55e9d0cf0c198d9f",
        "bytes": 2980,
        "data_rows": 142,
        "schema_sha256": "167de540612993de9e9db6a85ec44f7ee4a7c5a31abf86982901979b07baa0d2",
    },
    "observations": {
        "sha256": "46898370a27eb3528f722aa911e77b3e905e9d72942ec2fe18ece7720f51e9b2",
        "bytes": 66467130,
        "data_rows": 836548,
        "schema_sha256": "c3e3f44f43f95529ec90d272961ae55aec3a07975b99e2eda6a5a8d54f88e94e",
    },
    "focal_crosswalk": {
        "sha256": "2bd2778bdd2df8dd282b75ef48ba6b0fdc18b90a52263453b9ba95dc68cf4076",
        "bytes": 921,
        "mapping_rows": 8,
    },
}
FORBIDDEN_EVIDENCE_KEYS = {
    "site_id",
    "survey",
    "survey_id",
    "longitude",
    "latitude",
    "lon",
    "lat",
    "coordinate",
    "coordinates",
    "grid_cell_id",
    "datetime",
    "date",
    "filename",
    "imageid",
    "image_id",
    "source_code",
    "source_path",
    "private_path",
    "raw_row",
    "raw_values",
}


class CameraNormalizationError(ValueError):
    pass


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _schema_sha256(columns: Iterable[str]) -> str:
    payload = json.dumps(list(columns), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _safe_relative_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise CameraNormalizationError("private_manifest_path_invalid")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise CameraNormalizationError("private_manifest_path_unsafe")
    return path


def _validate_exact_directory_files(
    directory: Path,
    expected_names: Iterable[str],
    *,
    directory_error: str,
    footprint_error: str,
) -> None:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise CameraNormalizationError(directory_error)
    expected = set(expected_names)
    entries = list(directory.iterdir())
    if (
        len(entries) != len(expected)
        or {entry.name for entry in entries} != expected
        or any(not entry.is_file() or entry.is_symlink() for entry in entries)
    ):
        raise CameraNormalizationError(footprint_error)


def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(plan, Mapping)
        or plan.get("schema_version") != "1.0"
        or plan.get("goal_id") != GOAL_ID
    ):
        raise CameraNormalizationError("plan_identity_drift")
    bindings = plan.get("bindings")
    if not isinstance(bindings, Mapping) or set(bindings) != set(EXPECTED_BINDING_HASHES):
        raise CameraNormalizationError("plan_binding_shape_drift")
    for role, expected_hash in EXPECTED_BINDING_HASHES.items():
        binding = bindings.get(role)
        if (
            not isinstance(binding, Mapping)
            or binding.get("sha256") != expected_hash
            or not isinstance(binding.get("path"), str)
        ):
            raise CameraNormalizationError("plan_binding_drift")
        path = Path(binding["path"])
        if path.is_absolute() or ".." in path.parts:
            raise CameraNormalizationError("plan_binding_path_unsafe")

    private_roles = plan.get("private_inputs", {}).get("roles")
    if private_roles != EXPECTED_PRIVATE:
        raise CameraNormalizationError("private_role_contract_drift")
    species = plan.get("species_contract", {})
    if species.get("active_species_ids") != list(ACTIVE_SPECIES):
        raise CameraNormalizationError("active_species_contract_drift")
    excluded = species.get("excluded_downstream")
    if (
        not isinstance(excluded, Mapping)
        or excluded.get("species_id") != "macropus_giganteus"
        or excluded.get("reason")
        != "historically_constrained_remnant_contemporary_range"
        or excluded.get("prior_goal017_goal018_provenance_retained") is not True
    ):
        raise CameraNormalizationError("downstream_exclusion_contract_drift")

    spatial = plan.get("spatial_contract", {})
    if (
        spatial.get("crs") != "EPSG:4326"
        or spatial.get("grid_rows") != 74073
        or spatial.get("resolution_degree") != 0.01
        or spatial.get("origin_lower_edge") != [143.84, -43.6425]
        or spatial.get("assignment") != "containing_eligible_cell_only"
        or spatial.get("nearest_rescue") is not False
        or spatial.get("island_codes") != list(ISLAND_CODES)
        or spatial.get("coast_predicate") != "covers"
        or spatial.get("island_predicate") != "covers"
    ):
        raise CameraNormalizationError("spatial_contract_drift")
    source = plan.get("source_contract", {})
    if (
        source.get("analytical_unit")
        != "stable_camera_site_x_focal_species_whole_dataset"
        or source.get("survey_role") != "provenance_only"
        or source.get("temporal_window")
        != {"start_year": 2001, "end_year": 2025, "inclusive": True}
        or source.get("deployment_assertion")
        != "barry_broad_3_to_4_year_near_continuous"
        or source.get("detailed_effort_analysis") is not False
        or source.get("nonfocal_rows_are_operational_witnesses") is not True
        or source.get("positive_focal_count_is_presence") is not True
    ):
        raise CameraNormalizationError("source_contract_drift")
    classification = plan.get("classification_contract", {})
    if (
        classification.get("classes")
        != ["presence", "survey_supported_absence"]
        or classification.get("absence_rule_id") != "P1-D009"
        or classification.get("presence_dominates_within_camera_source") is not True
        or classification.get("species_island_absence_exclusion") is not True
        or classification.get("matrix_conflicting_presence")
        != "publication_blocker"
    ):
        raise CameraNormalizationError("classification_contract_drift")
    if (
        plan.get("outputs")
        != {
            "directory": CANONICAL_OUTPUT_DIRECTORY,
            "files": list(OUTPUT_FILES),
            "private_ignored": True,
        }
        or plan.get("evidence")
        != {
            "directory": CANONICAL_EVIDENCE_DIRECTORY,
            "files": list(EVIDENCE_FILES),
            "aggregate_only": True,
        }
        or plan.get("privacy") != PLAN_PRIVACY
        or plan.get("legacy_comparison")
        != {"runtime_input": False, "gate_target": False}
        or plan.get("atomic_publish") is not True
    ):
        raise CameraNormalizationError("publication_or_privacy_contract_drift")
    return {"goal_id": GOAL_ID, "species_count": len(ACTIVE_SPECIES)}


def _load_plan(plan_path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CameraNormalizationError("plan_json_invalid") from exc
    validate_plan(value)
    return value


def _bound_tracked_inputs(
    plan_path: Path, plan: Mapping[str, Any]
) -> dict[str, Path]:
    root = Path(plan_path).resolve().parents[1]
    paths: dict[str, Path] = {}
    for role, binding in plan["bindings"].items():
        relative = Path(binding["path"])
        path = (root / relative).resolve()
        if (
            not path.is_file()
            or path.is_symlink()
            or sha256(path) != binding["sha256"]
        ):
            raise CameraNormalizationError("tracked_binding_drift")
        paths[role] = path
    try:
        goal018 = json.loads(paths["goal018_plan"].read_text(encoding="utf-8"))
        bundle = json.loads(paths["decision_bundle"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CameraNormalizationError("tracked_binding_json_invalid") from exc
    if (
        goal018.get("bindings", {}).get("grid", {}).get("sha256")
        != plan["bindings"]["grid"]["sha256"]
        or goal018.get("spatial_bindings", {}).get("grid", {}).get("row_count")
        != 74073
    ):
        raise CameraNormalizationError("goal018_spatial_binding_drift")
    try:
        validate_phase1_decision_bundle(bundle)
    except Exception as exc:
        raise CameraNormalizationError("decision_bundle_invalid") from exc
    return paths


def validate_private_manifest(
    plan: Mapping[str, Any],
    private_dir: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Path]:
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != "1.0":
        raise CameraNormalizationError("private_manifest_schema_failure")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise CameraNormalizationError("private_manifest_schema_failure")
    by_role: dict[str, Mapping[str, Any]] = {}
    paths: dict[str, Path] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise CameraNormalizationError("private_manifest_schema_failure")
        role = entry.get("role")
        if role not in EXPECTED_PRIVATE or role in by_role:
            raise CameraNormalizationError("private_manifest_role_failure")
        relative = _safe_relative_path(entry.get("path"))
        expected = plan["private_inputs"]["roles"][role]
        for key in ("sha256", "bytes"):
            if entry.get(key) != expected[key]:
                raise CameraNormalizationError("private_manifest_binding_drift")
        if role == "focal_crosswalk":
            if entry.get("mapping_rows") != expected["mapping_rows"]:
                raise CameraNormalizationError("private_manifest_binding_drift")
            expected_keys = {"role", "path", "bytes", "mapping_rows", "sha256"}
        else:
            if (
                entry.get("data_rows") != expected["data_rows"]
                or not isinstance(entry.get("columns"), list)
                or _schema_sha256(entry["columns"]) != expected["schema_sha256"]
            ):
                raise CameraNormalizationError("private_manifest_binding_drift")
            expected_keys = {
                "role",
                "path",
                "bytes",
                "data_rows",
                "sha256",
                "columns",
            }
        if set(entry) != expected_keys:
            raise CameraNormalizationError("private_manifest_schema_failure")
        by_role[role] = entry
        paths[role] = Path(private_dir) / relative
    if set(by_role) != set(EXPECTED_PRIVATE):
        raise CameraNormalizationError("private_manifest_footprint_drift")

    private_dir = Path(private_dir)
    expected_names = {entry["path"] for entry in entries} | {"source_manifest.json"}
    _validate_exact_directory_files(
        private_dir,
        expected_names,
        directory_error="private_directory_invalid",
        footprint_error="private_manifest_footprint_drift",
    )
    for role, path in paths.items():
        entry = by_role[role]
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != entry["bytes"]
            or sha256(path) != entry["sha256"]
        ):
            raise CameraNormalizationError("private_source_binding_drift")
        if role == "focal_crosswalk":
            continue
        try:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.reader(stream)
                header = next(reader)
                row_count = sum(1 for _ in reader)
        except (OSError, csv.Error, StopIteration) as exc:
            raise CameraNormalizationError("private_source_csv_invalid") from exc
        if (
            header != entry["columns"]
            or _schema_sha256(header)
            != plan["private_inputs"]["roles"][role]["schema_sha256"]
            or row_count != entry["data_rows"]
        ):
            raise CameraNormalizationError("private_source_schema_or_rows_drift")
    return paths


def _load_private_inputs(
    plan: Mapping[str, Any], private_dir: Path
) -> tuple[dict[str, Path], dict[str, Any], str]:
    private_dir = Path(private_dir)
    manifest_path = private_dir / "source_manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise CameraNormalizationError("private_manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CameraNormalizationError("private_manifest_json_invalid") from exc
    paths = validate_private_manifest(plan, private_dir, manifest)
    return paths, manifest, sha256(manifest_path)


def _load_crosswalk(path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CameraNormalizationError("private_crosswalk_invalid") from exc
    if (
        not isinstance(value, Mapping)
        or value.get("schema_version") != "1.0"
        or not isinstance(value.get("mappings"), list)
        or len(value["mappings"]) != len(ACTIVE_SPECIES)
    ):
        raise CameraNormalizationError("private_crosswalk_invalid")
    mapping: dict[str, str] = {}
    for row in value["mappings"]:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"source_code", "species_id"}
            or not isinstance(row.get("source_code"), str)
            or not row["source_code"]
            or row["source_code"] in mapping
            or row.get("species_id") not in ACTIVE_SPECIES
        ):
            raise CameraNormalizationError("private_crosswalk_invalid")
        mapping[row["source_code"]] = row["species_id"]
    if set(mapping.values()) != set(ACTIVE_SPECIES):
        raise CameraNormalizationError("private_crosswalk_invalid")
    excluded = value.get("excluded_downstream")
    if (
        not isinstance(excluded, Mapping)
        or excluded.get("species_id") != "macropus_giganteus"
        or excluded.get("prior_goal017_goal018_provenance_retained") is not True
    ):
        raise CameraNormalizationError("private_crosswalk_invalid")
    return mapping, value


def _load_lookup(path: Path, focal_codes: set[str]) -> dict[str, Any]:
    groups: dict[str, int] = Counter()
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["species", "code"]:
                raise CameraNormalizationError("species_lookup_schema_failure")
            rows = 0
            for row in reader:
                rows += 1
                if (
                    set(row) != {"species", "code"}
                    or not row["species"].strip()
                    or not row["code"].strip()
                ):
                    raise CameraNormalizationError("species_lookup_row_failure")
                groups[row["code"].strip()] += 1
    except (OSError, csv.Error) as exc:
        raise CameraNormalizationError("species_lookup_csv_invalid") from exc
    ambiguous = {code for code, count in groups.items() if count > 1}
    if not focal_codes.issubset(groups) or ambiguous & focal_codes:
        raise CameraNormalizationError("focal_code_ambiguity")
    return {
        "rows": rows,
        "distinct_codes": len(groups),
        "ambiguous_codes": ambiguous,
        "all_codes": set(groups),
    }


def _load_islands(path: Path) -> dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        raise CameraNormalizationError("island_geometry_invalid") from exc
    islands: dict[str, Any] = {}
    for placemark in root.findall(".//{*}Placemark"):
        name = placemark.find("{*}name")
        code = "" if name is None or name.text is None else name.text.strip()
        polygons = []
        for element in placemark.findall(".//{*}Polygon"):
            outer = element.find(
                "{*}outerBoundaryIs/{*}LinearRing/{*}coordinates"
            )
            if outer is None or not outer.text:
                raise CameraNormalizationError("island_geometry_contract_failure")
            shell = [
                tuple(float(value) for value in token.split(",")[:2])
                for token in outer.text.split()
            ]
            holes = []
            for inner in element.findall(
                "{*}innerBoundaryIs/{*}LinearRing/{*}coordinates"
            ):
                if inner.text:
                    holes.append(
                        [
                            tuple(float(value) for value in token.split(",")[:2])
                            for token in inner.text.split()
                        ]
                    )
            polygons.append(Polygon(shell, holes))
        geometry = (
            polygons[0]
            if len(polygons) == 1
            else MultiPolygon(polygons)
            if polygons
            else None
        )
        if (
            code not in ISLAND_CODES
            or code in islands
            or geometry is None
            or geometry.is_empty
            or not geometry.is_valid
        ):
            raise CameraNormalizationError("island_geometry_contract_failure")
        islands[code] = geometry
    if set(islands) != set(ISLAND_CODES):
        raise CameraNormalizationError("island_geometry_footprint_drift")
    return islands


def classify_location_rows(
    coordinates: Iterable[tuple[float, float]],
    grid: Mapping[str, tuple[float, float]],
    coast: Any,
    islands: Mapping[str, Any],
) -> dict[str, Any]:
    cells: set[str] = set()
    island_classes: set[str] = set()
    centroids: set[tuple[float, float]] = set()
    distances: list[float] = []
    failures: list[str] = []
    count = 0
    for lon, lat in coordinates:
        count += 1
        if (
            not isinstance(lon, (int, float))
            or not isinstance(lat, (int, float))
            or isinstance(lon, bool)
            or isinstance(lat, bool)
            or not math.isfinite(float(lon))
            or not math.isfinite(float(lat))
            or not (-180 <= lon <= 180 and -90 <= lat <= 90)
        ):
            failures.append("coordinates_invalid")
            continue
        hits = [
            code
            for code, geometry in islands.items()
            if geometry.covers(Point(float(lon), float(lat)))
        ]
        if len(hits) > 1:
            return {
                "state": "ambiguous_site_location",
                "reason": "ambiguous_island_class",
            }
        island_classes.add(hits[0] if hits else "")
        centroid = candidate_centroid(float(lon), float(lat))
        if centroid is None:
            failures.append("outside_lattice")
            continue
        cell = grid_cell_id(*centroid)
        cells.add(cell)
        if not _coast_covers(float(lon), float(lat), coast):
            failures.append("outside_land_boundary")
        if cell not in grid:
            failures.append("ineligible_grid_cell")
            continue
        centroids.add(tuple(grid[cell]))
        distances.append(
            abs(float(GEOD.inv(centroid[0], centroid[1], lon, lat)[2]))
        )
    if count == 0:
        return {"state": "invalid_site_location", "reason": "coordinates_missing"}
    if len(cells) > 1 or len(island_classes) > 1 or len(centroids) > 1:
        return {"state": "ambiguous_site_location", "reason": "ambiguous_site_location"}
    island_code = next(iter(island_classes), "")
    if failures:
        priority = (
            "coordinates_invalid",
            "outside_lattice",
            "outside_land_boundary",
            "ineligible_grid_cell",
        )
        reason = next(item for item in priority if item in failures)
        return {
            "state": "invalid_site_location",
            "reason": reason,
            "island_code": island_code,
        }
    if len(cells) != 1 or len(centroids) != 1:
        return {"state": "invalid_site_location", "reason": "coordinates_invalid"}
    centroid = next(iter(centroids))
    return {
        "state": "eligible",
        "reason": "",
        "grid_cell_id": next(iter(cells)),
        "centroid_lon": centroid[0],
        "centroid_lat": centroid[1],
        "island_code": island_code,
        "centroid_distance_max_m": round(max(distances), 6),
    }


def site_disposition(
    spatial: Mapping[str, Any],
    *,
    has_observations: bool,
    in_window_rows: int,
) -> tuple[str, str]:
    if not has_observations:
        return "unreferenced_site", "unreferenced_site"
    if in_window_rows == 0:
        return "outside_temporal_window", "no_in_window_observation"
    if spatial.get("state") != "eligible":
        return str(spatial.get("state")), str(spatial.get("reason"))
    return "eligible", ""


def _positive_count(value: str) -> Decimal:
    try:
        count = Decimal(value)
    except InvalidOperation as exc:
        raise CameraNormalizationError("observation_count_invalid") from exc
    if not count.is_finite() or count <= 0:
        raise CameraNormalizationError("observation_count_invalid")
    return count


def _observation_year(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
    except ValueError as exc:
        raise CameraNormalizationError("observation_datetime_invalid") from exc
    return parsed.year


def _observation_row_id(raw_hash: str, ordinal: int) -> str:
    return hashlib.sha256(
        f"camera_observation\0{raw_hash}\0{ordinal}".encode()
    ).hexdigest()


def _write_header(path: Path, fields: tuple[str, ...]):
    stream = path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        stream, fieldnames=list(fields), lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    return stream, writer


def _write_rows(
    path: Path, fields: tuple[str, ...], rows: Iterable[Mapping[str, Any]]
) -> int:
    stream, writer = _write_header(path, fields)
    count = 0
    try:
        for row in rows:
            writer.writerow(row)
            count += 1
    finally:
        stream.close()
    return count


def build_site_species_rows(
    eligible_sites: Mapping[str, Mapping[str, Any]],
    detections: Mapping[tuple[str, str], int] | set[tuple[str, str]],
    species_ids: Iterable[str],
    island_exclusions: Mapping[str, Iterable[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    species_ids = tuple(species_ids)
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for site_id in sorted(eligible_sites):
        site = eligible_sites[site_id]
        for species_id in species_ids:
            key = (site_id, species_id)
            if isinstance(detections, set):
                positive_rows = 1 if key in detections else 0
            else:
                positive_rows = int(detections.get(key, 0))
            excluded = site.get("island_code", "") in set(
                island_exclusions.get(species_id, ())
            )
            if positive_rows:
                classification = "presence"
                pa: int | str = 1
                pa_type = "presence"
                rule_id = ""
            elif excluded:
                classification = "species_island_absence_exclusion"
                pa = ""
                pa_type = ""
                rule_id = ""
            else:
                classification = "survey_supported_absence"
                pa = 0
                pa_type = "survey_supported_absence"
                rule_id = "P1-D009"
            row = {
                "site_id": site_id,
                "species_id": species_id,
                "grid_cell_id": site["grid_cell_id"],
                "centroid_lon": site.get("centroid_lon", ""),
                "centroid_lat": site.get("centroid_lat", ""),
                "island_code": site.get("island_code", ""),
                "classification": classification,
                "pa": pa,
                "pa_type": pa_type,
                "survey_supported_absence_rule_id": rule_id,
                "positive_source_row_count": positive_rows,
            }
            rows.append(row)
            if positive_rows and excluded:
                blockers.append(row)
    return rows, blockers


def collapse_grid_evidence(
    site_species_rows: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in site_species_rows:
        if row["classification"] == "species_island_absence_exclusion":
            continue
        groups[(str(row["species_id"]), str(row["grid_cell_id"]))].append(row)
    output: list[dict[str, Any]] = []
    for (species_id, cell), rows in sorted(groups.items()):
        presence_rows = [row for row in rows if row["classification"] == "presence"]
        absence_rows = [
            row
            for row in rows
            if row["classification"] == "survey_supported_absence"
        ]
        if len(presence_rows) + len(absence_rows) != len(rows):
            raise CameraNormalizationError("site_species_classification_invalid")
        centroids = {
            (row.get("centroid_lon", ""), row.get("centroid_lat", "")) for row in rows
        }
        if len(centroids) != 1:
            raise CameraNormalizationError("grid_centroid_invariant_failure")
        centroid = next(iter(centroids))
        present = bool(presence_rows)
        output.append(
            {
                "species_id": species_id,
                "grid_cell_id": cell,
                "centroid_lon": centroid[0],
                "centroid_lat": centroid[1],
                "pa": 1 if present else 0,
                "pa_type": "presence" if present else "survey_supported_absence",
                "survey_supported_absence_rule_id": "" if present else "P1-D009",
                "site_count": len(rows),
                "presence_site_count": len(presence_rows),
                "survey_supported_absence_site_count": len(absence_rows),
                "positive_source_row_count": sum(
                    int(row.get("positive_source_row_count", 0))
                    for row in presence_rows
                ),
                "source_conflict": str(
                    bool(presence_rows) and bool(absence_rows)
                ).lower(),
            }
        )
    return output


def _walk_private_keys(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk_private_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_private_keys(item)


def _walk_string_values(value: Any):
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_string_values(item)
    elif isinstance(value, str):
        yield value


def assert_evidence_privacy(
    payloads: Mapping[str, Any], *, forbidden_values: Iterable[str] = ()
) -> None:
    if any(key in FORBIDDEN_EVIDENCE_KEYS for key in _walk_private_keys(payloads)):
        raise CameraNormalizationError("aggregate_evidence_privacy_failure")
    forbidden = {value for value in forbidden_values if value}
    for value in _walk_string_values(payloads):
        if (
            value in forbidden
            or value.startswith("/Users/")
            or re.fullmatch(r"g_-?\d+_-?\d+", value)
            or value.startswith("tascam_")
        ):
            raise CameraNormalizationError("aggregate_evidence_privacy_failure")


def _read_locations(path: Path) -> tuple[dict[str, list[tuple[float, float]]], int]:
    locations: dict[str, list[tuple[float, float]]] = defaultdict(list)
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["site", "lat", "lon"]:
                raise CameraNormalizationError("location_schema_failure")
            rows = 0
            for row in reader:
                rows += 1
                if (
                    set(row) != {"site", "lat", "lon"}
                    or not row["site"].strip()
                    or not row["lat"].strip()
                    or not row["lon"].strip()
                ):
                    raise CameraNormalizationError("location_row_failure")
                try:
                    lon = float(row["lon"])
                    lat = float(row["lat"])
                except ValueError as exc:
                    raise CameraNormalizationError("location_coordinate_invalid") from exc
                locations[row["site"]].append((lon, lat))
    except (OSError, csv.Error) as exc:
        raise CameraNormalizationError("location_csv_invalid") from exc
    return dict(locations), rows


def _process_observations(
    path: Path,
    output_path: Path,
    focal_mapping: Mapping[str, str],
    valid_codes: set[str],
) -> dict[str, Any]:
    stream, writer = _write_header(output_path, OBSERVATION_FIELDS)
    seen_ids: set[str] = set()
    site_rows: Counter[str] = Counter()
    in_window_site_rows: Counter[str] = Counter()
    detections: Counter[tuple[str, str]] = Counter()
    dispositions: Counter[str] = Counter()
    survey_ids: set[str] = set()
    observation_sites: set[str] = set()
    raw_hash = sha256(path)
    rows = 0
    try:
        with path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames != [
                "index",
                "survey",
                "site",
                "datetime",
                "flash",
                "count",
                "species",
                "filename",
                "imageid",
            ]:
                raise CameraNormalizationError("observation_schema_failure")
            for ordinal, row in enumerate(reader, 1):
                rows += 1
                if None in row or any(not str(row[field]).strip() for field in reader.fieldnames):
                    raise CameraNormalizationError("observation_row_missing_value")
                raw_id = row["index"]
                if raw_id in seen_ids:
                    raise CameraNormalizationError("observation_identity_duplicate")
                seen_ids.add(raw_id)
                _positive_count(row["count"])
                year = _observation_year(row["datetime"])
                code = row["species"]
                if code not in valid_codes:
                    raise CameraNormalizationError("observation_lookup_failure")
                site = row["site"]
                observation_sites.add(site)
                site_rows[site] += 1
                survey_ids.add(row["survey"])
                focal_species = focal_mapping.get(code, "")
                if 2001 <= year <= 2025:
                    in_window_site_rows[site] += 1
                    if focal_species:
                        state = "accepted_focal_presence"
                        detections[(site, focal_species)] += 1
                    else:
                        state = "accepted_operational_witness"
                    reason = ""
                else:
                    state = "excluded"
                    reason = "outside_primary_window"
                dispositions[state] += 1
                writer.writerow(
                    {
                        "observation_row_id": _observation_row_id(raw_hash, ordinal),
                        "source_row_ordinal": ordinal,
                        "raw_observation_id": raw_id,
                        "survey_id": row["survey"],
                        "site_id": site,
                        "observed_datetime": row["datetime"],
                        "flash": row["flash"],
                        "count": row["count"],
                        "source_code": code,
                        "source_filename": row["filename"],
                        "image_id": row["imageid"],
                        "focal_species_id": focal_species,
                        "observation_state": state,
                        "reason_code": reason,
                    }
                )
    except (OSError, csv.Error) as exc:
        raise CameraNormalizationError("observation_csv_invalid") from exc
    finally:
        stream.close()
    return {
        "rows": rows,
        "unique_ids": len(seen_ids),
        "site_rows": site_rows,
        "in_window_site_rows": in_window_site_rows,
        "detections": detections,
        "dispositions": dispositions,
        "survey_count": len(survey_ids),
        "observation_sites": observation_sites,
    }


def _output_metadata(output_dir: Path, counts: Mapping[str, int]) -> dict[str, Any]:
    return {
        role: {
            "rows": counts[role],
            "bytes": (output_dir / f"{role}.csv").stat().st_size,
            "sha256": sha256(output_dir / f"{role}.csv"),
            "schema_sha256": _schema_sha256(OUTPUT_SCHEMAS[role]),
        }
        for role in OUTPUT_SCHEMAS
    }


def _build_evidence_payloads(
    plan: Mapping[str, Any],
    tracked_paths: Mapping[str, Path],
    private_manifest_sha: str,
    source_metrics: Mapping[str, Any],
    lookup_metrics: Mapping[str, Any],
    location_rows: int,
    locations: Mapping[str, list[tuple[float, float]]],
    site_dispositions: Mapping[str, int],
    site_exclusion_reasons: Mapping[str, int],
    observation_island_sites: Mapping[str, int],
    eligible_island_sites: Mapping[str, int],
    eligible_sites: Mapping[str, Mapping[str, Any]],
    site_species_rows: list[dict[str, Any]],
    grid_rows: list[dict[str, Any]],
    output_dir: Path,
    output_counts: Mapping[str, int],
) -> dict[str, dict[str, Any]]:
    classifications = Counter(row["classification"] for row in site_species_rows)
    grid_classes = Counter(row["pa_type"] for row in grid_rows)
    per_species: dict[str, dict[str, int]] = {}
    for species_id in ACTIVE_SPECIES:
        site_subset = [
            row for row in site_species_rows if row["species_id"] == species_id
        ]
        grid_subset = [row for row in grid_rows if row["species_id"] == species_id]
        per_species[species_id] = {
            "detection_sites": sum(
                row["classification"] == "presence" for row in site_subset
            ),
            "presence_site_species_rows": sum(
                row["classification"] == "presence" for row in site_subset
            ),
            "survey_supported_absence_rows": sum(
                row["classification"] == "survey_supported_absence"
                for row in site_subset
            ),
            "island_absence_suppressions": sum(
                row["classification"] == "species_island_absence_exclusion"
                for row in site_subset
            ),
            "presence_grid_rows": sum(
                row["pa_type"] == "presence" for row in grid_subset
            ),
            "survey_supported_absence_grid_rows": sum(
                row["pa_type"] == "survey_supported_absence"
                for row in grid_subset
            ),
        }
    repeated_sites = sum(len(rows) > 1 for rows in locations.values())
    repeated_location_rows = sum(
        len(rows) for rows in locations.values() if len(rows) > 1
    )
    if set(site_dispositions) - set(SITE_DISPOSITION_KEYS):
        raise CameraNormalizationError("site_disposition_contract_failure")
    if set(site_exclusion_reasons) - set(SITE_EXCLUSION_REASON_KEYS):
        raise CameraNormalizationError("site_exclusion_reason_contract_failure")
    disposition_counts = {
        key: int(site_dispositions.get(key, 0)) for key in SITE_DISPOSITION_KEYS
    }
    exclusion_reason_counts = {
        key: int(site_exclusion_reasons.get(key, 0))
        for key in SITE_EXCLUSION_REASON_KEYS
    }
    private_roles = {
        role: dict(sorted(metadata.items()))
        for role, metadata in sorted(plan["private_inputs"]["roles"].items())
    }
    payloads = {
        "source_inventory.json": {
            "goal_id": GOAL_ID,
            "private_source_manifest_sha256": private_manifest_sha,
            "private_input_roles": private_roles,
            "frozen_bindings": {
                role: sha256(path)
                for role, path in sorted(tracked_paths.items())
            },
            "species_count": len(ACTIVE_SPECIES),
            "excluded_downstream_species": "macropus_giganteus",
        },
        "normalization_summary.json": {
            "observation_rows": source_metrics["rows"],
            "observation_rows_reconciled": sum(
                source_metrics["dispositions"].values()
            ),
            "unique_observation_id_count": source_metrics["unique_ids"],
            "observation_dispositions": {
                key: int(source_metrics["dispositions"].get(key, 0))
                for key in OBSERVATION_DISPOSITION_KEYS
            },
            "distinct_survey_count": source_metrics["survey_count"],
            "species_lookup_rows": lookup_metrics["rows"],
            "species_lookup_distinct_codes": lookup_metrics["distinct_codes"],
            "species_lookup_ambiguous_nonfocal_codes": len(
                lookup_metrics["ambiguous_codes"]
            ),
            "location_rows": location_rows,
            "location_sites": len(locations),
            "observation_bearing_sites": len(source_metrics["observation_sites"]),
            "eligible_sites": len(eligible_sites),
            "site_dispositions": disposition_counts,
            "site_species_rows_before_suppression": len(site_species_rows),
            "expected_site_species_rows": len(eligible_sites)
            * len(ACTIVE_SPECIES),
            "species_island_absence_suppressions": classifications[
                "species_island_absence_exclusion"
            ],
            "retained_site_species_rows": classifications["presence"]
            + classifications["survey_supported_absence"],
            "classification_counts": {
                key: classifications[key]
                for key in (
                    "presence",
                    "survey_supported_absence",
                    "species_island_absence_exclusion",
                )
            },
            "grid_classification_counts": {
                "presence": grid_classes["presence"],
                "survey_supported_absence": grid_classes[
                    "survey_supported_absence"
                ],
            },
            "grid_evidence_rows": len(grid_rows),
            "by_species": per_species,
            "privacy": {"aggregate_only": True},
        },
        "spatial_summary.json": {
            "canonical_grid_rows": len(_read_grid(tracked_paths["grid"])),
            "location_rows": location_rows,
            "location_sites": len(locations),
            "repeated_coordinate_sites": repeated_sites,
            "repeated_coordinate_rows": repeated_location_rows,
            "site_dispositions": disposition_counts,
            "site_exclusion_reason_counts": exclusion_reason_counts,
            "eligible_sites": len(eligible_sites),
            "observation_bearing_island_site_counts": {
                code: observation_island_sites.get(code, 0)
                for code in (*ISLAND_CODES, "outside")
            },
            "eligible_island_site_counts": {
                code: eligible_island_sites.get(code, 0)
                for code in (*ISLAND_CODES, "outside")
            },
            "max_centroid_distance_m": max(
                (
                    float(site["centroid_distance_max_m"])
                    for site in eligible_sites.values()
                ),
                default=0.0,
            ),
            "ambiguous_site_locations": site_dispositions.get(
                "ambiguous_site_location", 0
            ),
            "matrix_conflicting_presences": 0,
        },
        "outputs.json": {
            "private_output_roles": _output_metadata(output_dir, output_counts),
            "private_outputs_ignored": True,
        },
        "review.json": {
            "readiness": "goal019_camera_spatial_normalization_complete",
            "private_raw_replay_required": True,
            "matrix_conflicting_presences": 0,
            "privacy": REVIEW_PRIVACY,
            "classification": {
                "presence_first_class": True,
                "survey_supported_absence_first_class": True,
                "presence_dominates_within_camera_source": True,
                "absence_rule_id": "P1-D009",
            },
            "stopped_before": [
                "ala_camera_combination",
                "pseudoabsence",
                "predictors",
                "folds",
                "mapping",
                "modelling",
            ],
        },
    }
    assert_evidence_privacy(payloads)
    return payloads


def _recompute(
    plan: Mapping[str, Any],
    tracked_paths: Mapping[str, Path],
    private_paths: Mapping[str, Path],
    private_manifest_sha: str,
    output_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    output_dir.mkdir(parents=True, exist_ok=False)
    focal_mapping, _crosswalk = _load_crosswalk(private_paths["focal_crosswalk"])
    lookup = _load_lookup(private_paths["species_lookup"], set(focal_mapping))
    observations = _process_observations(
        private_paths["observations"],
        output_dir / "observation_audit.csv",
        focal_mapping,
        lookup["all_codes"],
    )
    locations, location_rows = _read_locations(private_paths["site_locations"])
    if not observations["observation_sites"].issubset(locations):
        raise CameraNormalizationError("observation_site_without_location")

    grid = _read_grid(tracked_paths["grid"])
    if len(grid) != plan["spatial_contract"]["grid_rows"]:
        raise CameraNormalizationError("canonical_grid_row_count_drift")
    coast = _shapefile_polygons(tracked_paths["coast_shp"])
    islands = _load_islands(tracked_paths["offshore_islands"])

    eligible_sites: dict[str, dict[str, Any]] = {}
    site_dispositions: Counter[str] = Counter()
    site_exclusion_reasons: Counter[str] = Counter()
    observation_island_sites: Counter[str] = Counter()
    eligible_island_sites: Counter[str] = Counter()
    site_audit: list[dict[str, Any]] = []
    for site_id in sorted(locations):
        coordinates = locations[site_id]
        spatial = classify_location_rows(coordinates, grid, coast, islands)
        if (
            site_id in observations["observation_sites"]
            and "island_code" in spatial
        ):
            observation_island_sites[spatial["island_code"] or "outside"] += 1
        state, reason = site_disposition(
            spatial,
            has_observations=site_id in observations["observation_sites"],
            in_window_rows=observations["in_window_site_rows"].get(site_id, 0),
        )
        if state == "eligible":
            eligible_sites[site_id] = dict(spatial)
            eligible_island_sites[spatial["island_code"] or "outside"] += 1
        else:
            site_exclusion_reasons[reason] += 1
        site_dispositions[state] += 1
        site_audit.append(
            {
                "site_id": site_id,
                "coordinate_row_count": len(coordinates),
                "raw_coordinate_pairs": json.dumps(
                    coordinates, separators=(",", ":")
                ),
                "grid_cell_id": spatial.get("grid_cell_id", ""),
                "centroid_lon": spatial.get("centroid_lon", ""),
                "centroid_lat": spatial.get("centroid_lat", ""),
                "island_code": spatial.get("island_code", ""),
                "centroid_distance_max_m": spatial.get(
                    "centroid_distance_max_m", ""
                ),
                "observation_row_count": observations["site_rows"].get(site_id, 0),
                "in_window_observation_row_count": observations[
                    "in_window_site_rows"
                ].get(site_id, 0),
                "site_state": state,
                "reason_code": reason,
            }
        )
    site_count = _write_rows(output_dir / "site_audit.csv", SITE_FIELDS, site_audit)

    try:
        decision_bundle = json.loads(
            tracked_paths["decision_bundle"].read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise CameraNormalizationError("decision_bundle_invalid") from exc
    island_matrix = decision_bundle["policies"]["island_exclusions"][
        "species_exclusions"
    ]
    site_species, blockers = build_site_species_rows(
        eligible_sites,
        observations["detections"],
        ACTIVE_SPECIES,
        island_matrix,
    )
    if blockers:
        raise CameraNormalizationError("matrix_conflicting_focal_presence")
    site_species_count = _write_rows(
        output_dir / "site_species.csv", SITE_SPECIES_FIELDS, site_species
    )
    grid_rows = collapse_grid_evidence(site_species)
    if any(row["species_id"] == "macropus_giganteus" for row in grid_rows):
        raise CameraNormalizationError("excluded_species_output_failure")
    if any(row["grid_cell_id"] not in grid for row in grid_rows):
        raise CameraNormalizationError("noncanonical_grid_output")
    grid_count = _write_rows(
        output_dir / "grid_evidence.csv", GRID_FIELDS, grid_rows
    )
    output_counts = {
        "observation_audit": observations["rows"],
        "site_audit": site_count,
        "site_species": site_species_count,
        "grid_evidence": grid_count,
    }
    payloads = _build_evidence_payloads(
        plan,
        tracked_paths,
        private_manifest_sha,
        observations,
        lookup,
        location_rows,
        locations,
        site_dispositions,
        site_exclusion_reasons,
        observation_island_sites,
        eligible_island_sites,
        eligible_sites,
        site_species,
        grid_rows,
        output_dir,
        output_counts,
    )
    return payloads, output_counts


def _write_evidence_bundle(
    evidence_dir: Path, payloads: Mapping[str, Mapping[str, Any]]
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=False)
    for name in EVIDENCE_PAYLOAD_FILES:
        (evidence_dir / name).write_text(
            json.dumps(payloads[name], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
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
        + "\n",
        encoding="utf-8",
    )


def _read_evidence_bundle(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    evidence_dir = Path(evidence_dir)
    _validate_exact_directory_files(
        evidence_dir,
        EVIDENCE_FILES,
        directory_error="evidence_directory_invalid",
        footprint_error="evidence_footprint_drift",
    )
    try:
        manifest = json.loads(
            (evidence_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise CameraNormalizationError("evidence_manifest_invalid") from exc
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != {"schema_version", "files"}
        or manifest.get("schema_version") != "1.0"
        or not isinstance(manifest.get("files"), list)
        or [entry.get("path") for entry in manifest["files"]]
        != list(EVIDENCE_PAYLOAD_FILES)
    ):
        raise CameraNormalizationError("evidence_manifest_invalid")
    for entry in manifest["files"]:
        if (
            not isinstance(entry, Mapping)
            or set(entry) != {"path", "bytes", "sha256"}
            or not _is_int(entry.get("bytes"))
            or entry["bytes"] < 0
            or not isinstance(entry.get("sha256"), str)
            or SHA256_RE.fullmatch(entry["sha256"]) is None
        ):
            raise CameraNormalizationError("evidence_manifest_invalid")
        path = evidence_dir / entry["path"]
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != entry["bytes"]
            or sha256(path) != entry["sha256"]
        ):
            raise CameraNormalizationError("evidence_manifest_tamper")
    payloads: dict[str, dict[str, Any]] = {}
    for name in EVIDENCE_PAYLOAD_FILES:
        try:
            value = json.loads((evidence_dir / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CameraNormalizationError("evidence_payload_invalid") from exc
        if not isinstance(value, dict):
            raise CameraNormalizationError("evidence_payload_invalid")
        payloads[name] = value
    assert_evidence_privacy(payloads)
    return payloads


def _is_nonnegative_int_map(value: Any, keys: Iterable[str]) -> bool:
    expected = set(keys)
    return (
        isinstance(value, Mapping)
        and set(value) == expected
        and all(_is_int(value[key]) and value[key] >= 0 for key in expected)
    )


def _validate_tracked_payloads(
    plan: Mapping[str, Any], payloads: Mapping[str, dict[str, Any]]
) -> None:
    source = payloads["source_inventory.json"]
    if set(source) != SOURCE_INVENTORY_KEYS:
        raise CameraNormalizationError("source_inventory_schema_failure")
    if (
        source["goal_id"] != GOAL_ID
        or source["species_count"] != len(ACTIVE_SPECIES)
        or source["excluded_downstream_species"] != "macropus_giganteus"
        or source["private_input_roles"]
        != {
            role: dict(sorted(metadata.items()))
            for role, metadata in sorted(EXPECTED_PRIVATE.items())
        }
        or source["frozen_bindings"] != EXPECTED_BINDING_HASHES
        or not isinstance(source["private_source_manifest_sha256"], str)
        or SHA256_RE.fullmatch(source["private_source_manifest_sha256"]) is None
    ):
        raise CameraNormalizationError("source_inventory_semantic_failure")

    summary = payloads["normalization_summary.json"]
    if set(summary) != NORMALIZATION_SUMMARY_KEYS:
        raise CameraNormalizationError("normalization_summary_schema_failure")
    required_counts = {
        "observation_rows",
        "observation_rows_reconciled",
        "unique_observation_id_count",
        "distinct_survey_count",
        "species_lookup_rows",
        "species_lookup_distinct_codes",
        "species_lookup_ambiguous_nonfocal_codes",
        "location_rows",
        "location_sites",
        "observation_bearing_sites",
        "eligible_sites",
        "site_species_rows_before_suppression",
        "expected_site_species_rows",
        "species_island_absence_suppressions",
        "retained_site_species_rows",
        "grid_evidence_rows",
    }
    by_species = summary["by_species"]
    if (
        not all(_is_int(summary[key]) and summary[key] >= 0 for key in required_counts)
        or not _is_nonnegative_int_map(
            summary["observation_dispositions"], OBSERVATION_DISPOSITION_KEYS
        )
        or not _is_nonnegative_int_map(
            summary["site_dispositions"], SITE_DISPOSITION_KEYS
        )
        or not _is_nonnegative_int_map(
            summary["classification_counts"],
            {
                "presence",
                "survey_supported_absence",
                "species_island_absence_exclusion",
            },
        )
        or not _is_nonnegative_int_map(
            summary["grid_classification_counts"],
            {"presence", "survey_supported_absence"},
        )
        or not isinstance(by_species, Mapping)
        or set(by_species) != set(ACTIVE_SPECIES)
        or any(
            not _is_nonnegative_int_map(metrics, SPECIES_SUMMARY_KEYS)
            for metrics in by_species.values()
        )
        or summary["privacy"] != {"aggregate_only": True}
    ):
        raise CameraNormalizationError("normalization_summary_schema_failure")

    classes = summary["classification_counts"]
    grid_classes = summary["grid_classification_counts"]
    site_states = summary["site_dispositions"]
    species_totals = {
        key: sum(metrics[key] for metrics in by_species.values())
        for key in SPECIES_SUMMARY_KEYS
    }
    if (
        summary["observation_rows"]
        != plan["private_inputs"]["roles"]["observations"]["data_rows"]
        or summary["observation_rows_reconciled"] != summary["observation_rows"]
        or summary["unique_observation_id_count"] != summary["observation_rows"]
        or sum(summary["observation_dispositions"].values())
        != summary["observation_rows"]
        or summary["species_lookup_rows"]
        != plan["private_inputs"]["roles"]["species_lookup"]["data_rows"]
        or summary["species_lookup_distinct_codes"]
        > summary["species_lookup_rows"]
        or summary["species_lookup_ambiguous_nonfocal_codes"]
        > summary["species_lookup_distinct_codes"]
        or summary["location_rows"]
        != plan["private_inputs"]["roles"]["site_locations"]["data_rows"]
        or sum(site_states.values()) != summary["location_sites"]
        or site_states["eligible"] != summary["eligible_sites"]
        or summary["observation_bearing_sites"]
        + site_states["unreferenced_site"]
        != summary["location_sites"]
        or summary["site_species_rows_before_suppression"]
        != summary["expected_site_species_rows"]
        or summary["expected_site_species_rows"]
        != summary["eligible_sites"] * len(ACTIVE_SPECIES)
        or summary["retained_site_species_rows"]
        + summary["species_island_absence_suppressions"]
        != summary["site_species_rows_before_suppression"]
        or sum(classes.values()) != summary["site_species_rows_before_suppression"]
        or classes["species_island_absence_exclusion"]
        != summary["species_island_absence_suppressions"]
        or classes["presence"] + classes["survey_supported_absence"]
        != summary["retained_site_species_rows"]
        or sum(grid_classes.values()) != summary["grid_evidence_rows"]
        or species_totals["detection_sites"]
        != species_totals["presence_site_species_rows"]
        or species_totals["presence_site_species_rows"] != classes["presence"]
        or species_totals["survey_supported_absence_rows"]
        != classes["survey_supported_absence"]
        or species_totals["island_absence_suppressions"]
        != classes["species_island_absence_exclusion"]
        or species_totals["presence_grid_rows"] != grid_classes["presence"]
        or species_totals["survey_supported_absence_grid_rows"]
        != grid_classes["survey_supported_absence"]
    ):
        raise CameraNormalizationError("normalization_summary_semantic_failure")

    spatial = payloads["spatial_summary.json"]
    island_keys = {*ISLAND_CODES, "outside"}
    if (
        set(spatial) != SPATIAL_SUMMARY_KEYS
        or not _is_nonnegative_int_map(
            spatial["site_dispositions"], SITE_DISPOSITION_KEYS
        )
        or not _is_nonnegative_int_map(
            spatial["site_exclusion_reason_counts"],
            SITE_EXCLUSION_REASON_KEYS,
        )
        or not _is_nonnegative_int_map(
            spatial["observation_bearing_island_site_counts"], island_keys
        )
        or not _is_nonnegative_int_map(
            spatial["eligible_island_site_counts"], island_keys
        )
        or any(
            not _is_int(spatial[key]) or spatial[key] < 0
            for key in (
                "canonical_grid_rows",
                "location_rows",
                "location_sites",
                "repeated_coordinate_sites",
                "repeated_coordinate_rows",
                "eligible_sites",
                "ambiguous_site_locations",
                "matrix_conflicting_presences",
            )
        )
        or isinstance(spatial["max_centroid_distance_m"], bool)
        or not isinstance(spatial["max_centroid_distance_m"], (int, float))
        or not math.isfinite(spatial["max_centroid_distance_m"])
        or spatial["max_centroid_distance_m"] < 0
    ):
        raise CameraNormalizationError("spatial_summary_schema_failure")
    reasons = spatial["site_exclusion_reason_counts"]
    if (
        spatial["canonical_grid_rows"] != 74073
        or spatial["location_rows"] != summary["location_rows"]
        or spatial["location_sites"] != summary["location_sites"]
        or spatial["site_dispositions"] != site_states
        or spatial["eligible_sites"] != summary["eligible_sites"]
        or spatial["ambiguous_site_locations"] != 0
        or spatial["matrix_conflicting_presences"] != 0
        or sum(spatial["observation_bearing_island_site_counts"].values())
        != summary["observation_bearing_sites"]
        or sum(spatial["eligible_island_site_counts"].values())
        != summary["eligible_sites"]
        or sum(reasons.values())
        != summary["location_sites"] - summary["eligible_sites"]
        or reasons["outside_land_boundary"] + reasons["ineligible_grid_cell"]
        != site_states["invalid_site_location"]
        or reasons["unreferenced_site"] != site_states["unreferenced_site"]
    ):
        raise CameraNormalizationError("spatial_summary_semantic_failure")

    outputs = payloads["outputs.json"]
    if set(outputs) != OUTPUTS_PAYLOAD_KEYS:
        raise CameraNormalizationError("outputs_schema_failure")
    roles = outputs["private_output_roles"]
    if (
        outputs["private_outputs_ignored"] is not True
        or not isinstance(roles, Mapping)
        or set(roles) != set(OUTPUT_SCHEMAS)
    ):
        raise CameraNormalizationError("outputs_semantic_failure")
    expected_rows = {
        "observation_audit": summary["observation_rows"],
        "site_audit": summary["location_sites"],
        "site_species": summary["site_species_rows_before_suppression"],
        "grid_evidence": summary["grid_evidence_rows"],
    }
    for role, metadata in roles.items():
        if (
            not isinstance(metadata, Mapping)
            or set(metadata) != {"rows", "bytes", "sha256", "schema_sha256"}
            or metadata.get("rows") != expected_rows[role]
            or not _is_int(metadata.get("bytes"))
            or metadata["bytes"] < 0
            or SHA256_RE.fullmatch(str(metadata.get("sha256", ""))) is None
            or metadata.get("schema_sha256")
            != _schema_sha256(OUTPUT_SCHEMAS[role])
        ):
            raise CameraNormalizationError("outputs_semantic_failure")

    review = payloads["review.json"]
    expected_classification = {
        "presence_first_class": True,
        "survey_supported_absence_first_class": True,
        "presence_dominates_within_camera_source": True,
        "absence_rule_id": "P1-D009",
    }
    expected_stops = [
        "ala_camera_combination",
        "pseudoabsence",
        "predictors",
        "folds",
        "mapping",
        "modelling",
    ]
    if set(review) != REVIEW_PAYLOAD_KEYS:
        raise CameraNormalizationError("review_schema_failure")
    if (
        review["readiness"] != "goal019_camera_spatial_normalization_complete"
        or review["private_raw_replay_required"] is not True
        or review["matrix_conflicting_presences"] != 0
        or review["classification"] != expected_classification
        or review["privacy"] != REVIEW_PRIVACY
        or review["stopped_before"] != expected_stops
    ):
        raise CameraNormalizationError("review_semantic_failure")
    assert_evidence_privacy(payloads)


def _validate_output_replay(output_dir: Path, expected_dir: Path) -> None:
    output_dir = Path(output_dir)
    _validate_exact_directory_files(
        output_dir,
        OUTPUT_FILES,
        directory_error="output_directory_invalid",
        footprint_error="output_footprint_drift",
    )
    for name in OUTPUT_FILES:
        actual = output_dir / name
        expected = expected_dir / name
        if (
            not actual.is_file()
            or actual.is_symlink()
            or actual.read_bytes() != expected.read_bytes()
        ):
            raise CameraNormalizationError("output_semantic_replay_failure")


def validate_evidence(
    plan_path: Path,
    evidence_dir: Path,
    *,
    private_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    plan = _load_plan(Path(plan_path))
    payloads = _read_evidence_bundle(Path(evidence_dir))
    _validate_tracked_payloads(plan, payloads)
    if private_dir is None:
        if output_dir is not None:
            raise CameraNormalizationError("full_validation_inputs_required")
        return {
            "readiness": "goal019_tracked_evidence_valid_private_replay_required",
            "private_raw_replay_required": True,
        }
    if output_dir is None:
        raise CameraNormalizationError("full_validation_inputs_required")
    tracked_paths = _bound_tracked_inputs(Path(plan_path), plan)
    private_paths, _manifest, manifest_sha = _load_private_inputs(plan, private_dir)
    with tempfile.TemporaryDirectory(prefix="goal019-replay-") as directory:
        expected_output = Path(directory) / "output"
        expected_payloads, _counts = _recompute(
            plan,
            tracked_paths,
            private_paths,
            manifest_sha,
            expected_output,
        )
        _validate_output_replay(Path(output_dir), expected_output)
        if payloads != expected_payloads:
            raise CameraNormalizationError(
                "aggregate_evidence_semantic_replay_failure"
            )
    return {
        "readiness": "goal019_camera_spatial_normalization_complete",
        "private_raw_replay_required": False,
    }


def _publish_staged(
    stage_output: Path,
    stage_evidence: Path,
    output_dir: Path,
    evidence_dir: Path,
) -> None:
    try:
        stage_output.rename(output_dir)
    except Exception as exc:
        raise CameraNormalizationError("output_publication_failure") from exc
    try:
        stage_evidence.rename(evidence_dir)
    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise CameraNormalizationError("evidence_publication_failure") from exc


def _git_path_is_ignored(root: Path, path: Path) -> bool:
    root = Path(root).resolve()
    path = Path(path).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    try:
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--no-index",
                "--",
                relative.as_posix(),
            ],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _resolve_run_destinations(
    plan_path: Path,
    plan: Mapping[str, Any],
    output_dir: Path | None,
    evidence_dir: Path | None,
) -> tuple[Path, Path, Path]:
    root = Path(plan_path).resolve().parents[1]
    canonical_output = (root / plan["outputs"]["directory"]).resolve()
    canonical_evidence = (root / plan["evidence"]["directory"]).resolve()
    requested_output = (
        Path(output_dir).resolve() if output_dir is not None else canonical_output
    )
    requested_evidence = (
        Path(evidence_dir).resolve()
        if evidence_dir is not None
        else canonical_evidence
    )
    if (
        requested_output != canonical_output
        or requested_evidence != canonical_evidence
    ):
        raise CameraNormalizationError("publication_destination_not_canonical")
    if not _git_path_is_ignored(root, canonical_output):
        raise CameraNormalizationError("private_output_not_ignored")
    return root, canonical_output, canonical_evidence


def run(
    plan_path: Path,
    *,
    private_dir: Path,
    output_dir: Path | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    plan_path = Path(plan_path)
    plan = _load_plan(plan_path)
    root, output_dir, evidence_dir = _resolve_run_destinations(
        plan_path, plan, output_dir, evidence_dir
    )
    tracked_paths = _bound_tracked_inputs(plan_path, plan)
    private_paths, _manifest, manifest_sha = _load_private_inputs(plan, private_dir)
    if output_dir.exists() or evidence_dir.exists():
        raise CameraNormalizationError("publication_destination_exists")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix="goal019-stage-", dir=output_dir.parent)
    )
    stage_output = stage_root / "output"
    stage_evidence = stage_root / "evidence"
    try:
        payloads, output_counts = _recompute(
            plan,
            tracked_paths,
            private_paths,
            manifest_sha,
            stage_output,
        )
        _write_evidence_bundle(stage_evidence, payloads)
        staged_payloads = _read_evidence_bundle(stage_evidence)
        _validate_tracked_payloads(plan, staged_payloads)
        evidence_dir.parent.mkdir(parents=True, exist_ok=True)
        _publish_staged(stage_output, stage_evidence, output_dir, evidence_dir)
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
    return {
        "readiness": "goal019_camera_spatial_normalization_complete",
        "observation_rows": output_counts["observation_audit"],
        "site_rows": output_counts["site_audit"],
        "site_species_rows": output_counts["site_species"],
        "grid_evidence_rows": output_counts["grid_evidence"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Goal019 offline private camera spatial normalization"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--plan", type=Path, required=True)
    run_parser.add_argument("--private-dir", type=Path, required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("--plan", type=Path, required=True)
    validate_parser.add_argument("--evidence-dir", type=Path, required=True)
    validate_parser.add_argument("--private-dir", type=Path)
    validate_parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run(args.plan, private_dir=args.private_dir)
        else:
            result = validate_evidence(
                args.plan,
                args.evidence_dir,
                private_dir=args.private_dir,
                output_dir=args.output_dir,
            )
    except CameraNormalizationError as exc:
        print(json.dumps({"readiness": "blocked", "reason": str(exc)}))
        return 2
    except Exception:
        print(json.dumps({"readiness": "blocked", "reason": "runtime_failure"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
