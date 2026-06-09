# Phase 1 questions from Phase 0 evidence

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
