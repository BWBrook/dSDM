from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

import dsdm.outer_ready as outer_ready_module
from dsdm.conventional_refit_import import (
    CROSS_PLATFORM_ATOL,
    _cross_platform_score_difference,
    record_producer_validation,
)
from dsdm.contracts import ArchitectureSpec
from dsdm.models import ResidualMLP
from dsdm.outer_ready import (
    ENDPOINT_SLUGS,
    OuterTrainingBundle,
    OuterReadyConfig,
    OuterReadyError,
    digest_value,
    exact_fit,
    load_config,
    load_outer_bundle,
    load_neural_model,
    lower_median,
    prepare_outer_bundle,
    save_outer_bundle,
    save_neural_model,
    score_neural_model,
    validate_epoch_policy,
)


def test_lower_median_and_epoch_policy_contract() -> None:
    assert lower_median([9, 1, 5, 7, 3]) == 5
    with pytest.raises(OuterReadyError):
        lower_median([1, 2, 3])

    policy = {
        "schema_version": "goal037-epoch-policy-v1",
        "architecture": "resmlp13",
        "fold_count": 5,
        "outer_attempted": 0,
        "outer_opened": 0,
        "records": [
            {
                "target": "species_a",
                "endpoint": "fraction100/full",
                "method": "target_only_resmlp",
                "seed": 31031,
                "fold_epochs": [1, 3, 5, 7, 9],
                "full_training_epochs": 5,
            }
        ],
    }
    assert validate_epoch_policy(policy, expected_records=1)["records"] == 1
    policy["records"][0]["full_training_epochs"] = 7
    with pytest.raises(OuterReadyError):
        validate_epoch_policy(policy, expected_records=1)


def test_production_config_is_strictly_bound() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config/dsdm_outer_ready.json")
    assert config.raw["scope"]["methods_total"] == 11
    assert config.raw["privacy"]["outer_opened"] == 0


