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

from .contracts import ENDPOINTS, SPECIES
from .final_inner_data import canonical, digest_value
from .outer_ready import OuterReadyConfig, OuterReadyError, _is_digest, _sha_file, _write_json, load_config
from dsdm_phase1.goal029_production import challenge_from_payload, canonical_prediction_bytes_sha256
from dsdm_phase1.model_adapters import load_fitted_model


FAMILIES = ("intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann")
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


def validate_conventional_copy(
    config: OuterReadyConfig,
    copied_root: str | Path,
    producer_validation_path: str | Path,
) -> Mapping[str, Any]:
    root = Path(copied_root)
    _require(root.is_dir() and not root.is_symlink(), "conventional copy missing")
    producer = _load_producer_validation(Path(producer_validation_path), config)
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
            scores = model.predict_scores(challenge)
            _require(canonical_prediction_bytes_sha256(scores) == receipt.get("canonical_prediction_bytes_sha256"), "selected challenge semantic replay mismatch")
            envelope = json.loads(model_path.read_text(encoding="utf-8"))
            _require(envelope.get("runtime_versions") == config.raw["runtime"]["conventional_producer"], "selected producer runtime drift")
            _require(receipt.get("outer_attempted_open_count") == receipt.get("outer_open_count") == 0, "selected refit outer access")
            tasks.append(task)
            model_inventory.append({
                "task": task, "model_sha256": receipt["model_sha256"],
                "challenge_digest": receipt["challenge_digest"],
                "prediction_digest": receipt["canonical_prediction_bytes_sha256"],
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
        "transaction_id": config.raw["conventional"]["transaction_id"],
        "selected_refits": 952, "family_counts": family_counts,
        "selected_candidate_count": len(selected_candidates),
        "task_inventory_digest": digest_value(tasks),
        "model_inventory_digest": digest_value(model_inventory),
        "copied_file_inventory_digest": digest_value(sorted(observed_files)),
        "runtime": runtime, "runtime_digest": digest_value(runtime),
        "outer_attempted": 0, "outer_opened": 0,
    }


def finalize_conventional_copy(
    config: OuterReadyConfig,
    copied_root: str | Path,
    producer_validation_path: str | Path,
    output: str | Path,
) -> Mapping[str, Any]:
    receipt = dict(validate_conventional_copy(config, copied_root, producer_validation_path))
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json(output, receipt)
    return receipt


def validate_conventional_receipt(
    config: OuterReadyConfig,
    copied_root: str | Path,
    producer_validation_path: str | Path,
    receipt_path: str | Path,
) -> Mapping[str, Any]:
    expected = dict(validate_conventional_copy(config, copied_root, producer_validation_path))
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
    parser.add_argument("--result")
    parser.add_argument("--output")
    parser.add_argument("command", choices=("record-producer-validation", "validate-copy", "finalize", "validate"))
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.command == "record-producer-validation":
        _require(bool(args.result and args.output), "record command paths required")
        value = record_producer_validation(args.result, config, args.output)
    else:
        _require(bool(args.copied_root and args.producer_validation), "copy validation paths required")
        if args.command == "validate-copy":
            value = validate_conventional_copy(config, args.copied_root, args.producer_validation)
        elif args.command == "finalize":
            _require(bool(args.output), "finalize output required")
            value = finalize_conventional_copy(config, args.copied_root, args.producer_validation, args.output)
        else:
            _require(bool(args.output), "validate receipt path required")
            value = validate_conventional_receipt(config, args.copied_root, args.producer_validation, args.output)
    print(canonical(value).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "conventional_runtime", "finalize_conventional_copy", "main",
    "record_producer_validation", "validate_conventional_copy",
    "validate_conventional_receipt",
]
