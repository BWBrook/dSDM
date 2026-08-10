from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pytest

from dsdm import predictor_sensitivity as ps


def _source_rows(n=80):
    rows = []
    for index in range(n):
        row = {"grid_cell_id": f"cell{index:03d}", "predictor_complete": "true"}
        for col, name in enumerate(ps.CONTINUOUS):
            row[name] = str(float(index * 0.1 + col + (index % 7) * (col + 1) / 100))
        for name in ps.CATEGORICAL:
            row[name] = "1"
        rows.append(row)
    assignments = [{"grid_cell_id": row["grid_cell_id"], "outer_role": "outer_train", "cv_fold": f"fold{index % 5:02d}"} for index, row in enumerate(rows)]
    return rows, assignments


def test_response_blind_mask_selector_is_shape_preserving_and_audited():
    rows, assignments = _source_rows()
    audit = ps.build_masks(rows, assignments)
    ps.validate_mask_audit(audit)
    assert set(audit["primary"]) == set(ps.FOLDS)
    assert len(audit["jaccard"]) == 10
    for mask in audit["primary"].values():
        assert len(mask["encoded_columns"]) == 77
        assert all(mask["encoded_columns"][25:])
        assert set(ps.MANDATORY_CONTINUOUS).issubset(mask["kept_raw"])
        assert any(name in mask["excluded_raw"] for name in ps.BIOCLIM)


def test_zeroing_preserves_encoded_shape_and_categorical_columns():
    x = np.arange(4 * 77, dtype=np.float32).reshape(4, 77)
    mask = ps.encoded_mask(set(ps.MANDATORY_CONTINUOUS) | set(ps.CATEGORICAL) | {"annmeantemp"})
    reduced = ps.apply_encoded_mask(x, mask)
    assert reduced.shape == x.shape
    assert np.array_equal(reduced[:, 25:], x[:, 25:])
    assert np.all(reduced[:, ~mask] == 0)


def test_auxiliary_views_are_zeroed_and_compact_leaf_is_atomic(tmp_path: Path):
    mask = ps.encoded_mask(set(ps.MANDATORY_CONTINUOUS) | set(ps.CATEGORICAL) | {"annmeantemp"})
    arrays = {"x_held": np.ones((2, 77), dtype=np.float32), "aux_x_replay": np.ones((2, 77), dtype=np.float32), "aux_species_replay": np.zeros(2, dtype=np.int32)}
    @dataclass(frozen=True)
    class FakeBundle:
        arrays: dict
    masked = ps.apply_mask_to_case(FakeBundle(arrays), mask)
    assert np.all(masked.arrays["aux_x_replay"][:, ~mask] == 0)
    identity = {"stage": "screen", "species": "thylogale_billardierii", "held_fold": "fold00", "seed": 31031, "mask_digest": ps.digest_value(mask.astype(int).tolist()), "bundle_digest": "a" * 64, "endpoints": list(ps.SCREEN_ENDPOINTS), "methods": [ps.TARGET_METHOD, ps.MULTIHEAD_METHOD], "config_digest": "b" * 64, "source_fingerprint": "c" * 64, "runtime_digest": "d" * 64}
    path = tmp_path / "leaf"
    artifacts = [{"logical_artifacts": 1, "physical_fits": 2, "finite": True, "runtime_digest": "d" * 64} for _ in range(7)]
    leaf_metadata = {"artifacts": artifacts, "support_mask_digests": {"auxiliary": "s"}, "reduced_support_mask_digests": {"auxiliary": "s"}}
    ps.write_reduced_leaf(path, identity, {"predictions": np.ones((3, 2, 2), dtype=np.float32), "metadata": leaf_metadata})
    values, metadata = ps.load_reduced_leaf(path)
    assert values.shape == (3, 2, 2) and metadata["identity"] == identity
    with pytest.raises(ps.PredictorSensitivityError):
        ps.write_reduced_leaf(path, identity, {"predictions": np.ones((3, 2, 2), dtype=np.float32), "metadata": leaf_metadata})


def test_stage_gate_and_reserved_seed_rule():
    records = [{"species": species, "endpoint": endpoint, "fold": fold, "seed": "common", "delta_u_auc": 0.1, "delta_u_tss": 0.01, "delta_i_auc": 0.1, "delta_i_tss": 0.01, "per_seed": [{"seed": seed, "delta_u_auc": 0.1, "delta_u_tss": 0.01, "delta_i_auc": 0.1, "delta_i_tss": 0.01} for seed in ps.SCREEN_SEEDS]} for species in ps.SPECIES for endpoint in ps.SCREEN_ENDPOINTS for fold in ps.FOLDS]
    summary = ps.reconstruct_effect_lanes(records)
    assert ps.screen_gate(summary["delta_u"])
    with pytest.raises(ps.PredictorSensitivityError):
        ps.assert_confirmation_eligible({"eligible": False, **summary["delta_u"]})
    assert not ps.confirmation_gate({"positive_endpoints": 4, "positive_species": 5, "positive_reserved_seeds": 1, "aggregate_tss": 0})


