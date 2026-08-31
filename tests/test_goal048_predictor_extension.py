from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

import importlib.util


SCRIPT = Path(__file__).parents[1] / "scripts" / "goal048_predictor_extension.py"
SPEC = importlib.util.spec_from_file_location("goal048_predictor_extension", SCRIPT)
ext = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ext)


def cell(cell_id="r1360c1201", row=1360, column=1201, lon=147.385, lat=-30.0275):
    return {"cell_id": cell_id, "row_south_to_north": row, "column_west_to_east": column, "longitude": lon, "latitude": lat, "region": "southeast_mainland"}


def test_native_grid_window_is_inclusive_and_aligned():
    window = ext.native_grid_window([cell()])
    assert window["width"] == 1
    assert window["height"] == 1
    assert window["column_min"] == window["column_max"]
    assert window["row_min"] == window["row_max"]
    assert window["west_center"] == pytest.approx(147.3875)
    with pytest.raises(ext.ExtensionError, match="misalignment"):
        ext.native_grid_window([cell(lon=float("nan"))])


def test_native_dataset_shape_transform_and_crs_gate():
    window = ext.native_grid_window([cell()])
    transform = ext.expected_native_transform(window)
    profile = {"driver": "GTiff", "width": 1, "height": 1, "count": 1, "dtype": "float32", "crs": "EPSG:4326", "transform": transform}
    with MemoryFile() as memory:
        with memory.open(**profile) as dataset:
            dataset.write(np.ones((1, 1), dtype="float32"), 1)
        with memory.open() as dataset:
            ext.validate_native_dataset(dataset, window)


def test_worldclim_trim_keeps_upper_native_centres_without_size(monkeypatch):
    window = ext.native_grid_window([cell()])
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"payload"

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(ext, "urlopen", fake_urlopen)
    ext._worldclim_query("https://example.test/wcs", "ALA__worldclim21_bio1", window)
    assert "SIZE" not in seen["url"]
    assert f"{window['east_center'] + ext.WORLDCLIM_STEP}" in seen["url"]
    assert f"{window['north_center'] + ext.WORLDCLIM_STEP}" in seen["url"]


def test_added_id_partition_uses_old_table_only(monkeypatch, tmp_path):
    monkeypatch.setattr(ext, "EXPECTED_OLD_ROWS", 1)
    monkeypatch.setattr(ext, "EXPECTED_ADDED_ROWS", 1)
    monkeypatch.setattr(ext, "EXPECTED_NEW_TOTAL", 2)
    monkeypatch.setattr(ext, "_read_domain", lambda root: [{"cell_id": "r0001c0001", "row": "1", "column": "1", "longitude": "135.385", "latitude": "-43.6175"}, {"cell_id": "r0002c0002", "row": "2", "column": "2", "longitude": "135.395", "latitude": "-43.6075"}])
    monkeypatch.setattr(ext, "_old_ids", lambda root: ["r0001c0001"])
    result = ext.added_cells(tmp_path)
    assert [row["cell_id"] for row in result] == ["r0002c0002"]
    assert result[0]["region"] == "southeast_mainland"


def test_cache_identity_and_orphan_fail_closed(tmp_path):
    path = tmp_path / "tile.tif"
    identity = {"source": "synthetic", "shape": [1, 1]}
    transform = from_origin(0, 1, 1, 1)
    profile = {"driver": "GTiff", "width": 1, "height": 1, "count": 1, "dtype": "float32", "crs": "EPSG:4326", "transform": transform}
    with MemoryFile() as memory:
        with memory.open(**profile) as dataset:
            dataset.write(np.ones((1, 1), dtype="float32"), 1)
        payload = memory.read()
    ext._store_raster_cache(path, payload, identity, (1, 1))
    assert ext._cache_pair(path, path.with_suffix(".json"), identity, (1, 1)) == path
    path.with_suffix(".json").write_text(json.dumps({"identity": {"changed": True}, "sha256": ext._sha256(path)}))
    with pytest.raises(ext.ExtensionError, match="identity"):
        ext._cache_pair(path, path.with_suffix(".json"), identity, (1, 1))
    orphan = tmp_path / "orphan.bin.part"
    orphan.write_bytes(b"x")
    with pytest.raises(ext.ExtensionError, match="orphaned_partial"):
        ext._write_bytes_atomic(orphan.with_suffix(""), b"y")


def test_atomic_block_resume_and_conflict(tmp_path):
    schema = pa.schema([pa.field("cell_id", pa.string()), pa.field("region", pa.string()), pa.field("bio01", pa.float64())])
    row = {"cell_id": "r0001c0001", "region": "southeast_mainland", "bio01": 1.0}
    first = ext._write_block(tmp_path, (1, 1), [row], schema, "synthetic-run")
    assert first.is_file()
    assert ext._write_block(tmp_path, (1, 1), [row], schema, "synthetic-run") == first
    first.with_suffix(".json").write_text(json.dumps({"ids": ["different"], "sha256": ext._sha256(first)}))
    with pytest.raises(ext.ExtensionError, match="receipt_conflict"):
        ext._write_block(tmp_path, (1, 1), [row], schema, "synthetic-run")


