from pathlib import Path

import pytest
import torch

from dsdm.contracts import load_contract
from dsdm.models import (
    MultiHeadResidual,
    build_residual,
    clone_state,
    load_transfer,
    set_trunk_trainable,
    trunk_signature,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_contract(ROOT / "config" / "dsdm_synthetic_vertical.json")


def _spec(name):
    return next(item for item in CONTRACT.architectures if item.id == name)


def test_all_registered_models_instantiate_and_produce_finite_logits():
    x = torch.zeros((3, 28), dtype=torch.float32)
    for spec in CONTRACT.architectures:
        model = build_residual(spec, input_dim=28, output_dim=1)
        logits = model(x)
        assert logits.shape == (3,)
        assert torch.isfinite(logits).all()


def test_matched_paths_share_trunk_signature_while_q_has_only_wider_stem():
    spec = _spec("resmlp01")
    target = build_residual(spec, input_dim=28, output_dim=1)
    transfer = build_residual(spec, input_dim=28, output_dim=1)
    q_target = build_residual(spec, input_dim=29, output_dim=1)

    assert trunk_signature(target) == trunk_signature(transfer)
    assert trunk_signature(target) == trunk_signature(q_target)
    assert target.stem.weight.shape == (64, 28)
    assert q_target.stem.weight.shape == (64, 29)
    assert target.head.weight.shape == transfer.head.weight.shape == q_target.head.weight.shape


def test_clone_load_and_freeze_have_exact_state_semantics():
    spec = _spec("resmlp01")
    source = build_residual(spec, 28, 1)
    target = build_residual(spec, 28, 1)
    state = clone_state(source)

    load_transfer(target, state)
    assert all(torch.equal(state[name], value) for name, value in target.state_dict().items())
    state["stem.weight"].zero_()
    assert not torch.equal(state["stem.weight"], target.state_dict()["stem.weight"])

    set_trunk_trainable(target, False)
    assert all(not parameter.requires_grad for parameter in target.stem.parameters())
    assert all(not parameter.requires_grad for parameter in target.trunk.parameters())
    assert all(parameter.requires_grad for parameter in target.head.parameters())


def test_multihead_uses_shared_trunk_and_named_scalar_heads():
    model = MultiHeadResidual(_spec("resmlp01"), 28, CONTRACT.species[:-1])
    x = torch.ones((4, 28), dtype=torch.float32)

    assert model(x, CONTRACT.species[0]).shape == (4,)
    assert set(model.heads) == set(CONTRACT.species[:-1])
    with pytest.raises(KeyError):
        model(x, "not_a_head")


@pytest.mark.parametrize("input_dim,output_dim", [(0, 1), (28, 2)])
def test_model_builder_rejects_invalid_dimensions(input_dim, output_dim):
    with pytest.raises(ValueError):
        build_residual(_spec("resmlp01"), input_dim, output_dim)
