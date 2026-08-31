"""Extend the Goal 041 predictor substrate to the complete BBS domain.

This module deliberately has no response or occurrence-data dependency.  It
adds only the 18,961 BBS cells absent from Goal 041, using the same source
semantics and schema.  Network payloads and intermediate tables are private;
the CLI is resumable so a long acquisition can run safely under ``tmux``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from dsdm_phase1 import goal041_predictor_substrate as goal041

try:
    import rasterio
    from rasterio.io import MemoryFile
except ImportError:  # pragma: no cover
    rasterio = None
    MemoryFile = None


ROOT_PRIVATE = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/predictors")
DOMAIN = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/domain_cells.csv")
OLD_TABLE = Path("data/raw/goal041/predictor_substrate.parquet")
WORLDCLIM_DIR = Path("data/raw/goal041/worldclim")
LOCAL_SOURCE_DIR = Path("data/raw/goal041")
OUTPUT_NAME = "predictor_substrate.parquet"
SCHEMA_VERSION = "goal048-predictor-extension-v1"
WORLDCLIM_ORIGIN_LON = -179.9958333333333
WORLDCLIM_ORIGIN_LAT = 89.9958333333333
WORLDCLIM_STEP = 1.0 / 120.0
EXPECTED_OLD_ROWS = 1_125_325
EXPECTED_ADDED_ROWS = 18_961
EXPECTED_NEW_TOTAL = EXPECTED_OLD_ROWS + EXPECTED_ADDED_ROWS
EXPECTED_ELEVATION_BLOCKS = 29
WORLDCLIM_LAYERS = tuple(f"bio{i:02d}" for i in range(1, 20))


class ExtensionError(ValueError):
    """Fail-closed extension contract error."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ExtensionError(reason)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    _require(not partial.exists(), f"orphaned_partial:{partial.name}")
    partial.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    partial.replace(path)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    _require(not partial.exists(), f"orphaned_partial:{partial.name}")
    with partial.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    partial.replace(path)


def _read_domain(root: Path) -> list[dict[str, str]]:
    path = root / DOMAIN
    _require(path.is_file(), "goal048_domain_cells_missing")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require(reader.fieldnames == ["cell_id", "row", "column", "longitude", "latitude"], "goal048_domain_schema_drift")
        rows = list(reader)
    _require(
        rows and set(rows[0]) == {"cell_id", "row", "column", "longitude", "latitude"},
        "goal048_domain_schema_drift",
    )
    _require([row["cell_id"] for row in rows] == sorted(row["cell_id"] for row in rows), "goal048_domain_order_drift")
    _require(len(rows) == EXPECTED_NEW_TOTAL, "goal048_domain_count_drift")
    return rows


def _old_ids(root: Path) -> list[str]:
    import pyarrow.parquet as pq

    path = root / OLD_TABLE
    _require(path.is_file(), "goal041_predictor_table_missing")
    ids = pq.read_table(path, columns=["cell_id"]).column("cell_id").to_pylist()
    _require(len(ids) == EXPECTED_OLD_ROWS and ids == sorted(ids) and len(ids) == len(set(ids)), "goal041_old_table_identity_drift")
    return [str(value) for value in ids]


def added_cells(root: Path) -> list[dict[str, Any]]:
    """Return exactly the BBS cells not present in the Goal041 authority."""
    rows = _read_domain(root)
    freeze_path = root / "data/processed/dsdm/goal048-seawfb-bioregional-freeze/domain_freeze.json"
    if freeze_path.is_file():
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        _require(freeze.get("cell_count") == EXPECTED_NEW_TOTAL and freeze.get("added_complete_bbs_cells") == EXPECTED_ADDED_ROWS, "goal048_domain_receipt_drift")
    old = set(_old_ids(root))
    added = [row for row in rows if row["cell_id"] not in old]
    _require(len(added) == EXPECTED_ADDED_ROWS, "goal048_added_cell_count_drift")
    _require(all(row["cell_id"].startswith("r") for row in added), "goal048_added_cell_id_drift")
    _require(len({row["cell_id"] for row in added}) == len(added), "goal048_added_cell_duplicates")
    _require(len({(row["row"], row["column"]) for row in added}) == len(added), "goal048_added_grid_duplicates")
    return [
        {
            "cell_id": str(row["cell_id"]),
            "row_south_to_north": int(row["row"]),
            "column_west_to_east": int(row["column"]),
            "longitude": float(row["longitude"]),
            "latitude": float(row["latitude"]),
            "region": "southeast_mainland",
        }
        for row in added
    ]


