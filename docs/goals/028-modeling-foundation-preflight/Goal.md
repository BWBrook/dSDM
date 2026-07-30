# Goal 028 — Modelling foundation and bounded preflight

## Objective

Implement and validate an executable, leakage-safe **target-only modelling
foundation** for the frozen Tasmanian design. Goal028 is an engineering
preflight, not a scientific analysis. It binds the Goal021 response, Goal024
`D_struct`, Goal025 spatial roles, Goal026 split transforms, and Goal027
protocol; creates deterministic split-specific target subsets; exercises the
target-only model adapters; and proves that inner-OOF selection, thresholding,
serialization, refitting, evidence publication, and tamper rejection work
without opening the real outer assessment.

The estimand inherited from Goal027 is a species-specific relative
habitat-suitability index over `D_struct`, conditional on the accepted
2001–2025 response construction and modelling design. Goal028 does not
estimate that quantity. It verifies machinery that a later authorised goal
may use to estimate it.

## Data-generating and observation contract

The atomic unit is one unique species × canonical grid-cell row with weight
exactly 1. `pa=1` denotes an included positive response. `pa=0` is retained
only when its source is known as survey-supported absence or pseudoabsence;
unknown zero provenance fails. Record multiplicity, camera effort, folds,
seeds, fractions, and subset ladders are not ecological replication. No
balancing, resampling, class weights, imputation, or response-driven feature
selection is permitted.

All 28 Goal026 predictors are primary. The accepted 25 continuous transforms
for `outer` and `cv_fold00`–`cv_fold04` are reused exactly. The three nominal
predictors are encoded within model family from inner-training rows only.
One-hot encoders use a neutral all-zero representation for a validation level
unseen in that inner-training set and record per-feature unseen-level counts.

## Required implementation

The completed foundation must provide:

- a tracked machine-readable run configuration with sections `identity`,
  `bindings`, `estimand`, `response`, `partitions`, `subsets`, `features`,
  `models`, `neural`, `selection`, `threshold`, `replication`, `artifacts`,
  `compute`, and `scope`;
- SHA-256 bindings to the exact Goal021, Goal024, Goal025, Goal026, and
  Goal027 tracked authorities and to the private upstream products by their
  already-frozen digests, without copying private paths into tracked evidence;
- deterministic target-row ladders built separately inside every permitted
  training split;
- one private ingestion factory that partitions the full upstream response
  internally and returns only an outer-training `SplitBroker`, an
  outer-training-key-restricted `FeatureProvider`, and a sealed `OuterVault`,
  making outer access structurally unavailable to every real Goal028 mode;
- adapters for intercept-only null, elastic-net logistic regression, penalised
  GAM, random forest, histogram gradient boosting, shallow one-hidden-layer
  ANN, and a parameterised target-only residual MLP;
- common inner-OOF prediction, candidate selection, training-only threshold
  selection, full-outer-training refit, serialization, semantic replay, and
  atomic aggregate/private publication;
- synthetic end-to-end, invariant, leakage, reproducibility, serialization,
  atomic-publication, semantic-replay, and tamper tests; and
- the bounded real-data preflight defined below.

## Deterministic target subsets

For each species and each permitted training split, create a single
deterministic prefix ordering using hierarchical proportional-deficit
round-robin:

1. canonicalise rows by `(species_id, grid_cell_id)` and reject duplicates;
2. use `pa_type` (`presence`, `survey_supported_absence`, or
   `pseudoabsence`) as response source and Goal025 `microcluster` as the
   nested stratum; assign source, microcluster, and row tie priorities as
   SHA-256 of the canonical tuple under master seed `dsdm-goal028-v1`;
3. at prefix position `k`, choose the response source with greatest
   `k * n_source / N - selected_source`;
4. within that source, choose the microcluster with greatest
   `k_source * n_source_cluster / n_source - selected_source_cluster`;
5. break each tie by its SHA-256 priority and take the next row in that
   source × microcluster bucket by row priority.

For training size `N`, use exact round-half-up endpoints
`K25=(N+2)//4`, `K50=(N+1)//2`, and `K100=N`. For `ladder00`, `ladder01`, and
`ladder02`, derive independent tie priorities from the ladder label, while
retaining the same algorithm. Within each ladder the 25% prefix is contained
in 50%, which is contained in 100%. Subsets are generated only from that
split's training rows; validation rows remain complete and unchanged. The
three 100% keys alias one canonical endpoint and are fitted only once.
Single-class training or validation tasks fail.

## Randomness

