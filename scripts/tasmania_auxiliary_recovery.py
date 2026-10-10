"""Bounded replay-only recovery for the 200 Goal035 multi-head states.

This module deliberately keeps preparation and validation separate from fitting.
``prepare`` stages an immutable copy of the historical Goal037 executable
sources and the ten Goal035 authority files.  ``validate`` reads the accepted
private bundles and leaves, but performs no fitting.  ``run`` refuses to fit
unless ``--execute`` is supplied, then replays only the recorded auxiliary
epochs with the archived Goal034/Goal037 implementation.

The final aggregate receipt is written only after all 200 states pass exact
semantic digest checks.  Failed attempts remain private and are never silently
retried or promoted.
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
import hashlib
import importlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = PROJECT_ROOT / "data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1"
BUNDLE_ROOT = PROJECT_ROOT / "data/processed/dsdm/goal035-final-inner-lifecycle/private"
AUDIT_PATH = PROJECT_ROOT / "evidence/tasmania_pseudoabsence/20261008/auxiliary-state-audit.json"
APPROVAL_PATH = PROJECT_ROOT / "docs/plan/TasmaniaPseudoabsenceRecoveryApproval-20261009.md"
APPROVAL_SHA256 = "8d210a06401f2f6540594b4ab57a7184baecb61909aeb1a3b78ec31ddaf85dd1"
AUDIT_RECEIPT_DIGEST = "765e45c7f567c1e021d5954ea69b7d6d0bd11c3863efff2c855e7780cd562347"
DEFAULT_STAGE_ROOT = PROJECT_ROOT / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private/reconstruction"
AGGREGATE_PATH = PROJECT_ROOT / "evidence/tasmania_pseudoabsence/20261009/auxiliary-recovery.json"

SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
FOLDS = tuple(f"fold{i:02d}" for i in range(5))
SEEDS = (31031, 31032, 31033, 31034, 31035)
EXPECTED_STATE_COUNT = len(SPECIES) * len(FOLDS) * len(SEEDS)
SEMANTIC_DIGEST_KEYS = (
    "initial_model_digest", "initial_shared_digest", "final_shared_digest",
    "model_digest", "prediction_digest", "replay_initial_model_digest",
)

# These are the live, accepted Goal035 authority bindings from the audit.  The
# values are intentionally explicit so an audit edit cannot silently widen the
# recovery input set.
AUTHORITY_BINDINGS = {
    "goal028_config": ("config/modeling_foundation_preflight.json", "35b6ab72ba2b8ba2267dc82179987bfffaa3f339d64272d68012444e46285f00"),
    "goal028_decision": ("docs/goals/028-modeling-foundation-preflight/Decision.md", "3eb6e0fbe2ee7eb1db08e75c8b99f7d1fd9760cdbebacd88bbba8ebc1889a50c"),
    "goal026_feature_contract": ("evidence/model_ready_features/2026-07-27/feature_contract.json", "e9a8f9b7bee7dee25905dfa052427f6e0a4f1b5ebd6ed02fcfb1761bbd224d98"),
    "goal026_fit_parameters": ("evidence/model_ready_features/2026-07-27/fit_parameters.json", "608b99f94af49122bf9e252e35ae7c067812762d20ba080c3e7fbd40f35661d0"),
    "goal033_config": ("config/dsdm_architecture_selection.json", "39542d079b3cdc6a11819dea3e1c18b52ec4aa38f530ff218955d7e89775596f"),
    "goal033_decision": ("docs/goals/033-dsdm-architecture-selection/Decision.md", "f9ba7b18498415422aa39618c4d4ec13f20c97be87a694f52d44bc788d6c68fb"),
    "goal034_config": ("config/dsdm_real_six_path_sentinel.json", "43f5161850d1c7384af8fe0600ae322c93ca9ccca54a2a878ce13f933c6367a9"),
    "goal034_decision": ("docs/goals/034-dsdm-real-six-path-sentinel/Decision.md", "edfd76dc3a3e94058da11fc5e36f93b40a23458326e04df8ea33a2ba6b386375"),
    "goal029_config": ("config/conventional_baseline_production.json", "62b1c5255c5aa5c74f5ba598818dd13e2f2234c0cb13da58671c3be286ccefae"),
    "corrected_aggregate": ("evidence/dsdm_architecture_selection/goal035/aggregate.json", "d80e524245d18f54184433b4fb4e3ba2a4b2c8226452a037d832e14f189e0d43"),
}


class RecoveryError(ValueError):
    """Raised when the bounded reconstruction contract is not satisfied."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryError(message)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_value(value: Any) -> str:
    return _digest_bytes(_canonical(value))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_audit(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    path = root / AUDIT_PATH.relative_to(PROJECT_ROOT)
    approval_path = root / APPROVAL_PATH.relative_to(PROJECT_ROOT)
    _require(approval_path.is_file() and _sha256(approval_path) == APPROVAL_SHA256, "immutable recovery approval binding drift")
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"audit unavailable: {path}") from exc
    _require(audit.get("schema_version") == "tasmania-pseudoabsence-auxiliary-availability-v1", "auxiliary audit schema drift")
    _require(audit.get("receipt_digest") == AUDIT_RECEIPT_DIGEST, "auxiliary audit receipt binding drift")
    self_digest = _digest_value({key: value for key, value in audit.items() if key != "receipt_digest"})
    _require(self_digest == AUDIT_RECEIPT_DIGEST, "auxiliary audit self digest drift")
    _require(audit.get("status") == "source_and_metadata_audit_complete_reconstruction_not_run", "audit status does not permit recovery")
    _require(audit.get("goal035_inventory", {}).get("multihead_digest_records") == EXPECTED_STATE_COUNT, "audit multi-head record count drift")
    _require(audit.get("goal035_inventory", {}).get("fold_specific_multihead_weight_files") == 0, "fold-specific model files already exist")
    _require(audit.get("minimal_amendment_proposal", {}).get("extra_physical_fits") == EXPECTED_STATE_COUNT, "audit recovery count drift")
    return audit


