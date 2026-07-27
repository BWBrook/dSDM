# dSDM 30,000-foot strategic plan

Originally framed: 2026-05-27
Last revised: 2026-07-26

This is the canonical living roadmap for the full dSDM research programme. It
should be revisited at major scientific and implementation gates rather than
treated as a fixed schedule.

## Strategic commitment

The dSDM repo will be rebuilt Python-first.

The existing R code, processed CSVs, notes, manuscript draft, and previous SE
Australia bird work are important archaeological artifacts. They preserve
intent, assumptions, partial methods, and useful warnings. They are not
canonical implementation targets and should not be treated as an unblemished
workflow to reproduce.

The core scientific and software posture is:

1. Rebuild from primary data wherever practical.
2. Treat old processed outputs as comparison and reference artifacts, not
   truth.
3. Acquire nine Tasmanian mammal candidates, then develop and prove the
   downstream workflow on the eight-species contract fixed at Goal 019.
4. Freeze a versioned method after the Tasmanian prove-out.
5. Rebuild the SE Australia birds case from acquisition and cleanup onward,
   using it as a larger-scale transferability and stress test.
6. Version any method changes forced by the bird case and propagate them back
   through the Tasmanian case before making cross-case claims.
7. Substantially revise the manuscript only after both case studies and their
   synthesis are complete.
8. Keep code, data provenance, results generation, and scientific claims
   coupled throughout.

## Case-study sequence

### Case study 1: Tasmanian mammals

The Tasmanian mammals case is the development and prove-out surface because it
is bounded, ecologically meaningful, and computationally tractable. Goal 017/018
preserves nine acquisition candidates; Goal 019 fixes eight downstream focal
species:

- smaller spatial extent;
- nine immutable acquisition candidates and eight downstream focal species;
- a mixture of ALA occurrence evidence and camera survey-supported absences;
- real prevalence imbalance that reflects ecology rather than an artificial
  teaching example.

The complete sequence should be developed here: acquisition, cleanup,
analysis-ready dataset construction, conventional SDM baselines, feedforward
dSDM development, evaluation, and case-study synthesis.

### Method-freeze checkpoint

Before scaling to birds, freeze a versioned method specification containing:

- source and normalized-data contracts;
- pseudoabsence and survey-supported-absence rules;
- partitioning and leakage controls;
- predictor transformations;
- conventional baseline definitions;
- feedforward dSDM architecture and training rules;
- tuning boundaries, metrics, and success criteria;
- computational and reproducibility requirements.

The freeze is a scientific boundary, not a claim that learning must stop. If
the bird case exposes a material defect or scale limitation, revise the method
explicitly, increment its version, document the reason, and rerun affected
Tasmanian analyses. Do not quietly tune on the bird case while describing it as
a predeclared transferability assessment; document adaptation and rerun every
affected comparison.

### Case study 2: SE Australia birds

The SE Australia birds case is the scale, transferability, and generalisation
test:

- much larger spatial extent;
- many more focal species;
- substantially larger source and modelling datasets;
- a stronger test of computational scaling and model generality.

Earlier bird work in the repo is reference and archaeological evidence only.
The bird pipeline should restart from reproducible acquisition and data cleanup,
then repeat analysis-ready dataset construction, conventional modelling,
feedforward dSDM evaluation, and case-study synthesis.

## Phased programme

### Phase 0: Preserve, inventory, and orient

Status: complete.

Inventory the repository, legacy workflows, processed artifacts, manuscript
scaffold, missing materials, provenance gaps, and known defects. Use that
evidence to define the rebuild without treating legacy outputs as canonical.

### Phase 1: Tasmanian source acquisition and reconstruction

Status: active.

Goal025 has frozen a deterministic macro-stratified held-patch interpolation
design for the Goal024 `D_struct` substrate. Geometry and fold allocation are
response-independent; feasibility and ranking are deliberately
response/covariate-conditioned but pre-model. The complete prescribed seed
schedule, training-only support diagnostics, aggregate topology/class audit,
and SHA-bound private figure passed the dSDM orchestrator review on 2026-07-26.
The goal still authorises no fitted transformation or model.

Build the provenance-rich source layer for the Tasmanian mammal candidates and
the eight-species downstream contract:

- focal-species and taxon contracts;
- ALA field calibration, count census, and controlled acquisition;
- camera source staging and privacy-safe ingestion;
- raw snapshots, manifests, versions, and checksums;
- spatial boundary, grid, and predictor source validation.

Goals 015–017 established the maintained `galah-python` route, calibrated its
field contract and provider identity, and froze the complete nine-species
Tasmania 2001–2025 source snapshot. The acquisition contains 50,834
ALA-indexed records whose per-species files reconcile exactly to their
pre-download counts; raw-backed replay verifies schema, checksums, and complete
unique provider identifiers. These are source records, not independent
observations, abundance, occupancy, or an analysis-ready dataset.

### Phase 2: Tasmanian analysis-ready dataset construction

Convert accepted sources into a frozen modelling substrate:

- normalize identifiers, dates, coordinates, uncertainty, and provenance;
- assign eligible 0.01-degree grid cells;
- integrate presence and camera survey-supported-absence evidence;
- resolve duplicates and source conflicts;
- derive pseudoabsences under accepted ecological rules;
- apply boundary and species-specific island rules;
- extract and transform predictors;
- construct pre-model-frozen held-patch outer tests and spatial CV folds with
  explicit adjacency and buffer diagnostics;
