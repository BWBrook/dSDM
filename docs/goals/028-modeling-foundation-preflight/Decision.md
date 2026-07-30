# Decision

Goal028 is authorised as an executable target-only foundation and bounded
engineering preflight. It is not authorised to produce scientific results.
The scientific estimand, response construction, `D_struct`, spatial
partition, split transforms, model families, target learning curve, and
outer-use rule remain those accepted in Goals021, 024, 025, 026, and 027.

## Frozen engineering decisions

- Use a `uv`-managed Python 3.12 environment.
- Use NumPy, SciPy, scikit-learn, and pyGAM for conventional models; native
  PyTorch is the sole neural backend; PyArrow writes private Parquet. Do not
  add Keras, TensorFlow, skorch, XGBoost, Optuna, or a workflow engine.
- Run the canonical preflight on Mac mini CPU. Estimators are single-threaded;
  independent task processes may run in parallel within the declared memory
  budget. MPS is optional diagnostic evidence and never acceptance-gating.
- Reuse Goal026 `cv_fold00`–`cv_fold04` transforms. Fit family-specific
  categorical encoding once on each complete split-specific
  fraction/ladder endpoint `E_v`, then reuse it unchanged for neural epoch
  discovery, stopping, exact replay, and assessment. Unseen assessment levels
  receive neutral all-zero one-hot values and audit counts. This uses
  stopping-fold covariates but not labels and does not claim fully nested
  preprocessing.
- Treat one unique species-cell row as the unit and weight it 1. Unknown zero
  provenance fails. Do not balance, resample, or apply class weights.
- Build deterministic, split-specific nested 25/50/100 prefixes by the
  Goal028 hierarchical deficit rule. Leave validation membership unchanged.
  External identity is fraction25/50 with ladder00/01/02 and
  fraction100/full only. `fraction100/ladder00` is an internal lookup, never a
  task or selection identity. Execute the full endpoint once.
- Use master seed `dsdm-goal028-v1` and canonical SHA-256-derived unsigned
  32-bit task seeds. Real preflight uses `seed00`; only paired-neural replay
  may add `seed01`.
- Use one private ingestion factory to partition the combined upstream
  response internally and reconstruct split-specific features from the
  digest-verified Goal024 raw predictor map plus Goal026 contract/fit
  parameters after Goal025 partitioning. It accepts no injected feature
  payload and returns only an outer-training `SplitBroker`, an
  outer-training-key/value-restricted `FeatureProvider`, and a sealed
  `OuterVault` containing held response rows; the broker never accepts
  combined response rows. Goal028 creates no valid unlock. Real acceptance
  requires attempted and successful outer-open counts both to equal zero.
- Select candidates by equal-fold mean ROC AUC, then equal-fold mean TSS at
  one candidate-specific threshold derived from concatenated,
  common-seed-averaged OOF scores and applied unchanged to all five folds,
  then canonical ID. Classify `score >= threshold`; among sorted finite
  TSS/BA-maximising thresholds choose the lower-median order statistic and
  confirm it attains the maximum. The lower-median rule is an executable
  clarification of Goal027's loose “median”, not a scientific-policy change.
- Separate ignored private row/task/model artefacts from tracked aggregate
  evidence. Publish staged complete pairs atomically; fail on semantic replay
  or tamper.

## Neural stopping and refit decision

For assessment fold `v`, neural epoch discovery uses stopping fold
`(v+1) mod 5` from within the four CV-training folds. The discovery fit
excludes that stopping fold. Build a distinct permitted endpoint `E_v` for
every assessment fold; no global endpoint is valid. After choosing
`best_epoch`, reinitialise with the same seed and fit complete `E_v` for
exactly `best_epoch`; the assessment batch never enters `fit`. Full
outer-training refit uses five fold-specific epoch integers from identical
seed/candidate/selection-stratum provenance, takes their lower median, and
uses no validation labels; conventional refits have no epoch input.

Convergence or iteration-budget warnings are hard failures for
convergence-controlled logistic/GAM only, not completion of RF's fixed 500
trees or HGB's fixed 300 rounds.
PyTorch fails on nonfinite computation or state, optimiser failure, no valid
checkpoint, or replay failure. `max_epochs_reached` with a valid finite
checkpoint is a recorded warning, not automatic failure.

