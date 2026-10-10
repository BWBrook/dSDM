"""Independent arithmetic and fail-closed gates for the Tasmania replay."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tasmania_pseudoabsence_audit.py"
SPEC = importlib.util.spec_from_file_location("tasmania_pseudoabsence_audit", SOURCE)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def write_receipt(path: Path, body: dict) -> dict:
    value = dict(body)
    value["receipt_digest"] = audit.digest_value(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def post_assessment_fixture(tmp_path: Path, *, response_sha: str | None = None, baseline_digest: str | None = None):
    response_sha = response_sha or audit.RESPONSE_SHA256
    baseline_digest = baseline_digest or audit.BASELINE_RECEIPT_DIGEST
    private = tmp_path / audit.PRIVATE_REL
    evidence = tmp_path / audit.EVIDENCE_REL
    evidence.mkdir(parents=True)
    closure = write_receipt(private / "prediction-closure.json", {
        "schema_version": "tasmania-pseudoabsence-prediction-closure-v1",
        "status": "accepted", "outer_held_response_labels_read": 0,
        "target_physical_fits": 8125, "smoke_physical_fits": 14,
        "recovery_physical_fits": 200, "baseline_receipt_digest": baseline_digest,
    })
    rows = [
        {"species_id": "thylogale_billardierii", "grid_cell_id": f"g{index}",
         "microcluster": "mc00", "pa": "1", "pa_type": "presence"}
        for index in range(audit.EXPECTED_HELD_ROWS)
    ]
    snapshot = write_receipt(private / "held-response-snapshot.json", {
        "schema_version": "tasmania-sensitivity-held-response-snapshot-v1",
        "prediction_closure_digest": closure["receipt_digest"],
        "response_sha256": response_sha, "rows": rows,
    })
    access = write_receipt(private / "response-access.json", {
        "schema_version": "tasmania-sensitivity-response-access-intent-v1",
        "prediction_closure_digest": closure["receipt_digest"],
        "response_sha256": response_sha, "held_rows_parsed": audit.EXPECTED_HELD_ROWS,
        "training_rows_parsed": 0, "response_parses": 1, "canonical_file_opens": 3,
        "integrity_hash_passes": 2, "private_snapshot_receipt_digest": snapshot["receipt_digest"],
    })
    aggregate_names = (
        "paired-performance.csv", "source-specificity.csv", "paired-contrasts.csv",
        "map-comparison.csv", "held-source-counts.csv",
    )
    files = []
    for name in aggregate_names:
        path = evidence / name
        path.write_text("synthetic\n")
        files.append({"path": str(path.relative_to(tmp_path)), "sha256": audit.sha256_file(path)})
    assessment = write_receipt(evidence / "assessment.json", {
        "schema_version": "tasmania-pseudoabsence-sensitivity-assessment-v1", "success": True,
        "prediction_closure_digest": closure["receipt_digest"],
        "response_access_digest": access["receipt_digest"],
        "baseline_receipt_digest": baseline_digest,
        "private_response_snapshot_digest": snapshot["receipt_digest"],
        "outer_held_response_parses": 1, "canonical_response_file_opens": 3,
        "canonical_response_integrity_hash_passes": 2,
        "privacy": {"aggregate_only": True, "tracked_response_rows": False, "tracked_coordinates": False},
        "counts": {"species": 8, "endpoints": 7, "methods": 3,
                   "paired_performance_rows": 168, "map_pairs": 24, "held_rows": 1672},
        "files": files,
    })
    return private, evidence, closure, access, snapshot, assessment


def test_rank_u_auc_uses_average_ties_and_manual_confusion_metrics():
    labels = np.asarray([0, 1, 0, 1])
    scores = np.asarray([0.1, 0.5, 0.5, 0.9])
    assert audit.average_ranks(scores).tolist() == [1.0, 2.5, 2.5, 4.0]
    assert audit.auc_rank_u(labels, scores) == 0.875
    result = audit.confusion(labels, scores, 0.5)
    assert {key: result[key] for key in ("tp", "tn", "fp", "fn")} == {"tp": 2, "tn": 1, "fp": 1, "fn": 0}
    assert result["tss"] == 0.5
    assert result["mcc"] == pytest.approx(1 / np.sqrt(3), abs=1e-15)


def test_threshold_uses_goal036_candidates_and_lower_median_maximizer():
    result = audit.select_threshold([0, 1, 0, 1], [0.2, 0.4, 0.6, 0.8])
    assert result == {
        "threshold": 0.30000000000000004,
        "maximizer_count": 2,
        "maximum_oof_tss": 0.5,
        "candidate_count": 5,
    }
    adjacent = audit.select_threshold([0, 1], [0.5, np.nextafter(0.5, np.inf)])
    assert adjacent["threshold"] == np.nextafter(0.5, np.inf)


def test_source_specificity_retains_zero_denominator_as_na():
    result = audit.source_specificity(
        [0, 1], ["survey_supported_absence", "presence"], [0.2, 0.8], 0.5,
    )
    assert result["survey_supported_absence"] == {"true_negative": 1, "denominator": 1, "specificity": 1.0}
    assert result["pseudoabsence"] == {"true_negative": 0, "denominator": 0, "specificity": None}


def test_seed_mean_is_float64_identity_joined_and_refuses_missing_seed():
    ids = np.asarray(["a", "b", "c"])
    records = [
        (2, np.asarray(["c", "a", "b"]), np.asarray([0.9, 0.1, 0.5], dtype=np.float32)),
        (1, np.asarray(["b", "c", "a"]), np.asarray([0.3, 0.7, 0.2], dtype=np.float32)),
    ]
    result = audit.seed_mean(records, (1, 2), ids, label="synthetic")
    expected = np.mean(np.asarray([
        np.asarray([0.2, 0.3, 0.7], dtype=np.float32),
        np.asarray([0.1, 0.5, 0.9], dtype=np.float32),
    ], dtype=np.float64), axis=0)
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, expected)
    with pytest.raises(audit.AuditError, match="seed_count_mismatch"):
        audit.seed_mean(records[:1], (1, 2), ids, label="synthetic")


def test_actual_conventional_selected_strata_have_supported_seed_contracts():
    preparation_path = (
        ROOT
        / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private/conventional/preparation.json"
    )
    preparation = audit.read_receipt(preparation_path)
    selected = preparation.get("selected_strata")
    assert isinstance(selected, list) and len(selected) == len(audit.SPECIES) * len(audit.ENDPOINTS)

    family_counts = {}
    for stratum in selected:
        family = stratum["family"]
        family_counts[family] = family_counts.get(family, 0) + 1
        rows = [{"task": {"family": family, "candidate": stratum["candidate"]}}]
        assert audit.expected_group_seeds(rows, neural=False) == tuple(stratum["seeds"])

    assert family_counts == {
        "elastic_net": 1,
        "hist_gradient_boosting": 10,
        "random_forest": 24,
        "shallow_ann": 21,
    }


def test_map_ties_linear_quantiles_and_canonical_top_boundary():
    ids = np.asarray(["d", "b", "a", "c"])
    before = np.asarray([0.1, 0.7, 0.7, 0.7])
    after = np.asarray([0.1, 0.6, 0.5, 0.9])
    row = audit.map_summary(ids, before, after, top_count=2, expected_cells=4)
    assert row["top_decile_intersection"] == 1
    displacement = 100 * (audit.average_ranks(after) - audit.average_ranks(before)) / 3
    assert row["rank_displacement_q025_percentile_points"] == audit.linear_quantile(displacement, 0.025)
    reorder = np.asarray([3, 0, 2, 1])
    assert row == audit.map_summary(ids[reorder], before[reorder], after[reorder], top_count=2, expected_cells=4)
    constant = audit.map_summary(["a", "b"], [0.5, 0.5], [0.4, 0.4], top_count=1, expected_cells=2)
    assert constant["spearman_rho"] is None
    assert constant["spearman_na_reason"] == "constant_probability_map"


def test_receipt_and_bound_file_tampering_are_rejected(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    body = {"status": "accepted"}
    receipt_path.write_text(json.dumps({**body, "receipt_digest": audit.digest_value(body)}))
    assert audit.read_receipt(receipt_path)["status"] == "accepted"
    receipt_path.write_text(json.dumps({"status": "changed", "receipt_digest": audit.digest_value(body)}))
    with pytest.raises(audit.AuditError, match="receipt_digest_mismatch"):
        audit.read_receipt(receipt_path)

    source = tmp_path / "source.json"
    source.write_text("original")
    record = [{"role": "closure", "path": "source.json", "sha256": audit.sha256_file(source)}]
    audit.validate_bound_records(tmp_path, record, label="synthetic")
    source.write_text("tampered")
    with pytest.raises(audit.AuditError, match="sha256_mismatch"):
        audit.validate_bound_records(tmp_path, record, label="synthetic")


def test_startup_refuses_before_source_validation_or_response_access(tmp_path):
    called = False

    def prohibited(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("source validation should not start")

    with pytest.raises(audit.AuditError, match="explicit_execute_gate"):
        audit.verify(tmp_path, execute=False, source_validator=prohibited)
    with pytest.raises(audit.AuditError, match="post_assessment_gate_missing"):
        audit.verify(tmp_path, execute=True, source_validator=prohibited)
    assert called is False
    source_text = SOURCE.read_text()
    assert "response_partitioned.csv" not in source_text
    assert "tasmania_pseudoabsence_assessment" not in source_text


def test_comparison_uses_exact_thresholds_but_tight_float_tolerance():
    assert audit.equal_value(0.2, 0.2 + 5e-13)
    assert not audit.equal_value(0.2, 0.2 + 2e-12)
    assert not audit.equal_value(0.2, np.nextafter(0.2, np.inf), exact=True)


def test_post_assessment_gate_binds_frozen_response_and_baseline(tmp_path):
    private, evidence, closure, access, snapshot, assessment = post_assessment_fixture(tmp_path)
    observed = audit.validate_post_assessment_gate(tmp_path, private, evidence)
    assert [row["receipt_digest"] for row in observed] == [
        closure["receipt_digest"], access["receipt_digest"],
        snapshot["receipt_digest"], assessment["receipt_digest"],
    ]

    wrong = tmp_path / "wrong-response"
    private, evidence, *_ = post_assessment_fixture(wrong, response_sha="0" * 64)
    with pytest.raises(audit.AuditError, match="response_access_source_binding_invalid"):
        audit.validate_post_assessment_gate(wrong, private, evidence)

    wrong = tmp_path / "wrong-baseline"
    private, evidence, *_ = post_assessment_fixture(wrong, baseline_digest="f" * 64)
    with pytest.raises(audit.AuditError, match="baseline_binding_invalid"):
        audit.validate_post_assessment_gate(wrong, private, evidence)


def test_failed_assessment_refuses_before_private_snapshot_parse(tmp_path, monkeypatch):
    private, evidence, *_values, assessment = post_assessment_fixture(tmp_path)
    body = dict(assessment)
    body.pop("receipt_digest")
    body["success"] = False
    write_receipt(evidence / "assessment.json", body)
    original = audit.read_receipt
    reads = []

    def observed(path):
        reads.append(Path(path).name)
        return original(path)

    monkeypatch.setattr(audit, "read_receipt", observed)
    with pytest.raises(audit.AuditError, match="assessment_not_complete"):
        audit.validate_post_assessment_gate(tmp_path, private, evidence)
    assert reads == ["prediction-closure.json", "assessment.json"]


def test_primary_authority_rebuild_detects_normalized_primary_tamper():
    _receipt, _closure, primary, _selected = audit.load_primary_authority(ROOT)
    panels = {
        species: {key: np.array(value, copy=True) for key, value in arrays.items()}
        for species, arrays in primary.items()
    }
    audit.validate_primary_panels(panels, primary)
    panels["dasyurus_viverrinus"]["primary_scores"][0, 0, 0] += 1e-9
    with pytest.raises(audit.AuditError, match="primary_scores_changed"):
        audit.validate_primary_panels(panels, primary)


def test_thylogale_exact_negative_control_inventory_and_arrays():
    values = {
        "primary_scores": np.zeros((7, 3, 2)), "sensitivity_scores": np.zeros((7, 3, 2)),
        "primary_thresholds": np.zeros((7, 3)), "sensitivity_thresholds": np.zeros((7, 3)),
        "primary_map_scores": np.zeros((3, 4)), "sensitivity_map_scores": np.zeros((3, 4)),
    }
    closure = {"thylogale_exact_negative_controls": {"held_scores": 21, "thresholds": 21, "maps": 3}}
    audit.validate_thylogale_negative_control(closure, {"thylogale_billardierii": values})
    values["sensitivity_map_scores"][0, 0] = 0.1
    with pytest.raises(audit.AuditError, match="negative_control_failed:map_scores"):
        audit.validate_thylogale_negative_control(closure, {"thylogale_billardierii": values})


def test_snapshot_identity_and_patch_binding():
    panels = {}
    rows = []
    for index, species in enumerate(audit.SPECIES):
        cell = f"g{index}"
        panels[species] = {"grid_cell_id": np.asarray([cell]), "patch": np.asarray(["mc00"])}
        rows.append({"species_id": species, "grid_cell_id": cell, "microcluster": "mc00", "pa": "0", "pa_type": "pseudoabsence"})
    indexed = audit.snapshot_index({"rows": rows}, panels)
    assert len(indexed) == len(audit.SPECIES)
    rows[0]["microcluster"] = "mc99"
    with pytest.raises(audit.AuditError, match="patch_mismatch"):
        audit.snapshot_index({"rows": rows}, panels)


def test_primary_metric_anchor_rejects_coherent_snapshot_label_tamper(monkeypatch):
    monkeypatch.setattr(audit, "SPECIES", ("sp",))
    monkeypatch.setattr(audit, "ENDPOINTS", ("ep",))
    monkeypatch.setattr(audit, "METHODS", ("target_only_resmlp",))
    cells = np.asarray(["a", "b", "c", "d"])
    panels = {"sp": {
        "grid_cell_id": cells, "patch": np.asarray(["mc0", "mc0", "mc1", "mc1"]),
        "primary_scores": np.asarray([[[0.1, 0.4, 0.6, 0.9]]]),
        "primary_thresholds": np.asarray([[0.5]]),
    }}
    snapshot = {
        ("sp", "a"): {"pa": "0", "pa_type": "survey_supported_absence", "microcluster": "mc0"},
        ("sp", "b"): {"pa": "0", "pa_type": "pseudoabsence", "microcluster": "mc0"},
        ("sp", "c"): {"pa": "1", "pa_type": "presence", "microcluster": "mc1"},
        ("sp", "d"): {"pa": "1", "pa_type": "presence", "microcluster": "mc1"},
    }
    receipt = {
        "response_counts": [{"species": "sp", "n": 4, "n_positive": 2, "n_negative": 2,
                             "patch_counts": {"mc0": 2, "mc1": 2, "mc2": 0}}],
        "metrics": [{"scope": "pooled", "species": "sp", "endpoint": "ep",
                     "model": "target_only_resmlp", "n": 4, "tp": 2, "tn": 2,
                     "fp": 0, "fn": 0, "threshold": 0.5, "roc_auc": 1.0,
                     "tss": 1.0, "mcc": 1.0}],
    }
    audit.validate_primary_metrics_and_response_counts(receipt, panels, snapshot, {})
    snapshot[("sp", "a")] = {"pa": "1", "pa_type": "presence", "microcluster": "mc0"}
    with pytest.raises(audit.AuditError, match="baseline_response_counts_mismatch"):
        audit.validate_primary_metrics_and_response_counts(receipt, panels, snapshot, {})
