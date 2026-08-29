import json
from pathlib import Path

import numpy as np
import pytest

from dsdm.contracts import ArchitectureSpec
from dsdm_phase1.goal045_mainland_dsdm import (
    _endpoint_tasks,
    _final_tasks,
    _selection_pretraining_tasks,
    _selection_tasks,
    validate_inputs,
)
from dsdm_phase1.mainland_dsdm import (
    MainlandDsdmError,
    NeuralDataset,
    equal_head_weights,
    fit_pretraining_lifecycle,
    fit_target_lifecycle,
)


ROOT = Path(__file__).resolve().parents[1]


def _config():
    return json.loads((ROOT / "config/goal045_mainland_dsdm.json").read_text())


def _binary(seed, rows, width):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(rows, width)).astype(np.float32)
    y = (x[:, 0] + 0.3 * x[:, 1] > 0).astype(np.float32)
    return x, y


def test_goal045_preserves_the_prospectively_frozen_goal044_design():
    goal045 = _config()
    goal044 = json.loads((ROOT / "config/goal044_mainland_conventional.json").read_text())

    assert goal045["design"] == goal044["goal045_frozen_design"]
    assert goal045["lifecycle"]["architecture_selection_seed_labels"] == ["seed00"]
    assert goal045["lifecycle"]["architecture_selection_arm"] == "multihead_full_finetune"
    assert goal045["privacy"]["tasmania_response_rows_read"] == 0
    assert goal045["privacy"]["tasmania_predictor_rows_used"] == 0


def test_goal045_task_plan_is_bounded_and_complete():
    config = _config()
    assert len(_endpoint_tasks(config)) == 35
    assert len(_selection_pretraining_tasks(config)) == 75
    assert len(_selection_tasks(config)) == 75
    assert len(_final_tasks(config, "bridge_control")) == 875


def test_equal_head_weights_equalize_heads_without_using_response_class():
    head = np.asarray([0, 0, 0, 1, 2, 2], dtype=np.int64)
    weights = equal_head_weights(head, 3)
    totals = np.bincount(head, weights=weights, minlength=3)

    assert np.allclose(totals, totals[0])
    assert np.mean(weights) == pytest.approx(1.0)
    assert weights[0] == weights[1] == weights[2]


def test_neural_dataset_rejects_nonpositive_weights():
    x, y = _binary(1, 8, 3)
    with pytest.raises(MainlandDsdmError, match="dataset_weights_invalid"):
        NeuralDataset(x, y, np.repeat([0, 1], 4), np.zeros(8))


def test_tiny_pretraining_and_transfer_lifecycle_runs_on_cpu():
    spec = ArchitectureSpec("tiny", 1, 8, 4, "constant", 0.0, 0.001)
    heads = ("aux_a", "aux_b")

    def auxiliary(seed, rows):
        x, y = _binary(seed, rows, 4)
        head = np.tile(np.asarray([0, 1], dtype=np.int64), rows // 2)
        return NeuralDataset(x, y, head, equal_head_weights(head, 2))

    state, pretraining = fit_pretraining_lifecycle(
        spec, auxiliary(1, 16), auxiliary(2, 8), auxiliary(3, 24), heads,
        seed=45, device_name="cpu", batch_size=8, max_epochs=2, patience=1,
        min_delta=0.0,
    )
    x_discovery, y_discovery = _binary(4, 16, 4)
    x_stopping, y_stopping = _binary(5, 8, 4)
    x_replay, y_replay = _binary(6, 24, 4)
    held_x, _ = _binary(7, 6, 4)
    scores, receipt = fit_target_lifecycle(
        spec,
        NeuralDataset(x_discovery, y_discovery),
        NeuralDataset(x_stopping, y_stopping),
        NeuralDataset(x_replay, y_replay),
        held_x,
        seed=46, device_name="cpu", batch_size=8, max_epochs=2, patience=1,
        min_delta=0.0, transferred_state=state, freeze_trunk=True,
    )

    assert pretraining["auxiliary_heads"] == list(heads)
    assert pretraining["within_head_class_balancing"] is False
    assert receipt["transferred"] is True
    assert receipt["freeze_trunk"] is True
    assert scores.shape == (6,)
    assert np.isfinite(scores).all()
    assert np.all((scores >= 0) & (scores <= 1))


def test_live_input_gate_keeps_tasmania_sealed():
    gate = validate_inputs(ROOT)
    assert gate["status"] == "goal045_inputs_ready"
    assert gate["tasmania_response_rows_read"] == 0
    assert gate["tasmania_predictor_rows_used"] == 0
