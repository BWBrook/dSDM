"""Focused qualification-repeat tests for the response-free outer auditor."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AUDITOR_PATH = ROOT / "scripts" / "goal052_outer_independent_audit.py"


def _auditor():
    spec = importlib.util.spec_from_file_location("goal052_outer_independent_audit_test", AUDITOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def _qualification_fixture(tmp_path: Path):
    audit = _auditor()
    run = tmp_path / "run"
    plan = {"plan_digest": "p" * 64, "sources": {"source.py": "s" * 64}}
    canary_rel = "qualification/canary.json"
    profile_rel = "qualification/profile.json"
    fingerprint = "f" * 64
    ann = {"family": "shallow_ann", "iterations": 1, "model_size_bytes": 49050,
           "score_digest": "d" * 64, "state_digest": "a" * 64}
    repeats = [
        {"repeat": 0, "pid": 101, "runtime_seconds": 1.0, "conventional": {"ann02": dict(ann)}},
        {"repeat": 1, "pid": 102, "runtime_seconds": 2.0, "conventional": {"ann02": dict(ann)}},
    ]
    canary = {"schema_version": audit.RUNTIME_SCHEMA, "status": audit.CANARY_STATUS,
              "plan_digest": plan["plan_digest"], "runtime_fingerprint": fingerprint,
              "code_hashes": plan["sources"], "workers_tested": 2,
              "deterministic_repeats": True, "repeats": repeats,
              "outer_response_rows_read": 0}
    profile = {"schema_version": audit.RUNTIME_SCHEMA, "status": audit.PROFILE_STATUS,
               "plan_digest": plan["plan_digest"], "runtime_fingerprint": fingerprint,
               "code_hashes": plan["sources"], "qualified_workers": 2,
               "peak_rss_bytes": 1000, "outer_response_rows_read": 0}
    _write(run / canary_rel, canary)
    _write(run / profile_rel, profile)
    canary_sha = audit.sha256_file(run / canary_rel)
    profile_sha = audit.sha256_file(run / profile_rel)
    final = {"schema_version": audit.RUNTIME_SCHEMA, "status": audit.QUALIFIED_STATUS,
             "plan_digest": plan["plan_digest"], "runtime_fingerprint": fingerprint,
             "qualified_workers": 2, "canary_workers_tested": 2,
             "canary": canary_rel, "profile": profile_rel,
             "canary_sha256": canary_sha, "profile_sha256": profile_sha,
             "files": {canary_rel: canary_sha, profile_rel: profile_sha},
             "outer_response_rows_read": 0}
    final_rel = "qualification/final.json"
    _write(run / final_rel, final)
    return audit, run, plan, final_rel


def _validate(audit, run, plan, final_rel):
    return audit.validate_qualification(run, final_rel, audit.sha256_file(run / final_rel), plan, {})


def test_validation_allows_only_ann_serialized_size_variation(tmp_path):
    audit, run, plan, final_rel = _qualification_fixture(tmp_path)
    canary_path = run / "qualification/canary.json"
    canary = json.loads(canary_path.read_text())
    canary["repeats"][1]["conventional"]["ann02"]["model_size_bytes"] = 49062
    _write(canary_path, canary)
    final_path = run / final_rel
    final = json.loads(final_path.read_text())
    final["canary_sha256"] = audit.sha256_file(canary_path)
    final["files"]["qualification/canary.json"] = final["canary_sha256"]
    _write(final_path, final)
    assert _validate(audit, run, plan, final_rel)["status"] == audit.QUALIFIED_STATUS


@pytest.mark.parametrize("field", ["state_digest", "score_digest", "iterations"])
def test_validation_rejects_ann_numeric_or_iteration_drift(tmp_path, field):
    audit, run, plan, final_rel = _qualification_fixture(tmp_path)
    canary_path = run / "qualification/canary.json"
    canary = json.loads(canary_path.read_text())
    canary["repeats"][1]["conventional"]["ann02"][field] = "b" * 64 if field == "state_digest" else ("changed" if field == "score_digest" else 2)
    _write(canary_path, canary)
    final_path = run / final_rel
    final = json.loads(final_path.read_text())
    final["canary_sha256"] = audit.sha256_file(canary_path)
    final["files"]["qualification/canary.json"] = final["canary_sha256"]
    _write(final_path, final)
    with pytest.raises(audit.AuditError, match="canary_repeat_drift"):
        _validate(audit, run, plan, final_rel)


def test_validation_rejects_missing_ann_state_digest(tmp_path):
    audit, run, plan, final_rel = _qualification_fixture(tmp_path)
    canary_path = run / "qualification/canary.json"
    canary = json.loads(canary_path.read_text())
    del canary["repeats"][1]["conventional"]["ann02"]["state_digest"]
    _write(canary_path, canary)
    final_path = run / final_rel
    final = json.loads(final_path.read_text())
    final["canary_sha256"] = audit.sha256_file(canary_path)
    final["files"]["qualification/canary.json"] = final["canary_sha256"]
    _write(final_path, final)
    with pytest.raises(audit.AuditError, match="canary_ann_state_digest_invalid"):
        _validate(audit, run, plan, final_rel)


def test_validation_rejects_invalid_ann_state_digest(tmp_path):
    audit, run, plan, final_rel = _qualification_fixture(tmp_path)
    canary_path = run / "qualification/canary.json"
    canary = json.loads(canary_path.read_text())
    canary["repeats"][1]["conventional"]["ann02"]["state_digest"] = "invalid"
    _write(canary_path, canary)
    final_path = run / final_rel
    final = json.loads(final_path.read_text())
    final["canary_sha256"] = audit.sha256_file(canary_path)
    final["files"]["qualification/canary.json"] = final["canary_sha256"]
    _write(final_path, final)
    with pytest.raises(audit.AuditError, match="canary_ann_state_digest_invalid"):
        _validate(audit, run, plan, final_rel)
