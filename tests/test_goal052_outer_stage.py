"""Fail-closed tests for the bounded Goal 052 logger recovery wrapper."""

import hashlib
import importlib.util
import json
from pathlib import Path
import traceback

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "goal052_outer_stage.py"


def _helper():
    spec = importlib.util.spec_from_file_location("goal052_outer_stage_test", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path, monkeypatch):
    helper = _helper()
    source = tmp_path / "src" / "dsdm_phase1"
    source.mkdir(parents=True)
    run = tmp_path / "run"
    run.mkdir()
    (run / "fits" / "q.block00").mkdir(parents=True)
    (run / "qualification").mkdir()
    (run / "fits" / "q.block00" / "model.npz").write_bytes(b"model")
    qualification = {"status": "outer_runtime_qualified", "plan_digest": "plan-digest", "files": {}}
    (run / "qualification" / "final.json").write_text(json.dumps(qualification))
    receipt = {
        "status": "outer_fit_complete", "plan_digest": "plan-digest",
        "task": {"id": "q.block00", "kind": "q", "block": 0, "seed": 11},
        "outer_response_rows_read": 0, "qualification": "qualification/final.json",
        "qualification_sha256": hashlib.sha256((run / "qualification" / "final.json").read_bytes()).hexdigest(),
        "files": {"model.npz": hashlib.sha256(b"model").hexdigest()},
        "fit": {}, "dependencies": {},
    }
    (run / "fits" / "q.block00" / "receipt.json").write_text(json.dumps(receipt))
    plan = {"plan_digest": "plan-digest", "outer_response_rows_read": 0,
            "sources": {"src/dsdm_phase1/goal052_outer.py": helper.NATIVE_SHA256},
            "tasks": [receipt["task"]]}
    (run / "plan.json").write_text(json.dumps(plan))
    prior = run / "production-control-001"
    prior.mkdir()
    terminal_log = (
        "Traceback (most recent call last):\n"
        "  File \"/remote/src/dsdm_phase1/goal052_outer.py\", line 331, in run_stage\n"
        "    event(\"stage_complete\", **result)\n"
        "TypeError: event() got multiple values for argument 'stage'\n"
    )
    (prior / "stage-01-q.log").write_text(terminal_log)
    manifest = {"plan_sha256": hashlib.sha256((run / "plan.json").read_bytes()).hexdigest(),
                "source_supervisor_sha256": "prior-supervisor"}
    (prior / "manifest.json").write_text(json.dumps(manifest))
    complete = {"status": "failed", "success": False, "plan_sha256": manifest["plan_sha256"],
                "failure": {"reason": "stage_nonzero", "stage": "q", "return_code": 1},
                "commands": [{"stage": "q", "log": "stage-01-q.log"}]}
    (prior / "complete.json").write_text(json.dumps(complete))
    active = run / "production-control-002"
    active.mkdir()
    (active / "manifest.json").write_text(json.dumps({
        "attempt": "002", "plan_sha256": hashlib.sha256((run / "plan.json").read_bytes()).hexdigest(),
        "source_supervisor_sha256": hashlib.sha256((ROOT / "scripts" / "goal052_outer_supervise.py").read_bytes()).hexdigest(),
        "recovery_helper_sha256": hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest(),
        "args": {"attempt": "002", "recover_stage_logging": True, "restart_from": "001", "root": str(tmp_path)},
    }))

    native = __import__("dsdm_phase1.goal052_outer", fromlist=["*"])
    monkeypatch.setattr(helper, "_load_native", lambda _root: native)
    plan_value = plan
    monkeypatch.setattr(native, "load_plan", lambda _root, _run: plan_value)
    monkeypatch.setattr(native, "load_leaf", lambda _run, _plan, task: receipt)
    monkeypatch.setattr(native, "load_q", lambda _run, _plan, block: (object(), receipt))
    runtime = __import__("dsdm_phase1.goal052_outer_runtime", fromlist=["*"])
    monkeypatch.setattr(runtime, "require_qualification", lambda *_args: "qualification/final.json")

    class Future:
        def __init__(self, value): self.value = value
        def result(self): return self.value
        def done(self): return True
        def cancelled(self): return False
        def exception(self): return None
        def cancel(self): return False

    class Pool:
        def __init__(self, *args, **kwargs): self.futures = []
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def submit(self, *args):
            future = Future(len(args[1]))
            self.futures.append(future)
            return future

    monkeypatch.setattr(native, "ProcessPoolExecutor", Pool)
    monkeypatch.setattr(native, "as_completed", lambda futures: iter(futures))
    return helper, native, tmp_path, run, plan


def test_recovery_calls_frozen_run_stage_and_writes_receipt(tmp_path, monkeypatch):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)
    receipt = helper.recover_stage(root, run, "q", 1)
    assert receipt["status"] == "recovered_stage_logging"
    assert receipt["initial_existing_fit_ids"] == ["q.block00"]
    assert receipt["preexisting_fits_unchanged"] is True
    assert (run / "production-control-002" / "stage-recovery-q.json").is_file()


