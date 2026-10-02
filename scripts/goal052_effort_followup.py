"""Reproduce the bounded Fable810 retained-only follow-up.

This is a read-only diagnostic over accepted inner prediction leaves and the
accepted Goal051 target100 endpoints.  It deliberately does not fit models or
open outer responses.  Payloads are read one focal target at a time; the JSON
result contains only provenance, aggregates, and per-species summaries.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

for _thread_var in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_var, "1")

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from goal052_effort_review import (  # noqa: E402
    ACCEPTED_GOAL051_SUMMARY_SHA256,
    ACCEPTED_SUMMARY_SHA256,
    CELLS,
    ENDPOINTS,
    FOLDS,
    GOAL051_ROOT,
    GOAL051_SUMMARY,
    GOAL052_ROOT,
    LEAVES,
    MEMBERSHIPS,
    SEEDS,
    SUMMARY,
    auc,
    digest,
    load_cell_index,
    load_membership_species,
    selected_conventional_index,
    sha256_file,
    stats,
)

OUTPUT = ROOT / "evidence/seawfb_dsdm/goal052/effort-followup-20261002.json"
FIRST_REVIEW = ROOT / "evidence/seawfb_dsdm/goal052/effort-review-20261001.json"
FIRST_REVIEW_SCRIPT = ROOT / "scripts/goal052_effort_review.py"
FT = "multihead_full_finetune"
TO = "target_only_random_init_resmlp"
TREES = {"random_forest", "hist_gradient_boosting"}
ANN = "shallow_ann"
CLASS_DEFS = ((10, 24, "10_24"), (25, 99, "25_99"), (100, math.inf, "100_plus"))
REPORT_BINS = (
    (10, 14, "10_14"),
    (15, 24, "15_24"),
    (25, 49, "25_49"),
    (50, 99, "50_99"),
    (100, 199, "100_199"),
    (200, math.inf, "200_plus"),
)
ZERO_REFERENCE_EXPECTED = {
    "Lophorina paradisea",
    "Melithreptus gularis",
    "Orthonyx temminckii",
    "Ptilinopus superbus",
    "Sericornis citreogularis",
    "Tregellasia capito",
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def accepted_target_sets(first: dict[str, Any]) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    summary = json.loads(SUMMARY.read_text())
    accepted = {(c["target"], int(c["fraction"]), c["auxiliary"]): c for c in summary["conditions"]}
    all_targets = {target for target, fraction, aux in accepted if fraction == 100 and aux == "full"}
    primary = {
        target
        for target in all_targets
        if accepted[(target, 100, "full")]["selection_target"]
    }
    other = all_targets - primary
    check(len(all_targets) == 157 and len(primary) == 73 and len(other) == 84, "accepted target-panel drift")
    rich = first["richness_decomposition"]
    primary_common = set(rich["primary73"]["common_all_strata"]["target_names"])
    other_common = set(rich["other84"]["common_all_strata"]["target_names"])
    check(len(primary_common) == 59 and len(other_common) == 83, "first-review common support drift")
    common = primary_common | other_common
    check(len(common) == 142 and primary_common <= primary and other_common <= other, "common panel drift")
    return all_targets, primary, other, primary_common, other_common


def index_leaves(ft_targets: set[str], to_targets: set[str]) -> tuple[dict[tuple[str, str, str, int], Path], dict[str, str]]:
    """Index and verify only the FT grid and the requested TO grid."""
    result: dict[tuple[str, str, str, int], Path] = {}
    hashes: dict[str, str] = {}
    for receipt_path in sorted(LEAVES.glob("*.json")):
        receipt = json.loads(receipt_path.read_text())
        key = receipt.get("key", {})
        target = str(key.get("target"))
        arm = key.get("arm")
        if (
            target not in (ft_targets | to_targets)
            or key.get("fraction") != 100
            or key.get("architecture") != "seawfb_scale"
            or arm not in (FT, TO)
            or (arm == TO and key.get("auxiliary") != "none")
            or (arm == FT and key.get("auxiliary") != "full")
            or key.get("seed_label") not in SEEDS
        ):
            continue
        path = receipt_path.with_suffix(".parquet")
        check(path.is_file(), f"missing leaf payload: {path.name}")
        declared = receipt.get("prediction_sha256")
        check(isinstance(declared, str) and len(declared) == 64, f"missing leaf hash: {receipt_path.name}")
        check(sha256_file(path) == declared, f"leaf hash mismatch: {receipt_path.name}")
        identity = (target, str(arm), str(key["seed_label"]), int(key["fold"]))
        check(identity not in result, f"duplicate leaf: {identity}")
        result[identity] = path
        hashes[json.dumps(identity, separators=(",", ":"))] = declared
    for target in sorted(ft_targets | to_targets):
        for arm, arm_targets in ((FT, ft_targets), (TO, to_targets)):
            if target not in arm_targets:
                continue
            for seed in SEEDS:
                for fold in FOLDS:
                    check((target, arm, seed, fold) in result, f"leaf grid incomplete: {target} {arm} {seed} {fold}")
    return result, hashes


def read_leaf(path: Path, cells: dict[str, tuple[int, int]], fold: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows = pq.read_table(path, columns=["cell_id", "y", "score"]).to_pydict()
    ids = np.asarray(rows["cell_id"], dtype=str)
    y = np.asarray(rows["y"], dtype=np.int8)
    score = np.asarray(rows["score"], dtype=np.float64)
    check(len(ids) == len(set(ids.tolist())), f"duplicate cells in {path.name}")
    check(np.isin(y, (0, 1)).all() and np.isfinite(score).all(), f"invalid leaf payload: {path.name}")
    known = [cells.get(cell) for cell in ids]
    check(all(x is not None for x in known), f"leaf cell outside retained cells: {path.name}")
    fold_values = np.asarray([x[0] for x in known], dtype=np.int8)
    richness = np.asarray([x[1] for x in known], dtype=np.int64)
    check(np.all(fold_values == fold), f"leaf fold mismatch: {path.name}")
    check(np.all(richness[y == 1] >= 1), f"focal presence exceeds richness: {path.name}")
    order = np.argsort(ids, kind="mergesort")
    return ids[order], y[order], score[order], richness[order]


def read_neural_target(
    target: str,
    arm: str,
    leaf_index: dict[tuple[str, str, str, int], Path],
    cells: dict[str, tuple[int, int]],
) -> dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    result: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    for fold in FOLDS:
        ids0 = y0 = richness0 = None
        scores: list[np.ndarray] = []
        for seed in SEEDS:
            ids, y, score, richness = read_leaf(leaf_index[(target, arm, seed, fold)], cells, fold)
            if ids0 is None:
                ids0, y0, richness0 = ids, y, richness
            else:
                check(np.array_equal(ids, ids0) and np.array_equal(y, y0) and np.array_equal(richness, richness0), f"seed alignment drift: {target} {arm} fold {fold}")
            scores.append(score)
        check(ids0 is not None and y0 is not None and richness0 is not None, "empty seed grid")
        result[fold] = (ids0, y0, np.mean(np.vstack(scores), axis=0, dtype=np.float64), richness0)
    return result


def read_endpoint(
    target: str,
    info: dict[str, Any],
    cells: dict[str, tuple[int, int]],
) -> dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Read selected rows, preserving source order for the qcut rule."""
    path = ROOT / info["endpoint_path"]
    family, candidate = info["family"], info["candidate_id"]
    rows = pq.read_table(path, columns=["fold", "cell_id", "y", "method", "family", "candidate_id", "score"]).to_pydict()
    mask = np.asarray(
        [m == "family_selected" and f == family and str(c) == candidate for m, f, c in zip(rows["method"], rows["family"], rows["candidate_id"])],
        dtype=bool,
    )
    all_fold = np.asarray(rows["fold"], dtype=np.int8)[mask]
    all_ids = np.asarray(rows["cell_id"], dtype=str)[mask]
    all_y = np.asarray(rows["y"], dtype=np.int8)[mask]
    all_score = np.asarray(rows["score"], dtype=np.float64)[mask]
    result: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    for fold in FOLDS:
        fold_mask = all_fold == fold
        raw_ids, raw_y, raw_score = all_ids[fold_mask], all_y[fold_mask], all_score[fold_mask]
        check(len(raw_ids) == len(set(raw_ids.tolist())), f"duplicate endpoint cells: {target} fold {fold}")
        check(np.isin(raw_y, (0, 1)).all() and np.isfinite(raw_score).all(), f"invalid endpoint payload: {target}")
        known = [cells.get(cell) for cell in raw_ids]
        check(all(x is not None for x in known), f"endpoint cell outside retained cells: {target}")
        check(all(x[0] == fold for x in known), f"endpoint fold mismatch: {target} fold {fold}")
        richness = np.asarray([x[1] for x in known], dtype=np.int64)
        check(np.all(richness[raw_y == 1] >= 1), f"endpoint focal presence exceeds richness: {target}")
        order = np.argsort(raw_ids, kind="mergesort")
        # The compact final tuple keeps source order plus aligned y/richness;
        # scores and ids are retained only until this target has been reduced.
        result[fold] = (raw_ids, raw_y, raw_score, richness, raw_ids[order], np.column_stack((raw_y[order], richness[order])))
    check(all(fold in result for fold in FOLDS), f"endpoint fold grid incomplete: {target}")
    return result


