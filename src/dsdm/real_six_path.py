"""Training, execution receipt, and CLI for the Goal034 six-path sentinel."""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence
import warnings

import numpy as np
import scipy
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
import threadpoolctl
from threadpoolctl import threadpool_limits
import torch
from torch import nn

from .contracts import METHODS, SPECIES, ArchitectureSpec
from .models import MultiHeadResidual, ResidualMLP, set_trunk_trainable
from .real_six_path_data import (
    BASE_SEED,
    BundleError,
    ContractError,
    ENDPOINTS,
    ENDPOINT_SLUGS,
    HELD_FOLD,
    RunError,
    RUNTIME_POLICY,
    SentinelConfig,
    SixPathBundle,
    STOPPING_FOLD,
    TARGET,
    _array_digest,
    _canonical,
    _require,
    _sha_bytes,
    build_bundle,
    build_plan,
    export_from_foundation,
    load_bundle,
    load_config,
    save_bundle,
    test_config,
    validate_bundle,
)
def _seed(seed: int, device: torch.device) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def _prepare_device(name: str) -> torch.device:
    device = torch.device(name)
    _require(device.type in {"cpu", "cuda"}, "unsupported device", RunError)
    if device.type == "cuda":
        _require(torch.cuda.is_available(), "CUDA unavailable", RunError)
        selected_device = torch.device("cuda", 0 if device.index is None else device.index)
        required = ":4096:8"
        configured = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
        _require(configured in (None, required), "CUBLAS_WORKSPACE_CONFIG conflict", RunError)
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = required
        torch.cuda.init()
        torch.cuda.set_device(selected_device)
        torch.cuda.reset_peak_memory_stats(selected_device)
    return device


def _runtime_attestation(device: torch.device) -> dict[str, Any]:
    shared = {
        "python_major_minor": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "threadpoolctl": threadpoolctl.__version__,
        "torch_base": torch.__version__.split("+", 1)[0],
        "torch_threads": torch.get_num_threads(),
    }
    return {
        "shared": shared,
        "shared_fingerprint": _sha_bytes(_canonical(shared)),
        "full": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "threadpoolctl": threadpoolctl.__version__,
            "torch": torch.__version__,
            "device": str(device),
            "cuda_runtime": str(torch.version.cuda or "none"),
            "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else "none",
            "torch_threads": torch.get_num_threads(),
        },
    }


def _validate_runtime(config: SentinelConfig, runtime: Mapping[str, Any]) -> None:
    _require(isinstance(runtime, dict) and set(runtime) == {"shared", "shared_fingerprint", "full"}, "runtime attestation schema drift", RunError)
    shared = runtime.get("shared")
    _require(isinstance(shared, dict), "shared runtime attestation missing", RunError)
    _require(set(shared) == set(RUNTIME_POLICY), "shared runtime schema drift", RunError)
    _require(runtime.get("shared_fingerprint") == _sha_bytes(_canonical(shared)), "shared runtime fingerprint mismatch", RunError)
    _require(shared.get("torch_threads") == 1, "torch thread policy drift", RunError)
    full = runtime.get("full")
    expected_full = {
        "python", "platform", "system", "machine", "numpy", "scipy",
        "scikit_learn", "threadpoolctl", "torch", "device", "cuda_runtime",
        "gpu", "torch_threads",
    }
    _require(isinstance(full, dict) and set(full) == expected_full, "full runtime schema drift", RunError)
    _require(
        full["numpy"] == shared["numpy"]
        and full["scipy"] == shared["scipy"]
        and full["scikit_learn"] == shared["scikit_learn"]
        and full["threadpoolctl"] == shared["threadpoolctl"]
        and str(full["torch"]).split("+", 1)[0] == shared["torch_base"]
        and ".".join(str(full["python"]).split(".")[:2]) == shared["python_major_minor"]
        and full["torch_threads"] == shared["torch_threads"],
        "full/shared runtime mismatch",
        RunError,
    )
    if not config.test_only:
        _require(shared == RUNTIME_POLICY, "shared runtime policy mismatch", RunError)


