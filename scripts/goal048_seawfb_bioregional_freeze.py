"""Count-free freezes and one aggregate canary for Goal 048."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import galah
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import covers, make_valid, points, union_all

from dsdm_phase1.goal040_domain import _reconcile_selector


class Goal048Error(RuntimeError):
    pass


def _require_galah_overlay() -> None:
    if galah.__version__ != "0.13.6":
        raise Goal048Error("Goal048 live stages require galah-python==0.13.6 via an explicit uv --with overlay")


REGIONS = ["AUA", "BBS", "KAN", "NAN", "NCP", "NET", "NNC", "NSS", "SCP", "SEC", "SEH", "SEQ", "SVP", "SYB", "VIM"]
NATIVE_WOODY = set(range(1, 19)) | {23, 31, 32}
NON_WOODY = {19, 20, 21, 25, 27}
MISSING_NVIS = {22, 24, 26, 28, 29, 99}
EFFORT_EXCLUDED = {"Spilopelia chinensis", "Fulica atra", "Ceyx azureus", "Haliaeetus leucogaster"}
STATIC_EXCLUDED = EFFORT_EXCLUDED | {
    "Accipiter fasciatus", "Aquila audax", "Anthochaera phrygia", "Cacatua sanguinea",
    "Cacatua tenuirostris", "Calamanthus fuliginosus", "Calyptorhynchus lathami",
    "Circus approximans", "Corvus coronoides", "Corvus mellori", "Corvus tasmanicus",
    "Eolophus roseicapilla", "Falco longipennis", "Glossopsitta concinna",
    "Gymnorhina tibicen", "Heteroscenes pallidus", "Hieraaetus morphnoides",
    "Hirundo neoxena", "Lathamus discolor", "Neophema chrysostoma",
    "Pezoporus wallicus", "Petrochelidon nigricans", "Podargus strigoides",
    "Trichoglossus moluccanus", "Vanellus miles",
}
SEASONAL = {"Cacomantis flabelliformis", "Chalcites lucidus", "Coracina novaehollandiae", "Myiagra cyanoleuca", "Myzomela sanguinolenta", "Petroica phoenicea", "Zosterops lateralis"}
NOMADIC = {"Anthochaera phrygia", "Glossopsitta concinna", "Lathamus discolor"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _get_json(url: str) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "dSDM-Goal048/1.1"})
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read())


def _private(root: Path) -> Path:
    return root / "data/processed/dsdm/goal048-seawfb-bioregional-freeze"


def _nvis_freeze(root: Path) -> dict[str, Any]:
    source = json.loads((root / "metadata/goal041_source_manifest.json").read_text())["sources"]["nvis"]
    labels = [
        "Rainforests and Vine Thickets", "Eucalypt Tall Open Forests", "Eucalypt Open Forests",
        "Eucalypt Low Open Forests", "Eucalypt Woodlands", "Acacia Forests and Woodlands",
        "Callitris Forests and Woodlands", "Casuarina Forests and Woodlands", "Melaleuca Forests and Woodlands",
        "Other Forests and Woodlands", "Eucalypt Open Woodlands", "Tropical Eucalypt Woodlands/Grasslands",
        "Acacia Open Woodlands", "Mallee Woodlands and Shrublands", "Low Closed Forests and Tall Closed Shrublands",
        "Acacia Shrublands", "Other Shrublands", "Heathlands", "Tussock Grasslands", "Hummock Grasslands",
        "Other Grasslands, Herblands, Sedgelands and Rushlands", "Chenopod Shrublands, Samphire Shrublands and Forblands",
        "Mangroves", "Inland Aquatic - freshwater, salt lakes, lagoons", "Cleared, non-native vegetation, buildings",
        "Unclassified native vegetation", "Naturally bare - sand, rock, claypan, mudflat", "Sea and Estuaries",
        "Regrowth, modified native vegetation", "Unknown/no data", "Plantations", "Native Forest not otherwise classified",
    ]
    rows = []
    for code, label in enumerate(labels, 1):
        cls = "native_woody" if code in NATIVE_WOODY else "non_woody" if code in NON_WOODY else "missing"
        rows.append({"code": code, "label": label, "class": cls})
    rows.append({"code": 99, "label": "Unknown/no data sentinel", "class": "missing"})
    receipt = {
        "status": "frozen_count_free", "source_archive_sha256": source["official_zip_sha256"],
        "derived_raster_sha256": source["derived_geotiff_sha256"], "rows": rows,
        "missing_codes": sorted(MISSING_NVIS), "mapping_sha256": _digest(rows),
    }
    _write(_private(root) / "nvis_freeze.json", receipt)
    return receipt


def _role_freeze(config: dict[str, Any], root: Path) -> dict[str, Any]:
    rows = []
    for name in config["species_universes"]["ecological_candidate_names"]:
        effort = name not in EFFORT_EXCLUDED
        static = name not in STATIC_EXCLUDED
        season = "strongly_nomadic_or_irruptive" if name in NOMADIC else "regular_seasonal" if name in SEASONAL else "resident_or_local_movement"
        reason = "eligible_native_terrestrial_seed"
        if name in EFFORT_EXCLUDED:
            reason = "introduced_or_obligate_aquatic_scale_mismatch"
        elif not static:
            reason = "static_pooled_suitability_or_detection_scale_mismatch"
        rows.append({"name": name, "effort": effort, "auxiliary": static, "target": static, "seasonality": season, "reason": reason})
    receipt = {
        "status": "frozen_response_blind", "authority": ["Goal048 accepted ecological rules", "BirdLife Australia species ecology review"],
        "rows": rows, "row_count": len(rows), "mapping_sha256": _digest(rows),
        "role_counts": {role: sum(bool(row[role]) for row in rows) for role in ("effort", "auxiliary", "target")},
    }
    _write(_private(root) / "role_freeze.json", receipt)
    return receipt


def _taxonomy_one(name: str) -> dict[str, Any]:
    match = galah.search_taxa(taxa=name)
    if len(match) != 1:
        raise Goal048Error(f"taxonomy match is not unique: {name}")
    row = match.iloc[0].to_dict()
    parent = str(row.get("taxonConceptID") or row.get("guid") or row.get("Species") or "")
    accepted = str(row.get("scientificName") or row.get("Species Name") or name)
    if not parent:
        raise Goal048Error(f"taxonomy match lacks identifier: {name}")
    detail = _get_json("https://bie-ws.ala.org.au/ws/species/" + quote(parent, safe=""))
    children = _get_json("https://bie.ala.org.au/ws/childConcepts/" + quote(parent, safe=""))
    descendants = []
    for child in children if isinstance(children, list) else []:
        if str(child.get("rank", "")).lower() == "subspecies":
            cid = str(child.get("guid") or child.get("taxonConceptID") or "")
            if cid:
                child_detail = _get_json("https://bie-ws.ala.org.au/ws/species/" + quote(cid, safe=""))
                concept = child_detail.get("taxonConcept", {})
                if str(concept.get("taxonomicStatus", "")).lower() != "accepted" or str(concept.get("parentGuid", parent)) != parent:
                    raise Goal048Error(f"subspecies does not round-trip to accepted parent: {cid}")
                descendants.append((str(child.get("name") or child.get("scientificName") or ""), cid))
    aliases = []
    for synonym in detail.get("synonyms", []) if isinstance(detail, dict) else []:
        if str(synonym.get("taxonomicStatus", "")).lower() != "synonym":
            continue
        alias_name = str(synonym.get("nameString") or synonym.get("name") or synonym.get("scientificName") or "")
        aid = str(synonym.get("guid") or synonym.get("nameGuid") or synonym.get("taxonConceptID") or "")
        if aid and "/" not in alias_name:
            aliases.append((alias_name, aid))
    descendants.sort()
    aliases.sort()
    identifiers = [parent] + [value for _, value in descendants] + [value for _, value in aliases]
    if len(identifiers) != len(set(identifiers)):
        raise Goal048Error(f"duplicate identifier within union: {name}")
    return {"seed_name": name, "accepted_name": accepted, "parent": parent, "descendants": descendants, "aliases": aliases, "ordered_identifiers": identifiers}


def _taxonomy_freeze(config: dict[str, Any], root: Path) -> dict[str, Any]:
    names = config["species_universes"]["ecological_candidate_names"]
    galah.galah_config(atlas="Australia", authenticate=False, verbose=False)
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(_taxonomy_one, names))
    parents = [row["parent"] for row in rows]
    all_ids = [identifier for row in rows for identifier in row["ordered_identifiers"]]
    if len(rows) != 100 or len(parents) != len(set(parents)) or len(all_ids) != len(set(all_ids)):
        raise Goal048Error("taxonomy global uniqueness failed")
    receipt = {
        "status": "frozen_count_free", "galah_version": galah.__version__, "species_count": len(rows),
        "parent_count": len(parents), "descendant_count": sum(len(r["descendants"]) for r in rows),
        "alias_count": sum(len(r["aliases"]) for r in rows), "rows": rows,
        "ledger_sha256": _digest(rows), "excluded_ambiguous_alias": "Trichoglossus moluccanus/rubritorquis",
    }
    _write(_private(root) / "taxonomy_freeze.json", receipt)
    return receipt


def _domain_freeze(root: Path) -> dict[str, Any]:
    ibra_path = root / "data/raw/goal040/domain/ibra7_1_subregions.geojson"
    state_path = root / "data/raw/goal040/domain/extracted/STE_2026_AUST_GDA2020.shp"
    old_cells_path = root / "data/raw/goal040/domain/eligible_cells.csv"
    ibra = gpd.read_file(ibra_path)
    if len(ibra) != 419 or ibra["REG_CODE_7"].nunique() != 89:
        raise Goal048Error("IBRA authority count drift")
    bbs_frame = ibra.loc[ibra["REG_CODE_7"] == "BBS"].to_crs(4326)
    if set(bbs_frame["SUB_CODE_7"]) - {"BBS01", "BBS02", "BBS03", "BBS04", "BBS05", "BBS06", "BBS07", "BBS08", "BBS09", "BBS10", "BBS11", "BBS12", "BBS13", "BBS14", "BBS15", "BBS16", "BBS17", "BBS18", "BBS19", "BBS20", "BBS21", "BBS22", "BBS23", "BBS24", "BBS25", "BBS26", "BBS27", "BBS28"}:
        raise Goal048Error("unexpected BBS subregion code")
    bbs = union_all(make_valid(bbs_frame.geometry.array))
    minx, miny, maxx, maxy = bbs.bounds
    water_dir = _private(root) / "domain_water"
    water_dir.mkdir(parents=True, exist_ok=True)
    layer = "https://hosting.wsapi.cloud.bom.gov.au/arcgis/rest/services/ahgf/Geofabric_V3x_All_Products/FeatureServer/27"
    ids_query = {"where": "ahgfftype IN (25,26)", "geometry": f"{minx},{miny},{maxx},{maxy}", "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true", "f": "json"}
    ids = sorted(_get_json(layer + "/query?" + urlencode(ids_query)).get("objectIds", []))
    water_geoms = []
    for start in range(0, len(ids), 1000):
        payload = _get_json(layer + "/query?" + urlencode({"objectIds": ",".join(map(str, ids[start:start+1000])), "outFields": "objectid,ahgfftype", "returnGeometry": "true", "outSR": "4326", "f": "geojson"}))
        cache = water_dir / f"features_{start//1000:04d}.json"
        _write(cache, payload)
        water_geoms.extend(gpd.GeoDataFrame.from_features(payload["features"], crs=4326).geometry)
    water = union_all(make_valid(np.asarray(water_geoms, dtype=object))) if water_geoms else shapely.GeometryCollection()
    states = gpd.read_file(state_path).to_crs(4326)
    selected, _, _ = _reconcile_selector(root, ibra_path)
    mainland_land = union_all(make_valid(states.loc[states["STE_CODE26"].astype(str).isin(["1", "2", "3", "4", "8"])].geometry.array))
    footprint = shapely.box(135.3700, -43.6325, 153.6300, -23.7725)
    old_domain = union_all(ibra.loc[ibra["SUB_CODE_7"].isin(selected)].geometry.array).intersection(mainland_land).intersection(footprint)
    screen = []
    for code in REGIONS + ["EYB"]:
        frame = ibra.loc[ibra["REG_CODE_7"] == code]
        region_land = union_all(frame.geometry.array).intersection(mainland_land)
        projected = gpd.GeoSeries([region_land, region_land.intersection(old_domain)], crs=4326).to_crs(3577)
        denominator = projected.iloc[0].area / 1e6
        numerator = projected.iloc[1].area / 1e6
        screen.append({"code": code, "name": str(frame["REG_NAME_7"].iloc[0]), "official_land_km2": round(denominator, 6), "goal040_overlap_km2": round(numerator, 6), "overlap_fraction": round(numerator / denominator, 12), "admitted": numerator / denominator >= 0.80})
    admitted = sorted(row["code"] for row in screen if row["admitted"])
    if admitted != REGIONS or [row["code"] for row in screen if not row["admitted"]] != ["EYB"]:
        raise Goal048Error("literal region overlap screen drift")
    land = union_all(make_valid(states.loc[~states["STE_CODE26"].isin(["7", "9"])].geometry.array))
    old = pd.read_csv(old_cells_path)
    old_ids = set(old["cell_id"])
    lon0, lat0 = 135.375, -43.6275
    c0, c1 = math.ceil((minx-lon0)/0.01), math.floor((maxx-lon0)/0.01)
    r0, r1 = math.ceil((miny-lat0)/0.01), math.floor((maxy-lat0)/0.01)
    new_rows = []
    shapely.prepare(bbs); shapely.prepare(land); shapely.prepare(water)
    for start in range(r0, r1 + 1, 50):
        stop = min(start + 50, r1 + 1)
        columns = np.arange(c0, c1 + 1)
        rows = np.arange(start, stop)
        cc = np.tile(columns, len(rows)); rr = np.repeat(rows, len(columns))
        lon = lon0 + cc * 0.01; lat = lat0 + rr * 0.01
        pts = points(lon, lat)
        keep = covers(bbs, pts) & covers(land, pts) & ~covers(water, pts)
        for i in np.flatnonzero(keep):
            cid = f"r{int(rr[i]):04d}c{int(cc[i]):04d}"
            if cid not in old_ids:
                new_rows.append((cid, int(rr[i]), int(cc[i]), float(lon[i]), float(lat[i])))
    combined = [(str(r.cell_id), int(r.row_south_to_north), int(r.column_west_to_east), float(r.longitude), float(r.latitude)) for r in old.itertuples()] + new_rows
    combined.sort()
    cells_path = _private(root) / "domain_cells.csv"
    pd.DataFrame(combined, columns=["cell_id", "row", "column", "longitude", "latitude"]).to_csv(cells_path, index=False)
    ids_digest = hashlib.sha256("".join(f"{row[0]}\n" for row in combined).encode()).hexdigest()
    receipt = {
        "status": "frozen_count_free", "region_codes": admitted, "region_count": len(admitted),
        "candidate_overlap_method": "IBRA7.1 whole-region official mainland ASGS land intersect Goal040 163-subregion union and exact 0.01-degree cell-footprint bbox; EPSG:3577 area",
        "candidate_overlap_threshold": 0.80, "candidate_overlap_screen": screen,
        "excluded_eyb_overlap_fraction": next(row["overlap_fraction"] for row in screen if row["code"] == "EYB"), "required_completion": ["BBS01", "BBS03", "BBS28"],
        "ibra_feature_count": 419, "ibra_region_count": 89, "ibra_sha256": _sha(ibra_path),
        "asgs_sha256": _sha(root / "data/raw/goal040/domain/STE_2026_AUST_SHP_GDA2020.zip"),
        "water_feature_count": len(ids), "old_cell_count": len(old), "added_complete_bbs_cells": len(new_rows),
        "cell_count": len(combined), "cell_id_sha256": ids_digest,
        "bbox": {"xmin": min(r[3] for r in combined), "xmax": max(r[3] for r in combined), "ymin": min(r[4] for r in combined), "ymax": max(r[4] for r in combined)},
        "private_cells_sha256": _sha(cells_path),
    }
    _write(_private(root) / "domain_freeze.json", receipt)
    return receipt


def compile_query(identifier_union: list[str], filters: list[str], group_by: str | None) -> dict[str, Any]:
    if not identifier_union or len(identifier_union) != len(set(identifier_union)):
        raise Goal048Error("identifier union empty or duplicated")
    if not all(any(f.startswith(prefix) for f in filters) for prefix in ("decimalLongitude>=", "decimalLongitude<=", "decimalLatitude>=", "decimalLatitude<=")):
        raise Goal048Error("query lacks explicit coordinate filters")
    return {"identifiers": identifier_union, "filters": filters, **({"group_by": group_by} if group_by else {})}


def freeze_prerequisites(root: Path) -> dict[str, Any]:
    _require_galah_overlay()
    config = json.loads((root / "config/goal048_seawfb_bioregional_freeze.json").read_text())
    receipts = {"domain": _domain_freeze(root), "taxonomy": _taxonomy_freeze(config, root), "roles": _role_freeze(config, root), "nvis": _nvis_freeze(root)}
    return _write_prerequisite_manifest(root, receipts)


def _write_prerequisite_manifest(root: Path, receipts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    paths = {name: _private(root) / f"{'role' if name == 'roles' else name}_freeze.json" for name in receipts}
    summary = {
        name: {
            "status": value["status"], "semantic_sha256": _digest(value),
            "private_receipt": str(paths[name].relative_to(root)), "private_receipt_sha256": _sha(paths[name]),
        }
        for name, value in receipts.items()
    }
    summary["domain"].update({"region_count": receipts["domain"]["region_count"], "cell_count": receipts["domain"]["cell_count"], "added_complete_bbs_cells": receipts["domain"]["added_complete_bbs_cells"], "excluded_eyb_overlap_fraction": receipts["domain"]["excluded_eyb_overlap_fraction"]})
    summary["taxonomy"].update({key: receipts["taxonomy"][key] for key in ("species_count", "parent_count", "descendant_count", "alias_count")})
    summary["roles"].update({"role_counts": receipts["roles"]["role_counts"], "excluded_target_count": sum(not row["target"] for row in receipts["roles"]["rows"])})
    summary["nvis"].update({"mapping_sha256": receipts["nvis"]["mapping_sha256"], "missing_codes": receipts["nvis"]["missing_codes"]})
    if any(value["status"] not in {"frozen_count_free", "frozen_response_blind"} for value in receipts.values()):
        raise Goal048Error("prerequisite freeze incomplete")
    summary["joint_sha256"] = _digest(summary)
    _write(root / "metadata/goal048_prerequisite_freeze.json", summary)
    return summary


def refresh_prerequisite_manifest(root: Path) -> dict[str, Any]:
    receipts = {name: json.loads((_private(root) / f"{'role' if name == 'roles' else name}_freeze.json").read_text()) for name in ("domain", "taxonomy", "roles", "nvis")}
    return _write_prerequisite_manifest(root, receipts)


def validate_freezes(root: Path) -> dict[str, Any]:
    manifest_path = root / "metadata/goal048_prerequisite_freeze.json"
    manifest = json.loads(manifest_path.read_text())
    for name in ("domain", "taxonomy", "roles", "nvis"):
        entry = manifest[name]
        path = root / entry["private_receipt"]
        value = json.loads(path.read_text())
        if _sha(path) != entry["private_receipt_sha256"] or _digest(value) != entry["semantic_sha256"]:
            raise Goal048Error(f"{name} receipt checksum drift")
        if value["status"] != entry["status"]:
            raise Goal048Error(f"{name} status drift")
    expected_joint = _digest({key: value for key, value in manifest.items() if key != "joint_sha256"})
    if manifest.get("joint_sha256") != expected_joint:
        raise Goal048Error("prerequisite joint checksum drift")
    domain = json.loads((root / manifest["domain"]["private_receipt"]).read_text())
    if _sha(_private(root) / "domain_cells.csv") != domain["private_cells_sha256"] or domain["cell_count"] != manifest["domain"]["cell_count"]:
        raise Goal048Error("domain cell ledger checksum or count drift")
    screen = domain.get("candidate_overlap_screen", [])
    admitted = sorted(row["code"] for row in screen if row["overlap_fraction"] >= domain.get("candidate_overlap_threshold", math.inf))
    excluded = sorted(row["code"] for row in screen if row["overlap_fraction"] < domain.get("candidate_overlap_threshold", math.inf))
    if len(screen) != 16 or admitted != REGIONS or excluded != ["EYB"] or domain["region_codes"] != admitted:
        raise Goal048Error("literal region overlap screen failed")
    taxonomy = json.loads((root / manifest["taxonomy"]["private_receipt"]).read_text())
    roles = json.loads((root / manifest["roles"]["private_receipt"]).read_text())
    nvis = json.loads((root / manifest["nvis"]["private_receipt"]).read_text())
    if (taxonomy["species_count"], taxonomy["parent_count"], taxonomy["descendant_count"], taxonomy["alias_count"]) != (100, 100, 247, 179):
        raise Goal048Error("taxonomy count invariants failed")
    if roles["row_count"] != 100 or set(roles["role_counts"]) != {"effort", "auxiliary", "target"}:
        raise Goal048Error("role count invariants failed")
    if {row["code"] for row in nvis["rows"]} != set(range(1, 33)) | {99}:
        raise Goal048Error("NVIS code completeness failed")
    return {"status": "validated_count_free", "receipt_count": 4, "joint_sha256": manifest["joint_sha256"]}


def run_canary(root: Path) -> dict[str, Any]:
    _require_galah_overlay()
    validate_freezes(root)
    prerequisite = json.loads((root / "metadata/goal048_prerequisite_freeze.json").read_text())
    taxonomy = json.loads((_private(root) / "taxonomy_freeze.json").read_text())
    domain = json.loads((_private(root) / "domain_freeze.json").read_text())
    taxon = next(row for row in taxonomy["rows"] if row["seed_name"] == "Acanthiza pusilla")
    box = domain["bbox"]
    filters = ["year>=2001", "year<=2025", "occurrenceStatus=PRESENT", "spatiallyValid=true", f"decimalLongitude>={box['xmin']}", f"decimalLongitude<={box['xmax']}", f"decimalLatitude>={box['ymin']}", f"decimalLatitude<={box['ymax']}"]
    total_query = compile_query(taxon["ordered_identifiers"], filters, None)
    facet_query = compile_query(taxon["ordered_identifiers"], filters, "lat_long")
    if total_query["identifiers"] != facet_query["identifiers"] or total_query["filters"] != facet_query["filters"]:
        raise Goal048Error("total/facet query identity mismatch")
    galah.galah_config(atlas="Australia", authenticate=False, verbose=False, timeout=600)
    start = time.monotonic()
    total_frame = galah.atlas_counts(**total_query)
    facet_frame = galah.atlas_counts(**facet_query)
    elapsed = time.monotonic() - start
    total = int(total_frame.iloc[0]["totalRecords"])
    if set(facet_frame.columns) != {"lat_long", "count"} or facet_frame["lat_long"].isna().any():
        raise Goal048Error("lat_long facet unavailable, malformed, or missing coordinate")
    if int(facet_frame["count"].sum()) != total:
        raise Goal048Error("lat_long facet sum does not conserve total")
    if len(facet_frame) > 750_000:
        raise Goal048Error("per-taxon facet-group ceiling exceeded")
    cells = pd.read_csv(_private(root) / "domain_cells.csv")
    allowed = set(zip(cells["row"].astype(int), cells["column"].astype(int)))
    retained = set()
    for value in facet_frame["lat_long"].astype(str):
        parts = value.replace("[", "").replace("]", "").split(",")
        if len(parts) != 2:
            raise Goal048Error("malformed lat_long facet label")
        lat, lon = map(float, parts)
        row = math.floor((lat - (-43.6325)) / 0.01)
        column = math.floor((lon - 135.37) / 0.01)
        if (row, column) in allowed:
            retained.add((row, column))
    private_receipt = {"species": "Acanthiza pusilla", "cells": sorted(f"r{r:04d}c{c:04d}" for r, c in retained)}
    _write(_private(root) / "canary_species_cells.json", private_receipt)
    disk = sum(path.stat().st_size for path in _private(root).rglob("*") if path.is_file())
    peak_ram = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    result = {
        "status": "passed" if disk <= 4_294_967_296 and peak_ram <= 8_589_934_592 else "failed_resource_ceiling",
        "species": "Acanthiza pusilla", "prerequisite_joint_sha256": prerequisite["joint_sha256"],
        "query_fingerprint": _digest({"identifiers": total_query["identifiers"], "filters": total_query["filters"]}),
        "identifier_count": len(total_query["identifiers"]), "total_count": total,
        "facet_count_sum": int(facet_frame["count"].sum()), "facet_group_count": len(facet_frame),
        "retained_species_cell_count": len(retained), "private_species_cell_sha256": _sha(_private(root) / "canary_species_cells.json"),
        "runtime_seconds": round(elapsed, 3), "peak_ram_bytes_upper_bound": peak_ram,
        "private_disk_bytes": disk, "full_100_seed_group_projection": len(facet_frame) * 100,
        "full_100_seed_projection_role": "planning_diagnostic_not_transport_gate",
        "count_conservation_sha256": _digest({"total_count": total, "facet_count_sum": int(facet_frame["count"].sum()), "facet_group_count": len(facet_frame)}),
        "occurrence_rows_downloaded": 0, "model_outcome_counter": 0,
    }
    _write(root / "evidence/seawfb_bioregional_freeze/goal048/aggregate_canary.json", result)
    return result


def validate(root: Path) -> dict[str, Any]:
    prerequisite = json.loads((root / "metadata/goal048_prerequisite_freeze.json").read_text())
    canary = json.loads((root / "evidence/seawfb_bioregional_freeze/goal048/aggregate_canary.json").read_text())
    expected_counts = _digest({"total_count": canary["total_count"], "facet_count_sum": canary["facet_count_sum"], "facet_group_count": canary["facet_group_count"]})
    if canary["prerequisite_joint_sha256"] != prerequisite["joint_sha256"] or canary["occurrence_rows_downloaded"] != 0 or canary["model_outcome_counter"] != 0:
        raise Goal048Error("canary provenance or forbidden-work counter failed")
    if canary["total_count"] != canary["facet_count_sum"] or canary["count_conservation_sha256"] != expected_counts:
        raise Goal048Error("canary count conservation failed")
    if canary["facet_group_count"] > 750_000 or canary["private_disk_bytes"] > 4_294_967_296 or canary["peak_ram_bytes_upper_bound"] > 8_589_934_592:
        raise Goal048Error("canary transport ceiling failed")
    if _sha(_private(root) / "canary_species_cells.json") != canary["private_species_cell_sha256"] or canary["status"] != "passed":
        raise Goal048Error("canary private receipt or status failed")
    return {"status": canary["status"], "prerequisites": 4, "facet_groups": canary["facet_group_count"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["freeze", "refresh-manifest", "validate-freezes", "canary", "validate"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = freeze_prerequisites(args.root) if args.stage == "freeze" else refresh_prerequisite_manifest(args.root) if args.stage == "refresh-manifest" else validate_freezes(args.root) if args.stage == "validate-freezes" else run_canary(args.root) if args.stage == "canary" else validate(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
