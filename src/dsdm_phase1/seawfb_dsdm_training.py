"""Bounded indexed neural training primitives for the Goal 052 SEAWFB fit.

The response rows may refer repeatedly to the same retained predictor cell.
``IndexedRows`` keeps the predictor matrix unique and stores only the row to
cell index on the device.  The resulting minibatches are otherwise identical
to the dense mainland lifecycle.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import time
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import nn

from dsdm.contracts import ArchitectureSpec
from dsdm.models import MultiHeadResidual, ResidualMLP, set_trunk_trainable

from .mainland_dsdm import (
    architecture_spec,
    load_shared_state,
    resolve_device,
    seed_all,
    shared_state,
    state_digest,
)
from .seawfb_dsdm_data import IndexedRows


class SeawfbTrainingError(ValueError):
    """Raised when indexed neural training inputs or outputs violate the contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SeawfbTrainingError(message)


def _finite_state(state: Mapping[str, torch.Tensor], message: str = "state_nonfinite") -> None:
    _require(isinstance(state, Mapping) and state, "state_invalid")
    _require(all(isinstance(value, torch.Tensor) and torch.isfinite(value).all().item() for value in state.values()), message)


def _digest_module_state(module: nn.Module) -> str:
    return state_digest(module.state_dict())


def _head_state(model: ResidualMLP | MultiHeadResidual) -> dict[str, torch.Tensor]:
    if isinstance(model, ResidualMLP):
        return {f"head.{name}": value for name, value in model.head.state_dict().items()}
    return {
        f"heads.{head}.{name}": value
        for head, module in model.heads.items()
        for name, value in module.state_dict().items()
    }


def _shared_digest(model: ResidualMLP | MultiHeadResidual) -> str:
    if isinstance(model, MultiHeadResidual):
        return state_digest(shared_state(model))
    state: dict[str, torch.Tensor] = {}
    for module_name in ("stem", "trunk", "final_norm"):
        for name, value in getattr(model, module_name).state_dict().items():
            state[f"{module_name}.{name}"] = value.detach().cpu().clone()
    return state_digest(state)


@dataclass(frozen=True)
class _IndexedTensors:
    features: torch.Tensor
    indices: torch.Tensor
    y: torch.Tensor
    weights: torch.Tensor
    head: torch.Tensor


def _validate_rows(rows: IndexedRows, width: int | None = None, *, require_heads: bool = False) -> int:
    _require(isinstance(rows, IndexedRows), "indexed_rows_invalid")
    _require(rows.features.ndim == 2 and rows.features.shape[1] > 0, "indexed_feature_width_invalid")
    if width is not None:
        _require(rows.features.shape[1] == width, "indexed_feature_width_drift")
    _require(len(rows.indices) == len(rows.y) and len(rows.indices) > 0, "indexed_row_count_invalid")
    if require_heads:
        _require(rows.head_index is not None and rows.weights is not None, "indexed_balance_missing")
    return int(rows.features.shape[1])


def _indexed_tensors(rows: IndexedRows, device: torch.device, width: int | None = None,
                     *, require_heads: bool = False) -> _IndexedTensors:
    _validate_rows(rows, width, require_heads=require_heads)
    # The feature matrix is transferred once.  Each observation only carries
    # its integer cell index; this is the bounded-memory path for many heads.
    features = torch.from_numpy(np.ascontiguousarray(rows.features, dtype=np.float32)).to(device)
    indices = torch.from_numpy(np.ascontiguousarray(rows.indices, dtype=np.int64)).to(device)
    y = torch.from_numpy(np.ascontiguousarray(rows.y, dtype=np.float32)).to(device)
    weights = torch.ones(len(rows.y), dtype=torch.float32, device=device) if rows.weights is None else torch.from_numpy(np.ascontiguousarray(rows.weights, dtype=np.float32)).to(device)
    head = torch.empty(0, dtype=torch.long, device=device) if rows.head_index is None else torch.from_numpy(np.ascontiguousarray(rows.head_index, dtype=np.int64)).to(device)
    _require(bool(torch.isfinite(features).all()), "indexed_features_nonfinite")
    _require(bool(torch.isfinite(y).all() & torch.isfinite(weights).all()), "indexed_values_nonfinite")
    return _IndexedTensors(features, indices, y, weights, head)


def _configure(model: nn.Module, freeze_trunk: bool) -> None:
    model.train()
    if isinstance(model, ResidualMLP):
        set_trunk_trainable(model, not freeze_trunk)
        if freeze_trunk:
            model.stem.eval()
            model.trunk.eval()
            model.final_norm.eval()
            model.head.train()