def _state_digest(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _named_state_digest(model: nn.Module, prefixes: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    matched = 0
    for name, value in sorted(model.state_dict().items()):
        if name.startswith(prefixes):
            matched += 1
            digest.update(name.encode("utf-8"))
            digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    _require(matched > 0, "state digest selection empty", RunError)
    return digest.hexdigest()


def _shared_digest(model: nn.Module) -> str:
    return _named_state_digest(model, ("stem.", "trunk.", "final_norm."))


def _head_digest(model: ResidualMLP) -> str:
    return _named_state_digest(model, ("head.",))


def _balanced_loss(
    model: nn.Module,
    x: torch.Tensor,
    y: torch.Tensor,
    species: torch.Tensor | None,
    species_names: Sequence[str],
) -> torch.Tensor:
    if species is None:
        return nn.functional.binary_cross_entropy_with_logits(model(x), y)
    _require(set(species.detach().cpu().tolist()) == set(range(7)), "balanced loss species set drift", RunError)
    losses = []
    for index, name in enumerate(species_names):
        mask = species == index
        logits = model(x[mask], name) if isinstance(model, MultiHeadResidual) else model(x[mask])
        losses.append(nn.functional.binary_cross_entropy_with_logits(logits, y[mask]))
    return torch.stack(losses).mean()


def _configure_modes(model: nn.Module, freeze_shared: bool) -> None:
    model.train()
    if freeze_shared:
        _require(isinstance(model, ResidualMLP), "only a target trunk may be frozen", RunError)
        model.stem.eval()
        model.trunk.eval()
        model.final_norm.eval()
        model.head.train()


def _optimizer(model: nn.Module, spec: ArchitectureSpec) -> torch.optim.AdamW:
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    _require(bool(parameters), "no trainable parameters", RunError)
    return torch.optim.AdamW(
        parameters,
        lr=0.001,
        weight_decay=spec.weight_decay,
        betas=(0.9, 0.999),
        eps=1e-8,
        amsgrad=False,
        foreach=False,
        fused=False,
    )


def _to_device(value: np.ndarray, device: torch.device) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(value)).to(device)


def _train_epochs(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    x: torch.Tensor,
    y: torch.Tensor,
    species: torch.Tensor | None,
    species_names: Sequence[str],
    *,
    epochs: int,
    seed: int,
    freeze_shared: bool,
) -> None:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    for _ in range(epochs):
        _configure_modes(model, freeze_shared)
        if species is not None:
            batches = (torch.arange(len(x), device=x.device),)
        else:
            order = torch.randperm(len(x), generator=generator, device="cpu").to(x.device)
            batches = tuple(order[start : start + 128] for start in range(0, len(order), 128))
        for batch in batches:
            optimizer.zero_grad(set_to_none=True)
            loss = _balanced_loss(
                model,
                x[batch],
                y[batch],
                species[batch] if species is not None else None,
                species_names,
            )
            _require(bool(torch.isfinite(loss)), "non-finite training loss", RunError)
            loss.backward()
            for parameter in model.parameters():
                if parameter.requires_grad:
                    _require(parameter.grad is not None and bool(torch.isfinite(parameter.grad).all()), "non-finite gradient", RunError)
            optimizer.step()
            _require(all(bool(torch.isfinite(parameter).all()) for parameter in model.parameters()), "non-finite parameter", RunError)


@dataclass(frozen=True)
class _Lifecycle:
    model: nn.Module
    selected_epoch: int
    discovery_executed_epochs: int
    stopping_status: str
    initial_model_digest: str
    replay_initial_model_digest: str
    initial_shared_digest: str
    final_shared_digest: str
    initial_head_digest: str
    model_digest: str
    prediction_digest: str
    wall_seconds: float


@dataclass(frozen=True)
class _Discovery:
    selected_epoch: int
    executed_epochs: int
    stopping_status: str
    initial_model_digest: str
    initial_shared_digest: str
    initial_head_digest: str


def _fit_discovery(
    factory: Callable[[], nn.Module], spec: ArchitectureSpec, seed: int, device: torch.device,
    x: np.ndarray, y: np.ndarray, x_stopping: np.ndarray, y_stopping: np.ndarray,
    *, max_epochs: int, patience: int, species_names: Sequence[str],
    species: np.ndarray | None, stopping_species: np.ndarray | None, freeze_shared: bool,
) -> _Discovery:
    _seed(seed, device)
    model = factory().to(device)
    if isinstance(model, ResidualMLP):
        set_trunk_trainable(model, not freeze_shared)
    initial_model = _state_digest(model)
    initial_shared = _shared_digest(model)
    initial_head = _head_digest(model) if isinstance(model, ResidualMLP) else ""
    optimizer = _optimizer(model, spec)
    xt, yt = _to_device(x, device), _to_device(y, device)
    xs, ys = _to_device(x_stopping, device), _to_device(y_stopping, device)
    st = _to_device(species, device) if species is not None else None
    ss = _to_device(stopping_species, device) if stopping_species is not None else None
    generator = torch.Generator(device="cpu").manual_seed(seed)
    best_loss, best_epoch, stale, completed = float("inf"), 0, 0, 0
    patience_stop = False
    for epoch in range(1, max_epochs + 1):
        completed = epoch
        _configure_modes(model, freeze_shared)
        order = torch.arange(len(xt), device=device) if st is not None else torch.randperm(len(xt), generator=generator, device="cpu").to(device)
        batches = (order,) if st is not None else tuple(order[start : start + 128] for start in range(0, len(order), 128))
        for batch in batches:
            optimizer.zero_grad(set_to_none=True)
            loss = _balanced_loss(model, xt[batch], yt[batch], st[batch] if st is not None else None, species_names)
            _require(bool(torch.isfinite(loss)), "non-finite discovery loss", RunError)
            loss.backward()
            _require(all(parameter.grad is not None and bool(torch.isfinite(parameter.grad).all()) for parameter in model.parameters() if parameter.requires_grad), "non-finite gradient", RunError)
            optimizer.step()
            _require(all(bool(torch.isfinite(parameter).all()) for parameter in model.parameters()), "non-finite parameter", RunError)
        model.eval()
        with torch.no_grad():
            value = float(_balanced_loss(model, xs, ys, ss, species_names).item())
        _require(np.isfinite(value), "non-finite stopping loss", RunError)
        if value < best_loss:
            best_loss, best_epoch, stale = value, epoch, 0
        else:
            stale += 1
            if stale >= patience:
                patience_stop = True
                break
    _require(best_epoch >= 1, "no selected epoch", RunError)
    return _Discovery(best_epoch, completed, "patience_stop" if patience_stop else "max_epochs_reached", initial_model, initial_shared, initial_head)


def _prediction_digest(
    model: nn.Module, x: np.ndarray, device: torch.device,
    species: np.ndarray | None, species_names: Sequence[str],
) -> str:
    model.eval()
    xt = _to_device(x, device)
    st = _to_device(species, device) if species is not None else None
    with torch.no_grad():
        if st is None:
            logits = model(xt)
        else:
            logits = torch.empty(len(xt), dtype=torch.float32, device=device)
            for index, name in enumerate(species_names):
                mask = st == index
                logits[mask] = model(xt[mask], name) if isinstance(model, MultiHeadResidual) else model(xt[mask])
        predictions = torch.sigmoid(logits)
    _require(bool(torch.isfinite(predictions).all()), "non-finite prediction", RunError)
    return _array_digest(predictions.detach().cpu().numpy().astype(np.float32, copy=False))


def _neural_lifecycle(
    factory: Callable[[], nn.Module],
    spec: ArchitectureSpec,
    seed: int,
    device: torch.device,
    x_discovery: np.ndarray,
    y_discovery: np.ndarray,
    x_stopping: np.ndarray,
    y_stopping: np.ndarray,
    x_replay: np.ndarray,
    y_replay: np.ndarray,
    x_prediction: np.ndarray,
    *,
    max_epochs: int,
    patience: int,
    species_names: Sequence[str] = (),
    species_discovery: np.ndarray | None = None,
    species_stopping: np.ndarray | None = None,
    species_replay: np.ndarray | None = None,
    species_prediction: np.ndarray | None = None,
    freeze_shared: bool = False,
) -> _Lifecycle:
    started = time.monotonic()
    discovery = _fit_discovery(
        factory, spec, seed, device, x_discovery, y_discovery, x_stopping, y_stopping,
        max_epochs=max_epochs, patience=patience, species_names=species_names,
        species=species_discovery, stopping_species=species_stopping, freeze_shared=freeze_shared,
    )
    _seed(seed, device)
    replay = factory().to(device)
    if isinstance(replay, ResidualMLP):
        set_trunk_trainable(replay, not freeze_shared)
    replay_initial = _state_digest(replay)
    _require(replay_initial == discovery.initial_model_digest, "discovery/replay reset mismatch", RunError)
    xr, yr = _to_device(x_replay, device), _to_device(y_replay, device)
    sr = _to_device(species_replay, device) if species_replay is not None else None
    _train_epochs(
        replay,
        _optimizer(replay, spec),
        xr,
        yr,
        sr,
        species_names,
        epochs=discovery.selected_epoch,
        seed=seed,
        freeze_shared=freeze_shared,
    )
    return _Lifecycle(
        replay,
        discovery.selected_epoch,
        discovery.executed_epochs,
        discovery.stopping_status,
        discovery.initial_model_digest,
        replay_initial,
        discovery.initial_shared_digest,
        _shared_digest(replay),
        discovery.initial_head_digest,
        _state_digest(replay),
        _prediction_digest(replay, x_prediction, device, species_prediction, species_names),
        round(time.monotonic() - started, 6),
    )


def _derive_seed(endpoint: str, purpose: str) -> int:
    payload = f"goal034|{BASE_SEED}|{TARGET}|{HELD_FOLD}|{endpoint}|resmlp13|{purpose}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _q_weights(species: np.ndarray) -> np.ndarray:
    counts = np.bincount(species, minlength=7)
    _require(set(species.tolist()) == set(range(7)) and np.all(counts > 0), "q species set drift", RunError)
    weights = len(species) / (7.0 * counts[species])
    totals = [float(weights[species == index].sum()) for index in range(7)]
    _require(max(totals) - min(totals) <= 1e-12, "q species weights unequal", RunError)
    return weights


def _fit_q_linear(bundle: SixPathBundle) -> tuple[LogisticRegression, dict[str, Any]]:
    x = bundle.arrays["aux_x_replay"]
    y = bundle.arrays["aux_y_replay"]
    species = bundle.arrays["aux_species_replay"]
    model = LogisticRegression(
        penalty="elasticnet",
        solver="saga",
        C=1.0,
        l1_ratio=0.5,
        max_iter=5000,
        tol=1e-5,
        random_state=_derive_seed("auxiliary", "q_linear"),
    )
    started = time.monotonic()
    with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        warnings.filterwarnings("ignore", message="'penalty' was deprecated", category=FutureWarning)
        model.fit(x, y, sample_weight=_q_weights(species))
    _require(not any(issubclass(item.category, ConvergenceWarning) for item in caught), "q_linear convergence warning", RunError)
    n_iter = int(np.max(model.n_iter_))
    _require(0 < n_iter < model.max_iter, "q_linear did not converge before max_iter", RunError)
    digest = hashlib.sha256()
    for value in (model.classes_, model.coef_, model.intercept_):
        digest.update(np.asarray(value).tobytes(order="C"))
    scores = model.predict_proba(bundle.arrays["target_x_assessment"])[:, 1].astype(np.float32)
    _require(np.isfinite(scores).all(), "non-finite q_linear prediction", RunError)
    return model, {
        "artifact_id": "aux/q_linear",
        "kind": "auxiliary",
        "logical_artifacts": 1,
        "physical_fits": 1,
        "selected_epoch": 0,
        "discovery_executed_epochs": 0,
        "replay_epochs": 0,
        "stopping_status": "not_applicable",
        "initial_model_digest": "not_applicable",
        "replay_initial_model_digest": "not_applicable",
        "initial_shared_digest": "not_applicable",
        "final_shared_digest": "not_applicable",
        "initial_head_digest": "not_applicable",
        "model_digest": digest.hexdigest(),
        "prediction_digest": _array_digest(scores),
        "n_iter": n_iter,
        "finite": True,
        "wall_seconds": round(time.monotonic() - started, 6),
    }


def _artifact(identifier: str, kind: str, lifecycle: _Lifecycle) -> dict[str, Any]:
    return {
        "artifact_id": identifier,
        "kind": kind,
        "logical_artifacts": 1,
        "physical_fits": 2,
        "selected_epoch": lifecycle.selected_epoch,
        "discovery_executed_epochs": lifecycle.discovery_executed_epochs,
        "replay_epochs": lifecycle.selected_epoch,
        "stopping_status": lifecycle.stopping_status,
        "initial_model_digest": lifecycle.initial_model_digest,
        "replay_initial_model_digest": lifecycle.replay_initial_model_digest,
        "initial_shared_digest": lifecycle.initial_shared_digest,
        "final_shared_digest": lifecycle.final_shared_digest,
        "initial_head_digest": lifecycle.initial_head_digest or "not_applicable",
        "model_digest": lifecycle.model_digest,
        "prediction_digest": lifecycle.prediction_digest,
        "n_iter": 0,
        "finite": True,
        "wall_seconds": lifecycle.wall_seconds,
    }


def _cpu_state(model: nn.Module) -> dict[str, torch.Tensor]:
    return {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}


def _shared_state(model: nn.Module) -> dict[str, torch.Tensor]:
    return {
        name: value.detach().cpu().clone()
        for name, value in model.state_dict().items()
        if name.startswith(("stem.", "trunk.", "final_norm."))
    }


def _residual_factory(
    spec: ArchitectureSpec,
    input_dim: int,
    *,
    full_state: Mapping[str, torch.Tensor] | None = None,
    shared_state: Mapping[str, torch.Tensor] | None = None,
) -> Callable[[], ResidualMLP]:
    def factory() -> ResidualMLP:
        model = ResidualMLP(spec, input_dim)
        if full_state is not None:
            model.load_state_dict(deepcopy(dict(full_state)), strict=True)
        elif shared_state is not None:
            state = model.state_dict()
            _require(set(shared_state) == {name for name in state if name.startswith(("stem.", "trunk.", "final_norm."))}, "shared transfer inventory mismatch", RunError)
            for name, value in shared_state.items():
                _require(state[name].shape == value.shape, "shared transfer shape mismatch", RunError)
                state[name] = value.detach().clone()
            model.load_state_dict(state, strict=True)
        return model

    return factory


def _scalar_from_neural(model: ResidualMLP, x: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        values = torch.sigmoid(model(_to_device(x, device)))
    _require(bool(torch.isfinite(values).all()), "non-finite q_deep scalar", RunError)
    return values.detach().cpu().numpy().astype(np.float32, copy=False)


def _scalar_from_linear(model: LogisticRegression, x: np.ndarray) -> np.ndarray:
    values = model.predict_proba(x)[:, 1].astype(np.float32)
    _require(np.isfinite(values).all(), "non-finite q_linear scalar", RunError)
    return values


@dataclass(frozen=True)
class _AuxiliaryRun:
    pooled: _Lifecycle
    multihead: _Lifecycle
    q_linear: LogisticRegression
    artifacts: tuple[dict[str, Any], ...]


def _run_auxiliary(bundle: SixPathBundle, config: SentinelConfig, device: torch.device) -> _AuxiliaryRun:
    arrays = bundle.arrays
    spec = config.architecture
    names = tuple(name for name in SPECIES if name != TARGET)
    pooled = _neural_lifecycle(
        _residual_factory(spec, 77), spec, _derive_seed("auxiliary", "pooled"), device,
        arrays["aux_x_discovery"], arrays["aux_y_discovery"],
        arrays["aux_x_stopping"], arrays["aux_y_stopping"],
        arrays["aux_x_replay"], arrays["aux_y_replay"],
        arrays["target_x_assessment"],
        max_epochs=config.max_epochs, patience=config.patience,
        species_names=names,
        species_discovery=arrays["aux_species_discovery"],
        species_stopping=arrays["aux_species_stopping"],
        species_replay=arrays["aux_species_replay"],
    )
    multi = _neural_lifecycle(
        lambda: MultiHeadResidual(spec, 77, names), spec, _derive_seed("auxiliary", "multihead"), device,
        arrays["aux_x_discovery"], arrays["aux_y_discovery"],
        arrays["aux_x_stopping"], arrays["aux_y_stopping"],
        arrays["aux_x_replay"], arrays["aux_y_replay"],
        arrays["aux_x_replay"],
        max_epochs=config.max_epochs, patience=config.patience,
        species_names=names,
        species_discovery=arrays["aux_species_discovery"],
        species_stopping=arrays["aux_species_stopping"],
        species_replay=arrays["aux_species_replay"],
        species_prediction=arrays["aux_species_replay"],
    )
    q_linear, q_artifact = _fit_q_linear(bundle)
    return _AuxiliaryRun(
        pooled,
        multi,
        q_linear,
        (_artifact("aux/pooled", "auxiliary", pooled), _artifact("aux/multihead", "auxiliary", multi), q_artifact),
    )


def _run_endpoint(
    endpoint: str,
    slug: str,
    bundle: SixPathBundle,
    config: SentinelConfig,
    device: torch.device,
    auxiliary: _AuxiliaryRun,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], _Lifecycle]]:
    arrays = bundle.arrays
    spec = config.architecture
    base = {
        role: (arrays[f"target_{slug}_x_{role}"], arrays[f"target_{slug}_y_{role}"])
        for role in ("discovery", "stopping", "replay")
    }
    assessment = arrays["target_x_assessment"]
    q_linear_x = {
        role: np.column_stack((x, _scalar_from_linear(auxiliary.q_linear, x))).astype(np.float32)
        for role, (x, _) in base.items()
    }
    q_deep_x = {
        role: np.column_stack((x, _scalar_from_neural(auxiliary.pooled.model, x, device))).astype(np.float32)
        for role, (x, _) in base.items()
    }
    plain = {role: value[0] for role, value in base.items()}
    q_linear_assess = np.column_stack((assessment, _scalar_from_linear(auxiliary.q_linear, assessment))).astype(np.float32)
    q_deep_assess = np.column_stack((assessment, _scalar_from_neural(auxiliary.pooled.model, assessment, device))).astype(np.float32)
    factories: dict[str, tuple[Callable[[], ResidualMLP], Mapping[str, np.ndarray], np.ndarray, bool]] = {
        "target_only_resmlp": (_residual_factory(spec, 77), plain, assessment, False),
        "legacy_pooled_finetune": (_residual_factory(spec, 77, full_state=_cpu_state(auxiliary.pooled.model)), plain, assessment, False),
        "multihead_frozen_trunk": (_residual_factory(spec, 77, shared_state=_shared_state(auxiliary.multihead.model)), plain, assessment, True),
        "multihead_full_finetune": (_residual_factory(spec, 77, shared_state=_shared_state(auxiliary.multihead.model)), plain, assessment, False),
        "target_plus_q_linear": (_residual_factory(spec, 78), q_linear_x, q_linear_assess, False),
        "target_plus_q_deep": (_residual_factory(spec, 78), q_deep_x, q_deep_assess, False),
    }
    artifacts: list[dict[str, Any]] = []
    lifecycles: dict[tuple[str, str], _Lifecycle] = {}
    for method in METHODS:
        factory, x_by_role, prediction_x, freeze = factories[method]
        lifecycle = _neural_lifecycle(
            factory, spec, _derive_seed(endpoint, "target"), device,
            x_by_role["discovery"], base["discovery"][1],
            x_by_role["stopping"], base["stopping"][1],
            x_by_role["replay"], base["replay"][1], prediction_x,
            max_epochs=config.max_epochs, patience=config.patience, freeze_shared=freeze,
        )
        lifecycles[(endpoint, method)] = lifecycle
        artifacts.append(_artifact(f"target/{endpoint}/{method}", "target", lifecycle))
    return artifacts, lifecycles


