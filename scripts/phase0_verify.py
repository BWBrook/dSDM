#!/usr/bin/env python3
"""Verify Phase 0 inventory artifacts without regenerating them."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import phase0_inventory as inventory


REPO = inventory.REPO

EXPECTED_FILES = [
    "docs/phase0/phase0_report.md",
    "docs/phase0/legacy_workflow_map.md",
    "docs/phase0/phase1_questions.md",
    "docs/plan/phase0_tactical_plan.md",
    "metadata/phase0/file_inventory.csv",
    "metadata/phase0/checksums.sha256",
    "metadata/phase0/tabular_inventory.csv",
    "metadata/phase0/spatial_inventory.csv",
    "metadata/phase0/legacy_script_inventory.csv",
    "scripts/phase0_inventory.py",
    "scripts/phase0_verify.py",
]

REQUIRED_TABULAR = {
    "temp/data/tas_sdm_data/tas_sdm_train.csv",
    "temp/data/tas_sdm_data/tas_sdm_test.csv",
    "temp/data/tas_sdm_data/tas_sdm_map.csv",
    "temp/data/se_sdm_data/se_train_data.csv",
    "temp/data/se_sdm_data/se_test_data.csv",
    "temp/data/se_sdm_data/se_sdm_map.csv",
    "temp/data/spatial/se_stack_metadata.xlsx",
}

REQUIRED_SPATIAL = {
    "temp/data/spatial/tas_stack.tif",
    "temp/data/spatial/tasmania_coast.shp",
    "temp/data/spatial/offshore_islands.kml",
    "data/input/spatial_polygons.zip",
}

REQUIRED_LEGACY = {
    "temp/src/0_galah_ALA.r",
    "temp/src/1_process_point_data.R",
    "temp/src/2_tas_sdm_data_cv_split.r",
    "temp/src/3_create_sdm_data.R",
    "temp/src/sdm_data_func.R",
    "temp/old_code/dsdm_func.R",
}

IGNORED_SENTINELS = [
    "temp/data/tas_sdm_data/tas_sdm_train.csv",
    "data/input/spatial_polygons.zip",
    "manuscript/build/dsdm_manuscript.pdf",
]


class VerifyError(RuntimeError):
    pass


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)


def verify_expected_files() -> None:
    missing = [path for path in EXPECTED_FILES if not (REPO / path).exists()]
    require(not missing, "Missing expected Phase 0 files: " + ", ".join(missing))


def verify_file_inventory() -> None:
    rows = read_csv_rows(inventory.FILE_INVENTORY)
    require(rows, "file_inventory.csv has no rows")
    paths = {row["path"] for row in rows}
    current = {rel(path) for path in inventory.iter_repo_files()}
    missing = sorted(current - paths)
    stale = sorted(paths - current)
    require(not missing, "file_inventory.csv missing current files: " + ", ".join(missing[:20]))
    require(not stale, "file_inventory.csv contains stale files: " + ", ".join(stale[:20]))


def verify_tabular_inventory() -> None:
    rows = read_csv_rows(inventory.TABULAR_INVENTORY)
    require(rows, "tabular_inventory.csv has no rows")
    paths = {row["path"] for row in rows}
    missing = sorted(REQUIRED_TABULAR - paths)
    require(not missing, "tabular_inventory.csv missing required rows: " + ", ".join(missing))
    for row in rows:
        require("path" in row and "columns" in row, "tabular inventory row missing required columns")


def verify_spatial_inventory() -> None:
    rows = read_csv_rows(inventory.SPATIAL_INVENTORY)
    require(rows, "spatial_inventory.csv has no rows")
    paths = {row["path"] for row in rows}
    missing = sorted(REQUIRED_SPATIAL - paths)
    require(not missing, "spatial_inventory.csv missing required rows: " + ", ".join(missing))
    require(
        any(row["member"].endswith("study_area.shp") for row in rows),
        "spatial_inventory.csv missing study_area.shp member inside spatial_polygons.zip",
    )


def verify_legacy_inventory() -> None:
    rows = read_csv_rows(inventory.LEGACY_SCRIPT_INVENTORY)
    require(rows, "legacy_script_inventory.csv has no rows")
    paths = {row["path"] for row in rows}
    missing = sorted(REQUIRED_LEGACY - paths)
    require(not missing, "legacy_script_inventory.csv missing required rows: " + ", ".join(missing))
    categories = {row["category"] for row in rows}
    for category in {"data_acquisition", "point_processing", "spatial_folds", "dsdm_helpers"}:
        require(category in categories, f"legacy_script_inventory.csv missing category {category}")


def verify_checksums() -> None:
    lines = [line for line in inventory.CHECKSUMS.read_text(encoding="utf-8").splitlines() if line.strip()]
    require(lines, "checksums.sha256 has no entries")
    for line in lines:
        parts = line.split(maxsplit=1)
        require(len(parts) == 2, f"Malformed checksum line: {line}")
        digest, path_text = parts
        require(len(digest) == 64, f"Checksum digest is not SHA-256 length: {line}")
        path = REPO / path_text.strip()
        require(path.exists(), f"Checksum points to missing file: {path_text}")
        rel_path = path_text.strip()
        require(not rel_path.startswith(".git/"), f"Checksum includes .git path: {rel_path}")
        require(not rel_path.startswith("manuscript/build/"), f"Checksum includes manuscript build output: {rel_path}")
        require(not rel_path.startswith("metadata/phase0/"), f"Checksum includes generated Phase 0 manifest: {rel_path}")


def verify_ignored_sentinels() -> None:
    existing = [path for path in IGNORED_SENTINELS if (REPO / path).exists()]
    require(existing, "No ignored sentinel files exist to check")
    for path in existing:
        proc = run(["git", "check-ignore", "-q", path])
        require(proc.returncode == 0, f"Bulky/generated sentinel is not ignored: {path}")


def verify_report_gate_language() -> None:
    text = inventory.PHASE0_REPORT.read_text(encoding="utf-8")
    for phrase in [
        "Known facts",
        "Inferred intent",
        "Known missing or broken pieces",
        "Barry signs off",
    ]:
        require(phrase in text, f"phase0_report.md missing gate/report phrase: {phrase}")


def main() -> int:
    try:
        verify_expected_files()
        verify_file_inventory()
        verify_tabular_inventory()
        verify_spatial_inventory()
        verify_legacy_inventory()
        verify_checksums()
        verify_ignored_sentinels()
        verify_report_gate_language()
    except VerifyError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: Phase 0 inventories and docs verify against current repo state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
