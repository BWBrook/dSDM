"""Shared mainland-only data, subset, metric, and community-surface helpers."""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import matthews_corrcoef, roc_auc_score

from .model_adapters import CANONICAL_CANDIDATES
from .modeling_contract import FeatureBatch, RowKey, canonical_json


CONTINUOUS = (
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19", "elevation_mean",
    "elevation_sd",
)
CATEGORICAL = ("nvis_mvg", "soil_order", "alum_secondary")
MISSING = "__MISSING__"
UNSEEN = "__UNSEEN__"


class MainlandModelingError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MainlandModelingError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_seed(*parts: object) -> int:
    raw = "\x1f".join(map(str, parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


def slug(value: str) -> str:
    return "_".join(value.lower().split())


@dataclass(frozen=True)
class ResponseRows:
    cell_ids: tuple[str, ...]
    y: np.ndarray
    source_folds: np.ndarray

    def __post_init__(self) -> None:
        y = np.asarray(self.y, dtype=np.int8)
        folds = np.asarray(self.source_folds, dtype=np.int8)
        require(
            len(self.cell_ids) == len(y) == len(folds)
            and len(self.cell_ids) == len(set(self.cell_ids)),
            "response_rows_invalid",
        )
        require(np.isin(y, [0, 1]).all(), "response_labels_invalid")
        require(np.isin(folds, range(5)).all(), "response_source_folds_invalid")
        y.flags.writeable = False
        folds.flags.writeable = False
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "source_folds", folds)

    def take(self, indices: Sequence[int]) -> "ResponseRows":
        idx = np.asarray(indices, dtype=np.int64)
        return ResponseRows(
            tuple(self.cell_ids[i] for i in idx), self.y[idx], self.source_folds[idx]
        )


@dataclass(frozen=True)
class EncodedFeatures:
    x: np.ndarray
    names: tuple[str, ...]
    kinds: tuple[str, ...]
    continuous_count: int
    transform_id: str
    transform_digest: str
    encoder_digest: str


class MainlandStore:
    """In-memory mainland view; the Tasmania predictor rows are never loaded."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.transforms = json.loads(
            (self.root / "metadata/goal043_transforms.json").read_text(encoding="utf-8")
        )
        require(tuple(self.transforms["continuous"]) == CONTINUOUS, "continuous_contract_drift")
        require(tuple(self.transforms["categorical"]) == CATEGORICAL, "categorical_contract_drift")

        columns = ["cell_id", *CONTINUOUS, *CATEGORICAL]
        predictor_path = self.root / "data/raw/goal041/predictor_substrate.parquet"
        table = pq.read_table(
            predictor_path,
            columns=columns,
            filters=[("region", "=", "southeast_mainland")],
        ).combine_chunks()
        self.cell_ids = tuple(table["cell_id"].to_pylist())
        require(len(self.cell_ids) == 1_053_032, "mainland_predictor_row_count_drift")
        require(len(self.cell_ids) == len(set(self.cell_ids)), "mainland_predictor_duplicate_cell")
        self.index = {cell_id: index for index, cell_id in enumerate(self.cell_ids)}
        self.continuous = {
            name: table[name].to_numpy(zero_copy_only=False).astype(np.float64, copy=False)
            for name in CONTINUOUS
        }
        self.categorical = {name: tuple(table[name].to_pylist()) for name in CATEGORICAL}

        assignments = pq.read_table(
            self.root / "data/raw/goal043/mainland_cell_partitions.parquet",
            columns=["cell_id", "fold"],
        ).combine_chunks()
        assignment_ids = assignments["cell_id"].to_pylist()
        require(tuple(assignment_ids) == self.cell_ids, "assignment_predictor_order_drift")
        self.fold_by_cell = dict(
            zip(assignment_ids, assignments["fold"].to_numpy(zero_copy_only=False).tolist())
        )
        self.responses = ds.dataset(
            self.root / "data/raw/goal043/split_responses.parquet", format="parquet"
        )

    def response_rows(self, target: str, held_fold: int, role: str) -> ResponseRows:
        require(held_fold in range(5) and role in {"train", "validation"}, "response_request_invalid")
        expression = (
            (ds.field("target") == target)
            & (ds.field("fold") == held_fold)
            & (ds.field("role") == role)
            & ds.field("continuous_complete")
            & (ds.field("is_presence") | ds.field("eligible_x3"))
        )
        table = self.responses.to_table(
            filter=expression, columns=["cell_id", "is_presence"]
        ).sort_by("cell_id")
        cells = tuple(table["cell_id"].to_pylist())
        y = table["is_presence"].to_numpy(zero_copy_only=False).astype(np.int8)
        require(cells and all(cell in self.index for cell in cells), "response_predictor_binding_failed")
        folds = np.asarray([self.fold_by_cell[cell] for cell in cells], dtype=np.int8)
        require(
            (folds != held_fold).all() if role == "train" else (folds == held_fold).all(),
            "response_role_partition_leakage",
        )
        require(len(set(y.tolist())) == 2, "response_role_single_class")
        return ResponseRows(cells, y, folds)

    def encoded(
        self,
        cell_ids: Sequence[str],
        held_fold: int,
        q_scores: Sequence[float] | None = None,
    ) -> EncodedFeatures:
        fit_id = f"fold{held_fold:02d}"
        fit = self.transforms["transforms"][fit_id]
        vocab = self.transforms["categorical_vocabularies"][fit["categorical_vocabulary_id"]]
        indices = np.asarray([self.index[cell] for cell in cell_ids], dtype=np.int64)
        means = np.asarray(fit["continuous_mean"], dtype=np.float64)
        sds = np.asarray(fit["continuous_population_sd"], dtype=np.float64)
        raw = np.column_stack([self.continuous[name][indices] for name in CONTINUOUS])
        require(np.isfinite(raw).all(), "continuous_nodata_in_model_rows")
        continuous = (raw - means) / sds
        names: list[str] = list(CONTINUOUS)
        kinds: list[str] = ["continuous"] * len(CONTINUOUS)
        continuous_count = len(CONTINUOUS)
        if q_scores is not None:
            q = np.asarray(q_scores, dtype=np.float64).reshape(-1, 1)
            require(len(q) == len(indices) and np.isfinite(q).all() and np.all((q >= 0) & (q <= 1)), "q_scores_invalid")
            continuous = np.column_stack((continuous, q))
            names.append("q_linear")
            kinds.append("continuous")
            continuous_count += 1

        encoded_columns: list[np.ndarray] = []
        encoded_levels: dict[str, list[str]] = {}
        for predictor in CATEGORICAL:
            levels = list(vocab[predictor]["encoded_levels"])
            require(MISSING in levels and UNSEEN in levels, "categorical_sentinel_missing")
            allowed = set(vocab[predictor]["observed_levels"])
            values = []
            for index in indices:
                raw_value = self.categorical[predictor][index]
                value = MISSING if raw_value is None else str(raw_value)
                values.append(value if value in allowed else UNSEEN)
            values_array = np.asarray(values, dtype=object)
            for level in levels:
                encoded_columns.append((values_array == level).astype(np.float64))
                names.append(f"{predictor}={level}")
                kinds.append("categorical")
            encoded_levels[predictor] = levels
        x = np.column_stack([continuous, *encoded_columns])
        transform_payload = {
            "fit_id": fit_id,
            "fit": fit,
            "vocabulary": vocab,
            "q_linear": q_scores is not None,
        }
        digest = hashlib.sha256(canonical_json(transform_payload).encode()).hexdigest()
        encoder_digest = hashlib.sha256(canonical_json(encoded_levels).encode()).hexdigest()
        return EncodedFeatures(
            x, tuple(names), tuple(kinds), continuous_count, fit_id, digest, encoder_digest
        )


def make_batch(target: str, rows: ResponseRows, features: EncodedFeatures) -> FeatureBatch:
    require(len(rows.cell_ids) == len(features.x), "batch_row_feature_mismatch")
    schema_digest = hashlib.sha256(
        canonical_json(
            {
                "feature_names": features.names,
                "feature_kinds": features.kinds,
                "continuous_count": features.continuous_count,
            }
        ).encode()
    ).hexdigest()
    return FeatureBatch(
        tuple(RowKey(target, cell) for cell in rows.cell_ids),
        features.x,
        rows.y.astype(np.float64),
        features.names,
        features.kinds,
        features.continuous_count,
        schema_digest,
        {},
        features.transform_id,
        features.transform_digest,
        features.encoder_digest,
    )


def subset_batch(batch: FeatureBatch, indices: Sequence[int]) -> FeatureBatch:
    idx = np.asarray(indices, dtype=np.int64)
    return FeatureBatch(
        tuple(batch.keys[i] for i in idx),
        batch.x[idx],
        batch.y[idx],
        batch.feature_names,
        batch.feature_kinds,
        batch.continuous_count,
        batch.feature_schema_digest,
        batch.unseen_level_counts,
        batch.transform_id,
        batch.transform_digest,
        batch.encoder_digest,
    )


def hierarchical_indices(rows: ResponseRows, ladder: str, master_seed: str) -> np.ndarray:
    """Return one deterministic order balanced over class x source fold."""
    require(ladder in {"ladder00", "ladder01", "ladder02"}, "ladder_invalid")
    groups: dict[tuple[int, int], list[tuple[bytes, int]]] = {}
    for index, (cell, y, fold) in enumerate(zip(rows.cell_ids, rows.y, rows.source_folds)):
        key = (int(y), int(fold))
        priority = hashlib.sha256(
            f"{master_seed}\x1f{ladder}\x1frow\x1f{cell}".encode()
        ).digest()
        groups.setdefault(key, []).append((priority, index))
    for values in groups.values():
        values.sort()
    counts = {key: len(values) for key, values in groups.items()}
    selected = {key: 0 for key in groups}
    group_priority = {
        key: hashlib.sha256(
            f"{master_seed}\x1f{ladder}\x1fgroup\x1f{key[0]}\x1f{key[1]}".encode()
        ).digest()
        for key in groups
    }
    order: list[int] = []
    n = len(rows.cell_ids)
    for k in range(1, n + 1):
        available = [key for key, values in groups.items() if selected[key] < len(values)]
        choice = min(
            available,
            key=lambda key: (
                -(k * counts[key] - selected[key] * n),
                group_priority[key],
            ),
        )
        order.append(groups[choice][selected[choice]][1])
        selected[choice] += 1
    return np.asarray(order, dtype=np.int64)


def endpoint_indices(
    rows: ResponseRows, fraction: int, ladder: str, master_seed: str
) -> np.ndarray:
    require(fraction in {25, 50, 100}, "fraction_invalid")
    if fraction == 100:
        return np.arange(len(rows.cell_ids), dtype=np.int64)
    order = hierarchical_indices(rows, ladder, master_seed)
    size = (len(order) + 2) // 4 if fraction == 25 else (len(order) + 1) // 2
    selected = order[:size]
    require(len(set(rows.y[selected].tolist())) == 2, "endpoint_single_class")
    return selected


def select_threshold(y_true: Sequence[int], scores: Sequence[float]) -> float:
    y = np.asarray(y_true, dtype=np.int8)
    score = np.asarray(scores, dtype=np.float64)
    require(
        len(y) == len(score) > 0
        and len(set(y.tolist())) == 2
        and np.isfinite(score).all(),
        "threshold_inputs_invalid",
    )
    order = np.argsort(-score, kind="mergesort")
    sorted_score = score[order]
    sorted_y = y[order]
    ends = np.r_[np.flatnonzero(sorted_score[:-1] != sorted_score[1:]), len(score) - 1]
    tp = np.cumsum(sorted_y)[ends]
    fp = (ends + 1) - tp
    positives = int(y.sum())
    negatives = len(y) - positives
    thresholds = sorted_score[ends]
    tss = tp / positives - fp / negatives
    all_negative_threshold = np.nextafter(float(sorted_score[0]), math.inf)
    thresholds = np.r_[thresholds, all_negative_threshold]
    tss = np.r_[tss, 0.0]
    best = float(np.max(tss))
    maximizers = np.sort(thresholds[np.isclose(tss, best, rtol=0, atol=1e-15)])
    require(len(maximizers) > 0 and np.isfinite(maximizers).all(), "threshold_selection_failed")
    return float(maximizers[(len(maximizers) - 1) // 2])


def binary_metrics(y_true: Sequence[int], scores: Sequence[float], threshold: float) -> dict[str, float | int]:
    y = np.asarray(y_true, dtype=np.int8)
    score = np.asarray(scores, dtype=np.float64)
    require(len(y) == len(score) and len(set(y.tolist())) == 2, "metric_inputs_invalid")
    predicted = score >= threshold
    tp = int(np.sum(predicted & (y == 1)))
    fn = int(np.sum(~predicted & (y == 1)))
    tn = int(np.sum(~predicted & (y == 0)))
    fp = int(np.sum(predicted & (y == 0)))
    sensitivity = tp / (tp + fn)
    specificity = tn / (tn + fp)
    return {
        "roc_auc": float(roc_auc_score(y, score)),
        "tss": float(sensitivity + specificity - 1),
        "balanced_accuracy": float((sensitivity + specificity) / 2),
        "mcc": float(matthews_corrcoef(y, predicted)),
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "prevalence": float(np.mean(y)),
        "n": int(len(y)),
        "presence_n": int(y.sum()),
        "background_n": int(len(y) - y.sum()),
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
    }


def summarize_oof(folds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    require(len(folds) == 5, "oof_fold_count_invalid")
    y = np.concatenate([np.asarray(fold["y"], dtype=np.int8) for fold in folds])
    scores = np.concatenate([np.asarray(fold["score"], dtype=np.float64) for fold in folds])
    threshold = select_threshold(y, scores)
    pooled = binary_metrics(y, scores, threshold)
    fold_metrics = [
        {"fold": int(fold["fold"]), **binary_metrics(fold["y"], fold["score"], threshold)}
        for fold in folds
    ]
    return {
        "threshold": threshold,
        "mean_fold_roc_auc": float(np.mean([item["roc_auc"] for item in fold_metrics])),
        "mean_fold_tss": float(np.mean([item["tss"] for item in fold_metrics])),
        "pooled": pooled,
        "folds": fold_metrics,
    }


def fit_q_linear(
    store: MainlandStore, config: Mapping[str, Any], target: str, held_fold: int
) -> tuple[dict[str, float], dict[str, Any]]:
    heads = [head for head in config["scope"]["response_heads"] if head != target]
    require(len(heads) == 19 and target not in heads, "q_target_exclusion_failed")
    rows_by_head = [store.response_rows(head, held_fold, "train") for head in heads]
    counts = np.asarray([len(rows.cell_ids) for rows in rows_by_head], dtype=np.float64)
    cells = tuple(cell for rows in rows_by_head for cell in rows.cell_ids)
    y = np.concatenate([rows.y for rows in rows_by_head])
    features = store.encoded(cells, held_fold)
    total = float(np.sum(counts))
    weights = np.concatenate(
        [np.full(int(count), total / (len(heads) * count), dtype=np.float64) for count in counts]
    )
    require(np.isclose(np.mean(weights), 1.0, rtol=0, atol=1e-12), "q_weight_normalization_failed")
    head_totals = [float(np.sum(weight)) for weight in np.split(weights, np.cumsum(counts.astype(int))[:-1])]
    require(np.allclose(head_totals, head_totals[0], rtol=0, atol=1e-8), "q_head_balance_failed")
    candidate = CANONICAL_CANDIDATES[config["community_control"]["candidate_id"]]
    model = LogisticRegression(
        C=float(candidate["C"]),
        l1_ratio=float(candidate["l1_ratio"]),
        penalty="elasticnet",
        solver="saga",
        max_iter=int(candidate["max_iter"]),
        tol=float(candidate["tol"]),
        fit_intercept=True,
        class_weight=None,
        n_jobs=1,
        random_state=stable_seed(config["target_subsets"]["master_seed"], "q", target, held_fold),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model.fit(features.x, y, sample_weight=weights)
    require(
        not any(issubclass(item.category, ConvergenceWarning) for item in caught)
        and int(model.n_iter_[0]) < int(candidate["max_iter"]),
        "q_linear_nonconverged",
    )
    target_cells = sorted(
        set(store.response_rows(target, held_fold, "train").cell_ids)
        | set(store.response_rows(target, held_fold, "validation").cell_ids)
    )
    target_features = store.encoded(target_cells, held_fold)
    scores = model.predict_proba(target_features.x)[:, 1].astype(np.float64)
    require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "q_prediction_invalid")
    return dict(zip(target_cells, scores.tolist())), {
        "target": target,
        "held_fold": held_fold,
        "excluded_target": True,
        "auxiliary_heads": heads,
        "auxiliary_head_count": len(heads),
        "rows_by_head": dict(zip(heads, counts.astype(int).tolist())),
        "total_training_rows": int(total),
        "mean_row_weight": float(np.mean(weights)),
        "head_total_weight_range": [float(min(head_totals)), float(max(head_totals))],
        "within_head_class_balancing": False,
        "iterations": int(model.n_iter_[0]),
        "target_score_count": len(scores),
        "target_score_range": [float(np.min(scores)), float(np.max(scores))],
    }
