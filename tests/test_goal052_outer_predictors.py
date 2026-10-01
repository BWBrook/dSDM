from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dsdm_phase1 import goal052_outer_predictors as reader


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path):
    config_path = tmp_path / reader.CONFIG_PATH
    manifest_path = tmp_path / reader.MANIFEST_PATH
    transforms_path = tmp_path / reader.TRANSFORMS_PATH
    ledger_path = tmp_path / "data/ledger.parquet"
    predictor_path = tmp_path / "data/predictors.parquet"
    for path in (config_path, manifest_path, transforms_path, ledger_path, predictor_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "schema_version": "goal050-seawfb-modeling-foundation-v1",
        "regions": list(reader.REGIONS),
        "grid": {"crs": "EPSG:4326", "projected_crs": "EPSG:3577", "block_m": 50000},
        "predictors": {"continuous": reader.CONTINUOUS, "categorical": reader.CATEGORICAL},
        "upstream": {"goal048_region_ledger": "data/ledger.parquet", "goal048_predictors": "data/predictors.parquet"},
    }
    levels = {
        "nvis_mvg": ["__MISSING__", "__UNSEEN__", *[f"n{i}" for i in range(30)]],
        "soil_order": ["__MISSING__", "__UNSEEN__", *[f"s{i}" for i in range(14)]],
        "alum_secondary": ["__MISSING__", "__UNSEEN__", *[f"a{i}" for i in range(32)]],
    }
    transform = {
        "transforms": {
            "retained_full": {
                "continuous": {name: {"mean": 10.0, "population_sd": 2.0} for name in reader.CONTINUOUS},
                "categorical": levels,
            }
        },
        "bindings": {},
    }
    ledger = pd.DataFrame(
        [
            {"cell_id": "c3", "row": 1, "column": 0, "longitude": 145.0, "latitude": -42.0, "region": "SEH"},
            {"cell_id": "c1", "row": 0, "column": 1, "longitude": 140.0, "latitude": -35.0, "region": "NCP"},
            {"cell_id": "c2", "row": 0, "column": 0, "longitude": 141.0, "latitude": -36.0, "region": "NNC"},
        ]
    )
    base = {name: [1.0, np.nan, 3.0] for name in reader.CONTINUOUS}
    predictors = pd.DataFrame({"cell_id": ["c1", "c2", "c3"], "region": [reader.PREDICTOR_SOURCE_REGION] * 3, **base})
    predictors["nvis_mvg"] = ["known", None, "unknown"]
    predictors["soil_order"] = ["s0", "unseen-soil", "s1"]
    predictors["alum_secondary"] = ["a0", "a1", "a2"]
    ledger.to_parquet(ledger_path, index=False)
    predictors.to_parquet(predictor_path, index=False)
    config_path.write_text(json.dumps(config))
    transforms_path.write_text(json.dumps(transform, sort_keys=True))
    manifest = {"bindings": {"config": _sha(config_path), "transforms": _sha(transforms_path), "goal048_region_ledger": _sha(ledger_path), "goal048_predictors": _sha(predictor_path)}}
    manifest_path.write_text(json.dumps(manifest))
    return tmp_path, ledger_path, predictor_path, _sha(manifest_path)


def test_response_free_read_and_deterministic_order_with_missing_unseen(tmp_path, monkeypatch):
    root, ledger_path, predictor_path, manifest_sha = _fixture(tmp_path)
    calls = []
    original = reader.pd.read_parquet

    def instrument(path, *args, **kwargs):
        calls.append(Path(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(reader.pd, "read_parquet", instrument)
    first = reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)
    second = reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)
    assert calls and set(calls) == {ledger_path, predictor_path}
    assert [*first["arrays"]["cell_ids"]] == ["c1", "c3", "c2"]
    for name in first["arrays"]:
        np.testing.assert_array_equal(first["arrays"][name], second["arrays"][name])
    assert first["arrays"]["x"].shape == (3, 103)
    assert np.isfinite(first["arrays"]["x"]).all()
    # c2 has a missing continuous value and categorical missing/unseen values;
    # the retained transform must encode them as finite mean/__MISSING__/__UNSEEN__.
    assert first["arrays"]["x"][2, 1] == 0.0
    assert first["arrays"]["x"][2, 21] == 1.0
    assert first["arrays"]["x"][2, 21 + 32 + 1] == 1.0
    assert first["summary"]["rows_by_region"] == {"NCP": 1, "SEH": 1, "NNC": 1}
    assert first["summary"]["feature_count"] == 103
    assert first["summary"]["outer_response_rows_read"] == 0


def test_missing_duplicate_and_join_drift_fail_closed(tmp_path):
    root, _, predictor_path, manifest_sha = _fixture(tmp_path)
    frame = pd.read_parquet(predictor_path)
    frame = frame.iloc[:-1]
    frame.to_parquet(predictor_path, index=False)
    manifest_path = root / reader.MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    manifest["bindings"]["goal048_predictors"] = _sha(predictor_path)
    manifest_path.write_text(json.dumps(manifest))
    manifest_sha = _sha(manifest_path)
    with pytest.raises(reader.OuterPredictorError, match="predictor_missing_cell"):
        reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)

    root, _, predictor_path, manifest_sha = _fixture(tmp_path / "duplicate")
    frame = pd.read_parquet(predictor_path)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame.to_parquet(predictor_path, index=False)
    manifest_path = root / reader.MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    manifest["bindings"]["goal048_predictors"] = _sha(predictor_path)
    manifest_path.write_text(json.dumps(manifest))
    manifest_sha = _sha(manifest_path)
    with pytest.raises(reader.OuterPredictorError, match="predictor_duplicate_cell_id"):
        reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)


def test_hash_corruption_is_detected_before_parquet_read(tmp_path):
    root, _, predictor_path, manifest_sha = _fixture(tmp_path)
    predictor_path.write_bytes(predictor_path.read_bytes() + b"corruption")
    with pytest.raises(reader.OuterPredictorError, match="predictor_surface_hash_mismatch"):
        reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)


def test_manifest_and_config_tampering_fail_before_surface_reads(tmp_path):
    root, _, _, manifest_sha = _fixture(tmp_path)
    manifest_path = root / reader.MANIFEST_PATH
    manifest_path.write_text(manifest_path.read_text() + "\n")
    with pytest.raises(reader.OuterPredictorError, match="goal050_manifest_hash_mismatch"):
        reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)

    root, _, _, manifest_sha = _fixture(tmp_path / "config")
    config_path = root / reader.CONFIG_PATH
    config = json.loads(config_path.read_text())
    config["grid"]["block_m"] = 49_999
    config_path.write_text(json.dumps(config))
    with pytest.raises(reader.OuterPredictorError, match="goal050_config_hash_mismatch"):
        reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)


def test_predictor_source_region_drift_fails_closed(tmp_path):
    root, _, predictor_path, manifest_sha = _fixture(tmp_path)
    predictors = pd.read_parquet(predictor_path)
    predictors.loc[predictors.cell_id == "c2", "region"] = "wrong-source-domain"
    predictors.to_parquet(predictor_path, index=False)
    manifest_path = root / reader.MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    manifest["bindings"]["goal048_predictors"] = _sha(predictor_path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(reader.OuterPredictorError, match="goal050_manifest_hash_mismatch"):
        reader.read_outer_predictors(root, expected_manifest_sha256=manifest_sha)
    with pytest.raises(reader.OuterPredictorError, match="predictor_source_region_drift"):
        reader.read_outer_predictors(root, expected_manifest_sha256=_sha(manifest_path))