def _safe_relative(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    _require(candidate == root.resolve() or root.resolve() in candidate.parents, f"path escapes root: {relative}")
    return candidate


def _copy_file(source: Path, destination: Path) -> None:
    _require(source.is_file(), f"source file missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _stage_manifest(stage_root: Path) -> Path:
    return stage_root / "reconstruction-manifest.json"


def _manifest_payload(stage_root: Path, audit: Mapping[str, Any]) -> dict[str, Any]:
    authorities = {
        name: {"path": relative, "sha256": expected}
        for name, (relative, expected) in sorted(AUTHORITY_BINDINGS.items())
    }
    source_files = sorted(str(path.relative_to(ARCHIVE_ROOT)) for path in (ARCHIVE_ROOT / "src").rglob("*.py"))
    return {
        "schema_version": "tasmania-auxiliary-reconstruction-stage-v1",
        "purpose": "Goal035 exact replay-only multihead auxiliary state recovery",
        "audit_receipt_digest": audit.get("receipt_digest"),
        "archive_receipt": _sha256(ARCHIVE_ROOT / "archive-receipt.json"),
        "archive_root": str(ARCHIVE_ROOT.relative_to(PROJECT_ROOT)),
        "authorities": authorities,
        "sources": {relative: _sha256(ARCHIVE_ROOT / relative) for relative in source_files},
        "config": _sha256(stage_root / "config/dsdm_final_inner_lifecycle.json"),
        "uv_lock": _sha256(stage_root / "uv.lock"),
        "bundle_root": str(BUNDLE_ROOT.relative_to(PROJECT_ROOT)),
        "expected_states": EXPECTED_STATE_COUNT,
        "outer_attempted": 0,
        "outer_opened": 0,
    }


def prepare_stage(root: Path = PROJECT_ROOT, stage_root: Path = DEFAULT_STAGE_ROOT) -> dict[str, Any]:
    """Create a separate, hash-bound executable/configuration root."""
    audit = _read_audit(root)
    archive = root / ARCHIVE_ROOT.relative_to(PROJECT_ROOT)
    _require(archive.is_dir(), f"Goal037 archive missing: {archive}")
    stage_root = stage_root.resolve()
    manifest_path = _stage_manifest(stage_root)
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RecoveryError("existing reconstruction manifest is invalid; preserve it and choose a new stage root") from exc
        expected = _manifest_payload(stage_root, audit)
        _require(existing == expected, "existing reconstruction stage manifest mismatch")
        return {"status": "already_staged", "stage_root": str(stage_root), "manifest_digest": _sha256(manifest_path)}

    temporary = Path(tempfile.mkdtemp(prefix=".aux-reconstruction-", dir=str(stage_root.parent)))
    try:
        shutil.copytree(archive / "src", temporary / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(archive / "config", temporary / "config")
        _copy_file(archive / "uv.lock", temporary / "uv.lock")
        if (archive / "pyproject.toml").is_file():
            _copy_file(archive / "pyproject.toml", temporary / "pyproject.toml")
        for name, (relative, expected) in AUTHORITY_BINDINGS.items():
            live = root / relative
            _require(live.is_file() and _sha256(live) == expected, f"live authority hash mismatch: {name}")
            _copy_file(live, temporary / relative)
        payload = _manifest_payload(temporary, audit)
        manifest_path_tmp = _stage_manifest(temporary)
        manifest_path_tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        _require(not stage_root.exists(), f"reconstruction stage already exists without manifest: {stage_root}")
        os.replace(temporary, stage_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"status": "staged", "stage_root": str(stage_root), "manifest_digest": _sha256(_stage_manifest(stage_root))}


def _import_archived(stage_root: Path):
    source_root = str(stage_root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    for name in tuple(sys.modules):
        if name == "dsdm" or name.startswith("dsdm."):
            del sys.modules[name]
    return importlib.import_module("dsdm.final_inner_data")


def _verify_staged_sources(stage_root: Path, manifest: Mapping[str, Any]) -> None:
    """Check staged executable bytes against the archive-bound manifest before import."""
    sources = manifest.get("sources")
    _require(isinstance(sources, dict) and sources, "staged source inventory missing")
    for relative, expected in sources.items():
        source = _safe_relative(stage_root, str(relative))
        _require(source.is_file() and _sha256(source) == expected, f"staged source hash mismatch: {relative}")


def _load_staged_config(stage_root: Path):
    manifest_path = _stage_manifest(stage_root)
    _require(manifest_path.is_file(), "reconstruction stage manifest missing")
    _verify_staged_sources(stage_root, json.loads(manifest_path.read_text(encoding="utf-8")))
    data = _import_archived(stage_root)
    config_path = stage_root / "config/dsdm_final_inner_lifecycle.json"
    _require(config_path.is_file(), "staged Goal035 config missing")
    config = data.load_config(config_path, root=stage_root, require_receipt=True)
    return data, config


def _accepted_leaf_metadata(data: Any, config: Any, bundles: Sequence[Any], leaf_root: Path) -> dict[tuple[str, str], tuple[Path, dict[str, Any]]]:
    """Resolve the 40 accepted leaves by the archived identity contract.

    The private directory also contains abandoned/repeated attempts.  Directory
    count is therefore not an acceptance criterion; the historical leaf
    identity derived from the current bundle, mask and runtime is.
    """
    found: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    runtime_digest = data.digest_value(data.runtime_attestation(config, strict=True))
    for bundle in bundles:
        prepared = data.prepare_case(bundle)
        identity = {
            "target": bundle.target,
            "held_fold": bundle.held_fold,
            "held_row_count": int(len(bundle.arrays["x_held"])),
            "bundle_digest": bundle.source_digest,
            "config_digest": config.config_digest,
            "runtime_digest": runtime_digest,
            "architecture": config.corrected_winner,
            "mask_digest": data.digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in data.FINAL_ENDPOINTS}),
            "aux_mask_digest": prepared["auxiliary_mask"].digest,
        }
        path = leaf_root / data.leaf_identity(identity)
        _require(path.is_dir(), f"accepted leaf missing: {bundle.target}/{bundle.held_fold}")
        metadata_path = path / "metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecoveryError(f"invalid accepted leaf metadata: {metadata_path}") from exc
        key = (bundle.target, bundle.held_fold)
        _require(key not in found and key[0] in SPECIES and key[1] in FOLDS, "accepted leaf identity inventory drift")
        found[key] = (path, metadata)
    _require(set(found) == {(target, fold) for target in SPECIES for fold in FOLDS}, "accepted leaf cross-product drift")
    return found


def _accepted_metadata_inventory_digest(leaves: Mapping[tuple[str, str], tuple[Path, Mapping[str, Any]]]) -> str:
    """Digest the raw metadata files for the independently resolved leaves."""
    metadata_digests = []
    for path, _metadata in sorted(leaves.values(), key=lambda item: str(item[0])):
        metadata_path = path / "metadata.json"
        _require(metadata_path.is_file(), f"accepted leaf metadata missing: {metadata_path}")
        metadata_digests.append(_sha256(metadata_path))
    return _digest_value(metadata_digests)


def _bind_accepted_metadata_inventory(
    audit: Mapping[str, Any],
    leaves: Mapping[tuple[str, str], tuple[Path, Mapping[str, Any]]],
) -> str:
    expected = audit.get("goal035_inventory", {}).get("accepted_metadata_inventory_digest")
    _require(isinstance(expected, str) and len(expected) == 64, "accepted metadata inventory binding missing")
    actual = _accepted_metadata_inventory_digest(leaves)
    _require(actual == expected, "accepted metadata inventory digest drift")
    return actual


def _auxiliary_record(metadata: Mapping[str, Any], target: str, fold: str, seed: int) -> Mapping[str, Any]:
    artifact_id = f"aux/multihead/seed{seed}"
    records = [row for row in metadata.get("artifacts", []) if row.get("artifact_id") == artifact_id]
    _require(len(records) == 1, f"missing auxiliary record: {target}/{fold}/{seed}")
    record = records[0]
    _require(record.get("kind") == "auxiliary" and record.get("fit_seed") == seed, f"auxiliary record identity drift: {target}/{fold}/{seed}")
    for key in ("initial_model_digest", "replay_initial_model_digest", "initial_shared_digest", "final_shared_digest", "model_digest", "prediction_digest", "runtime_digest"):
        _require(isinstance(record.get(key), str) and len(record[key]) == 64, f"auxiliary digest missing: {target}/{fold}/{seed}/{key}")
    _require(record["initial_model_digest"] == record["replay_initial_model_digest"], f"initial/replay state mismatch: {target}/{fold}/{seed}")
    _require(type(record.get("selected_epoch")) is int and record["selected_epoch"] == record.get("replay_epochs") and record["selected_epoch"] >= 1, f"auxiliary epoch invalid: {target}/{fold}/{seed}")
    _require(record.get("physical_fits") == 2 and record.get("logical_artifacts") == 1 and record.get("finite") is True, f"auxiliary fit arithmetic invalid: {target}/{fold}/{seed}")
    return record


def _check_replay_digests(expected: Mapping[str, Any], actual: Mapping[str, Any], identity: str) -> None:
    """Require exact semantic equality for one reconstructed state."""
    for key in SEMANTIC_DIGEST_KEYS:
        _require(actual.get(key) == expected.get(key), f"{key} mismatch: {identity}")


def _validate_state_inventory(records: Sequence[Mapping[str, Any]]) -> None:
    """Fail closed unless the complete 8 x 5 x 5 state cross-product exists."""
    keys = {(row.get("target"), row.get("held_fold"), row.get("seed")) for row in records}
    expected = {(target, fold, seed) for target in SPECIES for fold in FOLDS for seed in SEEDS}
    _require(len(records) == EXPECTED_STATE_COUNT and keys == expected, "expected 200 auxiliary records")


def _validate_input_binding(data: Any, bundle: Any, metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the numerical Goal035 bundle and the original prepare_case mask."""
    data.validate_case_payload  # fail loudly if the archived API is incomplete
    prepared = data.prepare_case(bundle)
    _require(prepared["auxiliary_mask"].digest == metadata.get("auxiliary_mask_digest"), f"auxiliary mask digest mismatch: {bundle.target}/{bundle.held_fold}")
    species_names = tuple(name for name in SPECIES if name != bundle.target)
    for role in ("discovery", "stopping", "replay"):
        species = np.asarray(bundle.arrays[f"aux_species_{role}"])
        _require(species.dtype == np.int32 and set(species.tolist()) == set(range(7)), f"auxiliary species order drift: {bundle.target}/{bundle.held_fold}/{role}")
        masked = prepared["auxiliary"][role]
        raw = np.asarray(bundle.arrays[f"aux_x_{role}"])
        _require(masked.dtype == np.float32 and masked.shape[0] == raw.shape[0], f"auxiliary mask payload drift: {bundle.target}/{bundle.held_fold}/{role}")
    return {"target": bundle.target, "held_fold": bundle.held_fold, "bundle_digest": bundle.source_digest, "auxiliary_mask_digest": metadata["auxiliary_mask_digest"], "species_names_digest": _digest_value(species_names)}


def validate_stage(root: Path = PROJECT_ROOT, stage_root: Path = DEFAULT_STAGE_ROOT, bundle_root: Path = BUNDLE_ROOT, leaf_root: Path | None = None) -> dict[str, Any]:
    """Validate all accepted inputs and state metadata without fitting."""
    audit = _read_audit(root)
    stage_root = stage_root.resolve()
    manifest_path = _stage_manifest(stage_root)
    _require(manifest_path.is_file(), "reconstruction stage is not prepared")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(manifest == _manifest_payload(stage_root, audit), "reconstruction stage manifest drift")
    data, config = _load_staged_config(stage_root)
    leaf_root = (leaf_root or (root / "data/processed/dsdm/goal035-final-inner-lifecycle/private/leaves")).resolve()
    bundle_root = bundle_root.resolve()
    bundles = data.validate_bundle_inventory(bundle_root, config=config)
    leaves = _accepted_leaf_metadata(data, config, bundles, leaf_root)
    accepted_metadata_inventory_digest = _bind_accepted_metadata_inventory(audit, leaves)
    records: list[dict[str, Any]] = []
    input_records: list[dict[str, Any]] = []
    for bundle in sorted(bundles, key=lambda item: (item.target, item.held_fold)):
        leaf_path, leaf_metadata = leaves[(bundle.target, bundle.held_fold)]
        identity = leaf_metadata.get("identity")
        _require(isinstance(identity, dict) and identity.get("bundle_digest") == bundle.source_digest, f"leaf/bundle binding drift: {bundle.target}/{bundle.held_fold}")
        # Full leaf validation reads only the accepted prediction tensor and metadata;
        # it does not fit or access any outer assessment response.
        data.validate_leaf(leaf_path, identity)
        input_records.append(_validate_input_binding(data, bundle, leaf_metadata))
        for seed in SEEDS:
            record = _auxiliary_record(leaf_metadata, bundle.target, bundle.held_fold, seed)
            records.append({"target": bundle.target, "held_fold": bundle.held_fold, "seed": seed, **dict(record)})
    _validate_state_inventory(records)
    return {
        "status": "validated",
        "stage_root": str(stage_root),
        "config_digest": config.config_digest,
        "source_fingerprint": config.source_fingerprint,
        "runtime": dict(config.raw["runtime"]),
        "bundle_count": len(bundles),
        "leaf_count": len(leaves),
        "accepted_metadata_inventory_digest": accepted_metadata_inventory_digest,
        "auxiliary_state_count": len(records),
        "input_inventory_digest": _digest_value(input_records),
        "state_inventory_digest": _digest_value([{key: row[key] for key in ("target", "held_fold", "seed", "initial_model_digest", "initial_shared_digest", "final_shared_digest", "model_digest", "prediction_digest")} for row in records]),
        "outer_attempted": 0,
        "outer_opened": 0,
        "fits": 0,
    }


@dataclass(frozen=True)
class _StateTask:
    target: str
    held_fold: str
    seed: int
    epoch: int
    expected: Mapping[str, Any]
    bundle_path: Path
    output_path: Path
    receipt_path: Path
    attempt_path: Path | None = None


def _state_output_paths(private_root: Path, target: str, fold: str, seed: int) -> tuple[Path, Path]:
    stem = f"state--{target}--{fold}--seed{seed}"
    return private_root / "states" / f"{stem}.pt", private_root / "receipts" / f"{stem}.json"


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _attempt_payload(task: _StateTask, *, status: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "goal035-auxiliary-reconstruction-attempt-v1",
        "status": status,
        "target": task.target,
        "held_fold": task.held_fold,
        "seed": task.seed,
        "replay_epochs": task.epoch,
        "expected_semantic_digests": {key: task.expected.get(key) for key in SEMANTIC_DIGEST_KEYS},
        "expected_runtime_digest": task.expected.get("runtime_digest"),
        "config_digest": task.expected.get("config_digest"),
        "bundle_digest": task.expected.get("bundle_digest"),
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    payload.update(extra)
    return payload


def _validate_serialized_state(
    path: Path,
    expected_model_digest: str,
    identity: str,
    *,
    target: str | None = None,
    held_fold: str | None = None,
    seed: int | None = None,
    replay_epochs: int | None = None,
) -> None:
    """Validate a promoted state with the safe, CPU-only Torch loader."""
    import torch

    _require(path.is_file(), f"serialized state missing: {identity}")
    try:
        loaded = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise RecoveryError(f"serialized state cannot be loaded: {identity}") from exc
    _require(isinstance(loaded, dict), f"serialized state envelope invalid: {identity}")
    for key, expected in (("target", target), ("held_fold", held_fold), ("seed", seed), ("replay_epochs", replay_epochs)):
        if expected is not None:
            _require(loaded.get(key) == expected, f"serialized {key} mismatch: {identity}")
    state_dict = loaded.get("state_dict")
    _require(isinstance(state_dict, dict) and state_dict, f"serialized state dictionary invalid: {identity}")
    _require(all(isinstance(key, str) and isinstance(value, torch.Tensor) for key, value in state_dict.items()), f"serialized tensor inventory invalid: {identity}")
    _require(all(bool(torch.isfinite(value).all()) for value in state_dict.values()), f"serialized state contains non-finite values: {identity}")
    digest = hashlib.sha256()
    for name, value in sorted(state_dict.items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    recomputed_model_digest = digest.hexdigest()
    _require(recomputed_model_digest == expected_model_digest, f"serialized semantic digest mismatch: {identity}")
    _require(loaded.get("semantic_model_digest") == recomputed_model_digest, f"serialized envelope digest mismatch: {identity}")


def _replay_one(task: _StateTask, stage_root: Path) -> dict[str, Any]:
    """Run one exact replay in the archived runtime and write private state."""
    started = time.monotonic()
    attempt_path = task.attempt_path or task.receipt_path.with_name(task.receipt_path.stem + f".intent-{time.time_ns()}.json")
    _write_json_atomic(attempt_path, _attempt_payload(task, status="failure_intent", fit_started=False, started_at_ns=time.time_ns()))
    fit_started = False
    try:
        data, config = _load_staged_config(stage_root)
        bundle = data.load_case_npz(task.bundle_path)
        _require(bundle.target == task.target and bundle.held_fold == task.held_fold, "state bundle identity drift")
        prepared = data.prepare_case(bundle)
        names = tuple(name for name in SPECIES if name != task.target)
        import torch
        from dsdm.contracts import ARCHITECTURES, ArchitectureSpec
        from dsdm.models import MultiHeadResidual
        from dsdm.real_six_path import _optimizer, _prediction_digest, _prepare_device, _seed, _shared_digest, _state_digest, _train_epochs
        torch.set_num_threads(1)
        device = _prepare_device("cpu")
        runtime = data.runtime_attestation(config, strict=True)
        runtime_digest = data.digest_value(runtime)
        _require(runtime_digest == task.expected["runtime_digest"], f"runtime digest mismatch: {task.target}/{task.held_fold}/{task.seed}")
        spec = next(item for item in ARCHITECTURES if item[0] == config.corrected_winner)
        architecture = ArchitectureSpec(*spec)
        _seed(task.seed, device)
        model = MultiHeadResidual(architecture, 77, names).to(device)
        initial_model = _state_digest(model)
        initial_shared = _shared_digest(model)
        expected = task.expected
        _require(initial_model == expected["initial_model_digest"], f"initial model hash mismatch: {task.target}/{task.held_fold}/{task.seed}")
        _require(initial_shared == expected["initial_shared_digest"], f"initial shared hash mismatch: {task.target}/{task.held_fold}/{task.seed}")
        x = prepared["auxiliary"]["replay"]
        y = bundle.arrays["aux_y_replay"]
        species = bundle.arrays["aux_species_replay"]
        xt = torch.from_numpy(np.ascontiguousarray(x)).to(device)
        yt = torch.from_numpy(np.ascontiguousarray(y)).to(device)
        st = torch.from_numpy(np.ascontiguousarray(species)).to(device)
        fit_started = True
        _write_json_atomic(attempt_path, _attempt_payload(task, status="running", fit_started=True, started_at_ns=time.time_ns()))
        _train_epochs(model, _optimizer(model, architecture), xt, yt, st, names, epochs=task.epoch, seed=task.seed, freeze_shared=False)
        final_shared = _shared_digest(model)
        model_digest = _state_digest(model)
        prediction_digest = _prediction_digest(model, x, device, species, names)
        actual = {"initial_model_digest": initial_model, "replay_initial_model_digest": initial_model, "initial_shared_digest": initial_shared, "final_shared_digest": final_shared, "model_digest": model_digest, "prediction_digest": prediction_digest}
        _check_replay_digests(expected, actual, f"{task.target}/{task.held_fold}/{task.seed}")
        task.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = task.output_path.with_name(f".{task.output_path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        try:
            torch.save({"state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()}, "semantic_model_digest": model_digest, "target": task.target, "held_fold": task.held_fold, "seed": task.seed, "replay_epochs": task.epoch}, temporary)
            _validate_serialized_state(temporary, model_digest, f"{task.target}/{task.held_fold}/{task.seed}", target=task.target, held_fold=task.held_fold, seed=task.seed, replay_epochs=task.epoch)
            os.replace(temporary, task.output_path)
        finally:
            temporary.unlink(missing_ok=True)
        serialization_digest = _sha256(task.output_path)
        receipt = {"schema_version": "goal035-auxiliary-reconstruction-state-v1", "status": "accepted", "target": task.target, "held_fold": task.held_fold, "seed": task.seed, "replay_epochs": task.epoch, "initial_model_digest": initial_model, "replay_initial_model_digest": initial_model, "initial_shared_digest": initial_shared, "final_shared_digest": final_shared, "model_digest": model_digest, "prediction_digest": prediction_digest, "runtime_digest": runtime_digest, "serialization_sha256": serialization_digest, "config_digest": config.config_digest, "bundle_digest": bundle.source_digest, "attempt_receipt": str(attempt_path), "outer_attempted": 0, "outer_opened": 0, "wall_seconds": round(time.monotonic() - started, 6)}
        _write_json_atomic(task.receipt_path, receipt)
        _write_json_atomic(attempt_path, _attempt_payload(task, status="accepted", fit_started=True, started_at_ns=time.time_ns(), serialization_sha256=serialization_digest))
        return receipt
    except Exception as exc:
        _write_json_atomic(attempt_path, _attempt_payload(task, status="failed", fit_started=fit_started, error_type=type(exc).__name__, error=str(exc), failed_at_ns=time.time_ns()))
        raise RecoveryError(str(exc)) from exc


def run_recovery(root: Path = PROJECT_ROOT, stage_root: Path = DEFAULT_STAGE_ROOT, bundle_root: Path = BUNDLE_ROOT, leaf_root: Path | None = None, private_root: Path | None = None, *, execute: bool = False, workers: int = 3) -> dict[str, Any]:
    """Replay all missing states after an explicit execution acknowledgement."""
    _require(execute, "run is fit-gated; pass --execute only after independent review")
    _require(workers == 3, "recovery resource contract requires exactly three workers")
    validation = validate_stage(root, stage_root, bundle_root, leaf_root)
    stage_root = stage_root.resolve()
    private_root = (private_root or (stage_root / "private")).resolve()
    private_root.mkdir(parents=True, exist_ok=True)
    data, config = _load_staged_config(stage_root)
    bundles = data.validate_bundle_inventory(bundle_root, config=config)
    audit = _read_audit(root)
    leaves = _accepted_leaf_metadata(data, config, bundles, (leaf_root or (root / "data/processed/dsdm/goal035-final-inner-lifecycle/private/leaves")).resolve())
    accepted_metadata_inventory_digest = _bind_accepted_metadata_inventory(audit, leaves)
    tasks: list[_StateTask] = []
    for bundle in sorted(bundles, key=lambda item: (item.target, item.held_fold)):
        metadata = leaves[(bundle.target, bundle.held_fold)][1]
        for seed in SEEDS:
            expected = dict(_auxiliary_record(metadata, bundle.target, bundle.held_fold, seed))
            expected.update({"config_digest": config.config_digest, "bundle_digest": bundle.source_digest})
            output, receipt = _state_output_paths(private_root, bundle.target, bundle.held_fold, seed)
            if receipt.is_file() and output.is_file():
                saved = json.loads(receipt.read_text(encoding="utf-8"))
                if saved.get("status") == "accepted":
                    _check_replay_digests(expected, saved, f"{bundle.target}/{bundle.held_fold}/{seed}")
                    _require(saved.get("target") == bundle.target and saved.get("held_fold") == bundle.held_fold and saved.get("seed") == seed, f"state receipt identity drift: {bundle.target}/{bundle.held_fold}/{seed}")
                    _require(saved.get("config_digest") == config.config_digest and saved.get("bundle_digest") == bundle.source_digest and saved.get("runtime_digest") == expected.get("runtime_digest"), f"state receipt input binding drift: {bundle.target}/{bundle.held_fold}/{seed}")
                    _require(saved.get("replay_epochs") == expected.get("replay_epochs"), f"replay epoch mismatch: {bundle.target}/{bundle.held_fold}/{seed}")
                    _require(saved.get("serialization_sha256") == _sha256(output), f"serialized state hash mismatch: {bundle.target}/{bundle.held_fold}/{seed}")
                    _validate_serialized_state(output, expected["model_digest"], f"{bundle.target}/{bundle.held_fold}/{seed}", target=bundle.target, held_fold=bundle.held_fold, seed=seed, replay_epochs=int(expected["replay_epochs"]))
                    continue
                raise RecoveryError(f"completed state receipt/output mismatch; preserve and inspect before retry: {bundle.target}/{bundle.held_fold}/{seed}")
            _require(not output.exists() and not receipt.exists(), f"partial state/output exists; preserve and inspect before retry: {bundle.target}/{bundle.held_fold}/{seed}")
            prior_attempts = sorted(receipt.parent.glob(receipt.stem + ".intent-*.json"))
            _require(not prior_attempts, f"prior reconstruction attempt exists; preserve and inspect before retry: {bundle.target}/{bundle.held_fold}/{seed}")
            tasks.append(_StateTask(bundle.target, bundle.held_fold, seed, int(expected["replay_epochs"]), expected, bundle_root / f"{bundle.target}--{bundle.held_fold}.npz", output, receipt))

    receipts: list[dict[str, Any]] = []
    failure: BaseException | None = None
    pending_tasks = iter(tasks)
    context = mp.get_context("spawn")
    pool = ProcessPoolExecutor(max_workers=workers, mp_context=context)
    futures: dict[Any, _StateTask] = {}
    try:
        for _ in range(min(workers, len(tasks))):
            task = next(pending_tasks, None)
            if task is None:
                break
            attempt = task.receipt_path.with_name(task.receipt_path.stem + f".intent-{time.time_ns()}.json")
            task = _StateTask(task.target, task.held_fold, task.seed, task.epoch, task.expected, task.bundle_path, task.output_path, task.receipt_path, attempt)
            _write_json_atomic(attempt, _attempt_payload(task, status="failure_intent", fit_started=False, dispatched_at_ns=time.time_ns()))
            futures[pool.submit(_replay_one, task, stage_root)] = task
        while futures:
            done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
            completed_successes = 0
            for future in done:
                task = futures.pop(future)
                try:
                    result = future.result()
                except BaseException as exc:
                    if not isinstance(exc, (KeyboardInterrupt, SystemExit)) and failure is None:
                        failure = exc
                else:
                    receipts.append(result)
                    completed_successes += 1
            if failure is not None:
                for future in futures:
                    future.cancel()
            else:
                for _ in range(completed_successes):
                    next_task = next(pending_tasks, None)
                    if next_task is None:
                        break
                    attempt = next_task.receipt_path.with_name(next_task.receipt_path.stem + f".intent-{time.time_ns()}.json")
                    next_task = _StateTask(next_task.target, next_task.held_fold, next_task.seed, next_task.epoch, next_task.expected, next_task.bundle_path, next_task.output_path, next_task.receipt_path, attempt)
                    _write_json_atomic(attempt, _attempt_payload(next_task, status="failure_intent", fit_started=False, dispatched_at_ns=time.time_ns()))
                    futures[pool.submit(_replay_one, next_task, stage_root)] = next_task
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    if failure is not None:
        raise RecoveryError(f"auxiliary recovery stopped after first failure: {failure}") from failure
    all_receipts = []
    for bundle in sorted(bundles, key=lambda item: (item.target, item.held_fold)):
        metadata = leaves[(bundle.target, bundle.held_fold)][1]
        for seed in SEEDS:
            _, receipt_path = _state_output_paths(private_root, bundle.target, bundle.held_fold, seed)
            all_receipts.append(json.loads(receipt_path.read_text(encoding="utf-8")))
    _require(len(all_receipts) == EXPECTED_STATE_COUNT and all(row.get("status") == "accepted" for row in all_receipts), "not all 200 auxiliary states accepted")
    _validate_state_inventory(all_receipts)
    for row in all_receipts:
        target, held_fold, seed = row["target"], row["held_fold"], int(row["seed"])
        expected = dict(_auxiliary_record(leaves[(target, held_fold)][1], target, held_fold, seed))
        expected.update({"config_digest": config.config_digest, "bundle_digest": next(bundle.source_digest for bundle in bundles if bundle.target == target and bundle.held_fold == held_fold)})
        _check_replay_digests(expected, row, f"{target}/{held_fold}/{seed}")
        _require(row.get("config_digest") == expected["config_digest"] and row.get("bundle_digest") == expected["bundle_digest"] and row.get("runtime_digest") == expected["runtime_digest"], "final state input binding drift")
        _require(row.get("replay_epochs") == expected["replay_epochs"], "final state epoch drift")
        state_path, _receipt_path = _state_output_paths(private_root, target, held_fold, seed)
        _require(row.get("serialization_sha256") == _sha256(state_path), "final serialized state hash drift")
        _validate_serialized_state(state_path, expected["model_digest"], f"{target}/{held_fold}/{seed}", target=target, held_fold=held_fold, seed=seed, replay_epochs=int(expected["replay_epochs"]))
    aggregate = {"schema_version": "tasmania-auxiliary-recovery-v1", "status": "accepted", "method": "exact_goal035_multihead_replay", "config_digest": validation["config_digest"], "source_fingerprint": validation["source_fingerprint"], "stage_manifest_digest": _sha256(_stage_manifest(stage_root)), "audit_receipt_digest": audit.get("receipt_digest"), "accepted_metadata_inventory_digest": accepted_metadata_inventory_digest, "runtime": validation["runtime"], "runtime_digest": _digest_value(validation["runtime"]), "states": EXPECTED_STATE_COUNT, "new_fits": len(receipts), "resumed_matching_states": EXPECTED_STATE_COUNT - len(receipts), "workers": workers, "threads_per_worker": 1, "pooled_reconstructions": 0, "q_reconstructions": 0, "outer_attempted": 0, "outer_opened": 0, "serialization_inventory_digest": _digest_value(sorted((row["target"], row["held_fold"], row["seed"], row["serialization_sha256"]) for row in all_receipts)), "semantic_state_inventory_digest": _digest_value(sorted((row["initial_model_digest"], row["initial_shared_digest"], row["final_shared_digest"], row["model_digest"], row["prediction_digest"]) for row in all_receipts)), "private_root": str(private_root.relative_to(root)), "fits": EXPECTED_STATE_COUNT}
    AGGREGATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = AGGREGATE_PATH.with_name(f".{AGGREGATE_PATH.name}.tmp")
    temporary.write_text(json.dumps(aggregate, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, AGGREGATE_PATH)
    return aggregate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "run"))
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--stage-root", type=Path, default=DEFAULT_STAGE_ROOT)
    parser.add_argument("--bundle-root", type=Path, default=BUNDLE_ROOT)
    parser.add_argument("--leaf-root", type=Path, default=None)
    parser.add_argument("--private-root", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--execute", action="store_true", help="explicitly acknowledge that run may perform 200 replay fits")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_stage(args.root, args.stage_root)
        elif args.command == "validate":
            result = validate_stage(args.root, args.stage_root, args.bundle_root, args.leaf_root)
        else:
            result = run_recovery(args.root, args.stage_root, args.bundle_root, args.leaf_root, args.private_root, execute=args.execute, workers=args.workers)
    except RecoveryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
