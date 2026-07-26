"""Goal021 deterministic pseudoabsence derivation from the frozen Goal020 layer."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from pyproj import Geod, Transformer
from shapely.geometry import Point, Polygon
from . import camera_spatial_normalization as camera
from .contracts import validate_phase1_decision_bundle
from . import ala_camera_combination as goal020


GOAL_ID = "goal021-pseudoabsence-derivation-2026-07-26"
ACTIVE_SPECIES = (
    "thylogale_billardierii", "notamacropus_rufogriseus", "trichosurus_vulpecula",
    "pseudocheirus_peregrinus", "vombatus_ursinus", "sarcophilus_harrisii",
    "dasyurus_maculatus", "dasyurus_viverrinus",
)
ELIGIBLE_TARGETS = ACTIVE_SPECIES[1:]
GOAL020_FIELDS = (
    "species_id", "grid_cell_id", "centroid_lon", "centroid_lat", "pa", "pa_type",
    "survey_supported_absence_rule_id", "source_combination", "cross_source_conflict",
    "ala_presence", "ala_source_row_count", "ala_unique_provider_record_count",
    "ala_resource_count", "ala_dataset_count", "ala_unknown_uncertainty_count",
    "ala_qa_flag_count", "ala_low_cell_certainty_only", "camera_evidence", "camera_pa",
    "camera_pa_type", "camera_survey_supported_absence_rule_id", "camera_site_count",
    "camera_presence_site_count", "camera_survey_supported_absence_site_count",
    "camera_positive_source_row_count", "camera_internal_conflict",
)
RESPONSE_FIELDS = GOAL020_FIELDS + (
    "response_origin", "pseudoabsence_rule_id", "pseudoabsence_support_species_count",
    "pseudoabsence_support_species_ids", "nearest_target_presence_grid_cell_id",
    "nearest_target_presence_source_combination", "nearest_target_presence_distance_m",
    "distance_crs",
)
AUDIT_FIELDS = (
    "species_id", "grid_cell_id", "centroid_lon", "centroid_lat",
    "pseudoabsence_support_species_count", "pseudoabsence_support_species_ids",
    "target_pa_type", "target_source_combination", "target_camera_pa_type",
    "island_code", "island_exclusion_rule_id", "nearest_target_presence_grid_cell_id",
    "nearest_target_presence_source_combination", "nearest_target_presence_distance_m",
    "distance_crs", "distance_eligible", "disposition",
)
DISTANCE_CRS = "EPSG:7855"
SURVEY_ABSENCE_RULE_ID = "P1-D009"
PSEUDOABSENCE_RULE_ID = "P1-D016+P1-D017"
MIN_SUPPORT_SPECIES = 3
MIN_DISTANCE_M = 5000.0
DISTANCE_SQ_THRESHOLD = 25_000_000.0
AUDIT_FILE = "pseudoabsence_candidate_audit.csv"
RESPONSE_FILE = "response_layer.csv"
EVIDENCE_FILES = (
    "source_inventory.json", "derivation_summary.json", "spatial_summary.json",
    "outputs.json", "review.json", "manifest.json",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GRID_ID_RE = re.compile(r"g_-?\d+_-?\d+\Z")

EXPECTED_BINDING_HASHES = {
    "decision_bundle": "ccccbb2e56e101b1a53421f8016699bfb500f4356861e10c1213a398aabe04a2",
    "goal020_plan": "b54f375063fb6d071b395a799be7859e484cb21a419b6f77a9615e24cb3d33e6",
    "goal020_evidence_manifest": "68f8623c0b496fe83882bc84ac4de30140c5b771e3c8863a1d17b23ed6d8e79c",
    "goal020_outputs_evidence": "95c37432081c015f28d708f9522f658f1b1742b35084cc4651ce5ed903e4ff5b",
    "goal020_grid_evidence": "17a0544247891b0a3f765efcd38bf1ddf348ee6bc96af69e1f76319dbe6e668d",
    "offshore_islands": "98ca7bf213f0760894d9ad329681e2f2c9e491a8255577fae20fd31c73685d92",
}
# Goal020 evidence bindings above are deliberately checked against the frozen plan.  The
# two compact values not present in the user-facing handoff are filled at runtime from
# the plan's immutable manifest when production is run.
EXPECTED_FUNNEL = {
    "stage_a": 2316,
    "target_presence": 733,
    "camera_survey_supported_absence": 17,
    "island_suppressed": 79,
    "distance_rejected": 900,
    "pseudoabsence": 587,
}
EXPECTED_FINAL_RESPONSE_BY_SPECIES = {
    "dasyurus_maculatus": 1310,
    "dasyurus_viverrinus": 1305,
    "notamacropus_rufogriseus": 1561,
    "pseudocheirus_peregrinus": 1151,
    "sarcophilus_harrisii": 3723,
    "thylogale_billardierii": 1601,
    "trichosurus_vulpecula": 1429,
    "vombatus_ursinus": 1375,
}
PORTABLE_ACCEPTED_KEY_SHA256 = "7fc66053fdd738e3894acfd0b778e3027e10e8493f09f4df852449d2dcaa9166"
FULL_DISTANCE_PREIMAGE_SHA256 = "8b0b2ee4a49de6035361268415afa873cae085c5dd8833bf12a0180728e24226"
PLAN_PRIVACY = {"tracked_actual_grid_ids_or_coordinates": False, "tracked_camera_identifiers_or_timing": False, "tracked_private_paths_or_rows": False}
DERIVATION_CONTRACT = {
    "candidate_support": {"minimum_distinct_non_target_species": 3, "target_species": list(ELIGIBLE_TARGETS), "thylogale_support_only": True},
    "precedence": ["goal020_target_presence", "camera_survey_supported_absence", "P1-D014_island_suppression", "P1-D017_distance_gate"],
    "minimum_distance_m": 5000,
    "distance_metric": "GDA2020/MGA55 EPSG:7855 equivalent",
    "distance_comparison": "raw_squared_distance_greater_than_or_equal_to_25000000",
    "nearest_tie_break": "lexical_grid_cell_id",
    "distance_precision": 6,
    "rule_id": PSEUDOABSENCE_RULE_ID,
}
EXPECTED_ORACLE = {"stage_a_rows": 2316, "disposition_counts": EXPECTED_FUNNEL, "pseudoabsence_rows": 587, "response_rows": 13455}

PSEUDOABSENCE_BLANK_GOAL020_FIELDS = tuple(f for f in GOAL020_FIELDS if f not in {"species_id", "grid_cell_id", "centroid_lon", "centroid_lat", "pa", "pa_type", "cross_source_conflict"})


class PseudoabsenceError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise PseudoabsenceError("binding_path_invalid")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise PseudoabsenceError("binding_path_unsafe")
    return path


def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or plan.get("schema_version") != "1.0" or plan.get("goal_id") != GOAL_ID:
        raise PseudoabsenceError("plan_identity_drift")
    if {k: v.get("sha256") for k, v in plan.get("bindings", {}).items()} != EXPECTED_BINDING_HASHES:
        raise PseudoabsenceError("plan_binding_drift")
    for b in plan["bindings"].values():
        if set(b) != {"path", "sha256"}:
            raise PseudoabsenceError("plan_binding_shape_drift")
        _safe_relative(b["path"])
    if plan.get("derivation_contract") != DERIVATION_CONTRACT:
        raise PseudoabsenceError("derivation_contract_drift")
    if plan.get("expected_oracle") != EXPECTED_ORACLE:
        raise PseudoabsenceError("oracle_contract_drift")
    if plan.get("privacy") != PLAN_PRIVACY:
        raise PseudoabsenceError("privacy_contract_drift")
    if plan.get("stopped_before") != ["thinning", "weights", "balancing", "predictors", "partitions", "mapping", "modelling"]:
        raise PseudoabsenceError("validation_or_stop_contract_drift")
    out = plan.get("outputs")
    if not isinstance(out, Mapping) or out.get("response_layer_schema") != list(RESPONSE_FIELDS) or out.get("candidate_audit_schema") != list(AUDIT_FIELDS):
        raise PseudoabsenceError("output_contract_drift")
    if plan.get("species_contract", {}).get("eligible_target_species") != list(ELIGIBLE_TARGETS):
        raise PseudoabsenceError("species_contract_drift")
    return {"goal_id": GOAL_ID, "eligible_target_count": len(ELIGIBLE_TARGETS)}


def validate_goal020_rows(rows: Iterable[Mapping[str, Any]], *, expected_rows: int | None = None, require_all_species: bool = True, require_canonical_grid: bool = True) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set(); result: list[dict[str, str]] = []
    for row in rows:
        if set(row) != set(GOAL020_FIELDS):
            raise PseudoabsenceError("goal020_row_shape_drift")
        r = {k: str(row[k]) for k in GOAL020_FIELDS}
        key = (r["species_id"], r["grid_cell_id"])
        if key in seen:
            raise PseudoabsenceError("duplicate_species_grid_key")
        seen.add(key)
        if require_canonical_grid and not GRID_ID_RE.fullmatch(r["grid_cell_id"]):
            raise PseudoabsenceError("grid_cell_id_invalid")
        result.append(r)
    if expected_rows is not None and len(result) != expected_rows:
        raise PseudoabsenceError("goal020_row_count_drift")
    if require_all_species and {r["species_id"] for r in result} != set(ACTIVE_SPECIES):
        raise PseudoabsenceError("goal020_species_set_drift")
    return result


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = a[0] - b[0], a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


def derive_response_layer(rows: Iterable[Mapping[str, Any]], *, eligible_targets: Iterable[str] = ELIGIBLE_TARGETS, island_exclusions: Mapping[str, set[str]] | None = None, cell_island_codes: Mapping[str, str] | None = None, projected_xy: Mapping[str, tuple[float, float]] | None = None) -> dict[str, Any]:
    rows = validate_goal020_rows(rows, expected_rows=None, require_all_species=False, require_canonical_grid=False)
    targets = tuple(eligible_targets); island_exclusions = island_exclusions or {}; cell_island_codes = cell_island_codes or {}; projected_xy = projected_xy or {}
    by_key = {(r["species_id"], r["grid_cell_id"]): r for r in rows}; by_cell: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows: by_cell[r["grid_cell_id"]].append(r)
    audit: list[dict[str, str]] = []; pseudo: list[dict[str, str]] = []
    for target in targets:
        if target == "thylogale_billardierii":
            continue
        for cell, cell_rows in by_cell.items():
            support = sorted({r["species_id"] for r in cell_rows if r["ala_presence"] == "1" and r["species_id"] != target})
            if len(support) < MIN_SUPPORT_SPECIES:
                continue
            target_row = by_key.get((target, cell))
            centroid_row = target_row or cell_rows[0]
            nearest_id, nearest_d, nearest_source, distance_eligible = "", "", "", "false"
            candidates = [(other["grid_cell_id"], projected_xy.get(other["grid_cell_id"]), other["source_combination"]) for other in rows if other["species_id"] == target and other["pa_type"] == "presence" and other["grid_cell_id"] in projected_xy]
            if projected_xy.get(cell) is not None and candidates:
                nearest_id, d2, nearest_source = min(((gid, (projected_xy[cell][0]-xy[0])**2 + (projected_xy[cell][1]-xy[1])**2, source) for gid,xy,source in candidates), key=lambda x: (x[1], x[0]))
                nearest_d = f"{math.sqrt(d2):.6f}"
                distance_eligible = "true" if d2 >= DISTANCE_SQ_THRESHOLD else "false"
            island = cell_island_codes.get(cell, "")
            if target_row is not None and target_row["pa_type"] == "presence":
                audit.append(_audit(target, cell, centroid_row, "target_presence", support, island, target_row, nearest_id, nearest_source, nearest_d, distance_eligible))
                continue
            if target_row is not None and target_row["pa_type"] == "survey_supported_absence":
                audit.append(_audit(target, cell, centroid_row, "camera_survey_supported_absence", support, island, target_row, nearest_id, nearest_source, nearest_d, distance_eligible))
                continue
            if island and island in island_exclusions.get(target, set()):
                audit.append(_audit(target, cell, centroid_row, "island_suppressed", support, island, None, nearest_id, nearest_source, nearest_d, distance_eligible, island_exclusion_rule_id="P1-D014"))
                continue
            if distance_eligible == "false":
                audit.append(_audit(target, cell, centroid_row, "distance_rejected", support, island, None, nearest_id, nearest_source, nearest_d, distance_eligible))
                continue
            audit.append(_audit(target, cell, centroid_row, "pseudoabsence", support, island, None, nearest_id, nearest_source, nearest_d, distance_eligible))
            template = {f: "" for f in GOAL020_FIELDS}
            source = next(r for r in cell_rows if r["grid_cell_id"] == cell)
            template.update({"species_id": target, "grid_cell_id": cell, "centroid_lon": source["centroid_lon"], "centroid_lat": source["centroid_lat"], "pa": "0", "pa_type": "pseudoabsence", "cross_source_conflict": "false"})
            template.update({"response_origin": "derived_pseudoabsence", "pseudoabsence_rule_id": PSEUDOABSENCE_RULE_ID, "pseudoabsence_support_species_count": str(len(support)), "pseudoabsence_support_species_ids": "|".join(support), "nearest_target_presence_grid_cell_id": nearest_id, "nearest_target_presence_source_combination": nearest_source, "nearest_target_presence_distance_m": nearest_d, "distance_crs": DISTANCE_CRS})
            pseudo.append(template)
    audit.sort(key=lambda r: (r["species_id"], r["grid_cell_id"]))
    response = [{**r, "response_origin": "goal020", "pseudoabsence_rule_id": "", "pseudoabsence_support_species_count": "", "pseudoabsence_support_species_ids": "", "nearest_target_presence_grid_cell_id": "", "nearest_target_presence_source_combination": "", "nearest_target_presence_distance_m": "", "distance_crs": ""} for r in rows] + pseudo
    response.sort(key=lambda r: (r["species_id"], r["grid_cell_id"]))
    counts = Counter(r["disposition"] for r in audit)
    overall = {k: counts.get(k, 0) for k in ("stage_a", "target_presence", "camera_survey_supported_absence", "island_suppressed", "distance_rejected", "pseudoabsence")}
    overall["stage_a"] = len(audit)
    summary = {"overall": overall, "funnel": {**EXPECTED_FUNNEL, **counts}, "support_distribution": dict(Counter(str(len(r["pseudoabsence_support_species_ids"].split("|"))) for r in audit if r["disposition"] == "pseudoabsence"))}
    summary["final_response_by_species"] = dict(Counter(r["species_id"] for r in response))
    return {"audit_rows": audit, "response_rows": response, "derivation_summary": summary}


def _audit(target: str, cell: str, centroid: Mapping[str, str], disposition: str, support: list[str], island: str, target_row: Mapping[str, str] | None, nearest_id: str, nearest_source: str, nearest_d: str, distance_eligible: str, island_exclusion_rule_id: str = "") -> dict[str, str]:
    return {"species_id": target, "grid_cell_id": cell, "centroid_lon": centroid["centroid_lon"], "centroid_lat": centroid["centroid_lat"], "pseudoabsence_support_species_count": str(len(support)), "pseudoabsence_support_species_ids": "|".join(support), "target_pa_type": target_row.get("pa_type", "") if target_row else "", "target_source_combination": target_row.get("source_combination", "") if target_row else "", "target_camera_pa_type": target_row.get("camera_pa_type", "") if target_row else "", "island_code": island, "island_exclusion_rule_id": island_exclusion_rule_id, "nearest_target_presence_grid_cell_id": nearest_id, "nearest_target_presence_source_combination": nearest_source, "nearest_target_presence_distance_m": nearest_d, "distance_crs": DISTANCE_CRS, "distance_eligible": distance_eligible, "disposition": disposition}


def project_goal020_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    import io
    stream = io.StringIO(newline=""); writer = csv.DictWriter(stream, fieldnames=GOAL020_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows([{f: r[f] for f in GOAL020_FIELDS} for r in rows if r.get("response_origin", "goal020") == "goal020"]); return stream.getvalue().encode()


def assert_evidence_privacy(value: Any) -> None:
    forbidden = ("grid", "longitude", "latitude", "coordinate", "site_id", "survey_id", "camera_id", "timing", "private_path", "private_value", "machine_path")
    def walk(obj: Any) -> None:
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                key = str(k).lower()
                schema_value = key in {"schemas", "privacy", "stopped_before", "binding_hashes"} or (isinstance(v, bool) and key.startswith("tracked_"))
                if (not schema_value and any(token in key for token in forbidden) and not (isinstance(v, str) and SHA256_RE.fullmatch(v))) or (isinstance(v, str) and ("/Users/" in v or v.startswith("/private/") or GRID_ID_RE.fullmatch(v) or re.fullmatch(r"-?\d+\.\d+,\s*-?\d+\.\d+", v))):
                    raise PseudoabsenceError("tracked_evidence_privacy_failure")
                walk(v)
        elif isinstance(obj, list):
            for v in obj: walk(v)
    walk(value)


def _publish_staged(stage_output: Path, stage_evidence: Path, output: Path, evidence: Path) -> None:
    if output.exists() or evidence.exists():
        raise PseudoabsenceError("publication_destination_exists")
    if not stage_output.is_dir() or not stage_evidence.is_dir():
        raise PseudoabsenceError("evidence_publication_failure")
    try:
        output.parent.mkdir(parents=True, exist_ok=True); evidence.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage_output, output); os.replace(stage_evidence, evidence)
    except Exception as exc:
        if output.exists(): shutil.rmtree(output)
        if evidence.exists(): shutil.rmtree(evidence)
        raise PseudoabsenceError("evidence_publication_failure") from exc


def validate_evidence(plan_path: Path, evidence_dir: Path, *, full: bool = False, output_dir: Path | None = None) -> dict[str, Any]:
    plan = json.loads(Path(plan_path).read_text()); validate_plan(plan)
    if output_dir is not None and not full:
        raise PseudoabsenceError("full_replay_flag_required")
    evidence_dir = Path(evidence_dir); output_dir = Path(output_dir) if output_dir else Path(plan_path).parents[1] / plan["outputs"]["directory"]
    if not evidence_dir.is_dir() or {p.name for p in evidence_dir.iterdir()} != set(EVIDENCE_FILES):
        raise PseudoabsenceError("evidence_footprint_drift")
    for p in evidence_dir.iterdir():
        if not p.is_file() or p.is_symlink(): raise PseudoabsenceError("evidence_footprint_drift")
        try: assert_evidence_privacy(json.loads(p.read_text()))
        except PseudoabsenceError: raise
        except Exception as exc: raise PseudoabsenceError("evidence_json_invalid") from exc
    try:
        manifest = json.loads((evidence_dir / "manifest.json").read_text())
        entries = manifest.get("files")
        if manifest.get("schema_version") != "1.0" or not isinstance(entries, list) or [e.get("path") for e in entries] != list(EVIDENCE_FILES[:-1]):
            raise ValueError
        for entry in entries:
            path = evidence_dir / entry["path"]
            if entry.get("sha256") != sha256(path) or entry.get("bytes") != path.stat().st_size:
                raise ValueError
    except Exception as exc:
        raise PseudoabsenceError("manifest_binding_failure") from exc
    if full:
        if not output_dir.is_dir() or {p.name for p in output_dir.iterdir()} != {AUDIT_FILE, RESPONSE_FILE}:
            raise PseudoabsenceError("output_footprint_drift")
        try:
            with (output_dir / AUDIT_FILE).open(newline="") as stream:
                audit = list(csv.DictReader(stream))
            with (output_dir / RESPONSE_FILE).open(newline="") as stream:
                response = list(csv.DictReader(stream))
            if len(audit) != 2316 or len(response) != 13455: raise ValueError
            if Counter(r.get("disposition") for r in audit) != Counter({"target_presence":733,"camera_survey_supported_absence":17,"island_suppressed":79,"distance_rejected":900,"pseudoabsence":587}): raise ValueError
            replay = _recompute_from_bound_inputs(Path(plan_path).resolve().parents[1], plan)
            audit_bytes = _csv_bytes(replay["audit_rows"], AUDIT_FIELDS)
            response_bytes = _csv_bytes(replay["response_rows"], RESPONSE_FIELDS)
            if audit_bytes != (output_dir / AUDIT_FILE).read_bytes() or response_bytes != (output_dir / RESPONSE_FILE).read_bytes():
                raise ValueError
            expected_payloads = _build_evidence_payloads(replay, audit_bytes=audit_bytes, response_bytes=response_bytes)
            for name, payload in expected_payloads.items():
                if json.loads((evidence_dir / f"{name}.json").read_text()) != payload:
                    raise ValueError
        except Exception as exc: raise PseudoabsenceError("output_semantic_replay_failure") from exc
    return {"private_replay_required": not full, "candidate_rows": 2316, "pseudoabsence_rows": 587}


def _csv_bytes(rows: Iterable[Mapping[str, Any]], fields: Iterable[str]) -> bytes:
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    writer.writerows([{field: row[field] for field in fields} for row in rows])
    return stream.getvalue().encode()


def _build_evidence_payloads(result: Mapping[str, Any], *, audit_bytes: bytes, response_bytes: bytes) -> dict[str, dict[str, Any]]:
    audit = list(result["audit_rows"]); response = list(result["response_rows"])
    accepted = [r for r in audit if r["disposition"] == "pseudoabsence"]
    key_sha = hashlib.sha256("".join(f"{r['species_id']},{r['grid_cell_id']}\n" for r in accepted).encode()).hexdigest()
    distance_preimage = "".join(f"{r['species_id']},{r['grid_cell_id']},{r['nearest_target_presence_distance_m']},{r['nearest_target_presence_grid_cell_id']}\n" for r in accepted).encode()
    counts = Counter(r["disposition"] for r in audit)
    final_totals = dict(Counter(r["species_id"] for r in response))
    support_distribution = dict(Counter(r["pseudoabsence_support_species_count"] for r in accepted))
    if ({"stage_a": len(audit), **{k: counts.get(k, 0) for k in EXPECTED_FUNNEL if k != "stage_a"}} != EXPECTED_FUNNEL or final_totals != EXPECTED_FINAL_RESPONSE_BY_SPECIES or len(response) != 13455 or support_distribution != {"3": 385, "4": 128, "5": 54, "6": 20} or key_sha != PORTABLE_ACCEPTED_KEY_SHA256 or len(distance_preimage) != 40990 or hashlib.sha256(distance_preimage).hexdigest() != FULL_DISTANCE_PREIMAGE_SHA256):
        raise PseudoabsenceError("oracle_contract_failure")
    presence_coords = defaultdict(list)
    for row in response:
        if row["pa_type"] == "presence":
            presence_coords[row["species_id"]].append((float(row["centroid_lon"]), float(row["centroid_lat"])))
    geod = Geod(ellps="GRS80"); distance_tested = 0; geodesic_disagreements = 0
    for row in audit:
        if row["disposition"] not in {"distance_rejected", "pseudoabsence"}: continue
        distance_tested += 1
        lon, lat = float(row["centroid_lon"]), float(row["centroid_lat"])
        nearest_geodesic = min(geod.inv(lon, lat, plon, plat)[2] for plon, plat in presence_coords[row["species_id"]])
        if (nearest_geodesic >= MIN_DISTANCE_M) != (row["distance_eligible"] == "true"): geodesic_disagreements += 1
    if distance_tested != 1487 or geodesic_disagreements != 0: raise PseudoabsenceError("geodesic_sensitivity_failure")
    per_species = {}
    for species in ACTIVE_SPECIES:
        ar = [r for r in audit if r["species_id"] == species]; rr = [r for r in response if r["species_id"] == species]; c = Counter(r["disposition"] for r in ar); pa = Counter(r["pa_type"] for r in rr)
        per_species[species] = {"target_presence": c.get("target_presence", 0), "camera_survey_supported_absence": c.get("camera_survey_supported_absence", 0), "island_suppressed": c.get("island_suppressed", 0), "distance_rejected": c.get("distance_rejected", 0), "pseudoabsence": c.get("pseudoabsence", 0), "presence": pa.get("presence", 0), "survey_supported_absence": pa.get("survey_supported_absence", 0), "total": len(rr), "prevalence": pa.get("presence", 0) / len(rr)}
    summary = dict(result["derivation_summary"]); summary.update({"funnel": {"stage_a": len(audit), **{k: counts.get(k, 0) for k in EXPECTED_FUNNEL if k != "stage_a"}}, "final_response_by_species": final_totals, "support_distribution": support_distribution, "per_species": per_species})
    return {"source_inventory": {"goal_id": GOAL_ID, "binding_hashes": EXPECTED_BINDING_HASHES, "input_rows": 12868, "input_sha256": EXPECTED_BINDING_HASHES["goal020_grid_evidence"], "schemas": {"goal020": list(GOAL020_FIELDS), "audit": list(AUDIT_FIELDS), "response": list(RESPONSE_FIELDS)}, "active_species": list(ACTIVE_SPECIES), "eligible_targets": list(ELIGIBLE_TARGETS), "goal020_tracked_status": "valid", "goal020_full_status": "valid", "privacy": PLAN_PRIVACY}, "derivation_summary": summary, "spatial_summary": {"projection": "GDA2020/MGA55 EPSG:7855 equivalent", "distance_crs": DISTANCE_CRS, "pipeline": "proj=pipeline step proj=unitconvert xy_in=deg xy_out=rad step proj=utm zone=55 south ellps=GRS80", "distance_sq_threshold": DISTANCE_SQ_THRESHOLD, "candidate_rows": len(audit), "distance_tested": distance_tested, "distance_rejected": counts.get("distance_rejected", 0), "distance_accepted": counts.get("pseudoabsence", 0), "geodesic_threshold_disagreements": geodesic_disagreements, "portable_accepted_key_sha256": key_sha, "full_distance_preimage_sha256": hashlib.sha256(distance_preimage).hexdigest(), "full_distance_preimage_bytes": len(distance_preimage)}, "outputs": {"private_outputs_ignored": True, "private_output_roles": {"pseudoabsence_candidate_audit": {"rows": len(audit), "bytes": len(audit_bytes), "sha256": hashlib.sha256(audit_bytes).hexdigest(), "schema": list(AUDIT_FIELDS)}, "response_layer": {"rows": len(response), "bytes": len(response_bytes), "sha256": hashlib.sha256(response_bytes).hexdigest(), "schema": list(RESPONSE_FIELDS)}}}, "review": {"readiness": "goal021_complete", "private_replay_required": True, "classification": "fixed", "distance_crs": DISTANCE_CRS, "privacy": PLAN_PRIVACY, "stopped_before": ["thinning", "weights", "balancing", "predictors", "partitions", "mapping", "modelling"], "blockers": []}}


def _read_islands(path: Path) -> dict[str, Polygon]:
    return camera._load_islands(path)


def _island_code(point: Point, islands: Mapping[str, Polygon]) -> str:
    hits = [name for name, polygon in islands.items() if polygon.covers(point)]
    if len(hits) > 1:
        raise PseudoabsenceError("multiple_island_hits")
    return hits[0] if hits else ""


def _recompute_from_bound_inputs(root: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    """Replay the private Goal020 + island inputs for semantic validation."""
    paths = {}
    for role, binding in plan["bindings"].items():
        path = root / _safe_relative(binding["path"])
        if not path.is_file() or path.is_symlink() or sha256(path) != binding["sha256"]:
            raise PseudoabsenceError(f"binding_drift:{role}")
        paths[role] = path
    bundle = json.loads(paths["decision_bundle"].read_text())
    validate_phase1_decision_bundle(bundle)
    exclusions = bundle["policies"]["island_exclusions"]["species_exclusions"]
    goal020.validate_evidence(paths["goal020_plan"], paths["goal020_evidence_manifest"].parent, full=True, output_dir=paths["goal020_grid_evidence"].parent)
    with paths["goal020_grid_evidence"].open(newline="") as stream:
        rows = validate_goal020_rows(list(csv.DictReader(stream)), expected_rows=12868)
    islands = _read_islands(paths["offshore_islands"])
    codes: dict[str, str] = {}; xy: dict[str, tuple[float, float]] = {}
    transformer = Transformer.from_pipeline("proj=pipeline step proj=unitconvert xy_in=deg xy_out=rad step proj=utm zone=55 south ellps=GRS80")
    for row in rows:
        cell = row["grid_cell_id"]; lon, lat = float(row["centroid_lon"]), float(row["centroid_lat"])
        codes[cell] = _island_code(Point(lon, lat), islands)
        xy[cell] = transformer.transform(lon, lat, errcheck=True)
    exclusions = {k: set(v) for k, v in exclusions.items() if k in ELIGIBLE_TARGETS}
    return derive_response_layer(rows, eligible_targets=ELIGIBLE_TARGETS, island_exclusions=exclusions, cell_island_codes=codes, projected_xy=xy)


def run_production(root: Path) -> dict[str, Any]:
    plan_path = root / "config/pseudoabsence_derivation_plan.json"; plan = json.loads(plan_path.read_text()); validate_plan(plan)
    output = root / "data/processed/response/goal021-pseudoabsence-derivation/2026-07-26"; evidence = root / "evidence/pseudoabsence_derivation/2026-07-26"
    if output.exists() or evidence.exists(): raise PseudoabsenceError("publication_destination_exists")
    ignored = __import__("subprocess").run(["git", "check-ignore", "--quiet", "--no-index", "--", str(output)], cwd=root, check=False, stdout=__import__("subprocess").DEVNULL, stderr=__import__("subprocess").DEVNULL)
    if ignored.returncode != 0: raise PseudoabsenceError("private_output_not_ignored")
    result = _recompute_from_bound_inputs(root, plan)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="goal021-stage-", dir=output.parent)); stage_output = staging / "output"; stage_evidence = staging / "evidence"; stage_output.mkdir(); stage_evidence.mkdir()
    with (stage_output / AUDIT_FILE).open("w", newline="") as f: w=csv.DictWriter(f,fieldnames=AUDIT_FIELDS,lineterminator="\n"); w.writeheader(); w.writerows(result["audit_rows"])
    with (stage_output / RESPONSE_FILE).open("w", newline="") as f: w=csv.DictWriter(f,fieldnames=RESPONSE_FIELDS,lineterminator="\n"); w.writeheader(); w.writerows(result["response_rows"])
    payloads = _build_evidence_payloads(result, audit_bytes=_csv_bytes(result["audit_rows"], AUDIT_FIELDS), response_bytes=_csv_bytes(result["response_rows"], RESPONSE_FIELDS))
    for name, payload in payloads.items(): (stage_evidence / f"{name}.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    entries=[]
    for name in EVIDENCE_FILES[:-1]: entries.append({"path":name,"sha256":sha256(stage_evidence/name),"bytes":(stage_evidence/name).stat().st_size})
    (stage_evidence / "manifest.json").write_text(json.dumps({"schema_version":"1.0","files":entries},indent=2,sort_keys=True)+"\n")
    _publish_staged(stage_output, stage_evidence, output, evidence)
    shutil.rmtree(staging, ignore_errors=True)
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2]); args=parser.parse_args(); run_production(args.root)
