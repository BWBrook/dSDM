#!/usr/bin/env python3
"""Continue one qualified Goal052 outer run through audit, scoring, and return.

The controller keeps fitted leaves on the remote Deep export.  It reads only
small JSON/control receipts before the response firewall has passed.  The
canonical response file is transferred from the local root only after both
the remote production closure and the independent response-free audit pass.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple


MAX_WORKERS = 24
MEMORY_RESERVE_GIB = 16.0
PROFILE_MULTIPLIER = 1.3
POLL_SECONDS = 5.0
SSH_TIMEOUT_SECONDS = 30.0
TRANSFER_TIMEOUT_SECONDS = 15.0 * 60.0
AUDIT_TIMEOUT_SECONDS = 12.0 * 3600.0
SCORE_TIMEOUT_SECONDS = 12.0 * 3600.0
REPORT_TIMEOUT_SECONDS = 2.0 * 3600.0
TRANSFER_ATTEMPTS = 3
RUNTIME_CONTROL = "runtime-control-001/complete.json"
PRODUCTION_CONTROL = "production-control-{}/complete.json"
STAGE_HELPER_RELATIVE = "scripts/goal052_outer_stage.py"
CONFIG_RELATIVE = "config/goal049_seawfb_canonical_response.json"
COMPLETION_RELATIVE = "evidence/seawfb_canonical_response/goal049/completion_receipt.json"
SUPERVISOR_RELATIVE = "scripts/goal052_outer_supervise.py"
AUDITOR_RELATIVE = "scripts/goal052_outer_independent_audit.py"
REPORT_RELATIVE = "scripts/goal052_outer_report.py"
STAGES = ("q", "pretraining", "neural", "conventional", "close", "verify")
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


class ControllerError(RuntimeError):
    """A bounded continuation gate failed."""


class TransportTimeout(ControllerError):
    """A bounded SSH/rsync operation timed out and may be retried."""


def utc_now() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _immutable_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json(value))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(str(temporary), str(path))
        except FileExistsError as error:
            raise ControllerError("immutable receipt already exists: {}".format(path)) from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _immutable_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(str(temporary), str(path))
        except FileExistsError as error:
            raise ControllerError("immutable receipt already exists: {}".format(path)) from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_json_bytes(raw: bytes, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ControllerError("invalid JSON in {}: {}".format(label, error)) from error
    if not isinstance(value, dict):
        raise ControllerError("JSON object required in {}".format(label))
    return value


def _safe_relative(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative or os.path.isabs(relative):
        raise ControllerError("unsafe {} path: {!r}".format(label, relative))
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ControllerError("{} path escapes root: {}".format(label, relative)) from error
    return candidate


class SubprocessTransport:
    """Bounded SSH/rsync transport; tests supply a compatible fake object."""

    def ssh(self, host: str, command: str, timeout: float) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, command],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise TransportTimeout("SSH timeout: {}".format(command)) from error

    def rsync(self, source: str, destination: str, timeout: float) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["rsync", "-a", "--partial", "--protect-args", source, destination],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise TransportTimeout("rsync timeout: {} -> {}".format(source, destination)) from error


def _stdout(result: Any) -> bytes:
    value = getattr(result, "stdout", b"")
    if isinstance(value, str):
        return value.encode("utf-8")
    return bytes(value or b"")


def _stderr(result: Any) -> str:
    value = getattr(result, "stderr", b"")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _returncode(result: Any) -> int:
    return int(getattr(result, "returncode", 1))


def _remaining(deadline: float, clock: Callable[[], float]) -> float:
    remaining = deadline - clock()
    if remaining <= 0:
        raise ControllerError("overall wall-time cap exceeded")
    return remaining


def _ssh_bytes(transport: Any, host: str, command: str, deadline: float,
               clock: Callable[[], float], retries: int = 1,
               sleeper: Callable[[float], None] = time.sleep) -> bytes:
    last_error = ""
    for attempt in range(retries + 1):
        timeout = min(SSH_TIMEOUT_SECONDS, _remaining(deadline, clock))
        try:
            result = transport.ssh(host, command, timeout)
        except TransportTimeout as error:
            last_error = str(error)
            if attempt < retries:
                sleeper(min(2.0 ** attempt, max(0.0, _remaining(deadline, clock))))
                continue
            raise
        if _returncode(result) == 0:
            return _stdout(result)
        last_error = _stderr(result).strip() or "return code {}".format(_returncode(result))
        if attempt < retries:
            sleeper(min(2.0 ** attempt, max(0.0, _remaining(deadline, clock))))
    raise ControllerError("SSH command failed: {}; {}".format(command, last_error))


def _ssh_text(transport: Any, host: str, command: str, deadline: float,
              clock: Callable[[], float], retries: int = 1,
              sleeper: Callable[[float], None] = time.sleep) -> str:
    return _ssh_bytes(transport, host, command, deadline, clock, retries, sleeper).decode("utf-8")


def _ssh_json(transport: Any, host: str, remote_path: str, deadline: float,
              clock: Callable[[], float], retries: int = 1,
              sleeper: Callable[[float], None] = time.sleep) -> Tuple[Dict[str, Any], bytes]:
    raw = _ssh_bytes(transport, host, "cat -- {}".format(shlex.quote(remote_path)), deadline,
                     clock, retries, sleeper)
    return _read_json_bytes(raw, remote_path), raw


def _poll_json(transport: Any, host: str, remote_path: str, deadline: float,
               clock: Callable[[], float]) -> Optional[Tuple[Dict[str, Any], bytes]]:
    """Read a polling receipt once; missing files are the only nonfatal result."""
    try:
        result = transport.ssh(host, "cat -- {}".format(shlex.quote(remote_path)),
                               min(SSH_TIMEOUT_SECONDS, _remaining(deadline, clock)))
    except TransportTimeout:
        return None
    code = _returncode(result)
    if code == 1:
        return None
    if code != 0:
        raise ControllerError("SSH polling command failed: {}".format(_stderr(result).strip()))
    raw = _stdout(result)
    return _read_json_bytes(raw, remote_path), raw


def _remote_sha256(transport: Any, host: str, path: str, deadline: float,
                   clock: Callable[[], float], sleeper: Callable[[float], None]) -> str:
    text = _ssh_text(transport, host, "sha256sum -- {}".format(shlex.quote(path)), deadline,
                     clock, retries=1, sleeper=sleeper).strip().splitlines()
    if not text:
        raise ControllerError("empty sha256sum output for {}".format(path))
    fields = text[-1].split()
    if len(fields) < 2 or len(fields[0]) != 64:
        raise ControllerError("invalid sha256sum output for {}".format(path))
    return fields[0]


def _parse_sha256sum(text: str, expected_paths: Sequence[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and len(fields[0]) == 64:
            values[fields[-1].lstrip("*")] = fields[0]
    missing = [path for path in expected_paths if path not in values]
    if missing:
        raise ControllerError("remote source hashes missing: {}".format(", ".join(missing)))
    return {path: values[path] for path in expected_paths}


def _rsync(transport: Any, source: str, destination: str, deadline: float,
           clock: Callable[[], float], sleeper: Callable[[float], None]) -> None:
    last_error = ""
    for attempt in range(TRANSFER_ATTEMPTS):
        try:
            result = transport.rsync(source, destination, min(TRANSFER_TIMEOUT_SECONDS, _remaining(deadline, clock)))
        except TransportTimeout as error:
            last_error = str(error)
            if attempt + 1 < TRANSFER_ATTEMPTS:
                sleeper(min(2.0 ** attempt, max(0.0, _remaining(deadline, clock))))
                continue
            raise
        if _returncode(result) == 0:
            return
        last_error = _stderr(result).strip() or "return code {}".format(_returncode(result))
        if attempt + 1 < TRANSFER_ATTEMPTS:
            sleeper(min(2.0 ** attempt, max(0.0, _remaining(deadline, clock))))
    raise ControllerError("rsync failed: {}; {} -> {}".format(last_error, source, destination))


def _validate_args(args: argparse.Namespace) -> None:
    if args.production_hours <= 0 or args.overall_hours <= 0:
        raise ControllerError("hour caps must be positive")
    if args.production_hours > 72.0 or args.overall_hours > 84.0:
        raise ControllerError("campaign caps are 72 production hours and 84 overall hours")
    if args.overall_hours < args.production_hours:
        raise ControllerError("--overall-hours must cover --production-hours")
    attempt = str(args.attempt)
    restart_from = getattr(args, "restart_from", None)
    if attempt not in {"001", "002"}:
        raise ControllerError("unknown continuation attempt: {}".format(attempt))
    if attempt == "001" and restart_from not in (None, ""):
        raise ControllerError("--restart-from is only valid for manual attempt 002")
    if attempt == "002" and restart_from != "001":
        raise ControllerError("manual attempt 002 requires --restart-from 001")
    if len(args.expected_plan_digest) != 64 or any(ch not in "0123456789abcdef" for ch in args.expected_plan_digest):
        raise ControllerError("--expected-plan-digest must be a lowercase SHA-256 digest")
    if not args.remote_host or not args.remote_root or not args.run_relative:
        raise ControllerError("remote host, remote root, and run-relative path are required")


def _load_local_metadata(root: Path, run: Path, expected_digest: str) -> Dict[str, Any]:
    plan_path = run / "plan.json"
    if not plan_path.is_file():
        raise ControllerError("missing local plan: {}".format(plan_path))
    plan_raw = plan_path.read_bytes()
    plan = _read_json_bytes(plan_raw, str(plan_path))
    if plan.get("plan_digest") != expected_digest:
        raise ControllerError("local plan digest does not match expected digest")
    plan_sha = sha256_bytes(plan_raw)
    config_path = _safe_relative(root, CONFIG_RELATIVE, "canonical config")
    completion_path = _safe_relative(root, COMPLETION_RELATIVE, "canonical completion")
    inputs = plan.get("inputs", {})
    if not isinstance(inputs, Mapping):
        raise ControllerError("plan inputs must be an object")
    config_expected = inputs.get(CONFIG_RELATIVE)
    completion_expected = inputs.get(COMPLETION_RELATIVE)
    config_sha = sha256_file(config_path)
    completion_sha = sha256_file(completion_path)
    if config_expected != config_sha or completion_expected != completion_sha:
        raise ControllerError("canonical config/completion hashes do not match plan inputs")
    config = _read_json_bytes(config_path.read_bytes(), str(config_path))
    completion = _read_json_bytes(completion_path.read_bytes(), str(completion_path))
    if config.get("schema_version") is None or completion.get("status") != "complete":
        raise ControllerError("canonical completion metadata is not complete")
    private_outputs = config.get("private_outputs", {})
    completion_outputs = completion.get("private_outputs", {})
    bindings = completion.get("bindings", {})
    if not isinstance(private_outputs, Mapping) or not isinstance(completion_outputs, Mapping) \
            or not isinstance(bindings, Mapping):
        raise ControllerError("canonical metadata sections must be objects")
    config_root_rel = private_outputs.get("root")
    response_rel = completion_outputs.get("canonical_species_cells")
    expected_response_sha = bindings.get("canonical_species_cells_sha256")
    if not isinstance(config_root_rel, str) or not isinstance(response_rel, str):
        raise ControllerError("canonical response path metadata is incomplete")
    response_path = _safe_relative(root, response_rel, "canonical response")
    config_root = _safe_relative(root, config_root_rel, "canonical output root")
    try:
        response_path.relative_to(config_root)
    except ValueError as error:
        raise ControllerError("canonical response escapes configured output root") from error
    if not isinstance(expected_response_sha, str) or len(expected_response_sha) != 64:
        raise ControllerError("canonical response SHA binding is missing")
    # Metadata-only readiness check.  This intentionally does not open or hash
    # the response file until the independent closure audit has passed.
    try:
        response_size = response_path.stat().st_size
    except OSError as error:
        raise ControllerError("canonical response metadata unavailable: {}".format(error)) from error
    if response_size <= 0:
        raise ControllerError("canonical response file is empty")
    return {
        "plan": plan, "plan_sha256": plan_sha, "plan_raw": plan_raw,
        "config_sha256": config_sha, "completion_sha256": completion_sha,
        "response_path": response_path, "response_relative": response_rel,
        "response_sha256": expected_response_sha, "response_size": response_size,
        "config": config, "completion": completion,
    }


def _validate_local_sources(root: Path, plan: Mapping[str, Any]) -> Dict[str, str]:
    sources = plan.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        raise ControllerError("plan source hash inventory is missing")
    observed: Dict[str, str] = {}
    for relative, expected in sorted(sources.items()):
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ControllerError("plan source hash inventory is invalid")
        actual = sha256_file(_safe_relative(root, relative, "plan source"))
        if actual != expected:
            raise ControllerError("local source drift: {}".format(relative))
        observed[relative] = actual
    return observed


def _extract_qualification(runtime: Mapping[str, Any], profile: Optional[Mapping[str, Any]]) -> Tuple[int, int]:
    nested = runtime.get("qualification") if isinstance(runtime.get("qualification"), Mapping) else {}
    values: Dict[str, Any] = dict(nested)
    values.update(runtime)
    if profile is not None:
        profile_values = dict(profile)
        profile_values.update(values)
        values = profile_values
    workers = values.get("qualified_workers")
    peak = values.get("profile_peak_bytes", values.get("peak_rss_bytes"))
    if workers is None or peak is None:
        raise ControllerError("runtime qualification lacks qualified_workers/profile peak")
    try:
        workers_i, peak_i = int(workers), int(peak)
    except (TypeError, ValueError) as error:
        raise ControllerError("runtime qualification worker/profile values are invalid") from error
    if workers_i < 1 or peak_i <= 0:
        raise ControllerError("runtime qualification worker/profile values are non-positive")
    return workers_i, peak_i


def _validate_runtime_complete(runtime: Mapping[str, Any], expected_digest: str,
                               plan_sha: str, runtime_raw: bytes, plan: Mapping[str, Any],
                               transport: Any, host: str, remote_run: str,
                               local_control: Path, deadline: float,
                               clock: Callable[[], float], sleeper: Callable[[float], None],
                               heartbeat: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Validate and retain the actual runtime controller's qualification files."""
    if runtime.get("status") != "runtime_qualification_completed":
        raise ControllerError("runtime qualification did not complete successfully")
    if runtime.get("plan_sha256") != plan_sha:
        raise ControllerError("runtime qualification plan SHA mismatch")
    if runtime.get("outer_response_rows_read") != 0:
        raise ControllerError("runtime qualification accessed outer response rows")
    _immutable_bytes(local_control / "runtime-control-001" / "complete.json", runtime_raw)
    stages = runtime.get("stages")
    if not isinstance(stages, list) or [item.get("stage") for item in stages if isinstance(item, Mapping)] != ["qualify", "profile"]:
        raise ControllerError("runtime qualification stages are incomplete")
    for stage in stages:
        if not isinstance(stage, Mapping) or stage.get("returncode") != 0:
            raise ControllerError("runtime qualification stage failed")
    files = runtime.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ControllerError("runtime qualification file map is missing")
    payloads: Dict[str, Dict[str, Any]] = {}
    for relative, expected in sorted(files.items()):
        if (not isinstance(relative, str) or not relative.startswith("qualification/")
                or not relative.endswith(".json") or not isinstance(expected, str)
                or len(expected) != 64):
            raise ControllerError("runtime qualification file map is invalid")
        remote_path = _safe_relative(Path(remote_run), relative, "remote qualification")
        actual_remote = _remote_sha256(transport, host, str(remote_path), deadline, clock, sleeper)
        if actual_remote != expected:
            raise ControllerError("remote qualification file hash mismatch: {}".format(relative))
        local_path = local_control / relative
        local_path.parent.mkdir(parents=True, exist_ok=True)
        _rsync(transport, "{}:{}".format(host, remote_path), str(local_path), deadline, clock, sleeper)
        if sha256_file(local_path) != expected:
            raise ControllerError("returned qualification file hash mismatch: {}".format(relative))
        payloads[relative] = _read_json_bytes(local_path.read_bytes(), relative)
        if heartbeat is not None:
            heartbeat("qualification")
    finals = [(relative, value) for relative, value in payloads.items()
              if value.get("status") == "outer_runtime_qualified"]
    if len(finals) != 1:
        raise ControllerError("runtime qualification requires exactly one final receipt")
    final_relative, final = finals[0]
    canary_relative, profile_relative = final.get("canary"), final.get("profile")
    if (not isinstance(canary_relative, str) or not isinstance(profile_relative, str)
            or set(files) != {final_relative, canary_relative, profile_relative}):
        raise ControllerError("runtime qualification final file binding is invalid")
    canary, profile = payloads.get(canary_relative), payloads.get(profile_relative)
    if canary is None or profile is None:
        raise ControllerError("runtime qualification canary/profile files are missing")
    fingerprint = final.get("runtime_fingerprint")
    if not isinstance(fingerprint, str) or fingerprint == "":
        raise ControllerError("runtime qualification fingerprint is missing")
    if any(value.get("runtime_fingerprint") != fingerprint for value in (canary, profile)):
        raise ControllerError("runtime qualification fingerprint mismatch")
    if any(value.get("plan_digest") != expected_digest for value in (final, canary, profile)):
        raise ControllerError("runtime qualification plan digest mismatch")
    sources = plan.get("sources")
    if not isinstance(sources, Mapping) or any(value.get("code_hashes") != sources for value in (canary, profile)):
        raise ControllerError("runtime qualification source hash mismatch")
    if canary.get("status") != "goal052_outer_canary_valid" or profile.get("status") != "goal052_outer_profile_valid":
        raise ControllerError("runtime qualification canary/profile status invalid")
    if any(value.get("outer_response_rows_read") != 0 for value in (final, canary, profile)):
        raise ControllerError("runtime qualification response firewall failed")
    final_files = final.get("files")
    expected_final_files = {canary_relative: files[canary_relative], profile_relative: files[profile_relative]}
    if final_files != expected_final_files:
        raise ControllerError("runtime qualification final hash binding is invalid")
    try:
        qualified_workers = int(final["qualified_workers"])
        profile_workers = int(profile["qualified_workers"])
        profile_peak = int(profile["peak_rss_bytes"])
    except (KeyError, TypeError, ValueError) as error:
        raise ControllerError("runtime qualification resource fields are invalid") from error
    if qualified_workers < 1 or profile_workers < 1 or profile_peak <= 0:
        raise ControllerError("runtime qualification resource fields are non-positive")
    return {"files": dict(files), "final": final, "canary": canary, "profile": profile,
            "fingerprint": fingerprint, "qualified_workers": qualified_workers,
            "profile_peak_bytes": profile_peak}


