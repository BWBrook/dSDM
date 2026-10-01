#!/usr/bin/env python3
"""Recover the missing selected shallow-ANN epochs for Goal052.

This is deliberately a retained-only, single-procedure helper.  It consumes
the accepted Goal051 endpoint and its saved prediction parquet, then replays
one already selected candidate/method through Goal051's ``_prepared_folds``
and ``_evaluate`` functions.  It never searches candidates and never opens
outer response data.  The default command is a read-only inventory plan;
``--run`` performs exactly one target/method procedure.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.metadata
import json
import os
import platform
import socket
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "evidence/seawfb_dsdm/goal052/outer-inventory-20260929.json"
GOAL051_SUMMARY = ROOT / "evidence/seawfb_conventional/goal051/summary.json"
GOAL051_CONFIG = ROOT / "config/goal051_seawfb_conventional.json"
RECOVERY_DIR = ROOT / "data/processed/dsdm/goal052-seawfb-dsdm-experiment/ann-epoch-recovery"
METHODS = ("ordinary", "q_full")
ANN_FAMILY = "shallow_ann"
TARGET_FRACTION = 100
EXPECTED_TARGETS = 40
EXPECTED_EPOCHS = 25


class RecoveryError(RuntimeError):
    """A fail-closed recovery or binding error."""


class PredictionMismatch(RecoveryError):
    """Numerical mismatch with machine-readable diagnostics."""

    def __init__(self, message: str, details: Mapping[str, Any]):
        super().__init__(message)
        self.details = dict(details)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryError(message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"invalid_json:{path}") from exc
    _require(isinstance(value, dict), f"json_not_object:{path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return sha256_file(path)


def _slug(value: str) -> str:
    return "_".join(value.lower().split())


def _script_hash() -> str:
    return sha256_file(Path(__file__).resolve())


def _runtime_metadata(host: str | None = None) -> dict[str, Any]:
    def version(name: str) -> str | None:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None

    try:
        import torch
        torch_threads = {"threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads()}
    except (ImportError, RuntimeError):
        torch_threads = None
    try:
        from threadpoolctl import threadpool_info
        thread_pools = threadpool_info()
    except ImportError:
        thread_pools = []
    return {
        "host": host or socket.gethostname(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "torch": version("torch"),
        "scikit_learn": version("scikit-learn"),
        "scipy": version("scipy"),
        "pyarrow": version("pyarrow"),
        "torch_thread_settings": torch_threads,
        "threadpool_info": thread_pools,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


@contextlib.contextmanager
def _procedure_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # The kernel releases this lock on process termination. Keep the inode:
    # unlinking a flock file would permit concurrent locks on different inodes.
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecoveryError(f"procedure_locked:{path}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()} host={socket.gethostname()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _inventory(path: Path = INVENTORY) -> dict[str, Any]:
    value = _read_json(path)
    _require(value.get("schema_version") == "goal052-outer-inventory-v1", "inventory_schema_mismatch")
    _require(value.get("outer_response_rows_read") == 0, "inventory_outer_response_access")
    records = value.get("conventional_target100", {}).get("records")
    _require(isinstance(records, list), "inventory_conventional_records_missing")
    ann = [item for item in records if item.get("ordinary", {}).get("family") == ANN_FAMILY]
    _require(len(ann) == EXPECTED_TARGETS, f"ann_target_count:{len(ann)}")
    for item in ann:
        _require(item.get("q_full", {}).get("family") == ANN_FAMILY, f"q_family_mismatch:{item.get('target')}")
        for method in METHODS:
            spec = item[method]
            _require(spec.get("candidate_id"), f"candidate_missing:{item.get('target')}:{method}")
            _require(spec.get("seed_labels") == [f"seed0{i}" for i in range(5)], f"seed_schedule_mismatch:{item.get('target')}:{method}")
    return value


def _ann_records(inventory: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["target"]: item
        for item in inventory["conventional_target100"]["records"]
        if item["ordinary"].get("family") == ANN_FAMILY
    }


def _smallest_row_count_candidate(root: Path, records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """Read only accepted endpoint JSON metadata for a bounded first replay."""

    endpoint_dir = root / "data/processed/dsdm/goal051-seawfb-conventional-benchmark-v4/endpoints"
    candidates = []
    for target in records:
        path = endpoint_dir / f"{_slug(target)}_target100.json"
        if not path.is_file():
            continue
        result = _read_json(path)
        rows = result.get("prediction_rows")
        if type(rows) is int and rows > 0:
            candidates.append((rows, target))
    if not candidates:
        return None
    rows, target = min(candidates, key=lambda value: (value[0], value[1]))
    return {"target": target, "prediction_rows": rows, "methods": list(METHODS), "source": "accepted_endpoint_json_metadata"}


def build_plan(inventory_path: Path = INVENTORY, root: Path = ROOT) -> dict[str, Any]:
    """Return the 80-procedure inventory without reading accepted payloads."""

    inventory = _inventory(inventory_path)
    records = _ann_records(inventory)
    procedures = [
        {
            "target": target,
            "target_fraction": TARGET_FRACTION,
            "method": method,
            "family": ANN_FAMILY,
            "candidate_id": records[target][method]["candidate_id"],
            "seed_labels": list(records[target][method]["seed_labels"]),
            "best_epoch_range": records[target][method]["best_epoch_range"],
        }
        for target in sorted(records)
        for method in METHODS
    ]
    return {
        "schema_version": "goal052-ann-epoch-recovery-plan-v1",
        "status": "read_only_inventory",
        "outer_response_rows_read": 0,
        "target_count": len(records),
        "procedure_count": len(procedures),
        "procedures": procedures,
        "smallest_row_count_candidate": _smallest_row_count_candidate(Path(root), records),
        "recovery_script_sha256": _script_hash(),
    }


def _accepted_binding(root: Path, inventory: Mapping[str, Any], target: str, method: str) -> dict[str, Any]:
    """Check all accepted identity and endpoint bindings before fitting."""

    _require(method in METHODS, f"method_invalid:{method}")
    records = _ann_records(inventory)
    _require(target in records, f"target_not_selected_ann:{target}")
    summary = _read_json(root / GOAL051_SUMMARY.relative_to(ROOT))
    _require(summary.get("outer_response_rows_read") == 0 and summary.get("outer_predictor_rows_used") == 0, "accepted_outer_access")
    accepted_identity = summary.get("identity")
    expected_identity = inventory["inputs"]["accepted_goal052_identity"]["goal051_identity"]
    _require(accepted_identity == expected_identity, "accepted_identity_inventory_mismatch")
    _require(sha256_file(root / GOAL051_SUMMARY.relative_to(ROOT)) == inventory["inputs"]["sha256"]["goal051_summary"], "accepted_summary_hash_mismatch")

    from dsdm_phase1 import goal051_seawfb_conventional as goal051

    config = goal051._config(root)
    current_identity = goal051._identity(root)
    _require(current_identity == accepted_identity, "current_identity_mismatch")
    manifest = _read_json(root / goal051.MANIFEST_PATH)
    for binding_key, relative_path in (("cells", goal051.CELLS_PATH), ("memberships", goal051.MEMBERSHIPS_PATH)):
        path = root / relative_path
        _require(path.is_file(), f"accepted_{binding_key}_missing")
        _require(manifest.get("bindings", {}).get(binding_key) == sha256_file(path), f"accepted_{binding_key}_hash_mismatch")
    result_path, prediction_path = goal051._task_paths(root, config, target, TARGET_FRACTION)
    _require(result_path.is_file() and prediction_path.is_file(), "accepted_endpoint_missing")
    result = _read_json(result_path)
    _require(result.get("identity") == accepted_identity, "endpoint_identity_mismatch")
    _require(result.get("target") == target and result.get("target_fraction") == TARGET_FRACTION, "endpoint_key_mismatch")
    _require(result.get("prediction_sha256") == sha256_file(prediction_path), "endpoint_prediction_hash_mismatch")
    endpoint_name = f"{_slug(target)}_target{TARGET_FRACTION}"
    accepted_private = {row.get("endpoint"): row for row in summary.get("private_outputs", [])}
    private = accepted_private.get(endpoint_name)
    _require(private is not None, "accepted_private_endpoint_missing")
    _require(private.get("result_sha256") == sha256_file(result_path), "accepted_result_binding_mismatch")
    _require(private.get("prediction_sha256") == result["prediction_sha256"], "accepted_prediction_binding_mismatch")
    selected = result.get("families", {}).get(ANN_FAMILY, {}).get("selected")
    q_selected = result.get("q_linear", {}).get("full")
    selected_metadata = selected if method == "ordinary" else q_selected
    _require(isinstance(selected_metadata, Mapping), f"accepted_{method}_selection_missing")
    spec = records[target][method]
    _require(selected_metadata.get("family", ANN_FAMILY) == ANN_FAMILY, f"accepted_{method}_family_mismatch")
    _require(selected_metadata.get("candidate_id") == spec["candidate_id"], f"accepted_{method}_candidate_mismatch")
    _require(selected_metadata.get("seed_labels") == spec["seed_labels"], f"accepted_{method}_seed_schedule_mismatch")
    return {
        "summary": summary,
        "identity": accepted_identity,
        "inventory_record": records[target],
        "method_spec": records[target][method],
        "config": config,
        "result": result,
        "result_path": result_path,
        "prediction_path": prediction_path,
        "prediction_sha256": result["prediction_sha256"],
        "manifest": manifest,
    }


def rounded_median_epochs(epochs: Sequence[int]) -> int:
    """Apply the frozen 25-value selected-epoch median convention."""

    values = list(epochs)
    _require(len(values) == EXPECTED_EPOCHS, f"epoch_count:{len(values)}")
    _require(all(type(value) is int and 1 <= value <= 300 for value in values), "epoch_receipt_invalid")
    median = statistics.median(values)
    _require(float(median).is_integer(), f"median_not_integer:{median}")
    return int(median)


def _accepted_prediction_frame(binding: Mapping[str, Any], method: str):
    import pyarrow.parquet as pq

    frame = pq.read_table(binding["prediction_path"]).to_pandas()
    spec = binding["method_spec"]
    expected_method = "family_selected" if method == "ordinary" else "q_linear"
    expected_auxiliary = "none" if method == "ordinary" else "full"
    subset = frame[
        (frame.target == binding["result"]["target"])
        & (frame.target_fraction == TARGET_FRACTION)
        & (frame.method == expected_method)
        & (frame.family == ANN_FAMILY)
        & (frame.candidate_id == spec["candidate_id"])
        & (frame.auxiliary_size == expected_auxiliary)
    ]
    _require(len(subset) > 0, "accepted_prediction_group_missing")
    _require(not subset.duplicated(["fold", "cell_id"]).any(), "accepted_prediction_duplicate_cells")
    _require(set(subset.fold.astype(int)) == set(range(5)), "accepted_prediction_fold_coverage")
    return subset


def _compare_predictions(binding: Mapping[str, Any], method: str, prepared: Sequence[Mapping[str, Any]], evaluated: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    accepted = _accepted_prediction_frame(binding, method)
    regenerated = {int(item["fold"]): item for item in evaluated.get("folds", [])}
    _require(set(regenerated) == set(range(5)), "regenerated_fold_coverage")
    prepared_folds = [int(item["fold"]) for item in prepared]
    _require(len(prepared_folds) == 5 and set(prepared_folds) == set(range(5)), "prepared_fold_coverage")
    seed_labels = list(binding["method_spec"]["seed_labels"])
    fit_records = list(evaluated.get("fit_records", []))
    _require(len(fit_records) == 25, f"fit_record_count:{len(fit_records)}")
    fit_keys = {(int(item.get("fold", -1)), item.get("seed_label")) for item in fit_records}
    _require(fit_keys == {(fold, seed) for fold in range(5) for seed in seed_labels}, "fit_record_coverage")
    predictions: dict[str, np.ndarray] = {}
    receipts = []
    fold_identities = []
    for item in prepared:
        fold = int(item["fold"])
        rows = item["validation_rows"]
        part = accepted[accepted.fold.astype(int) == fold]
        _require(tuple(part.cell_id.astype(str)) == tuple(rows.cell_ids), f"accepted_cell_coverage:{fold}")
        _require(np.array_equal(part.y.to_numpy(dtype=np.int8), np.asarray(rows.y, dtype=np.int8)), f"accepted_label_coverage:{fold}")
        current = regenerated[fold]
        _require(tuple(current["cell_ids"]) == tuple(rows.cell_ids), f"regenerated_cell_coverage:{fold}")
        _require(np.array_equal(np.asarray(current["y"], dtype=np.int8), np.asarray(rows.y, dtype=np.int8)), f"regenerated_label_coverage:{fold}")
        _require(all(seed in current.get("scores_by_seed", {}) for seed in seed_labels), f"regenerated_seed_coverage:{fold}")
        regenerated_mean = np.mean(np.vstack([np.asarray(current["scores_by_seed"][seed], dtype=np.float64) for seed in seed_labels]), axis=0)
        expected_scores = part.score.to_numpy(dtype=np.float64)
        observed_scores = np.asarray(current["score"], dtype=np.float64)
        if not np.array_equal(observed_scores, regenerated_mean):
            delta = np.abs(observed_scores - regenerated_mean) if observed_scores.shape == regenerated_mean.shape else np.array([], dtype=np.float64)
            raise PredictionMismatch(
                f"regenerated_seed_average_mismatch:{fold}",
                {"fold": fold, "max_abs_score_delta": float(np.max(delta)) if delta.size else None, "mismatch_count": int(np.count_nonzero(delta)) if delta.size else None},
            )
        if not np.array_equal(observed_scores, expected_scores):
            delta = np.abs(observed_scores - expected_scores) if observed_scores.shape == expected_scores.shape else np.array([], dtype=np.float64)
            raise PredictionMismatch(
                f"prediction_mismatch:{fold}",
                {"fold": fold, "max_abs_score_delta": float(np.max(delta)) if delta.size else None, "mismatch_count": int(np.count_nonzero(delta)) if delta.size else None},
            )
        fold_identities.append({"fold": fold, "cell_ids": list(rows.cell_ids), "row_count": len(rows.cell_ids)})
        for seed in seed_labels:
            seed_scores = np.asarray(current["scores_by_seed"][seed], dtype=np.float64)
            predictions.setdefault(seed, np.array([], dtype=np.float64))
            predictions[seed] = np.concatenate([predictions[seed], seed_scores])
    for item in fit_records:
        epoch = item.get("best_epoch")
        _require(type(epoch) is int and 1 <= epoch <= 300, "fit_epoch_invalid")
        _require(item.get("physical_fits") == 2, "fit_physical_count_invalid")
        _require(item.get("converged") is True, "fit_not_converged")
        receipt = _jsonable(item)
        receipt.update({"fold": int(item["fold"]), "seed_label": item["seed_label"], "selected_epoch": epoch})
        receipts.append(receipt)
    median = rounded_median_epochs([item["selected_epoch"] for item in receipts])
    return {"fit_receipts": receipts, "fold_identities": fold_identities, "median_rounded_epoch": median}, predictions


def _checkpoint_base(root: Path, target: str, method: str) -> Path:
    return root / RECOVERY_DIR.relative_to(ROOT) / f"{_slug(target)}_{method}.json"


def _next_checkpoint(base: Path) -> Path:
    if not base.exists():
        return base
    index = 2
    while True:
        path = base.with_name(f"{base.stem}.attempt{index:04d}{base.suffix}")
        if not path.exists():
            return path
        index += 1


def _evaluated_payload(base: Path, evaluated: Mapping[str, Any]) -> tuple[Path, str]:
    arrays: dict[str, np.ndarray] = {}
    for fold in evaluated.get("folds", []):
        fold_id = int(fold["fold"])
        arrays[f"fold{fold_id}__score"] = np.asarray(fold["score"], dtype=np.float64)
        arrays[f"fold{fold_id}__y"] = np.asarray(fold["y"], dtype=np.int8)
        for seed, scores in fold.get("scores_by_seed", {}).items():
            arrays[f"fold{fold_id}__seed_{seed}"] = np.asarray(scores, dtype=np.float64)
    path = base.with_suffix(".evaluated.npz")
    return path, _atomic_npz(path, arrays)


def _successful_checkpoint(root: Path, base: Path, binding: Mapping[str, Any], method: str) -> dict[str, Any] | None:
    paths = [base, *sorted(base.parent.glob(f"{base.stem}.attempt*{base.suffix}"))]
    for path in paths:
        if not path.is_file():
            continue
        value = _read_json(path)
        if value.get("status") == "success":
            _require(value.get("accepted_prediction_sha256") == binding["prediction_sha256"], "successful_checkpoint_binding_mismatch")
            _require(value.get("identity") == binding["identity"], "successful_checkpoint_identity_mismatch")
            _require(value.get("target") == binding["result"]["target"] and value.get("target_fraction") == TARGET_FRACTION and value.get("method") == method and value.get("family") == ANN_FAMILY, "successful_checkpoint_key_mismatch")
            _require(value.get("candidate_id") == binding["method_spec"]["candidate_id"], "successful_checkpoint_candidate_mismatch")
            _require(value.get("seed_labels") == binding["method_spec"]["seed_labels"], "successful_checkpoint_seed_mismatch")
            _require(value.get("recovery_script_sha256") == _script_hash(), "successful_checkpoint_helper_mismatch")
            payload = root / value.get("recovered_predictions_npz", "")
            _require(payload.is_file() and sha256_file(payload) == value.get("recovered_predictions_sha256"), "successful_checkpoint_payload_mismatch")
            return value
    return None


def recover_one(
    root: Path,
    target: str,
    method: str,
    *,
    inventory: Mapping[str, Any] | None = None,
    store: Any | None = None,
    prepared_folds: Callable[..., Sequence[Mapping[str, Any]]] | None = None,
    evaluator: Callable[..., Mapping[str, Any]] | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    """Recover one selected target/method and write an atomic private receipt."""

    root = Path(root)
    inventory = dict(inventory or _inventory(root / INVENTORY.relative_to(ROOT)))
    base = _checkpoint_base(root, target, method)
    binding: dict[str, Any] | None = None
    evaluated: Mapping[str, Any] | None = None
    evaluated_payload_path: Path | None = None
    evaluated_payload_sha256: str | None = None
    attempt_path: Path | None = None
    lock_path = base.with_suffix(".lock")
    with _procedure_lock(lock_path):
        try:
            binding = _accepted_binding(root, inventory, target, method)
            previous = _successful_checkpoint(root, base, binding, method)
            if previous is not None:
                return previous
            from dsdm_phase1 import goal051_seawfb_conventional as goal051

            config = binding["config"]
            if store is None:
                store = goal051.SeawfbStore(root)
            if prepared_folds is None:
                prepared_folds = goal051._prepared_folds
            if evaluator is None:
                evaluator = goal051._evaluate
            auxiliary = None if method == "ordinary" else "full"
            prepared = prepared_folds(root, store, config, target, TARGET_FRACTION, auxiliary)
            evaluated = evaluator(config, target, TARGET_FRACTION, ANN_FAMILY, binding["method_spec"]["candidate_id"], binding["method_spec"]["seed_labels"], prepared)
            attempt_path = _next_checkpoint(base)
            evaluated_payload_path, evaluated_payload_sha256 = _evaluated_payload(attempt_path, evaluated)
            fit_result, predictions = _compare_predictions(binding, method, prepared, evaluated)
            seed_ints = {}
            for receipt in fit_result["fit_receipts"]:
                expected = int(goal051._fit_seed(config, target, TARGET_FRACTION, receipt["fold"], ANN_FAMILY, binding["method_spec"]["candidate_id"], receipt["seed_label"]))
                receipt["seed"] = expected
                seed_ints[f"fold{receipt['fold']}:{receipt['seed_label']}"] = expected
            prediction_path = attempt_path.with_suffix(".predictions.npz")
            prediction_sha256 = _atomic_npz(prediction_path, predictions)
            runtime = _runtime_metadata(host)
            runtime["config_sha256"] = binding["identity"]["config_sha256"]
            runtime["source_identity"] = binding["identity"]
            receipt = {
                "schema_version": "goal052-ann-epoch-recovery-v1",
                "status": "success",
                "target": target,
                "target_fraction": TARGET_FRACTION,
                "method": method,
                "family": ANN_FAMILY,
                "candidate_id": binding["method_spec"]["candidate_id"],
                "seed_labels": list(binding["method_spec"]["seed_labels"]),
                "seed_integers": seed_ints,
                "fit_receipts": fit_result["fit_receipts"],
                "fold_identities": fit_result["fold_identities"],
                "prediction_seed_labels": list(predictions),
                "median_rounded_epoch": fit_result["median_rounded_epoch"],
                "accepted_prediction_sha256": binding["prediction_sha256"],
                "recovered_predictions_npz": str(prediction_path.relative_to(root)),
                "recovered_predictions_sha256": prediction_sha256,
                "identity": binding["identity"],
                "runtime": runtime,
                "recovery_script_sha256": _script_hash(),
                "outer_response_rows_read": 0,
            }
            _atomic_json(attempt_path, receipt)
            return receipt
        except Exception as exc:
            failed = {
                "schema_version": "goal052-ann-epoch-recovery-v1",
                "status": "failed",
                "target": target,
                "target_fraction": TARGET_FRACTION,
                "method": method,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "runtime": _runtime_metadata(host),
                "recovery_script_sha256": _script_hash(),
                "outer_response_rows_read": 0,
            }
            if binding is not None:
                failed["identity"] = binding.get("identity")
                failed["accepted_prediction_sha256"] = binding.get("prediction_sha256")
            if evaluated is not None:
                failed["evaluated_fit_records"] = _jsonable(evaluated.get("fit_records", []))
            if evaluated_payload_path is not None and evaluated_payload_sha256 is not None:
                failed["evaluated_predictions_npz"] = str(evaluated_payload_path.relative_to(root))
                failed["evaluated_predictions_sha256"] = evaluated_payload_sha256
            if isinstance(exc, PredictionMismatch):
                failed["diagnostics"] = exc.details
            try:
                _atomic_json(attempt_path or _next_checkpoint(base), failed)
            except Exception:
                pass
            if isinstance(exc, RecoveryError):
                raise
            raise RecoveryError(f"recovery_failed:{type(exc).__name__}:{exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path, default=None)
    parser.add_argument("--run", nargs=2, metavar=("TARGET", "METHOD"), help="run exactly one target and ordinary/q_full procedure")
    args = parser.parse_args(argv)
    inventory_path = args.inventory or (args.root / INVENTORY.relative_to(ROOT))
    if args.run is None:
        print(json.dumps(build_plan(inventory_path, args.root), indent=2, sort_keys=True))
        return 0
    target, method = args.run
    result = recover_one(args.root, target, method, inventory=_inventory(inventory_path))
    print(json.dumps({key: result[key] for key in ("status", "target", "method", "median_rounded_epoch") if key in result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
