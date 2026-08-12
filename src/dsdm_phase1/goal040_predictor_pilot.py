"""Goal 040 Stage 8 predictor portability pilot.

The pilot is deliberately response-neutral.  It samples the frozen eligible
cell ledger, obtains one value per candidate layer, and publishes only
aggregate diagnostics.  Cell identities and values are private replay input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import statistics
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from pyproj import Transformer

from .goal040_domain import validate_domain_manifest


CONTRACT_PATH = Path("config/goal040_se_mammal_feasibility.json")
DOMAIN_PATH = Path("metadata/goal040_domain_boundary_manifest.json")
SOURCE_MATRIX_PATH = Path("metadata/goal040_predictor_source_matrix.json")
MANIFEST_PATH = Path("metadata/goal040_predictor_pilot_manifest.json")
DECISION_PATH = Path("metadata/goal040_decision_receipt.json")
CELL_PATH = Path("data/raw/goal040/domain/eligible_cells.csv")
RAW_ROOT = Path("data/raw/goal040/predictor_pilot")
SELECTION_FILE = "selected_cells.csv"
VALUES_FILE = "pilot_values.jsonl"
CHECKPOINT_FILE = "checkpoint.json"
CHECKPOINT_SCHEMA_ID = "goal040-stage8-checkpoint-v2"
ALUM_ZIP = "NLUM_v7_250_ALUMV8_2020_21_alb_package_20241128.zip"
ALUM_URL = "https://www.agriculture.gov.au/sites/default/files/documents/" + ALUM_ZIP
ALUM_SHA256 = "39c05943f10ecd3e13abd8e9d0339c4576220b564883b7d7cf1769525ebf021f"
ALA_FIELDS_URL = "https://api.ala.org.au/spatial-service/fields"
ALA_INTERSECT_URL = "https://spatial.ala.org.au/ws/intersect"
WORLDCLIM_FIELDS = [f"el{value}" for value in range(10978, 10997)]
WORLDCLIM_NAMES = [f"bio{value:02d}" for value in range(1, 20)]
WORLDCLIM_DEFINITIONS = {
    "bio01": "Annual Mean Temperature", "bio02": "Mean Diurnal Range (Mean of monthly (max temp - min temp))", "bio03": "Isothermality (BIO2/BIO7) (x100)", "bio04": "Temperature Seasonality (standard deviation x100)", "bio05": "Max Temperature of Warmest Month", "bio06": "Min Temperature of Coldest Month", "bio07": "Temperature Annual Range (BIO5-BIO6)", "bio08": "Mean Temperature of Wettest Quarter", "bio09": "Mean Temperature of Driest Quarter", "bio10": "Mean Temperature of Warmest Quarter", "bio11": "Mean Temperature of Coldest Quarter", "bio12": "Annual Precipitation", "bio13": "Precipitation of Wettest Month", "bio14": "Precipitation of Driest Month", "bio15": "Precipitation Seasonality (Coefficient of Variation)", "bio16": "Precipitation of Wettest Quarter", "bio17": "Precipitation of Driest Quarter", "bio18": "Precipitation of Warmest Quarter", "bio19": "Precipitation of Coldest Quarter",
}
SOIL_LABELS = {"1": "Vertosol", "2": "Sodosol", "3": "Dermosol", "4": "Chromosol", "5": "Ferrosol", "6": "Kurosol", "7": "Tenosol", "8": "Kandosol", "9": "Hydrosol", "10": "Podosol", "11": "Rudosol", "12": "Calcarasol", "13": "Organosol", "14": "Anthroposol"}
CONTINUOUS = WORLDCLIM_NAMES + ["elevation_mean", "elevation_sd"]
CATEGORICAL = ["nvis_mvg", "soil_order", "alum_secondary"]
REGIONS = ("southeast_mainland", "tasmania")
CELL_FIELDS = ["cell_id", "row_south_to_north", "column_west_to_east", "longitude", "latitude", "state_code", "region"]
RAW_FIELDS = ["cell_id", "longitude", "latitude", "region", *CONTINUOUS, *CATEGORICAL]
TRANSFORM = Transformer.from_crs("EPSG:4326", "EPSG:3577", always_xy=True)
SHA256_RE = set("0123456789abcdef")


class Goal040PredictorError(ValueError):
    """Fail-closed Stage 8 error."""


class Goal040PredictorMissing(Goal040PredictorError):
    """Authoritative spatial nodata/no-feature, retained as missing."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal040PredictorError(reason)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def _http_get(url: str, *, accept: str = "application/json", timeout: int = 120) -> bytes:
    request = Request(url, headers={"Accept": accept, "User-Agent": "dSDM-Goal040-Stage8/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _cells(root: Path) -> list[dict[str, str]]:
    domain = json.loads((root / DOMAIN_PATH).read_text(encoding="utf-8"))
    validate_domain_manifest(domain["exact_study_domain"])
    path = root / CELL_PATH
    expected = domain["exact_study_domain"]["grid"]["ignored_cell_ledger_sha256"]
    _require(path.is_file() and _sha(path) == expected, "eligible_cell_ledger_authority_drift")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require(reader.fieldnames == CELL_FIELDS, "eligible_cell_ledger_schema_drift")
        rows = list(reader)
    _require(len(rows) == domain["exact_study_domain"]["grid"]["eligible_cell_count"], "eligible_cell_denominator_drift")
    _require(all(row["region"] in REGIONS for row in rows), "eligible_cell_region_drift")
    return rows


def select_pilot_cells(rows: Iterable[Mapping[str, Any]], *, per_region: int = 64) -> dict[str, list[dict[str, Any]]]:
    """Select equal-count 8x8 spatial strata with deterministic medoid cells."""
    _require(per_region == 64, "pilot_size_must_be_64")
    grouped = {region: [dict(row) for row in rows if row.get("region") == region] for region in REGIONS}
    selected: dict[str, list[dict[str, Any]]] = {}
    for region, values in grouped.items():
        _require(len(values) >= per_region, "insufficient_eligible_cells")
        for row in values:
            row["_x"], row["_y"] = TRANSFORM.transform(float(row["longitude"]), float(row["latitude"]))
        values.sort(key=lambda row: (row["_x"], str(row["cell_id"])))
        chosen: list[dict[str, Any]] = []
        for east_chunk in np.array_split(np.asarray(values, dtype=object), 8):
            east = list(east_chunk)
            east.sort(key=lambda row: (row["_y"], str(row["cell_id"])))
            for north_chunk in np.array_split(np.asarray(east, dtype=object), 8):
                stratum = list(north_chunk)
                _require(stratum, "empty_spatial_stratum")
                mx = statistics.median(row["_x"] for row in stratum)
                my = statistics.median(row["_y"] for row in stratum)
                def key(row: Mapping[str, Any]) -> tuple[float, str]:
                    return ((row["_x"] - mx) ** 2 + (row["_y"] - my) ** 2, str(row["cell_id"]))
                picked = dict(min(stratum, key=key))
                picked.pop("_x", None); picked.pop("_y", None)
                chosen.append(picked)
        _require(len(chosen) == per_region and len({r["cell_id"] for r in chosen}) == per_region, "pilot_selection_not_unique")
        selected[region] = sorted(chosen, key=lambda row: str(row["cell_id"]))
    return selected


def parse_ala_intersect(payload: Any, fields: list[str] = WORLDCLIM_FIELDS) -> dict[str, float]:
    """Parse ALA spatial intersect responses without inheriting its unit labels."""
    if isinstance(payload, (bytes, bytearray)):
        payload = json.loads(payload.decode())
    rows: Any = payload.get("intersect", payload) if isinstance(payload, dict) else payload
    if isinstance(rows, dict):
        rows = rows.get("data", rows.get("results", rows))
    if isinstance(rows, list) and rows and isinstance(rows[0], dict) and "field" in rows[0]:
        out: dict[str, float] = {}
        _require(len(rows) == len(fields) and {item.get("field") for item in rows} == set(fields), "ALA_intersect_fields_missing")
        for item in rows:
            field = item.get("field")
            if field not in fields:
                continue
            try:
                value = float(item.get("value"))
            except (TypeError, ValueError):
                out[str(field)] = None
                continue
            out[str(field)] = value if math.isfinite(value) else None
        return out
        return out
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        row = rows[0]
    elif isinstance(rows, dict):
        row = rows
    else:
        raise Goal040PredictorError("ALA_intersect_schema_drift")
    out: dict[str, float] = {}
    for field in fields:
        raw = row.get(field)
        if isinstance(raw, dict):
            raw = raw.get("value", raw.get("val"))
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            out[field] = None
            continue
        out[field] = value if math.isfinite(value) else None
    return out


def parse_service_value(payload: Any, *, value_keys: tuple[str, ...] = ("value", "name", "label", "code", "class")) -> str:
    if isinstance(payload, (bytes, bytearray)):
        payload = json.loads(payload.decode())
    candidates: list[Any] = []
    if isinstance(payload, dict):
        candidates.extend(payload.get(key) for key in value_keys)
        for key in ("features", "results", "data", "layers"):
            item = payload.get(key)
            if isinstance(item, list) and item:
                candidates.append(item[0])
            elif isinstance(item, dict):
                candidates.append(item)
    candidates.append(payload)
    for item in candidates:
        if isinstance(item, dict):
            for key in value_keys:
                value = item.get(key)
                if value not in (None, "", "NoData", "nodata"):
                    return str(value)
            attrs = item.get("attributes")
            if isinstance(attrs, dict):
                for key in ("code", "value", "name", "label", "class", *value_keys):
                    value = attrs.get(key)
                    if value not in (None, "", "NoData", "nodata"):
                        return str(value)
            properties = item.get("properties")
            if isinstance(properties, dict):
                for key in value_keys:
                    value = properties.get(key)
                    if value not in (None, "", "NoData", "nodata"):
                        return str(value)
        elif item not in (None, "", "NoData", "nodata") and not isinstance(item, (list, tuple)):
            return str(item)
    raise Goal040PredictorError("categorical_service_value_missing")


def continuous_diagnostic(mainland: Iterable[Any], tasmania: Iterable[Any]) -> dict[str, Any]:
    mainland_values = list(mainland)
    tasmania_values = list(tasmania)
    def clean(values: Iterable[Any]) -> list[float]:
        result = []
        for value in values:
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                result.append(value)
        return result
    m, t = clean(mainland_values), clean(tasmania_values)
    missing = {"mainland": 1 - len(m) / max(1, len(mainland_values)), "tasmania": 1 - len(t) / max(1, len(tasmania_values))}
    mean = float(np.mean(m)) if m else math.nan
    sd = float(np.std(m, ddof=1)) if len(m) > 1 else math.nan
    outside = sum(value < min(m) or value > max(m) for value in t) / max(1, len(t)) if m else 1.0
    z = [((value - mean) / sd) for value in t] if math.isfinite(sd) and sd > 0 else []
    return {"missing_fraction": missing, "finite": bool(m and t), "nonconstant": bool(len(set(m)) > 1), "mainland_range": [min(m), max(m)] if m else None, "tasmania_outside_mainland_range_fraction": outside, "tasmania_z": {"median": float(np.median(z)) if z else None, "iqr": [float(np.quantile(z, .25)), float(np.quantile(z, .75))] if z else None, "max_abs": max(map(abs, z), default=None)}}


def categorical_diagnostic(mainland: Iterable[Any], tasmania: Iterable[Any], *, ontology_validated: bool | None = None) -> dict[str, Any]:
    mainland_values = list(mainland)
    tasmania_values = list(tasmania)
    def clean(values: Iterable[Any]) -> list[str]:
        return [str(value).strip() for value in values if value not in (None, "", "NoData", "nodata")]
    m, t = clean(mainland_values), clean(tasmania_values)
    levels_m, levels_t = set(m), set(t)
    return {"missing_fraction": {"mainland": 1 - len(m) / max(1, len(mainland_values)), "tasmania": 1 - len(t) / max(1, len(tasmania_values))}, "official_codes_only": bool(m and t) if ontology_validated is None else bool(ontology_validated and m and t), "levels": {"mainland": sorted(levels_m), "tasmania": sorted(levels_t)}, "counts": {"mainland": dict(sorted(Counter(m).items())), "tasmania": dict(sorted(Counter(t).items()))}, "tasmania_novel_level_fraction": sum(value not in levels_m for value in t) / max(1, len(t))}


def source_matrix() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for i, field in enumerate(WORLDCLIM_FIELDS, 1):
        units = "degC" if i in {1, 2, 5, 6, 7, 8, 9, 10, 11} else ("percent" if i in {3, 15} else ("dimensionless (SD*100)" if i == 4 else "mm"))
        rows.append({"layer_id": f"bio{i:02d}", "source_product": "WorldClim 2.1", "source_version": "2.1", "definition": WORLDCLIM_DEFINITIONS[f"bio{i:02d}"], "units": units, "reference_period": "1970-2000", "native_resolution": "30 arc-sec", "extraction_resolution": "point at cell centroid", "alignment_and_resampling": "no resampling; ALA spatial field pilot", "nodata_policy": "missing remains missing; no zero fill", "categorical_ontology": None, "mainland_identity": field, "tasmania_identity": field, "decision": "retain", "decision_reason": "frozen common climate candidate", "publisher": "WorldClim", "source_url": "https://www.worldclim.org/data/worldclim21.html", "authoritative_url": "https://api.ala.org.au/spatial-service/fields", "licence": "CC BY 4.0"})
    rows.extend([
        {"layer_id": "elevation_mean", "source_product": "GA SRTM-derived 1 Second DEM", "source_version": "Version 1.0 / 2024 WCS", "definition": "valid native elevation mean per 0.01-degree cell", "units": "m", "reference_period": "static DEM", "native_resolution": "1 arc-sec", "extraction_resolution": "36x36 native coverage per cell bbox", "alignment_and_resampling": "exact bbox; valid-pixel mean", "nodata_policy": "exclude nodata; retain valid zero; fraction recorded", "categorical_ontology": None, "mainland_identity": "coverage 1", "tasmania_identity": "coverage 1", "decision": "retain", "decision_reason": "common terrain source", "publisher": "Geoscience Australia", "source_url": "https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_2024/MapServer/WCSServer", "licence": "CC BY 4.0"},
        {"layer_id": "elevation_sd", "source_product": "GA SRTM-derived 1 Second DEM", "source_version": "Version 1.0 / 2024 WCS", "definition": "valid native elevation SD per 0.01-degree cell", "units": "m", "reference_period": "static DEM", "native_resolution": "1 arc-sec", "extraction_resolution": "36x36 native coverage per cell bbox", "alignment_and_resampling": "exact bbox; valid-pixel sample SD", "nodata_policy": "exclude nodata; retain valid zero; fraction recorded", "categorical_ontology": None, "mainland_identity": "coverage 1", "tasmania_identity": "coverage 1", "decision": "retain", "decision_reason": "within-cell terrain heterogeneity", "publisher": "Geoscience Australia", "source_url": "https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_2024/MapServer/WCSServer", "licence": "CC BY 4.0"},
        {"layer_id": "nvis_mvg", "source_product": "NVIS Major Vegetation Group extant", "source_version": "NVIS 7.0", "definition": "extant Major Vegetation Group", "units": "official code/label", "reference_period": "NVIS 7.0", "native_resolution": "100 m", "extraction_resolution": "centroid identify pilot", "alignment_and_resampling": "centroid only pilot; future deterministic modal pixels", "nodata_policy": "missing is missing", "categorical_ontology": "source codes and labels", "mainland_identity": "NVIS7_0_AUST_EXT_MVG_ALB layer 0", "tasmania_identity": "NVIS7_0_AUST_EXT_MVG_ALB layer 0", "decision": "retain", "decision_reason": "common vegetation ontology", "publisher": "DCCEEW", "source_url": "https://gis.environment.gov.au/gispubmap/rest/services/ogc_services/NVIS_ext_mvg/MapServer", "licence": "CC BY 4.0"},
        {"layer_id": "soil_order", "source_product": "Australian Soil Classification Soil Order", "source_version": "SLGA Release 1 collection v4", "definition": "official soil order", "units": "official code/label", "reference_period": "Release 1", "native_resolution": "3 arc-sec", "extraction_resolution": "centroid WMS pilot", "alignment_and_resampling": "centroid only pilot; future deterministic modal pixels", "nodata_policy": "missing is missing", "categorical_ontology": "TERN official legend values", "mainland_identity": "landscapes:ASC_EV_C_P_AU_TRN_N", "tasmania_identity": "landscapes:ASC_EV_C_P_AU_TRN_N", "decision": "retain", "decision_reason": "common soil ontology", "publisher": "TERN", "source_url": "https://geoserver.tern.org.au/geoserver/landscapes/ASC/ows", "licence": "CC BY 4.0"},
        {"layer_id": "alum_secondary", "source_product": "Land Use of Australia", "source_version": "ABARES NLUM v7 250m / ALUM v8", "definition": "secondary ALUM class modal valid pixel", "units": "official code/label", "reference_period": "2020-21", "native_resolution": "250 m", "extraction_resolution": "modal native pixels per 0.01 cell", "alignment_and_resampling": "pixel centres within exact cell bbox", "nodata_policy": "exclude nodata; missing remains missing", "categorical_ontology": "SECV8N / SECV8", "mainland_identity": "NLUM v7 ALUM v8 exact zip", "tasmania_identity": "NLUM v7 ALUM v8 exact zip", "decision": "retain", "decision_reason": "common land-use ontology", "publisher": "ABARES", "source_url": ALUM_URL, "licence": "CC BY 4.0"},
    ])
    rejected = [
        ("legacy_fpar", "legacy/non-common product identity"), ("human_footprint", "not frozen common authority"), ("human_modification", "not frozen common authority"), ("road_distance", "derived accessibility proxy not required"), ("freshwater_distance", "derived proxy and ontology not common"), ("fire_frequency", "historical process layer not frozen"), ("nvis_mvs_finer", "finer NVIS ontology not required"), ("alum_primary_tertiary", "redundant with retained secondary ALUM class"),
    ]
    return {"schema_version": "goal040-stage8-source-matrix-v1", "goal_id": "goal040-se-mammal-acquisition-feasibility", "layers": rows, "retained_candidate_count": len(rows), "accepted_limitations": ["WorldClim reference baseline is 1970-2000 while occurrence evidence is 2001-2025; later claims are contemporary occurrence relative to long-term baseline climate, not contemporary climate."], "rejected_or_deferred": [{"layer_id": k, "reason": v, "decision": "reject_or_defer"} for k, v in rejected]}


def _fetch_worldclim(lat: float, lon: float) -> dict[str, float]:
    url = f"{ALA_INTERSECT_URL}/{'%2C'.join(WORLDCLIM_FIELDS)}/{lat:.8f}/{lon:.8f}"
    parsed = parse_ala_intersect(_http_get(url))
    return {f"bio{i:02d}": parsed[field] for i, field in enumerate(WORLDCLIM_FIELDS, 1)}


def _fetch_dem(lat: float, lon: float) -> tuple[float, float, float]:
    params = {"SERVICE": "WCS", "VERSION": "1.0.0", "REQUEST": "GetCoverage", "COVERAGE": "1", "CRS": "EPSG:4326", "BBOX": f"{lon-0.005:.5f},{lat-0.005:.5f},{lon+0.005:.5f},{lat+0.005:.5f}", "WIDTH": "36", "HEIGHT": "36", "FORMAT": "GeoTIFF"}
    payload = _http_get("https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_2024/MapServer/WCSServer?" + urlencode(params), accept="image/tiff")
    try:
        import rasterio
        from rasterio.io import MemoryFile
        with MemoryFile(payload) as memory, memory.open() as dataset:
            array = dataset.read(1, masked=True).astype(float)
            values = array.compressed()
    except Exception as exc:
        raise Goal040PredictorError("DEM_payload_invalid") from exc
    _require(len(values) > 0, "DEM_all_nodata")
    return float(np.mean(values)), float(np.std(values, ddof=1)) if len(values) > 1 else 0.0, float(len(values) / 1296)


def _fetch_nvis(lat: float, lon: float) -> str:
    params = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": "4326", "layers": "all:0", "tolerance": "1", "mapExtent": f"{lon-.01},{lat-.01},{lon+.01},{lat+.01}", "imageDisplay": "1000,1000,96", "returnGeometry": "false", "f": "json"}
    payload = json.loads(_http_get("https://gis.environment.gov.au/gispubmap/rest/services/ogc_services/NVIS_ext_mvg/MapServer/identify?" + urlencode(params)).decode())
    _require(isinstance(payload, dict) and "results" in payload and isinstance(payload["results"], list), "NVIS_service_schema")
    if payload["results"] == []:
        raise Goal040PredictorMissing("NVIS_spatial_nodata")
    return parse_service_value(payload, value_keys=("Raster.MVG_NAME",))


def _fetch_soil(lat: float, lon: float) -> str:
    params = {"service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo", "layers": "landscapes:ASC_EV_C_P_AU_TRN_N", "query_layers": "landscapes:ASC_EV_C_P_AU_TRN_N", "info_format": "application/json", "srs": "EPSG:4326", "bbox": f"{lon-.01},{lat-.01},{lon+.01},{lat+.01}", "width": "3", "height": "3", "x": "1", "y": "1"}
    payload = json.loads(_http_get("https://geoserver.tern.org.au/geoserver/landscapes/ASC/ows?" + urlencode(params)).decode())
    _require(isinstance(payload, dict) and "features" in payload and isinstance(payload["features"], list), "soil_service_schema")
    if payload["features"] == []:
        raise Goal040PredictorMissing("soil_spatial_nodata")
    value = parse_service_value(payload, value_keys=("estimated soil class", "value", "name", "label", "code", "class"))
    try:
        code = int(float(value))
    except (TypeError, ValueError):
        raise Goal040PredictorError("soil_order_code_invalid") from None
    _require(1 <= code <= 14, "soil_order_code_invalid")
    return f"{code}:{SOIL_LABELS[str(code)]}"


def _download_alum(root: Path) -> Path:
    target = root / RAW_ROOT / ALUM_ZIP
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(_http_get(ALUM_URL, accept="application/zip", timeout=600))
    _require(_sha(target) == ALUM_SHA256, "ABARES_archive_checksum_drift")
    return target


_ALUM_CACHE: tuple[Any, dict[str, str]] | None = None


def _fetch_alum(root: Path, lat: float, lon: float) -> str:
    global _ALUM_CACHE
    if _ALUM_CACHE is None:
        archive = _download_alum(root)
        import rasterio
        from rasterio.io import MemoryFile
        with zipfile.ZipFile(archive) as source:
            tif = source.read("NLUM_v7_250_ALUMV8_2020_21_alb.tif")
            lookup = source.read("NLUM_v7_250_ALUMV8_2020_21_alb.csv").decode()
        labels: dict[str, str] = {}
        for row in csv.DictReader(io.StringIO(lookup)):
            if row.get("Value") and row.get("SECV8N") and row.get("SECV8N") != "0":
                labels[row["Value"]] = f"{row['SECV8N']}:{row.get('SECV8', '')}"
        _ALUM_CACHE = (MemoryFile(tif).open(), labels)
    dataset, labels = _ALUM_CACHE
    return _alum_modal(dataset, labels, lat, lon)


def _alum_modal(dataset: Any, labels: Mapping[str, str], lat: float, lon: float) -> str:
    """Modal lookup using inverse-transformed native pixel centres."""
    import rasterio
    corners = [TRANSFORM.transform(xlon, xlat) for xlon in (lon - .005, lon + .005) for xlat in (lat - .005, lat + .005)]
    indices = [dataset.index(x, y) for x, y in corners]
    row_min = max(0, min(row for row, _ in indices) - 1); row_max = min(dataset.height - 1, max(row for row, _ in indices) + 1)
    col_min = max(0, min(col for _, col in indices) - 1); col_max = min(dataset.width - 1, max(col for _, col in indices) + 1)
    from rasterio.windows import Window
    window = Window(col_min, row_min, col_max - col_min + 1, row_max - row_min + 1)
    array = dataset.read(1, window=window, masked=True)
    values: list[str] = []
    for row_index, col_index in np.argwhere(~array.mask if np.ma.isMaskedArray(array) else np.ones(array.shape, dtype=bool)):
        value = int(array[row_index, col_index])
        if value == 0:
            continue
        x, y = dataset.xy(row_min + int(row_index), col_min + int(col_index), offset="center")
        cell_lon, cell_lat = TRANSFORM.transform(x, y, direction="INVERSE")
        if lon - 0.005 <= cell_lon <= lon + 0.005 and lat - 0.005 <= cell_lat <= lat + 0.005:
            values.append(str(value))
    if not values:
        raise Goal040PredictorMissing("ABARES_cell_all_nodata")
    counts = Counter(values)
    code = min(counts, key=lambda value: (-counts[value], int(value)))
    _require(code in labels, "ABARES_lookup_code_invalid")
    return labels[code]


def _row_for_cell(root: Path, cell: Mapping[str, Any]) -> dict[str, Any]:
    lat, lon = float(cell["latitude"]), float(cell["longitude"])
    values: dict[str, Any] = {"cell_id": cell["cell_id"], "longitude": lon, "latitude": lat, "region": cell["region"]}
    values.update(_fetch_worldclim(lat, lon))
    mean, sd, valid = _fetch_dem(lat, lon)
    values.update({"elevation_mean": mean, "elevation_sd": sd, "elevation_valid_fraction": valid})
    try:
        values["nvis_mvg"] = _fetch_nvis(lat, lon)
    except Goal040PredictorMissing:
        values["nvis_mvg"] = None
    try:
        values["soil_order"] = _fetch_soil(lat, lon)
    except Goal040PredictorMissing:
        values["soil_order"] = None
    try:
        values["alum_secondary"] = _fetch_alum(root, lat, lon)
    except Goal040PredictorMissing:
        values["alum_secondary"] = None
    return values


def _write_private(root: Path, selected: dict[str, list[dict[str, Any]]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = root / RAW_ROOT
    output.mkdir(parents=True, exist_ok=True)
    selection_path = output / SELECTION_FILE
    with selection_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CELL_FIELDS)
        writer.writeheader()
        writer.writerows(row for region in REGIONS for row in selected[region])
    values_path = output / VALUES_FILE
    with values_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    # Paths are intentionally omitted from the tracked manifest.  Replay uses
    # the fixed ignored-root names above, while the manifest carries only
    # privacy-safe content receipts.
    return {"selection": {"sha256": _sha(selection_path), "bytes": selection_path.stat().st_size, "rows": len(rows)}, "values": {"sha256": _sha(values_path), "bytes": values_path.stat().st_size, "rows": len(rows)}}


def _aggregate(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"continuous": {}, "categorical": {}}
    for layer in CONTINUOUS:
        result["continuous"][layer] = continuous_diagnostic([row.get(layer) for row in rows if row["region"] == REGIONS[0]], [row.get(layer) for row in rows if row["region"] == REGIONS[1]])
    for layer in CATEGORICAL:
        values = [row.get(layer) for row in rows]
        valid = (lambda value: isinstance(value, str) and value.split(":", 1)[0] in SOIL_LABELS and value.split(":", 1)[1] == SOIL_LABELS[value.split(":", 1)[0]]) if layer == "soil_order" else (lambda value: isinstance(value, str) and bool(value.strip()))
        ontology_ok = all(valid(value) for value in values if value not in (None, "")) and any(value not in (None, "") for value in values)
        result["categorical"][layer] = categorical_diagnostic([row.get(layer) for row in rows if row["region"] == REGIONS[0]], [row.get(layer) for row in rows if row["region"] == REGIONS[1]], ontology_validated=ontology_ok)
    return result


def _read_private(root: Path) -> list[dict[str, Any]]:
    path = root / RAW_ROOT / VALUES_FILE
    _require(path.is_file(), "predictor_private_values_missing")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    _require(len(rows) == 128, "predictor_private_row_count_drift")
    _require(all(set(row) >= set(RAW_FIELDS) for row in rows), "predictor_private_schema_drift")
    selected = select_pilot_cells(_cells(root))
    expected = {row["cell_id"]: row for region in REGIONS for row in selected[region]}
    _require(set(expected) == {row.get("cell_id") for row in rows}, "predictor_private_selection_mismatch")
    for row in rows:
        cell = expected[row["cell_id"]]
        _require(row.get("region") == cell["region"] and float(row.get("longitude")) == float(cell["longitude"]) and float(row.get("latitude")) == float(cell["latitude"]), "predictor_private_coordinate_mismatch")
    return rows


def run_pilot(root: Path, *, row_fetcher: Callable[[Path, Mapping[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    matrix = source_matrix()
    (root / SOURCE_MATRIX_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / SOURCE_MATRIX_PATH).write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    selected = select_pilot_cells(_cells(root))
    selection_digest = _digest({region: [row["cell_id"] for row in selected[region]] for region in REGIONS})
    checkpoint_path = root / RAW_ROOT / CHECKPOINT_FILE
    checkpoint = None
    if checkpoint_path.is_file():
        try: checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): checkpoint = None
    checkpoint_valid = checkpoint == {"schema_id": CHECKPOINT_SCHEMA_ID, "source_matrix_sha256": _sha(root / SOURCE_MATRIX_PATH), "selection_digest": selection_digest}
    if not checkpoint_valid:
        (root / RAW_ROOT).mkdir(parents=True, exist_ok=True)
        (root / RAW_ROOT / VALUES_FILE).write_text("", encoding="utf-8")
        rows = []
    checkpoint = {"schema_id": CHECKPOINT_SCHEMA_ID, "source_matrix_sha256": _sha(root / SOURCE_MATRIX_PATH), "selection_digest": selection_digest}
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True) + "\n", encoding="utf-8")
    values_path = root / RAW_ROOT / VALUES_FILE
    rows: list[dict[str, Any]] = []
    if checkpoint_valid and values_path.is_file():
        rows = [json.loads(line) for line in values_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        _require(len(rows) <= 128, "predictor_partial_row_count_drift")
    selected_by_id = {row["cell_id"]: row for region in REGIONS for row in selected[region]}
    rows = [row for row in rows if row.get("cell_id") in selected_by_id and row.get("region") == selected_by_id[row["cell_id"]]["region"] and float(row.get("longitude")) == float(selected_by_id[row["cell_id"]]["longitude"]) and float(row.get("latitude")) == float(selected_by_id[row["cell_id"]]["latitude"])]
    _require(len({row.get("cell_id") for row in rows}) == len(rows), "predictor_checkpoint_duplicate")
    done = {row["cell_id"] for row in rows}
    fetch = row_fetcher or _row_for_cell
    for region in REGIONS:
        for cell in selected[region]:
            if cell["cell_id"] in done:
                continue
            row = fetch(root, cell)
            rows.append(row)
            values_path.parent.mkdir(parents=True, exist_ok=True)
            with values_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    private = _write_private(root, selected, rows)
    aggregate = _aggregate(rows)
    manifest = {"schema_version": "goal040-stage8-predictor-pilot-v1", "goal_id": "goal040-se-mammal-acquisition-feasibility", "status": "complete_raw_replay_required", "retrieved_at": _now(), "selection": {"method": "8 equal-count easting strata x 8 equal-count northing strata; bivariate projected median nearest; deterministic identity tie", "cells_per_region": 64, "selection_digest": _digest({region: [row["cell_id"] for row in selected[region]] for region in REGIONS})}, "source_matrix_sha256": _sha(root / SOURCE_MATRIX_PATH), "private_outputs": private, "aggregate": aggregate, "privacy": {"tracked_cell_ids": False, "tracked_coordinates": False, "tracked_row_values": False, "tracked_private_paths": False}, "outer_access": 0, "response_access": 0, "model_fits": 0}
    (root / MANIFEST_PATH).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def validate_pilot(root: Path, *, require_raw: bool = False, check_receipt: bool = True) -> dict[str, Any]:
    matrix = json.loads((root / SOURCE_MATRIX_PATH).read_text(encoding="utf-8"))
    _require(matrix == source_matrix(), "source_matrix_semantic_drift")
    manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    _require(manifest.get("schema_version") == "goal040-stage8-predictor-pilot-v1", "predictor_manifest_schema_drift")
    _require(manifest.get("source_matrix_sha256") == _sha(root / SOURCE_MATRIX_PATH), "predictor_source_binding_drift")
    _require(manifest.get("selection", {}).get("cells_per_region") == 64, "predictor_selection_size_drift")
    _require(manifest.get("privacy") == {"tracked_cell_ids": False, "tracked_coordinates": False, "tracked_row_values": False, "tracked_private_paths": False}, "predictor_privacy_drift")
    receipt_path = root / DECISION_PATH
    if receipt_path.is_file() and check_receipt:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        _require(receipt.get("pilot_manifest_sha256") == _sha(root / MANIFEST_PATH), "predictor_receipt_manifest_binding")
        _require(receipt.get("receipt_sha256") == _digest({key: value for key, value in receipt.items() if key != "receipt_sha256"}), "predictor_receipt_hash_drift")
        manifest_for_decision = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
        expected_payload = _decision_payload(manifest_for_decision)
        _require(all(receipt.get(key) == value for key, value in expected_payload.items()), "predictor_receipt_semantic_drift")
    if require_raw:
        selected = select_pilot_cells(_cells(root))
        selection_path = root / RAW_ROOT / SELECTION_FILE
        with selection_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle); selected_rows = list(reader)
        expected_selection = [row for region in REGIONS for row in selected[region]]
        _require(reader.fieldnames == CELL_FIELDS and len(selected_rows) == 128 and len({row["cell_id"] for row in selected_rows}) == 128, "predictor_selection_file_schema")
        _require(selected_rows == [{field: str(row.get(field, "")) for field in CELL_FIELDS} for row in expected_selection], "predictor_selection_file_mismatch")
        rows = _read_private(root)
        expected = _aggregate(rows)
        _require(manifest.get("aggregate") == expected, "predictor_aggregate_replay_drift")
        for role in ("selection", "values"):
            receipt = manifest["private_outputs"][role]
            filename = SELECTION_FILE if role == "selection" else VALUES_FILE
            path = root / RAW_ROOT / filename
            _require(path.is_file() and _sha(path) == receipt["sha256"], "predictor_private_digest_drift")
    return {"status": "validated_raw_replay" if require_raw else "validated_tracked_only", "retained": matrix["retained_candidate_count"], "cells": 128}


def _decision_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    aggregate = manifest["aggregate"]
    retained, rejected = [], []
    for layer in CONTINUOUS:
        d = aggregate["continuous"][layer]
        (retained if all(d["missing_fraction"][label] <= .05 for label in ("mainland", "tasmania")) and d["finite"] and d["nonconstant"] else rejected).append(layer)
    for layer in CATEGORICAL:
        d = aggregate["categorical"][layer]
        (retained if all(d["missing_fraction"][label] <= .10 for label in ("mainland", "tasmania")) and d["official_codes_only"] else rejected).append(layer)
    decision = "ready" if set(retained) >= {"bio01", "elevation_mean", "elevation_sd", "nvis_mvg"} else "repair"
    return {"decision": decision, "retained_layers": retained, "rejected_layers": rejected, "retained_count": len(retained), "reason": "prespecified portability thresholds; optional layers may be rejected while a coherent climate+terrain+vegetation/landscape panel remains" if decision == "ready" else "one or more required common-source/coverage gates failed"}


def finalise(root: Path) -> dict[str, Any]:
    validate_pilot(root, require_raw=True, check_receipt=False)
    manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    payload = _decision_payload(manifest)
    receipt = {"schema_version": "goal040-stage8-decision-v1", "goal_id": "goal040-se-mammal-acquisition-feasibility", "stage": "stage8_predictor_portability", **payload, "source_matrix_sha256": manifest["source_matrix_sha256"], "pilot_manifest_sha256": _sha(root / MANIFEST_PATH), "diagnostics": {"continuous_layers": len(CONTINUOUS), "categorical_layers": len(CATEGORICAL), "cells": 128}, "outer_access": 0, "response_access": 0, "model_fits": 0}
    receipt["receipt_sha256"] = _digest(receipt)
    (root / DECISION_PATH).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("predictor-pilot", "validate-predictor-pilot", "finalise"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--raw-replay", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.stage == "predictor-pilot":
        result = run_pilot(root)
    elif args.stage == "validate-predictor-pilot":
        result = validate_pilot(root, require_raw=args.raw_replay)
    else:
        result = finalise(root)
    print(json.dumps(result, indent=2, sort_keys=True))


__all__ = ["Goal040PredictorError", "source_matrix", "select_pilot_cells", "parse_ala_intersect", "parse_service_value", "continuous_diagnostic", "categorical_diagnostic", "run_pilot", "validate_pilot", "finalise", "main"]


if __name__ == "__main__":
    main()
