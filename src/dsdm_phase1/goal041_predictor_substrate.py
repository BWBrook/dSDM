"""Goal 041 portable predictor substrate.

The implementation has one production path: eligible cells are grouped into
50-cell (0.5 degree) blocks, each source is read once per block, and output is
written as resumable latitude-band Parquet chunks.  Raw and cell-level replay
artefacts remain ignored; tracked manifests contain aggregate provenance only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import resource
import sys
import shutil
import statistics
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

from .goal040_domain import validate_domain_manifest

try:
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import rowcol
    from rasterio.warp import transform as warp_transform, transform_bounds
except ImportError:  # pragma: no cover
    rasterio = None
    MemoryFile = None
    rowcol = transform_bounds = warp_transform = None

CONFIG_PATH = Path("config/goal041_predictor_substrate.json")
DOMAIN_PATH = Path("metadata/goal040_domain_boundary_manifest.json")
CELL_PATH = Path("data/raw/goal040/domain/eligible_cells.csv")
RAW_ROOT = Path("data/raw/goal041")
METADATA_ROOT = Path("metadata")
TABLE_NAME = "predictor_substrate.parquet"
REGIONS = ("southeast_mainland", "tasmania")
CONTINUOUS = [f"bio{i:02d}" for i in range(1, 20)] + ["elevation_mean", "elevation_sd"]
CATEGORICAL = ["nvis_mvg", "soil_order", "alum_secondary"]
SOIL_LABELS = {"1":"Vertosol","2":"Sodosol","3":"Dermosol","4":"Chromosol","5":"Ferrosol","6":"Kurosol","7":"Tenosol","8":"Kandosol","9":"Hydrosol","10":"Podosol","11":"Rudosol","12":"Calcarasol","13":"Organosol","14":"Anthroposol"}
NVIS_MVG_LABELS = {
    "1": "Rainforests and Vine Thickets",
    "2": "Eucalypt Tall Open Forests",
    "3": "Eucalypt Open Forests",
    "4": "Eucalypt Low Open Forests",
    "5": "Eucalypt Woodlands",
    "6": "Acacia Forests and Woodlands",
    "7": "Callitris Forests and Woodlands",
    "8": "Casuarina Forests and Woodlands",
    "9": "Melaleuca Forests and Woodlands",
    "10": "Other Forests and Woodlands",
    "11": "Eucalypt Open Woodlands",
    "12": "Tropical Eucalypt Woodlands/Grasslands",
    "13": "Acacia Open Woodlands",
    "14": "Mallee Woodlands and Shrublands",
    "15": "Low Closed Forests and Tall Closed Shrublands",
    "16": "Acacia Shrublands",
    "17": "Other Shrublands",
    "18": "Heathlands",
    "19": "Tussock Grasslands",
    "20": "Hummock Grasslands",
    "21": "Other Grasslands, Herblands, Sedgelands and Rushlands",
    "22": "Chenopod Shrublands, Samphire Shrublands and Forblands",
    "23": "Mangroves",
    "24": "Inland aquatic - freshwater, salt lakes, lagoons",
    "25": "Cleared, non-native vegetation, buildings",
    "26": "Unclassified native vegetation",
    "27": "Naturally bare - sand, rock, claypan, mudflat",
    "28": "Sea and estuaries",
    "29": "Regrowth, modified native vegetation",
    "31": "Other Open Woodlands",
    "32": "Mallee Open Woodlands and Sparse Mallee Shrublands",
    "99": "Unknown/no data",
}
PREDICTORS = CONTINUOUS + CATEGORICAL
OUTPUT_FIELDS = ["cell_id", "region", *PREDICTORS]
CELL_FIELDS = ["cell_id", "row_south_to_north", "column_west_to_east", "longitude", "latitude", "state_code", "region"]
SCHEMA_VERSION = "goal041-predictor-substrate-v1"
GRID_ORIGIN_LON, GRID_ORIGIN_LAT, CELL_DEGREE = 135.3700, -43.6325, 0.01
BLOCK_CELLS, BAND_ROWS, EXPECTED_CELLS = 50, 50, 1_125_325
SHA256_RE = set("0123456789abcdef")


class Goal041Error(ValueError):
    pass


class SourceMissing(Goal041Error):
    pass


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise Goal041Error(reason)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()


def immutable_source_provenance(root: Path) -> dict[str, Any]:
    """Return source facts that should identify a run on every host."""
    source = json.loads((root / METADATA_ROOT / "goal041_source_manifest.json").read_text())
    return {
        name: {
            key: value
            for key, value in item.items()
            if key not in {"retrieved_at", "probe", "platform"}
        }
        for name, item in source.get("sources", {}).items()
    }


def run_identity(root: Path) -> str:
    """Stable immutable identity; excludes retrieval timestamps/platform."""
    payload = {
        "config_sha256": sha256(root / CONFIG_PATH),
        "code_sha256": sha256(Path(__file__)),
        "uv_lock_sha256": sha256(root / "uv.lock"),
        "cell_ledger_sha256": sha256(root / CELL_PATH),
        "domain_manifest_sha256": sha256(root / DOMAIN_PATH),
        "sources": immutable_source_provenance(root),
    }
    return _digest(payload)


def runtime_environment() -> dict[str, str]:
    import pyarrow
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "rasterio": getattr(rasterio, "__version__", "unavailable"),
        "gdal": getattr(rasterio, "__gdal_version__", "unavailable"),
        "pyarrow": pyarrow.__version__,
    }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _config(root: Path) -> dict[str, Any]:
    value = json.loads((root / CONFIG_PATH).read_text(encoding="utf-8"))
    _require(value.get("schema_version") == SCHEMA_VERSION, "goal041_config_schema_drift")
    _require(value.get("predictors", {}).get("continuous") == CONTINUOUS, "goal041_predictor_order_drift")
    _require(value.get("predictors", {}).get("categorical") == CATEGORICAL, "goal041_predictor_order_drift")
    _require(value.get("tolerances") == {"worldclim": "float32_one_ulp_plus_serialization", "elevation": 0.001, "categorical": "exact"}, "goal041_tolerance_drift")
    return value


def _cells(root: Path) -> list[dict[str, str]]:
    domain = json.loads((root / DOMAIN_PATH).read_text(encoding="utf-8"))
    validate_domain_manifest(domain["exact_study_domain"])
    path = root / CELL_PATH
    _require(path.is_file() and sha256(path) == domain["exact_study_domain"]["grid"]["ignored_cell_ledger_sha256"], "goal041_cell_ledger_authority_drift")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _require(reader.fieldnames == CELL_FIELDS, "goal041_cell_ledger_schema_drift")
        rows = list(reader)
    _require(len(rows) == EXPECTED_CELLS, "goal041_cell_count_drift")
    _require([r["cell_id"] for r in rows] == sorted(r["cell_id"] for r in rows), "goal041_cell_order_drift")
    _require(all(r["region"] in REGIONS for r in rows), "goal041_region_drift")
    return rows


def cell_bounds(cell: Mapping[str, Any]) -> tuple[float, float, float, float]:
    lon, lat = float(cell["longitude"]), float(cell["latitude"])
    return lon - CELL_DEGREE / 2, lat - CELL_DEGREE / 2, lon + CELL_DEGREE / 2, lat + CELL_DEGREE / 2


def ledger_indices(cell: Mapping[str, Any]) -> tuple[int, int]:
    return int(cell["row_south_to_north"]), int(cell["column_west_to_east"])


def production_block_key(cell: Mapping[str, Any], block_cells: int = BLOCK_CELLS) -> tuple[int, int]:
    row, col = ledger_indices(cell)
    return row // block_cells, col // block_cells


def production_block_bounds(key: tuple[int, int], block_cells: int = BLOCK_CELLS) -> tuple[float, float, float, float]:
    row, col = key
    west = GRID_ORIGIN_LON + col * block_cells * CELL_DEGREE
    south = GRID_ORIGIN_LAT + row * block_cells * CELL_DEGREE
    return west, south, west + block_cells * CELL_DEGREE, south + block_cells * CELL_DEGREE


def block_cell_offset(cell: Mapping[str, Any], block: tuple[int, int], block_cells: int = BLOCK_CELLS) -> tuple[int, int]:
    r, c = ledger_indices(cell)
    return r - block[0] * block_cells, c - block[1] * block_cells


def _snap_grid_coordinate(value: float) -> float:
    nearest = round(value)
    return float(nearest) if abs(value - nearest) <= 1e-9 else value


def _snap_grid_coordinates(values: np.ndarray) -> np.ndarray:
    nearest = np.rint(values)
    return np.where(np.abs(values - nearest) <= 1e-9, nearest, values)


def mode_low_code(values: Iterable[Any]) -> Any:
    """Return modal value, resolving ties by numeric code (then text)."""
    clean = []
    for value in values:
        if np.ma.is_masked(value) or value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in {"nodata", "nan", "none"}:
                continue
        try:
            if not isinstance(value, str) and not math.isfinite(float(value)):
                continue
            if not isinstance(value, str) and float(value) == 0:
                continue
        except (TypeError, ValueError):
            continue
        clean.append(value.item() if hasattr(value, "item") else value)
    if not clean:
        raise SourceMissing("cell_all_nodata")
    counts = Counter(clean)
    def key(value: Any) -> tuple[int, Any]:
        try:
            return 0, float(str(value).split(":", 1)[0])
        except (TypeError, ValueError):
            return 1, str(value)
    return min(counts, key=lambda value: (-counts[value], key(value)))


def _valid_values(values: Any, nodata: Any = None) -> np.ndarray:
    arr = np.ma.asarray(values)
    out = np.asarray(arr.compressed() if np.ma.isMaskedArray(arr) else arr).reshape(-1)
    if nodata is not None:
        out = out[out != nodata]
    if np.issubdtype(out.dtype, np.number):
        out = out[np.isfinite(out)]
    return out


def continuous_summary(values: Iterable[Any]) -> tuple[float | None, float | None]:
    if isinstance(values, np.ma.MaskedArray):
        out = _valid_values(values.astype(float))
    else:
        out = _valid_values(np.asarray(list(values), dtype=float))
    if not len(out):
        raise SourceMissing("cell_all_nodata")
    return float(np.mean(out)), float(np.std(out, ddof=1)) if len(out) > 1 else 0.0


def _cell_pixels(dataset: Any, cell: Mapping[str, Any]) -> np.ndarray:
    _require(rasterio is not None, "rasterio_unavailable")
    west, south, east, north = cell_bounds(cell)
    geo_bounds = (west, south, east, north)
    if dataset.crs and str(dataset.crs) != "EPSG:4326":
        west, south, east, north = transform_bounds("EPSG:4326", dataset.crs, west, south, east, north, densify_pts=8)
    window = dataset.window(west, south, east, north)
    # Expand before clipping so boundary-centre pixels cannot be lost to
    # floating-point alignment or a raster whose grid is offset from ours.
    roff = math.floor(float(window.row_off)) - 1; coff = math.floor(float(window.col_off)) - 1
    rstop = math.ceil(float(window.row_off + window.height)) + 1; cstop = math.ceil(float(window.col_off + window.width)) + 1
    # Requests at a source edge legitimately extend outside the raster.  Clip
    # the read window while retaining the original geographic half-open test.
    roff = max(0, roff); coff = max(0, coff); rstop = min(dataset.height, rstop); cstop = min(dataset.width, cstop)
    window = rasterio.windows.Window(coff, roff, max(0, cstop - coff), max(0, rstop - roff))
    arr = dataset.read(1, window=window, masked=True)
    values = []
    for rr, cc in np.ndindex(arr.shape):
        x, y = dataset.xy(int(window.row_off) + rr, int(window.col_off) + cc, offset="center")
        if dataset.crs and str(dataset.crs) != "EPSG:4326":
            x, y = warp_transform(dataset.crs, "EPSG:4326", [x], [y])
            x, y = x[0], y[0]
        if geo_bounds[0] <= x < geo_bounds[2] and geo_bounds[1] <= y < geo_bounds[3] and not np.ma.is_masked(arr[rr, cc]):
            values.append(arr[rr, cc].item() if hasattr(arr[rr, cc], "item") else arr[rr, cc])
    return np.asarray(values)


def summarize_raster_cell(dataset: Any, cell: Mapping[str, Any], kind: str) -> Any:
    values = _cell_pixels(dataset, cell)
    if kind == "continuous":
        return continuous_summary(values)
    if kind == "categorical":
        return mode_low_code(values)
    raise Goal041Error("unknown_raster_summary_kind")


def centroid_value(dataset: Any, cell: Mapping[str, Any], *, epsilon: float = 1e-10) -> Any:
    x, y = float(cell["longitude"]) + epsilon, float(cell["latitude"])
    if dataset.crs and str(dataset.crs) != "EPSG:4326":
        x, y = warp_transform("EPSG:4326", dataset.crs, [x], [y]); x, y = x[0], y[0]
    value = next(dataset.sample([(x, y)]))[0]
    out = _valid_values(np.asarray([value]), dataset.nodata)
    if not len(out):
        raise SourceMissing("centroid_nodata")
    return out[0].item() if hasattr(out[0], "item") else out[0]


def soil_centroid_value(dataset: Any, cell: Mapping[str, Any]) -> Any:
    """Address the official COG native centre explicitly via inverse affine."""
    x, y = float(cell["longitude"]), float(cell["latitude"])
    if dataset.crs and str(dataset.crs) != "EPSG:4326":
        x, y = warp_transform("EPSG:4326", dataset.crs, [x], [y]); x, y = x[0], y[0]
    colf, rowf = (~dataset.transform) * (x, y); col, row = round(colf - 0.5), round(rowf - 0.5)
    _require(abs((colf - 0.5) - col) < 1e-5 and abs((rowf - 0.5) - row) < 1e-5, "soil_centroid_alignment_drift")
    value = dataset.read(1, window=rasterio.windows.Window(col, row, 1, 1), masked=True)[0, 0]
    if np.ma.is_masked(value) or value in (0, None): raise SourceMissing("soil_centroid_nodata")
    return value.item() if hasattr(value, "item") else value


def reshape_wcs_tile(array: np.ndarray, *, target_rows: int, target_cols: int, pixels_per_cell: int) -> np.ndarray:
    _require(array.ndim == 2, "wcs_tile_not_2d")
    _require(array.shape == (target_rows * pixels_per_cell, target_cols * pixels_per_cell), "wcs_tile_shape_drift")
    return np.flipud(array).reshape(target_rows, pixels_per_cell, target_cols, pixels_per_cell)


def block_centroid_values(dataset: Any, cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Sample all centroids from one expanded window (one read per layer/block)."""
    _require(cells, "empty_block")
    west = min(float(c["longitude"]) for c in cells) - 1e-8
    east = max(float(c["longitude"]) for c in cells) + 1e-8
    south = min(float(c["latitude"]) for c in cells) - 1e-8
    north = max(float(c["latitude"]) for c in cells) + 1e-8
    raw_window = dataset.window(west, south, east, north)
    roff = max(0, math.floor(float(raw_window.row_off)) - 1); coff = max(0, math.floor(float(raw_window.col_off)) - 1)
    rstop = min(dataset.height, math.ceil(float(raw_window.row_off + raw_window.height)) + 1); cstop = min(dataset.width, math.ceil(float(raw_window.col_off + raw_window.width)) + 1)
    window = rasterio.windows.Window(coff, roff, max(0, cstop-coff), max(0, rstop-roff))
    arr = dataset.read(1, window=window, masked=True)
    result = {}
    for cell in cells:
        x, y = float(cell["longitude"]) + 1e-10, float(cell["latitude"])
        if dataset.crs and str(dataset.crs) != "EPSG:4326":
            x, y = warp_transform("EPSG:4326", dataset.crs, [x], [y]); x, y = x[0], y[0]
        rr, cc = dataset.index(x, y)
        rr -= int(window.row_off); cc -= int(window.col_off)
        if 0 <= rr < arr.shape[0] and 0 <= cc < arr.shape[1] and not np.ma.is_masked(arr[rr, cc]):
            value = arr[rr, cc]; result[str(cell["cell_id"])] = value.item() if hasattr(value, "item") else value
        else:
            result[str(cell["cell_id"])] = None
    return result


