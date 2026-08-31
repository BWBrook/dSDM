"""Resumable sequential aggregate census for the frozen Goal 048 seed ledger."""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any
from re import fullmatch

import galah
import pandas as pd

from goal048_seawfb_bioregional_freeze import (
    Goal048Error,
    _digest,
    _private,
    _require_galah_overlay,
    _sha,
    compile_query,
    validate,
    validate_freezes,
)


CENSUS_GROUP_LIMIT = 10_000_000
TAXON_GROUP_LIMIT = 750_000
DISK_LIMIT = 4_294_967_296
RAM_LIMIT = 8_589_934_592
CELL_ID_PATTERN = r"r[0-9]{4,}c[0-9]{4,}"


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _census_root(root: Path) -> Path:
    return _private(root) / "census"


def _progress_path(root: Path) -> Path:
    return root / "evidence/seawfb_bioregional_freeze/goal048/aggregate_census_progress.json"


def _peak_ram_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _private_disk_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in _private(root).rglob("*") if path.is_file())


def _query_pair(taxon: dict[str, Any], domain: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    box = domain["bbox"]
    filters = [
        "year>=2001",
        "year<=2025",
        "occurrenceStatus=PRESENT",
        "spatiallyValid=true",
        f"decimalLongitude>={box['xmin']}",
        f"decimalLongitude<={box['xmax']}",
        f"decimalLatitude>={box['ymin']}",
        f"decimalLatitude<={box['ymax']}",
    ]
    total = compile_query(taxon["ordered_identifiers"], filters, None)
    facet = compile_query(taxon["ordered_identifiers"], filters, "lat_long")
    if total["identifiers"] != facet["identifiers"] or total["filters"] != facet["filters"]:
        raise Goal048Error("total/facet query identity mismatch")
    fingerprint = _digest({"identifiers": total["identifiers"], "filters": total["filters"]})
    return total, facet, fingerprint


def _role_partition(root: Path, names: list[str], manifest: dict[str, Any]) -> dict[str, Any]:
    role_path = _private(root) / "role_freeze.json"
    role = json.loads(role_path.read_text())
    rows = role.get("rows", [])
    if role.get("row_count") != 100 or [row.get("name") for row in rows] != names:
        raise Goal048Error("frozen role ledger order drift")
    if role.get("role_counts", {}).get("effort") != 96:
        raise Goal048Error("frozen role ledger effort partition drift")
    eligible = [row for row in rows if row.get("effort") is True]
    excluded = [
        {"name": row["name"], "status": "not_queried_frozen_role_exclusion", "reason": row.get("reason", "")}
        for row in rows
        if row.get("effort") is not True
    ]
    if len(eligible) != 96 or len(excluded) != 4:
        raise Goal048Error("frozen role ledger exclusion partition drift")
    return {
        "eligible": eligible,
        "excluded": excluded,
        "receipt_sha256": manifest["roles"]["private_receipt_sha256"],
    }


def build_census_plan(root: Path) -> list[dict[str, Any]]:
    validation = validate_freezes(root)
    manifest = validation if "roles" in validation else json.loads((root / "metadata/goal048_prerequisite_freeze.json").read_text())
    config = json.loads((root / "config/goal048_seawfb_bioregional_freeze.json").read_text())
    taxonomy = json.loads((_private(root) / "taxonomy_freeze.json").read_text())
    domain = json.loads((_private(root) / "domain_freeze.json").read_text())
    names = config["species_universes"]["ecological_candidate_names"]
    rows = taxonomy["rows"]
    if len(names) != 100 or [row["seed_name"] for row in rows] != names:
        raise Goal048Error("frozen census species order drift")
    roles = _role_partition(root, names, manifest)
    plan = []
    eligible_names = {item["name"] for item in roles["eligible"]}
    for index, row in enumerate(row for row in rows if row["seed_name"] in eligible_names):
        total, facet, fingerprint = _query_pair(row, domain)
        plan.append(
            {
                "index": index,
                "species": row["seed_name"],
                "role_receipt_sha256": roles["receipt_sha256"],
                "query_fingerprint": fingerprint,
                "total_query": total,
                "facet_query": facet,
            }
        )
    if len(plan) != 96 or len({item["query_fingerprint"] for item in plan}) != 96:
        raise Goal048Error("census query fingerprints are not unique")
    return plan


def _checkpoint_path(root: Path, index: int) -> Path:
    return _census_root(root) / "checkpoints" / f"{index:03d}.json"


def _cell_receipt_path(root: Path, index: int) -> Path:
    return _census_root(root) / "cells" / f"{index:03d}.json"


def _validate_checkpoint(root: Path, item: dict[str, Any], prerequisite_sha: str, domain_ids: set[str] | None = None) -> dict[str, Any]:
    value = json.loads(_checkpoint_path(root, item["index"]).read_text())
    if value.get("index") != item["index"] or value.get("species") != item["species"]:
        raise Goal048Error("census checkpoint identity drift")
    if value.get("query_fingerprint") != item["query_fingerprint"] or value.get("prerequisite_joint_sha256") != prerequisite_sha or (item.get("role_receipt_sha256") is not None and value.get("role_receipt_sha256") != item["role_receipt_sha256"]):
        raise Goal048Error("census checkpoint authority drift")
    source = value.get("source")
    expected_receipt = (
        _private(root) / "canary_species_cells.json"
        if source == "validated_goal048_canary"
        else _cell_receipt_path(root, item["index"])
        if source == "live_galah_aggregate"
        else None
    )
    receipt_name = value.get("private_cell_receipt")
    cells = root / receipt_name if isinstance(receipt_name, str) else Path()
    expected_name = str(expected_receipt.relative_to(root)) if expected_receipt is not None else None
    if expected_receipt is None or receipt_name != expected_name or cells != expected_receipt or not cells.is_file() or _sha(cells) != value.get("private_cell_receipt_sha256"):
        raise Goal048Error("census private cell receipt drift")
    expected_counts = _digest(
        {
            "total_count": value.get("total_count"),
            "facet_count_sum": value.get("facet_count_sum"),
            "facet_group_count": value.get("facet_group_count"),
        }
    )
    if value.get("status") != "passed" or value.get("total_count") != value.get("facet_count_sum") or value.get("count_conservation_sha256") != expected_counts:
        raise Goal048Error("census checkpoint conservation drift")
    if not 0 <= int(value.get("facet_group_count", -1)) <= TAXON_GROUP_LIMIT:
        raise Goal048Error("census checkpoint per-taxon ceiling drift")
    cell_value = _validate_cell_receipt(root, item, cells, domain_ids)
    if len(cell_value["cells"]) != value.get("retained_species_cell_count"):
        raise Goal048Error("census checkpoint cell count drift")
    return value


def load_resume_state(root: Path, plan: list[dict[str, Any]], domain_ids: set[str] | None = None) -> list[dict[str, Any]]:
    prerequisite = json.loads((root / "metadata/goal048_prerequisite_freeze.json").read_text())["joint_sha256"]
    census_root = _census_root(root)
    checkpoint_dir = census_root / "checkpoints"
    if any(census_root.rglob("*.tmp")) or _progress_path(root).with_name(_progress_path(root).name + ".tmp").exists():
        raise Goal048Error("incomplete atomic census write present")
    existing = sorted(checkpoint_dir.glob("*.json")) if checkpoint_dir.exists() else []
    expected_names = [f"{index:03d}.json" for index in range(len(existing))]
    if [path.name for path in existing] != expected_names or len(existing) > len(plan):
        raise Goal048Error("census checkpoints are not a contiguous prefix")
    domain_ids = _domain_cell_ids(root) if domain_ids is None else domain_ids
    completed = [_validate_checkpoint(root, plan[index], prerequisite, domain_ids) for index in range(len(existing))]
    referenced_live_receipts = {
        (root / row["private_cell_receipt"]).resolve()
        for row in completed
        if row["source"] == "live_galah_aggregate"
    }
    actual_live_receipts = {path.resolve() for path in (census_root / "cells").glob("*.json")}
    if actual_live_receipts != referenced_live_receipts:
        raise Goal048Error("orphan or missing census cell receipt present")
    if sum(int(value["facet_group_count"]) for value in completed) > CENSUS_GROUP_LIMIT:
        raise Goal048Error("census cumulative group ceiling already exceeded")
    return completed


def _check_capacity(root: Path) -> tuple[int, int]:
    private = _private(root)
    private.mkdir(parents=True, exist_ok=True)
    disk = _private_disk_bytes(root)
    ram = _peak_ram_bytes()
    if disk > DISK_LIMIT or ram > RAM_LIMIT:
        raise Goal048Error("census disk or RAM ceiling exceeded")
    return disk, ram


def _enforce_cumulative_groups(completed_groups: int, next_groups: int) -> int:
    observed = completed_groups + next_groups
    if observed > CENSUS_GROUP_LIMIT:
        raise Goal048Error("observed cumulative census group ceiling exceeded")
    return observed


def _progress(root: Path, plan: list[dict[str, Any]], completed: list[dict[str, Any]], status: str) -> dict[str, Any]:
    checkpoint_hashes = [_sha(_checkpoint_path(root, index)) for index in range(len(completed))]
    value = {
        "schema_version": "goal048-aggregate-census-progress-v1",
        "status": status,
        "planned_species": len(plan),
        "frozen_role_exclusions": _frozen_role_exclusions(root),
        "completed_species": len(completed),
        "next_index": len(completed) if len(completed) < len(plan) else None,
        "cumulative_total_count": sum(int(row["total_count"]) for row in completed),
        "cumulative_facet_groups": sum(int(row["facet_group_count"]) for row in completed),
        "cumulative_retained_species_cells": sum(int(row["retained_species_cell_count"]) for row in completed),
        "checkpoint_inventory_sha256": _digest(checkpoint_hashes),
        "private_disk_bytes": _private_disk_bytes(root),
        "peak_ram_bytes_upper_bound": _peak_ram_bytes(),
        "occurrence_rows_downloaded": 0,
        "model_outcome_counter": 0,
    }
    _atomic_write(_progress_path(root), value)
    return value


def _reuse_canary(root: Path, item: dict[str, Any], prerequisite_sha: str, domain_ids: set[str] | None = None) -> dict[str, Any]:
    validate(root)
    canary = json.loads((root / "evidence/seawfb_bioregional_freeze/goal048/aggregate_canary.json").read_text())
    cells = _private(root) / "canary_species_cells.json"
    if item["species"] != "Acanthiza pusilla" or canary["query_fingerprint"] != item["query_fingerprint"]:
        raise Goal048Error("canary query is not reusable")
    if canary["prerequisite_joint_sha256"] != prerequisite_sha or _sha(cells) != canary["private_species_cell_sha256"]:
        raise Goal048Error("canary prerequisite or private cell receipt drift")
    _validate_cell_receipt(root, item, cells, domain_ids)
    return {
        "schema_version": "goal048-private-species-checkpoint-v1",
        "status": "passed",
        "index": item["index"],
        "species": item["species"],
        "source": "validated_goal048_canary",
        "query_fingerprint": item["query_fingerprint"],
        "role_receipt_sha256": item.get("role_receipt_sha256"),
        "prerequisite_joint_sha256": prerequisite_sha,
        "total_count": canary["total_count"],
        "facet_count_sum": canary["facet_count_sum"],
        "facet_group_count": canary["facet_group_count"],
        "count_conservation_sha256": canary["count_conservation_sha256"],
        "retained_species_cell_count": canary["retained_species_cell_count"],
        "private_cell_receipt": str(cells.relative_to(root)),
        "private_cell_receipt_sha256": _sha(cells),
        "runtime_seconds": canary["runtime_seconds"],
        "occurrence_rows_downloaded": 0,
    }


def _domain_cell_frame(root: Path) -> pd.DataFrame:
    frame = pd.read_csv(_private(root) / "domain_cells.csv")
    required = {"cell_id", "row", "column"}
    if not required.issubset(frame.columns) or frame["cell_id"].isna().any():
        raise Goal048Error("domain cell ledger is malformed")
    return frame


def _domain_cell_ids(root: Path, frame: pd.DataFrame | None = None) -> set[str]:
    frame = _domain_cell_frame(root) if frame is None else frame
    if not {"cell_id"}.issubset(frame.columns) or frame["cell_id"].isna().any():
        raise Goal048Error("domain cell ledger is malformed")
    ids = frame["cell_id"].astype(str).tolist()
    if len(ids) != len(set(ids)):
        raise Goal048Error("domain cell ledger contains duplicate IDs")
    return set(ids)


def _frozen_role_exclusions(root: Path) -> list[dict[str, Any]]:
    role = json.loads((_private(root) / "role_freeze.json").read_text())
    return [
        {"name": row["name"], "status": "not_queried_frozen_role_exclusion", "reason": row.get("reason", "")}
        for row in role.get("rows", [])
        if row.get("effort") is not True
    ]


def _validate_cell_receipt(root: Path, item: dict[str, Any], path: Path, domain_ids: set[str] | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise Goal048Error("census private cell receipt is unreadable") from error
    cells = value.get("cells")
    if value.get("species") != item["species"] or not isinstance(cells, list):
        raise Goal048Error("census private cell receipt identity drift")
    if any(not isinstance(cell, str) or fullmatch(CELL_ID_PATTERN, cell) is None for cell in cells):
        raise Goal048Error("census private cell receipt contains malformed cell ID")
    if cells != sorted(set(cells)):
        raise Goal048Error("census private cell receipt is not canonical")
    domain_ids = _domain_cell_ids(root) if domain_ids is None else domain_ids
    if not set(cells).issubset(domain_ids):
        raise Goal048Error("census private cell receipt contains an out-of-domain cell")
    return value


def _integer_counts(frame: pd.DataFrame, column: str) -> pd.Series:
    counts = pd.to_numeric(frame[column], errors="coerce")
    if counts.isna().any() or (counts < 0).any() or (counts % 1 != 0).any():
        raise Goal048Error("aggregate response contains malformed counts")
    return counts.astype("int64")


def _reject_partial_response(frame: pd.DataFrame) -> None:
    for key in ("truncated", "is_truncated", "partial"):
        if bool(frame.attrs.get(key, False)):
            raise Goal048Error("aggregate response indicates truncation")
    warnings = frame.attrs.get("warnings")
    if warnings:
        raise Goal048Error("aggregate response contains warnings")


def _grid_origin(cells: pd.DataFrame) -> tuple[float, float]:
    if not {"row", "column", "longitude", "latitude"}.issubset(cells.columns):
        raise Goal048Error("domain cell ledger is missing grid columns")
    south = cells.loc[cells["latitude"].idxmin()]
    west = cells.loc[cells["longitude"].idxmin()]
    return float(south["latitude"]) - 0.005 - int(south["row"]) * 0.01, float(west["longitude"]) - 0.005 - int(west["column"]) * 0.01


def _run_species(root: Path, item: dict[str, Any], prerequisite_sha: str, domain_frame: pd.DataFrame | None = None, domain_ids: set[str] | None = None) -> dict[str, Any]:
    start = time.monotonic()
    total_frame = galah.atlas_counts(**item["total_query"])
    facet_frame = galah.atlas_counts(**item["facet_query"])
    elapsed = time.monotonic() - start
    _reject_partial_response(total_frame)
    _reject_partial_response(facet_frame)
    if list(total_frame.columns) != ["totalRecords"] or len(total_frame) != 1:
        raise Goal048Error("malformed total-count response")
    total = int(_integer_counts(total_frame, "totalRecords").iloc[0])
    if set(facet_frame.columns) != {"lat_long", "count"} or facet_frame["lat_long"].isna().any() or facet_frame["lat_long"].astype(str).str.strip().eq("").any():
        raise Goal048Error("lat_long facet unavailable, malformed, or missing coordinate")
    groups = len(facet_frame)
    facet_sum = int(_integer_counts(facet_frame, "count").sum())
    if facet_sum != total:
        raise Goal048Error("lat_long facet sum does not conserve total")
    if groups > TAXON_GROUP_LIMIT:
        raise Goal048Error("per-taxon facet-group ceiling exceeded")
    cells = _domain_cell_frame(root) if domain_frame is None else domain_frame
    domain_ids = _domain_cell_ids(root, cells) if domain_ids is None else domain_ids
    lat_origin, lon_origin = _grid_origin(cells)
    retained = set()
    for value in facet_frame["lat_long"].astype(str):
        parts = value.replace("[", "").replace("]", "").split(",")
        if len(parts) != 2:
            raise Goal048Error("malformed lat_long facet label")
        try:
            lat, lon = map(float, parts)
        except ValueError as error:
            raise Goal048Error("non-numeric lat_long facet label") from error
        if not math.isfinite(lat) or not math.isfinite(lon):
            raise Goal048Error("non-finite lat_long facet label")
        row = math.floor((lat - lat_origin) / 0.01)
        column = math.floor((lon - lon_origin) / 0.01)
        cell_id = f"r{row:04d}c{column:04d}"
        if cell_id in domain_ids:
            retained.add(cell_id)
    del total_frame, facet_frame
    receipt_path = _cell_receipt_path(root, item["index"])
    _atomic_write(
        receipt_path,
        {
            "schema_version": "goal048-private-species-cells-v1",
            "species": item["species"],
            "cells": sorted(retained),
        },
    )
    counts = {"total_count": total, "facet_count_sum": facet_sum, "facet_group_count": groups}
    return {
        "schema_version": "goal048-private-species-checkpoint-v1",
        "status": "passed",
        "index": item["index"],
        "species": item["species"],
        "source": "live_galah_aggregate",
        "query_fingerprint": item["query_fingerprint"],
        "role_receipt_sha256": item.get("role_receipt_sha256"),
        "prerequisite_joint_sha256": prerequisite_sha,
        **counts,
        "count_conservation_sha256": _digest(counts),
        "retained_species_cell_count": len(retained),
        "private_cell_receipt": str(receipt_path.relative_to(root)),
        "private_cell_receipt_sha256": _sha(receipt_path),
        "runtime_seconds": round(elapsed, 3),
        "occurrence_rows_downloaded": 0,
    }


def _prepare_census(root: Path) -> tuple[list[dict[str, Any]], str, list[dict[str, Any]], pd.DataFrame, set[str]]:
    _require_galah_overlay()
    plan = build_census_plan(root)
    prerequisite_sha = json.loads((root / "metadata/goal048_prerequisite_freeze.json").read_text())["joint_sha256"]
    domain_frame = _domain_cell_frame(root)
    domain_ids = _domain_cell_ids(root, domain_frame)
    canary_item = next(item for item in plan if item["species"] == "Acanthiza pusilla")
    _reuse_canary(root, canary_item, prerequisite_sha, domain_ids)
    completed = load_resume_state(root, plan, domain_ids)
    _check_capacity(root)
    return plan, prerequisite_sha, completed, domain_frame, domain_ids


def census_preflight(root: Path) -> dict[str, Any]:
    plan, _, completed, _, _ = _prepare_census(root)
    exclusions = _frozen_role_exclusions(root)
    return {
        "status": "ready",
        "planned_species": len(plan),
        "queried_species": len(plan),
        "frozen_role_exclusion_count": len(exclusions),
        "frozen_role_exclusions": exclusions,
        "completed_species": len(completed),
        "remaining_species": len(plan) - len(completed),
        "canary_reusable": True,
        "plan_sha256": _digest([{"index": item["index"], "species": item["species"], "query_fingerprint": item["query_fingerprint"], "role_receipt_sha256": item["role_receipt_sha256"]} for item in plan]),
        "cumulative_facet_groups": sum(int(row["facet_group_count"]) for row in completed),
        "private_disk_bytes": _private_disk_bytes(root),
        "peak_ram_bytes_upper_bound": _peak_ram_bytes(),
    }


def run_census(root: Path) -> dict[str, Any]:
    plan, prerequisite_sha, completed, domain_frame, domain_ids = _prepare_census(root)
    exit_path = _census_root(root) / "run.exit"
    exit_path.unlink(missing_ok=True)
    galah.galah_config(atlas="Australia", authenticate=False, verbose=False, timeout=600)
    _progress(root, plan, completed, "running")
    try:
        for item in plan[len(completed) :]:
            checkpoint = _reuse_canary(root, item, prerequisite_sha, domain_ids) if item["species"] == "Acanthiza pusilla" else _run_species(root, item, prerequisite_sha, domain_frame, domain_ids)
            try:
                _enforce_cumulative_groups(
                    sum(int(row["facet_group_count"]) for row in completed),
                    int(checkpoint["facet_group_count"]),
                )
                disk, ram = _check_capacity(root)
                checkpoint["private_disk_bytes_after"] = disk
                checkpoint["peak_ram_bytes_upper_bound"] = ram
                _atomic_write(_checkpoint_path(root, item["index"]), checkpoint)
            except Exception:
                if checkpoint.get("source") == "live_galah_aggregate":
                    (root / checkpoint["private_cell_receipt"]).unlink(missing_ok=True)
                raise
            completed.append(_validate_checkpoint(root, item, prerequisite_sha, domain_ids))
            _progress(root, plan, completed, "running" if len(completed) < len(plan) else "complete")
        result = _progress(root, plan, completed, "complete")
        _atomic_write(
            exit_path,
            {
                "status": "complete",
                "completed_species": len(completed),
                "cumulative_facet_groups": result["cumulative_facet_groups"],
            },
        )
        return result
    except Exception as error:
        _progress(root, plan, completed, "blocked")
        _atomic_write(
            exit_path,
            {
                "status": "blocked",
                "completed_species": len(completed),
                "error_type": type(error).__name__,
                "error": "transport_or_validation_failure",
            },
        )
        raise Goal048Error(f"census stopped fail-closed: {type(error).__name__}") from None


def census_status(root: Path) -> dict[str, Any]:
    progress_path = _progress_path(root)
    exit_path = _census_root(root) / "run.exit"
    return {
        "progress": json.loads(progress_path.read_text()) if progress_path.exists() else {"status": "not_started"},
        "run_exit": json.loads(exit_path.read_text()) if exit_path.exists() else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["preflight", "run", "status"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = census_preflight(args.root) if args.stage == "preflight" else run_census(args.root) if args.stage == "run" else census_status(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
