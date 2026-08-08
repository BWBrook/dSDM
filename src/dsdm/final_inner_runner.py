"""Lean Goal035 final inner lifecycle runner.

The runner owns only private case leaves.  It never serialises labels or model
weights into a leaf and refuses production execution until the corrected
architecture receipt and a deterministic two-repeat canary are present.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import time
from typing import Any, Mapping, Sequence
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits
import torch

from .contracts import ARCHITECTURES, METHODS, SPECIES, ArchitectureSpec
from .models import MultiHeadResidual, ResidualMLP
from .real_six_path import (
    _artifact, _cpu_state, _neural_lifecycle, _prediction_digest, _residual_factory,
    _runtime_attestation, _scalar_from_linear, _scalar_from_neural, _seed,
    _shared_state, _state_digest, _prepare_device, _q_weights,
)
from .final_inner_data import (
    ENDPOINT_SLUGS, ENDPOINTS, SEEDS, CaseBundle, FinalInnerConfig,
    FinalInnerError, array_digest, canonical, digest_bytes, digest_value,
    leaf_identity, load_case_npz, load_config, prepare_case, runtime_attestation,
    _validate_endpoint_nesting,
    validate_bundle_inventory, validate_case_binding, validate_leaf, write_leaf,
)


class FinalInnerRunError(FinalInnerError):
    """Raised when execution or aggregate evidence is incomplete."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FinalInnerRunError(message)


def _bundle_inventory_digest(bundles: Sequence[CaseBundle]) -> str:
    return digest_value(sorted(bundle.source_digest for bundle in bundles))


def _without_wall(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _without_wall(item) for key, item in value.items() if key != "wall_seconds"}
    if isinstance(value, list):
        return [_without_wall(item) for item in value]
    return value


def _leaf_content_digest(path: Path) -> str:
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    predictions = np.load(path / "predictions.npy", allow_pickle=False)
    return digest_value({"metadata": _without_wall(metadata), "prediction_digest": array_digest(predictions)})


def _bind_artifact(artifact: dict[str, Any], *, fit_seed: int, runtime_digest: str) -> dict[str, Any]:
    value = dict(artifact)
    value["fit_seed"] = int(fit_seed)
    value["runtime_digest"] = runtime_digest
    return value


def _architecture(config: FinalInnerConfig) -> Any:
    _require(config.corrected_winner, "corrected architecture receipt is required")
    for row in ARCHITECTURES:
        if row[0] == config.corrected_winner:
            return ArchitectureSpec(*row)
    raise FinalInnerRunError("corrected architecture is not in the frozen registry")


def _fit_seed(config: FinalInnerConfig, bundle: CaseBundle, endpoint: str, seed: int, method: str) -> int:
    text = f"goal035-final-inner|{bundle.target}|{bundle.held_fold}|{endpoint}|{seed}|{method}|{config.corrected_winner}"
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


