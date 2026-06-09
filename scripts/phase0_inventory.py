#!/usr/bin/env python3
"""Generate Phase 0 inventory docs and manifests for the dSDM rebuild."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


REPO = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO / "docs" / "phase0"
META_DIR = REPO / "metadata" / "phase0"

FILE_INVENTORY = META_DIR / "file_inventory.csv"
CHECKSUMS = META_DIR / "checksums.sha256"
TABULAR_INVENTORY = META_DIR / "tabular_inventory.csv"
SPATIAL_INVENTORY = META_DIR / "spatial_inventory.csv"
LEGACY_SCRIPT_INVENTORY = META_DIR / "legacy_script_inventory.csv"

PHASE0_REPORT = DOCS_DIR / "phase0_report.md"
LEGACY_WORKFLOW_MAP = DOCS_DIR / "legacy_workflow_map.md"
PHASE1_QUESTIONS = DOCS_DIR / "phase1_questions.md"

EXCLUDED_PREFIXES = (
    ".git/",
    "_targets/",
    ".targets/",
    ".cache/",
    "manuscript/build/",
)
EXCLUDED_NAMES = {".DS_Store"}
FILE_INVENTORY_SELF = "metadata/phase0/file_inventory.csv"

CSV_MISSING_VALUES = {"", "NA", "NaN", "nan", "NULL", "null"}
KEY_FIELDS = (
    "Lon",
    "Lat",
    "lon",
    "lat",
    "longitude",
    "latitude",
    "species",
    "pa",
    "fold",
    "type",
)


@dataclass(frozen=True)
class LegacyInfo:
    category: str
    purpose: str
    implied_inputs: str
    implied_outputs: str
    missing_refs: str
    known_defects: str
    phase1_relevance: str


LEGACY_MAP: dict[str, LegacyInfo] = {
    "temp/src/0_galah_ALA.r": LegacyInfo(
        "data_acquisition",
        "Download focal mammal/bird occurrence records from ALA using galah and a study-area polygon.",
        "species list CSV; study-area/coast shapefile; live ALA service",
        "output/mammal_ala_tasmania.csv",
        "No local output artifact with this exact name arrived.",
        "Hard-coded Windows path and email; live ALA query is not version-pinned; output write path is implicit.",
        "Defines the ALA acquisition intent to rebuild in Python.",
    ),
    "temp/src/1_process_point_data.R": LegacyInfo(
        "point_processing",
        "Snap ALA occurrences to grid cells, derive pseudoabsences, and thin records by human-activity sampling intensity.",
        "grid points; ALA occurrence CSV; human-footprint raster; Tasmania coast shapefile",
        "output/tas_mammal_ala_pa.csv",
        "Requires helper logic from sdm_data_func.R.",
        "Manual species loop; hard-coded Windows path; relies on interactive plotting/sanity checks.",
        "Important source for pseudoabsence and sampling-bias intent.",
    ),
    "temp/src/1a_tas_sdm_data_combine.r": LegacyInfo(
        "data_combination",
        "Merge camera-trap true PA data with ALA-derived PA data and remove offshore-island absences by species.",
        "input/tascam_grid_pa.csv; output/tas_mammal_ala_pa.csv; offshore_islands.kml",
        "output/tas_mammal_combined_pa_grid.csv",
        "Only processed descendants arrived, not the named combined output.",
        "Manual one-species block; island exclusions are embedded as code rather than config.",
        "High priority for Phase 1 because true absence and pseudoabsence provenance must be explicit.",
    ),
    "temp/src/2_tas_sdm_data_cv_split.r": LegacyInfo(
        "spatial_folds",
        "Create 50 spatial clusters, manually choose 5 held-out folds, and aggregate the rest into 5 train folds.",
        "output/tas_mammal_combined_pa_grid.csv",
        "output/tas_sdm_cvsplit.csv",
        "Calls plot_species(), but provided helper is named plot_spatial_species_data().",
        "Manual visual fold selection; hard-coded test fold IDs; no persisted split manifest arrived.",
        "Defines spatial hold-out design that Phase 1 must make reproducible.",
    ),
    "temp/src/3_create_sdm_data.R": LegacyInfo(
        "predictor_formatting",
        "Join occurrence rows to raster covariates, drop selected layers, scale continuous predictors, one-hot encode categorical predictors.",
        "output/tas_sdm_cvsplit.csv; spatial/tas_stack.tif",
        "output/tas_sdm_train.csv; output/tas_sdm_test.csv; output/tas_sdm_map.csv",
        "Processed CSV descendants arrived under temp/data/tas_sdm_data/.",
        "Assumes complete raster stack and fixed categorical levels; no standalone schema manifest.",
        "Strong reference for predictor schema, but regenerated data should be canonical.",
    ),
    "temp/src/4a_ml_randomForest.R": LegacyInfo(
        "baseline_ml",
        "Fit and tune a random-forest SDM for one selected species, evaluate held-out predictions, and map habitat suitability.",
        "tas_sdm_train.csv; tas_sdm_test.csv; tas_sdm_map.csv",
        "sdm_results/performance/*_rf.csv; sdm_results/maps/tas_norm_maps_rf.csv",
        "No result/map artifacts arrived.",
        "One-species script; hard-coded output paths; normalises probabilities before thresholding.",
        "Reference for baseline comparison intent only, not Phase 0 implementation.",
    ),
    "temp/src/4b_ml_ANN.R": LegacyInfo(
        "baseline_ml",
        "Fit and tune a shallow ANN/MLP baseline through tidymodels/nnet.",
        "tas_sdm_train.csv; tas_sdm_test.csv; tas_sdm_map.csv",
        "sdm_results/performance/*_ann.csv; sdm_results/maps/tas_norm_maps_ann.csv",
        "No result/map artifacts arrived.",
        "One-species script; hard-coded output paths; normalises probabilities before thresholding.",
        "Reference for baseline comparison intent only, not Phase 0 implementation.",
    ),
    "temp/src/4c_ml_ensemble.R": LegacyInfo(
        "baseline_ml",
        "Fit GLM, GAM, GBM, RF, and ANN models and average predictions into an ensemble.",
        "tas_sdm_train.csv; tas_sdm_test.csv; tas_sdm_map.csv",
        "sdm_results/performance/*_ensemble.csv; sdm_results/maps/tas_norm_maps_ensemble.csv",
        "No result/map artifacts arrived.",
        "Large copy-paste script; hard-coded selected species; mixed model engines and output assumptions.",
        "Reference for baseline family and ensemble intent.",
    ),
    "temp/src/8_model_eval.R": LegacyInfo(
        "evaluation",
        "Evaluate a combined prediction CSV into per-model, per-species metrics.",
        "results/rahil_sdm_output.csv",
        "Printed/sorted metric table",
        "Input artifact did not arrive.",
        "Thin wrapper around helper; no reproducible result artifact.",
        "Reference for final metric-table intent.",
    ),
    "temp/src/modelling_functions.R": LegacyInfo(
        "baseline_ml_helpers",
        "Provide metric, threshold, formula-generation, RF, ANN, and GBM helper functions.",
        "Prediction data frames; tidymodels recipes/workflows",
        "Model objects and metric data frames",
        "Depends on packages not declared in current DESCRIPTION, e.g. PRROC/xgboost/neuralnet in places.",
        "Contains duplicated/fragile metric logic; probability normalisation affects calibration.",
        "Useful for metric list and baseline families; implementations should be rewritten/tested.",
    ),
    "temp/src/sdm_data_func.R": LegacyInfo(
        "data_helpers",
        "Provide helper functions for ALA retrieval, pseudoabsence construction, thinning, spatial folds, and predictor formatting.",
        "Occurrence CSVs; rasters; shapefiles; species lists",
        "Processed occurrence and modelling data frames",
        "make_sdm_sf() is not present although old dSDM preprocess calls it.",
        "potential_absences_from_sites() refers to presences instead of its pres argument; get_ALA_data() output write check is wrong.",
        "High priority source of intent and bugs for Phase 1 design.",
    ),
    "temp/src/z_execute.R": LegacyInfo(
        "orchestration",
        "Ad hoc execution scratchpad for legacy R workflow.",
        "Legacy local files",
        "Legacy local outputs",
        "Not a reproducible pipeline entry point.",
        "Hard-coded paths and manual state retention.",
        "Low value except as an ordering clue.",
    ),
    "temp/old_code/5_DSDM_preprocess.R": LegacyInfo(
        "dsdm_preprocess",
        "Create RDS train/test/augmentation objects for R-Keras dSDM.",
        "output/tas_sdm_cvsplit.csv; spatial/tas_stack.tif",
        "output/tas_sdm_train.RDS; output/tas_sdm_test.RDS; output/tas_sdm_aug.RDS",
        "Calls make_sdm_sf(), which did not arrive; RDS outputs did not arrive.",
        "Hard-coded paths; breaks out augmentation comments inconsistently; interactive jitter calibration block.",
        "Documents intended augmented-object shape for Python rebuild.",
    ),
    "temp/old_code/6_DSDM_tune_hyper_parameters.R": LegacyInfo(
        "dsdm_tuning",
        "Grid-search Keras dSDM hyperparameters for one target species.",
        "output/tas_sdm_train.RDS",
        "code/hyper_grid_v1.csv",
        "RDS input and hyperparameter output did not arrive.",
        "One-species manual script; legacy R-Keras/TensorFlow path.",
        "Reference for initial model search space.",
    ),
    "temp/old_code/7a_DSDM_single_species.R": LegacyInfo(
        "dsdm_training",
        "Train no-transfer dSDM from random weights for one species.",
        "tas_sdm_train.RDS; tas_sdm_test.RDS; tas_sdm_aug_100_epochs.RDS",
        "models/*_ss_sdm.h5; results/pred_*_ss.csv",
        "RDS, model, and prediction artifacts did not arrive.",
        "Manual target species; legacy HDF5 Keras artifacts; validation/early stopping is not cleanly resolved.",
        "Reference for no-transfer dSDM design.",
    ),
    "temp/old_code/7b_DSDM_paired_species.R": LegacyInfo(
        "dsdm_transfer",
        "Load a paired-species model, replace classifier top, and fine-tune on target species.",
        "paired *_ss_sdm.h5; tas RDS train/test/aug objects",
        "models/*_ps_sdm.h5; output/pred_*_ps.csv",
        "All model/RDS artifacts absent.",
        "Manual species pairings; top replacement and layer-freezing require modern Keras review.",
        "Reference for paired-transfer hypothesis.",
    ),
    "temp/old_code/7c_DSDM_sequential.R": LegacyInfo(
        "dsdm_transfer",
        "Train/fine-tune through a hand-coded species sequence before target transfer.",
        "tas_sdm_aug_100_epochs.RDS",
        "models/*_sq_base.h5",
        "RDS/model artifacts absent.",
        "Manual sequence embedded in code; no final target prediction in this script.",
        "Reference for sequential-transfer hypothesis.",
    ),
    "temp/old_code/7d_DSDM_melting_pot.R": LegacyInfo(
        "dsdm_transfer",
        "Train a community/melting-pot base model on all non-target species.",
        "tas RDS train/test/aug objects",
        "models/*_mp_base.h5",
        "RDS/model artifacts absent.",
        "Manual target species; base target exclusion embedded in script.",
        "Reference for community-transfer hypothesis.",
    ),
    "temp/old_code/7_DSDM_fine_tune_6cd_predict.R": LegacyInfo(
        "dsdm_transfer",
        "Fine-tune a saved transfer base on the target species and write held-out predictions.",
        "models/*_base.h5; tas RDS train/test/aug objects",
        "models/*_sdm.h5; output/pred_*.csv",
        "All required model/RDS artifacts absent.",
        "Manual target/base settings; legacy HDF5 Keras path.",
        "Reference for final transfer/fine-tune prediction flow.",
    ),
    "temp/old_code/8_model_eval.R": LegacyInfo(
        "evaluation",
        "Duplicate of legacy metric wrapper for combined predictions.",
        "results/rahil_sdm_output.csv",
        "Printed/sorted metric table",
        "Input artifact did not arrive.",
        "Thin wrapper; no persisted output.",
        "Reference only.",
    ),
    "temp/old_code/dsdm_func.R": LegacyInfo(
        "dsdm_helpers",
        "Provide R-Keras model building, tuning, jitter augmentation, transfer, and metric helpers.",
        "RDS train/test/aug objects; Keras models",
        "Model objects, histories, prediction metrics",
        "Depends on legacy R keras/tensorflow stack; no lockfile or model artifacts arrived.",
        "Dynamic early stopping mostly disabled; MultiWorker strategy likely wrong for single Alien WSL host; duplicated metric logic.",
        "Most important dSDM intent artifact, to mine carefully for Python Keras 3 design.",
    ),
    "temp/old_code/z_execute.R": LegacyInfo(
        "unrelated_scratch",
        "Appears to be an unrelated drought-seedlings dense neural network scratchpad.",
        "drought_seedlings local files",
        "none relevant",
        "Not part of dSDM payload.",
        "Hard-coded unrelated working directory.",
        "Exclude from Phase 1 except as a reminder to ignore unrelated archaeology.",
    ),
}


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def run(cmd: list[str], *, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def split_nul(text: str) -> set[str]:
    return {item for item in text.split("\0") if item}


def git_paths(args: list[str]) -> set[str]:
    proc = run(["git", *args, "-z"])
    if proc.returncode != 0:
        return set()
    return split_nul(proc.stdout)


def git_status_short() -> str:
    proc = run(["git", "status", "--short", "--ignored"])
    return proc.stdout.strip()


def should_exclude_common(rel_path: str) -> bool:
    if Path(rel_path).name in EXCLUDED_NAMES:
        return True
    if rel_path.endswith("__pycache__/") or "/__pycache__/" in rel_path:
        return True
    if rel_path.endswith((".pyc", ".pyo", ".pyd")):
        return True
    return any(rel_path.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def should_exclude_inventory(rel_path: str) -> bool:
    return should_exclude_common(rel_path) or rel_path == FILE_INVENTORY_SELF


def should_checksum(rel_path: str) -> bool:
    if should_exclude_common(rel_path):
        return False
    if rel_path.startswith("metadata/phase0/"):
        return False
    if rel_path.endswith(".pyc") or "/__pycache__/" in rel_path:
        return False
    return True


def iter_repo_files() -> list[Path]:
    files: list[Path] = []
    for root, dirs, names in os.walk(REPO):
        root_path = Path(root)
        rel_root = rel(root_path) if root_path != REPO else ""
        dirs[:] = [
            d
            for d in dirs
            if not should_exclude_common(f"{rel_root}/{d}/".lstrip("/"))
        ]
        for name in names:
            path = root_path / name
            rel_path = rel(path)
            if not should_exclude_inventory(rel_path):
                files.append(path)
    return sorted(files, key=rel)


def case_study_for_path(rel_path: str) -> str:
    lower = rel_path.lower()
    if "se_sdm" in lower or "se_stack" in lower or "human_footprint_se" in lower:
        return "se_birds"
    if "tas" in lower or "tascam" in lower or "offshore_islands" in lower:
        return "tas_mammals"
    if "spatial_polygons" in lower or "ibra" in lower:
        return "se_birds"
    return "general"


def role_for_path(rel_path: str) -> str:
    suffix = Path(rel_path).suffix.lower()
    if rel_path.startswith("docs/phase0/"):
        return "phase0_doc"
    if rel_path.startswith("docs/plan/"):
        return "plan_doc"
    if rel_path.startswith("docs/"):
        return "planning_doc"
    if rel_path.startswith("metadata/phase0/"):
        return "phase0_manifest"
    if rel_path.startswith("metadata/"):
        return "metadata"
    if rel_path.startswith("scripts/phase0_"):
        return "phase0_helper"
    if rel_path.startswith("manuscript/"):
        return "manuscript_source"
    if rel_path.startswith("temp/src/") or rel_path.startswith("temp/old_code/"):
        return "legacy_code"
    if rel_path.startswith("temp/data/"):
        if suffix in {".tif", ".shp", ".kml", ".dbf", ".shx", ".prj"}:
            return "legacy_spatial_data"
        return "legacy_processed_data"
    if rel_path.startswith("temp/"):
        return "legacy_reference"
    if rel_path.startswith("data/input/"):
        return "input_payload"
    if rel_path.startswith(("inst/", "profiles/", "config/", "reports/")):
        return "repo_scaffold"
    if rel_path in {"DESCRIPTION", "_targets.R", "dependencies.R", "quarto.yml"}:
        return "repo_scaffold"
    if suffix in {".r", ".R".lower()}:
        return "source_code"
    return "repo_file"


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def file_inventory_rows() -> list[dict[str, object]]:
    tracked = git_paths(["ls-files"])
    untracked = git_paths(["ls-files", "--others", "--exclude-standard"])
    ignored = git_paths(["ls-files", "--others", "--ignored", "--exclude-standard"])
    rows: list[dict[str, object]] = []
    for path in iter_repo_files():
        rel_path = rel(path)
        if rel_path in tracked:
            git_state = "tracked"
        elif rel_path in ignored:
            git_state = "ignored"
        elif rel_path in untracked:
            git_state = "untracked"
        else:
            git_state = "unknown"
        stat = path.stat()
        rows.append(
            {
                "path": rel_path,
                "git_state": git_state,
                "role": role_for_path(rel_path),
                "case_study": case_study_for_path(rel_path),
                "suffix": path.suffix.lower(),
                "bytes": stat.st_size,
                "mtime_epoch": int(stat.st_mtime),
            }
        )
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums() -> None:
    paths = [path for path in iter_repo_files() if should_checksum(rel(path))]
    with CHECKSUMS.open("w", encoding="utf-8") as handle:
        for path in paths:
            handle.write(f"{sha256_file(path)}  {rel(path)}\n")


def inspect_csv(path: Path) -> dict[str, object]:
    data_rows = 0
    missing_cells = 0
    missing_columns: Counter[str] = Counter()
    header: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        for row in reader:
            data_rows += 1
            for idx, value in enumerate(row):
                if value in CSV_MISSING_VALUES:
                    missing_cells += 1
                    if idx < len(header):
                        missing_columns[header[idx]] += 1
    key_fields = [field for field in KEY_FIELDS if field in header]
    notes = ""
    if path.name.endswith("_test.csv") and "fold" in missing_columns:
        notes = "fold is missing by design for held-out test rows"
    return {
        "path": rel(path),
        "table_kind": "csv",
        "sheet_name": "",
        "case_study": case_study_for_path(rel(path)),
        "bytes": path.stat().st_size,
        "data_rows": data_rows,
        "columns": len(header),
        "key_fields": ";".join(key_fields),
        "missing_cells": missing_cells,
        "columns_with_missing": ";".join(sorted(missing_columns)),
        "notes": notes,
    }


def col_ref_to_number(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch.upper()) - ord("A") + 1)
    return value


def inspect_xlsx(path: Path) -> list[dict[str, object]]:
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    rows: list[dict[str, object]] = []
    try:
        with zipfile.ZipFile(path) as zf:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for item in root.findall("a:si", ns):
                    shared.append("".join(t.text or "" for t in item.findall(".//a:t", ns)))
            workbook = ET.fromstring(zf.read("xl/workbook.xml"))
            rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
            for sheet in workbook.findall("a:sheets/a:sheet", ns):
                name = sheet.attrib.get("name", "")
                rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
                target = relmap.get(rid, "")
                if not target:
                    continue
                sheet_path = "xl/" + target.lstrip("/")
                root = ET.fromstring(zf.read(sheet_path))
                xml_rows = root.findall(".//a:sheetData/a:row", ns)
                max_col = 0
                header_values: list[str] = []
                for row_idx, xml_row in enumerate(xml_rows):
                    for cell in xml_row.findall("a:c", ns):
                        max_col = max(max_col, col_ref_to_number(cell.attrib.get("r", "")))
                        if row_idx == 0:
                            value = ""
                            node = cell.find("a:v", ns)
                            if node is not None and node.text is not None:
                                value = shared[int(node.text)] if cell.attrib.get("t") == "s" else node.text
                            header_values.append(value)
                rows.append(
                    {
                        "path": rel(path),
                        "table_kind": "xlsx_sheet",
                        "sheet_name": name,
                        "case_study": case_study_for_path(rel(path)),
                        "bytes": path.stat().st_size,
                        "data_rows": max(0, len(xml_rows) - 1),
                        "columns": max_col,
                        "key_fields": ";".join([field for field in KEY_FIELDS if field in header_values]),
                        "missing_cells": "",
                        "columns_with_missing": "",
                        "notes": "metadata workbook sheet",
                    }
                )
    except Exception as exc:  # pragma: no cover - defensive reporting
        rows.append(
            {
                "path": rel(path),
                "table_kind": "xlsx_error",
                "sheet_name": "",
                "case_study": case_study_for_path(rel(path)),
                "bytes": path.stat().st_size,
                "data_rows": "",
                "columns": "",
                "key_fields": "",
                "missing_cells": "",
                "columns_with_missing": "",
                "notes": f"ERROR: {type(exc).__name__}: {exc}",
            }
        )
    return rows


def tabular_inventory_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in iter_repo_files():
        rel_path = rel(path)
        if rel_path.startswith("metadata/phase0/"):
            continue
        suffix = path.suffix.lower()
        if suffix == ".csv":
            rows.append(inspect_csv(path))
        elif suffix == ".xlsx":
            rows.extend(inspect_xlsx(path))
    return rows


def parse_epsg(text: str) -> str:
    matches = re.findall(r'ID\["EPSG",\s*(\d+)\]', text)
    return matches[-1] if matches else ""


def extent_text_from_gdal(info: dict[str, object]) -> str:
    corners = info.get("cornerCoordinates") or {}
    if not isinstance(corners, dict):
        return ""
    lower_left = corners.get("lowerLeft")
    upper_right = corners.get("upperRight")
    if isinstance(lower_left, list) and isinstance(upper_right, list):
        return f"{lower_left[0]},{lower_left[1]} to {upper_right[0]},{upper_right[1]}"
    return ""


def inspect_raster(path: Path) -> dict[str, object]:
    proc = run(["gdalinfo", "-json", str(path)])
    rel_path = rel(path)
    if proc.returncode != 0:
        return {
            "path": rel_path,
            "member": "",
            "spatial_kind": "raster",
            "driver": "",
            "crs": "",
            "extent": "",
            "dimensions_or_features": "",
            "bands_or_layers": "",
            "case_study": case_study_for_path(rel_path),
            "notes": f"gdalinfo failed: {proc.stderr.strip()}",
        }
    info = json.loads(proc.stdout)
    size = info.get("size") or ["", ""]
    bands = info.get("bands") or []
    wkt = ((info.get("coordinateSystem") or {}).get("wkt") or "") if isinstance(info.get("coordinateSystem"), dict) else ""
    return {
        "path": rel_path,
        "member": "",
        "spatial_kind": "raster",
        "driver": (info.get("driverShortName") or ""),
        "crs": parse_epsg(wkt) or "unknown",
        "extent": extent_text_from_gdal(info),
        "dimensions_or_features": f"{size[0]}x{size[1]}" if len(size) >= 2 else "",
        "bands_or_layers": len(bands),
        "case_study": case_study_for_path(rel_path),
        "notes": "",
    }


def parse_ogr_text(text: str) -> dict[str, str]:
    driver = ""
    layer = ""
    geom = ""
    features = ""
    extent = ""
    for line in text.splitlines():
        line = line.strip()
        if "using driver" in line:
            match = re.search(r"using driver `([^']+)'", line)
            if match:
                driver = match.group(1)
        elif line.startswith("Layer name:"):
            layer = line.split(":", 1)[1].strip()
        elif line.startswith("Geometry:"):
            geom = line.split(":", 1)[1].strip()
        elif line.startswith("Feature Count:"):
            features = line.split(":", 1)[1].strip()
        elif line.startswith("Extent:"):
            extent = line.split(":", 1)[1].strip()
    epsg = parse_epsg(text)
    return {
        "driver": driver,
        "layer": layer,
        "geom": geom,
        "features": features,
        "extent": extent,
        "crs": epsg,
    }


def inspect_vector(path_label: str, datasource: str, layer: str = "", member: str = "") -> dict[str, object]:
    cmd = ["ogrinfo", "-ro", "-so", datasource]
    if layer:
        cmd.append(layer)
    proc = run(cmd)
    parsed = parse_ogr_text(proc.stdout + "\n" + proc.stderr)
    notes = ""
    if proc.returncode != 0:
        notes = f"ogrinfo failed: {proc.stderr.strip()}"
    return {
        "path": path_label,
        "member": member,
        "spatial_kind": "vector",
        "driver": parsed["driver"],
        "crs": parsed["crs"] or "unknown",
        "extent": parsed["extent"],
        "dimensions_or_features": parsed["features"],
        "bands_or_layers": parsed["layer"] or layer,
        "case_study": case_study_for_path(path_label + "/" + member),
        "notes": f"{parsed['geom']}; {notes}".strip("; "),
    }


def inspect_zip_spatial(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    rel_path = rel(path)
    try:
        with zipfile.ZipFile(path) as zf:
            members = zf.namelist()
    except zipfile.BadZipFile:
        return rows
    shp_members = [member for member in members if member.lower().endswith(".shp")]
    rows.append(
        {
            "path": rel_path,
            "member": "",
            "spatial_kind": "archive",
            "driver": "ZIP",
            "crs": "",
            "extent": "",
            "dimensions_or_features": len(members),
            "bands_or_layers": len(shp_members),
            "case_study": case_study_for_path(rel_path),
            "notes": "spatial archive with shapefile members",
        }
    )
    for member in shp_members:
        datasource = f"/vsizip/{path.resolve()}/{member}"
        layer = Path(member).stem
        rows.append(inspect_vector(rel_path, datasource, layer=layer, member=member))
    return rows


def kml_layer(path: Path) -> str:
    proc = run(["ogrinfo", "-ro", "-so", str(path)])
    for line in proc.stdout.splitlines():
        match = re.match(r"\s*\d+:\s+(.+)$", line)
        if match:
            return match.group(1).strip()
    return ""


def spatial_inventory_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in iter_repo_files():
        suffix = path.suffix.lower()
        if suffix in {".tif", ".tiff"}:
            rows.append(inspect_raster(path))
        elif suffix == ".shp":
            rows.append(inspect_vector(rel(path), str(path), layer=path.stem))
        elif suffix == ".kml":
            layer = kml_layer(path)
            rows.append(inspect_vector(rel(path), str(path), layer=layer))
        elif suffix == ".zip" and "spatial" in rel(path).lower():
            rows.extend(inspect_zip_spatial(path))
    return rows


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def legacy_script_inventory_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    paths = sorted(
        list((REPO / "temp" / "src").glob("*.R"))
        + list((REPO / "temp" / "src").glob("*.r"))
        + list((REPO / "temp" / "old_code").glob("*.R")),
        key=rel,
    )
    for path in paths:
        rel_path = rel(path)
        info = LEGACY_MAP.get(
            rel_path,
            LegacyInfo(
                "unclassified",
                "Unclassified legacy script.",
                "",
                "",
                "",
                "Needs manual review.",
                "Unknown.",
            ),
        )
        text = path.read_text(encoding="utf-8", errors="replace")
        rows.append(
            {
                "path": rel_path,
                "category": info.category,
                "line_count": line_count(path),
                "purpose": info.purpose,
                "implied_inputs": info.implied_inputs,
                "implied_outputs": info.implied_outputs,
                "missing_refs": info.missing_refs,
                "known_defects": info.known_defects,
                "phase1_relevance": info.phase1_relevance,
                "has_windows_setwd": "C:/Users/" in text,
                "mentions_keras": "keras" in text.lower() or "tensorflow" in text.lower(),
            }
        )
    return rows


def count_by(rows: Iterable[dict[str, object]], key: str) -> Counter[str]:
    return Counter(str(row.get(key, "")) for row in rows)


def markdown_table(rows: list[dict[str, object]], columns: list[str], limit: int | None = None) -> str:
    selected = rows if limit is None else rows[:limit]
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in selected:
        values = [str(row.get(column, "")).replace("|", "\\|") for column in columns]
        out.append("| " + " | ".join(values) + " |")
    return "\n".join(out)


def major_tabular_rows(tabular_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    names = {
        "temp/data/tas_sdm_data/tas_sdm_train.csv",
        "temp/data/tas_sdm_data/tas_sdm_test.csv",
        "temp/data/tas_sdm_data/tas_sdm_map.csv",
        "temp/data/tas_sdm_data/tascam_grid_pa.csv",
        "temp/data/tas_sdm_data/tas_mammal_ala_pa.csv",
        "temp/data/se_sdm_data/se_train_data.csv",
        "temp/data/se_sdm_data/se_test_data.csv",
        "temp/data/se_sdm_data/se_sdm_map.csv",
        "temp/data/spatial/se_stack_metadata.xlsx",
    }
    return [row for row in tabular_rows if row["path"] in names]


def write_phase0_report(
    file_rows: list[dict[str, object]],
    tabular_rows: list[dict[str, object]],
    spatial_rows: list[dict[str, object]],
    legacy_rows: list[dict[str, object]],
) -> None:
    file_states = count_by(file_rows, "git_state")
    roles = count_by(file_rows, "role")
    legacy_categories = count_by(legacy_rows, "category")
    status = git_status_short()
    status_excerpt = "\n".join(status.splitlines()[:30]) if status else "Clean working tree."
    major_rows = major_tabular_rows(tabular_rows)
    content = f"""# Phase 0 report: Preserve, inventory, orient

