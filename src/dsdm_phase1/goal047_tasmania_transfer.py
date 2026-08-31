"""Prospectively frozen mainland-to-Tasmania transfer assessment.

Every command except ``evaluate`` is mainland-only. The production opening
is irreversible: it validates the committed gate, durably creates an
exclusive marker, and only then opens the two bound Tasmania inputs.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable, Mapping, Sequence
import warnings

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
import torch

from dsdm.models import MultiHeadResidual, ResidualMLP
from . import goal042_transfer_response as goal042
from . import goal046_mainland_dsdm as goal046
from .goal040_normalisation import CELL_PATH as ELIGIBLE_CELL_PATH
from .goal040_support import SPECIES_CELLS_PATH
from .mainland_dsdm import (
    NeuralDataset,
    _predict,
    _reset_head,
    _train_epochs,
    architecture_spec,
    equal_head_weights,
    load_shared_state,
    resolve_device,
    seed_all,
    shared_state,
    state_digest,
)
from .mainland_modeling import (
    CATEGORICAL,
    CONTINUOUS,
    MISSING,
    UNSEEN,
    EncodedFeatures,
    MainlandStore,
    ResponseRows,
    binary_metrics,
    make_batch,
    sha256_file,
    slug,
    stable_seed,
)
from .model_adapters import CANONICAL_CANDIDATES, build_adapter, load_fitted_model
from .modeling_contract import FeatureBatch, RowKey, canonical_json


CONFIG_PATH = Path("config/goal047_tasmania_transfer.json")
SOURCE_PATH = Path("src/dsdm_phase1/goal047_tasmania_transfer.py")
FREEZE_PATH = Path("evidence/tasmania_transfer/goal047/freeze.json")
SEEDS = ("seed00", "seed01", "seed02", "seed03", "seed04")
TARGETS = (
    "Dasyurus maculatus",
    "Notamacropus rufogriseus",
    "Pseudocheirus peregrinus",
    "Trichosurus vulpecula",
    "Vombatus ursinus",
)
ARMS = (
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
)
METHODS = ARMS + ("selected_conventional", "strict_q_conventional")
METRIC_NAMES = (
    "roc_auc",
    "tss",
    "balanced_accuracy",
    "mcc",
    "sensitivity",
    "specificity",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
PRIVATE_RESULT_TOKENS = (
    "cell_id",
    "longitude",
    "latitude",
    "grid_cell_id",
    "site_id",
    "record_id",
    "data/raw/",
    "data/processed/",
)

RESPONSE_SCHEMA = goal042.MAINLAND_SCHEMA
RESPONSE_RECEIPT_SCHEMA = "goal047-mainland-full-response-v2"
Q_MODEL_SCHEMA = "goal047-q-model-v2"
Q_RECEIPT_SCHEMA = "goal047-q-receipt-v2"
MODEL_RECEIPT_SCHEMA = "goal047-model-receipt-v2"
PRETRAIN_RECEIPT_SCHEMA = "goal047-pretraining-receipt-v2"


class Goal047Error(ValueError):
    """Fail-closed Goal 047 contract error."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal047Error(reason)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal047Error(f"json_invalid:{path}") from exc
    _require(isinstance(value, dict), "json_object_required")
    return value


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _valid_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and SHA256_RE.fullmatch(value) is not None
        and value not in {"0" * 64, "f" * 64}
    )


def _atomic_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    _atomic_bytes(path, raw)


def _atomic_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        pq.write_table(table, temporary, compression="zstd")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_torch(path: Path, state: Mapping[str, torch.Tensor]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".pt", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        torch.save(dict(state), temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _config(root: Path) -> dict[str, Any]:
    config = _read_json(root / CONFIG_PATH)
    _require(config.get("schema_version") == "goal047-contract-v2", "config_schema_invalid")
    _require(config.get("goal_id") == "goal047-tasmania-transfer-assessment", "config_goal_invalid")
    _require(tuple(config["scope"]["targets"]) == TARGETS, "target_panel_drift")
    _require(tuple(config["design"]["arms"]) == ARMS, "arm_panel_drift")
    _require(tuple(config["design"]["methods"]) == METHODS, "method_panel_drift")
    _require(tuple(config["design"]["seed_labels"]) == SEEDS, "seed_panel_drift")
    _require(config["design"]["architecture"] == "bridge_control", "architecture_drift")
    _require(config["privacy"]["preopening_tasmania_response_rows_read"] == 0, "preopening_response_access_forbidden")
    _require(config["privacy"]["preopening_tasmania_predictor_rows_read"] == 0, "preopening_predictor_access_forbidden")
    return config


def _identity(root: Path) -> dict[str, Any]:
    config = _config(root)
    return {
        "config_sha256": sha256_file(root / CONFIG_PATH),
        "source_sha256": sha256_file(root / SOURCE_PATH),
        "bindings": {name: binding["sha256"] for name, binding in sorted(config["bindings"].items())},
    }


def _goal046_identity(root: Path) -> dict[str, str]:
    return goal046._identity(root)


def _git_state(root: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return commit, not bool(status.strip())


def _tracked_identical(root: Path, path: Path) -> bool:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    if subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{relative}"], cwd=root, capture_output=True
    ).returncode:
        return False
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"], cwd=root, check=True, capture_output=True
    ).stdout
    return committed == resolved.read_bytes()


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        capture_output=True,
    ).returncode == 0


def validate_inputs(root: Path) -> dict[str, Any]:
    """Validate tracked authorities without opening any Tasmania payload."""
    root = root.resolve()
    config = _config(root)
    for name, binding in config["bindings"].items():
        path = root / binding["path"]
        _require(path.is_file(), f"binding_missing:{name}")
        _require(sha256_file(path) == binding["sha256"], f"binding_digest_mismatch:{name}")

    response_manifest = _read_json(root / config["bindings"]["goal042_response_manifest"]["path"])
    _require(response_manifest.get("schema_version") == "goal042-response-manifest-v1", "goal042_manifest_invalid")
    _require(response_manifest.get("status") == "complete_raw_replay_required", "goal042_manifest_not_ready")
    _require(response_manifest.get("privacy", {}).get("tracked_row_payload") is False, "goal042_privacy_invalid")
    _require(set(response_manifest.get("summary", {}).get("mainland_reference", {})) == set(config["scope"]["response_heads"]), "goal042_head_coverage_invalid")

    predictor_manifest = _read_json(root / config["bindings"]["goal041_table_manifest"]["path"])
    _require(
        predictor_manifest.get("schema_version") == "goal041-table-manifest-v3"
        and predictor_manifest.get("regions") == {"southeast_mainland": 1_053_032, "tasmania": 72_293}
        and _valid_digest(predictor_manifest.get("final_sha256")),
        "goal041_manifest_invalid",
    )
    goal044_summary = _read_json(root / config["bindings"]["goal044_summary"]["path"])
    goal046_summary = _read_json(root / config["bindings"]["goal046_summary"]["path"])
    _require(goal044_summary.get("status") == "complete", "goal044_not_ready")
    _require(goal046_summary.get("status") == "goal046_ready", "goal046_not_ready")
    return {
        "status": "goal047_inputs_ready",
        "targets": len(TARGETS),
        "methods": len(METHODS),
        "seeds": len(SEEDS),
        "preopening_tasmania_response_rows_read": 0,
        "preopening_tasmania_predictor_rows_read": 0,
    }


def lower_median(values: Sequence[int]) -> int:
    _require(len(values) == 5, "epoch_fold_count_invalid")
    _require(all(type(value) is int and 1 <= value <= 300 for value in values), "epoch_value_invalid")
    return sorted(values)[2]


def _validate_goal046_epoch_receipts(
    root: Path,
    target: str,
    seed: str,
    fold: int,
    pre: Mapping[str, Any],
    final: Mapping[str, Any],
    *,
    verify_files: bool,
) -> None:
    identity = _goal046_identity(root)
    expected_pre_key = {
        "identity": identity,
        "target": target,
        "held_fold": fold,
        "architecture": "bridge_control",
        "seed_label": seed,
    }
    expected_final_key = {
        "identity": identity,
        "target": target,
        "fraction": 100,
        "ladder": "full",
        "held_fold": fold,
        "selected_architecture": "bridge_control",
        "seed_label": seed,
    }
    _require(set(pre) == {"schema_version", "key", "fit_seed", "meta", "fit", "shared_state_digest", "state_sha256"}, "epoch_pretraining_schema_invalid")
    _require(pre.get("schema_version") == "goal046-pretraining-v1" and pre.get("key") == expected_pre_key, "epoch_pretraining_provenance_invalid")
    heads = [head for head in _config(root)["scope"]["response_heads"] if head != target]
    meta = pre.get("meta", {})
    fit = pre.get("fit", {})
    expected_fit_seed = stable_seed(
        identity["goal045_config_sha256"],
        "pretrain",
        target,
        fold,
        "bridge_control",
        seed,
    )
    _require(
        pre.get("fit_seed") == expected_fit_seed
        and
        meta.get("target") == target
        and meta.get("held_fold") == fold
        and meta.get("excluded_target") is True
        and meta.get("strict_target_absent_as_head") is True
        and meta.get("auxiliary_heads") == heads
        and fit.get("auxiliary_heads") == heads
        and fit.get("auxiliary_head_count") == 19
        and fit.get("within_head_class_balancing") is False
        and fit.get("shared_state_digest") == pre.get("shared_state_digest")
        and _valid_digest(pre.get("shared_state_digest"))
        and _valid_digest(pre.get("state_sha256")),
        "epoch_pretraining_receipt_invalid",
    )
    _require(set(final) == {"schema_version", "key", "fits", "pretraining_shared_state_digest", "base_feature_width", "q_feature_width", "q_scaling", "parquet_rows", "parquet_sha256"}, "epoch_final_schema_invalid")
    _require(final.get("schema_version") == "goal046-final-v1" and final.get("key") == expected_final_key, "epoch_target_provenance_invalid")
    _require(set(final.get("fits", {})) == set(ARMS), "epoch_arm_coverage_invalid")
    _require(final.get("pretraining_shared_state_digest") == pre.get("shared_state_digest"), "epoch_pretraining_link_invalid")
    _require(final.get("base_feature_width") == 103 and final.get("q_feature_width") == 104, "epoch_feature_width_invalid")
    for arm in ARMS:
        item = final["fits"][arm]
        _require(
            set(item) == {
                "best_stopping_loss", "discovery_completed_epochs", "discovery_rows",
                "freeze_trunk", "held_rows", "model_digest", "replay_rows",
                "runtime_seconds", "selected_epoch", "stopping_rows", "transferred",
            }
            and
            type(item.get("selected_epoch")) is int
            and 1 <= item["selected_epoch"] <= 300
            and item.get("transferred") is (arm in ARMS[2:])
            and item.get("freeze_trunk") is (arm == "multihead_frozen_trunk")
            and _valid_digest(item.get("model_digest")),
            "epoch_arm_receipt_invalid",
        )
    _require(type(fit.get("selected_epoch")) is int and 1 <= fit["selected_epoch"] <= 300, "epoch_pretraining_value_invalid")
    _require(type(final.get("parquet_rows")) is int and final["parquet_rows"] > 0 and _valid_digest(final.get("parquet_sha256")), "epoch_final_artifact_invalid")
    if verify_files:
        pre_path, state_path = goal046._pretrain_paths(root, target, fold, "bridge_control", seed)
        final_path = root / "data/processed/dsdm/goal046-strict-mainland-dsdm/final" / f"{slug(target)}_fraction100_full_fold{fold:02d}_{seed}.parquet"
        _require(pre_path.is_file() and state_path.is_file() and sha256_file(state_path) == pre["state_sha256"], "epoch_pretraining_artifact_mismatch")
        _require(final_path.is_file() and sha256_file(final_path) == final["parquet_sha256"], "epoch_final_artifact_mismatch")