def _logits(model: nn.Module, x: torch.Tensor, head: torch.Tensor,
            head_names: Sequence[str] | None) -> torch.Tensor:
    if head_names is None:
        _require(isinstance(model, ResidualMLP) and head.numel() == 0, "target_model_contract_invalid")
        return model(x)
    _require(isinstance(model, MultiHeadResidual) and len(head_names) == len(model.heads), "multihead_model_contract_invalid")
    encoded = model.encode(x)
    weights = torch.stack([model.heads[name].weight.squeeze(0) for name in head_names])
    biases = torch.stack([model.heads[name].bias.squeeze(0) for name in head_names])
    return torch.sum(encoded * weights[head], dim=1) + biases[head]


def _weighted_loss(logits: torch.Tensor, y: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    losses = nn.functional.binary_cross_entropy_with_logits(logits, y, reduction="none")
    value = torch.mean(losses * weights)
    _require(bool(torch.isfinite(value)), "training_loss_nonfinite")
    return value


def _train_rows(model: nn.Module, rows: IndexedRows, spec: ArchitectureSpec, seed: int,
                device: torch.device, epochs: int, batch_size: int,
                head_names: Sequence[str] | None, freeze_trunk: bool) -> None:
    _require(epochs >= 1 and batch_size >= 1, "training_budget_invalid")
    _configure(model, freeze_trunk)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=0.001, weight_decay=spec.weight_decay,
    )
    tensors = _indexed_tensors(rows, device, require_heads=head_names is not None)
    generator = np.random.default_rng(seed)
    for _ in range(epochs):
        order = generator.permutation(len(rows.y))
        for start in range(0, len(order), batch_size):
            batch = torch.from_numpy(order[start:start + batch_size]).to(device)
            row_index = tensors.indices[batch]
            optimizer.zero_grad(set_to_none=True)
            batch_head = tensors.head[batch] if tensors.head.numel() else tensors.head
            loss = _weighted_loss(
                _logits(model, tensors.features[row_index], batch_head, head_names),
                tensors.y[batch], tensors.weights[batch],
            )
            loss.backward()
            optimizer.step()


def _stopping_loss_tensors(model: nn.Module, tensors: _IndexedTensors,
                           row_count: int, batch_size: int,
                           head_names: Sequence[str] | None) -> float:
    _require(batch_size >= 1, "training_budget_invalid")
    model.eval()
    weighted_sum = 0.0
    weight_sum = 0.0
    with torch.no_grad():
        for start in range(0, row_count, batch_size):
            stop = min(start + batch_size, row_count)
            batch = slice(start, stop)
            row_index = tensors.indices[batch]
            batch_head = tensors.head[batch] if tensors.head.numel() else tensors.head
            losses = nn.functional.binary_cross_entropy_with_logits(
                _logits(model, tensors.features[row_index], batch_head, head_names),
                tensors.y[batch], reduction="none",
            )
            weighted_sum += float(torch.sum(losses * tensors.weights[batch]).detach().cpu())
            weight_sum += float(torch.sum(tensors.weights[batch]).detach().cpu())
    _require(weight_sum > 0 and np.isfinite(weighted_sum), "stopping_loss_invalid")
    result = weighted_sum / weight_sum
    _require(np.isfinite(result), "stopping_loss_nonfinite")
    return result


def _stopping_loss(model: nn.Module, rows: IndexedRows, device: torch.device,
                   batch_size: int, head_names: Sequence[str] | None) -> float:
    """Evaluate a role, retaining the indexed feature matrix for one pass."""
    tensors = _indexed_tensors(rows, device, require_heads=head_names is not None)
    return _stopping_loss_tensors(model, tensors, len(rows.y), batch_size, head_names)


def _select_epoch(model: nn.Module, discovery: IndexedRows, stopping: IndexedRows,
                  spec: ArchitectureSpec, seed: int, device: torch.device,
                  batch_size: int, max_epochs: int, patience: int, min_delta: float,
                  head_names: Sequence[str] | None, freeze_trunk: bool) -> tuple[int, int, float, list[float]]:
    _require(max_epochs >= 1 and 1 <= patience <= max_epochs and min_delta >= 0, "stopping_budget_invalid")
    _configure(model, freeze_trunk)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=0.001, weight_decay=spec.weight_decay,
    )
    tensors = _indexed_tensors(discovery, device, require_heads=head_names is not None)
    stopping_tensors = _indexed_tensors(stopping, device, require_heads=head_names is not None)
    generator = np.random.default_rng(seed)
    best_loss = float("inf")
    best_epoch = 0
    stale = 0
    history: list[float] = []
    for epoch in range(1, max_epochs + 1):
        order = generator.permutation(len(discovery.y))
        for start in range(0, len(order), batch_size):
            batch = torch.from_numpy(order[start:start + batch_size]).to(device)
            row_index = tensors.indices[batch]
            optimizer.zero_grad(set_to_none=True)
            batch_head = tensors.head[batch] if tensors.head.numel() else tensors.head
            loss = _weighted_loss(
                _logits(model, tensors.features[row_index], batch_head, head_names),
                tensors.y[batch], tensors.weights[batch],
            )
            loss.backward()
            optimizer.step()
        stopping_value = _stopping_loss_tensors(model, stopping_tensors, len(stopping.y), batch_size, head_names)
        history.append(stopping_value)
        completed = epoch
        if stopping_value < best_loss - min_delta:
            best_loss = stopping_value
            best_epoch = epoch
            stale = 0
        else:
            stale += 1
        if stale >= patience:
            break
    _require(best_epoch >= 1 and history and np.isfinite(history).all(), "epoch_selection_failed")
    return best_epoch, completed, best_loss, history


