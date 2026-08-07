"""Deidentified target-only training for the Goal 032 compute canary.

The trainer consumes only the numeric, deidentified bundle.  Its neural
lifecycle mirrors Goal028: canonical bundle order, a seeded CPU permutation
for each epoch, full stopping-batch BCE, and an exact reset/replay pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
import platform
import random
import time
from typing import Any, Mapping

import numpy as np
import torch
from torch import nn

from .contracts import ARCHITECTURES, ArchitectureSpec
from .models import ResidualMLP


class TrainingError(ValueError):
    """Raised when the remote training contract is invalid."""


@dataclass(frozen=True)
class TrainingReceipt:
    case_id: str
    target: str
    architecture: str
    seed: int
    status: str
    discovery_epochs: int
    replay_epochs: int
    stopping_status: str
    wall_seconds: float
    peak_rss_bytes: int
    peak_vram_bytes: int
    device: str
    torch_version: str
    runtime_fingerprint: str
    python_version: str
    numpy_version: str
    cuda_runtime: str
    model_digest: str
    prediction_digest: str
    bundle_digest: str
    finite_outputs: bool
    outer_attempted: int = 0
    outer_opened: int = 0
    selected_epoch: int = 0
    discovery_executed_epochs: int = 0
    discovery_initial_state_digest: str = ""
    replay_initial_state_digest: str = ""
    initial_model_digest: str = ""
    runtime_versions: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def architecture_by_id(identifier: str) -> ArchitectureSpec:
    for row in ARCHITECTURES:
        if row[0] == identifier:
            return ArchitectureSpec(*row)
    raise TrainingError(f"unknown architecture: {identifier}")


def _seed(seed: int, device: torch.device) -> None:
    """Set every RNG used by the lifecycle before model construction."""
    torch.manual_seed(int(seed))
    np.random.seed(int(seed) % (2**32 - 1))
    random.seed(int(seed))
    if device.type == "cuda":
        torch.cuda.manual_seed_all(int(seed))
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def _prepare_cuda(device: torch.device) -> None:
    required = ":4096:8"
    configured = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    if configured is not None and configured != required:
        raise TrainingError("CUBLAS_WORKSPACE_CONFIG conflicts with Goal032")
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = required
    # Keep this order explicit: initialise, select, then reset the per-device
    # peak counter.  Tests can verify the order without a CUDA runtime.
    torch.cuda.init()
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)


def _digest_state(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _ensure_finite_parameters(model: nn.Module) -> None:
    if any(not torch.isfinite(parameter).all() for parameter in model.parameters()):
        raise TrainingError("non-finite parameter")


def _resolve_stopping_status(completed_epochs: int, max_epochs: int, patience_stop: bool) -> str | None:
    """Resolve status after the loop, preserving a patience stop at max epoch."""
    if patience_stop:
        return "patience_stop"
    if completed_epochs == max_epochs:
        return "max_epochs_reached"
    return None


def _validate_controls(max_epochs: int, patience: int, min_delta: float) -> None:
    if type(max_epochs) is not int or not 1 <= max_epochs <= 300:
        raise TrainingError("epoch budget outside Goal032 range")
    if type(patience) is not int or patience < 1:
        raise TrainingError("patience must be positive")
    if type(min_delta) not in (int, float) or not np.isfinite(min_delta) or min_delta < 0:
        raise TrainingError("min_delta invalid")


def _array_pair(x: Any, y: Any, role: str) -> tuple[np.ndarray, np.ndarray]:
    predictors = np.asarray(x)
    response = np.asarray(y)
    if predictors.ndim != 2 or predictors.shape[1] != 77 or predictors.dtype != np.float32:
        raise TrainingError(f"invalid {role} predictors")
    if response.ndim != 1 or len(response) != len(predictors) or response.dtype != np.float32:
        raise TrainingError(f"invalid {role} response")
    if len(predictors) == 0 or not np.isfinite(predictors).all() or not np.isfinite(response).all() or not np.isin(response, (0.0, 1.0)).all():
        raise TrainingError(f"invalid {role} values")
    # The bundle exporter has already canonicalised row order; preserving that
    # order is important because no identifiers are available remotely.
    return np.array(predictors, dtype=np.float32, copy=True, order="C"), np.array(response, dtype=np.float32, copy=True)


def _optimizer(model: nn.Module, spec: ArchitectureSpec) -> torch.optim.AdamW:
    return torch.optim.AdamW(
        model.parameters(),
        lr=0.001,
        weight_decay=spec.weight_decay,
        betas=(0.9, 0.999),
        eps=1e-8,
        amsgrad=False,
        foreach=False,
        fused=False,
    )


def _fit(
    model: ResidualMLP,
    x: np.ndarray,
    y: np.ndarray,
    xv: np.ndarray,
    yv: np.ndarray,
    spec: ArchitectureSpec,
    seed: int,
    device: torch.device,
    max_epochs: int,
    patience: int,
    min_delta: float,
) -> tuple[int, str, dict[str, torch.Tensor], int]:
    """Run discovery and return selected epoch, status, checkpoint, count."""
    train_x, train_y = _array_pair(x, y, "discovery")
    stop_x, stop_y = _array_pair(xv, yv, "stopping")
    if len(np.unique(stop_y)) < 2:
        raise TrainingError("stopping labels must contain both classes")
    xt = torch.from_numpy(train_x).to(device)
    yt = torch.from_numpy(train_y).to(device)
    xval = torch.from_numpy(stop_x).to(device)
    yval = torch.from_numpy(stop_y).to(device)
    optimizer = _optimizer(model, spec)
    loss_fn = nn.BCEWithLogitsLoss()
    # Goal028 uses a CPU generator even on CUDA; only the resulting indices
    # move to the model's device.
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = 0
    stale = 0
    patience_stop = False
    completed = 0
    batch_size = min(128, len(xt))
    for epoch in range(1, max_epochs + 1):
        completed = epoch
        model.train()
        permutation = torch.randperm(len(xt), generator=generator, device="cpu").to(device)
        for start in range(0, len(xt), batch_size):
            batch = permutation[start : start + batch_size]
            optimizer.zero_grad(set_to_none=True)
            logits = model(xt[batch])
            if not torch.isfinite(logits).all():
                raise TrainingError("non-finite training logits")
            loss = loss_fn(logits, yt[batch])
            if not torch.isfinite(loss):
                raise TrainingError("non-finite loss")
            loss.backward()
            for parameter in model.parameters():
                if parameter.grad is None or not torch.isfinite(parameter.grad).all():
                    raise TrainingError("non-finite gradient")
            optimizer.step()
            if any(not torch.isfinite(parameter).all() for parameter in model.parameters()):
                raise TrainingError("non-finite parameter")
        model.eval()
        with torch.no_grad():
            validation_logits = model(xval)
            if not torch.isfinite(validation_logits).all():
                raise TrainingError("non-finite validation")
            validation_loss = loss_fn(validation_logits, yval)
        if not torch.isfinite(validation_loss):
            raise TrainingError("non-finite validation")
        value = float(validation_loss.item())
        if value < best_loss - min_delta:
            best_loss = value
            best_epoch = epoch
            stale = 0
            best_state = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
        else:
            stale += 1
            if stale >= patience:
                patience_stop = True
                break
    status = _resolve_stopping_status(completed, max_epochs, patience_stop)
    if best_state is None or best_epoch < 1 or status is None:
        raise TrainingError("no finite stopping result")
    model.load_state_dict(best_state, strict=True)
    if any(not torch.isfinite(parameter).all() for parameter in model.parameters()):
        raise TrainingError("non-finite parameter")
    return best_epoch, status, best_state, completed


def _replay(
    model: ResidualMLP,
    x: np.ndarray,
    y: np.ndarray,
    spec: ArchitectureSpec,
    seed: int,
    device: torch.device,
    epochs: int,
) -> None:
    train_x, train_y = _array_pair(x, y, "replay")
    xt = torch.from_numpy(train_x).to(device)
    yt = torch.from_numpy(train_y).to(device)
    optimizer = _optimizer(model, spec)
    loss_fn = nn.BCEWithLogitsLoss()
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    batch_size = min(128, len(xt))
    for _ in range(epochs):
        model.train()
        permutation = torch.randperm(len(xt), generator=generator, device="cpu").to(device)
        for start in range(0, len(xt), batch_size):
            batch = permutation[start : start + batch_size]
            optimizer.zero_grad(set_to_none=True)
            logits = model(xt[batch])
            if not torch.isfinite(logits).all():
                raise TrainingError("non-finite training logits")
            loss = loss_fn(logits, yt[batch])
            if not torch.isfinite(loss):
                raise TrainingError("non-finite loss")
            loss.backward()
            for parameter in model.parameters():
                if parameter.grad is None or not torch.isfinite(parameter.grad).all():
                    raise TrainingError("non-finite gradient")
            optimizer.step()
            if any(not torch.isfinite(parameter).all() for parameter in model.parameters()):
                raise TrainingError("non-finite parameter")


def train_case(
    bundle: Any,
    architecture: ArchitectureSpec | str,
    *,
    seed: int | None = None,
    device: str = "cpu",
    max_epochs: int = 300,
    patience: int = 30,
    min_delta: float = 0.0,
) -> TrainingReceipt:
    """Train discovery, replay selected epochs, and predict the inner held fold."""
    spec = architecture_by_id(architecture) if isinstance(architecture, str) else architecture
    if not hasattr(bundle, "x_discovery") or bundle.x_discovery.shape[1] != 77:
        raise TrainingError("bundle or seed contract")
    if seed is None:
        seed = int(bundle.case.seed) if hasattr(bundle, "case") and hasattr(bundle.case, "seed") else None
    if seed is None:
        raise TrainingError("bundle or seed contract")
    _validate_controls(max_epochs, patience, min_delta)
    seed = int(seed)
    target_device = torch.device(device)
    if target_device.type not in {"cpu", "cuda"}:
        raise TrainingError("unsupported device")
    if target_device.type == "cuda":
        if not torch.cuda.is_available():
            raise TrainingError("CUDA unavailable")
        _prepare_cuda(target_device)
    started = time.monotonic()

    _seed(seed, target_device)
    discovery = ResidualMLP(spec, 77).to(target_device)
    _ensure_finite_parameters(discovery)
    discovery_initial = _digest_state(discovery)
    selected_epoch, stopping_status, _, discovery_completed = _fit(
        discovery,
        bundle.x_discovery,
        bundle.y_discovery,
        bundle.x_stopping,
        bundle.y_stopping,
        spec,
        seed,
        target_device,
        max_epochs,
        patience,
        min_delta,
    )

    # Reset both model and RNG to reproduce the exact discovery start state;
    # replay then fits all four non-held folds for the selected epoch count.
    _seed(seed, target_device)
    replay = ResidualMLP(spec, 77).to(target_device)
    _ensure_finite_parameters(replay)
    replay_initial = _digest_state(replay)
    if replay_initial != discovery_initial:
        raise TrainingError("discovery/replay initial state mismatch")
    _replay(replay, bundle.x_replay, bundle.y_replay, spec, seed, target_device, selected_epoch)
    replay.eval()
    assessment_x, _ = _array_pair(bundle.x_inner_assessment, np.zeros(len(bundle.x_inner_assessment), dtype=np.float32), "assessment")
    with torch.no_grad():
        logits = replay(torch.from_numpy(assessment_x).to(target_device))
        if not torch.isfinite(logits).all():
            raise TrainingError("non-finite prediction")
        predictions = torch.sigmoid(logits)
    if not torch.isfinite(predictions).all() or torch.any(predictions < 0) or torch.any(predictions > 1):
        raise TrainingError("non-finite prediction")
    prediction_array = predictions.detach().cpu().numpy().astype(np.float32, copy=False)
    if not np.isfinite(prediction_array).all():
        raise TrainingError("non-finite prediction")

    vram = int(torch.cuda.max_memory_allocated(target_device)) if target_device.type == "cuda" else 0
    try:
        import resource
        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * (1024 if platform.system() != "Darwin" else 1)
    except (ImportError, AttributeError):
        rss = 0
    from .real_data import bundle_digest
    runtime_versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "device": str(target_device),
        "cuda": str(torch.version.cuda or "none"),
    }
    runtime = hashlib.sha256(json.dumps(runtime_versions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return TrainingReceipt(
        case_id=bundle.case.case_id,
        target=bundle.case.target,
        architecture=spec.id,
        seed=seed,
        status="ok",
        discovery_epochs=selected_epoch,
        replay_epochs=selected_epoch,
        stopping_status=stopping_status,
        wall_seconds=round(time.monotonic() - started, 6),
        peak_rss_bytes=rss,
        peak_vram_bytes=vram,
        device=str(target_device),
        torch_version=torch.__version__,
        runtime_fingerprint=runtime,
        python_version=runtime_versions["python"],
        numpy_version=runtime_versions["numpy"],
        cuda_runtime=runtime_versions["cuda"],
        model_digest=_digest_state(replay),
        prediction_digest=hashlib.sha256(prediction_array.tobytes()).hexdigest(),
        bundle_digest=bundle_digest(bundle),
        finite_outputs=True,
        outer_attempted=0,
        outer_opened=0,
        selected_epoch=selected_epoch,
        discovery_executed_epochs=discovery_completed,
        discovery_initial_state_digest=discovery_initial,
        replay_initial_state_digest=replay_initial,
        initial_model_digest=discovery_initial,
        runtime_versions=runtime_versions,
    )


def write_receipt(receipt: TrainingReceipt, path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(receipt.to_dict(), handle, sort_keys=True, separators=(",", ":"))
