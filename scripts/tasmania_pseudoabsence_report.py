"""Generate manuscript tables from independently verified aggregate sensitivity results."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/tasmania_pseudoabsence/20261009"
SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
METHODS = ("target_only_resmlp", "multihead_full_finetune", "selected_conventional")
LABELS = {METHODS[0]: "Target-only", METHODS[1]: "Fine-tuning", METHODS[2]: "Conventional"}
ENDPOINTS = tuple(f"fraction{f}/ladder{i:02d}" for f in (25, 50) for i in range(3)) + ("fraction100/full",)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def receipt(path):
    value = json.loads(Path(path).read_text())
    body = {k: v for k, v in value.items() if k != "receipt_digest"}
    observed = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    require(observed == value["receipt_digest"], f"receipt changed: {path}")
    return value


def records(name):
    with (EVIDENCE / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_idempotent(path, text):
    path = Path(path)
    if path.exists():
        require(path.read_text() == text, f"prior reporting artifact differs: {path}")
    else:
        with path.open("x") as stream:
            stream.write(text)


def label(species):
    genus, epithet = species.split("_")
    return f"*{genus[0].upper()}. {epithet}*"


def number(value, digits=4, signed=False):
    if value in (None, "NA"):
        return "NA"
    value = float(value)
    require(math.isfinite(value), "nonfinite report value")
    return format(value, f"+.{digits}f" if signed else f".{digits}f")


def table(lines, headers, rows):
    lines.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"])
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    lines.append("")


def summarize(performance, contrasts, maps):
    output = {"full_performance": {}, "endpoint_contrasts": [], "full_map_ranges": {}}
    for method in METHODS:
        subset = [r for r in performance if r["method"] == method and r["endpoint"] == ENDPOINTS[-1]]
        require(len(subset) == 8 and {r["species"] for r in subset} == set(SPECIES), "full performance inventory")
        output["full_performance"][method] = {
            metric: {phase: mean(float(r[f"{phase}_{metric}"]) for r in subset)
                     for phase in ("primary", "sensitivity", "delta")}
            for metric in ("roc_auc", "tss", "mcc")
        }
        subset_maps = [r for r in maps if r["method"] == method]
        require(len(subset_maps) == 8, "map inventory")
        output["full_map_ranges"][method] = {}
        for key in ("spearman_rho", "top_decile_retention"):
            values = [float(r[key]) for r in subset_maps if r[key] != "NA"]
            output["full_map_ranges"][method][key] = {
                "n_defined": len(values), "n_missing": len(subset_maps) - len(values),
                "min": min(values) if values else None,
                "median": median(values) if values else None,
                "max": max(values) if values else None,
            }
    for endpoint in ENDPOINTS:
        for comparator in (METHODS[0], METHODS[2]):
            for metric in ("roc_auc", "tss", "mcc"):
                subset = [r for r in contrasts if r["endpoint"] == endpoint and r["metric"] == metric
                          and r["contrast"] == "multihead_full_finetune_minus_" + comparator]
                require(len(subset) == 8 and {r["species"] for r in subset} == set(SPECIES), "contrast inventory")
                output["endpoint_contrasts"].append({
                    "endpoint": endpoint, "comparator": comparator, "metric": metric,
                    "primary_mean": mean(float(r["primary_contrast"]) for r in subset),
                    "sensitivity_mean": mean(float(r["sensitivity_contrast"]) for r in subset),
                    "change_in_mean": mean(float(r["change_in_contrast"]) for r in subset),
                    "sensitivity_positive_species": sum(float(r["sensitivity_contrast"]) > 0 for r in subset),
                    "species": 8,
                })
    return output


def main():
    assessment = receipt(EVIDENCE / "assessment.json")
    audit = receipt(EVIDENCE / "independent-assessment-verification.json")
    require(assessment["schema_version"] == "tasmania-pseudoabsence-sensitivity-assessment-v1"
            and audit["schema_version"] == "tasmania-pseudoabsence-independent-assessment-verification-v1"
            and assessment["success"] and audit["status"] == "pass"
            and audit["assessment_receipt_digest"] == assessment["receipt_digest"], "accepted independent audit required")
    require(audit["audit_source_sha256"] == sha(ROOT / "scripts/tasmania_pseudoabsence_audit.py"), "audit source changed")
    for key, count in {"target_physical_fits": 8125, "smoke_physical_fits": 14, "recovery_physical_fits": 200,
                       "source_leaves": 4800, "smoke_leaves": 8, "normalized_prediction_files": 8,
                       "species": 8, "endpoints": 7, "methods": 3, "held_rows": 1672, "map_domain_cells": 71023}.items():
        require(audit["verified_counts"][key] == count, f"independent audit inventory: {key}")
    expected_names = {"paired-performance.csv", "paired-contrasts.csv", "map-comparison.csv",
                      "source-specificity.csv", "held-source-counts.csv"}
    require(len(assessment["files"]) == 5 and {r["path"] for r in assessment["files"]}
            == {str((EVIDENCE / name).relative_to(ROOT)) for name in expected_names}, "assessment file inventory")
    require(audit["verified_hashes"]["public_aggregates"] == {Path(r["path"]).name: r["sha256"] for r in assessment["files"]},
            "audited aggregate bindings differ")
    for row in assessment["files"]:
        require(sha(ROOT / row["path"]) == row["sha256"], "assessed aggregate changed")
    rendering = receipt(EVIDENCE / "map-rendering.json")
    require(rendering["schema_version"] == "tasmania-sensitivity-map-rendering-v1"
            and rendering["export_script_sha256"] == sha(ROOT / "scripts/tasmania_pseudoabsence_maps.py")
            and rendering["renderer_sha256"] == sha(ROOT / "scripts/plot_tasmania_pseudoabsence.R")
            and rendering["map_source_sha256"] == "c27b848bd4db81932553ac801029b8e66cf1a1ecd05271343ee2b4d0a3035cc5"
            and rendering["methods"] == list(METHODS)
            and rendering["private_coordinates_exported_to_tracked_files"] is False,
            "map-rendering producer or domain changed")
    require(rendering["success"] and rendering["assessment_receipt_digest"] == assessment["receipt_digest"]
            and rendering["prediction_closure_digest"] == assessment["prediction_closure_digest"]
            and rendering["pairs"] == 24 and rendering["domain_cells"] == 71023, "map rendering not bound to assessment")
    require(len(rendering["files"]) == 16 and {r["path"] for r in rendering["files"]}
            == {str((EVIDENCE / "maps" / f"{sp}.{ext}").relative_to(ROOT)) for sp in SPECIES for ext in ("png", "pdf")},
            "map plate inventory")
    for row in rendering["files"]:
        require(sha(ROOT / row["path"]) == row["sha256"], "map plate changed")
    performance, contrasts, maps, sources, held = [records(name) for name in (
        "paired-performance.csv", "paired-contrasts.csv", "map-comparison.csv",
        "source-specificity.csv", "held-source-counts.csv")]
    require([len(x) for x in (performance, contrasts, maps, sources, held)] == [168, 336, 24, 336, 8], "aggregate counts")
    summary = summarize(performance, contrasts, maps)
    summary.update({
        "schema_version": "tasmania-pseudoabsence-report-summary-v1",
        "assessment_receipt_digest": assessment["receipt_digest"],
        "independent_audit_receipt_digest": audit["receipt_digest"],
        "map_rendering_receipt_digest": rendering["receipt_digest"],
        "report_source_sha256": sha(__file__),
        "weighting": "equal species within each endpoint; no pooling of endpoints as independent observations",
        "source_files": assessment["files"],
    })
    census_path = ROOT / "evidence/tasmania_pseudoabsence/20261008/source-census.json"
    require(sha(census_path) == "211bad0f88daa140f1d56ac2916fd5da584f4164e6e96e36748547b8dc392352", "source census changed")
    census = json.loads(census_path.read_text())
    training = {r["species"]: r for r in census["records"] if r["role"] == "outer_fit" and r["endpoint"] == ENDPOINTS[-1]}
    held_index = {r["species"]: r for r in held}
    lines = ["\\newpage", "", "## Supplementary methods S2. Tasmania pseudoabsence-removal sensitivity", "",
        "The sensitivity removed protocol-defined pseudoabsences from target discovery, stopping, replay and outer-fitting roles by canonical identity. The original five folds, three nested ladders at each reduced fraction, full-data endpoint, and evaluation rows were retained. All 896 fitting roles retained both classes, although stopping sets retained as few as two absences. Target support masks and conventional encoders were fitted using the retained target rows. Auxiliary training already excluded pseudoabsences; its original states, feature transforms, architecture and seed policy were fixed. Missing inner auxiliary weights were recovered by 200 replay-only fits at the original recorded epochs, with exact original initialization, model-state and auxiliary-prediction hashes required before target fitting. No auxiliary discovery or new community covariate was fitted.", "",
        "The two residual networks and the primary-selected conventional candidate were refitted for all eight species and all seven endpoints. Conventional candidates were not reselected after filtering. Sensitivity thresholds were recomputed from seed-averaged inner out-of-fold probabilities using the original maximum-TSS rule and lower-median tie rule. The complete 8,125-fit production panel and 14 separate smoke fits passed closure before one new semantic parse of the 1,672 original held responses. An independent replay checked all performance, threshold, source-specificity and map summaries. Thylogale, which had no target pseudoabsences to remove, reproduced its original inner and outer predictions, thresholds and maps exactly.", "",
        "This implements a sensitivity question in the original protocol, with training-only filtering, threshold recalibration, fixed comparator selection and map summaries specified after primary outer opening. It is not a fully prospective confirmatory test. Removing pseudoabsences changes class balance, calibration, early stopping and spatial support together. The paired changes are conditional on this fixed evaluation sample, including its pseudoabsences; they do not identify false absences or correct imperfect detection. Means below weight the eight species equally within each endpoint. Endpoints, folds, seeds and species are not independent ecological replicates. No inferential intervals or significance tests are reported.", "",
        "### Table S5. Full-data training perturbation and unchanged evaluation support", "",
        "Training columns show retained presences and survey-supported absences, then removed pseudoabsences. Held columns show the unchanged evaluation counts. All counts are species–cell rows.", ""]
    table(lines, ["Species", "Train presence", "Train survey zero", "Removed pseudoabsence", "Held presence", "Held survey zero", "Held pseudoabsence"], [
        [label(sp), training[sp]["retained"]["source"]["presence"], training[sp]["retained"]["source"]["survey_supported_absence"],
         training[sp]["excluded"]["rows"], held_index[sp]["positive"], held_index[sp]["survey_supported_absence"], held_index[sp]["pseudoabsence"]]
        for sp in SPECIES])
    full = {(r["species"], r["method"]): r for r in performance if r["endpoint"] == ENDPOINTS[-1]}
    for letter, metric, title in (("a", "roc_auc", "ROC AUC"), ("b", "tss", "TSS"), ("c", "mcc", "MCC")):
        lines.extend(["\\newpage", "", f"### Table S6{letter}. Full-data {title}: primary → sensitivity", "",
                      "Each cell gives the original value followed by the refitted sensitivity value on the same held rows. Threshold metrics use their respective inner-derived thresholds.", ""])
        table(lines, ["Species"] + [LABELS[m] for m in METHODS], [
            [label(sp)] + [number(full[sp, m]["primary_" + metric]) + " → " + number(full[sp, m]["sensitivity_" + metric]) for m in METHODS]
            for sp in SPECIES] + [["Equal-species mean"] + [number(summary["full_performance"][m][metric]["primary"]) + " → " + number(summary["full_performance"][m][metric]["sensitivity"]) for m in METHODS]])
    lines.extend(["\\newpage", "", "### Table S7. Fine-tuning contrasts at every endpoint", "",
        "Values are equal-species mean fine-tuning minus the named comparator, primary → sensitivity. Positive values favour fine-tuning. L0–L2 denote the three original nested ladders. Each row uses eight species; rows must not be treated as independent replicates.", ""])
    contrast_index = {(r["endpoint"], r["comparator"], r["metric"]): r for r in summary["endpoint_contrasts"]}
    for comparator in (METHODS[0], METHODS[2]):
        lines.extend([f"Comparator: {LABELS[comparator]}.", ""])
        table(lines, ["Endpoint", "AUC", "TSS", "MCC"], [
            [endpoint.replace("fraction", "").replace("/ladder0", "% / L").replace("100/full", "100% / full")] + [
                number(contrast_index[endpoint, comparator, metric]["primary_mean"], signed=True) + " → " + number(contrast_index[endpoint, comparator, metric]["sensitivity_mean"], signed=True)
                for metric in ("roc_auc", "tss", "mcc")]
            for endpoint in ENDPOINTS])
    lines.extend(["\\newpage", "", "### Table S8. Full-data suitability-map comparisons", "",
        "Each pair covers the same 71,023 structural-domain cells. Rank displacement is sensitivity minus primary in percentile points, using average ranks for ties; the displayed interval contains the 2.5th and 97.5th percentiles of cell displacements, not uncertainty bounds. Top-decile retention is the intersection divided by 7,103. Exact score ties are resolved by ascending canonical cell ID. These model outputs are relative suitability scores, not occupancy probabilities. Spearman correlation is NA if either map is constant.", ""])
    map_index = {(r["species"], r["method"]): r for r in maps}
    table(lines, ["Species", "Method", r"Spearman $\rho$", "Median rank shift [2.5%, 97.5%]", "Top-decile retention"], [
        [label(sp), LABELS[m], number((r := map_index[sp, m])["spearman_rho"]),
         number(r["rank_displacement_median_percentile_points"], 2, True) + " [" + number(r["rank_displacement_q025_percentile_points"], 2, True) + ", " + number(r["rank_displacement_q975_percentile_points"], 2, True) + "]",
         f"{r['top_decile_intersection']}/7103 ({100 * float(r['top_decile_retention']):.1f}%)"]
        for sp in SPECIES for m in METHODS])
    lines.extend(["\\newpage", "", "### Table S9. Full-data specificity by absence source", "",
        "Each cell gives primary → sensitivity true negatives over the unchanged source-specific absence denominator. Specificity is that fraction. NA denotes a zero denominator, not zero specificity. The two source-specific true-negative counts sum to the total true-negative count for the corresponding species and method.", ""])
    source_index = {(r["species"], r["method"], r["absence_source"]): r for r in sources if r["endpoint"] == ENDPOINTS[-1]}
    rows = []
    for sp in SPECIES:
        for method in METHODS:
            row = [label(sp), LABELS[method]]
            for source in ("survey_supported_absence", "pseudoabsence"):
                r = source_index[sp, method, source]
                row.append("NA (0 rows)" if int(r["denominator"]) == 0 else f"{r['primary_true_negative']}/{r['denominator']} → {r['sensitivity_true_negative']}/{r['denominator']}")
            rows.append(row)
    table(lines, ["Species", "Method", "Survey-supported absence", "Pseudoabsence"], rows)
    lines.extend(["The complete seven-endpoint performance, contrast and source-specificity tables, plus all eight three-method map plates, are retained with the aggregate evidence. Numerical tables above reproduce those verified outputs; they do not replace the original primary assessment.", "",
                  f"<!-- assessment-receipt: {assessment['receipt_digest']}; independent-audit-receipt: {audit['receipt_digest']} -->", ""])
    output = ROOT / "manuscript/text/tasmania-sensitivity.md"
    write_idempotent(output, "\n".join(lines))
    summary["supplement_sha256"] = sha(output)
    summary["receipt_digest"] = hashlib.sha256(json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    write_idempotent(EVIDENCE / "report-summary.json", json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"summary_digest": summary["receipt_digest"], "supplement": str(output.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
