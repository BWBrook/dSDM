from __future__ import annotations

import numpy as np
import pytest
import torch

from dsdm.real_data import CaseSpec, build_bundle_from_records
from dsdm.real_training import (
    TrainingError,
    _prepare_cuda,
    _resolve_stopping_status,
    train_case,
    train_case_with_predictions,
)
from dsdm.contracts import ArchitectureSpec


def _bundle():
    rows = []
    levels = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
    veg = (1, 2, 3, 4, 5, 7, 9, 10, 11, 15, 16, 17, 18, 19, 21, 22, 24, 25, 26, 27, 29, 31)
    land = (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18)
    for si in range(8):
        for cell in range(25):
            src = "presence" if cell % 2 else "survey_supported_absence"
            rows.append({"species": f"species_{si:02d}", "cell": f"c{cell:03d}", "fold": f"fold{cell % 5:02d}", "y": float(src == "presence"), "source": src, "x": np.full(25, si + cell / 100, dtype=np.float32), "soil_class": levels[cell % 13], "veg_mvg": veg[cell % 22], "landuse_secondary": land[cell % 17]})
    return build_bundle_from_records(rows, CaseSpec("light", "species_00", "fold03", "resmlp00", 31032), strict_scope=False)


def test_training_receipt_is_aggregate_and_finite():
    spec = ArchitectureSpec("resmlp00", 2, 16, 8, "constant", 0.0, 1e-5)
    receipt = train_case(_bundle(), spec, seed=31032, max_epochs=3, patience=2)
    assert receipt.status == "ok"
    assert receipt.outer_attempted == receipt.outer_opened == 0
    assert receipt.prediction_digest and receipt.model_digest
    assert receipt.selected_epoch == receipt.discovery_epochs
    assert receipt.discovery_executed_epochs >= receipt.selected_epoch
    assert receipt.replay_epochs == receipt.selected_epoch
    assert receipt.discovery_initial_state_digest == receipt.replay_initial_state_digest
    assert receipt.initial_model_digest == receipt.discovery_initial_state_digest
    assert receipt.runtime_versions["torch"] == receipt.torch_version
    assert receipt.python_version and receipt.numpy_version and receipt.cuda_runtime is not None
    assert "loss" not in receipt.to_dict()


def test_training_is_repeatable():
    spec = ArchitectureSpec("resmlp00", 2, 16, 8, "constant", 0.0, 1e-5)
    first = train_case(_bundle(), spec, seed=31032, max_epochs=3, patience=2)
    second = train_case(_bundle(), spec, seed=31032, max_epochs=3, patience=2)
    assert first.model_digest == second.model_digest
    assert first.prediction_digest == second.prediction_digest
    assert first.bundle_digest == second.bundle_digest


def test_training_with_predictions_matches_receipt_only_lifecycle():
    spec = ArchitectureSpec("resmlp00", 2, 16, 8, "constant", 0.0, 1e-5)
    receipt, predictions = train_case_with_predictions(_bundle(), spec, seed=31032, max_epochs=3, patience=2)
    receipt_only = train_case(_bundle(), spec, seed=31032, max_epochs=3, patience=2)
    assert predictions.dtype == np.float32
    assert predictions.shape == (_bundle().x_inner_assessment.shape[0],)
    assert np.isfinite(predictions).all()
    assert receipt.model_digest == receipt_only.model_digest
    assert receipt.prediction_digest == receipt_only.prediction_digest


def test_cuda_memory_reset_initializes_and_selects_device(monkeypatch):
    calls = []
    monkeypatch.setattr(torch.cuda, "init", lambda: calls.append("init"))
    monkeypatch.setattr(torch.cuda, "set_device", lambda device: calls.append(("set", str(device))))
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda device: calls.append(("reset", str(device))))
    _prepare_cuda(torch.device("cuda:0"))
    assert calls == ["init", ("set", "cuda:0"), ("reset", "cuda:0")]


def test_stopping_status_keeps_epoch_300_patience_boundary():
    assert _resolve_stopping_status(300, 300, True) == "patience_stop"
    assert _resolve_stopping_status(300, 300, False) == "max_epochs_reached"
    assert _resolve_stopping_status(12, 300, False) is None


def test_epoch_permutation_uses_seeded_cpu_generator(monkeypatch):
    calls = []
    original = torch.randperm

    def traced(*args, **kwargs):
        calls.append((kwargs["generator"].device.type, kwargs["device"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(torch, "randperm", traced)
    spec = ArchitectureSpec("resmlp00", 2, 16, 8, "constant", 0.0, 1e-5)
    train_case(_bundle(), spec, seed=31032, max_epochs=1, patience=1)
    assert calls and all(generator_device == "cpu" and requested_device == "cpu" for generator_device, requested_device in calls)


def test_nonfinite_training_fails_closed(monkeypatch):
    original = torch.nn.Module.__call__

    def nan_call(self, *args, **kwargs):
        if self.__class__.__name__ == "ResidualMLP":
            return torch.full((len(args[0]),), float("nan"), device=args[0].device)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(torch.nn.Module, "__call__", nan_call)
    spec = ArchitectureSpec("resmlp00", 2, 16, 8, "constant", 0.0, 1e-5)
    with pytest.raises(TrainingError, match="non-finite"):
        train_case(_bundle(), spec, seed=31032, max_epochs=1, patience=1)


def test_cuda_workspace_conflict_fails_closed(monkeypatch):
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":16:8")
    with pytest.raises(TrainingError, match="CUBLAS_WORKSPACE_CONFIG"):
        _prepare_cuda(torch.device("cuda:0"))
