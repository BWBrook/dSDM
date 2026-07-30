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
  categorical encoding only on the corresponding CV-training rows. Unseen
  validation levels receive neutral all-zero one-hot values and audit counts.
- Treat one unique species-cell row as the unit and weight it 1. Unknown zero
  provenance fails. Do not balance, resample, or apply class weights.
- Build deterministic, split-specific nested 25/50/100 prefixes by the
  Goal028 hierarchical deficit rule. Leave validation membership unchanged.
  Alias and execute the full endpoint once.
- Use master seed `dsdm-goal028-v1` and canonical SHA-256-derived unsigned
  32-bit task seeds. Real preflight uses `seed00`; only paired-neural replay
  may add `seed01`.
- Use one private ingestion factory to partition the combined upstream
  response internally. It returns only an outer-training `SplitBroker`, an
  outer-training-key-restricted `FeatureProvider`, and a sealed `OuterVault`;
  the broker never accepts combined response rows. Goal028 creates no valid
  unlock. Real acceptance requires attempted and successful outer-open counts
  both to equal zero.
- Select candidates by equal-fold mean ROC AUC, then equal-fold mean TSS at
  one candidate-specific threshold derived from concatenated,
  common-seed-averaged OOF scores and applied unchanged to all five folds,
  then canonical ID. Classify `score >= threshold`; among sorted finite
  TSS/BA-maximising thresholds choose the lower-median order statistic and
  confirm it attains the maximum.
- Separate ignored private row/task/model artefacts from tracked aggregate
  evidence. Publish staged complete pairs atomically; fail on semantic replay
  or tamper.

## Neural stopping and refit decision

For assessment fold `v`, neural epoch discovery uses stopping fold
`(v+1) mod 5` from within the four CV-training folds. The discovery fit
excludes that stopping fold. After choosing `best_epoch`, reinitialise with
the same seed and fit the complete permitted CV-training endpoint for exactly
`best_epoch`; the assessment batch never enters `fit`. Full outer-training
refit uses the lower-median order statistic of the five fold-specific best
epochs and no validation labels.

Conventional convergence or iteration-budget warnings remain hard failures.
PyTorch fails on nonfinite computation or state, optimiser failure, no valid
checkpoint, or replay failure. `max_epochs_reached` with a valid finite
checkpoint is a recorded warning, not automatic failure.

## Candidate and scope decision

The complete conventional candidate registry and compact residual engineering
panel are frozen in [Goal.md](Goal.md). They are explicit rows, not Cartesian
products. The residual panel exists only to prove parameterisation,
serialization, paired seeds, and training plumbing. Goal027's larger shared
architecture panel and its scientific selection remain a later goal.

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
