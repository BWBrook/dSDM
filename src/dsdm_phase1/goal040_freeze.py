"""Count-free Goal 040 taxonomy discovery and domain-authority freeze."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import galah
import geopandas as gpd

from .goal040_domain import build_domain_freeze, validate_domain_manifest
from .goal040_count_census import run_count_census, validate_count_census
from .goal040_acquisition import run_acquisition, validate_acquisition
from .goal040_normalisation import run_normalisation, validate_normalisation
from .goal040_support import run_support, validate_support
from .goal040_taxonomy import QUERY_TAXA, validate_taxon_freeze, write_taxon_freeze


BBOX = {"xmin": 135.375, "xmax": 153.625, "ymin": -43.6275, "ymax": -23.7775}
YEARS = (2001, 2025)
ANCHORS = {
    "Notamacropus rufogriseus", "Trichosurus vulpecula",
    "Pseudocheirus peregrinus", "Vombatus ursinus", "Dasyurus maculatus",
}
AFD_PREFIX = "https://biodiversity.org.au/afd/taxa/"
BIE_SPECIES = "https://bie-ws.ala.org.au/ws/species/"
BIE_CHILDREN = "https://bie.ala.org.au/ws/childConcepts/"
ABS_URL = (
    "https://www.abs.gov.au/statistics/standards/"
    "australian-statistical-geography-standard-asgs/edition-4-july-2026-june-2031/"
    "access-and-downloads/digital-boundary-files/STE_2026_AUST_SHP_GDA2020.zip"
)
ABS_SHA256 = "057befed53bc7bd095e54d1594fe32925ed324443df767d66a889c52ba655c03"
WATER_LAYER = (
    "https://hosting.wsapi.cloud.bom.gov.au/arcgis/rest/services/ahgf/"
    "Geofabric_V3x_All_Products/FeatureServer/27"
)
class Goal040FreezeError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _get(url: str, *, accept: str = "application/json", retries: int = 3) -> bytes:
    request = Request(url, headers={"Accept": accept, "User-Agent": "dSDM-Goal040/1.0"})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=120) as response:
                return response.read()
        except Exception:
            if attempt + 1 == retries:
                raise
            time.sleep(1 + attempt)
    raise AssertionError("unreachable")


def _raw(root: Path) -> Path:
    return root / "data/raw/goal040"


def run_taxonomy(root: Path) -> dict[str, Any]:
    raw = _raw(root) / "taxonomy"
    raw.mkdir(parents=True, exist_ok=True)
    species_path = raw / "atlas_species_mammalia_2001_2025_bbox.csv"
    if not species_path.exists():
        email = os.environ.get("ALA_DOWNLOAD_EMAIL")
        if not email:
            raise Goal040FreezeError("ALA_DOWNLOAD_EMAIL is required for live taxonomy discovery")
        galah.galah_config(email=email, atlas="Australia", authenticate=False, verbose=False)
        frame = galah.atlas_species(
            taxa="Mammalia", filters=["year>=2001", "year<=2025"],
            bbox=BBOX, counts=False,
        )
        if any("count" in str(column).lower() for column in frame.columns):
            raise Goal040FreezeError("taxonomy response unexpectedly contains a count column")
        frame.to_csv(species_path, index=False)

    with species_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    _validate_discovery_rows(rows)

    evidence = raw / "concepts"
    evidence.mkdir(exist_ok=True)
    def fetch(row: dict[str, str]) -> list[str]:
        if row["Species Name"] not in QUERY_TAXA:
            return []
        concept = row["Species"]
        key = hashlib.sha256(concept.encode()).hexdigest()[:20]
        detail_path = evidence / f"{key}.bie.json"
        children_path = evidence / f"{key}.children.json"
        afd_path = evidence / f"{key}.afd.html"
        failures = []
        for label, path, url, accept in (
            ("bie", detail_path, BIE_SPECIES + quote(concept, safe=""), "application/json"),
            ("children", children_path, BIE_CHILDREN + quote(concept, safe=""), "application/json"),
            ("afd", afd_path, concept, "text/html"),
        ):
            if path.exists() or (label == "afd" and not concept.startswith(AFD_PREFIX)):
                continue
            try:
                path.write_bytes(_get(url, accept=accept))
            except Exception as error:
                failures.append(f"{row['Species Name']}:{label}:{type(error).__name__}")
        return failures

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = [pool.submit(fetch, row) for row in rows]
        for job in as_completed(jobs):
            failures.extend(job.result())

    manifest = {
        "stage": "taxonomy", "status": "complete_count_free", "retrieved_at": _now(),
        "package": {"name": "galah-python", "version": "0.13.3"},
        "scope": {"taxon": "Mammalia", "years": list(YEARS), "bbox": BBOX, "counts": False},
        "species_rows": len(rows), "species_csv_sha256": _sha(species_path),
        "concept_payloads": len(list(evidence.glob("*.bie.json"))),
        "child_payloads": len(list(evidence.glob("*.children.json"))),
        "afd_pages": len(list(evidence.glob("*.afd.html"))),
        "evidence_failures": failures,
        "email_recorded": False,
    }
    _write_json(raw / "manifest.json", manifest)
    return manifest


def _validate_discovery_rows(rows: list[dict[str, str]]) -> None:
    required = {"Species", "Species Name", "Taxon Rank", "Class", "Order", "Family"}
    if not rows or not required <= set(rows[0]):
        raise Goal040FreezeError("taxonomy discovery schema drift")
    if any(row["Class"] != "Mammalia" or row["Taxon Rank"] != "species" for row in rows):
        raise Goal040FreezeError("taxonomy discovery returned non-mammal or non-species rows")
    concepts = [row["Species"] for row in rows]
    names = [row["Species Name"] for row in rows]
    if len(concepts) != len(set(concepts)) or len(names) != len(set(names)):
        raise Goal040FreezeError("taxonomy discovery concepts or names are not unique")
    if not ANCHORS <= set(names):
        raise Goal040FreezeError("taxonomy discovery omitted an expected anchor")
    if any("count" in column.lower() for column in rows[0]):
        raise Goal040FreezeError("taxonomy discovery contains a count column")


def freeze_ledger(root: Path) -> dict[str, Any]:
    taxonomy = write_taxon_freeze(root)
    boundary = freeze_boundary(root)
    return {"taxonomy": taxonomy["summary"], "boundary": boundary["status"]}


def freeze_boundary(root: Path) -> dict[str, Any]:
    domain = _raw(root) / "domain"
    archive = domain / "STE_2026_AUST_SHP_GDA2020.zip"
    shape = domain / "extracted/STE_2026_AUST_GDA2020.shp"
    domain.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        archive.write_bytes(_get(ABS_URL, accept="application/zip"))
    if _sha(archive) != ABS_SHA256:
        raise Goal040FreezeError("ABS ASGS Edition 4 boundary archive checksum drifted")
    if not shape.exists():
        with zipfile.ZipFile(archive) as source:
            source.extractall(shape.parent)
    if not shape.exists():
        raise Goal040FreezeError("ABS ASGS Edition 4 boundary shape is absent from archive")
    states = gpd.read_file(shape)
    if states.crs is None or states.crs.to_epsg() != 7844 or "6" not in set(states["STE_CODE26"].dropna().astype(str)):
        raise Goal040FreezeError("ABS boundary schema, CRS, or Tasmania identity drift")

    water = domain / "waterbody"
    water.mkdir(exist_ok=True)
    service_path = water / "layer.json"
    if not service_path.exists():
        service_path.write_bytes(_get(WATER_LAYER + "?f=json"))
    service = json.loads(service_path.read_text(encoding="utf-8"))
    if service.get("name") != "AHGFWaterbody (SH_Cartography)":
        raise Goal040FreezeError("Geofabric waterbody layer identity drift")
    ids_path = water / "object_ids.json"
    query = {
        "where": "ahgfftype IN (25,26)", "geometry": f"{BBOX['xmin']},{BBOX['ymin']},{BBOX['xmax']},{BBOX['ymax']}",
        "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true", "f": "json",
    }
    if not ids_path.exists():
        ids_path.write_bytes(_get(WATER_LAYER + "/query?" + urlencode(query)))
    ids = sorted(json.loads(ids_path.read_text(encoding="utf-8")).get("objectIds", []))
    if not ids:
        raise Goal040FreezeError("Geofabric waterbody query returned no object IDs")
    chunk_hashes = []
    for start in range(0, len(ids), 1000):
        chunk = ids[start:start + 1000]
        path = water / f"features_{start // 1000:04d}.geojson"
        params = {"objectIds": ",".join(map(str, chunk)), "outFields": "objectid,ahgfftype,name", "returnGeometry": "true", "outSR": "4326", "f": "geojson"}
        if not path.exists():
            path.write_bytes(_get(WATER_LAYER + "/query?" + urlencode(params), accept="application/geo+json"))
        chunk_hashes.append(_sha(path))
    collection_sha = hashlib.sha256("\n".join(chunk_hashes).encode()).hexdigest()
    manifest = {
        "schema_version": "1.0", "goal_id": "goal040-se-mammal-acquisition-feasibility",
        "status": "frozen_before_counts", "frozen_at": _now(),
        "products": {
            "land_and_state": {
                "product_name": "Australian Statistical Geography Standard Edition 4 States and Territories 2026",
                "product_version": "STE_2026_AUST_GDA2020", "publisher": "Australian Bureau of Statistics",
                "source_url": ABS_URL, "source_identity": "ASGS Edition 4 released 2026-07-22; STE_2026_AUST_GDA2020",
                "sha256": ABS_SHA256, "retrieved_at": _now(),
                "crs": "EPSG:7844 (GDA2020)", "licence": "CC BY 4.0",
            },
            "inland_water": {
                "product_name": "Australian Hydrological Geospatial Fabric Surface Hydrology Cartography waterbodies",
                "product_version": "Geofabric V3.3; AHGFWaterbody layer 27",
                "publisher": "Australian Bureau of Meteorology", "source_url": WATER_LAYER,
                "source_identity": "ArcGIS item 35719064c4ea4ad79faa82f5c9c22068; attribution Commonwealth of Australia (Bureau of Meteorology) 2022",
                "service_metadata_sha256": _sha(service_path), "object_id_set_sha256": _sha(ids_path),
                "feature_collection_sha256": collection_sha, "sha256": collection_sha,
                "retrieved_at": _now(), "feature_count": len(ids),
                "crs": "service native GDA94; query output EPSG:4326", "licence": "CC BY 4.0",
            },
        },
        "rules": {
            "bbox": BBOX, "resolution_degree": 0.01, "cell_coordinates": "cell_centroids",
            "alignment": "future_se_bird_0p01_wgs84_frame",
            "operation": "deterministic bbox enumeration then centroid predicate",
            "land_eligibility": "centroid covered by ASGS STE polygon after EPSG:7844 to EPSG:4326 transform",
            "region": "STE_CODE26=6 is tasmania; every other eligible STE code is southeast_mainland",
            "water_and_lakes": "outside ASGS polygons and source polygon holes are water; centroids covered by Geofabric AHGFWaterbody type 25 Reservoir or type 26 Lake polygons are excluded; type 27 Swamp is retained as potentially suitable terrestrial wetland habitat; unmapped subscale water remains a known limitation",
            "boundary_predicate": "covers (boundary centroids retained before water exclusion)",
            "historical_se_geometry": "comparison_only_not_input",
        },
    }
    manifest["exact_study_domain"] = build_domain_freeze(root)
    validate_domain_manifest(manifest["exact_study_domain"])
    _write_json(root / "metadata/goal040_domain_boundary_manifest.json", manifest)
    return manifest


def validate(root: Path) -> dict[str, Any]:
    boundary_path = root / "metadata/goal040_domain_boundary_manifest.json"
    taxonomy = validate_taxon_freeze(root)
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    if boundary.get("status") != "frozen_before_counts" or boundary["products"]["land_and_state"]["sha256"] != ABS_SHA256:
        raise Goal040FreezeError("boundary authority not frozen")
    validate_domain_manifest(boundary["exact_study_domain"])
    return {
        "status": "validated_count_free", "taxonomy": taxonomy,
        "eligible_cells": boundary["exact_study_domain"]["grid"]["eligible_cell_count"],
        "eligible_cell_id_sha256": boundary["exact_study_domain"]["grid"]["eligible_cell_id_sha256"],
        "boundary": boundary["products"]["land_and_state"]["product_version"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=[
            "taxonomy", "freeze-ledger", "count-census", "validate-count-census",
            "acquire", "validate-acquisition", "normalise", "validate-normalisation", "support", "validate-support", "validate",
        ],
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--raw-replay", action="store_true",
        help="replay ignored raw acquisition CSV/receipt pairs during validation",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if args.stage == "taxonomy":
        result = run_taxonomy(root)
    elif args.stage == "freeze-ledger":
        result = freeze_ledger(root)
    elif args.stage == "count-census":
        result = run_count_census(root)
    elif args.stage == "validate-count-census":
        result = validate_count_census(root)
    elif args.stage == "acquire":
        result = run_acquisition(root)
    elif args.stage == "validate-acquisition":
        result = validate_acquisition(root, require_raw=args.raw_replay)
    elif args.stage == "normalise":
        result = run_normalisation(root)
    elif args.stage == "validate-normalisation":
        result = validate_normalisation(root, require_raw=args.raw_replay)
    elif args.stage == "support":
        result = run_support(root)
    elif args.stage == "validate-support":
        result = validate_support(root, require_raw=args.raw_replay)
    else:
        result = validate(root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
