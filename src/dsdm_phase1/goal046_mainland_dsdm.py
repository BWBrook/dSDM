"""Run the strict leave-target-out mainland correction for Goal 045."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Mapping, Sequence
import warnings

import numpy as np
import pyarrow.dataset as ds
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import torch
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from .goal044_mainland_conventional import validate_inputs as validate_goal044_inputs
from .goal044_mainland_conventional import _evaluate_candidate, _prepare_fold
from .model_adapters import CANONICAL_CANDIDATES
from .mainland_dsdm import (
    NeuralDataset,
    architecture_spec,
    equal_head_weights,
    fit_pretraining_lifecycle,
    fit_target_lifecycle,
    state_digest,
)
from .mainland_modeling import (
    MainlandStore,
    ResponseRows,
    endpoint_indices,
    sha256_file,
    slug,
    stable_seed,
    summarize_oof,
)


CONFIG_PATH = "config/goal046_mainland_dsdm.json"
SOURCE_PATH = "src/dsdm_phase1/goal046_mainland_dsdm.py"
TRAINING_SOURCE_PATH = "src/dsdm_phase1/mainland_dsdm.py"
GOAL045_SOURCE_PATH = "src/dsdm_phase1/goal045_mainland_dsdm.py"
GOAL044_SOURCE_PATH = "src/dsdm_phase1/goal044_mainland_conventional.py"
Q_CONVENTIONAL_SCHEMA = pa.schema([
    pa.field("cell_id", pa.string(), nullable=False),
    pa.field("fold", pa.int8(), nullable=False),
    pa.field("y", pa.int8(), nullable=False),
    pa.field("score", pa.float64(), nullable=False),
])


class Goal046Error(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Goal046Error(message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal046Error(f"json_invalid:{path}") from exc
    _require(isinstance(value, dict), f"json_object_required:{path}")
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _atomic_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        pq.write_table(table, temporary, compression="zstd")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _config(root: Path) -> dict[str, Any]:
    config = _read_json(root / CONFIG_PATH)
    _require(config.get("schema_version") == "goal046-contract-v1", "config_schema_invalid")
    _require(config.get("goal_id") == "goal046-strict-mainland-dsdm-correction", "config_goal_invalid")
    goal044 = _read_json(root / config["bindings"]["goal044_config"]["path"])
    goal045 = _read_json(root / config["bindings"]["goal045_config"]["path"])
    _require(config["design"]["architecture_candidates"] == goal045["design"]["architecture_candidates"], "architecture_panel_drift")
    _require(config["design"]["arms"] == goal045["design"]["arms"], "arm_panel_drift")
    _require(config["design"]["seed_labels"] == goal045["design"]["seed_labels"], "seed_panel_drift")
    _require(config["scope"] == {
        "region": goal044["scope"]["region"],
        "targets": goal044["scope"]["targets"],
        "response_heads": goal044["scope"]["response_heads"],
        "folds": goal044["scope"]["folds"],
        "primary_background": goal044["scope"]["primary_background"],
        "tasmania_evaluation": goal044["scope"]["tasmania_evaluation"],
    }, "goal044_scope_drift")
    _require(config["target_subsets"]["fractions"] == [100] and config["target_subsets"]["ladders"] == [], "endpoint_scope_invalid")
    _require(config["target_subsets"]["full_alias"] == goal045["target_subsets"]["full_alias"] and config["target_subsets"]["master_seed"] == goal045["target_subsets"]["master_seed"], "seed_authority_drift")
    _require(config["design"]["architecture_constants"]["shape"] == "constant", "architecture_shape_invalid")
    _require(config["lifecycle"]["architecture_selection_seed_labels"] == ["seed00"], "architecture_screen_seed_drift")
    _require(config["privacy"]["tasmania_response_rows_read"] == 0, "tasmania_response_access_forbidden")
    _require(config["privacy"]["tasmania_predictor_rows_used"] == 0, "tasmania_predictor_access_forbidden")
    return config


def _identity(root: Path) -> dict[str, str]:
    return {
        "config_sha256": sha256_file(root / CONFIG_PATH),
        "source_sha256": sha256_file(root / SOURCE_PATH),
        "training_source_sha256": sha256_file(root / TRAINING_SOURCE_PATH),
        "goal045_source_sha256": sha256_file(root / GOAL045_SOURCE_PATH),
        "goal045_config_sha256": sha256_file(root / "config/goal045_mainland_dsdm.json"),
        "goal045_summary_sha256": sha256_file(root / "evidence/mainland_dsdm/goal045/summary.json"),
        "goal044_source_sha256": sha256_file(root / GOAL044_SOURCE_PATH),
    }


def validate_inputs(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = _config(root)
    for name, binding in config["bindings"].items():
        path = root / binding["path"]
        _require(path.exists(), f"binding_missing:{name}")
        digest = sha256_file(path)
        _require(digest == binding["sha256"], f"binding_digest_mismatch:{name}")
    _require(_read_json(root / config["bindings"]["goal045_summary"]["path"]).get("status") == "goal045_ready", "goal045_not_ready")
    goal044_gate = validate_goal044_inputs(root)
    summary = _read_json(root / config["bindings"]["goal044_summary"]["path"])
    _require(summary.get("identity") == goal044_gate.get("identity"), "goal044_live_identity_drift")
    _require(summary.get("status") == "complete", "goal044_not_ready")
    _require(summary.get("totals", {}).get("tasks") == 35, "goal044_task_count_drift")
    _require(summary.get("totals", {}).get("q_surfaces") == 25, "goal044_q_count_drift")
    for key, value in summary.get("privacy", {}).items():
        _require(config["privacy"].get(key) == value, f"privacy_contract_drift:{key}")
    return {
        "status": "goal046_inputs_ready",
        "goal044_gate": goal044_gate,
        "targets": len(config["scope"]["targets"]),
        "response_heads": len(config["scope"]["response_heads"]),
        "architectures": len(config["design"]["architecture_candidates"]),
        "tasmania_response_rows_read": 0,
        "tasmania_predictor_rows_used": 0,
    }


def _architecture(config: Mapping[str, Any], identifier: str):
    rows = [row for row in config["design"]["architecture_candidates"] if row["id"] == identifier]
    _require(len(rows) == 1, "architecture_invalid")
    return architecture_spec(rows[0])


def _endpoint_tasks(config: Mapping[str, Any]) -> list[tuple[str, int, str]]:
    tasks: list[tuple[str, int, str]] = []
    for target in config["scope"]["targets"]:
        for fraction in config["target_subsets"]["fractions"]:
            ladders = [config["target_subsets"]["full_alias"]] if fraction == 100 else config["target_subsets"]["ladders"]
            tasks.extend((target, fraction, ladder) for ladder in ladders)
    _require(len(tasks) == 5, "endpoint_task_count_drift")
    return tasks


def _q_paths(root: Path, target: str, held_fold: int) -> tuple[Path, Path]:
    stem = f"{slug(target)}_fold{held_fold:02d}"
    directory = root / "data/processed/dsdm/goal046-strict-mainland-dsdm/q_linear"
    return directory / f"{stem}.json", directory / f"{stem}.parquet"


def _q_seed(config: Mapping[str, Any], target: str, held_fold: int) -> int:
    return stable_seed(config["target_subsets"]["master_seed"], "q", target, held_fold)


def _strict_auxiliary_rows(
    store: MainlandStore, target: str, head: str, held_fold: int
) -> tuple[ResponseRows, dict[str, int]]:
    rows, support = _response_rows_with_support(store, head, held_fold)
    target_rows = store.response_rows(target, held_fold, "train")
    target_presence = {
        cell for cell, label in zip(target_rows.cell_ids, target_rows.y, strict=True) if label == 1
    }
    selected, diagnostics = _apply_strict_support(rows, support, target_presence)
    return selected, diagnostics


def _apply_strict_support(
    rows: ResponseRows, support: np.ndarray, target_presence: set[str]
) -> tuple[ResponseRows, dict[str, int]]:
    support = np.asarray(support, dtype=np.int8)
    _require(support.shape == rows.y.shape and np.all(support >= 0), "support_count_invalid")
    adjusted = support - np.asarray(
        [cell in target_presence for cell in rows.cell_ids], dtype=np.int8
    )
    keep = (rows.y == 1) | (adjusted >= 3)
    selected = rows.take(np.flatnonzero(keep))
    diagnostics = {
        "original_rows": len(rows.y),
        "original_presences": int(np.sum(rows.y == 1)),
        "original_backgrounds": int(np.sum(rows.y == 0)),
        "focal_target_presence_cells": len(target_presence),
        "focal_target_overlap_backgrounds": int(np.sum((rows.y == 0) & np.isin(rows.cell_ids, list(target_presence)))),
        "dropped_backgrounds_adjusted_below_x3": int(np.sum((rows.y == 0) & ~keep)),
        "retained_rows": len(selected.y),
        "retained_presences": int(np.sum(selected.y == 1)),
        "retained_backgrounds": int(np.sum(selected.y == 0)),
        "adjusted_support_min": int(np.min(adjusted)),
    }
    _require(bool(np.all((selected.y == 1) | (adjusted[keep] >= 3))), "strict_support_rule_failed")
    return selected, diagnostics


def _response_rows_with_support(
    store: MainlandStore, target: str, held_fold: int
) -> tuple[ResponseRows, np.ndarray]:
    expression = (
        (ds.field("target") == target)
        & (ds.field("fold") == held_fold)
        & (ds.field("role") == "train")
        & ds.field("continuous_complete")
        & (ds.field("is_presence") | ds.field("eligible_x3"))
    )
    table = store.responses.to_table(
        filter=expression, columns=["cell_id", "is_presence", "other_species_count"]
    ).sort_by("cell_id")
    cells = tuple(table["cell_id"].to_pylist())
    y = table["is_presence"].to_numpy(zero_copy_only=False).astype(np.int8)
    support = table["other_species_count"].to_numpy(zero_copy_only=False).astype(np.int8)
    folds = np.asarray([store.fold_by_cell[cell] for cell in cells], dtype=np.int8)
    _require(cells and (folds != held_fold).all(), "strict_response_partition_invalid")
    return ResponseRows(cells, y, folds), support


def _fit_strict_q(
    root: Path, store: MainlandStore, config: Mapping[str, Any], target: str, held_fold: int
) -> tuple[dict[str, float], dict[str, Any]]:
    heads = [head for head in config["scope"]["response_heads"] if head != target]
    rows_by_head = []
    diagnostics = {}
    for head in heads:
        rows, audit = _strict_auxiliary_rows(store, target, head, held_fold)
        rows_by_head.append(rows)
        diagnostics[head] = audit
    _require(len(rows_by_head) == 19, "strict_auxiliary_head_count_invalid")
    counts = np.asarray([len(rows.y) for rows in rows_by_head], dtype=np.float64)
    cells = tuple(cell for rows in rows_by_head for cell in rows.cell_ids)
    y = np.concatenate([rows.y for rows in rows_by_head])
    features = store.encoded(cells, held_fold)
    total = float(np.sum(counts))
    weights = np.concatenate([
        np.full(int(count), total / (len(heads) * count), dtype=np.float64)
        for count in counts
    ])
    _require(np.isclose(np.mean(weights), 1.0, rtol=0, atol=1e-12), "q_weight_normalization_failed")
    head_totals = [float(np.sum(weight)) for weight in np.split(weights, np.cumsum(counts.astype(int))[:-1])]
    _require(np.allclose(head_totals, head_totals[0], rtol=0, atol=1e-8), "q_head_balance_failed")
    goal044_config = _read_json(root / config["bindings"]["goal044_config"]["path"])
    candidate = CANONICAL_CANDIDATES[goal044_config["community_control"]["candidate_id"]]
    model = LogisticRegression(
        C=float(candidate["C"]), l1_ratio=float(candidate["l1_ratio"]),
        penalty="elasticnet", solver="saga", max_iter=int(candidate["max_iter"]),
        tol=float(candidate["tol"]), fit_intercept=True, class_weight=None,
        n_jobs=1, random_state=_q_seed(config, target, held_fold),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model.fit(features.x, y, sample_weight=weights)
    _require(not any(issubclass(item.category, ConvergenceWarning) for item in caught)
             and int(model.n_iter_[0]) < int(candidate["max_iter"]), "q_linear_nonconverged")
    target_cells = sorted(set(store.response_rows(target, held_fold, "train").cell_ids)
                          | set(store.response_rows(target, held_fold, "validation").cell_ids))
    target_features = store.encoded(target_cells, held_fold)
    scores = model.predict_proba(target_features.x)[:, 1].astype(np.float64)
    _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "q_prediction_invalid")
    return dict(zip(target_cells, scores.tolist())), {
        "target": target, "held_fold": held_fold, "excluded_target": True,
        "fit_seed": _q_seed(config, target, held_fold),
        "auxiliary_heads": heads, "auxiliary_head_count": len(heads),
        "strict_support_rule": "subtract_focal_presence_before_x3",
        "rows_by_head": {head: int(count) for head, count in zip(heads, counts, strict=True)},
        "strict_support_diagnostics": diagnostics, "total_training_rows": int(total),
        "mean_row_weight": float(np.mean(weights)),
        "head_total_weight_range": [float(min(head_totals)), float(max(head_totals))],
        "within_head_class_balancing": False, "iterations": int(model.n_iter_[0]),
        "target_score_count": len(scores), "target_score_range": [float(np.min(scores)), float(np.max(scores))],
    }


def _q_surface(root: Path, target: str, held_fold: int) -> dict[str, float]:
    receipt_path, parquet_path = _q_paths(root, target, held_fold)
    receipt = _read_json(receipt_path)
    _require(receipt.get("schema_version") == "goal046-q-receipt-v1", "q_schema_invalid")
    _require(receipt.get("identity") == _identity(root), "q_identity_drift")
    _require(receipt.get("target") == target and receipt.get("held_fold") == held_fold, "q_identity_invalid")
    _require(receipt.get("excluded_target") is True and receipt.get("auxiliary_head_count") == 19, "q_target_exclusion_invalid")
    _require(sha256_file(parquet_path) == receipt.get("parquet_sha256"), "q_parquet_digest_mismatch")
    table = pq.read_table(parquet_path, columns=["cell_id", "q_linear"]).combine_chunks()
    cells = table["cell_id"].to_pylist()
    values = table["q_linear"].to_numpy(zero_copy_only=False).astype(np.float64)
    _require(len(cells) == receipt.get("parquet_rows") == len(set(cells)), "q_row_contract_invalid")
    _require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "q_values_invalid")
    return dict(zip(cells, values.tolist()))


def _write_q_surface(root: Path, target: str, held_fold: int, scores: Mapping[str, float], receipt: Mapping[str, Any]) -> None:
    receipt_path, parquet_path = _q_paths(root, target, held_fold)
    cells = sorted(scores)
    _atomic_parquet(parquet_path, pa.table({"cell_id": cells, "q_linear": [scores[cell] for cell in cells]}))
    _atomic_json(receipt_path, {
        "schema_version": "goal046-q-receipt-v1", "identity": _identity(root), **dict(receipt),
        "parquet_rows": len(cells), "parquet_sha256": sha256_file(parquet_path),
    })


def _prepare_q_surfaces(root: Path, store: MainlandStore, config: Mapping[str, Any]) -> None:
    for target in config["scope"]["targets"]:
        for held_fold in config["scope"]["folds"]:
            receipt_path, parquet_path = _q_paths(root, target, held_fold)
            if receipt_path.is_file() and parquet_path.is_file():
                try:
                    _q_surface(root, target, held_fold)
                    continue
                except Goal046Error:
                    pass
            scores, receipt = _fit_strict_q(root, store, config, target, held_fold)
            _write_q_surface(root, target, held_fold, scores, receipt)


@dataclass(frozen=True)
class TargetFoldData:
    discovery: NeuralDataset
    stopping: NeuralDataset
    replay: NeuralDataset
    held_x: np.ndarray
    held_y: np.ndarray
    held_cells: tuple[str, ...]
    feature_width: int
    q_scaling: Mapping[str, float] | None


def _dataset_for_rows(
    store: MainlandStore,
    rows: ResponseRows,
    held_fold: int,
    q: Mapping[str, float] | None,
    q_mean: float | None,
    q_sd: float | None,
) -> NeuralDataset:
    q_values = None if q is None else np.asarray([q[cell] for cell in rows.cell_ids], dtype=np.float64)
    encoded = store.encoded(rows.cell_ids, held_fold, q_values)
    x = np.asarray(encoded.x, dtype=np.float32)
    if q is not None:
        _require(q_mean is not None and q_sd is not None and q_sd > 0, "q_scaling_invalid")
        x[:, 21] = (x[:, 21] - q_mean) / q_sd
    return NeuralDataset(x, rows.y.astype(np.float32))


def _target_fold_data(
    root: Path,
    store: MainlandStore,
    config: Mapping[str, Any],
    target: str,
    held_fold: int,
    fraction: int,
    ladder: str,
    *,
    with_q: bool,
) -> TargetFoldData:
    full_train = store.response_rows(target, held_fold, "train")
    chosen = endpoint_indices(full_train, fraction, ladder, config["target_subsets"]["master_seed"])
    train = full_train.take(chosen)
    held = store.response_rows(target, held_fold, "validation")
    stopping_fold = (held_fold + 1) % 5
    discovery_index = np.flatnonzero(train.source_folds != stopping_fold)
    stopping_index = np.flatnonzero(train.source_folds == stopping_fold)
    _require(len(discovery_index) > 0 and len(stopping_index) > 0, "target_lifecycle_empty")
    discovery_rows = train.take(discovery_index)
    stopping_rows = train.take(stopping_index)
    q = _q_surface(root, target, held_fold) if with_q else None
    q_mean = q_sd = None
    if q is not None:
        _require(set(full_train.cell_ids) | set(held.cell_ids) <= set(q), "q_target_cells_missing")
        full_values = np.asarray([q[cell] for cell in full_train.cell_ids], dtype=np.float64)
        q_mean, q_sd = float(np.mean(full_values)), float(np.std(full_values, ddof=0))
        _require(np.isfinite(q_mean) and np.isfinite(q_sd) and q_sd > 0, "q_training_scale_invalid")
    discovery = _dataset_for_rows(store, discovery_rows, held_fold, q, q_mean, q_sd)
    stopping = _dataset_for_rows(store, stopping_rows, held_fold, q, q_mean, q_sd)
    replay = _dataset_for_rows(store, train, held_fold, q, q_mean, q_sd)
    held_data = _dataset_for_rows(store, held, held_fold, q, q_mean, q_sd)
    widths = {discovery.x.shape[1], stopping.x.shape[1], replay.x.shape[1], held_data.x.shape[1]}
    _require(len(widths) == 1, "target_feature_width_drift")
    return TargetFoldData(
        discovery, stopping, replay, held_data.x, held.y.astype(np.int8), held.cell_ids,
        widths.pop(), None if q is None else {"mean": q_mean, "population_sd": q_sd},
    )


def _pretraining_data(
    store: MainlandStore,
    config: Mapping[str, Any],
    target: str,
    held_fold: int,
) -> tuple[NeuralDataset, NeuralDataset, NeuralDataset, tuple[str, ...], dict[str, Any]]:
    heads = tuple(head for head in config["scope"]["response_heads"] if head != target)
    _require(len(heads) == 19 and target not in heads, "pretraining_target_exclusion_failed")
    rows_by_head: dict[str, ResponseRows] = {}
    support_audit: dict[str, Any] = {}
    for head in heads:
        rows_by_head[head], support_audit[head] = _strict_auxiliary_rows(store, target, head, held_fold)
    stopping_fold = (held_fold + 1) % 5

    def combine(role: str) -> NeuralDataset:
        cells: list[str] = []
        labels: list[np.ndarray] = []
        indices: list[np.ndarray] = []
        for head_index, head in enumerate(heads):
            rows = rows_by_head[head]
            if role == "discovery":
                selected = np.flatnonzero(rows.source_folds != stopping_fold)
            elif role == "stopping":
                selected = np.flatnonzero(rows.source_folds == stopping_fold)
            else:
                selected = np.arange(len(rows.y), dtype=np.int64)
            _require(len(selected) > 0, f"pretraining_{role}_head_empty")
            subset = rows.take(selected)
            cells.extend(subset.cell_ids)
            labels.append(subset.y.astype(np.float32))
            indices.append(np.full(len(subset.y), head_index, dtype=np.int64))
        head_index = np.concatenate(indices)
        encoded = store.encoded(cells, held_fold)
        return NeuralDataset(
            np.asarray(encoded.x, dtype=np.float32), np.concatenate(labels),
            head_index, equal_head_weights(head_index, len(heads)),
        )

    discovery = combine("discovery")
    stopping = combine("stopping")
    replay = combine("replay")
    _require(discovery.x.shape[1] == stopping.x.shape[1] == replay.x.shape[1], "pretraining_width_drift")
    meta = {
        "target": target,
        "held_fold": held_fold,
        "excluded_target": True,
        "auxiliary_heads": list(heads),
        "rows_by_head": {head: len(rows_by_head[head].y) for head in heads},
        "strict_support_diagnostics": support_audit,
        "strict_target_absent_as_head": target not in heads,
        "strict_target_presence_cells_removed_from_support": int(sum(
            item["dropped_backgrounds_adjusted_below_x3"] for item in support_audit.values()
        )),
        "feature_width": replay.x.shape[1],
        "stopping_fold": stopping_fold,
    }
    return discovery, stopping, replay, heads, meta


def _pretrain_paths(root: Path, target: str, held_fold: int, architecture: str, seed_label: str) -> tuple[Path, Path]:
    stem = f"{slug(target)}_fold{held_fold:02d}_{architecture}_{seed_label}"
    directory = root / "data/processed/dsdm/goal046-strict-mainland-dsdm/pretraining"
    return directory / f"{stem}.json", directory / f"{stem}.pt"


def _pretrain_key(identity: Mapping[str, str], target: str, held_fold: int, architecture: str, seed_label: str) -> dict[str, Any]:
    return {"identity": dict(identity), "target": target, "held_fold": held_fold, "architecture": architecture, "seed_label": seed_label}


def _load_pretraining(root: Path, expected: Mapping[str, Any]) -> tuple[dict[str, torch.Tensor], dict[str, Any]] | None:
    receipt_path, state_path = _pretrain_paths(root, expected["target"], expected["held_fold"], expected["architecture"], expected["seed_label"])
    if not receipt_path.is_file() or not state_path.is_file():
        return None
    receipt = _read_json(receipt_path)
    if receipt.get("schema_version") != "goal046-pretraining-v1" or receipt.get("key") != expected:
        return None
    if receipt.get("state_sha256") != sha256_file(state_path):
        return None
    try:
        state = torch.load(state_path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if not isinstance(state, dict) or state_digest(state) != receipt.get("shared_state_digest"):
        return None
    return state, receipt


def run_pretraining_task(
    root: Path,
    store: MainlandStore,
    config: Mapping[str, Any],
    identity: Mapping[str, str],
    target: str,
    held_fold: int,
    architecture_id: str,
    seed_label: str,
    device: str,
    *,
    max_epochs: int | None = None,
    patience: int | None = None,
    checkpoint: bool = True,
) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    key = _pretrain_key(identity, target, held_fold, architecture_id, seed_label)
    if checkpoint:
        loaded = _load_pretraining(root, key)
        if loaded is not None:
            return loaded
    discovery, stopping, replay, heads, meta = _pretraining_data(store, config, target, held_fold)
    constants = config["design"]["architecture_constants"]
    fit_seed = stable_seed(identity["goal045_config_sha256"], "pretrain", target, held_fold, architecture_id, seed_label)
    state, fit = fit_pretraining_lifecycle(
        _architecture(config, architecture_id), discovery, stopping, replay, heads,
        seed=fit_seed, device_name=device, batch_size=int(constants["batch_size"]),
        max_epochs=int(max_epochs or constants["max_epochs"]),
        patience=int(patience or constants["patience"]),
        min_delta=float(config["lifecycle"]["stopping_min_delta"]),
    )
    receipt: dict[str, Any] = {
        "schema_version": "goal046-pretraining-v1", "key": key, "fit_seed": fit_seed,
        "meta": meta, "fit": fit, "shared_state_digest": state_digest(state),
    }
    if checkpoint:
        receipt_path, state_path = _pretrain_paths(root, target, held_fold, architecture_id, seed_label)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=state_path.parent, suffix=".pt", delete=False) as handle:
            temporary = Path(handle.name)
        try:
            torch.save(state, temporary)
            os.replace(temporary, state_path)
        finally:
            temporary.unlink(missing_ok=True)
        receipt["state_sha256"] = sha256_file(state_path)
        _atomic_json(receipt_path, receipt)
    return state, receipt


def _prediction_paths(root: Path, stage: str, stem: str) -> tuple[Path, Path]:
    directory = root / f"data/processed/dsdm/goal046-strict-mainland-dsdm/{stage}"
    return directory / f"{stem}.json", directory / f"{stem}.parquet"


def _load_prediction(root: Path, stage: str, stem: str, key: Mapping[str, Any]) -> tuple[dict[str, Any], pa.Table] | None:
    receipt_path, parquet_path = _prediction_paths(root, stage, stem)
    if not receipt_path.is_file() or not parquet_path.is_file():
        return None
    receipt = _read_json(receipt_path)
    if receipt.get("key") != key or receipt.get("parquet_sha256") != sha256_file(parquet_path):
        return None
    table = pq.read_table(parquet_path).combine_chunks()
    if len(table) != receipt.get("parquet_rows"):
        return None
    return receipt, table


def _validate_held_prediction(
    store: MainlandStore, target: str, held_fold: int, table: pa.Table, score_columns: Sequence[str]
) -> None:
    expected_names = ["cell_id", "y", *score_columns]
    _require(table.schema.names == expected_names, "prediction_schema_columns_invalid")
    _require(table.schema.field("cell_id").type == pa.string(), "prediction_cell_type_invalid")
    _require(table.schema.field("y").type == pa.int8(), "prediction_y_type_invalid")
    for column in score_columns:
        _require(table.schema.field(column).type == pa.float64(), "prediction_score_type_invalid")
    authoritative = store.response_rows(target, held_fold, "validation")
    cells = tuple(table["cell_id"].to_pylist())
    y = table["y"].to_numpy(zero_copy_only=False).astype(np.int8)
    _require(len(cells) == len(set(cells)) and cells == authoritative.cell_ids, "prediction_held_cells_invalid")
    _require(np.array_equal(y, authoritative.y), "prediction_held_labels_invalid")
    for column in score_columns:
        scores = table[column].to_numpy(zero_copy_only=False).astype(np.float64)
        _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "prediction_scores_invalid")


def _write_prediction(root: Path, stage: str, stem: str, key: Mapping[str, Any], table: pa.Table, receipt: Mapping[str, Any]) -> dict[str, Any]:
    receipt_path, parquet_path = _prediction_paths(root, stage, stem)
    _atomic_parquet(parquet_path, table)
    payload = {"schema_version": f"goal046-{stage}-v1", "key": dict(key), **dict(receipt), "parquet_rows": len(table), "parquet_sha256": sha256_file(parquet_path)}
    _atomic_json(receipt_path, payload)
    return payload


def _target_seed(identity: Mapping[str, str], target: str, fraction: int, ladder: str, held_fold: int, architecture: str, seed_label: str) -> int:
    return stable_seed(identity["goal045_config_sha256"], "target", target, fraction, ladder, held_fold, architecture, seed_label)


def run_selection_task(
    root: Path,
    store: MainlandStore,
    config: Mapping[str, Any],
    identity: Mapping[str, str],
    target: str,
    held_fold: int,
    architecture_id: str,
    seed_label: str,
    device: str,
) -> dict[str, Any]:
    key = {"identity": dict(identity), "target": target, "held_fold": held_fold, "architecture": architecture_id, "seed_label": seed_label, "arm": config["design"]["primary_arm"], "endpoint": "fraction100/full"}
    stem = f"{architecture_id}_{slug(target)}_fold{held_fold:02d}_{seed_label}"
    loaded = _load_prediction(root, "selection", stem, key)
    if loaded is not None:
        _validate_held_prediction(store, target, held_fold, loaded[1], ["score"])
        return loaded[0]
    pretrained = _load_pretraining(root, _pretrain_key(identity, target, held_fold, architecture_id, seed_label))
    _require(pretrained is not None, "selection_pretraining_missing")
    state, pretraining_receipt = pretrained
    data = _target_fold_data(root, store, config, target, held_fold, 100, "full", with_q=False)
    constants = config["design"]["architecture_constants"]
    scores, fit = fit_target_lifecycle(
        _architecture(config, architecture_id), data.discovery, data.stopping, data.replay, data.held_x,
        seed=_target_seed(identity, target, 100, "full", held_fold, architecture_id, seed_label),
        device_name=device, batch_size=int(constants["batch_size"]), max_epochs=int(constants["max_epochs"]),
        patience=int(constants["patience"]), min_delta=float(config["lifecycle"]["stopping_min_delta"]),
        transferred_state=state, freeze_trunk=False,
    )
    table = pa.table({"cell_id": data.held_cells, "y": data.held_y, "score": scores})
    _validate_held_prediction(store, target, held_fold, table, ["score"])
    return _write_prediction(root, "selection", stem, key, table, {
        "fit": fit, "pretraining_shared_state_digest": pretraining_receipt["shared_state_digest"],
        "feature_width": data.feature_width,
    })


def _selection_result_path(root: Path) -> Path:
    return root / "data/processed/dsdm/goal046-strict-mainland-dsdm/architecture_selection.json"


def aggregate_selection(root: Path, config: Mapping[str, Any], identity: Mapping[str, str], *, write: bool = True) -> dict[str, Any]:
    seed_label = config["lifecycle"]["architecture_selection_seed_labels"][0]
    store = MainlandStore(root)
    metrics: dict[str, dict[str, Any]] = {}
    for architecture in [row["id"] for row in config["design"]["architecture_candidates"]]:
        metrics[architecture] = {}
        for target in config["scope"]["targets"]:
            folds = []
            for held_fold in config["scope"]["folds"]:
                key = {"identity": dict(identity), "target": target, "held_fold": held_fold, "architecture": architecture, "seed_label": seed_label, "arm": config["design"]["primary_arm"], "endpoint": "fraction100/full"}
                stem = f"{architecture}_{slug(target)}_fold{held_fold:02d}_{seed_label}"
                loaded = _load_prediction(root, "selection", stem, key)
                _require(loaded is not None, "selection_prediction_missing")
                table = loaded[1]
                _validate_held_prediction(store, target, held_fold, table, ["score"])
                folds.append({"fold": held_fold, "y": table["y"].to_numpy(), "score": table["score"].to_numpy()})
            metrics[architecture][target] = summarize_oof(folds)

    ranks = {architecture: [] for architecture in metrics}
    target_rankings: dict[str, list[str]] = {}
    for target in config["scope"]["targets"]:
        ordered = sorted(metrics, key=lambda architecture: (
            -metrics[architecture][target]["mean_fold_roc_auc"],
            -metrics[architecture][target]["pooled"]["tss"], architecture,
        ))
        target_rankings[target] = ordered
        for rank, architecture in enumerate(ordered, 1):
            ranks[architecture].append(rank)
    mean_ranks = {architecture: float(np.mean(values)) for architecture, values in ranks.items()}
    selected = min(mean_ranks, key=lambda architecture: (mean_ranks[architecture], architecture))
    result = {
        "schema_version": "goal046-architecture-selection-v1", "identity": dict(identity),
        "selected_architecture": selected, "mean_species_rank": mean_ranks,
        "target_rankings": target_rankings, "metrics": metrics,
        "selection_arm": config["design"]["primary_arm"], "selection_endpoint": "fraction100/full",
        "selection_seed_labels": [seed_label], "tasmania_response_rows_read": 0,
        "tasmania_predictor_rows_used": 0,
    }
    if write:
        _atomic_json(_selection_result_path(root), result)
    return result


def _final_stem(target: str, fraction: int, ladder: str, held_fold: int, seed_label: str) -> str:
    return f"{slug(target)}_fraction{fraction}_{ladder}_fold{held_fold:02d}_{seed_label}"


def run_final_task(
    root: Path,
    store: MainlandStore,
    config: Mapping[str, Any],
    identity: Mapping[str, str],
    selected_architecture: str,
    target: str,
    fraction: int,
    ladder: str,
    held_fold: int,
    seed_label: str,
    device: str,
) -> dict[str, Any]:
    key = {"identity": dict(identity), "selected_architecture": selected_architecture, "target": target, "fraction": fraction, "ladder": ladder, "held_fold": held_fold, "seed_label": seed_label}
    stem = _final_stem(target, fraction, ladder, held_fold, seed_label)
    loaded = _load_prediction(root, "final", stem, key)
    if loaded is not None:
        _validate_held_prediction(store, target, held_fold, loaded[1], config["design"]["arms"])
        return loaded[0]
    pretrained = _load_pretraining(root, _pretrain_key(identity, target, held_fold, selected_architecture, seed_label))
    _require(pretrained is not None, "final_pretraining_missing")
    state, pretraining_receipt = pretrained
    base = _target_fold_data(root, store, config, target, held_fold, fraction, ladder, with_q=False)
    q_data = _target_fold_data(root, store, config, target, held_fold, fraction, ladder, with_q=True)
    _require(base.held_cells == q_data.held_cells and np.array_equal(base.held_y, q_data.held_y), "q_target_binding_drift")
    constants = config["design"]["architecture_constants"]
    spec = _architecture(config, selected_architecture)
    seed = _target_seed(identity, target, fraction, ladder, held_fold, selected_architecture, seed_label)
    common = dict(
        seed=seed, device_name=device, batch_size=int(constants["batch_size"]),
        max_epochs=int(constants["max_epochs"]), patience=int(constants["patience"]),
        min_delta=float(config["lifecycle"]["stopping_min_delta"]),
    )
    outputs: dict[str, np.ndarray] = {}
    receipts: dict[str, Any] = {}
    arms = config["design"]["arms"]
    outputs[arms[0]], receipts[arms[0]] = fit_target_lifecycle(
        spec, base.discovery, base.stopping, base.replay, base.held_x, **common,
    )
    outputs[arms[1]], receipts[arms[1]] = fit_target_lifecycle(
        spec, q_data.discovery, q_data.stopping, q_data.replay, q_data.held_x, **common,
    )
    outputs[arms[2]], receipts[arms[2]] = fit_target_lifecycle(
        spec, base.discovery, base.stopping, base.replay, base.held_x,
        transferred_state=state, freeze_trunk=True, **common,
    )
    outputs[arms[3]], receipts[arms[3]] = fit_target_lifecycle(
        spec, base.discovery, base.stopping, base.replay, base.held_x,
        transferred_state=state, freeze_trunk=False, **common,
    )
    table = pa.table({"cell_id": base.held_cells, "y": base.held_y, **outputs})
    _validate_held_prediction(store, target, held_fold, table, config["design"]["arms"])
    return _write_prediction(root, "final", stem, key, table, {
        "fits": receipts, "pretraining_shared_state_digest": pretraining_receipt["shared_state_digest"],
        "base_feature_width": base.feature_width, "q_feature_width": q_data.feature_width,
        "q_scaling": q_data.q_scaling,
    })


_WORKER_ROOT: Path | None = None
_WORKER_STORE: MainlandStore | None = None
_WORKER_CONFIG: dict[str, Any] | None = None
_WORKER_IDENTITY: dict[str, str] | None = None
_WORKER_DEVICE: str | None = None


def _worker_init(root: str, device: str) -> None:
    global _WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, _WORKER_IDENTITY, _WORKER_DEVICE
    _WORKER_ROOT = Path(root)
    _WORKER_CONFIG = _config(_WORKER_ROOT)
    _WORKER_IDENTITY = _identity(_WORKER_ROOT)
    _WORKER_STORE = MainlandStore(_WORKER_ROOT)
    _WORKER_DEVICE = device
    torch.set_num_threads(1)


def _worker(payload: tuple[Any, ...]) -> str:
    _require(all(value is not None for value in (_WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, _WORKER_IDENTITY, _WORKER_DEVICE)), "worker_uninitialized")
    mode, *values = payload
    if mode == "pretrain":
        _, receipt = run_pretraining_task(_WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, _WORKER_IDENTITY, *values, _WORKER_DEVICE)
        return receipt["shared_state_digest"]
    if mode == "selection":
        receipt = run_selection_task(_WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, _WORKER_IDENTITY, *values, _WORKER_DEVICE)
        return receipt["parquet_sha256"]
    if mode == "final":
        receipt = run_final_task(_WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, _WORKER_IDENTITY, *values, _WORKER_DEVICE)
        return receipt["parquet_sha256"]
    raise Goal046Error("worker_mode_invalid")


def _execute(executor: ProcessPoolExecutor, stage: str, tasks: Sequence[tuple[Any, ...]]) -> None:
    futures = [executor.submit(_worker, task) for task in tasks]
    for completed, future in enumerate(as_completed(futures), 1):
        future.result()
        if completed == 1 or completed % 10 == 0 or completed == len(tasks):
            print(json.dumps({"stage": stage, "completed": completed, "total": len(tasks)}), flush=True)


def _selection_pretraining_tasks(config: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    seed = config["lifecycle"]["architecture_selection_seed_labels"][0]
    return [
        ("pretrain", target, fold, architecture["id"], seed)
        for target in config["scope"]["targets"]
        for fold in config["scope"]["folds"]
        for architecture in config["design"]["architecture_candidates"]
    ]


def _selection_tasks(config: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    seed = config["lifecycle"]["architecture_selection_seed_labels"][0]
    return [
        ("selection", target, fold, architecture["id"], seed)
        for target in config["scope"]["targets"]
        for fold in config["scope"]["folds"]
        for architecture in config["design"]["architecture_candidates"]
    ]


def _remaining_pretraining_tasks(config: Mapping[str, Any], architecture: str) -> list[tuple[Any, ...]]:
    selection_seeds = set(config["lifecycle"]["architecture_selection_seed_labels"])
    return [
        ("pretrain", target, fold, architecture, seed)
        for target in config["scope"]["targets"]
        for fold in config["scope"]["folds"]
        for seed in config["design"]["seed_labels"]
        if seed not in selection_seeds
    ]


def _final_tasks(config: Mapping[str, Any], architecture: str) -> list[tuple[Any, ...]]:
    return [
        ("final", architecture, target, fraction, ladder, fold, seed)
        for target, fraction, ladder in _endpoint_tasks(config)
        for fold in config["scope"]["folds"]
        for seed in config["design"]["seed_labels"]
    ]


def _goal044_task(summary: Mapping[str, Any], target: str, fraction: int, ladder: str) -> Mapping[str, Any]:
    matches = [row for row in summary["tasks"] if row["target"] == target and row["fraction"] == fraction and row["ladder"] == ladder]
    _require(len(matches) == 1, "goal044_comparison_missing")
    return matches[0]


def _goal044_q_authority(root: Path, config: Mapping[str, Any], target: str) -> tuple[str, str, list[str]]:
    summary = _read_json(root / config["bindings"]["goal044_summary"]["path"])
    selected = _goal044_task(summary, target, 100, "full")
    family = selected["best_non_null_family"]
    selected_family = selected["families"][family]["selected"]
    return family, selected_family["candidate_id"], list(selected_family["seed_labels"])


def _q_conventional_paths(root: Path, target: str) -> tuple[Path, Path]:
    directory = root / "data/processed/dsdm/goal046-strict-mainland-dsdm/q_conventional"
    stem = slug(target)
    return directory / f"{stem}.json", directory / f"{stem}.parquet"


def _strict_q_conventional(root: Path, store: MainlandStore, config: Mapping[str, Any], target: str) -> dict[str, Any]:
    family, candidate_id, seeds = _goal044_q_authority(root, config, target)
    goal044_config = _read_json(root / config["bindings"]["goal044_config"]["path"])
    prepared = []
    for fold in config["scope"]["folds"]:
        q_scores = _q_surface(root, target, fold)
        prepared.append(_prepare_fold(store, goal044_config, target, 100, "full", fold, q_scores))
    result = _evaluate_candidate(
        goal044_config, target, 100, "full", family, candidate_id, seeds, prepared, q=True
    )
    return {
        "identity": _identity(root), "id": "strict_q_linear", "family": family, "candidate_id": candidate_id,
        "candidate_retuned": False, "seed_labels": list(seeds), "metrics": result["metrics"],
        "physical_fits": result["physical_fits"], "runtime_seconds": result["runtime_seconds"],
        "q_surface_digests": {
            str(fold): _read_json(_q_paths(root, target, fold)[0])["parquet_sha256"]
            for fold in config["scope"]["folds"]
        },
        "_folds": result["folds"],
    }


def _write_q_conventional_cache(root: Path, target: str, receipt: Mapping[str, Any]) -> None:
    json_path, parquet_path = _q_conventional_paths(root, target)
    folds = receipt["_folds"]
    rows = [
        {"cell_id": cell, "fold": int(fold["fold"]), "y": int(y), "score": float(score)}
        for fold in folds
        for cell, y, score in zip(fold["cell_ids"], fold["y"], fold["score"], strict=True)
    ]
    _atomic_parquet(parquet_path, pa.Table.from_pylist(rows, schema=Q_CONVENTIONAL_SCHEMA))
    public = {key: value for key, value in receipt.items() if key != "_folds"}
    _atomic_json(json_path, {
        **public,
        "key": {"identity": dict(receipt["identity"]), "target": target, "fraction": 100, "ladder": "full", "family": receipt["family"], "candidate_id": receipt["candidate_id"], "seed_labels": receipt["seed_labels"]},
        "prediction_rows": len(rows), "prediction_parquet_sha256": sha256_file(parquet_path),
    })


def _load_verified_q_conventional(
    root: Path, store: MainlandStore, config: Mapping[str, Any], target: str
) -> dict[str, Any]:
    json_path, parquet_path = _q_conventional_paths(root, target)
    receipt = _read_json(json_path)
    identity = _identity(root)
    family, candidate_id, seed_labels = _goal044_q_authority(root, config, target)
    _require(receipt.get("identity") == identity, "q_conventional_identity_drift")
    _require(
        receipt.get("family") == family
        and receipt.get("candidate_id") == candidate_id
        and receipt.get("seed_labels") == seed_labels,
        "q_conventional_authority_drift",
    )
    expected_key = {
        "identity": dict(identity), "target": target, "fraction": 100,
        "ladder": "full", "family": family,
        "candidate_id": candidate_id, "seed_labels": seed_labels,
    }
    _require(receipt.get("key") == expected_key, "q_conventional_key_drift")
    _require(receipt.get("prediction_parquet_sha256") == sha256_file(parquet_path), "q_conventional_prediction_digest_mismatch")
    table = pq.read_table(parquet_path).combine_chunks()
    _require(table.schema == Q_CONVENTIONAL_SCHEMA, "q_conventional_prediction_schema_invalid")
    _require(table.num_rows == receipt.get("prediction_rows"), "q_conventional_prediction_rows_invalid")
    expected_folds = {int(fold) for fold in config["scope"]["folds"]}
    observed_folds = {int(fold) for fold in table["fold"].to_pylist()}
    _require(observed_folds == expected_folds, "q_conventional_fold_inventory_invalid")
    folds = []
    consumed_rows = 0
    for fold in config["scope"]["folds"]:
        fold_table = table.filter(pc.equal(table["fold"], fold)).sort_by("cell_id")
        authoritative = store.response_rows(target, fold, "validation")
        cells = tuple(fold_table["cell_id"].to_pylist())
        y = fold_table["y"].to_numpy(zero_copy_only=False).astype(np.int8)
        scores = fold_table["score"].to_numpy(zero_copy_only=False).astype(np.float64)
        _require(cells == authoritative.cell_ids and np.array_equal(y, authoritative.y), "q_conventional_held_binding_invalid")
        _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "q_conventional_scores_invalid")
        consumed_rows += len(fold_table)
        folds.append({"fold": fold, "y": y, "score": scores})
    _require(consumed_rows == table.num_rows, "q_conventional_rows_unconsumed")
    metrics = summarize_oof(folds)
    _require(metrics == receipt.get("metrics"), "q_conventional_metrics_replay_mismatch")
    for fold in config["scope"]["folds"]:
        _q_surface(root, target, fold)
        q_receipt_path, q_parquet_path = _q_paths(root, target, fold)
        q_receipt = _read_json(q_receipt_path)
        q_digest = sha256_file(q_parquet_path)
        _require(q_receipt.get("parquet_sha256") == q_digest, "q_conventional_q_binding_invalid")
        _require(receipt["q_surface_digests"].get(str(fold)) == q_digest, "q_conventional_q_binding_invalid")
    return receipt


def _prepare_q_conventional(root: Path, store: MainlandStore, config: Mapping[str, Any]) -> None:
    for target in config["scope"]["targets"]:
        json_path, parquet_path = _q_conventional_paths(root, target)
        if json_path.is_file() and parquet_path.is_file():
            try:
                _load_verified_q_conventional(root, store, config, target)
                continue
            except Goal046Error:
                pass
        _write_q_conventional_cache(root, target, _strict_q_conventional(root, store, config, target))


def aggregate_final(root: Path, config: Mapping[str, Any], identity: Mapping[str, str], selection: Mapping[str, Any], *, write: bool = True) -> dict[str, Any]:
    architecture = selection["selected_architecture"]
    goal044 = _read_json(root / config["bindings"]["goal044_summary"]["path"])
    arms = config["design"]["arms"]
    store = MainlandStore(root)
    results: list[dict[str, Any]] = []
    for target, fraction, ladder in _endpoint_tasks(config):
        arm_metrics: dict[str, Any] = {}
        for arm in arms:
            averaged_folds = []
            seed_metrics = []
            seed_fold_rows: dict[str, list[dict[str, Any]]] = {seed: [] for seed in config["design"]["seed_labels"]}
            for fold in config["scope"]["folds"]:
                reference_cells = None
                reference_y = None
                seed_scores = []
                for seed in config["design"]["seed_labels"]:
                    key = {"identity": dict(identity), "selected_architecture": architecture, "target": target, "fraction": fraction, "ladder": ladder, "held_fold": fold, "seed_label": seed}
                    stem = _final_stem(target, fraction, ladder, fold, seed)
                    loaded = _load_prediction(root, "final", stem, key)
                    _require(loaded is not None, "final_prediction_missing")
                    table = loaded[1]
                    _validate_held_prediction(store, target, fold, table, arms)
                    cells = tuple(table["cell_id"].to_pylist())
                    y = table["y"].to_numpy(zero_copy_only=False).astype(np.int8)
                    scores = table[arm].to_numpy(zero_copy_only=False).astype(np.float64)
                    if reference_cells is None:
                        reference_cells, reference_y = cells, y
                    _require(cells == reference_cells and np.array_equal(y, reference_y), "seed_prediction_binding_drift")
                    seed_scores.append(scores)
                    seed_fold_rows[seed].append({"fold": fold, "y": y, "score": scores})
                averaged_folds.append({"fold": fold, "y": reference_y, "score": np.mean(seed_scores, axis=0)})
            for seed in config["design"]["seed_labels"]:
                metrics = summarize_oof(seed_fold_rows[seed])
                seed_metrics.append({"seed_label": seed, "mean_fold_roc_auc": metrics["mean_fold_roc_auc"], "pooled_tss": metrics["pooled"]["tss"]})
            arm_metrics[arm] = {"metrics": summarize_oof(averaged_folds), "seed_metrics": seed_metrics}
        conventional = _goal044_task(goal044, target, fraction, ladder)
        best_family = conventional["best_non_null_family"]
        conventional_metrics = conventional["families"][best_family]["selected"]["metrics"]
        q_conventional = _load_verified_q_conventional(root, store, config, target)
        q_conventional_metrics = q_conventional["metrics"]
        primary = arm_metrics[config["design"]["primary_arm"]]["metrics"]["mean_fold_roc_auc"]
        results.append({
            "target": target, "fraction": fraction, "ladder": ladder,
            "endpoint": f"fraction{fraction}/{ladder}", "arms": arm_metrics,
            "goal044_best_conventional": {"family": best_family, "metrics": conventional_metrics},
            "strict_q_conventional": q_conventional,
            "primary_auc_contrasts": {
                "minus_target_only_random_init_resmlp": primary - arm_metrics[arms[0]]["metrics"]["mean_fold_roc_auc"],
                "minus_target_plus_q_linear_resmlp": primary - arm_metrics[arms[1]]["metrics"]["mean_fold_roc_auc"],
                "minus_best_goal044_conventional": primary - conventional_metrics["mean_fold_roc_auc"],
                "minus_strict_q_conventional": primary - q_conventional_metrics["mean_fold_roc_auc"],
            },
        })
    summary = {
        "schema_version": "goal046-summary-v1", "goal_id": config["goal_id"],
        "status": "goal046_ready", "identity": dict(identity), "design": config["design"],
        "architecture_selection": selection, "results": results,
        "totals": {"endpoint_tasks": 5, "final_fold_seed_tasks": 125, "final_target_fits": 500},
        "privacy": config["privacy"],
    }
    if write:
        _atomic_json(root / config["execution"]["tracked_summary"], summary)
    return summary


def run_all(root: Path, workers: int, device: str) -> dict[str, Any]:
    root = root.resolve()
    validate_inputs(root)
    config = _config(root)
    identity = _identity(root)
    _require(workers >= 1 and (device == "cpu" or workers == 1), "device_worker_contract_invalid")
    store = MainlandStore(root)
    _prepare_q_surfaces(root, store, config)
    _prepare_q_conventional(root, store, config)
    del store
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(str(root), device)) as executor:
        _execute(executor, "architecture_pretraining", _selection_pretraining_tasks(config))
        _execute(executor, "architecture_screen", _selection_tasks(config))
        selection = aggregate_selection(root, config, identity)
        print(json.dumps({"stage": "architecture_selected", "selected": selection["selected_architecture"]}), flush=True)
        _execute(executor, "final_pretraining", _remaining_pretraining_tasks(config, selection["selected_architecture"]))
        _execute(executor, "final_contrasts", _final_tasks(config, selection["selected_architecture"]))
    summary = aggregate_final(root, config, identity, selection)
    print(json.dumps({"stage": "complete", "runtime_seconds": time.monotonic() - started}), flush=True)
    return summary


def canary(root: Path, device: str) -> dict[str, Any]:
    root = root.resolve()
    gate = validate_inputs(root)
    config = _config(root)
    identity = _identity(root)
    store = MainlandStore(root)
    spec = config["execution"]["canary"]
    target = spec["target"]
    fold = int(spec["held_fold"])
    q_scores, q_fit = _fit_strict_q(root, store, config, target, fold)
    _write_q_surface(root, target, fold, q_scores, q_fit)
    architecture_id = spec["architecture"]
    seed_label = spec["seed_label"]
    started = time.monotonic()
    state, pretraining = run_pretraining_task(
        root, store, config, identity, target, fold, architecture_id, seed_label, device,
        max_epochs=int(spec["max_epochs"]), patience=int(spec["patience"]), checkpoint=False,
    )
    base = _target_fold_data(root, store, config, target, fold, 100, "full", with_q=False)
    q_data = _target_fold_data(root, store, config, target, fold, 100, "full", with_q=True)
    constants = config["design"]["architecture_constants"]
    common = dict(
        seed=_target_seed(identity, target, 100, "full", fold, architecture_id, seed_label),
        device_name=device, batch_size=int(constants["batch_size"]),
        max_epochs=int(spec["max_epochs"]), patience=int(spec["patience"]),
        min_delta=float(config["lifecycle"]["stopping_min_delta"]),
    )
    architecture = _architecture(config, architecture_id)
    arms = config["design"]["arms"]
    arm_runs = {}
    for arm, data, transferred, frozen in (
        (arms[0], base, None, False), (arms[1], q_data, None, False),
        (arms[2], base, state, True), (arms[3], base, state, False),
    ):
        scores, receipt = fit_target_lifecycle(
            architecture, data.discovery, data.stopping, data.replay, data.held_x,
            transferred_state=transferred, freeze_trunk=frozen, **common,
        )
        arm_runs[arm] = {"fit": receipt, "score_count": len(scores), "score_range": [float(np.min(scores)), float(np.max(scores))]}
    receipt = {
        "schema_version": "goal046-canary-v1", "status": "goal046_canary_ready",
        "identity": identity, "device": device, "gate": gate,
        "case": spec, "pretraining": pretraining, "arms": arm_runs,
        "runtime_seconds": time.monotonic() - started,
        "tasmania_response_rows_read": 0, "tasmania_predictor_rows_used": 0,
    }
    _atomic_json(root / config["execution"]["canary_receipt"], receipt)
    return receipt


def status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = _config(root)
    private = root / config["execution"]["private_root"]
    selection = _selection_result_path(root)
    return {
        "pretraining_receipts": len(list((private / "pretraining").glob("*.json"))) if (private / "pretraining").exists() else 0,
        "expected_pretraining_after_selection": 175,
        "selection_receipts": len(list((private / "selection").glob("*.json"))) if (private / "selection").exists() else 0,
        "expected_selection_receipts": 75,
        "selected_architecture": _read_json(selection).get("selected_architecture") if selection.is_file() else None,
        "final_receipts": len(list((private / "final").glob("*.json"))) if (private / "final").exists() else 0,
        "expected_final_receipts": 125,
        "summary_exists": (root / config["execution"]["tracked_summary"]).is_file(),
    }


def validate_outputs(root: Path) -> dict[str, Any]:
    root = root.resolve()
    validate_inputs(root)
    config = _config(root)
    identity = _identity(root)
    selection = _read_json(_selection_result_path(root))
    _require(selection.get("identity") == identity, "selection_identity_drift")
    replayed_selection = aggregate_selection(root, config, identity, write=False)
    _require(selection == replayed_selection, "selection_replay_mismatch")
    expected = aggregate_final(root, config, identity, selection, write=False)
    observed = _read_json(root / config["execution"]["tracked_summary"])
    _require(observed == expected, "tracked_summary_replay_mismatch")
    return {
        "status": "goal046_ready", "selected_architecture": selection["selected_architecture"],
        "endpoint_tasks": len(expected["results"]), "final_fold_seed_tasks": 125,
        "tasmania_response_rows_read": 0, "tasmania_predictor_rows_used": 0,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate-inputs", "canary", "run", "status", "validate"])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args(argv)
    if args.command == "validate-inputs":
        result = validate_inputs(args.root)
    elif args.command == "canary":
        result = canary(args.root, args.device)
    elif args.command == "run":
        summary = run_all(args.root, args.workers, args.device)
        result = {
            "status": summary["status"],
            "selected_architecture": summary["architecture_selection"]["selected_architecture"],
            "endpoint_tasks": summary["totals"]["endpoint_tasks"],
            "tracked_summary": _config(args.root.resolve())["execution"]["tracked_summary"],
        }
    elif args.command == "status":
        result = status(args.root)
    else:
        result = validate_outputs(args.root)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
