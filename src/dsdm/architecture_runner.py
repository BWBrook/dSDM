"""Private, identity-addressed Goal033 execution and aggregate validation.

The runner deliberately keeps labels, predictions, and model receipts below the
private root.  Only a deterministic aggregate receipt may be written to the
tracked evidence path, and only by ``finalize``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .architecture_selection import (
    SelectionConfig, SelectionError, build_task_plan, choose_tss_threshold,
    derive_fit_seed, load_selection_config, rank_architectures, roc_auc,
    validate_authorities,
)
from .contracts import ARCHITECTURES, FOLDS, SPECIES, ArchitectureSpec
from .real_data import RealDataBundle
from .real_training import train_case_with_predictions


class RunnerError(ValueError):
    """Raised when private execution state is missing or tampered."""


_BUNDLE_ARRAYS = ("x_discovery", "y_discovery", "x_stopping", "y_stopping", "x_replay", "y_replay", "x_held", "y_held")
_ROLES = ("discovery", "stopping", "replay", "held")
_HEX64 = set("0123456789abcdef")
_LEAF_KEYS = frozenset({"stage", "target", "held_fold", "architecture", "base_seed", "fit_seed", "bundle_digest", "config_digest", "runtime_digest", "held_row_count"})
_RECEIPT_KEYS = frozenset({"prediction_digest", "model_digest", "training_bundle_digest", "fit_seed", "selected_epoch", "discovery_executed_epochs", "replay_epochs", "stopping_status", "runtime_fingerprint", "outer_attempted", "outer_opened"})
_FORBIDDEN = ("row_id", "grid_cell", "site_id", "camera_id", "coordinate", "prediction", "label", "latitude", "longitude")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RunnerError(message)


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest_file(path: str | Path) -> str:
    return _digest_bytes(Path(path).read_bytes())


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= _HEX64


def runtime_attestation(expected: Mapping[str, Any], *, strict: bool = True) -> dict[str, str]:
    """Return actual runtime identity and fail closed against Goal033 config."""
    import torch
    # The configured runtime contract is part of the identity.  Set the
    # deterministic CPU thread count before recording the attestation.
    if str(expected.get("device", "cpu")) == "cpu":
        torch.set_num_threads(int(expected.get("threads", 1)))
    actual = {
        "system": platform.system(),
        "machine": platform.machine(),
        "python_major_minor": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
        "numpy": np.__version__,
        "torch": str(torch.__version__).split("+")[0],
        "device": "cpu",
        "threads": str(torch.get_num_threads()),
        "route": "mac_cpu",
    }
    if strict:
        _require(actual["system"] == "Darwin" and actual["machine"] == "arm64", "runtime host must be Darwin arm64")
        for key in ("python_major_minor", "numpy", "torch", "device", "threads"):
            if key in expected:
                _require(actual[key] == str(expected[key]), f"runtime attestation mismatch: {key}")
        _require(str(expected.get("route", "mac_cpu")) == "mac_cpu", "runtime route drift")
    return actual


def runtime_digest(attestation: Mapping[str, Any]) -> str:
    return _digest_bytes(_canonical(dict(attestation)).encode())


def leaf_identity(identity: Mapping[str, Any]) -> str:
    """Hash exactly the ten identity fields; no omissions or additions."""
    _require(set(identity) == _LEAF_KEYS, "leaf identity keys drift")
    _require(identity["stage"] in {"screen", "shortlist"}, "leaf stage invalid")
    _require(identity["target"] in SPECIES and identity["held_fold"] in FOLDS, "leaf target/fold invalid")
    _require(identity["architecture"] in {row[0] for row in ARCHITECTURES}, "leaf architecture invalid")
    _require(type(identity["base_seed"]) is int and type(identity["fit_seed"]) is int, "leaf seeds invalid")
    _require(type(identity["held_row_count"]) is int and identity["held_row_count"] > 0, "leaf row count invalid")
    for key in ("bundle_digest", "config_digest", "runtime_digest"):
        _require(_is_digest(identity[key]), f"leaf {key} invalid")
    return _digest_bytes(_canonical(dict(identity)).encode())


def _validate_receipt(receipt: Mapping[str, Any], identity: Mapping[str, Any], scores: np.ndarray) -> None:
    _require(set(receipt) == _RECEIPT_KEYS, "leaf receipt keys drift")
    for key in ("prediction_digest", "model_digest", "training_bundle_digest", "runtime_fingerprint"):
        _require(_is_digest(receipt[key]), f"leaf receipt {key} invalid")
    _require(receipt["training_bundle_digest"] == identity["bundle_digest"], "training bundle relation mismatch")
    _require(receipt["runtime_fingerprint"] == identity["runtime_digest"], "runtime relation mismatch")
    _require(receipt["fit_seed"] == identity["fit_seed"], "fit seed relation mismatch")
    _require(receipt["outer_attempted"] == 0 and receipt["outer_opened"] == 0, "outer access detected")
    _require(receipt["prediction_digest"] == _digest_bytes(np.ascontiguousarray(scores).tobytes(order="C")), "prediction digest mismatch")
    for key in ("selected_epoch", "discovery_executed_epochs", "replay_epochs"):
        _require(type(receipt[key]) is int and receipt[key] >= 1, f"{key} invalid")
    _require(receipt["replay_epochs"] == receipt["selected_epoch"], "replay epoch relation mismatch")
    _require(receipt["discovery_executed_epochs"] >= receipt["selected_epoch"], "discovery epoch relation mismatch")
    _require(receipt["stopping_status"] in {"patience_stop", "max_epochs_reached"}, "stopping status invalid")


def atomic_write_leaf(root: str | Path, identity: Mapping[str, Any], scores: np.ndarray, *, metadata: Mapping[str, Any] | None = None) -> Path:
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    identity = dict(identity); leaf_identity(identity)
    values = np.asarray(scores)
    _require(values.dtype == np.float32 and values.ndim == 1 and len(values) == identity["held_row_count"], "leaf scores invalid")
    _require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "leaf scores invalid")
    if metadata is None:
        metadata = {
            "prediction_digest": _digest_bytes(np.ascontiguousarray(values).tobytes(order="C")),
            "model_digest": "0" * 64,
            "training_bundle_digest": identity["bundle_digest"],
            "fit_seed": identity["fit_seed"], "selected_epoch": 1, "discovery_executed_epochs": 1,
            "replay_epochs": 1, "stopping_status": "max_epochs_reached",
            "runtime_fingerprint": identity["runtime_digest"], "outer_attempted": 0, "outer_opened": 0,
        }
    receipt = dict(metadata); _validate_receipt(receipt, identity, values)
    directory = root / leaf_identity(identity)
    temporary = Path(tempfile.mkdtemp(prefix=f".{directory.name}.", dir=str(root)))
    try:
        np.save(temporary / "scores.npy", np.ascontiguousarray(values), allow_pickle=False)
        envelope = {"identity": identity, "shape": list(values.shape), "dtype": "float32", "scores_sha256": _digest_bytes(values.tobytes(order="C")), "receipt": receipt}
        (temporary / "metadata.json").write_text(_canonical(envelope) + "\n", encoding="utf-8")
        if directory.exists():
            validate_leaf(directory, identity); return directory
        os.replace(temporary, directory); return directory
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir(): child.unlink()
            temporary.rmdir()
        raise


def validate_leaf(path: str | Path, identity: Mapping[str, Any]) -> bool:
    path = Path(path); identity = dict(identity); leaf_identity(identity)
    _require(path.is_dir() and {p.name for p in path.iterdir()} == {"scores.npy", "metadata.json"}, "leaf incomplete")
    try:
        envelope = json.loads((path / "metadata.json").read_text(encoding="utf-8")); scores = np.load(path / "scores.npy", allow_pickle=False)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RunnerError("leaf unreadable") from exc
    _require(set(envelope) == {"identity", "shape", "dtype", "scores_sha256", "receipt"}, "leaf envelope keys drift")
    _require(envelope["identity"] == identity and path.name == leaf_identity(identity), "leaf identity mismatch")
    _require(scores.dtype == np.float32 and scores.ndim == 1 and len(scores) == identity["held_row_count"], "leaf scores invalid")
    _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "leaf scores invalid")
    _require(envelope["shape"] == list(scores.shape) and envelope["dtype"] == "float32" and envelope["scores_sha256"] == _digest_bytes(np.ascontiguousarray(scores).tobytes(order="C")), "leaf digest mismatch")
    _validate_receipt(envelope["receipt"], identity, scores)
    return True


def validate_resume_leaf(path: str | Path, identity: Mapping[str, Any]) -> bool:
    return validate_leaf(path, identity)


def _bundle_arrays(bundle: RealDataBundle) -> dict[str, np.ndarray]:
    return {"x_discovery": bundle.x_discovery, "y_discovery": bundle.y_discovery, "x_stopping": bundle.x_stopping, "y_stopping": bundle.y_stopping, "x_replay": bundle.x_replay, "y_replay": bundle.y_replay, "x_held": bundle.x_inner_assessment, "y_held": bundle.y_inner_assessment}


def _validate_arrays(arrays: Mapping[str, np.ndarray]) -> None:
    for role in _ROLES:
        x = np.asarray(arrays[f"x_{role}"]); y = np.asarray(arrays[f"y_{role}"])
        _require(x.dtype == np.float32 and x.ndim == 2 and x.shape[1] == 77 and len(x) > 0, f"{role} predictors invalid")
        _require(y.dtype == np.float32 and y.ndim == 1 and len(y) == len(x), f"{role} response invalid")
        _require(np.isfinite(x).all() and np.isfinite(y).all() and np.isin(y, (0, 1)).all() and len(np.unique(y)) == 2, f"{role} requires both classes")


def _bundle_manifest(bundle: RealDataBundle, *, config_digest: str | None = None) -> dict[str, Any]:
    arrays = _bundle_arrays(bundle); _validate_arrays(arrays)
    metadata = dict(bundle.metadata)
    manifest = {
        "schema_version": "goal033-private-bundle-v1", "goal_id": "goal033-dsdm-architecture-selection",
        "target": bundle.case.target, "held_fold": bundle.case.held_fold, "stopping_fold": bundle.case.stopping_fold,
        "predictor_count": 77, "array_shapes": {k: list(v.shape) for k, v in arrays.items()},
        "array_digests": {k: _digest_bytes(np.ascontiguousarray(v).tobytes(order="C")) for k, v in arrays.items()},
        "goal033_config_digest": config_digest or str(metadata.get("goal033_config_digest", "unbound")),
        "goal032_config_digest": str(metadata.get("goal032_config_digest", "unbound")),
        "authority_digests": dict(metadata.get("authority_digests", {})),
        "source_binding_digest": str(metadata.get("source_binding_digest", "unbound")),
        "outer_attempted": 0, "outer_opened": 0,
    }
    _require(_is_digest(manifest["goal032_config_digest"]) and _is_digest(manifest["source_binding_digest"]), "Goal032 binding missing")
    _require(set(manifest["authority_digests"]) == {"goal029_config", "goal026_feature_contract", "goal026_fit_parameters"} and all(_is_digest(v) for v in manifest["authority_digests"].values()), "foundation authority binding invalid")
    _require(manifest["goal033_config_digest"] == "unbound" or _is_digest(manifest["goal033_config_digest"]), "Goal033 config binding invalid")
    check = dict(manifest); manifest["bundle_digest"] = _digest_bytes(_canonical(check).encode()); return manifest


def export_private_bundles(bundles: Iterable[RealDataBundle], output: str | Path, *, config: SelectionConfig | None = None) -> list[Path]:
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    _require(config is not None, "Goal033 config is required for private export")
    config_digest = _digest_file(config.source_path)
    all_bundles = list(bundles)
    _require(len(all_bundles) == 40, f"expected exactly 40 bundles, got {len(all_bundles)}")
    identities = [(b.case.target, b.case.held_fold) for b in all_bundles]
    _require(len(set(identities)) == 40 and set(identities) == {(s, f) for s in SPECIES for f in FOLDS}, "bundle cross-product drift")
    paths = []
    for target, held_fold in sorted(identities):
        bundle = all_bundles[identities.index((target, held_fold))]; manifest = _bundle_manifest(bundle, config_digest=config_digest)
        payload = {**_bundle_arrays(bundle), "manifest_json": np.frombuffer(_canonical(manifest).encode(), dtype=np.uint8)}
        filename = f"{target}--{held_fold}--{_digest_bytes(_canonical({'target': target, 'held_fold': held_fold}).encode())}.npz"
        temporary = output / f".{filename}.tmp.npz"; np.savez_compressed(temporary, **payload); final = output / filename; os.replace(temporary, final); paths.append(final)
    return paths


def validate_private_bundle(path: str | Path, *, expected_config_digest: str | None = None, expected_goal032: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        with np.load(path, allow_pickle=False) as payload:
            _require(set(payload.files) == set(_BUNDLE_ARRAYS) | {"manifest_json"}, "bundle keys drift")
            manifest = json.loads(bytes(payload["manifest_json"].tolist()).decode()); required = {"schema_version", "goal_id", "target", "held_fold", "stopping_fold", "predictor_count", "array_shapes", "array_digests", "goal033_config_digest", "goal032_config_digest", "authority_digests", "source_binding_digest", "outer_attempted", "outer_opened", "bundle_digest"}
            _require(set(manifest) == required and manifest["schema_version"] == "goal033-private-bundle-v1" and manifest["goal_id"] == "goal033-dsdm-architecture-selection", "bundle manifest schema drift")
            _require(manifest["target"] in SPECIES and manifest["held_fold"] in FOLDS and manifest["stopping_fold"] == f"fold{(int(manifest['held_fold'][-2:]) + 1) % 5:02d}", "bundle identity drift")
            arrays = {name: np.asarray(payload[name]) for name in _BUNDLE_ARRAYS}; _validate_arrays(arrays)
            for name, value in arrays.items():
                _require(manifest["array_shapes"].get(name) == list(value.shape) and manifest["array_digests"].get(name) == _digest_bytes(np.ascontiguousarray(value).tobytes(order="C")), "bundle array digest mismatch")
            _require(_is_digest(manifest["goal033_config_digest"]), "Goal033 config binding invalid")
            _require(_is_digest(manifest["goal032_config_digest"]) and _is_digest(manifest["source_binding_digest"]), "Goal032 binding invalid")
            _require(set(manifest["authority_digests"]) == {"goal029_config", "goal026_feature_contract", "goal026_fit_parameters"} and all(_is_digest(v) for v in manifest["authority_digests"].values()), "foundation authority invalid")
            if expected_config_digest is not None: _require(manifest["goal033_config_digest"] == expected_config_digest, "stale Goal033 config binding")
            if expected_goal032 is not None:
                for key in ("goal032_config_digest",):
                    _require(manifest[key] == expected_goal032[key], f"Goal032 {key} drift")
                _require(manifest["authority_digests"] == expected_goal032["authority_digests"], "Goal032 authority drift")
            check = dict(manifest); claimed = check.pop("bundle_digest"); _require(claimed == _digest_bytes(_canonical(check).encode()), "bundle manifest digest mismatch")
            _require(manifest["outer_attempted"] == 0 and manifest["outer_opened"] == 0, "outer access detected")
            _require(not any(token in _canonical(manifest).lower() for token in _FORBIDDEN), "forbidden private metadata")
            return manifest
    except RunnerError: raise
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc: raise RunnerError("invalid private bundle") from exc


def _expected_goal032(config: SelectionConfig, root: Path) -> dict[str, Any]:
    goal032_digest = _digest_file(root / config.raw["authorities"]["goal032_config"]["path"])
    receipt = json.loads((root / config.raw["authorities"]["goal032_receipt"]["path"]).read_text())
    goal032 = json.loads((root / config.raw["authorities"]["goal032_config"]["path"]).read_text())
    bindings = goal032.get("bindings", {})
    keys = ("goal029_config", "goal026_feature_contract", "goal026_fit_parameters")
    authorities = {key: str(bindings.get(key, {}).get("sha256", "")) for key in keys}
    _require(all(_is_digest(v) for v in authorities.values()), "Goal032 foundation authorities missing")
    _require(receipt.get("success") is True, "Goal032 receipt is not successful")
    return {"goal032_config_digest": goal032_digest, "authority_digests": authorities}


def validate_private_bundles(root: str | Path, expected_count: int = 40, *, config: SelectionConfig | None = None, repo_root: str | Path | None = None) -> list[dict[str, Any]]:
    paths = sorted(Path(root).glob("*.npz")); _require(len(paths) == expected_count == 40, f"expected exactly 40 bundles, got {len(paths)}")
    expected = _expected_goal032(config, Path(repo_root)) if config is not None and repo_root is not None else None
    config_digest = _digest_file(config.source_path) if config is not None else None
    manifests = [validate_private_bundle(path, expected_config_digest=config_digest, expected_goal032=expected) for path in paths]
    _require({(m["target"], m["held_fold"]) for m in manifests} == {(s, f) for s in SPECIES for f in FOLDS}, "bundle cross-product mismatch")
    source_digests = {m["source_binding_digest"] for m in manifests}
    _require(len(source_digests) == 1 and _is_digest(next(iter(source_digests))), "source membership binding drift")
    return manifests


def _load_private(path: str | Path, architecture: str, seed: int) -> tuple[Any, dict[str, Any]]:
    from .real_data import CaseSpec
    with np.load(path, allow_pickle=False) as payload:
        manifest = json.loads(bytes(payload["manifest_json"].tolist()).decode())
        case = CaseSpec("goal033", manifest["target"], manifest["held_fold"], architecture, int(seed))
        arrays = [np.asarray(payload[name], dtype=np.float32) for name in ("x_discovery", "y_discovery", "x_stopping", "y_stopping", "x_replay", "y_replay", "x_held", "y_held")]
    return RealDataBundle(case, *arrays, manifest), manifest


def _run_leaf(task: Mapping[str, Any]) -> str:
    identity = {k: task[k] for k in _LEAF_KEYS}
    root = Path(task["leaf_root"])
    leaf = root / leaf_identity(identity)
    if leaf.exists():
        validate_resume_leaf(leaf, identity)
        return str(leaf)
    spec = ArchitectureSpec(*next(row for row in ARCHITECTURES if row[0] == task["architecture"]))
    manifest = validate_private_bundle(task["bundle_path"])
    bundle, manifest = _load_private(task["bundle_path"], task["architecture"], int(task["base_seed"]))
    _require(manifest["bundle_digest"] == identity["bundle_digest"], "input bundle digest mismatch")
    _require(len(bundle.y_inner_assessment) == identity["held_row_count"], "input held-row count mismatch")
    receipt, scores = train_case_with_predictions(bundle, spec, seed=int(task["fit_seed"]), device="cpu", max_epochs=300, patience=30, min_delta=0.0)
    metadata = {"prediction_digest": _digest_bytes(np.ascontiguousarray(scores).tobytes(order="C")), "model_digest": receipt.model_digest, "training_bundle_digest": identity["bundle_digest"], "fit_seed": int(task["fit_seed"]), "selected_epoch": receipt.selected_epoch, "discovery_executed_epochs": receipt.discovery_executed_epochs, "replay_epochs": receipt.replay_epochs, "stopping_status": receipt.stopping_status, "runtime_fingerprint": identity["runtime_digest"], "outer_attempted": 0, "outer_opened": 0}
    return str(atomic_write_leaf(root, identity, scores, metadata=metadata))


def run_tasks(tasks: Sequence[Mapping[str, Any]], *, workers: int = 3) -> list[Path]:
    _require(type(workers) is int and workers == 3, "worker policy must be exactly 3")
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        return [Path(result) for result in pool.map(_run_leaf, tasks)]


def expected_tasks(config: SelectionConfig, stage: str, leaf_root: str | Path, bundle_root: str | Path, architectures: Sequence[str] | None = None, *, repo_root: str | Path | None = None) -> list[dict[str, Any]]:
    _require(stage in {"screen", "shortlist"}, "unknown stage")
    manifests = validate_private_bundles(bundle_root, config=config, repo_root=repo_root) if repo_root is not None else validate_private_bundles(bundle_root)
    archs = tuple(architectures or config.architectures); _require(stage != "shortlist" or len(archs) == config.shortlist_size, "shortlist architecture count invalid")
    seeds = config.screen_seeds if stage == "screen" else config.shortlist_seeds
    config_digest = _digest_file(config.source_path); attestation = runtime_attestation(config.raw["runtime"], strict=True); r_digest = runtime_digest(attestation)
    tasks = []
    for manifest in sorted(manifests, key=lambda m: (m["target"], m["held_fold"])):
        for architecture in archs:
            for base_seed in seeds:
                fit_seed = derive_fit_seed(int(base_seed), manifest["target"], manifest["held_fold"], config.endpoint, architecture, "fit")
                tasks.append({"stage": stage, "target": manifest["target"], "held_fold": manifest["held_fold"], "architecture": architecture, "base_seed": int(base_seed), "fit_seed": fit_seed, "bundle_digest": manifest["bundle_digest"], "config_digest": config_digest, "runtime_digest": r_digest, "held_row_count": int(manifest["array_shapes"]["y_held"][0]), "bundle_path": str(next(Path(bundle_root).glob(f"*{manifest['target']}--{manifest['held_fold']}--*.npz"))), "leaf_root": str(leaf_root)} )
    _require(len({leaf_identity({k: t[k] for k in _LEAF_KEYS}) for t in tasks}) == len(tasks), "task identity collision")
    return tasks


def status(leaf_root: str | Path, tasks: Sequence[Mapping[str, Any]], *, phase: str | None = None) -> dict[str, Any]:
    complete = invalid = 0
    for task in tasks:
        identity = {k: task[k] for k in _LEAF_KEYS}; path = Path(leaf_root) / leaf_identity(identity)
        if not path.exists(): continue
        try: validate_leaf(path, identity); complete += 1
        except RunnerError: invalid += 1
    return {"expected": len(tasks), "complete": complete, "invalid": invalid, "missing": len(tasks) - complete - invalid, "phase": phase or tasks[0].get("stage", "screen") if tasks else (phase or "screen"), "success": bool(tasks) and complete == len(tasks) and invalid == 0}


def combined_status(config: SelectionConfig, bundle_root: str | Path, leaf_root: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Report screen, derived-shortlist, and complete-work wake status."""
    root = Path(repo_root or config.source_path.parents[1])
    validate_authorities(config, root)
    runtime_attestation(config.raw["runtime"], strict=True)
    validate_private_bundles(bundle_root, config=config, repo_root=root)
    screen_tasks = expected_tasks(config, "screen", leaf_root, bundle_root, repo_root=root)
    screen = status(leaf_root, screen_tasks, phase="screen")
    result = {"screen": screen, "shortlist": {"expected": 480, "complete": 0, "invalid": 0, "missing": 480}, "total_expected": 1440, "total_complete": screen["complete"], "phase": "screen", "success": False}
    if screen["complete"] == 960 and screen["invalid"] == 0:
        ranking = aggregate_stage(leaf_root, bundle_root, screen_tasks, "screen")["ranking"]
        shortlist_tasks = expected_tasks(config, "shortlist", leaf_root, bundle_root, ranking[:config.shortlist_size], repo_root=root)
        shortlist = status(leaf_root, shortlist_tasks, phase="shortlist")
        result["shortlist"] = shortlist
        result["total_complete"] = screen["complete"] + shortlist["complete"]
        result["phase"] = "complete" if shortlist["complete"] == 480 and shortlist["invalid"] == 0 else "shortlist"
        if shortlist["complete"] == 480 and shortlist["invalid"] == 0:
            try:
                result["repeat_pairs"] = _replay(screen_tasks, shortlist_tasks, ranking, leaf_root)
            except RunnerError:
                result["phase"] = "shortlist"
                result["success"] = False
            else:
                result["success"] = True
    return result


