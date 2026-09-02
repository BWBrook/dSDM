"""Resumable, privacy-preserving Goal 049 aggregate occurrence census."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import sys
import time
from pathlib import Path
from re import fullmatch
from typing import Any

import galah
import pandas as pd

from goal049_taxonomy_freeze import Goal049TaxonomyError, _digest, _sha, validate_taxonomy_freeze


class Goal049CensusError(RuntimeError):
    """A Goal 049 acquisition, conservation, privacy, or replay invariant failed."""


Goal049Error = Goal049CensusError


PRIVATE_RELATIVE = Path("data/processed/dsdm/goal049-seawfb-canonical-response")
GOAL048_PRIVATE_RELATIVE = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze")
CONFIG_RELATIVE = Path("config/goal049_seawfb_canonical_response.json")
FREEZE_RELATIVE = Path("metadata/goal049_registry_taxonomy_freeze.json")
PROGRESS_RELATIVE = Path("evidence/seawfb_canonical_response/goal049/acquisition_progress.json")
CANARY_RELATIVE = Path("evidence/seawfb_canonical_response/goal049/acquisition_canary.json")
CELL_ID_PATTERN = r"r[0-9]{4,}c[0-9]{4,}"
TAXON_GROUP_LIMIT = 750_000
CENSUS_GROUP_LIMIT = 50_000_000
DISK_LIMIT = 4 * 1024**3
RAM_LIMIT = 8 * 1024**3


def _private(root: Path) -> Path:
    return Path(root) / PRIVATE_RELATIVE


def _private_goal048(root: Path) -> Path:
    return Path(root) / GOAL048_PRIVATE_RELATIVE


def _config(root: Path) -> dict[str, Any]:
    try:
        return json.loads((Path(root) / CONFIG_RELATIVE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049CensusError("Goal 049 config is unreadable") from error


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _peak_ram_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _private_disk_bytes(root: Path) -> int:
    private = _private(root)
    return sum(path.stat().st_size for path in private.rglob("*") if path.is_file()) if private.exists() else 0


def _domain_path(root: Path) -> Path:
    local = _private(root) / "domain_cells.csv"
    historical = _private_goal048(root) / "domain_cells.csv"
    if local.is_file():
        return local
    if historical.is_file():
        return historical
    raise Goal049CensusError("exact Goal 048 domain cell ledger is missing")


def _domain_receipt_path(root: Path) -> Path:
    local = _private(root) / "domain_freeze.json"
    historical = _private_goal048(root) / "domain_freeze.json"
    if local.is_file():
        return local
    if historical.is_file():
        return historical
    raise Goal049CensusError("exact Goal 048 domain freeze receipt is missing")


def _domain_frame(root: Path) -> pd.DataFrame:
    path = _domain_path(root)
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError) as error:
        raise Goal049CensusError("domain cell ledger is unreadable") from error
    required = {"cell_id", "row", "column", "longitude", "latitude"}
    if not required.issubset(frame.columns) or frame[list(required)].isna().any().any():
        raise Goal049CensusError("domain cell ledger is malformed")
    ids = frame["cell_id"].astype(str).tolist()
    if len(ids) != len(set(ids)) or any(fullmatch(CELL_ID_PATTERN, value) is None for value in ids):
        raise Goal049CensusError("domain cell ledger contains duplicate or malformed IDs")
    for column in ("row", "column"):
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.isna().any() or (numeric % 1 != 0).any():
            raise Goal049CensusError("domain cell ledger has malformed grid indices")
    for column in ("longitude", "latitude"):
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.isna().any() or not numeric.map(math.isfinite).all():
            raise Goal049CensusError("domain cell ledger has malformed coordinates")
    historical = _private_goal048(root) / "domain_cells.csv"
    if path != historical and historical.is_file() and _sha(path) != _sha(historical):
        raise Goal049CensusError("Goal 049 domain differs from immutable Goal 048 domain")
    return frame


def _grid_origin(frame: pd.DataFrame) -> tuple[float, float]:
    south = frame.loc[frame["latitude"].idxmin()]
    west = frame.loc[frame["longitude"].idxmin()]
    return (
        float(south["latitude"]) - 0.005 - int(south["row"]) * 0.01,
        float(west["longitude"]) - 0.005 - int(west["column"]) * 0.01,
    )


def _normalisation(frame: pd.DataFrame, resolution: float = 0.01) -> dict[str, Any]:
    origin = _grid_origin(frame)
    return {"resolution_degree": resolution, "grid_origin": [origin[0], origin[1]], "snap": "floor_cell_index"}


def _filters(config: dict[str, Any], domain: dict[str, Any]) -> list[str]:
    contract = config["occurrence_contract"]
    start = str(contract["time_start"])[:4]
    end = str(contract["time_end"])[:4]
    box = domain["bbox"]
    return [
        f"year>={start}", f"year<={end}",
        f"occurrenceStatus={contract['occurrence_status']}",
        f"spatiallyValid={str(contract['spatially_valid']).lower()}",
        f"decimalLongitude>={box['xmin']}", f"decimalLongitude<={box['xmax']}",
        f"decimalLatitude>={box['ymin']}", f"decimalLatitude<={box['ymax']}",
    ]


def compile_query(identifiers: list[str], filters: list[str], group_by: str | None = None) -> dict[str, Any]:
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise Goal049CensusError("identifier union is empty or duplicated")
    required = ("decimalLongitude>=", "decimalLongitude<=", "decimalLatitude>=", "decimalLatitude<=")
    if not all(any(item.startswith(prefix) for item in filters) for prefix in required):
        raise Goal049CensusError("query lacks explicit coordinate filters")
    return {"identifiers": list(identifiers), "filters": list(filters), **({"group_by": group_by} if group_by else {})}


def _taxonomy(root: Path) -> dict[str, Any]:
    try:
        path = _private(root) / "taxonomy_freeze.json"
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049CensusError("private Goal 049 taxonomy freeze is unreadable") from error
    if value.get("status") != "frozen_count_free" or value.get("occurrence_support_queried") is not False:
        raise Goal049CensusError("Goal 049 taxonomy freeze is not count-free")
    return value


def _stage_a(root: Path) -> dict[str, Any]:
    try:
        result = validate_taxonomy_freeze(root)
        receipt = json.loads((Path(root) / FREEZE_RELATIVE).read_text(encoding="utf-8"))
    except (Goal049TaxonomyError, OSError, json.JSONDecodeError) as error:
        raise Goal049CensusError("Goal 049 Stage A freeze is required before census") from error
    if receipt.get("status") not in {"passed", "passed_stage_a", "frozen_count_free"} or receipt.get("occurrence_support_queried") is not False:
        raise Goal049CensusError("Goal 049 Stage A freeze is not valid")
    if receipt.get("taxonomy_private_sha256") != result.get("taxonomy_private_sha256"):
        raise Goal049CensusError("Goal 049 Stage A taxonomy binding drift")
    return receipt


def _query_pair(row: dict[str, Any], config: dict[str, Any] | dict[str, Any], domain: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any], str]:
    if domain is None:
        domain = config
        config = _config(Path.cwd())
    filters = _filters(config, domain)
    total = compile_query(row["ordered_identifiers"], filters)
    facet = compile_query(row["ordered_identifiers"], filters, "lat_long")
    fingerprint = _digest({"identifiers": total["identifiers"], "filters": total["filters"]})
    return total, facet, fingerprint


def build_census_plan(root: Path) -> list[dict[str, Any]]:
    stage_a = _stage_a(root)
    config = _config(root)
    taxonomy = _taxonomy(root)
    frame = _domain_frame(root)
    domain = {"bbox": {"xmin": float(frame["longitude"].min()), "xmax": float(frame["longitude"].max()), "ymin": float(frame["latitude"].min()), "ymax": float(frame["latitude"].max())}}
    # A domain freeze may provide the authoritative bbox; derive only when the
    # small synthetic test tree has no private domain receipt.
    domain_receipt = _domain_receipt_path(root)
    domain.update(json.loads(domain_receipt.read_text(encoding="utf-8")))
    plan: list[dict[str, Any]] = []
    for row in taxonomy.get("rows", []):
        if not bool(row.get("active", True)):
            continue
        total, facet, fingerprint = _query_pair(row, config, domain)
        plan.append({
            "index": len(plan), "species": row.get("species") or row.get("seed_name") or row["source_name"],
            "identifiers": list(row["ordered_identifiers"]),
            "query_fingerprint": fingerprint, "total_query": total, "facet_query": facet,
            "domain_cells_sha256": _sha(_domain_path(root)), "domain_cell_count": len(frame),
            "normalisation": _normalisation(frame, float(config["occurrence_contract"]["snap_immediately_to_resolution_degree"])),
            "domain_freeze_sha256": _sha(domain_receipt),
            "stage_a_freeze_sha256": _sha(Path(root) / FREEZE_RELATIVE),
        })
    if len({item["query_fingerprint"] for item in plan}) != len(plan):
        raise Goal049CensusError("census query fingerprints are not unique")
    return plan


def _checkpoint_path(root: Path, index: int) -> Path:
    return _private(root) / "checkpoints" / f"{index:05d}.json"


def _cell_receipt_path(root: Path, index: int) -> Path:
    return _private(root) / "species_cells" / f"{index:05d}.json"


def _parse_lat_long(value: Any) -> tuple[float, float]:
    parts = str(value).replace("[", "").replace("]", "").split(",")
    if len(parts) != 2:
        raise Goal049CensusError("malformed lat_long facet label")
    try:
        lat, lon = float(parts[0].strip()), float(parts[1].strip())
    except ValueError as error:
        raise Goal049CensusError("non-numeric lat_long facet label") from error
    if not math.isfinite(lat) or not math.isfinite(lon):
        raise Goal049CensusError("non-finite lat_long facet label")
    return lat, lon


def _integer_counts(frame: pd.DataFrame, column: str) -> pd.Series:
    counts = pd.to_numeric(frame[column], errors="coerce")
    if counts.isna().any() or (counts < 0).any() or (counts % 1 != 0).any():
        raise Goal049CensusError("aggregate response contains malformed counts")
    return counts.astype("int64")


def _reject_partial(frame: pd.DataFrame) -> None:
    if any(bool(frame.attrs.get(key, False)) for key in ("truncated", "is_truncated", "partial")) or frame.attrs.get("warnings"):
        raise Goal049CensusError("aggregate response is partial or contains warnings")


def _validate_cell_receipt(root: Path, item: dict[str, Any], path: Path, domain_ids: set[str] | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049CensusError("private species-cell receipt is unreadable") from error
    cells = value.get("cells")
    if value.get("species") != item["species"] or not isinstance(cells, list):
        raise Goal049CensusError("private species-cell receipt identity drift")
    if cells != sorted(set(cells)) or any(not isinstance(cell, str) or fullmatch(CELL_ID_PATTERN, cell) is None for cell in cells):
        raise Goal049CensusError("private species-cell receipt is not canonical")
    if domain_ids is None:
        domain_ids = set(_domain_frame(root)["cell_id"].astype(str))
    if not set(cells).issubset(domain_ids):
        raise Goal049CensusError("private species-cell receipt contains an out-of-domain cell")
    for key, expected in (("query_fingerprint", item["query_fingerprint"]), ("identifiers_sha256", _digest(item["identifiers"])), ("domain_cells_sha256", item["domain_cells_sha256"]), ("domain_cell_count", item["domain_cell_count"]), ("domain_freeze_sha256", item["domain_freeze_sha256"]), ("normalisation", item["normalisation"])):
        if value.get(key) != expected:
            raise Goal049CensusError("private species-cell receipt binding drift")
    return value


def _receipt_payload(item: dict[str, Any], cells: list[str], *, source: str) -> dict[str, Any]:
    return {
        "schema_version": "goal049-private-species-cells-v1", "species": item["species"], "cells": sorted(set(cells)),
        "source": source, "query_fingerprint": item["query_fingerprint"],
        "identifiers_sha256": _digest(item["identifiers"]),
        "domain_cells_sha256": item["domain_cells_sha256"], "domain_cell_count": item["domain_cell_count"], "domain_freeze_sha256": item["domain_freeze_sha256"],
        "normalisation": item["normalisation"], "occurrence_rows_downloaded": 0,
    }


def _run_species(root: Path, item: dict[str, Any], frame: pd.DataFrame | None = None, domain_ids: set[str] | None = None, receipt_path: Path | None = None) -> dict[str, Any]:
    frame = _domain_frame(root) if frame is None else frame
    domain_ids = set(frame["cell_id"].astype(str)) if domain_ids is None else domain_ids
    start = time.monotonic()
    total_frame = galah.atlas_counts(**item["total_query"])
    facet_frame = galah.atlas_counts(**item["facet_query"])
    elapsed = time.monotonic() - start
    _reject_partial(total_frame); _reject_partial(facet_frame)
    if list(total_frame.columns) != ["totalRecords"] or len(total_frame) != 1:
        raise Goal049CensusError("malformed total-count response")
    if set(facet_frame.columns) != {"lat_long", "count"} or facet_frame["lat_long"].isna().any():
        raise Goal049CensusError("lat_long facet unavailable or malformed")
    total = int(_integer_counts(total_frame, "totalRecords").iloc[0])
    facet_sum = int(_integer_counts(facet_frame, "count").sum())
    groups = len(facet_frame)
    limits = _config(root)["occurrence_contract"]["transport_ceiling"]
    if facet_sum != total:
        raise Goal049CensusError("lat_long facet sum does not conserve total")
    if groups > int(limits["lat_long_groups_per_species"]):
        raise Goal049CensusError("per-species facet-group ceiling exceeded")
    lat_origin, lon_origin = _grid_origin(frame)
    retained: set[str] = set()
    for label in facet_frame["lat_long"].astype(str):
        lat, lon = _parse_lat_long(label)
        cell = f"r{math.floor((lat - lat_origin) / 0.01):04d}c{math.floor((lon - lon_origin) / 0.01):04d}"
        if cell in domain_ids:
            retained.add(cell)
    del total_frame, facet_frame
    receipt_path = _cell_receipt_path(root, item["index"]) if receipt_path is None else receipt_path
    _atomic_write(receipt_path, _receipt_payload(item, sorted(retained), source="live_galah_aggregate"))
    counts = {"total_count": total, "facet_count_sum": facet_sum, "facet_group_count": groups}
    return {
        "schema_version": "goal049-species-checkpoint-v1", "status": "passed", "index": item["index"], "species": item["species"],
        "source": "live_galah_aggregate", "query_fingerprint": item["query_fingerprint"],
        "stage_a_freeze_sha256": item["stage_a_freeze_sha256"], **counts, "count_conservation_sha256": _digest(counts),
        "retained_species_cell_count": len(retained), "private_cell_receipt": str(receipt_path.relative_to(root)),
        "private_cell_receipt_sha256": _sha(receipt_path), "runtime_seconds": round(elapsed, 3),
        "occurrence_rows_downloaded": 0, "model_outcome_counter": 0,
    }


def _goal048_contract(root: Path) -> tuple[dict[str, Any], dict[str, Any], Path] | None:
    base = _private_goal048(root)
    taxonomy_path, domain_path, config_path = base / "taxonomy_freeze.json", base / "domain_freeze.json", Path(root) / "config/goal048_seawfb_bioregional_freeze.json"
    if not all(path.is_file() for path in (taxonomy_path, domain_path, config_path)):
        return None
    try:
        return json.loads(taxonomy_path.read_text()), json.loads(domain_path.read_text()), config_path
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049CensusError("Goal 048 promotion authority is unreadable") from error


def audit_goal048_receipt(root: Path, item: dict[str, Any], frame: pd.DataFrame, domain_ids: set[str]) -> dict[str, Any] | None:
    """Return a Goal 049 checkpoint only when a Goal 048 receipt is exact."""
    contract = _goal048_contract(root)
    if contract is None:
        return None
    old_taxonomy, old_domain, old_config_path = contract
    matching_rows = [row for row in old_taxonomy.get("rows", []) if row.get("ordered_identifiers") == item["identifiers"]]
    if len(matching_rows) != 1:
        return None
    old_row = matching_rows[0]
    old_species = old_row.get("seed_name") or old_row.get("species") or old_row.get("source_name")
    old_domain_path = _private_goal048(root) / "domain_cells.csv"
    old_domain_receipt_path = _private_goal048(root) / "domain_freeze.json"
    if not old_domain_path.is_file() or not old_domain_receipt_path.is_file() or _sha(old_domain_path) != item["domain_cells_sha256"] or _sha(old_domain_receipt_path) != item["domain_freeze_sha256"] or old_domain.get("cell_count") != item["domain_cell_count"]:
        return None
    old_config = json.loads(old_config_path.read_text())
    old_contract = old_config.get("aggregate_feasibility", {})
    if old_contract.get("filters", {}).get("years_inclusive") != [2001, 2025] or old_contract.get("filters", {}).get("occurrence_status") != "present" or old_contract.get("filters", {}).get("spatial_validity") != "valid_coordinate_required":
        return None
    candidates: list[dict[str, Any]] = []
    checkpoints = _private_goal048(root) / "census/checkpoints"
    if checkpoints.is_dir():
        for path in checkpoints.glob("*.json"):
            try:
                value = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if value.get("species") == old_species:
                candidates.append(value)
    canary_path = Path(root) / "evidence/seawfb_bioregional_freeze/goal048/aggregate_canary.json"
    if canary_path.is_file() and old_species == "Acanthiza pusilla":
        candidates.append(json.loads(canary_path.read_text()))
    if not candidates:
        return None
    old = candidates[0]
    expected_fp = _digest({"identifiers": item["identifiers"], "filters": item["total_query"]["filters"]})
    if old.get("query_fingerprint") != expected_fp or old.get("total_count") != old.get("facet_count_sum"):
        return None
    expected_conservation = _digest({"total_count": old.get("total_count"), "facet_count_sum": old.get("facet_count_sum"), "facet_group_count": old.get("facet_group_count")})
    if old.get("count_conservation_sha256") != expected_conservation:
        return None
    old_receipt_name = old.get("private_cell_receipt") or (str((_private_goal048(root) / "canary_species_cells.json").relative_to(root)) if "private_species_cell_sha256" in old else None)
    if not isinstance(old_receipt_name, str):
        return None
    old_receipt_path = Path(root) / old_receipt_name
    if not old_receipt_path.is_file() or (old.get("private_cell_receipt_sha256") and _sha(old_receipt_path) != old.get("private_cell_receipt_sha256")):
        if old.get("private_species_cell_sha256") and _sha(old_receipt_path) != old.get("private_species_cell_sha256"):
            return None
    try:
        old_cells = json.loads(old_receipt_path.read_text()).get("cells", [])
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(old_cells, list) or not set(old_cells).issubset(domain_ids) or old_cells != sorted(set(old_cells)):
        return None
    # Goal 048 used the same 0.01-degree floor transformation.  Comparing the
    # computed origins and domain bytes makes this an identity audit, not a
    # count-only shortcut.
    if _normalisation(frame) != item["normalisation"]:
        return None
    receipt_path = _cell_receipt_path(root, item["index"])
    _atomic_write(receipt_path, _receipt_payload(item, old_cells, source="promoted_goal048_receipt"))
    counts = {"total_count": int(old["total_count"]), "facet_count_sum": int(old["facet_count_sum"]), "facet_group_count": int(old["facet_group_count"])}
    return {
        "schema_version": "goal049-species-checkpoint-v1", "status": "passed", "index": item["index"], "species": item["species"],
        "source": "promoted_goal048_receipt", "query_fingerprint": item["query_fingerprint"], "stage_a_freeze_sha256": item["stage_a_freeze_sha256"],
        **counts, "count_conservation_sha256": _digest(counts), "retained_species_cell_count": len(old_cells),
        "private_cell_receipt": str(receipt_path.relative_to(root)), "private_cell_receipt_sha256": _sha(receipt_path),
        "goal048_private_cell_receipt": old_receipt_name, "occurrence_rows_downloaded": 0, "model_outcome_counter": 0,
    }


def _goal048_identifier_unions(root: Path) -> set[tuple[str, ...]]:
    contract = _goal048_contract(root)
    if contract is None:
        return set()
    taxonomy, _, _ = contract
    return {tuple(row.get("ordered_identifiers", [])) for row in taxonomy.get("rows", []) if isinstance(row.get("ordered_identifiers"), list)}


def _validate_checkpoint(root: Path, item: dict[str, Any], value: dict[str, Any], domain_ids: set[str]) -> dict[str, Any]:
    if value.get("index") != item["index"] or value.get("species") != item["species"] or value.get("query_fingerprint") != item["query_fingerprint"] or value.get("stage_a_freeze_sha256") != item["stage_a_freeze_sha256"]:
        raise Goal049CensusError("census checkpoint identity or Stage A drift")
    if value.get("status") != "passed" or value.get("total_count") != value.get("facet_count_sum") or value.get("count_conservation_sha256") != _digest({"total_count": value.get("total_count"), "facet_count_sum": value.get("facet_count_sum"), "facet_group_count": value.get("facet_group_count")}):
        raise Goal049CensusError("census checkpoint conservation drift")
    if value.get("occurrence_rows_downloaded") != 0 or value.get("model_outcome_counter") != 0:
        raise Goal049CensusError("census checkpoint privacy or forbidden-work counter failed")
    path = root / value.get("private_cell_receipt", "")
    if not path.is_file() or _sha(path) != value.get("private_cell_receipt_sha256"):
        raise Goal049CensusError("census private cell receipt checksum drift")
    cells = _validate_cell_receipt(root, item, path, domain_ids)
    if len(cells["cells"]) != value.get("retained_species_cell_count"):
        raise Goal049CensusError("census checkpoint cell count drift")
    return value


def load_resume_state(root: Path, plan: list[dict[str, Any]], domain_ids: set[str] | None = None) -> list[dict[str, Any]]:
    root = Path(root)
    private = _private(root)
    progress = root / PROGRESS_RELATIVE
    if any(private.rglob("*.tmp")) or progress.with_name(progress.name + ".tmp").exists():
        raise Goal049CensusError("incomplete atomic census write present")
    directory = private / "checkpoints"
    existing = sorted(directory.glob("*.json")) if directory.exists() else []
    if [path.name for path in existing] != [f"{index:05d}.json" for index in range(len(existing))] or len(existing) > len(plan):
        raise Goal049CensusError("census checkpoints are not a contiguous prefix")
    domain_ids = set(_domain_frame(root)["cell_id"].astype(str)) if domain_ids is None else domain_ids
    completed = [_validate_checkpoint(root, plan[index], json.loads(existing[index].read_text()), domain_ids) for index in range(len(existing))]
    actual = {path.resolve() for path in (private / "species_cells").glob("*.json")} if (private / "species_cells").exists() else set()
    referenced = {(root / row["private_cell_receipt"]).resolve() for row in completed}
    if actual != referenced:
        raise Goal049CensusError("orphan or missing Goal 049 species-cell receipt present")
    limit = int(_config(root)["occurrence_contract"]["transport_ceiling"]["lat_long_groups_total"])
    if sum(int(row["facet_group_count"]) for row in completed) > limit:
        raise Goal049CensusError("cumulative facet-group ceiling already exceeded")
    return completed


def _check_capacity(root: Path) -> tuple[int, int]:
    limits = _config(root)["occurrence_contract"]["transport_ceiling"]
    disk, ram = _private_disk_bytes(root), _peak_ram_bytes()
    if disk > int(float(limits["private_disk_gib"]) * 1024**3) or ram > int(float(limits["peak_ram_gib"]) * 1024**3):
        raise Goal049CensusError("census disk or RAM ceiling exceeded")
    return disk, ram


def _enforce_cumulative_groups(completed_groups: int, next_groups: int) -> int:
    observed = completed_groups + next_groups
    if observed > CENSUS_GROUP_LIMIT:
        raise Goal049CensusError("cumulative facet-group ceiling exceeded")
    return observed


def _progress(root: Path, plan: list[dict[str, Any]], completed: list[dict[str, Any]], status: str, stage_a: dict[str, Any]) -> dict[str, Any]:
    value = {
        "schema_version": "goal049-aggregate-census-progress-v1", "status": status,
        "stage_a_freeze_sha256": _sha(Path(root) / FREEZE_RELATIVE), "planned_species": len(plan),
        "completed_species": len(completed), "next_index": len(completed) if len(completed) < len(plan) else None,
        "cumulative_total_count": sum(int(row["total_count"]) for row in completed),
        "cumulative_facet_groups": sum(int(row["facet_group_count"]) for row in completed),
        "cumulative_retained_species_cells": sum(int(row["retained_species_cell_count"]) for row in completed),
        "checkpoint_inventory_sha256": _digest([_sha(_checkpoint_path(root, index)) for index in range(len(completed))]),
        "private_disk_bytes": _private_disk_bytes(root), "peak_ram_bytes_upper_bound": _peak_ram_bytes(),
        "occurrence_rows_downloaded": 0, "model_outcome_counter": 0,
    }
    _atomic_write(Path(root) / PROGRESS_RELATIVE, value)
    return value


def _write_canary_receipt(root: Path, item: dict[str, Any], checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Publish a tracked, coordinate-free canary summary."""
    private_path = Path(root) / checkpoint["private_cell_receipt"]
    value = {
        "schema_version": "goal049-live-canary-receipt-v1", "status": "passed", "species": item["species"],
        "source": checkpoint["source"], "total_count": checkpoint["total_count"],
        "facet_count_sum": checkpoint["facet_count_sum"], "facet_group_count": checkpoint["facet_group_count"],
        "query_fingerprint": item["query_fingerprint"], "identifiers_sha256": _digest(item["identifiers"]),
        "domain_cells_sha256": item["domain_cells_sha256"], "domain_cell_count": item["domain_cell_count"],
        "domain_freeze_sha256": item["domain_freeze_sha256"], "normalisation_sha256": _digest(item["normalisation"]),
        "stage_a_freeze_sha256": item["stage_a_freeze_sha256"],
        "count_conservation_sha256": checkpoint["count_conservation_sha256"], "runtime_seconds": checkpoint.get("runtime_seconds"),
        "private_cell_receipt": str(private_path.relative_to(root)), "private_cell_receipt_sha256": _sha(private_path),
        "occurrence_rows_downloaded": 0, "model_outcome_counter": 0,
    }
    _atomic_write(Path(root) / CANARY_RELATIVE, value)
    return value


