"""Immutable Goal028 modelling contracts and the fail-closed data boundary."""

from __future__ import annotations

import hashlib
import json
import csv
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


class ModelingContractError(ValueError):
    """Raised when a Goal028 contract or leakage boundary is violated."""


EXPECTED_CONFIG_SHA256 = "04f855a9244d8e419797bb26f5f010c9d6fca16459faa42f24530b0287581403"
EXPECTED_BINDING_ROLES = ["goal021_plan", "goal021_manifest", "goal021_outputs", "goal021_response", "goal024_plan", "goal024_manifest", "goal024_review", "goal024_outputs", "goal024_support", "goal024_map", "goal024_response_cells", "goal024_response", "goal025_plan", "goal025_manifest", "goal025_review", "goal025_outputs", "goal025_assignments", "goal025_response_partitioned", "goal025_support", "goal026_plan", "goal026_manifest", "goal026_review", "goal026_feature_contract", "goal026_fit_parameters", "goal026_support", "goal027_goal", "goal027_decision", "goal027_protocol", "pyproject", "uv_lock"]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative_path(root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ModelingContractError("binding_path_not_relative")
    resolved = (root / path).resolve()
    if root.resolve() not in resolved.parents and resolved != root.resolve():
        raise ModelingContractError("binding_path_escape")
    return resolved


def load_run_config(root: Path, path: Path) -> Mapping[str, Any]:
    path = Path(path)
    if not path.is_absolute():
        path = Path(root) / path
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    validate_run_config(Path(root), config)
    return config


def validate_run_config(root: Path, config: Mapping[str, Any]) -> None:
    if hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest() != EXPECTED_CONFIG_SHA256:
        raise ModelingContractError("config_digest_mismatch")
    required = [
        "identity", "bindings", "estimand", "response", "partitions", "subsets",
        "features", "models", "neural", "selection", "threshold", "replication",
        "artifacts", "compute", "scope",
    ]
    if list(config) != required:
        raise ModelingContractError("config_sections_mismatch")
    identity = config["identity"]
    if identity != {"schema_version": "1.0", "goal_id": "goal028-modeling-foundation-preflight-2026-07-30", "protocol_version": "0.1", "master_seed": "dsdm-goal028-v1", "created_at": "2026-07-30"}:
        raise ModelingContractError("identity_contract_mismatch")
    if config["estimand"].get("goal028_estimates_estimand") is not False:
        raise ModelingContractError("estimand_contract_mismatch")
    if config["partitions"].get("folds") != [f"fold{i:02d}" for i in range(5)] or config["partitions"].get("transforms") != [f"cv_fold{i:02d}" for i in range(5)] or config["partitions"].get("outer_vault") != "sealed":
        raise ModelingContractError("partition_contract_mismatch")
    if config["subsets"].get("ladders") != ["ladder00", "ladder01", "ladder02"] or config["subsets"].get("full_alias") is not True:
        raise ModelingContractError("subset_contract_mismatch")
    if config["features"].get("categorical_fit_scope") != "cv_training_rows" or config["features"].get("unknown_category") != "all_zero_with_count":
        raise ModelingContractError("feature_contract_mismatch")
    expected_families = ["intercept", "elastic_net", "gam", "random_forest", "hist_gradient_boosting", "shallow_ann", "residual_mlp"]
    if config["models"].get("families") != expected_families:
        raise ModelingContractError("model_family_registry_mismatch")
    expected_ids = ["null00", *[f"enet{i:02d}" for i in range(10)], *[f"gam{i:02d}" for i in range(5)], *[f"rf{i:02d}" for i in range(7)], *[f"hgb{i:02d}" for i in range(7)], *[f"ann{i:02d}" for i in range(6)], *[f"resmlp{i:02d}" for i in range(3)]]
    candidates = config["models"].get("candidates", [])
    if [candidate.get("id") for candidate in candidates] != expected_ids:
        raise ModelingContractError("candidate_registry_mismatch")
    parameters = config["models"].get("candidate_parameters")
    if not isinstance(parameters, Mapping) or set(parameters) != set(expected_ids):
        raise ModelingContractError("candidate_parameters_incomplete")
    for candidate in candidates:
        declared = {key: value for key, value in candidate.items() if key not in {"family", "id"}}
        if declared != dict(parameters[candidate["id"]]):
            raise ModelingContractError(f"candidate_parameter_drift:{candidate.get('id')}")
    if config["models"].get("real_preflight_ids") not in (None, ["null00", "enet03", "enet07", "gam01", "rf03", "hgb03", "ann03", "resmlp01", "resmlp02"]):
        raise ModelingContractError("preflight_registry_mismatch")
    gam = config["models"].get("gam_defaults", {})
    if gam.get("spline_order") != 3 or gam.get("lambda_application") != "every_continuous_spline_and_categorical_linear_term" or gam.get("continuous_term") != "cubic" or gam.get("categorical_term") != "linear":
        raise ModelingContractError("gam_defaults_mismatch")
    neural = config["neural"]
    if neural.get("batch_size") != 128 or neural.get("effective_batch_size_min") != 1 or neural.get("retain_partial_batch") is not True or neural.get("row_order") != "canonical_RowKey_sort" or neural.get("minibatch_order") != "seeded_cpu_randperm_per_epoch" or neural.get("dtype") != "float32" or neural.get("returned_score_dtype") != "float64" or neural.get("returned_metric_dtype") != "float64":
        raise ModelingContractError("neural_batch_contract_mismatch")
    if neural.get("optimizer") != {"name": "AdamW", "betas": [0.9, 0.999], "eps": 1e-8, "amsgrad": False, "foreach": False, "fused": False} or neural.get("scheduler") is not None or neural.get("gradient_clipping") is not False:
        raise ModelingContractError("neural_optimizer_contract_mismatch")
    if neural.get("epoch_range") != [1, 300] or neural.get("stopping_evaluation") != "full_batch_loss" or neural.get("min_delta") != 0.0 or neural.get("patience_semantics") != "strict_loss_improvement_earliest_tie" or neural.get("selection_seed") != "seed00" or neural.get("diagnostic_seed") != "seed01_only" or neural.get("encoder_fit_scope") != "complete_E_v":
        raise ModelingContractError("neural_stopping_contract_mismatch")
    if identity.get("master_seed") != "dsdm-goal028-v1":
        raise ModelingContractError("master_seed_mismatch")
    if config["scope"].get("real_outer_attempted_open_limit") != 0 or config["scope"].get("real_outer_open_limit") != 0:
        raise ModelingContractError("outer_limits_must_be_zero")
    if config["response"].get("row_weight") != 1 or config["response"].get("resampling") is not False:
        raise ModelingContractError("response_contract_mismatch")
    bindings = config.get("bindings", {})
    if not isinstance(bindings, Mapping):
        raise ModelingContractError("bindings_not_mapping")
    required_roles = bindings.get("required_roles")
    if required_roles != EXPECTED_BINDING_ROLES or any(role not in bindings for role in required_roles):
        raise ModelingContractError("required_binding_role_missing")
    authority_digests: dict[str, str] = {}
    for authority_name in ("config/pseudoabsence_derivation_plan.json", "config/predictor_source_repair_domain_freeze_plan.json", "config/spatial_partition_plan.json", "config/model_ready_feature_plan.json"):
        authority_path = Path(root) / authority_name
        if authority_path.is_file():
            try:
                authority = json.loads(authority_path.read_text(encoding="utf-8"))
                for candidate in (authority.get("bindings", {}),):
                    for item in candidate.values():
                        if isinstance(item, Mapping) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str):
                            authority_digests[item["path"]] = item["sha256"]
            except (OSError, json.JSONDecodeError):
                pass
    for role, record in bindings.items():
        if role == "required_roles":
            continue
        if not isinstance(record, Mapping) or not isinstance(record.get("path"), str):
            raise ModelingContractError(f"binding_invalid:{role}")
        expected = record.get("sha256")
        if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            raise ModelingContractError(f"binding_digest_invalid:{role}")
        raw_target = Path(root) / record["path"]
        if raw_target.is_symlink():
            raise ModelingContractError(f"binding_not_regular:{role}")
        target = _safe_relative_path(Path(root), record["path"])
        # Private upstream products are intentionally not opened by tracked validation.
        if record.get("private", False):
            # Private product bytes are never opened by tracked validation; their
            # frozen digest is carried as provenance for the authorised factory.
            authority_digest = authority_digests.get(record["path"])
            if authority_digest is None:
                raise ModelingContractError(f"private_binding_authority_missing:{role}")
            if authority_digest != expected:
                raise ModelingContractError(f"private_binding_authority_mismatch:{role}")
            continue
        if not target.is_file():
            raise ModelingContractError(f"binding_not_regular:{role}")
        if not isinstance(expected, str) or sha256_file(target) != expected:
            raise ModelingContractError(f"binding_digest_mismatch:{role}")
    pyproject_path = Path(root) / "pyproject.toml"
    if not pyproject_path.is_file():
        raise ModelingContractError("pyproject_missing")
    with pyproject_path.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    if project.get("requires-python") != ">=3.12,<3.13":
        raise ModelingContractError("python_version_contract_mismatch")
    names = {re.split(r"[<>=!~\[]", dependency, maxsplit=1)[0].lower() for dependency in project.get("dependencies", [])}
    if not {"numpy", "scipy", "scikit-learn", "pygam", "pyarrow", "torch"} <= names:
        raise ModelingContractError("approved_dependency_missing")
    prohibited = {"keras", "tensorflow", "skorch", "xgboost", "optuna"}
    if prohibited & names:
        raise ModelingContractError("prohibited_dependency_present")


