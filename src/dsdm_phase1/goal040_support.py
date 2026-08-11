"""Goal 040 Stage 7 target-group observation-support diagnostics.

This is an effort-proxy feasibility calculation.  It deliberately does not
make an absence, occupancy, prevalence, validation, or final-label claim.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
from pyproj import Geod, Transformer
from scipy.spatial import cKDTree

from .goal040_domain import validate_domain_manifest
from .goal040_normalisation import (
    CELL_PATH,
    CONTRACT_PATH,
    DOMAIN_PATH,
    MANIFEST_PATH as NORMALISATION_MANIFEST_PATH,
    _sha,
)
from .goal040_taxonomy import ANCHORS


SUPPORT_MANIFEST_PATH = Path("metadata/goal040_support_manifest.json")
OUTPUT_ROOT = Path("data/raw/goal040/support")
DIAGNOSTICS_FILE = "sparse_support_diagnostics.csv"
SPECIES_CELLS_PATH = Path("data/raw/goal040/normalisation/species_cells.csv")
CAMERA_PATH = Path("data/processed/camera/goal019-spatial-normalization/2026-07-24/grid_evidence.csv")
CAMERA_OUTPUTS_PATH = Path("evidence/camera_spatial_normalization/2026-07-24/outputs.json")
CAMERA_EXPECTED_SHA256 = "a16249991384d9b8545aee4027a7ac22a3ae7166bdd7e8a141ae815015021563"
CAMERA_EXPECTED_SCHEMA_SHA256 = "3c2fd3780b04aaae5185171e89d2d6957203bd9eb085ce4e1840977278e149d9"
CAMERA_FIELDS = [
    "species_id", "grid_cell_id", "centroid_lon", "centroid_lat", "pa", "pa_type",
    "survey_supported_absence_rule_id", "site_count", "presence_site_count",
    "survey_supported_absence_site_count", "positive_source_row_count", "source_conflict",
]
SPECIES_CELL_FIELDS = ["species", "cell_id", "state_code", "region"]
CELL_FIELDS = ["cell_id", "row_south_to_north", "column_west_to_east", "longitude", "latitude", "state_code", "region"]
DIAGNOSTIC_FIELDS = [
    "target", "cell_id", "region", "donor_count", "nearest_target_presence_m",
    "precedence_state", "eligible_x2", "eligible_x3", "eligible_x5",
]
REGIONS = ("southeast_mainland", "tasmania")
THRESHOLDS = (2, 3, 5)
DISTANCE_M = 5000.0
DOMAIN_BOUNDS = (135.375, 153.625, -43.6275, -23.7775)
# EPSG:3577 scale is close to one over the frozen Australian domain.  This
# deliberately loose conservative bound makes the projected radius a superset
# of all points that could improve the current WGS84 geodesic nearest distance.
PROJECTED_PER_GEODESIC_SCALE_BOUND = 2.0
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
SLUGS = {
    "Dasyurus maculatus": "dasyurus_maculatus",
    "Notamacropus rufogriseus": "notamacropus_rufogriseus",
    "Pseudocheirus peregrinus": "pseudocheirus_peregrinus",
    "Trichosurus vulpecula": "trichosurus_vulpecula",
    "Vombatus ursinus": "vombatus_ursinus",
}
GEOD = Geod(ellps="WGS84")
TRANSFORM = Transformer.from_crs("EPSG:4326", "EPSG:3577", always_xy=True)
RULES = {
    "donors": "all_21_stage6_support_taxa_other_than_target; ALA_species_cells_only",
    "camera_role": "target_detection_for_presence_precedence_and_distance_only; never_donor_support",
    "response_precedence": ["presence", "camera_survey_supported_absence", "target_group_background_candidate", "unknown"],
    "thresholds": {"primary": 3, "sensitivities": [2, 5], "nesting": "X5_subset_X3_subset_X2"},
    "distance": "same_region_nearest_target_presence_adaptive_EPSG3577_index_WGS84_Geod_refined; inclusive_greater_than_or_equal_5000m",
    "future_split_rule": "recompute_donor_support_and_distance_from_split_authorised_records; share_materialised_response_universe_across_methods",
    "scope": "full_data_feasibility_diagnostic_only; not_a_bound_on_future_split_candidate_counts; effort_proxy_not_absence_occupancy_prevalence_or_validation",
}
PRIVACY = {
    "tracked_row_payload": False,
    "donor_identities_retained": False,
    "cell_ids_retained": False,
    "camera_identifiers_retained": False,
    "private_paths_retained": False,
}


class Goal040SupportError(ValueError):
    """Fail-closed support error without private data values."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal040SupportError(reason)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise Goal040SupportError("decimal_coordinate_invalid") from exc
    _require(result.is_finite(), "decimal_coordinate_invalid")
    return result


