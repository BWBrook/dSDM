# Runbook

Run from the repository root under the locked Python 3.12 environment.

## Static and synthetic gates

```sh
uv sync --locked
uv lock --check
uv run pytest -q tests/test_goal029_production.py tests/test_model_adapters.py
uv run pytest -q \
  tests/test_goal028_preflight.py \
  tests/test_inner_cv.py \
  tests/test_model_adapters.py
uv run python -m dsdm_phase1.goal029_production --root . --mode plan
uv run python -m dsdm_phase1.goal029_production --root . --mode synthetic
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode synthetic --validate
```

Synthetic output is disposable and must use a synthetic vault only. It
exercises checkpointing, invalid-candidate blinding, family quorum, selected
refit, challenge replay, pair publication, source audit, and partial/unmarked
rejection. Remove its ignored output after validation.

## Retained failed stage

Do not resume, publish, clean, or delete the old 2,016-candidate stage. It is
diagnostic evidence for the superseded GAM registry. The revised
source/config identity produces a clean run and cannot reuse old candidate
checkpoints.

## Real calibration

Run only after explicit orchestrator authorization:

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode calibration
```

The command performs, in order:

1. a four-child, zero-fit spawn proof under the frozen one-thread policy;
2. the 56-stratum class-support scan;
3. two frozen `hgb04` canary leaves at workers 1 and 2;
4. the 30-leaf representative panel at workers 1, 2, and 4; and
5. the 337-execution GAM feasibility gate at the selected worker count.

Canary semantics must match and the workers-2 wall time must not exceed
`1.25` times workers 1. Representative semantics must match. Among trials
with at least 6 GiB free memory before and after and no swap growth, the
smallest worker count within `1.10` times the fastest safe wall time is
selected.

The GAM gate attempts all five inner-training fits plus the full
outer-training refit/serialization/response-free replay for all six revised
candidates in all 56 strata. It runs the frozen sentinel twice. It writes
status, sanitized diagnostics, and semantic hashes only; never assessment
metrics, predictions, or thresholds. All 56 strata must contain at least two
complete candidates including at least one with `lam>=100`.

For each inner stage, fit the encoder on the training rows and predict the
actual held fold. Validate output length, finiteness, and `[0,1]` range, and
retain only its digest. Replicate 1 of the sentinel must run in a separately
spawned one-worker executor; the private receipt proves that its
process-instance digest differs from replicate 0. Each stage must have the
bounded `safe_diagnostics` record. Known fit/convergence/prediction failures
are candidate-local; unknown, protocol, or candidate-authority errors stop.
In particular, an exact `pygam.utils.OptimizationError` wrapped by the
adapter as `gam_fit_failed` is recorded as the bounded
`OptimizationError/optimization_error` diagnostic. Never retain or classify
from its raw PIRLS message; an unregistered cause still stops the gate.

Calibration totals are 431 candidate executions and at most 2,597 estimator
fits. The accepted tracked index is written only after the GAM gate passes.
On a failed GAM viability gate, the sanitized private gate receipt is retained
and no passing tracked calibration authority is published. Stop and return to
the orchestrator; do not widen the grid, relax convergence, or rerun unchanged.

The module sets `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`VECLIB_MAXIMUM_THREADS`, and `NUMEXPR_NUM_THREADS` before numerical imports,
then verifies live `threadpoolctl==3.6.0` and PyTorch intra/inter-op state in
parents and children. Do not substitute shell-only settings.

## Real production

Run only after an accepted calibration authority exists:

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production --validate
```

Production rejects missing, failed, modified, or host/context-incompatible
calibration authority. Its 336 GAM candidate statuses must match the accepted
gate exactly before selection or refit proceeds. Never use heterogeneous host
shards, and never open, predict, score, summarize, or inspect the real outer
vault.

A gate-invalid GAM candidate is written into production as a blinded invalid
overlay. Delete any matching partial OOF checkpoint, do not execute or select
it, and reproduce the same overlay during source audit. If a gate-complete
candidate becomes production-invalid, stop immediately rather than
reclassifying it. The `gamr*` payloads are authorized only by Goal029's scoped
registry context; a generic or Goal028 load is expected to reject them.

Late-phase restart is intentionally simple. At production startup, an
interrupted stage may discard and rebuild only `source_audit.json` and
transaction-generated `core_manifest.json`, `PAIR.json`, `FINALIZED.json`, or
its temporary final-marker file. The fresh 5% source audit is rerun. A
transaction rollback restores both stage trees and removes its generated
transaction metadata before returning failure, so the same stages can be
published again. Checkpoints, selections, selected models, memberships,
encoders, and failure receipts are never removed by this reset. Any symlink,
non-regular late metadata, unknown inventory entry, or existing final
destination remains a hard stop.

Publication is forbidden until complete staged artefact validation and the
fresh 362-leaf source audit both pass. Core manifests precede the pair
descriptor; the final acceptance marker is written last. The lifecycle
resumes only exact identity-matching revised checkpoints. There are no
user-invocable shortcuts around these gates.

If the revised GAM gate fails, the next separately authorised recovery is one
bounded Python-only penalized-spline logistic attempt. Failure there removes
GAM from the conventional panel. Do not introduce R, expand candidates, or
alter fitting limits within Goal029.

## Final engineering gate

```sh
uv run pytest -q
uv run python -m py_compile \
  src/dsdm_phase1/inner_cv.py \
  src/dsdm_phase1/model_adapters.py \
  src/dsdm_phase1/goal029_production.py
uv lock --check
git diff --check
git status --short --branch
```

The completion receipt must separate engineering validity from scientific
performance and report real outer attempted/open counts exactly.
