"""Fixed-budget neural fits for the Goal 052 retained-full outer assessment.

This adapter deliberately has no discovery, stopping, or early-stopping role.
It exposes the native indexed-row replay lifecycle with an explicitly supplied
number of epochs and returns CPU checkpoints so the fit can be replayed and
hash-closed by its caller.
"""

from __future__ import annotations

from copy import deepcopy
import time
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from dsdm.contracts import ArchitectureSpec
from dsdm.models import MultiHeadResidual, ResidualMLP

from .mainland_dsdm import (
    resolve_device,
    seed_all,
    shared_state,
    state_digest,
    load_shared_state,
)
from .seawfb_dsdm_data import IndexedRows
from .seawfb_dsdm_training import (
    _finite_state,
    _predict,
    _reset_head,
    _train_rows,
    _validate_rows,
)


class Goal052OuterTrainingError(ValueError):
    """Raised when a fixed outer fit violates the neural training contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Goal052OuterTrainingError(message)


def _cpu_state(state: Mapping[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """Return an independent, finite-checkable CPU copy of a state dict."""
    return deepcopy({name: value.detach().cpu().clone() for name, value in state.items()})


def _validate_budget(epochs: int, batch_size: int) -> None:
    _require(isinstance(epochs, int) and not isinstance(epochs, bool) and epochs >= 1, "training_budget_invalid")
    _require(isinstance(batch_size, int) and not isinstance(batch_size, bool) and batch_size >= 1, "training_budget_invalid")


def _common_receipt(
    *,
    seed: int,
    epochs: int,
    batch_size: int,
    device: torch.device,
    rows: IndexedRows,
    started: float,
    initial_state: Mapping[str, torch.Tensor],
    final_state: Mapping[str, torch.Tensor],
    transferred_state: Mapping[str, torch.Tensor] | None,
    freeze_trunk: bool,
    head_names: Sequence[str] | None,
) -> dict[str, Any]:
    initial_model = state_digest(initial_state)
    final_model = state_digest(final_state)
    initial_shared = _shared_digest_from_state(initial_state, head_names)
    final_shared = _shared_digest_from_state(final_state, head_names)
    initial_head = _head_digest_from_state(initial_state, head_names)
    final_head = _head_digest_from_state(final_state, head_names)
    finite = all(
        isinstance(value, torch.Tensor) and bool(torch.isfinite(value).all())
        for value in final_state.values()
    )
    frozen_invariant = (not freeze_trunk) or initial_shared == final_shared
    _require(finite, "final_state_nonfinite")
    _require(frozen_invariant, "frozen_shared_state_changed")
    replay_seed = seed + 100_000
    transfer_digest = None if transferred_state is None else state_digest(transferred_state)
    receipt: dict[str, Any] = {
        "schema_version": "goal052-outer-fixed-training-v1",
        "fit_mode": "fixed_budget",
        "epochs": int(epochs),
        "epoch_completed": int(epochs),
        "completed_epochs": int(epochs),
        "replay_epochs": int(epochs),
        "replay_completed_epochs": int(epochs),
        "batch_size": int(batch_size),
        "seed": int(seed),
        "base_seed": int(seed),
        "fit_seed": int(seed),
        # Multi-head construction consumes the base initialization stream;
        # target fits explicitly reset their scalar head at seed + 17.
        "head_initialization_seed": int(seed if head_names is not None else seed + 17),
        "head_seed": int(seed if head_names is not None else seed + 17),
        "replay_seed": int(replay_seed),
        "replay_shuffle_seed": int(replay_seed),
        "device": device.type,
        "device_name": device.type,
        "row_count": int(len(rows.y)),
        "replay_rows": int(len(rows.y)),
        "feature_count": int(len(rows.features)),
        "feature_rows": int(len(rows.features)),
        "feature_width": int(rows.features.shape[1]),
        "head_count": 0 if head_names is None else int(len(head_names)),
        "heads": None if head_names is None else list(head_names),
        "transferred": transferred_state is not None,
        "transfer_digest": transfer_digest,
        "freeze_trunk": bool(freeze_trunk),
        "freeze_shared_state_invariant": bool(frozen_invariant),
        "initial_model_digest": initial_model,
        "final_model_digest": final_model,
        "initial_state_digest": initial_model,
        "final_state_digest": final_model,
        "model_digest": final_model,
        "full_state_digest": final_model,
        "initial_shared_digest": initial_shared,
        "final_shared_digest": final_shared,
        "shared_state_digest": final_shared,
        "initial_head_digest": initial_head,
        "final_head_digest": final_head,
        "state_finite": bool(finite),
        "elapsed_seconds": float(time.monotonic() - started),
    }
    receipt["runtime_seconds"] = receipt["elapsed_seconds"]
    receipt["wall_seconds"] = receipt["elapsed_seconds"]
    # This is fixed-budget training, so there is no stopping history or
    # discovery role to report.  Keeping the explicit marker makes accidental
    # reuse of a lifecycle receipt detectable by callers.
    receipt.update({
        "discovery_rows": 0,
        "stopping_rows": 0,
        "early_stopping": False,
        "stopping_history": [],
        "stopping_history_finite": True,
    })
    return receipt


def _shared_digest_from_state(state: Mapping[str, torch.Tensor], head_names: Sequence[str] | None) -> str:
    prefixes = ("stem.", "trunk.", "final_norm.")
    return state_digest({name: value for name, value in state.items() if name.startswith(prefixes)})


def _head_digest_from_state(state: Mapping[str, torch.Tensor], head_names: Sequence[str] | None) -> str:
    prefix = "head." if head_names is None else "heads."
    return state_digest({name: value for name, value in state.items() if name.startswith(prefix)})


def _validate_pretraining_rows(rows: IndexedRows, width: int, head_count: int) -> None:
    _validate_rows(rows, width, require_heads=True)
    _require(set(rows.head_index.tolist()) == set(range(head_count)), "pretraining_head_set_drift")


def fit_pretraining_fixed(
    spec: ArchitectureSpec,
    replay: IndexedRows,
    head_names: Sequence[str],
    *,
    seed: int,
    epochs: int,
    batch_size: int = 128,
    device_name: str = "cpu",
) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor], dict[str, Any]]:
    """Fit a multi-head auxiliary model for exactly ``epochs`` replay epochs."""
    started = time.monotonic()
    _validate_budget(epochs, batch_size)
    names = tuple(head_names)
    _require(len(names) > 1 and len(set(names)) == len(names), "pretraining_heads_invalid")
    width = _validate_rows(replay, require_heads=True)
    _validate_pretraining_rows(replay, width, len(names))
    device = resolve_device(device_name)
    seed_all(seed, device)
    model = MultiHeadResidual(spec, width, names).to(device)
    initial = deepcopy(model.state_dict())
    _finite_state(initial, "initial_state_nonfinite")
    _train_rows(model, replay, spec, seed + 100_000, device, epochs, batch_size, names, False)
    _finite_state(model.state_dict(), "final_state_nonfinite")
    final = _cpu_state(model.state_dict())
    initial_cpu = _cpu_state(initial)
    shared = _cpu_state(shared_state(model))
    _finite_state(final)
    _finite_state(shared, "final_shared_state_nonfinite")
    receipt = _common_receipt(
        seed=seed, epochs=epochs, batch_size=batch_size, device=device,
        rows=replay, started=started, initial_state=initial_cpu,
        final_state=final, transferred_state=None, freeze_trunk=False,
        head_names=names,
    )
    receipt.update({
        "auxiliary_head_count": len(names),
        "auxiliary_heads": list(names),
        "shared_state_digest": state_digest(shared),
        "returned_shared_state_digest": state_digest(shared),
    })
    return deepcopy(final), deepcopy(shared), deepcopy(receipt)


def fit_target_fixed(
    spec: ArchitectureSpec,
    replay: IndexedRows,
    held_x: np.ndarray,
    *,
    seed: int,
    epochs: int,
    batch_size: int = 128,
    device_name: str = "cpu",
    transferred_state: Mapping[str, torch.Tensor] | None = None,
    freeze_trunk: bool = False,
) -> tuple[np.ndarray, dict[str, torch.Tensor], dict[str, Any]]:
    """Fit a target model for exactly ``epochs`` replay epochs and predict."""
    started = time.monotonic()
    _validate_budget(epochs, batch_size)
    width = _validate_rows(replay)
    _require(replay.head_index is None, "target_head_index_forbidden")
    held = np.asarray(held_x, dtype=np.float32)
    _require(held.ndim == 2 and len(held) > 0 and held.shape[1] == width, "target_feature_width_drift")
    _require(np.isfinite(held).all(), "held_features_nonfinite")
    device = resolve_device(device_name)
    seed_all(seed, device)
    model = ResidualMLP(spec, width).to(device)
    _reset_head(model, seed + 17, device)
    if transferred_state is not None:
        _finite_state(transferred_state, "transfer_state_nonfinite")
        load_shared_state(model, transferred_state)
    initial = deepcopy(model.state_dict())
    _finite_state(initial, "initial_state_nonfinite")
    _train_rows(model, replay, spec, seed + 100_000, device, epochs, batch_size, None, freeze_trunk)
    _finite_state(model.state_dict(), "final_state_nonfinite")
    scores = _predict(model, held, device, batch_size).astype(np.float64, copy=True)
    final = _cpu_state(model.state_dict())
    initial_cpu = _cpu_state(initial)
    receipt = _common_receipt(
        seed=seed, epochs=epochs, batch_size=batch_size, device=device,
        rows=replay, started=started, initial_state=initial_cpu,
        final_state=final, transferred_state=transferred_state,
        freeze_trunk=freeze_trunk, head_names=None,
    )
    receipt["held_rows"] = int(len(held))
    receipt["prediction_count"] = int(len(scores))
    receipt["prediction_dtype"] = str(scores.dtype)
    return scores, deepcopy(final), deepcopy(receipt)


__all__ = ["Goal052OuterTrainingError", "fit_pretraining_fixed", "fit_target_fixed"]
