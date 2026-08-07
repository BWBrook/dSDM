"""Small residual networks used by the Goal 031 sentinel."""

from __future__ import annotations

from copy import deepcopy
from math import ceil
from typing import Mapping, Sequence

import torch
from torch import nn

from .contracts import ArchitectureSpec


class ResidualBlock(nn.Module):
    def __init__(self, width: int, bottleneck: int, dropout: float) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(width)
        self.down = nn.Linear(width, bottleneck)
        self.activation = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        self.up = nn.Linear(bottleneck, width)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        update = self.up(self.dropout(self.activation(self.down(self.norm(x)))))
        return x + self.dropout(update)


def _blocks(spec: ArchitectureSpec) -> nn.Sequential:
    layers: list[nn.Module] = []
    taper_at = ceil(spec.blocks / 2)
    for index in range(spec.blocks):
        bottleneck = spec.bottleneck
        if spec.shape == "taper" and index >= taper_at:
            bottleneck = max(16, bottleneck // 2)
        layers.append(ResidualBlock(spec.width, bottleneck, spec.dropout))
    return nn.Sequential(*layers)


class ResidualMLP(nn.Module):
    def __init__(self, spec: ArchitectureSpec, input_dim: int) -> None:
        super().__init__()
        self.stem = nn.Linear(input_dim, spec.width)
        self.trunk = _blocks(spec)
        self.final_norm = nn.LayerNorm(spec.width)
        self.head = nn.Linear(spec.width, 1)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.final_norm(self.trunk(self.stem(x)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.encode(x)).squeeze(-1)


class MultiHeadResidual(nn.Module):
    def __init__(self, spec: ArchitectureSpec, input_dim: int, species: Sequence[str]) -> None:
        super().__init__()
        if input_dim < 1 or not species or len(set(species)) != len(species):
            raise ValueError("invalid multi-head dimensions")
        self.stem = nn.Linear(input_dim, spec.width)
        self.trunk = _blocks(spec)
        self.final_norm = nn.LayerNorm(spec.width)
        self.heads = nn.ModuleDict({name: nn.Linear(spec.width, 1) for name in species})

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.final_norm(self.trunk(self.stem(x)))

    def forward(self, x: torch.Tensor, species: str) -> torch.Tensor:
        if species not in self.heads:
            raise KeyError(species)
        return self.heads[species](self.encode(x)).squeeze(-1)


def build_residual(spec: ArchitectureSpec, input_dim: int, output_dim: int = 1) -> ResidualMLP:
    if input_dim < 1 or output_dim != 1:
        raise ValueError("Goal 031 supports positive input width and one scalar output")
    return ResidualMLP(spec, input_dim)


def clone_state(model: nn.Module) -> dict[str, torch.Tensor]:
    return {name: value.detach().clone() for name, value in model.state_dict().items()}


def load_transfer(model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
    expected = model.state_dict()
    if set(state) != set(expected) or any(state[name].shape != expected[name].shape for name in expected):
        raise ValueError("transfer state mismatch")
    model.load_state_dict(deepcopy(dict(state)), strict=True)


def set_trunk_trainable(model: ResidualMLP, trainable: bool) -> None:
    for module in (model.stem, model.trunk, model.final_norm):
        for parameter in module.parameters():
            parameter.requires_grad = trainable
    for parameter in model.head.parameters():
        parameter.requires_grad = True


def trunk_signature(model: ResidualMLP) -> tuple[tuple[str, tuple[int, ...]], ...]:
    return tuple((name, tuple(value.shape)) for name, value in model.trunk.state_dict().items())
