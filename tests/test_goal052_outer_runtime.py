from __future__ import annotations

import json
from pathlib import Path

import pytest

from dsdm_phase1 import goal052_outer_runtime as runtime


def test_runtime_fingerprint_excludes_dynamic_resource_probe(monkeypatch):
    monkeypatch.setattr(runtime, "_available_resources", lambda: {"available_cpus": 10, "available_ram_bytes": 100})
    first = runtime._runtime_context("cpu")
    monkeypatch.setattr(runtime, "_available_resources", lambda: {"available_cpus": 10, "available_ram_bytes": 200})
    second = runtime._runtime_context("cpu")
    assert first["runtime_fingerprint"] == second["runtime_fingerprint"]
    assert first["resources"] != second["resources"]
    assert first["runtime"]["torch_cpu_threads"] == 1
    assert first["runtime"]["torch_deterministic_algorithms"] is True


def test_synthetic_canary_repeats_are_exact_and_cover_native_paths():
    repeats = runtime._run_canary_repetitions(Path("."), "cpu", 2)
    assert len(repeats) == 2
    assert len({repeat["pid"] for repeat in repeats}) == 2
    assert repeats[0]["targets"] == repeats[1]["targets"]
    assert repeats[0]["q"] == repeats[1]["q"]
    assert runtime._strip_dynamic(repeats[0]) == runtime._strip_dynamic(repeats[1])
    assert set(repeats[0]["targets"]) == {
        "target_only_random_init_resmlp",
        "target_plus_q_linear_resmlp",
        "multihead_frozen_trunk",
        "multihead_full_finetune",
    }
    assert set(repeats[0]["conventional"]) == {"rf02", "hgb04", "ann02"}
    assert repeats[0]["feature_widths"] == {"base": 103, "q": 104}


def test_final_qualification_binds_stage_files_plan_host_and_workers(tmp_path, monkeypatch):
    plan = {"plan_digest": "p" * 64, "sources": {"source.py": "s" * 64}}
    context = {
        "host": {"hostname": "actual-host", "system": "TestOS", "machine": "arm64"},
        "runtime": {"python": "3.12", "torch": "2", "torch_cpu_threads": 1, "torch_deterministic_algorithms": True},
        "device": "cpu",
        "resources": {"available_cpus": 4, "available_ram_bytes": 1000},
        "runtime_fingerprint": "r" * 64,
    }
    monkeypatch.setattr(runtime, "load_plan", lambda root, run: plan)
    monkeypatch.setattr(runtime, "source_hashes", lambda root: dict(plan["sources"]))
    monkeypatch.setattr(runtime, "_runtime_context", lambda device: context)
    monkeypatch.setattr(runtime, "_available_resources", lambda: {"available_cpus": 4, "available_ram_bytes": 1000})
    run = tmp_path / "run"
    paths = runtime._receipt_paths(run, context)
    canary = {
        "schema_version": runtime.SCHEMA_VERSION,
        "status": runtime.CANARY_STATUS,
        "plan_digest": plan["plan_digest"],
        "runtime_fingerprint": context["runtime_fingerprint"],
        "code_hashes": plan["sources"],
        "workers_tested": 2,
    }
    profile = {
        "schema_version": runtime.SCHEMA_VERSION,
        "status": runtime.PROFILE_STATUS,
        "plan_digest": plan["plan_digest"],
        "runtime_fingerprint": context["runtime_fingerprint"],
        "code_hashes": plan["sources"],
        "qualified_workers": 2,
        "peak_rss_bytes": 100,
    }
    runtime.write_once(paths["canary"], canary)
    runtime.write_once(paths["profile"], profile)
    relative = runtime._maybe_finalize(tmp_path, run, plan, context)
    assert relative == str(paths["final"].relative_to(run))
    final = json.loads(paths["final"].read_text())
    assert final["status"] == runtime.QUALIFIED_STATUS
    assert final["files"] == {final["canary"]: final["canary_sha256"], final["profile"]: final["profile_sha256"]}
    assert runtime.require_qualification(tmp_path, run, plan, "cpu", 2) == relative
    with pytest.raises(ValueError, match="workers_exceed"):
        runtime.require_qualification(tmp_path, run, plan, "cpu", 3)


