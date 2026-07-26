"""Goal 023 predictor-support and map-domain decision diagnostics.

This module reads the frozen Goal 021 response and Goal 022 raw predictor
products, computes aggregate diagnostics only, and publishes a hash-bound
tracked evidence package.  No values are imputed, transformed, pooled,
partitioned, mapped, or modelled.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import tempfile
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree as ET

GOAL_ID = "goal023-predictor-support-map-domain-2026-07-26"
DATE = "2026-07-26"
EVIDENCE_FILES = ("source_metadata.json", "missingness_patterns.json", "response_impact.json", "categorical_support.json", "environmental_support.json", "policy_options.json", "analysis_scope.json", "review.json")
PREDICTOR_EVIDENCE = Path("evidence/predictor_stack_extraction/2026-07-26")
PREDICTOR_OUTPUT = Path("data/processed/predictors/goal022-predictor-stack-extraction/2026-07-26")
RESPONSE = Path("data/processed/response/goal021-pseudoabsence-derivation/2026-07-26/response_layer.csv")
ACTIVE = ("annmeantemp","meandiurnrange","isothermality","tempseason","maxtempwarmmonth","mintempcoldmonth","tempannrange","meantempwetq","meantempdryq","meantempwarmq","meantempcoldq","annprecip","precipwetmonth","precipdrymonth","precipseason","precipwetq","precipdryq","precipwarmq","precipcoldq","elevation","top_roughness","soil_class","dist_fw","dist_road","fpar","veg_mvg","landuse_secondary","human_footprint")
CATEGORICAL = ("soil_class", "veg_mvg", "landuse_secondary")
CONTINUOUS = tuple(x for x in ACTIVE if x not in CATEGORICAL)
CANONICAL_ROWS, RESPONSE_CELLS, RESPONSE_ROWS = 74073, 5407, 13455
DOWNSTREAM_SPECIES = ("dasyurus_maculatus","dasyurus_viverrinus","notamacropus_rufogriseus","pseudocheirus_peregrinus","sarcophilus_harrisii","thylogale_billardierii","trichosurus_vulpecula","vombatus_ursinus")
ALL_CANDIDATE_SPECIES = DOWNSTREAM_SPECIES + ("macropus_giganteus",)
PA_TYPES = ("presence", "pseudoabsence", "survey_supported_absence")
RESPONSE_ORIGINS = ("derived_pseudoabsence", "goal020")
SOURCE_COMBINATIONS = ("", "ala_only_presence", "ala_overrides_camera_absence", "both_presence", "camera_absence_retained", "camera_only_presence")
PENDING_DECISIONS = ["prediction target domain", "authority for targeted source-repair exception", "fallback treatment if full-domain prediction is required"]
SHARED_SIX = ("elevation", "top_roughness", "soil_class", "dist_fw", "dist_road", "fpar")
SOURCE_BINDING_ROLES = ("canonical_predictor_csv", "decision_bundle", "goal021_manifest", "goal021_outputs", "goal021_plan", "goal021_response", "legacy_script", "predictor_band_manifest", "predictor_categorical_levels", "predictor_manifest", "predictor_missingness", "predictor_plan", "predictor_review", "predictor_source_inventory", "predictor_spatial", "response_predictor_csv", "scoping_review", "workbook")
PLAN_PRIVACY = {"tracked_grid_ids_or_coordinates": False, "tracked_row_payloads": False, "tracked_private_paths": False, "tracked_response_identifiers": False, "tracked_site_or_camera_ids": False, "tracked_private_observation_timing": False}
STOPPED_BEFORE = ["imputation", "fill", "resampling", "encoding", "scaling", "partitions", "mapping", "modelling", "policy_selection"]
EXPECTED_PLAN_BINDINGS = {
    "decision_bundle": ("config/phase1_decision_bundle.json", "ccccbb2e56e101b1a53421f8016699bfb500f4356861e10c1213a398aabe04a2"),
    "predictor_plan": ("config/predictor_stack_extraction_plan.json", "e75af21cf553cd5a10e375a9f3f29ebfc7b574a8684b8f82f830c111c0c34c65"),
    "predictor_manifest": ("evidence/predictor_stack_extraction/2026-07-26/manifest.json", "d0c72e0b0fc614813438ae6d554b4522ae65305daf63543aa8b9774b7e891c60"),
    "predictor_source_inventory": ("evidence/predictor_stack_extraction/2026-07-26/source_inventory.json", "c102a140898a2ddb63671c008e980624879bb5cae9efe8734da1b2452ca468e0"),
    "predictor_band_manifest": ("evidence/predictor_stack_extraction/2026-07-26/band_manifest.json", "b1fd813bff80aa89ccc18396fce4d3e9c637dd435c73acaa1456c946757bce85"),
    "predictor_categorical": ("evidence/predictor_stack_extraction/2026-07-26/categorical_levels.json", "67267857bf1385bccc4d58566f736d4e16926c46cd4130e305fd176ea5be6a24"),
    "predictor_missingness": ("evidence/predictor_stack_extraction/2026-07-26/missingness_summary.json", "0d519aa2a11594e70c992096fb22e47b3ca5efeac151212a22a407e3e8c82a66"),
    "predictor_spatial": ("evidence/predictor_stack_extraction/2026-07-26/spatial_summary.json", "90022c610e364b2b6cdf3af69d807ae9ab7f66889ed5f70113c009372e57be45"),
    "predictor_outputs": ("evidence/predictor_stack_extraction/2026-07-26/outputs.json", "72bc6b81a25016fc8ba2bdae677d4f0c35021ce33ba0dfaac3aa4f2fe4c08ff5"),
    "goal021_plan": ("config/pseudoabsence_derivation_plan.json", "75cdc198815d3076af6ee3b6f25bed5ea4e90bf1433c7e9205f8692dfedd95fe"),
    "goal021_manifest": ("evidence/pseudoabsence_derivation/2026-07-26/manifest.json", "bf843690a6071f489b81fb5bdc348bab1c9f2001dfa37ad359ed7dc75d50f875"),
    "goal021_outputs": ("evidence/pseudoabsence_derivation/2026-07-26/outputs.json", "ecf0e6f46b3eec30c4edeff26d02f694be18cbc063268d9e1780f8cca7b5a3d9"),
    "goal021_response": (str(RESPONSE), "e67298d11d7eb29e6bf8ca055cd8b64cfaf119d193ff0675fff09719ce0616a3"),
    "predictor_map_csv": (str(PREDICTOR_OUTPUT/"predictor_cell_map_raw.csv"), "0e2082671096bbf80745038bad8329d3bb4fd58dc20b8a4adb146c3d62459542"),
    "predictor_response_csv": (str(PREDICTOR_OUTPUT/"predictor_response_cells_raw.csv"), "4438d383c6f63e38b0bf61bcbb3812df4e3a26b9e2185d718d2fc03817bbb92f"),
    "legacy_script": ("temp/src/3_create_sdm_data.R", "cff353c830fe78e351fc72f2672dd1c73e94930ebf4516b53c5950ec19a4effe"),
    "workbook": ("temp/data/spatial/se_stack_metadata.xlsx", "ec460f9a41913f3288ca7dd38b6150b575f9c00b73581b892468cd0577127edd"),
    "scoping_review": ("docs/scoping_review_2026-05-27.md", "758f2e0acba010f1a1a0f8bf35642bb969aa77b57e6a29ebc9884de035c96f61"),
}

class PredictorSupportError(ValueError):
    pass

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def _safe_relative(v: Any) -> Path:
    if not isinstance(v, str) or not v or Path(v).is_absolute() or ".." in Path(v).parts:
        raise PredictorSupportError("unsafe_binding_path")
    return Path(v)

def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f: return list(csv.DictReader(f))

def _percentile(values: list[float], p: float) -> float | None:
    if not values: return None
    x = sorted(values); pos = (len(x)-1)*p; lo, hi = math.floor(pos), math.ceil(pos)
    return float(x[lo] if lo == hi else x[lo] + (x[hi]-x[lo])*(pos-lo))

def missing_pattern(rows: Iterable[Mapping[str, Any]], predictors: Iterable[str] = ACTIVE) -> dict[str, Any]:
    preds = tuple(predictors); counts = Counter(); ncounts = Counter(); classes = Counter()
    for r in rows:
        miss = tuple(p for p in preds if str(r.get(p, "")) == "")
        counts["|".join(miss) if miss else "complete"] += 1; ncounts[len(miss)] += 1
        classes["complete" if not miss else "continuous_only" if all(p not in CATEGORICAL for p in miss) else "categorical_only" if all(p in CATEGORICAL for p in miss) else "both"] += 1
    return {"pattern_counts": dict(sorted(counts.items())), "missing_count_distribution": {str(k): v for k,v in sorted(ncounts.items())}, "pattern_class_counts": dict(sorted(classes.items()))}

def _grid_xy(key: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"g_(-?\d+)_(-?\d+)", key or "")
    return (int(m.group(1)), int(m.group(2))) if m else None

def rook_components(rows: Iterable[Mapping[str, Any]], missing_keys: set[str]) -> dict[str, Any]:
    xy = {k: _grid_xy(k) for k in missing_keys}; xy = {k:v for k,v in xy.items() if v is not None}; rev = {v:k for k,v in xy.items()}; edges = 0; seen=set(); sizes=[]
    for k, (x,y) in xy.items():
        for nb in ((x+100,y),(x-100,y),(x,y+100),(x,y-100)):
            if nb in rev: edges += 1
    edges //= 2
    for k in xy:
        if k in seen: continue
        q=[k]; seen.add(k); size=0
        while q:
            cur=q.pop(); size += 1; x,y=xy[cur]
            for nb in ((x+100,y),(x-100,y),(x,y+100),(x,y-100)):
                nk=rev.get(nb)
                if nk and nk not in seen: seen.add(nk); q.append(nk)
        sizes.append(size)
    return {"missing_cell_count": len(xy), "rook_missing_missing_edges": edges, "connected_component_count": len(sizes), "connected_component_size_distribution": {str(k):v for k,v in sorted(Counter(sizes).items())}}

def edge_distance_summary(rows: Iterable[Mapping[str, Any]], missing_keys: set[str]) -> dict[str, Any]:
    keys={r.get("grid_cell_id") for r in rows}; xy={k:_grid_xy(k) for k in keys}; xy={k:v for k,v in xy.items() if v is not None}; rev={v:k for k,v in xy.items()}
    edge=set()
    for k,(x,y) in xy.items():
        if any((x+dx,y+dy) not in rev for dx,dy in ((100,0),(-100,0),(0,100),(0,-100))): edge.add(k)
    dist={k:0 for k in edge}; q=deque(edge)
    while q:
        k=q.popleft(); x,y=xy[k]
        for nb in ((x+100,y),(x-100,y),(x,y+100),(x,y-100)):
            nk=rev.get(nb)
            if nk is not None and nk not in dist: dist[nk]=dist[k]+1; q.append(nk)
    bands={"edge":0,"1-10":0,">10":0,"unresolved":0}
    for k in missing_keys:
        d=dist.get(k)
        bands["unresolved" if d is None else "edge" if d==0 else "1-10" if d<=10 else ">10"] += 1
    edge_missing=sum(k in edge for k in missing_keys); nonedge_missing=len(missing_keys)-edge_missing; edge_total=len(edge); nonedge_total=len(keys)-edge_total
    er=edge_missing/edge_total if edge_total else None; nr=nonedge_missing/nonedge_total if nonedge_total else None
    return {"canonical_edge_definition":"cell has at least one absent rook neighbour on the frozen 100-unit ID lattice","canonical_edge_cells":edge_total,"canonical_nonedge_cells":nonedge_total,"incomplete_edge_cells":edge_missing,"incomplete_nonedge_cells":nonedge_missing,"incomplete_rate_edge":er,"incomplete_rate_nonedge":nr,"risk_ratio_edge_vs_nonedge":er/nr if er is not None and nr else None,"odds_ratio_edge_vs_nonedge":(er/(1-er))/(nr/(1-nr)) if er is not None and nr is not None and er<1 and nr<1 and nr>0 else None,"incomplete_distance_bands":bands}

def _parse_xlsx(path: Path) -> dict[str, list[list[str]]]:
    """Read simple shared-string XLSX sheets without external dependencies."""
    with zipfile.ZipFile(path) as z:
        shared=[]
        if "xl/sharedStrings.xml" in z.namelist():
            root=ET.fromstring(z.read("xl/sharedStrings.xml")); ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in root.findall("m:si", ns): shared.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
        wb=ET.fromstring(z.read("xl/workbook.xml")); rel=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"));
        relmap={r.attrib["Id"]:r.attrib["Target"] for r in rel}
        ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}; out={}
        for sh in wb.findall("m:sheets/m:sheet",ns):
            target=relmap[sh.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]; target="xl/"+target.lstrip("/") if not target.startswith("xl/") else target
            root=ET.fromstring(z.read(target)); rows=[]
            for row in root.findall("m:sheetData/m:row",ns):
                vals=[]
                for c in row.findall("m:c",ns):
                    v=c.find("m:v",ns); value="" if v is None else (shared[int(v.text)] if c.attrib.get("t")=="s" else v.text or "")
                    vals.append(value)
                rows.append(vals)
            out[sh.attrib["name"]]=rows
        return out

def parse_workbook_reference(path: Path) -> dict[str, Any]:
    sheets = _parse_xlsx(path); result={"workbook_sha256": sha256(path), "sheets": {}}
    for name, rows in sheets.items():
        clean=[]
        for row in rows:
            vals=[]
            for value in row:
                # The workbook contains one personal attribution email; retain
                # the attribution text while deliberately omitting the address.
                vals.append(re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email omitted]", str(value)))
            if any(v.strip() for v in vals): clean.append(vals)
        result["sheets"][name] = {"range": f"A1:{chr(64+max((len(r) for r in rows), default=1))}{len(rows)}", "rows": len(rows), "nonempty_rows": clean}
    return result

def _table(rows: list[Mapping[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    out={}
    for f in fields:
        c=Counter(str(r.get(f,"")) for r in rows); out[f]={k:v for k,v in sorted(c.items())}
    return out

def _joint_table(rows: list[Mapping[str, Any]], fields: tuple[str, ...]) -> dict[str, int]:
    c=Counter("|".join(str(r.get(f,"")) for f in fields) for r in rows)
    return dict(sorted(c.items()))

def _joint_breakdown(rows: list[Mapping[str, Any]], fields: tuple[str, ...], complete_flag) -> dict[str, dict[str, int]]:
    keys=sorted({"|".join(str(r.get(f,"")) for f in fields) for r in rows})
    return {k:{"rows":sum("|".join(str(r.get(f,"")) for f in fields)==k for r in rows),"complete":sum("|".join(str(r.get(f,"")) for f in fields)==k and complete_flag(r) for r in rows),"incomplete":sum("|".join(str(r.get(f,"")) for f in fields)==k and not complete_flag(r) for r in rows)} for k in keys}

def _read_sources(root: Path, plan: Mapping[str, Any]) -> tuple[list[dict[str,str]], list[dict[str,str]], list[dict[str,str]]]:
    pm = root / PREDICTOR_OUTPUT / "predictor_cell_map_raw.csv"; pr = root / PREDICTOR_OUTPUT / "predictor_response_cells_raw.csv"; rr = root / RESPONSE
    for p in (pm,pr,rr):
        if not p.is_file(): raise PredictorSupportError(f"missing_source:{p}")
    return _read_csv(pm), _read_csv(pr), _read_csv(rr)

def _verify_plan_bindings(root: Path, plan: Mapping[str, Any]) -> None:
    for role, spec in plan.get("bindings", {}).items():
        path = root / _safe_relative(spec.get("path"))
        if not path.is_file() or path.is_symlink() or sha256(path) != spec.get("sha256"):
            raise PredictorSupportError(f"binding_drift:{role}")

def _binding_records(root: Path) -> dict[str, dict[str, str]]:
    paths={"decision_bundle":"config/phase1_decision_bundle.json","predictor_plan":"config/predictor_stack_extraction_plan.json","predictor_manifest":"evidence/predictor_stack_extraction/2026-07-26/manifest.json","predictor_source_inventory":"evidence/predictor_stack_extraction/2026-07-26/source_inventory.json","predictor_band_manifest":"evidence/predictor_stack_extraction/2026-07-26/band_manifest.json","predictor_categorical_levels":"evidence/predictor_stack_extraction/2026-07-26/categorical_levels.json","predictor_missingness":"evidence/predictor_stack_extraction/2026-07-26/missingness_summary.json","predictor_spatial":"evidence/predictor_stack_extraction/2026-07-26/spatial_summary.json","predictor_review":"evidence/predictor_stack_extraction/2026-07-26/review.json","goal021_plan":"config/pseudoabsence_derivation_plan.json","goal021_manifest":"evidence/pseudoabsence_derivation/2026-07-26/manifest.json","goal021_outputs":"evidence/pseudoabsence_derivation/2026-07-26/outputs.json","goal021_response":str(RESPONSE),"legacy_script":"temp/src/3_create_sdm_data.R","workbook":"temp/data/spatial/se_stack_metadata.xlsx","scoping_review":"docs/scoping_review_2026-05-27.md","canonical_predictor_csv":str(PREDICTOR_OUTPUT/"predictor_cell_map_raw.csv"),"response_predictor_csv":str(PREDICTOR_OUTPUT/"predictor_response_cells_raw.csv")}
    return {k:{"path":v,"sha256":sha256(root/_safe_relative(v))} for k,v in paths.items()}

def compute_diagnostics(root: Path, plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    _verify_plan_bindings(root, plan)
    canonical, response_cells, response = _read_sources(root, plan); bykey={r["grid_cell_id"]:r for r in canonical}
    if len(canonical)!=CANONICAL_ROWS or len(response_cells)!=RESPONSE_CELLS or len(response)!=RESPONSE_ROWS: raise PredictorSupportError("source_row_count_drift")
    if any(r["grid_cell_id"] not in bykey for r in response): raise PredictorSupportError("response_join_failure")
    bind=_binding_records(root); wb=parse_workbook_reference(root/"temp/data/spatial/se_stack_metadata.xlsx")
    source={"goal_id":GOAL_ID,"verified_stack":{"canonical_cells":CANONICAL_ROWS,"response_cells":RESPONSE_CELLS,"active_predictors":list(ACTIVE),"categorical_predictors":list(CATEGORICAL),"geometry":{"crs":"EPSG:4326","width":468,"height":455,"bands":32,"alignment":"exact centre indexing"}},"workbook_reference":wb,"lineage_status":{"stack_order":"verified against hashed legacy positional order; native band descriptions unavailable","geometry":"verified from Goal022 extraction contract","units_dates_resampling_nodata":"unavailable in native metadata; not inferred","workbook_labels_sources":"reference descriptions only; not verified construction lineage","source_product_windows_allowed":"non-sensitive source-product dates/windows are reference metadata; private observation timing remains excluded"},"bindings":bind,"privacy":PLAN_PRIVACY}
    miss_can=missing_pattern(canonical); miss_cell=missing_pattern(response_cells); miss_row=missing_pattern([{**bykey[r["grid_cell_id"]], **r} for r in response])
    missing_keys={r["grid_cell_id"] for r in canonical if r.get("missing_predictor_count","0")!="0"}
    missing_patterns={"canonical":{"rows":len(canonical),**miss_can},"response_cells":{"rows":len(response_cells),**miss_cell},"response_rows":{"rows":len(response),**miss_row},"rook_adjacency":rook_components(canonical,missing_keys),"edge_support":edge_distance_summary(canonical,missing_keys)}
    complete_flag=lambda r: bykey[r["grid_cell_id"]].get("predictor_complete")=="true"
    def breakdown(field):
        return {k:{"rows":sum(r.get(field)==k for r in response),"complete":sum(r.get(field)==k and complete_flag(r) for r in response),"incomplete":sum(r.get(field)==k and not complete_flag(r) for r in response)} for k in sorted({r.get(field) for r in response})}
    response_impact={"rows":len(response),"complete":sum(complete_flag(r) for r in response),"incomplete":sum(not complete_flag(r) for r in response),"by_species":_table(response,("species_id",)),"by_pa_type":_table(response,("pa_type",)),"by_response_origin":breakdown("response_origin"),"by_source_combination":breakdown("source_combination"),"by_species_complete":{s:{"rows":sum(r.get("species_id")==s for r in response),"complete":sum(r.get("species_id")==s and complete_flag(r) for r in response),"incomplete":sum(r.get("species_id")==s and not complete_flag(r) for r in response),"loss_rate":sum(r.get("species_id")==s and not complete_flag(r) for r in response)/max(1,sum(r.get("species_id")==s for r in response))} for s in sorted({r.get("species_id") for r in response})},"by_pa_type_complete":{p:{"rows":sum(r.get("pa_type")==p for r in response),"complete":sum(r.get("pa_type")==p and complete_flag(r) for r in response),"incomplete":sum(r.get("pa_type")==p and not complete_flag(r) for r in response),"loss_rate":sum(r.get("pa_type")==p and not complete_flag(r) for r in response)/max(1,sum(r.get("pa_type")==p for r in response))} for p in sorted({r.get("pa_type") for r in response})},"material_intersections":{"species_x_pa_type":_joint_breakdown(response,("species_id","pa_type"),complete_flag),"species_x_source_combination":_joint_breakdown(response,("species_id","source_combination"),complete_flag),"pa_type_x_source_combination":_joint_breakdown(response,("pa_type","source_combination"),complete_flag)},"survey_supported_absence_first_class":True}
    cat={"sparse_threshold_response_cells":5,"variables":{}}
    for p in CATEGORICAL:
        cm=Counter(r[p] for r in canonical if r.get(p)!=""); rc=Counter(r[p] for r in response_cells if r.get(p)!=""); rr=Counter(bykey[x["grid_cell_id"]][p] for x in response if bykey[x["grid_cell_id"]].get(p)!="")
        cat["variables"][p]={"canonical_cell_counts":dict(sorted(cm.items())),"response_cell_counts":dict(sorted(rc.items())),"response_row_counts":dict(sorted(rr.items())),"observed_codes":sorted(cm),"sparse_response_codes":sorted(k for k,v in rc.items() if v<5),"absent_in_response_cells":sorted(k for k in cm if k not in rc),"reference_labels_status":"workbook reference only; lineage unproven"}
    response_code_sets={p:{x[p] for x in response_cells if x.get(p)!=""} for p in CATEGORICAL}
    pooled_unseen_by_variable={p:sum(r.get("predictor_complete")=="true" and r[p] not in response_code_sets[p] for r in canonical) for p in CATEGORICAL}
    cat["pooled_unseen_complete_cells_by_variable"]=pooled_unseen_by_variable
    cat["pooled_unseen_codes_in_fully_complete_map_cells"]=sum(r.get("predictor_complete")=="true" and any(r[p] not in response_code_sets[p] for p in CATEGORICAL) for r in canonical)
    cat["per_species"]={}
    complete_map=[r for r in canonical if r.get("predictor_complete")=="true"]
    for species in DOWNSTREAM_SPECIES:
        scells={x["grid_cell_id"] for x in response if x.get("species_id")==species}; details={}; affected=set()
        for p in CATEGORICAL:
            codes={bykey[k][p] for k in scells if bykey[k].get(p)!=""}; absent={r[p] for r in complete_map if r[p] not in codes}; details[p]={"response_cell_codes":sorted(codes),"map_codes_absent_from_species_response":sorted(absent),"affected_complete_map_cells":sum(r[p] in absent for r in complete_map),"denominator_complete_map_cells":len(complete_map),"rate":sum(r[p] in absent for r in complete_map)/len(complete_map)}
        affected.update(r["grid_cell_id"] for r in complete_map if any(r[q] in details[q]["map_codes_absent_from_species_response"] for q in CATEGORICAL))
        cat["per_species"][species]={"variables":details,"affected_complete_map_cells_any_unseen_level":len(affected),"denominator_complete_map_cells":len(complete_map),"rate":len(affected)/len(complete_map)}
    env={"support_is_marginal_descriptive":True,"predictors":{}}
    response_envelopes={p:(min(float(x[p]) for x in response_cells if x.get(p)!=""),max(float(x[p]) for x in response_cells if x.get(p)!="")) for p in CONTINUOUS}
    for p in CONTINUOUS:
        c=[float(r[p]) for r in canonical if r.get(p)!=""]; rc=[float(r[p]) for r in response_cells if r.get(p)!=""]; lo,hi=response_envelopes[p]
        env["predictors"][p]={"canonical_nonmissing":len(c),"response_cell_nonmissing":len(rc),"canonical_range":{"min":min(c),"max":max(c)},"response_cell_quantiles":{"q01":_percentile(rc,.01),"q05":_percentile(rc,.05),"q25":_percentile(rc,.25),"q50":_percentile(rc,.5),"q75":_percentile(rc,.75),"q95":_percentile(rc,.95),"q99":_percentile(rc,.99)},"canonical_below_response_min":sum(v<lo for v in c),"canonical_above_response_max":sum(v>hi for v in c),"interpretation":"marginal envelope only; not multivariate novelty or fitted transformation"}
    env["pooled_complete_map_cells_outside_any_response_envelope"]=sum((r.get("predictor_complete")=="true") and any(float(r[p]) < response_envelopes[p][0] or float(r[p]) > response_envelopes[p][1] for p in CONTINUOUS) for r in canonical)
    env["per_species"]= {}
    for species in DOWNSTREAM_SPECIES:
        srows=[x for x in response if x.get("species_id")==species]; scells={x["grid_cell_id"] for x in srows}; vals={p:[float(bykey[k][p]) for k in scells if bykey[k].get(p)!=""] for p in CONTINUOUS}; ranges={p:(min(v),max(v)) for p,v in vals.items() if v}
        affected=sum(r.get("predictor_complete")=="true" and any(float(r[p])<ranges[p][0] or float(r[p])>ranges[p][1] for p in ranges) for r in canonical)
        env["per_species"][species]={"response_cells":len(scells),"complete_map_cells_denominator":sum(r.get("predictor_complete")=="true" for r in canonical),"complete_map_cells_outside_any_marginal_envelope":affected,"rate":affected/max(1,sum(r.get("predictor_complete")=="true" for r in canonical)),"interpretation":"descriptive prepartition optimistic marginal envelope; forbidden as final fold support mask"}
    complete_resp=[r for r in response if bykey[r["grid_cell_id"]].get("predictor_complete")=="true"]
    policy={"complete_case_sensitivity":{"rows":len(complete_resp),"loss":len(response)-len(complete_resp),"loss_rate":(len(response)-len(complete_resp))/len(response)},"options":{}}
    for p in ACTIVE:
        miss=sum(bykey[r["grid_cell_id"]].get(p,"")=="" for r in response)
        keep=tuple(q for q in ACTIVE if q != p)
        map_complete=sum(all(r.get(q,"")!="" for q in keep) for r in canonical); cell_complete=sum(all(r.get(q,"")!="" for q in keep) for r in response_cells); row_complete=sum(all(bykey[r["grid_cell_id"]].get(q,"")!="" for q in keep) for r in response)
        policy["options"][p]={"single_predictor_recovery_rows":miss,"single_predictor_recovery_rate":miss/len(response),"if_drop_predictor":{"canonical_cells_retained":map_complete,"response_cells_retained":cell_complete,"response_rows_retained":row_complete,"response_rows_recovered_vs_whole_stack":row_complete-len(complete_resp)},"action":"repair_or_drop_candidate_only; no action applied"}
    policy["complete_case_losses"]={"by_pa_type":{p:{"rows":sum(r.get("pa_type")==p for r in response),"complete_case_rows":sum(r.get("pa_type")==p and bykey[r["grid_cell_id"]].get("predictor_complete")=="true" for r in response),"loss":sum(r.get("pa_type")==p and bykey[r["grid_cell_id"]].get("predictor_complete")!="true" for r in response)} for p in sorted({r.get("pa_type") for r in response})},"by_species":{s:{"rows":sum(r.get("species_id")==s for r in response),"complete_case_rows":sum(r.get("species_id")==s and bykey[r["grid_cell_id"]].get("predictor_complete")=="true" for r in response),"loss":sum(r.get("species_id")==s and bykey[r["grid_cell_id"]].get("predictor_complete")!="true" for r in response)} for s in sorted({r.get("species_id") for r in response})}}
    for name, dropped in {"shared_six":("elevation","top_roughness","soil_class","dist_fw","dist_road","fpar")}.items():
        keep=tuple(q for q in ACTIVE if q not in dropped)
        policy["options"][name]={"dropped_predictors":list(dropped),"if_drop_predictor":{"canonical_cells_retained":sum(all(r.get(q,"")!="" for q in keep) for r in canonical),"response_cells_retained":sum(all(r.get(q,"")!="" for q in keep) for r in response_cells),"response_rows_retained":sum(all(bykey[r["grid_cell_id"]].get(q,"")!="" for q in keep) for r in response)}}
    policy["policy_families"]={"A_source_repair":{"consequence":"recover missing values if native source/build metadata support it; currently unverified"},"B_supported_domain_restriction":{"consequence":"restrict prediction cells to supported domain; exact threshold pending Barry"},"C_predictor_revision":{"consequence":"drop/revise unsupported predictors; assess class/species losses above"},"D_training_only_type_specific_missing_treatment":{"consequence":"retain cells and defer type-specific treatment to training only; no imputation now"}}
    policy["provisional_ranking"]= ["A_source_repair","B_supported_domain_restriction","D_training_only_type_specific_missing_treatment","C_predictor_revision"]
    scope={"immutable_acquisition_candidates":list(ALL_CANDIDATE_SPECIES),"downstream_analysis_species":list(DOWNSTREAM_SPECIES),"excluded_downstream":"macropus_giganteus","historical_acquisition_provenance_unchanged":True}
    return {"source_metadata":source,"missingness_patterns":missing_patterns,"response_impact":response_impact,"categorical_support":cat,"environmental_support":env,"policy_options":policy,"analysis_scope":scope,"review":{"goal_id":GOAL_ID,"decision_readiness":"diagnostic_complete_decision_pending","barry_decisions_pending":["prediction target domain","authority for targeted source-repair exception","fallback treatment if full-domain prediction is required"],"downstream_scope_status":"Goal019 eight-species overlay is resolved and bound; nine-candidate acquisition history is preserved; no bundle rewrite","privacy":PLAN_PRIVACY,"stopped_before":STOPPED_BEFORE,"provisional_recommendation":"source audit/repair first; supported-domain restriction is the clearest fallback; later type-specific training-only treatment remains available; predictor revision follows ecological and held-out evidence","uncertainty":["native source metadata/build/nodata causes unavailable","workbook labels are reference lineage only","environmental support is marginal"]}}

def assert_evidence_privacy(value: Any) -> None:
    forbidden=("grid_cell_id","centroid","coordinate","row_payload","private_path","site_id","camera_id","deployment","timing","nearest_target")
    def walk(x: Any):
        if isinstance(x, Mapping):
            for k,v in x.items():
                kl=str(k).lower()
                if any(t in kl for t in forbidden) and not kl.startswith("tracked_"): raise PredictorSupportError("tracked_evidence_privacy_failure")
                if isinstance(v,str) and (v.startswith("/Users/") or re.fullmatch(r"g_-?\d+_-?\d+",v)): raise PredictorSupportError("tracked_evidence_privacy_failure")
                walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(value)

def validate_plan(plan: Mapping[str,Any]) -> dict[str,Any]:
    if plan.get("schema_version")!="1.0" or plan.get("goal_id")!=GOAL_ID: raise PredictorSupportError("plan_identity_drift")
    if plan.get("privacy")!=PLAN_PRIVACY or plan.get("stopped_before")!=STOPPED_BEFORE: raise PredictorSupportError("plan_privacy_or_stop_drift")
    b = {k:(v.get("path"),v.get("sha256")) for k,v in plan.get("bindings",{}).items()}
    if b != EXPECTED_PLAN_BINDINGS: raise PredictorSupportError("plan_binding_drift")
    if tuple(plan.get("active_predictors",())) != ACTIVE or tuple(plan.get("categorical_predictors",())) != CATEGORICAL: raise PredictorSupportError("predictor_contract_drift")
    if plan.get("canonical_cells") != CANONICAL_ROWS or plan.get("response_cells") != RESPONSE_CELLS or plan.get("response_rows") != RESPONSE_ROWS: raise PredictorSupportError("row_oracle_drift")
    if plan.get("outputs",{}).get("destination") != "evidence/predictor_support_diagnostics/2026-07-26" or plan.get("outputs",{}).get("tracked") != [*EVIDENCE_FILES,"manifest.json"] or plan.get("outputs",{}).get("private_row_products") is not False: raise PredictorSupportError("output_contract_drift")
    return {"goal_id":GOAL_ID}

def _validate_semantics(payloads: Mapping[str, Any]) -> None:
    """Strict tracked-only checks: tampered values cannot be rescued by hashes."""
    if set(payloads) != {n[:-5] for n in EVIDENCE_FILES}: raise PredictorSupportError("tracked_payload_key_drift")
    s=payloads["source_metadata"]
    expected_stack={"canonical_cells":CANONICAL_ROWS,"response_cells":RESPONSE_CELLS,"active_predictors":list(ACTIVE),"categorical_predictors":list(CATEGORICAL),"geometry":{"crs":"EPSG:4326","width":468,"height":455,"bands":32,"alignment":"exact centre indexing"}}
    bindings=s.get("bindings")
    if s.get("goal_id") != GOAL_ID or s.get("verified_stack") != expected_stack or s.get("privacy") != PLAN_PRIVACY or not isinstance(bindings,Mapping) or set(bindings) != set(SOURCE_BINDING_ROLES): raise PredictorSupportError("source_metadata_semantic_drift")
    plan_by_path={path: digest for path,digest in EXPECTED_PLAN_BINDINGS.values()}
    for record in bindings.values():
        if not isinstance(record,Mapping) or set(record) != {"path","sha256"}: raise PredictorSupportError("source_metadata_semantic_drift")
        try: path=_safe_relative(record["path"])
        except PredictorSupportError: raise PredictorSupportError("source_metadata_semantic_drift")
        digest=record["sha256"]
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest) or (str(path) in plan_by_path and plan_by_path[str(path)] != digest): raise PredictorSupportError("source_metadata_semantic_drift")
    m=payloads["missingness_patterns"]
    for key,n in (("canonical",CANONICAL_ROWS),("response_cells",RESPONSE_CELLS),("response_rows",RESPONSE_ROWS)):
        if m.get(key,{}).get("rows") != n: raise PredictorSupportError("missingness_semantic_drift")
        dist=m[key].get("missing_count_distribution",{});
        if sum(int(v) for v in dist.values()) != n: raise PredictorSupportError("missingness_arithmetic_drift")
    edge=m.get("edge_support",{})
    incomplete=CANONICAL_ROWS-int(m["canonical"]["missing_count_distribution"].get("0",0))
    et,nt=edge.get("canonical_edge_cells"),edge.get("canonical_nonedge_cells"); ie,ine=edge.get("incomplete_edge_cells"),edge.get("incomplete_nonedge_cells")
    if any(not isinstance(x,int) or x<0 for x in (et,nt,ie,ine)) or et+nt != CANONICAL_ROWS or ie+ine != incomplete or ie>et or ine>nt: raise PredictorSupportError("edge_arithmetic_drift")
    comp=m.get("rook_adjacency",{}); sizes=comp.get("connected_component_size_distribution",{})
    if comp.get("missing_cell_count") != incomplete or any(int(k)<=0 or int(v)<0 for k,v in sizes.items()) or sum(int(k)*int(v) for k,v in sizes.items()) != comp.get("missing_cell_count") or sum(int(v) for v in sizes.values()) != comp.get("connected_component_count"): raise PredictorSupportError("component_arithmetic_drift")
    bands=edge.get("incomplete_distance_bands",{})
    if set(bands) != {"edge","1-10",">10","unresolved"} or any(not isinstance(v,int) or v<0 for v in bands.values()) or sum(int(v) for v in bands.values()) != incomplete or bands.get("unresolved",0) != 0 or bands.get("edge") != ie or bands.get("1-10",0)+bands.get(">10",0) != ine: raise PredictorSupportError("edge_distance_arithmetic_drift")
    def close(actual, expected):
        return isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(float(actual)) and math.isclose(float(actual),float(expected),rel_tol=1e-12,abs_tol=1e-12)
    er, nr = ie/et if et else 0.0, ine/nt if nt else 0.0
    if not close(edge.get("incomplete_rate_edge"),er) or not close(edge.get("incomplete_rate_nonedge"),nr) or not close(edge.get("risk_ratio_edge_vs_nonedge"),er/nr) or not close(edge.get("odds_ratio_edge_vs_nonedge"),(er/(1-er))/(nr/(1-nr))): raise PredictorSupportError("edge_rate_arithmetic_drift")
    ri=payloads["response_impact"]
    if ri.get("rows") != RESPONSE_ROWS or ri.get("complete",0)+ri.get("incomplete",0) != RESPONSE_ROWS: raise PredictorSupportError("response_impact_semantic_drift")
    if set(ri.get("by_species_complete",{})) != set(DOWNSTREAM_SPECIES) or set(ri.get("by_pa_type_complete",{})) != set(PA_TYPES): raise PredictorSupportError("response_group_semantic_drift")
    species, pa = ri["by_species_complete"], ri["by_pa_type_complete"]
    for tab,err in ((species,"response_species_arithmetic_drift"),(pa,"response_pa_arithmetic_drift")):
        if any(not isinstance(v,Mapping) or any(not isinstance(v.get(k),int) or v.get(k)<0 for k in ("rows","complete","incomplete")) or v["rows"] != v["complete"]+v["incomplete"] or not close(v.get("loss_rate"),v["incomplete"]/v["rows"]) for v in tab.values()): raise PredictorSupportError(err)
    if sum(v["rows"] for v in species.values()) != RESPONSE_ROWS or sum(v["complete"] for v in species.values()) != ri["complete"] or sum(v["incomplete"] for v in species.values()) != ri["incomplete"] or sum(v["rows"] for v in pa.values()) != RESPONSE_ROWS or sum(v["complete"] for v in pa.values()) != ri["complete"] or sum(v["incomplete"] for v in pa.values()) != ri["incomplete"]: raise PredictorSupportError("response_group_arithmetic_drift")
    if set(ri.get("by_species",{})) != {"species_id"} or set(ri["by_species"]["species_id"]) != set(DOWNSTREAM_SPECIES) or sum(ri["by_species"]["species_id"].values()) != RESPONSE_ROWS or set(ri.get("by_pa_type",{})) != {"pa_type"} or set(ri["by_pa_type"]["pa_type"]) != set(PA_TYPES) or sum(ri["by_pa_type"]["pa_type"].values()) != RESPONSE_ROWS: raise PredictorSupportError("response_group_semantic_drift")
    for field,expected in (("by_response_origin",set(RESPONSE_ORIGINS)),("by_source_combination",set(SOURCE_COMBINATIONS))):
        groups=ri.get(field,{})
        if set(groups) != expected or sum(v.get("rows",0) for v in groups.values()) != RESPONSE_ROWS or sum(v.get("complete",0) for v in groups.values()) != ri["complete"] or sum(v.get("incomplete",0) for v in groups.values()) != ri["incomplete"] or any(v.get("rows",0) != v.get("complete",0)+v.get("incomplete",0) for v in groups.values()): raise PredictorSupportError("response_group_arithmetic_drift")
    for field in ("species_x_pa_type","species_x_source_combination","pa_type_x_source_combination"):
        tabs=ri.get("material_intersections",{}).get(field,{})
        if not tabs or sum(v.get("rows",0) for v in tabs.values()) != RESPONSE_ROWS or sum(v.get("complete",0) for v in tabs.values()) != ri["complete"] or sum(v.get("incomplete",0) for v in tabs.values()) != ri["incomplete"] or any(v.get("rows",0) != v.get("complete",0)+v.get("incomplete",0) for v in tabs.values()): raise PredictorSupportError("response_intersection_arithmetic_drift")
        left,right={"species_x_pa_type":("species", "pa"),"species_x_source_combination":("species", "source"),"pa_type_x_source_combination":("pa", "source")}[field]
        lefttab=species if left=="species" else pa; righttab=pa if right=="pa" else ri["by_source_combination"]
        for group in ("rows","complete","incomplete"):
            for key,tab in lefttab.items():
                if sum(v.get(group,0) for k,v in tabs.items() if k.split("|",1)[0]==key) != tab[group]: raise PredictorSupportError("response_intersection_marginal_drift")
            for key,tab in righttab.items():
                if sum(v.get(group,0) for k,v in tabs.items() if k.split("|",1)[1]==key) != tab[group]: raise PredictorSupportError("response_intersection_marginal_drift")
    cat=payloads["categorical_support"].get("variables",{})
    if set(cat) != set(CATEGORICAL): raise PredictorSupportError("categorical_semantic_drift")
    den=int(m["canonical"]["missing_count_distribution"].get("0",0))
    for p,v in cat.items():
        if any(int(x)<0 for x in v.get("canonical_cell_counts",{}).values()): raise PredictorSupportError("categorical_count_drift")
        if not set(v.get("sparse_response_codes",())).issubset(set(v.get("response_cell_counts",{}))): raise PredictorSupportError("categorical_sparse_drift")
    percat=payloads["categorical_support"].get("per_species",{})
    if set(percat) != set(DOWNSTREAM_SPECIES): raise PredictorSupportError("categorical_species_semantic_drift")
    for species,v in percat.items():
        if set(v.get("variables",{})) != set(CATEGORICAL) or v.get("denominator_complete_map_cells") != den or v.get("affected_complete_map_cells_any_unseen_level",0)>den or not close(v.get("rate"),v.get("affected_complete_map_cells_any_unseen_level",0)/den): raise PredictorSupportError("categorical_species_arithmetic_drift")
        for p,d in v["variables"].items():
            if set(d) != {"response_cell_codes","map_codes_absent_from_species_response","affected_complete_map_cells","denominator_complete_map_cells","rate"} or d["denominator_complete_map_cells"] != den or d["affected_complete_map_cells"]>den or not close(d["rate"],d["affected_complete_map_cells"]/den) or sorted(set(d["response_cell_codes"])) != d["response_cell_codes"] or sorted(set(d["map_codes_absent_from_species_response"])) != d["map_codes_absent_from_species_response"]: raise PredictorSupportError("categorical_species_arithmetic_drift")
    pooled_cat=payloads["categorical_support"]; pooled_n=pooled_cat.get("pooled_unseen_codes_in_fully_complete_map_cells",-1); pooled_by=pooled_cat.get("pooled_unseen_complete_cells_by_variable",{})
    if not isinstance(pooled_n,int) or pooled_n<0 or pooled_n>den or set(pooled_by)!=set(CATEGORICAL) or any(not isinstance(x,int) or x<0 or x>den for x in pooled_by.values()): raise PredictorSupportError("categorical_pooled_bounds_drift")
    absent_vars=[p for p,v in cat.items() if v.get("absent_in_response_cells")]
    if len(absent_vars)==1 and pooled_n != pooled_by[absent_vars[0]]: raise PredictorSupportError("categorical_pooled_arithmetic_drift")
    env=payloads["environmental_support"].get("predictors",{})
    if set(env) != set(CONTINUOUS): raise PredictorSupportError("environmental_predictor_drift")
    for p,v in env.items():
        if v.get("canonical_nonmissing",0)<0 or v.get("response_cell_nonmissing",0)<=0 or v.get("canonical_below_response_min",0)+v.get("canonical_above_response_max",0) > v.get("canonical_nonmissing",0): raise PredictorSupportError("environmental_envelope_drift")
        q=v.get("response_cell_quantiles",{}); order=("q01","q05","q25","q50","q75","q95","q99")
        if set(q) != set(order) or any(not isinstance(q[k],(int,float)) or not math.isfinite(float(q[k])) for k in order) or any(q[a]>q[b] for a,b in zip(order,order[1:])): raise PredictorSupportError("environmental_envelope_drift")
    den=int(m["canonical"]["missing_count_distribution"].get("0",0))
    envspecies=payloads["environmental_support"].get("per_species",{})
    if set(envspecies) != set(DOWNSTREAM_SPECIES): raise PredictorSupportError("environmental_species_semantic_drift")
    for species,v in envspecies.items():
        if v.get("complete_map_cells_outside_any_marginal_envelope",0)>v.get("complete_map_cells_denominator",0) or v.get("complete_map_cells_denominator") != den or not close(v.get("rate"),v.get("complete_map_cells_outside_any_marginal_envelope",0)/den): raise PredictorSupportError("environmental_species_arithmetic_drift")
    pooled_env=payloads["environmental_support"].get("pooled_complete_map_cells_outside_any_response_envelope",-1)
    max_marginal=max((v.get("canonical_below_response_min",0)+v.get("canonical_above_response_max",0) for v in env.values()),default=0)
    if not isinstance(pooled_env,int) or pooled_env<max_marginal or pooled_env>den: raise PredictorSupportError("environmental_pooled_bounds_drift")
    pol=payloads["policy_options"]
    if set(pol.get("policy_families",{})) != {"A_source_repair","B_supported_domain_restriction","C_predictor_revision","D_training_only_type_specific_missing_treatment"}: raise PredictorSupportError("policy_family_drift")
    if pol.get("provisional_ranking") != ["A_source_repair","B_supported_domain_restriction","D_training_only_type_specific_missing_treatment","C_predictor_revision"]: raise PredictorSupportError("policy_ranking_drift")
    cc=pol.get("complete_case_sensitivity",{}); whole=cc.get("rows",0)
    if whole + cc.get("loss",0) != RESPONSE_ROWS or abs(cc.get("loss_rate",0)-cc.get("loss",0)/RESPONSE_ROWS)>1e-12: raise PredictorSupportError("policy_complete_case_arithmetic_drift")
    if set(pol.get("options",{})) != set(ACTIVE)|{"shared_six"}: raise PredictorSupportError("policy_option_set_drift")
    for name,opt in pol.get("options",{}).items():
        if "if_drop_predictor" in opt:
            d=opt["if_drop_predictor"]
            if d.get("canonical_cells_retained",0)>CANONICAL_ROWS or d.get("response_cells_retained",0)>RESPONSE_CELLS or d.get("response_rows_retained",0)>RESPONSE_ROWS or d.get("canonical_cells_retained",0)<den or d.get("response_cells_retained",0)<RESPONSE_CELLS-int(m["response_cells"]["missing_count_distribution"].get("0",0)) or d.get("response_rows_retained",0)<whole: raise PredictorSupportError("policy_retained_bounds_drift")
            if "response_rows_recovered_vs_whole_stack" in d and d["response_rows_recovered_vs_whole_stack"] != d.get("response_rows_retained",0)-whole: raise PredictorSupportError("policy_recovery_arithmetic_drift")
    for p in ACTIVE:
        opt=pol["options"][p]; recovery=opt.get("single_predictor_recovery_rows")
        if not isinstance(recovery,int) or recovery<0 or recovery>RESPONSE_ROWS or not close(opt.get("single_predictor_recovery_rate"),recovery/RESPONSE_ROWS): raise PredictorSupportError("policy_single_recovery_drift")
    if pol["options"]["shared_six"].get("dropped_predictors") != list(SHARED_SIX): raise PredictorSupportError("policy_shared_drop_drift")
    scope=payloads["analysis_scope"]
    if tuple(scope.get("downstream_analysis_species",())) != DOWNSTREAM_SPECIES or scope.get("excluded_downstream") != "macropus_giganteus" or set(scope.get("immutable_acquisition_candidates",())) != set(ALL_CANDIDATE_SPECIES) or len(scope.get("immutable_acquisition_candidates",())) != 9 or scope.get("historical_acquisition_provenance_unchanged") is not True: raise PredictorSupportError("analysis_scope_drift")
    review=payloads["review"]
    if review.get("goal_id") != GOAL_ID or review.get("decision_readiness") != "diagnostic_complete_decision_pending" or review.get("barry_decisions_pending") != PENDING_DECISIONS or review.get("privacy") != PLAN_PRIVACY or review.get("stopped_before") != STOPPED_BEFORE: raise PredictorSupportError("review_semantic_drift")

def _expected_manifest(evidence: Path) -> dict[str,Any]:
    return {"schema_version":"1.0","files":[{"path":n,"bytes":(evidence/n).stat().st_size,"sha256":sha256(evidence/n)} for n in EVIDENCE_FILES]}

def validate_evidence(plan_path: Path, evidence_dir: Path, *, full: bool=False, root: Path|None=None) -> dict[str,Any]:
    plan=json.loads(plan_path.read_text()); validate_plan(plan)
    entries=list(evidence_dir.iterdir())
    if {p.name for p in entries} != set(EVIDENCE_FILES)|{"manifest.json"} or any(not p.is_file() or p.is_symlink() for p in entries): raise PredictorSupportError("evidence_footprint_drift")
    manifest=json.loads((evidence_dir/"manifest.json").read_text()); expected=_expected_manifest(evidence_dir)
    if manifest!=expected: raise PredictorSupportError("manifest_drift")
    payloads={n[:-5]:json.loads((evidence_dir/n).read_text()) for n in EVIDENCE_FILES}
    for p in payloads.values(): assert_evidence_privacy(p)
    _validate_semantics(payloads)
    if full:
        if root is None: root=plan_path.parents[1]
        # Upstream validators are invoked when their private inputs are available.
        try:
            from dsdm_phase1.pseudoabsence_derivation import validate_evidence as v021
            v021(root/"config/pseudoabsence_derivation_plan.json", root/"evidence/pseudoabsence_derivation/2026-07-26", full=True, output_dir=root/"data/processed/response/goal021-pseudoabsence-derivation/2026-07-26")
        except Exception as exc:
            raise PredictorSupportError("goal021_replay_failure") from exc
        try:
            from dsdm_phase1.predictor_stack_extraction import validate_evidence as v022
            v022(root/"config/predictor_stack_extraction_plan.json", root/PREDICTOR_EVIDENCE, full=True, output_dir=root/PREDICTOR_OUTPUT)
        except Exception as exc:
            raise PredictorSupportError("upstream_validation_failure") from exc
        actual=compute_diagnostics(root,plan)
        if actual!=payloads: raise PredictorSupportError("full_replay_failure")
    return {"tracked_valid":True,"full_replay":bool(full)}

def _publish(staging: Path, output: Path, *, fail_guard: bool=True) -> None:
    if output.exists() and fail_guard: raise PredictorSupportError("publication_destination_exists")
    staging.rename(output)

def run_production(root: Path) -> dict[str,Any]:
    plan_path=root/"config/predictor_support_diagnostic_plan.json"; plan=json.loads(plan_path.read_text()); validate_plan(plan)
    evidence=root/"evidence/predictor_support_diagnostics"/DATE
    if evidence.exists(): raise PredictorSupportError("publication_destination_exists")
    payloads=compute_diagnostics(root,plan)
    for payload in payloads.values(): assert_evidence_privacy(payload)
    _validate_semantics(payloads)
    evidence.parent.mkdir(parents=True,exist_ok=True); staging=Path(tempfile.mkdtemp(prefix="goal023-stage-",dir=evidence.parent)); se=staging/DATE; se.mkdir()
    try:
        for k,v in payloads.items(): (se/(k+".json")).write_text(json.dumps(v,sort_keys=True,indent=2)+"\n")
        (se/"manifest.json").write_text(json.dumps(_expected_manifest(se),sort_keys=True,indent=2)+"\n")
        _publish(se,evidence)
    finally: shutil.rmtree(staging,ignore_errors=True)
    return {"evidence":str(evidence),"files":len(EVIDENCE_FILES)+1}

# Stable descriptive aliases for focused downstream checks.
compute_missingness_patterns = missing_pattern
compute_rook_components = rook_components
parse_xlsx_reference = parse_workbook_reference
build_diagnostics = compute_diagnostics

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2]); ap.add_argument("--validate",action="store_true"); a=ap.parse_args(); print(validate_evidence(a.root/"config/predictor_support_diagnostic_plan.json",a.root/"evidence/predictor_support_diagnostics"/DATE,full=True,root=a.root) if a.validate else run_production(a.root))
