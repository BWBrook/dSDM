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
Every feature batch carries the stable ordered feature names, per-column kind,
25-continuous-column count, and a feature-schema/order digest.

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
canonical external endpoints are `fraction25` and `fraction50` with
`ladder00`, `ladder01`, or `ladder02`, plus exactly
`fraction100/ladder=full`. `ladder00` is only the internal lookup alias used
to construct the full subset. `fraction100/ladder00` must never appear in a
`TaskKey`, `SelectionStratum`, receipt, manifest task, or fitted-model
identity. The full endpoint is fitted once. Single-class training or
validation tasks fail.

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
| penalised GAM (`max_iter=500`, `tol=1e-5`, `spline_order=3`) | `gam00 n_splines=6,lam=0.1`; `gam01 6,1`; `gam02 8,1`; `gam03 8,10`; `gam04 12,10`; each of the first 25 ordered continuous columns is a cubic spline term and every encoded categorical indicator is a linear term; the candidate `lam` is supplied explicitly to every spline and linear term |
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

The fraction/ladder endpoint `E_v` is rebuilt from the permitted CV-training
rows separately for every assessment fold `v`; no singular or global endpoint
may be reused across folds. Fit the categorical encoder once on complete
`E_v` and reuse it unchanged for the epoch-discovery rows, stopping rows,
same-seed exact replay, and assessment prediction. This deliberately permits
stopping-fold covariates but not stopping labels to influence encoding,
preserves identical feature dimensions, and matches the frozen Goal026
`cv_foldVV` transform. Fully nested preprocessing would require new upstream
transforms and is outside Goal028.

For full outer-training refit, sort the five fold-specific `best_epoch` values
and use the lower-median order statistic `E[(len(E)-1)//2]`. Reinitialise with
the same task seed and train on the complete permitted outer-training endpoint
for exactly that many epochs, without validation or stopping labels.

`best_epoch`, completed epoch counts, and exact refit epochs are integers in
`[1,300]`, never booleans or floats. Every neural fold persists a complete
`NeuralFoldReceipt`: canonical task identity, stopping fold, best epoch,
discovery `FitReport`, replay `FitReport`, and both initial-state digests.
`FitReport.initial_state_digest` records the state immediately after
deterministic initialisation. Discovery and replay digests must match. The
five receipts remain attached to the matching `FoldEpochs` and
`CandidateOOF`; full refit rejects missing, incomplete, or mixed-provenance
receipts.

For convergence-controlled elastic-net logistic and GAM only, convergence
warnings or a nonconverged iteration-budget exhaustion are hard failures. A
GAM that first reaches the final allowed iteration is accepted only when its
finite final difference is strictly below `tol`; missing/nonfinite traces or
coefficients remain hard failures. RF always executes its declared 500 trees and HGB its declared fixed 300 rounds; completion of
those fixed budgets is not iteration exhaustion. PyTorch hard failures are
nonfinite loss, gradient, parameters, or scores; optimiser failure; absence
of a valid checkpoint; or replay failure.
Record `patience_stop` versus `max_epochs_reached`; reaching the maximum epoch
budget with a valid finite checkpoint is a warning, not itself a failure.

## Exact neural execution contract

Neural inputs, targets, parameters, logits, and loss are `float32`; emitted
scores and all metrics are `float64`. Batch size is 128, effectively
`min(128,n)`, retaining the final partial batch with no gradient accumulation.
Rows start in canonical `RowKey` order. Each epoch uses `torch.randperm` from
a dedicated CPU `torch.Generator`; initialise/reset that generator once at the
start of each fit from the fit seed, then advance it with one `randperm` call
per epoch. Data-loader workers are zero.

The shallow ANN is exactly
`Linear(input,width) -> GELU -> Dropout(p) -> Linear(width,1)`, with no
normalisation. The residual MLP is exactly: initialise
`h=GELU(input_projection(x))`; for each block compute
`z=LayerNorm(h) -> Linear(width,bottleneck) -> GELU -> Dropout(p) ->
Linear(bottleneck,width)` and set `h=h+z`; emit
`Linear(width,1)(LayerNorm(h))`. There is no post-add dropout. Initialise every
linear weight Xavier-uniform with gain 1 and every linear bias to zero;
LayerNorm weight is 1 and bias is 0.

Use AdamW with `betas=(0.9,0.999)`, `eps=1e-8`, and
`amsgrad=false, foreach=false, fused=false`; use no scheduler or gradient
clipping. Epochs are completed passes numbered 1–300; there is no epoch 0 and
exact `k` means exactly `k` completed passes. After every discovery epoch,
evaluate the complete stopping batch under `no_grad` using unweighted BCE.
Use `min_delta=0`: only strictly lower finite loss improves, equal loss keeps
the earliest epoch, improvement resets patience, otherwise patience
increments, and stopping occurs at 30. If patience is reached at epoch 300,
status is `patience_stop`; otherwise completing epoch 300 is the warning
`max_epochs_reached`. Deep-copy only a finite best state to obtain
`best_epoch`, discard the discovery model, and perform a fresh same-seed
replay. Check every loss, gradient, parameter tensor, and emitted score for
finiteness.

