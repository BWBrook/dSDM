# dSDM 30,000-foot strategic plan

Originally framed: 2026-05-27
Last revised: 2026-07-24

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
3. Develop and prove the complete workflow on nine Tasmanian mammals first.
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

The nine-species Tasmanian mammals case is the development and prove-out
surface because it is bounded, ecologically meaningful, and computationally
tractable:

- smaller spatial extent;
- nine focal species;
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
an untouched transferability test.

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

Build the provenance-rich source layer for the nine Tasmanian mammals:

- focal-species and taxon contracts;
- ALA field calibration, count census, and controlled acquisition;
- camera source staging and privacy-safe ingestion;
- raw snapshots, manifests, versions, and checksums;
- spatial boundary, grid, and predictor source validation.

Goal 015 established that the maintained `galah-python` route is usable for
later acquisition design. Goal 016 is the offline field-contract calibration
that precedes the nine-species count census and full acquisition.

### Phase 2: Tasmanian analysis-ready dataset construction

Convert accepted sources into a frozen modelling substrate:

- normalize identifiers, dates, coordinates, uncertainty, and provenance;
- assign eligible 0.01-degree grid cells;
- integrate presence and camera survey-supported-absence evidence;
- resolve duplicates and source conflicts;
- derive pseudoabsences under accepted ecological rules;
- apply boundary and species-specific island rules;
- extract and transform predictors;
- construct leakage-safe outer tests and spatial CV folds;
- run a bounded QA and acceptance gate.

This phase ends with versioned, analysis-ready training, validation, test, and
mapping products. It does not fit scientific models.

### Phase 3: Tasmanian conventional SDM baselines

Establish credible traditional machine-learning reference models:

- define a compact, defensible baseline model set;
- tune without contaminating the frozen outer test;
- evaluate discrimination, calibration, prevalence effects, and spatial
  generalisation;
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

The programme is near the start of Phase 1 and approximately 10-15% along the
full two-case-study journey, while being substantially further through the
conceptual foundations for the Tasmanian prove-out.

The next goal is Goal 016: use the existing frozen 17-row Galah pilot offline
to calibrate the returned-field contract, quantify privacy-safe field
population and uniqueness, and decide whether the pipeline is ready for the
nine-species 2001-2025 count census. The implementation should already
separate generic acquisition logic from Tasmania-specific configuration so the
later bird rebuild can reuse the machinery.
