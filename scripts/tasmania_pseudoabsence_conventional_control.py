"""Qualify the Thylogale conventional inner negative control.

This is an external, read-only verifier for the Tasmania pseudoabsence
sensitivity.  It authenticates the accepted Goal036 conventional OOF export,
derives the 95 selected Thylogale inner tasks, validates their completed
sensitivity leaves, and requires exact equality of canonical row identity and
float64 probabilities.  It never reads the outer-held response vault and its
aggregate receipt contains no row identifiers, probabilities, or labels.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SPECIES = "thylogale_billardierii"
FOLDS = tuple(f"fold{index:02d}" for index in range(5))
ENDPOINTS = (
    "fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02",
    "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02",
    "fraction100/full",
)
SEEDS_BY_FAMILY = {
    "elastic_net": tuple(f"seed{index:02d}" for index in range(5)),
    "random_forest": tuple(f"seed{index:02d}" for index in range(5)),
    "hist_gradient_boosting": ("seed00",),
    "shallow_ann": tuple(f"seed{index:02d}" for index in range(5)),
}

PRIVATE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/conventional")
SELECTION_REL = Path("evidence/dsdm_inner_evaluation/goal036/conventional_selection.csv")
MANIFEST_REL = Path("data/processed/dsdm/goal036-inner-evaluation/private/conventional_manifest.json")
PARQUET_REL = Path("data/processed/dsdm/goal036-inner-evaluation/private/conventional_selected_oof.parquet")
VALIDATION_REL = Path("data/processed/dsdm/goal036-inner-evaluation/private/validate-receipt.json")
EXPORTER_REL = Path("src/dsdm/conventional_oof_export.py")
ASSESSMENT_CONFIG_REL = Path("config/tasmania_outer_assessment.json")
OUTPUT_REL = Path("evidence/tasmania_pseudoabsence/20261009/conventional-inner-negative-control.json")

SELECTION_SHA256 = "3e05784670f58e88144dcbda43819c3811e8303c59cd15c36f23fdf38736a561"
MANIFEST_SHA256 = "98771a834391e3c3c9f3e0f40939707cfc55c4bd94ba4fe855e246947b1a3d09"
MANIFEST_DIGEST = "1bb5bcc7ea450d87a2ddb8b5ea3a11ac96163e8001e0a3cc11d2c6853b09b5bc"
PARQUET_SHA256 = "250a33d2111fc420e620535be113f14a6bd68ce26ae910b514571f397ebc2001"
VALIDATION_SHA256 = "9c6f8195d5bc291aa43c8cb2476291af39e7ac0f10613c5f2065200f86ef0c2d"
VALIDATION_DIGEST = "b3ff205c27522752a6671dc95eb6ef4bab5bb758d62302a68f71a1629a81a920"
EXPORTER_SHA256 = "96cbe8d2b7a1b2cba5749c2fa3d44de4c417fdd4dbb58ac12c579c814b8f0a95"
ASSESSMENT_CONFIG_SHA256 = "0913b323f1c53addee4cc7c0f181e850ee08ff5fe0fcbdd776450652f13e7a48"
PRODUCER_COMMIT = "f85e45922e182858fd351fdaf4f1b36b33fb4f2f"
PRIVATE_CORE_MANIFEST_SHA256 = "836384b71fa03797e3fe92052aed2255b737d59a347aaa8614830a28d0851ab6"
GOAL029_SELECTION_SHA256 = "d8d91c15bb37263a9979e3b2c77709eb7edeca9b9299c7a7a5cb7cf26178933b"
CANDIDATE_STATES_SHA256 = "83cce3b440ca46dfbe6c185f92d81317bfa6c6a5dfd3f47f0e09039bc2cd0a2f"
RUN_SHA256 = "af2ce85547afcee2b6cebe952cd6d115f7e8a02339c8b2638ada4a5b12642850"
SOURCE_AUDIT_SHA256 = "8b0c79b638b82bcc74f8b186cbe667886be778078cdb49a8c484d6be15d8af68"
CHECKPOINT_INVENTORY_DIGEST = "b04c6534122f8c25b5d69032ff9bd884cfe1f726b96ef25ae4643e213f68abda"
THYLOGALE_ROW_IDENTITY_DIGEST = "1a868e60120582ffce6c5f0c51a83618745505c91b51d6d285b3cd6d72003d35"


class ControlVerificationError(ValueError):
    """Raised when the negative-control qualification must fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ControlVerificationError(message)


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


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"json_missing:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlVerificationError(f"json_invalid:{path}") from exc
    require(isinstance(value, dict), f"json_object_required:{path}")
    return value


