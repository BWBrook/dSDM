"""Goal 042 mainland-to-Tasmania response substrate.

The mainland output is a full-data reference, not a fold-safe response table.
Later partitions must call the same materialiser with records authorised for
that split. Tasmania contains evidence-based evaluation responses only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

import pyarrow as pa
import pyarrow.parquet as pq

from .goal040_normalisation import (
    MANIFEST_PATH as NORMALISATION_MANIFEST_PATH,
    _sha,
)
from .goal040_support import (
    CAMERA_EXPECTED_SHA256,
    CAMERA_OUTPUTS_PATH,
    CAMERA_PATH,
    DISTANCE_M,
    SLUGS,
    SUPPORT_MANIFEST_PATH,
    _camera_rows,
    _load_cells,
    _load_species_cells,
    _nearest_geodesic_m,
)


CONFIG_PATH = Path("config/goal042_transfer_response.json")
MANIFEST_PATH = Path("metadata/goal042_response_manifest.json")
DECISION_PATH = Path("metadata/goal042_decision_receipt.json")
PREDICTOR_MANIFEST_PATH = Path("metadata/goal041_table_manifest.json")
PREDICTOR_PATH = Path("data/raw/goal041/predictor_substrate.parquet")
OUTPUT_ROOT = Path("data/raw/goal042")
MAINLAND_FILE = "mainland_response_reference.parquet"
TASMANIA_FILE = "tasmania_evaluation_response.parquet"
MAINLAND_REGION = "southeast_mainland"
TASMANIA_REGION = "tasmania"
THRESHOLDS = (2, 3, 5)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

MAINLAND_SCHEMA = pa.schema([
    pa.field("target", pa.string(), nullable=False),
    pa.field("cell_id", pa.string(), nullable=False),
    pa.field("is_presence", pa.bool_(), nullable=False),
    pa.field("other_species_count", pa.int8(), nullable=False),
    pa.field("nearest_target_presence_m", pa.float64(), nullable=False),
    pa.field("eligible_x2", pa.bool_(), nullable=False),
    pa.field("eligible_x3", pa.bool_(), nullable=False),
    pa.field("eligible_x5", pa.bool_(), nullable=False),
])
TASMANIA_SCHEMA = pa.schema([
    pa.field("target", pa.string(), nullable=False),
    pa.field("cell_id", pa.string(), nullable=False),
    pa.field("response", pa.int8(), nullable=False),
    pa.field("ala_presence", pa.bool_(), nullable=False),
    pa.field("camera_presence", pa.bool_(), nullable=False),
    pa.field("camera_survey_supported_absence", pa.bool_(), nullable=False),
])

PRIVACY = {
    "tracked_row_payload": False,
    "tracked_cell_ids": False,
    "tracked_coordinates": False,
    "tracked_camera_identifiers": False,
    "tracked_donor_to_cell_associations": False,
    "tracked_private_paths": False,
}


class Goal042Error(ValueError):
    """Fail-closed Goal 042 contract error."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal042Error(reason)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal042Error(reason) from exc
    _require(isinstance(value, dict), reason)
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _schema_contract(schema: pa.Schema) -> list[dict[str, Any]]:
    return [
        {"name": field.name, "type": str(field.type), "nullable": field.nullable}
        for field in schema
    ]


def _schema_sha(schema: pa.Schema) -> str:
    return hashlib.sha256(_canonical(_schema_contract(schema))).hexdigest()


def _row_values(row: Mapping[str, Any], schema: pa.Schema) -> list[Any]:
    values: list[Any] = []
    for field in schema:
        value = row[field.name]
        if field.name == "nearest_target_presence_m":
            value = f"{float(value):.6f}"
        values.append(value)
    return values


def _content_digest(rows: Iterable[Mapping[str, Any]], schema: pa.Schema) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_canonical(_row_values(row, schema)))
    return digest.hexdigest()


