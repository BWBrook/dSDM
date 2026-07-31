# Goal029 conventional-baseline production design

## Purpose

Goal029 produces the sealed conventional inner-OOF comparison and selected
outer-training refits without using the real outer assessment. It preserves
the Goal027 estimand: a conditional relative habitat-suitability index.

This design amendment freezes the final GAM-family fallback after two pyGAM
panels failed their production gates. The revised pyGAM gate completed 225 of
336 candidates and left 40 of 56 strata viable. That evidence is retained but
is not authority for the new run.

## Model design

The public `gam` family uses six Goal029-only `psgam*` candidates:

- base knots: 4 or 6;
- roughness lambda: 0.01, 0.1, or 1.0;
- cubic `SplineTransformer` blocks, `include_bias=False`;
- constant extrapolation;
- linear one-hot categorical effects;
- no interactions; and
- ridge lambda `1e-4`.

Each continuous predictor receives its own training-fitted basis. Equally
spaced empirical quantiles are used when strictly increasing; otherwise a
nonconstant feature receives uniform min/max knots. Exact constants are
omitted. These decisions are response-free.

For observed spline coefficients \(b_j\), append one omitted zero reference
coefficient before applying the second-difference operator. Normalize each
block penalty by its number of second differences. The float64 objective is
mean Bernoulli negative log likelihood plus half roughness lambda times the
summed normalized block penalty plus half ridge lambda times the squared norm
of all non-intercept coefficients.

L-BFGS-B starts at the empirical training-prevalence logit and zero
non-intercept coefficients. The exact controls are `max_iter=1000`,
`gtol=1e-6`, and `ftol=1e-12`. Completion requires solver success, finite
coefficients/objective/gradient/training scores, `[0,1]` scores, and gradient
infinity norm no greater than `1e-5`.

The fitted wrapper owns the exact transformers, omitted-constant decisions,
block dimensions, coefficients, schema, candidate, and seed. Serialization
and replay are deterministic and authority-scoped.

## Compatibility and authority

Goal028 `gam00`-`gam04` and its pyGAM implementation remain unchanged. Retired
`gamr00`-`gamr05` identifiers are invalid. The `psgam*` payloads exist only in
Goal029's exact context-scoped registry and cannot be validated or loaded
generically.

Protocol 0.4, config 1.4, registry v2, candidate-status v2, and gate-receipt v2
make old checkpoints and receipts stale by construction.

## Gate design

The single gate executes six candidates in each of 56 species-by-endpoint
strata, plus one independently spawned sentinel repeat:

- 336 base executions;
- 337 total executions;
- six fits per execution; and
- 2,022 total fits.

Each execution fits all five inner folds, predicts the actual held fold
through its training-fitted encoder, and performs one full outer-training
refit, serialization, and response-free challenge replay. Only bounded
statuses and semantic digests survive.

A stratum requires at least two complete candidates and at least one of
`psgam02` or `psgam05`. All 56 strata must pass. Candidate-local failure
classes are basis, optimizer, strict nonconvergence, nonfinite state,
excessive gradient, prediction failure, and invalid score. Unknown, schema,
authority, transform, serialization/replay integrity, sentinel,
leakage/outer-access, and gate/production contradiction are hard stops.

The sentinel is
`thylogale_billardierii/fraction100/full/psgam05/seed00`. Its two executions
must agree in status and bounded diagnostics and, when complete, all stage and
challenge semantic digests.

If the gate fails, GAM is removed globally. This design permits no third
GAM-family attempt.

## Production design

Non-GAM candidates, seed handling, family anchors, content-addressed
checkpoints, selected refits, challenge bundles, the 362-leaf source audit,
paired publication, thread limits, calibration canary, representative worker
trials, and privacy rules remain unchanged.

Gate-invalid GAM candidates are blinded overlays and cannot create OOF
artifacts or enter selection. A gate-complete candidate becoming invalid in
production is a hard stop.