def block_raster_summaries(dataset: Any, cells: Sequence[Mapping[str, Any]], *, categorical: bool = False) -> dict[str, Any]:
    """Read one block window and assign native pixel centres to exact cells."""
    _require(cells, "empty_block")
    block = production_block_key(cells[0]); bounds = production_block_bounds(block)
    west, south, east, north = bounds
    src_bounds = (west, south, east, north)
    if dataset.crs and str(dataset.crs) != "EPSG:4326":
        src_bounds = transform_bounds("EPSG:4326", dataset.crs, *bounds, densify_pts=8)
    raw_window = dataset.window(*src_bounds)
    roff = max(0, math.floor(float(raw_window.row_off)) - 1); coff = max(0, math.floor(float(raw_window.col_off)) - 1)
    rstop = min(dataset.height, math.ceil(float(raw_window.row_off + raw_window.height)) + 1); cstop = min(dataset.width, math.ceil(float(raw_window.col_off + raw_window.width)) + 1)
    window = rasterio.windows.Window(coff, roff, max(0, cstop-coff), max(0, rstop-roff))
    arr = dataset.read(1, window=window, masked=True)
    rows, cols = np.indices(arr.shape)
    xs, ys = dataset.transform * (cols + int(window.col_off) + 0.5, rows + int(window.row_off) + 0.5)
    if dataset.crs and str(dataset.crs) != "EPSG:4326":
        xs, ys = warp_transform(dataset.crs, "EPSG:4326", xs.ravel().tolist(), ys.ravel().tolist()); xs, ys = np.asarray(xs).reshape(arr.shape), np.asarray(ys).reshape(arr.shape)
    scaled_rows = (ys - GRID_ORIGIN_LAT) / CELL_DEGREE; scaled_cols = (xs - GRID_ORIGIN_LON) / CELL_DEGREE
    scaled_rows = _snap_grid_coordinates(scaled_rows); scaled_cols = _snap_grid_coordinates(scaled_cols)
    cell_rows = np.floor(scaled_rows).astype(int); cell_cols = np.floor(scaled_cols).astype(int)
    valid = ~np.ma.getmaskarray(arr)
    # Preserve values with the same vectorised index order (without per-pixel
    # coordinate transforms); category aggregation remains in-memory per cell.
    grouped = {str(c["cell_id"]): [] for c in cells}
    flat_values = np.asarray(arr)[valid].ravel()
    flat_rows, flat_cols = cell_rows[valid].ravel(), cell_cols[valid].ravel()
    for value, rr, cc in zip(flat_values, flat_rows, flat_cols):
        cid = f"r{rr:04d}c{cc:04d}"
        if cid in grouped: grouped[cid].append(value.item() if hasattr(value, "item") else value)
    out = {}
    for cid, values in grouped.items():
        if not values:
            out[cid] = None
        elif categorical:
            out[cid] = mode_low_code(values)
        else:
            out[cid] = continuous_summary(values)
    return out


def iter_tiles(bounds: tuple[float, float, float, float], tile_degrees: float = 1.0) -> Iterable[tuple[float, float, float, float]]:
    west, south, east, north = bounds; _require(tile_degrees > 0, "tile_size_invalid")
    y = south
    while y < north:
        x = west
        while x < east:
            yield x, y, min(x + tile_degrees, east), min(y + tile_degrees, north); x += tile_degrees
        y += tile_degrees


def map_alum_secondary(raw_code: Any, lookup: Mapping[Any, Any]) -> str | None:
    if raw_code is None:
        return None
    value = lookup.get(raw_code, lookup.get(str(raw_code)))
    if value is None:
        raise Goal041Error(f"alum_code_missing_from_lookup:{raw_code}")
    return str(value)