def _run_checks(bundle: SixPathBundle, artifacts: Sequence[Mapping[str, Any]], lifecycles: Mapping[tuple[str, str], _Lifecycle]) -> dict[str, bool]:
    by_id = {str(row["artifact_id"]): row for row in artifacts}
    return {
        "finite": all(row["finite"] for row in artifacts),
        "fit_arithmetic": len(artifacts) == 21 and sum(row["physical_fits"] for row in artifacts) == 41,
        "target_subsets_nested": bundle.metadata["audit"]["subset_nesting_verified"],
        "target_excluded": bundle.metadata["audit"]["target_excluded"],
        "pseudoabsence_free": bundle.metadata["audit"]["pseudoabsence_rows"] == 0,
        "equal_species_contribution": all(max(values) - min(values) <= 1e-12 for values in bundle.metadata["auxiliary_species_total_weights"].values()),
        "target_transfer_head_matched": all(
            lifecycles[(endpoint, "target_only_resmlp")].initial_head_digest
            == lifecycles[(endpoint, "multihead_frozen_trunk")].initial_head_digest
            == lifecycles[(endpoint, "multihead_full_finetune")].initial_head_digest
            for endpoint in ENDPOINTS
        ),
        "frozen_full_initial_matched": all(
            lifecycles[(endpoint, "multihead_frozen_trunk")].initial_model_digest
            == lifecycles[(endpoint, "multihead_full_finetune")].initial_model_digest
            for endpoint in ENDPOINTS
        ),
        "q_initial_matched": all(
            lifecycles[(endpoint, "target_plus_q_linear")].initial_model_digest
            == lifecycles[(endpoint, "target_plus_q_deep")].initial_model_digest
            for endpoint in ENDPOINTS
        ),
        "legacy_starts_from_pooled": all(
            lifecycles[(endpoint, "legacy_pooled_finetune")].initial_model_digest
            == by_id["aux/pooled"]["model_digest"]
            for endpoint in ENDPOINTS
        ),
        "multihead_shared_transfer_matched": all(
            lifecycles[(endpoint, method)].initial_shared_digest
            == by_id["aux/multihead"]["final_shared_digest"]
            for endpoint in ENDPOINTS
            for method in ("multihead_frozen_trunk", "multihead_full_finetune")
        ),
        "frozen_trunk_unchanged": all(
            lifecycles[(endpoint, "multihead_frozen_trunk")].initial_shared_digest
            == lifecycles[(endpoint, "multihead_frozen_trunk")].final_shared_digest
            for endpoint in ENDPOINTS
        ),
    }


