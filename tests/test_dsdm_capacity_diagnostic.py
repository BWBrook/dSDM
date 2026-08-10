from pathlib import Path

import numpy as np
import pytest

from dsdm import capacity_diagnostic as cd


def test_variant_parameter_counts_and_registry():
    assert cd.parameter_count(cd.VARIANTS["control"]) == 60865
    assert cd.parameter_count(cd.VARIANTS["wide512"]) == 439681
    assert cd.parameter_count(cd.VARIANTS["deep6"]) == 111361
    assert cd.parameter_count(cd.VARIANTS["deepwide6"]) == 837889
    assert cd.parameter_count(cd.VARIANTS["deepwide6_drop10"]) == 837889


def test_plan_arithmetic_and_scope():
    plan = cd.build_plan()
    assert plan == {
        "new_atomic_cells": 480,
        "logical_lifecycles": 1440,
        "physical_fits": 2880,
        "control_reused": True,
        "species": 8,
        "folds": 5,
        "seeds": 3,
        "variants": 4,
    }


def test_common_seed_metrics_and_gate():
    y = np.asarray([0, 1, 0, 1], dtype=np.int8)
    predictions = np.asarray(
        [[0.1, 0.8, 0.2, 0.7], [0.2, 0.7, 0.3, 0.6], [0.1, 0.9, 0.2, 0.8]],
        dtype=np.float32,
    )
    score = cd.average_common_seed_predictions(predictions)
    assert np.allclose(score, [0.13333334, 0.8, 0.23333333, 0.7])
    metrics = cd.binary_metrics(y, score, 0.5)
    assert metrics["auc"] == pytest.approx(1.0)
    assert metrics["tss"] == pytest.approx(1.0)
    row = {"median_species_d_auc": 0.01, "median_species_l_auc": 0.02,
           "species_d_auc_positive": 5, "seed_d_auc_positive": 2,
           "median_species_d_tss": 0.0}
    assert cd.eligibility_gate(row)
    row["seed_d_auc_positive"] = 1
    assert not cd.eligibility_gate(row)


def test_config_loads_and_binds_stage1_contract():
    config = cd.load_config("config/dsdm_capacity_diagnostic.json")
    assert config.raw["scope"]["fractions"] == ["fraction100/full"]
    assert config.raw["execution"]["logical_lifecycles"] == 1440
    assert config.raw["privacy"]["outer_attempted"] == 0


def test_rank_eligible_uses_frozen_tie_breaks():
    rows = [
        {"variant": "wide512", "median_species_d_auc": .2, "mean_species_d_auc": .2,
         "median_species_d_tss": .1, "parameter_count": 439681},
        {"variant": "deep6", "median_species_d_auc": .2, "mean_species_d_auc": .2,
         "median_species_d_tss": .1, "parameter_count": 111361},
    ]
    assert cd.rank_eligible(rows)[0]["variant"] == "deep6"


def test_production_target_view_uses_flat_prepared_keys():
    prepared = {"target": {"target_fraction100_full_x_discovery": np.ones((2, 3), dtype=np.float32), "target_fraction100_full_x_stopping": np.ones((2, 3), dtype=np.float32), "target_fraction100_full_x_replay": np.ones((2, 3), dtype=np.float32), "target_fraction100_full_x_held": np.ones((1, 3), dtype=np.float32)}}
    raw = {"target_fraction100_full_y_discovery": np.array([0, 1], dtype=np.float32), "target_fraction100_full_y_stopping": np.array([0, 1], dtype=np.float32), "target_fraction100_full_y_replay": np.array([0, 1], dtype=np.float32)}
    target, y = cd._target_arrays(prepared, raw)
    assert target["held"].shape == (1, 3) and len(y) == 3


def test_seed_gate_uses_species_balanced_mean_not_species_count():
    assert cd.seed_gate_count({31031: [0.01] * 8, 31032: [0.01, -0.02] * 4, 31033: [-0.01] * 8}) == 1


def test_config_runtime_mutation_fails_closed(tmp_path: Path):
    import json
    payload = json.loads(Path("config/dsdm_capacity_diagnostic.json").read_text())
    payload["runtime"]["route"] = "wrong"
    path = tmp_path / "capacity.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="runtime drift"):
        cd.load_config(path, root=Path("."))


def test_control_sentinel_slice_digest_shape_is_explicit():
    values = np.arange(3 * 2 * 4, dtype=np.float32).reshape(3, 2, 4)
    sliced = cd.control_sentinel_slice(values)
    assert sliced.shape == (2, 4)
    assert np.array_equal(sliced, values[0])


def test_stage2_contract_is_frozen_and_conditional():
    config = cd.load_config("config/dsdm_capacity_diagnostic.json")
    stage2 = config.raw["stage2"]
    assert stage2["status"] == "frozen_conditional"
    assert stage2["execution"] == {"atomic_cases": 40, "logical_artifacts": 8840, "physical_fits_minimum": 17640, "physical_fits_maximum": 17680}
    assert stage2["confirmation"]["seeds"] == [31034, 31035]


def test_lifecycle_digest_tamper_fails_even_when_boolean_claim_stays_true():
    digest = "a" * 64
    diagnostics = [
        {"role": "auxiliary_multihead", "fit_seed": 31031, "initial_model_digest": digest, "replay_initial_model_digest": digest, "initial_head_digest": digest, "initial_shared_digest": digest, "final_shared_digest": digest, "selected_epoch": 1, "replay_epochs": 1, "discovery_executed_epochs": 1, "wall_seconds": 0.0},
        {"role": "target_only_resmlp", "fit_seed": 123, "initial_model_digest": digest, "replay_initial_model_digest": digest, "initial_head_digest": digest, "initial_shared_digest": digest, "final_shared_digest": digest, "selected_epoch": 1, "replay_epochs": 1, "discovery_executed_epochs": 1, "wall_seconds": 0.0},
        {"role": "multihead_full_finetune", "fit_seed": 123, "initial_model_digest": digest, "replay_initial_model_digest": digest, "initial_head_digest": digest, "initial_shared_digest": digest, "final_shared_digest": digest, "selected_epoch": 1, "replay_epochs": 1, "discovery_executed_epochs": 1, "wall_seconds": 0.0},
    ]
    identity = {"seed": 31031, "fit_seed": 123}
    checks = {"auxiliary_reset": True, "target_reset": True, "common_target_head": True, "multihead_shared_transfer": True}
    cd._validate_lifecycle_diagnostics(diagnostics, checks, identity)
    diagnostics[2]["initial_shared_digest"] = "b" * 64
    with pytest.raises(ValueError, match="transfer checks"):
        cd._validate_lifecycle_diagnostics(diagnostics, checks, identity)


def test_control_threshold_postprocessing_maps_canonical_method_field():
    assert cd._prediction_field("target_only") == "target_only"
    assert cd._prediction_field("multihead_full_finetune") == "multihead"
