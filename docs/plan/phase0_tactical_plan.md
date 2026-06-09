# Phase 0 Tactical Plan: Preserve, Inventory, Orient

Date: 2026-05-27

## Summary

Phase 0 will produce an evidence-backed project map, not a new data pipeline.
It will keep old R code and current processed datasets as ignored
archaeological/reference artifacts, create tracked documentation plus
machine-readable inventories, and define a hard gate before any detailed Phase 1
data-acquisition plan is written.

Chosen defaults:

- Deliverables: docs plus machine-readable manifests.
- Legacy handling: summarize old artifacts in place; do not promote old scripts
  into a tracked archive.
- Gate: automated checks plus explicit user sign-off.

## Implementation Changes

Add a tracked Phase 0 workspace:

- `docs/phase0/phase0_report.md`: executive inventory, risks, known gaps, and
  gate status.
- `docs/phase0/legacy_workflow_map.md`: old-script intent map from ALA
  acquisition through modelling.
- `docs/phase0/phase1_questions.md`: evidence-backed questions Phase 1 must
  answer.
- `metadata/phase0/file_inventory.csv`: all tracked, ignored, and payload files,
  categorized by role.
- `metadata/phase0/checksums.sha256`: SHA-256 checksums for
  source/input/reference artifacts, excluding generated build/cache outputs.
- `metadata/phase0/tabular_inventory.csv`: CSV/XLSX row counts, columns, key
  fields, missingness summary, and case-study tags.
- `metadata/phase0/spatial_inventory.csv`: raster/vector type, CRS, extent,
  dimensions/features, and bands/layers.
- `metadata/phase0/legacy_script_inventory.csv`: old script purpose, implied
  inputs/outputs, missing refs, and known defects.

Add small reproducible inventory helpers:

- `scripts/phase0_inventory.py`: generates inventories from repo state using
  standard Python plus existing CLI tools.
- `scripts/phase0_verify.py`: validates expected inventories exist, parse
  cleanly, and match current file counts.
- No primary data acquisition, modelling, data conversion, or old-code cleanup
  in Phase 0.

Inventory scope:

- Include tracked repo scaffold, `manuscript/`, ignored `temp/`, ignored
  `data/input`, and current docs.
- Exclude `.git/`, `manuscript/build/`, runtime caches, and future generated
  outputs from checksums.
- Keep `temp/`, `data/`, and `manuscript/build/` ignored.

Analysis scope:

- Classify old R scripts into data acquisition, point processing, data
  combination, spatial folds, predictor formatting, baseline ML, dSDM, and
  evaluation.
- Document bugs/missing pieces already visible, including missing `R/`, missing
  `scripts/bootstrap.R`, missing `make_sdm_sf()`, placeholder targets, missing
  `renv.lock`, and absent fitted model/result artifacts.
- Summarize Tas mammals and SE birds separately, with Tas marked as the Phase 1
  proving-ground target.
- Mark old CSVs as comparison/reference artifacts only, not canonical modelling
  substrates.

## Test Plan

- Run `python3 scripts/phase0_inventory.py` and confirm all Phase 0 manifest
  files are regenerated.
- Run `python3 scripts/phase0_verify.py`; it must pass with:
  - all expected Phase 0 files present;
  - CSV manifests parseable;
  - checksum entries pointing to existing files;
  - ignored bulky payloads still ignored;
  - no generated build/cache outputs included in checksums.
- Run `make -C manuscript check` to confirm the manuscript scaffold remains
  healthy.
- Run `git status --short --ignored` and verify:
  - `temp/`, `data/input/`, and `manuscript/build/` remain ignored;
  - Phase 0 docs/manifests/scripts are visible as tracked candidates;
  - no large data files are accidentally unignored.
- Spot-check inventory counts against `find`/`du` outputs for `temp/data`,
  `data/input`, and tracked docs.

## Phase 0 Gate

Phase 0 passes only when:

- All Phase 0 docs and manifests exist and are generated from current repo
  state.
- Automated verification passes.
- The report clearly separates known facts, inferred intent, missing artifacts,
  and open questions.
- Phase 1 is not planned in detail beyond its required questions and acceptance
  needs.
- Barry explicitly signs off that the Phase 0 evidence is sufficient to begin
  detailed Phase 1 planning.

## Assumptions

- No commit/stage operation unless explicitly requested.
- No online ALA re-querying in Phase 0.
- No conversion of current processed CSVs into canonical Parquet/data products
  in Phase 0.
- No cleanup or deletion of legacy scaffold/R files in Phase 0.
- System Python and existing macOS CLI tools are sufficient for inventory
  generation; no new project environment is required yet.
