# Goal 029 - Sealed five-family conventional-baseline production

## Objective

Produce the complete inner-OOF conventional baseline panel for the eight
Tasmanian mammals under the Goal027 design, refit and seal every selected
species-by-endpoint-by-family-by-seed model on permitted outer-training rows,
and validate the private/tracked pair without opening or scoring the real
outer assessment.

This goal selects conventional candidates within frozen families. It does not
make an ecological performance claim and does not treat model scores as
occupancy probabilities.

## Final family closure

Goal029 now has exactly five active model families:

- `intercept`;
- `elastic_net`;
- `random_forest`;
- `hist_gradient_boosting`; and
- `shallow_ann`.

The revised pyGAM gate completed 225 of 336 candidates and made 40 of 56
species-by-endpoint strata viable, so it was rejected. The final pure-Python
penalised-spline gate ran all 336 base candidates plus its sentinel repeat,
making 337 executions and 2,022 fits. It produced 281 complete and 55 invalid candidates,
with 52 of 56 strata viable; the four failures were low-data strata. The
sentinel passed and real outer attempted/open counts remained `0/0`.

That result failed the prospective all-56-strata acceptance rule. Barry
therefore closed GAM development for Goal029 and removed the family globally
from the active comparison. Successful GAM strata are not retained
selectively, and there is no third rescue attempt. MARS is recorded only as a
possible future idea and is not an active substitute.

Goal028's pyGAM implementation and the dormant penalised-spline code and tests
remain historical and compatibility evidence. They are never Goal029
production authority.

## Exact scope

- eight ordered species and seven target endpoints;
- five frozen inner folds and all 28 predictors;
- exactly five conventional families and 31 active candidates;
- 56 species-by-endpoint strata and 280 family strata;
- 1,736 candidate strata and 6,888 candidate-seed leaves;
- 34,440 OOF fold units and 42,840 estimator fits;
- at most 952 selected refits;
- a deterministic 345-leaf source audit;
- calibration with four zero-fit spawn children, four canary executions
  producing 20 fits, and 84 representative-worker executions producing 525
  fits, for 88 executions and at most 545 fits in total;
- synthetic execution with 33 leaves, five selected families, and 17 selected
  refits; and
- no real outer assessment access.

Residual MLP, community surfaces, pooled or transfer models, multi-head
models, mapping, interpretation, sensitivities, and birds remain outside this
goal.

## Acceptance

Goal029 is acceptable when:

1. the packet, code, and machine-readable configuration agree on exactly the
   five active families and all frozen counts;
2. active Goal029 registry, planning, calibration, production, validation,
   and publication paths reject historical GAM candidates and gate material;
3. Goal028's legacy pyGAM replay and shared modelling contracts remain
   unchanged, while the dormant penalised-spline implementation is never
   treated as active Goal029 authority;
4. config schema `1.5`, protocol `0.5`, and calibration master/index version
   `4` reject stale authority, and obsolete GAM gate schema, stages, and
   fields are absent;
5. synthetic plan, production, independent validation, privacy, overlay,
   quorum, transaction, and stale-authority gates pass at 33 leaves, five
   families, and 17 refits;
6. authorised real calibration passes the four zero-fit spawn children,
   56-stratum class-support scan, two-leaf canary at workers 1 and 2, and the
   28-leaf representative panel at workers 1, 2, and 4;
7. calibration performs exactly 88 estimator-bearing executions and no more
   than 545 fits, without a GAM feasibility stage;
8. the clean real production plan contains exactly 280 family strata, 1,736
   candidate strata, 6,888 candidate-seed leaves, 34,440 OOF units, 42,840
   estimator fits, and at most 952 selected refits;
9. `intercept` is mandatory, and every non-intercept family satisfies its
   frozen anchor-and-quorum rule without selected-refit fallback;
10. staged artifact-only validation, the fresh 345-leaf source audit, and
    paired transaction validation pass;
11. every successful receipt reports real outer attempted/open counts `0/0`;
    and
12. tracked evidence contains no private paths, response identifiers, labels,
    prediction values, OOF scores, AUC, TSS, thresholds, maps, or claims.

No selective GAM retention, alternate smoother, MARS substitution, tolerance
relaxation, or further family rescue is permitted inside Goal029.
