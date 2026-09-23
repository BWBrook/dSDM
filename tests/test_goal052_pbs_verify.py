from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import goal052_pbs_verify as verify  # noqa: E402


IDENTITY = {"source_sha256": "s" * 64, "goal051_identity": {"source_sha256": "g" * 64}}
REFERENCE_RUNTIME = {
    "host": "n234.kunanyi", "system": "Linux", "machine": "x86_64",
    "torch": "2.13.0+cu130", "device": "cpu", "device_name": "x86_64",
}
CURRENT_RUNTIME = dict(REFERENCE_RUNTIME, host="n235.kunanyi")
ARMS = (
    "target_only_random_init_resmlp", "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk", "multihead_full_finetune",
)


def _write(path: Path, value) -> str:
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fit(runtime: float) -> dict:
    return {
        "runtime_seconds": runtime,
        "final_shared_digest": "shared",
        "initial_shared_digest": "shared",
        "transfer_digest": "shared",
        "initial_head_digest": "head",
        "initial_model_digest": "model",
    }


def _result(pid: int, runtime: float, rss: int) -> dict:
    return {
        "pid": pid,
        "runtime_seconds": runtime,
        "memory_after_full_data_bytes": rss - 1,
        "peak_rss_bytes": rss,
        "peak_cuda_allocated_bytes": None,
        "pretraining_fit": _fit(runtime),
        "repeat_pretraining_digest": "shared",
        "target_fits": {arm: _fit(runtime) for arm in ARMS},
        "prediction_digests": {arm: arm for arm in ARMS},
        "q_model_sha256": "q" * 64,
        "bounded_pretraining_rows": {"discovery": 2, "stopping": 2, "replay": 2},
    }


def _canary(runtime: dict, *, reference_sha: str, driver_sha: str, base_pid: int) -> dict:
    results = [_result(base_pid + index % 28, 1.0 + index, 1000 + index) for index in range(56)]
    return {
        "status": "goal052_canary_valid",
        "identity": IDENTITY,
        "runtime": runtime,
        "qualified_workers": 28,
        "scope": "full_auxiliary_memory_bounded_one_epoch_optimization",
        "architecture": "seawfb_scale",
        "block": 8,
        "fold": 2,
        "target": "target",
        "results": results,
        "jobs_per_worker": {str(base_pid + index): 2 for index in range(28)},
        "synchronized_waves": 2,
        "all_nonruntime_fields_match_prior": True,
        "comparison_excluded_runtime_fields": sorted(verify.CANARY_RUNTIME_FIELDS),
        "prior_canary_sha256": reference_sha,
        "driver_sha256": {"scripts/driver.py": driver_sha},
        "peak_worker_rss_bytes": max(result["peak_rss_bytes"] for result in results),
        "ecological_metrics_computed": False,
        "outer_response_rows_read": 0,
        "production_authorized": False,
    }


def _profile(runtime: dict, runtime_offset: float) -> dict:
    return {
        "status": "goal052_full_epoch_profile_valid",
        "identity": IDENTITY,
        "runtime": runtime,
        "device": "cpu",
        "block": 8,
        "fold": 2,
        "target": "target",
        "architecture": "seawfb_scale",
        "auxiliary": "full",
        "pretraining_seed": 1,
        "target_seed": 2,
        "pretraining_fit": _fit(10 + runtime_offset),
        "target_fits": {arm: _fit(1 + runtime_offset) for arm in ARMS},
        "transferred_state_digests": {
            ARMS[0]: None, ARMS[1]: None, ARMS[2]: "shared", ARMS[3]: "shared",
        },
        "prediction_digests": {arm: arm for arm in ARMS},
        "full_auxiliary_rows": {"discovery": 10, "stopping": 5, "replay": 12},
        "pretraining_runtime_seconds": 10 + runtime_offset,
        "pretraining_rows_per_second": 2 + runtime_offset,
        "target_runtime_seconds": {arm: 1 + runtime_offset for arm in ARMS},
        "lifecycle_runtime_seconds": 15 + runtime_offset,
        "rows_per_second": 3 + runtime_offset,
        "peak_rss_bytes": 2000 + int(runtime_offset),
        "peak_cuda_allocated_bytes": None,
        "ecological_metrics_computed": False,
        "outer_response_rows_read": 0,
    }