@dataclass(frozen=True, order=True)
class TaskKey:
    species_id: str
    transform_id: str
    fraction_id: str
    ladder_id: str
    model_family: str
    candidate_id: str
    seed_label: str


@dataclass(frozen=True, order=True)
class RowKey:
    species_id: str
    grid_cell_id: str


@dataclass(frozen=True)
class RowSet:
    keys: tuple[RowKey, ...]
    pa: np.ndarray
    response_source: tuple[str, ...]
    microcluster: tuple[str, ...]
    row_weight: np.ndarray | None = None

    def __post_init__(self) -> None:
        keys = tuple(self.keys)
        for key in keys:
            if not isinstance(key, RowKey) or type(key.species_id) is not str or type(key.grid_cell_id) is not str or not key.species_id or not key.grid_cell_id:
                raise ModelingContractError("row_key_invalid")
        if len(set(keys)) != len(keys):
            raise ModelingContractError("duplicate_species_cell")
        n = len(keys)
        raw_pa = tuple(self.pa)
        if any(type(value) not in (int, np.int8, np.int16, np.int32, np.int64) or int(value) not in (0, 1) for value in raw_pa):
            raise ModelingContractError("pa_not_exact_binary_integer")
        pa = np.asarray(raw_pa, dtype=np.int8).reshape(-1)
        raw_source = tuple(self.response_source)
        raw_micro = tuple(self.microcluster)
        if any(type(x) is not str or not x for x in raw_source) or any(type(x) is not str or not x for x in raw_micro):
            raise ModelingContractError("source_or_microcluster_invalid")
        source = raw_source
        micro = raw_micro
        if len(pa) != n or len(source) != n or len(micro) != n:
            raise ModelingContractError("rowset_length_mismatch")
        if not np.isin(pa, [0, 1]).all():
            raise ModelingContractError("pa_not_binary")
        allowed = {"presence", "survey_supported_absence", "pseudoabsence"}
        if any(not x or x not in allowed for x in source):
            raise ModelingContractError("unknown_zero_source")
        if any((value == 1 and src != "presence") or (value == 0 and src == "presence") for value, src in zip(pa, source)):
            raise ModelingContractError("pa_source_mismatch")
        raw_weights = (1.0,) * n if self.row_weight is None else tuple(self.row_weight)
        if len(raw_weights) != n or any(type(value) not in (int, float, np.int64, np.int32, np.float64, np.float32) or not np.isfinite(value) or value != 1 for value in raw_weights):
            raise ModelingContractError("row_weight_drift")
        weights = np.asarray(raw_weights, dtype=np.float64).reshape(-1)
        order = np.array(sorted(range(n), key=lambda i: keys[i]), dtype=int)
        pa = pa[order].copy()
        weights = weights[order].copy()
        object.__setattr__(self, "keys", tuple(keys[i] for i in order))
        object.__setattr__(self, "pa", pa)
        object.__setattr__(self, "response_source", tuple(source[i] for i in order))
        object.__setattr__(self, "microcluster", tuple(micro[i] for i in order))
        pa.flags.writeable = False
        weights.flags.writeable = False
        object.__setattr__(self, "row_weight", weights)

    @classmethod
    def from_records(cls, records: Sequence[Mapping[str, Any]]) -> "RowSet":
        keys: list[RowKey] = []
        pa: list[int] = []
        source: list[str] = []
        micro: list[str] = []
        weights: list[float] = []
        for row in records:
            try:
                species_id = row["species_id"]
                grid_cell_id = row["grid_cell_id"]
                if type(species_id) is not str or type(grid_cell_id) is not str or not species_id or not grid_cell_id:
                    raise ModelingContractError("row_key_invalid")
                keys.append(RowKey(species_id, grid_cell_id))
                value = row["pa"]
                if type(value) not in (int, np.int8, np.int16, np.int32, np.int64) or value not in (0, 1):
                    raise ModelingContractError("pa_not_exact_binary_integer")
                pa.append(value)
                source_value = row.get("pa_type", row.get("response_source", ""))
                micro_value = row["microcluster"]
                if type(source_value) is not str or not source_value or type(micro_value) is not str or not micro_value:
                    raise ModelingContractError("source_or_microcluster_invalid")
                source.append(source_value)
                micro.append(micro_value)
                weight = row.get("row_weight", 1)
                if type(weight) not in (int, float, np.int64, np.int32, np.float64, np.float32) or not np.isfinite(weight) or weight != 1:
                    raise ModelingContractError("row_weight_drift")
                weights.append(weight)
            except (KeyError, TypeError, ValueError) as exc:
                raise ModelingContractError("row_record_invalid") from exc
        return cls(tuple(keys), np.asarray(pa), tuple(source), tuple(micro), np.asarray(weights))

    def take(self, indices: Sequence[int]) -> "RowSet":
        idx = np.asarray(indices, dtype=int)
        return RowSet(tuple(self.keys[i] for i in idx), self.pa[idx], tuple(self.response_source[i] for i in idx), tuple(self.microcluster[i] for i in idx), self.row_weight[idx])