def validate_canary(root: Path) -> dict[str, Any]:
    path = Path(root) / CANARY_RELATIVE
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Goal049CensusError("tracked canary receipt is unreadable") from error
    required = ("species", "source", "total_count", "facet_count_sum", "facet_group_count", "query_fingerprint", "identifiers_sha256", "domain_cells_sha256", "domain_cell_count", "domain_freeze_sha256", "normalisation_sha256", "stage_a_freeze_sha256", "count_conservation_sha256", "private_cell_receipt", "private_cell_receipt_sha256")
    if value.get("status") != "passed" or any(key not in value for key in required) or value.get("occurrence_rows_downloaded") != 0 or value.get("model_outcome_counter") != 0:
        raise Goal049CensusError("tracked canary receipt fields are incomplete")
    private = Path(root) / value["private_cell_receipt"]
    if not private.is_file() or _sha(private) != value["private_cell_receipt_sha256"]:
        raise Goal049CensusError("tracked canary private receipt checksum drift")
    if value["total_count"] != value["facet_count_sum"] or value["count_conservation_sha256"] != _digest({"total_count": value["total_count"], "facet_count_sum": value["facet_count_sum"], "facet_group_count": value["facet_group_count"]}):
        raise Goal049CensusError("tracked canary conservation drift")
    return {"status": value["status"], "species": value["species"], "source": value["source"], "private_cell_receipt_sha256": value["private_cell_receipt_sha256"]}


