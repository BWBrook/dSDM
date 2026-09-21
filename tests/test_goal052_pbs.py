from __future__ import annotations

from concurrent.futures import Future
import hashlib
import json
from pathlib import Path
import platform
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import goal052_pbs as pbs  # noqa: E402


IDENTITY = {"source_sha256": "s" * 64, "goal051_identity": {"id": "goal051"}}
COORDINATOR = {"status": "goal052_pbs_handoff_verified", "identity": IDENTITY,
               "selection_digest": None, "prior_scheduler_stopped": True,
               "imported_checkpoint_inventory_sha256": "1" * 64}
RUNTIME = {"host": platform.node(), "system": "Linux", "machine": "x86_64",
           "torch": "test", "device": "cpu", "device_name": "test-cpu"}


def _write_receipt(tmp_path: Path, name: str, value: dict) -> dict[str, str]:
    path = tmp_path / name
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _qualification(identity=IDENTITY):
    return {"status": "goal052_pbs_node_qualification_verified", "qualified_workers": 2,
            "runtime": RUNTIME, "identity": identity,
            "profile_sha256": "p" * 64}


def _profile(identity=IDENTITY):
    return {"status": "goal052_full_profile_independently_verified", "identity": identity,
            "profile_sha256": "p" * 64, "runtime": RUNTIME}


def _root(monkeypatch, tmp_path, tasks=None):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "goal052_seawfb_dsdm.json").write_text("{}\n")
    (tmp_path / "uv.lock").write_text("lock\n")
    selection = {"selected_architecture": "seawfb_scale", "identity": IDENTITY}
    private = tmp_path / "private"
    private.mkdir()
    selection_path = private / "selection.json"
    selection_path.write_text(json.dumps(selection, sort_keys=True) + "\n")
    monkeypatch.setattr(pbs.native, "CONFIG", Path("config/goal052_seawfb_dsdm.json"))
    monkeypatch.setattr(pbs.native, "identity_at", lambda _root: IDENTITY)
    monkeypatch.setattr(pbs.native, "validate_inputs", lambda _root: {"identity": IDENTITY})
    monkeypatch.setattr(pbs.native, "host_runtime", lambda _device: RUNTIME)
    monkeypatch.setattr(pbs.native, "config_at", lambda _root: {"execution": {"private_root": "private"}})
    monkeypatch.setattr(pbs.native, "private_root", lambda root, _config: root / "private")
    monkeypatch.setattr(pbs, "_native_tasks", lambda _root, _stage, _arch: [list(t) for t in tasks or [
        ("pretrain", 0, 0, "20", "seawfb_scale", "seed01"),
        ("pretrain", 0, 1, "20", "seawfb_scale", "seed01"),
        ("pretrain", 0, 2, "20", "seawfb_scale", "seed01"),
        ("pretrain", 0, 3, "20", "seawfb_scale", "seed01"),
    ]])
    monkeypatch.setattr(pbs, "_full_pretraining_inventory", lambda *_args: [])
    return selection_path


def _plan(monkeypatch, tmp_path, tasks=None, nodes=("node-a", "node-b")):
    selection_path = _root(monkeypatch, tmp_path, tasks)
    selection = json.loads(selection_path.read_text())
    coordinator = dict(COORDINATOR)
    coordinator["selection_digest"] = pbs._digest(selection)
    coordinator_ref = _write_receipt(tmp_path, "coordinator.json", coordinator)
    return pbs.plan_stage(tmp_path, "remaining_pretraining", nodes, 2,
                          selection_path=selection_path, coordinator_reference=coordinator_ref), coordinator_ref


def test_native_inventory_is_disjoint_and_key_normalized(monkeypatch, tmp_path):
    manifest, _ = _plan(monkeypatch, tmp_path)
    inventory = [item["task_id"] for item in manifest["native_task_inventory"]]
    shards = [key for shard in manifest["shards"] for key in shard["task_ids"]]
    assert set(shards) == set(inventory)
    assert len(inventory) == len(set(inventory)) == 4
    first = manifest["native_task_inventory"][0]
    assert pbs.task_id(IDENTITY, tuple(first["task"])) == first["task_id"]
    assert pbs.manifest_digest(manifest) == manifest["manifest_digest"]


