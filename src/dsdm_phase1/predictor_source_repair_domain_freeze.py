"""Goal024 deterministic predictor source-recovery audit and domain freeze.

This module deliberately stops at a supported structural domain.  It never
fills, substitutes, transforms, encodes, partitions, maps, or models values.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

DATE = "2026-07-26"
GOAL_ID = "goal024-predictor-source-repair-domain-freeze-2026-07-26"
ACTIVE = ("annmeantemp","meandiurnrange","isothermality","tempseason","maxtempwarmmonth","mintempcoldmonth","tempannrange","meantempwetq","meantempdryq","meantempwarmq","meantempcoldq","annprecip","precipwetmonth","precipdrymonth","precipseason","precipwetq","precipdryq","precipwarmq","precipcoldq","elevation","top_roughness","soil_class","dist_fw","dist_road","fpar","veg_mvg","landuse_secondary","human_footprint")
CATEGORICAL = ("soil_class", "veg_mvg", "landuse_secondary")
SPECIES = ("dasyurus_maculatus","dasyurus_viverrinus","notamacropus_rufogriseus","pseudocheirus_peregrinus","sarcophilus_harrisii","thylogale_billardierii","trichosurus_vulpecula","vombatus_ursinus")
PA_TYPES = ("presence", "pseudoabsence", "survey_supported_absence")
RESPONSE_ORIGINS = ("derived_pseudoabsence", "goal020")
SOURCE_COMBINATIONS = ("", "ala_only_presence", "ala_overrides_camera_absence", "both_presence", "camera_absence_retained", "camera_only_presence")
MAP_ROWS, MAP_INCLUDED, MAP_EXCLUDED = 74073, 71023, 3050
RESP_CELLS, RESP_CELL_INCLUDED, RESP_CELL_EXCLUDED = 5407, 5087, 320
RESP_ROWS, RESP_INCLUDED, RESP_EXCLUDED = 13455, 12711, 744
PRIVACY = {"tracked_grid_ids_or_coordinates": False, "tracked_row_payloads": False, "tracked_private_paths": False, "tracked_response_identifiers": False, "tracked_site_or_camera_ids": False, "tracked_private_observation_timing": False}
MAP_SCHEMA = list(("grid_cell_id", "centroid_lon", "centroid_lat") + ACTIVE + ("predictor_complete", "missing_predictor_count", "missing_predictor_ids"))
RESPONSE_SCHEMA = ["species_id", "grid_cell_id", "centroid_lon", "centroid_lat", "pa", "pa_type", "survey_supported_absence_rule_id", "source_combination", "cross_source_conflict", "ala_presence", "ala_source_row_count", "ala_unique_provider_record_count", "ala_resource_count", "ala_dataset_count", "ala_unknown_uncERTAINTY_count", "ala_qa_flag_count", "ala_low_cell_certainty_only", "camera_evidence", "camera_pa", "camera_pa_type", "camera_survey_supported_absence_rule_id", "camera_site_count", "camera_presence_site_count", "camera_survey_supported_absence_site_count", "camera_positive_source_row_count", "camera_internal_conflict", "response_origin", "pseudoabsence_rule_id", "pseudoabsence_support_species_count", "pseudoabsence_support_species_ids", "nearest_target_presence_grid_cell_id", "nearest_target_presence_source_combination", "nearest_target_presence_distance_m", "distance_crs"]
RESPONSE_SCHEMA[14] = "ala_unknown_uncertainty_count"
AUDIT_CELL_SCHEMA = ["grid_cell_id", "included", "status", "original_missing_predictor_count", "original_missing_predictor_ids", "repair_status", "reason"]
AUDIT_RESP_SCHEMA = ["species_id", "grid_cell_id", "pa", "pa_type", "response_origin", "source_combination", "included", "status", "reason"]
PRIVATE_NAMES = ("predictor_cell_map_canonical.csv", "predictor_response_cells_canonical.csv", "response_layer_canonical.csv", "cell_domain_audit.csv", "response_domain_audit.csv")
LEGACY_AMBIGUOUS = ("elevation","soil_class","dist_fw","fpar","veg_mvg","landuse_secondary","annmeantemp","meandiurnrange","isothermality","tempseason","maxtempwarmmonth","mintempcoldmonth","tempannrange","meantempwetq","meantempdryq","meantempwarmq","meantempcoldq","annprecip","precipwetmonth","precipdrymonth","precipseason","precipwetq","precipdryq","precipwarmq","precipcoldq")
UNAVAILABLE = ("top_roughness", "dist_road")
EVIDENCE_FILES = ("source_inventory.json","source_comparison.json","domain_summary.json","response_impact.json","support_contract.json","outputs.json","review.json")
EXPECTED_TOP_KEYS = {
    "source_inventory": {"goal_id","repair_status","bindings","immutable_upstream","local_candidate_inventory","official_sources","privacy"},
    "source_comparison": {"repair_status","predictors","repaired_values","candidate_values_used","source_facts_status"},
    "domain_summary": {"rule","predictors_retained","map_cells","response_cells","response_rows","repairs","missingness_reconciliation"},
    "response_impact": {"rows","included","excluded","by_species","by_pa_type","by_response_origin","by_source_combination","species_x_pa_type","species_x_source_combination","pa_type_x_source_combination","survey_supported_absences"},
    "support_contract": {"primary_structural_domain","conditional_scope_of_inference","operational_estimand","domain_policy","goal023_diagnostics","later_recompute","future_repair","pseudoabsence_post_domain","stopped_before"},
    "outputs": {"private_outputs_ignored","roles"},
    "review": {"goal_id","repair_status","decision","zero_repairs","all_28_predictors_retained","conditional_inference_statement","operational_estimand","domain_policy","pseudoabsence_post_domain_status","barry_decisions_pending","stop_boundary","future_source_package","privacy"},
}

class PredictorDomainError(ValueError):
    pass

EXPECTED_BINDINGS = {
    "decision_bundle": ("config/phase1_decision_bundle.json", "ccccbb2e56e101b1a53421f8016699bfb500f4356861e10c1213a398aabe04a2"),
    "goal021_plan": ("config/pseudoabsence_derivation_plan.json", "75cdc198815d3076af6ee3b6f25bed5ea4e90bf1433c7e9205f8692dfedd95fe"),
    "goal021_manifest": ("evidence/pseudoabsence_derivation/2026-07-26/manifest.json", "bf843690a6071f489b81fb5bdc348bab1c9f2001dfa37ad359ed7dc75d50f875"),
    "goal021_outputs": ("evidence/pseudoabsence_derivation/2026-07-26/outputs.json", "ecf0e6f46b3eec30c4edeff26d02f694be18cbc063268d9e1780f8cca7b5a3d9"),
    "goal021_response": ("data/processed/response/goal021-pseudoabsence-derivation/2026-07-26/response_layer.csv", "e67298d11d7eb29e6bf8ca055cd8b64cfaf119d193ff0675fff09719ce0616a3"),
    "goal022_plan": ("config/predictor_stack_extraction_plan.json", "e75af21cf553cd5a10e375a9f3f29ebfc7b574a8684b8f82f830c111c0c34c65"),
    "goal022_manifest": ("evidence/predictor_stack_extraction/2026-07-26/manifest.json", "d0c72e0b0fc614813438ae6d554b4522ae65305daf63543aa8b9774b7e891c60"),
    "goal022_outputs": ("evidence/predictor_stack_extraction/2026-07-26/outputs.json", "72bc6b81a25016fc8ba2bdae677d4f0c35021ce33ba0dfaac3aa4f2fe4c08ff5"),
    "predictor_map_csv": ("data/processed/predictors/goal022-predictor-stack-extraction/2026-07-26/predictor_cell_map_raw.csv", "0e2082671096bbf80745038bad8329d3bb4fd58dc20b8a4adb146c3d62459542"),
    "predictor_response_csv": ("data/processed/predictors/goal022-predictor-stack-extraction/2026-07-26/predictor_response_cells_raw.csv", "4438d383c6f63e38b0bf61bcbb3812df4e3a26b9e2185d718d2fc03817bbb92f"),
    "goal023_plan": ("config/predictor_support_diagnostic_plan.json", "b877303de6bcb3292adca93f629897a4542585dd4a9ecc580b75a1726f611e6a"),
    "goal023_manifest": ("evidence/predictor_support_diagnostics/2026-07-26/manifest.json", "410e442ac462f0b0f56ed1a1009772e145be3045718a251cd1fb257d1391a0c6"),
    "goal023_decision": ("docs/goals/023-predictor-support-map-domain/Decision.md", "f2b831f7334243d9ea89ed90cf979798055727b3092b0360f8ea9b94f2fd3b08"),
    "legacy_script": ("temp/src/3_create_sdm_data.R", "cff353c830fe78e351fc72f2672dd1c73e94930ebf4516b53c5950ec19a4effe"),
    "workbook": ("temp/data/spatial/se_stack_metadata.xlsx", "ec460f9a41913f3288ca7dd38b6150b575f9c00b73581b892468cd0577127edd"),
    "hfp_stack_band": ("temp/data/spatial/tas_stack.tif", "e3dd4175688572d9c8afcfb521a5e1083a0f25ba90d4841938a93aa5d6f72088"),
    "hfp_candidate": ("temp/data/spatial/human_footprint_tas.tif", "b90197ee093025e79d57aad3e24cfa0d600de5b9ee1d2cd1dce6dfd24dbac469"),
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def _safe_relative(value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise PredictorDomainError("unsafe_binding_path")
    return Path(value)

def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.is_symlink():
        raise PredictorDomainError(f"missing_or_symlink:{path.name}")
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))

def _write_csv(path: Path, rows: list[Mapping[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader(); writer.writerows({f: row.get(f, "") for f in fields} for row in rows)

def _csv_bytes(rows: list[Mapping[str, Any]], fields: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader(); writer.writerows({f: row.get(f, "") for f in fields} for row in rows)
    return stream.getvalue().encode()

def _private_expected(computed: Mapping[str, Any]) -> dict[str, bytes]:
    d = computed["domain"]
    return {
        PRIVATE_NAMES[0]: _csv_bytes(d["map_in"], MAP_SCHEMA),
        PRIVATE_NAMES[1]: _csv_bytes(d["cell_in"], MAP_SCHEMA),
        PRIVATE_NAMES[2]: _csv_bytes(d["response_in"], RESPONSE_SCHEMA),
        PRIVATE_NAMES[3]: _csv_bytes(computed["cell_audit"], AUDIT_CELL_SCHEMA),
        PRIVATE_NAMES[4]: _csv_bytes(computed["response_audit"], AUDIT_RESP_SCHEMA),
    }

def _private_metadata(directory: Path, expected: Mapping[str, bytes]) -> dict[str, Any]:
    if not directory.is_dir() or directory.is_symlink(): raise PredictorDomainError("private_output_directory_drift")
    entries = list(directory.iterdir())
    if {p.name for p in entries} != set(PRIVATE_NAMES) or any(not p.is_file() or p.is_symlink() for p in entries): raise PredictorDomainError("private_output_footprint_drift")
    roles = {}
    schemas = {PRIVATE_NAMES[0]: MAP_SCHEMA, PRIVATE_NAMES[1]: MAP_SCHEMA, PRIVATE_NAMES[2]: RESPONSE_SCHEMA, PRIVATE_NAMES[3]: AUDIT_CELL_SCHEMA, PRIVATE_NAMES[4]: AUDIT_RESP_SCHEMA}
    for name in PRIVATE_NAMES:
        path = directory / name
        actual = path.read_bytes()
        if actual != expected[name]: raise PredictorDomainError(f"private_output_byte_drift:{name}")
        rows = list(csv.DictReader(io.StringIO(actual.decode())))
        roles[name] = {"rows": len(rows), "schema": schemas[name], "bytes": len(actual), "sha256": hashlib.sha256(actual).hexdigest()}
    return {"private_outputs_ignored": True, "roles": roles}

def _bindings(root: Path, plan: Mapping[str, Any]) -> dict[str, Path]:
    out = {}
    for role, spec in plan.get("bindings", {}).items():
        p = root / _safe_relative(spec.get("path"))
        if not p.is_file() or p.is_symlink() or sha256(p) != spec.get("sha256"):
            raise PredictorDomainError(f"binding_drift:{role}")
        out[role] = p
    return out

def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema_version") != "1.0" or plan.get("goal_id") != GOAL_ID:
        raise PredictorDomainError("plan_identity_drift")
    if tuple(plan.get("active_predictors", ())) != ACTIVE or tuple(plan.get("categorical_predictors", ())) != CATEGORICAL:
        raise PredictorDomainError("predictor_contract_drift")
    if plan.get("privacy") != PRIVACY or plan.get("repair_status") != "repair_not_authorized":
        raise PredictorDomainError("repair_or_privacy_contract_drift")
    bindings = {k: (v.get("path"), v.get("sha256")) for k, v in plan.get("bindings", {}).items()}
    if bindings != EXPECTED_BINDINGS:
        raise PredictorDomainError("plan_binding_drift")
    if plan.get("expected_counts") != {"map_cells": [MAP_ROWS, MAP_INCLUDED, MAP_EXCLUDED], "response_cells": [RESP_CELLS, RESP_CELL_INCLUDED, RESP_CELL_EXCLUDED], "response_rows": [RESP_ROWS, RESP_INCLUDED, RESP_EXCLUDED], "survey_absences": [2160, 2114, 46]}:
        raise PredictorDomainError("count_oracle_drift")
    if plan.get("stopped_before") != ["partitions", "fitted_transformations", "imputation", "encoding", "scaling", "mapping", "modelling"]:
        raise PredictorDomainError("stop_contract_drift")
    if plan.get("outputs") != {"private_destination": "data/processed/predictors/goal024-predictor-source-repair-domain-freeze/2026-07-26", "evidence_destination": "evidence/predictor_source_repair_domain_freeze/2026-07-26", "private_outputs_ignored": True}:
        raise PredictorDomainError("output_contract_drift")
    return {"goal_id": GOAL_ID, "predictor_count": len(ACTIVE)}

def _load_inputs(root: Path, plan: Mapping[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    paths = _bindings(root, plan)
    maps = _read_csv(paths["predictor_map_csv"]); cells = _read_csv(paths["predictor_response_csv"]); response = _read_csv(paths["goal021_response"])
    if len(maps) != MAP_ROWS or len(cells) != RESP_CELLS or len(response) != RESP_ROWS: raise PredictorDomainError("source_row_count_drift")
    if list(maps[0]) != MAP_SCHEMA or list(cells[0]) != MAP_SCHEMA or list(response[0]) != RESPONSE_SCHEMA: raise PredictorDomainError("source_schema_drift")
    if len({r.get("grid_cell_id") for r in maps}) != MAP_ROWS or len({r.get("grid_cell_id") for r in cells}) != RESP_CELLS: raise PredictorDomainError("duplicate_cell_key")
    if len({(r.get("species_id"), r.get("grid_cell_id")) for r in response}) != RESP_ROWS: raise PredictorDomainError("response_grain_drift")
    return maps, cells, response

def _domain_rows(maps: list[dict[str, str]], response_cells: list[dict[str, str]], response: list[dict[str, str]]) -> dict[str, Any]:
    complete = {r["grid_cell_id"] for r in maps if r.get("predictor_complete") == "true" and all(r.get(p, "") != "" for p in ACTIVE)}
    if len(maps) == MAP_ROWS and len(complete) != MAP_INCLUDED: raise PredictorDomainError("domain_inclusion_oracle")
    bykey = {r["grid_cell_id"]: r for r in maps}
    cell_bykey = {r["grid_cell_id"]: r for r in response_cells}
    if not set(cell_bykey).issubset(set(bykey)): raise PredictorDomainError("response_cell_key_drift")
    response_in = [r for r in response if r.get("grid_cell_id") in complete]
    response_cell_in = [r for r in response_cells if r.get("grid_cell_id") in complete]
    if len(response_cells) == RESP_CELLS and (len(response_cell_in) != RESP_CELL_INCLUDED or len(response_in) != RESP_INCLUDED): raise PredictorDomainError("response_domain_oracle")
    if any(any(r.get(p, "") == "" for p in ACTIVE) for r in maps if r["grid_cell_id"] in complete): raise PredictorDomainError("included_missing_value")
    if any(any(r.get(p, "") == "" for p in ACTIVE) for r in response_cell_in): raise PredictorDomainError("included_response_missing_value")
    return {"complete_keys": complete, "bykey": bykey, "cell_bykey": cell_bykey, "map_in": [r for r in maps if r["grid_cell_id"] in complete], "cell_in": response_cell_in, "response_in": response_in}

def _audit(maps: list[dict[str, str]], response: list[dict[str, str]], complete: set[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    cells=[]
    for r in maps:
        missing = [p for p in ACTIVE if r.get(p, "") == ""]
        included = r["grid_cell_id"] in complete
        cells.append({"grid_cell_id":r["grid_cell_id"],"included":"true" if included else "false","status":"included" if included else "excluded","original_missing_predictor_count":str(len(missing)),"original_missing_predictor_ids":"|".join(missing),"repair_status":"not_authorized","reason":"all_28_predictors_observed" if included else "one_or_more_predictors_missing;repair_not_authorized"})
    rows=[]
    for r in response:
        included = r.get("grid_cell_id") in complete
        rows.append({"species_id":r.get("species_id",""),"grid_cell_id":r.get("grid_cell_id",""),"pa":r.get("pa",""),"pa_type":r.get("pa_type",""),"response_origin":r.get("response_origin",""),"source_combination":r.get("source_combination",""),"included":"true" if included else "false","status":"included" if included else "excluded","reason":"cell_in_supported_structural_domain" if included else "cell_outside_supported_structural_domain"})
    return cells, rows

def _response_impact(response: list[dict[str, str]], complete: set[str]) -> dict[str, Any]:
    def breakdown(field: str) -> dict[str, dict[str, int]]:
        out={}
        for value in sorted({r.get(field, "") for r in response}):
            rows=[r for r in response if r.get(field, "") == value]
            out[value]={"rows":len(rows),"included":sum(r.get("grid_cell_id") in complete for r in rows),"excluded":sum(r.get("grid_cell_id") not in complete for r in rows)}
        return out
    def cross(a: str, b: str) -> dict[str, dict[str, int]]:
        out={}
        for x in sorted({r.get(a, "") for r in response}):
            for y in sorted({r.get(b, "") for r in response}):
                rows=[r for r in response if r.get(a, "")==x and r.get(b, "")==y]
                if rows: out[f"{x}|{y}"]={"rows":len(rows),"included":sum(r.get("grid_cell_id") in complete for r in rows),"excluded":sum(r.get("grid_cell_id") not in complete for r in rows)}
        return out
    return {"rows":len(response),"included":sum(r.get("grid_cell_id") in complete for r in response),"excluded":sum(r.get("grid_cell_id") not in complete for r in response),"by_species":breakdown("species_id"),"by_pa_type":breakdown("pa_type"),"by_response_origin":breakdown("response_origin"),"by_source_combination":breakdown("source_combination"),"species_x_pa_type":cross("species_id","pa_type"),"species_x_source_combination":cross("species_id","source_combination"),"pa_type_x_source_combination":cross("pa_type","source_combination"),"survey_supported_absences":{"rows":sum(r.get("pa_type")=="survey_supported_absence" for r in response),"included":sum(r.get("pa_type")=="survey_supported_absence" and r.get("grid_cell_id") in complete for r in response),"excluded":sum(r.get("pa_type")=="survey_supported_absence" and r.get("grid_cell_id") not in complete for r in response)}}

def _source_comparison(maps: list[dict[str, str]], cells: list[dict[str, str]] | None = None, response: list[dict[str, str]] | None = None) -> dict[str, Any]:
    missing={p:sum(r.get(p, "")=="" for r in maps) for p in ACTIVE}
    cell_missing={p:sum(r.get(p, "")=="" for r in (cells or [])) for p in ACTIVE}
    bykey={r["grid_cell_id"]:r for r in maps}
    row_missing={p:sum(bykey[r["grid_cell_id"]].get(p, "")=="" for r in (response or [])) for p in ACTIVE}
    classifications={"human_footprint":{"classification":"exact_local_duplicate_no_recovery","missing_cells":missing["human_footprint"],"candidate":"temp/data/spatial/human_footprint_tas.tif","candidate_recovered_values":0,"reason":"candidate exactly reproduces stack band 32 array and mask on the shared extent; files are not whole-file identical"}}
    for p in ("elevation","soil_class","dist_fw","fpar","veg_mvg","landuse_secondary","annmeantemp","meandiurnrange","isothermality","tempseason","maxtempwarmmonth","mintempcoldmonth","tempannrange","meantempwetq","meantempdryq","meantempwarmq","meantempcoldq","annprecip","precipwetmonth","precipdrymonth","precipseason","precipwetq","precipdryq","precipwarmq","precipcoldq"):
        classifications[p]={"classification":"legacy_lineage_ambiguous","missing_cells":missing[p],"candidate_recovered_values":0,"reason":"legacy lineage/build and native source identity are not proved"}
    for p in ("top_roughness","dist_road"):
        classifications[p]={"classification":"unavailable","missing_cells":missing[p],"candidate_recovered_values":0,"reason":"targeted constituent raster absent"}
    for p, value in classifications.items():
        value["missing_response_cells"] = cell_missing[p]
        value["missing_response_rows"] = row_missing[p]
    return {"repair_status":"repair_not_authorized","predictors":classifications,"repaired_values":0,"candidate_values_used":0,"source_facts_status":"reference_only_for_official_urls_and_workbook_labels"}

def _hfp_oracle(root: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    """Verify the one local constituent is an exact duplicate on shared extent."""
    try:
        import numpy as np
        import rasterio
        paths = _bindings(root, plan)
        with rasterio.open(paths["hfp_stack_band"]) as stack, rasterio.open(paths["hfp_candidate"]) as candidate:
            a = stack.read(32); b = candidate.read(1)
            if a.shape[0] != b.shape[0] + 1 or a.shape[1] != b.shape[1]: raise PredictorDomainError("hfp_extent_drift")
            if stack.crs != candidate.crs or stack.crs.to_string() != "EPSG:4326" or stack.width != 468 or stack.height != 455 or candidate.width != 468 or candidate.height != 454: raise PredictorDomainError("hfp_metadata_drift")
            if stack.dtypes[31] != "float32" or candidate.dtypes[0] != "float32" or stack.nodata != candidate.nodata: raise PredictorDomainError("hfp_nodata_dtype_drift")
            if abs(stack.transform.a - candidate.transform.a) > 1e-12 or abs(stack.transform.e - candidate.transform.e) > 1e-12 or abs(stack.transform.c - candidate.transform.c) > 1e-8 or abs(candidate.transform.f - (stack.transform.f + stack.transform.e)) > 1e-8: raise PredictorDomainError("hfp_alignment_drift")
            shared = a[1:, :]
            same = bool(np.array_equal(shared, b, equal_nan=True))
            missing = int(np.sum((shared <= -3.0e38) | ~np.isfinite(shared)))
            candidate_missing = int(np.sum((b <= -3.0e38) | ~np.isfinite(b)))
            if not same or missing != candidate_missing: raise PredictorDomainError("hfp_duplicate_oracle_failure")
            return {"stack_metadata": {"crs": stack.crs.to_string(), "width": stack.width, "height": stack.height, "dtype": stack.dtypes[31], "nodata": stack.nodata, "transform": [stack.transform.a, stack.transform.b, stack.transform.c, stack.transform.d, stack.transform.e, stack.transform.f]}, "candidate_metadata": {"crs": candidate.crs.to_string(), "width": candidate.width, "height": candidate.height, "dtype": candidate.dtypes[0], "nodata": candidate.nodata, "transform": [candidate.transform.a, candidate.transform.b, candidate.transform.c, candidate.transform.d, candidate.transform.e, candidate.transform.f]}, "shared_shape": [int(b.shape[0]), int(b.shape[1])], "exact_array_duplicate": True, "shared_raster_nodata_pixels": missing, "canonical_missing_cells": 954, "candidate_recovered_values": 0}
    except ImportError:
        return {"verification": "deferred_runtime_rasterio", "candidate_recovered_values": 0}

def compute_outputs(root: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    maps, cells, response = _load_inputs(root, plan); d = _domain_rows(maps, cells, response); ca, ra = _audit(maps, response, d["complete_keys"])
    return {"maps":maps,"cells":cells,"response":response,"domain":d,"cell_audit":ca,"response_audit":ra}

def _pseudoabsence_post_domain(response: list[dict[str, str]], complete: set[str]) -> dict[str, Any]:
    pseudo = [r for r in response if r.get("pa_type") == "pseudoabsence"]
    retained = [r for r in pseudo if r.get("grid_cell_id") in complete]
    presence_links = {(r.get("species_id"), r.get("grid_cell_id")) for r in response if r.get("pa_type") == "presence"}
    support_count_bad = sum(int(r.get("pseudoabsence_support_species_count", "0")) < 3 for r in retained)
    support_distinct_bad = sum(len(set(filter(None, r.get("pseudoabsence_support_species_ids", "").split("|")))) < 3 for r in retained)
    distance_bad = sum(float(r.get("nearest_target_presence_distance_m", "0")) < 5000.0 for r in retained)
    broken_links = sum(any((species, r.get("grid_cell_id")) not in presence_links for species in filter(None, r.get("pseudoabsence_support_species_ids", "").split("|"))) for r in retained)
    support_outside = sum(any(r.get("grid_cell_id") not in complete for _ in filter(None, r.get("pseudoabsence_support_species_ids", "").split("|"))) for r in retained)
    return {"before_rows": len(pseudo), "retained_rows": len(retained), "excluded_rows": len(pseudo) - len(retained), "retained_support_count_below_3": support_count_bad, "retained_support_species_distinct_below_3": support_distinct_bad, "retained_distance_below_5000_m": distance_bad, "retained_broken_same_cell_support_presence_links": broken_links, "retained_support_presence_outside_d_struct": support_outside, "rederivation_required": False, "preservation_rationale": "Goal024 filtering is cell/predictor-only and preserves the >=3 same-cell support rule, the conservative >=5 km test against the full frozen presence set, provenance/precedence, and the absence of a quota/balancing/thinning contract", "goal021_contract": {"quota_contract": False, "stops_before_balancing_thinning": True}, "goal025_deferred": "per-species and fold-level adequacy is deferred to Goal025"}

def compute_evidence(root: Path, plan: Mapping[str, Any], computed: Mapping[str, Any]) -> dict[str, Any]:
    maps, cells, response = computed["maps"], computed["cells"], computed["response"]; d=computed["domain"]; bind=_bindings(root,plan)
    source_inventory={"goal_id":GOAL_ID,"repair_status":"repair_not_authorized","bindings":{k:{"path":str(v.relative_to(root)),"sha256":sha256(v)} for k,v in bind.items()},"immutable_upstream":True,"local_candidate_inventory":{"human_footprint_tas.tif":{"status":"present_exact_shared_extent_duplicate","sha256":sha256(bind["hfp_candidate"]),"oracle":_hfp_oracle(root,plan)}},"official_sources":{"status":"reference_only","retrieval_date":DATE,"lineage_caveat":"families and URLs do not prove exact stack lineage","urls":["https://www.asris.csiro.au/arcgis/rest/services/ASRIS/ASRIS_ASC_MOB/MapServer/0","https://www.ga.gov.au/scientific-topics/water/national-surface-water-information","https://support.ecocommons.org.au/support/solutions/articles/6000261884-current-historic-datasets-available-on-the-ecocommons-for-sdms","https://www.dcceew.gov.au/environment/environment-information-australia/national-vegetation-information-system/data-products","https://www.agriculture.gov.au/abares/aclump/land-use/land-use-of-australia-2010-11_2015-16"]},"privacy":PRIVACY}
    missing_patterns=Counter("|".join(p for p in ACTIVE if r.get(p, "")=="") or "complete" for r in maps)
    bykey = {r["grid_cell_id"]: r for r in maps}
    response_cell_missing = {p: sum(r.get(p, "") == "" for r in cells) for p in ACTIVE}
    response_row_missing = {p: sum(bykey[r["grid_cell_id"]].get(p, "") == "" for r in response) for p in ACTIVE}
    response_cell_patterns = Counter("|".join(p for p in ACTIVE if r.get(p, "")=="") or "complete" for r in cells)
    response_row_patterns = Counter("|".join(p for p in ACTIVE if bykey[r["grid_cell_id"]].get(p, "")=="") or "complete" for r in response)
    domain_summary={"rule":"D_struct = canonical cells with observed nonmissing values for all 28 predictors","predictors_retained":list(ACTIVE),"map_cells":{"total":len(maps),"included":len(d["map_in"]),"excluded":len(maps)-len(d["map_in"]),"missing_pattern_counts":dict(sorted(missing_patterns.items()))},"response_cells":{"total":len(cells),"included":len(d["cell_in"]),"excluded":len(cells)-len(d["cell_in"]),"missing_by_predictor":response_cell_missing,"missing_pattern_counts":dict(sorted(response_cell_patterns.items()))},"response_rows":{"total":len(response),"included":len(d["response_in"]),"excluded":len(response)-len(d["response_in"]),"missing_by_predictor":response_row_missing,"missing_pattern_counts":dict(sorted(response_row_patterns.items()))},"repairs":{"status":"not_authorized","values":0},"missingness_reconciliation":{"map_total":MAP_ROWS,"map_included_plus_excluded":MAP_INCLUDED+MAP_EXCLUDED,"response_cell_total":RESP_CELLS,"response_cell_included_plus_excluded":RESP_CELL_INCLUDED+RESP_CELL_EXCLUDED,"response_row_total":RESP_ROWS,"response_row_included_plus_excluded":RESP_INCLUDED+RESP_EXCLUDED}}
    pseudoabsence_post_domain = _pseudoabsence_post_domain(response, d["complete_keys"])
    support_contract={"primary_structural_domain":"D_struct","conditional_scope_of_inference":"inference is conditional on cells and response rows within D_struct","operational_estimand":"species-specific relative response score over canonical cells in D_struct, conditional on the accepted presence/survey-supported-absence/pseudoabsence construction; not detection-corrected occupancy, abundance, population prevalence, or inference outside D_struct","domain_policy":{"primary":"D_struct is the deliberate primary policy: high-coverage, provenance-safe, retaining all 28 predictors","sensitivity":"any future full-domain fold-fitted missing-treatment analysis is sensitivity only; excluded cells and rows remain audit/sensitivity material","not_uniquely_data_determined":"D_struct is a policy choice, not the uniquely data-determined consequence of the source audit"},"goal023_diagnostics":{"pooled_and_species_support":"descriptive prepartition evidence only","structural_filter":False,"pooled_envelope_cells":987,"pooled_unseen_category_cells":51},"later_recompute":{"categorical_novelty":"per species and training fold","continuous_support":"per species and training fold"},"future_repair":"requires a new versioned goal","pseudoabsence_post_domain":pseudoabsence_post_domain,"stopped_before":["partitions","fitted_transformations","imputation","encoding","scaling","mapping","modelling"]}
    outputs={}
    return {"source_inventory":source_inventory,"source_comparison":_source_comparison(maps,cells,response),"domain_summary":domain_summary,"response_impact":_response_impact(response,d["complete_keys"]),"support_contract":support_contract,"outputs":outputs,"review":{"goal_id":GOAL_ID,"repair_status":"repair_not_authorized","decision":"supported_structural_domain_frozen","zero_repairs":True,"all_28_predictors_retained":True,"conditional_inference_statement":True,"operational_estimand":"species-specific relative response score over canonical cells in D_struct, conditional on the accepted presence/survey-supported-absence/pseudoabsence construction; not detection-corrected occupancy, abundance, population prevalence, or inference outside D_struct","domain_policy":"D_struct is the deliberate primary policy choice: high-coverage, provenance-safe, retaining all 28 predictors; it is not uniquely data-determined by the source audit","pseudoabsence_post_domain_status":"validated; rederivation not required; Goal025 defers per-species/fold adequacy","barry_decisions_pending":[],"stop_boundary":"before partitions, transformations, imputation, encoding, scaling, mapping, modelling","future_source_package":"opens a new goal","privacy":PRIVACY}}

def _evidence_privacy(value: Any) -> None:
    forbidden=("grid_cell_id","coordinate","row_payload","response_id","site_id","camera_id","private_path","observation_timing")
    coordinate_keys={"centroid_lon","centroid_lat","longitude","latitude","lon","lat"}
    def walk(x: Any, path: tuple[Any, ...] = ()):
        if isinstance(x, Mapping):
            for k,v in x.items():
                kl=str(k).lower()
                schema_metadata = "roles" in path and "schema" in path
                if not schema_metadata and (kl in coordinate_keys or "location" in kl or any(t in kl for t in forbidden)) and not kl.startswith("tracked_"): raise PredictorDomainError("tracked_evidence_privacy_failure")
                walk(v, path + (k,))
        elif isinstance(x,list):
            for i,v in enumerate(x): walk(v, path + (i,))
        elif isinstance(x, str):
            if os.path.isabs(x) or x.startswith("/Users/") or re.fullmatch(r"g_-?\d+_-?\d+",x): raise PredictorDomainError("tracked_evidence_privacy_failure")
    walk(value)

def _manifest(directory: Path) -> dict[str, Any]:
    files=[{"path":n,"bytes":(directory/n).stat().st_size,"sha256":sha256(directory/n)} for n in EVIDENCE_FILES]
    return {"schema_version":"1.0","files":files}

def _validate_semantics(payloads: Mapping[str, Any]) -> None:
    if set(payloads) != {n[:-5] for n in EVIDENCE_FILES}: raise PredictorDomainError("tracked_payload_key_drift")
    for name, keys in EXPECTED_TOP_KEYS.items():
        if not isinstance(payloads.get(name), Mapping) or set(payloads[name]) != keys: raise PredictorDomainError(f"{name}_schema_drift")
    s=payloads["source_inventory"]
    if s.get("goal_id") != GOAL_ID or s.get("repair_status") != "repair_not_authorized" or s.get("immutable_upstream") is not True or s.get("privacy") != PRIVACY or set(s.get("privacy", {})) != set(PRIVACY): raise PredictorDomainError("source_inventory_semantic_drift")
    bindings = s.get("bindings", {})
    if set(bindings) != set(EXPECTED_BINDINGS): raise PredictorDomainError("source_binding_role_drift")
    for role, record in bindings.items():
        if not isinstance(record, Mapping) or set(record) != {"path","sha256"} or record.get("path") != EXPECTED_BINDINGS[role][0] or record.get("sha256") != EXPECTED_BINDINGS[role][1]: raise PredictorDomainError("source_binding_semantic_drift")
    inv = s.get("local_candidate_inventory", {}).get("human_footprint_tas.tif", {})
    oracle = inv.get("oracle", {})
    if set(s.get("local_candidate_inventory", {})) != {"human_footprint_tas.tif"} or set(inv) != {"status","sha256","oracle"} or set(oracle) != {"stack_metadata","candidate_metadata","shared_shape","exact_array_duplicate","shared_raster_nodata_pixels","canonical_missing_cells","candidate_recovered_values"}: raise PredictorDomainError("hfp_inventory_schema_drift")
    for metadata in (oracle.get("stack_metadata", {}), oracle.get("candidate_metadata", {})):
        if set(metadata) != {"crs","width","height","dtype","nodata","transform"}: raise PredictorDomainError("hfp_metadata_schema_drift")
    if inv.get("status") != "present_exact_shared_extent_duplicate" or inv.get("sha256") != EXPECTED_BINDINGS["hfp_candidate"][1] or oracle.get("exact_array_duplicate") is not True or oracle.get("candidate_recovered_values") != 0 or oracle.get("shared_raster_nodata_pixels") != 139281 or oracle.get("canonical_missing_cells") != 954: raise PredictorDomainError("hfp_inventory_semantic_drift")
    official=s.get("official_sources", {})
    if set(official) != {"status","retrieval_date","lineage_caveat","urls"} or official.get("status") != "reference_only" or official.get("lineage_caveat") != "families and URLs do not prove exact stack lineage" or official.get("urls") != ["https://www.asris.csiro.au/arcgis/rest/services/ASRIS/ASRIS_ASC_MOB/MapServer/0","https://www.ga.gov.au/scientific-topics/water/national-surface-water-information","https://support.ecocommons.org.au/support/solutions/articles/6000261884-current-historic-datasets-available-on-the-ecocommons-for-sdms","https://www.dcceew.gov.au/environment/environment-information-australia/national-vegetation-information-system/data-products","https://www.agriculture.gov.au/abares/aclump/land-use/land-use-of-australia-2010-11_2015-16"]: raise PredictorDomainError("official_source_semantic_drift")
    comp=payloads["source_comparison"]
    predictors=comp.get("predictors", {})
    if comp.get("repair_status") != "repair_not_authorized" or set(predictors) != set(ACTIVE) or comp.get("repaired_values") != 0 or comp.get("candidate_values_used") != 0: raise PredictorDomainError("source_comparison_semantic_drift")
    expected_predictor_keys={"classification","missing_cells","missing_response_cells","missing_response_rows","candidate_recovered_values","reason"}
    if any(not isinstance(v, Mapping) or set(v) != (expected_predictor_keys | {"candidate"} if p == "human_footprint" else expected_predictor_keys) for p,v in predictors.items()): raise PredictorDomainError("source_predictor_schema_drift")
    if predictors["human_footprint"].get("classification") != "exact_local_duplicate_no_recovery" or {p: predictors[p].get("classification") for p in LEGACY_AMBIGUOUS} != {p: "legacy_lineage_ambiguous" for p in LEGACY_AMBIGUOUS} or {p: predictors[p].get("classification") for p in UNAVAILABLE} != {p: "unavailable" for p in UNAVAILABLE}: raise PredictorDomainError("source_classification_semantic_drift")
    ssum=payloads["domain_summary"]
    if ssum.get("rule") != "D_struct = canonical cells with observed nonmissing values for all 28 predictors" or ssum.get("predictors_retained") != list(ACTIVE): raise PredictorDomainError("domain_contract_semantic_drift")
    mc, rc, rr = ssum["map_cells"], ssum["response_cells"], ssum["response_rows"]
    if set(mc) != {"total","included","excluded","missing_pattern_counts"} or set(rc) != {"total","included","excluded","missing_by_predictor","missing_pattern_counts"} or set(rr) != {"total","included","excluded","missing_by_predictor","missing_pattern_counts"}: raise PredictorDomainError("domain_nested_schema_drift")
    if (mc.get("total"),mc.get("included"),mc.get("excluded")) != (MAP_ROWS,MAP_INCLUDED,MAP_EXCLUDED) or (rc.get("total"),rc.get("included"),rc.get("excluded")) != (RESP_CELLS,RESP_CELL_INCLUDED,RESP_CELL_EXCLUDED) or (rr.get("total"),rr.get("included"),rr.get("excluded")) != (RESP_ROWS,RESP_INCLUDED,RESP_EXCLUDED): raise PredictorDomainError("domain_summary_semantic_drift")
    for group, total in ((mc, MAP_ROWS), (rc, RESP_CELLS), (rr, RESP_ROWS)):
        patterns=group.get("missing_pattern_counts", {}); counts=[int(v) for v in patterns.values()]
        if any(v < 0 for v in counts) or sum(counts) != total: raise PredictorDomainError("missing_pattern_semantic_drift")
    if mc["missing_pattern_counts"].get("complete") != MAP_INCLUDED: raise PredictorDomainError("map_complete_semantic_drift")
    if ssum.get("repairs") != {"status":"not_authorized","values":0} or ssum.get("missingness_reconciliation") != {"map_total":MAP_ROWS,"map_included_plus_excluded":MAP_INCLUDED+MAP_EXCLUDED,"response_cell_total":RESP_CELLS,"response_cell_included_plus_excluded":RESP_CELL_INCLUDED+RESP_CELL_EXCLUDED,"response_row_total":RESP_ROWS,"response_row_included_plus_excluded":RESP_INCLUDED+RESP_EXCLUDED}: raise PredictorDomainError("domain_reconciliation_semantic_drift")
    if any(not isinstance(v, int) or v < 0 for v in rc.get("missing_by_predictor", {}).values()) or any(not isinstance(v, int) or v < 0 for v in rr.get("missing_by_predictor", {}).values()) or set(rc.get("missing_by_predictor", {})) != set(ACTIVE) or set(rr.get("missing_by_predictor", {})) != set(ACTIVE): raise PredictorDomainError("response_missingness_semantic_drift")
    for p in ACTIVE:
        burden = predictors[p]
        if burden.get("missing_cells") != sum(1 for key, count in mc["missing_pattern_counts"].items() if key != "complete" and p in key.split("|") for _ in range(count)) or burden.get("missing_response_cells") != rc["missing_by_predictor"][p] or burden.get("missing_response_rows") != rr["missing_by_predictor"][p] or burden.get("candidate_recovered_values") != 0: raise PredictorDomainError("source_burden_semantic_drift")
    ri=payloads["response_impact"]
    if ri.get("rows") != RESP_ROWS or ri.get("included") != RESP_INCLUDED or ri.get("excluded") != RESP_EXCLUDED: raise PredictorDomainError("response_impact_semantic_drift")
    expected_group = {"by_species": set(SPECIES), "by_pa_type": set(PA_TYPES), "by_response_origin": set(RESPONSE_ORIGINS), "by_source_combination": set(SOURCE_COMBINATIONS)}
    for key, levels in expected_group.items():
        tab=ri.get(key, {})
        if set(tab) != levels or any(not isinstance(v, Mapping) or set(v) != {"rows","included","excluded"} for v in tab.values()) or sum(v.get("rows",0) for v in tab.values()) != RESP_ROWS or sum(v.get("included",0) for v in tab.values()) != RESP_INCLUDED or sum(v.get("excluded",0) for v in tab.values()) != RESP_EXCLUDED or any(v.get("rows") != v.get("included") + v.get("excluded") for v in tab.values()): raise PredictorDomainError("response_group_semantic_drift")
    for key, left, right in (("species_x_pa_type", "by_species", "by_pa_type"), ("species_x_source_combination", "by_species", "by_source_combination"), ("pa_type_x_source_combination", "by_pa_type", "by_source_combination")):
        tab=ri.get(key, {})
        if any(not isinstance(v, Mapping) or set(v) != {"rows","included","excluded"} for v in tab.values()) or sum(v.get("rows",0) for v in tab.values()) != RESP_ROWS or sum(v.get("included",0) for v in tab.values()) != RESP_INCLUDED or sum(v.get("excluded",0) for v in tab.values()) != RESP_EXCLUDED: raise PredictorDomainError("response_intersection_semantic_drift")
        for group, values in ((left, ri[left]), (right, ri[right])):
            for level, summary in values.items():
                idx = 0 if group == left else 1
                if any(sum(v.get(metric,0) for k,v in tab.items() if k.split("|",1)[idx] == level) != summary[metric] for metric in ("rows","included","excluded")): raise PredictorDomainError("response_intersection_marginal_drift")
    if ri.get("survey_supported_absences") != {"rows":2160,"included":2114,"excluded":46}: raise PredictorDomainError("survey_absence_semantic_drift")
    sc=payloads["support_contract"]
    if set(sc.get("goal023_diagnostics", {})) != {"pooled_and_species_support","structural_filter","pooled_envelope_cells","pooled_unseen_category_cells"} or set(sc.get("later_recompute", {})) != {"categorical_novelty","continuous_support"} or set(sc.get("domain_policy", {})) != {"primary","sensitivity","not_uniquely_data_determined"} or set(sc.get("pseudoabsence_post_domain", {})) != {"before_rows","retained_rows","excluded_rows","retained_support_count_below_3","retained_support_species_distinct_below_3","retained_distance_below_5000_m","retained_broken_same_cell_support_presence_links","retained_support_presence_outside_d_struct","rederivation_required","preservation_rationale","goal021_contract","goal025_deferred"}: raise PredictorDomainError("support_nested_schema_drift")
    pp=sc["pseudoabsence_post_domain"]
    if pp.get("before_rows") != 587 or pp.get("retained_rows") != 498 or pp.get("excluded_rows") != 89 or any(pp.get(k) != 0 for k in ("retained_support_count_below_3","retained_support_species_distinct_below_3","retained_distance_below_5000_m","retained_broken_same_cell_support_presence_links","retained_support_presence_outside_d_struct")) or pp.get("rederivation_required") is not False or pp.get("goal021_contract") != {"quota_contract":False,"stops_before_balancing_thinning":True}: raise PredictorDomainError("pseudoabsence_post_domain_semantic_drift")
    if sc["operational_estimand"] != "species-specific relative response score over canonical cells in D_struct, conditional on the accepted presence/survey-supported-absence/pseudoabsence construction; not detection-corrected occupancy, abundance, population prevalence, or inference outside D_struct" or sc["domain_policy"] != {"primary":"D_struct is the deliberate primary policy: high-coverage, provenance-safe, retaining all 28 predictors","sensitivity":"any future full-domain fold-fitted missing-treatment analysis is sensitivity only; excluded cells and rows remain audit/sensitivity material","not_uniquely_data_determined":"D_struct is a policy choice, not the uniquely data-determined consequence of the source audit"}: raise PredictorDomainError("estimand_policy_semantic_drift")
    if sc["goal023_diagnostics"] != {"pooled_and_species_support":"descriptive prepartition evidence only","structural_filter":False,"pooled_envelope_cells":987,"pooled_unseen_category_cells":51} or sc["later_recompute"] != {"categorical_novelty":"per species and training fold","continuous_support":"per species and training fold"} or sc["future_repair"] != "requires a new versioned goal" or sc["stopped_before"] != ["partitions","fitted_transformations","imputation","encoding","scaling","mapping","modelling"]: raise PredictorDomainError("support_contract_semantic_drift")
    out = payloads.get("outputs", {})
    expected_rows = {PRIVATE_NAMES[0]: MAP_INCLUDED, PRIVATE_NAMES[1]: RESP_CELL_INCLUDED, PRIVATE_NAMES[2]: RESP_INCLUDED, PRIVATE_NAMES[3]: MAP_ROWS, PRIVATE_NAMES[4]: RESP_ROWS}
    expected_schemas = {PRIVATE_NAMES[0]: MAP_SCHEMA, PRIVATE_NAMES[1]: MAP_SCHEMA, PRIVATE_NAMES[2]: RESPONSE_SCHEMA, PRIVATE_NAMES[3]: AUDIT_CELL_SCHEMA, PRIVATE_NAMES[4]: AUDIT_RESP_SCHEMA}
    if out.get("private_outputs_ignored") is not True or set(out.get("roles", {})) != set(expected_rows): raise PredictorDomainError("outputs_semantic_drift")
    for name, rows in expected_rows.items():
        role=out["roles"].get(name)
        if not isinstance(role, Mapping) or set(role) != {"rows","schema","bytes","sha256"} or role.get("rows") != rows or role.get("schema") != expected_schemas[name] or not isinstance(role.get("bytes"), int) or role["bytes"] <= 0 or not re.fullmatch(r"[0-9a-f]{64}", str(role.get("sha256", ""))): raise PredictorDomainError("outputs_semantic_drift")
    review=payloads["review"]
    if review != {"goal_id":GOAL_ID,"repair_status":"repair_not_authorized","decision":"supported_structural_domain_frozen","zero_repairs":True,"all_28_predictors_retained":True,"conditional_inference_statement":True,"operational_estimand":"species-specific relative response score over canonical cells in D_struct, conditional on the accepted presence/survey-supported-absence/pseudoabsence construction; not detection-corrected occupancy, abundance, population prevalence, or inference outside D_struct","domain_policy":"D_struct is the deliberate primary policy choice: high-coverage, provenance-safe, retaining all 28 predictors; it is not uniquely data-determined by the source audit","pseudoabsence_post_domain_status":"validated; rederivation not required; Goal025 defers per-species/fold adequacy","barry_decisions_pending":[],"stop_boundary":"before partitions, transformations, imputation, encoding, scaling, mapping, modelling","future_source_package":"opens a new goal","privacy":PRIVACY}: raise PredictorDomainError("review_semantic_drift")

def validate_evidence(plan_path: Path, evidence_dir: Path, *, full: bool=False, root: Path|None=None) -> dict[str, Any]:
    plan=json.loads(plan_path.read_text()); validate_plan(plan)
    entries=list(evidence_dir.iterdir())
    if {p.name for p in entries} != set(EVIDENCE_FILES)|{"manifest.json"} or any(not p.is_file() or p.is_symlink() for p in entries): raise PredictorDomainError("evidence_footprint_drift")
    if json.loads((evidence_dir/"manifest.json").read_text()) != _manifest(evidence_dir): raise PredictorDomainError("manifest_drift")
    payloads={n[:-5]:json.loads((evidence_dir/n).read_text()) for n in EVIDENCE_FILES}
    for p in payloads.values(): _evidence_privacy(p)
    _validate_semantics(payloads)
    if full:
        if root is None: root=plan_path.parents[1]
        from dsdm_phase1.predictor_support_diagnostics import validate_evidence as v023
        try:
            v023(root/"config/predictor_support_diagnostic_plan.json",root/"evidence/predictor_support_diagnostics/2026-07-26",full=True,root=root)
            computed=compute_outputs(root,plan)
            expected_private=_private_expected(computed)
            private_dir=root/"data/processed/predictors/goal024-predictor-source-repair-domain-freeze"/DATE
            actual_outputs=_private_metadata(private_dir, expected_private)
            if payloads["outputs"] != actual_outputs: raise PredictorDomainError("private_output_metadata_drift")
            actual=compute_evidence(root,plan,computed)
            # ``outputs`` is bound to the freshly written private payloads;
            # compare every aggregate evidence surface and validate that
            # tracked output metadata remains structurally present.
            for key in ("source_inventory", "source_comparison", "domain_summary", "response_impact", "support_contract", "review"):
                if actual[key] != payloads[key]: raise PredictorDomainError("full_replay_failure")
            if actual_outputs != payloads["outputs"]: raise PredictorDomainError("outputs_semantic_drift")
        except PredictorDomainError: raise
        except Exception as exc: raise PredictorDomainError("upstream_validation_failure") from exc
    return {"tracked_valid":True,"full_replay":bool(full)}

def _publish_pair(stage_private: Path, stage_evidence: Path, private: Path, evidence: Path) -> None:
    if private.exists() or evidence.exists(): raise PredictorDomainError("publication_destination_exists")
    moved_private=False
    try:
        stage_private.rename(private); moved_private=True; stage_evidence.rename(evidence)
    except Exception as exc:
        if moved_private and private.exists(): private.rename(stage_private)
        raise PredictorDomainError("publication_rollback") from exc

def run_production(root: Path) -> dict[str, Any]:
    plan_path=root/"config/predictor_source_repair_domain_freeze_plan.json"; plan=json.loads(plan_path.read_text()); validate_plan(plan)
    private=root/"data/processed/predictors/goal024-predictor-source-repair-domain-freeze"/DATE; evidence=root/"evidence/predictor_source_repair_domain_freeze"/DATE
    if private.exists() or evidence.exists(): raise PredictorDomainError("publication_destination_exists")
    c=compute_outputs(root,plan); payloads=compute_evidence(root,plan,c)
    private_parent=private.parent; evidence_parent=evidence.parent; private_parent.mkdir(parents=True,exist_ok=True); evidence_parent.mkdir(parents=True,exist_ok=True)
    stage_root=Path(tempfile.mkdtemp(prefix="goal024-stage-",dir=private_parent)); sp=stage_root/"private"; se=stage_root/"evidence"; sp.mkdir(); se.mkdir()
    try:
        _write_csv(sp/"predictor_cell_map_canonical.csv",c["domain"]["map_in"],MAP_SCHEMA); _write_csv(sp/"predictor_response_cells_canonical.csv",c["domain"]["cell_in"],MAP_SCHEMA); _write_csv(sp/"response_layer_canonical.csv",c["domain"]["response_in"],RESPONSE_SCHEMA)
        _write_csv(sp/"cell_domain_audit.csv",c["cell_audit"],AUDIT_CELL_SCHEMA); _write_csv(sp/"response_domain_audit.csv",c["response_audit"],AUDIT_RESP_SCHEMA)
        outputs=_private_metadata(sp, _private_expected(c))
        payloads["outputs"]=outputs; _validate_semantics(payloads)
        for name in EVIDENCE_FILES: (se/name).write_text(json.dumps(payloads[name[:-5]],sort_keys=True,indent=2)+"\n")
        (se/"manifest.json").write_text(json.dumps(_manifest(se),sort_keys=True,indent=2)+"\n")
        validate_evidence(plan_path, se)
        _publish_pair(sp,se,private,evidence)
    finally: shutil.rmtree(stage_root,ignore_errors=True)
    return {"private":str(private),"evidence":str(evidence),"files":11}

if __name__ == "__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2]); ap.add_argument("--validate",action="store_true"); a=ap.parse_args(); print(validate_evidence(a.root/"config/predictor_source_repair_domain_freeze_plan.json",a.root/"evidence/predictor_source_repair_domain_freeze"/DATE,full=True,root=a.root) if a.validate else run_production(a.root))