## Selection and threshold rules

Each candidate must yield exactly one finite OOF score per inner-training row,
with no gaps or duplicates. Candidate selection uses equal-weight mean-fold
ROC AUC within the complete selection stratum
`species × fraction × ladder × model_family × identical ordered
selection-seed set`; tuning never crosses model families and residual probes
never compete as conventional baselines. Align scores by `RowKey`, average
across the identical declared selection seeds, compute each fold AUC from
those averaged scores, then equal-weight the five fold AUCs. Goal028 selection
uses only `seed00`; `seed01` is a paired neural replay diagnostic and never a
selection seed. For each candidate, derive one threshold from its
concatenated, selection-seed-averaged OOF scores; apply that threshold
unchanged within each fold and average the five fold TSS values with equal
fold weight. ROC-AUC ties use this `mean_fold_tss_at_oof_threshold`, then the
lexicographically smallest canonical `candidate_id`. Poor AUC is not a
failure.

Candidate selection recomputes every per-fold and aggregate AUC, threshold,
and TSS value from the stored OOF keys, labels, and per-seed scores; serialized
metric fields are evidence to verify, not trusted inputs. Residual candidates
may tune against other residual candidates within the `residual_mlp` family,
but remain excluded from conventional-baseline competition.

For the selected task, average OOF scores across the available common seeds.
Threshold candidates are the two finite boundary values and every finite
midpoint between adjacent distinct scores. When adjacent finite scores have no
representable floating-point midpoint strictly between them, use the upper
score as the candidate. A row is predicted positive iff `score >= threshold`.
Maximise TSS (equivalently BA), sort the finite
maximising candidates, and choose the lower-median order statistic
`M[(len(M)-1)//2]`; never take their arithmetic median. Recompute TSS at the
selected threshold and assert that it equals the maximum. Thresholding never
uses outer rows. This lower-median order statistic is Goal028's executable
clarification of Goal027's loose word “median”; it does not change the
scientific threshold policy.

## OuterVault and authorisation boundary

The single private ingestion factory digest-verifies the Goal024 canonical raw
predictor map, Goal025 response partition, and tracked Goal026 feature
contract/fit parameters; after partitioning responses, it reconstructs each
split-specific transformed feature batch internally. Goal026 did not
materialise duplicate transformed feature rows. There is no injected
`private_inputs.features` or equivalent escape hatch. Its public return
contains only an outer-training `SplitBroker`, a `FeatureProvider` retaining
only outer-training keys and values, and a sealed `OuterVault` within which
held response rows exist exclusively; `SplitBroker` never accepts or retains
the combined response. Any attempt to open, iterate, score, summarize, or expose real outer
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

For both species, internally build the three ladder prefixes in every
permitted split. Externally schedule only the six
`fraction25|fraction50 × ladder00|ladder01|ladder02` identities and the single
`fraction100/full` identity; the cheap intercept adapter exercises all seven
canonical keys, with the internal `fraction100/ladder00` lookup never exposed
as a task. Exercise every adapter on representative `fraction25/ladder00` and
`fraction100/full` endpoints with this reduced preflight registry:

`null00, enet03, enet07, gam01, rf03, hgb03, ann03, resmlp01, resmlp02`.
The real-preflight GAM representative is intentionally `gam01` (6 splines,
`lam=1`); `gam02` remains registered for synthetic family-plumbing coverage
only.

Use five inner folds, OOF prediction, candidate selection, thresholding,
serialization, full-outer-training refit, and replay. Use `seed00`, with
`seed01` only for the neural paired-replay check. Record convergence, runtime,
peak resident memory, and warnings. The Mac mini CPU is canonical.
Single-thread estimators plus between-task process parallelism are allowed.
An MPS benchmark is optional and diagnostic only; it cannot gate acceptance.
No remote job is authorised.

Every serialized model binds the feature-schema/order digest as well as the
transform, encoder, candidate, and model-payload digests. Neural full-refit
epoch inputs are exactly five integers per seed and candidate from matching
species/fraction/ladder/family provenance; they are never mixed across a
selection stratum. Conventional refits require no epoch input.

The frozen manifest supplies a separately trusted lowercase 64-character
SHA-256 for every model file. Model loading and semantic replay require that
external digest, verify the whole-file bytes first, parse and validate
envelope version and identity before unpickling, and bind payload identity to
feature schema/order, transform, encoder, candidate, fit seed, and runtime
versions. Embedded or recomputed self-hashes are consistency checks only and
are never authority. `replay_predictions` cannot run without the external
manifest digest.

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