def native_grid_window(cells: Sequence[Mapping[str, Any]], *, origin_lon: float = WORLDCLIM_ORIGIN_LON, origin_lat: float = WORLDCLIM_ORIGIN_LAT, step: float = WORLDCLIM_STEP) -> dict[str, Any]:
    """Derive an inclusive native-grid window from cell centres."""
    _require(cells, "empty_worldclim_window")
    columns: list[int] = []
    rows: list[int] = []
    for cell in cells:
        colf = (float(cell["longitude"]) - origin_lon) / step
        rowf = (origin_lat - float(cell["latitude"])) / step
        _require(math.isfinite(colf) and math.isfinite(rowf), "worldclim_native_grid_misalignment")
        # Goal041 nudges longitude east at native-pixel boundaries.  Half-up
        # rounding reproduces that deterministic choice for crop selection.
        col, row = math.floor(colf + 0.5 + 1e-10), math.floor(rowf + 0.5 + 1e-10)
        columns.append(col)
        rows.append(row)
    col0, col1, row0, row1 = min(columns), max(columns), min(rows), max(rows)
    _require(col0 >= 0 and row0 >= 0, "worldclim_window_outside_global_grid")
    return {
        "column_min": col0,
        "column_max": col1,
        "row_min": row0,
        "row_max": row1,
        "width": col1 - col0 + 1,
        "height": row1 - row0 + 1,
        "west_center": origin_lon + col0 * step,
        "east_center": origin_lon + col1 * step,
        "south_center": origin_lat - row1 * step,
        "north_center": origin_lat - row0 * step,
        "maximum_center_offset_pixels": max(
            max(
                abs((float(cell["longitude"]) - origin_lon) / step - math.floor((float(cell["longitude"]) - origin_lon) / step + 0.5 + 1e-10)),
                abs((origin_lat - float(cell["latitude"])) / step - math.floor((origin_lat - float(cell["latitude"])) / step + 0.5 + 1e-10)),
            )
            for cell in cells
        ),
    }


def expected_native_transform(window: Mapping[str, Any]):
    _require(rasterio is not None, "rasterio_unavailable")
    return rasterio.transform.from_origin(
        float(window["west_center"]) - WORLDCLIM_STEP / 2,
        float(window["north_center"]) + WORLDCLIM_STEP / 2,
        WORLDCLIM_STEP,
        WORLDCLIM_STEP,
    )


def validate_native_dataset(dataset: Any, window: Mapping[str, Any]) -> None:
    """Validate shape, CRS, and transform before any values are trusted."""
    _require((dataset.width, dataset.height) == (window["width"], window["height"]), "worldclim_native_shape_drift")
    _require(str(dataset.crs) == "EPSG:4326", "worldclim_native_crs_drift")
    expected = expected_native_transform(window)
    actual = dataset.transform
    _require(
        all(abs(float(a) - float(b)) <= 1e-10 for a, b in zip(actual[:6], expected[:6])),
        "worldclim_native_transform_drift",
    )


def _worldclim_query(url: str, coverage: str, window: Mapping[str, Any]) -> bytes:
    query = urlencode(
        [
            ("SERVICE", "WCS"),
            ("VERSION", "2.0.1"),
            ("REQUEST", "GetCoverage"),
            ("COVERAGEID", coverage),
            # ALA's trim endpoint is lower-inclusive/upper-exclusive.  Move
            # only the upper coordinate by one native pixel so the requested
            # maximum centre is retained without resampling.
            ("SUBSET", f"Long({window['west_center']},{float(window['east_center']) + WORLDCLIM_STEP})"),
            ("SUBSET", f"Lat({float(window['south_center'])},{float(window['north_center']) + WORLDCLIM_STEP})"),
            ("FORMAT", "image/tiff"),
        ]
    )
    request = Request(url + "?" + query, headers={"Accept": "image/tiff", "User-Agent": "dSDM-Goal048/1.0"})
    with urlopen(request, timeout=600) as response:
        payload = response.read()
    _require(payload and not payload.lstrip().startswith(b"<"), "worldclim_wcs_service_error")
    return payload


def _goal041_identity(root: Path) -> str:
    return goal041.run_identity(root)


