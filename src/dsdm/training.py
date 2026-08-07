"""Deterministic split-scoped fitting primitives for Goal 031."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Sequence
import warnings

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import torch
from torch import nn

from .contracts import ArchitectureSpec
from .models import MultiHeadResidual, ResidualMLP, set_trunk_trainable


class TrainingError(ValueError):
    """Raised when split scope or response provenance is invalid."""


@dataclass(frozen=True)
class Observation:
    species: str
    fold: str
    provenance: str
    label: float | None
    predictors: np.ndarray
    cell_index: int


@dataclass(frozen=True)
class NeuralFitSummary:
    epochs: int
    row_count: int


def derive_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % (2**31 - 1)


def seed_everything(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def validate_auxiliary(
    rows: Sequence[Observation],
    target: str,
    train_folds: set[str],
    auxiliary_species: Sequence[str],
) -> None:
    allowed_species = set(auxiliary_species)
    for row in rows:
        if row.species == target or row.species not in allowed_species:
            raise TrainingError("auxiliary target/species violation")
        if row.fold not in train_folds:
            raise TrainingError("auxiliary fold leakage")
        if row.provenance not in {"presence", "survey_supported_absence"}:
            raise TrainingError("auxiliary provenance violation")
        if row.label not in {0.0, 1.0}:
            raise TrainingError("auxiliary unknown response")
        if row.predictors.shape != (28,) or not np.isfinite(row.predictors).all():
            raise TrainingError("auxiliary predictor contract violation")


def select_auxiliary(
    rows: Iterable[Observation],
    target: str,
    train_folds: set[str],
    auxiliary_species: Sequence[str],
) -> tuple[Observation, ...]:
    allowed = set(auxiliary_species)
    selected = tuple(
        row for row in rows
        if row.species in allowed
        and row.species != target
        and row.fold in train_folds
        and row.provenance in {"presence", "survey_supported_absence"}
        and row.label in {0.0, 1.0}
    )
    validate_auxiliary(selected, target, train_folds, auxiliary_species)
    return selected


def species_balanced_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    species: Sequence[str],
    expected_species: Sequence[str],
) -> torch.Tensor:
    if logits.shape != labels.shape or logits.numel() != len(species):
        raise TrainingError("loss dimensions differ")
    if set(species) != set(expected_species):
        raise TrainingError("species balance set drift")
    losses = nn.functional.binary_cross_entropy_with_logits(logits, labels, reduction="none")
    means = []
    for name in expected_species:
        mask = torch.tensor([item == name for item in species], device=logits.device)
        if not mask.any():
            raise TrainingError("empty auxiliary species")
        means.append(losses[mask].mean())
    return torch.stack(means).mean()


def scale_split(train: np.ndarray, apply: np.ndarray) -> tuple[np.ndarray, np.ndarray, StandardScaler]:
    if train.ndim != 2 or apply.ndim != 2 or train.shape[1] != apply.shape[1]:
        raise TrainingError("scaler dimensions differ")
    scaler = StandardScaler().fit(train)
    return (
        scaler.transform(train).astype(np.float32),
        scaler.transform(apply).astype(np.float32),
        scaler,
    )


def q_linear_sample_weights(species: Sequence[str], expected_species: Sequence[str]) -> np.ndarray:
    if set(species) != set(expected_species) or not species:
        raise TrainingError("q_linear species balance set drift")
    total = len(species)
    group_count = len(expected_species)
    counts = {name: species.count(name) for name in expected_species}
    if any(count == 0 for count in counts.values()):
        raise TrainingError("empty q_linear auxiliary species")
    return np.asarray([total / (group_count * counts[name]) for name in species], dtype=np.float64)


def fit_q_linear(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
    *,
    species: Sequence[str] | None = None,
    expected_species: Sequence[str] | None = None,
) -> LogisticRegression:
    if x.ndim != 2 or x.shape[1] != 28 or y.shape != (x.shape[0],) or set(np.unique(y)) != {0.0, 1.0}:
        raise TrainingError("q_linear training contract violation")
    model = LogisticRegression(
        penalty="elasticnet",
        solver="saga",
        C=1.0,
        l1_ratio=0.5,
        max_iter=2000,
        tol=1e-6,
        random_state=derive_seed("q_linear", seed),
    )
    sample_weight = None
    if species is not None:
        if expected_species is None:
            raise TrainingError("q_linear expected species missing")
        sample_weight = q_linear_sample_weights(species, expected_species)
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="'penalty' was deprecated",
            category=FutureWarning,
            module="sklearn.linear_model._logistic",
        )
        model.fit(x, y, sample_weight=sample_weight)
    return model


def fit_neural_binary(
    model: ResidualMLP,
    x: torch.Tensor,
    y: torch.Tensor,
    spec: ArchitectureSpec,
    seed: int,
    *,
    freeze_trunk: bool = False,
    species: Sequence[str] | None = None,
    expected_species: Sequence[str] | None = None,
) -> NeuralFitSummary:
    if x.dtype != torch.float32 or y.dtype != torch.float32 or x.device.type != "cpu":
        raise TrainingError("neural execution must be CPU float32")
    if y.shape != (x.shape[0],) or not torch.isfinite(x).all() or not torch.isfinite(y).all():
        raise TrainingError("neural training dimensions invalid")
    seed_everything(seed)
    set_trunk_trainable(model, not freeze_trunk)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=0.001,
        weight_decay=spec.weight_decay,
    )
    model.train()
    if freeze_trunk:
        model.stem.eval()
        model.trunk.eval()
        model.final_norm.eval()
        model.head.train()
    for _ in range(12):
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        if species is None:
            loss = nn.functional.binary_cross_entropy_with_logits(logits, y)
        else:
            if expected_species is None:
                raise TrainingError("expected auxiliary species missing")
            loss = species_balanced_loss(logits, y, species, expected_species)
        loss.backward()
        optimizer.step()
    return NeuralFitSummary(epochs=12, row_count=x.shape[0])


def fit_multihead_binary(
    model: MultiHeadResidual,
    x: torch.Tensor,
    y: torch.Tensor,
    species: Sequence[str],
    expected_species: Sequence[str],
    spec: ArchitectureSpec,
    seed: int,
) -> NeuralFitSummary:
    if x.dtype != torch.float32 or y.dtype != torch.float32 or x.device.type != "cpu":
        raise TrainingError("multi-head execution must be CPU float32")
    if y.shape != (x.shape[0],) or len(species) != x.shape[0] or set(species) != set(expected_species):
        raise TrainingError("multi-head training contract violation")
    seed_everything(seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=spec.weight_decay)
    model.train()
    for _ in range(12):
        optimizer.zero_grad(set_to_none=True)
        means = []
        for name in expected_species:
            mask = torch.tensor([item == name for item in species], dtype=torch.bool)
            means.append(nn.functional.binary_cross_entropy_with_logits(model(x[mask], name), y[mask]))
        torch.stack(means).mean().backward()
        optimizer.step()
    return NeuralFitSummary(epochs=12, row_count=x.shape[0])


def copy_shared_trunk(source: nn.Module, target: ResidualMLP) -> None:
    for name in ("stem", "trunk", "final_norm"):
        source_module = getattr(source, name)
        target_module = getattr(target, name)
        target_module.load_state_dict(source_module.state_dict(), strict=True)


def q_deep_scalar(model: ResidualMLP, x: torch.Tensor) -> torch.Tensor:
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(x))
