"""Actual-host numerical and resource qualification for Goal052 outer fits.

Qualification and profiling are engineering gates.  They use retained or
synthetic rows only, write immutable receipts, and never import outer response
memberships.  Production callers consume the final receipt through
``require_qualification``.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import hashlib
import importlib
import json
import multiprocessing
import os
import gc
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

import numpy as np
import torch
import pandas as pd

from dsdm_phase1 import goal051_seawfb_conventional as baseline
from dsdm_phase1 import goal052_seawfb_dsdm as native
from dsdm_phase1.goal052_outer_artifacts import (
    load_plan,
    source_hashes,
    write_once,
)
from dsdm_phase1.goal052_outer_data import (
    FULL_FOLD,
    RetainedFullStore,
    auxiliary_full_data,
    prediction_batch,
    target_full_data,
)
from dsdm_phase1.goal050_seawfb_foundation import CATEGORICAL, CONTINUOUS
from dsdm_phase1.goal052_outer_training import fit_pretraining_fixed, fit_target_fixed
from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, build_adapter, load_fitted_model
from dsdm_phase1.modeling_contract import FeatureBatch, RowKey, canonical_json
from dsdm_phase1.seawfb_dsdm_data import IndexedRows
from dsdm_phase1.seawfb_dsdm_training import fit_pretraining_lifecycle, fit_target_lifecycle
from dsdm_phase1.seawfb_modeling import (
    fit_q_linear,
    q_parameter_digest,
    require,
    stable_seed,
)


SCHEMA_VERSION = "goal052-outer-runtime-v1"
CANARY_STATUS = "goal052_outer_canary_valid"
PROFILE_STATUS = "goal052_outer_profile_valid"
QUALIFIED_STATUS = "outer_runtime_qualified"
CANARY_REPEATS = (0, 1)
CANARY_HEADS = tuple(f"head_{index:02d}" for index in range(20))
CANARY_ROWS = 256
CANARY_SEED = 52052


class _CanaryQStore(RetainedFullStore):
    """Tiny retained substrate used to exercise the native q fitter."""

    def __init__(self, seed: int) -> None:
        rng = np.random.default_rng(stable_seed("goal052-outer-q-canary", seed))
        n = CANARY_ROWS
        self.cell_ids = np.asarray([f"q-cell-{index:04d}" for index in range(n)])
        self.folds = np.asarray(np.arange(n) % 5, dtype=np.int8)
        self.richness = np.full(n, 10, dtype=np.int64)
        self.presence_indices = {
            "focal_a": np.asarray([0, 1]),
            "focal_b": np.asarray([2, 3]),
        }
        heads: dict[str, np.ndarray] = {}
        for index in range(20):
            name = f"q-head-{index:02d}"
            heads[name] = np.flatnonzero((np.arange(n) + index) % (3 + index % 4) == 0)
            self.presence_indices[name] = heads[name]
        self.crossfit = {
            "focal_blocks": {"focal_a": 0, "focal_b": 0},
            "auxiliary_sets": {"0": {"20": list(heads), "80": list(heads), "full": list(heads)}},
        }
        self._response_cache = {}
        frame = {name: rng.normal(size=n) for name in CONTINUOUS}
        frame.update({name: np.asarray(["known"] * n, dtype=object) for name in CATEGORICAL})
        self.cells = pd.DataFrame(frame)
        self.transforms = {
            "transforms": {
                "retained_full": {
                    "continuous": {name: {"mean": 0.0, "population_sd": 1.0} for name in CONTINUOUS},
                    "categorical": {
                        "nvis_mvg": ["__MISSING__", "__UNSEEN__", "known", *[f"n{i}" for i in range(29)]],
                        "soil_order": ["__MISSING__", "__UNSEEN__", "known", *[f"s{i}" for i in range(13)]],
                        "alum_secondary": ["__MISSING__", "__UNSEEN__", "known", *[f"a{i}" for i in range(31)]],
                    },
                }
            }
        }


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Darwin reports bytes; Linux reports KiB.
    return value if platform.system() == "Darwin" else value * 1024


def _available_resources() -> dict[str, int | None]:
    cpus = os.cpu_count() or 1
    available: int | None = None
    if platform.system() == "Darwin":
        try:
            page = int(subprocess.check_output(["sysctl", "-n", "vm.stats.vm.page_size"], text=True).strip())
            stats = subprocess.check_output(["vm_stat"], text=True)
            pages = 0
            for line in stats.splitlines():
                if any(token in line for token in ("Pages free", "Pages inactive", "Pages speculative")):
                    pages += int(line.split(":", 1)[1].strip().rstrip("."))
            available = pages * page
        except (OSError, ValueError, subprocess.SubprocessError):
            available = None
    elif Path("/proc/meminfo").is_file():
        try:
            values = {
                line.split(":", 1)[0]: int(line.split()[1]) * 1024
                for line in Path("/proc/meminfo").read_text().splitlines()
                if ":" in line
            }
            available = values.get("MemAvailable")
        except (OSError, ValueError):
            available = None
    return {"available_cpus": int(cpus), "available_ram_bytes": available}


def _runtime_versions(device: str) -> dict[str, Any]:
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    thread_env = {
        name: os.environ.get(name)
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    }
    threadpools: list[dict[str, Any]] = []
    try:
        from threadpoolctl import threadpool_info

        for item in threadpool_info():
            threadpools.append({
                key: item.get(key)
                for key in ("user_api", "internal_api", "num_threads", "prefix")
                if key in item
            })
    except Exception:
        threadpools = []
    versions: dict[str, Any] = {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "scipy": importlib.import_module("scipy").__version__,
        "sklearn": importlib.import_module("sklearn").__version__,
        "torch_cpu_threads": int(torch.get_num_threads()),
        "torch_deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "device": device,
        "torch_cuda_available": bool(torch.cuda.is_available()),
        "torch_cuda_version": torch.version.cuda,
        "thread_env": thread_env,
        "threadpools": threadpools,
    }
    return versions


def _runtime_context(device: str) -> dict[str, Any]:
    require(device == "cpu", "outer_runtime_cpu_only")
    resources = _available_resources()
    host = {
        "hostname": platform.node(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": int(os.cpu_count() or 1),
        "python_executable": sys.executable,
    }
    runtime = _runtime_versions(device)
    stable = _digest({"host": host, "runtime": runtime, "device": device})
    return {"host": host, "runtime": runtime, "device": device, "resources": resources, "runtime_fingerprint": stable}


def _validate_workers(workers: int) -> None:
    require(type(workers) is int and workers >= 1, "outer_runtime_workers_invalid")


def _bind_plan(root: Path, run: Path) -> tuple[dict[str, Any], dict[str, str]]:
    plan = load_plan(root, run)
    actual = source_hashes(root)
    require(plan.get("sources") == actual, "outer_runtime_source_hash_drift")
    return plan, actual


def _receipt_paths(run: Path, context: Mapping[str, Any]) -> dict[str, Path]:
    directory = Path(run) / "qualification"
    identity = str(context["runtime_fingerprint"])
    return {
        "directory": directory,
        "canary": directory / f"{identity}-canary.json",
        "profile": directory / f"{identity}-profile.json",
        "final": directory / f"{identity}.json",
    }


def _feature_batch(x: np.ndarray, y: np.ndarray, *, species: str = "canary") -> FeatureBatch:
    names = tuple([f"feature_{index:03d}" for index in range(x.shape[1])])
    kinds = ("continuous",) * x.shape[1]
    schema = hashlib.sha256(canonical_json({"feature_names": names, "feature_kinds": kinds, "continuous_count": x.shape[1]}).encode()).hexdigest()
    return FeatureBatch(
        tuple(RowKey(species, f"cell-{index:04d}") for index in range(len(x))),
        x,
        y.astype(np.float64),
        names,
        kinds,
        x.shape[1],
        schema,
        {},
        "canary",
        "c" * 64,
        "e" * 64,
    )


def _canary_rows(seed: int) -> tuple[IndexedRows, IndexedRows, IndexedRows, np.ndarray, np.ndarray, tuple[str, ...]]:
    rng = np.random.default_rng(stable_seed("goal052-outer-canary", seed))
    x = rng.normal(size=(CANARY_ROWS, 103)).astype(np.float32)
    y = (np.arange(CANARY_ROWS) % 2).astype(np.float32)
    target = IndexedRows(x, np.arange(CANARY_ROWS), y)
    q = ((x[:, 0] * 0.25 + x[:, 1] * 0.1) > 0).astype(np.float32)
    q = (q - q.mean()) / q.std(ddof=0)
    target_q = IndexedRows(np.column_stack((x, q)).astype(np.float32), np.arange(CANARY_ROWS), y)
    aux_indices = np.tile(np.arange(CANARY_ROWS), len(CANARY_HEADS))
    aux_head = np.repeat(np.arange(len(CANARY_HEADS), dtype=np.int64), CANARY_ROWS)
    aux_y = ((aux_indices + aux_head) % 3 == 0).astype(np.float32)
    weights = np.full(len(aux_y), len(aux_y) / len(CANARY_HEADS) / CANARY_ROWS, dtype=np.float32)
    aux = IndexedRows(x, aux_indices, aux_y, aux_head, weights)
    discovery = aux.subset(np.tile(np.r_[True, False], len(aux_y) // 2))
    stopping = aux.subset(~np.tile(np.r_[True, False], len(aux_y) // 2))
    return discovery, stopping, aux, target_q.features, target.features, CANARY_HEADS


def _state_digest(state: Mapping[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        digest.update(name.encode())
        digest.update(np.asarray(state[name].detach().cpu(), dtype=np.float32).tobytes())
    return digest.hexdigest()


def _state_size_bytes(state: Mapping[str, torch.Tensor]) -> int:
    return int(sum(value.numel() * value.element_size() for value in state.values()))


def _canary_repetition(root: str, repeat: int, device: str) -> dict[str, Any]:
    root_path = Path(root)
    config = native.config_at(root_path)
    spec = native.spec_for(config, "seawfb_scale")
    torch.use_deterministic_algorithms(True)
    # The two labelled repetitions intentionally use the same seed and inputs:
    # they are independent process executions whose states and scores must be
    # byte-identical on a qualified host.
    discovery, stopping, aux, target_q_x, target_x, heads = _canary_rows(CANARY_SEED)
    q_store = _CanaryQStore(CANARY_SEED)
    numerical_fit = baseline._config(root_path)["community_control"]["numerical_fit"]
    q_model, q_fit = fit_q_linear(
        q_store,
        0,
        FULL_FOLD,
        "full",
        baseline._seed_namespace(baseline._config(root_path), "q"),
        numerical_fit,
    )
    options = {"seed": stable_seed("goal052-outer-canary", CANARY_SEED), "epochs": 1, "batch_size": 128, "device_name": device}
    started = time.monotonic()
    pre_fixed, shared_fixed, pre_receipt = fit_pretraining_fixed(spec, aux, heads, **options)
    pre_native, native_receipt = fit_pretraining_lifecycle(
        spec, discovery, stopping, aux, heads,
        seed=options["seed"], device_name=device, batch_size=128, max_epochs=1, patience=1, min_delta=0.0,
    )
    require(_state_digest(shared_fixed) == _state_digest(pre_native), "canary_pretraining_replay_mismatch")
    target_results: dict[str, Any] = {}
    for arm_index, arm in enumerate(native.ARMS):
        augmented = arm == native.ARMS[1]
        rows = target_q_x if augmented else target_x
        target_rows = IndexedRows(rows, np.arange(CANARY_ROWS), (np.arange(CANARY_ROWS) % 2).astype(np.float32))
        transferred = shared_fixed if arm in native.ARMS[2:] else None
        frozen = arm == native.ARMS[2]
        seed = stable_seed("goal052-outer-canary-target", CANARY_SEED, arm)
        fixed_scores, fixed_state, fixed_receipt = fit_target_fixed(
            spec, target_rows, rows, seed=seed, epochs=1, batch_size=128, device_name=device,
            transferred_state=transferred, freeze_trunk=frozen,
        )
        native_scores, native_receipt_target = fit_target_lifecycle(
            spec, target_rows, target_rows, target_rows, rows, seed=seed, device_name=device,
            batch_size=128, max_epochs=1, patience=1, min_delta=0.0,
            transferred_state=transferred, freeze_trunk=frozen,
        )
        require(np.array_equal(fixed_scores, native_scores), f"canary_target_replay_mismatch:{arm}")
        target_results[arm] = {
            "score_digest": _digest(fixed_scores.tolist()),
            "state_digest": _state_digest(fixed_state),
            "native_state_digest": native_receipt_target["final_model_digest"],
            "frozen": frozen,
            "feature_width": int(rows.shape[1]),
        }
    # Exercise all selected conventional adapters, including ANN save/reload.
    conventional = {}
    batch = _feature_batch(target_x, (np.arange(CANARY_ROWS) % 2).astype(np.float32))
    with tempfile.TemporaryDirectory(prefix="goal052-outer-canary-") as temporary:
        for candidate_id in ("rf02", "hgb04", "ann02"):
            candidate = CANONICAL_CANDIDATES[candidate_id]
            family = candidate["family"]
            fitted, report = build_adapter(family).fit(
                batch, None, candidate, stable_seed("goal052-outer-canary-conventional", CANARY_SEED, candidate_id),
                exact_epochs=1 if family == "shallow_ann" else None,
            )
            scores = fitted.predict_scores(batch)
            path = Path(temporary) / f"{candidate_id}.json"
            envelope = fitted.serialize(path)
            reloaded = load_fitted_model(path, envelope["whole_file_sha256"])
            require(np.array_equal(scores, reloaded.predict_scores(batch)), f"canary_save_reload_mismatch:{candidate_id}")
            conventional[candidate_id] = {"family": family, "score_digest": _digest(scores.tolist()), "iterations": report.iterations, "model_size_bytes": int(path.stat().st_size)}
    return {
        "repeat": repeat,
        "pid": os.getpid(),
        "status": "canary_repeat_valid",
        "runtime_seconds": time.monotonic() - started,
        "peak_rss_bytes": _rss_bytes(),
        "pretraining": {"fixed": _state_digest(shared_fixed), "native": _state_digest(pre_native), "receipt": pre_receipt, "native_receipt": native_receipt},
        "targets": target_results,
        "conventional": conventional,
        "q": {
            "parameter_digest": q_parameter_digest(q_model.coefficient, q_model.intercept),
            "fit": q_fit,
        },
        "feature_widths": {"base": 103, "q": 104},
    }


def _canary_worker_ready(barrier: Any) -> None:
    barrier.wait(timeout=60)


def _run_canary_repetitions(root: Path, device: str, workers: int) -> list[dict[str, Any]]:
    # Keep even the serial qualification on a fresh worker so its RSS and
    # numerical thread state are measured independently of the caller.
    context = multiprocessing.get_context("spawn")
    labels = tuple(range(max(2, workers)))
    barrier = context.Barrier(workers)
    with ProcessPoolExecutor(max_workers=workers, mp_context=context,
                             initializer=_canary_worker_ready, initargs=(barrier,)) as pool:
        futures = [pool.submit(_canary_repetition, str(root), repeat, device) for repeat in labels]
        results = [future.result() for future in futures]
    require(len({item["pid"] for item in results}) == workers, "outer_runtime_canary_concurrency_not_exercised")
    return results


def _strip_dynamic(value: Any) -> Any:
    """Remove measurements that are allowed to vary between fresh workers."""

    if isinstance(value, Mapping):
        return {
            key: _strip_dynamic(item)
            for key, item in value.items()
            if key not in {"repeat", "pid", "runtime_seconds", "elapsed_seconds", "wall_seconds", "peak_rss_bytes", "resources"}
        }
    if isinstance(value, list):
        return [_strip_dynamic(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_dynamic(item) for item in value)
    return value


def _write_or_validate(path: Path, value: Mapping[str, Any]) -> str:
    write_once(path, value)
    return _sha_file(path)


def _maybe_finalize(root: Path, run: Path, plan: Mapping[str, Any], context: Mapping[str, Any]) -> str | None:
    paths = _receipt_paths(run, context)
    if not paths["canary"].is_file() or not paths["profile"].is_file():
        return None
    canary = json.loads(paths["canary"].read_text())
    profile = json.loads(paths["profile"].read_text())
    require(canary.get("status") == CANARY_STATUS and profile.get("status") == PROFILE_STATUS, "outer_runtime_stage_invalid")
    require(canary.get("plan_digest") == plan["plan_digest"] == profile.get("plan_digest"), "outer_runtime_plan_mismatch")
    require(canary.get("runtime_fingerprint") == profile.get("runtime_fingerprint") == context["runtime_fingerprint"], "outer_runtime_fingerprint_mismatch")
    qualified_workers = int(profile.get("qualified_workers", 0))
    require(qualified_workers >= 1, "outer_runtime_no_qualified_workers")
    canary_workers = int(canary.get("workers_tested", canary.get("workers_requested", 0)))
    require(canary_workers >= 1, "outer_runtime_canary_workers_missing")
    qualified_workers = min(qualified_workers, canary_workers)
    final = {
        "schema_version": SCHEMA_VERSION,
        "status": QUALIFIED_STATUS,
        "plan_digest": plan["plan_digest"],
        # Available memory is a measurement, not part of the identity.  Keep
        # it in stage receipts while making the final gate stable across a
        # later resource probe on the same host.
        "runtime": {key: value for key, value in context.items() if key != "resources"},
        "runtime_fingerprint": context["runtime_fingerprint"],
        "qualified_workers": qualified_workers,
        "canary_workers_tested": canary_workers,
        "canary_sha256": _sha_file(paths["canary"]),
        "profile_sha256": _sha_file(paths["profile"]),
        "canary": str(paths["canary"].relative_to(run)),
        "profile": str(paths["profile"].relative_to(run)),
        "files": {
            str(paths["canary"].relative_to(run)): _sha_file(paths["canary"]),
            str(paths["profile"].relative_to(run)): _sha_file(paths["profile"]),
        },
        "outer_response_rows_read": 0,
    }
    _write_or_validate(paths["final"], final)
    return str(paths["final"].relative_to(run))


def qualify(root: Path, run: Path, device: str = "cpu", workers: int = 1) -> dict[str, Any]:
    """Run deterministic synthetic qualification on this actual host."""

    _validate_workers(workers)
    root, run = Path(root), Path(run)
    plan, code_hashes = _bind_plan(root, run)
    context = _runtime_context(device)
    paths = _receipt_paths(run, context)
    if paths["canary"].is_file():
        receipt = json.loads(paths["canary"].read_text())
        require(receipt.get("plan_digest") == plan["plan_digest"], "outer_runtime_canary_plan_mismatch")
    else:
        started = time.monotonic()
        repeats = _run_canary_repetitions(root, device, workers)
        require(len(repeats) >= len(CANARY_REPEATS), "outer_runtime_canary_repeat_count")
        reference = _strip_dynamic(repeats[0])
        require(all(_strip_dynamic(item) == reference for item in repeats[1:]), "outer_runtime_canary_repeat_drift")
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "status": CANARY_STATUS,
            "plan_digest": plan["plan_digest"],
            "runtime": context,
            "runtime_fingerprint": context["runtime_fingerprint"],
            "code_hashes": code_hashes,
            "workers_requested": workers,
            "workers_tested": workers,
            "repeat_count": len(repeats),
            "repeats": repeats,
            "repeat_score_digests": [
                {arm: value["score_digest"] for arm, value in repeat["targets"].items()}
                for repeat in repeats
            ],
            "deterministic_repeats": True,
            "started_seconds": started,
            "runtime_seconds": float(time.monotonic() - started),
            "peak_rss_bytes": int(max([_rss_bytes(), *[int(item["peak_rss_bytes"]) for item in repeats]])),
            "outer_response_rows_read": 0,
        }
        _write_or_validate(paths["canary"], receipt)
    final = _maybe_finalize(root, run, plan, context)
    return {"status": receipt["status"], "plan_digest": plan["plan_digest"], "runtime_fingerprint": context["runtime_fingerprint"], "canary": str(paths["canary"].relative_to(run)), "qualification": final}


def _conventional_profile_choices(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Select one maximum-memory candidate and largest target per family."""

    tasks = [task for task in plan.get("tasks", ()) if task.get("kind") == "conventional"]
    required = {"random_forest", "hist_gradient_boosting", "shallow_ann"}
    families = {str(task.get("family")) for task in tasks}
    require(required.issubset(families), "outer_profile_conventional_family_missing")

    def rank(task: Mapping[str, Any]) -> tuple[Any, ...]:
        candidate = CANONICAL_CANDIDATES[str(task["candidate_id"])]
        family = str(task["family"])
        if family == "random_forest":
            # Smaller leaves and unlimited depth retain more tree structure.
            depth = candidate.get("max_depth")
            return (1 if candidate.get("min_samples_leaf") == 1 else 0,
                    -int(candidate.get("min_samples_leaf", 0)),
                    1 if depth is None else 0,
                    int(depth or 0), str(candidate["id"]))
        if family == "shallow_ann":
            return (int(candidate.get("width", 0)), -float(candidate.get("dropout", 0)), str(candidate["id"]))
        if family == "hist_gradient_boosting":
            return (int(candidate.get("max_leaf_nodes", 0)),
                    -int(candidate.get("min_samples_leaf", 0)), str(candidate["id"]))
        return (str(candidate["id"]),)

    selected: list[dict[str, Any]] = []
    for family in sorted(required):
        family_tasks = [task for task in tasks if task.get("family") == family]
        candidate_id = max(family_tasks, key=rank)["candidate_id"]
        candidate_tasks = [task for task in family_tasks if task.get("candidate_id") == candidate_id]
        target_task = max(candidate_tasks, key=lambda task: int(plan.get("target_rows", {}).get(task["target"], {}).get("rows", 0)))
        selected.append({"family": family, "candidate_id": candidate_id, "target": target_task["target"]})
    return selected


