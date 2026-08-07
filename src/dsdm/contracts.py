"""Immutable contracts and aggregate planner for Goal 031."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """Raised when the synthetic execution contract drifts."""


SPECIES = (
    "thylogale_billardierii",
    "notamacropus_rufogriseus",
    "trichosurus_vulpecula",
    "pseudocheirus_peregrinus",
    "vombatus_ursinus",
    "sarcophilus_harrisii",
    "dasyurus_maculatus",
    "dasyurus_viverrinus",
)
FOLDS = tuple(f"fold{i:02d}" for i in range(5))
ENDPOINTS = (
    "fraction25/ladder00",
    "fraction25/ladder01",
    "fraction25/ladder02",
    "fraction50/ladder00",
    "fraction50/ladder01",
    "fraction50/ladder02",
    "fraction100/full",
)
METHODS = (
    "target_only_resmlp",
    "legacy_pooled_finetune",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
    "target_plus_q_linear",
    "target_plus_q_deep",
)
ARCHITECTURES = (
    ("resmlp00", 2, 64, 16, "constant", 0.0, 0.00001),
    ("resmlp01", 2, 64, 32, "taper", 0.1, 0.0001),
    ("resmlp02", 2, 64, 64, "constant", 0.2, 0.001),
    ("resmlp03", 2, 128, 16, "taper", 0.2, 0.0001),
    ("resmlp04", 2, 128, 32, "constant", 0.0, 0.001),
    ("resmlp05", 2, 128, 64, "taper", 0.1, 0.00001),
    ("resmlp06", 2, 256, 16, "constant", 0.1, 0.001),
    ("resmlp07", 2, 256, 32, "taper", 0.2, 0.00001),
    ("resmlp08", 3, 64, 16, "taper", 0.2, 0.001),
    ("resmlp09", 3, 64, 32, "constant", 0.0, 0.00001),
    ("resmlp10", 3, 64, 64, "taper", 0.1, 0.0001),
    ("resmlp11", 3, 128, 16, "constant", 0.1, 0.00001),
    ("resmlp12", 3, 128, 32, "taper", 0.2, 0.0001),
    ("resmlp13", 3, 128, 64, "constant", 0.0, 0.001),
    ("resmlp14", 3, 256, 16, "taper", 0.0, 0.0001),
    ("resmlp15", 3, 256, 64, "constant", 0.2, 0.00001),
    ("resmlp16", 4, 64, 16, "constant", 0.1, 0.0001),
    ("resmlp17", 4, 64, 32, "taper", 0.2, 0.00001),
    ("resmlp18", 4, 64, 64, "constant", 0.0, 0.001),
    ("resmlp19", 4, 128, 16, "taper", 0.0, 0.00001),
    ("resmlp20", 4, 128, 32, "constant", 0.1, 0.001),
    ("resmlp21", 4, 128, 64, "taper", 0.2, 0.0001),
    ("resmlp22", 4, 256, 32, "constant", 0.2, 0.0001),
    ("resmlp23", 4, 256, 64, "taper", 0.0, 0.001),
)


@dataclass(frozen=True)
class ArchitectureSpec:
    id: str
    blocks: int
    width: int
    bottleneck: int
    shape: str
    dropout: float
    weight_decay: float


@dataclass(frozen=True)
class ExperimentContract:
    source_path: Path
    species: tuple[str, ...]
    predictor_count: int
    folds: tuple[str, ...]
    endpoints: tuple[str, ...]
    methods: tuple[str, ...]
    architectures: tuple[ArchitectureSpec, ...]
    final_seeds: tuple[int, ...]
    raw: dict[str, Any]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def load_contract(path: str | Path) -> ExperimentContract:
    source = Path(path)
    try:
        raw = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid config: {exc}") from exc
    top_keys = {
        "schema_version", "goal_id", "species", "predictor_count", "folds",
        "endpoints", "methods", "architecture_registry",
        "architecture_selection", "final_seeds", "fixture", "training",
        "q_linear", "sentinel", "evidence",
    }
    _require(isinstance(raw, dict), "config must be an object")
    _require(set(raw) == top_keys, "unknown or missing top-level config key")
    _require(raw["schema_version"] == "1.0", "schema drift")
    _require(raw["goal_id"] == "goal031-dsdm-synthetic-vertical-slice", "goal drift")
    _require(tuple(raw["species"]) == SPECIES, "species drift")
    _require(raw["predictor_count"] == 28, "predictor drift")
    _require(tuple(raw["folds"]) == FOLDS, "fold drift")
    _require(tuple(raw["endpoints"]) == ENDPOINTS, "endpoint drift")
    _require(tuple(raw["methods"]) == METHODS, "method drift")

    arch_rows = raw["architecture_registry"]
    _require(isinstance(arch_rows, list) and len(arch_rows) == 24, "architecture count drift")
    expected_arch_keys = {"id", "blocks", "width", "bottleneck", "shape", "dropout", "weight_decay"}
    _require(all(isinstance(row, dict) and set(row) == expected_arch_keys for row in arch_rows), "architecture keys drift")
    actual_arch = tuple(
        (row["id"], row["blocks"], row["width"], row["bottleneck"], row["shape"], row["dropout"], row["weight_decay"])
        for row in arch_rows
    )
    _require(actual_arch == ARCHITECTURES, "architecture registry drift")

    _require(raw["architecture_selection"] == {"screen_seeds": 1, "shortlist_size": 4, "shortlist_seeds": 3, "endpoint": "fraction100/full"}, "architecture selection drift")
    _require(raw["final_seeds"] == [31031, 31032, 31033, 31034, 31035], "final seed drift")
    _require(raw["fixture"] == {
        "cell_count": 125,
        "per_species_provenance": {"presence": 40, "survey_supported_absence": 30, "pseudoabsence": 30, "unknown": 25},
        "per_fold_provenance": {"presence": 8, "survey_supported_absence": 6, "pseudoabsence": 6, "unknown": 5},
    }, "fixture drift")
    _require(raw["training"] == {
        "device": "cpu", "dtype": "float32", "torch_threads": 1,
        "deterministic_algorithms": True, "scaler": "StandardScaler",
        "scaler_scope": "split_training_predictors_only",
        "loss": "BCEWithLogitsLoss", "target_weighting": "unweighted",
        "auxiliary_weighting": "mean_of_within_species_means",
        "batching": "full_batch", "epochs": 12, "optimizer": "AdamW",
        "learning_rate": 0.001, "scheduler": None, "early_stopping": False,
    }, "training drift")
    _require(raw["q_linear"] == {
        "estimator": "LogisticRegression", "penalty": "elasticnet",
        "solver": "saga", "C": 1.0, "l1_ratio": 0.5,
        "max_iter": 2000, "tol": 0.000001, "random_state": "derived",
        "effective_threads": 1,
    }, "q_linear drift")
    _require(raw["sentinel"] == {
        "target": "sarcophilus_harrisii", "fold": "fold00", "seed": 31031,
        "endpoints": ["fraction25/ladder00", "fraction50/ladder00", "fraction100/full"],
        "canonical_architecture": "resmlp01",
        "architectures": ["resmlp00", "resmlp01", "resmlp23"],
        "runtime_limit_seconds": 60, "expected_target_fits": 20,
        "expected_auxiliary_fits": 3, "expected_total_fits": 23,
    }, "sentinel drift")
    _require(raw["evidence"] == {"outer_attempted": 0, "outer_opened": 0, "allow_aggregate_provenance_counts": True, "forbid_row_level": True}, "evidence drift")

    specs = tuple(ArchitectureSpec(*values) for values in ARCHITECTURES)
    return ExperimentContract(source, SPECIES, 28, FOLDS, ENDPOINTS, METHODS, specs, tuple(raw["final_seeds"]), raw)


def build_plan(contract: ExperimentContract) -> dict[str, int]:
    endpoint_strata = len(contract.species) * len(contract.endpoints)
    method_strata = endpoint_strata * len(contract.methods)
    method_fold_strata = method_strata * len(contract.folds)
    target_fits = method_fold_strata * len(contract.final_seeds)
    auxiliary_fits = (
        2 * len(contract.species) * len(contract.folds) * len(contract.final_seeds)
        + len(contract.species) * len(contract.folds)
    )
    selection = contract.raw["architecture_selection"]
    screen = len(contract.architectures) * len(contract.species) * len(contract.folds) * selection["screen_seeds"]
    shortlist = selection["shortlist_size"] * len(contract.species) * len(contract.folds) * selection["shortlist_seeds"]
    final_lifecycle = target_fits + auxiliary_fits
    return {
        "architecture_screen_fits": screen,
        "architecture_shortlist_fits": shortlist,
        "architecture_selection_fits": screen + shortlist,
        "auxiliary_fits": auxiliary_fits,
        "combined_declarative_fits": final_lifecycle + screen + shortlist,
        "endpoint_strata": endpoint_strata,
        "final_lifecycle_fits": final_lifecycle,
        "method_fold_strata": method_fold_strata,
        "method_strata": method_strata,
        "target_fits": target_fits,
    }