def test_missing_or_drifted_coordinator_fails_closed(monkeypatch, tmp_path):
    selection_path = _root(monkeypatch, tmp_path)
    bad = _write_receipt(tmp_path, "coordinator.json", {"status": "wrong"})
    with pytest.raises(ValueError, match="coordinator_status_invalid"):
        pbs.plan_stage(tmp_path, "remaining_pretraining", ("node-a",), 2,
                       selection_path=selection_path, coordinator_reference=bad)


def test_forged_embedded_receipt_is_rejected(monkeypatch, tmp_path):
    selection_path = _root(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="reference_required"):
        pbs.plan_stage(tmp_path, "remaining_pretraining", ("node-a",), 2,
                       selection_path=selection_path,
                       coordinator_reference={"path": "x", "sha256": "d" * 64,
                                              "receipt": {"status": "goal052_pbs_handoff_verified"}})


def test_source_qualification_and_profile_drift_fail_closed(monkeypatch, tmp_path):
    manifest, _ = _plan(monkeypatch, tmp_path, nodes=("node-a",))
    qual_ref = _write_receipt(tmp_path, "qualification.json", _qualification())
    profile_ref = _write_receipt(tmp_path, "profile.json", _profile())
    monkeypatch.setattr(pbs.native, "identity_at", lambda _root: {"drift": True})
    with pytest.raises(ValueError, match="source_identity_drift"):
        pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                           job_id="job", ownership_root=tmp_path / "state",
                           expected_manifest_digest=manifest["manifest_digest"])


def test_selection_drift_and_runtime_drift_fail_closed(monkeypatch, tmp_path):
    manifest, _ = _plan(monkeypatch, tmp_path, nodes=("node-a",))
    selection_path = tmp_path / "private" / "selection.json"
    selection_path.write_text(json.dumps({"selected_architecture": "bridge_control", "identity": IDENTITY}) + "\n")
    qual_ref = _write_receipt(tmp_path, "qualification.json", _qualification())
    profile_ref = _write_receipt(tmp_path, "profile.json", _profile())
    with pytest.raises(ValueError, match="selection_drift"):
        pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                           job_id="job", ownership_root=tmp_path / "state",
                           expected_manifest_digest=manifest["manifest_digest"])
    selection_path.write_text(json.dumps({"selected_architecture": "seawfb_scale", "identity": IDENTITY}) + "\n")
    changed = dict(RUNTIME, torch="different")
    qual_ref = _write_receipt(tmp_path, "qualification-changed.json", {**_qualification(), "runtime": changed})
    with pytest.raises(ValueError, match="qualification_runtime_drift"):
        pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                           job_id="job", ownership_root=tmp_path / "state",
                           expected_manifest_digest=manifest["manifest_digest"])


def test_partition_mutation_fails_closed(monkeypatch, tmp_path):
    manifest, _ = _plan(monkeypatch, tmp_path, nodes=("node-a",))
    manifest["shards"][0]["task_ids"] = []
    manifest["manifest_digest"] = pbs.manifest_digest(manifest)
    qual_ref = _write_receipt(tmp_path, "qualification.json", _qualification())
    profile_ref = _write_receipt(tmp_path, "profile.json", _profile())
    with pytest.raises(ValueError, match="shard_partition_drift"):
        pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                           job_id="job", ownership_root=tmp_path / "state",
                           expected_manifest_digest=manifest["manifest_digest"])


def test_failure_writes_no_completion_and_ownership_collides(monkeypatch, tmp_path):
    manifest, _ = _plan(monkeypatch, tmp_path, nodes=("node-a",))
    qual_ref = _write_receipt(tmp_path, "qualification.json", _qualification())
    profile_ref = _write_receipt(tmp_path, "profile.json", _profile())
    monkeypatch.setattr(pbs.native, "worker", lambda _task: (_ for _ in ()).throw(RuntimeError("fit failed")))

    class Pool:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def submit(self, function, task):
            future = Future()
            try: future.set_result(function(task))
            except BaseException as exc: future.set_exception(exc)
            return future

    monkeypatch.setattr(pbs, "ProcessPoolExecutor", Pool)
    state = tmp_path / "state"
    with pytest.raises(RuntimeError, match="fit failed"):
        pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                           job_id="job", ownership_root=state,
                           expected_manifest_digest=manifest["manifest_digest"])
    assert not (state / "remaining_pretraining" / "completions" / "rank-0000.json").exists()
    with pytest.raises(ValueError, match="ownership_collision"):
        pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                           job_id="job2", ownership_root=state,
                           expected_manifest_digest=manifest["manifest_digest"])