def test_recovery_rejects_wrong_terminal_typeerror(tmp_path, monkeypatch):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)

    def wrong(*args):
        raise TypeError("different failure")

    monkeypatch.setattr(native, "run_stage", wrong)
    with pytest.raises(TypeError, match="different failure"):
        helper.recover_stage(root, run, "q", 1)


def test_recovery_rejects_same_message_from_wrong_frame(tmp_path, monkeypatch):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)

    def wrong_frame(*args):
        raise TypeError(helper.TERMINAL_MESSAGE)

    monkeypatch.setattr(native, "run_stage", wrong_frame)
    with pytest.raises(TypeError, match="multiple values for argument"):
        helper.recover_stage(root, run, "q", 1)


def test_recovery_rejects_preexisting_fit_mutation(tmp_path, monkeypatch):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)
    original_load_plan = native.load_plan
    calls = [0]

    def mutating_load_plan(*args):
        calls[0] += 1
        if calls[0] == 2:
            (run / "fits" / "q.block00" / "model.npz").write_bytes(b"changed")
        return original_load_plan(*args)

    monkeypatch.setattr(native, "load_plan", mutating_load_plan)
    with pytest.raises(RuntimeError, match="fit file hash mismatch|pre-existing fit file changed"):
        helper.recover_stage(root, run, "q", 1)


@pytest.mark.parametrize("operation", ["missing", "corrupt"])
def test_leaf_file_inventory_rejects_missing_or_corrupt_saved_file(tmp_path, monkeypatch, operation):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)
    task = plan["tasks"][0]
    model = run / "fits" / task["id"] / "model.npz"
    if operation == "missing":
        model.unlink()
    else:
        model.write_bytes(b"corrupt")
    with pytest.raises(RuntimeError, match="fit file hash mismatch"):
        helper._relative_hashes(run, task, json.loads((run / "fits" / task["id"] / "receipt.json").read_text()))


def test_recovery_rejects_stale_active_manifest_hash(tmp_path, monkeypatch):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)
    manifest_path = run / "production-control-002" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["recovery_helper_sha256"] = "stale"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="active recovery helper hash drift"):
        helper.recover_stage(root, run, "q", 1)


def test_load_native_rejects_wrong_frozen_native_hash(monkeypatch):
    helper = _helper()
    monkeypatch.setattr(helper, "NATIVE_SHA256", "wrong-native-sha")
    with pytest.raises(RuntimeError, match="frozen native source hash drift"):
        helper._load_native(ROOT)


def test_worker_typeerror_with_approved_message_is_not_recovered(tmp_path, monkeypatch):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)

    class WorkerErrorFuture:
        def result(self):
            raise TypeError(helper.TERMINAL_MESSAGE)
        def done(self): return True
        def cancelled(self): return False
        def exception(self): return self._error
        def cancel(self): return False

    def make_future(*args):
        future = WorkerErrorFuture()
        try:
            future.result()
        except TypeError as error:
            future._error = error
        return future

    class Pool:
        def __init__(self, *args, **kwargs): self.futures = []
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def submit(self, *args):
            future = make_future(*args)
            self.futures.append(future)
            return future

    monkeypatch.setattr(native, "ProcessPoolExecutor", Pool)
    monkeypatch.setattr(native, "as_completed", lambda futures: iter(futures))
    with pytest.raises(TypeError, match="multiple values for argument"):
        helper.recover_stage(root, run, "q", 1)


def test_multi_fit_target_group_checks_future_result_count(tmp_path, monkeypatch):
    helper, native, root, run, plan = _fixture(tmp_path, monkeypatch)
    tasks = [
        {"id": "neural.target.full.seed-a", "kind": "neural", "target": "target",
         "arm": "full", "seed_label": "a"},
        {"id": "neural.target.full.seed-b", "kind": "neural", "target": "target",
         "arm": "full", "seed_label": "b"},
    ]
    plan["tasks"] = [plan["tasks"][0]] + tasks
    for task in tasks:
        directory = run / "fits" / task["id"]
        directory.mkdir(parents=True)
        (directory / "model.npz").write_bytes(b"model-" + task["id"].encode())
    plan["plan_digest"] = "plan-digest"
    receipt_template = json.loads((run / "fits" / "q.block00" / "receipt.json").read_text())
    for task in tasks:
        (run / "fits" / task["id"] / "receipt.json").write_text(json.dumps(receipt_template))
    monkeypatch.setattr(native, "load_leaf", lambda _run, _plan, task: {
        **receipt_template,
        "task": dict(task),
        "files": {"model.npz": hashlib.sha256((run / "fits" / task["id"] / "model.npz").read_bytes()).hexdigest()},
    })
    receipt = helper.recover_stage(root, run, "neural", 1)
    assert receipt["selected_fit_ids"] == [task["id"] for task in tasks]