def canonical_soil_code(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if ":" in raw:
        code, label = raw.split(":", 1)
        try: code = str(int(float(code)))
        except ValueError: return raw
        return f"{code}:{SOIL_LABELS.get(code, label)}"
    try: code = str(int(float(raw)))
    except ValueError: return raw
    return f"{code}:{SOIL_LABELS.get(code, code)}"


def canonical_numeric_code(value: Any) -> str | None:
    if value is None or np.ma.is_masked(value):
        return None
    raw = str(value).strip()
    try:
        numeric = float(raw)
        if math.isfinite(numeric) and numeric.is_integer():
            return str(int(numeric))
    except ValueError:
        pass
    return raw or None


def wcs_block_summaries(dataset: Any, cells: Sequence[Mapping[str, Any]], *, pixels_per_cell: int, categorical: bool) -> dict[str, Any]:
    """Summarise an exact aligned 50x50 WCS tile by fixed array offsets."""
    block = production_block_key(cells[0]); array = dataset.read(1, masked=True)
    reshaped = reshape_wcs_tile(array, target_rows=BLOCK_CELLS, target_cols=BLOCK_CELLS, pixels_per_cell=pixels_per_cell)
    output = {}
    for cell in cells:
        rr, cc = block_cell_offset(cell, block)
        values = reshaped[rr, :, cc, :].reshape(-1)
        output[str(cell["cell_id"])] = mode_low_code(values) if categorical else continuous_summary(values)
    return output


def alum_mode_then_secondary(values: Iterable[Any], lookup: Mapping[Any, Any]) -> str | None:
    try:
        return map_alum_secondary(mode_low_code(values), lookup)
    except SourceMissing:
        return None


def pilot_equivalent(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    mismatches = []
    for name in CONTINUOUS:
        a, b = expected.get(name), observed.get(name)
        if a is None or b is None:
            if a != b: mismatches.append(name)
            continue
        tol = max(1e-6, abs(float(np.spacing(np.float32(b)))) + 5e-7) if name.startswith("bio") else 1e-3
        if abs(float(a) - float(b)) > tol: mismatches.append(name)
    for name in CATEGORICAL:
        if expected.get(name) != observed.get(name): mismatches.append(name)
    return {"equivalent": not mismatches, "mismatches": mismatches, "tolerances": {"worldclim": "float32_one_ulp_plus_serialization", "elevation": 1e-3, "categorical": "exact"}}


def diagnose_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate diagnostics; callers should pass a stream for production."""
    grouped = {region: [] for region in REGIONS}
    for row in rows:
        if row.get("region") in grouped: grouped[row["region"]].append(row)
    result = {"schema_version": "goal041-diagnostics-v2", "regions": {}}
    for region, subset in grouped.items():
        info = {"cells": len(subset), "predictors": {}}
        for name in CONTINUOUS:
            vals = _valid_values(np.asarray([r.get(name) for r in subset], dtype=float))
            info["predictors"][name] = {"valid": int(len(vals)), "missing": len(subset) - len(vals), "missing_fraction": (len(subset)-len(vals))/max(1,len(subset)), "range": [float(vals.min()), float(vals.max())] if len(vals) else None, "quantiles": {str(q): float(np.quantile(vals,q)) for q in (.01,.25,.5,.75,.99)} if len(vals) else None}
        for name in CATEGORICAL:
            vals = [str(r[name]) for r in subset if r.get(name) not in (None, "")]
            info["predictors"][name] = {"valid": len(vals), "missing": len(subset)-len(vals), "missing_fraction": (len(subset)-len(vals))/max(1,len(subset)), "levels": dict(sorted(Counter(vals).items()))}
        result["regions"][region] = info
    mainland = result["regions"][REGIONS[0]]["predictors"]; tas = result["regions"][REGIONS[1]]["predictors"]
    for name in CONTINUOUS:
        vals = [float(r[name]) for r in grouped[REGIONS[1]] if r.get(name) is not None and math.isfinite(float(r[name]))]
        rng = mainland[name]["range"]
        tas[name]["below_mainland_range"] = sum(v < rng[0] for v in vals) if rng else None
        tas[name]["above_mainland_range"] = sum(v > rng[1] for v in vals) if rng else None
        tas[name]["below_mainland_range_fraction"] = tas[name]["below_mainland_range"] / max(1, len(vals)) if rng else None
        tas[name]["above_mainland_range_fraction"] = tas[name]["above_mainland_range"] / max(1, len(vals)) if rng else None
    for name in CATEGORICAL:
        tas[name]["mainland_absent_valid_levels"] = sorted(set(tas[name]["levels"]) - set(mainland[name]["levels"]))
    return result


def assert_metadata_privacy(value: Any) -> None:
    def looks_like_cell_id(text: str) -> bool:
        return len(text) == 10 and text[0] == "r" and text[5] == "c" and text[1:5].isdigit() and text[6:].isdigit()

    def walk(node: Any):
        if isinstance(node, Mapping):
            for name, child in node.items():
                lowered = str(name).lower()
                _require(lowered not in {"cell_id", "longitude", "latitude", "row_south_to_north", "column_west_to_east"}, "goal041_metadata_privacy_failure")
                yield from walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node: yield from walk(child)
        elif isinstance(node, str):
            lowered = node.lower()
            _require(
                not looks_like_cell_id(lowered)
                and "pilot_values" not in lowered
                and "predictor_substrate.parquet" not in lowered,
                "goal041_metadata_privacy_failure",
            )
    list(walk(value))


def _write_json(root: Path, name: str, payload: Mapping[str, Any], *, private: bool = False) -> Path:
    if not private: assert_metadata_privacy(payload)
    path = root / RAW_ROOT / name if private else root / METADATA_ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"); tmp.replace(path)
    return path


def _http_bytes(url: str, accept: str = "*/*") -> bytes:
    req = Request(url, headers={"Accept": accept, "User-Agent": "dSDM-Goal041/2.0"})
    with urlopen(req, timeout=600) as response: payload = response.read()
    _require(payload and not payload.lstrip().startswith(b"<ServiceException"), "wcs_service_error")
    return payload


def _stream_download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True); partial = target.with_suffix(target.suffix + ".part"); _require(not partial.exists(), "source_partial_exists")
    request = Request(url, headers={"Accept": "*/*", "User-Agent": "dSDM-Goal041/2.0"})
    with urlopen(request, timeout=600) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1024 * 1024)
    partial.replace(target)


def _validate_soil_cog(root: Path) -> None:
    source = _config(root)["sources"]["soil_order"]; path = root / RAW_ROOT / "soil_order/ASC_EV_C_P_AU_TRN_N.cog.tif"; legend = root / RAW_ROOT / "soil_order/legend.txt"
    _require(path.is_file() and legend.is_file() and path.stat().st_size == source["bytes"] and legend.stat().st_size == source["legend_bytes"], "soil_cog_asset_contract_drift")
    legend_text = legend.read_text(errors="replace")
    _require(sha256(path) == source["sha256"] and sha256(legend) == source["legend_sha256"] and any(line.startswith("12,") and "Calcarasol" in line for line in legend_text.splitlines()), "soil_cog_checksum_legend_drift")
    with rasterio.open(path) as dataset:
        _require((dataset.width,dataset.height)==(49200,40800) and str(dataset.crs)=="EPSG:4326" and dataset.nodata == 0, "soil_cog_contract_drift")
        codes = set()
        for _, window in dataset.block_windows(1):
            values = dataset.read(1, window=window, masked=True).compressed()
            codes.update(int(v) for v in np.unique(values) if int(v) != 0)
        _require(codes <= set(range(1,15)), "soil_cog_code_ontology_drift")


def wcs_request(url: str, *, coverage: str, bbox: tuple[float,float,float,float], width: int, height: int, version: str) -> bytes:
    west,south,east,north = bbox
    if version.startswith("1"):
        query = urlencode({"SERVICE":"WCS","VERSION":"1.0.0","REQUEST":"GetCoverage","COVERAGE":coverage,"CRS":"EPSG:4326","BBOX":f"{west},{south},{east},{north}","WIDTH":width,"HEIGHT":height,"FORMAT":"GeoTIFF"})
    else:
        query = urlencode({"SERVICE":"WCS","VERSION":version,"REQUEST":"GetCoverage","COVERAGEID":coverage,"SUBSET":[f"Long({west},{east})",f"Lat({south},{north})"],"FORMAT":"image/tiff","SIZE":[f"Long({width})",f"Lat({height})"]}, doseq=True)
    return _http_bytes(url + "?" + query, "image/tiff")


def _atomic_tile(root: Path, layer: str, block: tuple[int,int], payload: bytes, expected_shape: tuple[int,int], expected_crs: str) -> Path:
    if rasterio is None: raise Goal041Error("rasterio_unavailable")
    path = root / RAW_ROOT / "cache_v3" / layer / f"r{block[0]:04d}_c{block[1]:04d}.tif"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with rasterio.open(path) as ds: _require((ds.height,ds.width)==expected_shape and str(ds.crs)==expected_crs, "cached_tile_shape_crs_conflict")
        return path
    memory = MemoryFile(payload)
    with memory.open() as ds: _require((ds.height,ds.width)==expected_shape and str(ds.crs)==expected_crs, "service_tile_shape_crs_drift")
    partial = path.with_suffix(".tif.part"); _require(not partial.exists(), "orphaned_tile_partial"); partial.write_bytes(payload); partial.replace(path)
    return path


def _pilot_cached_tile(root: Path, layer: str, block: tuple[int, int], *, bbox: tuple[float, float, float, float], width: int, height: int, coverage: str, version: str) -> Path:
    """Acquire/reuse one pilot WCS tile with fail-closed identity binding."""
    expected_shape = (height, width); expected_crs = "EPSG:4326"
    cache = root / RAW_ROOT / "pilot_cache_v2" / layer
    path = cache / f"r{block[0]:04d}_c{block[1]:04d}.tif"; receipt = path.with_suffix(".json")
    identity = {"layer": layer, "block": list(block), "bbox": list(bbox), "coverage": coverage, "version": version, "shape": list(expected_shape), "crs": expected_crs, "source_config_digest": _digest(_config(root)["sources"][layer])}
    if path.exists() or receipt.exists():
        _require(path.is_file() and receipt.is_file(), "pilot_cache_orphaned")
        record = json.loads(receipt.read_text(encoding="utf-8")); _require(record.get("identity") == identity and record.get("sha256") == sha256(path), "pilot_cache_identity_conflict")
        with rasterio.open(path) as dataset:
            _require((dataset.height, dataset.width) == expected_shape and str(dataset.crs) == expected_crs, "pilot_cache_shape_crs_conflict")
        return path
    payload = wcs_request(_config(root)["sources"][layer]["url"], coverage=coverage, bbox=bbox, width=width, height=height, version=version)
    memory = MemoryFile(payload)
    try:
        with memory.open() as dataset:
            _require((dataset.height, dataset.width) == expected_shape and str(dataset.crs) == expected_crs, "pilot_service_shape_crs_drift")
    finally:
        memory.close()
    cache.mkdir(parents=True, exist_ok=True); partial = path.with_suffix(".tif.part"); _require(not partial.exists(), "pilot_cache_orphaned_partial"); partial.write_bytes(payload); partial.replace(path)
    receipt_partial = receipt.with_suffix(".json.part"); receipt_partial.write_text(json.dumps({"identity": identity, "sha256": sha256(path)}, sort_keys=True) + "\n", encoding="utf-8"); receipt_partial.replace(receipt)
    return path


def validate_sources(root: Path) -> dict[str, Any]:
    config = _config(root)
    receipt_path = root / RAW_ROOT / "acquisition_receipt.json"
    _require(receipt_path.is_file(), "goal041_acquisition_receipt_missing")
    receipt = json.loads(receipt_path.read_text())
    _require(receipt.get("schema_version") == "goal041-acquisition-v1", "goal041_acquisition_receipt_schema_drift")
    expected_sources = set(config["sources"])
    _require(set(receipt.get("sources", {})) == expected_sources, "goal041_acquisition_source_set_drift")
    manifest = source_provenance(root)
    _require(
        manifest.get("schema_version") == "goal041-source-manifest-v2"
        and set(manifest.get("sources", {})) == expected_sources,
        "goal041_source_manifest_set_drift",
    )
    _require(set(receipt.get("sources", {})) == set(_config(root)["sources"]) == {"worldclim", "elevation", "nvis", "soil_order", "alum_secondary"}, "goal041_source_set_drift")
    checked, pending = [], []
    for name, item in receipt.get("sources", {}).items():
        if item.get("status") == "blocked": raise Goal041Error(f"source_blocked:{name}")
        if name == "worldclim":
            paths = [root / RAW_ROOT / "worldclim" / f"bio{i:02d}.tif" for i in range(1,20)]
            _require(all(p.is_file() for p in paths), "worldclim_asset_missing")
            _require(_digest([sha256(p) for p in paths]) == item.get("sha256"), "source_receipt_drift:worldclim"); checked.append(name)
        elif name == "nvis":
            p = root / RAW_ROOT / item.get("filename", "nvis_mvg.tif"); official=root/RAW_ROOT/"probes/nvis_7_extant_all.zip"; _require(p.is_file() and official.is_file() and sha256(p)==item.get("sha256") and sha256(official)==_config(root)["sources"][name]["sha256"], "source_receipt_drift:nvis"); _nvis_rat(p); checked.append(name)
        elif name == "soil_order":
            source = _config(root)["sources"][name]; p = root / RAW_ROOT / "soil_order" / "ASC_EV_C_P_AU_TRN_N.cog.tif"; legend = root / RAW_ROOT / "soil_order" / "legend.txt"
            _require(p.is_file() and legend.is_file() and sha256(p) == source["sha256"] and sha256(legend) == source["legend_sha256"], "source_receipt_drift:soil_order")
            _validate_soil_cog(root)
            checked.append(name)
        elif name == "elevation":
            p = root / RAW_ROOT / "probes_v3" / name / "probe_0p01.tif"; _require(p.is_file() and sha256(p)==item.get("sha256"), f"source_receipt_drift:{name}"); checked.append(name)
        else:
            p = root / RAW_ROOT / _config(root)["sources"][name]["filename"]; _require(p.is_file() and sha256(p)==item.get("sha256"), f"source_receipt_drift:{name}")
            if name == "alum_secondary":
                for derived, digest_key in ((root/RAW_ROOT/"alum/alum.tif","derived_tif_sha256"),(root/RAW_ROOT/"alum/alum_labels.json","labels_sha256")):
                    _require(derived.is_file(),"source_derived_asset_missing"); _require(sha256(derived)==manifest.get("sources",{}).get(name,{}).get(digest_key),"source_derived_digest_drift")
            checked.append(name)
    status = "validated" if not pending else "pending_service_tiles"
    return {"status": status, "checked": sorted(checked), "pending": sorted(pending)}


def acquire(root: Path) -> dict[str, Any]:
    """Validate/acquire immutable local assets and perform 1-cell WCS probes."""
    config = _config(root); out = {"schema_version":"goal041-acquisition-v1","retrieved_at":_now(),"sources":{}}
    raw = root / RAW_ROOT; raw.mkdir(parents=True, exist_ok=True)
    for name, source in config["sources"].items():
        if name == "worldclim":
            paths=[raw/"worldclim"/f"bio{i:02d}.tif" for i in range(1,20)]; _require(all(p.is_file() for p in paths), "worldclim_bulk_assets_missing")
            out["sources"][name]={"url":source["url"],"status":"validated","bytes":sum(p.stat().st_size for p in paths),"sha256":_digest([sha256(p) for p in paths]),"files":19,"retrieved_at":_now()}; continue
        if name == "nvis":
            p=raw/"nvis_mvg.tif"; official=raw/"probes/nvis_7_extant_all.zip"; _require(p.is_file() and official.is_file(), "nvis_asset_missing"); _require(sha256(official)==source.get("sha256"), "nvis_official_checksum_drift"); out["sources"][name]={"url":source["url"],"status":"validated","bytes":p.stat().st_size,"sha256":sha256(p),"official_zip_sha256":sha256(official),"filename":"nvis_mvg.tif","retrieved_at":_now()}; continue
        if name == "soil_order":
            target = raw / "soil_order" / "ASC_EV_C_P_AU_TRN_N.cog.tif"; legend = raw / "soil_order" / "legend.txt"
            if not target.exists(): _stream_download(source["url"], target)
            if not legend.exists(): _stream_download(source["legend_url"], legend)
            _require(sha256(target)==source["sha256"] and sha256(legend)==source["legend_sha256"], "soil_cog_checksum_drift")
            _validate_soil_cog(root)
            out["sources"][name]={"url":source["url"],"legend_url":source["legend_url"],"file_id":source["file_id"],"legend_file_id":source["legend_file_id"],"status":"validated","bytes":target.stat().st_size,"legend_bytes":legend.stat().st_size,"sha256":sha256(target),"legend_sha256":sha256(legend),"retrieved_at":_now()}; continue
        filename=source.get("filename")
        if filename:
            target=raw/filename; old=root/"data/raw/goal040/predictor_pilot"/filename
            if not target.exists() and old.is_file(): target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(old,target)
            if target.exists():
                expected=source.get("sha256"); _require(expected is None or sha256(target)==expected, f"source_checksum_drift:{name}"); out["sources"][name]={"url":source["url"],"status":"reused","bytes":target.stat().st_size,"sha256":sha256(target),"retrieved_at":_now()}; continue
        coverage=source.get("coverage"); ppc=36 if name=="elevation" else 12; version="1.0.0" if name=="elevation" else "2.0.1"
        try:
            pilot_file=root/"data/raw/goal040/predictor_pilot/pilot_values.jsonl"; pilot_cell=json.loads(pilot_file.read_text().splitlines()[0]) if pilot_file.is_file() else {"longitude":GRID_ORIGIN_LON+.005,"latitude":GRID_ORIGIN_LAT+.005}
            probe_cell = {"longitude": str(pilot_cell["longitude"]), "latitude": str(pilot_cell["latitude"])}
            payload=wcs_request(source["url"],coverage=coverage,bbox=cell_bounds(probe_cell),width=ppc,height=ppc,version=version)
            target=raw/"probes_v3"/name/"probe_0p01.tif"; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(payload)
            out["sources"][name]={"url":source["url"],"coverage":coverage,"status":"validated","probe":True,"bytes":len(payload),"sha256":sha256(target),"retrieved_at":_now()}
        except Exception as exc:
            out["sources"][name]={"url":source["url"],"coverage":coverage,"status":"blocked","reason":f"{type(exc).__name__}:{exc}","retrieved_at":_now()}
            break
    _write_json(root,"acquisition_receipt.json",out,private=True)
    manifest={"schema_version":"goal041-source-manifest-v2","retrieved_at":_now(),"sources":{k:{"url":config["sources"][k].get("url"),"legend_url":config["sources"][k].get("legend_url"),"file_id":config["sources"][k].get("file_id"),"legend_file_id":config["sources"][k].get("legend_file_id"),"product":config["sources"][k].get("product"),"version":config["sources"][k].get("version"),"coverage":config["sources"][k].get("coverage"),"semantics":config["sources"][k].get("semantics"),"crs":config["sources"][k].get("crs"),"native_resolution":config["sources"][k].get("resolution"),"nodata":config["sources"][k].get("nodata"),"licence":config["sources"][k].get("licence"),"bytes":v.get("bytes"),"legend_bytes":v.get("legend_bytes"),"retrieved_at":v.get("retrieved_at"),"sha256":v.get("sha256"),"legend_sha256":v.get("legend_sha256"),"probe_sha256":v.get("sha256") if v.get("probe") else None,"probe":v.get("probe",False)} for k,v in out["sources"].items()},"platform":platform.platform()}
    manifest["sources"]["worldclim"]["per_layer_sha256"]={f"bio{i:02d}":sha256(root/RAW_ROOT/"worldclim"/f"bio{i:02d}.tif") for i in range(1,20)}
    nvis_zip=root/RAW_ROOT/"probes/nvis_7_extant_all.zip"; nvis_tif=root/RAW_ROOT/"nvis_mvg.tif"
    manifest["sources"].setdefault("nvis",{})["official_zip_sha256"]=sha256(nvis_zip) if nvis_zip.is_file() else None; manifest["sources"].setdefault("nvis",{})["derived_geotiff_sha256"]=sha256(nvis_tif) if nvis_tif.is_file() else None
    alum_zip=root/RAW_ROOT/config["sources"]["alum_secondary"]["filename"]
    manifest["sources"].setdefault("alum_secondary",{})["archive_sha256"]=sha256(alum_zip) if alum_zip.is_file() else None
    alum_tif=root/RAW_ROOT/"alum/alum.tif"; alum_labels=root/RAW_ROOT/"alum/alum_labels.json"
    manifest["sources"].setdefault("alum_secondary",{})["derived_tif_sha256"]=sha256(alum_tif) if alum_tif.is_file() else None; manifest["sources"]["alum_secondary"]["labels_sha256"]=sha256(alum_labels) if alum_labels.is_file() else None
    _write_json(root,"goal041_source_manifest.json",manifest)
    return out


def source_provenance(root: Path) -> dict[str, Any]:
    path=root/METADATA_ROOT/"goal041_source_manifest.json"; return json.loads(path.read_text()) if path.exists() else {}


def _load_pilot(root: Path) -> tuple[list[dict[str,Any]], dict[str,dict[str,Any]]]:
    path=root/"data/raw/goal040/predictor_pilot/pilot_values.jsonl"; _require(path.is_file(), "goal041_pilot_replay_missing")
    manifest=json.loads((root/"metadata/goal040_predictor_pilot_manifest.json").read_text()); _require(manifest.get("private_outputs",{}).get("values",{}).get("sha256")==sha256(path),"goal041_pilot_values_checksum_drift")
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]; _require(len(rows)==128 and len({r.get("cell_id") for r in rows})==128, "goal041_pilot_identity_count_drift"); _require(all(set(PREDICTORS)<=set(r) and r.get("region") in REGIONS for r in rows),"goal041_pilot_schema_drift")
    return rows,{str(r["cell_id"]):r for r in rows}


def _nvis_rat(path: Path) -> dict[str, str | None]:
    """Return the checksum-bound NVIS 7 MVG ontology used by the substrate."""
    archive = path.parent / "probes" / "nvis_7_extant_all.zip"
    _require(archive.is_file(), "nvis_official_archive_missing")
    expected = {str(value) for value in range(1, 30)} | {"31", "32", "99"}
    _require(set(NVIS_MVG_LABELS) == expected, "nvis_rat_code_set_drift")
    return {
        code: None if code == "99" else f"{code}:{label}"
        for code, label in NVIS_MVG_LABELS.items()
    }


def _pilot_block_key(cell: Mapping[str, Any]) -> tuple[int, int]:
    return (math.floor((float(cell["latitude"]) - GRID_ORIGIN_LAT) / 0.1), math.floor((float(cell["longitude"]) - GRID_ORIGIN_LON) / 0.1))


def _pilot_block_bounds(key: tuple[int, int]) -> tuple[float, float, float, float]:
    south = GRID_ORIGIN_LAT + key[0] * 0.1; west = GRID_ORIGIN_LON + key[1] * 0.1
    return west, south, west + 0.1, south + 0.1


def _pilot_replay(root: Path, expected_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Replay pilot using <=0.1 degree service blocks and frozen semantics."""
    _require(rasterio is not None, "rasterio_unavailable")
    groups = defaultdict(list)
    for cell in expected_rows: groups[_pilot_block_key(cell)].append(cell)
    config = _config(root); observed = {str(c["cell_id"]): {"cell_id": str(c["cell_id"]), "region": c["region"]} for c in expected_rows}
    climates = [rasterio.open(root / RAW_ROOT / "worldclim" / f"bio{i:02d}.tif") for i in range(1, 20)]
    nvis = rasterio.open(root / RAW_ROOT / "nvis_mvg.tif")
    alum = rasterio.open(root / RAW_ROOT / "alum/alum.tif")
    soil = rasterio.open(root / RAW_ROOT / "soil_order/ASC_EV_C_P_AU_TRN_N.cog.tif")
    labels_path = root / RAW_ROOT / "alum/alum_labels.json"; alum_labels = json.loads(labels_path.read_text()) if labels_path.exists() else {}
    nvis_labels = _nvis_rat(root / RAW_ROOT / "nvis_mvg.tif")
    try:
        for pilot_key, cells in groups.items():
            for i, ds in enumerate(climates, 1):
                values = block_centroid_values(ds, cells)
                for cid, value in values.items(): observed[cid][f"bio{i:02d}"] = None if value is None else float(np.float32(value))
            for cell in cells:
                cid = str(cell["cell_id"])
                try:
                    label = nvis_labels.get(canonical_numeric_code(centroid_value(nvis, cell))); observed[cid]["nvis_mvg"] = label.split(":", 1)[1] if label and ":" in label else label
                except SourceMissing: observed[cid]["nvis_mvg"] = None
                try:
                    observed[cid]["alum_secondary"] = alum_mode_then_secondary(_cell_pixels(alum, cell), alum_labels); _require(observed[cid]["alum_secondary"] is not None, "alum_code_missing_from_lookup")
                except SourceMissing: observed[cid]["alum_secondary"] = None
                try: observed[cid]["soil_order"] = canonical_soil_code(soil_centroid_value(soil, cell))
                except SourceMissing: observed[cid]["soil_order"] = None
            source = config["sources"]["elevation"]; bbox = _pilot_block_bounds(pilot_key)
            tile = _pilot_cached_tile(root, "elevation", pilot_key, bbox=bbox, width=360, height=360, coverage=source["coverage"], version="1.0.0")
            ds = rasterio.open(tile)
            try:
                for cell in cells:
                    cid = str(cell["cell_id"])
                    value = summarize_raster_cell(ds, cell, "continuous"); observed[cid]["elevation_mean"], observed[cid]["elevation_sd"] = value
            finally: ds.close()
    finally:
        for ds in climates: ds.close()
        nvis.close(); alum.close(); soil.close()
    return observed


def prepare_pilot_baselines(root: Path) -> dict[str, Any]:
    """Freeze corrected source-native centroids before an equivalence replay."""
    _require(validate_sources(root)["status"] == "validated", "goal041_source_gate_failed")
    expected_rows, expected = _load_pilot(root)
    soil_path = root / RAW_ROOT / "soil_order/ASC_EV_C_P_AU_TRN_N.cog.tif"
    nvis_path = root / RAW_ROOT / "nvis_mvg.tif"
    soil_ds = rasterio.open(soil_path)
    nvis_ds = rasterio.open(nvis_path)
    nvis_labels = _nvis_rat(nvis_path)
    baselines = {"soil_order": {}, "nvis_mvg": {}}
    exact = {name: Counter() for name in baselines}
    denominators = Counter(row["region"] for row in expected_rows)
    try:
        for row in expected_rows:
            cid, region = str(row["cell_id"]), str(row["region"])
            try:
                soil_value = canonical_soil_code(soil_centroid_value(soil_ds, row))
            except SourceMissing:
                soil_value = None
            try:
                label = nvis_labels.get(canonical_numeric_code(centroid_value(nvis_ds, row)))
                nvis_value = label.split(":", 1)[1] if label and ":" in label else label
            except SourceMissing:
                nvis_value = None
            baselines["soil_order"][cid] = {"soil_order": soil_value}
            baselines["nvis_mvg"][cid] = {"nvis_mvg": nvis_value}
            if expected[cid].get("soil_order") == soil_value:
                exact["soil_order"][region] += 1
            if expected[cid].get("nvis_mvg") == nvis_value:
                exact["nvis_mvg"][region] += 1
    finally:
        soil_ds.close()
        nvis_ds.close()

    specifications = {
        "soil_order": ("goal041_soil_correction_receipt.json", soil_path, "CSIRO_DAP_COG"),
        "nvis_mvg": ("goal041_nvis_correction_receipt.json", nvis_path, "NVIS_7_OFFICIAL_GEOTIFF"),
    }
    result = {"status": "prepared", "cells": len(expected_rows), "sources": {}}
    for name, (receipt_name, source_path, source_name) in specifications.items():
        baseline_path = _write_json(root, f"pilot_corrected_{name}_baseline.json", baselines[name], private=True)
        by_region = {region: denominators[region] - exact[name][region] for region in REGIONS}
        receipt = {
            "schema_version": "goal041-pilot-correction-v2",
            "predictor": name,
            "source": source_name,
            "source_sha256": sha256(source_path),
            "baseline_sha256": sha256(baseline_path),
            "legacy_exact": sum(exact[name].values()),
            "legacy_discrepancies": len(expected_rows) - sum(exact[name].values()),
            "legacy_discrepancies_by_region": by_region,
            "equivalence_rule": "fresh replay must exactly match the independently frozen official-source centroid baseline",
        }
        _write_json(root, receipt_name, receipt)
        result["sources"][name] = {
            "legacy_exact": receipt["legacy_exact"],
            "legacy_discrepancies": receipt["legacy_discrepancies"],
        }
    return result


def _load_corrected_pilot_baseline(root: Path, name: str, source_path: Path) -> dict[str, dict[str, Any]]:
    baseline_path = root / RAW_ROOT / f"pilot_corrected_{name}_baseline.json"
    receipt_path = root / METADATA_ROOT / f"goal041_{'soil' if name == 'soil_order' else 'nvis'}_correction_receipt.json"
    _require(baseline_path.is_file() and receipt_path.is_file(), f"goal041_{name}_baseline_missing")
    receipt = json.loads(receipt_path.read_text())
    _require(
        receipt.get("schema_version") == "goal041-pilot-correction-v2"
        and receipt.get("predictor") == name
        and receipt.get("baseline_sha256") == sha256(baseline_path)
        and receipt.get("source_sha256") == sha256(source_path),
        f"goal041_{name}_baseline_drift",
    )
    return json.loads(baseline_path.read_text())


def pilot_equivalence_stage(root: Path) -> dict[str, Any]:
    """Replay the frozen 128 cells against pre-existing corrected baselines."""
    expected_rows, expected = _load_pilot(root)
    comparison = {cid: dict(row) for cid, row in expected.items()}
    sources = {
        "soil_order": root / RAW_ROOT / "soil_order/ASC_EV_C_P_AU_TRN_N.cog.tif",
        "nvis_mvg": root / RAW_ROOT / "nvis_mvg.tif",
    }
    for name, source_path in sources.items():
        baseline = _load_corrected_pilot_baseline(root, name, source_path)
        _require(set(baseline) == set(comparison), f"goal041_{name}_baseline_identity_drift")
        for cid in comparison:
            _require(set(baseline[cid]) == {name}, f"goal041_{name}_baseline_schema_drift")
            comparison[cid][name] = baseline[cid][name]

    observed = _pilot_replay(root, expected_rows)
    _write_json(root, "pilot_observed.json", observed, private=True)
    _require(set(observed) == set(comparison), "goal041_pilot_identity_drift")
    results = {cid: pilot_equivalent(comparison[cid], observed[cid]) for cid in sorted(comparison)}
    exact = sum(not result["mismatches"] for result in results.values())
    failed = len(results) - exact
    summary = {
        "status": "validated" if exact == 128 and failed == 0 else "blocked",
        "cells": 128,
        "exact": exact,
        "failed": failed,
        "mismatch_count": failed,
        "run_identity": run_identity(root),
        "correction_receipt_sha256": {
            "soil_order": sha256(root / METADATA_ROOT / "goal041_soil_correction_receipt.json"),
            "nvis_mvg": sha256(root / METADATA_ROOT / "goal041_nvis_correction_receipt.json"),
        },
    }
    _write_json(root, "goal041_pilot_equivalence.json", summary)
    _require(summary["status"] == "validated", "goal041_pilot_equivalence_failed")
    return summary


def representative_blocks(cells: Sequence[Mapping[str,Any]], per_region: int = 2) -> list[tuple[int,int]]:
    grouped=defaultdict(Counter)
    for c in cells: grouped[c["region"]][production_block_key(c)] += 1
    selected=[]
    for region in REGIONS:
        occupancy=grouped[region]; _require(len(occupancy)>=per_region, "benchmark_insufficient_region_blocks")
        ranked=sorted(occupancy, key=lambda b:(-occupancy[b], b[0], b[1]))
        candidates=ranked[:max(per_region, (len(ranked)+1)//2)]
        picks=[candidates[0]]
        while len(picks)<per_region:
            picks.append(max((b for b in candidates if b not in picks), key=lambda b:(min((b[0]-p[0])**2+(b[1]-p[1])**2 for p in picks), occupancy[b], -b[0], -b[1])))
        selected.extend(picks)
    return selected


def run_benchmark(root: Path) -> dict[str, Any]:
    cells=_cells(root); blocks=representative_blocks(cells,2); by_block=defaultdict(list)
    for c in cells:
        if production_block_key(c) in blocks: by_block[production_block_key(c)].append(c)
    # Cold-cache evidence: discard only derived tiles for representative blocks.
    cache_root=root/RAW_ROOT/"cache_v3"
    for block in blocks:
        for layer in ("elevation",):
            for suffix in (".tif", ".json"):
                candidate=cache_root/layer/f"r{block[0]:04d}_c{block[1]:04d}{suffix}"
                if candidate.exists(): candidate.unlink()
    fetch=BlockProcessor(root)
    started=time.monotonic(); before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss; count=0
    try:
        for block in blocks:
            count += len(fetch.process_block(block))
    finally:
        fetch.close()
    elapsed=max(time.monotonic()-started,1e-9); after=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    projected=592*elapsed/max(1,len(blocks))
    selected_files=[cache_root/"elevation"/f"r{block[0]:04d}_c{block[1]:04d}{suffix}" for block in blocks for suffix in (".tif", ".json")]
    cache_bytes=sum(p.stat().st_size for p in selected_files if p.is_file())
    rss=max(before,after); rss_bytes=int(rss if sys.platform == "darwin" else rss * 1024)
    result={"status":"validated" if projected<12*3600 else "blocked","cells":count,"blocks":len(blocks),"seconds":elapsed,"blocks_per_second":len(blocks)/elapsed,"max_rss_bytes":rss_bytes,"max_rss_unit":"bytes","cache_bytes":cache_bytes,"output_bytes":0,"cache_temperature":"cold","projected_full_run_seconds":projected,"projected_basis":"592 occupied block rate","platform":platform.platform(),"route_recommendation":"deep-server-ts","regions":list(REGIONS),"run_identity":run_identity(root)}
    _write_json(root,"goal041_benchmark_manifest.json",result); _require(result["status"]=="validated", "goal041_benchmark_ceiling_failed"); return result


def validate_benchmark(root: Path) -> dict[str,Any]:
    benchmark_path = root / METADATA_ROOT / "goal041_benchmark_manifest.json"
    compute_path = root / METADATA_ROOT / "goal041_compute_manifest.json"
    value = json.loads(benchmark_path.read_text())
    compute = json.loads(compute_path.read_text())
    identity = run_identity(root)
    _require(
        value.get("status") == "validated"
        and value.get("blocks", 0) >= 4
        and value.get("projected_full_run_seconds", 1e99) < 12 * 3600
        and value.get("run_identity") == identity,
        "goal041_benchmark_gate_failed",
    )
    benchmark_facts = {
        "blocks": value["blocks"],
        "cells": value["cells"],
        "seconds": value["seconds"],
        "projected_seconds": value["projected_full_run_seconds"],
        "max_rss_bytes": value["max_rss_bytes"],
        "cache_bytes": value["cache_bytes"],
    }
    _require(
        compute.get("schema_version") == "goal041-compute-manifest-v2"
        and compute.get("route_selected") == "deep-server-ts"
        and compute.get("run_identity") == identity
        and compute.get("decision_timestamp")
        and compute.get("benchmark") == benchmark_facts
        and compute.get("benchmark_manifest_sha256") == sha256(benchmark_path),
        "goal041_compute_manifest_conflict",
    )
    return value


def build_elevation_tile_manifest(root: Path) -> dict[str, Any]:
    """Bind all production DEM WCS payloads without publishing block locations."""
    cache = root / RAW_ROOT / "cache_v3/elevation"
    tifs = sorted(cache.glob("r*_c*.tif"))
    sidecars = sorted(cache.glob("r*_c*.json"))
    _require(len(tifs) == 592 and [path.stem for path in tifs] == [path.stem for path in sidecars], "goal041_elevation_tile_set_drift")
    items = []
    upstream_identities = set()
    for tif, sidecar in zip(tifs, sidecars):
        receipt = json.loads(sidecar.read_text())
        identity = receipt.get("identity", {})
        _require(
            receipt.get("sha256") == sha256(tif)
            and identity.get("layer") == "elevation"
            and isinstance(identity.get("block"), list)
            and len(identity["block"]) == 2,
            "goal041_elevation_tile_receipt_drift",
        )
        upstream_identities.add(identity.get("run_identity"))
        items.append({
            "block": identity["block"],
            "request": {key: identity.get(key) for key in ("layer", "shape", "crs", "source")},
            "tile_sha256": receipt["sha256"],
        })
    _require(len(upstream_identities) == 1 and None not in upstream_identities, "goal041_elevation_tile_run_identity_drift")
    result = {
        "schema_version": "goal041-elevation-tile-manifest-v1",
        "tiles": len(items),
        "upstream_run_identity": next(iter(upstream_identities)),
        "ordered_request_tile_digest": _digest(items),
        "source_manifest_sha256": sha256(root / METADATA_ROOT / "goal041_source_manifest.json"),
        "validation_rule": "592 sorted block/request identities with each cached payload SHA-256 rechecked",
    }
    _write_json(root, "goal041_elevation_tile_manifest.json", result)
    return result


class BlockProcessor:
    """Production block processor; no cell callback path."""
    def __init__(self, root: Path):
        self.root=root; self.config=_config(root); self.cells=_cells(root); self.run_identity=run_identity(root); self.by_block=defaultdict(list)
        for c in self.cells: self.by_block[production_block_key(c)].append(c)
        self.local={}; self.tile_cache={}
        if rasterio is not None:
            self.local["worldclim"]=[rasterio.open(root/RAW_ROOT/"worldclim"/f"bio{i:02d}.tif") for i in range(1,20)] if all((root/RAW_ROOT/"worldclim"/f"bio{i:02d}.tif").is_file() for i in range(1,20)) else []
            nvis=root/RAW_ROOT/"nvis_mvg.tif"; alum=root/RAW_ROOT/"alum/alum.tif"
            if nvis.is_file(): self.local["nvis"]=rasterio.open(nvis); self.local["nvis_labels"]=_nvis_rat(nvis)
            soil = root / RAW_ROOT / "soil_order/ASC_EV_C_P_AU_TRN_N.cog.tif"
            if soil.is_file(): self.local["soil_order"] = rasterio.open(soil)
            if alum.is_file(): self.local["alum"]=rasterio.open(alum)
            labels=root/RAW_ROOT/"alum/alum_labels.json"; self.local["alum_labels"]=json.loads(labels.read_text()) if labels.is_file() else {}
    def close(self):
        for value in self.local.values():
            if isinstance(value,list):
                for ds in value: ds.close()
            elif hasattr(value,"close"): value.close()
        for ds,memory in self.tile_cache.values():
            ds.close()
            if memory is not None: memory.close()
        self.tile_cache.clear()
    def _service(self, layer: str, block: tuple[int,int]):
        key=(layer,*block)
        if key in self.tile_cache: return self.tile_cache[key][0]
        _require(layer == "elevation", "service_layer_not_supported")
        source=self.config["sources"]["elevation"]; ppc=36; version="1.0.0"
        expected_shape=(BLOCK_CELLS*ppc,)*2
        path=self.root/RAW_ROOT/"cache_v3"/layer/f"r{block[0]:04d}_c{block[1]:04d}.tif"; sidecar=path.with_suffix(".json"); path.parent.mkdir(parents=True,exist_ok=True)
        identity={"layer":layer,"block":list(block),"shape":list(expected_shape),"crs":"EPSG:4326","source":source.get("coverage"),"run_identity":self.run_identity}
        _require(path.exists() == sidecar.exists(), "cached_tile_orphaned")
        if path.exists() and sidecar.exists():
            recorded=json.loads(sidecar.read_text()); _require(recorded.get("identity")==identity and recorded.get("sha256")==sha256(path),"cached_tile_identity_conflict")
            ds=rasterio.open(path); _require((ds.height,ds.width)==expected_shape and str(ds.crs)=="EPSG:4326","cached_tile_shape_crs_conflict"); self.tile_cache[key]=(ds,None); return ds
        payload=wcs_request(source["url"],coverage=source["coverage"],bbox=production_block_bounds(block),width=expected_shape[1],height=expected_shape[0],version=version)
        memory=MemoryFile(payload); ds=memory.open(); _require((ds.height,ds.width)==expected_shape and str(ds.crs)=="EPSG:4326",f"{layer}_tile_shape_crs_drift"); memory.close(); ds.close()
        part=path.with_suffix(".tif.part"); side_part=sidecar.with_suffix(".json.part"); _require(not part.exists() and not side_part.exists(),"orphaned_tile_partial"); part.write_bytes(payload); part.replace(path); side_part.write_text(json.dumps({"identity":identity,"sha256":sha256(path)},sort_keys=True)+"\n"); side_part.replace(sidecar)
        ds=rasterio.open(path); self.tile_cache[key]=(ds,None); return ds
    def process_block(self, block: tuple[int,int]) -> list[dict[str,Any]]:
        cells=self.by_block[block]; result={str(c["cell_id"]):{"cell_id":str(c["cell_id"]),"region":c["region"]} for c in cells}
        if self.local.get("worldclim"):
            for i,ds in enumerate(self.local["worldclim"],1):
                values=block_centroid_values(ds,cells)
                for cid,v in values.items(): result[cid][f"bio{i:02d}"]=None if v is None else float(np.float32(v))
        dem_ds=self._service("elevation",block)
        dem=wcs_block_summaries(dem_ds,cells,pixels_per_cell=36,categorical=False)
        soil=block_raster_summaries(self.local["soil_order"],cells,categorical=True)
        nvis=block_raster_summaries(self.local["nvis"],cells,categorical=True) if self.local.get("nvis") else {}
        alum=block_raster_summaries(self.local["alum"],cells,categorical=True) if self.local.get("alum") else {}
        for cid in result:
            value=dem.get(cid); result[cid]["elevation_mean"]=value[0] if value else None; result[cid]["elevation_sd"]=value[1] if value else None
            soil_code = None if soil.get(cid) is None else canonical_soil_code(soil[cid]); result[cid]["soil_order"] = soil_code
            nvis_code = canonical_numeric_code(nvis.get(cid)); nvis_labels = self.local.get("nvis_labels", {}); result[cid]["nvis_mvg"] = nvis_labels.get(nvis_code, nvis_code)
            raw_alum=alum.get(cid); result[cid]["alum_secondary"]=map_alum_secondary(raw_alum,self.local.get("alum_labels",{})); _require(raw_alum is None or result[cid]["alum_secondary"] is not None, "alum_code_missing_from_lookup")
        rows=[result[cid] for cid in sorted(result)]
        for key in (("elevation",*block),):
            ds_mem=self.tile_cache.pop(key,None)
            if ds_mem:
                ds_mem[0].close()
        return rows

def _arrow_schema():
    import pyarrow as pa
    return pa.schema([
        pa.field("cell_id", pa.string()),
        pa.field("region", pa.string()),
        *[pa.field(name, pa.float64()) for name in CONTINUOUS],
        *[pa.field(name, pa.string()) for name in CATEGORICAL],
    ])


def _schema_contract(schema=None) -> list[dict[str, Any]]:
    schema = schema or _arrow_schema()
    return [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in schema]


def _write_parquet(path: Path, rows: Iterable[Mapping[str,Any]], *, overwrite: bool=False) -> Path:
    import pyarrow as pa, pyarrow.parquet as pq
    if path.exists() and not overwrite: raise Goal041Error("predictor_chunk_conflict")
    schema = _arrow_schema()
    temp=path.with_suffix(path.suffix+".part"); _require(not temp.exists(),"predictor_chunk_orphaned_partial"); writer=pq.ParquetWriter(temp,schema,compression="zstd"); batch=[]
    try:
        for row in rows:
            _require(set(row)==set(OUTPUT_FIELDS),"predictor_row_schema_drift"); value={n:row.get(n) for n in OUTPUT_FIELDS}; value["cell_id"]=str(value["cell_id"]); value["region"]=str(value["region"]); value.update({n:(None if value[n] is None else str(value[n])) for n in CATEGORICAL}); batch.append(value)
            if len(batch)>=10000: writer.write_table(pa.Table.from_pylist(batch,schema=schema)); batch=[]
        if batch: writer.write_table(pa.Table.from_pylist(batch,schema=schema))
    finally: writer.close()
    temp.replace(path); return path


def _chunk_band(path: Path) -> int:
    try:
        return int(path.stem.split("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise Goal041Error("predictor_chunk_name_invalid") from exc


def _chunk_receipt_path(root: Path, band: int) -> Path:
    return root / RAW_ROOT / f"chunk_receipt_{band:04d}.json"


def _chunk_receipt_payload(path: Path, band: int, ids: Sequence[str], identity: str) -> dict[str, Any]:
    import pyarrow.parquet as pq
    return {
        "schema_version": "goal041-chunk-receipt-v2",
        "band": band,
        "rows": pq.read_metadata(path).num_rows,
        "schema": _schema_contract(pq.read_schema(path)),
        "chunk_sha256": sha256(path),
        "cell_id_digest": _digest(list(ids)),
        "run_identity": identity,
    }


def _validate_chunk_pair(root: Path, path: Path, ids: Sequence[str], identity: str) -> dict[str, Any]:
    import pyarrow.parquet as pq
    band = _chunk_band(path)
    receipt_path = _chunk_receipt_path(root, band)
    _require(path.exists() == receipt_path.exists(), "predictor_chunk_orphaned")
    _require(path.is_file() and receipt_path.is_file(), "predictor_chunk_pair_missing")
    _require(pq.read_schema(path).equals(_arrow_schema(), check_metadata=False), "predictor_chunk_schema_drift")
    actual_ids = pq.read_table(path, columns=["cell_id"]).column("cell_id").to_pylist()
    _require(actual_ids == list(ids), "predictor_chunk_identity_order_drift")
    receipt = json.loads(receipt_path.read_text())
    _require(receipt == _chunk_receipt_payload(path, band, ids, identity), "predictor_chunk_receipt_drift")
    return receipt


def _band_chunks(root: Path, processor: BlockProcessor) -> list[Path]:
    chunk_root=root/RAW_ROOT/"chunks"; chunk_root.mkdir(parents=True,exist_ok=True); cells=processor.cells; chunks=[]
    max_row=max(int(c["row_south_to_north"]) for c in cells); band_count=max_row//BAND_ROWS+1
    for band in range(band_count):
        subset=[c for c in cells if band*BAND_ROWS<=int(c["row_south_to_north"])<(band+1)*BAND_ROWS]
        if not subset: continue
        path=chunk_root/f"band_{band:04d}.parquet"; ids=[c["cell_id"] for c in subset]; receipt_path=_chunk_receipt_path(root,band)
        _require(path.exists() == receipt_path.exists(), "predictor_chunk_orphaned")
        if path.exists():
            _validate_chunk_pair(root,path,ids,processor.run_identity); chunks.append(path); continue
        rows=[]; subset_ids={c["cell_id"] for c in subset}
        for block in sorted({production_block_key(c) for c in subset}): rows.extend(r for r in processor.process_block(block) if r["cell_id"] in subset_ids)
        rows.sort(key=lambda r:r["cell_id"]); _require([r["cell_id"] for r in rows]==ids,"predictor_chunk_rows_drift"); _write_parquet(path,rows); chunks.append(path)
        _require(not receipt_path.with_suffix(".json.part").exists(),"predictor_chunk_receipt_partial")
        _write_json(root,f"chunk_receipt_{band:04d}.json",_chunk_receipt_payload(path,band,ids,processor.run_identity),private=True)
        _validate_chunk_pair(root,path,ids,processor.run_identity)
    return chunks


def extract_chunks(root: Path) -> dict[str,Any]:
    processor=BlockProcessor(root)
    try: chunks=_band_chunks(root,processor)
    finally: processor.close()
    import pyarrow.parquet as pq
    final=root/RAW_ROOT/TABLE_NAME; rows=(row for chunk in chunks for row in pq.read_table(chunk).to_pylist()); _write_parquet(final,rows,overwrite=True)
    chunk_entries=[]
    for chunk in chunks:
        band=_chunk_band(chunk); receipt=json.loads(_chunk_receipt_path(root,band).read_text())
        chunk_entries.append({"band":band,"rows":receipt["rows"],"sha256":receipt["chunk_sha256"],"receipt_sha256":sha256(_chunk_receipt_path(root,band)),"ordered_identity_digest":receipt["cell_id_digest"]})
    manifest={"schema_version":"goal041-table-manifest-v3","schema":_schema_contract(),"rows":sum(entry["rows"] for entry in chunk_entries),"regions":dict(Counter(c["region"] for c in processor.cells)),"source_digest":_digest(immutable_source_provenance(root)),"run_identity":processor.run_identity,"chunks":chunk_entries,"final_sha256":sha256(final),"environment":runtime_environment()}
    _write_json(root,"goal041_table_manifest.json",manifest)
    return {"status":"complete","rows":manifest["rows"],"chunks":len(chunks),"sha256":manifest["final_sha256"]}


def validate_table(root: Path, *, table: Path|None=None) -> dict[str,Any]:
    import pyarrow.parquet as pq
    path=table or root/RAW_ROOT/TABLE_NAME; _require(path.is_file(),"predictor_table_missing"); schema=pq.read_schema(path); _require(schema.equals(_arrow_schema(),check_metadata=False),"predictor_table_schema_drift")
    actual=pq.read_table(path,columns=["cell_id","region"]); ids=actual.column("cell_id").to_pylist(); regions=actual.column("region").to_pylist(); cells=_cells(root)
    _require(len(ids)==EXPECTED_CELLS,"predictor_table_row_count_drift"); _require(ids==[c["cell_id"] for c in cells],"predictor_table_identity_order_drift"); _require(regions==[c["region"] for c in cells],"predictor_table_region_drift")
    identity=run_identity(root); expected_regions=dict(Counter(c["region"] for c in cells)); manifest_path=root/METADATA_ROOT/"goal041_table_manifest.json"; _require(manifest_path.is_file(),"goal041_table_manifest_missing"); manifest=json.loads(manifest_path.read_text())
    environment=manifest.get("environment",{}); _require(set(environment)=={"platform","python","numpy","rasterio","gdal","pyarrow"} and all(isinstance(value,str) and value for value in environment.values()),"goal041_table_environment_conflict")
    _require(manifest.get("schema_version")=="goal041-table-manifest-v3" and manifest.get("schema")==_schema_contract() and manifest.get("rows")==EXPECTED_CELLS and manifest.get("regions")==expected_regions and manifest.get("source_digest")==_digest(immutable_source_provenance(root)) and manifest.get("final_sha256")==sha256(path) and manifest.get("run_identity")==identity,"goal041_table_manifest_conflict")
    cells_by_band=defaultdict(list)
    for cell in cells: cells_by_band[int(cell["row_south_to_north"])//BAND_ROWS].append(cell["cell_id"])
    expected_entries=[]
    for band in sorted(cells_by_band):
        chunk=root/RAW_ROOT/"chunks"/f"band_{band:04d}.parquet"; receipt=_validate_chunk_pair(root,chunk,cells_by_band[band],identity)
        expected_entries.append({"band":band,"rows":receipt["rows"],"sha256":receipt["chunk_sha256"],"receipt_sha256":sha256(_chunk_receipt_path(root,band)),"ordered_identity_digest":receipt["cell_id_digest"]})
    _require(manifest.get("chunks")==expected_entries and sum(entry["rows"] for entry in expected_entries)==EXPECTED_CELLS,"goal041_table_chunk_manifest_conflict")
    return {"status":"validated","rows":len(ids),"chunks":len(expected_entries),"sha256":sha256(path)}


def diagnose(root: Path) -> dict[str,Any]:
    import pyarrow.parquet as pq
    path=root/RAW_ROOT/TABLE_NAME; _require(path.is_file(),"predictor_table_missing")
    # Iterate Arrow record batches: no 1.1-million-row Python dict materialisation.
    state={region:{"rows":0,"continuous":{name:[] for name in CONTINUOUS},"categorical":{name:Counter() for name in CATEGORICAL}} for region in REGIONS}
    for batch in pq.ParquetFile(path).iter_batches(columns=["region",*PREDICTORS],batch_size=65536):
        frame=batch.to_pydict()
        for i,region in enumerate(frame["region"]):
            if region not in state: continue
            state[region]["rows"]+=1
            for name in CONTINUOUS:
                value=frame[name][i]
                if value is not None and math.isfinite(float(value)): state[region]["continuous"][name].append(float(value))
            for name in CATEGORICAL:
                value=frame[name][i]
                if value not in (None, ""): state[region]["categorical"][name][str(value)]+=1
    diagnostics={"schema_version":"goal041-diagnostics-v3","table_sha256":sha256(path),"run_identity":run_identity(root),"regions":{}}
    for region in REGIONS:
        info={"cells":state[region]["rows"],"predictors":{}}
        for name in CONTINUOUS:
            values=np.asarray(state[region]["continuous"][name],dtype=float); missing=state[region]["rows"]-len(values)
            info["predictors"][name]={"valid":len(values),"missing":missing,"missing_fraction":missing/max(1,state[region]["rows"]),"range":[float(values.min()),float(values.max())] if len(values) else None,"quantiles":{str(q):float(np.quantile(values,q)) for q in (.01,.25,.5,.75,.99)} if len(values) else None}
        for name in CATEGORICAL:
            counts=dict(sorted(state[region]["categorical"][name].items())); valid=sum(counts.values()); missing=state[region]["rows"]-valid
            info["predictors"][name]={"valid":valid,"missing":missing,"missing_fraction":missing/max(1,state[region]["rows"]),"levels":counts}
        diagnostics["regions"][region]=info
    mainland=diagnostics["regions"][REGIONS[0]]["predictors"]; tas=diagnostics["regions"][REGIONS[1]]["predictors"]
    for name in CONTINUOUS:
        rng=mainland[name]["range"]; values=state[REGIONS[1]]["continuous"][name]; tas[name]["below_mainland_range"]=sum(v<rng[0] for v in values) if rng else None; tas[name]["above_mainland_range"]=sum(v>rng[1] for v in values) if rng else None; tas[name]["below_mainland_range_fraction"]=tas[name]["below_mainland_range"]/max(1,len(values)) if rng else None; tas[name]["above_mainland_range_fraction"]=tas[name]["above_mainland_range"]/max(1,len(values)) if rng else None
    for name in CATEGORICAL: tas[name]["mainland_absent_valid_levels"]=sorted(set(tas[name]["levels"])-set(mainland[name]["levels"]))
    _write_json(root,"goal041_diagnostics.json",diagnostics); return {"status":"complete","sha256":sha256(root/METADATA_ROOT/"goal041_diagnostics.json")}


def _component_summary(cells: set[tuple[int, int]]) -> dict[str, Any]:
    unseen = set(cells)
    sizes = []
    while unseen:
        stack = [unseen.pop()]
        size = 0
        while stack:
            row, column = stack.pop()
            size += 1
            for neighbour in ((row - 1, column), (row + 1, column), (row, column - 1), (row, column + 1)):
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
        sizes.append(size)
    sizes.sort(reverse=True)
    return {
        "components": len(sizes),
        "largest": sizes[0] if sizes else 0,
        "singletons": sum(size == 1 for size in sizes),
        "largest_fraction": (sizes[0] / len(cells)) if cells else 0.0,
    }


def build_worldclim_missingness_receipt(root: Path) -> dict[str, Any]:
    import pyarrow.parquet as pq
    table_path = root / RAW_ROOT / TABLE_NAME
    _require(table_path.is_file(), "predictor_table_missing")
    missing_ids = set()
    missing_region = {}
    other_names = ["elevation_mean", "elevation_sd", *CATEGORICAL]
    other_missing = {region: {name: 0 for name in other_names} for region in REGIONS}
    columns = ["cell_id", "region", *CONTINUOUS[:19], *other_names]
    for batch in pq.ParquetFile(table_path).iter_batches(columns=columns, batch_size=65536):
        frame = batch.to_pydict()
        for index, cell_id in enumerate(frame["cell_id"]):
            flags = [frame[name][index] is None for name in CONTINUOUS[:19]]
            _require(not any(flags) or all(flags), "goal041_worldclim_nonjoint_missingness")
            if not all(flags):
                continue
            region = frame["region"][index]
            _require(region in REGIONS, "goal041_worldclim_region_drift")
            missing_ids.add(cell_id)
            missing_region[cell_id] = region
            for name in other_names:
                other_missing[region][name] += frame[name][index] is None
    spatial = {region: set() for region in REGIONS}
    with (root / CELL_PATH).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cell_id = row["cell_id"]
            if cell_id in missing_ids:
                spatial[missing_region[cell_id]].add((int(row["row_south_to_north"]), int(row["column_west_to_east"])))
    _require(sum(len(cells) for cells in spatial.values()) == len(missing_ids), "goal041_worldclim_missing_ledger_drift")
    components = {region: _component_summary(spatial[region]) for region in REGIONS}
    dispersed = all(value["largest_fraction"] < 0.05 and value["singletons"] / max(1, len(spatial[region])) > 0.5 for region, value in components.items())
    receipt = {
        "schema_version": "goal041-worldclim-missingness-v1",
        "run_identity": run_identity(root),
        "table_sha256": sha256(table_path),
        "joint_missing_all_bio": {region: len(spatial[region]) for region in REGIONS},
        "components": components,
        "other_predictor_missing_within_footprint": other_missing,
        "classification": "dispersed_source_centroid_nodata" if dispersed else "coherent_unexplained_gap",
        "method": "four-neighbour components among exact eligible cells jointly missing BIO1-BIO19; dispersed requires largest component below 5% and more than 50% singletons in each region",
    }
    _write_json(root, "goal041_worldclim_missingness_receipt.json", receipt)
    return receipt


def validate_contract(root: Path) -> dict[str,Any]:
    config=_config(root); cells=_cells(root); counts=Counter(c["region"] for c in cells); _require(sum(counts.values())==EXPECTED_CELLS,"goal041_cell_count_drift"); return {"status":"validated","cells":len(cells),"regions":dict(counts),"predictors":len(PREDICTORS),"config_sha256":sha256(root/CONFIG_PATH)}


def _assess_diagnostics(root: Path, diagnostics: Mapping[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    table_path = root / RAW_ROOT / TABLE_NAME
    _require(
        diagnostics.get("schema_version") == "goal041-diagnostics-v3"
        and diagnostics.get("table_sha256") == sha256(table_path)
        and diagnostics.get("run_identity") == run_identity(root),
        "goal041_diagnostics_provenance_drift",
    )
    _require(set(diagnostics.get("regions", {})) == set(REGIONS), "goal041_diagnostics_region_drift")
    expected_counts = dict(Counter(cell["region"] for cell in _cells(root)))
    allowed_levels = {
        "nvis_mvg": set(_nvis_rat(root / RAW_ROOT / "nvis_mvg.tif").values()),
        "soil_order": {f"{i}:{SOIL_LABELS[str(i)]}" for i in range(1, 15)},
        "alum_secondary": set(json.loads((root / RAW_ROOT / "alum/alum_labels.json").read_text()).values()),
    }
    missingness = {name: {} for name in PREDICTORS}
    per_predictor = {name: {"status": "ready", "reasons": []} for name in PREDICTORS}

    for region in REGIONS:
        region_data = diagnostics["regions"][region]
        _require(region_data.get("cells") == expected_counts[region], "goal041_diagnostics_cell_count_drift")
        _require(set(region_data.get("predictors", {})) == set(PREDICTORS), "goal041_diagnostics_predictor_set_drift")
        for name in PREDICTORS:
            item = region_data["predictors"][name]
            valid, missing, fraction = item.get("valid"), item.get("missing"), item.get("missing_fraction")
            _require(
                isinstance(valid, int)
                and isinstance(missing, int)
                and valid >= 0
                and missing >= 0
                and valid + missing == expected_counts[region]
                and isinstance(fraction, (int, float))
                and math.isfinite(float(fraction))
                and math.isclose(float(fraction), missing / expected_counts[region], abs_tol=1e-12),
                "goal041_diagnostics_missingness_drift",
            )
            missingness[name][region] = float(fraction)
            if name in CONTINUOUS:
                value_range, quantiles = item.get("range"), item.get("quantiles")
                if valid:
                    _require(
                        isinstance(value_range, list)
                        and len(value_range) == 2
                        and all(math.isfinite(float(value)) for value in value_range)
                        and value_range[0] <= value_range[1]
                        and set(quantiles or {}) == {"0.01", "0.25", "0.5", "0.75", "0.99"}
                        and all(math.isfinite(float(value)) for value in quantiles.values()),
                        "goal041_diagnostics_nonfinite_summary",
                    )
                else:
                    _require(value_range is None and quantiles is None, "goal041_diagnostics_empty_summary_drift")
            else:
                levels = item.get("levels")
                _require(
                    isinstance(levels, Mapping)
                    and all(isinstance(count, int) and count > 0 for count in levels.values())
                    and sum(levels.values()) == valid,
                    "goal041_diagnostics_category_count_drift",
                )
                _require(set(levels) <= allowed_levels[name], "goal041_category_ontology_failure")

    tasmania = diagnostics["regions"][REGIONS[1]]["predictors"]
    mainland = diagnostics["regions"][REGIONS[0]]["predictors"]
    for name in CONTINUOUS:
        valid = tasmania[name]["valid"]
        for direction in ("below", "above"):
            count = tasmania[name].get(f"{direction}_mainland_range")
            fraction = tasmania[name].get(f"{direction}_mainland_range_fraction")
            if mainland[name]["valid"] and valid:
                _require(
                    isinstance(count, int)
                    and 0 <= count <= valid
                    and isinstance(fraction, (int, float))
                    and math.isfinite(float(fraction))
                    and math.isclose(float(fraction), count / valid, abs_tol=1e-12),
                    "goal041_diagnostics_extrapolation_drift",
                )
            else:
                _require(count is None and fraction is None, "goal041_diagnostics_extrapolation_drift")
    for name in CATEGORICAL:
        expected_unseen = sorted(set(tasmania[name]["levels"]) - set(mainland[name]["levels"]))
        _require(tasmania[name].get("mainland_absent_valid_levels") == expected_unseen, "goal041_diagnostics_unseen_level_drift")

    reasons = []
    for name in PREDICTORS:
        predictor_reasons = []
        for region in REGIONS:
            if missingness[name][region] >= 0.05:
                predictor_reasons.append(f"{region}_missingness_ge_5pct")
        if abs(missingness[name][REGIONS[0]] - missingness[name][REGIONS[1]]) >= 0.05:
            predictor_reasons.append("regional_missingness_difference_ge_5pp")
        if predictor_reasons:
            per_predictor[name] = {"status": "repair", "reasons": predictor_reasons}
            reasons.extend(f"{name}:{reason}" for reason in predictor_reasons)
    return ("repair" if reasons else "ready"), reasons, per_predictor


def _validate_provenance_receipts(root: Path, table: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> dict[str, str]:
    paths = {
        "elevation_tiles": root / METADATA_ROOT / "goal041_elevation_tile_manifest.json",
        "nvis_repair": root / METADATA_ROOT / "goal041_nvis_repair_receipt.json",
        "worldclim_missingness": root / METADATA_ROOT / "goal041_worldclim_missingness_receipt.json",
    }
    _require(all(path.is_file() for path in paths.values()), "goal041_provenance_receipt_missing")
    elevation = json.loads(paths["elevation_tiles"].read_text())
    repair = json.loads(paths["nvis_repair"].read_text())
    climate = json.loads(paths["worldclim_missingness"].read_text())
    identity = run_identity(root)
    table_manifest_path = root / METADATA_ROOT / "goal041_table_manifest.json"
    _require(
        elevation.get("schema_version") == "goal041-elevation-tile-manifest-v1"
        and elevation.get("tiles") == 592
        and elevation.get("source_manifest_sha256") == sha256(root / METADATA_ROOT / "goal041_source_manifest.json"),
        "goal041_elevation_tile_manifest_drift",
    )
    _require(
        repair.get("schema_version") == "goal041-nvis-repair-v1"
        and repair.get("upstream", {}).get("run_identity") == elevation.get("upstream_run_identity")
        and repair.get("upstream", {}).get("elevation_tile_manifest_sha256") == sha256(paths["elevation_tiles"])
        and repair.get("mapping", {}).get("source_sha256") == sha256(root / RAW_ROOT / "probes/nvis_7_extant_all.zip")
        and repair.get("mapping", {}).get("mapping_digest") == _digest(_nvis_rat(root / RAW_ROOT / "nvis_mvg.tif"))
        and repair.get("repaired", {}).get("run_identity") == identity
        and repair.get("repaired", {}).get("final_sha256") == table["sha256"]
        and repair.get("repaired", {}).get("table_manifest_sha256") == sha256(table_manifest_path),
        "goal041_nvis_repair_receipt_drift",
    )
    expected_missing = {region: diagnostics["regions"][region]["predictors"]["bio01"]["missing"] for region in REGIONS}
    _require(
        climate.get("schema_version") == "goal041-worldclim-missingness-v1"
        and climate.get("run_identity") == identity
        and climate.get("table_sha256") == table["sha256"]
        and climate.get("joint_missing_all_bio") == expected_missing
        and climate.get("classification") == "dispersed_source_centroid_nodata"
        and all(diagnostics["regions"][region]["predictors"][name]["missing"] == expected_missing[region] for region in REGIONS for name in CONTINUOUS[:19])
        and all(climate["components"][region]["largest"] / expected_missing[region] < 0.05 for region in REGIONS),
        "goal041_worldclim_missingness_receipt_drift",
    )
    return {name: sha256(path) for name, path in paths.items()}


def validate(root: Path) -> dict[str,Any]:
    gates = {}
    try:
        source=validate_sources(root); _require(source["status"]=="validated","goal041_source_gate_failed"); gates["sources"]="validated"
        pilot_path=root/METADATA_ROOT/"goal041_pilot_equivalence.json"; _require(pilot_path.is_file(),"goal041_pilot_gate_missing"); pilot=json.loads(pilot_path.read_text()); expected_corrections={"soil_order":sha256(root/METADATA_ROOT/"goal041_soil_correction_receipt.json"),"nvis_mvg":sha256(root/METADATA_ROOT/"goal041_nvis_correction_receipt.json")}; _require(pilot.get("status")=="validated" and pilot.get("cells")==128 and pilot.get("exact")==128 and pilot.get("failed")==0 and pilot.get("run_identity")==run_identity(root) and pilot.get("correction_receipt_sha256")==expected_corrections,"goal041_pilot_gate_failed"); gates["pilot"]="validated"
        validate_benchmark(root); gates["benchmark"]="validated"
        table=validate_table(root); gates["table"]="validated"
        diagnostics_path=root/METADATA_ROOT/"goal041_diagnostics.json"; _require(diagnostics_path.is_file(),"goal041_diagnostics_missing"); diagnostics=json.loads(diagnostics_path.read_text()); assert_metadata_privacy(diagnostics)
        status,reasons,per_predictor=_assess_diagnostics(root,diagnostics); gates["diagnostics"]="validated" if status=="ready" else "repair"
        evidence=_validate_provenance_receipts(root,table,diagnostics); gates["provenance"]="validated"
        decision={"schema_version":"goal041-decision-v2","status":status,"run_identity":run_identity(root),"table_sha256":table["sha256"],"diagnostics_sha256":sha256(diagnostics_path),"evidence_receipt_sha256":evidence,"reasons":reasons,"gates":gates,"per_predictor":per_predictor,"limitations":["Tasmania extrapolation is descriptive and not an automatic failure","WorldClim nodata is a dispersed coastal centroid/source-mask footprint, not a coherent unexplained gap","ALUM source-native code 62 maps to both 6.0 Water and 6.2 Reservoir/dam labels; full code:label strings remain distinct"]}
        _write_json(root,"goal041_decision_receipt.json",decision)
        return {"status":status,"table":table,"gates":gates,"reasons":reasons}
    except Goal041Error as exc:
        reason=str(exc); blocked={name:{"status":"blocked","reasons":[reason]} for name in PREDICTORS}; gates["terminal"]="blocked"
        _write_json(root,"goal041_decision_receipt.json",{"schema_version":"goal041-decision-v2","status":"blocked","reasons":[reason],"gates":gates,"per_predictor":blocked,"limitations":["Tasmania extrapolation is descriptive and not an automatic failure"]})
        raise


def main(argv: Sequence[str]|None=None) -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("stage",choices=("validate-contract","acquire","validate-sources","prepare-pilot-baselines","pilot-equivalence","benchmark","validate-benchmark","elevation-tile-manifest","extract","validate-table","diagnose","worldclim-missingness","validate")); parser.add_argument("--root",type=Path,default=Path(".")); args=parser.parse_args(argv); root=args.root.resolve()
    result={"validate-contract":validate_contract,"acquire":acquire,"validate-sources":validate_sources,"prepare-pilot-baselines":prepare_pilot_baselines,"pilot-equivalence":pilot_equivalence_stage,"benchmark":run_benchmark,"validate-benchmark":validate_benchmark,"elevation-tile-manifest":build_elevation_tile_manifest,"extract":extract_chunks,"validate-table":validate_table,"diagnose":diagnose,"worldclim-missingness":build_worldclim_missingness_receipt,"validate":validate}[args.stage](root); print(json.dumps(result,indent=2,sort_keys=True))


__all__=["Goal041Error","SourceMissing","CONTINUOUS","CATEGORICAL","PREDICTORS","OUTPUT_FIELDS","cell_bounds","ledger_indices","production_block_key","production_block_bounds","block_cell_offset","mode_low_code","continuous_summary","summarize_raster_cell","centroid_value","reshape_wcs_tile","block_centroid_values","block_raster_summaries","iter_tiles","map_alum_secondary","alum_mode_then_secondary","pilot_equivalent","diagnose_rows","assert_metadata_privacy","acquire","validate_sources","prepare_pilot_baselines","run_benchmark","validate_benchmark","BlockProcessor","extract_chunks","pilot_equivalence_stage","diagnose","validate_contract","validate_table","validate","main"]


if __name__ == "__main__": main()