def extension_run_identity(root: Path) -> str:
    """Bind every resumable artefact to the complete immutable input set."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "script_sha256": _sha256(Path(__file__)),
        "goal041_config_sha256": _sha256(root / "config/goal041_predictor_substrate.json"),
        "goal048_config_sha256": _sha256(root / "config/goal048_seawfb_bioregional_freeze.json"),
        "domain_sha256": _sha256(root / DOMAIN),
        "old_table_sha256": _sha256(root / OLD_TABLE),
        "source_manifest_sha256": _sha256(root / "metadata/goal041_source_manifest.json"),
    }
    return _digest(payload)


def _source_identity(root: Path, layer: str, window: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    config = goal041._config(root)
    source = config["sources"]["worldclim" if kind == "worldclim" else "elevation"]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "layer": layer,
        "window": dict(window),
        "source": source,
        "goal041_run_identity": _goal041_identity(root),
        "extension_run_identity": extension_run_identity(root),
        "extension_code_sha256": _sha256(Path(__file__)),
        "grid": {"origin_lon": WORLDCLIM_ORIGIN_LON, "origin_lat": WORLDCLIM_ORIGIN_LAT, "step": WORLDCLIM_STEP} if kind == "worldclim" else {"pixels_per_cell": 36, "shape": [1800, 1800]},
    }


def _cache_pair(path: Path, receipt: Path, identity: Mapping[str, Any], expected_shape: tuple[int, int], *, window: Mapping[str, Any] | None = None) -> Path:
    _require(path.is_file() and receipt.is_file(), "predictor_cache_pair_missing")
    record = json.loads(receipt.read_text(encoding="utf-8"))
    _require(record.get("identity") == identity and record.get("sha256") == _sha256(path), "predictor_cache_identity_conflict")
    with rasterio.open(path) as dataset:
        _require((dataset.height, dataset.width) == expected_shape and str(dataset.crs) == "EPSG:4326", "predictor_cache_shape_crs_conflict")
        if window is not None:
            validate_native_dataset(dataset, window)
    return path


def _store_raster_cache(path: Path, payload: bytes, identity: Mapping[str, Any], expected_shape: tuple[int, int], *, window: Mapping[str, Any] | None = None) -> Path:
    receipt = path.with_suffix(".json")
    if path.exists() or receipt.exists():
        return _cache_pair(path, receipt, identity, expected_shape, window=window)
    _require(rasterio is not None and MemoryFile is not None, "rasterio_unavailable")
    memory = MemoryFile(payload)
    try:
        with memory.open() as dataset:
            _require((dataset.height, dataset.width) == expected_shape and str(dataset.crs) == "EPSG:4326", "predictor_service_shape_crs_drift")
            if window is not None:
                validate_native_dataset(dataset, window)
    finally:
        memory.close()
    _write_bytes_atomic(path, payload)
    _write_json_atomic(receipt, {"identity": dict(identity), "sha256": _sha256(path)})
    return _cache_pair(path, receipt, identity, expected_shape)


def acquire_worldclim(root: Path, cells: Sequence[Mapping[str, Any]], *, layers: Sequence[str] | None = None, canary: bool = False, cache_dir: str = "worldclim") -> dict[str, Any]:
    """Acquire native-grid WCS crops and verify a local overlap."""
    _require(rasterio is not None, "rasterio_unavailable")
    config = goal041._config(root)
    window = native_grid_window(cells)
    selected = tuple(layers or WORLDCLIM_LAYERS)
    if canary:
        selected = selected[:1]
    result: dict[str, Any] = {"window": window, "layers": []}
    for layer in selected:
        identity = _source_identity(root, layer, window, kind="worldclim")
        path = root / ROOT_PRIVATE / cache_dir / f"{layer}.tif"
        if path.exists() or path.with_suffix(".json").exists():
            _cache_pair(path, path.with_suffix(".json"), identity, (window["height"], window["width"]), window=window)
        else:
            payload = _worldclim_query(config["sources"]["worldclim"]["url"], f"ALA__worldclim21_{layer[0:3]}{int(layer[3:]):d}", window)
            _store_raster_cache(path, payload, identity, (window["height"], window["width"]), window=window)
        result["layers"].append(layer)
    return result


def validate_worldclim_overlap(root: Path, cells: Sequence[Mapping[str, Any]], window: Mapping[str, Any], *, layers: Sequence[str] | None = None, cache_dir: str = "worldclim", sample_limit: int | None = None) -> dict[str, Any]:
    """Compare native crop and local Goal041 rasters at deterministic cells."""
    overlap = [cell for cell in cells if float(cell["latitude"]) < -23.775 + 1e-9]
    _require(overlap, "worldclim_overlap_empty")
    overlap = sorted(overlap, key=lambda value: str(value["cell_id"]))
    if sample_limit is not None and len(overlap) > sample_limit:
        indices = np.linspace(0, len(overlap) - 1, sample_limit, dtype=int)
        overlap = [overlap[index] for index in indices]
    selected = tuple(layers or WORLDCLIM_LAYERS)
    failures: list[str] = []
    compared = 0
    for layer in selected:
        local_path = root / WORLDCLIM_DIR / f"{layer}.tif"
        native_path = root / ROOT_PRIVATE / cache_dir / f"{layer}.tif"
        _require(local_path.is_file() and native_path.is_file(), "worldclim_overlap_asset_missing")
        with rasterio.open(local_path) as local, rasterio.open(native_path) as native:
            validate_native_dataset(native, window)
            local_values = local.read(1)
            native_values = native.read(1)
            for cell in overlap:
                x, y = float(cell["longitude"]) + 1e-10, float(cell["latitude"])
                li, lj = local.index(x, y)
                ni, nj = native.index(x, y)
                if not (0 <= li < local.height and 0 <= lj < local.width and 0 <= ni < native.height and 0 <= nj < native.width):
                    continue
                lv = local_values[li, lj]
                nv = native_values[ni, nj]
                if local.nodata is not None and lv == local.nodata:
                    continue
                if native.nodata is not None and nv == native.nodata:
                    continue
                compared += 1
                if not np.isclose(np.float32(lv), np.float32(nv), rtol=0, atol=max(abs(float(np.spacing(np.float32(nv)))), 1e-7)):
                    failures.append(f"{layer}:{cell['cell_id']}")
    _require(not failures, "worldclim_overlap_value_drift")
    return {"status": "validated", "overlap_cells": len(overlap), "compared_values": compared, "layers": len(selected), "sample_limit": sample_limit}


def missing_elevation_blocks(cells: Sequence[Mapping[str, Any]]) -> list[tuple[int, int]]:
    blocks = sorted({goal041.production_block_key(cell) for cell in cells})
    _require(len(blocks) == EXPECTED_ELEVATION_BLOCKS, "goal048_elevation_block_count_drift")
    return blocks


def acquire_elevation_block(root: Path, block: tuple[int, int], *, canary: bool = False, cache_dir: str = "elevation") -> Path:
    _require(rasterio is not None, "rasterio_unavailable")
    config = goal041._config(root)
    window = {"block": list(block), "bbox": list(goal041.production_block_bounds(block)), "width": 1800, "height": 1800}
    identity = _source_identity(root, "elevation", window, kind="elevation")
    path = root / ROOT_PRIVATE / cache_dir / f"r{block[0]:04d}_c{block[1]:04d}.tif"
    if path.exists() or path.with_suffix(".json").exists():
        return _cache_pair(path, path.with_suffix(".json"), identity, (1800, 1800))
    payload = goal041.wcs_request(config["sources"]["elevation"]["url"], coverage=config["sources"]["elevation"]["coverage"], bbox=tuple(window["bbox"]), width=1800, height=1800, version="1.0.0")
    return _store_raster_cache(path, payload, identity, (1800, 1800))


def _categorical_sources(root: Path):
    _require(rasterio is not None, "rasterio_unavailable")
    nvis = rasterio.open(root / LOCAL_SOURCE_DIR / "nvis_mvg.tif")
    soil = rasterio.open(root / LOCAL_SOURCE_DIR / "soil_order/ASC_EV_C_P_AU_TRN_N.cog.tif")
    alum = rasterio.open(root / LOCAL_SOURCE_DIR / "alum/alum.tif")
    labels = json.loads((root / LOCAL_SOURCE_DIR / "alum/alum_labels.json").read_text(encoding="utf-8"))
    nvis_labels = goal041._nvis_rat(root / LOCAL_SOURCE_DIR / "nvis_mvg.tif")
    return nvis, soil, alum, labels, nvis_labels


def extract_block(root: Path, block: tuple[int, int], cells: Sequence[Mapping[str, Any]], climate: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract one BBS block using Goal041 aggregation semantics."""
    result = {str(cell["cell_id"]): {"cell_id": str(cell["cell_id"]), "region": "southeast_mainland"} for cell in cells}
    for layer in WORLDCLIM_LAYERS:
        with rasterio.open(root / ROOT_PRIVATE / "worldclim" / f"{layer}.tif") as dataset:
            raster_values = dataset.read(1, masked=True)
            values = {}
            for cell in cells:
                row, col = dataset.index(float(cell["longitude"]) + 1e-10, float(cell["latitude"]))
                _require(0 <= row < dataset.height and 0 <= col < dataset.width, "worldclim_cell_outside_crop")
                value = raster_values[row, col]
                values[str(cell["cell_id"])] = None if np.ma.is_masked(value) else float(np.float32(value))
            for cid, value in values.items():
                result[cid][layer] = value
    elevation_path = acquire_elevation_block(root, block)
    nvis, soil, alum, alum_labels, nvis_labels = _categorical_sources(root)
    try:
        with rasterio.open(elevation_path) as elevation:
            elev = goal041.wcs_block_summaries(elevation, cells, pixels_per_cell=36, categorical=False)
        soil_values = goal041.block_raster_summaries(soil, cells, categorical=True)
        nvis_values = goal041.block_raster_summaries(nvis, cells, categorical=True)
        alum_values = goal041.block_raster_summaries(alum, cells, categorical=True)
        for cid in result:
            summary = elev.get(cid)
            result[cid]["elevation_mean"] = summary[0] if summary else None
            result[cid]["elevation_sd"] = summary[1] if summary else None
            result[cid]["soil_order"] = None if soil_values.get(cid) is None else goal041.canonical_soil_code(soil_values[cid])
            raw_nvis = goal041.canonical_numeric_code(nvis_values.get(cid))
            result[cid]["nvis_mvg"] = nvis_labels.get(raw_nvis, raw_nvis)
            raw_alum = alum_values.get(cid)
            result[cid]["alum_secondary"] = goal041.map_alum_secondary(raw_alum, alum_labels)
            _require(raw_alum is None or result[cid]["alum_secondary"] is not None, "alum_code_missing_from_lookup")
    finally:
        nvis.close(); soil.close(); alum.close()
    return [result[cid] for cid in sorted(result)]


