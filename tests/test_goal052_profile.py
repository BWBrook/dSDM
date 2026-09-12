from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from dsdm_phase1 import goal052_seawfb_dsdm as runner
from dsdm_phase1.goal052_profile import PROFILE_PATH, profile
from dsdm_phase1.seawfb_dsdm_data import IndexedRows
from dsdm_phase1.seawfb_modeling import SeawfbModelingError


def _config():
    return {
        "architectures": {
            "constants": {"batch_size": 128, "max_epochs": 300, "patience": 30, "min_improvement": 1e-5},
            "candidates": [{"id": "seawfb_scale", "blocks": 1, "width": 8, "bottleneck": 4, "dropout": 0.0, "weight_decay": 0.001}],
        },
        "execution": {"canary_receipt": "metadata/goal052_canary.json"},
    }


def _identity():
    return {"goal051_identity": {"accepted": "q"}, "source_sha256": "s" * 64}


def _rows(row_count: int, *, heads: bool = False) -> IndexedRows:
    cells = np.arange(5, dtype=np.float32).reshape(5, 1)
    indices = np.arange(row_count, dtype=np.int64) % len(cells)
    y = (np.arange(row_count) % 2).astype(np.float32)
    if not heads:
        return IndexedRows(cells, indices, y)
    head = np.arange(row_count, dtype=np.int64) % 2
    return IndexedRows(cells, indices, y, head, np.ones(row_count, dtype=np.float32))


def _patched_profile(monkeypatch, tmp_path):
    config = _config()
    identity = _identity()
    auxiliary = SimpleNamespace(
        discovery=_rows(24, heads=True), stopping=_rows(16, heads=True), replay=_rows(28, heads=True),
        heads=("head-a", "head-b"), metadata={"full": True},
    )
    target_data = SimpleNamespace(
        discovery=_rows(13), stopping=_rows(11), replay=_rows(17),
        held_x=np.ones((1500, 1), dtype=np.float32), held_y=np.zeros(1500, dtype=np.int8),
        held_cells=tuple(f"cell-{i}" for i in range(1500)), metadata={"target": True},
    )
    store = SimpleNamespace(crossfit={"focal_blocks": {"target": 7}})
    identity_calls = []
    pre_calls = []
    target_calls = []
    q_calls = []
    state = {"shared": torch.ones(2)}
    q_model = object()
    q_receipt = {"model_sha256": "q" * 64, "accepted": True}
    runtime = {"device": "cpu", "host": "synthetic"}

    monkeypatch.setattr(runner, "config_at", lambda _root: config)
    monkeypatch.setattr(runner, "identity_at", lambda _root: identity)
    monkeypatch.setattr(runner, "validate_inputs", lambda _root: {"identity": identity})
    monkeypatch.setattr(runner, "host_runtime", lambda _device: runtime)
    monkeypatch.setattr(runner, "read_json", lambda _path: {"status": "goal052_canary_valid", "identity": identity, "runtime": runtime, "block": 7, "fold": 2, "target": "target"})
    monkeypatch.setattr(runner, "SeawfbStore", lambda _root: store)
    monkeypatch.setattr(runner, "auxiliary_data", lambda *_args: auxiliary)
    monkeypatch.setattr(runner, "target_data", lambda _store, _target, _fold, _fraction, q: (q_calls.append(q) or target_data))
    monkeypatch.setattr(runner.baseline, "_config", lambda _root: {})
    monkeypatch.setattr(runner.baseline, "_load_q", lambda *_args: (q_model, q_receipt))
    monkeypatch.setattr(runner.baseline, "_peak_rss_bytes", lambda: 123456)

    def fake_pretraining(spec, discovery, stopping, replay, heads, *, seed, **options):
        pre_calls.append((discovery, stopping, replay, tuple(heads), seed, options))
        return state, {"selected_epoch": 1, "state_finite": True, "runtime_seconds": 0.25}

    def fake_target(spec, discovery, stopping, replay, held_x, *, seed, transferred_state, freeze_trunk, **options):
        target_calls.append((discovery, stopping, replay, len(held_x), seed, transferred_state, freeze_trunk, options))
        scores = np.full(len(held_x), 0.5, dtype=np.float64)
        return scores, {"selected_epoch": 1, "state_finite": True, "runtime_seconds": 0.2}

    monkeypatch.setattr(runner, "fit_pretraining_lifecycle", fake_pretraining)
    monkeypatch.setattr(runner, "fit_target_lifecycle", fake_target)
    return config, identity, auxiliary, target_data, state, q_model, q_receipt, runtime, pre_calls, target_calls, q_calls