def validate_self_digest(value: Mapping[str, Any], key: str, message: str) -> str:
    body = dict(value)
    claimed = body.pop(key, None)
    require(isinstance(claimed, str) and digest_value(body) == claimed, message)
    return claimed


@dataclass(frozen=True)
class InnerTask:
    species: str
    endpoint: str
    family: str
    candidate: str
    held_fold: str
    seed_label: str


def task_digest(task: InnerTask) -> str:
    return digest_value({"lane": "inner", "task": asdict(task)})


def load_expected_tasks(selection_path: Path) -> tuple[InnerTask, ...]:
    require(sha256_file(selection_path) == SELECTION_SHA256, "accepted_selection_sha256_mismatch")
    with selection_path.open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row.get("species") == SPECIES]
    require(len(rows) == 7, "thylogale_selection_count_mismatch")
    by_endpoint = {str(row["endpoint"]): row for row in rows}
    require(set(by_endpoint) == set(ENDPOINTS) and len(by_endpoint) == len(rows), "thylogale_endpoint_inventory_mismatch")
    tasks: list[InnerTask] = []
    for endpoint in ENDPOINTS:
        row = by_endpoint[endpoint]
        family = str(row["selected_family"])
        candidate = str(row["selected_candidate"])
        seeds = SEEDS_BY_FAMILY.get(family)
        require(seeds is not None and int(row["seed_count"]) == len(seeds), "thylogale_seed_inventory_mismatch")
        for fold in FOLDS:
            for seed in seeds:
                tasks.append(InnerTask(SPECIES, endpoint, family, candidate, fold, seed))
    require(len(tasks) == 95 and len({task_digest(task) for task in tasks}) == 95, "thylogale_task_crossproduct_mismatch")
    require(all(task.family != "shallow_ann" for task in tasks), "thylogale_ann_scope_changed")
    return tuple(tasks)


