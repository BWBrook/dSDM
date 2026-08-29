# dSDM 30,000-foot strategic plan

Originally framed: 2026-05-27
Last revised: 2026-08-29

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
4. Use a southeastern-mainland-to-Tasmania mammal transfer experiment to test
   the method with more pretraining species, broader target ranges, and a hard
   island holdout supported by camera absences.
5. Freeze a versioned method after the Tasmanian prove-out and mammal transfer
   bridge.
6. Rebuild the SE Australia birds case from acquisition and cleanup onward,
   using it as a larger-scale transferability and stress test.
7. Version any method changes forced by the bird case and propagate them back
   through the Tasmanian case before making cross-case claims.
8. Substantially revise the manuscript only after all case studies and their
   synthesis are complete.
9. Keep code, data provenance, results generation, and scientific claims
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

### Geographic-transfer bridge: southeastern mammals to Tasmania

The original Tasmanian case is a deliberately hard development surface: only
seven other focal species are available for pretraining, most targets have high
island prevalence, and the island represents only the southern part of several
species' wider ranges. Before scaling to birds, run a cleaner geographic-
transfer experiment:

- use 21 observed southeastern mammal taxa as the target-group support cohort
  and 20 sufficiently observed taxa as potential response heads;
- for each of five shared targets, pretrain dSDM on the exact other 19 heads,
  fine-tune on the target's mainland response, and predict to Tasmania;
- fit conventional comparators on the target's mainland response only;
- use target-group backgrounds on the mainland, but only ALA/camera presence
  and camera survey-supported absence for Tasmania evaluation; and
- use one 24-predictor source and ontology across Bass Strait.

This is a mechanistically sharper transfer test and an intermediate scale
between the eight-species island prove-out and the many-species bird case.

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

Status: complete.

Goals 015–024 completed the provenance-rich source reconstruction and froze
the eight-species downstream contract, combined response and pseudoabsence
substrate, predictor stack, and supported 28-predictor `D_struct` domain.
Goal025 then froze the deterministic macro-stratified held-patch interpolation
design and five inner CV folds, including its training-only support and
topology diagnostics. These are canonical inputs to modelling; they are not
reselected by later phases.

The completed source layer for the Tasmanian mammal candidates and the
eight-species downstream contract includes:

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

Status: complete.

The completed analysis-ready substrate converts accepted sources through:

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

Goal026 is the final pre-model feature gate: six split-fitted transformations
are frozen for the Goal025 roles, with nominal dictionaries retained and
model-family encoding deferred. The versioned substrate and its diagnostics
are complete; scientific model fitting remains a later phase.

### Phase 3: Tasmanian conventional SDM baselines

Status: completed and sealed by Goal029; outer assessment remains unopened and
is deferred to the method-freeze evaluation.

Establish the accepted conventional reference set:

- intercept-only null, elastic-net logistic, random forest, histogram
  gradient-boosted trees, and shallow one-hidden-layer ANN;
- tune without contaminating the frozen outer test;
- evaluate continuous suitability first, then the predeclared inner-OOF
  threshold rule and prevalence-aware/spatial metrics;
- preserve fitted models, predictions, run manifests, and diagnostics once a
  separate implementation goal authorises execution.

These models define the empirical standard the new approach must improve on or
complement.

### Phase 4: Tasmanian feedforward dSDM development

Status: inner development and prespecified comparison completed through
Goal036. Goal031
proved the PyTorch engine on a synthetic vertical slice; Goal032 bound the
target-only path to the real outer-training substrate; Goal033 selected
`resmlp13`; Goal034 proved all six paths on a bounded real-data sentinel and
froze the three-worker Mac CPU route; and Goal035 repaired categorical support,
confirmed the architecture, and completed the 40-case six-path lifecycle.
Goal036 then aligned the neural and conventional OOF products, completed the
frozen inner analysis, and recommended carrying the complete predeclared panel
to a no-rescue, one-shot outer assessment. Conventional models were materially
stronger on the inner surface; multispecies transfer was small, heterogeneous,
and concentrated in some reduced-data cases.

Develop the proposed residual-MLP/shared-trunk dSDM as the central
methodological contribution:

- compare target-only, pooled legacy pretraining, species-aware masked
  multi-head frozen-encoder and full-fine-tune ladders, plus `q_linear` and
  `q_deep` scalar controls;
- use the shared architecture panel and three nested 25/50/100% target
  learning-curve ladders, with matched five-seed replication;
- compare fairly against the accepted conventional set under Goal027's
  leakage, threshold, aggregation, and null-result rules;
- retain the frozen optimiser, batch, architecture, runtime, and compute
  contracts while the production lifecycle is implemented and executed.

Goal035 retains real inner-OOF predictions privately. Goal036 publishes only
aggregate inner performance and freezes the next comparison boundary; no outer-
test claim has yet been made. The outer assessment remains sealed pending
validated full-training refits and an explicit one-shot opening decision.

### Phase 5: Tasmanian synthesis and stress diagnosis

Interpret the first case study and identify its limitations before broadening
the pretraining surface. Goals 036-039 found no convincing inner benefit from
the original multispecies transfer, larger networks, or a reduced BIOCLIM
panel. Retain that null result and the selected `resmlp13`/full-predictor
method; do not tune it away or open the original outer assessment merely to
seek a positive result.