@dataclass(frozen=True)
class FeatureBatch:
    keys: tuple[RowKey, ...]
    x: np.ndarray
    y: np.ndarray
    feature_names: tuple[str, ...]
    feature_kinds: tuple[str, ...]
    continuous_count: int
    feature_schema_digest: str
    unseen_level_counts: Mapping[str, int]
    transform_id: str
    transform_digest: str
    encoder_digest: str

    def __post_init__(self) -> None:
        x = np.asarray(self.x, dtype=np.float64)
        y = np.asarray(self.y, dtype=np.float64).reshape(-1)
        if x.ndim != 2 or len(x) != len(self.keys) or len(y) != len(self.keys) or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ModelingContractError("feature_batch_invalid")
        names = tuple(self.feature_names)
        kinds = tuple(self.feature_kinds)
        if any(type(name) is not str or not name for name in names) or any(kind not in {"continuous", "categorical"} for kind in kinds):
            raise ModelingContractError("feature_schema_invalid")
        if len(names) != x.shape[1] or len(kinds) != x.shape[1] or len(set(names)) != len(names) or type(self.continuous_count) is not int or self.continuous_count < 0 or self.continuous_count > len(names):
            raise ModelingContractError("feature_schema_invalid")
        if self.continuous_count != kinds.count("continuous") or kinds[: self.continuous_count] != ("continuous",) * self.continuous_count or kinds[self.continuous_count :] != ("categorical",) * (len(kinds) - self.continuous_count):
            raise ModelingContractError("feature_kind_order_invalid")
        schema_digest = hashlib.sha256(canonical_json({"feature_names": names, "feature_kinds": kinds, "continuous_count": self.continuous_count}).encode()).hexdigest()
        if not isinstance(self.feature_schema_digest, str) or re.fullmatch(r"[0-9a-f]{64}", self.feature_schema_digest) is None or self.feature_schema_digest != schema_digest:
            raise ModelingContractError("feature_schema_digest_mismatch")
        x = x.copy(); y = y.copy(); x.flags.writeable = False; y.flags.writeable = False
        object.__setattr__(self, "x", x); object.__setattr__(self, "y", y)
        object.__setattr__(self, "feature_names", names); object.__setattr__(self, "feature_kinds", kinds); object.__setattr__(self, "feature_schema_digest", schema_digest)


