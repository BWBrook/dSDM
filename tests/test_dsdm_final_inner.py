"""Focused contract tests for the lean Goal035 final-inner runner."""

from __future__ import annotations

import hashlib
import json
import warnings
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning

from dsdm.contracts import ENDPOINTS, METHODS, FOLDS, SPECIES
from dsdm.final_inner_data import (
    ENDPOINT_SLUGS,
    SEEDS,
    array_digest,
    build_case_bundle,
    digest_value,
    leaf_identity,
    load_config,
    prepare_case,
    validate_leaf,
    write_leaf,
    load_case_npz,
)
import dsdm.final_inner_runner as runner


def _case() -> tuple[object, dict[str, np.ndarray]]:
    arrays: dict[str, np.ndarray] = {}
    held_x = None
    held_y = None
    for endpoint_index, endpoint in enumerate(ENDPOINTS):
        slug = ENDPOINT_SLUGS[endpoint]
        for role, count in (("discovery", 8), ("stopping", 8), ("replay", 16), ("held", 3)):
            x = np.zeros((count, 77), dtype=np.float32)
            x[:, :25] = np.float32(1.0)
            x[:, 38] = 1.0  # shared target support for nesting fixture
            if endpoint_index == 0 and role == "held":
                x[:, 39] = 1.0  # assessment-only value for q-view check
            y = np.arange(count, dtype=np.float32) % 2
            if role == "held":
                held_x, held_y = x, y
            else:
                arrays[f"target_{slug}_x_{role}"] = x
                arrays[f"target_{slug}_y_{role}"] = y
    held_x[:, 38] = 1.0
    held_x[:, 39] = 1.0
    arrays["x_held"], arrays["y_held"] = held_x, held_y
    for role, count in (("discovery", 14), ("stopping", 14), ("replay", 28)):
        x = np.zeros((count, 77), dtype=np.float32)
        x[:, :25] = 2.0
        x[:, 39] = 1.0  # auxiliary support only
        arrays[f"aux_x_{role}"] = x
        arrays[f"aux_y_{role}"] = np.arange(count, dtype=np.float32) % 2
        arrays[f"aux_species_{role}"] = np.arange(count, dtype=np.int32) % 7
    source_digest = hashlib.sha256(b"synthetic-case").hexdigest()
    return build_case_bundle(SPECIES[0], FOLDS[0], arrays, {"outer_attempted": 0, "outer_opened": 0}, source_digest), arrays


def _identity(bundle, prepared, config):
    return {
        "target": bundle.target,
        "held_fold": bundle.held_fold,
        "held_row_count": int(len(bundle.arrays["x_held"])),
        "bundle_digest": bundle.source_digest,
        "config_digest": config.config_digest,
        "runtime_digest": "a" * 64,
        "architecture": "resmlp13",
        "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}),
        "aux_mask_digest": prepared["auxiliary_mask"].digest,
    }


def test_two_view_masks_keep_training_bytes_and_separate_q_input():
    bundle, arrays = _case()
    prepared = prepare_case(bundle)
    assert prepared["target"]["target_fraction25_ladder00_x_replay"].tobytes() == arrays["target_fraction25_ladder00_x_replay"].tobytes()
    assert prepared["target"]["target_fraction25_ladder00_x_held"][0, 38] == 1.0
    assert prepared["q_inputs"]["fraction25/ladder00/held"][0, 38] == 0.0
    assert prepared["q_inputs"]["fraction25/ladder00/held"][0, 39] == 1.0
    assert prepared["support_overlap"]["fraction25/ladder00"] == 25


def test_nonheld_partition_is_disjoint_and_replays_exact_union():
    for held_index in range(5):
        held = f"fold{held_index:02d}"
        stopping = f"fold{(held_index + 1) % 5:02d}"
        replay = {f"fold{i:02d}" for i in range(5)} - {held}
        discovery = replay - {stopping}
        assert discovery.isdisjoint({stopping, held})
        assert discovery | {stopping} == replay


