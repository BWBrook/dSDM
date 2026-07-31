# Goal029 Conventional Baseline Production Implementation Plan

**Goal:** Produce a resumable, leakage-safe conventional baseline panel and
seal selected refits without using the real outer assessment.

**Architecture:** Keep Goal028 behaviour frozen. Add a Goal029-only GAM
registry and feasibility authority while retaining Goal029 planning,
checkpoints, reduction, challenge construction, validation, and publication
in the dedicated production module.

## Task 1: Preserve the diagnosis

- Retain the failed old stage under its old source/config identity.
- Record the exact GAM outcomes and outer `0/0` evidence.
- Prevent old checkpoints from entering the revised run.

## Task 2: Freeze the revised registry and plan

- Add `gamr00`–`gamr05` as
  `n_splines={4,6}` × `lam={10,100,1000}`, cubic,
  `max_iter=500`, `tol=1e-5`.
- Leave `gam00`–`gam04` unchanged for Goal028.
- Bind Goal029's exact registry in configuration and tests.
- Assert 2,072 candidate strata, 7,224 leaves, 36,120 OOF units, 44,520
  actual inner fits, at most 1,008 refits, and 362 audit leaves.

## Task 3: Implement the GAM feasibility gate

- Generate all 336 GAM species × endpoint × candidate executions.
- Add one independent repeat of the frozen `gamr05` sentinel.
- For every execution attempt five inner fits plus full outer-training refit,
  serialization, and response-free challenge replay.
- Predict each actual held fold with its training-fitted encoder, validate
  count/finiteness/`[0,1]`, and retain only a digest.
- Store status, sanitized diagnostic class/category/stage, the exact bounded
  safe-diagnostic fields, and semantic digests only.
- Reject any performance field or unknown diagnostic.
- Treat known fit/convergence/prediction failures as candidate-local and
  protocol/authority/unknown failures as hard stops.
- Require identical sentinel status/diagnostics and, when complete, identical
  stage/challenge semantic digests.
- Run sentinel replicate 1 in a fresh separately spawned one-worker executor
  and prove a distinct process-instance digest in private evidence.
- Require all 56 strata to have at least two complete candidates including
  one with `lam>=100`.

## Task 4: Revise calibration authority

- Keep the four-child zero-fit spawn audit and class-support scan.
- Use two frozen `hgb04` leaves for the workers-1/2 canary.
- Keep the 30-leaf representative panel at workers 1, 2, and 4.
- Run the 337-execution GAM gate once at the selected count.
- Publish tracked calibration authority only after a passing gate.
- Preserve a failed gate's sanitized private receipt and stop.

## Task 5: Bind gate to production

- Include the accepted calibration receipt in the revised run identity.
- Overlay each gate-invalid GAM candidate into production as blinded invalid,
  delete/skip its OOF checkpoints, and exclude it from selection.
- Require every gate-complete candidate to complete production; hard-stop if
  it becomes invalid.
- Apply the same overlay semantics in the fresh source audit.
- Revalidate calibration authority and status agreement when validating a
  published pair.
- Reject missing, failed, drifted, or context-incompatible evidence.

## Task 6: Retain production integrity

- Preserve content-addressed membership bundles and atomic leaf checkpoints.
- Preserve candidate-local blinded failure handling and family quorum.
- Preserve selected refits, response-free challenges, and no-runner-up rule.
- Preserve exact private/tracked inventories and acyclic pair publication.
- Keep real outer attempted/open limits at `0/0`.
- Keep `gamr00`–`gamr05` outside the shared candidate registry and authorize
  them only within Goal029's exact context.

## Task 7: Update source audit and documentation

- Recompute the deterministic audit at 362 leaves.
- Update Goal, Plan, Decision, Runbook, Log, design, and implementation plan.
- State the one-attempt pyGAM boundary and the later
  penalized-spline-or-remove-GAM branch.

## Task 8: Verification

- Run focused Goal029 and adapter tests.
- Run Goal028/shared regressions.
- Run synthetic production and independent validation.
- Run static plan, compile, lock, and diff checks.
- Perform one material self-review and stop.

## Task 9: Separate execution authorization

- Do not run real calibration or production in this implementation amendment.
- When separately authorized, run calibration once.
- If the GAM gate fails, stop for the predeclared fallback decision.
- If it passes, run one clean production lifecycle and stop before outer use.
