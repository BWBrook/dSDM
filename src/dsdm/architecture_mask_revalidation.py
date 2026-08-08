"""Corrected, fresh-identity architecture selection for Goal035.

This module replays Goal033's declared screen/shortlist design against the
immutable 40 Goal033 bundles after split-scoped categorical neutralisation.
It deliberately keeps all labels, scores, and corrected bundles private.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np

from .architecture_runner import (
    RunnerError, _canonical, _digest_bytes, _load_private, _metrics_for_rows,
    _validate_arrays, _validate_receipt, _is_digest,
    choose_tss_threshold, derive_fit_seed, rank_architectures, roc_auc,
    validate_private_bundle, validate_private_bundles,
)
from .architecture_selection import load_selection_config, validate_authorities, leave_one_species_out_audit
from .categorical_support import SupportMask, apply_support_mask, fit_support_mask
from .contracts import ARCHITECTURES, FOLDS, SPECIES, ArchitectureSpec
from .real_data import RealDataBundle
from .real_training import train_case_with_predictions


class RevalidationError(ValueError):
    """Raised when corrected architecture state is invalid or incomplete."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RevalidationError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class RevalidationConfig:
    source_path: Path
    raw: Mapping[str, Any]
    species: tuple[str, ...]
    folds: tuple[str, ...]
    architectures: tuple[str, ...]
    screen_seed: int
    shortlist_seeds: tuple[int, ...]
    shortlist_size: int
    workers: int


_AUTHORITY_KEYS = frozenset({"goal028_config", "goal028_decision", "goal033_config", "goal033_decision", "goal033_aggregate", "goal034_config", "goal034_decision"})
_EXECUTION_SOURCE_KEYS = frozenset({"architecture_mask_revalidation", "categorical_support", "architecture_selection", "architecture_runner", "real_data", "real_training", "models", "uv_lock"})


def load_revalidation_config(path: str | Path) -> RevalidationConfig:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RevalidationError(f"invalid config: {exc}") from exc
    _require(isinstance(raw, dict), "config must be an object")
    required = {"schema_version", "goal_id", "authorities", "execution_sources", "scope", "selection", "runtime", "privacy", "evidence"}
    _require(set(raw) == required, "config keys drift")
    _require(raw["schema_version"] == "1.0" and raw["goal_id"] == "goal035-dsdm-final-inner-lifecycle", "config identity drift")
    authorities = raw["authorities"]
    _require(isinstance(authorities, dict) and set(authorities) == _AUTHORITY_KEYS, "authority key set drift")
    for binding in authorities.values():
        _require(set(binding) == {"path", "sha256"} and _is_digest(binding["sha256"]), "authority binding invalid")
    _require(set(raw["execution_sources"]) == _EXECUTION_SOURCE_KEYS, "execution source key set drift")
    for binding in raw["execution_sources"].values():
        _require(set(binding) == {"path", "sha256"} and _is_digest(binding["sha256"]), "execution source binding invalid")
    scope = raw["scope"]
    _require(set(scope) == {"species", "folds", "endpoint", "predictor_count", "immutable_input_goal", "fresh_identity_namespace"}, "scope keys drift")
    _require(tuple(scope["species"]) == SPECIES and tuple(scope["folds"]) == FOLDS and scope["predictor_count"] == 77, "scope drift")
    selection = raw["selection"]
    _require(set(selection) == {"method", "screen_base_seed", "shortlist_size", "shortlist_base_seeds", "architectures"} and selection["method"] == "target_only_resmlp", "selection keys drift")
    archs = tuple(selection["architectures"])
    _require(archs == tuple(row[0] for row in ARCHITECTURES), "architecture registry drift")
    _require(selection["screen_base_seed"] == 31031 and selection["shortlist_size"] == 4 and tuple(selection["shortlist_base_seeds"]) == (31031, 31032, 31033), "selection drift")
    _require(raw["runtime"] == {"python_major_minor": "3.12", "numpy": "2.2.6", "torch": "2.7.1", "device": "cpu", "threads": 1, "route": "mac_cpu"}, "runtime drift")
    _require(raw["privacy"] == {"outer_attempted": 0, "outer_opened": 0, "tracked_predictions": False, "tracked_labels": False, "row_identifiers": False, "coordinates": False}, "privacy drift")
    execution = raw["evidence"].get("execution", {})
    _require(set(raw["evidence"]) == {"private_root", "tracked_root", "aggregate_only", "execution"}, "evidence keys drift")
    _require(set(execution) == {"workers", "screen_logical_evaluations", "shortlist_logical_evaluations", "physical_fit_multiplier"} and execution["screen_logical_evaluations"] == 960 and execution["shortlist_logical_evaluations"] == 480 and execution["physical_fit_multiplier"] == 2, "execution arithmetic drift")
    _require(raw["evidence"].get("aggregate_only") is True and execution.get("workers") == 3, "evidence policy drift")
    return RevalidationConfig(source, raw, SPECIES, FOLDS, archs, 31031, (31031, 31032, 31033), 4, 3)


