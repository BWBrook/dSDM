"""Nectar execution evidence for unchanged Goal051 scientific code and checkpoints.

The frozen canary's numerical probe is repeated here using its original helpers;
only host/scheduling/provenance plumbing differs. This module is deliberately
outside the frozen SOURCE_PATHS and has a separate execution identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import platform
import re
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from threadpoolctl import threadpool_limits

from . import goal051_seawfb_conventional as science
from .goal051_seawfb_conventional import (
    CANONICAL_CANDIDATES, SeawfbStore, _fit_predict, _peak_rss_bytes,
    _seed_namespace, fit_q_linear, standardized_q, require, _atomic_json,
)

CONFIG_PATH = Path("config/goal051_nectar_execution.json")
SOURCE_PATH = Path("src/dsdm_phase1/goal051_nectar_execution.py")


def execution_context(root: Path):
    plan = science._read_json(root / CONFIG_PATH)
    require(plan.get("schema_version") == "goal051-nectar-execution-plan-v1", "nectar_plan_schema_invalid")
    require(plan.get("workers") == 16 and plan.get("serial_repeats") == 2, "nectar_schedule_invalid")
    identity = science._identity(root)
    require(identity == plan["scientific_identity"], "nectar_scientific_identity_drift")
    previous = plan["previous_route"]
    previous_path = root / previous["path"]
    require(science.sha256_file(previous_path) == previous["sha256"], "nectar_previous_route_drift")
    old_route = science._read_json(previous_path)
    require(old_route.get("identity") == identity and old_route.get("status") == "metric_free_route_selected", "nectar_previous_route_invalid")
    execution = {
        "config_sha256": science.sha256_file(root / CONFIG_PATH),
        "source_sha256": science.sha256_file(root / SOURCE_PATH),
        "scientific_identity": identity,
    }
    return plan, execution


def actual_host():
    instance_path = Path("/sys/class/dmi/id/product_uuid")
    require(instance_path.is_file(), "nectar_instance_identity_unavailable")
    try:
        instance_id = instance_path.read_text().strip().lower()
    except PermissionError:
        # Some OpenStack guests restrict DMI reads; this is a bounded read only.
        result = subprocess.run(["sudo", "-n", "cat", str(instance_path)],
                                check=True, capture_output=True, text=True, timeout=10)
        instance_id = result.stdout.strip().lower()
    memory = re.search(r"^MemTotal:\s+(\d+) kB$", Path("/proc/meminfo").read_text(), re.MULTILINE)
    require(memory is not None, "nectar_memory_unavailable")
    return {
        "hostname": platform.node(), "system": platform.system(),
        "platform": platform.platform(), "instance_id": instance_id,
        "cpus": os.cpu_count(), "memory_bytes": int(memory[1]) * 1024,
    }


def validate_host(plan, host):
    expected = plan["host"]
    require(all(host.get(key) == expected[key] for key in ("hostname", "system", "instance_id")), "nectar_actual_host_mismatch")
    require(isinstance(host.get("platform"), str) and bool(host["platform"]), "nectar_platform_missing")
    require(isinstance(host.get("cpus"), int) and host["cpus"] >= expected["minimum_cpus"], "nectar_cpu_capacity_insufficient")
    require(isinstance(host.get("memory_bytes"), int) and host["memory_bytes"] >= expected["minimum_memory_bytes"], "nectar_memory_capacity_insufficient")


def expected_tags(plan):
    return [*(f"nectar-serial-{i}" for i in range(1, plan["serial_repeats"] + 1)),
            *(f"nectar-mixed-{i}" for i in range(1, plan["workers"] + 1))]


def receipt_path(root, plan, tag):
    require(tag in expected_tags(plan), "nectar_receipt_tag_invalid")
    return root / plan["private_root"] / f"receipt-{tag}.json"


def _probe(root: Path, receipt_tag: str) -> dict[str, Any]:
    """Run a family-representative engineering probe without computing metrics."""

    start_epoch_ns = time.time_ns()
    wall_started = time.perf_counter()
    plan, execution = execution_context(root)
    host = actual_host()
    validate_host(plan, host)
    path = receipt_path(root, plan, receipt_tag)
    host_key, run_mode, run_index = receipt_tag.split("-")
    run_index = int(run_index)
    config = science._config(root)
    science.validate_inputs(root)
    store = SeawfbStore(root)
    spec = config["execution"]["canary"]
    target = spec["target"]
    fold = int(str(spec["held_fold"]).replace("fold", ""))
    fraction = int(spec["target_fraction"])
    train_rows = store.target_rows(target, fold, fraction, "train")
    validation_rows = store.target_rows(target, fold, 100, "validation")
    train = store.batch(target, train_rows, fold)
    validation_batch = store.batch(target, validation_rows, fold)
    entries = []
    for candidate_id in spec["candidate_ids"]:
        family = CANONICAL_CANDIDATES[candidate_id]["family"]
        started = time.perf_counter()
        scores, fit = _fit_predict(config, target, fraction, fold, family, candidate_id, "seed00", train_rows, train, validation_batch)
        entries.append(
            {
                "family": family,
                "candidate_id": candidate_id,
                "runtime_seconds": time.perf_counter() - started,
                "physical_fits": fit["physical_fits"],
                "process_peak_rss_bytes": _peak_rss_bytes(),
                "converged": fit["converged"],
                "best_epoch": fit["best_epoch"],
                "prediction_count": len(scores),
                "finite": bool(np.isfinite(scores).all()),
                "prediction_range": [float(np.min(scores)), float(np.max(scores))],
                "prediction_digest": hashlib.sha256(scores.tobytes()).hexdigest(),
            }
        )
    block = int(store.crossfit["focal_blocks"][target])
    require(spec["focal_block"] == f"block{block}", "canary_focal_block_drift")
    auxiliary_sizes = [str(value) for value in spec["auxiliary_sizes"]]
    require(auxiliary_sizes == ["20", "full"], "canary_auxiliary_inventory_drift")
    q_entries = []
    for auxiliary in auxiliary_sizes:
        q_started = time.perf_counter()
        q_model, q_fit = fit_q_linear(
            store,
            block,
            fold,
            auxiliary,
            seed_namespace=_seed_namespace(config, "q"),
            numerical_fit=config["community_control"]["numerical_fit"],
        )
        train_q, validation_q, scale = standardized_q(q_model, store, fold, train_rows, validation_rows)
        q_train = store.batch(target, train_rows, fold, train_q)
        q_validation = store.batch(target, validation_rows, fold, validation_q)
        q_scores, q_downstream = _fit_predict(
            config,
            target,
            fraction,
            fold,
            spec["q_augmented_family"],
            "hgb04",
            "seed00",
            train_rows,
            q_train,
            q_validation,
        )
        q_entries.append(
            {
                "auxiliary_size": auxiliary,
                "runtime_seconds": time.perf_counter() - q_started,
                "process_peak_rss_bytes": _peak_rss_bytes(),
                "expanded_rows": q_fit["expanded_rows"],
                "collapsed_rows": q_fit["collapsed_rows"],
                "head_count": q_fit["head_count"],
                "iterations": q_fit["iterations"],
                "converged": True,
                "attempts": q_fit["attempts"],
                "accepted_attempt": q_fit["accepted_attempt"],
                "k": q_fit["k"],
                "canonical_C": q_fit["canonical_C"],
                "solver_C": q_fit["solver_C"],
                "representation": q_fit["representation"],
                "parameter_digest": q_fit["parameter_digest"],
                "standardization": scale,
                "downstream_family": spec["q_augmented_family"],
                "downstream_candidate_id": "hgb04",
                "prediction_count": len(q_scores),
                "finite": bool(np.isfinite(q_scores).all()),
                "prediction_range": [float(np.min(q_scores)), float(np.max(q_scores))],
                "prediction_digest": hashlib.sha256(q_scores.tobytes()).hexdigest(),
                "downstream_fit": q_downstream,
            }
        )
    resolved_tag = receipt_tag
    end_epoch_ns = time.time_ns()
    receipt = {
        "schema_version": "goal051-nectar-canary-v1",
        "identity": execution["scientific_identity"],
        "execution_identity": execution,
        "host_attestation": host,
        "status": "metric_free_complete",
        "host": platform.node(),
        "system": platform.system(),
        "platform": platform.platform(),
        "target": target,
        "held_fold": fold,
        "focal_block": block,
        "receipt_tag": resolved_tag,
        "host_key": host_key,
        "run_mode": run_mode,
        "run_index": run_index,
        "receipt_path": str(path.relative_to(root)),
        "start_epoch_ns": start_epoch_ns,
        "end_epoch_ns": end_epoch_ns,
        "total_wall_seconds": time.perf_counter() - wall_started,
        "metrics_computed": False,
        "entries": entries,
        "q_linear": q_entries,
        "process_peak_rss_bytes": _peak_rss_bytes(),
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }
    require(spec["metrics_allowed"] is False, "canary_metrics_enabled")
    _atomic_json(path, receipt)
    return receipt



def probe(root: Path, tag: str):
    with threadpool_limits(limits=1):
        return _probe(root, tag)


def _process(root: str, tag: str):
    return probe(Path(root), tag)["receipt_tag"]


def canary_batch(root: Path):
    plan, _ = execution_context(root)
    validate_host(plan, actual_host())
    science.validate_inputs(root)
    tags = expected_tags(plan)
    for tag in tags[:plan["serial_repeats"]]:
        probe(root, tag)
    mixed = tags[plan["serial_repeats"]:]
    with ProcessPoolExecutor(max_workers=plan["workers"], mp_context=multiprocessing.get_context("spawn")) as pool:
        completed = list(pool.map(_process, [str(root)] * len(mixed), mixed))
    require(completed == mixed, "nectar_mixed_inventory_incomplete")
    return canary_summary(root)


def _positive(value):
    return type(value) in (int, float) and np.isfinite(value) and value > 0


def _prediction(item):
    bounds = item.get("prediction_range")
    require(isinstance(bounds, list) and len(bounds) == 2 and all(type(v) in (int, float) for v in bounds), "nectar_prediction_range_invalid")
    require(item.get("finite") is True and item.get("converged") is True
            and type(item.get("prediction_count")) is int and item["prediction_count"] > 0
            and np.isfinite(bounds).all() and 0 <= bounds[0] <= bounds[1] <= 1
            and re.fullmatch(r"[0-9a-f]{64}", str(item.get("prediction_digest", ""))), "nectar_fit_invalid")


def _no_metrics(value):
    if isinstance(value, dict):
        require(not any(key in {"metrics", "scores", "predictions", "coordinates"} for key in value), "nectar_metric_payload_forbidden")
        for item in value.values():
            _no_metrics(item)
    elif isinstance(value, list):
        for item in value:
            _no_metrics(item)


def summarize(root: Path):
    """Validate raw evidence, deriving the summary rather than trusting flags."""
    plan, execution = execution_context(root)
    spec = science._config(root)["execution"]["canary"]
    numerical_fit = science._config(root)["community_control"]["numerical_fit"]
    receipts, checksums = [], {}
    for tag in expected_tags(plan):
        path = receipt_path(root, plan, tag)
        require(path.is_file(), f"nectar_receipt_missing:{tag}")
        value = science._read_json(path)
        _no_metrics(value)
        require(value.get("schema_version") == "goal051-nectar-canary-v1"
                and value.get("status") == "metric_free_complete"
                and value.get("identity") == execution["scientific_identity"]
                and value.get("execution_identity") == execution, "nectar_receipt_provenance_drift")
        host = value.get("host_attestation", {})
        validate_host(plan, host)
        require(value.get("host") == host["hostname"] and value.get("system") == host["system"]
                and value.get("platform") == host["platform"], "nectar_host_receipt_drift")
        _, mode, index = tag.split("-")
        require(value.get("receipt_tag") == tag and value.get("receipt_path") == str(path.relative_to(root))
                and value.get("host_key") == "nectar" and value.get("run_mode") == mode
                and value.get("run_index") == int(index), "nectar_run_identity_drift")
        require(value.get("target") == spec["target"]
                and value.get("held_fold") == int(spec["held_fold"].replace("fold", ""))
                and value.get("focal_block") == int(spec["focal_block"].replace("block", "")), "nectar_endpoint_drift")
        require(value.get("metrics_computed") is False and value.get("outer_response_rows_read") == 0
                and value.get("outer_predictor_rows_used") == 0, "nectar_firewall_drift")
        require(type(value.get("start_epoch_ns")) is int and type(value.get("end_epoch_ns")) is int
                and value["end_epoch_ns"] > value["start_epoch_ns"] and _positive(value.get("total_wall_seconds"))
                and type(value.get("process_peak_rss_bytes")) is int and value["process_peak_rss_bytes"] > 0, "nectar_timing_or_memory_invalid")
        require(abs(value["total_wall_seconds"] - (value["end_epoch_ns"] - value["start_epoch_ns"]) / 1e9) <= 1,
                "nectar_wall_interval_mismatch")
        require([item.get("candidate_id") for item in value.get("entries", [])] == spec["candidate_ids"], "nectar_candidate_inventory_drift")
        require([item.get("auxiliary_size") for item in value.get("q_linear", [])] == [str(v) for v in spec["auxiliary_sizes"]], "nectar_q_inventory_drift")
        for item in value["entries"]:
            _prediction(item)
            require(item.get("family") == CANONICAL_CANDIDATES[item["candidate_id"]]["family"], "nectar_family_drift")
        for item in value["q_linear"]:
            _prediction(item)
            science._validate_q_attempts(item, numerical_fit)
            science._validate_q_weight_rescaling(item)
            require(item.get("downstream_family") == spec["q_augmented_family"]
                    and item.get("downstream_candidate_id") == "hgb04"
                    and item.get("downstream_fit", {}).get("converged") is True
                    and all(type(item.get(key)) is int and item[key] > 0 for key in ("expanded_rows", "collapsed_rows", "head_count"))
                    and re.fullmatch(r"[0-9a-f]{64}", str(item.get("parameter_digest", ""))), "nectar_q_fit_invalid")
        receipts.append(value)
        checksums[str(path.relative_to(root))] = science.sha256_file(path)
    serial = [v for v in receipts if v["run_mode"] == "serial"]
    mixed = [v for v in receipts if v["run_mode"] == "mixed"]
    require(serial[0]["end_epoch_ns"] <= serial[1]["start_epoch_ns"]
            and serial[-1]["end_epoch_ns"] <= min(v["start_epoch_ns"] for v in mixed), "nectar_serial_schedule_invalid")
    peak = science._interval_peak([(v["start_epoch_ns"], v["end_epoch_ns"]) for v in mixed])
    require(peak == plan["workers"], "nectar_concurrency_not_proven")
    hosts = {json.dumps(v["host_attestation"], sort_keys=True) for v in receipts}
    require(len(hosts) == 1, "nectar_host_inventory_inconsistent")
    digests, parameters = {}, {}
    for value in receipts:
        for item in value["entries"]:
            digests.setdefault(item["candidate_id"], set()).add(item["prediction_digest"])
        for item in value["q_linear"]:
            digests.setdefault("q:" + item["auxiliary_size"], set()).add(item["prediction_digest"])
            parameters.setdefault(item["auxiliary_size"], set()).add(item["parameter_digest"])
    require(all(len(v) == 1 for v in digests.values()), "nectar_prediction_digest_instability")
    require(all(len(v) == 1 for v in parameters.values()), "nectar_q_parameter_digest_instability")
    elapsed = (max(v["end_epoch_ns"] for v in mixed) - min(v["start_epoch_ns"] for v in mixed)) / 1e9
    return {"schema_version": "goal051-nectar-summary-v1", "status": "metric_free_host_inventory_complete",
            "identity": execution["scientific_identity"], "execution_identity": execution,
            "host_attestation": receipts[0]["host_attestation"], "receipt_sha256": checksums,
            "receipt_count": len(receipts), "serial_latency_seconds": [v["total_wall_seconds"] for v in serial],
            "mixed_batch": {"runs": len(mixed), "configured_concurrency": plan["workers"], "interval_peak_concurrency": peak,
                            "elapsed_seconds": elapsed, "throughput_runs_per_second": len(mixed) / elapsed},
            "peak_rss_bytes": max(v["process_peak_rss_bytes"] for v in receipts),
            "prediction_digests": {k: next(iter(v)) for k, v in sorted(digests.items())},
            "q_parameter_digests": {k: next(iter(v)) for k, v in sorted(parameters.items())},
            "metrics_computed": False, "outer_response_rows_read": 0, "outer_predictor_rows_used": 0}


def canary_summary(root: Path):
    result = summarize(root)
    plan, _ = execution_context(root)
    _atomic_json(root / plan["private_root"] / "summary.json", result)
    return result


def expected_route(root: Path, workers: int):
    plan, execution = execution_context(root)
    require(type(workers) is int and 0 < workers <= plan["workers"], "nectar_route_workers_invalid")
    summary = summarize(root)
    path = root / plan["private_root"] / "summary.json"
    require(path.is_file() and science._read_json(path) == summary, "nectar_summary_missing_or_stale")
    return {"schema_version": "goal051-nectar-route-v1", "status": "metric_free_route_selected",
            "identity": execution["scientific_identity"], "execution_identity": execution,
            "selected_host": "nectar", "selected_workers": workers, "proven_mixed_concurrency": plan["workers"],
            "host_attestation": summary["host_attestation"], "host_plan": plan["host"],
            "summary": {"path": str(path.relative_to(root)), "sha256": science.sha256_file(path)},
            "previous_route": plan["previous_route"], "reason": plan["reason"],
            "metrics_computed": False, "outer_response_rows_read": 0, "outer_predictor_rows_used": 0}


def select_route(root: Path, workers: int):
    result = expected_route(root, workers)
    plan, _ = execution_context(root)
    _atomic_json(root / plan["route_path"], result)
    return result


def gate(root: Path, workers: int):
    plan, _ = execution_context(root)
    host = actual_host()
    validate_host(plan, host)
    expected = expected_route(root, workers)
    path = root / plan["route_path"]
    require(path.is_file() and science._read_json(path) == expected, "nectar_route_missing_or_stale")
    require(host == expected["host_attestation"], "nectar_live_host_drift")
    return {"status": "nectar_production_gate_passed", "workers": workers, "host": host["hostname"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("canary-batch", "canary-summary", "route", "gate"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "canary-batch":
        result = canary_batch(root)
    elif args.command == "canary-summary":
        result = canary_summary(root)
    elif args.command == "route":
        result = select_route(root, args.workers)
    else:
        result = gate(root, args.workers)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