def test_require_qualification_rejects_stage_hash_tampering(tmp_path, monkeypatch):
    plan = {"plan_digest": "p" * 64, "sources": {"source.py": "s" * 64}}
    context = {"host": {"hostname": "host"}, "runtime": {"torch_cpu_threads": 1}, "device": "cpu", "resources": {}, "runtime_fingerprint": "r" * 64}
    monkeypatch.setattr(runtime, "source_hashes", lambda root: dict(plan["sources"]))
    monkeypatch.setattr(runtime, "_runtime_context", lambda device: context)
    run = tmp_path / "run"
    paths = runtime._receipt_paths(run, context)
    for path, status in ((paths["canary"], runtime.CANARY_STATUS), (paths["profile"], runtime.PROFILE_STATUS)):
        runtime.write_once(path, {"schema_version": runtime.SCHEMA_VERSION, "status": status, "plan_digest": plan["plan_digest"], "runtime_fingerprint": context["runtime_fingerprint"], "code_hashes": plan["sources"], "qualified_workers": 1, "workers_tested": 1, "peak_rss_bytes": 100})
    runtime._maybe_finalize(tmp_path, run, plan, context)
    paths["canary"].write_text(paths["canary"].read_text() + "tamper")
    final = json.loads(paths["final"].read_text())
    with pytest.raises(ValueError, match="canary_hash_mismatch"):
        runtime.require_qualification(tmp_path, run, plan, "cpu", 1)


def test_conventional_profile_selector_covers_all_selected_families():
    plan = {
        "target_rows": {"small": {"rows": 10}, "large": {"rows": 20}},
        "tasks": [
            {"kind": "conventional", "family": "random_forest", "candidate_id": "rf00", "target": "small"},
            {"kind": "conventional", "family": "random_forest", "candidate_id": "rf02", "target": "large"},
            {"kind": "conventional", "family": "hist_gradient_boosting", "candidate_id": "hgb00", "target": "small"},
            {"kind": "conventional", "family": "hist_gradient_boosting", "candidate_id": "hgb04", "target": "large"},
            {"kind": "conventional", "family": "shallow_ann", "candidate_id": "ann00", "target": "small"},
            {"kind": "conventional", "family": "shallow_ann", "candidate_id": "ann04", "target": "large"},
        ],
    }
    selected = runtime._conventional_profile_choices(plan)
    assert {item["family"] for item in selected} == {"random_forest", "hist_gradient_boosting", "shallow_ann"}
    assert {item["candidate_id"] for item in selected} == {"rf00", "hgb04", "ann04"}
    assert all(item["target"] == "large" for item in selected if item["candidate_id"] != "rf00")


def test_require_qualification_rechecks_current_capacity(tmp_path, monkeypatch):
    plan = {"plan_digest": "p" * 64, "sources": {"source.py": "s" * 64}}
    context = {"host": {"hostname": "host"}, "runtime": {"torch_cpu_threads": 1}, "device": "cpu", "resources": {}, "runtime_fingerprint": "r" * 64}
    monkeypatch.setattr(runtime, "source_hashes", lambda root: dict(plan["sources"]))
    monkeypatch.setattr(runtime, "_runtime_context", lambda device: context)
    monkeypatch.setattr(runtime, "_available_resources", lambda: {"available_cpus": 4, "available_ram_bytes": 1000})
    run = tmp_path / "run"
    paths = runtime._receipt_paths(run, context)
    runtime.write_once(paths["canary"], {"schema_version": runtime.SCHEMA_VERSION, "status": runtime.CANARY_STATUS, "plan_digest": plan["plan_digest"], "runtime_fingerprint": context["runtime_fingerprint"], "code_hashes": plan["sources"], "workers_tested": 2})
    runtime.write_once(paths["profile"], {"schema_version": runtime.SCHEMA_VERSION, "status": runtime.PROFILE_STATUS, "plan_digest": plan["plan_digest"], "runtime_fingerprint": context["runtime_fingerprint"], "code_hashes": plan["sources"], "qualified_workers": 2, "peak_rss_bytes": 100})
    runtime._maybe_finalize(tmp_path, run, plan, context)
    assert runtime.require_qualification(tmp_path, run, plan, "cpu", 1)
    monkeypatch.setattr(runtime, "_available_resources", lambda: {"available_cpus": 4, "available_ram_bytes": 100})
    with pytest.raises(ValueError, match="capacity_insufficient"):
        runtime.require_qualification(tmp_path, run, plan, "cpu", 1)
