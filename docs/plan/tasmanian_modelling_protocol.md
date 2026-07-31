# Tasmanian modelling protocol (version 0.1)

**Authority and status.** This is the Barry-approved design freeze dated
2026-07-30. Goal027 records scientific policy; Goals028--029 bind and seal the
conventional implementation. The frozen outer assessment remains unopened,
so this engineering/provenance milestone makes no ecological performance
claim. Later execution details may refine implementation, but cannot silently
change this protocol.

## Estimand and response domain

For each of the eight Goal019 focal species, the primary output is a
species-specific **relative habitat-suitability index**, scaled 0--1, over the
Goal024 `D_struct` domain. It is conditional on the accepted 2001--2025
response construction and modelling design. It is not occupancy, abundance,
true prevalence, a probability of occurrence, or inference outside `D_struct`.
Endpoints are scores, not literal impossible/certain states, and absolute
scores are not automatically comparable between species.

The atomic response is one resolved species x canonical 0.01-degree grid-cell
row. Goal020--021 presence, survey-supported-absence, and pseudoabsence rules
remain authoritative. Unknown species-cell combinations are masked. Every
species row sharing a cell inherits the same frozen spatial role from
Goal025; record multiplicity is never a weight. Survey-supported absences and
pseudoabsences are equal-weight zeros in primary target models, with source
provenance retained and no class balancing. Every resolved target
species-cell row has weight 1, including presence and both zero sources;
camera effort and record multiplicity never increase its weight.

## Spatial nesting and leakage control

Goal025's outer union is a pre-model-frozen held-patch assessment of spatial
interpolation within `D_struct`, not independent or external transfer. Patches
touch training and have no buffer. The outer set is used once, for final
scoring. Five prescribed CV folds are the inner selection surface. Every
data-dependent operation--preprocessing and encoding, auxiliary construction,
target subsets, tuning, early stopping, architecture/model selection, and
thresholding--uses outer-training data only. Results are reported per patch
and pooled.

## Metrics and thresholding

Continuous suitability is primary. A secondary binary result is produced per
species, model, fraction, and subset ladder from averaged inner out-of-fold
(OOF) training scores only: choose the threshold maximising TSS/BA, breaking
finite ties by their median. Apply that threshold unchanged to the outer
predictions; the outer set never selects a threshold. Report MCC,
sensitivity/specificity, and confusion counts as supplementary diagnostics,
including threshold variability. Co-primary evaluation metrics are ROC AUC
and TSS; PR AUC is reported but is not headline. For any held patch lacking a
required class, report per-patch AUC/TSS/MCC as NA with the class counts; do not
pool, resample, or manufacture a class to fill the gap. No arbitrary
effect-size threshold is imposed.

## Absence sensitivity and anti-circularity

Primary target models include survey-supported absences and pseudoabsences
equally. A bounded pseudoabsence-removal sensitivity refit is run for the
full multi-head dSDM, its matched target-only MLP, and the best conventional
model. It compares suitability rankings/maps plus ROC AUC, TSS, MCC, and
source-specific specificity with counts. For every leave-target-out auxiliary
pretraining operation and every `q` surface, pseudoabsence rows are excluded
entirely: use auxiliary presences plus camera survey-supported absences only,
with species-balanced loss/contribution while retaining within-species
imbalance. This is the executable anti-circularity rule.

## Predictors and conventional baselines

All 28 predictors are primary. Transformations are fitted within each split;
encoding is model-appropriate. Response-driven stepwise or wrapper selection
is prohibited; use regularisation. Correlated importance is grouped or
conditional. A reduced, ecologically defensible subset is sensitivity-only and
is allowed only for the leading conventional model and dSDM.

The final conventional set is: intercept-only null, elastic-net logistic,
random forest, histogram gradient-boosted trees, and a shallow
one-hidden-layer ANN. Penalised GAM was prospectively removed after two
bounded feasibility attempts failed the all-strata rule; successful strata
were not retained selectively. MARS remains parked as a future idea and was
not substituted. A deep single-species residual MLP is a direct no-transfer
control, not a conventional model. MaxEnt and SVM are omitted from primary
analyses; BIOCLIM is a possible later historical benchmark. No large primary
ensemble is planned.

## Community controls and dSDM ladder

`q_linear` is the scalar output of a species-balanced pooled elastic-net
logistic model on seven auxiliary species, using X only and omitting species
identity. `q_deep` is the analogous scalar from a pooled single-head nonlinear
MLP, also omitting species identity. Both are target-excluded,
outer-training/CV-training-only, pseudoabsence-free, and mask unknowns. Supply
each split-fitted scalar as a covariate to the same downstream target learner.
Initially compare X, X+`q_linear`,
X+`q_deep`, and the full transferred representation in the leading
conventional learner and a matched target MLP. Interpret gains respectively as
community gradient, nonlinear scalar, or representation beyond a scalar.

