from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dsdm_phase1 import goal050_compute_canary as canary


def _valid_run(**overrides):
    receipt = {
        "schema_version": "goal050-compute-canary-run-v1", "status": "complete", "host_class": "mac_cpu", "hostname": "mac", "device": "cpu", "python": "3.12.0", "numpy": "2.5.1", "pytorch": "2.13.0", "cuda": None, "cuda_driver": None,
        "rows": 90000, "heads": 167, "predictor_width": 103, "epochs": 2, "batch_size": 128, "threads": 1, "seed": 5050394, "repeat": 1,
        "bundle_sha256": "a" * 64, "bundle_metadata_sha256": "b" * 64, "canary_source_sha256": "c" * 64, "config_sha256": "d" * 64, "uv_lock_sha256": "e" * 64,
        "multi_fit_seconds": 2.0, "single_fit_seconds": 1.0, "fit_seconds": 3.0, "multi_epoch_seconds": [1.0, 1.0], "single_epoch_seconds": [0.5, 0.5], "multi_rows_per_second": 45000.0, "multi_row_head_per_second": 7515000.0, "single_known_rows": 100, "single_rows_per_second": 200.0, "peak_rss_bytes": 1000000, "gpu_peak_allocated_bytes": 0, "gpu_peak_reserved_bytes": 0,
        "finite": True, "deterministic": True, "multi_state_digest": "f" * 64, "multi_probe_digest": "g" * 64, "single_state_digest": "h" * 64, "single_probe_digest": "i" * 64, "ecological_metrics": 0, "exit_status": 0, "process_seconds": 4.0,
    }
    receipt.update(overrides)
    return receipt


def _valid_aggregate(**overrides):
    receipt = {"schema_version": "goal050-compute-canary-aggregate-v1", "status": "complete", "batch_id": "mac_cpu-concurrency3", "host_class": "mac_cpu", "device": "cpu", "requested_jobs": 3, "successful_jobs": 3, "batch_wall_seconds": 2.0, "jobs_per_second": 1.5, "row_head_epoch_per_second": 45090000.0, "peak_rss_bytes": 1000000, "gpu_peak_allocated_bytes": 0, "gpu_peak_reserved_bytes": 0, "bundle_sha256": "a" * 64, "bundle_metadata_sha256": "b" * 64, "canary_source_sha256": "c" * 64, "config_sha256": "d" * 64, "uv_lock_sha256": "e" * 64, "finite": True, "deterministic": True, "ecological_metrics": 0, "exit_status": 0}
    receipt.update(overrides)
    return receipt


def test_strict_block_exclusion_changes_background_support_without_identifier_output():
    cells = ["a", "b", "c"]
    memberships = pd.DataFrame({"species": ["held-a", "head-a"], "cell_id": ["a", "b"]})
    y, mask, adjusted = canary.deidentified_responses(cells, [10, 10, 2], memberships, [0, 1, 2], ["held-a"], ["head-a", "head-b"])
    assert adjusted.tolist() == [9, 10, 2]
    assert y.dtype == np.uint8 and mask.dtype == np.uint8
    assert y.shape == mask.shape == (3, 2)
    assert mask[0, 0] == 0
    assert mask[1, 0] == 1 and y[1, 0] == 1


def test_one_hot_encoding_has_frozen_width_and_missing_unseen_levels():
    frame = pd.DataFrame({**{name: [1.0, np.nan] for name in canary.CONTINUOUS}, **{name: ["known", None] for name in canary.CATEGORICAL}})
    transform = {"continuous": {name: {"mean": 1.0, "population_sd": 1.0} for name in canary.CONTINUOUS}, "categorical": {name: ["__MISSING__", "__UNSEEN__", "known"] for name in canary.CATEGORICAL}}
    encoded = canary._encode_predictors(frame, transform)
    assert encoded.dtype == np.float32
    assert encoded.shape == (2, 30)
    assert np.isfinite(encoded).all()
    assert np.array_equal(encoded[1, 21:24], [1, 0, 0])


