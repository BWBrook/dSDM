"""Strict synthetic contracts for the local Goal052 continuation controller."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("goal052_outer_complete", ROOT / "scripts/goal052_outer_complete.py")
controller = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(controller)


class Result:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True).encode() + b"\n"


class StrictTransport:
    """A filesystem-backed transport implementing only expected commands."""

    def __init__(self, root, remote_root, plan_digest, plan_sha, source_hash, closure,
                 response_relative, response_sha, fail_audit=False,
                 corrupt_return=False, malformed_runtime=False):
        self.root = root
        self.remote_root = Path(remote_root)
        self.plan_digest = plan_digest
        self.plan_sha = plan_sha
        self.source_hash = source_hash
        self.closure = closure
        self.response_relative = response_relative
        self.response_sha = response_sha
        self.fail_audit = fail_audit
        self.corrupt_return = corrupt_return
        self.malformed_runtime = malformed_runtime
        self.audit_passed = False
        self.calls = []
        self._write_remote("run/plan.json", (root / "run/plan.json").read_bytes())
        self._build_runtime()

    def _write_remote(self, relative, value):
        path = self.remote_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else json_bytes(value))

    def _build_runtime(self):
        fingerprint = "f" * 64
        source_hashes = {"source.py": self.source_hash}
        canary = {"status": "goal052_outer_canary_valid", "plan_digest": self.plan_digest,
                  "runtime_fingerprint": fingerprint, "code_hashes": source_hashes,
                  "workers_tested": 4, "outer_response_rows_read": 0}
        profile = {"status": "goal052_outer_profile_valid", "plan_digest": self.plan_digest,
                   "runtime_fingerprint": fingerprint, "code_hashes": source_hashes,
                   "qualified_workers": 4, "peak_rss_bytes": 1024 ** 3,
                   "outer_response_rows_read": 0}
        final = {"status": "outer_runtime_qualified", "plan_digest": self.plan_digest,
                 "runtime_fingerprint": fingerprint, "qualified_workers": 4,
                 "canary": "qualification/canary.json", "profile": "qualification/profile.json",
                 "outer_response_rows_read": 0}
        canary_raw, profile_raw = json_bytes(canary), json_bytes(profile)
        final["files"] = {"qualification/canary.json": sha_bytes(canary_raw),
                           "qualification/profile.json": sha_bytes(profile_raw)}
        final_raw = json_bytes(final)
        files = dict(final["files"])
        files["qualification/final.json"] = sha_bytes(final_raw)
        final_raw = json_bytes(final)
        files["qualification/final.json"] = sha_bytes(final_raw)
        runtime = {"schema_version": "goal052-runtime-controller-v1",
                   "status": "runtime_qualification_completed", "plan_sha256": self.plan_sha,
                   "stages": [{"stage": "qualify", "returncode": 0},
                              {"stage": "profile", "returncode": 0}],
                   "files": files, "outer_response_rows_read": 0}
        if self.malformed_runtime:
            runtime["files"] = {"qualification/final.json": files["qualification/final.json"]}
        self._write_remote("run/runtime-control-001/complete.json", runtime)
        self._write_remote("run/qualification/canary.json", canary)
        self._write_remote("run/qualification/profile.json", profile)
        self._write_remote("run/qualification/final.json", final)

    def _remote_path(self, value):
        path = Path(value).resolve()
        remote_root = self.remote_root.resolve()
        try:
            return remote_root / path.relative_to(remote_root)
        except ValueError:
            return remote_root / path.name

    def _write_production(self):
        prediction = b"prediction bytes\n"
        domain = b"domain bytes\n"
        plan = (self.root / "run/plan.json").read_bytes()
        self._write_remote("run/domain.npz", domain)
        self._write_remote("run/predictions/target.npz", prediction)
        closure = dict(self.closure)
        closure["files"] = {"plan.json": sha_bytes(plan), "domain.npz": sha_bytes(domain),
                             "predictions/target.npz": sha_bytes(prediction)}
        closure_raw = json_bytes(closure)
        self._write_remote("run/closure.json", closure_raw)
        self.closure = closure
        closure_sha = sha_bytes(closure_raw)
        commands = [{"stage": stage, "status": "succeeded", "return_code": 0}
                    for stage in controller.STAGES]
        complete = {"status": "predictions_closed_verified", "success": True,
                    "source_supervisor_sha256": sha_bytes((ROOT / "scripts/goal052_outer_supervise.py").read_bytes()),
                    "plan_sha256": self.plan_sha, "closure_sha256": closure_sha,
                    "closure": {"exists": True, "sha256": closure_sha}, "commands": commands}
        self._write_remote("run/production-control-001/complete.json", complete)
        self._write_remote("run/production-supervisor-001.log", b"production log\n")
        self._write_remote("run/production-control-001/status.json", complete)

    def ssh(self, host, command, timeout):
        self.calls.append(("ssh", command))
        tokens = shlex.split(command)
        if command.startswith("sha256sum --"):
            lines = []
            for path in tokens[2:]:
                candidate = self._remote_path(path)
                if path.endswith("goal052_outer_supervise.py"):
                    digest = sha_bytes((ROOT / "scripts/goal052_outer_supervise.py").read_bytes())
                elif path.endswith("goal052_outer_independent_audit.py"):
                    digest = sha_bytes((ROOT / "scripts/goal052_outer_independent_audit.py").read_bytes())
                elif path.endswith("goal052_outer_report.py"):
                    digest = sha_bytes((ROOT / "scripts/goal052_outer_report.py").read_bytes())
                else:
                    if not candidate.is_file():
                        return Result(1, stderr=b"missing")
                    digest = sha_bytes(candidate.read_bytes())
                lines.append("{}  {}".format(digest, path))
            return Result(stdout=("\n".join(lines) + "\n").encode())
        if command.startswith("cat -- "):
            candidate = self._remote_path(tokens[2])
            return Result(stdout=candidate.read_bytes()) if candidate.is_file() else Result(1, stderr=b"missing")
        if command.startswith("test -e "):
            return Result(0 if self._remote_path(tokens[2]).exists() else 1)
        if command.startswith("find "):
            directory = self._remote_path(tokens[1])
            matches = [path for path in directory.iterdir() if path.is_file() and
                       ((path.name.startswith("response-access") and path.name.endswith(".json")) or
                        path.name == "scoring-failure.json")]
            return Result(stdout=(str(matches[0]).encode() + b"\n") if matches else b"")
        if command.startswith("kill -0 "):
            return Result(1)
        if command.startswith("awk "):
            return Result(stdout=str(64 * 1024 ** 3).encode() + b"\n")
        if "goal052_outer_supervise.py" in command:
            self._write_production()
            return Result(stdout=b"4242\n")
        if "outer_independent_audit.py" in command:
            self.audit_passed = True
            audit = {"status": "pass", "auditor": {"sha256": sha_bytes((ROOT / "scripts/goal052_outer_independent_audit.py").read_bytes())},
                     "provenance": {"plan_sha256": self.plan_sha,
                     "plan_digest": self.plan_digest, "closure_sha256": sha_bytes(json_bytes(self.closure))},
                     "verified": {"pre_score_absence": True, "pre_response_access_absence": True,
                                  "outer_response_content_opened": False}}
            if self.fail_audit:
                audit["status"] = "fail"
            output = self.remote_root / "continuation-control-001/audit/independent-audit.json"
            self._write_remote(str(output.relative_to(self.remote_root)), audit)
            self._write_remote("continuation-control-001/audit/stage.json",
                               {"status": "complete", "stage": "audit", "pid": 5001,
                                "return_code": 0 if not self.fail_audit else 1})
            return Result(stdout=b"5001\n")
        if "dsdm_phase1.goal052_outer" in command and " score " in command:
            closure_sha = sha_bytes(json_bytes(self.closure))
            self._write_remote("run/scores.json", {"schema_version": "goal052-outer-scores-v1",
                "plan_digest": self.plan_digest, "closure_sha256": closure_sha,
                "response_provenance": {"schema_version": "goal052-outer-response-provenance-v1",
                    "plan_digest": self.plan_digest, "closure_file_sha256": closure_sha,
                    "closure_digest": self.closure["closure_digest"],
                    "canonical_species_cells_sha256": self.response_sha},
                "targets": [], "aggregate": {}, "interpretive_limits": []})
            self._write_remote("run/response-access.json", {"status": "response_access_started"})
            self._write_remote("run/response-access-success.json", {"status": "response_access_complete"})
            self._write_remote("continuation-control-001/score/stage.json",
                               {"status": "complete", "stage": "score", "pid": 5002, "return_code": 0})
            return Result(stdout=b"5002\n")
        if "goal052_outer_report.py" in command:
            self._write_remote("run/outer-report.md", b"# report\n")
            self._write_remote("continuation-control-001/report/stage.json",
                               {"status": "complete", "stage": "report", "pid": 5003, "return_code": 0})
            return Result(stdout=b"5003\n")
        if command.startswith("mkdir -p "):
            self._remote_path(tokens[2]).mkdir(parents=True, exist_ok=True)
            return Result()
        if "response-transfer.json" in command:
            return Result()
        raise AssertionError("unexpected SSH command: {}".format(command))

    def rsync(self, source, destination, timeout):
        self.calls.append(("rsync", source, destination, self.audit_passed))
        if source == str(self.root / "data/goal049/canonical.parquet"):
            assert self.audit_passed, "response transfer occurred before audit"
        if ":" in source:
            source_path = self._remote_path(source.split(":", 1)[1].rstrip("/"))
            destination_path = Path(destination)
            if not destination_path.parent.is_dir():
                return Result(1, stderr=b"destination parent missing")
            if source.endswith("/") or source_path.is_dir():
                destination_path.mkdir(parents=True, exist_ok=True)
                for item in source_path.rglob("*"):
                    if item.is_file():
                        target = destination_path / item.relative_to(source_path)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target)
            else:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination_path)
        else:
            destination_path = self._remote_path(destination.split(":", 1)[1])
            if not destination_path.parent.is_dir():
                return Result(1, stderr=b"remote destination parent missing")
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source), destination_path)
        if self.corrupt_return and ":" in source and source.endswith("predictions/target.npz"):
            Path(destination).write_bytes(b"corrupt")
        return Result()


def fixture(tmp_path, *, fail_audit=False, corrupt_return=False, malformed_runtime=False):
    root = tmp_path / "root"
    run = root / "run"
    run.mkdir(parents=True)
    (root / "scripts").mkdir()
    for name in ("goal052_outer_supervise.py", "goal052_outer_independent_audit.py",
                 "goal052_outer_report.py", "goal052_outer_complete.py"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    (root / "config").mkdir()
    (root / "evidence/seawfb_canonical_response/goal049").mkdir(parents=True)
    (root / "data/goal049").mkdir(parents=True)
    (root / "source.py").write_bytes(b"source\n")
    response = b"synthetic response bytes\n"
    response_relative = "data/goal049/canonical.parquet"
    (root / response_relative).write_bytes(response)
    config = {"schema_version": "1.0", "private_outputs": {"root": "data/goal049"}}
    completion = {"status": "complete", "private_outputs": {"canonical_species_cells": response_relative},
                  "bindings": {"canonical_species_cells_sha256": sha_bytes(response)}}
    config_path = root / controller.CONFIG_RELATIVE
    completion_path = root / controller.COMPLETION_RELATIVE
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n")
    completion_path.write_text(json.dumps(completion, sort_keys=True) + "\n")
    digest = "a" * 64
    plan = {"plan_digest": digest, "sources": {"source.py": sha_bytes(b"source\n")}, "inputs": {
        controller.CONFIG_RELATIVE: sha_bytes(config_path.read_bytes()),
        controller.COMPLETION_RELATIVE: sha_bytes(completion_path.read_bytes()),
    }}
    (run / "plan.json").write_bytes(json_bytes(plan))
    # domain.npz is already a local retained artifact in the real continuation;
    # keep that contract present so return verification exercises the same path.
    (run / "domain.npz").write_bytes(b"domain bytes\n")
    remote_root = tmp_path / "remote-root"
    remote_root.mkdir()
    plan_sha = sha_bytes((run / "plan.json").read_bytes())
    closure = {"schema_version": "goal052-outer-closure-v1", "status": "predictions_closed_before_response",
               "plan_digest": digest, "closure_digest": "c" * 64,
               "predictions": {"target": "predictions/target.npz"}}
    fake = StrictTransport(root, remote_root, digest, plan_sha, sha_bytes(b"source\n"), closure,
                           response_relative, sha_bytes(response), fail_audit, corrupt_return,
                           malformed_runtime)
    args = controller.argparse.Namespace(root=root, remote_host="fake-host", remote_root=str(remote_root),
        run_relative="run", expected_plan_digest=digest, production_hours=1.0, overall_hours=2.0, attempt="001")
    return root, run, args, fake


def test_success_uses_real_receipts_and_gates_response(tmp_path, monkeypatch):
    root, run, args, fake = fixture(tmp_path)
    original = controller.sha256_file
    gates = []
    def tracked(path):
        if Path(path) == root / "data/goal049/canonical.parquet":
            gates.append(fake.audit_passed)
        return original(path)
    monkeypatch.setattr(controller, "sha256_file", tracked)
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 0
    assert gates == [True]
    assert (run / "response-access.json").is_file()
    assert json.loads((run / "returned-files.json").read_text())["remote_sha256"]["predictions/target.npz"] == sha_bytes(b"prediction bytes\n")
    score_commands = [call[1] for call in fake.calls
                      if call[0] == "ssh" and " dsdm_phase1.goal052_outer score " in call[1]]
    assert score_commands and "PYTHONPATH=" + str(args.remote_root) + "/src" in score_commands[0]
    returned = json.loads((run / "returned-files.json").read_text())
    for relative, expected in {**returned["files"], **returned["control_files"]}.items():
        assert sha_bytes((run / relative).read_bytes()) == expected, relative
    assert returned["control_files_scope"] == "immutable_evidence_written_before_continuation_completion"
    assert "continuation-control-001/status.json" not in returned["control_files"]
    assert "continuation-control-001/heartbeat.json" not in returned["control_files"]


def test_failed_audit_stops_before_response(tmp_path):
    root, run, args, fake = fixture(tmp_path, fail_audit=True)
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 1
    assert not any(call[0] == "rsync" and call[1] == str(root / "data/goal049/canonical.parquet") for call in fake.calls)


def test_malformed_runtime_fails_without_long_poll(tmp_path):
    _root, run, args, fake = fixture(tmp_path, malformed_runtime=True)
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 1
    assert "qualification final file binding" in json.loads((run / "continuation-control-001/complete.json").read_text())["failure"]["reason"]


def test_corrupt_return_fails_hash_gate(tmp_path):
    _root, run, args, fake = fixture(tmp_path, corrupt_return=True)
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 1
    assert "returned artifact hash mismatch" in json.loads((run / "continuation-control-001/complete.json").read_text())["failure"]["reason"]


def test_source_drift_and_replay_protection(tmp_path):
    root, run, args, fake = fixture(tmp_path)
    (root / "source.py").write_bytes(b"drift\n")
    with pytest.raises(controller.ControllerError, match="local source drift"):
        controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None)
    _root, run, args, fake = fixture(tmp_path / "replay")
    (run / "continuation-control-002").mkdir()
    with pytest.raises(controller.ControllerError, match="attempt already exists"):
        controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None)


def test_campaign_cap_is_explicit(tmp_path):
    _root, _run, args, _fake = fixture(tmp_path)
    args.production_hours = 73
    with pytest.raises(controller.ControllerError, match="72 production"):
        controller._validate_args(args)


def test_detached_wrapper_shell_syntax_is_valid():
    launch = controller._detached_stage_command(
        "audit", "printf '%s\\n' harmless", "/tmp/outer-stage",
        "/tmp/outer-stage/stage.log", "/tmp/outer-stage/stage.json", 15.0)
    tokens = shlex.split(launch)
    inner = tokens[tokens.index("-c") + 1]
    checked = subprocess.run(["/bin/sh", "-n", "-c", inner], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr


def test_uncertain_production_launch_is_reconciled_once_and_completes(tmp_path):
    _root, run, args, fake = fixture(tmp_path)
    original_ssh = fake.ssh
    launches = []
    def drop_launch_reply(host, command, timeout):
        result = original_ssh(host, command, timeout)
        if "nohup" in command and "goal052_outer_supervise.py" in command:
            launches.append(command)
            fake._write_remote("run/production-control-001/manifest.json", {
                "schema_version": "goal052-outer-production-control-v1", "attempt": "001",
                "plan_sha256": fake.plan_sha,
                "source_supervisor_sha256": sha_bytes((ROOT / controller.SUPERVISOR_RELATIVE).read_bytes()),
                "args": {"workers": 4, "max_hours": 1.0, "run": str(fake.remote_root / "run")},
            })
            fake._write_remote("run/production-control-001/heartbeat.json", {"stage": "setup", "pid": 4242})
            raise controller.TransportTimeout("synthetic lost launch reply")
        return result
    fake.ssh = drop_launch_reply
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 0
    final = json.loads((run / "continuation-control-001/complete.json").read_text())
    assert len(launches) == 1
    assert final["commands"]["launch"]["reconciled"] is True
    assert final["commands"]["launch"]["return_code"] is None


def test_directory_returns_with_real_rsync_are_flat_and_verified(tmp_path):
    _root, run, args, fake = fixture(tmp_path)
    original_rsync = fake.rsync
    directory_transfers = []
    def real_directory_rsync(source, destination, timeout):
        if ":" in source and Path(source.split(":", 1)[1]).is_dir():
            directory_transfers.append((source, destination))
            assert source.endswith("/") and destination.endswith("/")
            source_path = source.split(":", 1)[1]
            # Simulate a retried directory transfer to an existing destination.
            for _ in range(2):
                result = subprocess.run(["rsync", "-a", source_path, destination], capture_output=True, timeout=timeout)
                assert result.returncode == 0, result.stderr
            return result
        return original_rsync(source, destination, timeout)
    fake.rsync = real_directory_rsync
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 0
    assert len(directory_transfers) == 4
    assert (run / "production-control-001/complete.json").is_file()
    assert not (run / "production-control-001/production-control-001").exists()
    assert not (run / "continuation-control-001/remote-postproduction/audit/audit").exists()


def test_cleanup_signals_only_the_owned_process_group():
    class SignalRecorder:
        def __init__(self):
            self.calls = []
        def ssh(self, host, command, timeout):
            self.calls.append(command)
            return Result(1 if command.startswith("kill -0") else 0)
    transport = SignalRecorder()
    controller._kill_remote_process_group(transport, "fake-host", 4242, time.monotonic, lambda _: None)
    assert transport.calls == ["kill -TERM -- -4242 2>/dev/null || true", "kill -0 -- -4242"]


def test_wrong_auditor_identity_stops_before_response(tmp_path):
    root, _run, args, fake = fixture(tmp_path)
    original_ssh = fake.ssh
    def changed_auditor(host, command, timeout):
        result = original_ssh(host, command, timeout)
        if "nohup" in command and "outer_independent_audit.py" in command:
            path = fake.remote_root / "continuation-control-001/audit/independent-audit.json"
            payload = json.loads(path.read_text())
            payload["auditor"]["sha256"] = "0" * 64
            path.write_bytes(json_bytes(payload))
        return result
    fake.ssh = changed_auditor
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 1
    assert not any(call[0] == "rsync" and call[1] == str(root / "data/goal049/canonical.parquet") for call in fake.calls)


def test_post_scoring_closure_drift_is_rejected_and_access_evidence_returned(tmp_path):
    _root, run, args, fake = fixture(tmp_path)
    original_ssh = fake.ssh
    def drift_after_scoring(host, command, timeout):
        result = original_ssh(host, command, timeout)
        if "nohup" in command and "goal052_outer_report.py" in command:
            path = fake.remote_root / "run/closure.json"
            changed = json.loads(path.read_text())
            changed["unexpected_change"] = True
            path.write_bytes(json_bytes(changed))
        return result
    fake.ssh = drift_after_scoring
    assert controller.continue_campaign(args, transport=fake, sleeper=lambda _seconds: None) == 1
    final = json.loads((run / "continuation-control-001/complete.json").read_text())
    assert "closure changed after independent audit" in final["failure"]["reason"]
    assert (run / "response-access.json").is_file()
    assert (run / "response-access-success.json").is_file()
