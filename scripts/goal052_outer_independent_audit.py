#!/usr/bin/env python3
"""Independent, response-free audit of a closed Goal052 outer run.

This program intentionally does not import dsdm_phase1 code.  It rebuilds the
frozen task recipe from JSON authorities, hashes source/input/model artifacts,
validates qualification and leaf receipts, and recomputes every seed mean and
the fixed ensemble.  It never opens outer response, membership, richness, or
score-output content; recorded input files are read only as opaque bytes for
SHA-256 verification.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence

import numpy as np

SCHEMA = "dsdm-outer-independent-closure-audit-v1"
PLAN_SCHEMA = "goal052-outer-plan-v1"
CLOSURE_SCHEMA = "goal052-outer-closure-v1"
RUNTIME_SCHEMA = "goal052-outer-runtime-v1"
CANARY_STATUS = "goal052_outer_canary_valid"
PROFILE_STATUS = "goal052_outer_profile_valid"
QUALIFIED_STATUS = "outer_runtime_qualified"
CLOSURE_STATUS = "predictions_closed_before_response"
FULL_FOLD = -1
EXPECTED_DOMAIN_ROWS = 144_860
EXPECTED_FEATURES = 103
EXPECTED_TARGETS = 157
EXPECTED_TASK_COUNTS = {"q": 10, "pretraining": 50, "neural": 3140, "conventional": 1042}
NEURAL_ARMS = (
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
)
CONVENTIONAL_ARMS = ("selected_conventional", "selected_conventional_plus_q")
COMPONENT_ARMS = NEURAL_ARMS + CONVENTIONAL_ARMS
ENSEMBLE = "fixed_ensemble"
ALL_ARMS = COMPONENT_ARMS + (ENSEMBLE,)
SEED_LABELS = tuple(f"seed{i:02d}" for i in range(5))

EXPECTED_SOURCE_PATHS = frozenset({
    "scripts/goal049_canonical_response.py",
    "scripts/validate_goal049_seawfb_canonical_response.py",
    "src/dsdm/contracts.py",
    "src/dsdm/inner_evaluation.py",
    "src/dsdm/models.py",
    "src/dsdm_phase1/goal050_compute_canary.py",
    "src/dsdm_phase1/goal050_seawfb_foundation.py",
    "src/dsdm_phase1/goal051_seawfb_conventional.py",
    "src/dsdm_phase1/goal052_checkpoints.py",
    "src/dsdm_phase1/goal052_design.py",
    "src/dsdm_phase1/goal052_outer.py",
    "src/dsdm_phase1/goal052_outer_artifacts.py",
    "src/dsdm_phase1/goal052_outer_data.py",
    "src/dsdm_phase1/goal052_outer_diagnostics.py",
    "src/dsdm_phase1/goal052_outer_predictors.py",
    "src/dsdm_phase1/goal052_outer_response.py",
    "src/dsdm_phase1/goal052_outer_runtime.py",
    "src/dsdm_phase1/goal052_outer_scoring.py",
    "src/dsdm_phase1/goal052_outer_training.py",
    "src/dsdm_phase1/goal052_profile.py",
    "src/dsdm_phase1/goal052_results.py",
    "src/dsdm_phase1/goal052_seawfb_dsdm.py",
    "src/dsdm_phase1/mainland_dsdm.py",
    "src/dsdm_phase1/mainland_modeling.py",
    "src/dsdm_phase1/model_adapters.py",
    "src/dsdm_phase1/modeling_contract.py",
    "src/dsdm_phase1/seawfb_dsdm_data.py",
    "src/dsdm_phase1/seawfb_dsdm_training.py",
    "src/dsdm_phase1/seawfb_modeling.py",
})
EXPECTED_INPUT_PATHS = frozenset({
    "config/goal049_seawfb_canonical_response.json",
    "config/goal050_seawfb_modeling_foundation.json",
    "config/goal051_seawfb_conventional.json",
    "config/goal052_seawfb_dsdm.json",
    "data/processed/dsdm/goal048-seawfb-bioregional-freeze/predictors/predictor_substrate.parquet",
    "data/processed/dsdm/goal048-seawfb-bioregional-freeze/response_free/cell_region_ledger.parquet",
    "data/processed/dsdm/goal050-seawfb-modeling-foundation/cells.parquet",
    "data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json",
    "data/processed/dsdm/goal050-seawfb-modeling-foundation/learning_curves.json",
    "data/processed/dsdm/goal050-seawfb-modeling-foundation/memberships.parquet",
    "evidence/seawfb_canonical_response/goal049/completion_receipt.json",
    "evidence/seawfb_canonical_response/goal049/panel_summary.json",
    "evidence/seawfb_conventional/goal051/completion_review.json",
    "evidence/seawfb_conventional/goal051/summary.json",
    "evidence/seawfb_dsdm/goal052/ann-recovery-review-20261002.json",
    "evidence/seawfb_dsdm/goal052/completion_review.json",
    "evidence/seawfb_dsdm/goal052/outer-inventory-20260929.json",
    "evidence/seawfb_dsdm/goal052/summary.json",
    "metadata/goal049_registry_taxonomy_freeze.json",
    "metadata/goal050_manifest.json",
    "metadata/goal050_transforms.json",
    "uv.lock",
})


_HASH_CACHE: dict[Path, tuple[tuple[int, int, int], str]] = {}


class AuditError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise AuditError(code, detail)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), "missing_file", str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise AuditError("invalid_json", f"{path}: {exc}") from exc
    require(isinstance(value, dict), "json_object_required", str(path))
    return value


def sha256_file(path: Path) -> str:
    require(path.is_file(), "missing_file", str(path))
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise AuditError("file_read_failed", f"{path}: {exc}") from exc
    return digest.hexdigest()


def cached_sha256(path: Path) -> str:
    """Hash an immutable audit input once, with a final stat-stability check."""
    resolved = path.resolve()
    require(resolved.is_file(), "missing_file", str(resolved))
    before = resolved.stat()
    signature = (before.st_ino, before.st_size, before.st_mtime_ns)
    cached = _HASH_CACHE.get(resolved)
    if cached is not None:
        require(cached[0] == signature, "file_changed_during_audit", str(resolved))
        return cached[1]
    value = sha256_file(resolved)
    after = resolved.stat()
    after_signature = (after.st_ino, after.st_size, after.st_mtime_ns)
    require(signature == after_signature, "file_changed_during_audit", str(resolved))
    _HASH_CACHE[resolved] = (signature, value)
    return value


def require_hash_cache_stable() -> None:
    for path, (signature, _) in _HASH_CACHE.items():
        require(path.is_file(), "file_changed_during_audit", str(path))
        state = path.stat()
        require((state.st_ino, state.st_size, state.st_mtime_ns) == signature,
                "file_changed_during_audit", str(path))


def canonical_digest(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise AuditError("canonical_json_failed", str(exc)) from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_seed(*parts: object) -> int:
    raw = "\x1f".join(map(str, parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


def slug(value: str) -> str:
    return "_".join(value.lower().split())


def is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def safe_path(base: Path, relative: Any, *, label: str) -> Path:
    require(isinstance(relative, str) and relative and not os.path.isabs(relative), "unsafe_path", f"{label}: {relative!r}")
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise AuditError("unsafe_path", f"{label}: {relative}") from exc
    return candidate


def checked_file(base: Path, relative: Any, expected: Any, *, label: str) -> Path:
    require(is_digest(expected), "invalid_recorded_digest", f"{label}: {expected!r}")
    path = safe_path(base, relative, label=label)
    actual = cached_sha256(path)
    require(actual == expected, "file_hash_mismatch", f"{label}: {relative}; expected={expected}; actual={actual}")
    return path


def task_id(task: Mapping[str, Any]) -> str:
    kind = task.get("kind")
    if kind == "q":
        return f"q.block{int(task['block']):02d}"
    if kind == "pretraining":
        return f"pretraining.block{int(task['block']):02d}.{task['seed_label']}"
    require(kind in ("neural", "conventional"), "task_kind_invalid", repr(kind))
    return f"{kind}.{slug(str(task['target']))}.{task['arm']}.{task['seed_label']}"


def expected_recipe(root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]], dict[str, Any]]:
    inventory = read_json(root / "evidence/seawfb_dsdm/goal052/outer-inventory-20260929.json")
    recovery = read_json(root / "evidence/seawfb_dsdm/goal052/ann-recovery-review-20261002.json")
    crossfit = read_json(root / "data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json")
    config051 = read_json(root / "config/goal051_seawfb_conventional.json")
    config052 = read_json(root / "config/goal052_seawfb_dsdm.json")
    panel = read_json(root / "evidence/seawfb_canonical_response/goal049/panel_summary.json")
    budgets = {(row["target"], row["method"]): row for row in recovery["procedures"]}
    tasks: list[dict[str, Any]] = []
    thresholds: dict[str, dict[str, float]] = {}
    blocks = sorted(set(map(int, crossfit["focal_blocks"].values())))
    q_namespace = config051["community_control"]["fit_seed_namespace"]
    target_namespace = config051["execution"]["fit_seed_namespace"]
    for block in blocks:
        tasks.append({"kind": "q", "block": block,
                      "seed": stable_seed(q_namespace, "q_linear", block, FULL_FOLD, "full")})
        epoch = inventory["pretraining"]["prospective_epoch_choices"][f"block{block:02d}"]["pooled25_median_selected_epoch"]
        for label in SEED_LABELS:
            tasks.append({"kind": "pretraining", "block": block, "seed_label": label,
                          "seed": stable_seed("goal052-pretraining-v1", block, FULL_FOLD, "full", "seawfb_scale", label),
                          "epochs": epoch})
    for row in inventory["neural_target100_full"]["records"]:
        target = row["target"]
        thresholds[target] = {}
        for arm in NEURAL_ARMS:
            item = row["arms"][arm]
            thresholds[target][arm] = float(item["oof_threshold"])
            for label in SEED_LABELS:
                tasks.append({"kind": "neural", "target": target,
                              "block": int(crossfit["focal_blocks"][target]), "arm": arm,
                              "seed_label": label,
                              "seed": stable_seed("goal052-target-v1", target, 100, FULL_FOLD, "seawfb_scale", label),
                              "epochs": int(item["median_rounded_epoch"])})
    for row in inventory["conventional_target100"]["records"]:
        target = row["target"]
        for method, arm in zip(("ordinary", "q_full"), CONVENTIONAL_ARMS):
            item = row[method]
            thresholds[target][arm] = float(item["oof_threshold"])
            epoch = None
            if item["family"] == "shallow_ann":
                require((target, method) in budgets, "recovery_budget_missing", f"{target}:{method}")
                budget = budgets[(target, method)]
                require(budget["candidate_id"] == item["candidate_id"] and all(budget["exact_checks"].values()),
                        "recovery_budget_invalid", f"{target}:{method}")
                epoch = int(budget["median_rounded_epoch"])
            for label in item["seed_labels"]:
                tasks.append({"kind": "conventional", "target": target,
                              "block": int(crossfit["focal_blocks"][target]), "arm": arm,
                              "family": item["family"], "candidate_id": item["candidate_id"],
                              "seed_label": label, "epochs": epoch,
                              "seed": stable_seed(target_namespace, target, 100, FULL_FOLD,
                                                  item["family"], item["candidate_id"], label)})
    tasks = [{**task, "id": task_id(task)} for task in tasks]
    selected_architecture = next(item for item in config052["architectures"]["candidates"] if item["id"] == "seawfb_scale")
    authorities = {
        "panels": {
            "primary": panel["primary_common"]["species"],
            "regional": {region: value["species"] for region, value in panel["secondary_region_specific"].items()},
        },
        "x20_targets": {region: value["species"] for region, value in panel["x20_evaluation_only"].items()},
        "q_numerical_fit": config051["community_control"]["numerical_fit"],
        "architecture": selected_architecture,
    }
    return tasks, thresholds, authorities


def validate_vector(values: np.ndarray, rows: int, label: str) -> np.ndarray:
    array = np.asarray(values)
    require(array.shape == (rows,), "score_shape_invalid", f"{label}: {array.shape} != {(rows,)}")
    require(array.dtype == np.float64, "score_dtype_invalid", f"{label}: {array.dtype}")
    require(np.isfinite(array).all(), "score_nonfinite", label)
    require(np.all((array >= 0.0) & (array <= 1.0)), "score_range_invalid", label)
    return array


def load_scores(path: Path, rows: int, label: str) -> np.ndarray:
    try:
        with np.load(path, allow_pickle=False) as payload:
            require(set(payload.files) == {"scores"}, "seed_score_inventory_invalid", label)
            return validate_vector(np.array(payload["scores"], copy=True), rows, label)
    except AuditError:
        raise
    except Exception as exc:
        raise AuditError("npz_read_failed", f"{path}: {exc}") from exc


def _strip_canary_dynamic(value: Any) -> Any:
    dynamic = {"repeat", "pid", "runtime_seconds", "elapsed_seconds", "wall_seconds", "peak_rss_bytes", "resources"}
    if isinstance(value, Mapping):
        return {key: _strip_canary_dynamic(item) for key, item in value.items() if key not in dynamic}
    if isinstance(value, list):
        return [_strip_canary_dynamic(item) for item in value]
    return value


def validate_qualification(run: Path, relative: str, expected_hash: str, plan: Mapping[str, Any], cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if relative in cache:
        require(cache[relative]["_sha256"] == expected_hash, "qualification_leaf_hash_disagreement", relative)
        return cache[relative]
    require(relative.startswith("qualification/"), "qualification_path_invalid", relative)
    path = checked_file(run, relative, expected_hash, label="qualification")
    final = read_json(path)
    require(final.get("schema_version") == RUNTIME_SCHEMA and final.get("status") == QUALIFIED_STATUS,
            "qualification_status_invalid", relative)
    require(final.get("plan_digest") == plan["plan_digest"], "qualification_plan_mismatch", relative)
    require(final.get("outer_response_rows_read") == 0, "qualification_response_access", relative)
    fingerprint = final.get("runtime_fingerprint")
    require(is_digest(fingerprint), "qualification_fingerprint_invalid", relative)
    canary_rel, profile_rel = final.get("canary"), final.get("profile")
    require(final.get("files") == {canary_rel: final.get("canary_sha256"), profile_rel: final.get("profile_sha256")},
            "qualification_file_inventory_invalid", relative)
    canary_path = checked_file(run, canary_rel, final.get("canary_sha256"), label="qualification_canary")
    profile_path = checked_file(run, profile_rel, final.get("profile_sha256"), label="qualification_profile")
    canary, profile = read_json(canary_path), read_json(profile_path)
    for stage, status, stage_rel in ((canary, CANARY_STATUS, canary_rel), (profile, PROFILE_STATUS, profile_rel)):
        require(stage.get("schema_version") == RUNTIME_SCHEMA and stage.get("status") == status,
                "qualification_stage_invalid", stage_rel)
        require(stage.get("plan_digest") == plan["plan_digest"], "qualification_stage_plan_mismatch", stage_rel)
        require(stage.get("runtime_fingerprint") == fingerprint, "qualification_stage_fingerprint_mismatch", stage_rel)
        require(stage.get("code_hashes") == plan["sources"], "qualification_stage_source_mismatch", stage_rel)
        require(stage.get("outer_response_rows_read") == 0, "qualification_stage_response_access", stage_rel)
    workers_tested = canary.get("workers_tested")
    repeats = canary.get("repeats")
    require(type(workers_tested) is int and workers_tested >= 1, "canary_workers_invalid", canary_rel)
    require(canary.get("deterministic_repeats") is True and isinstance(repeats, list) and len(repeats) >= 2,
            "canary_repeat_inventory_invalid", canary_rel)
    pids = [item.get("pid") for item in repeats]
    require(len(set(pids)) == workers_tested and all(type(pid) is int and pid > 0 for pid in pids),
            "canary_process_coverage_invalid", canary_rel)
    reference = _strip_canary_dynamic(repeats[0])
    require(all(_strip_canary_dynamic(item) == reference for item in repeats[1:]),
            "canary_repeat_drift", canary_rel)
    profile_workers = profile.get("qualified_workers")
    require(type(profile_workers) is int and profile_workers >= 1, "profile_workers_invalid", profile_rel)
    require(type(profile.get("peak_rss_bytes")) is int and profile["peak_rss_bytes"] > 0,
            "profile_peak_invalid", profile_rel)
    expected_workers = min(workers_tested, profile_workers)
    require(final.get("canary_workers_tested") == workers_tested and final.get("qualified_workers") == expected_workers,
            "qualification_worker_binding_invalid", relative)
    final = dict(final)
    final.update({"_sha256": expected_hash, "_canary": canary, "_profile": profile})
    cache[relative] = final
    return final


def expected_dependencies(task: Mapping[str, Any]) -> set[str]:
    kind = task["kind"]
    dependencies: set[str] = set()
    if kind == "neural":
        if task["arm"] == NEURAL_ARMS[1]:
            dependencies.add(f"q.block{int(task['block']):02d}")
        if task["arm"] in NEURAL_ARMS[2:]:
            dependencies.add(f"pretraining.block{int(task['block']):02d}.{task['seed_label']}")
    elif kind == "conventional" and task["arm"] == CONVENTIONAL_ARMS[1]:
        dependencies.add(f"q.block{int(task['block']):02d}")
    return dependencies


def validate_fit_receipt(plan: Mapping[str, Any], task: Mapping[str, Any], receipt: Mapping[str, Any], run: Path,
                         tasks_by_id: Mapping[str, Mapping[str, Any]]) -> None:
    kind = task["kind"]
    fit = receipt.get("fit")
    require(isinstance(fit, Mapping), "fit_receipt_missing", task["id"])
    dependencies = receipt.get("dependencies")
    require(isinstance(dependencies, Mapping) and set(dependencies) == expected_dependencies(task),
            "dependency_inventory_invalid", task["id"])
    for dependency_id, checksum in dependencies.items():
        require(dependency_id in tasks_by_id, "dependency_unknown", f"{task['id']}->{dependency_id}")
        checked_file(run, f"fits/{dependency_id}/receipt.json", checksum, label="dependency_receipt")
        dependent = read_json(run / f"fits/{dependency_id}/receipt.json")
        require(dependent.get("task") == tasks_by_id[dependency_id], "dependency_identity_invalid", dependency_id)
        if dependency_id.startswith("pretraining."):
            prefit = dependent.get("fit", {})
            require(fit.get("transfer_digest") == fit.get("initial_shared_digest") == prefit.get("final_shared_digest"),
                    "transfer_digest_mismatch", task["id"])
    if kind in ("pretraining", "neural"):
        require(fit.get("seed") == task["seed"] and fit.get("replay_shuffle_seed") == task["seed"] + 100_000,
                "neural_seed_mismatch", task["id"])
        require(fit.get("epochs") == fit.get("completed_epochs") == task["epochs"] and fit.get("batch_size") == 128,
                "neural_budget_mismatch", task["id"])
        require(fit.get("fit_mode") == "fixed_budget" and fit.get("early_stopping") is False
                and fit.get("discovery_rows") == 0 and fit.get("stopping_rows") == 0,
                "neural_discovery_or_stopping_detected", task["id"])
        require(fit.get("state_finite") is True, "neural_state_invalid", task["id"])
        if kind == "pretraining":
            require(receipt.get("data") == plan["auxiliary_rows"][str(task["block"])],
                    "pretraining_data_mismatch", task["id"])
            require(fit.get("transferred") is False, "pretraining_transfer_invalid", task["id"])
        else:
            transferred = task["arm"] in NEURAL_ARMS[2:]
            frozen = task["arm"] == NEURAL_ARMS[2]
            require(fit.get("head_initialization_seed") == task["seed"] + 17,
                    "target_head_seed_mismatch", task["id"])
            require(fit.get("transferred") == transferred and fit.get("freeze_trunk") == frozen,
                    "target_transfer_mode_mismatch", task["id"])
            if frozen:
                require(fit.get("freeze_shared_state_invariant") is True
                        and fit.get("initial_shared_digest") == fit.get("final_shared_digest"),
                        "frozen_trunk_mismatch", task["id"])
    elif kind == "conventional":
        require(fit.get("converged") is True and fit.get("seed") == task["seed"]
                and fit.get("family") == task["family"] and fit.get("candidate_id") == task["candidate_id"],
                "conventional_fit_mismatch", task["id"])
        if task["family"] == "shallow_ann":
            require(fit.get("best_epoch") == fit.get("iterations") == task["epochs"],
                    "conventional_ann_budget_mismatch", task["id"])
    else:
        require(kind == "q", "task_kind_invalid", task["id"])
        require(fit.get("fit_seed") == task["seed"] and fit.get("candidate_id") == "enet04",
                "q_fit_identity_mismatch", task["id"])
        require(fit.get("held_block") == task["block"] and fit.get("held_fold") == FULL_FOLD
                and fit.get("auxiliary_size") == "full", "q_fit_scope_mismatch", task["id"])
        expected = plan["auxiliary_rows"][str(task["block"])]
        require(fit.get("heads") == expected.get("heads") and fit.get("expanded_rows") == expected.get("rows")
                and fit.get("held_species") == expected.get("excluded_species"),
                "q_fit_rows_mismatch", task["id"])
    if kind in ("neural", "conventional"):
        require(fit.get("save_reload_predictions_exact") is True, "save_reload_not_verified", task["id"])
        data, expected = receipt.get("data", {}), plan["target_rows"][task["target"]]
        for key in ("row_digest", "cell_id_digest", "rows", "folds_digest"):
            require(data.get(key) == expected.get(key), "target_data_mismatch", f"{task['id']}:{key}")
        augmented = task["arm"] in (NEURAL_ARMS[1], CONVENTIONAL_ARMS[1])
        scaling = data.get("q_scaling")
        if augmented:
            require(isinstance(scaling, Mapping), "q_scaling_missing", task["id"])
            mean, sd = scaling.get("training_mean"), scaling.get("training_population_sd")
            require(isinstance(mean, (int, float)) and isinstance(sd, (int, float))
                    and math.isfinite(float(mean)) and math.isfinite(float(sd)) and float(sd) > 0,
                    "q_scaling_invalid", task["id"])
        else:
            require(scaling is None, "unexpected_q_scaling", task["id"])


def audit_run(root: Path, run: Path, *, production: bool = True,
              expected_counts: Mapping[str, int] | None = None,
              expected_targets: int | None = None, expected_rows: int | None = None,
              progress: bool = True) -> dict[str, Any]:
    root, run = root.resolve(), run.resolve()
    _HASH_CACHE.clear()
    started = utc_now()
    script_hash = sha256_file(Path(__file__).resolve())
    require(not (run / "scores.json").exists() and not (run / "scoring-failure.json").exists(),
            "post_response_or_scoring_artifact_present", str(run))
    plan_path = run / "plan.json"
    plan_sha = cached_sha256(plan_path)
    plan = read_json(plan_path)
    require(plan.get("schema_version") == PLAN_SCHEMA, "plan_schema_invalid", repr(plan.get("schema_version")))
    identity = {key: value for key, value in plan.items() if key not in {"plan_digest", "created_utc"}}
    require(plan.get("plan_digest") == canonical_digest(identity), "plan_digest_mismatch", str(plan_path))
    require(plan.get("outer_response_rows_read") == 0, "plan_response_access", str(plan_path))
    sources, inputs = plan.get("sources"), plan.get("inputs")
    require(isinstance(sources, Mapping) and isinstance(inputs, Mapping), "plan_hash_inventory_invalid", str(plan_path))
    if production:
        require(set(sources) == EXPECTED_SOURCE_PATHS, "source_inventory_mismatch",
                f"missing={sorted(EXPECTED_SOURCE_PATHS-set(sources))}; extra={sorted(set(sources)-EXPECTED_SOURCE_PATHS)}")
        require(set(inputs) == EXPECTED_INPUT_PATHS, "input_inventory_mismatch",
                f"missing={sorted(EXPECTED_INPUT_PATHS-set(inputs))}; extra={sorted(set(inputs)-EXPECTED_INPUT_PATHS)}")
    for relative, expected in sources.items():
        checked_file(root, relative, expected, label="source")
    for relative, expected in inputs.items():
        checked_file(root, relative, expected, label="input")

    tasks = plan.get("tasks")
    require(isinstance(tasks, list), "task_inventory_invalid", "tasks is not a list")
    require(all(isinstance(task, Mapping) for task in tasks), "task_inventory_invalid", "non-object task")
    task_ids = [task.get("id") for task in tasks]
    require(all(isinstance(value, str) and value for value in task_ids) and len(set(task_ids)) == len(task_ids),
            "task_id_inventory_invalid", "duplicate or invalid task id")
    for task in tasks:
        require(task["id"] == task_id(task), "task_id_mismatch", str(task.get("id")))
    counts = dict(Counter(task["kind"] for task in tasks))
    expected_counts = dict(expected_counts or EXPECTED_TASK_COUNTS)
    require(counts == expected_counts and len(tasks) == sum(expected_counts.values()),
            "task_count_mismatch", f"observed={counts}; expected={expected_counts}")
    targets = plan.get("targets")
    expected_targets = EXPECTED_TARGETS if expected_targets is None else expected_targets
    require(isinstance(targets, list) and len(targets) == expected_targets and targets == sorted(targets)
            and len(set(targets)) == len(targets), "target_inventory_invalid", f"count={len(targets) if isinstance(targets,list) else None}")
    thresholds = plan.get("thresholds")
    require(isinstance(thresholds, Mapping) and set(thresholds) == set(targets), "threshold_target_inventory_invalid", "")
    for target, values in thresholds.items():
        require(isinstance(values, Mapping) and set(values) == set(COMPONENT_ARMS), "threshold_arm_inventory_invalid", target)
        require(all(isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(float(value)) and 0 <= float(value) <= 1 for value in values.values()),
                "threshold_value_invalid", target)
    if production:
        recipe_tasks, recipe_thresholds, authorities = expected_recipe(root)
        require(tasks == recipe_tasks, "task_recipe_mismatch", "plan tasks differ from frozen JSON authorities")
        require(thresholds == recipe_thresholds, "threshold_recipe_mismatch", "plan thresholds differ from frozen inventory")
        require(plan.get("panels") == authorities["panels"], "panel_recipe_mismatch", "")
        require(plan.get("x20_targets") == authorities["x20_targets"], "x20_recipe_mismatch", "")
        require(plan.get("q_numerical_fit") == authorities["q_numerical_fit"], "q_schedule_mismatch", "")
        require(plan.get("architecture") == authorities["architecture"] and plan.get("batch_size") == 128
                and plan.get("full_fold_sentinel") == FULL_FOLD, "architecture_or_fit_constant_mismatch", "")

    domain_rows = int(plan.get("domain", {}).get("rows", -1))
    expected_rows = EXPECTED_DOMAIN_ROWS if expected_rows is None else expected_rows
    require(domain_rows == expected_rows, "domain_row_count_mismatch", f"{domain_rows} != {expected_rows}")
    domain_path = checked_file(run, "domain.npz", plan.get("domain_file_sha256"), label="domain")
    try:
        with np.load(domain_path, allow_pickle=False) as payload:
            required_domain_arrays = {"cell_ids", "regions", "x", "longitude", "latitude", "block_x", "block_y"}
            require(set(payload.files) == required_domain_arrays, "domain_array_inventory_invalid", repr(payload.files))
            cell_ids = np.asarray(payload["cell_ids"], dtype=str)
            regions = np.asarray(payload["regions"], dtype=str)
            x = np.asarray(payload["x"])
            longitude, latitude = np.asarray(payload["longitude"]), np.asarray(payload["latitude"])
            block_x, block_y = np.asarray(payload["block_x"]), np.asarray(payload["block_y"])
    except AuditError:
        raise
    except Exception as exc:
        raise AuditError("npz_read_failed", f"{domain_path}: {exc}") from exc
    require(cell_ids.shape == regions.shape == longitude.shape == latitude.shape == block_x.shape == block_y.shape == (domain_rows,),
            "domain_vector_shape_invalid", "")
    require(len(set(cell_ids.tolist())) == domain_rows, "domain_cell_id_duplicate", "")
    require(x.shape == (domain_rows, EXPECTED_FEATURES) and x.dtype == np.float64 and np.isfinite(x).all(),
            "domain_feature_matrix_invalid", f"shape={x.shape}; dtype={x.dtype}")
    require(np.isfinite(longitude).all() and np.isfinite(latitude).all(), "domain_coordinate_invalid", "")
    require(np.issubdtype(block_x.dtype, np.integer) and np.issubdtype(block_y.dtype, np.integer), "domain_block_dtype_invalid", "")
    domain_summary = plan["domain"]
    require(domain_summary.get("feature_count") == EXPECTED_FEATURES and domain_summary.get("feature_dtype") == "float64",
            "domain_summary_feature_invalid", "")
    require(hashlib.sha256(("\n".join(cell_ids.tolist()) + "\n").encode()).hexdigest() == domain_summary.get("cell_id_sha256"),
            "domain_cell_digest_mismatch", "")
    require(hashlib.sha256(("\n".join(regions.tolist()) + "\n").encode()).hexdigest() == domain_summary.get("region_sha256"),
            "domain_region_digest_mismatch", "")
    require(hashlib.sha256(x.tobytes()).hexdigest() == domain_summary.get("encoded_sha256"),
            "domain_encoded_digest_mismatch", "")
    require({region: int(np.sum(regions == region)) for region in ("NCP", "SEH", "NNC")} == domain_summary.get("rows_by_region"),
            "domain_region_count_mismatch", "")
    domain_input_map = {
        "config": "config/goal050_seawfb_modeling_foundation.json",
        "manifest": "metadata/goal050_manifest.json",
        "transforms": "metadata/goal050_transforms.json",
        "ledger": "data/processed/dsdm/goal048-seawfb-bioregional-freeze/response_free/cell_region_ledger.parquet",
        "predictors": "data/processed/dsdm/goal048-seawfb-bioregional-freeze/predictors/predictor_substrate.parquet",
    }
    if production:
        require(domain_summary.get("input_sha256") == {key: inputs[path] for key, path in domain_input_map.items()},
                "domain_input_binding_mismatch", "")

    closure_path = run / "closure.json"
    closure_sha = cached_sha256(closure_path)
    closure = read_json(closure_path)
    closure_identity = {key: value for key, value in closure.items() if key != "closure_digest"}
    require(closure.get("schema_version") == CLOSURE_SCHEMA, "closure_schema_invalid", repr(closure.get("schema_version")))
    require(closure.get("closure_digest") == canonical_digest(closure_identity), "closure_digest_mismatch", str(closure_path))
    require(closure.get("status") == CLOSURE_STATUS and closure.get("outer_response_rows_read") == 0,
            "closure_firewall_invalid", "")
    require(closure.get("plan_digest") == plan["plan_digest"], "closure_plan_mismatch", "")
    require(closure.get("fit_counts") == counts, "closure_fit_counts_mismatch", repr(closure.get("fit_counts")))
    require(closure.get("thresholds") == thresholds and closure.get("domain") == domain_summary,
            "closure_threshold_or_domain_mismatch", "")
    predictions = closure.get("predictions")
    require(isinstance(predictions, Mapping) and set(predictions) == set(targets), "closure_prediction_inventory_invalid", "")
    for target in targets:
        require(predictions[target] == f"predictions/{slug(target)}.npz", "prediction_path_mismatch", target)
    closure_files = closure.get("files")
    require(isinstance(closure_files, Mapping), "closure_file_inventory_invalid", "not an object")

    tasks_by_id = {task["id"]: task for task in tasks}
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    qualifications: dict[str, dict[str, Any]] = {}
    expected_files = {"plan.json", "domain.npz"}
    fits_dir = run / "fits"
    require(fits_dir.is_dir(), "missing_directory", str(fits_dir))
    fit_entries = list(fits_dir.iterdir())
    require(all(path.is_dir() and not path.is_symlink() for path in fit_entries),
            "unexpected_fit_root_entry", str(fits_dir))
    observed_fit_dirs = {path.name for path in fit_entries}
    require(observed_fit_dirs == set(tasks_by_id), "fit_directory_inventory_mismatch",
            f"missing={len(set(tasks_by_id)-observed_fit_dirs)}; extra={len(observed_fit_dirs-set(tasks_by_id))}")
    for index, task in enumerate(tasks):
        identifier = task["id"]
        directory = safe_path(run, f"fits/{identifier}", label="leaf_directory")
        receipt_rel = f"fits/{identifier}/receipt.json"
        receipt_path = safe_path(run, receipt_rel, label="leaf_receipt")
        receipt = read_json(receipt_path)
        require(receipt.get("status") == "outer_fit_complete" and receipt.get("plan_digest") == plan["plan_digest"]
                and receipt.get("task") == task, "leaf_identity_invalid", identifier)
        require(receipt.get("outer_response_rows_read") == 0, "leaf_response_access", identifier)
        qualification_rel, qualification_sha = receipt.get("qualification"), receipt.get("qualification_sha256")
        validate_qualification(run, qualification_rel, qualification_sha, plan, qualifications)
        files = receipt.get("files")
        required_files = ({"model.npz"} if task["kind"] == "q" else
                          {"model.pt", "shared.pt"} if task["kind"] == "pretraining" else
                          {"model.pt", "scores.npz", "fit-input.json"} if task["kind"] == "neural" else
                          {"model.json", "scores.npz", "fit-input.json"})
        require(isinstance(files, Mapping) and set(files) == required_files, "leaf_file_inventory_invalid", identifier)
        for name, checksum in files.items():
            checked_file(directory, name, checksum, label="leaf_artifact")
        allowed_names = required_files | {"receipt.json", ".lock"}
        leaf_entries = list(directory.iterdir())
        require(all(path.is_file() and not path.is_symlink() for path in leaf_entries),
                "unexpected_leaf_entry", identifier)
        observed_names = {path.name for path in leaf_entries}
        require(observed_names <= allowed_names, "unexpected_leaf_file", f"{identifier}: {sorted(observed_names-allowed_names)}")
        if "fit-input.json" in files:
            fit_input = read_json(directory / "fit-input.json")
            require(fit_input == {"plan_digest": plan["plan_digest"], "task": task,
                                  "data": receipt.get("data"), "dependencies": receipt.get("dependencies")},
                    "fit_input_mismatch", identifier)
        validate_fit_receipt(plan, task, receipt, run, tasks_by_id)
        if task["kind"] == "q":
            try:
                with np.load(directory / "model.npz", allow_pickle=False) as payload:
                    require(set(payload.files) == {"coefficient", "intercept"}, "q_model_inventory_invalid", identifier)
                    coefficient = np.asarray(payload["coefficient"], dtype="<f8").reshape(-1)
                    intercept = np.asarray(payload["intercept"], dtype="<f8").reshape(-1)
                    require(len(coefficient) > 0 and intercept.shape == (1,)
                            and np.isfinite(coefficient).all() and np.isfinite(intercept).all(),
                            "q_model_nonfinite_or_shape_invalid", identifier)
                    parameter_digest = hashlib.sha256(np.concatenate([coefficient, intercept]).tobytes()).hexdigest()
                    require(parameter_digest == receipt["fit"].get("parameter_digest"),
                            "q_parameter_digest_mismatch", identifier)
            except AuditError:
                raise
            except Exception as exc:
                raise AuditError("npz_read_failed", f"{directory/'model.npz'}: {exc}") from exc
        if task["kind"] in ("neural", "conventional"):
            groups[(task["target"], task["arm"])].append(task)
        expected_files.add(receipt_rel)
        expected_files.update(f"fits/{identifier}/{name}" for name in files)
        expected_files.add(qualification_rel)
        expected_files.update(qualifications[qualification_rel]["files"])
        if progress and (index + 1) % 250 == 0:
            print(f"audited leaves {index+1}/{len(tasks)}", file=sys.stderr, flush=True)
    require(set(groups) == {(target, arm) for target in targets for arm in COMPONENT_ARMS},
            "prediction_group_inventory_invalid", f"groups={len(groups)}")
    expected_files.update(predictions.values())
    prediction_dir = run / "predictions"
    require(prediction_dir.is_dir(), "missing_directory", str(prediction_dir))
    prediction_entries = list(prediction_dir.iterdir())
    require(all(path.is_file() and not path.is_symlink() for path in prediction_entries)
            and {f"predictions/{path.name}" for path in prediction_entries} == set(predictions.values()),
            "prediction_directory_inventory_mismatch", str(prediction_dir))
    require(set(closure_files) == expected_files, "closure_file_inventory_invalid",
            f"missing={sorted(expected_files-set(closure_files))[:5]}; extra={sorted(set(closure_files)-expected_files)[:5]}")
    for relative, expected in closure_files.items():
        checked_file(run, relative, expected, label="closure_artifact")

    seed_score_files = 0
    for target_index, target in enumerate(targets):
        prediction_path = checked_file(run, predictions[target], closure_files[predictions[target]], label="closed_prediction")
        try:
            with np.load(prediction_path, allow_pickle=False) as payload:
                require(set(payload.files) == set(ALL_ARMS), "closed_arm_inventory_invalid", target)
                closed = {arm: validate_vector(np.array(payload[arm], copy=True), domain_rows,
                                               f"closed:{target}:{arm}") for arm in ALL_ARMS}
        except AuditError:
            raise
        except Exception as exc:
            raise AuditError("npz_read_failed", f"{prediction_path}: {exc}") from exc
        for arm in COMPONENT_ARMS:
            group = sorted(groups[(target, arm)], key=lambda task: task["seed_label"])
            require(group and len({task["seed_label"] for task in group}) == len(group),
                    "seed_group_invalid", f"{target}:{arm}")
            arrays = [load_scores(run / f"fits/{task['id']}/scores.npz", domain_rows,
                                  f"seed:{task['id']}") for task in group]
            seed_score_files += len(arrays)
            expected = np.mean(np.stack(arrays), axis=0, dtype=np.float64)
            require(np.array_equal(closed[arm], expected), "closed_seed_mean_mismatch", f"{target}:{arm}")
        expected_ensemble = 0.5 * closed[NEURAL_ARMS[3]] + 0.5 * closed[CONVENTIONAL_ARMS[0]]
        require(np.array_equal(closed[ENSEMBLE], expected_ensemble), "closed_ensemble_mismatch", target)
        if progress and (target_index + 1) % 10 == 0:
            print(f"recomputed closed predictions {target_index+1}/{len(targets)}", file=sys.stderr, flush=True)

    require_hash_cache_stable()
    result = {
        "schema_version": SCHEMA,
        "status": "pass",
        "started_utc": started,
        "completed_utc": utc_now(),
        "auditor": {"path": str(Path(__file__).resolve()), "sha256": script_hash,
                    "python": sys.version.split()[0], "numpy": np.__version__},
        "root": str(root),
        "run": str(run),
        "provenance": {
            "plan_sha256": plan_sha,
            "plan_digest": plan["plan_digest"],
            "domain_sha256": plan["domain_file_sha256"],
            "closure_sha256": closure_sha,
            "closure_digest": closure["closure_digest"],
            "source_hashes_digest": canonical_digest(dict(sources)),
            "input_hashes_digest": canonical_digest(dict(inputs)),
        },
        "verified": {
            "source_files": len(sources), "input_files": len(inputs),
            "tasks": len(tasks), "task_counts": counts, "fit_receipts": len(tasks),
            "qualification_receipts": len(qualifications), "seed_score_files_recomputed": seed_score_files,
            "targets": len(targets), "component_arms": len(COMPONENT_ARMS),
            "ensemble_arms": 1, "domain_rows_per_arm": domain_rows,
            "closure_files": len(closure_files), "hashed_files": len(_HASH_CACHE),
            "hashed_bytes": sum(signature[1] for signature, _ in _HASH_CACHE.values()),
            "pre_score_absence": True, "outer_response_content_opened": False,
        },
    }
    return result


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        np.savez_compressed(stream, **arrays)


def _build_synthetic_fixture(base: Path) -> tuple[Path, Path, dict[str, int]]:
    root, run = base / "root", base / "run"
    root.mkdir(parents=True); run.mkdir(parents=True)
    (root / "source.py").write_text("synthetic source\n")
    (root / "input.dat").write_bytes(b"synthetic input\n")
    rows, target = 3, "Synthetic species"
    cell_ids = np.array(["c0", "c1", "c2"])
    regions = np.array(["NCP", "SEH", "NNC"])
    x = np.arange(rows * EXPECTED_FEATURES, dtype=np.float64).reshape(rows, EXPECTED_FEATURES) / 1000.0
    longitude = np.array([140.0, 141.0, 142.0]); latitude = np.array([-30.0, -31.0, -32.0])
    block_x = np.array([1, 2, 3], dtype=np.int64); block_y = np.array([4, 5, 6], dtype=np.int64)
    _write_npz(run / "domain.npz", cell_ids=cell_ids, regions=regions, x=x,
               longitude=longitude, latitude=latitude, block_x=block_x, block_y=block_y)
    domain = {
        "schema_version": "goal052-outer-predictors-v1", "rows": rows,
        "rows_by_region": {region: 1 for region in ("NCP", "SEH", "NNC")},
        "feature_count": EXPECTED_FEATURES, "feature_dtype": "float64",
        "cell_id_sha256": hashlib.sha256(("\n".join(cell_ids.tolist()) + "\n").encode()).hexdigest(),
        "region_sha256": hashlib.sha256(("\n".join(regions.tolist()) + "\n").encode()).hexdigest(),
        "encoded_sha256": hashlib.sha256(x.tobytes()).hexdigest(),
        "input_sha256": {"config": sha256_file(root / "input.dat"), "manifest": sha256_file(root / "input.dat"),
                         "transforms": sha256_file(root / "input.dat"), "ledger": sha256_file(root / "input.dat"),
                         "predictors": sha256_file(root / "input.dat")},
    }
    tasks: list[dict[str, Any]] = []
    tasks.append({"kind": "q", "block": 0, "seed": 11, "id": "q.block00"})
    for seed_index, label in enumerate(("seed00", "seed01")):
        task = {"kind": "pretraining", "block": 0, "seed_label": label, "seed": 20 + seed_index, "epochs": 2}
        tasks.append({**task, "id": task_id(task)})
    for arm_index, arm in enumerate(NEURAL_ARMS):
        for seed_index, label in enumerate(("seed00", "seed01")):
            task = {"kind": "neural", "target": target, "block": 0, "arm": arm,
                    "seed_label": label, "seed": 100 + seed_index, "epochs": 2}
            tasks.append({**task, "id": task_id(task)})
    for arm_index, arm in enumerate(CONVENTIONAL_ARMS):
        for seed_index, label in enumerate(("seed00", "seed01")):
            task = {"kind": "conventional", "target": target, "block": 0, "arm": arm,
                    "family": "random_forest", "candidate_id": "rf02", "seed_label": label,
                    "seed": 200 + seed_index, "epochs": None}
            tasks.append({**task, "id": task_id(task)})
    counts = dict(Counter(task["kind"] for task in tasks))
    base_target_data = {"row_digest": "r" * 64, "cell_id_digest": "c" * 64, "rows": 5,
                        "folds_digest": "f" * 64, "q_scaling": None}
    auxiliary = {"heads": ["h1", "h2"], "rows": 8, "excluded_species": ["held"], "row_digest": "a" * 64}
    plan = {
        "schema_version": PLAN_SCHEMA,
        "sources": {"source.py": sha256_file(root / "source.py")},
        "inputs": {"input.dat": sha256_file(root / "input.dat")},
        "tasks": tasks, "targets": [target],
        "thresholds": {target: {arm: 0.5 for arm in COMPONENT_ARMS}},
        "panels": {"primary": [target], "regional": {region: [target] for region in ("NCP", "SEH", "NNC")}},
        "x20_targets": {region: [target] for region in ("NCP", "SEH", "NNC")},
        "target_rows": {target: base_target_data}, "auxiliary_rows": {"0": auxiliary},
        "domain": domain, "domain_file_sha256": sha256_file(run / "domain.npz"),
        "batch_size": 128, "full_fold_sentinel": FULL_FOLD, "outer_response_rows_read": 0,
    }
    plan["plan_digest"] = canonical_digest(plan); plan["created_utc"] = utc_now()
    _write_json(run / "plan.json", plan)
    canary_rel, profile_rel = "qualification/canary.json", "qualification/profile.json"
    science = {"status": "canary_repeat_valid", "targets": {"a": {"score_digest": "d" * 64}}}
    canary = {"schema_version": RUNTIME_SCHEMA, "status": CANARY_STATUS, "plan_digest": plan["plan_digest"],
              "runtime_fingerprint": "9" * 64, "code_hashes": plan["sources"], "workers_tested": 2,
              "deterministic_repeats": True, "repeats": [{**science, "repeat": 0, "pid": 101, "runtime_seconds": 1.0},
                                                           {**science, "repeat": 1, "pid": 102, "runtime_seconds": 2.0}],
              "outer_response_rows_read": 0}
    profile = {"schema_version": RUNTIME_SCHEMA, "status": PROFILE_STATUS, "plan_digest": plan["plan_digest"],
               "runtime_fingerprint": "9" * 64, "code_hashes": plan["sources"], "qualified_workers": 2,
               "peak_rss_bytes": 1000, "outer_response_rows_read": 0}
    _write_json(run / canary_rel, canary); _write_json(run / profile_rel, profile)
    final = {"schema_version": RUNTIME_SCHEMA, "status": QUALIFIED_STATUS, "plan_digest": plan["plan_digest"],
             "runtime_fingerprint": "9" * 64, "qualified_workers": 2, "canary_workers_tested": 2,
             "canary": canary_rel, "profile": profile_rel,
             "canary_sha256": sha256_file(run / canary_rel), "profile_sha256": sha256_file(run / profile_rel),
             "outer_response_rows_read": 0}
    final["files"] = {canary_rel: final["canary_sha256"], profile_rel: final["profile_sha256"]}
    qualification_rel = "qualification/final.json"; _write_json(run / qualification_rel, final)
    qualification_sha = sha256_file(run / qualification_rel)
    pre_shared = {"seed00": "1" * 64, "seed01": "2" * 64}
    seed_values: dict[tuple[str, str], np.ndarray] = {}
    for task_index, task in enumerate(tasks):
        directory = run / "fits" / task["id"]; directory.mkdir(parents=True)
        kind = task["kind"]
        dependencies = {}
        data: dict[str, Any] = {}
        if kind == "q":
            _write_npz(directory / "model.npz", coefficient=np.array([1.0]), intercept=np.array([0.0]))
            files = ["model.npz"]
            q_values = np.concatenate([np.asarray([1.0], dtype="<f8"), np.asarray([0.0], dtype="<f8")])
            fit = {"fit_seed": task["seed"], "candidate_id": "enet04", "held_block": 0, "held_fold": FULL_FOLD,
                   "auxiliary_size": "full", "heads": auxiliary["heads"], "expanded_rows": auxiliary["rows"],
                   "held_species": auxiliary["excluded_species"],
                   "parameter_digest": hashlib.sha256(q_values.tobytes()).hexdigest()}
        elif kind == "pretraining":
            (directory / "model.pt").write_bytes(b"model"); (directory / "shared.pt").write_bytes(b"shared")
            files = ["model.pt", "shared.pt"]; data = dict(auxiliary)
            fit = {"seed": task["seed"], "replay_shuffle_seed": task["seed"] + 100_000,
                   "epochs": task["epochs"], "completed_epochs": task["epochs"], "batch_size": 128,
                   "fit_mode": "fixed_budget", "early_stopping": False, "discovery_rows": 0, "stopping_rows": 0,
                   "state_finite": True, "transferred": False, "final_shared_digest": pre_shared[task["seed_label"]]}
        else:
            augmented = task["arm"] in (NEURAL_ARMS[1], CONVENTIONAL_ARMS[1])
            data = dict(base_target_data)
            if augmented:
                data["q_scaling"] = {"training_mean": 0.1, "training_population_sd": 1.2}
                dependencies["q.block00"] = sha256_file(run / "fits/q.block00/receipt.json")
            values = np.array([0.1 + task_index / 1000, 0.5, 0.9 - task_index / 1000], dtype=np.float64)
            _write_npz(directory / "scores.npz", scores=values)
            seed_values[(task["id"], task["arm"])] = values
            if kind == "neural":
                (directory / "model.pt").write_bytes(b"model")
                files = ["model.pt", "scores.npz", "fit-input.json"]
                transferred = task["arm"] in NEURAL_ARMS[2:]; frozen = task["arm"] == NEURAL_ARMS[2]
                if transferred:
                    dependency = f"pretraining.block00.{task['seed_label']}"
                    dependencies[dependency] = sha256_file(run / f"fits/{dependency}/receipt.json")
                initial = pre_shared.get(task["seed_label"]) if transferred else None
                final_shared = initial if frozen else ("3" * 64 if transferred else None)
                fit = {"seed": task["seed"], "replay_shuffle_seed": task["seed"] + 100_000,
                       "epochs": task["epochs"], "completed_epochs": task["epochs"], "batch_size": 128,
                       "fit_mode": "fixed_budget", "early_stopping": False, "discovery_rows": 0, "stopping_rows": 0,
                       "state_finite": True, "head_initialization_seed": task["seed"] + 17,
                       "transferred": transferred, "freeze_trunk": frozen,
                       "transfer_digest": initial, "initial_shared_digest": initial, "final_shared_digest": final_shared,
                       "freeze_shared_state_invariant": True if frozen else None,
                       "save_reload_predictions_exact": True}
            else:
                (directory / "model.json").write_text("{}\n")
                files = ["model.json", "scores.npz", "fit-input.json"]
                fit = {"converged": True, "seed": task["seed"], "family": task["family"],
                       "candidate_id": task["candidate_id"], "save_reload_predictions_exact": True}
            fit_input = {"plan_digest": plan["plan_digest"], "task": task, "data": data, "dependencies": dependencies}
            _write_json(directory / "fit-input.json", fit_input)
        receipt = {"status": "outer_fit_complete", "plan_digest": plan["plan_digest"], "task": task,
                   "qualification": qualification_rel, "qualification_sha256": qualification_sha,
                   "data": data, "dependencies": dependencies, "fit": fit, "outer_response_rows_read": 0,
                   "files": {name: sha256_file(directory / name) for name in files}}
        _write_json(directory / "receipt.json", receipt)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        if task["kind"] in ("neural", "conventional"):
            groups[task["arm"]].append(task)
    closed: dict[str, np.ndarray] = {}
    for arm in COMPONENT_ARMS:
        arrays = [load_scores(run / f"fits/{task['id']}/scores.npz", rows, task["id"])
                  for task in sorted(groups[arm], key=lambda item: item["seed_label"])]
        closed[arm] = np.mean(np.stack(arrays), axis=0, dtype=np.float64)
    closed[ENSEMBLE] = 0.5 * closed[NEURAL_ARMS[3]] + 0.5 * closed[CONVENTIONAL_ARMS[0]]
    prediction_rel = f"predictions/{slug(target)}.npz"; _write_npz(run / prediction_rel, **closed)
    files = {"plan.json": sha256_file(run / "plan.json"), "domain.npz": sha256_file(run / "domain.npz")}
    for task in tasks:
        rel = f"fits/{task['id']}"; receipt = read_json(run / rel / "receipt.json")
        files[f"{rel}/receipt.json"] = sha256_file(run / rel / "receipt.json")
        files.update({f"{rel}/{name}": checksum for name, checksum in receipt["files"].items()})
    files[qualification_rel] = qualification_sha; files.update(final["files"])
    files[prediction_rel] = sha256_file(run / prediction_rel)
    closure = {"schema_version": CLOSURE_SCHEMA, "status": CLOSURE_STATUS, "created_utc": utc_now(),
               "plan_digest": plan["plan_digest"], "fit_counts": counts, "files": files,
               "predictions": {target: prediction_rel}, "thresholds": plan["thresholds"],
               "domain": plan["domain"], "outer_response_rows_read": 0}
    closure["closure_digest"] = canonical_digest(closure); _write_json(run / "closure.json", closure)
    return root, run, counts


def _rewrite_closed_prediction(run: Path, mutate: Callable[[dict[str, np.ndarray]], None]) -> None:
    closure = read_json(run / "closure.json")
    relative = next(iter(closure["predictions"].values()))
    with np.load(run / relative, allow_pickle=False) as payload:
        arrays = {key: np.array(payload[key], copy=True) for key in payload.files}
    mutate(arrays); _write_npz(run / relative, **arrays)
    closure["files"][relative] = sha256_file(run / relative)
    closure["closure_digest"] = canonical_digest({key: value for key, value in closure.items() if key != "closure_digest"})
    _write_json(run / "closure.json", closure)


def self_test() -> dict[str, Any]:
    cases: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="dsdm-outer-independent-audit-") as temporary:
        base = Path(temporary)
        valid = base / "valid"
        root, run, counts = _build_synthetic_fixture(valid)
        result = audit_run(root, run, production=False, expected_counts=counts, expected_targets=1, expected_rows=3, progress=False)
        require(result["status"] == "pass", "self_test_valid_fixture_failed", "")
        cases.append({"case": "valid_fixture", "status": "pass"})
        mutations: list[tuple[str, str, Callable[[Path, Path], None]]] = [
            ("missing_model", "missing_file", lambda r, u: next((u / "fits").glob("conventional.*/model.json")).unlink()),
            ("source_drift", "file_hash_mismatch", lambda r, u: (r / "source.py").write_text("changed\n")),
            ("qualification_tamper", "file_hash_mismatch", lambda r, u: (u / "qualification/canary.json").write_text("{}\n")),
            ("wrong_seed_mean", "closed_seed_mean_mismatch",
             lambda r, u: _rewrite_closed_prediction(u, lambda arrays: arrays[CONVENTIONAL_ARMS[0]].__setitem__(0, arrays[CONVENTIONAL_ARMS[0]][0] + 0.01))),
            ("wrong_ensemble", "closed_ensemble_mismatch",
             lambda r, u: _rewrite_closed_prediction(u, lambda arrays: arrays[ENSEMBLE].__setitem__(0, arrays[ENSEMBLE][0] + 0.01))),
        ]
        for name, expected_code, mutation in mutations:
            case = base / name; shutil.copytree(valid, case)
            case_root, case_run = case / "root", case / "run"
            mutation(case_root, case_run)
            try:
                audit_run(case_root, case_run, production=False, expected_counts=counts,
                          expected_targets=1, expected_rows=3, progress=False)
            except AuditError as exc:
                require(exc.code == expected_code, "self_test_wrong_failure",
                        f"{name}: expected={expected_code}; observed={exc.code}")
                cases.append({"case": name, "status": "pass", "observed_failure": exc.code})
            else:
                raise AuditError("self_test_mutation_not_detected", name)
    return {"schema_version": SCHEMA, "status": "self_test_pass", "cases": cases}


def emit(value: Mapping[str, Any], output: Path | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--run", type=Path, help="Closed outer run directory")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress messages on stderr")
    parser.add_argument("--self-test", action="store_true", help="Run synthetic pass/failure fixtures")
    args = parser.parse_args(argv)
    started = utc_now()
    try:
        if args.self_test:
            result = self_test()
        else:
            require(args.run is not None, "run_argument_required", "--run is required")
            result = audit_run(args.root, args.run, progress=not args.quiet)
        emit(result, args.output)
        return 0
    except AuditError as exc:
        failure = {"schema_version": SCHEMA, "status": "fail", "started_utc": started,
                   "completed_utc": utc_now(), "failure": {"code": exc.code, "detail": exc.detail},
                   "auditor_sha256": sha256_file(Path(__file__).resolve())}
        emit(failure, args.output)
        return 1
    except Exception as exc:
        failure = {"schema_version": SCHEMA, "status": "error", "started_utc": started,
                   "completed_utc": utc_now(), "failure": {"code": "unexpected_exception",
                   "detail": f"{type(exc).__name__}: {exc}"},
                   "auditor_sha256": sha256_file(Path(__file__).resolve())}
        emit(failure, args.output)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