def _select_workers(qualified_workers: int, profile_peak_bytes: int,
                    available_ram_bytes: int) -> Tuple[int, int]:
    reserve = int(MEMORY_RESERVE_GIB * 1024 ** 3)
    allowance = int(PROFILE_MULTIPLIER * profile_peak_bytes)
    capacity = (available_ram_bytes - reserve) // max(allowance, 1)
    selected = min(MAX_WORKERS, qualified_workers, capacity)
    if selected < 1:
        raise ControllerError("current RAM cannot support one profiled worker with reserve")
    return int(selected), int(capacity)


def _parse_mem_available(text: str) -> int:
    for line in text.splitlines():
        fields = line.split()
        if fields:
            try:
                value = int(float(fields[0]))
            except ValueError:
                continue
            if value > 0:
                return value
    raise ControllerError("remote MemAvailable query returned no positive bytes")


def _remote_path(root: str, relative: str) -> str:
    return str(Path(root) / relative)


def _thread_exports() -> str:
    return " ".join("{}=1".format(name) for name in THREAD_VARS)


def _launch_command(remote_root: str, remote_run: str, workers: int,
                    production_hours: float, attempt: str,
                    restart_from: Optional[str] = None) -> str:
    python = str(Path(remote_root) / ".venv/bin/python")
    supervisor = str(Path(remote_root) / SUPERVISOR_RELATIVE)
    log = str(Path(remote_run) / "production-supervisor-{}.log".format(attempt))
    argv = [python, supervisor, "--root", remote_root, "--run", remote_run,
            "--python", python, "--workers", str(workers),
            "--max-hours", str(production_hours), "--attempt", attempt]
    if restart_from is not None:
        argv.extend(["--recover-stage-logging", "--restart-from", restart_from])
    rendered = " ".join(shlex.quote(item) for item in argv)
    return "export {}; cd {} || exit 1; nohup {} > {} 2>&1 < /dev/null & printf '%s\\n' \"$!\"".format(
        _thread_exports(), shlex.quote(remote_root), rendered, shlex.quote(log))


