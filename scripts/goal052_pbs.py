"""Offline-ready PBS sharding for the frozen Goal052 neural experiment.

This module deliberately stops at two boundaries.  Planning enumerates the
complete native Goal052 inventory and assigns immutable, disjoint node shards;
execution consumes one such shard with the native ``worker_init``/``worker``
functions.  It does not qualify a host, promote a canary, aggregate results,
or invent a coordinator authority.  A PBS wrapper can therefore perform host
qualification and pass reviewed JSON receipts here without changing the
scientific runner.

Typical use (after an independently reviewed qualification and coordinator
receipt exist)::

    manifest = plan_stage(
        root, "remaining_pretraining", nodes, 28,
        coordinator_reference={"path": "handoff.json", "sha256": "..."},
    )
    run_node_shard(manifest, root, "kunanyi-node-001", qualification, profile,
                   expected_manifest_digest=manifest["manifest_digest"])

All tasks remain in the manifest, including tasks whose native checkpoints are
already present.  Cache reuse is decided by the native runner at execution.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import re
import tempfile
from typing import Any, Mapping, Sequence

from dsdm_phase1 import goal052_seawfb_dsdm as native


SCHEMA_VERSION = "goal052-pbs-manifest-v1"
COMPLETION_SCHEMA = "goal052-pbs-rank-completion-v1"
STAGES = frozenset(("remaining_pretraining", "final_targets"))


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def canonical_task(task: Sequence[Any]) -> list[Any]:
    """Return the JSON-normalized representation of one native task tuple."""
    result = list(task)
    _require(result and result[0] in ("pretrain", "target"), "native_task_kind_invalid")
    json.dumps(result, sort_keys=True)
    return result


def task_id(identity: Mapping[str, Any], task: Sequence[Any]) -> str:
    """Stable ID of the native checkpoint key represented by ``task``."""
    task = canonical_task(task)
    if task[0] == "pretrain":
        key = native.pretraining_key(identity, *task[1:])
    else:
        key = native.leaf_key(identity, *task[1:])
    return _digest(key)


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Digest a manifest while ignoring its self-referential digest field."""
    value = dict(manifest)
    value.pop("manifest_digest", None)
    return _digest(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".json", mode="w", encoding="utf-8", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, (str, Path)):
        path = Path(value)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label}_invalid") from exc
    _require(isinstance(value, Mapping), f"{label}_invalid")
    return dict(value)


