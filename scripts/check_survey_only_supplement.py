#!/usr/bin/env python3
"""Check the owned survey-only SI tables against accepted public aggregates."""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "tasmania_pseudoabsence" / "20261011" / "survey-only"
SI = ROOT / "manuscript" / "text" / "survey-only-and-design.md"
METRICS = ("roc_auc", "tss", "mcc")
METHODS = ("target_only_resmlp", "multihead_full_finetune", "selected_conventional")
ENDPOINTS = {
    "25% / L0": "fraction25/ladder00", "25% / L1": "fraction25/ladder01",
    "25% / L2": "fraction25/ladder02", "50% / L0": "fraction50/ladder00",
    "50% / L1": "fraction50/ladder01", "50% / L2": "fraction50/ladder02",
    "100% / full": "fraction100/full",
}
PANELS = {"Mixed": "original_mixed", "Survey-only": "survey_only"}
TRAINING = {"Original": "primary", "Filtered": "sensitivity"}
SPECIES = {
    "*Dasyurus maculatus*": "dasyurus_maculatus", "*Dasyurus viverrinus*": "dasyurus_viverrinus",
    "*Notamacropus rufogriseus*": "notamacropus_rufogriseus", "*Pseudocheirus peregrinus*": "pseudocheirus_peregrinus",
    "*Sarcophilus harrisii*": "sarcophilus_harrisii", "*Thylogale billardierii*": "thylogale_billardierii",
    "*Trichosurus vulpecula*": "trichosurus_vulpecula", "*Vombatus ursinus*": "vombatus_ursinus",
}
CONTRASTS = {
    "target": "multihead_full_finetune_minus_target_only_resmlp",
    "conventional": "multihead_full_finetune_minus_selected_conventional",
}


def mean(rows: list[dict[str, str]], metric: str, phase: str) -> float:
    return sum(float(row[f"{phase}_{metric}"]) for row in rows) / len(rows)


def data_lines(lines: list[str], heading: str, next_heading: str | None) -> list[list[str]]:
    start = next(i for i, line in enumerate(lines) if line.startswith(heading)) + 1
    stop = next((i for i, line in enumerate(lines[start:], start) if line.startswith(next_heading)), len(lines)) if next_heading else len(lines)
    table = []
    for line in lines[start:stop]:
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        table.append([x.strip() for x in line.strip("|").split("|")])
    assert table, heading
    return table


def check_metric_table(lines: list[str], heading: str, metric: str, next_heading: str) -> int:
    table = data_lines(lines, heading, next_heading)
    assert len(table) == 29, (heading, len(table))  # header plus 28 rows
    rows = table[1:]
    accepted = json.loads((EVIDENCE / "summary.json").read_text())["all_endpoint_method_means"]
    means = {(x["evaluation_panel"], x["endpoint"], x["method"]): x for x in accepted}
    seen = set()
    for row in rows:
        assert len(row) == 6, row
        panel, training, endpoint = PANELS[row[0]], TRAINING[row[1]], ENDPOINTS[row[2]]
        phase = training
        for method, value in zip(METHODS, row[3:]):
            key = (panel, endpoint, method)
            expected = means[key][metric][phase]
            assert abs(float(value) - expected) < 5e-5, (heading, key, value, expected)
            seen.add((panel, training, endpoint, method))
    assert len(seen) == 2 * 2 * 7 * 3
    return len(rows)


def check_s11(lines: list[str], contrasts: list[dict[str, str]], counts: dict[str, dict]) -> int:
    heading = "### Table S11. Per-species full-data survey-only contrasts"
    table = data_lines(lines, heading, "### Public source and deterministic check")
    assert len(table) == 9, len(table)
    rows = table[1:]
    for row in rows:
        assert len(row) == 6, row
        species = SPECIES[row[0]]
        assert int(row[1]) == counts[species]["retained_survey_supported_absence"]
        for col, comp, metric in [
            (2, CONTRASTS["target"], "roc_auc"), (3, CONTRASTS["target"], "tss"),
            (4, CONTRASTS["conventional"], "roc_auc"), (5, CONTRASTS["conventional"], "tss"),
        ]:
            vals = [float(v) for v in re.findall(r"[-+]?\d+\.\d+", row[col])]
            assert len(vals) == 2, row[col]
            source = next(x for x in contrasts if x["evaluation_panel"] == "survey_only" and x["endpoint"] == "fraction100/full" and x["species"] == species and x["contrast"] == comp and x["metric"] == metric)
            assert abs(vals[0] - float(source["primary_contrast"])) < 5e-5
            assert abs(vals[1] - float(source["sensitivity_contrast"])) < 5e-5
    assert any(row[0] == "*Vombatus ursinus*" and row[1] == "7" for row in rows)
    return len(rows)


def main() -> None:
    with (EVIDENCE / "performance.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (EVIDENCE / "contrasts.csv").open(newline="") as handle:
        contrasts = list(csv.DictReader(handle))
    summary = json.loads((EVIDENCE / "summary.json").read_text())
    assert len(rows) == 336
    assert sorted({row["evaluation_panel"] for row in rows}) == ["original_mixed", "survey_only"]
    assert sorted({row["method"] for row in rows}) == sorted(METHODS)
    assert len({row["species"] for row in rows}) == 8
    assert len({row["endpoint"] for row in rows}) == 7
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["evaluation_panel"], row["endpoint"], row["method"])].append(row)
    accepted = {(x["evaluation_panel"], x["endpoint"], x["method"]): x for x in summary["all_endpoint_method_means"]}
    assert len(grouped) == len(accepted) == 42
    for key, group in grouped.items():
        assert len(group) == 8
        for metric in METRICS:
            for phase in ("primary", "sensitivity"):
                assert abs(mean(group, metric, phase) - float(accepted[key][metric][phase])) <= 1e-12
    counts = summary["counts"]
    assert sum(v["retained_presence"] for v in counts.values()) == 1300
    assert sum(v["retained_survey_supported_absence"] for v in counts.values()) == 242
    assert sum(v["excluded_pseudoabsence"] for v in counts.values()) == 130
    lines = SI.read_text().splitlines()
    n = sum(check_metric_table(lines, f"### Table {letter}.", metric, next_heading) for letter, metric, next_heading in [("S10a", "roc_auc", "### Table S10b."), ("S10b", "tss", "### Table S10c."), ("S10c", "mcc", "### Table S11.")])
    s11 = check_s11(lines, contrasts, counts)
    print(f"PASS: 336 aggregate rows and 42 exact AUC/TSS/MCC summaries")
    print(f"PASS: S10a/S10b/S10c each have 28 rows ({n} metric rows total); S11 has {s11} species rows")
    print("PASS: 1300 presences + 242 survey-supported negatives; 130 pseudoabsences excluded")


if __name__ == "__main__":
    main()