def test_deterministic_bundle_bytes_and_loader_rejects_extra_members():
    arrays = {"X": np.ones((3, 4), dtype=np.float32), "Y": np.array([[1], [0], [0]], dtype=np.uint8), "response_mask": np.ones((3, 1), dtype=np.uint8)}
    metadata = {"schema_version": "goal050-canary-bundle-v1", "rows": 3, "heads": 1, "predictor_width": 4}
    first = canary._deterministic_npz(arrays, metadata)
    second = canary._deterministic_npz(arrays, metadata)
    assert first == second
    path = Path("/tmp/goal050-test-bundle.npz")
    path.write_bytes(first)
    x, y, mask, loaded = canary._load_bundle(path)
    assert x.shape == (3, 4) and y.shape == mask.shape == (3, 1)
    assert loaded == metadata
    path.unlink()


def test_bridge_control_model_dimensions_and_receipt_metric_contract():
    model = canary._model(30, 167, True)
    state = model.state_dict()
    assert tuple(state["stem.weight"].shape) == (128, 30)
    assert tuple(state["head.weight"].shape) == (167, 128)
    assert sum(1 for name in state if name.endswith("down.weight")) == 3
    fake = _valid_run()
    canary._validate_run(fake)
    assert "loss" not in json.dumps(fake).lower()


def test_route_selection_requires_all_evidence_and_compares_latency_with_capacity():
    single = {"mac_cpu": 1.0, "deep_server_cpu": 10.0, "alien_gpu": 20.0}
    aggregate = {
        "mac_cpu-concurrency3": _valid_aggregate(row_head_epoch_per_second=100.0),
        "deep_server_cpu-concurrency16": _valid_aggregate(batch_id="deep_server_cpu-concurrency16", host_class="deep_server_cpu", requested_jobs=16, successful_jobs=16, batch_wall_seconds=2.0, jobs_per_second=8.0, row_head_epoch_per_second=16 * 90000 * 167 * 2 / 2),
        "deep_server_cpu-concurrency32": _valid_aggregate(batch_id="deep_server_cpu-concurrency32", host_class="deep_server_cpu", requested_jobs=32, successful_jobs=32, batch_wall_seconds=2.0, jobs_per_second=16.0, row_head_epoch_per_second=32 * 90000 * 167 * 2 / 2),
    }
    route, comparison = canary._select_route(single, aggregate)
    assert route == "deep_server_cpu"
    assert comparison["single_latency_winner"] == "mac_cpu"
    assert comparison["aggregate_capacity_winner"] == "deep_server_cpu"
    assert canary._select_route(single, {})[0] is None


def test_aggregate_gate_rejects_incomplete_jobs():
    with pytest.raises(canary.CanaryError, match="aggregate_batch_contract"):
        canary._validate_aggregate(_valid_aggregate(successful_jobs=2))


def test_aggregate_gate_rejects_provenance_drift_against_expected_binding():
    receipt = _valid_aggregate()
    expected = {"canary_source_sha256": "f" * 64, "config_sha256": "d" * 64, "uv_lock_sha256": "e" * 64}
    with pytest.raises(canary.CanaryError, match="aggregate_provenance_drift"):
        canary._validate_aggregate(receipt, None, expected)


def test_run_gate_rejects_wrong_dimensions_device_and_seed():
    for overrides, message in (({"rows": 89999}, "run_rows_drift"), ({"device": "cuda:0"}, "run_host_device"), ({"seed": 1}, "run_seed_drift")):
        with pytest.raises(canary.CanaryError, match=message):
            canary._validate_run(_valid_run(**overrides))


def test_run_gate_rejects_extra_outcome_or_identifier_fields():
    with pytest.raises(canary.CanaryError, match="run_schema_drift"):
        canary._validate_run(_valid_run(loss=0.1))
    with pytest.raises(canary.CanaryError, match="run_schema_drift"):
        canary._validate_run(_valid_run(cell_ids=["hidden"]))


def test_aggregate_gate_rejects_wrong_batch_contract_and_forged_throughput():
    with pytest.raises(canary.CanaryError, match="aggregate_batch_contract"):
        canary._validate_aggregate(_valid_aggregate(batch_id="deep_server_cpu-concurrency16"))
    with pytest.raises(canary.CanaryError, match="aggregate_row_head_epoch_per_second_forged"):
        canary._validate_aggregate(_valid_aggregate(row_head_epoch_per_second=1.0))
