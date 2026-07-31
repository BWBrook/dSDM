# Plan

1. Preserve the failed old production stage as diagnostic evidence. Do not
   clean, publish, resume, or reinterpret it as a successful production run.
2. Freeze the six-candidate Goal029-only pyGAM recovery registry:
   `n_splines={4,6}` × `lam={10,100,1000}`, cubic splines,
   `max_iter=500`, and `tol=1e-5`. Preserve `gam00`–`gam04` unchanged for
   Goal028.
3. Recompute and freeze the revised plan at 2,072 candidate strata, 7,224
   candidate-seed leaves, 36,120 OOF fold units, 44,520 actual inner fits,
   at most 1,008 refits, and 362 source-audit leaves.
4. Replace the old fragility stage with one status-only GAM feasibility gate:
   all six candidates in all 56 species × endpoint strata, each with five
   inner fits and one full outer-training refit/serialization/response-free
   replay. Each fitted fold predicts its actual held rows using the
   training-fitted encoder; validate prediction length, finiteness, and
   `[0,1]` range, then retain only the digest.
5. Execute the exact sentinel
   `thylogale_billardierii/fraction100/full/gamr05/seed00` twice in independent
   executions, with replicate 1 in a fresh separately spawned single-worker
   process and a distinct private process-instance digest. Require identical
   status and diagnostics; complete repeats must also have identical stage
   and challenge semantic digests.
6. Accept the GAM gate only when all 56 strata have at least two complete
   candidates including at least one `lam>=100`. No particular candidate ID
   is mandatory. Require the exact bounded safe-diagnostic schema for every
   complete or invalid stage. Treat known fit, convergence, and prediction
   failures as candidate-local; stop on unknown, protocol, or authority
   failures.
7. Retain the spawn audit, class-support scan, HGB concurrency canary, and
   30-leaf representative worker calibration. Run the 337-execution GAM gate
   once at the selected worker count. The complete calibration budget is 431
   candidate executions and at most 2,597 estimator fits.
8. Bind the accepted gate receipt into calibration authority, the clean
   production run ID, and publication validation. Reject missing, failed,
   drifted, or status-inconsistent gate evidence before selection/refit. A
   gate-invalid candidate becomes a blinded production overlay with no OOF
   artefact or selection eligibility; a gate-complete candidate becoming
   production-invalid is a hard stop.
9. Preserve Goal029's content-addressed provenance, resumable checkpoints,
   blinded candidate failures, family reduction, selected refits,
   response-free challenges, exact inventories, and paired publication. Keep
   `gamr00`–`gamr05` authorized only inside Goal029's exact scoped registry
   context.
10. Pass focused tests, Goal028 and shared-module regressions, synthetic
    production plus independent validation, compile/lock/diff gates, and
    update the log.
11. Stop without running real calibration or production in this amendment.
    Those commands require a separate orchestrator decision.
12. When authorised, run calibration once. If the revised pyGAM gate fails,
    stop with its sanitized private evidence and return for the predeclared
    penalized-spline-or-remove-GAM decision. If it passes, run one clean
    production lifecycle and stop before outer assessment.

The implementation plan is
[`docs/superpowers/plans/2026-07-30-goal029-conventional-baseline-production.md`](../../superpowers/plans/2026-07-30-goal029-conventional-baseline-production.md).
