#!/usr/bin/env python3
"""Independently verify Goal052 outer richness arithmetic from JSON artifacts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any, Mapping, Sequence


TOLERANCE = 1e-12
REGIONS = ("NCP", "SEH", "NNC")
BINS = ("10_24", "25_99", "100_plus")
INNER_CONTRASTS = (
    "multihead_full_finetune_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_target_plus_q_linear_resmlp",
    "multihead_full_finetune_minus_goal051_selected_conventional",
    "multihead_full_finetune_minus_goal051_q_augmented_conventional",
    "multihead_frozen_trunk_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_multihead_frozen_trunk",
)
EXPECTED_CONTRASTS = INNER_CONTRASTS + (
    "fixed_ensemble_minus_multihead_full_finetune",
    "fixed_ensemble_minus_selected_conventional",
)


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def close(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    return finite(left) and finite(right) and abs(float(left) - float(right)) <= TOLERANCE


def expected_stats(values: Mapping[str, Any], members: Sequence[str]) -> dict[str, Any]:
    ordered = list(members)
    evaluated = [target for target in ordered if finite(values.get(target))]
    missing = [target for target in ordered if target not in evaluated]
    vector = [float(values[target]) for target in evaluated]
    denominator = len(vector)
    positive = sum(value > 0 for value in vector)
    mean = sum(vector) / denominator if denominator else None
    median = statistics.median(vector) if denominator else None
    label = None if not denominator else (
        "consistent positive direction" if mean > 0 and positive > denominator / 2
        else "consistent nonpositive direction" if mean <= 0 and positive <= denominator / 2
        else "mixed direction"
    )
    return {
        "members": ordered,
        "evaluated_members": evaluated,
        "missing_members": missing,
        "values": {target: (float(values[target]) if target in evaluated else None) for target in ordered},
        "mean": mean,
        "median": median,
        "positive_count": positive,
        "denominator": denominator,
        "denom": denominator,
        "positive_fraction": positive / denominator if denominator else None,
        "label": label,
    }


class Checker:
    def __init__(self, scores: Mapping[str, Any], plan: Mapping[str, Any], inner: Mapping[str, Any]):
        self.scores = scores
        self.aggregate = scores.get("aggregate", {})
        self.plan = plan
        self.inner = inner
        self.failures: list[str] = []
        self.comparisons = 0
        self.rows: dict[tuple[str, str], Mapping[str, Any]] = {}
        self.contrasts: list[str] = list(self.aggregate.get("contrasts", []))
        self.richness = self.aggregate.get("richness", {})
        self.headline = self.aggregate.get("headline_decomposition", {})

    def fail(self, invariant: str) -> None:
        self.failures.append(invariant)

    def require(self, condition: bool, invariant: str) -> None:
        if not condition:
            self.fail(invariant)

    def compare(self, actual: Any, expected: Any, invariant: str) -> None:
        self.comparisons += 1
        if isinstance(expected, Mapping):
            self.require(isinstance(actual, Mapping), invariant + ".type")
            if not isinstance(actual, Mapping):
                return
            for key in expected:
                self.compare(actual.get(key), expected[key], invariant + "." + str(key))
            self.require(set(actual) == set(expected), invariant + ".keys")
        elif isinstance(expected, list):
            self.require(actual == expected, invariant)
        elif expected is None or isinstance(expected, bool):
            self.require(actual == expected, invariant)
        elif isinstance(expected, (int, float)):
            self.require(close(actual, expected), invariant)
        else:
            self.require(actual == expected, invariant)

    def row_value(self, region: str, target: str, label: str, contrast: str) -> Any:
        row = self.rows.get((region, target), {})
        return (row.get("richness", {}).get("background_strata", {}).get(label, {})
                .get("contrasts", {}).get(contrast))

    def high_value(self, region: str, target: str, contrast: str) -> Any:
        return (self.rows.get((region, target), {}).get("richness", {})
                .get("high_recording_richness_subset") or {}).get("contrasts", {}).get(contrast)

    def check_stats(self, actual: Any, values: Mapping[str, Any], members: Sequence[str], invariant: str) -> None:
        self.compare(actual, expected_stats(values, members), invariant)

    def load_inventory(self) -> tuple[list[str], dict[str, list[str]]]:
        panels = self.plan.get("panels", {})
        primary = list(panels.get("primary", []))
        regional = {region: list(panels.get("regional", {}).get(region, [])) for region in REGIONS
                    if region in panels.get("regional", {})}
        self.require(bool(primary), "plan.primary_panel_missing")
        self.require(set(regional) == set(REGIONS), "plan.regional_panel_inventory")
        expected = {(region, target) for region, targets in regional.items() for target in targets}
        for row in self.scores.get("targets", []):
            key = (row.get("region"), row.get("target"))
            self.require(key in expected, "target_region_unexpected:" + repr(key))
            self.require(key not in self.rows, "target_region_duplicate:" + repr(key))
            self.rows[key] = row
        self.require(set(self.rows) == expected, "target_region_inventory")
        return primary, regional

    def check_richness_panel(self, summary: Mapping[str, Any], region: str,
                             members: list[str], scope: str) -> None:
        bins = summary.get("bins", {})
        contrasts = self.contrasts
        for label in BINS:
            actual_bin = bins.get(label, {})
            for contrast in contrasts:
                values = {target: self.row_value(region, target, label, contrast) for target in members}
                common_members = [target for target in members if all(
                    self.row_value(region, target, other, contrast) is not None for other in BINS
                )]
                self.check_stats(actual_bin.get("all_available", {}).get(contrast), values, members,
                                 f"{scope}.{region}.{label}.all_available.{contrast}")
                common_expected = expected_stats({target: values[target] for target in common_members}, common_members)
                common_expected["panel_members"] = list(members)
                self.compare(actual_bin.get("common_support", {}).get(contrast), common_expected,
                             f"{scope}.{region}.{label}.common_support.{contrast}")

        actual_high = summary.get("high_recording_richness_subset", {})
        for contrast in contrasts:
            values = {target: self.high_value(region, target, contrast) for target in members}
            expected = expected_stats(values, [target for target in members if values[target] is not None])
            expected["panel_members"] = list(members)
            expected["nonevaluable_panel_members"] = [target for target in members if values[target] is None]
            self.compare(actual_high.get("contrasts", {}).get(contrast), expected,
                         f"{scope}.{region}.high_recording_richness_subset.{contrast}")

    def check_macro_richness(self, primary: list[str], regional: dict[str, list[str]]) -> None:
        macro = self.richness.get("supplementary_three_region_macro", {})
        contrasts = self.contrasts
        regions = list(regional)
        for label in BINS:
            actual_bin = macro.get("bins", {}).get(label, {})
            for contrast in contrasts:
                values: dict[str, Any] = {}
                for target in primary:
                    regional_values = [self.row_value(region, target, label, contrast) for region in regions]
                    values[target] = (sum(regional_values) / len(regional_values)
                                      if regional_values and all(value is not None for value in regional_values) else None)
                item = expected_stats(values, primary)
                item["equal_region_macro_mean"] = item["mean"]
                self.compare(actual_bin.get("contrasts", {}).get(contrast), item,
                             f"macro.{label}.{contrast}")
                common = [target for target in primary if all(
                    self.row_value(region, target, other, contrast) is not None
                    for region in regions for other in BINS
                )]
                common_item = expected_stats({target: values[target] for target in common}, common)
                common_item["panel_members"] = list(primary)
                self.compare(actual_bin.get("three_bin_common_support", {}).get(contrast), common_item,
                             f"macro.{label}.three_bin_common_support.{contrast}")

        actual_high = macro.get("high_recording_richness_subset", {})
        for contrast in contrasts:
            values = {}
            for target in primary:
                per_region = [self.high_value(region, target, contrast) for region in regions]
                values[target] = (sum(per_region) / len(per_region)
                                  if per_region and all(value is not None for value in per_region) else None)
            evaluated = [target for target in primary if values[target] is not None]
            item = expected_stats({target: values[target] for target in evaluated}, evaluated)
            item["panel_members"] = list(primary)
            item["nonevaluable_panel_members"] = [target for target in primary if target not in evaluated]
            self.compare(actual_high.get("contrasts", {}).get(contrast), item,
                         f"macro.high_recording_richness_subset.{contrast}")

    def check_headline_decomposition(self, primary: list[str], regional: dict[str, list[str]]) -> None:
        headline = self.headline
        contrasts = self.contrasts
        for scope, panel_map in (("primary_by_region", {r: primary for r in regional}), ("regional", regional)):
            for region, members in panel_map.items():
                actual = headline.get(scope, {}).get(region, {})
                for contrast in contrasts:
                    per_target = {}
                    for target in members:
                        item = (self.rows[(region, target)].get("richness", {})
                                .get("headline_decomposition", {}).get("contrasts", {}).get(contrast))
                        self.require(isinstance(item, Mapping), f"headline.target_missing:{scope}:{region}:{target}:{contrast}")
                        if not isinstance(item, Mapping):
                            continue
                        contributions = item.get("weighted_bin_contributions", {})
                        expected_sum = sum(float(contributions.get(label, math.nan)) for label in BINS)
                        row_contrast = self.rows[(region, target)].get("x10", {}).get("contrasts", {}).get(contrast)
                        self.require(finite(expected_sum) and close(expected_sum, row_contrast),
                                     f"headline.target_identity:{scope}:{region}:{target}:{contrast}")
                        per_target[target] = contributions
                    means = {label: sum(float(per_target[target][label]) for target in members) / len(members)
                             for label in BINS}
                    total = sum(means.values())
                    actual_item = actual.get("contrasts", {}).get(contrast, {})
                    expected = {"mean_weighted_bin_contributions": means, "sum": total,
                                "absolute_error": abs(total - sum(
                                    float(self.rows[(region, target)].get("x10", {}).get("contrasts", {}).get(contrast))
                                    for target in members) / len(members))}
                    self.compare(actual.get("targets"), list(members), f"headline.{scope}.{region}.targets")
                    self.compare(actual.get("target_count"), len(members), f"headline.{scope}.{region}.target_count")
                    self.compare(actual_item, expected, f"headline.{scope}.{region}.{contrast}")

    def check_attenuation(self, primary: list[str], regional: dict[str, list[str]]) -> None:
        inner: dict[str, Mapping[str, Any]] = {}
        for item in self.inner.get("conditions", []):
            if item.get("fraction") == 100 and item.get("auxiliary") == "full":
                self.require(item.get("target") not in inner, "inner.duplicate_target")
                inner[item["target"]] = {**item.get("primary_contrasts", {}), **item.get("mechanistic_contrasts", {})}
        names = list(INNER_CONTRASTS)
        self.require(self.contrasts == list(EXPECTED_CONTRASTS), "attenuation.contrast_inventory")
        self.require(bool(inner), "attenuation.inner_conditions_missing")
        stored = self.aggregate.get("matched_inner_attenuation", {})
        panels = [("primary_by_region", {r: primary for r in regional}), ("regional", regional)]
        for scope, panel_map in panels:
            for region, members in panel_map.items():
                actual = stored.get(scope, {}).get(region, {})
                for name in names:
                    inner_values = {target: float(inner[target][name]["delta_mean_fold_roc_auc"]) for target in members}
                    inner_mean = sum(inner_values.values()) / len(members) if members else None
                    outer = (self.aggregate.get(scope, {}).get(region, {})
                             .get("contrasts", {}).get(name, {}))
                    expected = {"targets": list(members), "target_count": len(members),
                                "inner_mean_difference": inner_mean,
                                "outer_mean_difference": outer.get("mean"),
                                "outer_minus_inner": None if inner_mean is None else outer.get("mean") - inner_mean,
                                "inner_target_differences": inner_values}
                    self.compare(actual.get(name), expected, f"attenuation.{scope}.{region}.{name}")
        common_actual = stored.get("common_equal_region_macro", {})
        common_outer = self.aggregate.get("common", {})
        for name in names:
            inner_values = {target: float(inner[target][name]["delta_mean_fold_roc_auc"]) for target in primary}
            inner_mean = sum(inner_values.values()) / len(primary) if primary else None
            outer = common_outer.get("contrasts", {}).get(name, {})
            expected = {"targets": list(primary), "target_count": len(primary),
                        "inner_mean_difference": inner_mean, "outer_mean_difference": outer.get("mean"),
                        "outer_minus_inner": None if inner_mean is None else outer.get("mean") - inner_mean,
                        "inner_target_differences": inner_values}
            self.compare(common_actual.get(name), expected, f"attenuation.common_equal_region_macro.{name}")

    def run(self) -> dict[str, Any]:
        self.require(self.scores.get("schema_version") == "goal052-outer-scores-v1", "scores.schema")
        self.require(self.contrasts == list(EXPECTED_CONTRASTS), "scores.contrast_inventory")
        self.require(isinstance(self.aggregate, Mapping), "scores.aggregate_missing")
        primary, regional = self.load_inventory()
        richness = self.richness
        for region, members in regional.items():
            self.check_richness_panel(richness.get("regional", {}).get(region, {}), region, members, "regional")
            self.check_richness_panel(richness.get("primary_by_region", {}).get(region, {}), region, primary, "primary_by_region")
        self.check_macro_richness(primary, regional)
        self.check_headline_decomposition(primary, regional)
        self.check_attenuation(primary, regional)
        return {"schema_version": "goal052-outer-richness-result-check-v1", "status": "pass" if not self.failures else "fail",
                "invariants_checked": self.comparisons,
                "failed_invariants": self.failures}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--inner-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = Checker(load(args.scores), load(args.plan), load(args.inner_summary)).run()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {"schema_version": "goal052-outer-richness-result-check-v1", "status": "fail",
                  "failed_invariants": ["checker_error:" + str(error)]}
    text = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
