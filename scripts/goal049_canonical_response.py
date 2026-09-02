"""Build the private Goal 049 species-cell substrate and frozen target panels.

This stage consumes only the completed, checksum-bound aggregate census. It
does not query ALA, fit a model, or compute an outer-assessment outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from shapely import covers, make_valid, points, union_all


class Goal049CanonicalError(RuntimeError):
    """A canonical-response, panel, provenance, or privacy invariant failed."""


CONFIG = Path("config/goal049_seawfb_canonical_response.json")
STAGE_A = Path("metadata/goal049_registry_taxonomy_freeze.json")
REGISTRY = Path("data/processed/dsdm/goal049-seawfb-canonical-response/registry.json")
TAXONOMY = Path("data/processed/dsdm/goal049-seawfb-canonical-response/taxonomy_freeze.json")
PRIVATE = Path("data/processed/dsdm/goal049-seawfb-canonical-response")
PROGRESS = Path("evidence/seawfb_canonical_response/goal049/acquisition_progress.json")
CANARY = Path("evidence/seawfb_canonical_response/goal049/acquisition_canary.json")
DOMAIN = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/domain_cells.csv")
DOMAIN_RECEIPT = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/domain_freeze.json")
REGION_LEDGER = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/response_free/cell_region_ledger.parquet")
REGION_LEDGER_RECEIPT = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/response_free/cell_region_ledger_receipt.json")
GOAL048_RESOLUTION = Path("evidence/seawfb_bioregional_freeze/goal048/design_resolution.json")
GOAL048_SELECTION = Path("evidence/seawfb_bioregional_freeze/goal048/estimability_selection_receipt.json")
IBRA = Path("data/raw/goal040/domain/ibra7_1_subregions.geojson")
SELECTED_REGIONS = ("NCP", "SEH", "NNC")
CELL_RE = re.compile(r"^r[0-9]{4,}c[0-9]{4,}$")
CELL_TOKEN_RE = re.compile(r"r[0-9]{4,}c[0-9]{4,}")
PROHIBITED_TRACKED_KEYS = {
    "cell", "cells", "cell_id", "cell_ids", "latitude", "longitude",
    "coordinates", "coordinate", "private_species_cell_lists",
}


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


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049CanonicalError(f"unreadable JSON authority: {path}") from error
    if not isinstance(value, dict):
        raise Goal049CanonicalError(f"JSON authority is not an object: {path}")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _thresholds(config: Mapping[str, Any]) -> dict[str, int]:
    support, gates = config["effort_support"], config["estimability"]
    values = {
        "x10": int(support["primary_x"]),
        "x20": int(support["evaluation_only_sensitivity_x"]),
        "eval_presence": int(gates["evaluation_minimum_presence_cells_per_target_region"]),
        "eval_background": int(gates["evaluation_minimum_x10_background_cells_per_target_region"]),
        "eval_tiles": int(gates["evaluation_minimum_50km_tiles_per_class"]),
        "train_presence": int(gates["training_minimum_presence_cells_per_target"]),
        "train_background": int(gates["training_minimum_x10_background_cells_per_target"]),
        "train_tiles": int(gates["training_minimum_spatial_tiles_per_class"]),
        "common_minimum": int(gates["common_primary_target_panel_minimum"]),
    }
    if values != {
        "x10": 10, "x20": 20, "eval_presence": 30, "eval_background": 100,
        "eval_tiles": 4, "train_presence": 200, "train_background": 500,
        "train_tiles": 4, "common_minimum": 20,
    } or support.get("require_x20_subset_of_x10") is not True:
        raise Goal049CanonicalError("Goal 049 support or estimability contract drift")
    if tuple(config["upstream"]["goal048_selected_regions"]) != SELECTED_REGIONS:
        raise Goal049CanonicalError("selected region identity drift")
    if config["panels"].get("two_of_three_panel") is not False:
        raise Goal049CanonicalError("forbidden two-of-three panel enabled")
    if float(config["upstream"].get("external_training_exclusion_km", -1)) != 50.0:
        raise Goal049CanonicalError("frozen external buffer distance drift")
    return values


def _expected_normalisation(domain: pd.DataFrame, resolution: float) -> dict[str, Any]:
    required = {"row", "column", "longitude", "latitude"}
    if not required.issubset(domain.columns) or float(resolution) != 0.01:
        raise Goal049CanonicalError("domain grid or resolution is malformed")
    south = domain.loc[domain["latitude"].idxmin()]
    west = domain.loc[domain["longitude"].idxmin()]
    return {
        "resolution_degree": 0.01,
        "grid_origin": [
            float(south["latitude"]) - 0.005 - int(south["row"]) * 0.01,
            float(west["longitude"]) - 0.005 - int(west["column"]) * 0.01,
        ],
        "snap": "floor_cell_index",
    }


def _expected_query_fingerprint(config: Mapping[str, Any], domain_receipt: Mapping[str, Any], identifiers: Sequence[str]) -> str:
    contract, box = config["occurrence_contract"], domain_receipt["bbox"]
    filters = [
        f"year>={str(contract['time_start'])[:4]}", f"year<={str(contract['time_end'])[:4]}",
        f"occurrenceStatus={contract['occurrence_status']}",
        f"spatiallyValid={str(contract['spatially_valid']).lower()}",
        f"decimalLongitude>={box['xmin']}", f"decimalLongitude<={box['xmax']}",
        f"decimalLatitude>={box['ymin']}", f"decimalLatitude<={box['ymax']}",
    ]
    return _digest({"identifiers": list(identifiers), "filters": filters})


def focal_background_masks(
    presence: np.ndarray,
    global_effort_richness: np.ndarray,
    *,
    focal_is_effort_donor: bool,
    x10: int = 10,
    x20: int = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return focal-excluded richness and nested X10/X20 background masks."""
    presence = np.asarray(presence, dtype=bool)
    richness = np.asarray(global_effort_richness)
    if presence.ndim != 1 or richness.shape != presence.shape or np.any(richness < 0):
        raise Goal049CanonicalError("presence and richness vectors are incompatible")
    excluded = richness.astype(np.int32, copy=True)
    if focal_is_effort_donor:
        excluded -= presence.astype(np.int32)
    if np.any(excluded < 0):
        raise Goal049CanonicalError("focal exclusion produced negative donor richness")
    absent = ~presence
    if not np.array_equal(excluded[absent], richness[absent]):
        raise Goal049CanonicalError("focal exclusion changed richness on a focal-background cell")
    background10 = absent & (excluded >= int(x10))
    background20 = absent & (excluded >= int(x20))
    if np.any(background20 & ~background10):
        raise Goal049CanonicalError("X20 background is not a subset of X10")
    return excluded, background10, background20


