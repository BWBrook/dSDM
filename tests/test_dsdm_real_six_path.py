from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np
import pytest
import torch

from dsdm.contracts import ArchitectureSpec
from dsdm.real_six_path import (
    BundleError,
    ContractError,
    RunError,
    build_bundle,
    build_plan,
    load_bundle,
    load_config,
    run_sentinel,
    save_bundle,
    test_config,
    validate_bundle,
    validate_run,
    write_run,
)
from dsdm.real_six_path import _fit_q_linear, _prepare_device, _runtime_attestation, _validate_runtime
from dsdm.real_six_path_data import RUNTIME_POLICY
from sklearn.exceptions import ConvergenceWarning


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "dsdm_real_six_path_sentinel.json"


def _arrays(seed: int = 7) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    master_x = rng.normal(size=(32, 77)).astype(np.float32)
    master_y = np.asarray(([0.0, 1.0] * 16), dtype=np.float32)
    arrays: dict[str, np.ndarray] = {}
    for slug, count in (("fraction25", 8), ("fraction50", 16), ("fraction100", 32)):
        indices = np.arange(count)
        stopping = indices % 4 < 2
        discovery = ~stopping
        for role, mask in (("discovery", discovery), ("stopping", stopping), ("replay", np.ones(count, dtype=bool))):
            arrays[f"target_{slug}_x_{role}"] = master_x[:count][mask].copy()
            arrays[f"target_{slug}_y_{role}"] = master_y[:count][mask].copy()
    arrays["target_x_assessment"] = rng.normal(size=(8, 77)).astype(np.float32)
    arrays["target_y_assessment"] = np.asarray([0.0, 1.0] * 4, dtype=np.float32)
    for role, per_species in (("discovery", 4), ("stopping", 2), ("replay", 6)):
        species = np.repeat(np.arange(7, dtype=np.int32), per_species)
        arrays[f"aux_x_{role}"] = rng.normal(size=(len(species), 77)).astype(np.float32)
        arrays[f"aux_y_{role}"] = np.tile(np.asarray([0.0, 1.0], dtype=np.float32), len(species) // 2)
        arrays[f"aux_species_{role}"] = species
    return arrays


def _audit() -> dict[str, object]:
    return {
        "target_excluded": True,
        "pseudoabsence_rows": 0,
        "held_fold_rows": 0,
        "unknown_rows": 0,
        "eligible_folds": ["fold00", "fold02", "fold03", "fold04"],
        "discovery_folds": ["fold00", "fold03", "fold04"],
        "stopping_fold": "fold02",
        "species_weighting": "mean_of_seven_within_species_means",
        "q_linear_weighting": "exact_equal_species_contribution",
        "outer_attempted": 0,
        "outer_opened": 0,
        "source_binding_digest": "a" * 64,
        "subset_membership_digests": {
            "fraction25/ladder00": "b" * 64,
            "fraction50/ladder00": "c" * 64,
            "fraction100/full": "d" * 64,
        },
        "subset_nesting_verified": True,
    }


@pytest.fixture
def config():
    production = load_config(CONFIG, root=ROOT)
    return test_config(
        production,
        ArchitectureSpec("test_resmlp", 1, 8, 4, "constant", 0.0, 1e-3),
        max_epochs=1,
        patience=1,
    )


@pytest.fixture
def bundle(config):
    return build_bundle(config, _arrays(), _audit())


def test_production_contract_and_exact_workload_arithmetic():
    config = load_config(CONFIG, root=ROOT)
    assert config.test_only is False
    assert config.raw["runtime"] == RUNTIME_POLICY
    assert config.raw["training"]["q_linear"] == {
        "penalty": "elasticnet",
        "solver": "saga",
        "C": 1.0,
        "l1_ratio": 0.5,
        "max_iter": 5000,
        "tol": 1e-5,
    }
    assert set(config.source_digests) == {
        "real_six_path", "real_six_path_data", "contracts", "models", "real_data",
        "target_subsets", "modeling_contract", "goal029_production", "uv_lock",
    }
    assert len(config.source_fingerprint) == 64
    assert build_plan(config) == {
        "auxiliary_logical_artifacts": 3,
        "target_logical_artifacts": 18,
        "logical_artifacts": 21,
        "neural_discovery_fits": 20,
        "neural_replay_fits": 20,
        "q_linear_fits": 1,
        "physical_fits": 41,
        "full_target_logical_artifacts": 8400,
        "full_auxiliary_logical_artifacts": 440,
        "full_lifecycle_logical_artifacts": 8840,
        "fits_executed": 0,
    }


def test_authority_digest_drift_fails_closed(tmp_path):
    raw = json.loads(CONFIG.read_text())
    raw["authorities"]["goal033_winner"]["sha256"] = "0" * 64
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ContractError, match="authority"):
        load_config(path, root=ROOT)


