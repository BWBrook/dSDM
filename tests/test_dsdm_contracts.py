import json
from pathlib import Path

import pytest

from dsdm.contracts import ContractError, build_plan, load_contract


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "dsdm_synthetic_vertical.json"


def test_contract_and_planner_freeze_exact_axes_and_counts():
    contract = load_contract(CONFIG)
    plan = build_plan(contract)

    assert contract.predictor_count == 28
    assert len(contract.species) == 8
    assert contract.folds == tuple(f"fold{i:02d}" for i in range(5))
    assert len(contract.endpoints) == 7
    assert len(contract.methods) == 6
    assert len(contract.architectures) == 24
    assert len({item.id for item in contract.architectures}) == 24
    assert {item.blocks for item in contract.architectures} == {2, 3, 4}
    assert {item.width for item in contract.architectures} == {64, 128, 256}
    assert {item.bottleneck for item in contract.architectures} == {16, 32, 64}
    assert plan == {
        "architecture_screen_fits": 960,
        "architecture_shortlist_fits": 480,
        "architecture_selection_fits": 1440,
        "auxiliary_fits": 440,
        "combined_declarative_fits": 10280,
        "endpoint_strata": 56,
        "final_lifecycle_fits": 8840,
        "method_fold_strata": 1680,
        "method_strata": 336,
        "target_fits": 8400,
    }


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("predictor_count",), 27),
        (("species", 0), "wrong_species"),
        (("folds", 4), "fold99"),
        (("endpoints", 0), "fraction10/ladder00"),
        (("methods", 0), "wrong_method"),
        (("architecture_registry", 0, "activation"), "relu"),
        (("architecture_selection", "shortlist_size"), 3),
        (("evidence", "outer_attempted"), 1),
        (("sentinel", "expected_total_fits"), 24),
        (("training", "epochs"), 11),
        (("q_linear", "solver"), "liblinear"),
    ],
)
def test_contract_rejects_axis_execution_and_outer_tampering(tmp_path, path, replacement):
    raw = json.loads(CONFIG.read_text())
    cursor = raw
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement
    candidate = tmp_path / "tampered.json"
    candidate.write_text(json.dumps(raw))

    with pytest.raises(ContractError):
        load_contract(candidate)


def test_contract_rejects_unknown_keys(tmp_path):
    raw = json.loads(CONFIG.read_text())
    raw["unapproved"] = True
    candidate = tmp_path / "unknown.json"
    candidate.write_text(json.dumps(raw))

    with pytest.raises(ContractError, match="unknown"):
        load_contract(candidate)