def anchored_tile_count(xy: np.ndarray, mask: np.ndarray, tile_size_m: float = 50_000.0) -> int:
    """Count fixed EPSG:3577 tiles anchored at projected coordinate (0, 0)."""
    xy = np.asarray(xy, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) != len(mask) or tile_size_m <= 0:
        raise Goal049CanonicalError("malformed anchored-tile input")
    if not np.isfinite(xy).all():
        raise Goal049CanonicalError("non-finite projected coordinates")
    if not mask.any():
        return 0
    return int(np.unique(np.floor(xy[mask] / tile_size_m).astype(np.int64), axis=0).shape[0])


def training_mask_from_buffers(buffer_masks: Mapping[str, np.ndarray], regions: Sequence[str] = SELECTED_REGIONS) -> np.ndarray:
    """Return the simultaneous retained complement of all frozen holdout buffers."""
    if tuple(regions) != SELECTED_REGIONS or set(buffer_masks) != set(SELECTED_REGIONS):
        raise Goal049CanonicalError("buffer mask region identity drift")
    arrays = [np.asarray(buffer_masks[code], dtype=bool) for code in regions]
    if not arrays or len({len(value) for value in arrays}) != 1:
        raise Goal049CanonicalError("buffer masks are malformed")
    return ~np.logical_or.reduce(arrays)


def gate_metrics(
    presence: np.ndarray,
    background10: np.ndarray,
    background20: np.ndarray,
    evaluation_mask: np.ndarray,
    training_mask: np.ndarray,
    xy: np.ndarray,
    thresholds: Mapping[str, int],
) -> dict[str, Any]:
    """Compute one focal-species by frozen-region support gate."""
    presence = np.asarray(presence, dtype=bool)
    background10 = np.asarray(background10, dtype=bool)
    background20 = np.asarray(background20, dtype=bool)
    evaluation_mask = np.asarray(evaluation_mask, dtype=bool)
    training_mask = np.asarray(training_mask, dtype=bool)
    lengths = {len(presence), len(background10), len(background20), len(evaluation_mask), len(training_mask), len(xy)}
    if len(lengths) != 1 or np.any(background20 & ~background10):
        raise Goal049CanonicalError("gate masks are malformed or non-nested")
    masks = {
        "evaluation_presence": evaluation_mask & presence,
        "evaluation_x10_background": evaluation_mask & background10,
        "evaluation_x20_background": evaluation_mask & background20,
        "training_presence": training_mask & presence,
        "training_x10_background": training_mask & background10,
    }
    result: dict[str, Any] = {}
    for name, mask in masks.items():
        result[f"{name}_cells"] = int(mask.sum())
        result[f"{name}_tiles"] = anchored_tile_count(xy, mask)
    result["training_pass"] = bool(
        result["training_presence_cells"] >= thresholds["train_presence"]
        and result["training_x10_background_cells"] >= thresholds["train_background"]
        and result["training_presence_tiles"] >= thresholds["train_tiles"]
        and result["training_x10_background_tiles"] >= thresholds["train_tiles"]
    )
    result["evaluation_x10_pass"] = bool(
        result["evaluation_presence_cells"] >= thresholds["eval_presence"]
        and result["evaluation_x10_background_cells"] >= thresholds["eval_background"]
        and result["evaluation_presence_tiles"] >= thresholds["eval_tiles"]
        and result["evaluation_x10_background_tiles"] >= thresholds["eval_tiles"]
    )
    result["evaluation_x20_pass_diagnostic"] = bool(
        result["evaluation_presence_cells"] >= thresholds["eval_presence"]
        and result["evaluation_x20_background_cells"] >= thresholds["eval_background"]
        and result["evaluation_presence_tiles"] >= thresholds["eval_tiles"]
        and result["evaluation_x20_background_tiles"] >= thresholds["eval_tiles"]
    )
    return result