def aligned_endpoint(endpoint: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]], fold: int, ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    raw_ids, raw_y, raw_score, raw_richness, sorted_ids, sorted_y_richness = endpoint[fold]
    check(np.array_equal(sorted_ids, ids), "conventional/neural cell alignment drift")
    return sorted_y_richness[:, 0].astype(np.int8), sorted_y_richness[:, 1].astype(np.int64)


def class_metric(
    ft: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    other_score: dict[int, np.ndarray],
    endpoint: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    low: int,
    high: float,
) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    for fold in FOLDS:
        ids, y, ft_score, richness = ft[fold]
        conv_y, conv_richness = aligned_endpoint(endpoint, fold, ids)
        check(np.array_equal(y, conv_y) and np.array_equal(richness, conv_richness), "endpoint response/richness drift")
        other_richness = richness - y.astype(np.int64)
        background = (y == 0) & (other_richness >= low) & (other_richness <= high)
        presence = y == 1
        presence_n, background_n = int(np.sum(presence)), int(np.sum(background))
        available = presence_n >= 20 and background_n >= 20
        record: dict[str, Any] = {"fold": fold, "presence_n": presence_n, "background_n": background_n, "available": available}
        if available:
            response = np.concatenate([y[presence], y[background]])
            f_auc = auc(response, np.concatenate([ft_score[presence], ft_score[background]]))
            o_auc = auc(response, np.concatenate([other_score[fold][presence], other_score[fold][background]]))
            check(f_auc is not None and o_auc is not None, "class AUC unexpectedly undefined")
            record["delta"] = float(f_auc - o_auc)
        else:
            record["delta"] = None
        folds.append(record)
    available = all(x["available"] for x in folds)
    deltas = [x["delta"] for x in folds if x["delta"] is not None]
    return {"available_all_folds": available, "folds": folds, "delta": None if not available else float(np.mean(deltas))}