def assert_seed_replay_identity(screen_leaf: str | Path, shortlist_leaf: str | Path) -> None:
    first = Path(screen_leaf); second = Path(shortlist_leaf)
    a = json.loads((first / "metadata.json").read_text()); b = json.loads((second / "metadata.json").read_text())
    _require(a["identity"]["base_seed"] == b["identity"]["base_seed"] == 31031, "seed replay requires base seed 31031")
    _require(np.load(first / "scores.npy", allow_pickle=False).tobytes() == np.load(second / "scores.npy", allow_pickle=False).tobytes(), "screen/shortlist score replay mismatch")
    _require(a["receipt"]["prediction_digest"] == b["receipt"]["prediction_digest"] and a["receipt"]["model_digest"] == b["receipt"]["model_digest"], "screen/shortlist digest replay mismatch")


def _metrics_for_rows(rows: Sequence[tuple[str, int, np.ndarray, np.ndarray]]) -> dict[str, float]:
    by_fold: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}
    for fold, _, scores, y in rows: by_fold.setdefault(fold, []).append((scores, y))
    _require(set(by_fold) == set(FOLDS), "fold coverage mismatch")
    means = []
    for fold in FOLDS:
        values = by_fold[fold]; _require(len(values) > 0 and len({len(v[0]) for v in values}) == 1, "seed alignment mismatch")
        mean = np.mean(np.vstack([v[0] for v in values]), axis=0); y = values[0][1]; _require(all(np.array_equal(y, v[1]) for v in values), "label alignment mismatch"); means.append((mean, y))
    aucs = [roc_auc(y, score) for score, y in means]; all_y = np.concatenate([y for _, y in means]); all_s = np.concatenate([score for score, _ in means]); threshold = choose_tss_threshold(all_y, all_s).threshold
    tss = [float(np.mean(score[y == 1] >= threshold) + np.mean(score[y == 0] < threshold) - 1.0) for score, y in means]
    return {"auc": float(np.mean(aucs)), "tss": float(np.mean(tss)), "threshold": float(threshold)}