def _fixture(tmp_path: Path, monkeypatch):
    root = tmp_path / "root"
    reference = tmp_path / "reference"
    output = tmp_path / "output"
    (root / "scripts").mkdir(parents=True)
    reference.mkdir()
    output.mkdir()
    driver_sha = _write(root / "scripts" / "driver.py", "driver\n")
    reference_canary = _canary(REFERENCE_RUNTIME, reference_sha="d" * 64,
                                driver_sha=driver_sha, base_pid=100)
    reference_canary_sha = _write(reference / "canary.json", reference_canary)
    current_canary = _canary(CURRENT_RUNTIME, reference_sha=reference_canary_sha,
                              driver_sha=driver_sha, base_pid=200)
    _write(output / "canary.json", current_canary)
    reference_profile = _profile(REFERENCE_RUNTIME, 0.0)
    current_profile = _profile(CURRENT_RUNTIME, 5.0)
    reference_profile_sha = _write(reference / "full-epoch-profile.json", reference_profile)
    _write(output / "full-epoch-profile.json", current_profile)
    _write(reference / "qualification-reference-review.json", {
        "status": "goal052_kunanyi_pilot_qualification_accepted",
        "identity": IDENTITY,
        "canary_sha256": reference_canary_sha,
        "profile_sha256": reference_profile_sha,
        "qualified_workers": 28,
    })
    samples = [
        {
            "unix_time": 1.0,
            "parent_pid": 99,
            "rss_bytes": 5000,
            "cpu_percent": 100.0,
            "cpu_measurement": "interval_live_processes",
            "pids": list(range(200, 228)),
        }
    ]
    (output / "resource-samples.jsonl").write_text(
        "".join(json.dumps(sample) + "\n" for sample in samples), encoding="utf-8"
    )
    monkeypatch.setattr(verify.native, "validate_inputs", lambda _root: {"identity": IDENTITY})
    monkeypatch.setattr(verify.native, "host_runtime", lambda _device: CURRENT_RUNTIME)
    monkeypatch.setattr(verify.native, "config_at", lambda _root: {
        "architectures": {"constants": {"max_epochs": 30, "patience": 5}}
    })
    monkeypatch.setattr(verify, "_verify_canary_result", lambda *_args: None)
    monkeypatch.setattr(verify, "_verify_profile_fits", lambda *_args: None)
    return root, reference, output


def test_verify_host_accepts_only_runtime_differences_and_writes_adapter_receipts(tmp_path, monkeypatch):
    root, reference, output = _fixture(tmp_path, monkeypatch)
    qualification, profile = verify.verify_host(root, reference, output)
    assert qualification["status"] == "goal052_pbs_node_qualification_verified"
    assert qualification["qualified_workers"] == 28
    assert qualification["runtime"] == CURRENT_RUNTIME
    assert qualification["resource_samples"]["all_canary_workers_observed"] is True
    assert profile["status"] == "goal052_full_profile_independently_verified"
    assert profile["profile"]["allowed_runtime_differences"]["runtime"] == ["host"]
    assert json.loads((output / "qualification-review.json").read_text()) == qualification
    assert json.loads((output / "profile-review.json").read_text()) == profile


def test_scientific_profile_drift_fails_closed(tmp_path, monkeypatch):
    root, reference, output = _fixture(tmp_path, monkeypatch)
    profile_path = output / "full-epoch-profile.json"
    profile = json.loads(profile_path.read_text())
    profile["full_auxiliary_rows"]["discovery"] += 1
    _write(profile_path, profile)
    with pytest.raises(ValueError, match="profile_cross_host_scientific_drift"):
        verify.verify_host(root, reference, output)
    assert not (output / "qualification-review.json").exists()


def test_runtime_environment_drift_and_empty_samples_fail_closed(tmp_path, monkeypatch):
    root, reference, output = _fixture(tmp_path, monkeypatch)
    reference_canary_path = reference / "canary.json"
    reference_canary = json.loads(reference_canary_path.read_text())
    reference_canary["runtime"]["torch"] = "different"
    new_sha = _write(reference_canary_path, reference_canary)
    current_canary_path = output / "canary.json"
    current_canary = json.loads(current_canary_path.read_text())
    current_canary["prior_canary_sha256"] = new_sha
    _write(current_canary_path, current_canary)
    reference_review_path = reference / "qualification-reference-review.json"
    review = json.loads(reference_review_path.read_text())
    review["canary_sha256"] = new_sha
    _write(reference_review_path, review)
    with pytest.raises(ValueError, match="canary_runtime_environment_drift"):
        verify.verify_host(root, reference, output)

    root, reference, output = _fixture(tmp_path / "empty", monkeypatch)
    (output / "resource-samples.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="resource_samples_empty"):
        verify.verify_host(root, reference, output)


def test_resource_samples_require_every_canary_worker_and_bounded_rss(tmp_path, monkeypatch):
    root, reference, output = _fixture(tmp_path, monkeypatch)
    sample_path = output / "resource-samples.jsonl"
    sample = json.loads(sample_path.read_text())
    sample["pids"] = sample["pids"][:-1]
    sample_path.write_text(json.dumps(sample) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="resource_samples_missing_canary_workers"):
        verify.verify_host(root, reference, output)

    root, reference, output = _fixture(tmp_path / "rss", monkeypatch)
    sample_path = output / "resource-samples.jsonl"
    sample = json.loads(sample_path.read_text())
    sample["rss_bytes"] = verify.MAX_SAMPLED_RSS_BYTES
    sample_path.write_text(json.dumps(sample) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="resource_sample_rss_invalid"):
        verify.verify_host(root, reference, output)
