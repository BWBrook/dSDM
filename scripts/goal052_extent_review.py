"""Reproduce the post hoc Goal052 bird extent and ensemble checks.

This is an aggregate-only reader.  It does not fit, tune, or invoke the native
outer response loader.  Inner summaries use the retained five-fold prediction
leaves and the response-free Goal048 region ledger.  Outer summaries use the
accepted, closed prediction vectors and reconstruct only the labels/richness
arrays through the already-reviewed canonical row reader.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import numpy as np
import pyarrow.parquet as pq
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "evidence/seawfb_dsdm/goal052/summary.json"
GOAL051_SUMMARY = ROOT / "evidence/seawfb_conventional/goal051/summary.json"
CELLS = ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/cells.parquet"
LEDGER = ROOT / "data/processed/dsdm/goal048-seawfb-bioregional-freeze/response_free/cell_region_ledger.parquet"
MEMBERSHIPS = ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/memberships.parquet"
OUTER = ROOT / "data/processed/dsdm/goal052-seawfb-dsdm-experiment/outer-assessment-20261003-r2"
OUTER_PLAN = OUTER / "plan.json"
OUTER_CLOSURE = OUTER / "closure.json"
OUTER_SCORES = OUTER / "scores.json"
OUTER_ACCEPTANCE = ROOT / "evidence/seawfb_dsdm/goal052/outer-acceptance-20261005.json"
OUTPUT = ROOT / "evidence/seawfb_dsdm/goal052/extent-review-20261005.json"
REPORT = ROOT / "docs/goals/052-seawfb-dsdm-experiment/ExtentReview-20261005.md"

SUMMARY_SHA256 = "ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3"
GOAL051_SUMMARY_SHA256 = "9c1bf1ff8884fae35fe7ebe6f8d19e2aae46ab7eedee252b398c0c74705dd2d8"
LEDGER_SHA256 = "0c14fcc5c9d39c1c1a6587c52f41deb69d5ecb7cbc86225ec170127dda63d890"
OUTER_SCORES_SHA256 = "3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41"
OUTER_PLAN_SHA256 = "377a3caf3537eaae727e5830f374ae9166f469b9afefb0d116556d12e75edc75"
OUTER_CLOSURE_SHA256 = "aa5b7949cd0c76bb324edde55d5209e0fbf8447b9e00f45a0efa5850ce185063"
OUTER_DOMAIN_SHA256 = "302b18ee8f2c1451e72d946f1aadec9c0d8aac62f752cc870d10b056140867ce"
PRIMARY_N = 73
TARGET_N = 157
FOLDS = tuple(range(5))
INNER_REGIONS = ("BBS", "KAN", "NAN", "NET", "NSS", "SCP", "SEC", "SEQ", "SVP", "SYB", "VIM")
OUTER_REGIONS = ("NCP", "SEH", "NNC")
SEEDS = tuple(f"seed{i:02d}" for i in range(5))
FT = "multihead_full_finetune"
TO = "target_only_random_init_resmlp"
FZ = "multihead_frozen_trunk"
Q = "target_plus_q_linear_resmlp"
CONV = "conventional"
ARMS = (FT, TO, FZ, Q, CONV)
OUTER_ARMS = ("target_only_random_init_resmlp", "target_plus_q_linear_resmlp", "multihead_frozen_trunk", "multihead_full_finetune", "selected_conventional", "selected_conventional_plus_q", "fixed_ensemble")
METRIC_ARMS = {FT: FT, TO: TO, FZ: FZ, Q: Q, CONV: CONV, "ft_conv_ensemble": "ft_conv_ensemble", "to_conv_ensemble": "to_conv_ensemble"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    labels = np.asarray(labels, dtype=np.int8)
    scores = np.asarray(scores, dtype=np.float64)
    require(labels.ndim == scores.ndim == 1 and len(labels) == len(scores), "AUC vector mismatch")
    require(np.isin(labels, (0, 1)).all() and np.isfinite(scores).all(), "invalid AUC values")
    if len(labels) == 0 or np.unique(labels).size != 2:
        return None
    return float(roc_auc_score(labels, scores))


def finite_mean(values: Iterable[float | None]) -> float | None:
    values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return None if not values else float(np.mean(np.asarray(values, dtype=np.float64)))


def distribution(values: Iterable[float | None]) -> dict[str, Any]:
    values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not values:
        return {"n": 0, "mean": None, "median": None, "positive": 0, "min": None, "max": None, "quantiles": {}}
    x = np.asarray(values, dtype=np.float64)
    return {
        "n": int(len(x)), "mean": float(np.mean(x)), "median": float(np.median(x)),
        "positive": int(np.sum(x > 0)), "min": float(np.min(x)), "max": float(np.max(x)),
        "quantiles": {key: float(np.quantile(x, q)) for key, q in (("q05", .05), ("q10", .10), ("q25", .25), ("q75", .75), ("q90", .90), ("q95", .95))},
    }


def load_goal052_helpers():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import goal052_effort_review as effort
    from goal052_outer_score_recovery import import_response
    return effort, import_response(ROOT)


def load_region_index(cells: Mapping[str, tuple[int, int]]) -> tuple[dict[str, str | None], dict[str, int]]:
    require(sha256_file(LEDGER) == LEDGER_SHA256, "response-free ledger hash drift")
    table = pq.read_table(LEDGER, columns=["cell_id", "region"])
    values = table.to_pydict()
    region = {str(cell): (None if value is None else str(value)) for cell, value in zip(values["cell_id"], values["region"], strict=True)}
    require(len(region) == table.num_rows, "duplicate ledger cell IDs")
    missing = set(cells) - set(region)
    require(not missing, f"retained cells missing from ledger: {len(missing)}")
    counts = Counter(region[cell] for cell in cells)
    require(set(counts) <= set(INNER_REGIONS) | {None}, "unexpected ledger region")
    return region, {"retained_cells": len(cells), "retained_region_null": counts[None], "ledger_rows": table.num_rows, "retained_named_cells": len(cells) - counts[None], **{f"retained_{key}": counts[key] for key in INNER_REGIONS}}


def load_outer_domain() -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    with np.load(OUTER / "domain.npz", allow_pickle=False) as payload:
        require(set(payload.files) >= {"cell_ids", "regions"}, "outer domain fields missing")
        cell_ids = np.asarray(payload["cell_ids"], dtype=str)
        arrays = {key: np.asarray(payload[key]) for key in payload.files}
    require(len(cell_ids) == 144860 and len(set(cell_ids.tolist())) == len(cell_ids), "outer domain identity drift")
    require(sha256_file(OUTER / "domain.npz") == OUTER_DOMAIN_SHA256, "outer domain hash drift")
    return cell_ids, arrays, {"rows": int(len(cell_ids)), "region_counts": {region: int(np.sum(arrays["regions"] == region)) for region in OUTER_REGIONS}, "region_null": int(np.sum(arrays["regions"] == ""))}


def load_outer_responses(targets: list[str], cell_ids: np.ndarray, response_module: Any) -> dict[str, dict[str, np.ndarray]]:
    config = json.loads((ROOT / "config/goal049_seawfb_canonical_response.json").read_text())
    completion_path = ROOT / config["tracked_outputs"]["completion"]
    completion = json.loads(completion_path.read_text())
    canonical_relative = completion["private_outputs"]["canonical_species_cells"]
    canonical_path = ROOT / canonical_relative
    canonical_hash = completion["bindings"]["canonical_species_cells_sha256"]
    require(sha256_file(canonical_path) == canonical_hash, "canonical response hash drift")
    # The accepted completion has equal active and donor counts and therefore
    # intentionally does not serialize a private donor-name list.
    donor_species = None
    present, richness, row_count, species_seen, donor_seen = response_module._read_canonical_rows(
        canonical_path, {cell: index for index, cell in enumerate(cell_ids)}, targets,
        donor_species, 449, 449,
    )
    require(row_count == 5_048_061 and len(species_seen) == 449 and len(donor_seen) == 449, "canonical serialized universe drift")
    result = {}
    for target in targets:
        y = present[target].astype(np.int8, copy=False)
        focal_richness = richness - present[target].astype(np.int32)
        require(np.all(focal_richness >= 0), f"negative focal-excluded richness: {target}")
        result[target] = {"y": y, "richness": focal_richness}
    return result


def metric_values(values: Mapping[str, np.ndarray], labels: np.ndarray) -> dict[str, float | None]:
    out = {arm: auc(labels, values[arm]) for arm in ARMS if arm in values}
    out["ft_conv_ensemble"] = auc(labels, .5 * (values[FT] + values[CONV]))
    out["to_conv_ensemble"] = auc(labels, .5 * (values[TO] + values[CONV]))
    return out


def contrasts(metrics: Mapping[str, float | None]) -> dict[str, float | None]:
    pairs = {
        "ft_minus_to": (FT, TO), "ft_minus_conv": (FT, CONV), "fz_minus_to": (FZ, TO),
        "ft_conv_ensemble_minus_conv": ("ft_conv_ensemble", CONV),
        "ft_conv_ensemble_minus_ft": ("ft_conv_ensemble", FT),
        "to_conv_ensemble_minus_conv": ("to_conv_ensemble", CONV),
        "to_conv_ensemble_minus_to": ("to_conv_ensemble", TO),
        "ft_conv_ensemble_minus_to_conv_ensemble": ("ft_conv_ensemble", "to_conv_ensemble"),
    }
    result = {}
    for name, (left, right) in pairs.items():
        result[name] = None if metrics.get(left) is None or metrics.get(right) is None else float(metrics[left] - metrics[right])
    return result


def summarize_strata(rows: Mapping[str, Mapping[str, Any]], targets: Iterable[str], key: str) -> dict[str, Any]:
    targets = sorted(targets)
    arm_names = tuple(ARMS) + ("ft_conv_ensemble", "to_conv_ensemble")
    per_arm = {}
    for arm in arm_names:
        per_arm[arm] = distribution([rows[target][key]["metrics"].get(arm) for target in targets])
    per_contrast = {name: distribution([rows[target][key]["contrasts"].get(name) for target in targets]) for name in next(iter(rows.values()))[key]["contrasts"]}
    return {"targets": len(targets), "metrics": per_arm, "contrasts": per_contrast}


def target_metric_record(metrics: Mapping[str, float | None], support: Mapping[str, Any], eligible: bool) -> dict[str, Any]:
    return {"eligible": bool(eligible), "support": dict(support), "metrics": {key: None if value is None else float(value) for key, value in metrics.items()}, "contrasts": contrasts(metrics)}


def inner_target(target: str, data: Mapping[str, Any], cells: Mapping[str, tuple[int, int]], region: Mapping[str, str | None]) -> dict[str, Any]:
    # Each record is an OOF row; seeds are averaged in float64 before AUC.
    fold_values: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for fold in FOLDS:
        ids = data["arms"][FT][fold][0]
        y = data["arms"][FT][fold][1]
        region_values = np.asarray([region[str(cell)] for cell in ids], dtype=object)
        values = {arm: data["arms"][arm][fold][2] for arm in (FT, TO, FZ, Q)}
        values[CONV] = data["conventional"][fold][2]
        for arm in ARMS:
            fold_values[arm].append({"ids": ids, "y": y, "score": values[arm], "region": region_values, "fold": fold})

    def one(mask: np.ndarray, minimum: int) -> dict[str, Any]:
        support = {"presence": int(np.sum(mask & (all_y == 1))), "background": int(np.sum(mask & (all_y == 0))), "minimum_each_class": minimum}
        eligible = support["presence"] >= minimum and support["background"] >= minimum
        vals = {arm: auc(all_y[mask], all_scores[arm][mask]) if eligible else None for arm in ARMS}
        vals["ft_conv_ensemble"] = auc(all_y[mask], .5 * (all_scores[FT][mask] + all_scores[CONV][mask])) if eligible else None
        vals["to_conv_ensemble"] = auc(all_y[mask], .5 * (all_scores[TO][mask] + all_scores[CONV][mask])) if eligible else None
        return target_metric_record(vals, support, eligible)

    all_y = np.concatenate([item["y"] for item in fold_values[FT]])
    all_region = np.concatenate([item["region"] for item in fold_values[FT]])
    all_scores = {arm: np.concatenate([item["score"] for item in fold_values[arm]]) for arm in ARMS}
    all_metrics = {}
    for arm in ARMS:
        all_metrics[arm] = auc(all_y, all_scores[arm])
    all_metrics["ft_conv_ensemble"] = auc(all_y, .5 * (all_scores[FT] + all_scores[CONV]))
    all_metrics["to_conv_ensemble"] = auc(all_y, .5 * (all_scores[TO] + all_scores[CONV]))
    pooled = target_metric_record(all_metrics, {"presence": int(np.sum(all_y == 1)), "background": int(np.sum(all_y == 0)), "minimum_each_class": 1}, True)

    regions: dict[str, Any] = {}
    region_fold: dict[str, Any] = {}
    for name in INNER_REGIONS:
        mask = all_region == name
        regions[name] = one(mask, 30)
        region_fold[name] = {}
        for fold, item in enumerate(fold_values[FT]):
            fold_mask = item["region"] == name
            fold_scores = {arm: fold_values[arm][fold]["score"] for arm in ARMS}
            fold_y = item["y"]
            support = {"presence": int(np.sum(fold_mask & (fold_y == 1))), "background": int(np.sum(fold_mask & (fold_y == 0))), "minimum_each_class": 20}
            eligible = support["presence"] >= 20 and support["background"] >= 20
            vals = {arm: auc(fold_y[fold_mask], fold_scores[arm][fold_mask]) if eligible else None for arm in ARMS}
            vals["ft_conv_ensemble"] = auc(fold_y[fold_mask], .5 * (fold_scores[FT][fold_mask] + fold_scores[CONV][fold_mask])) if eligible else None
            vals["to_conv_ensemble"] = auc(fold_y[fold_mask], .5 * (fold_scores[TO][fold_mask] + fold_scores[CONV][fold_mask])) if eligible else None
            region_fold[name][str(fold)] = target_metric_record(vals, support, eligible)

    def macro(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        records = list(records)
        eligible = [record for record in records if record["eligible"]]
        metrics = {arm: finite_mean(record["metrics"].get(arm) for record in eligible) for arm in tuple(ARMS) + ("ft_conv_ensemble", "to_conv_ensemble")}
        return {"eligible_strata": len(eligible), "total_strata": len(records), "metrics": metrics, "contrasts": contrasts(metrics)}

    published_metrics = {arm: mean_fold(data["arms"][arm] if arm in data["arms"] else data["conventional"], 2)[0] for arm in ARMS}
    published_metrics["ft_conv_ensemble"] = finite_mean(auc(data["arms"][FT][fold][1], .5 * (data["arms"][FT][fold][2] + data["conventional"][fold][2])) for fold in FOLDS)
    published_metrics["to_conv_ensemble"] = finite_mean(auc(data["arms"][TO][fold][1], .5 * (data["arms"][TO][fold][2] + data["conventional"][fold][2])) for fold in FOLDS)
    published = target_metric_record(published_metrics, {"folds": len(FOLDS)}, True)
    published["fold_auc"] = {
        arm: mean_fold(data["arms"][arm] if arm in data["arms"] else data["conventional"], 2)[1] for arm in ARMS
    }
    return {
        "published_mean_fold": published,
        "pooled_whole_domain": pooled,
        "region_pooled": {"by_region": regions, "equal_eligible_region_macro": macro(regions.values())},
        "region_fold": {"by_region": region_fold, "equal_eligible_region_fold_macro": macro(item for values in region_fold.values() for item in values.values())},
    }


def mean_fold(data: Mapping[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | tuple[Any, ...]], index: int = 2) -> tuple[float | None, list[float | None]]:
    values = [auc(data[fold][1], data[fold][index]) for fold in FOLDS]
    return (None if any(value is None for value in values) else float(np.mean(values)), values)


def outer_target(target: str, arrays: Mapping[str, np.ndarray], response: Mapping[str, np.ndarray], regions: np.ndarray) -> dict[str, Any]:
    y = response["y"]
    richness = response["richness"]
    values = {FT: arrays[FT], TO: arrays[TO], FZ: arrays[FZ], Q: arrays[Q], CONV: arrays["selected_conventional"]}
    x10 = (y == 1) | ((y == 0) & (richness >= 10))
    whole_values = {arm: values[arm][x10] for arm in values}
    record: dict[str, Any] = {"whole_domain_x10": target_metric_record(metric_values(whole_values, y[x10]), {"presence": int(np.sum(y[x10] == 1)), "background": int(np.sum(y[x10] == 0)), "minimum_each_class": 100}, True), "region_pooled_x10": {}}
    for name in OUTER_REGIONS:
        mask = (regions == name) & x10
        metric = metric_values({arm: values[arm][mask] for arm in values}, y[mask])
        support = {"presence": int(np.sum(y[mask] == 1)), "background": int(np.sum(y[mask] == 0)), "minimum_each_class": {"presence": 30, "background": 100}}
        eligible = support["presence"] >= 30 and support["background"] >= 100
        if not eligible:
            metric = {key: None for key in metric}
        record["region_pooled_x10"][name] = target_metric_record(metric, support, eligible)
    return record


def tail_summary(rows: Mapping[str, Mapping[str, Any]], targets: Iterable[str]) -> dict[str, Any]:
    targets = sorted(targets)
    values = []
    for target in targets:
        item = rows[target]["region_pooled_x10"]["SEH"]
        values.append((target, item))
    output = {"targets_total": len(targets), "contrasts": {}}
    for name in ("ft_minus_to", "ft_minus_conv"):
        vals = [item["contrasts"].get(name) for _, item in values]
        output["contrasts"][name] = distribution(vals)
    def sort_key(item: tuple[str, Mapping[str, Any]]) -> tuple[float, str]:
        value = item[1]["contrasts"].get("ft_minus_to")
        return (float("inf") if value is None else float(value), item[0])
    output["most_negative_ft_minus_to"] = [
        {"target": target, "presence": item["support"]["presence"], "background": item["support"]["background"], "metrics": item["metrics"], "contrasts": item["contrasts"]}
        for target, item in sorted(values, key=sort_key)[:10]
    ]
    return output


def replay_accepted_fixed_ensemble(targets: Iterable[str], outer_closure: Mapping[str, Any], responses: Mapping[str, Mapping[str, np.ndarray]], regions: np.ndarray) -> dict[str, Any]:
    """Recompute every accepted x10 arm before trusting new TO+conv."""
    accepted = json.loads(OUTER_SCORES.read_text())
    comparisons = Counter()
    maximum = Counter()
    accepted_na = Counter()
    score_names = {"target_only_random_init_resmlp": "target_only_random_init_resmlp", "target_plus_q_linear_resmlp": "target_plus_q_linear_resmlp", "multihead_frozen_trunk": "multihead_frozen_trunk", "multihead_full_finetune": "multihead_full_finetune", "selected_conventional": "selected_conventional", "selected_conventional_plus_q": "selected_conventional_plus_q", "fixed_ensemble": "fixed_ensemble"}
    target_list = sorted(targets)
    for target in target_list:
        with np.load(OUTER / outer_closure["predictions"][target], allow_pickle=False) as payload:
            saved = {name: np.asarray(payload[name], dtype=np.float64) for name in score_names}
        y = responses[target]["y"]
        richness = responses[target]["richness"]
        target_rows = [row for row in accepted["targets"] if row["target"] == target]
        require(len(target_rows) == 3, f"accepted score region inventory drift: {target}")
        for row in target_rows:
            region = row["region"]
            mask = (regions == region) & ((y == 1) | ((y == 0) & (richness >= 10)))
            for name in score_names:
                observed = auc(y[mask], saved[name][mask])
                expected = row["metrics"]["x10"][name]["roc_auc"]
                if expected is None:
                    require(observed is None, f"accepted x10 NA drift: {target}/{region}/{name}")
                    accepted_na[name] += 1
                else:
                    require(observed is not None, f"accepted x10 observed NA: {target}/{region}/{name}")
                    comparisons[name] += 1
                    maximum[name] = max(maximum[name], abs(float(observed) - float(expected)))
    require(all(value <= 1e-12 for value in maximum.values()), f"accepted arm replay drift: {dict(maximum)}")
    return {"status": "pass", "targets": len(target_list), "numeric_comparisons": dict(sorted(comparisons.items())), "accepted_na": dict(sorted(accepted_na.items())), "maximum_absolute_error": dict(sorted((key, float(value)) for key, value in maximum.items())), "tolerance": 1e-12}


def verify_outer_bindings(plan: Mapping[str, Any], closure: Mapping[str, Any], acceptance: Mapping[str, Any]) -> None:
    require(plan.get("plan_digest") == "4b179d6cf8134551099c896bbcb30837d2d316cc3e5c70ed30d91c53bf4b63e0", "outer plan digest drift")
    require(closure.get("closure_digest") == "3c6ae7e4c522f5fcf9d90b720af077b813229e6bd14dda7d41fd6251de1a3b9a", "outer closure digest drift")
    require(closure.get("outer_response_rows_read") == 0 and acceptance.get("status") == "complete_verified", "outer acceptance status drift")
    require(acceptance.get("scores_sha256") == OUTER_SCORES_SHA256 and acceptance.get("plan_sha256") == OUTER_PLAN_SHA256 and acceptance.get("closure_sha256") == OUTER_CLOSURE_SHA256, "accepted chain binding drift")
    predictions = closure.get("predictions", {})
    require(len(predictions) == TARGET_N, "outer prediction inventory drift")
    for target, relative in predictions.items():
        path = OUTER / relative
        require(path.is_file() and sha256_file(path) == closure["files"].get(str(Path(relative))), f"outer prediction hash drift: {target}")


def augment_existing_output() -> None:
    """Add compact per-species equal-region contrasts to an existing receipt."""
    output = json.loads(OUTPUT.read_text())
    species = output["per_species"]
    per_species = {}
    contrast_names = None
    for target, item in sorted(species.items()):
        regions = [item["outer"]["region_pooled_x10"][region] for region in OUTER_REGIONS]
        metrics = {arm: finite_mean(row["metrics"].get(arm) for row in regions) for arm in tuple(ARMS) + ("ft_conv_ensemble", "to_conv_ensemble")}
        per_species[target] = {"metrics": metrics, "contrasts": contrasts(metrics), "regions": list(OUTER_REGIONS)}
        contrast_names = tuple(per_species[target]["contrasts"])
    output["outer"]["primary73"]["equal_region_then_species_per_species"] = per_species
    output["outer"]["primary73"]["equal_region_then_species_contrast_distributions"] = {name: distribution(item["contrasts"].get(name) for item in per_species.values()) for name in contrast_names or ()}
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if sha256_file(SUMMARY) != SUMMARY_SHA256 or sha256_file(GOAL051_SUMMARY) != GOAL051_SUMMARY_SHA256:
        raise RuntimeError("accepted summary hash drift")
    require(sha256_file(OUTER_PLAN) == OUTER_PLAN_SHA256 and sha256_file(OUTER_CLOSURE) == OUTER_CLOSURE_SHA256 and sha256_file(OUTER_SCORES) == OUTER_SCORES_SHA256, "outer artifact hash drift")
    summary = json.loads(SUMMARY.read_text())
    accepted = {(str(item["target"]), int(item["fraction"]), str(item["auxiliary"])): item for item in summary["conditions"]}
    targets = sorted(target for target, fraction, auxiliary in accepted if fraction == 100 and auxiliary == "full")
    primary = sorted(target for target in targets if accepted[(target, 100, "full")]["selection_target"])
    require(len(targets) == TARGET_N and len(primary) == PRIMARY_N, "Goal052 target/panel drift")
    outer_plan = json.loads(OUTER_PLAN.read_text())
    outer_closure = json.loads(OUTER_CLOSURE.read_text())
    outer_acceptance = json.loads(OUTER_ACCEPTANCE.read_text())
    verify_outer_bindings(outer_plan, outer_closure, outer_acceptance)
    effort, response_module = load_goal052_helpers()
    cells = effort.load_cell_index()
    region_index, ledger_counts = load_region_index(cells)
    leaf_index, leaf_digest = effort.index_neural_leaves()
    conventional, family_counts, candidate_counts = effort.selected_conventional_index(set(targets))
    inner_rows = {}
    max_inner_baseline_delta = 0.0
    for index, target in enumerate(primary, start=1):
        data = effort.load_target_data(target, leaf_index, conventional[target], cells)
        row = inner_target(target, data, cells, region_index)
        expected = accepted[(target, 100, "full")]
        for arm in ARMS:
            observed = row["published_mean_fold"]["metrics"][arm]
            accepted_value = expected["arm_metrics"][arm]["mean_fold_roc_auc"] if arm != CONV else expected["conventional_metrics"]["mean_fold_roc_auc"]
            max_inner_baseline_delta = max(max_inner_baseline_delta, abs(float(observed) - float(accepted_value)))
        inner_rows[target] = row
        print(f"inner {index}/{len(primary)}", flush=True)

    cell_ids, domain_arrays, outer_domain_counts = load_outer_domain()
    ledger_region = {str(cell): value for cell, value in zip(pq.read_table(LEDGER, columns=["cell_id", "region"])["cell_id"].to_pylist(), pq.read_table(LEDGER, columns=["cell_id", "region"])["region"].to_pylist())}
    outer_regions = np.asarray([ledger_region.get(cell) for cell in cell_ids], dtype=object)
    require(all(value in OUTER_REGIONS for value in outer_regions), "outer domain has null or unknown ledger region")
    require(np.array_equal(outer_regions.astype(str), domain_arrays["regions"].astype(str)), "outer region binding drift")
    # Reconstruct all 157 labels for the accepted-score replay gate; detailed
    # post hoc rows below are restricted to the primary 73 panel.
    outer_response = load_outer_responses(targets, cell_ids, response_module)
    replay = replay_accepted_fixed_ensemble(targets, outer_closure, outer_response, outer_regions)
    outer_rows = {}
    for index, target in enumerate(primary, start=1):
        with np.load(OUTER / outer_closure["predictions"][target], allow_pickle=False) as payload:
            arrays = {key: np.asarray(payload[key], dtype=np.float64) for key in payload.files}
        require(set(OUTER_ARMS) <= set(arrays) and all(value.shape == (len(cell_ids),) and np.isfinite(value).all() for value in arrays.values()), f"outer payload invalid: {target}")
        fixed = .5 * (arrays[FT] + arrays["selected_conventional"])
        require(float(np.max(np.abs(arrays["fixed_ensemble"] - fixed))) <= 1e-15, f"fixed ensemble drift: {target}")
        outer_rows[target] = outer_target(target, arrays, outer_response[target], outer_regions)
        print(f"outer {index}/{len(primary)}", flush=True)

    panel_rows = {"primary73": primary}
    inner_summary = {}
    for panel, names in panel_rows.items():
        inner_summary[panel] = {
            "published_mean_fold": summarize_strata(inner_rows, names, "published_mean_fold"),
            "pooled_whole_domain": summarize_strata(inner_rows, names, "pooled_whole_domain"),
            "region_pooled_equal_eligible_strata_per_target": summarize_strata({target: {"region_pooled": inner_rows[target]["region_pooled"]["equal_eligible_region_macro"]} for target in names}, names, "region_pooled"),
            "region_fold_equal_eligible_strata_per_target": summarize_strata({target: {"region_fold": inner_rows[target]["region_fold"]["equal_eligible_region_fold_macro"]} for target in names}, names, "region_fold"),
        }
    outer_summary = {}
    for panel, names in panel_rows.items():
        outer_summary[panel] = {
            "whole_domain_x10": summarize_strata(outer_rows, names, "whole_domain_x10"),
            "region_pooled_x10_by_region": {region: summarize_strata({target: {"region": outer_rows[target]["region_pooled_x10"][region]} for target in names}, names, "region") for region in OUTER_REGIONS},
        }
        region_summaries = outer_summary[panel]["region_pooled_x10_by_region"]
        outer_summary[panel]["equal_region_then_species"] = {
            "regions": list(OUTER_REGIONS),
            "metrics": {arm: finite_mean(region_summaries[region]["metrics"][arm]["mean"] for region in OUTER_REGIONS) for arm in tuple(ARMS) + ("ft_conv_ensemble", "to_conv_ensemble")},
            "contrasts": {name: finite_mean(region_summaries[region]["contrasts"][name]["mean"] for region in OUTER_REGIONS) for name in region_summaries[OUTER_REGIONS[0]]["contrasts"]},
        }
    require(max_inner_baseline_delta <= 2e-10, f"published mean-fold replay drift: {max_inner_baseline_delta}")
    require(all(value <= replay["tolerance"] for value in replay["maximum_absolute_error"].values()), "accepted arm replay gate failed")
    output = {
        "schema_version": "goal052-extent-review-v1",
        "status": "posthoc_aggregate_only",
        "scope": {"outer_rows_read": 5_048_061, "canonical_membership_rows_reconstructed": 5_048_061, "response_state": "re-reading already-opened accepted outer responses; no new unsealing", "fitting_performed": False, "target_inventory_verified": TARGET_N, "target_count_evaluated": PRIMARY_N, "primary_count": PRIMARY_N, "inner_regions": list(INNER_REGIONS), "outer_regions": list(OUTER_REGIONS), "outer_region_labels": {"NCP": "Naracoorte Coastal Plain", "SEH": "South Eastern Highlands", "NNC": "NSW North Coast"}, "seed_average": "float64 mean per fold before AUC", "region_pooled_minimum_each_class": 30, "region_fold_minimum_each_class": 20, "aggregation": "equal eligible strata per target, then equal target; outer region summaries exclude NULL explicitly"},
        "inputs": {"goal052_summary_sha256": sha256_file(SUMMARY), "goal051_summary_sha256": sha256_file(GOAL051_SUMMARY), "goal052_leaf_digest": leaf_digest, "goal051_family_counts": dict(sorted(family_counts.items())), "goal051_candidate_counts": dict(sorted(candidate_counts.items())), "cell_region_ledger": {"path": str(LEDGER.relative_to(ROOT)), "sha256": sha256_file(LEDGER), **ledger_counts}, "outer_plan_sha256": sha256_file(OUTER_PLAN), "outer_closure_sha256": sha256_file(OUTER_CLOSURE), "outer_scores_sha256": sha256_file(OUTER_SCORES), "outer_acceptance_sha256": sha256_file(OUTER_ACCEPTANCE), "outer_domain": outer_domain_counts},
        "inner": inner_summary,
        "outer": outer_summary,
        "seh_support_tail_primary73": tail_summary(outer_rows, primary),
        "per_species": {target: {"inner": inner_rows[target], "outer": outer_rows[target]} for target in primary},
        "checks": {"published_mean_fold_max_abs_delta": max_inner_baseline_delta, "published_mean_fold_matches": True, "accepted_arm_replay": replay},
        "interpretive_limits": ["These region and extent summaries are post hoc descriptive re-aggregations of saved predictions.", "Region contrasts do not identify a geographic transfer penalty because composition, support, training size, and fitted-fold/retained-full models differ.", "Similar ensemble performance would not establish that pretraining contributes no information.", "Presence versus effort-supported unrecorded background is not occupancy or verified absence; species and regions are not iid replicates."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    primary_inner = output["inner"]["primary73"]
    inner_primary = output["inner"]["primary73"]
    outer_primary = output["outer"]["primary73"]["equal_region_then_species"]
    def row(label: str, item: Mapping[str, Any]) -> str:
        m, c = item["metrics"], item["contrasts"]
        def val(x: Any) -> str:
            return "NA" if x is None else f"{float(x):.6f}"
        return f"| {label} | {val(m[FT]['mean'] if isinstance(m[FT], dict) else m[FT])} | {val(m[TO]['mean'] if isinstance(m[TO], dict) else m[TO])} | {val(c['ft_minus_to']['mean'] if isinstance(c['ft_minus_to'], dict) else c['ft_minus_to'])} | {val(c['ft_minus_conv']['mean'] if isinstance(c['ft_minus_conv'], dict) else c['ft_minus_conv'])} | {val(c['ft_conv_ensemble_minus_conv']['mean'] if isinstance(c['ft_conv_ensemble_minus_conv'], dict) else c['ft_conv_ensemble_minus_conv'])} | {val(c['to_conv_ensemble_minus_conv']['mean'] if isinstance(c['to_conv_ensemble_minus_conv'], dict) else c['to_conv_ensemble_minus_conv'])} |"
    region_pooled_eligible = sum(inner_rows[target]["region_pooled"]["equal_eligible_region_macro"]["eligible_strata"] for target in primary)
    region_fold_eligible = sum(inner_rows[target]["region_fold"]["equal_eligible_region_fold_macro"]["eligible_strata"] for target in primary)
    report_text = "\n".join([
        "# Goal052 post hoc bird extent and ensemble review", "",
        "This dated supplement reproduces aggregate-only extent and ensemble checks from the accepted Goal052 saved predictions. It does not refit or tune models. Inner OOF scores retain the published mean-fold values and add pooled whole-domain, named-region pooled, and named-region-by-fold summaries. Eligible strata are averaged within target and targets are then equally weighted.", "",
        f"The response-free ledger contains {ledger_counts['retained_cells']:,} retained cells: {ledger_counts['retained_region_null']:,} have NULL region because they are the domain complement and are included only in whole-domain summaries. The outer domain contains {outer_domain_counts['rows']:,} cells, all bound to NCP (Naracoorte Coastal Plain), SEH (South Eastern Highlands), and NNC (NSW North Coast); no NULL region occurs in the outer domain. Across the primary 73, the named-region pooled calculation used {region_pooled_eligible:,} eligible target×region strata and the named-region×fold calculation used {region_fold_eligible:,} eligible target×region×fold strata; each target was then weighted equally. Outer summaries use the accepted X10 mask: all presences plus focal-excluded richness at least 10.", "",
        "## Primary 73 comparison means", "", "| Aggregation | FT AUC | TO AUC | FT−TO | FT−conv | FT+conv−conv | TO+conv−conv |", "|---|---:|---:|---:|---:|---:|---:|",
        row("Published mean-fold", inner_primary["published_mean_fold"]), row("Pooled whole-domain", inner_primary["pooled_whole_domain"]), row("Named-region pooled", inner_primary["region_pooled_equal_eligible_strata_per_target"]), row("Named-region×fold", inner_primary["region_fold_equal_eligible_strata_per_target"]), row("Outer equal-region then species", outer_primary), "",
        f"The accepted X10 replay gate compared {sum(replay['numeric_comparisons'].values()):,} saved-score AUCs across all verified 157-target region records and every saved arm; the largest observed absolute error was {max(replay['maximum_absolute_error'].values()):.3g} (tolerance {replay['tolerance']:.3g}). The exploratory target-only/conventional ensemble uses unchanged saved predictions. The SEH tail is retained for all 73 primary species, with undefined scores kept as NA rather than excluded silently. These extent summaries do not identify a geographic penalty, and ensemble similarity does not establish that pretraining contributes no information.", ""
    ])
    REPORT.write_text(report_text)
    augment_existing_output()
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)), "report": str(REPORT.relative_to(ROOT)), "published_mean_fold_matches": output["checks"]["published_mean_fold_matches"], "max_abs_delta": max_inner_baseline_delta, "outer_replay_max_abs_error": replay["maximum_absolute_error"]}, indent=2))


if __name__ == "__main__":
    if "--augment-existing" in sys.argv:
        augment_existing_output()
    else:
        main()
