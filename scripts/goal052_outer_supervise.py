#!/usr/bin/env python3
"""Run the retained-full Goal 052 outer campaign under a bounded host guard.

This module deliberately delegates all scientific validation to
``dsdm_phase1.goal052_outer``.  It only owns process lifetime, resource
limits, and production-control receipts.  The intended execution host is
Linux; an absent ``/proc/meminfo`` is recorded as unavailable so the helper
can still be smoke-tested on macOS.
"""

from __future__ import print_function

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple


STAGES = ("q", "pretraining", "neural", "conventional", "close", "verify")
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
GIB = 1024 ** 3
POLL_SECONDS = 5.0
TERM_GRACE_SECONDS = 60.0

_STOP_REQUESTED = None  # type: Optional[str]


def _utc() -> str:
    # datetime.fromtimestamp is avoided so this remains usable on old Python
    # versions without depending on a third-party date package.
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _atomic_write(path: Path, value: Dict[str, Any]) -> None:
    """Replace a mutable JSON receipt without exposing a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _immutable_write(path: Path, value: Dict[str, Any]) -> None:
    """Create a JSON receipt once, refusing an accidental second result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(str(temporary), str(path))
        except FileExistsError:
            raise RuntimeError("immutable receipt already exists: {}".format(path))
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_mem_available_bytes(meminfo: Path = Path("/proc/meminfo")) -> Optional[int]:
    """Return Linux MemAvailable in bytes, or None where /proc is unavailable."""
    try:
        lines = meminfo.read_text().splitlines()
    except (FileNotFoundError, OSError):
        return None
    for line in lines:
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "MemAvailable:":
            try:
                # /proc/meminfo reports kB (1024-byte units).
                return int(fields[1]) * 1024
            except ValueError:
                return None
    return None


def _resource_snapshot(root: Path) -> Dict[str, Optional[int]]:
    try:
        free_bytes = int(shutil.disk_usage(str(root)).free)
    except OSError:
        free_bytes = None
    return {
        "memory_available_bytes": _read_mem_available_bytes(),
        "disk_free_bytes": free_bytes,
    }


def _resource_violation(snapshot: Dict[str, Optional[int]], memory_floor: int,
                        disk_floor: int) -> Optional[str]:
    memory_available = snapshot.get("memory_available_bytes")
    if memory_available is None and memory_floor > 0:
        return "memory_available_unavailable"
    if memory_available is not None and memory_available < memory_floor:
        return "memory_floor_exceeded"
    disk_free = snapshot.get("disk_free_bytes")
    if disk_free is None:
        return "disk_free_unavailable"
    if disk_free < disk_floor:
        return "disk_floor_exceeded"
    return None


def _signal_handler(signum: int, _frame: Any) -> None:
    global _STOP_REQUESTED
    try:
        name = signal.Signals(signum).name
    except ValueError:
        name = "signal-{}".format(signum)
    _STOP_REQUESTED = name


def _group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _terminate_process_group(process: subprocess.Popen, reason: str,
                             grace_seconds: float = TERM_GRACE_SECONDS) -> Dict[str, Any]:
    """Terminate only the process group created for this child."""
    process_group = int(process.pid)
    action = {"reason": reason, "term_sent": False, "kill_sent": False,
              "term_grace_seconds": grace_seconds}
    # The group may outlive its leader when a worker spawned descendants.
    # Signal the group even when the leader has already returned.
    if _group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGTERM)
            action["term_sent"] = True
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + grace_seconds
    while _group_exists(process_group) and time.monotonic() < deadline:
        remaining = max(0.01, deadline - time.monotonic())
        if process.poll() is None:
            try:
                process.wait(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                pass
        else:
            time.sleep(min(0.1, remaining))
    if _group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGKILL)
            action["kill_sent"] = True
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        # The supervisor cannot safely wait forever.  The group was already
        # addressed with KILL; retain the original failure reason.
        pass
    action["return_code"] = process.returncode
    return action


def _command(base: Sequence[str], root: Path, run: Path, stage: str, workers: int) -> List[str]:
    command = list(base) + [
        "-m", "dsdm_phase1.goal052_outer",
    ]
    if stage in ("q", "pretraining", "neural", "conventional"):
        command += ["run", "--stage", stage, "--workers", str(workers)]
    else:
        command += [stage]
    command += ["--root", str(root), "--run", str(run)]
    return command


def _args_for_receipt(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "root": str(args.root),
        "run": str(args.run),
        "python": args.python,
        "workers": args.workers,
        "max_hours": args.max_hours,
        "memory_floor_gib": args.memory_floor_gib,
        "disk_floor_gib": args.disk_floor_gib,
        "attempt": args.attempt,
    }


