from __future__ import annotations

import numpy as np
import pytest

from dsdm_phase1.seawfb_dsdm_data import auxiliary_data, target_data
from dsdm_phase1.seawfb_modeling import EncodedFeatures, QLinearModel, ResponseRows, SeawfbStore


class SyntheticSeawfbStore(SeawfbStore):
    """Small in-memory store exposing only the data interfaces under test."""

    def __init__(self, *, missing_head: bool = False):
        self.cell_ids = np.asarray([f"cell-{i}" for i in range(10)])
        self.folds = np.asarray([0, 1, 2, 3, 4, 0, 1, 2, 3, 4], dtype=np.int8)
        self.richness = np.full(10, 10, dtype=np.int64)
        self.presence_indices = {
            "target_a": np.asarray([2, 5]),
            "target_b": np.asarray([6, 8]),
            "donor_a": np.asarray([3, 4]),
            "donor_b": np.asarray([7]),
        }
        if missing_head:
            # donor_b then has no discovery-fold row when richness is below
            # the background threshold; its only row is in stopping fold 1.
            self.richness[:] = 9
            self.presence_indices["donor_a"] = np.asarray([1, 3])
            self.presence_indices["donor_b"] = np.asarray([1])
        self.crossfit = {
            "focal_blocks": {"target_a": 0, "target_b": 0},
            "auxiliary_sets": {
                "0": {
                    "20": ["donor_a", "donor_b"],
                    "80": ["donor_a", "donor_b"],
                    "full": ["donor_a", "donor_b"],
                }
            },
        }
        self.encoded_calls: list[tuple[tuple[int, ...], int]] = []

    def presence_mask(self, species: str) -> np.ndarray:
        mask = np.zeros(len(self.cell_ids), dtype=bool)
        mask[self.presence_indices[species]] = True
        return mask

    def encoded(self, indices, held_fold: int) -> EncodedFeatures:
        selected = np.asarray(indices, dtype=np.int64)
        self.encoded_calls.append((tuple(selected.tolist()), held_fold))
        features = np.zeros((len(selected), 21), dtype=np.float32)
        features[:, 0] = selected
        return EncodedFeatures(
            features,
            tuple(f"continuous_{i}" for i in range(21)),
            ("continuous",) * 21,
            21,
            f"fold_{held_fold}",
            "transform-digest",
            "encoder-digest",
        )


class StubTargetStore:
    """Target-row-plan stub: calls return frozen rows without resampling."""

    def __init__(self):
        self.crossfit = {"focal_blocks": {"target": 2}}
        self.train = ResponseRows(
            np.asarray([0, 1, 2, 3]),
            ("cell-0", "cell-1", "cell-2", "cell-3"),
            np.asarray([1, 0, 1, 0]),
            np.asarray([1, 2, 1, 3]),
        )
        self.held = ResponseRows(
            np.asarray([4, 5]),
            ("cell-4", "cell-5"),
            np.asarray([0, 1]),
            np.asarray([0, 0]),
        )
        self.calls: list[tuple[str, int, int, str]] = []
        self.encoded_calls: list[tuple[tuple[int, ...], int]] = []

    def target_rows(self, target: str, held_fold: int, fraction: int, role: str) -> ResponseRows:
        self.calls.append((target, held_fold, fraction, role))
        return self.train if role == "train" else self.held

    def encoded(self, indices, held_fold: int) -> EncodedFeatures:
        selected = np.asarray(indices, dtype=np.int64)
        self.encoded_calls.append((tuple(selected.tolist()), held_fold))
        features = np.zeros((len(selected), 21), dtype=np.float32)
        features[:, 0] = selected
        return EncodedFeatures(
            features,
            tuple(f"continuous_{i}" for i in range(21)),
            ("continuous",) * 21,
            21,
            f"fold_{held_fold}",
            "transform-digest",
            "encoder-digest",
        )


def _q_model(*, held_block: int = 2, held_fold: int = 0) -> QLinearModel:
    return QLinearModel(
        np.asarray([1.0] + [0.0] * 20),
        0.0,
        held_block,
        held_fold,
        "full",
        "fold_0",
        1,
    )


def test_auxiliary_data_removes_whole_block_and_reuses_one_feature_matrix():
    store = SyntheticSeawfbStore()
    result = auxiliary_data(store, block=0, held_fold=0, auxiliary="full")

    assert result.heads == ("donor_a", "donor_b")
    assert set(result.metadata["held_species"]) == {"target_a", "target_b"}
    assert len(store.encoded_calls) == 1
    assert result.discovery.features is result.stopping.features is result.replay.features
    donor_a_rows = result.replay.head_index == 0
    donor_a_cells = result.replay.features[result.replay.indices[donor_a_rows], 0].astype(int)
    # Cell 2 has full richness 10 but loses target_a's held-block membership,
    # so it cannot be a donor background after the complement adjustment.
    assert 2 not in set(donor_a_cells.tolist())
    assert not set(result.heads).intersection({"target_a", "target_b"})


