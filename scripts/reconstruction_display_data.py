"""Extract reconstruction figure data from accepted species-level aggregates.

No responses, predictions or fitted models are opened. Resampling describes
the composition of observed species panels conditional on the fitted models.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/reconstruction/20261113"
REPLICATES = 100_000
BATCH_SIZE = 4096
REGIONS = ("NCP", "SEH", "NNC")
BINS = ("10_24", "25_99", "100_plus")
SOURCES = {
    "synthesis": ("evidence/cross_case_synthesis/20261005/revision-01/summary.json", "6834e34c74767864686862734f57a64a2ac10b324fcdadab89797e1cecbe0fd2"),
    "extent": ("evidence/seawfb_dsdm/goal052/extent-review-20261005.json", "08652c0909c600bd0e4794d89b522a1e3ecb32557e4f2dad64598cea3be12fa7"),
    "effort": ("evidence/seawfb_dsdm/goal052/effort-followup-20261002.json", "742c367ab100886da764853cceeaca1684176259d934794d7ec83c8896e5cad0"),
    "outer_scores": ("data/processed/dsdm/goal052-seawfb-dsdm-experiment/outer-assessment-20261003-r2/scores.json", "3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41"),
    "tasmania_summary": ("evidence/tasmania_pseudoabsence/20261011/survey-only/summary.json", "0edae61c9bc851c57cd6716d43fb93df204d4742f2c4e7fb2a6cbad73b9f224e"),
    "tasmania_species": ("evidence/tasmania_pseudoabsence/20261011/survey-only/performance.csv", "2589625618db2a0da34fe78fbb880963b1476c5a758f6ef2033db49babf3b933"),
    "prior_resampling": ("evidence/cross_case_synthesis/20261008/bird-composition-resampling.csv", "27e9815fc4ec58900690b7a06e7374a10ae780e619c53c0de6461c392f9cbc13"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def close(actual: float, expected: float, message: str) -> None:
    require(abs(actual - expected) < 2e-12, f"{message}: {actual} != {expected}")


def load(key: str):
    rel, expected = SOURCES[key]
    path = ROOT / rel
    require(digest(path) == expected, f"accepted input hash changed: {rel}")
    if path.suffix == ".csv":
        with path.open(newline="") as stream:
            return list(csv.DictReader(stream))
    return json.loads(path.read_text())


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    with (OUT / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sample_ranges(vectors: dict[str, np.ndarray], rng) -> dict[str, tuple[float, float]]:
    sizes = {len(x) for x in vectors.values()}
    require(len(sizes) == 1, "paired vectors have different species counts")
    n = next(iter(sizes))
    require(n > 0, "empty composition panel")
    samples = {key: np.empty(REPLICATES) for key in vectors}
    for start in range(0, REPLICATES, BATCH_SIZE):
        stop = min(REPLICATES, start + BATCH_SIZE)
        indices = rng.integers(0, n, size=(stop - start, n))
        for key, vector in vectors.items():
            require(np.all(np.isfinite(vector)), f"nonfinite contrast {key}")
            samples[key][start:stop] = vector[indices].mean(axis=1)
    return {key: tuple(float(x) for x in np.quantile(values, [0.025, 0.975], method="linear")) for key, values in samples.items()}


def summary_row(figure, case, setting, comparison, values, limits=(None, None), richness_bin=""):
    vector = np.asarray(values, dtype=float)
    require(np.all(np.isfinite(vector)), "nonfinite display values")
    return dict(figure=figure, case=case, setting=setting, comparison=comparison,
                richness_bin=richness_bin, n=len(vector), positive=int(np.sum(vector > 0)),
                mean=float(np.mean(vector)), lower=limits[0], upper=limits[1])


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    synthesis, extent = load("synthesis"), load("extent")
    effort, scores = load("effort"), load("outer_scores")
    tasmania, tasmania_species = load("tasmania_summary"), load("tasmania_species")
    prior = load("prior_resampling")
    cases = synthesis["cases"]
    primary = sorted(row["species"] for row in cases["birds_inner"]["species"])
    require(len(primary) == 73 and len(set(primary)) == 73, "primary inventory changed")
    require(set(primary) == set(extent["per_species"]), "extent primary inventory changed")
    rows2, rows3, rows4, rows_tas, rows_tas_species, summaries = [], [], [], [], [], []
    vectors = {}
    for setting, case in [("development", "birds_inner"), ("new_regions", "birds_outer")]:
        inventory = {row["species"]: row for row in cases[case]["species"]}
        require(set(inventory) == set(primary), f"{case} inventory changed")
        vector = np.array([inventory[s]["fine_tuned"] - inventory[s]["target_only"] for s in primary])
        vectors[f"fig2/{setting}"] = vector
        rows2.extend(dict(case="birds", setting=setting, species=s, difference=float(x)) for s, x in zip(primary, vector))
    vector = np.array([extent["per_species"][s]["inner"]["region_fold"]["equal_eligible_region_fold_macro"]["contrasts"]["ft_minus_to"] for s in primary])
    vectors["fig2/development_within_regions_folds"] = vector
    accepted = extent["inner"]["primary73"]["region_fold_equal_eligible_strata_per_target"]["contrasts"]["ft_minus_to"]
    close(float(vector.mean()), accepted["mean"], "region-fold mean")
    require(int(np.sum(vector > 0)) == accepted["positive"], "region-fold positive count changed")
    rows2.extend(dict(case="birds", setting="development_within_regions_folds", species=s, difference=float(x)) for s, x in zip(primary, vector))
    regional_rows = []
    for region in REGIONS:
        rs = {r["species"]: r for r in cases[f"birds_{region}"]["species"]}
        require(set(rs) == set(primary), f"regional inventory changed: {region}")
        xs = np.array([rs[s]["fine_tuned"] - rs[s]["target_only"] for s in primary])
        regional_rows.append(dict(region=region, n=73, positive=int(np.sum(xs > 0)), mean=float(xs.mean())))
    comparison_keys = {
        "single_species_minus_conventional": None,
        "pretrained_minus_conventional": "ft_minus_conv",
        "single_species_ensemble_minus_conventional": "to_conv_ensemble_minus_conv",
        "pretrained_ensemble_minus_conventional": "ft_conv_ensemble_minus_conv",
    }
    outer = extent["outer"]["primary73"]["equal_region_then_species_per_species"]
    for comparison, key in comparison_keys.items():
        values = []
        for species in primary:
            metrics = outer[species]["metrics"]
            if key is None:
                difference = metrics["target_only_random_init_resmlp"] - metrics["conventional"]
            else:
                difference = outer[species]["contrasts"][key]
            values.append(difference)
            rows3.append(dict(comparison=comparison, species=species, difference=difference))
        vector = np.array(values)
        vectors[f"fig3/{comparison}"] = vector
        if key:
            accepted = extent["outer"]["primary73"]["equal_region_then_species_contrast_distributions"][key]
            close(float(vector.mean()), accepted["mean"], f"{comparison} mean")
            require(int(np.sum(vector > 0)) == accepted["positive"], f"{comparison} positive count")
    primary_seed = np.random.SeedSequence(20261008).spawn(2)[0]
    ranges = sample_ranges(vectors, np.random.Generator(np.random.PCG64(primary_seed)))
    prior_checks = []
    for key, vector in vectors.items():
        figure, setting = key.split("/", 1)
        comparison = "pretrained_minus_single_species" if figure == "fig2" else setting
        summaries.append(summary_row(figure, "birds", setting if figure == "fig2" else "new_regions", comparison, vector, ranges[key]))
        if key in ("fig2/development", "fig2/new_regions"):
            case = "birds_inner" if setting == "development" else "birds_outer"
            previous = [r for r in prior if r["case"] == case and r["comparator"] == "target_only" and r["scheme"] == "species"]
            require(len(previous) == 1, "prior resampling row missing")
            for endpoint, value in zip(("lower", "upper"), ranges[key]):
                close(value, float(previous[0][endpoint]), f"prior range {case}/{endpoint}")
            prior_checks.append(case)
    for group, inner, geographic in [("tasmania", "tasmania_inner", "tasmania_outer"), ("mainland", "mainland_inner", "mainland_to_tasmania")]:
        require({r["species"] for r in cases[inner]["species"]} == {r["species"] for r in cases[geographic]["species"]}, "paired mammal panel changed")
        for setting, case in [("development", inner), ("new_regions", geographic)]:
            values = []
            for row in sorted(cases[case]["species"], key=lambda r: r["species"]):
                difference = row["fine_tuned"] - row["target_only"]
                rows2.append(dict(case=group, setting=setting, species=row["species"], difference=difference))
                values.append(difference)
            summaries.append(summary_row("fig2", group, setting, "pretrained_minus_single_species", values))
    richness_panels = []
    selected = [s for s in primary if all(effort["per_species"][s]["ft_minus_conventional"][b]["available_all_folds"] for b in BINS)]
    require(len(selected) == 59, "development common59 changed")
    development = {b: np.array([effort["per_species"][s]["ft_minus_conventional"][b]["delta"] for s in selected]) for b in BINS}
    for b in BINS:
        accepted = effort["class_checks"]["ft_minus_conventional"]["primary59"]["classes"][b]
        close(float(development[b].mean()), accepted["mean"], f"development richness {b}")
    richness_panels.append(("development", "all", selected, development))
    contrast = "multihead_full_finetune_minus_goal051_selected_conventional"
    for region, expected_n in [("NCP", 0), ("SEH", 38), ("NNC", 55)]:
        bins = scores["aggregate"]["richness"]["primary_by_region"][region]["bins"]
        members = sorted(bins[BINS[0]]["common_support"][contrast]["values"])
        require(len(members) == expected_n, f"outer common support changed: {region}")
        require(set(members) <= set(primary), "richness panel outside primary")
        values = {}
        for b in BINS:
            record = bins[b]["common_support"][contrast]
            require(sorted(record["values"]) == members, "common bin species differ")
            values[b] = np.array([record["values"][s] for s in members])
            if members:
                close(float(values[b].mean()), record["mean"], f"outer richness {region}/{b}")
                require(int(np.sum(values[b] > 0)) == record["positive_count"], "outer richness positives changed")
        if members:
            richness_panels.append(("new_regions", region, members, values))
    richness_seeds = np.random.SeedSequence(20261113).spawn(3)
    for panel, child in zip(richness_panels, richness_seeds):
        stage, region, members, values = panel
        limits = sample_ranges(values, np.random.Generator(np.random.PCG64(child)))
        for b in BINS:
            rows4.extend(dict(stage=stage, region=region, richness_bin=b, species=s, difference=float(x)) for s, x in zip(members, values[b]))
            summaries.append(summary_row("fig4", "birds", f"{stage}/{region}", "pretrained_minus_conventional", values[b], limits[b], b))
    method_map = {"multihead_full_finetune": "pretrained", "target_only_resmlp": "single_species", "selected_conventional": "conventional"}
    evaluations = {"original_mixed": "mixed", "survey_only": "survey_only"}
    for source_eval, evaluation in evaluations.items():
        for method, learner in method_map.items():
            metrics = tasmania["full_endpoint_original_vs_survey_means"][source_eval][method]["roc_auc"]
            records = [r for r in tasmania_species if r["evaluation_panel"] == source_eval and r["endpoint"] == "fraction100/full" and r["method"] == method]
            require(len(records) == 8, f"Tasmania full-data panel changed: {source_eval}/{method}: {len(records)}")
            for training, field in [("original", "primary"), ("pseudoabsences_removed", "sensitivity")]:
                values = [float(r[f"{field}_roc_auc"]) for r in records]
                close(float(np.mean(values)), metrics[field], "Tasmania mean/species agreement")
                rows_tas.append(dict(evaluation=evaluation, training=training, learner=learner, n=8, auc=metrics[field]))
                rows_tas_species.extend(dict(evaluation=evaluation, training=training, learner=learner, species=r["species"], auc=float(r[f"{field}_roc_auc"])) for r in records)
    outputs = {
        "fig2-pretraining-species.csv": (["case", "setting", "species", "difference"], rows2),
        "fig2-bird-region-means.csv": (["region", "n", "positive", "mean"], regional_rows),
        "fig3-bird-comparisons.csv": (["comparison", "species", "difference"], rows3),
        "fig4-richness-species.csv": (["stage", "region", "richness_bin", "species", "difference"], rows4),
        "fig4-tasmania-means.csv": (["evaluation", "training", "learner", "n", "auc"], rows_tas),
        "fig4-tasmania-species.csv": (["evaluation", "training", "learner", "species", "auc"], rows_tas_species),
        "display-resampling.csv": (["figure", "case", "setting", "comparison", "richness_bin", "n", "positive", "mean", "lower", "upper"], summaries),
    }
    for name, (fields, rows) in outputs.items():
        write_csv(name, fields, rows)
    receipt = {
        "schema_version": "dsdm-reconstruction-display-data-v1", "status": "pass", "date": "2026-11-13",
        "scope": "Accepted aggregate extraction and post hoc species-composition reporting extension; no raw responses, predictions or fits",
        "sources": {key: {"path": rel, "sha256": sha} for key, (rel, sha) in SOURCES.items()},
        "script": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": digest(Path(__file__))},
        "resampling": {
            "replicates": REPLICATES, "batch_size": BATCH_SIZE, "bit_generator": "PCG64", "numpy": np.__version__, "python": platform.python_version(),
            "quantiles": [0.025, 0.975], "quantile_method": "linear", "species_order": "ascending lexical",
            "primary73_seed": 20261008, "primary73_spawn_key": list(primary_seed.spawn_key),
            "pairing": "One index draw jointly carries all primary73 methods and assessments; bins paired within each separate richness panel",
            "richness_seed": 20261113, "richness_streams": [{"stage": x[0], "region": x[1], "n": len(x[2]), "spawn_key": list(child.spawn_key)} for x, child in zip(richness_panels, richness_seeds)],
            "interpretation": "Central 95% species-composition resampling range conditional on the observed species panel and fitted models; not a confidence interval; excludes fitting, spatial-sampling, selection and population uncertainty",
            "prior_ranges_reproduced": prior_checks,
        },
        "estimands": {
            "fig2_development": "Equal mean of five spatial folds within species, then species",
            "fig2_region_fold": "Equal eligible bioregion-by-fold strata within species, then species; retained development predictions",
            "fig2_new_regions": "Equal NCP/SEH/NNC mean within species, then species",
            "fig3": "Fixed-model contrasts against conventional, equal regions within species then equal species",
            "fig4_richness": "FT minus conventional on each common three-bin species panel; equal folds within development species; no NCP common-three-bin estimate",
            "fig4_tasmania": "Equal eight-species mean AUC of full-target/full-auxiliary models, original or pseudoabsence-removed training crossed with mixed or survey-only evaluation",
        },
        "checks": {"accepted_hashes_match": True, "source_aggregate_means_match": True, "prior_primary73_ranges_match": True, "tasmania_means_match_eight_species": True, "ncp_common_three_bin_support": 0},
        "outputs": {name: {"rows": len(rows), "sha256": digest(OUT / name)} for name, (_, rows) in outputs.items()},
    }
    (OUT / "display-data-verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "outputs": {name: len(rows) for name, (_, rows) in outputs.items()}}, indent=2))


if __name__ == "__main__":
    run()
