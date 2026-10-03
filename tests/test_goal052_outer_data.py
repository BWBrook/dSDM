from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dsdm_phase1.goal052_outer_predictors import _encode_retained_full
from dsdm_phase1.goal050_seawfb_foundation import CATEGORICAL, CONTINUOUS
from dsdm_phase1.goal052_outer_data import (
    FULL_FOLD,
    OUTER_PREDICTION_SPECIES,
    RetainedFullStore,
    auxiliary_full_data,
    full_encoded_metadata,
    prediction_batch,
    target_full_data,
)
from dsdm_phase1.seawfb_modeling import QLinearModel


class SyntheticRetainedStore(RetainedFullStore):
    def __init__(self) -> None:
        n = 15
        self.cell_ids = np.asarray([f"cell-{i:02d}" for i in range(n)])
        self.folds = np.asarray([i % 5 for i in range(n)], dtype=np.int8)
        self.richness = np.asarray([10, 9, 10, 11, 10, 9, 12, 10, 9, 13, 10, 11, 10, 9, 12], dtype=np.int64)
        self.presence_indices = {
            "target_a": np.asarray([0, 4]),
            "target_b": np.asarray([1, 5]),
            "donor_a": np.asarray([2, 3, 7]),
            "donor_b": np.asarray([6, 8, 12]),
        }
        self.crossfit = {
            "focal_blocks": {"target_a": 0, "target_b": 0},
            "auxiliary_sets": {"0": {"20": ["donor_a"], "80": ["donor_a"], "full": ["donor_a", "donor_b"]}},
        }
        self._response_cache = {}
        self.transforms = {
            "transforms": {
                "retained_full": {
                    "continuous": {name: {"mean": 10.0, "population_sd": 2.0} for name in CONTINUOUS},
                    "categorical": {
                        "nvis_mvg": ["__MISSING__", "__UNSEEN__", "known", *[f"n{i}" for i in range(29)]],
                        "soil_order": ["__MISSING__", "__UNSEEN__", "soil", *[f"s{i}" for i in range(13)]],
                        "alum_secondary": ["__MISSING__", "__UNSEEN__", "alum", *[f"a{i}" for i in range(31)]],
                    },
                }
            }
        }
        frame = {name: np.arange(n, dtype=float) + 10.0 for name in CONTINUOUS}
        frame["bio01"][2] = np.nan
        frame["nvis_mvg"] = ["known", None, "unknown", "known", "known"] * 3
        frame["soil_order"] = ["soil", "soil", "unknown", None, "soil"] * 3
        frame["alum_secondary"] = ["alum", "unknown", "alum", "alum", None] * 3
        self.cells = pd.DataFrame(frame)
        self.cells.insert(0, "cell_id", self.cell_ids)


def _q_model() -> QLinearModel:
    coefficient = np.zeros(103, dtype=float)
    coefficient[0] = 1.0
    return QLinearModel(coefficient, 0.0, 0, FULL_FOLD, "full", "retained_full", 1)


def _domain(store: SyntheticRetainedStore, indices: np.ndarray) -> dict[str, object]:
    base = store.encoded(indices, FULL_FOLD)
    metadata = full_encoded_metadata(store)
    return {
        "arrays": {"cell_ids": np.asarray([f"outer-{i}" for i in range(len(indices))]), "x": base.x},
        "summary": {"feature_order": list(metadata["feature_names"]), "feature_count": 103},
    }


def test_retained_full_target_rows_include_all_folds_and_native_eligibility():
    store = SyntheticRetainedStore()
    rows = store.target_rows("target_a", FULL_FOLD, 100, "train")
    present = store.presence_mask("target_a")
    expected = np.flatnonzero(present | ((~present) & (store.richness >= 10)))
    np.testing.assert_array_equal(rows.indices, expected)
    assert set(rows.source_folds.tolist()) == set(range(5))
    with pytest.raises(ValueError, match="retained_full_target_scope_invalid"):
        store.target_rows("target_a", FULL_FOLD, 25, "train")
    with pytest.raises(ValueError, match="retained_full_target_scope_invalid"):
        store.target_rows("target_a", FULL_FOLD, 100, "validation")


def test_retained_full_transform_matches_goal050_encoder_and_metadata():
    store = SyntheticRetainedStore()
    indices = np.asarray([1, 2, 3, 4])
    encoded = store.encoded(indices, FULL_FOLD)
    raw = store.cells.iloc[indices][[*CONTINUOUS, *CATEGORICAL]]
    expected = _encode_retained_full(raw, store.transforms["transforms"]["retained_full"])
    np.testing.assert_array_equal(encoded.x, expected)
    metadata = full_encoded_metadata(store)
    assert encoded.names == metadata["feature_names"]
    assert encoded.kinds == metadata["feature_kinds"]
    assert encoded.continuous_count == 21
    assert encoded.transform_digest == metadata["transform_digest"]
    assert encoded.encoder_digest == metadata["encoder_digest"]
    nvis_unseen = encoded.names.index("nvis_mvg=__UNSEEN__")
    nvis_missing = encoded.names.index("nvis_mvg=__MISSING__")
    assert encoded.x[1, nvis_unseen] == 1.0  # unseen categorical level
    assert encoded.x[0, nvis_missing] == 1.0  # missing categorical level