### Phase 6: Southeastern mammals geographic-transfer substrate

Status: mainland development substrate complete through Goal 043.

Goals 040-042 froze the 21-taxon cohort, acquired and normalised 2001-2025 ALA
evidence, established the mainland X=3 target-group convention with X=2/X=5
sensitivities, built a common 24-predictor table for 1,125,325 cells, and
separated five Tasmania evaluation targets from mainland development. The next
Goal 043 then selected a 50 km five-fold mainland block design, rematerialised
all responses within split-authorised records, and froze five fold-specific
plus one reserved full-mainland predictor transform. The next step is a
mainland-only modelling protocol and compute preflight; Tasmania must remain
unopened and cannot inform training or tuning.

### Phase 7: Southeastern mammals modelling and bridge synthesis

Status: conventional mainland development benchmark complete through Goal 044;
Goal 045 dSDM production calibrated and pending detached execution; Tasmania
transfer evaluation remains pending.

Fit strong conventional target-only models and the prespecified dSDM transfer
arms, evaluate once in Tasmania, and determine whether additional pretraining
species and full-range mainland evidence materially alter transfer behaviour.
Retain the original Tasmanian result as the compact hard case, not a result to
be tuned away.

Goal 044 completed five-family mainland CV for the five transfer targets over
the frozen 25/50/100% learning ladder. Random forest was selected in 27/35
target-endpoint strata, histogram boosting in six, and elastic net in two.
The target-excluded `q_linear` community scalar supplied a small positive mean
AUC change (+0.00111 across strata), establishing a useful but modest scalar
community-information control. The separate Goal 045 dSDM arms and three-
architecture panel were frozen before these outcomes and must not be revised
post hoc to chase the conventional benchmark.

Goal 045 now binds those frozen arms to an executable mainland-only lifecycle.
Alien was unavailable at preflight, but a complete two-epoch Mac CPU canary
exercised all 277,571 leave-target-out auxiliary rows and all four target arms
in 11.76 seconds. The three-worker Mac CPU route is therefore adequate for the
resumable production run. This is compute evidence only; architecture and model
performance remain unresolved until production completes.

### Phase 8: Method-freeze checkpoint

Freeze the version that emerges from the original Tasmanian prove-out and the
southeastern-mammal geographic-transfer bridge. Record any null results and
limitations explicitly before birds.

### Phase 9: SE Australia birds acquisition and dataset construction

Repeat the source-acquisition and analysis-ready construction sequence for the
larger bird case:

- reacquire and clean primary occurrence data reproducibly;
- rebuild source and normalized contracts;
- construct the larger spatial and taxonomic modelling substrate;
- validate portability, memory, runtime, and compute routing;
- keep region and species details in configuration rather than Tasmanian
  hard-coding.

### Phase 10: SE Australia birds modelling and case synthesis

Apply the frozen method first, then evaluate its limits:

- rerun conventional baselines at continental scale;
- test feedforward dSDM transferability and computational scaling;
- assess performance across many species and prevalence regimes;
- distinguish genuine generalisation from case-specific tuning;
- version and propagate any justified method revisions;
- complete a second case-study synthesis.

### Phase 11: Cross-case synthesis, manuscript, and closure

Only after all three experimental stages:

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

The source and analysis-ready foundations and conventional modelling engine
for the Tasmanian prove-out are complete through Goal029. Goal030 reconciled
their authority boundary, Goal031 proved the dSDM engine synthetically, and
Goal032 completed real outer-training binding plus three-host compute
calibration. The frozen outer assessment remains unopened, so this is not an
ecological performance result or a claim of programme completion.

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

Goal026 is complete as the final pre-model feature gate. Its six deterministic
split transforms are fitted from all split-training `D_struct` map cells (not
pooled response cells), keeping the substrate species/response neutral and
aligned with the frozen domain. Continuous predictors use population SD;
categorical predictors remain nominal and model-family encoding is deferred.
Identity-bearing lazy materialisation, support diagnostics, exact upstream
bindings, and replayable receipts are frozen.

Goal027 documents the supervisor-approved Tasmanian modelling protocol: the
accepted conventional baselines, multi-head and scalar-`q` controls, nested
target learning curve, shared architecture and replication rules, primary
contrasts, and cross-case version boundary. Goals028--029 implemented and
sealed the five-family conventional engine. Goals031--034 established the
neural engine, exact stopping/replay lifecycle, de-identified real-data
boundary, selected `resmlp13`, proved all six paths on a real sentinel, and
froze a three-worker Mac CPU route without opening the outer assessment.
Goals035--039 then completed the full inner lifecycle and comparison, rejected
wide-network confirmation, and retained the full predictor panel. The small,
heterogeneous original multispecies signal did not become a convincing
Tasmanian transfer benefit; the outer assessment remains sealed.

The programme is now in the southeastern-mammal geographic-transfer bridge.
Goal040 froze and acquired a 21-taxon southeastern cohort, Goal041 built the
common 24-predictor mainland/Tasmania table, Goal042 froze 20 mainland response
heads plus camera-supported Tasmania evaluation for five shared targets, and
Goal043 completed mainland partitions, split-authorised responses, and
split-fitted transformations. The next tranche is the mainland-only modelling
protocol and compute preflight. Tasmania must remain unopened until model
development and selection are complete.
