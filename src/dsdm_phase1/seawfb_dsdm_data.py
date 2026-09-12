"""Retained-only, indexed training rows for the frozen SEAWFB neural experiment.

Features are stored once per cell; repeated auxiliary head/cell observations
remain distinct training rows. This avoids expanding the predictor matrix for
hundreds of heads without changing the empirical loss or minibatch ordering.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

import numpy as np

from .seawfb_modeling import QLinearModel, ResponseRows, SeawfbStore, digest, require


@dataclass(frozen=True)
class IndexedRows:
    features: np.ndarray
    indices: np.ndarray
    y: np.ndarray
    head_index: np.ndarray | None = None
    weights: np.ndarray | None = None

    def __post_init__(self) -> None:
        x = np.asarray(self.features, dtype=np.float32)
        index = np.asarray(self.indices, dtype=np.int64)
        y = np.asarray(self.y, dtype=np.float32)
        require(x.ndim == 2 and len(x) > 0 and np.isfinite(x).all(), "neural_features_invalid")
        require(index.ndim == 1 and len(index) > 0 and y.shape == index.shape, "neural_rows_invalid")
        require(np.all((index >= 0) & (index < len(x))) and np.isin(y, (0, 1)).all(), "neural_indices_or_labels_invalid")
        head = None if self.head_index is None else np.asarray(self.head_index, dtype=np.int64)
        weight = None if self.weights is None else np.asarray(self.weights, dtype=np.float32)
        if head is not None:
            require(head.shape == y.shape and np.all(head >= 0), "neural_head_indices_invalid")
        if weight is not None:
            require(weight.shape == y.shape and np.isfinite(weight).all() and np.all(weight > 0), "neural_weights_invalid")
        for name, value in (("features", x), ("indices", index), ("y", y), ("head_index", head), ("weights", weight)):
            object.__setattr__(self, name, value)

    def subset(self, selected: np.ndarray) -> IndexedRows:
        return IndexedRows(self.features, self.indices[selected], self.y[selected],
                           None if self.head_index is None else self.head_index[selected],
                           None if self.weights is None else self.weights[selected])


def row_digest(indices: np.ndarray, y: np.ndarray, folds: np.ndarray, head: np.ndarray | None = None) -> str:
    result = hashlib.sha256()
    for value, dtype in ((indices, "<i8"), (y, "i1"), (folds, "i1")):
        result.update(np.asarray(value, dtype=dtype).tobytes())
    if head is not None:
        result.update(np.asarray(head, dtype="<i4").tobytes())
    return result.hexdigest()


def _roles(indices: np.ndarray, y: np.ndarray, folds: np.ndarray, held_fold: int,
           head: np.ndarray | None = None) -> dict[str, Any]:
    require(held_fold in range(5) and np.all(folds != held_fold), "neural_held_fold_leakage")
    stopping = (held_fold + 1) % 5
    return {
        "held_fold": held_fold, "stopping_fold": stopping,
        "discovery_folds": sorted(set(range(5)) - {held_fold, stopping}),
        "replay_folds": sorted(set(range(5)) - {held_fold}),
        "rows": {
            role: {"n": int(mask.sum()), "digest": row_digest(indices[mask], y[mask], folds[mask], None if head is None else head[mask])}
            for role, mask in (("discovery", folds != stopping), ("stopping", folds == stopping), ("replay", np.ones(len(indices), dtype=bool)))
        },
    }


@dataclass(frozen=True)
class TargetData:
    discovery: IndexedRows
    stopping: IndexedRows
    replay: IndexedRows
    held_x: np.ndarray
    held_y: np.ndarray
    held_cells: tuple[str, ...]
    metadata: Mapping[str, Any]


def target_data(store: SeawfbStore, target: str, held_fold: int, fraction: int,
                q_model: QLinearModel | None = None) -> TargetData:
    train = store.target_rows(target, held_fold, fraction, "train")
    held = store.target_rows(target, held_fold, fraction, "validation")
    require(not np.intersect1d(train.indices, held.indices).size, "neural_target_role_overlap")
    cells = np.union1d(train.indices, held.indices)
    encoded = store.encoded(cells, held_fold)
    train_index = np.searchsorted(cells, train.indices)
    held_index = np.searchsorted(cells, held.indices)
    matrix = encoded.x
    q_scaling = None
    if q_model is not None:
        require(q_model.held_fold == held_fold and q_model.held_block == int(store.crossfit["focal_blocks"][target]), "neural_q_scope_mismatch")
        raw = q_model.raw_scores(encoded)
        mean, sd = float(raw[train_index].mean()), float(raw[train_index].std(ddof=0))
        require(np.isfinite(mean) and np.isfinite(sd) and sd > 0, "neural_q_scale_invalid")
        matrix = np.insert(matrix, encoded.continuous_count, (raw - mean) / sd, axis=1)
        q_scaling = {"training_mean": mean, "training_population_sd": sd}
    features = np.asarray(matrix, dtype=np.float32)
    replay = IndexedRows(features, train_index, train.y)
    stopping_mask = train.source_folds == (held_fold + 1) % 5
    metadata = _roles(train.indices, train.y, train.source_folds, held_fold)
    metadata.update({"target": target, "fraction": fraction, "feature_width": int(features.shape[1]),
                     "transform_digest": encoded.transform_digest, "encoder_digest": encoded.encoder_digest,
                     "q_scaling": q_scaling, "held_row_digest": row_digest(held.indices, held.y, held.source_folds),
                     "held_rows": len(held.y), "target_subset_digest": digest(list(train.cell_ids))})
    return TargetData(replay.subset(~stopping_mask), replay.subset(stopping_mask), replay,
                      features[held_index], held.y, held.cell_ids, metadata)


@dataclass(frozen=True)
class AuxiliaryData:
    discovery: IndexedRows
    stopping: IndexedRows
    replay: IndexedRows
    heads: tuple[str, ...]
    metadata: Mapping[str, Any]


def _balanced_rows(features: np.ndarray, index: np.ndarray, y: np.ndarray,
                   head: np.ndarray, head_count: int) -> tuple[IndexedRows, dict[str, Any]]:
    counts = np.bincount(head, minlength=head_count)
    require(len(counts) == head_count and np.all(counts > 0), "neural_auxiliary_role_missing_head")
    weights = (len(index) / (head_count * counts[head])).astype(np.float32)
    totals = np.bincount(head, weights=weights.astype(np.float64), minlength=head_count)
    require(np.allclose(totals, totals[0], rtol=2*np.finfo(np.float32).eps, atol=0), "neural_equal_head_weight_failure")
    rows = IndexedRows(features, index, y, head, weights)
    return rows, {"head_rows": counts.tolist(), "head_total_weight_range": [float(totals.min()), float(totals.max())],
                  "within_head_class_balancing": False}


def auxiliary_data(store: SeawfbStore, block: int, held_fold: int, auxiliary: str) -> AuxiliaryData:
    require(held_fold in range(5) and auxiliary in ("20", "80", "full"), "neural_auxiliary_scope_invalid")
    require(str(block) in store.crossfit["auxiliary_sets"], "neural_auxiliary_block_invalid")
    held_species = sorted(s for s, b in store.crossfit["focal_blocks"].items() if int(b) == block)
    heads = tuple(store.crossfit["auxiliary_sets"][str(block)][auxiliary])
    require(heads and len(set(heads)) == len(heads) and not set(heads).intersection(held_species), "neural_auxiliary_head_leakage")
    richness = store.richness.copy()
    for species in held_species:
        richness[store.presence_indices[species]] -= 1
    require(np.all(richness >= 0), "neural_complement_richness_negative")
    nonheld = store.folds != held_fold
    indices, labels, head_indices = [], [], []
    for i, species in enumerate(heads):
        present = store.presence_mask(species)
        index = np.flatnonzero(nonheld & (present | (richness >= 10)))
        indices.append(index); labels.append(present[index].astype(np.int8))
        head_indices.append(np.full(len(index), i, dtype=np.int32))
    index = np.concatenate(indices)
    y = np.concatenate(labels)
    head = np.concatenate(head_indices)
    folds = store.folds[index]
    cells = np.unique(index)
    encoded = store.encoded(cells, held_fold)
    features = np.asarray(encoded.x, dtype=np.float32)
    mapped = np.searchsorted(cells, index)
    masks = {"discovery": folds != (held_fold + 1) % 5, "stopping": folds == (held_fold + 1) % 5,
             "replay": np.ones(len(index), dtype=bool)}
    datasets, weights = {}, {}
    for role, mask in masks.items():
        datasets[role], weights[role] = _balanced_rows(features, mapped[mask], y[mask], head[mask], len(heads))
    meta = _roles(index, y, folds, held_fold, head)
    meta.update({"held_block": block, "auxiliary_size": auxiliary, "held_species": held_species,
                 "heads": list(heads), "weights": weights, "richness": "R_complement",
                 "feature_width": int(features.shape[1]), "unique_feature_cells": len(cells),
                 "transform_digest": encoded.transform_digest, "encoder_digest": encoded.encoder_digest})
    return AuxiliaryData(datasets["discovery"], datasets["stopping"], datasets["replay"], heads, meta)