def run_sentinel(bundle: SixPathBundle, config: SentinelConfig, *, device: str) -> dict[str, Any]:
    """Execute one bounded 21-artifact run without ecological scoring."""
    validate_bundle(bundle, config)
    target_device = _prepare_device(device)
    torch.set_num_threads(1)
    runtime = _runtime_attestation(target_device)
    _validate_runtime(config, runtime)
    started = time.monotonic()
    auxiliary = _run_auxiliary(bundle, config, target_device)
    artifacts = list(auxiliary.artifacts)
    lifecycles: dict[tuple[str, str], _Lifecycle] = {}
    for endpoint, slug in ENDPOINT_SLUGS.items():
        endpoint_artifacts, endpoint_lifecycles = _run_endpoint(endpoint, slug, bundle, config, target_device, auxiliary)
        artifacts.extend(endpoint_artifacts)
        lifecycles.update(endpoint_lifecycles)

    checks = _run_checks(bundle, artifacts, lifecycles)
    _require(all(checks.values()), "six-path invariant failed", RunError)
    return {
        "schema_version": "goal034-six-path-run-v1",
        "goal_id": "goal034-dsdm-real-six-path-sentinel",
        "status": "pass",
        "config_digest": config.config_digest,
        "bundle_digest": bundle.digest,
        "source_digests": dict(sorted(config.source_digests.items())),
        "source_fingerprint": config.source_fingerprint,
        "architecture": "resmlp13",
        "target": TARGET,
        "held_fold": HELD_FOLD,
        "stopping_fold": STOPPING_FOLD,
        "base_seed": BASE_SEED,
        "device": str(target_device),
        "runtime": runtime,
        "counts": {
            "auxiliary_logical_artifacts": 3,
            "target_logical_artifacts": 18,
            "logical_artifacts": 21,
            "physical_fits": 41,
        },
        "artifacts": artifacts,
        "checks": checks,
        "outer": {"attempted": 0, "opened": 0},
        "resources": _resource_usage(target_device),
        "wall_seconds": round(time.monotonic() - started, 6),
    }


