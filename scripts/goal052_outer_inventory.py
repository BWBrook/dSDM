#!/usr/bin/env python3
"""Build the bounded Goal052 bird outer-refit preparation inventory.

This script reads only accepted aggregate summaries, frozen panel metadata,
the frozen Goal052 configuration, and pretraining JSON receipts.  It records
prospective refit metadata; it never reads outer rows, model payloads,
Parquet, memberships, predictions, or response outcomes.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GOAL052_SUMMARY = ROOT / "evidence/seawfb_dsdm/goal052/summary.json"
GOAL051_SUMMARY = ROOT / "evidence/seawfb_conventional/goal051/summary.json"
PANEL_SUMMARY = ROOT / "evidence/seawfb_canonical_response/goal049/panel_summary.json"
GOAL052_CONFIG = ROOT / "config/goal052_seawfb_dsdm.json"
PRETRAINING_DIR = ROOT / "data/processed/dsdm/goal052-seawfb-dsdm-experiment/pretraining"
OUTPUT = ROOT / "evidence/seawfb_dsdm/goal052/outer-inventory-20260929.json"

EXPECTED_GOAL052_SUMMARY_SHA256 = "ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3"
EXPECTED_GOAL051_SUMMARY_SHA256 = "9c1bf1ff8884fae35fe7ebe6f8d19e2aae46ab7eedee252b398c0c74705dd2d8"
EXPECTED_GOAL052_CONFIG_SHA256 = "04b667168944b39ced1044da8f381553c4024e31cca1f5590f2fbc693e521f9a"
EXPECTED_ARMS = (
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"expected_object:{path}")
    return value


def rounded_median(values: list[int]) -> int:
    value = statistics.median(values)
    require(float(value).is_integer(), f"non_integer_median:{value}")
    return int(value)


def finite_threshold(value: Any, label: str) -> float:
    result = float(value)
    require(math.isfinite(result), f"non_finite_threshold:{label}")
    return result


def neural_inventory(summary: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    conditions = [
        condition
        for condition in summary["conditions"]
        if condition["fraction"] == 100 and condition["auxiliary"] == "full"
    ]
    require(len(conditions) == 157, "goal052_target100_full_count")
    records: list[dict[str, Any]] = []
    for condition in sorted(conditions, key=lambda item: item["target"]):
        target = condition["target"]
        arms = condition["arm_metrics"]
        record_arms: dict[str, Any] = {}
        for arm in EXPECTED_ARMS:
            auxiliary = "none" if arm == "target_only_random_init_resmlp" else "full"
            key = f"{target}|100|{auxiliary}|{arm}"
            epoch_record = summary["selected_epochs"].get(key)
            require(isinstance(epoch_record, dict), f"missing_neural_epoch:{key}")
            epoch = epoch_record.get("median_rounded")
            require(isinstance(epoch, int) and not isinstance(epoch, bool), f"epoch_type:{key}")
            require(1 <= epoch <= 300, f"epoch_range:{key}")
            values = epoch_record["selected_epochs"]
            require(len(values) == 25 and all(type(v) is int and 1 <= v <= 300 for v in values), f"selected_epochs:{key}")
            require(epoch == rounded_median(values), f"stored_median_drift:{key}")
            require(arm in arms, f"missing_neural_arm:{target}:{arm}")
            threshold = finite_threshold(arms[arm]["threshold"], f"{target}:{arm}")
            record_arms[arm] = {
                "auxiliary": auxiliary,
                "median_rounded_epoch": epoch,
                "oof_threshold": threshold,
            }
        records.append({"target": target, "arms": record_arms})
    require(len(records) == len({item["target"] for item in records}) == 157, "neural_target_uniqueness")
    return records, dict(Counter(arm for record in records for arm in record["arms"]))


def conventional_inventory(summary: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoints = [endpoint for endpoint in summary["endpoints"] if endpoint["target_fraction"] == 100]
    require(len(endpoints) == 157, "goal051_target100_count")
    records: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    ordinary_fit_counts: Counter[str] = Counter()
    q_full_fit_counts: Counter[str] = Counter()
    ordinary_total = 0
    q_full_total = 0
    for endpoint in sorted(endpoints, key=lambda item: item["target"]):
        family = endpoint["best_non_null_family"]
        selected = endpoint["families"][family]["selected"]
        q_selected = endpoint["q_linear"]["full"]
        require(q_selected["family"] == family, f"q_family_not_reused:{endpoint['target']}")
        require(q_selected["candidate_id"] == selected["candidate_id"], f"q_candidate_not_reused:{endpoint['target']}")
        ordinary_threshold = finite_threshold(selected["metrics"]["threshold"], f"ordinary:{endpoint['target']}")
        q_threshold = finite_threshold(q_selected["metrics"]["threshold"], f"q_full:{endpoint['target']}")
        ordinary_seeds = list(selected["seed_labels"])
        q_seeds = list(q_selected["seed_labels"])
        require(ordinary_seeds == q_seeds, f"seed_labels_not_reused:{endpoint['target']}")
        family_counts[family] += 1
        ordinary_fit_counts[family] += len(ordinary_seeds)
        q_full_fit_counts[family] += len(q_seeds)
        ordinary_total += len(ordinary_seeds)
        q_full_total += len(q_seeds)
        records.append(
            {
                "target": endpoint["target"],
                "ordinary": {
                    "family": family,
                    "candidate_id": selected["candidate_id"],
                    "seed_labels": ordinary_seeds,
                    "oof_threshold": ordinary_threshold,
                    "best_epoch_range": selected["best_epoch_range"],
                },
                "q_full": {
                    "family": q_selected["family"],
                    "candidate_id": q_selected["candidate_id"],
                    "seed_labels": q_seeds,
                    "oof_threshold": q_threshold,
                    "best_epoch_range": q_selected["best_epoch_range"],
                },
            }
        )
    require(family_counts == Counter({"random_forest": 51, "hist_gradient_boosting": 66, "shallow_ann": 40}), "selected_family_counts")
    require(ordinary_total + q_full_total == 1042, "prospective_conventional_fit_count")
    return records, {
        "selected_family_counts": dict(sorted(family_counts.items())),
        "prospective_full_full_seed_fits": {
            "ordinary": dict(sorted(ordinary_fit_counts.items())),
            "q_full": dict(sorted(q_full_fit_counts.items())),
            "total": ordinary_total + q_full_total,
            "excludes_ann_epoch_recovery": True,
        },
    }


def pretraining_inventory(goal052_identity: dict[str, Any]) -> dict[str, Any]:
    paths = sorted(PRETRAINING_DIR.glob("*.json"))
    selected: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        receipt = read_json(path)
        key = receipt.get("key", {})
        if key.get("architecture") == "seawfb_scale" and key.get("auxiliary") == "full":
            selected.append((path, receipt))
    require(len(selected) == 250, "pretraining_seawfb_scale_full_count")
    expected_identity = goal052_identity
    rows: list[dict[str, Any]] = []
    by_block: defaultdict[int, list[int]] = defaultdict(list)
    by_block_seed: defaultdict[int, defaultdict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    keys: set[tuple[int, int, str]] = set()
    for path, receipt in selected:
        key = receipt["key"]
        require(key.get("identity") == expected_identity, f"pretraining_identity:{path.name}")
        block, fold, seed = key.get("block"), key.get("fold"), key.get("seed_label")
        require(isinstance(block, int) and 0 <= block < 10, f"pretraining_block:{path.name}")
        require(isinstance(fold, int) and 0 <= fold < 5, f"pretraining_fold:{path.name}")
        require(seed in {f"seed0{i}" for i in range(5)}, f"pretraining_seed:{path.name}")
        identity = (block, fold, seed)
        require(identity not in keys, f"duplicate_pretraining_identity:{identity}")
        keys.add(identity)
        fit = receipt.get("fit", {})
        epoch = fit.get("selected_epoch")
        require(isinstance(epoch, int) and not isinstance(epoch, bool) and 1 <= epoch <= 300, f"pretraining_epoch:{path.name}")
        receipt_hash = sha256_file(path)
        rows.append({
            "block": block,
            "fold": fold,
            "seed_label": seed,
            "selected_epoch": epoch,
            "receipt_sha256": receipt_hash,
        })
        by_block[block].append(epoch)
        by_block_seed[block][seed].append(epoch)
    require(keys == {(block, fold, f"seed0{seed}") for block in range(10) for fold in range(5) for seed in range(5)}, "pretraining_complete_grid")
    rows.sort(key=lambda row: (row["block"], row["fold"], row["seed_label"]))
    block_summary = {}
    for block in range(10):
        block_summary[f"block{block:02d}"] = {
            "pooled25_median_selected_epoch": rounded_median(by_block[block]),
            "seed5_median_selected_epochs": {
                seed: rounded_median(by_block_seed[block][seed])
                for seed in sorted(by_block_seed[block])
            },
        }
    inventory_digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "receipt_count": len(rows),
        "grid": {"blocks": 10, "folds": 5, "seeds": 5, "complete_unique": True},
        "selected_architecture": "seawfb_scale",
        "auxiliary": "full",
        "epoch_range_check": {"minimum": 1, "maximum": 300, "all_valid": True},
        "prospective_epoch_choices": block_summary,
        "receipt_inventory_sha256": inventory_digest,
        "receipt_provenance": rows,
    }


def build_inventory() -> dict[str, Any]:
    source_hashes = {
        "goal052_summary": sha256_file(GOAL052_SUMMARY),
        "goal051_summary": sha256_file(GOAL051_SUMMARY),
        "panel_summary": sha256_file(PANEL_SUMMARY),
        "goal052_config": sha256_file(GOAL052_CONFIG),
    }
    require(source_hashes["goal052_summary"] == EXPECTED_GOAL052_SUMMARY_SHA256, "goal052_summary_hash")
    require(source_hashes["goal051_summary"] == EXPECTED_GOAL051_SUMMARY_SHA256, "goal051_summary_hash")
    require(source_hashes["goal052_config"] == EXPECTED_GOAL052_CONFIG_SHA256, "goal052_config_hash")
    goal052 = read_json(GOAL052_SUMMARY)
    goal051 = read_json(GOAL051_SUMMARY)
    panel = read_json(PANEL_SUMMARY)
    config = read_json(GOAL052_CONFIG)
    require(goal052.get("outer_response_rows_read") == 0, "goal052_outer_rows_read")
    require(goal051.get("outer_response_rows_read") == 0 and goal051.get("outer_predictor_rows_used") == 0, "goal051_outer_rows_read")
    require(goal052.get("selected_architecture") == "seawfb_scale", "selected_architecture")
    require(config["scope"]["primary_targets"] == 73 and config["scope"]["full_only_targets"] == 84, "target_panel_counts")
    require(config["architectures"]["constants"]["max_epochs"] == 300, "max_epoch_contract")
    require(panel["primary_common"]["count"] == 73, "primary_panel_count")
    require({item: panel["secondary_region_specific"][item]["count"] for item in ("NCP", "SEH", "NNC")} == {"NCP": 88, "SEH": 122, "NNC": 134}, "regional_panel_counts")
    require(set(panel["regions"]) == {"NCP", "SEH", "NNC"}, "regional_panel_identity")
    neural, neural_counts = neural_inventory(goal052)
    conventional, conventional_summary = conventional_inventory(goal051)
    targets = {row["target"] for row in neural}
    require(len({row["target"] for row in conventional}) == len(conventional) == 157, "conventional_target_uniqueness")
    require(targets == {row["target"] for row in conventional}, "target_inventory_mismatch")
    primary = set(panel["primary_common"]["species"])
    require(len(primary) == 73, "primary_panel_membership_count")
    require(primary == {row["target"] for row in goal052["conditions"] if row["selection_target"]}, "primary_panel_membership_drift")
    regional = {region: set(panel["secondary_region_specific"][region]["species"]) for region in ("NCP", "SEH", "NNC")}
    require(all(len(regional[r]) == panel["secondary_region_specific"][r]["count"] and primary <= regional[r] for r in regional), "regional_panel_membership_drift")
    require(set.union(*regional.values()) == targets, "regional_union_target_mismatch")
    require(goal051["identity"] == goal052["identity"]["goal051_identity"], "accepted_identity_mismatch")
    pretraining = pretraining_inventory(goal052["identity"])
    missing_ann = [row["target"] for row in conventional if row["ordinary"]["family"] == "shallow_ann"]
    require(len(missing_ann) == 40, "ann_missing_endpoint_count")
    script_hash = sha256_file(Path(__file__).resolve())
    return {
        "schema_version": "goal052-outer-inventory-v1",
        "status": "proposal_inventory_not_execution",
        "execution_permit": False,
        "outer_response_rows_read": 0,
        "scope": {
            "target100_auxiliary_full_endpoints": len(neural),
            "primary_panel": 73,
            "full_only_targets": 84,
            "regions": {"NCP": 88, "SEH": 122, "NNC": 134},
        },
        "inputs": {"sha256": source_hashes, "accepted_goal052_identity": goal052["identity"]},
        "neural_target100_full": {"arm_endpoint_counts": neural_counts, "records": neural},
        "conventional_target100": {"summary": conventional_summary, "records": conventional},
        "pretraining": pretraining,
        "prospective_full_full_workload": {
            "pretraining_new_trunks": 50,
            "q_surfaces": 10,
            "neural_target_full_refit_fits": 157 * 4 * 5,
            "conventional_selected_seed_fits": 1042,
            "total_excluding_retries_and_ann_epoch_recovery": 50 + 10 + 157 * 4 * 5 + 1042,
        },
        "missing_recipe_items": [
            {
                "item": "exact_selected_shallow_ann_epochs",
                "ordinary_target_conditions_missing": len(missing_ann),
                "q_full_target_conditions_missing": len(missing_ann),
                "total_target_conditions_missing": 2 * len(missing_ann),
                "targets": missing_ann,
                "reason": "accepted public summary retains best_epoch_range only; fit_records were not retained",
                "handling": "flag missing; do not infer an epoch from range endpoints",
            }
        ],
        "limitations": [
            "Preparation metadata only; this artifact is not a launch permit.",
            "No .pt, Parquet, raw memberships, outer outcomes, predictions, or fits were read.",
            "The 250 inner pretraining receipts are not retained-full outer refits.",
            "Outer predictor hashing, synthetic separation checks, implementation, and runtime qualification remain outstanding.",
        ],
        "script_sha256": script_hash,
    }


def main() -> None:
    inventory = build_inventory()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": inventory["status"],
        "output": str(OUTPUT.relative_to(ROOT)),
        "neural_refit_fits": inventory["prospective_full_full_workload"]["neural_target_full_refit_fits"],
        "conventional_selected_seed_fits": inventory["prospective_full_full_workload"]["conventional_selected_seed_fits"],
        "pretraining_receipts": inventory["pretraining"]["receipt_count"],
        "outer_response_rows_read": inventory["outer_response_rows_read"],
        "script_sha256": inventory["script_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