Date: 2026-05-27

## Gate status

Phase 0 evidence has been generated from the current repository state. The gate
is not complete until automated verification passes and Barry explicitly signs
off that this evidence is sufficient for detailed Phase 1 planning.

## Known facts

- Repository root: `{REPO}`
- Inventory files counted: {len(file_rows)}
- Git states in inventory: {dict(file_states)}
- Main roles in inventory: {dict(roles)}
- Legacy R scripts inventoried: {len(legacy_rows)}
- Legacy categories: {dict(legacy_categories)}
- Tabular resources inventoried: {len(tabular_rows)}
- Spatial resources inventoried: {len(spatial_rows)}
- Existing processed data are reference artifacts only, not canonical rebuild
  substrates.
- Tasmanian mammals are the Phase 1 proving-ground case study; SE Australia
  birds are the later scale-out case.

## Major tabular payloads

{markdown_table(major_rows, ["path", "table_kind", "sheet_name", "case_study", "data_rows", "columns", "missing_cells"])}

## Known missing or broken pieces

- Tracked `src/` files were moved to ignored `temp/src/` and currently appear as
  tracked deletions until the repo is intentionally committed.
- `_targets.R` is placeholder scaffold: it calls `tar_source("R")`, `cfg_read()`,
  and `read_manifest()`, but no tracked `R/` directory exists.
