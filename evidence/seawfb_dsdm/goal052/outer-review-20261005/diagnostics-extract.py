#!/usr/bin/env python3
"""Extract and independently check the frozen Goal052 outer diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Mapping

TOL = 1e-12
REGIONS = ("NCP", "SEH", "NNC")
BINS = ("10_24", "25_99", "100_plus")
CONTRASTS = (
    "multihead_full_finetune_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_target_plus_q_linear_resmlp",
    "multihead_full_finetune_minus_goal051_selected_conventional",
    "multihead_full_finetune_minus_goal051_q_augmented_conventional",
    "multihead_frozen_trunk_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_multihead_frozen_trunk",
    "fixed_ensemble_minus_multihead_full_finetune",
    "fixed_ensemble_minus_selected_conventional",
)
ARMS = (
    "target_only_random_init_resmlp", "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk", "multihead_full_finetune",
    "selected_conventional", "selected_conventional_plus_q", "fixed_ensemble",
)
PAIRS = {
    CONTRASTS[0]: (ARMS[3], ARMS[0]), CONTRASTS[1]: (ARMS[3], ARMS[1]),
    CONTRASTS[2]: (ARMS[3], ARMS[4]), CONTRASTS[3]: (ARMS[3], ARMS[5]),
    CONTRASTS[4]: (ARMS[2], ARMS[0]), CONTRASTS[5]: (ARMS[3], ARMS[2]),
    CONTRASTS[6]: (ARMS[6], ARMS[3]), CONTRASTS[7]: (ARMS[6], ARMS[4]),
}
SCORE_SHA256 = "3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41"


class CheckError(RuntimeError):
    pass


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def close(left: Any, right: Any) -> bool:
    return left == right if left is None or right is None else finite(left) and finite(right) and abs(float(left) - float(right)) <= TOL


def fmt(value: Any) -> str:
    if value is None or not finite(value):
        return "NA"
    return f"{float(value):.12g}"


def stats(values: Mapping[str, Any], members: list[str]) -> dict[str, Any]:
    evaluated = [target for target in members if finite(values.get(target))]
    missing = [target for target in members if target not in evaluated]
    vector = [float(values[target]) for target in evaluated]
    denominator = len(vector)
    positive = sum(value > 0 for value in vector)
    mean = sum(vector) / denominator if denominator else None
    median = statistics.median(vector) if denominator else None
    return {"members": list(members), "evaluated_members": evaluated, "missing_members": missing,
            "values": {target: (float(values[target]) if target in evaluated else None) for target in members},
            "mean": mean, "median": median, "positive_count": positive,
            "denominator": denominator, "denom": denominator,
            "positive_fraction": positive / denominator if denominator else None,
            "label": (None if not denominator else
                       "consistent positive direction" if mean > 0 and positive > denominator / 2 else
                       "consistent nonpositive direction" if mean <= 0 and positive <= denominator / 2 else "mixed direction")}


class Extractor:
    def __init__(self, scores: Mapping[str, Any], plan: Mapping[str, Any], inner: Mapping[str, Any]):
        self.scores, self.plan, self.inner = scores, plan, inner
        self.aggregate = scores["aggregate"]
        self.richness = self.aggregate["richness"]
        self.contrasts = list(self.aggregate["contrasts"])
        self.rows = {(row["region"], row["target"]): row for row in scores["targets"]}
        self.support_ids: dict[tuple[str, ...], str] = {}
        self.supports: list[tuple[str, tuple[str, ...]]] = []
        self.checks = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            raise CheckError(message)

    def compare(self, actual: Any, expected: Any, message: str) -> None:
        self.checks += 1
        if isinstance(expected, Mapping):
            self.require(isinstance(actual, Mapping), message + ".type")
            for key, value in expected.items():
                self.compare(actual.get(key), value, message + "." + str(key))
            self.require(set(actual) == set(expected), message + ".keys")
        elif isinstance(expected, list):
            self.require(actual == expected, message)
        elif isinstance(expected, (int, float)) or expected is None:
            self.require(close(actual, expected), message)
        else:
            self.require(actual == expected, message)

    def support_id(self, members: list[str], prefix: str = "S") -> str:
        key = tuple(members)
        if key not in self.support_ids:
            self.support_ids[key] = f"{prefix}{len(self.support_ids) + 1:02d}"
            self.supports.append((self.support_ids[key], key))
        return self.support_ids[key]

    def row_auc(self, region: str, target: str, label: str, arm: str) -> Any:
        return self.rows[(region, target)]["richness"]["background_strata"][label]["auc"].get(arm)

    def row_contrast(self, region: str, target: str, label: str, contrast: str) -> Any:
        return self.rows[(region, target)]["richness"]["background_strata"][label]["contrasts"].get(contrast)

    def row_high_auc(self, region: str, target: str, arm: str) -> Any:
        return (self.rows[(region, target)]["richness"]["high_recording_richness_subset"]
                .get("auc", {}).get(arm))

    def row_high_contrast(self, region: str, target: str, contrast: str) -> Any:
        return (self.rows[(region, target)]["richness"]["high_recording_richness_subset"]
                .get("contrasts", {}).get(contrast))

    def verify_source_support(self, region: str, label: str, support: list[str]) -> None:
        for target in support:
            for arm in ARMS:
                self.require(finite(self.row_auc(region, target, label, arm)),
                             f"source_auc_missing:{region}:{target}:{label}:{arm}")
            for name, (left, right) in PAIRS.items():
                self.compare(self.row_contrast(region, target, label, name),
                             float(self.row_auc(region, target, label, left)) - float(self.row_auc(region, target, label, right)),
                             f"source_contrast:{region}:{target}:{label}:{name}")
        return None

    def verify_panel_bins(self, scope: str, region: str, members: list[str]) -> list[dict[str, Any]]:
        summary = self.richness[scope][region]
        rows = []
        for label in BINS:
            for kind in ("common_support", "all_available"):
                section = summary["bins"][label][kind]
                support = [list(section[c]["evaluated_members"]) for c in self.contrasts]
                self.require(all(item == support[0] for item in support), f"aggregate_support_drift:{scope}:{region}:{label}:{kind}")
                self.verify_source_support(region, label, support[0])
                sid = self.support_id(support[0])
                auc_means = {arm: (sum(float(self.row_auc(region, t, label, arm)) for t in support[0]) / len(support[0]) if support[0] else None) for arm in ARMS}
                rows.append((label, kind, sid, len(support[0]), auc_means))
                for name in self.contrasts:
                    values = {t: section[name]["values"].get(t) for t in members}
                    self.compare(section[name], stats(values, members if kind == "all_available" else support[0]) |
                                 ({"panel_members": members} if kind == "common_support" else {}),
                                 f"stats:{scope}:{region}:{label}:{kind}:{name}")
        return rows

    def verify_high(self, scope: str, region: str, members: list[str]) -> tuple[str, list[str], dict[str, Any]]:
        section = self.richness[scope][region]["high_recording_richness_subset"]["contrasts"]
        evaluated = [list(section[c]["evaluated_members"]) for c in self.contrasts]
        self.require(all(item == evaluated[0] for item in evaluated), f"high_support_drift:{scope}:{region}")
        support = evaluated[0]
        for target in support:
            for arm in ARMS:
                self.require(finite(self.row_high_auc(region, target, arm)), f"source_high_auc_missing:{region}:{target}:{arm}")
            for name, (left, right) in PAIRS.items():
                self.compare(self.row_high_contrast(region, target, name),
                             float(self.row_high_auc(region, target, left)) - float(self.row_high_auc(region, target, right)),
                             f"source_high_contrast:{region}:{target}:{name}")
        for name in self.contrasts:
            values = {target: section[name]["values"].get(target) for target in members}
            expected = stats(values, support) | {"panel_members": members,
                                                "nonevaluable_panel_members": [target for target in members if target not in support]}
            self.compare(section[name], expected, f"high_stats:{scope}:{region}:{name}")
        sid = self.support_id(support, "H")
        return sid, support, section

    def verify_macro(self, primary: list[str], regional: dict[str, list[str]]) -> None:
        macro = self.richness["supplementary_three_region_macro"]
        for label in BINS:
            section = macro["bins"][label]["contrasts"]
            common_section = macro["bins"][label]["three_bin_common_support"]
            evals = [list(section[c]["evaluated_members"]) for c in self.contrasts]
            commons = [list(common_section[c]["evaluated_members"]) for c in self.contrasts]
            self.require(all(x == evals[0] for x in evals), f"macro_support_drift:{label}")
            self.require(all(x == commons[0] for x in commons), f"macro_common_support_drift:{label}")
            self.support_id(evals[0], "M")
            self.support_id(commons[0], "M")
            for name in self.contrasts:
                values = {}
                for target in primary:
                    parts = [self.row_contrast(region, target, label, name) for region in REGIONS]
                    values[target] = sum(parts) / len(parts) if all(part is not None for part in parts) else None
                expected = stats(values, primary) | {"equal_region_macro_mean": stats(values, primary)["mean"]}
                self.compare(section[name], expected, f"macro_stats:{label}:{name}")
                self.compare(common_section[name], stats({t: values[t] for t in commons[0]}, commons[0]) | {"panel_members": primary}, f"macro_common_stats:{label}:{name}")
        high = macro["high_recording_richness_subset"]["contrasts"]
        evals = [list(high[c]["evaluated_members"]) for c in self.contrasts]
        self.require(all(x == evals[0] for x in evals), "macro_high_support_drift")
        self.support_id(evals[0], "H")
        for name in self.contrasts:
            values = {}
            for target in primary:
                parts = [self.row_high_contrast(region, target, name) for region in REGIONS]
                values[target] = sum(parts) / len(parts) if all(part is not None for part in parts) else None
            evaluated = [t for t in primary if values[t] is not None]
            expected = stats({t: values[t] for t in evaluated}, evaluated) | {"panel_members": primary, "nonevaluable_panel_members": [t for t in primary if t not in evaluated]}
            self.compare(high[name], expected, f"macro_high_stats:{name}")

    def report(self, scores_path: Path, plan_path: Path, inner_path: Path, script_sha: str) -> str:
        primary = list(self.plan["panels"]["primary"])
        regional = {region: list(self.plan["panels"]["regional"][region]) for region in REGIONS}
        self.require(self.contrasts == list(CONTRASTS), "contrast_inventory")
        self.require(len(self.plan["targets"]) == 157 and len(self.rows) == 471, "frozen_target_row_inventory")
        self.require(set(self.rows) == {(region, target) for region in REGIONS for target in self.plan["targets"]}, "frozen_target_row_identity")
        panel_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        high_rows = []
        for scope, panels in (("primary_by_region", {r: primary for r in REGIONS}), ("regional", regional)):
            for region, members in panels.items():
                panel_rows[(scope, region)] = self.verify_panel_bins(scope, region, members)
                sid, support, _ = self.verify_high(scope, region, members)
                high_rows.extend((scope, region, sid, len(support), name,
                                  self.richness[scope][region]["high_recording_richness_subset"]["contrasts"][name]) for name in self.contrasts)
        self.verify_macro(primary, regional)
        lines = ["# Goal052 outer diagnostics results (2026-10-05)", "",
                 "This derived readout was generated from the hash-verified closed outer score file. It adds mechanical recorded-richness diagnostics omitted by the native Markdown renderer.", "",
                 "## Provenance and rules", "",
                 f"- Scores: `{scores_path}`; SHA256 `{sha256(scores_path)}`.",
                 f"- Plan: `{plan_path}`; plan digest `{self.scores['plan_digest']}`.",
                 f"- Closure SHA256: `{self.scores['closure_sha256']}`.",
                 f"- Extraction script SHA256: `{script_sha}`.",
                 "- Richness is focal-excluded recorded richness of the complete frozen effort-donor pool. Presences remain in every X10/X20 response set; richness bins restrict background cells only.",
                 "- Bins are 10–24, 25–99, and 100+. Every binned or subset diagnostic AUC requires 20 cells per class; the high-recording subset is richness ≥100 for both presences and backgrounds.",
                 "- Values are descriptive AUC diagnostics. They do not establish causation, inferential significance, occupancy, or mechanism.", ""]
        lines += ["## Panel membership", "", "| Panel | Regions | Targets |", "|---|---|---:|",
                  f"| Primary | NCP / SEH / NNC | {len(primary)} |",
                  f"| Regional NCP | NCP | {len(regional['NCP'])} |", f"| Regional SEH | SEH | {len(regional['SEH'])} |", f"| Regional NNC | NNC | {len(regional['NNC'])} |", ""]
        lines += ["## Exact support membership inventory", "", "Each support ID is listed once; tables below refer to these exact evaluated target sets.", ""]
        for sid, members in self.supports:
            lines.append(f"- **{sid}** (n={len(members)}): " + (", ".join(members) if members else "∅"))
        lines += ["", "## High-recording-richness contrast summaries", "", "Mean, median, positive count, and evaluated denominator are reported for all eight contrasts. `NA (0/0)` is preserved.", ""]
        lines += ["| Panel | Region | Support | Contrast | Mean | Median | Positive / denominator |", "|---|---|---|---|---:|---:|---:|"]
        for scope, region, sid, n, name, item in high_rows:
            lines.append(f"| {scope} | {region} | {sid} (n={n}) | {name} | {fmt(item['mean'])} | {fmt(item['median'])} | {item['positive_count']}/{item['denominator']} |")
        lines += [""]
        macro_high = self.richness["supplementary_three_region_macro"]["high_recording_richness_subset"]["contrasts"]
        lines += ["### Supplementary three-region macro high subset", "", "| Contrast | Mean | Median | Positive / denominator |", "|---|---:|---:|---:|"]
        for name in self.contrasts:
            item = macro_high[name]; lines.append(f"| {name} | {fmt(item['mean'])} | {fmt(item['median'])} | {item['positive_count']}/{item['denominator']} |")
        lines += ["", "## Absolute AUCs by richness bin", "", "The following tables use source target-row `richness.background_strata[bin].auc` values. A common-three-bin table is only emitted after all eight contrast support lists agree exactly.", ""]
        for (scope, region), rows in panel_rows.items():
            lines += [f"### {scope} — {region}", "", "| Bin | Support | n | " + " | ".join(ARMS) + " |", "|---|---|---:|" + "---:|" * len(ARMS)]
            for label, kind, sid, n, means in rows:
                lines.append("| {} | {} ({}) | {} | {} |".format(label, kind, sid, n, " | ".join(fmt(means[a]) for a in ARMS)))
            lines.append("")
        lines += ["## Regional all-eight binned contrast summaries", "", "These summaries are for the regional panels; the native report already contains primary-panel summaries.", ""]
        for region in REGIONS:
            lines += [f"### Regional {region}", "", "| Bin | Support | n | Contrast | Mean | Median | Positive / denominator |", "|---|---|---:|---|---:|---:|---:|"]
            for label in BINS:
                for kind in ("common_support", "all_available"):
                    sec = self.richness["regional"][region]["bins"][label][kind]; sid = self.support_id(list(sec[self.contrasts[0]]["evaluated_members"])); n = sec[self.contrasts[0]]["denominator"]
                    for name in self.contrasts:
                        item = sec[name]; lines.append(f"| {label} | {kind} ({sid}) | {n} | {name} | {fmt(item['mean'])} | {fmt(item['median'])} | {item['positive_count']}/{item['denominator']} |")
            lines.append("")
        lines += ["## Three-region same-target richness macro", "", "The macro averages each target's regional contrast only when all three regions are available. The three-bin common-support rows additionally require all three bins in all three regions.", ""]
        macro = self.richness["supplementary_three_region_macro"]
        for label in BINS:
            lines += [f"### {label}", "", "| Support | n | Contrast | Mean | Median | Positive / denominator |", "|---|---:|---|---:|---:|---:|"]
            sec = macro["bins"][label]["contrasts"]; common = macro["bins"][label]["three_bin_common_support"]
            for kind, data in (("same-target macro", sec), ("three-bin common support", common)):
                sid = self.support_id(list(data[self.contrasts[0]]["evaluated_members"]), "M")
                for name in self.contrasts:
                    item = data[name]; lines.append(f"| {kind} ({sid}) | {item['denominator']} | {name} | {fmt(item['mean'])} | {fmt(item['median'])} | {item['positive_count']}/{item['denominator']} |")
        lines += ["", "## Exact headline weighted-bin decomposition", "", "Each row is the mean of target-level weighted contributions; the sum and absolute error are retained at 1e-12 tolerance.", ""]
        for scope in ("primary_by_region", "regional"):
            for region, members in ((r, primary if scope == "primary_by_region" else regional[r]) for r in REGIONS):
                lines += [f"### {scope} — {region}", "", "| Contrast | 10–24 | 25–99 | 100+ | Sum | Absolute error |", "|---|---:|---:|---:|---:|---:|"]
                for name in self.contrasts:
                    item = self.aggregate["headline_decomposition"][scope][region]["contrasts"][name]
                    c = item["mean_weighted_bin_contributions"]; lines.append(f"| {name} | {fmt(c['10_24'])} | {fmt(c['25_99'])} | {fmt(c['100_plus'])} | {fmt(item['sum'])} | {fmt(item['absolute_error'])} |")
                lines.append("")
        lines += ["## Matched-inner attenuation", "", "The stored matched-inner arithmetic is retained for auditability; it is an outer-minus-inner descriptive difference under the accepted target100/full inner reference.", ""]
        att = self.aggregate["matched_inner_attenuation"]
        lines += ["| Panel | Contrast | Inner mean | Outer mean | Outer minus inner | n |", "|---|---|---:|---:|---:|---:|"]
        for scope in ("primary_by_region", "regional"):
            for region in REGIONS:
                for name in self.contrasts[:6]:
                    item = att[scope][region][name]; lines.append(f"| {scope} / {region} | {name} | {fmt(item['inner_mean_difference'])} | {fmt(item['outer_mean_difference'])} | {fmt(item['outer_minus_inner'])} | {item['target_count']} |")
        for name in self.contrasts[:6]:
            item = att["common_equal_region_macro"][name]; lines.append(f"| common equal-region macro | {name} | {fmt(item['inner_mean_difference'])} | {fmt(item['outer_mean_difference'])} | {fmt(item['outer_minus_inner'])} | {item['target_count']} |")
        lines += ["", f"Mechanical extraction checks passed: {self.checks}.", ""]
        return "\n".join(line for line in lines if line is not None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--inner-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    self_sha = sha256(Path(__file__).resolve())
    scores = load(args.scores); actual_sha = sha256(args.scores)
    if actual_sha != SCORE_SHA256:
        raise SystemExit(f"score SHA mismatch: {actual_sha}")
    extractor = Extractor(scores, load(args.plan), load(args.inner_summary))
    report = extractor.report(args.scores, args.plan, args.inner_summary, self_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "checks": extractor.checks, "output": str(args.output), "output_sha256": sha256(args.output), "extractor_sha256": self_sha}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