def _commit_checkpoint(root: Path, item: dict[str, Any], checkpoint: dict[str, Any], completed: list[dict[str, Any]], plan: list[dict[str, Any]], frame: pd.DataFrame, domain_ids: set[str], stage_a: dict[str, Any]) -> dict[str, Any]:
    observed = _enforce_cumulative_groups(sum(int(row["facet_group_count"]) for row in completed), int(checkpoint["facet_group_count"]))
    disk, ram = _check_capacity(root)
    checkpoint["private_disk_bytes_after"], checkpoint["peak_ram_bytes_upper_bound"] = disk, ram
    _atomic_write(_checkpoint_path(root, item["index"]), checkpoint)
    value = _validate_checkpoint(root, item, json.loads(_checkpoint_path(root, item["index"]).read_text()), domain_ids)
    completed.append(value)
    _progress(root, plan, completed, "running" if len(completed) < len(plan) else "complete", stage_a)
    return value


def census_preflight(root: Path) -> dict[str, Any]:
    stage_a = _stage_a(root)
    plan = build_census_plan(root)
    frame = _domain_frame(root)
    completed = load_resume_state(root, plan, set(frame["cell_id"].astype(str)))
    _check_capacity(root)
    return {"status": "ready", "planned_species": len(plan), "completed_species": len(completed), "remaining_species": len(plan) - len(completed), "plan_sha256": _digest([{key: item[key] for key in ("index", "species", "query_fingerprint")} for item in plan]), "stage_a_freeze_sha256": _sha(Path(root) / FREEZE_RELATIVE), "occurrence_rows_downloaded": 0, "model_outcome_counter": 0}