def test_validate_synthetic_output_preserves_old_rows(monkeypatch, tmp_path):
    old_path = tmp_path / ext.OLD_TABLE
    old_path.parent.mkdir(parents=True)
    schema = pa.schema([pa.field("cell_id", pa.string()), pa.field("region", pa.string()), pa.field("bio01", pa.float64())])
    old = pa.Table.from_pylist([{"cell_id": "r0001c0001", "region": "southeast_mainland", "bio01": 7.0}], schema=schema)
    pq.write_table(old, old_path)
    domain = tmp_path / ext.DOMAIN
    domain.parent.mkdir(parents=True)
    domain.write_text("cell_id,row,column,longitude,latitude\nr0001c0001,1,1,135.385,-43.6175\nr0002c0002,2,2,135.395,-43.6075\n")
    output = tmp_path / ext.ROOT_PRIVATE / ext.OUTPUT_NAME
    output.parent.mkdir(parents=True)
    added = pa.Table.from_pylist([{"cell_id": "r0002c0002", "region": "southeast_mainland", "bio01": 8.0}], schema=schema)
    pq.write_table(pa.concat_tables([old, added]), output)
    config = tmp_path / "config"
    metadata = tmp_path / "metadata"
    config.mkdir()
    metadata.mkdir()
    (config / "goal041_predictor_substrate.json").write_text("synthetic-goal041")
    (config / "goal048_seawfb_bioregional_freeze.json").write_text("synthetic-goal048")
    (metadata / "goal041_source_manifest.json").write_text("synthetic-source")
    monkeypatch.setattr(ext, "EXPECTED_OLD_ROWS", 1)
    monkeypatch.setattr(ext, "EXPECTED_ADDED_ROWS", 1)
    monkeypatch.setattr(ext, "EXPECTED_NEW_TOTAL", 2)
    monkeypatch.setattr(ext, "EXPECTED_ELEVATION_BLOCKS", 1)
    monkeypatch.setattr(ext, "WORLDCLIM_LAYERS", ("bio01",))
    monkeypatch.setattr(ext.goal041, "PREDICTORS", ("bio01",))
    monkeypatch.setattr(ext.goal041, "OUTPUT_FIELDS", ["cell_id", "region", "bio01"])
    monkeypatch.setattr(ext, "extension_run_identity", lambda root: "synthetic-run")
    monkeypatch.setattr(ext, "_goal041_identity", lambda root: "synthetic-goal041-run")
    monkeypatch.setattr(ext, "_source_identity", lambda *args, **kwargs: {"synthetic": True})
    monkeypatch.setattr(ext, "_cache_pair", lambda *args, **kwargs: args[0])
    block = (0, 0)
    block_path = ext._write_block(tmp_path, block, [{"cell_id": "r0002c0002", "region": "southeast_mainland", "bio01": 8.0}], schema, "synthetic-run")
    climate_path = tmp_path / ext.ROOT_PRIVATE / "worldclim" / "bio01.tif"
    climate_receipt = climate_path.with_suffix(".json")
    climate_path.parent.mkdir(parents=True, exist_ok=True)
    climate_path.write_bytes(b"synthetic-climate")
    climate_receipt.write_text("synthetic-climate-receipt")
    elevation_path = tmp_path / ext.ROOT_PRIVATE / "elevation" / "r0000_c0000.tif"
    elevation_receipt = elevation_path.with_suffix(".json")
    elevation_path.parent.mkdir(parents=True, exist_ok=True)
    elevation_path.write_bytes(b"synthetic-elevation")
    elevation_receipt.write_text("synthetic-elevation-receipt")
    overlap_path = tmp_path / ext.ROOT_PRIVATE / "worldclim_overlap.json"
    overlap_result = {"status": "validated", "overlap_cells": 1, "compared_values": 1, "layers": 1, "sample_limit": None}
    overlap_path.write_text(json.dumps({**overlap_result, "run_identity": "synthetic-run", "window": ext.native_grid_window([{"longitude": 135.395, "latitude": -43.6075}])}))
    source = {"goal041_run_identity": "synthetic-goal041-run", "goal041_config_sha256": ext._sha256(config / "goal041_predictor_substrate.json"), "goal041_source_manifest_sha256": ext._sha256(metadata / "goal041_source_manifest.json"), "goal041_table_sha256": ext._sha256(old_path), "goal048_domain_sha256": ext._sha256(domain)}
    manifest = {"schema_version": ext.SCHEMA_VERSION, "response_inputs_read": 0, "run_identity": "synthetic-run", "source": source, "output": {"path": str(output.relative_to(tmp_path)), "sha256": ext._sha256(output), "rows": 2, "added_rows": 1}, "predictors": ["bio01"], "worldclim_overlap": {"path": str(overlap_path.relative_to(tmp_path)), "sha256": ext._sha256(overlap_path), "result": overlap_result}, "blocks": [{"block": [0, 0], "path": str(block_path.relative_to(tmp_path)), "sha256": ext._sha256(block_path), "receipt_sha256": ext._sha256(block_path.with_suffix(".json")), "run_identity": "synthetic-run"}], "worldclim": [{"layer": "bio01", "path": str(climate_path.relative_to(tmp_path)), "sha256": ext._sha256(climate_path), "receipt_path": str(climate_receipt.relative_to(tmp_path)), "receipt_sha256": ext._sha256(climate_receipt)}], "elevation": [{"block": [0, 0], "path": str(elevation_path.relative_to(tmp_path)), "sha256": ext._sha256(elevation_path), "receipt_path": str(elevation_receipt.relative_to(tmp_path)), "receipt_sha256": ext._sha256(elevation_receipt)}]}
    (output.parent / "extension_manifest.json").write_text(json.dumps(manifest))
    result = ext.validate(tmp_path)
    assert result["status"] == "validated"
    assert result["added_rows"] == 1


def test_output_path_matches_scorer_contract():
    assert ext.OUTPUT_NAME == "predictor_substrate.parquet"
