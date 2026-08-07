from __future__ import annotations

import json
import numpy as np
import subprocess
from pathlib import Path
import pytest

from dsdm.compute_canary import (
    _digest,
    _deterministic_pairs,
    _inventory_valid,
    build_plan,
    derive_case_seed,
    load_config,
    summarize,
    validate_host_attestation,
    validate_receipt,
)
from dsdm.real_data import CaseSpec, build_bundle_from_records, save_bundle
from dsdm.contracts import ArchitectureSpec
from dsdm.real_training import train_case


def test_plan_has_three_bounded_cases():
    plan = build_plan({"base_seed": 31032, "cases": ["light", "medium", "heavy"]})
    assert plan["case_count"] == 3
    assert plan["outer_attempted"] == plan["outer_opened"] == 0


def test_receipt_validation_rejects_outer_access():
    receipt = {"status": "ok", "outer_attempted": 1, "outer_opened": 0}
    assert validate_receipt(receipt) is False


def test_case_seed_is_stable_and_case_specific():
    assert derive_case_seed(31032, "light") == derive_case_seed(31032, "light")
    assert derive_case_seed(31032, "light") != derive_case_seed(31032, "heavy")


def test_official_config_and_plan_cli_path():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["uv", "run", "--locked", "python", "-m", "dsdm.compute_canary", "plan", "--config", str(root / "config/dsdm_real_compute_calibration.json")], cwd=root, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)["logical_evaluations"] == 24


def test_counts_only_or_nondeterministic_final_receipt_is_rejected():
    fabricated = {"schema_version": "goal032-calibration-receipt-v1", "success": True, "serial_hosts": ["a", "b", "c"], "concurrency_hosts": ["a"], "deterministic_pairs": True, "logical_evaluations": 24, "physical_fit_count": 48, "projected_architecture_logical_evaluations": 1440, "projected_architecture_physical_fits": 2880, "outer_attempted": 0, "outer_opened": 0}
    assert validate_receipt(fabricated) is False


def test_host_attestation_binds_identity_runtime_and_device():
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config/dsdm_real_compute_calibration.json")
    attestation = {
        "host_id": "mac_cpu", "hostname": "Barrys-Mac-mini.local",
        "python_version": "3.12.13", "numpy_version": "2.2.6", "torch_version": "2.7.1",
        "wheel_role": "official_cpu", "device": "cpu", "cuda_runtime": "none",
        "driver_version": None, "gpu_count": 0, "total_vram_bytes": 0,
        "total_ram_bytes": 1, "swap_total_bytes": 0, "swap_used_bytes": 0,
        "swap_before_bytes": 0, "swap_after_bytes": 0, "swap_growth_bytes": 0,
    }
    attestation["attestation_digest"] = _digest(attestation)
    validate_host_attestation(config, "mac_cpu", attestation)
    bad = dict(attestation, torch_version="2.7.0")
    bad["attestation_digest"] = _digest(bad)
    with pytest.raises(ValueError, match="runtime"):
        validate_host_attestation(config, "mac_cpu", bad)


def test_config_publication_drift_is_rejected(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config_path = root / "config/dsdm_real_compute_calibration.json"
    value = json.loads(config_path.read_text())
    value["publication"]["worker_push_allowed"] = True
    mutated = tmp_path / "config.json"
    mutated.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="publication"):
        load_config(mutated)


def test_config_authority_uses_file_bytes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = root / "config/dsdm_real_compute_calibration.json"
    first = load_config(source)
    copy = tmp_path / "config.json"
    copy.write_bytes(source.read_bytes() + b"\n")
    second = load_config(copy)
    assert first["_source_sha256"] != second["_source_sha256"]


def _attestation(host_id, *, swap_growth=0):
    cuda = host_id == "alien_cuda"
    hostnames = {"mac_cpu": "Barrys-Mac-mini.local", "deep_server_cpu": "deep-server", "alien_cuda": "alienware"}
    value = {
        "host_id": host_id,
        "hostname": hostnames[host_id],
        "python_version": "3.12.13",
        "numpy_version": "2.2.6",
        "torch_version": "2.7.1",
        "wheel_role": "official_cu118" if cuda else "official_cpu",
        "device": "cuda:0" if cuda else "cpu",
        "cuda_runtime": "11.8" if cuda else "none",
        "driver_version": "546.01" if cuda else None,
        "gpu_count": 2 if cuda else 0,
        "total_vram_bytes": 16_000 if cuda else 0,
        "total_ram_bytes": 100_000,
        "swap_total_bytes": 10_000,
        "swap_used_bytes": 100 + swap_growth,
        "swap_before_bytes": 100,
        "swap_after_bytes": 100 + swap_growth,
        "swap_growth_bytes": swap_growth,
    }
    value["attestation_digest"] = _digest(value)
    return value