class LazyFeatureSubstrate:
    """Small in-memory substrate used by tests and private ingestion wrappers."""
    def __init__(self, values: Mapping[RowKey, Any]):
        self.values = dict(values)

    def get(self, key: RowKey, transform_id: str = "outer") -> Any:
        value = self.values[key]
        if isinstance(value, Mapping) and transform_id in value and not ("continuous" in value or "categorical" in value):
            return value[transform_id]
        return value


class MappingFeatureSubstrate(LazyFeatureSubstrate):
    def __init__(self, values: Mapping[RowKey, Any]):
        super().__init__(values)


class TransformingFeatureSubstrate(LazyFeatureSubstrate):
    """Outer-training-only raw predictor view with frozen Goal026 transforms."""
    def __init__(self, values: Mapping[RowKey, Mapping[str, Any]], fit_parameters: Mapping[str, Any], continuous: Sequence[str], categorical: Sequence[str]):
        self.values = dict(values)
        self.fit_parameters = dict(fit_parameters)
        self.continuous = tuple(continuous)
        self.categorical = tuple(categorical)

    def get(self, key: RowKey, transform_id: str = "outer") -> Mapping[str, Any]:
        if key not in self.values:
            raise ModelingContractError("feature_key_not_allowlisted")
        fit = self.fit_parameters.get("fits", {}).get(transform_id, self.fit_parameters.get(transform_id))
        if not isinstance(fit, Mapping):
            raise ModelingContractError("unknown_feature_transform")
        means, sds = fit.get("means", {}), fit.get("population_sd", {})
        if any(name not in means or name not in sds or not np.isfinite(float(means[name])) or not np.isfinite(float(sds[name])) or float(sds[name]) <= 0 for name in self.continuous):
            raise ModelingContractError("feature_transform_parameters_invalid")
        raw = self.values[key]
        x = [((float(raw[name]) - float(means[name])) / float(sds[name])) for name in self.continuous]
        cats = {name: str(raw[name]) for name in self.categorical}
        return {"continuous": x, "categorical": cats}

    def transform_record(self, transform_id: str) -> Mapping[str, Any]:
        fit = self.fit_parameters.get("fits", {}).get(transform_id, self.fit_parameters.get(transform_id))
        if not isinstance(fit, Mapping):
            raise ModelingContractError("unknown_feature_transform")
        return fit


