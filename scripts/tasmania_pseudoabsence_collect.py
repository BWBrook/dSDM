"""Close the response-free Tasmania pseudoabsence prediction panel.

This collector performs no fitting and never opens the canonical outer-held
response table.  It authenticates the completed neural and conventional
lanes, joins every seed prediction by canonical cell identity, derives the
seven-endpoint OOF thresholds, and writes the immutable prediction bundle that
the separately gated assessment may later score.

The command is deliberately execution-gated::

    python scripts/tasmania_pseudoabsence_collect.py collect --execute

Without ``--execute`` it refuses before reading model leaves or writing output.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence
import zipfile

import numpy as np

from tasmania_pseudoabsence_metrics import select_threshold


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_BASE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private")
NEURAL_REL = PRIVATE_BASE_REL / "neural/results"
CONVENTIONAL_REL = PRIVATE_BASE_REL / "conventional"
ASSESSMENT_REL = PRIVATE_BASE_REL / "assessment"
INPUT_MANIFEST_REL = PRIVATE_BASE_REL / "neural/input-manifest.json"
INPUTS_REL = PRIVATE_BASE_REL / "neural/inputs"
BASELINE_REL = Path("data/processed/dsdm/tasmania-outer-assessment-20261005/private")
RECOVERY_REL = Path("evidence/tasmania_pseudoabsence/20261009/auxiliary-recovery.json")
ASSESSMENT_SOURCE_REL = Path("scripts/tasmania_pseudoabsence_assessment.py")
METRICS_SOURCE_REL = Path("scripts/tasmania_pseudoabsence_metrics.py")
NEURAL_SOURCE_REL = Path("scripts/tasmania_pseudoabsence_neural.py")
CONVENTIONAL_SOURCE_REL = Path("scripts/tasmania_pseudoabsence_conventional.py")

SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
FOLDS = tuple(f"fold{i:02d}" for i in range(5))
ENDPOINTS = (
    "fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02",
    "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02",
    "fraction100/full",
)
METHODS = ("target_only_resmlp", "multihead_full_finetune", "selected_conventional")
NEURAL_METHODS = METHODS[:2]
NEURAL_SEEDS = (31031, 31032, 31033, 31034, 31035)
BASE_NEURAL = (
    "target_only_resmlp", "legacy_pooled_finetune", "multihead_frozen_trunk",
    "multihead_full_finetune", "target_plus_q_linear", "target_plus_q_deep",
)
BASE_CONVENTIONAL = (
    "intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann",
)
BASELINE_RECEIPT_DIGEST = "6b1240538079be2219a22502625e34c473fce4c56c1030f5a302b4cacd6cb77e"
INPUT_MANIFEST_DIGEST = "e1b6d585f8dfe2a0a4569b89cb09799c24cebb95060034a51580b4cb08bd39a8"
INPUT_HELPER_SHA256 = "192780828d695f27a149ed049774e0668966d9f8682a53439ec57909d6e5d4bc"
RECOVERY_SHA256 = "2d86a42321dcbaf1abca9f6cb592e9c6f7bb41e5d59c8e97c683c8fe8464c4f9"
EXPECTED_HELD_ROWS = 1672
EXPECTED_MAP_ROWS = 71023


class CollectionError(ValueError):
    """Raised when response-free prediction closure must fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CollectionError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_digest(array: np.ndarray) -> str:
    """Shape-aware digest used in the normalized source-leaf inventory."""
    value = np.ascontiguousarray(array)
    descriptor = f"{value.dtype.str}|{value.shape}".encode("ascii")
    return hashlib.sha256(descriptor + b"\0" + value.tobytes(order="C")).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    require(target.is_file() and not target.is_symlink(), f"source_json_missing:{target}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectionError(f"source_json_invalid:{target}") from exc
    require(isinstance(value, dict), f"source_json_object_required:{target}")
    return value


def validate_self_digest(value: Mapping[str, Any], key: str, message: str) -> str:
    body = dict(value)
    claimed = body.pop(key, None)
    require(
        isinstance(claimed, str) and len(claimed) == 64 and digest_value(body) == claimed,
        message,
    )
    return claimed


def read_receipt(path: str | Path, *, key: str = "receipt_digest") -> dict[str, Any]:
    value = read_json(path)
    validate_self_digest(value, key, f"receipt_digest_mismatch:{Path(path)}")
    return value


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"module_import_failed:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def module_bundle(root: Path) -> tuple[ModuleType, ModuleType, ModuleType]:
    archive = root / "data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1/src"
    if str(archive) not in sys.path:
        sys.path.insert(0, str(archive))
    suffix = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    neural = load_module(root / NEURAL_SOURCE_REL, f"_tas_collect_neural_{suffix}")
    conventional = load_module(root / CONVENTIONAL_SOURCE_REL, f"_tas_collect_conventional_{suffix}")
    assessment = load_module(root / ASSESSMENT_SOURCE_REL, f"_tas_collect_assessment_{suffix}")
    return neural, conventional, assessment


def validate_input_manifest(root: Path) -> dict[str, Any]:
    path = root / INPUT_MANIFEST_REL
    manifest = read_json(path)
    body = dict(manifest)
    claimed = body.pop("digest", None)
    require(claimed == INPUT_MANIFEST_DIGEST and digest_value(body) == claimed, "input_manifest_digest_mismatch")
    require(
        manifest.get("success") is True and manifest.get("fits") == 0
        and manifest.get("outer_response_labels_read") == 0,
        "input_manifest_response_boundary_invalid",
    )
    require(manifest.get("script_sha256") == INPUT_HELPER_SHA256, "input_helper_manifest_binding_mismatch")
    helper = root / "scripts/tasmania_pseudoabsence_neural_data.py"
    require(sha256_file(helper) == INPUT_HELPER_SHA256, "input_helper_source_changed")
    records = manifest.get("files")
    require(isinstance(records, list) and len(records) == 49, "input_manifest_inventory_invalid")
    paths: set[str] = set()
    for record in records:
        require(
            isinstance(record, dict) and set(record) == {"path", "sha256", "metadata_digest"},
            "input_manifest_record_invalid",
        )
        relative = str(record["path"])
        require(relative not in paths, "input_manifest_duplicate_path")
        paths.add(relative)
        source = (root / relative).resolve()
        require(root.resolve() in source.parents and sha256_file(source) == record["sha256"], f"input_file_changed:{relative}")
    return manifest


def read_npz(path: Path, expected: set[str] | None = None) -> dict[str, np.ndarray]:
    require(path.is_file() and not path.is_symlink(), f"prediction_file_missing:{path}")
    try:
        with np.load(path, allow_pickle=False) as loaded:
            if expected is not None:
                require(set(loaded.files) == expected, f"prediction_array_inventory_mismatch:{path}")
            return {name: np.array(loaded[name], copy=True) for name in loaded.files}
    except CollectionError:
        raise
    except (OSError, ValueError) as exc:
        raise CollectionError(f"prediction_file_invalid:{path}") from exc


def validate_ids(ids: np.ndarray, *, expected_length: int | None = None, label: str = "ids") -> np.ndarray:
    value = np.asarray(ids)
    require(value.ndim == 1 and value.dtype.kind == "U", f"{label}_invalid")
    require(len(set(value.tolist())) == len(value), f"{label}_duplicate")
    if expected_length is not None:
        require(len(value) == expected_length, f"{label}_length_mismatch")
    return value


def align_vector(expected_ids: np.ndarray, observed_ids: np.ndarray, values: np.ndarray, *, label: str) -> np.ndarray:
    expected = validate_ids(np.asarray(expected_ids), label=f"{label}_expected_ids")
    observed = validate_ids(np.asarray(observed_ids), label=f"{label}_observed_ids")
    score = np.asarray(values)
    require(score.ndim == 1 and score.shape == observed.shape, f"{label}_score_shape_mismatch")
    require(set(observed.tolist()) == set(expected.tolist()), f"{label}_membership_mismatch")
    lookup = {str(cell): index for index, cell in enumerate(observed)}
    return score[np.asarray([lookup[str(cell)] for cell in expected], dtype=np.int64)]


def mean_seed_predictions(
    records: Sequence[tuple[Any, np.ndarray, np.ndarray]],
    expected_seeds: Sequence[Any],
    expected_ids: np.ndarray,
    *,
    label: str,
) -> np.ndarray:
    """Average one complete seed panel after an identity join."""
    expected = tuple(expected_seeds)
    require(len(records) == len(expected), f"{label}_seed_count_mismatch")
    by_seed: dict[Any, tuple[np.ndarray, np.ndarray]] = {}
    for seed, ids, scores in records:
        require(seed not in by_seed, f"{label}_duplicate_seed")
        by_seed[seed] = (ids, scores)
    require(set(by_seed) == set(expected), f"{label}_seed_inventory_mismatch")
    aligned = [
        np.asarray(align_vector(expected_ids, *by_seed[seed], label=f"{label}:{seed}"), dtype=np.float64)
        for seed in expected
    ]
    result = np.mean(np.stack(aligned, axis=0), axis=0, dtype=np.float64)
    require(np.isfinite(result).all() and np.all((result >= 0) & (result <= 1)), f"{label}_mean_invalid")
    return result


def deterministic_npz_bytes(arrays: Mapping[str, np.ndarray]) -> bytes:
    """Write a byte-stable NumPy archive with fixed ZIP metadata."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in arrays:
            payload = io.BytesIO()
            np.lib.format.write_array(payload, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, payload.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def write_idempotent(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == raw, f"immutable_output_drift:{path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    try:
        os.link(temporary, path)
    except FileExistsError:
        require(path.read_bytes() == raw, f"concurrent_output_drift:{path}")
    finally:
        temporary.unlink(missing_ok=True)


def write_json_receipt(path: Path, body: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(body)
    value["receipt_digest"] = digest_value(value)
    write_idempotent(path, canonical(value) + b"\n")
    return value


def validate_probability_payload(
    arrays: Mapping[str, np.ndarray], *, expect_map: bool, neural: bool, label: str,
) -> None:
    expected = {"grid_cell_id", "scores"}
    if expect_map:
        expected |= (
            {"map_grid_cell_id", "sensitivity_map_scores", "accepted_primary_map_scores"}
            if neural else {"map_grid_cell_id", "map_scores", "baseline_map_scores"}
        )
    require(set(arrays) == expected, f"{label}_array_inventory_invalid")
    ids = validate_ids(arrays["grid_cell_id"], label=f"{label}_held_ids")
    scores = np.asarray(arrays["scores"])
    require(scores.shape == ids.shape and scores.ndim == 1, f"{label}_held_shape_invalid")
    expected_dtype = np.float32 if neural else np.float64
    require(scores.dtype == expected_dtype, f"{label}_held_dtype_invalid")
    require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), f"{label}_held_probability_invalid")
    if expect_map:
        map_ids = validate_ids(arrays["map_grid_cell_id"], expected_length=EXPECTED_MAP_ROWS, label=f"{label}_map_ids")
        names = ("sensitivity_map_scores", "accepted_primary_map_scores") if neural else ("map_scores", "baseline_map_scores")
        for name in names:
            values = np.asarray(arrays[name])
            require(values.shape == map_ids.shape and values.dtype == expected_dtype, f"{label}_{name}_invalid")
            require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), f"{label}_{name}_probability_invalid")


def _relative(root: Path, path: Path) -> str:
    resolved = path.resolve()
    require(root.resolve() in resolved.parents, f"source_outside_root:{path}")
    return str(resolved.relative_to(root.resolve()))


def _source_record(root: Path, role: str, path: Path) -> dict[str, str]:
    require(path.is_file() and not path.is_symlink(), f"source_binding_invalid:{role}")
    return {"role": role, "path": _relative(root, path), "sha256": sha256_file(path)}


def validate_source_receipts(
    root: Path, neural: ModuleType, conventional: ModuleType,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    """Authenticate closures and derive fit counts from their leaf evidence."""
    neural_root = root / NEURAL_REL
    conventional_root = root / CONVENTIONAL_REL
    neural_preparation = read_receipt(neural_root / "preparation.json")
    neural_smoke = read_receipt(neural_root / "smoke-qualification.json")
    neural_caps = read_receipt(neural_root / "production-caps.json")
    neural_inner = read_receipt(neural_root / "inner-closure.json")
    neural_outer = read_receipt(neural_root / "outer-closure.json")
    neural_complete = read_receipt(neural_root / "closure.json")
    conventional_preparation = read_receipt(conventional_root / "preparation.json")
    conventional_smoke = read_receipt(conventional_root / "smoke-qualification.json")
    conventional_caps = read_receipt(conventional_root / "production-caps.json")
    conventional_inner = read_receipt(conventional_root / "inner-closure.json")
    conventional_outer = read_receipt(conventional_root / "outer-closure.json")
    recovery_path = root / RECOVERY_REL
    recovery = read_json(recovery_path)
    require(sha256_file(recovery_path) == RECOVERY_SHA256, "recovery_receipt_changed")

    require(neural_preparation.get("schema_version") == "tasmania-pseudoabsence-neural-preparation-v2" and neural_preparation.get("success") is True and neural_preparation.get("fitting") is False, "neural_preparation_not_accepted")
    require(neural_smoke.get("schema_version") == "tasmania-pseudoabsence-neural-smoke-v2" and neural_smoke.get("success") is True and neural_smoke.get("non_promotable") is True, "neural_smoke_not_accepted")
    require(neural_caps.get("schema_version") == "tasmania-pseudoabsence-neural-production-caps-v2" and neural_caps.get("status") == "approved", "neural_caps_not_approved")
    require(conventional_preparation.get("schema_version") == "tasmania-pseudoabsence-conventional-preparation-v1" and conventional_preparation.get("success") is True and conventional_preparation.get("fitting") is False, "conventional_preparation_not_accepted")
    require(conventional_smoke.get("schema_version") == "tasmania-pseudoabsence-conventional-smoke-v1" and conventional_smoke.get("success") is True and conventional_smoke.get("non_promotable") is True, "conventional_smoke_not_accepted")
    require(conventional_caps.get("schema_version") == "tasmania-pseudoabsence-conventional-production-caps-v1" and conventional_caps.get("status") == "assigned", "conventional_caps_not_assigned")
    require(recovery.get("schema_version") == "tasmania-auxiliary-recovery-v1" and recovery.get("status") == "accepted" and recovery.get("states") == recovery.get("fits") == 200, "recovery_not_accepted")
    require(recovery.get("outer_opened") == 0 and recovery.get("outer_attempted") == 0, "recovery_response_boundary_breached")

    for value, lane, logical, physical in (
        (neural_inner, "inner", 2800, 5600), (neural_outer, "outer", 560, 560),
        (conventional_inner, "inner", 1200, 1725), (conventional_outer, "outer", 240, 240),
    ):
        framework = "neural" if logical in (2800, 560) else "conventional"
        expected_schema = f"tasmania-pseudoabsence-{framework}-{lane}-closure-{'v2' if framework == 'neural' else 'v1'}"
        require(value.get("schema_version") == expected_schema and value.get("success") is True and value.get("lane") == lane, f"{value.get('schema_version')}_not_accepted")
        records = value.get("records")
        require(isinstance(records, list) and len(records) == logical, f"{value.get('schema_version')}_record_count_invalid")
        require(digest_value(records) == value.get("inventory_digest"), f"{value.get('schema_version')}_inventory_digest_invalid")
        require(sum(int(row.get("physical_fits", -1)) for row in records) == physical, f"{value.get('schema_version')}_leaf_fit_sum_invalid")
        require(value.get("logical_tasks") == logical and value.get("physical_fits") == physical, f"{value.get('schema_version')}_declared_scope_invalid")

    require(
        neural_complete.get("success") is True
        and neural_complete.get("schema_version") == "tasmania-pseudoabsence-neural-complete-closure-v2"
        and neural_complete.get("logical_tasks") == 3360
        and neural_complete.get("inner_closure_receipt_digest") == neural_inner["receipt_digest"]
        and neural_complete.get("outer_closure_receipt_digest") == neural_outer["receipt_digest"]
        and neural_complete.get("physical_fits") == 6160
        and neural_complete.get("outer_held_response_labels_read") == 0,
        "neural_complete_closure_invalid",
    )
    require(neural_inner.get("outer_held_response_labels_read") == 0 and neural_outer.get("outer_held_response_labels_read") == 0, "neural_response_boundary_breached")
    require(conventional_inner.get("held_response_vault_read") is False and conventional_outer.get("held_response_vault_read") is False, "conventional_response_boundary_breached")
    require(neural_smoke.get("outer_held_response_labels_read") == 0, "neural_smoke_response_boundary_breached")
    require(conventional_smoke.get("held_response_vault_read") is False, "conventional_smoke_response_boundary_breached")

    # Link every closure to the accepted preparation and production caps.
    require(neural_smoke.get("preparation_receipt_digest") == neural_preparation["receipt_digest"], "neural_smoke_preparation_link_invalid")
    require(neural_caps.get("preparation_receipt_digest") == neural_preparation["receipt_digest"] and neural_caps.get("smoke_receipt_digest") == neural_smoke["receipt_digest"], "neural_caps_link_invalid")
    require(neural_inner.get("production_caps_receipt_digest") == neural_caps["receipt_digest"] and neural_outer.get("production_caps_receipt_digest") == neural_caps["receipt_digest"], "neural_lane_caps_link_invalid")
    require(conventional_smoke.get("preparation_receipt_digest") == conventional_preparation["receipt_digest"], "conventional_smoke_preparation_link_invalid")
    require(conventional_caps.get("preparation_receipt_digest") == conventional_preparation["receipt_digest"] and conventional_caps.get("smoke_receipt_digest") == conventional_smoke["receipt_digest"], "conventional_caps_link_invalid")
    require(conventional_inner.get("production_caps_receipt_digest") == conventional_caps["receipt_digest"] and conventional_outer.get("production_caps_receipt_digest") == conventional_caps["receipt_digest"], "conventional_lane_caps_link_invalid")
    require(
        neural_inner.get("bindings") == neural_preparation.get("bindings")
        and neural_outer.get("bindings") == neural_preparation.get("bindings")
        and neural_complete.get("bindings") == neural_preparation.get("bindings"),
        "neural_closure_preparation_binding_invalid",
    )
    require(
        conventional_inner.get("bindings") == conventional_preparation.get("bindings")
        and conventional_outer.get("bindings") == conventional_preparation.get("bindings"),
        "conventional_closure_preparation_binding_invalid",
    )

    current_neural_sha = sha256_file(root / NEURAL_SOURCE_REL)
    current_conventional_sha = sha256_file(root / CONVENTIONAL_SOURCE_REL)
    require(neural_preparation.get("bindings", {}).get("runner_sha256") == current_neural_sha, "neural_runner_changed_after_preparation")
    require(conventional_preparation.get("bindings", {}).get("script_sha256") == current_conventional_sha, "conventional_runner_changed_after_preparation")

    source_closures = [
        _source_record(root, "neural_inner", neural_root / "inner-closure.json"),
        _source_record(root, "neural_outer", neural_root / "outer-closure.json"),
        _source_record(root, "conventional_inner", conventional_root / "inner-closure.json"),
        _source_record(root, "conventional_outer", conventional_root / "outer-closure.json"),
        _source_record(root, "neural_smoke", neural_root / "smoke-qualification.json"),
        _source_record(root, "conventional_smoke", conventional_root / "smoke-qualification.json"),
        _source_record(root, "recovery", recovery_path),
    ]
    source_bindings = [
        _source_record(root, "neural_complete", neural_root / "closure.json"),
        _source_record(root, "neural_preparation", neural_root / "preparation.json"),
        _source_record(root, "neural_caps", neural_root / "production-caps.json"),
        _source_record(root, "conventional_preparation", conventional_root / "preparation.json"),
        _source_record(root, "conventional_caps", conventional_root / "production-caps.json"),
        _source_record(root, "neural_runner", root / NEURAL_SOURCE_REL),
        _source_record(root, "conventional_runner", root / CONVENTIONAL_SOURCE_REL),
        _source_record(root, "input_manifest", root / INPUT_MANIFEST_REL),
        _source_record(root, "input_helper", root / "scripts/tasmania_pseudoabsence_neural_data.py"),
        _source_record(root, "assessment_source", root / ASSESSMENT_SOURCE_REL),
        _source_record(root, "metrics_source", root / METRICS_SOURCE_REL),
        _source_record(root, "collector_source", root / "scripts/tasmania_pseudoabsence_collect.py"),
    ]
    counts = {
        "neural_inner": sum(int(row["physical_fits"]) for row in neural_inner["records"]),
        "neural_outer": sum(int(row["physical_fits"]) for row in neural_outer["records"]),
        "conventional_inner": sum(int(row["physical_fits"]) for row in conventional_inner["records"]),
        "conventional_outer": sum(int(row["physical_fits"]) for row in conventional_outer["records"]),
        "neural_smoke": int(neural_smoke.get("physical_fits", -1)),
        "conventional_smoke": int(conventional_smoke.get("physical_fits", -1)),
        "recovery": int(recovery.get("fits", -1)),
    }
    require(counts["neural_smoke"] == 8 and counts["conventional_smoke"] == 6, "smoke_fit_inventory_invalid")
    closures = {
        "neural_inner": neural_inner, "neural_outer": neural_outer,
        "conventional_inner": conventional_inner, "conventional_outer": conventional_outer,
    }
    preparations = {"neural": neural_preparation, "conventional": conventional_preparation}
    caps = {"neural": neural_caps, "conventional": conventional_caps}
    return closures, preparations, caps, source_closures, source_bindings, counts


def _neural_attempt_physical_starts(root: Path, lane: str, task_digest: str, receipt: Mapping[str, Any]) -> int:
    lane_root = root / NEURAL_REL / lane
    intent_path = lane_root / "intents" / f"{task_digest}.json"
    attempt = lane_root / "attempts" / task_digest
    intent = read_json(intent_path)
    attempt_intent = read_json(attempt / "intent.json")
    running = read_json(attempt / "running.json")
    completed = read_json(attempt / "completed.json")
    require(intent == attempt_intent, f"neural_{lane}_intent_copy_mismatch")
    require(intent.get("task_digest") == task_digest and intent.get("task") == receipt.get("task"), f"neural_{lane}_intent_identity_mismatch")
    stages = intent.get("physical_stages")
    require(isinstance(stages, list) and len(stages) == receipt.get("physical_fits"), f"neural_{lane}_physical_stage_mismatch")
    require(running.get("task_digest") == task_digest and running.get("fit_started") is True, f"neural_{lane}_fit_start_missing")
    require(completed.get("task_digest") == task_digest and completed.get("receipt_digest") == receipt.get("receipt_digest"), f"neural_{lane}_completion_mismatch")
    require(not (attempt / "failed.json").exists() and not (attempt / "cancelled.json").exists(), f"neural_{lane}_failed_attempt_present")
    return len(stages)


def _conventional_attempt_physical_starts(root: Path, lane: str, task_digest: str, receipt: Mapping[str, Any]) -> int:
    lane_root = root / CONVENTIONAL_REL / lane
    intent = read_receipt(lane_root / "intents" / f"{task_digest}.json", key="intent_digest")
    attempt = lane_root / "attempts" / task_digest
    require(intent.get("task_digest") == task_digest and intent.get("task") == receipt.get("task"), f"conventional_{lane}_intent_identity_mismatch")
    stages = intent.get("physical_stages")
    require(isinstance(stages, list) and len(stages) == receipt.get("physical_fits"), f"conventional_{lane}_physical_stage_mismatch")
    starts = attempt / "fit-starts"
    entries = sorted(starts.iterdir()) if starts.is_dir() else []
    require(len(entries) == len(stages) and all(path.is_file() and not path.is_symlink() for path in entries), f"conventional_{lane}_fit_start_inventory_mismatch")
    for number, (stage, path) in enumerate(zip(stages, entries, strict=True), start=1):
        start = read_json(path)
        require(start.get("task") == receipt.get("task") and start.get("stage") == stage and start.get("physical_fit_number") == number, f"conventional_{lane}_fit_start_invalid")
    completed = read_json(attempt / "completed.json")
    require(completed.get("task_digest") == task_digest and completed.get("receipt_digest") == receipt.get("receipt_digest"), f"conventional_{lane}_completion_mismatch")
    require(not (attempt / "failed.json").exists(), f"conventional_{lane}_failed_attempt_present")
    return len(entries)


def _validate_neural_scope_boundary(receipt: Mapping[str, Any], lane: str, role: str) -> None:
    """Validate the lane-specific production/smoke marker contract.

    Inner v2 receipts always carry the explicit production marker.  Frozen
    outer v2 receipts predate that redundant field and omit it, while the
    runner's own validator treats omission as the production default.  An
    explicit outer marker is accepted only when it is the boolean ``False``;
    truthy or non-boolean values remain fail-closed.
    """
    require(lane in {"inner", "outer"}, f"{role}_leaf_lane_invalid")
    if lane == "inner":
        require(
            "smoke_non_promotable" in receipt
            and receipt["smoke_non_promotable"] is False,
            f"{role}_leaf_scope_boundary_invalid",
        )
    elif "smoke_non_promotable" in receipt:
        require(
            receipt["smoke_non_promotable"] is False,
            f"{role}_leaf_scope_boundary_invalid",
        )
    response_reads = receipt.get("outer_held_response_labels_read")
    require(
        type(response_reads) is int and response_reads == 0,
        f"{role}_leaf_scope_boundary_invalid",
    )


def validate_leaf(
    root: Path, role: str, task: Any, runner: ModuleType, closure_row: Mapping[str, Any],
    preparation: Mapping[str, Any], production_caps_receipt_digest: str,
) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, Any], int]:
    lane = "inner" if role.endswith("inner") else "outer"
    neural = role.startswith("neural")
    base = root / (NEURAL_REL if neural else CONVENTIONAL_REL)
    task_digest = runner._task_digest(task, lane)
    require(task_digest == closure_row.get("task_digest"), f"{role}_closure_task_digest_mismatch")
    leaf = base / lane / "leaves" / task_digest
    require(leaf.is_dir() and not leaf.is_symlink(), f"{role}_leaf_missing")
    expected_files = {"receipt.json", "predictions.npz", "model.pt"} if neural else {
        "receipt.json", "predictions.npz", "model.model", "encoder.json",
    }
    if not neural and (leaf / "discovery.model").exists():
        expected_files.add("discovery.model")
    require(
        {item.name for item in leaf.iterdir()} == expected_files
        and all(item.is_file() and not item.is_symlink() for item in leaf.iterdir()),
        f"{role}_leaf_file_inventory_mismatch",
    )
    receipt_path = leaf / "receipt.json"
    receipt = read_receipt(receipt_path)
    expected_schema = f"tasmania-pseudoabsence-{'neural' if neural else 'conventional'}-{lane}-leaf-{'v2' if neural else 'v1'}"
    require(receipt.get("schema_version") == expected_schema, f"{role}_leaf_schema_mismatch")
    require(receipt.get("task") == asdict(task) and receipt.get("task_digest") == task_digest, f"{role}_leaf_task_identity_mismatch")
    require(receipt.get("receipt_digest") == closure_row.get("receipt_digest"), f"{role}_leaf_receipt_not_in_closure")
    require(receipt.get("physical_fits") == closure_row.get("physical_fits"), f"{role}_leaf_fit_count_mismatch")
    require(receipt.get("bindings") == preparation.get("bindings"), f"{role}_leaf_preparation_binding_mismatch")
    require(receipt.get("production_caps_receipt_digest") == production_caps_receipt_digest, f"{role}_leaf_caps_binding_mismatch")
    if neural:
        _validate_neural_scope_boundary(receipt, lane, role)
    else:
        require(
            receipt.get("preparation_receipt_digest") == preparation.get("receipt_digest")
            and receipt.get("held_response_vault_read") is False
            and receipt.get("labels_in_prediction_batch") is False,
            f"{role}_leaf_scope_boundary_invalid",
        )
    prediction_path = leaf / "predictions.npz"
    require(sha256_file(prediction_path) == receipt.get("prediction_sha256"), f"{role}_prediction_sha_mismatch")
    arrays = read_npz(prediction_path)
    expect_map = lane == "outer" and task.endpoint == "fraction100/full"
    validate_probability_payload(arrays, expect_map=expect_map, neural=neural, label=f"{role}:{task_digest}")
    if neural:
        require(runner.array_digest(arrays["scores"]) == receipt.get("prediction_digest"), f"{role}_prediction_digest_mismatch")
        model_path = leaf / "model.pt"
        model_sha = receipt.get("model_receipt", {}).get("model_sha256")
        model_state_digest = receipt.get("model_digest")
        model_identity_digest = receipt.get("model_receipt", {}).get("identity_digest")
        auxiliary_artifacts: list[dict[str, str]] = []
        starts = _neural_attempt_physical_starts(root, lane, task_digest, receipt)
        if expect_map:
            require(runner.array_digest(arrays["sensitivity_map_scores"]) == receipt.get("map", {}).get("prediction_digest"), f"{role}_map_digest_mismatch")
            require(runner.array_digest(arrays["accepted_primary_map_scores"]) == receipt.get("accepted_primary_map", {}).get("prediction_digest"), f"{role}_primary_map_digest_mismatch")
        require(
            closure_row.get("model_sha256") == model_sha
            and closure_row.get("model_state_digest") == model_state_digest
            and closure_row.get("prediction_sha256") == receipt.get("prediction_sha256")
            and closure_row.get("prediction_digest") == receipt.get("prediction_digest"),
            f"{role}_closure_leaf_content_mismatch",
        )
    else:
        require(runner._prediction_digest(arrays["grid_cell_id"].tolist(), arrays["scores"]) == receipt.get("prediction_digest"), f"{role}_prediction_digest_mismatch")
        model_path = leaf / "model.model"
        model_sha = receipt.get("model_sha256")
        model_state_digest = receipt.get("model_semantic_digest")
        model_identity_digest = receipt.get("model_identity_digest")
        encoder_path = leaf / "encoder.json"
        require(sha256_file(encoder_path) == receipt.get("encoder_sha256"), f"{role}_encoder_sha_mismatch")
        auxiliary_artifacts = [{"role": "encoder", "path": _relative(root, encoder_path), "sha256": receipt["encoder_sha256"]}]
        discovery_path = leaf / "discovery.model"
        if discovery_path.exists():
            require(sha256_file(discovery_path) == receipt.get("discovery_model_sha256"), f"{role}_discovery_model_sha_mismatch")
            auxiliary_artifacts.append({"role": "discovery_model", "path": _relative(root, discovery_path), "sha256": receipt["discovery_model_sha256"]})
        starts = _conventional_attempt_physical_starts(root, lane, task_digest, receipt)
        if expect_map:
            require(runner._prediction_digest(arrays["map_grid_cell_id"].tolist(), arrays["map_scores"]) == receipt.get("map", {}).get("prediction_digest"), f"{role}_map_digest_mismatch")
            require(runner._prediction_digest(arrays["map_grid_cell_id"].tolist(), arrays["baseline_map_scores"]) == receipt.get("accepted_primary_map", {}).get("prediction_digest"), f"{role}_primary_map_digest_mismatch")
        require(
            closure_row.get("model_sha256") == model_sha
            and closure_row.get("prediction_digest") == receipt.get("prediction_digest"),
            f"{role}_closure_leaf_content_mismatch",
        )
    require(model_path.is_file() and not model_path.is_symlink() and sha256_file(model_path) == model_sha, f"{role}_model_sha_mismatch")
    require(starts == receipt.get("physical_fits"), f"{role}_actual_fit_starts_mismatch")
    inventory = {
        "role": role, "lane": lane, "task": asdict(task), "task_digest": task_digest,
        "leaf_path": _relative(root, leaf),
        "receipt_path": _relative(root, receipt_path), "receipt_sha256": sha256_file(receipt_path),
        "receipt_digest": receipt["receipt_digest"],
        "model_path": _relative(root, model_path), "model_sha256": model_sha,
        "model_state_digest": model_state_digest, "model_identity_digest": model_identity_digest,
        "auxiliary_artifacts": auxiliary_artifacts,
        "prediction_path": _relative(root, prediction_path),
        "prediction_sha256": receipt["prediction_sha256"],
        "prediction_receipt_digest": receipt["prediction_digest"],
        "array_digests": {name: array_digest(arrays[name]) for name in sorted(arrays)},
        "identity_digest": digest_value({
            "role": role, "task": asdict(task), "task_digest": task_digest,
            "evaluation_id_digest": array_digest(arrays["grid_cell_id"]),
            "bindings": receipt.get("bindings"),
        }),
        "physical_fit_starts": starts,
    }
    return receipt, arrays, inventory, starts


def _closure_rows(closure: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = closure["records"]
    result = {str(row["task_digest"]): row for row in rows}
    require(len(result) == len(rows), "closure_duplicate_task_digest")
    return result


def _baseline_arrays(root: Path, species: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    inputs = read_npz(root / BASELINE_REL / "inputs" / f"{species}.npz")
    cells = validate_ids(inputs["grid_cell_id"], label=f"primary:{species}:cells")
    patch = np.asarray(inputs["patch"])
    require(patch.shape == cells.shape and patch.dtype.kind == "U", f"primary:{species}:patch_invalid")
    means = read_npz(root / BASELINE_REL / "predictions/averaged" / f"{species}.npz", {"neural_mean", "conventional_mean"})
    neural = means["neural_mean"]
    conventional = means["conventional_mean"]
    require(neural.shape == (7, 6, len(cells)) and neural.dtype == np.float64, f"primary:{species}:neural_invalid")
    require(conventional.shape == (7, 5, len(cells)) and conventional.dtype == np.float64, f"primary:{species}:conventional_invalid")
    return cells, patch, neural, conventional


def _input_inner(root: Path, species: str, fold: str) -> tuple[np.ndarray, np.ndarray]:
    arrays = read_npz(root / INPUTS_REL / "inner" / f"{species}--{fold}.npz")
    cells = validate_ids(arrays["held_cells"], label=f"inner_input:{species}:{fold}:cells")
    labels = np.asarray(arrays["y_held"])
    require(labels.shape == cells.shape and np.isin(labels, [0, 1]).all(), f"inner_input:{species}:{fold}:labels_invalid")
    return cells, labels.astype(np.int8)


def _input_outer(root: Path, species: str) -> tuple[np.ndarray, np.ndarray]:
    arrays = read_npz(root / INPUTS_REL / "outer" / f"{species}.npz")
    cells = validate_ids(arrays["held_cells"], label=f"outer_input:{species}:cells")
    patch = np.asarray(arrays["held_patch"])
    require(patch.shape == cells.shape and patch.dtype.kind == "U", f"outer_input:{species}:patch_invalid")
    return cells, patch


def _input_map(root: Path) -> np.ndarray:
    arrays = read_npz(root / INPUTS_REL / "map.npz")
    return validate_ids(arrays["cells"], expected_length=EXPECTED_MAP_ROWS, label="map_input_cells")


def _csv_threshold_details(path: Path, rows: Sequence[Mapping[str, Any]]) -> bytes:
    require(len(rows) == 168, "threshold_detail_inventory_incomplete")
    fields = ["species", "endpoint", "method", "threshold", "maximum_oof_tss", "maximizer_count", "candidate_count", "oof_rows"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _validate_task_sets(root: Path, neural: ModuleType, conventional: ModuleType) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...], tuple[Any, ...], dict[tuple[str, str], Any]]:
    neural_inner = neural.build_inner_inventory()
    neural_outer = neural.build_outer_inventory()
    strata = conventional._selection_inventory(root)
    conventional_inner, conventional_outer, counts = conventional.build_task_inventory(strata)
    require(len(neural_inner) == 2800 and len(neural_outer) == 560, "neural_task_inventory_invalid")
    require(len(conventional_inner) == 1200 and len(conventional_outer) == 240, "conventional_task_inventory_invalid")
    require(counts["inner_physical_fits"] == 1725 and counts["outer_physical_fits"] == 240, "conventional_fit_arithmetic_invalid")
    selection = {(item.species, item.endpoint): item for item in strata}
    require(len(selection) == 56, "conventional_selection_inventory_invalid")
    return neural_inner, neural_outer, conventional_inner, conventional_outer, selection


def _group_tasks(tasks: Iterable[Any], keys: Sequence[str]) -> dict[tuple[Any, ...], list[Any]]:
    grouped: dict[tuple[Any, ...], list[Any]] = {}
    for task in tasks:
        key = tuple(getattr(task, name) for name in keys)
        grouped.setdefault(key, []).append(task)
    return grouped


def validate_lane_directory_inventory(
    root: Path, role: str, tasks: Sequence[Any], runner: ModuleType,
) -> None:
    """Reject unclosed, duplicate, orphaned, or extra target attempts."""
    lane = "inner" if role.endswith("inner") else "outer"
    base = root / (NEURAL_REL if role.startswith("neural") else CONVENTIONAL_REL)
    require(not (base / "ABORT.json").exists(), f"{role}_panel_abort_present")
    lane_root = base / lane
    expected = {runner._task_digest(task, lane) for task in tasks}
    inventories = (
        (lane_root / "leaves", expected, "directory"),
        (lane_root / "intents", {f"{key}.json" for key in expected}, "file"),
        (lane_root / "attempts", expected, "directory"),
    )
    for directory, names, kind in inventories:
        entries = list(directory.iterdir()) if directory.is_dir() else []
        require(
            {entry.name for entry in entries} == names
            and all(not entry.is_symlink() for entry in entries)
            and all(entry.is_dir() if kind == "directory" else entry.is_file() for entry in entries),
            f"{role}_{directory.name}_directory_inventory_mismatch",
        )


def validate_smoke_directory_inventory(
    root: Path, neural: ModuleType, conventional: ModuleType,
    selection: Mapping[tuple[str, str], Any],
) -> None:
    neural_tasks = tuple(
        neural.InnerTask(neural.SMOKE_TARGET, neural.SMOKE_FOLD, neural.SMOKE_ENDPOINT, method, neural.SMOKE_SEED)
        for method in neural.METHODS
    )
    conventional_tasks = conventional._smoke_tasks(tuple(selection[key] for key in sorted(selection)))
    for framework, runner, tasks, base in (
        ("neural", neural, neural_tasks, root / NEURAL_REL),
        ("conventional", conventional, conventional_tasks, root / CONVENTIONAL_REL),
    ):
        expected = {
            f"{runner._task_digest(task, 'inner')}--repeat{repetition}"
            for task in tasks for repetition in (1, 2)
        }
        inventories = (
            (base / "smoke/leaves", expected, "directory"),
            (base / "smoke/intents", {f"{key}.json" for key in expected}, "file"),
            (base / "smoke/attempts", expected, "directory"),
        )
        for directory, names, kind in inventories:
            entries = list(directory.iterdir()) if directory.is_dir() else []
            require(
                {entry.name for entry in entries} == names
                and all(not entry.is_symlink() for entry in entries)
                and all(entry.is_dir() if kind == "directory" else entry.is_file() for entry in entries),
                f"{framework}_smoke_{directory.name}_directory_inventory_mismatch",
            )


def validate_smoke_leaves(
    root: Path, neural: ModuleType, conventional: ModuleType,
    selection: Mapping[tuple[str, str], Any],
    preparations: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Bind every non-promotable smoke model and prediction leaf."""
    rows: list[dict[str, Any]] = []
    counts = {"neural_smoke": 0, "conventional_smoke": 0}
    neural_tasks = tuple(
        neural.InnerTask(neural.SMOKE_TARGET, neural.SMOKE_FOLD, neural.SMOKE_ENDPOINT, method, neural.SMOKE_SEED)
        for method in neural.METHODS
    )
    strata = tuple(selection[key] for key in sorted(selection))
    conventional_tasks = conventional._smoke_tasks(strata)
    for framework, runner, tasks, base, model_name in (
        ("neural", neural, neural_tasks, root / NEURAL_REL, "model.pt"),
        ("conventional", conventional, conventional_tasks, root / CONVENTIONAL_REL, "model.model"),
    ):
        for task in tasks:
            task_digest = runner._task_digest(task, "inner")
            for repetition in (1, 2):
                leaf = base / "smoke/leaves" / f"{task_digest}--repeat{repetition}"
                receipt_path = leaf / "receipt.json"
                receipt = read_receipt(receipt_path)
                expected_schema = f"tasmania-pseudoabsence-{framework}-inner-leaf-{'v2' if framework == 'neural' else 'v1'}"
                require(receipt.get("schema_version") == expected_schema, f"{framework}_smoke_leaf_schema_mismatch")
                require(receipt.get("task") == asdict(task) and receipt.get("task_digest") == task_digest, f"{framework}_smoke_leaf_identity_mismatch")
                require(receipt.get("bindings") == preparations[framework].get("bindings"), f"{framework}_smoke_leaf_preparation_binding_mismatch")
                require(receipt.get("held_response_vault_read") is False if framework == "conventional" else receipt.get("outer_held_response_labels_read") == 0, f"{framework}_smoke_response_boundary_breached")
                if framework == "neural":
                    require(receipt.get("smoke_non_promotable") is True and receipt.get("production_caps_receipt_digest") is None, "neural_smoke_leaf_promotable")
                    model_sha = receipt.get("model_receipt", {}).get("model_sha256")
                    model_state = receipt.get("model_digest")
                    model_identity = receipt.get("model_receipt", {}).get("identity_digest")
                    auxiliary_artifacts: list[dict[str, str]] = []
                    expected_files = {"receipt.json", "predictions.npz", "model.pt"}
                else:
                    require(
                        receipt.get("production_caps_receipt_digest") is None
                        and receipt.get("preparation_receipt_digest") == preparations[framework].get("receipt_digest")
                        and receipt.get("labels_in_prediction_batch") is False,
                        "conventional_smoke_leaf_promotable",
                    )
                    model_sha = receipt.get("model_sha256")
                    model_state = receipt.get("model_semantic_digest")
                    model_identity = receipt.get("model_identity_digest")
                    expected_files = {"receipt.json", "predictions.npz", "model.model", "encoder.json"}
                    if receipt.get("discovery_model_sha256") is not None:
                        expected_files.add("discovery.model")
                require(
                    leaf.is_dir() and not leaf.is_symlink()
                    and {item.name for item in leaf.iterdir()} == expected_files
                    and all(item.is_file() and not item.is_symlink() for item in leaf.iterdir()),
                    f"{framework}_smoke_leaf_file_inventory_mismatch",
                )
                model_path = leaf / model_name
                prediction_path = leaf / "predictions.npz"
                require(sha256_file(model_path) == model_sha, f"{framework}_smoke_model_changed")
                if framework == "conventional":
                    encoder_path = leaf / "encoder.json"
                    require(sha256_file(encoder_path) == receipt.get("encoder_sha256"), "conventional_smoke_encoder_changed")
                    auxiliary_artifacts = [{"role": "encoder", "path": _relative(root, encoder_path), "sha256": receipt["encoder_sha256"]}]
                    discovery_path = leaf / "discovery.model"
                    if discovery_path.exists():
                        require(sha256_file(discovery_path) == receipt.get("discovery_model_sha256"), "conventional_smoke_discovery_model_changed")
                        auxiliary_artifacts.append({"role": "discovery_model", "path": _relative(root, discovery_path), "sha256": receipt["discovery_model_sha256"]})
                require(sha256_file(prediction_path) == receipt.get("prediction_sha256"), f"{framework}_smoke_prediction_changed")
                arrays = read_npz(prediction_path)
                validate_probability_payload(arrays, expect_map=False, neural=framework == "neural", label=f"{framework}_smoke:{task_digest}:{repetition}")
                if framework == "neural":
                    require(runner.array_digest(arrays["scores"]) == receipt.get("prediction_digest"), "neural_smoke_prediction_digest_mismatch")
                else:
                    require(runner._prediction_digest(arrays["grid_cell_id"].tolist(), arrays["scores"]) == receipt.get("prediction_digest"), "conventional_smoke_prediction_digest_mismatch")
                physical = int(receipt.get("physical_fits", -1))
                require(physical in (1, 2), f"{framework}_smoke_physical_fit_invalid")
                attempt_id = f"{task_digest}--repeat{repetition}"
                intent_path = base / "smoke/intents" / f"{attempt_id}.json"
                attempt_path = base / "smoke/attempts" / attempt_id
                intent = read_json(intent_path)
                require(
                    intent.get("task") == asdict(task)
                    and intent.get("task_digest") == task_digest
                    and intent.get("physical_stages") is not None
                    and len(intent["physical_stages"]) == physical,
                    f"{framework}_smoke_intent_invalid",
                )
                if framework == "neural":
                    require(read_json(attempt_path / "intent.json") == intent, "neural_smoke_intent_copy_mismatch")
                    running = read_json(attempt_path / "running.json")
                    completed = read_json(attempt_path / "completed.json")
                    require(running.get("task_digest") == task_digest and running.get("fit_started") is True, "neural_smoke_fit_start_missing")
                    require(completed.get("task_digest") == task_digest and completed.get("receipt_digest") == receipt["receipt_digest"], "neural_smoke_completion_invalid")
                    require(not (attempt_path / "failed.json").exists(), "neural_smoke_failure_present")
                    starts = physical
                else:
                    validate_self_digest(intent, "intent_digest", "conventional_smoke_intent_digest_invalid")
                    start_root = attempt_path / "fit-starts"
                    start_paths = sorted(start_root.iterdir()) if start_root.is_dir() else []
                    require(len(start_paths) == physical, "conventional_smoke_fit_start_inventory_invalid")
                    for number, (stage, start_path) in enumerate(zip(intent["physical_stages"], start_paths, strict=True), start=1):
                        start = read_json(start_path)
                        require(start.get("task") == asdict(task) and start.get("stage") == stage and start.get("physical_fit_number") == number, "conventional_smoke_fit_start_invalid")
                    completed = read_json(attempt_path / "completed.json")
                    require(completed.get("task_digest") == task_digest and completed.get("receipt_digest") == receipt["receipt_digest"], "conventional_smoke_completion_invalid")
                    require(not (attempt_path / "failed.json").exists(), "conventional_smoke_failure_present")
                    starts = len(start_paths)
                require(starts == physical, f"{framework}_smoke_actual_fit_starts_mismatch")
                counts[f"{framework}_smoke"] += starts
                rows.append({
                    "role": f"{framework}_smoke", "task": asdict(task), "task_digest": task_digest,
                    "repetition": repetition, "leaf_path": _relative(root, leaf),
                    "receipt_path": _relative(root, receipt_path), "receipt_sha256": sha256_file(receipt_path),
                    "receipt_digest": receipt["receipt_digest"],
                    "model_path": _relative(root, model_path), "model_sha256": model_sha,
                    "model_state_digest": model_state, "model_identity_digest": model_identity,
                    "auxiliary_artifacts": auxiliary_artifacts,
                    "prediction_path": _relative(root, prediction_path),
                    "prediction_sha256": receipt["prediction_sha256"],
                    "prediction_receipt_digest": receipt["prediction_digest"],
                    "array_digests": {name: array_digest(arrays[name]) for name in sorted(arrays)},
                    "identity_digest": digest_value({
                        "role": f"{framework}_smoke", "task": asdict(task),
                        "task_digest": task_digest, "repetition": repetition,
                        "bindings": receipt.get("bindings"),
                    }),
                    "physical_fit_starts": starts,
                })
    require(len(rows) == 8 and counts == {"neural_smoke": 8, "conventional_smoke": 6}, "smoke_leaf_inventory_invalid")
    return rows, counts


def verify_closed_sources(
    closure: Mapping[str, Any],
    private: Path | None = None,
    *,
    root: Path = ROOT,
    require_closure_digest: bool = True,
) -> Mapping[str, Any]:
    """Revalidate every source byte and all normalized map averages.

    The assessment calls this function after authenticating this module's
    source hash and before opening the outer response vault.  The collector
    also calls it on the pending closure body before publishing the immutable
    self-digested closure.
    """
    root = root.resolve()
    require(root == ROOT.resolve(), "source_verifier_must_run_from_owning_checkout")
    private = (private or root / ASSESSMENT_REL).resolve()
    require(private == (root / ASSESSMENT_REL).resolve(), "source_verifier_private_path_invalid")
    if require_closure_digest:
        validate_self_digest(closure, "receipt_digest", "prediction_closure_digest_mismatch")
    require(
        closure.get("status") == "accepted"
        and closure.get("outer_held_response_labels_read") == 0,
        "prediction_closure_not_response_free",
    )
    collector_sha = sha256_file(Path(__file__).resolve())
    require(closure.get("collector_source_sha256") == collector_sha, "collector_source_changed_after_closure")
    require(
        closure.get("assessment_source_sha256") == sha256_file(root / ASSESSMENT_SOURCE_REL)
        and closure.get("metrics_source_sha256") == sha256_file(root / METRICS_SOURCE_REL),
        "assessment_source_changed_after_closure",
    )
    validate_input_manifest(root)
    neural, conventional, assessment = module_bundle(root)
    require(tuple(neural.SPECIES) == SPECIES == tuple(conventional.SPECIES) == tuple(assessment.SPECIES), "verifier_species_contract_disagreement")
    require(tuple(neural.ENDPOINTS) == ENDPOINTS == tuple(conventional.ENDPOINTS) == tuple(assessment.ENDPOINTS), "verifier_endpoint_contract_disagreement")
    closures, preparations, caps, actual_closures, actual_bindings, fit_counts = validate_source_receipts(root, neural, conventional)
    require(
        [row.get("role") for row in closure.get("source_closures", [])]
        == ["neural_inner", "neural_outer", "conventional_inner", "conventional_outer", "neural_smoke", "conventional_smoke", "recovery"],
        "source_closure_role_inventory_invalid",
    )
    require(closure.get("source_closures") == actual_closures, "source_closure_bytes_changed")
    require(closure.get("source_bindings") == actual_bindings, "source_binding_bytes_changed")
    require(
        closure.get("target_physical_fits")
        == sum(fit_counts[name] for name in ("neural_inner", "neural_outer", "conventional_inner", "conventional_outer"))
        == 8125
        and closure.get("smoke_physical_fits") == fit_counts["neural_smoke"] + fit_counts["conventional_smoke"] == 14
        and closure.get("recovery_physical_fits") == fit_counts["recovery"] == 200,
        "closure_fit_totals_not_derived_from_sources",
    )
    n_inner, n_outer, c_inner, c_outer, selection = _validate_task_sets(root, neural, conventional)
    validate_smoke_directory_inventory(root, neural, conventional, selection)
    current_smoke_inventory, smoke_counts = validate_smoke_leaves(
        root, neural, conventional, selection, preparations,
    )
    require(smoke_counts == {"neural_smoke": fit_counts["neural_smoke"], "conventional_smoke": fit_counts["conventional_smoke"]}, "smoke_leaf_receipts_disagree_with_qualification")
    require(closure.get("actual_smoke_physical_fit_starts") == smoke_counts, "closure_smoke_physical_starts_invalid")
    tasks_by_role = {
        "neural_inner": n_inner, "neural_outer": n_outer,
        "conventional_inner": c_inner, "conventional_outer": c_outer,
    }
    rows_by_role = {role: _closure_rows(closures[role]) for role in tasks_by_role}
    current_inventory: list[dict[str, Any]] = []
    actual_starts = {role: 0 for role in tasks_by_role}
    source_payloads: dict[str, dict[str, dict[str, np.ndarray]]] = {
        role: {} for role in tasks_by_role
    }
    for role, tasks in tasks_by_role.items():
        runner = neural if role.startswith("neural") else conventional
        lane = "inner" if role.endswith("inner") else "outer"
        validate_lane_directory_inventory(root, role, tasks, runner)
        expected_digests = {runner._task_digest(task, lane) for task in tasks}
        require(set(rows_by_role[role]) == expected_digests, f"{role}_verifier_crossproduct_incomplete")
        for task in tasks:
            task_digest = runner._task_digest(task, lane)
            _receipt, arrays, row, starts = validate_leaf(
                root, role, task, runner, rows_by_role[role][task_digest],
                preparations["neural" if role.startswith("neural") else "conventional"],
                caps["neural" if role.startswith("neural") else "conventional"]["receipt_digest"],
            )
            current_inventory.append(row)
            actual_starts[role] += starts
            source_payloads[role][task_digest] = arrays
    expected_starts = {
        "neural_inner": 5600, "neural_outer": 560,
        "conventional_inner": 1725, "conventional_outer": 240,
    }
    require(actual_starts == expected_starts, "source_actual_physical_starts_invalid")
    require(closure.get("actual_physical_fit_starts") == expected_starts, "closure_actual_physical_starts_invalid")

    inventory_path = private / "source-leaf-inventory.json"
    require(closure.get("source_leaf_inventory_path") == _relative(root, inventory_path), "source_leaf_inventory_path_invalid")
    require(sha256_file(inventory_path) == closure.get("source_leaf_inventory_sha256"), "source_leaf_inventory_file_changed")
    inventory = read_receipt(inventory_path)
    require(inventory.get("receipt_digest") == closure.get("source_leaf_inventory_receipt_digest"), "source_leaf_inventory_receipt_link_invalid")
    require(
        inventory.get("status") == "accepted"
        and inventory.get("outer_held_response_labels_read") == 0
        and inventory.get("leaf_count") == len(current_inventory) == 4800
        and inventory.get("smoke_leaf_count") == len(current_smoke_inventory) == 8
        and inventory.get("physical_fit_starts") == expected_starts
        and inventory.get("smoke_physical_fits") == smoke_counts
        and inventory.get("inventory_digest") == digest_value(current_inventory)
        and inventory.get("leaves") == current_inventory,
        "source_leaf_inventory_current_bytes_mismatch",
    )
    require(
        inventory.get("smoke_inventory_digest") == digest_value(current_smoke_inventory)
        and inventory.get("smoke_leaves") == current_smoke_inventory,
        "source_smoke_leaf_inventory_current_bytes_mismatch",
    )

    file_records = closure.get("files")
    require(isinstance(file_records, list) and len(file_records) == 8, "normalized_prediction_file_inventory_invalid")
    file_index = {str(row.get("species")): row for row in file_records}
    require(set(file_index) == set(SPECIES), "normalized_prediction_species_inventory_invalid")
    map_cells = _input_map(root)
    inner_inputs = {
        (species, fold): _input_inner(root, species, fold)
        for species in SPECIES for fold in FOLDS
    }
    n_inner_groups = _group_tasks(n_inner, ("target", "held_fold", "endpoint", "method"))
    n_groups = _group_tasks(n_outer, ("target", "endpoint", "method"))
    c_inner_groups = _group_tasks(c_inner, ("species", "held_fold", "endpoint"))
    c_groups = _group_tasks(c_outer, ("species", "endpoint"))
    verified_pairs = 0
    verified_held_panels = 0
    verified_thresholds = 0
    verified_threshold_rows: list[dict[str, Any]] = []
    for species in SPECIES:
        prediction_path = private / "predictions" / f"{species}.npz"
        require(sha256_file(prediction_path) == file_index[species].get("sha256"), f"normalized_prediction_file_changed:{species}")
        normalized = read_npz(prediction_path, {
            "grid_cell_id", "patch", "primary_scores", "sensitivity_scores",
            "primary_thresholds", "sensitivity_thresholds", "map_grid_cell_id",
            "primary_map_scores", "sensitivity_map_scores",
        })
        require(np.array_equal(normalized["map_grid_cell_id"], map_cells), f"normalized_map_identity_changed:{species}")
        require(normalized["primary_map_scores"].shape == normalized["sensitivity_map_scores"].shape == (3, EXPECTED_MAP_ROWS), f"normalized_map_shape_invalid:{species}")
        require(normalized["primary_map_scores"].dtype == normalized["sensitivity_map_scores"].dtype == np.float64, f"normalized_map_dtype_invalid:{species}")
        held_cells = validate_ids(normalized["grid_cell_id"], label=f"normalized_held_ids:{species}")
        require(normalized["sensitivity_scores"].shape == (7, 3, len(held_cells)) and normalized["sensitivity_scores"].dtype == np.float64, f"normalized_sensitivity_score_shape_invalid:{species}")
        require(normalized["sensitivity_thresholds"].shape == (7, 3) and normalized["sensitivity_thresholds"].dtype == np.float64, f"normalized_sensitivity_threshold_shape_invalid:{species}")
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            for method_index, method in enumerate(METHODS):
                fold_vectors: list[np.ndarray] = []
                fold_labels: list[np.ndarray] = []
                if method in NEURAL_METHODS:
                    expected_seeds: Sequence[Any] = NEURAL_SEEDS
                    for fold in FOLDS:
                        cells, labels = inner_inputs[species, fold]
                        tasks = n_inner_groups[species, fold, endpoint, method]
                        records = [
                            (task.seed, source_payloads["neural_inner"][neural._task_digest(task, "inner")]["grid_cell_id"],
                             source_payloads["neural_inner"][neural._task_digest(task, "inner")]["scores"])
                            for task in tasks
                        ]
                        fold_vectors.append(mean_seed_predictions(records, expected_seeds, cells, label=f"verify_inner:{species}:{fold}:{endpoint}:{method}"))
                        fold_labels.append(labels)
                    outer_tasks = n_groups[species, endpoint, method]
                    outer_records = [
                        (task.seed, source_payloads["neural_outer"][neural._task_digest(task, "outer")]["grid_cell_id"],
                         source_payloads["neural_outer"][neural._task_digest(task, "outer")]["scores"])
                        for task in outer_tasks
                    ]
                else:
                    expected_seeds = selection[species, endpoint].seeds
                    for fold in FOLDS:
                        cells, labels = inner_inputs[species, fold]
                        tasks = c_inner_groups[species, fold, endpoint]
                        records = [
                            (task.seed_label, source_payloads["conventional_inner"][conventional._task_digest(task, "inner")]["grid_cell_id"],
                             source_payloads["conventional_inner"][conventional._task_digest(task, "inner")]["scores"])
                            for task in tasks
                        ]
                        fold_vectors.append(mean_seed_predictions(records, expected_seeds, cells, label=f"verify_inner:{species}:{fold}:{endpoint}:{method}"))
                        fold_labels.append(labels)
                    outer_tasks = c_groups[species, endpoint]
                    outer_records = [
                        (task.seed_label, source_payloads["conventional_outer"][conventional._task_digest(task, "outer")]["grid_cell_id"],
                         source_payloads["conventional_outer"][conventional._task_digest(task, "outer")]["scores"])
                        for task in outer_tasks
                    ]
                outer_mean = mean_seed_predictions(
                    outer_records, expected_seeds, held_cells,
                    label=f"verify_outer:{species}:{endpoint}:{method}",
                )
                require(np.array_equal(outer_mean, normalized["sensitivity_scores"][endpoint_index, method_index]), f"normalized_sensitivity_scores_not_source_average:{species}:{endpoint}:{method}")
                pooled_labels = np.concatenate(fold_labels).astype(np.int8, copy=False)
                pooled_scores = np.concatenate(fold_vectors).astype(np.float64, copy=False)
                threshold = select_threshold(pooled_labels, pooled_scores)
                require(threshold["threshold"] == normalized["sensitivity_thresholds"][endpoint_index, method_index], f"normalized_sensitivity_threshold_not_source_oof:{species}:{endpoint}:{method}")
                verified_threshold_rows.append({
                    "species": species, "endpoint": endpoint, "method": method,
                    "threshold": threshold["threshold"], "maximum_oof_tss": threshold["maximum_oof_tss"],
                    "maximizer_count": threshold["maximizer_count"], "candidate_count": threshold["candidate_count"],
                    "oof_rows": len(pooled_labels),
                })
                verified_held_panels += 1
                verified_thresholds += 1
        for method_index, method in enumerate(METHODS):
            if method in NEURAL_METHODS:
                tasks = n_groups[species, "fraction100/full", method]
                runner = neural
                role = "neural_outer"
                seeds = NEURAL_SEEDS
                seed_name = "seed"
                sensitivity_name = "sensitivity_map_scores"
                primary_name = "accepted_primary_map_scores"
            else:
                tasks = c_groups[species, "fraction100/full"]
                runner = conventional
                role = "conventional_outer"
                seeds = selection[species, "fraction100/full"].seeds
                seed_name = "seed_label"
                sensitivity_name = "map_scores"
                primary_name = "baseline_map_scores"
            sensitivity_records = []
            primary_records = []
            for task in tasks:
                task_digest = runner._task_digest(task, "outer")
                arrays = source_payloads[role][task_digest]
                seed = getattr(task, seed_name)
                sensitivity_records.append((seed, arrays["map_grid_cell_id"], arrays[sensitivity_name]))
                primary_records.append((seed, arrays["map_grid_cell_id"], arrays[primary_name]))
            sensitivity = mean_seed_predictions(sensitivity_records, seeds, map_cells, label=f"verify_sensitivity_map:{species}:{method}")
            primary = mean_seed_predictions(primary_records, seeds, map_cells, label=f"verify_primary_map:{species}:{method}")
            require(np.array_equal(sensitivity, normalized["sensitivity_map_scores"][method_index]), f"normalized_sensitivity_map_not_source_average:{species}:{method}")
            require(np.array_equal(primary, normalized["primary_map_scores"][method_index]), f"normalized_primary_map_not_source_average:{species}:{method}")
            verified_pairs += 1
    require(verified_pairs == 24, "normalized_map_pair_inventory_incomplete")
    require(verified_held_panels == verified_thresholds == 168, "normalized_held_panel_inventory_incomplete")
    threshold_path = private / "threshold-details.csv"
    require(closure.get("threshold_details_path") == _relative(root, threshold_path), "threshold_details_path_invalid")
    require(closure.get("threshold_records") == 168 and sha256_file(threshold_path) == closure.get("threshold_details_sha256"), "threshold_details_file_changed")
    require(threshold_path.read_bytes() == _csv_threshold_details(threshold_path, verified_threshold_rows), "threshold_details_not_source_derived")
    return {
        "status": "pass", "outer_held_response_labels_read": 0,
        "source_leaves": len(current_inventory), "smoke_leaves": len(current_smoke_inventory),
        "actual_physical_fit_starts": actual_starts,
        "verified_map_pairs": verified_pairs, "verified_held_panels": verified_held_panels,
        "verified_thresholds": verified_thresholds,
        "source_leaf_inventory_receipt_digest": inventory["receipt_digest"],
    }


def collect(
    root: Path = ROOT, output: Path | None = None, *, execute: bool = False,
) -> Mapping[str, Any]:
    """Build response-free assessment inputs after complete target closure."""
    require(execute, "collection_requires_explicit_execute_gate")
    root = root.resolve()
    require(root == ROOT.resolve(), "collector_must_run_from_owning_checkout")
    output = (output or root / ASSESSMENT_REL).resolve()
    require(output == (root / ASSESSMENT_REL).resolve(), "assessment_output_path_invalid")
    validate_input_manifest(root)
    neural, conventional, assessment = module_bundle(root)
    require(tuple(neural.SPECIES) == SPECIES == tuple(conventional.SPECIES) == tuple(assessment.SPECIES), "species_contract_disagreement")
    require(tuple(neural.ENDPOINTS) == ENDPOINTS == tuple(conventional.ENDPOINTS) == tuple(assessment.ENDPOINTS), "endpoint_contract_disagreement")
    closures, preparations, caps, source_closures, source_bindings, fit_counts = validate_source_receipts(root, neural, conventional)
    n_inner, n_outer, c_inner, c_outer, selection = _validate_task_sets(root, neural, conventional)
    validate_smoke_directory_inventory(root, neural, conventional, selection)
    smoke_leaf_inventory, smoke_leaf_counts = validate_smoke_leaves(
        root, neural, conventional, selection, preparations,
    )
    require(
        smoke_leaf_counts == {
            "neural_smoke": fit_counts["neural_smoke"],
            "conventional_smoke": fit_counts["conventional_smoke"],
        },
        "smoke_leaf_receipts_disagree_with_qualification",
    )
    expected_by_role = {
        "neural_inner": n_inner, "neural_outer": n_outer,
        "conventional_inner": c_inner, "conventional_outer": c_outer,
    }
    closure_rows = {role: _closure_rows(closures[role]) for role in expected_by_role}
    for role, tasks in expected_by_role.items():
        runner = neural if role.startswith("neural") else conventional
        lane = "inner" if role.endswith("inner") else "outer"
        validate_lane_directory_inventory(root, role, tasks, runner)
        expected = {runner._task_digest(task, lane) for task in tasks}
        require(set(closure_rows[role]) == expected, f"{role}_closure_task_inventory_mismatch")

    primary_receipt, primary_thresholds, primary_selected = assessment.baseline()
    require(primary_receipt.get("receipt_digest") == BASELINE_RECEIPT_DIGEST, "baseline_receipt_binding_mismatch")
    for key, item in selection.items():
        require(primary_selected[key] == item.family, f"conventional_selection_disagrees_with_primary:{key}")

    # Authenticate all source leaves once and cache only response-free arrays.
    source_arrays: dict[str, dict[str, dict[str, np.ndarray]]] = {role: {} for role in expected_by_role}
    leaf_inventory: list[dict[str, Any]] = []
    actual_starts = {role: 0 for role in expected_by_role}
    for role, tasks in expected_by_role.items():
        runner = neural if role.startswith("neural") else conventional
        for task in tasks:
            lane = "inner" if role.endswith("inner") else "outer"
            task_digest = runner._task_digest(task, lane)
            framework = "neural" if role.startswith("neural") else "conventional"
            _receipt, arrays, row, starts = validate_leaf(
                root, role, task, runner, closure_rows[role][task_digest],
                preparations[framework], caps[framework]["receipt_digest"],
            )
            source_arrays[role][task_digest] = arrays
            leaf_inventory.append(row)
            actual_starts[role] += starts
    require(actual_starts == {"neural_inner": 5600, "neural_outer": 560, "conventional_inner": 1725, "conventional_outer": 240}, "actual_physical_start_inventory_invalid")

    map_cells = _input_map(root)
    inner_inputs = {
        (species, fold): _input_inner(root, species, fold)
        for species in SPECIES for fold in FOLDS
    }
    outer_inputs = {species: _input_outer(root, species) for species in SPECIES}
    threshold_rows: list[dict[str, Any]] = []
    output_files: list[dict[str, str]] = []
    negative_controls = {"held_scores": 0, "thresholds": 0, "maps": 0}
    n_inner_groups = _group_tasks(n_inner, ("target", "held_fold", "endpoint", "method"))
    n_outer_groups = _group_tasks(n_outer, ("target", "endpoint", "method"))
    c_inner_groups = _group_tasks(c_inner, ("species", "held_fold", "endpoint"))
    c_outer_groups = _group_tasks(c_outer, ("species", "endpoint"))

    for species in SPECIES:
        held_cells, held_patch, primary_neural, primary_conventional = _baseline_arrays(root, species)
        input_outer_cells, input_outer_patch = outer_inputs[species]
        aligned_patch = align_vector(held_cells, input_outer_cells, input_outer_patch, label=f"outer_input:{species}:patch")
        require(np.array_equal(held_patch, aligned_patch), f"outer_input:{species}:primary_patch_mismatch")
        primary_scores = np.empty((7, 3, len(held_cells)), dtype=np.float64)
        sensitivity_scores = np.empty_like(primary_scores)
        primary_threshold_array = np.empty((7, 3), dtype=np.float64)
        sensitivity_threshold_array = np.empty_like(primary_threshold_array)
        primary_maps = np.empty((3, EXPECTED_MAP_ROWS), dtype=np.float64)
        sensitivity_maps = np.empty_like(primary_maps)

        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            conventional_item = selection[species, endpoint]
            for method_index, method in enumerate(METHODS):
                if method in NEURAL_METHODS:
                    primary_scores[endpoint_index, method_index] = primary_neural[
                        endpoint_index, BASE_NEURAL.index(method)
                    ]
                    primary_method = method
                    fold_vectors = []
                    fold_labels = []
                    for fold in FOLDS:
                        cells, labels = inner_inputs[species, fold]
                        tasks = n_inner_groups[species, fold, endpoint, method]
                        records = [
                            (task.seed, source_arrays["neural_inner"][neural._task_digest(task, "inner")]["grid_cell_id"],
                             source_arrays["neural_inner"][neural._task_digest(task, "inner")]["scores"])
                            for task in tasks
                        ]
                        fold_vectors.append(mean_seed_predictions(records, NEURAL_SEEDS, cells, label=f"inner:{species}:{fold}:{endpoint}:{method}"))
                        fold_labels.append(labels)
                    outer_tasks = n_outer_groups[species, endpoint, method]
                    outer_records = [
                        (task.seed, source_arrays["neural_outer"][neural._task_digest(task, "outer")]["grid_cell_id"],
                         source_arrays["neural_outer"][neural._task_digest(task, "outer")]["scores"])
                        for task in outer_tasks
                    ]
                    sensitivity_scores[endpoint_index, method_index] = mean_seed_predictions(
                        outer_records, NEURAL_SEEDS, held_cells, label=f"outer:{species}:{endpoint}:{method}",
                    )
                else:
                    family = conventional_item.family
                    primary_scores[endpoint_index, method_index] = primary_conventional[
                        endpoint_index, BASE_CONVENTIONAL.index(family)
                    ]
                    primary_method = "conventional/" + family
                    expected_seeds = conventional_item.seeds
                    fold_vectors, fold_labels = [], []
                    for fold in FOLDS:
                        cells, labels = inner_inputs[species, fold]
                        tasks = c_inner_groups[species, fold, endpoint]
                        records = [
                            (task.seed_label, source_arrays["conventional_inner"][conventional._task_digest(task, "inner")]["grid_cell_id"],
                             source_arrays["conventional_inner"][conventional._task_digest(task, "inner")]["scores"])
                            for task in tasks
                        ]
                        fold_vectors.append(mean_seed_predictions(records, expected_seeds, cells, label=f"inner:{species}:{fold}:{endpoint}:{method}"))
                        fold_labels.append(labels)
                    outer_tasks = c_outer_groups[species, endpoint]
                    outer_records = [
                        (task.seed_label, source_arrays["conventional_outer"][conventional._task_digest(task, "outer")]["grid_cell_id"],
                         source_arrays["conventional_outer"][conventional._task_digest(task, "outer")]["scores"])
                        for task in outer_tasks
                    ]
                    sensitivity_scores[endpoint_index, method_index] = mean_seed_predictions(
                        outer_records, expected_seeds, held_cells, label=f"outer:{species}:{endpoint}:{method}",
                    )
                pooled_labels = np.concatenate(fold_labels).astype(np.int8, copy=False)
                pooled_scores = np.concatenate(fold_vectors).astype(np.float64, copy=False)
                threshold = select_threshold(pooled_labels, pooled_scores)
                primary_threshold_array[endpoint_index, method_index] = primary_thresholds[species, endpoint, primary_method]
                sensitivity_threshold_array[endpoint_index, method_index] = threshold["threshold"]
                threshold_rows.append({
                    "species": species, "endpoint": endpoint, "method": method,
                    "threshold": threshold["threshold"], "maximum_oof_tss": threshold["maximum_oof_tss"],
                    "maximizer_count": threshold["maximizer_count"], "candidate_count": threshold["candidate_count"],
                    "oof_rows": len(pooled_labels),
                })

        full = "fraction100/full"
        for method_index, method in enumerate(METHODS):
            if method in NEURAL_METHODS:
                tasks = n_outer_groups[species, full, method]
                sensitivity_records = [
                    (task.seed, source_arrays["neural_outer"][neural._task_digest(task, "outer")]["map_grid_cell_id"],
                     source_arrays["neural_outer"][neural._task_digest(task, "outer")]["sensitivity_map_scores"])
                    for task in tasks
                ]
                primary_records = [
                    (task.seed, source_arrays["neural_outer"][neural._task_digest(task, "outer")]["map_grid_cell_id"],
                     source_arrays["neural_outer"][neural._task_digest(task, "outer")]["accepted_primary_map_scores"])
                    for task in tasks
                ]
                seeds = NEURAL_SEEDS
            else:
                tasks = c_outer_groups[species, full]
                sensitivity_records = [
                    (task.seed_label, source_arrays["conventional_outer"][conventional._task_digest(task, "outer")]["map_grid_cell_id"],
                     source_arrays["conventional_outer"][conventional._task_digest(task, "outer")]["map_scores"])
                    for task in tasks
                ]
                primary_records = [
                    (task.seed_label, source_arrays["conventional_outer"][conventional._task_digest(task, "outer")]["map_grid_cell_id"],
                     source_arrays["conventional_outer"][conventional._task_digest(task, "outer")]["baseline_map_scores"])
                    for task in tasks
                ]
                seeds = selection[species, full].seeds
            sensitivity_maps[method_index] = mean_seed_predictions(sensitivity_records, seeds, map_cells, label=f"sensitivity_map:{species}:{method}")
            primary_maps[method_index] = mean_seed_predictions(primary_records, seeds, map_cells, label=f"primary_map:{species}:{method}")

        if species == "thylogale_billardierii":
            require(np.array_equal(primary_scores, sensitivity_scores), "thylogale_held_score_negative_control_failed")
            require(np.array_equal(primary_threshold_array, sensitivity_threshold_array), "thylogale_threshold_negative_control_failed")
            require(np.array_equal(primary_maps, sensitivity_maps), "thylogale_map_negative_control_failed")
            negative_controls = {"held_scores": 21, "thresholds": 21, "maps": 3}
        arrays = {
            "grid_cell_id": held_cells,
            "patch": held_patch,
            "primary_scores": primary_scores,
            "sensitivity_scores": sensitivity_scores,
            "primary_thresholds": primary_threshold_array,
            "sensitivity_thresholds": sensitivity_threshold_array,
            "map_grid_cell_id": map_cells,
            "primary_map_scores": primary_maps,
            "sensitivity_map_scores": sensitivity_maps,
        }
        prediction_path = output / "predictions" / f"{species}.npz"
        raw = deterministic_npz_bytes(arrays)
        write_idempotent(prediction_path, raw)
        output_files.append({"species": species, "sha256": hashlib.sha256(raw).hexdigest()})

    require(len(threshold_rows) == 168, "threshold_inventory_incomplete")
    require(sum(len(_baseline_arrays(root, species)[0]) for species in SPECIES) == EXPECTED_HELD_ROWS, "held_row_inventory_changed")
    leaf_inventory_body = {
        "schema_version": "tasmania-pseudoabsence-source-leaf-inventory-v1",
        "status": "accepted", "outer_held_response_labels_read": 0,
        "leaf_count": len(leaf_inventory), "physical_fit_starts": actual_starts,
        "inventory_digest": digest_value(leaf_inventory), "leaves": leaf_inventory,
        "smoke_leaf_count": len(smoke_leaf_inventory),
        "smoke_physical_fits": smoke_leaf_counts,
        "smoke_inventory_digest": digest_value(smoke_leaf_inventory),
        "smoke_leaves": smoke_leaf_inventory,
    }
    leaf_inventory_receipt = write_json_receipt(output / "source-leaf-inventory.json", leaf_inventory_body)
    threshold_path = output / "threshold-details.csv"
    write_idempotent(threshold_path, _csv_threshold_details(threshold_path, threshold_rows))
    fit_total = sum(fit_counts[key] for key in ("neural_inner", "neural_outer", "conventional_inner", "conventional_outer"))
    closure_body = {
        "schema_version": "tasmania-pseudoabsence-prediction-closure-v1",
        "status": "accepted", "outer_held_response_labels_read": 0,
        "target_physical_fits": fit_total,
        "smoke_physical_fits": fit_counts["neural_smoke"] + fit_counts["conventional_smoke"],
        "recovery_physical_fits": fit_counts["recovery"],
        "actual_physical_fit_starts": actual_starts,
        "actual_smoke_physical_fit_starts": smoke_leaf_counts,
        "assessment_source_sha256": sha256_file(root / ASSESSMENT_SOURCE_REL),
        "metrics_source_sha256": sha256_file(root / METRICS_SOURCE_REL),
        "collector_source_sha256": sha256_file(Path(__file__).resolve()),
        "baseline_receipt_digest": BASELINE_RECEIPT_DIGEST,
        "input_manifest_digest": INPUT_MANIFEST_DIGEST,
        "source_closures": source_closures,
        "source_bindings": source_bindings,
        "source_leaf_inventory_path": _relative(root, output / "source-leaf-inventory.json"),
        "source_leaf_inventory_sha256": sha256_file(output / "source-leaf-inventory.json"),
        "source_leaf_inventory_receipt_digest": leaf_inventory_receipt["receipt_digest"],
        "threshold_details_path": _relative(root, threshold_path),
        "threshold_details_sha256": sha256_file(threshold_path),
        "threshold_records": len(threshold_rows),
        "thylogale_exact_negative_controls": negative_controls,
        "files": output_files,
    }
    require(closure_body["target_physical_fits"] == 8125 and closure_body["smoke_physical_fits"] == 14 and closure_body["recovery_physical_fits"] == 200, "final_fit_inventory_mismatch")
    verify_closed_sources(
        closure_body, private=output, root=root, require_closure_digest=False,
    )
    closure = write_json_receipt(output / "prediction-closure.json", closure_body)
    return closure


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("collect",))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    result = collect(args.root, args.output, execute=args.execute)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