def test_success_and_resume_validate_native_results(monkeypatch, tmp_path):
    manifest, _ = _plan(monkeypatch, tmp_path, nodes=("node-a",))
    qual_ref = _write_receipt(tmp_path, "qualification.json", _qualification())
    profile_ref = _write_receipt(tmp_path, "profile.json", _profile())
    calls = []

    def worker(task):
        calls.append(tuple(task))
        return pbs.task_id(IDENTITY, task)

    class Pool:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def submit(self, function, task):
            future = Future()
            try: future.set_result(function(task))
            except BaseException as exc: future.set_exception(exc)
            return future

    monkeypatch.setattr(pbs.native, "worker", worker)
    monkeypatch.setattr(pbs, "ProcessPoolExecutor", Pool)
    state = tmp_path / "state"
    first = pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                               job_id="job", ownership_root=state,
                               expected_manifest_digest=manifest["manifest_digest"])
    assert first["status"] == "complete" and len(calls) == 4
    second = pbs.run_node_shard(manifest, tmp_path, "node-a", qual_ref, profile_ref,
                                job_id="job2", ownership_root=state,
                                expected_manifest_digest=manifest["manifest_digest"])
    assert second == first and len(calls) == 4


def test_final_stage_requires_full_pretraining_and_default_stage_claims_are_distinct(monkeypatch, tmp_path):
    selection_path = _root(monkeypatch, tmp_path)
    selection = json.loads(selection_path.read_text())
    coordinator = dict(COORDINATOR, selection_digest=pbs._digest(selection))
    coordinator_ref = _write_receipt(tmp_path, "coordinator.json", coordinator)
    with pytest.raises(ValueError, match="full_pretraining_reference_required"):
        pbs.plan_stage(tmp_path, "final_targets", ("node-a",), 2,
                       selection_path=selection_path, coordinator_reference=coordinator_ref)
    full = {"status": "goal052_full_pretraining_verified", "immutable": True, "identity": IDENTITY,
            "selection_digest": pbs._digest(selection), "native_inventory_digest": pbs._digest([])}
    full_ref = _write_receipt(tmp_path, "full-pretraining.json", full)
    remaining = pbs.plan_stage(tmp_path, "remaining_pretraining", ("node-a",), 2,
                               selection_path=selection_path, coordinator_reference=coordinator_ref)
    final = pbs.plan_stage(tmp_path, "final_targets", ("node-a",), 2,
                           selection_path=selection_path, coordinator_reference=coordinator_ref,
                           full_pretraining_reference=full_ref)
    qual_ref = _write_receipt(tmp_path, "qualification.json", _qualification())
    profile_ref = _write_receipt(tmp_path, "profile.json", _profile())
    monkeypatch.setattr(pbs.native, "worker", lambda task: pbs.task_id(IDENTITY, task))

    class Pool:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def submit(self, function, task):
            future = Future()
            future.set_result(function(task))
            return future

    monkeypatch.setattr(pbs, "ProcessPoolExecutor", Pool)
    pbs.run_node_shard(remaining, tmp_path, "node-a", qual_ref, profile_ref,
                       job_id="job-r", expected_manifest_digest=remaining["manifest_digest"])
    pbs.run_node_shard(final, tmp_path, "node-a", qual_ref, profile_ref,
                       job_id="job-f", expected_manifest_digest=final["manifest_digest"])
    assert (tmp_path / ".goal052-pbs" / "remaining_pretraining" / "ownership" / "rank-0000").is_dir()
    assert (tmp_path / ".goal052-pbs" / "final_targets" / "ownership" / "rank-0000").is_dir()
