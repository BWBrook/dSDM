"""Focused neural fitting primitives for the Goal 045 mainland experiment."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import time
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import nn

from dsdm.contracts import ArchitectureSpec
from dsdm.models import MultiHeadResidual, ResidualMLP, set_trunk_trainable


class MainlandDsdmError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MainlandDsdmError(message)


@dataclass(frozen=True)
class NeuralDataset:
    x: np.ndarray
    y: np.ndarray
    head_index: np.ndarray | None = None
    weights: np.ndarray | None = None

    def __post_init__(self) -> None:
        x = np.asarray(self.x, dtype=np.float32)
        y = np.asarray(self.y, dtype=np.float32)
        _require(x.ndim == 2 and len(x) > 0, "dataset_predictors_invalid")
        _require(y.shape == (len(x),) and np.isin(y, [0, 1]).all(), "dataset_response_invalid")
        _require(np.isfinite(x).all() and np.isfinite(y).all(), "dataset_nonfinite")
        head_index = None if self.head_index is None else np.asarray(self.head_index, dtype=np.int64)
        weights = None if self.weights is None else np.asarray(self.weights, dtype=np.float32)
        if head_index is not None:
            _require(head_index.shape == y.shape and np.min(head_index) >= 0, "dataset_head_index_invalid")
        if weights is not None:
            _require(weights.shape == y.shape and np.isfinite(weights).all() and np.all(weights > 0), "dataset_weights_invalid")
        object.__setattr__(self, "x", np.ascontiguousarray(x))
        object.__setattr__(self, "y", np.ascontiguousarray(y))
        object.__setattr__(self, "head_index", None if head_index is None else np.ascontiguousarray(head_index))
        object.__setattr__(self, "weights", None if weights is None else np.ascontiguousarray(weights))


def architecture_spec(row: Mapping[str, Any]) -> ArchitectureSpec:
    return ArchitectureSpec(
        str(row["id"]), int(row["blocks"]), int(row["width"]),
        int(row["bottleneck"]), "constant", float(row["dropout"]),
        float(row["weight_decay"]),
    )


def resolve_device(name: str) -> torch.device:
    _require(name in {"cpu", "cuda", "mps"}, "device_invalid")
    if name == "cuda":
        _require(torch.cuda.is_available(), "cuda_unavailable")
    if name == "mps":
        _require(torch.backends.mps.is_available(), "mps_unavailable")
    return torch.device(name)


def seed_all(seed: int, device: torch.device) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def state_digest(state: Mapping[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        value = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(value.numpy().tobytes(order="C"))
    return digest.hexdigest()


def shared_state(model: MultiHeadResidual) -> dict[str, torch.Tensor]:
    state: dict[str, torch.Tensor] = {}
    for module_name in ("stem", "trunk", "final_norm"):
        module = getattr(model, module_name)
        for name, value in module.state_dict().items():
            state[f"{module_name}.{name}"] = value.detach().cpu().clone()
    return state


def load_shared_state(model: ResidualMLP, state: Mapping[str, torch.Tensor]) -> None:
    expected = {
        f"{module_name}.{name}"
        for module_name in ("stem", "trunk", "final_norm")
        for name in getattr(model, module_name).state_dict()
    }
    _require(set(state) == expected, "shared_state_keys_invalid")
    for module_name in ("stem", "trunk", "final_norm"):
        prefix = f"{module_name}."
        values = {name[len(prefix):]: value for name, value in state.items() if name.startswith(prefix)}
        getattr(model, module_name).load_state_dict(values, strict=True)


def equal_head_weights(head_index: np.ndarray, head_count: int) -> np.ndarray:
    index = np.asarray(head_index, dtype=np.int64)
    _require(index.ndim == 1 and len(index) > 0 and set(index.tolist()) == set(range(head_count)), "head_set_invalid")
    counts = np.bincount(index, minlength=head_count).astype(np.float64)
    weights = (len(index) / (head_count * counts[index])).astype(np.float32)
    totals = np.bincount(index, weights=weights.astype(np.float64), minlength=head_count)
    tolerance = 2 * np.finfo(np.float32).eps
    _require(np.allclose(totals, totals[0], rtol=tolerance, atol=0), "head_weight_balance_failed")
    _require(np.isclose(np.mean(weights, dtype=np.float64), 1.0, rtol=tolerance, atol=0), "head_weight_mean_failed")
    return weights


def _tensor_dataset(dataset: NeuralDataset, device: torch.device) -> tuple[torch.Tensor, ...]:
    x = torch.from_numpy(dataset.x).to(device)
    y = torch.from_numpy(dataset.y).to(device)
    head = torch.empty(0, dtype=torch.long, device=device) if dataset.head_index is None else torch.from_numpy(dataset.head_index).to(device)
    weights = torch.ones(len(y), dtype=torch.float32, device=device) if dataset.weights is None else torch.from_numpy(dataset.weights).to(device)
    return x, y, head, weights


def _logits(model: nn.Module, x: torch.Tensor, head_index: torch.Tensor, head_names: Sequence[str] | None) -> torch.Tensor:
    if head_names is None:
        _require(isinstance(model, ResidualMLP) and head_index.numel() == 0, "target_model_contract_invalid")
        return model(x)
    _require(isinstance(model, MultiHeadResidual) and len(head_names) == len(model.heads), "multihead_model_contract_invalid")
    encoded = model.encode(x)
    weights = torch.stack([model.heads[name].weight.squeeze(0) for name in head_names])
    biases = torch.stack([model.heads[name].bias.squeeze(0) for name in head_names])
    return torch.sum(encoded * weights[head_index], dim=1) + biases[head_index]


def _configure(model: nn.Module, freeze_trunk: bool) -> None:
    model.train()
    if isinstance(model, ResidualMLP):
        set_trunk_trainable(model, not freeze_trunk)
        if freeze_trunk:
            model.stem.eval()
            model.trunk.eval()
            model.final_norm.eval()
            model.head.train()


def _train_epochs(
    model: nn.Module,
    dataset: NeuralDataset,
    spec: ArchitectureSpec,
    seed: int,
    device: torch.device,
    epochs: int,
    batch_size: int,
    head_names: Sequence[str] | None,
    freeze_trunk: bool,
) -> None:
    _require(epochs >= 1 and batch_size >= 1, "training_budget_invalid")
    _configure(model, freeze_trunk)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=0.001,
        weight_decay=spec.weight_decay,
    )
    x, y, head, weights = _tensor_dataset(dataset, device)
    generator = np.random.default_rng(seed)
    for _ in range(epochs):
        order = generator.permutation(len(y))
        for start in range(0, len(order), batch_size):
            index = torch.from_numpy(order[start:start + batch_size]).to(device)
            optimizer.zero_grad(set_to_none=True)
            batch_head = head[index] if head.numel() else head
            losses = nn.functional.binary_cross_entropy_with_logits(
                _logits(model, x[index], batch_head, head_names), y[index], reduction="none"
            )
            loss = torch.mean(losses * weights[index])
            _require(bool(torch.isfinite(loss)), "training_loss_nonfinite")
            loss.backward()
            optimizer.step()


def _evaluation_loss(
    model: nn.Module,
    dataset: NeuralDataset,
    device: torch.device,
    batch_size: int,
    head_names: Sequence[str] | None,
) -> float:
    model.eval()
    x, y, head, weights = _tensor_dataset(dataset, device)
    weighted_sum = 0.0
    weight_sum = 0.0
    with torch.no_grad():
        for start in range(0, len(y), batch_size):
            stop = min(start + batch_size, len(y))
            batch_head = head[start:stop] if head.numel() else head
            losses = nn.functional.binary_cross_entropy_with_logits(
                _logits(model, x[start:stop], batch_head, head_names),
                y[start:stop], reduction="none",
            )
            weighted_sum += float(torch.sum(losses * weights[start:stop]).cpu())
            weight_sum += float(torch.sum(weights[start:stop]).cpu())
    _require(weight_sum > 0 and np.isfinite(weighted_sum), "validation_loss_invalid")
    return weighted_sum / weight_sum


def _select_epoch(
    model: nn.Module,
    discovery: NeuralDataset,
    stopping: NeuralDataset,
    spec: ArchitectureSpec,
    seed: int,
    device: torch.device,
    batch_size: int,
    max_epochs: int,
    patience: int,
    min_delta: float,
    head_names: Sequence[str] | None,
    freeze_trunk: bool,
) -> tuple[int, int, float]:
    _require(max_epochs >= 1 and 1 <= patience <= max_epochs and min_delta >= 0, "stopping_budget_invalid")
    _configure(model, freeze_trunk)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=0.001,
        weight_decay=spec.weight_decay,
    )
    x, y, head, weights = _tensor_dataset(discovery, device)
    generator = np.random.default_rng(seed)
    best_loss = float("inf")
    best_epoch = 0
    stale = 0
    completed = 0
    for epoch in range(1, max_epochs + 1):
        order = generator.permutation(len(y))
        for start in range(0, len(order), batch_size):
            index = torch.from_numpy(order[start:start + batch_size]).to(device)
            optimizer.zero_grad(set_to_none=True)
            batch_head = head[index] if head.numel() else head
            losses = nn.functional.binary_cross_entropy_with_logits(
                _logits(model, x[index], batch_head, head_names), y[index], reduction="none"
            )
            loss = torch.mean(losses * weights[index])
            _require(bool(torch.isfinite(loss)), "training_loss_nonfinite")
            loss.backward()
            optimizer.step()
        loss = _evaluation_loss(model, stopping, device, batch_size, head_names)
        completed = epoch
        if loss < best_loss - min_delta:
            best_loss = loss
            best_epoch = epoch
            stale = 0
        else:
            stale += 1
        if stale >= patience:
            break
    _require(best_epoch >= 1 and np.isfinite(best_loss), "epoch_selection_failed")
    return best_epoch, completed, best_loss


def _reset_head(model: ResidualMLP, seed: int, device: torch.device) -> None:
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model.head.reset_parameters()


def _predict(model: ResidualMLP, x: np.ndarray, device: torch.device, batch_size: int) -> np.ndarray:
    values = torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)).to(device)
    model.eval()
    output: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(values), batch_size):
            output.append(torch.sigmoid(model(values[start:start + batch_size])).cpu().numpy())
    scores = np.concatenate(output).astype(np.float64)
    _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "prediction_invalid")
    return scores


def fit_target_lifecycle(
    spec: ArchitectureSpec,
    discovery: NeuralDataset,
    stopping: NeuralDataset,
    replay: NeuralDataset,
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
    _require(discovery.x.shape[1] == stopping.x.shape[1] == replay.x.shape[1] == held_x.shape[1], "target_feature_width_drift")
    _require(discovery.head_index is None and stopping.head_index is None and replay.head_index is None, "target_head_index_forbidden")
    device = resolve_device(device_name)
    seed_all(seed, device)
    model = ResidualMLP(spec, replay.x.shape[1]).to(device)
    _reset_head(model, seed + 17, device)
    if transferred_state is not None:
        load_shared_state(model, transferred_state)
    initial = deepcopy(model.state_dict())
    started = time.monotonic()
    selected_epoch, completed_epochs, best_loss = _select_epoch(
        model, discovery, stopping, spec, seed, device, batch_size,
        max_epochs, patience, min_delta, None, freeze_trunk,
    )
    replay_model = ResidualMLP(spec, replay.x.shape[1]).to(device)
    replay_model.load_state_dict(initial, strict=True)
    _train_epochs(
        replay_model, replay, spec, seed + 100_000, device, selected_epoch,
        batch_size, None, freeze_trunk,
    )
    scores = _predict(replay_model, held_x, device, batch_size)
    receipt = {
        "selected_epoch": selected_epoch,
        "discovery_completed_epochs": completed_epochs,
        "best_stopping_loss": best_loss,
        "discovery_rows": len(discovery.y),
        "stopping_rows": len(stopping.y),
        "replay_rows": len(replay.y),
        "held_rows": len(held_x),
        "freeze_trunk": freeze_trunk,
        "transferred": transferred_state is not None,
        "model_digest": state_digest(replay_model.state_dict()),
        "runtime_seconds": time.monotonic() - started,
    }
    return scores, receipt


def fit_pretraining_lifecycle(
    spec: ArchitectureSpec,
    discovery: NeuralDataset,
    stopping: NeuralDataset,
    replay: NeuralDataset,
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
    for dataset in (discovery, stopping, replay):
        _require(dataset.x.shape[1] == replay.x.shape[1], "pretraining_feature_width_drift")
        _require(dataset.head_index is not None and dataset.weights is not None, "pretraining_balance_missing")
        _require(set(dataset.head_index.tolist()) == set(range(len(names))), "pretraining_head_set_drift")
    device = resolve_device(device_name)
    seed_all(seed, device)
    model = MultiHeadResidual(spec, replay.x.shape[1], names).to(device)
    initial = deepcopy(model.state_dict())
    started = time.monotonic()
    selected_epoch, completed_epochs, best_loss = _select_epoch(
        model, discovery, stopping, spec, seed, device, batch_size,
        max_epochs, patience, min_delta, names, False,
    )
    replay_model = MultiHeadResidual(spec, replay.x.shape[1], names).to(device)
    replay_model.load_state_dict(initial, strict=True)
    _train_epochs(
        replay_model, replay, spec, seed + 100_000, device, selected_epoch,
        batch_size, names, False,
    )
    state = shared_state(replay_model)
    receipt = {
        "selected_epoch": selected_epoch,
        "discovery_completed_epochs": completed_epochs,
        "best_stopping_loss": best_loss,
        "discovery_rows": len(discovery.y),
        "stopping_rows": len(stopping.y),
        "replay_rows": len(replay.y),
        "auxiliary_head_count": len(names),
        "auxiliary_heads": list(names),
        "mean_discovery_weight": float(np.mean(discovery.weights)),
        "mean_stopping_weight": float(np.mean(stopping.weights)),
        "mean_replay_weight": float(np.mean(replay.weights)),
        "within_head_class_balancing": False,
        "shared_state_digest": state_digest(state),
        "runtime_seconds": time.monotonic() - started,
    }
    return state, receipt