The dSDM ladder is:

1. target-only deep residual MLP with random initialisation;
2. pooled legacy community pretraining followed by target fine-tuning;
3. species-aware masked multi-head shared trunk with frozen encoder and new
   target head;
4. the same multi-head model with full target fine-tuning; and
5. the scalar `q` controls above.

The primary innovation is multi-head full fine-tuning. Paired/sequential
legacy transfer is pruned, and spatial augmentation is parked rather than a
core analysis or sensitivity. Use standard dropout, weight decay, and early
stopping only.

## Target learning curve and architecture

Use 25%, 50%, and 100% of target outer-training species-cell rows in three
deterministic nested ladders (25 within 50 within 100), representative of
spatial, class, and negative-source structure and shared across all models.
The 100% endpoint is one endpoint, not three replicates. Auxiliary seven-
species data remain complete within their allowed split; validation and outer
sets are unchanged. Do not introduce 10% initially.

Use a modern residual MLP/shared trunk with a fixed bounded candidate panel:
approximately 20--30 predeclared space-filling candidates around 2/3/4
blocks, widths 64/128/256, constant residual/simple taper, bottlenecks
16/32/64, bounded dropout and weight decay, and one initial activation/norm
choice. A reduced-budget one-seed screen selects a shortlist; the top 3--4
then run all five folds x three common seeds. Select one shared architecture by
species-balanced aggregate ROC-AUC rank, TSS as tie-break, entirely inside
outer-training. A descriptive leave-one-target-out ranking-stability audit may
flag fragility; if a target drives the winner, flag that instability and do not
use the outer set. Freeze the architecture across
targets, target-only/pretrained/fractions/pooled/multi-head. Conventional
models remain strongly tuned per species. FT-Transformer, TabPFN, TabM, CNN,
and GNN are follow-on options only.

## Matched replication and outcomes

Target-only and transferred MLPs share architecture, target head,
preprocessing, optimisation budget, stopping rule, common seeds, and target
subsets; they differ only in initialisation/representation. `q` models use the
same downstream learner. Exact optimiser, batch, and range manifests must be
predeclared before execution and matched where required.

Frozen final stochastic models use five common seeds. The target curve has
three nested ladders; reuse auxiliary pretraining across fractions where valid
and pair identical seeds/subsets. Average five seed scores for final
predictions while retaining individual seeds. Thresholds use the corresponding
averaged OOF scores. Seeds, folds, and nested fractions are not independent
ecological replicates.

At each 25/50/100% fraction and subset ladder, select the best conventional
model separately for each species using inner-CV ROC-AUC rank, with TSS as the
tie-break; the outer set never selects it. Report all conventional results,
whether or not one is selected as the best. Primary contrasts are: (a) full
multi-head fine-tune versus matched target-only MLP; (b) full multi-head
versus target MLP + `q_deep`; and (c) full multi-head versus that separately
selected best conventional model. A gain must exceed fold/seed noise, recur
across species (especially reduced fractions), and not systematically degrade
outer performance. A null is publishable and informative; no goalpost
movement is permitted.

Report all eight species. Species x outer patch x ladder is paired evidence,
not independent replication. Report pooled outer metrics from concatenated
held-patch predictions and every held patch separately; cross-species medians
are descriptive only. Do not use naive row bootstrap, p-values treating
folds/seeds/rows as independent, or outer selection.

## Cross-case boundary and residual risks

Tasmania is a bounded low-auxiliary, high-prevalence, within-range stress test.
A failure is a genuine null for that regime, not general falsification. Birds
are the preplanned larger-scale/generalisation test, not a rescue. Freeze this
Tasmanian method before birds; any bird-forced change is versioned and reruns
affected Tasmanian analyses. The bounded auxiliary-species-number learning
curve is deferred to birds. Because architecture may be developed with
Tasmanian inner target evidence, the bird frozen-architecture application is
the stronger test and is not species-naive.

Declare, rather than solve at this design gate, the residual risks of mixed
zero provenance and imperfect detection, high prevalence and rare negatives,
within-range/domain conditionality, spatial dependence and touching patches,
only eight species, and architecture-selection uncertainty.

## Implementation boundary

Goal027 authorises the scientific protocol. Goals028--029 bind the conventional
data products, exact candidate grids, runtime manifests, deterministic seeds,
software versions, and acceptance checks without changing that policy. Goal029
seals conventional engineering and provenance only: its private fitted models
remain off Git, the frozen outer assessment remains unopened, and no metric or
ecological performance result is claimed here. Phase 4 requires a separate
implementation gate.
