from __future__ import annotations

import json
from pathlib import Path

import pytest
import numpy as np

from dsdm_phase1 import goal040_predictor_pilot as pilot


def _cells():
    rows = []
    for region, offset in (("southeast_mainland", 0), ("tasmania", 1000)):
        for i in range(128):
            rows.append({"cell_id": f"r{offset+i:04d}", "row_south_to_north": str(i), "column_west_to_east": str(i), "longitude": str(140 + (i % 16) * .01), "latitude": str(-40 + (i // 16) * .01), "state_code": "6", "region": region})
    return rows


def test_selection_is_deterministic_and_64_each():
    a = pilot.select_pilot_cells(_cells())
    b = pilot.select_pilot_cells(list(reversed(_cells())))
    assert {key: [row["cell_id"] for row in value] for key, value in a.items()} == {key: [row["cell_id"] for row in value] for key, value in b.items()}
    assert all(len(value) == 64 for value in a.values())


def test_selection_uses_projected_stratum_medians():
    rows = _cells()
    selected = pilot.select_pilot_cells(rows)
    values = [r for r in rows if r["region"] == "southeast_mainland"]
    for row in values:
        row["xy"] = pilot.TRANSFORM.transform(float(row["longitude"]), float(row["latitude"]))
    values.sort(key=lambda r: (r["xy"][0], r["cell_id"]))
    first = list(np.array_split(np.asarray(values, dtype=object), 8)[0])
    first.sort(key=lambda r: (r["xy"][1], r["cell_id"]))
    stratum = list(np.array_split(np.asarray(first, dtype=object), 8)[0])
    mx = float(np.median([r["xy"][0] for r in stratum])); my = float(np.median([r["xy"][1] for r in stratum]))
    expected = min(stratum, key=lambda r: ((r["xy"][0]-mx)**2 + (r["xy"][1]-my)**2, r["cell_id"]))["cell_id"]
    assert selected["southeast_mainland"][0]["cell_id"] == expected


def test_mocked_source_parsing_and_diagnostic_thresholds():
    payload = {"data": [{f"el{10977+i}": i + 1 for i in range(1, 20)}]}
    parsed = pilot.parse_ala_intersect(payload)
    assert parsed["el10992"] == 16.0  # BIO15 remains numeric; no mm relabelling
    assert pilot.parse_service_value({"features": [{"attributes": {"code": "MVG01", "label": "Forest"}}]}) == "MVG01"
    diag = pilot.continuous_diagnostic([1, 2, 3], [2, 4])
    assert diag["missing_fraction"] == {"mainland": 0.0, "tasmania": 0.0}
    assert diag["tasmania_outside_mainland_range_fraction"] == 0.5
    cat = pilot.categorical_diagnostic(["A", "A", "B"], ["B", "C"])
    assert cat["tasmania_novel_level_fraction"] == 0.5


def test_tern_properties_schema_and_soil_code_validation(monkeypatch):
    payload = {"features": [{"properties": {"estimated soil class": "3.0"}}]}
    monkeypatch.setattr(pilot, "_http_get", lambda *args, **kwargs: json.dumps(payload).encode())
    assert pilot._fetch_soil(-37.8, 144.9) == "3:Dermosol"
    monkeypatch.setattr(pilot, "_http_get", lambda *args, **kwargs: json.dumps({"features": [{"properties": {"estimated soil class": "99"}}]}).encode())
    with pytest.raises(pilot.Goal040PredictorError, match="soil_order_code_invalid"):
        pilot._fetch_soil(-37.8, 144.9)


def test_tern_soil_legend_mapping_is_frozen():
    assert pilot.SOIL_LABELS == {
        "1": "Vertosol", "2": "Sodosol", "3": "Dermosol", "4": "Chromosol",
        "5": "Ferrosol", "6": "Kurosol", "7": "Tenosol", "8": "Kandosol",
        "9": "Hydrosol", "10": "Podosol", "11": "Rudosol", "12": "Calcarasol",
        "13": "Organosol", "14": "Anthroposol",
    }


def test_alum_pixel_centres_and_numeric_tie(monkeypatch):
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    lon, lat = 145.0, -37.0
    x, y = pilot.TRANSFORM.transform(lon, lat)
    transform = from_origin(x - 1500, y + 1500, 1000, 1000)
    with MemoryFile() as memory:
        with memory.open(driver="GTiff", height=3, width=3, count=1, dtype="int16", crs="EPSG:3577", transform=transform, nodata=0) as ds:
            ds.write(np.array([[1, 2, 1], [2, 1, 2], [1, 2, 0]], dtype="int16"), 1)
            labels = {"1": "1:A", "2": "2:B"}
            assert pilot._alum_modal(ds, labels, lat, lon) == "1:A"


def test_categorical_transport_schema_failure_is_not_missing(monkeypatch):
    monkeypatch.setattr(pilot, "_http_get", lambda *args, **kwargs: b"{}")
    with pytest.raises(pilot.Goal040PredictorError) as exc:
        pilot._fetch_nvis(-37.8, 144.9)
    assert type(exc.value) is pilot.Goal040PredictorError
    monkeypatch.setattr(pilot, "_http_get", lambda *args, **kwargs: json.dumps({"results": []}).encode())
    with pytest.raises(pilot.Goal040PredictorMissing) as exc:
        pilot._fetch_nvis(-37.8, 144.9)
    assert type(exc.value) is pilot.Goal040PredictorMissing
    monkeypatch.setattr(pilot, "_http_get", lambda *args, **kwargs: json.dumps({"features": []}).encode())
    with pytest.raises(pilot.Goal040PredictorMissing):
        pilot._fetch_soil(-37.8, 144.9)


def test_ala_list_blank_is_missing_and_short_list_fails():
    payload = [{"field": field, "value": "" if i == 3 else str(i)} for i, field in enumerate(pilot.WORLDCLIM_FIELDS)]
    parsed = pilot.parse_ala_intersect(payload)
    assert set(parsed) == set(pilot.WORLDCLIM_FIELDS)
    assert parsed[pilot.WORLDCLIM_FIELDS[3]] is None
    with pytest.raises(pilot.Goal040PredictorError, match="ALA_intersect_fields_missing"):
        pilot.parse_ala_intersect(payload[:-1])


def test_checkpoint_mismatch_invalidates_reuse(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pilot, "_cells", lambda root: _cells())
    calls = []
    def fake(root, cell):
        calls.append(cell["cell_id"]); return {"cell_id": cell["cell_id"], "longitude": float(cell["longitude"]), "latitude": float(cell["latitude"]), "region": cell["region"], **{name: 1.0 for name in pilot.CONTINUOUS}, **{name: "A" for name in pilot.CATEGORICAL}}
    pilot.run_pilot(tmp_path, row_fetcher=fake); calls.clear()
    cp = tmp_path / pilot.RAW_ROOT / pilot.CHECKPOINT_FILE; value=json.loads(cp.read_text()); value["source_matrix_sha256"]="0"*64; cp.write_text(json.dumps(value))
    pilot.run_pilot(tmp_path, row_fetcher=fake)
    assert len(calls) == 128


def test_semantic_matrix_selection_and_receipt_tamper(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pilot, "_cells", lambda root: _cells())
    def fake(root, cell): return {"cell_id": cell["cell_id"], "longitude": float(cell["longitude"]), "latitude": float(cell["latitude"]), "region": cell["region"], **{name: 1.0 for name in pilot.CONTINUOUS}, **{name: "A" for name in pilot.CATEGORICAL}}
    pilot.run_pilot(tmp_path, row_fetcher=fake); pilot.finalise(tmp_path)
    matrix=tmp_path/pilot.SOURCE_MATRIX_PATH; d=json.loads(matrix.read_text()); d["layers"][0]["definition"]="tampered"; matrix.write_text(json.dumps(d));
    with pytest.raises(pilot.Goal040PredictorError): pilot.validate_pilot(tmp_path)


def test_run_replay_and_tracked_tamper(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pilot, "_cells", lambda root: _cells())

    def fake_fetch(root, cell):
        value = {"cell_id": cell["cell_id"], "longitude": float(cell["longitude"]), "latitude": float(cell["latitude"]), "region": cell["region"]}
        value.update({name: float(i + 1) for i, name in enumerate(pilot.CONTINUOUS)})
        value.update({name: "A" for name in pilot.CATEGORICAL})
        return value

    pilot.run_pilot(tmp_path, row_fetcher=fake_fetch)
    assert pilot.validate_pilot(tmp_path, require_raw=True)["cells"] == 128
    manifest_path = tmp_path / pilot.MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    manifest["aggregate"]["continuous"]["bio01"]["mainland_range"] = [999.0, 1000.0]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(pilot.Goal040PredictorError, match="aggregate_replay"):
        pilot.validate_pilot(tmp_path, require_raw=True)


def test_private_replay_tamper(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pilot, "_cells", lambda root: _cells())

    def fake_fetch(root, cell):
        value = {"cell_id": cell["cell_id"], "longitude": float(cell["longitude"]), "latitude": float(cell["latitude"]), "region": cell["region"]}
        value.update({name: float(i + 1) for i, name in enumerate(pilot.CONTINUOUS)})
        value.update({name: "A" for name in pilot.CATEGORICAL})
        return value

    pilot.run_pilot(tmp_path, row_fetcher=fake_fetch)
    path = tmp_path / pilot.RAW_ROOT / pilot.VALUES_FILE
    path.write_text(path.read_text() + "\n")
    with pytest.raises(pilot.Goal040PredictorError, match="private_digest"):
        pilot.validate_pilot(tmp_path, require_raw=True)
