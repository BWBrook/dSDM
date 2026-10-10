"""Close and score the complete approved Tasmania sensitivity prediction panel.

Model execution is separate. Only ``score`` may parse outer-held responses,
and only after every prediction, threshold and map file has been closed.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from tasmania_pseudoabsence_metrics import binary_metrics, map_summary, require, source_specificity

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private/assessment"
EVIDENCE = ROOT / "evidence/tasmania_pseudoabsence/20261009"
BASELINE = ROOT / "data/processed/dsdm/tasmania-outer-assessment-20261005/private"
SPECIES = ("thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
           "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
           "dasyurus_maculatus", "dasyurus_viverrinus")
ENDPOINTS = ("fraction25/ladder00", "fraction25/ladder01", "fraction25/ladder02",
             "fraction50/ladder00", "fraction50/ladder01", "fraction50/ladder02", "fraction100/full")
METHODS = ("target_only_resmlp", "multihead_full_finetune", "selected_conventional")
BASE_NEURAL = ("target_only_resmlp", "legacy_pooled_finetune", "multihead_frozen_trunk",
               "multihead_full_finetune", "target_plus_q_linear", "target_plus_q_deep")
BASE_CONVENTIONAL = ("intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann")
RESPONSE = ROOT / "data/processed/partitions/goal025-spatial-partition/2026-07-26/response_partitioned.csv"
RESPONSE_SHA = "b93fbdfa4df2b2d8617dd890cdb7fc4c3aa54ed10c72eed9c9ebc93df18edafc"
BASE_RECEIPT_DIGEST = "6b1240538079be2219a22502625e34c473fce4c56c1030f5a302b4cacd6cb77e"
BASE_CLOSURE_DIGEST = "a160318d5cc627ff5a724256ee4a008ad4f13038b9419ba7e809cf01bd6a4e6e"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verified_receipt(path, expected=None):
    value = read(path)
    body = dict(value)
    claimed = body.pop("receipt_digest")
    require(digest(body) == claimed, f"receipt digest mismatch: {Path(path).name}")
    if expected is not None:
        require(claimed == expected, f"accepted receipt changed: {Path(path).name}")
    return value


def write_new_json(path, body):
    value = dict(body)
    value["receipt_digest"] = digest(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def baseline():
    receipt = verified_receipt(ROOT / "evidence/tasmania_outer_assessment/20261005/receipt.json", BASE_RECEIPT_DIGEST)
    closure = verified_receipt(BASELINE / "prediction-closure.json", BASE_CLOSURE_DIGEST)
    require(receipt["prediction_closure_digest"] == closure["receipt_digest"], "primary closure link mismatch")
    require(len(closure["files"]) == 32 and digest(closure["files"]) == closure["file_inventory_digest"], "primary inventory changed")
    for row in closure["files"]:
        path = BASELINE / ("inputs" if row["role"] == "input" else "predictions/" + row["role"]) / (row["species"] + ".npz")
        require(sha(path) == row["sha256"], "accepted primary prediction changed")
    config_path = ROOT / "config/tasmania_outer_assessment.json"
    require(sha(config_path) == receipt["config_digest"], "primary configuration changed")
    config = read(config_path)
    tables = {}
    for name in ("goal036_stratum_metrics", "goal036_conventional_selection"):
        binding = config["authorities"][name]
        path = ROOT / binding["path"]
        require(sha(path) == binding["sha256"], "primary threshold/selection changed")
        with path.open() as stream:
            tables[name] = list(csv.DictReader(stream))
    thresholds = {(r["species"], r["endpoint"], r["method"]): float(r["threshold"])
                  for r in tables["goal036_stratum_metrics"]}
    selected = {(r["species"], r["endpoint"]): r["selected_family"]
                for r in tables["goal036_conventional_selection"]}
    return receipt, thresholds, selected


def validate_prediction_file(path, expected_sha, species):
    require(sha(path) == expected_sha, "closed prediction file changed")
    with np.load(path, allow_pickle=False) as z:
        required = {"grid_cell_id", "patch", "primary_scores", "sensitivity_scores", "primary_thresholds",
                    "sensitivity_thresholds", "map_grid_cell_id", "primary_map_scores", "sensitivity_map_scores"}
        require(set(z.files) == required, "closed prediction array inventory changed")
        arrays = {name: z[name].copy() for name in z.files}
    cells = arrays["grid_cell_id"]
    require(cells.ndim == 1 and cells.dtype.kind == "U" and len(set(cells.tolist())) == len(cells), "closed held identities invalid")
    require(arrays["patch"].shape == cells.shape, "closed patch alignment failed")
    for name in ("primary_scores", "sensitivity_scores"):
        a = arrays[name]
        require(a.shape == (7, 3, len(cells)) and a.dtype == np.float64 and np.isfinite(a).all()
                and ((a >= 0) & (a <= 1)).all(), "closed held score inventory invalid")
    for name in ("primary_thresholds", "sensitivity_thresholds"):
        require(arrays[name].shape == (7, 3) and np.isfinite(arrays[name]).all(), "closed threshold inventory invalid")
    map_cells = arrays["map_grid_cell_id"]
    require(map_cells.shape == (71023,) and map_cells.dtype.kind == "U" and len(set(map_cells.tolist())) == 71023,
            "closed map domain invalid")
    for name in ("primary_map_scores", "sensitivity_map_scores"):
        a = arrays[name]
        require(a.shape == (3, 71023) and a.dtype == np.float64 and np.isfinite(a).all()
                and ((a >= 0) & (a <= 1)).all(), "closed map scores invalid")
    if species == "thylogale_billardierii":
        for suffix in ("scores", "thresholds", "map_scores"):
            require(np.array_equal(arrays["primary_" + suffix], arrays["sensitivity_" + suffix]),
                    "Thylogale end-to-end negative control failed: " + suffix)
    return arrays


def validate_normalized_primary(arrays, thresholds, selected):
    """Compare actual probabilities and identities before opening responses."""
    for species, a in arrays.items():
        with np.load(BASELINE / "inputs" / f"{species}.npz", allow_pickle=False) as z:
            original_cells = z["grid_cell_id"].copy()
            original_patch = z["patch"].copy()
        require(set(original_cells.tolist()) == set(a["grid_cell_id"].tolist())
                and len(original_cells) == len(a["grid_cell_id"]), "primary held membership changed")
        lookup = {str(cell): index for index, cell in enumerate(original_cells)}
        indices = np.asarray([lookup[str(cell)] for cell in a["grid_cell_id"]])
        require(np.array_equal(a["patch"], original_patch[indices]), "primary held patch membership changed")
        with np.load(BASELINE / "predictions/averaged" / f"{species}.npz", allow_pickle=False) as z:
            neural, conventional = z["neural_mean"].copy(), z["conventional_mean"].copy()
        for ei, endpoint in enumerate(ENDPOINTS):
            for mi, method in enumerate(METHODS):
                if mi < 2:
                    score = neural[ei, BASE_NEURAL.index(method), indices]
                    original_method = method
                else:
                    family = selected[species, endpoint]
                    score = conventional[ei, BASE_CONVENTIONAL.index(family), indices]
                    original_method = "conventional/" + family
                require(np.array_equal(a["primary_scores"][ei, mi], score), "primary held probabilities changed")
                require(a["primary_thresholds"][ei, mi] == thresholds[species, endpoint, original_method],
                        "primary frozen threshold changed")


def validate_closure(private=PRIVATE):
    closure = verified_receipt(private / "prediction-closure.json")
    require(closure.get("status") == "accepted" and closure.get("outer_held_response_labels_read") == 0,
            "complete pre-response prediction closure required")
    require(closure.get("target_physical_fits") == 8125 and closure.get("smoke_physical_fits") == 14
            and closure.get("recovery_physical_fits") == 200, "fit inventory incomplete")
    require(closure.get("assessment_source_sha256") == sha(Path(__file__))
            and closure.get("metrics_source_sha256") == sha(ROOT / "scripts/tasmania_pseudoabsence_metrics.py"),
            "scoring source changed after closure")
    require(closure.get("baseline_receipt_digest") == BASE_RECEIPT_DIGEST, "primary baseline binding changed")
    roles = {"neural_inner", "neural_outer", "conventional_inner", "conventional_outer",
             "neural_smoke", "conventional_smoke", "recovery"}
    require(len(closure.get("source_closures", [])) == len(roles)
            and {r.get("role") for r in closure["source_closures"]} == roles,
            "complete source-closure role inventory required")
    for source in closure["source_closures"]:
        path = (ROOT / source["path"]).resolve()
        require(ROOT in path.parents and sha(path) == source["sha256"], "fit closure changed")
    collector_path = ROOT / "scripts/tasmania_pseudoabsence_collect.py"
    require(closure.get("collector_source_sha256") == sha(collector_path), "collector changed after closure")
    # The collector reconciles real leaf/attempt inventories, source model and
    # prediction bytes, and both map means. Literal fit counters alone do not
    # qualify a panel for response access.
    from tasmania_pseudoabsence_collect import verify_closed_sources
    verify_closed_sources(closure, private=private)
    records = closure["files"]
    require(len(records) == 8 and {r["species"] for r in records} == set(SPECIES), "incomplete species closure")
    arrays = {}
    for record in records:
        path = private / "predictions" / (record["species"] + ".npz")
        arrays[record["species"]] = validate_prediction_file(path, record["sha256"], record["species"])
    require(sum(len(a["grid_cell_id"]) for a in arrays.values()) == 1672, "held row inventory changed")
    return closure, arrays


def open_held_response_once(closure, arrays, private=PRIVATE):
    allowlist = {(sp, str(cell)) for sp, a in arrays.items() for cell in a["grid_cell_id"]}
    intent = {"schema_version": "tasmania-sensitivity-response-access-intent-v1", "started_at": now(),
              "prediction_closure_digest": closure["receipt_digest"], "response_sha256": RESPONSE_SHA,
              "expected_held_rows": 1672, "planned_canonical_file_opens": 3,
              "planned_integrity_hash_passes": 2, "planned_response_parses": 1}
    write_new_json(private / "response-access-intent.json", intent)
    require(sha(RESPONSE) == RESPONSE_SHA, "canonical response changed")
    rows = {}
    with RESPONSE.open(newline="") as stream:
        header = next(csv.reader([stream.readline()]))
        require(header[:2] == ["species_id", "grid_cell_id"], "response identity prefix changed")
        for line in stream:
            species, cell, _ = line.split(",", 2)
            key = (species, cell)
            if key not in allowlist:
                continue
            require(key not in rows, "duplicate held response identity")
            row = dict(zip(header, next(csv.reader([line])), strict=True))
            require(row["outer_role"] == "test", "response split changed")
            rows[key] = row
    require(set(rows) == allowlist and sha(RESPONSE) == RESPONSE_SHA, "opened held response inventory changed")
    snapshot = write_new_json(private / "held-response-snapshot.json", {
        "schema_version": "tasmania-sensitivity-held-response-snapshot-v1",
        "prediction_closure_digest": closure["receipt_digest"], "response_sha256": RESPONSE_SHA,
        "rows": [{key: row[key] for key in ("species_id", "grid_cell_id", "microcluster", "pa", "pa_type")}
                 for _, row in sorted(rows.items())],
    })
    access = write_new_json(private / "response-access.json", {**intent, "completed_at": now(),
                            "canonical_file_opens": 3, "integrity_hash_passes": 2,
                            "response_parses": 1, "held_rows_parsed": len(rows), "training_rows_parsed": 0,
                            "private_snapshot_receipt_digest": snapshot["receipt_digest"]})
    return rows, access


def write_csv(path, rows):
    require(rows, "empty aggregate output")
    fields = list(rows[0])
    with Path(path).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: "NA" if value is None else value for key, value in row.items()} for row in rows)


def score(private=PRIVATE):
    # Refuse stale or partial outputs before any response parse; no overwrite
    # or automatic retry can turn a failed assessment into a clean first run.
    for name in ("response-access-intent.json", "response-access.json", "held-response-snapshot.json"):
        require(not (private / name).exists(), "prior response-access evidence exists: " + name)
    for name in ("assessment.json", "paired-performance.csv", "source-specificity.csv",
                 "paired-contrasts.csv", "map-comparison.csv", "held-source-counts.csv"):
        require(not (EVIDENCE / name).exists(), "prior assessment output exists: " + name)
    closure, arrays = validate_closure(private)
    primary_receipt, thresholds, selected = baseline()
    validate_normalized_primary(arrays, thresholds, selected)
    primary_index = {(r["species"], r["endpoint"], r["model"]): r for r in primary_receipt["metrics"] if r["scope"] == "pooled"}
    rows, access = open_held_response_once(closure, arrays, private)
    performance, source_rows, maps, contrast_rows, counts = [], [], [], [], []
    for species in SPECIES:
        a = arrays[species]
        records = [rows[species, str(cell)] for cell in a["grid_cell_id"]]
        require(all(r["microcluster"] == patch for r, patch in zip(records, a["patch"])), "held patch identity changed")
        labels = np.asarray([int(r["pa"]) for r in records], dtype=np.int8)
        sources = np.asarray([r["pa_type"] for r in records])
        counts.append({"species": species, "rows": len(labels), "positive": int(labels.sum()),
                       "survey_supported_absence": int(np.sum(sources == "survey_supported_absence")),
                       "pseudoabsence": int(np.sum(sources == "pseudoabsence"))})
        for ei, endpoint in enumerate(ENDPOINTS):
            metric_cache = {}
            for mi, method in enumerate(METHODS):
                before = binary_metrics(labels, a["primary_scores"][ei, mi], a["primary_thresholds"][ei, mi])
                after = binary_metrics(labels, a["sensitivity_scores"][ei, mi], a["sensitivity_thresholds"][ei, mi])
                original_method = method if mi < 2 else "conventional/" + selected[species, endpoint]
                accepted = primary_index[species, endpoint, original_method]
                require(all(before[k] == accepted[k] for k in ("n", "tp", "tn", "fp", "fn", "threshold", "roc_auc", "tss", "mcc")),
                        "primary metrics failed exact replay")
                row = {"species": species, "endpoint": endpoint, "method": method,
                       "selected_conventional_family": selected[species, endpoint] if mi == 2 else None,
                       "n": len(labels), "n_positive": int(labels.sum()), "n_negative": int(len(labels) - labels.sum())}
                for metric in ("threshold", "roc_auc", "tss", "mcc"):
                    row.update({"primary_" + metric: before[metric], "sensitivity_" + metric: after[metric],
                                "delta_" + metric: after[metric] - before[metric]})
                performance.append(row)
                metric_cache[method] = (before, after)
                bs = source_specificity(labels, sources, a["primary_scores"][ei, mi], before["threshold"])
                ss = source_specificity(labels, sources, a["sensitivity_scores"][ei, mi], after["threshold"])
                for source in bs:
                    b, s = bs[source], ss[source]
                    source_rows.append({"species": species, "endpoint": endpoint, "method": method, "absence_source": source,
                                        "denominator": b["denominator"], "primary_true_negative": b["true_negative"],
                                        "sensitivity_true_negative": s["true_negative"], "primary_specificity": b["specificity"],
                                        "sensitivity_specificity": s["specificity"], "delta_specificity": None if not b["denominator"] else s["specificity"] - b["specificity"]})
            for comparator in ("target_only_resmlp", "selected_conventional"):
                for metric in ("roc_auc", "tss", "mcc"):
                    primary_delta = metric_cache["multihead_full_finetune"][0][metric] - metric_cache[comparator][0][metric]
                    sensitivity_delta = metric_cache["multihead_full_finetune"][1][metric] - metric_cache[comparator][1][metric]
                    contrast_rows.append({"species": species, "endpoint": endpoint, "contrast": "multihead_full_finetune_minus_" + comparator,
                                          "metric": metric, "primary_contrast": primary_delta, "sensitivity_contrast": sensitivity_delta,
                                          "change_in_contrast": sensitivity_delta - primary_delta})
        for mi, method in enumerate(METHODS):
            maps.append({"species": species, "endpoint": "fraction100/full", "method": method,
                         **map_summary(a["map_grid_cell_id"], a["primary_map_scores"][mi], a["sensitivity_map_scores"][mi])})
    require(len(performance) == 168 and len(source_rows) == len(contrast_rows) == 336 and len(maps) == 24, "aggregate result inventory drift")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    tables = {"paired-performance.csv": performance, "source-specificity.csv": source_rows,
              "paired-contrasts.csv": contrast_rows, "map-comparison.csv": maps, "held-source-counts.csv": counts}
    for name, table in tables.items():
        write_csv(EVIDENCE / name, table)
    return write_new_json(EVIDENCE / "assessment.json", {
        "schema_version": "tasmania-pseudoabsence-sensitivity-assessment-v1", "success": True,
        "prediction_closure_digest": closure["receipt_digest"], "response_access_digest": access["receipt_digest"],
        "baseline_receipt_digest": BASE_RECEIPT_DIGEST, "completed_at": now(),
        "counts": {"species": 8, "endpoints": 7, "methods": 3, "paired_performance_rows": 168, "map_pairs": 24, "held_rows": 1672},
        "files": [{"path": str((EVIDENCE / name).relative_to(ROOT)), "sha256": sha(EVIDENCE / name)} for name in tables],
        "outer_held_response_parses": 1, "canonical_response_file_opens": 3,
        "canonical_response_integrity_hash_passes": 2,
        "private_response_snapshot_digest": access["private_snapshot_receipt_digest"],
        "interpretation": "paired descriptive sensitivity conditional on the frozen evaluation panel and conventional selections",
        "privacy": {"aggregate_only": True, "tracked_response_rows": False, "tracked_coordinates": False}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("score", "validate"))
    args = parser.parse_args()
    if args.command == "score":
        print(json.dumps(score(), sort_keys=True))
    else:
        closure, _ = validate_closure()
        print(json.dumps({"status": "accepted", "closure_digest": closure["receipt_digest"]}))