def test_q_fit_accepts_only_bounded_prediction_stability(monkeypatch):
    class FakeLogisticRegression:
        delta = 0.00005

        def __init__(self, *, max_iter, **kwargs):
            self.max_iter = max_iter

        def fit(self, x, y, sample_weight=None):
            self.classes_ = np.asarray([0.0, 1.0], dtype=np.float32)
            self.coef_ = np.zeros((1, x.shape[1]), dtype=np.float32)
            self.intercept_ = np.zeros(1, dtype=np.float32)
            self.n_iter_ = np.asarray([self.max_iter], dtype=np.int32)
            warnings.warn("iteration ceiling", ConvergenceWarning)
            return self

        def predict_proba(self, x):
            shift = self.delta if self.max_iter == 10000 else 0.0
            positive = np.full(len(x), 0.5 + shift, dtype=np.float32)
            return np.column_stack((1.0 - positive, positive))

        def decision_function(self, x):
            return np.full(len(x), self.delta if self.max_iter == 10000 else 0.0, dtype=np.float32)

    monkeypatch.setattr(runner, "LogisticRegression", FakeLogisticRegression)
    x = np.zeros((14, 77), dtype=np.float32)
    y = np.arange(14, dtype=np.float32) % 2
    species = np.arange(14, dtype=np.int32) % 7
    model, artifact = runner._q_fit(x, y, species, 31031, stability_x=x)
    assert model.max_iter == 10000
    assert artifact["convergence"] is False
    assert artifact["termination_status"] == "prediction_stable_at_iteration_ceiling"
    assert artifact["stability_accepted"] is True
    assert artifact["stability_probability_delta"] <= 0.0001
    assert artifact["physical_fits"] == 2

    FakeLogisticRegression.delta = 0.0002
    with pytest.raises(ValueError, match="prediction stability"):
        runner._q_fit(x, y, species, 31031, stability_x=x)


def test_row_multiset_replay_and_ladder01_02_nesting_fail_closed():
    _, arrays = _case()
    broken_replay = {name: value.copy() for name, value in arrays.items()}
    broken_replay["target_fraction25_ladder02_x_replay"][0, 0] = 99.0
    with pytest.raises(ValueError, match="row.?multiset"):
        build_case_bundle(SPECIES[0], FOLDS[0], broken_replay, {"outer_attempted": 0, "outer_opened": 0}, "a" * 64)
    broken_ladder = {name: value.copy() for name, value in arrays.items()}
    for endpoint in ("fraction25/ladder01", "fraction50/ladder01"):
        broken_ladder[f"target_{ENDPOINT_SLUGS[endpoint]}_x_discovery"][0, 0] = 101.0
        broken_ladder[f"target_{ENDPOINT_SLUGS[endpoint]}_x_replay"][0, 0] = 101.0
    with pytest.raises(ValueError, match="ladder01"):
        build_case_bundle(SPECIES[0], FOLDS[0], broken_ladder, {"outer_attempted": 0, "outer_opened": 0}, "a" * 64)


def test_case_npz_extra_array_fails_before_metadata_or_fit(tmp_path: Path):
    bundle, arrays = _case()
    payload = dict(arrays)
    payload["extra"] = np.zeros(1, dtype=np.float32)
    payload["metadata_json"] = np.frombuffer(b"{}", dtype=np.uint8)
    path = tmp_path / "bad.npz"
    np.savez_compressed(path, **payload)
    with pytest.raises(ValueError, match="array inventory"):
        load_case_npz(path)