def _command_string(remote_root: str, relative_script: str, args: Sequence[str]) -> str:
    executable = str(Path(remote_root) / ".venv/bin/python")
    script = str(Path(remote_root) / relative_script)
    return " ".join(shlex.quote(item) for item in [executable, script] + list(args))


def _is_remote_file(transport: Any, host: str, path: str, deadline: float,
                    clock: Callable[[], float], sleeper: Callable[[float], None]) -> bool:
    for attempt in range(2):
        try:
            result = transport.ssh(host, "test -e {}".format(shlex.quote(path)),
                                   min(SSH_TIMEOUT_SECONDS, _remaining(deadline, clock)))
            break
        except TransportTimeout:
            if attempt:
                raise
            sleeper(min(1.0, _remaining(deadline, clock)))
    if _returncode(result) == 0:
        return True
    if _returncode(result) == 1:
        return False
    raise ControllerError("remote existence check failed: {}".format(_stderr(result).strip()))


def _require_response_absent(transport: Any, host: str, remote_root: str,
                             remote_run: str, response_relative: str,
                             deadline: float, clock: Callable[[], float],
                             sleeper: Callable[[float], None]) -> None:
    paths = (response_relative, "response-access.json", "response-access-success.json")
    for relative in paths:
        path = _remote_path(remote_root if relative == response_relative else remote_run, relative)
        if _is_remote_file(transport, host, path, deadline, clock, sleeper):
            raise ControllerError("remote response access already exists: {}".format(path))
    # The native loader may add a suffixed response-access receipt.  Check the
    # directory pattern directly so a stale receipt cannot bypass the firewall.
    find_command = "find {} -maxdepth 1 -type f \\( -name 'response-access*.json' -o -name 'scoring-failure.json' \\) -print -quit".format(
        shlex.quote(remote_run))
    output = _ssh_bytes(transport, host, find_command, deadline, clock, retries=1, sleeper=sleeper).strip()
    if output:
        raise ControllerError("remote response access receipt already exists: {}".format(
            output.decode("utf-8", errors="replace")))


def _remote_process_alive(transport: Any, host: str, pid: int, deadline: float,
                          clock: Callable[[], float]) -> bool:
    result = transport.ssh(host, "kill -0 {}".format(int(pid)),
                           min(SSH_TIMEOUT_SECONDS, _remaining(deadline, clock)))
    if _returncode(result) == 0:
        return True
    if _returncode(result) == 1:
        return False
    raise ControllerError("remote process probe failed: {}".format(_stderr(result).strip()))


def _remote_process_group_alive(transport: Any, host: str, pid: int, deadline: float,
                                clock: Callable[[], float]) -> bool:
    result = transport.ssh(host, "kill -0 -- -{}".format(int(pid)),
                           min(SSH_TIMEOUT_SECONDS, _remaining(deadline, clock)))
    if _returncode(result) == 0:
        return True
    if _returncode(result) == 1:
        return False
    raise ControllerError("remote process-group probe failed: {}".format(_stderr(result).strip()))


def _kill_remote_process_group(transport: Any, host: str, pid: int,
                               clock: Callable[[], float], sleeper: Callable[[float], None]) -> None:
    """Signal one detached group, then force it after a bounded 60-second grace."""
    cleanup_deadline = clock() + 60.0
    result = transport.ssh(host, "kill -TERM -- -{} 2>/dev/null || true".format(pid),
                           SSH_TIMEOUT_SECONDS)
    if _returncode(result) != 0:
        raise ControllerError("remote stage termination command failed")
    while clock() < cleanup_deadline:
        try:
            if not _remote_process_group_alive(transport, host, pid, cleanup_deadline, clock):
                return
        except Exception:
            break
        sleeper(min(1.0, max(0.0, cleanup_deadline - clock())))
    transport.ssh(host, "kill -KILL -- -{} 2>/dev/null || true".format(pid),
                  SSH_TIMEOUT_SECONDS)


def _detached_stage_command(stage: str, command: str, remote_stage_dir: str,
                            remote_log: str, remote_status: str, cap_seconds: float) -> str:
    # The wrapper writes a receipt even when the scientific command fails.  Its
    # process group is created by setsid and is the only group this controller
    # ever signals.
    receipt_format = shlex.quote(
        '{"status":"complete","stage":"%s","pid":%s,"return_code":%s}\\n')
    script = (
        "rc=0; timeout --signal=TERM --kill-after=60s {} sh -c {} > {} 2>&1 || rc=$?; "
        "printf {} {} \"$$\" \"$rc\" > {}.tmp; "
        "mv -f {}.tmp {}; exit $rc"
    ).format(cap_seconds, shlex.quote(command), shlex.quote(remote_log), receipt_format,
             shlex.quote(stage), shlex.quote(remote_status), shlex.quote(remote_status),
             shlex.quote(remote_status))
    # Keep the directory setup outside the backgrounded command list.  With
    # ``mkdir && command &`` POSIX shells return the list subshell's PID;
    # that process exits immediately and is not the owned stage leader.
    return "mkdir -p {} || exit 1; nohup setsid sh -c {} </dev/null >/dev/null 2>{} & printf '%s\\n' \"$!\"".format(
        shlex.quote(remote_stage_dir), shlex.quote(script), shlex.quote(remote_log))


def _launch_detached_stage(control: Path, stage: str, command: str,
                           remote_stage_dir: str, remote_log: str, remote_status: str,
                           cap_seconds: float, transport: Any, host: str, deadline: float,
                           clock: Callable[[], float]) -> Tuple[int, Dict[str, Any]]:
    marker = control / (stage + "-launch.json")
    if marker.exists():
        raise ControllerError("{} launch marker already exists".format(stage))
    launch_command = _detached_stage_command(stage, command, remote_stage_dir, remote_log, remote_status, cap_seconds)
    marker_data = {"stage": stage, "command": command, "launch_command": launch_command,
                   "remote_stage_dir": remote_stage_dir, "remote_log": remote_log,
                   "remote_status": remote_status, "cap_seconds": cap_seconds, "started_utc": utc_now()}
    _immutable_json(marker, marker_data)
    # This SSH launch is intentionally not retried: a timeout leaves the
    # immutable marker proving that the remote outcome is uncertain.
    result = transport.ssh(host, launch_command, min(SSH_TIMEOUT_SECONDS, _remaining(deadline, clock)))
    if _returncode(result) != 0:
        raise ControllerError("{} launch failed: {}".format(stage, _stderr(result).strip()))
    output = _stdout(result).decode("utf-8").strip().splitlines()
    try:
        pid = int(output[-1])
    except (IndexError, ValueError) as error:
        raise ControllerError("{} launch did not return a PID".format(stage)) from error
    marker_data.update({"pid": pid, "launched_utc": utc_now()})
    _immutable_json(control / (stage + "-process.json"), marker_data)
    return pid, marker_data


def _wait_detached_stage(control: Path, stage: str, pid: int, remote_status: str,
                         transport: Any, host: str, stage_deadline: float,
                         overall_deadline: float, clock: Callable[[], float],
                         sleeper: Callable[[float], None]) -> Dict[str, Any]:
    while True:
        deadline = min(stage_deadline, overall_deadline)
        if clock() >= deadline:
            _kill_remote_process_group(transport, host, pid, clock, sleeper)
            raise ControllerError("{} detached stage exceeded its bounded cap".format(stage))
        try:
            polled = _poll_json(transport, host, remote_status, deadline, clock)
            if polled is not None:
                receipt, raw = polled
                if receipt.get("status") != "complete" or receipt.get("pid") != pid:
                    raise ControllerError("{} detached receipt identity is invalid".format(stage))
                if receipt.get("return_code") != 0:
                    raise ControllerError("{} detached stage failed".format(stage))
                receipt["remote_status_sha256"] = sha256_bytes(raw)
                return receipt
            if not _remote_process_group_alive(transport, host, pid, deadline, clock):
                raise ControllerError("{} exited without a completion receipt".format(stage))
            _heartbeat(control, stage + "_wait")
            sleeper(min(POLL_SECONDS, _remaining(deadline, clock)))
        except ControllerError:
            try:
                _kill_remote_process_group(transport, host, pid, clock, sleeper)
            except Exception:
                pass
            raise


def _write_event(control: Path, status: Dict[str, Any], event: Mapping[str, Any]) -> None:
    status.setdefault("events", []).append(dict(event))
    status["heartbeat_utc"] = utc_now()
    _atomic_json(control / "status.json", status)
    _atomic_json(control / "heartbeat.json", {
        "utc": status["heartbeat_utc"], "stage": event.get("stage", "unknown"),
    })


def _heartbeat(control: Path, stage: str) -> None:
    _atomic_json(control / "heartbeat.json", {"utc": utc_now(), "stage": stage})


def _wait_for_runtime(transport: Any, host: str, remote_run: str,
                      deadline: float, clock: Callable[[], float], sleeper: Callable[[float], None],
                      heartbeat: Optional[Callable[[str], None]] = None) -> Tuple[Dict[str, Any], bytes]:
    remote_path = _remote_path(remote_run, RUNTIME_CONTROL)
    while True:
        polled = _poll_json(transport, host, remote_path, deadline, clock)
        if polled is not None:
            runtime, raw = polled
            if runtime.get("status") == "failed":
                raise ControllerError("runtime qualification failed; no production replay permitted")
            if runtime.get("status") == "runtime_qualification_completed":
                return runtime, raw
            if runtime.get("status") != "running":
                raise ControllerError("invalid runtime qualification status: {}".format(runtime.get("status")))
        if heartbeat is not None:
            heartbeat("runtime_wait")
        sleeper(min(POLL_SECONDS, _remaining(deadline, clock)))


