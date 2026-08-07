"""Goal032 plan, bounded execution, attestation, and evidence aggregation.

The module is deliberately an orchestration boundary: it never opens the
sealed outer assessment.  Host execution is expected to be staged by the
operator (locally or over SSH); the command records the attestation supplied
by the host and validates it before any fit is started.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Mapping

from .real_data import CaseSpec, bind_case_from_foundation, load_bundle, validate_bundle
from .real_training import architecture_by_id, train_case

CASE_DEFAULTS = {
    "light": ("pseudocheirus_peregrinus", "fold03", "resmlp00"),
    "medium": ("notamacropus_rufogriseus", "fold03", "resmlp12"),
    "heavy": ("sarcophilus_harrisii", "fold01", "resmlp23"),
}
HOSTNAMES = {"mac_cpu": "Barrys-Mac-mini.local", "deep_server_cpu": "deep-server", "alien_cuda": "alienware"}
ARCHITECTURE_SPECS = {
    "resmlp00": {"blocks": 2, "width": 64, "bottleneck": 16, "shape": "constant", "dropout": 0.0, "weight_decay": 0.00001},
    "resmlp12": {"blocks": 3, "width": 128, "bottleneck": 32, "shape": "taper", "dropout": 0.2, "weight_decay": 0.0001},
    "resmlp23": {"blocks": 4, "width": 256, "bottleneck": 64, "shape": "taper", "dropout": 0.0, "weight_decay": 0.001},
}
FORBIDDEN = ("auc", "tss", "mcc", "pr_auc", "loss", "grid_cell_id", "coordinates", "row_id", "outer_assessment_labels", "prediction_values")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def derive_case_seed(base_seed: int, case_id: str, purpose: str = "target") -> int:
    digest = hashlib.sha256(f"goal032|{base_seed}|{case_id}|{purpose}".encode()).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"Goal032 {label} drift")


def load_config(path: str | Path) -> dict[str, Any]:
    source_path = Path(path)
    value = json.loads(source_path.read_text(encoding="utf-8"))
    _require_equal(value.get("schema_version"), "1.0", "schema")
    _require_equal(value.get("goal_id"), "goal032-dsdm-real-compute-calibration", "goal")
    top = {"schema_version", "goal_id", "bindings", "scope", "binding", "features", "training", "cases", "remote_bundle", "hosts", "runtime", "calibration", "evidence", "publication", "stop_before"}
    _require_equal(set(value), top, "config keys")
    _require_equal(tuple(x.get("case_id") for x in value["cases"]), tuple(CASE_DEFAULTS), "case order")
    expected_cases = {
        "light": ("pseudocheirus_peregrinus", "fold03", "fold04", ("fold00", "fold01", "fold02"), "resmlp00"),
        "medium": ("notamacropus_rufogriseus", "fold03", "fold04", ("fold00", "fold01", "fold02"), "resmlp12"),
        "heavy": ("sarcophilus_harrisii", "fold01", "fold02", ("fold00", "fold03", "fold04"), "resmlp23"),
    }
    for row in value["cases"]:
        cid = row.get("case_id")
        if cid not in expected_cases or set(row) != {"case_id", "architecture", "target", "held_fold", "stopping_fold", "discovery_folds"}:
            raise ValueError("Goal032 case schema drift")
        expected = expected_cases[cid]
        _require_equal((row["target"], row["held_fold"], row["stopping_fold"], tuple(row["discovery_folds"]), row["architecture"].get("id")), expected, "case contract")
        arch = row["architecture"]
        if set(arch) != {"id", *ARCHITECTURE_SPECS[expected[-1]]} or {k: arch[k] for k in ARCHITECTURE_SPECS[expected[-1]]} != ARCHITECTURE_SPECS[expected[-1]]:
            raise ValueError("Goal032 architecture specification drift")
    _require_equal(value["scope"].get("outer_training_rows"), 11039, "scope")
    _require_equal(value["features"].get("target_input_columns"), 77, "feature columns")
    # These fields are authority, rather than descriptive metadata.  In
    # particular, publication and runtime controls must not be silently edited.
    _require_equal(value["publication"], {"worker_commit_allowed": False, "worker_push_allowed": False, "orchestrator_may_commit_and_push_after_acceptance_gates": True}, "publication")
    runtime = value["runtime"]
    for key, expected in (("environment", "isolated_goal032_canary_only"), ("python_major_minor", "3.12"), ("numpy_version", "2.2.6"), ("torch_version", "2.7.1"), ("alien_driver_version", "546.01"), ("repository_lock_used_for_canary_runtime", False), ("modify_pyproject_or_uv_lock", False)):
        _require_equal(runtime.get(key), expected, f"runtime.{key}")
    _require_equal(runtime.get("mac_cpu_wheel"), "official_cpu", "runtime.mac_cpu_wheel")
    _require_equal(runtime.get("deep_server_cpu_wheel"), "official_cpu", "runtime.deep_server_cpu_wheel")
    _require_equal(runtime.get("alien_cuda_wheel"), "official_cu118", "runtime.alien_cuda_wheel")
    _require_equal(value["calibration"]["total_logical_evaluations"], 24, "workload")
    _require_equal(value["calibration"]["total_physical_fit_count"], 48, "physical workload")
    _require_equal(value["calibration"]["projection"]["total_logical_evaluations"], 1440, "projection")
    _require_equal(value["calibration"]["projection"]["total_physical_fits"], 2880, "projection fits")
    _require_equal(value["evidence"].get("real_outer_attempted"), 0, "outer attempted")
    _require_equal(value["evidence"].get("real_outer_opened"), 0, "outer opened")
    _require_equal(value["evidence"].get("private_root"), "data/processed/dsdm/goal032-real-compute-calibration/final/private", "private evidence root")
    manifest_keys = ["schema_version", "goal_id", "case_id", "target", "held_fold", "stopping_fold", "architecture_id", "seed", "base_seed", "transform", "input_columns", "array_shapes", "array_digests", "source_binding_digest", "outer_attempted", "outer_opened", "goal032_config_digest", "authority_digests", "auxiliary_aggregate_digest", "bundle_digest"]
    _require_equal(value["remote_bundle"].get("allowed_metadata"), manifest_keys, "bundle manifest allowlist")
    _require_equal(value["calibration"].get("record"), ["wall_seconds", "selected_epoch", "discovery_executed_epochs", "replay_epochs", "peak_rss_bytes", "peak_vram_bytes", "model_digest", "prediction_digest", "runtime_fingerprint", "bundle_digest"], "receipt fields")
    for host in value["hosts"]:
        if host.get("host_id") not in HOSTNAMES or set(host) - {"host_id", "connection", "hostname", "device", "serial_worker_count", "concurrency_worker_cap", "maximum_workers_per_gpu", "ddp"}:
            raise ValueError("Goal032 host registry drift")
        _require_equal(host.get("hostname"), HOSTNAMES[host["host_id"]], "host identity")
        if host["device"] == "cpu":
            _require_equal(host.get("serial_worker_count"), 1, "CPU serial workers")
        else:
            _require_equal(host.get("concurrency_worker_cap"), 2, "Alien workers")
            _require_equal(host.get("maximum_workers_per_gpu"), 1, "Alien workers per GPU")
            _require_equal(host.get("ddp"), False, "Alien DDP")
    # Keep the file-byte authority private to the in-process config object.
    # real_data uses this to validate bundles exported from the exact file;
    # it is never serialised into the tracked receipt.
    value["_source_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return value


def build_plan(config: dict[str, Any]) -> dict[str, Any]:
    cases = tuple(row["case_id"] if isinstance(row, dict) else row for row in config.get("cases", tuple(CASE_DEFAULTS)))
    if set(cases) != set(CASE_DEFAULTS):
        raise ValueError("canary case set drift")
    calibration = config.get("calibration", {})
    return {"schema_version": "goal032-compute-plan-v1", "case_count": len(cases), "cases": list(cases), "base_seed": int(config.get("base_seed", config.get("training", {}).get("base_seed", 31032))), "outer_attempted": 0, "outer_opened": 0, "serial_logical_evaluations": int(calibration.get("serial", {}).get("logical_evaluations", 18)), "concurrency_logical_evaluations": int(calibration.get("concurrency", {}).get("task_count", 6)), "logical_evaluations": int(calibration.get("total_logical_evaluations", 24)), "physical_fits": int(calibration.get("total_physical_fit_count", 48)), "projected_architecture_logical_evaluations": int(calibration.get("projection", {}).get("total_logical_evaluations", 1440)), "projected_architecture_physical_fits": int(calibration.get("projection", {}).get("total_physical_fits", 2880))}


def _memory_snapshot() -> dict[str, int]:
    total = 0
    swap_total = swap_used = 0
    try:
        if sys.platform.startswith("linux"):
            values = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, val = line.split(":", 1); values[key] = int(val.strip().split()[0]) * 1024
            total, swap_total = values.get("MemTotal", 0), values.get("SwapTotal", 0)
            swap_used = max(0, swap_total - values.get("SwapFree", swap_total))
        else:
            total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
            swap = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
            import re
            match = re.search(r"used = ([0-9.]+)([MG])", swap)
            if match: swap_used = int(float(match.group(1)) * (1024**2 if match.group(2) == "M" else 1024**3))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return {"total_ram_bytes": total, "swap_total_bytes": swap_total, "swap_used_bytes": swap_used}


def collect_host_attestation(host_id: str, *, before: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Collect a bounded, de-identified host/runtime witness."""
    import numpy as np
    import torch
    memory = _memory_snapshot()
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    cuda_runtime = str(torch.version.cuda or "none")
    gpu_count = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
    vram = 0
    if gpu_count:
        vram = sum(int(torch.cuda.get_device_properties(i).total_memory) for i in range(gpu_count))
    driver = None
    if gpu_count:
        candidates = [shutil.which("nvidia-smi"), "/usr/lib/wsl/lib/nvidia-smi"]
        for executable in candidates:
            if not executable or not Path(executable).is_file():
                continue
            try:
                driver = subprocess.check_output([executable, "--query-gpu=driver_version", "--format=csv,noheader"], text=True).splitlines()[0].strip()
                break
            except (OSError, subprocess.SubprocessError, IndexError):
                continue
    role = "official_cu118" if gpu_count else "official_cpu"
    result = {"host_id": host_id, "hostname": socket.gethostname(), "python_version": platform.python_version(), "numpy_version": np.__version__, "torch_version": str(torch.__version__).split("+", 1)[0], "wheel_role": role, "device": device, "cuda_runtime": cuda_runtime, "driver_version": driver, "gpu_count": gpu_count, "total_vram_bytes": vram, **memory}
    result["swap_before_bytes"] = int((before or {}).get("swap_after_bytes", (before or {}).get("swap_used_bytes", result["swap_used_bytes"])))
    result["swap_after_bytes"] = result["swap_used_bytes"]
    result["swap_growth_bytes"] = result["swap_after_bytes"] - result["swap_before_bytes"]
    result["attestation_digest"] = _digest({k: v for k, v in result.items() if k != "attestation_digest"})
    return result