class FeatureProvider:
    def __init__(self, substrate: Any, allowed_keys: frozenset[RowKey]):
        self.substrate = substrate
        self.allowed_keys = frozenset(allowed_keys)

    def _value(self, key: RowKey, transform_id: str) -> Any:
        if hasattr(self.substrate, "get"):
            try:
                return self.substrate.get(key, transform_id)
            except TypeError:
                return self.substrate.get(key)
        return self.substrate[key]

    def _schema(self, transform_id: str, train: RowSet | None = None) -> tuple[tuple[str, ...], tuple[str, ...], Mapping[str, Any]]:
        continuous = tuple(getattr(self.substrate, "continuous", ()))
        categorical = tuple(getattr(self.substrate, "categorical", ()))
        transform_record = self.substrate.transform_record(transform_id) if hasattr(self.substrate, "transform_record") else {"transform_id": transform_id}
        if train is not None and train.keys and not continuous:
            value = self._value(train.keys[0], transform_id)
            cvals, cats = self._parts(value)
            continuous = tuple(f"continuous_{i:02d}" for i in range(len(cvals)))
            categorical = tuple(sorted(cats))
        return continuous, categorical, transform_record

    @staticmethod
    def _parts(value: Any) -> tuple[list[float], dict[str, str]]:
        if isinstance(value, Mapping):
            continuous = value.get("continuous", [])
            categorical = value.get("categorical", {})
            if not isinstance(categorical, Mapping):
                raise ModelingContractError("categorical_features_invalid")
            if any(type(k) is not str or not k or type(v) is not str or not v for k, v in categorical.items()):
                raise ModelingContractError("categorical_features_invalid")
            return [float(v) for v in continuous], dict(categorical)
        return [float(v) for v in value], {}

    def fit_encoder(self, train: RowSet, family: str, transform_id: str) -> Mapping[str, Any]:
        if not set(train.keys) <= self.allowed_keys:
            raise ModelingContractError("feature_key_not_allowlisted")
        continuous_names, categorical_names, transform_record = self._schema(transform_id, train)
        levels: dict[str, tuple[str, ...]] = {name: tuple() for name in categorical_names}
        for key in train.keys:
            continuous, categorical = self._parts(self._value(key, transform_id))
            if len(continuous) != len(continuous_names) or set(categorical) != set(categorical_names):
                raise ModelingContractError("feature_schema_drift")
            for name, value in categorical.items():
                levels[name] = tuple(sorted(set(levels.get(name, ())) | {value}))
        names = continuous_names + tuple(f"{name}__{level}" for name in categorical_names for level in levels[name])
        kinds = tuple("continuous" for _ in continuous_names) + tuple("categorical" for name in categorical_names for _ in levels[name])
        schema_digest = hashlib.sha256(canonical_json({"feature_names": names, "feature_kinds": kinds, "continuous_count": len(continuous_names)}).encode()).hexdigest()
        transform_digest = hashlib.sha256(canonical_json({"transform_id": transform_id, "continuous": continuous_names, "categorical": categorical_names, "record": transform_record}).encode()).hexdigest()
        state = {"family": family, "transform_id": transform_id, "levels": levels, "categorical_names": categorical_names, "continuous_names": continuous_names, "continuous_count": len(continuous_names), "feature_names": names, "feature_kinds": kinds, "feature_schema_digest": schema_digest, "transform_digest": transform_digest}
        state["encoder_digest"] = hashlib.sha256(canonical_json(state).encode()).hexdigest()
        return state

    def materialize(self, rows: RowSet, transform_id: str, encoder_state: Mapping[str, Any]) -> FeatureBatch:
        if not set(rows.keys) <= self.allowed_keys:
            raise ModelingContractError("feature_key_not_allowlisted")
        if encoder_state.get("transform_id") != transform_id:
            raise ModelingContractError("encoder_transform_mismatch")
        expected_digest = encoder_state.get("encoder_digest")
        copy_state = dict(encoder_state); copy_state.pop("encoder_digest", None)
        if not isinstance(expected_digest, str) or hashlib.sha256(canonical_json(copy_state).encode()).hexdigest() != expected_digest:
            raise ModelingContractError("encoder_digest_mismatch")
        continuous_names, categorical_names, transform_record = self._schema(transform_id, rows)
        if tuple(encoder_state.get("continuous_names", ())) != continuous_names or tuple(encoder_state.get("categorical_names", ())) != categorical_names:
            raise ModelingContractError("encoder_schema_mismatch")
        levels = {name: tuple(values) for name, values in encoder_state.get("levels", {}).items()}
        if tuple(levels) != categorical_names:
            raise ModelingContractError("encoder_level_order_mismatch")
        matrix: list[list[float]] = []
        unseen = {name: 0 for name in levels}
        for key in rows.keys:
            continuous, categorical = self._parts(self._value(key, transform_id))
            if len(continuous) != len(continuous_names) or set(categorical) != set(categorical_names):
                raise ModelingContractError("feature_schema_drift")
            vector = list(continuous)
            for name, vocab in levels.items():
                value = categorical.get(name)
                if value not in vocab:
                    unseen[name] += 1
                    vector.extend([0.0] * len(vocab))
                else:
                    vector.extend([float(value == level) for level in vocab])
            matrix.append(vector)
        x = np.asarray(matrix, dtype=np.float64)
        transform_digest = hashlib.sha256(canonical_json({"transform_id": transform_id, "continuous": continuous_names, "categorical": categorical_names, "record": transform_record}).encode()).hexdigest()
        if transform_digest != encoder_state.get("transform_digest"):
            raise ModelingContractError("transform_digest_mismatch")
        return FeatureBatch(tuple(rows.keys), x, rows.pa.astype(float), tuple(encoder_state["feature_names"]), tuple(encoder_state["feature_kinds"]), int(encoder_state["continuous_count"]), str(encoder_state["feature_schema_digest"]), unseen, transform_id, transform_digest, str(encoder_state.get("encoder_digest", "")))


