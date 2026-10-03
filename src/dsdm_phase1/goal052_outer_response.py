"""Gated Goal 049 response loading for the Goal 052 outer assessment.

The outer closure is verified before this module reads any canonical response
rows.  The response loader then reconstructs full-domain target presences and
focal-excluded effort richness in the exact order stored by ``domain.npz``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pyarrow.parquet as pq

from .goal052_outer_artifacts import read_json, sha256_file, verify_closure, write_once


class Goal052OuterResponseError(ValueError):
    """Raised when the gated canonical response contract is not satisfied."""


EXPECTED_TARGET_COUNT = 157
CANONICAL_SCHEMA = ["species", "cell_id"]
REGIONS = ("NCP", "SEH", "NNC")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Goal052OuterResponseError(message)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _array_digest(value: np.ndarray, dtype: str) -> str:
    return _sha256_bytes(np.ascontiguousarray(value, dtype=dtype).tobytes(order="C"))


def _string_digest(values: list[str]) -> str:
    return _sha256_bytes(("\n".join(values) + "\n").encode())


def _safe_path(root: Path, relative: str, label: str) -> Path:
    path = (root / str(relative)).resolve()
    _require(path.is_relative_to(root.resolve()), f"{label}_path_escape")
    _require(path.is_file(), f"{label}_missing")
    return path


def _panel_targets(summary: Mapping[str, Any]) -> list[str]:
    _require(summary.get("status") == "frozen", "panel_summary_not_frozen")
    _require(tuple(summary.get("regions", ())) == REGIONS, "panel_regions_drift")
    primary = summary.get("primary_common", {})
    regional = summary.get("secondary_region_specific", {})
    _require(isinstance(primary, Mapping) and isinstance(regional, Mapping), "panel_membership_missing")
    _require(int(primary.get("count", -1)) == len(primary.get("species", ())), "primary_panel_count_drift")
    _require(int(primary.get("count", -1)) == 73, "primary_panel_inventory_drift")
    expected_regional = {"NCP": 88, "SEH": 122, "NNC": 134}
    selected: set[str] = set(map(str, primary.get("species", ())))
    _require(len(selected) == 73, "primary_panel_identity_drift")
    for region in REGIONS:
        item = regional.get(region, {})
        _require(isinstance(item, Mapping), f"regional_panel_missing:{region}")
        species = [str(value) for value in item.get("species", ())]
        _require(int(item.get("count", -1)) == len(species), f"regional_panel_count_drift:{region}")
        _require(int(item.get("count", -1)) == expected_regional[region], f"regional_panel_inventory_drift:{region}")
        _require(len(set(species)) == len(species) and set(primary.get("species", ())).issubset(species), f"regional_panel_membership_drift:{region}")
        selected.update(species)
    targets = sorted(selected)
    _require(len(targets) == EXPECTED_TARGET_COUNT, "target_panel_count_drift")
    return targets


def _read_domain(run: Path, closure: Mapping[str, Any]) -> tuple[np.ndarray, str]:
    domain_path = run / "domain.npz"
    _require(domain_path.is_file(), "outer_domain_missing")
    expected_hash = closure.get("files", {}).get("domain.npz")
    _require(isinstance(expected_hash, str) and sha256_file(domain_path) == expected_hash, "outer_domain_hash_drift")
    with np.load(domain_path, allow_pickle=False) as payload:
        _require("cell_ids" in payload.files, "outer_domain_cell_ids_missing")
        cell_ids = np.asarray(payload["cell_ids"], dtype=str)
    _require(cell_ids.ndim == 1 and len(cell_ids) > 0, "outer_domain_cell_ids_invalid")
    _require(len(set(cell_ids.tolist())) == len(cell_ids), "outer_domain_cell_ids_duplicate")
    expected_rows = int(closure.get("domain", {}).get("rows", -1))
    _require(len(cell_ids) == expected_rows, "outer_domain_row_count_drift")
    return cell_ids, _string_digest(cell_ids.tolist())


def _metadata_before_response_read(root: Path, closure: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Path, Path, Path, str, str, list[str], set[str] | None]:
    """Read only frozen JSON metadata needed to bind the response source."""
    config_path = root / "config/goal049_seawfb_canonical_response.json"
    config = read_json(config_path)
    tracked = config.get("tracked_outputs", {})
    completion_path = _safe_path(root, tracked.get("completion", ""), "completion_receipt")
    panel_path = _safe_path(root, tracked.get("panel_summary", ""), "panel_summary")
    completion = read_json(completion_path)
    panel = read_json(panel_path)
    bindings = completion.get("bindings", {})
    panel_bindings = panel.get("bindings", {})
    _require(config.get("schema_version") == "1.0" and config.get("goal_id") == "049", "goal049_config_identity_drift")
    _require(completion.get("schema_version") == "goal049-canonical-response-completion-v1", "completion_schema_drift")
    _require(panel.get("schema_version") == "goal049-panel-summary-v1", "panel_schema_drift")
    _require(completion.get("status") == "complete", "goal049_completion_not_complete")
    _require(completion.get("privacy") == {
        "coordinates_written": False,
        "private_species_cell_lists_written": False,
        "raw_occurrence_rows": 0,
        "model_outcomes": 0,
    }, "goal049_privacy_drift")
    _require(panel.get("privacy") == {
        "coordinates_written": False,
        "private_lists_written": False,
        "raw_occurrence_rows": 0,
        "model_outcomes": 0,
    }, "panel_privacy_drift")
    _require(tuple(completion.get("regions", REGIONS)) == REGIONS, "completion_regions_drift")
    invariants = completion.get("scientific_invariants", {})
    _require(invariants.get("focal_excluded_from_donor_richness") is True, "completion_focal_exclusion_drift")
    _require(invariants.get("focal_absent_richness_identity_verified") is True, "completion_focal_identity_drift")
    _require(invariants.get("richness_used_as_predictor") is False, "completion_richness_predictor_drift")
    _require(bindings.get("config_sha256") == sha256_file(config_path), "goal049_config_binding_drift")
    _require(bindings.get("panel_summary_sha256") == sha256_file(panel_path), "goal049_panel_summary_binding_drift")
    _require(panel_bindings.get("completion_config_sha256") == bindings.get("config_sha256"), "panel_completion_config_binding_drift")
    _require(panel.get("two_of_three_panel") is False and panel.get("x20_changes_membership") is False, "panel_semantics_drift")
    canonical_relative = completion.get("private_outputs", {}).get("canonical_species_cells")
    config_private = config.get("private_outputs", {})
    configured_canonical = str(Path(config_private.get("root", "")) / str(config_private.get("canonical_memberships", ""))) if config_private.get("root") else config_private.get("canonical_memberships")
    _require(canonical_relative == configured_canonical, "canonical_path_binding_drift")
    panel_ledger_relative = completion.get("private_outputs", {}).get("panel_ledger")
    if config_private.get("root") and config_private.get("panel_ledger"):
        _require(panel_ledger_relative == str(Path(config_private["root"]) / str(config_private["panel_ledger"])), "panel_ledger_path_binding_drift")
    canonical_path = (root / str(canonical_relative)).resolve()
    _require(canonical_path.is_relative_to(root.resolve()), "canonical_path_escape")
    expected_canonical_hash = bindings.get("canonical_species_cells_sha256")
    _require(isinstance(expected_canonical_hash, str), "canonical_hash_binding_missing")
    _require(panel_bindings.get("canonical_species_cells_sha256") == expected_canonical_hash, "panel_canonical_binding_drift")
    _require(panel_bindings.get("panel_ledger_sha256") == bindings.get("panel_ledger_sha256"), "panel_ledger_binding_drift")
    counts = completion.get("counts", {})
    donor_values = completion.get("effort_species", completion.get("effort_donor_species"))
    if donor_values is not None:
        _require(isinstance(donor_values, list) and len(set(map(str, donor_values))) == len(donor_values), "effort_donor_metadata_invalid")
        donor_species: set[str] | None = set(map(str, donor_values))
        _require(len(donor_species) == int(counts.get("effort_donors", -1)), "effort_donor_metadata_count_drift")
    else:
        _require(int(counts.get("effort_donors", -1)) == int(counts.get("active_species", -2)), "effort_donor_inventory_ambiguous")
        donor_species = None
    target_names = _panel_targets(panel)
    _require(int(counts.get("common_primary_targets", len(panel.get("primary_common", {}).get("species", ())))) == 73, "completion_primary_panel_drift")
    return config, completion, completion_path, panel_path, canonical_path, expected_canonical_hash, _string_digest(target_names), target_names, donor_species


def _write_access_started(run: Path, closure: Mapping[str, Any], canonical_hash: str, target_digest: str, domain_rows: int) -> Path:
    closure_path = run / "closure.json"
    access = {
        "schema_version": "goal052-outer-response-access-v1",
        "status": "response_access_started",
        "immutable": True,
        "closure_file_sha256": sha256_file(closure_path),
        "closure_digest": closure.get("closure_digest"),
        "plan_digest": closure.get("plan_digest"),
        "canonical_species_cells_sha256": canonical_hash,
        "target_inventory_sha256": target_digest,
        "domain_rows": int(domain_rows),
        "response_rows_read": None,
        "success_receipt": "response-access-success.json",
    }
    write_once(run / "response-access.json", access)
    return run / "response-access.json"


def _read_canonical_rows(
    path: Path,
    cell_index: Mapping[str, int],
    targets: list[str],
    donor_species: set[str] | None,
    active_count: int,
    donor_count: int,
) -> tuple[dict[str, np.ndarray], np.ndarray, int, list[str], list[str]]:
    parquet = pq.ParquetFile(path)
    _require(list(parquet.schema_arrow.names) == CANONICAL_SCHEMA, "canonical_schema_drift")
    present = {target: np.zeros(len(cell_index), dtype=bool) for target in targets}
    richness = np.zeros(len(cell_index), dtype=np.int32)
    previous: tuple[str, str] | None = None
    species_seen: list[str] = []
    donor_seen: list[str] = []
    row_count = 0
    for batch in parquet.iter_batches(columns=CANONICAL_SCHEMA, batch_size=131_072):
        species_values = batch.column(0).to_pylist()
        cell_values = batch.column(1).to_pylist()
        for species_value, cell_value in zip(species_values, cell_values, strict=True):
            species = str(species_value)
            cell = str(cell_value)
            current = (species, cell)
            _require(previous is None or current > previous, "canonical_duplicate_or_order_drift")
            previous = current
            if not species_seen or species_seen[-1] != species:
                species_seen.append(species)
            # Goal049 canonical memberships cover the complete Goal048
            # domain.  Retained and buffer cells outside the outer predictor
            # domain are valid rows and are retained in the file-level
            # conservation counts, but cannot contribute to outer arrays.
            is_donor = donor_species is None or species in donor_species
            if is_donor and (not donor_seen or donor_seen[-1] != species):
                donor_seen.append(species)
            if cell in cell_index:
                index = cell_index[cell]
                if is_donor:
                    richness[index] += 1
                if species in present:
                    present[species][index] = True
            row_count += 1
    _require(len(species_seen) == active_count, "active_species_count_drift")
    _require(len(donor_seen) == donor_count, "effort_donor_species_count_drift")
    if donor_species is not None:
        _require(set(donor_seen) == donor_species, "effort_donor_species_identity_drift")
    return present, richness, row_count, species_seen, donor_seen


def _write_access_success(
    run: Path,
    access_path: Path,
    closure: Mapping[str, Any],
    canonical_hash: str,
    target_digest: str,
    domain_digest: str,
    target_rows: Mapping[str, Mapping[str, Any]],
    row_count: int,
    species_count: int,
) -> None:
    success = {
        "schema_version": "goal052-outer-response-access-success-v1",
        "status": "response_access_complete",
        "immutable": True,
        "closure_file_sha256": sha256_file(run / "closure.json"),
        "closure_digest": closure.get("closure_digest"),
        "plan_digest": closure.get("plan_digest"),
        "access_started_sha256": sha256_file(access_path),
        "canonical_species_cells_sha256": canonical_hash,
        "target_inventory_sha256": target_digest,
        "domain_cell_ids_sha256": domain_digest,
        "domain_rows": int(closure.get("domain", {}).get("rows", -1)),
        "canonical_membership_rows": int(row_count),
        "canonical_species_count": int(species_count),
        "target_count": len(target_rows),
        "targets": {
            target: {
                "presence_cells": int(values["presence_cells"]),
                "y_sha256": values["y_sha256"],
                "richness_minus_f_sha256": values["richness_minus_f_sha256"],
            }
            for target, values in sorted(target_rows.items())
        },
    }
    write_once(run / "response-access-success.json", success)


def load_closed_outer_responses(root: Path, run: Path) -> dict[str, Any]:
    """Load gated full-domain canonical responses for all 157 outer targets."""
    # This must remain the first operation: it is the response firewall.
    closure = verify_closure(root, run)
    root = Path(root)
    run = Path(run)
    config, completion, completion_path, panel_path, canonical_path, expected_hash, target_digest, targets, donor_species = _metadata_before_response_read(root, closure)
    del config
    cell_ids, domain_digest = _read_domain(run, closure)
    access_path = _write_access_started(run, closure, expected_hash, target_digest, len(cell_ids))
    _require(canonical_path.is_file(), "canonical_species_cells_missing")
    _require(sha256_file(canonical_path) == expected_hash, "canonical_species_cells_hash_drift")
    counts = completion.get("counts", {})
    present, richness, row_count, species_seen, donor_seen = _read_canonical_rows(
        canonical_path, {cell: index for index, cell in enumerate(cell_ids)}, targets,
        donor_species, int(counts.get("active_species", -1)), int(counts.get("effort_donors", -1)),
    )
    expected_rows = counts.get("canonical_memberships")
    if expected_rows is not None:
        _require(int(expected_rows) == row_count, "canonical_membership_count_drift")
    by_target: dict[str, dict[str, np.ndarray]] = {}
    target_receipts: dict[str, dict[str, Any]] = {}
    for target in targets:
        is_donor = donor_species is None or target in donor_species
        focal = richness - present[target].astype(np.int32) if is_donor else richness.copy()
        _require(np.all(focal >= 0), "focal_excluded_richness_negative")
        _require(np.array_equal(focal[~present[target]], richness[~present[target]]), "focal_background_richness_changed")
        y = present[target].astype(np.int8, copy=True)
        richness_minus_f = focal.astype(np.int32, copy=False)
        by_target[target] = {"y": y, "richness_minus_f": richness_minus_f}
        target_receipts[target] = {
            "presence_cells": int(y.sum()),
            "y_sha256": _array_digest(y, "<i1"),
            "richness_minus_f_sha256": _array_digest(richness_minus_f, "<i4"),
        }
    _write_access_success(run, access_path, closure, expected_hash, target_digest, domain_digest, target_receipts, row_count, len(species_seen))
    provenance = {
        "schema_version": "goal052-outer-response-provenance-v1",
        "closure_file_sha256": sha256_file(run / "closure.json"),
        "closure_digest": closure.get("closure_digest"),
        "plan_digest": closure.get("plan_digest"),
        "canonical_species_cells_sha256": expected_hash,
        "completion_receipt_sha256": sha256_file(completion_path),
        "panel_summary_sha256": sha256_file(panel_path),
        "domain_cell_ids_sha256": domain_digest,
        "domain_rows": len(cell_ids),
        "canonical_membership_rows": row_count,
        "canonical_species_count": len(species_seen),
        "effort_donor_count": len(donor_seen),
        "target_count": len(by_target),
        "target_inventory_sha256": target_digest,
    }
    return {"closure": closure, "by_target": by_target, "response_provenance": provenance}


__all__ = ["Goal052OuterResponseError", "load_closed_outer_responses"]