def validate_host_attestation(config: Mapping[str, Any], host_id: str, attestation: Mapping[str, Any]) -> None:
    host = next((row for row in config.get("hosts", ()) if row.get("host_id") == host_id), None)
    if host is None or attestation.get("host_id") != host_id:
        raise ValueError("host attestation identity mismatch")
    expected_hostname = host.get("hostname", HOSTNAMES.get(host_id))
    if expected_hostname and attestation.get("hostname") != expected_hostname:
        raise ValueError("host attestation hostname mismatch")
    runtime = config["runtime"]
    if str(attestation.get("python_version", ""))[:4] != runtime["python_major_minor"] or str(attestation.get("numpy_version")) != runtime["numpy_version"] or str(attestation.get("torch_version", "")).split("+", 1)[0] != runtime["torch_version"]:
        raise ValueError("host runtime attestation mismatch")
    expected_device = host["device"]
    if expected_device == "cpu" and (attestation.get("device") != "cpu" or attestation.get("gpu_count", 0) != 0):
        raise ValueError("CPU host device mismatch")
    if expected_device.startswith("cuda") and (not str(attestation.get("device", "")).startswith("cuda") or int(attestation.get("gpu_count", 0)) < 2):
        raise ValueError("CUDA host device/GPU count mismatch")
    expected_role = runtime.get(f"{host_id}_wheel", "official_cu118" if expected_device.startswith("cuda") else "official_cpu")
    if attestation.get("wheel_role") != expected_role:
        raise ValueError("host wheel role mismatch")
    if expected_device.startswith("cuda") and str(attestation.get("driver_version")) != str(runtime.get("alien_driver_version")):
        raise ValueError("Alien driver mismatch")
    if expected_device.startswith("cuda") and not str(attestation.get("cuda_runtime", "")).startswith("11.8"):
        raise ValueError("CUDA runtime mismatch")
    if expected_device == "cpu" and str(attestation.get("cuda_runtime")) != "none":
        raise ValueError("CPU CUDA runtime mismatch")
    for key in ("total_ram_bytes", "total_vram_bytes", "swap_total_bytes", "swap_used_bytes", "swap_before_bytes", "swap_after_bytes", "swap_growth_bytes"):
        if key not in attestation or int(attestation[key]) < 0:
            raise ValueError("host memory attestation incomplete")
    if int(attestation["swap_used_bytes"]) != int(attestation["swap_after_bytes"]) or int(attestation["swap_growth_bytes"]) != int(attestation["swap_after_bytes"]) - int(attestation["swap_before_bytes"]):
        raise ValueError("host swap attestation mismatch")
    if not attestation.get("attestation_digest") or attestation.get("attestation_digest") != _digest({k: v for k, v in attestation.items() if k != "attestation_digest"}):
        raise ValueError("host attestation digest mismatch")