def _output_schema(root: Path):
    import pyarrow.parquet as pq
    schema = pq.read_schema(root / OLD_TABLE)
    _require(schema.names == goal041.OUTPUT_FIELDS, "goal041_old_table_schema_drift")
    return schema


def _write_block(root: Path, block: tuple[int, int], rows: Sequence[Mapping[str, Any]], schema: Any, run_identity: str) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = root / ROOT_PRIVATE / "blocks" / f"r{block[0]:04d}_c{block[1]:04d}.parquet"
    receipt = path.with_suffix(".json")
    expected_ids = [str(row["cell_id"]) for row in rows]
    if path.exists() or receipt.exists():
        _require(path.is_file() and receipt.is_file(), "extension_block_pair_missing")
        existing = pq.read_table(path, columns=["cell_id"]).column("cell_id").to_pylist()
        record = json.loads(receipt.read_text(encoding="utf-8"))
        _require(existing == expected_ids and record.get("sha256") == _sha256(path) and record.get("ids") == expected_ids and record.get("run_identity") == run_identity, "extension_block_receipt_conflict")
        return path
    table = pa.Table.from_pylist([{name: row.get(name) for name in schema.names} for row in rows], schema=schema)
    partial = path.with_name(path.name + ".part"); _require(not partial.exists(), "extension_block_partial_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, partial, compression="zstd")
    partial.replace(path)
    _write_json_atomic(receipt, {"schema_version": SCHEMA_VERSION, "block": list(block), "rows": len(rows), "ids": expected_ids, "sha256": _sha256(path), "run_identity": run_identity})
    return path


def _progress_path(root: Path) -> Path:
    return root / ROOT_PRIVATE / "extension_progress.json"


def run(root: Path) -> dict[str, Any]:
    import pyarrow as pa
    import pyarrow.parquet as pq
    cells = added_cells(root)
    window = native_grid_window(cells)
    run_id = extension_run_identity(root)
    progress_path = _progress_path(root)
    if progress_path.is_file():
        previous = json.loads(progress_path.read_text(encoding="utf-8"))
        _require(previous.get("run_identity") == run_id, "extension_progress_identity_conflict")
    acquire_worldclim(root, cells)
    overlap = validate_worldclim_overlap(root, cells, window)
    overlap_receipt = {**overlap, "run_identity": run_id, "window": window}
    overlap_path = root / ROOT_PRIVATE / "worldclim_overlap.json"
    _write_json_atomic(overlap_path, overlap_receipt)
    overlap_sha256 = _sha256(overlap_path)
    climate = {"window": window}
    by_block: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for cell in cells:
        by_block.setdefault(goal041.production_block_key(cell), []).append(cell)
    schema = _output_schema(root)
    completed: list[list[int]] = []
    for block in sorted(by_block):
        block_path = root / ROOT_PRIVATE / "blocks" / f"r{block[0]:04d}_c{block[1]:04d}.parquet"
        block_receipt = block_path.with_suffix(".json")
        if block_path.exists() or block_receipt.exists():
            _require(block_path.is_file() and block_receipt.is_file(), "extension_block_pair_missing")
            record = json.loads(block_receipt.read_text(encoding="utf-8"))
            expected_ids = [str(cell["cell_id"]) for cell in by_block[block]]
            _require(record.get("run_identity") == run_id and record.get("ids") == expected_ids and record.get("sha256") == _sha256(block_path), "extension_block_receipt_conflict")
            completed.append(list(block))
            continue
        rows = extract_block(root, block, by_block[block], climate)
        _write_block(root, block, rows, schema, run_id)
        completed.append(list(block))
        _write_json_atomic(progress_path, {"schema_version": SCHEMA_VERSION, "status": "running", "run_identity": run_id, "completed_blocks": completed, "total_blocks": len(by_block), "rows": sum(len(by_block[tuple(value)]) for value in completed)})
    block_tables = [pq.read_table(root / ROOT_PRIVATE / "blocks" / f"r{b[0]:04d}_c{b[1]:04d}.parquet") for b in sorted(by_block)]
    added = pa.concat_tables(block_tables, promote_options="default")
    old = pq.read_table(root / OLD_TABLE)
    combined = pa.concat_tables([old, added], promote_options="default")
    import pyarrow.compute as pc
    order = pc.sort_indices(combined, sort_keys=[("cell_id", "ascending")])
    combined = pc.take(combined, order)
    output = root / ROOT_PRIVATE / OUTPUT_NAME
    partial = output.with_name(output.name + ".part"); _require(not partial.exists(), "extension_output_partial_exists")
    output.parent.mkdir(parents=True, exist_ok=True); pq.write_table(combined, partial, compression="zstd"); partial.replace(output)
    result = {"status": "complete", "rows": combined.num_rows, "added_rows": added.num_rows, "sha256": _sha256(output), "output": str(output.relative_to(root))}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "source": {
            "goal041_run_identity": _goal041_identity(root),
            "goal041_config_sha256": _sha256(root / "config/goal041_predictor_substrate.json"),
            "goal041_source_manifest_sha256": _sha256(root / "metadata/goal041_source_manifest.json"),
            "goal041_table_sha256": _sha256(root / OLD_TABLE),
            "goal048_domain_sha256": _sha256(root / DOMAIN),
        },
        "output": {"path": str(output.relative_to(root)), "sha256": result["sha256"], "rows": combined.num_rows, "added_rows": added.num_rows},
        "run_identity": run_id,
        "blocks": [{"block": list(block), "path": str((root / ROOT_PRIVATE / "blocks" / f"r{block[0]:04d}_c{block[1]:04d}.parquet").relative_to(root)), "sha256": _sha256(root / ROOT_PRIVATE / "blocks" / f"r{block[0]:04d}_c{block[1]:04d}.parquet"), "receipt_sha256": _sha256(root / ROOT_PRIVATE / "blocks" / f"r{block[0]:04d}_c{block[1]:04d}.json"), "run_identity": run_id} for block in sorted(by_block)],
        "worldclim": [{"layer": layer, "path": str((root / ROOT_PRIVATE / "worldclim" / f"{layer}.tif").relative_to(root)), "sha256": _sha256(root / ROOT_PRIVATE / "worldclim" / f"{layer}.tif"), "receipt_path": str((root / ROOT_PRIVATE / "worldclim" / f"{layer}.json").relative_to(root)), "receipt_sha256": _sha256(root / ROOT_PRIVATE / "worldclim" / f"{layer}.json")} for layer in WORLDCLIM_LAYERS],
        "elevation": [{"block": list(block), "path": str((root / ROOT_PRIVATE / "elevation" / f"r{block[0]:04d}_c{block[1]:04d}.tif").relative_to(root)), "sha256": _sha256(root / ROOT_PRIVATE / "elevation" / f"r{block[0]:04d}_c{block[1]:04d}.tif"), "receipt_path": str((root / ROOT_PRIVATE / "elevation" / f"r{block[0]:04d}_c{block[1]:04d}.json").relative_to(root)), "receipt_sha256": _sha256(root / ROOT_PRIVATE / "elevation" / f"r{block[0]:04d}_c{block[1]:04d}.json")} for block in missing_elevation_blocks(cells)],
        "worldclim_overlap": {"path": str(overlap_path.relative_to(root)), "sha256": overlap_sha256, "result": overlap},
        "predictors": list(goal041.PREDICTORS),
        "response_inputs_read": 0,
    }
    _write_json_atomic(root / ROOT_PRIVATE / "extension_manifest.json", manifest)
    _write_json_atomic(progress_path, {**result, "schema_version": SCHEMA_VERSION, "run_identity": run_id, "completed_blocks": [list(b) for b in sorted(by_block)]})
    return result