def derive_seed(task: TaskKey, purpose: str, master_seed: str = "dsdm-goal028-v1") -> int:
    fields = [master_seed, task.species_id, task.transform_id, task.fraction_id, task.ladder_id, task.model_family, task.candidate_id, task.seed_label, purpose]
    return int.from_bytes(hashlib.sha256("\x1f".join(fields).encode("utf-8")).digest()[:4], "big", signed=False)


def task_id(task: TaskKey) -> str:
    return hashlib.sha256(canonical_json({"species_id": task.species_id, "transform_id": task.transform_id, "fraction_id": task.fraction_id, "ladder_id": task.ladder_id, "model_family": task.model_family, "candidate_id": task.candidate_id, "seed_label": task.seed_label}).encode()).hexdigest()


class OuterVault:
    def __init__(self, rows: RowSet | None, synthetic: bool = False):
        self._rows = rows
        self._synthetic = synthetic
        self._open_count = 0
        self._attempted_open_count = 0

    @classmethod
    def synthetic(cls, rows: Sequence[Mapping[str, Any]]) -> "OuterVault":
        return cls(RowSet.from_records(rows), synthetic=True)

    def open(self, authorization: Mapping[str, Any] | None = None) -> RowSet:
        self._attempted_open_count += 1
        if not self._synthetic:
            raise ModelingContractError("real_outer_vault_sealed")
        if not authorization or authorization.get("synthetic") is not True:
            raise ModelingContractError("synthetic_authorization_required")
        self._open_count += 1
        assert self._rows is not None
        return self._rows

    @property
    def open_count(self) -> int:
        return self._open_count

    @property
    def attempted_open_count(self) -> int:
        return self._attempted_open_count