def _validate_config(config: dict[str, Any]) -> None:
    cohort = config.get("cohort", {})
    mainland = config.get("mainland_response", {})
    tasmania = config.get("tasmania_evaluation", {})
    firewall = config.get("transfer_firewall", {})
    predictor = config.get("predictor_binding", {})
    privacy = config.get("privacy", {})
    _require(
        config.get("schema_version") == "goal042-contract-v1"
        and config.get("goal_id") == "goal042-mainland-tasmania-response-substrate"
        and cohort.get("support_tier") == "support_observed"
        and cohort.get("response_head_tier") == "mainland_pretraining_candidate"
        and cohort.get("expected_support_taxa") == 21
        and cohort.get("expected_response_heads") == 20
        and sorted(cohort.get("shared_targets", [])) == sorted(SLUGS)
        and mainland.get("region") == MAINLAND_REGION
        and mainland.get("support_fact") == "distinct_other_support_taxa_in_cell"
        and mainland.get("target_excluded_from_support") is True
        and mainland.get("primary_support_threshold") == 3
        and mainland.get("sensitivity_support_thresholds") == [2, 5]
        and mainland.get("minimum_nearest_target_presence_distance_m") == 5000
        and mainland.get("distance_comparison") == "greater_than_or_equal"
        and mainland.get("full_data_output_role") == "reference_only_not_split_authorised"
        and mainland.get("split_rule") == "recompute_support_and_distance_from_records_authorised_for_that_split"
        and tasmania.get("region") == TASMANIA_REGION
        and tasmania.get("presence_sources") == ["goal040_ala", "goal019_camera"]
        and tasmania.get("absence_source") == "goal019_camera_survey_supported_absence"
        and tasmania.get("presence_precedence") is True
        and tasmania.get("target_group_backgrounds_permitted") is False
        and firewall.get("mainland_only_for_pretraining_and_fine_tuning") is True
        and firewall.get("tasmania_only_for_evaluation") is True
        and firewall.get("target_excluded_from_cross_species_pretraining") is True
        and firewall.get("expected_cross_species_heads_per_target") == 19
        and predictor == {
            "authority": "goal041_portable_predictor_substrate",
            "join_key": "cell_id",
            "copy_predictor_values_into_response_outputs": False,
        }
        and privacy == {
            "cell_level_outputs_tracked": False,
            "coordinates_tracked": False,
            "camera_identifiers_tracked": False,
            "aggregate_species_counts_tracked": True,
        },
        "goal042_contract_drift",
    )