def _monitor_child(process: subprocess.Popen, root: Path, started_monotonic: float,
                   max_seconds: float, memory_floor: int, disk_floor: int,
                   control: Path, stage_record: Dict[str, Any],
                   status: Dict[str, Any]) -> Tuple[int, Optional[str], Dict[str, Any]]:
    """Poll one child and return (return code, guard failure, last resources)."""
    last_snapshot = _resource_snapshot(root)
    guard_failure = None  # type: Optional[str]
    while True:
        return_code = process.poll()
        elapsed = time.monotonic() - started_monotonic
        last_snapshot = _resource_snapshot(root)
        if return_code is not None:
            # Preserve a completed leader's return code while still cleaning
            # descendants when a nonzero child leaves its group alive.
            if return_code != 0:
                stage_record["cleanup"] = _terminate_process_group(process, "stage_nonzero")
            guard_failure = None
        elif _STOP_REQUESTED:
            guard_failure = "supervisor_{}".format(_STOP_REQUESTED.lower())
        elif elapsed >= max_seconds:
            guard_failure = "wall_time_cap_exceeded"
        else:
            guard_failure = _resource_violation(
                last_snapshot, memory_floor, disk_floor)
        status["heartbeat"] = {
            "utc": _utc(), "stage": stage_record["stage"], "pid": process.pid,
            "process_group": process.pid, "elapsed_seconds": elapsed,
            "resources": last_snapshot, "guard_failure": guard_failure,
        }
        _atomic_write(control / "heartbeat.json", status["heartbeat"])
        _atomic_write(control / "status.json", status)
        if guard_failure:
            stage_record["cleanup"] = _terminate_process_group(process, guard_failure)
            return process.returncode, guard_failure, last_snapshot
        if return_code is not None:
            return return_code, None, last_snapshot
        remaining = max_seconds - elapsed
        interval = min(POLL_SECONDS, max(0.05, remaining))
        try:
            process.wait(timeout=interval)
        except subprocess.TimeoutExpired:
            continue
        except InterruptedError:
            continue


def _validate_args(args: argparse.Namespace) -> None:
    if args.workers < 1:
        raise ValueError("--workers must be >= 1")
    if args.max_hours <= 0:
        raise ValueError("--max-hours must be > 0")
    if args.memory_floor_gib < 0 or args.disk_floor_gib < 0:
        raise ValueError("resource floors must be >= 0")
    if len(args.attempt) != 3 or any(character not in "0123456789" for character in args.attempt):
        raise ValueError("--attempt must be exactly three digits")
    if not args.python.strip():
        raise ValueError("--python must not be empty")


def _acquire_run_lock(run: Path):
    lock_path = run / "production-control.lock"
    stream = lock_path.open("a+b")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as error:
        stream.close()
        raise ValueError("production run is already locked: {}".format(run)) from error
    return stream


def _release_run_lock(stream) -> None:
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


