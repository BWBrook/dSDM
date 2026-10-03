"""Small process-control tests for the Goal 052 production supervisor."""

import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
import time


ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "scripts" / "goal052_outer_supervise.py"


def _stub_root(tmp_path: Path, *, fail_stage=None, sleep_stage=None,
               write_closure=True, spawn_grandchild=False):
    source = tmp_path / "src" / "dsdm_phase1"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("")
    fail_literal = repr(fail_stage)
    sleep_literal = repr(sleep_stage)
    closure_literal = repr(bool(write_closure))
    grandchild_literal = repr(bool(spawn_grandchild))
    module = textwrap.dedent(
        """
        import json
        import os
        from pathlib import Path
        import signal
        import subprocess
        import sys
        import time

        args = sys.argv[1:]
        stage = args[args.index("run") + 2] if "run" in args else args[0]
        run = Path(args[args.index("--run") + 1])
        calls = run / "stub-calls.json"
        previous = json.loads(calls.read_text()) if calls.exists() else []
        previous.append(stage)
        calls.write_text(json.dumps(previous))
        if stage == SLEEP_STAGE:
            time.sleep(30)
        if stage == FAIL_STAGE and SPAWN_GRANDCHILD:
            marker = run / "grandchild-term.txt"
            ready = run / "grandchild-ready.txt"
            code = "import pathlib, signal, sys, time\\n"
            code += "def stop(_signum, _frame):\\n"
            code += "    pathlib.Path(sys.argv[1]).write_text('term')\\n"
            code += "    raise SystemExit(0)\\n"
            code += "signal.signal(signal.SIGTERM, stop)\\n"
            code += "pathlib.Path(sys.argv[2]).write_text('ready')\\n"
            code += "time.sleep(30)\\n"
            child = subprocess.Popen([sys.executable, "-c", code, str(marker), str(ready)])
            (run / "grandchild.pid").write_text(str(child.pid))
            for _ in range(100):
                if ready.exists():
                    break
                time.sleep(0.01)
        if stage == FAIL_STAGE:
            raise SystemExit(7)
        if stage == "close" and WRITE_CLOSURE:
            (run / "closure.json").write_text(json.dumps({"status": "closed"}))
        """
    ).replace("SLEEP_STAGE", sleep_literal).replace("FAIL_STAGE", fail_literal).replace(
        "WRITE_CLOSURE", closure_literal
    ).replace(
        "SPAWN_GRANDCHILD", grandchild_literal
    )
    (source / "goal052_outer.py").write_text(module)
    run = tmp_path / "run"
    run.mkdir()
    (run / "plan.json").write_text("{}\n")
    return run


def _run(run: Path, *extra):
    return subprocess.run(
        _command(run, *extra),
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=20,
    )


def _command(run: Path, *extra):
    return [sys.executable, str(SUPERVISOR), "--root", str(run.parent), "--run", str(run),
            "--python", sys.executable, "--workers", "1", "--max-hours", "0.1",
            "--memory-floor-gib", "0", "--disk-floor-gib", "0"] + list(extra)


def _complete(run: Path, attempt="001"):
    return json.loads((run / ("production-control-{}".format(attempt)) / "complete.json").read_text())


def test_nonzero_stage_stops_sequence_and_preserves_failure(tmp_path):
    run = _stub_root(tmp_path, fail_stage="neural")
    result = _run(run)
    assert result.returncode == 1, result.stderr
    assert json.loads((run / "stub-calls.json").read_text()) == ["q", "pretraining", "neural"]
    complete = _complete(run)
    assert complete["status"] == "failed"
    assert complete["failure"] == {"reason": "stage_nonzero", "stage": "neural", "return_code": 7}
    assert (run / "production-control-001" / "stage-02-pretraining.json").is_file()
    assert not (run / "production-control-001" / "stage-04-conventional.json").exists()


def test_nonzero_stage_cleans_spawned_descendant_group(tmp_path):
    run = _stub_root(tmp_path, fail_stage="neural", spawn_grandchild=True)
    result = _run(run)
    assert result.returncode == 1, result.stderr
    marker = run / "grandchild-term.txt"
    for _ in range(50):
        if marker.exists():
            break
        time.sleep(0.02)
    assert marker.read_text() == "term"
    stage = json.loads((run / "production-control-001" / "stage-03-neural.json").read_text())
    assert stage["cleanup"]["term_sent"] is True


def test_run_level_lock_rejects_different_concurrent_attempt(tmp_path):
    run = _stub_root(tmp_path, sleep_stage="q")
    first = subprocess.Popen(
        _command(run, "--attempt", "001"), cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        lock = run / "production-control.lock"
        for _ in range(100):
            if lock.exists():
                break
            time.sleep(0.02)
        second = subprocess.run(
            _command(run, "--attempt", "002"), cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=5,
        )
        assert second.returncode == 2
        assert "already locked" in second.stderr
        assert not (run / "production-control-002").exists()
    finally:
        first.send_signal(signal.SIGTERM)
        first.communicate(timeout=10)
    assert first.returncode == 1


def test_wall_cap_terminates_owned_child_group(tmp_path):
    run = _stub_root(tmp_path, sleep_stage="q")
    result = _run(run, "--max-hours", "0.0001")
    assert result.returncode == 1, result.stderr
    complete = _complete(run)
    assert complete["failure"]["reason"] == "wall_time_cap_exceeded"
    stage = complete["commands"][0]
    assert stage["return_code"] is not None
    assert stage["status"] == "failed"


def test_success_requires_closure_and_binds_its_hash(tmp_path):
    run = _stub_root(tmp_path, write_closure=True)
    result = _run(run)
    assert result.returncode == 0, result.stderr
    calls = json.loads((run / "stub-calls.json").read_text())
    assert calls == ["q", "pretraining", "neural", "conventional", "close", "verify"]
    complete = _complete(run)
    assert complete["status"] == "predictions_closed_verified"
    expected = hashlib.sha256((run / "closure.json").read_bytes()).hexdigest()
    assert complete["closure"] == {"path": "closure.json", "exists": True, "sha256": expected}

    missing = _stub_root(tmp_path / "missing", write_closure=False)
    failed = _run(missing, "--attempt", "002")
    assert failed.returncode == 1
    missing_complete = _complete(missing, "002")
    assert missing_complete["status"] == "failed"
    assert missing_complete["failure"]["reason"] == "closure_missing_after_successful_commands"