def _reset_head(model: ResidualMLP, seed: int, device: torch.device) -> None:
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model.head.reset_parameters()


def _predict(model: ResidualMLP, held_x: np.ndarray, device: torch.device, batch_size: int) -> np.ndarray:
    values = torch.from_numpy(np.ascontiguousarray(held_x, dtype=np.float32)).to(device)
    _require(values.ndim == 2 and values.shape[1] == model.stem.in_features, "held_feature_width_invalid")
    _require(bool(torch.isfinite(values).all()), "held_features_nonfinite")
    model.eval()
    output: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(values), batch_size):
            output.append(torch.sigmoid(model(values[start:start + batch_size])).detach().cpu().numpy())
    scores = np.concatenate(output).astype(np.float64)
    _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "prediction_invalid")
    return scores


def _base_receipt(seed: int, batch_size: int, max_epochs: int, patience: int,
                  min_delta: float, started: float, selected: int,
                  completed: int, replay_epochs: int, best_loss: float,
                  history: list[float], rows: Mapping[str, int],
                  initial_model: str, initial_shared: str, initial_head: str,
                  replay_initial: str, final_model: str, final_shared: str,
                  freeze_trunk: bool, transferred_state: Mapping[str, torch.Tensor] | None,
                  state_finite: bool, freeze_invariant: bool) -> dict[str, Any]:
    replay_seed = seed + 100_000
    receipt: dict[str, Any] = {
        "selected_epoch": selected,
        "discovery_completed_epochs": completed,
        "completed_epochs": completed,
        "replay_epochs": replay_epochs,
        "replay_completed_epochs": replay_epochs,
        "best_stopping_loss": float(best_loss),
        "stopping_history": [float(value) for value in history],
        "stopping_history_finite": bool(np.isfinite(history).all()),
        "stopping_history_length": len(history),
        "discovery_rows": rows["discovery"],
        "stopping_rows": rows["stopping"],
        "replay_rows": rows["replay"],
        "held_rows": rows.get("held", 0),
        "feature_rows": rows.get("features", 0),
        "freeze_trunk": bool(freeze_trunk),
        "freeze_shared_state_invariant": bool(freeze_invariant),
        "transferred": transferred_state is not None,
        "transfer_digest": None if transferred_state is None else state_digest(transferred_state),
        "initial_model_digest": initial_model,
        "initial_shared_digest": initial_shared,
        "initial_head_digest": initial_head,
        "replay_initial_model_digest": replay_initial,
        "final_model_digest": final_model,
        "final_shared_digest": final_shared,
        "model_digest": final_model,
        "state_finite": bool(state_finite),
        "seed": int(seed),
        "fit_seed": int(seed),
        "discovery_shuffle_seed": int(seed),
        "replay_shuffle_seed": int(replay_seed),
        "replay_seed": int(replay_seed),
        "shuffle_seeds": {"discovery": int(seed), "replay": int(replay_seed)},
        "batch_size": int(batch_size),
        "max_epochs": int(max_epochs),
        "patience": int(patience),
        "min_delta": float(min_delta),
        "runtime_seconds": time.monotonic() - started,
    }
    return receipt