def config_digest(config: RevalidationConfig) -> str:
    return _sha256(config.source_path)


def execution_source_fingerprint(config: RevalidationConfig) -> str:
    payload = [{"name": name, "path": binding["path"], "sha256": binding["sha256"]} for name, binding in sorted(config.raw["execution_sources"].items())]
    return _digest_bytes(_canonical(payload).encode())


def runtime_attestation(config: RevalidationConfig, *, strict: bool = True) -> dict[str, Any]:
    import platform
    import torch
    if config.raw["runtime"]["device"] == "cpu":
        torch.set_num_threads(int(config.raw["runtime"]["threads"]))
    actual = {"system": platform.system(), "machine": platform.machine(), "python_major_minor": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}", "numpy": np.__version__, "torch": str(torch.__version__).split("+")[0], "device": "cpu", "threads": torch.get_num_threads(), "route": "mac_cpu"}
    if strict:
        expected = config.raw["runtime"]
        _require(actual["system"] == "Darwin" and actual["machine"] == "arm64", "Goal035 runtime host must be Darwin arm64")
        for key in ("python_major_minor", "numpy", "torch", "device", "route"):
            _require(str(actual[key]) == str(expected[key]), f"runtime mismatch: {key}")
        _require(int(actual["threads"]) == int(expected["threads"]), "runtime thread mismatch")
    return actual


def validate_revalidation_authorities(config: RevalidationConfig, root: str | Path) -> dict[str, str]:
    """Recompute every bound authority and execution-source digest."""
    root = Path(root)
    result: dict[str, str] = {}
    for group in ("authorities", "execution_sources"):
        for name, binding in config.raw[group].items():
            path = root / binding["path"]
            _require(path.is_file(), f"{group} missing: {name}")
            digest = _sha256(path)
            _require(digest == binding["sha256"], f"{group} digest mismatch: {name}")
            result[name] = digest
    return result


def validate_immutable_inputs(config: RevalidationConfig, bundle_root: str | Path, root: str | Path) -> list[dict[str, Any]]:
    """Validate old bundles through Goal033's complete authority gate."""
    root = Path(root)
    goal033_path = root / config.raw["authorities"]["goal033_config"]["path"]
    goal033 = load_selection_config(goal033_path)
    validate_authorities(goal033, root)
    manifests = validate_private_bundles(bundle_root, config=goal033, repo_root=root)
    source_membership = {m["source_binding_digest"] for m in manifests}
    _require(len(source_membership) == 1, "immutable source membership drift")
    aggregate_binding = config.raw["authorities"]["goal033_aggregate"]
    aggregate_path = root / aggregate_binding["path"]
    aggregate = json.loads(aggregate_path.read_text())
    _require(aggregate.get("success") is True, "Goal033 aggregate is not successful")
    goal033_digest = _sha256(goal033_path)
    _require(aggregate.get("config_digest") == goal033_digest, "Goal033 aggregate config binding drift")
    common_source = next(iter(source_membership))
    _require(aggregate.get("source_binding_digest") == common_source, "Goal033 aggregate source binding drift")
    expected_inventory = _digest_bytes(_canonical(sorted(m["bundle_digest"] for m in manifests)).encode())
    _require(aggregate.get("bundle_inventory_digest") == expected_inventory, "Goal033 aggregate bundle inventory drift")
    return manifests


def bundle_digest(bundle: RealDataBundle, source_digest: str) -> str:
    arrays = {name: np.asarray(getattr(bundle, name)) for name in ("x_discovery", "y_discovery", "x_stopping", "y_stopping", "x_replay", "y_replay", "x_inner_assessment", "y_inner_assessment")}
    payload = {"source": source_digest, "mask": dict(bundle.metadata).get("support_mask_digest"), "arrays": {k: _digest_bytes(np.ascontiguousarray(v).tobytes()) for k, v in arrays.items()}}
    return _digest_bytes(_canonical(payload).encode())


