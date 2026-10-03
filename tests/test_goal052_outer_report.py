from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from dsdm_phase1.goal052_outer_scoring import (
    EXISTING_ARMS,
    MECHANISTIC_CONTRASTS,
    PRIMARY_CONTRASTS,
    aggregate_regions,
    matched_inner_attenuation,
    score_target_region,
)


_REPORT_SPEC = importlib.util.spec_from_file_location(
    "goal052_outer_report", Path(__file__).resolve().parents[1] / "scripts/goal052_outer_report.py"
)
assert _REPORT_SPEC and _REPORT_SPEC.loader
_REPORT_MODULE = importlib.util.module_from_spec(_REPORT_SPEC)
_REPORT_SPEC.loader.exec_module(_REPORT_MODULE)
render_report = _REPORT_MODULE.render_report
render_scores_file = _REPORT_MODULE.render_scores_file


def _scores(n: int) -> dict[str, np.ndarray]:
    base = np.linspace(0.05, 0.95, n, dtype=np.float64)
    values = {
        "target_only_random_init_resmlp": base,
        "target_plus_q_linear_resmlp": np.clip(base + 0.01, 0, 1),
        "multihead_frozen_trunk": np.clip(base + 0.02, 0, 1),
        "multihead_full_finetune": np.clip(base + 0.03, 0, 1),
        "selected_conventional": np.clip(base + 0.04, 0, 1),
        "selected_conventional_plus_q": np.clip(base + 0.05, 0, 1),
    }
    values["fixed_ensemble"] = 0.5 * (
        values["multihead_full_finetune"] + values["selected_conventional"]
    )
    return values


def _case(target: str, region: str):
    y = np.r_[np.ones(40, dtype=np.int8), np.zeros(120, dtype=np.int8)]
    richness = np.r_[np.r_[np.repeat(5, 20), np.repeat(100, 20)], np.repeat([10, 25, 100], 40)]
    thresholds = {name: 0.5 for name in EXISTING_ARMS}
    return score_target_region(
        target, region, y, richness, np.tile(np.arange(4), 40), _scores(len(y)), thresholds,
        primary=target == "a", regional=True,
    )


def _payload() -> dict:
    results = [_case(target, region) for region in ("NCP", "SEH", "NNC") for target in ("a", "b")]
    # Keep one explicit X20 NA while retaining a region-specific eligible
    # denominator in the aggregate macro.
    x20_name = "multihead_full_finetune_minus_target_only_random_init_resmlp"
    results[1]["x20"]["contrasts"][x20_name] = None
    aggregate = aggregate_regions(
        results, ["a"], {region: ["a", "b"] for region in ("NCP", "SEH", "NNC")}
    )
    inner = {
        "conditions": [
            {
                "target": target,
                "fraction": 100,
                "auxiliary": "full",
                "primary_contrasts": {name: {"delta_mean_fold_roc_auc": 0.1} for name in PRIMARY_CONTRASTS},
                "mechanistic_contrasts": {name: {"delta_mean_fold_roc_auc": 0.1} for name in MECHANISTIC_CONTRASTS},
            }
            for target in ("a", "b")
        ]
    }
    aggregate["matched_inner_attenuation"] = matched_inner_attenuation(aggregate, inner)
    return {
        "schema_version": "goal052-outer-scores-v1",
        "created_utc": "2026-10-03T00:00:00Z",
        "plan_digest": "plan-digest-synthetic",
        "closure_sha256": "closure-sha-synthetic",
        "response_provenance": {"canonical_species_cells_sha256": "response-sha-synthetic"},
        "targets": results,
        "aggregate": aggregate,
        "interpretive_limits": [
            "Synthetic fixture: descriptive values only.",
            "No inferential significance, occupancy, or mechanism claim is licensed.",
        ],
    }


def test_renderer_maps_identity_support_na_and_fixed_ensemble():
    payload = _payload()
    report = render_report(payload, source_sha256="score-sha-synthetic")

    assert "Score JSON SHA256: `score-sha-synthetic`" in report
    assert "Plan digest: `plan-digest-synthetic`" in report
    assert "Closure SHA256: `closure-sha-synthetic`" in report
    assert "## Primary common73 panel" in report
    assert "## X20 sensitivity panel" in report
    assert "Supplementary common three-region intersection" in report
    assert "## Fixed ensemble diagnostic contrasts" in report
    assert "## Headline decomposition" in report
    assert "10–24 contribution" in report
    assert "Fixed ensemble (AUC-only)" in report
    assert "AUC-only" in report
    assert "NA (n=0/1)" in report or "NA (n=0/2)" in report
    assert "Positive / denominator" in report
    assert "10_24" in report and "Background count / share" in report
    assert "No inferential significance, occupancy, or mechanism claim is licensed." in report
    assert "| Fixed ensemble − full fine-tune | 0 (n=1/1) | 0 (n=1/1) | 0/1/1 | consistent nonpositive direction |" in report
    assert "| primary by region | NCP | Fixed ensemble − full fine-tune | 0 | 0 | 0 | 0 | 0 |" in report
    # The scorer returns nested regional attenuation panels.  These rows must
    # retain their numeric inner, outer, and outer-minus-inner values.
    assert "| primary by region / NCP | Full fine-tune − target-only random-init ResMLP | 0.1 | 0 | -0.1 | 1 |" in report
    assert "| regional / NCP | Full fine-tune − target-only random-init ResMLP | 0.1 | 0 | -0.1 | 2 |" in report


def test_renderer_is_deterministic_and_refuses_different_existing_report(tmp_path):
    payload = _payload()
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    scores_path = tmp_path / "scores.json"
    output_path = tmp_path / "outer.md"
    scores_path.write_bytes(raw)

    expected_hash = hashlib.sha256(raw).hexdigest()
    first = render_scores_file(scores_path, output_path)
    assert output_path.read_text(encoding="utf-8") == first
    assert f"Score JSON SHA256: `{expected_hash}`" in first
    assert render_scores_file(scores_path, output_path) == first

    output_path.write_text("different report\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        render_scores_file(scores_path, output_path)


def test_renderer_rejects_wrong_schema_before_rendering():
    payload = _payload()
    payload["schema_version"] = "wrong"
    with pytest.raises(ValueError, match="unsupported score schema"):
        render_report(payload, source_sha256="sha")
