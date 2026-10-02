#!/usr/bin/env python3
"""Independently review all Goal052 shallow-ANN epoch recoveries.

The review is read-only apart from its compact JSON result.  It verifies the
returned-file manifest and native bindings, then reconstructs every saved
fold mean from the evaluated seed arrays and compares it exactly with the
accepted Goal051 prediction rows.  It never imports model implementations,
fits a model, or opens an outer response.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

# This audit is deliberately one-process and one-thread.  Set these before
# importing NumPy or PyArrow so native libraries cannot start worker pools.
for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "ARROW_NUM_THREADS",
):
    os.environ[_name] = "1"

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = Path("evidence/seawfb_dsdm/goal052/outer-inventory-20260929.json")
SUMMARY = Path("evidence/seawfb_conventional/goal051/summary.json")
GOAL051_CONFIG = Path("config/goal051_seawfb_conventional.json")
GOAL052_CONFIG = Path("config/goal052_seawfb_dsdm.json")
RECOVERY = Path("data/processed/dsdm/goal052-seawfb-dsdm-experiment/ann-epoch-recovery")
BATCH = RECOVERY / "batch-20261001"
MANIFEST = Path("metadata/goal050_manifest.json")
TRANSFORMS = Path("metadata/goal050_transforms.json")
CROSSFIT = Path("data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json")
CURVES = Path("data/processed/dsdm/goal050-seawfb-modeling-foundation/learning_curves.json")
CELLS = Path("data/processed/dsdm/goal050-seawfb-modeling-foundation/cells.parquet")
MEMBERSHIPS = Path("data/processed/dsdm/goal050-seawfb-modeling-foundation/memberships.parquet")
HELPER = Path("scripts/goal052_ann_epoch_recovery.py")
DEEP_REVIEW = Path("evidence/seawfb_dsdm/goal052/ann-recovery-deep-probe-20261001.json")
NECTAR_REVIEW = Path("evidence/seawfb_dsdm/goal052/ann-recovery-nectar-probe-20261001.json")
OUTPUT = Path("evidence/seawfb_dsdm/goal052/ann-recovery-review-20261002.json")
SOURCE_PATHS = (
    Path("src/dsdm_phase1/seawfb_modeling.py"),
    Path("src/dsdm_phase1/goal051_seawfb_conventional.py"),
    Path("src/dsdm_phase1/model_adapters.py"),
    Path("src/dsdm_phase1/modeling_contract.py"),
    Path("src/dsdm_phase1/mainland_modeling.py"),
    Path("src/dsdm_phase1/goal050_seawfb_foundation.py"),
)
METHODS = ("ordinary", "q_full")
SEEDS = tuple(f"seed0{i}" for i in range(5))
FOLDS = tuple(range(5))


class ReviewError(RuntimeError):
    """A fail-closed acceptance error."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ReviewError(reason)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"invalid_json:{path}") from exc
    require(isinstance(value, dict), f"json_not_object:{path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def slug(value: str) -> str:
    return "_".join(value.lower().split())


def stable_seed(*parts: object) -> int:
    raw = "\x1f".join(map(str, parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


def current_identity(root: Path) -> dict[str, str]:
    source = {str(path): sha256_file(root / path) for path in SOURCE_PATHS}
    return {
        "config_sha256": sha256_file(root / GOAL051_CONFIG),
        "goal052_config_sha256": sha256_file(root / GOAL052_CONFIG),
        "goal050_manifest_sha256": sha256_file(root / MANIFEST),
        "goal050_transforms_sha256": sha256_file(root / TRANSFORMS),
        "goal050_crossfit_sha256": sha256_file(root / CROSSFIT),
        "goal050_curves_sha256": sha256_file(root / CURVES),
        "uv_lock_sha256": sha256_file(root / "uv.lock"),
        "source_sha256": digest_json(source),
    }


def inventory_records(inventory: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    require(inventory.get("schema_version") == "goal052-outer-inventory-v1", "inventory_schema")
    require(inventory.get("outer_response_rows_read") == 0, "inventory_outer_response_access")
    rows = inventory.get("conventional_target100", {}).get("records")
    require(isinstance(rows, list), "inventory_records_missing")
    records = {
        row["target"]: row
        for row in rows
        if row.get("ordinary", {}).get("family") == "shallow_ann"
    }
    require(len(records) == 40, f"inventory_ann_targets:{len(records)}")
    for target, row in records.items():
        for method in METHODS:
            spec = row.get(method, {})
            require(spec.get("family") == "shallow_ann", f"inventory_family:{target}:{method}")
            require(spec.get("candidate_id"), f"inventory_candidate:{target}:{method}")
            require(tuple(spec.get("seed_labels", ())) == SEEDS, f"inventory_seeds:{target}:{method}")
            bounds = spec.get("best_epoch_range")
            require(
                isinstance(bounds, list)
                and len(bounds) == 2
                and all(type(item) is int and 1 <= item <= 300 for item in bounds)
                and bounds[0] <= bounds[1],
                f"inventory_epoch_range:{target}:{method}",
            )
    return records


def verify_return_manifest(root: Path) -> dict[str, Any]:
    recovery_root = (root / RECOVERY).resolve()
    manifest_path = root / BATCH / "return-manifest.json"
    manifest = read_json(manifest_path)
    require(len(manifest) == 264, f"return_manifest_count:{len(manifest)}")
    for relative, expected in manifest.items():
        require(isinstance(relative, str) and isinstance(expected, str), "return_manifest_entry")
        path = (recovery_root / relative).resolve()
        require(path.is_relative_to(recovery_root), f"return_path_escape:{relative}")
        require(path.is_file() and not path.is_symlink(), f"return_file_missing:{relative}")
        require(sha256_file(path) == expected, f"return_hash_mismatch:{relative}")
    return {
        "entries": len(manifest),
        "manifest_sha256": sha256_file(manifest_path),
        "all_paths_confined_regular_files": True,
        "all_payload_hashes_verified": True,
        "values": manifest,
    }


def verify_batch_receipts(root: Path, manifest_review: Mapping[str, Any], expected_identity: Mapping[str, str]) -> dict[str, Any]:
    batch = root / BATCH
    receipts = {
        name: read_json(batch / name)
        for name in (
            "controller-claim.json",
            "launch.json",
            "process-group.json",
            "completion.json",
            "exit.json",
            "batch-exit.json",
            "ssh-return.json",
            "return-review.json",
            "controller-result.json",
        )
    }
    run_ids = {value.get("run_id") for value in receipts.values()}
    require(len(run_ids) == 1 and None not in run_ids, "batch_run_id_binding")
    run_id = next(iter(run_ids))
    completion = receipts["completion.json"]
    inner_exit = receipts["exit.json"]
    wrapper_exit = receipts["batch-exit.json"]
    returned = receipts["return-review.json"]
    controller = receipts["controller-result.json"]
    require(completion.get("status") == "complete", "batch_completion_status")
    require(completion.get("task_count") == completion.get("completed_count") == 80, "batch_completion_count")
    require(completion.get("failed") == [], "batch_failures_present")
    require(completion.get("outer_response_rows_read") == 0, "batch_outer_response_access")
    require(inner_exit.get("status") == "complete" and inner_exit.get("exit_code") == 0, "batch_inner_exit")
    require(wrapper_exit.get("status") == "finished" and wrapper_exit.get("exit_code") == 0, "batch_wrapper_exit")
    require(receipts["ssh-return.json"].get("returncode") == 0, "batch_ssh_exit")
    require(returned.get("files") == 264, "batch_return_count")
    require(returned.get("manifest_sha256") == manifest_review["manifest_sha256"], "batch_manifest_binding")
    require(returned.get("returned_file_hashes_verified") is True, "batch_native_return_review")
    require(returned.get("process_group_stopped") is True, "batch_process_group")
    require(returned.get("outer_response_rows_read") == 0, "batch_return_outer_response_access")
    require(controller.get("closeout_status") == "returned_verified_and_parked", "controller_closeout")
    require(controller.get("flavour") == "c3.xsmall", "controller_parked_flavour")
    require(controller.get("cloud_status") == "ACTIVE", "controller_cloud_status")
    expected_helper = sha256_file(root / HELPER)
    expected_inventory = sha256_file(root / INVENTORY)
    for name in ("launch.json", "completion.json", "exit.json"):
        bindings = receipts[name].get("bindings", {})
        require(bindings.get("helper_sha256") == expected_helper, f"batch_helper_binding:{name}")
        require(bindings.get("inventory_sha256") == expected_inventory, f"batch_inventory_binding:{name}")
        require(bindings.get("source_identity") == expected_identity, f"batch_identity_binding:{name}")
    return {
        "run_id": run_id,
        "native_completed_count": 80,
        "native_failed_count": 0,
        "native_exit_codes": {"inner": 0, "wrapper": 0, "ssh": 0},
        "process_group_stopped": True,
        "closeout_status": controller["closeout_status"],
        "parked_flavour": controller["flavour"],
        "local_closeout_artifact_sha256": {
            "controller-result.json": sha256_file(batch / "controller-result.json"),
            "return-review.json": sha256_file(batch / "return-review.json"),
            "parked-cloud-status.txt": sha256_file(batch / "parked-cloud-status.txt"),
        },
        "live_resource_assertion": "verified separately by the parent reviewer; this offline audit verifies only the hash-bound local closeout artifacts",
        "helper_sha256": expected_helper,
        "inventory_sha256": expected_inventory,
    }


def recovery_receipts(root: Path, expected_keys: set[tuple[str, str]]) -> tuple[dict[tuple[str, str], tuple[Path, dict[str, Any]]], list[tuple[Path, dict[str, Any]]]]:
    successes: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    failures: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((root / RECOVERY).glob("*.json")):
        value = read_json(path)
        if value.get("schema_version") != "goal052-ann-epoch-recovery-v1":
            continue
        key = (value.get("target"), value.get("method"))
        require(key in expected_keys, f"unexpected_recovery_key:{path.name}:{key}")
        if value.get("status") == "success":
            require(key not in successes, f"duplicate_success:{key}")
            successes[key] = (path, value)
        elif value.get("status") == "failed":
            failures.append((path, value))
        else:
            raise ReviewError(f"recovery_status:{path.name}")
    require(set(successes) == expected_keys, "success_inventory_mismatch")
    require(len(successes) == 80, f"success_count:{len(successes)}")
    return successes, failures


def accepted_endpoint(root: Path, target: str, row: Mapping[str, Any], summary: Mapping[str, Any], expected_identity: Mapping[str, str]) -> tuple[Path, dict[str, Any]]:
    stem = f"{slug(target)}_target100"
    directory = root / "data/processed/dsdm/goal051-seawfb-conventional-benchmark-v4/endpoints"
    result_path = directory / f"{stem}.json"
    prediction_path = directory / f"{stem}.parquet"
    result = read_json(result_path)
    require(result.get("identity") == expected_identity, f"endpoint_identity:{target}")
    require(result.get("target") == target and result.get("target_fraction") == 100, f"endpoint_key:{target}")
    require(result.get("outer_response_rows_read") == 0 and result.get("outer_predictor_rows_used") == 0, f"endpoint_outer_access:{target}")
    prediction_sha = sha256_file(prediction_path)
    require(result.get("prediction_sha256") == prediction_sha, f"endpoint_prediction_hash:{target}")
    private = {item.get("endpoint"): item for item in summary.get("private_outputs", [])}.get(stem)
    require(private is not None, f"summary_endpoint_missing:{target}")
    require(private.get("result_sha256") == sha256_file(result_path), f"summary_result_hash:{target}")
    require(private.get("prediction_sha256") == prediction_sha, f"summary_prediction_hash:{target}")
    selected = {
        "ordinary": result.get("families", {}).get("shallow_ann", {}).get("selected"),
        "q_full": result.get("q_linear", {}).get("full"),
    }
    for method, metadata in selected.items():
        require(isinstance(metadata, dict), f"endpoint_selection:{target}:{method}")
        spec = row[method]
        require(metadata.get("candidate_id") == spec["candidate_id"], f"endpoint_candidate:{target}:{method}")
        require(tuple(metadata.get("seed_labels", ())) == SEEDS, f"endpoint_seeds:{target}:{method}")
        require(metadata.get("best_epoch_range") == spec["best_epoch_range"], f"endpoint_epoch_range:{target}:{method}")
        if method == "q_full":
            require(metadata.get("family") == "shallow_ann", f"endpoint_q_family:{target}")
    return prediction_path, result


def read_selected_rows(path: Path, target: str, specs: Mapping[str, Mapping[str, Any]]) -> dict[str, pa.Table]:
    dataset = ds.dataset(path, format="parquet")
    common = (
        (ds.field("target") == target)
        & (ds.field("target_fraction") == 100)
        & (ds.field("family") == "shallow_ann")
    )
    filters = {}
    for method in METHODS:
        native_method = "family_selected" if method == "ordinary" else "q_linear"
        auxiliary = "none" if method == "ordinary" else "full"
        filters[method] = (
            common
            & (ds.field("method") == native_method)
            & (ds.field("auxiliary_size") == auxiliary)
            & (ds.field("candidate_id") == specs[method]["candidate_id"])
        )
    table = dataset.to_table(
        columns=["method", "auxiliary_size", "candidate_id", "fold", "cell_id", "y", "score"],
        filter=filters["ordinary"] | filters["q_full"],
        use_threads=False,
    )
    result = {}
    for method in METHODS:
        native_method = "family_selected" if method == "ordinary" else "q_linear"
        auxiliary = "none" if method == "ordinary" else "full"
        mask = pc.and_(
            pc.and_(pc.equal(table["method"], native_method), pc.equal(table["auxiliary_size"], auxiliary)),
            pc.equal(table["candidate_id"], specs[method]["candidate_id"]),
        )
        result[method] = table.filter(mask).select(["fold", "cell_id", "y", "score"])
    return result


def coverage_digest(folds: Sequence[int], cells: Sequence[str], labels: Sequence[int]) -> str:
    digest = hashlib.sha256()
    for fold, cell, label in zip(folds, cells, labels):
        digest.update(str(int(fold)).encode("ascii"))
        digest.update(b"\x1f")
        digest.update(str(cell).encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(str(int(label)).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def review_procedure(
    root: Path,
    target: str,
    method: str,
    spec: Mapping[str, Any],
    accepted: pa.Table,
    receipt_path: Path,
    receipt: Mapping[str, Any],
    expected_identity: Mapping[str, str],
    endpoint_sha256: str,
    manifest: Mapping[str, str],
    fit_seed_namespace: str,
) -> dict[str, Any]:
    key = f"{target}:{method}"
    require(receipt.get("status") == "success", f"receipt_status:{key}")
    require(receipt.get("target") == target and receipt.get("target_fraction") == 100, f"receipt_target:{key}")
    require(receipt.get("method") == method and receipt.get("family") == "shallow_ann", f"receipt_method:{key}")
    require(receipt.get("candidate_id") == spec["candidate_id"], f"receipt_candidate:{key}")
    require(tuple(receipt.get("seed_labels", ())) == SEEDS, f"receipt_seeds:{key}")
    require(tuple(receipt.get("prediction_seed_labels", ())) == SEEDS, f"receipt_prediction_seeds:{key}")
    require(receipt.get("identity") == expected_identity, f"receipt_identity:{key}")
    require(receipt.get("accepted_prediction_sha256") == endpoint_sha256, f"receipt_endpoint_hash:{key}")
    require(receipt.get("recovery_script_sha256") == sha256_file(root / HELPER), f"receipt_helper_hash:{key}")
    require(receipt.get("outer_response_rows_read") == 0, f"receipt_outer_access:{key}")

    relative_receipt = receipt_path.relative_to(root / RECOVERY).as_posix()
    require(manifest.get(relative_receipt) == sha256_file(receipt_path), f"manifest_receipt:{key}")
    evaluated_path = receipt_path.with_suffix(".evaluated.npz")
    relative_evaluated = evaluated_path.relative_to(root / RECOVERY).as_posix()
    evaluated_sha = sha256_file(evaluated_path)
    require(manifest.get(relative_evaluated) == evaluated_sha, f"manifest_evaluated:{key}")
    prediction_path = root / str(receipt.get("recovered_predictions_npz", ""))
    require(prediction_path.is_file() and prediction_path.parent == root / RECOVERY, f"receipt_prediction_path:{key}")
    prediction_sha = sha256_file(prediction_path)
    require(prediction_sha == receipt.get("recovered_predictions_sha256"), f"receipt_prediction_hash:{key}")
    relative_prediction = prediction_path.relative_to(root / RECOVERY).as_posix()
    require(manifest.get(relative_prediction) == prediction_sha, f"manifest_prediction:{key}")

    fit_receipts = receipt.get("fit_receipts")
    require(isinstance(fit_receipts, list) and len(fit_receipts) == 25, f"fit_receipt_count:{key}")
    fit_keys = {(item.get("fold"), item.get("seed_label")) for item in fit_receipts}
    expected_fit_keys = {(fold, seed) for fold in FOLDS for seed in SEEDS}
    require(fit_keys == expected_fit_keys and len(fit_keys) == 25, f"fit_receipt_keys:{key}")
    seed_integers = receipt.get("seed_integers")
    require(isinstance(seed_integers, dict) and len(seed_integers) == 25, f"seed_integer_count:{key}")
    epochs = []
    for item in fit_receipts:
        fold = item["fold"]
        seed_label = item["seed_label"]
        epoch = item.get("selected_epoch")
        require(type(epoch) is int and epoch == item.get("best_epoch"), f"selected_epoch:{key}:{fold}:{seed_label}")
        require(item.get("converged") is True and item.get("physical_fits") == 2, f"fit_contract:{key}:{fold}:{seed_label}")
        expected_seed = stable_seed(fit_seed_namespace, target, 100, fold, "shallow_ann", spec["candidate_id"], seed_label)
        require(item.get("seed") == expected_seed, f"fit_seed:{key}:{fold}:{seed_label}")
        require(seed_integers.get(f"fold{fold}:{seed_label}") == expected_seed, f"seed_map:{key}:{fold}:{seed_label}")
        epochs.append(epoch)
    bounds = spec["best_epoch_range"]
    require(all(bounds[0] <= epoch <= bounds[1] for epoch in epochs), f"epoch_outside_range:{key}")
    require([min(epochs), max(epochs)] == bounds, f"epoch_range_not_reproduced:{key}")
    median = statistics.median(epochs)
    require(float(median).is_integer() and int(median) == receipt.get("median_rounded_epoch"), f"epoch_median:{key}")

    fold_identities = receipt.get("fold_identities")
    require(isinstance(fold_identities, list) and len(fold_identities) == 5, f"fold_identity_count:{key}")
    fold_identity = {item.get("fold"): item for item in fold_identities}
    require(set(fold_identity) == set(FOLDS), f"fold_identity_keys:{key}")
    require(accepted.num_rows > 0, f"accepted_rows_missing:{key}")
    folds = accepted["fold"].to_numpy(zero_copy_only=False).astype(np.int8, copy=False)
    cells = accepted["cell_id"].to_pylist()
    labels = accepted["y"].to_numpy(zero_copy_only=False).astype(np.int8, copy=False)
    accepted_scores = accepted["score"].to_numpy(zero_copy_only=False).astype(np.float64, copy=False)
    require(np.isin(folds, FOLDS).all(), f"accepted_fold_values:{key}")
    require(np.isin(labels, (0, 1)).all(), f"accepted_label_values:{key}")
    require(
        np.isfinite(accepted_scores).all()
        and ((accepted_scores >= 0.0) & (accepted_scores <= 1.0)).all(),
        f"accepted_score_values:{key}",
    )
    require(len(set(zip(folds.tolist(), cells))) == accepted.num_rows, f"accepted_duplicate_rows:{key}")

    expected_array_names = {
        name
        for fold in FOLDS
        for name in (f"fold{fold}__score", f"fold{fold}__y", *(f"fold{fold}__seed_{seed}" for seed in SEEDS))
    }
    fold_rows = []
    positives = 0
    seed_parts: dict[str, list[np.ndarray]] = {seed: [] for seed in SEEDS}
    with np.load(evaluated_path, allow_pickle=False) as evaluated, np.load(prediction_path, allow_pickle=False) as predictions:
        require(set(evaluated.files) == expected_array_names, f"evaluated_array_inventory:{key}")
        require(set(predictions.files) == set(SEEDS), f"prediction_array_inventory:{key}")
        for fold in FOLDS:
            mask = folds == fold
            fold_cells = [cell for cell, keep in zip(cells, mask.tolist()) if keep]
            fold_labels = labels[mask]
            fold_scores = accepted_scores[mask]
            identity = fold_identity[fold]
            require(identity.get("row_count") == len(fold_cells), f"fold_row_count:{key}:{fold}")
            require(identity.get("cell_ids") == fold_cells, f"fold_cell_coverage:{key}:{fold}")
            observed_y = np.asarray(evaluated[f"fold{fold}__y"], dtype=np.int8)
            observed_score = np.asarray(evaluated[f"fold{fold}__score"], dtype=np.float64)
            require(np.array_equal(observed_y, fold_labels), f"evaluated_y:{key}:{fold}")
            require(np.array_equal(observed_score, fold_scores), f"accepted_score:{key}:{fold}")
            seeds = []
            for seed in SEEDS:
                values = np.asarray(evaluated[f"fold{fold}__seed_{seed}"], dtype=np.float64)
                require(values.shape == fold_scores.shape, f"seed_shape:{key}:{fold}:{seed}")
                require(np.isfinite(values).all() and ((values >= 0.0) & (values <= 1.0)).all(), f"seed_values:{key}:{fold}:{seed}")
                seeds.append(values)
                seed_parts[seed].append(values)
            reconstructed = np.mean(np.vstack(seeds), axis=0)
            require(np.array_equal(reconstructed, observed_score), f"seed_mean:{key}:{fold}")
            fold_rows.append(len(fold_cells))
            positives += int(np.count_nonzero(fold_labels))
        for seed in SEEDS:
            reconstructed_seed = np.concatenate(seed_parts[seed])
            require(np.array_equal(reconstructed_seed, np.asarray(predictions[seed], dtype=np.float64)), f"prediction_payload:{key}:{seed}")

    return {
        "target": target,
        "method": method,
        "candidate_id": spec["candidate_id"],
        "median_rounded_epoch": int(median),
        "observed_epoch_range": [min(epochs), max(epochs)],
        "fit_receipts": 25,
        "physical_fits": sum(int(item["physical_fits"]) for item in fit_receipts),
        "rows": accepted.num_rows,
        "positive_rows": positives,
        "fold_rows": fold_rows,
        "coverage_sha256": coverage_digest(folds.tolist(), cells, labels.tolist()),
        "receipt_sha256": sha256_file(receipt_path),
        "evaluated_arrays_sha256": evaluated_sha,
        "recovered_seed_arrays_sha256": prediction_sha,
        "accepted_endpoint_predictions_sha256": endpoint_sha256,
        "exact_checks": {
            "accepted_cell_y_fold_coverage": True,
            "all_five_seed_vectors_reconstructed": True,
            "seed_mean_equals_saved_and_accepted_score": True,
            "concatenated_seed_payload_equals_evaluated_arrays": True,
        },
    }


def verify_failed_deep_attempt(root: Path, failures: Sequence[tuple[Path, Mapping[str, Any]]], manifest: Mapping[str, str], selected_paths: set[Path]) -> dict[str, Any]:
    require(len(failures) == 1, f"failed_attempt_count:{len(failures)}")
    path, receipt = failures[0]
    require(path.name == "chalcites_minutillus_ordinary.json", "deep_failure_path")
    require((receipt.get("target"), receipt.get("method")) == ("Chalcites minutillus", "ordinary"), "deep_failure_key")
    require(receipt.get("status") == "failed" and receipt.get("error_type") == "PredictionMismatch", "deep_failure_status")
    require(str(receipt.get("error", "")).startswith("prediction_mismatch:"), "deep_failure_reason")
    require(path not in selected_paths, "deep_failure_selected")
    evaluated = root / str(receipt.get("evaluated_predictions_npz", ""))
    require(evaluated.is_file() and sha256_file(evaluated) == receipt.get("evaluated_predictions_sha256"), "deep_failure_payload")
    for item in (path, evaluated):
        relative = item.relative_to(root / RECOVERY).as_posix()
        require(manifest.get(relative) == sha256_file(item), f"deep_failure_manifest:{relative}")
    review = read_json(root / DEEP_REVIEW)
    require(review.get("status") == "failed_exact_prediction_replay" and review.get("epochs_accepted") is False, "deep_review_status")
    require(review.get("exact_gate_relaxed") is False and review.get("q_full_attempted") is False, "deep_review_gate")
    for relative, expected in review.get("private_evidence", {}).items():
        evidence_path = root / relative
        require(evidence_path.is_file() and sha256_file(evidence_path) == expected, f"deep_review_hash:{relative}")
    return {
        "receipt": str(path.relative_to(root)),
        "receipt_sha256": sha256_file(path),
        "evaluated_arrays_sha256": sha256_file(evaluated),
        "error": receipt["error"],
        "epochs_accepted": 0,
        "selected_for_recovery": False,
        "preserved_private_evidence_hashes_verified": len(review["private_evidence"]),
    }


def build_review(root: Path) -> dict[str, Any]:
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    inventory = read_json(root / INVENTORY)
    records = inventory_records(inventory)
    expected_keys = {(target, method) for target in records for method in METHODS}
    expected_identity = inventory["inputs"]["accepted_goal052_identity"]["goal051_identity"]
    summary = read_json(root / SUMMARY)
    require(sha256_file(root / SUMMARY) == inventory["inputs"]["sha256"]["goal051_summary"], "summary_inventory_hash")
    require(summary.get("identity") == expected_identity, "summary_identity")
    require(summary.get("outer_response_rows_read") == 0 and summary.get("outer_predictor_rows_used") == 0, "summary_outer_access")
    observed_identity = current_identity(root)
    require(observed_identity == expected_identity, "current_identity_drift")
    foundation_manifest = read_json(root / MANIFEST)
    require(foundation_manifest.get("bindings", {}).get("cells") == sha256_file(root / CELLS), "cells_hash_drift")
    require(foundation_manifest.get("bindings", {}).get("memberships") == sha256_file(root / MEMBERSHIPS), "memberships_hash_drift")
    config = read_json(root / GOAL051_CONFIG)
    fit_seed_namespace = config.get("execution", {}).get("fit_seed_namespace")
    require(isinstance(fit_seed_namespace, str) and fit_seed_namespace, "fit_seed_namespace")

    manifest_review = verify_return_manifest(root)
    batch_review = verify_batch_receipts(root, manifest_review, expected_identity)
    successes, failures = recovery_receipts(root, expected_keys)
    procedures = []
    selected_paths = set()
    total_rows = 0
    total_fit_receipts = 0
    coverage_by_target: dict[str, str] = {}
    for target in sorted(records):
        prediction_path, endpoint = accepted_endpoint(root, target, records[target], summary, expected_identity)
        selected_rows = read_selected_rows(prediction_path, target, records[target])
        for method in METHODS:
            receipt_path, receipt = successes[(target, method)]
            selected_paths.add(receipt_path)
            item = review_procedure(
                root,
                target,
                method,
                records[target][method],
                selected_rows[method],
                receipt_path,
                receipt,
                expected_identity,
                endpoint["prediction_sha256"],
                manifest_review["values"],
                fit_seed_namespace,
            )
            previous = coverage_by_target.setdefault(target, item["coverage_sha256"])
            require(previous == item["coverage_sha256"], f"method_coverage_drift:{target}")
            procedures.append(item)
            total_rows += item["rows"]
            total_fit_receipts += item["fit_receipts"]
    deep = verify_failed_deep_attempt(root, failures, manifest_review["values"], selected_paths)
    nectar = read_json(root / NECTAR_REVIEW)
    require(nectar.get("deep_failed_attempt_preserved") is True, "nectar_deep_preservation")
    require(nectar.get("helper_sha256") == batch_review["helper_sha256"], "nectar_helper_binding")
    require(nectar.get("source_identity") == expected_identity, "nectar_identity_binding")

    manifest_values = manifest_review.pop("values")
    return {
        "schema_version": "goal052-ann-recovery-independent-review-v1",
        "status": "accepted_exact_recovery",
        "scientific_target": "recover exact selected shallow-ANN epoch budgets for retained-full outer refits without changing the frozen Goal051 estimand",
        "estimand_scope": {
            "procedures": "40 selected shallow-ANN targets x ordinary/q_full",
            "prediction_target": "accepted Goal051 retained-training out-of-fold cell probabilities",
            "inference_change": "none; exact epoch-budget recovery only",
            "outer_response_rows_read": 0,
            "epoch_source": "25 exact fold-seed discovery receipts per procedure; ranges used only as containment checks",
        },
        "checks": {
            "exact_inventory_80_unique_keys": True,
            "current_source_config_and_inputs_match_accepted_identity": True,
            "endpoint_result_and_prediction_hashes_match_accepted_summary": True,
            "candidate_and_seed_bindings_match_inventory_and_endpoints": True,
            "all_return_manifest_hashes_verified": True,
            "all_success_payload_hashes_verified": True,
            "all_2000_fold_seed_receipts_unique_and_seed_bound": True,
            "all_80_saved_seed_means_reconstructed_exactly": True,
            "all_cell_y_fold_rows_match_accepted_predictions": True,
            "all_epoch_ranges_and_rounded_medians_reproduced": True,
            "failed_deep_attempt_preserved_and_unused": True,
            "no_epoch_inferred_from_range": True,
            "source_helper_identity_unchanged": True,
        },
        "counts": {
            "targets": len(records),
            "procedures": len(procedures),
            "fit_receipts": total_fit_receipts,
            "physical_fits_represented": sum(item["physical_fits"] for item in procedures),
            "accepted_prediction_rows_checked_across_procedures": total_rows,
            "returned_manifest_files": manifest_review["entries"],
            "failed_attempts_preserved": len(failures),
        },
        "provenance": {
            "inventory": str(INVENTORY),
            "inventory_sha256": batch_review["inventory_sha256"],
            "accepted_summary": str(SUMMARY),
            "accepted_summary_sha256": sha256_file(root / SUMMARY),
            "accepted_identity": expected_identity,
            "recovery_helper": str(HELPER),
            "recovery_helper_sha256": batch_review["helper_sha256"],
            "return_manifest": str(BATCH / "return-manifest.json"),
            "return_manifest_sha256": manifest_review["manifest_sha256"],
            "review_script": str(Path(__file__).resolve().relative_to(root)),
            "review_script_sha256": sha256_file(Path(__file__).resolve()),
            "execution": "one process; NumPy, Arrow, BLAS and OpenMP threads fixed at one; endpoint Parquet read one target at a time",
        },
        "batch_closeout": batch_review,
        "failed_deep_attempt": deep,
        "procedures": procedures,
        "limitations": [
            "This accepts exact retained-only epoch recovery; it does not qualify the retained-full outer fitting or prediction pipeline.",
            "The accepted Goal051 artifacts retain each five-seed fold mean, not the original per-seed vectors. The recovered per-seed arrays are hash-, seed-, and coverage-bound and reproduce every accepted mean exactly, but cannot be compared with unavailable original per-seed arrays.",
            "Exact agreement establishes original-runtime reproduction, not a causal diagnosis of the earlier Deep-server floating-point mismatch.",
            "No outer response, outer membership, outer fit, or ecological outcome was inspected.",
        ],
        "independent_scientific_review_scope": "This completed independent audit resolves the mechanical epoch-budget decision. Scientific review remains necessary for the later outer evaluation and claims, where it can affect inference.",
        "recommendation": "Accept the 80 recovered epoch budgets for the prospective retained-full refit. Preserve the failed Deep attempt as numerical-portability evidence and retain the original-runtime requirement.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output or (root / OUTPUT)
    review = build_review(root)
    atomic_json(output, review)
    print(json.dumps({"status": review["status"], **review["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