def mask_architecture_bundle(bundle: RealDataBundle) -> tuple[RealDataBundle, dict[str, Any]]:
    """Apply a replay-fitted target mask to every target role."""
    support = fit_support_mask(bundle.x_replay)
    masked: dict[str, np.ndarray] = {}
    audits: list[Mapping[str, object]] = []
    for role in ("discovery", "stopping", "replay", "inner_assessment"):
        values, audit = apply_support_mask(getattr(bundle, f"x_{role}"), support)
        masked[role] = values
        audits.append(audit)
    for role in ("discovery", "stopping", "replay"):
        _require(np.array_equal(masked[role], getattr(bundle, f"x_{role}")), f"{role} training covariates changed")
    metadata = dict(bundle.metadata)
    metadata["support_mask_digest"] = support.digest
    metadata["support_mask_columns"] = int(support.columns.sum())
    result = RealDataBundle(bundle.case, masked["discovery"], bundle.y_discovery, masked["stopping"], bundle.y_stopping, masked["replay"], bundle.y_replay, masked["inner_assessment"], bundle.y_inner_assessment, metadata)
    changed = audits[-1]
    audit = {
        "support_mask_digest": support.digest,
        "supported_columns": int(support.columns.sum()),
        "affected_rows": int(changed["affected_rows"]),
        "affected_instances": int(changed["affected_instances"]),
        "unsupported_columns": int(changed["unsupported_columns"]),
        "training_byte_identical": True,
        "continuous_byte_identical": True,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    return result, audit


def load_corrected_bundles(bundle_root: str | Path, *, expected_count: int = 40) -> list[tuple[Path, RealDataBundle, dict[str, Any]]]:
    paths = sorted(Path(bundle_root).glob("*.npz"))
    _require(len(paths) == expected_count, f"expected {expected_count} immutable Goal033 bundles")
    output = []
    for path in paths:
        manifest = validate_private_bundle(path)
        bundle, _ = _load_private(path, manifest["architecture_id"] if "architecture_id" in manifest else "resmlp00", 31031)
        corrected, audit = mask_architecture_bundle(bundle)
        metadata = dict(corrected.metadata)
        metadata["mask_audit"] = audit
        corrected = RealDataBundle(corrected.case, corrected.x_discovery, corrected.y_discovery, corrected.x_stopping, corrected.y_stopping, corrected.x_replay, corrected.y_replay, corrected.x_inner_assessment, corrected.y_inner_assessment, metadata)
        output.append((path, corrected, manifest))
    _require({(b.case.target, b.case.held_fold) for _, b, _ in output} == {(s, f) for s in SPECIES for f in FOLDS}, "immutable bundle cross-product mismatch")
    return output


_LEAF_KEYS = frozenset({"stage", "target", "held_fold", "architecture", "base_seed", "fit_seed", "bundle_digest", "source_bundle_digest", "config_digest", "runtime_digest", "mask_digest", "held_row_count"})


def revalidation_leaf_identity(identity: Mapping[str, Any]) -> str:
    _require(set(identity) == _LEAF_KEYS, "revalidation leaf identity keys drift")
    _require(identity["stage"] in {"screen", "shortlist"} and identity["target"] in SPECIES and identity["held_fold"] in FOLDS and identity["architecture"] in {a[0] for a in ARCHITECTURES}, "leaf identity scope invalid")
    for key in ("bundle_digest", "source_bundle_digest", "config_digest", "runtime_digest", "mask_digest"):
        _require(_is_digest(identity[key]), f"leaf digest invalid: {key}")
    return _digest_bytes(_canonical(dict(identity)).encode())


def expected_tasks(config: RevalidationConfig, stage: str, bundle_root: str | Path, leaves: str | Path, *, architectures: Sequence[str] | None = None, repo_root: str | Path | None = None, expected_count: int = 40) -> list[dict[str, Any]]:
    _require(stage in {"screen", "shortlist"}, "stage invalid")
    if repo_root is not None:
        validate_revalidation_authorities(config, repo_root)
        validate_immutable_inputs(config, bundle_root, repo_root)
        runtime_attestation(config, strict=True)
    _require(type(expected_count) is int and expected_count > 0, "bundle fixture count invalid")
    bundles = load_corrected_bundles(bundle_root, expected_count=expected_count)
    archs = tuple(architectures or config.architectures)
    if stage == "shortlist":
        _require(len(archs) == config.shortlist_size, "shortlist architecture count invalid")
    seeds = (config.screen_seed,) if stage == "screen" else config.shortlist_seeds
    c_digest = config_digest(config)
    actual_runtime = runtime_attestation(config, strict=True)
    actual_runtime_digest = _digest_bytes(_canonical(actual_runtime).encode())
    tasks = []
    for path, bundle, manifest in sorted(bundles, key=lambda row: (row[1].case.target, row[1].case.held_fold)):
        mask = str(bundle.metadata["support_mask_digest"])
        b_digest = bundle_digest(bundle, str(manifest.get("source_binding_digest", "unbound")))
        for architecture in archs:
            for seed in seeds:
                tasks.append({"stage": stage, "target": bundle.case.target, "held_fold": bundle.case.held_fold, "architecture": architecture, "base_seed": int(seed), "fit_seed": derive_fit_seed(int(seed), bundle.case.target, bundle.case.held_fold, "fraction100/full", architecture), "bundle_digest": b_digest, "source_bundle_digest": manifest["bundle_digest"], "config_digest": c_digest, "runtime_digest": actual_runtime_digest, "mask_digest": mask, "held_row_count": int(len(bundle.y_inner_assessment)), "bundle_path": str(path), "leaf_root": str(leaves)})
    _require(len({revalidation_leaf_identity({k: t[k] for k in _LEAF_KEYS}) for t in tasks}) == len(tasks), "fresh leaf identity collision")
    return tasks


def _write_leaf(task: Mapping[str, Any], scores: np.ndarray, receipt: Mapping[str, Any]) -> str:
    identity = {k: task[k] for k in _LEAF_KEYS}
    values = np.asarray(scores, dtype=np.float32)
    _require(values.ndim == 1 and len(values) == identity["held_row_count"] and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "leaf scores invalid")
    root = Path(task["leaf_root"]); root.mkdir(parents=True, exist_ok=True)
    directory = root / revalidation_leaf_identity(identity)
    if directory.exists():
        validate_leaf(directory, identity)
        return str(directory)
    temporary = Path(tempfile.mkdtemp(prefix=".leaf-", dir=str(root)))
    try:
        np.save(temporary / "scores.npy", values, allow_pickle=False)
        envelope = {"identity": identity, "shape": list(values.shape), "dtype": "float32", "scores_sha256": _digest_bytes(values.tobytes()), "receipt": dict(receipt)}
        (temporary / "metadata.json").write_text(_canonical(envelope) + "\n")
        os.replace(temporary, directory)
    except Exception:
        if temporary.exists():
            for item in temporary.iterdir(): item.unlink()
            temporary.rmdir()
        raise
    return str(directory)


def validate_leaf(path: str | Path, identity: Mapping[str, Any]) -> bool:
    directory = Path(path); identity = dict(identity); revalidation_leaf_identity(identity)
    _require(directory.is_dir() and {p.name for p in directory.iterdir()} == {"scores.npy", "metadata.json"}, "leaf incomplete")
    envelope = json.loads((directory / "metadata.json").read_text())
    scores = np.load(directory / "scores.npy", allow_pickle=False)
    _require(set(envelope) == {"identity", "shape", "dtype", "scores_sha256", "receipt"}, "leaf envelope keys drift")
    _require(envelope["identity"] == identity and envelope["shape"] == list(scores.shape) and envelope["dtype"] == "float32", "leaf identity mismatch")
    _require(scores.dtype == np.float32 and scores.ndim == 1 and len(scores) == identity["held_row_count"], "leaf score shape/dtype invalid")
    _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "leaf scores invalid")
    _require(envelope["scores_sha256"] == _digest_bytes(np.ascontiguousarray(scores).tobytes()), "leaf digest mismatch")
    receipt = envelope["receipt"]
    required_receipt = {"prediction_digest", "model_digest", "training_bundle_digest", "runtime_fingerprint", "fit_seed", "selected_epoch", "discovery_executed_epochs", "replay_epochs", "stopping_status", "outer_attempted", "outer_opened"}
    _require(set(receipt) == required_receipt, "leaf receipt keys drift")
    _require(receipt.get("training_bundle_digest") == identity["bundle_digest"] and receipt.get("runtime_fingerprint") == identity["runtime_digest"], "receipt binding mismatch")
    for key in ("prediction_digest", "model_digest", "training_bundle_digest", "runtime_fingerprint"):
        _require(_is_digest(receipt[key]), f"receipt digest invalid: {key}")
    _require(receipt.get("fit_seed") == identity["fit_seed"], "fit seed mismatch")
    _require(type(receipt.get("selected_epoch")) is int and receipt["selected_epoch"] >= 1, "selected epoch invalid")
    _require(type(receipt.get("discovery_executed_epochs")) is int and receipt["discovery_executed_epochs"] >= receipt["selected_epoch"], "discovery epoch invalid")
    _require(type(receipt.get("replay_epochs")) is int and receipt["replay_epochs"] == receipt["selected_epoch"], "replay epoch invalid")
    _require(receipt.get("stopping_status") in {"patience_stop", "max_epochs_reached"}, "stopping status invalid")
    _require(receipt.get("outer_attempted") == 0 and receipt.get("outer_opened") == 0, "outer access detected")
    _require(receipt.get("prediction_digest") == _digest_bytes(np.ascontiguousarray(scores).tobytes()), "prediction digest mismatch")
    return True


