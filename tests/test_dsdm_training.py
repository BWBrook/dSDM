from pathlib import Path

import numpy as np
import pytest
import torch
from torch.nn import functional as F

from dsdm.contracts import load_contract
from dsdm.models import build_residual, clone_state
from dsdm.training import (
    Observation,
    TrainingError,
    copy_shared_trunk,
    fit_neural_binary,
    fit_q_linear,
    q_deep_scalar,
    q_linear_sample_weights,
    scale_split,
    select_auxiliary,
    species_balanced_loss,
    validate_auxiliary,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_contract(ROOT / "config" / "dsdm_synthetic_vertical.json")
SPEC = CONTRACT.architectures[0]


def _row(species, fold, provenance, label, value):
    return Observation(species, fold, provenance, label, np.full(28, value, dtype=np.float32), int(value * 10))


def test_auxiliary_selection_is_leave_target_out_split_scoped_and_pseudoabsence_free():
    target = CONTRACT.species[0]
    rows = [
        _row(target, "fold01", "presence", 1.0, 1),
        _row(CONTRACT.species[1], "fold00", "presence", 1.0, 2),
        _row(CONTRACT.species[1], "fold01", "pseudoabsence", 0.0, 3),
        _row(CONTRACT.species[1], "fold01", "unknown", None, 4),
        _row(CONTRACT.species[1], "fold01", "presence", 1.0, 5),
        _row(CONTRACT.species[1], "fold02", "survey_supported_absence", 0.0, 6),
    ]

    selected = select_auxiliary(rows, target, {"fold01", "fold02"}, CONTRACT.species[1:])
    assert [(row.provenance, row.fold) for row in selected] == [
        ("presence", "fold01"),
        ("survey_supported_absence", "fold02"),
    ]


@pytest.mark.parametrize(
    "tampered",
    [
        _row(CONTRACT.species[0], "fold01", "presence", 1.0, 1),
        _row(CONTRACT.species[1], "fold01", "pseudoabsence", 0.0, 1),
        _row(CONTRACT.species[1], "fold01", "unknown", None, 1),
        _row(CONTRACT.species[1], "fold00", "presence", 1.0, 1),
        Observation(CONTRACT.species[1], "fold01", "presence", 1.0, np.ones(29, dtype=np.float32), 1),
    ],
)
def test_auxiliary_validation_rejects_target_pseudo_unknown_held_fold_and_feature_width(tampered):
    with pytest.raises(TrainingError):
        validate_auxiliary([tampered], CONTRACT.species[0], {"fold01"}, CONTRACT.species[1:])


def test_species_balanced_loss_is_mean_of_species_means_not_row_mean():
    logits = torch.tensor([0.0, 0.0, 0.0, 4.0])
    labels = torch.tensor([0.0, 0.0, 0.0, 0.0])
    species = ("a", "a", "a", "b")
    row_losses = F.binary_cross_entropy_with_logits(logits, labels, reduction="none")

    result = species_balanced_loss(logits, labels, species, ("a", "b"))
    expected = torch.stack((row_losses[:3].mean(), row_losses[3:].mean())).mean()
    assert torch.equal(result, expected)
    assert not torch.equal(result, row_losses.mean())


def test_standard_scaler_is_fitted_only_on_training_predictors():
    train = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)
    apply = np.array([[100.0, 101.0]], dtype=np.float32)

    scaled_train, scaled_apply, scaler = scale_split(train, apply)
    assert np.allclose(scaler.mean_, [1.0, 2.0])
    assert np.allclose(scaled_train.mean(axis=0), 0.0)
    assert np.all(scaled_apply > 90)


def test_q_linear_has_frozen_parameters_and_deterministic_scalar():
    rng = np.random.default_rng(4)
    x = rng.normal(size=(80, 28)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)

    first = fit_q_linear(x, y, 31031)
    second = fit_q_linear(x, y, 31031)
    params = first.get_params()
    assert params["penalty"] == "elasticnet"
    assert params["solver"] == "saga"
    assert params["C"] == 1.0
    assert params["l1_ratio"] == 0.5
    assert params["max_iter"] == 2000
    assert params["tol"] == 1e-6
    assert np.array_equal(first.predict_proba(x), second.predict_proba(x))


def test_q_linear_sample_weights_equalize_species_not_classes():
    species = ("a", "a", "a", "b")
    weights = q_linear_sample_weights(species, ("a", "b"))

    assert weights[:3].sum() == pytest.approx(weights[3:].sum())
    assert weights.sum() == pytest.approx(4.0)


def test_neural_fit_uses_12_epochs_and_freezing_preserves_shared_state():
    rng = np.random.default_rng(7)
    x = torch.tensor(rng.normal(size=(32, 28)), dtype=torch.float32)
    y = torch.tensor((x[:, 0] > 0).numpy(), dtype=torch.float32)
    source = build_residual(SPEC, 28, 1)
    fit_neural_binary(source, x, y, SPEC, 31031)

    frozen = build_residual(SPEC, 28, 1)
    copy_shared_trunk(source, frozen)
    before_frozen = clone_state(frozen)
    frozen_summary = fit_neural_binary(frozen, x, y, SPEC, 31032, freeze_trunk=True)
    assert frozen_summary.epochs == 12
    assert all(torch.equal(before_frozen[name], frozen.state_dict()[name]) for name in before_frozen if not name.startswith("head."))
    assert not frozen.stem.training
    assert not frozen.trunk.training
    assert not frozen.final_norm.training
    assert all(not module.training for module in frozen.trunk.modules() if isinstance(module, torch.nn.Dropout))
    assert frozen.head.training

    full = build_residual(SPEC, 28, 1)
    copy_shared_trunk(source, full)
    before_full = clone_state(full)
    fit_neural_binary(full, x, y, SPEC, 31032, freeze_trunk=False)
    assert any(not torch.equal(before_full[name], full.state_dict()[name]) for name in before_full if not name.startswith("head."))
    assert torch.equal(q_deep_scalar(source, x), torch.sigmoid(source(x)))