def _supervise_locked(args: argparse.Namespace, root: Path, run: Path) -> int:
    """Run one attempt while holding the run-level lock."""
    global _STOP_REQUESTED
    _STOP_REQUESTED = None
    plan_path = run / "plan.json"
    try:
        python_base = shlex.split(args.python)
    except ValueError as error:
        raise ValueError("invalid --python command: {}".format(error))
    if not python_base:
        raise ValueError("--python must contain an executable")

    control = run / "production-control-{}".format(args.attempt)
    # Exclusive creation is the relaunch guard.  Do this before any mutable
    # receipt is written and never remove this directory on failure.
    try:
        os.mkdir(str(control))
    except FileExistsError:
        raise ValueError("production attempt already exists: {}".format(control))
    started_utc = _utc()
    started_monotonic = time.monotonic()
    source_path = Path(__file__).resolve()
    source_sha = _sha256(source_path)
    plan_sha = _sha256(plan_path)
    receipt_args = _args_for_receipt(args)
    commands = [_command(python_base, root, run, stage, args.workers) for stage in STAGES]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    for name in THREAD_VARS:
        env[name] = "1"
    max_seconds = float(args.max_hours) * 3600.0
    memory_floor = int(float(args.memory_floor_gib) * GIB)
    disk_floor = int(float(args.disk_floor_gib) * GIB)
    status = {
        "schema_version": "goal052-outer-production-status-v1",
        "status": "running", "attempt": args.attempt,
        "source_supervisor_sha256": source_sha, "plan_sha256": plan_sha,
        "args": receipt_args, "started_utc": started_utc,
        "commands": [], "failure": None,
    }
    manifest = {
        "schema_version": "goal052-outer-production-control-v1",
        "attempt": args.attempt, "source_supervisor": str(source_path),
        "source_supervisor_sha256": source_sha,
        "plan": str(plan_path), "plan_sha256": plan_sha,
        "args": receipt_args, "started_utc": started_utc,
        "commands": commands, "resource_limits": {
            "max_seconds": max_seconds, "memory_floor_bytes": memory_floor,
            "disk_floor_bytes": disk_floor, "poll_seconds": POLL_SECONDS,
            "term_grace_seconds": TERM_GRACE_SECONDS,
        },
    }
    _immutable_write(control / "manifest.json", manifest)
    _atomic_write(control / "status.json", status)
    _atomic_write(control / "heartbeat.json", {"utc": started_utc, "stage": "setup", "pid": os.getpid()})

    previous_handlers = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.signal(signum, _signal_handler)

    original_failure = None  # type: Optional[Dict[str, Any]]
    all_succeeded = False
    try:
        for index, (stage, command) in enumerate(zip(STAGES, commands), 1):
            if _STOP_REQUESTED:
                original_failure = {"reason": "supervisor_{}".format(_STOP_REQUESTED.lower()),
                                    "stage": stage}
                break
            elapsed = time.monotonic() - started_monotonic
            if elapsed >= max_seconds:
                original_failure = {"reason": "wall_time_cap_exceeded", "stage": stage}
                break
            snapshot = _resource_snapshot(root)
            resource_failure = _resource_violation(snapshot, memory_floor, disk_floor)
            if resource_failure:
                original_failure = {"reason": resource_failure, "stage": stage,
                                    "resources": snapshot}
                break
            log_path = control / "stage-{:02d}-{}.log".format(index, stage)
            stage_record = {
                "index": index, "stage": stage, "command": command,
                "log": log_path.name, "started_utc": _utc(),
                "pid": None, "process_group": None, "return_code": None,
                "duration_seconds": None, "status": "running",
            }
            status["commands"].append(stage_record)
            status["current_stage"] = stage
            _atomic_write(control / "status.json", status)
            stage_started = time.monotonic()
            process = None
            try:
                with log_path.open("wb") as log:
                    process = subprocess.Popen(
                        command, cwd=str(root), env=env, stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                    stage_record["pid"] = process.pid
                    stage_record["process_group"] = process.pid
                    _atomic_write(control / "status.json", status)
                    return_code, guard_failure, snapshot = _monitor_child(
                        process, root, started_monotonic, max_seconds, memory_floor,
                        disk_floor, control, stage_record, status)
            except BaseException:
                if process is not None:
                    _terminate_process_group(process, "supervisor_exception")
                raise
            duration = time.monotonic() - stage_started
            stage_record.update({
                "ended_utc": _utc(), "duration_seconds": duration,
                "return_code": return_code, "resources": snapshot,
            })
            if guard_failure:
                stage_record["status"] = "failed"
                stage_record["failure_reason"] = guard_failure
                original_failure = {"reason": guard_failure, "stage": stage,
                                    "return_code": return_code}
            elif return_code != 0:
                stage_record["status"] = "failed"
                stage_record["failure_reason"] = "stage_nonzero"
                original_failure = {"reason": "stage_nonzero", "stage": stage,
                                    "return_code": return_code}
            else:
                stage_record["status"] = "succeeded"
            _immutable_write(control / "stage-{:02d}-{}.json".format(index, stage), dict(stage_record))
            status["failure"] = original_failure
            _atomic_write(control / "status.json", status)
            if original_failure:
                break
        else:
            all_succeeded = True
    except BaseException as error:
        if original_failure is None:
            original_failure = {"reason": "supervisor_exception", "error": repr(error)}
        status["failure"] = original_failure
        _atomic_write(control / "status.json", status)
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

    ended_utc = _utc()
    closure = run / "closure.json"
    closure_exists = closure.is_file()
    closure_sha = _sha256(closure) if closure_exists else None
    success = bool(all_succeeded and original_failure is None and closure_exists)
    final = {
        "schema_version": "goal052-outer-production-complete-v1",
        "status": "predictions_closed_verified" if success else "failed",
        "success": success, "attempt": args.attempt,
        "source_supervisor_sha256": source_sha, "plan_sha256": plan_sha,
        "args": receipt_args, "started_utc": started_utc, "ended_utc": ended_utc,
        "duration_seconds": time.monotonic() - started_monotonic,
        "commands": status["commands"], "failure": original_failure,
        "closure_sha256": closure_sha,
        "closure": {"path": "closure.json", "exists": closure_exists,
                     "sha256": closure_sha},
    }
    if all_succeeded and not closure_exists and original_failure is None:
        final["failure"] = {"reason": "closure_missing_after_successful_commands"}
    status["status"] = final["status"]
    status["ended_utc"] = ended_utc
    status["failure"] = final["failure"]
    _atomic_write(control / "status.json", status)
    _immutable_write(control / "complete.json", final)
    return 0 if success else 1


def supervise(args: argparse.Namespace) -> int:
    """Run one exclusive attempt, returning a shell-compatible exit code."""
    _validate_args(args)
    root = Path(args.root).resolve()
    run = Path(args.run).resolve()
    if not run.is_dir():
        raise ValueError("--run must be an existing directory: {}".format(run))
    plan_path = run / "plan.json"
    if not plan_path.is_file():
        raise ValueError("missing plan file: {}".format(plan_path))
    lock = _acquire_run_lock(run)
    try:
        return _supervise_locked(args, root, run)
    finally:
        _release_run_lock(lock)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable,
                        help="Python executable or shell-like wrapper command")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-hours", type=float, required=True)
    parser.add_argument("--memory-floor-gib", type=float, default=16.0)
    parser.add_argument("--disk-floor-gib", type=float, default=200.0)
    parser.add_argument("--attempt", default="001")
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    args.run = args.run.resolve()
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        return supervise(parse_args(argv))
    except (ValueError, OSError, RuntimeError) as error:
        print("goal052 outer supervisor: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