def _run_one(task: Mapping[str, Any]) -> str:
    identity = {k: task[k] for k in _LEAF_KEYS}
    path = Path(task["leaf_root"]) / revalidation_leaf_identity(identity)
    if path.exists():
        validate_leaf(path, identity)
        return str(path)
    manifest = validate_private_bundle(task["bundle_path"])
    _require(manifest["bundle_digest"] == identity["source_bundle_digest"], "immutable source bundle digest mismatch")
    bundle, _ = _load_private(task["bundle_path"], task["architecture"], int(task["base_seed"]))
    corrected, _ = mask_architecture_bundle(bundle)
    _require(bundle_digest(corrected, str(corrected.metadata.get("source_binding_digest", "unbound"))) == identity["bundle_digest"], "corrected bundle digest mismatch")
    spec = next(ArchitectureSpec(*row) for row in ARCHITECTURES if row[0] == task["architecture"])
    receipt, scores = train_case_with_predictions(corrected, spec, seed=int(task["fit_seed"]), device="cpu", max_epochs=300, patience=30, min_delta=0.0)
    metadata = {"prediction_digest": _digest_bytes(np.ascontiguousarray(scores).tobytes()), "training_bundle_digest": identity["bundle_digest"], "runtime_fingerprint": identity["runtime_digest"], "model_digest": receipt.model_digest, "fit_seed": int(task["fit_seed"]), "selected_epoch": receipt.selected_epoch, "discovery_executed_epochs": receipt.discovery_executed_epochs, "replay_epochs": receipt.replay_epochs, "stopping_status": receipt.stopping_status, "outer_attempted": 0, "outer_opened": 0}
    return _write_leaf(task, scores, metadata)


