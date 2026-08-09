"""Frozen full-training neural package for Goal 037.

This module prepares and validates models for a later one-shot outer
assessment.  It deliberately has no API that can open the outer vault.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import shutil
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch
from torch import nn

from .categorical_support import SupportMask, apply_support_mask, fit_support_mask
from .contracts import ARCHITECTURES, ENDPOINTS, FOLDS, METHODS, SPECIES, ArchitectureSpec
from .final_inner_data import canonical, digest_bytes, digest_value
from .models import MultiHeadResidual, ResidualMLP, set_trunk_trainable
from .real_six_path import (
    _cpu_state,
    _head_digest,
    _optimizer,
    _prepare_device,
    _residual_factory,
    _scalar_from_linear,
    _scalar_from_neural,
    _seed,
    _shared_digest,
    _shared_state,
    _state_digest,
    _train_epochs,
)
from .final_inner_runner import _q_fit


SEEDS = (31031, 31032, 31033, 31034, 31035)
PREDICTOR_COUNT = 77
Q_PREDICTOR_COUNT = 78
ARCHITECTURE_ID = "resmlp13"
EPOCH_POLICY_RECORDS = 8 * (2 * 5 + 7 * 6 * 5)
TARGET_MODELS_PER_SPECIES = 7 * 6 * 5
LOGICAL_ARTIFACTS_PER_SPECIES = 2 * 5 + 1 + TARGET_MODELS_PER_SPECIES
LOGICAL_ARTIFACTS = LOGICAL_ARTIFACTS_PER_SPECIES * 8
ENDPOINT_SLUGS = {endpoint: endpoint.replace("/", "_") for endpoint in ENDPOINTS}

AUTHORITY_KEYS = frozenset({
    "goal029_config", "goal029_summary", "goal029_core_manifest", "goal029_pair",
    "goal029_finalized", "goal035_config", "goal035_aggregate", "goal035_canary",
    "goal036_config", "goal036_summary", "goal036_decision",
    "goal036_stratum_metrics", "goal036_conventional_selection",
})
SOURCE_KEYS = frozenset({
    "outer_ready", "conventional_refit_import", "contracts", "models",
    "real_six_path", "categorical_support", "final_inner_data",
    "modeling_contract", "target_subsets", "goal029_production",
    "model_adapters", "uv_lock",
})


class OuterReadyError(ValueError):
    """Raised when Goal 037 evidence or model state is not outer-ready."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OuterReadyError(message)


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _sha_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _array_digest(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(canonical(dict(value)) + b"\n")
    temporary.replace(target)


def _bound_file(root: Path, binding: Mapping[str, Any], label: str) -> Path:
    _require(set(binding) == {"path", "sha256"}, f"{label} binding schema drift")
    candidate = (root / str(binding["path"])).resolve()
    _require(candidate.is_relative_to(root) and candidate.is_file() and not candidate.is_symlink(), f"{label} binding path invalid")
    _require(_is_digest(binding["sha256"]) and _sha_file(candidate) == binding["sha256"], f"{label} binding digest mismatch")
    return candidate


@dataclass(frozen=True)
class OuterReadyConfig:
    source_path: Path
    root: Path
    raw: Mapping[str, Any]
    config_digest: str
    authority_digests: Mapping[str, str]
    source_digests: Mapping[str, str]
    source_fingerprint: str
    private_root: Path
    tracked_root: Path
    goal035_private_root: Path
    epoch_policy_path: Path
    conventional_import_receipt: Path
    canary_receipt: Path


def load_config(path: str | Path, *, verify_sources: bool = True) -> OuterReadyConfig:
    source = Path(path).resolve()
    root = source.parents[1]
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("Goal037 config invalid") from exc
    expected_top = {
        "schema_version", "goal_id", "authorities", "execution_sources", "scope",
        "neural", "epoch_policy", "conventional", "runtime", "evidence", "privacy",
    }
    _require(set(raw) == expected_top, "Goal037 config schema drift")
    _require(raw["schema_version"] == "1.0" and raw["goal_id"] == "goal037-dsdm-outer-ready", "Goal037 config identity drift")
    _require(set(raw["authorities"]) == AUTHORITY_KEYS, "Goal037 authority inventory drift")
    _require(set(raw["execution_sources"]) == SOURCE_KEYS, "Goal037 execution-source inventory drift")
    authority_digests = {name: str(binding["sha256"]) for name, binding in raw["authorities"].items()}
    source_digests = {name: str(binding["sha256"]) for name, binding in raw["execution_sources"].items()}
    for name, binding in raw["authorities"].items():
        _bound_file(root, binding, name)
    if verify_sources:
        for name, binding in raw["execution_sources"].items():
            _bound_file(root, binding, name)
    scope = raw["scope"]
    _require(scope == {
        "species": list(SPECIES), "folds": list(FOLDS), "endpoints": list(ENDPOINTS),
        "neural_methods": list(METHODS),
        "conventional_families": ["intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann"],
        "seeds": list(SEEDS), "predictor_count": 77, "q_predictor_count": 78,
        "species_packages": 8, "epoch_policy_records": EPOCH_POLICY_RECORDS,
        "neural_logical_artifacts": LOGICAL_ARTIFACTS,
        "conventional_selected_refits": 952, "methods_total": 11,
    }, "Goal037 scope drift")
    neural = raw["neural"]
    _require(neural == {
        "architecture": ARCHITECTURE_ID, "optimizer": "AdamW", "learning_rate": 0.001,
        "batch_size": 128, "full_training_epoch_policy": "lower_median_of_five_inner_selected_epochs",
        "workers": 3, "device": "cpu", "torch_threads": 1, "blas_threads": 1,
        "q_linear": {"penalty": "elasticnet", "solver": "saga", "C": 1.0, "l1_ratio": 0.5, "max_iter": 5000, "tol": 0.00001, "stability_max_iter": 10000, "stability_probability_tolerance": 0.0001},
    }, "Goal037 neural policy drift")
    evidence = raw["evidence"]
    _require(set(evidence) == {"private_root", "tracked_root", "goal035_private_root", "epoch_policy", "conventional_import_receipt", "canary_receipt", "aggregate_receipt"}, "Goal037 evidence schema drift")
    paths = {key: (root / evidence[key]).resolve() for key in evidence if key != "aggregate_receipt"}
    _require(all(path.is_relative_to(root) for path in paths.values()), "Goal037 evidence path escape")
    tracked_root = paths["tracked_root"]
    aggregate = (root / evidence["aggregate_receipt"]).resolve()
    _require(aggregate.is_relative_to(tracked_root) and tracked_root.is_relative_to(root / "evidence"), "Goal037 tracked path invalid")
    privacy = raw["privacy"]
    _require(privacy == {"aggregate_only": True, "labels_private": True, "row_identifiers": False, "coordinates": False, "outer_attempted": 0, "outer_opened": 0}, "Goal037 privacy drift")
    _require(raw["epoch_policy"] == {"rule": "lower_median_of_five_inner_selected_epochs", "records": EPOCH_POLICY_RECORDS, "folds": 5, "maximum_epoch": 300, "outer_labels_used": False}, "Goal037 epoch-policy config drift")
    _require(raw["conventional"] == {
        "producer_commit": "f85e45922e182858fd351fdaf4f1b36b33fb4f2f",
        "validator_commit": "e6f07ae8bdb48399af907cf44598cc34d51391f6",
        "transaction_id": "38abaa77531936e9fe37c15f2ed9f08802f68e0b936ff5b351c0b38b45f83918",
        "private_core_manifest_sha256": "836384b71fa03797e3fe92052aed2255b737d59a347aaa8614830a28d0851ab6",
        "selected_refits": 952,
        "validation": "full_producer_publication_plus_local_challenge_replay",
    }, "Goal037 conventional authority drift")
    _require(set(raw["runtime"]) == {"neural", "conventional_producer", "conventional_scorer"}, "Goal037 runtime lane drift")
    return OuterReadyConfig(
        source_path=source,
        root=root,
        raw=raw,
        config_digest=_sha_file(source),
        authority_digests=authority_digests,
        source_digests=source_digests,
        source_fingerprint=digest_value({name: {"path": raw["execution_sources"][name]["path"], "sha256": source_digests[name]} for name in sorted(source_digests)}),
        private_root=paths["private_root"],
        tracked_root=tracked_root,
        goal035_private_root=paths["goal035_private_root"],
        epoch_policy_path=paths["epoch_policy"],
        conventional_import_receipt=paths["conventional_import_receipt"],
        canary_receipt=paths["canary_receipt"],
    )


def neural_runtime(config: OuterReadyConfig, *, strict: bool = True) -> dict[str, Any]:
    import scipy
    import sklearn
    import threadpoolctl

    try:
        pools = threadpoolctl.threadpool_info()
        blas_threads = max((int(item.get("num_threads", 0)) for item in pools if item.get("user_api") == "blas"), default=1)
    except (TypeError, ValueError):
        blas_threads = -1
    actual = {
        "system": platform.system(), "machine": platform.machine(),
        "python_major_minor": ".".join(platform.python_version().split(".")[:2]),
        "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
        "threadpoolctl": threadpoolctl.__version__, "torch": str(torch.__version__).split("+", 1)[0],
        "device": "cpu", "route": "mac_cpu", "torch_threads": torch.get_num_threads(), "blas_threads": blas_threads,
    }
    if strict:
        expected = config.raw["runtime"]["neural"]
        _require(actual == expected, "Goal037 neural runtime mismatch")
    return actual


def lower_median(values: Sequence[int]) -> int:
    """Return the frozen lower median of exactly five positive epoch counts."""
    epochs = list(values)
    _require(len(epochs) == 5, "full-training epoch policy requires five folds")
    _require(all(type(value) is int and 1 <= value <= 300 for value in epochs), "fold epoch invalid")
    return sorted(epochs)[2]


def validate_epoch_policy(value: Mapping[str, Any], *, expected_records: int = EPOCH_POLICY_RECORDS) -> dict[str, Any]:
    required = {
        "schema_version", "architecture", "fold_count", "source", "records",
        "policy_digest", "outer_attempted", "outer_opened",
    }
    # Small unit fixtures may omit the source and digest wrappers.
    fixture = set(value) == {"schema_version", "architecture", "fold_count", "records", "outer_attempted", "outer_opened"}
    _require(fixture or set(value) == required, "epoch-policy schema drift")
    _require(value.get("schema_version") == "goal037-epoch-policy-v1", "epoch-policy version drift")
    _require(value.get("architecture") == ARCHITECTURE_ID, "epoch-policy architecture drift")
    _require(value.get("fold_count") == 5, "epoch-policy fold count drift")
    _require(value.get("outer_attempted") == value.get("outer_opened") == 0, "epoch-policy outer access")
    records = value.get("records")
    _require(isinstance(records, list) and len(records) == expected_records, "epoch-policy record count drift")
    identities: set[tuple[Any, ...]] = set()
    for record in records:
        _require(
            isinstance(record, Mapping)
            and set(record) == {"target", "endpoint", "method", "seed", "fold_epochs", "full_training_epochs"},
            "epoch-policy record schema drift",
        )
        identity = (record["target"], record["endpoint"], record["method"], record["seed"])
        _require(identity not in identities, "duplicate epoch-policy identity")
        identities.add(identity)
        fold_epochs = record["fold_epochs"]
        _require(isinstance(fold_epochs, list), "epoch-policy fold epochs invalid")
        _require(record["full_training_epochs"] == lower_median(fold_epochs), "epoch-policy lower median mismatch")
    if not fixture:
        source = value.get("source")
        _require(isinstance(source, Mapping) and all(_is_digest(item) for item in source.values()), "epoch-policy source drift")
        body = dict(value)
        claimed = body.pop("policy_digest")
        _require(_is_digest(claimed) and claimed == digest_value(body), "epoch-policy digest mismatch")
    return {"records": len(records), "minimum": min((r["full_training_epochs"] for r in records), default=0), "maximum": max((r["full_training_epochs"] for r in records), default=0)}


def extract_epoch_policy(
    goal035_private_root: str | Path,
    goal035_aggregate_path: str | Path,
    output: str | Path,
) -> dict[str, Any]:
    """Extract the five-fold lower-median policy from validated Goal 035 leaves."""
    private_root = Path(goal035_private_root)
    aggregate_path = Path(goal035_aggregate_path)
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    _require(
        aggregate.get("success") is True
        and aggregate.get("cases") == 40
        and aggregate.get("outer_attempted") == aggregate.get("outer_opened") == 0,
        "Goal035 aggregate is not accepted authority",
    )
    config_digest = aggregate.get("config_digest")
    source_fingerprint = aggregate.get("source_fingerprint")
    _require(_is_digest(config_digest) and _is_digest(source_fingerprint), "Goal035 aggregate identity invalid")
    leaves: dict[tuple[str, str], Mapping[str, Any]] = {}
    directories: list[str] = []
    content_inventory: list[str] = []
    from .final_inner_data import validate_leaf
    for metadata_path in sorted((private_root / "leaves").glob("*/metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("config_digest") != config_digest:
            continue
        identity = metadata.get("identity", {})
        _require(metadata.get("outer_attempted") == metadata.get("outer_opened") == 0, "Goal035 leaf outer access")
        _require(metadata.get("architecture") == ARCHITECTURE_ID, "Goal035 leaf architecture drift")
        key = (str(metadata.get("target")), str(metadata.get("held_fold")))
        _require(key[0] in SPECIES and key[1] in FOLDS and key not in leaves, "Goal035 leaf identity drift")
        _require(identity.get("config_digest") == config_digest, "Goal035 leaf config binding drift")
        validated = validate_leaf(metadata_path.parent, identity)
        predictions = np.load(metadata_path.parent / "predictions.npy", allow_pickle=False)
        content_inventory.append(digest_value({"identity": identity, "metadata": validated, "predictions": _array_digest(predictions)}))
        leaves[key] = metadata
        directories.append(metadata_path.parent.name)
    _require(set(leaves) == {(target, fold) for target in SPECIES for fold in FOLDS}, "Goal035 current leaf cross-product incomplete")
    _require(digest_value(sorted(directories)) == aggregate.get("leaf_inventory_digest"), "Goal035 leaf inventory drift")
    _require(digest_value(sorted(content_inventory)) == aggregate.get("leaf_content_inventory_digest"), "Goal035 leaf content inventory drift")

    values: dict[tuple[str, str, str, int], dict[str, int]] = {}
    for (target, fold), metadata in leaves.items():
        artifacts = metadata.get("artifacts")
        _require(isinstance(artifacts, list) and len(artifacts) == 221, "Goal035 artifact inventory drift")
        for artifact in artifacts:
            identifier = str(artifact.get("artifact_id", ""))
            if identifier == "aux/q_linear":
                continue
            if identifier.startswith("aux/"):
                parts = identifier.split("/")
                _require(len(parts) == 3 and parts[1] in {"pooled", "multihead"} and parts[2].startswith("seed"), "Goal035 auxiliary artifact identity drift")
                endpoint, method, seed = "auxiliary", parts[1], int(parts[2][4:])
                _require(seed in SEEDS, "Goal035 artifact seed drift")
                key = (target, endpoint, method, seed)
                values.setdefault(key, {})[fold] = int(artifact.get("selected_epoch"))
            else:
                _require(identifier.startswith("target/"), "Goal035 artifact identity drift")

    # The target path is target/fraction/ladder/seed/method (six components).
    # Reparse target artifacts directly to avoid tolerating malformed variants.
    for (target, fold), metadata in leaves.items():
        for artifact in metadata["artifacts"]:
            identifier = str(artifact["artifact_id"])
            if not identifier.startswith("target/"):
                continue
            parts = identifier.split("/")
            _require(len(parts) == 5 and parts[0] == "target", "Goal035 target artifact identity drift")
            endpoint = f"{parts[1]}/{parts[2]}"
            seed = int(parts[3][4:]) if parts[3].startswith("seed") else -1
            method = parts[4]
            _require(endpoint in ENDPOINTS and seed in SEEDS and method in METHODS, "Goal035 target artifact scope drift")
            key = (target, endpoint, method, seed)
            values.setdefault(key, {})[fold] = int(artifact["selected_epoch"])

    expected = {
        *((target, "auxiliary", method, seed) for target in SPECIES for method in ("pooled", "multihead") for seed in SEEDS),
        *((target, endpoint, method, seed) for target in SPECIES for endpoint in ENDPOINTS for method in METHODS for seed in SEEDS),
    }
    _require(set(values) == expected, "Goal035 epoch-policy identity cross-product drift")
    records: list[dict[str, Any]] = []
    for target, endpoint, method, seed in sorted(values):
        by_fold = values[(target, endpoint, method, seed)]
        _require(set(by_fold) == set(FOLDS), "Goal035 epoch-policy fold inventory drift")
        fold_epochs = [by_fold[fold] for fold in FOLDS]
        records.append({
            "target": target,
            "endpoint": endpoint,
            "method": method,
            "seed": seed,
            "fold_epochs": fold_epochs,
            "full_training_epochs": lower_median(fold_epochs),
        })
    body: dict[str, Any] = {
        "schema_version": "goal037-epoch-policy-v1",
        "architecture": ARCHITECTURE_ID,
        "fold_count": 5,
        "source": {
            "goal035_aggregate_sha256": _sha_file(aggregate_path),
            "goal035_config_digest": str(config_digest),
            "goal035_source_fingerprint": str(source_fingerprint),
            "goal035_leaf_inventory_digest": str(aggregate["leaf_inventory_digest"]),
            "goal035_leaf_content_inventory_digest": str(aggregate["leaf_content_inventory_digest"]),
        },
        "records": records,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    body["policy_digest"] = digest_value(body)
    validate_epoch_policy(body)
    _write_json(output, body)
    return body


def _row_counter(x: np.ndarray, y: np.ndarray) -> Counter[tuple[bytes, bytes]]:
    xx = np.array(x, dtype=np.float32, copy=True, order="C")
    yy = np.array(y, dtype=np.float32, copy=True, order="C")
    return Counter((np.ascontiguousarray(xx[index]).tobytes(), np.asarray(yy[index], dtype=np.float32).tobytes()) for index in range(len(xx)))


def _counter_subset(left: Counter[Any], right: Counter[Any]) -> bool:
    return all(count <= right.get(key, 0) for key, count in left.items())


def _bundle_array_keys() -> set[str]:
    keys = {"aux_x", "aux_y", "aux_species"}
    for endpoint in ENDPOINTS:
        slug = ENDPOINT_SLUGS[endpoint]
        keys.update({f"target_{slug}_x", f"target_{slug}_y"})
    return keys


@dataclass(frozen=True)
class OuterTrainingBundle:
    target: str
    arrays: Mapping[str, np.ndarray]
    metadata: Mapping[str, Any]
    bundle_digest: str

    def __post_init__(self) -> None:
        _require(self.target in SPECIES, "outer-training bundle target invalid")
        _require(_is_digest(self.bundle_digest), "outer-training bundle digest invalid")
        arrays = {name: np.asarray(value) for name, value in self.arrays.items()}
        _require(set(arrays) == _bundle_array_keys(), "outer-training bundle array inventory drift")
        for endpoint in ENDPOINTS:
            slug = ENDPOINT_SLUGS[endpoint]
            x, y = arrays[f"target_{slug}_x"], arrays[f"target_{slug}_y"]
            _require(x.dtype == np.float32 and x.ndim == 2 and x.shape[1] == PREDICTOR_COUNT and len(x) > 0 and np.isfinite(x).all(), f"target predictors invalid: {endpoint}")
            _require(y.dtype == np.float32 and y.ndim == 1 and len(y) == len(x) and set(np.unique(y).tolist()) == {0.0, 1.0}, f"target response invalid: {endpoint}")
            masked, _ = apply_support_mask(x, fit_support_mask(x))
            _require(masked.tobytes(order="C") == x.tobytes(order="C"), f"target training mask changed bytes: {endpoint}")
        for ladder in ("ladder00", "ladder01", "ladder02"):
            chain = []
            for fraction in (25, 50, 100):
                endpoint = "fraction100/full" if fraction == 100 else f"fraction{fraction}/{ladder}"
                slug = ENDPOINT_SLUGS[endpoint]
                chain.append(_row_counter(arrays[f"target_{slug}_x"], arrays[f"target_{slug}_y"]))
            _require(_counter_subset(chain[0], chain[1]) and _counter_subset(chain[1], chain[2]), f"outer-training target nesting failed: {ladder}")
        x_aux, y_aux, species = arrays["aux_x"], arrays["aux_y"], arrays["aux_species"]
        _require(x_aux.dtype == np.float32 and x_aux.ndim == 2 and x_aux.shape[1] == PREDICTOR_COUNT and len(x_aux) > 0 and np.isfinite(x_aux).all(), "auxiliary predictors invalid")
        _require(y_aux.dtype == np.float32 and y_aux.shape == (len(x_aux),) and set(np.unique(y_aux).tolist()) == {0.0, 1.0}, "auxiliary response invalid")
        _require(species.dtype == np.int32 and species.shape == (len(x_aux),) and set(species.tolist()) == set(range(7)), "auxiliary species invalid")
        masked_aux, _ = apply_support_mask(x_aux, fit_support_mask(x_aux))
        _require(masked_aux.tobytes(order="C") == x_aux.tobytes(order="C"), "auxiliary training mask changed bytes")
        metadata = dict(self.metadata)
        _require(metadata.get("outer_attempted") == metadata.get("outer_opened") == 0, "outer-training bundle outer access")
        inventory = {name: _array_digest(array) for name, array in sorted(arrays.items())}
        _require(metadata.get("array_digests") == inventory, "outer-training bundle array digest drift")
        body = dict(metadata)
        claimed = body.pop("bundle_digest", None)
        _require(claimed == self.bundle_digest == digest_value({"metadata": body, "arrays": inventory}), "outer-training bundle digest mismatch")
        for array in arrays.values():
            array.flags.writeable = False
        object.__setattr__(self, "arrays", arrays)


def save_outer_bundle(bundle: OuterTrainingBundle, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {**bundle.arrays, "metadata_json": np.frombuffer(canonical(dict(bundle.metadata)), dtype=np.uint8)}
    temporary = target.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **payload)
    temporary.replace(target)
    load_outer_bundle(target)
    return target


def load_outer_bundle(path: str | Path) -> OuterTrainingBundle:
    source = Path(path)
    _require(source.is_file() and not source.is_symlink(), "outer-training bundle missing")
    try:
        with np.load(source, allow_pickle=False) as loaded:
            _require("metadata_json" in loaded.files, "outer-training metadata missing")
            metadata = json.loads(np.asarray(loaded["metadata_json"], dtype=np.uint8).tobytes().decode("utf-8"))
            arrays = {name: np.array(loaded[name], copy=True) for name in loaded.files if name != "metadata_json"}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise OuterReadyError("outer-training bundle invalid") from exc
    return OuterTrainingBundle(str(metadata.get("target")), arrays, metadata, str(metadata.get("bundle_digest")))


def prepare_outer_bundle(bundle: OuterTrainingBundle) -> dict[str, Any]:
    target_masks: dict[str, SupportMask] = {}
    target: dict[str, np.ndarray] = {}
    for endpoint in ENDPOINTS:
        slug = ENDPOINT_SLUGS[endpoint]
        mask = fit_support_mask(bundle.arrays[f"target_{slug}_x"])
        target_masks[endpoint] = mask
        target[endpoint] = apply_support_mask(bundle.arrays[f"target_{slug}_x"], mask)[0]
    aux_mask = fit_support_mask(bundle.arrays["aux_x"])
    auxiliary = apply_support_mask(bundle.arrays["aux_x"], aux_mask)[0]
    q_inputs = {endpoint: apply_support_mask(bundle.arrays[f"target_{ENDPOINT_SLUGS[endpoint]}_x"], aux_mask)[0] for endpoint in ENDPOINTS}
    return {"target": target, "target_masks": target_masks, "auxiliary": auxiliary, "auxiliary_mask": aux_mask, "q_inputs": q_inputs}


def export_outer_training_bundles(
    root: str | Path,
    goal035_config_path: str | Path,
    output: str | Path,
) -> list[Path]:
    """Materialize eight full outer-training bundles without touching the vault."""
    from .real_data import _encode
    from dsdm_phase1.goal029_production import ingest_production_foundation
    from dsdm_phase1.target_subsets import build_ladders

    repo_root = Path(root).resolve()
    goal035_path = Path(goal035_config_path).resolve()
    goal035 = json.loads(goal035_path.read_text(encoding="utf-8"))
    binding = goal035["authorities"]["goal029_config"]
    goal029_path = repo_root / binding["path"]
    _require(_sha_file(goal029_path) == binding["sha256"], "Goal029 foundation authority drift")
    goal029 = json.loads(goal029_path.read_text(encoding="utf-8"))
    broker, provider, vault = ingest_production_foundation(repo_root, goal029)
    _require(vault.attempted_open_count == vault.open_count == 0, "outer access during full-training export")
    outer_rows = broker._rows
    output_root = Path(output)
    output_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    source_tokens = []
    for key, label, source in zip(outer_rows.keys, outer_rows.pa, outer_rows.response_source, strict=True):
        source_tokens.append((key.species_id, key.grid_cell_id, broker._fold_by_key[key], str(source), int(label)))
    source_binding_digest = digest_value(source_tokens)
    transform_digest = digest_value(provider.substrate.transform_record("outer"))
    for target_name in SPECIES:
        target_rows = broker.outer_training(target_name)
        ladders = build_ladders(target_rows)
        arrays: dict[str, np.ndarray] = {}
        subset_digests: dict[str, str] = {}
        for endpoint in ENDPOINTS:
            fraction, ladder = endpoint.split("/")
            lookup = "ladder00" if fraction == "fraction100" else ladder
            subset = ladders[(fraction, lookup)]
            rows = []
            labels = []
            for key in subset.keys:
                value = provider._value(key, "outer")
                record = {"x": value["continuous"], **value["categorical"]}
                rows.append(_encode(record))
                labels.append(float(target_rows.pa[target_rows.keys.index(key)]))
            slug = ENDPOINT_SLUGS[endpoint]
            arrays[f"target_{slug}_x"] = np.stack(rows).astype(np.float32)
            arrays[f"target_{slug}_y"] = np.asarray(labels, dtype=np.float32)
            subset_digests[endpoint] = str(subset.subset_digest)
        auxiliary_names = tuple(name for name in SPECIES if name != target_name)
        species_index = {name: index for index, name in enumerate(auxiliary_names)}
        aux_x: list[np.ndarray] = []
        aux_y: list[float] = []
        aux_species: list[int] = []
        aux_sources: Counter[str] = Counter()
        for key, label, source in zip(outer_rows.keys, outer_rows.pa, outer_rows.response_source, strict=True):
            if key.species_id == target_name or source not in {"presence", "survey_supported_absence"}:
                continue
            value = provider._value(key, "outer")
            aux_x.append(_encode({"x": value["continuous"], **value["categorical"]}))
            aux_y.append(float(label))
            aux_species.append(species_index[key.species_id])
            aux_sources[str(source)] += 1
        arrays["aux_x"] = np.stack(aux_x).astype(np.float32)
        arrays["aux_y"] = np.asarray(aux_y, dtype=np.float32)
        arrays["aux_species"] = np.asarray(aux_species, dtype=np.int32)
        inventory = {name: _array_digest(array) for name, array in sorted(arrays.items())}
        metadata: dict[str, Any] = {
            "schema_version": "goal037-outer-training-bundle-v1",
            "goal_id": "goal037-dsdm-outer-ready",
            "target": target_name,
            "goal035_config_sha256": _sha_file(goal035_path),
            "goal029_config_sha256": _sha_file(goal029_path),
            "source_binding_digest": source_binding_digest,
            "outer_transform_digest": transform_digest,
            "subset_membership_digests": subset_digests,
            "auxiliary_species_count": 7,
            "auxiliary_source_counts": dict(sorted(aux_sources.items())),
            "auxiliary_pseudoabsence_rows": 0,
            "array_shapes": {name: list(array.shape) for name, array in sorted(arrays.items())},
            "array_digests": inventory,
            "privacy": {"labels_private": True, "row_identifiers": False, "coordinates": False},
            "outer_attempted": 0,
            "outer_opened": 0,
        }
        metadata["bundle_digest"] = digest_value({"metadata": metadata, "arrays": inventory})
        bundle = OuterTrainingBundle(target_name, arrays, metadata, metadata["bundle_digest"])
        written.append(save_outer_bundle(bundle, output_root / f"{target_name}.npz"))
    _require(vault.attempted_open_count == vault.open_count == 0, "outer access during full-training export")
    _require(len(written) == 8, "outer-training bundle count drift")
    return written


def _architecture() -> ArchitectureSpec:
    row = next((row for row in ARCHITECTURES if row[0] == ARCHITECTURE_ID), None)
    _require(row is not None, "frozen architecture missing")
    return ArchitectureSpec(*row)


@dataclass(frozen=True)
class ExactFit:
    model: nn.Module
    epochs: int
    initial_model_digest: str
    initial_shared_digest: str
    initial_head_digest: str
    state_digest: str
    final_shared_digest: str
    wall_seconds: float


def exact_fit(
    factory: Callable[[], nn.Module],
    spec: ArchitectureSpec,
    seed: int,
    x: np.ndarray,
    y: np.ndarray,
    *,
    epochs: int,
    species: np.ndarray | None = None,
    species_names: Sequence[str] = (),
    freeze_shared: bool = False,
    device: str = "cpu",
) -> ExactFit:
    """Fit one freshly initialized model for exactly the frozen epoch count."""
    _require(type(seed) is int and 0 <= seed < 2**32, "exact-fit seed invalid")
    _require(type(epochs) is int and 1 <= epochs <= 300, "exact-fit epochs invalid")
    xx = np.array(x, dtype=np.float32, copy=True, order="C")
    yy = np.array(y, dtype=np.float32, copy=True, order="C")
    _require(xx.ndim == 2 and yy.ndim == 1 and len(xx) == len(yy) > 0, "exact-fit array shape invalid")
    _require(np.isfinite(xx).all() and np.isin(yy, (0.0, 1.0)).all(), "exact-fit values invalid")
    if species is not None:
        ss = np.array(species, dtype=np.int32, copy=True, order="C")
        _require(ss.shape == yy.shape and set(ss.tolist()) == set(range(len(species_names))), "exact-fit species invalid")
    else:
        ss = None
    target_device = _prepare_device(device)
    started = time.monotonic()
    _seed(seed, target_device)
    model = factory().to(target_device)
    if isinstance(model, ResidualMLP):
        set_trunk_trainable(model, not freeze_shared)
    initial_model = _state_digest(model)
    initial_shared = _shared_digest(model)
    initial_head = _head_digest(model) if isinstance(model, ResidualMLP) else "not_applicable"
    _train_epochs(
        model,
        _optimizer(model, spec),
        torch.from_numpy(np.ascontiguousarray(xx)).to(target_device),
        torch.from_numpy(np.ascontiguousarray(yy)).to(target_device),
        None if ss is None else torch.from_numpy(np.ascontiguousarray(ss)).to(target_device),
        tuple(species_names),
        epochs=epochs,
        seed=seed,
        freeze_shared=freeze_shared,
    )
    _require(all(bool(torch.isfinite(parameter).all()) for parameter in model.parameters()), "exact-fit non-finite state")
    return ExactFit(
        model=model,
        epochs=epochs,
        initial_model_digest=initial_model,
        initial_shared_digest=initial_shared,
        initial_head_digest=initial_head,
        state_digest=_state_digest(model),
        final_shared_digest=_shared_digest(model),
        wall_seconds=round(time.monotonic() - started, 6),
    )


def score_neural_model(model: ResidualMLP, x: np.ndarray, *, device: str = "cpu") -> np.ndarray:
    values = np.asarray(x, dtype=np.float32)
    _require(values.ndim == 2 and len(values) > 0 and np.isfinite(values).all(), "scoring predictors invalid")
    target_device = _prepare_device(device)
    model = model.to(target_device).eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(torch.from_numpy(np.ascontiguousarray(values)).to(target_device)))
    output = scores.detach().cpu().numpy().astype(np.float32, copy=False)
    _require(output.shape == (len(values),) and np.isfinite(output).all() and np.all((output >= 0) & (output <= 1)), "neural scores invalid")
    return output


def save_neural_model(
    model: ResidualMLP,
    path: str | Path,
    *,
    identity: Mapping[str, Any],
    challenge_x: np.ndarray,
) -> dict[str, Any]:
    """Write a trusted weights-only model and return its external receipt."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "identity_json": canonical(dict(identity)).decode("utf-8"),
        "state_dict": {name: value.detach().cpu().contiguous() for name, value in sorted(model.state_dict().items())},
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(target)
    challenge = score_neural_model(model, challenge_x)
    receipt = {
        "identity": dict(identity),
        "identity_digest": digest_value(dict(identity)),
        "model_sha256": _sha_file(target),
        "state_digest": _state_digest(model),
        "challenge_prediction_digest": _array_digest(challenge),
        "bytes": target.stat().st_size,
    }
    # Read-after-write is part of publication, not a later optional check.
    load_neural_model(target, spec=_architecture() if identity.get("architecture") == ARCHITECTURE_ID else None, input_dim=int(identity["input_dim"]), expected=receipt, challenge_x=challenge_x, test_spec=None if identity.get("architecture") == ARCHITECTURE_ID else model)
    return receipt


def load_neural_model(
    path: str | Path,
    *,
    spec: ArchitectureSpec | None,
    input_dim: int,
    expected: Mapping[str, Any],
    challenge_x: np.ndarray,
    test_spec: ResidualMLP | None = None,
) -> ResidualMLP:
    target = Path(path)
    _require(target.is_file() and not target.is_symlink(), "neural model missing")
    _require(_sha_file(target) == expected.get("model_sha256"), "neural model file digest mismatch")
    try:
        payload = torch.load(target, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise OuterReadyError("neural model payload invalid") from exc
    _require(isinstance(payload, Mapping) and set(payload) == {"identity_json", "state_dict"}, "neural model payload schema drift")
    try:
        identity = json.loads(payload["identity_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise OuterReadyError("neural model identity invalid") from exc
    _require(identity == expected.get("identity") and digest_value(identity) == expected.get("identity_digest"), "neural model identity mismatch")
    model = deepcopy(test_spec) if test_spec is not None else ResidualMLP(spec, input_dim)  # type: ignore[arg-type]
    try:
        model.load_state_dict(payload["state_dict"], strict=True)
    except Exception as exc:
        raise OuterReadyError("neural model state invalid") from exc
    _require(_state_digest(model) == expected.get("state_digest"), "neural model state digest mismatch")
    _require(_array_digest(score_neural_model(model, challenge_x)) == expected.get("challenge_prediction_digest"), "neural challenge replay mismatch")
    return model.eval()


def score_multihead_model(
    model: MultiHeadResidual,
    x: np.ndarray,
    species: np.ndarray,
    species_names: Sequence[str],
    *,
    device: str = "cpu",
) -> np.ndarray:
    xx = np.asarray(x, dtype=np.float32)
    ss = np.asarray(species, dtype=np.int32)
    _require(xx.ndim == 2 and ss.shape == (len(xx),) and len(xx) > 0, "multihead scoring arrays invalid")
    _require(set(ss.tolist()) <= set(range(len(species_names))), "multihead scoring species invalid")
    target_device = _prepare_device(device)
    model = model.to(target_device).eval()
    tensor_x = torch.from_numpy(np.ascontiguousarray(xx)).to(target_device)
    tensor_s = torch.from_numpy(np.ascontiguousarray(ss)).to(target_device)
    logits = torch.empty(len(xx), dtype=torch.float32, device=target_device)
    with torch.no_grad():
        for index, name in enumerate(species_names):
            mask = tensor_s == index
            if bool(mask.any()):
                logits[mask] = model(tensor_x[mask], name)
        output = torch.sigmoid(logits).detach().cpu().numpy().astype(np.float32, copy=False)
    _require(np.isfinite(output).all() and np.all((output >= 0) & (output <= 1)), "multihead scores invalid")
    return output


def save_multihead_model(
    model: MultiHeadResidual,
    path: str | Path,
    *,
    identity: Mapping[str, Any],
    challenge_x: np.ndarray,
    challenge_species: np.ndarray,
    species_names: Sequence[str],
) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "identity_json": canonical(dict(identity)).decode("utf-8"),
        "state_dict": {name: value.detach().cpu().contiguous() for name, value in sorted(model.state_dict().items())},
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(target)
    receipt = {
        "identity": dict(identity), "identity_digest": digest_value(dict(identity)),
        "model_sha256": _sha_file(target), "state_digest": _state_digest(model),
        "challenge_prediction_digest": _array_digest(score_multihead_model(model, challenge_x, challenge_species, species_names)),
        "bytes": target.stat().st_size,
    }
    load_multihead_model(target, spec=_architecture(), input_dim=int(identity["input_dim"]), species_names=species_names, expected=receipt, challenge_x=challenge_x, challenge_species=challenge_species)
    return receipt


def load_multihead_model(
    path: str | Path,
    *,
    spec: ArchitectureSpec,
    input_dim: int,
    species_names: Sequence[str],
    expected: Mapping[str, Any],
    challenge_x: np.ndarray,
    challenge_species: np.ndarray,
) -> MultiHeadResidual:
    target = Path(path)
    _require(target.is_file() and not target.is_symlink() and _sha_file(target) == expected.get("model_sha256"), "multihead model digest mismatch")
    try:
        payload = torch.load(target, map_location="cpu", weights_only=True)
        identity = json.loads(payload["identity_json"])
    except Exception as exc:
        raise OuterReadyError("multihead model payload invalid") from exc
    _require(set(payload) == {"identity_json", "state_dict"} and identity == expected.get("identity") and digest_value(identity) == expected.get("identity_digest"), "multihead model identity mismatch")
    model = MultiHeadResidual(spec, input_dim, tuple(species_names))
    try:
        model.load_state_dict(payload["state_dict"], strict=True)
    except Exception as exc:
        raise OuterReadyError("multihead model state invalid") from exc
    _require(_state_digest(model) == expected.get("state_digest"), "multihead model state digest mismatch")
    _require(_array_digest(score_multihead_model(model, challenge_x, challenge_species, species_names)) == expected.get("challenge_prediction_digest"), "multihead challenge replay mismatch")
    return model.eval()


def _sigmoid(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    output = np.empty_like(values)
    positive = values >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponent = np.exp(values[~positive])
    output[~positive] = exponent / (1.0 + exponent)
    return output.astype(np.float32)


def score_q_payload(payload: Mapping[str, Any], x: np.ndarray) -> np.ndarray:
    xx = np.asarray(x, dtype=np.float32)
    coefficient = np.asarray(payload.get("coefficient"), dtype=np.float64)
    intercept = np.asarray(payload.get("intercept"), dtype=np.float64)
    _require(xx.ndim == 2 and coefficient.shape == (1, xx.shape[1]) and intercept.shape == (1,), "q payload shape invalid")
    scores = _sigmoid(np.asarray(xx, dtype=np.float64) @ coefficient.T + intercept).reshape(-1)
    _require(scores.shape == (len(xx),) and np.isfinite(scores).all(), "q payload scores invalid")
    return scores


def save_q_model(model: Any, path: str | Path, *, identity: Mapping[str, Any], challenge_x: np.ndarray, artifact: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "goal037-q-linear-v1",
        "identity": dict(identity),
        "identity_digest": digest_value(dict(identity)),
        "classes": np.asarray(model.classes_, dtype=np.int64).tolist(),
        "coefficient": np.asarray(model.coef_, dtype=np.float64).tolist(),
        "intercept": np.asarray(model.intercept_, dtype=np.float64).tolist(),
        "n_iter": int(np.max(model.n_iter_)),
        "termination_status": artifact["termination_status"],
    }
    payload["challenge_prediction_digest"] = _array_digest(score_q_payload(payload, challenge_x))
    _write_json(path, payload)
    receipt = {
        "identity": dict(identity), "identity_digest": payload["identity_digest"],
        "model_sha256": _sha_file(path), "state_digest": digest_value({key: payload[key] for key in ("classes", "coefficient", "intercept")}),
        "challenge_prediction_digest": payload["challenge_prediction_digest"], "bytes": Path(path).stat().st_size,
    }
    load_q_model(path, expected=receipt, challenge_x=challenge_x)
    return receipt


def load_q_model(path: str | Path, *, expected: Mapping[str, Any], challenge_x: np.ndarray) -> Mapping[str, Any]:
    target = Path(path)
    _require(target.is_file() and not target.is_symlink() and _sha_file(target) == expected.get("model_sha256"), "q model file digest mismatch")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("q model payload invalid") from exc
    _require(payload.get("schema_version") == "goal037-q-linear-v1", "q model version drift")
    _require(payload.get("identity") == expected.get("identity") and payload.get("identity_digest") == expected.get("identity_digest") == digest_value(payload["identity"]), "q model identity mismatch")
    state = {key: payload[key] for key in ("classes", "coefficient", "intercept")}
    _require(payload.get("classes") == [0, 1] and digest_value(state) == expected.get("state_digest"), "q model state mismatch")
    _require(_array_digest(score_q_payload(payload, challenge_x)) == expected.get("challenge_prediction_digest") == payload.get("challenge_prediction_digest"), "q challenge replay mismatch")
    return payload


def _fit_seed(target: str, endpoint: str, seed: int, purpose: str) -> int:
    token = f"goal037-outer-ready|{target}|{endpoint}|{seed}|{purpose}|{ARCHITECTURE_ID}"
    return int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:4], "big")


def _challenge(x: np.ndarray, maximum: int = 16) -> np.ndarray:
    values = np.asarray(x, dtype=np.float32)
    _require(values.ndim == 2 and len(values) > 0, "challenge predictors invalid")
    if len(values) <= maximum:
        return np.array(values, copy=True, order="C")
    half = maximum // 2
    return np.concatenate((values[:half], values[-(maximum - half):]), axis=0).astype(np.float32, copy=False)


def _challenge_with_species(x: np.ndarray, species: np.ndarray, maximum: int = 28) -> tuple[np.ndarray, np.ndarray]:
    xx = np.asarray(x, dtype=np.float32)
    ss = np.asarray(species, dtype=np.int32)
    indices: list[int] = []
    per_species = max(1, maximum // 7)
    for index in range(7):
        positions = np.flatnonzero(ss == index)
        _require(len(positions) > 0, "auxiliary challenge species missing")
        take = positions[:per_species]
        indices.extend(int(value) for value in take)
    selected = np.asarray(indices, dtype=np.int64)
    return np.array(xx[selected], copy=True, order="C"), np.array(ss[selected], copy=True)


def _policy_lookup(policy: Mapping[str, Any]) -> dict[tuple[str, str, str, int], int]:
    validate_epoch_policy(policy)
    return {(str(row["target"]), str(row["endpoint"]), str(row["method"]), int(row["seed"])): int(row["full_training_epochs"]) for row in policy["records"]}


def _artifact_from_fit(
    identifier: str,
    fit: ExactFit,
    *,
    fit_seed: int,
    model_receipt: Mapping[str, Any],
    model_relative_path: str,
    runtime_digest: str,
    freeze_shared: bool = False,
) -> dict[str, Any]:
    return {
        "artifact_id": identifier, "kind": "auxiliary" if identifier.startswith("aux/") else "target",
        "fit_seed": fit_seed, "exact_epochs": fit.epochs,
        "initial_model_digest": fit.initial_model_digest, "initial_shared_digest": fit.initial_shared_digest,
        "initial_head_digest": fit.initial_head_digest, "model_digest": fit.state_digest,
        "final_shared_digest": fit.final_shared_digest, "freeze_shared": freeze_shared,
        "model_relative_path": model_relative_path, "model_receipt": dict(model_receipt),
        "runtime_digest": runtime_digest, "finite": True, "physical_fits": 1,
        "wall_seconds": fit.wall_seconds,
    }


def _model_filename(identifier: str, suffix: str = ".pt") -> str:
    return identifier.replace("/", "--") + suffix


def _package_identity(
    bundle: OuterTrainingBundle,
    config: OuterReadyConfig,
    policy: Mapping[str, Any],
    runtime_digest: str,
    seeds: Sequence[int],
    endpoints: Sequence[str],
) -> dict[str, Any]:
    return {
        "target": bundle.target, "bundle_digest": bundle.bundle_digest,
        "config_digest": config.config_digest, "source_fingerprint": config.source_fingerprint,
        "epoch_policy_digest": policy["policy_digest"], "runtime_digest": runtime_digest,
        "architecture": ARCHITECTURE_ID, "seeds": list(seeds), "endpoints": list(endpoints),
    }


def _run_package(
    bundle: OuterTrainingBundle,
    config: OuterReadyConfig,
    policy: Mapping[str, Any],
    destination: Path,
    *,
    seeds: Sequence[int] = SEEDS,
    endpoints: Sequence[str] = ENDPOINTS,
) -> Mapping[str, Any]:
    runtime = neural_runtime(config, strict=True)
    runtime_digest = digest_value(runtime)
    lookup = _policy_lookup(policy)
    prepared = prepare_outer_bundle(bundle)
    spec = _architecture()
    target = bundle.target
    species_names = tuple(name for name in SPECIES if name != target)
    if destination.exists():
        _require(destination.is_dir() and not any(destination.iterdir()), "package destination is not empty")
    else:
        destination.mkdir(parents=True)
    model_root = destination / "models"
    model_root.mkdir()
    artifacts: list[dict[str, Any]] = []
    pooled_by_seed: dict[int, ExactFit] = {}
    multi_by_seed: dict[int, ExactFit] = {}
    aux_challenge_x, aux_challenge_species = _challenge_with_species(
        prepared["auxiliary"], bundle.arrays["aux_species"]
    )

    for seed in seeds:
        pooled_epochs = lookup[(target, "auxiliary", "pooled", seed)]
        pooled = exact_fit(
            _residual_factory(spec, PREDICTOR_COUNT), spec, seed,
            prepared["auxiliary"], bundle.arrays["aux_y"], epochs=pooled_epochs,
            species=bundle.arrays["aux_species"], species_names=species_names,
        )
        pooled_by_seed[seed] = pooled
        pooled_id = f"aux/pooled/seed{seed}"
        pooled_relative = f"models/{_model_filename(pooled_id)}"
        pooled_identity = {
            **_package_identity(bundle, config, policy, runtime_digest, seeds, endpoints),
            "artifact_id": pooled_id, "input_dim": PREDICTOR_COUNT,
            "method": "pooled", "seed": seed, "exact_epochs": pooled_epochs,
        }
        pooled_receipt = save_neural_model(
            pooled.model, destination / pooled_relative, identity=pooled_identity,
            challenge_x=aux_challenge_x,
        )
        artifacts.append(_artifact_from_fit(
            pooled_id, pooled, fit_seed=seed, model_receipt=pooled_receipt,
            model_relative_path=pooled_relative, runtime_digest=runtime_digest,
        ))

        multi_epochs = lookup[(target, "auxiliary", "multihead", seed)]
        multi = exact_fit(
            lambda: MultiHeadResidual(spec, PREDICTOR_COUNT, species_names), spec, seed,
            prepared["auxiliary"], bundle.arrays["aux_y"], epochs=multi_epochs,
            species=bundle.arrays["aux_species"], species_names=species_names,
        )
        multi_by_seed[seed] = multi
        multi_id = f"aux/multihead/seed{seed}"
        multi_relative = f"models/{_model_filename(multi_id)}"
        multi_identity = {
            **_package_identity(bundle, config, policy, runtime_digest, seeds, endpoints),
            "artifact_id": multi_id, "input_dim": PREDICTOR_COUNT,
            "method": "multihead", "seed": seed, "exact_epochs": multi_epochs,
            "species_names": list(species_names),
        }
        multi_receipt = save_multihead_model(
            multi.model, destination / multi_relative, identity=multi_identity,
            challenge_x=aux_challenge_x, challenge_species=aux_challenge_species,
            species_names=species_names,
        )
        artifacts.append(_artifact_from_fit(
            multi_id, multi, fit_seed=seed, model_receipt=multi_receipt,
            model_relative_path=multi_relative, runtime_digest=runtime_digest,
        ))

    q_seed = _fit_seed(target, "auxiliary", SEEDS[0], "q_linear")
    stability_x = np.vstack((prepared["auxiliary"], *(prepared["q_inputs"][endpoint] for endpoint in ENDPOINTS))).astype(np.float32)
    q_model, q_fit_artifact = _q_fit(
        prepared["auxiliary"], bundle.arrays["aux_y"], bundle.arrays["aux_species"],
        q_seed, stability_x=stability_x,
    )
    q_id = "aux/q_linear"
    q_relative = f"models/{_model_filename(q_id, '.json')}"
    q_identity = {
        **_package_identity(bundle, config, policy, runtime_digest, seeds, endpoints),
        "artifact_id": q_id, "input_dim": PREDICTOR_COUNT, "method": "q_linear",
        "fit_seed": q_seed,
    }
    q_challenge = _challenge(prepared["q_inputs"]["fraction100/full"])
    q_receipt = save_q_model(
        q_model, destination / q_relative, identity=q_identity,
        challenge_x=q_challenge, artifact=q_fit_artifact,
    )
    q_payload = load_q_model(
        destination / q_relative, expected=q_receipt, challenge_x=q_challenge
    )
    artifacts.append({
        "artifact_id": q_id, "kind": "auxiliary", "fit_seed": q_seed,
        "exact_epochs": 0, "initial_model_digest": "not_applicable",
        "initial_shared_digest": "not_applicable", "initial_head_digest": "not_applicable",
        "model_digest": q_receipt["state_digest"], "final_shared_digest": "not_applicable",
        "freeze_shared": False, "model_relative_path": q_relative,
        "model_receipt": q_receipt, "runtime_digest": runtime_digest, "finite": True,
        "physical_fits": int(q_fit_artifact["physical_fits"]),
        "n_iter": int(q_fit_artifact["n_iter"]),
        "primary_n_iter": int(q_fit_artifact["primary_n_iter"]),
        "termination_status": q_fit_artifact["termination_status"],
        "stability_accepted": bool(q_fit_artifact["stability_accepted"]),
        "stability_probability_delta": float(q_fit_artifact["stability_probability_delta"]),
        "wall_seconds": float(q_fit_artifact["wall_seconds"]),
    })

    for seed in seeds:
        pooled = pooled_by_seed[seed]
        multi = multi_by_seed[seed]
        pooled_state = _cpu_state(pooled.model)
        shared_state = _shared_state(multi.model)
        for endpoint in endpoints:
            x_plain = prepared["target"][endpoint]
            y = bundle.arrays[f"target_{ENDPOINT_SLUGS[endpoint]}_y"]
            q_view = prepared["q_inputs"][endpoint]
            q_linear = score_q_payload(q_payload, q_view)
            q_deep = _scalar_from_neural(pooled.model, q_view, _prepare_device("cpu"))
            x_by_method: dict[str, tuple[np.ndarray, Callable[[], ResidualMLP], bool]] = {
                "target_only_resmlp": (x_plain, _residual_factory(spec, PREDICTOR_COUNT), False),
                "legacy_pooled_finetune": (x_plain, _residual_factory(spec, PREDICTOR_COUNT, full_state=pooled_state), False),
                "multihead_frozen_trunk": (x_plain, _residual_factory(spec, PREDICTOR_COUNT, shared_state=shared_state), True),
                "multihead_full_finetune": (x_plain, _residual_factory(spec, PREDICTOR_COUNT, shared_state=shared_state), False),
                "target_plus_q_linear": (np.column_stack((x_plain, q_linear)).astype(np.float32), _residual_factory(spec, Q_PREDICTOR_COUNT), False),
                "target_plus_q_deep": (np.column_stack((x_plain, q_deep)).astype(np.float32), _residual_factory(spec, Q_PREDICTOR_COUNT), False),
            }
            fit_seed = _fit_seed(target, endpoint, seed, "target")
            for method in METHODS:
                x, factory, freeze = x_by_method[method]
                epochs = lookup[(target, endpoint, method, seed)]
                fit = exact_fit(factory, spec, fit_seed, x, y, epochs=epochs, freeze_shared=freeze)
                identifier = f"target/{endpoint}/seed{seed}/{method}"
                relative = f"models/{_model_filename(identifier)}"
                identity = {
                    **_package_identity(bundle, config, policy, runtime_digest, seeds, endpoints),
                    "artifact_id": identifier, "input_dim": int(x.shape[1]),
                    "method": method, "seed": seed, "endpoint": endpoint,
                    "fit_seed": fit_seed, "exact_epochs": epochs,
                }
                receipt = save_neural_model(
                    fit.model, destination / relative, identity=identity,
                    challenge_x=_challenge(x),
                )
                artifacts.append(_artifact_from_fit(
                    identifier, fit, fit_seed=fit_seed, model_receipt=receipt,
                    model_relative_path=relative, runtime_digest=runtime_digest,
                    freeze_shared=freeze,
                ))

    by_id = {row["artifact_id"]: row for row in artifacts}
    _require(len(by_id) == len(artifacts), "package artifact identity collision")
    for seed in seeds:
        pooled = by_id[f"aux/pooled/seed{seed}"]
        multi = by_id[f"aux/multihead/seed{seed}"]
        for endpoint in endpoints:
            rows = {method: by_id[f"target/{endpoint}/seed{seed}/{method}"] for method in METHODS}
            _require(rows["legacy_pooled_finetune"]["initial_model_digest"] == pooled["model_digest"], "legacy pooled transfer mismatch")
            _require(rows["multihead_frozen_trunk"]["initial_model_digest"] == rows["multihead_full_finetune"]["initial_model_digest"], "multihead target initial mismatch")
            _require(rows["multihead_frozen_trunk"]["initial_shared_digest"] == rows["multihead_full_finetune"]["initial_shared_digest"] == multi["final_shared_digest"], "multihead shared transfer mismatch")
            _require(rows["multihead_frozen_trunk"]["initial_shared_digest"] == rows["multihead_frozen_trunk"]["final_shared_digest"], "frozen trunk changed")
            _require(rows["target_only_resmlp"]["initial_head_digest"] == rows["multihead_frozen_trunk"]["initial_head_digest"] == rows["multihead_full_finetune"]["initial_head_digest"], "target head initialization mismatch")
            _require(rows["target_plus_q_linear"]["initial_model_digest"] == rows["target_plus_q_deep"]["initial_model_digest"], "q target initialization mismatch")

    expected_artifacts = len(seeds) * 2 + 1 + len(seeds) * len(endpoints) * len(METHODS)
    _require(len(artifacts) == expected_artifacts, "package artifact arithmetic drift")
    physical_fits = sum(int(row["physical_fits"]) for row in artifacts)
    identity = _package_identity(bundle, config, policy, runtime_digest, seeds, endpoints)
    metadata: dict[str, Any] = {
        "schema_version": "goal037-neural-package-v1", "goal_id": "goal037-dsdm-outer-ready",
        "identity": identity, "identity_digest": digest_value(identity), "target": target,
        "bundle_digest": bundle.bundle_digest, "config_digest": config.config_digest,
        "source_fingerprint": config.source_fingerprint, "epoch_policy_digest": policy["policy_digest"],
        "architecture": ARCHITECTURE_ID, "seeds": list(seeds), "endpoints": list(endpoints),
        "target_mask_digests": {endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS},
        "auxiliary_mask_digest": prepared["auxiliary_mask"].digest,
        "artifacts": artifacts,
        "counts": {"logical_artifacts": len(artifacts), "physical_fits": physical_fits, "model_files": len(artifacts)},
        "runtime": runtime, "runtime_digest": runtime_digest,
        "outer_attempted": 0, "outer_opened": 0,
    }
    semantic_inventory = [
        {key: row[key] for key in ("artifact_id", "fit_seed", "exact_epochs", "initial_model_digest", "initial_shared_digest", "initial_head_digest", "model_digest", "final_shared_digest", "freeze_shared", "runtime_digest", "physical_fits")}
        | {"model_identity_digest": row["model_receipt"]["identity_digest"], "model_state_digest": row["model_receipt"]["state_digest"], "challenge_prediction_digest": row["model_receipt"]["challenge_prediction_digest"]}
        for row in artifacts
    ]
    metadata["semantic_inventory_digest"] = digest_value(semantic_inventory)
    metadata["receipt_digest"] = digest_value(metadata)
    _write_json(destination / "metadata.json", metadata)
    return metadata


def _metadata_without_nondeterminism(value: Mapping[str, Any]) -> Mapping[str, Any]:
    def clean(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {key: clean(val) for key, val in item.items() if key not in {"wall_seconds", "model_sha256", "bytes", "receipt_digest"}}
        if isinstance(item, list):
            return [clean(val) for val in item]
        return item
    return clean(value)


def _load_policy(path: str | Path) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("epoch policy missing or invalid") from exc
    validate_epoch_policy(value)
    return value


def _validate_package_files(path: Path, metadata: Mapping[str, Any]) -> None:
    expected = {"metadata.json"} | {str(row["model_relative_path"]) for row in metadata["artifacts"]}
    observed = {str(item.relative_to(path)) for item in path.rglob("*") if item.is_file()}
    _require(observed == expected and not any(item.is_symlink() for item in path.rglob("*")), "neural package file inventory drift")


def validate_package(
    path: str | Path,
    bundle: OuterTrainingBundle,
    config: OuterReadyConfig,
    policy: Mapping[str, Any],
    *,
    seeds: Sequence[int] = SEEDS,
    endpoints: Sequence[str] = ENDPOINTS,
    replay_models: bool = True,
) -> Mapping[str, Any]:
    package = Path(path)
    try:
        metadata = json.loads((package / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("neural package metadata invalid") from exc
    runtime = neural_runtime(config, strict=True)
    runtime_digest = digest_value(runtime)
    expected_identity = _package_identity(bundle, config, policy, runtime_digest, seeds, endpoints)
    _require(metadata.get("schema_version") == "goal037-neural-package-v1" and metadata.get("goal_id") == "goal037-dsdm-outer-ready", "neural package version drift")
    _require(metadata.get("identity") == expected_identity and metadata.get("identity_digest") == digest_value(expected_identity), "neural package identity mismatch")
    _require(metadata.get("outer_attempted") == metadata.get("outer_opened") == 0, "neural package outer access")
    body = dict(metadata)
    claimed = body.pop("receipt_digest", None)
    _require(_is_digest(claimed) and claimed == digest_value(body), "neural package receipt digest mismatch")
    prepared = prepare_outer_bundle(bundle)
    _require(metadata.get("target_mask_digests") == {endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS} and metadata.get("auxiliary_mask_digest") == prepared["auxiliary_mask"].digest, "neural package mask drift")
    artifacts = metadata.get("artifacts")
    expected_ids = {
        *(f"aux/{method}/seed{seed}" for seed in seeds for method in ("pooled", "multihead")),
        "aux/q_linear",
        *(f"target/{endpoint}/seed{seed}/{method}" for seed in seeds for endpoint in endpoints for method in METHODS),
    }
    _require(isinstance(artifacts, list) and {row.get("artifact_id") for row in artifacts} == expected_ids and len(artifacts) == len(expected_ids), "neural package artifact scope drift")
    _validate_package_files(package, metadata)
    lookup = _policy_lookup(policy)
    by_id = {row["artifact_id"]: row for row in artifacts}
    species_names = tuple(name for name in SPECIES if name != bundle.target)
    aux_challenge_x, aux_challenge_species = _challenge_with_species(prepared["auxiliary"], bundle.arrays["aux_species"])
    if replay_models:
        for seed in seeds:
            pooled = by_id[f"aux/pooled/seed{seed}"]
            _require(pooled["exact_epochs"] == lookup[(bundle.target, "auxiliary", "pooled", seed)] and pooled["fit_seed"] == seed, "pooled epoch/seed drift")
            load_neural_model(package / pooled["model_relative_path"], spec=_architecture(), input_dim=77, expected=pooled["model_receipt"], challenge_x=aux_challenge_x)
            multi = by_id[f"aux/multihead/seed{seed}"]
            _require(multi["exact_epochs"] == lookup[(bundle.target, "auxiliary", "multihead", seed)] and multi["fit_seed"] == seed, "multihead epoch/seed drift")
            load_multihead_model(package / multi["model_relative_path"], spec=_architecture(), input_dim=77, species_names=species_names, expected=multi["model_receipt"], challenge_x=aux_challenge_x, challenge_species=aux_challenge_species)
        q = by_id["aux/q_linear"]
        q_payload = load_q_model(package / q["model_relative_path"], expected=q["model_receipt"], challenge_x=_challenge(prepared["q_inputs"]["fraction100/full"]))
        for seed in seeds:
            pooled_row = by_id[f"aux/pooled/seed{seed}"]
            pooled_model = load_neural_model(package / pooled_row["model_relative_path"], spec=_architecture(), input_dim=77, expected=pooled_row["model_receipt"], challenge_x=aux_challenge_x)
            for endpoint in endpoints:
                x_plain = prepared["target"][endpoint]
                q_view = prepared["q_inputs"][endpoint]
                q_linear = score_q_payload(q_payload, q_view)
                q_deep = score_neural_model(pooled_model, q_view)
                x_by_method = {
                    "target_only_resmlp": x_plain, "legacy_pooled_finetune": x_plain,
                    "multihead_frozen_trunk": x_plain, "multihead_full_finetune": x_plain,
                    "target_plus_q_linear": np.column_stack((x_plain, q_linear)).astype(np.float32),
                    "target_plus_q_deep": np.column_stack((x_plain, q_deep)).astype(np.float32),
                }
                fit_seed = _fit_seed(bundle.target, endpoint, seed, "target")
                for method in METHODS:
                    row = by_id[f"target/{endpoint}/seed{seed}/{method}"]
                    _require(row["fit_seed"] == fit_seed and row["exact_epochs"] == lookup[(bundle.target, endpoint, method, seed)], "target epoch/seed drift")
                    load_neural_model(package / row["model_relative_path"], spec=_architecture(), input_dim=x_by_method[method].shape[1], expected=row["model_receipt"], challenge_x=_challenge(x_by_method[method]))
    for seed in seeds:
        pooled = by_id[f"aux/pooled/seed{seed}"]
        multi = by_id[f"aux/multihead/seed{seed}"]
        for endpoint in endpoints:
            rows = {method: by_id[f"target/{endpoint}/seed{seed}/{method}"] for method in METHODS}
            _require(rows["legacy_pooled_finetune"]["initial_model_digest"] == pooled["model_digest"], "validated pooled transfer mismatch")
            _require(rows["multihead_frozen_trunk"]["initial_shared_digest"] == rows["multihead_full_finetune"]["initial_shared_digest"] == multi["final_shared_digest"], "validated multihead transfer mismatch")
            _require(rows["multihead_frozen_trunk"]["initial_shared_digest"] == rows["multihead_frozen_trunk"]["final_shared_digest"], "validated frozen trunk changed")
    _require(metadata.get("runtime") == runtime and metadata.get("runtime_digest") == runtime_digest, "neural package runtime drift")
    _require(metadata.get("counts") == {"logical_artifacts": len(expected_ids), "physical_fits": sum(int(row["physical_fits"]) for row in artifacts), "model_files": len(expected_ids)}, "neural package count drift")
    return metadata


def _leaf_path(leaf_root: Path, identity: Mapping[str, Any]) -> Path:
    return leaf_root / digest_value(dict(identity))


def run_species(
    bundle: OuterTrainingBundle,
    config: OuterReadyConfig,
    policy: Mapping[str, Any],
    leaf_root: str | Path,
) -> Path:
    runtime_digest = digest_value(neural_runtime(config, strict=True))
    identity = _package_identity(bundle, config, policy, runtime_digest, SEEDS, ENDPOINTS)
    destination = _leaf_path(Path(leaf_root), identity)
    if destination.exists():
        validate_package(destination, bundle, config, policy, replay_models=True)
        return destination
    root = Path(leaf_root)
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{bundle.target}-", dir=root))
    try:
        _run_package(bundle, config, policy, temporary)
        validate_package(temporary, bundle, config, policy, replay_models=True)
        os.rename(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def validate_bundle_inventory(root: str | Path, config: OuterReadyConfig) -> list[OuterTrainingBundle]:
    paths = sorted(Path(root).glob("*.npz"))
    _require(len(paths) == 8, "outer-training bundle count drift")
    bundles = [load_outer_bundle(path) for path in paths]
    _require({bundle.target for bundle in bundles} == set(SPECIES), "outer-training bundle species cross-product drift")
    goal035_sha = config.authority_digests["goal035_config"]
    goal029_sha = config.authority_digests["goal029_config"]
    _require(all(bundle.metadata.get("goal035_config_sha256") == goal035_sha and bundle.metadata.get("goal029_config_sha256") == goal029_sha for bundle in bundles), "outer-training bundle authority drift")
    _require(len({bundle.metadata.get("source_binding_digest") for bundle in bundles}) == 1 and len({bundle.metadata.get("outer_transform_digest") for bundle in bundles}) == 1, "outer-training bundle common source/transform drift")
    return sorted(bundles, key=lambda bundle: SPECIES.index(bundle.target))


def _bundle_inventory_digest(bundles: Sequence[OuterTrainingBundle]) -> str:
    return digest_value([{"target": bundle.target, "bundle_digest": bundle.bundle_digest} for bundle in bundles])


def _run_subset_package(
    bundle: OuterTrainingBundle,
    config: OuterReadyConfig,
    policy: Mapping[str, Any],
    root: Path,
    label: str,
    seeds: Sequence[int],
    endpoints: Sequence[str],
) -> Path:
    runtime_digest = digest_value(neural_runtime(config, strict=True))
    identity = _package_identity(bundle, config, policy, runtime_digest, seeds, endpoints)
    destination = root / label / digest_value(identity)
    if destination.exists():
        validate_package(destination, bundle, config, policy, seeds=seeds, endpoints=endpoints, replay_models=True)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".canary-", dir=destination.parent))
    try:
        _run_package(bundle, config, policy, temporary, seeds=seeds, endpoints=endpoints)
        validate_package(temporary, bundle, config, policy, seeds=seeds, endpoints=endpoints, replay_models=True)
        os.rename(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def run_canary(
    config: OuterReadyConfig,
    bundle_root: str | Path,
    policy_path: str | Path,
    output: str | Path,
) -> Mapping[str, Any]:
    bundles = validate_bundle_inventory(bundle_root, config)
    policy = _load_policy(policy_path)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii")
    canary_root = config.private_root / "canary"
    seeds = (SEEDS[0],)
    endpoints = ("fraction100/full",)
    first_path = _run_subset_package(sentinel, config, policy, canary_root, "repeat_a", seeds, endpoints)
    second_path = _run_subset_package(sentinel, config, policy, canary_root, "repeat_b", seeds, endpoints)
    first = validate_package(first_path, sentinel, config, policy, seeds=seeds, endpoints=endpoints, replay_models=True)
    second = validate_package(second_path, sentinel, config, policy, seeds=seeds, endpoints=endpoints, replay_models=True)
    _require(_metadata_without_nondeterminism(first) == _metadata_without_nondeterminism(second), "outer-ready canary semantic repeat mismatch")
    receipt: dict[str, Any] = {
        "schema_version": "goal037-outer-ready-canary-v1", "success": True,
        "config_digest": config.config_digest, "source_fingerprint": config.source_fingerprint,
        "bundle_inventory_digest": _bundle_inventory_digest(bundles),
        "sentinel_target": sentinel.target, "sentinel_bundle_digest": sentinel.bundle_digest,
        "epoch_policy_digest": policy["policy_digest"], "architecture": ARCHITECTURE_ID,
        "seeds": list(seeds), "endpoints": list(endpoints),
        "logical_artifacts": 9, "physical_fits_minimum": 9, "physical_fits_maximum": 10,
        "repeat_semantic_digest": digest_value(_metadata_without_nondeterminism(first)),
        "runtime": first["runtime"], "runtime_digest": first["runtime_digest"],
        "outer_attempted": 0, "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json(output, receipt)
    return receipt


def validate_canary(config: OuterReadyConfig, bundle_root: str | Path, policy_path: str | Path) -> Mapping[str, Any]:
    try:
        receipt = json.loads(config.canary_receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("outer-ready canary receipt missing") from exc
    body = dict(receipt)
    claimed = body.pop("receipt_digest", None)
    _require(_is_digest(claimed) and claimed == digest_value(body), "outer-ready canary receipt digest mismatch")
    bundles = validate_bundle_inventory(bundle_root, config)
    policy = _load_policy(policy_path)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii")
    _require(
        receipt.get("success") is True and receipt.get("config_digest") == config.config_digest
        and receipt.get("source_fingerprint") == config.source_fingerprint
        and receipt.get("bundle_inventory_digest") == _bundle_inventory_digest(bundles)
        and receipt.get("sentinel_bundle_digest") == sentinel.bundle_digest
        and receipt.get("epoch_policy_digest") == policy["policy_digest"]
        and receipt.get("logical_artifacts") == 9
        and receipt.get("outer_attempted") == receipt.get("outer_opened") == 0,
        "outer-ready canary binding drift",
    )
    seeds = (SEEDS[0],)
    endpoints = ("fraction100/full",)
    identity = _package_identity(sentinel, config, policy, digest_value(neural_runtime(config, strict=True)), seeds, endpoints)
    paths = [config.private_root / "canary" / label / digest_value(identity) for label in ("repeat_a", "repeat_b")]
    values = [validate_package(path, sentinel, config, policy, seeds=seeds, endpoints=endpoints, replay_models=True) for path in paths]
    _require(_metadata_without_nondeterminism(values[0]) == _metadata_without_nondeterminism(values[1]) and receipt["repeat_semantic_digest"] == digest_value(_metadata_without_nondeterminism(values[0])), "outer-ready canary private evidence drift")
    return receipt


def _run_species_worker(task: Mapping[str, str]) -> str:
    config = load_config(task["config"])
    bundle = load_outer_bundle(task["bundle"])
    policy = _load_policy(task["policy"])
    return str(run_species(bundle, config, policy, task["leaf_root"]))


def run_all(config: OuterReadyConfig) -> Mapping[str, Any]:
    bundle_root = config.private_root / "bundles"
    leaf_root = config.private_root / "neural" / "leaves"
    validate_canary(config, bundle_root, config.epoch_policy_path)
    bundles = validate_bundle_inventory(bundle_root, config)
    policy = _load_policy(config.epoch_policy_path)
    runtime_digest = digest_value(neural_runtime(config, strict=True))
    tasks: list[dict[str, str]] = []
    complete = 0
    for bundle in bundles:
        identity = _package_identity(bundle, config, policy, runtime_digest, SEEDS, ENDPOINTS)
        path = _leaf_path(leaf_root, identity)
        if path.exists():
            validate_package(path, bundle, config, policy, replay_models=True)
            complete += 1
        else:
            tasks.append({"config": str(config.source_path), "bundle": str(bundle_root / f"{bundle.target}.npz"), "policy": str(config.epoch_policy_path), "leaf_root": str(leaf_root)})
    if tasks:
        with ProcessPoolExecutor(max_workers=3, mp_context=mp.get_context("spawn")) as pool:
            for _ in pool.map(_run_species_worker, tasks):
                complete += 1
    return {"species_packages": complete, "logical_artifacts": LOGICAL_ARTIFACTS, "physical_fits_minimum": LOGICAL_ARTIFACTS, "physical_fits_maximum": LOGICAL_ARTIFACTS + 8, "workers": 3, "outer_attempted": 0, "outer_opened": 0}


def status(config: OuterReadyConfig) -> Mapping[str, Any]:
    bundle_root = config.private_root / "bundles"
    leaf_root = config.private_root / "neural" / "leaves"
    bundles = validate_bundle_inventory(bundle_root, config)
    policy = _load_policy(config.epoch_policy_path)
    runtime_digest = digest_value(neural_runtime(config, strict=True))
    complete = invalid = 0
    for bundle in bundles:
        identity = _package_identity(bundle, config, policy, runtime_digest, SEEDS, ENDPOINTS)
        path = _leaf_path(leaf_root, identity)
        if not path.exists():
            continue
        try:
            validate_package(path, bundle, config, policy, replay_models=False)
            complete += 1
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            invalid += 1
    return {"species_packages_expected": 8, "species_packages_complete": complete, "species_packages_invalid": invalid, "species_packages_missing": 8 - complete - invalid, "outer_attempted": 0, "outer_opened": 0}


def score_species_package(
    package_path: str | Path,
    bundle: OuterTrainingBundle,
    config: OuterReadyConfig,
    policy: Mapping[str, Any],
    endpoint: str,
    x_raw: np.ndarray,
) -> np.ndarray:
    """Score already encoded outer-transform rows; this cannot open the vault."""
    _require(endpoint in ENDPOINTS, "scorer endpoint invalid")
    raw = np.asarray(x_raw, dtype=np.float32)
    _require(raw.ndim == 2 and raw.shape[1] == 77 and len(raw) > 0 and np.isfinite(raw).all(), "scorer raw predictors invalid")
    metadata = validate_package(package_path, bundle, config, policy, replay_models=True)
    package = Path(package_path)
    artifacts = {row["artifact_id"]: row for row in metadata["artifacts"]}
    prepared = prepare_outer_bundle(bundle)
    x_plain = apply_support_mask(raw, prepared["target_masks"][endpoint])[0]
    q_view = apply_support_mask(raw, prepared["auxiliary_mask"])[0]
    q_row = artifacts["aux/q_linear"]
    q_payload = load_q_model(package / q_row["model_relative_path"], expected=q_row["model_receipt"], challenge_x=_challenge(prepared["q_inputs"]["fraction100/full"]))
    q_linear = score_q_payload(q_payload, q_view)
    result = np.empty((len(SEEDS), len(METHODS), len(raw)), dtype=np.float32)
    aux_challenge_x, _ = _challenge_with_species(prepared["auxiliary"], bundle.arrays["aux_species"])
    for seed_index, seed in enumerate(SEEDS):
        pooled_row = artifacts[f"aux/pooled/seed{seed}"]
        pooled = load_neural_model(package / pooled_row["model_relative_path"], spec=_architecture(), input_dim=77, expected=pooled_row["model_receipt"], challenge_x=aux_challenge_x)
        q_deep = score_neural_model(pooled, q_view)
        x_by_method = {
            "target_only_resmlp": x_plain, "legacy_pooled_finetune": x_plain,
            "multihead_frozen_trunk": x_plain, "multihead_full_finetune": x_plain,
            "target_plus_q_linear": np.column_stack((x_plain, q_linear)).astype(np.float32),
            "target_plus_q_deep": np.column_stack((x_plain, q_deep)).astype(np.float32),
        }
        for method_index, method in enumerate(METHODS):
            row = artifacts[f"target/{endpoint}/seed{seed}/{method}"]
            training_x = prepared["target"][endpoint]
            if method == "target_plus_q_linear":
                train_q = score_q_payload(q_payload, prepared["q_inputs"][endpoint])
                challenge_x = _challenge(np.column_stack((training_x, train_q)).astype(np.float32))
            elif method == "target_plus_q_deep":
                train_q = score_neural_model(pooled, prepared["q_inputs"][endpoint])
                challenge_x = _challenge(np.column_stack((training_x, train_q)).astype(np.float32))
            else:
                challenge_x = _challenge(training_x)
            model = load_neural_model(package / row["model_relative_path"], spec=_architecture(), input_dim=x_by_method[method].shape[1], expected=row["model_receipt"], challenge_x=challenge_x)
            result[seed_index, method_index] = score_neural_model(model, x_by_method[method])
    _require(np.isfinite(result).all() and np.all((result >= 0) & (result <= 1)), "scorer output invalid")
    return result


def _load_conventional_receipt(config: OuterReadyConfig) -> Mapping[str, Any]:
    try:
        value = json.loads(config.conventional_import_receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("conventional import receipt missing") from exc
    body = dict(value)
    claimed = body.pop("receipt_digest", None)
    _require(_is_digest(claimed) and claimed == digest_value(body), "conventional import receipt digest mismatch")
    _require(value.get("success") is True and value.get("config_digest") == config.config_digest and value.get("source_fingerprint") == config.source_fingerprint and value.get("selected_refits") == 952 and value.get("outer_attempted") == value.get("outer_opened") == 0, "conventional import receipt binding drift")
    return value


def aggregate(config: OuterReadyConfig) -> Mapping[str, Any]:
    bundle_root = config.private_root / "bundles"
    leaf_root = config.private_root / "neural" / "leaves"
    bundles = validate_bundle_inventory(bundle_root, config)
    policy = _load_policy(config.epoch_policy_path)
    canary = validate_canary(config, bundle_root, config.epoch_policy_path)
    conventional = _load_conventional_receipt(config)
    runtime = neural_runtime(config, strict=True)
    runtime_digest = digest_value(runtime)
    leaf_inventory: list[str] = []
    content_inventory: list[str] = []
    physical_fits = 0
    total_bytes = 0
    for bundle in bundles:
        identity = _package_identity(bundle, config, policy, runtime_digest, SEEDS, ENDPOINTS)
        path = _leaf_path(leaf_root, identity)
        metadata = validate_package(path, bundle, config, policy, replay_models=True)
        leaf_inventory.append(path.name)
        content_inventory.append(metadata["receipt_digest"])
        physical_fits += int(metadata["counts"]["physical_fits"])
        total_bytes += sum(int(row["model_receipt"]["bytes"]) for row in metadata["artifacts"])
    _require(LOGICAL_ARTIFACTS <= physical_fits <= LOGICAL_ARTIFACTS + 8, "outer-ready physical-fit arithmetic drift")
    epoch_summary = validate_epoch_policy(policy)
    transaction = {
        "bundle_inventory_digest": _bundle_inventory_digest(bundles),
        "epoch_policy_digest": policy["policy_digest"],
        "neural_leaf_inventory_digest": digest_value(sorted(leaf_inventory)),
        "neural_content_inventory_digest": digest_value(sorted(content_inventory)),
        "conventional_model_inventory_digest": conventional["model_inventory_digest"],
        "conventional_task_inventory_digest": conventional["task_inventory_digest"],
        "threshold_table_sha256": config.authority_digests["goal036_stratum_metrics"],
    }
    receipt: dict[str, Any] = {
        "schema_version": "goal037-outer-ready-aggregate-v1", "success": True,
        "decision": "outer_ready_not_opened", "config_digest": config.config_digest,
        "authority_digests": dict(config.authority_digests), "source_digests": dict(config.source_digests),
        "source_fingerprint": config.source_fingerprint, "architecture": ARCHITECTURE_ID,
        "methods": {"neural": list(METHODS), "conventional": list(config.raw["scope"]["conventional_families"]), "total": 11},
        "counts": {"species": 8, "endpoints": 7, "neural_packages": 8, "neural_logical_artifacts": LOGICAL_ARTIFACTS, "neural_physical_fits": physical_fits, "conventional_selected_refits": 952, "scorer_model_artifacts": LOGICAL_ARTIFACTS + 952},
        "epoch_policy": {**epoch_summary, "sum": sum(row["full_training_epochs"] for row in policy["records"]), "digest": policy["policy_digest"]},
        "bundle_inventory_digest": transaction["bundle_inventory_digest"],
        "neural_leaf_inventory_digest": transaction["neural_leaf_inventory_digest"],
        "neural_content_inventory_digest": transaction["neural_content_inventory_digest"],
        "neural_model_bytes": total_bytes,
        "conventional_import_receipt_digest": conventional["receipt_digest"],
        "canary_receipt_digest": canary["receipt_digest"],
        "transaction_digest": digest_value(transaction),
        "runtime": {"neural": runtime, "conventional_scorer_digest": conventional["runtime_digest"]},
        "privacy": {"aggregate_only": True, "labels_tracked": False, "predictions_tracked": False, "row_identifiers": False, "coordinates": False},
        "outer_attempted": 0, "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    return receipt


def finalize(config: OuterReadyConfig) -> Mapping[str, Any]:
    receipt = aggregate(config)
    output = (config.root / config.raw["evidence"]["aggregate_receipt"]).resolve()
    _write_json(output, receipt)
    return receipt


def validate(config: OuterReadyConfig) -> Mapping[str, Any]:
    expected = aggregate(config)
    path = (config.root / config.raw["evidence"]["aggregate_receipt"]).resolve()
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OuterReadyError("outer-ready aggregate receipt invalid") from exc
    _require(actual == expected, "outer-ready aggregate receipt mismatch")
    return actual


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.outer_ready")
    parser.add_argument("--config", default="config/dsdm_outer_ready.json")
    parser.add_argument("command", choices=("plan", "epochs", "export", "validate-bundles", "canary", "run", "status", "finalize", "validate"))
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.command == "plan":
        value: Mapping[str, Any] = {
            "schema_version": "goal037-outer-ready-plan-v1",
            "config_digest": config.config_digest,
            "source_fingerprint": config.source_fingerprint,
            "species_packages": 8,
            "epoch_policy_records": EPOCH_POLICY_RECORDS,
            "neural_logical_artifacts": LOGICAL_ARTIFACTS,
            "neural_physical_fits_minimum": LOGICAL_ARTIFACTS,
            "neural_physical_fits_maximum": LOGICAL_ARTIFACTS + 8,
            "conventional_selected_refits": 952,
            "scorer_model_artifacts": LOGICAL_ARTIFACTS + 952,
            "workers": 3,
            "outer_attempted": 0,
            "outer_opened": 0,
        }
    elif args.command == "epochs":
        value = extract_epoch_policy(config.goal035_private_root, config.root / config.raw["authorities"]["goal035_aggregate"]["path"], config.epoch_policy_path)
    elif args.command == "export":
        paths = export_outer_training_bundles(config.root, config.root / config.raw["authorities"]["goal035_config"]["path"], config.private_root / "bundles")
        value = {"bundles": len(paths), "outer_attempted": 0, "outer_opened": 0}
    elif args.command == "validate-bundles":
        bundles = validate_bundle_inventory(config.private_root / "bundles", config)
        value = {"bundles": len(bundles), "bundle_inventory_digest": _bundle_inventory_digest(bundles), "outer_attempted": 0, "outer_opened": 0}
    elif args.command == "canary":
        value = run_canary(config, config.private_root / "bundles", config.epoch_policy_path, config.canary_receipt)
    elif args.command == "run":
        value = run_all(config)
    elif args.command == "status":
        value = status(config)
    elif args.command == "finalize":
        value = finalize(config)
    else:
        value = validate(config)
    print(canonical(value).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ENDPOINT_SLUGS", "ExactFit", "OuterReadyConfig", "OuterReadyError",
    "OuterTrainingBundle", "aggregate", "digest_value", "exact_fit",
    "export_outer_training_bundles", "extract_epoch_policy", "finalize",
    "load_config", "load_neural_model", "load_outer_bundle", "lower_median",
    "main", "neural_runtime", "prepare_outer_bundle", "run_all", "run_canary",
    "run_species", "save_neural_model", "save_outer_bundle",
    "score_neural_model", "score_species_package", "status", "validate",
    "validate_bundle_inventory", "validate_canary", "validate_epoch_policy",
    "validate_package",
]