The canonical master seed is the literal UTF-8 string
`dsdm-goal028-v1`. Seed labels are `seed00`–`seed04`. Derive an unsigned
32-bit integer as the big-endian value of the first four bytes of SHA-256 over
these UTF-8 fields joined by ASCII unit separator (`\x1f`):

`master_seed, species_id, transform_id, fraction_id, ladder_id,
model_family, candidate_id, seed_label, purpose`.

Goal028 real preflight uses `seed00`; `seed01` is allowed only for the paired
neural replay check. Five-seed production inference is deferred.

## Model candidate registry

Candidate rows are explicit records, never an implicit Cartesian product.
Continuous inputs use Goal026 values; categorical one-hot state is fitted
inside each CV-training split. All conventional estimators run with one
estimator thread.

| Family | Candidate IDs and parameters |
|---|---|
| intercept | `null00`: empirical inner-training positive fraction, clipped to `[1e-7,1-1e-7]` |
| elastic-net logistic (`saga`, `max_iter=5000`, `tol=1e-6`) | `enet00 C=0.01,l1_ratio=0`; `enet01 0.03,0`; `enet02 0.1,0`; `enet03 0.03,0.5`; `enet04 0.1,0.5`; `enet05 0.3,0.5`; `enet06 0.03,1`; `enet07 0.1,1`; `enet08 0.3,1`; `enet09 1,0.5` |
| penalised GAM (`max_iter=500`, `tol=1e-5`) | `gam00 n_splines=6,lam=0.1`; `gam01 6,1`; `gam02 8,1`; `gam03 8,10`; `gam04 12,10`; each continuous term is cubic and each encoded categorical indicator is linear |
| random forest (`n_estimators=500`, `bootstrap=true`) | `rf00 max_features=sqrt,min_samples_leaf=1,max_depth=null`; `rf01 sqrt,3,null`; `rf02 sqrt,10,null`; `rf03 0.33,3,null`; `rf04 0.33,10,null`; `rf05 0.67,3,20`; `rf06 0.67,10,20` |
| histogram gradient boosting (`max_iter=300`, `early_stopping=false`) | `hgb00 learning_rate=0.03,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=0`; `hgb01 0.03,31,20,1`; `hgb02 0.05,15,20,1`; `hgb03 0.05,31,20,1`; `hgb04 0.05,31,50,1`; `hgb05 0.1,15,20,10`; `hgb06 0.1,31,50,10` |
| shallow ANN, native PyTorch (`max_epochs=300`, `patience=30`) | `ann00 width=32,dropout=0,weight_decay=0,lr=1e-3`; `ann01 32,0.1,1e-5,1e-3`; `ann02 64,0.1,1e-5,1e-3`; `ann03 64,0.2,1e-4,1e-3`; `ann04 128,0.2,1e-4,5e-4`; `ann05 128,0.3,1e-3,5e-4` |
| target-only residual MLP, native PyTorch (`activation=GELU`, `norm=LayerNorm`, `max_epochs=300`, `patience=30`) | `resmlp00 blocks=2,width=64,bottleneck=32,dropout=0.1,weight_decay=1e-5,lr=1e-3`; `resmlp01 3,128,32,0.2,1e-4,5e-4`; `resmlp02 4,128,64,0.3,1e-3,5e-4` |

The residual rows are engineering probes only. They do not select or freeze
the Goal027 final architecture panel.

## Neural OOF stopping firewall

For assessment fold `v`, set the neural stopping fold to
`s=(v+1) mod 5`. Within the permitted fraction/ladder endpoint, the
epoch-discovery fit uses endpoint rows outside both `v` and `s`, and the
stopping batch is the endpoint intersection with `s`. Determine `best_epoch`
from stopping loss only. Discard that fit, reinitialise the same architecture
with the same task seed, train on the complete permitted CV-training endpoint
(all endpoint rows outside `v`) for exactly `best_epoch`, and only then
predict assessment fold `v`. The assessment batch is passed only to
`predict_scores`; it must never be accepted by an adapter `fit` method.

For full outer-training refit, sort the five fold-specific `best_epoch` values
and use the lower-median order statistic `E[(len(E)-1)//2]`. Reinitialise with
the same task seed and train on the complete permitted outer-training endpoint
for exactly that many epochs, without validation or stopping labels.

Conventional convergence warnings or iteration-budget exhaustion are hard
failures. PyTorch hard failures are nonfinite loss, gradient, parameters, or
scores; optimiser failure; absence of a valid checkpoint; or replay failure.
Record `patience_stop` versus `max_epochs_reached`; reaching the maximum epoch
budget with a valid finite checkpoint is a warning, not itself a failure.

## Selection and threshold rules

