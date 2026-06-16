# Phase 1 Primary-Data Acquisition Plan

Date: 2026-06-16

## Purpose

Phase 1 will rebuild the Tasmanian mammals primary-data acquisition pathway in
Python. The goal is to produce an auditable, provenance-rich data foundation for
later QA, modelling, and manuscript work.

This plan is a design contract for later implementation. It does not acquire
data, process records, choose scientific rules, or create modelling datasets.

## Boundaries

Phase 1 implementation should:

- target Tasmanian mammals first;
- keep SE Australia birds as later scale-out;
- rebuild from primary data wherever practical;
- treat old processed CSVs as comparison/reference artifacts only;
- preserve camera-trap true absences separately from ALA-derived presences and
  pseudoabsences;
- stop before modelling, metrics, maps, or manuscript result claims.

Phase 1 implementation must not decide Barry-level scientific choices by
default. Any unresolved biological, provenance, filtering, or acceptance rule
must be represented as an explicit decision before the relevant code path runs.

## Inherited Phase 0 Decisions

- The rebuild is Python-first.
- Tasmanian mammals are the proving-ground case study.
- The legacy R workflow is an intent map, not an implementation template.
- The old processed Tas and SE CSVs are useful for comparison, not canonical
  inputs.
- The old workflow implies these stages:
  1. acquire ALA records;
  2. snap records to a canonical grid;
  3. derive pseudoabsences;
  4. merge ALA-derived rows with camera-trap true presence/absence data;
  5. apply biologically justified offshore-island exclusions;
  6. construct spatial test/train/CV splits;
  7. extract predictors and persist transformation metadata.
- Phase 0 identified missing or broken pieces that Phase 1 should not paper
  over: missing fitted models, missing RDS augmented datasets, missing
  `make_sdm_sf()`, placeholder `_targets.R`, no active `renv`, no canonical
  primary camera-trap location, and unresolved `Thylogale billardierii`
  membership.

## Target Case Study

The Phase 1 implementation target is the Tasmanian mammals case study.

Expected focal group, pending Barry-level confirmation:

- `Thylogale billardierii`
- `Notamacropus rufogriseus`
- `Macropus giganteus`
- `Trichosurus vulpecula`
- `Pseudocheirus peregrinus`
- `Vombatus ursinus`
- `Sarcophilus harrisii`
- `Dasyurus maculatus`
- `Dasyurus viverrinus`

The inclusion of `Thylogale billardierii` must not be settled by an executor.
The old R vectors include it, but Phase 0 notes that the old species list CSV
omitted it while processed Tas modelling files include it.

## Proposed Python-First Workflow

The implementation should be organized as small, testable Python modules, with
names treated as provisional until the implementation goal chooses package
layout.

Recommended design-level modules:

- `config`: load versioned YAML/TOML configs and validate required decisions.
- `schemas`: define tabular schemas for raw, cleaned, gridded, combined, split,
  predictor, and manifest outputs.
- `species`: load the authoritative focal-species table and enforce scientific
  names, aliases, class, and inclusion status.
- `ala`: build ALA requests, save raw responses, and normalize selected fields.
- `camera`: ingest camera-trap primary data and normalize survey effort,
  presence, and true-absence evidence.
- `spatial`: load boundaries, grid, CRS, offshore-island polygons, and snapping
  rules.
- `pseudoabsence`: derive candidate pseudoabsence rows after the required
  decisions are present.
- `folds`: construct deterministic spatial split metadata after fold rules are
  accepted.
- `predictors`: extract covariates and persist scaler and categorical metadata.
- `manifests`: write run, input, output, checksum, and decision manifests.
- `qa`: run acceptance checks and produce gate reports.

Recommended workflow stages:

1. `species_contract`: validate focal-species config and decision status.
2. `source_contracts`: validate that ALA, camera-trap, spatial, and predictor
   source contracts are complete.
3. `acquire_raw_ala`: acquire raw ALA records only after filter decisions are
   made.
4. `ingest_camera`: ingest raw camera-trap data only after source and
   interpretation decisions are made.
5. `normalize_records`: standardize columns and preserve raw identifiers.
6. `snap_to_grid`: assign canonical grid cells with recorded distance and CRS.
7. `derive_pseudoabsence`: create ALA-derived pseudoabsences under accepted
   rules.
8. `combine_sources`: merge ALA-derived rows and camera rows while preserving
   source provenance and true-absence status.
9. `apply_spatial_rules`: apply accepted boundary, offshore-island, and cleaning
   rules with exclusion flags.
10. `build_splits`: create train/test/CV split manifests after spatial rules are
    accepted.
11. `extract_predictors`: join predictors and persist transformation metadata.
12. `qa_gate`: produce a Phase 1 acceptance report before any modelling begins.