def build_epoch_table(
    root: Path,
    *,
    receipts: Mapping[tuple[str, str, str, int], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute every seed-specific lower median from five matching folds."""
    root = root.resolve()
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        for seed in SEEDS:
            pre_values: list[int] = []
            arm_values: dict[str, list[int]] = {arm: [] for arm in ARMS}
            for fold in range(5):
                if receipts is None:
                    pre_path, _ = goal046._pretrain_paths(root, target, fold, "bridge_control", seed)
                    final_path = root / "data/processed/dsdm/goal046-strict-mainland-dsdm/final" / f"{slug(target)}_fraction100_full_fold{fold:02d}_{seed}.json"
                    pre, final = _read_json(pre_path), _read_json(final_path)
                else:
                    pre = receipts[(target, seed, "pretraining", fold)]
                    final = receipts[(target, seed, "final", fold)]
                _validate_goal046_epoch_receipts(root, target, seed, fold, pre, final, verify_files=receipts is None)
                pre_values.append(pre["fit"]["selected_epoch"])
                for arm in ARMS:
                    arm_values[arm].append(final["fits"][arm]["selected_epoch"])
            rows.append({
                "target": target,
                "seed_label": seed,
                "lifecycle": "pretraining",
                "arm": "shared_trunk",
                "selected_epoch": lower_median(pre_values),
                "fold_selected_epochs": pre_values,
            })
            for arm in ARMS:
                values = arm_values[arm]
                rows.append({
                    "target": target,
                    "seed_label": seed,
                    "lifecycle": "target",
                    "arm": arm,
                    "selected_epoch": lower_median(values),
                    "fold_selected_epochs": values,
                })
    expected = len(TARGETS) * len(SEEDS) * (1 + len(ARMS))
    _require(len(rows) == expected and len({(r["target"], r["seed_label"], r["lifecycle"], r["arm"]) for r in rows}) == expected, "epoch_table_coverage_invalid")
    return {
        "schema_version": "goal047-epoch-table-v2",
        "architecture": "bridge_control",
        "rule": "lower_median_of_five_matching_goal046_fold_selected_epoch_integers",
        "rows": rows,
    }


def _threshold_authority(root: Path) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    config = _config(root)
    goal044 = _read_json(root / config["bindings"]["goal044_summary"]["path"])
    goal046_summary = _read_json(root / config["bindings"]["goal046_summary"]["path"])
    tasks = [row for row in goal044.get("tasks", []) if row.get("fraction") == 100 and row.get("ladder") == "full"]
    results = goal046_summary.get("results", [])
    _require(len(tasks) == len(results) == len(TARGETS), "threshold_target_count_invalid")
    table: dict[str, dict[str, float]] = {method: {} for method in METHODS}
    conventional: dict[str, Any] = {}
    for target in TARGETS:
        task_rows = [row for row in tasks if row.get("target") == target]
        result_rows = [row for row in results if row.get("target") == target]
        _require(len(task_rows) == len(result_rows) == 1, "threshold_target_identity_invalid")
        task, result = task_rows[0], result_rows[0]
        family = task.get("best_non_null_family")
        selected = task.get("families", {}).get(family, {}).get("selected", {})
        frozen_candidate = config["design"]["selected_conventional_candidates"][target]
        _require({"family": family, "candidate_id": selected.get("candidate_id")} == frozen_candidate, "selected_candidate_drift")
        selected_seeds = selected.get("seed_labels")
        strict = result.get("strict_q_conventional", {})
        _require(
            selected_seeds == strict.get("seed_labels")
            and strict.get("family") == family
            and strict.get("candidate_id") == selected.get("candidate_id")
            and selected_seeds == (["seed00"] if family == "hist_gradient_boosting" else list(SEEDS)),
            "conventional_seed_authority_invalid",
        )
        for arm in ARMS:
            table[arm][target] = float(result["arms"][arm]["metrics"]["threshold"])
        table["selected_conventional"][target] = float(selected["metrics"]["threshold"])
        table["strict_q_conventional"][target] = float(strict["metrics"]["threshold"])
        conventional[target] = {
            "family": family,
            "candidate_id": selected["candidate_id"],
            "seed_labels": list(selected_seeds),
        }
    _require(set(table) == set(METHODS), "threshold_method_coverage_invalid")
    for method in METHODS:
        _require(set(table[method]) == set(TARGETS), "threshold_target_coverage_invalid")
        _require(all(np.isfinite(value) and 0 <= value <= 1 for value in table[method].values()), "threshold_value_invalid")
    return table, conventional


def _predictor_authority(root: Path) -> dict[str, Any]:
    """Freeze mainland-only ranges and the Goal 043 categorical vocabulary."""
    store = MainlandStore(root)
    ranges = {
        name: {
            "minimum": float(np.nanmin(store.continuous[name])),
            "maximum": float(np.nanmax(store.continuous[name])),
        }
        for name in CONTINUOUS
    }
    transform = store.transforms["transforms"]["mainland_full"]
    vocab_id = transform["categorical_vocabulary_id"]
    vocabulary = store.transforms["categorical_vocabularies"][vocab_id]
    return {
        "transform_id": "mainland_full",
        "training_cell_count": transform["training_cell_count"],
        "training_identity_sha256": transform["training_identity_sha256"],
        "continuous_ranges": ranges,
        "categorical_vocabulary_id": vocab_id,
        "categorical_vocabulary": vocabulary,
        "tasmania_predictor_rows_read": 0,
    }


def prepare(root: Path) -> dict[str, Any]:
    root = root.resolve()
    gate = validate_inputs(root)
    epoch_table = build_epoch_table(root)
    thresholds, conventional = _threshold_authority(root)
    freeze = {
        "schema_version": "goal047-freeze-v2",
        "status": "prospective_preopening_freeze",
        "identity": _identity(root),
        "epoch_table": epoch_table,
        "threshold_table": thresholds,
        "conventional_specs": conventional,
        "predictor_authority": _predictor_authority(root),
        "preopening_access_counters": {"response_rows_read": 0, "predictor_rows_read": 0},
        "production_run": False,
    }
    _atomic_json(root / FREEZE_PATH, freeze)
    return {
        "status": "goal047_freeze_written",
        "gate": gate,
        "epoch_rows": len(epoch_table["rows"]),
        "threshold_values": len(METHODS) * len(TARGETS),
        "production_run": False,
    }


def validate_freeze(root: Path) -> dict[str, Any]:
    root = root.resolve()
    validate_inputs(root)
    freeze = _read_json(root / FREEZE_PATH)
    thresholds, conventional = _threshold_authority(root)
    _require(set(freeze) == {
        "schema_version", "status", "identity", "epoch_table", "threshold_table",
        "conventional_specs", "predictor_authority", "preopening_access_counters",
        "production_run",
    }, "freeze_schema_invalid")
    _require(freeze.get("schema_version") == "goal047-freeze-v2", "freeze_schema_invalid")
    _require(freeze.get("status") == "prospective_preopening_freeze" and freeze.get("production_run") is False, "freeze_status_invalid")
    _require(freeze.get("identity") == _identity(root), "freeze_identity_invalid")
    _require(freeze.get("epoch_table") == build_epoch_table(root), "freeze_epoch_drift")
    _require(freeze.get("threshold_table") == thresholds, "freeze_threshold_drift")
    _require(freeze.get("conventional_specs") == conventional, "freeze_conventional_drift")
    _require(freeze.get("predictor_authority") == _predictor_authority(root), "freeze_predictor_authority_drift")
    _require(freeze.get("preopening_access_counters") == {"response_rows_read": 0, "predictor_rows_read": 0}, "freeze_preopening_access_invalid")
    return {"status": "goal047_freeze_valid", "sha256": sha256_file(root / FREEZE_PATH)}


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise Goal047Error("mainland_coordinate_invalid") from exc
    _require(result.is_finite(), "mainland_coordinate_invalid")
    return result


def _load_mainland_authorities(root: Path) -> tuple[dict[str, tuple[Decimal, Decimal]], dict[str, set[str]], dict[str, Any]]:
    """Verify whole Goal 040 ledgers, retaining mainland records only."""
    config = _config(root)
    domain = _read_json(root / config["bindings"]["goal040_domain_manifest"]["path"])
    normal = _read_json(root / config["bindings"]["goal040_normalisation_manifest"]["path"])
    cell_path = root / ELIGIBLE_CELL_PATH
    species_path = root / SPECIES_CELLS_PATH
    expected_cell_sha = domain["exact_study_domain"]["grid"]["ignored_cell_ledger_sha256"]
    expected_species = normal["outputs"]["species_cells"]
    _require(sha256_file(cell_path) == expected_cell_sha, "eligible_cell_ledger_digest_mismatch")
    _require(sha256_file(species_path) == expected_species["sha256"], "species_cell_ledger_digest_mismatch")

    cells: dict[str, tuple[Decimal, Decimal]] = {}
    discarded_cell_rows = 0
    with cell_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require(reader.fieldnames == ["cell_id", "row_south_to_north", "column_west_to_east", "longitude", "latitude", "state_code", "region"], "eligible_cell_schema_invalid")
        for row in reader:
            if row["region"] != goal042.MAINLAND_REGION:
                discarded_cell_rows += 1
                continue
            cell = row["cell_id"]
            _require(cell not in cells, "eligible_cell_duplicate")
            cells[cell] = (_decimal(row["longitude"]), _decimal(row["latitude"]))
    _require(len(cells) == 1_053_032 and discarded_cell_rows == 72_293, "eligible_cell_region_counts_invalid")

    species_cells: dict[str, set[str]] = defaultdict(set)
    discarded_species_rows = 0
    total_species_rows = 0
    with species_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require(reader.fieldnames == ["species", "cell_id", "state_code", "region"], "species_cell_schema_invalid")
        for row in reader:
            total_species_rows += 1
            if row["region"] != goal042.MAINLAND_REGION:
                discarded_species_rows += 1
                continue
            species, cell = row["species"], row["cell_id"]
            _require(cell in cells and cell not in species_cells[species], "species_cell_mainland_binding_invalid")
            species_cells[species].add(cell)
    _require(total_species_rows == expected_species["rows"], "species_cell_row_count_invalid")
    expected_taxa = set(normal["taxon_tiers"])
    _require(set(species_cells) == expected_taxa, "species_cell_taxon_coverage_invalid")
    _require(all(len(species_cells[name]) == normal["taxon_tiers"][name]["mainland"] for name in expected_taxa), "species_cell_mainland_count_invalid")
    diagnostics = {
        "eligible_cell_sha256": expected_cell_sha,
        "species_cell_sha256": expected_species["sha256"],
        "mainland_cells_retained": len(cells),
        "nonmainland_cell_rows_discarded": discarded_cell_rows,
        "nonmainland_species_rows_discarded": discarded_species_rows,
        "tasmania_rows_retained": 0,
    }
    return cells, dict(species_cells), diagnostics


def _mainland_response_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return goal042._summarise_mainland(rows)


def _response_paths(root: Path) -> tuple[Path, Path]:
    private = root / _config(root)["execution"]["private_root"]
    return private / "mainland_full_response.parquet", private / "mainland_full_response_receipt.json"


def materialise_full_mainland(root: Path) -> dict[str, Any]:
    """Replay all 20 response heads from Goal 040 mainland authorities."""
    root = root.resolve()
    freeze_digest = sha256_file(root / FREEZE_PATH)
    cells, species_cells, authority_diagnostics = _load_mainland_authorities(root)
    config = _config(root)
    heads = list(config["scope"]["response_heads"])
    donor_members: dict[str, set[str]] = defaultdict(set)
    manifest = _read_json(root / config["bindings"]["goal042_response_manifest"]["path"])
    support_taxa = manifest["summary"]["cohort"]["support_taxa"]
    for species in support_taxa:
        for cell in species_cells[species]:
            donor_members[cell].add(species)

    expected = manifest["summary"]["mainland_reference"]
    store = MainlandStore(root)
    complete = np.ones(len(store.cell_ids), dtype=bool)
    for name in CONTINUOUS:
        complete &= np.isfinite(store.continuous[name])
    complete_by_cell = dict(zip(store.cell_ids, complete.tolist(), strict=True))
    groups: list[list[dict[str, Any]]] = []
    full_diagnostics: dict[str, Any] = {}
    for target in heads:
        rows = goal042.materialise_mainland_rows(target, cells, donor_members, species_cells[target])
        observed_summary = _mainland_response_summary(rows)
        _require(observed_summary == expected[target], "mainland_response_manifest_aggregate_mismatch")
        retained = [row for row in rows if complete_by_cell.get(row["cell_id"], False)]
        groups.append(retained)
        full_diagnostics[target] = {
            "replayed_rows": len(rows),
            "replayed_presence_rows": observed_summary["presence_cells"],
            "replayed_primary_x3_rows": observed_summary["primary_x3_response_cells"],
            "continuous_complete_rows": len(retained),
            "continuous_complete_primary_x3_rows": sum(row["is_presence"] or row["eligible_x3"] for row in retained),
            "continuous_incomplete_rows_removed": len(rows) - len(retained),
        }
    table = pa.Table.from_pylist([row for group in groups for row in group], schema=RESPONSE_SCHEMA)
    _require(table.num_rows > 0, "mainland_response_empty")
    response_path, receipt_path = _response_paths(root)
    _atomic_parquet(response_path, table)
    receipt = {
        "schema_version": RESPONSE_RECEIPT_SCHEMA,
        "identity": _identity(root),
        "freeze_sha256": freeze_digest,
        "source": "goal040_mainland_ledgers_replayed_with_goal042_materialise_mainland_rows",
        "goal042_manifest_sha256": config["bindings"]["goal042_response_manifest"]["sha256"],
        "authority_diagnostics": authority_diagnostics,
        "head_diagnostics": full_diagnostics,
        "response_heads": heads,
        "rows": table.num_rows,
        "schema": str(RESPONSE_SCHEMA),
        "parquet_sha256": sha256_file(response_path),
        "tasmania_rows_retained": 0,
    }
    _atomic_json(receipt_path, receipt)
    return receipt


def _validate_response_substrate(root: Path, freeze_digest: str) -> dict[str, Any] | None:
    response_path, receipt_path = _response_paths(root)
    if not response_path.is_file() or not receipt_path.is_file():
        return None
    receipt = _read_json(receipt_path)
    if (
        receipt.get("schema_version") != RESPONSE_RECEIPT_SCHEMA
        or receipt.get("identity") != _identity(root)
        or receipt.get("freeze_sha256") != freeze_digest
        or receipt.get("response_heads") != _config(root)["scope"]["response_heads"]
        or receipt.get("tasmania_rows_retained") != 0
        or receipt.get("parquet_sha256") != sha256_file(response_path)
    ):
        return None
    parquet = pq.ParquetFile(response_path)
    if parquet.schema_arrow != RESPONSE_SCHEMA or parquet.metadata.num_rows != receipt.get("rows"):
        return None
    expected = _read_json(root / _config(root)["bindings"]["goal042_response_manifest"]["path"])["summary"]["mainland_reference"]
    diagnostics = receipt.get("head_diagnostics", {})
    if set(diagnostics) != set(_config(root)["scope"]["response_heads"]):
        return None
    if any(diagnostics[target].get("replayed_primary_x3_rows") != expected[target]["primary_x3_response_cells"] for target in expected):
        return None
    return receipt


def _rows_from_table(table: pa.Table, store: MainlandStore, *, primary_only: bool = True) -> tuple[ResponseRows, np.ndarray]:
    if primary_only:
        mask = np.asarray(table["is_presence"].to_numpy()) | np.asarray(table["eligible_x3"].to_numpy())
        table = table.filter(pa.array(mask))
    table = table.sort_by("cell_id")
    cells = tuple(table["cell_id"].to_pylist())
    labels = table["is_presence"].to_numpy(zero_copy_only=False).astype(np.int8)
    support = table["other_species_count"].to_numpy(zero_copy_only=False).astype(np.int8)
    _require(cells and all(cell in store.index for cell in cells), "full_response_predictor_binding_invalid")
    folds = np.asarray([store.fold_by_cell[cell] for cell in cells], dtype=np.int8)
    return ResponseRows(cells, labels, folds), support


def apply_strict_focal_subtraction(
    rows: ResponseRows, support: Sequence[int], focal_target_presence: set[str]
) -> tuple[ResponseRows, dict[str, int]]:
    """Subtract focal presence for every auxiliary row, regardless of label."""
    support_array = np.asarray(support, dtype=np.int16)
    _require(support_array.shape == rows.y.shape and np.all(support_array >= 0), "strict_support_invalid")
    overlaps = np.asarray([cell in focal_target_presence for cell in rows.cell_ids], dtype=np.int16)
    adjusted = support_array - overlaps
    _require(np.all(adjusted >= 0), "strict_support_negative")
    keep = (rows.y == 1) | (adjusted >= 3)
    selected = rows.take(np.flatnonzero(keep))
    diagnostics = {
        "original_rows": len(rows.y),
        "original_presences": int(np.sum(rows.y == 1)),
        "original_backgrounds": int(np.sum(rows.y == 0)),
        "focal_target_presence_cells": len(focal_target_presence),
        "focal_overlap_all_rows": int(np.sum(overlaps)),
        "focal_overlap_auxiliary_presences": int(np.sum((rows.y == 1) & (overlaps == 1))),
        "focal_overlap_auxiliary_backgrounds": int(np.sum((rows.y == 0) & (overlaps == 1))),
        "dropped_backgrounds_adjusted_below_x3": int(np.sum((rows.y == 0) & ~keep)),
        "retained_rows": len(selected.y),
        "retained_presences": int(np.sum(selected.y == 1)),
        "retained_backgrounds": int(np.sum(selected.y == 0)),
        "adjusted_support_min": int(np.min(adjusted)),
    }
    _require(diagnostics["retained_presences"] == diagnostics["original_presences"], "strict_presence_loss")
    _require(np.all((rows.y[keep] == 1) | (adjusted[keep] >= 3)), "strict_support_rule_failed")
    return selected, diagnostics


def _response_tables(root: Path) -> dict[str, pa.Table]:
    response_path, _ = _response_paths(root)
    table = pq.read_table(response_path).combine_chunks()
    output: dict[str, pa.Table] = {}
    for target in _config(root)["scope"]["response_heads"]:
        selected = table.filter(pc.equal(table["target"], target))
        _require(selected.num_rows > 0, "response_head_missing")
        output[target] = selected
    return output


def _feature_schema(features: EncodedFeatures) -> dict[str, Any]:
    return {
        "feature_names": list(features.names),
        "feature_kinds": list(features.kinds),
        "continuous_count": features.continuous_count,
        "transform_id": features.transform_id,
        "transform_digest": features.transform_digest,
        "encoder_digest": features.encoder_digest,
        "feature_schema_digest": _canonical_digest({
            "feature_names": features.names,
            "feature_kinds": features.kinds,
            "continuous_count": features.continuous_count,
        }),
    }


def _frozen_feature_schema(root: Path, *, with_q: bool) -> dict[str, Any]:
    """Reconstruct the exact mainland_full schema without reading response rows."""
    transforms = _read_json(root / _config(root)["bindings"]["goal043_transforms"]["path"])
    fit = transforms["transforms"]["mainland_full"]
    vocabulary = transforms["categorical_vocabularies"][fit["categorical_vocabulary_id"]]
    names = list(CONTINUOUS)
    kinds = ["continuous"] * len(CONTINUOUS)
    if with_q:
        names.append("q_linear")
        kinds.append("continuous")
    encoded_levels: dict[str, list[str]] = {}
    for predictor in CATEGORICAL:
        levels = list(vocabulary[predictor]["encoded_levels"])
        encoded_levels[predictor] = levels
        names.extend(f"{predictor}={level}" for level in levels)
        kinds.extend("categorical" for _ in levels)
    transform_payload = {
        "fit_id": "mainland_full",
        "fit": fit,
        "vocabulary": vocabulary,
        "q_linear": with_q,
    }
    return {
        "feature_names": names,
        "feature_kinds": kinds,
        "continuous_count": len(CONTINUOUS) + int(with_q),
        "transform_id": "mainland_full",
        "transform_digest": hashlib.sha256(canonical_json(transform_payload).encode()).hexdigest(),
        "encoder_digest": hashlib.sha256(canonical_json(encoded_levels).encode()).hexdigest(),
        "feature_schema_digest": _canonical_digest({
            "feature_names": names,
            "feature_kinds": kinds,
            "continuous_count": len(CONTINUOUS) + int(with_q),
        }),
    }


def _encode_mainland_full(
    store: MainlandStore,
    cell_ids: Sequence[str],
    q_scores: Sequence[float] | None = None,
) -> EncodedFeatures:
    """Encode rows with the already-frozen Goal 043 mainland_full transform."""
    fit = store.transforms["transforms"]["mainland_full"]
    vocabulary = store.transforms["categorical_vocabularies"][fit["categorical_vocabulary_id"]]
    indices = np.asarray([store.index[cell] for cell in cell_ids], dtype=np.int64)
    raw = np.column_stack([store.continuous[name][indices] for name in CONTINUOUS])
    _require(np.isfinite(raw).all(), "continuous_nodata_in_model_rows")
    continuous = (raw - np.asarray(fit["continuous_mean"])) / np.asarray(fit["continuous_population_sd"])
    names = list(CONTINUOUS)
    kinds = ["continuous"] * len(CONTINUOUS)
    continuous_count = len(CONTINUOUS)
    if q_scores is not None:
        q = np.asarray(q_scores, dtype=np.float64).reshape(-1, 1)
        _require(len(q) == len(indices) and np.isfinite(q).all() and np.all((q >= 0) & (q <= 1)), "q_scores_invalid")
        continuous = np.column_stack((continuous, q))
        names.append("q_linear")
        kinds.append("continuous")
        continuous_count += 1
    encoded_columns: list[np.ndarray] = []
    encoded_levels: dict[str, list[str]] = {}
    for predictor in CATEGORICAL:
        levels = list(vocabulary[predictor]["encoded_levels"])
        _require(MISSING in levels and UNSEEN in levels, "categorical_sentinel_missing")
        allowed = set(vocabulary[predictor]["observed_levels"])
        values = []
        for index in indices:
            raw_value = store.categorical[predictor][index]
            value = MISSING if raw_value is None else str(raw_value)
            values.append(value if value in allowed else UNSEEN)
        values_array = np.asarray(values, dtype=object)
        for level in levels:
            encoded_columns.append((values_array == level).astype(np.float64))
            names.append(f"{predictor}={level}")
            kinds.append("categorical")
        encoded_levels[predictor] = levels
    x = np.column_stack([continuous, *encoded_columns])
    transform_payload = {
        "fit_id": "mainland_full",
        "fit": fit,
        "vocabulary": vocabulary,
        "q_linear": q_scores is not None,
    }
    return EncodedFeatures(
        x,
        tuple(names),
        tuple(kinds),
        continuous_count,
        "mainland_full",
        hashlib.sha256(canonical_json(transform_payload).encode()).hexdigest(),
        hashlib.sha256(canonical_json(encoded_levels).encode()).hexdigest(),
    )


def _score_diagnostics(scores: Sequence[float]) -> dict[str, Any]:
    values = np.asarray(scores, dtype=np.float64)
    _require(len(values) > 1 and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "mainland_training_scores_invalid")
    _require(float(np.ptp(values)) > 0, "mainland_training_scores_constant")
    return {
        "count": len(values),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "nonconstant": True,
    }


def _artifact_paths(root: Path, target: str, seed: str | None, kind: str) -> tuple[Path, Path]:
    base = root / _config(root)["execution"]["private_root"]
    directory = base / "models" / slug(target)
    stem = kind if seed is None else f"{seed}_{kind}"
    suffix = ".pt" if kind == "pretraining" or kind in ARMS else ".json"
    return directory / f"{stem}{suffix}", directory / f"{stem}.receipt.json"


def _expected_task_identity(
    root: Path, freeze_digest: str, implementation_commit: str, response_receipt: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "goal047": _identity(root),
        "freeze_sha256": freeze_digest,
        "implementation_commit": implementation_commit,
        "response_parquet_sha256": response_receipt["parquet_sha256"],
        "response_receipt_sha256": sha256_file(_response_paths(root)[1]),
    }


def _fit_q_model(
    root: Path,
    store: MainlandStore,
    tables: Mapping[str, pa.Table],
    target: str,
    task_identity: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, float]]:
    artifact_path, receipt_path = _artifact_paths(root, target, None, "strict_q_surface")
    heads = [head for head in _config(root)["scope"]["response_heads"] if head != target]
    target_rows, _ = _rows_from_table(tables[target], store)
    target_presence = {cell for cell, label in zip(target_rows.cell_ids, target_rows.y, strict=True) if label == 1}
    row_groups: list[ResponseRows] = []
    support_diagnostics: dict[str, Any] = {}
    for head in heads:
        rows, support = _rows_from_table(tables[head], store)
        selected, diagnostics = apply_strict_focal_subtraction(rows, support, target_presence)
        row_groups.append(selected)
        support_diagnostics[head] = diagnostics
    _require(len(row_groups) == 19 and target not in heads, "strict_q_head_coverage_invalid")
    cells = tuple(cell for rows in row_groups for cell in rows.cell_ids)
    labels = np.concatenate([rows.y for rows in row_groups])
    head_index = np.concatenate([np.full(len(rows.y), index, dtype=np.int64) for index, rows in enumerate(row_groups)])
    weights = equal_head_weights(head_index, len(heads)).astype(np.float64)
    features = _encode_mainland_full(store, cells)
    candidate = dict(CANONICAL_CANDIDATES["enet04"])
    seed = stable_seed(task_identity["freeze_sha256"], "q", target)
    model = LogisticRegression(
        C=float(candidate["C"]),
        l1_ratio=float(candidate["l1_ratio"]),
        penalty="elasticnet",
        solver="saga",
        max_iter=int(candidate["max_iter"]),
        tol=float(candidate["tol"]),
        fit_intercept=True,
        class_weight=None,
        n_jobs=1,
        random_state=seed,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model.fit(features.x, labels, sample_weight=weights)
    _require(not any(issubclass(item.category, ConvergenceWarning) for item in caught), "q_linear_nonconverged")
    _require(int(model.n_iter_[0]) < int(candidate["max_iter"]), "q_linear_nonconverged")
    target_features = _encode_mainland_full(store, target_rows.cell_ids)
    scores = model.predict_proba(target_features.x)[:, 1].astype(np.float64)
    score_diagnostics = _score_diagnostics(scores)
    schema = _feature_schema(target_features)
    artifact = {
        "schema_version": Q_MODEL_SCHEMA,
        "candidate": candidate,
        "fit_seed": seed,
        "feature_schema": schema,
        "coefficient": model.coef_[0].astype(float).tolist(),
        "intercept": float(model.intercept_[0]),
    }
    _atomic_json(artifact_path, artifact)
    q_scaling = {"mean": float(np.mean(scores)), "population_sd": float(np.std(scores, ddof=0))}
    _require(np.isfinite(q_scaling["mean"]) and np.isfinite(q_scaling["population_sd"]) and q_scaling["population_sd"] > 0, "q_scaling_invalid")
    receipt = {
        "schema_version": Q_RECEIPT_SCHEMA,
        "key": {"target": target, "candidate_id": "enet04"},
        "identity": dict(task_identity),
        "auxiliary_heads": heads,
        "auxiliary_head_count": len(heads),
        "focal_head_absent": target not in heads,
        "strict_support_rule": "adjusted_support_equals_other_species_count_minus_focal_presence_for_every_auxiliary_row",
        "support_diagnostics": support_diagnostics,
        "rows_by_head": {head: len(rows.y) for head, rows in zip(heads, row_groups, strict=True)},
        "equal_total_head_weights": True,
        "within_head_class_balancing": False,
        "iterations": int(model.n_iter_[0]),
        "feature_schema": schema,
        "q_scaling": q_scaling,
        "mainland_training_scores": score_diagnostics,
        "artifact_sha256": sha256_file(artifact_path),
    }
    _atomic_json(receipt_path, receipt)
    return receipt, dict(zip(target_rows.cell_ids, scores.tolist(), strict=True))


def _load_q_model(path: Path, expected_sha: str) -> dict[str, Any]:
    _require(path.is_file() and sha256_file(path) == expected_sha, "q_artifact_digest_invalid")
    artifact = _read_json(path)
    _require(artifact.get("schema_version") == Q_MODEL_SCHEMA, "q_artifact_schema_invalid")
    coefficients = np.asarray(artifact.get("coefficient"), dtype=np.float64)
    _require(coefficients.ndim == 1 and np.isfinite(coefficients).all() and np.isfinite(float(artifact.get("intercept"))), "q_artifact_parameters_invalid")
    return artifact


def _predict_q(artifact: Mapping[str, Any], features: EncodedFeatures) -> np.ndarray:
    _require(artifact.get("feature_schema") == _feature_schema(features), "q_feature_schema_mismatch")
    coefficient = np.asarray(artifact["coefficient"], dtype=np.float64)
    _require(len(coefficient) == features.x.shape[1], "q_coefficient_width_invalid")
    scores = expit(features.x @ coefficient + float(artifact["intercept"])).astype(np.float64)
    _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "q_prediction_invalid")
    return scores


def _epoch(freeze: Mapping[str, Any], target: str, seed: str, lifecycle: str, arm: str) -> int:
    rows = [row for row in freeze["epoch_table"]["rows"] if row["target"] == target and row["seed_label"] == seed and row["lifecycle"] == lifecycle and row["arm"] == arm]
    _require(len(rows) == 1, "frozen_epoch_lookup_invalid")
    return int(rows[0]["selected_epoch"])


def _bridge_control_spec(root: Path) -> Any:
    config = _read_json(root / _config(root)["bindings"]["goal046_config"]["path"])
    matches = [
        row
        for row in config["design"]["architecture_candidates"]
        if row["id"] == "bridge_control"
    ]
    _require(len(matches) == 1, "bridge_control_architecture_invalid")
    return architecture_spec(matches[0])


def _validate_neural_checkpoint(
    root: Path,
    state: Mapping[str, torch.Tensor],
    input_width: int,
    *,
    shared_only: bool,
) -> None:
    _require(type(input_width) is int and input_width > 0, "model_feature_width_invalid")
    model = ResidualMLP(_bridge_control_spec(root), input_width)
    try:
        if shared_only:
            load_shared_state(model, state)
        else:
            model.load_state_dict(state, strict=True)
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        raise Goal047Error("model_architecture_state_invalid") from exc


def _exact_target_model(
    x: np.ndarray,
    y: np.ndarray,
    spec: Any,
    epoch: int,
    seed: int,
    *,
    transferred: Mapping[str, torch.Tensor] | None,
    freeze_trunk: bool,
) -> tuple[dict[str, torch.Tensor], np.ndarray]:
    device = resolve_device("cpu")
    seed_all(seed, device)
    model = ResidualMLP(spec, x.shape[1]).to(device)
    _reset_head(model, seed + 17, device)
    if transferred is not None:
        load_shared_state(model, transferred)
    _train_epochs(model, NeuralDataset(x, y), spec, seed + 100_000, device, epoch, 128, None, freeze_trunk)
    scores = _predict(model, x, device, 4096)
    return dict(model.state_dict()), scores


def _exact_pretraining(
    x: np.ndarray,
    y: np.ndarray,
    head_index: np.ndarray,
    weights: np.ndarray,
    head_names: Sequence[str],
    spec: Any,
    epoch: int,
    seed: int,
) -> dict[str, torch.Tensor]:
    device = resolve_device("cpu")
    seed_all(seed, device)
    model = MultiHeadResidual(spec, x.shape[1], tuple(head_names)).to(device)
    dataset = NeuralDataset(x, y, head_index, weights)
    _train_epochs(model, dataset, spec, seed + 100_000, device, epoch, 128, tuple(head_names), False)
    return shared_state(model)


def _serialize_adapter_atomic(fitted: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".json", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        fitted.serialize(temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _method_seed_table(freeze: Mapping[str, Any]) -> dict[str, dict[str, list[str]]]:
    output: dict[str, dict[str, list[str]]] = {}
    for target in TARGETS:
        output[target] = {arm: list(SEEDS) for arm in ARMS}
        seeds = list(freeze["conventional_specs"][target]["seed_labels"])
        output[target]["selected_conventional"] = seeds
        output[target]["strict_q_conventional"] = seeds
    return output


def _expected_model_keys(freeze: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    seeds = _method_seed_table(freeze)
    return {(target, method, seed) for target in TARGETS for method in METHODS for seed in seeds[target][method]}


def _run_target_refits(
    root: Path,
    target: str,
    freeze: Mapping[str, Any],
    task_identity: Mapping[str, Any],
) -> int:
    store = MainlandStore(root)
    tables = _response_tables(root)
    target_rows, _ = _rows_from_table(tables[target], store)
    base_features = _encode_mainland_full(store, target_rows.cell_ids)
    base_batch = make_batch(target, target_rows, base_features)

    q_artifact_path, q_receipt_path = _artifact_paths(root, target, None, "strict_q_surface")
    q_receipt: dict[str, Any] | None = None
    q_scores: np.ndarray | None = None
    if q_receipt_path.is_file() and q_artifact_path.is_file():
        try:
            candidate = _validate_q_receipt(root, target, task_identity)
            artifact = _load_q_model(q_artifact_path, candidate["artifact_sha256"])
            q_scores = _predict_q(artifact, base_features)
            _score_diagnostics(q_scores)
            q_receipt = candidate
        except (Goal047Error, KeyError, OSError, RuntimeError, TypeError, ValueError):
            q_receipt = None
            q_scores = None
    if q_receipt is None or q_scores is None:
        q_receipt, score_map = _fit_q_model(root, store, tables, target, task_identity)
        q_scores = np.asarray([score_map[cell] for cell in target_rows.cell_ids], dtype=np.float64)

    raw_q_features = _encode_mainland_full(store, target_rows.cell_ids, q_scores)
    _require(raw_q_features.names[21] == "q_linear" and raw_q_features.continuous_count == 22, "q_feature_position_invalid")
    neural_q_x = np.asarray(raw_q_features.x, dtype=np.float32).copy()
    neural_q_x[:, 21] = (neural_q_x[:, 21] - q_receipt["q_scaling"]["mean"]) / q_receipt["q_scaling"]["population_sd"]
    goal046_config = _read_json(root / _config(root)["bindings"]["goal046_config"]["path"])
    spec = architecture_spec(next(row for row in goal046_config["design"]["architecture_candidates"] if row["id"] == "bridge_control"))

    auxiliary_heads = [head for head in _config(root)["scope"]["response_heads"] if head != target]
    target_presence = {cell for cell, label in zip(target_rows.cell_ids, target_rows.y, strict=True) if label == 1}
    row_groups: list[ResponseRows] = []
    for head in auxiliary_heads:
        rows, support = _rows_from_table(tables[head], store)
        row_groups.append(apply_strict_focal_subtraction(rows, support, target_presence)[0])
    pre_cells = tuple(cell for rows in row_groups for cell in rows.cell_ids)
    pre_y = np.concatenate([rows.y for rows in row_groups]).astype(np.float32)
    pre_head = np.concatenate([np.full(len(rows.y), index, dtype=np.int64) for index, rows in enumerate(row_groups)])
    pre_features = _encode_mainland_full(store, pre_cells)
    pre_x = pre_features.x.astype(np.float32)
    pre_weights = equal_head_weights(pre_head, len(auxiliary_heads))

    fitted_count = 0
    for seed_label in SEEDS:
        pre_path, pre_receipt_path = _artifact_paths(root, target, seed_label, "pretraining")
        pre_epoch = _epoch(freeze, target, seed_label, "pretraining", "shared_trunk")
        pre_seed = stable_seed(task_identity["freeze_sha256"], "pretraining", target, seed_label)
        expected_pre_key = {"target": target, "seed_label": seed_label, "selected_epoch": pre_epoch, "architecture": "bridge_control"}
        pre_state: dict[str, torch.Tensor] | None = None
        if pre_path.is_file() and pre_receipt_path.is_file():
            try:
                receipt = _validate_pretrain_receipt(root, target, seed_label, freeze, task_identity)
                try:
                    candidate_state = torch.load(pre_path, map_location="cpu", weights_only=True)
                except (OSError, RuntimeError, ValueError):
                    candidate_state = None
                if isinstance(candidate_state, dict) and state_digest(candidate_state) == receipt.get("model_digest"):
                    pre_state = candidate_state
            except (Goal047Error, KeyError, OSError, RuntimeError, TypeError, ValueError):
                pre_state = None
        if pre_state is None:
            pre_state = _exact_pretraining(pre_x, pre_y, pre_head, pre_weights, auxiliary_heads, spec, pre_epoch, pre_seed)
            _atomic_torch(pre_path, pre_state)
            receipt = {
                "schema_version": PRETRAIN_RECEIPT_SCHEMA,
                "key": expected_pre_key,
                "identity": dict(task_identity),
                "fit_seed": pre_seed,
                "auxiliary_heads": auxiliary_heads,
                "auxiliary_head_count": 19,
                "focal_head_absent": target not in auxiliary_heads,
                "equal_total_head_weights": True,
                "within_head_class_balancing": False,
                "training_rows": len(pre_y),
                "feature_schema": _feature_schema(pre_features),
                "model_digest": state_digest(pre_state),
                "artifact_sha256": sha256_file(pre_path),
            }
            _atomic_json(pre_receipt_path, receipt)
            fitted_count += 1

        for method in ARMS:
            model_path, receipt_path = _artifact_paths(root, target, seed_label, method)
            epoch = _epoch(freeze, target, seed_label, "target", method)
            expected_key = {"target": target, "method": method, "seed_label": seed_label, "selected_epoch": epoch}
            if model_path.is_file() and receipt_path.is_file():
                try:
                    _validate_model_receipt(root, (target, method, seed_label), freeze, task_identity)
                    continue
                except (Goal047Error, KeyError, OSError, RuntimeError, TypeError, ValueError):
                    pass
            x = neural_q_x if method == "target_plus_q_linear_resmlp" else np.asarray(base_features.x, dtype=np.float32)
            seed = stable_seed(task_identity["freeze_sha256"], "target", target, method, seed_label)
            transferred = pre_state if method in ARMS[2:] else None
            state, scores = _exact_target_model(x, target_rows.y.astype(np.float32), spec, epoch, seed, transferred=transferred, freeze_trunk=method == "multihead_frozen_trunk")
            _atomic_torch(model_path, state)
            receipt = {
                "schema_version": MODEL_RECEIPT_SCHEMA,
                "key": expected_key,
                "identity": dict(task_identity),
                "family": "residual_mlp",
                "architecture": "bridge_control",
                "fit_seed": seed,
                "exact_epochs": epoch,
                "stopping_labels_used": False,
                "validation_labels_used": False,
                "transferred": method in ARMS[2:],
                "freeze_trunk": method == "multihead_frozen_trunk",
                "pretraining_model_digest": state_digest(pre_state) if method in ARMS[2:] else None,
                "feature_schema": _feature_schema(raw_q_features if method == "target_plus_q_linear_resmlp" else base_features),
                "q_transform": ({"position": 21, "scaling": q_receipt["q_scaling"], "neural_z_scaled": True} if method == "target_plus_q_linear_resmlp" else None),
                "q_binding": ({"artifact_sha256": q_receipt["artifact_sha256"], "receipt_sha256": sha256_file(q_receipt_path)} if method == "target_plus_q_linear_resmlp" else None),
                "mainland_training_scores": _score_diagnostics(scores),
                "model_digest": state_digest(state),
                "artifact_sha256": sha256_file(model_path),
            }
            _atomic_json(receipt_path, receipt)
            fitted_count += 1

    conventional_spec = freeze["conventional_specs"][target]
    for method in ("selected_conventional", "strict_q_conventional"):
        batch = base_batch if method == "selected_conventional" else make_batch(target, target_rows, raw_q_features)
        for seed_label in conventional_spec["seed_labels"]:
            model_path, receipt_path = _artifact_paths(root, target, seed_label, method)
            expected_key = {
                "target": target,
                "method": method,
                "seed_label": seed_label,
                "family": conventional_spec["family"],
                "candidate_id": conventional_spec["candidate_id"],
            }
            if model_path.is_file() and receipt_path.is_file():
                try:
                    _validate_model_receipt(root, (target, method, seed_label), freeze, task_identity)
                    continue
                except (Goal047Error, KeyError, OSError, RuntimeError, TypeError, ValueError):
                    pass
            seed = stable_seed(task_identity["freeze_sha256"], "conventional", target, method, seed_label)
            fitted, report = build_adapter(conventional_spec["family"]).fit(
                batch, None, CANONICAL_CANDIDATES[conventional_spec["candidate_id"]], seed
            )
            _require(report.converged, "conventional_fit_nonconverged")
            scores = fitted.predict_scores(batch)
            _serialize_adapter_atomic(fitted, model_path)
            receipt = {
                "schema_version": MODEL_RECEIPT_SCHEMA,
                "key": expected_key,
                "identity": dict(task_identity),
                "fit_seed": seed,
                "iterations": report.iterations,
                "feature_schema": _feature_schema(raw_q_features if method == "strict_q_conventional" else base_features),
                "q_transform": ({"position": 21, "raw_q": True, "neural_z_scaled": False} if method == "strict_q_conventional" else None),
                "q_binding": ({"artifact_sha256": q_receipt["artifact_sha256"], "receipt_sha256": sha256_file(q_receipt_path)} if method == "strict_q_conventional" else None),
                "mainland_training_scores": _score_diagnostics(scores),
                "artifact_sha256": sha256_file(model_path),
            }
            _atomic_json(receipt_path, receipt)
            fitted_count += 1
    return fitted_count


def _run_target_refits_worker(root: str, target: str, task_identity: Mapping[str, Any]) -> tuple[str, int]:
    resolved = Path(root)
    return target, _run_target_refits(resolved, target, _read_json(resolved / FREEZE_PATH), task_identity)


def _require_refit_authority(root: Path) -> tuple[str, dict[str, Any], str]:
    freeze_path = root / FREEZE_PATH
    _require(_tracked_identical(root, freeze_path), "freeze_not_tracked_and_content_identical")
    _require(_tracked_identical(root, root / SOURCE_PATH) and _tracked_identical(root, root / CONFIG_PATH), "implementation_not_committed")
    commit, clean = _git_state(root)
    _require(clean, "refit_worktree_not_clean")
    validate_freeze(root)
    return commit, _read_json(freeze_path), sha256_file(freeze_path)


def run_full_refits(root: Path, workers: int = 3, device: str = "cpu") -> dict[str, Any]:
    """Run resumable full mainland refits from committed prospective authority."""
    root = root.resolve()
    _require(device == "cpu", "production_device_invalid")
    _require(1 <= workers <= len(TARGETS), "worker_count_invalid")
    validate_inputs(root)
    implementation_commit, freeze, freeze_digest = _require_refit_authority(root)
    response_receipt = _validate_response_substrate(root, freeze_digest)
    if response_receipt is None:
        response_receipt = materialise_full_mainland(root)
        _require(_validate_response_substrate(root, freeze_digest) is not None, "response_substrate_validation_failed")
    task_identity = _expected_task_identity(root, freeze_digest, implementation_commit, response_receipt)
    fitted = 0
    if workers == 1:
        for target in TARGETS:
            fitted += _run_target_refits(root, target, freeze, task_identity)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_run_target_refits_worker, str(root), target, task_identity) for target in TARGETS]
            for future in as_completed(futures):
                _, count = future.result()
                fitted += count
    validation = validate_full_refits(root)
    return {
        "status": "goal047_full_refits_ready",
        "new_artifacts_fitted": fitted,
        "validated_models": validation["model_count"],
        "workers": workers,
        "preopening_tasmania_response_rows_read": 0,
        "preopening_tasmania_predictor_rows_read": 0,
    }


def _validate_q_receipt(root: Path, target: str, task_identity: Mapping[str, Any]) -> dict[str, Any]:
    artifact_path, receipt_path = _artifact_paths(root, target, None, "strict_q_surface")
    receipt = _read_json(receipt_path)
    _require(set(receipt) == {
        "schema_version", "key", "identity", "auxiliary_heads", "auxiliary_head_count",
        "focal_head_absent", "strict_support_rule", "support_diagnostics", "rows_by_head",
        "equal_total_head_weights", "within_head_class_balancing", "iterations",
        "feature_schema", "q_scaling", "mainland_training_scores", "artifact_sha256",
    }, "q_receipt_schema_invalid")
    _require(receipt.get("schema_version") == Q_RECEIPT_SCHEMA, "q_receipt_schema_invalid")
    _require(receipt.get("key") == {"target": target, "candidate_id": "enet04"} and receipt.get("identity") == task_identity, "q_receipt_identity_invalid")
    heads = [head for head in _config(root)["scope"]["response_heads"] if head != target]
    _require(receipt.get("auxiliary_heads") == heads and receipt.get("auxiliary_head_count") == 19 and receipt.get("focal_head_absent") is True, "q_receipt_head_coverage_invalid")
    _require(receipt.get("equal_total_head_weights") is True and receipt.get("within_head_class_balancing") is False, "q_receipt_weighting_invalid")
    _require(receipt.get("artifact_sha256") == sha256_file(artifact_path), "q_receipt_artifact_mismatch")
    artifact = _load_q_model(artifact_path, receipt["artifact_sha256"])
    expected_schema = _frozen_feature_schema(root, with_q=False)
    _require(
        artifact.get("candidate") == dict(CANONICAL_CANDIDATES["enet04"])
        and artifact.get("fit_seed") == stable_seed(task_identity["freeze_sha256"], "q", target)
        and artifact.get("feature_schema") == expected_schema
        and receipt.get("feature_schema") == expected_schema,
        "q_artifact_provenance_invalid",
    )
    store = MainlandStore(root)
    tables = _response_tables(root)
    target_rows, _ = _rows_from_table(tables[target], store)
    features = _encode_mainland_full(store, target_rows.cell_ids)
    scores = _predict_q(artifact, features)
    expected_scaling = {"mean": float(np.mean(scores)), "population_sd": float(np.std(scores, ddof=0))}
    _require(
        receipt.get("q_scaling") == expected_scaling
        and receipt.get("mainland_training_scores") == _score_diagnostics(scores),
        "q_receipt_scores_invalid",
    )
    target_presence = {cell for cell, label in zip(target_rows.cell_ids, target_rows.y, strict=True) if label == 1}
    support_diagnostics: dict[str, Any] = {}
    rows_by_head: dict[str, int] = {}
    for head in heads:
        rows, support = _rows_from_table(tables[head], store)
        selected, diagnostics = apply_strict_focal_subtraction(rows, support, target_presence)
        support_diagnostics[head] = diagnostics
        rows_by_head[head] = len(selected.y)
    _require(
        receipt.get("strict_support_rule") == "adjusted_support_equals_other_species_count_minus_focal_presence_for_every_auxiliary_row"
        and receipt.get("support_diagnostics") == support_diagnostics
        and receipt.get("rows_by_head") == rows_by_head,
        "q_receipt_support_diagnostics_invalid",
    )
    return receipt


def _validate_pretrain_receipt(root: Path, target: str, seed: str, freeze: Mapping[str, Any], task_identity: Mapping[str, Any]) -> dict[str, Any]:
    path, receipt_path = _artifact_paths(root, target, seed, "pretraining")
    receipt = _read_json(receipt_path)
    _require(set(receipt) == {
        "schema_version", "key", "identity", "fit_seed", "auxiliary_heads",
        "auxiliary_head_count", "focal_head_absent", "equal_total_head_weights",
        "within_head_class_balancing", "training_rows", "feature_schema", "model_digest",
        "artifact_sha256",
    }, "pretrain_receipt_schema_invalid")
    expected = {"target": target, "seed_label": seed, "selected_epoch": _epoch(freeze, target, seed, "pretraining", "shared_trunk"), "architecture": "bridge_control"}
    _require(receipt.get("schema_version") == PRETRAIN_RECEIPT_SCHEMA and receipt.get("key") == expected and receipt.get("identity") == task_identity, "pretrain_receipt_identity_invalid")
    heads = [head for head in _config(root)["scope"]["response_heads"] if head != target]
    q_receipt_path = _artifact_paths(root, target, None, "strict_q_surface")[1]
    q_receipt = _read_json(q_receipt_path)
    expected_seed = stable_seed(task_identity["freeze_sha256"], "pretraining", target, seed)
    _require(
        receipt.get("auxiliary_heads") == heads
        and receipt.get("auxiliary_head_count") == 19
        and receipt.get("focal_head_absent") is True
        and receipt.get("equal_total_head_weights") is True
        and receipt.get("within_head_class_balancing") is False
        and receipt.get("fit_seed") == expected_seed
        and receipt.get("training_rows") == sum(q_receipt["rows_by_head"].values())
        and receipt.get("feature_schema") == _frozen_feature_schema(root, with_q=False),
        "pretrain_receipt_heads_invalid",
    )
    _require(receipt.get("artifact_sha256") == sha256_file(path), "pretrain_artifact_digest_invalid")
    state = torch.load(path, map_location="cpu", weights_only=True)
    _require(isinstance(state, dict) and state_digest(state) == receipt.get("model_digest"), "pretrain_model_digest_invalid")
    _validate_neural_checkpoint(
        root,
        state,
        len(receipt["feature_schema"]["feature_names"]),
        shared_only=True,
    )
    return receipt


def _validate_model_receipt(root: Path, key: tuple[str, str, str], freeze: Mapping[str, Any], task_identity: Mapping[str, Any]) -> dict[str, Any]:
    target, method, seed = key
    path, receipt_path = _artifact_paths(root, target, seed, method)
    receipt = _read_json(receipt_path)
    if method in ARMS:
        expected = {"target": target, "method": method, "seed_label": seed, "selected_epoch": _epoch(freeze, target, seed, "target", method)}
        expected_fields = {
            "schema_version", "key", "identity", "family", "architecture", "fit_seed",
            "exact_epochs", "stopping_labels_used", "validation_labels_used", "transferred",
            "freeze_trunk", "pretraining_model_digest", "feature_schema", "q_transform",
            "q_binding", "mainland_training_scores", "model_digest", "artifact_sha256",
        }
    else:
        spec = freeze["conventional_specs"][target]
        expected = {"target": target, "method": method, "seed_label": seed, "family": spec["family"], "candidate_id": spec["candidate_id"]}
        expected_fields = {
            "schema_version", "key", "identity", "fit_seed", "iterations", "feature_schema",
            "q_transform", "q_binding", "mainland_training_scores", "artifact_sha256",
        }
    _require(set(receipt) == expected_fields, "model_receipt_schema_invalid")
    _require(receipt.get("schema_version") == MODEL_RECEIPT_SCHEMA and receipt.get("key") == expected and receipt.get("identity") == task_identity, "model_receipt_identity_invalid")
    _require(receipt.get("artifact_sha256") == sha256_file(path), "model_artifact_digest_invalid")
    scores = receipt.get("mainland_training_scores", {})
    _require(scores.get("nonconstant") is True and 0 <= scores.get("minimum", -1) < scores.get("maximum", 2) <= 1, "model_training_scores_invalid")
    uses_q = method in {"target_plus_q_linear_resmlp", "strict_q_conventional"}
    schema = receipt.get("feature_schema", {})
    _require(schema == _frozen_feature_schema(root, with_q=uses_q), "model_feature_schema_invalid")
    q_receipt_path = _artifact_paths(root, target, None, "strict_q_surface")[1]
    q_receipt = _read_json(q_receipt_path)
    expected_q_binding = ({"artifact_sha256": q_receipt["artifact_sha256"], "receipt_sha256": sha256_file(q_receipt_path)} if uses_q else None)
    _require(receipt.get("q_binding") == expected_q_binding, "model_q_binding_invalid")
    if method in ARMS:
        expected_seed = stable_seed(task_identity["freeze_sha256"], "target", target, method, seed)
        pre_receipt = _read_json(_artifact_paths(root, target, seed, "pretraining")[1])
        _require(
            receipt.get("family") == "residual_mlp"
            and receipt.get("architecture") == "bridge_control"
            and receipt.get("fit_seed") == expected_seed
            and receipt.get("exact_epochs") == expected["selected_epoch"]
            and receipt.get("stopping_labels_used") is False
            and receipt.get("validation_labels_used") is False
            and receipt.get("transferred") is (method in ARMS[2:])
            and receipt.get("freeze_trunk") is (method == "multihead_frozen_trunk")
            and receipt.get("pretraining_model_digest") == (pre_receipt["model_digest"] if method in ARMS[2:] else None),
            "model_neural_provenance_invalid",
        )
        expected_q_transform = ({"position": 21, "scaling": q_receipt["q_scaling"], "neural_z_scaled": True} if uses_q else None)
        _require(receipt.get("q_transform") == expected_q_transform, "model_q_transform_invalid")
        state = torch.load(path, map_location="cpu", weights_only=True)
        _require(isinstance(state, dict) and state_digest(state) == receipt.get("model_digest"), "model_state_digest_invalid")
        _validate_neural_checkpoint(
            root,
            state,
            len(schema["feature_names"]),
            shared_only=False,
        )
    else:
        expected_seed = stable_seed(task_identity["freeze_sha256"], "conventional", target, method, seed)
        expected_q_transform = ({"position": 21, "raw_q": True, "neural_z_scaled": False} if uses_q else None)
        _require(
            receipt.get("fit_seed") == expected_seed
            and type(receipt.get("iterations")) is int
            and receipt["iterations"] >= 0
            and receipt.get("q_transform") == expected_q_transform,
            "model_conventional_provenance_invalid",
        )
        load_fitted_model(path, receipt["artifact_sha256"])
    return receipt


def validate_full_refits(root: Path) -> dict[str, Any]:
    """Independently rehash every expected method-specific private artifact."""
    root = root.resolve()
    implementation_commit, freeze, freeze_digest = _require_refit_authority(root)
    response_receipt = _validate_response_substrate(root, freeze_digest)
    _require(response_receipt is not None, "response_substrate_invalid")
    task_identity = _expected_task_identity(root, freeze_digest, implementation_commit, response_receipt)
    q_inventory: dict[str, Any] = {}
    pretraining_inventory: dict[str, Any] = {}
    model_inventory: dict[str, Any] = {}
    for target in TARGETS:
        receipt = _validate_q_receipt(root, target, task_identity)
        _, receipt_path = _artifact_paths(root, target, None, "strict_q_surface")
        q_inventory[target] = {"artifact_sha256": receipt["artifact_sha256"], "receipt_sha256": sha256_file(receipt_path)}
        for seed in SEEDS:
            pre = _validate_pretrain_receipt(root, target, seed, freeze, task_identity)
            _, pre_receipt_path = _artifact_paths(root, target, seed, "pretraining")
            pretraining_inventory[f"{target}|{seed}|pretraining"] = {"artifact_sha256": pre["artifact_sha256"], "receipt_sha256": sha256_file(pre_receipt_path)}
    expected = _expected_model_keys(freeze)
    for key in sorted(expected):
        receipt = _validate_model_receipt(root, key, freeze, task_identity)
        _, receipt_path = _artifact_paths(root, key[0], key[2], key[1])
        model_inventory["|".join(key)] = {"artifact_sha256": receipt["artifact_sha256"], "receipt_sha256": sha256_file(receipt_path)}
    _require(set(model_inventory) == {"|".join(key) for key in expected}, "model_inventory_exact_keys_invalid")
    inventory = {
        "schema_version": "goal047-validated-inventory-v2",
        "identity": task_identity,
        "response": {
            "parquet_sha256": response_receipt["parquet_sha256"],
            "receipt_sha256": sha256_file(_response_paths(root)[1]),
        },
        "q_inventory": q_inventory,
        "pretraining_inventory": pretraining_inventory,
        "model_inventory": model_inventory,
    }
    inventory_path = root / _config(root)["execution"]["private_root"] / "validated_inventory.json"
    _atomic_json(inventory_path, inventory)
    return {
        "status": "goal047_full_refits_valid",
        "model_count": len(model_inventory),
        "q_count": len(q_inventory),
        "pretraining_count": len(pretraining_inventory),
        "inventory": inventory,
    }


def build_opening_receipt(root: Path, receipt_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    config = _config(root)
    destination = root / (receipt_path or config["execution"]["opening_receipt"])
    _require(not destination.exists(), "opening_receipt_already_exists")
    implementation_commit, freeze, freeze_digest = _require_refit_authority(root)
    validation = validate_full_refits(root)
    inventory = validation["inventory"]
    receipt = {
        "schema_version": "goal047-opening-v2",
        "status": "sealed_ready_for_opening",
        "production_authorized": True,
        "authorities": {
            "goal047_identity": _identity(root),
            "freeze_sha256": freeze_digest,
            "bindings": config["bindings"],
        },
        "epoch_table": freeze["epoch_table"],
        "threshold_table": freeze["threshold_table"],
        "conventional_specs": freeze["conventional_specs"],
        "predictor_authority": freeze["predictor_authority"],
        "response_inventory": inventory["response"],
        "q_inventory": inventory["q_inventory"],
        "pretraining_inventory": inventory["pretraining_inventory"],
        "model_inventory": inventory["model_inventory"],
        "expected_coverage": {
            "targets": list(TARGETS),
            "methods": list(METHODS),
            "neural_seed_labels": list(SEEDS),
            "method_seed_table": _method_seed_table(freeze),
        },
        "preopening_access_counters": {"response_rows_read": 0, "predictor_rows_read": 0},
        "git": {"implementation_commit": implementation_commit, "clean_worktree_before_receipt": True},
    }
    lowered = json.dumps(receipt, sort_keys=True).lower()
    _require(not any(token in lowered for token in PRIVATE_RESULT_TOKENS), "opening_receipt_private_material")
    _atomic_json(destination, receipt)
    return {"status": "goal047_opening_receipt_written", "implementation_commit": implementation_commit}


def _validate_git_predicate(root: Path, receipt_path: Path, implementation_commit: str) -> tuple[str, bool]:
    _require(_tracked_identical(root, receipt_path), "opening_receipt_not_tracked_or_content_drift")
    commit, clean = _git_state(root)
    _require(clean, "opening_worktree_not_clean")
    _require(isinstance(implementation_commit, str) and re.fullmatch(r"[0-9a-f]{40}", implementation_commit) is not None, "opening_implementation_commit_invalid")
    _require(_is_ancestor(root, implementation_commit, commit), "opening_implementation_not_ancestor")
    return commit, clean


def validate_opening_receipt(root: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    _require(set(receipt) == {
        "schema_version", "status", "production_authorized", "authorities", "epoch_table",
        "threshold_table", "conventional_specs", "predictor_authority", "response_inventory",
        "q_inventory", "pretraining_inventory", "model_inventory", "expected_coverage",
        "preopening_access_counters", "git",
    }, "opening_schema_invalid")
    _require(receipt.get("schema_version") == "goal047-opening-v2", "opening_schema_invalid")
    _require(receipt.get("status") == "sealed_ready_for_opening" and receipt.get("production_authorized") is True, "opening_not_authorized")
    freeze = _read_json(root / FREEZE_PATH)
    freeze_validation = validate_freeze(root)
    _require(receipt.get("authorities") == {"goal047_identity": _identity(root), "freeze_sha256": freeze_validation["sha256"], "bindings": _config(root)["bindings"]}, "opening_authority_invalid")
    _require(receipt.get("epoch_table") == freeze["epoch_table"] and receipt.get("threshold_table") == freeze["threshold_table"], "opening_frozen_table_drift")
    _require(receipt.get("conventional_specs") == freeze["conventional_specs"], "opening_conventional_drift")
    _require(receipt.get("predictor_authority") == freeze["predictor_authority"], "opening_predictor_authority_drift")
    _require(receipt.get("preopening_access_counters") == {"response_rows_read": 0, "predictor_rows_read": 0}, "opening_preopening_access_invalid")
    expected_coverage = {"targets": list(TARGETS), "methods": list(METHODS), "neural_seed_labels": list(SEEDS), "method_seed_table": _method_seed_table(freeze)}
    _require(receipt.get("expected_coverage") == expected_coverage, "opening_coverage_invalid")
    implementation_commit = receipt.get("git", {}).get("implementation_commit")
    _require(isinstance(implementation_commit, str) and re.fullmatch(r"[0-9a-f]{40}", implementation_commit) is not None, "opening_implementation_commit_invalid")
    _require(receipt.get("git") == {"implementation_commit": implementation_commit, "clean_worktree_before_receipt": True}, "opening_git_receipt_invalid")
    lowered = json.dumps(receipt, sort_keys=True).lower()
    _require(not any(token in lowered for token in PRIVATE_RESULT_TOKENS), "opening_receipt_private_material")
    response_receipt = _validate_response_substrate(root, freeze_validation["sha256"])
    _require(response_receipt is not None, "opening_response_substrate_invalid")
    task_identity = _expected_task_identity(root, freeze_validation["sha256"], implementation_commit, response_receipt)
    q_inventory: dict[str, Any] = {}
    pretraining_inventory: dict[str, Any] = {}
    model_inventory: dict[str, Any] = {}
    for target in TARGETS:
        q = _validate_q_receipt(root, target, task_identity)
        _, q_receipt_path = _artifact_paths(root, target, None, "strict_q_surface")
        q_inventory[target] = {"artifact_sha256": q["artifact_sha256"], "receipt_sha256": sha256_file(q_receipt_path)}
        for seed in SEEDS:
            pre = _validate_pretrain_receipt(root, target, seed, freeze, task_identity)
            _, pre_receipt_path = _artifact_paths(root, target, seed, "pretraining")
            pretraining_inventory[f"{target}|{seed}|pretraining"] = {"artifact_sha256": pre["artifact_sha256"], "receipt_sha256": sha256_file(pre_receipt_path)}
    for key in sorted(_expected_model_keys(freeze)):
        item = _validate_model_receipt(root, key, freeze, task_identity)
        _, item_receipt_path = _artifact_paths(root, key[0], key[2], key[1])
        model_inventory["|".join(key)] = {"artifact_sha256": item["artifact_sha256"], "receipt_sha256": sha256_file(item_receipt_path)}
    _require(receipt.get("response_inventory") == {"parquet_sha256": response_receipt["parquet_sha256"], "receipt_sha256": sha256_file(_response_paths(root)[1])}, "opening_response_inventory_invalid")
    _require(receipt.get("q_inventory") == q_inventory and receipt.get("pretraining_inventory") == pretraining_inventory and receipt.get("model_inventory") == model_inventory, "opening_inventory_invalid")
    return {"status": "goal047_opening_receipt_valid", "implementation_commit": implementation_commit}


def validate_opening_gate(root: Path, receipt_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    config = _config(root)
    path = root / (receipt_path or config["execution"]["opening_receipt"])
    _require(path.is_file(), "opening_receipt_missing")
    receipt = _read_json(path)
    implementation_commit = receipt.get("git", {}).get("implementation_commit")
    _require(isinstance(implementation_commit, str), "opening_implementation_commit_invalid")
    commit, clean = _validate_git_predicate(root, path, implementation_commit)
    validate_opening_receipt(root, receipt)
    return {
        "status": "goal047_opening_gate_ready",
        "commit": commit,
        "clean_worktree": clean,
        "preopening_tasmania_response_rows_read": 0,
        "preopening_tasmania_predictor_rows_read": 0,
    }


def validate_response_precedence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in rows:
        row = dict(source)
        _require(set(("target", "cell_id", "response", "ala_presence", "camera_presence", "camera_survey_supported_absence")) <= set(row), "response_row_schema_invalid")
        key = (str(row["target"]), str(row["cell_id"]))
        _require(key not in seen, "response_duplicate_target_cell")
        seen.add(key)
        ala = bool(row["ala_presence"])
        camera_presence = bool(row["camera_presence"])
        camera_absence = bool(row["camera_survey_supported_absence"])
        expected = int(ala or camera_presence)
        _require(int(row["response"]) == expected, "response_precedence_invalid")
        if expected == 0:
            _require(camera_absence, "response_zero_without_camera_support")
        _require(ala or camera_presence or camera_absence, "response_without_evidence")
        row["response"] = expected
        output.append(row)
    return output


def source_surface_rows(rows: Iterable[Mapping[str, Any]], surface: str = "primary") -> list[dict[str, Any]]:
    _require(surface in {"primary", "secondary"}, "surface_invalid")
    validated = validate_response_precedence(rows)
    if surface == "secondary":
        return validated
    return [row for row in validated if bool(row["camera_presence"]) or bool(row["camera_survey_supported_absence"])]


select_surface_rows = source_surface_rows


def _normalise_predictions(
    predictions: Mapping[str, Sequence[Mapping[str, Any]]],
    expected_seed_table: Mapping[str, Mapping[str, Sequence[str]]],
) -> dict[str, dict[str, dict[str, dict[tuple[str, str], tuple[float, bool]]]]]:
    _require(set(predictions) == set(METHODS), "prediction_method_coverage_invalid")
    output: dict[str, dict[str, dict[str, dict[tuple[str, str], tuple[float, bool]]]]] = {}
    for method in METHODS:
        by_target: dict[str, dict[str, dict[tuple[str, str], tuple[float, bool]]]] = defaultdict(lambda: defaultdict(dict))
        for row in predictions[method]:
            target, seed = str(row["target"]), str(row["seed_label"])
            _require(target in expected_seed_table and seed in expected_seed_table[target][method], "prediction_seed_unexpected")
            key = (target, str(row["cell_id"]))
            _require(key not in by_target[target][seed], "prediction_duplicate_key")
            score = float(row["score"])
            _require(np.isfinite(score) and 0 <= score <= 1, "prediction_score_invalid")
            by_target[target][seed][key] = (score, bool(row.get("predictor_complete", True)))
        for target in expected_seed_table:
            _require(set(by_target[target]) == set(expected_seed_table[target][method]), "prediction_seed_coverage_invalid")
        output[method] = {target: dict(seeds) for target, seeds in by_target.items()}
    return output


def _null_metrics(reason: str) -> dict[str, Any]:
    return {
        "roc_auc": None,
        "tss": None,
        "balanced_accuracy": None,
        "mcc": None,
        "sensitivity": None,
        "specificity": None,
        "null_reason": reason,
    }


def evaluate_transfer(
    rows: Iterable[Mapping[str, Any]],
    predictions: Mapping[str, Sequence[Mapping[str, Any]]],
    thresholds: Mapping[str, Mapping[str, float]],
    *,
    surface: str = "primary",
    targets: Sequence[str] = TARGETS,
    expected_seed_table: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
) -> dict[str, Any]:
    """Evaluate internally generated predictions into aggregate-only evidence."""
    target_list = list(targets)
    seed_table = expected_seed_table or {target: {method: ["seed00"] for method in METHODS} for target in target_list}
    _require(set(seed_table) == set(target_list), "evaluation_seed_target_coverage_invalid")
    source = source_surface_rows(rows, surface)
    maps = _normalise_predictions(predictions, seed_table)
    _require(set(thresholds) == set(METHODS), "threshold_method_coverage_invalid")
    results: list[dict[str, Any]] = []
    contrast_names = [method for method in METHODS if method != "multihead_full_finetune"]
    contrast_values: dict[str, dict[str, float | None]] = {f"multihead_full_finetune_minus_{method}": {} for method in contrast_names}
    total_common = 0
    for target in target_list:
        selected = [row for row in source if row["target"] == target]
        common: list[dict[str, Any]] = []
        missing = incomplete = 0
        for row in selected:
            key = (target, str(row["cell_id"]))
            values: list[tuple[float, bool]] = []
            complete_key = True
            for method in METHODS:
                for seed in seed_table[target][method]:
                    item = maps[method].get(target, {}).get(seed, {}).get(key)
                    if item is None:
                        complete_key = False
                        break
                    values.append(item)
                if not complete_key:
                    break
            if not complete_key:
                missing += 1
            elif not bool(row.get("predictor_complete", True)) or any(not value[1] for value in values):
                incomplete += 1
            else:
                common.append(row)
        total_common += len(common)
        y = np.asarray([row["response"] for row in common], dtype=np.int8)
        counts = {"surface_rows": len(selected), "common_complete_cells": len(common), "presence_n": int(np.sum(y)), "background_n": int(len(y) - np.sum(y)), "missing_method_prediction": missing, "predictor_incomplete": incomplete}
        methods: dict[str, Any] = {}
        for method in METHODS:
            _require(set(thresholds[method]) >= {target}, "threshold_target_missing")
            threshold = float(thresholds[method][target])
            _require(np.isfinite(threshold) and 0 <= threshold <= 1, "threshold_value_invalid")
            scores = []
            for row in common:
                key = (target, str(row["cell_id"]))
                scores.append(float(np.mean([maps[method][target][seed][key][0] for seed in seed_table[target][method]])))
            if len(y) == 0:
                metrics = _null_metrics("no_common_complete_cells")
            elif len(set(y.tolist())) < 2:
                metrics = _null_metrics("single_class_surface")
            else:
                metric = binary_metrics(y, scores, threshold)
                metrics = {name: metric[name] for name in ("roc_auc", "tss", "balanced_accuracy", "mcc", "sensitivity", "specificity")}
                metrics["null_reason"] = None
            methods[method] = {"threshold": threshold, "seed_count": len(seed_table[target][method]), "metrics": metrics}
        for comparator in contrast_names:
            name = f"multihead_full_finetune_minus_{comparator}"
            primary = methods["multihead_full_finetune"]["metrics"]["roc_auc"]
            other = methods[comparator]["metrics"]["roc_auc"]
            contrast_values[name][target] = None if primary is None or other is None else float(primary - other)
        results.append({"target": target, "counts": counts, "methods": methods})
    contrasts: dict[str, Any] = {}
    for name, values in contrast_values.items():
        nonnull = [value for value in values.values() if value is not None]
        contrasts[name] = {
            "per_species": values,
            "equal_species_mean": None if not nonnull else float(np.mean(nonnull)),
            "equal_species_median": None if not nonnull else float(np.median(nonnull)),
            "nonnull_species_count": len(nonnull),
            "null_species_count": len(values) - len(nonnull),
            "nulls_ignored_in_equal_species_summary": True,
        }
    equal_species_summaries: dict[str, Any] = {}
    for method in METHODS:
        equal_species_summaries[method] = {}
        for metric_name in METRIC_NAMES:
            values = [row["methods"][method]["metrics"][metric_name] for row in results]
            nonnull = [float(value) for value in values if value is not None]
            equal_species_summaries[method][metric_name] = {
                "mean": None if not nonnull else float(np.mean(nonnull)),
                "median": None if not nonnull else float(np.median(nonnull)),
                "nonnull_species_count": len(nonnull),
                "null_species_count": len(values) - len(nonnull),
                "nulls_ignored": True,
            }
    return {
        "schema_version": "goal047-surface-result-v2",
        "surface": surface,
        "targets": target_list,
        "common_complete_cells": total_common,
        "results": results,
        "equal_species_summaries": equal_species_summaries,
        "contrasts": contrasts,
        "privacy": {"cell_level_outputs_tracked": False, "coordinates_tracked": False, "camera_identifiers_tracked": False, "row_payload_tracked": False},
    }


def _create_opening_marker(path: Path, payload: Mapping[str, Any]) -> None:
    """Create and fsync an exclusive durable marker."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise Goal047Error("opening_already_started") from exc
    try:
        raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        written = 0
        while written < len(raw):
            written += os.write(descriptor, raw[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _read_bound_parquet_once(path: Path, expected: Mapping[str, Any], schema: pa.Schema, *, filters: Sequence[tuple[str, str, Any]] | None = None, columns: Sequence[str] | None = None) -> pa.Table:
    """Open one file once, hash its bytes, then parse the verified in-memory copy."""
    with path.open("rb") as handle:
        raw = handle.read()
    _require(len(raw) == expected["bytes"] and hashlib.sha256(raw).hexdigest() == expected["sha256"], "private_input_digest_invalid")
    table = pq.read_table(pa.BufferReader(raw), filters=filters, columns=columns).combine_chunks()
    if filters is None:
        _require(table.schema == schema and table.num_rows == expected["rows"], "private_response_receipt_invalid")
    return table


def _encode_external(table: pa.Table, transforms: Mapping[str, Any], q_scores: Sequence[float] | None = None) -> EncodedFeatures:
    fit = transforms["transforms"]["mainland_full"]
    vocab = transforms["categorical_vocabularies"][fit["categorical_vocabulary_id"]]
    raw = np.column_stack([table[name].to_numpy(zero_copy_only=False).astype(np.float64) for name in CONTINUOUS])
    _require(np.isfinite(raw).all(), "external_continuous_incomplete")
    continuous = (raw - np.asarray(fit["continuous_mean"])) / np.asarray(fit["continuous_population_sd"])
    names = list(CONTINUOUS)
    kinds = ["continuous"] * len(CONTINUOUS)
    continuous_count = len(CONTINUOUS)
    if q_scores is not None:
        q = np.asarray(q_scores, dtype=np.float64).reshape(-1, 1)
        _require(len(q) == len(table) and np.isfinite(q).all() and np.all((q >= 0) & (q <= 1)), "external_q_invalid")
        continuous = np.column_stack((continuous, q))
        names.append("q_linear")
        kinds.append("continuous")
        continuous_count += 1
    encoded_columns: list[np.ndarray] = []
    encoded_levels: dict[str, list[str]] = {}
    for predictor in CATEGORICAL:
        levels = list(vocab[predictor]["encoded_levels"])
        allowed = set(vocab[predictor]["observed_levels"])
        values = [MISSING if value is None else (str(value) if str(value) in allowed else UNSEEN) for value in table[predictor].to_pylist()]
        values_array = np.asarray(values, dtype=object)
        for level in levels:
            encoded_columns.append((values_array == level).astype(np.float64))
            names.append(f"{predictor}={level}")
            kinds.append("categorical")
        encoded_levels[predictor] = levels
    x = np.column_stack([continuous, *encoded_columns])
    transform_payload = {"fit_id": "mainland_full", "fit": fit, "vocabulary": vocab, "q_linear": q_scores is not None}
    return EncodedFeatures(
        x,
        tuple(names),
        tuple(kinds),
        continuous_count,
        "mainland_full",
        hashlib.sha256(canonical_json(transform_payload).encode()).hexdigest(),
        hashlib.sha256(canonical_json(encoded_levels).encode()).hexdigest(),
    )


def _external_batch(target: str, cells: Sequence[str], features: EncodedFeatures) -> FeatureBatch:
    schema = _feature_schema(features)
    return FeatureBatch(
        tuple(RowKey(target, cell) for cell in cells),
        features.x,
        np.zeros(len(cells), dtype=np.float64),
        features.names,
        features.kinds,
        features.continuous_count,
        schema["feature_schema_digest"],
        {},
        features.transform_id,
        features.transform_digest,
        features.encoder_digest,
    )


def _predict_private_models(
    root: Path,
    response_rows: Sequence[Mapping[str, Any]],
    predictor_table: pa.Table,
    opening: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    transforms = _read_json(root / _config(root)["bindings"]["goal043_transforms"]["path"])
    predictor_cells = predictor_table["cell_id"].to_pylist()
    predictor_index = {cell: index for index, cell in enumerate(predictor_cells)}
    _require(len(predictor_cells) == len(predictor_index), "tasmania_predictor_duplicate_cell")
    output: dict[str, list[dict[str, Any]]] = {method: [] for method in METHODS}
    used_cells: set[str] = set()
    goal046_config = _read_json(root / _config(root)["bindings"]["goal046_config"]["path"])
    spec = architecture_spec(next(row for row in goal046_config["design"]["architecture_candidates"] if row["id"] == "bridge_control"))
    for target in TARGETS:
        rows = [row for row in response_rows if row["target"] == target]
        available = [row for row in rows if row["cell_id"] in predictor_index]
        indices = np.asarray([predictor_index[row["cell_id"]] for row in available], dtype=np.int64)
        selected = predictor_table.take(pa.array(indices))
        complete = np.ones(len(selected), dtype=bool)
        for name in CONTINUOUS:
            complete &= np.isfinite(selected[name].to_numpy(zero_copy_only=False).astype(np.float64))
        complete_indices = np.flatnonzero(complete)
        incomplete_rows = [available[index] for index in np.flatnonzero(~complete)]
        complete_table = selected.take(pa.array(complete_indices))
        complete_rows = [available[index] for index in complete_indices]
        cells = [row["cell_id"] for row in complete_rows]
        used_cells.update(cells)
        seed_table = opening["expected_coverage"]["method_seed_table"][target]
        if not complete_rows:
            for method in METHODS:
                for seed in seed_table[method]:
                    output[method].extend(
                        {
                            "target": target,
                            "cell_id": row["cell_id"],
                            "seed_label": seed,
                            "score": 0.5,
                            "predictor_complete": False,
                        }
                        for row in incomplete_rows
                    )
            continue
        base = _encode_external(complete_table, transforms)
        q_path, q_receipt_path = _artifact_paths(root, target, None, "strict_q_surface")
        q_receipt = _read_json(q_receipt_path)
        q_artifact = _load_q_model(q_path, q_receipt["artifact_sha256"])
        q_scores = _predict_q(q_artifact, base)
        raw_q = _encode_external(complete_table, transforms, q_scores)
        neural_q = np.asarray(raw_q.x, dtype=np.float32).copy()
        neural_q[:, 21] = (neural_q[:, 21] - q_receipt["q_scaling"]["mean"]) / q_receipt["q_scaling"]["population_sd"]
        for method in METHODS:
            for seed in seed_table[method]:
                path, receipt_path = _artifact_paths(root, target, seed, method)
                receipt = _read_json(receipt_path)
                if method in ARMS:
                    state = torch.load(path, map_location="cpu", weights_only=True)
                    x = neural_q if method == "target_plus_q_linear_resmlp" else np.asarray(base.x, dtype=np.float32)
                    model = ResidualMLP(spec, x.shape[1])
                    model.load_state_dict(state, strict=True)
                    scores = _predict(model, x, resolve_device("cpu"), 4096)
                else:
                    fitted = load_fitted_model(path, receipt["artifact_sha256"])
                    batch = _external_batch(target, cells, raw_q if method == "strict_q_conventional" else base)
                    scores = fitted.predict_scores(batch)
                _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "production_prediction_invalid")
                output[method].extend({"target": target, "cell_id": cell, "seed_label": seed, "score": float(score), "predictor_complete": True} for cell, score in zip(cells, scores, strict=True))
                output[method].extend({"target": target, "cell_id": row["cell_id"], "seed_label": seed, "score": 0.5, "predictor_complete": False} for row in incomplete_rows)
    return output, len(used_cells)


def _postopening_predictor_diagnostics(table: pa.Table, authority: Mapping[str, Any]) -> dict[str, Any]:
    continuous: dict[str, Any] = {}
    for name in CONTINUOUS:
        values = table[name].to_numpy(zero_copy_only=False).astype(np.float64)
        finite = np.isfinite(values)
        bounds = authority["continuous_ranges"][name]
        continuous[name] = {
            "below_mainland_minimum": int(np.sum(finite & (values < bounds["minimum"]))),
            "above_mainland_maximum": int(np.sum(finite & (values > bounds["maximum"]))),
            "missing": int(np.sum(~finite)),
        }
    categorical: dict[str, Any] = {}
    vocabulary = authority["categorical_vocabulary"]
    for name in CATEGORICAL:
        allowed = set(vocabulary[name]["observed_levels"])
        values = table[name].to_pylist()
        categorical[name] = {
            "unseen_nonmissing": sum(value is not None and str(value) not in allowed for value in values),
            "missing": sum(value is None for value in values),
        }
    return {"continuous_out_of_mainland_range": continuous, "categorical_unseen": categorical, "descriptive_only_no_model_changes": True}


def one_shot_evaluate(root: Path) -> dict[str, Any]:
    """Perform the irreversible internally predicted Tasmania opening."""
    root = root.resolve()
    gate = validate_opening_gate(root)
    config = _config(root)
    opening_path = root / config["execution"]["opening_receipt"]
    opening = _read_json(opening_path)
    private = root / config["execution"]["private_root"]
    completed = private / "opening_completed.json"
    _require(not completed.exists(), "opening_already_completed")
    marker = private / "opening_started.json"
    _create_opening_marker(marker, {"schema_version": "goal047-opening-started-v2", "status": "started", "gate_commit": gate["commit"], "opening_receipt_sha256": sha256_file(opening_path)})

    response_manifest = _read_json(root / config["bindings"]["goal042_response_manifest"]["path"])
    response_receipt = response_manifest["outputs"]["private_output_roles"]["tasmania_evaluation_response"]
    response_path = root / goal042.OUTPUT_ROOT / goal042.TASMANIA_FILE
    response_table = _read_bound_parquet_once(response_path, response_receipt, goal042.TASMANIA_SCHEMA)
    response_rows = validate_response_precedence(response_table.to_pylist())
    _require(set(row["target"] for row in response_rows) == set(TARGETS), "tasmania_response_target_coverage_invalid")

    predictor_manifest = _read_json(root / config["bindings"]["goal041_table_manifest"]["path"])
    predictor_path = root / goal042.PREDICTOR_PATH
    predictor_expected = {"bytes": os.path.getsize(predictor_path), "sha256": predictor_manifest["final_sha256"]}
    predictor_table = _read_bound_parquet_once(
        predictor_path,
        predictor_expected,
        pa.schema([]),
        filters=[("region", "=", goal042.TASMANIA_REGION)],
        columns=["cell_id", "region", *CONTINUOUS, *CATEGORICAL],
    )
    _require(predictor_table.num_rows == predictor_manifest["regions"]["tasmania"], "tasmania_predictor_row_count_invalid")
    observed_schema = [
        {"name": field.name, "type": str(field.type), "nullable": field.nullable}
        for field in predictor_table.schema
    ]
    _require(observed_schema == predictor_manifest["schema"], "tasmania_predictor_schema_invalid")
    predictor_cells = set(predictor_table["cell_id"].to_pylist())
    _require({row["cell_id"] for row in response_rows} <= predictor_cells, "tasmania_response_predictor_binding_invalid")
    predictions, predictor_rows_used = _predict_private_models(root, response_rows, predictor_table, opening)
    surfaces = {
        surface: evaluate_transfer(
            response_rows,
            predictions,
            opening["threshold_table"],
            surface=surface,
            expected_seed_table=opening["expected_coverage"]["method_seed_table"],
        )
        for surface in ("primary", "secondary")
    }
    access = {
        "response_file_opens": 1,
        "predictor_file_opens": 1,
        "response_rows_read": len(response_rows),
        "predictor_rows_read": predictor_table.num_rows,
        "predictor_rows_used": predictor_rows_used,
    }
    _require(
        access["response_file_opens"] == access["predictor_file_opens"] == 1
        and access["response_rows_read"] > 0
        and access["predictor_rows_read"] > 0
        and 0 <= access["predictor_rows_used"] <= access["predictor_rows_read"],
        "postopening_access_counters_invalid",
    )
    result = {
        "schema_version": "goal047-transfer-result-v2",
        "status": "production_complete",
        "surfaces": surfaces,
        "postopening_predictor_diagnostics": _postopening_predictor_diagnostics(predictor_table, opening["predictor_authority"]),
        "preopening_access_counters": opening["preopening_access_counters"],
        "postopening_access_counters": access,
        "privacy": {"cell_level_outputs_tracked": False, "coordinates_tracked": False, "camera_identifiers_tracked": False, "row_payload_tracked": False},
    }
    _atomic_json(root / config["execution"]["tracked_summary"], result)
    _atomic_json(completed, {"schema_version": "goal047-opening-completed-v2", "status": "complete", "access_counters": access, "result_sha256": sha256_file(root / config["execution"]["tracked_summary"])})
    return {"status": "goal047_evaluation_complete", "postopening_access_counters": access}


def _result_privacy() -> dict[str, bool]:
    return {
        "cell_level_outputs_tracked": False,
        "coordinates_tracked": False,
        "camera_identifiers_tracked": False,
        "row_payload_tracked": False,
    }


def _metric_value_valid(name: str, value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value):
        return False
    lower = -1.0 if name in {"tss", "mcc"} else 0.0
    return lower <= float(value) <= 1.0


def _validate_result_metrics(metrics: Mapping[str, Any]) -> None:
    _require(set(metrics) == {*METRIC_NAMES, "null_reason"}, "result_metric_schema_invalid")
    null_reason = metrics["null_reason"]
    if null_reason is None:
        _require(all(_metric_value_valid(name, metrics[name]) for name in METRIC_NAMES), "result_metric_value_invalid")
    else:
        _require(
            null_reason in {"no_common_complete_cells", "single_class_surface"}
            and all(metrics[name] is None for name in METRIC_NAMES),
            "result_metric_null_invalid",
        )


def _validate_surface_result(
    value: Mapping[str, Any],
    surface: str,
    threshold_table: Mapping[str, Mapping[str, float]],
    method_seed_table: Mapping[str, Mapping[str, Sequence[str]]],
) -> dict[str, Mapping[str, Any]]:
    _require(set(value) == {
        "schema_version", "surface", "targets", "common_complete_cells", "results",
        "equal_species_summaries", "contrasts", "privacy",
    }, "result_surface_schema_invalid")
    _require(
        value.get("schema_version") == "goal047-surface-result-v2"
        and value.get("surface") == surface
        and value.get("targets") == list(TARGETS),
        "result_target_coverage_invalid",
    )
    rows = value.get("results")
    _require(
        isinstance(rows, list)
        and [row.get("target") for row in rows if isinstance(row, Mapping)] == list(TARGETS),
        "result_target_rows_invalid",
    )
    by_target: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        _require(set(row) == {"target", "counts", "methods"}, "result_target_schema_invalid")
        target = row["target"]
        counts = row["counts"]
        _require(set(counts) == {
            "surface_rows", "common_complete_cells", "presence_n", "background_n",
            "missing_method_prediction", "predictor_incomplete",
        }, "result_count_schema_invalid")
        _require(all(type(item) is int and item >= 0 for item in counts.values()), "result_count_value_invalid")
        _require(
            counts["presence_n"] + counts["background_n"] == counts["common_complete_cells"]
            and counts["common_complete_cells"] + counts["missing_method_prediction"] + counts["predictor_incomplete"] == counts["surface_rows"],
            "result_count_identity_invalid",
        )
        methods = row["methods"]
        _require(set(methods) == set(METHODS), "result_method_coverage_invalid")
        for method in METHODS:
            item = methods[method]
            _require(set(item) == {"threshold", "seed_count", "metrics"}, "result_method_schema_invalid")
            _require(
                _metric_value_valid("roc_auc", item["threshold"])
                and type(item["seed_count"]) is int
                and float(item["threshold"]) == float(threshold_table[method][target])
                and item["seed_count"] == len(method_seed_table[target][method]),
                "result_method_authority_invalid",
            )
            _validate_result_metrics(item["metrics"])
        by_target[target] = row
    _require(
        type(value["common_complete_cells"]) is int
        and value["common_complete_cells"] >= 0
        and value["common_complete_cells"] == sum(row["counts"]["common_complete_cells"] for row in rows),
        "result_common_complete_count_invalid",
    )

    summaries = value["equal_species_summaries"]
    _require(set(summaries) == set(METHODS), "result_equal_species_summary_invalid")
    for method in METHODS:
        _require(set(summaries[method]) == set(METRIC_NAMES), "result_equal_species_summary_invalid")
        for metric_name in METRIC_NAMES:
            item = summaries[method][metric_name]
            _require(set(item) == {"mean", "median", "nonnull_species_count", "null_species_count", "nulls_ignored"}, "result_equal_species_schema_invalid")
            values = [row["methods"][method]["metrics"][metric_name] for row in rows]
            nonnull = [float(metric) for metric in values if metric is not None]
            _require(
                item["nonnull_species_count"] == len(nonnull)
                and item["null_species_count"] == len(values) - len(nonnull)
                and item["nulls_ignored"] is True,
                "result_equal_species_count_invalid",
            )
            if nonnull:
                _require(
                    _metric_value_valid(metric_name, item["mean"])
                    and _metric_value_valid(metric_name, item["median"])
                    and np.isclose(item["mean"], np.mean(nonnull), rtol=0, atol=1e-12)
                    and np.isclose(item["median"], np.median(nonnull), rtol=0, atol=1e-12),
                    "result_equal_species_value_invalid",
                )
            else:
                _require(item["mean"] is None and item["median"] is None, "result_equal_species_null_invalid")

    comparators = [method for method in METHODS if method != "multihead_full_finetune"]
    expected_contrasts = {f"multihead_full_finetune_minus_{method}": method for method in comparators}
    contrasts = value["contrasts"]
    _require(set(contrasts) == set(expected_contrasts), "result_contrast_coverage_invalid")
    for name, comparator in expected_contrasts.items():
        item = contrasts[name]
        _require(set(item) == {
            "per_species", "equal_species_mean", "equal_species_median",
            "nonnull_species_count", "null_species_count",
            "nulls_ignored_in_equal_species_summary",
        }, "result_contrast_schema_invalid")
        per_species = item["per_species"]
        _require(set(per_species) == set(TARGETS), "result_contrast_target_invalid")
        expected_values: list[float] = []
        for target in TARGETS:
            primary = by_target[target]["methods"]["multihead_full_finetune"]["metrics"]["roc_auc"]
            other = by_target[target]["methods"][comparator]["metrics"]["roc_auc"]
            expected = None if primary is None or other is None else float(primary - other)
            observed = per_species[target]
            _require(
                (expected is None and observed is None)
                or (expected is not None and isinstance(observed, (int, float)) and not isinstance(observed, bool) and np.isfinite(observed) and np.isclose(observed, expected, rtol=0, atol=1e-12)),
                "result_contrast_value_invalid",
            )
            if expected is not None:
                expected_values.append(expected)
        _require(
            item["nonnull_species_count"] == len(expected_values)
            and item["null_species_count"] == len(TARGETS) - len(expected_values)
            and item["nulls_ignored_in_equal_species_summary"] is True,
            "result_contrast_count_invalid",
        )
        if expected_values:
            _require(
                np.isclose(item["equal_species_mean"], np.mean(expected_values), rtol=0, atol=1e-12)
                and np.isclose(item["equal_species_median"], np.median(expected_values), rtol=0, atol=1e-12),
                "result_contrast_summary_invalid",
            )
        else:
            _require(item["equal_species_mean"] is None and item["equal_species_median"] is None, "result_contrast_null_invalid")
    _require(value["privacy"] == _result_privacy(), "result_surface_privacy_invalid")
    return by_target


def _validate_postopening_diagnostics(value: Mapping[str, Any]) -> None:
    _require(set(value) == {
        "continuous_out_of_mainland_range", "categorical_unseen",
        "descriptive_only_no_model_changes",
    }, "result_predictor_diagnostics_schema_invalid")
    continuous = value["continuous_out_of_mainland_range"]
    categorical = value["categorical_unseen"]
    _require(set(continuous) == set(CONTINUOUS) and set(categorical) == set(CATEGORICAL), "result_predictor_diagnostics_coverage_invalid")
    _require(
        all(
            set(continuous[name]) == {"below_mainland_minimum", "above_mainland_maximum", "missing"}
            and all(type(item) is int and item >= 0 for item in continuous[name].values())
            for name in CONTINUOUS
        )
        and all(
            set(categorical[name]) == {"unseen_nonmissing", "missing"}
            and all(type(item) is int and item >= 0 for item in categorical[name].values())
            for name in CATEGORICAL
        )
        and value["descriptive_only_no_model_changes"] is True,
        "result_predictor_diagnostics_value_invalid",
    )


def _result_opening_authority(
    root: Path,
    config: Mapping[str, Any],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, list[str]]]]:
    opening_path = root / config["execution"]["opening_receipt"]
    _require(
        opening_path.is_file() and _tracked_identical(root, opening_path),
        "result_opening_receipt_not_tracked_or_content_drift",
    )
    opening = _read_json(opening_path)
    _require(
        opening.get("schema_version") == "goal047-opening-v2"
        and opening.get("status") == "sealed_ready_for_opening"
        and opening.get("production_authorized") is True,
        "result_opening_receipt_invalid",
    )
    thresholds = opening.get("threshold_table")
    coverage = opening.get("expected_coverage", {})
    seeds = coverage.get("method_seed_table")
    _require(
        isinstance(thresholds, Mapping)
        and set(thresholds) == set(METHODS)
        and all(
            isinstance(thresholds[method], Mapping)
            and set(thresholds[method]) == set(TARGETS)
            and all(_metric_value_valid("roc_auc", thresholds[method][target]) for target in TARGETS)
            for method in METHODS
        ),
        "result_opening_threshold_authority_invalid",
    )
    _require(
        coverage.get("targets") == list(TARGETS)
        and coverage.get("methods") == list(METHODS)
        and coverage.get("neural_seed_labels") == list(SEEDS)
        and isinstance(seeds, Mapping)
        and set(seeds) == set(TARGETS)
        and all(
            isinstance(seeds[target], Mapping)
            and set(seeds[target]) == set(METHODS)
            and all(
                isinstance(seeds[target][method], list)
                and len(seeds[target][method]) > 0
                and len(seeds[target][method]) == len(set(seeds[target][method]))
                and set(seeds[target][method]) <= set(SEEDS)
                and (method not in ARMS or seeds[target][method] == list(SEEDS))
                for method in METHODS
            )
            for target in TARGETS
        ),
        "result_opening_seed_authority_invalid",
    )
    return (
        {method: {target: float(thresholds[method][target]) for target in TARGETS} for method in METHODS},
        {target: {method: list(seeds[target][method]) for method in METHODS} for target in TARGETS},
    )


def validate_result(root: Path, result_path: Path | None = None) -> dict[str, Any]:
    """Validate an aggregate result without reopening private inputs."""
    root = root.resolve()
    config = _config(root)
    path = root / (result_path or config["execution"]["tracked_summary"])
    _require(path.is_file(), "result_missing")
    result = _read_json(path)
    lowered = json.dumps(result, sort_keys=True).lower()
    _require(not any(token in lowered for token in PRIVATE_RESULT_TOKENS), "result_contains_private_material")
    _require(set(result) == {
        "schema_version", "status", "surfaces", "postopening_predictor_diagnostics",
        "preopening_access_counters", "postopening_access_counters", "privacy",
    }, "result_schema_invalid")
    _require(result.get("schema_version") == "goal047-transfer-result-v2", "result_schema_invalid")
    _require(result.get("status") == "production_complete", "result_status_invalid")
    threshold_table, method_seed_table = _result_opening_authority(root, config)
    _require(set(result.get("surfaces", {})) == {"primary", "secondary"}, "result_surface_coverage_invalid")
    surface_rows = {
        surface: _validate_surface_result(
            result["surfaces"][surface],
            surface,
            threshold_table,
            method_seed_table,
        )
        for surface in ("primary", "secondary")
    }
    _require(
        all(
            surface_rows["primary"][target]["counts"]["surface_rows"]
            <= surface_rows["secondary"][target]["counts"]["surface_rows"]
            for target in TARGETS
        ),
        "result_surface_nesting_invalid",
    )
    _validate_postopening_diagnostics(result["postopening_predictor_diagnostics"])
    _require(result.get("preopening_access_counters") == {"response_rows_read": 0, "predictor_rows_read": 0}, "result_preopening_access_invalid")
    access = result.get("postopening_access_counters", {})
    _require(
        set(access) == {"response_file_opens", "predictor_file_opens", "response_rows_read", "predictor_rows_read", "predictor_rows_used"}
        and all(type(value) is int for value in access.values())
        and access["response_file_opens"] == access["predictor_file_opens"] == 1
        and access["response_rows_read"] > 0
        and access["predictor_rows_read"] > 0
        and 0 <= access["predictor_rows_used"] <= access["predictor_rows_read"]
        and access["response_rows_read"] == sum(surface_rows["secondary"][target]["counts"]["surface_rows"] for target in TARGETS),
        "result_postopening_access_invalid",
    )
    _require(result.get("privacy") == _result_privacy(), "result_privacy_invalid")
    completed_path = root / config["execution"]["private_root"] / "opening_completed.json"
    _require(completed_path.is_file(), "result_completion_receipt_missing")
    completed = _read_json(completed_path)
    _require(
        set(completed) == {"schema_version", "status", "access_counters", "result_sha256"}
        and completed.get("schema_version") == "goal047-opening-completed-v2"
        and completed.get("status") == "complete"
        and completed.get("access_counters") == access
        and completed.get("result_sha256") == sha256_file(path),
        "result_completion_receipt_invalid",
    )
    return {"status": "goal047_result_valid", "targets": len(TARGETS), "postopening_access_counters": access}


def mainland_canary(root: Path, device: str = "cpu") -> dict[str, Any]:
    """Run the existing bounded mainland-only bridge-control canary."""
    root = root.resolve()
    _require(device == "cpu", "canary_device_invalid")
    gate = validate_inputs(root)
    config = _config(root)
    case = config["execution"]["canary"]
    store = MainlandStore(root)
    goal046_config = _read_json(root / config["bindings"]["goal046_config"]["path"])
    state, pretraining = goal046.run_pretraining_task(
        root,
        store,
        goal046_config,
        _goal046_identity(root),
        case["target"],
        int(case["held_fold"]),
        "bridge_control",
        "seed00",
        device,
        max_epochs=int(case["max_epochs"]),
        patience=int(case["patience"]),
        checkpoint=False,
    )
    _require(len(state) > 0 and pretraining["fit"]["auxiliary_head_count"] == 19, "canary_pretraining_invalid")
    return {
        "status": "goal047_canary_ready",
        "gate": gate,
        "selected_epoch": pretraining["fit"]["selected_epoch"],
        "auxiliary_head_count": 19,
        "preopening_tasmania_response_rows_read": 0,
        "preopening_tasmania_predictor_rows_read": 0,
    }


def status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = _config(root)
    private = root / config["execution"]["private_root"]
    return {
        "status": config["status"],
        "production_run": (private / "opening_completed.json").is_file(),
        "opening_started": (private / "opening_started.json").is_file(),
        "opening_receipt_exists": (root / config["execution"]["opening_receipt"]).is_file(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "validate-inputs",
            "freeze",
            "validate-freeze",
            "canary",
            "run-full-refits",
            "validate-full-refits",
            "build-opening-receipt",
            "validate-opening-gate",
            "evaluate",
            "validate-result",
            "status",
        ],
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--device", choices=["cpu"], default="cpu")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--opening-receipt", type=Path)
    args = parser.parse_args(argv)
    if args.command == "validate-inputs":
        result = validate_inputs(args.root)
    elif args.command == "freeze":
        result = prepare(args.root)
    elif args.command == "validate-freeze":
        result = validate_freeze(args.root)
    elif args.command == "canary":
        result = mainland_canary(args.root, args.device)
    elif args.command == "run-full-refits":
        result = run_full_refits(args.root, args.workers, args.device)
    elif args.command == "validate-full-refits":
        result = validate_full_refits(args.root)
    elif args.command == "build-opening-receipt":
        result = build_opening_receipt(args.root, args.opening_receipt)
    elif args.command == "validate-opening-gate":
        result = validate_opening_gate(args.root, args.opening_receipt)
    elif args.command == "evaluate":
        result = one_shot_evaluate(args.root)
    elif args.command == "validate-result":
        result = validate_result(args.root)
    else:
        result = status(args.root)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