def _csv_rows(path: Path, fields: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            _require(reader.fieldnames == fields, "private_input_schema_drift")
            rows = list(reader)
    except OSError as exc:
        raise Goal040SupportError("private_input_unavailable") from exc
    _require(all(set(row) == set(fields) for row in rows), "private_input_row_schema_drift")
    return rows


def _validate_contract_payload(contract: dict[str, Any]) -> None:
    support = contract.get("target_group_support", {})
    _require(
        contract.get("goal_id") == "goal040-se-mammal-acquisition-feasibility"
        and support.get("fact") == "distinct_other_eligible_native_support_species_per_target_cell"
        and support.get("exclude_target") is True
        and support.get("preserve_threshold_neutral_facts") is True
        and support.get("primary_threshold") == 3
        and support.get("sensitivity_thresholds") == [2, 5]
        and support.get("required_nesting") == "X5_subset_X3_subset_X2"
        and support.get("minimum_nearest_target_presence_distance_m") == 5000
        and support.get("distance_comparison") == "greater_than_or_equal"
        and support.get("split_allowed_records_only") is True
        and support.get("camera_absence_is_donor") is False
        and support.get("camera_concordance_role") == "aggregate_diagnostic_only_not_threshold_selection",
        "support_contract_drift",
    )


def _load_contract(root: Path) -> dict[str, Any]:
    try:
        contract = json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal040SupportError("support_contract_invalid") from exc
    _validate_contract_payload(contract)
    return contract


def _load_cells(root: Path) -> dict[str, tuple[Decimal, Decimal, str]]:
    boundary = json.loads((root / DOMAIN_PATH).read_text(encoding="utf-8"))
    validate_domain_manifest(boundary["exact_study_domain"])
    expected = boundary["exact_study_domain"]["grid"].get("ignored_cell_ledger_sha256")
    path = root / CELL_PATH
    _require(path.is_file() and _sha(path) == expected, "eligible_cell_ledger_authority_drift")
    cells: dict[str, tuple[Decimal, Decimal, str]] = {}
    for row in _csv_rows(path, CELL_FIELDS):
        cell = row["cell_id"]
        _require(cell not in cells and row["region"] in REGIONS, "eligible_cell_ledger_content_drift")
        cells[cell] = (_decimal(row["longitude"]), _decimal(row["latitude"]), row["region"])
    _require(len(cells) == boundary["exact_study_domain"]["grid"]["eligible_cell_count"], "eligible_cell_denominator_drift")
    return cells


def _load_species_cells(root: Path, cells: dict[str, tuple[Decimal, Decimal, str]]) -> dict[str, set[str]]:
    normal = json.loads((root / NORMALISATION_MANIFEST_PATH).read_text(encoding="utf-8"))
    _require(normal.get("status") == "complete_raw_replay_required", "normalisation_not_complete")
    output = normal.get("outputs", {}).get("species_cells", {})
    path = root / SPECIES_CELLS_PATH
    _require(path.is_file() and _sha(path) == output.get("sha256"), "species_cells_authority_drift")
    rows = _csv_rows(path, SPECIES_CELL_FIELDS)
    _require(len(rows) == output.get("rows"), "species_cells_row_count_drift")
    values: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        cell = row["cell_id"]
        _require(cell in cells and row["region"] == cells[cell][2], "species_cell_region_drift")
        _require(cell not in values[row["species"]], "species_cell_duplicate_key")
        values[row["species"]].add(cell)
    _require(set(values) == set(normal["taxon_tiers"]), "species_cell_taxon_coverage_drift")
    _require(set(ANCHORS) <= set(values), "anchor_species_cell_coverage_drift")
    return values


def _camera_rows(root: Path, cells: dict[str, tuple[Decimal, Decimal, str]]) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, int]]:
    try:
        output = json.loads((root / CAMERA_OUTPUTS_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal040SupportError("camera_output_receipt_invalid") from exc
    role = output.get("private_output_roles", {}).get("grid_evidence", {})
    path = root / CAMERA_PATH
    _require(role.get("sha256") == CAMERA_EXPECTED_SHA256 and role.get("schema_sha256") == CAMERA_EXPECTED_SCHEMA_SHA256 and _sha(path) == CAMERA_EXPECTED_SHA256, "camera_grid_authority_drift")
    rows = _csv_rows(path, CAMERA_FIELDS)
    _require(len(rows) == role.get("rows"), "camera_grid_row_count_drift")
    coordinate_to_cell = {(lon, lat): cell for cell, (lon, lat, _) in cells.items()}
    detections: dict[str, set[str]] = defaultdict(set)
    absences: dict[str, set[str]] = defaultdict(set)
    target_rows = retained_rows = 0
    for row in rows:
        if row["species_id"] not in SLUGS.values():
            continue
        target_rows += 1
        cell = coordinate_to_cell.get((_decimal(row["centroid_lon"]), _decimal(row["centroid_lat"])))
        # Goal 019's older camera frame extends beyond the later frozen exact
        # domain.  Such rows are not re-keyed; retained rows must match exactly.
        if cell is None:
            continue
        _require(cells[cell][2] == "tasmania", "camera_grid_alignment_region_drift")
        retained_rows += 1
        _require(row["pa"] in {"0", "1"}, "camera_response_state_drift")
        if row["pa"] == "1":
            _require(row["pa_type"] == "presence", "camera_presence_state_drift")
            detections[row["species_id"]].add(cell)
        else:
            _require(row["pa_type"] == "survey_supported_absence", "camera_absence_state_drift")
            absences[row["species_id"]].add(cell)
    return detections, absences, {"target_rows": target_rows, "rekeyed_rows": retained_rows, "outside_exact_domain_rows": target_rows - retained_rows}


def _nearest_geodesic_m(
    queries: list[tuple[Decimal, Decimal]], presences: list[tuple[Decimal, Decimal]],
) -> list[float]:
    """Find the true nearest under the encoded projected/geodesic scale bound."""
    _require(bool(presences), "target_presence_missing_in_region")
    if not queries:
        return []
    xmin, xmax, ymin, ymax = DOMAIN_BOUNDS
    _require(
        all(xmin <= float(lon) <= xmax and ymin <= float(lat) <= ymax for lon, lat in queries + presences),
        "distance_coordinate_outside_frozen_domain",
    )
    presence_lon = np.asarray([float(x) for x, _ in presences])
    presence_lat = np.asarray([float(y) for _, y in presences])
    query_lon = np.asarray([float(x) for x, _ in queries])
    query_lat = np.asarray([float(y) for _, y in queries])
    px, py = TRANSFORM.transform(presence_lon, presence_lat)
    qx, qy = TRANSFORM.transform(query_lon, query_lat)
    projected_queries = np.column_stack((qx, qy))
    tree = cKDTree(np.column_stack((px, py)))
    _, initial_indices = tree.query(projected_queries, k=1)
    initial_indices = np.asarray(initial_indices, dtype=int)
    initial_geodesic = np.asarray(GEOD.inv(
        query_lon, query_lat, presence_lon[initial_indices], presence_lat[initial_indices]
    )[2])
    # If projected distance <= 2 * geodesic distance everywhere in the frozen
    # domain, no point outside this radius can improve the initial geodesic hit.
    radii = np.nextafter(
        initial_geodesic * PROJECTED_PER_GEODESIC_SCALE_BOUND, np.inf
    )
    candidate_indices = tree.query_ball_point(projected_queries, radii)
    values: list[float] = []
    for lon, lat, nearby in zip(query_lon, query_lat, candidate_indices):
        _require(bool(nearby), "adaptive_neighbour_search_empty")
        other_lon = presence_lon[nearby]
        other_lat = presence_lat[nearby]
        values.append(float(np.min(GEOD.inv(
            np.full(len(nearby), lon), np.full(len(nearby), lat), other_lon, other_lat
        )[2])))
    return values


def _precedence(cell: str, presences: set[str], absences: set[str]) -> str:
    if cell in presences:
        return "presence"
    if cell in absences:
        return "camera_survey_supported_absence"
    return "unknown"


def _far_enough(distance_m: float) -> bool:
    return distance_m >= DISTANCE_M


def _file_receipt(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    rows = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        _require(next(reader, None) == DIAGNOSTIC_FIELDS, "support_output_schema_drift")
        for row in reader:
            _require(len(row) == len(DIAGNOSTIC_FIELDS), "support_output_row_schema_drift")
            digest.update(_canonical(row)); rows += 1
    return {
        "bytes": path.stat().st_size, "rows": rows, "sha256": _sha(path),
        "content_sha256": digest.hexdigest(),
        "schema_sha256": hashlib.sha256(_canonical(DIAGNOSTIC_FIELDS)).hexdigest(),
    }


def _rows_content_sha(rows: list[list[str]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_canonical(row))
    return digest.hexdigest()


def _read_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal040SupportError(reason) from exc
    _require(isinstance(value, dict), reason)
    return value


def _tracked_authorities(root: Path) -> tuple[dict[str, str], dict[str, int]]:
    """Resolve every private-input digest from tracked upstream evidence."""
    _load_contract(root)
    domain = _read_json(root / DOMAIN_PATH, "support_domain_manifest_invalid")
    exact_domain = domain.get("exact_study_domain")
    _require(isinstance(exact_domain, dict), "support_domain_manifest_invalid")
    validate_domain_manifest(exact_domain)
    grid = exact_domain.get("grid", {})
    region_counts = grid.get("region_counts")
    _require(
        isinstance(region_counts, dict)
        and set(region_counts) == set(REGIONS)
        and all(_nonnegative_int(value) and value > 0 for value in region_counts.values()),
        "support_domain_denominator_drift",
    )
    eligible_sha = grid.get("ignored_cell_ledger_sha256")
    _require(isinstance(eligible_sha, str) and SHA256_RE.fullmatch(eligible_sha) is not None, "eligible_cell_authority_digest_drift")

    normal = _read_json(root / NORMALISATION_MANIFEST_PATH, "support_normalisation_manifest_invalid")
    _require(
        normal.get("stage") == "qc-species-cell-normalisation"
        and normal.get("status") == "complete_raw_replay_required",
        "normalisation_not_complete",
    )
    species_sha = normal.get("outputs", {}).get("species_cells", {}).get("sha256")
    _require(isinstance(species_sha, str) and SHA256_RE.fullmatch(species_sha) is not None, "species_cells_authority_digest_drift")

    camera = _read_json(root / CAMERA_OUTPUTS_PATH, "camera_output_receipt_invalid")
    role = camera.get("private_output_roles", {}).get("grid_evidence", {})
    _require(
        camera.get("private_outputs_ignored") is True
        and role.get("sha256") == CAMERA_EXPECTED_SHA256
        and role.get("schema_sha256") == CAMERA_EXPECTED_SCHEMA_SHA256,
        "camera_grid_authority_drift",
    )
    return {
        "contract_sha256": _sha(root / CONTRACT_PATH),
        "domain_manifest_sha256": _sha(root / DOMAIN_PATH),
        "normalisation_manifest_sha256": _sha(root / NORMALISATION_MANIFEST_PATH),
        "eligible_cell_ledger_sha256": eligible_sha,
        "species_cells_sha256": species_sha,
        "camera_grid_evidence_sha256": CAMERA_EXPECTED_SHA256,
        "camera_grid_evidence_schema_sha256": CAMERA_EXPECTED_SCHEMA_SHA256,
        "camera_outputs_sha256": _sha(root / CAMERA_OUTPUTS_PATH),
    }, {region: int(region_counts[region]) for region in REGIONS}


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _threshold_counts(value: Any, reason: str) -> dict[str, int]:
    _require(
        isinstance(value, dict)
        and set(value) == {str(item) for item in THRESHOLDS}
        and all(_nonnegative_int(count) for count in value.values()),
        reason,
    )
    _require(value["5"] <= value["3"] <= value["2"], "support_threshold_nesting_drift")
    return value


def _validate_tracked_manifest_payload(
    manifest: dict[str, Any], expected_bindings: dict[str, str], denominators: dict[str, int],
) -> None:
    root_keys = {"schema_version", "goal_id", "stage", "status", "completed_at", "bindings", "rules", "summary", "outputs", "privacy"}
    _require(set(manifest) == root_keys, "support_manifest_structure_drift")
    _require(
        manifest.get("schema_version") == "1.0"
        and manifest.get("goal_id") == "goal040-se-mammal-acquisition-feasibility"
        and manifest.get("stage") == "target-group-observation-support"
        and manifest.get("status") == "complete_raw_replay_required"
        and isinstance(manifest.get("completed_at"), str)
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["completed_at"]) is not None,
        "support_manifest_identity_drift",
    )
    _require(manifest.get("bindings") == expected_bindings, "support_manifest_binding_drift")
    _require(manifest.get("rules") == RULES, "support_manifest_rule_drift")
    _require(manifest.get("privacy") == PRIVACY, "support_manifest_privacy_drift")

    outputs = manifest.get("outputs")
    _require(isinstance(outputs, dict) and set(outputs) == {"private_outputs_ignored", "private_output_roles"} and outputs.get("private_outputs_ignored") is True, "support_manifest_output_structure_drift")
    roles = outputs.get("private_output_roles")
    _require(isinstance(roles, dict) and set(roles) == {"sparse_support_diagnostics"}, "support_manifest_output_structure_drift")
    receipt = roles["sparse_support_diagnostics"]
    _require(isinstance(receipt, dict) and set(receipt) == {"bytes", "rows", "sha256", "content_sha256", "schema_sha256"}, "support_manifest_receipt_structure_drift")
    # Tracked-only validation can check opaque digest form, not private content;
    # Git supplies tracked provenance and raw replay authenticates those digests.
    _require(
        _nonnegative_int(receipt.get("bytes")) and receipt["bytes"] > 0
        and _nonnegative_int(receipt.get("rows")) and receipt["rows"] > 0
        and all(isinstance(receipt.get(key), str) and SHA256_RE.fullmatch(receipt[key]) is not None for key in ("sha256", "content_sha256", "schema_sha256"))
        and receipt["schema_sha256"] == hashlib.sha256(_canonical(DIAGNOSTIC_FIELDS)).hexdigest(),
        "support_manifest_receipt_value_drift",
    )

    summary = manifest.get("summary")
    _require(isinstance(summary, dict) and set(summary) == {"camera_alignment", "nesting_valid", "target_region"} and summary.get("nesting_valid") is True, "support_manifest_summary_structure_drift")
    alignment = summary["camera_alignment"]
    _require(
        isinstance(alignment, dict)
        and set(alignment) == {"target_rows", "rekeyed_rows", "outside_exact_domain_rows"}
        and all(_nonnegative_int(value) for value in alignment.values())
        and alignment["target_rows"] == alignment["rekeyed_rows"] + alignment["outside_exact_domain_rows"],
        "support_manifest_camera_alignment_drift",
    )
    target_region = summary["target_region"]
    expected_keys = {f"{target}|{region}" for target in ANCHORS for region in REGIONS}
    _require(isinstance(target_region, dict) and set(target_region) == expected_keys, "support_manifest_target_region_coverage_drift")
    row_keys = {
        "eligible_denominator", "donor_count_histogram_0_to_20", "target_presence_cells",
        "camera_survey_supported_absence_cells", "pre_distance_support_cells",
        "distance_rejected_under_5000m", "final_target_group_background_candidates",
        "candidate_to_presence_ratio", "camera_absence_concordance_diagnostic",
    }
    for key, item in target_region.items():
        region = key.rsplit("|", 1)[1]
        denominator = denominators[region]
        _require(isinstance(item, dict) and set(item) == row_keys, "support_manifest_target_region_structure_drift")
        _require(item["eligible_denominator"] == denominator, "support_manifest_regional_denominator_drift")
        histogram = item["donor_count_histogram_0_to_20"]
        _require(
            isinstance(histogram, dict)
            and set(histogram) == {str(value) for value in range(21)}
            and all(_nonnegative_int(value) for value in histogram.values())
            and sum(histogram.values()) == denominator,
            "support_manifest_histogram_drift",
        )
        presence = item["target_presence_cells"]
        absence = item["camera_survey_supported_absence_cells"]
        _require(
            _nonnegative_int(presence) and presence > 0 and presence <= denominator
            and _nonnegative_int(absence) and presence + absence <= denominator,
            "support_manifest_precedence_count_drift",
        )
        pre = _threshold_counts(item["pre_distance_support_cells"], "support_manifest_pre_distance_drift")
        rejected = _threshold_counts(item["distance_rejected_under_5000m"], "support_manifest_distance_rejection_drift")
        final = _threshold_counts(item["final_target_group_background_candidates"], "support_manifest_final_candidate_drift")
        _require(
            all(pre[level] == rejected[level] + final[level] for level in map(str, THRESHOLDS))
            and all(pre[str(level)] <= sum(histogram[str(value)] for value in range(level, 21)) for level in THRESHOLDS),
            "support_manifest_candidate_reconciliation_drift",
        )
        ratios = item["candidate_to_presence_ratio"]
        _require(isinstance(ratios, dict) and set(ratios) == {str(value) for value in THRESHOLDS}, "support_manifest_ratio_structure_drift")
        _require(
            all(isinstance(value, float) and math.isfinite(value) and value >= 0 for value in ratios.values())
            and all(math.isclose(ratios[level], final[level] / presence, rel_tol=1e-15, abs_tol=0.0) for level in map(str, THRESHOLDS)),
            "support_manifest_ratio_drift",
        )
        concordance = item["camera_absence_concordance_diagnostic"]
        _require(isinstance(concordance, dict) and set(concordance) == {str(value) for value in THRESHOLDS}, "support_manifest_camera_concordance_structure_drift")
        before: dict[str, int] = {}
        after: dict[str, int] = {}
        for level, values in concordance.items():
            _require(
                isinstance(values, dict)
                and set(values) == {"camera_absence_cells", "support_before_distance", "support_after_distance"}
                and all(_nonnegative_int(value) for value in values.values())
                and values["camera_absence_cells"] == absence
                and values["support_after_distance"] <= values["support_before_distance"] <= absence,
                "support_manifest_camera_concordance_drift",
            )
            before[level] = values["support_before_distance"]
            after[level] = values["support_after_distance"]
        _require(before["5"] <= before["3"] <= before["2"] and after["5"] <= after["3"] <= after["2"], "support_manifest_camera_concordance_nesting_drift")

    text = json.dumps(manifest, sort_keys=True).lower()
    _require(not any(token in text for token in ("longitude", "latitude", "grid_cell_id", "site_id", "data/raw/")), "support_manifest_private_material")


def _analyse(root: Path, *, write_output: bool) -> tuple[dict[str, Any], dict[str, Any] | None]:
    _load_contract(root)
    cells = _load_cells(root)
    species_cells = _load_species_cells(root, cells)
    camera_detection, camera_absence, camera_alignment = _camera_rows(root, cells)
    donor_cells: dict[str, set[str]] = defaultdict(set)
    for species, values in species_cells.items():
        for cell in values:
            donor_cells[cell].add(species)
    _require(len(species_cells) == 21, "support_taxon_coverage_drift")
    by_region: dict[str, list[str]] = {region: [] for region in REGIONS}
    for cell, (_, _, region) in cells.items():
        by_region[region].append(cell)
    report: dict[str, Any] = {"target_region": {}, "nesting_valid": True, "camera_alignment": camera_alignment}
    output_rows: list[list[str]] = []
    for target in sorted(ANCHORS):
        slug = SLUGS[target]
        target_ala = species_cells[target]
        presences = target_ala | camera_detection.get(slug, set())
        absences = camera_absence.get(slug, set()) - presences
        for region in REGIONS:
            regional_cells = by_region[region]
            target_presence = [cells[cell][:2] for cell in presences if cells[cell][2] == region]
            _require(bool(target_presence), "target_region_presence_missing")
            relevant = {
                cell for cell, members in donor_cells.items()
                if cells[cell][2] == region and (len(members) - int(target in members) > 0)
            } | {cell for cell in presences | absences if cells[cell][2] == region}
            counts = {cell: len(donor_cells.get(cell, set())) - int(target in donor_cells.get(cell, set())) for cell in relevant}
            _require(all(0 <= value <= 20 for value in counts.values()), "donor_count_out_of_range")
            histogram = Counter(counts.get(cell, 0) for cell in regional_cells)
            _require(sum(histogram.values()) == len(regional_cells), "histogram_denominator_drift")
            distance_cells = sorted(relevant)
            distances = dict(zip(distance_cells, _nearest_geodesic_m([cells[cell][:2] for cell in distance_cells], target_presence)))
            state = {cell: _precedence(cell, presences, absences) for cell in relevant}
            unknown = [cell for cell in relevant if state[cell] == "unknown"]
            pre = {threshold: sum(counts[cell] >= threshold for cell in unknown) for threshold in THRESHOLDS}
            rejected = {threshold: sum(counts[cell] >= threshold and distances[cell] < DISTANCE_M for cell in unknown) for threshold in THRESHOLDS}
            final = {threshold: sum(counts[cell] >= threshold and _far_enough(distances[cell]) for cell in unknown) for threshold in THRESHOLDS}
            _require(final[5] <= final[3] <= final[2] and pre[5] <= pre[3] <= pre[2], "threshold_nesting_failure")
            report["nesting_valid"] = report["nesting_valid"] and final[5] <= final[3] <= final[2]
            absence_cells = [cell for cell in absences if cells[cell][2] == region]
            concordance = {
                str(threshold): {
                    "camera_absence_cells": len(absence_cells),
                    "support_before_distance": sum(counts.get(cell, 0) >= threshold for cell in absence_cells),
                    "support_after_distance": sum(counts.get(cell, 0) >= threshold and _far_enough(distances.get(cell, 0.0)) for cell in absence_cells),
                }
                for threshold in THRESHOLDS
            }
            report["target_region"][f"{target}|{region}"] = {
                "eligible_denominator": len(regional_cells),
                "donor_count_histogram_0_to_20": {str(value): histogram.get(value, 0) for value in range(21)},
                "target_presence_cells": sum(cell in presences for cell in regional_cells),
                "camera_survey_supported_absence_cells": len(absence_cells),
                "pre_distance_support_cells": {str(key): value for key, value in pre.items()},
                "distance_rejected_under_5000m": {str(key): value for key, value in rejected.items()},
                "final_target_group_background_candidates": {str(key): value for key, value in final.items()},
                "candidate_to_presence_ratio": {str(key): (final[key] / sum(cell in presences for cell in regional_cells)) for key in THRESHOLDS},
                "camera_absence_concordance_diagnostic": concordance,
            }
            for cell in distance_cells:
                count = counts[cell]
                current = state[cell]
                output_rows.append([
                    target, cell, region, str(count), f"{distances[cell]:.6f}", current,
                    str(current == "unknown" and count >= 2 and _far_enough(distances[cell])).lower(),
                    str(current == "unknown" and count >= 3 and _far_enough(distances[cell])).lower(),
                    str(current == "unknown" and count >= 5 and _far_enough(distances[cell])).lower(),
                ])
    _require(len(report["target_region"]) == 10 and report["nesting_valid"], "support_result_coverage_drift")
    private = None
    if write_output:
        output = root / OUTPUT_ROOT
        output.mkdir(parents=True, exist_ok=True)
        _require({path.name for path in output.iterdir()} <= {DIAGNOSTICS_FILE}, "support_output_footprint_drift")
        path = output / DIAGNOSTICS_FILE
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(DIAGNOSTIC_FIELDS)
            writer.writerows(output_rows)
        private = _file_receipt(path)
        _require(private["content_sha256"] == _rows_content_sha(output_rows), "support_output_content_drift")
    else:
        private = {"rows": len(output_rows), "content_sha256": _rows_content_sha(output_rows)}
    return report, private


def _manifest(root: Path, report: dict[str, Any], private: dict[str, Any]) -> dict[str, Any]:
    bindings, _ = _tracked_authorities(root)
    return {
        "schema_version": "1.0", "goal_id": "goal040-se-mammal-acquisition-feasibility",
        "stage": "target-group-observation-support", "status": "complete_raw_replay_required",
        "completed_at": _now(),
        "bindings": bindings,
        "rules": RULES,
        "summary": report,
        "outputs": {"private_outputs_ignored": True, "private_output_roles": {"sparse_support_diagnostics": private}},
        "privacy": PRIVACY,
    }


def run_support(root: Path) -> dict[str, Any]:
    root = Path(root)
    report, private = _analyse(root, write_output=True)
    _require(private is not None, "support_output_missing")
    manifest = _manifest(root, report, private)
    (root / SUPPORT_MANIFEST_PATH).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validate_support(root, require_raw=True)


def validate_support(root: Path, *, require_raw: bool = False) -> dict[str, Any]:
    root = Path(root)
    expected, denominators = _tracked_authorities(root)
    manifest = _read_json(root / SUPPORT_MANIFEST_PATH, "support_manifest_invalid")
    _validate_tracked_manifest_payload(manifest, expected, denominators)
    if not require_raw:
        return {"status": "tracked_support_manifest_structure_valid_raw_replay_required", "raw_replay_required": True}
    output = root / OUTPUT_ROOT
    _require(output.is_dir() and {path.name for path in output.iterdir()} == {DIAGNOSTICS_FILE}, "support_output_footprint_drift")
    private = _file_receipt(output / DIAGNOSTICS_FILE)
    _require(private == manifest["outputs"]["private_output_roles"]["sparse_support_diagnostics"], "support_output_receipt_drift")
    replay, replay_output = _analyse(root, write_output=False)
    _require(replay == manifest["summary"], "support_raw_replay_disagrees_with_manifest")
    _require(
        replay_output is not None
        and replay_output["rows"] == private["rows"]
        and replay_output["content_sha256"] == private["content_sha256"],
        "support_sparse_output_disagrees_with_raw_replay",
    )
    return {"status": "support_complete_raw_replay_validated", "raw_replay_required": False, **manifest["summary"]}
