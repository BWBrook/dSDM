"""Measure and bound the approved Linux conventional sensitivity execution.

Runs only the fixed smoke or four conventional shards. A cap breach or worker
failure writes ABORT before terminating the process groups. This does not retry
fits. RSS is the conservatively summed resident size of those process groups.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def exclusive_json(path, body):
    body = dict(body)
    body["receipt_digest"] = hashlib.sha256(canonical(body)).hexdigest()
    with Path(path).open("x") as stream:
        json.dump(body, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return body


def group_rss(groups):
    total = 0
    processes = 0
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) in groups:
                total += int(fields[21]) * os.sysconf("SC_PAGE_SIZE")
                processes += 1
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return total, processes


def storage_bytes(root):
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            continue
    return total


def terminate_workers(workers):
    groups = {worker.pid for worker in workers}
    for worker in workers:
        # A dead group leader can leave a live fitting child behind.
        try:
            os.killpg(worker.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        for worker in workers:
            worker.poll()
        if group_rss(groups)[1] == 0:
            break
        time.sleep(0.1)
    for group in groups:
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for worker in workers:
        worker.wait()


def interrupted(signum, frame):
    raise KeyboardInterrupt(f"supervisor received signal {signum}")


def run(root, python, stage, expected_runner_sha):
    if os.uname().sysname != "Linux":
        raise ValueError("supervisor requires Linux /proc")
    runner = root / "scripts/tasmania_pseudoabsence_conventional.py"
    if sha(runner) != expected_runner_sha:
        raise ValueError("reviewed runner source changed")
    private = root / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private/conventional"
    if (private / "ABORT.json").exists():
        raise ValueError("panel already aborted")
    logs = private / "supervisor" / stage
    logs.mkdir(parents=True, exist_ok=False)
    lock = private / "supervisor-exclusive.lock"
    lock.mkdir(exist_ok=False)
    started = time.monotonic()
    before_bytes = storage_bytes(private)
    limits = None
    if stage != "smoke":
        cap_receipt = json.loads((private / "production-caps.json").read_text())
        body = dict(cap_receipt)
        claimed = body.pop("receipt_digest")
        if hashlib.sha256(canonical(body)).hexdigest() != claimed:
            raise ValueError("resource cap receipt changed")
        if cap_receipt.get("supervisor_sha256") != sha(__file__):
            raise ValueError("resource cap supervisor binding changed")
        limits = cap_receipt["caps"]
    execution = {"schema_version": "tasmania-conventional-supervisor-v1", "stage": stage,
                 "started_unix": time.time(), "runner_sha256": expected_runner_sha,
                 "supervisor_sha256": sha(__file__), "pid": os.getpid(),
                 "workers": 1 if stage == "smoke" else 4,
                 "production_caps_digest": None if limits is None else claimed}
    exclusive_json(logs / "intent.json", execution)
    workers, streams = [], []
    error = None
    peak_rss = peak_processes = 0
    peak_bytes = before_bytes
    last_storage = 0.0
    signal.signal(signal.SIGTERM, interrupted)
    try:
        for shard in range(execution["workers"]):
            stream = (logs / f"worker-{shard}.log").open("x")
            streams.append(stream)
            command = [str(python), str(runner), stage, "--root", str(root)]
            if stage != "smoke":
                command += ["--shard-index", str(shard), "--shard-count", "4"]
            workers.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                            start_new_session=True,
                                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1")))
        groups = {worker.pid for worker in workers}
        while True:
            elapsed = time.monotonic() - started
            rss, process_count = group_rss(groups)
            peak_rss = max(peak_rss, rss)
            peak_processes = max(peak_processes, process_count)
            if elapsed - last_storage >= 2:
                peak_bytes = max(peak_bytes, storage_bytes(private))
                last_storage = elapsed
            codes = [worker.poll() for worker in workers]
            if (private / "ABORT.json").exists():
                error = "worker recorded ABORT"
            elif any(code is not None and code != 0 for code in codes):
                error = "worker exited unsuccessfully"
            elif limits is not None:
                if elapsed > limits["wall_time_seconds"]:
                    error = "wall-time cap exceeded"
                elif rss > limits["peak_rss_bytes"]:
                    error = "resident-memory cap exceeded"
                elif peak_bytes > limits["private_storage_bytes"]:
                    error = "private-storage cap exceeded"
            finished = all(code is not None for code in codes)
            if finished:
                peak_bytes = max(peak_bytes, storage_bytes(private))
                if limits is not None and peak_bytes > limits["private_storage_bytes"]:
                    error = "private-storage cap exceeded at completion"
            if error or finished:
                break
            time.sleep(0.1)
        if error:
            abort = private / "ABORT.json"
            if not abort.exists():
                try:
                    exclusive_json(abort, {**execution, "status": "failed", "reason": error,
                                           "wall_seconds": elapsed, "peak_rss_bytes": peak_rss,
                                           "private_storage_bytes": peak_bytes})
                except FileExistsError:
                    pass
    except BaseException as exc:
        error = f"supervisor error: {type(exc).__name__}: {exc}"
        abort = private / "ABORT.json"
        if not abort.exists():
            try:
                exclusive_json(abort, {**execution, "status": "failed", "reason": error,
                                       "wall_seconds": time.monotonic() - started})
            except FileExistsError:
                pass
    finally:
        # Termination must still run if an ABORT write fails (for example,
        # because the storage cap coincides with a full filesystem).
        try:
            if error is not None:
                terminate_workers(workers)
        finally:
            for stream in streams:
                stream.close()
    result = {**execution, "status": "accepted" if error is None else "failed", "error": error,
              "finished_unix": time.time(), "wall_seconds": time.monotonic() - started,
              "peak_rss_bytes": peak_rss, "peak_process_count": peak_processes,
              "initial_private_storage_bytes": before_bytes, "final_private_storage_bytes": storage_bytes(private),
              "maximum_observed_private_storage_bytes": max(peak_bytes, storage_bytes(private)),
              "worker_exit_codes": [worker.returncode for worker in workers],
              "rss_measurement": "sum of resident pages in launched process groups, sampled every 100 ms",
              "storage_measurement": "all conventional private files, sampled every 2 s"}
    receipt = exclusive_json(logs / "receipt.json", result)
    if error is None:
        lock.rmdir()
    print(json.dumps(receipt, sort_keys=True), flush=True)
    if error:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("smoke", "run-inner", "run-outer"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path("/data/codex/repos/dsdm-goal029-f85e459/.venv/bin/python"))
    parser.add_argument("--runner-sha256", required=True)
    args = parser.parse_args()
    # Preserve the venv executable path: resolving its symlink would bypass
    # pyvenv.cfg and silently select the system interpreter's package set.
    run(args.root.resolve(), args.python.absolute(), args.stage, args.runner_sha256)
