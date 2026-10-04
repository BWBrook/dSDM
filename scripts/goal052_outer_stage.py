#!/usr/bin/env python3
"""Recover the Goal 052 terminal stage logger failure.

This is a deliberately narrow operational wrapper.  It accepts one known
failure in the frozen native runner, calls that runner unchanged, and only
returns success after the stage's leaves and all provenance bindings validate.
It never imports the outer response reader or invokes closure/scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Dict, Mapping, Optional, Sequence


NATIVE_RELATIVE = Path("src/dsdm_phase1/goal052_outer.py")
NATIVE_SHA256 = "cd7f9d31a68144ba93f204ac4419a0d7e9de0bb9287a3801d3d80ce312feb5c3"
TERMINAL_LINE = 331
TERMINAL_CALL = 'event("stage_complete", **result)'
TERMINAL_MESSAGE = "event() got multiple values for argument 'stage'"
FIT_STAGES = ("q", "pretraining", "neural", "conventional")
PRIOR_ATTEMPT = "001"
CURRENT_ATTEMPT = "002"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text())
    _require(isinstance(value, dict), "JSON object required: {}".format(path))
    return value


def _immutable_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".{}.tmp".format(os.getpid()))
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    try:
        os.link(str(temporary), str(path))
    except FileExistsError as error:
        raise RuntimeError("immutable recovery receipt already exists: {}".format(path)) from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _relative_hashes(run: Path, task: Mapping[str, Any], receipt: Mapping[str, Any]) -> Dict[str, str]:
    """Hash a leaf, its saved files, qualification, and qualification files."""
    directory = run / "fits" / str(task["id"])
    result = {str((directory / "receipt.json").relative_to(run)): _sha256(directory / "receipt.json")}
    for name, expected in receipt.get("files", {}).items():
        path = directory / str(name)
        actual = _sha256(path) if path.is_file() else None
        _require(actual == expected, "fit file hash mismatch: {}".format(path))
        result[str(path.relative_to(run))] = actual
    qualification = str(receipt.get("qualification", ""))
    _require(qualification.startswith("qualification/"), "invalid qualification path")
    qualification_path = run / qualification
    _require(qualification_path.is_file(), "missing qualification receipt: {}".format(qualification)
    )
    qualification_value = _json(qualification_path)
    qualification_sha = _sha256(qualification_path)
    _require(qualification_sha == receipt.get("qualification_sha256"), "qualification hash mismatch")
    result[qualification] = qualification_sha
    for name, expected in qualification_value.get("files", {}).items():
        path = run / str(name)
        actual = _sha256(path) if path.is_file() else None
        _require(actual == expected, "qualification file hash mismatch: {}".format(path))
        result[str(path.relative_to(run))] = actual
    return result


def _load_native(root: Path):
    source = root / NATIVE_RELATIVE
    _require(source.is_file(), "missing frozen native source: {}".format(source))
    _require(_sha256(source) == NATIVE_SHA256, "frozen native source hash drift")
    source_text = source.read_text().splitlines()
    _require(len(source_text) >= TERMINAL_LINE and source_text[TERMINAL_LINE - 1].strip() == TERMINAL_CALL,
             "frozen native terminal call drift")
    source_dir = str((root / "src").resolve())
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)
    native = importlib.import_module("dsdm_phase1.goal052_outer")
    native_file = Path(native.__file__).resolve()
    _require(native_file == source.resolve(), "native module path drift")
    _require(native.run_stage.__code__ is not None, "native run_stage unavailable")
    return native


def _prior_receipts(run: Path, restart_from: str, stage: str) -> Dict[str, Any]:
    _require(restart_from == PRIOR_ATTEMPT, "recovery is bound to restart-from 001")
    prior = run / "production-control-{}".format(restart_from)
    complete_path = prior / "complete.json"
    manifest_path = prior / "manifest.json"
    _require(complete_path.is_file() and manifest_path.is_file(), "prior production attempt is incomplete")
    complete = _json(complete_path)
    manifest = _json(manifest_path)
    _require(complete.get("status") == "failed" and complete.get("success") is False, "prior attempt was not failed")
    _require(complete.get("failure") == {"reason": "stage_nonzero", "stage": "q", "return_code": 1},
             "prior attempt failure is not the approved q logger failure")
    _require(complete.get("plan_sha256") == manifest.get("plan_sha256"), "prior plan binding drift")
    command = next((item for item in complete.get("commands", []) if item.get("stage") == "q"), None)
    _require(isinstance(command, dict), "prior q stage receipt missing")
    log_name = str(command.get("log", ""))
    log_path = prior / log_name
    _require(log_path.is_file(), "prior q log missing")
    log = log_path.read_text(errors="replace")
    lines = log.rstrip("\n").splitlines()
    _require(lines and lines[-1] == "TypeError: {}".format(TERMINAL_MESSAGE), "prior log terminal error drift")
    marker = 'event("stage_complete", **result)'
    _require(any(marker in line for line in lines[-8:]), "prior log terminal call missing")
    _require(any("goal052_outer.py\", line 331, in run_stage" in line for line in lines[-12:]),
             "prior log terminal source location drift")
    return {
        "attempt": restart_from,
        "complete": str(complete_path.relative_to(run)),
        "complete_sha256": _sha256(complete_path),
        "manifest": str(manifest_path.relative_to(run)),
        "manifest_sha256": _sha256(manifest_path),
        "log": str(log_path.relative_to(run)),
        "log_sha256": _sha256(log_path),
        "plan_sha256": str(complete.get("plan_sha256")),
        "failure": complete["failure"],
        "requested_stage": stage,
    }


def _expected_tasks(plan: Mapping[str, Any], stage: str) -> list[dict]:
    tasks = [task for task in plan["tasks"] if task.get("kind") == stage]
    _require(tasks, "stage inventory is empty: {}".format(stage))
    grouped: Dict[str, list] = {}
    for task in tasks:
        grouped.setdefault(str(task.get("target", task["id"])), []).append(task)
    selected = [group for _, group in sorted(grouped.items())]
    _require(sum(len(group) for group in selected) == len(tasks), "stage inventory grouping drift")
    return [task for group in selected for task in group]


def _response_free(run: Path, plan: Mapping[str, Any]) -> None:
    _require(plan.get("outer_response_rows_read") == 0, "plan response access")
    _require(not (run / "closure.json").exists() and not (run / "scores.json").exists()
             and not (run / "scoring-failure.json").exists(),
             "closure or scores already exists")
    for path in run.rglob("*.json"):
        name = path.name.lower()
        if ("response" in name and "access" in name) or "response_access" in name:
            raise RuntimeError("response access receipt exists: {}".format(path))


def _validate_leaves(native: Any, root: Path, run: Path, plan: Mapping[str, Any], tasks: Sequence[dict]) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    seen = set()
    for task in tasks:
        task_id = str(task["id"])
        if task_id in seen:
            raise RuntimeError("duplicate selected fit: {}".format(task_id))
        seen.add(task_id)
        receipt = native.load_leaf(run, plan, task)
        _require(receipt is not None, "missing selected leaf: {}".format(task_id))
        hashes.update(_relative_hashes(run, task, receipt))
        for dependency_id in receipt.get("dependencies", {}):
            dep = next((item for item in plan["tasks"] if item.get("id") == dependency_id), None)
            _require(dep is not None, "unknown fit dependency: {}".format(dependency_id))
            dep_receipt = native.load_leaf(run, plan, dep)
            _require(dep_receipt is not None, "missing fit dependency: {}".format(dependency_id))
            hashes.update(_relative_hashes(run, dep, dep_receipt))
        if task.get("kind") == "q":
            loader = getattr(native, "load_q", None)
            _require(loader is not None, "native q loader unavailable")
            loaded = loader(run, plan, int(task["block"]))
            _require(loaded is not None, "native q loader returned no model")
    return hashes


def _existing_hashes(run: Path) -> tuple[list[str], Dict[str, str]]:
    ids = []
    hashes: Dict[str, str] = {}
    fits = run / "fits"
    if not fits.is_dir():
        return ids, hashes
    for receipt_path in sorted(fits.glob("*/receipt.json")):
        fit_id = receipt_path.parent.name
        ids.append(fit_id)
        for path in sorted(receipt_path.parent.rglob("*")):
            if path.is_file() and path.name != ".lock":
                hashes[str(path.relative_to(run))] = _sha256(path)
    return ids, hashes


def _check_manifest(run: Path, attempt: str, restart_from: str, plan_sha: str,
                    helper_path: Path, supervisor_path: Path) -> Dict[str, Any]:
    path = run / "production-control-{}".format(attempt) / "manifest.json"
    _require(path.is_file(), "active production manifest is missing")
    manifest = _json(path)
    args = manifest.get("args", {})
    _require(manifest.get("attempt") == attempt and args.get("attempt") == attempt,
             "active production attempt binding drift")
    _require(args.get("recover_stage_logging") is True and args.get("restart_from") == restart_from,
             "active recovery mode binding drift")
    _require(manifest.get("plan_sha256") == plan_sha and args.get("root") is not None,
             "active production plan binding drift")
    _require(manifest.get("recovery_helper_sha256") == _sha256(helper_path),
             "active recovery helper hash drift")
    _require(manifest.get("source_supervisor_sha256") == _sha256(supervisor_path),
             "active supervisor hash drift")
    return manifest


def _terminal_exception(error: TypeError, native: Any, stage: str, workers: int, plan: Mapping[str, Any]) -> Dict[str, Any]:
    _require(str(error) == TERMINAL_MESSAGE and error.args == (TERMINAL_MESSAGE,), "unexpected TypeError message")
    _require(error.__cause__ is None and error.__context__ is None, "unexpected TypeError context")
    source = Path(native.__file__).resolve()
    traceback_last = error.__traceback__
    while traceback_last is not None and traceback_last.tb_next is not None:
        traceback_last = traceback_last.tb_next
    _require(traceback_last is not None and traceback_last.tb_frame.f_code is native.run_stage.__code__,
             "TypeError did not terminate in native run_stage")
    _require(traceback_last.tb_lineno == TERMINAL_LINE, "TypeError line drift")
    frame = traceback_last.tb_frame
    local = frame.f_locals
    _require(local.get("stage") == stage and local.get("workers") == workers,
             "native stage arguments drift")
    _require(local.get("shard") == 0 and local.get("shards") == 1, "native sharding is not full")
    selected = local.get("selected")
    result = local.get("result")
    futures = local.get("futures")
    _require(isinstance(selected, list) and isinstance(futures, list) and isinstance(result, dict),
             "native terminal locals incomplete")
    expected = _expected_tasks(plan, stage)
    actual = [task for group in selected for task in group]
    _require(actual == expected and result == {
        "status": "outer_stage_complete", "stage": stage, "shard": 0, "shards": 1,
        "fits": len(expected), "outer_response_rows_read": 0,
    }, "native terminal inventory drift")
    _require(len(futures) == len(selected), "native future inventory drift")
    for future, group in zip(futures, selected):
        _require(future.done() and not future.cancelled() and future.exception() is None,
                 "native future incomplete or failed")
        _require(future.result() == len(group), "native future result inventory drift")
    return {
        "type": type(error).__name__, "message": str(error), "args": list(error.args),
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        "source": str(source), "line": TERMINAL_LINE, "call": TERMINAL_CALL,
        "frame_locals": {"stage": stage, "workers": workers, "shard": 0, "shards": 1,
                          "result": result, "selected_count": len(selected), "futures_count": len(futures)},
    }


def recover_stage(root: Path, run: Path, stage: str, workers: int,
                  attempt: str = CURRENT_ATTEMPT, restart_from: str = PRIOR_ATTEMPT) -> Dict[str, Any]:
    _require(stage in FIT_STAGES, "recovery stage must be a fitting stage")
    _require(workers >= 1 and attempt == CURRENT_ATTEMPT, "recovery is bound to production attempt 002")
    control = run / "production-control-{}".format(attempt)
    _require(control.is_dir(), "active production-control attempt is missing")
    prior = _prior_receipts(run, restart_from, stage)
    native = _load_native(root)
    plan_path = run / "plan.json"
    _require(plan_path.is_file(), "missing plan")
    plan = native.load_plan(root, run)
    plan_sha = _sha256(plan_path)
    _require(prior.get("plan_sha256") == plan_sha, "prior attempt plan differs from current plan")
    helper_path = Path(__file__).resolve()
    supervisor_path = helper_path.with_name("goal052_outer_supervise.py")
    _check_manifest(run, attempt, restart_from, plan_sha, helper_path, supervisor_path)
    _response_free(run, plan)
    tasks = _expected_tasks(plan, stage)
    initial_ids, initial_hashes = _existing_hashes(run)
    valid_ids = {str(task["id"]) for task in plan["tasks"]}
    _require(set(initial_ids).issubset(valid_ids), "unexpected pre-existing fit inventory")
    exception_info: Optional[Dict[str, Any]] = None
    try:
        native.run_stage(root, run, stage, workers, "cpu", 0, 1)
    except TypeError as error:
        try:
            exception_info = _terminal_exception(error, native, stage, workers, plan)
        except RuntimeError:
            # A TypeError outside the exact bound terminal site is not a
            # recoverable logger failure; preserve its original exception.
            raise error.with_traceback(error.__traceback__) from None
    if exception_info is None:
        raise RuntimeError("native stage did not produce the approved terminal logger failure")
    plan_after = native.load_plan(root, run)
    _require(plan_after["plan_digest"] == plan["plan_digest"] and _sha256(plan_path) == plan_sha,
             "plan changed during recovery")
    _response_free(run, plan_after)
    final_hashes = _validate_leaves(native, root, run, plan_after, tasks)
    after_ids, all_after_hashes = _existing_hashes(run)
    _require(set(initial_ids).issubset(set(after_ids)), "pre-existing fit inventory changed")
    _require(set(after_ids).issubset(valid_ids), "unexpected completed fit inventory")
    for path, expected in initial_hashes.items():
        _require(all_after_hashes.get(path) == expected, "pre-existing fit file changed: {}".format(path))
    for fit_id in initial_ids:
        prefix = "fits/{}/".format(fit_id)
        before_files = {path for path in initial_hashes if path.startswith(prefix)}
        after_files = {path for path in all_after_hashes if path.startswith(prefix)}
        _require(before_files == after_files, "pre-existing fit file inventory changed: {}".format(fit_id))
    _check_manifest(run, attempt, restart_from, plan_sha, helper_path, supervisor_path)
    receipt = {
        "schema_version": "goal052-outer-stage-recovery-v1", "status": "recovered_stage_logging",
        "attempt": attempt, "restart_from": restart_from, "stage": stage, "workers": workers,
        "device": "cpu", "shard": 0, "shards": 1,
        "plan": "plan.json", "plan_sha256": plan_sha, "plan_digest": plan_after["plan_digest"],
        "native_source": str(NATIVE_RELATIVE), "native_source_sha256": NATIVE_SHA256,
        "source_hashes": dict(plan_after.get("sources", {})),
        "helper": str(helper_path.relative_to(root) if helper_path.is_relative_to(root) else helper_path),
        "helper_sha256": _sha256(helper_path),
        "supervisor": str(supervisor_path.relative_to(root) if supervisor_path.is_relative_to(root) else supervisor_path),
        "supervisor_sha256": _sha256(supervisor_path),
        "prior_attempt": prior, "exception": exception_info,
        "selected_fit_ids": [task["id"] for task in tasks],
        "initial_existing_fit_ids": initial_ids, "initial_existing_file_hashes": initial_hashes,
        "validated_fit_file_hashes": final_hashes,
        "post_existing_fit_file_hashes": all_after_hashes,
        "preexisting_fits_unchanged": True,
        "outer_response_rows_read": 0,
        "manifest_sha256": _sha256(control / "manifest.json"),
    }
    path = control / "stage-recovery-{}.json".format(stage)
    _immutable_json(path, receipt)
    return receipt


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--stage", choices=FIT_STAGES, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--attempt", default=CURRENT_ATTEMPT)
    parser.add_argument("--restart-from", default=PRIOR_ATTEMPT)
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    args.run = args.run.resolve()
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    recover_stage(args.root, args.run, args.stage, args.workers, args.attempt, args.restart_from)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