def aggregate_stage(leaf_root: str | Path, bundle_root: str | Path, tasks: Sequence[Mapping[str, Any]], stage: str) -> dict[str, Any]:
    _require(tasks and all(t["stage"] == stage for t in tasks), "stage task mismatch")
    _require(len(tasks) == (960 if stage == "screen" else 480), "stage workload count mismatch")
    rows: dict[tuple[str, str], list[tuple[str, int, np.ndarray, np.ndarray]]] = {}
    bundle_paths = { (m["target"], m["held_fold"]): p for p in Path(bundle_root).glob("*.npz") for m in [validate_private_bundle(p)] }
    for task in tasks:
        identity = {k: task[k] for k in _LEAF_KEYS}; leaf = Path(leaf_root) / leaf_identity(identity); validate_leaf(leaf, identity); scores = np.load(leaf / "scores.npy", allow_pickle=False)
        with np.load(bundle_paths[(task["target"], task["held_fold"])], allow_pickle=False) as payload: y = np.asarray(payload["y_held"], dtype=np.float32)
        _require(len(y) == len(scores), "score/label alignment mismatch")
        rows.setdefault((task["architecture"], task["target"]), []).append((task["held_fold"], int(task["base_seed"]), scores, y))
    metrics: dict[str, dict[str, dict[str, float]]] = {}
    expected_per = len(config_seeds := {int(t["base_seed"]) for t in tasks}) * len(FOLDS)
    for (architecture, target), values in rows.items():
        _require(len(values) == expected_per and len({(f, s) for f, s, _, _ in values}) == expected_per, "seed/fold cartesian coverage mismatch")
        metrics.setdefault(architecture, {})[target] = _metrics_for_rows(values)
    return {"stage": stage, "metrics": metrics, "ranking": rank_architectures(metrics), "loso": _loso(metrics)}