def test_target_full_q_scaling_uses_only_retained_target_rows():
    store = SyntheticRetainedStore()
    result = target_full_data(store, "target_a", _q_model())
    base = store.encoded(store.target_rows("target_a", FULL_FOLD, 100, "train").indices, FULL_FOLD)
    raw = 1.0 / (1.0 + np.exp(-base.x[:, 0]))
    expected_mean = float(raw.mean())
    expected_sd = float(raw.std(ddof=0))
    assert result.metadata["q_scaling"]["training_mean"] == pytest.approx(expected_mean)
    assert result.metadata["q_scaling"]["training_population_sd"] == pytest.approx(expected_sd)
    np.testing.assert_allclose(result.replay.features[:, 21], (raw - expected_mean) / expected_sd)
    assert result.train.continuous_count == 22
    assert result.metadata["folds"] == [0, 1, 2, 3, 4]


def test_auxiliary_full_excludes_whole_focal_block_and_balances_heads():
    store = SyntheticRetainedStore()
    result = auxiliary_full_data(store, 0)
    assert result.heads == ("donor_a", "donor_b")
    assert result.metadata["excluded_species"] == ["target_a", "target_b"]
    rows = result.replay
    for head in range(2):
        selected = rows.indices[rows.head_index == head]
        assert np.all(selected[:-1] <= selected[1:])
        assert np.allclose(rows.weights[rows.head_index == head].sum(), len(rows.indices) / 2, rtol=0, atol=1e-6)
    # Cell 0 has richness 10 but loses target_a from the complement count.
    donor_a_cells = rows.indices[rows.head_index == 0]
    complement = store.richness.copy()
    for species in ("target_a", "target_b"):
        complement[store.presence_indices[species]] -= 1
    all_cells = np.unique(np.concatenate([
        *[
            np.flatnonzero(store.presence_mask(species) | ((~store.presence_mask(species)) & (complement >= 10)))
            for species in result.heads
        ],
    ]))
    assert 0 not in all_cells[donor_a_cells]
    assert set(result.metadata["folds"]) == set(range(5))


def test_full_q_collapse_retains_all_folds_and_native_equal_head_weights():
    store = SyntheticRetainedStore()
    collapsed, receipt = store.q_collapsed_rows(0, FULL_FOLD, "full")
    assert set(receipt["heads"]) == {"donor_a", "donor_b"}
    assert set(receipt["head_rows"]) == {"donor_a", "donor_b"}
    assert receipt["head_total_weight_range"][0] == receipt["head_total_weight_range"][1]
    assert receipt["expanded_rows"] == sum(receipt["head_rows"].values())
    assert set(store.folds[collapsed.indices]) == set(range(5))


def test_prediction_batch_reuses_full_columns_and_q_scaling_without_response():
    store = SyntheticRetainedStore()
    domain = _domain(store, np.asarray([0, 1]))
    domain["arrays"]["x"][0, 0] = 0.12345678912345678
    batch = prediction_batch(store, domain)
    np.testing.assert_array_equal(batch.x, domain["arrays"]["x"])
    assert batch.x.dtype == np.float64
    assert batch.feature_names == full_encoded_metadata(store)["feature_names"]
    assert batch.transform_id == "retained_full"
    assert batch.keys[0] == (batch.keys[0].__class__)(OUTER_PREDICTION_SPECIES, "outer-0")
    np.testing.assert_array_equal(batch.y, np.zeros(2))

    trained = target_full_data(store, "target_a", _q_model())
    q_batch = prediction_batch(store, domain, _q_model(), trained.metadata["q_scaling"])
    assert q_batch.x.shape == (2, 104)
    assert q_batch.continuous_count == 22
    raw_q = 1.0 / (1.0 + np.exp(-domain["arrays"]["x"][:, 0]))
    scaling = trained.metadata["q_scaling"]
    np.testing.assert_allclose(q_batch.x[:, 21], (raw_q - scaling["training_mean"]) / scaling["training_population_sd"], rtol=0, atol=1e-15)
    with pytest.raises(ValueError, match="outer_domain_feature_order_mismatch"):
        bad = dict(domain)
        bad["summary"] = {"feature_order": ["wrong"]}
        prediction_batch(store, bad)
