"""Reproduce the retained-only Goal052 effort diagnostics.

The script reads saved retained inner prediction leaves, the retained Goal051
selected conventional endpoints, and the Goal050 retained cell table.  It
never fits a model and never opens an outer response.  Processing is target at
a time so that the private prediction leaves do not accumulate in memory.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

# Keep numerical libraries single-threaded even if this script is invoked
# without an explicit shell environment.
for _thread_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_thread_var, "1")

import numpy as np
import pyarrow.parquet as pq
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "evidence/seawfb_dsdm/goal052/summary.json"
GOAL051_SUMMARY = ROOT / "evidence/seawfb_conventional/goal051/summary.json"
GOAL052_ROOT = ROOT / "data/processed/dsdm/goal052-seawfb-dsdm-experiment"
LEAVES = GOAL052_ROOT / "leaves"
GOAL051_ROOT = ROOT / "data/processed/dsdm/goal051-seawfb-conventional-benchmark-v4"
ENDPOINTS = GOAL051_ROOT / "endpoints"
CELLS = ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/cells.parquet"
MEMBERSHIPS = ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/memberships.parquet"
OUTPUT = ROOT / "evidence/seawfb_dsdm/goal052/effort-review-20261001.json"

ACCEPTED_SUMMARY_SHA256 = "ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3"
ACCEPTED_GOAL051_SUMMARY_SHA256 = "9c1bf1ff8884fae35fe7ebe6f8d19e2aae46ab7eedee252b398c0c74705dd2d8"
SEEDS = tuple(f"seed{i:02d}" for i in range(5))
FOLDS = tuple(range(5))
FT = "multihead_full_finetune"
TO = "target_only_random_init_resmlp"
FZ = "multihead_frozen_trunk"
Q = "target_plus_q_linear_resmlp"
NEURAL_ARMS = (FT, TO, FZ, Q)
RICHNESS_CLASSES = ((10, 24, "10_24"), (25, 99, "25_99"), (100, math.inf, "100_plus"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def auc(y: np.ndarray, score: np.ndarray) -> float | None:
    y = np.asarray(y, dtype=np.int8)
    if len(y) == 0 or np.unique(y).size != 2:
        return None
    return float(roc_auc_score(y, np.asarray(score, dtype=np.float64)))


def stats(values: Iterable[float], positive: bool = False) -> dict[str, Any]:
    vals = np.asarray(list(values), dtype=np.float64)
    if len(vals) == 0:
        return {"n": 0, "mean": None, "positive": 0, "min": None, "max": None}
    return {
        "n": int(len(vals)),
        "mean": float(np.mean(vals)),
        "median": float(np.median(vals)),
        "positive": int(np.sum(vals > 0)) if positive else None,
        "min": float(np.min(vals)),
        "max": float(np.max(vals)),
    }


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_cell_index() -> dict[str, tuple[int, int]]:
    """Read only the retained identity, fold, and full richness columns."""
    table = pq.read_table(CELLS, columns=["cell_id", "fold", "effort_richness"])
    rows = table.to_pylist()
    result: dict[str, tuple[int, int]] = {}
    for row in rows:
        cell = str(row["cell_id"])
        _assert(cell not in result, f"duplicate retained cell_id: {cell}")
        result[cell] = (int(row["fold"]), int(row["effort_richness"]))
    _assert(len(result) == table.num_rows, "retained cell identity drift")
    _assert(all(0 <= fold < 5 and richness >= 0 for fold, richness in result.values()), "cell bounds drift")
    return result


def load_membership_species() -> set[str]:
    table = pq.read_table(MEMBERSHIPS, columns=["species"])
    species = {str(value) for value in table["species"].to_pylist()}
    _assert(species, "frozen membership table is empty")
    return species


def index_neural_leaves() -> tuple[dict[tuple[str, str, str, str, int], Path], str]:
    """Index receipts, without loading any prediction vectors."""
    indexed: dict[tuple[str, str, str, str, int], Path] = {}
    payload_hashes: dict[str, str] = {}
    json_paths = sorted(LEAVES.glob("*.json"))
    _assert(json_paths, "Goal052 leaf receipts are missing")
    for receipt_path in json_paths:
        receipt = json.loads(receipt_path.read_text())
        key = receipt.get("key", {})
        if key.get("fraction") != 100 or key.get("auxiliary") not in ("full", "none"):
            continue
        arm = key.get("arm")
        architecture = key.get("architecture")
        seed_label = key.get("seed_label")
        target = key.get("target")
        fold = key.get("fold")
        if arm not in NEURAL_ARMS or architecture != "seawfb_scale" or seed_label not in SEEDS:
            continue
        parquet_path = receipt_path.with_suffix(".parquet")
        _assert(parquet_path.is_file(), f"missing prediction payload: {parquet_path.name}")
        declared_hash = receipt.get("prediction_sha256")
        _assert(isinstance(declared_hash, str) and len(declared_hash) == 64, f"neural prediction hash missing: {receipt_path.name}")
        _assert(sha256_file(parquet_path) == declared_hash, f"neural prediction hash mismatch: {parquet_path.name}")
        expected_aux = "none" if arm == TO else "full"
        _assert(key.get("auxiliary") == expected_aux, f"neural auxiliary drift for {target}")
        identity = (str(target), str(arm), str(seed_label), int(fold), int(key["fraction"]))
        _assert(identity not in indexed, f"duplicate neural leaf: {identity}")
        indexed[identity] = parquet_path
        payload_hashes[json.dumps(identity, separators=(",", ":"))] = declared_hash
    expected = len({key[0] for key in indexed})
    _assert(expected == 157, f"expected 157 targets, found {expected}")
    for target in sorted({key[0] for key in indexed}):
        for arm in NEURAL_ARMS:
            for seed in SEEDS:
                _assert(all((target, arm, seed, fold, 100) in indexed for fold in FOLDS), f"neural leaf grid incomplete: {target} {arm} {seed}")
    return indexed, digest(payload_hashes)


def selected_conventional_index(targets: set[str]) -> tuple[dict[str, dict[str, Any]], Counter[str], Counter[str]]:
    """Return selected-family/candidate metadata for target100 endpoints."""
    selection: dict[str, dict[str, Any]] = {}
    families: Counter[str] = Counter()
    candidates: Counter[str] = Counter()
    for target in sorted(targets):
        slug = "_".join(target.lower().split())
        receipt_path = ENDPOINTS / f"{slug}_target100.json"
        parquet_path = ENDPOINTS / f"{slug}_target100.parquet"
        _assert(receipt_path.is_file() and parquet_path.is_file(), f"Goal051 endpoint missing: {target}")
        receipt = json.loads(receipt_path.read_text())
        family = str(receipt["best_non_null_family"])
        family_result = receipt["families"][family]["selected"]
        candidate = str(family_result["candidate_id"])
        declared_hash = receipt.get("prediction_sha256")
        _assert(isinstance(declared_hash, str) and len(declared_hash) == 64, f"Goal051 prediction hash missing: {target}")
        _assert(sha256_file(parquet_path) == declared_hash, f"Goal051 prediction hash mismatch: {target}")
        selection[target] = {
            "family": family,
            "candidate_id": candidate,
            "endpoint_json_sha256": sha256_file(receipt_path),
            "endpoint_prediction_sha256_declared": receipt.get("prediction_sha256"),
            "endpoint_path": str(parquet_path.relative_to(ROOT)),
        }
        families[family] += 1
        candidates[candidate] += 1
    return selection, families, candidates


def read_neural_fold(path: Path, cells: dict[str, tuple[int, int]], expected_fold: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    table = pq.read_table(path, columns=["cell_id", "y", "score"])
    rows = table.to_pydict()
    ids = np.asarray(rows["cell_id"], dtype=str)
    y = np.asarray(rows["y"], dtype=np.int8)
    score = np.asarray(rows["score"], dtype=np.float64)
    _assert(len(ids) == len(set(ids.tolist())), f"duplicate neural cells in {path.name}")
    _assert(np.isin(y, (0, 1)).all() and np.isfinite(score).all(), f"neural payload invalid: {path.name}")
    known = [cells.get(cell) for cell in ids]
    _assert(all(item is not None for item in known), f"neural cell outside retained substrate: {path.name}")
    folds = np.asarray([item[0] for item in known], dtype=np.int8)
    richness = np.asarray([item[1] for item in known], dtype=np.int64)
    _assert(np.all(richness[y == 1] >= 1), f"focal presence exceeds retained richness: {path.name}")
    _assert(np.all(folds == expected_fold), f"leaf fold mismatch: {path.name}")
    order = np.argsort(ids, kind="mergesort")
    return ids[order], y[order], score[order], richness[order]


def read_conventional(target: str, info: dict[str, Any], cells: dict[str, tuple[int, int]]) -> dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    path = ROOT / info["endpoint_path"]
    family, candidate = info["family"], info["candidate_id"]
    table = pq.read_table(
        path,
        columns=["fold", "cell_id", "y", "method", "family", "candidate_id", "score"],
        filters=[("method", "=", "family_selected"), ("family", "=", family), ("candidate_id", "=", candidate)],
    )
    rows = table.to_pydict()
    result: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    for fold in FOLDS:
        mask = np.asarray(rows["fold"], dtype=np.int8) == fold
        ids = np.asarray(rows["cell_id"], dtype=str)[mask]
        y = np.asarray(rows["y"], dtype=np.int8)[mask]
        score = np.asarray(rows["score"], dtype=np.float64)[mask]
        _assert(len(ids) == len(set(ids.tolist())), f"duplicate conventional cells: {target} fold {fold}")
        _assert(np.isin(y, (0, 1)).all() and np.isfinite(score).all(), f"conventional payload invalid: {target}")
        known = [cells.get(cell) for cell in ids]
        _assert(all(item is not None for item in known), f"conventional cell outside retained substrate: {target}")
        _assert(all(item[0] == fold for item in known), f"conventional fold mismatch: {target} fold {fold}")
        richness = np.asarray([item[1] for item in known], dtype=np.int64)
        _assert(np.all(richness[y == 1] >= 1), f"focal presence exceeds retained richness: {target}")
        order = np.argsort(ids, kind="mergesort")
        result[fold] = (ids[order], y[order], score[order], richness[order])
    _assert(all(fold in result for fold in FOLDS), f"conventional fold grid incomplete: {target}")
    return result


def load_target_data(target: str, leaf_index: dict[tuple[str, str, str, str, int], Path], conventional: dict[str, Any], cells: dict[str, tuple[int, int]]) -> dict[str, Any]:
    arms: dict[str, dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = {}
    base: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    for arm in NEURAL_ARMS:
        arm_data: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        for fold in FOLDS:
            ids0 = y0 = richness0 = None
            seed_scores = []
            for seed in SEEDS:
                ids, y, score, richness = read_neural_fold(leaf_index[(target, arm, seed, fold, 100)], cells, fold)
                if ids0 is None:
                    ids0, y0, richness0 = ids, y, richness
                else:
                    _assert(np.array_equal(ids, ids0) and np.array_equal(y, y0) and np.array_equal(richness, richness0), f"neural seed alignment drift: {target} {arm} fold {fold}")
                seed_scores.append(score)
            assert ids0 is not None and y0 is not None and richness0 is not None
            mean_score = np.mean(np.vstack(seed_scores), axis=0, dtype=np.float64)
            arm_data[fold] = (ids0, y0, mean_score, richness0, np.vstack(seed_scores))
            if arm == FT:
                base[fold] = (ids0, y0, mean_score, richness0)
        arms[arm] = arm_data
    for fold in FOLDS:
        ids0, y0, _, richness0 = arms[FT][fold][:4]
        for arm in NEURAL_ARMS:
            ids, y, _, richness = arms[arm][fold][:4]
            _assert(np.array_equal(ids, ids0) and np.array_equal(y, y0) and np.array_equal(richness, richness0), f"neural arm alignment drift: {target} {arm} fold {fold}")
    conv = read_conventional(target, conventional, cells)
    for fold in FOLDS:
        ids, y, score, richness = conv[fold]
        ids0, y0, _, richness0 = base[fold]
        _assert(np.array_equal(ids, ids0) and np.array_equal(y, y0) and np.array_equal(richness, richness0), f"conventional/neural alignment drift: {target} fold {fold}")
    return {"arms": arms, "conventional": conv}


def mean_fold_auc(data: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]], score_index: int = 2) -> tuple[float | None, list[float | None]]:
    fold_aucs = [auc(data[fold][1], data[fold][score_index]) for fold in FOLDS]
    return (None if any(value is None for value in fold_aucs) else float(np.mean(fold_aucs)), fold_aucs)


def baseline_metrics(target: str, data: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    observed: dict[str, float] = {}
    expected_values: dict[str, float] = {}
    deltas: dict[str, float] = {}
    for arm in NEURAL_ARMS:
        value, _ = mean_fold_auc(data["arms"][arm])
        _assert(value is not None, f"baseline AUC unavailable: {target} {arm}")
        observed[arm] = float(value)
        expected_values[arm] = float(expected["arm_metrics"][arm]["mean_fold_roc_auc"])
        deltas[arm] = observed[arm] - expected_values[arm]
    value, _ = mean_fold_auc(data["conventional"])
    _assert(value is not None, f"baseline AUC unavailable: {target} conventional")
    observed["conventional"] = float(value)
    expected_values["conventional"] = float(expected["conventional_metrics"]["mean_fold_roc_auc"])
    deltas["conventional"] = observed["conventional"] - expected_values["conventional"]
    return {"observed": observed, "accepted": expected_values, "delta": deltas, "max_abs_delta": max(abs(v) for v in deltas.values())}


def ensemble_metrics(data: dict[str, Any]) -> dict[str, float]:
    ft = data["arms"][FT]
    result: dict[str, float] = {}
    for label, other in (("conventional", data["conventional"]), ("target_only", data["arms"][TO])):
        fold_gain = []
        for fold in FOLDS:
            y = ft[fold][1]
            score = 0.5 * (ft[fold][2] + other[fold][2])
            ensembled = auc(y, score)
            ft_auc = auc(y, ft[fold][2])
            _assert(ensembled is not None and ft_auc is not None, f"ensemble AUC unavailable fold {fold}")
            fold_gain.append(ensembled - ft_auc)
        result[f"{label}_gain"] = float(np.mean(fold_gain))
    return result


def class_metrics(data: dict[str, Any], class_low: int, class_high: float, min_support: int | None) -> dict[str, Any]:
    per_fold: list[dict[str, Any]] = []
    for fold in FOLDS:
        ids, y, ft_score, richness = data["arms"][FT][fold][:4]
        conv_score = data["conventional"][fold][2]
        other = richness - y.astype(np.int64)
        bg = (y == 0) & (other >= class_low) & (other <= class_high)
        present = y == 1
        required = 1 if min_support is None else int(min_support)
        valid = int(np.sum(present)) >= required and int(np.sum(bg)) >= required
        record = {"fold": fold, "presence_n": int(np.sum(present)), "background_n": int(np.sum(bg)), "available": bool(valid)}
        if valid:
            response = np.concatenate([y[present], y[bg]])
            record["ft_auc"] = auc(response, np.concatenate([ft_score[present], ft_score[bg]]))
            record["conventional_auc"] = auc(response, np.concatenate([conv_score[present], conv_score[bg]]))
            record["ft_minus_conventional"] = record["ft_auc"] - record["conventional_auc"]
        else:
            record.update({"ft_auc": None, "conventional_auc": None, "ft_minus_conventional": None})
        per_fold.append(record)
    valid = all(item["available"] for item in per_fold)
    deltas = [item["ft_minus_conventional"] for item in per_fold if item["ft_minus_conventional"] is not None]
    return {
        "folds": per_fold,
        "available_all_folds": valid,
        "ft_minus_conventional": None if not valid else float(np.mean(deltas)),
        "ft_auc": None if not valid else float(np.mean([item["ft_auc"] for item in per_fold])),
        "conventional_auc": None if not valid else float(np.mean([item["conventional_auc"] for item in per_fold])),
    }


def restricted_high_metrics(data: dict[str, Any], min_support: int = 20) -> dict[str, Any]:
    """AUC where both response classes are restricted to other-richness >=100."""
    fold_records = []
    for fold in FOLDS:
        _, y, ft_score, richness = data["arms"][FT][fold][:4]
        conv_score = data["conventional"][fold][2]
        other = richness - y.astype(np.int64)
        mask = other >= 100
        pos, neg = mask & (y == 1), mask & (y == 0)
        available = int(np.sum(pos)) >= min_support and int(np.sum(neg)) >= min_support
        rec = {"fold": fold, "presence_n": int(np.sum(pos)), "background_n": int(np.sum(neg)), "available": available}
        if available:
            response = y[mask]
            rec["ft_auc"] = auc(response, ft_score[mask])
            rec["conventional_auc"] = auc(response, conv_score[mask])
            rec["ft_minus_conventional"] = rec["ft_auc"] - rec["conventional_auc"]
        else:
            rec.update({"ft_auc": None, "conventional_auc": None, "ft_minus_conventional": None})
        fold_records.append(rec)
    pooled_presence = int(sum(item["presence_n"] for item in fold_records))
    pooled_background = int(sum(item["background_n"] for item in fold_records))
    return {
        "folds": fold_records,
        "available_all_folds": all(item["available"] for item in fold_records),
        "pooled_eligible": pooled_presence >= 100 and pooled_background >= 100,
        "pooled_presence_n": pooled_presence,
        "pooled_background_n": pooled_background,
        "ft_minus_conventional": None if not all(item["available"] for item in fold_records) else float(np.mean([item["ft_minus_conventional"] for item in fold_records])),
    }


def additive_target_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """Return equal-fold additive contributions for one target."""
    fold_all: list[float] = []
    fold_reconstructed: list[float] = []
    fold_contributions = {key: [] for _, _, key in RICHNESS_CLASSES}
    for fold in FOLDS:
        _, y, ft_score, richness = data["arms"][FT][fold][:4]
        conv_score = data["conventional"][fold][2]
        bg_all = y == 0
        all_delta = auc(y, ft_score) - auc(y, conv_score)
        weighted = 0.0
        other = richness - y.astype(np.int64)
        for low, high, key in RICHNESS_CLASSES:
            bg = bg_all & (other >= low) & (other <= high)
            n = int(np.sum(bg))
            contribution = 0.0
            if n:
                response = np.concatenate([y[y == 1], y[bg]])
                d = auc(response, np.concatenate([ft_score[y == 1], ft_score[bg]])) - auc(response, np.concatenate([conv_score[y == 1], conv_score[bg]]))
                contribution = n / int(np.sum(bg_all)) * d
            weighted += contribution
            fold_contributions[key].append(float(contribution))
        fold_all.append(float(all_delta))
        fold_reconstructed.append(float(weighted))
    return {
        "all_background_delta": float(np.mean(fold_all)),
        "reconstructed_delta": float(np.mean(fold_reconstructed)),
        "weighted_contribution": {key: float(np.mean(values)) for key, values in fold_contributions.items()},
        "max_abs_identity_error": float(np.max(np.abs(np.asarray(fold_all) - np.asarray(fold_reconstructed)))),
    }


def richness_summary(rows: dict[str, dict[str, Any]], target_sets: dict[str, set[str]]) -> dict[str, Any]:
    result: dict[str, Any] = {"minimum_per_class_per_fold": 20, "classes": {}}
    class_keys = [item[2] for item in RICHNESS_CLASSES]
    for panel_name, target_set in target_sets.items():
        each: dict[str, Any] = {}
        common = set(target_set)
        for key in class_keys:
            available = {target for target in target_set if rows[target]["richness"][key]["available_all_folds"]}
            common &= available
            each[key] = {
                "targets": len(available),
                "target_names": sorted(available),
                "ft_minus_conventional": stats([rows[t]["richness"][key]["ft_minus_conventional"] for t in sorted(available)], positive=True),
                "eligibility_rule": ">=20 presences and >=20 class backgrounds in every fold",
            }
        pooled_each = {}
        for key in class_keys:
            available = {target for target in target_set if rows[target]["richness"][key]["pooled_eligible"] and rows[target]["richness"][key]["available_all_folds"]}
            pooled_each[key] = {
                "targets": len(available),
                "target_names": sorted(available),
                "ft_minus_conventional": stats([rows[t]["richness"][key]["ft_minus_conventional"] for t in sorted(available)], positive=True),
                "eligibility_rule": ">=20 pooled presences and >=20 pooled class backgrounds; AUC still requires all five fold values",
            }
        common_stats = {
            "targets": len(common),
            "target_names": sorted(common),
            "ft_minus_conventional_by_class": {
                key: stats([rows[t]["richness"][key]["ft_minus_conventional"] for t in sorted(common)], positive=True)
                for key in class_keys
            },
        }
        high = {t for t in common if rows[t]["richness"]["100_plus_both"]["available_all_folds"]}
        common_stats["100_plus_both_support_at_least_100"] = {
            "targets": len(high),
            "target_names": sorted(high),
            "ft_minus_conventional": stats([rows[t]["richness"]["100_plus_both"]["ft_minus_conventional"] for t in sorted(high) if rows[t]["richness"]["100_plus_both"]["ft_minus_conventional"] is not None], positive=True),
            "eligibility_rule": "other-species richness >=100 for both presences and backgrounds; at least 20 of each class in every fold; pooled >=100 is recorded as a consequence/diagnostic, not an added gate",
        }
        result[panel_name] = {"each_stratum_available": each, "pooled_support_eligible": pooled_each, "common_all_strata": common_stats}
    return result


def additive_richness_check(rows: dict[str, dict[str, Any]], target_sets: dict[str, set[str]]) -> dict[str, Any]:
    """Check the exact additive decomposition with no support threshold."""
    result = {}
    for panel, targets in target_sets.items():
        observed_all, reconstructed_all = [], []
        contributions = {key: [] for _, _, key in RICHNESS_CLASSES}
        for target in sorted(targets):
            item = rows[target]["additive"]
            observed_all.append(item["all_background_delta"])
            reconstructed_all.append(item["reconstructed_delta"])
            for key in contributions:
                contributions[key].append(item["weighted_contribution"][key])
        result[panel] = {
            "targets": len(targets),
            "all_background_ft_minus_conventional": stats(observed_all, positive=True),
            "weighted_class_contributions": {key: stats(values, positive=False) for key, values in contributions.items()},
            "sum_weighted_contributions": stats([r for r in reconstructed_all], positive=False),
            "max_abs_identity_error": float(np.max(np.abs(np.asarray(observed_all) - np.asarray(reconstructed_all)))) if observed_all else None,
        }
    return result


def reporting_rate(data: dict[str, Any]) -> dict[str, Any]:
    bins = ((10, 14, "10_14"), (15, 24, "15_24"), (25, 49, "25_49"), (50, 99, "50_99"), (100, math.inf, "100_plus"))
    score = np.concatenate([data["conventional"][fold][2] for fold in FOLDS])
    y = np.concatenate([data["conventional"][fold][1] for fold in FOLDS])
    richness = np.concatenate([data["conventional"][fold][3] - data["conventional"][fold][1] for fold in FOLDS])
    threshold = float(np.quantile(score, 0.8))
    top = score >= threshold
    proportions: dict[str, Any] = {}
    for low, high, key in bins:
        mask = top & (richness >= low) & (richness <= high)
        n = int(np.sum(mask))
        proportions[key] = {"top_cells_n": n, "reporting_proportion": None if n == 0 else float(np.mean(y[mask]))}
    baseline = proportions["100_plus"]["reporting_proportion"]
    for key, item in proportions.items():
        item["ratio_to_100_plus"] = None if not baseline or item["reporting_proportion"] is None else float(item["reporting_proportion"] / baseline)
    return {"threshold_rule": "pooled conventional score 80th percentile; ties retained", "threshold": threshold, "top_cells_n": int(np.sum(top)), "total_cells_n": int(len(score)), "bins": proportions}


def panel_summary(rows: dict[str, dict[str, Any]], targets: set[str]) -> dict[str, Any]:
    return {
        "targets": len(targets),
        "ensemble_gain_ft_plus_conventional": stats([rows[t]["ensemble"]["conventional_gain"] for t in sorted(targets)], positive=True),
        "ensemble_gain_ft_plus_target_only": stats([rows[t]["ensemble"]["target_only_gain"] for t in sorted(targets)], positive=True),
    }


def main() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    _assert(sha256_file(SUMMARY) == ACCEPTED_SUMMARY_SHA256, "accepted Goal052 summary hash drift")
    _assert(sha256_file(GOAL051_SUMMARY) == ACCEPTED_GOAL051_SUMMARY_SHA256, "accepted Goal051 summary hash drift")
    summary = json.loads(SUMMARY.read_text())
    goal051_summary = json.loads(GOAL051_SUMMARY.read_text())
    accepted = {(c["target"], int(c["fraction"]), c["auxiliary"]): c for c in summary["conditions"]}
    target_set = {target for target, fraction, aux in accepted if fraction == 100 and aux == "full"}
    _assert(len(target_set) == 157, "accepted target set drift")
    primary = {target for target, fraction, aux in accepted if fraction == 100 and aux == "full" and accepted[(target, fraction, aux)]["selection_target"]}
    other = target_set - primary
    _assert(len(primary) == 73 and len(other) == 84, "accepted panel membership drift")
    membership_species = load_membership_species()
    _assert(target_set <= membership_species, "accepted focal target missing from frozen membership metadata")
    leaf_index, neural_payload_hash_digest = index_neural_leaves()
    conventional, family_counts, candidate_counts = selected_conventional_index(target_set)
    cells = load_cell_index()

    rows: dict[str, dict[str, Any]] = {}
    max_baseline_delta = 0.0
    baseline_match = True
    for i, target in enumerate(sorted(target_set), start=1):
        data = load_target_data(target, leaf_index, conventional[target], cells)
        expected = accepted[(target, 100, "full")]
        baseline = baseline_metrics(target, data, expected)
        max_baseline_delta = max(max_baseline_delta, baseline["max_abs_delta"])
        baseline_match &= baseline["max_abs_delta"] <= 2e-10
        richness = {}
        for low, high, key in RICHNESS_CLASSES:
            rich = class_metrics(data, low, high, 20)
            rich_any = class_metrics(data, low, high, None)
            pooled_presence = int(sum(item["presence_n"] for item in rich["folds"]))
            pooled_background = int(sum(item["background_n"] for item in rich["folds"]))
            rich["pooled_presence_n"] = pooled_presence
            rich["pooled_background_n"] = pooled_background
            rich["pooled_eligible"] = pooled_presence >= 20 and pooled_background >= 20
            # Keep the no-threshold result only as compact fold summaries so
            # pooled-vs-each-fold eligibility can be reported without arrays.
            rich["no_minimum_available_all_folds"] = rich_any["available_all_folds"]
            richness[key] = rich
        richness["100_plus_both"] = restricted_high_metrics(data)
        rows[target] = {
            "baseline": baseline,
            "ensemble": ensemble_metrics(data),
            "richness": richness,
            "reporting": reporting_rate(data),
            "additive": additive_target_metrics(data),
            "selected_conventional": {"family": conventional[target]["family"], "candidate_id": conventional[target]["candidate_id"]},
        }
        print(f"processed {i}/157", flush=True)

    panel_targets = {"primary73": primary, "other84": other, "all157": target_set}
    additive = additive_richness_check(rows, {"primary73": primary, "other84": other})
    reporting_ratios = {panel: {key: stats([rows[t]["reporting"]["bins"][key]["ratio_to_100_plus"] for t in sorted(targets) if rows[t]["reporting"]["bins"][key]["ratio_to_100_plus"] is not None]) for key in ("10_14", "15_24", "25_49", "50_99", "100_plus")} for panel, targets in panel_targets.items()}
    output = {
        "status": "retained_only_effort_review",
        "board_reference": "Fable board783; supplied definitions",
        "scope": {
            "outer_rows_read": 0,
            "fitting_performed": False,
            "neural_arms": list(NEURAL_ARMS),
            "neural_auxiliary": {FT: "full", TO: "none", FZ: "full", Q: "full"},
            "fraction": 100,
            "architecture": "seawfb_scale",
            "seeds": list(SEEDS),
            "folds": list(FOLDS),
            "processing": "one target at a time, one process, BLAS/OpenMP thread caps set before numerical work",
            "richness_name": "other-species richness = retained effort_richness - focal y; these are richness strata, not measured effort",
            "richness_classes": [{"low": low, "high": None if math.isinf(high) else high, "label": key} for low, high, key in RICHNESS_CLASSES],
            "richness_eligibility": "all presences plus class-specific backgrounds; minimum 20 presences and 20 backgrounds in every fold; equal fold mean; common_all_strata requires all three classes",
            "reporting_rule": "selected conventional score pooled 80th percentile within target; ties retained; association only, not a detection estimate",
            "reporting_minimum_bin_support": None,
        },
        "inputs": {
            "goal052_summary": {"path": str(SUMMARY.relative_to(ROOT)), "sha256": sha256_file(SUMMARY)},
            "goal051_summary": {"path": str(GOAL051_SUMMARY.relative_to(ROOT)), "sha256": sha256_file(GOAL051_SUMMARY)},
            "goal050_cells": {"path": str(CELLS.relative_to(ROOT)), "sha256": sha256_file(CELLS), "columns": ["cell_id", "fold", "effort_richness"]},
            "goal050_memberships": {"path": str(MEMBERSHIPS.relative_to(ROOT)), "sha256": sha256_file(MEMBERSHIPS), "columns": ["species"]},
            "goal052_leaf_key_digest": digest(sorted((str(k), str(v.relative_to(ROOT))) for k, v in leaf_index.items())),
            "goal052_neural_payload_hash_digest": neural_payload_hash_digest,
            "goal051_selected_endpoint_digest": digest({target: {k: v for k, v in info.items() if k != "endpoint_path"} for target, info in conventional.items()}),
        },
        "baseline_auc_match": {"all_157": baseline_match, "tolerance": 2e-10, "max_abs_delta": max_baseline_delta, "per_target": {target: row["baseline"] for target, row in sorted(rows.items())}},
        "ensemble_panels": {panel: panel_summary(rows, targets) for panel, targets in panel_targets.items()},
        "richness_decomposition": richness_summary(rows, {"primary73": primary, "other84": other}),
        "richness_additive_check_no_minimum": additive,
        "reporting_rate": {"panel_ratios_to_100_plus": reporting_ratios, "per_target": {target: row["reporting"] for target, row in sorted(rows.items())}},
        "selected_conventional": {"family_counts": dict(sorted(family_counts.items())), "candidate_counts": dict(sorted(candidate_counts.items())), "per_target": {target: row["selected_conventional"] for target, row in sorted(rows.items())}},
        "per_species": {target: {"baseline": row["baseline"], "ensemble": row["ensemble"], "richness": row["richness"], "additive": row["additive"], "selected_conventional": row["selected_conventional"]} for target, row in sorted(rows.items())},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output["analysis_script_sha256"] = sha256_file(Path(__file__))
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)), "baseline_match": baseline_match, "max_abs_baseline_delta": max_baseline_delta, "family_counts": dict(family_counts)}, indent=2))


if __name__ == "__main__":
    main()
