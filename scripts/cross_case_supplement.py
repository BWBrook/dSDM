"""Generate the supplementary methods and descriptive tables from aggregates.

This is a reporting-only script.  It reads accepted aggregate JSON and frozen
configuration files, validates their inventories, and writes one deterministic
Markdown document.  It does not fit models, read response rows or prediction
payloads, or calculate metrics from raw inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / "evidence/cross_case_synthesis/20261005/revision-01/summary.json"
DEFAULT_OUTPUT = ROOT / "manuscript/text/supplement.md"
RESAMPLING_INPUT = ROOT / "evidence/cross_case_synthesis/20261008/bird-composition-resampling.csv"

STATIC_INPUTS = {
    "effort_followup": (
        "evidence/seawfb_dsdm/goal052/effort-followup-20261002.json",
        "742c367ab100886da764853cceeaca1684176259d934794d7ec83c8896e5cad0",
    ),
    "effort_review": (
        "evidence/seawfb_dsdm/goal052/effort-review-20261001.json",
        "920b43478ec4d8cb3d94b165017e69b20cdfe4b7bff8c9f6f3029c5161d7f7db",
    ),
    "modeling_foundation": (
        "config/modeling_foundation_preflight.json",
        "35b6ab72ba2b8ba2267dc82179987bfffaa3f339d64272d68012444e46285f00",
    ),
    "tasmania_conventional": (
        "config/conventional_baseline_production.json",
        "62b1c5255c5aa5c74f5ba598818dd13e2f2234c0cb13da58671c3be286ccefae",
    ),
    "mainland_conventional": (
        "config/goal044_mainland_conventional.json",
        "66350f80d58e58eb1c55fa95cc9e4c899d8792404b09acc26d40c71715828a68",
    ),
    "bird_conventional": (
        "config/goal051_seawfb_conventional.json",
        "48465d0a5180931a72ffc87aa830f6ce60da93a4b491558540af5afa9d42884d",
    ),
    "bird_dsdm": (
        "config/goal052_seawfb_dsdm.json",
        "04b667168944b39ced1044da8f381553c4024e31cca1f5590f2fbc693e521f9a",
    ),
    "uv_lock": (
        "uv.lock",
        "51712e74b2f9d78a4efb7bfd6732244188e8c6c5bc722f7a78f2724e6b8b84f6",
    ),
}

CASE_ORDER = (
    "tasmania_inner",
    "tasmania_outer",
    "mainland_inner",
    "mainland_to_tasmania",
    "birds_inner",
    "birds_outer",
)
CASE_LABELS = {
    "tasmania_inner": "Tasmania inner",
    "tasmania_outer": "Tasmania held patches",
    "mainland_inner": "Mainland inner",
    "mainland_to_tasmania": "Mainland to Tasmania",
    "birds_inner": "Birds inner (common 73)",
    "birds_outer": "Birds outer (equal regions)",
}
RICHNESS_BINS = ("10_24", "25_99", "100_plus")
PANELS = ("primary59", "other83", "all142")
CONTRASTS = ("ft_minus_conventional", "ft_minus_target_only")
FAMILIES = ("intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def content_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    require(isinstance(value, dict), f"expected object: {path}")
    return value


def fmt_delta(value: Any) -> str:
    return "NA" if value is None else f"{float(value):+.6f}"


def fmt_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):g}"


def fmt_component(value: Any) -> str:
    return f"{float(value):+.12f}"


def table(lines: list[str], headers: list[str], rows: list[list[str]], aligns: list[str] | None = None) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    if aligns is None:
        aligns = ["---"] * len(headers)
    lines.append("| " + " | ".join(aligns) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    lines.append("")


def validate_summary(summary: dict[str, Any]) -> None:
    require(summary.get("schema_version") == "dsdm-cross-case-synthesis-v2", "summary schema must be v2")
    require(summary.get("analysis") == "descriptive_reporting_of_accepted_aggregates", "unexpected summary analysis")
    cases = summary.get("cases")
    require(isinstance(cases, dict), "summary cases missing")
    require(set(CASE_ORDER).issubset(cases), "summary missing required paired case")
    for case in CASE_ORDER:
        value = cases[case]
        require(isinstance(value, dict), f"case is not an object: {case}")
        require("contrasts" in value and "species" in value, f"case fields missing: {case}")
        require(set(value["contrasts"]) >= {"target_only", "conventional"}, f"comparators missing: {case}")
        n = len(value["species"])
        for comparator in ("target_only", "conventional"):
            stats = value["contrasts"][comparator]
            require(stats["n"] == n and stats["undefined"] == 0, f"contrast inventory: {case}/{comparator}")
            for key in (
                "mean",
                "median",
                "q25",
                "q75",
                "leave_one_species_out_mean_min",
                "leave_one_species_out_mean_max",
                "positive",
            ):
                require(key in stats, f"contrast field missing: {case}/{comparator}/{key}")
    baseline = summary.get("bird_target_only_baseline", {})
    panels = baseline.get("panels", {})
    require({"primary73", "other84", "all157"}.issubset(panels), "bird baseline panels missing")
    require(panels["primary73"]["n"] == 73 and panels["other84"]["n"] == 84 and panels["all157"]["n"] == 157, "bird baseline panel counts")


def load_static_inputs() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    fingerprints: dict[str, dict[str, str]] = {}
    data: dict[str, dict[str, Any]] = {}
    for name, (relative, expected) in STATIC_INPUTS.items():
        path = ROOT / relative
        actual = content_sha(path)
        require(actual == expected, f"accepted static input changed: {name}")
        fingerprints[name] = {"path": relative, "sha256": actual}
        if path.suffix == ".json":
            data[name] = read_json(path)
    return fingerprints, data


def validate_effort_inputs(followup: dict[str, Any], review: dict[str, Any]) -> None:
    checks = followup.get("class_checks", {})
    require(set(CONTRASTS).issubset(checks), "richness contrast panels missing")
    expected_targets = {"primary59": 59, "other83": 83, "all142": 142}
    for contrast in CONTRASTS:
        for panel, expected_n in expected_targets.items():
            block = checks[contrast].get(panel)
            require(isinstance(block, dict) and block.get("targets") == expected_n, f"richness panel inventory: {contrast}/{panel}")
            classes = block.get("classes", {})
            require(set(RICHNESS_BINS).issubset(classes), f"richness bins missing: {contrast}/{panel}")
            for richness in RICHNESS_BINS:
                value = classes[richness]
                require(value.get("n") == expected_n and "mean" in value and "positive" in value, f"richness class record: {contrast}/{panel}/{richness}")
    additive_root = review.get("richness_additive_check_no_minimum", {})
    additive = additive_root.get("primary73"), additive_root.get("other84")
    require(all(isinstance(item, dict) for item in additive), "additive panels missing")
    for name, expected_n in (("primary73", 73), ("other84", 84)):
        item = additive_root[name]
        require(item.get("targets") == expected_n, f"additive panel inventory: {name}")
        require(set(RICHNESS_BINS).issubset(item.get("weighted_class_contributions", {})), f"additive bins missing: {name}")
        require("sum_weighted_contributions" in item and "max_abs_identity_error" in item, f"additive checks missing: {name}")


def validate_model_inputs(foundation: dict[str, Any], tas: dict[str, Any], mainland: dict[str, Any], birds: dict[str, Any], dsdm: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    models = foundation.get("models", {})
    candidates = models.get("candidates", [])
    parameters = models.get("candidate_parameters", {})
    candidate_rows = {row["id"]: row for row in candidates}
    require(set(candidate_rows) == set(parameters), "foundation candidate registry mismatch")
    tas_ids = tas.get("models", {}).get("candidate_ids", {})
    mainland_ids = mainland.get("conventional", {}).get("candidate_ids", {})
    bird_ids = birds.get("conventional", {}).get("candidate_ids", {})
    require(set(tas_ids) == set(FAMILIES), "Tasmania conventional family inventory")
    require(mainland_ids == bird_ids, "portable candidate grids differ")
    require(set(mainland_ids) == set(FAMILIES), "portable conventional family inventory")
    require("gam" not in tas_ids and "residual_mlp" not in tas_ids, "excluded family entered conventional grid")
    require(
        tas.get("models", {}).get("seed_labels_by_family") == {
            "intercept": ["seed00"],
            "elastic_net": ["seed00", "seed01", "seed02", "seed03", "seed04"],
            "random_forest": ["seed00", "seed01", "seed02", "seed03", "seed04"],
            "hist_gradient_boosting": ["seed00"],
            "shallow_ann": ["seed00", "seed01", "seed02", "seed03", "seed04"],
        },
        "Tasmania seed policy drift",
    )
    expected_screen = {family: ["seed00"] for family in FAMILIES}
    expected_screen["shallow_ann"] = ["seed00", "seed01", "seed02"]
    expected_selected = {family: ["seed00"] for family in FAMILIES}
    expected_selected["random_forest"] = ["seed00", "seed01", "seed02", "seed03", "seed04"]
    expected_selected["shallow_ann"] = ["seed00", "seed01", "seed02", "seed03", "seed04"]
    for name, config in (("mainland", mainland), ("birds", birds)):
        conventional = config["conventional"]
        require(conventional.get("screen_seed_labels") == expected_screen, f"{name} screening seed policy drift")
        require(conventional.get("selected_seed_labels") == expected_selected, f"{name} selected seed policy drift")
        require(conventional.get("candidate_selection") == ["mean_fold_roc_auc_desc", "pooled_oof_tss_desc", "candidate_id_asc"], f"{name} candidate ranking drift")
        family_key = "best_family_selection" if name == "mainland" else "family_selection"
        require(conventional.get(family_key) == ["mean_fold_roc_auc_desc", "pooled_oof_tss_desc", "family_asc"], f"{name} family ranking drift")
    for family in FAMILIES:
        require(set(tas_ids[family]).issubset(candidate_rows), f"unknown Tasmania candidate: {family}")
        require(set(mainland_ids[family]).issubset(tas_ids[family]), f"portable candidate not in Tasmania grid: {family}")
    architecture = dsdm.get("architectures", {})
    require(len(architecture.get("candidates", [])) == 4, "bird architecture candidate count")
    require(set(architecture.get("constants", {})) >= {"activation", "normalization", "optimizer", "learning_rate", "batch_size", "max_epochs", "patience", "min_improvement"}, "bird architecture constants incomplete")
    return {"tasmania": tas_ids, "portable": mainland_ids}


def conventional_table_rows(foundation: dict[str, Any], inventories: dict[str, dict[str, list[str]]], family: str) -> list[list[str]]:
    params = foundation["models"]["candidate_parameters"]
    rows = []
    portable = set(inventories["portable"][family])
    for candidate_id in inventories["tasmania"][family]:
        value = params[candidate_id]
        if family == "intercept":
            row = [candidate_id, "—", "—", "yes" if candidate_id in portable else "no"]
        elif family == "elastic_net":
            row = [candidate_id, fmt_number(value["C"]), fmt_number(value["l1_ratio"]), "yes" if candidate_id in portable else "no"]
        elif family == "random_forest":
            row = [candidate_id, fmt_number(value["max_features"]), fmt_number(value["min_samples_leaf"]), fmt_number(value["max_depth"]), "yes" if candidate_id in portable else "no"]
        elif family == "hist_gradient_boosting":
            row = [candidate_id, fmt_number(value["learning_rate"]), fmt_number(value["max_leaf_nodes"]), fmt_number(value["min_samples_leaf"]), fmt_number(value["l2_regularization"]), "yes" if candidate_id in portable else "no"]
        else:
            row = [candidate_id, fmt_number(value["width"]), fmt_number(value["dropout"]), fmt_number(value["weight_decay"]), fmt_number(value["lr"]), "yes" if candidate_id in portable else "no"]
        rows.append(row)
    return rows


def render(summary: dict[str, Any], followup: dict[str, Any], review: dict[str, Any], foundation: dict[str, Any], tas: dict[str, Any], mainland: dict[str, Any], birds: dict[str, Any], dsdm: dict[str, Any], fingerprints: dict[str, dict[str, str]], resampling: list[dict[str, str]]) -> str:
    inventories = validate_model_inputs(foundation, tas, mainland, birds, dsdm)
    lines = [
        "# Supplementary methods and descriptive tables",
        "",
        "This supplement gives model specifications and descriptive comparisons for the three study settings.",
        "",
        "## Supplementary methods",
        "",
        "Cross-case contrasts are reported in the paired order of the inner and outer assessments. Within each assessment, species-level ROC AUC contrasts were summarized by their arithmetic mean, median and interquartile range. Quartiles use linear interpolation with inclusive endpoints (R type 7). The positive count is the number of species with a contrast greater than zero. The single-deletion range is the minimum and maximum of the species mean after deleting each species once. These summaries are descriptive; the IQR is not a confidence interval, and the deletion calculation does not assume independent species or represent joint ecological uncertainty.",
        "",
        "The central 95% species-composition resampling ranges in Table S1d use 100,000 draws of 73 species with replacement from the observed primary bird panel. A single draw carries all methods, inner estimates and the three outer regions together; outer AUC remains the equal-region mean within species before averaging species. The reported endpoints are the 2.5th and 97.5th percentiles of replicate means, with linear interpolation. NumPy PCG64 uses two spawned streams from SeedSequence(20261008), stream 0 for species and stream 1 for focal blocks. These post hoc ranges describe empirical reweighting conditional on the fitted models, data and regions. They are not confidence intervals and exclude fitting, spatial-sampling, model-selection and population uncertainty. No coverage, significance or probability-of-benefit interpretation is attached to them.",
        "",
        "The inner-only focal-block width check uses 100,000 draws of ten blocks with replacement, keeping every primary-panel species in each sampled block occurrence. The mean is the sum of these species contrasts divided by their total count, rather than an equal mean of block means. The ten primary-panel block sizes are 6, 4, 3, 9, 7, 8, 9, 10, 7 and 10. These hash-balanced computational blocks share pretrained objects but are neither taxonomic nor spatial clusters. Common folds, predictors, geography, architecture selection and overlapping auxiliary pools still induce dependence across blocks. Ten blocks give limited tail resolution. Table S1e compares widths descriptively; neither range is selected as a conservative inferential bound.",
        "",
        "The exploratory inner bird recording-richness check reused all available focal presences for each background bin; only the background cells changed between the 10–24, 25–99 and 100+ donor-richness classes. Each stratified panel retained the same targets across all three bins, requiring at least 20 presences and 20 bin-specific backgrounds in every fold. Seed means were formed first, followed by equal-fold and equal-species means. The additive check retained all targets in each panel without the diagnostic minimum-20 gate. It weighted each bin's AUC contrast by its background share within each species and fold before averaging folds and species; separate averaged weights were not multiplied by separate averaged AUCs.",
        "",
        "The original Tasmania conventional grid used the candidate IDs and family-specific seeds in `conventional_baseline_production.json`: `seed00` for the intercept and histogram-gradient-boosting families, and `seed00`–`seed04` for elastic net, random forest and shallow ANN. The portable mainland and bird grids used the common subset shown in Table S3, one screening seed for every family except shallow ANN (`seed00`–`seed02`), then the selected refit seeds: `seed00` for intercept, elastic net and histogram-gradient boosting, and `seed00`–`seed04` for random forest and shallow ANN. Candidate ranking used mean-fold ROC AUC, then pooled out-of-fold TSS, then candidate ID; family ranking used the same first two criteria and then family ID.",
        "",
        "The four bird residual-network candidates and shared constants are listed below the conventional grids. The bird selection scope was the 73 primary targets with one selection seed. Pretraining excluded the focal target and its entire focal block in the ten-block design, with the held-fold exclusion retained. Retained-full refits used the same rounded median selected epoch across 25 fold-by-seed fits for each target and arm; pretraining used the corresponding block-level median. Exact shallow-ANN epochs were recovered before the outer assessment, as recorded by the accepted outer inventory. The accepted architecture constants were GELU activation, LayerNorm, AdamW, learning rate 0.001, batch size 128, maximum 300 epochs, patience 30 and minimum improvement 0.00001; stopping used the next fold and replay used all four non-held folds at the selected epoch.",
        "",
        "The bird software environment was fixed by a uv lockfile, including PyTorch 2.13.0, scikit-learn 1.9.0 and NumPy 2.5.1. Source and environment fingerprints accompany the archived run records. Historical mammal executions retain their separately archived specifications.",
        "",
        "## Table S1. Cross-case species-level contrasts",
        "",
        "Positive means favour full fine-tuning over the named comparator. Values are AUC differences.",
        "",
        "### Table S1a. Full fine-tuning minus target-only network",
        "",
    ]

    rows = []
    for case in CASE_ORDER:
        stats = summary["cases"][case]["contrasts"]["target_only"]
        rows.append([CASE_LABELS[case], fmt_delta(stats["mean"]), f"{fmt_delta(stats['median'])} [{fmt_delta(stats['q25'])}, {fmt_delta(stats['q75'])}]", f"{stats['positive']}/{stats['n']}"])
    table(lines, ["Assessment", "Mean", "Median [Q1, Q3]", "Positive/n"], rows, ["---", "---:", "---:", "---:"])

    lines.extend(["### Table S1b. Full fine-tuning minus selected conventional learner", ""])
    rows = []
    for case in CASE_ORDER:
        stats = summary["cases"][case]["contrasts"]["conventional"]
        rows.append([CASE_LABELS[case], fmt_delta(stats["mean"]), f"{fmt_delta(stats['median'])} [{fmt_delta(stats['q25'])}, {fmt_delta(stats['q75'])}]", f"{stats['positive']}/{stats['n']}"])
    table(lines, ["Assessment", "Mean", "Median [Q1, Q3]", "Positive/n"], rows, ["---", "---:", "---:", "---:"])

    lines.extend(["\\newpage", "", "### Table S1c. Single-species deletion sensitivity", ""])
    rows = []
    for case in CASE_ORDER:
        target = summary["cases"][case]["contrasts"]["target_only"]
        conventional = summary["cases"][case]["contrasts"]["conventional"]
        rows.append([CASE_LABELS[case], f"[{fmt_delta(target['leave_one_species_out_mean_min'])}, {fmt_delta(target['leave_one_species_out_mean_max'])}]", f"[{fmt_delta(conventional['leave_one_species_out_mean_min'])}, {fmt_delta(conventional['leave_one_species_out_mean_max'])}]"])
    table(lines, ["Assessment", "Target-only deletion range", "Conventional deletion range"], rows, ["---", "---:", "---:"])

    lines.extend(["### Table S1d. Bird species-composition resampling ranges", "", "Central 95% ranges of resampled-panel means, conditional on the observed 73 species, fitted models, data and regions. These are not confidence intervals and exclude fitting, spatial-sampling, model-selection and population uncertainty.", ""])
    comp_labels = {"target_only": "Target-only", "conventional": "Conventional"}
    sampled = {(r["case"], r["comparator"], r["scheme"]): r for r in resampling}
    rows = []
    for case in ("birds_inner", "birds_outer"):
        for comp in ("target_only", "conventional"):
            r = sampled[(case, comp, "species")]
            rows.append(["Inner" if case == "birds_inner" else "Outer", comp_labels[comp], fmt_delta(r["mean"]), f"[{fmt_delta(r['lower'])}, {fmt_delta(r['upper'])}]"])
    table(lines, ["Assessment", "Comparator", "Mean", "Resampling range"], rows, ["---", "---", "---:", "---:"])

    lines.extend(["### Table S1e. Inner bird focal-block resampling width check", "", "Both schemes preserve paired model comparisons. Block replicates contain varying numbers of species. The ten computational blocks are not ecological clusters, and neither scheme estimates all dependence or supplies population coverage.", ""])
    rows = []
    for comp in ("target_only", "conventional"):
        for scheme, label in (("species", "Species"), ("focal_block", "Focal block")):
            r = sampled[("birds_inner", comp, scheme)]
            rows.append([comp_labels[comp], label, f"[{fmt_delta(r['lower'])}, {fmt_delta(r['upper'])}]", fmt_number(float(r["width"]))])
    table(lines, ["Comparator", "Scheme", "Central 95% range", "Width"], rows, ["---", "---", "---:", "---:"])

    lines.extend(["## Table S2. Bird recording-richness diagnostics", "", "### Table S2a. Inner richness-bin contrasts", ""])
    rows = []
    labels = {"ft_minus_conventional": "Fine-tuning − conventional", "ft_minus_target_only": "Fine-tuning − target-only"}
    panel_labels = {"primary59": "Primary 59", "other83": "Other 83", "all142": "All 142"}
    bin_labels = {"10_24": "10–24", "25_99": "25–99", "100_plus": "100+"}
    for panel in PANELS:
        for contrast in CONTRASTS:
            for richness in RICHNESS_BINS:
                value = followup["class_checks"][contrast][panel]["classes"][richness]
                rows.append([panel_labels[panel], labels[contrast], bin_labels[richness], fmt_delta(value["mean"]), f"{value['positive']}/{value['n']}"])
    table(lines, ["Panel", "Contrast", "Background richness", "Mean", "Positive/n"], rows, ["---", "---", "---", "---:", "---:"])

    lines.extend(["### Table S2b. Exact background-share-weighted additive decomposition", ""])
    rows = []
    additive = review["richness_additive_check_no_minimum"]
    for richness in RICHNESS_BINS:
        rows.append([bin_labels[richness] + " contribution", *[
            fmt_component(additive[panel]["weighted_class_contributions"][richness]["mean"])
            for panel in ("primary73", "other84")]])
    for label, key in (("Sum of contributions", "sum_weighted_contributions"),
                       ("All-background mean", "all_background_ft_minus_conventional")):
        rows.append([label, *[fmt_component(additive[panel][key]["mean"])
                              for panel in ("primary73", "other84")]])
    rows.append(["Maximum identity error", *[f"{additive[panel]['max_abs_identity_error']:.3e}"
                                              for panel in ("primary73", "other84")]])
    table(lines, ["Fine-tuning minus conventional", "Primary 73", "Other 84"], rows, ["---", "---:", "---:"])

    lines.extend(["## Table S3. Conventional grids and bird architecture candidates", "", "Portable = candidate retained in both the mainland and bird conventional grids; all other rows belong to the original Tasmania grid only.", "", "### Table S3a. Intercept and elastic-net candidates", ""])
    table(lines, ["Candidate", "C", "l1 ratio", "Portable"], conventional_table_rows(foundation, inventories, "intercept") + conventional_table_rows(foundation, inventories, "elastic_net"), ["---", "---:", "---:", "---:"])

    lines.extend(["### Table S3b. Random-forest candidates", ""])
    table(lines, ["Candidate", "max features", "min samples leaf", "max depth", "Portable"], conventional_table_rows(foundation, inventories, "random_forest"), ["---", "---:", "---:", "---:", "---:"])

    lines.extend(["### Table S3c. Histogram-gradient-boosting candidates", ""])
    table(lines, ["Candidate", "Learning rate", "Max leaf nodes", "Min samples leaf", "L2 regularization", "Portable"], conventional_table_rows(foundation, inventories, "hist_gradient_boosting"), ["---", "---:", "---:", "---:", "---:", "---:"])

    lines.extend(["### Table S3d. Shallow-ANN candidates", ""])
    table(lines, ["Candidate", "Width", "Dropout", "Weight decay", "Learning rate", "Portable"], conventional_table_rows(foundation, inventories, "shallow_ann"), ["---", "---:", "---:", "---:", "---:", "---:"])

    lines.extend(["Shared conventional constants were 500 trees with bootstrap sampling for random forests, 300 iterations without early stopping for histogram-gradient boosting, and 300 maximum epochs with patience 30 for shallow ANNs. A dash in the random-forest depth column denotes no depth limit; decimal max-feature values are fractions of the input columns. Elastic-net candidates used the SAGA solver with 5000 iterations and tolerance 1e−6. `null00` was the empirical inner-training prevalence clipped at 1e−7. GAM and residual-MLP registry entries were excluded from these conventional grids.", "", "### Table S3e. Bird residual-network architecture candidates", ""])
    arch_rows = []
    for candidate in dsdm["architectures"]["candidates"]:
        arch_rows.append([candidate["id"], str(candidate["blocks"]), str(candidate["width"]), str(candidate["bottleneck"]), fmt_number(candidate["dropout"]), fmt_number(candidate["weight_decay"])])
    table(lines, ["Candidate", "Blocks", "Width", "Bottleneck", "Dropout", "Weight decay"], arch_rows, ["---", "---:", "---:", "---:", "---:", "---:"])

    lines.extend(["\\newpage", "", "## Table S4. Bird target-only baseline comparison", "", "These descriptive contrasts use the full-data mean-fold AUC endpoint. They document baseline performance while retaining the asymmetry that architecture selection used fine-tuning.", ""])
    baseline = summary["bird_target_only_baseline"]["panels"]
    rows = []
    for panel, label in (("primary73", "Primary 73"), ("all157", "All 157")):
        value = baseline[panel]
        rows.append([label, str(value["n"]), fmt_delta(value["target_only_minus_ann"]), fmt_delta(value["target_only_minus_conventional"])])
    table(lines, ["Panel", "n", "Target-only − ANN", "Target-only − conventional"], rows, ["---", "---:", "---:", "---:"])

    lines.extend(["<!-- accepted-input-sha256"])
    lines.append(f"summary: {summary['_source_path']} sha256={summary['_source_sha256']}")
    for name, fingerprint in fingerprints.items():
        lines.append(f"{name}: {fingerprint['path']} sha256={fingerprint['sha256']}")
    lines.extend(["-->", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary_path = args.summary.resolve()
    require(summary_path.is_relative_to(ROOT / "evidence"), "summary must be aggregate evidence")
    summary = read_json(summary_path)
    validate_summary(summary)
    fingerprints, static_data = load_static_inputs()
    summary["_source_path"] = str(summary_path.relative_to(ROOT))
    summary["_source_sha256"] = content_sha(summary_path)
    validate_effort_inputs(static_data["effort_followup"], static_data["effort_review"])
    with RESAMPLING_INPUT.open(newline="") as stream:
        resampling = list(csv.DictReader(stream))
    expected = {(case, comp, "species") for case in ("birds_inner", "birds_outer") for comp in ("target_only", "conventional")}
    expected |= {("birds_inner", comp, "focal_block") for comp in ("target_only", "conventional")}
    require(len(resampling) == 6 and {(r["case"], r["comparator"], r["scheme"]) for r in resampling} == expected, "bird resampling inventory drift")
    for r in resampling:
        require(int(r["n_species"]) == 73, "resampling species count drift")
        require(all(math.isfinite(float(r[key])) for key in ("mean", "lower", "upper", "width")), "nonfinite resampling summary")
        require(float(r["lower"]) <= float(r["upper"]) and abs(float(r["width"]) - (float(r["upper"]) - float(r["lower"]))) < 1e-12, "resampling range drift")
        require(abs(float(r["mean"]) - summary["cases"][r["case"]]["contrasts"][r["comparator"]]["mean"]) < 1e-12, "resampling changed original mean")
    fingerprints["bird_composition_resampling"] = {"path": str(RESAMPLING_INPUT.relative_to(ROOT)), "sha256": content_sha(RESAMPLING_INPUT)}
    output = render(summary, static_data["effort_followup"], static_data["effort_review"], static_data["modeling_foundation"], static_data["tasmania_conventional"], static_data["mainland_conventional"], static_data["bird_conventional"], static_data["bird_dsdm"], fingerprints, resampling)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    print(f"summary_sha256={summary['_source_sha256']}")
    print(f"output_sha256={content_sha(args.output)}")


if __name__ == "__main__":
    main()