def test_producer_validation_accepts_canonical_goal029_result(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config/dsdm_outer_ready.json")
    result = {
        "status": "pass",
        "mode": "production",
        "candidate_seed_leaf_count": 6888,
        "family_count": 280,
        "selected_model_seed_count": 952,
        "source_audit_leaf_count": 345,
        "transaction_id": config.raw["conventional"]["transaction_id"],
        "semantic_digest": "a" * 64,
        "outer_attempted_open_count": 0,
        "outer_open_count": 0,
    }
    result_path = tmp_path / "producer-result.json"
    output_path = tmp_path / "producer-validation.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    receipt = record_producer_validation(result_path, config, output_path)

    assert receipt["success"] is True
    assert receipt["selected_refits"] == 952
    assert receipt["outer_attempted"] == receipt["outer_opened"] == 0


def test_conventional_cross_platform_score_tolerance_is_bounded() -> None:
    producer = np.asarray([0.1, 0.5, 0.9], dtype=np.float64)
    negligible = producer.copy()
    negligible[0] = np.nextafter(negligible[0], 1.0)
    material = producer.copy()
    material[0] += 2 * CROSS_PLATFORM_ATOL

    assert _cross_platform_score_difference(negligible, producer) < CROSS_PLATFORM_ATOL
    assert _cross_platform_score_difference(material, producer) > CROSS_PLATFORM_ATOL


def test_exact_fit_is_deterministic_and_serialized_model_replays(tmp_path: Path) -> None:
    spec = ArchitectureSpec("tiny", 1, 8, 4, "constant", 0.0, 0.0)
    x = np.asarray(
        [[-1.0, 0.0], [-0.5, 0.2], [0.5, -0.1], [1.0, 0.3]],
        dtype=np.float32,
    )
    y = np.asarray([0.0, 0.0, 1.0, 1.0], dtype=np.float32)
    first = exact_fit(lambda: ResidualMLP(spec, 2), spec, 123, x, y, epochs=3)
    second = exact_fit(lambda: ResidualMLP(spec, 2), spec, 123, x, y, epochs=3)
    assert first.state_digest == second.state_digest
    assert np.array_equal(
        score_neural_model(first.model, x), score_neural_model(second.model, x)
    )

    path = tmp_path / "model.pt"
    receipt = save_neural_model(
        first.model,
        path,
        identity={"architecture": "tiny", "input_dim": 2, "method": "target_only"},
        challenge_x=x,
    )
    loaded = load_neural_model(
        path,
        spec=spec,
        input_dim=2,
        expected=receipt,
        challenge_x=x,
    )
    assert np.array_equal(score_neural_model(first.model, x), score_neural_model(loaded, x))

    payload = torch.load(path, map_location="cpu", weights_only=True)
    payload["state_dict"]["head.bias"] = payload["state_dict"]["head.bias"] + 1
    torch.save(payload, path)
    with pytest.raises(OuterReadyError):
        load_neural_model(path, spec=spec, input_dim=2, expected=receipt, challenge_x=x)


def test_epoch_policy_rejects_outer_access() -> None:
    value = {
        "schema_version": "goal037-epoch-policy-v1",
        "architecture": "resmlp13",
        "fold_count": 5,
        "outer_attempted": 1,
        "outer_opened": 0,
        "records": [],
    }
    with pytest.raises(OuterReadyError):
        validate_epoch_policy(value, expected_records=0)


def test_outer_training_bundle_roundtrip_and_nesting(tmp_path: Path) -> None:
    full_x = np.zeros((6, 77), dtype=np.float32)
    full_x[:, 0] = np.arange(6, dtype=np.float32)
    full_y = np.asarray([0, 1, 0, 1, 0, 1], dtype=np.float32)
    arrays: dict[str, np.ndarray] = {}
    for endpoint in (
        "fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02",
        "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02",
        "fraction100/full",
    ):
        count = 2 if endpoint.startswith("fraction25") else 4 if endpoint.startswith("fraction50") else 6
        slug = ENDPOINT_SLUGS[endpoint]
        arrays[f"target_{slug}_x"] = full_x[:count].copy()
        arrays[f"target_{slug}_y"] = full_y[:count].copy()
    arrays["aux_x"] = np.tile(full_x[:2], (7, 1)).astype(np.float32)
    arrays["aux_y"] = np.tile(np.asarray([0, 1], dtype=np.float32), 7)
    arrays["aux_species"] = np.repeat(np.arange(7, dtype=np.int32), 2)
    inventory = {
        name: __import__("hashlib").sha256(value.tobytes(order="C")).hexdigest()
        for name, value in sorted(arrays.items())
    }
    metadata = {
        "target": "dasyurus_maculatus",
        "array_digests": inventory,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    metadata["bundle_digest"] = digest_value({"metadata": metadata, "arrays": inventory})
    bundle = OuterTrainingBundle(
        "dasyurus_maculatus", arrays, metadata, metadata["bundle_digest"]
    )
    path = save_outer_bundle(bundle, tmp_path / "bundle.npz")
    loaded = load_outer_bundle(path)
    assert loaded.bundle_digest == bundle.bundle_digest
    assert set(prepare_outer_bundle(loaded)["target_masks"]) == set(ENDPOINT_SLUGS)

    bad = dict(arrays)
    bad["target_fraction50_ladder00_x"] = full_x[2:6].copy()
    with pytest.raises(OuterReadyError):
        OuterTrainingBundle("dasyurus_maculatus", bad, metadata, metadata["bundle_digest"])


def test_bounded_package_runs_and_replays_all_transfer_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    full_x = np.zeros((6, 77), dtype=np.float32)
    full_x[:, 0] = np.arange(6, dtype=np.float32)
    full_x[:, 1] = np.asarray([-1, 1, -2, 2, -3, 3], dtype=np.float32)
    full_y = np.asarray([0, 1, 0, 1, 0, 1], dtype=np.float32)
    arrays: dict[str, np.ndarray] = {}
    for endpoint in outer_ready_module.ENDPOINT_SLUGS:
        count = 2 if endpoint.startswith("fraction25") else 4 if endpoint.startswith("fraction50") else 6
        slug = outer_ready_module.ENDPOINT_SLUGS[endpoint]
        arrays[f"target_{slug}_x"] = full_x[:count].copy()
        arrays[f"target_{slug}_y"] = full_y[:count].copy()
    arrays["aux_x"] = np.tile(full_x[:2], (7, 1)).astype(np.float32)
    arrays["aux_y"] = np.tile(np.asarray([0, 1], dtype=np.float32), 7)
    arrays["aux_species"] = np.repeat(np.arange(7, dtype=np.int32), 2)
    inventory = {name: __import__("hashlib").sha256(value.tobytes(order="C")).hexdigest() for name, value in sorted(arrays.items())}
    metadata = {"target": "dasyurus_maculatus", "array_digests": inventory, "outer_attempted": 0, "outer_opened": 0}
    metadata["bundle_digest"] = digest_value({"metadata": metadata, "arrays": inventory})
    bundle = OuterTrainingBundle("dasyurus_maculatus", arrays, metadata, metadata["bundle_digest"])

    records = []
    for target in outer_ready_module.SPECIES:
        for method in ("pooled", "multihead"):
            for seed in outer_ready_module.SEEDS:
                records.append({"target": target, "endpoint": "auxiliary", "method": method, "seed": seed, "fold_epochs": [1] * 5, "full_training_epochs": 1})
        for endpoint in outer_ready_module.ENDPOINTS:
            for method in outer_ready_module.METHODS:
                for seed in outer_ready_module.SEEDS:
                    records.append({"target": target, "endpoint": endpoint, "method": method, "seed": seed, "fold_epochs": [1] * 5, "full_training_epochs": 1})
    policy = {
        "schema_version": "goal037-epoch-policy-v1", "architecture": "resmlp13", "fold_count": 5,
        "source": {"goal035_aggregate_sha256": "a" * 64, "goal035_config_digest": "b" * 64, "goal035_source_fingerprint": "c" * 64, "goal035_leaf_inventory_digest": "d" * 64, "goal035_leaf_content_inventory_digest": "e" * 64},
        "records": records, "outer_attempted": 0, "outer_opened": 0,
    }
    policy["policy_digest"] = digest_value(policy)
    runtime = {"route": "test", "device": "cpu"}
    config = OuterReadyConfig(
        source_path=tmp_path / "config.json", root=tmp_path, raw={"runtime": {"neural": runtime}},
        config_digest="f" * 64, authority_digests={}, source_digests={}, source_fingerprint="1" * 64,
        private_root=tmp_path / "private", tracked_root=tmp_path / "evidence",
        goal035_private_root=tmp_path / "goal035", epoch_policy_path=tmp_path / "policy.json",
        conventional_import_receipt=tmp_path / "conventional.json", canary_receipt=tmp_path / "canary.json",
    )
    monkeypatch.setattr(outer_ready_module, "neural_runtime", lambda _config, strict=True: runtime)
    package = tmp_path / "package"
    outer_ready_module._run_package(
        bundle, config, policy, package, seeds=(31031,), endpoints=("fraction100/full",)
    )
    validated = outer_ready_module.validate_package(
        package, bundle, config, policy, seeds=(31031,), endpoints=("fraction100/full",), replay_models=True
    )
    assert validated["counts"]["logical_artifacts"] == 9
    assert validated["outer_opened"] == 0

    model = next((package / "models").glob("target--*.pt"))
    model.write_bytes(model.read_bytes() + b"tamper")
    with pytest.raises(OuterReadyError):
        outer_ready_module.validate_package(
            package, bundle, config, policy, seeds=(31031,), endpoints=("fraction100/full",), replay_models=True
        )
