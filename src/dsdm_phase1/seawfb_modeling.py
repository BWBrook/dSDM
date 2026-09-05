"""Lean retained-training modelling primitives for the SEAWFB experiments.

Only the Goal 050 retained substrate is visible here.  In particular, this
module has no path or API for opening any geographic holdout response.
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from .goal050_seawfb_foundation import CATEGORICAL, CONTINUOUS, nested_response_rows
from .model_adapters import CANONICAL_CANDIDATES
from .modeling_contract import FeatureBatch, RowKey, canonical_json


FOUNDATION_ROOT = Path("data/processed/dsdm/goal050-seawfb-modeling-foundation")
CELLS_PATH = FOUNDATION_ROOT / "cells.parquet"
MEMBERSHIPS_PATH = FOUNDATION_ROOT / "memberships.parquet"
CROSSFIT_PATH = FOUNDATION_ROOT / "crossfit_plan.json"
CURVES_PATH = FOUNDATION_ROOT / "learning_curves.json"
TRANSFORMS_PATH = Path("metadata/goal050_transforms.json")
MANIFEST_PATH = Path("metadata/goal050_manifest.json")
MISSING = "__MISSING__"
UNSEEN = "__UNSEEN__"


class SeawfbModelingError(ValueError):
    """Raised when a frozen modelling invariant is violated."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SeawfbModelingError(reason)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(raw.encode()).hexdigest()


def stable_seed(*parts: object) -> int:
    raw = "\x1f".join(map(str, parts)).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


def q_parameter_digest(coefficient: Sequence[float], intercept: float) -> str:
    values = np.concatenate(
        [np.asarray(coefficient, dtype="<f8").reshape(-1), np.asarray([intercept], dtype="<f8")]
    )
    require(np.isfinite(values).all(), "q_linear_nonfinite_parameters")
    return hashlib.sha256(values.tobytes()).hexdigest()


def slug(value: str) -> str:
    return "_".join(value.lower().split())


@dataclass(frozen=True)
class ResponseRows:
    indices: np.ndarray
    cell_ids: tuple[str, ...]
    y: np.ndarray
    source_folds: np.ndarray

    def __post_init__(self) -> None:
        indices = np.asarray(self.indices, dtype=np.int64)
        y = np.asarray(self.y, dtype=np.int8)
        folds = np.asarray(self.source_folds, dtype=np.int8)
        require(
            len(indices) == len(self.cell_ids) == len(y) == len(folds)
            and len(indices) == len(set(indices.tolist())),
            "response_rows_invalid",
        )
        require(np.isin(y, (0, 1)).all(), "response_labels_invalid")
        for array in (indices, y, folds):
            array.flags.writeable = False
        object.__setattr__(self, "indices", indices)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "source_folds", folds)


@dataclass(frozen=True)
class EncodedFeatures:
    x: np.ndarray
    names: tuple[str, ...]
    kinds: tuple[str, ...]
    continuous_count: int
    transform_id: str
    transform_digest: str
    encoder_digest: str


@dataclass(frozen=True)
class CollapsedBinaryRows:
    """Sufficient rows for a pooled binary likelihood without species ID."""

    indices: np.ndarray
    y: np.ndarray
    sample_weight: np.ndarray
    head_counts: tuple[int, ...]
    expanded_rows: int

    def __post_init__(self) -> None:
        indices = np.asarray(self.indices, dtype=np.int64)
        y = np.asarray(self.y, dtype=np.int8)
        weights = np.asarray(self.sample_weight, dtype=np.float64)
        require(
            len(indices) == len(y) == len(weights) > 0
            and np.isin(y, (0, 1)).all()
            and np.isfinite(weights).all()
            and np.all(weights > 0),
            "collapsed_rows_invalid",
        )
        require(self.expanded_rows == sum(self.head_counts), "collapsed_row_count_drift")
        for array in (indices, y, weights):
            array.flags.writeable = False
        object.__setattr__(self, "indices", indices)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "sample_weight", weights)


@dataclass(frozen=True)
class QLinearModel:
    coefficient: np.ndarray
    intercept: float
    held_block: int
    held_fold: int
    auxiliary_size: str
    transform_id: str
    iterations: int

    def raw_scores(self, features: EncodedFeatures) -> np.ndarray:
        require(features.transform_id == self.transform_id, "q_transform_mismatch")
        coefficient = np.asarray(self.coefficient, dtype=np.float64)
        require(features.x.shape[1] == len(coefficient), "q_feature_width_mismatch")
        scores = expit(features.x @ coefficient + self.intercept).astype(np.float64)
        require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "q_score_invalid")
        return scores


