"""Neural lane for the Tasmania pseudoabsence-removal sensitivity.

The scientific perturbation is confined to target training rows.  This runner
keeps the original inner and outer evaluation memberships, refits target
support masks from the filtered replay/training view, uses the recovered
Goal035 auxiliary states for inner fits, and uses the accepted Goal037 outer
auxiliary states for outer fits.  It never reads outer held responses.

Preparation, smoke, inner production, outer production, and closure are
separate fail-closed stages.  ``smoke`` and production are fitting commands;
the orchestration entry points require an explicit ``--execute`` flag.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace
from typing import Any, Iterable, Iterator, Mapping, Sequence

# These must be fixed before NumPy, SciPy, sklearn or torch load a BLAS/OpenMP
# runtime in a spawned fit worker.  The threadpoolctl scope below remains active
# for the whole fit as a second, live enforcement layer.
THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
}
for _thread_name, _thread_value in THREAD_ENVIRONMENT.items():
    os.environ[_thread_name] = _thread_value

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/neural/results")
DEFAULT_OUTPUT = ROOT / PRIVATE_REL
INPUT_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/neural")
MANIFEST_REL = INPUT_REL / "input-manifest.json"
DATA_HELPER_REL = Path("scripts/tasmania_pseudoabsence_neural_data.py")
RECOVERY_REL = Path("scripts/tasmania_auxiliary_recovery.py")
STAGE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/reconstruction")
DEFAULT_STAGE_ROOT = ROOT / STAGE_REL
RECOVERY_AGGREGATE_REL = Path("evidence/tasmania_pseudoabsence/20261009/auxiliary-recovery.json")
AUX_AUDIT_REL = Path("evidence/tasmania_pseudoabsence/20261008/auxiliary-state-audit.json")
SOURCE_CENSUS_REL = Path("evidence/tasmania_pseudoabsence/20261008/source-census.json")
GOAL035_BUNDLE_REL = Path("data/processed/dsdm/goal035-final-inner-lifecycle/private")
GOAL035_LEAF_REL = Path("data/processed/dsdm/goal035-final-inner-lifecycle/private/leaves")
GOAL037_BUNDLE_REL = Path("data/processed/dsdm/goal037-outer-ready/private/bundles")
GOAL037_PACKAGE_REL = Path("data/processed/dsdm/goal037-outer-ready/private/neural/leaves")
GOAL037_RECEIPT_REL = Path("evidence/dsdm_outer_ready/goal037/receipt.json")

MANIFEST_DIGEST = "e1b6d585f8dfe2a0a4569b89cb09799c24cebb95060034a51580b4cb08bd39a8"
DATA_HELPER_SHA256 = "192780828d695f27a149ed049774e0668966d9f8682a53439ec57909d6e5d4bc"
RECOVERY_SOURCE_SHA256 = "0f3d519ab6510bcb83063f31be608bac002cb6cb4e1670c3dcc26cf6456afa0c"
RECOVERY_AGGREGATE_SHA256 = "2d86a42321dcbaf1abca9f6cb592e9c6f7bb41e5d59c8e97c683c8fe8464c4f9"
AUX_AUDIT_SHA256 = "335986169feb00c867ba9fc7cc0ab609607256e71b73c8d5dd4311dd04f15a94"
SOURCE_CENSUS_SHA256 = "211bad0f88daa140f1d56ac2916fd5da584f4164e6e96e36748547b8dc392352"
GOAL037_RECEIPT_SHA256 = "c691bf13f3722431687e0fed0259125a23c066959a114b56566dfe21afed4f13"

SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
FOLDS = tuple(f"fold{i:02d}" for i in range(5))
ENDPOINTS = (
    "fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02",
    "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02",
    "fraction100/full",
)
SLUGS = {endpoint: endpoint.replace("/", "_") for endpoint in ENDPOINTS}
METHODS = ("target_only_resmlp", "multihead_full_finetune")
SEEDS = (31031, 31032, 31033, 31034, 31035)
THYLOGALE = "thylogale_billardierii"
SMOKE_TARGET = "dasyurus_viverrinus"
SMOKE_FOLD = "fold01"
SMOKE_ENDPOINT = "fraction100/full"
SMOKE_SEED = 31031
EXPECTED_RUNTIME = {
    "python": "3.12.13", "python_major_minor": "3.12", "torch": "2.7.1",
    "numpy": "2.2.6", "scipy": "1.16.3", "scikit_learn": "1.9.0",
    "threadpoolctl": "3.6.0", "system": "Darwin", "machine": "arm64",
    "device": "cpu", "route": "mac_cpu", "torch_threads": 1, "blas_threads": 1,
}


class NeuralSensitivityError(ValueError):
    """Raised when an input, execution, or closure contract is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NeuralSensitivityError(message)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_digest(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    descriptor = f"{value.dtype.str}|{value.shape}".encode("ascii")
    return hashlib.sha256(descriptor + b"\0" + value.tobytes(order="C")).hexdigest()


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NeuralSensitivityError(f"invalid_json:{path}") from exc
    _require(isinstance(value, dict), f"json_object_required:{path}")
    return value


def _validated_self_digest(value: Mapping[str, Any], key: str, message: str) -> str:
    body = dict(value)
    claimed = body.pop(key, None)
    _require(_is_digest(claimed) and digest_value(body) == claimed, message)
    return str(claimed)


def _write_json_idempotent(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical(value) + b"\n"
    if path.exists():
        _require(path.read_bytes() == raw, f"existing_output_drift:{path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical(value) + b"\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise NeuralSensitivityError(f"immutable_record_exists:{path}") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _source_sha() -> str:
    return sha256_file(Path(__file__).resolve())


def _require_file_sha(path: Path, expected: str, message: str) -> None:
    _require(path.is_file() and not path.is_symlink() and sha256_file(path) == expected, message)


@dataclass(frozen=True)
class InnerTask:
    target: str
    held_fold: str
    endpoint: str
    method: str
    seed: int


@dataclass(frozen=True)
class OuterTask:
    target: str
    endpoint: str
    method: str
    seed: int


def build_inner_inventory() -> tuple[InnerTask, ...]:
    return tuple(
        InnerTask(target, fold, endpoint, method, seed)
        for target in SPECIES for fold in FOLDS for endpoint in ENDPOINTS
        for method in METHODS for seed in SEEDS
    )


def build_outer_inventory() -> tuple[OuterTask, ...]:
    return tuple(
        OuterTask(target, endpoint, method, seed)
        for target in SPECIES for endpoint in ENDPOINTS for method in METHODS for seed in SEEDS
    )


def inventory_counts() -> dict[str, int]:
    inner = build_inner_inventory()
    outer = build_outer_inventory()
    return {
        "inner_logical_tasks": len(inner), "inner_physical_fits": len(inner) * 2,
        "outer_logical_tasks": len(outer), "outer_physical_fits": len(outer),
        "total_logical_tasks": len(inner) + len(outer),
        "total_physical_fits": len(inner) * 2 + len(outer),
    }


def lower_median(values: Sequence[int]) -> int:
    values = list(values)
    _require(len(values) == 5, "lower_median_requires_five_folds")
    _require(all(type(value) is int and 1 <= value <= 300 for value in values), "invalid_selected_epoch")
    return sorted(values)[2]


def validate_epoch_completeness(
    records: Iterable[Mapping[str, Any]], *, expected: int | None = None,
) -> dict[tuple[str, str, str, int], int]:
    result: dict[tuple[str, str, str, int], int] = {}
    for record in records:
        key = (str(record.get("target")), str(record.get("endpoint")), str(record.get("method")), int(record.get("seed")))
        _require(key not in result and key[0] in SPECIES and key[1] in ENDPOINTS and key[2] in METHODS and key[3] in SEEDS, "epoch_record_identity_drift")
        folds = record.get("fold_epochs")
        _require(isinstance(folds, list), "epoch_record_folds_missing")
        result[key] = lower_median(folds)
        _require(record.get("full_training_epochs", result[key]) == result[key], "epoch_lower_median_mismatch")
    if expected is not None:
        _require(len(result) == expected, "epoch_record_inventory_incomplete")
    return result


def _task_digest(task: InnerTask | OuterTask, lane: str) -> str:
    return digest_value({"lane": lane, "task": asdict(task)})


def _validate_manifest_record(root: Path, record: Mapping[str, Any]) -> Path:
    _require(set(record) == {"path", "sha256", "metadata_digest"}, "input_manifest_record_schema_drift")
    relative = Path(str(record["path"]))
    _require(not relative.is_absolute() and ".." not in relative.parts, f"prepared_input_path_invalid:{relative}")
    candidate = root / relative
    _require(
        candidate.resolve().is_relative_to(root.resolve())
        and candidate.is_file() and not candidate.is_symlink(),
        f"prepared_input_missing:{relative}",
    )
    _require(sha256_file(candidate) == record["sha256"], f"prepared_input_hash_mismatch:{relative}")
    return candidate


def _manifest(root: Path = ROOT, *, verify_files: bool = True) -> dict[str, Any]:
    path = root / MANIFEST_REL
    raw = _read_json(path)
    body = dict(raw)
    claimed = body.pop("digest", None)
    _require(claimed == MANIFEST_DIGEST and digest_value(body) == claimed, "input_manifest_digest_mismatch")
    _require(raw.get("success") is True and raw.get("fits") == 0 and raw.get("outer_response_labels_read") == 0, "input_manifest_boundary_invalid")
    _require(raw.get("role_filter_checks") == 896 and raw.get("schema_version") == "tasmania-sensitivity-neural-inputs-v1", "input_manifest_scope_drift")
    helper = root / DATA_HELPER_REL
    _require(sha256_file(helper) == DATA_HELPER_SHA256 == raw.get("script_sha256"), "data_helper_source_hash_mismatch")
    records = raw.get("files")
    _require(isinstance(records, list) and len(records) == 49, "input_manifest_file_inventory_drift")
    for record in records:
        _require(isinstance(record, Mapping) and set(record) == {"path", "sha256", "metadata_digest"}, "input_manifest_record_schema_drift")
        if verify_files:
            _validate_manifest_record(root, record)
    return raw


def _load_module_from_file(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"module_import_failed:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_data_helper(root: Path, manifest: Mapping[str, Any]) -> ModuleType:
    path = root / DATA_HELPER_REL
    _require(sha256_file(path) == DATA_HELPER_SHA256 == manifest.get("script_sha256"), "data_helper_source_changed")
    return _load_module_from_file("_tasmania_pseudoabsence_neural_data_bound", path)


def load_bound_npz(path: Path, data_helper: Any) -> tuple[dict[str, np.ndarray], Mapping[str, Any]]:
    arrays, metadata = data_helper.load_bound_npz(path)
    _require(isinstance(arrays, dict) and isinstance(metadata, Mapping), f"prepared_input_invalid:{path.name}")
    return arrays, metadata


def _load_manifest_case(
    root: Path, manifest: Mapping[str, Any], relative: Path, data_helper: Any,
) -> tuple[dict[str, np.ndarray], Mapping[str, Any]]:
    records = [record for record in manifest["files"] if record["path"] == str(relative)]
    _require(len(records) == 1, f"prepared_input_manifest_record_missing:{relative}")
    path = _validate_manifest_record(root, records[0])
    arrays, metadata = load_bound_npz(path, data_helper)
    _require(metadata.get("digest") == records[0]["metadata_digest"], f"prepared_metadata_binding_mismatch:{relative}")
    return arrays, metadata


def _check_float_matrix(value: Any, name: str, width: int = 77) -> np.ndarray:
    _require(isinstance(value, np.ndarray) and value.dtype == np.float32 and value.ndim == 2 and len(value) > 0 and value.shape[1] == width and np.isfinite(value).all(), f"{name}_predictor_array_invalid")
    return value


def _check_labels(value: Any, rows: int, name: str) -> np.ndarray:
    _require(isinstance(value, np.ndarray) and value.dtype == np.float32 and value.shape == (rows,) and np.isfinite(value).all() and set(np.unique(value).tolist()) == {0.0, 1.0}, f"{name}_class_support_failure")
    return value


def _check_cells(value: Any, rows: int, name: str) -> np.ndarray:
    _require(isinstance(value, np.ndarray) and value.ndim == 1 and value.shape == (rows,) and len(set(value.tolist())) == rows, f"{name}_cell_support_invalid")
    return value


def validate_inner_arrays(arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    held_x = _check_float_matrix(arrays.get("x_held"), "inner_held")
    held = _check_cells(arrays.get("held_cells"), len(held_x), "inner_held")
    counts: dict[str, Any] = {}
    for endpoint in ENDPOINTS:
        prefix = f"target_{SLUGS[endpoint]}"
        counts[endpoint] = {}
        for role in ("discovery", "stopping", "replay"):
            x = _check_float_matrix(arrays.get(f"{prefix}_x_{role}"), f"{endpoint}_{role}")
            _check_labels(arrays.get(f"{prefix}_y_{role}"), len(x), f"{endpoint}_{role}")
            _check_cells(arrays.get(f"{prefix}_cells_{role}"), len(x), f"{endpoint}_{role}")
            counts[endpoint][role] = len(x)
    return {"held_rows": len(held), "predictor_count": held_x.shape[1], "roles": counts}


def validate_outer_arrays(arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    _require(not any(name.startswith("y_held") for name in arrays), "outer_held_response_labels_prohibited")
    held_x = _check_float_matrix(arrays.get("x_held"), "outer_held")
    held = _check_cells(arrays.get("held_cells"), len(held_x), "outer_held")
    patch = arrays.get("held_patch")
    _require(isinstance(patch, np.ndarray) and patch.shape == (len(held),), "outer_held_patch_invalid")
    counts: dict[str, int] = {}
    for endpoint in ENDPOINTS:
        prefix = f"target_{SLUGS[endpoint]}"
        x = _check_float_matrix(arrays.get(f"{prefix}_x"), f"outer_{endpoint}")
        _check_labels(arrays.get(f"{prefix}_y"), len(x), f"outer_{endpoint}")
        _check_cells(arrays.get(f"{prefix}_cells"), len(x), f"outer_{endpoint}")
        counts[endpoint] = len(x)
    return {"held_rows": len(held), "predictor_count": held_x.shape[1], "training_rows": counts}


def load_inputs(root: Path = ROOT) -> dict[str, Any]:
    manifest = _manifest(root)
    helper = _load_data_helper(root, manifest)
    inner: dict[tuple[str, str], tuple[dict[str, np.ndarray], Mapping[str, Any]]] = {}
    outer: dict[str, tuple[dict[str, np.ndarray], Mapping[str, Any]]] = {}
    map_case: tuple[dict[str, np.ndarray], Mapping[str, Any]] | None = None
    for record in manifest["files"]:
        path = root / str(record["path"])
        arrays, metadata = load_bound_npz(path, helper)
        _require(metadata.get("digest") == record["metadata_digest"], f"prepared_metadata_binding_mismatch:{path.name}")
        if "/inner/" in str(record["path"]):
            arrays.pop("y_held", None)
            target, fold = path.stem.rsplit("--", 1)
            validate_inner_arrays(arrays)
            inner[(target, fold)] = (arrays, metadata)
        elif "/outer/" in str(record["path"]):
            validate_outer_arrays(arrays)
            outer[path.stem] = (arrays, metadata)
        elif path.name == "map.npz":
            x = _check_float_matrix(arrays.get("x"), "map")
            cells = _check_cells(arrays.get("cells"), len(x), "map")
            _require(len(cells) == 71023, "map_domain_size_drift")
            map_case = arrays, metadata
    _require(set(inner) == {(target, fold) for target in SPECIES for fold in FOLDS}, "inner_case_cross_product_incomplete")
    _require(set(outer) == set(SPECIES), "outer_case_cross_product_incomplete")
    _require(map_case is not None, "map_case_missing")
    return {"manifest": manifest, "inner": inner, "outer": outer, "map": map_case}


def _load_recovery_module(root: Path) -> ModuleType:
    path = root / RECOVERY_REL
    _require(path.is_file() and sha256_file(path) == RECOVERY_SOURCE_SHA256, "recovery_source_hash_mismatch")
    return _load_module_from_file("_tasmania_auxiliary_recovery_for_neural", path)


def _load_staged(root: Path, stage_root: Path) -> tuple[Any, Any, ModuleType]:
    aggregate_path = root / RECOVERY_AGGREGATE_REL
    _require_file_sha(
        aggregate_path, RECOVERY_AGGREGATE_SHA256,
        "auxiliary_recovery_aggregate_hash_mismatch",
    )
    aggregate = _read_json(aggregate_path)
    stage_manifest = stage_root / "reconstruction-manifest.json"
    _require(
        stage_manifest.is_file() and not stage_manifest.is_symlink()
        and sha256_file(stage_manifest) == aggregate.get("stage_manifest_digest"),
        "reconstruction_stage_manifest_binding_mismatch",
    )
    recovery = _load_recovery_module(root)
    data, config = recovery._load_staged_config(stage_root)
    return data, config, recovery


def _attest_runtime(data: Any, config: Any) -> dict[str, Any]:
    try:
        runtime = dict(data.runtime_attestation(config, strict=True))
    except Exception as exc:
        raise NeuralSensitivityError(f"historical_neural_runtime_mismatch:{exc}") from exc
    _require(platform.python_version() == EXPECTED_RUNTIME["python"], "python_patch_runtime_mismatch")
    expected = {key: value for key, value in EXPECTED_RUNTIME.items() if key != "python"}
    _require(runtime == expected, "historical_neural_runtime_mismatch")
    return {"python": platform.python_version(), **runtime}


def _attest_live_thread_pools() -> list[dict[str, Any]]:
    from threadpoolctl import threadpool_info

    records = sorted(
        (
            {
                "user_api": str(row.get("user_api")),
                "internal_api": str(row.get("internal_api")),
                "prefix": str(row.get("prefix")),
                "num_threads": int(row.get("num_threads", 0)),
            }
            for row in threadpool_info()
            if row.get("user_api") in {"blas", "openmp"}
        ),
        key=lambda row: (row["user_api"], row["internal_api"], row["prefix"]),
    )
    _require(all(row["num_threads"] == 1 for row in records), "live_thread_pool_limit_mismatch")
    return records


def _recovery_inventory(root: Path, stage_root: Path) -> dict[str, Any]:
    aggregate_path = root / RECOVERY_AGGREGATE_REL
    _require(aggregate_path.is_file() and sha256_file(aggregate_path) == RECOVERY_AGGREGATE_SHA256, "auxiliary_recovery_aggregate_hash_mismatch")
    aggregate = _read_json(aggregate_path)
    _require(
        aggregate.get("status") == "accepted" and aggregate.get("states") == 200
        and aggregate.get("fits") == 200 and aggregate.get("outer_attempted") == aggregate.get("outer_opened") == 0
        and aggregate.get("runtime") == {key: value for key, value in EXPECTED_RUNTIME.items() if key not in {"python"}},
        "auxiliary_recovery_closure_invalid",
    )
    recovery = _load_recovery_module(root)
    private = stage_root / "private"
    records: dict[tuple[str, str, int], dict[str, Any]] = {}
    serialization = []
    semantic = []
    for target in SPECIES:
        for fold in FOLDS:
            for seed in SEEDS:
                state, receipt_path = recovery._state_output_paths(private, target, fold, seed)
                _require(state.is_file() and not state.is_symlink() and receipt_path.is_file() and not receipt_path.is_symlink(), f"auxiliary_state_missing:{target}:{fold}:{seed}")
                row = _read_json(receipt_path)
                _require(
                    row.get("status") == "accepted" and row.get("target") == target
                    and row.get("held_fold") == fold and row.get("seed") == seed
                    and row.get("serialization_sha256") == sha256_file(state)
                    and row.get("outer_attempted") == row.get("outer_opened") == 0,
                    f"auxiliary_state_receipt_mismatch:{target}:{fold}:{seed}",
                )
                recovery._validate_serialized_state(
                    state, row["model_digest"], f"{target}/{fold}/{seed}",
                    target=target, held_fold=fold, seed=seed, replay_epochs=int(row["replay_epochs"]),
                )
                records[(target, fold, seed)] = {
                    "state_path": str(state.relative_to(root)),
                    "receipt_path": str(receipt_path.relative_to(root)),
                    "state_sha256": row["serialization_sha256"],
                    "receipt_sha256": sha256_file(receipt_path),
                    "model_digest": row["model_digest"],
                    "final_shared_digest": row["final_shared_digest"],
                    "runtime_digest": row["runtime_digest"],
                    "replay_epochs": row["replay_epochs"],
                }
                serialization.append((target, fold, seed, row["serialization_sha256"]))
                semantic.append(tuple(row[key] for key in ("initial_model_digest", "initial_shared_digest", "final_shared_digest", "model_digest", "prediction_digest")))
    _require(len(records) == 200, "auxiliary_state_inventory_incomplete")
    _require(digest_value(sorted(serialization)) == aggregate["serialization_inventory_digest"], "auxiliary_serialization_inventory_mismatch")
    _require(digest_value(sorted(semantic)) == aggregate["semantic_state_inventory_digest"], "auxiliary_semantic_inventory_mismatch")
    return {"aggregate": aggregate, "records": records}


def _mask_inner_case(arrays: Mapping[str, np.ndarray], endpoint: str) -> dict[str, Any]:
    from dsdm.categorical_support import apply_support_mask, fit_support_mask

    prefix = f"target_{SLUGS[endpoint]}"
    support = fit_support_mask(arrays[f"{prefix}_x_replay"])
    views: dict[str, np.ndarray] = {}
    audits: dict[str, Any] = {}
    for role in ("discovery", "stopping", "replay"):
        views[role], audits[role] = apply_support_mask(arrays[f"{prefix}_x_{role}"], support)
        _require(np.array_equal(views[role], arrays[f"{prefix}_x_{role}"]), f"filtered_training_support_changed:{endpoint}:{role}")
    views["held"], audits["held"] = apply_support_mask(arrays["x_held"], support)
    return {"support": support, "views": views, "audits": audits}


def _mask_outer_case(
    arrays: Mapping[str, np.ndarray], endpoint: str, map_arrays: Mapping[str, np.ndarray] | None = None,
) -> dict[str, Any]:
    from dsdm.categorical_support import apply_support_mask, fit_support_mask

    prefix = f"target_{SLUGS[endpoint]}"
    support = fit_support_mask(arrays[f"{prefix}_x"])
    training, training_audit = apply_support_mask(arrays[f"{prefix}_x"], support)
    _require(np.array_equal(training, arrays[f"{prefix}_x"]), f"filtered_outer_training_support_changed:{endpoint}")
    held, held_audit = apply_support_mask(arrays["x_held"], support)
    result = {
        "support": support, "training": training, "held": held,
        "audits": {"training": training_audit, "held": held_audit},
    }
    if map_arrays is not None:
        mapped, map_audit = apply_support_mask(map_arrays["x"], support)
        result.update({"map": mapped, "map_cells": map_arrays["cells"], "audits": {**result["audits"], "map": map_audit}})
    return result


def _goal037_package_index(root: Path) -> dict[str, dict[str, Any]]:
    receipt_path = root / GOAL037_RECEIPT_REL
    audit_path = root / AUX_AUDIT_REL
    _require(receipt_path.is_file() and sha256_file(receipt_path) == GOAL037_RECEIPT_SHA256, "goal037_receipt_hash_mismatch")
    _require(audit_path.is_file() and sha256_file(audit_path) == AUX_AUDIT_SHA256, "auxiliary_audit_hash_mismatch")
    audit = _read_json(audit_path)
    receipt = _read_json(receipt_path)
    _validated_self_digest(receipt, "receipt_digest", "goal037_receipt_digest_mismatch")
    _require(
        receipt.get("schema_version") == "goal037-outer-ready-aggregate-v1"
        and receipt.get("success") is True
        and receipt.get("decision") == "outer_ready_not_opened"
        and receipt.get("outer_attempted") == receipt.get("outer_opened") == 0
        and receipt.get("counts", {}).get("species") == 8
        and receipt.get("counts", {}).get("neural_packages") == 8,
        "goal037_receipt_scope_invalid",
    )
    _require(
        audit.get("outer_multihead_states", {}).get("canonical_production_states") == 40
        and audit["outer_multihead_states"].get("all_file_sha256_match_receipts") is True
        and audit["outer_multihead_states"].get("inner_substitution_permitted") is False,
        "outer_auxiliary_audit_invalid",
    )
    index: dict[str, dict[str, Any]] = {}
    package_root = root / GOAL037_PACKAGE_REL
    package_directories = sorted(item for item in package_root.iterdir() if item.is_dir())
    _require(
        len(package_directories) == 8
        and all(not item.is_symlink() and _is_digest(item.name) for item in package_directories),
        "goal037_package_directory_inventory_invalid",
    )
    leaf_inventory: list[str] = []
    content_inventory: list[str] = []
    for package in package_directories:
        metadata_path = package / "metadata.json"
        _require(metadata_path.is_file() and not metadata_path.is_symlink(), "goal037_package_metadata_missing")
        metadata = _read_json(metadata_path)
        body = dict(metadata)
        claimed = body.pop("receipt_digest", None)
        _require(claimed == digest_value(body), f"goal037_package_receipt_invalid:{metadata_path.parent.name}")
        target = str(metadata.get("target"))
        _require(target in SPECIES and target not in index, "goal037_package_target_inventory_invalid")
        _require(
            metadata.get("identity_digest") == package.name
            and metadata.get("schema_version") == "goal037-neural-package-v1",
            f"goal037_package_identity_invalid:{target}",
        )
        _require(metadata.get("outer_attempted") == metadata.get("outer_opened") == 0, "goal037_package_outer_boundary_drift")
        artifacts = metadata.get("artifacts")
        _require(isinstance(artifacts, list), "goal037_package_artifacts_missing")
        by_id = {str(row.get("artifact_id")): row for row in artifacts}
        required_aux = {f"aux/multihead/seed{seed}" for seed in SEEDS}
        _require(required_aux.issubset(by_id), f"goal037_outer_auxiliary_incomplete:{target}")
        for seed in SEEDS:
            row = by_id[f"aux/multihead/seed{seed}"]
            model = metadata_path.parent / str(row["model_relative_path"])
            model_receipt = row.get("model_receipt", {})
            _require(
                model.resolve().is_relative_to(metadata_path.parent.resolve())
                and model.is_file() and not model.is_symlink()
                and sha256_file(model) == model_receipt.get("model_sha256")
                and row.get("model_digest") == model_receipt.get("state_digest"),
                f"goal037_outer_auxiliary_file_invalid:{target}:{seed}",
            )
        index[target] = {
            "package_path": str(metadata_path.parent.relative_to(root)),
            "metadata_sha256": sha256_file(metadata_path),
            "receipt_digest": claimed,
            "bundle_digest": metadata["bundle_digest"],
            "runtime_digest": metadata["runtime_digest"],
        }
        leaf_inventory.append(package.name)
        content_inventory.append(str(claimed))
    _require(set(index) == set(SPECIES), "goal037_package_cross_product_incomplete")
    _require(
        digest_value(sorted(leaf_inventory)) == receipt.get("neural_leaf_inventory_digest")
        and digest_value(sorted(content_inventory)) == receipt.get("neural_content_inventory_digest"),
        "goal037_package_accepted_inventory_mismatch",
    )
    from dsdm import outer_ready
    bundles = [
        outer_ready.load_outer_bundle(root / GOAL037_BUNDLE_REL / f"{target}.npz")
        for target in SPECIES
    ]
    _require(
        all(bundle.target == target for bundle, target in zip(bundles, SPECIES))
        and digest_value([
            {"target": bundle.target, "bundle_digest": bundle.bundle_digest}
            for bundle in bundles
        ]) == receipt.get("bundle_inventory_digest")
        and all(index[bundle.target]["bundle_digest"] == bundle.bundle_digest for bundle in bundles),
        "goal037_bundle_accepted_inventory_mismatch",
    )
    return index


def _validate_outer_auxiliary_models(
    root: Path, package_index: Mapping[str, Mapping[str, Any]], outer_ready: Any,
) -> dict[tuple[str, int], dict[str, Any]]:
    records: dict[tuple[str, int], dict[str, Any]] = {}
    for target in SPECIES:
        package = root / str(package_index[target]["package_path"])
        metadata_path = package / "metadata.json"
        _require(sha256_file(metadata_path) == package_index[target]["metadata_sha256"], f"goal037_package_metadata_changed:{target}")
        metadata = _read_json(metadata_path)
        bundle = outer_ready.load_outer_bundle(root / GOAL037_BUNDLE_REL / f"{target}.npz")
        _require(bundle.bundle_digest == package_index[target]["bundle_digest"], f"goal037_outer_bundle_mismatch:{target}")
        prepared = outer_ready.prepare_outer_bundle(bundle)
        challenge_x, challenge_species = outer_ready._challenge_with_species(prepared["auxiliary"], bundle.arrays["aux_species"])
        names = tuple(name for name in SPECIES if name != target)
        by_id = {row["artifact_id"]: row for row in metadata["artifacts"]}
        for seed in SEEDS:
            row = by_id[f"aux/multihead/seed{seed}"]
            model_path = package / row["model_relative_path"]
            model = outer_ready.load_multihead_model(
                model_path, spec=outer_ready._architecture(), input_dim=77,
                species_names=names, expected=row["model_receipt"],
                challenge_x=challenge_x, challenge_species=challenge_species,
            )
            shared = outer_ready._shared_state(model)
            shared_digest = outer_ready._shared_digest(model)
            _require(shared_digest == row["final_shared_digest"], f"goal037_outer_auxiliary_shared_mismatch:{target}:{seed}")
            records[(target, seed)] = {
                "package_path": str(package.relative_to(root)),
                "metadata_sha256": package_index[target]["metadata_sha256"],
                "artifact_id": row["artifact_id"],
                "model_path": row["model_relative_path"],
                "model_sha256": row["model_receipt"]["model_sha256"],
                "model_state_digest": row["model_digest"],
                "final_shared_digest": row["final_shared_digest"],
                "challenge_prediction_digest": row["model_receipt"]["challenge_prediction_digest"],
                "shared_state_digest": digest_value(sorted((name, array_digest(value.detach().cpu().numpy())) for name, value in shared.items())),
            }
    _require(len(records) == 40, "goal037_outer_auxiliary_validation_incomplete")
    return records


def _accepted_inner_authorities(
    root: Path, stage_root: Path, data: Any, config: Any, recovery: ModuleType,
) -> dict[tuple[str, str], dict[str, Any]]:
    bundles = data.validate_bundle_inventory(root / GOAL035_BUNDLE_REL, config=config)
    leaves = recovery._accepted_leaf_metadata(
        data, config, bundles, root / GOAL035_LEAF_REL,
    )
    recovery._bind_accepted_metadata_inventory(recovery._read_audit(root), leaves)
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for key, (leaf, metadata) in leaves.items():
        metadata_path = leaf / "metadata.json"
        predictions_path = leaf / "predictions.npy"
        _require(metadata_path.is_file() and predictions_path.is_file(), f"accepted_inner_leaf_files_missing:{key}")
        records[key] = {
            "leaf_path": str(leaf.relative_to(root)),
            "metadata_sha256": sha256_file(metadata_path),
            "predictions_sha256": sha256_file(predictions_path),
            "prediction_digest": metadata["prediction_digest"],
            "identity": metadata["identity"],
        }
    _require(set(records) == {(target, fold) for target in SPECIES for fold in FOLDS}, "accepted_inner_authority_inventory_incomplete")
    return records


def _thylogale_zero_policy(root: Path) -> dict[str, Any]:
    path = root / SOURCE_CENSUS_REL
    _require(path.is_file() and sha256_file(path) == SOURCE_CENSUS_SHA256, "source_census_hash_mismatch")
    report = _read_json(path)
    rows = [row for row in report.get("records", ()) if row.get("species") == THYLOGALE]
    _require(len(rows) == 112, "thylogale_role_inventory_drift")
    _require(all(row.get("excluded", {}).get("rows") == 0 for row in rows), "thylogale_not_zero_pseudoabsence_control")
    return {
        "roles": len(rows),
        "inventory_digest": digest_value([
            (row["held_fold"], row["endpoint"], row["role"], row["baseline_id_set_digest"], row["retained_id_set_digest"])
            for row in rows
        ]),
    }


def _bindings(root: Path, stage_root: Path) -> dict[str, str]:
    return {
        "runner_sha256": _source_sha(),
        "input_manifest_sha256": sha256_file(root / MANIFEST_REL),
        "input_manifest_digest": MANIFEST_DIGEST,
        "data_helper_sha256": DATA_HELPER_SHA256,
        "recovery_source_sha256": RECOVERY_SOURCE_SHA256,
        "recovery_aggregate_sha256": RECOVERY_AGGREGATE_SHA256,
        "auxiliary_audit_sha256": AUX_AUDIT_SHA256,
        "source_census_sha256": SOURCE_CENSUS_SHA256,
        "goal037_receipt_sha256": GOAL037_RECEIPT_SHA256,
        "stage_manifest_sha256": sha256_file(stage_root / "reconstruction-manifest.json"),
    }


def _preparation_path(output: Path) -> Path:
    return output / "preparation.json"


def prepare(root: Path = ROOT, output: Path = DEFAULT_OUTPUT, stage_root: Path = DEFAULT_STAGE_ROOT) -> dict[str, Any]:
    root, output, stage_root = root.resolve(), output.resolve(), stage_root.resolve()
    _require(output == (root / PRIVATE_REL).resolve() or output.is_relative_to(root / INPUT_REL), "output_outside_private_sensitivity_root")
    inputs = load_inputs(root)
    recovery_inventory = _recovery_inventory(root, stage_root)
    data, config, recovery = _load_staged(root, stage_root)
    runtime = _attest_runtime(data, config)
    from dsdm import outer_ready

    package_index = _goal037_package_index(root)
    outer_aux = _validate_outer_auxiliary_models(root, package_index, outer_ready)
    inner_authorities = _accepted_inner_authorities(root, stage_root, data, config, recovery)
    masks = []
    for (target, fold), (arrays, metadata) in sorted(inputs["inner"].items()):
        for endpoint in ENDPOINTS:
            masked = _mask_inner_case(arrays, endpoint)
            masks.append({
                "lane": "inner", "target": target, "held_fold": fold, "endpoint": endpoint,
                "input_metadata_digest": metadata["digest"], "support_mask_digest": masked["support"].digest,
                "audits": masked["audits"],
            })
    map_arrays, map_metadata = inputs["map"]
    for target, (arrays, metadata) in sorted(inputs["outer"].items()):
        for endpoint in ENDPOINTS:
            masked = _mask_outer_case(arrays, endpoint, map_arrays if endpoint == "fraction100/full" else None)
            masks.append({
                "lane": "outer", "target": target, "held_fold": None, "endpoint": endpoint,
                "input_metadata_digest": metadata["digest"], "support_mask_digest": masked["support"].digest,
                "audits": masked["audits"],
            })
    _require(len(masks) == 336, "support_mask_inventory_incomplete")
    bindings = _bindings(root, stage_root)
    payload = {
        "schema_version": "tasmania-pseudoabsence-neural-preparation-v2",
        "success": True, "fitting": False, "scoring": False,
        "task_counts": inventory_counts(),
        "inner_task_inventory_digest": digest_value([asdict(task) for task in build_inner_inventory()]),
        "outer_task_inventory_digest": digest_value([asdict(task) for task in build_outer_inventory()]),
        "input_manifest_digest": inputs["manifest"]["digest"],
        "runtime": runtime,
        "auxiliary_recovery": {
            "states": len(recovery_inventory["records"]),
            "semantic_state_inventory_digest": recovery_inventory["aggregate"]["semantic_state_inventory_digest"],
            "serialization_inventory_digest": recovery_inventory["aggregate"]["serialization_inventory_digest"],
            "records": [
                {"target": target, "held_fold": fold, "seed": seed, **row}
                for (target, fold, seed), row in sorted(recovery_inventory["records"].items())
            ],
        },
        "outer_auxiliary": {
            "states": len(outer_aux),
            "inventory_digest": digest_value(sorted((target, seed, row) for (target, seed), row in outer_aux.items())),
            "records": [
                {"target": target, "seed": seed, **row}
                for (target, seed), row in sorted(outer_aux.items())
            ],
        },
        "accepted_inner_authorities": [
            {"target": target, "held_fold": fold, **row}
            for (target, fold), row in sorted(inner_authorities.items())
        ],
        "support_masks": masks,
        "support_mask_inventory_digest": digest_value(masks),
        "map_metadata_digest": map_metadata["digest"],
        "thylogale_negative_control": _thylogale_zero_policy(root),
        "execution_contract": {
            "workers": 3, "threads_per_worker": 1, "maximum_in_flight": 3,
            "inner_physical_fits_per_leaf": 2, "outer_physical_fits_per_leaf": 1,
            "outer_held_response_labels_read": 0,
            "inner_held_labels_present_only_in_prepared_source_npz": True,
            "map_endpoint": "fraction100/full",
        },
        "bindings": bindings,
    }
    payload["receipt_digest"] = digest_value(payload)
    _write_json_idempotent(_preparation_path(output), payload)
    return payload


def _load_preparation(root: Path, output: Path, stage_root: Path) -> dict[str, Any]:
    receipt = _read_json(_preparation_path(output))
    _validated_self_digest(receipt, "receipt_digest", "preparation_receipt_invalid")
    _require(receipt.get("success") is True and receipt.get("bindings") == _bindings(root, stage_root), "preparation_binding_drift")
    _require(receipt.get("task_counts") == inventory_counts(), "preparation_task_scope_drift")
    _require(receipt.get("auxiliary_recovery", {}).get("states") == 200, "preparation_inner_auxiliary_incomplete")
    _require(receipt.get("outer_auxiliary", {}).get("states") == 40, "preparation_outer_auxiliary_incomplete")
    _preparation_recovery_index(receipt)
    return receipt


def _preparation_inner_index(preparation: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    rows = preparation.get("accepted_inner_authorities")
    _require(isinstance(rows, list), "preparation_inner_authorities_missing")
    result = {(str(row["target"]), str(row["held_fold"])): row for row in rows}
    _require(len(result) == 40, "preparation_inner_authority_inventory_drift")
    return result


def _preparation_recovery_index(
    preparation: Mapping[str, Any],
) -> dict[tuple[str, str, int], Mapping[str, Any]]:
    rows = preparation.get("auxiliary_recovery", {}).get("records")
    _require(isinstance(rows, list), "preparation_recovery_records_missing")
    result = {
        (str(row["target"]), str(row["held_fold"]), int(row["seed"])): row
        for row in rows
    }
    _require(
        set(result) == {
            (target, fold, seed)
            for target in SPECIES for fold in FOLDS for seed in SEEDS
        },
        "preparation_recovery_inventory_drift",
    )
    return result


def _preparation_outer_aux_index(preparation: Mapping[str, Any]) -> dict[tuple[str, int], Mapping[str, Any]]:
    rows = preparation.get("outer_auxiliary", {}).get("records")
    _require(isinstance(rows, list), "preparation_outer_auxiliary_records_missing")
    result = {(str(row["target"]), int(row["seed"])): row for row in rows}
    _require(len(result) == 40, "preparation_outer_auxiliary_inventory_drift")
    return result


def _validate_outer_package_bindings(
    preparation: Mapping[str, Any], live_packages: Mapping[str, Mapping[str, Any]],
) -> None:
    _require(set(live_packages) == set(SPECIES), "live_outer_package_inventory_drift")
    for (target, seed), authority in _preparation_outer_aux_index(preparation).items():
        live = live_packages[target]
        _require(
            authority.get("artifact_id") == f"aux/multihead/seed{seed}"
            and authority.get("package_path") == live.get("package_path")
            and authority.get("metadata_sha256") == live.get("metadata_sha256"),
            f"preparation_outer_package_binding_drift:{target}:{seed}",
        )


def _load_case(root: Path, task: InnerTask | OuterTask) -> tuple[dict[str, np.ndarray], Mapping[str, Any], dict[str, np.ndarray] | None, Mapping[str, Any] | None]:
    manifest = _manifest(root, verify_files=False)
    helper = _load_data_helper(root, manifest)
    if isinstance(task, InnerTask):
        relative = INPUT_REL / "inputs/inner" / f"{task.target}--{task.held_fold}.npz"
        arrays, metadata = _load_manifest_case(root, manifest, relative, helper)
        arrays.pop("y_held", None)
        validate_inner_arrays(arrays)
        return arrays, metadata, None, None
    relative = INPUT_REL / "inputs/outer" / f"{task.target}.npz"
    arrays, metadata = _load_manifest_case(root, manifest, relative, helper)
    validate_outer_arrays(arrays)
    map_arrays = map_metadata = None
    if task.endpoint == "fraction100/full":
        map_arrays, map_metadata = _load_manifest_case(
            root, manifest, INPUT_REL / "inputs/map.npz", helper,
        )
        _check_float_matrix(map_arrays.get("x"), "map")
        _check_cells(map_arrays.get("cells"), len(map_arrays["x"]), "map")
    return arrays, metadata, map_arrays, map_metadata


def _runtime_peak_rss_bytes() -> int:
    # Darwin reports bytes; Linux reports KiB.  Production is Darwin, but keep
    # tests and read-only validation portable.
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def _semantic_lifecycle(lifecycle: Any) -> dict[str, Any]:
    return {
        "selected_epoch": int(lifecycle.selected_epoch),
        "discovery_executed_epochs": int(lifecycle.discovery_executed_epochs),
        "stopping_status": str(lifecycle.stopping_status),
        "initial_model_digest": str(lifecycle.initial_model_digest),
        "replay_initial_model_digest": str(lifecycle.replay_initial_model_digest),
        "initial_shared_digest": str(lifecycle.initial_shared_digest),
        "final_shared_digest": str(lifecycle.final_shared_digest),
        "initial_head_digest": str(lifecycle.initial_head_digest),
        "model_digest": str(lifecycle.model_digest),
        "lifecycle_prediction_digest": str(lifecycle.prediction_digest),
    }


def _semantic_exact_fit(fit: Any) -> dict[str, Any]:
    return {
        "exact_epochs": int(fit.epochs),
        "initial_model_digest": str(fit.initial_model_digest),
        "initial_shared_digest": str(fit.initial_shared_digest),
        "initial_head_digest": str(fit.initial_head_digest),
        "model_digest": str(fit.state_digest),
        "final_shared_digest": str(fit.final_shared_digest),
    }


def _load_recovered_inner_shared(
    root: Path, stage_root: Path, task: InnerTask,
    recovery_records: Mapping[tuple[str, str, int], Mapping[str, Any]], recovery: ModuleType,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    import torch

    record = recovery_records.get((task.target, task.held_fold, task.seed))
    _require(isinstance(record, Mapping), "inner_auxiliary_record_missing")
    state_path, receipt_path = recovery._state_output_paths(
        stage_root / "private", task.target, task.held_fold, task.seed,
    )
    _require(
        state_path.resolve().is_relative_to(stage_root.resolve())
        and receipt_path.resolve().is_relative_to(stage_root.resolve())
        and state_path.is_relative_to(root) and receipt_path.is_relative_to(root)
        and not state_path.is_symlink() and not receipt_path.is_symlink()
        and str(state_path.relative_to(root)) == record.get("state_path")
        and str(receipt_path.relative_to(root)) == record.get("receipt_path"),
        "inner_auxiliary_canonical_path_mismatch",
    )
    _require(sha256_file(state_path) == record["state_sha256"] and sha256_file(receipt_path) == record["receipt_sha256"], "inner_auxiliary_file_changed")
    payload = torch.load(state_path, map_location="cpu", weights_only=True)
    _require(
        isinstance(payload, Mapping) and isinstance(payload.get("state_dict"), Mapping)
        and payload.get("semantic_model_digest") == record["model_digest"]
        and payload.get("target") == task.target and payload.get("held_fold") == task.held_fold
        and payload.get("seed") == task.seed,
        "inner_auxiliary_payload_invalid",
    )
    shared = {
        name: value for name, value in payload["state_dict"].items()
        if name.startswith(("stem.", "trunk.", "final_norm."))
    }
    _require(shared, "inner_auxiliary_shared_state_empty")
    digest = hashlib.sha256()
    for name, value in sorted(shared.items()):
        digest.update(name.encode("utf-8")); digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    _require(digest.hexdigest() == record["final_shared_digest"], "inner_auxiliary_shared_state_mismatch")
    return shared, record


def _load_outer_shared(
    root: Path, task: OuterTask, authority: Mapping[str, Any], outer_ready: Any,
) -> tuple[dict[str, Any], Mapping[str, Any], Mapping[str, Any], Any, Any]:
    package = root / str(authority["package_path"])
    _require(
        package.resolve().is_relative_to((root / GOAL037_PACKAGE_REL).resolve())
        and package.is_dir() and not package.is_symlink()
        and authority.get("artifact_id") == f"aux/multihead/seed{task.seed}",
        "outer_auxiliary_authority_path_or_identity_invalid",
    )
    metadata_path = package / "metadata.json"
    _require(sha256_file(metadata_path) == authority["metadata_sha256"], "outer_auxiliary_package_metadata_changed")
    metadata = _read_json(metadata_path)
    _require(metadata.get("target") == task.target, "outer_auxiliary_package_target_mismatch")
    bundle = outer_ready.load_outer_bundle(root / GOAL037_BUNDLE_REL / f"{task.target}.npz")
    prepared = outer_ready.prepare_outer_bundle(bundle)
    challenge_x, challenge_species = outer_ready._challenge_with_species(prepared["auxiliary"], bundle.arrays["aux_species"])
    row = next(item for item in metadata["artifacts"] if item["artifact_id"] == authority["artifact_id"])
    _require(row.get("model_relative_path") == authority.get("model_path"), "outer_auxiliary_model_path_drift")
    model_path = package / str(row["model_relative_path"])
    _require(
        model_path.resolve().is_relative_to(package.resolve())
        and model_path.is_file() and not model_path.is_symlink(),
        "outer_auxiliary_model_path_invalid",
    )
    _require(
        row["model_receipt"]["model_sha256"] == authority["model_sha256"]
        and row["model_digest"] == authority["model_state_digest"]
        and row["final_shared_digest"] == authority["final_shared_digest"],
        "outer_auxiliary_authority_drift",
    )
    model = outer_ready.load_multihead_model(
        model_path, spec=outer_ready._architecture(), input_dim=77,
        species_names=tuple(name for name in SPECIES if name != task.target), expected=row["model_receipt"],
        challenge_x=challenge_x, challenge_species=challenge_species,
    )
    shared = outer_ready._shared_state(model)
    _require(outer_ready._shared_digest(model) == authority["final_shared_digest"], "outer_auxiliary_shared_transfer_mismatch")
    return shared, row, metadata, bundle, prepared


def _original_inner_comparison(
    root: Path, task: InnerTask, result: Mapping[str, Any], scores: np.ndarray,
    authority: Mapping[str, Any], fit_seed: int,
) -> dict[str, Any] | None:
    if task.target != THYLOGALE:
        return None
    leaf = root / str(authority["leaf_path"])
    _require(
        leaf.resolve().is_relative_to((root / GOAL035_LEAF_REL).resolve())
        and leaf.is_dir() and not leaf.is_symlink(),
        "thylogale_original_inner_authority_path_invalid",
    )
    metadata_path = leaf / "metadata.json"
    predictions_path = leaf / "predictions.npy"
    _require(sha256_file(metadata_path) == authority["metadata_sha256"] and sha256_file(predictions_path) == authority["predictions_sha256"], "thylogale_original_inner_authority_changed")
    metadata = _read_json(metadata_path)
    _require(
        metadata.get("target") == task.target and metadata.get("held_fold") == task.held_fold,
        "thylogale_original_inner_authority_identity_mismatch",
    )
    artifact_id = f"target/{task.endpoint}/seed{task.seed}/{task.method}"
    artifact = next((row for row in metadata["artifacts"] if row["artifact_id"] == artifact_id), None)
    _require(isinstance(artifact, Mapping), "thylogale_original_inner_artifact_missing")
    method_order = (
        "target_only_resmlp", "legacy_pooled_finetune", "multihead_frozen_trunk",
        "multihead_full_finetune", "target_plus_q_linear", "target_plus_q_deep",
    )
    original = np.load(predictions_path, allow_pickle=False)
    expected_scores = original[SEEDS.index(task.seed), ENDPOINTS.index(task.endpoint), method_order.index(task.method)]
    _require(np.array_equal(scores, expected_scores), "thylogale_inner_prediction_negative_control_failed")
    mapping = {
        "selected_epoch": "selected_epoch", "initial_model_digest": "initial_model_digest",
        "discovery_executed_epochs": "discovery_executed_epochs",
        "stopping_status": "stopping_status",
        "replay_initial_model_digest": "replay_initial_model_digest",
        "initial_shared_digest": "initial_shared_digest", "final_shared_digest": "final_shared_digest",
        "initial_head_digest": "initial_head_digest", "model_digest": "model_digest",
        "lifecycle_prediction_digest": "prediction_digest",
    }
    _require(all(result[key] == artifact[value] for key, value in mapping.items()), "thylogale_inner_semantic_negative_control_failed")
    _require(
        fit_seed == artifact.get("fit_seed")
        and result["selected_epoch"] == artifact.get("replay_epochs"),
        "thylogale_inner_seed_or_replay_epoch_negative_control_failed",
    )
    return {
        "status": "exact", "original_artifact_id": artifact_id,
        "original_leaf_metadata_sha256": authority["metadata_sha256"],
        "original_leaf_metadata_digest": digest_value(metadata),
        "original_prediction_digest": artifact["prediction_digest"],
        "original_model_digest": artifact["model_digest"],
    }


def _original_outer_model_and_scores(
    root: Path, task: OuterTask, package_metadata: Mapping[str, Any], package: Path,
    original_bundle: Any, original_prepared: Mapping[str, Any], outer_ready: Any,
    raw_held: np.ndarray, raw_map: np.ndarray | None,
) -> tuple[Mapping[str, Any], np.ndarray, np.ndarray | None]:
    row = next(
        (item for item in package_metadata["artifacts"] if item["artifact_id"] == f"target/{task.endpoint}/seed{task.seed}/{task.method}"),
        None,
    )
    _require(isinstance(row, Mapping), "accepted_primary_neural_artifact_missing")
    training = original_prepared["target"][task.endpoint]
    model_path = package / str(row["model_relative_path"])
    _require(
        model_path.resolve().is_relative_to(package.resolve())
        and model_path.is_file() and not model_path.is_symlink(),
        "accepted_primary_neural_model_path_invalid",
    )
    model = outer_ready.load_neural_model(
        model_path, spec=outer_ready._architecture(), input_dim=77,
        expected=row["model_receipt"], challenge_x=outer_ready._challenge(training),
    )
    support = original_prepared["target_masks"][task.endpoint]
    from dsdm.categorical_support import apply_support_mask
    held = apply_support_mask(raw_held, support)[0]
    held_scores = outer_ready.score_neural_model(model, held)
    map_scores = None
    if raw_map is not None:
        map_scores = outer_ready.score_neural_model(model, apply_support_mask(raw_map, support)[0])
    return row, held_scores, map_scores


def _save_predictions(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, path)


def _fit_inner_task(
    *, task: InnerTask, root: Path, output: Path, stage_root: Path,
    preparation: Mapping[str, Any], destination: Path, attempt: Path,
    production_caps_receipt_digest: str | None, smoke: bool = False,
) -> Mapping[str, Any]:
    started = time.monotonic()
    data, config, recovery = _load_staged(root, stage_root)
    runtime = _attest_runtime(data, config)  # strict and before any fit
    thread_pools = _attest_live_thread_pools()
    from dsdm.contracts import ARCHITECTURES, ArchitectureSpec
    from dsdm.final_inner_runner import _fit_seed
    from dsdm.real_six_path import _neural_lifecycle, _prepare_device, _residual_factory
    from dsdm.outer_ready import save_neural_model, score_neural_model

    arrays, metadata, _map_arrays, _map_metadata = _load_case(root, task)
    masked = _mask_inner_case(arrays, task.endpoint)
    prefix = f"target_{SLUGS[task.endpoint]}"
    fit_seed = _fit_seed(config, SimpleNamespace(target=task.target, held_fold=task.held_fold), task.endpoint, task.seed, "target")
    architecture = ArchitectureSpec(*next(item for item in ARCHITECTURES if item[0] == config.corrected_winner))
    auxiliary = None
    if task.method == "multihead_full_finetune":
        shared, auxiliary = _load_recovered_inner_shared(
            root, stage_root, task, _preparation_recovery_index(preparation), recovery,
        )
        factory = _residual_factory(architecture, 77, shared_state=shared)
        auxiliary_before = auxiliary["state_sha256"]
    else:
        factory = _residual_factory(architecture, 77)
        auxiliary_before = None
    _write_json_idempotent(attempt / "running.json", {
        "schema_version": "tasmania-pseudoabsence-neural-fit-running-v2",
        "lane": "inner",
        "task": asdict(task), "task_digest": _task_digest(task, "inner"),
        "physical_stages_entered": ["discovery", "replay"],
        "physical_fits_started": 2,
        "process_id": os.getpid(), "fit_started": True, "started_unix_ns": time.time_ns(),
    })
    lifecycle = _neural_lifecycle(
        factory, architecture, fit_seed, _prepare_device("cpu"),
        masked["views"]["discovery"], arrays[f"{prefix}_y_discovery"],
        masked["views"]["stopping"], arrays[f"{prefix}_y_stopping"],
        masked["views"]["replay"], arrays[f"{prefix}_y_replay"],
        masked["views"]["held"], max_epochs=300, patience=30, freeze_shared=False,
    )
    scores = score_neural_model(lifecycle.model, masked["views"]["held"])
    semantic = _semantic_lifecycle(lifecycle)
    # The historical digest hashes raw float bytes; retain it separately from
    # this runner's shape-aware file/content digest.
    raw_prediction_digest = hashlib.sha256(np.ascontiguousarray(scores).tobytes()).hexdigest()
    _require(raw_prediction_digest == semantic["lifecycle_prediction_digest"], "inner_lifecycle_prediction_mismatch")
    if auxiliary is not None:
        _require_file_sha(root / str(auxiliary["state_path"]), auxiliary_before, "inner_auxiliary_mutated_during_target_fit")
        _require(semantic["initial_shared_digest"] == auxiliary["final_shared_digest"], "inner_auxiliary_transfer_mismatch")
    stage = attempt / "stage"
    _require(not stage.exists(), "fit_stage_already_exists")
    stage.mkdir(parents=True)
    identity = {
        "schema_version": "tasmania-neural-sensitivity-model-v2", "lane": "inner",
        "task": asdict(task), "input_dim": 77, "architecture": config.corrected_winner,
        "fit_seed": fit_seed, "support_mask_digest": masked["support"].digest,
        "input_metadata_digest": metadata["digest"], "bindings": preparation["bindings"],
    }
    model_receipt = save_neural_model(
        lifecycle.model, stage / "model.pt", identity=identity,
        challenge_x=masked["views"]["replay"][: min(16, len(masked["views"]["replay"]))],
    )
    _save_predictions(stage / "predictions.npz", {
        "grid_cell_id": np.asarray(arrays["held_cells"], dtype=str),
        "scores": np.asarray(scores, dtype=np.float32),
    })
    negative = _original_inner_comparison(
        root, task, semantic, scores,
        _preparation_inner_index(preparation)[(task.target, task.held_fold)],
        fit_seed,
    )
    wall = time.monotonic() - started
    receipt: dict[str, Any] = {
        "schema_version": "tasmania-pseudoabsence-neural-inner-leaf-v2",
        "task": asdict(task), "task_digest": _task_digest(task, "inner"),
        "process_id": os.getpid(), "physical_fits": 2,
        "physical_stages_completed": ["discovery", "replay"], "fit_seed": fit_seed,
        **semantic,
        "support_mask_digest": masked["support"].digest, "support_audits": masked["audits"],
        "input_metadata_digest": metadata["digest"],
        "input_digests": {
            role: {"x": array_digest(masked["views"][role]), "y": array_digest(arrays[f"{prefix}_y_{role}"]), "cells": array_digest(arrays[f"{prefix}_cells_{role}"])}
            for role in ("discovery", "stopping", "replay")
        },
        "evaluation_id_digest": array_digest(np.asarray(arrays["held_cells"], dtype=str)),
        "prediction_digest": array_digest(scores),
        "prediction_raw_digest": raw_prediction_digest,
        "prediction_sha256": sha256_file(stage / "predictions.npz"),
        "model_receipt": model_receipt,
        "auxiliary": auxiliary,
        "auxiliary_unchanged": auxiliary is None or sha256_file(root / str(auxiliary["state_path"])) == auxiliary_before,
        "thylogale_negative_control": negative,
        "runtime": runtime, "thread_environment": dict(THREAD_ENVIRONMENT),
        "thread_pools": thread_pools,
        "wall_seconds": round(wall, 6), "peak_rss_bytes": _runtime_peak_rss_bytes(),
        "smoke_non_promotable": smoke,
        "production_caps_receipt_digest": production_caps_receipt_digest,
        "outer_held_response_labels_read": 0,
        "bindings": preparation["bindings"],
    }
    receipt["receipt_digest"] = digest_value(receipt)
    (stage / "receipt.json").write_bytes(_canonical(receipt) + b"\n")
    _publish_leaf(stage, destination)
    _write_json_idempotent(attempt / "completed.json", {
        "schema_version": "tasmania-pseudoabsence-neural-fit-complete-v2",
        "task_digest": receipt["task_digest"], "receipt_digest": receipt["receipt_digest"],
        "completed_unix_ns": time.time_ns(),
    })
    return receipt


def _fit_outer_task(
    *, task: OuterTask, root: Path, output: Path, stage_root: Path,
    preparation: Mapping[str, Any], destination: Path, attempt: Path,
    epochs: int, inner_epochs: Sequence[int], production_caps_receipt_digest: str,
) -> Mapping[str, Any]:
    started = time.monotonic()
    data, config, _recovery = _load_staged(root, stage_root)
    runtime = _attest_runtime(data, config)  # strict and before any fit
    thread_pools = _attest_live_thread_pools()
    from dsdm.contracts import ARCHITECTURES, ArchitectureSpec
    from dsdm.outer_ready import _fit_seed, exact_fit, save_neural_model, score_neural_model
    from dsdm.real_six_path import _residual_factory
    from dsdm import outer_ready

    arrays, metadata, map_arrays, map_metadata = _load_case(root, task)
    masked = _mask_outer_case(arrays, task.endpoint, map_arrays)
    prefix = f"target_{SLUGS[task.endpoint]}"
    architecture = ArchitectureSpec(*next(item for item in ARCHITECTURES if item[0] == config.corrected_winner))
    fit_seed = _fit_seed(task.target, task.endpoint, task.seed, "target")
    outer_aux_index = _preparation_outer_aux_index(preparation)
    authority = outer_aux_index[(task.target, task.seed)]
    shared = aux_row = package_metadata = original_bundle = original_prepared = None
    package = root / str(authority["package_path"])
    if task.method == "multihead_full_finetune":
        shared, aux_row, package_metadata, original_bundle, original_prepared = _load_outer_shared(root, task, authority, outer_ready)
        factory = _residual_factory(architecture, 77, shared_state=shared)
        aux_sha_before = sha256_file(package / str(aux_row["model_relative_path"]))
    else:
        # The accepted package also supplies the primary target model and its
        # original target support mask.  Load the package metadata now, but do
        # not use any auxiliary weights for target-only fitting.
        _require(sha256_file(package / "metadata.json") == authority["metadata_sha256"], "goal037_package_metadata_changed")
        package_metadata = _read_json(package / "metadata.json")
        _require(
            package.resolve().is_relative_to((root / GOAL037_PACKAGE_REL).resolve())
            and package.is_dir() and not package.is_symlink()
            and package_metadata.get("target") == task.target,
            "goal037_package_target_or_path_invalid",
        )
        original_bundle = outer_ready.load_outer_bundle(root / GOAL037_BUNDLE_REL / f"{task.target}.npz")
        original_prepared = outer_ready.prepare_outer_bundle(original_bundle)
        factory = _residual_factory(architecture, 77)
        aux_sha_before = authority["model_sha256"]
    _write_json_idempotent(attempt / "running.json", {
        "schema_version": "tasmania-pseudoabsence-neural-fit-running-v2",
        "lane": "outer",
        "task": asdict(task), "task_digest": _task_digest(task, "outer"),
        "physical_stages_entered": ["exact_fit"],
        "physical_fits_started": 1,
        "process_id": os.getpid(), "fit_started": True, "started_unix_ns": time.time_ns(),
    })
    fit = exact_fit(
        factory, architecture, fit_seed, masked["training"], arrays[f"{prefix}_y"], epochs=epochs,
    )
    scores = score_neural_model(fit.model, masked["held"])
    semantic = _semantic_exact_fit(fit)
    if task.method == "multihead_full_finetune":
        _require(semantic["initial_shared_digest"] == authority["final_shared_digest"], "outer_auxiliary_transfer_mismatch")
        _require_file_sha(package / str(aux_row["model_relative_path"]), aux_sha_before, "outer_auxiliary_mutated_during_target_fit")
    stage = attempt / "stage"
    _require(not stage.exists(), "fit_stage_already_exists")
    stage.mkdir(parents=True)
    identity = {
        "schema_version": "tasmania-neural-sensitivity-model-v2", "lane": "outer",
        "task": asdict(task), "input_dim": 77, "architecture": config.corrected_winner,
        "fit_seed": fit_seed, "exact_epochs": epochs,
        "support_mask_digest": masked["support"].digest,
        "input_metadata_digest": metadata["digest"], "bindings": preparation["bindings"],
    }
    model_receipt = save_neural_model(
        fit.model, stage / "model.pt", identity=identity,
        challenge_x=masked["training"][: min(16, len(masked["training"]))],
    )
    prediction_arrays: dict[str, np.ndarray] = {
        "grid_cell_id": np.asarray(arrays["held_cells"], dtype=str),
        "scores": np.asarray(scores, dtype=np.float32),
    }
    sensitivity_map_scores = accepted_primary_map_scores = None
    if task.endpoint == "fraction100/full":
        _require(map_arrays is not None and map_metadata is not None and "map" in masked, "full_endpoint_map_input_missing")
        sensitivity_map_scores = score_neural_model(fit.model, masked["map"])
    original_row, original_held_scores, original_map_scores = _original_outer_model_and_scores(
        root, task, package_metadata, package, original_bundle, original_prepared, outer_ready,
        arrays["x_held"], map_arrays["x"] if map_arrays is not None else None,
    )
    if task.endpoint == "fraction100/full":
        _require(original_map_scores is not None and sensitivity_map_scores is not None, "full_endpoint_primary_map_missing")
        accepted_primary_map_scores = original_map_scores
        prediction_arrays.update({
            "map_grid_cell_id": np.asarray(map_arrays["cells"], dtype=str),
            "sensitivity_map_scores": np.asarray(sensitivity_map_scores, dtype=np.float32),
            "accepted_primary_map_scores": np.asarray(accepted_primary_map_scores, dtype=np.float32),
        })
    negative = None
    if task.target == THYLOGALE:
        _require(np.array_equal(scores, original_held_scores), "thylogale_outer_prediction_negative_control_failed")
        _require(
            semantic["model_digest"] == original_row["model_digest"]
            and semantic["initial_model_digest"] == original_row["initial_model_digest"]
            and semantic["initial_shared_digest"] == original_row["initial_shared_digest"]
            and semantic["initial_head_digest"] == original_row["initial_head_digest"]
            and semantic["final_shared_digest"] == original_row["final_shared_digest"]
            and epochs == original_row["exact_epochs"] and fit_seed == original_row["fit_seed"],
            "thylogale_outer_semantic_negative_control_failed",
        )
        if task.endpoint == "fraction100/full":
            _require(np.array_equal(sensitivity_map_scores, original_map_scores), "thylogale_outer_map_negative_control_failed")
        negative = {
            "status": "exact", "original_artifact_id": original_row["artifact_id"],
            "original_model_digest": original_row["model_digest"],
            "held_prediction_digest": array_digest(original_held_scores),
            "map_prediction_digest": array_digest(original_map_scores) if original_map_scores is not None else None,
        }
    _save_predictions(stage / "predictions.npz", prediction_arrays)
    wall = time.monotonic() - started
    map_record = None
    primary_map_record = None
    if sensitivity_map_scores is not None:
        map_record = {
            "rows": 71023, "cell_digest": array_digest(np.asarray(map_arrays["cells"], dtype=str)),
            "prediction_digest": array_digest(sensitivity_map_scores),
            "support_mask_digest": masked["support"].digest,
        }
        primary_map_record = {
            "rows": 71023, "prediction_digest": array_digest(accepted_primary_map_scores),
            "original_artifact_id": original_row["artifact_id"],
            "original_model_sha256": original_row["model_receipt"]["model_sha256"],
            "original_model_state_digest": original_row["model_digest"],
            "original_support_mask_digest": original_prepared["target_masks"][task.endpoint].digest,
        }
    auxiliary_receipt = None
    if task.method == "multihead_full_finetune":
        auxiliary_receipt = {
            "authority": dict(authority),
            "artifact_model_digest": aux_row["model_digest"],
            "artifact_final_shared_digest": aux_row["final_shared_digest"],
            "unchanged_after_fit": sha256_file(package / str(aux_row["model_relative_path"])) == aux_sha_before,
        }
    receipt: dict[str, Any] = {
        "schema_version": "tasmania-pseudoabsence-neural-outer-leaf-v2",
        "task": asdict(task), "task_digest": _task_digest(task, "outer"),
        "process_id": os.getpid(), "physical_fits": 1,
        "physical_stages_completed": ["exact_fit"], "fit_seed": fit_seed,
        **semantic,
        "inner_selected_epochs": list(inner_epochs), "outer_selected_epoch": epochs,
        "support_mask_digest": masked["support"].digest, "support_audits": masked["audits"],
        "input_metadata_digest": metadata["digest"],
        "input_digest": {"x": array_digest(masked["training"]), "y": array_digest(arrays[f"{prefix}_y"]), "cells": array_digest(arrays[f"{prefix}_cells"])},
        "evaluation_id_digest": array_digest(np.asarray(arrays["held_cells"], dtype=str)),
        "prediction_digest": array_digest(scores),
        "prediction_sha256": sha256_file(stage / "predictions.npz"),
        "model_receipt": model_receipt,
        "auxiliary": auxiliary_receipt,
        "map": map_record, "accepted_primary_map": primary_map_record,
        "thylogale_negative_control": negative,
        "runtime": runtime, "thread_environment": dict(THREAD_ENVIRONMENT),
        "thread_pools": thread_pools,
        "wall_seconds": round(wall, 6), "peak_rss_bytes": _runtime_peak_rss_bytes(),
        "production_caps_receipt_digest": production_caps_receipt_digest,
        "outer_held_response_labels_read": 0,
        "bindings": preparation["bindings"],
    }
    receipt["receipt_digest"] = digest_value(receipt)
    (stage / "receipt.json").write_bytes(_canonical(receipt) + b"\n")
    _publish_leaf(stage, destination)
    _write_json_idempotent(attempt / "completed.json", {
        "schema_version": "tasmania-pseudoabsence-neural-fit-complete-v2",
        "task_digest": receipt["task_digest"], "receipt_digest": receipt["receipt_digest"],
        "completed_unix_ns": time.time_ns(),
    })
    return receipt


def _publish_leaf(stage: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    _require(not destination.exists(), "leaf_identity_collision")
    try:
        os.rename(stage, destination)
    except FileExistsError as exc:
        raise NeuralSensitivityError("leaf_identity_collision") from exc


def _begin_fit_attempt(
    root: Path, output: Path, lane: str, task: InnerTask | OuterTask,
    destination: Path, physical_stages: Sequence[str], preparation: Mapping[str, Any],
) -> Path:
    _require(not (output / "ABORT.json").exists(), "neural_panel_aborted")
    task_digest = _task_digest(task, lane)
    intent = output / lane / "intents" / f"{task_digest}.json"
    attempt = output / lane / "attempts" / task_digest
    _require(not destination.exists(), "fit_destination_already_exists")
    _require(not intent.exists() and not attempt.exists(), "orphan_or_failed_fit_intent")
    payload = {
        "schema_version": "tasmania-pseudoabsence-neural-fit-intent-v2",
        "lane": lane, "task": asdict(task), "task_digest": task_digest,
        "destination": str(destination.relative_to(output)),
        "physical_stages": list(physical_stages), "fit_started": False,
        "created_unix_ns": time.time_ns(), "bindings": preparation["bindings"],
    }
    _write_json_exclusive(intent, payload)
    attempt.mkdir(parents=True, exist_ok=False)
    _write_json_exclusive(attempt / "intent.json", payload)
    return attempt


def _record_attempt_failure(
    lane: str, task: InnerTask | OuterTask, attempt: Path, exc: BaseException,
) -> dict[str, Any]:
    path = attempt / "failed.json"
    if path.exists():
        failure = _read_json(path)
        _require(
            failure.get("lane") == lane
            and failure.get("task") == asdict(task)
            and failure.get("task_digest") == _task_digest(task, lane),
            "fit_failure_record_identity_mismatch",
        )
        return failure
    failure: dict[str, Any] = {
        "schema_version": "tasmania-pseudoabsence-neural-fit-failure-v2",
        "lane": lane, "task": asdict(task), "task_digest": _task_digest(task, lane),
        "error_type": type(exc).__name__, "error": str(exc), "failed_unix_ns": time.time_ns(),
    }
    _write_json_exclusive(path, failure)
    return failure


def _mark_fit_failure(output: Path, lane: str, task: InnerTask | OuterTask, attempt: Path, exc: BaseException) -> None:
    failure: dict[str, Any] = {
        "schema_version": "tasmania-pseudoabsence-neural-fit-failure-v2",
        "lane": lane, "task": asdict(task), "task_digest": _task_digest(task, lane),
        "error_type": type(exc).__name__, "error": str(exc), "failed_unix_ns": time.time_ns(),
    }
    try:
        failure = _record_attempt_failure(lane, task, attempt, exc)
    except BaseException as evidence_exc:
        failure["attempt_evidence_error"] = f"{type(evidence_exc).__name__}:{evidence_exc}"
    abort = {
        "schema_version": "tasmania-pseudoabsence-neural-panel-abort-v2",
        "status": "aborted_after_first_failure", "failure": failure,
    }
    try:
        _write_json_idempotent(output / "ABORT.json", abort)
    except BaseException:
        # Worker termination has already happened.  Preserve the originating
        # exception even when a full disk or damaged output root prevents the
        # best-effort abort receipt from being written.
        pass


def _mark_dispatcher_failure(output: Path, lane: str, exc: BaseException) -> None:
    failure = {
        "schema_version": "tasmania-pseudoabsence-neural-dispatcher-failure-v2",
        "lane": lane, "error_type": type(exc).__name__, "error": str(exc),
        "failed_unix_ns": time.time_ns(),
    }
    try:
        _write_json_idempotent(output / "ABORT.json", {
            "schema_version": "tasmania-pseudoabsence-neural-panel-abort-v2",
            "status": "aborted_after_dispatcher_failure", "failure": failure,
        })
    except BaseException:
        pass


def _prediction_payload(path: Path, *, expect_map: bool) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            expected = {"grid_cell_id", "scores"}
            if expect_map:
                expected |= {"map_grid_cell_id", "sensitivity_map_scores", "accepted_primary_map_scores"}
            _require(set(loaded.files) == expected, "leaf_prediction_inventory_mismatch")
            arrays = {name: np.array(loaded[name], copy=True) for name in loaded.files}
    except NeuralSensitivityError:
        raise
    except (OSError, ValueError) as exc:
        raise NeuralSensitivityError("leaf_prediction_payload_invalid") from exc
    keys = arrays["grid_cell_id"]
    scores = arrays["scores"]
    _require(keys.ndim == scores.ndim == 1 and keys.shape == scores.shape and keys.dtype.kind == "U", "leaf_prediction_shape_invalid")
    _require(len(set(keys.tolist())) == len(keys) and scores.dtype == np.float32 and np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "leaf_prediction_values_invalid")
    if expect_map:
        map_keys = arrays["map_grid_cell_id"]
        sensitivity = arrays["sensitivity_map_scores"]
        primary = arrays["accepted_primary_map_scores"]
        _require(map_keys.shape == sensitivity.shape == primary.shape == (71023,) and map_keys.dtype.kind == "U", "leaf_map_shape_invalid")
        _require(len(set(map_keys.tolist())) == 71023, "leaf_map_cells_invalid")
        _require(sensitivity.dtype == primary.dtype == np.float32 and np.isfinite(sensitivity).all() and np.isfinite(primary).all(), "leaf_map_values_invalid")
        _require(np.all((sensitivity >= 0) & (sensitivity <= 1)) and np.all((primary >= 0) & (primary <= 1)), "leaf_map_probability_invalid")
    return arrays


def _validate_prediction_file(
    path: Path, receipt: Mapping[str, Any], *, expect_map: bool,
) -> dict[str, np.ndarray]:
    _require_file_sha(path, str(receipt.get("prediction_sha256")), "leaf_prediction_file_mismatch")
    arrays = _prediction_payload(path, expect_map=expect_map)
    _require(array_digest(arrays["scores"]) == receipt.get("prediction_digest"), "leaf_prediction_digest_mismatch")
    if expect_map:
        map_receipt = receipt.get("map")
        primary_receipt = receipt.get("accepted_primary_map")
        _require(isinstance(map_receipt, Mapping), "leaf_map_receipt_missing")
        _require(isinstance(primary_receipt, Mapping), "leaf_primary_map_receipt_missing")
        _require(array_digest(arrays["sensitivity_map_scores"]) == map_receipt.get("prediction_digest"), "leaf_map_prediction_digest_mismatch")
        _require(array_digest(arrays["accepted_primary_map_scores"]) == primary_receipt.get("prediction_digest"), "leaf_primary_map_prediction_digest_mismatch")
    return arrays


def _validated_leaf(
    path: Path, task: InnerTask | OuterTask, lane: str, root: Path, stage_root: Path,
    preparation: Mapping[str, Any], production_caps_receipt_digest: str | None,
    *, smoke: bool = False,
) -> Mapping[str, Any]:
    _require(path.is_dir() and not path.is_symlink(), f"{lane}_leaf_missing")
    observed = {item.name for item in path.iterdir() if item.is_file()}
    _require(observed == {"model.pt", "predictions.npz", "receipt.json"}, f"{lane}_leaf_file_inventory_mismatch")
    receipt = _read_json(path / "receipt.json")
    _validated_self_digest(receipt, "receipt_digest", f"{lane}_leaf_receipt_mismatch")
    expected_schema = f"tasmania-pseudoabsence-neural-{lane}-leaf-v2"
    _require(receipt.get("schema_version") == expected_schema, f"{lane}_leaf_schema_mismatch")
    _require(receipt.get("task") == asdict(task) and receipt.get("task_digest") == _task_digest(task, lane), f"{lane}_leaf_task_mismatch")
    _require(receipt.get("bindings") == preparation.get("bindings"), f"{lane}_leaf_binding_mismatch")
    _require(receipt.get("production_caps_receipt_digest") == production_caps_receipt_digest, f"{lane}_leaf_cap_binding_mismatch")
    _require(receipt.get("smoke_non_promotable", False) is smoke, f"{lane}_leaf_smoke_status_mismatch")
    _require(receipt.get("outer_held_response_labels_read") == 0, f"{lane}_leaf_outer_response_boundary_drift")
    model_receipt = receipt.get("model_receipt")
    _require(isinstance(model_receipt, Mapping) and sha256_file(path / "model.pt") == model_receipt.get("model_sha256"), f"{lane}_leaf_model_file_mismatch")
    _require(receipt.get("model_digest") == model_receipt.get("state_digest"), f"{lane}_leaf_model_state_mismatch")
    prediction_path = path / "predictions.npz"
    expected_map = lane == "outer" and task.endpoint == "fraction100/full"
    payload = _validate_prediction_file(prediction_path, receipt, expect_map=expected_map)
    arrays, metadata, map_arrays, _map_metadata = _load_case(root, task)
    _require(receipt.get("input_metadata_digest") == metadata.get("digest"), f"{lane}_leaf_input_metadata_mismatch")
    _require(np.array_equal(payload["grid_cell_id"], np.asarray(arrays["held_cells"], dtype=str)), f"{lane}_leaf_evaluation_membership_mismatch")
    data, config, _recovery = _load_staged(root, stage_root)
    runtime = _attest_runtime(data, config)
    _require(receipt.get("runtime") == runtime, f"{lane}_leaf_runtime_mismatch")
    pools = receipt.get("thread_pools")
    _require(
        receipt.get("thread_environment") == THREAD_ENVIRONMENT
        and isinstance(pools, list)
        and all(isinstance(row, Mapping) and row.get("num_threads") == 1 for row in pools),
        f"{lane}_leaf_thread_enforcement_mismatch",
    )
    from dsdm import outer_ready
    if lane == "inner":
        masked = _mask_inner_case(arrays, task.endpoint)
        challenge = masked["views"]["replay"][: min(16, len(masked["views"]["replay"]))]
        prediction_x = masked["views"]["held"]
        _require(receipt.get("physical_fits") == 2, "inner_leaf_fit_count_mismatch")
    else:
        masked = _mask_outer_case(arrays, task.endpoint, map_arrays)
        challenge = masked["training"][: min(16, len(masked["training"]))]
        prediction_x = masked["held"]
        _require(receipt.get("physical_fits") == 1, "outer_leaf_fit_count_mismatch")
    _require(receipt.get("support_mask_digest") == masked["support"].digest and receipt.get("support_audits") == masked["audits"], f"{lane}_leaf_support_mask_mismatch")
    model = outer_ready.load_neural_model(
        path / "model.pt", spec=outer_ready._architecture(), input_dim=77,
        expected=model_receipt, challenge_x=challenge,
    )
    replayed = outer_ready.score_neural_model(model, prediction_x)
    _require(np.array_equal(replayed, payload["scores"]), f"{lane}_leaf_closed_prediction_tamper")
    if lane == "inner":
        auxiliary = receipt.get("auxiliary")
        if task.method == "multihead_full_finetune":
            _require(isinstance(auxiliary, Mapping), "inner_leaf_auxiliary_binding_missing")
            state_path = root / str(auxiliary["state_path"])
            _require(sha256_file(state_path) == auxiliary["state_sha256"] and receipt.get("initial_shared_digest") == auxiliary["final_shared_digest"], "inner_leaf_auxiliary_binding_mismatch")
        else:
            _require(auxiliary is None, "target_only_leaf_received_auxiliary_state")
        if task.target == THYLOGALE:
            comparison = _original_inner_comparison(
                root, task, receipt, payload["scores"],
                _preparation_inner_index(preparation)[(task.target, task.held_fold)],
                int(receipt["fit_seed"]),
            )
            _require(comparison == receipt.get("thylogale_negative_control"), "inner_leaf_thylogale_negative_control_receipt_mismatch")
    else:
        authority = _preparation_outer_aux_index(preparation)[(task.target, task.seed)]
        package = root / str(authority["package_path"])
        _require_file_sha(package / "metadata.json", str(authority["metadata_sha256"]), "outer_leaf_package_metadata_changed")
        package_metadata = _read_json(package / "metadata.json")
        original_bundle = outer_ready.load_outer_bundle(root / GOAL037_BUNDLE_REL / f"{task.target}.npz")
        original_prepared = outer_ready.prepare_outer_bundle(original_bundle)
        original_row, original_held, original_map = _original_outer_model_and_scores(
            root, task, package_metadata, package, original_bundle, original_prepared,
            outer_ready, arrays["x_held"], map_arrays["x"] if map_arrays is not None else None,
        )
        auxiliary = receipt.get("auxiliary")
        if task.method == "multihead_full_finetune":
            _require(isinstance(auxiliary, Mapping) and auxiliary.get("authority") == authority, "outer_leaf_auxiliary_binding_missing")
            aux_model = package / str(authority["model_path"])
            _require_file_sha(aux_model, str(authority["model_sha256"]), "outer_leaf_auxiliary_model_changed")
            _require(receipt.get("initial_shared_digest") == authority["final_shared_digest"], "outer_leaf_auxiliary_shared_mismatch")
        else:
            _require(auxiliary is None, "outer_target_only_received_auxiliary_state")
        if expected_map:
            _require(np.array_equal(payload["map_grid_cell_id"], np.asarray(map_arrays["cells"], dtype=str)), "outer_leaf_map_membership_mismatch")
            replayed_map = outer_ready.score_neural_model(model, masked["map"])
            _require(np.array_equal(replayed_map, payload["sensitivity_map_scores"]), "outer_leaf_map_prediction_tamper")
            _require(array_digest(replayed_map) == receipt.get("map", {}).get("prediction_digest"), "outer_leaf_map_digest_mismatch")
            _require(array_digest(payload["accepted_primary_map_scores"]) == receipt.get("accepted_primary_map", {}).get("prediction_digest"), "outer_leaf_primary_map_digest_mismatch")
            _require(original_map is not None and np.array_equal(original_map, payload["accepted_primary_map_scores"]), "outer_leaf_primary_map_replay_mismatch")
            _require(receipt.get("accepted_primary_map", {}).get("original_model_state_digest") == original_row["model_digest"], "outer_leaf_primary_model_binding_mismatch")
        else:
            _require(receipt.get("map") is None and receipt.get("accepted_primary_map") is None, "reduced_endpoint_map_prohibited")
        if task.target == THYLOGALE:
            _require(np.array_equal(original_held, payload["scores"]), "outer_leaf_thylogale_held_negative_control_mismatch")
            if expected_map:
                _require(np.array_equal(original_map, payload["sensitivity_map_scores"]), "outer_leaf_thylogale_map_negative_control_mismatch")
            _require(receipt.get("thylogale_negative_control", {}).get("status") == "exact", "outer_leaf_thylogale_negative_control_receipt_missing")
    return receipt


def _semantic_smoke_receipt(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    excluded = {
        "process_id", "wall_seconds", "peak_rss_bytes", "prediction_sha256",
        "receipt_digest", "model_receipt",
    }
    return {key: value for key, value in receipt.items() if key not in excluded}


def _smoke_destination(output: Path, task: InnerTask, repetition: int) -> Path:
    return output / "smoke/leaves" / f"{_task_digest(task, 'inner')}--repeat{repetition}"


def smoke_one(
    root: Path, output: Path, stage_root: Path, method: str, repetition: int,
) -> Mapping[str, Any]:
    _require(method in METHODS and repetition in (1, 2), "smoke_worker_scope_invalid")
    preparation = _load_preparation(root, output, stage_root)
    _manifest(root)  # all prepared inputs are intact before this subprocess fits
    _recovery_inventory(root, stage_root)
    task = InnerTask(SMOKE_TARGET, SMOKE_FOLD, SMOKE_ENDPOINT, method, SMOKE_SEED)
    destination = _smoke_destination(output, task, repetition)
    _require(not destination.exists(), "smoke_worker_destination_exists")
    attempt_id = f"{_task_digest(task, 'inner')}--repeat{repetition}"
    intent = output / "smoke/intents" / f"{attempt_id}.json"
    attempt = output / "smoke/attempts" / attempt_id
    _require(not intent.exists() and not attempt.exists(), "smoke_orphan_or_failed_intent")
    payload = {
        "schema_version": "tasmania-pseudoabsence-neural-smoke-intent-v2",
        "task": asdict(task), "task_digest": _task_digest(task, "inner"),
        "repetition": repetition, "physical_stages": ["discovery", "replay"],
        "created_unix_ns": time.time_ns(), "bindings": preparation["bindings"],
    }
    _write_json_exclusive(intent, payload)
    attempt.mkdir(parents=True, exist_ok=False)
    _write_json_exclusive(attempt / "intent.json", payload)
    try:
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            return _fit_inner_task(
                task=task, root=root, output=output, stage_root=stage_root,
                preparation=preparation, destination=destination, attempt=attempt,
                production_caps_receipt_digest=None, smoke=True,
            )
    except BaseException as exc:
        _write_json_idempotent(attempt / "failed.json", {
            "schema_version": "tasmania-pseudoabsence-neural-smoke-failure-v2",
            "task": asdict(task), "repetition": repetition,
            "error_type": type(exc).__name__, "error": str(exc),
        })
        raise


def _smoke_under_lock(
    root: Path = ROOT, output: Path = DEFAULT_OUTPUT, stage_root: Path = DEFAULT_STAGE_ROOT,
) -> dict[str, Any]:
    preparation = _load_preparation(root, output, stage_root)
    _manifest(root)  # repeat the whole-panel input gate before smoke fits
    _recovery_inventory(root, stage_root)
    all_receipts = []
    comparisons = []
    for method in METHODS:
        task = InnerTask(SMOKE_TARGET, SMOKE_FOLD, SMOKE_ENDPOINT, method, SMOKE_SEED)
        repeated = []
        for repetition in (1, 2):
            destination = _smoke_destination(output, task, repetition)
            if destination.exists():
                receipt = _validated_leaf(destination, task, "inner", root, stage_root, preparation, None, smoke=True)
            else:
                command = [
                    sys.executable, str(Path(__file__).resolve()), "smoke-one",
                    "--root", str(root), "--output", str(output), "--stage-root", str(stage_root),
                    "--smoke-method", method, "--smoke-repeat", str(repetition), "--execute",
                ]
                completed = subprocess.run(command, text=True, capture_output=True, check=False)
                _require(completed.returncode == 0, f"smoke_subprocess_failed:{method}:repeat{repetition}:{completed.stderr[-1000:]}")
                receipt = _validated_leaf(destination, task, "inner", root, stage_root, preparation, None, smoke=True)
            attempt_id = f"{_task_digest(task, 'inner')}--repeat{repetition}"
            intent_path = output / "smoke/intents" / f"{attempt_id}.json"
            attempt = output / "smoke/attempts" / attempt_id
            _require(
                intent_path.is_file() and attempt.is_dir()
                and (attempt / "intent.json").is_file()
                and (attempt / "running.json").is_file()
                and (attempt / "completed.json").is_file()
                and not (attempt / "failed.json").exists(),
                f"smoke_attempt_evidence_incomplete:{method}:repeat{repetition}",
            )
            intent = _read_json(intent_path)
            _require(
                intent.get("task") == asdict(task) and intent.get("repetition") == repetition
                and intent.get("physical_stages") == ["discovery", "replay"]
                and intent.get("bindings") == preparation["bindings"],
                f"smoke_attempt_identity_mismatch:{method}:repeat{repetition}",
            )
            running = _read_json(attempt / "running.json")
            completed = _read_json(attempt / "completed.json")
            _require(
                running.get("lane") == "inner" and running.get("task") == asdict(task)
                and running.get("fit_started") is True
                and running.get("physical_stages_entered") == ["discovery", "replay"]
                and running.get("physical_fits_started") == 2
                and receipt.get("physical_stages_completed") == ["discovery", "replay"]
                and receipt.get("physical_fits") == 2
                and completed.get("receipt_digest") == receipt.get("receipt_digest"),
                f"smoke_physical_stage_evidence_mismatch:{method}:repeat{repetition}",
            )
            repeated.append(receipt); all_receipts.append(receipt)
        _require(repeated[0]["process_id"] != repeated[1]["process_id"], f"smoke_process_not_clean:{method}")
        left, right = _semantic_smoke_receipt(repeated[0]), _semantic_smoke_receipt(repeated[1])
        _require(left == right, f"smoke_semantic_repeat_mismatch:{method}")
        comparisons.append({"method": method, "semantic_digest": digest_value(left)})
    _require(sum(int(row["physical_fits"]) for row in all_receipts) == 8, "smoke_physical_fit_count_mismatch")
    observed = {
        "maximum_leaf_wall_seconds": max(float(row["wall_seconds"]) for row in all_receipts),
        "maximum_worker_peak_rss_bytes": max(int(row["peak_rss_bytes"]) for row in all_receipts),
        "private_storage_bytes": sum(path.stat().st_size for path in (output / "smoke").rglob("*") if path.is_file()),
    }
    receipt = {
        "schema_version": "tasmania-pseudoabsence-neural-smoke-v2",
        "success": True, "non_promotable": True,
        "preparation_receipt_digest": preparation["receipt_digest"],
        "source_sha256": _source_sha(), "logical_tasks": 4, "physical_fits": 8,
        "target": SMOKE_TARGET, "held_fold": SMOKE_FOLD, "endpoint": SMOKE_ENDPOINT,
        "seed": SMOKE_SEED, "methods": list(METHODS), "repeats": 2,
        "comparisons": comparisons, "observed": observed,
        "production_caps_assigned": False,
        "outer_held_response_labels_read": 0,
        "bindings": preparation["bindings"],
    }
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json_idempotent(output / "smoke-qualification.json", receipt)
    return receipt


def smoke(
    root: Path = ROOT, output: Path = DEFAULT_OUTPUT, stage_root: Path = DEFAULT_STAGE_ROOT,
    *, execute: bool = False,
) -> dict[str, Any]:
    _require(execute, "smoke_is_fit_gated_pass_execute_after_independent_review")
    with _orchestration_lock(output, "smoke"):
        return _smoke_under_lock(root, output, stage_root)


def _load_smoke(output: Path, preparation: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _read_json(output / "smoke-qualification.json")
    _validated_self_digest(receipt, "receipt_digest", "smoke_receipt_invalid")
    _require(
        receipt.get("success") is True and receipt.get("non_promotable") is True
        and receipt.get("physical_fits") == 8 and receipt.get("logical_tasks") == 4
        and receipt.get("source_sha256") == _source_sha()
        and receipt.get("preparation_receipt_digest") == preparation.get("receipt_digest")
        and receipt.get("bindings") == preparation.get("bindings"),
        "smoke_qualification_binding_mismatch",
    )
    return receipt


def _load_production_caps(output: Path, preparation: Mapping[str, Any], smoke_receipt: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _read_json(output / "production-caps.json")
    _validated_self_digest(receipt, "receipt_digest", "production_caps_digest_invalid")
    caps = receipt.get("caps")
    observed = smoke_receipt.get("observed", {})
    _require(
        receipt.get("schema_version") == "tasmania-pseudoabsence-neural-production-caps-v2"
        and receipt.get("status") == "approved"
        and receipt.get("preparation_receipt_digest") == preparation.get("receipt_digest")
        and receipt.get("smoke_receipt_digest") == smoke_receipt.get("receipt_digest")
        and receipt.get("source_sha256") == _source_sha()
        and isinstance(caps, Mapping),
        "production_caps_binding_invalid",
    )
    _require(caps.get("max_workers") == 3 and caps.get("threads_per_worker") == 1 and caps.get("maximum_in_flight") == 3, "production_concurrency_cap_invalid")
    for name in ("max_leaf_wall_seconds", "max_stage_wall_seconds", "max_worker_peak_rss_bytes", "max_private_storage_bytes"):
        _require(type(caps.get(name)) in (int, float) and caps[name] > 0, f"production_cap_invalid:{name}")
    _require(caps["max_leaf_wall_seconds"] >= observed.get("maximum_leaf_wall_seconds", 0), "production_wall_cap_below_smoke")
    _require(caps["max_worker_peak_rss_bytes"] >= observed.get("maximum_worker_peak_rss_bytes", 0), "production_rss_cap_below_smoke")
    _require(caps["max_private_storage_bytes"] >= observed.get("private_storage_bytes", 0), "production_storage_cap_below_smoke")
    return receipt


def _private_bytes(output: Path) -> int:
    return sum(path.stat().st_size for path in output.rglob("*") if path.is_file())


@contextmanager
def _orchestration_lock(output: Path, stage: str) -> Iterator[None]:
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "orchestration.lock"
    payload = _canonical({"stage": stage, "pid": os.getpid(), "created_unix_ns": time.time_ns()}) + b"\n"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise NeuralSensitivityError("exclusive_orchestration_lock_exists") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    try:
        yield
    finally:
        try:
            if lock.read_bytes() == payload:
                lock.unlink()
        except FileNotFoundError:
            pass


def _check_resource_receipt(receipt: Mapping[str, Any], caps: Mapping[str, Any]) -> None:
    _require(float(receipt.get("wall_seconds", float("inf"))) <= float(caps["max_leaf_wall_seconds"]), "leaf_wall_cap_exceeded")
    _require(int(receipt.get("peak_rss_bytes", 2**63 - 1)) <= int(caps["max_worker_peak_rss_bytes"]), "worker_rss_cap_exceeded")


def _validate_completed_attempt(
    output: Path, intent_path: Path, attempt: Path, destination: Path, lane: str,
    task: InnerTask | OuterTask, receipt: Mapping[str, Any], preparation: Mapping[str, Any],
) -> None:
    _require(
        intent_path.is_file() and attempt.is_dir()
        and (attempt / "intent.json").is_file()
        and (attempt / "running.json").is_file()
        and (attempt / "completed.json").is_file()
        and not (attempt / "failed.json").exists()
        and not (attempt / "cancelled.json").exists()
        and not (attempt / "terminated.json").exists(),
        f"{lane}_completed_leaf_attempt_evidence_missing",
    )
    intent = _read_json(intent_path)
    expected_stages = ["discovery", "replay"] if lane == "inner" else ["exact_fit"]
    _require(
        _read_json(attempt / "intent.json") == intent
        and intent.get("lane") == lane and intent.get("task") == asdict(task)
        and intent.get("task_digest") == _task_digest(task, lane)
        and intent.get("destination") == str(destination.relative_to(output))
        and intent.get("physical_stages") == expected_stages
        and intent.get("bindings") == preparation.get("bindings"),
        f"{lane}_completed_leaf_intent_mismatch",
    )
    running = _read_json(attempt / "running.json")
    _require(
        running.get("schema_version") == "tasmania-pseudoabsence-neural-fit-running-v2"
        and running.get("lane") == lane and running.get("task") == asdict(task)
        and running.get("task_digest") == _task_digest(task, lane)
        and running.get("fit_started") is True
        and running.get("physical_stages_entered") == expected_stages
        and running.get("physical_fits_started") == len(expected_stages)
        and receipt.get("physical_stages_completed") == expected_stages
        and receipt.get("physical_fits") == len(expected_stages),
        f"{lane}_completed_leaf_physical_stage_evidence_mismatch",
    )
    completed = _read_json(attempt / "completed.json")
    _require(
        completed.get("schema_version") == "tasmania-pseudoabsence-neural-fit-complete-v2"
        and completed.get("task_digest") == receipt.get("task_digest")
        and completed.get("receipt_digest") == receipt.get("receipt_digest"),
        f"{lane}_completed_leaf_receipt_evidence_mismatch",
    )


def _stage_existing_and_missing(
    tasks: Sequence[InnerTask | OuterTask], lane: str, root: Path, output: Path,
    stage_root: Path, preparation: Mapping[str, Any], caps_receipt: Mapping[str, Any],
) -> tuple[list[InnerTask | OuterTask], int]:
    missing: list[InnerTask | OuterTask] = []
    reused = 0
    for task in tasks:
        digest = _task_digest(task, lane)
        destination = output / lane / "leaves" / digest
        intent = output / lane / "intents" / f"{digest}.json"
        attempt = output / lane / "attempts" / digest
        if destination.exists():
            receipt = _validated_leaf(destination, task, lane, root, stage_root, preparation, caps_receipt["receipt_digest"])
            _check_resource_receipt(receipt, caps_receipt["caps"])
            _validate_completed_attempt(output, intent, attempt, destination, lane, task, receipt, preparation)
            reused += 1
        else:
            _require(not intent.exists() and not attempt.exists(), f"{lane}_failed_or_orphan_attempt_refuses_retry:{digest}")
            missing.append(task)
    return missing, reused


def _inner_epoch_policy(
    inner_closure: Mapping[str, Any],
) -> dict[tuple[str, str, str, int], tuple[list[int], int]]:
    _require(
        inner_closure.get("schema_version") == "tasmania-pseudoabsence-neural-inner-closure-v2"
        and inner_closure.get("success") is True,
        "inner_closure_epoch_policy_invalid",
    )
    records = inner_closure.get("records")
    _require(isinstance(records, list) and len(records) == 2800, "inner_epoch_record_inventory_incomplete")
    grouped: dict[tuple[str, str, str, int], dict[str, int]] = {}
    for record in records:
        task = record.get("task")
        _require(isinstance(task, Mapping), "inner_epoch_task_missing")
        key = (str(task.get("target")), str(task.get("endpoint")), str(task.get("method")), int(task.get("seed")))
        fold = str(task.get("held_fold"))
        _require(
            key[0] in SPECIES and key[1] in ENDPOINTS and key[2] in METHODS
            and key[3] in SEEDS and fold in FOLDS,
            "inner_epoch_task_identity_drift",
        )
        by_fold = grouped.setdefault(key, {})
        _require(fold not in by_fold, "inner_epoch_fold_duplicate")
        by_fold[fold] = int(record.get("selected_epoch"))
    result: dict[tuple[str, str, str, int], tuple[list[int], int]] = {}
    for key, by_fold in grouped.items():
        _require(set(by_fold) == set(FOLDS), "inner_epoch_five_fold_incomplete")
        values = [by_fold[fold] for fold in FOLDS]
        result[key] = (values, lower_median(values))
    _require(len(result) == 560, "outer_epoch_policy_cross_product_incomplete")
    return result


def _worker_inner(kwargs: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            return _fit_inner_task(**dict(kwargs))
    except BaseException as exc:
        _record_attempt_failure("inner", kwargs["task"], Path(kwargs["attempt"]), exc)
        raise


def _worker_outer(kwargs: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            return _fit_outer_task(**dict(kwargs))
    except BaseException as exc:
        _record_attempt_failure("outer", kwargs["task"], Path(kwargs["attempt"]), exc)
        raise


def _pool_processes(pool: ProcessPoolExecutor) -> list[Any]:
    processes = getattr(pool, "_processes", None)
    _require(isinstance(processes, dict), "worker_process_inventory_unavailable")
    return [process for process in processes.values() if process is not None]


def _probe_host_rss_monitor() -> int:
    completed = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(os.getpid())],
        text=True, capture_output=True, check=False,
    )
    value = completed.stdout.strip()
    _require(completed.returncode == 0 and value.isdigit(), "host_rss_monitor_unavailable")
    return int(value) * 1024


def _pool_rss_bytes(pool: ProcessPoolExecutor) -> dict[int, int]:
    result: dict[int, int] = {}
    for process in _pool_processes(pool):
        pid = process.pid
        if pid is None or not process.is_alive():
            continue
        completed = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            text=True, capture_output=True, check=False,
        )
        if completed.returncode != 0 and not process.is_alive():
            continue
        _require(completed.returncode == 0, f"worker_rss_probe_failed:{pid}")
        text_value = completed.stdout.strip()
        if not text_value and not process.is_alive():
            continue
        _require(text_value.isdigit(), f"worker_rss_probe_invalid:{pid}")
        result[int(pid)] = int(text_value) * 1024
    return result


def _terminate_pool_workers(pool: ProcessPoolExecutor) -> list[int]:
    processes = _pool_processes(pool)
    terminated = [int(process.pid) for process in processes if process.pid is not None and process.is_alive()]
    for process in processes:
        if process.is_alive():
            process.terminate()
    deadline = time.monotonic() + 3.0
    for process in processes:
        process.join(timeout=max(0.0, deadline - time.monotonic()))
    for process in processes:
        if process.is_alive():
            process.kill()
    for process in processes:
        process.join(timeout=1.0)
    _require(not any(process.is_alive() for process in processes), "worker_hard_termination_failed")
    return terminated


def _run_bounded_pool(
    *, tasks: Sequence[InnerTask | OuterTask], lane: str, root: Path, output: Path,
    stage_root: Path, preparation: Mapping[str, Any], caps_receipt: Mapping[str, Any],
    epoch_policy: Mapping[tuple[str, str, str, int], tuple[list[int], int]] | None = None,
) -> int:
    caps = caps_receipt["caps"]
    _probe_host_rss_monitor()  # prove the launch scope can monitor before workers exist
    pending = iter(tasks)
    submitted: dict[Any, tuple[InnerTask | OuterTask, Path, float]] = {}
    completed = 0
    failure: tuple[InnerTask | OuterTask, Path, BaseException] | None = None
    dispatcher_error: BaseException | None = None
    started = time.monotonic()
    context = mp.get_context("spawn")
    pool = ProcessPoolExecutor(max_workers=3, mp_context=context)

    def submit_one(task: InnerTask | OuterTask) -> None:
        _require(len(submitted) < 3, "maximum_in_flight_exceeded")
        _require(_private_bytes(output) <= int(caps["max_private_storage_bytes"]), "private_storage_cap_exceeded")
        destination = output / lane / "leaves" / _task_digest(task, lane)
        attempt = _begin_fit_attempt(
            root, output, lane, task, destination,
            ("discovery", "replay") if lane == "inner" else ("exact_fit",), preparation,
        )
        common = {
            "task": task, "root": root, "output": output, "stage_root": stage_root,
            "preparation": preparation, "destination": destination, "attempt": attempt,
            "production_caps_receipt_digest": caps_receipt["receipt_digest"],
        }
        if lane == "outer":
            assert isinstance(task, OuterTask) and epoch_policy is not None
            folds, epoch = epoch_policy[(task.target, task.endpoint, task.method, task.seed)]
            common.update({"epochs": epoch, "inner_epochs": folds})
            future = pool.submit(_worker_outer, common)
        else:
            common["smoke"] = False
            future = pool.submit(_worker_inner, common)
        submitted[future] = (task, attempt, time.monotonic())

    try:
        for _ in range(min(3, len(tasks))):
            task = next(pending, None)
            if task is None:
                break
            submit_one(task)
        while submitted:
            now = time.monotonic()
            if now - started > float(caps["max_stage_wall_seconds"]):
                task, attempt, _submitted_at = next(iter(submitted.values()))
                failure = (task, attempt, NeuralSensitivityError("stage_wall_cap_exceeded"))
                break
            over_wall = next(
                (
                    (task, attempt) for future, (task, attempt, submitted_at) in submitted.items()
                    if not future.done() and now - submitted_at > float(caps["max_leaf_wall_seconds"])
                ),
                None,
            )
            if over_wall is not None:
                failure = (*over_wall, NeuralSensitivityError("leaf_wall_cap_exceeded_during_fit"))
                break
            worker_rss = _pool_rss_bytes(pool)
            if worker_rss and max(worker_rss.values()) > int(caps["max_worker_peak_rss_bytes"]):
                task, attempt, _submitted_at = next(iter(submitted.values()))
                failure = (task, attempt, NeuralSensitivityError("worker_rss_cap_exceeded_during_fit"))
                break
            if _private_bytes(output) > int(caps["max_private_storage_bytes"]):
                task, attempt, _submitted_at = next(iter(submitted.values()))
                failure = (task, attempt, NeuralSensitivityError("private_storage_cap_exceeded_during_fit"))
                break
            done, _ = wait(tuple(submitted), timeout=1.0, return_when=FIRST_COMPLETED)
            if not done:
                continue
            successes = 0
            for future in done:
                task, attempt, _submitted_at = submitted.pop(future)
                try:
                    receipt = future.result()
                    _check_resource_receipt(receipt, caps)
                    _require(_private_bytes(output) <= int(caps["max_private_storage_bytes"]), "private_storage_cap_exceeded")
                except BaseException as exc:
                    if failure is None:
                        failure = (task, attempt, exc)
                else:
                    completed += 1
                    successes += 1
            if failure is not None:
                break
            for _ in range(successes):
                task = next(pending, None)
                if task is None:
                    break
                submit_one(task)
    except BaseException as exc:
        dispatcher_error = exc
    finally:
        hard_stop = failure is not None or dispatcher_error is not None
        if hard_stop:
            for future in submitted:
                try:
                    future.cancel()
                except BaseException:
                    pass
            try:
                terminated_pids = _terminate_pool_workers(pool)
            except BaseException as exc:
                terminated_pids = []
                if dispatcher_error is None:
                    dispatcher_error = exc
            for future, (task, attempt, _submitted_at) in submitted.items():
                try:
                    if future.cancelled():
                        _write_json_idempotent(attempt / "cancelled.json", {
                            "schema_version": "tasmania-pseudoabsence-neural-fit-cancelled-v2",
                            "lane": lane, "task": asdict(task),
                            "task_digest": _task_digest(task, lane),
                            "reason": "cancelled_after_peer_or_dispatcher_failure",
                        })
                    else:
                        _write_json_idempotent(attempt / "terminated.json", {
                            "schema_version": "tasmania-pseudoabsence-neural-fit-terminated-v2",
                            "lane": lane, "task": asdict(task),
                            "task_digest": _task_digest(task, lane),
                            "reason": "hard_stop_after_resource_peer_or_dispatcher_failure",
                            "terminated_worker_pids": terminated_pids,
                        })
                        if future.done():
                            try:
                                future.result()
                            except BaseException as exc:
                                _record_attempt_failure(lane, task, attempt, exc)
                except BaseException:
                    pass
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except BaseException:
                pass
        else:
            pool.shutdown(wait=True, cancel_futures=True)
    if failure is not None:
        task, attempt, exc = failure
        _mark_fit_failure(output, lane, task, attempt, exc)
        raise NeuralSensitivityError(f"{lane}_stopped_after_first_failure:{exc}") from exc
    if dispatcher_error is not None:
        _mark_dispatcher_failure(output, lane, dispatcher_error)
        raise NeuralSensitivityError(f"{lane}_dispatcher_hard_stopped:{dispatcher_error}") from dispatcher_error
    return completed


def _lane_artifact_inventory_complete(
    output: Path, lane: str, tasks: Sequence[InnerTask | OuterTask],
) -> bool:
    expected = {_task_digest(task, lane) for task in tasks}
    layouts = (
        (output / lane / "leaves", expected, "directory"),
        (output / lane / "attempts", expected, "directory"),
        (output / lane / "intents", {f"{value}.json" for value in expected}, "file"),
    )
    complete = True
    for directory, expected_names, kind in layouts:
        if not directory.is_dir() or directory.is_symlink():
            complete = False
            continue
        entries = list(directory.iterdir())
        actual_names = {entry.name for entry in entries}
        valid_types = all(
            entry.is_dir() and not entry.is_symlink()
            if kind == "directory"
            else entry.is_file() and not entry.is_symlink()
            for entry in entries
        )
        _require(valid_types and actual_names.issubset(expected_names), f"{lane}_{kind}_inventory_has_extra_or_invalid_entries")
        if actual_names != expected_names:
            complete = False
    return complete


def _has_exact_negative_control(receipt: Mapping[str, Any]) -> bool:
    value = receipt.get("thylogale_negative_control") or {}
    return isinstance(value, Mapping) and value.get("status") == "exact"


def _close_lane(
    lane: str, tasks: Sequence[InnerTask | OuterTask], expected_fits: int,
    root: Path, output: Path, stage_root: Path, preparation: Mapping[str, Any],
    caps_digest: str,
) -> Mapping[str, Any] | None:
    _require(not (output / "ABORT.json").exists(), "neural_panel_aborted")
    if not _lane_artifact_inventory_complete(output, lane, tasks):
        return None
    records = []
    pair_rows: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = {}
    negative = 0
    maps = 0
    primary_maps = 0
    for task in tasks:
        leaf = output / lane / "leaves" / _task_digest(task, lane)
        if not leaf.is_dir():
            return None
        receipt = _validated_leaf(leaf, task, lane, root, stage_root, preparation, caps_digest)
        task_digest = _task_digest(task, lane)
        _validate_completed_attempt(
            output, output / lane / "intents" / f"{task_digest}.json",
            output / lane / "attempts" / task_digest, leaf, lane, task, receipt, preparation,
        )
        if _has_exact_negative_control(receipt):
            negative += 1
        if receipt.get("map") is not None:
            maps += 1
        if receipt.get("accepted_primary_map") is not None:
            primary_maps += 1
        record = {
            "task": receipt["task"], "task_digest": receipt["task_digest"],
            "receipt_digest": receipt["receipt_digest"],
            "model_sha256": receipt["model_receipt"]["model_sha256"],
            "model_state_digest": receipt["model_digest"],
            "prediction_sha256": receipt["prediction_sha256"],
            "prediction_digest": receipt["prediction_digest"],
            "support_mask_digest": receipt["support_mask_digest"],
            "physical_fits": receipt["physical_fits"],
        }
        if lane == "inner":
            record["selected_epoch"] = receipt["selected_epoch"]
        else:
            record["exact_epochs"] = receipt["exact_epochs"]
        records.append(record)
        if lane == "inner":
            assert isinstance(task, InnerTask)
            key = (task.target, task.held_fold, task.endpoint, task.seed)
        else:
            assert isinstance(task, OuterTask)
            key = (task.target, task.endpoint, task.seed)
        pair_rows.setdefault(key, {})[task.method] = receipt
    _require(sum(int(row["physical_fits"]) for row in records) == expected_fits, f"{lane}_physical_fit_inventory_mismatch")
    _require(all(set(pair) == set(METHODS) for pair in pair_rows.values()), f"{lane}_paired_method_inventory_incomplete")
    for key, pair in pair_rows.items():
        target_only = pair["target_only_resmlp"]
        multihead = pair["multihead_full_finetune"]
        _require(target_only["fit_seed"] == multihead["fit_seed"], f"{lane}_paired_fit_seed_mismatch:{key}")
        _require(target_only["initial_head_digest"] == multihead["initial_head_digest"], f"{lane}_paired_head_initialization_mismatch:{key}")
        auxiliary = multihead.get("auxiliary")
        _require(isinstance(auxiliary, Mapping), f"{lane}_multihead_auxiliary_missing:{key}")
        if lane == "inner":
            _require(multihead["initial_shared_digest"] == auxiliary["final_shared_digest"] and multihead.get("auxiliary_unchanged") is True, f"inner_multihead_auxiliary_transfer_mismatch:{key}")
        else:
            _require(multihead["initial_shared_digest"] == auxiliary["artifact_final_shared_digest"] and auxiliary.get("unchanged_after_fit") is True, f"outer_multihead_auxiliary_transfer_mismatch:{key}")
    expected_negative = 350 if lane == "inner" else 70
    _require(negative == expected_negative, f"{lane}_thylogale_negative_control_incomplete")
    if lane == "outer":
        _require(maps == primary_maps == 80, "outer_full_endpoint_map_inventory_mismatch")
    closure = {
        "schema_version": f"tasmania-pseudoabsence-neural-{lane}-closure-v2",
        "success": True, "lane": lane, "logical_tasks": len(tasks),
        "physical_fits": expected_fits, "records": records,
        "inventory_digest": digest_value(records),
        "paired_initialization_checks": len(pair_rows),
        "thylogale_exact_negative_controls": negative,
        "sensitivity_map_seed_leaves": maps,
        "accepted_primary_map_seed_leaves": primary_maps,
        "production_caps_receipt_digest": caps_digest,
        "outer_held_response_labels_read": 0,
        "bindings": preparation["bindings"],
    }
    closure["receipt_digest"] = digest_value(closure)
    _write_json_idempotent(output / f"{lane}-closure.json", closure)
    return closure


def run_inner(
    root: Path = ROOT, output: Path = DEFAULT_OUTPUT, stage_root: Path = DEFAULT_STAGE_ROOT,
    *, execute: bool = False, workers: int = 3,
) -> Mapping[str, Any]:
    _require(execute, "inner_production_is_fit_gated")
    _require(workers == 3, "inner_requires_exactly_three_workers")
    preparation = _load_preparation(root, output, stage_root)
    _manifest(root)  # whole-panel input gate before inner production fits
    _recovery_inventory(root, stage_root)
    smoke_receipt = _load_smoke(output, preparation)
    caps_receipt = _load_production_caps(output, preparation, smoke_receipt)
    tasks = build_inner_inventory()
    with _orchestration_lock(output, "inner"):
        _lane_artifact_inventory_complete(output, "inner", tasks)  # reject extras before any submission
        missing, reused = _stage_existing_and_missing(tasks, "inner", root, output, stage_root, preparation, caps_receipt)
        new = _run_bounded_pool(
            tasks=missing, lane="inner", root=root, output=output, stage_root=stage_root,
            preparation=preparation, caps_receipt=caps_receipt,
        ) if missing else 0
        closure = _close_lane("inner", tasks, 5600, root, output, stage_root, preparation, caps_receipt["receipt_digest"])
    _require(closure is not None, "inner_closure_incomplete")
    return {"success": True, "lane": "inner", "new_tasks": new, "reused_tasks": reused, "closure_receipt_digest": closure["receipt_digest"]}


def run_outer(
    root: Path = ROOT, output: Path = DEFAULT_OUTPUT, stage_root: Path = DEFAULT_STAGE_ROOT,
    *, execute: bool = False, workers: int = 3,
) -> Mapping[str, Any]:
    _require(execute, "outer_production_is_fit_gated")
    _require(workers == 3, "outer_requires_exactly_three_workers")
    preparation = _load_preparation(root, output, stage_root)
    _manifest(root)  # repeat the whole-panel input gate before outer production fits
    _recovery_inventory(root, stage_root)
    _validate_outer_package_bindings(preparation, _goal037_package_index(root))
    smoke_receipt = _load_smoke(output, preparation)
    caps_receipt = _load_production_caps(output, preparation, smoke_receipt)
    inner_tasks = build_inner_inventory()
    inner_closure = _close_lane("inner", inner_tasks, 5600, root, output, stage_root, preparation, caps_receipt["receipt_digest"])
    _require(inner_closure is not None, "inner_closure_required_before_outer")
    policy = _inner_epoch_policy(inner_closure)
    tasks = build_outer_inventory()
    with _orchestration_lock(output, "outer"):
        _lane_artifact_inventory_complete(output, "outer", tasks)  # reject extras before any submission
        missing, reused = _stage_existing_and_missing(tasks, "outer", root, output, stage_root, preparation, caps_receipt)
        new = _run_bounded_pool(
            tasks=missing, lane="outer", root=root, output=output, stage_root=stage_root,
            preparation=preparation, caps_receipt=caps_receipt, epoch_policy=policy,
        ) if missing else 0
        closure = _close_lane("outer", tasks, 560, root, output, stage_root, preparation, caps_receipt["receipt_digest"])
    _require(closure is not None, "outer_closure_incomplete")
    return {"success": True, "lane": "outer", "new_tasks": new, "reused_tasks": reused, "closure_receipt_digest": closure["receipt_digest"]}


def _close_under_lock(
    root: Path = ROOT, output: Path = DEFAULT_OUTPUT, stage_root: Path = DEFAULT_STAGE_ROOT,
) -> Mapping[str, Any]:
    preparation = _load_preparation(root, output, stage_root)
    _recovery_inventory(root, stage_root)
    _validate_outer_package_bindings(preparation, _goal037_package_index(root))
    smoke_receipt = _load_smoke(output, preparation)
    caps_receipt = _load_production_caps(output, preparation, smoke_receipt)
    inner = _close_lane("inner", build_inner_inventory(), 5600, root, output, stage_root, preparation, caps_receipt["receipt_digest"])
    _require(inner is not None, "inner_closure_required")
    outer = _close_lane("outer", build_outer_inventory(), 560, root, output, stage_root, preparation, caps_receipt["receipt_digest"])
    _require(outer is not None, "outer_closure_required")
    payload = {
        "schema_version": "tasmania-pseudoabsence-neural-complete-closure-v2",
        "success": True, "logical_tasks": 3360, "physical_fits": 6160,
        "inner_closure_receipt_digest": inner["receipt_digest"],
        "outer_closure_receipt_digest": outer["receipt_digest"],
        "inner_leaves": inner["logical_tasks"], "outer_leaves": outer["logical_tasks"],
        "thylogale_exact_negative_controls": inner["thylogale_exact_negative_controls"] + outer["thylogale_exact_negative_controls"],
        "sensitivity_map_seed_leaves": outer["sensitivity_map_seed_leaves"],
        "accepted_primary_map_seed_leaves": outer["accepted_primary_map_seed_leaves"],
        "production_caps_receipt_digest": caps_receipt["receipt_digest"],
        "outer_held_response_labels_read": 0,
        "bindings": preparation["bindings"],
    }
    payload["receipt_digest"] = digest_value(payload)
    _write_json_idempotent(output / "closure.json", payload)
    return payload


def close(
    root: Path = ROOT, output: Path = DEFAULT_OUTPUT, stage_root: Path = DEFAULT_STAGE_ROOT,
) -> Mapping[str, Any]:
    with _orchestration_lock(output, "close"):
        return _close_under_lock(root, output, stage_root)


def validate(root: Path = ROOT) -> Mapping[str, Any]:
    inputs = load_inputs(root)
    counts = inventory_counts()
    _require(
        counts == {
            "inner_logical_tasks": 2800, "inner_physical_fits": 5600,
            "outer_logical_tasks": 560, "outer_physical_fits": 560,
            "total_logical_tasks": 3360, "total_physical_fits": 6160,
        },
        "task_inventory_arithmetic_drift",
    )
    return {
        "status": "pass", "manifest_digest": inputs["manifest"]["digest"],
        "counts": counts, "inner_cases": len(inputs["inner"]), "outer_cases": len(inputs["outer"]),
        "map_cells": len(inputs["map"][0]["cells"]), "outer_held_response_labels_read": 0,
        "fits": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "prepare", "smoke", "smoke-one", "run-inner", "run-outer", "close"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stage-root", type=Path, default=DEFAULT_STAGE_ROOT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--smoke-method", choices=METHODS)
    parser.add_argument("--smoke-repeat", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root, output, stage_root = args.root.resolve(), args.output.resolve(), args.stage_root.resolve()
    try:
        if args.command == "validate":
            result = validate(root)
        elif args.command == "prepare":
            result = prepare(root, output, stage_root)
        elif args.command == "smoke":
            result = smoke(root, output, stage_root, execute=args.execute)
        elif args.command == "smoke-one":
            _require(args.execute, "smoke_worker_requires_execute")
            result = smoke_one(root, output, stage_root, str(args.smoke_method), int(args.smoke_repeat))
        elif args.command == "run-inner":
            result = run_inner(root, output, stage_root, execute=args.execute, workers=args.workers)
        elif args.command == "run-outer":
            result = run_outer(root, output, stage_root, execute=args.execute, workers=args.workers)
        else:
            result = close(root, output, stage_root)
    except NeuralSensitivityError as exc:
        print(_canonical({"status": "refused", "error": str(exc)}).decode("utf-8"))
        return 2
    print(_canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ENDPOINTS", "FOLDS", "InnerTask", "METHODS", "NeuralSensitivityError",
    "OuterTask", "SEEDS", "SLUGS", "SPECIES", "build_inner_inventory",
    "build_outer_inventory", "close", "inventory_counts", "lower_median",
    "prepare", "run_inner", "run_outer", "smoke", "validate",
    "validate_epoch_completeness", "validate_inner_arrays", "validate_outer_arrays",
]
