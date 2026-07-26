"""Goal022 deterministic extraction of the authoritative Tasmanian predictor stack.

The module deliberately stops at raw, cell-level predictors.  It does not impute,
transform, encode, partition, or fit any model.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import rasterio
from rasterio.transform import rowcol

GOAL_ID = "goal022-predictor-stack-extraction-2026-07-26"
ACTIVE_BAND_INDICES = tuple(list(range(1, 25)) + [26, 28, 30, 32])
EXCLUDED_BAND_INDICES = (25, 27, 29, 31)
ALL_BAND_NAMES = (
    "annmeantemp", "meandiurnrange", "isothermality", "tempseason",
    "maxtempwarmmonth", "mintempcoldmonth", "tempannrange", "meantempwetq",
    "meantempdryq", "meantempwarmq", "meantempcoldq", "annprecip",
    "precipwetmonth", "precipdrymonth", "precipseason", "precipwetq",
    "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness",
    "soil_class", "dist_fw", "dist_road", "fire_freq", "fpar", "veg_mvs",
    "veg_mvg", "landuse_primary", "landuse_secondary", "landuse_tertiary",
    "human_footprint",
)
ACTIVE_PREDICTORS = tuple(ALL_BAND_NAMES[i - 1] for i in ACTIVE_BAND_INDICES)
EXCLUDED_PREDICTORS = tuple(ALL_BAND_NAMES[i - 1] for i in EXCLUDED_BAND_INDICES)
CATEGORICAL_PREDICTORS = ("soil_class", "veg_mvg", "landuse_secondary")
EXPECTED_LEVELS = {
    "soil_class": list(range(2, 15)),
    "veg_mvg": [1, 2, 3, 4, 5, 7, 9, 10, 11, 15, 16, 17, 18, 19, 21, 22, 24, 25, 26, 27, 29, 31],
    "landuse_secondary": [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18],
}
OUTPUT_FIELDS = ("grid_cell_id", "centroid_lon", "centroid_lat") + ACTIVE_PREDICTORS + (
    "predictor_complete", "missing_predictor_count", "missing_predictor_ids"
)
OUTPUT_FILES = ("predictor_cell_map_raw.csv", "predictor_response_cells_raw.csv")
EVIDENCE_FILES = ("source_inventory.json", "band_manifest.json", "categorical_levels.json", "missingness_summary.json", "spatial_summary.json", "outputs.json", "review.json")
PLAN_PRIVACY = {"tracked_grid_ids_or_coordinates": False, "tracked_row_payloads": False, "tracked_private_paths": False, "tracked_response_identifiers": False}
RUNTIME_CONTRACT = {"python_requires": ">=3.11", "rasterio": "1.4.4", "numpy_by_python": {"python_full_version < '3.12'": "2.4.6", "python_full_version >= '3.12'": "2.5.1"}}
EXPECTED_BINDINGS = {
    "decision_bundle": ("config/phase1_decision_bundle.json", "ccccbb2e56e101b1a53421f8016699bfb500f4356861e10c1213a398aabe04a2"),
    "stack": ("temp/data/spatial/tas_stack.tif", "e3dd4175688572d9c8afcfb521a5e1083a0f25ba90d4841938a93aa5d6f72088"),
    "canonical_grid": ("temp/data/spatial/tasmanian_gridpoints.csv", "91c7e0158ee8a808e9345d4bca28ec3e3fd7468dc3b7b1c1268e33e2da9499da"),
    "legacy_band_order": ("temp/src/3_create_sdm_data.R", "cff353c830fe78e351fc72f2672dd1c73e94930ebf4516b53c5950ec19a4effe"),
    "goal021_plan": ("config/pseudoabsence_derivation_plan.json", "75cdc198815d3076af6ee3b6f25bed5ea4e90bf1433c7e9205f8692dfedd95fe"),
    "goal021_manifest": ("evidence/pseudoabsence_derivation/2026-07-26/manifest.json", "bf843690a6071f489b81fb5bdc348bab1c9f2001dfa37ad359ed7dc75d50f875"),
    "goal021_outputs_evidence": ("evidence/pseudoabsence_derivation/2026-07-26/outputs.json", "ecf0e6f46b3eec30c4edeff26d02f694be18cbc063268d9e1780f8cca7b5a3d9"),
    "goal021_response": ("data/processed/response/goal021-pseudoabsence-derivation/2026-07-26/response_layer.csv", "e67298d11d7eb29e6bf8ca055cd8b64cfaf119d193ff0675fff09719ce0616a3"),
}
EXPECTED_ORACLE = {"canonical_rows": 74073, "raster_active_complete": 71057, "canonical_complete": 71023, "raster_complete_outside_canonical": 34, "canonical_incomplete": 3050, "response_rows": 13455, "response_cells": 5407, "response_complete": 5087, "response_incomplete": 320}
EXPECTED_MISSING = {"annmeantemp": 1, "meandiurnrange": 1, "isothermality": 1, "tempseason": 1, "maxtempwarmmonth": 1, "mintempcoldmonth": 1, "tempannrange": 1, "meantempwetq": 1, "meantempdryq": 1, "meantempwarmq": 1, "meantempcoldq": 1, "annprecip": 1, "precipwetmonth": 1, "precipdrymonth": 1, "precipseason": 1, "precipwetq": 1, "precipdryq": 1, "precipwarmq": 1, "precipcoldq": 1, "elevation": 1579, "top_roughness": 1503, "soil_class": 1777, "dist_fw": 1361, "dist_road": 1406, "fpar": 1828, "veg_mvg": 398, "landuse_secondary": 102, "human_footprint": 954}
EXPECTED_RESPONSE_MISSING = {"annmeantemp": 0, "meandiurnrange": 0, "isothermality": 0, "tempseason": 0, "maxtempwarmmonth": 0, "mintempcoldmonth": 0, "tempannrange": 0, "meantempwetq": 0, "meantempdryq": 0, "meantempwarmq": 0, "meantempcoldq": 0, "annprecip": 0, "precipwetmonth": 0, "precipdrymonth": 0, "precipseason": 0, "precipwetq": 0, "precipdryq": 0, "precipwarmq": 0, "precipcoldq": 0, "elevation": 149, "top_roughness": 117, "soil_class": 192, "dist_fw": 97, "dist_road": 109, "fpar": 314, "veg_mvg": 124, "landuse_secondary": 2, "human_footprint": 339}
EXPECTED_RESPONSE_CELL_MISSING = {"annmeantemp": 0, "meandiurnrange": 0, "isothermality": 0, "tempseason": 0, "maxtempwarmmonth": 0, "mintempcoldmonth": 0, "tempannrange": 0, "meantempwetq": 0, "meantempdryq": 0, "meantempwarmq": 0, "meantempcoldq": 0, "annprecip": 0, "precipwetmonth": 0, "precipdrymonth": 0, "precipseason": 0, "precipwetq": 0, "precipdryq": 0, "precipwarmq": 0, "precipcoldq": 0, "elevation": 66, "top_roughness": 50, "soil_class": 85, "dist_fw": 40, "dist_road": 46, "fpar": 112, "veg_mvg": 69, "landuse_secondary": 2, "human_footprint": 161}
EXPECTED_CATEGORICAL_COUNTS = {
    "soil_class": {"2": 15, "3": 3920, "4": 18042, "5": 6169, "6": 719, "7": 1440, "8": 7856, "9": 11615, "10": 2953, "11": 7053, "12": 3217, "13": 8862, "14": 435},
    "veg_mvg": {"1": 8901, "2": 9067, "3": 10180, "4": 1303, "5": 9957, "7": 6, "9": 133, "10": 981, "11": 32, "15": 3938, "16": 11, "17": 772, "18": 3228, "19": 836, "21": 5384, "22": 67, "24": 1943, "25": 16021, "26": 31, "27": 222, "29": 507, "31": 155},
    "landuse_secondary": {"1": 24493, "2": 8730, "3": 5128, "4": 5035, "5": 12571, "6": 7565, "7": 3712, "8": 571, "9": 4, "11": 566, "12": 186, "13": 16, "14": 748, "15": 35, "16": 1827, "17": 48, "18": 2736},
}
EXPECTED_CONTINUOUS_RANGES = {
    "annmeantemp": {"min": 4.0, "max": 14.0}, "meandiurnrange": {"min": 5.0808334, "max": 12.423333}, "isothermality": {"min": 0.38988712, "max": 0.54427326}, "tempseason": {"min": 2.2, "max": 3.9}, "maxtempwarmmonth": {"min": 13.0, "max": 24.4}, "mintempcoldmonth": {"min": -2.2, "max": 8.0}, "tempannrange": {"min": 11.8, "max": 23.3}, "meantempwetq": {"min": 0.2, "max": 16.1}, "meantempdryq": {"min": 2.2, "max": 17.6}, "meantempwarmq": {"min": 8.1, "max": 17.6}, "meantempcoldq": {"min": 0.2, "max": 11.0}, "annprecip": {"min": 443.0, "max": 3387.0}, "precipwetmonth": {"min": 43.0, "max": 365.0}, "precipdrymonth": {"min": 24.0, "max": 164.0}, "precipseason": {"min": 0.10854754, "max": 0.41035748}, "precipwetq": {"min": 125.0, "max": 1044.0}, "precipdryq": {"min": 90.0, "max": 596.0}, "precipwarmq": {"min": 103.0, "max": 604.0}, "precipcoldq": {"min": 111.0, "max": 1044.0}, "elevation": {"min": 0.0, "max": 1493.5328}, "top_roughness": {"min": 0.0, "max": 489.0}, "dist_fw": {"min": 0.0, "max": 31035.115}, "dist_road": {"min": 0.0, "max": 23984.984}, "fpar": {"min": 0.12952025, "max": 1.0}, "human_footprint": {"min": 0.0, "max": 93.0},
}
EXPECTED_SPECIES_AGGREGATES = {
    "dasyurus_maculatus": {"rows": 1310, "complete": 1258, "incomplete": 52}, "dasyurus_viverrinus": {"rows": 1305, "complete": 1244, "incomplete": 61}, "notamacropus_rufogriseus": {"rows": 1561, "complete": 1434, "incomplete": 127}, "pseudocheirus_peregrinus": {"rows": 1151, "complete": 1083, "incomplete": 68}, "sarcophilus_harrisii": {"rows": 3723, "complete": 3573, "incomplete": 150}, "thylogale_billardierii": {"rows": 1601, "complete": 1485, "incomplete": 116}, "trichosurus_vulpecula": {"rows": 1429, "complete": 1336, "incomplete": 93}, "vombatus_ursinus": {"rows": 1375, "complete": 1298, "incomplete": 77},
}
EXPECTED_MULTIPLICITY = {"1": 3391, "2": 767, "3": 24, "4": 150, "5": 172, "6": 85, "7": 56, "8": 762}
EXPECTED_OUTPUTS = {"private_outputs_ignored": True, "roles": {"predictor_cell_map_raw.csv": {"rows": 74073, "bytes": 14049753, "sha256": "0e2082671096bbf80745038bad8329d3bb4fd58dc20b8a4adb146c3d62459542", "schema": list(OUTPUT_FIELDS)}, "predictor_response_cells_raw.csv": {"rows": 5407, "bytes": 1014200, "sha256": "4438d383c6f63e38b0bf61bcbb3812df4e3a26b9e2185d718d2fc03817bbb92f", "schema": list(OUTPUT_FIELDS)}}}

class PredictorExtractionError(ValueError):
    pass

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def _safe_relative(value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise PredictorExtractionError("unsafe_binding_path")
    return Path(value)

def grid_cell_id(lon: float, lat: float) -> str:
    return f"g_{int(round(lon * 10000))}_{int(round(lat * 10000))}"

def serialize_float32(value: float) -> str:
    """Shortest decimal representation that round-trips to the Float32 value."""
    return np.format_float_positional(np.float32(value), unique=True, trim="-")

def _csv_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    s = io.StringIO(newline=""); w = csv.DictWriter(s, fieldnames=OUTPUT_FIELDS, lineterminator="\n"); w.writeheader(); w.writerows([{k: r.get(k, "") for k in OUTPUT_FIELDS} for r in rows]); return s.getvalue().encode()

def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema_version") != "1.0" or plan.get("goal_id") != GOAL_ID: raise PredictorExtractionError("plan_identity_drift")
    bindings = plan.get("bindings", {})
    if {k: (v.get("path"), v.get("sha256")) for k, v in bindings.items()} != EXPECTED_BINDINGS: raise PredictorExtractionError("plan_binding_drift")
    if tuple(plan.get("active_band_indices", [])) != ACTIVE_BAND_INDICES or tuple(plan.get("excluded_band_indices", [])) != EXCLUDED_BAND_INDICES: raise PredictorExtractionError("band_index_contract_drift")
    if tuple(plan.get("active_predictors", [])) != ACTIVE_PREDICTORS or tuple(plan.get("excluded_predictors", [])) != EXCLUDED_PREDICTORS: raise PredictorExtractionError("band_name_contract_drift")
    if tuple(plan.get("categorical_predictors", [])) != CATEGORICAL_PREDICTORS or plan.get("expected_levels") != EXPECTED_LEVELS: raise PredictorExtractionError("categorical_contract_drift")
    if plan.get("expected_oracle") != EXPECTED_ORACLE or plan.get("expected_missingness") != EXPECTED_MISSING or plan.get("expected_response_missingness") != EXPECTED_RESPONSE_MISSING: raise PredictorExtractionError("oracle_contract_drift")
    if plan.get("privacy") != PLAN_PRIVACY or plan.get("stopped_before") != ["partitions", "fitted_transformations", "mapping", "modelling"]: raise PredictorExtractionError("stop_or_privacy_contract_drift")
    if plan.get("outputs", {}).get("schema") != list(OUTPUT_FIELDS): raise PredictorExtractionError("output_schema_drift")
    return {"goal_id": GOAL_ID, "active_predictor_count": len(ACTIVE_PREDICTORS)}

def _validate_grid(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not rows or set(rows[0]) != {"lon", "lat"}: raise PredictorExtractionError("grid_schema_drift")
    seen: set[str] = set(); out=[]
    for r in rows:
        try: lon, lat = float(r["lon"]), float(r["lat"])
        except Exception as e: raise PredictorExtractionError("grid_coordinate_invalid") from e
        key=grid_cell_id(lon,lat)
        if key in seen: raise PredictorExtractionError("duplicate_grid_key")
        seen.add(key); out.append({"grid_cell_id":key,"centroid_lon":serialize_float32(lon),"centroid_lat":serialize_float32(lat),"lon":lon,"lat":lat})
    return out

def _cell_indices(src: rasterio.DatasetReader, lon: float, lat: float) -> tuple[int, int]:
    # The GeoTIFF extent is half a cell beyond the legacy point centres.
    cx = src.bounds.left + abs(src.transform.a) / 2.0; cy = src.bounds.top - abs(src.transform.e) / 2.0
    fx, fy = (lon-cx)/abs(src.transform.a), (cy-lat)/abs(src.transform.e)
    col, row = int(round(fx)), int(round(fy))
    if abs(fx-col) > 1e-7 or abs(fy-row) > 1e-7: raise PredictorExtractionError("grid_raster_alignment_failure")
    if not (0 <= row < src.height and 0 <= col < src.width): raise PredictorExtractionError("grid_raster_outside")
    return row, col

def _is_missing(v: Any, nodata: float | None) -> bool:
    if v is None or not np.isfinite(v): return True
    if nodata is not None and (float(v) == float(nodata) or float(v) <= -3.0e38): return True
    return False

def extract_predictors(root: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    paths = {k: root / _safe_relative(v["path"]) for k,v in plan["bindings"].items()}
    for role,p in paths.items():
        if not p.is_file() or p.is_symlink() or sha256(p) != plan["bindings"][role]["sha256"]: raise PredictorExtractionError(f"binding_drift:{role}")
    with paths["canonical_grid"].open(newline="") as f: grid = _validate_grid(list(csv.DictReader(f)))
    with rasterio.open(paths["stack"]) as src:
        if src.count != 32 or src.width != 468 or src.height != 455 or src.crs.to_epsg() != 4326 or src.transform.b != 0 or src.transform.d != 0: raise PredictorExtractionError("raster_contract_drift")
        arr = src.read(indexes=ACTIVE_BAND_INDICES)
        rows=[]; index_map={}
        for g in grid:
            row,col=_cell_indices(src,g["lon"],g["lat"]); index_map[g["grid_cell_id"]]=(row,col)
            vals={}; missing=[]
            for j,name in enumerate(ACTIVE_PREDICTORS):
                value=arr[j,row,col]
                if _is_missing(value, src.nodata): vals[name]=""; missing.append(name)
                elif name in CATEGORICAL_PREDICTORS:
                    numeric = float(value)
                    if abs(numeric - round(numeric)) > 1e-6: raise PredictorExtractionError("categorical_value_not_integer")
                    vals[name]=str(int(round(numeric)))
                else: vals[name]=serialize_float32(float(value))
            rows.append({"grid_cell_id":g["grid_cell_id"],"centroid_lon":serialize_float32(g["lon"]),"centroid_lat":serialize_float32(g["lat"]),**vals,"predictor_complete":"true" if not missing else "false","missing_predictor_count":str(len(missing)),"missing_predictor_ids":"|".join(missing)})
    rows.sort(key=lambda r:r["grid_cell_id"])
    complete_counts=sum(r["predictor_complete"]=="true" for r in rows)
    return {"rows":rows,"grid":grid,"index_map":index_map,"raster_complete":int(np.sum(np.all(np.isfinite(arr) & (arr > -3e38),axis=0))),"canonical_complete":complete_counts}

def _response_keys(root: Path, plan: Mapping[str, Any]) -> tuple[set[str], dict[str, int], dict[str, int]]:
    p=root / _safe_relative(plan["bindings"]["goal021_response"]["path"])
    if sha256(p) != plan["bindings"]["goal021_response"]["sha256"]: raise PredictorExtractionError("goal021_response_binding_drift")
    with p.open(newline="") as f: rows=list(csv.DictReader(f))
    if len(rows) != EXPECTED_ORACLE["response_rows"]: raise PredictorExtractionError("response_row_count_drift")
    keys=[r["grid_cell_id"] for r in rows]; counts=Counter(keys)
    if any(not k for k in keys) or len(counts)!=EXPECTED_ORACLE["response_cells"]: raise PredictorExtractionError("response_key_drift")
    return set(counts), dict(Counter(r.get("pa_type","") for r in rows)), dict(counts)

def _aggregate(rows: list[dict[str, Any]], fields: Iterable[str]) -> dict[str, int]: return {f: sum(r.get(f, "") == "" for r in rows) for f in fields}

def _build_payloads(root: Path, plan: Mapping[str, Any], result: Mapping[str, Any], full: bool = True) -> dict[str, dict[str, Any]]:
    rows=list(result["rows"]); response_keys, pa_counts, multiplicities = _response_keys(root,plan); by_key={r["grid_cell_id"]:r for r in rows}
    subset=[by_key[k] for k in sorted(response_keys)]
    if len(subset)!=EXPECTED_ORACLE["response_cells"]: raise PredictorExtractionError("response_join_failure")
    miss=_aggregate(rows,ACTIVE_PREDICTORS); rmiss=_aggregate(subset,ACTIVE_PREDICTORS)
    response_path=root / _safe_relative(plan["bindings"]["goal021_response"]["path"])
    with response_path.open(newline="") as stream: response_rows=list(csv.DictReader(stream))
    row_predictors=[by_key[r["grid_cell_id"]] for r in response_rows]
    row_miss=_aggregate(row_predictors, ACTIVE_PREDICTORS)
    row_complete=sum(r["predictor_complete"] == "true" for r in row_predictors)
    if row_miss != EXPECTED_RESPONSE_MISSING or row_complete != 12711: raise PredictorExtractionError("response_missingness_oracle_failure")
    species_aggregates = {}
    for species in sorted({r.get("species_id", "") for r in response_rows}):
        indices = [i for i, r in enumerate(response_rows) if r.get("species_id", "") == species]
        species_aggregates[species] = {"rows": len(indices), "complete": sum(row_predictors[i]["predictor_complete"] == "true" for i in indices), "incomplete": sum(row_predictors[i]["predictor_complete"] == "false" for i in indices)}
    levels={}
    for name in CATEGORICAL_PREDICTORS:
        c=Counter(int(r[name]) for r in rows if r[name] != "")
        observed=sorted(c)
        if observed != EXPECTED_LEVELS[name]: raise PredictorExtractionError(f"categorical_levels_drift:{name}")
        levels[name]={"codes":observed,"counts":{str(k):v for k,v in sorted(c.items())},"labels_status":"unknown_not_authoritative"}
    cont={name:{"min":min(float(r[name]) for r in rows if r[name] != ""),"max":max(float(r[name]) for r in rows if r[name] != "")} for name in ACTIVE_PREDICTORS if name not in CATEGORICAL_PREDICTORS}
    return {
        "source_inventory":{"goal_id":GOAL_ID,"binding_hashes":{k:v["sha256"] for k,v in plan["bindings"].items()},"runtime":RUNTIME_CONTRACT,"raster_contract":{"crs":"EPSG:4326","width":468,"height":455,"bands":32,"nodata":"-3.4e38 Float32","compression":"LZW","interleave":"PIXEL"},"privacy":PLAN_PRIVACY},
        "band_manifest":{"all_bands":[{"index":i+1,"name":n,"role":"active" if i+1 in ACTIVE_BAND_INDICES else "excluded","type":"categorical" if n in CATEGORICAL_PREDICTORS else "continuous"} for i,n in enumerate(ALL_BAND_NAMES)],"active_indices":list(ACTIVE_BAND_INDICES),"excluded_indices":list(EXCLUDED_BAND_INDICES)},
        "categorical_levels":{"variables":levels,"continuous_ranges":cont},
        "missingness_summary":{"canonical":{"rows":len(rows),"complete":sum(r["predictor_complete"]=="true" for r in rows),"incomplete":sum(r["predictor_complete"]=="false" for r in rows),"by_predictor":miss},"response_cells":{"rows":len(subset),"complete":sum(r["predictor_complete"]=="true" for r in subset),"incomplete":sum(r["predictor_complete"]=="false" for r in subset),"by_predictor":rmiss},"response_rows":{"rows":len(response_rows),"complete":row_complete,"incomplete":len(response_rows)-row_complete,"by_predictor":row_miss,"pa_type_counts":pa_counts,"species_aggregates":species_aggregates}},
        "spatial_summary":{"canonical_unique_cells":len(rows),"raster_active_complete":result["raster_complete"],"canonical_intersection_complete":result["canonical_complete"],"raster_complete_outside_canonical":result["raster_complete"]-result["canonical_complete"],"alignment":"exact centre indexing; no nearest/rescue/interpolation","response_unique_cells":len(response_keys),"response_join_audit":{"response_rows":len(response_rows),"unique_predictor_keys":len(response_keys),"unmatched_rows":sum(r["grid_cell_id"] not in by_key for r in response_rows),"duplicate_response_rows":len(response_rows)-len(response_keys),"key_multiplicity_distribution":{str(k):v for k,v in sorted(Counter(multiplicities.values()).items())}},"response_join_unmatched":len(response_keys-set(by_key))},
        "outputs":{"private_outputs_ignored":True,"roles":{name:{"rows":len(rows) if name==OUTPUT_FILES[0] else len(subset),"schema":list(OUTPUT_FIELDS),"sha256":hashlib.sha256(_csv_bytes(rows if name==OUTPUT_FILES[0] else subset)).hexdigest(),"bytes":len(_csv_bytes(rows if name==OUTPUT_FILES[0] else subset))} for name in OUTPUT_FILES}},
        "review":{"readiness":"goal022_complete","classification":"fixed","privacy":PLAN_PRIVACY,"stopped_before":["partitions","fitted_transformations","mapping","modelling"],"blockers":[]},
    }

def assert_evidence_privacy(value: Any) -> None:
    forbidden=("grid_cell_id","coordinate","centroid","row_payload","private_path","site_id","camera_id","timing")
    def walk(obj: Any):
        if isinstance(obj, Mapping):
            for k,v in obj.items():
                kl=str(k).lower()
                if any(t in kl for t in forbidden) and not kl.startswith("tracked_"): raise PredictorExtractionError("tracked_evidence_privacy_failure")
                if isinstance(v,str) and (v.startswith("/Users/") or re.fullmatch(r"g_-?\d+_-?\d+",v)): raise PredictorExtractionError("tracked_evidence_privacy_failure")
                walk(v)
        elif isinstance(obj,list):
            for v in obj: walk(v)
    walk(value)

def _validate_tracked_payloads(plan: Mapping[str, Any], payloads: Mapping[str, Any]) -> None:
    """Validate semantic evidence using only frozen contract constants and plan."""
    expected_names = {name.removesuffix(".json") for name in EVIDENCE_FILES}
    if set(payloads) != expected_names:
        raise PredictorExtractionError("tracked_payload_key_drift")
    bindings = {k: v[1] for k, v in EXPECTED_BINDINGS.items()}
    source = payloads["source_inventory"]
    if source != {"goal_id": GOAL_ID, "binding_hashes": bindings, "runtime": RUNTIME_CONTRACT, "raster_contract": {"crs": "EPSG:4326", "width": 468, "height": 455, "bands": 32, "nodata": "-3.4e38 Float32", "compression": "LZW", "interleave": "PIXEL"}, "privacy": PLAN_PRIVACY}:
        raise PredictorExtractionError("source_inventory_semantic_drift")
    expected_bands = {"all_bands": [{"index": i + 1, "name": n, "role": "active" if i + 1 in ACTIVE_BAND_INDICES else "excluded", "type": "categorical" if n in CATEGORICAL_PREDICTORS else "continuous"} for i, n in enumerate(ALL_BAND_NAMES)], "active_indices": list(ACTIVE_BAND_INDICES), "excluded_indices": list(EXCLUDED_BAND_INDICES)}
    if payloads["band_manifest"] != expected_bands:
        raise PredictorExtractionError("band_manifest_semantic_drift")
    expected_cat = {"variables": {name: {"codes": EXPECTED_LEVELS[name], "counts": EXPECTED_CATEGORICAL_COUNTS[name], "labels_status": "unknown_not_authoritative"} for name in CATEGORICAL_PREDICTORS}, "continuous_ranges": EXPECTED_CONTINUOUS_RANGES}
    if payloads["categorical_levels"] != expected_cat:
        raise PredictorExtractionError("categorical_semantic_drift")
    missing = payloads["missingness_summary"]
    expected_missing = {"canonical": {"rows": 74073, "complete": 71023, "incomplete": 3050, "by_predictor": EXPECTED_MISSING}, "response_cells": {"rows": 5407, "complete": 5087, "incomplete": 320, "by_predictor": EXPECTED_RESPONSE_CELL_MISSING}, "response_rows": {"rows": 13455, "complete": 12711, "incomplete": 744, "by_predictor": EXPECTED_RESPONSE_MISSING, "pa_type_counts": {"presence": 10708, "pseudoabsence": 587, "survey_supported_absence": 2160}, "species_aggregates": EXPECTED_SPECIES_AGGREGATES}}
    if missing != expected_missing:
        raise PredictorExtractionError("missingness_semantic_drift")
    expected_spatial = {"canonical_unique_cells": 74073, "raster_active_complete": 71057, "canonical_intersection_complete": 71023, "raster_complete_outside_canonical": 34, "alignment": "exact centre indexing; no nearest/rescue/interpolation", "response_unique_cells": 5407, "response_join_audit": {"response_rows": 13455, "unique_predictor_keys": 5407, "unmatched_rows": 0, "duplicate_response_rows": 8048, "key_multiplicity_distribution": EXPECTED_MULTIPLICITY}, "response_join_unmatched": 0}
    if payloads["spatial_summary"] != expected_spatial:
        raise PredictorExtractionError("spatial_semantic_drift")
    if payloads["outputs"] != EXPECTED_OUTPUTS:
        raise PredictorExtractionError("outputs_semantic_drift")
    expected_review = {"readiness": "goal022_complete", "classification": "fixed", "privacy": PLAN_PRIVACY, "stopped_before": ["partitions", "fitted_transformations", "mapping", "modelling"], "blockers": []}
    if payloads["review"] != expected_review:
        raise PredictorExtractionError("review_semantic_drift")

def validate_evidence(plan_path: Path, evidence_dir: Path, *, full: bool = False, output_dir: Path | None = None) -> dict[str, Any]:
    plan=json.loads(plan_path.read_text()); validate_plan(plan)
    if not evidence_dir.is_dir(): raise PredictorExtractionError("evidence_missing")
    expected=set(EVIDENCE_FILES)|{"manifest.json"}
    if {p.name for p in evidence_dir.iterdir()} != expected: raise PredictorExtractionError("evidence_footprint_drift")
    for name in EVIDENCE_FILES:
        payload=json.loads((evidence_dir/name).read_text()); assert_evidence_privacy(payload)
    manifest=json.loads((evidence_dir/"manifest.json").read_text());
    if manifest.get("schema_version")!="1.0" or {e["path"] for e in manifest.get("files",[])} != set(EVIDENCE_FILES): raise PredictorExtractionError("manifest_drift")
    for e in manifest["files"]:
        p=evidence_dir/e["path"]
        if e["sha256"]!=sha256(p) or e["bytes"]!=p.stat().st_size: raise PredictorExtractionError("evidence_checksum_failure")
    tracked_payloads = {name.removesuffix(".json"): json.loads((evidence_dir / name).read_text()) for name in EVIDENCE_FILES}
    _validate_tracked_payloads(plan, tracked_payloads)
    if full:
        if output_dir is None: raise PredictorExtractionError("full_output_required")
        if {p.name for p in output_dir.iterdir()} != set(OUTPUT_FILES): raise PredictorExtractionError("output_footprint_drift")
        result=extract_predictors(plan_path.parents[1],plan); payloads=_build_payloads(plan_path.parents[1],plan,result)
        for name in EVIDENCE_FILES:
            if json.loads((evidence_dir/name).read_text()) != payloads[name.removesuffix(".json")]: raise PredictorExtractionError("evidence_replay_failure")
        by={r["grid_cell_id"]:r for r in result["rows"]}; keys,_,_= _response_keys(plan_path.parents[1],plan); subset=[by[k] for k in sorted(keys)]
        if (output_dir/OUTPUT_FILES[0]).read_bytes()!=_csv_bytes(result["rows"]) or (output_dir/OUTPUT_FILES[1]).read_bytes()!=_csv_bytes(subset): raise PredictorExtractionError("output_replay_failure")
    return {"tracked_valid":True,"full_replay":full}

def _publish_staged(stage_output: Path, stage_evidence: Path, output: Path, evidence: Path) -> None:
    """Publish the two directories as a pair, rolling back if the second rename fails."""
    published_output = False
    try:
        stage_output.rename(output)
        published_output = True
        stage_evidence.rename(evidence)
    except Exception:
        if published_output and output.exists() and not stage_output.exists():
            output.rename(stage_output)
        raise

def run_production(root: Path) -> dict[str, Any]:
    plan_path=root/"config/predictor_stack_extraction_plan.json"; plan=json.loads(plan_path.read_text()); validate_plan(plan)
    output=root/"data/processed/predictors/goal022-predictor-stack-extraction/2026-07-26"; evidence=root/"evidence/predictor_stack_extraction/2026-07-26"
    if output.exists() or evidence.exists(): raise PredictorExtractionError("publication_destination_exists")
    chk=subprocess.run(["git","check-ignore","--quiet","--no-index","--",str(output)],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if chk.returncode != 0: raise PredictorExtractionError("private_output_not_ignored")
    result=extract_predictors(root,plan); payloads=_build_payloads(root,plan,result)
    _validate_tracked_payloads(plan, payloads)
    if result["canonical_complete"]!=EXPECTED_ORACLE["canonical_complete"] or result["raster_complete"]!=EXPECTED_ORACLE["raster_active_complete"]: raise PredictorExtractionError("oracle_contract_failure")
    by={r["grid_cell_id"]:r for r in result["rows"]}; keys,_,_= _response_keys(root,plan); subset=[by[k] for k in sorted(keys)]
    output.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix="goal022-stage-",dir=output.parent)); so=staging/"output"; se=staging/"evidence"; so.mkdir(parents=True); se.mkdir()
    try:
        (so/OUTPUT_FILES[0]).write_bytes(_csv_bytes(result["rows"])); (so/OUTPUT_FILES[1]).write_bytes(_csv_bytes(subset))
        for name,payload in payloads.items(): (se/(name+".json")).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
        entries=[{"path":name,"bytes":(se/name).stat().st_size,"sha256":sha256(se/name)} for name in EVIDENCE_FILES]
        (se/"manifest.json").write_text(json.dumps({"schema_version":"1.0","files":entries},indent=2,sort_keys=True)+"\n")
        evidence.parent.mkdir(parents=True,exist_ok=True)
        _publish_staged(so, se, output, evidence)
    finally: shutil.rmtree(staging,ignore_errors=True)
    return {"rows":len(result["rows"]),"response_cells":len(subset),"outputs":payloads["outputs"]}

# Public descriptive aliases used by downstream checks.
extract_raw_predictors = extract_predictors

if __name__ == "__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2]); args=ap.parse_args(); print(run_production(args.root))