## Source Data Contracts

### Focal Species Table

Required role: authoritative species membership and naming source.

Minimum fields:

- `species_id`
- `scientific_name`
- `accepted_name`
- `common_name`
- `class`
- `include_phase1`
- `decision_status`
- `decision_reference`
- `notes`

Acceptance requirements:

- every included species has one stable `species_id`;
- scientific names match ALA query names or have explicit aliases;
- `Thylogale billardierii` has an explicit decision status;
- any excluded legacy species has an exclusion reason.

### ALA Occurrence Records

Required role: citizen-science or occurrence-derived presence source, and
potential basis for ALA-derived pseudoabsence logic.

Minimum raw retention:

- complete raw response file or files;
- ALA query parameters;
- ALA package/API version or endpoint metadata if available;
- acquisition timestamp and operator;
- species query string and resolved taxon information;
- spatial filter geometry identifier;
- date, data-resource, record-quality, and field-selection settings.

Minimum normalized fields:

- source identifiers and dataset metadata;
- scientific name, accepted name, and matched focal species;
- event or observation date fields;
- raw longitude and latitude;
- cleaned longitude and latitude;
- coordinate uncertainty or precision fields when available;
- record quality flags and exclusion reasons;
- acquisition run id.

Unresolved decisions:

- exact ALA fields to retain;
- date bounds;
- data-resource filters;
- quality filters;
- whether and how to handle records with missing or imprecise coordinates;
- versioning strategy for changing live ALA results.

### Camera-Trap Primary Data

Required role: primary source for camera-trap presence and true absence.

Minimum raw retention:

- primary file path or source location;
- survey/site identifiers;
- camera deployment metadata;
- species detection/non-detection evidence;
- survey effort fields;
- timestamps or sampling windows;
- any source-specific QA flags.

Minimum normalized fields:

- `camera_site_id`
- `survey_id`
- `species_id`
- `scientific_name`
- `pa`
- `pa_type`
- `survey_effort`
- `survey_start`
- `survey_end`
- `raw_source_path`
- `source_record_id`

Unresolved decisions:

- where the primary camera-trap dataset lives;
- which fields define a true absence at grid-cell/species level;
- how survey effort gates true-absence eligibility;
- whether true absences and pseudoabsences are modelled, weighted, or reported
  differently.

### Spatial Sources

Required role: canonical study area, grid, snapping surface, and exclusion
geometry.

Minimum source contracts:

- Tasmania boundary source, CRS, date/version, and checksum;
- canonical grid source, CRS, resolution, cell-centre convention, and
  `grid_cell_id` construction rule;
- offshore-island polygon source and accepted island names/codes;
- coordinate-cleaning and snapping tolerance rules;
- output CRS and precision rules.

Unresolved decisions:

- canonical Tas grid definition;
- offshore-island exclusions by species;
- whether legacy manually chosen folds are reproduced, revised, or replaced;
- distance tolerances for snapping and exclusion.

### Predictor Sources

Required role: covariate extraction for later modelling substrate, not model
training during Phase 1 acquisition.

Minimum source contracts:

- predictor name;
- source file or endpoint;
- variable type: continuous, categorical, ordinal, binary, or derived;
- CRS, resolution, extent, and nodata handling;
- layer inclusion/exclusion decision;
- categorical level dictionary;
- transformation policy;
- checksum or source version.

Unresolved decisions:

- authoritative predictor stack and layer list;
- which legacy deleted layers remain excluded;
- categorical level authority;
- missingness tolerance;
- whether scaling/encoding parameters become first-class artifacts.

### Legacy Reference Artifacts

Required role: comparison only.

Legacy Tas files under `temp/data/tas_sdm_data/` should be used to compare row
counts, prevalence, spatial extent, schemas, and broad sanity checks. They must
not become canonical inputs for regenerated data.

## Required Provenance Columns

Every row-level product after normalization should preserve enough information
to reconstruct source, transformation, and decision history.

Recommended core columns:

- `run_id`
- `row_id`
- `species_id`
- `scientific_name`
- `accepted_name`
- `source`
- `source_record_id`
- `source_dataset_id`
- `source_dataset_name`
- `raw_source_path`
- `event_date`
- `survey_start`
- `survey_end`
- `survey_effort`
- `lon_raw`
- `lat_raw`
- `crs_raw`
- `lon_clean`
- `lat_clean`
- `coordinate_uncertainty_m`
- `grid_cell_id`
- `grid_lon`
- `grid_lat`
- `snap_distance_m`
- `pa`
- `pa_type`
- `absence_basis`
- `pseudoabsence_rule_id`
- `true_absence_rule_id`
- `spatial_rule_id`
- `predictor_schema_id`
- `split_id`
- `fold`
- `record_status`
- `exclusion_reason`
- `qa_flags`
- `decision_manifest_id`
- `input_manifest_id`