def verify_accepted_authority(root: Path) -> dict[str, str]:
    paths = {
        "manifest": root / MANIFEST_REL,
        "parquet": root / PARQUET_REL,
        "selection": root / SELECTION_REL,
        "validation_receipt": root / VALIDATION_REL,
        "exporter_source": root / EXPORTER_REL,
        "assessment_config": root / ASSESSMENT_CONFIG_REL,
    }
    expected = {
        "manifest": MANIFEST_SHA256,
        "parquet": PARQUET_SHA256,
        "selection": SELECTION_SHA256,
        "validation_receipt": VALIDATION_SHA256,
        "exporter_source": EXPORTER_SHA256,
        "assessment_config": ASSESSMENT_CONFIG_SHA256,
    }
    for name, path in paths.items():
        require(path.is_file() and not path.is_symlink(), f"accepted_authority_missing:{name}")
        require(sha256_file(path) == expected[name], f"accepted_authority_sha256_mismatch:{name}")

    manifest = read_json(paths["manifest"])
    require(validate_self_digest(manifest, "manifest_digest", "accepted_manifest_self_digest_mismatch") == MANIFEST_DIGEST, "accepted_manifest_digest_mismatch")
    required_manifest = {
        "schema_version": "goal036-conventional-oof-export-v1",
        "producer_commit": PRODUCER_COMMIT,
        "private_core_manifest_sha256": PRIVATE_CORE_MANIFEST_SHA256,
        "selection_sha256": GOAL029_SELECTION_SHA256,
        "candidate_states_sha256": CANDIDATE_STATES_SHA256,
        "run_sha256": RUN_SHA256,
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "checkpoint_inventory_digest": CHECKPOINT_INVENTORY_DIGEST,
        "parquet_sha256": PARQUET_SHA256,
        "selected_checkpoints": 952,
        "family_strata": 280,
        "rows": 1313641,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    require(all(manifest.get(key) == value for key, value in required_manifest.items()), "accepted_manifest_producer_chain_mismatch")
    require(manifest.get("row_identity_digest_by_species", {}).get(SPECIES) == THYLOGALE_ROW_IDENTITY_DIGEST, "accepted_thylogale_identity_authority_mismatch")

    validation = read_json(paths["validation_receipt"])
    require(validate_self_digest(validation, "receipt_digest", "goal036_validation_self_digest_mismatch") == VALIDATION_DIGEST, "goal036_validation_digest_mismatch")
    conventional = validation.get("conventional_audit", {})
    require(
        validation.get("success") is True
        and validation.get("outer_attempted") == validation.get("outer_opened") == 0
        and validation.get("execution_source_digests", {}).get("conventional_oof_export") == EXPORTER_SHA256
        and validation.get("table_digests", {}).get("conventional_selection.csv") == SELECTION_SHA256
        and conventional.get("manifest_digest") == MANIFEST_DIGEST
        and conventional.get("parquet_sha256") == PARQUET_SHA256
        and conventional.get("checkpoint_inventory_digest") == CHECKPOINT_INVENTORY_DIGEST,
        "goal036_validation_chain_mismatch",
    )
    config = read_json(paths["assessment_config"])
    authority = config.get("authorities", {}).get("goal036_conventional_selection", {})
    require(authority.get("path") == str(SELECTION_REL) and authority.get("sha256") == SELECTION_SHA256, "assessment_selection_authority_mismatch")
    return expected


def load_baseline(tasks: Sequence[InnerTask], parquet_path: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    expected = {
        (task.endpoint.split("/")[0], task.endpoint.split("/")[1], task.family, task.candidate, task.seed_label, task.held_fold): task
        for task in tasks
    }
    table = pq.read_table(
        parquet_path,
        columns=["species_id", "fraction_id", "ladder_id", "model_family", "candidate_id", "seed_label", "fold_id", "row_index", "row_token", "score"],
        filters=[("species_id", "=", SPECIES)],
    )
    require(table.num_rows > 0 and pc.all(pc.equal(table["species_id"], SPECIES)).as_py(), "baseline_species_filter_failed")
    grouped: dict[str, list[tuple[int, str, float]]] = {task_digest(task): [] for task in tasks}
    columns = table.to_pydict()
    for index in range(table.num_rows):
        key = tuple(columns[name][index] for name in ("fraction_id", "ladder_id", "model_family", "candidate_id", "seed_label", "fold_id"))
        task = expected.get(key)
        if task is not None:
            token = columns["row_token"][index]
            try:
                identity = json.loads(token)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ControlVerificationError("baseline_row_token_invalid") from exc
            require(isinstance(identity, list) and len(identity) == 2 and identity[0] == SPECIES and isinstance(identity[1], str), "baseline_row_identity_invalid")
            grouped[task_digest(task)].append((int(columns["row_index"][index]), identity[1], float(columns["score"][index])))
    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for task in tasks:
        key = task_digest(task)
        rows = sorted(grouped[key])
        require(rows and [row[0] for row in rows] == list(range(len(rows))), f"baseline_row_index_mismatch:{key}")
        ids = np.asarray([row[1] for row in rows], dtype=str)
        scores = np.asarray([row[2] for row in rows], dtype=np.float64)
        require(len(set(ids.tolist())) == len(ids) and np.isfinite(scores).all(), f"baseline_leaf_invalid:{key}")
        result[key] = (ids, scores)
    require(set(result) == {task_digest(task) for task in tasks}, "baseline_task_inventory_mismatch")
    return result


def prediction_digest(ids: np.ndarray, scores: np.ndarray) -> str:
    canonical_scores = np.asarray(scores, dtype=">f8")
    return digest_value({
        "keys": np.asarray(ids).tolist(),
        "scores_be_f8_sha256": hashlib.sha256(canonical_scores.tobytes(order="C")).hexdigest(),
    })


def compare_leaf_arrays(
    expected_ids: np.ndarray,
    expected_scores: np.ndarray,
    observed_ids: np.ndarray,
    observed_scores: np.ndarray,
) -> int:
    expected_ids = np.asarray(expected_ids)
    observed_ids = np.asarray(observed_ids)
    expected_scores = np.asarray(expected_scores, dtype=np.float64)
    observed_scores = np.asarray(observed_scores, dtype=np.float64)
    require(expected_ids.ndim == observed_ids.ndim == expected_scores.ndim == observed_scores.ndim == 1, "control_array_rank_mismatch")
    require(expected_ids.dtype.kind == observed_ids.dtype.kind == "U", "control_identity_dtype_mismatch")
    require(np.array_equal(expected_ids, observed_ids), "control_identity_or_order_mismatch")
    require(np.array_equal(expected_scores, observed_scores), "control_probability_mismatch")
    return len(expected_ids)


def verify_sensitivity(
    root: Path,
    private_root: Path,
    tasks: Sequence[InnerTask],
    baseline: Mapping[str, tuple[np.ndarray, np.ndarray]],
) -> tuple[list[dict[str, Any]], int, str]:
    require(not (private_root / "ABORT.json").exists(), "conventional_abort_present")
    preparation = read_json(private_root / "preparation.json")
    preparation_digest = validate_self_digest(preparation, "receipt_digest", "preparation_self_digest_mismatch")
    require(
        preparation.get("schema_version") == "tasmania-pseudoabsence-conventional-preparation-v1"
        and preparation.get("success") is True
        and preparation.get("fitting") is False
        and preparation.get("scoring") is False
        and preparation.get("execution_contract", {}).get("outer_held_response_vault_reads") == 0,
        "preparation_contract_mismatch",
    )
    caps = read_json(private_root / "production-caps.json")
    caps_digest = validate_self_digest(caps, "receipt_digest", "production_caps_self_digest_mismatch")
    require(
        caps.get("schema_version") == "tasmania-pseudoabsence-conventional-production-caps-v1"
        and caps.get("status") == "assigned"
        and caps.get("preparation_receipt_digest") == preparation_digest,
        "production_caps_contract_mismatch",
    )
    closure_path = private_root / "inner-closure.json"
    closure = read_json(closure_path)
    closure_digest = validate_self_digest(closure, "receipt_digest", "inner_closure_self_digest_mismatch")
    require(
        closure.get("schema_version") == "tasmania-pseudoabsence-conventional-inner-closure-v1"
        and closure.get("success") is True and closure.get("lane") == "inner"
        and closure.get("logical_tasks") == 1200 and closure.get("physical_fits") == 1725
        and closure.get("held_response_vault_read") is False
        and closure.get("production_caps_receipt_digest") == caps_digest,
        "inner_closure_contract_mismatch",
    )
    records = closure.get("records")
    require(isinstance(records, list) and len(records) == 1200 and digest_value(records) == closure.get("inventory_digest"), "inner_closure_record_inventory_mismatch")
    closure_records = {record.get("task_digest"): record for record in records if isinstance(record, dict)}
    require(len(closure_records) == 1200, "inner_closure_duplicate_task")

    safe_records: list[dict[str, Any]] = []
    compared_rows = 0
    binding_reference: Mapping[str, str] | None = None
    for task in tasks:
        key = task_digest(task)
        leaf = private_root / "inner/leaves" / key
        require(leaf.is_dir() and not leaf.is_symlink(), f"sensitivity_leaf_missing:{key}")
        require({item.name for item in leaf.iterdir()} == {"encoder.json", "model.model", "predictions.npz", "receipt.json"}, f"sensitivity_leaf_inventory_mismatch:{key}")
        require(not any(item.is_symlink() for item in leaf.iterdir()), f"sensitivity_leaf_symlink:{key}")
        receipt_path = leaf / "receipt.json"
        receipt = read_json(receipt_path)
        receipt_digest = validate_self_digest(receipt, "receipt_digest", f"sensitivity_leaf_self_digest_mismatch:{key}")
        require(
            receipt.get("schema_version") == "tasmania-pseudoabsence-conventional-inner-leaf-v1"
            and receipt.get("task") == asdict(task) and receipt.get("task_digest") == key
            and receipt.get("physical_fits") == 1 and receipt.get("selected_epoch") is None
            and receipt.get("discovery_report") is None and receipt.get("discovery_model_sha256") is None
            and receipt.get("labels_in_prediction_batch") is False
            and receipt.get("held_response_vault_read") is False
            and receipt.get("preparation_receipt_digest") == preparation_digest
            and receipt.get("production_caps_receipt_digest") == caps_digest,
            f"sensitivity_leaf_contract_mismatch:{key}",
        )
        bindings = receipt.get("bindings")
        require(isinstance(bindings, dict), f"sensitivity_leaf_bindings_missing:{key}")
        if binding_reference is None:
            binding_reference = bindings
        require(bindings == binding_reference == closure.get("bindings"), f"sensitivity_leaf_binding_mismatch:{key}")
        require(
            bindings.get("script_sha256") == sha256_file(root / "scripts/tasmania_pseudoabsence_conventional.py"),
            f"sensitivity_runner_source_mismatch:{key}",
        )
        require(sha256_file(leaf / "model.model") == receipt.get("model_sha256"), f"sensitivity_model_sha256_mismatch:{key}")
        require(sha256_file(leaf / "encoder.json") == receipt.get("encoder_sha256"), f"sensitivity_encoder_sha256_mismatch:{key}")
        prediction_path = leaf / "predictions.npz"
        prediction_sha = sha256_file(prediction_path)
        require(prediction_sha == receipt.get("prediction_sha256"), f"sensitivity_prediction_sha256_mismatch:{key}")
        try:
            with np.load(prediction_path, allow_pickle=False) as loaded:
                require(set(loaded.files) == {"grid_cell_id", "scores"}, f"sensitivity_prediction_inventory_mismatch:{key}")
                observed_ids = np.array(loaded["grid_cell_id"], copy=True)
                observed_scores = np.asarray(loaded["scores"], dtype=np.float64).copy()
        except (OSError, ValueError) as exc:
            raise ControlVerificationError(f"sensitivity_prediction_invalid:{key}") from exc
        require(prediction_digest(observed_ids, observed_scores) == receipt.get("prediction_digest"), f"sensitivity_prediction_digest_mismatch:{key}")
        expected_ids, expected_scores = baseline[key]
        compared_rows += compare_leaf_arrays(expected_ids, expected_scores, observed_ids, observed_scores)

        completed_path = private_root / "inner/attempts" / key / "completed.json"
        completed = read_json(completed_path)
        require(
            completed.get("schema_version") == "tasmania-pseudoabsence-conventional-fit-complete-v1"
            and completed.get("task_digest") == key
            and completed.get("receipt_digest") == receipt_digest
            and type(completed.get("completed_unix_ns")) is int,
            f"sensitivity_completion_mismatch:{key}",
        )
        closed = closure_records.get(key)
        require(
            isinstance(closed, dict)
            and closed.get("receipt_digest") == receipt_digest
            and closed.get("model_sha256") == receipt.get("model_sha256")
            and closed.get("prediction_digest") == receipt.get("prediction_digest")
            and closed.get("physical_fits") == 1,
            f"sensitivity_closure_leaf_mismatch:{key}",
        )
        safe_records.append({
            "task_digest": key,
            "receipt_digest": receipt_digest,
            "receipt_sha256": sha256_file(receipt_path),
            "prediction_sha256": prediction_sha,
            "completion_sha256": sha256_file(completed_path),
        })
    require(len(safe_records) == 95 and compared_rows == 24092, "sensitivity_comparison_arithmetic_mismatch")
    return safe_records, compared_rows, closure_digest


def assert_aggregate_privacy(receipt: Mapping[str, Any]) -> None:
    serialized = canonical(receipt).decode("utf-8")
    forbidden = ("grid_cell_id", "row_token", "y_true", '"score"', '"scores"')
    require(not any(token in serialized for token in forbidden), "aggregate_receipt_discloses_row_data")


def write_idempotent(path: Path, value: Mapping[str, Any]) -> None:
    raw = canonical(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == raw, "existing_output_drift")
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def verify(root: Path, private_root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    private_root = private_root.resolve()
    output = output.resolve()
    require(private_root == (root / PRIVATE_REL).resolve() or private_root.is_relative_to(root / "data/processed/dsdm"), "private_root_outside_project_data")
    authority_hashes = verify_accepted_authority(root)
    tasks = load_expected_tasks(root / SELECTION_REL)
    baseline = load_baseline(tasks, root / PARQUET_REL)
    records, compared_rows, closure_digest = verify_sensitivity(root, private_root, tasks, baseline)
    receipt: dict[str, Any] = {
        "schema_version": "tasmania-pseudoabsence-conventional-inner-negative-control-v1",
        "success": True,
        "species": SPECIES,
        "expected_tasks": 95,
        "compared_tasks": len(records),
        "compared_predictions": compared_rows,
        "identity_match": "exact_ordered",
        "probability_match": "numpy_array_equal_float64",
        "maximum_absolute_probability_difference": 0.0,
        "epoch_check": "not_applicable_no_selected_shallow_ann",
        "selected_shallow_ann_tasks": 0,
        "leaf_inventory_digest": digest_value(records),
        "inner_closure_receipt_digest": closure_digest,
        "accepted_authorities": authority_hashes,
        "accepted_manifest_digest": MANIFEST_DIGEST,
        "accepted_checkpoint_inventory_digest": CHECKPOINT_INVENTORY_DIGEST,
        "accepted_thylogale_row_identity_digest": THYLOGALE_ROW_IDENTITY_DIGEST,
        "verifier_sha256": sha256_file(Path(__file__).resolve()),
        "outer_held_response_vault_read": False,
        "contains_row_identifiers": False,
        "contains_probabilities": False,
        "contains_response_labels": False,
    }
    assert_aggregate_privacy(receipt)
    receipt["receipt_digest"] = digest_value(receipt)
    write_idempotent(output, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--private-root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    private_root = (arguments.private_root or root / PRIVATE_REL).resolve()
    output = (arguments.output or root / OUTPUT_REL).resolve()
    receipt = verify(root, private_root, output)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
