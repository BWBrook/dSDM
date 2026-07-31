# Decision

Goal029 remains the sealed conventional-baseline production goal. It may tune
models inside the five inner folds, but it must not open, score, or otherwise
use the real outer assessment. The public model output is a conditional
relative habitat-suitability index, not occupancy probability.

The exact executable authority is
[`config/conventional_baseline_production.json`](../../../config/conventional_baseline_production.json).

## Final GAM-family decision

Two bounded recovery attempts have now supplied decisive evidence:

- the revised pyGAM gate completed 225 of 336 candidates and made 40 of 56
  species-by-endpoint strata viable; and
- the final pure-Python penalised-spline gate ran all 336 candidates plus one
  sentinel repeat, making 337 executions and 2,022 fits. It returned 281
  complete and 55 invalid candidates, leaving 52 of 56 strata viable. The
  four failed strata were low-data cases, the sentinel passed, and real outer
  attempted/open counts were `0/0`.

The final gate therefore failed its prospective requirement that all 56
strata be viable. The family is rejected globally from active Goal029
authority. Retaining only successful strata would create a species-dependent
comparison panel and is not permitted. There is no third GAM rescue,
alternative language implementation, wider search, or relaxed acceptance
rule.

MARS is not a replacement in this goal. It may remain on the future ideas
ledger for separate scientific consideration after Goal029.

The revised pyGAM and final penalised-spline receipts remain historical
diagnostic evidence. They must not be cleaned, promoted, resumed, or reused.
Goal028's pyGAM implementation and replay contract remain unchanged. Dormant
penalised-spline code and tests are retained only to preserve history and
regression evidence; they carry no active Goal029 authority.

## Frozen active panel

The exact active production families are:

| Family | Goal029 role |
|---|---|
| `intercept` | mandatory prevalence-only null |
| `elastic_net` | regularised linear baseline |
| `random_forest` | tree-ensemble baseline |
| `hist_gradient_boosting` | boosted-tree baseline |
| `shallow_ann` | conventional single-species neural-network baseline |

There are eight species and seven endpoints, hence 56 species-by-endpoint
strata and 280 family strata. The frozen active workload is:

- 31 active candidates;
- 1,736 candidate strata;
- 6,888 candidate-seed leaves;
- 34,440 OOF fold units;
- 42,840 estimator fits;
- at most 952 selected refits; and
- 345 immutable source-audit leaves.

`intercept` is mandatory. The frozen anchors for the other families remain
`enet00`, `rf02`, `hgb04`, and `ann01`, each with at least one additional
complete candidate required. There is no selected-refit fallback.

## Calibration closure

Calibration now establishes execution safety and selects a worker count
without any family-feasibility gate:

1. four independently spawned zero-fit children prove the one-thread
   execution contract;
2. the 56-stratum class-support scan runs once;
3. two frozen canary leaves run at workers 1 and 2, for four executions and 20
   fits; and
4. 28 representative leaves run at workers 1, 2, and 4, for 84 executions and
   525 fits.

The estimator-bearing calibration total is exactly 88 executions and no more
than 545 fits. Worker-selection, memory, swap, thread-pool, canary-ratio, and
representative-runtime rules remain fail closed. Calibration is engineering
evidence, not scientific model comparison.

## Authority and production

Config schema `1.5`, protocol `0.5`, and calibration master/index version `4`
make all prior Goal029 authority stale by construction. Active calibration
and production have no GAM gate schema, stage, fields, receipt, candidate
overlay, or viability dependency.

The synthetic lifecycle contains 33 leaves, five selected families, and 17
selected refits. The real plan contains the exact active counts above.
Candidate checkpoints, selected refits, challenge replay, the 345-leaf source
audit, and paired publication remain content addressed and fail closed.

Each non-intercept candidate may fail only under its existing bounded
candidate-local policy. Schema, authority, transform, serialization/replay
integrity, thread evidence, leakage or outer access, transaction, inventory,
and unknown failures remain hard stops.

No calibration or conventional-production path may open, predict, score,
summarize, or inspect the real outer vault. Every successful receipt must
report real outer attempted/open counts `0/0`.
