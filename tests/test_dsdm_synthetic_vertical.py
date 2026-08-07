from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pytest
import torch

import dsdm.synthetic_vertical as synthetic_vertical
from dsdm.contracts import load_contract
from dsdm.models import MultiHeadResidual, build_residual, clone_state
from dsdm.synthetic_vertical import (
    ReceiptError,
    SyntheticFixture,
    endpoint_rows,
    execute_sentinel,
    main,
    make_fixture,
    summarize_fixture,
    validate_receipt,
    write_run_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "dsdm_synthetic_vertical.json"
CONTRACT = load_contract(CONFIG)


def test_fixture_has_exact_balanced_counts_and_nested_endpoints():
    fixture = make_fixture(CONTRACT)
    summary = summarize_fixture(fixture)

    assert fixture.predictors.shape == (125, 28)
    assert len(fixture.observations) == 1000
    assert summary == {
        "cell_count": 125,
        "record_count": 1000,
        "resolved_count": 800,
        "unknown_count": 200,
        "provenance_counts": {
            "presence": 320,
            "pseudoabsence": 240,
            "survey_supported_absence": 240,
            "unknown": 200,
        },
    }
    for species in CONTRACT.species:
        for fold in CONTRACT.folds:
            rows = [row for row in fixture.observations if row.species == species and row.fold == fold]
            counts = {name: sum(row.provenance == name for row in rows) for name in ("presence", "survey_supported_absence", "pseudoabsence", "unknown")}
            assert counts == {"presence": 8, "survey_supported_absence": 6, "pseudoabsence": 6, "unknown": 5}

    target = CONTRACT.raw["sentinel"]["target"]
    small = endpoint_rows(fixture, target, "fold00", "fraction25/ladder00")
    medium = endpoint_rows(fixture, target, "fold00", "fraction50/ladder00")
    full = endpoint_rows(fixture, target, "fold00", "fraction100/full")
    assert (len(small), len(medium), len(full)) == (20, 40, 80)
    assert {row.cell_index for row in small} < {row.cell_index for row in medium}
    assert {row.cell_index for row in medium} < {row.cell_index for row in full}
    assert [sum(row.provenance == name for row in small) for name in ("presence", "survey_supported_absence", "pseudoabsence")] == [8, 6, 6]
    assert [sum(row.provenance == name for row in medium) for name in ("presence", "survey_supported_absence", "pseudoabsence")] == [16, 12, 12]


def _tampered_fixture(kind):
    fixture = make_fixture(CONTRACT)
    predictors = fixture.predictors.copy()
    observations = list(fixture.observations)
    if kind == "unknown_label":
        index = next(i for i, row in enumerate(observations) if row.provenance == "unknown")
        observations[index] = replace(observations[index], label=0.0)
    elif kind == "provenance_label":
        index = next(i for i, row in enumerate(observations) if row.provenance == "presence")
        observations[index] = replace(observations[index], label=0.0)
    elif kind == "fold_cell":
        observations[0] = replace(observations[0], fold="fold04")
    elif kind == "duplicate_missing":
        observations[0] = observations[1]
    elif kind == "predictor_mismatch":
        observations[0] = replace(observations[0], predictors=observations[0].predictors + 1.0)
    elif kind == "nonfinite_predictor":
        predictors[0, 0] = np.nan
    else:
        raise AssertionError(kind)
    return SyntheticFixture(predictors, tuple(observations))


@pytest.mark.parametrize(
    "kind",
    ["unknown_label", "provenance_label", "fold_cell", "duplicate_missing", "predictor_mismatch", "nonfinite_predictor"],
)
def test_fixture_validator_rejects_one_field_observation_and_predictor_tampering(kind):
    from dsdm.synthetic_vertical import FixtureError, validate_fixture

    with pytest.raises(FixtureError):
        validate_fixture(CONTRACT, _tampered_fixture(kind))


def test_fixture_validator_rejects_broken_ladder_nesting(monkeypatch):
    from dsdm.synthetic_vertical import FixtureError, validate_fixture

    fixture = make_fixture(CONTRACT)
    original = synthetic_vertical.endpoint_rows

    def broken_endpoint_rows(fixture_arg, target, held_fold, endpoint):
        result = list(original(fixture_arg, target, held_fold, endpoint))
        if endpoint == "fraction50/ladder00":
            small = original(fixture_arg, target, held_fold, "fraction25/ladder00")
            victim = small[0]
            full = original(fixture_arg, target, held_fold, "fraction100/full")
            result_cells = {row.cell_index for row in result}
            replacement = next(row for row in full if row.provenance == victim.provenance and row.cell_index not in result_cells)
            victim_index = next(i for i, row in enumerate(result) if row.cell_index == victim.cell_index)
            result[victim_index] = replacement
        return tuple(result)

    monkeypatch.setattr(synthetic_vertical, "endpoint_rows", broken_endpoint_rows)
    with pytest.raises(FixtureError, match="nesting"):
        validate_fixture(CONTRACT, fixture)


def test_invalid_fixture_fails_before_any_fit(monkeypatch):
    from dsdm.synthetic_vertical import FixtureError

    def fitting_must_not_start(*args, **kwargs):
        raise AssertionError("fit started before fixture validation")

    monkeypatch.setattr(synthetic_vertical, "fit_neural_binary", fitting_must_not_start)
    with pytest.raises(FixtureError):
        execute_sentinel(CONTRACT, _tampered_fixture("unknown_label"))


def test_sentinel_executes_six_paths_three_architectures_and_is_deterministic():
    fixture = make_fixture(CONTRACT)
    first = execute_sentinel(CONTRACT, fixture)
    second = execute_sentinel(CONTRACT, fixture)

    assert first.target_fits == 20
    assert first.auxiliary_fits == 3
    assert first.total_fits == 23
    assert first.auxiliary_usable_count == 392
    assert first.finite_output_fits == 20
    assert first.method_fits == {method: 3 for method in CONTRACT.methods}
    assert first.architectures == ("resmlp00", "resmlp01", "resmlp23")
    assert first.execution_sha256 == second.execution_sha256


def test_target_preparation_pairs_actual_initial_states_and_fit_seeds():
    from dsdm.synthetic_vertical import prepare_target_model

    spec = CONTRACT.architectures[1]
    pooled = build_residual(spec, 28, 1)
    auxiliary = tuple(name for name in CONTRACT.species if name != "sarcophilus_harrisii")
    multihead = MultiHeadResidual(spec, 28, auxiliary)
    prepared = {
        method: prepare_target_model(
            spec=spec,
            method=method,
            pooled=pooled,
            multihead=multihead,
            target="sarcophilus_harrisii",
            fold="fold00",
            base_seed=31031,
            endpoint="fraction25/ladder00",
            architecture="resmlp01",
        )
        for method in CONTRACT.methods
    }

    assert len({item.fit_seed for item in prepared.values()}) == 1
    frozen_state = clone_state(prepared["multihead_frozen_trunk"].model)
    full_state = clone_state(prepared["multihead_full_finetune"].model)
    assert all(torch.equal(frozen_state[name], full_state[name]) for name in frozen_state)
    target_head = prepared["target_only_resmlp"].model.head.state_dict()
    assert all(torch.equal(target_head[name], frozen_state[f"head.{name}"]) for name in target_head)
    q_linear_state = clone_state(prepared["target_plus_q_linear"].model)
    q_deep_state = clone_state(prepared["target_plus_q_deep"].model)
    assert all(torch.equal(q_linear_state[name], q_deep_state[name]) for name in q_linear_state)
    assert all(
        torch.equal(prepared["legacy_pooled_finetune"].model.state_dict()[name], pooled.state_dict()[name])
        for name in pooled.state_dict()
    )


def test_plan_run_receipts_are_byte_stable_aggregate_only_and_independently_validated(tmp_path):
    plan_path = tmp_path / "plan.json"
    first_path = tmp_path / "receipt-a.json"
    second_path = tmp_path / "receipt-b.json"

    assert main(["--config", str(CONFIG), "plan", "--output", str(plan_path)]) == 0
    assert json.loads(plan_path.read_text())["fits_executed"] == 0
    first_fixture = make_fixture(CONTRACT)
    second_fixture = make_fixture(CONTRACT)
    first_result = execute_sentinel(CONTRACT, first_fixture)
    second_result = execute_sentinel(CONTRACT, second_fixture)
    write_run_receipt(CONTRACT, first_fixture, first_result, first_path)
    write_run_receipt(CONTRACT, second_fixture, second_result, second_path)
    assert first_path.read_bytes() == second_path.read_bytes()
    validate_receipt(CONTRACT, first_path)

    text = first_path.read_text()
    forbidden = re.compile(
        r"row.?id|cell.?id|grid.?cell|response.?label|prediction|species.?cell|/Users/|data/|tas_cam/|temp/|auc|tss|mcc|accuracy|performance|checkpoint|state_dict",
        re.IGNORECASE,
    )
    assert forbidden.search(text) is None
    receipt = json.loads(text)
    assert receipt["outer_access"] == {"attempted": 0, "opened": 0}
    assert receipt["sentinel"]["total_fits"] == 23
    assert receipt["sentinel"]["execution_sha256"] == first_result.execution_sha256
    assert receipt["fixture"]["sha256"] == first_result.fixture_sha256
    assert receipt["fixture"]["provenance_counts"]["presence"] == 320


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("sentinel", "total_fits", 24),
        ("outer_access", "opened", 1),
        ("contract", "architecture_count", 23),
        ("checks", "privacy", False),
    ],
)
def test_validator_rejects_count_outer_contract_and_privacy_tampering(tmp_path, section, key, value):
    path = tmp_path / "receipt.json"
    fixture = make_fixture(CONTRACT)
    write_run_receipt(CONTRACT, fixture, execute_sentinel(CONTRACT, fixture), path)
    raw = json.loads(path.read_text())
    raw[section][key] = value
    path.write_text(json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(ReceiptError):
        validate_receipt(CONTRACT, path)


def test_validator_rejects_forbidden_row_level_material(tmp_path):
    path = tmp_path / "receipt.json"
    fixture = make_fixture(CONTRACT)
    write_run_receipt(CONTRACT, fixture, execute_sentinel(CONTRACT, fixture), path)
    raw = json.loads(path.read_text())
    raw["row_id"] = "synthetic-1"
    path.write_text(json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(ReceiptError, match="privacy"):
        validate_receipt(CONTRACT, path)


def test_validator_reconstructs_expected_receipt_without_writer_helper(tmp_path, monkeypatch):
    path = tmp_path / "receipt.json"
    fixture = make_fixture(CONTRACT)
    write_run_receipt(CONTRACT, fixture, execute_sentinel(CONTRACT, fixture), path)

    def writer_must_not_be_called(*args, **kwargs):
        raise AssertionError("validator reused writer")

    monkeypatch.setattr(synthetic_vertical, "_run_payload", writer_must_not_be_called)
    validate_receipt(CONTRACT, path)


def test_fabricated_execution_digest_cannot_validate_even_with_valid_receipt_hash(tmp_path):
    path = tmp_path / "fabricated.json"
    fixture = make_fixture(CONTRACT)
    actual = execute_sentinel(CONTRACT, fixture)
    fabricated = replace(actual, execution_sha256="0" * 64)
    write_run_receipt(CONTRACT, fixture, fabricated, path)

    with pytest.raises(ReceiptError, match="semantic"):
        validate_receipt(CONTRACT, path)


def test_tampered_but_structurally_valid_executed_fixture_cannot_validate(tmp_path):
    path = tmp_path / "tampered-fixture.json"
    fixture = make_fixture(CONTRACT)
    predictors = fixture.predictors.copy()
    predictors[:, 0] += np.float32(0.25)
    observations = tuple(
        replace(row, predictors=predictors[row.cell_index].copy())
        for row in fixture.observations
    )
    tampered = SyntheticFixture(predictors, observations)
    result = execute_sentinel(CONTRACT, tampered)
    write_run_receipt(CONTRACT, tampered, result, path)

    with pytest.raises(ReceiptError, match="semantic"):
        validate_receipt(CONTRACT, path)


def test_independent_validator_rejects_rehashed_fabricated_bundle(tmp_path):
    path = tmp_path / "rehashed.json"
    fixture = make_fixture(CONTRACT)
    write_run_receipt(CONTRACT, fixture, execute_sentinel(CONTRACT, fixture), path)
    raw = json.loads(path.read_text())
    raw["sentinel"]["execution_sha256"] = "f" * 64
    raw.pop("receipt_sha256")
    raw["receipt_sha256"] = hashlib.sha256(synthetic_vertical._canonical_bytes(raw)).hexdigest()
    path.write_bytes(synthetic_vertical._canonical_bytes(raw))

    with pytest.raises(ReceiptError, match="semantic"):
        validate_receipt(CONTRACT, path)