def _q_fit(
    x: np.ndarray,
    y: np.ndarray,
    species: np.ndarray,
    seed: int,
    *,
    stability_x: np.ndarray,
) -> tuple[LogisticRegression, dict[str, Any]]:
    """Fit q, extending only warned cases behind a prediction-stability gate."""
    started = time.monotonic()

    def fit_once(max_iter: int) -> tuple[LogisticRegression, int, bool]:
        fitted = LogisticRegression(penalty="elasticnet", solver="saga", C=1.0, l1_ratio=0.5, max_iter=max_iter, tol=1e-5, random_state=seed)
        with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.filterwarnings("ignore", category=FutureWarning)
            fitted.fit(x, y, sample_weight=_q_weights(species))
        iteration = int(np.max(fitted.n_iter_))
        warned = any(issubclass(item.category, ConvergenceWarning) for item in caught)
        return fitted, iteration, warned

    primary, primary_n_iter, primary_warned = fit_once(5000)
    model = primary
    n_iter = primary_n_iter
    convergence = not primary_warned
    termination_status = "converged"
    stability_accepted = False
    stability_delta = 0.0
    _require(0 < primary_n_iter <= 5000, "q_linear primary iteration evidence invalid")
    if primary_warned:
        comparison, n_iter, comparison_warned = fit_once(10000)
        stability_values = np.asarray(stability_x, dtype=np.float32)
        _require(stability_values.ndim == 2 and stability_values.shape[1] == x.shape[1] and len(stability_values) > 0 and np.isfinite(stability_values).all(), "q_linear stability predictors invalid")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            primary_probability = primary.predict_proba(stability_values)[:, 1]
            comparison_probability = comparison.predict_proba(stability_values)[:, 1]
        _require(np.isfinite(primary_probability).all() and np.isfinite(comparison_probability).all(), "q_linear stability predictions non-finite")
        stability_delta = float(np.max(np.abs(comparison_probability - primary_probability)))
        _require(stability_delta <= 1e-4, "q_linear prediction stability gate failed")
        model = comparison
        convergence = not comparison_warned
        if convergence:
            _require(5000 < n_iter < 10000, "q_linear extended convergence evidence invalid")
            termination_status = "converged_after_extension"
        else:
            _require(n_iter == 10000, "q_linear stability ceiling evidence invalid")
            termination_status = "prediction_stable_at_iteration_ceiling"
            stability_accepted = True
    digest = hashlib.sha256()
    for value in (model.classes_, model.coef_, model.intercept_):
        digest.update(np.asarray(value).tobytes(order="C"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        logits = model.decision_function(x).astype(np.float32)
        probabilities = model.predict_proba(x)[:, 1].astype(np.float32)
    _require(np.isfinite(model.coef_).all() and np.isfinite(model.intercept_).all() and np.isfinite(logits).all() and np.isfinite(probabilities).all(), "q_linear selected fit non-finite")
    return model, {"artifact_id": "aux/q_linear", "kind": "auxiliary", "logical_artifacts": 1, "physical_fits": 2 if primary_warned else 1, "selected_epoch": 0, "discovery_executed_epochs": 0, "replay_epochs": 0, "stopping_status": "not_applicable", "initial_model_digest": "not_applicable", "replay_initial_model_digest": "not_applicable", "initial_shared_digest": "not_applicable", "final_shared_digest": "not_applicable", "initial_head_digest": "not_applicable", "model_digest": digest.hexdigest(), "prediction_digest": array_digest(probabilities), "n_iter": n_iter, "primary_n_iter": primary_n_iter, "convergence": convergence, "termination_status": termination_status, "stability_accepted": stability_accepted, "stability_probability_delta": stability_delta, "stability_probability_tolerance": 1e-4, "coefficient_range": {"min": float(np.asarray(model.coef_).min()), "max": float(np.asarray(model.coef_).max())}, "logit_range": {"min": float(logits.min()), "max": float(logits.max())}, "probability_range": {"min": float(probabilities.min()), "max": float(probabilities.max())}, "finite": True, "wall_seconds": round(time.monotonic() - started, 6)}


def _auxiliary_lifecycle(bundle: CaseBundle, prepared: Mapping[str, Any], spec: Any, seed: int, device: torch.device) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    x = prepared["auxiliary"]
    names = tuple(name for name in SPECIES if name != bundle.target)
    ys = {role: bundle.arrays[f"aux_y_{role}"] for role in ("discovery", "stopping", "replay")}
    sp = {role: bundle.arrays[f"aux_species_{role}"] for role in ("discovery", "stopping", "replay")}
    pooled = _neural_lifecycle(
        _residual_factory(spec, 77), spec, seed, device,
        x["discovery"], ys["discovery"], x["stopping"], ys["stopping"], x["replay"], ys["replay"], x["replay"],
        max_epochs=300, patience=30, species_names=names, species_discovery=sp["discovery"], species_stopping=sp["stopping"], species_replay=sp["replay"],
    )
    multi_factory = lambda: MultiHeadResidual(spec, 77, names)
    multi = _neural_lifecycle(
        multi_factory, spec, seed, device,
        x["discovery"], ys["discovery"], x["stopping"], ys["stopping"], x["replay"], ys["replay"], x["replay"],
        max_epochs=300, patience=30, species_names=names, species_discovery=sp["discovery"], species_stopping=sp["stopping"], species_replay=sp["replay"], species_prediction=sp["replay"],
    )
    return pooled.model, multi.model, _artifact(f"aux/pooled/seed{seed}", "auxiliary", pooled), _artifact(f"aux/multihead/seed{seed}", "auxiliary", multi)


def _case_lifecycle(bundle: CaseBundle, config: FinalInnerConfig, *, device: str = "cpu", max_epochs: int | None = None, patience: int | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    target_device = _prepare_device(device)
    runtime = runtime_attestation(config, strict=True)
    runtime_digest = digest_value(runtime)
    prepared = prepare_case(bundle)
    spec = _architecture(config)
    epochs = int(max_epochs if max_epochs is not None else config.raw["training"]["max_epochs"])
    patience_value = int(patience if patience is not None else config.raw["training"]["patience"])
    _require(1 <= patience_value <= epochs, "epoch budget invalid")
    aux_artifacts: list[dict[str, Any]] = []
    aux_models: dict[int, tuple[Any, Any]] = {}
    for seed in SEEDS:
        pooled, multi, pooled_artifact, multi_artifact = _auxiliary_lifecycle(bundle, prepared, spec, seed, target_device)
        aux_models[seed] = (pooled, multi)
        aux_artifacts.extend((_bind_artifact(pooled_artifact, fit_seed=seed, runtime_digest=runtime_digest), _bind_artifact(multi_artifact, fit_seed=seed, runtime_digest=runtime_digest)))
    q_x = prepared["auxiliary"]["replay"]
    q_y = bundle.arrays["aux_y_replay"]
    q_species = bundle.arrays["aux_species_replay"]
    q_stability_x = np.vstack([q_x, *(prepared["q_inputs"][key] for key in sorted(prepared["q_inputs"]))]).astype(np.float32)
    q_model, q_artifact = _q_fit(q_x, q_y, q_species, _fit_seed(config, bundle, "auxiliary", SEEDS[0], "q_linear"), stability_x=q_stability_x)
    aux_artifacts.append(_bind_artifact(q_artifact, fit_seed=_fit_seed(config, bundle, "auxiliary", SEEDS[0], "q_linear"), runtime_digest=runtime_digest))
    q_linear_values = {role: _scalar_from_linear(q_model, prepared["q_inputs"][f"{ENDPOINTS[0]}/{role}"]) for role in ("discovery", "stopping", "replay", "held")}
    predictions = np.empty((len(SEEDS), len(ENDPOINTS), len(METHODS), len(bundle.arrays["x_held"])), dtype=np.float32)
    target_artifacts: list[dict[str, Any]] = []
    target_masks = prepared["target_masks"]
    aux_mask = prepared["auxiliary_mask"]
    for seed_index, seed in enumerate(SEEDS):
        pooled, multi = aux_models[seed]
        pooled_state = _cpu_state(pooled)
        shared_state = _shared_state(multi)
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            slug = ENDPOINT_SLUGS[endpoint]
            raw = bundle.arrays
            xdis = prepared["target"][f"target_{slug}_x_discovery"]
            xstop = prepared["target"][f"target_{slug}_x_stopping"]
            xrep = prepared["target"][f"target_{slug}_x_replay"]
            xheld = prepared["target"][f"target_{slug}_x_held"]
            ydis, ystop, yrep = raw[f"target_{slug}_y_discovery"], raw[f"target_{slug}_y_stopping"], raw[f"target_{slug}_y_replay"]
            q_input = {role: prepared["q_inputs"][f"{endpoint}/{role}"] for role in ("discovery", "stopping", "replay", "held")}
            q_values = {role: _scalar_from_linear(q_model, q_input[role]) for role in q_input}
            q_deep_values = {role: _scalar_from_neural(pooled, q_input[role], target_device) for role in q_input}
            x_by_method: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any, bool]] = {
                "target_only_resmlp": (xdis, xstop, xrep, xheld, _residual_factory(spec, 77), False),
                "legacy_pooled_finetune": (xdis, xstop, xrep, xheld, _residual_factory(spec, 77, full_state=pooled_state), False),
                "multihead_frozen_trunk": (xdis, xstop, xrep, xheld, _residual_factory(spec, 77, shared_state=shared_state), True),
                "multihead_full_finetune": (xdis, xstop, xrep, xheld, _residual_factory(spec, 77, shared_state=shared_state), False),
                "target_plus_q_linear": (np.column_stack((xdis, q_values["discovery"])), np.column_stack((xstop, q_values["stopping"])), np.column_stack((xrep, q_values["replay"])), np.column_stack((xheld, q_values["held"])), _residual_factory(spec, 78), False),
                "target_plus_q_deep": (np.column_stack((xdis, q_deep_values["discovery"])), np.column_stack((xstop, q_deep_values["stopping"])), np.column_stack((xrep, q_deep_values["replay"])), np.column_stack((xheld, q_deep_values["held"])), _residual_factory(spec, 78), False),
            }
            for method_index, method in enumerate(METHODS):
                xd, xs, xr, xh, factory, frozen = x_by_method[method]
                lifecycle = _neural_lifecycle(factory, spec, _fit_seed(config, bundle, endpoint, seed, "target"), target_device, xd, ydis, xs, ystop, xr, yrep, xh, max_epochs=epochs, patience=patience_value, freeze_shared=frozen)
                # _neural_lifecycle retains the replay model; use its deterministic prediction helper.
                with torch.no_grad():
                    logits = lifecycle.model(torch.from_numpy(np.ascontiguousarray(xh)).to(target_device))
                    values = torch.sigmoid(logits).detach().cpu().numpy().astype(np.float32)
                _require(values.shape == (len(xh),) and np.isfinite(values).all(), "target prediction invalid")
                predictions[seed_index, endpoint_index, method_index] = values
                target_artifacts.append(_bind_artifact(_artifact(f"target/{endpoint}/seed{seed}/{method}", "target", lifecycle), fit_seed=_fit_seed(config, bundle, endpoint, seed, "target"), runtime_digest=runtime_digest))
    artifacts = aux_artifacts + target_artifacts
    by_id = {item["artifact_id"]: item for item in artifacts}
    for seed in SEEDS:
        target_rows = [item for item in target_artifacts if f"seed{seed}/" in item["artifact_id"]]
        target_only = next(item for item in target_rows if item["artifact_id"].endswith("/target_only_resmlp"))
        frozen = next(item for item in target_rows if item["artifact_id"].endswith("/multihead_frozen_trunk"))
        full = next(item for item in target_rows if item["artifact_id"].endswith("/multihead_full_finetune"))
        qlinear = next(item for item in target_rows if item["artifact_id"].endswith("/target_plus_q_linear"))
        qdeep = next(item for item in target_rows if item["artifact_id"].endswith("/target_plus_q_deep"))
        _require(target_only["initial_head_digest"] == frozen["initial_head_digest"] == full["initial_head_digest"], "target transfer head mismatch")
        _require(frozen["initial_model_digest"] == full["initial_model_digest"], "frozen/full initial mismatch")
        legacy = next(item for item in target_rows if item["artifact_id"].endswith("/legacy_pooled_finetune"))
        aux_pooled = next(item for item in aux_artifacts if item["artifact_id"] == f"aux/pooled/seed{seed}")
        aux_multi = next(item for item in aux_artifacts if item["artifact_id"] == f"aux/multihead/seed{seed}")
        _require(legacy["initial_model_digest"] == aux_pooled["model_digest"], "legacy pooled transfer mismatch")
        _require(frozen["initial_shared_digest"] == full["initial_shared_digest"] == aux_multi["final_shared_digest"], "multihead shared transfer mismatch")
        _require(frozen["initial_shared_digest"] == frozen["final_shared_digest"], "frozen trunk changed")
        _require(qlinear["initial_model_digest"] == qdeep["initial_model_digest"], "q method initial mismatch")
    physical_fits = sum(item["physical_fits"] for item in artifacts)
    _require(len(artifacts) == 221 and physical_fits in {441, 442}, "case lifecycle arithmetic drift")
    metadata = {
        "schema_version": "goal035-final-inner-case-v1", "goal_id": "goal035-dsdm-final-inner-lifecycle", "target": bundle.target, "held_fold": bundle.held_fold,
        "architecture": config.corrected_winner, "config_digest": config.config_digest, "bundle_digest": bundle.source_digest,
        "target_mask_digests": {endpoint: target_masks[endpoint].digest for endpoint in ENDPOINTS}, "auxiliary_mask_digest": aux_mask.digest,
        "support_overlap": prepared["support_overlap"], "target_support_audits": prepared["target_audits"], "auxiliary_support_audits": prepared["auxiliary_audits"],
        "q_ranges": {"linear": {"coefficient_min": float(np.asarray(q_model.coef_).min()), "coefficient_max": float(np.asarray(q_model.coef_).max()), "probability_min": float(min(value.min() for value in q_linear_values.values())), "probability_max": float(max(value.max() for value in q_linear_values.values()))}, "deep": {"probability_min": float(min(_scalar_from_neural(aux_models[SEEDS[0]][0], prepared["q_inputs"][f"{ENDPOINTS[0]}/{role}"], target_device).min() for role in ("discovery", "stopping", "replay", "held"))), "probability_max": float(max(_scalar_from_neural(aux_models[SEEDS[0]][0], prepared["q_inputs"][f"{ENDPOINTS[0]}/{role}"], target_device).max() for role in ("discovery", "stopping", "replay", "held"))) }},
        "target_plus_q_prediction_ranges": {"linear_min": float(predictions[:, :, METHODS.index("target_plus_q_linear")].min()), "linear_max": float(predictions[:, :, METHODS.index("target_plus_q_linear")].max()), "deep_min": float(predictions[:, :, METHODS.index("target_plus_q_deep")].min()), "deep_max": float(predictions[:, :, METHODS.index("target_plus_q_deep")].max())},
        "artifacts": artifacts, "counts": {"auxiliary_logical_artifacts": 11, "target_logical_artifacts": 210, "logical_artifacts": 221, "physical_fits": physical_fits},
        "runtime": runtime, "outer_attempted": 0, "outer_opened": 0,
    }
    return predictions, metadata


def run_case(bundle: CaseBundle, config: FinalInnerConfig, *, leaf_root: str | Path | None = None, device: str = "cpu", max_epochs: int | None = None, patience: int | None = None) -> Path | tuple[np.ndarray, dict[str, Any]]:
    runtime_attestation(config, strict=True)
    predictions, metadata = _case_lifecycle(bundle, config, device=device, max_epochs=max_epochs, patience=patience)
    identity = {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": config.config_digest, "runtime_digest": digest_value(metadata["runtime"]), "architecture": config.corrected_winner, "mask_digest": digest_value(metadata["target_mask_digests"]), "aux_mask_digest": metadata["auxiliary_mask_digest"]}
    if leaf_root is None:
        return predictions, {**metadata, "identity": identity, "prediction_digest": array_digest(predictions)}
    return write_leaf(leaf_root, identity, predictions, metadata)


def _run_case_worker(task: Mapping[str, Any]) -> str:
    config = load_config(task["config_path"])
    runtime_attestation(config, strict=True)
    bundle = load_case_npz(task["bundle_path"])
    validate_case_binding(bundle, config)
    return str(run_case(bundle, config, leaf_root=task["leaf_root"], device="cpu"))


def canary(config: FinalInnerConfig, bundle_root: str | Path, output: str | Path, *, max_epochs: int | None = None, patience: int | None = None) -> dict[str, Any]:
    runtime_attestation(config, strict=True)
    bundles = validate_bundle_inventory(bundle_root, config=config)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00")
    repeat_root = config.private_root / "canary_repeats"
    first_path = run_case(sentinel, config, leaf_root=repeat_root / "repeat_a", device="cpu", max_epochs=max_epochs, patience=patience)
    second_path = run_case(sentinel, config, leaf_root=repeat_root / "repeat_b", device="cpu", max_epochs=max_epochs, patience=patience)
    metadata_a = validate_leaf(first_path, json.loads((first_path / "metadata.json").read_text(encoding="utf-8"))["identity"])
    metadata_b = validate_leaf(second_path, json.loads((second_path / "metadata.json").read_text(encoding="utf-8"))["identity"])
    first = np.load(first_path / "predictions.npy", allow_pickle=False)
    second = np.load(second_path / "predictions.npy", allow_pickle=False)
    _require(np.array_equal(first, second), "canary prediction repeat mismatch")
    deterministic_a, deterministic_b = _without_wall(metadata_a), _without_wall(metadata_b)
    _require(deterministic_a == deterministic_b, "canary deterministic evidence repeat mismatch")
    fields = ("artifact_id", "selected_epoch", "discovery_executed_epochs", "replay_epochs", "stopping_status", "initial_model_digest", "replay_initial_model_digest", "initial_shared_digest", "final_shared_digest", "initial_head_digest", "model_digest", "prediction_digest", "n_iter", "primary_n_iter", "termination_status", "stability_accepted", "stability_probability_delta", "fit_seed", "runtime_digest")
    left = [tuple(item.get(field) for field in fields) for item in metadata_a["artifacts"]]
    strict_runtime = runtime_attestation(config, strict=True)
    receipt = {"schema_version": "goal035-final-inner-canary-v1", "success": True, "decision": "pass", "config_digest": config.config_digest, "corrected_winner": config.corrected_winner, "target": sentinel.target, "held_fold": sentinel.held_fold, "bundle_inventory_digest": _bundle_inventory_digest(bundles), "sentinel_bundle_digest": sentinel.source_digest, "source_fingerprint": config.source_fingerprint, "runtime": strict_runtime, "runtime_digest": digest_value(strict_runtime), "counts": dict(metadata_a["counts"]), "repeat_a_content_digest": _leaf_content_digest(first_path), "repeat_b_content_digest": _leaf_content_digest(second_path), "prediction_digest": array_digest(first), "artifact_digest": digest_value(left), "deterministic_evidence_digest": digest_value(deterministic_a), "gates": {"transfer": True, "reset": True, "frozen_trunk": True, "q_initial": True, "outer": True}, "outer_attempted": 0, "outer_opened": 0}
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_text(canonical(receipt).decode() + "\n", encoding="utf-8"); temporary.replace(path)
    return receipt


def export_from_foundation(config: FinalInnerConfig, *, root: str | Path, output: str | Path) -> list[Path]:
    """Export the 53-array private case layout from the sealed foundation.

    This is the only path that knows the Phase-1 foundation.  It creates one
    shared held view per case (not seven duplicates), seven target endpoint
    training views, and the permitted four-fold auxiliary view.
    """
    _require(Path(root).resolve() == config.root, "export root/config mismatch")
    from .real_data import CaseSpec, _encode, records_from_foundation
    from dsdm_phase1.goal029_production import ingest_production_foundation
    from dsdm_phase1.target_subsets import build_ladders

    authorities = config.raw["authorities"]
    foundation_binding = {"bindings": {name: deepcopy(authorities[name]) for name in ("goal029_config", "goal026_feature_contract", "goal026_fit_parameters")}, "training": {"base_seed": SEEDS[0]}}
    goal029_path = config.root / authorities["goal029_config"]["path"]
    goal029_raw = json.loads(goal029_path.read_text(encoding="utf-8"))
    broker, _, vault = ingest_production_foundation(config.root, goal029_raw)
    _require(vault.attempted_open_count == vault.open_count == 0, "outer access during export binding")
    output_root = Path(output); output_root.mkdir(parents=True, exist_ok=True); written: list[Path] = []
    for target in SPECIES:
        for held_fold in (f"fold{i:02d}" for i in range(5)):
            case = CaseSpec("goal035", target, held_fold, config.corrected_winner, SEEDS[0])
            records, source_audit = records_from_foundation(config.root, foundation_binding, case)
            _require(source_audit.get("outer_attempted") == source_audit.get("outer_opened") == 0, "outer access during export")
            record_by_key = {(str(row["species"]), str(row["cell"])): row for row in records}
            training, assessment = broker.inner(target, held_fold)
            ladders = build_ladders(training)
            arrays: dict[str, np.ndarray] = {}
            stopping_fold = case.stopping_fold
            nonheld_folds = {fold for fold in (f"fold{i:02d}" for i in range(5)) if fold != held_fold}
            discovery_folds = nonheld_folds - {stopping_fold}
            for endpoint in ENDPOINTS:
                fraction, ladder_name = endpoint.split("/")
                lookup_ladder = "ladder00" if fraction == "fraction100" else ladder_name
                keys = ladders[(fraction, lookup_ladder)].keys
                role_keys = {"discovery": [key for key in keys if broker._fold_by_key[key] in discovery_folds], "stopping": [key for key in keys if broker._fold_by_key[key] == stopping_fold], "replay": list(keys)}
                slug = ENDPOINT_SLUGS[endpoint]
                for role, selected in role_keys.items():
                    _require(selected, f"empty export role {target}/{held_fold}/{endpoint}/{role}")
                    rows = [record_by_key[(key.species_id, key.grid_cell_id)] for key in selected]
                    arrays[f"target_{slug}_x_{role}"] = np.stack([_encode(row) for row in rows]).astype(np.float32)
                    arrays[f"target_{slug}_y_{role}"] = np.asarray([row["y"] for row in rows], dtype=np.float32)
            held_rows = [record_by_key[(key.species_id, key.grid_cell_id)] for key in assessment.keys]
            arrays["x_held"] = np.stack([_encode(row) for row in held_rows]).astype(np.float32)
            arrays["y_held"] = np.asarray([row["y"] for row in held_rows], dtype=np.float32)
            auxiliary = [row for row in records if row["species"] != target and row["fold"] != held_fold and row["source"] in {"presence", "survey_supported_absence"}]
            auxiliary_names = tuple(name for name in SPECIES if name != target); species_index = {name: index for index, name in enumerate(auxiliary_names)}
            for role, folds in {"discovery": discovery_folds, "stopping": {stopping_fold}, "replay": nonheld_folds}.items():
                rows = [row for row in auxiliary if row["fold"] in folds]
                _require(rows, f"empty auxiliary export role {target}/{held_fold}/{role}")
                arrays[f"aux_x_{role}"] = np.stack([_encode(row) for row in rows]).astype(np.float32)
                arrays[f"aux_y_{role}"] = np.asarray([row["y"] for row in rows], dtype=np.float32)
                arrays[f"aux_species_{role}"] = np.asarray([species_index[str(row["species"])] for row in rows], dtype=np.int32)
            inventory = {name: array_digest(value) for name, value in sorted(arrays.items())}
            subset_nesting_by_ladder = _validate_endpoint_nesting(arrays)
            subset_nesting = all(subset_nesting_by_ladder.values())
            _require(subset_nesting, f"target ladder nesting failed: {target}/{held_fold}")
            aux_counts = {str(index): int(np.sum(arrays["aux_species_replay"] == index)) for index in range(7)}
            aux_total = float(len(arrays["aux_species_replay"]) / 7.0)
            metadata = {"schema_version": "goal035-final-inner-bundle-v1", "goal_id": "goal035-dsdm-final-inner-lifecycle", "case_id": f"{target}--{held_fold}", "target": target, "held_fold": held_fold, "stopping_fold": stopping_fold, "config_digest": config.config_digest, "authority_digests": dict(config.authority_digests), "source_digests": dict(config.source_digests), "source_fingerprint": config.source_fingerprint, "source_binding_digest": str(source_audit["source_binding_digest"]), "subset_membership_digests": {endpoint: ladders[(endpoint.split("/")[0], "ladder00" if endpoint.startswith("fraction100") else endpoint.split("/")[1])].subset_digest for endpoint in ENDPOINTS}, "subset_nesting_verified": bool(subset_nesting), "subset_nesting_by_ladder": subset_nesting_by_ladder, "fold_partition": {"held": held_fold, "stopping": stopping_fold, "discovery": sorted(discovery_folds), "replay": sorted(nonheld_folds)}, "array_shapes": {name: list(value.shape) for name, value in sorted(arrays.items())}, "array_digests": inventory, "auxiliary_audit": {"target_excluded": True, "held_fold_excluded": True, "pseudoabsence_rows": 0, "unknown_rows": 0, "species_set": list(range(7)), "equal_species_weighting": "exact_equal_species_contribution", "species_counts": aux_counts, "species_weight_totals": {str(index): aux_total for index in range(7)}}, "privacy": {"labels_private": True, "row_identifiers": False, "coordinates": False, "outer_attempted": 0, "outer_opened": 0}, "outer_attempted": 0, "outer_opened": 0}
            metadata["bundle_digest"] = digest_value({"metadata": metadata, "arrays": inventory})
            payload = {**arrays, "metadata_json": np.frombuffer(canonical(metadata), dtype=np.uint8)}
            output_path = output_root / f"{target}--{held_fold}.npz"; temporary = output_path.with_suffix(".tmp.npz"); np.savez_compressed(temporary, **payload); temporary.replace(output_path); written.append(output_path)
    return written


def validate_canary(config: FinalInnerConfig) -> dict[str, Any]:
    path = config.canary_receipt
    _require(path.is_file(), "canary receipt missing")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    expected_keys = {"schema_version", "success", "decision", "config_digest", "corrected_winner", "target", "held_fold", "bundle_inventory_digest", "sentinel_bundle_digest", "source_fingerprint", "runtime", "runtime_digest", "counts", "repeat_a_content_digest", "repeat_b_content_digest", "prediction_digest", "artifact_digest", "deterministic_evidence_digest", "gates", "outer_attempted", "outer_opened"}
    _require(set(receipt) == expected_keys, "canary receipt schema drift")
    _require(receipt["schema_version"] == "goal035-final-inner-canary-v1" and receipt["success"] is True and receipt["decision"] == "pass", "canary decision gate failed")
    for key in ("config_digest", "bundle_inventory_digest", "sentinel_bundle_digest", "source_fingerprint", "runtime_digest", "repeat_a_content_digest", "repeat_b_content_digest", "prediction_digest", "artifact_digest", "deterministic_evidence_digest"):
        _require(isinstance(receipt[key], str) and len(receipt[key]) == 64 and all(char in "0123456789abcdef" for char in receipt[key]), f"canary digest format drift: {key}")
    bundles = validate_bundle_inventory(config.private_root, config=config)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00")
    current_runtime = runtime_attestation(config, strict=True)
    _require(receipt["config_digest"] == config.config_digest and receipt["corrected_winner"] == config.corrected_winner and receipt["source_fingerprint"] == config.source_fingerprint and receipt["target"] == sentinel.target and receipt["held_fold"] == sentinel.held_fold, "canary binding drift")
    _require(receipt["bundle_inventory_digest"] == _bundle_inventory_digest(bundles) and receipt["sentinel_bundle_digest"] == sentinel.source_digest, "canary bundle drift")
    _require(receipt["runtime"] == current_runtime and receipt["runtime_digest"] == digest_value(current_runtime), "canary runtime drift")
    _require(receipt["counts"].get("logical_artifacts") == 221 and receipt["counts"].get("physical_fits") in {441, 442} and receipt["gates"] == {"transfer": True, "reset": True, "frozen_trunk": True, "q_initial": True, "outer": True} and receipt["outer_attempted"] == receipt["outer_opened"] == 0, "canary arithmetic/gate drift")
    repeat_root = config.private_root / "canary_repeats"
    prepared = prepare_case(sentinel)
    expected_identity = {"target": sentinel.target, "held_fold": sentinel.held_fold, "held_row_count": int(len(sentinel.arrays["x_held"])), "bundle_digest": sentinel.source_digest, "config_digest": config.config_digest, "runtime_digest": digest_value(current_runtime), "architecture": config.corrected_winner, "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}
    expected_leaf = leaf_identity(expected_identity)
    repeat_paths = [repeat_root / "repeat_a" / expected_leaf, repeat_root / "repeat_b" / expected_leaf]
    _require(all(path.is_dir() for path in repeat_paths), "canary private repeat leaves missing")
    identities = [json.loads((path / "metadata.json").read_text(encoding="utf-8"))["identity"] for path in repeat_paths]
    for identity in identities:
        _require(identity["target"] == sentinel.target and identity["held_fold"] == sentinel.held_fold and identity["bundle_digest"] == sentinel.source_digest and identity["config_digest"] == config.config_digest and identity["runtime_digest"] == digest_value(current_runtime), "canary repeat identity drift")
    metadata_a = validate_leaf(repeat_paths[0], identities[0]); metadata_b = validate_leaf(repeat_paths[1], identities[1])
    pred_a = np.load(repeat_paths[0] / "predictions.npy", allow_pickle=False); pred_b = np.load(repeat_paths[1] / "predictions.npy", allow_pickle=False)
    _require(np.array_equal(pred_a, pred_b) and _without_wall(metadata_a) == _without_wall(metadata_b), "canary repeat evidence drift")
    _require(receipt["counts"] == metadata_a["counts"] == metadata_b["counts"], "canary count evidence drift")
    _require(receipt["repeat_a_content_digest"] == _leaf_content_digest(repeat_paths[0]) and receipt["repeat_b_content_digest"] == _leaf_content_digest(repeat_paths[1]), "canary repeat content drift")
    fields = ("artifact_id", "selected_epoch", "discovery_executed_epochs", "replay_epochs", "stopping_status", "initial_model_digest", "replay_initial_model_digest", "initial_shared_digest", "final_shared_digest", "initial_head_digest", "model_digest", "prediction_digest", "n_iter", "primary_n_iter", "termination_status", "stability_accepted", "stability_probability_delta", "fit_seed", "runtime_digest")
    artifact_rows = [tuple(item.get(field) for field in fields) for item in metadata_a["artifacts"]]
    _require(receipt["prediction_digest"] == array_digest(pred_a) and receipt["artifact_digest"] == digest_value(artifact_rows) and receipt["deterministic_evidence_digest"] == digest_value(_without_wall(metadata_a)), "canary deterministic digest drift")
    return receipt


def run_all(config: FinalInnerConfig, bundle_root: str | Path, leaf_root: str | Path) -> dict[str, Any]:
    validate_canary(config)
    bundles = validate_bundle_inventory(bundle_root, config=config)
    bundle_paths = {(load_case_npz(path).target, load_case_npz(path).held_fold): path for path in Path(bundle_root).glob("*.npz")}
    root = Path(leaf_root); complete = invalid = 0; tasks: list[dict[str, Any]] = []
    for bundle in bundles:
        prepared = prepare_case(bundle)
        identity = {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": config.config_digest, "runtime_digest": digest_value(runtime_attestation(config, strict=True)), "architecture": config.corrected_winner, "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}
        path = root / leaf_identity(identity)
        if path.exists():
            try:
                validate_leaf(path, identity); complete += 1; continue
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                raise FinalInnerRunError(f"corrupt existing leaf rejected before scheduling: {path}")
        _require((bundle.target, bundle.held_fold) in bundle_paths, "bundle path inventory drift")
        tasks.append({"config_path": str(config.source_path), "bundle_path": str(bundle_paths[(bundle.target, bundle.held_fold)]), "leaf_root": str(root)})
    if tasks:
        # Each task is an independent case leaf; spawn exactly the authorised
        # three Mac CPU workers and let atomic leaf resume handle retries.
        with ProcessPoolExecutor(max_workers=3, mp_context=mp.get_context("spawn")) as pool:
            for _ in pool.map(_run_case_worker, tasks):
                complete += 1
    return {"cases_expected": 40, "cases_complete": complete, "cases_invalid": invalid, "logical_artifacts": 8840, "physical_fits_minimum": 17640, "physical_fits_maximum": 17680, "workers": 3, "outer_attempted": 0, "outer_opened": 0}


def status(config: FinalInnerConfig, bundle_root: str | Path, leaf_root: str | Path) -> dict[str, Any]:
    runtime_attestation(config, strict=True)
    bundles = validate_bundle_inventory(bundle_root, config=config); complete = invalid = 0
    for bundle in bundles:
        prepared = prepare_case(bundle)
        identity = {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": config.config_digest, "runtime_digest": digest_value(runtime_attestation(config, strict=True)), "architecture": config.corrected_winner, "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}
        path = Path(leaf_root) / leaf_identity(identity)
        if not path.exists(): continue
        try: validate_leaf(path, identity); complete += 1
        except (OSError, ValueError, KeyError, json.JSONDecodeError): invalid += 1
    return {"cases_expected": 40, "cases_complete": complete, "cases_invalid": invalid, "cases_missing": 40 - complete - invalid, "outer_attempted": 0, "outer_opened": 0}


def aggregate(config: FinalInnerConfig, bundle_root: str | Path, leaf_root: str | Path) -> dict[str, Any]:
    runtime_attestation(config, strict=True)
    validate_canary(config)
    bundles = validate_bundle_inventory(bundle_root, config=config); inventory: list[str] = []
    content_inventory: list[str] = []; mask_inventory: list[str] = []
    physical_fits = 0
    for bundle in bundles:
        prepared = prepare_case(bundle)
        identity = {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": config.config_digest, "runtime_digest": digest_value(runtime_attestation(config, strict=True)), "architecture": config.corrected_winner, "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}
        path = Path(leaf_root) / leaf_identity(identity); metadata = validate_leaf(path, identity)
        inventory.append(leaf_identity(identity)); mask_inventory.append(identity["mask_digest"] + identity["aux_mask_digest"])
        predictions = np.load(path / "predictions.npy", allow_pickle=False)
        content_inventory.append(digest_value({"identity": identity, "metadata": metadata, "predictions": array_digest(predictions)}))
        physical_fits += int(metadata["counts"]["physical_fits"])
    runtime = runtime_attestation(config, strict=True)
    canary_digest = digest_bytes(config.canary_receipt.read_bytes())
    _require(17640 <= physical_fits <= 17680, "aggregate physical-fit arithmetic drift")
    return {"schema_version": "goal035-final-inner-aggregate-v1", "success": True, "corrected_winner": config.corrected_winner, "config_digest": config.config_digest, "authority_digests": dict(config.authority_digests), "source_digests": dict(config.source_digests), "source_fingerprint": config.source_fingerprint, "runtime": runtime, "runtime_digest": digest_value(runtime), "canary_receipt_digest": canary_digest, "bundle_inventory_digest": _bundle_inventory_digest(bundles), "mask_inventory_digest": digest_value(sorted(mask_inventory)), "leaf_inventory_digest": digest_value(sorted(inventory)), "leaf_content_inventory_digest": digest_value(sorted(content_inventory)), "cases": 40, "logical_artifacts": 8840, "physical_fits": physical_fits, "stability_extension_fits": physical_fits - 17640, "workers": 3, "outer_attempted": 0, "outer_opened": 0}


def finalize(config: FinalInnerConfig, bundle_root: str | Path, leaf_root: str | Path, output: str | Path) -> dict[str, Any]:
    receipt = aggregate(config, bundle_root, leaf_root)
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_text(canonical(receipt).decode() + "\n", encoding="utf-8"); temporary.replace(path)
    return receipt


def validate(config: FinalInnerConfig, bundle_root: str | Path, leaf_root: str | Path, aggregate_path: str | Path) -> dict[str, Any]:
    expected = aggregate(config, bundle_root, leaf_root)
    actual = json.loads(Path(aggregate_path).read_text(encoding="utf-8")); _require(actual == expected, "aggregate receipt mismatch")
    return actual


def _write_json(value: Mapping[str, Any], path: str | Path | None) -> None:
    payload = canonical(dict(value)).decode() + "\n"
    if path is None: print(payload, end=""); return
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True); temporary = target.with_suffix(target.suffix + ".tmp"); temporary.write_text(payload, encoding="utf-8"); temporary.replace(target)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.final_inner_runner")
    parser.add_argument("--config", default="config/dsdm_final_inner_lifecycle.json")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "validate-bundles", "canary", "run", "status", "finalize", "validate", "export"):
        commands.add_parser(name)
    parser_args = parser.parse_args(argv); source = Path(parser_args.config).resolve(); root = source.parents[1]
    config = load_config(source, root=root, require_receipt=parser_args.command not in {"plan", "validate-bundles"})
    if parser_args.command == "plan":
        _write_json({"schema_version": "goal035-final-inner-plan-v1", "goal_id": config.raw["goal_id"], "config_digest": config.config_digest, "cases": 40, "logical_artifacts": 8840, "physical_fits_minimum": 17640, "physical_fits_maximum": 17680, "workers": 3, "outer_attempted": 0, "outer_opened": 0}, None); return 0
    if parser_args.command == "validate-bundles":
        _write_json({"bundles": len(validate_bundle_inventory(config.private_root, config=config)), "outer_attempted": 0, "outer_opened": 0}, None); return 0
    if parser_args.command == "canary":
        runtime_attestation(config, strict=True); _write_json(canary(config, config.private_root, config.canary_receipt), None); return 0
    if parser_args.command == "export":
        runtime_attestation(config, strict=True); _write_json({"bundles": len(export_from_foundation(config, root=root, output=config.private_root)), "outer_attempted": 0, "outer_opened": 0}, None); return 0
    if parser_args.command == "run":
        runtime_attestation(config, strict=True); _write_json(run_all(config, config.private_root, config.private_root / "leaves"), None); return 0
    if parser_args.command == "status":
        _write_json(status(config, config.private_root, config.private_root / "leaves"), None); return 0
    if parser_args.command == "finalize":
        _write_json(finalize(config, config.private_root, config.private_root / "leaves", config.tracked_root / "aggregate.json"), None); return 0
    _write_json(validate(config, config.private_root, config.private_root / "leaves", config.tracked_root / "aggregate.json"), None); return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["aggregate", "canary", "finalize", "main", "run_all", "run_case", "status", "validate", "validate_canary"]