Every neural `FitReport` records `initial_state_digest`. Each fold retains a
complete `NeuralFoldReceipt` containing task, stopping fold, integer best
epoch, discovery/replay reports, and equal discovery/replay initial-state
digests. The five matching receipts remain in `FoldEpochs` and `CandidateOOF`
and are mandatory full-refit provenance.

Neural execution is fully declared in [Goal.md](Goal.md): deterministic
canonical-row batching, fixed float types and initialisation, exact shallow
and residual graphs, fixed AdamW settings, and exact stopping semantics.
Feature batches and serialized models bind stable feature-schema/order
metadata and digest.

## Candidate and scope decision

The complete conventional candidate registry and compact residual engineering
panel are frozen in [Goal.md](Goal.md). They are explicit rows, not Cartesian
products. The residual panel exists only to prove parameterisation,
serialization, paired seeds, and training plumbing. Goal027's larger shared
architecture panel and its scientific selection remain a later goal.

Candidate tuning is confined to
`species × fraction × ladder × model_family × identical ordered
selection-seed set`. OOF scores align by `RowKey` and average across declared
selection seeds before fold AUC and equal-fold aggregation. Goal028 selection
uses `seed00`; `seed01` remains replay-only. Residual candidates may tune
within their own family but never enter conventional-baseline competition.
Selection recomputes every fold and aggregate metric from OOF evidence rather
than trusting stored metric fields.

### Goal028 real-preflight GAM repair

The first real Task 9 attempt was fail-closed on
`pseudocheirus_peregrinus/fraction25/ladder00/gam02/seed00`, inner `fold01`:
the 8-spline, `lam=1` fit exhausted 500 iterations with final difference
`0.406` versus `1e-5`, alongside convergence/overflow warnings. The finite
coefficients do not make that fit acceptable. Independent checks showed the
registered `gam01` (6 splines, `lam=1`) converged on all 20 real GAM inner-fold
checks, while `gam03` did not. The real-preflight representative is therefore
bounded to `gam01`; the full registry, model family, predictors, folds,
thresholds, transforms, seeds, outer boundary, and production policy are
unchanged. Synthetic family-plumbing coverage retains `gam02` unchanged.

For GAM convergence, a fit is accepted only with finite coefficients and a
nonempty, finite `diffs` trace whose final value is strictly below `tol`, and
without convergence/overflow/divide warnings. Reaching exactly
`max_iter` is accepted only when that final tolerance condition is already
met; the observed `gam02` failure remains a hard stop. The bounded retry gate
must exercise the failed fold twice, all four real GAM strata across five OOF
fits, and four outer-training refit/serialization/replay paths, privately and
with attempted/open outer-vault counts `0/0`. It must not run or publish the
full 46-stratum real preflight.

Adjacent-score threshold candidates use the upper score when no
floating-point midpoint is representable. This and the lower-median rule are
executable clarifications, not scientific-policy changes.

## Trusted model replay decision

The frozen manifest is the authority for a separate lowercase model-file
SHA-256. Loading validates whole-file bytes and envelope identity before
unpickling, then binds payload identity to schema/order, transform, encoder,
candidate, fit seed, and runtime versions. Embedded self-hashes are not
authority. Semantic replay requires the external manifest digest explicitly.

The real preflight is limited to `sarcophilus_harrisii` and
`pseudocheirus_peregrinus`. Their stated counts are included-row positive
fractions, not prevalence. Poor discrimination is not a failed preflight;
leakage, invalid tasks, conventional nonconvergence, neural hard failure, or
irreproducible replay are failures.

## Publication decision

The executor may implement, install through `uv`, test, and generate the
Goal028 artefacts, but may not commit or push. The dSDM orchestrator must
review the source, raw private receipts locally, aggregate tracked evidence,
full validation replay, and repository diff before publication.

No fitted model, prediction, threshold, AUC, TSS, or ecological inference is
accepted by this design checkpoint.

## Deferred pre-outer-use hardening gate

Before any outer unlock, scoring, or map production, validation must bind to
the final commit/tree and include either deterministic estimator/state digests
or frozen, non-assessment challenge-grid predictions spanning map-domain
features. The Goal025 dual-runtime exception remains explicit. Consumers
must validate both publication destinations, or validate a transaction marker
covering both. This gate is deferred and nonblocking for Goal028 engineering
acceptance.