The exact final schema can be implemented with stricter types later, but Phase
1 should reject products that collapse `pa_type`, source provenance, or spatial
decision identity.

## Focal Species Contract

Implementation must start by loading an explicit species contract. It should
fail fast if any included species lacks:

- a stable id;
- a scientific name;
- an ALA query name or alias;
- a decision status;
- an inclusion/exclusion rationale.

The implementation should not infer species membership from old processed CSVs.
It may report differences between the accepted species contract and legacy
reference files.

`Thylogale billardierii` is a blocking decision before live acquisition because
it changes ALA queries, camera-trap rows, pseudoabsence derivation, row counts,
and downstream prevalence.

## ALA Acquisition Contract

Before any live ALA call, the implementation packet should require a complete
ALA acquisition config containing:

- accepted focal species table;
- spatial query geometry;
- date bounds;
- selected ALA fields;
- data-resource filters;
- record-quality filters;
- coordinate precision rules;
- raw-output destination;
- normalized-output destination;
- run id and manifest destination;
- retry/cache policy;
- expected license/citation metadata capture.

Acquisition outputs should include:

- raw ALA response files;
- normalized ALA occurrence table;
- per-species acquisition summary;
- query manifest;
- checksum manifest;
- exclusion/QA report.

Stop if live ALA behavior, authentication, rate limits, or upstream schema
changes prevent reproducible acquisition. Do not silently change filters to get
a run through.

## Camera-Trap Ingestion Contract

Before camera-trap ingestion, the implementation packet should require:

- primary dataset location;
- permitted local path or staged copy policy;
- schema mapping from raw fields to normalized fields;
- survey effort interpretation;
- rule for true absence at site/grid/species level;
- rule for duplicate detections or repeated surveys;
- privacy or sensitivity constraints;
- source checksum and run manifest.

Ingestion outputs should include:

- raw source manifest;
- normalized camera-trap table;
- site/grid summary;
- species by `pa_type` summary;
- true-absence rule report;
- QA flags and exclusions.

Stop if the primary camera-trap dataset is absent, ambiguous, or cannot support
true-absence interpretation without a Barry-level decision.

## Spatial Grid And Boundary Contract

The spatial contract should define:

- canonical boundary and CRS;
- canonical grid and grid-cell id;
- coordinate input CRS and output CRS;
- snap-to-grid algorithm;
- maximum allowed snap distance;
- duplicate grid-cell handling;
- offshore-island exclusion rule ids;
- spatial extent acceptance checks.

The old scripts used WGS84 and nearest-grid snapping, but Phase 1 should not
assume that this is authoritative until the grid and boundary decision is made.

All spatial transformations should write diagnostics:

- rows before and after boundary filtering;
- rows excluded by offshore-island rules;
- rows with missing or invalid coordinates;
- snap-distance distribution;
- duplicate grid-cell counts by species and source.

## Presence, True-Absence, And Pseudoabsence Contract

Phase 1 must distinguish:

- `presence`: accepted evidence that the target species was observed;
- `true_absence`: camera-trap non-detection that meets accepted effort and
  survey rules;
- `pseudoabsence`: derived non-target/background absence candidate from ALA or
  other occurrence context.

The old scripts suggest:

- candidate pseudoabsence sites require observations of at least three
  non-target species;
- pseudoabsences are separated from presences by a distance threshold;
- points are thinned spatially;
- human-activity classes are used to reduce sampling-bias imbalance.

These values are evidence, not accepted rules. The implementation must load
them from a decisioned config and record the corresponding rule ids.

Stop if any code path would merge true absences and pseudoabsences without
preserving `pa_type` and `absence_basis`.

## Predictor And Covariate Contract

Predictor extraction should happen only after source authority and spatial
rules are accepted. It should produce predictor-ready data and transformation
metadata, not train models.

Required outputs:

- predictor source manifest;
- extracted predictor table keyed by `grid_cell_id`;
- joined species/predictor table;
- continuous scaler parameters fit only on training data when splits exist;
- categorical level dictionary from accepted source scope;
- one-hot encoding schema;
- missingness report;
- predictor range report;
- checksum manifest.

The old scripts provide useful predictor names and transformation intent, but
the authoritative layer list, deleted layers, categorical levels, and nodata
policy remain decisions.

## Provenance And Manifest Requirements

Each run should write a manifest bundle, preferably as human-readable YAML or
JSON plus CSV summaries.

Required manifests:

- `run_manifest`: run id, timestamp, operator, git HEAD, command, config files,
  Python version, package lockfile hash if available.