def test_execution_source_digest_and_shared_runtime_drift_fail_closed(tmp_path):
    raw = json.loads(CONFIG.read_text())
    raw["execution_sources"]["models"]["sha256"] = "0" * 64
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ContractError, match="authority"):
        load_config(path, root=ROOT)

    production = load_config(CONFIG, root=ROOT)
    torch.set_num_threads(1)
    runtime = _runtime_attestation(torch.device("cpu"))
    runtime["shared"] = {**runtime["shared"], "numpy": "0.0.0"}
    runtime["shared_fingerprint"] = hashlib.sha256(json.dumps(runtime["shared"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    runtime["full"] = {**runtime["full"], "numpy": "0.0.0"}
    with pytest.raises(RunError, match="runtime"):
        _validate_runtime(production, runtime)


def test_bundle_is_numeric_private_content_addressed_and_round_trips(config, bundle, tmp_path):
    path = save_bundle(bundle, tmp_path)
    assert path.name == f"{bundle.digest}.npz"
    loaded = load_bundle(path, config)
    validate_bundle(loaded, config)
    assert loaded.digest == bundle.digest
    with np.load(path, allow_pickle=False) as payload:
        assert all(value.dtype == np.float32 for name, value in payload.items() if name.startswith(("target_", "aux_x_", "aux_y_")))
        assert all(value.dtype == np.int32 for name, value in payload.items() if name.startswith("aux_species_"))
    text = json.dumps(loaded.metadata, sort_keys=True)
    for forbidden in ("/Users/", "grid_cell", "row_id", "tas_cam", "latitude", "longitude", "camera"):
        assert forbidden not in text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_excluded", False),
        ("pseudoabsence_rows", 1),
        ("held_fold_rows", 1),
        ("outer_attempted", 1),
        ("outer_opened", 1),
    ],
)
def test_bundle_rejects_leakage_and_outer_mutations(config, field, value):
    audit = _audit()
    audit[field] = value
    with pytest.raises(BundleError):
        build_bundle(config, _arrays(), audit)


def test_bundle_accepts_unequal_counts_but_requires_all_species_and_equal_total_weights(config):
    unequal = _arrays()
    unequal["aux_species_discovery"][-1] = 5
    accepted = build_bundle(config, unequal, _audit())
    totals = accepted.metadata["auxiliary_species_total_weights"]["discovery"]
    assert len(set(totals)) == 1

    missing = _arrays()
    missing["aux_species_discovery"][missing["aux_species_discovery"] == 6] = 5
    with pytest.raises(BundleError, match="species"):
        build_bundle(config, missing, _audit())


def test_bundle_rejects_nonnested_subsets(config):

    nonnested = _arrays()
    nonnested["target_fraction25_x_replay"][0, 0] += 1
    with pytest.raises(BundleError, match="nested"):
        build_bundle(config, nonnested, _audit())


def test_bundle_digest_and_portable_privacy_tamper_fail(config, bundle, tmp_path):
    path = save_bundle(bundle, tmp_path)
    with np.load(path, allow_pickle=False) as source:
        payload = {name: source[name].copy() for name in source.files}
    payload["target_fraction25_x_replay"][0, 0] += 1
    tampered = tmp_path / "tampered.npz"
    np.savez_compressed(tampered, **payload)
    with pytest.raises(BundleError):
        load_bundle(tampered, config)

    audit = _audit()
    audit["private_source_path"] = "/Users/example/tas_cam/locations.csv"
    with pytest.raises(BundleError, match="privacy"):
        build_bundle(config, _arrays(), audit)


def test_tiny_six_path_run_is_complete_finite_and_repeatable(config, bundle):
    first = run_sentinel(bundle, config, device="cpu")
    second = run_sentinel(bundle, config, device="cpu")
    assert first["status"] == "pass"
    assert first["counts"] == {
        "auxiliary_logical_artifacts": 3,
        "target_logical_artifacts": 18,
        "logical_artifacts": 21,
        "physical_fits": 41,
    }
    assert len(first["artifacts"]) == 21
    assert all(row["finite"] for row in first["artifacts"])
    assert [(r["artifact_id"], r["model_digest"], r["prediction_digest"]) for r in first["artifacts"]] == [
        (r["artifact_id"], r["model_digest"], r["prediction_digest"]) for r in second["artifacts"]
    ]
    assert first["checks"]["frozen_trunk_unchanged"] is True
    assert first["checks"]["legacy_starts_from_pooled"] is True
    assert first["checks"]["multihead_shared_transfer_matched"] is True
    assert first["source_fingerprint"] == config.source_fingerprint
    assert set(first["runtime"]["shared"]) == set(RUNTIME_POLICY)
    assert {"scipy", "scikit_learn", "threadpoolctl"} <= set(first["runtime"]["full"])
    assert first["outer"] == {"attempted": 0, "opened": 0}
    assert "auc" not in json.dumps(first).lower()
    assert "tss" not in json.dumps(first).lower()


def test_run_validator_rejects_receipt_and_frozen_trunk_tamper(config, bundle, tmp_path):
    first = run_sentinel(bundle, config, device="cpu")
    second = run_sentinel(bundle, config, device="cpu")
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    write_run(first, first_path)
    write_run(second, second_path)
    validate_run(first_path, config, bundle, repeat_path=second_path)

    raw = json.loads(first_path.read_text())
    raw["checks"]["frozen_trunk_unchanged"] = False
    body = deepcopy(raw)
    body.pop("receipt_digest")
    from hashlib import sha256

    raw["receipt_digest"] = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    first_path.write_text(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    with pytest.raises(RunError, match="invariant"):
        validate_run(first_path, config, bundle, repeat_path=second_path)

    raw["checks"]["frozen_trunk_unchanged"] = True
    first_path.write_text(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    with pytest.raises(RunError, match="digest"):
        validate_run(first_path, config, bundle)


def test_both_repeat_receipts_get_full_transfer_validation(config, bundle, tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    write_run(run_sentinel(bundle, config, device="cpu"), first_path)
    write_run(run_sentinel(bundle, config, device="cpu"), second_path)
    repeat = json.loads(second_path.read_text())
    legacy = next(row for row in repeat["artifacts"] if row["artifact_id"].endswith("legacy_pooled_finetune"))
    legacy["initial_model_digest"] = "0" * 64
    legacy["replay_initial_model_digest"] = "0" * 64
    body = deepcopy(repeat)
    body.pop("receipt_digest")
    repeat["receipt_digest"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    second_path.write_text(json.dumps(repeat, sort_keys=True, separators=(",", ":")))
    with pytest.raises(RunError, match="legacy pooled transfer"):
        validate_run(first_path, config, bundle, repeat_path=second_path)


def test_q_linear_convergence_warning_fails_closed(config, bundle, monkeypatch):
    from sklearn.linear_model import LogisticRegression

    original = LogisticRegression.fit

    def warned_fit(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        warnings.warn("forced nonconvergence", ConvergenceWarning)
        return result

    monkeypatch.setattr(LogisticRegression, "fit", warned_fit)
    with pytest.raises(RunError, match="convergence warning"):
        _fit_q_linear(bundle)


def test_indexless_cuda_selects_device_zero(monkeypatch):
    selected: list[torch.device] = []
    reset: list[torch.device] = []
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "init", lambda: None)
    monkeypatch.setattr(torch.cuda, "set_device", selected.append)
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", reset.append)

    route = _prepare_device("cuda")

    assert route == torch.device("cuda")
    assert selected == [torch.device("cuda:0")]
    assert reset == [torch.device("cuda:0")]