def test_confirmation_decision_table_and_context_is_non_gating():
    screen = {
        "receipt_digest": "screen-receipt",
        "eligible_delta_u": False,
        "eligible_delta_i": True,
    }
    confirmation = {
        "screen_receipt_digest": "screen-receipt",
        "screen_eligibility": {
            "eligible_delta_u": False,
            "eligible_delta_i": True,
        },
        "eligible_delta_u": True,
        "eligible_delta_i": False,
        "conventional_context": {"mean_delta": 999.0},
    }
    assert ps.decision_table(screen, confirmation) == "retain_full28"

    confirmation["eligible_delta_i"] = True
    confirmation["effective_eligible_delta_i"] = True
    assert ps.decision_table({**screen, "eligible_delta_i": True}, confirmation) == "propose_reduced_panel_transfer"
    confirmation["effective_eligible_delta_i"] = False
    confirmation["raw_eligible_delta_i"] = True
    confirmation["delta_u_guard_passed"] = False
    assert ps.decision_table({**screen, "eligible_delta_i": True}, confirmation) == "retain_full28_delta_i_guard_rejected"
    confirmation["raw_eligible_delta_i"] = False
    confirmation["eligible_delta_u"] = True
    confirmation["screen_eligibility"]["eligible_delta_u"] = True
    assert ps.decision_table({**screen, "eligible_delta_u": True, "eligible_delta_i": True}, confirmation) == "propose_reduced_panel_generalisation"
    confirmation["conventional_context"] = {"mean_delta": -999.0}
    assert ps.decision_table({**screen, "eligible_delta_u": True, "eligible_delta_i": True}, confirmation) == "propose_reduced_panel_generalisation"

    confirmation["screen_eligibility"]["eligible_delta_u"] = True
    with pytest.raises(ps.PredictorSensitivityError, match="screen-lane binding"):
        ps.decision_table(screen, confirmation)


def test_decision_authority_is_exact_sha_bound():
    config_path = Path("config/dsdm_predictor_substrate_sensitivity.json")
    raw = __import__("json").loads(config_path.read_text())
    authority = raw["authorities"]["goal039_decision"]
    assert authority["path"] == "docs/goals/039-predictor-substrate-sensitivity/Decision.md"
    assert authority["sha256"] == ps.file_digest(authority["path"])


def test_stage_receipts_use_v2_schema():
    source = Path(ps.__file__).read_text(encoding="utf-8")
    assert "goal039-screen-v1" not in source
    assert "goal039-confirmation-v1" not in source
    assert "goal039-screen-v2" in source
    assert "goal039-confirmation-v2" in source


def test_receipt_reconstruction_is_paired_and_delta_lanes_are_distinct():
    reduced = {"a": {"auc": 0.8, "tss": 0.3, "mcc": 0.2}}
    full = {"a": {"auc": 0.7, "tss": 0.1, "mcc": 0.0}}
    reduced_target = {"a": {"auc": 0.8, "tss": 0.3, "mcc": 0.2}}
    full_target = {"a": {"auc": 0.7, "tss": 0.1, "mcc": 0.0}}
    assert ps.delta_u(reduced, full) == pytest.approx({"auc": 0.1, "tss": 0.2, "mcc": 0.2})
    assert ps.delta_i(reduced, reduced_target, full, full_target) == pytest.approx({"auc": 0.0, "tss": 0.0, "mcc": 0.0})


def test_config_is_self_and_source_bound():
    config = ps.load_config("config/dsdm_predictor_substrate_sensitivity.json")
    assert config.raw["config_digest"] == ps.digest_value({key: value for key, value in config.raw.items() if key != "config_digest"})
    assert config.raw["evidence"]["outer_attempted"] == config.raw["evidence"]["outer_opened"] == 0
    assert {
        "phase1_goal029_production",
        "phase1_inner_cv",
        "phase1_model_adapters",
        "phase1_modeling_contract",
        "phase1_target_subsets",
    } <= set(config.raw["execution_sources"])


def test_public_mask_audit_returns_frozen_receipt_without_rewriting():
    config = ps.load_config("config/dsdm_predictor_substrate_sensitivity.json")
    path = config.root / config.raw["mask_authority"]["path"]
    before = ps.file_digest(path)
    receipt = ps.mask_audit(config)
    assert receipt["config_digest"] == config.raw["mask_authority"]["selector_config_digest"]
    assert ps.file_digest(path) == before == config.raw["mask_authority"]["sha256"]