Each candidate must yield exactly one finite OOF score per inner-training row,
with no gaps or duplicates. Candidate selection uses equal-weight mean-fold
ROC AUC. For each candidate, derive one threshold from its concatenated,
common-seed-averaged OOF scores; apply that threshold unchanged within each
fold and average the five fold TSS values with equal fold weight. ROC-AUC ties
use this `mean_fold_tss_at_oof_threshold`, then the lexicographically smallest
canonical `candidate_id`. Poor AUC is not a failure.

For the selected task, average OOF scores across the available common seeds.
Threshold candidates are the two finite boundary values and every finite
midpoint between adjacent distinct scores. A row is predicted positive iff
`score >= threshold`. Maximise TSS (equivalently BA), sort the finite
maximising candidates, and choose the lower-median order statistic
`M[(len(M)-1)//2]`; never take their arithmetic median. Recompute TSS at the
selected threshold and assert that it equals the maximum. Thresholding never
uses outer rows.

## OuterVault and authorisation boundary

The single private ingestion factory reads and partitions the full upstream
response internally. Its public return contains only an outer-training
`SplitBroker`, a `FeatureProvider` restricted to outer-training keys, and a
sealed `OuterVault`; `SplitBroker` never accepts or retains the combined
response. Any attempt to open, iterate, score, summarize, or expose real outer
rows increments `outer_attempted_open_count` and raises before returning data.
Successful opens increment `outer_open_count`. Every private task row, tracked
aggregate, semantic replay, and acceptance receipt records both counts. Real
acceptance requires `outer_attempted_open_count=0` and `outer_open_count=0`.

A future unlock requires a separately accepted, tracked authorisation that
binds an exact frozen run-manifest digest and repository commit. Goal028
creates no valid unlock token. A synthetic fake vault may exercise final-score
plumbing, but its manifest must state `synthetic=true`.

## Bounded real preflight

The real preflight is restricted to:

- `sarcophilus_harrisii`: 3,460 positive included rows among 3,573;
- `pseudocheirus_peregrinus`: 366 positive included rows among 1,083.

These ratios are **included-row positive fractions**, not ecological
prevalence.

For both species, build all three fractions and three ladder keys in every
permitted split. Exercise the cheap intercept adapter over the complete 3×3
fraction/ladder key path, aliasing the full endpoint. Exercise every adapter
on representative `25%/ladder00` and `100%/full` endpoints with this reduced
preflight registry:

`null00, enet03, enet07, gam02, rf03, hgb03, ann03, resmlp01, resmlp02`.

Use five inner folds, OOF prediction, candidate selection, thresholding,
serialization, full-outer-training refit, and replay. Use `seed00`, with
`seed01` only for the neural paired-replay check. Record convergence, runtime,
peak resident memory, and warnings. The Mac mini CPU is canonical.
Single-thread estimators plus between-task process parallelism are allowed.
An MPS benchmark is optional and diagnostic only; it cannot gate acceptance.
No remote job is authorised.

## Stop conditions

Stop and publish no partial destination if any task has leakage or outer
access, unknown zero provenance, duplicate species-cell rows, missing training
or validation class, nonfinite feature/score/parameter values, OOF gaps or
duplication, nonnested subsets, inconsistent 100% aliases, seed/subset pairing
mismatch, digest drift, semantic replay failure, irreproducibility outside the
declared tolerance, conventional nonconvergence, or a PyTorch hard failure.
`max_epochs_reached` with a valid finite checkpoint is a warning and is not
alone a stop condition.

## Explicit non-goals

Goal028 stops before:

- real outer prediction, scoring, metrics, or threshold application;
- fitted `q_linear` or `q_deep` surfaces;
- pooled, transferred, or multi-head models;
- final residual architecture screening or selection;
- pseudoabsence-removal or reduced-predictor sensitivities;
- maps, all-eight-species production runs, five-seed inference, headline
  model selection, primary contrasts, or ecological claims;
- Tasmania-to-birds transfer; and
- remote compute.

## Acceptance

Acceptance requires the exact configuration and bindings, full synthetic
end-to-end and tamper pass, bounded real preflight pass, zero attempted and
zero successful real outer access, complete private task provenance,
privacy-safe tracked aggregates, atomic publication, semantic replay, focused
and full tests, `uv lock --check`, compilation, and `git diff --check`.

Implementation agents may edit source, tests, configuration, dependency and
lock files, run `uv` installs and the runbook commands, and create ignored
private plus tracked aggregate Goal028 artefacts. They must not commit or push.
The dSDM orchestrator reviews and publishes only after independent acceptance.
