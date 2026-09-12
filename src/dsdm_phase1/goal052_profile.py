"""Metric-free full-row, one-epoch engineering profile for Goal 052."""

from __future__ import annotations

import gc
import json
from pathlib import Path
import time
from typing import Any

import torch


PROFILE_PATH = Path("metadata/goal052_full_epoch_profile.json")


def profile(root: Path, device: str) -> dict[str, Any]:
    """Run one full-row pretraining lifecycle and four target arm lifecycles.

    This profile is an engineering measurement only.  It writes a metadata
    receipt and does not create resumable production leaves.
    """
    # Deliberately import the orchestrator only after module import so the
    # profile remains importable while the runner imports its training stack.
    from . import goal052_seawfb_dsdm as runner

    root = Path(root).resolve()
    validated = runner.validate_inputs(root)
    identity = validated["identity"]
    config = runner.config_at(root)
    canary_path = root / config["execution"]["canary_receipt"]
    canary = runner.read_json(canary_path)
    runner.require(canary.get("status") == "goal052_canary_valid", "profile_canary_status_invalid")
    runner.require(canary.get("identity") == identity, "profile_canary_identity_drift")
    runtime = runner.host_runtime(device)
    runner.require(canary.get("runtime") == runtime, "profile_canary_runtime_drift")
    runner.require(all(name in canary for name in ("block", "fold", "target")), "profile_canary_selection_missing")
    block, fold, target = int(canary["block"]), int(canary["fold"]), str(canary["target"])

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    store = runner.SeawfbStore(root)
    data = runner.auxiliary_data(store, block, fold, "full")
    full_auxiliary_rows = {role: int(len(rows.y)) for role, rows in zip(
        ("discovery", "stopping", "replay"), (data.discovery, data.stopping, data.replay)
    )}
    options = runner.fit_options(config, device)
    options.update(max_epochs=1, patience=1)
    spec = runner.spec_for(config, "seawfb_scale")
    pre_seed = runner.stable_seed("goal052-profile-pretraining-v1", block, fold)
    print(json.dumps({"stage": "goal052_full_epoch_profile", "event": "pretraining_started", "block": block, "fold": fold, "target": target}), flush=True)
    pre_started = time.monotonic()
    state, pre_fit = runner.fit_pretraining_lifecycle(
        spec, data.discovery, data.stopping, data.replay, data.heads,
        seed=pre_seed, **options,
    )
    pre_runtime = time.monotonic() - pre_started
    print(json.dumps({"stage": "goal052_full_epoch_profile", "event": "pretraining_finished", "runtime_seconds": pre_runtime}), flush=True)
    runner.require(pre_fit.get("selected_epoch") == 1, "profile_pretraining_epoch_invalid")
    runner.require(pre_fit.get("state_finite") is True, "profile_pretraining_nonfinite")
    pre_processed = sum(full_auxiliary_rows.values())

    # The full auxiliary object may be very large.  Its shared state is the
    # only object needed by transferred target arms.
    del data
    gc.collect()

    q_loaded = runner.baseline._load_q(
        root, runner.baseline._config(root), identity["goal051_identity"], block, fold, "full"
    )
    runner.require(q_loaded is not None, "profile_q_missing")
    q_model, q_receipt = q_loaded
    q_digest = runner.digest(q_receipt)
    q_model_sha256 = q_receipt.get("model_sha256")

    target_rows: dict[str, int] | None = None
    held_prediction_rows: int | None = None
    target_fits: dict[str, dict[str, Any]] = {}
    prediction_digests: dict[str, str] = {}
    target_runtimes: dict[str, float] = {}
    transferred_digests: dict[str, str | None] = {}
    target_processed = 0
    for arm in runner.ARMS:
        print(json.dumps({"stage": "goal052_full_epoch_profile", "event": "target_started", "arm": arm}), flush=True)
        target_data = runner.target_data(store, target, fold, 100, q_model if arm == runner.ARMS[1] else None)
        if target_rows is None:
            target_rows = {role: int(len(rows.y)) for role, rows in zip(
                ("discovery", "stopping", "replay"),
                (target_data.discovery, target_data.stopping, target_data.replay),
            )}
            held_prediction_rows = min(1024, len(target_data.held_x))
        else:
            runner.require(
                target_rows == {role: int(len(rows.y)) for role, rows in zip(
                    ("discovery", "stopping", "replay"),
                    (target_data.discovery, target_data.stopping, target_data.replay),
                )},
                "profile_target_row_count_drift",
            )
        numeric_seed = runner.target_seed(target, 100, fold, "seawfb_scale", "seed00")
        transferred = state if arm in runner.ARMS[2:] else None
        transferred_digests[arm] = None if transferred is None else runner.state_digest(transferred)
        fit_started = time.monotonic()
        scores, fit = runner.fit_target_lifecycle(
            spec, target_data.discovery, target_data.stopping, target_data.replay,
            target_data.held_x[:1024], seed=numeric_seed, transferred_state=transferred,
            freeze_trunk=arm == runner.ARMS[2], **options,
        )
        target_runtimes[arm] = time.monotonic() - fit_started
        print(json.dumps({"stage": "goal052_full_epoch_profile", "event": "target_finished", "arm": arm, "runtime_seconds": target_runtimes[arm]}), flush=True)
        runner.require(fit.get("selected_epoch") == 1, "profile_target_epoch_invalid")
        runner.require(fit.get("state_finite") is True, "profile_target_nonfinite")
        target_fits[arm] = fit
        prediction_digests[arm] = runner.digest(scores.tolist())
        target_processed += sum(target_rows.values())
        del target_data, scores
        gc.collect()
    runner.require(target_rows is not None, "profile_target_data_missing")

    total_processed = pre_processed + target_processed
    elapsed = time.monotonic() - started
    receipt = {
        "status": "goal052_full_epoch_profile_valid",
        "identity": identity,
        "runtime": runtime,
        "device": device,
        "block": block,
        "fold": fold,
        "target": target,
        "architecture": "seawfb_scale",
        "auxiliary": "full",
        "seed_label": "seed00",
        "pretraining_seed": int(pre_seed),
        "target_seed": int(runner.target_seed(target, 100, fold, "seawfb_scale", "seed00")),
        "epoch_count": 1,
        "full_auxiliary_rows": full_auxiliary_rows,
        "target_rows": target_rows,
        "held_prediction_rows": held_prediction_rows,
        "pretraining_processed_rows": int(pre_processed),
        "target_processed_rows_by_arm": {arm: int(sum(target_rows.values())) for arm in runner.ARMS},
        "processed_rows_total": int(total_processed),
        "rows_per_second": float(total_processed / max(elapsed, 1e-12)),
        "pretraining_runtime_seconds": float(pre_runtime),
        "pretraining_rows_per_second": float(pre_processed / max(pre_runtime, 1e-12)),
        "target_runtime_seconds": target_runtimes,
        "lifecycle_runtime_seconds": float(elapsed),
        "peak_rss_bytes": int(runner.baseline._peak_rss_bytes()),
        "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated()) if device == "cuda" else None,
        "pretraining_fit": pre_fit,
        "target_fits": target_fits,
        "selected_epochs": {"pretraining": 1, **{arm: 1 for arm in runner.ARMS}},
        "prediction_digests": prediction_digests,
        "transferred_state_digests": transferred_digests,
        "q_receipt_digest": q_digest,
        "q_model_sha256": q_model_sha256,
        "ecological_metrics_computed": False,
        "outer_response_rows_read": 0,
    }
    runner.atomic_json(root / PROFILE_PATH, receipt)
    print(json.dumps({"stage": "goal052_full_epoch_profile", "event": "profile_finished", "runtime_seconds": elapsed}), flush=True)
    return receipt


__all__ = ["PROFILE_PATH", "profile"]
