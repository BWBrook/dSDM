# Phase 0 report: Preserve, inventory, orient

Date: 2026-05-27

## Gate status

Phase 0 evidence has been generated from the current repository state. The gate
is not complete until automated verification passes and Barry explicitly signs
off that this evidence is sufficient for detailed Phase 1 planning.

## Known facts

- Repository root: `/Users/bwbrook/papers/dSDM`
- Inventory files counted: 94
- Git states in inventory: {'tracked': 46, 'ignored': 48}
- Main roles in inventory: {'repo_file': 5, 'repo_scaffold': 13, 'input_payload': 1, 'planning_doc': 6, 'phase0_doc': 4, 'plan_doc': 1, 'manuscript_source': 9, 'metadata': 1, 'phase0_manifest': 4, 'phase0_helper': 2, 'legacy_reference': 3, 'legacy_processed_data': 14, 'legacy_spatial_data': 8, 'legacy_code': 22, 'source_code': 1}
- Legacy R scripts inventoried: 22
- Legacy categories: {'dsdm_preprocess': 1, 'dsdm_tuning': 1, 'dsdm_transfer': 4, 'dsdm_training': 1, 'evaluation': 2, 'dsdm_helpers': 1, 'unrelated_scratch': 1, 'data_acquisition': 1, 'point_processing': 1, 'data_combination': 1, 'spatial_folds': 1, 'predictor_formatting': 1, 'baseline_ml': 3, 'baseline_ml_helpers': 1, 'data_helpers': 1, 'orchestration': 1}
- Tabular resources inventoried: 20
- Spatial resources inventoried: 8
- Existing processed data are reference artifacts only, not canonical rebuild
  substrates.
- Tasmanian mammals are the Phase 1 proving-ground case study; SE Australia
  birds are the later scale-out case.

## Major tabular payloads

| path | table_kind | sheet_name | case_study | data_rows | columns | missing_cells |
| --- | --- | --- | --- | --- | --- | --- |
| temp/data/se_sdm_data/se_sdm_map.csv | csv |  | se_birds | 630677 | 87 | 0 |
| temp/data/se_sdm_data/se_test_data.csv | csv |  | se_birds | 424421 | 91 | 424421 |
| temp/data/se_sdm_data/se_train_data.csv | csv |  | se_birds | 2487312 | 91 | 0 |
| temp/data/spatial/se_stack_metadata.xlsx | xlsx_sheet | climate | se_birds | 19 | 2 |  |
| temp/data/spatial/se_stack_metadata.xlsx | xlsx_sheet | landscape | se_birds | 8 | 2 |  |
| temp/data/spatial/se_stack_metadata.xlsx | xlsx_sheet | landuse | se_birds | 139 | 8 |  |
| temp/data/spatial/se_stack_metadata.xlsx | xlsx_sheet | veg | se_birds | 105 | 4 |  |
| temp/data/spatial/se_stack_metadata.xlsx | xlsx_sheet | soil | se_birds | 14 | 2 |  |
| temp/data/spatial/se_stack_metadata.xlsx | xlsx_sheet | data_source | se_birds | 10 | 2 |  |
| temp/data/tas_sdm_data/tas_mammal_ala_pa.csv | csv |  | tas_mammals | 8791 | 4 | 0 |
| temp/data/tas_sdm_data/tas_sdm_map.csv | csv |  | tas_mammals | 71057 | 77 | 0 |
| temp/data/tas_sdm_data/tas_sdm_test.csv | csv |  | tas_mammals | 1036 | 81 | 1036 |
| temp/data/tas_sdm_data/tas_sdm_train.csv | csv |  | tas_mammals | 10489 | 81 | 0 |
| temp/data/tas_sdm_data/tascam_grid_pa.csv | csv |  | tas_mammals | 7803 | 4 | 0 |

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
!! .DS_Store
!! data/
!! manuscript/build/
!! scripts/__pycache__/
!! temp/
```

## Gate checklist

- [ ] Phase 0 manifests and docs exist.
- [ ] `python3 scripts/phase0_verify.py` passes.
- [ ] `make -C manuscript check` passes.
- [ ] Bulky payloads remain ignored.
- [ ] Barry signs off before detailed Phase 1 planning begins.
