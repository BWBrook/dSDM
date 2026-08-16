from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dsdm_phase1 import goal041_predictor_substrate as substrate


def _cell(row=50, col=50, region="tasmania"):
    return {
        "cell_id": f"r{row:04d}c{col:04d}",
        "row_south_to_north": str(row),
        "column_west_to_east": str(col),
        "longitude": f"{substrate.GRID_ORIGIN_LON + col * .01 + .005:.4f}",
        "latitude": f"{substrate.GRID_ORIGIN_LAT + row * .01 + .005:.4f}",
        "region": region,
    }


def _raster(data, *, transform=None, crs="EPSG:4326", nodata=None):
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    transform = transform or from_origin(135.87, -43.12, .002, .002)
    mem = MemoryFile()
    ds = mem.open(driver="GTiff", height=data.shape[0], width=data.shape[1], count=1,
                  dtype=str(data.dtype), crs=crs, transform=transform, nodata=nodata)
    ds.write(data, 1)
    return mem, ds


def test_exact_block_geometry_and_orientation():
    cell = _cell(50, 50, "southeast_mainland")
    assert substrate.production_block_key(cell) == (1, 1)
    assert substrate.production_block_bounds((1, 1)) == (135.87, -43.1325, 136.37, -42.6325)
    assert substrate.cell_bounds(cell) == pytest.approx((135.87, -43.1325, 135.88, -43.1225))
    source = np.arange(4 * 6).reshape(4, 6)
    blocks = substrate.reshape_wcs_tile(source, target_rows=2, target_cols=3, pixels_per_cell=2)
    assert blocks.shape == (2, 2, 3, 2)
    assert blocks[0, 0, 0, 0] == source[3, 0]
    with pytest.raises(substrate.Goal041Error, match="shape"):
        substrate.reshape_wcs_tile(source, target_rows=3, target_cols=2, pixels_per_cell=2)


def test_expanded_window_assigns_projected_pixel_centres_to_half_open_cells():
    # A 2x2 raster whose centres straddle the exact cell's west/south edges.
    from rasterio.transform import from_origin
    mem, ds = _raster(np.array([[1, 2], [3, 4]], dtype="int16"), transform=from_origin(135.378, -43.6225, .002, .002), nodata=0)
    try:
        value = substrate.summarize_raster_cell(ds, _cell(0, 0), "categorical")
        assert value == 1
    finally:
        ds.close(); mem.close()


def test_continuous_summary_preserves_masked_nodata():
    values = np.ma.array([1.0, 99.0, 3.0], mask=[False, True, False], dtype="float32")
    mean, sd = substrate.continuous_summary(values)
    assert mean == pytest.approx(2.0)
    assert sd == pytest.approx(np.std([1.0, 3.0], ddof=1))


def test_pilot_wcs_cache_reuses_checksum_bound_tile(tmp_path, monkeypatch):
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    config_path = tmp_path / substrate.CONFIG_PATH
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}")
    monkeypatch.setattr(substrate, "_config", lambda root: {"sources": {"elevation": {"url": "mock://ga"}}})
    memory = MemoryFile()
    with memory.open(driver="GTiff", height=2, width=2, count=1, dtype="int16", crs="EPSG:4326", transform=from_origin(0, 2, 1, 1)) as dataset:
        dataset.write(np.ones((2, 2), dtype="int16"), 1)
    payload = memory.read(); memory.close(); calls = []
    monkeypatch.setattr(substrate, "wcs_request", lambda *args, **kwargs: calls.append(1) or payload)
    kwargs = {"bbox": (0.0, 0.0, 2.0, 2.0), "width": 2, "height": 2, "coverage": "1", "version": "1.0.0"}
    first = substrate._pilot_cached_tile(tmp_path, "elevation", (1, 2), **kwargs)
    second = substrate._pilot_cached_tile(tmp_path, "elevation", (1, 2), **kwargs)
    assert first == second and len(calls) == 1
    receipt = first.with_suffix(".json")
    receipt.write_text(receipt.read_text().replace('"shape": [2, 2]', '"shape": [3, 3]'))
    with pytest.raises(substrate.Goal041Error, match="identity"):
        substrate._pilot_cached_tile(tmp_path, "elevation", (1, 2), **kwargs)


