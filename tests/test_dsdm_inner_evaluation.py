from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dsdm.inner_evaluation import (
    FoldScores,
    InnerEvaluationError,
    binary_metrics,
    digest_value,
    load_config,
    select_threshold,
    sha256_file,
    validate_tracked_output,
)


def test_goal036_config_freezes_scope_and_outer_boundary():
    config = load_config("config/dsdm_inner_evaluation.json")
    assert len(config.raw["scope"]["species"]) == 8
    assert len(config.raw["scope"]["endpoints"]) == 7
    assert len(config.raw["scope"]["neural_methods"]) == 6
    assert len(config.raw["scope"]["conventional_families"]) == 5
    assert config.raw["evidence"]["outer_attempted"] == 0
    assert config.raw["evidence"]["outer_opened"] == 0


def test_config_mutation_fails_closed(tmp_path):
    raw = json.loads(Path("config/dsdm_inner_evaluation.json").read_text())
    raw["evaluation"]["positive_rule"] = "score_greater_than_threshold"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(InnerEvaluationError, match="evaluation contract"):
        load_config(path, root=Path.cwd())


def test_threshold_matches_frozen_lower_median_rule():
    threshold, maximizers, tss = select_threshold(
        np.asarray([0, 1, 0, 1]),
        np.asarray([0.1, 0.2, 0.8, 0.9]),
    )
    assert tss == pytest.approx(0.5)
    assert threshold == pytest.approx(0.15)
    assert threshold == maximizers[(len(maximizers) - 1) // 2]


def test_binary_metrics_use_ge_rule_and_report_support():
    metrics = binary_metrics([0, 0, 1, 1], [0.1, 0.5, 0.5, 0.9], 0.5)
    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert metrics["tn"] == 1
    assert metrics["fn"] == 0
    assert metrics["n_positive"] == metrics["n_negative"] == 2
    assert metrics["tss"] == pytest.approx(0.5)


def test_classless_metric_is_na_not_manufactured():
    metrics = binary_metrics([1, 1], [0.2, 0.8], 0.5)
    assert metrics["roc_auc"] is None
    assert metrics["tss"] is None
    assert metrics["mcc"] is None
    assert metrics["n_positive"] == 2
    assert metrics["n_negative"] == 0


def test_fold_scores_require_unique_aligned_private_rows():
    FoldScores(("a", "b"), np.asarray([0, 1]), np.asarray([[0.1, 0.9], [0.2, 0.8]]))
    with pytest.raises(InnerEvaluationError, match="row/class"):
        FoldScores(("a", "a"), np.asarray([0, 1]), np.asarray([[0.1, 0.9]]))


def test_tracked_validator_rejects_private_tokens(tmp_path):
    table_names = (
        "fold_metrics.csv", "stratum_metrics.csv", "conventional_selection.csv",
        "contrasts.csv", "endpoint_summary.csv", "contrast_summary.csv",
    )
    for name in table_names:
        (tmp_path / name).write_text("metric\n1\n")
    receipt = {
        "schema_version": "goal036-inner-evaluation-v1",
        "success": True,
        "table_digests": {name: sha256_file(tmp_path / name) for name in table_names},
        "privacy": {"aggregate_only": True, "row_identifiers": False, "coordinates": False, "predictions_tracked": False, "labels_tracked": False},
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    (tmp_path / "summary.json").write_text(json.dumps(receipt, sort_keys=True))
    assert validate_tracked_output(tmp_path)["success"] is True
    (tmp_path / "fold_metrics.csv").write_text('"row_token"\nsecret\n')
    receipt["table_digests"]["fold_metrics.csv"] = sha256_file(tmp_path / "fold_metrics.csv")
    body = dict(receipt)
    body.pop("receipt_digest")
    receipt["receipt_digest"] = digest_value(body)
    (tmp_path / "summary.json").write_text(json.dumps(receipt, sort_keys=True))
    with pytest.raises(InnerEvaluationError, match="private material"):
        validate_tracked_output(tmp_path)
