"""Goal038 Stage1 capacity diagnostic.

This module is deliberately a thin orchestration layer over the frozen Goal035
bundle/preparation and neural lifecycle helpers.  It owns only the four
exploratory architectures, their private identity-addressed leaves, and the
aggregate metric/eligibility gate.  No outer-vault adapter is present.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.metrics import matthews_corrcoef, roc_auc_score

from .contracts import FOLDS, SPECIES, ArchitectureSpec


class CapacityDiagnosticError(ValueError):
    """Raised when the Goal038 identity, leaf, or aggregate contract fails."""


VARIANTS: dict[str, ArchitectureSpec] = {
    "control": ArchitectureSpec("resmlp13", 3, 128, 64, "constant", 0.0, 0.001),
    "wide512": ArchitectureSpec("wide512", 3, 512, 128, "constant", 0.0, 0.001),
    "deep6": ArchitectureSpec("deep6", 6, 128, 64, "constant", 0.0, 0.001),
    "deepwide6": ArchitectureSpec("deepwide6", 6, 512, 128, "constant", 0.0, 0.001),
    "deepwide6_drop10": ArchitectureSpec("deepwide6_drop10", 6, 512, 128, "constant", 0.1, 0.001),
}
NEW_VARIANTS = ("wide512", "deep6", "deepwide6", "deepwide6_drop10")
SEEDS = (31031, 31032, 31033)
METHODS = ("target_only_resmlp", "multihead_full_finetune")
ENDPOINT = "fraction100/full"


@dataclass(frozen=True)
class CapacityConfig:
    source_path: Path
    root: Path
    raw: Mapping[str, Any]
    config_digest: str

    @property
    def private_root(self) -> Path:
        return self.root / self.raw["evidence"]["private_root"]

    @property
    def tracked_root(self) -> Path:
        return self.root / self.raw["evidence"]["tracked_root"]

    @property
    def canary_receipt(self) -> Path:
        return self.root / self.raw["evidence"]["canary_receipt"]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def file_digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CapacityDiagnosticError(message)


def parameter_count(spec: ArchitectureSpec, *, input_dim: int = 77) -> int:
    """Exact trainable count for the single-head residual network."""
    width, bottleneck = int(spec.width), int(spec.bottleneck)
    block = 2 * width * bottleneck + bottleneck + 3 * width
    return (input_dim + 1) * width + spec.blocks * block + 3 * width + 1


def build_plan(config: CapacityConfig | None = None) -> dict[str, Any]:
    return {
        "new_atomic_cells": len(NEW_VARIANTS) * len(SPECIES) * len(FOLDS) * len(SEEDS),
        "logical_lifecycles": len(NEW_VARIANTS) * len(SPECIES) * len(FOLDS) * len(SEEDS) * 3,
        "physical_fits": len(NEW_VARIANTS) * len(SPECIES) * len(FOLDS) * len(SEEDS) * 6,
        "control_reused": True, "species": len(SPECIES), "folds": len(FOLDS),
        "seeds": len(SEEDS), "variants": len(NEW_VARIANTS),
    }


def load_config(path: str | Path, *, root: str | Path | None = None) -> CapacityConfig:
    source = Path(path).resolve()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapacityDiagnosticError("invalid Goal038 config") from exc
    _require(set(raw) == {"schema_version", "goal_id", "authorities", "execution_sources", "scope", "architectures", "training", "execution", "evaluation", "privacy", "evidence", "runtime", "stage2"}, "Goal038 config keys drift")
    _require(raw["schema_version"] == "1.0" and raw["goal_id"] == "goal038-dsdm-capacity-diagnostic", "Goal038 identity drift")
    project_root = Path(root).resolve() if root is not None else source.parents[1]
    for group in ("authorities", "execution_sources"):
        _require(isinstance(raw[group], dict), f"{group} missing")
        for name, binding in raw[group].items():
            _require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}, f"{group} binding drift: {name}")
            target = project_root / binding["path"]
            _require(not Path(binding["path"]).is_absolute() and ".." not in Path(binding["path"]).parts and target.is_file(), f"missing binding: {name}")
            _require(file_digest(target) == binding["sha256"], f"binding digest mismatch: {name}")
    _require(set(raw["authorities"]) == {"goal035_config", "goal035_aggregate", "goal035_decision", "goal036_summary", "goal036_decision", "goal037_config", "goal037_decision", "goal037_receipt"}, "Goal038 authority key set drift")
    _require(set(raw["execution_sources"]) == {"capacity_diagnostic", "contracts", "models", "final_inner_data", "final_inner_runner", "inner_evaluation", "real_six_path", "uv_lock"}, "Goal038 source key set drift")
    scope = raw["scope"]
    _require(scope == {"species": list(SPECIES), "folds": list(FOLDS), "fractions": [ENDPOINT], "seeds": list(SEEDS), "methods": list(METHODS)}, "Goal038 scope drift")
    expected_arch = {key: {"blocks": spec.blocks, "width": spec.width, "bottleneck": spec.bottleneck, "shape": spec.shape, "dropout": spec.dropout, "weight_decay": spec.weight_decay, "parameter_count": parameter_count(spec)} for key, spec in VARIANTS.items()}
    _require(raw["architectures"] == expected_arch, "Goal038 architecture registry drift")
    _require(raw["training"] == {"dtype": "float32", "device": "cpu", "threads": 1, "blas_threads": 1, "optimizer": "AdamW", "learning_rate": 0.001, "batch_size": 128, "max_epochs": 300, "patience": 30}, "Goal038 training drift")
    _require(raw["execution"] == {"new_atomic_cells": 480, "logical_lifecycles": 1440, "physical_fits": 2880, "workers": 3, "outer_attempted": 0, "outer_opened": 0}, "Goal038 execution arithmetic drift")
    _require(raw["evaluation"]["primary_metrics"] == ["auc", "tss"] and raw["evaluation"]["supplementary_metrics"] == ["mcc"], "Goal038 metrics drift")
    _require(raw["privacy"] == {"labels_private": True, "predictions_private": True, "leaves_private": True, "aggregate_only": True, "outer_attempted": 0, "outer_opened": 0}, "Goal038 privacy drift")
    _require(raw["runtime"] == {"system": "Darwin", "machine": "arm64", "python_major_minor": "3.12", "numpy": "2.2.6", "scipy": "1.16.3", "scikit_learn": "1.9.0", "threadpoolctl": "3.6.0", "torch": "2.7.1", "device": "cpu", "route": "mac_cpu", "threads": 1, "blas_threads": 1}, "Goal038 runtime drift")
    _require(raw["stage2"] == {"status": "frozen_conditional", "candidate_limit": 1, "control_reused": True, "scope": {"fractions": ["fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02", "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02", "fraction100/full"], "seeds": [31031, 31032, 31033, 31034, 31035], "species": 8, "folds": 5, "methods": ["target_only_resmlp", "legacy_pooled_finetune", "multihead_frozen_trunk", "multihead_full_finetune", "target_plus_q_linear", "target_plus_q_deep"]}, "execution": {"atomic_cases": 40, "logical_artifacts": 8840, "physical_fits_minimum": 17640, "physical_fits_maximum": 17680}, "confirmation": {"endpoints": ["fraction25/ladder01", "fraction25/ladder02", "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02"], "seeds": [31034, 31035], "median_species_d_auc_positive_endpoints_min": 4, "species_five_endpoint_mean_positive_min": 5, "fresh_seed_species_balanced_d_auc_positive_min": 2, "aggregate_d_tss_min": 0}, "nested_endpoints_not_independent": True, "secondary_paths": ["legacy_pooled_finetune", "multihead_frozen_trunk", "target_plus_q_linear", "target_plus_q_deep"]}, "Goal038 Stage2 freeze drift")
    return CapacityConfig(source, project_root, raw, file_digest(source))


def average_common_seed_predictions(predictions: np.ndarray) -> np.ndarray:
    values = np.asarray(predictions, dtype=np.float32)
    _require(values.ndim == 2 and values.shape[0] == len(SEEDS), "seed prediction shape drift")
    _require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "prediction values invalid")
    return np.mean(values, axis=0, dtype=np.float64).astype(np.float32)


def control_sentinel_slice(predictions: np.ndarray) -> np.ndarray:
    """Return the explicit seed-31031, two-method, held-row control slice."""
    values = np.asarray(predictions, dtype=np.float32)
    _require(values.ndim == 3 and values.shape[0] == len(SEEDS) and values.shape[1] == len(METHODS), "control sentinel shape drift")
    return values[0, :, :].copy()


def binary_metrics(y: Sequence[int], score: Sequence[float], threshold: float) -> dict[str, float | int | None]:
    labels = np.asarray(y, dtype=np.int8); values = np.asarray(score, dtype=np.float64)
    _require(labels.ndim == values.ndim == 1 and len(labels) == len(values) > 0 and np.isin(labels, (0, 1)).all(), "metric shape/class drift")
    _require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "metric values invalid")
    pred = values >= float(threshold); pos = labels == 1; neg = ~pos
    tp, fn, tn, fp = int(np.sum(pred & pos)), int(np.sum(~pred & pos)), int(np.sum(~pred & neg)), int(np.sum(pred & neg))
    auc = float(roc_auc_score(labels, values)) if pos.any() and neg.any() else None
    tss = float(tp / pos.sum() + tn / neg.sum() - 1.0) if pos.any() and neg.any() else None
    mcc = float(matthews_corrcoef(labels, pred)) if pos.any() and neg.any() else None
    return {"auc": auc, "tss": tss, "mcc": mcc, "n": len(labels), "tp": tp, "fn": fn, "tn": tn, "fp": fp}


def choose_tss_threshold(y: Sequence[int], score: Sequence[float]) -> float:
    """Goal036 max-TSS threshold with representable midpoints and lower median."""
    labels = np.asarray(y, dtype=np.int8); values = np.asarray(score, dtype=np.float64)
    _require(len(labels) == len(values) and set(np.unique(labels).tolist()) == {0, 1}, "threshold class drift")
    unique = np.unique(values); candidates = [float(np.nextafter(unique[0], -np.inf)), float(np.nextafter(unique[-1], np.inf))]
    candidates.extend(float(low + (high - low) / 2.0) for low, high in zip(unique[:-1], unique[1:]))
    tss = [binary_metrics(labels, values, cut)["tss"] for cut in candidates]; maximum = max(float(value) for value in tss)
    winners = sorted(float(cut) for cut, value in zip(candidates, tss) if float(value) == maximum)
    return winners[(len(winners) - 1) // 2]


def _prediction_field(method: str) -> str:
    """Map canonical method IDs to compact cell-record prediction fields."""
    return "multihead" if method == "multihead_full_finetune" else "target_only"


def eligibility_gate(row: Mapping[str, Any]) -> bool:
    return (float(row["median_species_d_auc"]) > 0 and float(row["median_species_l_auc"]) > 0 and int(row["species_d_auc_positive"]) >= 5 and int(row["seed_d_auc_positive"]) >= 2 and float(row["median_species_d_tss"]) >= 0)


def seed_gate_count(seed_species_d_auc: Mapping[int, Sequence[float]]) -> int:
    """Count seeds whose species-balanced D_AUC is positive."""
    return sum(int(float(np.mean(values)) > 0) for values in seed_species_d_auc.values())


def rank_eligible(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    eligible = [dict(row) for row in rows if row.get("eligible", True)]
    return sorted(eligible, key=lambda row: (-float(row["median_species_d_auc"]), -float(row.get("mean_species_d_auc", row["median_species_d_auc"])), -float(row["median_species_d_tss"]), int(row["parameter_count"]), str(row["variant"])))


def aggregate_species_lifts(records: Sequence[Mapping[str, Any]], *, threshold: float | Mapping[str, float]) -> list[dict[str, Any]]:
    """Aggregate target/multihead records using the frozen seed/fold order."""
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        key = (str(record["variant"]), str(record["species"]), str(record["fold"]))
        grouped.setdefault(key, []).append(record)
    rows: list[dict[str, Any]] = []
    for (variant, species, fold), values in sorted(grouped.items()):
        ys = np.asarray(values[0]["y"], dtype=np.int8)
        target = average_common_seed_predictions(np.asarray([v["target_only"] for v in values]))
        multi = average_common_seed_predictions(np.asarray([v["multihead"] for v in values]))
        target_cut = threshold[(variant, species, "target_only")] if isinstance(threshold, Mapping) and (variant, species, "target_only") in threshold else (threshold[species] if isinstance(threshold, Mapping) else threshold)
        multi_cut = threshold[(variant, species, "multihead_full_finetune")] if isinstance(threshold, Mapping) and (variant, species, "multihead_full_finetune") in threshold else (threshold[species] if isinstance(threshold, Mapping) else threshold)
        tm, mm = binary_metrics(ys, target, float(target_cut)), binary_metrics(ys, multi, float(multi_cut))
        rows.append({"variant": variant, "species": species, "fold": fold, "target_auc": tm["auc"], "multi_auc": mm["auc"], "target_tss": tm["tss"], "multi_tss": mm["tss"], "target_mcc": tm["mcc"], "multi_mcc": mm["mcc"], "lift_auc": float(mm["auc"] - tm["auc"]), "lift_tss": float(mm["tss"] - tm["tss"]), "lift_mcc": float(mm["mcc"] - tm["mcc"])})
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _goal035_context(config: CapacityConfig):
    """Load and validate the immutable Goal035 bundle/leaf boundary."""
    from .final_inner_data import load_config as load_goal035_config, prepare_case, validate_bundle_inventory
    from .final_inner_runner import validate_canary as validate_goal035_canary, validate_leaf
    goal_config = load_goal035_config(config.root / config.raw["authorities"]["goal035_config"]["path"])
    validate_goal035_canary(goal_config)
    aggregate_path = config.root / config.raw["evidence"]["goal035_tracked_root"] / "aggregate.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    _require(aggregate.get("success") is True and aggregate.get("corrected_winner") == "resmlp13" and aggregate.get("config_digest") == goal_config.config_digest and aggregate.get("outer_attempted") == aggregate.get("outer_opened") == 0, "Goal035 control aggregate gate failed")
    bundles = validate_bundle_inventory(config.root / config.raw["evidence"]["goal035_private_root"], config=goal_config)
    return goal_config, bundles, prepare_case, validate_leaf


def _live_runtime(config: CapacityConfig) -> dict[str, Any]:
    """Attest the actual frozen Goal035 numerical runtime and bind it exactly."""
    from .final_inner_data import load_config as load_goal035_config, runtime_attestation
    goal_config = load_goal035_config(config.root / config.raw["authorities"]["goal035_config"]["path"])
    actual = runtime_attestation(goal_config, strict=True)
    normalized = {"system": actual["system"], "machine": actual["machine"], "python_major_minor": actual["python_major_minor"], "numpy": actual["numpy"], "scipy": actual["scipy"], "scikit_learn": actual["scikit_learn"], "threadpoolctl": actual["threadpoolctl"], "torch": actual["torch"], "device": actual["device"], "route": actual["route"], "threads": actual["torch_threads"], "blas_threads": actual["blas_threads"]}
    _require(normalized == dict(config.raw["runtime"]), "Goal038 live runtime mismatch")
    return normalized


def _goal035_identity(goal_config: Any, bundle: Any, prepared: Mapping[str, Any]) -> dict[str, Any]:
    from .final_inner_data import ENDPOINTS as G035_ENDPOINTS, digest_value as g035_digest, runtime_attestation
    runtime = runtime_attestation(goal_config, strict=True)
    return {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": goal_config.config_digest, "runtime_digest": g035_digest(runtime), "architecture": "resmlp13", "mask_digest": g035_digest({endpoint: prepared["target_masks"][endpoint].digest for endpoint in G035_ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}


def validate_control_predictions(config: CapacityConfig) -> dict[tuple[str, str], np.ndarray]:
    """Validate every Goal035 control leaf before importing its predictions."""
    from .final_inner_data import ENDPOINTS as G035_ENDPOINTS, METHODS as G035_METHODS, leaf_identity, runtime_attestation
    goal_config, bundles, prepare_case, validate_leaf = _goal035_context(config)
    leaf_root = config.root / config.raw["evidence"]["goal035_private_root"] / "leaves"
    control: dict[tuple[str, str], np.ndarray] = {}
    for bundle in bundles:
        identity = _goal035_identity(goal_config, bundle, prepare_case(bundle))
        path = leaf_root / leaf_identity(identity)
        metadata = validate_leaf(path, identity)
        predictions = np.load(path / "predictions.npy", allow_pickle=False)
        _require(predictions.ndim == 4 and predictions.shape[0] == 5 and predictions.shape[1] == 7 and predictions.shape[2] == 6 and np.isfinite(predictions).all() and np.all((predictions >= 0) & (predictions <= 1)), "Goal035 control prediction inventory drift")
        endpoint_index = G035_ENDPOINTS.index(ENDPOINT)
        method_indices = [G035_METHODS.index(method) for method in METHODS]
        control[(bundle.target, bundle.held_fold)] = predictions[: len(SEEDS), endpoint_index, method_indices, :].copy()
        _require(metadata["architecture"] == "resmlp13" and metadata["outer_attempted"] == metadata["outer_opened"] == 0, "Goal035 control leaf identity drift")
    _require(len(control) == 40, "Goal035 control coverage drift")
    return control


def replay_control_sentinel(config: CapacityConfig) -> dict[str, Any]:
    """Replay the exact Goal035 sentinel lifecycle and compare both control vectors."""
    from .final_inner_runner import _case_lifecycle
    from .final_inner_data import ENDPOINTS as G035_ENDPOINTS, METHODS as G035_METHODS
    goal_config, bundles, _, _ = _goal035_context(config)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00")
    accepted = validate_control_predictions(config)[(sentinel.target, sentinel.held_fold)]
    replay, metadata = _case_lifecycle(sentinel, goal_config, device="cpu")
    expected = replay[0, G035_ENDPOINTS.index(ENDPOINT), [G035_METHODS.index(method) for method in METHODS], :]
    accepted = control_sentinel_slice(accepted)
    _require(np.array_equal(expected, accepted), "Goal035 control sentinel replay mismatch")
    return {"prediction_digest": hashlib.sha256(np.ascontiguousarray(expected).tobytes()).hexdigest(), "artifact_digest": digest_value([(row["artifact_id"], row.get("fit_seed"), row.get("model_digest"), row.get("prediction_digest")) for row in metadata["artifacts"]]), "counts": metadata["counts"], "seed": SEEDS[0], "shape": list(expected.shape)}


def _new_identity(config: CapacityConfig, bundle: Any, variant: str, seed: int, *, runtime: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source_fingerprint = digest_value(sorted((name, binding["path"], binding["sha256"]) for name, binding in config.raw["execution_sources"].items()))
    fit_seed = int.from_bytes(hashlib.sha256(f"goal038|{variant}|{bundle.target}|{bundle.held_fold}|{seed}".encode()).digest()[:4], "big")
    runtime_value = dict(runtime or config.raw["runtime"])
    return {"schema_version": "goal038-capacity-cell-v1", "goal_id": config.raw["goal_id"], "variant": variant, "target": bundle.target, "held_fold": bundle.held_fold, "endpoint": ENDPOINT, "seed": int(seed), "fit_seed": fit_seed, "held_row_count": int(len(bundle.arrays["x_held"])), "config_digest": config.config_digest, "bundle_digest": bundle.source_digest, "source_fingerprint": source_fingerprint, "runtime_digest": digest_value(runtime_value), "architecture": VARIANTS[variant].id, "outer_attempted": 0, "outer_opened": 0}


def _cell_path(config: CapacityConfig, identity: Mapping[str, Any]) -> Path:
    return config.private_root / "cells" / digest_value(identity)


def _target_arrays(prepared: Mapping[str, Any], raw: Mapping[str, np.ndarray], endpoint: str = ENDPOINT) -> tuple[dict[str, np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray]]:
    slug = endpoint.replace("/", "_"); prefix = f"target_{slug}_"
    target = {role: prepared["target"][prefix + "x_" + role] for role in ("discovery", "stopping", "replay", "held")}
    y = tuple(raw[f"{prefix}y_{role}"] for role in ("discovery", "stopping", "replay"))
    return target, y  # type: ignore[return-value]


def _run_cell(config_path: str, bundle: Any, variant: str, seed: int, leaf_path: Path) -> str:
    """Fit one auxiliary lifecycle and two transferred target lifecycles."""
    import torch
    from .final_inner_data import prepare_case
    from .models import MultiHeadResidual, ResidualMLP
    from .real_six_path import _cpu_state, _neural_lifecycle, _prepare_device, _residual_factory, _shared_state
    config = load_config(config_path); runtime = _live_runtime(config); spec = VARIANTS[variant]; prepared = prepare_case(bundle); device = _prepare_device("cpu")
    names = tuple(name for name in SPECIES if name != bundle.target); a = prepared["auxiliary"]; raw = bundle.arrays
    aux = _neural_lifecycle(lambda: MultiHeadResidual(spec, 77, names), spec, seed, device, a["discovery"], raw["aux_y_discovery"], a["stopping"], raw["aux_y_stopping"], a["replay"], raw["aux_y_replay"], a["replay"], max_epochs=300, patience=30, species_names=names, species_discovery=raw["aux_species_discovery"], species_stopping=raw["aux_species_stopping"], species_replay=raw["aux_species_replay"], species_prediction=raw["aux_species_replay"])
    target, y = _target_arrays(prepared, raw)
    fit_seed = int.from_bytes(hashlib.sha256(f"goal038|{variant}|{bundle.target}|{bundle.held_fold}|{seed}".encode()).digest()[:4], "big")
    predictions = []
    lifecycle_rows = [{"role": "auxiliary_multihead", "fit_seed": int(seed), "selected_epoch": aux.selected_epoch, "discovery_executed_epochs": aux.discovery_executed_epochs, "replay_epochs": aux.selected_epoch, "stopping_status": aux.stopping_status, "initial_model_digest": aux.initial_model_digest, "replay_initial_model_digest": aux.replay_initial_model_digest, "initial_shared_digest": aux.initial_shared_digest, "final_shared_digest": aux.final_shared_digest, "initial_head_digest": aux.initial_head_digest, "model_digest": aux.model_digest, "wall_seconds": aux.wall_seconds, "prediction_digest": aux.prediction_digest}]
    target_lifecycles = []
    for method, factory in ((METHODS[0], _residual_factory(spec, 77)), (METHODS[1], _residual_factory(spec, 77, shared_state=_shared_state(aux.model)))):
        lifecycle = _neural_lifecycle(factory, spec, fit_seed, device, target["discovery"], y[0], target["stopping"], y[1], target["replay"], y[2], target["held"], max_epochs=300, patience=30)
        target_lifecycles.append((method, lifecycle))
        lifecycle.model.eval()
        with torch.no_grad():
            values = torch.sigmoid(lifecycle.model(torch.from_numpy(np.ascontiguousarray(target["held"])).to(device))).cpu().numpy().astype(np.float32)
        _require(np.isfinite(values).all(), "non-finite cell prediction")
        predictions.append(values)
    _require(target_lifecycles[0][1].initial_head_digest == target_lifecycles[1][1].initial_head_digest, "common target head initialization drift")
    _require(target_lifecycles[1][1].initial_shared_digest == aux.final_shared_digest, "multihead auxiliary transfer drift")
    for method, lifecycle in target_lifecycles:
        lifecycle_rows.append({"role": method, "fit_seed": fit_seed, "selected_epoch": lifecycle.selected_epoch, "discovery_executed_epochs": lifecycle.discovery_executed_epochs, "replay_epochs": lifecycle.selected_epoch, "stopping_status": lifecycle.stopping_status, "initial_model_digest": lifecycle.initial_model_digest, "replay_initial_model_digest": lifecycle.replay_initial_model_digest, "initial_shared_digest": lifecycle.initial_shared_digest, "final_shared_digest": lifecycle.final_shared_digest, "initial_head_digest": lifecycle.initial_head_digest, "model_digest": lifecycle.model_digest, "wall_seconds": lifecycle.wall_seconds, "prediction_digest": lifecycle.prediction_digest})
    identity = _new_identity(config, bundle, variant, seed, runtime=runtime); leaf_path.parent.mkdir(parents=True, exist_ok=True)
    values = np.stack(predictions); metadata = {"identity": identity, "shape": [2, len(predictions[0])], "dtype": "float32", "prediction_digest": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest(), "lifecycle_diagnostics": lifecycle_rows, "transfer_checks": {"auxiliary_reset": aux.initial_model_digest == aux.replay_initial_model_digest, "target_reset": all(row["initial_model_digest"] == row["replay_initial_model_digest"] for row in lifecycle_rows[1:]), "common_target_head": target_lifecycles[0][1].initial_head_digest == target_lifecycles[1][1].initial_head_digest, "multihead_shared_transfer": target_lifecycles[1][1].initial_shared_digest == aux.final_shared_digest}, "counts": {"logical_lifecycles": 3, "physical_fits": 6}, "runtime": runtime, "outer_attempted": 0, "outer_opened": 0}
    temporary = Path(tempfile.mkdtemp(prefix=f".{leaf_path.name}.", dir=str(leaf_path.parent)))
    try:
        np.save(temporary / "predictions.npy", values, allow_pickle=False); _write_json(temporary / "metadata.json", metadata)
        if leaf_path.exists():
            _validate_new_leaf(leaf_path, identity)
            for child in temporary.iterdir(): child.unlink()
            temporary.rmdir()
            return digest_value({"identity": identity, "prediction_digest": metadata["prediction_digest"]})
        os.replace(temporary, leaf_path)
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir(): child.unlink()
            temporary.rmdir()
        raise
    return digest_value({"identity": identity, "prediction_digest": metadata["prediction_digest"]})


def canary(config: CapacityConfig) -> dict[str, Any]:
    """Repeat the largest/dropout variant on a fixed private sentinel."""
    runtime = _live_runtime(config)
    control = validate_control_predictions(config)
    replay_evidence = replay_control_sentinel(config)
    _, bundles, _, _ = _goal035_context(config)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00")
    root = config.private_root / "canary_repeats"; digests = []; canary_metadata = []
    for repeat in ("repeat_a", "repeat_b"):
        path = root / repeat / digest_value({"variant": "deepwide6_drop10", "target": sentinel.target, "held_fold": sentinel.held_fold, "seed": SEEDS[0]})
        _run_cell(str(config.source_path), sentinel, "deepwide6_drop10", SEEDS[0], path); digests.append(file_digest(path / "predictions.npy")); canary_metadata.append(json.loads((path / "metadata.json").read_text(encoding="utf-8")))
    determinism = digests[0] == digests[1] and canary_metadata[0]["prediction_digest"] == canary_metadata[1]["prediction_digest"]
    transfer = all(item["transfer_checks"]["multihead_shared_transfer"] and item["transfer_checks"]["common_target_head"] for item in canary_metadata)
    reset = all(item["transfer_checks"]["auxiliary_reset"] and item["transfer_checks"]["target_reset"] for item in canary_metadata)
    repeat_paths = [root / repeat / digest_value({"variant": "deepwide6_drop10", "target": sentinel.target, "held_fold": sentinel.held_fold, "seed": SEEDS[0]}) for repeat in ("repeat_a", "repeat_b")]
    finite = all(np.isfinite(np.load(path / "predictions.npy", allow_pickle=False)).all() for path in repeat_paths)
    _require(determinism and transfer and reset and finite, "canary lifecycle gate failed")
    control_digest = hashlib.sha256(np.ascontiguousarray(control_sentinel_slice(control[(sentinel.target, sentinel.held_fold)])).tobytes()).hexdigest()
    receipt = {"schema_version": "goal038-capacity-canary-v1", "success": True, "decision": "pass", "config_digest": config.config_digest, "sentinel": {"variant": "deepwide6_drop10", "target": sentinel.target, "held_fold": sentinel.held_fold, "seed": SEEDS[0]}, "prediction_digest": digests[0], "control_prediction_digest": control_digest, "control_replay": replay_evidence, "goal035_canary_receipt_digest": file_digest(config.root / config.raw["evidence"]["goal035_tracked_root"] / "canary.json"), "runtime": runtime, "runtime_digest": digest_value(runtime), "source_fingerprint": digest_value(sorted((name, binding["path"], binding["sha256"]) for name, binding in config.raw["execution_sources"].items())), "determinism": determinism, "transfer": transfer, "reset": reset, "finite": finite, "resource_timing": {"threads": 1, "blas_threads": 1}, "outer_attempted": 0, "outer_opened": 0}
    _write_json(config.canary_receipt, receipt); return receipt


def validate_canary(config: CapacityConfig) -> dict[str, Any]:
    runtime = _live_runtime(config)
    _require(config.canary_receipt.is_file(), "Goal038 canary receipt missing")
    value = json.loads(config.canary_receipt.read_text(encoding="utf-8"))
    _require(value.get("schema_version") == "goal038-capacity-canary-v1" and value.get("success") is True and value.get("config_digest") == config.config_digest and value.get("determinism") is True and value.get("transfer") is True and value.get("reset") is True and value.get("finite") is True and value.get("outer_attempted") == value.get("outer_opened") == 0, "Goal038 canary gate failed")
    _require(value.get("runtime") == runtime and value.get("runtime_digest") == digest_value(runtime) and isinstance(value.get("source_fingerprint"), str) and len(value["source_fingerprint"]) == 64 and isinstance(value.get("control_prediction_digest"), str) and len(value["control_prediction_digest"]) == 64 and isinstance(value.get("control_replay"), dict) and value["control_replay"].get("prediction_digest") == value["control_prediction_digest"], "Goal038 canary evidence schema drift")
    sentinel = value.get("sentinel", {}); _require(sentinel.get("variant") == "deepwide6_drop10" and sentinel.get("seed") == SEEDS[0], "Goal038 canary sentinel drift")
    _, bundles, _, _ = _goal035_context(config)
    sentinel_bundle = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00")
    expected_identity = _new_identity(config, sentinel_bundle, "deepwide6_drop10", SEEDS[0], runtime=runtime)
    repeat_digest = digest_value({"variant": "deepwide6_drop10", "target": sentinel_bundle.target, "held_fold": sentinel_bundle.held_fold, "seed": SEEDS[0]})
    paths = [config.private_root / "canary_repeats" / name / repeat_digest for name in ("repeat_a", "repeat_b")]
    _require(all(path.is_dir() for path in paths), "Goal038 canary leaves missing")
    values = [_validate_new_leaf(path, expected_identity) for path in paths]
    _require(np.array_equal(values[0], values[1]) and file_digest(paths[0] / "predictions.npy") == value.get("prediction_digest"), "Goal038 canary repeat mismatch")
    return value


def status_stage1(config: CapacityConfig) -> dict[str, Any]:
    _live_runtime(config)
    _, bundles, _, _ = _goal035_context(config); root = config.private_root / "cells"; complete = invalid = 0
    for bundle in bundles:
        for variant in NEW_VARIANTS:
            for seed in SEEDS:
                path = _cell_path(config, _new_identity(config, bundle, variant, seed))
                if not path.exists(): continue
                try: _validate_new_leaf(path, _new_identity(config, bundle, variant, seed)); complete += 1
                except (OSError, ValueError, KeyError, json.JSONDecodeError): invalid += 1
    return {**build_plan(config), "completed_leaves": complete, "missing_leaves": build_plan(config)["new_atomic_cells"] - complete - invalid, "invalid_leaves": invalid, "outer_attempted": 0, "outer_opened": 0}


def _validate_new_leaf(path: Path, identity: Mapping[str, Any]) -> np.ndarray:
    _require(path.is_dir() and {item.name for item in path.iterdir()} == {"metadata.json", "predictions.npy"}, "Goal038 leaf inventory drift")
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8")); values = np.load(path / "predictions.npy", allow_pickle=False)
    _require(metadata.get("identity") == dict(identity) and metadata.get("outer_attempted") == metadata.get("outer_opened") == 0, "Goal038 leaf identity drift")
    _require(metadata.get("runtime") is not None and digest_value(metadata["runtime"]) == identity.get("runtime_digest"), "Goal038 leaf runtime evidence drift")
    _require(identity.get("endpoint") == ENDPOINT and identity.get("held_row_count") == int(values.shape[1]) and isinstance(identity.get("runtime_digest"), str) and len(identity["runtime_digest"]) == 64, "Goal038 leaf runtime/endpoint binding drift")
    _require(values.dtype == np.float32 and values.shape[0] == 2 and values.ndim == 2 and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "Goal038 leaf prediction invalid")
    _require(metadata.get("prediction_digest") == hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest() and metadata.get("counts") == {"logical_lifecycles": 3, "physical_fits": 6}, "Goal038 leaf digest/arithmetic drift")
    _validate_lifecycle_diagnostics(metadata.get("lifecycle_diagnostics"), metadata.get("transfer_checks"), identity)
    return values


def _validate_lifecycle_diagnostics(diagnostics: Any, checks: Any, identity: Mapping[str, Any]) -> None:
    _require(isinstance(diagnostics, list) and [row.get("role") for row in diagnostics] == ["auxiliary_multihead", "target_only_resmlp", "multihead_full_finetune"], "Goal038 lifecycle role inventory drift")
    for row in diagnostics:
        expected_fit_seed = int(identity["seed"] if row["role"] == "auxiliary_multihead" else identity["fit_seed"])
        _require(row["fit_seed"] == expected_fit_seed and row["initial_model_digest"] == row["replay_initial_model_digest"] and row["selected_epoch"] == row["replay_epochs"] and row["selected_epoch"] >= 1 and row["discovery_executed_epochs"] >= row["selected_epoch"] and float(row["wall_seconds"]) >= 0 and isinstance(row["fit_seed"], int), "Goal038 lifecycle evidence invalid")
    aux, target, multi = diagnostics
    recomputed = {"auxiliary_reset": aux["initial_model_digest"] == aux["replay_initial_model_digest"], "target_reset": target["initial_model_digest"] == target["replay_initial_model_digest"] and multi["initial_model_digest"] == multi["replay_initial_model_digest"], "common_target_head": target["initial_head_digest"] == multi["initial_head_digest"], "multihead_shared_transfer": multi["initial_shared_digest"] == aux["final_shared_digest"]}
    _require(checks == recomputed and all(recomputed.values()), "Goal038 lifecycle transfer checks drift")


def _worker_cell(task: Mapping[str, Any]) -> str:
    from .final_inner_data import load_case_npz, load_config as load_goal035_config, validate_case_binding
    config = load_config(task["config_path"]); bundle = load_case_npz(task["bundle_path"])
    goal_config = load_goal035_config(config.root / config.raw["authorities"]["goal035_config"]["path"])
    validate_case_binding(bundle, goal_config)
    return _run_cell(task["config_path"], bundle, task["variant"], int(task["seed"]), Path(task["leaf_path"]))


def _stage_metrics(config: CapacityConfig) -> list[dict[str, Any]]:
    control = validate_control_predictions(config); _, bundles, _, _ = _goal035_context(config)
    by_variant: dict[str, list[dict[str, Any]]] = {variant: [] for variant in NEW_VARIANTS}
    for bundle in bundles:
        y = bundle.arrays["y_held"]
        for variant in NEW_VARIANTS:
            rows = []
            for seed_index, seed in enumerate(SEEDS):
                path = _cell_path(config, _new_identity(config, bundle, variant, seed)); values = _validate_new_leaf(path, _new_identity(config, bundle, variant, seed))
                rows.append({"variant": variant, "species": bundle.target, "fold": bundle.held_fold, "seed": seed, "y": y, "target_only": values[0], "multihead": values[1]})
            by_variant[variant].extend(rows)
    thresholds: dict[tuple[str, str, str], float] = {}
    for variant, rows in by_variant.items():
        for species_name in SPECIES:
            for method in ("target_only", "multihead"):
                pooled_y = []; pooled_scores = []
                for fold in FOLDS:
                    fold_rows = [record for record in rows if record["species"] == species_name and record["fold"] == fold]
                    if fold_rows:
                        pooled_y.extend(fold_rows[0]["y"]); pooled_scores.extend(average_common_seed_predictions(np.asarray([record[method] for record in fold_rows])))
                thresholds[(variant, species_name, "target_only" if method == "target_only" else "multihead_full_finetune")] = choose_tss_threshold(pooled_y, pooled_scores)
    lifts = {variant: aggregate_species_lifts(rows, threshold=thresholds) for variant, rows in by_variant.items()}
    control_rows = []
    for bundle in bundles:
        values = control[(bundle.target, bundle.held_fold)]
        control_rows.extend({"variant": "control", "species": bundle.target, "fold": bundle.held_fold, "seed": seed, "y": bundle.arrays["y_held"], "target_only": values[index, 0], "multihead": values[index, 1]} for index, seed in enumerate(SEEDS))
    control_thresholds: dict[tuple[str, str, str], float] = {}
    for species_name in SPECIES:
        for method in ("target_only", "multihead_full_finetune"):
            pooled_y = []; pooled_scores = []
            for fold in FOLDS:
                fold_rows = [record for record in control_rows if record["species"] == species_name and record["fold"] == fold]
                if fold_rows:
                    pooled_y.extend(fold_rows[0]["y"]); pooled_scores.extend(average_common_seed_predictions(np.asarray([record[_prediction_field(method)] for record in fold_rows])))
            control_thresholds[("control", species_name, method)] = choose_tss_threshold(pooled_y, pooled_scores)
    control_lifts = aggregate_species_lifts(control_rows, threshold=control_thresholds)
    out: list[dict[str, Any]] = []
    for variant in NEW_VARIANTS:
        def species_metric(rows: Sequence[Mapping[str, Any]], field: str, species: str, seed: int | None = None) -> float:
            vals = [float(row[field]) for row in rows if row["species"] == species and (seed is None or row.get("seed") == seed)]
            return float(np.mean(vals))
        species = list(SPECIES); l_auc = []; l_tss = []; l_mcc = []; d_auc = []; d_tss = []; d_mcc = []
        for species_name in species:
            vr = [row for row in lifts[variant] if row["species"] == species_name]; cr = [row for row in control_lifts if row["species"] == species_name]
            l_auc.append(species_metric(vr, "lift_auc", species_name)); l_tss.append(species_metric(vr, "lift_tss", species_name)); l_mcc.append(species_metric(vr, "lift_mcc", species_name)); d_auc.append(l_auc[-1] - species_metric(cr, "lift_auc", species_name)); d_tss.append(l_tss[-1] - species_metric(cr, "lift_tss", species_name)); d_mcc.append(l_mcc[-1] - species_metric(cr, "lift_mcc", species_name))
        seed_values_by_seed: dict[int, list[float]] = {}
        for seed in SEEDS:
            seed_d_values = []
            for species_name in species:
                vr = [record for record in by_variant[variant] if record["seed"] == seed and record["species"] == species_name]
                cr = [record for record in control_rows if record["seed"] == seed and record["species"] == species_name]
                v_lift = np.mean([binary_metrics(record["y"], record["multihead"], thresholds[(variant, species_name, "multihead_full_finetune")])["auc"] - binary_metrics(record["y"], record["target_only"], thresholds[(variant, species_name, "target_only")])["auc"] for record in vr])
                c_lift = np.mean([binary_metrics(record["y"], record["multihead"], control_thresholds[("control", species_name, "multihead_full_finetune")])["auc"] - binary_metrics(record["y"], record["target_only"], control_thresholds[("control", species_name, "target_only")])["auc"] for record in cr])
                seed_d_values.append(float(v_lift - c_lift))
            seed_values_by_seed[seed] = seed_d_values
        seed_positive = seed_gate_count(seed_values_by_seed)
        row = {"variant": variant, "parameter_count": parameter_count(VARIANTS[variant]), "median_species_d_auc": float(np.median(d_auc)), "mean_species_d_auc": float(np.mean(d_auc)), "median_species_l_auc": float(np.median(l_auc)), "median_species_d_tss": float(np.median(d_tss)), "species_d_auc_positive": int(sum(value > 0 for value in d_auc)), "seed_d_auc_positive": seed_positive, "species_d_auc": d_auc, "species_l_auc": l_auc, "species_d_tss": d_tss, "species_d_mcc": d_mcc, "seed_d_auc": {str(seed): float(np.mean(seed_values_by_seed[seed])) for seed in SEEDS}}
        row["eligible"] = eligibility_gate(row); out.append(row)
    return out


def _receipt_extras(config: CapacityConfig) -> dict[str, Any]:
    control = validate_control_predictions(config)
    source_fingerprint = digest_value(sorted((name, binding["path"], binding["sha256"]) for name, binding in config.raw["execution_sources"].items()))
    identities = []; contents = []
    for path in sorted((config.private_root / "cells").glob("*/metadata.json")):
        metadata = json.loads(path.read_text(encoding="utf-8")); values = np.load(path.parent / "predictions.npy", allow_pickle=False)
        identities.append(digest_value(metadata["identity"])); contents.append(digest_value({"identity": metadata["identity"], "metadata": {key: value for key, value in metadata.items() if key != "identity"}, "prediction_digest": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()}))
    return {"authority_digests": {name: binding["sha256"] for name, binding in sorted(config.raw["authorities"].items())}, "source_fingerprint": source_fingerprint, "runtime": config.raw["runtime"], "control_inventory_digest": digest_value(sorted((target, fold, hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()) for (target, fold), values in control.items())), "leaf_inventory_digest": digest_value(sorted(identities)), "leaf_content_inventory_digest": digest_value(sorted(contents)), "threshold_authority_digest": config.raw["authorities"]["goal036_summary"]["sha256"]}


def finalize_stage1(config: CapacityConfig) -> dict[str, Any]:
    _live_runtime(config); validate_canary(config)
    status = status_stage1(config); _require(status["missing_leaves"] == 0 and status["invalid_leaves"] == 0, "Goal038 leaves incomplete or invalid")
    rows = _stage_metrics(config); ranked = rank_eligible(rows); decision = "advance_stage2" if ranked else "stop_no_stage2"
    receipt = {"schema_version": "goal038-capacity-aggregate-v1", "success": True, "config_digest": config.config_digest, **build_plan(config), **_receipt_extras(config), "variant_metrics": rows, "eligible_ranking": ranked[:1], "decision": decision, "outer_attempted": 0, "outer_opened": 0}
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json(config.tracked_root / "aggregate.json", receipt); return receipt


def validate_stage1(config: CapacityConfig) -> dict[str, Any]:
    _live_runtime(config); validate_canary(config)
    path = config.tracked_root / "aggregate.json"; _require(path.is_file(), "Goal038 aggregate missing")
    value = json.loads(path.read_text(encoding="utf-8")); rows = _stage_metrics(config); expected = {"schema_version": "goal038-capacity-aggregate-v1", "success": True, "config_digest": config.config_digest, **build_plan(config), **_receipt_extras(config), "variant_metrics": rows, "eligible_ranking": rank_eligible(rows)[:1], "decision": "advance_stage2" if rank_eligible(rows) else "stop_no_stage2", "outer_attempted": 0, "outer_opened": 0}
    expected["receipt_digest"] = digest_value(expected)
    _require(value == expected, "Goal038 aggregate receipt mismatch")
    return value


def run_stage1(config: CapacityConfig) -> dict[str, Any]:
    _live_runtime(config)
    validate_canary(config); _, bundles, _, _ = _goal035_context(config); bundle_paths = {path.stem: path for path in (config.root / config.raw["evidence"]["goal035_private_root"]).glob("*.npz")}; tasks = []
    for bundle in bundles:
        path = bundle_paths.get(f"{bundle.target}--{bundle.held_fold}"); _require(path is not None, "Goal035 bundle path inventory drift")
        for variant in NEW_VARIANTS:
            for seed in SEEDS:
                identity = _new_identity(config, bundle, variant, seed); leaf = _cell_path(config, identity)
                if leaf.exists(): _validate_new_leaf(leaf, identity); continue
                tasks.append({"config_path": str(config.source_path), "bundle_path": str(path), "variant": variant, "seed": seed, "leaf_path": str(leaf)})
    if tasks:
        with ProcessPoolExecutor(max_workers=3, mp_context=mp.get_context("spawn")) as pool: list(pool.map(_worker_cell, tasks))
    return status_stage1(config)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("plan", "canary", "run-stage1", "status-stage1", "finalize-stage1", "validate-stage1")); parser.add_argument("--config", default="config/dsdm_capacity_diagnostic.json")
    args = parser.parse_args(argv); config = load_config(args.config)
    result = {"plan": build_plan, "canary": canary, "run-stage1": run_stage1, "status-stage1": status_stage1, "finalize-stage1": finalize_stage1, "validate-stage1": validate_stage1}[args.command](config)
    print(json.dumps(result, sort_keys=True, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["CapacityConfig", "CapacityDiagnosticError", "VARIANTS", "NEW_VARIANTS", "SEEDS", "METHODS", "parameter_count", "build_plan", "load_config", "average_common_seed_predictions", "binary_metrics", "eligibility_gate", "rank_eligible", "aggregate_species_lifts", "canary", "validate_canary", "run_stage1", "status_stage1", "finalize_stage1", "validate_stage1", "main"]