def derive_panel_membership(
    rows: pd.DataFrame,
    *,
    regions: Sequence[str] = SELECTED_REGIONS,
    common_minimum: int = 20,
) -> tuple[pd.DataFrame, list[str], dict[str, list[str]]]:
    """Derive exactly one common panel and three region-specific panels."""
    required = {"species", "region", "training_pass", "evaluation_x10_pass", "evaluation_x20_pass_diagnostic"}
    if not required.issubset(rows.columns) or tuple(regions) != SELECTED_REGIONS:
        raise Goal049CanonicalError("panel-gate ledger schema or region identity drift")
    frame = rows.copy()
    if frame.duplicated(["species", "region"]).any() or set(frame["region"]) != set(regions):
        raise Goal049CanonicalError("panel-gate ledger has duplicate or missing region tasks")
    counts = frame.groupby("species", sort=True)["region"].nunique()
    if not (counts == len(regions)).all():
        raise Goal049CanonicalError("every focal candidate must have all three region rows")
    frame["regional_secondary_member"] = frame["training_pass"] & frame["evaluation_x10_pass"]
    by_species = frame.groupby("species", sort=True)["regional_secondary_member"].all()
    common = sorted(by_species[by_species].index.astype(str).tolist())
    if len(common) < int(common_minimum):
        raise Goal049CanonicalError(f"common primary panel has fewer than {common_minimum} targets")
    frame["primary_common_member"] = frame["species"].isin(common)
    secondary = {
        code: sorted(frame.loc[(frame["region"] == code) & frame["regional_secondary_member"], "species"].astype(str).tolist())
        for code in regions
    }
    return frame.sort_values(["species", "region"], kind="mergesort").reset_index(drop=True), common, secondary


def _failure_reason(row: Mapping[str, Any]) -> str:
    failed: list[str] = []
    if not bool(row["training_pass"]):
        failed.append("retained_training_gate")
    if not bool(row["evaluation_x10_pass"]):
        failed.append("region_x10_evaluation_gate")
    return "passed_x10" if not failed else "+".join(failed)


