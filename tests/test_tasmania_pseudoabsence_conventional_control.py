from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tasmania_pseudoabsence_conventional_control.py"
SPEC = importlib.util.spec_from_file_location("tasmania_conventional_control_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
control = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = control
SPEC.loader.exec_module(control)


def test_exact_thylogale_crossproduct_is_95_non_ann_tasks():
    tasks = control.load_expected_tasks(ROOT / control.SELECTION_REL)
    assert len(tasks) == 95
    assert len({control.task_digest(task) for task in tasks}) == 95
    assert {task.family for task in tasks} == {"random_forest", "hist_gradient_boosting"}
    assert sum(task.family == "random_forest" for task in tasks) == 75
    assert sum(task.family == "hist_gradient_boosting" for task in tasks) == 20
    assert all(task.family != "shallow_ann" for task in tasks)


def test_exact_comparison_rejects_order_and_probability_drift():
    ids = np.asarray(["cell-a", "cell-b"], dtype=str)
    scores = np.asarray([0.125, 0.875], dtype=np.float64)
    assert control.compare_leaf_arrays(ids, scores, ids.copy(), scores.copy()) == 2
    with pytest.raises(control.ControlVerificationError, match="identity_or_order"):
        control.compare_leaf_arrays(ids, scores, ids[::-1], scores)
    changed = scores.copy()
    changed[1] = np.nextafter(changed[1], np.inf)
    with pytest.raises(control.ControlVerificationError, match="probability_mismatch"):
        control.compare_leaf_arrays(ids, scores, ids, changed)


def test_self_digest_and_aggregate_privacy_fail_closed():
    body = {"success": True, "compared_predictions": 24092}
    receipt = {**body, "receipt_digest": control.digest_value(body)}
    assert control.validate_self_digest(receipt, "receipt_digest", "bad") == receipt["receipt_digest"]
    control.assert_aggregate_privacy(receipt)
    tampered = dict(receipt)
    tampered["compared_predictions"] = 1
    with pytest.raises(control.ControlVerificationError, match="bad"):
        control.validate_self_digest(tampered, "receipt_digest", "bad")
    with pytest.raises(control.ControlVerificationError, match="discloses"):
        control.assert_aggregate_privacy({"row_token": json.dumps(["species", "cell"])})


def test_accepted_goal036_authority_chain_is_current():
    hashes = control.verify_accepted_authority(ROOT)
    assert hashes["manifest"] == control.MANIFEST_SHA256
    assert hashes["parquet"] == control.PARQUET_SHA256
    assert hashes["selection"] == control.SELECTION_SHA256
    tasks = control.load_expected_tasks(ROOT / control.SELECTION_REL)
    baseline = control.load_baseline(tasks, ROOT / control.PARQUET_REL)
    assert len(baseline) == 95
    assert sum(len(ids) for ids, _ in baseline.values()) == 24092
