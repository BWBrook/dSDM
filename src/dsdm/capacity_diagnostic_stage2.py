"""Conditional Goal038 Stage2 runner for the sole frozen ``wide512`` candidate."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np

from .contracts import ENDPOINTS, FOLDS, METHODS, SPECIES


class Stage2Error(ValueError):
    pass


SEEDS = (31031, 31032, 31033, 31034, 31035)
METHODS_STAGE2 = tuple(METHODS)
CANDIDATE = "wide512"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def source_fingerprint(config: Stage2Config) -> str:
    return digest_value(sorted((name, binding["path"], binding["sha256"]) for name, binding in config.raw["execution_sources"].items()))


def file_digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Stage2Error(message)


class Stage2Config:
    def __init__(self, source_path: Path, root: Path, raw: Mapping[str, Any]):
        self.source_path, self.root, self.raw = source_path, root, raw
        self.config_digest = file_digest(source_path)

    @property
    def private_root(self) -> Path:
        return self.root / self.raw["evidence"]["private_root"]

    @property
    def tracked_root(self) -> Path:
        return self.root / self.raw["evidence"]["tracked_root"]

    @property
    def canary_receipt(self) -> Path:
        return self.root / self.raw["evidence"]["canary_receipt"]


def build_plan() -> dict[str, int]:
    return {"atomic_cases": 40, "logical_artifacts": 8840, "physical_fits_minimum": 17640, "physical_fits_maximum": 17680, "workers": 3}


def load_config(path: str | Path, *, root: str | Path | None = None) -> Stage2Config:
    source = Path(path).resolve(); raw = json.loads(source.read_text(encoding="utf-8")); project_root = Path(root).resolve() if root is not None else source.parents[1]
    _require(set(raw) == {"schema_version", "goal_id", "candidate", "authorities", "execution_sources", "scope", "architecture", "training", "execution", "confirmation", "evidence", "runtime"}, "Stage2 config keys drift")
    _require(raw["schema_version"] == "1.0" and raw["goal_id"] == "goal038-dsdm-capacity-diagnostic-stage2" and raw["candidate"] == CANDIDATE, "Stage2 identity/candidate drift")
    _require(set(raw["authorities"]) == {"stage1_aggregate", "stage1_canary", "goal035_config", "goal035_aggregate", "goal036_decision", "goal036_summary", "goal037_config", "goal037_decision"}, "Stage2 authority key set drift")
    _require(set(raw["execution_sources"]) == {"capacity_diagnostic_stage2", "contracts", "final_inner_data", "final_inner_runner", "inner_evaluation", "models", "real_six_path", "uv_lock"}, "Stage2 source key set drift")
    for group in ("authorities", "execution_sources"):
        for name, binding in raw[group].items():
            _require(set(binding) == {"path", "sha256"} and not Path(binding["path"]).is_absolute() and ".." not in Path(binding["path"]).parts, f"binding drift: {name}")
            target = project_root / binding["path"]; _require(target.is_file(), f"binding missing: {name}")
            if binding["sha256"]: _require(file_digest(target) == binding["sha256"], f"binding digest mismatch: {name}")
    stage1 = json.loads((project_root / raw["authorities"]["stage1_aggregate"]["path"]).read_text(encoding="utf-8"))
    _require(stage1.get("decision") == "advance_stage2" and stage1.get("eligible_ranking", [{}])[0].get("variant") == "wide512" and stage1.get("outer_attempted") == stage1.get("outer_opened") == 0, "Stage1 advance gate failed")
    _require(raw["scope"] == {"fractions": list(ENDPOINTS), "seeds": list(SEEDS), "species": 8, "folds": 5, "methods": list(METHODS)}, "Stage2 scope drift")
    _require(raw["architecture"] == {"id": "wide512", "blocks": 3, "width": 512, "bottleneck": 128, "shape": "constant", "dropout": 0.0, "weight_decay": 0.001, "parameter_count": 439681}, "Stage2 architecture drift")
    _require(raw["training"] == {"dtype": "float32", "device": "cpu", "threads": 1, "blas_threads": 1, "optimizer": "AdamW", "learning_rate": 0.001, "batch_size": 128, "max_epochs": 300, "patience": 30}, "Stage2 training drift")
    _require(raw["execution"] == {**build_plan(), "outer_attempted": 0, "outer_opened": 0}, "Stage2 arithmetic drift")
    _require(raw["confirmation"] == {"endpoints": ["fraction25/ladder01", "fraction25/ladder02", "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02"], "seeds": [31034, 31035], "median_species_d_auc_positive_endpoints_min": 4, "species_five_endpoint_mean_positive_min": 5, "fresh_seed_species_balanced_d_auc_positive_min": 2, "aggregate_d_tss_min": 0, "aggregate_d_tss_rule": "equal_species_mean_of_equal_endpoint_mean"}, "Stage2 confirmation drift")
    _require(raw["runtime"] == {"system": "Darwin", "machine": "arm64", "python_major_minor": "3.12", "numpy": "2.2.6", "scipy": "1.16.3", "scikit_learn": "1.9.0", "threadpoolctl": "3.6.0", "torch": "2.7.1", "device": "cpu", "route": "mac_cpu", "threads": 1, "blas_threads": 1}, "Stage2 runtime drift")
    _require(raw["evidence"]["aggregate_only"] is True and raw["evidence"]["outer_attempted"] == raw["evidence"]["outer_opened"] == 0, "Stage2 evidence drift")
    return Stage2Config(source, project_root, raw)


def confirmation_gate(metrics: Mapping[str, Any]) -> bool:
    return (int(metrics["median_species_d_auc_positive_endpoints"]) >= 4 and int(metrics["species_five_endpoint_mean_positive"]) >= 5 and int(metrics["fresh_seed_species_balanced_d_auc_positive"]) >= 2 and float(metrics["aggregate_d_tss"]) >= 0)


def fresh_seed_positive_count(seed_species_values: Mapping[int, Sequence[float]], fresh_seeds: Sequence[int] = (31034, 31035)) -> int:
    """Count positive species-balanced interactions for fresh seeds only."""
    return sum(float(np.mean(seed_species_values[seed])) > 0 for seed in fresh_seeds)


def positive_species_count(species_means: Mapping[str, float]) -> int:
    """Count positive species means from the aggregate-only mapping."""
    return sum(float(value) > 0 for value in species_means.values())


def _receipt_metric_values(metrics: Mapping[str, Any]) -> dict[str, float | None]:
    """Map Goal036 metric names into the Stage2 receipt schema."""
    return {"auc": None if metrics.get("roc_auc") is None else float(metrics["roc_auc"]), "tss": None if metrics.get("tss") is None else float(metrics["tss"]), "mcc": None if metrics.get("mcc") is None else float(metrics["mcc"])}


def _stage1_context(config: Stage2Config):
    from .final_inner_data import load_config as load_goal035_config, validate_bundle_inventory
    goal035 = load_goal035_config(config.root / config.raw["authorities"]["goal035_config"]["path"])
    bundles = validate_bundle_inventory(goal035.private_root, config=goal035)
    return goal035, bundles


def _stage_config(config: Stage2Config, goal035: Any) -> Any:
    """Use the sealed Goal035 lifecycle with a Stage2 provenance digest."""
    return replace(goal035, corrected_winner=CANDIDATE, config_digest=config.config_digest)


def _identity(config: Stage2Config, goal035: Any, bundle: Any) -> dict[str, Any]:
    from .final_inner_data import prepare_case, runtime_attestation
    prepared = prepare_case(bundle)
    runtime = runtime_attestation(goal035, strict=True)
    return {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": config.config_digest, "runtime_digest": digest_value(runtime), "architecture": CANDIDATE, "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}


def _leaf_path(config: Stage2Config, identity: Mapping[str, Any]) -> Path:
    from .final_inner_data import leaf_identity
    return config.private_root / "leaves" / leaf_identity(identity)


def _run_case_worker(task: Mapping[str, Any]) -> str:
    from .final_inner_data import load_case_npz, validate_case_binding
    from . import final_inner_runner as runner
    config = load_config(task["config_path"]); goal035, _ = _stage1_context(config); bundle = load_case_npz(task["bundle_path"]); validate_case_binding(bundle, goal035)
    if not any(row[0] == CANDIDATE for row in runner.ARCHITECTURES):
        runner.ARCHITECTURES = tuple(runner.ARCHITECTURES) + ((CANDIDATE, 3, 512, 128, "constant", 0.0, 0.001),)
    stage_config = _stage_config(config, goal035)
    identity = _identity(config, goal035, bundle)
    predictions, metadata = runner._case_lifecycle(bundle, stage_config, device="cpu")
    from .final_inner_data import write_leaf
    output = write_leaf(config.private_root / "leaves", identity, predictions, metadata)
    return str(output)


def validate_leaf(path: Path, identity: Mapping[str, Any]) -> np.ndarray:
    from .final_inner_data import validate_leaf as validate_goal035_leaf, leaf_identity
    validate_goal035_leaf(path, identity)
    return np.load(path / "predictions.npy", allow_pickle=False)


def status(config: Stage2Config) -> dict[str, Any]:
    goal035, bundles = _stage1_context(config); complete = invalid = 0
    for bundle in bundles:
        identity = _identity(config, goal035, bundle); path = _leaf_path(config, identity)
        if not path.exists(): continue
        try: validate_leaf(path, identity); complete += 1
        except (OSError, ValueError, KeyError, json.JSONDecodeError): invalid += 1
    return {**build_plan(), "completed_cases": complete, "missing_cases": 40 - complete - invalid, "invalid_cases": invalid, "outer_attempted": 0, "outer_opened": 0}


def canary(config: Stage2Config) -> dict[str, Any]:
    from . import final_inner_runner as runner
    from .final_inner_data import load_case_npz, prepare_case, validate_case_binding, validate_leaf as validate_goal035_leaf, write_leaf, runtime_attestation
    _require(config.raw["candidate"] == CANDIDATE, "Stage2 canary candidate drift")
    goal035, bundles = _stage1_context(config)
    sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00")
    validate_case_binding(sentinel, goal035)
    if not any(row[0] == CANDIDATE for row in runner.ARCHITECTURES):
        runner.ARCHITECTURES = tuple(runner.ARCHITECTURES) + ((CANDIDATE, 3, 512, 128, "constant", 0.0, 0.001),)
    stage_config = _stage_config(config, goal035); identity = _identity(config, goal035, sentinel)
    repeat_paths = []
    for label in ("repeat_a", "repeat_b"):
        predictions, metadata = runner._case_lifecycle(sentinel, stage_config, device="cpu", max_epochs=1, patience=1)
        repeat_paths.append(write_leaf(config.private_root / "canary_repeats" / label, identity, predictions, metadata))
    first = np.load(repeat_paths[0] / "predictions.npy", allow_pickle=False); second = np.load(repeat_paths[1] / "predictions.npy", allow_pickle=False)
    _require(np.array_equal(first, second), "Stage2 canary repeat predictions differ")
    meta_a = json.loads((repeat_paths[0] / "metadata.json").read_text(encoding="utf-8")); meta_b = json.loads((repeat_paths[1] / "metadata.json").read_text(encoding="utf-8"))
    def strip_wall(value: Any) -> Any:
        if isinstance(value, dict): return {key: strip_wall(item) for key, item in value.items() if key != "wall_seconds"}
        if isinstance(value, list): return [strip_wall(item) for item in value]
        return value
    _require(strip_wall(meta_a) == strip_wall(meta_b), "Stage2 canary deterministic metadata differs")
    counts = meta_a["counts"]; _require(len(meta_a["artifacts"]) == 221 and counts["physical_fits"] in {441, 442}, "Stage2 canary arithmetic drift")
    runtime = runtime_attestation(goal035, strict=True)
    receipt = {"schema_version": "goal038-stage2-canary-v1", "success": True, "decision": "pass", "candidate": CANDIDATE, "config_digest": config.config_digest, "source_fingerprint": source_fingerprint(config), "goal035_config_digest": goal035.config_digest, "runtime": runtime, "runtime_digest": digest_value(runtime), "target": sentinel.target, "held_fold": sentinel.held_fold, "sentinel_bundle_digest": sentinel.source_digest, "counts": counts, "repeat_a_content_digest": file_digest(repeat_paths[0] / "metadata.json"), "repeat_b_content_digest": file_digest(repeat_paths[1] / "metadata.json"), "prediction_digest": hashlib.sha256(np.ascontiguousarray(first).tobytes()).hexdigest(), "deterministic": True, "finite": bool(np.isfinite(first).all()), "gates": {"transfer": True, "reset": True, "frozen_trunk": True, "q_initial": True, "outer": True}, "outer_attempted": 0, "outer_opened": 0}
    receipt["receipt_digest"] = digest_value(receipt); config.canary_receipt.parent.mkdir(parents=True, exist_ok=True); config.canary_receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"); return receipt


def validate_canary(config: Stage2Config) -> dict[str, Any]:
    from .final_inner_data import validate_leaf as validate_goal035_leaf, leaf_identity
    _require(config.canary_receipt.is_file(), "Stage2 canary missing"); value = json.loads(config.canary_receipt.read_text(encoding="utf-8")); _require(value.get("success") is True and value.get("decision") == "pass" and value.get("candidate") == CANDIDATE and value.get("config_digest") == config.config_digest and value.get("source_fingerprint") == source_fingerprint(config) and value.get("deterministic") is True and value.get("finite") is True and value.get("outer_attempted") == value.get("outer_opened") == 0, "Stage2 canary gate failed"); _require(value.get("receipt_digest") == digest_value({key: item for key, item in value.items() if key != "receipt_digest"}), "Stage2 canary receipt digest drift")
    goal035, bundles = _stage1_context(config); sentinel = next(bundle for bundle in bundles if bundle.target == value.get("target") and bundle.held_fold == value.get("held_fold")); identity = _identity(config, goal035, sentinel)
    paths = [config.private_root / "canary_repeats" / label / leaf_identity(identity) for label in ("repeat_a", "repeat_b")]
    for path in paths: validate_goal035_leaf(path, identity)
    meta = [json.loads((path / "metadata.json").read_text(encoding="utf-8")) for path in paths]
    pred = [np.load(path / "predictions.npy", allow_pickle=False) for path in paths]
    strip_wall = lambda x: ({k: strip_wall(v) for k, v in x.items() if k != "wall_seconds"} if isinstance(x, dict) else [strip_wall(v) for v in x] if isinstance(x, list) else x)
    _require(np.array_equal(pred[0], pred[1]) and strip_wall(meta[0]) == strip_wall(meta[1]), "Stage2 canary repeat reconstruction drift")
    _require(value.get("counts") == meta[0].get("counts") and value.get("counts", {}).get("logical_artifacts") == 221 and value.get("counts", {}).get("physical_fits") in {441, 442}, "Stage2 canary counts drift")
    _require(value.get("prediction_digest") == hashlib.sha256(np.ascontiguousarray(pred[0]).tobytes()).hexdigest(), "Stage2 canary prediction digest drift")
    _require(value.get("repeat_a_content_digest") == file_digest(paths[0] / "metadata.json") and value.get("repeat_b_content_digest") == file_digest(paths[1] / "metadata.json"), "Stage2 canary content digest drift")
    _require(value.get("runtime_digest") == digest_value(meta[0]["runtime"]) and value.get("gates") == {"transfer": True, "reset": True, "frozen_trunk": True, "q_initial": True, "outer": True}, "Stage2 canary substantive gates drift")
    return value


def run_stage2(config: Stage2Config) -> dict[str, Any]:
    validate_canary(config); goal035, bundles = _stage1_context(config); tasks = []
    for bundle in bundles:
        identity = _identity(config, goal035, bundle); path = _leaf_path(config, identity)
        if path.exists(): validate_leaf(path, identity); continue
        private = goal035.private_root / f"{bundle.target}--{bundle.held_fold}.npz"
        tasks.append({"config_path": str(config.source_path), "bundle_path": str(private), "leaf_path": str(path)})
    if tasks:
        with ProcessPoolExecutor(max_workers=3, mp_context=mp.get_context("spawn")) as pool: list(pool.map(_run_case_worker, tasks))
    return status(config)


def _confirmation_metrics(config: Stage2Config, goal035: Any, bundles: Sequence[Any], identities: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Reconstruct confirmation metrics from validated Stage2 and Goal035 leaves."""
    from .inner_evaluation import binary_metrics, select_threshold
    from .final_inner_data import leaf_identity, prepare_case, validate_leaf as validate_goal035_leaf, runtime_attestation
    endpoints = tuple(config.raw["confirmation"]["endpoints"]); method_names = tuple(METHODS)
    control_root = goal035.private_root / "leaves"
    records: dict[str, dict[tuple[str, str], np.ndarray]] = {"control": {}, CANDIDATE: {}}
    ys: dict[tuple[str, str], np.ndarray] = {}
    for bundle, identity in zip(bundles, identities):
        ys[(bundle.target, bundle.held_fold)] = np.asarray(bundle.arrays["y_held"], dtype=np.int8)
        stage_values = validate_leaf(_leaf_path(config, identity), identity)
        records[CANDIDATE][(bundle.target, bundle.held_fold)] = stage_values
        prepared = prepare_case(bundle)
        control_identity = {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": goal035.config_digest, "runtime_digest": digest_value(runtime_attestation(goal035, strict=True)), "architecture": "resmlp13", "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}
        control_path = control_root / leaf_identity(control_identity); validate_goal035_leaf(control_path, control_identity)
        records["control"][(bundle.target, bundle.held_fold)] = np.load(control_path / "predictions.npy", allow_pickle=False)
    fresh_indices = [SEEDS.index(seed) for seed in config.raw["confirmation"]["seeds"]]
    thresholds: dict[tuple[str, str, str, str], float] = {}
    for architecture in ("control", CANDIDATE):
        for species in SPECIES:
            for endpoint in ENDPOINTS:
                ei = ENDPOINTS.index(endpoint)
                for method in method_names:
                    mi = method_names.index(method); pooled_y=[]; pooled_s=[]
                    for fold in FOLDS:
                        key = (species, fold)
                        if key in records[architecture]:
                            pooled_y.extend(ys[key]); pooled_s.extend(np.mean(records[architecture][key][fresh_indices, ei, mi, :], axis=0))
                    thresholds[(architecture, species, endpoint, method)] = select_threshold(pooled_y, pooled_s)[0]
    d_auc_by_endpoint: dict[str, list[float]] = {endpoint: [] for endpoint in endpoints}; d_tss_values=[]; seed_positive={}
    for species in SPECIES:
        for endpoint in endpoints:
            ei = ENDPOINTS.index(endpoint)
            fold_metrics: dict[str, dict[str, list[dict[str, Any]]]] = {a: {m: [] for m in method_names} for a in ("control", CANDIDATE)}
            for architecture in ("control", CANDIDATE):
                for method in method_names:
                    mi = method_names.index(method)
                    for fold in FOLDS:
                        key=(species, fold)
                        if key not in records[architecture]: continue
                        score=np.mean(records[architecture][key][fresh_indices, ei, mi, :], axis=0); met=binary_metrics(ys[key], score, thresholds[(architecture,species,endpoint,method)]); fold_metrics[architecture][method].append(met)
            c_lift=float(np.mean([m["roc_auc"] for m in fold_metrics["control"]["multihead_full_finetune"]])-np.mean([m["roc_auc"] for m in fold_metrics["control"]["target_only_resmlp"]]))
            v_lift=float(np.mean([m["roc_auc"] for m in fold_metrics[CANDIDATE]["multihead_full_finetune"]])-np.mean([m["roc_auc"] for m in fold_metrics[CANDIDATE]["target_only_resmlp"]]))
            d_auc_by_endpoint[endpoint].append(v_lift-c_lift)
            c_tss=float(np.mean([m["tss"] for m in fold_metrics["control"]["multihead_full_finetune"]])-np.mean([m["tss"] for m in fold_metrics["control"]["target_only_resmlp"]]))
            v_tss=float(np.mean([m["tss"] for m in fold_metrics[CANDIDATE]["multihead_full_finetune"]])-np.mean([m["tss"] for m in fold_metrics[CANDIDATE]["target_only_resmlp"]]))
            d_tss_values.append(v_tss-c_tss)
    for seed in (31034, 31035):
        vals=[]
        for species in SPECIES:
            endpoint_vals=[]
            for endpoint in endpoints:
                ei=ENDPOINTS.index(endpoint); lifts=[]
                for architecture in ("control", CANDIDATE):
                    per_fold=[]
                    for fold in FOLDS:
                        key=(species,fold)
                        if key not in records[architecture]: continue
                        mi_t=method_names.index("target_only_resmlp"); mi_m=method_names.index("multihead_full_finetune"); y=ys[key]; t=records[architecture][key][SEEDS.index(seed),ei,mi_t]; m=records[architecture][key][SEEDS.index(seed),ei,mi_m]; per_fold.append(binary_metrics(y,m,thresholds[(architecture,species,endpoint,"multihead_full_finetune")])["roc_auc"]-binary_metrics(y,t,thresholds[(architecture,species,endpoint,"target_only_resmlp")])["roc_auc"])
                    lifts.append(float(np.mean(per_fold)))
                endpoint_vals.append(lifts[1]-lifts[0])
            vals.append(float(np.mean(endpoint_vals)))
        seed_positive[str(seed)] = float(np.mean(vals))
    median_positive=sum(float(np.median(values))>0 for values in d_auc_by_endpoint.values())
    species_five_endpoint_mean_d_auc = {species: float(np.mean([d_auc_by_endpoint[endpoint][index] for endpoint in endpoints])) for index, species in enumerate(SPECIES)}
    species_endpoint_positive=positive_species_count(species_five_endpoint_mean_d_auc)
    descriptive = {a: {m: {"auc": [], "tss": [], "mcc": []} for m in method_names} for a in ("control", CANDIDATE)}
    for architecture in descriptive:
        for species in SPECIES:
            for endpoint in ENDPOINTS:
                ei = ENDPOINTS.index(endpoint)
                for method in method_names:
                    mi = method_names.index(method); scores=[]; labels=[]
                    for fold in FOLDS:
                        key=(species, fold)
                        if key in records[architecture]:
                            score=np.mean(records[architecture][key][:,ei,mi,:],axis=0); scores.extend(score); labels.extend(ys[key])
                    if scores:
                        threshold=select_threshold(labels, scores)[0]; met=binary_metrics(labels,scores,threshold)
                        for receipt_metric, metric_value in _receipt_metric_values(met).items():
                            if metric_value is not None: descriptive[architecture][method][receipt_metric].append(metric_value)
    metrics={"median_species_d_auc_positive_endpoints": median_positive, "species_five_endpoint_mean_positive": species_endpoint_positive, "species_five_endpoint_mean_d_auc": species_five_endpoint_mean_d_auc, "fresh_seed_species_balanced_d_auc_positive": fresh_seed_positive_count({int(k): [v] for k,v in seed_positive.items()}), "aggregate_d_tss": float(np.mean(d_tss_values)), "aggregate_d_tss_rule": config.raw["confirmation"]["aggregate_d_tss_rule"], "d_auc_by_endpoint": {k: float(np.median(v)) for k,v in d_auc_by_endpoint.items()}, "fresh_seed_species_balanced_d_auc": seed_positive, "method_summaries": {a: {m: {metric: float(np.mean(values)) if values else None for metric, values in descriptive[a][m].items()} for m in method_names} for a in descriptive}}
    metrics["gate"] = confirmation_gate(metrics); return metrics


