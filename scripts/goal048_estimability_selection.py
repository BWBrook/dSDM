"""Apply the frozen Goal 048 estimability gates to immutable region rankings.

The aggregate census is used only to reconstruct distinct effort-species
richness and focal membership masks.  No occurrence rows, coordinates, or
model outcomes are written by this stage.  The response-free ranking is read
in its existing order and is never rescored or reordered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import html
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import covers, points
from shapely.geometry import mapping

import goal048_response_free_scoring as scoring


REGIONS = scoring.REGIONS
ROLES = ("supported", "edge", "mosaic")
PRIVATE_ROOT = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze")
CENSUS_ROOT = PRIVATE_ROOT / "census"
RESPONSE_FREE_ROOT = PRIVATE_ROOT / "response_free"
RECEIPT_PATH = Path("evidence/seawfb_bioregional_freeze/goal048/estimability_selection_receipt.json")
RESOLUTION_PATH = Path("evidence/seawfb_bioregional_freeze/goal048/design_resolution.json")
SVG_PATH = Path("evidence/seawfb_bioregional_freeze/goal048/selected_holdouts.svg")
DOMAIN_PATH = PRIVATE_ROOT / "domain_cells.csv"
LEDGER_PATH = RESPONSE_FREE_ROOT / "cell_region_ledger.parquet"
LEDGER_RECEIPT_PATH = RESPONSE_FREE_ROOT / "cell_region_ledger_receipt.json"
METRICS_PATH = RESPONSE_FREE_ROOT / "candidate_metrics.json"
RANKED_PATH = RESPONSE_FREE_ROOT / "ranked_structurally_feasible_sets.json"
CENSUS_PROGRESS_PATH = Path("evidence/seawfb_bioregional_freeze/goal048/aggregate_census_progress.json")
PREREQUISITE_PATH = Path("metadata/goal048_prerequisite_freeze.json")
ROLE_PATH = PRIVATE_ROOT / "role_freeze.json"

CELL_PATTERN = re.compile(r"^r[0-9]{4,}c[0-9]{4,}$")


class SelectionError(ValueError):
    """Raised when a frozen Goal 048 input or invariant is invalid."""


SELECTED_REGIONS = ("NCP", "SEH", "NNC")
SELECTED_REGION_SET = tuple(sorted(SELECTED_REGIONS))
SELECTED_ROLES = {"supported": "NCP", "edge": "SEH", "mosaic": "NNC"}
RESOLUTION_SCHEMA = "goal048-design-resolution-v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(_json_safe(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_config(root: Path) -> dict[str, Any]:
    config = json.loads((root / scoring.CONFIG_PATH).read_text())
    effort = config["effort_support"]
    estimability = config["estimability"]
    buffer = config["buffer"]
    ambiguity = config["joint_selection"]["ambiguity"]
    expected = {
        "primary_x": 10,
        "evaluation_only_sensitivity_x": 20,
        "candidate_region_minimum_x10_effort_cells": 1000,
        "evaluation_minimum_presence_cells_per_target_region": 30,
        "evaluation_minimum_x10_background_cells_per_target_region": 100,
        "evaluation_minimum_50km_tiles_per_class": 4,
        "training_minimum_presence_cells_per_target": 200,
        "training_minimum_x10_background_cells_per_target": 500,
        "training_minimum_spatial_folds_per_class": 4,
        "common_primary_target_panel_minimum": 20,
    }
    actual = {
        "primary_x": effort["primary_x"],
        "evaluation_only_sensitivity_x": effort["evaluation_only_sensitivity_x"],
        **{key: estimability[key] for key in expected if key in estimability},
    }
    if actual != expected:
        raise SelectionError("estimability or X threshold drift")
    if effort.get("require_x20_subset_of_x10") is not True:
        raise SelectionError("X20 subset contract drift")
    if buffer.get("external_training_exclusion_km") != 50.0 or buffer.get("applies_to_all_three_holdouts_simultaneously") is not True:
        raise SelectionError("buffer contract drift")
    if ambiguity.get("minimum_role_score_margin_below") != 0.01 or ambiguity.get("summed_role_score_margin_below") != 0.02:
        raise SelectionError("ambiguity threshold drift")
    if config["domain"]["prospective_region_codes"] != REGIONS:
        raise SelectionError("candidate region order drift")
    return config


def _load_roles(root: Path) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    value = json.loads((root / ROLE_PATH).read_text())
    rows = value.get("rows")
    if value.get("row_count") != 100 or not isinstance(rows, list) or len(rows) != 100:
        raise SelectionError("role freeze identity drift")
    if value.get("role_counts") != {"auxiliary": 71, "effort": 96, "target": 71}:
        raise SelectionError("role freeze counts drift")
    names = [str(row.get("name")) for row in rows]
    if len(set(names)) != 100 or any(not row.get("name") for row in rows):
        raise SelectionError("role freeze names drift")
    effort = [name for name, row in zip(names, rows) if row.get("effort") is True]
    targets = [name for name, row in zip(names, rows) if row.get("target") is True]
    auxiliary = [name for name, row in zip(names, rows) if row.get("auxiliary") is True]
    if len(effort) != 96 or len(targets) != 71 or len(auxiliary) != 71:
        raise SelectionError("role partitions drift")
    return effort, targets, auxiliary, value


def _load_ledger(root: Path) -> pd.DataFrame:
    receipt = json.loads((root / LEDGER_RECEIPT_PATH).read_text())
    path = root / LEDGER_PATH
    if receipt.get("row_count") != 1_144_286 or not path.is_file() or _sha(path) != receipt.get("ledger_sha256"):
        raise SelectionError("cell-region ledger receipt drift")
    ledger = pd.read_parquet(path)
    required = {"cell_id", "row", "column", "longitude", "latitude", "region"}
    if len(ledger) != 1_144_286 or not required <= set(ledger) or ledger.cell_id.duplicated().any():
        raise SelectionError("cell-region ledger schema drift")
    ledger = ledger.sort_values("cell_id", kind="mergesort").reset_index(drop=True)
    if int(ledger.region.notna().sum()) != 756_836 or int(ledger.region.isna().sum()) != 387_450:
        raise SelectionError("cell-region geography invariant drift")
    return ledger


def _validate_census(root: Path, effort: Sequence[str], roles: Mapping[str, Any]) -> dict[str, Any]:
    progress = json.loads((root / CENSUS_PROGRESS_PATH).read_text())
    prerequisite = json.loads((root / PREREQUISITE_PATH).read_text())
    if progress.get("status") != "complete" or progress.get("planned_species") != 96 or progress.get("completed_species") != 96:
        raise SelectionError("census is not complete")
    if progress.get("occurrence_rows_downloaded") != 0 or progress.get("model_outcome_counter") != 0:
        raise SelectionError("census outcome/raw-row counters are non-zero")
    expected_exclusions = [
        {"name": row["name"], "status": "not_queried_frozen_role_exclusion", "reason": row.get("reason", "")}
        for row in roles["rows"] if row.get("effort") is not True
    ]
    if len(expected_exclusions) != 4 or progress.get("frozen_role_exclusions") != expected_exclusions:
        raise SelectionError("census frozen exclusions drift")
    domain = pd.read_csv(root / DOMAIN_PATH, usecols=["cell_id"], dtype={"cell_id": str})
    if len(domain) != 1_144_286 or domain.cell_id.duplicated().any():
        raise SelectionError("census domain identity drift")
    domain_ids = set(domain.cell_id)
    checkpoint_dir = root / CENSUS_ROOT / "checkpoints"
    checkpoints = sorted(checkpoint_dir.glob("*.json"))
    if [path.name for path in checkpoints] != [f"{index:03d}.json" for index in range(96)]:
        raise SelectionError("census checkpoints are not exactly 96 canonical entries")
    checkpoint_hashes = [_sha(path) for path in checkpoints]
    if progress.get("checkpoint_inventory_sha256") != _digest(checkpoint_hashes):
        raise SelectionError("census checkpoint inventory drift")
    prerequisite_sha = prerequisite.get("joint_sha256")
    totals = {"total_count": 0, "facet_group_count": 0, "retained_species_cell_count": 0}
    cells_by_species: dict[str, list[str]] = {}
    effort_index = {name: index for index, name in enumerate(effort)}
    for index, name in enumerate(effort):
        checkpoint = json.loads(checkpoints[index].read_text())
        if checkpoint.get("index") != index or checkpoint.get("species") != name or checkpoint.get("status") != "passed":
            raise SelectionError("census checkpoint identity drift")
        if checkpoint.get("prerequisite_joint_sha256") != prerequisite_sha or checkpoint.get("role_receipt_sha256") != _sha(root / ROLE_PATH):
            raise SelectionError("census checkpoint authority drift")
        counts = {key: checkpoint.get(key) for key in ("total_count", "facet_count_sum", "facet_group_count")}
        if counts["total_count"] != counts["facet_count_sum"] or checkpoint.get("count_conservation_sha256") != _digest(counts):
            raise SelectionError("census count conservation drift")
        if not isinstance(counts["facet_group_count"], int) or counts["facet_group_count"] < 0:
            raise SelectionError("census facet-group count drift")
        expected = root / checkpoint["private_cell_receipt"]
        canary = root / PRIVATE_ROOT / "canary_species_cells.json"
        if index == effort_index.get("Acanthiza pusilla"):
            expected = canary
        if expected != root / checkpoint["private_cell_receipt"] or not expected.is_file() or _sha(expected) != checkpoint.get("private_cell_receipt_sha256"):
            raise SelectionError("census private receipt binding drift")
        value = json.loads(expected.read_text())
        cells = value.get("cells")
        if value.get("species") != name or not isinstance(cells, list) or cells != sorted(set(cells)):
            raise SelectionError("census private cell canonicality drift")
        if any(not isinstance(cell, str) or CELL_PATTERN.fullmatch(cell) is None for cell in cells) or not set(cells) <= domain_ids:
            raise SelectionError("census private cell domain drift")
        if len(cells) != checkpoint.get("retained_species_cell_count"):
            raise SelectionError("census retained-cell count drift")
        cells_by_species[name] = cells
        totals["total_count"] += counts["total_count"]
        totals["facet_group_count"] += counts["facet_group_count"]
        totals["retained_species_cell_count"] += checkpoint["retained_species_cell_count"]
    if totals["total_count"] != progress.get("cumulative_total_count") or totals["facet_group_count"] != progress.get("cumulative_facet_groups") or totals["retained_species_cell_count"] != progress.get("cumulative_retained_species_cells"):
        raise SelectionError("census cumulative totals drift")
    if len(cells_by_species) != 96:
        raise SelectionError("census species accounting drift")
    return {"progress": progress, "cells_by_species": cells_by_species, "domain_ids": domain_ids, "checkpoint_hashes": checkpoint_hashes}


def load_frozen_inputs(root: Path) -> dict[str, Any]:
    """Load and validate every frozen input needed by the gate stage."""
    config = _read_config(root)
    effort, targets, auxiliary, role_value = _load_roles(root)
    census = _validate_census(root, effort, role_value)
    ledger = _load_ledger(root)
    ranked = json.loads((root / RANKED_PATH).read_text())
    candidate = json.loads((root / METRICS_PATH).read_text())
    run_identity = scoring._run_identity(root)
    if ranked.get("run_identity") != run_identity or candidate.get("run_identity") != run_identity:
        raise SelectionError("response-free scoring identity drift")
    ranked_rows = ranked.get("ranked")
    if not isinstance(ranked_rows, list) or len(ranked_rows) != 147:
        raise SelectionError("immutable ranked-set count drift")
    seen: set[tuple[str, ...]] = set()
    for row in ranked_rows:
        regions = tuple(sorted(row.get("regions", [])))
        if len(regions) != 3 or regions in seen or any(code not in REGIONS for code in regions):
            raise SelectionError("immutable ranked-set identity drift")
        seen.add(regions)
        if not row.get("structurally_valid") or not row.get("role_feasible"):
            raise SelectionError("ranked set contains a non-feasible context")
    metric_rows = candidate.get("rows")
    if not isinstance(metric_rows, list) or [row.get("region") for row in metric_rows] != REGIONS:
        raise SelectionError("candidate metric region order drift")
    metric_map = {row["region"]: row for row in metric_rows}
    for code in REGIONS:
        row = metric_map[code]
        if float(row["predictor_complete_fraction"]) < 0.95 or int(row["domain_cells"]) < 5000:
            raise SelectionError(f"candidate predictor/land gate failed: {code}")
    config_hashes = {
        "config": _sha(root / scoring.CONFIG_PATH),
        "domain_cells": _sha(root / DOMAIN_PATH),
        "ibra": _sha(root / scoring.IBRA_PATH),
        "nvis": _sha(root / scoring.NVIS_PATH),
        "predictors": _sha(root / scoring.PREDICTOR_PATH),
        "role_freeze": _sha(root / ROLE_PATH),
        "census_progress": _sha(root / CENSUS_PROGRESS_PATH),
        "ledger": _sha(root / LEDGER_PATH),
        "ledger_receipt": _sha(root / LEDGER_RECEIPT_PATH),
        "candidate_metrics": _sha(root / METRICS_PATH),
        "ranked_sets": _sha(root / RANKED_PATH),
        "design_resolution": _sha(root / RESOLUTION_PATH),
    }
    return {
        "config": config,
        "effort": effort,
        "targets": targets,
        "auxiliary": auxiliary,
        "roles": role_value,
        "census": census,
        "ledger": ledger,
        "ranked": ranked_rows,
        "metric_map": metric_map,
        "run_identity": run_identity,
        "input_sha256": config_hashes,
    }


def x_background_mask(presence: np.ndarray, richness: np.ndarray, threshold: int) -> np.ndarray:
    """Return focal-excluded effort-supported background cells."""
    presence = np.asarray(presence, dtype=bool)
    richness = np.asarray(richness)
    if presence.ndim != 1 or richness.shape != presence.shape or np.any(richness < 0):
        raise SelectionError("presence/richness shape or value drift")
    return (~presence) & (richness >= int(threshold))


def anchored_tiles(xy: np.ndarray, mask: np.ndarray, tile_size_m: float = 50_000.0) -> set[tuple[int, int]]:
    """Return fixed EPSG:3577 tiles anchored at the projected origin."""
    xy = np.asarray(xy, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) != len(mask) or tile_size_m <= 0:
        raise SelectionError("tile inputs are malformed")
    if not np.isfinite(xy).all():
        raise SelectionError("tile coordinates are non-finite")
    selected = xy[mask]
    if len(selected) == 0:
        return set()
    tiles = np.floor(selected / tile_size_m).astype(np.int64)
    return {(int(row[0]), int(row[1])) for row in tiles}


def region_gate_metrics(
    region_mask: np.ndarray,
    presence: np.ndarray,
    x10_background: np.ndarray,
    x20_background: np.ndarray,
    xy: np.ndarray,
    training_mask: np.ndarray,
    thresholds: Mapping[str, int],
) -> dict[str, Any]:
    """Compute aggregate evaluation/training gates for one target and region."""
    region_mask = np.asarray(region_mask, dtype=bool)
    presence = np.asarray(presence, dtype=bool)
    x10_background = np.asarray(x10_background, dtype=bool)
    x20_background = np.asarray(x20_background, dtype=bool)
    training_mask = np.asarray(training_mask, dtype=bool)
    if not (len(region_mask) == len(presence) == len(x10_background) == len(x20_background) == len(training_mask) == len(xy)):
        raise SelectionError("gate vector length drift")
    evaluation_presence = region_mask & presence
    evaluation_x10 = region_mask & x10_background
    evaluation_x20 = region_mask & x20_background
    training_presence = training_mask & presence
    training_x10 = training_mask & x10_background
    minimum_eval = thresholds["evaluation_minimum_50km_tiles_per_class"]
    minimum_train = thresholds["training_minimum_spatial_folds_per_class"]
    result = {
        "evaluation_presence_cells": int(evaluation_presence.sum()),
        "evaluation_x10_background_cells": int(evaluation_x10.sum()),
        "evaluation_x20_background_cells": int(evaluation_x20.sum()),
        "evaluation_presence_tiles": len(anchored_tiles(xy, evaluation_presence)),
        "evaluation_x10_background_tiles": len(anchored_tiles(xy, evaluation_x10)),
        "evaluation_x20_background_tiles": len(anchored_tiles(xy, evaluation_x20)),
        "training_presence_cells": int(training_presence.sum()),
        "training_x10_background_cells": int(training_x10.sum()),
        "training_presence_tiles": len(anchored_tiles(xy, training_presence)),
        "training_x10_background_tiles": len(anchored_tiles(xy, training_x10)),
    }
    result["evaluation_pass"] = bool(
        result["evaluation_presence_cells"] >= thresholds["evaluation_minimum_presence_cells_per_target_region"]
        and result["evaluation_x10_background_cells"] >= thresholds["evaluation_minimum_x10_background_cells_per_target_region"]
        and result["evaluation_presence_tiles"] >= minimum_eval
        and result["evaluation_x10_background_tiles"] >= minimum_eval
    )
    result["training_pass"] = bool(
        result["training_presence_cells"] >= thresholds["training_minimum_presence_cells_per_target"]
        and result["training_x10_background_cells"] >= thresholds["training_minimum_x10_background_cells_per_target"]
        and result["training_presence_tiles"] >= minimum_train
        and result["training_x10_background_tiles"] >= minimum_train
    )
    result["x20_evaluation_pass_diagnostic"] = bool(
        result["evaluation_presence_cells"] >= thresholds["evaluation_minimum_presence_cells_per_target_region"]
        and result["evaluation_x20_background_cells"] >= thresholds["evaluation_minimum_x10_background_cells_per_target_region"]
        and result["evaluation_presence_tiles"] >= minimum_eval
        and result["evaluation_x20_background_tiles"] >= minimum_eval
    )
    return result


def _tile_count_for_indices(tile_codes: np.ndarray, indices: np.ndarray, retained: np.ndarray | None = None) -> int:
    """Count distinct fixed tiles, inspecting only cells in the class."""
    indices = np.asarray(indices, dtype=np.int64)
    if retained is not None:
        indices = indices[np.asarray(retained, dtype=bool)[indices]]
    return int(np.unique(tile_codes[indices]).size) if len(indices) else 0


def filter_immutable_ranked(ranked: Sequence[Mapping[str, Any]], gate_by_regions: Mapping[tuple[str, ...], Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Filter in input order; no score, role, or ranking field is changed."""
    filtered = []
    for rank, row in enumerate(ranked, 1):
        regions = tuple(sorted(row["regions"]))
        gate = gate_by_regions.get(regions)
        if gate is None:
            raise SelectionError("missing gate result for ranked set")
        if gate.get("passes"):
            copied = dict(row)
            copied["immutable_rank"] = rank
            filtered.append(copied)
    return filtered


