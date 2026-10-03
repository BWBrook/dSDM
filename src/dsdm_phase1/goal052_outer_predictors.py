"""Response-free retained predictor reader for the Goal052 outer preparation.

Only the frozen Goal050 contract and the two Goal048 response-free parquet
surfaces are read.  The reader returns private arrays for downstream fitting
and a compact digest/count summary; it never writes tracked evidence and never
opens memberships, richness, species, canonical response, or outcome files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from pyproj import Transformer


CONFIG_PATH = Path("config/goal050_seawfb_modeling_foundation.json")
MANIFEST_PATH = Path("metadata/goal050_manifest.json")
TRANSFORMS_PATH = Path("metadata/goal050_transforms.json")
REGIONS = ("NCP", "SEH", "NNC")
PREDICTOR_SOURCE_REGION = "southeast_mainland"
CONTINUOUS = [f"bio{i:02d}" for i in range(1, 20)] + ["elevation_mean", "elevation_sd"]
CATEGORICAL = ["nvis_mvg", "soil_order", "alum_secondary"]
PREDICTORS = CONTINUOUS + CATEGORICAL
EXPECTED_FEATURES = 103
EXPECTED_MANIFEST_SHA256 = "239dd61cc5d3ab942a813201c0cb4117820b74367c7ba71deffddc6990d36198"


class OuterPredictorError(ValueError):
    """Raised when the response-free predictor contract is not satisfied."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise OuterPredictorError(reason)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterPredictorError(f"invalid_json:{path}") from exc
    _require(isinstance(value, dict), f"json_not_object:{path}")
    return value