def _append_engineering_q(train: FeatureBatch, prediction: FeatureBatch) -> tuple[FeatureBatch, FeatureBatch, dict[str, float]]:
    """Append a deterministic bounded linear feature for engineering-only q fits."""

    raw_train = np.tanh(np.asarray(train.x[:, 0], dtype=np.float64))
    mean = float(raw_train.mean())
    sd = float(raw_train.std(ddof=0))
    require(np.isfinite(mean) and np.isfinite(sd) and sd > 0, "outer_profile_engineering_q_scale_invalid")
    q_train = ((raw_train - mean) / sd).astype(np.float32)
    q_prediction = ((np.tanh(np.asarray(prediction.x[:, 0], dtype=np.float64)) - mean) / sd).astype(np.float32)

    def add(batch: FeatureBatch, q: np.ndarray) -> FeatureBatch:
        x = np.insert(np.asarray(batch.x), int(batch.continuous_count), q, axis=1)
        names = tuple(batch.feature_names[:batch.continuous_count]) + ("q_linear",) + tuple(batch.feature_names[batch.continuous_count:])
        kinds = tuple(batch.feature_kinds[:batch.continuous_count]) + ("continuous",) + tuple(batch.feature_kinds[batch.continuous_count:])
        schema = hashlib.sha256(canonical_json({"feature_names": names, "feature_kinds": kinds, "continuous_count": batch.continuous_count + 1}).encode()).hexdigest()
        return FeatureBatch(batch.keys, x, batch.y, names, kinds, batch.continuous_count + 1,
                            schema, batch.unseen_level_counts, batch.transform_id,
                            _digest({"base": batch.transform_digest, "engineering_q": True}), batch.encoder_digest)

    return add(train, q_train), add(prediction, q_prediction), {"training_mean": mean, "training_population_sd": sd}