def _loso(metrics: Mapping[str, Mapping[str, Mapping[str, float]]]) -> dict[str, Any]:
    if not metrics: return {"winners": {}, "instability": False}
    species = sorted(next(iter(metrics.values())))
    full_winner = rank_architectures(metrics)[0]
    winners = {omitted: rank_architectures({a: {s: metrics[a][s] for s in metrics[a] if s != omitted} for a in metrics})[0] for omitted in species}
    return {"winners": winners, "instability": any(winner != full_winner for winner in winners.values())}


def _replay(screen_tasks: Sequence[Mapping[str, Any]], shortlist_tasks: Sequence[Mapping[str, Any]], screen_ranking: Sequence[str], leaf_root: str | Path) -> int:
    pairs = 0
    shortlist_set = {(t["target"], t["held_fold"], t["architecture"]): t for t in shortlist_tasks if t["base_seed"] == 31031}
    for task in screen_tasks:
        if task["base_seed"] != 31031 or task["architecture"] not in screen_ranking[:4]: continue
        key = (task["target"], task["held_fold"], task["architecture"]); _require(key in shortlist_set, "shortlist replay pair missing")
        a_identity = {k: task[k] for k in _LEAF_KEYS}; btask = shortlist_set[key]; b_identity = {k: btask[k] for k in _LEAF_KEYS}
        a = Path(leaf_root) / leaf_identity(a_identity); b = Path(leaf_root) / leaf_identity(b_identity)
        validate_leaf(a, a_identity); validate_leaf(b, b_identity); assert_seed_replay_identity(a, b); pairs += 1
    _require(pairs == 160, f"expected 160 replay pairs, got {pairs}"); return pairs


