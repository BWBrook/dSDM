# Goal029 final penalised-spline implementation plan

**Objective:** Replace the rejected Goal029 `gamr*` pyGAM registry with one
bounded pure-Python penalised-spline logistic implementation while retaining
the public `gam` family and every non-GAM production contract.

**Mutation boundary:** Configuration, model adapters, Goal029 production
gates, focused tests, and Goal029 documentation only. No dependency, private
data, real calibration, real production, outer assessment, commit, or push.

## Task 1: Freeze the estimator registry

- Add exact `psgam00`-`psgam05` payloads.
- Keep `gam00`-`gam04` unchanged and reject `gamr*`.
- Require exact Goal029 authority for validation and loading.
- Version config, protocol, registry, status records, and gate receipt.

## Task 2: Implement the numerical core

- Build response-free per-feature cubic bases from training rows.
- Use strictly increasing quantile knots, uniform fallback for repeated
  nonconstant quantiles, and omit exact constants.
- Append the omitted zero coefficient when constructing each normalized
  second-difference penalty.
- Implement mean logistic NLL, roughness, ridge, and analytic float64 gradient.
- Run deterministic L-BFGS-B from the prevalence-logit initialization.
- Enforce solver, finiteness, range, and gradient-norm completion criteria.

## Task 3: Implement exact replay

- Add a dedicated fitted wrapper and serialized model state.
- Bind exact basis decisions, dimensions, coefficients, feature schema,
  transform/encoder identity, candidate, and seed.
- Reject type, dimension, basis, authority, and replay drift.

## Task 4: Migrate the feasibility gate

- Preserve 56 strata, 336 base executions, one sentinel repeat, 337 total
  executions, and 2,022 fits.
- Make `psgam05` the sentinel.
- Require at least two complete candidates including `psgam02` or `psgam05`.
- Replace pyGAM diagnostics with bounded basis/solver/gradient/finiteness
  diagnostics.
- Keep known numerical failures candidate-local and all protocol, authority,
  integrity, leakage, sentinel, and unknown failures hard.
- Preserve blinded production overlays and gate/production contradiction.

## Task 5: Test

- Finite-difference the objective gradient.
- Prove nonlinear recovery and non-increasing fitted roughness under stronger
  lambda on identical data.
- Cover high prevalence, exact constants, repeated quantiles, categorical
  effects, deterministic refit, and serialize/load replay.
- Prove Goal028 legacy pyGAM behavior is unchanged and stale IDs fail.
- Cover gate stages, privacy, sentinel, quorum, overlays, stale authority,
  planning counts, and outer `0/0`.
- Run focused Goal029 and shared Goal028/inner-CV suites.

## Task 6: Validate and stop

- Run plan, synthetic production, and independent synthetic validation.
- Run Python compile, lock, and diff checks.
- Perform one focused self-review and repair material defects only.
- Record the two pyGAM failures, final-attempt policy, exact objective, gate,
  and global-removal consequence in the Goal029 documents.
- Stop before any real or private execution.