class SplitBroker:
    def __init__(self, outer_training: RowSet, fold_by_key: Mapping[RowKey, str]):
        if set(fold_by_key) != set(outer_training.keys):
            raise ModelingContractError("partition_mismatch")
        self._rows = outer_training
        if any(type(fold) is not str for fold in fold_by_key.values()):
            raise ModelingContractError("invalid_fold")
        self._fold_by_key = dict(fold_by_key)
        if any(fold not in {f"fold{i:02d}" for i in range(5)} for fold in self._fold_by_key.values()):
            raise ModelingContractError("invalid_fold")

    def inner(self, species_id: str, fold_id: str) -> tuple[RowSet, RowSet]:
        fold = fold_id
        if type(fold) is not str:
            raise ModelingContractError("invalid_fold")
        if fold not in {f"fold{i:02d}" for i in range(5)}:
            raise ModelingContractError("invalid_fold")
        indices = [i for i, key in enumerate(self._rows.keys) if key.species_id == species_id]
        val_idx = [i for i in indices if self._fold_by_key[self._rows.keys[i]] == fold]
        train_idx = [i for i in indices if i not in set(val_idx)]
        if not train_idx or not val_idx:
            raise ModelingContractError("empty_inner_split")
        train, val = self._rows.take(train_idx), self._rows.take(val_idx)
        if len(set(train.pa)) < 2 or len(set(val.pa)) < 2:
            raise ModelingContractError("single_class_inner_split")
        return train, val

    def outer_training(self, species_id: str) -> RowSet:
        indices = [i for i, key in enumerate(self._rows.keys) if key.species_id == species_id]
        if not indices:
            raise ModelingContractError("unknown_species")
        return self._rows.take(indices)


