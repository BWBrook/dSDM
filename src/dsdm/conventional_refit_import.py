"""Validate the copied Goal 029 full-training conventional model set.

The producer's complete publication validator remains the foundation-level
authority.  This module independently checks the copied selected models and
their frozen challenge predictions under the locked conventional runtime.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
from typing import Any, Mapping, Sequence

import numpy as np

from .contracts import ENDPOINTS, SPECIES
from .final_inner_data import canonical, digest_value
from .outer_ready import OuterReadyConfig, OuterReadyError, _is_digest, _sha_file, _write_json, load_config
from dsdm_phase1.goal029_production import challenge_from_payload, canonical_prediction_bytes_sha256
from dsdm_phase1.model_adapters import load_fitted_model


FAMILIES = ("intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann")
CROSS_PLATFORM_ATOL = 1e-12
SEEDS_BY_FAMILY = {
    "intercept": ("seed00",),
    "elastic_net": ("seed00", "seed01", "seed02", "seed03", "seed04"),
    "random_forest": ("seed00", "seed01", "seed02", "seed03", "seed04"),
    "hist_gradient_boosting": ("seed00",),
    "shallow_ann": ("seed00", "seed01", "seed02", "seed03", "seed04"),
}
GOAL029_ENDPOINTS = tuple(tuple(endpoint.split("/")) for endpoint in ENDPOINTS)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OuterReadyError(message)


def _cross_platform_score_difference(
    local_scores: np.ndarray,
    producer_scores: np.ndarray,
) -> float:
    local = np.asarray(local_scores, dtype=np.float64)
    producer = np.asarray(producer_scores, dtype=np.float64)
    _require(
        local.shape == producer.shape
        and local.ndim == 1
        and local.size > 0
        and np.isfinite(local).all()
        and np.isfinite(producer).all()
        and np.all((local >= 0.0) & (local <= 1.0))
        and np.all((producer >= 0.0) & (producer <= 1.0)),
        "cross-platform challenge scores invalid",
    )
    return float(np.max(np.abs(local - producer)))


def conventional_runtime(config: OuterReadyConfig, *, strict: bool = True) -> dict[str, Any]:
    actual = {
        "python_major_minor": ".".join(platform.python_version().split(".")[:2]),
        "python_patch": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "pygam": importlib.metadata.version("pygam"),
        "torch": importlib.metadata.version("torch"),
    }
    if strict:
        expected = config.raw["runtime"]["conventional_scorer"]
        for key in ("python_major_minor", "numpy", "scipy", "scikit_learn", "pygam", "torch"):
            _require(str(actual[key]) == str(expected[key]), f"conventional scorer runtime mismatch: {key}")
    return actual


def record_producer_validation(
    result_path: str | Path,
    config: OuterReadyConfig,
    output: str | Path,
) -> Mapping[str, Any]:
    try:
        result = json.loads(Path(result_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("producer validation result invalid") from exc
    conventional = config.raw["conventional"]
    _require(
        result.get("status") == "pass"
        and result.get("transaction_id") == conventional["transaction_id"]
        and result.get("selected_model_seed_count") == 952
        and result.get("outer_attempted_open_count") == result.get("outer_open_count") == 0,
        "producer validation did not reproduce the frozen publication",
    )
    receipt = {
        "schema_version": "goal037-producer-validation-v1", "success": True,
        "producer_commit": conventional["producer_commit"],
        "validator_commit": conventional["validator_commit"],
        "transaction_id": conventional["transaction_id"],
        "private_core_manifest_sha256": conventional["private_core_manifest_sha256"],
        "result_digest": digest_value(result), "selected_refits": 952,
        "outer_attempted": 0, "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json(output, receipt)
    return receipt


def _load_producer_validation(path: Path, config: OuterReadyConfig) -> Mapping[str, Any]:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("producer validation receipt missing") from exc
    body = dict(receipt)
    claimed = body.pop("receipt_digest", None)
    conventional = config.raw["conventional"]
    _require(_is_digest(claimed) and claimed == digest_value(body), "producer validation receipt digest mismatch")
    _require(
        receipt.get("success") is True and receipt.get("producer_commit") == conventional["producer_commit"]
        and receipt.get("validator_commit") == conventional["validator_commit"]
        and receipt.get("transaction_id") == conventional["transaction_id"]
        and receipt.get("private_core_manifest_sha256") == conventional["private_core_manifest_sha256"]
        and receipt.get("selected_refits") == 952
        and receipt.get("outer_attempted") == receipt.get("outer_opened") == 0,
        "producer validation authority drift",
    )
    return receipt


def export_producer_reference(
    config: OuterReadyConfig,
    copied_root: str | Path,
    output: str | Path,
) -> Mapping[str, Any]:
    """Export exact producer-runtime challenge scores for portable replay."""
    root = Path(copied_root)
    _require(root.is_dir() and not root.is_symlink(), "conventional producer tree missing")
    try:
        selection = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("conventional selection index invalid") from exc
    _require(
        selection.get("selected_model_seed_count") == 952
        and len(selection.get("family_records", [])) == 280,
        "conventional selection arithmetic drift",
    )
    records: list[Mapping[str, Any]] = []
    for index in selection["family_records"]:
        record_path = root / str(index["relative_path"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        for receipt in record.get("refit_receipts", []):
            bundle = root / str(receipt["bundle_path"])
            model_path = bundle / "model.model"
            challenge_record = json.loads(
                (bundle / "challenge.json").read_text(encoding="utf-8")
            )
            _require(
                _sha_file(model_path) == receipt.get("model_sha256")
                and challenge_record.get("challenge_digest")
                == receipt.get("challenge_digest"),
                "producer reference artifact identity drift",
            )
            challenge = challenge_from_payload(challenge_record)
            model = load_fitted_model(model_path, str(receipt["model_sha256"]))
            scores = np.asarray(model.predict_scores(challenge), dtype=np.float64)
            _require(
                scores.ndim == 1
                and 0 < scores.size <= 32
                and np.isfinite(scores).all()
                and np.all((scores >= 0.0) & (scores <= 1.0)),
                "producer reference score invalid",
            )
            prediction_digest = canonical_prediction_bytes_sha256(scores)
            _require(
                prediction_digest
                == receipt.get("canonical_prediction_bytes_sha256"),
                "producer reference semantic replay mismatch",
            )
            records.append(
                {
                    "task": receipt["selected_task"],
                    "model_sha256": receipt["model_sha256"],
                    "challenge_digest": receipt["challenge_digest"],
                    "prediction_digest": prediction_digest,
                    "scores": scores.tolist(),
                }
            )
    _require(
        len(records) == 952
        and len({digest_value(record["task"]) for record in records}) == 952,
        "producer reference task inventory drift",
    )
    runtime = conventional_runtime(config, strict=True)
    expected = config.raw["runtime"]["conventional_producer"]
    _require(
        runtime["python_patch"] == expected["python"]
        and runtime["numpy"] == expected["numpy"]
        and runtime["scipy"] == expected["scipy"]
        and runtime["scikit_learn"] == expected["sklearn"]
        and runtime["pygam"] == expected["pygam"]
        and runtime["torch"] == expected["torch"],
        "producer reference runtime drift",
    )
    reference = {
        "schema_version": "goal037-producer-challenge-reference-v1",
        "config_digest": config.config_digest,
        "source_fingerprint": config.source_fingerprint,
        "producer_commit": config.raw["conventional"]["producer_commit"],
        "validator_commit": config.raw["conventional"]["validator_commit"],
        "transaction_id": config.raw["conventional"]["transaction_id"],
        "selected_refits": 952,
        "runtime": runtime,
        "runtime_digest": digest_value(runtime),
        "records": records,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    reference["receipt_digest"] = digest_value(reference)
    _write_json(output, reference)
    return reference


def _load_producer_reference(
    path: Path,
    config: OuterReadyConfig,
) -> tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    try:
        reference = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("producer challenge reference missing") from exc
    body = dict(reference)
    claimed = body.pop("receipt_digest", None)
    _require(
        _is_digest(claimed) and claimed == digest_value(body),
        "producer challenge reference digest mismatch",
    )
    _require(
        reference.get("schema_version")
        == "goal037-producer-challenge-reference-v1"
        and reference.get("config_digest") == config.config_digest
        and reference.get("source_fingerprint") == config.source_fingerprint
        and reference.get("producer_commit")
        == config.raw["conventional"]["producer_commit"]
        and reference.get("validator_commit")
        == config.raw["conventional"]["validator_commit"]
        and reference.get("transaction_id")
        == config.raw["conventional"]["transaction_id"]
        and reference.get("selected_refits") == 952
        and reference.get("outer_attempted")
        == reference.get("outer_opened")
        == 0,
        "producer challenge reference authority drift",
    )
    records = reference.get("records")
    _require(isinstance(records, list) and len(records) == 952, "producer challenge reference count drift")
    by_task: dict[str, Mapping[str, Any]] = {}
    for record in records:
        _require(
            isinstance(record, Mapping)
            and set(record)
            == {
                "task",
                "model_sha256",
                "challenge_digest",
                "prediction_digest",
                "scores",
            },
            "producer challenge reference record schema drift",
        )
        scores = np.asarray(record["scores"], dtype=np.float64)
        _require(
            _is_digest(record.get("model_sha256"))
            and _is_digest(record.get("challenge_digest"))
            and _is_digest(record.get("prediction_digest"))
            and scores.ndim == 1
            and 0 < scores.size <= 32
            and np.isfinite(scores).all()
            and np.all((scores >= 0.0) & (scores <= 1.0))
            and canonical_prediction_bytes_sha256(scores)
            == record["prediction_digest"],
            "producer challenge reference record invalid",
        )
        key = digest_value(record["task"])
        _require(key not in by_task, "duplicate producer challenge task")
        by_task[key] = record
    return reference, by_task


def validate_conventional_copy(
    config: OuterReadyConfig,
    copied_root: str | Path,
    producer_validation_path: str | Path,
    producer_reference_path: str | Path,
) -> Mapping[str, Any]:
    root = Path(copied_root)
    _require(root.is_dir() and not root.is_symlink(), "conventional copy missing")
    producer = _load_producer_validation(Path(producer_validation_path), config)
    reference, reference_by_task = _load_producer_reference(
        Path(producer_reference_path), config
    )
    runtime = conventional_runtime(config, strict=True)
    try:
        selection = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("conventional selection index invalid") from exc
    _require(selection.get("selected_model_seed_count") == 952 and len(selection.get("family_records", [])) == 280, "conventional selection arithmetic drift")
    expected_strata = [
        {"species_id": species, "fraction_id": fraction, "ladder_id": ladder, "model_family": family}
        for species in SPECIES for fraction, ladder in GOAL029_ENDPOINTS for family in FAMILIES
    ]
    _require([row.get("family_stratum") for row in selection["family_records"]] == expected_strata, "conventional selection order drift")
    tasks: list[Mapping[str, Any]] = []
    model_inventory: list[Mapping[str, Any]] = []
    selected_candidates: dict[str, int] = {}
    expected_files = {"selection.json"}
    exact_byte_replays = 0
    maximum_abs_difference = 0.0
    for index in selection["family_records"]:
        relative = Path(str(index["relative_path"]))
        _require(not relative.is_absolute() and ".." not in relative.parts and relative.parts[0] == "selections", "selection record path invalid")
        record_path = root / relative
        expected_files.add(str(relative))
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OuterReadyError("selection record invalid") from exc
        body = dict(record)
        claimed = body.pop("record_digest", None)
        _require(claimed == index["record_digest"] == digest_value(body), "selection record digest mismatch")
        stratum = record["family_stratum"]
        family = stratum["model_family"]
        selected_candidates[str(record["selected_candidate_id"])] = selected_candidates.get(str(record["selected_candidate_id"]), 0) + 1
        receipts = record.get("refit_receipts")
        _require(isinstance(receipts, list) and len(receipts) == len(SEEDS_BY_FAMILY[family]), "selected refit seed count drift")
        for receipt, seed_label in zip(receipts, SEEDS_BY_FAMILY[family], strict=True):
            task = receipt.get("selected_task")
            expected_task = {
                "species_id": stratum["species_id"], "transform_id": "outer",
                "fraction_id": stratum["fraction_id"], "ladder_id": stratum["ladder_id"],
                "model_family": family, "candidate_id": record["selected_candidate_id"],
                "seed_label": seed_label,
            }
            _require(task == expected_task, "selected refit task mismatch")
            bundle_relative = Path(str(receipt.get("bundle_path", "")))
            _require(not bundle_relative.is_absolute() and len(bundle_relative.parts) == 2 and bundle_relative.parts[0] == "selected" and ".." not in bundle_relative.parts, "selected bundle path invalid")
            bundle = root / bundle_relative
            files = {"model.model", "challenge.json", "receipt.json"}
            _require(bundle.is_dir() and not bundle.is_symlink() and {item.name for item in bundle.iterdir()} == files and not any(item.is_symlink() for item in bundle.iterdir()), "selected bundle inventory drift")
            for filename in files:
                expected_files.add(str(bundle_relative / filename))
            try:
                stored_receipt = json.loads((bundle / "receipt.json").read_text(encoding="utf-8"))
                challenge_record = json.loads((bundle / "challenge.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise OuterReadyError("selected bundle JSON invalid") from exc
            _require(stored_receipt == receipt, "selected bundle receipt mismatch")
            model_path = bundle / "model.model"
            _require(_sha_file(model_path) == receipt.get("model_sha256"), "selected model file digest mismatch")
            challenge = challenge_from_payload(challenge_record)
            _require(challenge_record.get("challenge_digest") == receipt.get("challenge_digest"), "selected challenge digest mismatch")
            model = load_fitted_model(model_path, str(receipt["model_sha256"]))
            scores = np.asarray(model.predict_scores(challenge), dtype=np.float64)
            local_prediction_digest = canonical_prediction_bytes_sha256(scores)
            reference_record = reference_by_task.get(digest_value(task))
            _require(
                reference_record is not None
                and reference_record["task"] == task
                and reference_record["model_sha256"] == receipt["model_sha256"]
                and reference_record["challenge_digest"] == receipt["challenge_digest"]
                and reference_record["prediction_digest"]
                == receipt.get("canonical_prediction_bytes_sha256"),
                "selected challenge reference identity mismatch",
            )
            producer_scores = np.asarray(reference_record["scores"], dtype=np.float64)
            difference = _cross_platform_score_difference(scores, producer_scores)
            _require(
                difference <= CROSS_PLATFORM_ATOL,
                "selected challenge cross-platform replay mismatch",
            )
            maximum_abs_difference = max(maximum_abs_difference, difference)
            exact_byte_replays += int(
                local_prediction_digest
                == receipt.get("canonical_prediction_bytes_sha256")
            )
            envelope = json.loads(model_path.read_text(encoding="utf-8"))
            _require(envelope.get("runtime_versions") == config.raw["runtime"]["conventional_producer"], "selected producer runtime drift")
            _require(receipt.get("outer_attempted_open_count") == receipt.get("outer_open_count") == 0, "selected refit outer access")
            tasks.append(task)
            model_inventory.append({
                "task": task, "model_sha256": receipt["model_sha256"],
                "challenge_digest": receipt["challenge_digest"],
                "prediction_digest": receipt["canonical_prediction_bytes_sha256"],
                "local_prediction_digest": local_prediction_digest,
                "bundle_digest": receipt["selected_bundle_digest"],
            })
    _require(len(tasks) == 952 and len({digest_value(task) for task in tasks}) == 952, "selected task inventory drift")
    observed_files = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    _require(observed_files == expected_files and not any(path.is_symlink() for path in root.rglob("*")), "conventional copied tree inventory drift")
    family_counts = {family: sum(task["model_family"] == family for task in tasks) for family in FAMILIES}
    _require(family_counts == {"intercept": 56, "elastic_net": 280, "random_forest": 280, "hist_gradient_boosting": 56, "shallow_ann": 280}, "conventional family arithmetic drift")
    return {
        "schema_version": "goal037-conventional-import-v1", "success": True,
        "config_digest": config.config_digest, "source_fingerprint": config.source_fingerprint,
        "producer_validation_receipt_digest": producer["receipt_digest"],
        "producer_reference_receipt_digest": reference["receipt_digest"],
        "transaction_id": config.raw["conventional"]["transaction_id"],
        "selected_refits": 952, "family_counts": family_counts,
        "selected_candidate_count": len(selected_candidates),
        "task_inventory_digest": digest_value(tasks),
        "model_inventory_digest": digest_value(model_inventory),
        "copied_file_inventory_digest": digest_value(sorted(observed_files)),
        "cross_platform_replay": {
            "absolute_tolerance": CROSS_PLATFORM_ATOL,
            "equivalent_replays": 952,
            "exact_byte_replays": exact_byte_replays,
            "maximum_absolute_difference": maximum_abs_difference,
        },
        "runtime": runtime, "runtime_digest": digest_value(runtime),
        "outer_attempted": 0, "outer_opened": 0,
    }


def finalize_conventional_copy(
    config: OuterReadyConfig,
    copied_root: str | Path,
    producer_validation_path: str | Path,
    producer_reference_path: str | Path,
    output: str | Path,
) -> Mapping[str, Any]:
    receipt = dict(
        validate_conventional_copy(
            config,
            copied_root,
            producer_validation_path,
            producer_reference_path,
        )
    )
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json(output, receipt)
    return receipt


def validate_conventional_receipt(
    config: OuterReadyConfig,
    copied_root: str | Path,
    producer_validation_path: str | Path,
    producer_reference_path: str | Path,
    receipt_path: str | Path,
) -> Mapping[str, Any]:
    expected = dict(
        validate_conventional_copy(
            config,
            copied_root,
            producer_validation_path,
            producer_reference_path,
        )
    )
    expected["receipt_digest"] = digest_value(expected)
    try:
        actual = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("conventional import receipt invalid") from exc
    _require(actual == expected, "conventional import receipt mismatch")
    return actual


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.conventional_refit_import")
    parser.add_argument("--config", default="config/dsdm_outer_ready.json")
    parser.add_argument("--copied-root")
    parser.add_argument("--producer-validation")
    parser.add_argument("--producer-reference")
    parser.add_argument("--result")
    parser.add_argument("--output")
    parser.add_argument(
        "command",
        choices=(
            "record-producer-validation",
            "export-producer-reference",
            "validate-copy",
            "finalize",
            "validate",
        ),
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.command == "record-producer-validation":
        _require(bool(args.result and args.output), "record command paths required")
        value = record_producer_validation(args.result, config, args.output)
    elif args.command == "export-producer-reference":
        _require(bool(args.copied_root and args.output), "producer reference paths required")
        value = export_producer_reference(config, args.copied_root, args.output)
    else:
        _require(
            bool(
                args.copied_root
                and args.producer_validation
                and args.producer_reference
            ),
            "copy validation paths required",
        )
        if args.command == "validate-copy":
            value = validate_conventional_copy(
                config,
                args.copied_root,
                args.producer_validation,
                args.producer_reference,
            )
        elif args.command == "finalize":
            _require(bool(args.output), "finalize output required")
            value = finalize_conventional_copy(
                config,
                args.copied_root,
                args.producer_validation,
                args.producer_reference,
                args.output,
            )
        else:
            _require(bool(args.output), "validate receipt path required")
            value = validate_conventional_receipt(
                config,
                args.copied_root,
                args.producer_validation,
                args.producer_reference,
                args.output,
            )
    print(canonical(value).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "conventional_runtime", "export_producer_reference",
    "finalize_conventional_copy", "main",
    "record_producer_validation", "validate_conventional_copy",
    "validate_conventional_receipt",
]
