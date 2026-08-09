"""Leakage-safe inner evaluation for Goal036.

This module fits no models and never opens the outer vault.  It validates the
Goal035 neural prediction leaves and the compact Goal029 selected-family OOF
export, averages the frozen seed predictions, applies the prespecified inner
threshold rule, and publishes aggregate-only metrics and paired contrasts.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.parquet as pq
from sklearn.metrics import average_precision_score, matthews_corrcoef, roc_auc_score

from .contracts import ENDPOINTS, FOLDS, METHODS, SPECIES
from .conventional_oof_export import FAMILIES, SEEDS_BY_FAMILY


class InnerEvaluationError(ValueError):
    """Raised when the Goal036 analysis contract or evidence is invalid."""


NEURAL_SEEDS = ("31031", "31032", "31033", "31034", "31035")
ALL_METHODS = tuple(METHODS) + tuple(f"conventional/{family}" for family in FAMILIES)
PRIMARY_CONTRASTS = {
    "multihead_vs_target_only": ("multihead_full_finetune", "target_only_resmlp"),
    "multihead_vs_q_deep": ("multihead_full_finetune", "target_plus_q_deep"),
}
HEX = frozenset("0123456789abcdef")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InnerEvaluationError(message)


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InnerEvaluationError(f"invalid JSON: {Path(path).name}") from exc
    _require(isinstance(value, dict), f"JSON object required: {Path(path).name}")
    return value


def _endpoint(fraction: str, ladder: str) -> str:
    return f"{fraction}/{ladder}"


@dataclass(frozen=True)
class EvaluationConfig:
    source_path: Path
    root: Path
    raw: Mapping[str, Any]
    authority_digests: Mapping[str, str]

    @property
    def private_root(self) -> Path:
        return self.root / self.raw["evidence"]["private_root"]

    @property
    def tracked_root(self) -> Path:
        return self.root / self.raw["evidence"]["tracked_root"]


def load_config(path: str | Path, *, root: str | Path | None = None) -> EvaluationConfig:
    source = Path(path).resolve()
    raw = _read_json(source)
    expected_keys = {"schema_version", "goal_id", "authorities", "scope", "conventional_export", "evaluation", "evidence"}
    _require(set(raw) == expected_keys and raw["schema_version"] == "1.0" and raw["goal_id"] == "goal036-dsdm-inner-evaluation", "Goal036 config identity drift")
    project_root = Path(root).resolve() if root is not None else source.parents[1]
    authority_names = {
        "protocol", "goal028_config", "goal029_config", "goal029_summary", "goal029_pair", "goal029_finalized",
        "goal035_config", "goal035_aggregate",
    }
    _require(isinstance(raw["authorities"], dict) and set(raw["authorities"]) == authority_names, "Goal036 authority key drift")
    digests: dict[str, str] = {}
    for name, binding in raw["authorities"].items():
        _require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}, f"authority schema drift: {name}")
        relative = Path(binding["path"])
        _require(not relative.is_absolute() and ".." not in relative.parts and _is_digest(binding["sha256"]), f"authority binding invalid: {name}")
        target = project_root / relative
        _require(target.is_file(), f"authority missing: {name}")
        actual = sha256_file(target)
        _require(actual == binding["sha256"], f"authority digest mismatch: {name}")
        digests[name] = actual
    scope = raw["scope"]
    _require(scope == {
        "species": list(SPECIES), "folds": list(FOLDS), "endpoints": list(ENDPOINTS),
        "neural_methods": list(METHODS), "conventional_families": list(FAMILIES),
        "neural_seeds": [31031, 31032, 31033, 31034, 31035],
    }, "Goal036 scope drift")
    pair = _read_json(project_root / raw["authorities"]["goal029_pair"]["path"])
    export = raw["conventional_export"]
    _require(export == {
        "producer_commit": "f85e45922e182858fd351fdaf4f1b36b33fb4f2f",
        "private_core_manifest_sha256": pair["private_core_manifest_sha256"],
        "family_strata": 280, "selected_checkpoints": 952,
        "private_parquet": "data/processed/dsdm/goal036-inner-evaluation/private/conventional_selected_oof.parquet",
        "private_manifest": "data/processed/dsdm/goal036-inner-evaluation/private/conventional_manifest.json",
    }, "Goal036 conventional export drift")
    _require(raw["evaluation"] == {
        "seed_aggregation": "arithmetic_mean_scores",
        "threshold_objective": "max_tss_equal_max_balanced_accuracy",
        "threshold_candidates": "finite_representable_midpoints_plus_extremes",
        "threshold_tie_rule": "sorted_lower_median",
        "positive_rule": "score_greater_than_or_equal_threshold",
        "co_primary_metrics": ["roc_auc", "tss"],
        "supplementary_metrics": ["average_precision", "mcc", "sensitivity", "specificity", "confusion_counts"],
        "classless_fold_policy": "metric_na_with_class_counts",
        "conventional_selection": "highest_mean_fold_roc_auc_then_mean_fold_tss_then_family_id",
        "primary_contrasts": ["multihead_vs_target_only", "multihead_vs_q_deep", "multihead_vs_best_conventional"],
        "replication_unit": "paired_species_by_fold_with_ladders_and_seeds_descriptive_not_independent",
        "inference": "descriptive_no_naive_p_values_or_row_bootstrap",
        "threshold_variability": "leave_one_fold_out_diagnostic_only",
    }, "Goal036 evaluation contract drift")
    _require(raw["evidence"] == {
        "goal035_private_root": "data/processed/dsdm/goal035-final-inner-lifecycle/private",
        "private_root": "data/processed/dsdm/goal036-inner-evaluation/private",
        "tracked_root": "evidence/dsdm_inner_evaluation/goal036",
        "aggregate_only": True, "row_identifiers": False, "coordinates": False,
        "predictions_tracked": False, "labels_tracked": False,
        "outer_attempted": 0, "outer_opened": 0,
    }, "Goal036 evidence boundary drift")
    return EvaluationConfig(source, project_root, raw, dict(sorted(digests.items())))


@dataclass(frozen=True)
class FoldScores:
    row_tokens: tuple[str, ...]
    y: np.ndarray
    scores_by_seed: np.ndarray

    def __post_init__(self) -> None:
        y = np.asarray(self.y, dtype=np.int8)
        scores = np.asarray(self.scores_by_seed, dtype=np.float64)
        _require(y.ndim == 1 and scores.ndim == 2 and scores.shape[1] == len(y) == len(self.row_tokens), "fold score shape drift")
        _require(len(set(self.row_tokens)) == len(self.row_tokens) and set(np.unique(y).tolist()) == {0, 1}, "fold row/class identity drift")
        _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "fold score values invalid")
        y.flags.writeable = False
        scores.flags.writeable = False
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "scores_by_seed", scores)

    @property
    def mean_score(self) -> np.ndarray:
        return np.mean(self.scores_by_seed, axis=0)


@dataclass(frozen=True)
class ScoreStratum:
    species: str
    endpoint: str
    method: str
    source: str
    candidate: str
    seed_labels: tuple[str, ...]
    folds: Mapping[str, FoldScores]


def _tss(y: np.ndarray, score: np.ndarray, threshold: float) -> float:
    predicted = score >= threshold
    positive = y == 1
    negative = ~positive
    return float(np.mean(predicted[positive]) + np.mean(~predicted[negative]) - 1.0)


def select_threshold(y: Sequence[int], score: Sequence[float]) -> tuple[float, tuple[float, ...], float]:
    labels = np.asarray(y, dtype=np.int8)
    values = np.asarray(score, dtype=np.float64)
    _require(labels.ndim == values.ndim == 1 and len(labels) == len(values) > 0 and set(np.unique(labels).tolist()) == {0, 1}, "threshold labels invalid")
    _require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "threshold scores invalid")
    unique = np.unique(values)
    candidates = [float(np.nextafter(unique[0], -np.inf)), float(np.nextafter(unique[-1], np.inf))]
    for low, high in zip(unique[:-1], unique[1:]):
        midpoint = float(low + (high - low) / 2.0)
        if not low < midpoint < high:
            midpoint = float(high)
        if np.isfinite(midpoint):
            candidates.append(midpoint)
    candidates = sorted(set(candidates))
    tss_values = np.asarray([_tss(labels, values, threshold) for threshold in candidates])
    maximum = float(np.max(tss_values))
    maximizers = tuple(threshold for threshold, metric in zip(candidates, tss_values) if metric == maximum)
    threshold = float(maximizers[(len(maximizers) - 1) // 2])
    return threshold, tuple(float(value) for value in maximizers), _tss(labels, values, threshold)


def binary_metrics(y: Sequence[int], score: Sequence[float], threshold: float) -> dict[str, Any]:
    labels = np.asarray(y, dtype=np.int8)
    values = np.asarray(score, dtype=np.float64)
    _require(labels.ndim == values.ndim == 1 and len(labels) == len(values) > 0, "metric vector shape drift")
    _require(np.isin(labels, (0, 1)).all() and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "metric values invalid")
    predicted = values >= threshold
    tp = int(np.sum(predicted & (labels == 1)))
    fn = int(np.sum(~predicted & (labels == 1)))
    tn = int(np.sum(~predicted & (labels == 0)))
    fp = int(np.sum(predicted & (labels == 0)))
    n_pos = tp + fn
    n_neg = tn + fp
    both = n_pos > 0 and n_neg > 0
    return {
        "n": len(labels), "n_positive": n_pos, "n_negative": n_neg,
        "prevalence": float(n_pos / len(labels)),
        "roc_auc": float(roc_auc_score(labels, values)) if both else None,
        "average_precision": float(average_precision_score(labels, values)) if n_pos > 0 else None,
        "tss": float(tp / n_pos + tn / n_neg - 1.0) if both else None,
        "mcc": float(matthews_corrcoef(labels, predicted)) if both else None,
        "sensitivity": float(tp / n_pos) if n_pos else None,
        "specificity": float(tn / n_neg) if n_neg else None,
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
    }


def _goal035_identity(config: Any, aggregate: Mapping[str, Any], bundle: Any, prepared: Mapping[str, Any]) -> dict[str, Any]:
    from .final_inner_data import digest_value as goal035_digest
    return {
        "target": bundle.target,
        "held_fold": bundle.held_fold,
        "held_row_count": int(len(bundle.arrays["x_held"])),
        "bundle_digest": bundle.source_digest,
        "config_digest": config.config_digest,
        "runtime_digest": aggregate["runtime_digest"],
        "architecture": config.corrected_winner,
        "mask_digest": goal035_digest({endpoint: prepared["target_masks"][endpoint].digest for endpoint in ENDPOINTS}),
        "aux_mask_digest": prepared["auxiliary_mask"].digest,
    }


def collect_neural(config: EvaluationConfig) -> tuple[dict[tuple[str, str, str], ScoreStratum], dict[str, Any]]:
    from .final_inner_data import array_digest, digest_value as goal035_digest, leaf_identity, load_config as load_goal035, prepare_case, validate_bundle_inventory, validate_leaf
    from dsdm_phase1.goal029_production import ingest_production_foundation

    goal035_config_path = config.root / config.raw["authorities"]["goal035_config"]["path"]
    goal035 = load_goal035(goal035_config_path, root=config.root, require_receipt=True)
    aggregate = _read_json(config.root / config.raw["authorities"]["goal035_aggregate"]["path"])
    _require(aggregate.get("success") is True and aggregate.get("cases") == 40 and aggregate.get("outer_attempted") == aggregate.get("outer_opened") == 0, "Goal035 aggregate gate failed")
    private_root = config.root / config.raw["evidence"]["goal035_private_root"]
    bundles = validate_bundle_inventory(private_root, config=goal035)

    goal029_raw = _read_json(config.root / config.raw["authorities"]["goal029_config"]["path"])
    broker, _, vault = ingest_production_foundation(config.root, goal029_raw)
    _require(vault.attempted_open_count == vault.open_count == 0, "outer access during Goal035 row reconstruction")

    strata: dict[tuple[str, str, str], dict[str, FoldScores]] = {}
    leaf_ids: list[str] = []
    leaf_contents: list[str] = []
    bundle_digests: list[str] = []
    row_identity_by_species: dict[str, list[dict[str, Any]]] = {species: [] for species in SPECIES}
    for bundle in bundles:
        prepared = prepare_case(bundle)
        identity = _goal035_identity(goal035, aggregate, bundle, prepared)
        leaf_id = leaf_identity(identity)
        leaf_path = private_root / "leaves" / leaf_id
        metadata = validate_leaf(leaf_path, identity)
        predictions = np.load(leaf_path / "predictions.npy", allow_pickle=False)
        _require(predictions.shape == (5, 7, 6, len(bundle.arrays["y_held"])), "Goal035 prediction shape drift")
        _, assessment = broker.inner(bundle.target, bundle.held_fold)
        row_tokens = tuple(json.dumps([key.species_id, key.grid_cell_id], separators=(",", ":")) for key in assessment.keys)
        y = np.asarray(assessment.pa, dtype=np.int8)
        _require(np.array_equal(y, bundle.arrays["y_held"].astype(np.int8)), "Goal035 held response reconstruction mismatch")
        row_identity_by_species[bundle.target].append({"fold": bundle.held_fold, "tokens": row_tokens, "y": y.tolist()})
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            for method_index, method in enumerate(METHODS):
                strata.setdefault((bundle.target, endpoint, method), {})[bundle.held_fold] = FoldScores(
                    row_tokens, y.copy(), predictions[:, endpoint_index, method_index, :].astype(np.float64)
                )
        leaf_ids.append(leaf_id)
        leaf_contents.append(goal035_digest({"identity": identity, "metadata": metadata, "predictions": array_digest(predictions)}))
        bundle_digests.append(bundle.source_digest)

    _require(goal035_digest(sorted(bundle_digests)) == aggregate["bundle_inventory_digest"], "Goal035 bundle inventory mismatch")
    _require(goal035_digest(sorted(leaf_ids)) == aggregate["leaf_inventory_digest"], "Goal035 leaf inventory mismatch")
    _require(goal035_digest(sorted(leaf_contents)) == aggregate["leaf_content_inventory_digest"], "Goal035 leaf content inventory mismatch")
    _require(len(strata) == 8 * 7 * 6 and all(set(folds) == set(FOLDS) for folds in strata.values()), "Goal035 neural stratum coverage drift")
    result = {
        key: ScoreStratum(key[0], key[1], key[2], "neural", goal035.corrected_winner, NEURAL_SEEDS, dict(sorted(folds.items())))
        for key, folds in strata.items()
    }
    audit = {
        "cases": 40,
        "strata": len(result),
        "leaf_inventory_digest": aggregate["leaf_inventory_digest"],
        "leaf_content_inventory_digest": aggregate["leaf_content_inventory_digest"],
        "row_identity_digest_by_species": {species: digest_value(rows) for species, rows in row_identity_by_species.items()},
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    return result, audit


def collect_conventional(
    config: EvaluationConfig,
    neural: Mapping[tuple[str, str, str], ScoreStratum],
) -> tuple[dict[tuple[str, str, str], ScoreStratum], dict[str, Any]]:
    export = config.raw["conventional_export"]
    parquet_path = config.root / export["private_parquet"]
    manifest_path = config.root / export["private_manifest"]
    manifest = _read_json(manifest_path)
    body = dict(manifest)
    claimed = body.pop("manifest_digest", None)
    _require(claimed == digest_value(body) and manifest.get("schema_version") == "goal036-conventional-oof-export-v1", "conventional export manifest invalid")
    _require(manifest.get("producer_commit") == export["producer_commit"] and manifest.get("private_core_manifest_sha256") == export["private_core_manifest_sha256"], "conventional export producer binding drift")
    _require(manifest.get("family_strata") == 280 and manifest.get("selected_checkpoints") == 952 and manifest.get("outer_attempted") == manifest.get("outer_opened") == 0, "conventional export arithmetic/boundary drift")
    _require(parquet_path.is_file() and sha256_file(parquet_path) == manifest.get("parquet_sha256") and parquet_path.stat().st_size == manifest.get("parquet_bytes"), "conventional OOF Parquet drift")
    table = pq.read_table(parquet_path)
    _require(table.num_rows == manifest.get("rows"), "conventional OOF row count drift")
    expected_columns = ["species_id", "fraction_id", "ladder_id", "model_family", "candidate_id", "seed_label", "fold_id", "row_index", "row_token", "y_true", "score"]
    _require(table.column_names == expected_columns, "conventional OOF columns drift")
    frame = table.to_pandas()
    group_columns = ["species_id", "fraction_id", "ladder_id", "model_family", "candidate_id"]
    grouped = frame.groupby(group_columns, sort=False, observed=True)
    _require(grouped.ngroups == 280, "conventional selected stratum count drift")
    result: dict[tuple[str, str, str], ScoreStratum] = {}
    for identity, group in grouped:
        species, fraction, ladder, family, candidate = map(str, identity)
        endpoint = _endpoint(fraction, ladder)
        _require(species in SPECIES and endpoint in ENDPOINTS and family in FAMILIES, "conventional OOF scope drift")
        seeds = SEEDS_BY_FAMILY[family]
        _require(tuple(sorted(group["seed_label"].unique())) == seeds, "conventional selected seed coverage drift")
        folds: dict[str, FoldScores] = {}
        for fold in FOLDS:
            folded = group[group["fold_id"] == fold].copy()
            _require(len(folded) > 0, "conventional fold missing")
            baseline: tuple[tuple[str, ...], np.ndarray] | None = None
            score_rows: list[np.ndarray] = []
            for seed in seeds:
                seeded = folded[folded["seed_label"] == seed].sort_values("row_index")
                tokens = tuple(str(value) for value in seeded["row_token"].tolist())
                y = seeded["y_true"].to_numpy(dtype=np.int8)
                if baseline is None:
                    baseline = (tokens, y)
                else:
                    _require(tokens == baseline[0] and np.array_equal(y, baseline[1]), "conventional seed row identity drift")
                score_rows.append(seeded["score"].to_numpy(dtype=np.float64))
            assert baseline is not None
            reference = neural[(species, endpoint, METHODS[0])].folds[fold]
            _require(baseline[0] == reference.row_tokens and np.array_equal(baseline[1], reference.y), "Goal029/Goal035 held rows do not align")
            folds[fold] = FoldScores(baseline[0], baseline[1].copy(), np.vstack(score_rows))
        method = f"conventional/{family}"
        key = (species, endpoint, method)
        _require(key not in result, "duplicate conventional stratum")
        result[key] = ScoreStratum(species, endpoint, method, "conventional", candidate, seeds, folds)
    _require(len(result) == 8 * 7 * 5, "conventional stratum coverage drift")
    audit = {
        "strata": len(result),
        "selected_checkpoints": manifest["selected_checkpoints"],
        "rows": manifest["rows"],
        "manifest_digest": claimed,
        "parquet_sha256": manifest["parquet_sha256"],
        "checkpoint_inventory_digest": manifest["checkpoint_inventory_digest"],
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    return result, audit


def _mean(values: Sequence[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return float(np.mean(finite)) if finite else None


def _summarize_stratum(stratum: ScoreStratum) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[float]]]:
    all_y = np.concatenate([stratum.folds[fold].y for fold in FOLDS])
    all_mean = np.concatenate([stratum.folds[fold].mean_score for fold in FOLDS])
    threshold, maximizers, _ = select_threshold(all_y, all_mean)
    fold_rows: list[dict[str, Any]] = []
    for fold in FOLDS:
        metrics = binary_metrics(stratum.folds[fold].y, stratum.folds[fold].mean_score, threshold)
        fold_rows.append({
            "species": stratum.species, "endpoint": stratum.endpoint, "method": stratum.method,
            "source": stratum.source, "candidate": stratum.candidate, "fold": fold,
            "seed_count": len(stratum.seed_labels), "threshold": threshold, **metrics,
        })
    pooled = binary_metrics(all_y, all_mean, threshold)
    loo_thresholds = []
    for omitted in FOLDS:
        y = np.concatenate([stratum.folds[fold].y for fold in FOLDS if fold != omitted])
        score = np.concatenate([stratum.folds[fold].mean_score for fold in FOLDS if fold != omitted])
        loo_thresholds.append(select_threshold(y, score)[0])
    seed_auc: list[float] = []
    seed_tss: list[float] = []
    for seed_index in range(len(stratum.seed_labels)):
        score = np.concatenate([stratum.folds[fold].scores_by_seed[seed_index] for fold in FOLDS])
        seed_auc.append(float(roc_auc_score(all_y, score)))
        seed_tss.append(_tss(all_y, score, threshold))
    row = {
        "species": stratum.species, "endpoint": stratum.endpoint, "method": stratum.method,
        "source": stratum.source, "candidate": stratum.candidate, "seed_count": len(stratum.seed_labels),
        "threshold": threshold, "threshold_maximizer_count": len(maximizers),
        "threshold_loo_min": min(loo_thresholds), "threshold_loo_max": max(loo_thresholds),
        "threshold_loo_sd": float(np.std(loo_thresholds, ddof=1)),
        "mean_fold_roc_auc": _mean([record["roc_auc"] for record in fold_rows]),
        "mean_fold_tss": _mean([record["tss"] for record in fold_rows]),
        "mean_fold_average_precision": _mean([record["average_precision"] for record in fold_rows]),
        "mean_fold_mcc": _mean([record["mcc"] for record in fold_rows]),
        "pooled_roc_auc": pooled["roc_auc"], "pooled_tss": pooled["tss"],
        "pooled_average_precision": pooled["average_precision"], "pooled_mcc": pooled["mcc"],
        "n": pooled["n"], "n_positive": pooled["n_positive"], "n_negative": pooled["n_negative"],
        "prevalence": pooled["prevalence"],
        "seed_roc_auc_min": min(seed_auc), "seed_roc_auc_max": max(seed_auc), "seed_roc_auc_sd": float(np.std(seed_auc, ddof=1)) if len(seed_auc) > 1 else 0.0,
        "seed_tss_min": min(seed_tss), "seed_tss_max": max(seed_tss), "seed_tss_sd": float(np.std(seed_tss, ddof=1)) if len(seed_tss) > 1 else 0.0,
    }
    return row, fold_rows, {"roc_auc": seed_auc, "tss": seed_tss}


def _paired_delta(left: Sequence[float], right: Sequence[float]) -> dict[str, float]:
    _require(len(left) == len(right) and len(left) > 0, "paired seed contrast invalid")
    delta = np.asarray(left, dtype=np.float64) - np.asarray(right, dtype=np.float64)
    return {"seed_delta_min": float(np.min(delta)), "seed_delta_median": float(np.median(delta)), "seed_delta_max": float(np.max(delta))}


def evaluate(config: EvaluationConfig, output_root: str | Path) -> dict[str, Any]:
    neural, neural_audit = collect_neural(config)
    conventional, conventional_audit = collect_conventional(config, neural)
    strata = {**neural, **conventional}
    _require(len(strata) == 8 * 7 * 11, "combined method stratum coverage drift")

    stratum_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    seed_metrics: dict[tuple[str, str, str], dict[str, list[float]]] = {}
    summaries: dict[tuple[str, str, str], dict[str, Any]] = {}
    fold_lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for key in sorted(strata):
        summary, folds, seed_values = _summarize_stratum(strata[key])
        stratum_rows.append(summary)
        fold_rows.extend(folds)
        summaries[key] = summary
        seed_metrics[key] = seed_values
        for record in folds:
            fold_lookup[(record["species"], record["endpoint"], record["method"], record["fold"])] = record

    selection_rows: list[dict[str, Any]] = []
    best_conventional: dict[tuple[str, str], str] = {}
    for species in SPECIES:
        for endpoint in ENDPOINTS:
            candidates = [summaries[(species, endpoint, f"conventional/{family}")] for family in FAMILIES]
            winner = sorted(candidates, key=lambda row: (-float(row["mean_fold_roc_auc"]), -float(row["mean_fold_tss"]), row["method"]))[0]
            family = str(winner["method"]).split("/", 1)[1]
            best_conventional[(species, endpoint)] = winner["method"]
            selection_rows.append({
                "species": species, "endpoint": endpoint, "selected_family": family,
                "selected_candidate": winner["candidate"], "mean_fold_roc_auc": winner["mean_fold_roc_auc"],
                "mean_fold_tss": winner["mean_fold_tss"], "seed_count": winner["seed_count"],
            })

    contrast_rows: list[dict[str, Any]] = []
    for species in SPECIES:
        for endpoint in ENDPOINTS:
            pairs = dict(PRIMARY_CONTRASTS)
            pairs["multihead_vs_best_conventional"] = ("multihead_full_finetune", best_conventional[(species, endpoint)])
            for contrast, (left_method, right_method) in pairs.items():
                left = summaries[(species, endpoint, left_method)]
                right = summaries[(species, endpoint, right_method)]
                fold_auc = []
                fold_tss = []
                for fold in FOLDS:
                    left_fold = fold_lookup[(species, endpoint, left_method, fold)]
                    right_fold = fold_lookup[(species, endpoint, right_method, fold)]
                    fold_auc.append(float(left_fold["roc_auc"]) - float(right_fold["roc_auc"]))
                    fold_tss.append(float(left_fold["tss"]) - float(right_fold["tss"]))
                record: dict[str, Any] = {
                    "species": species, "endpoint": endpoint, "contrast": contrast,
                    "left_method": left_method, "right_method": right_method,
                    "delta_mean_fold_roc_auc": float(left["mean_fold_roc_auc"]) - float(right["mean_fold_roc_auc"]),
                    "delta_mean_fold_tss": float(left["mean_fold_tss"]) - float(right["mean_fold_tss"]),
                    "delta_pooled_roc_auc": float(left["pooled_roc_auc"]) - float(right["pooled_roc_auc"]),
                    "delta_pooled_tss": float(left["pooled_tss"]) - float(right["pooled_tss"]),
                    "auc_fold_wins": int(np.sum(np.asarray(fold_auc) > 0)), "auc_fold_ties": int(np.sum(np.asarray(fold_auc) == 0)),
                    "tss_fold_wins": int(np.sum(np.asarray(fold_tss) > 0)), "tss_fold_ties": int(np.sum(np.asarray(fold_tss) == 0)),
                    "fold_count": 5,
                    "seed_delta_roc_auc_min": None, "seed_delta_roc_auc_median": None, "seed_delta_roc_auc_max": None,
                    "seed_delta_tss_min": None, "seed_delta_tss_median": None, "seed_delta_tss_max": None,
                }
                if right_method in METHODS:
                    auc_delta = _paired_delta(seed_metrics[(species, endpoint, left_method)]["roc_auc"], seed_metrics[(species, endpoint, right_method)]["roc_auc"])
                    tss_delta = _paired_delta(seed_metrics[(species, endpoint, left_method)]["tss"], seed_metrics[(species, endpoint, right_method)]["tss"])
                    for suffix in ("min", "median", "max"):
                        record[f"seed_delta_roc_auc_{suffix}"] = auc_delta[f"seed_delta_{suffix}"]
                        record[f"seed_delta_tss_{suffix}"] = tss_delta[f"seed_delta_{suffix}"]
                contrast_rows.append(record)

    endpoint_rows: list[dict[str, Any]] = []
    for endpoint in ENDPOINTS:
        for method in ALL_METHODS:
            rows = [summaries[(species, endpoint, method)] for species in SPECIES]
            endpoint_rows.append({
                "endpoint": endpoint, "method": method, "species_count": 8,
                "median_species_mean_fold_roc_auc": float(np.median([row["mean_fold_roc_auc"] for row in rows])),
                "mean_species_mean_fold_roc_auc": float(np.mean([row["mean_fold_roc_auc"] for row in rows])),
                "median_species_mean_fold_tss": float(np.median([row["mean_fold_tss"] for row in rows])),
                "mean_species_mean_fold_tss": float(np.mean([row["mean_fold_tss"] for row in rows])),
            })

    contrast_summary_rows: list[dict[str, Any]] = []
    for endpoint in ENDPOINTS:
        for contrast in (*PRIMARY_CONTRASTS, "multihead_vs_best_conventional"):
            rows = [row for row in contrast_rows if row["endpoint"] == endpoint and row["contrast"] == contrast]
            auc = np.asarray([row["delta_mean_fold_roc_auc"] for row in rows])
            tss = np.asarray([row["delta_mean_fold_tss"] for row in rows])
            contrast_summary_rows.append({
                "endpoint": endpoint, "contrast": contrast, "species_count": 8,
                "median_delta_mean_fold_roc_auc": float(np.median(auc)),
                "min_delta_mean_fold_roc_auc": float(np.min(auc)), "max_delta_mean_fold_roc_auc": float(np.max(auc)),
                "species_auc_positive": int(np.sum(auc > 0)), "species_auc_tied": int(np.sum(auc == 0)),
                "median_delta_mean_fold_tss": float(np.median(tss)),
                "min_delta_mean_fold_tss": float(np.min(tss)), "max_delta_mean_fold_tss": float(np.max(tss)),
                "species_tss_positive": int(np.sum(tss > 0)), "species_tss_tied": int(np.sum(tss == 0)),
            })

    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    tables = {
        "fold_metrics.csv": fold_rows,
        "stratum_metrics.csv": stratum_rows,
        "conventional_selection.csv": selection_rows,
        "contrasts.csv": contrast_rows,
        "endpoint_summary.csv": endpoint_rows,
        "contrast_summary.csv": contrast_summary_rows,
    }
    for name, rows in tables.items():
        _write_csv(output / name, rows)
    receipt = {
        "schema_version": "goal036-inner-evaluation-v1", "success": True,
        "config_digest": sha256_file(config.source_path), "authority_digests": dict(config.authority_digests),
        "execution_source_digests": {
            "conventional_oof_export": sha256_file(config.root / "src/dsdm/conventional_oof_export.py"),
            "inner_evaluation": sha256_file(config.root / "src/dsdm/inner_evaluation.py"),
        },
        "neural_audit": neural_audit, "conventional_audit": conventional_audit,
        "counts": {"methods": 11, "neural_strata": 336, "conventional_strata": 280, "combined_strata": 616, "fold_metrics": 3080, "conventional_selections": 56, "primary_contrasts": 168},
        "table_digests": {name: sha256_file(output / name) for name in sorted(tables)},
        "privacy": {"aggregate_only": True, "row_identifiers": False, "coordinates": False, "predictions_tracked": False, "labels_tracked": False},
        "outer_attempted": 0, "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    (output / "summary.json").write_text(canonical(receipt).decode() + "\n", encoding="utf-8")
    validate_tracked_output(output)
    return receipt


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    _require(bool(rows), f"empty table: {path.name}")
    fields = list(rows[0])
    _require(all(list(row) == fields for row in rows), f"table schema drift: {path.name}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def validate_tracked_output(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    expected = {"summary.json", "fold_metrics.csv", "stratum_metrics.csv", "conventional_selection.csv", "contrasts.csv", "endpoint_summary.csv", "contrast_summary.csv"}
    _require(root.is_dir() and {item.name for item in root.iterdir() if item.is_file()} == expected, "Goal036 tracked inventory drift")
    summary = _read_json(root / "summary.json")
    body = dict(summary)
    claimed = body.pop("receipt_digest", None)
    _require(claimed == digest_value(body) and summary.get("success") is True, "Goal036 summary receipt drift")
    _require(summary.get("outer_attempted") == summary.get("outer_opened") == 0 and summary.get("privacy") == {"aggregate_only": True, "row_identifiers": False, "coordinates": False, "predictions_tracked": False, "labels_tracked": False}, "Goal036 tracked boundary drift")
    for name, digest in summary["table_digests"].items():
        _require(sha256_file(root / name) == digest, f"Goal036 table digest mismatch: {name}")
    text = "\n".join(item.read_text(encoding="utf-8") for item in root.iterdir() if item.is_file())
    for forbidden in ('"row_token"', "grid_cell_id", "g_1", "latitude", "longitude", "predictions.npy", "/Users/", "/data/codex/"):
        _require(forbidden not in text, f"private material in tracked evidence: {forbidden}")
    return summary


def validate_recompute(config: EvaluationConfig) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="goal036-validate-", dir=str(config.private_root)) as temporary:
        evaluate(config, temporary)
        expected = config.tracked_root
        actual = Path(temporary)
        _require({item.name for item in actual.iterdir()} == {item.name for item in expected.iterdir()}, "Goal036 recompute inventory mismatch")
        for item in actual.iterdir():
            _require(item.read_bytes() == (expected / item.name).read_bytes(), f"Goal036 recompute mismatch: {item.name}")
    return validate_tracked_output(config.tracked_root)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.inner_evaluation")
    parser.add_argument("--config", default="config/dsdm_inner_evaluation.json")
    parser.add_argument("command", choices=("plan", "run", "validate"))
    args = parser.parse_args(argv)
    source = Path(args.config).resolve()
    config = load_config(source, root=source.parents[1])
    if args.command == "plan":
        print(canonical({"goal_id": config.raw["goal_id"], "methods": 11, "strata": 616, "fold_metrics": 3080, "contrasts": 168, "fits": 0, "outer_attempted": 0, "outer_opened": 0}).decode())
        return 0
    if args.command == "run":
        print(canonical(evaluate(config, config.tracked_root)).decode())
        return 0
    print(canonical(validate_recompute(config)).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