def preflight(root: Path) -> dict[str, Any]:
    cells = added_cells(root)
    blocks = missing_elevation_blocks(cells)
    return {"status": "ready", "added_cells": len(cells), "elevation_blocks": len(blocks), "worldclim_window": native_grid_window(cells), "response_inputs_read": 0}


def canary(root: Path) -> dict[str, Any]:
    cells = added_cells(root)
    window = native_grid_window(cells)
    acquire_worldclim(root, cells, layers=("bio01",), canary=True, cache_dir="canary_worldclim")
    overlap = validate_worldclim_overlap(root, cells, window, layers=("bio01",), cache_dir="canary_worldclim", sample_limit=256)
    acquire_elevation_block(root, missing_elevation_blocks(cells)[0], canary=True, cache_dir="canary_elevation")
    return {"status": "passed", "worldclim_requests": 1, "elevation_requests": 1, "worldclim_window": window, "overlap": overlap, "full_extension": False, "response_inputs_read": 0}


def status(root: Path) -> dict[str, Any]:
    path = _progress_path(root)
    if not path.is_file():
        return {"status": "not_started", "response_inputs_read": 0}
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("run_identity"):
        _require(result["run_identity"] == extension_run_identity(root), "extension_progress_identity_conflict")
    return result


def validate(root: Path) -> dict[str, Any]:
    import pyarrow as pa
    import pyarrow.parquet as pq
    cells = added_cells(root)
    output = root / ROOT_PRIVATE / OUTPUT_NAME
    _require(output.is_file(), "extension_output_missing")
    manifest_path = root / ROOT_PRIVATE / "extension_manifest.json"
    _require(manifest_path.is_file(), "extension_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(manifest.get("schema_version") == SCHEMA_VERSION and manifest.get("response_inputs_read") == 0, "extension_manifest_contract_drift")
    run_id = extension_run_identity(root)
    _require(manifest.get("run_identity") == run_id, "extension_manifest_identity_conflict")
    source = manifest.get("source", {})
    _require(
        source.get("goal041_run_identity") == _goal041_identity(root)
        and source.get("goal041_config_sha256") == _sha256(root / "config/goal041_predictor_substrate.json")
        and source.get("goal041_source_manifest_sha256") == _sha256(root / "metadata/goal041_source_manifest.json")
        and source.get("goal041_table_sha256") == _sha256(root / OLD_TABLE)
        and source.get("goal048_domain_sha256") == _sha256(root / DOMAIN),
        "extension_source_receipt_drift",
    )
    _require(manifest.get("output", {}).get("sha256") == _sha256(output), "extension_output_checksum_drift")
    _require(manifest.get("output", {}).get("path") == str(output.relative_to(root)) and manifest.get("output", {}).get("rows") == EXPECTED_NEW_TOTAL and manifest.get("output", {}).get("added_rows") == EXPECTED_ADDED_ROWS, "extension_output_manifest_drift")
    table = pq.read_table(output)
    old = pq.read_table(root / OLD_TABLE)
    _require(table.schema.equals(old.schema, check_metadata=False), "extension_schema_drift")
    ids = table.column("cell_id").to_pylist()
    _require(len(ids) == EXPECTED_NEW_TOTAL and ids == sorted(ids) and len(ids) == len(set(ids)), "extension_identity_drift")
    old_ids = old.column("cell_id").to_pylist()
    old_index = {str(value): i for i, value in enumerate(ids)}
    actual_added = [str(cell["cell_id"]) for cell in cells]
    _require(actual_added == sorted(actual_added) and set(actual_added) == set(ids) - set(old_ids), "extension_added_ids_drift")
    old_positions = pa.array([old_index[str(cid)] for cid in old_ids], type=pa.int64())
    old_reordered = table.take(old_positions)
    for name in old.schema.names:
        _require(old.column(name).to_pylist() == old_reordered.column(name).to_pylist(), f"old_row_changed:{name}")
    expected_window = native_grid_window(cells)
    overlap_entry = manifest.get("worldclim_overlap", {})
    overlap_path = root / overlap_entry.get("path", "")
    _require(overlap_path.is_file() and overlap_entry.get("sha256") == _sha256(overlap_path), "extension_overlap_receipt_drift")
    overlap_receipt = json.loads(overlap_path.read_text(encoding="utf-8"))
    _require(overlap_receipt.get("status") == "validated" and overlap_receipt.get("run_identity") == run_id and overlap_receipt.get("window") == expected_window and overlap_entry.get("result") == {key: overlap_receipt.get(key) for key in ("status", "overlap_cells", "compared_values", "layers", "sample_limit")}, "extension_overlap_contract_drift")
    expected_blocks = {tuple(goal041.production_block_key(cell)) for cell in cells}
    blocks = manifest.get("blocks", [])
    _require(len(blocks) == len(expected_blocks) == EXPECTED_ELEVATION_BLOCKS and {tuple(entry.get("block", [])) for entry in blocks} == expected_blocks, "extension_block_manifest_count_drift")
    for entry in blocks:
        block_path = root / entry["path"]
        receipt_path = block_path.with_suffix(".json")
        _require(block_path.is_file() and receipt_path.is_file() and entry.get("sha256") == _sha256(block_path) and entry.get("receipt_sha256") == _sha256(receipt_path), "extension_block_checksum_drift")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        _require(receipt.get("run_identity") == run_id and receipt.get("block") == entry["block"] and receipt.get("sha256") == entry["sha256"], "extension_block_identity_drift")
    worldclim_entries = manifest.get("worldclim", [])
    _require(len(worldclim_entries) == len(WORLDCLIM_LAYERS) and {entry.get("layer") for entry in worldclim_entries} == set(WORLDCLIM_LAYERS), "extension_worldclim_manifest_drift")
    for entry in worldclim_entries:
        layer = entry["layer"]
        path = root / entry["path"]
        receipt_path = root / entry["receipt_path"]
        _require(path.is_file() and receipt_path.is_file() and entry.get("sha256") == _sha256(path) and entry.get("receipt_sha256") == _sha256(receipt_path), "extension_worldclim_checksum_drift")
        _cache_pair(path, receipt_path, _source_identity(root, layer, expected_window, kind="worldclim"), (expected_window["height"], expected_window["width"]), window=expected_window)
    elevation_entries = manifest.get("elevation", [])
    _require(len(elevation_entries) == len(expected_blocks) and {tuple(entry.get("block", [])) for entry in elevation_entries} == expected_blocks, "extension_elevation_manifest_drift")
    for entry in elevation_entries:
        block = tuple(entry["block"])
        path = root / entry["path"]
        receipt_path = root / entry["receipt_path"]
        _require(path.is_file() and receipt_path.is_file() and entry.get("sha256") == _sha256(path) and entry.get("receipt_sha256") == _sha256(receipt_path), "extension_elevation_checksum_drift")
        elevation_window = {"block": list(block), "bbox": list(goal041.production_block_bounds(block)), "width": 1800, "height": 1800}
        _cache_pair(path, receipt_path, _source_identity(root, "elevation", elevation_window, kind="elevation"), (1800, 1800))
    _require(manifest.get("predictors") == list(goal041.PREDICTORS), "extension_predictor_manifest_drift")
    missing = {name: sum(value is None for value in table.column(name).to_pylist()) for name in goal041.PREDICTORS}
    return {"status": "validated", "rows": table.num_rows, "added_rows": len(actual_added), "sha256": _sha256(output), "missingness": missing, "response_inputs_read": 0}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preflight", "canary", "run", "status", "validate"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = {"preflight": preflight, "canary": canary, "run": run, "status": status, "validate": validate}[args.stage](args.root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