def ensemble_gain(
    ft: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    other_score: dict[int, np.ndarray],
    endpoint: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
) -> float:
    gains: list[float] = []
    for fold in FOLDS:
        ids, y, ft_score, _ = ft[fold]
        conv_y, _ = aligned_endpoint(endpoint, fold, ids)
        check(np.array_equal(y, conv_y), "ensemble response alignment drift")
        ft_auc = auc(y, ft_score)
        conv_or_to = other_score[fold]
        score = 0.5 * (ft_score + conv_or_to)
        mixed_auc = auc(y, score)
        check(ft_auc is not None and mixed_auc is not None, "ensemble AUC unexpectedly undefined")
        gains.append(float(mixed_auc - ft_auc))
    return float(np.mean(gains))


def reporting_summary(endpoint: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]) -> dict[str, Any]:
    top_y: list[np.ndarray] = []
    top_richness: list[np.ndarray] = []
    fold_meta: list[dict[str, Any]] = []
    for fold in FOLDS:
        raw_ids, y, score, raw_richness, sorted_ids, sorted_y_richness = endpoint[fold]
        ranks = pd.Series(score).rank(method="first")
        labels = pd.qcut(ranks, q=10, labels=False, duplicates="drop")
        top = np.asarray(labels.isin((8, 9)), dtype=bool)
        check(np.sum(top) > 0, "qcut produced no top decile rows")
        top_y.append(y[top])
        # Source order is retained in the endpoint tuple; use source-order y
        # and frozen richness for the specified ranking rule.
        top_richness.append(raw_richness[top].astype(np.int64) - y[top].astype(np.int64))
        top_score = score[top]
        boundary = float(np.min(top_score))
        tie_n = int(np.sum(score == boundary))
        crosses = bool(np.any((score == boundary) & ~top))
        id_order = np.argsort(raw_ids, kind="mergesort")
        id_labels = pd.qcut(pd.Series(score[id_order]).rank(method="first"), q=10, labels=False, duplicates="drop")
        id_top = np.zeros(len(score), dtype=bool)
        id_top[id_order] = np.asarray(id_labels.isin((8, 9)), dtype=bool)
        fold_meta.append({"fold": fold, "top_n": int(np.sum(top)), "total_n": int(len(score)), "boundary_tie_n": tie_n, "boundary_tie_crosses_cut": crosses, "top_fraction": float(np.mean(top)), "cell_id_order_changed_top_membership_n": int(np.sum(top != id_top)), "cell_id_order_presence_n": int(np.sum(y[id_top]))})
    y = np.concatenate(top_y)
    richness = np.concatenate(top_richness)
    values: dict[str, dict[str, Any]] = {}
    for low, high, key in REPORT_BINS:
        mask = (richness >= low) & (richness <= high)
        n = int(np.sum(mask))
        presence_n = int(np.sum(y[mask]))
        values[key] = {"top_cells_n": n, "presence_n": presence_n, "reporting_proportion": None if n == 0 else float(np.mean(y[mask]))}
    ref = values["200_plus"]
    ref_prop = ref["reporting_proportion"]
    for item in values.values():
        prop = item["reporting_proportion"]
        item["ratio_to_200_plus_clipped"] = None if prop is None or not ref_prop else float(min(prop / ref_prop, 1.0))
    pooled = values["100_199"]["top_cells_n"] + values["200_plus"]["top_cells_n"]
    pooled_presence = values["100_199"]["presence_n"] + values["200_plus"]["presence_n"]
    pooled_prop = None if pooled == 0 else pooled_presence / pooled
    for key in ("10_14", "15_24", "25_49", "50_99"):
        prop = values[key]["reporting_proportion"]
        values[key]["ratio_to_100_plus_unclipped"] = None if prop is None or not pooled_prop else float(prop / pooled_prop)
    values["100_plus_pooled"] = {"top_cells_n": pooled, "presence_n": pooled_presence, "reporting_proportion": pooled_prop, "reference": True}
    return {
        "folds": fold_meta,
        "bins": values,
        "reference_200_plus_presence_n": int(ref["presence_n"]),
        "reference_200_plus_cells_n": int(ref["top_cells_n"]),
        "max_observed_other_richness": int(np.max(richness)) if len(richness) else None,
    }


