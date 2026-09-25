import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import goal052_pbs_run as launcher  # noqa: E402


IDENTITY = {"source_sha256": "s" * 64, "goal051_identity": {"id": "goal051"}}


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding_case(tmp_path, stage, node_count, receipt_overrides=None):
    root = tmp_path / "production"
    handoff = root / "handoff"
    pilot = handoff / "pilot-reference"
    nodes = ["node-%02d" % index for index in range(node_count)]

    driver_sha = {}
    for name in launcher.REQUIRED_DRIVERS:
        driver_sha[name] = _write(root / name, name + "\n")
    sif_sha = _write(root / "runtime.sif", "sif\n")
    inputs_sha = _write(root / "inputs.tar.gz", "inputs\n")
    pilot_sha = {
        "canary.json": _write(pilot / "canary.json", "canary\n"),
        "full-epoch-profile.json": _write(pilot / "full-epoch-profile.json", "profile\n"),
        "qualification-reference-review.json": _write(
            pilot / "qualification-reference-review.json", "review\n"
        ),
    }

    manifest = {
        "manifest_digest": "a" * 64,
        "stage": stage,
        "identity": IDENTITY,
        "selection_digest": "b" * 64,
        "full_pretraining_inventory_digest": None,
        "nodes": nodes,
        "workers_per_node": 28,
        "shards": [{"node": node, "rank": index} for index, node in enumerate(nodes)],
    }
    if stage == "final_targets":
        manifest["full_pretraining_inventory_digest"] = "c" * 64
        receipt = {
            "immutable": True,
            "status": "goal052_full_pretraining_verified",
            "identity": IDENTITY,
            "selection_digest": manifest["selection_digest"],
            "native_inventory_digest": manifest["full_pretraining_inventory_digest"],
            "validated_checkpoint_count": 900,
            "checkpoint_inventory_sha256": "d" * 64,
        }
        if receipt_overrides:
            receipt.update(receipt_overrides)
        receipt_path = handoff / "full-pretraining.json"
        receipt_sha = _write(receipt_path, receipt)
        manifest["full_pretraining_reference"] = {
            "path": "handoff/full-pretraining.json",
            "sha256": receipt_sha,
        }
    else:
        manifest["full_pretraining_reference"] = None

    manifest_path = handoff / "manifest.json"
    manifest_sha = _write(manifest_path, manifest)
    launch = {
        "status": (
            launcher.LAUNCH_STATUS
            if stage == "remaining_pretraining"
            else launcher.FINAL_TARGETS_LAUNCH_STATUS
        ),
        "production_root": str(root),
        "manifest_path": str(manifest_path),
        "manifest_digest": manifest["manifest_digest"],
        "manifest_sha256": manifest_sha,
        "sif_path": str(root / "runtime.sif"),
        "sif_sha256": sif_sha,
        "inputs_archive_path": str(root / "inputs.tar.gz"),
        "inputs_archive_sha256": inputs_sha,
        "pilot_reference_root": str(pilot),
        "pilot_reference_sha256": pilot_sha,
        "driver_sha256": driver_sha,
        "walltime_hours": 48,
        "nodes": node_count,
        "workers_per_node": 28,
    }
    launch_path = tmp_path / "launch.json"
    launch_sha = _write(launch_path, launch)
    return root, manifest_path, manifest["manifest_digest"], launch_path, launch_sha


def _validate(case):
    root, manifest_path, manifest_digest, launch_path, launch_sha = case
    return launcher.validate_launch_binding(
        launch_path, launch_sha, root, manifest_path, manifest_digest
    )


def test_pretraining_launch_accepts_bound_25_node_manifest(tmp_path):
    binding = _validate(_binding_case(tmp_path, "remaining_pretraining", 25))
    assert binding["stage"] == "remaining_pretraining"
    assert binding["full_pretraining_reference"] is None


def test_final_targets_launch_accepts_bound_48_node_manifest(tmp_path):
    binding = _validate(_binding_case(tmp_path, "final_targets", 48))
    assert binding["stage"] == "final_targets"
    assert binding["full_pretraining_reference"]["receipt"]["validated_checkpoint_count"] == 900


def test_cross_stage_status_is_rejected(tmp_path):
    case = list(_binding_case(tmp_path, "final_targets", 1))
    launch_path = case[3]
    launch = json.loads(launch_path.read_text())
    launch["status"] = launcher.LAUNCH_STATUS
    launch_sha = _write(launch_path, launch)
    case[4] = launch_sha
    with pytest.raises(ValueError, match="launch_stage_mismatch"):
        _validate(case)


def test_final_targets_node_count_must_match_manifest(tmp_path):
    case = list(_binding_case(tmp_path, "final_targets", 48))
    launch_path = case[3]
    launch = json.loads(launch_path.read_text())
    launch["nodes"] = 47
    case[4] = _write(launch_path, launch)
    with pytest.raises(ValueError, match="launch_manifest_node_count_mismatch"):
        _validate(case)


def test_worker_count_must_remain_28(tmp_path):
    case = list(_binding_case(tmp_path, "final_targets", 1))
    launch_path = case[3]
    launch = json.loads(launch_path.read_text())
    launch["workers_per_node"] = 27
    case[4] = _write(launch_path, launch)
    with pytest.raises(ValueError, match="launch_worker_count_invalid"):
        _validate(case)


def test_missing_or_modified_barrier_is_rejected(tmp_path):
    case = list(_binding_case(tmp_path, "final_targets", 1))
    root, manifest_path = case[0], case[1]
    barrier = root / "handoff" / "full-pretraining.json"
    barrier.unlink()
    with pytest.raises(ValueError, match="full_pretraining_reference_missing"):
        _validate(case)

    case = list(_binding_case(tmp_path / "modified", "final_targets", 1))
    barrier = case[0] / "handoff" / "full-pretraining.json"
    barrier.write_text(barrier.read_text().replace('"validated_checkpoint_count": 900',
                                                    '"validated_checkpoint_count": 899'))
    with pytest.raises(ValueError, match="full_pretraining_reference_drift"):
        _validate(case)


def test_malformed_barrier_receipt_is_rejected(tmp_path):
    case = _binding_case(
        tmp_path, "final_targets", 1,
        receipt_overrides={"validated_checkpoint_count": 899},
    )
    with pytest.raises(ValueError, match="full_pretraining_checkpoint_count_invalid"):
        _validate(case)