def run_canary(root: Path) -> dict[str, Any]:
    stage_a = _stage_a(root); plan = build_census_plan(root)
    if not plan:
        raise Goal049CensusError("census plan has no active species")
    frame = _domain_frame(root); domain_ids = set(frame["cell_id"].astype(str)); completed = load_resume_state(root, plan, domain_ids)
    if len(completed) >= len(plan):
        raise Goal049CensusError("no incomplete species remains for a live canary")
    old_unions = _goal048_identifier_unions(root)
    item = next((candidate for candidate in plan[len(completed):] if tuple(candidate["identifiers"]) not in old_unions), None)
    if item is None:
        raise Goal049CensusError("no genuinely new species remains for a live canary")
    galah.galah_config(atlas="Australia", authenticate=False, verbose=False, timeout=600)
    canary_receipt = _cell_receipt_path(root, item["index"]) if item["index"] == len(completed) else _private(root) / "canary_species_cells.json"
    checkpoint = _run_species(root, item, frame, domain_ids, canary_receipt)
    _write_canary_receipt(root, item, checkpoint)
    if item["index"] == len(completed):
        _commit_checkpoint(root, item, checkpoint, completed, plan, frame, domain_ids, stage_a)
    return checkpoint


def run_census(root: Path) -> dict[str, Any]:
    stage_a = _stage_a(root); plan = build_census_plan(root)
    frame = _domain_frame(root); domain_ids = set(frame["cell_id"].astype(str)); completed = load_resume_state(root, plan, domain_ids)
    _progress(root, plan, completed, "running", stage_a)
    try:
        galah.galah_config(atlas="Australia", authenticate=False, verbose=False, timeout=600)
        for item in plan[len(completed):]:
            checkpoint = audit_goal048_receipt(root, item, frame, domain_ids)
            if checkpoint is None:
                checkpoint = _run_species(root, item, frame, domain_ids)
            try:
                _commit_checkpoint(root, item, checkpoint, completed, plan, frame, domain_ids, stage_a)
            except Exception:
                if checkpoint.get("source") in {"live_galah_aggregate", "promoted_goal048_receipt"}:
                    (root / checkpoint["private_cell_receipt"]).unlink(missing_ok=True)
                _checkpoint_path(root, item["index"]).unlink(missing_ok=True)
                raise
        result = _progress(root, plan, completed, "complete", stage_a)
        _atomic_write(_private(root) / "run.exit", {"status": "complete", "completed_species": len(completed), "cumulative_facet_groups": result["cumulative_facet_groups"]})
        return result
    except Exception as error:
        _progress(root, plan, completed, "blocked", stage_a)
        _atomic_write(_private(root) / "run.exit", {"status": "blocked", "completed_species": len(completed), "error_type": type(error).__name__, "error": "transport_or_validation_failure"})
        raise Goal049CensusError(f"census stopped fail-closed: {type(error).__name__}") from None


def census_status(root: Path) -> dict[str, Any]:
    progress = Path(root) / PROGRESS_RELATIVE
    exit_path = _private(root) / "run.exit"
    return {"progress": json.loads(progress.read_text()) if progress.exists() else {"status": "not_started"}, "run_exit": json.loads(exit_path.read_text()) if exit_path.exists() else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preflight", "canary", "validate-canary", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = census_preflight(args.root) if args.stage == "preflight" else run_canary(args.root) if args.stage == "canary" else validate_canary(args.root) if args.stage == "validate-canary" else run_census(args.root) if args.stage == "run" else census_status(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
