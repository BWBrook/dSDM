# Retained-full outer implementation

3 October 2026, Australia/Hobart. Fable's message 839 accepts the scientific
corrections and needs no further review before outer scores unless a fixed
definition changes. Barry explicitly instructed Astra to proceed. The existing
opening and compute-allocation authority applies; the prediction-before-response
boundary remains mandatory.

The implementation uses separate retained-training, response-free prediction,
closure and scoring entrypoints. Existing inner source, configuration and
accepted artifacts remain immutable. The implementation adds no learner search,
epoch discovery, stopping subset, calibration or outer-dependent choice.

## Seeds and replay

Reserve fold identifier `-1` for retained-full fitting. Keep the existing seed
functions and namespaces, replacing only the fold argument by `-1`:

- neural pretraining: `goal052-pretraining-v1`, block, -1, full,
  seawfb_scale, seed label;
- neural target: `goal052-target-v1`, target, 100, -1, seawfb_scale, seed label;
- conventional target: Goal051's target namespace, target, 100, -1, family,
  selected candidate, seed label;
- q: Goal051's q namespace, q_linear, block, -1, full.

Ordinary/q target fits share their seed integers. Neural transfer arms preserve
the native target-head reset at seed + 17 and native replay shuffle at seed +
100000. The selected residual architecture has zero dropout. Use native training
primitives at the accepted fixed epoch budgets, and retain every full fitted
state, including target heads. Check frozen shared states exactly.

## Data and manifests

Retained-full rows use all five retained folds, with existing eligibility and
whole-focal-block exclusions. Preserve native head-major row order, ascending
cell order within head, natural prevalence and equal total auxiliary-head
weights. Use the Goal050 retained-full transform for both retained training and
the complete three-region predictor domain. Preserve all 103 columns, including
imputed incomplete-predictor rows; insert standardized q after the 21 continuous
columns for augmented models.

Preserve float64 transformed predictors through conventional and q prediction;
the neural adapter performs its native float32 conversion. The preparation
reader's earlier reuse of the float32 engineering-canary encoder was corrected
before run preparation or fitting. Precision-sensitive synthetic tests cover
the parquet reader and its agreement with retained training encoding.

An immutable run plan records input/source hashes, complete fit identities,
seeds, budgets, row/head digests, feature order, domain identity and frozen OOF
thresholds before fitting. Each fitted q surface then supplies its target-specific
training mean and population SD. These values and the q-state hash enter the
target fit receipt before that target is trained. This is the necessary staged
ordering of the preparation requirement: q scaling cannot be calculated before
the retained-only q model exists. It does not use outer responses or change the
q definition.

Each leaf is resumable only under matching plan, task, runtime qualification and
file hashes. A partial checkpoint does not count as completion. Predictions
cover the identical full domain for each seed. Average probabilities over the
prescribed seeds, then form the fixed 50:50 fine-tuning/conventional ensemble.
Close and hash all 4,242 fitted models, all component and ensemble predictions,
thresholds and supporting receipts before the scoring entrypoint can load any
outer response membership or richness.

## Qualification and reporting

Synthetic tests cover native replay equivalence, full-retained data rules,
checkpoint corruption/incomplete closure and scoring with frozen thresholds.
Measure full-row runtime and memory on the selected execution host. Production
requires actual-host numerical and resource qualification, including the fitted
model save/reload prediction check. Select capacity from these measurements;
the completed inner campaign is not an outer runtime estimate.

This implementation qualifies CPU execution. The first host is Deep, using an
isolated source export and its existing Python environment. Test 24 single-thread
workers with identical synthetic inputs; profile the full retained rows in one
process before selecting production concurrency. Profile all three conventional
families, auxiliary pretraining, q and all four neural target arms. No production
worker count may exceed the measured memory limit or the tested concurrency.

The first actual Deep canary rejected a 12-byte difference in serialized ANN
file sizes. A separate 24-process diagnostic found no other repeated-receipt
difference. Preserve that failed attempt. Serialization size remains a resource
measurement; deterministic qualification compares exact scores and states,
including an explicit ANN weight digest. No numerical tolerance changed. Freeze
a fresh source-bound plan for run `outer-assessment-20261003-r2` before retrying.

The scorer retains the original common 73 and regional 88/122/134 panels,
X10 and X20 gates, all six registered contrasts and fixed thresholds. The
prospective richness diagnostics and exploratory AUC-only ensemble follow
`OuterDiagnostics-20261001.md`. An unexpected primary support or prediction
failure stops acceptance and is reported explicitly. No post-opening rescue,
threshold change or target deletion is allowed.

The next scientific discussion with Fable follows the completed outer scores.
An implementation-forced change to a fixed scientific definition must be raised
before using outer outcomes. Routine engineering qualification stays within the
approved assessment.

## Bounded execution and report rendering

`scripts/goal052_outer_supervise.py` runs the qualified q, pretraining, neural
and conventional stages, followed by closure and verification. A run-level lock
prevents concurrent supervisors; each attempt has a separate immutable manifest,
stage receipts and completion receipt. The controller enforces the selected
wall-time cap, a 16 GiB available-memory floor and a 200 GiB free-disk floor.
Failure stops the sequence and terminates the owned process group, including
descendants whose group leader has exited. It never invokes scoring. A failed
attempt is retained; a later attempt may reuse only verified fitting leaves.

`scripts/goal052_outer_report.py` renders an already-created score JSON to
Markdown, carrying its score, plan and closure identities. Tables preserve
panel denominators, missing values, nested regional attenuation, the fixed
ensemble and the arithmetic richness decomposition. Synthetic scoring fixtures
test the actual output schema. These two operational helpers do not change the
hash-bound scientific source or the frozen plan.

`scripts/goal052_outer_independent_audit.py` independently reconstructs the task
inventory and verifies source/input bindings, fitted leaves, qualifications,
seed means, the fixed ensemble and the complete prediction closure. It rejects
existing score files and any native response-access receipt. Run it before
transferring the canonical response source or invoking the scorer, and bind its
passing receipt to the exact plan and closure hashes.