- `renv::status()` reports that this project is not currently using `renv`.
- `scripts/bootstrap.R` is referenced by container recipes but does not exist.
- `make_sdm_sf()` is called by old dSDM preprocessing but did not arrive.
- `plot_species()` is called by the old fold script but the visible helper name
  is `plot_spatial_species_data()`.
- No fitted models, RDS augmented datasets, prediction CSVs, or final metric
  outputs arrived with the payload.
- `species_list_tas.csv` omits `Thylogale billardierii` even though processed
  Tas modelling files include that species.

## Inferred intent

- Re-acquire primary ALA and camera-trap data rather than treating processed CSVs
  as canonical.
- Preserve true-absence versus pseudoabsence provenance through the rebuild.
- Rebuild spatial folds and predictor formatting in Python with explicit
  configs, manifests, and QA gates.
- Mine old R and R-Keras code for method intent, not implementation structure.
- Keep manuscript revisions coupled to accepted data/model artifacts.

## Current git status excerpt

```text
{status_excerpt}
```

## Gate checklist

- [ ] Phase 0 manifests and docs exist.
- [ ] `python3 scripts/phase0_verify.py` passes.
- [ ] `make -C manuscript check` passes.
- [ ] Bulky payloads remain ignored.
- [ ] Barry signs off before detailed Phase 1 planning begins.
"""
    PHASE0_REPORT.write_text(content, encoding="utf-8")


def write_legacy_workflow_map(legacy_rows: list[dict[str, object]]) -> None:
    ordered = [
        "data_acquisition",
        "point_processing",
        "data_combination",
        "spatial_folds",
        "predictor_formatting",
        "baseline_ml",
        "baseline_ml_helpers",
        "dsdm_preprocess",
        "dsdm_tuning",
        "dsdm_training",
        "dsdm_transfer",
        "dsdm_helpers",
        "evaluation",
    ]
    by_category: dict[str, list[dict[str, object]]] = {category: [] for category in ordered}
    for row in legacy_rows:
        by_category.setdefault(str(row["category"]), []).append(row)

    sections = [
        "# Legacy workflow map",
        "",
        "This map records intent inferred from ignored legacy scripts. It is not a",
        "directive to mimic the old implementation.",
        "",
        "## High-level inferred flow",
        "",
        "1. Query ALA records for focal species.",
        "2. Snap records to a spatial grid and derive pseudoabsences.",
        "3. Merge ALA-derived rows with Tas camera-trap true PA rows.",
        "4. Exclude selected offshore-island absences and thin records.",
        "5. Build spatial train/test/CV folds.",
        "6. Extract raster predictors, scale continuous fields, and one-hot encode categories.",
        "7. Fit baseline ML models and produce predictions/metrics/maps.",
        "8. Fit dSDM variants with no-transfer, paired, sequential, and community transfer.",
        "9. Evaluate metrics and feed accepted outputs into the manuscript.",
        "",
        "## Script inventory by category",
        "",
    ]
    for category in ordered:
        rows = by_category.get(category, [])
        if not rows:
            continue
        sections.append(f"### {category}")
        sections.append("")
        sections.append(
            markdown_table(
                rows,
                ["path", "purpose", "implied_inputs", "implied_outputs", "missing_refs", "known_defects"],
            )
        )
        sections.append("")
    sections.append("## Phase 1 mining rules")
    sections.append("")
    sections.extend(
        [
            "- Preserve ecological intent, provenance distinctions, and QA clues.",
            "- Do not copy hard-coded paths, one-species manual loops, or stale Keras idioms.",
            "- Treat missing outputs and missing helpers as evidence that upstream data must be rebuilt.",
            "- Use old processed CSVs only as comparison/reference artifacts.",
        ]
    )
    LEGACY_WORKFLOW_MAP.write_text("\n".join(sections) + "\n", encoding="utf-8")


def write_phase1_questions() -> None:
    content = """# Phase 1 questions from Phase 0 evidence