def _resource_usage(device: torch.device) -> dict[str, int]:
    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        rss = peak if platform.system() == "Darwin" else peak * 1024
    except (ImportError, AttributeError):
        rss = 0
    vram = int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else 0
    return {"peak_rss_bytes": rss, "peak_vram_bytes": vram}


def write_run(receipt: Mapping[str, Any], path: str | Path) -> None:
    body = deepcopy(dict(receipt))
    body.pop("receipt_digest", None)
    body["receipt_digest"] = _sha_bytes(_canonical(body))
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".goal034-run-", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(_canonical(body))
    try:
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def _read_run(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunError("invalid run receipt") from exc
    _require(isinstance(value, dict), "run receipt is not an object", RunError)
    claimed = value.get("receipt_digest")
    body = dict(value)
    body.pop("receipt_digest", None)
    _require(isinstance(claimed, str) and claimed == _sha_bytes(_canonical(body)), "run receipt digest mismatch", RunError)
    return value


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def _validate_artifacts(artifacts: Any, config: SentinelConfig) -> list[Mapping[str, Any]]:
    _require(isinstance(artifacts, list) and len(artifacts) == 21, "run artifact inventory drift", RunError)
    expected_ids = ["aux/pooled", "aux/multihead", "aux/q_linear"] + [
        f"target/{endpoint}/{method}" for endpoint in ENDPOINTS for method in METHODS
    ]
    expected_keys = {
        "artifact_id", "kind", "logical_artifacts", "physical_fits", "selected_epoch",
        "discovery_executed_epochs", "replay_epochs", "stopping_status",
        "initial_model_digest", "replay_initial_model_digest", "initial_shared_digest",
        "final_shared_digest", "initial_head_digest", "model_digest",
        "prediction_digest", "n_iter", "finite", "wall_seconds",
    }
    _require([row.get("artifact_id") for row in artifacts] == expected_ids, "run artifact identity drift", RunError)
    for index, row in enumerate(artifacts):
        _require(isinstance(row, dict) and set(row) == expected_keys, "run artifact schema drift", RunError)
        _require(row["logical_artifacts"] == 1 and row["finite"] is True, "run artifact incomplete", RunError)
        _require(type(row["wall_seconds"]) in (int, float) and np.isfinite(row["wall_seconds"]) and row["wall_seconds"] >= 0, "run artifact timing invalid", RunError)
        _require(_is_digest(row["model_digest"]) and _is_digest(row["prediction_digest"]), "run artifact digest invalid", RunError)
        if index == 2:
            _require(row["kind"] == "auxiliary" and row["physical_fits"] == 1, "q artifact role drift", RunError)
            _require(row["selected_epoch"] == row["discovery_executed_epochs"] == row["replay_epochs"] == 0, "q artifact epoch drift", RunError)
            _require(row["stopping_status"] == "not_applicable" and all(row[name] == "not_applicable" for name in ("initial_model_digest", "replay_initial_model_digest", "initial_shared_digest", "final_shared_digest", "initial_head_digest")), "q artifact state drift", RunError)
            _require(type(row["n_iter"]) is int and 0 < row["n_iter"] < 5000, "q convergence evidence invalid", RunError)
            continue
        _require(row["kind"] == ("auxiliary" if index < 2 else "target") and row["physical_fits"] == 2 and row["n_iter"] == 0, "neural artifact role drift", RunError)
        selected, executed, replayed = row["selected_epoch"], row["discovery_executed_epochs"], row["replay_epochs"]
        _require(type(selected) is int and type(executed) is int and type(replayed) is int and 1 <= selected == replayed <= executed <= config.max_epochs, "neural artifact epoch drift", RunError)
        _require(row["stopping_status"] in {"patience_stop", "max_epochs_reached"}, "neural stopping status drift", RunError)
        for name in ("initial_model_digest", "replay_initial_model_digest", "initial_shared_digest", "final_shared_digest"):
            _require(_is_digest(row[name]), "neural state digest invalid", RunError)
        _require(row["initial_model_digest"] == row["replay_initial_model_digest"], "neural reset digest mismatch", RunError)
        head = row["initial_head_digest"]
        _require(_is_digest(head) if index != 1 else head == "not_applicable", "neural head digest invalid", RunError)
    return artifacts


def _validate_transfer_evidence(artifacts: Sequence[Mapping[str, Any]]) -> None:
    by_id = {str(row["artifact_id"]): row for row in artifacts}
    pooled = by_id["aux/pooled"]
    multi = by_id["aux/multihead"]
    for endpoint in ENDPOINTS:
        target = by_id[f"target/{endpoint}/target_only_resmlp"]
        legacy = by_id[f"target/{endpoint}/legacy_pooled_finetune"]
        frozen = by_id[f"target/{endpoint}/multihead_frozen_trunk"]
        full = by_id[f"target/{endpoint}/multihead_full_finetune"]
        q_linear = by_id[f"target/{endpoint}/target_plus_q_linear"]
        q_deep = by_id[f"target/{endpoint}/target_plus_q_deep"]
        _require(legacy["initial_model_digest"] == pooled["model_digest"], "legacy pooled transfer mismatch", RunError)
        _require(frozen["initial_shared_digest"] == full["initial_shared_digest"] == multi["final_shared_digest"], "multihead shared transfer mismatch", RunError)
        _require(frozen["initial_model_digest"] == full["initial_model_digest"], "frozen/full initial mismatch", RunError)
        _require(target["initial_head_digest"] == frozen["initial_head_digest"] == full["initial_head_digest"], "target transfer head mismatch", RunError)
        _require(q_linear["initial_model_digest"] == q_deep["initial_model_digest"], "q initial mismatch", RunError)
        _require(frozen["initial_shared_digest"] == frozen["final_shared_digest"], "frozen trunk drift", RunError)


def _validate_single_run(path: str | Path, config: SentinelConfig, bundle: SixPathBundle) -> dict[str, Any]:
    value = _read_run(path)
    expected_top = {
        "schema_version", "goal_id", "status", "config_digest", "bundle_digest",
        "source_digests", "source_fingerprint", "architecture", "target", "held_fold",
        "stopping_fold", "base_seed", "device", "runtime", "counts", "artifacts",
        "checks", "outer", "resources", "wall_seconds", "receipt_digest",
    }
    _require(set(value) == expected_top, "run receipt schema drift", RunError)
    text = json.dumps(value, sort_keys=True).lower()
    _require(not any(term in text for term in ('"auc"', '"tss"', '"mcc"', '"accuracy"')), "ecological metric in run receipt", RunError)
    _require(value.get("schema_version") == "goal034-six-path-run-v1" and value.get("goal_id") == "goal034-dsdm-real-six-path-sentinel" and value.get("status") == "pass", "run status/schema drift", RunError)
    _require(value.get("config_digest") == config.config_digest and value.get("bundle_digest") == bundle.digest, "run binding mismatch", RunError)
    _require(value.get("source_digests") == dict(sorted(config.source_digests.items())) and value.get("source_fingerprint") == config.source_fingerprint, "run source binding mismatch", RunError)
    _require(value.get("architecture") == "resmlp13" and value.get("target") == TARGET and value.get("held_fold") == HELD_FOLD and value.get("stopping_fold") == STOPPING_FOLD and value.get("base_seed") == BASE_SEED, "run identity drift", RunError)
    _require(value.get("device") in {"cpu", "cuda"} and value.get("runtime", {}).get("full", {}).get("device") == value.get("device"), "run device drift", RunError)
    _validate_runtime(config, value.get("runtime", {}))
    _require(value.get("outer") == {"attempted": 0, "opened": 0}, "run outer access detected", RunError)
    _require(value.get("counts") == {"auxiliary_logical_artifacts": 3, "target_logical_artifacts": 18, "logical_artifacts": 21, "physical_fits": 41}, "run count drift", RunError)
    artifacts = _validate_artifacts(value.get("artifacts"), config)
    _validate_transfer_evidence(artifacts)
    checks = value.get("checks", {})
    _require(isinstance(checks, dict) and set(checks) == {"finite", "fit_arithmetic", "target_subsets_nested", "target_excluded", "pseudoabsence_free", "equal_species_contribution", "target_transfer_head_matched", "frozen_full_initial_matched", "q_initial_matched", "legacy_starts_from_pooled", "multihead_shared_transfer_matched", "frozen_trunk_unchanged"} and all(checks.values()), "run invariant failed", RunError)
    resources = value.get("resources")
    _require(isinstance(resources, dict) and set(resources) == {"peak_rss_bytes", "peak_vram_bytes"} and all(type(item) is int and item >= 0 for item in resources.values()), "run resource evidence invalid", RunError)
    _require(value["device"] == "cuda" or resources["peak_vram_bytes"] == 0, "CPU VRAM evidence drift", RunError)
    _require(type(value.get("wall_seconds")) in (int, float) and np.isfinite(value["wall_seconds"]) and value["wall_seconds"] >= 0, "run wall timing invalid", RunError)
    return value


def validate_run(
    path: str | Path,
    config: SentinelConfig,
    bundle: SixPathBundle,
    *,
    repeat_path: str | Path | None = None,
) -> None:
    validate_bundle(bundle, config)
    value = _validate_single_run(path, config, bundle)
    _require(repeat_path is not None, "deterministic repeat required", RunError)
    repeat = _validate_single_run(repeat_path, config, bundle)
    _require(value["device"] == repeat["device"] and value["runtime"] == repeat["runtime"], "repeat route/runtime mismatch", RunError)
    deterministic_fields = (
        "artifact_id", "selected_epoch", "discovery_executed_epochs", "replay_epochs",
        "stopping_status", "initial_model_digest", "replay_initial_model_digest",
        "initial_shared_digest", "final_shared_digest", "initial_head_digest",
        "model_digest", "prediction_digest", "n_iter",
    )
    left = [tuple(row[name] for name in deterministic_fields) for row in value["artifacts"]]
    right = [tuple(row[name] for name in deterministic_fields) for row in repeat["artifacts"]]
    _require(left == right, "deterministic repeat mismatch", RunError)


def _bundle_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_dir():
        candidates = sorted(path.glob("*.npz"))
        _require(len(candidates) == 1, "bundle directory must contain exactly one npz", BundleError)
        return candidates[0]
    return path


def _write_json(value: Mapping[str, Any], path: str | Path | None) -> None:
    payload = _canonical(dict(value)) + b"\n"
    if path is None:
        print(payload.decode("utf-8"), end="")
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".goal034-json-", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(payload)
    try:
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.real_six_path")
    parser.add_argument("--config", default="config/dsdm_real_six_path_sentinel.json")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--output")
    export = commands.add_parser("export")
    export.add_argument("--root", default=".")
    export.add_argument("--output", required=True)
    bundle_check = commands.add_parser("validate-bundle")
    bundle_check.add_argument("--bundle", required=True)
    run = commands.add_parser("run")
    run.add_argument("--bundle", required=True)
    run.add_argument("--device", choices=("cpu", "cuda"), required=True)
    run.add_argument("--output", required=True)
    run_check = commands.add_parser("validate-run")
    run_check.add_argument("--bundle", required=True)
    run_check.add_argument("--receipt", required=True)
    run_check.add_argument("--repeat", required=True)
    args = parser.parse_args(argv)
    source = Path(args.config).resolve()
    config = load_config(source, root=source.parents[1])
    if args.command == "plan":
        payload = {
            "schema_version": "goal034-plan-v1",
            "goal_id": "goal034-dsdm-real-six-path-sentinel",
            "config_digest": config.config_digest,
            "plan": build_plan(config),
            "outer": {"attempted": 0, "opened": 0},
            "full_lifecycle_authorized": False,
        }
        _write_json(payload, args.output)
        return 0
    if args.command == "export":
        path, bundle = export_from_foundation(config, root=args.root, output=args.output)
        print(json.dumps({"bundle": path.name, "bundle_digest": bundle.digest}, sort_keys=True))
        return 0
    bundle = load_bundle(_bundle_path(args.bundle), config)
    if args.command == "validate-bundle":
        return 0
    if args.command == "run":
        write_run(run_sentinel(bundle, config, device=args.device), args.output)
        return 0
    validate_run(args.receipt, config, bundle, repeat_path=args.repeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
