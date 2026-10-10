"""Render the 24 approved full-data map pairs from closed private predictions."""
from __future__ import annotations

import csv
from pathlib import Path
import subprocess

import numpy as np

from tasmania_pseudoabsence_assessment import (
    EVIDENCE, METHODS, PRIVATE, ROOT, SPECIES, read, require, sha,
    verified_receipt, write_new_json,
)


def render():
    assessment = verified_receipt(EVIDENCE / "assessment.json")
    closure = verified_receipt(PRIVATE / "prediction-closure.json")
    require(assessment["success"] and assessment["prediction_closure_digest"] == closure["receipt_digest"],
            "accepted assessment required before map rendering")
    foundation = ROOT / "config/modeling_foundation_preflight.json"
    require(sha(foundation) == "35b6ab72ba2b8ba2267dc82179987bfffaa3f339d64272d68012444e46285f00", "map foundation changed")
    binding = read(foundation)["bindings"]["goal024_map"]
    source = ROOT / binding["path"]
    require(sha(source) == binding["sha256"], "frozen map domain changed")
    with source.open() as stream:
        coordinates = {row["grid_cell_id"]: (float(row["centroid_lon"]), float(row["centroid_lat"]))
                       for row in csv.DictReader(stream)}
    require(len(coordinates) == 71023, "map coordinate domain incomplete")
    index = {row["species"]: row for row in closure["files"]}
    exports = PRIVATE / "map-render-inputs"
    destination = EVIDENCE / "maps"
    exports.mkdir(exist_ok=True)
    destination.mkdir(exist_ok=True)
    renderer = ROOT / "scripts/plot_tasmania_pseudoabsence.R"
    outputs = []
    for species in SPECIES:
        path = PRIVATE / "predictions" / f"{species}.npz"
        require(sha(path) == index[species]["sha256"], "closed map predictions changed")
        with np.load(path, allow_pickle=False) as values:
            cells = values["map_grid_cell_id"]
            primary, sensitivity = values["primary_map_scores"], values["sensitivity_map_scores"]
        require(len(cells) == len(set(cells.tolist())) == 71023 and set(cells.tolist()) == set(coordinates),
                "map identities differ from frozen coordinate domain")
        require(primary.shape == sensitivity.shape == (3, 71023), "map probability shape invalid")
        require(np.isfinite(primary).all() and np.isfinite(sensitivity).all(), "nonfinite map probability")
        exported = exports / f"{species}.csv"
        with exported.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["longitude", "latitude"] + [f"primary_{i}" for i in range(3)] + [f"sensitivity_{i}" for i in range(3)])
            writer.writerows([*coordinates[str(cell)], *primary[:, i], *sensitivity[:, i]] for i, cell in enumerate(cells))
        subprocess.run(["Rscript", str(renderer), str(exported), species, str(destination / species)], check=True)
        for extension in ("pdf", "png"):
            product = destination / f"{species}.{extension}"
            outputs.append({"path": str(product.relative_to(ROOT)), "sha256": sha(product)})
    return write_new_json(EVIDENCE / "map-rendering.json", {
        "schema_version": "tasmania-sensitivity-map-rendering-v1", "success": True,
        "assessment_receipt_digest": assessment["receipt_digest"],
        "prediction_closure_digest": closure["receipt_digest"],
        "export_script_sha256": sha(__file__), "renderer_sha256": sha(renderer),
        "map_source_sha256": binding["sha256"], "pairs": 24, "domain_cells": 71023,
        "methods": list(METHODS), "probability_limits": [0, 1], "difference_limits": [-1, 1],
        "difference": "sensitivity minus primary", "files": outputs,
        "private_coordinates_exported_to_tracked_files": False,
    })


if __name__ == "__main__":
    print(render()["receipt_digest"])
