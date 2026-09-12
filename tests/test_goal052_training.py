import numpy as np
import torch

from dsdm.contracts import ArchitectureSpec
from dsdm.models import MultiHeadResidual, ResidualMLP
from dsdm_phase1.mainland_dsdm import state_digest
from dsdm_phase1.seawfb_dsdm_data import IndexedRows
from dsdm_phase1.seawfb_dsdm_training import (
    _indexed_tensors,
    _logits,
    _weighted_loss,
    fit_pretraining_lifecycle,
    fit_target_lifecycle,
)


SPEC = ArchitectureSpec("tiny", 1, 8, 4, "constant", 0.0, 0.001)


def _rows(seed: int, width: int, n_cells: int = 7, n_rows: int = 18, *, heads: int | None = None) -> IndexedRows:
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(n_cells, width)).astype(np.float32)
    indices = rng.integers(0, n_cells, size=n_rows, dtype=np.int64)
    y = (rng.random(n_rows) > 0.45).astype(np.float32)
    if heads is None:
        return IndexedRows(features, indices, y)
    head = np.arange(n_rows, dtype=np.int64) % heads
    weights = (n_rows / (heads * np.bincount(head, minlength=heads)[head])).astype(np.float32)
    return IndexedRows(features, indices, y, head, weights)


def test_indexed_and_dense_weighted_bce_have_same_loss_and_gradient():
    rows = _rows(3, 4, n_cells=5, n_rows=12, heads=3)
    torch.manual_seed(17)
    model_indexed = MultiHeadResidual(SPEC, 4, ("a", "b", "c"))
    model_dense = MultiHeadResidual(SPEC, 4, ("a", "b", "c"))
    model_dense.load_state_dict(model_indexed.state_dict())
    device = torch.device("cpu")
    tensors = _indexed_tensors(rows, device, require_heads=True)
    dense_x = torch.from_numpy(rows.features[rows.indices])
    y = torch.from_numpy(rows.y)
    weights = torch.from_numpy(rows.weights)
    head = torch.from_numpy(rows.head_index)
    indexed_loss = _weighted_loss(_logits(model_indexed, tensors.features[tensors.indices], tensors.head, ("a", "b", "c")), tensors.y, tensors.weights)
    dense_loss = _weighted_loss(_logits(model_dense, dense_x, head, ("a", "b", "c")), y, weights)
    indexed_loss.backward()
    dense_loss.backward()
    assert indexed_loss.item() == dense_loss.item()
    for left, right in zip(model_indexed.parameters(), model_dense.parameters(), strict=True):
        assert torch.equal(left.grad, right.grad)


def test_target_replay_is_deterministic_and_provenance_is_complete():
    rows = _rows(5, 4)
    kwargs = dict(seed=91, device_name="cpu", batch_size=8, max_epochs=3, patience=2, min_delta=1e-5)
    first = fit_target_lifecycle(SPEC, rows, rows, rows, rows.features, **kwargs)
    second = fit_target_lifecycle(SPEC, rows, rows, rows, rows.features, **kwargs)
    assert np.array_equal(first[0], second[0])
    for key in ("initial_model_digest", "replay_initial_model_digest", "final_model_digest", "stopping_history", "selected_epoch", "replay_epochs"):
        assert first[1][key] == second[1][key]
    assert first[1]["discovery_shuffle_seed"] == 91
    assert first[1]["replay_shuffle_seed"] == 100091
    assert first[1]["state_finite"] is True


def test_target_head_initialisation_matches_across_input_widths():
    receipts = []
    for width in (3, 4, 7):
        rows = _rows(10 + width, width)
        _, receipt = fit_target_lifecycle(
            SPEC, rows, rows, rows, rows.features,
            seed=104, device_name="cpu", batch_size=128, max_epochs=1, patience=1, min_delta=1e-5,
        )
        receipts.append(receipt)
    assert len({receipt["initial_head_digest"] for receipt in receipts}) == 1


def test_frozen_target_preserves_transferred_shared_state_and_full_fit_changes_it():
    rows = _rows(21, 4)
    pre_rows = _rows(22, 4, heads=2)
    transferred, _ = fit_pretraining_lifecycle(
        SPEC, pre_rows, pre_rows, pre_rows, ("a", "b"),
        seed=77, device_name="cpu", batch_size=8, max_epochs=1, patience=1, min_delta=1e-5,
    )
    _, frozen = fit_target_lifecycle(
        SPEC, rows, rows, rows, rows.features,
        seed=78, device_name="cpu", batch_size=8, max_epochs=2, patience=2, min_delta=0.0,
        transferred_state=transferred, freeze_trunk=True,
    )
    _, full = fit_target_lifecycle(
        SPEC, rows, rows, rows, rows.features,
        seed=78, device_name="cpu", batch_size=8, max_epochs=2, patience=2, min_delta=0.0,
        transferred_state=transferred, freeze_trunk=False,
    )
    assert frozen["freeze_shared_state_invariant"] is True
    assert frozen["initial_shared_digest"] == frozen["final_shared_digest"]
    assert full["initial_shared_digest"] != full["final_shared_digest"]


def test_pretraining_equal_head_weights_has_finite_shared_state_and_receipt_provenance():
    rows = _rows(31, 4, n_rows=20, heads=3)
    state, receipt = fit_pretraining_lifecycle(
        SPEC, rows, rows, rows, ("head0", "head1", "head2"),
        seed=88, device_name="cpu", batch_size=128, max_epochs=2, patience=1, min_delta=1e-5,
    )
    assert receipt["auxiliary_head_count"] == 3
    assert receipt["auxiliary_heads"] == ["head0", "head1", "head2"]
    assert receipt["within_head_class_balancing"] is False
    assert receipt["shared_state_digest"] == state_digest(state)
    assert receipt["state_finite"] is True
    assert all(torch.isfinite(value).all() for value in state.values())
