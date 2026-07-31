# Goal029 Conventional Baseline Production Design

## Purpose

Scale the accepted Goal028 modelling foundation to the complete conventional
Tasmanian panel while retaining a sealed outer assessment and making a long
run exactly resumable. This amended design incorporates the bounded pyGAM
recovery decision made after the first full candidate pass failed closed.

## Historical diagnosis

The old 2,016-candidate pass completed its candidate-state ledger but did not
produce an accepted production pair. The old GAM panel yielded 133/280
complete and 147/280 invalid candidate strata (122 nonconverged; 25 fit
failed), leaving only 32/56 GAM family strata viable. All non-GAM family
strata remained viable. No selected refit/publication proceeded and real
outer attempted/open counts remained `0/0`.

That stage remains diagnostic evidence under its old source/config identity.
The amended registry creates a clean run identity and cannot reuse it.

## Revised registry and gate

Goal029 uses six additive recovery IDs, leaving Goal028's `gam00`–`gam04`
payloads unchanged. The new IDs are absent from the shared canonical registry
and are accepted only within Goal029's exact-payload authority context:

- `gamr00`–`gamr02`: `n_splines=4`, `lam=10,100,1000`;
- `gamr03`–`gamr05`: `n_splines=6`, `lam=10,100,1000`; and
- all candidates: cubic splines, `max_iter=500`, `tol=1e-5`, `seed00`.

Before production authority can exist, all six candidates run in all 56
species × endpoint strata. One execution means five independent
inner-training fits plus a full outer-training refit, serialization, and
response-free challenge replay. The exact
`thylogale_billardierii/fraction100/full/gamr05/seed00` sentinel is repeated
independently, giving 337 candidate executions and 2,022 fit attempts.

Each inner fit predicts its actual held fold with the encoder learned from its
training fold. Prediction count, finiteness, and `[0,1]` range are validated
before only a semantic digest is retained. No held labels, metrics,
thresholds, row IDs, or prediction values enter gate evidence.

The gate is deliberately status-only. It retains sanitized diagnostic class,
category, and stage plus semantic hashes, but no assessment metrics,
predictions, thresholds, or partial performance. All 56 strata require at
least two complete candidates, including one with `lam>=100`; no candidate ID
is mandatory. Complete sentinel repeats must have identical stage/challenge
semantic digests. Identically invalid repeats establish only reproducibility,
not viability. The second sentinel replicate runs in a fresh separately
spawned single-worker executor with distinct private process-instance
evidence.

Every stage, complete or invalid, records only the bounded diagnostic fields:
iteration count, final-difference class, warning category, coefficient
finiteness, prediction finiteness, and prediction-range status. Known
fit/convergence/prediction failures are candidate-local; unknown,
protocol-authority, and schema failures stop.

The gate receipt is part of calibration authority. Production and publication
validation reject missing, failed, drifted, host/context-incompatible, or
status-inconsistent authority.

Gate-invalid candidates cross into production as blinded invalid overlays:
they have no OOF checkpoint, cannot compete in selection, and are audited
under the same rule. Gate-complete candidates must also complete production;
a subsequent invalid state is a hard contradiction rather than a permissible
local failure.

## Production architecture

The revised plan contains 336 family strata, 2,072 candidate strata, 7,224
candidate-seed leaves, 36,120 OOF fold units, 44,520 actual inner estimator
fits, and at most 1,008 selected refits.

It has three layers:

1. **Leaf execution.** One leaf is one candidate seed across all five inner
   assessment folds. It produces one complete OOF score per permitted
   outer-training row or one blinded failure receipt.
2. **Family reduction.** Seed leaves merge only when RowKeys, labels, folds,
   memberships, encoders, and required seed sets agree. Complete candidates
   compete within one species × endpoint × family.
3. **Selected refit.** The winner is refit once per required seed on permitted
   outer-training rows, serialized, and replayed on a response-free challenge.
   No held row is requested.

Subset membership is content addressed separately for every
species × endpoint × split. The five fold memberships and outer-training
refit membership are not collapsed.

## Failure and fallback model

A failed fold or seed invalidates that candidate locally and hides its partial
performance. `null00` remains mandatory. Elastic net, random forest, HGB, and
shallow ANN require their conservative anchor plus one other complete
candidate. GAM instead uses the two-complete/one-conservative-lambda rule
already proven by the gate. A selected model cannot silently fall back to a
runner-up.

This is the sole revised pyGAM attempt. If its gate fails, the next separately
authorized option is one bounded Python-only penalized-spline logistic family.
Failure there removes GAM globally. R fallback, broader grids, and numerical
relaxation are excluded.

## Resumption and provenance

Leaf checkpoints bind the controlled `src/dsdm_phase1/*.py` closure,
configuration, lock, runtime, host, upstream authorities, task, split
memberships, encoder state, and thread-policy evidence. A complete temporary
sibling is validated and fsynced before atomic rename. Resumption accepts only
an exact identity. Parallel workers share no mutable model state, and one host
owns a canonical run.

## Validation and publication

Staged artefact validation recomputes every plan identity, seed set, subset,
metric, threshold, selection, model digest, challenge replay, privacy rule,
and outer counter. A fresh cache-disabled source audit then reruns exactly
`ceil(0.05 × 7224)=362` leaves while covering every family stratum, candidate,
and seed.

Private and tracked trees receive core manifests before one acyclic pair
descriptor binds their digests and transaction ID. The final marker is written
last. Missing, partial, mismatched, unmarked, or extra-file pairs fail closed.

## Compute decision

Calibration proves four zero-fit spawned children and scans class support.
Two frozen `hgb04` leaves provide the workers-1/2 concurrency canary without
coupling worker selection to the family under recovery. The 30-leaf
representative panel then runs at workers 1, 2, and 4. Among trials with 6 GiB
free-memory headroom and no swap growth, the smallest count within `1.10` of
the fastest safe wall time is selected. The GAM gate runs once at that count.

Total calibration is 431 candidate executions and at most 2,597 estimator
fits. It is feasibility and execution evidence, not candidate selection or
scientific performance evaluation.