def _fit_conventional_profile(
    target: str,
    family: str,
    candidate_id: str,
    train: FeatureBatch,
    prediction: FeatureBatch,
    label: str,
    q_mode: str,
) -> dict[str, Any]:
    candidate = CANONICAL_CANDIDATES[candidate_id]
    started = time.monotonic()
    fitted, report = build_adapter(family).fit(
        train, None, candidate, stable_seed("goal052-outer-profile", target, family, candidate_id, label),
        exact_epochs=1 if family == "shallow_ann" else None,
    )
    scores = fitted.predict_scores(prediction)
    with tempfile.TemporaryDirectory(prefix="goal052-outer-profile-model-") as temporary:
        path = Path(temporary) / "model.json"
        envelope = fitted.serialize(path)
        reloaded = load_fitted_model(path, envelope["whole_file_sha256"])
        reloaded_scores = reloaded.predict_scores(prediction)
        require(np.array_equal(scores, reloaded_scores), "outer_profile_save_reload_prediction_drift")
        model_size = int(path.stat().st_size)
    return {
        "family": family,
        "candidate_id": candidate_id,
        "target": target,
        "label": label,
        "q_mode": q_mode,
        "rows": len(train.keys),
        "feature_width": train.x.shape[1],
        "runtime_seconds": time.monotonic() - started,
        "peak_rss_bytes": _rss_bytes(),
        "iterations": report.iterations,
        "score_digest": _digest(scores.tolist()),
        "model_size_bytes": model_size,
        "save_reload_predictions_exact": True,
        "resource_binding": "engineering_profile_only",
    }