def collapse_equal_head_rows(
    row_indices: Sequence[np.ndarray], labels: Sequence[np.ndarray]
) -> CollapsedBinaryRows:
    """Collapse repeated ``(cell, y)`` rows while preserving pooled loss exactly.

    Every head contributes the same total weight.  Natural prevalence within
    each head is untouched; only repeated design rows are algebraically summed.
    """

    require(len(row_indices) == len(labels) > 0, "q_head_inputs_invalid")
    counts = np.asarray([len(values) for values in row_indices], dtype=np.int64)
    require(np.all(counts > 0), "q_empty_head")
    expanded = int(np.sum(counts))
    per_row = expanded / (len(counts) * counts.astype(np.float64))
    keys: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    for indices, y, weight in zip(row_indices, labels, per_row):
        index_array = np.asarray(indices, dtype=np.int64)
        y_array = np.asarray(y, dtype=np.int8)
        require(len(index_array) == len(y_array) and np.isin(y_array, (0, 1)).all(), "q_head_row_invalid")
        keys.append(index_array * 2 + y_array)
        weights.append(np.full(len(index_array), weight, dtype=np.float64))
    all_keys = np.concatenate(keys)
    unique, inverse = np.unique(all_keys, return_inverse=True)
    collapsed_weight = np.bincount(inverse, weights=np.concatenate(weights), minlength=len(unique))
    require(np.isclose(collapsed_weight.sum(), expanded, rtol=0, atol=1e-6), "q_weight_normalization_failed")
    return CollapsedBinaryRows(
        unique // 2,
        (unique % 2).astype(np.int8),
        collapsed_weight,
        tuple(counts.tolist()),
        expanded,
    )