def _external_receipt(value: Any, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read only a path/SHA reference; embedded receipts are forbidden."""
    _require(isinstance(value, Mapping) and set(value) == {"path", "sha256"},
             f"{label}_reference_required")
    reference = {"path": str(value["path"]), "sha256": value["sha256"]}
    _require(reference["path"] and isinstance(reference["sha256"], str)
             and re.fullmatch(r"[0-9a-f]{64}", reference["sha256"]) is not None,
             f"{label}_reference_invalid")
    path = Path(reference["path"])
    _require(path.is_file() and _sha256_file(path) == reference["sha256"], f"{label}_reference_drift")
    return _read_json(path, label), reference


def _selection(root: Path, value: Path | None, identity: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    config = native.config_at(root)
    private_path = native.private_root(root, config) / "selection.json"
    path = Path(value) if value is not None else private_path
    _require(path.resolve() == private_path.resolve(), "selection_must_be_native_private")
    selection = _read_json(path, "selection")
    _require(isinstance(selection.get("selected_architecture"), str), "selected_architecture_missing")
    _require(selection.get("identity") == dict(identity), "selection_identity_drift")
    return selection, _digest(selection)


def _native_tasks(root: Path, stage: str, architecture: str) -> list[list[Any]]:
    store = native.SeawfbStore(root)
    blocks = sorted({int(value) for value in store.crossfit["focal_blocks"].values()})
    if stage == "remaining_pretraining":
        generated = native.remaining_pretraining_tasks(blocks, architecture)
    else:
        generated = native.final_tasks(store.primary_targets, store.focal_targets, architecture)
    return [canonical_task(task) for task in generated]


def _full_pretraining_inventory(root: Path, architecture: str) -> list[list[Any]]:
    store = native.SeawfbStore(root)
    blocks = sorted({int(value) for value in store.crossfit["focal_blocks"].values()})
    return [canonical_task(task) for task in (
        list(native.selection_pretraining_tasks(blocks))
        + list(native.remaining_pretraining_tasks(blocks, architecture))
    )]


def _validate_coordinator(reference: Any, identity: Mapping[str, Any], selection_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    value, reference = _external_receipt(reference, "coordinator")
    _require(value.get("status") == "goal052_pbs_handoff_verified", "coordinator_status_invalid")
    _require(value.get("identity") == dict(identity), "coordinator_identity_drift")
    _require(value.get("selection_digest") == selection_digest, "coordinator_selection_drift")
    _require(value.get("prior_scheduler_stopped") is True, "coordinator_scheduler_active")
    _require(re.fullmatch(r"[0-9a-f]{64}", str(value.get("imported_checkpoint_inventory_sha256"))) is not None,
             "coordinator_checkpoint_inventory_binding_missing")
    return value, reference


def _validate_full_pretraining(reference: Any, identity: Mapping[str, Any], selection_digest: str,
                               inventory_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    value, reference = _external_receipt(reference, "full_pretraining")
    _require(value.get("immutable") is True, "full_pretraining_receipt_not_immutable")
    _require(value.get("status") == "goal052_full_pretraining_verified",
             "full_pretraining_receipt_unverified")
    _require(value.get("identity") == dict(identity), "full_pretraining_identity_drift")
    _require(value.get("selection_digest") == selection_digest, "full_pretraining_selection_drift")
    receipt_inventory = value.get("native_inventory_digest", value.get("native_full_inventory_digest"))
    _require(receipt_inventory == inventory_digest, "full_pretraining_inventory_drift")
    return value, reference


def plan_stage(
    root: Path,
    stage: str,
    nodes: Sequence[str],
    workers_per_node: int,
    *,
    selection_path: Path | None = None,
    coordinator_reference: Mapping[str, Any],
    full_pretraining_reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a deterministic disjoint PBS node-shard manifest.

    ``coordinator_reference`` must identify an externally supplied JSON
    binding the preceding shutdown/import state.  This function never creates
    that authority and never promotes qualification evidence.
    """
    root = Path(root)
    _require(stage in STAGES, "pbs_stage_invalid")
    ordered_nodes = sorted(str(node) for node in nodes)
    _require(ordered_nodes and len(ordered_nodes) == len(set(ordered_nodes)), "pbs_nodes_invalid")
    _require(len(ordered_nodes) <= 48, "pbs_node_cap_exceeded")
    _require(isinstance(workers_per_node, int) and 1 <= workers_per_node <= 28, "pbs_worker_cap_exceeded")
    identity = native.identity_at(root)
    selection_value, selection_sha = _selection(root, selection_path, identity)
    architecture = selection_value["selected_architecture"]
    _coordinator, coordinator = _validate_coordinator(coordinator_reference, identity, selection_sha)
    native_inventory = _native_tasks(root, stage, architecture)
    ids = [task_id(identity, task) for task in native_inventory]
    _require(len(ids) == len(set(ids)), "native_task_inventory_duplicate")
    if stage == "final_targets":
        _require(full_pretraining_reference is not None, "full_pretraining_reference_required")
        full_inventory = _full_pretraining_inventory(root, architecture)
        full_digest = _digest([task_id(identity, task) for task in full_inventory])
        _full_pretraining, full_reference = _validate_full_pretraining(full_pretraining_reference, identity, selection_sha, full_digest)
    else:
        full_digest = None
        full_reference = None
    shards = []
    for rank, node in enumerate(ordered_nodes):
        selected = [(task, task_id(identity, task)) for index, task in enumerate(native_inventory) if index % len(ordered_nodes) == rank]
        shards.append({"rank": rank, "node": node, "task_ids": [item[1] for item in selected],
                       "tasks": [item[0] for item in selected]})
    config_path, lock_path = root / native.CONFIG, root / "uv.lock"
    _require(config_path.is_file(), "binding_missing:config")
    _require(lock_path.is_file(), "binding_missing:uv.lock")
    bindings = {"config_sha256": _sha256_file(config_path), "uv_lock_sha256": _sha256_file(lock_path),
                "adapter_sha256": _sha256_file(Path(__file__))}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "identity": identity,
        "source_identity": identity,
        "selection_digest": selection_sha,
        "selected_architecture": architecture,
        "native_inventory_digest": _digest(ids),
        "native_task_inventory": [{"task_id": key, "task": task} for key, task in zip(ids, native_inventory)],
        "full_pretraining_inventory_digest": full_digest,
        "nodes": ordered_nodes,
        "workers_per_node": workers_per_node,
        "shards": shards,
        "bindings": bindings,
        "coordinator_reference": coordinator,
        "full_pretraining_reference": full_reference,
    }
    manifest["manifest_digest"] = manifest_digest(manifest)
    return manifest