def test_auxiliary_roles_exclude_held_fold_and_partition_discovery_stopping_replay():
    store = SyntheticSeawfbStore()
    result = auxiliary_data(store, block=0, held_fold=0, auxiliary="full")
    role_rows = {role: getattr(result, role) for role in ("discovery", "stopping", "replay")}

    def cells(rows):
        return rows.features[rows.indices, 0].astype(int)

    assert all(np.all(store.folds[cells(rows)] != 0) for rows in role_rows.values())
    discovery = set(map(int, cells(role_rows["discovery"])))
    stopping = set(map(int, cells(role_rows["stopping"])))
    replay = set(map(int, cells(role_rows["replay"])))
    assert discovery.isdisjoint(stopping)
    assert discovery | stopping == replay
    assert set(store.folds[list(replay)]) == {1, 2, 3, 4}
    assert result.metadata["stopping_fold"] == 1
    assert result.metadata["discovery_folds"] == [2, 3, 4]
    assert result.metadata["replay_folds"] == [1, 2, 3, 4]


def test_auxiliary_weights_balance_head_totals_without_changing_class_prevalence():
    store = SyntheticSeawfbStore()
    result = auxiliary_data(store, block=0, held_fold=0, auxiliary="full")

    for role in ("discovery", "stopping", "replay"):
        rows = getattr(result, role)
        totals = [rows.weights[rows.head_index == head].sum() for head in (0, 1)]
        assert np.allclose(totals, totals[0], rtol=0, atol=1e-6)
        for head, species in enumerate(result.heads):
            cells = rows.features[rows.indices[rows.head_index == head], 0].astype(int)
            expected = np.isin(cells, store.presence_indices[species]).astype(np.float32)
            np.testing.assert_array_equal(rows.y[rows.head_index == head], expected)
    assert result.metadata["weights"]["replay"]["within_head_class_balancing"] is False


def test_missing_head_role_fails_before_an_auxiliary_dataset_is_returned():
    with pytest.raises(ValueError, match="missing_head"):
        auxiliary_data(SyntheticSeawfbStore(missing_head=True), block=0, held_fold=0, auxiliary="full")


def test_target_data_reuses_frozen_rows_and_splits_roles_without_resampling():
    store = StubTargetStore()
    result = target_data(store, "target", held_fold=0, fraction=25)

    assert store.calls == [
        ("target", 0, 25, "train"),
        ("target", 0, 25, "validation"),
    ]
    assert set(result.replay.features[result.replay.indices, 0]) == {0, 1, 2, 3}
    assert set(result.stopping.features[result.stopping.indices, 0]) == {0, 2}
    assert set(result.discovery.features[result.discovery.indices, 0]) == {1, 3}
    assert result.metadata["held_rows"] == 2
    assert tuple(result.held_cells) == ("cell-4", "cell-5")


def test_target_q_scaling_uses_fraction_training_rows_and_inserts_after_21_continuous_features():
    store = StubTargetStore()
    result = target_data(store, "target", held_fold=0, fraction=25, q_model=_q_model())
    raw = 1.0 / (1.0 + np.exp(-np.asarray([0, 1, 2, 3, 4, 5], dtype=float)))
    expected_mean = float(raw[:4].mean())
    expected_sd = float(raw[:4].std(ddof=0))

    assert result.metadata["feature_width"] == 22
    assert result.metadata["q_scaling"]["training_mean"] == pytest.approx(expected_mean)
    assert result.metadata["q_scaling"]["training_population_sd"] == pytest.approx(expected_sd)
    assert result.metadata["q_scaling"]["training_mean"] != pytest.approx(float(raw.mean()))
    expected_q = (raw[:4] - expected_mean) / expected_sd
    np.testing.assert_allclose(result.replay.features[result.replay.indices, 21], expected_q)
    np.testing.assert_allclose(result.replay.features[result.replay.indices, :21][:, 0], [0, 1, 2, 3])


@pytest.mark.parametrize("kwargs", [{"held_block": 3}, {"held_fold": 1}])
def test_target_q_scope_rejects_wrong_block_or_fold(kwargs):
    store = StubTargetStore()
    with pytest.raises(ValueError, match="q_scope_mismatch"):
        target_data(store, "target", held_fold=0, fraction=25, q_model=_q_model(**kwargs))
