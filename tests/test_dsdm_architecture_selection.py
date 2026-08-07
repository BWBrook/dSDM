from __future__ import annotations

import json

import numpy as np
import pytest

from dsdm.architecture_selection import (
    SelectionError,
    average_tie_ranks,
    build_task_plan,
    choose_tss_threshold,
    derive_fit_seed,
    load_selection_config,
    rank_architectures,
)


def test_config_is_strict_and_has_exact_workload():
    config = load_selection_config("config/dsdm_architecture_selection.json")
    plan = build_task_plan(config)
    assert plan["screen_logical_evaluations"] == 960
    assert plan["shortlist_logical_evaluations"] == 480
    assert plan["physical_fits"] == 2880
    assert len(config.architectures) == 24


def test_unknown_config_key_fails_closed(tmp_path):
    payload = json.loads(open("config/dsdm_architecture_selection.json").read())
    payload["unexpected"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(SelectionError):
        load_selection_config(path)


def test_seed_derivation_excludes_host_and_stage():
    first = derive_fit_seed(31031, "species_0", "fold02", "fraction100/full", "resmlp00", "fit")
    second = derive_fit_seed(31031, "species_0", "fold02", "fraction100/full", "resmlp00", "fit")
    assert first == second
    assert first != derive_fit_seed(31032, "species_0", "fold02", "fraction100/full", "resmlp00", "fit")


def test_threshold_uses_lower_median_maximizer_and_ge_rule():
    result = choose_tss_threshold(np.array([0, 1, 0, 1]), np.array([0.1, 0.2, 0.8, 0.9]))
    assert result.tss == pytest.approx(0.5)
    assert result.threshold == pytest.approx(0.15)


def test_average_tie_ranks_and_species_balanced_ranking():
    assert average_tie_ranks([0.8, 0.8, 0.2]) == pytest.approx([2.5, 2.5, 1.0])
    metrics = {
        "a": {"s0": {"auc": 0.8, "tss": 0.2}, "s1": {"auc": 0.6, "tss": 0.1}},
        "b": {"s0": {"auc": 0.7, "tss": 0.3}, "s1": {"auc": 0.9, "tss": 0.2}},
    }
    ranked = rank_architectures(metrics)
    assert ranked[0] == "b"


@pytest.mark.parametrize("section,key,value", [
    ("execution", "workers", 4),
    ("execution", "route", "deep_server_cpu"),
    ("runtime", "device", "cuda"),
    ("runtime", "threads", 2),
    ("runtime", "export_environment", "selected_training_runtime"),
    ("scope", "predictor_count", 76),
    ("privacy", "tracked_predictions", True),
    ("evidence", "aggregate_only", False),
])
def test_material_config_mutation_fails_closed(tmp_path, section, key, value):
    payload = json.loads(open("config/dsdm_architecture_selection.json").read())
    payload[section][key] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(SelectionError):
        load_selection_config(path)


def test_authority_key_set_includes_goal033_execution_sources():
    payload = json.loads(open("config/dsdm_architecture_selection.json").read())
    expected = {
        "goal027_protocol", "goal028_decision", "goal031_config", "goal031_decision",
        "goal032_config", "goal032_decision", "goal032_receipt",
        "contracts", "models", "real_data", "real_training",
        "architecture_selection", "architecture_runner",
    }
    assert set(payload["authorities"]) == expected