def fit_target_lifecycle(
    spec: ArchitectureSpec,
    discovery: IndexedRows,
    stopping: IndexedRows,
    replay: IndexedRows,
    held_x: np.ndarray,
    *,
    seed: int,
    device_name: str,
    batch_size: int,
    max_epochs: int,
    patience: int,
    min_delta: float,
    transferred_state: Mapping[str, torch.Tensor] | None = None,
    freeze_trunk: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    width = _validate_rows(replay)
    for rows in (discovery, stopping):
        _validate_rows(rows, width)
    held = np.asarray(held_x, dtype=np.float32)
    _require(held.ndim == 2 and held.shape[1] == width, "target_feature_width_drift")
    _require(discovery.head_index is None and stopping.head_index is None and replay.head_index is None, "target_head_index_forbidden")
    device = resolve_device(device_name)
    seed_all(seed, device)
    model = ResidualMLP(spec, width).to(device)
    _reset_head(model, seed + 17, device)
    if transferred_state is not None:
        _finite_state(transferred_state, "transfer_state_nonfinite")
        load_shared_state(model, transferred_state)
    _finite_state(model.state_dict())
    initial = deepcopy(model.state_dict())
    initial_model = state_digest(initial)
    initial_shared = _shared_digest(model)
    initial_head = state_digest(_head_state(model))
    started = time.monotonic()
    selected, completed, best_loss, history = _select_epoch(
        model, discovery, stopping, spec, seed, device, batch_size,
        max_epochs, patience, min_delta, None, freeze_trunk,
    )
    replay_model = ResidualMLP(spec, width).to(device)
    replay_model.load_state_dict(initial, strict=True)
    replay_initial = state_digest(replay_model.state_dict())
    _train_rows(replay_model, replay, spec, seed + 100_000, device, selected, batch_size, None, freeze_trunk)
    _finite_state(replay_model.state_dict(), "final_state_nonfinite")
    scores = _predict(replay_model, held, device, batch_size)
    final_model = state_digest(replay_model.state_dict())
    final_shared = _shared_digest(replay_model)
    freeze_invariant = (not freeze_trunk) or final_shared == initial_shared
    _require(freeze_invariant, "frozen_shared_state_changed")
    receipt = _base_receipt(
        seed, batch_size, max_epochs, patience, min_delta, started, selected,
        completed, selected, best_loss, history,
        {"discovery": len(discovery.y), "stopping": len(stopping.y), "replay": len(replay.y), "held": len(held), "features": len(replay.features)},
        initial_model, initial_shared, initial_head, replay_initial, final_model,
        final_shared, freeze_trunk, transferred_state, True, freeze_invariant,
    )
    receipt['head_initialization_seed'] = int(seed + 17)
    return scores, receipt


def fit_pretraining_lifecycle(
    spec: ArchitectureSpec,
    discovery: IndexedRows,
    stopping: IndexedRows,
    replay: IndexedRows,
    head_names: Sequence[str],
    *,
    seed: int,
    device_name: str,
    batch_size: int,
    max_epochs: int,
    patience: int,
    min_delta: float,
) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    names = tuple(head_names)
    _require(len(names) > 1 and len(set(names)) == len(names), "pretraining_heads_invalid")
    width = _validate_rows(replay, require_heads=True)
    for rows in (discovery, stopping):
        _validate_rows(rows, width, require_heads=True)
    for rows in (discovery, stopping, replay):
        _require(set(rows.head_index.tolist()) == set(range(len(names))), "pretraining_head_set_drift")
    device = resolve_device(device_name)
    seed_all(seed, device)
    model = MultiHeadResidual(spec, width, names).to(device)
    _finite_state(model.state_dict())
    initial = deepcopy(model.state_dict())
    initial_model = state_digest(initial)
    initial_shared = _shared_digest(model)
    initial_head = state_digest(_head_state(model))
    started = time.monotonic()
    selected, completed, best_loss, history = _select_epoch(
        model, discovery, stopping, spec, seed, device, batch_size,
        max_epochs, patience, min_delta, names, False,
    )
    replay_model = MultiHeadResidual(spec, width, names).to(device)
    replay_model.load_state_dict(initial, strict=True)
    replay_initial = state_digest(replay_model.state_dict())
    _train_rows(replay_model, replay, spec, seed + 100_000, device, selected, batch_size, names, False)
    _finite_state(replay_model.state_dict(), "final_state_nonfinite")
    state = shared_state(replay_model)
    _finite_state(state, "final_shared_state_nonfinite")
    final_model = state_digest(replay_model.state_dict())
    final_shared = state_digest(state)
    receipt = _base_receipt(
        seed, batch_size, max_epochs, patience, min_delta, started, selected,
        completed, selected, best_loss, history,
        {"discovery": len(discovery.y), "stopping": len(stopping.y), "replay": len(replay.y), "features": len(replay.features)},
        initial_model, initial_shared, initial_head, replay_initial, final_model,
        final_shared, False, None, True, True,
    )
    receipt.update({
        "auxiliary_head_count": len(names),
        "auxiliary_heads": list(names),
        "mean_discovery_weight": float(np.mean(discovery.weights)),
        "mean_stopping_weight": float(np.mean(stopping.weights)),
        "mean_replay_weight": float(np.mean(replay.weights)),
        "within_head_class_balancing": False,
        "shared_state_digest": final_shared,
    })
    return {name: value.detach().cpu().clone() for name, value in state.items()}, receipt


__all__ = [
    "SeawfbTrainingError",
    "architecture_spec",
    "fit_pretraining_lifecycle",
    "fit_target_lifecycle",
]