def _digest_strings(values: list[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def _bind_contract(root: Path, expected_manifest_sha256: str = EXPECTED_MANIFEST_SHA256) -> dict[str, Any]:
    """Hash all frozen inputs before parsing or reading either parquet file."""

    root = Path(root)
    config_path = root / CONFIG_PATH
    manifest_path = root / MANIFEST_PATH
    transforms_path = root / TRANSFORMS_PATH
    for path in (config_path, manifest_path, transforms_path):
        _require(path.is_file(), f"frozen_metadata_missing:{path}")
    config_hash = sha256_file(config_path)
    manifest_hash = sha256_file(manifest_path)
    _require(manifest_hash == expected_manifest_sha256, "goal050_manifest_hash_mismatch")
    transforms_hash = sha256_file(transforms_path)
    config = _read_json(config_path)
    manifest = _read_json(manifest_path)
    transforms = _read_json(transforms_path)
    bindings = manifest.get("bindings", {})
    _require(bindings.get("config") == config_hash, "goal050_config_hash_mismatch")
    _require(bindings.get("transforms") == transforms_hash, "goal050_transform_hash_mismatch")
    _require(config.get("schema_version") == "goal050-seawfb-modeling-foundation-v1", "goal050_config_schema_drift")
    _require(config.get("regions") == list(REGIONS), "region_contract_drift")
    _require(config.get("predictors", {}).get("continuous") == CONTINUOUS, "continuous_predictor_order_drift")
    _require(config.get("predictors", {}).get("categorical") == CATEGORICAL, "categorical_predictor_order_drift")
    _require(config.get("grid", {}).get("crs") == "EPSG:4326", "geographic_crs_drift")
    _require(config.get("grid", {}).get("projected_crs") == "EPSG:3577", "projected_crs_drift")
    block_m = config.get("grid", {}).get("block_m")
    _require(type(block_m) is int and block_m == 50_000, "projected_block_size_drift")
    upstream = config.get("upstream", {})
    ledger_path = root / upstream.get("goal048_region_ledger", "")
    predictor_path = root / upstream.get("goal048_predictors", "")
    _require(ledger_path.is_file() and predictor_path.is_file(), "response_free_surface_missing")
    ledger_hash = sha256_file(ledger_path)
    predictor_hash = sha256_file(predictor_path)
    _require(bindings.get("goal048_region_ledger") == ledger_hash, "region_ledger_hash_mismatch")
    _require(bindings.get("goal048_predictors") == predictor_hash, "predictor_surface_hash_mismatch")
    retained = transforms.get("transforms", {}).get("retained_full")
    _require(isinstance(retained, Mapping), "retained_full_transform_missing")
    _require(set(retained.get("continuous", {}).keys()) == set(CONTINUOUS), "retained_full_continuous_set_drift")
    _require(set(retained.get("categorical", {}).keys()) == set(CATEGORICAL), "retained_full_categorical_set_drift")
    for name in CONTINUOUS:
        spec = retained["continuous"][name]
        _require(np.isfinite(float(spec.get("mean"))) and np.isfinite(float(spec.get("population_sd"))) and float(spec["population_sd"]) > 0, f"retained_full_continuous_transform_invalid:{name}")
    for name in CATEGORICAL:
        levels = retained["categorical"][name]
        _require("__MISSING__" in levels and "__UNSEEN__" in levels and len(levels) == len(set(levels)), f"retained_full_categorical_transform_invalid:{name}")
    _require(sum(len(retained["categorical"][name]) for name in CATEGORICAL) + len(CONTINUOUS) == EXPECTED_FEATURES, "retained_full_feature_count_drift")
    return {
        "config": config,
        "manifest": manifest,
        "transform": retained,
        "paths": {"ledger": ledger_path, "predictors": predictor_path},
        "hashes": {"config": config_hash, "manifest": manifest_hash, "transforms": transforms_hash, "ledger": ledger_hash, "predictors": predictor_hash},
    }


def _projected_blocks(longitude: np.ndarray, latitude: np.ndarray, block_m: int) -> tuple[np.ndarray, np.ndarray]:
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:3577", always_xy=True).transform(longitude, latitude)
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    _require(np.isfinite(x).all() and np.isfinite(y).all(), "projected_coordinates_nonfinite")
    return np.floor(x / block_m).astype(np.int64), np.floor(y / block_m).astype(np.int64)


def _encode_retained_full(frame: Any, transform: Mapping[str, Any]) -> np.ndarray:
    """Apply the native retained transform without an early float32 rounding."""
    columns: list[np.ndarray] = []
    for name in CONTINUOUS:
        spec = transform["continuous"][name]
        values = np.asarray(frame[name], dtype=np.float64).copy()
        values[~np.isfinite(values)] = float(spec["mean"])
        columns.append((values - float(spec["mean"])) / float(spec["population_sd"]))
    for name in CATEGORICAL:
        levels = list(transform["categorical"][name])
        allowed = set(levels)
        raw = frame[name].astype("string").fillna("__MISSING__").astype(str).to_numpy()
        values = np.asarray([value if value in allowed else "__UNSEEN__" for value in raw], dtype=object)
        columns.extend((values == level).astype(np.float64) for level in levels)
    return np.column_stack(columns)


def read_outer_predictors(root: Path = Path("."), *, expected_manifest_sha256: str = EXPECTED_MANIFEST_SHA256) -> dict[str, Any]:
    """Read all three fixed regions and encode predictors with retained_full."""

    bound = _bind_contract(Path(root), expected_manifest_sha256)
    ledger_path = bound["paths"]["ledger"]
    predictor_path = bound["paths"]["predictors"]
    ledger_columns = ["cell_id", "row", "column", "longitude", "latitude", "region"]
    predictor_columns = ["cell_id", "region", *PREDICTORS]
    ledger = pd.read_parquet(ledger_path, columns=ledger_columns)
    predictors = pd.read_parquet(predictor_path, columns=predictor_columns)
    for frame, label in ((ledger, "region_ledger"), (predictors, "predictor")):
        _require(frame["cell_id"].notna().all() and frame["cell_id"].astype(str).str.strip().ne("").all(), f"{label}_cell_id_invalid")
    _require(ledger["cell_id"].is_unique, "region_ledger_duplicate_cell_id")
    _require(predictors["cell_id"].is_unique, "predictor_duplicate_cell_id")
    for field in ("row", "column"):
        values = pd.to_numeric(ledger[field], errors="coerce").to_numpy(dtype=float)
        _require(np.isfinite(values).all() and np.equal(values, np.floor(values)).all(), f"region_ledger_{field}_invalid")
    selected = ledger.loc[ledger["region"].astype(str).isin(REGIONS)].copy()
    _require(len(selected) > 0, "no_outer_region_cells")
    _require(set(selected["region"].astype(str)) == set(REGIONS), "outer_region_coverage")
    selected = selected.rename(columns={"region": "ledger_region"})
    predictors = predictors.rename(columns={"region": "predictor_region"})
    predictors["_predictor_row_present"] = True
    merged = selected.merge(predictors, on="cell_id", how="left", validate="one_to_one", sort=False)
    _require(len(merged) == len(selected), "predictor_join_row_count_drift")
    _require(merged["_predictor_row_present"].fillna(False).all(), "predictor_missing_cell")
    _require(merged["predictor_region"].notna().all(), "predictor_region_missing")
    _require((merged["predictor_region"].astype(str) == PREDICTOR_SOURCE_REGION).all(), "predictor_source_region_drift")
    order = {region: index for index, region in enumerate(REGIONS)}
    merged["_region_order"] = merged["ledger_region"].astype(str).map(order)
    _require(merged["_region_order"].notna().all(), "region_order_missing")
    merged = merged.sort_values(["_region_order", "row", "column", "cell_id"], kind="mergesort").reset_index(drop=True)
    frame = merged[PREDICTORS]
    encoded = _encode_retained_full(frame, bound["transform"])
    _require(encoded.shape == (len(merged), EXPECTED_FEATURES), "encoded_feature_shape_drift")
    _require(np.isfinite(encoded).all(), "encoded_predictors_nonfinite")
    longitude = merged["longitude"].to_numpy(dtype=float)
    latitude = merged["latitude"].to_numpy(dtype=float)
    _require(np.isfinite(longitude).all() and np.isfinite(latitude).all(), "outer_coordinates_nonfinite")
    block_x, block_y = _projected_blocks(longitude, latitude, int(bound["config"]["grid"]["block_m"]))
    cell_ids = merged["cell_id"].astype(str).tolist()
    regions = merged["ledger_region"].astype(str).tolist()
    arrays = {
        "cell_ids": np.asarray(cell_ids, dtype="U"),
        "regions": np.asarray(regions, dtype="U"),
        "x": encoded,
        "longitude": longitude,
        "latitude": latitude,
        "block_x": block_x,
        "block_y": block_y,
    }
    summary = {
        "schema_version": "goal052-outer-predictors-v1",
        "regions": list(REGIONS),
        "rows": len(merged),
        "rows_by_region": {region: int(sum(value == region for value in regions)) for region in REGIONS},
        "feature_count": int(encoded.shape[1]),
        "feature_dtype": str(encoded.dtype),
        "feature_order": [*CONTINUOUS, *[f"{name}={level}" for name in CATEGORICAL for level in bound["transform"]["categorical"][name]]],
        "cell_id_sha256": _digest_strings(cell_ids),
        "region_sha256": _digest_strings(regions),
        "encoded_sha256": hashlib.sha256(encoded.tobytes()).hexdigest(),
        "input_sha256": bound["hashes"],
        "sort_order": ["region(NCP,SEH,NNC)", "row", "column", "cell_id"],
        "predictor_source_region": PREDICTOR_SOURCE_REGION,
        "outer_response_rows_read": 0,
    }
    return {"arrays": arrays, "summary": summary}
