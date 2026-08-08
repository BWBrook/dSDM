"""Data, authority, masking, and leaf contracts for Goal035's final inner run.

This module is intentionally free of fitting code.  It accepts only numeric,
deidentified case bundles and keeps labels private to the bundle boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
import platform
import re
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np

from .categorical_support import SupportMask, apply_support_mask, fit_support_mask
from .contracts import ENDPOINTS, FOLDS, METHODS, SPECIES, ARCHITECTURES


class FinalInnerError(ValueError):
    """Raised when the final inner contract or an atomic leaf is invalid."""


PREDICTOR_COUNT = 77
SEEDS = (31031, 31032, 31033, 31034, 31035)
ENDPOINT_SLUGS = {endpoint: endpoint.replace("/", "_") for endpoint in ENDPOINTS}
FINAL_ENDPOINTS = tuple(ENDPOINTS)
TARGET_METHODS = tuple(METHODS)
CASE_COUNT = len(SPECIES) * len(FOLDS)
HEX64 = re.compile(r"[0-9a-f]{64}")
AUTHORITY_KEYS = frozenset({"goal028_config", "goal028_decision", "goal029_config", "goal026_feature_contract", "goal026_fit_parameters", "goal033_config", "goal033_decision", "goal034_config", "goal034_decision", "corrected_aggregate"})
SOURCE_KEYS = frozenset({"contracts", "architecture_mask_revalidation", "architecture_runner", "architecture_selection", "categorical_support", "final_inner_data", "final_inner_runner", "models", "real_data", "real_six_path", "real_six_path_data", "real_training", "phase1_modeling_contract", "phase1_target_subsets", "phase1_goal029_production", "uv_lock"})
EVIDENCE_KEYS = frozenset({"private_root", "tracked_root", "canary_receipt", "aggregate_receipt", "aggregate_only", "workers", "canary_required", "labels_private", "outer_attempted", "outer_opened"})
TRAINING_KEYS = frozenset({"predictor_count", "q_predictor_count", "dtype", "device", "threads", "blas_threads", "max_epochs", "patience", "optimizer", "learning_rate", "q_linear"})


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical(value))


def array_digest(value: np.ndarray) -> str:
    return digest_bytes(np.ascontiguousarray(value).tobytes(order="C"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FinalInnerError(message)


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _safe_binding(root: Path, binding: Mapping[str, Any], *, allow_unbound: bool = False) -> Path:
    _require(isinstance(binding, Mapping) and set(binding) == {"path", "sha256"}, "binding schema drift")
    raw_path = binding["path"]
    claimed = binding["sha256"]
    _require(isinstance(raw_path, str) and raw_path and not Path(raw_path).is_absolute() and ".." not in Path(raw_path).parts, "binding path invalid")
    _require(claimed is None or _is_digest(claimed) or (allow_unbound and claimed == ""), "binding digest invalid")
    path = (root / raw_path).resolve()
    _require(root.resolve() == path or root.resolve() in path.parents, "binding path escapes root")
    _require(path.is_file(), f"bound file missing: {raw_path}")
    actual = digest_bytes(path.read_bytes())
    if claimed not in (None, ""):
        _require(actual == claimed, f"binding digest mismatch: {raw_path}")
    return path


@dataclass(frozen=True)
class FinalInnerConfig:
    source_path: Path
    root: Path
    raw: Mapping[str, Any]
    authority_digests: Mapping[str, str]
    source_digests: Mapping[str, str]
    config_digest: str
    corrected_receipt: Mapping[str, Any]
    corrected_winner: str

    @property
    def private_root(self) -> Path:
        return self.root / self.raw["evidence"]["private_root"]

    @property
    def tracked_root(self) -> Path:
        return self.root / self.raw["evidence"]["tracked_root"]

    @property
    def canary_receipt(self) -> Path:
        return self.root / self.raw["evidence"]["canary_receipt"]

    @property
    def source_fingerprint(self) -> str:
        records = [{"name": name, "path": self.raw["execution_sources"][name]["path"], "sha256": self.source_digests[name]} for name in sorted(self.source_digests)]
        return digest_value(records)


def load_corrected_receipt(config_raw: Mapping[str, Any], root: str | Path) -> tuple[dict[str, Any], str]:
    """Load the corrected architecture receipt and fail closed on drift."""
    root_path = Path(root).resolve()
    binding = config_raw["authorities"]["corrected_aggregate"]
    path = _safe_binding(root_path, binding)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(receipt, dict), "corrected aggregate is not an object")
    _require(receipt.get("success") is True and receipt.get("schema_version") == "goal035-corrected-aggregate-v1", "corrected aggregate not successful")
    winner = receipt.get("corrected_winner")
    _require(isinstance(winner, str) and winner in {row[0] for row in ARCHITECTURES}, "corrected winner invalid")
    _require(receipt.get("outer_attempted") == receipt.get("outer_opened") == 0, "corrected aggregate outer boundary drift")
    _require(receipt.get("logical_evaluations") == 1440 and receipt.get("physical_fits") == 2880, "corrected aggregate arithmetic drift")
    return receipt, digest_bytes(path.read_bytes())


def load_config(path: str | Path, *, root: str | Path | None = None, require_receipt: bool = True) -> FinalInnerConfig:
    source = Path(path).resolve()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalInnerError(f"invalid final-inner config: {exc}") from exc
    required = {"schema_version", "goal_id", "authorities", "execution_sources", "scope", "seeds", "methods", "training", "execution", "privacy", "evidence", "runtime"}
    _require(isinstance(raw, dict) and set(raw) == required, "final-inner config keys drift")
    _require(raw["schema_version"] == "1.0" and raw["goal_id"] == "goal035-dsdm-final-inner-lifecycle", "final-inner config identity drift")
    project_root = Path(root).resolve() if root is not None else source.parents[1]
    authorities = raw["authorities"]
    _require(isinstance(authorities, dict) and set(authorities) == AUTHORITY_KEYS, "authority key set drift")
    authority_digests: dict[str, str] = {}
    for name, binding in authorities.items():
        if name == "corrected_aggregate" and not require_receipt:
            candidate = project_root / str(binding.get("path", ""))
            if not candidate.is_file():
                continue
        path_value = _safe_binding(project_root, binding)
        authority_digests[name] = digest_bytes(path_value.read_bytes())
    sources = raw["execution_sources"]
    _require(isinstance(sources, dict) and set(sources) == SOURCE_KEYS, "execution source key set drift")
    source_digests: dict[str, str] = {}
    for name, binding in sources.items():
        path_value = _safe_binding(project_root, binding)
        source_digests[name] = digest_bytes(path_value.read_bytes())
    scope = raw["scope"]
    _require(scope == {"species": list(SPECIES), "folds": list(FOLDS), "endpoints": list(ENDPOINTS), "predictor_count": 77, "case_count": 40}, "final-inner scope drift")
    _require(tuple(raw["seeds"]) == SEEDS, "final-inner seed drift")
    _require(tuple(raw["methods"]) == METHODS, "final-inner method drift")
    _require(isinstance(raw["training"], dict) and set(raw["training"]) == TRAINING_KEYS, "training key set drift")
    _require(raw["training"] == {"predictor_count": 77, "q_predictor_count": 78, "dtype": "float32", "device": "cpu", "threads": 1, "blas_threads": 1, "max_epochs": 300, "patience": 30, "optimizer": "AdamW", "learning_rate": 0.001, "q_linear": {"penalty": "elasticnet", "solver": "saga", "C": 1.0, "l1_ratio": 0.5, "max_iter": 5000, "tol": 0.00001, "stability_max_iter": 10000, "stability_probability_tolerance": 0.0001}}, "training contract drift")
    execution = raw["execution"]
    _require(execution == {"auxiliary_logical_artifacts_per_case": 11, "target_logical_artifacts_per_case": 210, "logical_artifacts_per_case": 221, "physical_fits_per_case_minimum": 441, "physical_fits_per_case_maximum": 442, "logical_artifacts": 8840, "physical_fits_minimum": 17640, "physical_fits_maximum": 17680, "workers": 3, "outer_attempted": 0, "outer_opened": 0}, "final-inner execution arithmetic drift")
    _require(raw["privacy"] == {"labels_private": True, "row_identifiers": False, "coordinates": False, "outer_attempted": 0, "outer_opened": 0}, "final-inner privacy drift")
    evidence = raw["evidence"]
    _require(isinstance(evidence, dict) and set(evidence) == EVIDENCE_KEYS, "evidence key set drift")
    for key in ("private_root", "tracked_root", "canary_receipt", "aggregate_receipt"):
        value = evidence[key]
        _require(isinstance(value, str) and value and not Path(value).is_absolute() and ".." not in Path(value).parts, f"evidence path invalid: {key}")
    _require(evidence["aggregate_only"] is True and evidence["workers"] == 3 and evidence["canary_required"] is True and evidence["labels_private"] is True and evidence["outer_attempted"] == evidence["outer_opened"] == 0, "evidence policy drift")
    _require(raw["runtime"] == {"system": "Darwin", "machine": "arm64", "python_major_minor": "3.12", "numpy": "2.2.6", "scipy": "1.16.3", "scikit_learn": "1.9.0", "threadpoolctl": "3.6.0", "torch": "2.7.1", "device": "cpu", "route": "mac_cpu", "torch_threads": 1, "blas_threads": 1}, "runtime contract drift")
    receipt: Mapping[str, Any] = {}
    corrected_winner = ""
    if require_receipt:
        receipt, _ = load_corrected_receipt(raw, project_root)
        corrected_winner = str(receipt["corrected_winner"])
    return FinalInnerConfig(source, project_root, raw, dict(sorted(authority_digests.items())), dict(sorted(source_digests.items())), digest_bytes(source.read_bytes()), receipt, corrected_winner)


def runtime_attestation(config: FinalInnerConfig, *, strict: bool = True) -> dict[str, Any]:
    import scipy
    import sklearn
    import threadpoolctl
    import torch
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    torch.set_num_threads(1)
    with threadpoolctl.threadpool_limits(limits=1):
        blas_threads = max((int(item.get("num_threads", 1)) for item in threadpoolctl.threadpool_info()), default=1)
    actual = {
        "system": platform.system(), "machine": platform.machine(),
        "python_major_minor": ".".join(platform.python_version().split(".")[:2]),
        "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__, "threadpoolctl": threadpoolctl.__version__, "torch": str(torch.__version__).split("+", 1)[0],
        "device": "cpu", "route": "mac_cpu", "torch_threads": torch.get_num_threads(), "blas_threads": blas_threads,
    }
    if strict:
        expected = config.raw["runtime"]
        _require(actual["system"] == "Darwin" and actual["machine"] == "arm64", "final-inner runtime host mismatch")
        for key in ("system", "machine", "python_major_minor", "numpy", "scipy", "scikit_learn", "threadpoolctl", "torch", "device", "route", "torch_threads", "blas_threads"):
            _require(str(actual[key]) == str(expected[key]), f"final-inner runtime mismatch: {key}")
    return actual


def _target_keys(endpoint: str) -> tuple[str, ...]:
    slug = ENDPOINT_SLUGS[endpoint]
    return tuple(f"target_{slug}_x_{role}" for role in ("discovery", "stopping", "replay")) + tuple(f"target_{slug}_y_{role}" for role in ("discovery", "stopping", "replay"))


ARRAY_KEYS = frozenset({key for endpoint in ENDPOINTS for key in _target_keys(endpoint)} | {"x_held", "y_held"} | {f"aux_{prefix}_{role}" for role in ("discovery", "stopping", "replay") for prefix in ("x", "y", "species")})
BUNDLE_METADATA_KEYS = frozenset({"schema_version", "goal_id", "case_id", "target", "held_fold", "stopping_fold", "config_digest", "authority_digests", "source_digests", "source_fingerprint", "source_binding_digest", "subset_membership_digests", "subset_nesting_verified", "subset_nesting_by_ladder", "fold_partition", "array_shapes", "array_digests", "auxiliary_audit", "privacy", "outer_attempted", "outer_opened", "bundle_digest"})
LEAF_METADATA_KEYS = frozenset({"schema_version", "goal_id", "target", "held_fold", "architecture", "config_digest", "bundle_digest", "target_mask_digests", "auxiliary_mask_digest", "support_overlap", "target_support_audits", "auxiliary_support_audits", "q_ranges", "target_plus_q_prediction_ranges", "artifacts", "counts", "runtime", "outer_attempted", "outer_opened", "identity", "shape", "dtype", "prediction_digest"})
NEURAL_ARTIFACT_KEYS = frozenset({"artifact_id", "kind", "logical_artifacts", "physical_fits", "selected_epoch", "discovery_executed_epochs", "replay_epochs", "stopping_status", "initial_model_digest", "replay_initial_model_digest", "initial_shared_digest", "final_shared_digest", "initial_head_digest", "model_digest", "prediction_digest", "n_iter", "finite", "wall_seconds", "fit_seed", "runtime_digest"})
Q_ARTIFACT_KEYS = NEURAL_ARTIFACT_KEYS | frozenset({"primary_n_iter", "convergence", "termination_status", "stability_accepted", "stability_probability_delta", "stability_probability_tolerance", "coefficient_range", "logit_range", "probability_range"})


def _row_counter(x: np.ndarray, y: np.ndarray, species: np.ndarray | None = None) -> Counter[tuple[Any, ...]]:
    """Return a byte-stable multiset of complete rows, preserving multiplicity."""
    xx = np.asarray(x, dtype=np.float32)
    yy = np.asarray(y, dtype=np.float32)
    ss = None if species is None else np.asarray(species, dtype=np.int32)
    _require(xx.ndim == 2 and yy.ndim == 1 and len(xx) == len(yy), "row multiset shape drift")
    if ss is not None:
        _require(ss.ndim == 1 and len(ss) == len(xx), "row multiset species shape drift")
    tokens: list[tuple[Any, ...]] = []
    for index in range(len(xx)):
        token: tuple[Any, ...] = (np.ascontiguousarray(xx[index]).tobytes(), np.asarray(yy[index], dtype=np.float32).tobytes())
        if ss is not None:
            token += (int(ss[index]),)
        tokens.append(token)
    return Counter(tokens)


def _counter_subset(left: Counter[tuple[Any, ...]], right: Counter[tuple[Any, ...]]) -> bool:
    return all(count <= right.get(row, 0) for row, count in left.items())


def _validate_row_partition(arrays: Mapping[str, np.ndarray], *, prefix: str, species: bool = False) -> None:
    """Require replay to equal discovery + stopping exactly, as row multisets."""
    def rows(role: str) -> Counter[tuple[Any, ...]]:
        return _row_counter(arrays[f"{prefix}_x_{role}"], arrays[f"{prefix}_y_{role}"], arrays[f"{prefix}_species_{role}"] if species else None)
    discovery, stopping, replay = rows("discovery"), rows("stopping"), rows("replay")
    _require(replay == discovery + stopping, f"{prefix} replay row multiset is not discovery+stopping")


def _validate_endpoint_nesting(arrays: Mapping[str, np.ndarray]) -> dict[str, bool]:
    """Check each available 25/50/100 ladder chain using complete row multisets."""
    results: dict[str, bool] = {}
    for ladder in ("ladder00", "ladder01", "ladder02"):
        for role in ("discovery", "stopping", "replay"):
            def rows(fraction: str) -> Counter[tuple[Any, ...]]:
                endpoint = "fraction100/full" if fraction == "100" else f"fraction{fraction}/{ladder}"
                slug = ENDPOINT_SLUGS[endpoint]
                return _row_counter(arrays[f"target_{slug}_x_{role}"], arrays[f"target_{slug}_y_{role}"])
            chain = [rows("25"), rows("50"), rows("100")]
            valid = all(_counter_subset(chain[index], chain[index + 1]) for index in range(len(chain) - 1))
            _require(valid, f"target {ladder} {role} row-multiset nesting failed")
        results[ladder] = True
    return results


@dataclass(frozen=True)
class CaseBundle:
    target: str
    held_fold: str
    arrays: Mapping[str, np.ndarray]
    metadata: Mapping[str, Any]
    source_digest: str

    def __post_init__(self) -> None:
        _require(self.target in SPECIES and self.held_fold in FOLDS, "case identity invalid")
        _require(_is_digest(self.source_digest), "case source digest invalid")
        arrays = dict(self.arrays)
        _require("x_held" in arrays and "y_held" in arrays, "shared held arrays missing")
        held_x = np.asarray(arrays["x_held"]); held_y = np.asarray(arrays["y_held"])
        _require(held_x.dtype == np.float32 and held_x.ndim == 2 and held_x.shape[1] == PREDICTOR_COUNT and len(held_x) > 0 and np.isfinite(held_x).all(), "held predictors invalid")
        _require(held_y.dtype == np.float32 and held_y.ndim == 1 and len(held_y) == len(held_x) and np.isin(held_y, (0.0, 1.0)).all(), "held response invalid")
        for endpoint in ENDPOINTS:
            for key in _target_keys(endpoint):
                _require(key in arrays, f"missing target array: {key}")
            for role in ("discovery", "stopping", "replay"):
                x = np.asarray(arrays[f"target_{ENDPOINT_SLUGS[endpoint]}_x_{role}"])
                y = np.asarray(arrays[f"target_{ENDPOINT_SLUGS[endpoint]}_y_{role}"])
                _require(x.dtype == np.float32 and x.ndim == 2 and x.shape[1] == PREDICTOR_COUNT and len(x) > 0 and np.isfinite(x).all(), f"target {endpoint}/{role} predictors invalid")
                _require(y.dtype == np.float32 and y.ndim == 1 and len(y) == len(x) and np.isfinite(y).all() and np.isin(y, (0.0, 1.0)).all(), f"target {endpoint}/{role} response invalid")
                _require(set(np.unique(y).tolist()) == {0.0, 1.0}, f"target {endpoint}/{role} requires both classes")
            _validate_row_partition(arrays, prefix=f"target_{ENDPOINT_SLUGS[endpoint]}")
        _require(set(np.unique(held_y).tolist()) == {0.0, 1.0}, "held response requires both classes")
        for role in ("discovery", "stopping", "replay"):
            x = np.asarray(arrays[f"aux_x_{role}"]); y = np.asarray(arrays[f"aux_y_{role}"]); species = np.asarray(arrays[f"aux_species_{role}"])
            _require(x.dtype == np.float32 and x.ndim == 2 and x.shape[1] == PREDICTOR_COUNT and len(x) > 0 and np.isfinite(x).all(), f"auxiliary {role} predictors invalid")
            _require(y.dtype == np.float32 and y.ndim == 1 and len(y) == len(x) and np.isin(y, (0.0, 1.0)).all(), f"auxiliary {role} responses invalid")
            _require(set(np.unique(y).tolist()) == {0.0, 1.0}, f"auxiliary {role} requires both classes")
            _require(species.dtype == np.int32 and species.ndim == 1 and len(species) == len(x) and set(species.tolist()) == set(range(7)), f"auxiliary {role} species invalid")
        _validate_row_partition(arrays, prefix="aux", species=True)
        _validate_endpoint_nesting(arrays)
        _require(dict(self.metadata).get("outer_attempted", 0) == dict(self.metadata).get("outer_opened", 0) == 0, "case outer boundary drift")
        for value in arrays.values():
            np.asarray(value).flags.writeable = False
        object.__setattr__(self, "arrays", arrays)


def build_case_bundle(target: str, held_fold: str, arrays: Mapping[str, np.ndarray], metadata: Mapping[str, Any], source_digest: str) -> CaseBundle:
    return CaseBundle(target, held_fold, arrays, dict(metadata), source_digest)


def prepare_case(bundle: CaseBundle) -> dict[str, Any]:
    """Apply target masks and construct the separate q inference view."""
    arrays = bundle.arrays
    target_masks: dict[str, SupportMask] = {}
    masked: dict[str, np.ndarray] = {}
    target_audits: dict[str, Any] = {}
    for endpoint in ENDPOINTS:
        slug = ENDPOINT_SLUGS[endpoint]
        support = fit_support_mask(arrays[f"target_{slug}_x_replay"])
        target_masks[endpoint] = support
        for role in ("discovery", "stopping", "replay"):
            value, audit = apply_support_mask(arrays[f"target_{slug}_x_{role}"], support)
            masked[f"target_{slug}_x_{role}"] = value
            target_audits[f"{endpoint}/{role}"] = audit
        masked[f"target_{slug}_x_held"], target_audits[f"{endpoint}/held"] = apply_support_mask(arrays["x_held"], support)
        for role in ("discovery", "stopping", "replay"):
            _require(masked[f"target_{slug}_x_{role}"].tobytes(order="C") == arrays[f"target_{slug}_x_{role}"].tobytes(order="C"), f"target training bytes changed: {endpoint}/{role}")
    aux_support = fit_support_mask(arrays["aux_x_replay"])
    aux_masked: dict[str, np.ndarray] = {}
    aux_audits: dict[str, Any] = {}
    for role in ("discovery", "stopping", "replay"):
        aux_masked[role], aux_audits[role] = apply_support_mask(arrays[f"aux_x_{role}"], aux_support)
    q_inputs: dict[str, np.ndarray] = {}
    for endpoint in ENDPOINTS:
        slug = ENDPOINT_SLUGS[endpoint]
        for role in ("discovery", "stopping", "replay", "held"):
            # q inference deliberately uses the raw fixed x and auxiliary mask.
            raw = arrays["x_held"] if role == "held" else arrays[f"target_{slug}_x_{role}"]
            q_inputs[f"{endpoint}/{role}"] = apply_support_mask(raw, aux_support)[0]
    overlap = {endpoint: int(np.logical_and(target_masks[endpoint].columns, aux_support.columns).sum()) for endpoint in ENDPOINTS}
    return {"target": masked, "auxiliary": aux_masked, "target_masks": target_masks, "auxiliary_mask": aux_support, "target_audits": target_audits, "auxiliary_audits": aux_audits, "q_inputs": q_inputs, "support_overlap": overlap}


def leaf_identity(identity: Mapping[str, Any]) -> str:
    required = {"target", "held_fold", "held_row_count", "bundle_digest", "config_digest", "runtime_digest", "architecture", "mask_digest", "aux_mask_digest"}
    _require(set(identity) == required, "final-inner leaf identity keys drift")
    _require(identity["target"] in SPECIES and identity["held_fold"] in FOLDS and type(identity["held_row_count"]) is int and identity["held_row_count"] > 0 and isinstance(identity["architecture"], str), "final-inner leaf scope invalid")
    for key in ("bundle_digest", "config_digest", "runtime_digest", "mask_digest", "aux_mask_digest"):
        _require(_is_digest(identity[key]), f"final-inner leaf digest invalid: {key}")
    return digest_value(dict(identity))


def write_leaf(root: str | Path, identity: Mapping[str, Any], predictions: np.ndarray, metadata: Mapping[str, Any]) -> Path:
    leaf_id = leaf_identity(identity)
    values = np.asarray(predictions, dtype=np.float32)
    _require(values.ndim == 4 and values.shape == (len(SEEDS), len(ENDPOINTS), len(METHODS), int(identity["held_row_count"])) and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "final-inner prediction array invalid")
    payload = dict(metadata)
    payload.update({"identity": dict(identity), "shape": list(values.shape), "dtype": "float32", "prediction_digest": array_digest(values), "outer_attempted": 0, "outer_opened": 0})
    output_root = Path(root); output_root.mkdir(parents=True, exist_ok=True); output = output_root / leaf_id
    if output.exists():
        validate_leaf(output, identity)
        return output
    temporary = Path(tempfile.mkdtemp(prefix=".final-inner-", dir=str(output_root)))
    try:
        np.save(temporary / "predictions.npy", values, allow_pickle=False)
        (temporary / "metadata.json").write_text(canonical(payload).decode() + "\n", encoding="utf-8")
        validate_case_payload(identity, values, payload)
        os.replace(temporary, output)
        validate_leaf(output, identity)
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir(): child.unlink(missing_ok=True)
            temporary.rmdir()
        raise
    return output


def validate_case_payload(identity: Mapping[str, Any], predictions: np.ndarray, metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one complete case payload before or after publication."""
    leaf_identity(identity)
    metadata = dict(metadata)
    _require(set(metadata) == LEAF_METADATA_KEYS, "final-inner leaf metadata schema drift")
    predictions = np.asarray(predictions)
    _require(metadata.get("identity") == dict(identity) and metadata.get("shape") == list(predictions.shape) and metadata.get("dtype") == "float32", "final-inner leaf identity mismatch")
    _require(predictions.dtype == np.float32 and predictions.ndim == 4 and predictions.shape == (len(SEEDS), len(ENDPOINTS), len(METHODS), int(identity["held_row_count"])), "final-inner leaf shape/dtype invalid")
    _require(metadata.get("prediction_digest") == array_digest(predictions), "final-inner prediction digest mismatch")
    _require(metadata.get("outer_attempted") == metadata.get("outer_opened") == 0, "final-inner leaf outer boundary drift")
    artifacts = metadata.get("artifacts")
    _require(isinstance(artifacts, list) and len(artifacts) == 221 and len({item.get("artifact_id") for item in artifacts}) == 221, "final-inner artifact inventory drift")
    physical_fits = sum(int(item.get("physical_fits", -1)) for item in artifacts)
    _require(metadata.get("counts") == {"auxiliary_logical_artifacts": 11, "target_logical_artifacts": 210, "logical_artifacts": 221, "physical_fits": physical_fits} and physical_fits in {441, 442}, "final-inner count evidence drift")
    runtime_digest = identity["runtime_digest"]
    def expected_fit_seed(endpoint: str, seed: int, method: str) -> int:
        text = f"goal035-final-inner|{identity['target']}|{identity['held_fold']}|{endpoint}|{seed}|{method}|{identity['architecture']}"
        return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")
    _require(all(item.get("logical_artifacts") == 1 and item.get("finite") is True and type(item.get("fit_seed")) is int and item.get("runtime_digest") == runtime_digest for item in artifacts), "final-inner physical/artifact schema drift")
    for item in artifacts:
        expected = Q_ARTIFACT_KEYS if item.get("artifact_id") == "aux/q_linear" else NEURAL_ARTIFACT_KEYS
        _require(set(item) == expected, f"final-inner artifact schema drift: {item.get('artifact_id')}")
        for key in ("model_digest", "prediction_digest", "initial_model_digest", "replay_initial_model_digest", "initial_shared_digest", "final_shared_digest", "initial_head_digest"):
            _require(item.get(key) == "not_applicable" or _is_digest(item.get(key)), f"final-inner artifact digest invalid: {key}")
        if item.get("kind") != "auxiliary" or item.get("artifact_id") != "aux/q_linear":
            _require(item.get("initial_model_digest") == item.get("replay_initial_model_digest"), "final-inner replay reset drift")
    q = next((item for item in artifacts if item.get("artifact_id") == "aux/q_linear"), None)
    _require(q is not None and type(q.get("primary_n_iter")) is int and type(q.get("n_iter")) is int and q.get("stability_probability_tolerance") == 1e-4 and isinstance(q.get("stability_probability_delta"), (int, float)) and np.isfinite(float(q["stability_probability_delta"])) and 0.0 <= float(q["stability_probability_delta"]) <= 1e-4, "final-inner q stability evidence drift")
    if q.get("termination_status") == "converged":
        _require(q.get("physical_fits") == 1 and q.get("convergence") is True and q.get("stability_accepted") is False and 0 < q["n_iter"] == q["primary_n_iter"] < 5000 and q["stability_probability_delta"] == 0.0, "final-inner q termination evidence drift")
    elif q.get("termination_status") == "converged_after_extension":
        _require(q.get("physical_fits") == 2 and q.get("convergence") is True and q.get("stability_accepted") is False and q["primary_n_iter"] == 5000 and 5000 < q["n_iter"] < 10000, "final-inner q termination evidence drift")
    else:
        _require(q.get("physical_fits") == 2 and q.get("termination_status") == "prediction_stable_at_iteration_ceiling" and q.get("convergence") is False and q.get("stability_accepted") is True and q["primary_n_iter"] == 5000 and q["n_iter"] == 10000, "final-inner q termination evidence drift")
    _require(q["fit_seed"] == expected_fit_seed("auxiliary", SEEDS[0], "q_linear"), "final-inner q fit-seed derivation drift")
    for key in ("coefficient_range", "logit_range", "probability_range"):
        value = q[key]
        _require(set(value) == {"min", "max"} and all(np.isfinite(float(value[bound])) for bound in ("min", "max")) and float(value["min"]) <= float(value["max"]), "final-inner q range evidence drift")
    _require(0.0 <= float(q["probability_range"]["min"]) <= float(q["probability_range"]["max"]) <= 1.0, "final-inner q probability range drift")
    for seed in SEEDS:
        pooled_aux = next((item for item in artifacts if item.get("artifact_id") == f"aux/pooled/seed{seed}"), None)
        multi_aux = next((item for item in artifacts if item.get("artifact_id") == f"aux/multihead/seed{seed}"), None)
        _require(pooled_aux is not None and multi_aux is not None, "final-inner auxiliary seed inventory drift")
        _require(pooled_aux["fit_seed"] == seed and multi_aux["fit_seed"] == seed, "final-inner auxiliary fit-seed inventory drift")
        for endpoint in FINAL_ENDPOINTS:
            rows = {item["artifact_id"].rsplit("/", 1)[-1]: item for item in artifacts if item.get("artifact_id", "").startswith(f"target/{endpoint}/seed{seed}/")}
            _require(set(rows) == set(TARGET_METHODS), "final-inner method inventory drift")
            _require(rows["target_only_resmlp"]["initial_head_digest"] == rows["multihead_frozen_trunk"]["initial_head_digest"] == rows["multihead_full_finetune"]["initial_head_digest"], "final-inner head transfer drift")
            _require(rows["multihead_frozen_trunk"]["initial_model_digest"] == rows["multihead_full_finetune"]["initial_model_digest"], "final-inner shared start drift")
            _require(rows["multihead_frozen_trunk"]["initial_shared_digest"] == rows["multihead_frozen_trunk"]["final_shared_digest"], "final-inner frozen trunk drift")
            _require(rows["target_plus_q_linear"]["initial_model_digest"] == rows["target_plus_q_deep"]["initial_model_digest"], "final-inner q start drift")
            _require(len({row["fit_seed"] for row in rows.values()}) == 1, "final-inner common fit seed drift")
            _require(rows["target_only_resmlp"]["fit_seed"] == expected_fit_seed(endpoint, seed, "target"), "final-inner target fit-seed derivation drift")
            for row in rows.values():
                _require(type(row.get("selected_epoch")) is int and type(row.get("discovery_executed_epochs")) is int and type(row.get("replay_epochs")) is int and 1 <= row["selected_epoch"] == row["replay_epochs"] <= row["discovery_executed_epochs"] <= 300, "final-inner epoch evidence drift")
            _require(rows["legacy_pooled_finetune"]["initial_model_digest"] == pooled_aux["model_digest"], "final-inner pooled transfer drift")
            _require(rows["multihead_frozen_trunk"]["initial_shared_digest"] == rows["multihead_full_finetune"]["initial_shared_digest"] == multi_aux["final_shared_digest"], "final-inner multihead transfer drift")
    return metadata


