"""Exact count-free spatial-domain freeze for Goal 040."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import shapely
from shapely import covers, make_valid, points, union_all


IBRA_LAYER = (
    "https://gis.environment.gov.au/gispubmap/rest/services/ogc_services/"
    "IBRA7_Subregions/FeatureServer/0"
)
IBRA_VERSION = "7.1"
ARCHIVE_SHA256 = "017794c7c093c325e6e5a551ed1ffd7c807ab92534963be6892f239c210b31a7"
EXPECTED_ALLOWLIST_SIZE = 163
EXPECTED_ALLOWLIST_SHA256 = "00e6b954b657e1ad09c10bbf088dacd5ae72b7dfaa1d8d507da5bfc55243f81e"
EXPECTED_ELIGIBLE_CELL_COUNT = 1_125_325
EXPECTED_ELIGIBLE_CELL_ID_SHA256 = "022a83b2762b886f455406a96cb48a91d612e1b08d6d1cad00eb5db7070a2b06"
EXPECTED_STATE_COUNTS = {
    "Australian Capital Territory": 2_332,
    "New South Wales": 460_725,
    "Queensland": 242_636,
    "South Australia": 121_710,
    "Tasmania": 72_293,
    "Victoria": 225_629,
}
GRID_SCALE = 10_000
GRID_STEP = 100
LON_MIN, LON_MAX = 1_353_750, 1_536_250
LAT_MIN, LAT_MAX = -436_275, -237_775
STATE_NAMES = {
    "1": "New South Wales", "2": "Victoria", "3": "Queensland",
    "4": "South Australia", "5": "Western Australia", "6": "Tasmania",
    "7": "Northern Territory", "8": "Australian Capital Territory",
    "9": "Other Territories",
}


class Goal040DomainError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "dSDM-Goal040/2.0"})
    with urlopen(request, timeout=180) as response:
        return response.read()


def _union(frame: gpd.GeoDataFrame, crs: int) -> object:
    return union_all(make_valid(frame.to_crs(crs).geometry.array))


def _ensure_ibra(root: Path) -> tuple[Path, Path]:
    raw = root / "data/raw/goal040/domain"
    raw.mkdir(parents=True, exist_ok=True)
    metadata = raw / "ibra7_1_layer.json"
    features = raw / "ibra7_1_subregions.geojson"
    if not metadata.exists():
        metadata.write_bytes(_download(IBRA_LAYER + "?f=pjson"))
    if not features.exists():
        query = urlencode({
            "where": "1=1", "outFields": "*", "returnGeometry": "true",
            "outSR": "4326", "f": "geojson",
        })
        features.write_bytes(_download(IBRA_LAYER + "/query?" + query))
    return metadata, features


def _reconcile_selector(root: Path, current_path: Path) -> tuple[list[str], dict, object]:
    archive = root / "data/input/spatial_polygons.zip"
    if not archive.exists() or _sha(archive) != ARCHIVE_SHA256:
        raise Goal040DomainError("archived selector is missing or checksum-drifted")
    prefix = f"zip://{archive}!spatial_polygons/"
    study = gpd.read_file(prefix + "study_area/study_area.shp")
    historical = gpd.read_file(prefix + "ibra7_subregions/ibra7_subregions.shp")
    current = gpd.read_file(current_path)
    if len(study) != 1 or len(historical) != 419 or len(current) != 419:
        raise Goal040DomainError("IBRA selector/product feature-count drift")
    if current.geometry.isna().any() or current.geometry.is_empty.any():
        raise Goal040DomainError("authoritative IBRA7.1 query has null or empty geometry")
    invalid_codes = sorted(current.loc[~current.geometry.is_valid, "SUB_CODE_7"].tolist())
    if invalid_codes != ["GAW08", "SEC02"]:
        raise Goal040DomainError("unexpected authoritative IBRA7.1 invalid geometry")
    current.geometry = make_valid(current.geometry.array)
    if not current.geometry.is_valid.all():
        raise Goal040DomainError("IBRA7.1 make-valid repair failed")

    study_3577 = _union(study, 3577)
    historical_3577 = historical.to_crs(3577)
    fractions = np.asarray([
        geometry.intersection(study_3577).area / geometry.area
        for geometry in historical_3577.geometry
    ])
    selected = sorted(historical.loc[fractions >= 0.99, "SUB_CODE_7"].tolist())
    if len(selected) != EXPECTED_ALLOWLIST_SIZE:
        raise Goal040DomainError("archived selector no longer yields 163 whole subregions")
    allowlist_sha = hashlib.sha256(("\n".join(selected) + "\n").encode()).hexdigest()
    if allowlist_sha != EXPECTED_ALLOWLIST_SHA256:
        raise Goal040DomainError("exact sorted IBRA allowlist digest drift")
    partial = historical.loc[(fractions >= 0.001) & (fractions < 0.99)].copy()
    if partial["SUB_CODE_7"].tolist() != ["MDD01"]:
        raise Goal040DomainError("archived selector partial-subregion evidence drift")
    partial_fraction = float(fractions[partial.index[0]])
    partial_area = float(partial.to_crs(3577).geometry.iloc[0].intersection(study_3577).area / 1e6)
    tiny_contacts = int(((fractions > 0) & (fractions < 0.001)).sum())

    current_codes = set(current["SUB_CODE_7"])
    if not set(selected) <= current_codes:
        raise Goal040DomainError("IBRA7.1 lacks an archived selected subregion code")
    current_selected = current.loc[current["SUB_CODE_7"].isin(selected)]
    current_3577 = _union(current_selected, 3577)
    reconciliation = {
        "method": "historical_IBRA7.0_overlap_fraction_ge_0.99_then_same_code_in_IBRA7.1",
        "historical_selector_role": "archaeological_design_evidence_only",
        "historical_archive_sha256": ARCHIVE_SHA256,
        "historical_study_area_km2": round(study_3577.area / 1e6, 6),
        "selected_current_IBRA7_1_area_km2": round(current_3577.area / 1e6, 6),
        "current_vs_archived_symmetric_difference_km2": round(
            current_3577.symmetric_difference(study_3577).area / 1e6, 6
        ),
        "whole_subregion_overlap_threshold": 0.99,
        "selected_subregion_count": len(selected),
        "sorted_allowlist_sha256": allowlist_sha,
        "excluded_partial_subregion": {
            "code": "MDD01", "archived_overlap_fraction": round(partial_fraction, 12),
            "archived_overlap_km2": round(partial_area, 6),
            "rationale": "whole-subregion allowlist cannot preserve the 2.15-percent sliver without widening to all MDD01",
        },
        "excluded_topology_contacts_below_0.001_fraction": tiny_contacts,
        "authoritative_geometry_repairs": {
            "method": "shapely.make_valid",
            "source_invalid_subregion_codes": invalid_codes,
        },
    }
    return selected, reconciliation, _union(current_selected, 4326)


def _load_land_and_water(root: Path) -> tuple[dict[str, object], object]:
    shape = root / "data/raw/goal040/domain/extracted/STE_2026_AUST_GDA2020.shp"
    if not shape.exists():
        raise Goal040DomainError("run the boundary-source freeze before grid enumeration")
    states = gpd.read_file(shape)
    states = states.loc[states["STE_CODE26"].notna()].copy()
    state_geometry = {
        str(row.STE_CODE26): make_valid(row.geometry)
        for row in states.to_crs(4326).itertuples()
    }
    water_files = sorted((root / "data/raw/goal040/domain/waterbody").glob("features_*.geojson"))
    if not water_files:
        raise Goal040DomainError("Geofabric lake/reservoir features are absent")
    water_frames = [gpd.read_file(path) for path in water_files]
    water = gpd.GeoDataFrame(
        pd.concat(water_frames, ignore_index=True), crs=water_frames[0].crs
    )
    types = set(water["ahgfftype"].astype(int))
    if types != {25, 26}:
        raise Goal040DomainError("water mask must contain only reservoirs and lakes")
    return state_geometry, _union(water, 4326)


def _enumerate_grid(
    root: Path, ibra: object, states: dict[str, object], water: object
) -> dict:
    lon_values = np.arange(LON_MIN, LON_MAX + 1, GRID_STEP, dtype=np.int64)
    lat_values = np.arange(LAT_MIN, LAT_MAX + 1, GRID_STEP, dtype=np.int64)
    width, height = len(lon_values), len(lat_values)
    if (width, height) != (1826, 1986):
        raise Goal040DomainError("grid dimensions drift")
    raw_path = root / "data/raw/goal040/domain/eligible_cells.csv"
    digest = hashlib.sha256()
    state_counts: Counter[str] = Counter()
    excluded_jurisdiction_counts: Counter[str] = Counter()
    total = 0
    shapely.prepare(ibra)
    shapely.prepare(water)
    for geometry in states.values():
        shapely.prepare(geometry)
    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["cell_id", "row_south_to_north", "column_west_to_east", "longitude", "latitude", "state_code", "region"])
        for row_start in range(0, height, 20):
            row_stop = min(height, row_start + 20)
            lon_grid = np.tile(lon_values, row_stop - row_start)
            lat_grid = np.repeat(lat_values[row_start:row_stop], width)
            point_array = points(lon_grid / GRID_SCALE, lat_grid / GRID_SCALE)
            candidate = covers(ibra, point_array) & ~covers(water, point_array)
            state_for_point = np.full(len(point_array), "", dtype=object)
            land = np.zeros(len(point_array), dtype=bool)
            allowed_land = np.zeros(len(point_array), dtype=bool)
            for code, geometry in states.items():
                hit = covers(geometry, point_array)
                state_for_point[hit] = code
                land |= hit
                if code not in {"7", "9"}:
                    allowed_land |= hit
            for code in ("7", "9"):
                excluded_jurisdiction_counts[code] += int(
                    np.count_nonzero(candidate & land & (state_for_point == code))
                )
            eligible = np.flatnonzero(candidate & allowed_land)
            for position in eligible:
                row_index = row_start + position // width
                column_index = position % width
                code = str(state_for_point[position])
                if code not in STATE_NAMES:
                    raise Goal040DomainError("eligible centroid lacks a valid state classification")
                cell_id = f"r{row_index:04d}c{column_index:04d}"
                region = "tasmania" if code == "6" else "southeast_mainland"
                writer.writerow([
                    cell_id, row_index, column_index,
                    f"{lon_values[column_index] / GRID_SCALE:.4f}",
                    f"{lat_values[row_index] / GRID_SCALE:.4f}", code, region,
                ])
                digest.update((cell_id + "\n").encode())
                state_counts[code] += 1
                total += 1
    return {
        "eligible_cell_count": total,
        "eligible_cell_id_sha256": digest.hexdigest(),
        "ignored_cell_ledger_sha256": _sha(raw_path),
        "state_counts": {STATE_NAMES[code]: state_counts[code] for code in sorted(state_counts)},
        "region_counts": {
            "southeast_mainland": total - state_counts["6"],
            "tasmania": state_counts["6"],
        },
        "absent_jurisdictions": ["Northern Territory", "Other Territories"],
        "jurisdiction_exclusions_before_final_eligibility": {
            STATE_NAMES[code]: excluded_jurisdiction_counts[code]
            for code in ("7", "9")
        },
    }


def build_domain_freeze(root: Path) -> dict:
    metadata_path, current_path = _ensure_ibra(root)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("name") != "IBRA7 subregions" or "version 7.1" not in metadata.get("description", ""):
        raise Goal040DomainError("authoritative IBRA7.1 identity drift")
    allowlist, reconciliation, selector = _reconcile_selector(root, current_path)
    states, water = _load_land_and_water(root)
    grid = _enumerate_grid(root, selector, states, water)
    return {
        "authority": {
            "product_name": "Interim Biogeographic Regionalisation for Australia subregions",
            "product_version": IBRA_VERSION,
            "publisher": "Australian Government Department of Climate Change, Energy, the Environment and Water",
            "source_url": IBRA_LAYER,
            "source_identity": "DCCEEW gispubmap IBRA7_Subregions FeatureServer layer 0; 419 unique subregion codes; version 7.1",
            "retrieved_at": _now(), "licence": "CC BY 3.0 AU",
            "metadata_sha256": _sha(metadata_path),
            "sha256": _sha(current_path),
            "crs": "source EPSG:4283; authoritative query output EPSG:4326",
        },
        "ibra_subregion_allowlist": allowlist,
        "reconciliation": reconciliation,
        "grid": {
            "crs": "EPSG:4326", "resolution_degree": 0.01,
            "centroid_bounds": {"longitude_min": 135.375, "longitude_max": 153.625, "latitude_min": -43.6275, "latitude_max": -23.7775},
            "dimensions": {"columns": 1826, "rows": 1986},
            "origin": "r0000c0000 is the southwest centroid (135.3750,-43.6275)",
            "index_order": "row-major; rows south-to-north; columns west-to-east; zero-based",
            "eligibility": "IBRA7.1 allowlist covers centroid AND allowed ASGS state land (excluding NT and Other Territories) covers centroid AND no Geofabric type-25/26 polygon covers centroid",
            **grid,
        },
        "software": {
            "geopandas": gpd.__version__, "shapely": shapely.__version__,
            "pyproj": pyproj.__version__, "numpy": np.__version__,
        },
    }


def validate_domain_manifest(domain: dict) -> None:
    if len(domain.get("ibra_subregion_allowlist", [])) != EXPECTED_ALLOWLIST_SIZE:
        raise Goal040DomainError("IBRA allowlist size drift")
    digest = hashlib.sha256(("\n".join(domain["ibra_subregion_allowlist"]) + "\n").encode()).hexdigest()
    if digest != EXPECTED_ALLOWLIST_SHA256:
        raise Goal040DomainError("IBRA allowlist identity drift")
    if domain["reconciliation"]["excluded_partial_subregion"]["code"] != "MDD01":
        raise Goal040DomainError("MDD01 reconciliation evidence drift")
    grid = domain["grid"]
    if grid["eligible_cell_count"] != EXPECTED_ELIGIBLE_CELL_COUNT:
        raise Goal040DomainError("exact eligible-cell count drift")
    if grid["eligible_cell_id_sha256"] != EXPECTED_ELIGIBLE_CELL_ID_SHA256:
        raise Goal040DomainError("ordered eligible-cell identity drift")
    if grid["state_counts"] != EXPECTED_STATE_COUNTS:
        raise Goal040DomainError("eligible-cell state allocation drift")
    if set(grid["state_counts"]) & {"Northern Territory", "Other Territories"}:
        raise Goal040DomainError("forbidden jurisdiction in domain receipt")