def finalize(config: Stage2Config) -> dict[str, Any]:
    validate_canary(config); current = status(config); _require(current["missing_cases"] == current["invalid_cases"] == 0, "Stage2 inventory incomplete")
    goal035, bundles = _stage1_context(config); identities = [_identity(config, goal035, bundle) for bundle in bundles]; contents = []; metadata_contents = []; physical_fits = 0
    for identity in identities:
        path = _leaf_path(config, identity); values = validate_leaf(path, identity); metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8")); contents.append(digest_value({"identity": identity, "prediction_digest": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()})); metadata_contents.append(digest_value(metadata)); physical_fits += int(metadata["counts"]["physical_fits"])
    confirmation = _confirmation_metrics(config, goal035, bundles, identities)
    canary_digest = file_digest(config.canary_receipt); decision = "pass" if confirmation["gate"] else "stop_no_confirmation"
    receipt = {"schema_version": "goal038-stage2-aggregate-v1", "success": True, "candidate": CANDIDATE, "decision": decision, "config_digest": config.config_digest, "source_fingerprint": source_fingerprint(config), "runtime": config.raw["runtime"], "canary_receipt_digest": canary_digest, "authority_digests": {name: binding["sha256"] for name, binding in sorted(config.raw["authorities"].items())}, "execution_source_digests": {name: binding["sha256"] for name, binding in sorted(config.raw["execution_sources"].items())}, **build_plan(), "physical_fits_actual": physical_fits, "leaf_inventory_digest": digest_value(sorted(digest_value(item) for item in identities)), "leaf_content_inventory_digest": digest_value(sorted(contents)), "leaf_metadata_content_digest": digest_value(sorted(metadata_contents)), "confirmation": confirmation, "outer_attempted": 0, "outer_opened": 0}; receipt["receipt_digest"] = digest_value(receipt)
    config.tracked_root.mkdir(parents=True, exist_ok=True); output = config.tracked_root / "aggregate.json"; temporary = output.with_suffix(".json.tmp"); temporary.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"); temporary.replace(output); return receipt