def _private_rows(config):
    rows = []
    host_seconds = {"mac_cpu": 1.0, "deep_server_cpu": 3.0, "alien_cuda": 2.0}
    for panel, hosts in (("serial", tuple(host_seconds)), ("concurrency", ("mac_cpu",))):
        for host_id in hosts:
            witness = _attestation(host_id)
            for case in config["cases"]:
                case_id = case["case_id"]
                for repeat in range(2):
                    rows.append({
                        "panel": panel,
                        "host_id": host_id,
                        "case_id": case_id,
                        "repeat": repeat,
                        "architecture": case["architecture"]["id"],
                        "architecture_id": case["architecture"]["id"],
                        "architecture_spec": case["architecture"],
                        "seed": derive_case_seed(config["training"]["base_seed"], case_id),
                        "status": "ok",
                        "finite_outputs": True,
                        "outer_attempted": 0,
                        "outer_opened": 0,
                        "selected_epoch": 10,
                        "discovery_executed_epochs": 40,
                        "replay_epochs": 10,
                        "stopping_status": "patience_stop",
                        "discovery_initial_state_digest": f"init-{case_id}",
                        "replay_initial_state_digest": f"init-{case_id}",
                        "model_digest": f"model-{host_id}-{case_id}",
                        "prediction_digest": f"prediction-{host_id}-{case_id}",
                        "bundle_digest": f"bundle-{case_id}",
                        "runtime_attestation_digest": witness["attestation_digest"],
                        "host_attestation": witness,
                        "wall_seconds": host_seconds[host_id],
                        "panel_makespan_seconds": 3.0 if panel == "concurrency" else 0.0,
                        "peak_rss_bytes": 1_000,
                        "peak_vram_bytes": 500 if host_id == "alien_cuda" else 0,
                    })
    return rows


def test_final_receipt_is_fully_recomputed_from_private_rows(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config/dsdm_real_compute_calibration.json")
    rows = _private_rows(config)
    receipt = summarize(rows, config=config)
    assert receipt["success"] is True
    for row in rows:
        directory = tmp_path / row["panel"] / row["host_id"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{row['case_id']}-repeat{row['repeat']:02d}.json"
        path.write_text(json.dumps(row), encoding="utf-8")
    monkeypatch.setattr("dsdm.compute_canary._validate_bundle_inventory", lambda *_args: True)
    assert validate_receipt(receipt, config, tmp_path)
    mutated = dict(receipt, central_duration_seconds=receipt["central_duration_seconds"] + 1)
    assert not validate_receipt(mutated, config, tmp_path)


def test_inventory_rejects_wrong_leader_and_swap_growth():
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config/dsdm_real_compute_calibration.json")
    rows = _private_rows(config)
    for row in rows:
        if row["panel"] == "concurrency":
            witness = _attestation("deep_server_cpu")
            row["host_id"] = "deep_server_cpu"
            row["host_attestation"] = witness
            row["runtime_attestation_digest"] = witness["attestation_digest"]
    assert not _inventory_valid(rows, config)

    rows = _private_rows(config)
    witness = _attestation("mac_cpu", swap_growth=1)
    rows[0]["host_attestation"] = witness
    rows[0]["runtime_attestation_digest"] = witness["attestation_digest"]
    assert not _inventory_valid(rows, config)


def test_inventory_rejects_cross_host_bundle_drift_and_cross_panel_model_drift():
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config/dsdm_real_compute_calibration.json")
    rows = _private_rows(config)
    for row in rows:
        if row["panel"] == "serial" and row["host_id"] == "alien_cuda" and row["case_id"] == "light":
            row["bundle_digest"] = "different-light-bundle"
    assert not _inventory_valid(rows, config)

    rows = _private_rows(config)
    for row in rows:
        if row["panel"] == "concurrency" and row["case_id"] == "light":
            row["model_digest"] = "different-concurrent-model"
    assert not _deterministic_pairs(rows)


def test_partial_serial_panel_can_be_summarized_before_host_ranking():
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config/dsdm_real_compute_calibration.json")
    rows = [row for row in _private_rows(config) if row["panel"] == "serial" and row["host_id"] == "mac_cpu"]
    summary = summarize(rows, config=config)
    assert summary["count"] == 6
    assert summary["success"] is False
