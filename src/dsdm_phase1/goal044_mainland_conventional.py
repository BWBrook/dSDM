"""Goal 044 mainland conventional benchmark and frozen community control."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import platform
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from .mainland_modeling import (
    MainlandModelingError,
    MainlandStore,
    ResponseRows,
    endpoint_indices,
    fit_q_linear,
    make_batch,
    require,
    sha256_file,
    slug,
    stable_seed,
    subset_batch,
    summarize_oof,
)
from .model_adapters import CANONICAL_CANDIDATES, ModelAdapterError, build_adapter
from .modeling_contract import FeatureBatch, canonical_json


CONFIG_PATH = Path("config/goal044_mainland_conventional.json")
PRIVATE_ROOT = Path("data/processed/dsdm/goal044-mainland-conventional")
SUMMARY_PATH = Path("evidence/mainland_conventional/goal044/summary.json")
CANARY_PATH = Path("evidence/mainland_conventional/goal044/canary.json")
SOURCE_PATHS = (
    Path("src/dsdm_phase1/mainland_modeling.py"),
    Path("src/dsdm_phase1/goal044_mainland_conventional.py"),
)
PREDICTION_SCHEMA = pa.schema(
    [
        pa.field("target", pa.string(), nullable=False),
        pa.field("fraction", pa.int8(), nullable=False),
        pa.field("ladder", pa.string(), nullable=False),
        pa.field("fold", pa.int8(), nullable=False),
        pa.field("cell_id", pa.string(), nullable=False),
        pa.field("y", pa.int8(), nullable=False),
        pa.field("method", pa.string(), nullable=False),
        pa.field("family", pa.string(), nullable=False),
        pa.field("candidate_id", pa.string(), nullable=False),
        pa.field("score", pa.float64(), nullable=False),
    ]
)


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MainlandModelingError(f"invalid_json:{path}") from exc
    require(isinstance(value, Mapping), f"invalid_json_object:{path}")
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    require(not temporary.exists(), f"orphaned_temporary:{temporary}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _atomic_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    require(not temporary.exists(), f"orphaned_temporary:{temporary}")
    pq.write_table(table.cast(PREDICTION_SCHEMA), temporary, compression="zstd")
    os.replace(temporary, path)


def _config(root: Path) -> Mapping[str, Any]:
    return _read_json(root / CONFIG_PATH)


def _source_digest(root: Path) -> str:
    return hashlib.sha256(
        canonical_json({str(path): sha256_file(root / path) for path in SOURCE_PATHS}).encode()
    ).hexdigest()


def _identity(root: Path) -> dict[str, str]:
    return {
        "config_sha256": sha256_file(root / CONFIG_PATH),
        "source_sha256": _source_digest(root),
        "goal043_manifest_sha256": sha256_file(root / "metadata/goal043_manifest.json"),
    }


def validate_inputs(root: Path) -> dict[str, Any]:
    config = _config(root)
    require(config.get("schema_version") == "goal044-contract-v1", "goal044_schema_drift")
    for binding in config["bindings"].values():
        path = root / binding["path"]
        require(path.is_file() and sha256_file(path) == binding["sha256"], f"binding_drift:{binding['path']}")
    require(len(config["scope"]["targets"]) == 5, "target_count_drift")
    require(len(config["scope"]["response_heads"]) == 20, "response_head_count_drift")
    require(set(config["scope"]["targets"]) <= set(config["scope"]["response_heads"]), "target_head_binding_drift")
    require(config["scope"]["tasmania_evaluation"] == "sealed", "tasmania_seal_drift")
    require(config["privacy"]["tasmania_response_rows_read"] == 0, "tasmania_response_access_drift")
    require(config["privacy"]["tasmania_predictor_rows_used"] == 0, "tasmania_predictor_access_drift")

    goal043 = _read_json(root / "metadata/goal043_manifest.json")
    roles = goal043["outputs"]["private_output_roles"]
    assignment = root / "data/raw/goal043/mainland_cell_partitions.parquet"
    responses = root / "data/raw/goal043/split_responses.parquet"
    predictors = root / "data/raw/goal041/predictor_substrate.parquet"
    require(assignment.is_file() and sha256_file(assignment) == roles["mainland_cell_partitions"]["sha256"], "assignment_receipt_drift")
    require(responses.is_file() and sha256_file(responses) == roles["split_responses"]["sha256"], "response_receipt_drift")
    require(predictors.is_file(), "predictor_substrate_missing")
    response_heads = set(
        pc.unique(pq.read_table(responses, columns=["target"])["target"]).to_pylist()
    )
    require(response_heads == set(config["scope"]["response_heads"]), "response_head_inventory_drift")
    return {
        "status": "goal044_inputs_valid",
        "identity": _identity(root),
        "mainland_assignment_rows": roles["mainland_cell_partitions"]["rows"],
        "split_response_rows": roles["split_responses"]["rows"],
        "targets": len(config["scope"]["targets"]),
        "response_heads": len(response_heads),
        "tasmania_response_rows_read": 0,
        "tasmania_predictor_rows_used": 0,
    }


def _q_paths(root: Path, target: str, fold: int) -> tuple[Path, Path]:
    stem = f"{slug(target)}_fold{fold:02d}"
    directory = root / PRIVATE_ROOT / "q_linear"
    return directory / f"{stem}.parquet", directory / f"{stem}.json"


def _write_q_checkpoint(
    root: Path,
    identity: Mapping[str, str],
    target: str,
    fold: int,
    scores: Mapping[str, float],
    receipt: Mapping[str, Any],
) -> None:
    parquet_path, receipt_path = _q_paths(root, target, fold)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    cells = sorted(scores)
    table = pa.table(
        {
            "cell_id": pa.array(cells, pa.string()),
            "q_linear": pa.array([scores[cell] for cell in cells], pa.float64()),
        }
    )
    temporary = parquet_path.with_suffix(".parquet.tmp")
    require(not temporary.exists(), "q_orphaned_temporary")
    pq.write_table(table, temporary, compression="zstd")
    os.replace(temporary, parquet_path)
    _atomic_json(
        receipt_path,
        {
            "schema_version": "goal044-q-receipt-v1",
            "identity": dict(identity),
            "parquet_sha256": sha256_file(parquet_path),
            "parquet_rows": len(cells),
            **dict(receipt),
        },
    )


def _load_q_checkpoint(root: Path, identity: Mapping[str, str], target: str, fold: int) -> dict[str, float] | None:
    parquet_path, receipt_path = _q_paths(root, target, fold)
    if not parquet_path.is_file() or not receipt_path.is_file():
        return None
    receipt = _read_json(receipt_path)
    if receipt.get("identity") != identity or receipt.get("parquet_sha256") != sha256_file(parquet_path):
        return None
    table = pq.read_table(parquet_path).combine_chunks()
    cells = table["cell_id"].to_pylist()
    values = table["q_linear"].to_numpy(zero_copy_only=False).astype(np.float64)
    require(len(cells) == receipt["parquet_rows"] == len(set(cells)), "q_checkpoint_row_drift")
    require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "q_checkpoint_score_drift")
    return dict(zip(cells, values.tolist()))


def prepare_q_surfaces(root: Path, store: MainlandStore, config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    identity = _identity(root)
    receipts: list[Mapping[str, Any]] = []
    for target in config["scope"]["targets"]:
        for fold in config["scope"]["folds"]:
            cached = _load_q_checkpoint(root, identity, target, fold)
            _, receipt_path = _q_paths(root, target, fold)
            if cached is None:
                start = time.perf_counter()
                scores, receipt = fit_q_linear(store, config, target, fold)
                receipt = {**receipt, "runtime_seconds": time.perf_counter() - start}
                _write_q_checkpoint(root, identity, target, fold, scores, receipt)
            receipts.append(_read_json(receipt_path))
            print(f"q_linear ready: {target} fold{fold:02d}", flush=True)
    return receipts


def _load_q_required(root: Path, identity: Mapping[str, str], target: str, fold: int) -> dict[str, float]:
    scores = _load_q_checkpoint(root, identity, target, fold)
    require(scores is not None, f"q_checkpoint_missing:{target}:{fold}")
    return scores


def _endpoint_label(fraction: int, ladder: str) -> str:
    return f"fraction{fraction}/{ladder}"


def _tasks(config: Mapping[str, Any]) -> list[tuple[str, int, str]]:
    endpoints = [(25, ladder) for ladder in config["target_subsets"]["ladders"]]
    endpoints += [(50, ladder) for ladder in config["target_subsets"]["ladders"]]
    endpoints.append((100, "full"))
    return [(target, fraction, ladder) for target in config["scope"]["targets"] for fraction, ladder in endpoints]


def _task_paths(root: Path, target: str, fraction: int, ladder: str) -> tuple[Path, Path]:
    stem = f"{slug(target)}_fraction{fraction}_{ladder}"
    directory = root / PRIVATE_ROOT / "tasks"
    return directory / f"{stem}.json", directory / f"{stem}.parquet"


def _fit_seed(config: Mapping[str, Any], target: str, fraction: int, ladder: str, fold: int, family: str, candidate_id: str, seed_label: str, q: bool) -> int:
    return stable_seed(
        config["target_subsets"]["master_seed"], target, fraction, ladder, fold,
        family, candidate_id, seed_label, "q" if q else "target",
    )


def _fit_predict(
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    ladder: str,
    fold: int,
    family: str,
    candidate_id: str,
    seed_label: str,
    train_rows: ResponseRows,
    train_batch: FeatureBatch,
    validation_batch: FeatureBatch,
    q: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    candidate = CANONICAL_CANDIDATES[candidate_id]
    adapter = build_adapter(family)
    seed = _fit_seed(config, target, fraction, ladder, fold, family, candidate_id, seed_label, q)
    if family != "shallow_ann":
        fitted, report = adapter.fit(train_batch, None, candidate, seed)
        scores = fitted.predict_scores(validation_batch)
        return scores, {
            "physical_fits": 1,
            "runtime_seconds": report.runtime_seconds,
            "best_epoch": None,
        }

    stopping_fold = (fold + 1) % 5
    stopping_indices = np.flatnonzero(train_rows.source_folds == stopping_fold)
    discovery_indices = np.flatnonzero(train_rows.source_folds != stopping_fold)
    require(len(set(train_rows.y[stopping_indices].tolist())) == 2, "ann_stopping_single_class")
    require(len(set(train_rows.y[discovery_indices].tolist())) == 2, "ann_discovery_single_class")
    discovery = subset_batch(train_batch, discovery_indices)
    stopping = subset_batch(train_batch, stopping_indices)
    _, discovery_report = adapter.fit(discovery, stopping, candidate, seed)
    require(discovery_report.best_epoch is not None, "ann_best_epoch_missing")
    replay, replay_report = adapter.fit(
        train_batch, None, candidate, seed, exact_epochs=int(discovery_report.best_epoch)
    )
    require(
        discovery_report.initial_state_digest == replay_report.initial_state_digest,
        "ann_replay_initialization_drift",
    )
    scores = replay.predict_scores(validation_batch)
    return scores, {
        "physical_fits": 2,
        "runtime_seconds": discovery_report.runtime_seconds + replay_report.runtime_seconds,
        "best_epoch": int(discovery_report.best_epoch),
    }


def _prepare_fold(
    store: MainlandStore,
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    ladder: str,
    fold: int,
    q_scores: Mapping[str, float] | None,
) -> dict[str, Any]:
    full_train = store.response_rows(target, fold, "train")
    endpoint_ladder = "ladder00" if fraction == 100 else ladder
    indices = endpoint_indices(
        full_train, fraction, endpoint_ladder, config["target_subsets"]["master_seed"]
    )
    train = full_train.take(indices)
    validation = store.response_rows(target, fold, "validation")
    train_q = None if q_scores is None else [q_scores[cell] for cell in train.cell_ids]
    validation_q = None if q_scores is None else [q_scores[cell] for cell in validation.cell_ids]
    train_features = store.encoded(train.cell_ids, fold, train_q)
    validation_features = store.encoded(validation.cell_ids, fold, validation_q)
    return {
        "fold": fold,
        "train_rows": train,
        "validation_rows": validation,
        "train_batch": make_batch(target, train, train_features),
        "validation_batch": make_batch(target, validation, validation_features),
    }


def _evaluate_candidate(
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    ladder: str,
    family: str,
    candidate_id: str,
    seed_labels: Sequence[str],
    prepared: Sequence[Mapping[str, Any]],
    q: bool = False,
) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    fit_records: list[dict[str, Any]] = []
    for item in prepared:
        scores_by_seed: dict[str, np.ndarray] = {}
        for seed_label in seed_labels:
            scores, fit = _fit_predict(
                config, target, fraction, ladder, int(item["fold"]), family,
                candidate_id, seed_label, item["train_rows"], item["train_batch"],
                item["validation_batch"], q,
            )
            require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "candidate_score_invalid")
            scores_by_seed[seed_label] = scores
            fit_records.append({"fold": int(item["fold"]), "seed_label": seed_label, **fit})
        folds.append(
            {
                "fold": int(item["fold"]),
                "cell_ids": item["validation_rows"].cell_ids,
                "y": item["validation_rows"].y,
                "score": np.mean(np.vstack([scores_by_seed[label] for label in seed_labels]), axis=0),
                "scores_by_seed": scores_by_seed,
            }
        )
    metrics = summarize_oof(folds)
    return {
        "candidate_id": candidate_id,
        "seed_labels": list(seed_labels),
        "folds": folds,
        "metrics": metrics,
        "fit_records": fit_records,
        "physical_fits": int(sum(record["physical_fits"] for record in fit_records)),
        "runtime_seconds": float(sum(record["runtime_seconds"] for record in fit_records)),
    }


def _public_candidate(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": result["candidate_id"],
        "seed_labels": result["seed_labels"],
        "metrics": result["metrics"],
        "physical_fits": result["physical_fits"],
        "runtime_seconds": result["runtime_seconds"],
        "best_epoch_range": (
            [
                min(record["best_epoch"] for record in result["fit_records"] if record["best_epoch"] is not None),
                max(record["best_epoch"] for record in result["fit_records"] if record["best_epoch"] is not None),
            ]
            if any(record["best_epoch"] is not None for record in result["fit_records"])
            else None
        ),
    }


def _selection_key(result: Mapping[str, Any], identity: str) -> tuple[float, float, str]:
    metrics = result["metrics"]
    return (-metrics["mean_fold_roc_auc"], -metrics["pooled"]["tss"], identity)


def _extend_selected_seeds(
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    ladder: str,
    family: str,
    selected: Mapping[str, Any],
    prepared: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    desired = config["conventional"]["selected_seed_labels"][family]
    existing = list(selected["seed_labels"])
    missing = [label for label in desired if label not in existing]
    if not missing:
        return dict(selected)
    extra = _evaluate_candidate(
        config, target, fraction, ladder, family, selected["candidate_id"], missing, prepared
    )
    folds: list[dict[str, Any]] = []
    for base_fold, extra_fold in zip(selected["folds"], extra["folds"]):
        combined = {**base_fold["scores_by_seed"], **extra_fold["scores_by_seed"]}
        folds.append(
            {
                "fold": base_fold["fold"],
                "cell_ids": base_fold["cell_ids"],
                "y": base_fold["y"],
                "scores_by_seed": combined,
                "score": np.mean(np.vstack([combined[label] for label in desired]), axis=0),
            }
        )
    return {
        "candidate_id": selected["candidate_id"],
        "seed_labels": list(desired),
        "folds": folds,
        "metrics": summarize_oof(folds),
        "fit_records": [*selected["fit_records"], *extra["fit_records"]],
        "physical_fits": selected["physical_fits"] + extra["physical_fits"],
        "runtime_seconds": selected["runtime_seconds"] + extra["runtime_seconds"],
    }


def _prediction_rows(
    target: str,
    fraction: int,
    ladder: str,
    method: str,
    family: str,
    candidate_id: str,
    result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fold in result["folds"]:
        for cell, y, score in zip(fold["cell_ids"], fold["y"], fold["score"]):
            rows.append(
                {
                    "target": target,
                    "fraction": fraction,
                    "ladder": ladder,
                    "fold": fold["fold"],
                    "cell_id": cell,
                    "y": int(y),
                    "method": method,
                    "family": family,
                    "candidate_id": candidate_id,
                    "score": float(score),
                }
            )
    return rows


def run_task(root: Path, store: MainlandStore, config: Mapping[str, Any], target: str, fraction: int, ladder: str) -> Mapping[str, Any]:
    started = time.perf_counter()
    identity = _identity(root)
    prepared = [
        _prepare_fold(store, config, target, fraction, ladder, fold, None)
        for fold in config["scope"]["folds"]
    ]
    family_results: dict[str, Any] = {}
    prediction_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for family in config["conventional"]["families"]:
        candidates: list[Mapping[str, Any]] = []
        for candidate_id in config["conventional"]["candidate_ids"][family]:
            try:
                candidates.append(
                    _evaluate_candidate(
                        config, target, fraction, ladder, family, candidate_id,
                        config["conventional"]["screen_seed_labels"][family], prepared,
                    )
                )
            except (MainlandModelingError, ModelAdapterError, ValueError) as exc:
                failures.append({"family": family, "candidate_id": candidate_id, "error": str(exc)})
        minimum = config["conventional"]["minimum_complete_candidates"][family]
        require(len(candidates) >= minimum, f"family_candidate_minimum_failed:{family}")
        selected = min(candidates, key=lambda item: _selection_key(item, item["candidate_id"]))
        selected = _extend_selected_seeds(
            config, target, fraction, ladder, family, selected, prepared
        )
        family_results[family] = {
            "candidates": [_public_candidate(item) for item in candidates],
            "selected": _public_candidate(selected),
        }
        prediction_rows.extend(
            _prediction_rows(
                target, fraction, ladder, f"family:{family}", family,
                selected["candidate_id"], selected,
            )
        )
        family_results[family]["_selected_private"] = selected

    non_null = [family for family in family_results if family != "intercept"]
    best_family = min(
        non_null,
        key=lambda family: _selection_key(
            family_results[family]["_selected_private"], family
        ),
    )
    best = family_results[best_family]["_selected_private"]
    q_prepared = []
    for fold in config["scope"]["folds"]:
        q_scores = _load_q_required(root, identity, target, fold)
        q_prepared.append(_prepare_fold(store, config, target, fraction, ladder, fold, q_scores))
    q_result = _evaluate_candidate(
        config, target, fraction, ladder, best_family, best["candidate_id"],
        config["conventional"]["selected_seed_labels"][best_family], q_prepared, q=True,
    )
    prediction_rows.extend(
        _prediction_rows(
            target, fraction, ladder, "q_linear_selected_conventional", best_family,
            best["candidate_id"], q_result,
        )
    )

    for family in family_results:
        family_results[family].pop("_selected_private")
    result_path, prediction_path = _task_paths(root, target, fraction, ladder)
    table = pa.Table.from_pylist(prediction_rows, schema=PREDICTION_SCHEMA)
    _atomic_parquet(prediction_path, table)
    result = {
        "schema_version": "goal044-task-v1",
        "identity": identity,
        "target": target,
        "fraction": fraction,
        "ladder": ladder,
        "endpoint": _endpoint_label(fraction, ladder),
        "families": family_results,
        "best_non_null_family": best_family,
        "community_control": {
            "id": "q_linear",
            "family": best_family,
            "candidate_id": best["candidate_id"],
            "candidate_retuned": False,
            **_public_candidate(q_result),
        },
        "candidate_failures": failures,
        "prediction_rows": len(prediction_rows),
        "prediction_sha256": sha256_file(prediction_path),
        "physical_fits": int(
            sum(
                candidate["physical_fits"]
                for family in family_results.values()
                for candidate in family["candidates"]
            )
            + sum(
                max(0, family["selected"]["physical_fits"] - next(
                    candidate["physical_fits"]
                    for candidate in family["candidates"]
                    if candidate["candidate_id"] == family["selected"]["candidate_id"]
                ))
                for family in family_results.values()
            )
            + q_result["physical_fits"]
        ),
        "runtime_seconds": time.perf_counter() - started,
        "tasmania_response_rows_read": 0,
        "tasmania_predictor_rows_used": 0,
    }
    _atomic_json(result_path, result)
    return result


def _task_checkpoint(root: Path, identity: Mapping[str, str], target: str, fraction: int, ladder: str) -> Mapping[str, Any] | None:
    result_path, prediction_path = _task_paths(root, target, fraction, ladder)
    if not result_path.is_file() or not prediction_path.is_file():
        return None
    result = _read_json(result_path)
    if (
        result.get("identity") != identity
        or result.get("target") != target
        or result.get("fraction") != fraction
        or result.get("ladder") != ladder
        or result.get("prediction_sha256") != sha256_file(prediction_path)
    ):
        return None
    return result


_WORKER_ROOT: Path | None = None
_WORKER_CONFIG: Mapping[str, Any] | None = None
_WORKER_STORE: MainlandStore | None = None


def _worker_init(root: str) -> None:
    global _WORKER_ROOT, _WORKER_CONFIG, _WORKER_STORE
    os.environ.update(
        OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
    )
    _WORKER_ROOT = Path(root)
    _WORKER_CONFIG = _config(_WORKER_ROOT)
    _WORKER_STORE = MainlandStore(_WORKER_ROOT)


def _worker_task(task: tuple[str, int, str]) -> tuple[str, str]:
    require(_WORKER_ROOT is not None and _WORKER_CONFIG is not None and _WORKER_STORE is not None, "worker_not_initialized")
    with threadpool_limits(limits=1):
        result = run_task(_WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, *task)
    return result["target"], result["endpoint"]


def _aggregate(root: Path, config: Mapping[str, Any]) -> Mapping[str, Any]:
    identity = _identity(root)
    results = []
    private_outputs = []
    for target, fraction, ladder in _tasks(config):
        result = _task_checkpoint(root, identity, target, fraction, ladder)
        require(result is not None, f"task_checkpoint_missing:{target}:{fraction}:{ladder}")
        result_path, prediction_path = _task_paths(root, target, fraction, ladder)
        results.append(result)
        private_outputs.append(
            {
                "task": f"{slug(target)}_fraction{fraction}_{ladder}",
                "result_sha256": sha256_file(result_path),
                "prediction_sha256": sha256_file(prediction_path),
                "prediction_rows": result["prediction_rows"],
            }
        )
    q_receipts = []
    for target in config["scope"]["targets"]:
        for fold in config["scope"]["folds"]:
            _, receipt_path = _q_paths(root, target, fold)
            receipt = _read_json(receipt_path)
            q_receipts.append(
                {
                    "target": target,
                    "held_fold": fold,
                    "auxiliary_head_count": receipt["auxiliary_head_count"],
                    "excluded_target": receipt["excluded_target"],
                    "total_training_rows": receipt["total_training_rows"],
                    "iterations": receipt["iterations"],
                    "target_score_count": receipt["target_score_count"],
                    "target_score_range": receipt["target_score_range"],
                    "runtime_seconds": receipt["runtime_seconds"],
                }
            )
    task_summaries = []
    for result in results:
        task_summaries.append(
            {
                key: result[key]
                for key in (
                    "target", "fraction", "ladder", "endpoint", "families",
                    "best_non_null_family", "community_control", "candidate_failures",
                    "physical_fits", "runtime_seconds",
                )
            }
        )
    return {
        "schema_version": "goal044-summary-v1",
        "goal_id": config["goal_id"],
        "status": "complete",
        "identity": identity,
        "design": {
            "targets": config["scope"]["targets"],
            "families": config["conventional"]["families"],
            "endpoints_per_target": 7,
            "primary_background": "eligible_x3",
            "goal045_status": config["goal045_frozen_design"]["status"],
        },
        "q_linear": q_receipts,
        "tasks": task_summaries,
        "private_outputs": private_outputs,
        "totals": {
            "tasks": len(results),
            "q_surfaces": len(q_receipts),
            "physical_fits": int(sum(result["physical_fits"] for result in results)),
            "task_runtime_seconds": float(sum(result["runtime_seconds"] for result in results)),
            "q_runtime_seconds": float(sum(item["runtime_seconds"] for item in q_receipts)),
            "candidate_failures": sum(len(result["candidate_failures"]) for result in results),
        },
        "privacy": {
            "tracked_cell_ids": False,
            "tracked_predictions": False,
            "tracked_coordinates": False,
            "tasmania_response_rows_read": 0,
            "tasmania_predictor_rows_used": 0,
        },
    }


def run_all(root: Path, workers: int) -> Mapping[str, Any]:
    validate_inputs(root)
    config = _config(root)
    require(1 <= workers <= 3, "workers_out_of_bounds")
    store = MainlandStore(root)
    prepare_q_surfaces(root, store, config)
    del store
    identity = _identity(root)
    pending = [task for task in _tasks(config) if _task_checkpoint(root, identity, *task) is None]
    if workers == 1:
        store = MainlandStore(root)
        for task in pending:
            with threadpool_limits(limits=1):
                result = run_task(root, store, config, *task)
            print(f"task ready: {result['target']} {result['endpoint']}", flush=True)
    elif pending:
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=workers, mp_context=context, initializer=_worker_init,
            initargs=(str(root),),
        ) as executor:
            futures = {executor.submit(_worker_task, task): task for task in pending}
            for future in as_completed(futures):
                target, endpoint = future.result()
                print(f"task ready: {target} {endpoint}", flush=True)
    summary = _aggregate(root, config)
    _atomic_json(root / SUMMARY_PATH, summary)
    return summary


def canary(root: Path) -> Mapping[str, Any]:
    inputs = validate_inputs(root)
    config = _config(root)
    spec = config["execution"]["canary"]
    store = MainlandStore(root)
    identity = _identity(root)
    q = _load_q_checkpoint(root, identity, spec["target"], spec["fold"])
    q_runtime = 0.0
    if q is None:
        start = time.perf_counter()
        q, receipt = fit_q_linear(store, config, spec["target"], spec["fold"])
        q_runtime = time.perf_counter() - start
        _write_q_checkpoint(root, identity, spec["target"], spec["fold"], q, {**receipt, "runtime_seconds": q_runtime})
    prepared = _prepare_fold(store, config, spec["target"], 100, "full", spec["fold"], None)
    results = []
    for candidate_id in spec["candidate_ids"]:
        family = CANONICAL_CANDIDATES[candidate_id]["family"]
        start = time.perf_counter()
        scores, fit = _fit_predict(
            config, spec["target"], 100, "full", spec["fold"], family,
            candidate_id, "seed00", prepared["train_rows"], prepared["train_batch"],
            prepared["validation_batch"], False,
        )
        results.append(
            {
                "family": family,
                "candidate_id": candidate_id,
                "runtime_seconds": time.perf_counter() - start,
                "physical_fits": fit["physical_fits"],
                "prediction_count": len(scores),
                "prediction_range": [float(np.min(scores)), float(np.max(scores))],
            }
        )
    q_prepared = _prepare_fold(store, config, spec["target"], 100, "full", spec["fold"], q)
    start = time.perf_counter()
    q_scores, q_fit = _fit_predict(
        config, spec["target"], 100, "full", spec["fold"],
        "hist_gradient_boosting", "hgb04", "seed00", q_prepared["train_rows"],
        q_prepared["train_batch"], q_prepared["validation_batch"], True,
    )
    receipt = {
        "schema_version": "goal044-canary-v1",
        "status": "pass",
        "identity": identity,
        "host": {"system": platform.system(), "machine": platform.machine()},
        "inputs": inputs,
        "target": spec["target"],
        "fold": spec["fold"],
        "q_fit_runtime_seconds": q_runtime,
        "candidate_results": results,
        "q_augmented_result": {
            "family": "hist_gradient_boosting",
            "candidate_id": "hgb04",
            "runtime_seconds": time.perf_counter() - start,
            "physical_fits": q_fit["physical_fits"],
            "prediction_count": len(q_scores),
            "prediction_range": [float(np.min(q_scores)), float(np.max(q_scores))],
        },
        "performance_metrics_computed": False,
        "tasmania_response_rows_read": 0,
        "tasmania_predictor_rows_used": 0,
    }
    _atomic_json(root / CANARY_PATH, receipt)
    return receipt


def _assert_close(actual: Any, expected: Any, path: str = "root") -> None:
    if isinstance(expected, Mapping):
        require(isinstance(actual, Mapping) and set(actual) == set(expected), f"summary_key_drift:{path}")
        for key in expected:
            _assert_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"summary_list_drift:{path}")
        for index, value in enumerate(expected):
            _assert_close(actual[index], value, f"{path}[{index}]")
    elif isinstance(expected, float):
        require(isinstance(actual, (int, float)) and np.isclose(actual, expected, rtol=0, atol=1e-12), f"summary_float_drift:{path}")
    else:
        require(actual == expected, f"summary_value_drift:{path}")


def _validate_task_predictions(root: Path, store: MainlandStore, result: Mapping[str, Any]) -> None:
    target, fraction, ladder = result["target"], result["fraction"], result["ladder"]
    _, prediction_path = _task_paths(root, target, fraction, ladder)
    table = pq.read_table(prediction_path).combine_chunks()
    require(table.schema == PREDICTION_SCHEMA, "prediction_schema_drift")
    require(table.num_rows == result["prediction_rows"], "prediction_row_count_drift")
    require(sha256_file(prediction_path) == result["prediction_sha256"], "prediction_receipt_drift")
    methods = [f"family:{family}" for family in result["families"]] + ["q_linear_selected_conventional"]
    require(set(pc.unique(table["method"]).to_pylist()) == set(methods), "prediction_method_inventory_drift")
    for method in methods:
        method_folds = []
        filtered = table.filter(pc.equal(table["method"], method)).sort_by([("fold", "ascending"), ("cell_id", "ascending")])
        for fold in range(5):
            fold_table = filtered.filter(pc.equal(filtered["fold"], fold))
            expected_rows = store.response_rows(target, fold, "validation")
            cells = tuple(fold_table["cell_id"].to_pylist())
            y = fold_table["y"].to_numpy(zero_copy_only=False).astype(np.int8)
            score = fold_table["score"].to_numpy(zero_copy_only=False).astype(np.float64)
            require(cells == expected_rows.cell_ids and np.array_equal(y, expected_rows.y), "prediction_response_binding_drift")
            method_folds.append({"fold": fold, "y": y, "score": score})
        observed = summarize_oof(method_folds)
        expected = (
            result["community_control"]["metrics"]
            if method == "q_linear_selected_conventional"
            else result["families"][method.split(":", 1)[1]]["selected"]["metrics"]
        )
        _assert_close(observed, expected, f"{target}:{fraction}:{ladder}:{method}")


def validate_outputs(root: Path) -> Mapping[str, Any]:
    validate_inputs(root)
    config = _config(root)
    identity = _identity(root)
    store = MainlandStore(root)
    for target in config["scope"]["targets"]:
        for fold in config["scope"]["folds"]:
            scores = _load_q_checkpoint(root, identity, target, fold)
            require(scores is not None, f"q_checkpoint_invalid:{target}:{fold}")
            _, receipt_path = _q_paths(root, target, fold)
            receipt = _read_json(receipt_path)
            require(receipt["excluded_target"] is True and target not in receipt["auxiliary_heads"], "q_target_exclusion_receipt_drift")
            require(receipt["auxiliary_head_count"] == 19, "q_auxiliary_head_count_drift")
    for target, fraction, ladder in _tasks(config):
        result = _task_checkpoint(root, identity, target, fraction, ladder)
        require(result is not None, f"task_checkpoint_invalid:{target}:{fraction}:{ladder}")
        require(result["tasmania_response_rows_read"] == 0 and result["tasmania_predictor_rows_used"] == 0, "task_tasmania_firewall_drift")
        _validate_task_predictions(root, store, result)
    expected = _aggregate(root, config)
    actual = _read_json(root / SUMMARY_PATH)
    _assert_close(actual, expected)
    require(actual["privacy"]["tasmania_response_rows_read"] == 0, "summary_tasmania_response_drift")
    require(actual["privacy"]["tasmania_predictor_rows_used"] == 0, "summary_tasmania_predictor_drift")
    return {
        "status": "goal044_ready",
        "tasks": expected["totals"]["tasks"],
        "q_surfaces": expected["totals"]["q_surfaces"],
        "physical_fits": expected["totals"]["physical_fits"],
        "candidate_failures": expected["totals"]["candidate_failures"],
        "tasmania_response_rows_read": 0,
        "tasmania_predictor_rows_used": 0,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate-inputs", "canary", "run", "validate"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "validate-inputs":
        output = validate_inputs(root)
    elif args.command == "canary":
        output = canary(root)
    elif args.command == "run":
        output = run_all(root, args.workers)
    else:
        output = validate_outputs(root)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