def validate(config: Stage2Config) -> dict[str, Any]:
    path = config.tracked_root / "aggregate.json"; _require(path.is_file(), "Stage2 aggregate missing"); value = json.loads(path.read_text(encoding="utf-8")); _require(value.get("config_digest") == config.config_digest and value.get("outer_attempted") == value.get("outer_opened") == 0, "Stage2 aggregate identity drift"); _require(value.get("receipt_digest") == digest_value({key: item for key, item in value.items() if key != "receipt_digest"}), "Stage2 aggregate receipt digest drift"); goal035, bundles = _stage1_context(config); identities = [_identity(config, goal035, bundle) for bundle in bundles]; _require(value.get("leaf_inventory_digest") == digest_value(sorted(digest_value(item) for item in identities)), "Stage2 aggregate identity inventory drift"); contents=[]; metadata_contents=[]; physical_fits=0
    for identity in identities:
        leaf_path = _leaf_path(config, identity); values=validate_leaf(leaf_path, identity); metadata=json.loads((leaf_path / "metadata.json").read_text(encoding="utf-8")); contents.append(digest_value({"identity": identity, "prediction_digest": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()})); metadata_contents.append(digest_value(metadata)); physical_fits += int(metadata["counts"]["physical_fits"])
    _require(value.get("leaf_content_inventory_digest") == digest_value(sorted(contents)) and value.get("leaf_metadata_content_digest") == digest_value(sorted(metadata_contents)), "Stage2 aggregate content inventory drift"); _require(value.get("physical_fits_actual") == physical_fits and 17640 <= physical_fits <= 17680, "Stage2 aggregate physical-fit reconstruction drift"); _require(value.get("source_fingerprint") == source_fingerprint(config) and value.get("authority_digests") == {name: binding["sha256"] for name, binding in sorted(config.raw["authorities"].items())} and value.get("execution_source_digests") == {name: binding["sha256"] for name, binding in sorted(config.raw["execution_sources"].items())} and value.get("runtime") == config.raw["runtime"] and value.get("canary_receipt_digest") == file_digest(config.canary_receipt), "Stage2 aggregate provenance drift"); expected_confirmation = _confirmation_metrics(config, goal035, bundles, identities); _require(value.get("confirmation") == expected_confirmation and value.get("decision") == ("pass" if expected_confirmation["gate"] else "stop_no_confirmation"), "Stage2 aggregate confirmation reconstruction drift"); return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("plan", "canary", "run", "status", "finalize", "validate")); parser.add_argument("--config", default="config/dsdm_capacity_diagnostic_stage2.json"); args = parser.parse_args(argv); config = load_config(args.config)
    result = {"plan": lambda: build_plan(), "canary": lambda: canary(config), "run": lambda: run_stage2(config), "status": lambda: status(config), "finalize": lambda: finalize(config), "validate": lambda: validate(config)}[args.command]()
    print(json.dumps(result, sort_keys=True, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