- `decision_manifest`: decision ids, owner, status, and config values used.
- `input_manifest`: source files, source URLs where applicable, checksums,
  sizes, timestamps, and licenses.
- `output_manifest`: output paths, schemas, row counts, checksums, and status.
- `qa_manifest`: checks run, thresholds used, pass/fail, and report paths.
- `legacy_comparison_manifest`: comparison artifacts used and deltas observed.

The implementation should fail if a required decision is missing, stale, or
marked unresolved for the stage being run.

## QA And Acceptance Gates

Phase 1 implementation should be accepted only after an explicit QA report
passes.

Minimum gate checks:

- species contract is complete and decisioned;
- all raw source files or acquisitions have manifests and checksums;
- normalized tables match schema;
- no included row lacks source provenance;
- no included row lacks `pa_type`;
- ALA rows retain raw and cleaned coordinates;
- camera rows retain survey/site identifiers and effort evidence;
- all spatial rows are inside accepted boundary or have exclusion reasons;
- snap-distance summary is within accepted tolerance;
- duplicate grid-cell handling is documented;
- row counts by species, source, `pa`, `pa_type`, split, and fold are reported;
- prevalence and imbalance summaries are reported;
- pseudoabsence derivation parameters are recorded;
- true absences and pseudoabsences remain separable;
- predictor schema and levels are stable;
- train-fitted scalers are persisted and not fit on held-out rows;
- regenerated outputs have documented deltas from legacy reference artifacts;
- all outputs are reproducible under fixed seeds and unchanged inputs.

Gate-blocking tolerances should be decisioned before implementation. The plan
should not invent acceptable deltas from old CSVs.

## Smoke-Test Fixture Strategy

The first implementation goal should create small fixtures before touching live
ALA or bulky primary data.

Recommended fixture layers:

- synthetic focal-species table with two or three fake species;
- tiny synthetic ALA-like occurrence table;
- tiny synthetic camera-trap table with presence and true absence;
- tiny grid and boundary geometry;
- tiny offshore-island polygon;
- tiny predictor table with one continuous and one categorical variable;
- expected manifest and QA outputs.

Fixtures should be tracked only if they are small, non-sensitive, and clearly
synthetic or approved. Any real-data fixture requires `dSDM` approval and must
avoid sensitive locations unless Barry approves otherwise.

Smoke tests should prove:

- schema validation fails on missing decisions;
- source provenance survives normalization;
- true absence and pseudoabsence remain distinct;
- grid snapping is deterministic;
- duplicate handling is explicit;
- scaler and categorical schemas are persisted;
- QA reports expected row counts and flags.

## Implementation Sequence

Recommended sequence of future implementation goals:

1. Phase 1 contracts and fixtures:
   - create Python package skeleton, config schema, data schemas, manifest
     writers, and synthetic fixtures;
   - no live ALA or primary camera-trap data.
2. Focal species and decision config:
   - implement species contract loading;
   - block unresolved scientific decisions.
3. Spatial contract implementation:
   - implement boundary/grid loading, CRS checks, snapping, and diagnostics
     using fixtures first.
4. ALA acquisition dry-run design:
   - implement request construction and manifest writing without live calls, or
     with mocked responses.
5. Camera-trap ingestion:
   - implement source mapping after primary dataset location and interpretation
     rules are accepted.
6. Pseudoabsence and source-combination logic:
   - implement only after pseudoabsence and true-absence decisions are made.
7. Predictor extraction and transformation metadata:
   - implement after predictor authority and split/fold policy are accepted.
8. Full Tas Phase 1 acquisition run:
   - run only after contracts, decisions, fixtures, and dry-run checks pass.

## Risks And Stop Rules

Stop and return to `dSDM` or Barry if:

- focal species membership is unresolved at acquisition time;
- `Thylogale billardierii` inclusion remains undecided;
- ALA filters or date bounds are unspecified;
- the primary camera-trap source cannot be located;
- true-absence rules are not scientifically accepted;
- pseudoabsence parameters are missing or disputed;
- grid, boundary, offshore-island, or fold decisions are unresolved;
- predictor authority is unclear;
- implementation would need external service behavior not captured in the
  decision/config contract;
- sensitive data handling or licensing is unclear;
- QA tolerances cannot be chosen without scientific judgement.

## Handoff To First Implementation Goal

Recommended first implementation goal:

Create the Phase 1 Python contract scaffold and synthetic fixture suite.

That goal should add the minimal package/test/config structure needed to
validate species, source, spatial, provenance, and manifest contracts using
synthetic data only. It should not query ALA, read primary camera-trap data,
process legacy payloads, build modelling datasets, or choose scientific rules.

The first implementation success signal should be a small tracked fixture suite
and passing tests that prove unresolved decisions block execution before any
real data are touched.