def test_atomic_leaf_round_trip_and_corruption_is_rejected(tmp_path: Path):
    bundle, _ = _case()
    config = load_config("config/dsdm_final_inner_lifecycle.json")
    prepared = prepare_case(bundle)
    identity = _identity(bundle, prepared, config)
    predictions = np.full((5, 7, 6, 3), 0.5, dtype=np.float32)
    digest = "a" * 64
    artifacts = []
    def neural(identifier, *, physical=2, model=digest, shared=digest, head=digest, epochs=1, fit_seed=0):
        return {"artifact_id": identifier, "kind": "auxiliary" if identifier.startswith("aux/") else "target", "logical_artifacts": 1, "physical_fits": physical, "selected_epoch": epochs, "discovery_executed_epochs": epochs, "replay_epochs": epochs, "stopping_status": "converged", "initial_model_digest": model, "replay_initial_model_digest": model, "initial_shared_digest": shared, "final_shared_digest": shared, "initial_head_digest": head, "model_digest": model, "prediction_digest": digest, "n_iter": 0, "finite": True, "wall_seconds": 0.0, "fit_seed": fit_seed, "runtime_digest": digest}
    def q_artifact():
        q_seed = int.from_bytes(hashlib.sha256(f"goal035-final-inner|{bundle.target}|{bundle.held_fold}|auxiliary|{SEEDS[0]}|q_linear|resmlp13".encode()).digest()[:4], "big")
        value = neural("aux/q_linear", physical=1, model="not_applicable", shared="not_applicable", head="not_applicable", epochs=0, fit_seed=q_seed)
        value.update({"n_iter": 1, "primary_n_iter": 1, "convergence": True, "termination_status": "converged", "stability_accepted": False, "stability_probability_delta": 0.0, "stability_probability_tolerance": 0.0001, "coefficient_range": {"min": -1.0, "max": 1.0}, "logit_range": {"min": -2.0, "max": 2.0}, "probability_range": {"min": 0.1, "max": 0.9}})
        return value
    for seed in SEEDS:
        artifacts.extend((neural(f"aux/pooled/seed{seed}", fit_seed=seed), neural(f"aux/multihead/seed{seed}", fit_seed=seed)))
    artifacts.append(q_artifact())
    for seed in SEEDS:
        for endpoint in ENDPOINTS:
                for method in METHODS:
                    target_seed = int.from_bytes(hashlib.sha256(f"goal035-final-inner|{bundle.target}|{bundle.held_fold}|{endpoint}|{seed}|target|resmlp13".encode()).digest()[:4], "big")
                    artifacts.append(neural(f"target/{endpoint}/seed{seed}/{method}", fit_seed=target_seed))
    metadata = {"schema_version": "goal035-final-inner-case-v1", "goal_id": "goal035-dsdm-final-inner-lifecycle", "target": bundle.target, "held_fold": bundle.held_fold, "architecture": "resmlp13", "config_digest": config.config_digest, "bundle_digest": bundle.source_digest, "target_mask_digests": {endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}, "auxiliary_mask_digest": prepared["auxiliary_mask"].digest, "support_overlap": prepared["support_overlap"], "target_support_audits": prepared["target_audits"], "auxiliary_support_audits": prepared["auxiliary_audits"], "q_ranges": {"linear": {"coefficient_min": -1.0, "coefficient_max": 1.0, "probability_min": 0.1, "probability_max": 0.9}, "deep": {"probability_min": 0.1, "probability_max": 0.9}}, "target_plus_q_prediction_ranges": {"linear_min": 0.1, "linear_max": 0.9, "deep_min": 0.1, "deep_max": 0.9}, "artifacts": artifacts, "counts": {"auxiliary_logical_artifacts": 11, "target_logical_artifacts": 210, "logical_artifacts": 221, "physical_fits": 441}, "runtime": {"device": "cpu"}, "outer_attempted": 0, "outer_opened": 0}
    leaf = write_leaf(tmp_path, identity, predictions, metadata)
    assert validate_leaf(leaf, identity)["prediction_digest"] == array_digest(predictions)
    good_envelope = json.loads((leaf / "metadata.json").read_text())
    np.save(leaf / "predictions.npy", predictions + np.float32(0.1), allow_pickle=False)
    with pytest.raises(ValueError, match="prediction digest"):
        validate_leaf(leaf, identity)
    np.save(leaf / "predictions.npy", predictions, allow_pickle=False)
    envelope = deepcopy(good_envelope)
    envelope["artifacts"][0]["model_digest"] = "b" * 64
    (leaf / "metadata.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="pooled transfer|artifact"):
        validate_leaf(leaf, identity)
    envelope = deepcopy(good_envelope)
    envelope["artifacts"][0]["runtime_digest"] = "b" * 64
    (leaf / "metadata.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="physical/artifact"):
        validate_leaf(leaf, identity)
    envelope = deepcopy(good_envelope)
    envelope["artifacts"][10]["n_iter"] = 0
    (leaf / "metadata.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="q termination"):
        validate_leaf(leaf, identity)


def test_config_binds_corrected_winner_and_arithmetic():
    config = load_config("config/dsdm_final_inner_lifecycle.json")
    assert config.corrected_winner == "resmlp13"
    assert config.raw["execution"]["logical_artifacts"] == 8840
    assert config.raw["execution"]["physical_fits_minimum"] == 17640
    assert config.raw["execution"]["physical_fits_maximum"] == 17680
    assert tuple(config.raw["methods"]) == METHODS


def test_config_runtime_mutation_fails_closed(tmp_path: Path):
    payload = json.loads(Path("config/dsdm_final_inner_lifecycle.json").read_text())
    payload["runtime"]["route"] = "wrong"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="runtime contract drift"):
        load_config(path, root=Path("."))


def test_canary_inventory_binding_rejects_stale_receipt(tmp_path: Path, monkeypatch):
    base, arrays = _case()
    bundles = [build_case_bundle(species, fold, arrays, {"outer_attempted": 0, "outer_opened": 0}, hashlib.sha256(f"{species}|{fold}".encode()).hexdigest()) for species in SPECIES for fold in FOLDS]
    config = load_config("config/dsdm_final_inner_lifecycle.json")
    raw = deepcopy(config.raw)
    raw["evidence"]["canary_receipt"] = str(tmp_path / "canary.json")
    raw["evidence"]["private_root"] = str(tmp_path / "private")
    test_config = replace(config, raw=raw)
    runtime = {"system": "Darwin", "machine": "arm64", "python_major_minor": "3.12", "numpy": "2.2.6", "scipy": "1.16.3", "scikit_learn": "1.9.0", "threadpoolctl": "3.6.0", "torch": "2.7.1", "device": "cpu", "route": "mac_cpu", "torch_threads": 1, "blas_threads": 1}
    monkeypatch.setattr(runner, "validate_bundle_inventory", lambda root, config=None: bundles)
    monkeypatch.setattr(runner, "runtime_attestation", lambda config, strict=True: runtime)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00")
    repeat_root = test_config.private_root / "canary_repeats"
    prepared = prepare_case(sentinel)
    repeat_identity = {"target": sentinel.target, "held_fold": sentinel.held_fold, "held_row_count": int(len(sentinel.arrays["x_held"])), "bundle_digest": sentinel.source_digest, "config_digest": config.config_digest, "runtime_digest": runner.digest_value(runtime), "architecture": config.corrected_winner, "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}
    repeat_leaf = leaf_identity(repeat_identity)
    for name in ("repeat_a", "repeat_b"):
        path = repeat_root / name / repeat_leaf
        path.mkdir(parents=True)
        (path / "metadata.json").write_text(json.dumps({"identity": repeat_identity}))
        np.save(path / "predictions.npy", np.zeros(1, dtype=np.float32), allow_pickle=False)
    counts = {"auxiliary_logical_artifacts": 11, "target_logical_artifacts": 210, "logical_artifacts": 221, "physical_fits": 441}
    repeat_metadata = {"identity": repeat_identity, "artifacts": [], "counts": counts}
    monkeypatch.setattr(runner, "validate_leaf", lambda path, identity: repeat_metadata)
    monkeypatch.setattr(runner, "_leaf_content_digest", lambda path: "c" * 64)
    receipt = {"schema_version": "goal035-final-inner-canary-v1", "success": True, "decision": "pass", "config_digest": config.config_digest, "corrected_winner": config.corrected_winner, "target": sentinel.target, "held_fold": sentinel.held_fold, "bundle_inventory_digest": runner._bundle_inventory_digest(bundles), "sentinel_bundle_digest": sentinel.source_digest, "source_fingerprint": config.source_fingerprint, "runtime": runtime, "runtime_digest": runner.digest_value(runtime), "counts": counts, "repeat_a_content_digest": "c" * 64, "repeat_b_content_digest": "c" * 64, "prediction_digest": runner.array_digest(np.zeros(1, dtype=np.float32)), "artifact_digest": runner.digest_value([]), "deterministic_evidence_digest": runner.digest_value(repeat_metadata), "gates": {"transfer": True, "reset": True, "frozen_trunk": True, "q_initial": True, "outer": True}, "outer_attempted": 0, "outer_opened": 0}
    test_config.canary_receipt.write_text(json.dumps(receipt))
    assert runner.validate_canary(test_config)["decision"] == "pass"
    receipt["bundle_inventory_digest"] = "c" * 64
    test_config.canary_receipt.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="bundle drift"):
        runner.validate_canary(test_config)