def _wait_for_production(transport: Any, host: str, remote_run: str,
                         expected_digest: str, plan_sha: str,
                         deadline: float, clock: Callable[[], float], sleeper: Callable[[float], None],
                         heartbeat: Optional[Callable[[str], None]] = None,
                         expected_attempt: str = "001",
                         expected_stage_helper_sha: Optional[str] = None) -> Tuple[Dict[str, Any], bytes]:
    remote_path = _remote_path(remote_run, PRODUCTION_CONTROL.format(expected_attempt))
    while True:
        polled = _poll_json(transport, host, remote_path, deadline, clock)
        if polled is not None:
            complete, raw = polled
            if complete.get("status") == "failed":
                raise ControllerError("remote production failed; no automatic replay permitted")
            if complete.get("status") == "predictions_closed_verified":
                if complete.get("success") is not True:
                    raise ControllerError("remote production completion lacks success=true")
                if (complete.get("plan_digest") is not None
                        and complete.get("plan_digest") != expected_digest):
                    raise ControllerError("remote production plan digest mismatch")
                if complete.get("plan_sha256") != plan_sha:
                    raise ControllerError("remote production plan SHA mismatch")
                if expected_stage_helper_sha is not None and complete.get("recovery_helper_sha256") != expected_stage_helper_sha:
                    raise ControllerError("remote production stage-helper source SHA mismatch")
                commands = complete.get("commands")
                if (not isinstance(commands, list) or len(commands) != len(STAGES) or any(
                    not isinstance(item, Mapping) or item.get("stage") != STAGES[index]
                    or item.get("status") != "succeeded" or item.get("return_code") != 0
                    for index, item in enumerate(commands)
                )):
                    raise ControllerError("remote production stage receipts are incomplete")
                closure = complete.get("closure", {})
                if not isinstance(closure, Mapping) or closure.get("exists") is not True:
                    raise ControllerError("remote production completion lacks closure")
                return complete, raw
            if complete.get("status") != "running":
                raise ControllerError("invalid remote production status: {}".format(complete.get("status")))
        if heartbeat is not None:
            heartbeat("production_wait")
        sleeper(min(POLL_SECONDS, _remaining(deadline, clock)))


def _reconcile_production_launch(transport: Any, host: str, remote_control: str,
                                 remote_run: str, expected_plan_sha: str,
                                 expected_supervisor_sha: str, expected_workers: int,
                                 expected_max_hours: float, expected_attempt: str,
                                 deadline: float, clock: Callable[[], float],
                                 sleeper: Callable[[float], None],
                                 expected_stage_helper_sha: Optional[str] = None) -> Optional[int]:
    """Recover an uncertain SSH launch from the supervisor's immutable control."""
    manifest_path = _remote_path(remote_control, "manifest.json")
    if not _is_remote_file(transport, host, manifest_path, deadline, clock, sleeper):
        return None
    manifest, _ = _ssh_json(transport, host, manifest_path, deadline, clock, retries=1, sleeper=sleeper)
    args = manifest.get("args", {})
    try:
        workers = int(args.get("workers", -1)) if isinstance(args, Mapping) else -1
        max_hours = float(args.get("max_hours", -1)) if isinstance(args, Mapping) else -1.0
    except (TypeError, ValueError):
        workers, max_hours = -1, -1.0
    if (manifest.get("schema_version") != "goal052-outer-production-control-v1"
            or manifest.get("attempt") != expected_attempt
            or manifest.get("plan_sha256") != expected_plan_sha
            or manifest.get("source_supervisor_sha256") != expected_supervisor_sha
            or (expected_stage_helper_sha is not None
                and manifest.get("recovery_helper_sha256") != expected_stage_helper_sha)
            or not isinstance(args, Mapping)
            or workers != expected_workers
            or max_hours != float(expected_max_hours)
            or str(args.get("run")) != remote_run):
        raise ControllerError("uncertain production launch manifest identity mismatch")
    for relative in ("heartbeat.json", "status.json"):
        path = _remote_path(remote_control, relative)
        if not _is_remote_file(transport, host, path, deadline, clock, sleeper):
            continue
        receipt, _ = _ssh_json(transport, host, path, deadline, clock, retries=1, sleeper=sleeper)
        pid = receipt.get("pid")
        if isinstance(pid, int) and pid > 0:
            return pid
        for stage in receipt.get("commands", ()) if isinstance(receipt.get("commands"), list) else ():
            if isinstance(stage, Mapping) and isinstance(stage.get("pid"), int) and stage["pid"] > 0:
                return int(stage["pid"])
    return None


def _remote_process_table(transport: Any, host: str, deadline: float,
                          clock: Callable[[], float], sleeper: Callable[[float], None]) -> str:
    """Return a command-bearing process table for identity-safe restart checks."""
    return _ssh_text(transport, host, "ps -eo pid=,pgid=,args=", deadline, clock,
                     retries=1, sleeper=sleeper)


def _require_prior_processes_dead(transport: Any, host: str,
                                  process_records: Sequence[Mapping[str, Any]],
                                  deadline: float, clock: Callable[[], float],
                                  sleeper: Callable[[float], None]) -> None:
    """Fail closed on an active or ambiguously reused prior PID/PGID.

    A numeric ``kill -0`` result is insufficient here: a recycled PID must not
    be mistaken for the old production process.  The command-bearing process
    table binds both PID and process group to the recorded command identity.
    """
    table = _remote_process_table(transport, host, deadline, clock, sleeper)
    rows = []
    for line in table.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) < 2:
            continue
        try:
            pid, pgid = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        rows.append((pid, pgid, fields[2] if len(fields) == 3 else ""))
    for record in process_records:
        try:
            pid = int(record.get("pid"))
            pgid = int(record.get("process_group", pid))
        except (TypeError, ValueError):
            raise ControllerError("prior process identity is malformed")
        if pid <= 0 or pgid <= 0:
            raise ControllerError("prior process identity is non-positive")
        expected = record.get("command")
        expected_text = " ".join(str(part) for part in expected) if isinstance(expected, list) else str(expected or "")
        for observed_pid, observed_pgid, observed_args in rows:
            if observed_pid != pid and observed_pgid != pgid:
                continue
            # A same-PID or same-PGID process with a different command is a
            # possible PID reuse or group collision, so it is never ignored.
            if expected_text and not all(token in observed_args for token in (
                    "goal052_outer_supervise.py" if "supervise" in expected_text else "dsdm_phase1.goal052_outer" ,)):
                raise ControllerError("prior process identity is ambiguous or PID was reused")
            raise ControllerError("prior production process or group is still active")


def _hash_remote_file(transport: Any, host: str, path: str, deadline: float,
                      clock: Callable[[], float], sleeper: Callable[[float], None]) -> str:
    if not _is_remote_file(transport, host, path, deadline, clock, sleeper):
        raise ControllerError("prior immutable file is missing: {}".format(path))
    return _remote_sha256(transport, host, path, deadline, clock, sleeper)