def reporting_panel(per_target: dict[str, dict[str, Any]], targets: set[str]) -> dict[str, Any]:
    eligible = [target for target in sorted(targets) if per_target[target]["reporting"]["reference_200_plus_presence_n"] > 0]
    medians: dict[str, Any] = {}
    for key in ("10_14", "15_24", "25_49", "50_99"):
        clipped = [per_target[t]["reporting"]["bins"][key]["ratio_to_200_plus_clipped"] for t in eligible]
        pooled = [per_target[t]["reporting"]["bins"][key]["ratio_to_100_plus_unclipped"] for t in eligible]
        medians[key] = {"clipped_to_200_plus": stats(clipped), "unclipped_to_pooled_100_plus": stats(pooled)}
    excluded = sorted(set(targets) - set(eligible))
    details = {
        target: {
            "reference_200_plus_top_cells_n": per_target[target]["reporting"]["reference_200_plus_cells_n"],
            "reference_200_plus_presence_n": per_target[target]["reporting"]["reference_200_plus_presence_n"],
            "denominator_defined": per_target[target]["reporting"]["reference_200_plus_presence_n"] > 0,
        }
        for target in excluded
    }
    return {"targets": len(targets), "eligible_reference_presence": len(eligible), "excluded_zero_reference_presence": excluded, "excluded_reference_details": details, "medians": medians}


