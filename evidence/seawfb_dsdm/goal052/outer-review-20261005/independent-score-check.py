#!/usr/bin/env python3
"""Independent, prospective spot-check of three Goal052 outer-score targets.

The selected targets were fixed before outer scores were inspected: the first,
middle, and last lexicographic members of the frozen 73-species primary panel.
The production scorer is deliberately not imported.  This script reconstructs
labels and focal-excluded richness from canonical rows, implements tie-aware
ROC AUC and threshold metrics locally, and compares them with the returned
score receipt.  Outcome files are not opened until a successful, return-only
reconciliation receipt binds the preserved attempt-005 controller failure and
all relevant file hashes have been verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.parquet as pq


RUN_RELATIVE = Path(
    "data/processed/dsdm/goal052-seawfb-dsdm-experiment/"
    "outer-assessment-20261003-r2"
)
CONTROL_NAME = "postproduction-control-005"
REGIONS = ("NCP", "SEH", "NNC")
EXISTING_ARMS = (
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
    "selected_conventional",
    "selected_conventional_plus_q",
)
ALL_ARMS = (*EXISTING_ARMS, "fixed_ensemble")
SELECTED_TARGETS = (
    "Acanthagenys rufogularis",
    "Heteroscenes pallidus",
    "Zosterops lateralis",
)
PRIMARY_COUNT = 73
TARGET_COUNT = 157
DOMAIN_ROWS = 144_860
CANONICAL_ROWS = 5_048_061
SERIALIZED_SPECIES = 449
REGISTERED_SPECIES = 505
EMPTY_SPECIES = 56
X10_RICHNESS = 10
X20_RICHNESS = 20
MIN_PRESENCES = 30
MIN_BACKGROUNDS = 100
MIN_TILES = 4
FLOAT_TOLERANCE = 1e-12

EXPECTED_HELPER_SHA256 = "16bc4c2405a62222a6fcf190a861ad9ad45065e75cbf50d57a4cb7ec16abf328"
EXPECTED_LAUNCHER_SHA256 = "ba0f4970335417926459c2320ddd85a2f6ad0e8731170432726922edafc1c4d9"
EXPECTED_FINISHER_SHA256 = "e0acd85d5d7050c2a7a1e25609674f2ccfbd9e57b064fd486609f4e7616a3362"
EXPECTED_BINDING_SHA256 = "c9519e0e34c15f563f419d06a643bee55605791aa38253c59edb243d6d258015"
EXPECTED_ATTEMPT005_MANIFEST_SHA256 = "a5bfa5d9ff02b96d6430828844751dd8519c7c9715c3e6d17580c8bf1b84ab1a"
EXPECTED_PROOF_SHA256 = "8e21478e8e7fd312b47a1827606771c0c3b2bf9e0f37d311072d0bc10ea65fea"
EXPECTED_CERTIFICATE_SHA256 = "acbce53636cd4e5c02a02781e2265d87cb2f0a09fded7ecdbafde41fca84e8b2"
EXPECTED_PRIOR_ACCESS_SHA256 = "1d89233916fe9d9ef81a235723fe1aa8f952c9f293a092246dc508f290ee0829"
EXPECTED_FAILED_COMPLETE_SHA256 = "bb2e4c50c07e86476edd747fc0999ce455e0ac98a65450645576b371d8433f77"
EXPECTED_FAILED_REASON = "report exited without a completion receipt"
RECONCILIATION_MODE = "return_only"
EXPECTED_STAGE_PIDS = {"score": 597547, "report": 609488}
EXPECTED_STAGE_SHA256 = {
    "score": "65ee80a967cf805a0bfae8d62cf61679333008f243408e21c50f8c2cd9e50f3e",
    "report": "892f7dab94e10e02d130c06b5db501934e8492022eeedc23df78e9567018f134",
}
EXPECTED_RETURN_SOURCE_SHA256 = "c31cb96e7608096ab990da35ccc439beb8f8f421cf0c19dc4d0397f4870aae3c"


class SpotCheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SpotCheckError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file(), f"missing file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_array(values: np.ndarray, dtype: str) -> str:
    raw = np.ascontiguousarray(values, dtype=dtype).tobytes(order="C")
    return hashlib.sha256(raw).hexdigest()


def string_digest(values: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def object_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SpotCheckError(f"invalid JSON for {label}: {path}") from error
    require(isinstance(value, dict), f"JSON object required for {label}")
    return value


def read_hashed_json(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    require(sha256_file(path) == expected_sha256, f"{label} hash mismatch")
    return read_json(path, label)


def safe_file(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"{label} path missing")
    item = Path(relative)
    require(not item.is_absolute() and ".." not in item.parts, f"unsafe {label} path")
    path = (root / item).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), f"{label} missing")
    return path


def immutable_json(path: Path, value: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise SpotCheckError(f"spot-check output already exists: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)
    return sha256_file(path)


def rank_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    """Mann-Whitney ROC AUC using average ranks for exact score ties."""
    y = np.asarray(labels, dtype=np.int8)
    values = np.asarray(scores, dtype=np.float64)
    require(y.ndim == values.ndim == 1 and len(y) == len(values), "AUC vector mismatch")
    require(np.isin(y, (0, 1)).all() and np.isfinite(values).all(), "invalid AUC values")
    positive = int(np.sum(y == 1))
    negative = int(np.sum(y == 0))
    if not positive or not negative:
        return None
    order = np.argsort(values, kind="mergesort")
    ordered = values[order]
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(ordered):
        stop = start + 1
        while stop < len(ordered) and ordered[stop] == ordered[start]:
            stop += 1
        ranks[order[start:stop]] = 0.5 * ((start + 1) + stop)
        start = stop
    rank_sum = float(np.sum(ranks[y == 1]))
    u = rank_sum - positive * (positive + 1) / 2.0
    return float(u / (positive * negative))


def average_precision(labels: np.ndarray, scores: np.ndarray) -> float | None:
    """Non-interpolated average precision with tied scores updated as groups."""
    y = np.asarray(labels, dtype=np.int8)
    values = np.asarray(scores, dtype=np.float64)
    positive = int(np.sum(y == 1))
    if not positive:
        return None
    order = np.argsort(-values, kind="mergesort")
    ordered_scores = values[order]
    ordered_y = y[order]
    tp = 0
    fp = 0
    previous_recall = 0.0
    result = 0.0
    start = 0
    while start < len(ordered_scores):
        stop = start + 1
        while stop < len(ordered_scores) and ordered_scores[stop] == ordered_scores[start]:
            stop += 1
        group = ordered_y[start:stop]
        tp += int(np.sum(group == 1))
        fp += int(np.sum(group == 0))
        recall = tp / positive
        precision = tp / (tp + fp)
        result += (recall - previous_recall) * precision
        previous_recall = recall
        start = stop
    return float(result)


def threshold_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    y = np.asarray(labels, dtype=np.int8)
    values = np.asarray(scores, dtype=np.float64)
    require(y.ndim == values.ndim == 1 and len(y) == len(values) > 0, "metric vector mismatch")
    require(np.isin(y, (0, 1)).all(), "non-binary labels")
    require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "invalid scores")
    require(math.isfinite(float(threshold)) and 0 <= threshold <= 1, "invalid threshold")
    predicted = values >= threshold
    positive = y == 1
    negative = y == 0
    tp = int(np.sum(predicted & positive))
    fn = int(np.sum(~predicted & positive))
    tn = int(np.sum(~predicted & negative))
    fp = int(np.sum(predicted & negative))
    n = len(y)
    n_positive = tp + fn
    n_negative = tn + fp
    both = n_positive > 0 and n_negative > 0
    sensitivity = float(tp / n_positive) if n_positive else None
    specificity = float(tn / n_negative) if n_negative else None
    auc = rank_auc(y, values)
    ap = average_precision(y, values)
    denominator = math.sqrt(
        (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    )
    mcc = float((tp * tn - fp * fn) / denominator) if both and denominator else (0.0 if both else None)
    observed = (tp + tn) / n
    expected = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    kappa = (
        1.0 if expected == 1 and observed == 1
        else 0.0 if expected == 1
        else float((observed - expected) / (1 - expected))
    ) if both else None
    return {
        "n": int(n),
        "n_positive": int(n_positive),
        "n_negative": int(n_negative),
        "prevalence": float(n_positive / n),
        "roc_auc": auc,
        "auc": auc,
        "average_precision": ap,
        "pr_auc": ap,
        "tss": float(sensitivity + specificity - 1.0) if both else None,
        "balanced_accuracy": float((sensitivity + specificity) / 2.0) if both else None,
        "mcc": mcc,
        "kappa": kappa,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "threshold": float(threshold),
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
        "na_reason": None if both else "single_response_class",
    }


def null_metric(n: int, positive: int, negative: int, threshold: float, reason: str) -> dict[str, Any]:
    return {
        "n": int(n), "n_positive": int(positive), "n_negative": int(negative),
        "prevalence": float(positive / n) if n else None,
        "roc_auc": None, "auc": None, "average_precision": None, "pr_auc": None,
        "tss": None, "balanced_accuracy": None, "mcc": None, "kappa": None,
        "sensitivity": None, "specificity": None, "threshold": float(threshold),
        "tp": None, "fn": None, "tn": None, "fp": None, "na_reason": reason,
    }


def auc_metric(labels: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    positive = int(np.sum(labels == 1))
    negative = int(np.sum(labels == 0))
    auc = rank_auc(labels, scores)
    return {
        "n": int(len(labels)), "n_positive": positive, "n_negative": negative,
        "roc_auc": auc, "auc": auc,
        "na_reason": None if auc is not None else "single_response_class",
    }


def support(labels: np.ndarray, blocks: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    presence = mask & (labels == 1)
    background = mask & (labels == 0)
    n_presence = int(np.sum(presence))
    n_background = int(np.sum(background))
    presence_tiles = len(set(map(tuple, blocks[presence].tolist())))
    background_tiles = len(set(map(tuple, blocks[background].tolist())))
    failures: list[str] = []
    if n_presence < MIN_PRESENCES:
        failures.append("fewer_than_30_presences")
    if n_background < MIN_BACKGROUNDS:
        failures.append("fewer_than_100_backgrounds")
    if presence_tiles < MIN_TILES:
        failures.append("fewer_than_4_anchored_50km_presence_tiles")
    if background_tiles < MIN_TILES:
        failures.append("fewer_than_4_anchored_50km_background_tiles")
    return {
        "passes": not failures,
        "presence_cells": n_presence,
        "background_cells": n_background,
        "presence_tiles": presence_tiles,
        "background_tiles": background_tiles,
        "minimums": {
            "presence_cells": MIN_PRESENCES,
            "background_cells": MIN_BACKGROUNDS,
            "distinct_anchored_50km_tiles_per_class": MIN_TILES,
        },
        "failure_reasons": failures,
    }


def independent_metrics(
    labels: np.ndarray,
    richness: np.ndarray,
    blocks: np.ndarray,
    arm_scores: Mapping[str, np.ndarray],
    thresholds: Mapping[str, float],
) -> dict[str, Any]:
    require(set(arm_scores) == set(ALL_ARMS), "prediction arm inventory mismatch")
    require(set(thresholds) == set(EXISTING_ARMS), "threshold inventory mismatch")
    masks = {
        "x10": (labels == 1) | ((labels == 0) & (richness >= X10_RICHNESS)),
        "x20": (labels == 1) | ((labels == 0) & (richness >= X20_RICHNESS)),
    }
    result: dict[str, Any] = {}
    for name, mask in masks.items():
        selected_y = labels[mask]
        item_support = support(labels, blocks, mask)
        metrics: dict[str, Any] = {}
        for arm in EXISTING_ARMS:
            if not len(selected_y):
                metrics[arm] = null_metric(0, 0, 0, thresholds[arm], "empty_mask")
            else:
                metrics[arm] = threshold_metrics(selected_y, arm_scores[arm][mask], thresholds[arm])
        metrics["fixed_ensemble"] = auc_metric(selected_y, arm_scores["fixed_ensemble"][mask])
        if name == "x20" and not item_support["passes"]:
            n = int(np.sum(mask))
            positive = int(np.sum(mask & (labels == 1)))
            negative = int(np.sum(mask & (labels == 0)))
            metrics = {
                arm: null_metric(n, positive, negative, thresholds[arm], "x20_support_failure")
                for arm in EXISTING_ARMS
            } | {
                "fixed_ensemble": {
                    **auc_metric(selected_y, arm_scores["fixed_ensemble"][mask]),
                    "roc_auc": None, "auc": None, "na_reason": "x20_support_failure",
                }
            }
        result[name] = {
            "cells": int(np.sum(mask)),
            "presence_cells": int(np.sum(mask & (labels == 1))),
            "background_cells": int(np.sum(mask & (labels == 0))),
            "support": item_support,
            "metrics": metrics,
        }
    return result


def compare_value(actual: Any, expected: Any, label: str) -> float:
    if expected is None or actual is None:
        require(actual is expected, f"{label} null mismatch: {actual!r} != {expected!r}")
        return 0.0
    if isinstance(expected, bool) or isinstance(actual, bool):
        require(actual is expected, f"{label} boolean mismatch")
        return 0.0
    if isinstance(expected, (int, np.integer)) and isinstance(actual, (int, np.integer)):
        require(int(actual) == int(expected), f"{label} integer mismatch")
        return 0.0
    if isinstance(expected, (float, np.floating)) or isinstance(actual, (float, np.floating)):
        left, right = float(actual), float(expected)
        require(math.isfinite(left) and math.isfinite(right), f"{label} nonfinite")
        difference = abs(left - right)
        require(difference <= FLOAT_TOLERANCE, f"{label} differs by {difference}")
        return difference
    require(actual == expected, f"{label} mismatch: {actual!r} != {expected!r}")
    return 0.0


def compare_metric(actual: Mapping[str, Any], expected: Mapping[str, Any], label: str) -> float:
    require(set(actual) == set(expected), f"{label} field inventory mismatch")
    maximum = 0.0
    for field in expected:
        maximum = max(maximum, compare_value(actual[field], expected[field], f"{label}.{field}"))
    return maximum


def returned_hash(returned: Mapping[str, Any], relative: str, expected: str) -> None:
    files = returned.get("files", {})
    remote = returned.get("remote_sha256", {})
    require(files.get(relative) == expected, f"returned local hash mismatch: {relative}")
    require(remote.get(relative) == expected, f"returned remote hash mismatch: {relative}")


def gate_and_load_metadata(root: Path, run: Path, control: Path) -> dict[str, Any]:
    """Verify the completion and every outcome-file hash before parsing outcomes."""
    root, run, control = root.resolve(), run.resolve(), control.resolve()
    require(run == (root / RUN_RELATIVE).resolve(), "unexpected run path")
    require(control == (run / CONTROL_NAME).resolve(), "unexpected control path")
    failed_complete_path = control / "complete.json"
    failed_complete = read_hashed_json(
        failed_complete_path, EXPECTED_FAILED_COMPLETE_SHA256, "original failed attempt-005 completion"
    )
    require(
        failed_complete.get("status") == "failed"
        and failed_complete.get("success") is False
        and failed_complete.get("error_type") == "ControllerError"
        and failed_complete.get("reason") == EXPECTED_FAILED_REASON,
        "original attempt-005 failure identity mismatch",
    )
    require(
        failed_complete.get("recovery_failure_evidence", {}).get("verified_files", {}).get("score/stage.json")
        == "65ee80a967cf805a0bfae8d62cf61679333008f243408e21c50f8c2cd9e50f3e",
        "preserved failure does not bind the successful score-stage receipt",
    )
    complete_path = control / "return-complete-006.json"
    complete = read_json(complete_path, "return-only reconciliation completion")
    require(
        complete.get("schema_version") == "goal052-outer-postproduction-completion-v1"
        and complete.get("status") == "complete"
        and complete.get("success") is True,
        "return-only reconciliation is not successfully complete",
    )
    require(
        complete.get("reconciled_failure_sha256") == EXPECTED_FAILED_COMPLETE_SHA256
        and complete.get("reconciled_failure_reason") == EXPECTED_FAILED_REASON
        and complete.get("reconciliation_mode") == RECONCILIATION_MODE
        and complete.get("original_attempt005_manifest_sha256") == EXPECTED_ATTEMPT005_MANIFEST_SHA256
        and complete.get("return_source_sha256") == EXPECTED_RETURN_SOURCE_SHA256
        and complete.get("scientific_recomputation") is False
        and complete.get("report_regenerated") is False,
        "return-only reconciliation does not bind the preserved failure",
    )
    require(
        sha256_file(control / "return-source-006.py") == EXPECTED_RETURN_SOURCE_SHA256,
        "return-only reconciliation source drift",
    )
    for stage_name in ("score", "report"):
        stage = complete.get(f"{stage_name}_stage", {})
        require(
            stage.get("status") == "complete"
            and stage.get("stage") == stage_name
            and stage.get("return_code") == 0
            and stage.get("remote_status_sha256") == EXPECTED_STAGE_SHA256[stage_name],
            f"reconciled {stage_name} stage did not complete successfully",
        )
        require(stage.get("pid") == EXPECTED_STAGE_PIDS[stage_name], f"reconciled {stage_name} PID mismatch")
        stage_receipt = read_hashed_json(
            control / f"remote-postproduction/{stage_name}/stage.json",
            EXPECTED_STAGE_SHA256[stage_name],
            f"returned {stage_name} stage receipt",
        )
        require(
            stage_receipt == {
                "status": "complete", "stage": stage_name,
                "pid": EXPECTED_STAGE_PIDS[stage_name], "return_code": 0,
            },
            f"returned {stage_name} stage receipt identity mismatch",
        )
    require(complete.get("original_response_access_preserved") is True, "prior access was not preserved")
    require(not (run / "scoring-failure.json").exists(), "scoring-failure receipt exists")

    manifest = read_hashed_json(
        control / "manifest.json", EXPECTED_ATTEMPT005_MANIFEST_SHA256, "attempt-005 manifest"
    )
    require(
        manifest.get("schema_version") == "goal052-score-recovery-launch-v1"
        and manifest.get("recovery_attempt") == "005",
        "attempt-005 manifest identity mismatch",
    )
    require(manifest.get("recovery_helper_sha256") == EXPECTED_HELPER_SHA256, "helper hash drift")
    require(sha256_file(control / "recovery-source.py") == EXPECTED_HELPER_SHA256, "staged helper drift")
    require(sha256_file(control / "launch-source.py") == EXPECTED_LAUNCHER_SHA256, "launcher drift")
    require(sha256_file(control / "finish-source.py") == EXPECTED_FINISHER_SHA256, "finisher drift")
    validation = read_hashed_json(
        control / "validation.json", manifest.get("validation_sha256", ""), "entrypoint validation"
    )
    require(
        validation.get("status") == "pass"
        and validation.get("independent_review", {}).get("verdict") == "supported"
        and validation.get("runtime_binding_validation_sha256") == EXPECTED_BINDING_SHA256,
        "entrypoint validation gate mismatch",
    )
    require(
        sha256_file(control / "runtime-binding-validation.json") == EXPECTED_BINDING_SHA256,
        "runtime-binding receipt drift",
    )

    plan_path = run / "plan.json"
    closure_path = run / "closure.json"
    scores_path = run / "scores.json"
    success_path = run / "response-access-success.json"
    returned_path = run / "returned-files.json"
    require(sha256_file(plan_path) == complete.get("plan_sha256") == manifest.get("plan_sha256"), "plan hash mismatch")
    require(sha256_file(closure_path) == complete.get("closure_sha256") == manifest.get("closure_sha256"), "closure hash mismatch")
    require(sha256_file(scores_path) == complete.get("scores_sha256"), "scores hash mismatch")
    require(sha256_file(success_path) == complete.get("native_access_success_sha256"), "response-success hash mismatch")
    require(sha256_file(run / "response-access.json") == complete.get("native_access_started_sha256") == EXPECTED_PRIOR_ACCESS_SHA256, "response-start hash mismatch")
    require(sha256_file(returned_path) == complete.get("returned_manifest_sha256"), "returned manifest hash mismatch")
    require(sha256_file(run / "outer-report.md") == complete.get("report_sha256"), "report hash mismatch")

    # Plan, closure, and transfer manifests are response-free metadata.  Parse
    # them now to locate the sealed files, but delay scores/access-success
    # parsing until the canonical and selected prediction hashes also pass.
    plan = read_json(plan_path, "plan")
    closure = read_json(closure_path, "closure")
    returned = read_json(returned_path, "returned files")
    require(returned.get("schema_version") == "goal052-returned-files-v2", "returned manifest schema mismatch")
    returned_hash(returned, "scores.json", complete["scores_sha256"])
    returned_hash(returned, "response-access-success.json", complete["native_access_success_sha256"])
    returned_hash(returned, "closure.json", complete["closure_sha256"])
    returned_hash(returned, "plan.json", complete["plan_sha256"])

    identity = {key: value for key, value in plan.items() if key not in ("plan_digest", "created_utc")}
    require(plan.get("plan_digest") == object_digest(identity), "plan digest mismatch")
    closure_identity = {key: value for key, value in closure.items() if key != "closure_digest"}
    require(closure.get("closure_digest") == object_digest(closure_identity), "closure digest mismatch")
    require(
        closure.get("schema_version") == "goal052-outer-closure-v1"
        and closure.get("status") == "predictions_closed_before_response"
        and closure.get("outer_response_rows_read") == 0
        and closure.get("plan_digest") == plan.get("plan_digest")
        and closure.get("thresholds") == plan.get("thresholds"),
        "closure identity mismatch",
    )
    for relative, expected in plan.get("sources", {}).items():
        require(sha256_file(safe_file(root, relative, "frozen source")) == expected, f"frozen source drift: {relative}")

    primary = sorted(map(str, plan.get("panels", {}).get("primary", ())))
    require(len(primary) == PRIMARY_COUNT and len(set(primary)) == PRIMARY_COUNT, "primary panel drift")
    prospective = (primary[0], primary[len(primary) // 2], primary[-1])
    require(prospective == SELECTED_TARGETS, "prospective target selection drift")
    require(len(plan.get("targets", ())) == TARGET_COUNT, "target inventory drift")
    require(set(closure.get("predictions", {})) == set(plan["targets"]), "prediction inventory drift")

    recovery_success_path = control / "remote-postproduction/recovery/response-access-recovery-success.json"
    recovery_success = read_hashed_json(
        recovery_success_path, complete.get("recovery_success_sha256", ""), "recovery success"
    )
    require(
        recovery_success.get("status") == "scoring_complete"
        and recovery_success.get("scores_sha256") == complete.get("scores_sha256")
        and recovery_success.get("native_access_success_sha256") == complete.get("native_access_success_sha256"),
        "recovery success binding mismatch",
    )
    recovery_provenance = recovery_success.get("recovery_provenance", {})
    require(
        recovery_provenance.get("recovery_helper_sha256") == EXPECTED_HELPER_SHA256
        and recovery_provenance.get("inventory_proof_sha256") == EXPECTED_PROOF_SHA256
        and recovery_provenance.get("inventory_certificate_sha256") == EXPECTED_CERTIFICATE_SHA256
        and recovery_provenance.get("prior_access_sha256") == EXPECTED_PRIOR_ACCESS_SHA256,
        "recovery provenance mismatch",
    )
    require(
        complete.get("recovery_helper_sha256") == EXPECTED_HELPER_SHA256
        and complete.get("inventory_proof_sha256") == EXPECTED_PROOF_SHA256
        and complete.get("inventory_certificate_sha256") == EXPECTED_CERTIFICATE_SHA256,
        "completion recovery provenance mismatch",
    )

    proof = read_hashed_json(control / "inventory-proof.json", EXPECTED_PROOF_SHA256, "inventory proof")
    certificate = read_hashed_json(control / "inventory-certificate.json", EXPECTED_CERTIFICATE_SHA256, "inventory certificate")
    require(
        proof.get("active_species") == REGISTERED_SPECIES
        and proof.get("effort_donors") == REGISTERED_SPECIES
        and proof.get("nonempty_species") == SERIALIZED_SPECIES
        and proof.get("empty_species") == EMPTY_SPECIES
        and proof.get("canonical_memberships") == CANONICAL_ROWS,
        "inventory proof count mismatch",
    )
    require(certificate.get("canonical_sha256") == proof.get("canonical_sha256"), "proof/certificate canonical mismatch")
    active = set(map(str, proof.get("active_names", ())))
    donors = set(map(str, proof.get("effort_donor_names", ())))
    nonempty = set(map(str, proof.get("nonempty_names", ())))
    empty = set(map(str, proof.get("empty_names", ())))
    require(len(nonempty) == SERIALIZED_SPECIES and len(empty) == EMPTY_SPECIES, "proof identity count mismatch")
    require(
        len(active) == REGISTERED_SPECIES
        and donors == active == nonempty | empty
        and not nonempty & empty,
        "active/donor/nonempty/empty partition mismatch",
    )
    require(set(SELECTED_TARGETS) <= nonempty and not set(SELECTED_TARGETS) & empty, "selected target inventory invalid")

    response_metadata = manifest.get("response_metadata", {})
    require(
        certificate.get("metadata_files", {}).get("completion", {}).get("sha256")
        == response_metadata.get("completion_sha256"),
        "Goal049 completion binding mismatch",
    )
    canonical_path = safe_file(root, response_metadata.get("response_relative", ""), "canonical response")
    canonical_hash = response_metadata.get("response_sha256")
    require(canonical_hash == proof.get("canonical_sha256"), "manifest canonical hash mismatch")
    require(canonical_path.stat().st_size == response_metadata.get("response_size"), "canonical size mismatch")
    require(sha256_file(canonical_path) == canonical_hash, "canonical hash mismatch")

    domain_path = run / "domain.npz"
    domain_hash = sha256_file(domain_path)
    require(
        domain_hash == plan.get("domain_file_sha256") == closure.get("files", {}).get("domain.npz"),
        "domain hash mismatch",
    )
    returned_hash(returned, "domain.npz", domain_hash)

    prediction_paths: dict[str, Path] = {}
    for target in SELECTED_TARGETS:
        relative = closure["predictions"].get(target)
        path = safe_file(run, relative, f"prediction for {target}")
        expected = closure.get("files", {}).get(relative)
        require(isinstance(expected, str) and sha256_file(path) == expected, f"prediction hash mismatch: {target}")
        returned_hash(returned, relative, expected)
        prediction_paths[target] = path

    # All plan, closure, scores, response-success, domain, canonical, and
    # selected-prediction hashes have now passed.  Outcome summaries may be
    # parsed; raw prediction and canonical arrays remain unopened until later.
    scores = read_json(scores_path, "scores")
    access_success = read_json(success_path, "response success")

    require(
        scores.get("schema_version") == "goal052-outer-scores-v1"
        and scores.get("plan_digest") == plan.get("plan_digest")
        and scores.get("closure_sha256") == complete.get("closure_sha256")
        and scores.get("recovery_provenance") == recovery_provenance,
        "scores identity mismatch",
    )
    provenance = scores.get("response_provenance", {})
    require(
        provenance.get("canonical_species_cells_sha256") == canonical_hash
        and provenance.get("canonical_membership_rows") == CANONICAL_ROWS
        and provenance.get("serialized_nonempty_species_count") == SERIALIZED_SPECIES
        and provenance.get("registered_active_species_count") == REGISTERED_SPECIES
        and provenance.get("registered_effort_donor_count") == REGISTERED_SPECIES
        and provenance.get("target_count") == TARGET_COUNT,
        "score response provenance mismatch",
    )
    require(
        access_success.get("status") == "response_access_complete"
        and access_success.get("access_started_sha256") == EXPECTED_PRIOR_ACCESS_SHA256
        and access_success.get("canonical_species_cells_sha256") == canonical_hash
        and access_success.get("canonical_membership_rows") == CANONICAL_ROWS
        and access_success.get("canonical_species_count") == SERIALIZED_SPECIES
        and access_success.get("target_count") == TARGET_COUNT,
        "response-success provenance mismatch",
    )
    target_digest = string_digest(sorted(map(str, plan["targets"])))
    require(
        access_success.get("target_inventory_sha256") == target_digest
        and provenance.get("target_inventory_sha256") == target_digest,
        "target inventory digest mismatch",
    )

    expected_pairs = {(target, region) for target in plan["targets"] for region in REGIONS}
    score_inventory: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in scores.get("targets", ()):
        require(isinstance(item, Mapping), "invalid score target item")
        key = (str(item.get("target")), str(item.get("region")))
        require(key not in score_inventory, f"duplicate score item: {key}")
        score_inventory[key] = item
    require(set(score_inventory) == expected_pairs, "score target-region inventory mismatch")

    return {
        "root": root, "run": run, "control": control,
        "complete": complete, "manifest": manifest, "plan": plan, "closure": closure,
        "scores": scores, "score_inventory": score_inventory, "access_success": access_success,
        "proof": proof, "certificate": certificate, "nonempty": nonempty, "canonical_path": canonical_path,
        "canonical_hash": canonical_hash, "domain_path": domain_path,
        "prediction_paths": prediction_paths, "returned": returned,
        "completion_sha256": sha256_file(complete_path),
        "failed_completion_sha256": sha256_file(failed_complete_path),
    }


def load_domain(metadata: Mapping[str, Any]) -> dict[str, Any]:
    plan = metadata["plan"]
    with np.load(metadata["domain_path"], allow_pickle=False) as payload:
        required = {"cell_ids", "regions", "block_x", "block_y"}
        require(required <= set(payload.files), "domain array inventory missing")
        cell_ids = np.asarray(payload["cell_ids"], dtype=str)
        regions = np.asarray(payload["regions"], dtype=str)
        block_x = np.asarray(payload["block_x"])
        block_y = np.asarray(payload["block_y"])
    require(
        all(value.ndim == 1 and len(value) == DOMAIN_ROWS for value in (cell_ids, regions, block_x, block_y)),
        "domain vector shape mismatch",
    )
    require(len(set(cell_ids.tolist())) == DOMAIN_ROWS, "duplicate domain cell id")
    require(set(regions.tolist()) == set(REGIONS), "domain region inventory mismatch")
    require(
        np.issubdtype(block_x.dtype, np.number)
        and np.issubdtype(block_y.dtype, np.number)
        and np.isfinite(block_x).all()
        and np.isfinite(block_y).all(),
        "domain spatial block values invalid",
    )
    summary = plan.get("domain", {})
    require(summary.get("rows") == DOMAIN_ROWS, "domain row-count metadata mismatch")
    require(string_digest(cell_ids.tolist()) == summary.get("cell_id_sha256"), "domain cell-id digest mismatch")
    require(string_digest(regions.tolist()) == summary.get("region_sha256"), "domain region digest mismatch")
    observed_rows = {region: int(np.sum(regions == region)) for region in REGIONS}
    require(observed_rows == summary.get("rows_by_region"), "domain regional counts mismatch")
    blocks = np.column_stack((block_x, block_y))
    return {"cell_ids": cell_ids, "regions": regions, "blocks": blocks}


def reconstruct_response(metadata: Mapping[str, Any], domain: Mapping[str, Any]) -> dict[str, Any]:
    cell_ids = domain["cell_ids"]
    cell_index = {cell: index for index, cell in enumerate(cell_ids.tolist())}
    richness = np.zeros(len(cell_ids), dtype=np.int32)
    presence = {target: np.zeros(len(cell_ids), dtype=bool) for target in SELECTED_TARGETS}
    parquet = pq.ParquetFile(metadata["canonical_path"])
    require(list(parquet.schema_arrow.names) == ["species", "cell_id"], "canonical schema mismatch")
    previous: tuple[str, str] | None = None
    species_seen: list[str] = []
    row_count = 0
    for batch in parquet.iter_batches(columns=["species", "cell_id"], batch_size=131_072):
        species_values = batch.column(0).to_pylist()
        cell_values = batch.column(1).to_pylist()
        for species_value, cell_value in zip(species_values, cell_values, strict=True):
            species, cell = str(species_value), str(cell_value)
            current = (species, cell)
            require(previous is None or current > previous, "canonical duplicate/order drift")
            previous = current
            if not species_seen or species_seen[-1] != species:
                species_seen.append(species)
            index = cell_index.get(cell)
            if index is not None:
                richness[index] += 1
                if species in presence:
                    presence[species][index] = True
            row_count += 1
    require(row_count == CANONICAL_ROWS, "canonical row-count mismatch")
    require(len(species_seen) == SERIALIZED_SPECIES, "serialized species count mismatch")
    require(set(species_seen) == metadata["nonempty"], "serialized species identity mismatch")
    species_identity_sha256 = hashlib.sha256(
        json.dumps(species_seen, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    require(
        species_identity_sha256 == metadata["certificate"].get("identity_digests", {}).get("nonempty"),
        "serialized species identity digest mismatch",
    )
    require(np.all(richness >= 0), "negative reconstructed richness")

    target_rows: dict[str, Any] = {}
    target_receipts: dict[str, Any] = {}
    success_targets = metadata["access_success"].get("targets", {})
    for target in SELECTED_TARGETS:
        y = presence[target].astype(np.int8)
        focal = richness - presence[target].astype(np.int32)
        require(np.all(focal >= 0), f"negative focal-excluded richness: {target}")
        require(np.array_equal(focal[y == 0], richness[y == 0]), f"background richness changed: {target}")
        receipt = success_targets.get(target, {})
        require(receipt.get("presence_cells") == int(y.sum()), f"presence count differs: {target}")
        require(receipt.get("y_sha256") == sha256_array(y, "<i1"), f"y digest differs: {target}")
        require(
            receipt.get("richness_minus_f_sha256") == sha256_array(focal, "<i4"),
            f"focal-richness digest differs: {target}",
        )
        target_rows[target] = {"y": y, "richness_minus_f": focal}
        target_receipts[target] = {
            "presence_cells": int(y.sum()),
            "y_sha256": sha256_array(y, "<i1"),
            "richness_minus_f_sha256": sha256_array(focal, "<i4"),
        }
    return {
        "targets": target_rows,
        "target_receipts": target_receipts,
        "row_count": row_count,
        "species_count": len(species_seen),
        "species_identity_sha256": species_identity_sha256,
    }


def load_prediction(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        require(set(payload.files) == set(ALL_ARMS), "prediction arm inventory mismatch")
        values = {arm: np.asarray(payload[arm]) for arm in ALL_ARMS}
    for arm, value in values.items():
        require(value.shape == (DOMAIN_ROWS,) and value.dtype == np.float64, f"prediction shape/dtype: {arm}")
        require(np.isfinite(value).all() and np.all((value >= 0) & (value <= 1)), f"prediction range: {arm}")
    expected_ensemble = 0.5 * values["multihead_full_finetune"] + 0.5 * values["selected_conventional"]
    require(np.array_equal(values["fixed_ensemble"], expected_ensemble), "fixed ensemble mismatch")
    return values


def run_spotcheck(root: Path, run: Path, control: Path) -> dict[str, Any]:
    metadata = gate_and_load_metadata(root, run, control)
    domain = load_domain(metadata)
    require(
        metadata["access_success"].get("domain_cell_ids_sha256") == string_digest(domain["cell_ids"].tolist()),
        "response-success domain digest mismatch",
    )
    response = reconstruct_response(metadata, domain)
    checks: dict[str, Any] = {}
    comparison_count = 0
    maximum_difference = 0.0
    for target in SELECTED_TARGETS:
        predictions = load_prediction(metadata["prediction_paths"][target])
        thresholds = metadata["plan"]["thresholds"][target]
        require(set(thresholds) == set(EXISTING_ARMS), f"threshold inventory mismatch: {target}")
        checks[target] = {}
        y = response["targets"][target]["y"]
        richness = response["targets"][target]["richness_minus_f"]
        for region in REGIONS:
            region_mask = domain["regions"] == region
            expected = independent_metrics(
                y[region_mask], richness[region_mask], domain["blocks"][region_mask],
                {arm: values[region_mask] for arm, values in predictions.items()}, thresholds,
            )
            actual = metadata["score_inventory"][(target, region)]
            require(actual.get("panel") == {"primary": True, "regional": True}, f"panel flags differ: {target}/{region}")
            require(actual.get("thresholds") == thresholds, f"reported thresholds differ: {target}/{region}")
            region_result: dict[str, Any] = {}
            for mask_name in ("x10", "x20"):
                expected_mask = expected[mask_name]
                actual_mask = actual.get("masks", {}).get(mask_name, {})
                require(actual_mask.get("cells") == expected_mask["cells"], f"mask cells differ: {target}/{region}/{mask_name}")
                require(actual_mask.get("presence_cells") == expected_mask["presence_cells"], f"mask presences differ: {target}/{region}/{mask_name}")
                require(actual_mask.get("background_cells") == expected_mask["background_cells"], f"mask backgrounds differ: {target}/{region}/{mask_name}")
                require(actual_mask.get("support") == expected_mask["support"], f"mask support differs: {target}/{region}/{mask_name}")
                require(actual.get("support", {}).get(mask_name) == expected_mask["support"], f"support alias differs: {target}/{region}/{mask_name}")
                if mask_name == "x10":
                    require(expected_mask["support"]["passes"] is True, f"selected primary x10 support fails: {target}/{region}")
                else:
                    expected_membership = target in metadata["plan"]["x20_targets"][region]
                    require(expected_mask["support"]["passes"] is expected_membership, f"x20 membership differs: {target}/{region}")
                metric_result: dict[str, Any] = {}
                actual_metrics = actual.get(mask_name, {}).get("metrics", {})
                require(set(actual_metrics) == set(ALL_ARMS), f"reported arm inventory differs: {target}/{region}/{mask_name}")
                for arm in ALL_ARMS:
                    difference = compare_metric(
                        actual_metrics[arm], expected_mask["metrics"][arm],
                        f"{target}/{region}/{mask_name}/{arm}",
                    )
                    maximum_difference = max(maximum_difference, difference)
                    comparison_count += len(expected_mask["metrics"][arm])
                    metric_result[arm] = {
                        "roc_auc": expected_mask["metrics"][arm]["roc_auc"],
                        "threshold": expected_mask["metrics"][arm].get("threshold"),
                        "tss": expected_mask["metrics"][arm].get("tss"),
                        "balanced_accuracy": expected_mask["metrics"][arm].get("balanced_accuracy"),
                        "mcc": expected_mask["metrics"][arm].get("mcc"),
                    }
                region_result[mask_name] = {
                    "cells": expected_mask["cells"],
                    "presence_cells": expected_mask["presence_cells"],
                    "background_cells": expected_mask["background_cells"],
                    "support": expected_mask["support"],
                    "metrics": metric_result,
                }
            checks[target][region] = region_result
    return {
        "schema_version": "goal052-independent-score-spotcheck-v1",
        "status": "pass",
        "selection_rule": "first_middle_last_lexicographic_target_in_frozen_primary73",
        "selected_targets": list(SELECTED_TARGETS),
        "regions": list(REGIONS),
        "arms": list(ALL_ARMS),
        "masks": ["x10", "x20"],
        "method": {
            "response": "independent canonical-row reconstruction of y and focal-excluded donor richness",
            "roc_auc": "Mann-Whitney positive-rank statistic with average ranks for exact ties",
            "threshold_rule": "score_greater_than_or_equal_to_frozen_inner_oof_threshold",
            "support": {"minimum_presences": MIN_PRESENCES, "minimum_backgrounds": MIN_BACKGROUNDS, "minimum_tiles_per_class": MIN_TILES},
            "production_scorer_imported": False,
            "aggregate_contrasts_recomputed": False,
        },
        "provenance": {
            "return_complete_006_sha256": metadata["completion_sha256"],
            "preserved_failed_complete_sha256": metadata["failed_completion_sha256"],
            "reconciled_failure_reason": EXPECTED_FAILED_REASON,
            "reconciliation_mode": RECONCILIATION_MODE,
            "original_attempt005_manifest_sha256": EXPECTED_ATTEMPT005_MANIFEST_SHA256,
            "score_stage_receipt_sha256": metadata["complete"]["score_stage"]["remote_status_sha256"],
            "report_stage_receipt_sha256": metadata["complete"]["report_stage"]["remote_status_sha256"],
            "plan_sha256": metadata["complete"]["plan_sha256"],
            "closure_sha256": metadata["complete"]["closure_sha256"],
            "scores_sha256": metadata["complete"]["scores_sha256"],
            "canonical_sha256": metadata["canonical_hash"],
            "helper_sha256": EXPECTED_HELPER_SHA256,
            "launcher_sha256": EXPECTED_LAUNCHER_SHA256,
            "finisher_sha256": EXPECTED_FINISHER_SHA256,
            "runtime_binding_validation_sha256": EXPECTED_BINDING_SHA256,
            "spotcheck_script_sha256": sha256_file(Path(__file__).resolve()),
        },
        "reconstruction": {
            "canonical_membership_rows": response["row_count"],
            "serialized_species": response["species_count"],
            "species_identity_sha256": response["species_identity_sha256"],
            "domain_rows": DOMAIN_ROWS,
            "selected_target_receipts": response["target_receipts"],
        },
        "comparison": {
            "field_comparisons": comparison_count,
            "float_tolerance": FLOAT_TOLERANCE,
            "maximum_absolute_difference": maximum_difference,
            "all_selected_metrics_match": True,
        },
        "checks": checks,
        "residual_scope": "Three prospectively selected primary targets only; aggregate contrasts checked separately.",
    }


def self_test() -> None:
    labels = np.asarray([0, 1, 0, 1, 0, 1], dtype=np.int8)
    scores = np.asarray([0.1, 0.8, 0.8, 0.5, 0.5, 0.8], dtype=np.float64)
    require(abs(rank_auc(labels, scores) - 13 / 18) <= 1e-15, "rank AUC self-test failed")
    require(abs(average_precision(labels, scores) - 29 / 45) <= 1e-15, "AP self-test failed")
    metrics = threshold_metrics(labels, scores, 0.6)
    require((metrics["tp"], metrics["fn"], metrics["tn"], metrics["fp"]) == (2, 1, 2, 1), "confusion self-test failed")
    for name in ("tss", "mcc", "kappa"):
        require(abs(metrics[name] - 1 / 3) <= 1e-15, f"{name} self-test failed")
    require(abs(metrics["balanced_accuracy"] - 2 / 3) <= 1e-15, "balanced-accuracy self-test failed")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/Users/bwbrook/papers/dSDM"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--control", type=Path)
    parser.add_argument(
        "--output", type=Path,
        default=Path("/tmp/dsdm-outer-independent-score-spotcheck-result-20261005.json"),
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    args.run = (args.run or args.root / RUN_RELATIVE).resolve()
    args.control = (args.control or args.run / CONTROL_NAME).resolve()
    args.output = args.output.resolve()
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            self_test()
            print(json.dumps({"status": "self_test_pass"}, sort_keys=True))
            return 0
        result = run_spotcheck(args.root, args.run, args.control)
        digest = immutable_json(args.output, result)
        print(json.dumps({"status": "pass", "output": str(args.output), "sha256": digest}, sort_keys=True))
        return 0
    except (SpotCheckError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Goal052 independent score spot-check failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