def test_cog_soil_centroid_and_code_contract():
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    memory = MemoryFile()
    with memory.open(driver="GTiff", height=2, width=2, count=1, dtype="int16", crs="EPSG:4326", transform=from_origin(135.3725, -43.625, .005, .005), nodata=0) as dataset:
        dataset.write(np.array([[12, 12], [0, 12]], dtype="int16"), 1)
        cell = _cell(0, 0)
        assert substrate.canonical_soil_code(substrate.soil_centroid_value(dataset, cell)) == "12:Calcarasol"
    memory.close()
    config = json.loads((Path(__file__).resolve().parents[1] / substrate.CONFIG_PATH).read_text())
    soil = config["sources"]["soil_order"]
    assert soil["file_id"] == "64191223" and soil["legend_file_id"] == "64191225"
    assert soil["legend"] .endswith("12:Calcarasol")


def test_numeric_category_codes_are_canonical_before_lookup():
    assert substrate.canonical_numeric_code(1) == "1"
    assert substrate.canonical_numeric_code(1.0) == "1"
    assert substrate.canonical_numeric_code(np.float32(99.0)) == "99"


def test_nvis_labels_are_complete_and_treat_official_unknown_as_missing(tmp_path):
    tif = tmp_path / substrate.RAW_ROOT / "nvis_mvg.tif"
    tif.parent.mkdir(parents=True)
    archive = tif.parent / "probes" / "nvis_7_extant_all.zip"
    archive.parent.mkdir()
    archive.touch()
    mapping = substrate._nvis_rat(tif)
    assert len(mapping) == 32
    assert mapping["18"] == "18:Heathlands"
    assert mapping["99"] is None


def test_aligned_soil_cell_assigns_144_native_centres_half_open(monkeypatch):
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    memory = MemoryFile()
    resolution = .01 / 12
    transform = from_origin(135.37 - resolution / 2, -43.6225 - resolution / 2, resolution, resolution)
    with memory.open(driver="GTiff", height=12, width=12, count=1, dtype="int16", crs="EPSG:4326", transform=transform, nodata=0) as dataset:
        dataset.write(np.full((12, 12), 12, dtype="int16"), 1)
        counts = []
        original = substrate.mode_low_code
        monkeypatch.setattr(substrate, "mode_low_code", lambda values: counts.append(len(values)) or original(values))
        assert substrate.block_raster_summaries(dataset, [_cell(0, 0)], categorical=True)["r0000c0000"] == 12
        assert counts == [144]
    memory.close()


def test_boundary_snap_is_absolute_only():
    assert substrate._snap_grid_coordinate(2000.001) == pytest.approx(2000.001)
    assert substrate._snap_grid_coordinate(2000.0000000001) == 2000.0
    values = substrate._snap_grid_coordinates(np.array([2000.001, 2000.0000000001]))
    assert values.tolist() == pytest.approx([2000.001, 2000.0])


def test_numeric_low_ties_and_alum_mode_before_secondary_mapping():
    assert substrate.mode_low_code([2, 1, 2, 1]) == 1
    assert substrate.mode_low_code(["12:Managed", "11:Nature", "12:Managed"]) == "12:Managed"
    lookup = {"1": "10:Secondary A", "2": "20:Secondary B"}
    assert substrate.alum_mode_then_secondary([2, 1, 2, 1], lookup) == "10:Secondary A"
    with pytest.raises(substrate.SourceMissing):
        substrate.mode_low_code([None, "NoData"])
    with pytest.raises(substrate.Goal041Error, match="missing_from_lookup"):
        substrate.map_alum_secondary(99, lookup)


