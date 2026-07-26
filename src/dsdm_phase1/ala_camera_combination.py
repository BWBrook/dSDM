"""Goal020 deterministic reconciliation of accepted ALA and camera evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

from shapely.geometry import Point

from . import ala_spatial_normalization as ala
from . import camera_spatial_normalization as camera
from .contracts import validate_phase1_decision_bundle


GOAL_ID = "goal020-ala-camera-combination-2026-07-26"
ACTIVE_SPECIES = tuple(camera.ACTIVE_SPECIES)
EXCLUDED_SPECIES = "macropus_giganteus"
ABSENCE_RULE_ID = "P1-D009"
CANONICAL_OUTPUT_DIRECTORY = (
    "data/processed/combined/goal020-ala-camera-combination/2026-07-26"
)
CANONICAL_EVIDENCE_DIRECTORY = (
    "evidence/ala_camera_combination/2026-07-26"
)
OUTPUT_FILE = "grid_evidence.csv"
EVIDENCE_PAYLOAD_FILES = (
    "source_inventory.json",
    "combination_summary.json",
    "spatial_summary.json",
    "outputs.json",
    "review.json",
)
EVIDENCE_FILES = (*EVIDENCE_PAYLOAD_FILES, "manifest.json")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GRID_ID_RE = re.compile(r"g_-?\d+_-?\d+\Z")
FORBIDDEN_EVIDENCE_KEYS = {
    "grid_cell_id",
    "longitude",
    "latitude",
    "coordinates",
    "site_id",
    "survey_id",
    "media_id",
    "image_id",
    "event_date",
    "deployment_timing",
    "current_activity",
    "source_code",
    "focal_mapping",
    "private_path",
    "row_value",
}

ALA_FIELDS = tuple(ala.PRESENCE_FIELDS)
CAMERA_FIELDS = tuple(camera.GRID_FIELDS)
OUTPUT_FIELDS = (
    "species_id",
    "grid_cell_id",
    "centroid_lon",
    "centroid_lat",
    "pa",
    "pa_type",
    "survey_supported_absence_rule_id",
    "source_combination",
    "cross_source_conflict",
    "ala_presence",
    "ala_source_row_count",
    "ala_unique_provider_record_count",
    "ala_resource_count",
    "ala_dataset_count",
    "ala_unknown_uncertainty_count",
    "ala_qa_flag_count",
    "ala_low_cell_certainty_only",
    "camera_evidence",
    "camera_pa",
    "camera_pa_type",
    "camera_survey_supported_absence_rule_id",
    "camera_site_count",
    "camera_presence_site_count",
    "camera_survey_supported_absence_site_count",
    "camera_positive_source_row_count",
    "camera_internal_conflict",
)

EXPECTED_BINDING_HASHES = {
    "decision_bundle": "ccccbb2e56e101b1a53421f8016699bfb500f4356861e10c1213a398aabe04a2",
    "goal018_plan": "516b0bbb089cfcbc6558677ea0f0b4ac2662acb2c79e33308485ae6ff605d75b",
    "goal018_evidence_manifest": "74766fc49bb809f7af7b9716ce96bbc081d9c0c165f6e304dfbf38bfee19717e",
    "goal018_outputs_evidence": "5b69b95fef535a63b36a1f6a10c15f5682d8ef073e42579754e2c97f21c3d3e5",
    "goal018_presence": "a41f3570cbc5afaaa15358fe25a011bdf57e3fdb4c9b488ac658e2b774b022d4",
    "goal019_plan": "378333d40cdb8afae07152de2435cff74ebb41be227ac498bdf68bf326a23174",
    "goal019_evidence_manifest": "5058b60028b0e5185a3994d58243d9aba16681bc21903f4f0447afcb43c010a7",
    "goal019_outputs_evidence": "491dfe10a50c6e208550919e59fbfd86600e23fb21504bbc4266ebb542464d38",
    "goal019_grid_evidence": "a16249991384d9b8545aee4027a7ac22a3ae7166bdd7e8a141ae815015021563",
    "offshore_islands": "98ca7bf213f0760894d9ad329681e2f2c9e491a8255577fae20fd31c73685d92",
}
PRIVATE_BINDINGS = {"goal018_presence", "goal019_grid_evidence"}

EXPECTED_OVERALL = {
    "active_ala_rows": 6595,
    "camera_rows": 6451,
    "overlap_rows": 178,
    "output_rows": 12868,
    "ala_only_presence": 6417,
    "camera_only_presence": 4113,
    "both_presence": 165,
    "ala_overrides_camera_absence": 13,
    "camera_absence_retained": 2160,
    "final_presence": 10708,
    "final_survey_supported_absence": 2160,
    "camera_internal_conflicts": 651,
    "ala_low_cell_certainty_only": 1221,
    "unique_physical_cells": 5407,
    "excluded_macropus_ala_rows": 34,
}
EXPECTED_BY_SPECIES = {
    "dasyurus_maculatus": {
        "ala_only": 460,
        "override": 1,
        "both": 13,
        "camera_only": 512,
        "absence_retained": 221,
        "final_presence": 986,
        "final_absence": 221,
        "total": 1207,
        "internal_conflict": 151,
    },
    "dasyurus_viverrinus": {
        "ala_only": 377,
        "override": 3,
        "both": 7,
        "camera_only": 88,
        "absence_retained": 649,
        "final_presence": 475,
        "final_absence": 649,
        "total": 1124,
        "internal_conflict": 35,
    },
    "notamacropus_rufogriseus": {
        "ala_only": 675,
        "override": 2,
        "both": 11,
        "camera_only": 692,
        "absence_retained": 147,
        "final_presence": 1380,
        "final_absence": 147,
        "total": 1527,
        "internal_conflict": 86,
    },
    "pseudocheirus_peregrinus": {
        "ala_only": 135,
        "override": 1,
        "both": 0,
        "camera_only": 252,
        "absence_retained": 599,
        "final_presence": 388,
        "final_absence": 599,
        "total": 987,
        "internal_conflict": 78,
    },
    "sarcophilus_harrisii": {
        "ala_only": 2961,
        "override": 4,
        "both": 99,
        "camera_only": 543,
        "absence_retained": 101,
        "final_presence": 3607,
        "final_absence": 101,
        "total": 3708,
        "internal_conflict": 83,
    },
    "thylogale_billardierii": {
        "ala_only": 749,
        "override": 0,
        "both": 15,
        "camera_only": 707,
        "absence_retained": 130,
        "final_presence": 1471,
        "final_absence": 130,
        "total": 1601,
        "internal_conflict": 40,
    },
    "trichosurus_vulpecula": {
        "ala_only": 558,
        "override": 1,
        "both": 9,
        "camera_only": 667,
        "absence_retained": 175,
        "final_presence": 1235,
        "final_absence": 175,
        "total": 1410,
        "internal_conflict": 95,
    },
    "vombatus_ursinus": {
        "ala_only": 502,
        "override": 1,
        "both": 11,
        "camera_only": 652,
        "absence_retained": 138,
        "final_presence": 1166,
        "final_absence": 138,
        "total": 1304,
        "internal_conflict": 83,
    },
}

PLAN_PRIVACY = {
    "tracked_actual_grid_ids_or_coordinates": False,
    "tracked_camera_identifiers_or_timing": False,
    "tracked_private_paths_or_rows": False,
}
REVIEW_PRIVACY = {
    "actual_grid_ids_or_coordinates_retained": False,
    "camera_identifiers_or_timing_retained": False,
    "private_paths_or_rows_retained": False,
}


class CombinationError(ValueError):
    """Raised when the frozen Goal020 combination contract is violated."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _schema_sha256(fields: Iterable[str]) -> str:
    payload = json.dumps(list(fields), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _safe_relative(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise CombinationError("binding_path_invalid")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise CombinationError("binding_path_unsafe")
    return path


def _load_json(path: Path, error: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CombinationError(error) from exc
    if not isinstance(value, dict):
        raise CombinationError(error)
    return value


def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(plan, Mapping)
        or plan.get("schema_version") != "1.0"
        or plan.get("goal_id") != GOAL_ID
    ):
        raise CombinationError("plan_identity_drift")
    bindings = plan.get("bindings")
    if not isinstance(bindings, Mapping) or set(bindings) != set(
        EXPECTED_BINDING_HASHES
    ):
        raise CombinationError("plan_binding_shape_drift")
    for role, expected_hash in EXPECTED_BINDING_HASHES.items():
        binding = bindings.get(role)
        if (
            not isinstance(binding, Mapping)
            or set(binding) != {"path", "sha256"}
            or binding.get("sha256") != expected_hash
        ):
            raise CombinationError("plan_binding_drift")
        _safe_relative(binding.get("path"))

    species = plan.get("species_contract")
    if species != {
        "active_species_ids": list(ACTIVE_SPECIES),
        "excluded_downstream": {
            "species_id": EXCLUDED_SPECIES,
            "expected_ala_rows": 34,
            "upstream_provenance_unchanged": True,
        },
    }:
        raise CombinationError("species_contract_drift")
    if plan.get("combination_contract") != {
        "key": ["species_id", "grid_cell_id"],
        "join": "full_outer_union",
        "accepted_presence_dominates": True,
        "camera_absence_without_presence_only": True,
        "absence_label": "survey_supported_absence",
        "absence_rule_id": ABSENCE_RULE_ID,
        "source_combinations": [
            "ala_only_presence",
            "camera_only_presence",
            "both_presence",
            "ala_overrides_camera_absence",
            "camera_absence_retained",
        ],
        "camera_internal_conflict_distinct_from_cross_source_conflict": True,
        "source_absent_provenance": "blank",
        "sort": ["species_id", "grid_cell_id"],
    }:
        raise CombinationError("combination_contract_drift")
    inputs = plan.get("input_contracts")
    if inputs != {
        "ala": {"rows": 6629, "schema": list(ALA_FIELDS)},
        "camera": {"rows": 6451, "schema": list(CAMERA_FIELDS)},
    }:
        raise CombinationError("input_contract_drift")
    if plan.get("expected_oracle") != {
        "overall": EXPECTED_OVERALL,
        "by_species": EXPECTED_BY_SPECIES,
        "centroid_mismatch_rows": 0,
        "matrix_conflicting_presences": 0,
    }:
        raise CombinationError("oracle_contract_drift")
    if plan.get("island_gate") != {
        "decision_id": "P1-D014",
        "apply_to": "absence_evidence_only",
        "excluded_combination_presence": "block_and_review",
        "provisional_exclusions_remain_suppressed": True,
    }:
        raise CombinationError("island_gate_contract_drift")
    if plan.get("outputs") != {
        "directory": CANONICAL_OUTPUT_DIRECTORY,
        "file": OUTPUT_FILE,
        "schema": list(OUTPUT_FIELDS),
        "private_ignored": True,
    }:
        raise CombinationError("output_contract_drift")
    if plan.get("evidence") != {
        "directory": CANONICAL_EVIDENCE_DIRECTORY,
        "files": list(EVIDENCE_FILES),
        "aggregate_only": True,
    }:
        raise CombinationError("evidence_contract_drift")
    if (
        plan.get("privacy") != PLAN_PRIVACY
        or plan.get("upstream_validation")
        != {
            "tracked_validators_required": True,
            "goal020_full_replay_required": True,
            "goal018_full_replay_at_acceptance": True,
            "goal019_full_replay_at_acceptance": True,
        }
        or plan.get("legacy_comparison")
        != {"runtime_input": False, "gate_target": False}
        or plan.get("stopped_before")
        != [
            "pseudoabsence",
            "predictors",
            "partitions",
            "mapping",
            "modelling",
        ]
        or plan.get("atomic_publish") is not True
    ):
        raise CombinationError("validation_or_stop_contract_drift")
    return {"goal_id": GOAL_ID, "species_count": len(ACTIVE_SPECIES)}


def _load_plan(plan_path: Path) -> dict[str, Any]:
    plan = _load_json(plan_path, "plan_json_invalid")
    validate_plan(plan)
    return plan


def _bound_paths(
    plan_path: Path, plan: Mapping[str, Any], *, include_private: bool
) -> dict[str, Path]:
    root = Path(plan_path).resolve().parents[1]
    paths: dict[str, Path] = {}
    for role, binding in plan["bindings"].items():
        if role in PRIVATE_BINDINGS and not include_private:
            continue
        path = root / _safe_relative(binding["path"])
        if (
            not path.is_file()
            or path.is_symlink()
            or sha256(path) != binding["sha256"]
        ):
            raise CombinationError(f"binding_drift:{role}")
        paths[role] = path
    if include_private:
        _validate_exact_files(
            paths["goal018_presence"].parent,
            ("row_audit.csv", "presence.csv"),
            error="goal018_output_footprint_drift",
        )
        _validate_exact_files(
            paths["goal019_grid_evidence"].parent,
            camera.OUTPUT_FILES,
            error="goal019_output_footprint_drift",
        )
    return paths


def _validate_exact_files(
    directory: Path, names: Iterable[str], *, error: str
) -> None:
    expected = set(names)
    if not directory.is_dir() or directory.is_symlink():
        raise CombinationError(error)
    entries = list(directory.iterdir())
    if (
        len(entries) != len(expected)
        or {entry.name for entry in entries} != expected
        or any(not entry.is_file() or entry.is_symlink() for entry in entries)
    ):
        raise CombinationError(error)


def _validate_upstream_tracked(
    plan_path: Path, plan: Mapping[str, Any], paths: Mapping[str, Path]
) -> dict[str, str]:
    try:
        decision = _load_json(paths["decision_bundle"], "decision_bundle_invalid")
        validate_phase1_decision_bundle(decision)
        ala_result = ala.validate_evidence(
            paths["goal018_plan"],
            paths["goal018_evidence_manifest"].parent,
        )
        camera_result = camera.validate_evidence(
            paths["goal019_plan"],
            paths["goal019_evidence_manifest"].parent,
        )
    except Exception as exc:
        raise CombinationError("upstream_tracked_validation_failure") from exc
    expected = {
        "goal018": "goal018_tracked_evidence_valid_raw_replay_required",
        "goal019": "goal019_tracked_evidence_valid_private_replay_required",
    }
    observed = {
        "goal018": ala_result.get("readiness"),
        "goal019": camera_result.get("readiness"),
    }
    if observed != expected:
        raise CombinationError("upstream_tracked_validation_failure")
    goal018_outputs = _load_json(
        paths["goal018_outputs_evidence"], "goal018_outputs_evidence_invalid"
    )
    if (
        goal018_outputs.get("presence_rows") != 6629
        or goal018_outputs.get("presence_sha256")
        != EXPECTED_BINDING_HASHES["goal018_presence"]
        or goal018_outputs.get("schemas", {}).get("presence") != list(ALA_FIELDS)
    ):
        raise CombinationError("goal018_output_binding_failure")
    goal019_outputs = _load_json(
        paths["goal019_outputs_evidence"], "goal019_outputs_evidence_invalid"
    )
    camera_role = goal019_outputs.get("private_output_roles", {}).get(
        "grid_evidence"
    )
    if (
        not isinstance(camera_role, Mapping)
        or camera_role.get("rows") != 6451
        or camera_role.get("sha256")
        != EXPECTED_BINDING_HASHES["goal019_grid_evidence"]
        or camera_role.get("schema_sha256") != _schema_sha256(CAMERA_FIELDS)
    ):
        raise CombinationError("goal019_output_binding_failure")
    return observed


def _read_csv(
    path: Path,
    *,
    fields: tuple[str, ...],
    rows: int,
    key_error: str,
) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != fields:
                raise CombinationError("source_schema_drift")
            values = list(reader)
    except OSError as exc:
        raise CombinationError("source_read_failure") from exc
    if len(values) != rows or any(set(row) != set(fields) or None in row for row in values):
        raise CombinationError("source_row_count_or_shape_drift")
    keys = [(row["species_id"], row["grid_cell_id"]) for row in values]
    if len(keys) != len(set(keys)):
        raise CombinationError(key_error)
    return values


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise CombinationError("coordinate_invalid") from exc
    if not result.is_finite():
        raise CombinationError("coordinate_invalid")
    return result


def _boolean(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise CombinationError("boolean_invalid")


def _validate_ala_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    species = Counter(row["species_id"] for row in rows)
    if set(species) != set(ACTIVE_SPECIES) | {EXCLUDED_SPECIES}:
        raise CombinationError("ala_species_footprint_drift")
    if species[EXCLUDED_SPECIES] != 34:
        raise CombinationError("macropus_frozen_count_drift")
    for row in rows:
        if (
            row["presence"] != "1"
            or not GRID_ID_RE.fullmatch(row["grid_cell_id"])
            or ala.grid_cell_id(float(_decimal(row["centroid_lon"])), float(_decimal(row["centroid_lat"])))
            != row["grid_cell_id"]
        ):
            raise CombinationError("ala_row_contract_drift")
        for field in (
            "source_row_count",
            "unique_provider_record_count",
            "resource_count",
            "dataset_count",
            "unknown_uncertainty_count",
            "qa_flag_count",
        ):
            try:
                if int(row[field]) < 0 or str(int(row[field])) != row[field]:
                    raise ValueError
            except ValueError as exc:
                raise CombinationError("ala_count_contract_drift") from exc
        _boolean(row["low_cell_certainty_only"])
    active = [row for row in rows if row["species_id"] != EXCLUDED_SPECIES]
    if len(active) != EXPECTED_OVERALL["active_ala_rows"]:
        raise CombinationError("active_ala_count_drift")
    return active, species[EXCLUDED_SPECIES]


def _validate_camera_rows(rows: list[dict[str, str]]) -> None:
    if set(row["species_id"] for row in rows) != set(ACTIVE_SPECIES):
        raise CombinationError("camera_species_footprint_drift")
    for row in rows:
        if (
            not GRID_ID_RE.fullmatch(row["grid_cell_id"])
            or ala.grid_cell_id(float(_decimal(row["centroid_lon"])), float(_decimal(row["centroid_lat"])))
            != row["grid_cell_id"]
            or row["pa_type"] not in {"presence", "survey_supported_absence"}
            or row["pa"] != ("1" if row["pa_type"] == "presence" else "0")
            or row["survey_supported_absence_rule_id"]
            != ("" if row["pa_type"] == "presence" else ABSENCE_RULE_ID)
        ):
            raise CombinationError("camera_row_contract_drift")
        counts: dict[str, int] = {}
        for field in (
            "site_count",
            "presence_site_count",
            "survey_supported_absence_site_count",
            "positive_source_row_count",
        ):
            try:
                counts[field] = int(row[field])
                if counts[field] < 0 or str(counts[field]) != row[field]:
                    raise ValueError
            except ValueError as exc:
                raise CombinationError("camera_count_contract_drift") from exc
        if (
            counts["site_count"]
            != counts["presence_site_count"]
            + counts["survey_supported_absence_site_count"]
        ):
            raise CombinationError("camera_count_reconciliation_failure")
        _boolean(row["source_conflict"])


def combine_rows(
    ala_rows: Iterable[Mapping[str, str]],
    camera_rows: Iterable[Mapping[str, str]],
    *,
    active_species: Iterable[str] = ACTIVE_SPECIES,
) -> list[dict[str, str]]:
    """Combine already validated unique species-cell rows using the frozen truth table."""
    active = set(active_species)
    ala_rows = list(ala_rows)
    camera_rows = list(camera_rows)
    ala_by_key = {
        (row["species_id"], row["grid_cell_id"]): dict(row)
        for row in ala_rows
        if row["species_id"] in active
    }
    camera_by_key = {
        (row["species_id"], row["grid_cell_id"]): dict(row)
        for row in camera_rows
        if row["species_id"] in active
    }
    if len(ala_by_key) != sum(
        1 for row in ala_rows if row["species_id"] in active
    ) or len(camera_by_key) != sum(
        1 for row in camera_rows if row["species_id"] in active
    ):
        raise CombinationError("duplicate_species_grid_key")

    output: list[dict[str, str]] = []
    for key in sorted(set(ala_by_key) | set(camera_by_key)):
        ala_row = ala_by_key.get(key)
        camera_row = camera_by_key.get(key)
        if ala_row is not None and camera_row is not None:
            if (
                _decimal(ala_row["centroid_lon"])
                != _decimal(camera_row["centroid_lon"])
                or _decimal(ala_row["centroid_lat"])
                != _decimal(camera_row["centroid_lat"])
            ):
                raise CombinationError("overlap_centroid_mismatch")
        source = ala_row or camera_row
        if source is None:
            raise CombinationError("empty_union_row")

        camera_presence = camera_row is not None and camera_row["pa_type"] == "presence"
        if ala_row is not None and camera_row is None:
            category = "ala_only_presence"
            final_pa, final_type, conflict = "1", "presence", False
        elif ala_row is None and camera_presence:
            category = "camera_only_presence"
            final_pa, final_type, conflict = "1", "presence", False
        elif ala_row is not None and camera_presence:
            category = "both_presence"
            final_pa, final_type, conflict = "1", "presence", False
        elif ala_row is not None and camera_row is not None:
            category = "ala_overrides_camera_absence"
            final_pa, final_type, conflict = "1", "presence", True
        else:
            category = "camera_absence_retained"
            final_pa, final_type, conflict = "0", "survey_supported_absence", False

        row = {
            "species_id": key[0],
            "grid_cell_id": key[1],
            "centroid_lon": source["centroid_lon"],
            "centroid_lat": source["centroid_lat"],
            "pa": final_pa,
            "pa_type": final_type,
            "survey_supported_absence_rule_id": (
                ABSENCE_RULE_ID if final_type == "survey_supported_absence" else ""
            ),
            "source_combination": category,
            "cross_source_conflict": str(conflict).lower(),
            "ala_presence": "",
            "ala_source_row_count": "",
            "ala_unique_provider_record_count": "",
            "ala_resource_count": "",
            "ala_dataset_count": "",
            "ala_unknown_uncertainty_count": "",
            "ala_qa_flag_count": "",
            "ala_low_cell_certainty_only": "",
            "camera_evidence": "",
            "camera_pa": "",
            "camera_pa_type": "",
            "camera_survey_supported_absence_rule_id": "",
            "camera_site_count": "",
            "camera_presence_site_count": "",
            "camera_survey_supported_absence_site_count": "",
            "camera_positive_source_row_count": "",
            "camera_internal_conflict": "",
        }
        if ala_row is not None:
            row.update(
                {
                    "ala_presence": ala_row["presence"],
                    "ala_source_row_count": ala_row["source_row_count"],
                    "ala_unique_provider_record_count": ala_row[
                        "unique_provider_record_count"
                    ],
                    "ala_resource_count": ala_row["resource_count"],
                    "ala_dataset_count": ala_row["dataset_count"],
                    "ala_unknown_uncertainty_count": ala_row[
                        "unknown_uncertainty_count"
                    ],
                    "ala_qa_flag_count": ala_row["qa_flag_count"],
                    "ala_low_cell_certainty_only": ala_row[
                        "low_cell_certainty_only"
                    ],
                }
            )
        if camera_row is not None:
            row.update(
                {
                    "camera_evidence": "1",
                    "camera_pa": camera_row["pa"],
                    "camera_pa_type": camera_row["pa_type"],
                    "camera_survey_supported_absence_rule_id": camera_row[
                        "survey_supported_absence_rule_id"
                    ],
                    "camera_site_count": camera_row["site_count"],
                    "camera_presence_site_count": camera_row[
                        "presence_site_count"
                    ],
                    "camera_survey_supported_absence_site_count": camera_row[
                        "survey_supported_absence_site_count"
                    ],
                    "camera_positive_source_row_count": camera_row[
                        "positive_source_row_count"
                    ],
                    "camera_internal_conflict": camera_row["source_conflict"],
                }
            )
        output.append(row)
    return output


def _matrix_conflicts(
    rows: Iterable[Mapping[str, str]],
    decision_bundle: Mapping[str, Any],
    islands_path: Path,
) -> int:
    exclusions = decision_bundle["policies"]["island_exclusions"][
        "species_exclusions"
    ]
    islands = camera._load_islands(islands_path)
    conflicts = 0
    for row in rows:
        if row["pa_type"] != "presence":
            continue
        point = Point(float(row["centroid_lon"]), float(row["centroid_lat"]))
        island_codes = [
            code for code, geometry in islands.items() if geometry.covers(point)
        ]
        if len(island_codes) > 1:
            raise CombinationError("overlapping_island_geometry")
        if island_codes and island_codes[0] in exclusions[row["species_id"]]:
            conflicts += 1
    return conflicts


def _summaries(
    rows: list[dict[str, str]],
    *,
    active_ala_rows: int,
    camera_rows: int,
    overlap_rows: int,
    excluded_macropus_rows: int,
    matrix_conflicts: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    categories = Counter(row["source_combination"] for row in rows)
    by_species: dict[str, dict[str, int]] = {}
    for species_id in sorted(ACTIVE_SPECIES):
        subset = [row for row in rows if row["species_id"] == species_id]
        counts = Counter(row["source_combination"] for row in subset)
        by_species[species_id] = {
            "ala_only": counts["ala_only_presence"],
            "override": counts["ala_overrides_camera_absence"],
            "both": counts["both_presence"],
            "camera_only": counts["camera_only_presence"],
            "absence_retained": counts["camera_absence_retained"],
            "final_presence": sum(row["pa_type"] == "presence" for row in subset),
            "final_absence": sum(
                row["pa_type"] == "survey_supported_absence" for row in subset
            ),
            "total": len(subset),
            "internal_conflict": sum(
                row["camera_internal_conflict"] == "true" for row in subset
            ),
        }
    overall = {
        "active_ala_rows": active_ala_rows,
        "camera_rows": camera_rows,
        "overlap_rows": overlap_rows,
        "output_rows": len(rows),
        "ala_only_presence": categories["ala_only_presence"],
        "camera_only_presence": categories["camera_only_presence"],
        "both_presence": categories["both_presence"],
        "ala_overrides_camera_absence": categories[
            "ala_overrides_camera_absence"
        ],
        "camera_absence_retained": categories["camera_absence_retained"],
        "final_presence": sum(row["pa_type"] == "presence" for row in rows),
        "final_survey_supported_absence": sum(
            row["pa_type"] == "survey_supported_absence" for row in rows
        ),
        "camera_internal_conflicts": sum(
            row["camera_internal_conflict"] == "true" for row in rows
        ),
        "ala_low_cell_certainty_only": sum(
            row["ala_low_cell_certainty_only"] == "true" for row in rows
        ),
        "unique_physical_cells": len({row["grid_cell_id"] for row in rows}),
        "excluded_macropus_ala_rows": excluded_macropus_rows,
    }
    reconciliation = {
        "ala_rows_reconcile": active_ala_rows
        == categories["ala_only_presence"]
        + categories["both_presence"]
        + categories["ala_overrides_camera_absence"],
        "camera_rows_reconcile": camera_rows
        == categories["camera_only_presence"]
        + categories["both_presence"]
        + categories["camera_absence_retained"]
        + categories["ala_overrides_camera_absence"],
        "camera_presence_reconciles": 4278
        == categories["camera_only_presence"] + categories["both_presence"],
        "camera_absence_reconciles": 2173
        == categories["camera_absence_retained"]
        + categories["ala_overrides_camera_absence"],
        "union_reconciles": len(rows)
        == active_ala_rows + camera_rows - overlap_rows,
        "categories_exhaustive": sum(categories.values()) == len(rows),
    }
    if (
        overall != EXPECTED_OVERALL
        or by_species != EXPECTED_BY_SPECIES
        or not all(reconciliation.values())
        or matrix_conflicts != 0
    ):
        raise CombinationError("accepted_oracle_mismatch")
    combination_summary = {
        "goal_id": GOAL_ID,
        "overall": overall,
        "by_species": by_species,
        "reconciliation": reconciliation,
    }
    spatial_summary = {
        "unique_physical_cells": overall["unique_physical_cells"],
        "overlap_species_grid_rows": overlap_rows,
        "centroid_mismatch_rows": 0,
        "grid_invariant_failures": 0,
        "matrix_conflicting_presences": matrix_conflicts,
        "provisional_exclusion_rules_retained": 2,
    }
    return combination_summary, spatial_summary


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def _output_metadata(path: Path, rows: int) -> dict[str, Any]:
    return {
        "private_output": {
            "bytes": path.stat().st_size,
            "rows": rows,
            "schema_sha256": _schema_sha256(OUTPUT_FIELDS),
            "sha256": sha256(path),
        },
        "private_output_ignored": True,
    }


def _build_payloads(
    plan: Mapping[str, Any],
    output_path: Path,
    combination_summary: Mapping[str, Any],
    spatial_summary: Mapping[str, Any],
    upstream_statuses: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    bindings = {
        role: {"sha256": binding["sha256"]}
        for role, binding in sorted(plan["bindings"].items())
    }
    return {
        "source_inventory.json": {
            "goal_id": GOAL_ID,
            "active_species_ids": list(ACTIVE_SPECIES),
            "excluded_downstream_species": {
                "species_id": EXCLUDED_SPECIES,
                "excluded_ala_rows": 34,
                "upstream_provenance_unchanged": True,
            },
            "frozen_bindings": bindings,
            "ordered_schemas": {
                "ala_input": list(ALA_FIELDS),
                "camera_input": list(CAMERA_FIELDS),
                "combined_output": list(OUTPUT_FIELDS),
            },
            "upstream_tracked_validation": dict(upstream_statuses),
        },
        "combination_summary.json": dict(combination_summary),
        "spatial_summary.json": dict(spatial_summary),
        "outputs.json": _output_metadata(
            output_path, combination_summary["overall"]["output_rows"]
        ),
        "review.json": {
            "readiness": "goal020_ala_camera_combination_complete",
            "private_replay_required": True,
            "matrix_conflicting_presences": 0,
            "privacy": REVIEW_PRIVACY,
            "classification": {
                "presence_dominates_across_sources": True,
                "survey_supported_absence_first_class": True,
                "absence_rule_id": ABSENCE_RULE_ID,
                "source_absent_provenance_blank": True,
            },
            "stopped_before": list(plan["stopped_before"]),
        },
    }


def _walk_strings(value: Any, *, keys: bool):
    if isinstance(value, Mapping):
        for key, item in value.items():
            if keys:
                yield str(key)
            yield from _walk_strings(item, keys=keys)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item, keys=keys)
    elif isinstance(value, str) and not keys:
        yield value


def assert_evidence_privacy(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    allowed_schema_names = set(ALA_FIELDS) | set(CAMERA_FIELDS) | set(OUTPUT_FIELDS)
    if any(
        key.lower() in FORBIDDEN_EVIDENCE_KEYS
        for key in _walk_strings(payloads, keys=True)
    ):
        raise CombinationError("tracked_evidence_privacy_failure")
    for value in _walk_strings(payloads, keys=False):
        lowered = value.lower()
        if value in allowed_schema_names:
            continue
        if (
            GRID_ID_RE.fullmatch(value)
            or "/users/" in lowered
            or "data/processed/" in lowered
            or "tas_cam" in lowered
            or re.search(r"-?\d{2,3}\.\d+[, ]+-?\d{2,3}\.\d+", value)
        ):
            raise CombinationError("tracked_evidence_privacy_failure")


def _write_evidence(
    evidence_dir: Path, payloads: Mapping[str, Mapping[str, Any]]
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=False)
    assert_evidence_privacy(payloads)
    entries: list[dict[str, Any]] = []
    for name in EVIDENCE_PAYLOAD_FILES:
        path = evidence_dir / name
        path.write_text(json.dumps(payloads[name], indent=2, sort_keys=True) + "\n")
        entries.append(
            {"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {"schema_version": "1.0", "files": entries},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _read_evidence(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    _validate_exact_files(
        evidence_dir, EVIDENCE_FILES, error="evidence_footprint_drift"
    )
    payloads = {
        name: _load_json(evidence_dir / name, "evidence_json_invalid")
        for name in EVIDENCE_PAYLOAD_FILES
    }
    manifest = _load_json(evidence_dir / "manifest.json", "manifest_json_invalid")
    entries = manifest.get("files")
    if (
        manifest.get("schema_version") != "1.0"
        or not isinstance(entries, list)
        or [entry.get("path") for entry in entries]
        != list(EVIDENCE_PAYLOAD_FILES)
    ):
        raise CombinationError("manifest_shape_drift")
    for entry in entries:
        path = evidence_dir / entry["path"]
        if (
            set(entry) != {"path", "bytes", "sha256"}
            or entry["bytes"] != path.stat().st_size
            or entry["sha256"] != sha256(path)
        ):
            raise CombinationError("manifest_binding_drift")
    assert_evidence_privacy(payloads)
    return payloads


def _validate_tracked_payloads(
    plan: Mapping[str, Any], payloads: Mapping[str, Mapping[str, Any]]
) -> None:
    inventory = payloads["source_inventory.json"]
    expected_bindings = {
        role: {"sha256": binding["sha256"]}
        for role, binding in sorted(plan["bindings"].items())
    }
    if (
        inventory.get("goal_id") != GOAL_ID
        or inventory.get("active_species_ids") != list(ACTIVE_SPECIES)
        or inventory.get("excluded_downstream_species")
        != {
            "species_id": EXCLUDED_SPECIES,
            "excluded_ala_rows": 34,
            "upstream_provenance_unchanged": True,
        }
        or inventory.get("frozen_bindings") != expected_bindings
        or inventory.get("ordered_schemas")
        != {
            "ala_input": list(ALA_FIELDS),
            "camera_input": list(CAMERA_FIELDS),
            "combined_output": list(OUTPUT_FIELDS),
        }
        or inventory.get("upstream_tracked_validation")
        != {
            "goal018": "goal018_tracked_evidence_valid_raw_replay_required",
            "goal019": "goal019_tracked_evidence_valid_private_replay_required",
        }
        or set(inventory)
        != {
            "goal_id",
            "active_species_ids",
            "excluded_downstream_species",
            "frozen_bindings",
            "ordered_schemas",
            "upstream_tracked_validation",
        }
    ):
        raise CombinationError("source_inventory_shape_drift")
    summary = payloads["combination_summary.json"]
    if (
        set(summary) != {"goal_id", "overall", "by_species", "reconciliation"}
        or summary.get("goal_id") != GOAL_ID
        or summary.get("overall") != EXPECTED_OVERALL
        or summary.get("by_species") != EXPECTED_BY_SPECIES
        or not isinstance(summary.get("reconciliation"), Mapping)
        or set(summary["reconciliation"])
        != {
            "ala_rows_reconcile",
            "camera_rows_reconcile",
            "camera_presence_reconciles",
            "camera_absence_reconciles",
            "union_reconciles",
            "categories_exhaustive",
        }
        or not all(value is True for value in summary["reconciliation"].values())
    ):
        raise CombinationError("combination_summary_shape_drift")
    if payloads["spatial_summary.json"] != {
        "unique_physical_cells": 5407,
        "overlap_species_grid_rows": 178,
        "centroid_mismatch_rows": 0,
        "grid_invariant_failures": 0,
        "matrix_conflicting_presences": 0,
        "provisional_exclusion_rules_retained": 2,
    }:
        raise CombinationError("spatial_summary_shape_drift")
    outputs = payloads["outputs.json"]
    metadata = outputs.get("private_output")
    if (
        set(outputs) != {"private_output", "private_output_ignored"}
        or outputs.get("private_output_ignored") is not True
        or not isinstance(metadata, Mapping)
        or set(metadata) != {"bytes", "rows", "schema_sha256", "sha256"}
        or not isinstance(metadata.get("bytes"), int)
        or metadata["bytes"] <= 0
        or metadata.get("rows") != 12868
        or metadata.get("schema_sha256") != _schema_sha256(OUTPUT_FIELDS)
        or not isinstance(metadata.get("sha256"), str)
        or SHA256_RE.fullmatch(metadata["sha256"]) is None
    ):
        raise CombinationError("outputs_shape_drift")
    if payloads["review.json"] != {
        "readiness": "goal020_ala_camera_combination_complete",
        "private_replay_required": True,
        "matrix_conflicting_presences": 0,
        "privacy": REVIEW_PRIVACY,
        "classification": {
            "presence_dominates_across_sources": True,
            "survey_supported_absence_first_class": True,
            "absence_rule_id": ABSENCE_RULE_ID,
            "source_absent_provenance_blank": True,
        },
        "stopped_before": list(plan["stopped_before"]),
    }:
        raise CombinationError("review_shape_drift")


def _recompute(
    plan_path: Path,
    plan: Mapping[str, Any],
    paths: Mapping[str, Path],
    output_path: Path,
    upstream_statuses: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    ala_rows = _read_csv(
        paths["goal018_presence"],
        fields=ALA_FIELDS,
        rows=6629,
        key_error="ala_duplicate_key",
    )
    camera_rows = _read_csv(
        paths["goal019_grid_evidence"],
        fields=CAMERA_FIELDS,
        rows=6451,
        key_error="camera_duplicate_key",
    )
    active_ala, excluded_count = _validate_ala_rows(ala_rows)
    _validate_camera_rows(camera_rows)
    ala_keys = {(row["species_id"], row["grid_cell_id"]) for row in active_ala}
    camera_keys = {
        (row["species_id"], row["grid_cell_id"]) for row in camera_rows
    }
    rows = combine_rows(active_ala, camera_rows)
    decision_bundle = _load_json(
        paths["decision_bundle"], "decision_bundle_invalid"
    )
    matrix_conflicts = _matrix_conflicts(
        rows, decision_bundle, paths["offshore_islands"]
    )
    combination_summary, spatial_summary = _summaries(
        rows,
        active_ala_rows=len(active_ala),
        camera_rows=len(camera_rows),
        overlap_rows=len(ala_keys & camera_keys),
        excluded_macropus_rows=excluded_count,
        matrix_conflicts=matrix_conflicts,
    )
    _write_csv(output_path, rows)
    return _build_payloads(
        plan,
        output_path,
        combination_summary,
        spatial_summary,
        upstream_statuses,
    )


def validate_evidence(
    plan_path: Path,
    evidence_dir: Path,
    *,
    full: bool = False,
    ala_input: Path | None = None,
    camera_input: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    plan_path = Path(plan_path)
    plan = _load_plan(plan_path)
    tracked_paths = _bound_paths(plan_path, plan, include_private=False)
    upstream_statuses = _validate_upstream_tracked(
        plan_path, plan, tracked_paths
    )
    payloads = _read_evidence(Path(evidence_dir))
    _validate_tracked_payloads(plan, payloads)
    if not full:
        if any(value is not None for value in (ala_input, camera_input, output_dir)):
            raise CombinationError("full_replay_flag_required")
        return {
            "readiness": "goal020_tracked_evidence_valid_private_replay_required",
            "private_replay_required": True,
        }

    root = plan_path.resolve().parents[1]
    private_paths = _bound_paths(plan_path, plan, include_private=True)
    overrides = {
        "goal018_presence": ala_input,
        "goal019_grid_evidence": camera_input,
    }
    for role, override in overrides.items():
        if override is not None:
            override = Path(override)
            if (
                not override.is_file()
                or override.is_symlink()
                or sha256(override) != EXPECTED_BINDING_HASHES[role]
            ):
                raise CombinationError(f"binding_drift:{role}")
            private_paths[role] = override
    output_dir = Path(output_dir) if output_dir is not None else root / plan["outputs"]["directory"]
    _validate_exact_files(output_dir, [OUTPUT_FILE], error="output_footprint_drift")
    with tempfile.TemporaryDirectory(prefix="goal020-replay-") as directory:
        expected_output = Path(directory) / OUTPUT_FILE
        expected_payloads = _recompute(
            plan_path,
            plan,
            private_paths,
            expected_output,
            upstream_statuses,
        )
        actual_output = output_dir / OUTPUT_FILE
        if actual_output.read_bytes() != expected_output.read_bytes():
            raise CombinationError("output_semantic_replay_failure")
        if payloads != expected_payloads:
            raise CombinationError("aggregate_evidence_semantic_replay_failure")
    return {
        "readiness": "goal020_ala_camera_combination_complete",
        "private_replay_required": False,
        "output_rows": EXPECTED_OVERALL["output_rows"],
    }


def _git_path_is_ignored(root: Path, path: Path) -> bool:
    try:
        relative = Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", relative.as_posix()],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def run(plan_path: Path) -> dict[str, Any]:
    plan_path = Path(plan_path)
    plan = _load_plan(plan_path)
    root = plan_path.resolve().parents[1]
    output_dir = (root / plan["outputs"]["directory"]).resolve()
    evidence_dir = (root / plan["evidence"]["directory"]).resolve()
    if not _git_path_is_ignored(root, output_dir):
        raise CombinationError("private_output_not_ignored")
    if output_dir.exists() or evidence_dir.exists():
        raise CombinationError("publication_destination_exists")
    paths = _bound_paths(plan_path, plan, include_private=True)
    upstream_statuses = _validate_upstream_tracked(plan_path, plan, paths)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix="goal020-stage-", dir=output_dir.parent)
    )
    stage_output = stage_root / "output"
    stage_evidence = stage_root / "evidence"
    try:
        stage_output.mkdir()
        payloads = _recompute(
            plan_path,
            plan,
            paths,
            stage_output / OUTPUT_FILE,
            upstream_statuses,
        )
        _write_evidence(stage_evidence, payloads)
        staged_payloads = _read_evidence(stage_evidence)
        _validate_tracked_payloads(plan, staged_payloads)
        stage_output.rename(output_dir)
        try:
            stage_evidence.rename(evidence_dir)
        except Exception as exc:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise CombinationError("evidence_publication_failure") from exc
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
    return {
        "readiness": "goal020_ala_camera_combination_complete",
        "output_rows": EXPECTED_OVERALL["output_rows"],
        "final_presence": EXPECTED_OVERALL["final_presence"],
        "final_survey_supported_absence": EXPECTED_OVERALL[
            "final_survey_supported_absence"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Goal020 ALA-camera evidence combination"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--plan", type=Path, required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("--plan", type=Path, required=True)
    validate_parser.add_argument("--evidence-dir", type=Path, required=True)
    validate_parser.add_argument("--full", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run(args.plan)
        else:
            result = validate_evidence(
                args.plan, args.evidence_dir, full=args.full
            )
    except CombinationError as exc:
        print(json.dumps({"readiness": "blocked", "reason": str(exc)}))
        return 2
    except Exception:
        print(json.dumps({"readiness": "blocked", "reason": "runtime_failure"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