def _validate_manual_restart(transport: Any, host: str, root: Path, run: Path,
                             remote_root: str, remote_run: str,
                             metadata: Mapping[str, Any], expected_digest: str,
                             plan_sha: str, expected_supervisor_sha: str,
                             expected_stage_helper_sha: str, deadline: float,
                             clock: Callable[[], float], sleeper: Callable[[float], None]) -> Dict[str, Any]:
    """Validate the exact failed attempt that a manual 002 restart may follow."""
    prior = "001"
    prior_control = run / "continuation-control-001"
    required_local = [prior_control / name for name in ("manifest.json", "complete.json", "status.json",
                                                         "production-process.json")]
    if any(not path.is_file() for path in required_local):
        raise ControllerError("manual restart requires complete local attempt 001 evidence")
    local_manifest_raw = (prior_control / "manifest.json").read_bytes()
    local_complete_raw = (prior_control / "complete.json").read_bytes()
    local_status_raw = (prior_control / "status.json").read_bytes()
    prior_manifest = _read_json_bytes(local_manifest_raw, str(required_local[0]))
    prior_complete = _read_json_bytes(local_complete_raw, str(required_local[1]))
    prior_status = _read_json_bytes(local_status_raw, str(required_local[2]))
    prior_manifest_sha = sha256_bytes(local_manifest_raw)
    if (prior_manifest.get("attempt") != prior or prior_complete.get("attempt") != prior
            or prior_status.get("attempt") != prior
            or prior_manifest.get("plan_sha256") != plan_sha
            or prior_complete.get("schema_version") != "goal052-outer-continuation-complete-v1"
            or prior_complete.get("status") != "failed" or prior_complete.get("success") is not False
            or prior_status.get("status") != "failed"
            or ("manifest_sha256" in prior_complete and prior_complete.get("manifest_sha256") != prior_manifest_sha)
            or ("remote_run" in prior_manifest and prior_manifest.get("remote_run") != remote_run)
            or ("remote_root" in prior_manifest and prior_manifest.get("remote_root") != remote_root)):
        raise ControllerError("prior continuation attempt 001 identity/status is invalid")
    failure = prior_complete.get("failure", {})
    reason = str(failure.get("reason", "")) if isinstance(failure, Mapping) else ""
    if "remote production failed" not in reason:
        raise ControllerError("prior continuation was not the authorized remote-production failure")
    prior_remote_sources = prior_complete.get("remote_source_hashes", {})
    if not isinstance(prior_remote_sources, Mapping):
        prior_remote_sources = {}
    prior_supervisor_sha = prior_remote_sources.get(
        _remote_path(remote_root, SUPERVISOR_RELATIVE))
    if not isinstance(prior_supervisor_sha, str):
        prior_sources = prior_manifest.get("source_hashes", {})
        prior_supervisor_sha = prior_sources.get(SUPERVISOR_RELATIVE) if isinstance(prior_sources, Mapping) else None
    if not isinstance(prior_supervisor_sha, str) or len(prior_supervisor_sha) != 64:
        raise ControllerError("prior supervisor source SHA is missing")
    local_production_manifest = _read_json_bytes(
        (run / "production-control-001" / "manifest.json").read_bytes(),
        str(run / "production-control-001" / "manifest.json"))
    local_production_complete = _read_json_bytes(
        (run / "production-control-001" / "complete.json").read_bytes(),
        str(run / "production-control-001" / "complete.json"))
    if (local_production_manifest.get("source_supervisor_sha256") not in (None, prior_supervisor_sha)
            or local_production_complete.get("source_supervisor_sha256") not in (None, prior_supervisor_sha)):
        raise ControllerError("local prior production supervisor source SHA drift")
    local_manifest_sources = prior_manifest.get("source_hashes", {})
    if (isinstance(local_manifest_sources, Mapping)
            and local_manifest_sources.get(SUPERVISOR_RELATIVE) not in (None, prior_supervisor_sha)):
        raise ControllerError("local prior continuation supervisor source SHA drift")

    remote_control = _remote_path(remote_root, "continuation-control-001")
    remote_production = _remote_path(remote_run, "production-control-001")
    remote_complete_path = _remote_path(remote_production, "complete.json")
    remote_manifest_path = _remote_path(remote_production, "manifest.json")
    remote_status_path = _remote_path(remote_production, "status.json")
    remote_complete, remote_complete_raw = _ssh_json(transport, host, remote_complete_path, deadline, clock,
                                                     retries=1, sleeper=sleeper)
    remote_manifest, remote_manifest_raw = _ssh_json(transport, host, remote_manifest_path, deadline, clock,
                                                     retries=1, sleeper=sleeper)
    remote_status, remote_status_raw = _ssh_json(transport, host, remote_status_path, deadline, clock,
                                                  retries=1, sleeper=sleeper)
    if (remote_complete.get("attempt") != prior or remote_complete.get("status") != "failed"
            or remote_complete.get("success") is not False
            or remote_complete.get("plan_sha256") != plan_sha
            or remote_complete.get("source_supervisor_sha256") != prior_supervisor_sha
            or remote_manifest.get("attempt") != prior
            or remote_manifest.get("plan_sha256") != plan_sha
            or remote_manifest.get("source_supervisor_sha256") != prior_supervisor_sha
            or ("args" in remote_manifest and isinstance(remote_manifest.get("args"), Mapping)
                and remote_manifest["args"].get("run") not in (None, remote_run))
            or ("args" in remote_complete and isinstance(remote_complete.get("args"), Mapping)
                and remote_complete["args"].get("run") not in (None, remote_run))
            or remote_status.get("status") != "failed"):
        raise ControllerError("prior production attempt 001 identity/status is invalid")
    commands = remote_complete.get("commands")
    if not isinstance(commands, list) or len(commands) != 1:
        raise ControllerError("prior production did not terminate at exactly one stage")
    q_stage = commands[0]
    if (not isinstance(q_stage, Mapping) or q_stage.get("stage") != "q"
            or q_stage.get("status") != "failed" or int(q_stage.get("return_code", 0)) == 0):
        raise ControllerError("prior production q-stage terminal failure is invalid")
    closure = remote_complete.get("closure", {})
    if remote_complete.get("closure_sha256") is not None or (isinstance(closure, Mapping) and closure.get("exists") is True):
        raise ControllerError("prior production already has a closure")
    q_log = q_stage.get("log")
    if not isinstance(q_log, str) or os.path.isabs(q_log) or not q_log.endswith(".log"):
        raise ControllerError("prior q-stage log binding is missing")
    q_log_path = _remote_path(remote_production, q_log)
    q_log_sha = _hash_remote_file(transport, host, q_log_path, deadline, clock, sleeper)
    q_log_raw = _ssh_bytes(transport, host, "cat -- {}".format(shlex.quote(q_log_path)),
                           deadline, clock, retries=1, sleeper=sleeper)
    q_log_text = q_log_raw.decode("utf-8", errors="replace")
    if ("TypeError: event() got multiple values for argument 'stage'" not in q_log_text
            or 'event("stage_complete", **result)' not in q_log_text
            or 'goal052_outer.py", line 331, in run_stage' not in q_log_text):
        raise ControllerError("prior q-stage log is not the approved terminal logger failure")
    prior_process = _read_json_bytes((prior_control / "production-process.json").read_bytes(),
                                     str(prior_control / "production-process.json"))
    records = []
    if isinstance(prior_process.get("remote_pid"), int):
        records.append({"pid": prior_process["remote_pid"], "process_group": prior_process.get("remote_pid"),
                        "command": prior_process.get("command", "goal052_outer_supervise.py")})
    if isinstance(q_stage.get("pid"), int):
        records.append({"pid": q_stage["pid"], "process_group": q_stage.get("process_group", q_stage["pid"]),
                        "command": q_stage.get("command", ["dsdm_phase1.goal052_outer", "run", "--stage", "q"])})
    if not records:
        raise ControllerError("prior process identity is missing")
    _require_prior_processes_dead(transport, host, records, deadline, clock, sleeper)
    # A response-access receipt, score failure, or canonical closure in either
    # namespace makes a restart ambiguous and therefore stops before launch.
    _require_response_absent(transport, host, remote_root, remote_run,
                             metadata["response_relative"], deadline, clock, sleeper)
    for relative in ("closure.json", "scores.json", "outer-report.md"):
        if (run / relative).is_file():
            raise ControllerError("prior local production artifact already exists: {}".format(relative))
        if _is_remote_file(transport, host, _remote_path(remote_run, relative), deadline, clock, sleeper):
            raise ControllerError("prior production artifact already exists: {}".format(relative))
    for path in run.glob("response-access*.json"):
        raise ControllerError("prior local response access receipt already exists: {}".format(path))
    for path in (run / "scoring-failure.json",):
        if path.is_file():
            raise ControllerError("prior local scoring failure receipt already exists: {}".format(path))
    if _is_remote_file(transport, host, _remote_path(remote_root, "continuation-control-002"), deadline, clock, sleeper):
        raise ControllerError("new continuation control already exists")
    if _is_remote_file(transport, host, _remote_path(remote_run, "production-control-002"), deadline, clock, sleeper):
        raise ControllerError("new production control already exists")
    return {
        "attempt": prior, "plan_sha256": plan_sha,
        "continuation_manifest_sha256": sha256_bytes(local_manifest_raw),
        "continuation_complete_sha256": sha256_bytes(local_complete_raw),
        "continuation_status_sha256": sha256_bytes(local_status_raw),
        "production_manifest_sha256": sha256_bytes(remote_manifest_raw),
        "production_complete_sha256": sha256_bytes(remote_complete_raw),
        "production_status_sha256": sha256_bytes(remote_status_raw),
        "q_terminal_log": q_log,
        "q_terminal_log_sha256": q_log_sha,
        "source_supervisor_sha256": expected_supervisor_sha,
        "prior_source_supervisor_sha256": prior_supervisor_sha,
        "source_stage_helper_sha256": expected_stage_helper_sha,
        "remote_control": remote_control,
    }


def _local_prior_restart_evidence(run: Path) -> Dict[str, Any]:
    """Hash the preserved local 001 receipts before creating the 002 manifest."""
    prior = run / "continuation-control-001"
    production = run / "production-control-001"
    paths = {
        "continuation_manifest_sha256": prior / "manifest.json",
        "continuation_complete_sha256": prior / "complete.json",
        "continuation_status_sha256": prior / "status.json",
        "production_manifest_sha256": production / "manifest.json",
        "production_complete_sha256": production / "complete.json",
        "production_status_sha256": production / "status.json",
        "q_terminal_log_sha256": production / "stage-01-q.log",
    }
    if any(not path.is_file() for path in paths.values()):
        raise ControllerError("manual restart requires preserved local 001 manifests, receipts, and q log")
    values = {key: sha256_file(path) for key, path in paths.items()}
    values["q_terminal_log"] = "stage-01-q.log"
    return values


def _response_receipt(metadata: Mapping[str, Any], audit_sha: str, remote_path: str,
                      actual_sha: str) -> Dict[str, Any]:
    return {
        "schema_version": "goal052-outer-response-transfer-v1",
        "status": "transferred_after_closure_and_audit",
        "created_utc": utc_now(),
        "source_relative": metadata["response_relative"],
        "remote_path": remote_path,
        "expected_sha256": metadata["response_sha256"],
        "actual_sha256": actual_sha,
        "size_bytes": metadata["response_size"],
        "plan_digest": metadata["plan"]["plan_digest"],
        "plan_sha256": metadata["plan_sha256"],
        "config_sha256": metadata["config_sha256"],
        "completion_sha256": metadata["completion_sha256"],
        "independent_audit_sha256": audit_sha,
        "response_bytes_opened_before_audit": False,
    }


def _collect_returned_files(run: Path, closure: Mapping[str, Any], attempt: str = "001") -> Sequence[Path]:
    required = ["plan.json", "domain.npz", "closure.json", "scores.json", "outer-report.md",
                "response-access.json", "response-access-success.json",
                "production-supervisor-{}.log".format(attempt)]
    paths = [run / rel for rel in required]
    predictions = closure.get("predictions", {})
    if not isinstance(predictions, Mapping) or not predictions:
        raise ControllerError("returned closure has no prediction inventory")
    expected_predictions = set(str(value) for value in predictions.values())
    for relative in expected_predictions:
        if not relative.startswith("predictions/") or _safe_relative(run, relative, "prediction").parent != run / "predictions":
            raise ControllerError("returned prediction path is unsafe")
    prediction_dir = run / "predictions"
    observed_predictions = {str(path.relative_to(run)) for path in prediction_dir.glob("*.npz")}
    if observed_predictions != expected_predictions:
        raise ControllerError("returned prediction inventory mismatch")
    paths.extend(prediction_dir / Path(relative).name for relative in sorted(expected_predictions))
    # Runtime qualification receipts are retained under continuation-control;
    # the returned run payload contains only the production control receipts.
    for directory in (run / "production-control-{}".format(attempt),):
        if not directory.is_dir():
            raise ControllerError("returned control directory missing: {}".format(directory))
        paths.extend(path for path in sorted(directory.rglob("*")) if path.is_file())
    for path in paths:
        if not path.is_file():
            raise ControllerError("returned artifact missing: {}".format(path))
    return sorted(set(paths))


