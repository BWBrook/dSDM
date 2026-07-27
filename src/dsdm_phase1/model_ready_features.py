"""Goal026 deterministic, split-fitted model-ready feature substrate.

The module intentionally stops at feature preparation.  It validates the
frozen Goal024/025 inputs, fits six independent standardisers from training
map cells only, preserves nominal categorical values, and exposes a lazy
materialisation API.  No model matrices or fitted models are produced.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np

DATE = "2026-07-27"
GOAL_ID = "goal026-model-ready-feature-substrate-2026-07-27"
ACTIVE = (
    "annmeantemp", "meandiurnrange", "isothermality", "tempseason",
    "maxtempwarmmonth", "mintempcoldmonth", "tempannrange", "meantempwetq",
    "meantempdryq", "meantempwarmq", "meantempcoldq", "annprecip",
    "precipwetmonth", "precipdrymonth", "precipseason", "precipwetq",
    "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness",
    "soil_class", "dist_fw", "dist_road", "fpar", "veg_mvg",
    "landuse_secondary", "human_footprint",
)
CATEGORICAL = ("soil_class", "veg_mvg", "landuse_secondary")
CONTINUOUS = tuple(x for x in ACTIVE if x not in CATEGORICAL)
TRANSFORMS = ("outer", "cv_fold00", "cv_fold01", "cv_fold02", "cv_fold03", "cv_fold04")
MAP_ROWS = 71023
RESPONSE_CELLS = 5087
RESPONSE_ROWS = 12711
EVIDENCE_FILES = ("bindings.json", "feature_contract.json", "fit_parameters.json", "output_metadata.json", "review.json", "summary.json", "support_summary.json", "manifest.json")
STOPPED_BEFORE = ("feature_selection", "model_fitting", "tuning", "resampling_or_class_weighting", "prediction", "performance_comparison", "calibration", "mapping_products", "scientific_synthesis")
SELECTED_OUTER = {"mc08", "mc20", "mc35", "mc40", "mc49"}
EXPECTED_CV_CLUSTERS = {
    "fold00": {"mc00", "mc07", "mc21", "mc25", "mc26", "mc31", "mc32", "mc45", "mc46"},
    "fold01": {"mc01", "mc05", "mc09", "mc10", "mc13", "mc33", "mc37", "mc41", "mc47"},
    "fold02": {"mc02", "mc04", "mc16", "mc17", "mc19", "mc27", "mc39", "mc43", "mc48"},
    "fold03": {"mc03", "mc14", "mc18", "mc22", "mc24", "mc29", "mc30", "mc34", "mc44"},
    "fold04": {"mc06", "mc11", "mc12", "mc15", "mc23", "mc28", "mc36", "mc38", "mc42"},
}

EXPECTED_BINDINGS = {
    "goal024_plan": ("config/predictor_source_repair_domain_freeze_plan.json", "2debc3d01f93c4734d155af733360ac3b4c98eb0305f6034919947df72127c24"),
    "goal024_manifest": ("evidence/predictor_source_repair_domain_freeze/2026-07-26/manifest.json", "a610752079bd2d1e2be7f84829660bb327a349ad34a3e2844837094b2bef8daa"),
    "goal024_review": ("evidence/predictor_source_repair_domain_freeze/2026-07-26/review.json", "d4001628712baadfe4882c5327a61c62d285503477c90e2347218d3ea4e0e4db"),
    "goal024_outputs": ("evidence/predictor_source_repair_domain_freeze/2026-07-26/outputs.json", "254c058d563fd66dfbfe44f789ecf55494399df6dcef01c01812ba4b7d01ac2f"),
    "goal024_support_contract": ("evidence/predictor_source_repair_domain_freeze/2026-07-26/support_contract.json", "f313dbaf4cf0bdf2048103c4f7677d9b0124df17b48b264cbcf87cb9223e4aaa"),
    "goal024_map": ("data/processed/predictors/goal024-predictor-source-repair-domain-freeze/2026-07-26/predictor_cell_map_canonical.csv", "c27b848bd4db81932553ac801029b8e66cf1a1ecd05271343ee2b4d0a3035cc5"),
    "goal024_response_cells": ("data/processed/predictors/goal024-predictor-source-repair-domain-freeze/2026-07-26/predictor_response_cells_canonical.csv", "cf6bd574e3eaa7ed04b6ec6ddbbaa22935b5f03b3fe66bcbdfc4df5691361303"),
    "goal024_response": ("data/processed/predictors/goal024-predictor-source-repair-domain-freeze/2026-07-26/response_layer_canonical.csv", "e6ee507e225ab024a56b8b505fe0e0402d7dac18c7ae34068c8b8141a21ede27"),
    "goal025_map_assignments": ("data/processed/partitions/goal025-spatial-partition/2026-07-26/map_assignments.csv", "ee5a00731810cdd7eb3a9c764b0314c5a338dcdfa39a8cee1885bdd71f450ec0"),
    "goal025_response_partitioned": ("data/processed/partitions/goal025-spatial-partition/2026-07-26/response_partitioned.csv", "b93fbdfa4df2b2d8617dd890cdb7fc4c3aa54ed10c72eed9c9ebc93df18edafc"),
    "goal025_support_diagnostics": ("data/processed/partitions/goal025-spatial-partition/2026-07-26/support_diagnostics.json", "afcb952e603bf8d370845453f697cb93e2092d16d6aaded608af6920cd8a830a"),
    "goal025_plan": ("config/spatial_partition_plan.json", "07ee7ffc88fc2a438ed96cc0bd3190c0b97bc087aed4fd09620a1a8ffa1586dd"),
    "goal025_manifest": ("evidence/spatial_partition/2026-07-26/manifest.json", "dfab4794756652669160708554a7ac901484e6f0cee94f1c34d15130913d679e"),
    "goal025_review": ("evidence/spatial_partition/2026-07-26/review.json", "a05b1114414433ab8e6dbe086e6e536468982865e4a09d1782695eb41c0bee5c"),
    "goal025_outputs": ("evidence/spatial_partition/2026-07-26/outputs.json", "5e72c009fc061d2c27b0ecef782e88189e3ac73127313139f2535add7ea4b3dd"),
    "goal025_response_cell_assignments": ("data/processed/partitions/goal025-spatial-partition/2026-07-26/response_cell_assignments.csv", "f74b1df0ce62b71ee0b0c96b2f51060bfed370eece628dfb1c83d7eea5d6ab84"),
}

class ModelReadyFeatureError(ValueError):
    """Raised when a frozen input or feature contract is invalid."""

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def _safe_path(root: Path, value: str) -> Path:
    p = Path(value)
    if p.is_absolute() or ".." in p.parts or not value:
        raise ModelReadyFeatureError("unsafe_binding_path")
    return root / p

def read_csv(path: Path) -> list[dict[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise ModelReadyFeatureError(f"missing_or_symlink:{path}")
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))

def canonical_rows(rows: Iterable[Mapping[str, Any]], keys: Sequence[str] = ("grid_cell_id",)) -> list[dict[str, Any]]:
    out = [dict(row) for row in rows]
    if any(any(k not in row for k in keys) for row in out):
        raise ModelReadyFeatureError("missing_canonical_key")
    if len({tuple(row[k] for k in keys) for row in out}) != len(out):
        raise ModelReadyFeatureError("duplicate_key")
    return sorted(out, key=lambda row: tuple(str(row[k]) for k in keys))

def _number(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ModelReadyFeatureError("non_numeric_predictor") from exc
    if not math.isfinite(result):
        raise ModelReadyFeatureError("nonfinite_predictor")
    return result

def safe_level_token(value: Any) -> str:
    """Return an injective UTF-8 hex token for a nominal level."""
    return "v_" + str(value).encode("utf-8").hex()

@dataclass(frozen=True)
class TransformParameters:
    transform_id: str
    training_role: str
    training_count: int
    training_hash: str
    means: Mapping[str, float]
    population_sd: Mapping[str, float]
    minima: Mapping[str, float]
    maxima: Mapping[str, float]
    near_zero_variance: tuple[str, ...]
    category_levels: Mapping[str, tuple[str, ...]] = None

    def to_dict(self) -> dict[str, Any]:
        return {"transform_id": self.transform_id, "training_role": self.training_role,
                "training_count": self.training_count, "training_hash": self.training_hash,
                "formula": "z=(x-mean)/population_sd", "ddof": 0, "dtype": "float64",
                "means": dict(self.means), "population_sd": dict(self.population_sd),
                "minima": dict(self.minima), "maxima": dict(self.maxima),
                "near_zero_variance": list(self.near_zero_variance),
                "category_levels": {k: list(v) for k, v in (self.category_levels or {}).items()}}

    def apply_blocks(self, rows: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
        continuous = np.empty((len(rows), len(CONTINUOUS)), dtype=np.float64)
        categorical = np.empty((len(rows), len(CATEGORICAL)), dtype=object)
        for i, row in enumerate(rows):
            for j, name in enumerate(CONTINUOUS):
                continuous[i, j] = (_number(row[name]) - self.means[name]) / self.population_sd[name]
            for j, name in enumerate(CATEGORICAL):
                value = str(row.get(name, ""))
                if self.category_levels is not None and value not in self.category_levels[name]:
                    raise ModelReadyFeatureError("unknown_category")
                categorical[i, j] = value
        continuous.setflags(write=False); categorical.setflags(write=False)
        return continuous, categorical

    def inverse_continuous(self, values: np.ndarray) -> np.ndarray:
        matrix = np.asarray(values, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != len(CONTINUOUS):
            raise ModelReadyFeatureError("continuous_feature_shape")
        out = matrix.copy()
        for j, name in enumerate(CONTINUOUS):
            out[:, j] = out[:, j] * self.population_sd[name] + self.means[name]
        return out

def _training_selector(transform_id: str, assignments: Mapping[str, Mapping[str, str]]) -> set[str]:
    if transform_id == "outer":
        return {k for k, v in assignments.items() if v.get("outer_role") == "outer_train"}
    if transform_id not in TRANSFORMS:
        raise ModelReadyFeatureError("unknown_transform_id")
    fold = "fold" + transform_id[-2:]
    return {k for k, v in assignments.items() if v.get("outer_role") == "outer_train" and v.get("cv_fold") != fold}

def fit_transform(rows: Sequence[Mapping[str, Any]], assignments: Sequence[Mapping[str, Any]], transform_id: str) -> TransformParameters:
    """Fit a split transform from canonical map cells only."""
    maps = canonical_rows(rows)
    amap = {str(x["grid_cell_id"]): dict(x) for x in canonical_rows(assignments)}
    if set(amap) != {str(x["grid_cell_id"]) for x in maps}:
        raise ModelReadyFeatureError("map_assignment_key_drift")
    selected = _training_selector(transform_id, amap)
    train = [r for r in maps if str(r["grid_cell_id"]) in selected]
    if not train:
        raise ModelReadyFeatureError("empty_training_split")
    values: dict[str, np.ndarray] = {}
    for name in CONTINUOUS:
        values[name] = np.asarray([_number(r.get(name)) for r in train], dtype=np.float64)
    means = {name: float(np.mean(vals, dtype=np.float64)) for name, vals in values.items()}
    sds = {name: float(np.std(vals, ddof=0, dtype=np.float64)) for name, vals in values.items()}
    if any(not math.isfinite(x) or x <= 0 for x in sds.values()):
        raise ModelReadyFeatureError("zero_or_nonfinite_sd")
    mins = {name: float(np.min(vals)) for name, vals in values.items()}
    maxs = {name: float(np.max(vals)) for name, vals in values.items()}
    serial = "\n".join(f"{r['grid_cell_id']}" for r in train).encode()
    categories = {name: tuple(sorted({str(r[name]) for r in maps}, key=lambda x: (float(x) if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", x) else math.inf, x))) for name in CATEGORICAL}
    return TransformParameters(transform_id, "outer_train" if transform_id == "outer" else f"outer_train_excluding_{transform_id}", len(train), hashlib.sha256(serial).hexdigest(), means, sds, mins, maxs, tuple(name for name, sd in sds.items() if sd < 1e-8), categories)

def fit_all_transforms(rows: Sequence[Mapping[str, Any]], assignments: Sequence[Mapping[str, Any]]) -> dict[str, TransformParameters]:
    return {name: fit_transform(rows, assignments, name) for name in TRANSFORMS}

class LazyFeatureSubstrate:
    """Lazily apply a frozen transform to canonical rows on request."""
    def __init__(self, rows: Sequence[Mapping[str, Any]], parameters: Mapping[str, TransformParameters]):
        self.rows = tuple(canonical_rows(rows))
        self.parameters = dict(parameters)

    def materialize(self, transform_id: str = "outer", grid_cell_ids: Sequence[str] | None = None, indices: Sequence[int] | None = None) -> "MaterializedFeatures":
        if transform_id not in TRANSFORMS or transform_id not in self.parameters:
            raise ModelReadyFeatureError("unknown_transform_id")
        if grid_cell_ids is not None and indices is not None:
            raise ModelReadyFeatureError("selection_conflict")
        if grid_cell_ids is not None:
            requested = [str(x) for x in grid_cell_ids]
            if len(set(requested)) != len(requested):
                raise ModelReadyFeatureError("duplicate_requested_id")
            by_id = {str(row["grid_cell_id"]): row for row in self.rows}
            if any(x not in by_id for x in requested):
                raise ModelReadyFeatureError("unknown_requested_id")
            selected = [by_id[x] for x in requested]
        elif indices is not None:
            if len(set(indices)) != len(indices) or any(i < 0 or i >= len(self.rows) for i in indices):
                raise ModelReadyFeatureError("invalid_indices")
            selected = [self.rows[i] for i in indices]
        else:
            selected = list(self.rows)
        continuous, categorical = self.parameters[transform_id].apply_blocks(selected)
        return MaterializedFeatures(np.asarray([str(r["grid_cell_id"]) for r in selected], dtype=object), continuous, categorical, CONTINUOUS, CATEGORICAL, transform_id)

    def iter_materialized(self, transform_id: str = "outer", chunk_size: int = 8192) -> Iterator["MaterializedFeatures"]:
        if chunk_size <= 0:
            raise ModelReadyFeatureError("invalid_chunk_size")
        for start in range(0, len(self.rows), chunk_size):
            yield self.materialize(transform_id, indices=range(start, min(start + chunk_size, len(self.rows))))

@dataclass(frozen=True)
class MaterializedFeatures:
    grid_cell_ids: np.ndarray
    continuous: np.ndarray
    categorical: np.ndarray
    continuous_names: tuple[str, ...]
    categorical_names: tuple[str, ...]
    transform_id: str

    def __post_init__(self):
        for array in (self.grid_cell_ids, self.continuous, self.categorical):
            array.setflags(write=False)

def categorical_vocabulary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in CATEGORICAL:
        values = sorted({str(row[name]) for row in rows}, key=lambda x: (float(x) if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", x) else math.inf, x))
        result[name] = {"levels": values, "tokens": [safe_level_token(v) for v in values], "full_indicators": [f"{name}__{safe_level_token(v)}" for v in values], "semantics": "nominal_raw_code"}
    return result

def support_flags(rows: Sequence[Mapping[str, Any]], response: Sequence[Mapping[str, Any]], assignments: Sequence[Mapping[str, Any]], parameters: Mapping[str, TransformParameters]) -> list[dict[str, Any]]:
    """Compute deterministic split-map and species-response support flags."""
    amap = {str(x["grid_cell_id"]): dict(x) for x in assignments}
    map_rows = {str(x["grid_cell_id"]): x for x in rows}
    train_cache: dict[str, tuple[set[str], dict[str, set[str]]]] = {}
    for tid in parameters:
        train_ids = _training_selector(tid, amap)
        train_rows = [map_rows[k] for k in train_ids]
        train_cache[tid] = (train_ids, {n: {str(x[n]) for x in train_rows} for n in CATEGORICAL})
    response_train_cache: dict[tuple[str, str], tuple[dict[str, set[str]], dict[str, tuple[float, float]]]] = {}
    response_rows = [dict(x) for x in response]
    for tid in parameters:
        train_ids = train_cache[tid][0]
        for species in sorted({str(x["species_id"]) for x in response_rows}):
            train_cells = {str(x["grid_cell_id"]) for x in response_rows if str(x["species_id"]) == species and str(x["grid_cell_id"]) in train_ids}
            species_maps = [map_rows[k] for k in train_cells]
            cats = {n: {str(x[n]) for x in species_maps} for n in CATEGORICAL}
            ranges = {n: (min(_number(x[n]) for x in species_maps), max(_number(x[n]) for x in species_maps)) for n in CONTINUOUS} if species_maps else {n: (math.nan, math.nan) for n in CONTINUOUS}
            response_train_cache[(tid, species)] = (cats, ranges)
    out = []
    for row in canonical_rows(response, ("species_id", "grid_cell_id")):
        cell = map_rows.get(str(row["grid_cell_id"]))
        if cell is None:
            raise ModelReadyFeatureError("response_cell_not_in_map")
        role = amap[str(row["grid_cell_id"])]
        for tid, par in parameters.items():
            if tid == "outer":
                transform_role = "training" if role.get("outer_role") == "outer_train" else "assessment"
            elif role.get("outer_role") == "test":
                transform_role = "outer_test_audit"
            elif role.get("cv_fold") == "fold" + tid[-2:]:
                transform_role = "assessment"
            else:
                transform_role = "training"
            _, train_categories = train_cache[tid]
            cat_ok = all(str(cell[n]) in train_categories[n] for n in CATEGORICAL)
            range_ok = all(par.minima[n] <= _number(cell[n]) <= par.maxima[n] for n in CONTINUOUS)
            species_categories, species_ranges = response_train_cache[(tid, str(row["species_id"]))]
            species_cat_ok = all(str(cell[n]) in species_categories[n] for n in CATEGORICAL)
            species_range_ok = all(lo <= _number(cell[n]) <= hi for n, (lo, hi) in species_ranges.items())
            out.append({"species_id": row["species_id"], "grid_cell_id": row["grid_cell_id"], "transform_id": tid, "transform_role": transform_role, "outer_role": role.get("outer_role", ""), "cv_fold": role.get("cv_fold", ""), "marginal_envelope_supported": bool(cat_ok and range_ok), "marginal_envelope_categorical_supported": bool(cat_ok), "marginal_envelope_range_supported": bool(range_ok), "target_species_response_marginal_envelope_supported": bool(species_cat_ok and species_range_ok), "target_species_response_categorical_supported": bool(species_cat_ok), "target_species_response_range_supported": bool(species_range_ok)})
    return out

def validate_bindings(root: Path, plan: Mapping[str, Any] | None = None) -> dict[str, Path]:
    out = {}
    if plan is not None:
        expected_plan = {role: {"path": rel, "sha256": digest} for role, (rel, digest) in EXPECTED_BINDINGS.items()}
        if plan.get("bindings") != expected_plan:
            raise ModelReadyFeatureError("plan_binding_drift")
    for role, (rel, expected) in EXPECTED_BINDINGS.items():
        path = _safe_path(root, rel)
        if not path.is_file() or path.is_symlink():
            raise ModelReadyFeatureError(f"binding_missing:{role}")
        digest = sha256(path)
        if expected and digest != expected:
            raise ModelReadyFeatureError(f"binding_drift:{role}")
        out[role] = path
    return out

def load_frozen_inputs(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    plan_path = root / "config/model_ready_feature_plan.json"
    if not plan_path.is_file():
        raise ModelReadyFeatureError("missing_goal026_plan")
    plan = json.loads(plan_path.read_text())
    validate_plan(plan)
    paths = validate_bindings(root, plan)
    maps = read_csv(paths["goal024_map"])
    cells = read_csv(paths["goal024_response_cells"])
    response = read_csv(paths["goal025_response_partitioned"])
    assignments = read_csv(paths["goal025_map_assignments"])
    response_assignments = read_csv(paths["goal025_response_cell_assignments"])
    if len(maps) != MAP_ROWS or len(cells) != RESPONSE_CELLS or len(response) != RESPONSE_ROWS or len(assignments) != MAP_ROWS or len(response_assignments) != RESPONSE_CELLS:
        raise ModelReadyFeatureError("upstream_count_drift")
    map_ids = {r["grid_cell_id"] for r in maps}
    assignment_ids = {r["grid_cell_id"] for r in assignments}
    cell_ids = {r["grid_cell_id"] for r in cells}
    response_assignment_ids = {r["grid_cell_id"] for r in response_assignments}
    if len(map_ids) != MAP_ROWS or len(assignment_ids) != MAP_ROWS or assignment_ids != map_ids:
        raise ModelReadyFeatureError("duplicate_map_key")
    if len(cell_ids) != RESPONSE_CELLS or response_assignment_ids != cell_ids or not cell_ids.issubset(map_ids):
        raise ModelReadyFeatureError("response_cell_assignment_drift")
    if len({(r["species_id"], r["grid_cell_id"]) for r in response}) != RESPONSE_ROWS:
        raise ModelReadyFeatureError("duplicate_response_key")
    if set(r["grid_cell_id"] for r in response) != cell_ids:
        raise ModelReadyFeatureError("response_cell_identity_drift")
    map_by_id = {r["grid_cell_id"]: r for r in maps}
    for cell in cells:
        source = map_by_id[cell["grid_cell_id"]]
        for name in ACTIVE:
            if str(cell.get(name, "")) != str(source.get(name, "")):
                raise ModelReadyFeatureError("response_cell_predictor_identity_drift")
    allowed_outer = {"outer_train", "test"}
    if any(r.get("outer_role") not in allowed_outer or not r.get("microcluster") or not r.get("macroregion") for r in assignments):
        raise ModelReadyFeatureError("invalid_map_assignment")
    if sum(r["outer_role"] == "outer_train" for r in assignments) != 64270 or sum(r["outer_role"] == "test" for r in assignments) != 6753:
        raise ModelReadyFeatureError("outer_role_count_drift")
    outer_clusters = {r["microcluster"] for r in assignments if r["outer_role"] == "test"}
    if outer_clusters != SELECTED_OUTER:
        raise ModelReadyFeatureError("selected_outer_drift")
    for fold, expected_clusters in EXPECTED_CV_CLUSTERS.items():
        observed = {r["microcluster"] for r in assignments if r.get("cv_fold") == fold}
        if observed != expected_clusters:
            raise ModelReadyFeatureError(f"{fold}_cluster_drift")
    if any(not r.get("cv_fold") for r in assignments if r["outer_role"] == "outer_train"):
        raise ModelReadyFeatureError("blank_cv_role")
    return maps, cells, response, assignments

def json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "goal_id", "date", "action_main_base", "decision_ids", "active_predictors", "categorical_predictors", "transforms", "formula", "ddof", "dtype", "fit_grain", "fit_membership", "categorical_semantics", "encoding_deferred", "support_definitions", "bindings", "expected_counts", "private_destination", "evidence_destination", "private_outputs_ignored", "privacy", "stopped_before"}
    if set(plan) != required:
        raise ModelReadyFeatureError("plan_schema_drift")
    if plan.get("schema_version") != "1.0" or plan.get("goal_id") != GOAL_ID:
        raise ModelReadyFeatureError("plan_identity_drift")
    if plan.get("action_main_base") != "ce75c7fd2efe8c7c87e01e9fa8877da672cbf358" or plan.get("date") != DATE:
        raise ModelReadyFeatureError("plan_base_drift")
    if plan.get("decision_ids") != ["P1-D021", "P1-D022", "P1-D023", "P1-D028"]:
        raise ModelReadyFeatureError("decision_contract_drift")
    if tuple(plan.get("active_predictors", ())) != ACTIVE or tuple(plan.get("categorical_predictors", ())) != CATEGORICAL:
        raise ModelReadyFeatureError("feature_contract_drift")
    if tuple(plan.get("transforms", ())) != TRANSFORMS or plan.get("ddof") != 0 or plan.get("dtype") != "float64":
        raise ModelReadyFeatureError("transform_contract_drift")
    if plan.get("formula") != "z=(x-mean)/population_sd" or plan.get("fit_grain") != "equal weight per canonical D_struct training map cell; 25 continuous predictors only" or plan.get("fit_membership") != "outer_train; CV outer-training cells excluding validation fold" or plan.get("categorical_semantics") != "nominal raw codes; complete D_struct dictionaries and injective UTF-8 hex safe tokens" or plan.get("encoding_deferred") is not True:
        raise ModelReadyFeatureError("policy_contract_drift")
    if plan.get("support_definitions") != {"marginal_envelope": "all complete-map/training-map categorical membership and all 25 univariate training min/max checks; not multivariate environmental, spatial, stationarity, or prediction support", "species_response_lens": "same marginal-envelope checks against target-species training-response cells"}:
        raise ModelReadyFeatureError("support_definition_drift")
    if plan.get("expected_counts") != {"map_cells": MAP_ROWS, "response_cells": RESPONSE_CELLS, "response_rows": RESPONSE_ROWS, "predictors": len(ACTIVE), "transforms": len(TRANSFORMS), "outer_train_map": 64270, "outer_test_map": 6753}:
        raise ModelReadyFeatureError("count_contract_drift")
    if plan.get("privacy") != {"tracked_grid_ids_or_coordinates": False, "tracked_row_payloads": False, "tracked_private_paths": False, "tracked_response_identifiers": False, "tracked_site_or_camera_ids": False, "tracked_private_observation_timing": False}:
        raise ModelReadyFeatureError("privacy_contract_drift")
    if plan.get("private_destination") != "data/processed/features/goal026-model-ready-feature-substrate/2026-07-27" or plan.get("evidence_destination") != "evidence/model_ready_features/2026-07-27" or plan.get("private_outputs_ignored") is not True:
        raise ModelReadyFeatureError("destination_contract_drift")
    if plan.get("stopped_before") != ["feature_selection", "model_fitting", "tuning", "resampling_or_class_weighting", "prediction", "performance_comparison", "calibration", "mapping_products", "scientific_synthesis"]:
        raise ModelReadyFeatureError("stop_contract_drift")
    return {"goal_id": GOAL_ID, "predictors": len(ACTIVE), "transforms": len(TRANSFORMS)}

def validate_evidence(root: Path, evidence_dir: Path, private_dir: Path | None = None, *, full: bool = False) -> dict[str, Any]:
    """Replay tracked manifest and privacy-safe aggregate contract."""
    evidence_dir = Path(evidence_dir)
    upstream_result = None
    if full:
        from dsdm_phase1 import spatial_partition
        upstream_result = spatial_partition.validate_evidence(root / "config/spatial_partition_plan.json", root / "evidence/spatial_partition/2026-07-26", root=root, mode="final", full=True)
    manifest_path = evidence_dir / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ModelReadyFeatureError("missing_manifest")
    manifest = json.loads(manifest_path.read_text())
    expected_privacy = {"tracked_grid_ids_or_coordinates": False, "tracked_row_payloads": False, "tracked_private_paths": False, "tracked_response_identifiers": False, "tracked_site_or_camera_ids": False, "tracked_private_observation_timing": False}
    if set(manifest) != {"schema_version", "goal_id", "files", "privacy"} or manifest.get("goal_id") != GOAL_ID or manifest.get("schema_version") != "1.0" or manifest.get("privacy") != expected_privacy:
        raise ModelReadyFeatureError("manifest_identity_drift")
    actual = {p.name for p in evidence_dir.iterdir()}
    if actual != set(EVIDENCE_FILES) or set(manifest.get("files", {})) != set(EVIDENCE_FILES) - {"manifest.json"} or any((evidence_dir / name).is_symlink() or not (evidence_dir / name).is_file() for name in actual):
        raise ModelReadyFeatureError("evidence_footprint_drift")
    for name, info in manifest["files"].items():
        if set(info) != {"bytes", "sha256"} or not isinstance(info["bytes"], int) or not re.fullmatch(r"[0-9a-f]{64}", info["sha256"]):
            raise ModelReadyFeatureError("manifest_schema_drift")
        path = evidence_dir / name
        if path.stat().st_size != info.get("bytes") or sha256(path) != info.get("sha256"):
            raise ModelReadyFeatureError("evidence_byte_drift")
    def privacy_walk(value: Any, key: str = "") -> None:
        lowered = key.lower()
        if lowered.startswith("tracked_"):
            if value is not False:
                raise ModelReadyFeatureError("tracked_privacy_contract")
            return
        forbidden = ("grid_cell_id", "species_id", "site_id", "camera_id", "source_row", "observation_time", "coordinate")
        if any(token in lowered for token in forbidden):
            raise ModelReadyFeatureError("tracked_privacy_payload")
        if isinstance(value, str):
            if value.startswith("/") or "data/processed" in value or "/private" in value:
                raise ModelReadyFeatureError("tracked_private_path")
        elif isinstance(value, Mapping):
            for k, v in value.items(): privacy_walk(v, str(k))
        elif isinstance(value, list):
            for item in value: privacy_walk(item, key)
    for path in evidence_dir.iterdir():
        if path.name != "manifest.json": privacy_walk(json.loads(path.read_text()))
    bindings_evidence = json.loads((evidence_dir / "bindings.json").read_text())
    if bindings_evidence != {"schema_version": "1.0", "goal_id": GOAL_ID, "bindings": _binding_payload(root)}:
        raise ModelReadyFeatureError("bindings_evidence_drift")
    contract = json.loads((evidence_dir / "feature_contract.json").read_text())
    maps, response_cells, responses, assignments = load_frozen_inputs(root)
    vocabulary = categorical_vocabulary(maps)
    if contract != _feature_contract(vocabulary):
        raise ModelReadyFeatureError("feature_contract_drift")
    parameters = fit_all_transforms(maps, assignments)
    fit_evidence = json.loads((evidence_dir / "fit_parameters.json").read_text())
    if fit_evidence.get("fits") != {name: p.to_dict() for name, p in parameters.items()}:
        raise ModelReadyFeatureError("fit_evidence_drift")
    expected_flags = support_flags(maps, responses, assignments, parameters)
    support_evidence = json.loads((evidence_dir / "support_summary.json").read_text())
    if support_evidence != _support_payload(_support_summary_rows(expected_flags)):
        raise ModelReadyFeatureError("support_evidence_drift")
    summary = json.loads((evidence_dir / "summary.json").read_text())
    if summary != _summary_payload(MAP_ROWS, RESPONSE_CELLS, RESPONSE_ROWS):
        raise ModelReadyFeatureError("summary_count_drift")
    if json.loads((evidence_dir / "review.json").read_text()) != _review_payload():
        raise ModelReadyFeatureError("review_receipt_drift")
    for key, value in manifest.get("privacy", {}).items():
        if value is not False:
            raise ModelReadyFeatureError("privacy_contract_drift")
    if private_dir is not None:
        private_dir = Path(private_dir)
        expected_private = {"response_support.csv", "materialisation_receipt.json"}
        if not private_dir.is_dir() or {p.name for p in private_dir.iterdir()} != expected_private or any(p.is_symlink() or not p.is_file() for p in private_dir.iterdir()):
            raise ModelReadyFeatureError("private_footprint_drift")
        support_path = private_dir / "response_support.csv"
        with support_path.open(newline="") as stream:
            reader = csv.DictReader(stream); private_rows = list(reader)
        private_fields = ["species_id", "grid_cell_id", "transform_id", "transform_role", "outer_role", "cv_fold", "marginal_envelope_supported", "marginal_envelope_categorical_supported", "marginal_envelope_range_supported", "target_species_response_marginal_envelope_supported", "target_species_response_categorical_supported", "target_species_response_range_supported"]
        if reader.fieldnames != private_fields or len(private_rows) != 76266 or len({(r["species_id"], r["grid_cell_id"], r["transform_id"]) for r in private_rows}) != 76266:
            raise ModelReadyFeatureError("private_schema_or_rows_drift")
        def normalise_private(row: Mapping[str, Any]) -> dict[str, Any]:
            out = dict(row)
            for key in ("marginal_envelope_supported", "marginal_envelope_categorical_supported", "marginal_envelope_range_supported", "target_species_response_marginal_envelope_supported", "target_species_response_categorical_supported", "target_species_response_range_supported"):
                if out.get(key) not in {"true", "false"}:
                    raise ModelReadyFeatureError("private_boolean_drift")
                out[key] = out[key] == "true"
            return out
        expected_private_rows = [{k: ("true" if v is True else "false" if v is False else str(v)) for k, v in row.items()} for row in expected_flags]
        if [normalise_private(row) for row in private_rows] != [normalise_private(row) for row in expected_private_rows]:
            raise ModelReadyFeatureError("private_semantic_drift")
        meta = json.loads((evidence_dir / "output_metadata.json").read_text())
        if meta != _output_metadata(MAP_ROWS, RESPONSE_CELLS, RESPONSE_ROWS, private_dir):
            raise ModelReadyFeatureError("output_metadata_drift")
        receipt = json.loads((private_dir / "materialisation_receipt.json").read_text())
        binding_payload = _binding_payload(root)
        substrate = LazyFeatureSubstrate(maps, parameters)
        expected_receipt = _receipt_payload(binding_payload, {name: p.to_dict() for name, p in parameters.items()}, substrate, expected_flags)
        if receipt != expected_receipt:
            raise ModelReadyFeatureError("logical_digest_drift")
    result = {"status": "passed", "files": len(actual)}
    if upstream_result is not None:
        result["full_replay"] = upstream_result
    return result

def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("true" if value is True else "false" if value is False else value) for key, value in row.items()})

def _manifest(directory: Path) -> dict[str, Any]:
    files = {}
    for path in sorted(directory.iterdir()):
        if path.name == "manifest.json" or not path.is_file() or path.is_symlink():
            continue
        files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return {"schema_version": "1.0", "goal_id": GOAL_ID, "files": files, "privacy": {"tracked_grid_ids_or_coordinates": False, "tracked_row_payloads": False, "tracked_private_paths": False, "tracked_response_identifiers": False, "tracked_site_or_camera_ids": False, "tracked_private_observation_timing": False}}

def _binding_payload(root: Path) -> dict[str, Any]:
    return {role: {"role": role, "sha256": sha256(root / rel)} for role, (rel, _) in EXPECTED_BINDINGS.items()}

def _feature_contract(vocabulary: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": "1.0", "goal_id": GOAL_ID, "feature_order": list(ACTIVE), "continuous_predictors": list(CONTINUOUS), "categorical_predictors": list(CATEGORICAL), "raw_categorical_semantics": "nominal_raw_code", "categorical_vocabulary": vocabulary, "transform_ids": list(TRANSFORMS), "formula": "z=(x-mean)/population_sd", "ddof": 0, "dtype": "float64", "identity_shape": ["n_rows"], "continuous_shape": ["n_rows", 25], "categorical_shape": ["n_rows", 3], "continuous_dtype": "float64", "categorical_dtype": "object_nominal_strings", "identity_dtype": "object_string", "canonical_order": ["canonical_key"], "model_family_encoding": "deferred; vocabulary is a lossless schema only", "inverse_tolerance": 1e-10}

def _review_payload() -> dict[str, Any]:
    return {"schema_version": "1.0", "goal_id": GOAL_ID, "criteria_version": "goal026-v1", "reviewer": "dSDM_orchestrator", "reviewed_at": DATE, "receipt_status": "passed", "decision": "final_pre_model_feature_gate", "limitations": ["Goal025 computability and support warnings remain in force", "no performance or transfer claim"], "privacy": {"tracked_grid_ids_or_coordinates": False, "tracked_row_payloads": False, "tracked_private_paths": False, "tracked_response_identifiers": False, "tracked_site_or_camera_ids": False, "tracked_private_observation_timing": False}}

def _summary_payload(map_count: int, response_cell_count: int, response_count: int) -> dict[str, Any]:
    return {"schema_version": "1.0", "goal_id": GOAL_ID, "counts": {"map_cells": map_count, "response_cells": response_cell_count, "response_rows": response_count, "predictors": len(ACTIVE), "transforms": len(TRANSFORMS)}, "stopped_before": list(STOPPED_BEFORE)}

def _support_payload(summary_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"schema_version": "1.0", "goal_id": GOAL_ID, "rows": list(summary_rows), "lens": ["split_training_map", "target_species_training_response"], "support_definition": "marginal_envelope_supported is the conjunction of complete-map/training-map categorical membership and all 25 univariate training min/max checks; it is not multivariate environmental, spatial, stationarity, or prediction support", "membership_unchanged": True}

def _output_metadata(map_count: int, response_cell_count: int, response_count: int, private_dir: Path) -> dict[str, Any]:
    return {"schema_version": "1.0", "goal_id": GOAL_ID, "map_cells": map_count, "response_cells": response_cell_count, "response_rows": response_count, "transformed_map_copies": 0, "lazy_materialisation": True, "private_roles": {name: {"rows": 1 if name.endswith("receipt.json") else 76266, "bytes": (private_dir / name).stat().st_size, "sha256": sha256(private_dir / name)} for name in ("response_support.csv", "materialisation_receipt.json")}}

def _logical_materialisation_digest(substrate: LazyFeatureSubstrate, transform_id: str) -> dict[str, Any]:
    result = substrate.materialize(transform_id)
    digest = hashlib.sha256()
    for value in result.grid_cell_ids.tolist(): digest.update(str(value).encode("utf-8")); digest.update(b"\n")
    digest.update(np.ascontiguousarray(result.continuous).tobytes(order="C"))
    for row in result.categorical.tolist():
        digest.update("\x1f".join(str(x) for x in row).encode("utf-8")); digest.update(b"\n")
    return {"sha256": digest.hexdigest(), "rows": int(result.grid_cell_ids.size), "continuous_shape": list(result.continuous.shape), "categorical_shape": list(result.categorical.shape), "continuous_dtype": str(result.continuous.dtype), "categorical_dtype": str(result.categorical.dtype)}

def _receipt_payload(binding_payload: Mapping[str, Any], fit_payload: Mapping[str, Any], substrate: LazyFeatureSubstrate, flags: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"schema_version": "1.0", "goal_id": GOAL_ID, "rows": len(flags), "transformed_map_copies": 0, "api": "LazyFeatureSubstrate.materialize/iter_materialized", "source_bindings_digest": hashlib.sha256(json_text(binding_payload).encode()).hexdigest(), "fit_parameters_digest": hashlib.sha256(json_text(fit_payload).encode()).hexdigest(), "logical_materialisations": {tid: _logical_materialisation_digest(substrate, tid) for tid in TRANSFORMS}}

def _support_summary_rows(flags: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for tid in TRANSFORMS:
        subset = [x for x in flags if x["transform_id"] == tid]
        for role in ("training", "assessment", "outer_test_audit"):
            part = [x for x in subset if x["transform_role"] == role]
            rows.append({"transform_id": tid, "transform_role": role, "rows": len(part), "marginal_envelope_supported": sum(bool(x["marginal_envelope_supported"]) for x in part), "marginal_envelope_categorical_unsupported": sum(not bool(x["marginal_envelope_categorical_supported"]) for x in part), "marginal_envelope_range_unsupported": sum(not bool(x["marginal_envelope_range_supported"]) for x in part), "target_species_response_marginal_envelope_supported": sum(bool(x["target_species_response_marginal_envelope_supported"]) for x in part)})
    return rows

def _publish_pair(stage_evidence: Path, stage_private: Path, evidence_dir: Path, private_dir: Path) -> None:
    """Atomically publish two new directories, rolling back on either rename."""
    if evidence_dir.exists() or private_dir.exists():
        raise ModelReadyFeatureError("destination_exists")
    published_evidence = False
    published_private = False
    try:
        os.replace(stage_evidence, evidence_dir); published_evidence = True
        os.replace(stage_private, private_dir); published_private = True
    except Exception as exc:
        if published_private and private_dir.exists(): shutil.rmtree(private_dir)
        if published_evidence and evidence_dir.exists(): shutil.rmtree(evidence_dir)
        raise ModelReadyFeatureError("atomic_publication_rollback") from exc

def build_artifacts(root: Path, evidence_dir: Path, private_dir: Path) -> dict[str, Any]:
    """Build the exact aggregate evidence and one lazy private support table."""
    maps, response_cells, responses, assignments = load_frozen_inputs(root)
    parameters = fit_all_transforms(maps, assignments)
    vocabulary = categorical_vocabulary(maps)
    flags = support_flags(maps, responses, assignments, parameters)
    evidence_dir = Path(evidence_dir); private_dir = Path(private_dir)
    evidence_dir.parent.mkdir(parents=True, exist_ok=True)
    private_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="goal026-", dir=str(evidence_dir.parent)))
    stage_evidence = stage / "evidence"; stage_private = stage / "private"
    stage_evidence.mkdir(); stage_private.mkdir()
    binding_payload = _binding_payload(root)
    (stage_evidence / "bindings.json").write_text(json_text({"schema_version": "1.0", "goal_id": GOAL_ID, "bindings": binding_payload}), encoding="utf-8")
    contract = _feature_contract(vocabulary)
    (stage_evidence / "feature_contract.json").write_text(json_text(contract), encoding="utf-8")
    fit_payload = {name: p.to_dict() for name, p in parameters.items()}
    (stage_evidence / "fit_parameters.json").write_text(json_text({"schema_version": "1.0", "goal_id": GOAL_ID, "fits": fit_payload}), encoding="utf-8")
    summary_rows = _support_summary_rows(flags)
    # Aggregate-only support evidence: no cell, species, or source identifiers.
    (stage_evidence / "support_summary.json").write_text(json_text(_support_payload(summary_rows)), encoding="utf-8")
    (stage_evidence / "summary.json").write_text(json_text(_summary_payload(len(maps), len(response_cells), len(responses))), encoding="utf-8")
    private_fields = ["species_id", "grid_cell_id", "transform_id", "transform_role", "outer_role", "cv_fold", "marginal_envelope_supported", "marginal_envelope_categorical_supported", "marginal_envelope_range_supported", "target_species_response_marginal_envelope_supported", "target_species_response_categorical_supported", "target_species_response_range_supported"]
    _write_csv(stage_private / "response_support.csv", flags, private_fields)
    substrate = LazyFeatureSubstrate(maps, parameters)
    receipt = _receipt_payload(binding_payload, fit_payload, substrate, flags)
    (stage_private / "materialisation_receipt.json").write_text(json_text(receipt), encoding="utf-8")
    output_meta = _output_metadata(len(maps), len(response_cells), len(responses), stage_private)
    (stage_evidence / "output_metadata.json").write_text(json_text(output_meta), encoding="utf-8")
    (stage_evidence / "review.json").write_text(json_text(_review_payload()), encoding="utf-8")
    (stage_evidence / "manifest.json").write_text(json_text(_manifest(stage_evidence)), encoding="utf-8")
    # Publish as complete directories. Existing destinations are refused.
    try:
        _publish_pair(stage_evidence, stage_private, evidence_dir, private_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    shutil.rmtree(stage)
    manifest = json.loads((evidence_dir / "manifest.json").read_text())
    return {"evidence": manifest, "private_rows": len(flags), "fit_parameters": fit_payload}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path, default=Path("evidence/model_ready_features/2026-07-27"))
    parser.add_argument("--private", type=Path, default=Path("data/processed/features/goal026-model-ready-feature-substrate/2026-07-27"))
    parser.add_argument("--validate", action="store_true", help="validate existing Goal026 evidence/private footprint")
    parser.add_argument("--full", action="store_true", help="perform full upstream-bound replay and Goal026 recomputation")
    args = parser.parse_args()
    plan = json.loads((args.root / "config/model_ready_feature_plan.json").read_text())
    if args.validate or args.full:
        validate_plan(plan)
        result = validate_evidence(args.root, args.root / args.evidence, args.root / args.private, full=args.full)
        print(json_text(result))
    else:
        print(json_text(build_artifacts(args.root, args.root / args.evidence, args.root / args.private)))