def validate_receipt(receipt: dict[str, Any], config: Mapping[str, Any] | None = None, private_root: str | Path | None = None) -> bool:
    encoded = json.dumps(receipt, sort_keys=True).lower()
    if any(token in encoded for token in FORBIDDEN):
        return False
    if receipt.get("schema_version") == "goal032-calibration-receipt-v1":
        required = (receipt.get("success") is True and receipt.get("count") == 24 and receipt.get("serial_count") == 18 and receipt.get("concurrency_count") == 6 and receipt.get("logical_evaluations") == 24 and receipt.get("physical_fit_count") == 48 and receipt.get("projected_architecture_logical_evaluations") == 1440 and receipt.get("projected_architecture_physical_fits") == 2880 and receipt.get("outer_attempted") == 0 and receipt.get("outer_opened") == 0 and receipt.get("deterministic_pairs") is True and len(receipt.get("serial_hosts", ())) == 3 and len(receipt.get("concurrency_hosts", ())) == 1 and receipt.get("recommendation") and receipt.get("inventory_digest") and receipt.get("bundle_inventory_digest") and receipt.get("authority_digest") and receipt.get("runtime_attestation_digest") and receipt.get("worker_policy"))
        if not required:
            return False
        if private_root is None or config is None:
            return False
        try:
            rows = _read_private_rows(Path(private_root))
            recomputed = summarize(rows, config=config)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        return receipt == recomputed and _validate_bundle_inventory(config, Path(private_root), rows)
    return bool(receipt.get("status") == "ok" and receipt.get("outer_attempted") == 0 and receipt.get("outer_opened") == 0 and receipt.get("finite_outputs") is True and receipt.get("model_digest") and receipt.get("prediction_digest") and receipt.get("bundle_digest"))