def _load_manifest(value: Any) -> dict[str, Any]:
    manifest = _read_json(value, "pbs_manifest")
    _require(manifest.get("schema_version") == SCHEMA_VERSION, "pbs_manifest_schema_invalid")
    _require(manifest.get("manifest_digest") == manifest_digest(manifest), "pbs_manifest_digest_mismatch")
    return manifest


def _validate_bindings(root: Path, manifest: Mapping[str, Any]) -> None:
    """Recheck execution bindings before any native worker is submitted."""
    _require(native.identity_at(root) == manifest["identity"], "pbs_source_identity_drift")
    bindings = manifest.get("bindings")
    _require(isinstance(bindings, Mapping), "pbs_bindings_missing")
    adapter = Path(__file__)
    _require(_sha256_file(adapter) == bindings.get("adapter_sha256"), "pbs_adapter_hash_drift")
    config = root / str(native.CONFIG)
    _require(config.is_file() and _sha256_file(config) == bindings.get("config_sha256"), "pbs_config_hash_drift")
    lockfile = root / "uv.lock"
    _require(lockfile.is_file() and _sha256_file(lockfile) == bindings.get("uv_lock_sha256"), "pbs_lockfile_hash_drift")


def _validate_qualification(value: Any, manifest: Mapping[str, Any], hostname: str,
                            workers: int, runtime_expected: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    qualification, reference = _external_receipt(value, "qualification")
    _require(qualification.get("qualified_workers") == workers, "qualification_worker_count_drift")
    runtime = qualification.get("runtime")
    _require(isinstance(runtime, Mapping) and dict(runtime) == dict(runtime_expected)
             and runtime.get("host") == hostname and runtime.get("device") == "cpu",
             "qualification_runtime_drift")
    qualification_identity = qualification.get("identity", qualification.get("source_identity"))
    _require(qualification_identity == manifest["identity"], "qualification_identity_drift")
    status = qualification.get("status")
    _require(status == "goal052_pbs_node_qualification_verified", "qualification_unverified")
    profile_sha = qualification.get("profile_sha256")
    _require(isinstance(profile_sha, str) and len(profile_sha) == 64, "qualification_profile_binding_missing")
    return qualification, reference


def _validate_profile(value: Any, manifest: Mapping[str, Any], hostname: str,
                      qualification: Mapping[str, Any], runtime_expected: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    profile, reference = _external_receipt(value, "profile_review")
    _require(profile.get("status") == "goal052_full_profile_independently_verified", "profile_review_unverified")
    profile_identity = profile.get("identity", profile.get("source_identity"))
    _require(profile_identity == manifest["identity"], "profile_identity_drift")
    _require(profile.get("profile_sha256") == qualification.get("profile_sha256"), "profile_binding_drift")
    runtime = profile.get("runtime")
    _require(isinstance(runtime, Mapping) and dict(runtime) == dict(runtime_expected)
             and runtime.get("host") == hostname and runtime.get("device") == "cpu", "profile_runtime_drift")
    return profile, reference


def _expected_result(manifest: Mapping[str, Any], task: Sequence[Any]) -> str:
    return task_id(manifest["identity"], task)


def _shard(manifest: Mapping[str, Any], node: str) -> dict[str, Any]:
    for shard in manifest["shards"]:
        if shard["node"] == node:
            return shard
    raise ValueError("pbs_node_not_in_manifest")


def _recompute_partition(manifest: Mapping[str, Any], tasks: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    nodes = list(manifest["nodes"])
    identity = manifest["identity"]
    ids = [task_id(identity, task) for task in tasks]
    _require(len(ids) == len(set(ids)), "native_task_inventory_duplicate")
    result = []
    for rank, node in enumerate(nodes):
        selected = [(list(task), task_id(identity, task)) for index, task in enumerate(tasks)
                    if index % len(nodes) == rank]
        result.append({"rank": rank, "node": node, "task_ids": [item[1] for item in selected],
                       "tasks": [item[0] for item in selected]})
    return result


def run_node_shard(
    manifest: Any,
    root: Path,
    node: str,
    qualification: Any,
    profile_review: Any,
    *,
    job_id: str | None = None,
    ownership_root: Path | None = None,
    expected_manifest_digest: str,
    resume: bool = True,
) -> dict[str, Any]:
    """Run one node shard with native spawned workers and atomic completion."""
    manifest = _load_manifest(manifest)
    _require(manifest["manifest_digest"] == expected_manifest_digest, "pbs_manifest_external_digest_mismatch")
    root = Path(root)
    _validate_bindings(root, manifest)
    _require(manifest.get("stage") in STAGES, "pbs_stage_invalid")
    validated = native.validate_inputs(root)
    _require(validated.get("identity") == manifest["identity"], "pbs_validated_identity_drift")
    current_selection, current_selection_digest = _selection(root, None, manifest["identity"])
    _require(current_selection_digest == manifest["selection_digest"]
             and current_selection["selected_architecture"] == manifest["selected_architecture"],
             "pbs_selection_drift")
    hostname = platform.node()
    job_id = job_id or os.environ.get("PBS_JOBID")
    _require(isinstance(job_id, str) and bool(job_id), "pbs_job_id_required")
    nodes = list(manifest.get("nodes", ()))
    _require(nodes == sorted(nodes) and len(nodes) == len(set(nodes)) and 1 <= len(nodes) <= 48,
             "pbs_nodes_binding_invalid")
    workers = manifest.get("workers_per_node")
    _require(isinstance(workers, int) and 1 <= workers <= 28, "pbs_worker_binding_invalid")
    recomputed_tasks = _native_tasks(root, manifest["stage"], manifest["selected_architecture"])
    recomputed_ids = [task_id(manifest["identity"], task) for task in recomputed_tasks]
    _require(_digest(recomputed_ids) == manifest["native_inventory_digest"], "pbs_native_inventory_drift")
    _require(manifest.get("native_task_inventory") == [
        {"task_id": key, "task": task} for key, task in zip(recomputed_ids, recomputed_tasks)
    ], "pbs_native_task_inventory_drift")
    recomputed_shards = _recompute_partition(manifest, recomputed_tasks)
    _require(recomputed_shards == manifest["shards"], "pbs_shard_partition_drift")
    shard = _shard(manifest, str(node))
    runtime_expected = native.host_runtime("cpu")
    qualification_value, qualification_ref = _validate_qualification(qualification, manifest, hostname, workers, runtime_expected)
    profile_value, profile_ref = _validate_profile(profile_review, manifest, hostname, qualification_value, runtime_expected)
    _validate_coordinator(manifest["coordinator_reference"], manifest["identity"], manifest["selection_digest"])
    if manifest["stage"] == "final_targets":
        _require(manifest.get("full_pretraining_reference") is not None, "full_pretraining_reference_missing")
        full_inventory = _full_pretraining_inventory(root, manifest["selected_architecture"])
        full_digest = _digest([task_id(manifest["identity"], task) for task in full_inventory])
        _require(full_digest == manifest.get("full_pretraining_inventory_digest"), "pbs_full_pretraining_inventory_drift")
        _validate_full_pretraining(manifest["full_pretraining_reference"], manifest["identity"],
                                    manifest["selection_digest"], full_digest)
    state = Path(ownership_root or root / ".goal052-pbs") / manifest["stage"]
    rank_dir = state / "ownership" / f"rank-{int(shard['rank']):04d}"
    completion_path = state / "completions" / f"rank-{int(shard['rank']):04d}.json"
    if resume and completion_path.is_file():
        completion = _read_json(completion_path, "rank_completion")
        _require(completion.get("schema_version") == COMPLETION_SCHEMA, "rank_completion_schema_invalid")
        _require(completion.get("status") == "complete", "rank_completion_status_invalid")
        _require(completion.get("manifest_digest") == manifest["manifest_digest"], "completion_manifest_drift")
        _require(completion.get("stage") == manifest["stage"] and completion.get("rank") == shard["rank"]
                 and completion.get("node") == node, "completion_owner_binding_drift")
        _require(completion.get("task_ids") == shard["task_ids"], "completion_task_inventory_drift")
        _require(isinstance(completion.get("results"), Mapping)
                 and set(completion["results"]) == set(shard["task_ids"])
                 and all(completion["results"][key] == key for key in shard["task_ids"]),
                 "rank_completion_results_invalid")
        return completion
    try:
        rank_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise ValueError("pbs_rank_ownership_collision") from None
    _atomic_json(rank_dir / "owner.json", {"job_id": job_id, "hostname": hostname,
                                             "manifest_digest": manifest["manifest_digest"], "node": node})
    tasks = [canonical_task(task) for task in shard["tasks"]]
    expected = {task_id(manifest["identity"], task): _expected_result(manifest, task) for task in tasks}
    results: dict[str, str] = {}
    context = multiprocessing.get_context("spawn")
    try:
        if tasks:
            with ProcessPoolExecutor(max_workers=workers, mp_context=context,
                                     initializer=native.worker_init,
                                     initargs=(str(root), "cpu", manifest["identity"])) as pool:
                futures = {pool.submit(native.worker, task): task for task in tasks}
                for future in as_completed(futures):
                    task = futures[future]
                    key = task_id(manifest["identity"], task)
                    value = future.result()
                    _require(value == expected[key], "native_worker_result_key_mismatch")
                    results[key] = value
        _require(set(results) == set(expected), "native_worker_completion_incomplete")
    except BaseException:
        # The ownership marker remains intentionally.  A later run must make
        # stale ownership explicit instead of silently taking over a rank.
        raise
    completion = {
        "schema_version": COMPLETION_SCHEMA,
        "status": "complete",
        "manifest_digest": manifest["manifest_digest"],
        "stage": manifest["stage"],
        "rank": shard["rank"],
        "node": node,
        "job_id": job_id,
        "hostname": hostname,
        "task_ids": shard["task_ids"],
        "results": {key: results[key] for key in shard["task_ids"]},
        "qualification_reference": qualification_ref,
        "profile_reference": profile_ref,
        "coordinator_reference": manifest["coordinator_reference"],
        "full_pretraining_reference": manifest.get("full_pretraining_reference"),
    }
    _atomic_json(completion_path, completion)
    return completion


# Descriptive aliases for wrappers and callers that use the PBS vocabulary.
plan_manifest = plan_stage
run_shard = run_node_shard


__all__ = ["SCHEMA_VERSION", "canonical_task", "task_id", "manifest_digest",
           "plan_stage", "plan_manifest", "run_node_shard", "run_shard"]
