# Plan

1. Preserve both failed pyGAM stages and their receipts as historical
   diagnostic evidence. Do not clean, resume, publish, or reuse them.
2. Freeze `psgam00`-`psgam05` as the exact Goal029-only penalised-spline
   registry: base knots `{4,6}` crossed with roughness lambda
   `{0.01,0.1,1.0}`, with all remaining estimator and optimiser fields fixed.
3. Keep the shared public family as `gam`, the Goal028 `gam00`-`gam04` pyGAM
   implementation unchanged, and reject all retired `gamr*` payloads.
4. Implement training-only cubic bases, exact-constant omission, quantile
   knots with a uniform fallback for repeated quantiles, unchanged
   categorical indicators, the normalized second-difference penalty, ridge,
   analytic float64 gradient, and deterministic L-BFGS-B.
5. Require optimiser success, finite state and training predictions, unit
   interval scores, and final gradient infinity norm at most `1e-5`.
6. Bind exact basis dimensions, transformers, coefficients, schema, candidate,
   seed, transform, and encoder identity into deterministic serialization and
   replay.
7. Version the config, protocol, registry, candidate-status record, and gate
   receipt so no artifact from commit `6344721` or either pyGAM attempt can be
   reused.
8. Keep the feasibility workload fixed at 56 strata, 336 base candidate
   executions, one independent `psgam05` sentinel repeat, 337 executions, and
   2,022 fits. Retain prediction-digest-only held-fold and response-free
   challenge checks.
9. Accept each stratum only with at least two complete candidates including
   `psgam02` or `psgam05`; require all 56 strata to pass.
10. Treat recognized basis, optimizer, nonconvergence, nonfinite-state,
    excessive-gradient, and prediction failures as candidate-local. Stop on
    schema, authority, transform, serialization/replay integrity, sentinel,
    leakage/outer, and unknown failures.
11. Preserve the non-GAM production lifecycle, blinded gate overlays,
    content-addressed checkpoints, selected refits, source audit, transaction,
    and publication validators.
12. Pass focused estimator and Goal029 tests, shared Goal028/inner-CV tests,
    synthetic plan/run/validate, Python compilation, lock, and diff checks.
13. Perform one focused self-review and repair pass, then stop without real
    calibration, real production, private-data processing, outer assessment,
    commit, or push.
14. When separately authorised, run the one real calibration gate. If it
    fails, remove GAM globally; if it passes, proceed through one clean
    conventional production lifecycle.

The detailed implementation plan is
[`docs/superpowers/plans/2026-07-30-goal029-conventional-baseline-production.md`](../../superpowers/plans/2026-07-30-goal029-conventional-baseline-production.md).