def run(bundle_path: str | Path, *, architecture: str, seed: int, device: str = "cpu", max_epochs: int = 300) -> dict[str, Any]:
    bundle = load_bundle(bundle_path)
    receipt = train_case(bundle, architecture_by_id(architecture), seed=seed, device=device, max_epochs=max_epochs)
    return receipt.to_dict()


def case_specs(config: dict[str, Any]) -> dict[str, CaseSpec]:
    return {row["case_id"]: CaseSpec(row["case_id"], row["target"], row["held_fold"], row["architecture"]["id"], derive_case_seed(config["training"]["base_seed"], row["case_id"])) for row in config["cases"]}


def _bundle_for(bundle_root: Path, case_id: str) -> Path:
    candidates = sorted(bundle_root.glob(f"{case_id}-*.npz")) or sorted(bundle_root.glob(f"{case_id}.npz"))
    if len(candidates) != 1: raise ValueError(f"expected one content-addressed bundle for {case_id}")
    return candidates[0]


def _host_context(config: Mapping[str, Any], host_id: str, attestation: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    host = next((row for row in config["hosts"] if row["host_id"] == host_id), None)
    if host is None: raise ValueError("unknown host")
    witness = dict(attestation) if attestation is not None else collect_host_attestation(host_id)
    validate_host_attestation(config, host_id, witness)
    return host, witness


def _decorate(value: dict[str, Any], *, config: Mapping[str, Any], host_id: str, host_attestation: Mapping[str, Any], panel: str, repeat: int, case_id: str, architecture: Mapping[str, Any], seed: int, worker_device: str | None = None, panel_makespan: float | None = None) -> dict[str, Any]:
    value.update({"host_id": host_id, "repeat": repeat, "panel": panel, "case_id": case_id, "seed": seed, "seed_derivation": "goal032|base_seed|case_id|target", "architecture_id": architecture["id"], "architecture_spec": dict(architecture), "host_attestation": dict(host_attestation), "runtime_attestation_digest": host_attestation["attestation_digest"]})
    if worker_device is not None: value["worker_device"] = worker_device
    if panel_makespan is not None: value["panel_makespan_seconds"] = panel_makespan
    return value


def run_serial(config: dict[str, Any], host_id: str, bundle_root: Path, output: Path, *, attestation: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    host, witness = _host_context(config, host_id, attestation)
    output.mkdir(parents=True, exist_ok=True); receipts = []
    for case_id, case in case_specs(config).items():
        bundle_path = _bundle_for(bundle_root, case_id); expected = dict(next(row for row in config["cases"] if row["case_id"] == case_id)); expected["seed"] = case.seed
        validate_bundle(bundle_path, expected, config)
        for repeat in range(2):
            value = run(bundle_path, architecture=case.architecture, seed=case.seed, device=host["device"], max_epochs=config["training"]["early_stopping"]["maximum_epochs"])
            value = _decorate(value, config=config, host_id=host_id, host_attestation=witness, panel="serial", repeat=repeat, case_id=case_id, architecture=expected["architecture"], seed=case.seed)
            (output / f"{case_id}-repeat{repeat:02d}.json").write_text(json.dumps(value, sort_keys=True), encoding="utf-8"); receipts.append(value)
    after = collect_host_attestation(host_id, before=witness)
    validate_host_attestation(config, host_id, after)
    for value in receipts:
        value["host_attestation"] = dict(after); value["runtime_attestation_digest"] = after["attestation_digest"]
        (output / f"{value['case_id']}-repeat{int(value['repeat']):02d}.json").write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return receipts


def run_concurrency(config: dict[str, Any], host_id: str, bundle_root: Path, output: Path, *, attestation: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    host, witness = _host_context(config, host_id, attestation)
    workers = int(host.get("concurrency_worker_cap", 1));
    if host["device"].startswith("cuda"):
        workers = min(workers, int(host.get("maximum_workers_per_gpu", 1)) * int(witness.get("gpu_count", 0)))
    if host["device"].startswith("cuda") and workers < 2: raise ValueError("Alien requires one worker per GPU")
    tasks = [(case_id, repeat, (f"cuda:{i % workers}" if host["device"].startswith("cuda") else "cpu")) for i, (case_id, repeat) in enumerate(( (c, r) for r in range(2) for c in case_specs(config)))]
    output.mkdir(parents=True, exist_ok=True); started = time.monotonic()
    payloads = [(config, host_id, bundle_root, output, case_id, repeat, worker_device, witness) for case_id, repeat, worker_device in tasks]
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as executor:
        if host["device"].startswith("cuda"):
            batches = [[payload for payload in payloads if payload[6] == f"cuda:{index}"] for index in range(workers)]
            values = [value for batch in executor.map(_concurrency_batch, batches) for value in batch]
        else:
            values = list(executor.map(_concurrency_worker, payloads))
    elapsed = round(time.monotonic() - started, 6)
    after = collect_host_attestation(host_id, before=witness)
    validate_host_attestation(config, host_id, after)
    for value in values:
        value["panel_makespan_seconds"] = elapsed
        value["host_attestation"] = dict(after); value["runtime_attestation_digest"] = after["attestation_digest"]
        (output / f"{value['case_id']}-repeat{int(value['repeat']):02d}.json").write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return values


def _concurrency_worker(payload: tuple[Any, ...]) -> dict[str, Any]:
    config, host_id, bundle_root, output, case_id, repeat, worker_device, witness = payload
    host, _ = _host_context(config, host_id, witness)
    case = case_specs(config)[case_id]; expected = dict(next(row for row in config["cases"] if row["case_id"] == case_id)); expected["seed"] = case.seed
    bundle = _bundle_for(bundle_root, case_id); validate_bundle(bundle, expected, config)
    value = run(bundle, architecture=case.architecture, seed=case.seed, device=worker_device, max_epochs=config["training"]["early_stopping"]["maximum_epochs"])
    value = _decorate(value, config=config, host_id=host_id, host_attestation=witness, panel="concurrency", repeat=repeat, case_id=case_id, architecture=expected["architecture"], seed=case.seed, worker_device=worker_device)
    (output / f"{case_id}-repeat{repeat:02d}.json").write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return value


def _concurrency_batch(payloads: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Run one fixed task queue in one process, hence on one fixed GPU."""
    return [_concurrency_worker(payload) for payload in payloads]


def _semantic_tuple(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("selected_epoch", row.get("discovery_epochs")),
        row.get("discovery_executed_epochs", row.get("executed_epochs", row.get("discovery_epochs"))),
        row.get("replay_epochs"),
        row.get("discovery_initial_state_digest", row.get("initial_model_digest", row.get("initial_digest"))),
        row.get("replay_initial_state_digest", row.get("initial_model_digest", row.get("initial_digest"))),
        row.get("model_digest"), row.get("prediction_digest"), row.get("bundle_digest"), row.get("runtime_attestation_digest"),
    )


def _deterministic_pairs(receipts: list[dict[str, Any]]) -> bool:
    for panel in {r.get("panel") for r in receipts}:
        for host in {r.get("host_id") for r in receipts if r.get("panel") == panel}:
            for case in {r.get("case_id") for r in receipts if r.get("panel") == panel and r.get("host_id") == host}:
                pair = [r for r in receipts if r.get("panel") == panel and r.get("host_id") == host and r.get("case_id") == case]
                if len(pair) != 2 or {r.get("repeat") for r in pair} != {0, 1} or len({_semantic_tuple(r) for r in pair}) != 1:
                    return False
                if any(any(value in (None, "") for value in _semantic_tuple(row)) for row in pair):
                    return False
    # The selected host reruns the same case/seed under concurrency.  Runtime
    # witness digests may differ after a second panel, but model semantics may not.
    for host in {r.get("host_id") for r in receipts}:
        for case in {r.get("case_id") for r in receipts if r.get("host_id") == host}:
            rows = [r for r in receipts if r.get("host_id") == host and r.get("case_id") == case]
            if {r.get("panel") for r in rows} == {"serial", "concurrency"}:
                semantics = {tuple(value for index, value in enumerate(_semantic_tuple(row)) if index != 8) for row in rows}
                if len(semantics) != 1:
                    return False
    return bool(receipts)


def _inventory_valid(receipts: list[dict[str, Any]], config: Mapping[str, Any] | None) -> bool:
    """Check the evidence rows, rather than trusting aggregate booleans."""
    if len(receipts) != 24 or any(r.get("status") != "ok" or r.get("finite_outputs") is not True or r.get("outer_attempted", 0) != 0 or r.get("outer_opened", 0) != 0 for r in receipts):
        return False
    for row in receipts:
        try:
            selected = int(row.get("selected_epoch", 0))
            executed = int(row.get("discovery_executed_epochs", 0))
            replay = int(row.get("replay_epochs", 0))
            wall = float(row.get("wall_seconds", 0.0))
        except (TypeError, ValueError):
            return False
        if not (1 <= selected <= executed <= 300 and replay == selected and wall > 0.0 and math.isfinite(wall)):
            return False
        if row.get("stopping_status") not in {"patience_stop", "max_epochs_reached"}:
            return False
    keys = [(r.get("panel"), r.get("host_id"), r.get("case_id"), r.get("repeat")) for r in receipts]
    if len(set(keys)) != 24 or any(None in key for key in keys):
        return False
    if config is not None:
        hosts = {h["host_id"] for h in config.get("hosts", ())}; cases = {c["case_id"]: c for c in config.get("cases", ())}
        if {r.get("panel") for r in receipts} != {"serial", "concurrency"} or {r.get("host_id") for r in receipts if r.get("panel") == "serial"} != hosts:
            return False
        if len({r.get("host_id") for r in receipts if r.get("panel") == "concurrency"}) != 1:
            return False
        serial_rates = {host: 6.0 / max(1e-12, sum(float(r.get("wall_seconds", 0.0)) for r in receipts if r.get("panel") == "serial" and r.get("host_id") == host)) for host in hosts}
        cpu_hosts = {h["host_id"] for h in config.get("hosts", ()) if h.get("device") == "cpu"}
        gpu_hosts = hosts - cpu_hosts
        best_cpu = max((serial_rates[h] for h in cpu_hosts), default=0.0)
        best_gpu = max((serial_rates[h] for h in gpu_hosts), default=0.0)
        provisional = max(cpu_hosts, key=lambda h: serial_rates[h]) if best_cpu >= 0.8 * best_gpu and cpu_hosts else (max(gpu_hosts, key=lambda h: serial_rates[h]) if gpu_hosts else None)
        if {r.get("host_id") for r in receipts if r.get("panel") == "concurrency"} != {provisional}:
            return False
        for row in receipts:
            case = cases.get(row.get("case_id"));
            if case is None or row.get("architecture") != case["architecture"]["id"] or row.get("architecture_id", row.get("architecture")) != case["architecture"]["id"] or row.get("architecture_spec") != case["architecture"] or row.get("seed") != derive_case_seed(config["training"]["base_seed"], row["case_id"]):
                return False
            witness = row.get("host_attestation")
            if not isinstance(witness, Mapping) or witness.get("host_id") != row.get("host_id") or row.get("runtime_attestation_digest") != witness.get("attestation_digest"):
                return False
            try:
                validate_host_attestation(config, str(row.get("host_id")), witness)
            except ValueError:
                return False
            if int(witness.get("swap_growth_bytes", 1)) > 0:
                return False
        for case_id in cases:
            if len({r.get("bundle_digest") for r in receipts if r.get("case_id") == case_id}) != 1:
                return False
    return all(r.get("bundle_digest") and r.get("runtime_attestation_digest") and r.get("model_digest") and r.get("prediction_digest") for r in receipts)


def _read_private_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.rglob("*-repeat*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError: continue
        if isinstance(value, dict) and value.get("panel") in {"serial", "concurrency"}: rows.append(value)
    return rows


def _validate_bundle_inventory(config: Mapping[str, Any], private_root: Path, rows: list[dict[str, Any]]) -> bool:
    bundle_root = private_root.parent / "bundles"
    expected_digests: dict[str, str] = {}
    for case_id, case in case_specs(dict(config)).items():
        expected = dict(next(row for row in config["cases"] if row["case_id"] == case_id))
        expected["seed"] = case.seed
        bundle = validate_bundle(_bundle_for(bundle_root, case_id), expected, config)
        expected_digests[case_id] = str(bundle.metadata["bundle_digest"])
    return all(row.get("bundle_digest") == expected_digests.get(str(row.get("case_id"))) for row in rows)


def summarize(receipts: list[dict[str, Any]], *, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    serial = [r for r in receipts if r.get("panel") == "serial"]; concurrency = [r for r in receipts if r.get("panel") == "concurrency"]
    serial_hosts = sorted({r.get("host_id") for r in serial}); concurrency_hosts = sorted({r.get("host_id") for r in concurrency}); deterministic = _deterministic_pairs(receipts)
    inventory_valid = _inventory_valid(receipts, config)
    bundles = sorted({r.get("bundle_digest") for r in receipts if r.get("bundle_digest")}); attests = sorted({r.get("runtime_attestation_digest") or r.get("host_attestation", {}).get("attestation_digest") for r in receipts if r.get("runtime_attestation_digest") or r.get("host_attestation", {}).get("attestation_digest")})
    inventory = sorted(
        ({k: r.get(k) for k in ("panel", "host_id", "case_id", "repeat", "seed", "architecture", "architecture_spec", "bundle_digest", "model_digest", "prediction_digest", "runtime_attestation_digest", "status", "finite_outputs", "outer_attempted", "outer_opened")} for r in receipts),
        key=lambda row: (str(row["panel"]), str(row["host_id"]), str(row["case_id"]), int(row["repeat"])),
    )
    panel_makespan = max((float(r.get("panel_makespan_seconds", 0.0)) for r in concurrency), default=0.0)
    serial_rates = {host: 6.0 / max(1e-12, sum(float(r.get("wall_seconds", 0.0)) for r in serial if r.get("host_id") == host)) for host in serial_hosts}
    cpu_hosts = {h["host_id"] for h in (config or {}).get("hosts", ()) if h.get("device") == "cpu"} & set(serial_hosts); gpu_hosts = set(serial_hosts) - cpu_hosts
    best_cpu = max((serial_rates[h] for h in cpu_hosts), default=0.0); best_gpu = max((serial_rates[h] for h in gpu_hosts), default=0.0)
    provisional = max(cpu_hosts, key=lambda h: serial_rates[h]) if best_cpu >= 0.8 * best_gpu and cpu_hosts else (max(gpu_hosts, key=lambda h: serial_rates[h]) if gpu_hosts else None)
    recommendation = concurrency_hosts[0] if len(concurrency_hosts) == 1 and len(concurrency) == 6 and concurrency_hosts[0] == provisional else None
    selected_rows = [r for r in concurrency if r.get("host_id") == recommendation]
    epoch_cost = max((float(r.get("wall_seconds", 0.0)) / max(1, int(r.get("discovery_executed_epochs", 0)) + int(r.get("replay_epochs", 0))) for r in selected_rows), default=0.0)
    selected_attestations = [r.get("host_attestation", {}) for r in receipts if r.get("host_id") == recommendation]
    selected_host_rows = [r for r in receipts if r.get("host_id") == recommendation]
    total_ram = max((int(a.get("total_ram_bytes", 0)) for a in selected_attestations), default=0); total_vram = max((int(a.get("total_vram_bytes", 0)) for a in selected_attestations), default=0)
    peak_rss = max((int(r.get("peak_rss_bytes", 0)) for r in selected_host_rows), default=0)
    peak_vram = max((int(r.get("peak_vram_bytes", 0)) for r in selected_host_rows), default=0)
    workers = int(next((h.get("concurrency_worker_cap", 1) for h in (config or {}).get("hosts", ()) if h.get("host_id") == recommendation), 1)) if recommendation else 0
    return {"schema_version": "goal032-calibration-receipt-v1", "success": len(serial) == 18 and len(concurrency) == 6 and len(serial_hosts) == 3 and len(concurrency_hosts) == 1 and inventory_valid and deterministic, "count": len(receipts), "serial_count": len(serial), "concurrency_count": len(concurrency), "logical_evaluations": 24 if len(receipts) == 24 else len(receipts), "physical_fit_count": 48 if len(receipts) == 24 else len(receipts) * 2, "serial_hosts": serial_hosts, "concurrency_hosts": concurrency_hosts, "deterministic_pairs": deterministic, "runtime_attestation_digest": _digest(attests), "inventory_digest": _digest(inventory), "bundle_inventory_digest": _digest(bundles), "authority_digest": _digest({"goal032_config_digest": (config or {}).get("_source_sha256"), "bindings": (config or {}).get("bindings"), "publication": (config or {}).get("publication")}), "statuses": {status: sum(r.get("status") == status for r in receipts) for status in {r.get("status") for r in receipts}}, "outer_attempted": sum(r.get("outer_attempted", 0) for r in receipts), "outer_opened": sum(r.get("outer_opened", 0) for r in receipts), "projected_architecture_logical_evaluations": 1440, "projected_architecture_physical_fits": 2880, "provisional_leader": provisional, "serial_throughput": serial_rates, "cpu_preferred": bool(provisional in cpu_hosts), "recommendation": recommendation, "worker_policy": ({"host_id": recommendation, "workers": workers, "ddp": False} if recommendation else None), "central_duration_seconds": round(panel_makespan * 240, 6), "upper_bound_duration_seconds": round(epoch_cost * 600 * 1440 / max(1, workers), 6), "panel_makespan_seconds": panel_makespan, "epoch_seconds": epoch_cost, "peak_rss_bytes": peak_rss, "peak_vram_bytes": peak_vram, "ram_headroom_bytes": max(0, total_ram - workers * peak_rss), "vram_headroom_bytes": max(0, total_vram - workers * peak_vram), "swap_growth_bytes": max((int(r.get("host_attestation", {}).get("swap_growth_bytes", 0)) for r in receipts), default=0)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.compute_canary"); parser.add_argument("--config", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    def with_config(command): command.add_argument("--config", type=Path, default=argparse.SUPPRESS); return command
    with_config(sub.add_parser("plan")); run_parser = with_config(sub.add_parser("run")); run_parser.add_argument("bundle", type=Path); run_parser.add_argument("--architecture", required=True); run_parser.add_argument("--seed", type=int, default=31032); run_parser.add_argument("--device", default="cpu"); run_parser.add_argument("--max-epochs", type=int, default=300)
    export = with_config(sub.add_parser("export")); export.add_argument("--root", type=Path, default=Path.cwd()); export.add_argument("--output", type=Path, required=True)
    serial = with_config(sub.add_parser("serial")); serial.add_argument("--host", required=True); serial.add_argument("--bundle", type=Path, required=True); serial.add_argument("--output", type=Path, required=True); serial.add_argument("--attestation", type=Path)
    concurrency = with_config(sub.add_parser("concurrency")); concurrency.add_argument("--host", required=True); concurrency.add_argument("--bundle", type=Path, required=True); concurrency.add_argument("--output", type=Path, required=True); concurrency.add_argument("--attestation", type=Path)
    bundle_validate = with_config(sub.add_parser("validate-bundle")); bundle_validate.add_argument("--bundle", type=Path, required=True)
    recommend = with_config(sub.add_parser("recommend")); recommend.add_argument("--private-root", type=Path, required=True); recommend.add_argument("--output", type=Path, required=True)
    val = with_config(sub.add_parser("validate")); val.add_argument("receipt", type=Path, nargs="?"); val.add_argument("--private-root", type=Path); val.add_argument("--receipt", dest="receipt_option", type=Path)
    attest = with_config(sub.add_parser("attest")); attest.add_argument("--host", required=True); attest.add_argument("--before", type=Path); attest.add_argument("--output", type=Path)
    summ = sub.add_parser("summarize"); summ.add_argument("receipts", type=Path)
    args = parser.parse_args(argv)
    if args.command == "attest":
        before = json.loads(args.before.read_text()) if args.before else None; result = collect_host_attestation(args.host, before=before); text = json.dumps(result, sort_keys=True); print(text); args.output and args.output.write_text(text + "\n", encoding="utf-8"); return 0
    if args.command == "plan": print(json.dumps(build_plan(load_config(args.config) if args.config else {}), sort_keys=True)); return 0
    if args.command == "run": print(json.dumps(run(args.bundle, architecture=args.architecture, seed=args.seed, device=args.device, max_epochs=args.max_epochs), sort_keys=True)); return 0
    if args.command == "export":
        config = load_config(args.config); args.output.mkdir(parents=True, exist_ok=True)
        from dsdm.real_data import bundle_digest
        for cid, case in case_specs(config).items():
            temporary = args.output / f"{cid}.npz"; bundle = bind_case_from_foundation(args.root, config, case, temporary); temporary.replace(args.output / f"{cid}-{bundle_digest(bundle)}.npz")
        print(json.dumps({"case_count": 3, "outer_attempted": 0, "outer_opened": 0}, sort_keys=True)); return 0
    if args.command in {"serial", "concurrency"}:
        config = load_config(args.config); witness = json.loads(args.attestation.read_text()) if args.attestation else None
        values = run_serial(config, args.host, args.bundle, args.output, attestation=witness) if args.command == "serial" else run_concurrency(config, args.host, args.bundle, args.output, attestation=witness); print(json.dumps(summarize(values, config=config), sort_keys=True)); return 0
    if args.command == "validate-bundle":
        config = load_config(args.config); results = []
        for cid, case in case_specs(config).items():
            path = _bundle_for(args.bundle, cid); expected = dict(next(r for r in config["cases"] if r["case_id"] == cid)); expected["seed"] = case.seed; value = validate_bundle(path, expected, config); results.append({"case_id": cid, "bundle_digest": value.metadata["bundle_digest"]})
        print(json.dumps({"valid": True, "cases": results}, sort_keys=True)); return 0
    if args.command == "recommend":
        config = load_config(args.config); values = _read_private_rows(args.private_root); result = summarize(values, config=config); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, sort_keys=True), encoding="utf-8"); print(json.dumps(result, sort_keys=True)); return 0
    if args.command == "validate":
        receipt_path = args.receipt_option or args.receipt or (args.private_root / "receipt.json" if args.private_root else None)
        if receipt_path is None: raise SystemExit("receipt path required")
        ok = validate_receipt(json.loads(receipt_path.read_text()), load_config(args.config), args.private_root); print(json.dumps({"valid": ok})); return 0 if ok else 1
    values = json.loads(args.receipts.read_text()); print(json.dumps(summarize(values), sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