def _verify_remote_transfer(transport: Any, host: str, remote_run: str,
                            relative: str, local_path: Path, expected: Optional[str],
                            deadline: float, clock: Callable[[], float],
                            sleeper: Callable[[float], None]) -> str:
    remote_path = _remote_path(remote_run, relative)
    remote_sha = _remote_sha256(transport, host, remote_path, deadline, clock, sleeper)
    if expected is not None and remote_sha != expected:
        raise ControllerError("remote artifact hash differs from closure manifest: {}".format(relative))
    local_sha = sha256_file(local_path)
    if local_sha != remote_sha:
        raise ControllerError("returned artifact hash mismatch: {}".format(relative))
    return remote_sha


def _return_optional_receipts(transport: Any, host: str, remote_run: str,
                              local_run: Path, relatives: Sequence[str],
                              deadline: float, clock: Callable[[], float],
                              sleeper: Callable[[float], None]) -> Dict[str, str]:
    returned: Dict[str, str] = {}
    for relative in relatives:
        remote_path = _remote_path(remote_run, relative)
        if not _is_remote_file(transport, host, remote_path, deadline, clock, sleeper):
            continue
        local_path = local_run / relative
        local_path.parent.mkdir(parents=True, exist_ok=True)
        _rsync(transport, "{}:{}".format(host, remote_path), str(local_path), deadline, clock, sleeper)
        returned[relative] = _verify_remote_transfer(
            transport, host, remote_run, relative, local_path, None, deadline, clock, sleeper)
    return returned


def _return_artifacts(transport: Any, host: str, remote_root: str, remote_run: str,
                      remote_control: str, local_run: Path, local_control: Path,
                      closure: Mapping[str, Any], deadline: float,
                      clock: Callable[[], float], sleeper: Callable[[float], None],
                      attempt: str = "001") -> Dict[str, Any]:
    closure_files = closure.get("files")
    if not isinstance(closure_files, Mapping):
        raise ControllerError("closure remote SHA manifest is missing")
    selected = ["plan.json", "domain.npz", "closure.json", "scores.json", "outer-report.md",
                "response-access.json", "response-access-success.json",
                "production-supervisor-{}.log".format(attempt)]
    prediction_values = closure.get("predictions", {})
    if not isinstance(prediction_values, Mapping) or not prediction_values:
        raise ControllerError("returned closure has no prediction inventory")
    selected.extend(sorted(set(str(value) for value in prediction_values.values())))
    remote_manifest: Dict[str, str] = {}
    # plan/domain already exist locally; verify them against the remote closure
    # manifest without copying the potentially large domain array.
    for relative in ("plan.json", "domain.npz"):
        expected = closure_files.get(relative)
        if not isinstance(expected, str) or sha256_file(local_run / relative) != expected:
            raise ControllerError("local {} does not match remote closure manifest".format(relative))
        remote_manifest[relative] = expected
    for relative in selected:
        if relative in ("plan.json", "domain.npz"):
            continue
        _safe_relative(local_run, relative, "returned artifact")
        expected = closure_files.get(relative)
        source = "{}:{}".format(host, _remote_path(remote_run, relative))
        destination = str(local_run / relative)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        _rsync(transport, source, destination, deadline, clock, sleeper)
        remote_manifest[relative] = _verify_remote_transfer(
            transport, host, remote_run, relative, Path(destination),
            expected if isinstance(expected, str) else None, deadline, clock, sleeper)
    # Control receipts and detached-stage receipts are not part of closure.json,
    # so hash each returned file against the remote source after transfer.
    control_transfers = [
        ("production-control-{}/".format(attempt), remote_run, local_run / "production-control-{}".format(attempt)),
        ("audit/", remote_control, local_control / "remote-postproduction/audit"),
        ("score/", remote_control, local_control / "remote-postproduction/score"),
        ("report/", remote_control, local_control / "remote-postproduction/report"),
    ]
    for relative, base, destination in control_transfers:
        source = "{}:{}/".format(host, _remote_path(base, relative.rstrip("/")))
        destination.mkdir(parents=True, exist_ok=True)
        _rsync(transport, source, str(destination) + "/", deadline, clock, sleeper)
    response_transfer_remote = _remote_path(remote_control, "response-transfer.json")
    if _is_remote_file(transport, host, response_transfer_remote, deadline, clock, sleeper):
        (local_control / "remote-postproduction").mkdir(parents=True, exist_ok=True)
        _rsync(transport, "{}:{}".format(host, response_transfer_remote),
               str(local_control / "remote-postproduction/response-transfer.json"),
               deadline, clock, sleeper)
    for directory, remote_base in ((local_run / "production-control-{}".format(attempt), _remote_path(remote_run, "production-control-{}".format(attempt))),
                                   (local_control / "remote-postproduction", remote_control)):
        if not directory.is_dir():
            raise ControllerError("returned control directory missing: {}".format(directory))
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                relative = str(path.relative_to(local_run)) if directory == local_run / "production-control-{}".format(attempt) else "remote-postproduction/{}".format(path.relative_to(directory))
                remote_relative = str(path.relative_to(directory))
                remote_manifest[relative] = _verify_remote_transfer(
                    transport, host, remote_base, remote_relative, path, None,
                    deadline, clock, sleeper)
    response_transfer = local_control / "remote-postproduction/response-transfer.json"
    if response_transfer.is_file():
        remote_manifest["remote-postproduction/response-transfer.json"] = _verify_remote_transfer(
            transport, host, remote_control, "response-transfer.json", response_transfer, None,
            deadline, clock, sleeper)
    paths = _collect_returned_files(local_run, closure, attempt)
    manifest = {str(path.relative_to(local_run)): sha256_file(path) for path in paths}
    control_manifest = {}
    excluded_control_files = {"status.json", "heartbeat.json", "complete.json"}
    for path in sorted(local_control.rglob("*")):
        relative = str(path.relative_to(local_control))
        if path.is_file() and relative not in excluded_control_files:
            control_manifest["{}/{}".format(local_control.name, relative)] = sha256_file(path)
    _immutable_json(local_run / "returned-files.json", {
        "schema_version": "goal052-returned-files-v2", "files": manifest,
        "control_files": control_manifest, "remote_sha256": remote_manifest,
        "control_files_scope": "immutable_evidence_written_before_continuation_completion",
        "control_files_excluded": sorted(excluded_control_files),
    })
    manifest["returned-files.json"] = sha256_file(local_run / "returned-files.json")
    return {"files": manifest, "control_files": control_manifest, "remote_sha256": remote_manifest}