- run a bounded QA and acceptance gate.

This phase ends with versioned, analysis-ready training, validation, test, and
mapping products. It does not fit scientific models.

### Phase 3: Tasmanian conventional SDM baselines

Establish credible traditional machine-learning reference models:

- define a compact, defensible baseline model set;
- tune without contaminating the frozen outer test;
- evaluate discrimination, calibration, prevalence effects, and spatial
  held-patch interpolation with spatial-block uncertainty;
- preserve fitted models, predictions, run manifests, and diagnostics.

These models define the empirical standard the new approach must improve on or
complement.

### Phase 4: Tasmanian feedforward dSDM development

Develop the proposed feedforward deep neural network as the central
methodological contribution:

- implement the model natively in Python and Keras 3, using legacy R-Keras
  code only as a record of design intent;
- establish architecture and training behaviour;
- test no-transfer, paired, sequential, and community transfer strategies;
- examine augmentation, regularisation, calibration, and class prevalence;
- run ablations and sensitivity analyses;
- compare fairly against conventional SDMs;
- route suitable GPU workloads to Alien or another deliberately selected
  compute target;
- iterate until the method is useful, reproducible, and scientifically
  defensible.

This is expected to be one of the largest and most research-intensive phases.

### Phase 5: Tasmanian synthesis and method freeze

Interpret the first case study, identify limitations, and freeze the first
transferable method version. Produce a concise case-study synthesis and claim
map, but do not substantially rewrite the manuscript as though the research
programme were complete.

### Phase 6: SE Australia birds acquisition and dataset construction

Repeat Phases 1 and 2 for the larger bird case:

- reacquire and clean primary occurrence data reproducibly;
- rebuild source and normalized contracts;
- construct the larger spatial and taxonomic modelling substrate;
- validate portability, memory, runtime, and compute routing;
- keep region and species details in configuration rather than Tasmanian
  hard-coding.

### Phase 7: SE Australia birds modelling and case synthesis

Apply the frozen method first, then evaluate its limits:

- rerun conventional baselines at continental scale;
- test feedforward dSDM transferability and computational scaling;
- assess performance across many species and prevalence regimes;
- distinguish genuine generalisation from case-specific tuning;
- version and propagate any justified method revisions;
- complete a second case-study synthesis.

### Phase 8: Cross-case synthesis, manuscript, and closure

Only after both case studies:

- compare ecological and methodological results across cases;
- decide which claims are general, conditional, or case-specific;
- substantially revise and rewrite the manuscript;
- regenerate all figures, tables, maps, and supplementary analyses;
- complete reproducibility, provenance, sensitivity, and release checks;
- prepare publication-ready code, data products, and documentation.

## Gate discipline

Detailed implementation planning remains goal-based and evidence-led. At each
gate, revise the live plan by asking:

1. What did we learn?
2. What broke or proved stale?
3. What assumptions should be retired?
4. What artifacts and decisions are now canonical?
5. What must be true before the next phase starts?

Normally complete one high-value implementation pass and one focused repair
for material defects, then return for scientific steering. Do not chase
submission-level polish during early pipeline development.

The method-freeze gate is especially important. It must make clear which
elements are fixed before the bird case, what evidence can justify revision,
and which analyses must be rerun after a change.

## Current position and next step

The programme remains early in Phase 1 and approximately 10–15% along the full
two-case-study journey, while being substantially further through the
conceptual foundations and ALA source reconstruction for the Tasmanian
prove-out.

Goals 017–024 are complete. The frozen 50,834-record ALA snapshot was replayed
into a provenance-preserving nine-candidate presence layer with 40,263 accepted
records and 6,629 species-grid cells. The private camera source was independently
normalised for the eight downstream focal species, and Goals 020–021 froze the
combined response and pseudoabsence substrate. Goal 022 froze the 32-band
predictor extraction; Goal 023 diagnosed support; Goal 024 rejected repair and
froze the supported 28-predictor structural domain: 71,023 of 74,073 map cells,
5,087 of 5,407 response cells, and 12,711 of 13,455 response rows. All excluded
cells/rows remain auditable and survey-supported absences remain first-class.

Goal025 is complete. Its complete prescribed seed schedule selected and froze
one pre-model held-patch outer/CV design, then recomputed categorical novelty
and continuous support within each species and training fold. Five dispersed
outer patches have no buffer, CV folds are scattered and multi-patch, and
rare-class/support limitations are machine-recorded for downstream
prevalence-aware and spatial-block uncertainty analysis. The v2 review receipt
passed against the unchanged frozen SVG and aggregate audit. No fitted
transformations or modelling were performed. Goal024 diagnostics remain
descriptive only; no repair or imputation is authorised. Legacy
`tascam_grid_pa.csv` remains comparison-only.

Goal026 is complete as the final pre-model feature gate. The six deterministic
split transforms are fitted from all split-training D_struct map cells (not
pooled response cells), keeping the substrate species/response neutral and
aligned with the frozen domain. Continuous predictors use population SD;
categorical predictors remain nominal and model-family encoding is deferred.
Identity-bearing lazy materialisation, precise marginal-envelope support
diagnostics, exact upstream bindings, and replayable aggregate/private
receipts are frozen. The next action is supervisor Phase 1 review before any
SDM fitting, tuning, prediction, or performance analysis.
