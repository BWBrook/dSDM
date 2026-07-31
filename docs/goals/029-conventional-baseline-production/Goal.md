# Goal 029 - Sealed conventional-baseline production

## Objective

Produce the complete inner-OOF conventional baseline panel for the eight
Tasmanian mammals under the Goal027 design, refit and seal every selected
species-by-endpoint-by-family-by-seed model on permitted outer-training rows,
and validate the private/tracked pair without opening or scoring the real
outer assessment.

This goal selects conventional candidates within frozen families. It does not
make an ecological performance claim and does not treat model scores as
occupancy probabilities.

## Final GAM-family amendment

The original and revised pyGAM attempts are complete failures of their
respective production gates, not partial production results. The revised gate
completed 225/336 candidates and made 40/56 strata viable, which is
insufficient. Barry therefore authorised the predeclared, pure-Python
penalised-spline logistic fallback as the second and final recovery attempt.

The exact Goal029-only panel is:

- `psgam00`, `psgam01`, `psgam02`: four base knots with roughness lambda
  `0.01`, `0.1`, and `1.0`;
- `psgam03`, `psgam04`, `psgam05`: six base knots with the same three
  roughness values;
- cubic univariate training-fitted smooths for 25 continuous predictors;
- unchanged linear categorical indicators, an intercept, and no interactions;
- ridge lambda `1e-4`; and
- deterministic float64 L-BFGS-B with the exact convergence contract in
  `Decision.md`.

The public family remains `gam`. The old `gam00`-`gam04` pyGAM replay path
remains frozen for Goal028, while retired `gamr*` IDs are invalid.

## Exact scope

- eight ordered species and seven target endpoints;
- five frozen inner folds and all 28 predictors;
- six conventional families and 37 Goal029 candidates;
- `seed00` for intercept, GAM, and HGB candidates;
- `seed00`-`seed04` for elastic net, random forest, and shallow ANN;
- 336 family strata, 2,072 candidate strata, 7,224 candidate-seed leaves,
  36,120 OOF fold units, 44,520 actual inner fits, and at most 1,008 selected
  refits;
- a deterministic 362-leaf source audit; and
- no real outer assessment access.

Residual MLP, community surfaces, pooled or transfer models, multi-head
models, mapping, interpretation, sensitivities, and birds remain outside this
goal.

## Acceptance

Goal029 is acceptable when:

1. the packet, code, and machine-readable configuration agree exactly;
2. analytic-gradient, nonlinear-recovery, roughness, edge-case, determinism,
   and serialization tests pass for the new estimator;
3. Goal028's legacy pyGAM candidates and shared modelling contracts replay
   unchanged, while `gamr*` and unscoped `psgam*` payloads fail closed;
4. synthetic plan, production, independent validation, privacy, sentinel,
   overlay, quorum, transaction, and stale-authority gates pass;
5. authorised real calibration passes spawn, class-support, HGB canary,
   representative-worker, and the single penalised-spline feasibility gate;
6. the gate executes exactly 336 base candidates plus one sentinel repeat,
   making 2,022 fits without performance reporting or outer access;
7. all 56 GAM strata have at least two complete candidates, including
   `psgam02` or `psgam05`;
8. every complete candidate predicts every actual held fold through its
   training-fitted encoder and completes outer-training refit, serialization,
   and response-free challenge replay;
9. known candidate-local numerical failures are bounded and sanitized, while
   protocol, authority, leakage, replay-integrity, sentinel, and unknown
   failures stop;
10. gate-invalid GAM candidates become blinded production overlays with no
    OOF or selection eligibility, while gate/production contradiction stops;
11. the clean real production plan completes or fails under the predeclared
    candidate policy, without tolerance or budget relaxation;
12. staged artifact-only validation, the fresh 362-leaf source audit, and
    paired transaction validation pass;
13. every successful receipt reports real outer attempted/open counts `0/0`;
    and
14. tracked evidence contains no private paths, response identifiers, labels,
    prediction values, OOF scores, AUC, TSS, thresholds, maps, or claims.

If the one real penalised-spline gate fails, GAM is removed globally from the
conventional comparison. Do not widen the panel, switch languages, or begin a
third recovery attempt.
