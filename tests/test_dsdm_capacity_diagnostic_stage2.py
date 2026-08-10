import json
from pathlib import Path

import pytest

from dsdm import capacity_diagnostic_stage2 as s2


def test_stage2_config_and_plan_are_frozen():
    config = s2.load_config("config/dsdm_capacity_diagnostic_stage2.json")
    assert config.raw["candidate"] == "wide512"
    assert s2.build_plan() == {"atomic_cases": 40, "logical_artifacts": 8840, "physical_fits_minimum": 17640, "physical_fits_maximum": 17680, "workers": 3}
    assert config.raw["confirmation"]["seeds"] == [31034, 31035]


def test_confirmation_gate_requires_all_prespecified_conditions():
    good = {"median_species_d_auc_positive_endpoints": 4, "species_five_endpoint_mean_positive": 5, "fresh_seed_species_balanced_d_auc_positive": 2, "aggregate_d_tss": 0.0}
    assert s2.confirmation_gate(good)
    bad = dict(good, aggregate_d_tss=-1e-9)
    assert not s2.confirmation_gate(bad)


def test_stage1_advance_binding_fails_closed_on_mutation(tmp_path: Path):
    payload = json.loads(Path("config/dsdm_capacity_diagnostic_stage2.json").read_text())
    payload["candidate"] = "deep6"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="candidate|stage1"):
        s2.load_config(path, root=Path("."))


@pytest.mark.parametrize(("section", "key"), [("architecture", "width"), ("training", "max_epochs"), ("confirmation", "aggregate_d_tss_rule"), ("runtime", "device")])
def test_stage2_contract_sections_are_strictly_frozen(tmp_path: Path, section: str, key: str):
    payload = json.loads(Path("config/dsdm_capacity_diagnostic_stage2.json").read_text())
    payload[section][key] = "mutated" if isinstance(payload[section][key], str) else -1
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="drift"):
        s2.load_config(path, root=Path("."))


def test_confirmation_rule_is_explicit_and_gate_boundary_is_inclusive():
    config = s2.load_config("config/dsdm_capacity_diagnostic_stage2.json")
    assert config.raw["confirmation"]["aggregate_d_tss_rule"] == "equal_species_mean_of_equal_endpoint_mean"
    assert s2.confirmation_gate({"median_species_d_auc_positive_endpoints": 4, "species_five_endpoint_mean_positive": 5, "fresh_seed_species_balanced_d_auc_positive": 2, "aggregate_d_tss": 0.0}) is True


def test_fresh_seed_gate_ignores_exposed_seed_signs():
    values = {31031: [-1.0], 31032: [-1.0], 31033: [-1.0], 31034: [1.0], 31035: [1.0]}
    assert s2.fresh_seed_positive_count(values) == 2


def test_goal036_metric_names_map_to_stage2_receipt_labels():
    assert s2._receipt_metric_values({"roc_auc": 0.75, "tss": 0.2, "mcc": 0.1}) == {"auc": 0.75, "tss": 0.2, "mcc": 0.1}


def test_species_five_endpoint_mapping_reconstructs_positive_count():
    mapping = {f"species{i}": value for i, value in enumerate((0.2, -0.1, 0.3, 0.0, 0.4, -0.2, 0.1, 0.5))}
    assert s2.positive_species_count(mapping) == 5