def test_profile_runs_full_rows_once_and_writes_metric_free_bound(tmp_path, monkeypatch):
    config, identity, auxiliary, target_data, state, q_model, q_receipt, runtime, pre_calls, target_calls, q_calls = _patched_profile(monkeypatch, tmp_path)
    result = profile(tmp_path, "cpu")

    assert result["status"] == "goal052_full_epoch_profile_valid"
    assert result["identity"] == identity
    assert result["runtime"] == runtime
    assert result["block"] == 7 and result["fold"] == 2 and result["target"] == "target"
    assert result["full_auxiliary_rows"] == {"discovery": 24, "stopping": 16, "replay": 28}
    assert result["target_rows"] == {"discovery": 13, "stopping": 11, "replay": 17}
    assert result["held_prediction_rows"] == 1024
    assert result["processed_rows_total"] == (24 + 16 + 28) + 4 * (13 + 11 + 17)
    assert result["epoch_count"] == 1
    assert result["selected_epochs"] == {"pretraining": 1, **{arm: 1 for arm in runner.ARMS}}
    assert result["ecological_metrics_computed"] is False
    assert result["outer_response_rows_read"] == 0
    assert result["q_model_sha256"] == q_receipt["model_sha256"]
    assert result["pretraining_rows_per_second"] > 0
    assert result["peak_rss_bytes"] == 123456
    assert (tmp_path / PROFILE_PATH).is_file()
    assert json.loads((tmp_path / PROFILE_PATH).read_text()) == result

    # No canary row cap was applied to any of the three full auxiliary roles.
    assert pre_calls[0][0] is auxiliary.discovery
    assert pre_calls[0][1] is auxiliary.stopping
    assert pre_calls[0][2] is auxiliary.replay
    assert len(target_calls) == 4
    assert all(call[3] == 1024 for call in target_calls)
    assert [call[6] for call in target_calls] == [False, False, True, False]
    assert target_calls[0][5] is None and target_calls[1][5] is None
    assert target_calls[2][5] is state and target_calls[3][5] is state
    assert q_calls == [None, q_model, None, None]


@pytest.mark.parametrize("field", ["identity", "runtime", "status"])
def test_profile_rejects_current_host_canary_binding_drift(tmp_path, monkeypatch, field):
    _patched_profile(monkeypatch, tmp_path)
    if field == "identity":
        monkeypatch.setattr(runner, "read_json", lambda _path: {"status": "goal052_canary_valid", "identity": {"wrong": True}, "runtime": {"device": "cpu", "host": "synthetic"}, "block": 7, "fold": 2, "target": "target"})
    elif field == "runtime":
        monkeypatch.setattr(runner, "read_json", lambda _path: {"status": "goal052_canary_valid", "identity": _identity(), "runtime": {"device": "cuda", "host": "other"}, "block": 7, "fold": 2, "target": "target"})
    else:
        monkeypatch.setattr(runner, "read_json", lambda _path: {"status": "incomplete", "identity": _identity(), "runtime": {"device": "cpu", "host": "synthetic"}, "block": 7, "fold": 2, "target": "target"})
    with pytest.raises(SeawfbModelingError):
        profile(tmp_path, "cpu")