def ambiguity_summary(feasible: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> dict[str, Any]:
    """Compute signed top-minus-runner-up margins under the frozen AND rule."""
    ambiguity = config["joint_selection"]["ambiguity"]
    if not feasible:
        return {"feasible_count": 0, "first": None, "second": None, "minimum_margin": None, "sum_margin": None, "ambiguous": False}
    first = feasible[0]
    second = feasible[1] if len(feasible) > 1 else None
    if second is None:
        return {"feasible_count": len(feasible), "first": first, "second": None, "minimum_margin": None, "sum_margin": None, "ambiguous": False}
    min_margin = float(first["minimum_role_score"]) - float(second["minimum_role_score"])
    sum_margin = float(first["sum_role_scores"]) - float(second["sum_role_scores"])
    different = tuple(sorted(first["regions"])) != tuple(sorted(second["regions"]))
    return {
        "feasible_count": len(feasible),
        "first": first,
        "second": second,
        "minimum_margin": min_margin,
        "sum_margin": sum_margin,
        "ambiguous": bool(different and min_margin < ambiguity["minimum_role_score_margin_below"] and sum_margin < ambiguity["summed_role_score_margin_below"]),
    }


def x20_panel_diagnostic_summary(
    target_metrics: Mapping[str, Mapping[str, Mapping[str, Any]]],
    panel: Sequence[str],
    codes: Sequence[str],
) -> dict[str, int]:
    """Summarize X20 sensitivity for the frozen X10 common panel only."""
    values = [target_metrics[species][code] for species in panel for code in codes]
    passing_targets = sum(
        all(bool(target_metrics[species][code]["x20_evaluation_pass_diagnostic"]) for code in codes)
        for species in panel
    )
    backgrounds = [int(value["evaluation_x20_background_cells"]) for value in values]
    return {
        "common_x10_panel_target_region_count": len(panel) * len(codes),
        "common_x10_panel_x20_diagnostic_pass_count": passing_targets,
        "common_x10_panel_x20_background_cells_min": min(backgrounds) if backgrounds else 0,
        "common_x10_panel_x20_background_cells_max": max(backgrounds) if backgrounds else 0,
    }


def _projected_xy(ledger: pd.DataFrame) -> np.ndarray:
    geometry = gpd.GeoSeries(points(ledger.longitude.to_numpy(), ledger.latitude.to_numpy()), crs=4326).to_crs(3577)
    return np.column_stack((geometry.x.to_numpy(), geometry.y.to_numpy()))


def _region_masks(
    region_masks: Mapping[str, np.ndarray],
    buffer_masks: Mapping[str, np.ndarray],
    codes: Sequence[str],
) -> tuple[Mapping[str, np.ndarray], np.ndarray]:
    masks = region_masks
    excluded = np.logical_or.reduce([buffer_masks[code] for code in codes])
    return masks, ~excluded


def _thresholds(config: Mapping[str, Any]) -> dict[str, int]:
    effort = config["effort_support"]
    values = config["estimability"]
    return {
        "x10": int(effort["primary_x"]),
        "x20": int(effort["evaluation_only_sensitivity_x"]),
        "evaluation_minimum_presence_cells_per_target_region": int(values["evaluation_minimum_presence_cells_per_target_region"]),
        "evaluation_minimum_x10_background_cells_per_target_region": int(values["evaluation_minimum_x10_background_cells_per_target_region"]),
        "evaluation_minimum_50km_tiles_per_class": int(values["evaluation_minimum_50km_tiles_per_class"]),
        "training_minimum_presence_cells_per_target": int(values["training_minimum_presence_cells_per_target"]),
        "training_minimum_x10_background_cells_per_target": int(values["training_minimum_x10_background_cells_per_target"]),
        "training_minimum_spatial_folds_per_class": int(values["training_minimum_spatial_folds_per_class"]),
    }


def _expected_resolution() -> dict[str, Any]:
    """Return the one explicit human resolution permitted by Goal 048."""
    return {
        "schema_version": RESOLUTION_SCHEMA,
        "decision_date": "2026-08-31",
        "authority": "Barry / Lab Lead",
        "selected_immutable_rank": 4,
        "selected_regions": list(SELECTED_REGIONS),
        "role_assignment": dict(SELECTED_ROLES),
        "comparison_to_rank_3": {
            "edge_score_gain": 0.0080645161,
            "mosaic_score_gain": 0.0714285714,
            "shared_supported_score_loss": 0.0054985337,
        },
        "reason": (
            "Select rank 4 because it gains 0.0080645161 on the environmental-edge role "
            "and 0.0714285714 on the fragmented/land-use-mosaic role versus rank 3, "
            "for a 0.0054985337 loss on the shared supported-transfer role. This "
            "transparent human resolution uses no occurrence magnitudes and was made "
            "before any model outcomes or model fitting."
        ),
    }


def _load_resolution(root: Path, feasible: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> dict[str, Any]:
    """Validate Barry's explicit resolution against the immutable top two."""
    path = root / RESOLUTION_PATH
    if not path.is_file():
        raise SelectionError("explicit design resolution is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SelectionError("explicit design resolution is not valid JSON") from exc
    expected = _expected_resolution()
    if value != expected:
        raise SelectionError("explicit design resolution does not match the authorised decision")
    if not summary.get("ambiguous") or len(feasible) < 2:
        raise SelectionError("explicit resolution requires two feasible ambiguous alternatives")
    first, second = feasible[0], feasible[1]
    if int(first.get("immutable_rank")) != 3 or int(second.get("immutable_rank")) != 4:
        raise SelectionError("explicit resolution is not against the audited rank-3/rank-4 alternatives")
    if tuple(sorted(first.get("regions", []))) != ("NCP", "NET", "SEH") or tuple(sorted(second.get("regions", []))) != SELECTED_REGION_SET:
        raise SelectionError("audited alternatives no longer match the explicit resolution")
    if tuple(sorted(value["selected_regions"])) != SELECTED_REGION_SET or value["role_assignment"] != SELECTED_ROLES:
        raise SelectionError("selected resolution region or role assignment drift")
    return value


def _svg_geometry_path(geometry: Any, transform: Any) -> str:
    """Serialize polygon boundaries in normalized SVG coordinates."""
    parts: list[str] = []
    geometry_mapping = mapping(geometry)

    def ring_path(ring: Sequence[Sequence[float]]) -> None:
        if not ring:
            return
        coords = [transform(float(x), float(y)) for x, y in ring]
        parts.append("M " + " ".join(f"{x:.3f},{y:.3f}" for x, y in coords) + " Z")

    def geometry_parts(value: Mapping[str, Any]) -> None:
        kind = value.get("type")
        coords = value.get("coordinates")
        if kind == "Polygon":
            for ring in coords:
                ring_path(ring)
        elif kind == "MultiPolygon":
            for polygon in coords:
                for ring in polygon:
                    ring_path(ring)
        elif kind == "GeometryCollection":
            for child in value.get("geometries", []):
                geometry_parts(child)

    geometry_parts(geometry_mapping)
    return " ".join(parts)


def write_selected_holdouts_svg(root: Path, resolution: Mapping[str, Any]) -> Path:
    """Write a deterministic boundary-only map from the official IBRA source."""
    if tuple(sorted(resolution.get("selected_regions", []))) != SELECTED_REGION_SET:
        raise SelectionError("cannot map an unapproved selected-region set")
    frame = gpd.read_file(root / scoring.IBRA_PATH).to_crs(3577)
    if len(frame) != 419 or frame["REG_CODE_7"].nunique() != 89:
        raise SelectionError("IBRA authority count drift while creating map")
    geometries: dict[str, Any] = {}
    names: dict[str, str] = {}
    for code in REGIONS:
        subset = frame.loc[frame["REG_CODE_7"] == code]
        if subset.empty:
            raise SelectionError(f"missing candidate region geometry: {code}")
        # This geometry is only for the human-readable map. All analytical
        # masks continue to use the unsimplified official geometry upstream.
        geometries[code] = scoring.make_valid(scoring.union_all(subset.geometry.array)).simplify(3_000.0, preserve_topology=True)
        region_names = sorted({str(value).strip() for value in subset["REG_NAME_7"] if str(value).strip()})
        if len(region_names) != 1:
            raise SelectionError(f"official region name is not unique: {code}")
        names[code] = region_names[0]
    envelope = scoring.union_all(list(geometries.values())).bounds
    min_x, min_y, max_x, max_y = map(float, envelope)
    width, height, margin = 1200.0, 760.0, 24.0
    scale = min((width - 2 * margin) / (max_x - min_x), (height - 2 * margin) / (max_y - min_y))
    used_width, used_height = (max_x - min_x) * scale, (max_y - min_y) * scale
    x_offset = (width - used_width) / 2.0
    y_offset = (height - used_height) / 2.0

    def transform(x: float, y: float) -> tuple[float, float]:
        return (x_offset + (x - min_x) * scale, height - (y_offset + (y - min_y) * scale))

    selected = set(resolution["selected_regions"])
    role_for = {region: role for role, region in resolution["role_assignment"].items()}
    colors = {"supported": "#2563a6", "edge": "#c2410c", "mosaic": "#27734d"}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">',
        '<title>Goal 048 IBRA7.1 outer-assessment design</title>',
        '<metadata>Display-only cartography from official IBRA7.1 boundaries; analytical masks use unsimplified source geometry.</metadata>',
        '<rect width="1200" height="760" fill="#ffffff"/>',
        '<g id="candidate-boundaries" fill="none" stroke="#c7ced6" stroke-width="1.1" stroke-linejoin="round">',
    ]
    for code in REGIONS:
        path_data = _svg_geometry_path(geometries[code], transform)
        lines.append(f'<path data-region-code="{code}" d="{path_data}"/>')
    lines.append("</g>")
    lines.append('<g id="selected-holdouts" stroke-linejoin="round">')
    for code in SELECTED_REGIONS:
        role = role_for[code]
        color = colors[role]
        path_data = _svg_geometry_path(geometries[code], transform)
        lines.append(
            f'<path data-region-code="{code}" data-role="{role}" d="{path_data}" '
            f'fill="{color}" fill-opacity="0.14" stroke="{color}" stroke-width="3.2"/>'
        )
        label_x, label_y = transform(*geometries[code].representative_point().coords[0])
        label = html.escape(f"{names[code]} ({code}) - {role}")
        lines.append(
            f'<text data-region-code="{code}" data-role="{role}" x="{label_x:.3f}" y="{label_y:.3f}" '
            f'font-family="sans-serif" font-size="15" font-weight="600" text-anchor="middle" '
            f'fill="{color}">{label}</text>'
        )
    lines.extend(["</g>", "</svg>", ""])
    path = root / SVG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    temporary.replace(path)
    return path


def compute_selection(inputs: Mapping[str, Any]) -> dict[str, Any]:
    config = inputs["config"]
    thresholds = _thresholds(config)
    ledger = inputs["ledger"]
    ids = ledger.cell_id.tolist()
    id_index = {cell_id: index for index, cell_id in enumerate(ids)}
    richness = np.zeros(len(ids), dtype=np.uint8)
    target_presence: dict[str, np.ndarray] = {}
    for species in inputs["effort"]:
        cells = inputs["census"]["cells_by_species"][species]
        indices = np.fromiter((id_index[cell] for cell in cells), dtype=np.int64, count=len(cells))
        richness[indices] += 1
        if species in inputs["targets"]:
            mask = np.zeros(len(ids), dtype=bool)
            mask[indices] = True
            target_presence[species] = mask
    if int(richness.max()) > len(inputs["effort"]):
        raise SelectionError("richness overflow")
    x10_cells = richness >= thresholds["x10"]
    x20_cells = richness >= thresholds["x20"]
    if np.any(x20_cells & ~x10_cells):
        raise SelectionError("X20 is not a subset of X10")
    xy = _projected_xy(ledger)
    tile_codes = np.floor(xy / 50_000.0).astype(np.int64)
    regions = scoring._load_regions(Path(inputs["root"]))
    projected_regions = {
        code: gpd.GeoSeries([regions[code]], crs=4326).to_crs(3577).iloc[0]
        for code in REGIONS
    }
    projected_points = points(xy[:, 0], xy[:, 1])
    buffer_masks = {
        code: np.asarray(covers(projected_regions[code].buffer(50_000.0), projected_points), dtype=bool)
        for code in REGIONS
    }
    region_masks = {
        code: ledger.region.astype("string").eq(code).fillna(False).to_numpy(dtype=bool)
        for code in REGIONS
    }
    # Evaluation summaries depend only on a target and a region, whereas the
    # training complement depends only on the candidate triple. Cache both
    # layers so each large boolean mask is traversed once per needed unit.
    evaluation_cache: dict[tuple[str, str], dict[str, Any]] = {}
    background_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    class_indices: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for species in inputs["targets"]:
        presence = target_presence[species]
        background_cache[species] = (
            x_background_mask(presence, richness, thresholds["x10"]),
            x_background_mask(presence, richness, thresholds["x20"]),
        )
        x10_background, x20_background = background_cache[species]
        presence_indices = np.flatnonzero(presence)
        x10_indices = np.flatnonzero(x10_background)
        x20_indices = np.flatnonzero(x20_background)
        class_indices[species] = (presence_indices, x10_indices)
        for code in REGIONS:
            mask = region_masks[code]
            region_indices = np.flatnonzero(mask)
            eval_presence_indices = region_indices[presence[region_indices]]
            eval_x10_indices = region_indices[x10_background[region_indices]]
            eval_x20_indices = region_indices[x20_background[region_indices]]
            evaluation_cache[(species, code)] = {
                "evaluation_presence_cells": len(eval_presence_indices),
                "evaluation_x10_background_cells": len(eval_x10_indices),
                "evaluation_x20_background_cells": len(eval_x20_indices),
                "evaluation_presence_tiles": _tile_count_for_indices(tile_codes, eval_presence_indices),
                "evaluation_x10_background_tiles": _tile_count_for_indices(tile_codes, eval_x10_indices),
                "evaluation_x20_background_tiles": _tile_count_for_indices(tile_codes, eval_x20_indices),
            }
    candidate_gates = {}
    for code in REGIONS:
        metric = inputs["metric_map"][code]
        mask = ledger.region.astype("string").eq(code).fillna(False).to_numpy(dtype=bool)
        count = int((mask & x10_cells).sum())
        candidate_gates[code] = {
            "predictor_complete_fraction": float(metric["predictor_complete_fraction"]),
            "eligible_land_cells": int(metric["domain_cells"]),
            "x10_effort_cells": count,
            "passes": count >= config["estimability"]["candidate_region_minimum_x10_effort_cells"],
        }
    gate_by_regions: dict[tuple[str, ...], dict[str, Any]] = {}
    all_target_metrics: dict[tuple[str, ...], dict[str, dict[str, dict[str, Any]]]] = {}
    for row in inputs["ranked"]:
        codes = tuple(sorted(row["regions"]))
        masks, training_mask = _region_masks(region_masks, buffer_masks, codes)
        target_metrics: dict[str, dict[str, dict[str, Any]]] = {}
        panel: list[str] = []
        for species in inputs["targets"]:
            presence = target_presence[species]
            x10_background, x20_background = background_cache[species]
            presence_indices, x10_indices = class_indices[species]
            retained_presence = training_mask[presence_indices]
            retained_x10 = training_mask[x10_indices]
            training_values = {
                "training_presence_cells": int(retained_presence.sum()),
                "training_x10_background_cells": int(retained_x10.sum()),
                "training_presence_tiles": _tile_count_for_indices(tile_codes, presence_indices, training_mask),
                "training_x10_background_tiles": _tile_count_for_indices(tile_codes, x10_indices, training_mask),
            }
            by_region = {}
            target_pass = True
            for code in codes:
                values = {**evaluation_cache[(species, code)], **training_values}
                values["evaluation_pass"] = bool(
                    values["evaluation_presence_cells"] >= thresholds["evaluation_minimum_presence_cells_per_target_region"]
                    and values["evaluation_x10_background_cells"] >= thresholds["evaluation_minimum_x10_background_cells_per_target_region"]
                    and values["evaluation_presence_tiles"] >= thresholds["evaluation_minimum_50km_tiles_per_class"]
                    and values["evaluation_x10_background_tiles"] >= thresholds["evaluation_minimum_50km_tiles_per_class"]
                )
                values["training_pass"] = bool(
                    values["training_presence_cells"] >= thresholds["training_minimum_presence_cells_per_target"]
                    and values["training_x10_background_cells"] >= thresholds["training_minimum_x10_background_cells_per_target"]
                    and values["training_presence_tiles"] >= thresholds["training_minimum_spatial_folds_per_class"]
                    and values["training_x10_background_tiles"] >= thresholds["training_minimum_spatial_folds_per_class"]
                )
                values["x20_evaluation_pass_diagnostic"] = bool(
                    values["evaluation_presence_cells"] >= thresholds["evaluation_minimum_presence_cells_per_target_region"]
                    and values["evaluation_x20_background_cells"] >= thresholds["evaluation_minimum_x10_background_cells_per_target_region"]
                    and values["evaluation_presence_tiles"] >= thresholds["evaluation_minimum_50km_tiles_per_class"]
                    and values["evaluation_x20_background_tiles"] >= thresholds["evaluation_minimum_50km_tiles_per_class"]
                )
                by_region[code] = values
                target_pass &= bool(values["evaluation_pass"] and values["training_pass"])
            target_metrics[species] = by_region
            if target_pass:
                panel.append(species)
        candidate_pass = all(candidate_gates[code]["passes"] for code in codes)
        set_pass = candidate_pass and len(panel) >= config["estimability"]["common_primary_target_panel_minimum"]
        gate_by_regions[codes] = {
            "passes": set_pass,
            "candidate_pass": candidate_pass,
            "candidate": {code: candidate_gates[code] for code in codes},
            "panel": panel,
            "panel_count": len(panel),
        }
        all_target_metrics[codes] = target_metrics
    feasible = filter_immutable_ranked(inputs["ranked"], gate_by_regions)
    summary = ambiguity_summary(feasible, config)
    def compact(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        codes = tuple(sorted(row["regions"]))
        gate = gate_by_regions[codes]
        target_values = all_target_metrics[codes]
        x20_summary = x20_panel_diagnostic_summary(target_values, gate["panel"], codes)
        return {
            "immutable_rank": int(row["immutable_rank"]),
            "regions": list(codes),
            "roles": row.get("role_assignment"),
            "minimum_role_score": float(row["minimum_role_score"]),
            "sum_role_scores": float(row["sum_role_scores"]),
            "candidate_gate": gate["candidate"],
            "common_x10_panel": gate["panel"],
            "common_x10_panel_count": gate["panel_count"],
            "evaluation_training_gate_aggregate": {
                "panel_target_region_count": gate["panel_count"] * len(codes),
                "evaluation_presence_min": min(target_values[s][code]["evaluation_presence_cells"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
                "evaluation_x10_background_min": min(target_values[s][code]["evaluation_x10_background_cells"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
                "evaluation_presence_tiles_min": min(target_values[s][code]["evaluation_presence_tiles"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
                "evaluation_x10_background_tiles_min": min(target_values[s][code]["evaluation_x10_background_tiles"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
                "training_presence_min": min(target_values[s][code]["training_presence_cells"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
                "training_x10_background_min": min(target_values[s][code]["training_x10_background_cells"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
                "training_presence_tiles_min": min(target_values[s][code]["training_presence_tiles"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
                "training_x10_background_tiles_min": min(target_values[s][code]["training_x10_background_tiles"] for s in gate["panel"] for code in codes) if gate["panel"] else 0,
            },
            "x20_evaluation_only_diagnostic": {
                **x20_summary,
            },
        }
    first = compact(summary["first"])
    second = compact(summary["second"])
    resolution = _load_resolution(inputs["root"], feasible, summary)
    selected = compact(next(row for row in feasible if int(row["immutable_rank"]) == int(resolution["selected_immutable_rank"])))
    selected["regions"] = list(SELECTED_REGIONS)
    selected["roles"] = dict(SELECTED_ROLES)
    boundary_map_hash = _sha(inputs["root"] / SVG_PATH) if (inputs["root"] / SVG_PATH).is_file() else None
    receipt = {
        "schema_version": "goal048-estimability-selection-v1",
        "status": "selected_after_explicit_resolution",
        "selection_only": True,
        "run_identity": inputs["run_identity"],
        "input_sha256": inputs["input_sha256"],
        "census": {
            "planned_species": 96,
            "completed_species": 96,
            "cumulative_total_count": inputs["census"]["progress"]["cumulative_total_count"],
            "cumulative_facet_groups": inputs["census"]["progress"]["cumulative_facet_groups"],
            "cumulative_retained_species_cells": inputs["census"]["progress"]["cumulative_retained_species_cells"],
            "occurrence_rows_downloaded": 0,
            "model_outcome_counter": 0,
            "frozen_role_exclusion_count": 4,
        },
        "ranking": {
            "immutable_ranked_set_count": len(inputs["ranked"]),
            "estimable_set_count": len(feasible),
            "first_feasible": first,
            "second_feasible": second,
            "signed_top_minus_runner_up_minimum_role_score": summary["minimum_margin"],
            "signed_top_minus_runner_up_sum_role_scores": summary["sum_margin"],
            "different_top_two_region_identity": bool(summary["second"] is not None and tuple(sorted(summary["first"]["regions"])) != tuple(sorted(summary["second"]["regions"]))) if summary["first"] and summary["second"] else False,
            "final_ambiguity_under_frozen_and_rule": summary["ambiguous"],
            "pre_resolution_status": "ambiguous_stop" if summary["ambiguous"] else "selected" if first else "no_feasible_set",
            "action": "selected_after_explicit_resolution",
        },
        "candidate_gate_aggregate": {
            "region_count": len(REGIONS),
            "candidate_x10_minimum": config["estimability"]["candidate_region_minimum_x10_effort_cells"],
            "candidate_x10_passing_region_count": sum(value["passes"] for value in candidate_gates.values()),
            "candidate_x10_minimum_observed": min(value["x10_effort_cells"] for value in candidate_gates.values()),
        },
        "final_resolution": {
            **resolution,
            "pre_resolution_ambiguity_preserved": bool(summary["ambiguous"]),
            "alternatives_validated": [
                {"immutable_rank": int(first["immutable_rank"]), "regions": first["regions"], "roles": first["roles"]},
                {"immutable_rank": int(second["immutable_rank"]), "regions": second["regions"], "roles": second["roles"]},
            ],
        },
        "selected_design": {
            "immutable_rank": int(selected["immutable_rank"]),
            "regions": selected["regions"],
            "roles": selected["roles"],
            "common_x10_panel": selected["common_x10_panel"],
            "common_x10_panel_count": selected["common_x10_panel_count"],
            "species_panel_policy": "conservative 40-species seed screen; Goal049 may expand the universe but cannot rerank or substitute these regions",
            "simultaneous_50km_buffer": {"distance_km": 50, "applies_to_all_three_holdouts": True, "excluded_from_training": True},
            "firewall": {
                "holdout_and_buffer_excluded_from": [
                    "model fitting",
                    "predictor transforms",
                    "pseudoabsence construction",
                    "inner spatial CV",
                    "tuning",
                    "threshold selection",
                    "architecture selection",
                    "predictor subset selection",
                    "stopping decisions",
                ],
                "training_only_tuning_thresholds_cv": True,
                "future_holdout_outcomes_opened": False,
            },
            "training_and_inner_cv": "training uses the simultaneous-buffer complement; tuning, thresholds, architecture, predictor choices, stopping, and inner spatial CV use retained geography only",
            "evaluation": {
                "primary_metric": "AUC",
                "diagnostics": ["balanced_accuracy", "TSS", "MCC", "sensitivity", "specificity"],
                "threshold_source": "training-only OOF predictions",
                "aggregate_support_used_for_estimability_gates_only": True,
                "outer_model_outcomes_unopened": True,
                "thresholds_from_training_only": True,
            },
            "weighting": {"equal_species_within_region": True, "equal_regions": True},
            "boundary_map": {"path": str(SVG_PATH), "sha256": boundary_map_hash, "source_ibra_sha256": inputs["input_sha256"]["ibra"], "display_only_simplification_m": 3000},
        },
        "privacy": {"raw_occurrence_rows": 0, "model_outcomes": 0, "coordinates_written": False, "private_cell_lists_written": False},
    }
    return receipt


def _build_inputs(root: Path) -> dict[str, Any]:
    inputs = load_frozen_inputs(root)
    inputs["root"] = root
    return inputs


def preflight(root: Path) -> dict[str, Any]:
    receipt = compute_selection(_build_inputs(root))
    return {"status": "ready", "ranking": receipt["ranking"], "candidate_gate_aggregate": receipt["candidate_gate_aggregate"], "run_identity": receipt["run_identity"]}


def run(root: Path) -> dict[str, Any]:
    receipt = compute_selection(_build_inputs(root))
    write_selected_holdouts_svg(root, receipt["final_resolution"])
    boundary_map_hash = _sha(root / SVG_PATH)
    receipt["input_sha256"]["selected_holdouts_svg"] = boundary_map_hash
    receipt["selected_design"]["boundary_map"]["sha256"] = boundary_map_hash
    _write_json(root / RECEIPT_PATH, receipt)
    return {"status": receipt["status"], "receipt": str(RECEIPT_PATH), "ranking": receipt["ranking"], "run_identity": receipt["run_identity"]}


def validate(root: Path) -> dict[str, Any]:
    path = root / RECEIPT_PATH
    if not path.is_file():
        raise SelectionError("estimability receipt is missing")
    receipt = json.loads(path.read_text())
    if receipt.get("privacy", {}).get("coordinates_written") is not False or receipt.get("privacy", {}).get("private_cell_lists_written") is not False:
        raise SelectionError("privacy receipt flags drift")
    if re.search(r"r[0-9]{4,}c[0-9]{4,}", path.read_text()) or any(key in receipt for key in ("longitude", "latitude", "cell_id")):
        raise SelectionError("estimability receipt contains private cell detail")
    svg = root / SVG_PATH
    if not svg.is_file() or _sha(svg) != receipt.get("selected_design", {}).get("boundary_map", {}).get("sha256"):
        raise SelectionError("selected holdout boundary-map checksum drift")
    if receipt.get("selected_design", {}).get("boundary_map", {}).get("source_ibra_sha256") != _sha(root / scoring.IBRA_PATH):
        raise SelectionError("selected holdout boundary-map source binding drift")
    svg_text = svg.read_text(encoding="utf-8")
    if any(token in svg_text.lower() for token in ("occurrence", "species", "response", "longitude", "latitude", "cell_id")):
        raise SelectionError("selected holdout map contains private or response-bearing content")
    import xml.etree.ElementTree as ET
    try:
        svg_root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise SelectionError("selected holdout map is not valid XML") from exc
    if svg_root.tag.rsplit("}", 1)[-1] != "svg":
        raise SelectionError("selected holdout map root drift")
    selected_paths = svg_root.findall(".//{http://www.w3.org/2000/svg}path")
    if not all(path.get("d") for path in selected_paths):
        raise SelectionError("selected holdout map path drift")
    selected_groups = svg_root.findall(".//*[@id='selected-holdouts']/{http://www.w3.org/2000/svg}path")
    if {path.get("data-region-code") for path in selected_groups if path.get("data-role") is not None} != set(SELECTED_REGIONS):
        raise SelectionError("selected holdout map region identity drift")
    if {path.get("data-role") for path in selected_groups if path.get("data-role") is not None} != set(SELECTED_ROLES):
        raise SelectionError("selected holdout map role identity drift")
    expected = compute_selection(_build_inputs(root))
    expected["input_sha256"]["selected_holdouts_svg"] = _sha(svg)
    expected["selected_design"]["boundary_map"]["sha256"] = _sha(svg)
    if receipt != expected:
        raise SelectionError("estimability receipt does not reproduce from frozen inputs")
    return {"status": "valid", "receipt": str(RECEIPT_PATH), "selection_status": receipt["status"], "estimable_set_count": receipt["ranking"]["estimable_set_count"], "ambiguous": receipt["ranking"]["final_ambiguity_under_frozen_and_rule"]}


def status(root: Path) -> dict[str, Any]:
    path = root / RECEIPT_PATH
    if not path.is_file():
        return {"status": "not_run", "receipt": str(RECEIPT_PATH)}
    value = json.loads(path.read_text())
    return {"status": value.get("status", "unknown"), "receipt": str(RECEIPT_PATH), "run_identity": value.get("run_identity")}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run", "validate", "status"))
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        fn = {"preflight": preflight, "run": run, "validate": validate, "status": status}[args.command]
        result = fn(args.root.resolve())
    except (OSError, SelectionError, ValueError, KeyError, FileNotFoundError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