def validate_leaf(path: str | Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    directory = Path(path); leaf_identity(identity)
    _require(directory.is_dir() and {item.name for item in directory.iterdir()} == {"metadata.json", "predictions.npy"}, "final-inner leaf inventory invalid")
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    predictions = np.load(directory / "predictions.npy", allow_pickle=False)
    return validate_case_payload(identity, predictions, metadata)


def load_case_npz(path: str | Path) -> CaseBundle:
    """Read the private Goal035 case bundle format (no object arrays)."""
    source = Path(path)
    try:
        with np.load(source, allow_pickle=False) as payload:
            _require("metadata_json" in payload.files, "case metadata missing")
            metadata = json.loads(bytes(payload["metadata_json"].tolist()).decode("utf-8"))
            arrays = {name: np.asarray(payload[name]).copy() for name in payload.files if name != "metadata_json"}
    except FinalInnerError:
        raise
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise FinalInnerError("invalid final-inner case bundle") from exc
    _require(set(arrays) == ARRAY_KEYS and len(arrays) == 53, "case array inventory drift")
    _require(isinstance(metadata, dict) and set(metadata) == BUNDLE_METADATA_KEYS, "case metadata schema drift")
    target = metadata.get("target"); held_fold = metadata.get("held_fold")
    _require(isinstance(target, str) and isinstance(held_fold, str), "case metadata identity missing")
    _require(metadata["case_id"] == f"{target}--{held_fold}" and metadata["stopping_fold"] == f"fold{(int(held_fold[-2:]) + 1) % 5:02d}", "case fold identity drift")
    _require(metadata["privacy"] == {"labels_private": True, "row_identifiers": False, "coordinates": False, "outer_attempted": 0, "outer_opened": 0}, "case privacy drift")
    _require(metadata["outer_attempted"] == metadata["outer_opened"] == 0 and metadata["subset_nesting_verified"] is True, "case evidence boundary drift")
    _require(metadata["subset_nesting_by_ladder"] == {"ladder00": True, "ladder01": True, "ladder02": True}, "case ladder nesting inventory drift")
    partition = metadata["fold_partition"]
    _require(set(partition) == {"held", "stopping", "discovery", "replay"}, "fold partition schema drift")
    held = partition["held"]; stopping = partition["stopping"]; discovery = tuple(partition["discovery"]); replay = tuple(partition["replay"])
    _require(held == held_fold and stopping == metadata["stopping_fold"] and held not in replay and stopping not in discovery and set(discovery).isdisjoint({stopping}) and set(discovery) | {stopping} == set(replay) == set(FOLDS) - {held}, "fold partition leakage")
    _require(metadata["array_shapes"] == {name: list(value.shape) for name, value in sorted(arrays.items())}, "case array shape inventory drift")
    _require(metadata["array_digests"] == {name: array_digest(value) for name, value in sorted(arrays.items())}, "case array digest inventory drift")
    _require(_is_digest(metadata["config_digest"]) and _is_digest(metadata["source_fingerprint"]) and _is_digest(metadata["source_binding_digest"]), "case source binding invalid")
    _require(set(metadata["authority_digests"]) == AUTHORITY_KEYS and all(_is_digest(value) for value in metadata["authority_digests"].values()), "case authority inventory drift")
    _require(set(metadata["source_digests"]) == SOURCE_KEYS and all(_is_digest(value) for value in metadata["source_digests"].values()), "case source inventory drift")
    _require(set(metadata["subset_membership_digests"]) == set(ENDPOINTS) and all(_is_digest(value) for value in metadata["subset_membership_digests"].values()), "subset membership inventory drift")
    aux_audit = metadata["auxiliary_audit"]
    _require(set(aux_audit) == {"target_excluded", "held_fold_excluded", "pseudoabsence_rows", "unknown_rows", "species_set", "equal_species_weighting", "species_counts", "species_weight_totals"}, "auxiliary audit schema drift")
    _require(aux_audit["target_excluded"] is True and aux_audit["held_fold_excluded"] is True and aux_audit["pseudoabsence_rows"] == aux_audit["unknown_rows"] == 0 and aux_audit["species_set"] == list(range(7)) and aux_audit["equal_species_weighting"] == "exact_equal_species_contribution", "auxiliary audit drift")
    _require(set(aux_audit["species_counts"]) == set(map(str, range(7))) and len(set(float(value) for value in aux_audit["species_weight_totals"].values())) == 1, "auxiliary equal-weight audit drift")
    array_inventory = {name: array_digest(value) for name, value in sorted(arrays.items())}
    manifest = dict(metadata)
    claimed = manifest.pop("bundle_digest", None)
    source_digest = digest_value({"metadata": manifest, "arrays": array_inventory})
    if claimed is not None:
        _require(claimed == source_digest, "case bundle digest mismatch")
    metadata["bundle_digest"] = source_digest
    return build_case_bundle(target, held_fold, arrays, metadata, source_digest)


def validate_bundle_inventory(root: str | Path, *, expected_count: int = CASE_COUNT, config: FinalInnerConfig | None = None) -> list[CaseBundle]:
    paths = sorted(Path(root).glob("*.npz"))
    _require(len(paths) == expected_count, f"expected {expected_count} final-inner case bundles")
    bundles = [load_case_npz(path) for path in paths]
    if config is not None:
        for bundle in bundles:
            _require(bundle.metadata.get("config_digest") == config.config_digest, "case config binding drift")
            _require(bundle.metadata.get("authority_digests") == dict(config.authority_digests), "case authority binding drift")
            _require(bundle.metadata.get("source_digests") == dict(config.source_digests) and bundle.metadata.get("source_fingerprint") == config.source_fingerprint, "case source binding drift")
    _require({(bundle.target, bundle.held_fold) for bundle in bundles} == {(target, fold) for target in SPECIES for fold in FOLDS}, "final-inner case cross-product drift")
    return bundles


def validate_case_binding(bundle: CaseBundle, config: FinalInnerConfig) -> None:
    _require(bundle.metadata.get("config_digest") == config.config_digest, "case config binding drift")
    _require(bundle.metadata.get("authority_digests") == dict(config.authority_digests), "case authority binding drift")
    _require(bundle.metadata.get("source_digests") == dict(config.source_digests) and bundle.metadata.get("source_fingerprint") == config.source_fingerprint, "case source binding drift")


__all__ = [
    "CASE_COUNT", "CaseBundle", "ENDPOINT_SLUGS", "FINAL_ENDPOINTS", "FinalInnerConfig", "FinalInnerError", "METHODS", "PREDICTOR_COUNT", "SEEDS", "TARGET_METHODS", "array_digest", "build_case_bundle", "canonical", "digest_bytes", "digest_value", "leaf_identity", "load_case_npz", "load_config", "load_corrected_receipt", "prepare_case", "runtime_attestation", "validate_bundle_inventory", "validate_case_binding", "validate_case_payload", "validate_leaf", "write_leaf",
]
