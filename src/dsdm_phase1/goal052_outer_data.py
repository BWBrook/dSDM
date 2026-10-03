"""Retained-full, response-free data adapters for the Goal052 outer pass.

The outer response surface is deliberately absent from this module.  The
adapters use the retained Goal050 cells and memberships for refit data and
accept the response-free predictor mapping produced by
``goal052_outer_predictors.read_outer_predictors`` for prediction batches.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from .goal050_seawfb_foundation import CATEGORICAL, CONTINUOUS
from .modeling_contract import FeatureBatch, RowKey, canonical_json
from .seawfb_dsdm_data import IndexedRows, _balanced_rows, row_digest
from .seawfb_modeling import (
    EncodedFeatures,
    QLinearModel,
    ResponseRows,
    SeawfbStore,
    digest,
    require,
)


FULL_FOLD = -1
RETAINED_FULL_TRANSFORM = "retained_full"
OUTER_PREDICTION_SPECIES = "__outer_prediction__"
EXPECTED_FEATURES = 103


def _digest_bytes(value: Any, dtype: str) -> str:
    return hashlib.sha256(np.asarray(value, dtype=dtype).tobytes()).hexdigest()


def _digest_strings(values: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(map(str, values)) + "\n").encode()).hexdigest()


def _feature_schema(features: EncodedFeatures) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "feature_names": features.names,
                "feature_kinds": features.kinds,
                "continuous_count": features.continuous_count,
            }
        ).encode()
    ).hexdigest()


def _full_transform(store: SeawfbStore) -> Mapping[str, Any]:
    transforms = getattr(store, "transforms", {}).get("transforms", {})
    transform = transforms.get(RETAINED_FULL_TRANSFORM)
    require(isinstance(transform, Mapping), "retained_full_transform_missing")
    require(set(transform.get("continuous", {})) == set(CONTINUOUS), "retained_full_continuous_set_drift")
    require(set(transform.get("categorical", {})) == set(CATEGORICAL), "retained_full_categorical_set_drift")
    for name in CONTINUOUS:
        spec = transform["continuous"][name]
        require(
            np.isfinite(float(spec["mean"]))
            and np.isfinite(float(spec["population_sd"]))
            and float(spec["population_sd"]) > 0,
            f"retained_full_continuous_transform_invalid:{name}",
        )
    for name in CATEGORICAL:
        levels = list(transform["categorical"][name])
        require(
            levels[:2] == ["__MISSING__", "__UNSEEN__"]
            and len(levels) == len(set(levels)),
            f"retained_full_categorical_transform_invalid:{name}",
        )
    return transform


def full_encoded_metadata(store: SeawfbStore, *, q: bool = False) -> dict[str, Any]:
    """Return the native feature names, kinds, and retained-full digests."""

    transform = _full_transform(store)
    names = list(CONTINUOUS)
    kinds = ["continuous"] * len(CONTINUOUS)
    continuous_count = len(CONTINUOUS)
    if q:
        names.append("q_linear")
        kinds.append("continuous")
        continuous_count += 1
    levels = {name: list(transform["categorical"][name]) for name in CATEGORICAL}
    names.extend(f"{name}={level}" for name in CATEGORICAL for level in levels[name])
    kinds.extend(["categorical"] * (len(names) - len(kinds)))
    transform_digest = digest(
        {"id": RETAINED_FULL_TRANSFORM, "transform": transform, "q_linear": q}
    )
    encoder_digest = digest(levels)
    require(len(names) == EXPECTED_FEATURES + int(q), "retained_full_feature_count_drift")
    return {
        "feature_names": tuple(names),
        "feature_kinds": tuple(kinds),
        "continuous_count": continuous_count,
        "transform_id": RETAINED_FULL_TRANSFORM,
        "transform_digest": transform_digest,
        "encoder_digest": encoder_digest,
    }


class RetainedFullStore(SeawfbStore):
    """Goal050 store with a ``FULL_FOLD`` retained-all-cells scope.

    Existing fold-scoped methods remain inherited.  The three overrides below
    only add the explicit retained-full sentinel and leave the native fold
    behaviour untouched.
    """

    def target_rows(self, target: str, held_fold: int, fraction: int, role: str) -> ResponseRows:
        if held_fold != FULL_FOLD:
            return super().target_rows(target, held_fold, fraction, role)
        require(target in self.crossfit["focal_blocks"], f"unknown_target:{target}")
        require(fraction == 100 and role == "train", "retained_full_target_scope_invalid")
        key = (target, FULL_FOLD, fraction, role)
        if key in self._response_cache:
            return self._response_cache[key]
        present = self.presence_mask(target)
        eligible = present | ((~present) & (self.richness >= 10))
        indices = np.flatnonzero(eligible)
        rows = ResponseRows(
            indices,
            tuple(self.cell_ids[indices].tolist()),
            present[indices].astype(np.int8),
            self.folds[indices],
        )
        require(len(set(rows.y.tolist())) == 2, "target_role_single_class")
        require(set(rows.source_folds.tolist()) == set(range(5)), "retained_full_fold_coverage")
        self._response_cache[key] = rows
        return rows

    def encoded(
        self,
        indices: Sequence[int],
        held_fold: int,
        q: Sequence[float] | None = None,
    ) -> EncodedFeatures:
        if held_fold != FULL_FOLD:
            return super().encoded(indices, held_fold, q)
        selected = np.asarray(indices, dtype=np.int64)
        require(
            selected.ndim == 1
            and np.all((selected >= 0) & (selected < len(self.cells))),
            "encode_request_invalid",
        )
        transform = _full_transform(self)
        continuous_columns: list[np.ndarray] = []
        for name in CONTINUOUS:
            spec = transform["continuous"][name]
            raw = np.asarray(self.cells[name].iloc[selected], dtype=np.float64, copy=True)
            raw[~np.isfinite(raw)] = float(spec["mean"])
            continuous_columns.append((raw - float(spec["mean"])) / float(spec["population_sd"]))
        matrix = np.column_stack(continuous_columns) if continuous_columns else np.empty((len(selected), 0))
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
            allowed = set(levels)
            raw = self.cells[name].iloc[selected].astype("string").fillna("__MISSING__").astype(str).to_numpy()
            values = np.asarray([value if value in allowed else "__UNSEEN__" for value in raw], dtype=object)
            for level in levels:
                encoded.append((values == level).astype(np.float64))
                names.append(f"{name}={level}")
                kinds.append("categorical")
            categorical_payload[name] = levels
        if encoded:
            matrix = np.column_stack((matrix, *encoded))
        require(np.isfinite(matrix).all(), "encoded_feature_nonfinite")
        return EncodedFeatures(
            matrix,
            tuple(names),
            tuple(kinds),
            continuous_count,
            RETAINED_FULL_TRANSFORM,
            digest({"id": RETAINED_FULL_TRANSFORM, "transform": transform, "q_linear": q is not None}),
            digest(categorical_payload),
        )

    def q_collapsed_rows(
        self, held_block: int, held_fold: int, auxiliary_size: str
    ) -> tuple[Any, dict[str, Any]]:
        if held_fold != FULL_FOLD:
            return super().q_collapsed_rows(held_block, held_fold, auxiliary_size)
        # This is the native q row construction with only the fold mask changed
        # to all retained cells.  Whole focal-block exclusion and equal-head
        # collapse are intentionally kept identical to SeawfbStore.
        block_key = str(held_block)
        require(block_key in self.crossfit["auxiliary_sets"], "q_block_invalid")
        require(auxiliary_size in ("20", "80", "full"), "q_endpoint_invalid")
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
        background_base = complement_richness >= 10
        row_indices: list[np.ndarray] = []
        labels: list[np.ndarray] = []
        for head in heads:
            present = self.presence_mask(head)
            indices = np.flatnonzero(present | ((~present) & background_base))
            row_indices.append(indices)
            labels.append(present[indices].astype(np.int8))
        from .seawfb_modeling import collapse_equal_head_rows

        collapsed = collapse_equal_head_rows(row_indices, labels)
        total_per_head = [collapsed.expanded_rows / len(heads)] * len(heads)
        return collapsed, {
            "held_block": held_block,
            "held_fold": FULL_FOLD,
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


@dataclass(frozen=True)
class TargetFullData:
    replay: IndexedRows
    train: FeatureBatch
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class AuxiliaryFullData:
    replay: IndexedRows
    heads: tuple[str, ...]
    metadata: Mapping[str, Any]


def _q_features(
    store: RetainedFullStore,
    indices: np.ndarray,
    q_model: QLinearModel | None,
) -> tuple[EncodedFeatures, dict[str, float] | None]:
    base = store.encoded(indices, FULL_FOLD)
    if q_model is None:
        return base, None
    require(q_model.held_fold == FULL_FOLD, "retained_full_q_scope_invalid")
    require(q_model.transform_id == RETAINED_FULL_TRANSFORM, "q_transform_mismatch")
    raw = q_model.raw_scores(base)
    mean, sd = float(raw.mean()), float(raw.std(ddof=0))
    require(np.isfinite(mean) and np.isfinite(sd) and sd > 0, "q_scale_invalid")
    return store.encoded(indices, FULL_FOLD, q=(raw - mean) / sd), {
        "training_mean": mean,
        "training_population_sd": sd,
    }


def target_full_data(
    store: RetainedFullStore,
    target: str,
    q_model: QLinearModel | None = None,
) -> TargetFullData:
    """Build retained-full focal training rows and their structural batch."""

    rows = store.target_rows(target, FULL_FOLD, 100, "train")
    require(np.array_equal(rows.indices, np.sort(rows.indices)), "retained_full_rows_not_sorted")
    if q_model is not None:
        require(
            q_model.held_block == int(store.crossfit["focal_blocks"][target]),
            "retained_full_q_scope_invalid",
        )
    features, q_scaling = _q_features(store, rows.indices, q_model)
    replay = IndexedRows(features.x, np.arange(len(rows.indices), dtype=np.int64), rows.y)
    train = FeatureBatch(
        tuple(RowKey(target, cell) for cell in rows.cell_ids),
        features.x,
        rows.y.astype(np.float64),
        features.names,
        features.kinds,
        features.continuous_count,
        _feature_schema(features),
        {},
        features.transform_id,
        features.transform_digest,
        features.encoder_digest,
    )
    metadata = {
        "target": target,
        "fraction": 100,
        "held_fold": FULL_FOLD,
        "rows": len(rows.indices),
        "row_digest": row_digest(rows.indices, rows.y, rows.source_folds),
        "rows_digest": row_digest(rows.indices, rows.y, rows.source_folds),
        "cell_id_digest": _digest_strings(rows.cell_ids),
        "cell_ids_digest": _digest_strings(rows.cell_ids),
        "folds": sorted(set(map(int, rows.source_folds.tolist()))),
        "folds_digest": _digest_bytes(rows.source_folds, "<i1"),
        "transform_id": features.transform_id,
        "transform_digest": features.transform_digest,
        "encoder_digest": features.encoder_digest,
        "feature_width": int(features.x.shape[1]),
        "q_scaling": q_scaling,
    }
    return TargetFullData(replay, train, metadata)


def auxiliary_full_data(store: RetainedFullStore, block: int) -> AuxiliaryFullData:
    """Build all retained auxiliary heads after whole-block focal exclusion."""

    block_key = str(block)
    require(block_key in store.crossfit["auxiliary_sets"], "neural_auxiliary_block_invalid")
    held_species = sorted(
        species for species, value in store.crossfit["focal_blocks"].items() if int(value) == block
    )
    heads = tuple(store.crossfit["auxiliary_sets"][block_key]["full"])
    require(heads and len(set(heads)) == len(heads), "neural_auxiliary_head_invalid")
    require(not set(heads).intersection(held_species), "neural_auxiliary_head_leakage")
    richness = store.richness.copy()
    for species in held_species:
        richness[store.presence_indices[species]] -= 1
    require(np.all(richness >= 0), "neural_complement_richness_negative")
    indices_by_head: list[np.ndarray] = []
    labels_by_head: list[np.ndarray] = []
    heads_by_row: list[np.ndarray] = []
    for head_index, species in enumerate(heads):
        present = store.presence_mask(species)
        indices = np.flatnonzero(present | ((~present) & (richness >= 10)))
        indices_by_head.append(indices)
        labels_by_head.append(present[indices].astype(np.int8))
        heads_by_row.append(np.full(len(indices), head_index, dtype=np.int32))
    cell_indices = np.concatenate(indices_by_head)
    labels = np.concatenate(labels_by_head)
    head = np.concatenate(heads_by_row)
    folds = store.folds[cell_indices]
    cells = np.unique(cell_indices)
    encoded = store.encoded(cells, FULL_FOLD)
    mapped = np.searchsorted(cells, cell_indices)
    replay, weights = _balanced_rows(encoded.x, mapped, labels, head, len(heads))
    metadata = {
        "held_block": block,
        "held_fold": FULL_FOLD,
        "heads": list(heads),
        "excluded_species": held_species,
        "rows": len(cell_indices),
        "row_digest": row_digest(cell_indices, labels, folds, head),
        "rows_digest": row_digest(cell_indices, labels, folds, head),
        "cell_id_digest": _digest_strings(store.cell_ids[cells].tolist()),
        "cell_ids_digest": _digest_strings(store.cell_ids[cells].tolist()),
        "folds": sorted(set(map(int, folds.tolist()))),
        "folds_digest": _digest_bytes(folds, "<i1"),
        "transform_id": encoded.transform_id,
        "transform_digest": encoded.transform_digest,
        "encoder_digest": encoded.encoder_digest,
        "feature_width": int(encoded.x.shape[1]),
        "head_weight_digest": _digest_bytes(replay.weights, "<f4"),
        "weights": weights,
    }
    return AuxiliaryFullData(replay, heads, metadata)


def _domain_arrays(domain: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, Mapping[str, Any], str]:
    require(isinstance(domain, Mapping), "outer_domain_mapping_invalid")
    arrays = domain.get("arrays", domain)
    summary = domain.get("summary", {})
    require(isinstance(arrays, Mapping), "outer_domain_arrays_invalid")
    require("cell_ids" in arrays and "x" in arrays, "outer_domain_arrays_missing")
    cell_ids = np.asarray(arrays["cell_ids"], dtype=str)
    # Preserve native float64 transforms for conventional and q prediction.
    # Neural replay and prediction perform their own native float32 conversion.
    x = np.asarray(arrays["x"], dtype=np.float64)
    require(cell_ids.ndim == 1 and len(cell_ids) > 0 and len(set(cell_ids.tolist())) == len(cell_ids), "outer_domain_cell_ids_invalid")
    require(x.ndim == 2 and x.shape == (len(cell_ids), EXPECTED_FEATURES) and np.isfinite(x).all(), "outer_domain_feature_shape_invalid")
    species = str(domain.get("target", domain.get("species_id", OUTER_PREDICTION_SPECIES)))
    require(species, "outer_domain_species_invalid")
    return cell_ids, x, summary, species


def prediction_batch(
    store: RetainedFullStore,
    domain: Mapping[str, Any],
    q_model: QLinearModel | None = None,
    q_scaling: Mapping[str, float] | None = None,
) -> FeatureBatch:
    """Create a response-free batch from a complete outer predictor mapping."""

    cell_ids, x, summary, species = _domain_arrays(domain)
    metadata = full_encoded_metadata(store, q=q_model is not None)
    base_metadata = full_encoded_metadata(store, q=False)
    expected_order = list(base_metadata["feature_names"])
    if isinstance(summary, Mapping) and "feature_count" in summary:
        require(int(summary["feature_count"]) == EXPECTED_FEATURES, "outer_domain_feature_count_mismatch")
    if isinstance(summary, Mapping) and "feature_order" in summary:
        require(list(summary["feature_order"]) == expected_order, "outer_domain_feature_order_mismatch")
    if q_model is not None:
        require(q_model.held_fold == FULL_FOLD, "retained_full_q_scope_invalid")
        require(q_scaling is not None, "q_scaling_required")
        mean = q_scaling.get("training_mean")
        sd = q_scaling.get("training_population_sd")
        require(mean is not None and sd is not None, "q_scaling_invalid")
        base = EncodedFeatures(
            x,
            tuple(base_metadata["feature_names"]),
            tuple(base_metadata["feature_kinds"]),
            int(base_metadata["continuous_count"]),
            RETAINED_FULL_TRANSFORM,
            base_metadata["transform_digest"],
            base_metadata["encoder_digest"],
        )
        raw = q_model.raw_scores(base)
        sd = float(sd); mean = float(mean)
        require(np.isfinite(mean) and np.isfinite(sd) and sd > 0, "q_scaling_invalid")
        q = (raw - mean) / sd
        x_features = EncodedFeatures(
            np.insert(x, int(metadata["continuous_count"] - 1), q, axis=1),
            tuple(metadata["feature_names"]),
            tuple(metadata["feature_kinds"]),
            int(metadata["continuous_count"]),
            RETAINED_FULL_TRANSFORM,
            metadata["transform_digest"],
            metadata["encoder_digest"],
        )
    else:
        require(q_scaling is None, "q_scaling_without_model")
        x_features = EncodedFeatures(
            x,
            tuple(metadata["feature_names"]),
            tuple(metadata["feature_kinds"]),
            int(metadata["continuous_count"]),
            RETAINED_FULL_TRANSFORM,
            metadata["transform_digest"],
            metadata["encoder_digest"],
        )
    return FeatureBatch(
        tuple(RowKey(species, cell) for cell in cell_ids.tolist()),
        x_features.x,
        np.zeros(len(cell_ids), dtype=np.float64),
        x_features.names,
        x_features.kinds,
        x_features.continuous_count,
        _feature_schema(x_features),
        {},
        x_features.transform_id,
        x_features.transform_digest,
        x_features.encoder_digest,
    )