class SeawfbStore:
    """In-memory view of Goal 050 retained cells and sparse memberships."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.manifest = json.loads((self.root / MANIFEST_PATH).read_text())
        self.transforms = json.loads((self.root / TRANSFORMS_PATH).read_text())
        self.crossfit = json.loads((self.root / CROSSFIT_PATH).read_text())
        self.curves = json.loads((self.root / CURVES_PATH).read_text())
        require(self.manifest.get("status") == "complete", "goal050_incomplete")
        require(self.transforms.get("schema_version") == "goal050-transforms-v1", "transform_schema_drift")
        require(self.crossfit.get("schema_version") == "goal050-crossfit-v1", "crossfit_schema_drift")
        require(self.curves.get("schema_version") == "goal050-learning-curves-v1", "curve_schema_drift")

        columns = ["cell_id", "fold", "effort_richness", *CONTINUOUS, *CATEGORICAL]
        self.cells = pq.read_table(self.root / CELLS_PATH, columns=columns).to_pandas()
        self.cell_ids = self.cells["cell_id"].astype(str).to_numpy()
        require(len(self.cell_ids) == len(set(self.cell_ids)), "duplicate_retained_cell")
        require(np.all(self.cell_ids[:-1] <= self.cell_ids[1:]), "retained_cell_order_drift")
        self.folds = self.cells["fold"].to_numpy(dtype=np.int8)
        self.richness = self.cells["effort_richness"].to_numpy(dtype=np.int64)

        membership = pq.read_table(self.root / MEMBERSHIPS_PATH, columns=["species", "cell_id"]).to_pandas()
        self.presence_indices: dict[str, np.ndarray] = {}
        for species, frame in membership.groupby("species", sort=False, observed=True):
            indices = np.searchsorted(self.cell_ids, frame["cell_id"].astype(str).to_numpy())
            require(
                np.all(indices < len(self.cell_ids))
                and np.array_equal(self.cell_ids[indices], frame["cell_id"].astype(str).to_numpy()),
                "membership_cell_binding_failed",
            )
            self.presence_indices[str(species)] = np.unique(indices.astype(np.int64))
        expected_heads = set(self.crossfit["focal_blocks"])
        expected_heads.update(
            species
            for block in self.crossfit["auxiliary_sets"].values()
            for species in block["full"]
        )
        require(expected_heads <= set(self.presence_indices), "membership_head_missing")
        self._curve_plan = {
            (item["target"], int(item["held_fold"])): item
            for item in self.curves["response_row_plan"]
        }
        self._response_cache: dict[tuple[str, int, int, str], ResponseRows] = {}

    @property
    def focal_targets(self) -> tuple[str, ...]:
        return tuple(self.curves["applies_to"]["full_full_focal_targets"])

    @property
    def primary_targets(self) -> tuple[str, ...]:
        return tuple(self.curves["applies_to"]["primary_targets"])

    def presence_mask(self, species: str) -> np.ndarray:
        require(species in self.presence_indices, f"unknown_species:{species}")
        mask = np.zeros(len(self.cell_ids), dtype=bool)
        mask[self.presence_indices[species]] = True
        return mask

    def target_rows(self, target: str, held_fold: int, fraction: int, role: str) -> ResponseRows:
        require(target in self.crossfit["focal_blocks"], f"unknown_target:{target}")
        require(held_fold in range(5) and fraction in (25, 50, 100), "target_endpoint_invalid")
        require(role in ("train", "validation"), "target_role_invalid")
        key = (target, held_fold, fraction, role)
        if key in self._response_cache:
            return self._response_cache[key]
        present = self.presence_mask(target)
        eligible = present | ((~present) & (self.richness >= 10))
        if role == "validation":
            indices = np.flatnonzero(eligible & (self.folds == held_fold))
        else:
            require(
                fraction == 100 or target in self.primary_targets,
                "fractional_nonprimary_target",
            )
            subsets = nested_response_rows(
                self.cell_ids,
                present,
                self.richness,
                self.folds,
                held_fold,
                fractions=(0.25, 0.5, 1.0) if target in self.primary_targets else (1.0,),
                seed=target,
            )
            label = {25: "0.25", 50: "0.5", 100: "1.0"}[fraction]
            selected_ids = np.asarray(subsets[label])
            plan = self._curve_plan[(target, held_fold)]["fractions"][label]
            require(len(selected_ids) == plan["count"] and digest(selected_ids.tolist()) == plan["selection_digest"], "target_subset_replay_failed")
            indices = np.searchsorted(self.cell_ids, selected_ids)
            require(np.array_equal(self.cell_ids[indices], selected_ids), "target_subset_cell_binding_failed")
        rows = ResponseRows(
            indices,
            tuple(self.cell_ids[indices].tolist()),
            present[indices].astype(np.int8),
            self.folds[indices],
        )
        require(len(set(rows.y.tolist())) == 2, "target_role_single_class")
        require(
            (rows.source_folds != held_fold).all() if role == "train" else (rows.source_folds == held_fold).all(),
            "target_fold_leakage",
        )
        self._response_cache[key] = rows
        return rows

    def encoded(self, indices: Sequence[int], held_fold: int, q: Sequence[float] | None = None) -> EncodedFeatures:
        selected = np.asarray(indices, dtype=np.int64)
        require(held_fold in range(5) and np.all((selected >= 0) & (selected < len(self.cells))), "encode_request_invalid")
        transform_id = f"fold_{held_fold}"
        transform = self.transforms["transforms"][transform_id]
        continuous_columns = []
        for name in CONTINUOUS:
            spec = transform["continuous"][name]
            raw = pd.to_numeric(self.cells[name].iloc[selected], errors="coerce").to_numpy(dtype=np.float64, copy=True)
            raw[~np.isfinite(raw)] = float(spec["mean"])
            continuous_columns.append((raw - float(spec["mean"])) / float(spec["population_sd"]))
        matrix = np.column_stack(continuous_columns)
        names: list[str] = list(CONTINUOUS)
        kinds: list[str] = ["continuous"] * len(CONTINUOUS)
        continuous_count = len(CONTINUOUS)
        if q is not None:
            q_values = np.asarray(q, dtype=np.float64)
            require(len(q_values) == len(selected) and np.isfinite(q_values).all(), "standardized_q_invalid")
            matrix = np.column_stack((matrix, q_values))
            names.append("q_linear")
            kinds.append("continuous")
            continuous_count += 1
        encoded: list[np.ndarray] = []
        categorical_payload: dict[str, list[str]] = {}
        for name in CATEGORICAL:
            levels = list(transform["categorical"][name])
            require(levels[:2] == [MISSING, UNSEEN], "categorical_sentinel_drift")
            allowed = set(levels)
            raw = self.cells[name].iloc[selected].astype("string").fillna(MISSING).astype(str).to_numpy()
            values = np.asarray([value if value in allowed else UNSEEN for value in raw], dtype=object)
            for level in levels:
                encoded.append((values == level).astype(np.float64))
                names.append(f"{name}={level}")
                kinds.append("categorical")
            categorical_payload[name] = levels
        if encoded:
            matrix = np.column_stack((matrix, *encoded))
        require(np.isfinite(matrix).all(), "encoded_feature_nonfinite")
        transform_payload = {"id": transform_id, "transform": transform, "q_linear": q is not None}
        return EncodedFeatures(
            matrix,
            tuple(names),
            tuple(kinds),
            continuous_count,
            transform_id,
            digest(transform_payload),
            digest(categorical_payload),
        )

    def batch(self, target: str, rows: ResponseRows, held_fold: int, q: Sequence[float] | None = None) -> FeatureBatch:
        features = self.encoded(rows.indices, held_fold, q)
        schema = {
            "feature_names": features.names,
            "feature_kinds": features.kinds,
            "continuous_count": features.continuous_count,
        }
        return FeatureBatch(
            tuple(RowKey(target, cell) for cell in rows.cell_ids),
            features.x,
            rows.y.astype(np.float64),
            features.names,
            features.kinds,
            features.continuous_count,
            hashlib.sha256(canonical_json(schema).encode()).hexdigest(),
            {},
            features.transform_id,
            features.transform_digest,
            features.encoder_digest,
        )

    def q_collapsed_rows(self, held_block: int, held_fold: int, auxiliary_size: str) -> tuple[CollapsedBinaryRows, dict[str, Any]]:
        block_key = str(held_block)
        require(block_key in self.crossfit["auxiliary_sets"], "q_block_invalid")
        require(held_fold in range(5) and auxiliary_size in ("20", "80", "full"), "q_endpoint_invalid")
        held_species = sorted(
            species
            for species, block in self.crossfit["focal_blocks"].items()
            if int(block) == held_block
        )
        heads = list(self.crossfit["auxiliary_sets"][block_key][auxiliary_size])
        require(set(held_species).isdisjoint(heads), "q_held_block_leakage")
        held_count = np.zeros(len(self.cell_ids), dtype=np.int16)
        for species in held_species:
            held_count[self.presence_indices[species]] += 1
        complement_richness = self.richness - held_count
        require(np.all(complement_richness >= 0), "q_complement_richness_negative")
        in_training = self.folds != held_fold
        background_base = in_training & (complement_richness >= 10)
        row_indices: list[np.ndarray] = []
        labels: list[np.ndarray] = []
        for head in heads:
            present = self.presence_mask(head)
            indices = np.flatnonzero(in_training & (present | ((~present) & background_base)))
            row_indices.append(indices)
            labels.append(present[indices].astype(np.int8))
        collapsed = collapse_equal_head_rows(row_indices, labels)
        total_per_head = [collapsed.expanded_rows / len(heads)] * len(heads)
        return collapsed, {
            "held_block": held_block,
            "held_fold": held_fold,
            "auxiliary_size": auxiliary_size,
            "held_species": held_species,
            "heads": heads,
            "head_count": len(heads),
            "head_rows": dict(zip(heads, collapsed.head_counts)),
            "expanded_rows": collapsed.expanded_rows,
            "collapsed_rows": len(collapsed.indices),
            "head_total_weight_range": [min(total_per_head), max(total_per_head)],
            "within_head_class_balancing": False,
            "richness": "R_complement",
        }


def fit_q_linear(
    store: SeawfbStore,
    held_block: int,
    held_fold: int,
    auxiliary_size: str,
    seed_namespace: str,
    numerical_fit: Mapping[str, Any],
    candidate_id: str = "enet04",
) -> tuple[QLinearModel, dict[str, Any]]:
    require(candidate_id == "enet04", "q_candidate_drift")
    collapsed, receipt = store.q_collapsed_rows(held_block, held_fold, auxiliary_size)
    features = store.encoded(collapsed.indices, held_fold)
    candidate = CANONICAL_CANDIDATES[candidate_id]
    seed = stable_seed(seed_namespace, "q_linear", held_block, held_fold, auxiliary_size)
    tol = float(numerical_fit["tol"])
    k = float(np.max(collapsed.sample_weight))
    canonical_c = float(candidate["C"])
    require(math.isfinite(k) and k > 0, "q_weight_rescaling_invalid")
    solver_c = canonical_c * k
    solver_sample_weight = collapsed.sample_weight / k
    require(
        np.isfinite(solver_sample_weight).all()
        and np.all(solver_sample_weight > 0)
        and np.isclose(np.max(solver_sample_weight), 1.0, rtol=0, atol=1e-12),
        "q_solver_weight_rescaling_invalid",
    )
    representation = "collapsed_weight_divided_by_k_solver_C_multiplied_by_k"
    attempts = []
    model = None
    accepted_attempt = None
    for attempt, max_iter in (
        ("primary", int(numerical_fit["primary_max_iter"])),
        ("extended", int(numerical_fit["extended_max_iter"])),
    ):
        fitted_attempt = LogisticRegression(
            C=solver_c,
            l1_ratio=float(candidate["l1_ratio"]),
            solver="saga",
            max_iter=max_iter,
            tol=tol,
            fit_intercept=True,
            class_weight=None,
            random_state=seed,
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                fitted_attempt.fit(features.x, collapsed.y, sample_weight=solver_sample_weight)
            except Exception as exc:
                warning_types = sorted({type(item.message).__name__ for item in caught})
                attempts.append(
                    {
                        "attempt": attempt,
                        "max_iter": max_iter,
                        "tol": tol,
                        "n_iter": None,
                        "warning": "ConvergenceWarning" in warning_types,
                        "warning_types": warning_types,
                        "numerical_warning": any(name == "RuntimeWarning" for name in warning_types),
                        "converged": False,
                        "error": type(exc).__name__,
                    }
                )
                details = json.dumps({"attempts": attempts}, sort_keys=True, separators=(",", ":"))
                raise SeawfbModelingError(f"q_linear_fit_failed:{details}") from exc
        warning_types = sorted({type(item.message).__name__ for item in caught})
        warning = any(isinstance(item.message, ConvergenceWarning) for item in caught)
        numerical_warning = any(isinstance(item.message, RuntimeWarning) for item in caught)
        n_iter = int(fitted_attempt.n_iter_[0])
        converged = not warning and not numerical_warning and n_iter < max_iter
        attempts.append(
            {
                "attempt": attempt,
                "max_iter": max_iter,
                "tol": tol,
                "n_iter": n_iter,
                "warning": warning,
                "warning_types": warning_types,
                "numerical_warning": numerical_warning,
                "converged": converged,
            }
        )
        if converged:
            model = fitted_attempt
            accepted_attempt = attempt
            break
    if model is None or accepted_attempt is None:
        details = json.dumps({"attempts": attempts}, sort_keys=True, separators=(",", ":"))
        raise SeawfbModelingError(f"q_linear_nonconverged_after_extended_attempt:{details}")
    fitted = QLinearModel(
        np.asarray(model.coef_[0], dtype=np.float64),
        float(model.intercept_[0]),
        held_block,
        held_fold,
        auxiliary_size,
        features.transform_id,
        int(model.n_iter_[0]),
    )
    require(np.isfinite(fitted.coefficient).all() and math.isfinite(fitted.intercept), "q_linear_nonfinite_parameters")
    parameter_digest = q_parameter_digest(fitted.coefficient, fitted.intercept)
    return fitted, {
        **receipt,
        "candidate_id": candidate_id,
        "fit_seed": seed,
        "iterations": fitted.iterations,
        "attempts": attempts,
        "accepted_attempt": accepted_attempt,
        "parameter_digest": parameter_digest,
        "numerical_fit": dict(numerical_fit),
        "coefficient_count": len(fitted.coefficient),
        "k": k,
        "canonical_C": canonical_c,
        "solver_C": solver_c,
        "representation": representation,
    }


def standardized_q(
    model: QLinearModel,
    store: SeawfbStore,
    held_fold: int,
    training_rows: ResponseRows,
    validation_rows: ResponseRows,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Scale both roles using one evaluation of the target training rows."""

    require((training_rows.source_folds != held_fold).all(), "q_scale_training_fold_leakage")
    training_raw = model.raw_scores(store.encoded(training_rows.indices, held_fold))
    mean = float(np.mean(training_raw))
    sd = float(np.std(training_raw, ddof=0))
    require(math.isfinite(mean) and math.isfinite(sd) and sd > 0, "q_standardization_degenerate")
    validation_raw = model.raw_scores(store.encoded(validation_rows.indices, held_fold))
    training_q = (training_raw - mean) / sd
    validation_q = (validation_raw - mean) / sd
    require(np.isfinite(training_q).all() and np.isfinite(validation_q).all(), "q_standardization_nonfinite")
    return training_q, validation_q, {"training_mean": mean, "training_population_sd": sd}
