"""Goal039 response-blind predictor-substrate sensitivity.

This module keeps the scientific boundary deliberately narrow.  Predictor
masks are selected from the canonical map and fold assignment tables only;
the neural runner preserves the Goal035 77-column input and fit lifecycle by
zeroing excluded continuous columns.  Private leaves are resumable, while
tracked receipts contain aggregate provenance only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import rankdata

from .contracts import ENDPOINTS, FOLDS, METHODS, SPECIES
from .inner_evaluation import binary_metrics, select_threshold


class PredictorSensitivityError(ValueError):
    """Raised when the Goal039 contract or evidence is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PredictorSensitivityError(message)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _without_wall(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _without_wall(item) for key, item in value.items() if key != "wall_seconds"}
    if isinstance(value, list):
        return [_without_wall(item) for item in value]
    return value


def file_digest(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


RAW_PREDICTORS = (
    "annmeantemp", "meandiurnrange", "isothermality", "tempseason",
    "maxtempwarmmonth", "mintempcoldmonth", "tempannrange", "meantempwetq",
    "meantempdryq", "meantempwarmq", "meantempcoldq", "annprecip",
    "precipwetmonth", "precipdrymonth", "precipseason", "precipwetq",
    "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness",
    "soil_class", "dist_fw", "dist_road", "fpar", "veg_mvg", "landuse_secondary",
    "human_footprint",
)
CONTINUOUS = tuple(name for name in RAW_PREDICTORS if name not in {"soil_class", "veg_mvg", "landuse_secondary"})
MANDATORY_CONTINUOUS = ("elevation", "top_roughness", "dist_fw", "dist_road", "fpar", "human_footprint")
CATEGORICAL = ("soil_class", "veg_mvg", "landuse_secondary")
BIOCLIM_BLOCKS = {
    "BIO1_8_11": ("annmeantemp", "meantempwetq", "meantempdryq", "meantempwarmq", "meantempcoldq"),
    "BIO5_7": ("maxtempwarmmonth", "mintempcoldmonth", "tempannrange"),
    "BIO2_4": ("meandiurnrange", "isothermality", "tempseason"),
    "BIO12_14_16_19": ("annprecip", "precipwetmonth", "precipdrymonth", "precipwetq", "precipdryq", "precipwarmq", "precipcoldq"),
    "BIO15": ("precipseason",),
}
BIOCLIM = tuple(name for block in BIOCLIM_BLOCKS.values() for name in block)
FROZEN_ORDER = {name: index for index, name in enumerate(RAW_PREDICTORS)}
ENCODED_CONTINUOUS_INDEX = {name: index for index, name in enumerate(CONTINUOUS)}
PREDICTOR_COUNT = 77
SEEDS = (31031, 31032, 31033, 31034, 31035)
SCREEN_ENDPOINTS = ("fraction25/ladder00", "fraction50/ladder00", "fraction100/full")
CONFIRMATION_ENDPOINTS = ("fraction25/ladder01", "fraction25/ladder02", "fraction50/ladder01", "fraction50/ladder02", "fraction100/full")
SCREEN_SEEDS = (31031, 31032, 31033)
CONFIRMATION_SEEDS = (31034, 31035)
TARGET_METHOD = "target_only_resmlp"
MULTIHEAD_METHOD = "multihead_full_finetune"


def _numeric(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PredictorSensitivityError("non-numeric predictor") from exc
    _require(math.isfinite(number), "non-finite predictor")
    return number


def _raw_matrix(rows: Sequence[Mapping[str, Any]], names: Sequence[str]) -> np.ndarray:
    values = np.asarray([[_numeric(row[name]) for name in names] for row in rows], dtype=np.float64)
    _require(values.ndim == 2 and values.shape[0] >= 2 and np.isfinite(values).all(), "correlation matrix input invalid")
    return values


def _spearman_abs(rows: Sequence[Mapping[str, Any]], names: Sequence[str]) -> np.ndarray:
    raw = _raw_matrix(rows, names)
    if len(names) == 1:
        return np.ones((1, 1), dtype=np.float64)
    ranked = np.column_stack([rankdata(raw[:, index], method="average") for index in range(raw.shape[1])])
    correlation = np.corrcoef(ranked, rowvar=False)
    correlation = np.nan_to_num(correlation, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(correlation, 1.0)
    return np.abs(correlation)


def _complete_clusters(similarity: np.ndarray, names: Sequence[str], threshold: float) -> list[tuple[int, ...]]:
    """Deterministic complete-linkage clusters at an absolute-correlation cut."""
    clusters: list[tuple[int, ...]] = [(index,) for index in range(len(names))]
    limit = 1.0 - float(threshold)
    while len(clusters) > 1:
        candidate: tuple[float, tuple[int, ...], tuple[int, ...]] | None = None
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                a, b = clusters[left], clusters[right]
                distance = max(1.0 - float(similarity[i, j]) for i in a for j in b)
                pair = (distance, a, b)
                if distance <= limit + 1e-12 and (candidate is None or pair < candidate):
                    candidate = pair
        if candidate is None:
            break
        _, a, b = candidate
        merged = tuple(sorted(a + b))
        clusters.remove(a); clusters.remove(b); clusters.append(merged); clusters.sort()
    return clusters


def _cluster_medoid(cluster: Sequence[int], similarity: np.ndarray, names: Sequence[str]) -> int:
    scores = {index: float(sum(1.0 - similarity[index, other] for other in cluster)) for index in cluster}
    return min(cluster, key=lambda index: (scores[index], FROZEN_ORDER[names[index]]))


def _validate_source_rows(rows: Sequence[Mapping[str, Any]], assignments: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    forbidden = {"response", "label", "presence", "absence", "y", "species", "occurrence", "prediction", "score", "importance"}
    if forbidden.intersection({str(key).lower() for row in rows for key in row}):
        raise PredictorSensitivityError("response-aware fields reached mask audit")
    by_cell: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("grid_cell_id", "")); _require(key and key not in by_cell, "duplicate map cell")
        by_cell[key] = dict(row)
    amap: dict[str, dict[str, Any]] = {}
    for row in assignments:
        key = str(row.get("grid_cell_id", "")); _require(key and key not in amap, "duplicate map assignment")
        amap[key] = dict(row)
    _require(set(by_cell) == set(amap), "map/assignment keys do not join exactly")
    return {key: {**by_cell[key], "__assignment": amap[key]} for key in sorted(by_cell)}


def _eligible_rows(rows: Sequence[Mapping[str, Any]], assignments: Sequence[Mapping[str, Any]], held_fold: str) -> list[dict[str, Any]]:
    joined = _validate_source_rows(rows, assignments)
    result = []
    for row in joined.values():
        assignment = row["__assignment"]
        if assignment.get("outer_role") != "outer_train" or assignment.get("cv_fold") == held_fold:
            continue
        if str(row.get("predictor_complete", "")).lower() not in {"true", "1"}:
            continue
        if any(name not in row or str(row[name]) == "" for name in RAW_PREDICTORS):
            continue
        # Categorical values participate only in completeness; no response or
        # category support decision is made by this correlation selector.
        for name in CONTINUOUS:
            _numeric(row[name])
        result.append(row)
    _require(len(result) >= 2, f"insufficient complete outer-training cells for {held_fold}")
    return result


def encoded_mask(kept_raw: Iterable[str]) -> np.ndarray:
    kept = set(kept_raw)
    _require(kept.issubset(set(RAW_PREDICTORS)), "unknown raw predictor")
    _require(set(MANDATORY_CONTINUOUS).issubset(kept) and set(CATEGORICAL).issubset(kept), "mandatory predictor omitted")
    columns = np.zeros(PREDICTOR_COUNT, dtype=bool)
    for name in CONTINUOUS:
        columns[ENCODED_CONTINUOUS_INDEX[name]] = name in kept
    # The 52 one-hot columns are retained as a shape-preserving categorical
    # support block; category neutralisation remains Goal035's responsibility.
    columns[len(CONTINUOUS):] = True
    _require(int(columns[:len(CONTINUOUS)].sum()) < len(CONTINUOUS), "mask must remove a continuous predictor")
    columns.flags.writeable = False
    return columns


def _mask_for_rows(rows: Sequence[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    kept: set[str] = set(MANDATORY_CONTINUOUS) | set(CATEGORICAL)
    block_records: dict[str, Any] = {}
    for block_name, names in BIOCLIM_BLOCKS.items():
        similarity = _spearman_abs(rows, names)
        clusters = _complete_clusters(similarity, names, threshold)
        medoids = [_cluster_medoid(cluster, similarity, names) for cluster in clusters]
        selected = [names[index] for index in medoids]
        kept.update(selected)
        block_records[block_name] = {"predictors": list(names), "clusters": [[names[index] for index in cluster] for cluster in clusters], "medoids": selected}
    mask = encoded_mask(kept)
    return {"threshold": float(threshold), "kept_raw": [name for name in RAW_PREDICTORS if name in kept], "excluded_raw": [name for name in RAW_PREDICTORS if name not in kept], "encoded_columns": mask.astype(int).tolist(), "encoded_column_count": int(mask.sum()), "blocks": block_records, "mask_digest": digest_value(mask.astype(int).tolist()), "outer_attempted": 0, "outer_opened": 0}


def jaccard(left: Sequence[bool], right: Sequence[bool]) -> float:
    a, b = set(np.flatnonzero(np.asarray(left, dtype=bool))), set(np.flatnonzero(np.asarray(right, dtype=bool)))
    union = a | b
    return 1.0 if not union else float(len(a & b) / len(union))


def build_masks(map_rows: Sequence[Mapping[str, Any]], assignment_rows: Sequence[Mapping[str, Any]], *, threshold: float = 0.85, diagnostic_thresholds: Sequence[float] = (0.80, 0.90)) -> dict[str, Any]:
    _require(float(threshold) == 0.85, "primary threshold is frozen at 0.85")
    primary: dict[str, dict[str, Any]] = {}; diagnostics: dict[str, dict[str, Any]] = {}
    for fold in FOLDS:
        rows = _eligible_rows(map_rows, assignment_rows, fold)
        primary[fold] = _mask_for_rows(rows, 0.85)
        for diagnostic_threshold in diagnostic_thresholds:
            _require(float(diagnostic_threshold) in {0.80, 0.90}, "diagnostic threshold drift")
            diagnostics[f"{fold}@{float(diagnostic_threshold):.2f}"] = _mask_for_rows(rows, float(diagnostic_threshold))
    pairwise = {}
    for i, left in enumerate(FOLDS):
        for right in FOLDS[i + 1:]:
            pairwise[f"{left}__{right}"] = jaccard(primary[left]["encoded_columns"], primary[right]["encoded_columns"])
    _require(len(pairwise) == 10, "primary Jaccard inventory drift")
    _require(all(any(name in mask["excluded_raw"] for name in BIOCLIM) for mask in primary.values()), "primary mask removed no BIOCLIM predictor")
    return {"primary": primary, "diagnostic": diagnostics, "jaccard": pairwise, "mask_count": 5, "threshold": 0.85, "outer_attempted": 0, "outer_opened": 0, "source_rows_response_blind": True}


def apply_encoded_mask(values: np.ndarray, mask: Sequence[bool]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    columns = np.asarray(mask, dtype=bool)
    _require(array.ndim == 2 and array.shape[1] == PREDICTOR_COUNT and np.isfinite(array).all(), "encoded predictors invalid")
    _require(columns.shape == (PREDICTOR_COUNT,) and bool(columns[len(CONTINUOUS):].all()), "encoded mask shape/category drift")
    result = np.array(array, copy=True, order="C")
    result[:, ~columns] = 0.0
    _require(np.array_equal(result[:, len(CONTINUOUS):], array[:, len(CONTINUOUS):]), "categorical columns changed")
    result.flags.writeable = False
    return result


def apply_mask_to_case(bundle: Any, mask: Sequence[bool]) -> Any:
    """Return a CaseBundle with the same 77 columns and neutralised inputs."""
    from dataclasses import replace
    original = np.asarray(mask, dtype=bool)
    _require(original.shape == (PREDICTOR_COUNT,), "case mask shape drift")
    arrays = {
        key: (apply_encoded_mask(value, original) if np.asarray(value).ndim == 2 and np.asarray(value).shape[1] == PREDICTOR_COUNT else np.asarray(value))
        for key, value in bundle.arrays.items()
    }
    return replace(bundle, arrays=arrays)


def _support_mask_digests(bundle: Any) -> dict[str, Any]:
    """Return the split-scoped categorical-support digests used by Goal035."""
    from .final_inner_data import ENDPOINTS as DATA_ENDPOINTS, prepare_case
    prepared = prepare_case(bundle)
    _require(tuple(DATA_ENDPOINTS) == tuple(ENDPOINTS), "endpoint registry drift")
    return {
        "target": {endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS},
        "auxiliary": prepared["auxiliary_mask"].digest,
    }


def build_plan() -> dict[str, Any]:
    return {"primary_masks": 5, "diagnostic_thresholds": [0.80, 0.90], "screen_cases": 120, "screen_logical_artifacts": 840, "screen_physical_fits": 1680, "confirmation_cases": 80, "confirmation_logical_artifacts": 880, "confirmation_physical_fits": 1760, "outer_attempted": 0, "outer_opened": 0}


def screen_gate(metrics: Mapping[str, Any]) -> bool:
    return int(metrics.get("positive_endpoints", 0)) >= 2 and int(metrics.get("positive_species", 0)) >= 5 and int(metrics.get("positive_seeds", 0)) >= 2 and float(metrics.get("aggregate_tss", -math.inf)) >= 0.0


def confirmation_gate(metrics: Mapping[str, Any]) -> bool:
    return int(metrics.get("positive_endpoints", 0)) >= 4 and int(metrics.get("positive_species", 0)) >= 5 and int(metrics.get("positive_reserved_seeds", 0)) >= 2 and float(metrics.get("aggregate_tss", -math.inf)) >= 0.0


def delta_u(reduced: Mapping[str, Mapping[str, float]], full: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    keys = sorted(set(reduced) & set(full)); _require(keys, "Delta U requires paired metrics")
    return {metric: float(np.mean([float(reduced[key][metric]) - float(full[key][metric]) for key in keys])) for metric in ("auc", "tss", "mcc")}


def delta_i(reduced_multi: Mapping[str, Mapping[str, float]], reduced_target: Mapping[str, Mapping[str, float]], full_multi: Mapping[str, Mapping[str, float]], full_target: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    keys = sorted(set(reduced_multi) & set(reduced_target) & set(full_multi) & set(full_target)); _require(keys, "Delta I requires paired metrics")
    return {metric: float(np.mean([(reduced_multi[key][metric] - reduced_target[key][metric]) - (full_multi[key][metric] - full_target[key][metric]) for key in keys])) for metric in ("auc", "tss", "mcc")}


def _positive_seed_count(values: Mapping[int | str, float], seeds: Sequence[int]) -> int:
    return sum(float(values.get(seed, values.get(str(seed), -math.inf))) > 0 for seed in seeds)


def reconstruct_effect_lanes(records: Sequence[Mapping[str, Any]], *, reserved_seeds: Sequence[int] = CONFIRMATION_SEEDS) -> dict[str, Any]:
    """Return separately gated Delta U and Delta I aggregate summaries."""
    _require(records, "effect records missing")
    species_seen = {str(row.get("species")) for row in records}
    endpoints_seen = {str(row.get("endpoint")) for row in records}
    _require(species_seen == set(SPECIES), "effect species inventory drift")
    _require(endpoints_seen in (set(SCREEN_ENDPOINTS), set(CONFIRMATION_ENDPOINTS)), "effect endpoint inventory drift")
    for species_name in SPECIES:
        for endpoint_name in endpoints_seen:
            rows = [row for row in records if str(row["species"]) == species_name and str(row["endpoint"]) == endpoint_name]
            _require(len(rows) == len(FOLDS) and {str(row["fold"]) for row in rows} == set(FOLDS), "effect fold inventory drift")
            seed_values = {int(item["seed"]) for row in rows for item in row.get("per_seed", [])}
            _require(seed_values in (set(SCREEN_SEEDS), set(CONFIRMATION_SEEDS)), "effect seed inventory drift")
    def one(prefix: str) -> dict[str, Any]:
        fold_values: dict[tuple[str, str], list[float]] = {}; fold_tss: dict[tuple[str, str], list[float]] = {}; seed: dict[int, list[float]] = {}; seed_tss: dict[int, list[float]] = {}
        for row in records:
            key = (str(row["species"]), str(row["endpoint"]))
            fold_values.setdefault(key, []).append(float(row[f"{prefix}_auc"]))
            fold_tss.setdefault(key, []).append(float(row[f"{prefix}_tss"]))
            for item in row.get("per_seed", []):
                seed.setdefault(int(item["seed"]), []).append(float(item[f"{prefix}_auc"]))
                seed_tss.setdefault(int(item["seed"]), []).append(float(item[f"{prefix}_tss"]))
        species_endpoint_auc = {key: float(np.mean(values)) for key, values in fold_values.items()}
        species_endpoint_tss = {key: float(np.mean(values)) for key, values in fold_tss.items()}
        endpoint_species: dict[str, list[float]] = {}; species_values: dict[str, list[float]] = {}
        endpoint_tss: dict[str, list[float]] = {}; species_tss: dict[str, list[float]] = {}
        for (species_name, endpoint_name), value in species_endpoint_auc.items():
            endpoint_species.setdefault(endpoint_name, []).append(value); species_values.setdefault(species_name, []).append(value)
        for (species_name, endpoint_name), value in species_endpoint_tss.items():
            endpoint_tss.setdefault(endpoint_name, []).append(value); species_tss.setdefault(species_name, []).append(value)
        em = {key: float(np.mean(values)) for key, values in endpoint_species.items()}; sm = {key: float(np.mean(values)) for key, values in species_values.items()}
        sem = {key: float(np.mean(values)) for key, values in seed.items()}; sem_tss = {key: float(np.mean(values)) for key, values in seed_tss.items()}
        aggregate_auc = float(np.mean(list(species_endpoint_auc.values())))
        aggregate_tss = float(np.mean(list(species_endpoint_tss.values())))
        return {"endpoint_means": em, "species_means": sm, "seed_means": sem, "positive_endpoints": sum(v > 0 for v in em.values()), "positive_species": sum(v > 0 for v in sm.values()), "positive_seeds": sum(v > 0 for v in sem.values()), "positive_reserved_seeds": _positive_seed_count(sem, reserved_seeds), "aggregate_tss": aggregate_tss, "aggregate_auc": aggregate_auc, "aggregate_tss_value": aggregate_tss, "seed_tss_means": sem_tss}
    return {"delta_u": one("delta_u"), "delta_i": one("delta_i")}


def assert_confirmation_eligible(screen: Mapping[str, Any]) -> None:
    """Fail closed unless a declared screen lane earned advancement."""
    _require(bool(screen.get("eligible_delta_u") or screen.get("eligible_delta_i")), "confirmation forbidden until screen gate is earned")


def validate_mask_audit(audit: Mapping[str, Any]) -> dict[str, Any]:
    _require(audit.get("mask_count") == 5 and audit.get("threshold") == 0.85 and audit.get("outer_attempted") == audit.get("outer_opened") == 0, "mask audit gate failed")
    primary = audit.get("primary", {}); _require(set(primary) == set(FOLDS), "mask fold inventory drift")
    for fold, mask in primary.items():
        columns = np.asarray(mask.get("encoded_columns"), dtype=bool)
        _require(columns.shape == (PREDICTOR_COUNT,) and columns[len(CONTINUOUS):].all() and mask.get("mask_digest") == digest_value(columns.astype(int).tolist()), f"mask identity drift: {fold}")
        _require(any(name in mask.get("excluded_raw", []) for name in BIOCLIM), f"mask does not reduce BIOCLIM: {fold}")
        _require(set(MANDATORY_CONTINUOUS).issubset(mask.get("kept_raw", [])) and set(CATEGORICAL).issubset(mask.get("kept_raw", [])), f"mandatory mask predictor drift: {fold}")
    _require(len(audit.get("jaccard", {})) == 10 and all(0.0 <= float(value) <= 1.0 for value in audit["jaccard"].values()), "Jaccard inventory drift")
    return dict(audit)


def load_frozen_mask_audit(
    config: SensitivityConfig,
    audit_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the committed Goal039 mask receipt without recomputing it."""
    authority = config.raw.get("mask_authority")
    _require(isinstance(authority, Mapping), "mask authority binding missing")
    expected = (config.root / str(authority["path"])).resolve()
    target = expected if audit_path is None else Path(audit_path).resolve()
    _require(target == expected and target.is_file() and not target.is_symlink(), "mask authority path drift")
    _require(file_digest(target) == authority.get("sha256"), "mask authority file digest drift")
    try:
        receipt = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictorSensitivityError("mask authority receipt unreadable") from exc
    _require(
        receipt.get("config_digest") == authority.get("selector_config_digest"),
        "mask authority selector digest drift",
    )
    expected_sources = {
        name: config.raw["authorities"][name]["sha256"]
        for name in ("goal024_map", "goal025_map_assignments")
    }
    _require(receipt.get("source_digests") == expected_sources, "mask authority source digest drift")
    return validate_mask_audit(receipt)


def run_neural_stage_case(bundle: Any, mask: Sequence[bool], goal035_config_path: str | Path, *, endpoints: Sequence[str], seeds: Sequence[int], max_epochs: int | None = None, patience: int | None = None) -> dict[str, Any]:
    """Run only declared Goal039 endpoint/seed leaves using Goal038's pattern.

    Each seed gets one direct auxiliary multi-head lifecycle and two target
    lifecycles per endpoint.  Inputs stay 77-column and are neutralised only
    after the frozen standardisation/support preparation.
    """
    from .final_inner_data import ENDPOINT_SLUGS, load_config as load_goal035_config, prepare_case, runtime_attestation
    from . import final_inner_runner as runner
    from .real_six_path import _artifact

    goal035 = load_goal035_config(
        goal035_config_path, root=Path(goal035_config_path).resolve().parents[1],
        require_receipt=True,
    )
    runtime = runtime_attestation(goal035, strict=True)
    runtime_digest = digest_value(runtime)
    _require(set(endpoints).issubset(set(ENDPOINTS)) and set(seeds).issubset(set(SEEDS)), "stage lane scope drift")
    _require(len(tuple(seeds)) == 1, "one seed is required per atomic neural leaf")
    _require(len(set(endpoints)) == len(tuple(endpoints)) and len(set(seeds)) == len(tuple(seeds)), "stage lane duplicate")
    masked = apply_mask_to_case(bundle, mask)
    original_support = _support_mask_digests(bundle)
    reduced_support = _support_mask_digests(masked)
    _require(original_support == reduced_support, "support-mask digest changed under substrate mask")
    prepared = prepare_case(masked)
    spec = runner._architecture(goal035)
    device = runner._prepare_device("cpu")
    epochs = int(max_epochs if max_epochs is not None else goal035.raw["training"]["max_epochs"])
    patience_value = int(patience if patience is not None else goal035.raw["training"]["patience"])
    _require(1 <= patience_value <= epochs, "stage epoch budget invalid")
    names = tuple(name for name in SPECIES if name != bundle.target)
    aux_x = prepared["auxiliary"]
    raw = masked.arrays
    aux_y = {role: raw[f"aux_y_{role}"] for role in ("discovery", "stopping", "replay")}
    aux_species = {role: raw[f"aux_species_{role}"] for role in ("discovery", "stopping", "replay")}
    outputs = np.empty((len(endpoints), 2, len(raw["x_held"])), dtype=np.float32)
    artifacts: list[dict[str, Any]] = []
    for seed in seeds:
        multi_factory = lambda: runner.MultiHeadResidual(spec, 77, names)
        aux_lifecycle = runner._neural_lifecycle(
            multi_factory, spec, int(seed), device,
            aux_x["discovery"], aux_y["discovery"],
            aux_x["stopping"], aux_y["stopping"],
            aux_x["replay"], aux_y["replay"], aux_x["replay"],
            max_epochs=epochs, patience=patience_value,
            species_names=names,
            species_discovery=aux_species["discovery"],
            species_stopping=aux_species["stopping"],
            species_replay=aux_species["replay"],
            species_prediction=aux_species["replay"],
        )
        aux_artifact = runner._artifact(f"aux/multihead/seed{int(seed)}", "auxiliary", aux_lifecycle)
        aux_artifact["fit_seed"] = int(seed)
        aux_artifact["runtime_digest"] = runtime_digest
        artifacts.append(aux_artifact)
        shared_state = runner._shared_state(aux_lifecycle.model)
        for endpoint_index, endpoint in enumerate(endpoints):
            slug = ENDPOINT_SLUGS[endpoint]
            xdis = prepared["target"][f"target_{slug}_x_discovery"]
            xstop = prepared["target"][f"target_{slug}_x_stopping"]
            xrep = prepared["target"][f"target_{slug}_x_replay"]
            xheld = prepared["target"][f"target_{slug}_x_held"]
            ydis, ystop, yrep = (raw[f"target_{slug}_y_{role}"] for role in ("discovery", "stopping", "replay"))
            fit_seed = runner._fit_seed(goal035, masked, endpoint, int(seed), "target")
            target_lifecycle = runner._neural_lifecycle(
                runner._residual_factory(spec, 77), spec, fit_seed, device,
                xdis, ydis, xstop, ystop, xrep, yrep, xheld,
                max_epochs=epochs, patience=patience_value,
            )
            multi_lifecycle = runner._neural_lifecycle(
                runner._residual_factory(spec, 77, shared_state=shared_state), spec, fit_seed, device,
                xdis, ydis, xstop, ystop, xrep, yrep, xheld,
                max_epochs=epochs, patience=patience_value,
            )
            _require(target_lifecycle.initial_head_digest == multi_lifecycle.initial_head_digest, "target head reset mismatch")
            _require(multi_lifecycle.initial_shared_digest == aux_lifecycle.final_shared_digest, "auxiliary shared state transfer mismatch")
            with runner.torch.no_grad():
                x_tensor = runner.torch.from_numpy(np.ascontiguousarray(xheld)).to(device)
                target_values = runner.torch.sigmoid(target_lifecycle.model(x_tensor)).detach().cpu().numpy().astype(np.float32)
                multi_values = runner.torch.sigmoid(multi_lifecycle.model(x_tensor)).detach().cpu().numpy().astype(np.float32)
            _require(target_values.shape == multi_values.shape == (len(xheld),) and np.isfinite(target_values).all() and np.isfinite(multi_values).all(), "stage prediction invalid")
            _require(np.all((target_values >= 0) & (target_values <= 1)) and np.all((multi_values >= 0) & (multi_values <= 1)), "stage prediction range invalid")
            outputs[endpoint_index, 0] = target_values
            outputs[endpoint_index, 1] = multi_values
            for method, lifecycle in ((TARGET_METHOD, target_lifecycle), (MULTIHEAD_METHOD, multi_lifecycle)):
                artifact = runner._artifact(f"target/{endpoint}/seed{int(seed)}/{method}", "target", lifecycle)
                artifact["fit_seed"] = int(fit_seed)
                artifact["runtime_digest"] = runtime_digest
                artifacts.append(artifact)
    expected_logical = 7 if len(endpoints) == 3 else 11 if len(endpoints) == 5 else 1 + 2 * len(endpoints)
    expected_physical = expected_logical * 2
    _require(len(artifacts) == expected_logical and sum(int(item["physical_fits"]) for item in artifacts) == expected_physical, "stage fit arithmetic drift")
    return {"predictions": outputs, "metadata": {
        "schema_version": "goal039-stage-neural-v2", "methods": [TARGET_METHOD, MULTIHEAD_METHOD],
        "endpoints": list(endpoints), "seeds": [int(seed) for seed in seeds],
        "mask_digest": digest_value(np.asarray(mask, dtype=np.uint8).tolist()),
        "support_mask_digests": original_support, "reduced_support_mask_digests": reduced_support,
        "runtime_digest": runtime_digest,
        "artifacts": artifacts, "logical_artifacts": expected_logical, "physical_fits": expected_physical,
        "outer_attempted": 0, "outer_opened": 0,
    }}


def write_reduced_leaf(path: str | Path, identity: Mapping[str, Any], result: Mapping[str, Any]) -> Path:
    values = np.asarray(result["predictions"], dtype=np.float32)
    required_keys = {"stage", "species", "held_fold", "seed", "mask_digest", "bundle_digest", "endpoints", "methods", "config_digest", "source_fingerprint", "runtime_digest"}
    _require(set(identity) == required_keys, "reduced leaf identity schema drift")
    expected_endpoints = len(SCREEN_ENDPOINTS) if identity["stage"] == "screen" else len(CONFIRMATION_ENDPOINTS) if identity["stage"] == "confirmation" else 0
    _require(expected_endpoints and values.ndim == 3 and values.shape[0] == expected_endpoints and values.shape[1] == 2 and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "reduced leaf prediction shape drift")
    _require(tuple(identity["methods"]) == (TARGET_METHOD, MULTIHEAD_METHOD), "reduced leaf methods drift")
    _require(tuple(identity["endpoints"]) == (SCREEN_ENDPOINTS if identity["stage"] == "screen" else CONFIRMATION_ENDPOINTS), "reduced leaf endpoints drift")
    for name in ("config_digest", "source_fingerprint", "runtime_digest"):
        _require(isinstance(identity[name], str) and len(identity[name]) == 64, f"reduced leaf {name} drift")
    metadata = dict(result.get("metadata", {})); metadata.update({"schema_version": "goal039-reduced-leaf-v2", "identity": dict(identity), "prediction_digest": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest(), "outer_attempted": 0, "outer_opened": 0})
    _validate_reduced_metadata(metadata, identity, values)
    destination = Path(path); destination.parent.mkdir(parents=True, exist_ok=True)
    _require(not destination.exists(), "reduced leaf already exists; validate before resume")
    temporary = Path(tempfile.mkdtemp(dir=destination.parent, prefix=f".{destination.name}."))
    try:
        np.save(temporary / "predictions.npy", values); (temporary / "metadata.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
    except Exception:
        import shutil
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_reduced_leaf(path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    directory = Path(path); _require((directory / "predictions.npy").is_file() and (directory / "metadata.json").is_file(), "reduced leaf missing")
    values = np.load(directory / "predictions.npy", allow_pickle=False); metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    _validate_reduced_metadata(metadata, metadata.get("identity", {}), values)
    return values, metadata


def _validate_reduced_metadata(metadata: Mapping[str, Any], identity: Mapping[str, Any], values: np.ndarray) -> None:
    """Validate compact leaf invariants without retaining labels or scores."""
    _require(metadata.get("schema_version") == "goal039-reduced-leaf-v2", "reduced leaf schema drift")
    _require(metadata.get("identity") == dict(identity), "reduced leaf identity mismatch")
    _require(metadata.get("prediction_digest") == hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest(), "reduced leaf prediction digest drift")
    _require(metadata.get("outer_attempted") == metadata.get("outer_opened") == 0, "reduced leaf outer boundary drift")
    expected_endpoints = SCREEN_ENDPOINTS if identity.get("stage") == "screen" else CONFIRMATION_ENDPOINTS
    expected_logical = 7 if len(expected_endpoints) == 3 else 11
    artifacts = metadata.get("artifacts")
    _require(isinstance(artifacts, list) and len(artifacts) == expected_logical, "reduced leaf artifact inventory drift")
    _require(all(item.get("logical_artifacts") == 1 and item.get("finite") is True and item.get("runtime_digest") == identity.get("runtime_digest") for item in artifacts), "reduced leaf artifact invariant drift")
    _require(sum(int(item.get("physical_fits", -1)) for item in artifacts) == expected_logical * 2, "reduced leaf fit count drift")
    _require(metadata.get("support_mask_digests") == metadata.get("reduced_support_mask_digests"), "reduced support-mask digest drift")


def canary_compare(full_control: np.ndarray, full_replay: np.ndarray, reduced_a: np.ndarray, reduced_b: np.ndarray, mask: Sequence[bool]) -> dict[str, Any]:
    """Validate the canary evidence without retaining row-level predictions."""
    control = np.asarray(full_control); replay = np.asarray(full_replay); first = np.asarray(reduced_a); second = np.asarray(reduced_b); columns = np.asarray(mask, dtype=bool)
    _require(control.ndim == replay.ndim == first.ndim == second.ndim == 3 and first.shape == second.shape == replay.shape == control.shape and first.shape[:2] == (3, 2), "canary prediction shape drift")
    _require(np.isfinite(control).all() and np.isfinite(replay).all() and np.isfinite(first).all() and np.isfinite(second).all() and np.array_equal(control, replay) and np.array_equal(first, second), "canary deterministic prediction gate failed")
    _require(columns.shape == (PREDICTOR_COUNT,) and columns[len(CONTINUOUS):].all() and int((~columns[:len(CONTINUOUS)]).sum()) >= 1, "canary mask gate failed")
    receipt = {"schema_version": "goal039-canary-v2", "decision": "pass", "deterministic": True, "finite": True, "full_control_replayed": True, "full_control_bitwise_match": True, "reduced_repeats": 2, "reduced_repeats_bitwise_match": True, "mask_digest": digest_value(columns.astype(int).tolist()), "full_control_shape": list(control.shape), "reduced_shape": list(first.shape), "outer_attempted": 0, "outer_opened": 0}
    receipt["receipt_digest"] = digest_value(receipt)
    return receipt


def paired_effect_records(cases: Sequence[Mapping[str, Any]], *, endpoints: Sequence[str], seeds: Sequence[int]) -> list[dict[str, Any]]:
    """Calculate fold/species paired Delta U and Delta I records.

    ``cases`` contain held labels and reduced/full two-method predictions.  A
    threshold is selected separately for each architecture/method from pooled
    held predictions, then applied to each fold, matching Goal036's threshold
    policy without ever persisting labels or row scores.
    """
    _require(cases and set(endpoints).issubset(ENDPOINTS) and set(seeds).issubset(SEEDS), "effect case scope invalid")
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for case in cases:
        key = (str(case["species"]), str(case["endpoint"])); _require(key[1] in endpoints, "effect endpoint drift"); grouped.setdefault(key, []).append(case)
    seed_positions = {int(seed): index for index, seed in enumerate(SEEDS)}
    thresholds: dict[tuple[str, str, str], float] = {}
    for key, rows in grouped.items():
        for architecture in ("full", "reduced"):
            for method_index, method in enumerate((TARGET_METHOD, MULTIHEAD_METHOD)):
                labels = np.concatenate([np.asarray(row["y"], dtype=np.int8) for row in rows]); scores = np.concatenate([np.mean(np.asarray(row[architecture])[ [seed_positions[int(seed)] for seed in seeds], ENDPOINTS.index(key[1]), method_index, :], axis=0) for row in rows]); thresholds[(key[0], key[1], f"{architecture}/{method}")] = select_threshold(labels, scores)[0]
    records: list[dict[str, Any]] = []
    for row in cases:
        key = (str(row["species"]), str(row["endpoint"])); y = np.asarray(row["y"], dtype=np.int8); fold = str(row["fold"]); reduced = np.asarray(row["reduced"]); full = np.asarray(row["full"]); endpoint_index = ENDPOINTS.index(key[1])
        _require(reduced.ndim == full.ndim == 4 and reduced.shape == full.shape and reduced.shape[0] == len(SEEDS), "effect prediction shape drift")
        common = [seed_positions[int(seed)] for seed in seeds]
        averaged: dict[str, dict[str, Any]] = {}
        per_seed: list[dict[str, Any]] = []
        for architecture, values in (("full", full), ("reduced", reduced)):
            for method_index, method in enumerate((TARGET_METHOD, MULTIHEAD_METHOD)):
                score = np.mean(values[common, endpoint_index, method_index, :], axis=0)
                threshold = thresholds[(key[0], key[1], f"{architecture}/{method}")]
                averaged[f"{architecture}/{method}"] = binary_metrics(y, score, threshold)
        for seed in seeds:
            seed_index = seed_positions[int(seed)]; metrics: dict[str, dict[str, Any]] = {}
            for architecture, values in (("full", full), ("reduced", reduced)):
                for method_index, method in enumerate((TARGET_METHOD, MULTIHEAD_METHOD)):
                    score = values[seed_index, endpoint_index, method_index]; threshold = thresholds[(key[0], key[1], f"{architecture}/{method}")]; metrics[f"{architecture}/{method}"] = binary_metrics(y, score, threshold)
            du_auc = float(metrics[f"reduced/{MULTIHEAD_METHOD}"]["roc_auc"] - metrics[f"full/{MULTIHEAD_METHOD}"]["roc_auc"]); du_tss = float(metrics[f"reduced/{MULTIHEAD_METHOD}"]["tss"] - metrics[f"full/{MULTIHEAD_METHOD}"]["tss"])
            reduced_lift_auc = metrics[f"reduced/{MULTIHEAD_METHOD}"]["roc_auc"] - metrics[f"reduced/{TARGET_METHOD}"]["roc_auc"]; full_lift_auc = metrics[f"full/{MULTIHEAD_METHOD}"]["roc_auc"] - metrics[f"full/{TARGET_METHOD}"]["roc_auc"]
            reduced_lift_tss = metrics[f"reduced/{MULTIHEAD_METHOD}"]["tss"] - metrics[f"reduced/{TARGET_METHOD}"]["tss"]; full_lift_tss = metrics[f"full/{MULTIHEAD_METHOD}"]["tss"] - metrics[f"full/{TARGET_METHOD}"]["tss"]
            per_seed.append({"seed": int(seed), "delta_u_auc": du_auc, "delta_u_tss": du_tss, "delta_i_auc": float(reduced_lift_auc - full_lift_auc), "delta_i_tss": float(reduced_lift_tss - full_lift_tss)})
        du_auc = float(averaged[f"reduced/{MULTIHEAD_METHOD}"]["roc_auc"] - averaged[f"full/{MULTIHEAD_METHOD}"]["roc_auc"])
        du_tss = float(averaged[f"reduced/{MULTIHEAD_METHOD}"]["tss"] - averaged[f"full/{MULTIHEAD_METHOD}"]["tss"])
        di_auc = float((averaged[f"reduced/{MULTIHEAD_METHOD}"]["roc_auc"] - averaged[f"reduced/{TARGET_METHOD}"]["roc_auc"]) - (averaged[f"full/{MULTIHEAD_METHOD}"]["roc_auc"] - averaged[f"full/{TARGET_METHOD}"]["roc_auc"]))
        di_tss = float((averaged[f"reduced/{MULTIHEAD_METHOD}"]["tss"] - averaged[f"reduced/{TARGET_METHOD}"]["tss"]) - (averaged[f"full/{MULTIHEAD_METHOD}"]["tss"] - averaged[f"full/{TARGET_METHOD}"]["tss"]))
        records.append({"species": key[0], "endpoint": key[1], "fold": fold, "seed": "common", "delta_u_auc": du_auc, "delta_u_tss": du_tss, "delta_i_auc": di_auc, "delta_i_tss": di_tss, "per_seed": per_seed})
    return records


def _read_csv(path: Path) -> list[dict[str, str]]:
    _require(path.is_file() and not path.is_symlink(), f"missing source: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", delete=False, encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2); stream.write("\n"); temporary = Path(stream.name)
    temporary.replace(path)


@dataclass(frozen=True)
class SensitivityConfig:
    source_path: Path
    root: Path
    raw: Mapping[str, Any]

    @property
    def private_root(self) -> Path: return self.root / self.raw["evidence"]["private_root"]
    @property
    def tracked_root(self) -> Path: return self.root / self.raw["evidence"]["tracked_root"]


def load_config(path: str | Path, *, root: str | Path | None = None) -> SensitivityConfig:
    source = Path(path).resolve(); raw = json.loads(source.read_text(encoding="utf-8")); project_root = Path(root).resolve() if root is not None else source.parents[1]
    expected = {"schema_version", "goal_id", "config_digest", "authorities", "execution_sources", "scope", "mask", "training", "execution", "conventional", "mask_authority", "gates", "evidence", "runtime"}
    _require(set(raw) == expected and raw["schema_version"] == "1.0" and raw["goal_id"] == "goal039-predictor-substrate-sensitivity", "Goal039 config identity drift")
    body = dict(raw); claimed = body.pop("config_digest"); _require(claimed == digest_value(body), "Goal039 self digest drift")
    _require("goal039_decision" in raw["authorities"], "Goal039 decision authority missing")
    for group in ("authorities", "execution_sources"):
        _require(isinstance(raw[group], dict), f"{group} binding schema drift")
        for name, binding in raw[group].items():
            _require(set(binding) == {"path", "sha256"} and not Path(binding["path"]).is_absolute() and ".." not in Path(binding["path"]).parts, f"{group} binding drift: {name}")
            target = project_root / binding["path"]; _require(target.is_file() and file_digest(target) == binding["sha256"], f"{group} digest mismatch: {name}")
    _require(raw["scope"] == {"species": list(SPECIES), "folds": list(FOLDS), "endpoints": list(ENDPOINTS), "predictor_count": 77, "architecture": "resmlp13"}, "Goal039 scope drift")
    _require(raw["mask"] == {"primary_threshold": 0.85, "diagnostic_thresholds": [0.80, 0.90], "blocks": {key: list(value) for key, value in BIOCLIM_BLOCKS.items()}, "mandatory_continuous": list(MANDATORY_CONTINUOUS), "categorical": list(CATEGORICAL), "shape_preserving": True, "complete_linkage": True, "medoid_tie_rule": "frozen_predictor_order"}, "Goal039 mask contract drift")
    from .predictor_sensitivity_conventional import (
        CONFIRMATION_ANALYSIS_ENDPOINTS as CONVENTIONAL_CONFIRMATION_ANALYSIS_ENDPOINTS,
        CONFIRMATION_NEW_ENDPOINTS as CONVENTIONAL_CONFIRMATION_NEW_ENDPOINTS,
        EXPECTED_PRIVATE_CORE_MANIFEST,
        FAMILIES as CONVENTIONAL_FAMILIES,
        PRODUCER_COMMIT,
        SCREEN_ENDPOINTS as CONVENTIONAL_SCREEN_ENDPOINTS,
        stage_counts,
    )
    expected_conventional = {
        "families": list(CONVENTIONAL_FAMILIES),
        "producer_commit": PRODUCER_COMMIT,
        "private_core_manifest_sha256": EXPECTED_PRIVATE_CORE_MANIFEST,
        "manifest_digest": "1bb5bcc7ea450d87a2ddb8b5ea3a11ac96163e8001e0a3cc11d2c6853b09b5bc",
        "parquet_sha256": "250a33d2111fc420e620535be113f14a6bd68ce26ae910b514571f397ebc2001",
        "runtime": {
            "python_relative": ".venv/bin/python",
            "python_major_minor": "3.12",
            "numpy": "2.5.1",
            "scipy": "1.16.3",
            "scikit_learn": "1.9.0",
            "torch": "2.13.0",
            "device": "cpu",
            "threads": 1,
            "blas_threads": 1,
        },
        "screen_endpoints": [f"{fraction}/{ladder}" for fraction, ladder in CONVENTIONAL_SCREEN_ENDPOINTS],
        "confirmation_new_endpoints": [f"{fraction}/{ladder}" for fraction, ladder in CONVENTIONAL_CONFIRMATION_NEW_ENDPOINTS],
        "confirmation_analysis_endpoints": [f"{fraction}/{ladder}" for fraction, ladder in CONVENTIONAL_CONFIRMATION_ANALYSIS_ENDPOINTS],
        "stages": {stage: stage_counts(stage) for stage in ("screen", "confirmation")},
        "decision_authority": False,
    }
    _require(raw["conventional"] == expected_conventional, "Goal039 conventional contract drift")
    _require(raw["execution"]["outer_attempted"] == raw["execution"]["outer_opened"] == 0 and raw["evidence"]["outer_attempted"] == raw["evidence"]["outer_opened"] == 0, "Goal039 outer boundary drift")
    return SensitivityConfig(source, project_root, raw)


def mask_audit(config: SensitivityConfig) -> dict[str, Any]:
    return load_frozen_mask_audit(config)


def _goal035_context(config: SensitivityConfig) -> tuple[Any, list[Any]]:
    from .final_inner_data import load_config as load_goal035_config, validate_bundle_inventory
    path = config.root / config.raw["authorities"]["goal035_config"]["path"]
    goal035 = load_goal035_config(path, root=config.root, require_receipt=True)
    aggregate = json.loads((config.root / goal035.raw["evidence"]["aggregate_receipt"]).read_text(encoding="utf-8")); canary = json.loads((config.root / goal035.raw["evidence"]["canary_receipt"]).read_text(encoding="utf-8"))
    _require(aggregate.get("success") is True and aggregate.get("config_digest") == goal035.config_digest and aggregate.get("cases") == 40 and aggregate.get("outer_attempted") == aggregate.get("outer_opened") == 0, "Goal035 aggregate gate failed")
    _require(canary.get("success") is True and canary.get("decision") == "pass" and canary.get("config_digest") == goal035.config_digest and canary.get("outer_attempted") == canary.get("outer_opened") == 0 and canary.get("runtime_digest") == aggregate.get("runtime_digest"), "Goal035 canary gate failed")
    bundles = validate_bundle_inventory(goal035.private_root, config=goal035)
    return goal035, bundles


def _goal035_control(bundle: Any, goal035: Any) -> np.ndarray:
    from .final_inner_data import leaf_identity, prepare_case, validate_leaf
    aggregate_path = goal035.root / goal035.raw["evidence"]["aggregate_receipt"]
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    prepared = prepare_case(bundle)
    identity = {"target": bundle.target, "held_fold": bundle.held_fold, "held_row_count": int(len(bundle.arrays["x_held"])), "bundle_digest": bundle.source_digest, "config_digest": goal035.config_digest, "runtime_digest": aggregate["runtime_digest"], "architecture": goal035.corrected_winner, "mask_digest": digest_value({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}), "aux_mask_digest": prepared["auxiliary_mask"].digest}
    path = goal035.private_root / "leaves" / leaf_identity(identity)
    validate_leaf(path, identity)
    predictions = np.load(path / "predictions.npy", allow_pickle=False)
    predictions = np.take(predictions, [METHODS.index(TARGET_METHOD), METHODS.index(MULTIHEAD_METHOD)], axis=2)
    return predictions


def _control_catalog(config: SensitivityConfig) -> Any:
    from .predictor_sensitivity_conventional import load_full28_controls

    conventional = config.raw["conventional"]
    return load_full28_controls(
        config.root / config.raw["authorities"]["goal036_private_parquet"]["path"],
        config.root / config.raw["authorities"]["goal036_private_manifest"]["path"],
        expected_manifest_digest=conventional["manifest_digest"],
        expected_parquet_sha256=conventional["parquet_sha256"],
        expected_producer_commit=conventional["producer_commit"],
        expected_private_core_manifest=conventional["private_core_manifest_sha256"],
    )


def _conventional_foundation(
    config: SensitivityConfig, audit: Mapping[str, Any]
) -> tuple[Mapping[str, Any], Any, Any, Any]:
    from dsdm_phase1.goal029_production import (
        ingest_production_foundation,
        load_goal029_config,
    )
    from .predictor_sensitivity_conventional import ZeroedContinuousProvider

    goal029 = load_goal029_config(
        config.root, config.root / config.raw["authorities"]["goal029_config"]["path"]
    )
    broker, provider, vault = ingest_production_foundation(config.root, goal029)
    _require(
        vault.attempted_open_count == vault.open_count == 0,
        "conventional foundation opened outer vault",
    )
    exclusions = {
        fold: tuple(audit["primary"][fold]["excluded_raw"]) for fold in FOLDS
    }
    return goal029, broker, provider, ZeroedContinuousProvider(provider, exclusions)


def _conventional_mask_digests(audit: Mapping[str, Any]) -> dict[str, str]:
    values = {fold: str(audit["primary"][fold]["mask_digest"]) for fold in FOLDS}
    _require(all(len(value) == 64 for value in values.values()), "conventional mask digest invalid")
    return values


def _conventional_child_command(
    config: SensitivityConfig,
    audit_path: Path,
    operation: str,
) -> tuple[list[str], dict[str, str]]:
    """Build the one-way child invocation for the locked conventional lane."""
    _require(operation in {"canary", "screen", "confirmation"}, "conventional child operation invalid")
    runtime = config.raw["conventional"].get("runtime")
    _require(isinstance(runtime, Mapping), "conventional runtime binding missing")
    python_relative = runtime.get("python_relative")
    _require(isinstance(python_relative, str) and not Path(python_relative).is_absolute(), "conventional runtime path invalid")
    executable = (config.root / python_relative).absolute()
    _require(executable.is_file(), "conventional runtime executable missing")
    _require(audit_path.is_file() and not audit_path.is_symlink(), "conventional child audit missing")
    env = dict(os.environ)
    src = str((config.root / "src").resolve())
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["DSDM_GOAL039_CONVENTIONAL_WORKER"] = "1"
    for name in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[name] = "1"
    command = [
        str(executable),
        "-m",
        "dsdm.predictor_sensitivity_conventional",
        "--worker-operation",
        operation,
        "--config",
        str(config.source_path),
        "--audit",
        str(audit_path),
    ]
    return command, env


def _dispatch_conventional(
    config: SensitivityConfig,
    audit_path: Path,
    operation: str,
) -> dict[str, Any]:
    """Run and validate one aggregate conventional child receipt."""
    from .predictor_sensitivity_conventional import validate_worker_receipt
    from dsdm_phase1.goal029_production import load_goal029_config

    _require(os.environ.get("DSDM_GOAL039_CONVENTIONAL_WORKER") != "1", "conventional worker recursion blocked")
    command, env = _conventional_child_command(config, audit_path, operation)
    try:
        completed = subprocess.run(
            command,
            cwd=config.root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise PredictorSensitivityError(f"conventional worker launch failed: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no child diagnostic"
        raise PredictorSensitivityError(f"conventional worker failed ({completed.returncode}): {detail[-2000:]}")
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = completed.stdout.strip()[-2000:]
        raise PredictorSensitivityError(f"conventional worker emitted invalid receipt: {detail}") from exc
    goal029_config = None
    if "authorities" in config.raw:
        goal029_config = load_goal029_config(
            config.root,
            config.root / config.raw["authorities"]["goal029_config"]["path"],
        )
    result = validate_worker_receipt(
        envelope,
        operation=operation,
        config_digest=config.raw["config_digest"],
        expected_runtime=config.raw["conventional"]["runtime"],
        goal029_config=goal029_config,
        expected_mask_authority=config.raw.get("mask_authority"),
    )
    # Preserve the child provenance without treating the child envelope as a
    # tracked scientific result.  Re-digest the parent-side aggregate after
    # adding this runtime binding.
    result = dict(result)
    child_result_receipt_digest = result.pop("receipt_digest", None)
    _require(
        isinstance(child_result_receipt_digest, str) and len(child_result_receipt_digest) == 64,
        "conventional child result receipt digest missing",
    )
    result["worker_runtime"] = dict(envelope["runtime"])
    result["worker_receipt_digest"] = envelope["receipt_digest"]
    result["worker_result_digest"] = envelope["result_digest"]
    result["child_result_receipt_digest"] = child_result_receipt_digest
    result["receipt_digest"] = digest_value(result)
    return result


def _run_conventional_canary(
    config: SensitivityConfig,
    audit: Mapping[str, Any],
    catalog: Any,
    goal029: Mapping[str, Any],
    broker: Any,
    provider: Any,
    reduced_provider: Any,
) -> dict[str, Any]:
    from dsdm_phase1.goal029_production import SEEDS_BY_FAMILY
    from .predictor_sensitivity_conventional import (
        FAMILIES,
        ConventionalLeaf,
        compare_reduced_repeats,
        diagnose_result_against_control,
        load_control_leaf,
        run_selected_leaf,
        validate_historical_control_diagnostics,
    )

    full_receipts = []
    family_receipts = []
    mask_digests = _conventional_mask_digests(audit)
    for family in FAMILIES:
        leaf = ConventionalLeaf(
            "sarcophilus_harrisii",
            "fraction100",
            "full",
            family,
            catalog.selected_candidate(
                "sarcophilus_harrisii", "fraction100", "full", family
            ),
            SEEDS_BY_FAMILY[family][0],
        )
        control = load_control_leaf(catalog, leaf)
        full = run_selected_leaf(
            catalog, leaf, broker, provider, goal029_config=goal029
        )
        full_second = run_selected_leaf(
            catalog, leaf, broker, provider, goal029_config=goal029
        )
        # Goal036 remains a sealed lineage/row/label control.  Its numerical
        # scores are recorded as cross-runtime diagnostics, never as a canary
        # equality gate or a reduced-minus-full baseline.
        full_receipt = diagnose_result_against_control(full, control)
        full_repeat = compare_reduced_repeats(full, full_second)
        _require(
            full_repeat["observation_digest"] == control.row_identity_digest,
            "conventional full canary row identity drift",
        )
        first = run_selected_leaf(
            catalog, leaf, broker, reduced_provider, goal029_config=goal029
        )
        second = run_selected_leaf(
            catalog, leaf, broker, reduced_provider, goal029_config=goal029
        )
        repeat = compare_reduced_repeats(first, second)
        _require(
            repeat["observation_digest"] == control.row_identity_digest,
            "conventional reduced canary row identity drift",
        )
        full_receipts.append(full_receipt)
        family_receipts.append(
            {
                "family": family,
                "candidate": leaf.candidate_id,
                "seed": leaf.seed_label,
                "historical_control_diagnostic": full_receipt,
                "full_repeat_receipt_digest": full_repeat["receipt_digest"],
                "reduced_repeat_receipt_digest": repeat["receipt_digest"],
                "observation_digest": control.row_identity_digest,
                "reduced_value_digest": repeat["value_digest"],
                "mask_digest_by_fold": mask_digests,
            }
        )
    replay = validate_historical_control_diagnostics(full_receipts)
    receipt = {
        "schema_version": "goal039-conventional-canary-v2",
        "families": family_receipts,
        "family_count": len(family_receipts),
        "full28_replay": replay,
        "full28_replays": len(full_receipts),
        "current_full_repeat_fits": 2 * len(family_receipts),
        "reduced_repeat_fits": 2 * len(family_receipts),
        "control_manifest_digest": catalog.manifest_digest,
        "config_digest": config.raw["config_digest"],
        "source_fingerprint": digest_value(config.raw["execution_sources"]),
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    return receipt


def _conventional_identities(
    config: SensitivityConfig,
    audit: Mapping[str, Any],
    catalog: Any,
    stage: str,
) -> tuple[tuple[Any, ...], dict[Any, Mapping[str, Any]]]:
    from .predictor_sensitivity_conventional import (
        build_conventional_plan,
        reduced_leaf_identity,
    )

    leaves = build_conventional_plan(catalog, stage)
    source_fingerprint = digest_value(config.raw["execution_sources"])
    mask_digests = _conventional_mask_digests(audit)
    identities = {
        leaf: reduced_leaf_identity(
            leaf,
            stage=stage,
            config_digest=config.raw["config_digest"],
            source_fingerprint=source_fingerprint,
            control_manifest_digest=catalog.manifest_digest,
            mask_digest_by_fold=mask_digests,
        )
        for leaf in leaves
    }
    _require(len(identities) == len(leaves), "conventional identity collision")
    return leaves, identities


def _run_conventional_stage(
    config: SensitivityConfig,
    audit: Mapping[str, Any],
    catalog: Any,
    stage: str,
    goal029: Mapping[str, Any],
    broker: Any,
    reduced_provider: Any,
    provider: Any | None = None,
) -> dict[str, Any]:
    from .predictor_sensitivity_conventional import (
        CONFIRMATION_ANALYSIS_ENDPOINTS,
        SCREEN_ENDPOINTS as CONVENTIONAL_SCREEN_ENDPOINTS,
        aggregate_family_effects,
        build_conventional_analysis_plan,
        inventory_status,
        load_full_leaf,
        load_reduced_leaf as load_conventional_leaf,
        result_prediction_digest,
        run_selected_leaf,
        stage_counts,
        write_reduced_leaf as write_conventional_leaf,
        write_full_leaf,
        validate_current_result,
    )

    leaves, identities = _conventional_identities(config, audit, catalog, stage)
    from .predictor_sensitivity_conventional import full_leaf_identity
    full_identities = {
        leaf: full_leaf_identity(
            leaf,
            stage=stage,
            config_digest=config.raw["config_digest"],
            source_fingerprint=digest_value(config.raw["execution_sources"]),
            control_manifest_digest=catalog.manifest_digest,
            mask_digest_by_fold=_conventional_mask_digests(audit),
        )
        for leaf in leaves
    }
    leaf_root = config.private_root / "conventional" / "leaves"
    reduced_root = leaf_root / "reduced"
    full_root = leaf_root / "full"
    results: dict[Any, Any] = {}
    full_results: dict[Any, Any] = {}
    current_full_provider = provider if provider is not None else reduced_provider
    for leaf in leaves:
        identity = identities[leaf]
        path = reduced_root / str(identity["identity_digest"])
        if path.exists() or path.is_symlink():
            try:
                results[leaf] = load_conventional_leaf(reduced_root, identity)
                validate_current_result(results[leaf])
            except Exception as exc:
                raise PredictorSensitivityError(
                    f"corrupt conventional leaf: {identity['identity_digest']}"
                ) from exc
        else:
            result = run_selected_leaf(
                catalog,
                leaf,
                broker,
                reduced_provider,
                goal029_config=goal029,
            )
            write_conventional_leaf(reduced_root, identity, result)
            results[leaf] = result
            validate_current_result(result)
        full_identity = full_identities[leaf]
        full_path = full_root / str(full_identity["identity_digest"])
        if full_path.exists() or full_path.is_symlink():
            try:
                full_result = load_full_leaf(full_root, full_identity)
            except Exception as exc:
                raise PredictorSensitivityError(
                    f"corrupt conventional full leaf: {full_identity['identity_digest']}"
                ) from exc
        else:
            full_result = run_selected_leaf(catalog, leaf, broker, current_full_provider, goal029_config=goal029)
            write_full_leaf(full_root, full_identity, full_result)
        validate_current_result(full_result)
        full_results[leaf] = full_result
    reduced_status = inventory_status(reduced_root, tuple(identities.values()))
    full_status = inventory_status(full_root, tuple(full_identities.values()))
    _require(
        reduced_status["complete"] == len(leaves)
        and reduced_status["missing"] == reduced_status["invalid"] == 0
        and full_status["complete"] == len(leaves)
        and full_status["missing"] == full_status["invalid"] == 0,
        "conventional stage inventory incomplete",
    )

    reused: dict[Any, Any] = {}
    reused_identities: dict[Any, Mapping[str, Any]] = {}
    analysis_endpoints = CONVENTIONAL_SCREEN_ENDPOINTS
    if stage == "confirmation":
        screen_leaves, screen_identities = _conventional_identities(
            config, audit, catalog, "screen"
        )
        for leaf in screen_leaves:
            if (leaf.fraction_id, leaf.ladder_id) != ("fraction100", "full"):
                continue
            identity = screen_identities[leaf]
            try:
                reused[leaf] = load_conventional_leaf(reduced_root, identity)
            except Exception as exc:
                raise PredictorSensitivityError(
                    "confirmation requires complete screen full-endpoint leaves"
                ) from exc
            reused_identities[leaf] = identity
            full_identity = full_leaf_identity(
                leaf,
                stage="screen",
                config_digest=config.raw["config_digest"],
                source_fingerprint=digest_value(config.raw["execution_sources"]),
                control_manifest_digest=catalog.manifest_digest,
                mask_digest_by_fold=_conventional_mask_digests(audit),
            )
            try:
                full_results[leaf] = load_full_leaf(full_root, full_identity)
            except Exception as exc:
                raise PredictorSensitivityError(
                    "confirmation requires complete screen full-endpoint leaves"
                ) from exc
            full_identities[leaf] = full_identity
        _require(len(reused) == 128, "confirmation screen-full reuse inventory drift")
        results.update(reused)
        identities.update(reused_identities)
        analysis_endpoints = CONFIRMATION_ANALYSIS_ENDPOINTS

    _require(
        set(results) == set(build_conventional_analysis_plan(catalog, stage)),
        "conventional analysis inventory drift",
    )
    _require(
        stage_counts(stage) == config.raw["conventional"]["stages"][stage],
        "conventional stage arithmetic drift",
    )

    context = aggregate_family_effects(
        catalog,
        results,
        endpoints=analysis_endpoints,
        full_results=full_results,
    )
    inventory_digest = digest_value(
        sorted(str(identity["identity_digest"]) for identity in identities.values())
    )
    full_inventory_digest = digest_value(
        sorted(str(identity["identity_digest"]) for identity in full_identities.values())
    )
    paired_inventory_digest = digest_value(
        sorted(
            (
                str(identities[leaf]["identity_digest"]),
                str(full_identities[leaf]["identity_digest"]),
            )
            for leaf in results
        )
    )
    content_digest = digest_value(
        sorted(
            (
                str(identities[leaf]["identity_digest"]),
                result_prediction_digest(result),
                result_prediction_digest(full_results[leaf]),
            )
            for leaf, result in results.items()
        )
    )
    receipt = {
        "schema_version": f"goal039-conventional-{stage}-v2",
        "stage": stage,
        "new_stage": stage_counts(stage),
        "new_leaf_count": len(leaves),
        "reused_screen_full_leaves": len(reused),
        "analysis_leaf_count": len(results),
        "analysis_endpoints": [f"{a}/{b}" for a, b in analysis_endpoints],
        "inventory_digest": inventory_digest,
        "reduced_inventory_digest": inventory_digest,
        "full_inventory_digest": full_inventory_digest,
        "paired_inventory_digest": paired_inventory_digest,
        "content_digest": content_digest,
        "paired_leaf_count": len(results),
        "context": context,
        "context_digest": context["receipt_digest"],
        "control_manifest_digest": catalog.manifest_digest,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    return receipt


def canary(config: SensitivityConfig) -> dict[str, Any]:
    audit_path = config.tracked_root / "mask_audit.json"; _require(audit_path.is_file(), "mask audit required before canary")
    audit = load_frozen_mask_audit(config, audit_path); goal035, bundles = _goal035_context(config); sentinel = next(bundle for bundle in bundles if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00"); mask = np.asarray(audit["primary"][sentinel.held_fold]["encoded_columns"], dtype=bool)
    goal035_path = config.root / config.raw["authorities"]["goal035_config"]["path"]
    # Replay the immutable full-substrate sentinel once with an all-ones mask.
    seed_index = SEEDS.index(31031)
    full_control = _goal035_control(sentinel, goal035)[seed_index, [ENDPOINTS.index(endpoint) for endpoint in SCREEN_ENDPOINTS]]
    ones = np.ones(PREDICTOR_COUNT, dtype=bool)
    full_replay_result = run_neural_stage_case(sentinel, ones, goal035_path, endpoints=SCREEN_ENDPOINTS, seeds=(31031,), max_epochs=300, patience=30)
    full_replay = full_replay_result["predictions"]
    _require(np.array_equal(full_control, full_replay), "full-substrate canary replay differs from Goal035 control")
    reduced_a_result = run_neural_stage_case(sentinel, mask, goal035_path, endpoints=SCREEN_ENDPOINTS, seeds=(31031,), max_epochs=300, patience=30)
    reduced_b_result = run_neural_stage_case(sentinel, mask, goal035_path, endpoints=SCREEN_ENDPOINTS, seeds=(31031,), max_epochs=300, patience=30)
    reduced_a, reduced_b = reduced_a_result["predictions"], reduced_b_result["predictions"]
    deterministic_a = _without_wall(reduced_a_result["metadata"])
    deterministic_b = _without_wall(reduced_b_result["metadata"])
    _require(deterministic_a == deterministic_b, "reduced canary metadata repeat mismatch")
    for metadata in (full_replay_result["metadata"], reduced_a_result["metadata"], reduced_b_result["metadata"]):
        _require(metadata["logical_artifacts"] == 7 and metadata["physical_fits"] == 14 and metadata["support_mask_digests"] == metadata["reduced_support_mask_digests"], "canary lifecycle evidence drift")
    # Conventional fitting is intentionally isolated in the project-lock
    # interpreter.  Only its validated aggregate receipt crosses this edge.
    conventional = _dispatch_conventional(config, audit_path, "canary")
    receipt = canary_compare(full_control, full_replay, reduced_a, reduced_b, mask)
    receipt.update({"config_digest": config.raw["config_digest"], "sentinel": {"target": sentinel.target, "held_fold": sentinel.held_fold, "bundle_digest": sentinel.source_digest}, "source_fingerprint": digest_value(config.raw["execution_sources"]), "mask_digest": audit["primary"][sentinel.held_fold]["mask_digest"], "conventional": conventional, "conventional_canary_digest": conventional["receipt_digest"]})
    receipt["runtime_digest"] = reduced_a_result["metadata"]["runtime_digest"]
    receipt["lifecycle"] = {"logical_artifacts": 7, "physical_fits": 14, "support_mask_digest": digest_value(reduced_a_result["metadata"]["support_mask_digests"]), "deterministic_metadata_digest": digest_value(deterministic_a)}
    receipt["receipt_digest"] = digest_value({key: value for key, value in receipt.items() if key != "receipt_digest"})
    _write_json(config.tracked_root / "canary.json", receipt)
    return receipt


def _validate_canary_stage_gate(
    config: SensitivityConfig,
    audit: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    sentinel: Any,
    runtime_digest: str,
) -> None:
    """Reject stale or incomplete canary evidence before model execution."""
    def is_digest(value: Any) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    conventional = receipt.get("conventional", {})
    lifecycle = receipt.get("lifecycle", {})
    _require(
        receipt.get("decision") == "pass"
        and receipt.get("deterministic") is True
        and receipt.get("finite") is True
        and receipt.get("full_control_replayed") is True
        and receipt.get("full_control_bitwise_match") is True
        and receipt.get("reduced_repeats") == 2
        and receipt.get("reduced_repeats_bitwise_match") is True
        and receipt.get("config_digest") == config.raw["config_digest"]
        and receipt.get("source_fingerprint")
        == digest_value(config.raw["execution_sources"])
        and receipt.get("runtime_digest") == runtime_digest
        and receipt.get("mask_digest")
        == audit["primary"][sentinel.held_fold]["mask_digest"]
        and receipt.get("sentinel")
        == {
            "target": sentinel.target,
            "held_fold": sentinel.held_fold,
            "bundle_digest": sentinel.source_digest,
        }
        and lifecycle.get("logical_artifacts") == 7
        and lifecycle.get("physical_fits") == 14
        and is_digest(lifecycle.get("support_mask_digest"))
        and is_digest(lifecycle.get("deterministic_metadata_digest"))
        and conventional.get("schema_version")
        == "goal039-conventional-canary-v2"
        and conventional.get("family_count") == 4
        and conventional.get("full28_replays") == 4
        and conventional.get("current_full_repeat_fits") == 8
        and conventional.get("reduced_repeat_fits") == 8
        and conventional.get("config_digest") == config.raw["config_digest"]
        and conventional.get("source_fingerprint")
        == digest_value(config.raw["execution_sources"])
        and conventional.get("mask_authority") == config.raw["mask_authority"]
        and conventional.get("outer_attempted")
        == conventional.get("outer_opened")
        == 0
        and receipt.get("conventional_canary_digest")
        == conventional.get("receipt_digest"),
        "current complete neural and conventional canary required before model stage",
    )


def _run_stage(config: SensitivityConfig, stage: str) -> dict[str, Any]:
    mask_path = config.tracked_root / "mask_audit.json"
    _require(mask_path.is_file(), "mask audit required before model stage")
    audit = load_frozen_mask_audit(config, mask_path)
    canary_receipt = _load_receipt(
        config.tracked_root / "canary.json", "goal039-canary-v2"
    )
    goal035, bundles = _goal035_context(config)
    sentinel = next(
        bundle
        for bundle in bundles
        if bundle.target == "sarcophilus_harrisii" and bundle.held_fold == "fold00"
    )
    from .final_inner_data import runtime_attestation

    runtime_digest = digest_value(runtime_attestation(goal035, strict=True))
    _validate_canary_stage_gate(
        config,
        audit,
        canary_receipt,
        sentinel=sentinel,
        runtime_digest=runtime_digest,
    )
    screen_receipt: Mapping[str, Any] | None = None
    if stage == "confirmation":
        screen_receipt = _load_receipt(
            config.tracked_root / "screen.json", "goal039-screen-v2"
        )
        assert_confirmation_eligible(screen_receipt)
    endpoints = SCREEN_ENDPOINTS if stage == "screen" else CONFIRMATION_ENDPOINTS; seeds = SCREEN_SEEDS if stage == "screen" else CONFIRMATION_SEEDS; cases_for_metrics: list[dict[str, Any]] = []
    source_fingerprint = digest_value(config.raw["execution_sources"])
    for bundle in bundles:
        mask = audit["primary"][bundle.held_fold]["encoded_columns"]; leaf_by_seed: dict[int, np.ndarray] = {}; all_present = True
        for seed in seeds:
            identity = {"stage": stage, "species": bundle.target, "held_fold": bundle.held_fold, "seed": int(seed), "mask_digest": audit["primary"][bundle.held_fold]["mask_digest"], "bundle_digest": bundle.source_digest, "endpoints": list(endpoints), "methods": [TARGET_METHOD, MULTIHEAD_METHOD], "config_digest": config.raw["config_digest"], "source_fingerprint": source_fingerprint, "runtime_digest": runtime_digest}; path = config.private_root / "leaves" / digest_value(identity)
            if not path.is_dir(): all_present = False; continue
            values, metadata = load_reduced_leaf(path); _require(metadata.get("identity") == identity, "reduced leaf identity drift"); leaf_by_seed[int(seed)] = values
        if not all_present:
            for seed in seeds:
                if int(seed) in leaf_by_seed:
                    continue
                reduced_stage = run_neural_stage_case(bundle, mask, config.root / config.raw["authorities"]["goal035_config"]["path"], endpoints=endpoints, seeds=(seed,))
                leaf_values = reduced_stage["predictions"]
                identity = {"stage": stage, "species": bundle.target, "held_fold": bundle.held_fold, "seed": int(seed), "mask_digest": audit["primary"][bundle.held_fold]["mask_digest"], "bundle_digest": bundle.source_digest, "endpoints": list(endpoints), "methods": [TARGET_METHOD, MULTIHEAD_METHOD], "config_digest": config.raw["config_digest"], "source_fingerprint": source_fingerprint, "runtime_digest": runtime_digest}
                path = config.private_root / "leaves" / digest_value(identity)
                leaf_by_seed[int(seed)] = leaf_values.astype(np.float32)
                write_reduced_leaf(path, identity, {"predictions": leaf_values, "metadata": reduced_stage["metadata"]})
        reduced = np.zeros((len(SEEDS), len(ENDPOINTS), 2, len(bundle.arrays["y_held"])), dtype=np.float32); seed_positions = {int(value): index for index, value in enumerate(SEEDS)}
        for si, seed in enumerate(seeds):
            for ei, endpoint in enumerate(endpoints):
                reduced[seed_positions[int(seed)], ENDPOINTS.index(endpoint)] = leaf_by_seed[int(seed)][ei]
        full = _goal035_control(bundle, goal035)
        for endpoint in endpoints:
            cases_for_metrics.append({"species": bundle.target, "fold": bundle.held_fold, "endpoint": endpoint, "y": bundle.arrays["y_held"].astype(np.int8), "reduced": reduced, "full": full})
    records = paired_effect_records(cases_for_metrics, endpoints=endpoints, seeds=seeds)
    lanes = reconstruct_effect_lanes(records, reserved_seeds=CONFIRMATION_SEEDS)
    delta_u_guard = (
        lanes["delta_u"]["aggregate_auc"] >= 0.0
        and lanes["delta_u"]["aggregate_tss_value"] >= 0.0
        if stage == "confirmation"
        else True
    )
    if stage == "screen":
        raw_delta_u_gate = screen_gate(lanes["delta_u"])
        raw_delta_i_gate = screen_gate(lanes["delta_i"])
        u_gate = raw_delta_u_gate
        i_gate = raw_delta_i_gate
        screen_eligibility = None
        screen_receipt_digest = None
    else:
        _require(screen_receipt is not None, "screen receipt missing")
        screen_eligibility = {
            "eligible_delta_u": bool(screen_receipt.get("eligible_delta_u")),
            "eligible_delta_i": bool(screen_receipt.get("eligible_delta_i")),
        }
        screen_receipt_digest = screen_receipt["receipt_digest"]
        raw_delta_u_gate = confirmation_gate(lanes["delta_u"])
        raw_delta_i_gate = confirmation_gate(lanes["delta_i"])
        u_gate = bool(
            screen_eligibility["eligible_delta_u"]
            and raw_delta_u_gate
        )
        i_gate = bool(
            screen_eligibility["eligible_delta_i"]
            and raw_delta_i_gate
        )
    # Keep all conventional fitting in the project-lock interpreter; the
    # parent retains authority over neural metrics and Goal039 gates.
    conventional = _dispatch_conventional(config, mask_path, stage)
    effective_delta_i = bool(i_gate and delta_u_guard)
    summary = {"schema_version": f"goal039-{stage}-v2", "stage": stage, "delta_u": lanes["delta_u"], "delta_i": lanes["delta_i"], "raw_delta_u_gate": bool(raw_delta_u_gate), "raw_delta_i_gate": bool(raw_delta_i_gate), "eligible_delta_u": bool(u_gate), "raw_eligible_delta_i": bool(i_gate), "effective_eligible_delta_i": effective_delta_i, "eligible_delta_i": effective_delta_i, "eligible": bool(u_gate or effective_delta_i), "delta_u_guard_passed": bool(delta_u_guard), "delta_i_rejection_reason": "target_only_degradation_guard_failed" if bool(i_gate) and not delta_u_guard else None, "screen_eligibility": screen_eligibility, "screen_receipt_digest": screen_receipt_digest, "records": len(records), "conventional_context": conventional, "conventional_context_digest": conventional["receipt_digest"], "decision_basis": "neural_only", "outer_attempted": 0, "outer_opened": 0}
    summary["receipt_digest"] = digest_value(summary)
    _write_json(config.tracked_root / f"{stage}.json", summary)
    return summary


def plan(config: SensitivityConfig) -> dict[str, Any]:
    value = build_plan()
    value["conventional"] = config.raw["conventional"]["stages"]
    value.update({"config_digest": config.raw["config_digest"], "outer_attempted": 0, "outer_opened": 0})
    return value


def _neural_status(config: SensitivityConfig) -> dict[str, Any]:
    planned = {
        "screen": int(config.raw["execution"]["screen_cases"]),
        "confirmation": int(config.raw["execution"]["confirmation_cases"]),
    }
    complete = {"screen": 0, "confirmation": 0}
    invalid = 0
    root = config.private_root / "leaves"
    expected_by_stage: dict[str, set[str]] = {"screen": set(), "confirmation": set()}
    audit_path = config.tracked_root / "mask_audit.json"
    if audit_path.is_file():
        audit = load_frozen_mask_audit(config, audit_path)
        goal035, bundles = _goal035_context(config)
        from .final_inner_data import runtime_attestation
        runtime_digest = digest_value(runtime_attestation(goal035, strict=True))
        source_fingerprint = digest_value(config.raw["execution_sources"])
        for stage, stage_seeds, stage_endpoints in (("screen", SCREEN_SEEDS, SCREEN_ENDPOINTS), ("confirmation", CONFIRMATION_SEEDS, CONFIRMATION_ENDPOINTS)):
            for bundle in bundles:
                for seed in stage_seeds:
                    identity = {"stage": stage, "species": bundle.target, "held_fold": bundle.held_fold, "seed": int(seed), "mask_digest": audit["primary"][bundle.held_fold]["mask_digest"], "bundle_digest": bundle.source_digest, "endpoints": list(stage_endpoints), "methods": [TARGET_METHOD, MULTIHEAD_METHOD], "config_digest": config.raw["config_digest"], "source_fingerprint": source_fingerprint, "runtime_digest": runtime_digest}
                    expected_by_stage[stage].add(digest_value(identity))
    if root.is_dir() and not expected_by_stage["screen"] and not expected_by_stage["confirmation"]:
        invalid = len(list(root.iterdir()))
    elif root.is_dir():
        for path in root.iterdir():
            if not path.is_dir():
                invalid += 1
                continue
            try:
                values, metadata = load_reduced_leaf(path)
                identity = metadata.get("identity", {})
                stage = identity.get("stage")
                expected = SCREEN_ENDPOINTS if stage == "screen" else CONFIRMATION_ENDPOINTS if stage == "confirmation" else ()
                _require(
                    values.ndim == 3 and stage in planned
                    and tuple(identity.get("endpoints", expected)) == tuple(expected)
                    and tuple(identity.get("methods", (TARGET_METHOD, MULTIHEAD_METHOD))) == (TARGET_METHOD, MULTIHEAD_METHOD)
                    and identity.get("species") in SPECIES and identity.get("held_fold") in FOLDS
                    and int(identity.get("seed")) in (SCREEN_SEEDS if stage == "screen" else CONFIRMATION_SEEDS),
                    "reduced leaf status scope drift",
                )
                if path.name != digest_value(identity) or path.name not in expected_by_stage[stage]:
                    raise PredictorSensitivityError("unexpected reduced leaf identity")
                complete[str(stage)] += 1
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                invalid += 1
    _require(all(complete[stage] <= planned[stage] for stage in planned), "neural leaf inventory exceeds contract")
    stages = {
        stage: {
            "planned": planned[stage],
            "complete": complete[stage],
            "missing": planned[stage] - complete[stage],
        }
        for stage in planned
    }
    return {
        "planned": sum(planned.values()),
        "complete": sum(complete.values()),
        "missing": sum(planned.values()) - sum(complete.values()),
        "invalid": invalid,
        "stages": stages,
    }


def _conventional_status(config: SensitivityConfig) -> dict[str, Any]:
    from .predictor_sensitivity_conventional import full_leaf_identity, inventory_status

    arithmetic = config.raw["conventional"]["stages"]
    planned = sum(int(arithmetic[stage]["leaves"]) for stage in ("screen", "confirmation"))
    leaf_root = config.private_root / "conventional" / "leaves"
    reduced_root = leaf_root / "reduced"
    full_root = leaf_root / "full"
    audit_path = config.tracked_root / "mask_audit.json"
    if not audit_path.is_file():
        existing = list(leaf_root.iterdir()) if leaf_root.is_dir() else []
        return {
            "planned": planned,
            "complete": 0,
            "missing": planned,
            "invalid": len(existing),
            "reduced": {"complete": 0, "missing": planned, "invalid": len(existing)},
            "full": {"complete": 0, "missing": planned, "invalid": len(existing)},
            "unexpected": len(existing),
            "stages": {
                stage: {
                    **arithmetic[stage],
                    "planned": arithmetic[stage]["leaves"],
                    "complete": 0,
                    "missing": arithmetic[stage]["leaves"],
                    "invalid": 0,
                }
                for stage in ("screen", "confirmation")
            },
        }
    audit = load_frozen_mask_audit(config, audit_path)
    catalog = _control_catalog(config)
    stage_rows: dict[str, Any] = {}
    expected_digests: set[str] = set()
    for stage in ("screen", "confirmation"):
        leaves, identities = _conventional_identities(config, audit, catalog, stage)
        full_identities = {
            leaf: full_leaf_identity(
                leaf,
                stage=stage,
                config_digest=config.raw["config_digest"],
                source_fingerprint=digest_value(config.raw["execution_sources"]),
                control_manifest_digest=catalog.manifest_digest,
                mask_digest_by_fold=_conventional_mask_digests(audit),
            )
            for leaf in leaves
        }
        reduced_receipt = inventory_status(reduced_root, tuple(identities.values()))
        full_receipt = inventory_status(full_root, tuple(full_identities.values()))
        expected_digests.update(str(value["identity_digest"]) for value in identities.values())
        expected_digests.update(str(value["identity_digest"]) for value in full_identities.values())
        stage_rows[stage] = {
            **arithmetic[stage],
            "planned": reduced_receipt["planned"],
            "complete": min(reduced_receipt["complete"], full_receipt["complete"]),
            "missing": max(reduced_receipt["missing"], full_receipt["missing"]),
            "invalid": reduced_receipt["invalid"] + full_receipt["invalid"],
            "reduced": reduced_receipt,
            "full": full_receipt,
            "inventory_digest": digest_value({"reduced": reduced_receipt["complete_inventory_digest"], "full": full_receipt["complete_inventory_digest"]}),
        }
    existing = {
        path.name
        for root in (reduced_root, full_root)
        if root.is_dir()
        for path in root.iterdir()
    }
    unexpected = existing - expected_digests
    return {
        "planned": planned,
        "complete": sum(stage_rows[stage]["complete"] for stage in stage_rows),
        "missing": sum(stage_rows[stage]["missing"] for stage in stage_rows),
        "invalid": sum(stage_rows[stage]["invalid"] for stage in stage_rows) + len(unexpected),
        "unexpected": len(unexpected),
        "stages": stage_rows,
    }


def status(config: SensitivityConfig) -> dict[str, Any]:
    return {
        "neural": _neural_status(config),
        "conventional": _conventional_status(config),
        "outer_attempted": 0,
        "outer_opened": 0,
    }


def _load_receipt(path: Path, schema: str) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), f"missing receipt: {path.name}")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictorSensitivityError(f"invalid receipt: {path.name}") from exc
    body = dict(receipt)
    claimed = body.pop("receipt_digest", None)
    _require(
        receipt.get("schema_version") == schema
        and claimed == digest_value(body)
        and receipt.get("outer_attempted") == receipt.get("outer_opened") == 0,
        f"receipt integrity drift: {path.name}",
    )
    return receipt


def decision_table(
    screen: Mapping[str, Any], confirmation: Mapping[str, Any] | None
) -> str:
    if confirmation is not None:
        _require(
            confirmation.get("screen_receipt_digest") == screen.get("receipt_digest")
            and confirmation.get("screen_eligibility")
            == {
                "eligible_delta_u": bool(screen.get("eligible_delta_u")),
                "eligible_delta_i": bool(screen.get("eligible_delta_i")),
            },
            "confirmation screen-lane binding drift",
        )
    if confirmation is None:
        return "retain_full28"
    if bool(screen.get("eligible_delta_i")) and bool(confirmation.get("effective_eligible_delta_i", confirmation.get("eligible_delta_i"))):
        return "propose_reduced_panel_transfer"
    if bool(screen.get("eligible_delta_u")) and bool(confirmation.get("eligible_delta_u")):
        return "propose_reduced_panel_generalisation"
    if bool(screen.get("eligible_delta_i")) and bool(confirmation.get("raw_eligible_delta_i")) and not bool(confirmation.get("delta_u_guard_passed", True)):
        return "retain_full28_delta_i_guard_rejected"
    return "retain_full28"


def finalize(config: SensitivityConfig) -> dict[str, Any]:
    screen = _load_receipt(config.tracked_root / "screen.json", "goal039-screen-v2")
    screen_eligible = bool(
        screen.get("eligible_delta_u") or screen.get("eligible_delta_i")
    )
    confirmation_path = config.tracked_root / "confirmation.json"
    confirmation = (
        _load_receipt(confirmation_path, "goal039-confirmation-v2")
        if confirmation_path.is_file()
        else None
    )
    _require(
        not screen_eligible or confirmation is not None,
        "eligible screen requires completed confirmation",
    )
    if confirmation is not None:
        _require(
            confirmation.get("screen_receipt_digest") == screen["receipt_digest"]
            and confirmation.get("screen_eligibility")
            == {
                "eligible_delta_u": bool(screen.get("eligible_delta_u")),
                "eligible_delta_i": bool(screen.get("eligible_delta_i")),
            },
            "confirmation screen-lane binding drift",
        )
    inventory = status(config)
    _require(
        inventory["neural"]["invalid"] == 0
        and inventory["conventional"]["invalid"] == 0
        and inventory["neural"]["stages"]["screen"]["complete"]
        == config.raw["execution"]["screen_cases"]
        and inventory["conventional"]["stages"]["screen"]["complete"]
        == config.raw["conventional"]["stages"]["screen"]["leaves"],
        "screen inventory incomplete",
    )
    if confirmation is not None:
        _require(
            inventory["neural"]["stages"]["confirmation"]["complete"]
            == config.raw["execution"]["confirmation_cases"]
            and inventory["conventional"]["stages"]["confirmation"]["complete"]
            == config.raw["conventional"]["stages"]["confirmation"]["leaves"],
            "confirmation inventory incomplete",
        )
    conventional = {
        "screen": {
            key: screen["conventional_context"][key]
            for key in (
                "receipt_digest",
                "inventory_digest",
                "content_digest",
                "context_digest",
            )
        },
        "confirmation": (
            {
                key: confirmation["conventional_context"][key]
                for key in (
                    "receipt_digest",
                    "inventory_digest",
                    "content_digest",
                    "context_digest",
                )
            }
            if confirmation is not None
            else None
        ),
        "decision_authority": False,
    }
    aggregate = {
        "schema_version": "goal039-aggregate-v1",
        "config_digest": config.raw["config_digest"],
        "source_fingerprint": digest_value(config.raw["execution_sources"]),
        "screen_receipt_digest": screen["receipt_digest"],
        "confirmation_receipt_digest": (
            confirmation["receipt_digest"] if confirmation is not None else None
        ),
        "screen": screen,
        "confirmation": confirmation,
        "conventional": conventional,
        "inventory": inventory,
        "decision_basis": "neural_only",
        "decision": decision_table(screen, confirmation),
        "decision_evidence": {
            "screen_lane_eligible_delta_u": bool(screen.get("eligible_delta_u")),
            "screen_lane_eligible_delta_i": bool(screen.get("eligible_delta_i")),
            "confirmation_raw_delta_u_gate": bool(confirmation and confirmation.get("raw_delta_u_gate")),
            "confirmation_raw_delta_i_gate": bool(confirmation and confirmation.get("raw_delta_i_gate")),
            "confirmation_delta_u_guard_passed": bool(confirmation and confirmation.get("delta_u_guard_passed")),
            "confirmation_effective_delta_i": bool(confirmation and confirmation.get("effective_eligible_delta_i")),
            "delta_i_rejection_reason": confirmation.get("delta_i_rejection_reason") if confirmation else None,
        },
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    aggregate["receipt_digest"] = digest_value(aggregate)
    _write_json(config.tracked_root / "aggregate.json", aggregate)
    return aggregate


def validate(config: SensitivityConfig) -> dict[str, Any]:
    aggregate = _load_receipt(
        config.tracked_root / "aggregate.json", "goal039-aggregate-v1"
    )
    screen = _load_receipt(config.tracked_root / "screen.json", "goal039-screen-v2")
    confirmation_path = config.tracked_root / "confirmation.json"
    confirmation = (
        _load_receipt(confirmation_path, "goal039-confirmation-v2")
        if confirmation_path.is_file()
        else None
    )
    current = status(config)
    expected_decision_evidence = {
        "screen_lane_eligible_delta_u": bool(screen.get("eligible_delta_u")),
        "screen_lane_eligible_delta_i": bool(screen.get("eligible_delta_i")),
        "confirmation_raw_delta_u_gate": bool(confirmation and confirmation.get("raw_delta_u_gate")),
        "confirmation_raw_delta_i_gate": bool(confirmation and confirmation.get("raw_delta_i_gate")),
        "confirmation_delta_u_guard_passed": bool(confirmation and confirmation.get("delta_u_guard_passed")),
        "confirmation_effective_delta_i": bool(confirmation and confirmation.get("effective_eligible_delta_i")),
        "delta_i_rejection_reason": confirmation.get("delta_i_rejection_reason") if confirmation else None,
    }
    _require(
        aggregate.get("config_digest") == config.raw["config_digest"]
        and aggregate.get("source_fingerprint")
        == digest_value(config.raw["execution_sources"])
        and aggregate.get("screen_receipt_digest") == screen["receipt_digest"]
        and aggregate.get("confirmation_receipt_digest")
        == (confirmation["receipt_digest"] if confirmation else None)
        and aggregate.get("inventory") == current
        and aggregate.get("decision_basis") == "neural_only"
        and aggregate.get("decision") == decision_table(screen, confirmation)
        and aggregate.get("decision_evidence") == expected_decision_evidence
        and aggregate.get("conventional", {}).get("decision_authority") is False,
        "Goal039 aggregate validation failed",
    )
    for stage, receipt in (("screen", screen), ("confirmation", confirmation)):
        if receipt is None:
            continue
        context = receipt.get("conventional_context", {})
        bound = aggregate["conventional"][stage]
        _require(
            receipt.get("decision_basis") == "neural_only"
            and context.get("receipt_digest")
            == receipt.get("conventional_context_digest")
            and all(bound.get(key) == context.get(key) for key in bound),
            f"conventional {stage} binding drift",
        )
    receipt = {
        "schema_version": "goal039-validation-v1",
        "success": True,
        "decision": aggregate["decision"],
        "aggregate_receipt_digest": aggregate["receipt_digest"],
        "conventional_decision_authority": False,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    return receipt


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("plan", "mask-audit", "canary", "run-screen", "status", "run-confirmation", "finalize", "validate")); parser.add_argument("--config", default="config/dsdm_predictor_substrate_sensitivity.json"); args = parser.parse_args(argv); config = load_config(args.config)
    if args.command == "plan": value = plan(config)
    elif args.command == "mask-audit": value = mask_audit(config)
    elif args.command == "canary": value = canary(config)
    elif args.command == "run-screen": value = _run_stage(config, "screen")
    elif args.command == "run-confirmation": value = _run_stage(config, "confirmation")
    elif args.command == "status": value = status(config)
    elif args.command == "finalize": value = finalize(config)
    elif args.command == "validate": value = validate(config)
    print(json.dumps(value, sort_keys=True)); return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())


__all__ = ["BIOCLIM_BLOCKS", "CATEGORICAL", "CONFIRMATION_ENDPOINTS", "CONTINUOUS", "ENDPOINTS", "FOLDS", "MANDATORY_CONTINUOUS", "METHODS", "PREDICTOR_COUNT", "PredictorSensitivityError", "RAW_PREDICTORS", "SCREEN_ENDPOINTS", "SEEDS", "SPECIES", "SensitivityConfig", "apply_encoded_mask", "apply_mask_to_case", "assert_confirmation_eligible", "build_masks", "build_plan", "canary_compare", "confirmation_gate", "delta_i", "delta_u", "digest_value", "encoded_mask", "file_digest", "jaccard", "load_config", "load_reduced_leaf", "mask_audit", "paired_effect_records", "plan", "screen_gate", "status", "validate_mask_audit", "write_reduced_leaf"]
