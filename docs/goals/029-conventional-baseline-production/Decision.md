# Decision

Goal029 implements the frozen conventional panel without changing the
Goal027 estimand or using the outer assessment. The exact executable contract
is [`config/conventional_baseline_production.json`](../../../config/conventional_baseline_production.json).

## Failed-run interpretation

The old run was a useful fail-closed diagnosis, not a production result. It
assigned terminal states to all 2,016 old candidate strata, while the GAM
family produced 133/280 complete and 147/280 invalid candidate strata
(122 nonconverged; 25 fit failed). Only 32/56 GAM family strata satisfied the
old anchor-plus-quorum rule. All non-GAM family strata were viable. Selection
publication and selected refits did not proceed, and the real outer vault
remained untouched at attempted/open `0/0`.

The retained old stage is not resumed into the revised run because its
candidate registry and source/config identities are superseded. The amended
contract yields a clean, independently identified run.

## Revised GAM recovery decision

Barry authorised exactly one revised pyGAM attempt:

| ID | `n_splines` | `lam` |
|---|---:|---:|
| `gamr00` | 4 | 10 |
| `gamr01` | 4 | 100 |
| `gamr02` | 4 | 1,000 |
| `gamr03` | 6 | 10 |
| `gamr04` | 6 | 100 |
| `gamr05` | 6 | 1,000 |

All six use cubic splines (`spline_order=3`), `max_iter=500`, and
`tol=1e-5`. This is a conservative regularization panel, not an iteration or
tolerance relaxation. The old `gam00`–`gam04` payloads remain unchanged and
available to the frozen Goal028 plan. The `gamr00`–`gamr05` IDs are visible
only inside Goal029's explicit exact-payload authority context; shared
Goal028/generic validation and deserialization reject them.

Each species × endpoint GAM stratum is viable only with at least two complete
candidates, one of which must have `lam>=100`. There is no mandatory GAM
candidate ID. A candidate is complete only after all five inner-training fits
and its full outer-training refit, serialization, and response-free challenge
replay complete. The gate records status, sanitized diagnostic categories,
and semantic digests only. It exposes no assessment metrics, predictions,
thresholds, or partial performance.

Every inner fit must predict its actual held fold through the encoder fitted
only on that fold's training rows. The gate verifies prediction count,
finiteness, and `[0,1]` range and persists only the digest. Every complete and
invalid stage also carries exactly these safe private diagnostics:
iteration count; final-difference class (`lt_tol`, `ge_tol`, `missing`,
`nonfinite`, or `not_applicable`); warning category; coefficient finiteness;
prediction finiteness; and prediction-range status. Exact difference values,
warning messages, paths, scores, labels, thresholds, row IDs, and prediction
values are forbidden. Known fit, strict-convergence, and prediction failures
are sanitized candidate-local invalidity; unknown exceptions and
protocol/authority failures stop.

The exact sentinel
`thylogale_billardierii/fraction100/full/gamr05/seed00` is repeated
independently. Complete repeats require identical stage and challenge
semantic digests. Invalid repeats require identical status and sanitized
diagnostics; reproducible invalidity does not itself satisfy family viability.
Replicate 1 runs in a new separately spawned one-worker executor, and private
evidence must prove a distinct process-instance digest. Unknown diagnostic
classes stop the gate.

All 56 strata must be viable before calibration authority is published.
Production must reproduce the gate's status for every one of its 336 GAM
candidate strata. Missing, failed, modified, or status-inconsistent authority
stops production and publication validation. Concretely, a gate-invalid
candidate is overlaid as a blinded production invalid, produces or retains no
OOF checkpoint, cannot enter selection, and receives the same treatment in
the fresh source audit. A gate-complete candidate that becomes invalid during
production is not converted into an overlay: it hard-stops as a gate/production
contradiction.

If this one gate fails, the next decision is one bounded, Python-only
penalized-spline logistic implementation. If that also fails, GAM is removed
from the conventional comparison globally. There is no R fallback and no
repeated hyperparameter expansion.

## Other candidate validity

A hard failure in any required fold or seed invalidates that candidate only
within its species × endpoint × family. Partial scores and metrics from an
invalid candidate cannot enter selection or tracked evidence. `null00` is
mandatory. Every other tunable family requires at least two complete valid
candidates, including its conservative anchor:

| Family | Mandatory anchor |
|---|---|
| elastic net | `enet00` |
| random forest | `rf02` |
| histogram gradient boosting | `hgb04` |
| shallow ANN | `ann01` |

There is no tolerance, iteration, architecture, or candidate-budget
relaxation. A selected candidate that fails refit, serialization, or replay
aborts its family stratum; the runner-up is not substituted. Unknown or
unclassified warnings stop. Failed candidates expose only blinded failure
receipts.

## Production integrity

Each five-fold candidate-seed leaf is independently content addressed and
atomically checkpointed. Identity includes the complete project-module source
closure, config, lock, runtime, host, upstream, task, split-specific subset,
and encoder provenance. Each membership artefact has exactly one
species × endpoint × split identity; fold-specific and outer-training
memberships are never collapsed.

Every selected refit receives exactly `min(32,n_unique_eligible)` canonical
response-free rows from permitted training-feature support. Its
content-addressed bundle binds model bytes, challenge bytes,
schema/transform/encoder state, parameters, fit seed, adapter runtime,
execution context, and canonical prediction bytes. Validation reconstructs
the training support and challenge independently.

The staged pair is fully validated before a fresh cache-disabled source audit.
The audit salt is fixed from the pre-result plan and execution authority; it
chooses one leaf per family stratum, augments candidate and seed coverage, and
fills to exactly `ceil(0.05 × 7224)=362` leaves. Publication occurs only after
the audit and a second staged validation.

Publication is acyclic: private and tracked core manifests are frozen first;
one pair descriptor binds both core digests and the transaction ID; the final
acceptance marker binds that descriptor and is written last. Unmarked,
partial, mismatched, or extra-file pairs are invalid.

## Numerical execution and calibration

Goal029 retains its fail-closed one-thread-per-process policy. Import-time
environment caps, `threadpoolctl`, and PyTorch intra/inter-op setters enforce
the live state. Policy and effective-evidence digests bind the execution
context and checkpoint identity.

Calibration now has five distinct stages:

1. start four distinct zero-fit spawned children under the thread policy;
2. confirm class support for all 56 species × endpoint strata;
3. run two frozen `hgb04` canary leaves at workers 1 and 2, requiring complete
   identical semantics and a workers-2/workers-1 wall ratio no greater than
   `1.25`;
4. run the frozen 30-leaf representative panel at workers 1, 2, and 4, then
   select the smallest no-swap, minimum-6-GiB worker count within `1.10` of
   the fastest safe trial; and
5. run all 337 GAM candidate executions, including the repeated sentinel,
   once at the selected worker count.

This totals 431 candidate executions and at most 2,597 estimator fits:
20 canary fits, 555 representative fits, and 2,022 GAM-gate fits.
Calibration is feasibility and execution evidence, not model selection.