These questions are not the detailed Phase 1 plan. They define what Phase 1
planning must decide after Phase 0 is accepted.

## Primary data acquisition

- What exact focal Tas mammal species list is authoritative, given that the old
  species list omits `Thylogale billardierii` but processed data include it?
- Which ALA record fields, filters, date bounds, data-resource filters, and QA
  rules must be used for the rebuild?
- How will ALA query results be versioned when the upstream service is live and
  changing?

## Camera-trap data and provenance

- Where is the primary camera-trap dataset, and what fields define true
  presence/absence at the grid-cell/species level?
- Should true absences and pseudoabsences be modelled, weighted, or reported
  differently?
- What provenance column(s) must survive through all downstream data products?

## Spatial grid and boundaries

- What is the canonical Tas grid definition: source file, resolution, CRS, and
  cell-centre convention?
- Which offshore-island exclusions are biologically authoritative for each
  species?
- Should old manually selected spatial test folds be reproduced, revised, or
  replaced with a documented deterministic rule?

## Pseudoabsence and thinning logic

- What minimum survey-effort rule defines candidate pseudoabsence sites?
- What distance rule separates presences and pseudoabsences?
- How should sampling-bias thinning by human activity be configured and tested?

## Predictor extraction and formatting

- Which raster/vector predictor sources are canonical for the Tas rebuild?
- Which predictors are continuous versus categorical, and which categorical
  levels must be retained even when absent in a split?