def profile(root: Path, run: Path, device: str = "cpu", workers: int = 1) -> dict[str, Any]:
    """Measure one full-row engineering lifecycle and conventional capacity."""

    _validate_workers(workers)
    require(device == "cpu", "outer_profile_cpu_only")
    root, run = Path(root), Path(run)
    plan, code_hashes = _bind_plan(root, run)
    context = _runtime_context(device)
    paths = _receipt_paths(run, context)
    if paths["profile"].is_file():
        receipt = json.loads(paths["profile"].read_text())
    else:
        started = time.monotonic()
        store = RetainedFullStore(root)
        block = max(plan["auxiliary_rows"], key=lambda key: int(plan["auxiliary_rows"][key]["rows"]))
        block_int = int(block)
        target = max(
            (name for name in plan["targets"] if int(store.crossfit["focal_blocks"][name]) == block_int),
            key=lambda name: int(plan["target_rows"][name]["rows"]),
        )
        auxiliary = auxiliary_full_data(store, block_int)
        auxiliary_rows = len(auxiliary.replay.y)
        auxiliary_row_digest = auxiliary.metadata["row_digest"]
        spec = native.spec_for(native.config_at(root), "seawfb_scale")
        seed = stable_seed("goal052-outer-profile", block_int)
        pre_started = time.monotonic()
        pre_state, pre_shared, pre_fit = fit_pretraining_fixed(spec, auxiliary.replay, auxiliary.heads, seed=seed, epochs=1, device_name=device)
        pre_runtime = time.monotonic() - pre_started
        # The full auxiliary matrix is the largest transient allocation.  Do
        # not retain it while fitting q or focal targets.
        del auxiliary
        gc.collect()
        numerical_fit = baseline._config(root)["community_control"]["numerical_fit"]
        q_started = time.monotonic()
        q_model, q_fit = fit_q_linear(store, block_int, FULL_FOLD, "full", baseline._seed_namespace(baseline._config(root), "q"), numerical_fit)
        q_runtime = time.monotonic() - q_started
        target_plain = target_full_data(store, target)
        target_q = target_full_data(store, target, q_model)
        with np.load(run / "domain.npz", allow_pickle=False) as payload:
            domain_arrays = {key: payload[key] for key in payload.files}
        domain = {"arrays": domain_arrays, "summary": plan["domain"]}
        prediction_plain = prediction_batch(store, domain)
        prediction_q = prediction_batch(store, domain, q_model, target_q.metadata["q_scaling"])
        target_fits = {}
        ordinary_arms = (native.ARMS[0], native.ARMS[2], native.ARMS[3])
        for augmented, data, prediction in ((False, target_plain, prediction_plain), (True, target_q, prediction_q)):
            arms = ordinary_arms if not augmented else (native.ARMS[1],)
            for arm in arms:
                transferred = pre_shared if (not augmented and arm in native.ARMS[2:]) else None
                fit_started = time.monotonic()
                scores, state, fit = fit_target_fixed(spec, data.replay, prediction.x, seed=stable_seed("goal052-outer-profile-target", target, arm, augmented), epochs=1, device_name=device, transferred_state=transferred, freeze_trunk=arm == native.ARMS[2])
                target_fits[f"{arm}:{'q' if augmented else 'ordinary'}"] = {"rows": len(data.replay.y), "feature_width": prediction.x.shape[1], "runtime_seconds": time.monotonic() - fit_started, "score_digest": _digest(scores.tolist()), "state_digest": _state_digest(state), "model_size_bytes": _state_size_bytes(state), "fit": fit}
        # Profile the largest retained target for the most demanding selected
        # candidate in each conventional family.  The actual q fit is reused
        # for the selected target; other target q columns are a bounded,
        # deterministic engineering proxy and are marked accordingly.
        conventional = {}
        for choice in _conventional_profile_choices(plan):
            choice_target = str(choice["target"])
            if choice_target == target:
                plain_data, plain_prediction = target_plain, prediction_plain
                q_data, q_prediction, q_mode = target_q, prediction_q, "actual"
            else:
                plain_data = target_full_data(store, choice_target)
                plain_prediction = prediction_batch(store, domain)
                engineered_train, engineered_prediction, _ = _append_engineering_q(plain_data.train, plain_prediction)
                q_data = engineered_train
                q_prediction = engineered_prediction
                q_mode = "synthetic_bounded_linear"
            ordinary_key = f"{choice['family']}:{choice['candidate_id']}:ordinary"
            q_key = f"{choice['family']}:{choice['candidate_id']}:q"
            conventional[ordinary_key] = _fit_conventional_profile(
                choice_target, choice["family"], choice["candidate_id"], plain_data.train,
                plain_prediction, "ordinary", "none",
            )
            conventional[q_key] = _fit_conventional_profile(
                choice_target, choice["family"], choice["candidate_id"],
                q_data.train if hasattr(q_data, "train") else q_data, q_prediction, "q", q_mode,
            )
            if choice_target != target:
                del plain_data
                gc.collect()
        resources = _available_resources()
        peak = max([_rss_bytes(), int(pre_fit.get("peak_rss_bytes", 0)), *[int(item.get("peak_rss_bytes", 0)) for item in target_fits.values()], *[int(item.get("peak_rss_bytes", 0)) for item in conventional.values()]])
        require(resources["available_ram_bytes"] is not None, "outer_runtime_capacity_unavailable")
        require(resources["available_cpus"] is not None and int(resources["available_cpus"]) >= 1, "outer_runtime_cpu_capacity_unavailable")
        admissible = int(int(resources["available_ram_bytes"]) // max(1.3 * peak, 1))
        require(admissible >= 1, "outer_runtime_capacity_insufficient")
        admissible = min(workers, int(resources["available_cpus"]), admissible)
        receipt = {"schema_version": SCHEMA_VERSION, "status": PROFILE_STATUS, "plan_digest": plan["plan_digest"], "runtime": context, "runtime_fingerprint": context["runtime_fingerprint"], "code_hashes": code_hashes, "workers_requested": workers, "qualified_workers": admissible, "selected_block": block_int, "selected_target": target, "full_auxiliary_rows": auxiliary_rows, "full_auxiliary_row_digest": auxiliary_row_digest, "target_rows": len(target_plain.replay.y), "target_row_digest": target_plain.metadata["row_digest"], "pretraining": {"runtime_seconds": pre_runtime, "fit": pre_fit, "state_digest": _state_digest(pre_state), "shared_digest": _state_digest(pre_shared), "model_size_bytes": _state_size_bytes(pre_state)}, "q_profile": {"runtime_seconds": q_runtime, "parameter_digest": q_parameter_digest(q_model.coefficient, q_model.intercept), "fit": q_fit}, "target_fits": target_fits, "conventional_fits": conventional, "resources": resources, "peak_rss_bytes": peak, "runtime_seconds": time.monotonic() - started, "engineering_only": True, "outer_response_rows_read": 0}
        _write_or_validate(paths["profile"], receipt)
    final = _maybe_finalize(root, run, plan, context)
    return {"status": receipt["status"], "plan_digest": plan["plan_digest"], "runtime_fingerprint": context["runtime_fingerprint"], "profile": str(paths["profile"].relative_to(run)), "qualification": final, "qualified_workers": receipt.get("qualified_workers")}


def require_qualification(root: Path, run: Path, plan: Mapping[str, Any], device: str = "cpu", workers: int = 1) -> str:
    """Require a matching actual-host canary/profile qualification receipt."""

    _validate_workers(workers)
    root, run = Path(root), Path(run)
    context = _runtime_context(device)
    paths = _receipt_paths(run, context)
    require(paths["final"].is_file(), "outer_runtime_qualification_missing")
    receipt = json.loads(paths["final"].read_text())
    require(receipt.get("schema_version") == SCHEMA_VERSION and receipt.get("status") == QUALIFIED_STATUS, "outer_runtime_qualification_invalid")
    require(receipt.get("plan_digest") == plan.get("plan_digest"), "outer_runtime_plan_mismatch")
    require(receipt.get("runtime_fingerprint") == context["runtime_fingerprint"], "outer_runtime_fingerprint_mismatch")
    require(workers <= int(receipt.get("qualified_workers", 0)), "outer_runtime_workers_exceed_qualification")
    require(_sha_file(run / receipt["canary"]) == receipt["canary_sha256"], "outer_runtime_canary_hash_mismatch")
    require(_sha_file(run / receipt["profile"]) == receipt["profile_sha256"], "outer_runtime_profile_hash_mismatch")
    require(receipt.get("files") == {
        receipt["canary"]: receipt["canary_sha256"],
        receipt["profile"]: receipt["profile_sha256"],
    }, "outer_runtime_file_binding_invalid")
    actual = source_hashes(root)
    require(plan.get("sources") == actual, "outer_runtime_source_hash_drift")
    canary = json.loads((run / receipt["canary"]).read_text())
    profile = json.loads((run / receipt["profile"]).read_text())
    require(canary.get("status") == CANARY_STATUS and profile.get("status") == PROFILE_STATUS, "outer_runtime_stage_invalid")
    require(canary.get("plan_digest") == plan.get("plan_digest") == profile.get("plan_digest"), "outer_runtime_stage_plan_mismatch")
    require(canary.get("runtime_fingerprint") == context["runtime_fingerprint"] == profile.get("runtime_fingerprint"), "outer_runtime_stage_fingerprint_mismatch")
    require(canary.get("code_hashes") == actual, "outer_runtime_canary_source_drift")
    require(profile.get("code_hashes") == actual, "outer_runtime_profile_source_drift")
    profile_peak = int(profile.get("peak_rss_bytes", 0))
    require(profile_peak > 0, "outer_runtime_profile_peak_missing")
    resources = _available_resources()
    require(resources.get("available_ram_bytes") is not None, "outer_runtime_capacity_unavailable")
    require(resources.get("available_cpus") is not None and int(resources["available_cpus"]) >= workers, "outer_runtime_cpu_capacity_insufficient")
    require(int(resources["available_ram_bytes"]) >= int(np.ceil(workers * 1.3 * profile_peak)), "outer_runtime_capacity_insufficient")
    return str(paths["final"].relative_to(run))


__all__ = ["qualify", "profile", "require_qualification"]
