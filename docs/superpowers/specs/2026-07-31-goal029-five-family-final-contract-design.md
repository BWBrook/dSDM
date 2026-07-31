# Goal029 five-family final-contract amendment design

## Status and supersession

This amendment supersedes the active GAM-family authority in
`2026-07-30-goal029-conventional-baseline-production-design.md`. The earlier
design remains an accurate record of the bounded P-spline attempt at the time
it was written; it is not current production authority.

Goal029 remains a sealed conventional-baseline production exercise. It selects
and refits models using only permitted outer-training rows and never opens or
scores the real outer assessment. Its estimand remains a conditional relative
habitat-suitability index.

## Evidence and stopping decision

The revised pyGAM recovery completed 225 of 336 candidates and made 40 of 56
species-by-endpoint strata viable. It was rejected.

The predeclared final pure-Python penalised-spline recovery then completed all
336 base candidates plus one sentinel repeat:

- 337 candidate executions;
- 2,022 estimator fits;
- 281 complete and 55 invalid base candidates;
- 52 of 56 viable strata;
- four failed low-data strata;
- a passing sentinel; and
- real outer attempted/open counts `0/0`.

The prospective rule required all 56 strata to be viable. The P-spline panel
therefore failed even though most strata succeeded. Barry authorised the
predeclared stop: GAM is removed globally from active Goal029 rather than
retained selectively. There is no third rescue attempt.

MARS is not introduced as an immediate replacement. It remains a possible
future ideas-ledger item requiring a separate scientific decision.

## Active family design

The final active family panel is exactly:

1. `intercept`;
2. `elastic_net`;
3. `random_forest`;
4. `hist_gradient_boosting`; and
5. `shallow_ann`.

The intercept-only candidate remains mandatory. The existing non-GAM
candidate registries, seeds, anchors, quorum rules, model adapters, and
selected-refit policy remain unchanged. The four non-intercept anchors are
`enet00`, `rf02`, `hgb04`, and `ann01`; each family also requires at least one
other complete candidate. There is no selected-refit fallback.

## Frozen arithmetic

For eight species, seven endpoints, five inner folds, all 28 predictors, and
the existing family-specific seed policy, the final plan contains:

| Quantity | Count |
|---|---:|
| species-by-endpoint strata | 56 |
| family strata | 280 |
| active candidates | 31 |
| candidate strata | 1,736 |
| candidate-seed leaves | 6,888 |
| OOF fold units | 34,440 |
| estimator fits | 42,840 |
| maximum selected refits | 952 |
| source-audit leaves | 345 |

The synthetic lifecycle has 33 leaves, five selected families, and 17 selected
refits.

## Calibration design

Calibration remains an execution-safety and worker-selection exercise:

- four independently spawned zero-fit children;
- one 56-stratum class-support scan;
- two canary leaves at workers 1 and 2, for four executions and 20 fits; and
- 28 representative leaves at workers 1, 2, and 4, for 84 executions and 525
  fits.

The estimator-bearing total is exactly 88 executions and at most 545 fits.
The zero-fit children are outside that execution count. There is no GAM
feasibility gate after worker selection.

Existing native-thread, process-spawn, memory, swap, canary-ratio, and
representative-worker rules remain unchanged and fail closed.

## Authority migration

The active authority versions become:

- configuration schema `1.5`;
- protocol `0.5`; and
- calibration master/index version `4`.

The GAM gate schema, stage, candidate-status fields, receipt bindings,
production overlays, and viability dependencies are removed from active
Goal029 artifacts. Old config, protocol, calibration, checkpoint, and
publication material is stale by construction.

Goal028's frozen pyGAM candidates and replay path remain valid only in Goal028.
The P-spline estimator, registry support, and tests remain dormant historical
and regression evidence. Neither implementation may validate as active
Goal029 authority.

## Production and validation

The five-family lifecycle retains content-addressed candidate checkpoints,
bounded candidate-local failure handling, deterministic selection and refit,
response-free challenge replay, exact inventories, fresh source audit, atomic
paired publication, privacy checks, and transaction rollback.

Schema, authority, transform, serialization/replay integrity, thread evidence,
leakage or outer access, inventory, transaction, and unknown failures remain
hard stops. Every successful calibration, production, and validation receipt
must report real outer attempted/open counts `0/0`.

This amendment authorises contract implementation and synthetic verification
only. It does not authorise real calibration, production, private-data
processing, remote execution, or outer assessment.