def _validate_privacy(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in PROHIBITED_TRACKED_KEYS:
                raise Goal049CanonicalError(f"tracked privacy leak at {'.'.join(path + (str(key),))}")
            _validate_privacy(item, path=path + (str(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_privacy(item, path=path + (str(index),))
    elif isinstance(value, str) and CELL_TOKEN_RE.search(value):
        raise Goal049CanonicalError("tracked output contains a private cell identifier")


def _privacy_scan_tracked(root: Path, config: Mapping[str, Any]) -> None:
    for relative in config["tracked_outputs"].values():
        path = root / str(relative)
        if path.suffix == ".json" and path.is_file():
            _validate_privacy(_json(path))


def _load_upstream(root: Path) -> dict[str, Any]:
    config = _json(root / CONFIG)
    thresholds = _thresholds(config)
    stage_a = _json(root / STAGE_A)
    registry = _json(root / REGISTRY)
    taxonomy = _json(root / TAXONOMY)
    progress = _json(root / PROGRESS)
    run_exit = _json(root / PRIVATE / "run.exit")
    if stage_a.get("status") != "passed" or stage_a.get("occurrence_support_queried") is not False:
        raise Goal049CanonicalError("Stage A is not a passed count-free freeze")
    if stage_a.get("config_sha256") != _sha(root / CONFIG) or stage_a.get("registry_sha256") != _sha(root / REGISTRY) or stage_a.get("taxonomy_private_sha256") != _sha(root / TAXONOMY):
        raise Goal049CanonicalError("Stage A binding drift")
    if taxonomy.get("status") != "frozen_count_free" or taxonomy.get("ledger_sha256") != _digest(taxonomy.get("rows")):
        raise Goal049CanonicalError("private taxonomy freeze drift")
    if progress.get("status") != "complete" or run_exit.get("status") != "complete":
        raise Goal049CanonicalError("Goal 049 aggregate census is incomplete")
    if progress.get("occurrence_rows_downloaded") != 0 or progress.get("model_outcome_counter") != 0:
        raise Goal049CanonicalError("aggregate census contains forbidden rows or outcomes")
    if progress.get("stage_a_freeze_sha256") != _sha(root / STAGE_A):
        raise Goal049CanonicalError("aggregate census Stage A binding drift")
    rows = registry.get("rows") or registry.get("species") or registry.get("registry")
    if not isinstance(rows, list):
        raise Goal049CanonicalError("private registry has no row ledger")
    registry_by_name = {str(row.get("name") or row.get("species")): row for row in rows}
    if len(registry_by_name) != len(rows) or "" in registry_by_name:
        raise Goal049CanonicalError("private registry names are empty or duplicated")
    active_taxonomy = [row for row in taxonomy["rows"] if bool(row.get("active"))]
    taxonomy_by_name = {str(row["species"]): row for row in active_taxonomy}
    active_names = [str(row["species"]) for row in active_taxonomy]
    if progress.get("planned_species") != len(active_names) or progress.get("completed_species") != len(active_names) or run_exit.get("completed_species") != len(active_names):
        raise Goal049CanonicalError("census/taxonomy species count drift")
    for row in active_taxonomy:
        registry_row = registry_by_name.get(str(row["species"]))
        roles = row.get("roles", {})
        if registry_row is None or any(bool(registry_row.get(role)) != bool(roles.get(role)) for role in ("effort", "auxiliary", "target")):
            raise Goal049CanonicalError("taxonomy roles no longer match the count-free registry")
    domain = pd.read_csv(root / DOMAIN, dtype={"cell_id": str})
    if domain["cell_id"].duplicated().any() or domain["cell_id"].map(lambda x: CELL_RE.fullmatch(x) is None).any():
        raise Goal049CanonicalError("Goal 048 exact domain ledger is malformed")
    domain_ids = set(domain["cell_id"])
    domain_receipt = _json(root / DOMAIN_RECEIPT)
    resolution = _json(root / GOAL048_RESOLUTION)
    selection = _json(root / GOAL048_SELECTION)
    if domain_receipt.get("status") != "frozen_count_free" or domain_receipt.get("cell_count") != len(domain) or domain_receipt.get("private_cells_sha256") != _sha(root / DOMAIN):
        raise Goal049CanonicalError("Goal 048 exact domain receipt drift")
    if tuple(resolution.get("selected_regions", ())) != SELECTED_REGIONS or tuple(selection.get("selected_design", {}).get("regions", ())) != SELECTED_REGIONS or selection.get("status") != "selected_after_explicit_resolution":
        raise Goal049CanonicalError("Goal 048 selected-region authority drift")
    expected_normalisation = _expected_normalisation(domain, float(config["occurrence_contract"]["snap_immediately_to_resolution_degree"]))
    domain_freeze_sha = _sha(root / DOMAIN_RECEIPT)
    checkpoints = sorted((root / PRIVATE / "checkpoints").glob("*.json"))
    receipts = sorted((root / PRIVATE / "species_cells").glob("*.json"))
    expected_names = [f"{index:05d}.json" for index in range(len(active_names))]
    if [path.name for path in checkpoints] != expected_names or [path.name for path in receipts] != expected_names:
        raise Goal049CanonicalError("checkpoint/species-cell inventory is not exact and contiguous")
    checkpoint_hashes: list[str] = []
    species_cells: list[tuple[str, list[str], Path, dict[str, Any]]] = []
    totals = {"total_count": 0, "facet_groups": 0, "memberships": 0}
    for index, species in enumerate(active_names):
        checkpoint_path, receipt_path = checkpoints[index], receipts[index]
        checkpoint, receipt = _json(checkpoint_path), _json(receipt_path)
        if checkpoint.get("status") != "passed" or checkpoint.get("index") != index or checkpoint.get("species") != species:
            raise Goal049CanonicalError("checkpoint identity drift")
        if checkpoint.get("total_count") != checkpoint.get("facet_count_sum"):
            raise Goal049CanonicalError("checkpoint total-to-facet conservation failed")
        count_values = {key: checkpoint.get(key) for key in ("total_count", "facet_count_sum", "facet_group_count")}
        if checkpoint.get("count_conservation_sha256") != _digest(count_values) or checkpoint.get("stage_a_freeze_sha256") != _sha(root / STAGE_A):
            raise Goal049CanonicalError("checkpoint conservation or Stage A binding drift")
        if checkpoint.get("occurrence_rows_downloaded") != 0 or checkpoint.get("model_outcome_counter") != 0:
            raise Goal049CanonicalError("checkpoint contains forbidden work")
        expected_receipt = root / str(checkpoint.get("private_cell_receipt", ""))
        if expected_receipt != receipt_path or checkpoint.get("private_cell_receipt_sha256") != _sha(receipt_path):
            raise Goal049CanonicalError("checkpoint private receipt binding drift")
        cells = receipt.get("cells")
        if receipt.get("species") != species or not isinstance(cells, list) or cells != sorted(set(cells)) or not set(cells).issubset(domain_ids):
            raise Goal049CanonicalError("private species-cell receipt is not canonical or in-domain")
        if any(not isinstance(cell, str) or CELL_RE.fullmatch(cell) is None for cell in cells) or len(cells) != checkpoint.get("retained_species_cell_count"):
            raise Goal049CanonicalError("private species-cell receipt count or identifier drift")
        expected_identifiers = taxonomy_by_name[species].get("ordered_identifiers")
        expected_query = _expected_query_fingerprint(config, domain_receipt, expected_identifiers)
        if checkpoint.get("query_fingerprint") != expected_query or receipt.get("query_fingerprint") != expected_query or receipt.get("identifiers_sha256") != _digest(expected_identifiers) or receipt.get("domain_cells_sha256") != _sha(root / DOMAIN) or receipt.get("domain_cell_count") != len(domain) or receipt.get("domain_freeze_sha256") != domain_freeze_sha or receipt.get("normalisation") != expected_normalisation or receipt.get("occurrence_rows_downloaded") != 0:
            raise Goal049CanonicalError("private species-cell query/domain binding drift")
        limits = config["occurrence_contract"]["transport_ceiling"]
        if "private_disk_bytes_after" not in checkpoint or "peak_ram_bytes_upper_bound" not in checkpoint or int(checkpoint["facet_group_count"]) > int(limits["lat_long_groups_per_species"]) or int(checkpoint["private_disk_bytes_after"]) > int(float(limits["private_disk_gib"]) * 1024**3) or int(checkpoint["peak_ram_bytes_upper_bound"]) > int(float(limits["peak_ram_gib"]) * 1024**3):
            raise Goal049CanonicalError("checkpoint transport ceiling failed")
        checkpoint_hashes.append(_sha(checkpoint_path))
        species_cells.append((species, cells, receipt_path, checkpoint))
        totals["total_count"] += int(checkpoint["total_count"])
        totals["facet_groups"] += int(checkpoint["facet_group_count"])
        totals["memberships"] += len(cells)
    if progress.get("checkpoint_inventory_sha256") != _digest(checkpoint_hashes):
        raise Goal049CanonicalError("census checkpoint inventory hash drift")
    if totals != {
        "total_count": int(progress["cumulative_total_count"]),
        "facet_groups": int(progress["cumulative_facet_groups"]),
        "memberships": int(progress["cumulative_retained_species_cells"]),
    } or run_exit.get("cumulative_facet_groups") != totals["facet_groups"]:
        raise Goal049CanonicalError("census cumulative conservation drift")
    limits = config["occurrence_contract"]["transport_ceiling"]
    if "private_disk_bytes" not in progress or "peak_ram_bytes_upper_bound" not in progress or totals["facet_groups"] > int(limits["lat_long_groups_total"]) or int(progress["private_disk_bytes"]) > int(float(limits["private_disk_gib"]) * 1024**3) or int(progress["peak_ram_bytes_upper_bound"]) > int(float(limits["peak_ram_gib"]) * 1024**3):
        raise Goal049CanonicalError("census transport ceiling failed")
    canary = _json(root / CANARY)
    if canary.get("status") != "passed" or canary.get("occurrence_rows_downloaded") != 0 or canary.get("model_outcome_counter") != 0:
        raise Goal049CanonicalError("mandatory live canary is missing or invalid")
    canary_species = str(canary.get("species", ""))
    if canary_species not in taxonomy_by_name:
        raise Goal049CanonicalError("canary species is not in the frozen active taxonomy")
    canary_identifiers = taxonomy_by_name[canary_species]["ordered_identifiers"]
    canary_query = _expected_query_fingerprint(config, domain_receipt, canary_identifiers)
    canary_counts = {key: canary.get(key) for key in ("total_count", "facet_count_sum", "facet_group_count")}
    canary_private = root / str(canary.get("private_cell_receipt", ""))
    extra_canary = root / PRIVATE / "canary_species_cells.json"
    if canary_private not in set(receipts) | {extra_canary} or not canary_private.is_file() or canary.get("private_cell_receipt_sha256") != _sha(canary_private):
        raise Goal049CanonicalError("canary private receipt is missing, orphaned, or checksum-drifted")
    if extra_canary.exists() != (canary_private == extra_canary):
        raise Goal049CanonicalError("unreferenced or missing noncontiguous canary receipt")
    canary_cells = _json(canary_private)
    if canary.get("total_count") != canary.get("facet_count_sum") or int(canary.get("facet_group_count", -1)) > int(limits["lat_long_groups_per_species"]) or canary.get("count_conservation_sha256") != _digest(canary_counts) or canary.get("query_fingerprint") != canary_query or canary.get("identifiers_sha256") != _digest(canary_identifiers) or canary.get("domain_cells_sha256") != _sha(root / DOMAIN) or canary.get("domain_cell_count") != len(domain) or canary.get("domain_freeze_sha256") != domain_freeze_sha or canary.get("normalisation_sha256") != _digest(expected_normalisation) or canary.get("stage_a_freeze_sha256") != _sha(root / STAGE_A):
        raise Goal049CanonicalError("canary conservation or query/domain binding drift")
    if canary_cells.get("species") != canary_species or canary_cells.get("query_fingerprint") != canary_query or canary_cells.get("identifiers_sha256") != _digest(canary_identifiers) or canary_cells.get("domain_cells_sha256") != _sha(root / DOMAIN) or canary_cells.get("domain_cell_count") != len(domain) or canary_cells.get("domain_freeze_sha256") != domain_freeze_sha or canary_cells.get("normalisation") != expected_normalisation or canary_cells.get("occurrence_rows_downloaded") != 0:
        raise Goal049CanonicalError("canary private receipt binding drift")
    canary_cell_ids = canary_cells.get("cells")
    if not isinstance(canary_cell_ids, list) or canary_cell_ids != sorted(set(canary_cell_ids)) or not set(canary_cell_ids).issubset(domain_ids):
        raise Goal049CanonicalError("canary private cells are not canonical and in-domain")
    _privacy_scan_tracked(root, config)
    return {
        "config": config, "thresholds": thresholds, "stage_a": stage_a,
        "registry": registry, "registry_by_name": registry_by_name,
        "taxonomy": taxonomy, "active_names": active_names,
        "species_cells": species_cells, "domain_ids": domain_ids,
        "totals": totals, "progress": progress, "run_exit": run_exit, "canary": canary,
    }


def _write_canonical_parquet(root: Path, species_cells: Sequence[tuple[str, list[str], Path, dict[str, Any]]]) -> Path:
    path = root / PRIVATE / "canonical_species_cells.parquet"
    temporary = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema([("species", pa.string()), ("cell_id", pa.string())])
    writer = pq.ParquetWriter(temporary, schema, compression="zstd", use_dictionary=True)
    try:
        for species, cells, _, _ in sorted(species_cells, key=lambda item: item[0]):
            if cells:
                writer.write_table(pa.table({"species": [species] * len(cells), "cell_id": cells}, schema=schema))
    finally:
        writer.close()
    os.replace(temporary, path)
    return path


def _load_geography(root: Path, domain_ids: set[str], buffer_km: float) -> tuple[pd.DataFrame, np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    receipt = _json(root / REGION_LEDGER_RECEIPT)
    ledger_path = root / REGION_LEDGER
    if receipt.get("ledger_sha256") != _sha(ledger_path):
        raise Goal049CanonicalError("Goal 048 cell-region ledger binding drift")
    ledger = pd.read_parquet(ledger_path, columns=["cell_id", "longitude", "latitude", "region"])
    ledger = ledger.sort_values("cell_id", kind="mergesort").reset_index(drop=True)
    if ledger["cell_id"].duplicated().any() or set(ledger["cell_id"].astype(str)) != domain_ids:
        raise Goal049CanonicalError("Goal 048 cell-region ledger differs from exact domain")
    geographic = gpd.GeoSeries(points(ledger["longitude"].to_numpy(), ledger["latitude"].to_numpy()), crs=4326).to_crs(3577)
    xy = np.column_stack([geographic.x.to_numpy(), geographic.y.to_numpy()])
    region_masks = {code: ledger["region"].astype("string").eq(code).fillna(False).to_numpy(bool) for code in SELECTED_REGIONS}
    if any(not mask.any() for mask in region_masks.values()) or np.logical_and.reduce(list(region_masks.values())).any():
        raise Goal049CanonicalError("selected whole-region masks are missing or overlapping")
    ibra = gpd.read_file(root / IBRA)
    if len(ibra) != 419 or ibra["REG_CODE_7"].nunique() != 89:
        raise Goal049CanonicalError("IBRA7.1 authority identity drift")
    ibra = ibra.to_crs(3577)
    projected_points = points(xy[:, 0], xy[:, 1])
    buffer_masks: dict[str, np.ndarray] = {}
    for code in SELECTED_REGIONS:
        subset = ibra.loc[ibra["REG_CODE_7"] == code]
        if subset.empty:
            raise Goal049CanonicalError(f"official selected region missing: {code}")
        geometry = make_valid(union_all(subset.geometry.array)).buffer(float(buffer_km) * 1000.0)
        buffer_masks[code] = np.asarray(covers(geometry, projected_points), dtype=bool)
        if np.any(region_masks[code] & ~buffer_masks[code]):
            raise Goal049CanonicalError(f"region is not contained by its buffer: {code}")
    training_mask = training_mask_from_buffers(buffer_masks)
    return ledger, xy, region_masks, buffer_masks, training_mask


def _derive(root: Path, inputs: Mapping[str, Any]) -> tuple[pd.DataFrame, list[str], dict[str, list[str]], dict[str, Any]]:
    ledger, xy, region_masks, buffer_masks, training_mask = _load_geography(
        root, inputs["domain_ids"], float(inputs["config"]["upstream"]["external_training_exclusion_km"]),
    )
    ids = ledger["cell_id"].astype(str).tolist()
    index = {cell: position for position, cell in enumerate(ids)}
    cells_by_species = {species: cells for species, cells, _, _ in inputs["species_cells"]}
    role_rows = inputs["registry_by_name"]
    effort = sorted(name for name in inputs["active_names"] if bool(role_rows[name].get("effort")))
    auxiliary = sorted(name for name in inputs["active_names"] if bool(role_rows[name].get("auxiliary")))
    targets = sorted(name for name in inputs["active_names"] if bool(role_rows[name].get("target")))
    if not set(targets).issubset(auxiliary) or not set(auxiliary).issubset(effort):
        raise Goal049CanonicalError("focal/auxiliary/effort roles are not nested")
    richness = np.zeros(len(ids), dtype=np.uint16)
    indices_by_species: dict[str, np.ndarray] = {}
    for species in inputs["active_names"]:
        indices = np.fromiter((index[cell] for cell in cells_by_species[species]), dtype=np.int64, count=len(cells_by_species[species]))
        indices_by_species[species] = indices
        if species in effort:
            richness[indices] += 1
    if int(richness.max(initial=0)) > len(effort):
        raise Goal049CanonicalError("effort donor richness overflow")
    rows: list[dict[str, Any]] = []
    for species in targets:
        presence = np.zeros(len(ids), dtype=bool)
        presence[indices_by_species[species]] = True
        excluded, background10, background20 = focal_background_masks(
            presence, richness, focal_is_effort_donor=species in effort,
            x10=inputs["thresholds"]["x10"], x20=inputs["thresholds"]["x20"],
        )
        if not np.array_equal(excluded[~presence], richness[~presence]):
            raise Goal049CanonicalError("focal-background richness identity failed")
        for code in SELECTED_REGIONS:
            metrics = gate_metrics(presence, background10, background20, region_masks[code], training_mask, xy, inputs["thresholds"])
            rows.append({"species": species, "region": code, **metrics})
    raw = pd.DataFrame(rows)
    if raw.empty:
        raise Goal049CanonicalError("canonical registry has no focal target candidates")
    panels, common, secondary = derive_panel_membership(raw, common_minimum=inputs["thresholds"]["common_minimum"])
    panels["gate_reason"] = panels.apply(_failure_reason, axis=1)
    x20 = {
        code: sorted(panels.loc[(panels["region"] == code) & panels["regional_secondary_member"] & panels["evaluation_x20_pass_diagnostic"], "species"].tolist())
        for code in SELECTED_REGIONS
    }
    context = {
        "effort_species": effort, "auxiliary_species": auxiliary, "target_species": targets,
        "x20_diagnostic_species": x20, "training_cell_count": int(training_mask.sum()),
        "region_cell_counts": {code: int(mask.sum()) for code, mask in region_masks.items()},
        "buffer_cell_counts": {code: int(mask.sum()) for code, mask in buffer_masks.items()},
        "maximum_effort_richness": int(richness.max(initial=0)),
    }
    return panels, common, secondary, context


def build(root: Path) -> dict[str, Any]:
    root = Path(root)
    inputs = _load_upstream(root)
    canonical_path = _write_canonical_parquet(root, inputs["species_cells"])
    panels, common, secondary, context = _derive(root, inputs)
    panel_path = root / PRIVATE / "panel_ledger.parquet"
    temporary = panel_path.with_name(panel_path.name + ".tmp")
    panels.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, panel_path)
    tracked = inputs["config"]["tracked_outputs"]
    panel_summary = {
        "schema_version": "goal049-panel-summary-v1", "status": "frozen",
        "regions": list(SELECTED_REGIONS),
        "primary_common": {"count": len(common), "species": common},
        "secondary_region_specific": {code: {"count": len(names), "species": names} for code, names in secondary.items()},
        "x20_evaluation_only": {
            code: {"count": len(context["x20_diagnostic_species"][code]), "species": context["x20_diagnostic_species"][code]}
            for code in SELECTED_REGIONS
        },
        "focal_gate_reasons": {
            species: {
                code: str(panels.loc[(panels["species"] == species) & (panels["region"] == code), "gate_reason"].iloc[0])
                for code in SELECTED_REGIONS
            }
            for species in context["target_species"]
        },
        "secondary_motivation": inputs["config"]["panels"]["secondary_motivation_disclosure"],
        "x20_changes_membership": False, "two_of_three_panel": False,
        "privacy": {"coordinates_written": False, "private_lists_written": False, "raw_occurrence_rows": 0, "model_outcomes": 0},
    }
    completion = {
        "schema_version": "goal049-canonical-response-completion-v1", "status": "complete",
        "regions": list(SELECTED_REGIONS), "simultaneous_buffer_km": 50.0,
        "tasmania_role": "ordinary_training_geography",
        "counts": {
            "active_species": len(inputs["active_names"]), "effort_donors": len(context["effort_species"]),
            "auxiliary_heads": len(context["auxiliary_species"]), "focal_candidates": len(context["target_species"]),
            "canonical_memberships": inputs["totals"]["memberships"], "panel_rows": len(panels),
            "common_primary_targets": len(common),
            "regional_secondary_targets": {code: len(names) for code, names in secondary.items()},
            "training_cells_after_simultaneous_buffers": context["training_cell_count"],
            "selected_region_cells": context["region_cell_counts"],
            "selected_region_buffer_cells": context["buffer_cell_counts"],
            "maximum_effort_donor_richness": context["maximum_effort_richness"],
        },
        "bindings": {
            "config_sha256": _sha(root / CONFIG), "stage_a_sha256": _sha(root / STAGE_A),
            "registry_sha256": _sha(root / REGISTRY), "taxonomy_sha256": _sha(root / TAXONOMY),
            "acquisition_progress_sha256": _sha(root / PROGRESS), "run_exit_sha256": _sha(root / PRIVATE / "run.exit"),
            "domain_sha256": _sha(root / DOMAIN), "region_ledger_sha256": _sha(root / REGION_LEDGER),
            "domain_receipt_sha256": _sha(root / DOMAIN_RECEIPT),
            "region_ledger_receipt_sha256": _sha(root / REGION_LEDGER_RECEIPT), "ibra_sha256": _sha(root / IBRA),
            "goal048_design_resolution_sha256": _sha(root / GOAL048_RESOLUTION),
            "goal048_selection_receipt_sha256": _sha(root / GOAL048_SELECTION),
            "acquisition_canary_sha256": _sha(root / CANARY),
            "canonical_species_cells_sha256": _sha(canonical_path), "panel_ledger_sha256": _sha(panel_path),
        },
        "private_outputs": {
            "canonical_species_cells": str(canonical_path.relative_to(root)),
            "panel_ledger": str(panel_path.relative_to(root)),
        },
        "scientific_invariants": {
            "focal_excluded_from_donor_richness": True, "focal_absent_richness_identity_verified": True,
            "future_focal_exclusion_from_auxiliary_pretraining_required": inputs["config"]["roles"]["focal_exclusion"]["from_auxiliary_pretraining"] is True,
            "richness_used_as_predictor": False,
            "x20_subset_of_x10": True, "x20_changes_membership": False,
            "training_excludes_all_three_region_buffers_simultaneously": True,
        },
        "privacy": {"coordinates_written": False, "private_species_cell_lists_written": False, "raw_occurrence_rows": 0, "model_outcomes": 0},
    }
    panel_summary["bindings"] = {
        "completion_config_sha256": completion["bindings"]["config_sha256"],
        "canonical_species_cells_sha256": completion["bindings"]["canonical_species_cells_sha256"],
        "panel_ledger_sha256": completion["bindings"]["panel_ledger_sha256"],
    }
    _validate_privacy(panel_summary)
    _validate_privacy(completion)
    _atomic_json(root / tracked["panel_summary"], panel_summary)
    completion["bindings"]["panel_summary_sha256"] = _sha(root / tracked["panel_summary"])
    _validate_privacy(completion)
    _atomic_json(root / tracked["completion"], completion)
    _privacy_scan_tracked(root, inputs["config"])
    return completion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("build",))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(build(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
