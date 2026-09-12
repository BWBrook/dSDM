from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from dsdm_phase1 import goal052_seawfb_dsdm as runner
from dsdm_phase1.goal052_checkpoints import load_pretraining
from dsdm_phase1.seawfb_dsdm_data import IndexedRows
from dsdm_phase1.seawfb_modeling import ResponseRows, digest


def _identity():
    return {
        "goal051_identity": {"fake": "goal051"},
        "acceptance_sha256": "a" * 64,
        "baseline_summary_sha256": "b" * 64,
        "source_sha256": "c" * 64,
    }


def _config():
    return {
        "architectures": {
            "constants": {"batch_size": 128, "max_epochs": 1, "patience": 1, "min_improvement": 1e-5},
            "candidates": [{"id": "bridge_control", "blocks": 1, "width": 8, "bottleneck": 4, "dropout": 0.0, "weight_decay": 0.001}],
        },
        "execution": {"private_root": "private"},
    }


def test_goal052_task_inventory_and_reuse_are_exact():
    primary = tuple(f"primary-{i:03d}" for i in range(73))
    focal = primary + tuple(f"focal-{i:03d}" for i in range(84))
    blocks = tuple(range(10))
    selection_pre = runner.selection_pretraining_tasks(blocks)
    remaining_pre = runner.remaining_pretraining_tasks(blocks, "bridge_control")
    selection = runner.selection_tasks(primary)
    final = runner.final_tasks(primary, focal, "bridge_control")

    assert len(selection_pre) == 200
    assert len(remaining_pre) == 700
    assert len(set(selection_pre) & set(remaining_pre)) == 0
    assert len(selection_pre) + len(remaining_pre) == 900
    assert len(selection) == 1460
    assert len(final) == 41250
    assert len(set(selection) & set(final)) == 365


def test_goal052_keys_share_target_only_leaves_and_omit_arm_aux_from_numeric_seed():
    identity = _identity()
    parameters = inspect.signature(runner.target_seed).parameters
    assert set(parameters) == {"target", "fraction", "fold", "architecture", "seed"}
    assert runner.target_seed("t", 100, 2, "bridge_control", "seed00") == runner.target_seed("t", 100, 2, "bridge_control", "seed00")
    first = runner.leaf_key(identity, "t", 100, "20", runner.ARMS[0], "bridge_control", "seed00", 2)
    second = runner.leaf_key(identity, "t", 100, "80", runner.ARMS[0], "bridge_control", "seed00", 2)
    assert first["auxiliary"] == second["auxiliary"] == "none"
    assert first["arm"] == runner.ARMS[0]
    assert runner.pretraining_key(identity, 1, 2, "20", "bridge_control", "seed00")["auxiliary"] == "20"


def test_verify_fit_rejects_budget_initialisation_seed_and_freeze_drift():
    config = _config()
    expected = runner.fit_options(config, "cpu")
    base = {
        **expected,
        "seed": 19,
        "adamw_implementation": "foreach",
        "replay_shuffle_seed": 100019,
        "state_finite": True,
        "stopping_history_finite": True,
        "initial_model_digest": "a",
        "replay_initial_model_digest": "a",
        "transferred": False,
        "freeze_trunk": False,
        "replay_epochs": 1,
        "selected_epoch": 1,
        "completed_epochs": 1,
    }
    for mutation in (
        {"adamw_implementation": "fused"},
        {"max_epochs": 2},
        {"replay_initial_model_digest": "different"},
        {"seed": 20},
        {"freeze_trunk": True},
    ):
        receipt = {**base, **mutation}
        with pytest.raises(ValueError):
            runner.verify_fit(receipt, config, 19, transferred=False, frozen=False)


def _indexed_fixture(seed: int = 1) -> IndexedRows:
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(6, 4)).astype(np.float32)
    indices = np.asarray([0, 1, 2, 3, 4, 5, 0, 2, 4, 1], dtype=np.int64)
    y = np.asarray([0, 1, 0, 1, 1, 0, 1, 0, 1, 0], dtype=np.float32)
    return IndexedRows(features, indices, y)


def test_goal052_synthetic_run_pretraining_and_all_arms_resume_without_refit(tmp_path, monkeypatch):
    config = _config()
    identity = _identity()
    rows = _indexed_fixture()
    auxiliary_rows = IndexedRows(
        rows.features,
        np.tile(rows.indices, 2),
        np.tile(rows.y, 2),
        np.repeat(np.arange(2, dtype=np.int64), len(rows.y)),
        np.ones(2 * len(rows.y), dtype=np.float32),
    )
    auxiliary = SimpleNamespace(discovery=auxiliary_rows, stopping=auxiliary_rows, replay=auxiliary_rows,
                                heads=("aux-a", "aux-b"), metadata={"synthetic": True})
    target = SimpleNamespace(
        discovery=rows, stopping=rows, replay=rows, held_x=rows.features[:3],
        held_y=np.asarray([0, 1, 0], dtype=np.int8), held_cells=("held-0", "held-1", "held-2"),
        metadata={"synthetic": True},
    )

    monkeypatch.setattr(runner, "auxiliary_data", lambda *_args: auxiliary)
    monkeypatch.setattr(runner, "target_data", lambda *_args: target)
    monkeypatch.setattr(runner.baseline, "_config", lambda _root: {})
    q_receipt = {"source": "accepted-q-stub", "block": 0, "fold": 0, "auxiliary": "full"}
    monkeypatch.setattr(runner.baseline, "_load_q", lambda *_args: (object(), q_receipt))

    store = SimpleNamespace(
        target_rows=lambda *_args: ResponseRows(np.arange(3), target.held_cells, target.held_y, np.zeros(3, dtype=np.int8)),
        crossfit={"focal_blocks": {"target": 0}},
    )
    pre = runner.run_pretraining(tmp_path, store, config, identity, 0, 0, "full", "bridge_control", "seed00", "cpu")
    assert pre[1]["key"] == runner.pretraining_key(identity, 0, 0, "full", "bridge_control", "seed00")
    assert load_pretraining(tmp_path / "private", pre[1]["key"]) is not None

    calls = {arm: 0 for arm in runner.ARMS}
    original_fit = runner.fit_target_lifecycle

    def counting_fit(*args, **kwargs):
        calls[current_arm[0]] += 1
        return original_fit(*args, **kwargs)

    monkeypatch.setattr(runner, "fit_target_lifecycle", counting_fit)
    current_arm = [runner.ARMS[0]]
    receipts = {}
    for arm in runner.ARMS:
        current_arm[0] = arm
        receipts[arm] = runner.run_target(tmp_path, store, config, identity, "target", 100, "full", arm,
                                          "bridge_control", "seed00", 0, "cpu")
    assert set(receipts) == set(runner.ARMS)
    assert calls == {arm: 1 for arm in runner.ARMS}
    assert receipts[runner.ARMS[1]]["q_receipt_digest"] == digest(q_receipt)
    assert receipts[runner.ARMS[1]]["pretraining_receipt_digest"] is None
    for arm in runner.ARMS[2:]:
        assert receipts[arm]["pretraining_receipt_digest"] == digest(pre[1])

    # Existing leaf receipts are returned before data/model fitting is reached.
    for arm in runner.ARMS:
        current_arm[0] = arm
        runner.run_target(tmp_path, store, config, identity, "target", 100, "full", arm,
                          "bridge_control", "seed00", 0, "cpu")
    assert calls == {arm: 1 for arm in runner.ARMS}
