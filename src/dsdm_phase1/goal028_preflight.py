"""Goal028 leakage-safe execution, publication, and semantic replay.

Synthetic and real preflight modes use the same explicit-plan engine.  The
engine consumes only an already-authorised outer-training broker/provider and
a vault, runs the Tasks 4--6 OOF/refit machinery, serializes the fitted model
that produced each replay receipt, and validates a complete staged pair before
publication.  No real mode opens or scores the outer vault.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .inner_cv import (
    CandidateOOF,
    FoldOOF,
    SelectionStratum,
    refit_outer_training,
    replay_predictions,
    run_candidate_oof,
    select_candidate,
)
from .model_adapters import CANONICAL_CANDIDATES, build_adapter, load_fitted_model
from .modeling_contract import (
    FeatureProvider,
    MappingFeatureSubstrate,
    ModelingContractError,
    OuterVault,
    RowKey,
    RowSet,
    SplitBroker,
    TaskKey,
    canonical_json,
    derive_seed,
    ingest_private_foundation,
    ingest_synthetic_foundation,
    load_run_config,
    task_id,
)
from .target_subsets import SubsetEndpoint, build_ladders


FOLDS = tuple(f"fold{i:02d}" for i in range(5))
ENDPOINTS = (
    ("fraction25", "ladder00"),
    ("fraction25", "ladder01"),
    ("fraction25", "ladder02"),
    ("fraction50", "ladder00"),
    ("fraction50", "ladder01"),
    ("fraction50", "ladder02"),
    ("fraction100", "full"),
)
REAL_SPECIES = ("sarcophilus_harrisii", "pseudocheirus_peregrinus")
REAL_IDS = (
    "null00", "enet03", "enet07", "gam01", "rf03", "hgb03",
    "ann03", "resmlp01", "resmlp02",
)
SYNTHETIC_FULL_IDS = ("enet03", "gam02", "rf03", "hgb03", "ann03", "resmlp01")
TRACKED_NAMES = (
    "bindings.json", "contract.json", "preflight_summary.json",
    "runtime_summary.json", "review.json", "manifest.json",
)
PRIVATE_NAMES = ("tasks.parquet", "oof.parquet", "subsets.parquet", "run.json", "models")


TASK_SCHEMA = pa.schema([
    pa.field("schema_version", pa.string(), nullable=False),
    pa.field("run_id", pa.string(), nullable=False),
    pa.field("task_id", pa.string(), nullable=False),
    pa.field("task_digest", pa.string(), nullable=False),
    pa.field("config_digest", pa.string(), nullable=False),
    pa.field("git_commit", pa.string(), nullable=False),
    pa.field("species_id", pa.string(), nullable=False),
    pa.field("transform_id", pa.string(), nullable=False),
    pa.field("cv_fold", pa.string(), nullable=False),
    pa.field("fraction_id", pa.string(), nullable=False),
    pa.field("ladder_id", pa.string(), nullable=False),
    pa.field("subset_digest", pa.string(), nullable=False),
    pa.field("model_family", pa.string(), nullable=False),
    pa.field("candidate_id", pa.string(), nullable=False),
    pa.field("seed_label", pa.string(), nullable=False),
    pa.field("seed_uint32", pa.uint32(), nullable=False),
    pa.field("pair_id", pa.string(), nullable=False),
    pa.field("synthetic", pa.bool_(), nullable=False),
    pa.field("n_train", pa.int64(), nullable=False),
    pa.field("n_validation", pa.int64(), nullable=False),
    pa.field("train_positive", pa.int64(), nullable=False),
    pa.field("train_zero_survey", pa.int64(), nullable=False),
    pa.field("train_zero_pseudoabsence", pa.int64(), nullable=False),
    pa.field("validation_positive", pa.int64(), nullable=False),
    pa.field("validation_zero_survey", pa.int64(), nullable=False),
    pa.field("validation_zero_pseudoabsence", pa.int64(), nullable=False),
    pa.field("feature_transform_id", pa.string(), nullable=False),
    pa.field("transform_digest", pa.string(), nullable=False),
    pa.field("encoder_digest", pa.string(), nullable=False),
    pa.field("feature_schema_digest", pa.string(), nullable=False),
    pa.field("unseen_level_counts", pa.string(), nullable=False),
    pa.field("stopping_fold", pa.string(), nullable=False),
    pa.field("best_epochs_by_fold", pa.string(), nullable=False),
    pa.field("best_epoch", pa.int64()),
    pa.field("initial_state_digest", pa.string(), nullable=False),
    pa.field("discovery_initial_state_digest", pa.string(), nullable=False),
    pa.field("replay_initial_state_digest", pa.string(), nullable=False),
    pa.field("neural_stop_status", pa.string(), nullable=False),
    pa.field("outer_attempted_open_count", pa.int64(), nullable=False),
    pa.field("outer_open_count", pa.int64(), nullable=False),
    pa.field("convergence_status", pa.string(), nullable=False),
    pa.field("epochs_or_iterations", pa.int64(), nullable=False),
    pa.field("warnings", pa.string(), nullable=False),
    pa.field("runtime_seconds", pa.float64(), nullable=False),
    pa.field("peak_rss_bytes", pa.int64(), nullable=False),
    pa.field("package_versions", pa.string(), nullable=False),
    pa.field("python_version", pa.string(), nullable=False),
    pa.field("platform", pa.string(), nullable=False),
    pa.field("model_path", pa.string(), nullable=False),
    pa.field("model_sha256", pa.string(), nullable=False),
    pa.field("oof_path", pa.string(), nullable=False),
    pa.field("oof_sha256", pa.string(), nullable=False),
    pa.field("publication_state", pa.string(), nullable=False),
    pa.field("selected", pa.bool_(), nullable=False),
    pa.field("selection_rank", pa.int64(), nullable=False),
    pa.field("mean_fold_roc_auc", pa.float64(), nullable=False),
    pa.field("mean_fold_tss_at_oof_threshold", pa.float64(), nullable=False),
    pa.field("threshold", pa.float64(), nullable=False),
    pa.field("oof_score_digest", pa.string(), nullable=False),
    pa.field("replay_score_digest", pa.string(), nullable=False),
    pa.field("fake_vault_authorized", pa.bool_(), nullable=False),
])

OOF_SCHEMA = pa.schema([
    pa.field("task_id", pa.string(), nullable=False),
    pa.field("record_kind", pa.string(), nullable=False),
    pa.field("fold_id", pa.string(), nullable=False),
    pa.field("row_index", pa.int64(), nullable=False),
    pa.field("row_key", pa.string(), nullable=False),
    pa.field("y_true", pa.int8(), nullable=False),
    pa.field("seed_label", pa.string(), nullable=False),
    pa.field("score", pa.float64(), nullable=False),
    pa.field("mean_score", pa.float64(), nullable=False),
    pa.field("fold_roc_auc", pa.float64()),
    pa.field("threshold", pa.float64(), nullable=False),
    pa.field("fold_tss", pa.float64()),
    pa.field("transform_id", pa.string(), nullable=False),
    pa.field("transform_digest", pa.string(), nullable=False),
    pa.field("encoder_digest", pa.string(), nullable=False),
    pa.field("feature_schema_digest", pa.string(), nullable=False),
    pa.field("unseen_level_counts", pa.string(), nullable=False),
])

SUBSET_SCHEMA = pa.schema([
    pa.field("task_id", pa.string(), nullable=False),
    pa.field("membership_kind", pa.string(), nullable=False),
    pa.field("split_id", pa.string(), nullable=False),
    pa.field("fraction_id", pa.string(), nullable=False),
    pa.field("ladder_id", pa.string(), nullable=False),
    pa.field("subset_digest", pa.string(), nullable=False),
    pa.field("row_key", pa.string(), nullable=False),
    pa.field("rank", pa.int64(), nullable=False),
])


@dataclass(frozen=True)
class _TaskExecution:
    task: TaskKey
    result: CandidateOOF
    runtime_seconds: float
    peak_rss_bytes: int


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _table_from_rows(rows: Sequence[Mapping[str, Any]], schema: pa.Schema) -> pa.Table:
    names = set(schema.names)
    if any(set(row) != names for row in rows):
        raise ModelingContractError("private_schema_fields_mismatch")
    return pa.Table.from_pylist([dict(row) for row in rows], schema=schema)


def _row_token(key: RowKey) -> str:
    return f"{key.species_id}\x1f{key.grid_cell_id}"


def _parse_row_token(value: str) -> RowKey:
    parts = value.split("\x1f")
    if len(parts) != 2 or not all(parts):
        raise ModelingContractError("private_row_key_invalid")
    return RowKey(*parts)


def _endpoint_lookup(rows: RowSet, fraction_id: str, ladder_id: str) -> SubsetEndpoint:
    lookup = "ladder00" if fraction_id == "fraction100" else ladder_id
    return build_ladders(rows)[(fraction_id, lookup)]


def _rowset_for_keys(rows: RowSet, keys: Sequence[RowKey]) -> RowSet:
    lookup = {key: i for i, key in enumerate(rows.keys)}
    if len(set(keys)) != len(keys) or any(key not in lookup for key in keys):
        raise ModelingContractError("endpoint_key_not_in_training")
    return rows.take([lookup[key] for key in keys])


def _source_counts(rows: RowSet) -> dict[str, int]:
    return {
        "positive": int(np.sum(rows.pa == 1)),
        "zero_survey": sum(source == "survey_supported_absence" for source in rows.response_source),
        "zero_pseudoabsence": sum(source == "pseudoabsence" for source in rows.response_source),
    }


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _enforce_task_budget(elapsed: float, peak_rss_bytes: int, config: Mapping[str, Any]) -> None:
    if elapsed > float(config["compute"]["task_wall_budget_seconds"]):
        raise ModelingContractError("task_wall_budget_overrun")
    if peak_rss_bytes > int(config["compute"]["peak_rss_budget_bytes"]):
        raise ModelingContractError("task_rss_budget_overrun")


def _git_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    value = result.stdout.strip()
    return value if len(value) == 40 else "unknown"


def _synthetic_task_plan(species: Sequence[str]) -> tuple[TaskKey, ...]:
    if tuple(species) != REAL_SPECIES:
        raise ModelingContractError("synthetic_species_scope_drift")
    out: list[TaskKey] = []
    for species_id in species:
        for fraction_id, ladder_id in ENDPOINTS:
            out.append(TaskKey(species_id, "outer", fraction_id, ladder_id, "intercept", "null00", "seed00"))
        for candidate_id in SYNTHETIC_FULL_IDS:
            candidate = CANONICAL_CANDIDATES[candidate_id]
            out.append(TaskKey(species_id, "outer", "fraction100", "full", candidate["family"], candidate_id, "seed00"))
    return tuple(out)


def _real_task_plan(config: Mapping[str, Any]) -> tuple[TaskKey, ...]:
    _validate_real_scope(config)
    out: list[TaskKey] = []
    for species_id in REAL_SPECIES:
        for fraction_id, ladder_id in ENDPOINTS:
            out.append(TaskKey(species_id, "outer", fraction_id, ladder_id, "intercept", "null00", "seed00"))
        for fraction_id, ladder_id in (("fraction25", "ladder00"), ("fraction100", "full")):
            for candidate_id in REAL_IDS[1:]:
                candidate = CANONICAL_CANDIDATES[candidate_id]
                out.append(TaskKey(species_id, "outer", fraction_id, ladder_id, candidate["family"], candidate_id, "seed00"))
    return tuple(out)


def _synthetic_fixture() -> tuple[
    list[dict[str, Any]], dict[RowKey, Any], dict[RowKey, str], OuterVault, FeatureProvider
]:
    rows: list[dict[str, Any]] = []
    values: dict[RowKey, Any] = {}
    folds: dict[RowKey, str] = {}
    held_rows: list[dict[str, Any]] = []
    held_values: dict[RowKey, Any] = {}
    for species_index, species_id in enumerate(REAL_SPECIES):
        for i in range(30):
            key = RowKey(species_id, f"syn_{species_index}_{i:03d}")
            positive = int((i + species_index) % 3 == 0)
            source = "presence" if positive else (
                "survey_supported_absence" if (i + species_index) % 2 else "pseudoabsence"
            )
            rows.append({
                "species_id": species_id, "grid_cell_id": key.grid_cell_id,
                "pa": positive, "pa_type": source,
                "microcluster": f"mc{(i + species_index) % 4}",
            })
            continuous = [
                float(np.sin((i + 1) * (j + 1) / 13.0) + positive * 0.2)
                for j in range(25)
            ]
            # This level occurs only in assessment fold04 and is therefore
            # unseen by that fold's complete E_v encoder.
            region = "unseen_validation" if i == 4 else ("north" if i % 2 else "south")
            values[key] = {
                "continuous": continuous,
                "categorical": {
                    "bioregion": region,
                    "substrate": f"s{(i + species_index) % 2}",
                    "season": f"q{(i + species_index) % 3}",
                },
            }
            folds[key] = f"fold{i % 5:02d}"
        for i in range(10):
            key = RowKey(species_id, f"held_{species_index}_{i:03d}")
            positive = int((i + species_index) % 2)
            source = "presence" if positive else (
                "survey_supported_absence" if i % 3 else "pseudoabsence"
            )
            held_rows.append({
                "species_id": species_id, "grid_cell_id": key.grid_cell_id,
                "pa": positive, "pa_type": source, "microcluster": f"held_mc{i % 3}",
            })
            held_values[key] = {
                "continuous": [
                    float(np.cos((i + 2) * (j + 1) / 17.0)) for j in range(25)
                ],
                "categorical": {
                    "bioregion": "held_unseen" if i == 0 else ("north" if i % 2 else "south"),
                    "substrate": f"s{i % 2}", "season": f"q{i % 3}",
                },
            }
    held = RowSet.from_records(held_rows)
    vault = OuterVault.synthetic(held_rows)
    fake_provider = FeatureProvider(MappingFeatureSubstrate(held_values), frozenset(held.keys))
    return rows, values, folds, vault, fake_provider


def _candidate_oof_rows(
    execution: _TaskExecution,
    broker: SplitBroker,
    provider: FeatureProvider,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task = execution.task
    rows: list[dict[str, Any]] = []
    subsets: list[dict[str, Any]] = []
    row_index = 0
    for fold_result in execution.result.folds:
        cv_train, assessment = broker.inner(task.species_id, fold_result.fold_id)
        endpoint = _endpoint_lookup(cv_train, task.fraction_id, task.ladder_id)
        endpoint_rows = _rowset_for_keys(cv_train, endpoint.keys)
        transform_id = f"cv_{fold_result.fold_id}"
        encoder = provider.fit_encoder(endpoint_rows, task.model_family, transform_id)
        batch = provider.materialize(assessment, transform_id, encoder)
        for rank, key in enumerate(endpoint.keys):
            subsets.append({
                "task_id": task_id(task), "membership_kind": "oof_train_endpoint",
                "split_id": transform_id, "fraction_id": task.fraction_id,
                "ladder_id": task.ladder_id, "subset_digest": endpoint.subset_digest,
                "row_key": _row_token(key), "rank": rank,
            })
        for index, key in enumerate(fold_result.keys):
            rows.append({
                "task_id": task_id(task), "record_kind": "oof",
                "fold_id": fold_result.fold_id, "row_index": row_index,
                "row_key": _row_token(key), "y_true": int(fold_result.y_true[index]),
                "seed_label": task.seed_label,
                "score": float(fold_result.scores_by_seed[task.seed_label][index]),
                "mean_score": float(fold_result.mean_score[index]),
                "fold_roc_auc": float(fold_result.roc_auc),
                "threshold": float(execution.result.threshold),
                "fold_tss": float(fold_result.tss_at_oof_threshold),
                "transform_id": transform_id,
                "transform_digest": batch.transform_digest,
                "encoder_digest": batch.encoder_digest,
                "feature_schema_digest": batch.feature_schema_digest,
                "unseen_level_counts": canonical_json(dict(batch.unseen_level_counts)),
            })
            row_index += 1
    outer = broker.outer_training(task.species_id)
    endpoint = _endpoint_lookup(outer, task.fraction_id, task.ladder_id)
    for rank, key in enumerate(endpoint.keys):
        subsets.append({
            "task_id": task_id(task), "membership_kind": "outer_refit_endpoint",
            "split_id": "outer", "fraction_id": task.fraction_id,
            "ladder_id": task.ladder_id, "subset_digest": endpoint.subset_digest,
            "row_key": _row_token(key), "rank": rank,
        })
    return rows, subsets


def _selection_groups(executions: Sequence[_TaskExecution]) -> list[list[_TaskExecution]]:
    groups: dict[tuple[Any, ...], list[_TaskExecution]] = {}
    order: list[tuple[Any, ...]] = []
    for execution in executions:
        task = execution.task
        key = (task.species_id, task.fraction_id, task.ladder_id, task.model_family)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(execution)
    return [groups[key] for key in order]


def _task_digest(row: Mapping[str, Any]) -> str:
    payload = {name: row[name] for name in TASK_SCHEMA.names if name != "task_digest"}
    return _sha(payload)


def _validate_real_scope(config: Mapping[str, Any]) -> None:
    scope = config.get("scope", {})
    if tuple(scope.get("real_species", ())) != REAL_SPECIES:
        raise ModelingContractError("real_scope_species_drift")
    if tuple(scope.get("permitted_endpoints", ())) != tuple(f"{a}/{b}" for a, b in ENDPOINTS):
        raise ModelingContractError("real_endpoint_scope_drift")
    counts = scope.get("included_row_counts")
    if not isinstance(counts, Mapping) or tuple(counts) != REAL_SPECIES:
        raise ModelingContractError("real_complete_count_scope_drift")
    if scope.get("real_outer_attempted_open_limit") != 0 or scope.get("real_outer_open_limit") != 0:
        raise ModelingContractError("real_scope_outer_unlock")
    if tuple(config.get("models", {}).get("real_preflight_ids", ())) != REAL_IDS:
        raise ModelingContractError("real_candidate_scope_drift")
    if config.get("replication", {}).get("real_preflight_labels") != ["seed00"]:
        raise ModelingContractError("real_seed_scope_drift")
    neural = config.get("neural", {})
    if neural.get("device") != "cpu" or neural.get("diagnostic_seed") != "seed01_only":
        raise ModelingContractError("real_neural_scope_drift")
    compute = config.get("compute", {})
    if (
        compute.get("platform") != "Mac mini CPU"
        or compute.get("estimator_threads") != 1
        or type(compute.get("process_workers")) is not int
        or not 1 <= compute["process_workers"] <= 2
        or type(compute.get("task_wall_budget_seconds")) not in (int, float)
        or compute["task_wall_budget_seconds"] > 1200
        or type(compute.get("peak_rss_budget_bytes")) is not int
        or compute["peak_rss_budget_bytes"] > 12 * 1024**3
        or compute.get("mps_gating") is not False
    ):
        raise ModelingContractError("real_compute_scope_drift")


def _publication_destinations(
    root: Path, config: Mapping[str, Any], synthetic: bool
) -> tuple[Path, Path]:
    private = Path(root) / str(config["artifacts"]["private_destination"])
    evidence = Path(root) / str(config["artifacts"]["aggregate_destination"])
    if synthetic:
        private /= "synthetic"
        evidence /= "synthetic"
    return private, evidence


def _run_seed01_diagnostic(
    task: TaskKey,
    candidate: Mapping[str, Any],
    batch: Any,
    exact_epochs: int,
    stage_private: Path,
    atol: float,
) -> Mapping[str, Any]:
    diagnostic_task = TaskKey(
        task.species_id, task.transform_id, task.fraction_id, task.ladder_id,
        task.model_family, task.candidate_id, "seed01",
    )
    seed = derive_seed(diagnostic_task, "fit")
    first, first_report = build_adapter(task.model_family).fit(
        batch, None, candidate, seed, exact_epochs=exact_epochs
    )
    second, second_report = build_adapter(task.model_family).fit(
        batch, None, candidate, seed, exact_epochs=exact_epochs
    )
    first_scores = first.predict_scores(batch)
    second_scores = second.predict_scores(batch)
    if not np.allclose(first_scores, second_scores, rtol=0.0, atol=atol):
        raise ModelingContractError("seed01_deterministic_pair_mismatch")
    path = stage_private / f".{task_id(diagnostic_task)}.diagnostic.model"
    first.serialize(path)
    trusted = _digest_file(path)
    replay_predictions(path, batch, first_scores, atol, trusted)
    path.unlink()
    return {
        "task_id": task_id(diagnostic_task), "seed_label": "seed01",
        "score_digest": _sha(first_scores.tolist()), "exact_epochs": exact_epochs,
        "first_initial_state_digest": first_report.initial_state_digest,
        "second_initial_state_digest": second_report.initial_state_digest,
        "status": "pass",
    }


def run_preflight_engine(
    *,
    root: Path,
    config: Mapping[str, Any],
    broker: SplitBroker,
    provider: FeatureProvider,
    vault: OuterVault,
    task_plan: Sequence[TaskKey],
    mode: str,
    synthetic: bool,
    private_dir: Path,
    evidence_dir: Path,
    fake_vault_provider: FeatureProvider | None = None,
    authorize_fake_vault: bool = False,
    _require_independent_replay: bool = True,
) -> Mapping[str, Any]:
    """Execute an explicit frozen task plan and publish one validated pair."""
    if mode not in {"synthetic", "real-preflight"} or synthetic != (mode == "synthetic"):
        raise ModelingContractError("engine_mode_mismatch")
    expected_plan = _synthetic_task_plan(REAL_SPECIES) if synthetic else _real_task_plan(config)
    if tuple(task_plan) != expected_plan:
        raise ModelingContractError("frozen_task_plan_mismatch")
    if synthetic != authorize_fake_vault or synthetic != (fake_vault_provider is not None):
        raise ModelingContractError("fake_vault_authorization_mismatch")
    if not synthetic and (vault.attempted_open_count != 0 or vault.open_count != 0):
        raise ModelingContractError("real_outer_access_detected")

    config_digest = _sha(config)
    plan_payload = [asdict(task) for task in task_plan]
    run_id = _sha({"schema_version": "1.0", "mode": mode, "config_digest": config_digest, "plan": plan_payload})
    git_commit = _git_commit(Path(root))
    start_run = time.perf_counter()
    executions: list[_TaskExecution] = []
    oof_rows: list[dict[str, Any]] = []
    subset_rows: list[dict[str, Any]] = []

    for task in task_plan:
        started = time.perf_counter()
        endpoint_by_fold = {
            fold: _endpoint_lookup(
                broker.inner(task.species_id, fold)[0], task.fraction_id, task.ladder_id
            )
            for fold in FOLDS
        }
        result = run_candidate_oof(
            SelectionStratum(
                task.species_id, task.fraction_id, task.ladder_id,
                task.model_family, ("seed00",),
            ),
            FOLDS,
            endpoint_by_fold,
            CANONICAL_CANDIDATES[task.candidate_id],
            broker,
            provider,
            build_adapter(task.model_family),
        )
        elapsed = time.perf_counter() - started
        rss = _peak_rss_bytes()
        _enforce_task_budget(elapsed, rss, config)
        execution = _TaskExecution(task, result, elapsed, rss)
        executions.append(execution)
        candidate_rows, candidate_subsets = _candidate_oof_rows(execution, broker, provider)
        oof_rows.extend(candidate_rows)
        subset_rows.extend(candidate_subsets)

    selected_by_task: dict[str, tuple[_TaskExecution, int]] = {}
    selection_rank: dict[str, int] = {}
    for group in _selection_groups(executions):
        selected = select_candidate([execution.result for execution in group])
        ranked = sorted(
            group,
            key=lambda execution: (
                -execution.result.mean_fold_roc_auc,
                -execution.result.mean_fold_tss_at_oof_threshold,
                execution.task.candidate_id,
            ),
        )
        for rank, execution in enumerate(ranked, start=1):
            selection_rank[task_id(execution.task)] = rank
        chosen = next(execution for execution in group if execution.result is selected)
        selected_by_task[task_id(chosen.task)] = (chosen, 1)

    private_dir = Path(private_dir)
    evidence_dir = Path(evidence_dir)
    stage_parent = private_dir.parent if private_dir.parent.exists() else Path(root)
    stage_root = Path(tempfile.mkdtemp(prefix="goal028-stage-", dir=stage_parent))
    stage_private, stage_evidence = stage_root / "private", stage_root / "evidence"
    stage_private.mkdir()
    stage_evidence.mkdir()
    (stage_private / "models").mkdir()
    selected_meta: dict[str, dict[str, Any]] = {}
    diagnostics: list[Mapping[str, Any]] = []
    try:
        for execution, _ in selected_by_task.values():
            task = execution.task
            candidate = CANONICAL_CANDIDATES[task.candidate_id]
            outer = broker.outer_training(task.species_id)
            endpoint = _endpoint_lookup(outer, task.fraction_id, task.ladder_id)
            endpoint_rows = _rowset_for_keys(outer, endpoint.keys)
            encoder = provider.fit_encoder(endpoint_rows, task.model_family, "outer")
            replay_batch = provider.materialize(endpoint_rows, "outer", encoder)
            fold_epochs = execution.result.neural_epochs_by_seed.get("seed00")
            started = time.perf_counter()
            fitted, report = refit_outer_training(
                task, endpoint, candidate, broker, provider,
                build_adapter(task.model_family), fold_epochs,
            )
            model_rel = f"models/{task_id(task)}.model"
            model_path = stage_private / model_rel
            envelope = fitted.serialize(model_path)
            trusted_sha = _digest_file(model_path)
            expected_scores = fitted.predict_scores(replay_batch)
            replay_predictions(
                model_path, replay_batch, expected_scores,
                float(config["neural"]["score_atol"]), trusted_sha,
            )
            elapsed = execution.runtime_seconds + (time.perf_counter() - started)
            rss = _peak_rss_bytes()
            _enforce_task_budget(elapsed, rss, config)
            for index, (key, score) in enumerate(zip(replay_batch.keys, expected_scores)):
                oof_rows.append({
                    "task_id": task_id(task), "record_kind": "replay",
                    "fold_id": "outer", "row_index": index,
                    "row_key": _row_token(key), "y_true": int(replay_batch.y[index]),
                    "seed_label": "seed00", "score": float(score),
                    "mean_score": float(score), "fold_roc_auc": None,
                    "threshold": float(execution.result.threshold), "fold_tss": None,
                    "transform_id": "outer", "transform_digest": replay_batch.transform_digest,
                    "encoder_digest": replay_batch.encoder_digest,
                    "feature_schema_digest": replay_batch.feature_schema_digest,
                    "unseen_level_counts": canonical_json(dict(replay_batch.unseen_level_counts)),
                })
            selected_meta[task_id(task)] = {
                "model_rel": model_rel,
                "model_sha": trusted_sha,
                "replay_digest": _sha(expected_scores.tolist()),
                "replay_batch": replay_batch,
                "report": report,
                "envelope": envelope,
                "runtime": elapsed,
                "rss": rss,
                "fitted": fitted,
                "encoder": encoder,
            }
            if not synthetic and task.model_family in {"shallow_ann", "residual_mlp"}:
                diagnostics.append(_run_seed01_diagnostic(
                    task, candidate, replay_batch, int(report.iterations), stage_private,
                    float(config["neural"]["score_atol"]),
                ))

        fake_scores: list[dict[str, Any]] = []
        fake_attempted = fake_open = 0
        if synthetic:
            assert fake_vault_provider is not None
            held = vault.open({"synthetic": True})
            fake_attempted, fake_open = vault.attempted_open_count, vault.open_count
            for task_id_value, meta in sorted(selected_meta.items()):
                task = next(task for task in task_plan if task_id(task) == task_id_value)
                held_species = _rowset_for_keys(
                    held, [key for key in held.keys if key.species_id == task.species_id]
                )
                batch = fake_vault_provider.materialize(held_species, "outer", meta["encoder"])
                scores = meta["fitted"].predict_scores(batch)
                fake_scores.append({
                    "task_id": task_id_value, "n": len(scores),
                    "score_digest": _sha(scores.tolist()),
                })
        elif vault.attempted_open_count != 0 or vault.open_count != 0:
            raise ModelingContractError("real_outer_access_detected")

        oof_rows.sort(key=lambda row: (
            row["task_id"], 0 if row["record_kind"] == "oof" else 1,
            row["fold_id"], row["row_index"], row["row_key"],
        ))
        subset_rows.sort(key=lambda row: (
            row["task_id"], row["membership_kind"], row["split_id"], row["rank"], row["row_key"],
        ))
        pq.write_table(_table_from_rows(oof_rows, OOF_SCHEMA), stage_private / "oof.parquet")
        pq.write_table(_table_from_rows(subset_rows, SUBSET_SCHEMA), stage_private / "subsets.parquet")
        oof_sha = _digest_file(stage_private / "oof.parquet")

        task_rows: list[dict[str, Any]] = []
        for execution in executions:
            task = execution.task
            identity = task_id(task)
            outer = broker.outer_training(task.species_id)
            endpoint = _endpoint_lookup(outer, task.fraction_id, task.ladder_id)
            train_rows = _rowset_for_keys(outer, endpoint.keys)
            train_counts = _source_counts(train_rows)
            validation_counts = _source_counts(outer)
            encoder = provider.fit_encoder(train_rows, task.model_family, "outer")
            refit_batch = provider.materialize(train_rows, "outer", encoder)
            chosen = identity in selected_meta
            meta = selected_meta.get(identity, {})
            report = meta.get("report")
            fold_epochs = execution.result.neural_epochs_by_seed.get("seed00")
            receipts = tuple(fold_epochs.receipts) if fold_epochs is not None else tuple()
            best_epoch = (
                sorted(fold_epochs.best_epochs_by_fold)[2]
                if fold_epochs is not None else None
            )
            initial = report.initial_state_digest if report and report.initial_state_digest else ""
            discovery = [receipt.discovery_initial_state_digest for receipt in receipts]
            replay = [receipt.replay_initial_state_digest for receipt in receipts]
            stop_folds = [receipt.stopping_fold for receipt in receipts]
            stop_status = [
                receipt.discovery_report.neural_stop_status for receipt in receipts
            ]
            candidate_oof = [
                row["score"] for row in oof_rows
                if row["task_id"] == identity and row["record_kind"] == "oof"
            ]
            row: dict[str, Any] = {
                "schema_version": "1.0", "run_id": run_id, "task_id": identity,
                "task_digest": "", "config_digest": config_digest,
                "git_commit": git_commit, "species_id": task.species_id,
                "transform_id": task.transform_id, "cv_fold": "all_five",
                "fraction_id": task.fraction_id, "ladder_id": task.ladder_id,
                "subset_digest": endpoint.subset_digest,
                "model_family": task.model_family, "candidate_id": task.candidate_id,
                "seed_label": task.seed_label,
                "seed_uint32": derive_seed(task, "fit"),
                "pair_id": _sha({
                    "run_id": run_id, "species_id": task.species_id,
                    "fraction_id": task.fraction_id, "ladder_id": task.ladder_id,
                    "model_family": task.model_family,
                }),
                "synthetic": synthetic, "n_train": len(train_rows.keys),
                "n_validation": len(outer.keys),
                "train_positive": train_counts["positive"],
                "train_zero_survey": train_counts["zero_survey"],
                "train_zero_pseudoabsence": train_counts["zero_pseudoabsence"],
                "validation_positive": validation_counts["positive"],
                "validation_zero_survey": validation_counts["zero_survey"],
                "validation_zero_pseudoabsence": validation_counts["zero_pseudoabsence"],
                "feature_transform_id": "outer",
                "transform_digest": refit_batch.transform_digest,
                "encoder_digest": refit_batch.encoder_digest,
                "feature_schema_digest": refit_batch.feature_schema_digest,
                "unseen_level_counts": canonical_json(dict(refit_batch.unseen_level_counts)),
                "stopping_fold": canonical_json(stop_folds),
                "best_epochs_by_fold": canonical_json(
                    list(fold_epochs.best_epochs_by_fold) if fold_epochs is not None else []
                ),
                "best_epoch": best_epoch,
                "initial_state_digest": initial,
                "discovery_initial_state_digest": canonical_json(discovery),
                "replay_initial_state_digest": canonical_json(replay),
                "neural_stop_status": canonical_json(stop_status),
                "outer_attempted_open_count": 0, "outer_open_count": 0,
                "convergence_status": (
                    "converged" if chosen and report and report.converged else
                    "oof_complete_not_selected"
                ),
                "epochs_or_iterations": int(report.iterations) if chosen and report else 0,
                "warnings": canonical_json(list(report.warnings) if chosen and report else []),
                "runtime_seconds": float(meta.get("runtime", execution.runtime_seconds)),
                "peak_rss_bytes": int(meta.get("rss", execution.peak_rss_bytes)),
                "package_versions": canonical_json(
                    meta.get("envelope", {}).get("runtime_versions", {})
                ),
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "model_path": str(meta.get("model_rel", "")),
                "model_sha256": str(meta.get("model_sha", "")),
                "oof_path": "oof.parquet", "oof_sha256": oof_sha,
                "publication_state": "staged_validated",
                "selected": chosen, "selection_rank": selection_rank[identity],
                "mean_fold_roc_auc": float(execution.result.mean_fold_roc_auc),
                "mean_fold_tss_at_oof_threshold": float(
                    execution.result.mean_fold_tss_at_oof_threshold
                ),
                "threshold": float(execution.result.threshold),
                "oof_score_digest": _sha(candidate_oof),
                "replay_score_digest": str(meta.get("replay_digest", "")),
                "fake_vault_authorized": synthetic,
            }
            row["task_digest"] = _task_digest(row)
            task_rows.append(row)
        task_rows.sort(key=lambda row: next(
            i for i, task in enumerate(task_plan) if task_id(task) == row["task_id"]
        ))
        pq.write_table(_table_from_rows(task_rows, TASK_SCHEMA), stage_private / "tasks.parquet")

        semantic_payload = [{
            "task_id": row["task_id"], "selected": row["selected"],
            "auc": row["mean_fold_roc_auc"], "tss": row["mean_fold_tss_at_oof_threshold"],
            "threshold": row["threshold"], "oof_score_digest": row["oof_score_digest"],
            "replay_score_digest": row["replay_score_digest"],
        } for row in task_rows]
        semantic_digest = _sha(semantic_payload)
        run_meta = {
            "schema_version": "1.0", "run_id": run_id, "mode": mode,
            "synthetic": synthetic, "config_digest": config_digest,
            "candidate_strata": len(task_rows),
            "selected_model_count": len(selected_meta),
            "oof_row_count": sum(row["record_kind"] == "oof" for row in oof_rows),
            "replay_row_count": sum(row["record_kind"] == "replay" for row in oof_rows),
            "subset_row_count": len(subset_rows),
            "semantic_digest": semantic_digest,
            "task_plan": plan_payload,
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
            "fake_vault_authorized": synthetic,
            "fake_vault_attempted_open_count": fake_attempted,
            "fake_vault_open_count": fake_open,
            "fake_vault_score_receipts": fake_scores,
            "seed01_diagnostics": diagnostics,
        }
        _write_json(stage_private / "run.json", run_meta)

        bindings = {
            role: {"digest": record["sha256"], "status": "verified"}
            for role, record in config["bindings"].items()
            if role != "required_roles"
        }
        bindings["config"] = {"digest": config_digest, "status": "verified"}
        tracked = {
            "bindings": {"schema_version": "1.0", "roles": bindings},
            "contract": {
                "schema_version": "1.0", "synthetic": synthetic,
                "privacy_safe": True, "fake_vault_authorized": synthetic,
                "real_outer_attempted_open_count": 0,
                "real_outer_open_count": 0,
            },
            "preflight_summary": {
                "schema_version": "1.0", "status": "pass",
                "candidate_strata": len(task_rows),
                "selected_model_count": len(selected_meta),
                "oof_row_count": run_meta["oof_row_count"],
                "replay_row_count": run_meta["replay_row_count"],
                "subset_row_count": len(subset_rows),
                "species_count": len(set(row["species_id"] for row in task_rows)),
                "family_count": len(set(row["model_family"] for row in task_rows)),
                "semantic_digest": semantic_digest,
                "real_outer_attempted_open_count": 0,
                "real_outer_open_count": 0,
            },
            "runtime_summary": {
                "schema_version": "1.0",
                "runtime_seconds": time.perf_counter() - start_run,
                "peak_rss_bytes": _peak_rss_bytes(),
                "task_runtime_min": min(row["runtime_seconds"] for row in task_rows),
                "task_runtime_max": max(row["runtime_seconds"] for row in task_rows),
                "warnings_count": sum(row["warnings"] != "[]" for row in task_rows),
                "budget_status": "pass",
            },
            "review": {
                "schema_version": "1.0", "publication_state": "staged_validated",
                "byte_validation": "pass", "semantic_replay": "pass",
                "selection_recomputed": True, "trusted_model_hash_replay": True,
                "privacy_walk": "pass", "paired_publication": True,
            },
        }
        for name, value in tracked.items():
            _privacy_walk(value)
            _write_json(stage_evidence / f"{name}.json", value)
        payloads = sorted(
            [path for path in stage_private.rglob("*") if path.is_file()]
            + [path for path in stage_evidence.rglob("*") if path.is_file()]
        )
        manifest = {
            "schema_version": "1.0", "synthetic": synthetic,
            "publication_state": "staged_validated",
            "files": {
                (
                    f"private/{path.relative_to(stage_private)}"
                    if stage_private in path.parents
                    else f"evidence/{path.relative_to(stage_evidence)}"
                ): {"sha256": _digest_file(path), "bytes": path.stat().st_size}
                for path in payloads
            },
        }
        _privacy_walk(manifest)
        _write_json(stage_evidence / "manifest.json", manifest)
        validate_publication(
            Path(root), stage_evidence, stage_private, mode,
            _require_independent_replay,
        )
        publish_staged_pair(stage_private, stage_evidence, private_dir, evidence_dir)
    except Exception:
        shutil.rmtree(stage_root, ignore_errors=True)
        raise
    shutil.rmtree(stage_root, ignore_errors=True)
    return {
        "mode": mode, "synthetic": synthetic, "status": "pass",
        "candidate_strata": len(executions),
        "selected_model_count": len(selected_meta),
        "outer_attempted_open_count": 0, "outer_open_count": 0,
        "semantic_digest": semantic_digest,
        "private_dir": str(private_dir), "evidence_dir": str(evidence_dir),
    }


def _run_synthetic_to_destinations(
    root: Path,
    config_path: Path,
    private_dir: Path,
    evidence_dir: Path,
) -> Mapping[str, Any]:
    config = load_run_config(Path(root), Path(config_path))
    rows, values, folds, vault, fake_provider = _synthetic_fixture()
    broker, provider, _unused_vault = ingest_synthetic_foundation(rows, values, folds)
    return run_preflight_engine(
        root=Path(root), config=config, broker=broker, provider=provider,
        vault=vault, task_plan=_synthetic_task_plan(REAL_SPECIES),
        mode="synthetic", synthetic=True, private_dir=Path(private_dir),
        evidence_dir=Path(evidence_dir), fake_vault_provider=fake_provider,
        authorize_fake_vault=True,
    )


def run_synthetic(root: Path, config_path: Path) -> Mapping[str, Any]:
    config = load_run_config(Path(root), Path(config_path))
    private, evidence = _publication_destinations(Path(root), config, True)
    return _run_synthetic_to_destinations(Path(root), Path(config_path), private, evidence)


def run_real_preflight(root: Path, config_path: Path) -> Mapping[str, Any]:
    config = load_run_config(Path(root), Path(config_path))
    _validate_real_scope(config)
    task_plan = _real_task_plan(config)
    broker, provider, vault = ingest_private_foundation(Path(root), config)
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise ModelingContractError("real_outer_access_detected")
    observed: dict[str, Mapping[str, int]] = {}
    for species_id in REAL_SPECIES:
        outer = broker.outer_training(species_id)
        counts = _source_counts(outer)
        observed[species_id] = {
            "included": len(outer.keys), "positive": counts["positive"],
            "zero_survey": counts["zero_survey"],
            "zero_pseudoabsence": counts["zero_pseudoabsence"],
        }
    private, evidence = _publication_destinations(Path(root), config, False)
    result = dict(run_preflight_engine(
        root=Path(root), config=config, broker=broker, provider=provider,
        vault=vault, task_plan=task_plan, mode="real-preflight",
        synthetic=False, private_dir=private, evidence_dir=evidence,
    ))
    result["factory_validated_complete_counts"] = config["scope"]["included_row_counts"]
    result["observed_outer_training_counts"] = observed
    result["included_count_interpretation"] = "included_row_positive_fraction"
    return result


_FORBIDDEN = (
    "grid_cell_id", "coordinates", "row_payload", "private_path",
    "site_id", "camera_id", "observation_timing",
)
_PRIVATE_TEXT_TOKENS = (
    "/data/processed/", "response_partitioned", "canonical_map",
    "grid_cell", "camera_", "site_",
)


def _privacy_walk(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            low = str(key).lower()
            if any(token in low for token in _FORBIDDEN):
                raise ModelingContractError("tracked_privacy_field")
            _privacy_walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _privacy_walk(child)
    elif isinstance(value, str):
        low = value.lower()
        if value.startswith("/") or any(token in low for token in _PRIVATE_TEXT_TOKENS):
            raise ModelingContractError("tracked_private_path")


def _read_canonical_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelingContractError("json_payload_invalid") from exc
    if path.read_text(encoding="utf-8") != canonical_json(value) + "\n":
        raise ModelingContractError("canonical_json_mismatch")
    return value


def _reconstruct_candidate(
    task: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> CandidateOOF:
    folds: list[FoldOOF] = []
    for fold_id in FOLDS:
        fold_rows = sorted(
            [row for row in rows if row["record_kind"] == "oof" and row["fold_id"] == fold_id],
            key=lambda row: row["row_index"],
        )
        if not fold_rows:
            raise ModelingContractError("oof_fold_missing")
        scores = np.asarray([row["score"] for row in fold_rows], dtype=np.float64)
        means = np.asarray([row["mean_score"] for row in fold_rows], dtype=np.float64)
        folds.append(FoldOOF(
            fold_id,
            tuple(_parse_row_token(row["row_key"]) for row in fold_rows),
            np.asarray([row["y_true"] for row in fold_rows], dtype=np.int8),
            {"seed00": scores}, means,
            float(fold_rows[0]["fold_roc_auc"]),
            float(fold_rows[0]["fold_tss"]),
        ))
    stratum = SelectionStratum(
        task["species_id"], task["fraction_id"], task["ladder_id"],
        task["model_family"], ("seed00",),
    )
    return CandidateOOF(
        stratum, task["candidate_id"], tuple(folds), float(task["threshold"]),
        float(task["mean_fold_roc_auc"]),
        float(task["mean_fold_tss_at_oof_threshold"]), {},
    )


_DETERMINISTIC_TASK_FIELDS = (
    "schema_version", "run_id", "task_id", "config_digest", "species_id",
    "transform_id", "cv_fold", "fraction_id", "ladder_id", "subset_digest",
    "model_family", "candidate_id", "seed_label", "seed_uint32", "pair_id",
    "synthetic", "n_train", "n_validation", "train_positive",
    "train_zero_survey", "train_zero_pseudoabsence", "validation_positive",
    "validation_zero_survey", "validation_zero_pseudoabsence",
    "feature_transform_id", "transform_digest", "encoder_digest",
    "feature_schema_digest", "unseen_level_counts", "stopping_fold",
    "best_epochs_by_fold", "best_epoch", "initial_state_digest",
    "discovery_initial_state_digest", "replay_initial_state_digest",
    "neural_stop_status", "outer_attempted_open_count", "outer_open_count",
    "convergence_status", "epochs_or_iterations", "warnings", "model_path",
    "oof_path", "selected", "selection_rank", "mean_fold_roc_auc",
    "mean_fold_tss_at_oof_threshold", "threshold", "oof_score_digest",
    "replay_score_digest", "fake_vault_authorized",
)


def _authoritative_semantic_bundle(
    private_dir: Path,
    evidence_dir: Path,
) -> Mapping[str, Any]:
    """Return deterministic scientific/engineering semantics, excluding timing noise."""
    private_dir, evidence_dir = Path(private_dir), Path(evidence_dir)
    tasks = pq.read_table(private_dir / "tasks.parquet").to_pylist()
    oof = pq.read_table(private_dir / "oof.parquet").to_pylist()
    subsets = pq.read_table(private_dir / "subsets.parquet").to_pylist()
    run = _read_canonical_json(private_dir / "run.json")
    summary = _read_canonical_json(evidence_dir / "preflight_summary.json")
    task_semantics = [
        {field: task[field] for field in _DETERMINISTIC_TASK_FIELDS}
        for task in tasks
    ]
    model_semantics: list[Mapping[str, Any]] = []
    for task in tasks:
        if not task["selected"]:
            continue
        try:
            envelope = json.loads((private_dir / task["model_path"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelingContractError("independent_model_envelope_invalid") from exc
        model_semantics.append({
            "task_id": task["task_id"],
            "family": envelope.get("family"),
            "candidate": envelope.get("candidate"),
            "candidate_digest": envelope.get("candidate_digest"),
            "fit_seed": envelope.get("fit_seed"),
            "schema": envelope.get("schema"),
            "transform_digest": envelope.get("transform_digest"),
            "encoder_digest": envelope.get("encoder_digest"),
            "feature_schema_digest": envelope.get("feature_schema_digest"),
            "identity_digest": envelope.get("identity_digest"),
        })
    return {
        "schema_version": "1.0",
        "mode": run["mode"],
        "config_digest": run["config_digest"],
        "task_plan": run["task_plan"],
        "semantic_digest": run["semantic_digest"],
        "tasks": task_semantics,
        "oof": sorted(oof, key=lambda row: (
            row["task_id"], row["record_kind"], row["fold_id"],
            row["row_index"], row["row_key"],
        )),
        "subsets": sorted(subsets, key=lambda row: (
            row["task_id"], row["membership_kind"], row["split_id"],
            row["rank"], row["row_key"],
        )),
        "models": model_semantics,
        "fake_vault_score_receipts": run["fake_vault_score_receipts"],
        "seed01_diagnostics": run["seed01_diagnostics"],
        "aggregate_semantic_digest": summary["semantic_digest"],
    }


def _independent_full_replay_bundle(
    root: Path,
    config: Mapping[str, Any],
    mode: str,
) -> Mapping[str, Any]:
    """Freshly execute the frozen plan without recursively invoking full replay."""
    synthetic = mode == "synthetic"
    with tempfile.TemporaryDirectory(prefix="goal028-independent-") as temp:
        destination = Path(temp)
        if synthetic:
            rows, values, folds, vault, fake_provider = _synthetic_fixture()
            broker, provider, _ = ingest_synthetic_foundation(rows, values, folds)
            task_plan = _synthetic_task_plan(REAL_SPECIES)
        else:
            broker, provider, vault = ingest_private_foundation(Path(root), config)
            fake_provider = None
            task_plan = _real_task_plan(config)
            if vault.attempted_open_count != 0 or vault.open_count != 0:
                raise ModelingContractError("real_outer_access_detected")
        private_dir, evidence_dir = destination / "private", destination / "evidence"
        run_preflight_engine(
            root=Path(root), config=config, broker=broker, provider=provider,
            vault=vault, task_plan=task_plan, mode=mode, synthetic=synthetic,
            private_dir=private_dir, evidence_dir=evidence_dir,
            fake_vault_provider=fake_provider,
            authorize_fake_vault=synthetic,
            _require_independent_replay=False,
        )
        if not synthetic and (vault.attempted_open_count != 0 or vault.open_count != 0):
            raise ModelingContractError("real_outer_access_detected")
        return _authoritative_semantic_bundle(private_dir, evidence_dir)


def validate_publication(
    root: Path,
    evidence_dir: Path,
    private_dir: Path | None,
    mode: str,
    full: bool,
) -> Mapping[str, Any]:
    """Validate canonical bytes, exact footprints, and full semantic replay."""
    root, evidence_dir = Path(root), Path(evidence_dir)
    if mode not in {"synthetic", "real-preflight"}:
        raise ModelingContractError("validation_mode_invalid")
    if not evidence_dir.is_dir() or evidence_dir.is_symlink():
        raise ModelingContractError("aggregate_footprint_incomplete")
    if {path.name for path in evidence_dir.iterdir()} != set(TRACKED_NAMES):
        raise ModelingContractError("aggregate_footprint_incomplete")
    docs = {Path(name).stem: _read_canonical_json(evidence_dir / name) for name in TRACKED_NAMES}
    _privacy_walk(docs)
    manifest = docs["manifest"]
    if manifest.get("publication_state") != "staged_validated":
        raise ModelingContractError("publication_state_mismatch")
    if bool(manifest.get("synthetic")) != (mode == "synthetic"):
        raise ModelingContractError("publication_mode_mismatch")
    if private_dir is None:
        raise ModelingContractError("private_manifest_requires_private_dir")
    private_dir = Path(private_dir)
    if not private_dir.is_dir() or private_dir.is_symlink():
        raise ModelingContractError("private_footprint_incomplete")
    if {path.name for path in private_dir.iterdir()} != set(PRIVATE_NAMES):
        raise ModelingContractError("private_footprint_incomplete")
    if any(path.is_symlink() for path in private_dir.rglob("*")):
        raise ModelingContractError("private_symlink_forbidden")
    actual_manifest_paths = {
        f"private/{path.relative_to(private_dir)}"
        for path in private_dir.rglob("*") if path.is_file()
    } | {
        f"evidence/{path.relative_to(evidence_dir)}"
        for path in evidence_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if set(manifest.get("files", {})) != actual_manifest_paths:
        raise ModelingContractError("manifest_footprint_mismatch")
    for rel, receipt in manifest["files"].items():
        path = (
            private_dir / rel.removeprefix("private/")
            if rel.startswith("private/")
            else evidence_dir / rel.removeprefix("evidence/")
        )
        if (
            not path.is_file() or path.is_symlink()
            or receipt != {"sha256": _digest_file(path), "bytes": path.stat().st_size}
        ):
            raise ModelingContractError("manifest_byte_mismatch")
    if docs["review"].get("publication_state") != "staged_validated":
        raise ModelingContractError("publication_state_mismatch")

    tasks_table = pq.read_table(private_dir / "tasks.parquet")
    oof_table = pq.read_table(private_dir / "oof.parquet")
    subset_table = pq.read_table(private_dir / "subsets.parquet")
    if tasks_table.schema != TASK_SCHEMA or oof_table.schema != OOF_SCHEMA or subset_table.schema != SUBSET_SCHEMA:
        raise ModelingContractError("private_schema_mismatch")
    tasks = tasks_table.to_pylist()
    oof = oof_table.to_pylist()
    subsets = subset_table.to_pylist()
    run = _read_canonical_json(private_dir / "run.json")
    config = load_run_config(root, root / "config/modeling_foundation_preflight.json")
    config_digest = _sha(config)
    synthetic = mode == "synthetic"
    if run.get("config_digest") != config_digest or bool(run.get("synthetic")) != synthetic:
        raise ModelingContractError("config_semantic_replay_mismatch")
    expected_plan = _synthetic_task_plan(REAL_SPECIES) if synthetic else _real_task_plan(config)
    if run.get("task_plan") != [asdict(task) for task in expected_plan]:
        raise ModelingContractError("run_task_plan_mismatch")
    expected_run_id = _sha({
        "schema_version": "1.0", "mode": mode, "config_digest": config_digest,
        "plan": [asdict(task) for task in expected_plan],
    })
    if run.get("run_id") != expected_run_id:
        raise ModelingContractError("run_identity_mismatch")
    if len(tasks) != len(expected_plan) or len({row["task_id"] for row in tasks}) != len(tasks):
        raise ModelingContractError("task_count_or_identity_mismatch")

    if synthetic:
        source_rows, values, folds, vault, fake_provider = _synthetic_fixture()
        broker, provider, _ = ingest_synthetic_foundation(source_rows, values, folds)
    else:
        broker, provider, vault = ingest_private_foundation(root, config)
        fake_provider = None
        if vault.attempted_open_count != 0 or vault.open_count != 0:
            raise ModelingContractError("real_outer_access_detected")
    by_task_oof = {
        row["task_id"]: [candidate for candidate in oof if candidate["task_id"] == row["task_id"]]
        for row in tasks
    }
    by_task_subset = {
        row["task_id"]: [candidate for candidate in subsets if candidate["task_id"] == row["task_id"]]
        for row in tasks
    }
    reconstructed: dict[str, CandidateOOF] = {}
    loaded_for_fake: list[tuple[Mapping[str, Any], Any, Mapping[str, Any]]] = []
    expected_seed01_diagnostics: list[Mapping[str, Any]] = []
    for planned, task in zip(expected_plan, tasks):
        if task["task_id"] != task_id(planned):
            raise ModelingContractError("task_id_mismatch")
        if any(task[key] != getattr(planned, key) for key in (
            "species_id", "transform_id", "fraction_id", "ladder_id",
            "model_family", "candidate_id", "seed_label",
        )):
            raise ModelingContractError("task_identity_mismatch")
        if task["config_digest"] != config_digest or task["task_digest"] != _task_digest(task):
            raise ModelingContractError("task_digest_mismatch")
        if task["run_id"] != expected_run_id or task["pair_id"] != _sha({
            "run_id": expected_run_id, "species_id": planned.species_id,
            "fraction_id": planned.fraction_id, "ladder_id": planned.ladder_id,
            "model_family": planned.model_family,
        }):
            raise ModelingContractError("task_pair_identity_mismatch")
        if task["git_commit"] != "unknown" and re.fullmatch(r"[0-9a-f]{40}", task["git_commit"]) is None:
            raise ModelingContractError("git_commit_provenance_invalid")
        if task["seed_uint32"] != derive_seed(planned, "fit"):
            raise ModelingContractError("task_seed_mismatch")
        if task["publication_state"] != "staged_validated":
            raise ModelingContractError("publication_state_mismatch")
        if bool(task["synthetic"]) != synthetic or bool(task["fake_vault_authorized"]) != synthetic:
            raise ModelingContractError("fake_vault_flag_mismatch")
        if task["outer_attempted_open_count"] != 0 or task["outer_open_count"] != 0:
            raise ModelingContractError("real_outer_access_detected")
        if task["oof_path"] != "oof.parquet" or task["oof_sha256"] != _digest_file(private_dir / "oof.parquet"):
            raise ModelingContractError("oof_digest_mismatch")
        outer = broker.outer_training(planned.species_id)
        endpoint = _endpoint_lookup(outer, planned.fraction_id, planned.ladder_id)
        endpoint_rows = _rowset_for_keys(outer, endpoint.keys)
        encoder = provider.fit_encoder(endpoint_rows, planned.model_family, "outer")
        replay_batch = provider.materialize(endpoint_rows, "outer", encoder)
        train_counts, validation_counts = _source_counts(endpoint_rows), _source_counts(outer)
        expected_counts = (
            len(endpoint_rows.keys), len(outer.keys),
            train_counts["positive"], train_counts["zero_survey"],
            train_counts["zero_pseudoabsence"], validation_counts["positive"],
            validation_counts["zero_survey"], validation_counts["zero_pseudoabsence"],
        )
        observed_counts = tuple(task[key] for key in (
            "n_train", "n_validation", "train_positive", "train_zero_survey",
            "train_zero_pseudoabsence", "validation_positive",
            "validation_zero_survey", "validation_zero_pseudoabsence",
        ))
        if observed_counts != expected_counts or task["subset_digest"] != endpoint.subset_digest:
            raise ModelingContractError("task_class_or_subset_count_mismatch")
        if (
            task["transform_digest"] != replay_batch.transform_digest
            or task["encoder_digest"] != replay_batch.encoder_digest
            or task["feature_schema_digest"] != replay_batch.feature_schema_digest
            or task["unseen_level_counts"] != canonical_json(dict(replay_batch.unseen_level_counts))
        ):
            raise ModelingContractError("refit_feature_provenance_mismatch")

        candidate_subsets = by_task_subset[task["task_id"]]
        expected_subset_rows: list[tuple[Any, ...]] = []
        for fold_id in FOLDS:
            cv_train, _ = broker.inner(planned.species_id, fold_id)
            fold_endpoint = _endpoint_lookup(cv_train, planned.fraction_id, planned.ladder_id)
            expected_subset_rows.extend(
                ("oof_train_endpoint", f"cv_{fold_id}", fold_endpoint.subset_digest, rank, key)
                for rank, key in enumerate(fold_endpoint.keys)
            )
        expected_subset_rows.extend(
            ("outer_refit_endpoint", "outer", endpoint.subset_digest, rank, key)
            for rank, key in enumerate(endpoint.keys)
        )
        observed_subset_rows = [
            (
                row["membership_kind"], row["split_id"], row["subset_digest"],
                row["rank"], _parse_row_token(row["row_key"]),
            )
            for row in candidate_subsets
        ]
        if observed_subset_rows != sorted(expected_subset_rows, key=lambda row: (
            row[0], row[1], row[3], _row_token(row[4])
        )):
            raise ModelingContractError("subset_semantic_replay_mismatch")

        task_oof = by_task_oof[task["task_id"]]
        expected_neural_initials: list[str] = []
        for fold_id in FOLDS:
            fold_rows = sorted(
                [row for row in task_oof if row["record_kind"] == "oof" and row["fold_id"] == fold_id],
                key=lambda row: row["row_index"],
            )
            cv_train, assessment = broker.inner(planned.species_id, fold_id)
            fold_endpoint = _endpoint_lookup(cv_train, planned.fraction_id, planned.ladder_id)
            fold_train = _rowset_for_keys(cv_train, fold_endpoint.keys)
            fold_encoder = provider.fit_encoder(fold_train, planned.model_family, f"cv_{fold_id}")
            fold_batch = provider.materialize(assessment, f"cv_{fold_id}", fold_encoder)
            if (
                tuple(_parse_row_token(row["row_key"]) for row in fold_rows) != assessment.keys
                or tuple(row["y_true"] for row in fold_rows) != tuple(int(v) for v in assessment.pa)
                or any(
                    row["transform_digest"] != fold_batch.transform_digest
                    or row["encoder_digest"] != fold_batch.encoder_digest
                    or row["feature_schema_digest"] != fold_batch.feature_schema_digest
                    or row["unseen_level_counts"] != canonical_json(dict(fold_batch.unseen_level_counts))
                    for row in fold_rows
                )
            ):
                raise ModelingContractError("oof_feature_or_label_mismatch")
            if planned.model_family in {"shallow_ann", "residual_mlp"}:
                fold_task = TaskKey(
                    planned.species_id, f"cv_{fold_id}", planned.fraction_id,
                    planned.ladder_id, planned.model_family,
                    planned.candidate_id, "seed00",
                )
                _, initial_report = build_adapter(planned.model_family).fit(
                    provider.materialize(fold_train, f"cv_{fold_id}", fold_encoder),
                    None,
                    CANONICAL_CANDIDATES[planned.candidate_id],
                    derive_seed(fold_task, "fit"),
                    exact_epochs=1,
                )
                if initial_report.initial_state_digest is None:
                    raise ModelingContractError("neural_initial_state_missing")
                expected_neural_initials.append(initial_report.initial_state_digest)
        candidate = _reconstruct_candidate(task, task_oof)
        select_candidate([candidate])
        scores = [
            row["score"] for row in task_oof if row["record_kind"] == "oof"
        ]
        if task["oof_score_digest"] != _sha(scores):
            raise ModelingContractError("oof_score_digest_mismatch")
        reconstructed[task["task_id"]] = candidate

        replay_rows = sorted(
            [row for row in task_oof if row["record_kind"] == "replay"],
            key=lambda row: row["row_index"],
        )
        if task["selected"]:
            model_path = private_dir / task["model_path"]
            manifest_model = manifest["files"].get(f"private/{task['model_path']}", {})
            if (
                task["model_path"] != f"models/{task['task_id']}.model"
                or task["model_sha256"] != manifest_model.get("sha256")
                or task["model_sha256"] != _digest_file(model_path)
                or tuple(_parse_row_token(row["row_key"]) for row in replay_rows) != replay_batch.keys
            ):
                raise ModelingContractError("model_or_replay_identity_mismatch")
            expected_scores = np.asarray([row["score"] for row in replay_rows], dtype=np.float64)
            if task["replay_score_digest"] != _sha(expected_scores.tolist()):
                raise ModelingContractError("replay_score_digest_mismatch")
            replay_predictions(
                model_path, replay_batch, expected_scores,
                float(config["neural"]["score_atol"]), task["model_sha256"],
            )
            loaded_for_fake.append((task, load_fitted_model(model_path, task["model_sha256"]), encoder))
        elif (
            task["model_path"] or task["model_sha256"] or task["replay_score_digest"]
            or replay_rows
        ):
            raise ModelingContractError("unselected_model_artifact_present")

        if planned.model_family in {"shallow_ann", "residual_mlp"}:
            try:
                best_epochs = json.loads(task["best_epochs_by_fold"])
                stop_folds = json.loads(task["stopping_fold"])
                discovery = json.loads(task["discovery_initial_state_digest"])
                replay_initial = json.loads(task["replay_initial_state_digest"])
                stop_status = json.loads(task["neural_stop_status"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise ModelingContractError("neural_receipt_invalid") from exc
            if (
                len(best_epochs) != 5
                or any(type(value) is not int or value < 1 or value > 300 for value in best_epochs)
                or task["best_epoch"] != sorted(best_epochs)[2]
                or stop_folds != [f"fold{(i + 1) % 5:02d}" for i in range(5)]
                or discovery != replay_initial
                or discovery != expected_neural_initials
                or len(stop_status) != 5
                or any(value not in {"patience_stop", "max_epochs_reached"} for value in stop_status)
            ):
                raise ModelingContractError("neural_receipt_mismatch")
            if task["selected"]:
                _, refit_initial_report = build_adapter(planned.model_family).fit(
                    replay_batch, None, CANONICAL_CANDIDATES[planned.candidate_id],
                    derive_seed(planned, "fit"), exact_epochs=1,
                )
                if task["initial_state_digest"] != refit_initial_report.initial_state_digest:
                    raise ModelingContractError("neural_refit_initial_state_mismatch")
                if not synthetic:
                    diagnostic_task = TaskKey(
                        planned.species_id, planned.transform_id,
                        planned.fraction_id, planned.ladder_id,
                        planned.model_family, planned.candidate_id, "seed01",
                    )
                    diagnostic_seed = derive_seed(diagnostic_task, "fit")
                    first, first_report = build_adapter(planned.model_family).fit(
                        replay_batch, None, CANONICAL_CANDIDATES[planned.candidate_id],
                        diagnostic_seed, exact_epochs=int(task["best_epoch"]),
                    )
                    second, second_report = build_adapter(planned.model_family).fit(
                        replay_batch, None, CANONICAL_CANDIDATES[planned.candidate_id],
                        diagnostic_seed, exact_epochs=int(task["best_epoch"]),
                    )
                    first_scores = first.predict_scores(replay_batch)
                    second_scores = second.predict_scores(replay_batch)
                    if not np.allclose(
                        first_scores, second_scores, rtol=0.0,
                        atol=float(config["neural"]["score_atol"]),
                    ):
                        raise ModelingContractError("seed01_deterministic_pair_mismatch")
                    expected_seed01_diagnostics.append({
                        "task_id": task_id(diagnostic_task), "seed_label": "seed01",
                        "score_digest": _sha(first_scores.tolist()),
                        "exact_epochs": int(task["best_epoch"]),
                        "first_initial_state_digest": first_report.initial_state_digest,
                        "second_initial_state_digest": second_report.initial_state_digest,
                        "status": "pass",
                    })
            elif task["initial_state_digest"] != "":
                raise ModelingContractError("unselected_refit_initial_state_present")
        elif (
            task["best_epochs_by_fold"] != "[]" or task["best_epoch"] is not None
            or task["stopping_fold"] != "[]"
            or task["initial_state_digest"] != ""
            or task["discovery_initial_state_digest"] != "[]"
            or task["replay_initial_state_digest"] != "[]"
            or task["neural_stop_status"] != "[]"
        ):
            raise ModelingContractError("conventional_neural_receipt_present")

    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for task in tasks:
        key = (
            task["species_id"], task["fraction_id"], task["ladder_id"],
            task["model_family"],
        )
        groups.setdefault(key, []).append(task)
    for group in groups.values():
        selected = select_candidate([reconstructed[row["task_id"]] for row in group])
        selected_rows = [row for row in group if row["selected"]]
        if len(selected_rows) != 1 or selected_rows[0]["candidate_id"] != selected.candidate_id:
            raise ModelingContractError("candidate_selection_mismatch")
        expected_ranked = sorted(
            group,
            key=lambda row: (
                -row["mean_fold_roc_auc"],
                -row["mean_fold_tss_at_oof_threshold"],
                row["candidate_id"],
            ),
        )
        if [row["selection_rank"] for row in expected_ranked] != list(range(1, len(group) + 1)):
            raise ModelingContractError("candidate_selection_rank_mismatch")

    semantic_payload = [{
        "task_id": row["task_id"], "selected": row["selected"],
        "auc": row["mean_fold_roc_auc"], "tss": row["mean_fold_tss_at_oof_threshold"],
        "threshold": row["threshold"], "oof_score_digest": row["oof_score_digest"],
        "replay_score_digest": row["replay_score_digest"],
    } for row in tasks]
    semantic_digest = _sha(semantic_payload)
    if run.get("semantic_digest") != semantic_digest:
        raise ModelingContractError("semantic_digest_mismatch")
    if (
        run.get("candidate_strata") != len(tasks)
        or run.get("selected_model_count") != sum(row["selected"] for row in tasks)
        or run.get("oof_row_count") != sum(row["record_kind"] == "oof" for row in oof)
        or run.get("replay_row_count") != sum(row["record_kind"] == "replay" for row in oof)
        or run.get("subset_row_count") != len(subsets)
        or run.get("real_outer_attempted_open_count") != 0
        or run.get("real_outer_open_count") != 0
    ):
        raise ModelingContractError("run_reconciliation_mismatch")
    summary = docs["preflight_summary"]
    expected_aggregate = {
        "candidate_strata": len(tasks),
        "selected_model_count": sum(row["selected"] for row in tasks),
        "oof_row_count": sum(row["record_kind"] == "oof" for row in oof),
        "replay_row_count": sum(row["record_kind"] == "replay" for row in oof),
        "subset_row_count": len(subsets),
        "semantic_digest": semantic_digest,
    }
    if any(summary.get(key) != value for key, value in expected_aggregate.items()):
        raise ModelingContractError("aggregate_reconciliation_mismatch")
    if (
        docs["contract"].get("real_outer_attempted_open_count") != 0
        or docs["contract"].get("real_outer_open_count") != 0
        or summary.get("real_outer_attempted_open_count") != 0
        or summary.get("real_outer_open_count") != 0
    ):
        raise ModelingContractError("real_outer_access_detected")
    tracked_roles = docs["bindings"].get("roles")
    expected_roles = {
        role: {"digest": record["sha256"], "status": "verified"}
        for role, record in config["bindings"].items()
        if role != "required_roles"
    }
    expected_roles["config"] = {"digest": config_digest, "status": "verified"}
    if tracked_roles != expected_roles:
        raise ModelingContractError("binding_reconciliation_mismatch")

    if synthetic:
        assert fake_provider is not None
        held = vault.open({"synthetic": True})
        receipts: list[dict[str, Any]] = []
        for task, fitted, encoder in sorted(loaded_for_fake, key=lambda item: item[0]["task_id"]):
            held_species = _rowset_for_keys(
                held, [key for key in held.keys if key.species_id == task["species_id"]]
            )
            batch = fake_provider.materialize(held_species, "outer", encoder)
            scores = fitted.predict_scores(batch)
            receipts.append({
                "task_id": task["task_id"], "n": len(scores),
                "score_digest": _sha(scores.tolist()),
            })
        if (
            run.get("fake_vault_authorized") is not True
            or run.get("fake_vault_attempted_open_count") != 1
            or run.get("fake_vault_open_count") != 1
            or run.get("fake_vault_score_receipts") != receipts
        ):
            raise ModelingContractError("fake_vault_semantic_mismatch")
    elif (
        vault.attempted_open_count != 0 or vault.open_count != 0
        or run.get("fake_vault_attempted_open_count") != 0
        or run.get("fake_vault_open_count") != 0
    ):
        raise ModelingContractError("real_outer_access_detected")
    if not synthetic and run.get("seed01_diagnostics") != expected_seed01_diagnostics:
        raise ModelingContractError("seed01_diagnostic_replay_mismatch")
    authoritative_bundle_digest = ""
    if full:
        proposed_bundle = _authoritative_semantic_bundle(private_dir, evidence_dir)
        independent_bundle = _independent_full_replay_bundle(root, config, mode)
        proposed_digest = _sha(proposed_bundle)
        authoritative_bundle_digest = _sha(independent_bundle)
        if (
            proposed_digest != authoritative_bundle_digest
            or canonical_json(proposed_bundle) != canonical_json(independent_bundle)
        ):
            raise ModelingContractError("independent_semantic_replay_mismatch")
    return {
        "status": "pass", "mode": mode, "full": bool(full),
        "synthetic": synthetic, "candidate_strata": len(tasks),
        "outer_attempted_open_count": 0, "outer_open_count": 0,
        "semantic_digest": semantic_digest,
        "independent_semantic_replay": bool(full),
        "authoritative_bundle_digest": authoritative_bundle_digest,
    }


def publish_staged_pair(
    stage_private: Path,
    stage_evidence: Path,
    private_dir: Path,
    evidence_dir: Path,
) -> None:
    stage_private, stage_evidence, private_dir, evidence_dir = map(
        Path, (stage_private, stage_evidence, private_dir, evidence_dir)
    )
    for destination in (private_dir, evidence_dir):
        if destination.exists() or destination.is_symlink():
            raise ModelingContractError("publication_destination_exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
    if (
        not stage_private.is_dir() or stage_private.is_symlink()
        or not stage_evidence.is_dir() or stage_evidence.is_symlink()
    ):
        raise ModelingContractError("publication_stage_missing")
    published: list[Path] = []
    try:
        os.rename(stage_private, private_dir)
        published.append(private_dir)
        os.rename(stage_evidence, evidence_dir)
        published.append(evidence_dir)
    except Exception as exc:
        for destination in reversed(published):
            if destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
        raise ModelingContractError("publication_rollback") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--mode", choices=("synthetic", "real-preflight"), default="synthetic")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--real-preflight", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    config_path = root / "config/modeling_foundation_preflight.json"
    if args.validate:
        config = load_run_config(root, config_path)
        mode = "real-preflight" if args.real_preflight else (
            "synthetic" if args.synthetic else args.mode
        )
        private, evidence = _publication_destinations(root, config, mode == "synthetic")
        result = validate_publication(root, evidence, private, mode, args.full)
    elif args.mode == "real-preflight":
        result = run_real_preflight(root, config_path)
    else:
        result = run_synthetic(root, config_path)
    print(canonical_json(result))


if __name__ == "__main__":
    main()
