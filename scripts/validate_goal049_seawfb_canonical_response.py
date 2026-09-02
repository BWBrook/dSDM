"""Independent validator for the Goal 049 canonical response substrate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from shapely import covers, make_valid, points, union_all


class Goal049ValidationError(RuntimeError):
    """A Goal 049 completion claim could not be independently reproduced."""


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
REGION_RECEIPT = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/response_free/cell_region_ledger_receipt.json")
GOAL048_RESOLUTION = Path("evidence/seawfb_bioregional_freeze/goal048/design_resolution.json")
GOAL048_SELECTION = Path("evidence/seawfb_bioregional_freeze/goal048/estimability_selection_receipt.json")
IBRA = Path("data/raw/goal040/domain/ibra7_1_subregions.geojson")
REGIONS = ("NCP", "SEH", "NNC")
CELL_RE = re.compile(r"^r[0-9]{4,}c[0-9]{4,}$")
CELL_TOKEN_RE = re.compile(r"r[0-9]{4,}c[0-9]{4,}")
PRIVATE_KEYS = {"cell", "cells", "cell_id", "cell_ids", "latitude", "longitude", "coordinate", "coordinates"}


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


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049ValidationError(f"unreadable JSON: {path}") from error
    if not isinstance(value, dict):
        raise Goal049ValidationError(f"non-object JSON: {path}")
    return value


def _privacy(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in PRIVATE_KEYS:
                raise Goal049ValidationError(f"tracked privacy leak: {key}")
            _privacy(item)
    elif isinstance(value, list):
        for item in value:
            _privacy(item)
    elif isinstance(value, str) and CELL_TOKEN_RE.search(value):
        raise Goal049ValidationError("tracked output contains a private cell ID")


def _thresholds(config: Mapping[str, Any]) -> dict[str, int]:
    effort, gate = config["effort_support"], config["estimability"]
    values = {
        "x10": int(effort["primary_x"]), "x20": int(effort["evaluation_only_sensitivity_x"]),
        "eval_presence": int(gate["evaluation_minimum_presence_cells_per_target_region"]),
        "eval_background": int(gate["evaluation_minimum_x10_background_cells_per_target_region"]),
        "eval_tiles": int(gate["evaluation_minimum_50km_tiles_per_class"]),
        "train_presence": int(gate["training_minimum_presence_cells_per_target"]),
        "train_background": int(gate["training_minimum_x10_background_cells_per_target"]),
        "train_tiles": int(gate["training_minimum_spatial_tiles_per_class"]),
        "common_minimum": int(gate["common_primary_target_panel_minimum"]),
    }
    expected = {"x10": 10, "x20": 20, "eval_presence": 30, "eval_background": 100, "eval_tiles": 4, "train_presence": 200, "train_background": 500, "train_tiles": 4, "common_minimum": 20}
    if values != expected or effort.get("require_x20_subset_of_x10") is not True:
        raise Goal049ValidationError("frozen support thresholds drifted")
    if tuple(config["upstream"]["goal048_selected_regions"]) != REGIONS or config["panels"].get("two_of_three_panel") is not False:
        raise Goal049ValidationError("frozen region or panel contract drifted")
    if float(config["upstream"].get("external_training_exclusion_km", -1)) != 50.0:
        raise Goal049ValidationError("frozen external buffer distance drifted")
    return values


def _expected_normalisation(domain: pd.DataFrame, resolution: float) -> dict[str, Any]:
    if not {"row", "column", "longitude", "latitude"}.issubset(domain.columns) or float(resolution) != 0.01:
        raise Goal049ValidationError("domain grid or resolution is malformed")
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


def _privacy_scan_tracked(root: Path, config: Mapping[str, Any]) -> None:
    for relative in config["tracked_outputs"].values():
        path = root / str(relative)
        if path.suffix == ".json" and path.is_file():
            _privacy(_read(path))


def _tile_count(xy: np.ndarray, mask: np.ndarray) -> int:
    mask = np.asarray(mask, dtype=bool)
    return int(np.unique(np.floor(xy[mask] / 50_000.0).astype(np.int64), axis=0).shape[0]) if mask.any() else 0


def _metrics(
    presence: np.ndarray,
    richness: np.ndarray,
    evaluation: np.ndarray,
    training: np.ndarray,
    xy: np.ndarray,
    thresholds: Mapping[str, int],
) -> dict[str, Any]:
    focal_richness = richness.astype(np.int32) - presence.astype(np.int32)
    if np.any(focal_richness < 0) or not np.array_equal(focal_richness[~presence], richness[~presence]):
        raise Goal049ValidationError("focal-excluded richness reconstruction failed")
    x10 = (~presence) & (focal_richness >= thresholds["x10"])
    x20 = (~presence) & (focal_richness >= thresholds["x20"])
    if np.any(x20 & ~x10):
        raise Goal049ValidationError("X20 is not nested within X10")
    masks = {
        "evaluation_presence": evaluation & presence,
        "evaluation_x10_background": evaluation & x10,
        "evaluation_x20_background": evaluation & x20,
        "training_presence": training & presence,
        "training_x10_background": training & x10,
    }
    result: dict[str, Any] = {}
    for label, mask in masks.items():
        result[f"{label}_cells"] = int(mask.sum())
        result[f"{label}_tiles"] = _tile_count(xy, mask)
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


def _validate_canonical_stream(path: Path, expected: Sequence[tuple[str, list[str]]]) -> int:
    parquet = pq.ParquetFile(path)
    if parquet.schema_arrow.names != ["species", "cell_id"]:
        raise Goal049ValidationError("canonical Parquet schema drift")
    expected_rows = sum(len(cells) for _, cells in expected)
    if parquet.metadata.num_rows != expected_rows:
        raise Goal049ValidationError("canonical Parquet row conservation failed")
    species_index = 0
    cell_index = 0
    previous: tuple[str, str] | None = None
    for batch in parquet.iter_batches(columns=["species", "cell_id"], batch_size=131_072):
        species_values = batch.column(0).to_pylist()
        cell_values = batch.column(1).to_pylist()
        for species, cell in zip(species_values, cell_values, strict=True):
            while species_index < len(expected) and cell_index == len(expected[species_index][1]):
                species_index += 1
                cell_index = 0
            if species_index >= len(expected):
                raise Goal049ValidationError("canonical Parquet has surplus rows")
            expected_species, expected_cells = expected[species_index]
            if species != expected_species or cell != expected_cells[cell_index]:
                raise Goal049ValidationError("canonical Parquet differs from private species receipts")
            current = (str(species), str(cell))
            if previous is not None and current <= previous:
                raise Goal049ValidationError("canonical Parquet is not sorted and unique")
            previous = current
            cell_index += 1
    while species_index < len(expected) and cell_index == len(expected[species_index][1]):
        species_index += 1
        cell_index = 0
    if species_index != len(expected):
        raise Goal049ValidationError("canonical Parquet ended before private species receipts")
    return expected_rows


def _assert_exact_panel_frame(observed: pd.DataFrame, expected: pd.DataFrame) -> None:
    if observed.columns.tolist() != expected.columns.tolist():
        raise Goal049ValidationError("private panel ledger schema has missing or surplus columns")
    try:
        pd.testing.assert_frame_equal(observed, expected, check_dtype=False, check_like=False)
    except AssertionError as error:
        raise Goal049ValidationError("private panel ledger is not independently reproducible") from error


def _load_inputs(root: Path) -> dict[str, Any]:
    config = _read(root / CONFIG)
    thresholds = _thresholds(config)
    tracked = config["tracked_outputs"]
    completion_path, summary_path = root / tracked["completion"], root / tracked["panel_summary"]
    completion, summary = _read(completion_path), _read(summary_path)
    _privacy(completion); _privacy(summary)
    if completion.get("status") != "complete" or summary.get("status") != "frozen":
        raise Goal049ValidationError("tracked completion is not final")
    if completion.get("privacy") != {"coordinates_written": False, "private_species_cell_lists_written": False, "raw_occurrence_rows": 0, "model_outcomes": 0}:
        raise Goal049ValidationError("completion privacy counters failed")
    bindings = completion.get("bindings", {})
    bound = {
        "config_sha256": CONFIG, "stage_a_sha256": STAGE_A, "registry_sha256": REGISTRY,
        "taxonomy_sha256": TAXONOMY, "acquisition_progress_sha256": PROGRESS,
        "run_exit_sha256": PRIVATE / "run.exit", "domain_sha256": DOMAIN,
        "domain_receipt_sha256": DOMAIN_RECEIPT,
        "region_ledger_sha256": REGION_LEDGER, "region_ledger_receipt_sha256": REGION_RECEIPT,
        "ibra_sha256": IBRA, "goal048_design_resolution_sha256": GOAL048_RESOLUTION,
        "goal048_selection_receipt_sha256": GOAL048_SELECTION, "acquisition_canary_sha256": CANARY,
    }
    for key, relative in bound.items():
        if bindings.get(key) != _sha(root / relative):
            raise Goal049ValidationError(f"completion binding drift: {key}")
    if bindings.get("panel_summary_sha256") != _sha(summary_path):
        raise Goal049ValidationError("panel summary binding drift")
    stage_a, registry, taxonomy = _read(root / STAGE_A), _read(root / REGISTRY), _read(root / TAXONOMY)
    progress, run_exit = _read(root / PROGRESS), _read(root / PRIVATE / "run.exit")
    if stage_a.get("status") != "passed" or stage_a.get("occurrence_support_queried") is not False:
        raise Goal049ValidationError("Stage A is not count-free and passed")
    if stage_a.get("config_sha256") != _sha(root / CONFIG) or stage_a.get("registry_sha256") != _sha(root / REGISTRY) or stage_a.get("taxonomy_private_sha256") != _sha(root / TAXONOMY):
        raise Goal049ValidationError("Stage A checksum drift")
    if taxonomy.get("status") != "frozen_count_free" or taxonomy.get("ledger_sha256") != _digest(taxonomy.get("rows")):
        raise Goal049ValidationError("taxonomy freeze drift")
    if progress.get("status") != "complete" or run_exit.get("status") != "complete" or progress.get("occurrence_rows_downloaded") != 0 or progress.get("model_outcome_counter") != 0:
        raise Goal049ValidationError("aggregate census completion/privacy failed")
    if progress.get("stage_a_freeze_sha256") != _sha(root / STAGE_A):
        raise Goal049ValidationError("aggregate census Stage A binding drift")
    registry_rows = registry.get("rows") or registry.get("species") or registry.get("registry")
    if not isinstance(registry_rows, list):
        raise Goal049ValidationError("registry row ledger missing")
    roles = {str(row.get("name") or row.get("species")): row for row in registry_rows}
    if len(roles) != len(registry_rows):
        raise Goal049ValidationError("registry species identity collision")
    active = [row for row in taxonomy["rows"] if bool(row.get("active"))]
    taxonomy_by_name = {str(row["species"]): row for row in active}
    names = [str(row["species"]) for row in active]
    if len(names) != int(progress.get("planned_species", -1)) or len(names) != int(progress.get("completed_species", -1)) or len(names) != int(run_exit.get("completed_species", -1)):
        raise Goal049ValidationError("active taxonomy/census species count drift")
    for row in active:
        registry_row = roles.get(str(row["species"])); frozen_roles = row.get("roles", {})
        if registry_row is None or any(bool(registry_row.get(role)) != bool(frozen_roles.get(role)) for role in ("effort", "auxiliary", "target")):
            raise Goal049ValidationError("taxonomy role snapshot differs from frozen registry")
    checkpoints = sorted((root / PRIVATE / "checkpoints").glob("*.json"))
    receipts = sorted((root / PRIVATE / "species_cells").glob("*.json"))
    expected_files = [f"{index:05d}.json" for index in range(len(names))]
    if [path.name for path in checkpoints] != expected_files or [path.name for path in receipts] != expected_files:
        raise Goal049ValidationError("orphan or missing census receipt")
    domain = pd.read_csv(root / DOMAIN, dtype={"cell_id": str})
    domain_ids = set(domain["cell_id"])
    if len(domain_ids) != len(domain):
        raise Goal049ValidationError("domain cell identity collision")
    domain_receipt = _read(root / DOMAIN_RECEIPT)
    resolution = _read(root / GOAL048_RESOLUTION)
    selection = _read(root / GOAL048_SELECTION)
    if domain_receipt.get("status") != "frozen_count_free" or domain_receipt.get("cell_count") != len(domain) or domain_receipt.get("private_cells_sha256") != _sha(root / DOMAIN):
        raise Goal049ValidationError("Goal 048 domain receipt drift")
    if tuple(resolution.get("selected_regions", ())) != REGIONS or tuple(selection.get("selected_design", {}).get("regions", ())) != REGIONS or selection.get("status") != "selected_after_explicit_resolution":
        raise Goal049ValidationError("Goal 048 selected-region authority drift")
    expected_normalisation = _expected_normalisation(domain, float(config["occurrence_contract"]["snap_immediately_to_resolution_degree"]))
    domain_freeze_sha = _sha(root / DOMAIN_RECEIPT)
    cells_by_species: dict[str, list[str]] = {}
    checkpoint_hashes: list[str] = []
    total_count = facet_groups = membership_count = 0
    for index, species in enumerate(names):
        checkpoint, receipt = _read(checkpoints[index]), _read(receipts[index])
        if checkpoint.get("index") != index or checkpoint.get("species") != species or checkpoint.get("status") != "passed":
            raise Goal049ValidationError("checkpoint order or identity drift")
        if checkpoint.get("total_count") != checkpoint.get("facet_count_sum") or checkpoint.get("occurrence_rows_downloaded") != 0 or checkpoint.get("model_outcome_counter") != 0:
            raise Goal049ValidationError("checkpoint conservation/privacy failed")
        count_values = {key: checkpoint.get(key) for key in ("total_count", "facet_count_sum", "facet_group_count")}
        if checkpoint.get("count_conservation_sha256") != _digest(count_values) or checkpoint.get("stage_a_freeze_sha256") != _sha(root / STAGE_A):
            raise Goal049ValidationError("checkpoint conservation or Stage A binding drift")
        if root / str(checkpoint.get("private_cell_receipt", "")) != receipts[index] or checkpoint.get("private_cell_receipt_sha256") != _sha(receipts[index]):
            raise Goal049ValidationError("checkpoint species receipt binding drift")
        cells = receipt.get("cells")
        if receipt.get("species") != species or not isinstance(cells, list) or cells != sorted(set(cells)) or not set(cells).issubset(domain_ids):
            raise Goal049ValidationError("private species-cell receipt drift")
        identifiers = taxonomy_by_name[species].get("ordered_identifiers")
        expected_query = _expected_query_fingerprint(config, domain_receipt, identifiers)
        if checkpoint.get("query_fingerprint") != expected_query or receipt.get("query_fingerprint") != expected_query or receipt.get("identifiers_sha256") != _digest(identifiers) or receipt.get("domain_cells_sha256") != _sha(root / DOMAIN) or receipt.get("domain_cell_count") != len(domain) or receipt.get("domain_freeze_sha256") != domain_freeze_sha or receipt.get("normalisation") != expected_normalisation or receipt.get("occurrence_rows_downloaded") != 0:
            raise Goal049ValidationError("private species-cell query/domain binding drift")
        if len(cells) != checkpoint.get("retained_species_cell_count"):
            raise Goal049ValidationError("checkpoint retained-cell count drift")
        limits = config["occurrence_contract"]["transport_ceiling"]
        if "private_disk_bytes_after" not in checkpoint or "peak_ram_bytes_upper_bound" not in checkpoint or int(checkpoint["facet_group_count"]) > int(limits["lat_long_groups_per_species"]) or int(checkpoint["private_disk_bytes_after"]) > int(float(limits["private_disk_gib"]) * 1024**3) or int(checkpoint["peak_ram_bytes_upper_bound"]) > int(float(limits["peak_ram_gib"]) * 1024**3):
            raise Goal049ValidationError("checkpoint transport ceiling failed")
        cells_by_species[species] = cells
        checkpoint_hashes.append(_sha(checkpoints[index]))
        total_count += int(checkpoint["total_count"]); facet_groups += int(checkpoint["facet_group_count"]); membership_count += len(cells)
    if progress.get("checkpoint_inventory_sha256") != _digest(checkpoint_hashes):
        raise Goal049ValidationError("checkpoint inventory digest drift")
    if (total_count, facet_groups, membership_count) != (int(progress["cumulative_total_count"]), int(progress["cumulative_facet_groups"]), int(progress["cumulative_retained_species_cells"])):
        raise Goal049ValidationError("aggregate cumulative totals drift")
    limits = config["occurrence_contract"]["transport_ceiling"]
    if "private_disk_bytes" not in progress or "peak_ram_bytes_upper_bound" not in progress or facet_groups > int(limits["lat_long_groups_total"]) or int(progress["private_disk_bytes"]) > int(float(limits["private_disk_gib"]) * 1024**3) or int(progress["peak_ram_bytes_upper_bound"]) > int(float(limits["peak_ram_gib"]) * 1024**3):
        raise Goal049ValidationError("census transport ceiling failed")
    canary = _read(root / CANARY)
    if canary.get("status") != "passed" or canary.get("occurrence_rows_downloaded") != 0 or canary.get("model_outcome_counter") != 0:
        raise Goal049ValidationError("mandatory live canary is missing or invalid")
    canary_species = str(canary.get("species", ""))
    if canary_species not in taxonomy_by_name:
        raise Goal049ValidationError("canary species is not active in frozen taxonomy")
    canary_identifiers = taxonomy_by_name[canary_species]["ordered_identifiers"]
    canary_query = _expected_query_fingerprint(config, domain_receipt, canary_identifiers)
    canary_counts = {key: canary.get(key) for key in ("total_count", "facet_count_sum", "facet_group_count")}
    canary_private = root / str(canary.get("private_cell_receipt", ""))
    extra_canary = root / PRIVATE / "canary_species_cells.json"
    if canary_private not in set(receipts) | {extra_canary} or not canary_private.is_file() or canary.get("private_cell_receipt_sha256") != _sha(canary_private):
        raise Goal049ValidationError("canary private receipt is missing, orphaned, or checksum-drifted")
    if extra_canary.exists() != (canary_private == extra_canary):
        raise Goal049ValidationError("unreferenced or missing noncontiguous canary receipt")
    canary_cells = _read(canary_private)
    if canary.get("total_count") != canary.get("facet_count_sum") or int(canary.get("facet_group_count", -1)) > int(limits["lat_long_groups_per_species"]) or canary.get("count_conservation_sha256") != _digest(canary_counts) or canary.get("query_fingerprint") != canary_query or canary.get("identifiers_sha256") != _digest(canary_identifiers) or canary.get("domain_cells_sha256") != _sha(root / DOMAIN) or canary.get("domain_cell_count") != len(domain) or canary.get("domain_freeze_sha256") != domain_freeze_sha or canary.get("normalisation_sha256") != _digest(expected_normalisation) or canary.get("stage_a_freeze_sha256") != _sha(root / STAGE_A):
        raise Goal049ValidationError("canary conservation or query/domain binding drift")
    if canary_cells.get("species") != canary_species or canary_cells.get("query_fingerprint") != canary_query or canary_cells.get("identifiers_sha256") != _digest(canary_identifiers) or canary_cells.get("domain_cells_sha256") != _sha(root / DOMAIN) or canary_cells.get("domain_cell_count") != len(domain) or canary_cells.get("domain_freeze_sha256") != domain_freeze_sha or canary_cells.get("normalisation") != expected_normalisation or canary_cells.get("occurrence_rows_downloaded") != 0:
        raise Goal049ValidationError("canary private receipt binding drift")
    canary_cell_ids = canary_cells.get("cells")
    if not isinstance(canary_cell_ids, list) or canary_cell_ids != sorted(set(canary_cell_ids)) or not set(canary_cell_ids).issubset(domain_ids):
        raise Goal049ValidationError("canary private cells are not canonical and in-domain")
    _privacy_scan_tracked(root, config)
    canonical_path = root / completion["private_outputs"]["canonical_species_cells"]
    panel_path = root / completion["private_outputs"]["panel_ledger"]
    if not str(canonical_path.relative_to(root)).startswith(str(PRIVATE)) or not str(panel_path.relative_to(root)).startswith(str(PRIVATE)):
        raise Goal049ValidationError("private payload escaped the private namespace")
    if bindings.get("canonical_species_cells_sha256") != _sha(canonical_path) or bindings.get("panel_ledger_sha256") != _sha(panel_path):
        raise Goal049ValidationError("private output checksum drift")
    expected = sorted(cells_by_species.items())
    if _validate_canonical_stream(canonical_path, expected) != membership_count:
        raise Goal049ValidationError("canonical membership conservation failed")
    return {
        "config": config, "thresholds": thresholds, "completion": completion, "summary": summary,
        "roles": roles, "active": names, "cells_by_species": cells_by_species,
        "domain_ids": domain_ids, "panel_path": panel_path, "membership_count": membership_count,
    }


def _reconstruct(root: Path, inputs: Mapping[str, Any]) -> tuple[pd.DataFrame, list[str], dict[str, list[str]], dict[str, list[str]], dict[str, Any]]:
    region_receipt = _read(root / REGION_RECEIPT)
    if region_receipt.get("ledger_sha256") != _sha(root / REGION_LEDGER):
        raise Goal049ValidationError("Goal 048 region-ledger receipt drift")
    ledger = pd.read_parquet(root / REGION_LEDGER, columns=["cell_id", "longitude", "latitude", "region"])
    ledger = ledger.sort_values("cell_id", kind="mergesort").reset_index(drop=True)
    if set(ledger["cell_id"].astype(str)) != inputs["domain_ids"] or ledger["cell_id"].duplicated().any():
        raise Goal049ValidationError("region ledger does not match exact domain")
    geoseries = gpd.GeoSeries(points(ledger["longitude"].to_numpy(), ledger["latitude"].to_numpy()), crs=4326).to_crs(3577)
    xy = np.column_stack([geoseries.x.to_numpy(), geoseries.y.to_numpy()])
    region_masks = {code: ledger["region"].astype("string").eq(code).fillna(False).to_numpy(bool) for code in REGIONS}
    ibra = gpd.read_file(root / IBRA)
    if len(ibra) != 419 or ibra["REG_CODE_7"].nunique() != 89:
        raise Goal049ValidationError("IBRA authority count drift")
    ibra = ibra.to_crs(3577)
    projected = points(xy[:, 0], xy[:, 1])
    buffers: dict[str, np.ndarray] = {}
    for code in REGIONS:
        geometry = make_valid(union_all(ibra.loc[ibra["REG_CODE_7"] == code].geometry.array)).buffer(50_000.0)
        buffers[code] = np.asarray(covers(geometry, projected), dtype=bool)
        if np.any(region_masks[code] & ~buffers[code]):
            raise Goal049ValidationError("region cell is outside reconstructed buffer")
    training = ~np.logical_or.reduce([buffers[code] for code in REGIONS])
    ids = ledger["cell_id"].astype(str).tolist(); positions = {cell: index for index, cell in enumerate(ids)}
    effort = sorted(name for name in inputs["active"] if bool(inputs["roles"][name].get("effort")))
    auxiliary = sorted(name for name in inputs["active"] if bool(inputs["roles"][name].get("auxiliary")))
    targets = sorted(name for name in inputs["active"] if bool(inputs["roles"][name].get("target")))
    if not set(targets).issubset(auxiliary) or not set(auxiliary).issubset(effort):
        raise Goal049ValidationError("role nesting failed")
    richness = np.zeros(len(ids), dtype=np.uint16)
    indices: dict[str, np.ndarray] = {}
    for species in inputs["active"]:
        value = np.fromiter((positions[cell] for cell in inputs["cells_by_species"][species]), dtype=np.int64, count=len(inputs["cells_by_species"][species]))
        indices[species] = value
        if species in effort:
            richness[value] += 1
    rows: list[dict[str, Any]] = []
    for species in targets:
        presence = np.zeros(len(ids), dtype=bool); presence[indices[species]] = True
        for code in REGIONS:
            rows.append({"species": species, "region": code, **_metrics(presence, richness, region_masks[code], training, xy, inputs["thresholds"])})
    frame = pd.DataFrame(rows).sort_values(["species", "region"], kind="mergesort").reset_index(drop=True)
    frame["regional_secondary_member"] = frame["training_pass"] & frame["evaluation_x10_pass"]
    common_flags = frame.groupby("species", sort=True)["regional_secondary_member"].all()
    common = sorted(common_flags[common_flags].index.astype(str).tolist())
    if len(common) < inputs["thresholds"]["common_minimum"]:
        raise Goal049ValidationError("reconstructed common panel fails minimum")
    frame["primary_common_member"] = frame["species"].isin(common)
    frame["gate_reason"] = frame.apply(lambda row: "passed_x10" if row["regional_secondary_member"] else "+".join(filter(None, ["retained_training_gate" if not row["training_pass"] else "", "region_x10_evaluation_gate" if not row["evaluation_x10_pass"] else ""])), axis=1)
    secondary = {code: sorted(frame.loc[(frame["region"] == code) & frame["regional_secondary_member"], "species"].astype(str).tolist()) for code in REGIONS}
    x20 = {code: sorted(frame.loc[(frame["region"] == code) & frame["regional_secondary_member"] & frame["evaluation_x20_pass_diagnostic"], "species"].astype(str).tolist()) for code in REGIONS}
    context = {"effort": effort, "auxiliary": auxiliary, "targets": targets, "training_cells": int(training.sum()), "region_cells": {code: int(region_masks[code].sum()) for code in REGIONS}, "buffer_cells": {code: int(buffers[code].sum()) for code in REGIONS}, "max_richness": int(richness.max(initial=0))}
    return frame, common, secondary, x20, context


def validate(root: Path) -> dict[str, Any]:
    root = Path(root)
    inputs = _load_inputs(root)
    expected, common, secondary, x20, context = _reconstruct(root, inputs)
    observed = pd.read_parquet(inputs["panel_path"]).sort_values(["species", "region"], kind="mergesort").reset_index(drop=True)
    _assert_exact_panel_frame(observed, expected)
    summary, completion = inputs["summary"], inputs["completion"]
    if summary["primary_common"] != {"count": len(common), "species": common}:
        raise Goal049ValidationError("tracked common panel summary drift")
    for code in REGIONS:
        if summary["secondary_region_specific"].get(code) != {"count": len(secondary[code]), "species": secondary[code]}:
            raise Goal049ValidationError("tracked regional secondary panel drift")
        if summary["x20_evaluation_only"].get(code) != {"count": len(x20[code]), "species": x20[code]}:
            raise Goal049ValidationError("tracked X20 diagnostic drift")
    expected_reasons = {species: {code: str(expected.loc[(expected["species"] == species) & (expected["region"] == code), "gate_reason"].iloc[0]) for code in REGIONS} for species in context["targets"]}
    if summary.get("focal_gate_reasons") != expected_reasons or summary.get("x20_changes_membership") is not False or summary.get("two_of_three_panel") is not False:
        raise Goal049ValidationError("tracked gate reasons or panel semantics drift")
    counts = completion.get("counts", {})
    expected_counts = {
        "active_species": len(inputs["active"]), "effort_donors": len(context["effort"]), "auxiliary_heads": len(context["auxiliary"]),
        "focal_candidates": len(context["targets"]), "canonical_memberships": inputs["membership_count"], "panel_rows": len(expected),
        "common_primary_targets": len(common), "regional_secondary_targets": {code: len(secondary[code]) for code in REGIONS},
        "training_cells_after_simultaneous_buffers": context["training_cells"], "selected_region_cells": context["region_cells"],
        "selected_region_buffer_cells": context["buffer_cells"], "maximum_effort_donor_richness": context["max_richness"],
    }
    if counts != expected_counts:
        raise Goal049ValidationError("tracked completion counts drift")
    invariants = completion.get("scientific_invariants", {})
    required_true = {"focal_excluded_from_donor_richness", "focal_absent_richness_identity_verified", "future_focal_exclusion_from_auxiliary_pretraining_required", "x20_subset_of_x10", "training_excludes_all_three_region_buffers_simultaneously"}
    if any(invariants.get(key) is not True for key in required_true) or invariants.get("richness_used_as_predictor") is not False or invariants.get("x20_changes_membership") is not False:
        raise Goal049ValidationError("scientific invariant receipt drift")
    return {
        "status": "passed", "active_species": len(inputs["active"]), "canonical_memberships": inputs["membership_count"],
        "common_primary_targets": len(common), "regional_secondary_targets": {code: len(secondary[code]) for code in REGIONS},
        "raw_occurrence_rows": 0, "model_outcomes": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(validate(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