def test_pilot_tolerance_and_missingness_are_frozen():
    expected = {name: 1.0 for name in substrate.CONTINUOUS} | {name: "1:A" for name in substrate.CATEGORICAL}
    observed = dict(expected); observed["bio01"] = float(np.float32(1.0 + np.spacing(np.float32(1.0))))
    assert substrate.pilot_equivalent(expected, observed)["equivalent"]
    observed["bio01"] = 1.00002
    assert not substrate.pilot_equivalent(expected, observed)["equivalent"]
    observed = dict(expected); observed["soil_order"] = None
    assert "soil_order" in substrate.pilot_equivalent(expected, observed)["mismatches"]


def test_diagnostics_and_metadata_privacy():
    rows = [{"region": "southeast_mainland", **{n: 1.0 for n in substrate.CONTINUOUS}, **{n: "1:A" for n in substrate.CATEGORICAL}},
            {"region": "tasmania", **{n: 2.0 for n in substrate.CONTINUOUS}, **{n: "2:B" for n in substrate.CATEGORICAL}}]
    diagnostics = substrate.diagnose_rows(rows)
    assert diagnostics["regions"]["tasmania"]["predictors"]["bio01"]["above_mainland_range"] == 1
    assert diagnostics["regions"]["tasmania"]["predictors"]["nvis_mvg"]["mainland_absent_valid_levels"] == ["2:B"]
    substrate.assert_metadata_privacy({"schema": [{"name": "cell_id", "type": "string"}], "ordered_identity_digest": "abc"})
    with pytest.raises(substrate.Goal041Error, match="privacy"):
        substrate.assert_metadata_privacy({"identities": ["r0001c0002"]})
    with pytest.raises(substrate.Goal041Error, match="privacy"):
        substrate.assert_metadata_privacy({"cell_id": "r0001c0002"})


def test_chunk_receipt_requires_exact_pair_schema_and_identity(tmp_path):
    rows = [{"cell_id": "r0000c0000", "region": "tasmania",
             **{name: 1.0 for name in substrate.CONTINUOUS},
             **{name: "1:A" for name in substrate.CATEGORICAL}}]
    path = tmp_path / substrate.RAW_ROOT / "chunks" / "band_0000.parquet"
    path.parent.mkdir(parents=True)
    substrate._write_parquet(path, rows)
    receipt = substrate._chunk_receipt_payload(path, 0, ["r0000c0000"], "run")
    substrate._write_json(tmp_path, "chunk_receipt_0000.json", receipt, private=True)
    assert substrate._validate_chunk_pair(tmp_path, path, ["r0000c0000"], "run") == receipt
    path.unlink()
    with pytest.raises(substrate.Goal041Error, match="orphaned"):
        substrate._validate_chunk_pair(tmp_path, path, ["r0000c0000"], "run")
    substrate.assert_metadata_privacy({"schema": ["cell_id", "region"], "rows": 1125325})


def test_representative_benchmark_blocks_cover_both_regions():
    cells = [_cell(0, i, "southeast_mainland") for i in range(0, 200, 50)] + [_cell(100, i, "tasmania") for i in range(0, 200, 50)]
    blocks = substrate.representative_blocks(cells, per_region=2)
    assert len(blocks) == 4 and len(set(blocks)) == 4


def test_missingness_component_summary_is_four_neighbour_and_bounded():
    summary = substrate._component_summary({(0, 0), (0, 1), (1, 1), (10, 10)})
    assert summary == {"components": 2, "largest": 3, "singletons": 1, "largest_fraction": 0.75}


def test_representative_blocks_prefer_high_occupancy_over_sparse_edges():
    cells = []
    for region, row in (("southeast_mainland", 100), ("tasmania", 200)):
        cells.extend(_cell(row, 100, region) for _ in range(20))
        cells.extend(_cell(row, 150, region) for _ in range(20))
        cells.extend([_cell(row, 0, region), _cell(row, 450, region)])
    blocks = substrate.representative_blocks(cells, per_region=2)
    assert (2, 0) not in blocks and (2, 9) not in blocks
    assert (4, 0) not in blocks and (4, 9) not in blocks


def test_contract_config_is_frozen():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / substrate.CONFIG_PATH).read_text())
    assert config["sources"]["worldclim"]["url"].endswith("/wcs")
    assert config["sources"]["elevation"]["coverage"] == "1"