- Should scaling/encoding parameters be saved as first-class artifacts for model
  reproducibility?

## QA and acceptance

- What tolerances are acceptable when regenerated data differ from old CSVs?
- Which summaries are gate-blocking: row counts, prevalence, fold balance,
  missingness, spatial extent, duplicate cells, or all of these?
- What minimum smoke dataset should be tracked for tests without committing
  bulky/raw data?
"""
    PHASE1_QUESTIONS.write_text(content, encoding="utf-8")


def generate() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    tabular_rows = tabular_inventory_rows()
    spatial_rows = spatial_inventory_rows()
    legacy_rows = legacy_script_inventory_rows()

    write_csv(
        TABULAR_INVENTORY,
        tabular_rows,
        [
            "path",
            "table_kind",
            "sheet_name",
            "case_study",
            "bytes",
            "data_rows",
            "columns",
            "key_fields",
            "missing_cells",
            "columns_with_missing",
            "notes",
        ],
    )
    write_csv(
        SPATIAL_INVENTORY,
        spatial_rows,
        [
            "path",
            "member",
            "spatial_kind",
            "driver",
            "crs",
            "extent",
            "dimensions_or_features",
            "bands_or_layers",
            "case_study",
            "notes",
        ],
    )
    write_csv(
        LEGACY_SCRIPT_INVENTORY,
        legacy_rows,
        [
            "path",
            "category",
            "line_count",
            "purpose",
            "implied_inputs",
            "implied_outputs",
            "missing_refs",
            "known_defects",
            "phase1_relevance",
            "has_windows_setwd",
            "mentions_keras",
        ],
    )

    provisional_file_rows = file_inventory_rows()
    write_phase0_report(provisional_file_rows, tabular_rows, spatial_rows, legacy_rows)
    write_legacy_workflow_map(legacy_rows)
    write_phase1_questions()
    write_checksums()

    final_file_rows = file_inventory_rows()
    write_csv(
        FILE_INVENTORY,
        final_file_rows,
        ["path", "git_state", "role", "case_study", "suffix", "bytes", "mtime_epoch"],
    )

    print(f"Wrote {rel(PHASE0_REPORT)}")
    print(f"Wrote {rel(LEGACY_WORKFLOW_MAP)}")
    print(f"Wrote {rel(PHASE1_QUESTIONS)}")
    print(f"Wrote {rel(FILE_INVENTORY)} ({len(final_file_rows)} files)")
    print(f"Wrote {rel(TABULAR_INVENTORY)} ({len(tabular_rows)} rows)")
    print(f"Wrote {rel(SPATIAL_INVENTORY)} ({len(spatial_rows)} rows)")
    print(f"Wrote {rel(LEGACY_SCRIPT_INVENTORY)} ({len(legacy_rows)} scripts)")
    print(f"Wrote {rel(CHECKSUMS)}")


def main() -> int:
    os.chdir(REPO)
    try:
        generate()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