def _cohorts(normalisation: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    tiers = normalisation.get("taxon_tiers", {})
    _require(isinstance(tiers, dict), "goal042_taxon_tiers_missing")
    support = sorted(name for name, item in tiers.items() if item.get("support_observed") is True)
    heads = sorted(name for name, item in tiers.items() if item.get("mainland_pretraining_candidate") is True)
    targets = sorted(name for name, item in tiers.items() if item.get("shared_evaluation_candidate") is True)
    _require(len(support) == 21 and len(heads) == 20 and targets == sorted(SLUGS), "goal042_cohort_drift")
    _require(set(heads) <= set(support), "goal042_head_not_support_taxon")
    return support, heads, targets


def materialise_mainland_rows(
    target: str,
    coordinates: Mapping[str, tuple[Decimal, Decimal]],
    donor_members: Mapping[str, set[str]],
    target_presences: set[str],
) -> list[dict[str, Any]]:
    """Materialise one target from records already authorised by the caller."""
    _require(bool(target_presences), "goal042_target_presence_missing")
    _require(target_presences <= set(coordinates), "goal042_target_presence_outside_authorised_cells")
    _require(set(donor_members) <= set(coordinates), "goal042_donor_cell_outside_authorised_cells")
    for cell in target_presences:
        _require(target in donor_members.get(cell, set()), "goal042_target_presence_membership_drift")

    candidate_cells: list[str] = []
    counts: dict[str, int] = {}
    for cell, members in donor_members.items():
        count = len(members) - int(target in members)
        _require(0 <= count <= 20, "goal042_other_species_count_out_of_range")
        if cell not in target_presences and count >= 2:
            candidate_cells.append(cell)
            counts[cell] = count
    candidate_cells.sort()
    presence_coordinates = [coordinates[cell] for cell in sorted(target_presences)]
    distances = _nearest_geodesic_m(
        [coordinates[cell] for cell in candidate_cells], presence_coordinates
    )
    by_cell: dict[str, dict[str, Any]] = {}
    for cell in target_presences:
        by_cell[cell] = {
            "target": target,
            "cell_id": cell,
            "is_presence": True,
            "other_species_count": len(donor_members.get(cell, set())) - 1,
            "nearest_target_presence_m": 0.0,
            "eligible_x2": False,
            "eligible_x3": False,
            "eligible_x5": False,
        }
    for cell, distance in zip(candidate_cells, distances, strict=True):
        count = counts[cell]
        far = distance >= DISTANCE_M
        by_cell[cell] = {
            "target": target,
            "cell_id": cell,
            "is_presence": False,
            "other_species_count": count,
            "nearest_target_presence_m": round(float(distance), 6),
            "eligible_x2": far and count >= 2,
            "eligible_x3": far and count >= 3,
            "eligible_x5": far and count >= 5,
        }
    rows = [by_cell[cell] for cell in sorted(by_cell)]
    _require(
        all(not row["eligible_x5"] or row["eligible_x3"] for row in rows)
        and all(not row["eligible_x3"] or row["eligible_x2"] for row in rows)
        and all(not row["is_presence"] or not any(row[f"eligible_x{x}"] for x in THRESHOLDS) for row in rows),
        "goal042_response_nesting_drift",
    )
    return rows


def materialise_tasmania_rows(
    target: str,
    ala_presence: set[str],
    camera_presence: set[str],
    camera_absence: set[str],
) -> list[dict[str, Any]]:
    """Apply presence precedence to Tasmania's evidence-based evaluation rows."""
    presences = ala_presence | camera_presence
    cells = sorted(presences | camera_absence)
    rows = []
    for cell in cells:
        is_presence = cell in presences
        rows.append({
            "target": target,
            "cell_id": cell,
            "response": int(is_presence),
            "ala_presence": cell in ala_presence,
            "camera_presence": cell in camera_presence,
            "camera_survey_supported_absence": cell in camera_absence,
        })
    _require(all(row["response"] in {0, 1} for row in rows), "goal042_tasmania_response_drift")
    return rows


def _summarise_mainland(rows: list[dict[str, Any]]) -> dict[str, Any]:
    presences = sum(row["is_presence"] for row in rows)
    backgrounds = {str(x): sum(row[f"eligible_x{x}"] for row in rows) for x in THRESHOLDS}
    supported = {
        str(x): sum((not row["is_presence"]) and row["other_species_count"] >= x for row in rows)
        for x in THRESHOLDS
    }
    rejected = {str(x): supported[str(x)] - backgrounds[str(x)] for x in THRESHOLDS}
    primary_total = presences + backgrounds["3"]
    _require(backgrounds["5"] <= backgrounds["3"] <= backgrounds["2"], "goal042_summary_nesting_drift")
    return {
        "reference_rows": len(rows),
        "presence_cells": presences,
        "support_cells_before_distance": supported,
        "distance_rejected_under_5000m": rejected,
        "reference_background_cells": backgrounds,
        "primary_x3_response_cells": primary_total,
        "primary_x3_presence_fraction": presences / primary_total,
    }


def _summarise_tasmania(rows: list[dict[str, Any]]) -> dict[str, Any]:
    presences = sum(row["response"] == 1 for row in rows)
    absences = len(rows) - presences
    return {
        "response_cells": len(rows),
        "presence_cells": presences,
        "survey_supported_absence_cells": absences,
        "ala_presence_cells": sum(row["ala_presence"] for row in rows),
        "camera_presence_cells": sum(row["camera_presence"] for row in rows),
        "ala_camera_presence_overlap_cells": sum(row["ala_presence"] and row["camera_presence"] for row in rows),
        "presence_over_camera_absence_conflict_cells": sum(
            row["response"] == 1 and row["camera_survey_supported_absence"] for row in rows
        ),
        "presence_fraction": presences / len(rows),
    }


def _write_parquet(path: Path, schema: pa.Schema, groups: Iterable[list[dict[str, Any]]]) -> dict[str, Any]:
    temp = path.with_suffix(path.suffix + ".part")
    _require(not temp.exists(), "goal042_orphaned_partial_output")
    digest = hashlib.sha256()
    rows = 0
    writer = pq.ParquetWriter(temp, schema, compression="zstd", use_dictionary=True)
    try:
        for group in groups:
            if not group:
                continue
            writer.write_table(pa.Table.from_pylist(group, schema=schema))
            rows += len(group)
            for row in group:
                digest.update(_canonical(_row_values(row, schema)))
    finally:
        writer.close()
    temp.replace(path)
    return {
        "bytes": path.stat().st_size,
        "rows": rows,
        "sha256": _sha(path),
        "content_sha256": digest.hexdigest(),
        "schema_sha256": _schema_sha(schema),
    }


def _parquet_receipt(path: Path, schema: pa.Schema) -> dict[str, Any]:
    try:
        parquet = pq.ParquetFile(path)
    except (OSError, pa.ArrowInvalid) as exc:
        raise Goal042Error("goal042_private_output_invalid") from exc
    _require(parquet.schema_arrow == schema, "goal042_private_output_schema_drift")
    digest = hashlib.sha256()
    rows = 0
    for batch in parquet.iter_batches(batch_size=100_000):
        for row in batch.to_pylist():
            digest.update(_canonical(_row_values(row, schema)))
            rows += 1
    return {
        "bytes": path.stat().st_size,
        "rows": rows,
        "sha256": _sha(path),
        "content_sha256": digest.hexdigest(),
        "schema_sha256": _schema_sha(schema),
    }


def _authorities(root: Path, *, require_raw: bool) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    config = _read_json(root / CONFIG_PATH, "goal042_config_invalid")
    _validate_config(config)
    normal = _read_json(root / NORMALISATION_MANIFEST_PATH, "goal042_normalisation_manifest_invalid")
    support_manifest = _read_json(root / SUPPORT_MANIFEST_PATH, "goal042_support_manifest_invalid")
    predictor_manifest = _read_json(root / PREDICTOR_MANIFEST_PATH, "goal042_predictor_manifest_invalid")
    camera_outputs = _read_json(root / CAMERA_OUTPUTS_PATH, "goal042_camera_receipt_invalid")
    support, heads, targets = _cohorts(normal)
    species_receipt = normal.get("outputs", {}).get("species_cells", {})
    camera_role = camera_outputs.get("private_output_roles", {}).get("grid_evidence", {})
    _require(
        normal.get("status") == "complete_raw_replay_required"
        and support_manifest.get("status") == "complete_raw_replay_required"
        and predictor_manifest.get("schema_version") == "goal041-table-manifest-v3"
        and predictor_manifest.get("rows") == 1_125_325
        and predictor_manifest.get("regions") == {MAINLAND_REGION: 1_053_032, TASMANIA_REGION: 72_293}
        and isinstance(predictor_manifest.get("final_sha256"), str)
        and SHA256_RE.fullmatch(predictor_manifest["final_sha256"]) is not None
        and camera_role.get("sha256") == CAMERA_EXPECTED_SHA256,
        "goal042_upstream_authority_drift",
    )
    bindings = {
        "config_sha256": _sha(root / CONFIG_PATH),
        "goal040_normalisation_manifest_sha256": _sha(root / NORMALISATION_MANIFEST_PATH),
        "goal040_support_manifest_sha256": _sha(root / SUPPORT_MANIFEST_PATH),
        "goal040_species_cells_sha256": species_receipt.get("sha256"),
        "goal019_camera_outputs_sha256": _sha(root / CAMERA_OUTPUTS_PATH),
        "goal019_camera_grid_sha256": camera_role.get("sha256"),
        "goal041_table_manifest_sha256": _sha(root / PREDICTOR_MANIFEST_PATH),
        "goal041_predictor_table_sha256": predictor_manifest.get("final_sha256"),
    }
    _require(all(isinstance(value, str) and SHA256_RE.fullmatch(value) for value in bindings.values()), "goal042_binding_digest_drift")
    if require_raw:
        _require(
            (root / PREDICTOR_PATH).is_file()
            and _sha(root / PREDICTOR_PATH) == predictor_manifest["final_sha256"]
            and (root / CAMERA_PATH).is_file()
            and _sha(root / CAMERA_PATH) == CAMERA_EXPECTED_SHA256,
            "goal042_raw_authority_drift",
        )
    return {"config": config, "bindings": bindings}, support, heads, targets


def _predictor_identity(root: Path) -> dict[str, str]:
    table = pq.read_table(root / PREDICTOR_PATH, columns=["cell_id", "region"])
    cell_ids = table.column("cell_id").to_pylist()
    regions = table.column("region").to_pylist()
    _require(len(cell_ids) == len(set(cell_ids)) == 1_125_325, "goal042_predictor_identity_drift")
    return dict(zip(cell_ids, regions, strict=True))


def _analyse(root: Path, *, write_output: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    _, support_taxa, heads, targets = _authorities(root, require_raw=True)
    cells = _load_cells(root)
    species_cells = _load_species_cells(root, cells)
    camera_presence, camera_absence, camera_alignment = _camera_rows(root, cells)
    predictor_identity = _predictor_identity(root)
    _require(
        len(predictor_identity) == len(cells)
        and all(predictor_identity.get(cell) == region for cell, (_, _, region) in cells.items()),
        "goal042_predictor_cell_binding_drift",
    )

    mainland_coordinates = {
        cell: (lon, lat) for cell, (lon, lat, region) in cells.items() if region == MAINLAND_REGION
    }
    donor_members: dict[str, set[str]] = defaultdict(set)
    for species in support_taxa:
        for cell in species_cells[species]:
            if cell in mainland_coordinates:
                donor_members[cell].add(species)

    mainland_groups: list[list[dict[str, Any]]] = []
    mainland_summary: dict[str, Any] = {}
    for target in heads:
        rows = materialise_mainland_rows(
            target,
            mainland_coordinates,
            donor_members,
            species_cells[target] & set(mainland_coordinates),
        )
        mainland_groups.append(rows)
        mainland_summary[target] = _summarise_mainland(rows)

    tasmania_groups: list[list[dict[str, Any]]] = []
    tasmania_summary: dict[str, Any] = {}
    for target in targets:
        slug = SLUGS[target]
        ala = {cell for cell in species_cells[target] if cells[cell][2] == TASMANIA_REGION}
        rows = materialise_tasmania_rows(
            target,
            ala,
            camera_presence.get(slug, set()),
            camera_absence.get(slug, set()),
        )
        _require(all(predictor_identity.get(row["cell_id"]) == TASMANIA_REGION for row in rows), "goal042_tasmania_predictor_binding_drift")
        tasmania_groups.append(rows)
        tasmania_summary[target] = _summarise_tasmania(rows)

    outputs: dict[str, Any]
    if write_output:
        output = root / OUTPUT_ROOT
        output.mkdir(parents=True, exist_ok=True)
        _require({path.name for path in output.iterdir()} <= {MAINLAND_FILE, TASMANIA_FILE}, "goal042_output_footprint_drift")
        outputs = {
            "mainland_response_reference": _write_parquet(output / MAINLAND_FILE, MAINLAND_SCHEMA, mainland_groups),
            "tasmania_evaluation_response": _write_parquet(output / TASMANIA_FILE, TASMANIA_SCHEMA, tasmania_groups),
        }
    else:
        outputs = {
            "mainland_response_reference": {
                "rows": sum(map(len, mainland_groups)),
                "content_sha256": _content_digest((row for group in mainland_groups for row in group), MAINLAND_SCHEMA),
            },
            "tasmania_evaluation_response": {
                "rows": sum(map(len, tasmania_groups)),
                "content_sha256": _content_digest((row for group in tasmania_groups for row in group), TASMANIA_SCHEMA),
            },
        }

    report = {
        "cohort": {
            "support_taxa": support_taxa,
            "response_heads": heads,
            "support_only_taxa": sorted(set(support_taxa) - set(heads)),
            "shared_targets": targets,
            "cross_species_pretraining_heads_by_target": {
                target: [head for head in heads if head != target] for target in targets
            },
        },
        "mainland_reference": mainland_summary,
        "tasmania_evaluation": tasmania_summary,
        "camera_alignment": camera_alignment,
        "firewall": {
            "mainland_reference_region": MAINLAND_REGION,
            "tasmania_evaluation_region": TASMANIA_REGION,
            "tasmania_rows_in_mainland_output": 0,
            "mainland_rows_in_tasmania_output": 0,
            "target_group_background_rows_in_tasmania_output": 0,
            "cross_species_heads_per_target": 19,
            "predictor_cell_binding_complete": True,
            "mainland_output_is_split_authorised": False,
        },
    }
    return report, outputs


def _manifest(root: Path, report: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    authorities, _, _, _ = _authorities(root, require_raw=True)
    return {
        "schema_version": "goal042-response-manifest-v1",
        "goal_id": "goal042-mainland-tasmania-response-substrate",
        "status": "complete_raw_replay_required",
        "completed_at": _now(),
        "bindings": authorities["bindings"],
        "rules": {
            "mainland_primary_threshold": 3,
            "mainland_sensitivity_thresholds": [2, 5],
            "mainland_minimum_distance_m": 5000,
            "mainland_reference_role": "full_data_reference_not_split_authorised",
            "split_rule": "recompute_support_and_distance_from_split_authorised_records",
            "tasmania_response_sources": "ALA_or_camera_presence_with_presence_precedence; otherwise_camera_survey_supported_absence",
            "tasmania_target_group_backgrounds": False,
            "cross_species_target_exclusion": True,
        },
        "summary": report,
        "outputs": {"private_outputs_ignored": True, "private_output_roles": outputs},
        "privacy": PRIVACY,
    }


def _validate_manifest(manifest: dict[str, Any], bindings: dict[str, str]) -> None:
    _require(
        set(manifest) == {"schema_version", "goal_id", "status", "completed_at", "bindings", "rules", "summary", "outputs", "privacy"}
        and manifest.get("schema_version") == "goal042-response-manifest-v1"
        and manifest.get("goal_id") == "goal042-mainland-tasmania-response-substrate"
        and manifest.get("status") == "complete_raw_replay_required"
        and isinstance(manifest.get("completed_at"), str)
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["completed_at"])
        and manifest.get("bindings") == bindings
        and manifest.get("privacy") == PRIVACY,
        "goal042_manifest_identity_drift",
    )
    rules = manifest.get("rules", {})
    _require(
        rules == {
            "mainland_primary_threshold": 3,
            "mainland_sensitivity_thresholds": [2, 5],
            "mainland_minimum_distance_m": 5000,
            "mainland_reference_role": "full_data_reference_not_split_authorised",
            "split_rule": "recompute_support_and_distance_from_split_authorised_records",
            "tasmania_response_sources": "ALA_or_camera_presence_with_presence_precedence; otherwise_camera_survey_supported_absence",
            "tasmania_target_group_backgrounds": False,
            "cross_species_target_exclusion": True,
        },
        "goal042_manifest_rule_drift",
    )
    summary = manifest.get("summary", {})
    cohort = summary.get("cohort", {})
    firewall = summary.get("firewall", {})
    response_heads = cohort.get("response_heads", [])
    shared_targets = cohort.get("shared_targets", [])
    expected_pretraining = {
        target: [head for head in response_heads if head != target]
        for target in shared_targets
    }
    _require(
        len(cohort.get("support_taxa", [])) == 21
        and len(response_heads) == 20
        and cohort.get("support_only_taxa") == ["Burramys parvus"]
        and sorted(shared_targets) == sorted(SLUGS)
        and cohort.get("cross_species_pretraining_heads_by_target") == expected_pretraining
        and firewall == {
            "mainland_reference_region": MAINLAND_REGION,
            "tasmania_evaluation_region": TASMANIA_REGION,
            "tasmania_rows_in_mainland_output": 0,
            "mainland_rows_in_tasmania_output": 0,
            "target_group_background_rows_in_tasmania_output": 0,
            "cross_species_heads_per_target": 19,
            "predictor_cell_binding_complete": True,
            "mainland_output_is_split_authorised": False,
        },
        "goal042_manifest_firewall_drift",
    )
    mainland = summary.get("mainland_reference", {})
    tasmania = summary.get("tasmania_evaluation", {})
    _require(set(mainland) == set(cohort["response_heads"]) and set(tasmania) == set(cohort["shared_targets"]), "goal042_manifest_species_coverage_drift")
    for item in mainland.values():
        bg = item.get("reference_background_cells", {})
        total = item.get("primary_x3_response_cells")
        fraction = item.get("primary_x3_presence_fraction")
        _require(
            set(bg) == {"2", "3", "5"}
            and bg["5"] <= bg["3"] <= bg["2"]
            and total == item.get("presence_cells") + bg["3"]
            and isinstance(fraction, float) and math.isclose(fraction, item["presence_cells"] / total),
            "goal042_manifest_mainland_summary_drift",
        )
    for item in tasmania.values():
        _require(
            item.get("response_cells") == item.get("presence_cells") + item.get("survey_supported_absence_cells")
            and isinstance(item.get("presence_fraction"), float)
            and math.isclose(item["presence_fraction"], item["presence_cells"] / item["response_cells"]),
            "goal042_manifest_tasmania_summary_drift",
        )
    output = manifest.get("outputs", {})
    roles = output.get("private_output_roles", {})
    _require(output.get("private_outputs_ignored") is True and set(roles) == {"mainland_response_reference", "tasmania_evaluation_response"}, "goal042_manifest_output_drift")
    for role, schema in (("mainland_response_reference", MAINLAND_SCHEMA), ("tasmania_evaluation_response", TASMANIA_SCHEMA)):
        receipt = roles[role]
        _require(
            set(receipt) == {"bytes", "rows", "sha256", "content_sha256", "schema_sha256"}
            and isinstance(receipt["bytes"], int) and receipt["bytes"] > 0
            and isinstance(receipt["rows"], int) and receipt["rows"] > 0
            and all(isinstance(receipt[key], str) and SHA256_RE.fullmatch(receipt[key]) for key in ("sha256", "content_sha256", "schema_sha256"))
            and receipt["schema_sha256"] == _schema_sha(schema),
            "goal042_manifest_receipt_drift",
        )
    text = json.dumps(manifest, sort_keys=True).lower()
    _require(
        not any(token in text for token in ("longitude", "latitude", '"cell_id"', "grid_cell_id", "site_id", "record_id", "data/raw/")),
        "goal042_manifest_private_material",
    )


def _decision(manifest_sha: str, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "goal042-decision-v1",
        "status": "ready",
        "response_manifest_sha256": manifest_sha,
        "bindings": manifest["bindings"],
        "gates": {
            "cohort": "validated",
            "mainland_reference": "validated_not_split_authorised",
            "tasmania_evaluation": "validated",
            "transfer_firewall": "validated",
            "predictor_identity": "validated",
            "privacy": "validated",
        },
        "limitations": [
            "Mainland reference backgrounds must be recomputed from split-authorised records before model fitting",
            "Target-group backgrounds are effort-supported candidates, not true absences or occupancy non-detections",
            "Tasmania camera absences are survey-supported at sampled cells and do not imply island-wide detection certainty",
            "The frozen 21-taxon cohort is a feasibility subset, not a representative census of southeastern mammals"
        ],
        "next_boundary": "spatial_partitions_and_split_fitted_predictor_transformations_without_opening_tasmania",
    }


def build(root: Path) -> dict[str, Any]:
    root = Path(root)
    report, outputs = _analyse(root, write_output=True)
    manifest = _manifest(root, report, outputs)
    (root / MANIFEST_PATH).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decision = _decision(_sha(root / MANIFEST_PATH), manifest)
    (root / DECISION_PATH).write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validate(root, require_raw=True)


def validate(root: Path, *, require_raw: bool = False) -> dict[str, Any]:
    root = Path(root)
    authorities, _, _, _ = _authorities(root, require_raw=require_raw)
    manifest = _read_json(root / MANIFEST_PATH, "goal042_manifest_invalid")
    _validate_manifest(manifest, authorities["bindings"])
    decision = _read_json(root / DECISION_PATH, "goal042_decision_invalid")
    _require(decision == _decision(_sha(root / MANIFEST_PATH), manifest), "goal042_decision_drift")
    if not require_raw:
        return {"status": "tracked_goal042_valid_raw_replay_required", "raw_replay_required": True}
    output = root / OUTPUT_ROOT
    _require(output.is_dir() and {path.name for path in output.iterdir()} == {MAINLAND_FILE, TASMANIA_FILE}, "goal042_output_footprint_drift")
    observed = {
        "mainland_response_reference": _parquet_receipt(output / MAINLAND_FILE, MAINLAND_SCHEMA),
        "tasmania_evaluation_response": _parquet_receipt(output / TASMANIA_FILE, TASMANIA_SCHEMA),
    }
    _require(observed == manifest["outputs"]["private_output_roles"], "goal042_private_output_receipt_drift")
    replay_report, replay_outputs = _analyse(root, write_output=False)
    _require(replay_report == manifest["summary"], "goal042_raw_replay_summary_drift")
    for role in observed:
        _require(
            replay_outputs[role]["rows"] == observed[role]["rows"]
            and replay_outputs[role]["content_sha256"] == observed[role]["content_sha256"],
            "goal042_raw_replay_content_drift",
        )
    return {
        "status": "goal042_ready_raw_replay_validated",
        "mainland_rows": observed["mainland_response_reference"]["rows"],
        "tasmania_rows": observed["tasmania_evaluation_response"]["rows"],
        "shared_targets": manifest["summary"]["cohort"]["shared_targets"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate", "validate-tracked"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build(args.root)
    else:
        result = validate(args.root, require_raw=args.command == "validate")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "Goal042Error",
    "MAINLAND_SCHEMA",
    "TASMANIA_SCHEMA",
    "materialise_mainland_rows",
    "materialise_tasmania_rows",
    "build",
    "validate",
    "main",
]