def continue_campaign(args: argparse.Namespace, transport: Optional[Any] = None,
                      sleeper: Callable[[float], None] = time.sleep,
                      clock: Callable[[], float] = time.monotonic) -> int:
    """Run one bounded continuation attempt; tests may inject transport."""
    _validate_args(args)
    transport = transport or SubprocessTransport()
    root = Path(args.root).resolve()
    run = _safe_relative(root, args.run_relative, "local run")
    if not run.is_dir():
        raise ControllerError("local run directory missing: {}".format(run))
    metadata = _load_local_metadata(root, run, args.expected_plan_digest)
    plan_source_hashes = _validate_local_sources(root, metadata["plan"])
    restart_from = getattr(args, "restart_from", None)
    source_paths = (SUPERVISOR_RELATIVE, AUDITOR_RELATIVE, REPORT_RELATIVE,
                    "scripts/goal052_outer_complete.py")
    if args.attempt == "002":
        source_paths = source_paths + (STAGE_HELPER_RELATIVE,)
    local_source_hashes = dict(plan_source_hashes)
    for relative in source_paths:
        local_source_hashes[relative] = sha256_file(
            _safe_relative(root, relative, "source"))
    overall_deadline = clock() + args.overall_hours * 3600.0
    lock_path = run / "continuation-control.lock"
    lock = lock_path.open("a+b")
    try:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as error:
            raise ControllerError("continuation run is already locked") from error
        existing_controls = sorted(run.glob("continuation-control-*"))
        allowed_prior = run / "continuation-control-001"
        if args.attempt == "001":
            if existing_controls:
                raise ControllerError("continuation attempt already exists: {}".format(existing_controls[0]))
        else:
            if any(path != allowed_prior for path in existing_controls):
                raise ControllerError("unknown or existing continuation control blocks manual restart")
            if not allowed_prior.is_dir():
                raise ControllerError("manual restart requires continuation-control-001")
        control = run / "continuation-control-{}".format(args.attempt)
        try:
            os.mkdir(str(control))
        except FileExistsError as error:
            raise ControllerError("continuation attempt already exists: {}".format(control)) from error
        started = utc_now()
        status: Dict[str, Any] = {"schema_version": "goal052-outer-continuation-status-v1", "status": "running",
                                  "attempt": args.attempt, "started_utc": started, "events": []}
        prior_restart = _local_prior_restart_evidence(run) if args.attempt == "002" else None
        manifest = {
            "schema_version": "goal052-outer-continuation-manifest-v1", "attempt": args.attempt,
            "started_utc": started, "args": {key: value for key, value in vars(args).items()
                                                if key not in {"root"}},
            "root": str(root), "local_run": str(run), "remote_root": args.remote_root,
            "remote_run": _remote_path(args.remote_root, args.run_relative),
            "expected_plan_digest": args.expected_plan_digest,
            "plan_sha256": metadata["plan_sha256"], "source_hashes": local_source_hashes,
            "response_metadata": {"relative": metadata["response_relative"],
                                   "expected_sha256": metadata["response_sha256"],
                                   "size_bytes": metadata["response_size"]},
            "response_transfer_gate": "closure_and_independent_audit_required",
        }
        if prior_restart is not None:
            manifest["manual_restart"] = {
                "restart_from": restart_from,
                "prior_evidence": prior_restart,
                "mode": "explicit_manual_restart",
            }
        _atomic_json(control / "status.json", status)
        _atomic_json(control / "heartbeat.json", {"utc": started, "stage": "preflight"})
        failure: Optional[Dict[str, Any]] = None
        final_data: Dict[str, Any] = {}
        remote_source_hashes: Dict[str, str] = {}
        remote_run = _remote_path(args.remote_root, args.run_relative)
        remote_control = _remote_path(args.remote_root, "continuation-control-{}".format(args.attempt))
        partial_returned: Dict[str, str] = {}
        try:
            remote_source_paths = source_paths[:3]
            if STAGE_HELPER_RELATIVE in source_paths:
                remote_source_paths = remote_source_paths + (STAGE_HELPER_RELATIVE,)
            remote_source_text = _ssh_text(
                transport, args.remote_host,
                "sha256sum -- {}".format(
                    " ".join(shlex.quote(_remote_path(args.remote_root, relative)) for relative in remote_source_paths)
                ), overall_deadline, clock, retries=1, sleeper=sleeper)
            remote_source_hashes = _parse_sha256sum(
                remote_source_text, [_remote_path(args.remote_root, relative) for relative in remote_source_paths])
            expected_remote_hashes = { _remote_path(args.remote_root, relative): local_source_hashes[relative]
                                       for relative in remote_source_paths }
            if remote_source_hashes != expected_remote_hashes:
                raise ControllerError("staged remote helper source hash mismatch")
            plan_remote_path = _remote_path(remote_run, "plan.json")
            remote_plan, remote_plan_raw = _ssh_json(transport, args.remote_host, plan_remote_path,
                                                     overall_deadline, clock, retries=1, sleeper=sleeper)
            remote_plan_sha = sha256_bytes(remote_plan_raw)
            if remote_plan.get("plan_digest") != args.expected_plan_digest or remote_plan_sha != metadata["plan_sha256"]:
                raise ControllerError("remote plan binding mismatch")
            expected_stage_helper_sha = None
            if args.attempt == "002":
                expected_stage_helper_sha = local_source_hashes[STAGE_HELPER_RELATIVE]
                prior_remote = _validate_manual_restart(
                    transport, args.remote_host, root, run, args.remote_root, remote_run,
                    metadata, args.expected_plan_digest, metadata["plan_sha256"],
                    remote_source_hashes[_remote_path(args.remote_root, SUPERVISOR_RELATIVE)],
                    expected_stage_helper_sha, overall_deadline, clock, sleeper)
                expected_prior = manifest["manual_restart"]["prior_evidence"]
                for key in ("continuation_manifest_sha256", "continuation_complete_sha256",
                            "continuation_status_sha256", "production_manifest_sha256",
                            "production_complete_sha256", "production_status_sha256",
                            "q_terminal_log_sha256"):
                    if prior_remote.get(key) != expected_prior.get(key):
                        raise ControllerError("prior immutable evidence changed before restart launch")
                manifest["manual_restart"]["remote_source_hashes"] = remote_source_hashes
            _immutable_json(control / "manifest.json", manifest)
            _write_event(control, status, {"stage": "preflight", "status": "succeeded",
                                           "remote_plan_sha256": remote_plan_sha,
                                           "restart_from": restart_from})
            _require_response_absent(transport, args.remote_host, args.remote_root, remote_run,
                                     metadata["response_relative"], overall_deadline, clock, sleeper)

            runtime, runtime_raw = _wait_for_runtime(transport, args.remote_host, remote_run,
                                                     overall_deadline, clock, sleeper,
                                                     lambda stage: _heartbeat(control, stage))
            qualification = _validate_runtime_complete(
                runtime, args.expected_plan_digest, metadata["plan_sha256"], runtime_raw, remote_plan,
                transport, args.remote_host, remote_run, control, overall_deadline, clock,
                sleeper, lambda stage: _heartbeat(control, stage))
            qualified_workers = qualification["qualified_workers"]
            profile_peak = qualification["profile_peak_bytes"]
            memory_text = _ssh_text(transport, args.remote_host,
                                    "awk '/^MemAvailable:/ {printf \"%.0f\\n\", $2 * 1024; exit}' /proc/meminfo",
                                    overall_deadline, clock, retries=1, sleeper=sleeper)
            available_ram = _parse_mem_available(memory_text)
            workers, ram_capacity = _select_workers(qualified_workers, profile_peak, available_ram)
            _write_event(control, status, {"stage": "qualification", "status": "succeeded",
                                           "qualified_workers": qualified_workers, "profile_peak_bytes": profile_peak,
                                           "available_ram_bytes": available_ram, "selected_workers": workers,
                                           "ram_capacity_workers": ram_capacity})
            remote_production_dir = _remote_path(remote_run, "production-control-{}".format(args.attempt))
            if _is_remote_file(transport, args.remote_host, remote_production_dir,
                               overall_deadline, clock, sleeper):
                raise ControllerError("remote production attempt already exists; refusing replay")
            launch = _launch_command(args.remote_root, remote_run, workers, args.production_hours, args.attempt,
                                     restart_from if args.attempt == "002" else None)
            _immutable_json(control / "production-launch.json", {
                "stage": "production", "command": launch, "workers": workers,
                "attempt": args.attempt, "max_hours": args.production_hours,
                "created_utc": utc_now(),
            })
            # This launch is deliberately not retried.  If SSH is uncertain,
            # the immutable marker and attempt directory prevent a replay.
            launch_reconciled = False
            launch_result = None
            try:
                launch_result = _ssh_text(transport, args.remote_host, launch, overall_deadline, clock,
                                          retries=0, sleeper=sleeper).strip()
            except TransportTimeout:
                expected_supervisor_sha = remote_source_hashes.get(
                    _remote_path(args.remote_root, SUPERVISOR_RELATIVE))
                remote_pid = _reconcile_production_launch(
                    transport, args.remote_host, remote_production_dir, remote_run,
                    metadata["plan_sha256"], expected_supervisor_sha, workers,
                    args.production_hours, args.attempt, overall_deadline, clock, sleeper,
                    expected_stage_helper_sha)
                if remote_pid is None:
                    raise ControllerError("remote production launch outcome is uncertain; no replay permitted")
                launch_reconciled = True
            else:
                try:
                    remote_pid = int(launch_result.splitlines()[-1])
                except (IndexError, ValueError) as error:
                    raise ControllerError("remote launch did not return a PID") from error
            _immutable_json(control / "production-process.json", {
                "stage": "production", "command": launch, "remote_pid": remote_pid,
                "attempt": args.attempt, "reconciled": launch_reconciled,
                "created_utc": utc_now(),
            })
            _write_event(control, status, {"stage": "production", "status": "launched",
                                           "remote_pid": remote_pid, "remote_command": launch,
                                           "workers": workers})
            complete, complete_raw = _wait_for_production(transport, args.remote_host, remote_run,
                                                           args.expected_plan_digest, metadata["plan_sha256"],
                                                           overall_deadline, clock, sleeper,
                                                           lambda stage: _heartbeat(control, stage),
                                                           args.attempt, expected_stage_helper_sha)
            closure_sha = complete.get("closure_sha256") or complete.get("closure", {}).get("sha256")
            if not isinstance(closure_sha, str):
                raise ControllerError("production completion lacks closure SHA")
            recorded_supervisor_sha = complete.get("source_supervisor_sha256")
            expected_supervisor_sha = remote_source_hashes.get(
                _remote_path(args.remote_root, SUPERVISOR_RELATIVE))
            if (not isinstance(recorded_supervisor_sha, str)
                    or recorded_supervisor_sha != expected_supervisor_sha):
                raise ControllerError("production supervisor source SHA mismatch")
            if expected_stage_helper_sha is not None and complete.get("recovery_helper_sha256") != expected_stage_helper_sha:
                raise ControllerError("production stage-helper source SHA mismatch")
            remote_closure_sha = _remote_sha256(transport, args.remote_host, _remote_path(remote_run, "closure.json"),
                                                overall_deadline, clock, sleeper)
            if remote_closure_sha != closure_sha:
                raise ControllerError("remote closure SHA does not match completion receipt")
            _write_event(control, status, {"stage": "production", "status": "predictions_closed_verified",
                                           "remote_pid": remote_pid, "complete_sha256": sha256_bytes(complete_raw),
                                           "closure_sha256": closure_sha,
                                           "commands": complete.get("commands", [])})
            remote_control = _remote_path(args.remote_root, "continuation-control-{}".format(args.attempt))
            audit_dir = _remote_path(remote_control, "audit")
            audit_output = _remote_path(audit_dir, "independent-audit.json")
            audit_log = _remote_path(audit_dir, "stage.log")
            audit_status = _remote_path(audit_dir, "stage.json")
            audit_args = ["--root", args.remote_root, "--run", remote_run, "--output", audit_output, "--quiet"]
            audit_command = "export {}; {}".format(
                _thread_exports(), _command_string(args.remote_root, AUDITOR_RELATIVE, audit_args))
            audit_cap = min(overall_deadline, clock() + AUDIT_TIMEOUT_SECONDS)
            audit_pid, audit_marker = _launch_detached_stage(
                control, "audit", audit_command, audit_dir, audit_log, audit_status,
                audit_cap - clock(), transport, args.remote_host, overall_deadline, clock)
            _write_event(control, status, {"stage": "audit", "status": "launched",
                                           "remote_pid": audit_pid, "command": audit_command})
            audit_result = _wait_detached_stage(
                control, "audit", audit_pid, audit_status, transport, args.remote_host,
                audit_cap, overall_deadline, clock, sleeper)
            audit, audit_raw = _ssh_json(transport, args.remote_host, audit_output,
                                         overall_deadline, clock, retries=1, sleeper=sleeper)
            audit_local = control / "independent-audit.json"
            _rsync(transport, "{}:{}".format(args.remote_host, audit_output),
                   str(audit_local), overall_deadline, clock, sleeper)
            if sha256_file(audit_local) != sha256_bytes(audit_raw):
                raise ControllerError("returned audit hash mismatch")
            provenance = audit.get("provenance", {})
            auditor = audit.get("auditor", {})
            if audit.get("status") != "pass" or provenance.get("plan_digest") != args.expected_plan_digest \
                    or provenance.get("plan_sha256") != metadata["plan_sha256"] \
                    or provenance.get("closure_sha256") != closure_sha \
                    or audit.get("auditor", {}).get("sha256") != remote_source_hashes.get(
                        _remote_path(args.remote_root, AUDITOR_RELATIVE)) \
                    or not isinstance(auditor, Mapping) \
                    or auditor.get("sha256") != remote_source_hashes.get(_remote_path(args.remote_root, AUDITOR_RELATIVE)) \
                    or audit.get("verified", {}).get("pre_score_absence") is not True \
                    or audit.get("verified", {}).get("pre_response_access_absence") is not True \
                    or audit.get("verified", {}).get("outer_response_content_opened") is not False:
                raise ControllerError("independent closure audit binding/firewall failed")
            audit_sha = sha256_bytes(audit_raw)
            _write_event(control, status, {"stage": "audit", "status": "pass", "audit_sha256": audit_sha,
                                           "command": audit_command, "remote_pid": audit_pid,
                                           "return_code": audit_result["return_code"]})

            # Rebind the canonical path immediately before any response bytes
            # are opened.  A local config/completion edit during production or
            # audit must fail closed rather than redirecting the transfer.
            fresh_metadata = _load_local_metadata(root, run, args.expected_plan_digest)
            for key in ("plan_sha256", "config_sha256", "completion_sha256",
                        "response_relative", "response_sha256", "response_size"):
                if fresh_metadata[key] != metadata[key]:
                    raise ControllerError("canonical metadata changed before response transfer: {}".format(key))

            response_path = metadata["response_path"]
            _require_response_absent(transport, args.remote_host, args.remote_root, remote_run,
                                     metadata["response_relative"], overall_deadline, clock, sleeper)
            try:
                response_size_after = response_path.stat().st_size
            except OSError as error:
                raise ControllerError("canonical response metadata disappeared after audit") from error
            if response_size_after != metadata["response_size"]:
                raise ControllerError("canonical response size changed before transfer")
            actual_response_sha = sha256_file(response_path)
            if actual_response_sha != metadata["response_sha256"]:
                raise ControllerError("canonical response SHA does not match frozen completion binding")
            remote_response_path = _remote_path(args.remote_root, metadata["response_relative"])
            _ssh_text(transport, args.remote_host, "mkdir -p {}".format(shlex.quote(str(Path(remote_response_path).parent))),
                      overall_deadline, clock, retries=1, sleeper=sleeper)
            _rsync(transport, str(response_path), "{}:{}".format(args.remote_host, remote_response_path),
                   overall_deadline, clock, sleeper)
            if _remote_sha256(transport, args.remote_host, remote_response_path, overall_deadline, clock, sleeper) != actual_response_sha:
                raise ControllerError("remote canonical response SHA mismatch after transfer")
            response_receipt = _response_receipt(metadata, audit_sha, remote_response_path, actual_response_sha)
            _immutable_json(control / "response-transfer.json", response_receipt)
            _rsync(transport, str(control / "response-transfer.json"),
                   "{}:{}".format(args.remote_host, _remote_path(remote_control, "response-transfer.json")),
                   overall_deadline, clock, sleeper)
            _write_event(control, status, {"stage": "response_transfer", "status": "pass",
                                           "response_sha256": actual_response_sha, "audit_sha256": audit_sha})

            score_args = ["score", "--root", args.remote_root, "--run", remote_run]
            score_command = "export {} PYTHONPATH={}; cd {} && {} -m dsdm_phase1.goal052_outer {}".format(
                _thread_exports(), shlex.quote(str(Path(args.remote_root) / "src")), shlex.quote(args.remote_root),
                shlex.quote(str(Path(args.remote_root) / ".venv/bin/python")),
                " ".join(shlex.quote(item) for item in score_args))
            score_dir = _remote_path(remote_control, "score")
            score_status = _remote_path(score_dir, "stage.json")
            score_log = _remote_path(score_dir, "stage.log")
            score_cap = min(overall_deadline, clock() + SCORE_TIMEOUT_SECONDS)
            score_pid, score_marker = _launch_detached_stage(
                control, "score", score_command, score_dir, score_log, score_status,
                score_cap - clock(), transport, args.remote_host, overall_deadline, clock)
            _write_event(control, status, {"stage": "score", "status": "launched",
                                           "remote_pid": score_pid, "command": score_command})
            score_result = _wait_detached_stage(
                control, "score", score_pid, score_status, transport, args.remote_host,
                score_cap, overall_deadline, clock, sleeper)
            partial_returned.update(_return_optional_receipts(
                transport, args.remote_host, remote_run, run,
                ("response-access.json", "response-access-success.json", "scoring-failure.json"),
                overall_deadline, clock, sleeper))
            report_args = [str(Path(remote_run) / "scores.json"), str(Path(remote_run) / "outer-report.md")]
            report_command = "export {}; {}".format(
                _thread_exports(), _command_string(args.remote_root, REPORT_RELATIVE, report_args))
            report_dir = _remote_path(remote_control, "report")
            report_status = _remote_path(report_dir, "stage.json")
            report_log = _remote_path(report_dir, "stage.log")
            report_cap = min(overall_deadline, clock() + REPORT_TIMEOUT_SECONDS)
            report_pid, report_marker = _launch_detached_stage(
                control, "report", report_command, report_dir, report_log, report_status,
                report_cap - clock(), transport, args.remote_host, overall_deadline, clock)
            _write_event(control, status, {"stage": "report", "status": "launched",
                                           "remote_pid": report_pid, "command": report_command})
            report_result = _wait_detached_stage(
                control, "report", report_pid, report_status, transport, args.remote_host,
                report_cap, overall_deadline, clock, sleeper)
            _write_event(control, status, {"stage": "score_report", "status": "pass",
                                           "score_command": score_command, "score_return_code": score_result["return_code"],
                                           "report_command": report_command, "report_return_code": report_result["return_code"]})

            closure_raw = _ssh_bytes(transport, args.remote_host, "cat -- {}".format(shlex.quote(_remote_path(remote_run, "closure.json"))),
                                     overall_deadline, clock, retries=1, sleeper=sleeper)
            if sha256_bytes(closure_raw) != closure_sha:
                raise ControllerError("remote closure changed after independent audit")
            closure = _read_json_bytes(closure_raw, "remote closure")
            returned = _return_artifacts(transport, args.remote_host, args.remote_root, remote_run,
                                         remote_control, run, control, closure,
                                         overall_deadline, clock, sleeper, args.attempt)
            if sha256_file(run / "closure.json") != closure_sha:
                raise ControllerError("returned closure differs from audited closure")
            scores = _read_json_bytes((run / "scores.json").read_bytes(), str(run / "scores.json"))
            provenance = scores.get("response_provenance", {})
            if (scores.get("plan_digest") != args.expected_plan_digest
                    or scores.get("closure_sha256") != closure_sha
                    or scores.get("schema_version") != "goal052-outer-scores-v1"
                    or provenance.get("plan_digest") != args.expected_plan_digest
                    or provenance.get("schema_version") != "goal052-outer-response-provenance-v1"
                    or provenance.get("closure_file_sha256") != closure_sha
                    or provenance.get("canonical_species_cells_sha256") != metadata["response_sha256"]
                    or provenance.get("closure_digest") != closure.get("closure_digest")):
                raise ControllerError("returned score binding mismatch")
            final_data = {
                "status": "complete", "success": True, "ended_utc": utc_now(),
                "remote_pid": remote_pid, "workers": workers,
                "plan_digest": args.expected_plan_digest, "plan_sha256": metadata["plan_sha256"],
                "closure_sha256": closure_sha, "audit_sha256": audit_sha,
                "response_sha256": actual_response_sha,
                "scores_sha256": sha256_file(run / "scores.json"),
                "report_sha256": sha256_file(run / "outer-report.md"),
                "returned_files": returned,
                "production_complete_sha256": sha256_bytes(complete_raw),
                "runtime_complete_sha256": sha256_bytes(runtime_raw),
                "score_remote_sha256": returned.get("remote_sha256", {}).get("scores.json"),
                "commands": {"launch": {"command": launch, "remote_pid": remote_pid,
                                          "return_code": None if launch_reconciled else 0,
                                          "reconciled": launch_reconciled},
                             "production": complete.get("commands", []),
                             "audit": {"command": audit_command, "remote_pid": audit_pid, "return_code": audit_result["return_code"]},
                             "score": {"command": score_command, "remote_pid": score_pid, "return_code": score_result["return_code"]},
                             "report": {"command": report_command, "remote_pid": report_pid, "return_code": report_result["return_code"]}},
            }
        except Exception as error:
            failure = {"reason": str(error), "error_type": type(error).__name__}
            try:
                partial_returned.update(_return_optional_receipts(
                    transport, args.remote_host, remote_run, run,
                    ("response-access.json", "response-access-success.json", "scoring-failure.json"),
                    overall_deadline, clock, sleeper))
            except Exception as receipt_error:
                failure["receipt_return_error"] = str(receipt_error)
            final_data = {"status": "failed", "success": False, "ended_utc": utc_now(), "failure": failure}
            if partial_returned:
                final_data["partial_returned_files"] = partial_returned
            status["status"] = "failed"
            status["failure"] = failure
            _atomic_json(control / "status.json", status)
        else:
            status["status"] = "complete"
            status["ended_utc"] = final_data["ended_utc"]
            _atomic_json(control / "status.json", status)
        if not (control / "manifest.json").is_file():
            # A preflight failure can occur before remote source/plan binding;
            # retain the immutable local prior-evidence manifest so the failed
            # manual restart remains auditable and cannot be replayed silently.
            _immutable_json(control / "manifest.json", manifest)
        final = {"schema_version": "goal052-outer-continuation-complete-v1", "attempt": args.attempt,
                 "manifest_sha256": sha256_file(control / "manifest.json"),
                 "source_hashes": local_source_hashes,
                 "remote_source_hashes": remote_source_hashes, **final_data}
        _immutable_json(control / "complete.json", final)
        return 0 if final.get("success") else 1
    finally:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        finally:
            lock.close()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--remote-host", default="utas-ubuntu")
    parser.add_argument("--remote-root", default="/data/codex/repos/dSDM-outer-20261003-r2")
    parser.add_argument("--run-relative", required=True)
    parser.add_argument("--expected-plan-digest", required=True)
    parser.add_argument("--production-hours", type=float, required=True)
    parser.add_argument("--overall-hours", type=float, required=True)
    parser.add_argument("--attempt", default="001")
    parser.add_argument("--restart-from", default=None,
                        help="explicit prior failed attempt for a manual restart (only 001 -> 002)")
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        return continue_campaign(parse_args(argv))
    except (ControllerError, OSError, ValueError) as error:
        print("goal052 continuation: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