def run_tasks(tasks: Sequence[Mapping[str, Any]], *, workers: int = 3) -> list[Path]:
    _require(type(workers) is int and workers == 3, "worker policy must be exactly 3")
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as pool:
        return [Path(value) for value in pool.map(_run_one, tasks)]


def _replay_pairs(screen_tasks: Sequence[Mapping[str, Any]], shortlist_tasks: Sequence[Mapping[str, Any]], ranking: Sequence[str], leaves: str | Path) -> int:
    shortlist = {(t["target"], t["held_fold"], t["architecture"]): t for t in shortlist_tasks if t["base_seed"] == 31031}
    pairs = 0
    for task in screen_tasks:
        if task["base_seed"] != 31031 or task["architecture"] not in ranking[:4]:
            continue
        key = (task["target"], task["held_fold"], task["architecture"])
        _require(key in shortlist, "shortlist replay task missing")
        a = Path(leaves) / revalidation_leaf_identity({k: task[k] for k in _LEAF_KEYS})
        btask = shortlist[key]; b = Path(leaves) / revalidation_leaf_identity({k: btask[k] for k in _LEAF_KEYS})
        validate_leaf(a, {k: task[k] for k in _LEAF_KEYS}); validate_leaf(b, {k: btask[k] for k in _LEAF_KEYS})
        ma = json.loads((a / "metadata.json").read_text()); mb = json.loads((b / "metadata.json").read_text())
        _require(np.load(a / "scores.npy", allow_pickle=False).tobytes() == np.load(b / "scores.npy", allow_pickle=False).tobytes(), "screen/shortlist score replay mismatch")
        _require(ma["receipt"] == mb["receipt"], "screen/shortlist deterministic receipt mismatch")
        pairs += 1
    _require(pairs == 160, f"expected 160 replay pairs, got {pairs}")
    return pairs