def adaptive_reporting_panel(per_target: dict[str, dict[str, Any]], targets: set[str]) -> dict[str, Any]:
    """Apply the supplied 151-target interpretation without tuning cutoffs.

    The literal 200+ bin is empty for many targets in the frozen cells table.
    For this diagnostic, the adaptive reference is the highest nonempty
    top-decile richness bin. A target
    with zero presences in that reference remains excluded.  This is reported
    separately from the literal fixed-200+ rule.
    """
    references: dict[str, str | None] = {}
    for target in sorted(targets):
        bins = per_target[target]["reporting"]["bins"]
        references[target] = next((key for _, _, key in reversed(REPORT_BINS)
                                   if bins[key]["top_cells_n"] > 0), None)
    eligible = [target for target in sorted(targets) if references[target] is not None and per_target[target]["reporting"]["bins"][references[target]]["presence_n"] > 0]
    medians: dict[str, Any] = {}
    for key in ("10_14", "15_24", "25_49", "50_99"):
        clipped: list[float] = []
        pooled: list[float] = []
        for target in eligible:
            bins = per_target[target]["reporting"]["bins"]
            ref = bins[references[target]]
            prop = bins[key]["reporting_proportion"]
            if prop is not None and ref["reporting_proportion"]:
                clipped.append(float(min(prop / ref["reporting_proportion"], 1.0)))
            high_n = bins["100_199"]["top_cells_n"] + bins["200_plus"]["top_cells_n"]
            high_presence = bins["100_199"]["presence_n"] + bins["200_plus"]["presence_n"]
            high_prop = None if high_n == 0 else high_presence / high_n
            if prop is not None and high_prop:
                pooled.append(float(prop / high_prop))
        medians[key] = {"clipped_to_highest_nonempty": stats(clipped), "unclipped_to_pooled_100_plus": stats(pooled)}
    excluded = sorted(set(targets) - set(eligible))
    details = {
        target: {
            "reference_bin": references[target],
            "reference_top_cells_n": None if references[target] is None else per_target[target]["reporting"]["bins"][references[target]]["top_cells_n"],
            "reference_presence_n": None if references[target] is None else per_target[target]["reporting"]["bins"][references[target]]["presence_n"],
            "denominator_defined": target in eligible,
        }
        for target in excluded
    }
    return {
        "targets": len(targets),
        "eligible_reference_presence": len(eligible),
        "reference_bin_counts": {key: sum(value == key for value in references.values())
                                 for _, _, key in REPORT_BINS if key in references.values()},
        "excluded_zero_reference_presence": excluded,
        "excluded_reference_details": details,
        "medians": medians,
        "rule": "highest nonempty top-decile bin per target; zero reference presences excluded; no threshold tuned",
    }


def class_panel(per_target: dict[str, dict[str, Any]], targets: set[str], metric_name: str, family: str | None = None) -> dict[str, Any]:
    chosen = [target for target in sorted(targets) if family is None or per_target[target]["family_group"] == family]
    result: dict[str, Any] = {"targets": len(chosen), "classes": {}}
    for _, _, key in CLASS_DEFS:
        vals = [per_target[t][metric_name][key]["delta"] for t in chosen if per_target[t][metric_name][key]["delta"] is not None]
        result["classes"][key] = stats(vals, positive=True)
    return result