def _collect_result(config: SelectionConfig, bundle_root: str | Path, leaf_root: str | Path, *, repo_root: str | Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    root = Path(repo_root or config.source_path.parents[1])
    validate_authorities(config, root)
    runtime_attestation(config.raw["runtime"], strict=True)
    manifests = validate_private_bundles(bundle_root, config=config, repo_root=root)
    screen_tasks = expected_tasks(config, "screen", leaf_root, bundle_root, repo_root=root)
    screen_state = status(leaf_root, screen_tasks)
    _require(screen_state["complete"] == 960 and screen_state["invalid"] == 0, "screen leaves incomplete or invalid")
    screen = aggregate_stage(leaf_root, bundle_root, screen_tasks, "screen")
    shortlist_tasks = expected_tasks(config, "shortlist", leaf_root, bundle_root, screen["ranking"][:config.shortlist_size], repo_root=root)
    shortlist_state = status(leaf_root, shortlist_tasks)
    _require(shortlist_state["complete"] == 480 and shortlist_state["invalid"] == 0, "shortlist leaves incomplete or invalid")
    shortlist = aggregate_stage(leaf_root, bundle_root, shortlist_tasks, "shortlist")
    repeats = _replay(screen_tasks, shortlist_tasks, screen["ranking"], leaf_root)
    result = {"screen": screen, "shortlist": shortlist, "final_winner": shortlist["ranking"][0], "repeat_pairs": repeats, "counts": {"screen": 960, "shortlist": 480, "total": 1440}}
    return result, manifests, screen_tasks, shortlist_tasks


def run_pipeline(config: SelectionConfig, bundle_root: str | Path, leaf_root: str | Path, tracked_path: str | Path | None = None, *, workers: int | None = None, repo_root: str | Path | None = None) -> dict[str, Any]:
    _require(tracked_path is None, "run is private; finalize writes tracked evidence")
    root = Path(repo_root or config.source_path.parents[1])
    validate_authorities(config, root)
    runtime_attestation(config.raw["runtime"], strict=True)
    validate_private_bundles(bundle_root, config=config, repo_root=root)
    screen_tasks = expected_tasks(config, "screen", leaf_root, bundle_root, repo_root=root)
    run_tasks(screen_tasks, workers=workers or config.workers)
    screen = aggregate_stage(leaf_root, bundle_root, screen_tasks, "screen")
    shortlist_tasks = expected_tasks(config, "shortlist", leaf_root, bundle_root, screen["ranking"][:config.shortlist_size], repo_root=root)
    run_tasks(shortlist_tasks, workers=workers or config.workers)
    result, _, _, _ = _collect_result(config, bundle_root, leaf_root, repo_root=root)
    return result


def _aggregate_receipt(result: Mapping[str, Any], config: SelectionConfig, manifests: Sequence[Mapping[str, Any]], screen_tasks: Sequence[Mapping[str, Any]], shortlist_tasks: Sequence[Mapping[str, Any]], runtime: Mapping[str, Any], *, repo_root: str | Path | None = None) -> dict[str, Any]:
    config_digest = _digest_file(config.source_path)
    authority_digests = validate_authorities(config, repo_root or config.source_path.parents[1])
    source_binding_digest = next(iter({m["source_binding_digest"] for m in manifests}))
    bundle_digest = _digest_bytes(_canonical(sorted(m["bundle_digest"] for m in manifests)).encode())
    leaf_records = []
    for task in [*screen_tasks, *shortlist_tasks]:
        identity = {k: task[k] for k in _LEAF_KEYS}
        leaf = Path(task["leaf_root"]) / leaf_identity(identity)
        envelope = json.loads((leaf / "metadata.json").read_text(encoding="utf-8"))
        leaf_records.append({"identity": identity, "scores_sha256": envelope["scores_sha256"], "receipt": envelope["receipt"]})
    leaf_digest = _digest_bytes(_canonical(sorted(leaf_records, key=lambda row: _canonical(row))).encode())
    return {"schema_version": "goal033-aggregate-v2", "success": True, "final_winner": result["final_winner"], "screen_ranking": result["screen"]["ranking"], "shortlist_ranking": result["shortlist"]["ranking"], "screen_metrics": result["screen"]["metrics"], "shortlist_metrics": result["shortlist"]["metrics"], "loso": result["shortlist"]["loso"], "config_digest": config_digest, "authority_digests": authority_digests, "runtime_attestation": dict(runtime), "runtime_attestation_digest": runtime_digest(runtime), "source_binding_digest": source_binding_digest, "bundle_inventory_digest": bundle_digest, "leaf_inventory_digest": leaf_digest, "screen_logical_evaluations": 960, "shortlist_logical_evaluations": 480, "logical_evaluations": 1440, "physical_fits": 2880, "workers": 3, "route": "mac_cpu", "repeat_pairs": result["repeat_pairs"], "expected_repeat_pairs": 160, "outer_attempted": 0, "outer_opened": 0}


def finalize(config: SelectionConfig, leaf_root: str | Path, bundle_root: str | Path, tracked_path: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    result, manifests, screen_tasks, shortlist_tasks = _collect_result(config, bundle_root, leaf_root, repo_root=repo_root)
    runtime = runtime_attestation(config.raw["runtime"], strict=True)
    receipt = _aggregate_receipt(result, config, manifests, screen_tasks, shortlist_tasks, runtime, repo_root=repo_root)
    output = Path(tracked_path); output.parent.mkdir(parents=True, exist_ok=True); temporary = output.with_suffix(output.suffix + ".tmp"); temporary.write_text(_canonical(receipt) + "\n", encoding="utf-8"); os.replace(temporary, output); return receipt


def validate_all(config: SelectionConfig, bundle_root: str | Path, leaf_root: str | Path, tracked_path: str | Path | None = None, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    result, manifests, screen_tasks, shortlist_tasks = _collect_result(config, bundle_root, leaf_root, repo_root=repo_root)
    expected = _aggregate_receipt(result, config, manifests, screen_tasks, shortlist_tasks, runtime_attestation(config.raw["runtime"], strict=True), repo_root=repo_root)
    if tracked_path is not None:
        path = Path(tracked_path); _require(path.is_file(), "tracked aggregate receipt missing"); actual = json.loads(path.read_text()); _require(actual == expected, "tracked aggregate receipt mismatch")
    return expected


def _cli() -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.architecture_runner"); parser.add_argument("command", choices=("plan", "export", "validate-bundles", "run", "status", "finalize", "validate")); parser.add_argument("--config", default="config/dsdm_architecture_selection.json"); parser.add_argument("--bundles", default="data/processed/dsdm/goal033-architecture-selection/private/bundles"); parser.add_argument("--leaves", default="data/processed/dsdm/goal033-architecture-selection/private/leaves"); parser.add_argument("--tracked", default="evidence/dsdm_architecture_selection/goal033/aggregate.json"); parser.add_argument("--foundation-root", default="."); parser.add_argument("--goal032-config", default="config/dsdm_real_compute_calibration.json"); args = parser.parse_args(); config = load_selection_config(args.config); root = Path(args.config).parents[1]
    if args.command == "plan": print(json.dumps(build_task_plan(config), sort_keys=True)); return 0
    if args.command == "export":
        validate_authorities(config, root)
        _require(config.raw["runtime"]["export_environment"] == "repository_locked_uv", "export environment drift")
        expected_goal032_path = (root / config.raw["authorities"]["goal032_config"]["path"]).resolve()
        _require(Path(args.goal032_config).resolve() == expected_goal032_path, "Goal032 config path is not the bound authority")
        from .real_data import CaseSpec, bind_case_from_foundation
        from .compute_canary import load_config as load_goal032_config
        goal032 = load_goal032_config(expected_goal032_path)
        with tempfile.TemporaryDirectory(prefix="goal033-export-") as temp:
            bundles = []
            for target in config.species:
                for held_fold in config.folds:
                    case = CaseSpec(f"goal033-{target}-{held_fold}", target, held_fold, "resmlp00", 31031)
                    bundles.append(bind_case_from_foundation(args.foundation_root, goal032, case, Path(temp) / f"{target}-{held_fold}.npz"))
            paths = export_private_bundles(bundles, args.bundles, config=config)
        print(json.dumps({"bundles": len(paths)}, sort_keys=True)); return 0
    if args.command == "validate-bundles": print(json.dumps({"bundles": len(validate_private_bundles(args.bundles, config=config, repo_root=root))}, sort_keys=True)); return 0
    if args.command == "run": print(json.dumps(run_pipeline(config, args.bundles, args.leaves, repo_root=root), sort_keys=True)); return 0
    if args.command == "finalize": print(json.dumps(finalize(config, args.leaves, args.bundles, args.tracked, repo_root=root), sort_keys=True)); return 0
    if args.command == "validate": print(json.dumps(validate_all(config, args.bundles, args.leaves, args.tracked, repo_root=root), sort_keys=True)); return 0
    if args.command == "status":
        print(json.dumps(combined_status(config, args.bundles, args.leaves, repo_root=root), sort_keys=True)); return 0
    raise RunnerError("unsupported command")


if __name__ == "__main__":
    raise SystemExit(_cli())