def run_pipeline(config: RevalidationConfig, bundle_root: str | Path, leaves: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    _require("goal033" not in str(Path(leaves)), "old Goal033 leaf root cannot be reused")
    screen_tasks = expected_tasks(config, "screen", bundle_root, leaves, repo_root=repo_root)
    run_tasks(screen_tasks, workers=config.workers)
    screen_state = status(config, bundle_root, leaves, repo_root=repo_root)
    _require(screen_state["screen_complete"] == 960, "screen incomplete")
    screen = _aggregate_stage(config, bundle_root, leaves, "screen", config.architectures)
    shortlist_tasks = expected_tasks(config, "shortlist", bundle_root, leaves, architectures=screen["ranking"][: config.shortlist_size], repo_root=repo_root)
    run_tasks(shortlist_tasks, workers=config.workers)
    shortlist = _aggregate_stage(config, bundle_root, leaves, "shortlist", screen["ranking"][: config.shortlist_size])
    repeats = _replay_pairs(screen_tasks, shortlist_tasks, screen["ranking"], leaves)
    return {"screen": {"complete": len(screen_tasks), "ranking": screen["ranking"]}, "shortlist": {"complete": len(shortlist_tasks), "ranking": shortlist["ranking"]}, "repeat_pairs": repeats, "outer_attempted": 0, "outer_opened": 0}


def plan(config: RevalidationConfig) -> dict[str, int]:
    screen = len(config.architectures) * len(config.species) * len(config.folds)
    shortlist = config.shortlist_size * len(config.species) * len(config.folds) * len(config.shortlist_seeds)
    return {"screen_logical_evaluations": screen, "shortlist_logical_evaluations": shortlist, "logical_evaluations": screen + shortlist, "physical_fits": 2 * (screen + shortlist), "workers": config.workers}


def audit_categories(bundle_root: str | Path) -> dict[str, Any]:
    rows = [dict(bundle.metadata).get("mask_audit", {}) for _, bundle, _ in load_corrected_bundles(bundle_root)]
    affected = [row for row in rows if row["affected_rows"]]
    return {"cases": len(rows), "affected_cases": len(affected), "affected_rows": sum(row["affected_rows"] for row in rows), "affected_instances": sum(row["affected_instances"] for row in rows), "affected_column_occurrences": sum(row["unsupported_columns"] for row in rows), "outer_attempted": 0, "outer_opened": 0}


def status(config: RevalidationConfig, bundle_root: str | Path, leaves: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    screen = expected_tasks(config, "screen", bundle_root, leaves, repo_root=repo_root)
    complete = 0
    invalid = 0
    for task in screen:
        path = Path(leaves) / revalidation_leaf_identity({k: task[k] for k in _LEAF_KEYS})
        if not path.exists():
            continue
        try:
            validate_leaf(path, {k: task[k] for k in _LEAF_KEYS}); complete += 1
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            invalid += 1
    result = {"screen_expected": len(screen), "screen_complete": int(complete), "screen_invalid": invalid, "screen_missing": len(screen) - int(complete) - invalid, "shortlist_expected": 480, "shortlist_complete": 0, "shortlist_missing": 480, "outer_attempted": 0, "outer_opened": 0}
    if complete == len(screen):
        ranked = _aggregate_stage(config, bundle_root, leaves, "screen", config.architectures)["ranking"]
        shortlist = expected_tasks(config, "shortlist", bundle_root, leaves, architectures=ranked[: config.shortlist_size], repo_root=repo_root)
        shortlist_complete = 0; shortlist_invalid = 0
        for task in shortlist:
            path = Path(leaves) / revalidation_leaf_identity({k: task[k] for k in _LEAF_KEYS})
            if not path.exists():
                continue
            try:
                validate_leaf(path, {k: task[k] for k in _LEAF_KEYS}); shortlist_complete += 1
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                shortlist_invalid += 1
        result.update(shortlist_complete=int(shortlist_complete), shortlist_invalid=shortlist_invalid, shortlist_missing=480 - int(shortlist_complete) - shortlist_invalid, phase="complete" if shortlist_complete == 480 and shortlist_invalid == 0 else "shortlist")
    else:
        result["phase"] = "screen"
    return result


def _aggregate_stage(config: RevalidationConfig, bundle_root: str | Path, leaves: str | Path, stage: str, architectures: Sequence[str]) -> dict[str, Any]:
    tasks = expected_tasks(config, stage, bundle_root, leaves, architectures=architectures)
    by_case = {(bundle.case.target, bundle.case.held_fold): bundle for _, bundle, _ in load_corrected_bundles(bundle_root)}
    rows: dict[tuple[str, str], list[tuple[str, int, np.ndarray, np.ndarray]]] = {}
    inventory: list[str] = []
    for task in tasks:
        identity = {k: task[k] for k in _LEAF_KEYS}
        leaf = Path(leaves) / revalidation_leaf_identity(identity)
        validate_leaf(leaf, identity)
        scores = np.load(leaf / "scores.npy", allow_pickle=False)
        bundle = by_case[(task["target"], task["held_fold"])]
        _require(len(scores) == len(bundle.y_inner_assessment), "score/label alignment mismatch")
        rows.setdefault((task["architecture"], task["target"]), []).append((task["held_fold"], int(task["base_seed"]), scores, bundle.y_inner_assessment))
        envelope = json.loads((leaf / "metadata.json").read_text())
        inventory.append(_canonical({"identity": identity, "scores_sha256": envelope["scores_sha256"]}))
    metrics: dict[str, dict[str, dict[str, float]]] = {}
    expected_per = len({int(t["base_seed"]) for t in tasks}) * len(FOLDS)
    for (architecture, target), values in rows.items():
        _require(len(values) == expected_per, "fold/seed coverage mismatch")
        metrics.setdefault(architecture, {})[target] = _metrics_for_rows(values)
    return {"metrics": metrics, "ranking": rank_architectures(metrics), "loso": leave_one_species_out_audit(metrics), "leaf_inventory_digest": _digest_bytes("\n".join(sorted(inventory)).encode())}


def finalize(config: RevalidationConfig, bundle_root: str | Path, leaves: str | Path, tracked: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Write aggregate evidence only after every corrected leaf validates."""
    root = Path(repo_root or config.source_path.parents[1])
    validate_revalidation_authorities(config, root)
    runtime = runtime_attestation(config, strict=True)
    validate_immutable_inputs(config, bundle_root, root)
    screen_tasks = expected_tasks(config, "screen", bundle_root, leaves, repo_root=root)
    screen = _aggregate_stage(config, bundle_root, leaves, "screen", config.architectures)
    shortlist_architectures = screen["ranking"][: config.shortlist_size]
    shortlist_tasks = expected_tasks(config, "shortlist", bundle_root, leaves, architectures=shortlist_architectures, repo_root=root)
    shortlist = _aggregate_stage(config, bundle_root, leaves, "shortlist", shortlist_architectures)
    repeat_pairs = _replay_pairs(screen_tasks, shortlist_tasks, screen["ranking"], leaves)
    old_binding = config.raw["authorities"]["goal033_aggregate"]
    old_path = root / old_binding["path"]; _require(_sha256(old_path) == old_binding["sha256"], "Goal033 aggregate authority drift")
    old_receipt = json.loads(old_path.read_text()); old_winner = old_receipt.get("final_winner")
    _require(old_winner == "resmlp13", "Goal033 original winner drift")
    masks = [dict(bundle.metadata).get("support_mask_digest") for _, bundle, _ in load_corrected_bundles(bundle_root)]
    corrected_bundle_digests = [bundle_digest(bundle, str(manifest.get("source_binding_digest", "unbound"))) for _, bundle, manifest in load_corrected_bundles(bundle_root)]
    receipt = {
        "schema_version": "goal035-corrected-aggregate-v1",
        "success": True,
        "original_winner": old_winner,
        "corrected_winner": shortlist["ranking"][0],
        "screen_ranking": screen["ranking"],
        "shortlist_ranking": shortlist["ranking"],
        "screen_metrics": screen["metrics"],
        "shortlist_metrics": shortlist["metrics"],
        "screen_loso": screen["loso"],
        "shortlist_loso": shortlist["loso"],
        "config_digest": config_digest(config),
        "authority_digests": validate_revalidation_authorities(config, root),
        "execution_source_fingerprint": execution_source_fingerprint(config),
        "runtime_attestation": runtime,
        "runtime_attestation_digest": _digest_bytes(_canonical(runtime).encode()),
        "corrected_bundle_inventory_digest": _digest_bytes(_canonical(sorted(corrected_bundle_digests)).encode()),
        "support_mask_inventory_digest": _digest_bytes(_canonical(sorted(masks)).encode()),
        "screen_leaf_inventory_digest": screen["leaf_inventory_digest"],
        "shortlist_leaf_inventory_digest": shortlist["leaf_inventory_digest"],
        "repeat_pairs": repeat_pairs,
        "expected_repeat_pairs": 160,
        "category_audit": audit_categories(bundle_root),
        "screen_logical_evaluations": 960,
        "shortlist_logical_evaluations": 480,
        "logical_evaluations": 1440,
        "physical_fits": 2880,
        "workers": 3,
        "route": "mac_cpu",
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    output = Path(tracked); output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp"); temporary.write_text(_canonical(receipt) + "\n"); os.replace(temporary, output)
    return receipt


def validate(config: RevalidationConfig, bundle_root: str | Path, leaves: str | Path, tracked: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    # Recompute without writing by using the same aggregate gates.
    root = Path(repo_root or config.source_path.parents[1]); validate_revalidation_authorities(config, root); runtime = runtime_attestation(config, strict=True); validate_immutable_inputs(config, bundle_root, root)
    screen_tasks = expected_tasks(config, "screen", bundle_root, leaves, repo_root=root)
    screen = _aggregate_stage(config, bundle_root, leaves, "screen", config.architectures)
    shortlist_tasks = expected_tasks(config, "shortlist", bundle_root, leaves, architectures=screen["ranking"][: config.shortlist_size], repo_root=root)
    shortlist = _aggregate_stage(config, bundle_root, leaves, "shortlist", screen["ranking"][: config.shortlist_size])
    repeat_pairs = _replay_pairs(screen_tasks, shortlist_tasks, screen["ranking"], leaves)
    old_binding = config.raw["authorities"]["goal033_aggregate"]; old_path = root / old_binding["path"]; _require(_sha256(old_path) == old_binding["sha256"], "Goal033 aggregate authority drift"); old_winner = json.loads(old_path.read_text()).get("final_winner"); _require(old_winner == "resmlp13", "Goal033 original winner drift")
    masks = [dict(bundle.metadata).get("support_mask_digest") for _, bundle, _ in load_corrected_bundles(bundle_root)]
    corrected_bundle_digests = [bundle_digest(bundle, str(manifest.get("source_binding_digest", "unbound"))) for _, bundle, manifest in load_corrected_bundles(bundle_root)]
    expected = {
        "schema_version": "goal035-corrected-aggregate-v1", "success": True, "original_winner": old_winner, "corrected_winner": shortlist["ranking"][0], "screen_ranking": screen["ranking"], "shortlist_ranking": shortlist["ranking"], "screen_metrics": screen["metrics"], "shortlist_metrics": shortlist["metrics"], "screen_loso": screen["loso"], "shortlist_loso": shortlist["loso"], "config_digest": config_digest(config), "authority_digests": validate_revalidation_authorities(config, root), "execution_source_fingerprint": execution_source_fingerprint(config), "runtime_attestation": runtime, "runtime_attestation_digest": _digest_bytes(_canonical(runtime).encode()), "corrected_bundle_inventory_digest": _digest_bytes(_canonical(sorted(corrected_bundle_digests)).encode()), "support_mask_inventory_digest": _digest_bytes(_canonical(sorted(masks)).encode()), "screen_leaf_inventory_digest": screen["leaf_inventory_digest"], "shortlist_leaf_inventory_digest": shortlist["leaf_inventory_digest"], "repeat_pairs": repeat_pairs, "expected_repeat_pairs": 160, "category_audit": audit_categories(bundle_root), "screen_logical_evaluations": 960, "shortlist_logical_evaluations": 480, "logical_evaluations": 1440, "physical_fits": 2880, "workers": 3, "route": "mac_cpu", "outer_attempted": 0, "outer_opened": 0,
    }
    path = Path(tracked); _require(path.is_file(), "aggregate receipt missing"); _require(json.loads(path.read_text()) == expected, "aggregate receipt mismatch")
    return expected


def _cli() -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.architecture_mask_revalidation")
    parser.add_argument("--config", default="config/dsdm_categorical_revalidation.json")
    parser.add_argument("--bundles", default="data/processed/dsdm/goal033-architecture-selection/private/bundles")
    parser.add_argument("--leaves", default="data/processed/dsdm/goal035-final-inner-lifecycle/private/revalidation-leaves")
    parser.add_argument("--tracked", default="evidence/dsdm_architecture_selection/goal035/aggregate.json")
    parser.add_argument("command", choices=("plan", "audit-categories", "run", "status", "finalize", "validate"))
    args = parser.parse_args(); config = load_revalidation_config(args.config); validate_revalidation_authorities(config, Path(args.config).parents[1])
    if args.command == "plan": print(json.dumps(plan(config), sort_keys=True)); return 0
    if args.command == "audit-categories": print(json.dumps(audit_categories(args.bundles), sort_keys=True)); return 0
    if args.command == "status": print(json.dumps(status(config, args.bundles, args.leaves, repo_root=Path(args.config).parents[1]), sort_keys=True)); return 0
    if args.command == "run":
        _require("goal033" not in str(Path(args.leaves)), "old Goal033 leaf root cannot be reused")
        print(json.dumps(run_pipeline(config, args.bundles, args.leaves, repo_root=Path(args.config).parents[1]), sort_keys=True)); return 0
    if args.command == "finalize":
        print(json.dumps(finalize(config, args.bundles, args.leaves, args.tracked, repo_root=Path(args.config).parents[1]), sort_keys=True)); return 0
    if args.command == "validate":
        print(json.dumps(validate(config, args.bundles, args.leaves, args.tracked, repo_root=Path(args.config).parents[1]), sort_keys=True)); return 0
    raise RevalidationError("unsupported command")


if __name__ == "__main__":
    raise SystemExit(_cli())