def main() -> None:
    check(sha256_file(SUMMARY) == ACCEPTED_SUMMARY_SHA256, "accepted Goal052 summary hash drift")
    check(sha256_file(GOAL051_SUMMARY) == ACCEPTED_GOAL051_SUMMARY_SHA256, "accepted Goal051 summary hash drift")
    first = json.loads(FIRST_REVIEW.read_text())
    check(first["analysis_script_sha256"] == sha256_file(FIRST_REVIEW_SCRIPT), "first-review script provenance drift")
    for key, path in (("goal052_summary", SUMMARY), ("goal051_summary", GOAL051_SUMMARY), ("goal050_cells", CELLS), ("goal050_memberships", MEMBERSHIPS)):
        check(first["inputs"][key]["sha256"] == sha256_file(path), f"first-review input provenance drift: {key}")
    all_targets, primary, other, primary_common, other_common = accepted_target_sets(first)
    common = primary_common | other_common
    membership_species = load_membership_species()
    check(all_targets <= membership_species, "accepted focal target missing from frozen membership metadata")
    cells = load_cell_index()
    conventional, family_counts, candidate_counts = selected_conventional_index(all_targets)
    leaf_index, leaf_hashes = index_leaves(all_targets, common)
    for target in sorted(all_targets):
        for seed in SEEDS:
            for fold in FOLDS:
                check((target, FT, seed, fold) in leaf_index, f"FT leaf missing: {target}")
                if target in common:
                    check((target, TO, seed, fold) in leaf_index, f"TO leaf missing: {target}")
    rows: dict[str, dict[str, Any]] = {}
    endpoint_hashes = {}
    for target in sorted(all_targets):
        endpoint_hashes[target] = {"endpoint_json_sha256": conventional[target]["endpoint_json_sha256"], "prediction_sha256": conventional[target]["endpoint_prediction_sha256_declared"]}
        endpoint = read_endpoint(target, conventional[target], cells)
        ft = read_neural_target(target, FT, leaf_index, cells)
        conv_score: dict[int, np.ndarray] = {}
        for fold in FOLDS:
            ids, y, _, richness = ft[fold]
            conv_y, conv_richness = aligned_endpoint(endpoint, fold, ids)
            raw_ids, raw_y, raw_score, raw_richness, sorted_ids, sorted_y_richness = endpoint[fold]
            order = np.argsort(raw_ids, kind="mergesort")
            score_sorted = raw_score[order]
            check(np.array_equal(conv_y, y) and np.array_equal(conv_richness, richness), f"endpoint alignment drift: {target} fold {fold}")
            conv_score[fold] = score_sorted
        class_conv: dict[str, Any] = {}
        for low, high, key in CLASS_DEFS:
            class_conv[key] = class_metric(ft, conv_score, endpoint, low, high)
        family = conventional[target]["family"]
        row: dict[str, Any] = {
            "family": family,
            "candidate_id": conventional[target]["candidate_id"],
            "family_group": "trees" if family in TREES else "ann",
            "ft_minus_conventional": {key: class_conv[key] for _, _, key in CLASS_DEFS},
            "ensemble_ft_plus_conventional_gain": ensemble_gain(ft, conv_score, endpoint),
            "reporting": reporting_summary(endpoint),
        }
        if target in common:
            to = read_neural_target(target, TO, leaf_index, cells)
            for fold in FOLDS:
                check(np.array_equal(to[fold][0], ft[fold][0]) and np.array_equal(to[fold][1], ft[fold][1]) and np.array_equal(to[fold][3], ft[fold][3]), f"FT-TO cell/y/richness alignment drift: {target} fold {fold}")
            to_score = {fold: to[fold][2] for fold in FOLDS}
            class_to: dict[str, Any] = {}
            for low, high, key in CLASS_DEFS:
                class_to[key] = class_metric(ft, to_score, endpoint, low, high)
            row["ft_minus_target_only"] = class_to
            row["ensemble_ft_plus_target_only_gain"] = ensemble_gain(ft, to_score, endpoint)
            del to, to_score
        rows[target] = row
        del ft, conv_score, endpoint
        print(f"processed {len(rows)}/157", flush=True)

    common_panel = {"targets": 142, "primary59": 59, "other83": 83}
    output = {
        "status": "retained_only_effort_followup",
        "board_reference": "Fable810 exact reporting rule and matched-twin/family follow-up",
        "scope": {
            "outer_rows_read": 0,
            "fitting_performed": False,
            "arms_used": [FT, TO],
            "fraction": 100,
            "architecture": "seawfb_scale",
            "seeds": list(SEEDS),
            "folds": list(FOLDS),
            "processing": "one process, one target at a time; FT all157 and TO matched142 only; BLAS/OpenMP caps set before numerical work",
            "richness_name": "other-species richness = frozen effort_richness - focal y; richness strata, not measured effort",
            "class_support_rule": "all presences against class-specific backgrounds; >=20 presences and >=20 backgrounds in every fold; equal fold mean; common panels inherit the frozen first-review three-class support set",
            "reporting_rule": "selected conventional target100 OOF scores; within each held fold rank(method='first'), pandas qcut(10), top labels 8 and 9 pooled; original endpoint Parquet row order resolves score ties",
            "reporting_bins": [
                {"low": low, "high": None if math.isinf(high) else high, "label": key} for low, high, key in REPORT_BINS
            ],
            "reporting_reference": "literal fixed 200+ and separately each target's highest nonempty top-decile bin",
            "reporting_ratios": "lower-bin reporting proportions divided by reference, clipped above at 1; companion pooled100+ reference is unclipped",
            "reporting_minimum_bin_support": None,
            "reporting_association_only": True,
        },
        "inputs": {
            "first_review": {"path": str(FIRST_REVIEW.relative_to(ROOT)), "sha256": sha256_file(FIRST_REVIEW)},
            "first_review_script": {"path": str(FIRST_REVIEW_SCRIPT.relative_to(ROOT)), "sha256": sha256_file(FIRST_REVIEW_SCRIPT), "stored_sha256": first["analysis_script_sha256"]},
            "goal052_summary": {"path": str(SUMMARY.relative_to(ROOT)), "sha256": sha256_file(SUMMARY)},
            "goal051_summary": {"path": str(GOAL051_SUMMARY.relative_to(ROOT)), "sha256": sha256_file(GOAL051_SUMMARY)},
            "goal050_cells": {"path": str(CELLS.relative_to(ROOT)), "sha256": sha256_file(CELLS), "columns": ["cell_id", "fold", "effort_richness"]},
            "goal050_memberships": {"path": str(MEMBERSHIPS.relative_to(ROOT)), "sha256": sha256_file(MEMBERSHIPS), "columns": ["species"]},
            "goal052_leaf_key_digest": digest(sorted((str(k), str(v.relative_to(ROOT))) for k, v in leaf_index.items())),
            "goal052_payload_hash_digest": digest(leaf_hashes),
            "goal051_selected_endpoint_digest": digest(endpoint_hashes),
            "goal051_root": str(GOAL051_ROOT.relative_to(ROOT)),
            "goal052_root": str(GOAL052_ROOT.relative_to(ROOT)),
        },
        "provenance_checks": {
            "first_review_script_hash_matches_stored": True,
            "first_review_source_input_hashes_match_current": True,
            "ft_to_cell_y_richness_alignment_checked": True,
            "outer_rows_read": 0,
        },
        "selected_conventional": {"family_counts": dict(sorted(family_counts.items())), "candidate_counts": dict(sorted(candidate_counts.items()))},
        "matched_panels": common_panel,
        "class_checks": {
            "ft_minus_target_only": {
                "all142": class_panel(rows, common, "ft_minus_target_only"),
                "primary59": class_panel(rows, primary_common, "ft_minus_target_only"),
                "other83": class_panel(rows, other_common, "ft_minus_target_only"),
            },
            "ft_minus_conventional": {
                "all142": class_panel(rows, common, "ft_minus_conventional"),
                "primary59": class_panel(rows, primary_common, "ft_minus_conventional"),
                "other83": class_panel(rows, other_common, "ft_minus_conventional"),
                "all142_trees103": class_panel(rows, common, "ft_minus_conventional", "trees"),
                "all142_ann39": class_panel(rows, common, "ft_minus_conventional", "ann"),
            },
        },
        "ensemble_checks": {
            panel: {
                "targets": len(targets),
                "ft_plus_conventional": stats([rows[t]["ensemble_ft_plus_conventional_gain"] for t in sorted(targets)], positive=True),
                "ft_plus_target_only": stats([rows[t]["ensemble_ft_plus_target_only_gain"] for t in sorted(targets) if "ensemble_ft_plus_target_only_gain" in rows[t]], positive=True),
            }
            for panel, targets in {"all157": all_targets, "primary73": primary, "other84": other, "matched142": common}.items()
        },
        "ensemble_family_checks": {
            group: {
                "targets": sum(rows[t]["family_group"] == group for t in all_targets),
                "ft_plus_conventional": stats([rows[t]["ensemble_ft_plus_conventional_gain"] for t in sorted(all_targets) if rows[t]["family_group"] == group], positive=True),
            }
            for group in ("trees", "ann")
        },
        "reporting_rate_exact": {
            "zero_reference_expected": sorted(ZERO_REFERENCE_EXPECTED),
            "panels": {
                "literal_fixed_200_plus_all157": reporting_panel(rows, all_targets),
                "literal_fixed_200_plus_primary73": reporting_panel(rows, primary),
                "literal_fixed_200_plus_other84": reporting_panel(rows, other),
                "adaptive_highest_nonempty_all157": adaptive_reporting_panel(rows, all_targets),
                "adaptive_highest_nonempty_primary73": adaptive_reporting_panel(rows, primary),
                "adaptive_highest_nonempty_other84": adaptive_reporting_panel(rows, other),
            },
            "per_species": {target: rows[target]["reporting"] for target in sorted(all_targets)},
            "tie_limitation": "rank(method='first') is deterministic for ties only after preserving the source endpoint Parquet row order; Fable's original tie-row convention was not supplied, so no cutoff was tuned to the claimed medians",
            "source_order_tie_audit": {
                "target_folds": sum(len(row["reporting"]["folds"]) for row in rows.values()),
                "folds_with_changed_membership": sum(
                    fold["cell_id_order_changed_top_membership_n"] > 0
                    for row in rows.values() for fold in row["reporting"]["folds"]),
                "changed_membership_total": sum(
                    fold["cell_id_order_changed_top_membership_n"]
                    for row in rows.values() for fold in row["reporting"]["folds"]),
            },
        },
        "per_species": rows,
        "comparison_to_claimed": {
            "claimed_151_clipped_200_plus_medians": {"10_14": 0.122, "15_24": 0.203, "25_49": 0.367, "50_99": 0.679},
            "claimed_151_unclipped_pooled100_plus_medians": {"10_14": 0.126, "15_24": 0.203, "25_49": 0.376, "50_99": 0.712},
            "first_review_old_rule": "157-target pooled score 80th percentile with ties retained; retained only for scope comparison, not used for this exact rule",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output["analysis_script_sha256"] = sha256_file(Path(__file__))
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "reporting_fixed_200_plus": output["reporting_rate_exact"]["panels"]["literal_fixed_200_plus_all157"]["eligible_reference_presence"],
        "reporting_highest_nonempty": output["reporting_rate_exact"]["panels"]["adaptive_highest_nonempty_all157"]["eligible_reference_presence"],
        "class_ft_to_all142": output["class_checks"]["ft_minus_target_only"]["all142"],
        "ensemble_family": output["ensemble_family_checks"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