def _read_private_records(root: Path, record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    path = _safe_relative_path(root, str(record.get("path", "")))
    if record.get("private") is not True or not path.is_file() or path.is_symlink():
        raise ModelingContractError("private_binding_unavailable")
    claimed = record.get("sha256")
    if not isinstance(claimed, str) or len(claimed) != 64 or any(c not in "0123456789abcdef" for c in claimed):
        raise ModelingContractError("private_digest_invalid")
    if sha256_file(path) != claimed:
        raise ModelingContractError("private_digest_mismatch")
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        return list(value if isinstance(value, list) else value.get("rows", []))
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_bound_json(root: Path, record: Mapping[str, Any]) -> Mapping[str, Any]:
    path = _safe_relative_path(root, str(record.get("path", "")))
    if not path.is_file() or path.is_symlink() or sha256_file(path) != record.get("sha256"):
        raise ModelingContractError("authority_digest_mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ModelingContractError("authority_schema_invalid")
    return value


def _normalize_response_pa(value: Any) -> int:
    """Normalize the exact binary response values accepted by the RowSet path."""
    if type(value) in (int, np.int8, np.int16, np.int32, np.int64) and int(value) in (0, 1):
        return int(value)
    if type(value) is str and value in {"0", "1"}:
        return int(value)
    raise ModelingContractError("pa_not_exact_binary_integer")


def _validate_private_response_scope(config: Mapping[str, Any], response_records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Validate complete response counts before any outer/held partitioning."""
    scope = config.get("scope")
    if not isinstance(scope, Mapping):
        raise ModelingContractError("private_scope_invalid")
    real_species = scope.get("real_species")
    expected_species = ["sarcophilus_harrisii", "pseudocheirus_peregrinus"]
    if type(real_species) is not list or real_species != expected_species:
        raise ModelingContractError("private_scope_species_invalid")
    expected_counts = scope.get("included_row_counts")
    if not isinstance(expected_counts, Mapping) or set(expected_counts) != set(expected_species):
        raise ModelingContractError("private_scope_counts_invalid")
    for species in expected_species:
        record = expected_counts[species]
        if not isinstance(record, Mapping) or set(record) != {"included", "positive"}:
            raise ModelingContractError("private_scope_count_schema_invalid")
        if any(type(record[name]) is not int or isinstance(record[name], bool) or record[name] < 0 for name in ("included", "positive")):
            raise ModelingContractError("private_scope_count_type_invalid")
        if record["positive"] > record["included"]:
            raise ModelingContractError("private_scope_count_relation_invalid")

    observed: dict[str, list[int]] = {}
    normalized: list[Mapping[str, Any]] = []
    for raw in response_records:
        if not isinstance(raw, Mapping):
            raise ModelingContractError("response_record_invalid")
        species = raw.get("species_id")
        if type(species) is not str or not species:
            raise ModelingContractError("row_key_invalid")
        pa = _normalize_response_pa(raw.get("pa"))
        counts = observed.setdefault(species, [0, 0])
        counts[0] += 1
        counts[1] += pa
        row = dict(raw)
        row["pa"] = pa
        normalized.append(row)
    for species in expected_species:
        if species not in observed:
            raise ModelingContractError("private_scope_species_missing")
        included, positive = observed[species]
        expected = expected_counts[species]
        if included != expected["included"] or positive != expected["positive"]:
            raise ModelingContractError("included_row_positive_fraction_scope_mismatch")
    return normalized


def ingest_private_foundation(root: Path, config: Mapping[str, Any]) -> tuple[SplitBroker, FeatureProvider, OuterVault]:
    """Load and partition authorised private products before exposing outer-training views."""
    if "_synthetic_rows" in config or "rows" in config or "private_inputs" in config:
        raise ModelingContractError("combined_response_argument_forbidden")
    bindings = config.get("bindings", {})
    required = ("goal025_response_partitioned", "goal024_map", "goal026_fit_parameters", "goal026_feature_contract")
    if any(role not in bindings for role in required):
        raise ModelingContractError("private_ingestion_unavailable")
    response_records = _read_private_records(Path(root), bindings["goal025_response_partitioned"])
    # Count the digest-verified complete response product before partitioning;
    # the broker below intentionally exposes outer-training rows only.
    response_records = _validate_private_response_scope(config, response_records)
    map_records = _read_private_records(Path(root), bindings["goal024_map"])
    fit_parameters = _read_bound_json(Path(root), bindings["goal026_fit_parameters"])
    feature_contract = _read_bound_json(Path(root), bindings["goal026_feature_contract"])
    continuous = tuple(feature_contract.get("continuous_predictors", ()))
    categorical = tuple(feature_contract.get("categorical_predictors", ()))
    if len(continuous) != 25 or len(categorical) != 3:
        raise ModelingContractError("feature_contract_schema_drift")
    feature_by_cell: dict[str, Mapping[str, Any]] = {}
    for record in map_records:
        cell = record.get("grid_cell_id")
        if not isinstance(cell, str) or not cell:
            raise ModelingContractError("feature_key_invalid")
        if cell in feature_by_cell:
            raise ModelingContractError("duplicate_feature_key")
        if record.get("predictor_complete") not in (True, "true", "True", 1, "1"):
            raise ModelingContractError("incomplete_predictor_row")
        try:
            feature_by_cell[cell] = {name: float(record[name]) if name in continuous else str(record[name]) for name in continuous + categorical}
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelingContractError("feature_value_invalid") from exc
    outer_records: list[Mapping[str, Any]] = []
    held_records: list[Mapping[str, Any]] = []
    fold_map: dict[RowKey, str] = {}
    global_keys: set[RowKey] = set()
    for row in response_records:
        role = row.get("outer_role")
        fold = row.get("cv_fold")
        if type(row.get("species_id")) is not str or not row.get("species_id") or type(row.get("grid_cell_id")) is not str or not row.get("grid_cell_id"):
            raise ModelingContractError("row_key_invalid")
        key = RowKey(row["species_id"], row["grid_cell_id"])
        if key in global_keys:
            raise ModelingContractError("duplicate_species_cell")
        global_keys.add(key)
        if role not in {"outer_train", "test"} or (role == "outer_train" and (type(fold) is not str or fold not in {f"fold{i:02d}" for i in range(5)})) or (role == "test" and fold not in ("", None)):
            raise ModelingContractError("partition_or_fold_invalid")
        if role in {"outer_train", "test"}:
            row = dict(row)
            row["pa"] = _normalize_response_pa(row.get("pa"))
        if role == "outer_train":
            outer_records.append(row)
            fold_map[RowKey(row["species_id"], row["grid_cell_id"])] = fold
        else:
            held_records.append(row)
    if not outer_records:
        raise ModelingContractError("missing_outer_training")
    outer = RowSet.from_records(outer_records)
    outer_keys = frozenset(outer.keys)
    raw_values: dict[RowKey, Mapping[str, Any]] = {}
    for key in outer_keys:
        row = next((record for record in outer_records if record["species_id"] == key.species_id and record["grid_cell_id"] == key.grid_cell_id), None)
        if row is None or row["grid_cell_id"] not in feature_by_cell:
            raise ModelingContractError("outer_feature_join_incomplete")
        raw_values[key] = feature_by_cell[row["grid_cell_id"]]
    substrate = TransformingFeatureSubstrate(raw_values, fit_parameters, continuous, categorical)
    if set(substrate.values) != set(outer_keys):
        raise ModelingContractError("outer_feature_join_incomplete")
    broker = SplitBroker(outer, fold_map)
    provider = FeatureProvider(substrate, outer_keys)
    vault = OuterVault(RowSet.from_records(held_records) if held_records else None, synthetic=False)
    return broker, provider, vault


def ingest_synthetic_foundation(rows: Sequence[Mapping[str, Any]], feature_values: Mapping[RowKey, Any], fold_by_key: Mapping[RowKey, str]) -> tuple[SplitBroker, FeatureProvider, OuterVault]:
    """Explicit synthetic-only factory; never used by the real ingestion path."""
    outer = RowSet.from_records(rows)
    broker = SplitBroker(outer, fold_by_key)
    provider = FeatureProvider(MappingFeatureSubstrate(feature_values), frozenset(outer.keys))
    return broker, provider, OuterVault.synthetic(rows)
