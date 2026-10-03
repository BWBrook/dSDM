from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
import torch

from dsdm.contracts import ArchitectureSpec
from dsdm_phase1.seawfb_dsdm_data import IndexedRows
from dsdm_phase1.seawfb_dsdm_training import fit_pretraining_lifecycle, fit_target_lifecycle
from dsdm_phase1.goal052_outer_training import fit_pretraining_fixed, fit_target_fixed
from dsdm_phase1.mainland_dsdm import state_digest


SPEC = ArchitectureSpec("tiny", 1, 8, 4, "constant", 0.0, 0.001)


def _rows(seed: int, width: int = 4, cells: int = 7, n: int = 24, *, heads: int | None = None) -> IndexedRows:
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(cells, width)).astype(np.float32)
    indices = rng.integers(0, cells, size=n, dtype=np.int64)
    y = (rng.random(n) > 0.45).astype(np.float32)
    if heads is None:
        return IndexedRows(features, indices, y)
    head = np.arange(n, dtype=np.int64) % heads
    weights = (n / (heads * np.bincount(head, minlength=heads)[head])).astype(np.float32)
    return IndexedRows(features, indices, y, head, weights)


def _assert_finite_cpu_state(state: dict[str, torch.Tensor]) -> None:
    assert state
    assert all(value.device.type == "cpu" for value in state.values())
    assert all(torch.isfinite(value).all().item() for value in state.values())


def test_fixed_target_matches_native_replay_at_native_selected_epoch():
    rows = _rows(4)
    native_scores, native_receipt = fit_target_lifecycle(
        SPEC, rows, rows, rows, rows.features,
        seed=91, device_name="cpu", batch_size=8, max_epochs=3, patience=2, min_delta=1e-5,
    )
    scores, state, receipt = fit_target_fixed(
        SPEC, rows, rows.features,
        seed=91, epochs=native_receipt["selected_epoch"], batch_size=8,
    )
    assert np.array_equal(scores, native_scores)
    assert receipt["final_model_digest"] == native_receipt["final_model_digest"]
    assert receipt["replay_seed"] == 100091
    assert receipt["completed_epochs"] == native_receipt["selected_epoch"]
    _assert_finite_cpu_state(state)


def test_fixed_pretraining_matches_native_shared_replay():
    rows = _rows(5, n=30, heads=3)
    names = ("aux_a", "aux_b", "aux_c")
    native_shared, native_receipt = fit_pretraining_lifecycle(
        SPEC, rows, rows, rows, names,
        seed=77, device_name="cpu", batch_size=8, max_epochs=3, patience=2, min_delta=1e-5,
    )
    full, shared, receipt = fit_pretraining_fixed(
        SPEC, rows, names, seed=77, epochs=native_receipt["selected_epoch"], batch_size=8,
    )
    assert state_digest(shared) == state_digest(native_shared)
    assert receipt["shared_state_digest"] == state_digest(shared)
    assert receipt["head_initialization_seed"] == 77
    _assert_finite_cpu_state(full)
    _assert_finite_cpu_state(shared)


def test_target_head_initialisation_is_paired_across_feature_widths():
    receipts = []
    for width in (3, 4, 7):
        rows = _rows(20 + width, width=width)
        _, _, receipt = fit_target_fixed(SPEC, rows, rows.features, seed=104, epochs=1)
        receipts.append(receipt)
    assert len({receipt["initial_head_digest"] for receipt in receipts}) == 1
    assert all(receipt["head_initialization_seed"] == 121 for receipt in receipts)


def test_frozen_target_preserves_transferred_shared_state_and_input_checkpoint():
    source_rows = _rows(21, heads=2)
    target_rows = _rows(22)
    _, transferred, _ = fit_pretraining_fixed(
        SPEC, source_rows, ("a", "b"), seed=77, epochs=1, batch_size=8,
    )
    before = deepcopy(transferred)
    _, final, receipt = fit_target_fixed(
        SPEC, target_rows, target_rows.features,
        seed=78, epochs=2, batch_size=8, transferred_state=transferred, freeze_trunk=True,
    )
    assert all(torch.equal(before[name], transferred[name]) for name in before)
    assert receipt["transferred"] is True
    assert receipt["transfer_digest"] == state_digest(before)
    assert receipt["freeze_shared_state_invariant"] is True
    assert receipt["initial_shared_digest"] == receipt["final_shared_digest"]
    _assert_finite_cpu_state(final)


def test_fixed_adapter_rejects_wrong_inputs():
    rows = _rows(30)
    with pytest.raises(ValueError, match="training_budget_invalid"):
        fit_target_fixed(SPEC, rows, rows.features, seed=1, epochs=0)
    with pytest.raises(ValueError, match="target_feature_width_drift"):
        fit_target_fixed(SPEC, rows, np.zeros((2, rows.features.shape[1] + 1), dtype=np.float32), seed=1, epochs=1)
    with pytest.raises(ValueError, match="held_features_nonfinite"):
        fit_target_fixed(SPEC, rows, np.full_like(rows.features, np.nan), seed=1, epochs=1)
    bad_heads = IndexedRows(rows.features, rows.indices, rows.y, np.zeros(len(rows.y), dtype=np.int64), np.ones(len(rows.y), dtype=np.float32))
    with pytest.raises(ValueError, match="pretraining_head_set_drift"):
        fit_pretraining_fixed(SPEC, bad_heads, ("a", "b"), seed=1, epochs=1)
    with pytest.raises(ValueError, match="target_head_index_forbidden"):
        fit_target_fixed(SPEC, bad_heads, rows.features, seed=1, epochs=1)
