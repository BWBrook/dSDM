"""Pure, deterministic architecture-selection helpers for Goal 033.

This module deliberately contains no data access or model fitting.  It owns
the frozen workload arithmetic, seed derivation, and the metric/ranking rules
used by the private runner.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .contracts import ARCHITECTURES, FOLDS, SPECIES


_AUTHORITY_KEYS = frozenset({
    "goal027_protocol", "goal028_decision", "goal031_config", "goal031_decision",
    "goal032_config", "goal032_decision", "goal032_receipt", "contracts", "models",
    "real_data", "real_training", "architecture_selection", "architecture_runner",
})
_HEX64 = set("0123456789abcdef")


class SelectionError(ValueError):
    """Raised when the Goal 033 selection contract is invalid."""


@dataclass(frozen=True)
class SelectionConfig:
    source_path: Path
    raw: Mapping[str, Any]
    species: tuple[str, ...]
    folds: tuple[str, ...]
    endpoint: str
    architectures: tuple[str, ...]
    screen_seeds: tuple[int, ...]
    shortlist_seeds: tuple[int, ...]
    shortlist_size: int
    workers: int


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    maximizers: tuple[float, ...]
    tss: float


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SelectionError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_selection_config(path: str | Path) -> SelectionConfig:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectionError(f"invalid config: {exc}") from exc
    _require(isinstance(raw, dict), "config must be an object")
    expected = {
        "schema_version", "goal_id", "authorities", "scope", "architecture_registry",
        "selection", "training", "execution", "privacy", "runtime", "evidence",
    }
    _require(set(raw) == expected, "unknown or missing top-level config key")
    _require(raw["schema_version"] == "1.0", "schema drift")
    _require(raw["goal_id"] == "goal033-dsdm-architecture-selection", "goal drift")
    authorities = raw["authorities"]
    _require(isinstance(authorities, dict) and set(authorities) == _AUTHORITY_KEYS, "authority key drift")
    for name, binding in authorities.items():
        _require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}, f"authority {name} invalid")
        _require(isinstance(binding["path"], str) and binding["path"] and isinstance(binding["sha256"], str) and len(binding["sha256"]) == 64 and set(binding["sha256"].lower()) <= _HEX64, f"authority {name} digest invalid")
    scope = raw["scope"]
    _require(isinstance(scope, dict), "scope invalid")
    _require(set(scope) == {"species", "folds", "endpoint", "predictor_count"}, "scope keys drift")
    _require(tuple(scope.get("species", ())) == SPECIES, "species drift")
    _require(tuple(scope.get("folds", ())) == FOLDS, "fold drift")
    _require(scope.get("endpoint") == "fraction100/full", "endpoint drift")
    _require(scope.get("predictor_count") == 77, "predictor drift")
    registry = raw["architecture_registry"]
    _require(isinstance(registry, list) and len(registry) == len(ARCHITECTURES), "architecture count drift")
    ids = tuple(row.get("id") for row in registry if isinstance(row, dict))
    _require(ids == tuple(row[0] for row in ARCHITECTURES), "architecture registry drift")
    _require(all(set(row) == {"id", "blocks", "width", "bottleneck", "shape", "dropout", "weight_decay"} for row in registry), "architecture keys drift")
    for row, expected_row in zip(registry, ARCHITECTURES):
        _require(tuple(row[k] for k in ("id", "blocks", "width", "bottleneck", "shape", "dropout", "weight_decay")) == expected_row, "architecture parameters drift")
    selection = raw["selection"]
    _require(selection == {
        "method": "target_only_resmlp", "screen_base_seeds": [31031],
        "shortlist_size": 4, "shortlist_base_seeds": [31031, 31032, 31033],
        "endpoint": "fraction100/full", "screen_architectures": list(ids),
    }, "selection contract drift")
    training = raw["training"]
    _require(training == {
        "held_fold_rule": "h", "stopping_fold_rule": "(h+1)%5",
        "discovery_folds": "other_three", "replay_folds": "all_four",
        "predictor_count": 77, "target_response": ["presence", "survey_supported_absence", "pseudoabsence"],
        "unknown_masked": True, "row_weights": "equal", "fit_seed_purpose": "fit",
        "max_epochs": 300, "patience": 30, "min_delta": 0.0,
    }, "training contract drift")
    execution = raw["execution"]
    _require(set(execution) == {"screen_logical_evaluations", "shortlist_logical_evaluations", "physical_fit_multiplier", "workers", "route"}, "execution keys drift")
    _require(execution.get("screen_logical_evaluations") == 960 and execution.get("shortlist_logical_evaluations") == 480, "workload arithmetic drift")
    _require(execution == {"screen_logical_evaluations": 960, "shortlist_logical_evaluations": 480, "physical_fit_multiplier": 2, "workers": 3, "route": "mac_cpu"}, "execution contract drift")
    privacy = raw["privacy"]
    _require(privacy == {"outer_attempted": 0, "outer_opened": 0, "tracked_predictions": False, "tracked_labels": False, "private_inner_labels_allowed": True, "row_identifiers": False, "coordinates": False}, "privacy contract drift")
    runtime = raw["runtime"]
    _require(runtime == {
        "python_major_minor": "3.12", "numpy": "2.2.6", "torch": "2.7.1",
        "device": "cpu", "threads": 1,
        "environment_path": "data/processed/dsdm/goal033-architecture-selection/runtime",
        "export_environment": "repository_locked_uv",
    }, "runtime contract drift")
    evidence = raw["evidence"]
    _require(evidence == {"private_root": "data/processed/dsdm/goal033-architecture-selection/private", "tracked_root": "evidence/dsdm_architecture_selection/goal033", "aggregate_only": True}, "evidence contract drift")
    workers = 3
    return SelectionConfig(
        source, raw, SPECIES, FOLDS, "fraction100/full", ids,
        tuple(selection["screen_base_seeds"]), tuple(selection["shortlist_base_seeds"]),
        int(selection["shortlist_size"]), workers,
    )


def build_task_plan(config: SelectionConfig) -> dict[str, int]:
    screen = len(config.architectures) * len(config.species) * len(config.folds) * len(config.screen_seeds)
    shortlist = config.shortlist_size * len(config.species) * len(config.folds) * len(config.shortlist_seeds)
    return {
        "screen_logical_evaluations": screen,
        "shortlist_logical_evaluations": shortlist,
        "logical_evaluations": screen + shortlist,
        "physical_fits": 2 * (screen + shortlist),
        "workers": config.workers,
    }


def derive_fit_seed(base_seed: int, target: str, held_fold: str, endpoint: str, architecture: str, purpose: str = "fit") -> int:
    """Derive a stable uint32 seed without host or selection-stage identity."""
    if not target or held_fold not in FOLDS or endpoint != "fraction100/full" or not architecture or not purpose:
        raise SelectionError("seed derivation identity invalid")
    payload = f"goal033|{int(base_seed)}|{target}|{held_fold}|{endpoint}|{architecture}|{purpose}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _validate_binary(y: np.ndarray, score: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y)
    score = np.asarray(score)
    _require(y.ndim == score.ndim == 1 and len(y) == len(score) and len(y) > 0, "metric vectors invalid")
    _require(np.isin(y, (0, 1)).all() and len(np.unique(y)) == 2, "both classes required")
    _require(np.isfinite(score).all() and np.all((score >= 0) & (score <= 1)), "scores invalid")
    return y.astype(np.int8), score.astype(np.float64)


def _average_ranks(values: Sequence[float], *, descending: bool) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: (-values[i] if descending else values[i], i))
    ranks = [0.0] * len(order)
    pos = 0
    while pos < len(order):
        end = pos + 1
        value = values[order[pos]]
        while end < len(order) and values[order[end]] == value:
            end += 1
        rank = (pos + 1 + end) / 2.0
        for index in order[pos:end]:
            ranks[index] = rank
        pos = end
    return ranks


def average_tie_ranks(values: Sequence[float]) -> list[float]:
    """Ascending average ranks, retained as a small general helper."""
    return _average_ranks([float(v) for v in values], descending=False)


def roc_auc(y: Sequence[float], scores: Sequence[float]) -> float:
    yv, sv = _validate_binary(np.asarray(y), np.asarray(scores))
    ranks = _average_ranks(sv.tolist(), descending=False)
    n_pos = int(np.sum(yv == 1)); n_neg = int(np.sum(yv == 0))
    return float((sum(r for r, label in zip(ranks, yv) if label == 1) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _tss(y: np.ndarray, scores: np.ndarray, threshold: float) -> float:
    pred = scores >= threshold
    tp = np.sum(pred & (y == 1)); fn = np.sum(~pred & (y == 1))
    tn = np.sum(~pred & (y == 0)); fp = np.sum(pred & (y == 0))
    return float(tp / (tp + fn) + tn / (tn + fp) - 1.0)


def choose_tss_threshold(y: Sequence[float], scores: Sequence[float]) -> ThresholdResult:
    yv, sv = _validate_binary(np.asarray(y), np.asarray(scores))
    unique = np.unique(sv)
    candidates = [float(np.nextafter(unique[0], -np.inf)), float(np.nextafter(unique[-1], np.inf))]
    for low, high in zip(unique[:-1], unique[1:]):
        midpoint = float(low + (high - low) / 2.0)
        if not low < midpoint < high:
            midpoint = float(high)
        if np.isfinite(midpoint):
            candidates.append(midpoint)
    candidates = sorted(set(candidates))
    values = np.asarray([_tss(yv, sv, threshold) for threshold in candidates])
    maximum = float(np.max(values))
    maximizers = tuple(t for t, value in zip(candidates, values) if value == maximum)
    threshold = maximizers[(len(maximizers) - 1) // 2]
    return ThresholdResult(float(threshold), tuple(float(t) for t in maximizers), _tss(yv, sv, threshold))


def rank_architectures(metrics: Mapping[str, Mapping[str, Mapping[str, float]]]) -> list[str]:
    """Rank by species-balanced AUC ranks, then species-balanced TSS ranks."""
    ids = sorted(metrics)
    species = sorted({species for value in metrics.values() for species in value})
    auc_by_species = {s: _average_ranks([float(metrics[a][s]["auc"]) for a in ids], descending=True) for s in species}
    tss_by_species = {s: _average_ranks([float(metrics[a][s]["tss"]) for a in ids], descending=True) for s in species}
    auc_mean = {a: float(np.mean([auc_by_species[s][ids.index(a)] for s in species])) for a in ids}
    tss_mean = {a: float(np.mean([tss_by_species[s][ids.index(a)] for s in species])) for a in ids}
    return sorted(ids, key=lambda a: (auc_mean[a], tss_mean[a], a))


def leave_one_species_out_audit(metrics: Mapping[str, Mapping[str, Mapping[str, float]]]) -> dict[str, list[str]]:
    """Return diagnostic rankings after omitting each species."""
    species = sorted({s for values in metrics.values() for s in values})
    return {
        omitted: rank_architectures({architecture: {s: value[s] for s in value if s != omitted} for architecture, value in metrics.items()})
        for omitted in species
    }


loso_audit = leave_one_species_out_audit


def validate_authorities(config: SelectionConfig, root: str | Path) -> dict[str, str]:
    """Recompute configured authority digests; copied summaries are not trusted."""
    root = Path(root)
    result: dict[str, str] = {}
    for name, binding in config.raw["authorities"].items():
        _require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}, f"authority {name} invalid")
        path = root / binding["path"]
        _require(path.is_file(), f"authority {name} missing")
        digest = _sha256(path)
        _require(digest == binding["sha256"], f"authority {name} digest mismatch")
        result[name] = digest
    return result


# Intentional aliases for callers that use the shorter names in runbooks.
load_config = load_selection_config
auc = roc_auc
select_threshold = choose_tss_threshold
