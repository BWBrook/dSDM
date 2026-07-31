# Decision

Goal029 remains the sealed conventional-baseline production goal. It may tune
models inside the five inner folds, but it must not open, score, or otherwise
use the real outer assessment. The public model output is a conditional
relative habitat-suitability index, not occupancy probability.

The exact executable authority is
[`config/conventional_baseline_production.json`](../../../config/conventional_baseline_production.json).

## Evidence that led to the final GAM attempt

Two pyGAM panels have now been rejected as production authorities:

- the original panel completed 133/280 candidate strata and left only 32/56
  species-by-endpoint GAM strata viable; and
- the revised `gamr00`-`gamr05` gate completed 225/336 candidates and left
  only 40/56 strata viable.

Both runs failed closed before conventional-model production. Their real outer
attempted/open counts remained `0/0`. Their retained receipts are historical
diagnostic evidence only and must not be cleaned, promoted, resumed, or reused
under the new registry.

Barry authorised one final GAM-family attempt: a bounded, pure-Python
penalised-spline logistic implementation. This is the second and final recovery
attempt under the agreed two-attempt stopping rule. If its single real gate
fails, GAM is removed globally from the conventional comparison. There is no R
fallback, wider grid, changed optimiser budget, or further GAM search.

## Frozen penalised-spline model

The public family remains `gam`, but the Goal029-only IDs are `psgam00` through
`psgam05`:

| ID | base knots | roughness lambda |
|---|---:|---:|
| `psgam00` | 4 | 0.01 |
| `psgam01` | 4 | 0.1 |
| `psgam02` | 4 | 1.0 |
| `psgam03` | 6 | 0.01 |
| `psgam04` | 6 | 0.1 |
| `psgam05` | 6 | 1.0 |

Each model has an intercept, one univariate cubic B-spline smooth for each of
the 25 continuous predictors, and unchanged linear one-hot effects for the
categorical predictors. It has no interactions. `SplineTransformer` uses
`degree=3`, `include_bias=False`, and constant extrapolation.

Base knots are fitted on training rows only at equally spaced empirical
quantiles. If those knots are not strictly increasing for a nonconstant
feature, the model uses a uniform min-to-max basis. An exactly constant
continuous feature is omitted. No response information enters either choice.

For response \(y_i\), linear predictor \(\eta_i\), non-intercept coefficients
\(\beta\), and spline blocks \(b_j\), the fitted objective is

\[
\frac{1}{n}\sum_i \{\log(1+\exp(\eta_i))-y_i\eta_i\}
+\frac{\lambda}{2}\sum_j
\frac{\|D_2[b_j,0]\|_2^2}{n_{2,j}}
+\frac{10^{-4}}{2}\|\beta\|_2^2 .
\]

The zero appended to each retained `include_bias=False` block is the omitted
reference coefficient used only to construct the second-difference penalty.
Each block is normalized by its number of second differences. The objective
and analytic gradient use float64.

L-BFGS-B starts from the training-prevalence logit with all other coefficients
zero. The frozen limits are `max_iter=1000`, `gtol=1e-6`, and `ftol=1e-12`.
A fit is complete only when the optimiser reports success, coefficients,
objective, gradient, and training scores are finite, scores are in `[0,1]`,
and the final gradient infinity norm is no greater than `1e-5`.

The original `gam00`-`gam04` definitions and pyGAM replay path remain unchanged
for Goal028. The retired `gamr*` IDs are rejected. The exact `psgam*` payloads
are accepted only inside Goal029's content-bound authority context, including
deserialization.

## One-run feasibility gate

The workload is unchanged:

- 56 species-by-endpoint strata;
- six candidates per stratum;
- 336 base candidate executions;
- one separately spawned repeat of the frozen
  `thylogale_billardierii/fraction100/full/psgam05/seed00` sentinel;
- 337 total executions and 2,022 fits; and
- five actual held-fold predictions plus one full outer-training
  refit/serialization/response-free replay per execution.

A stratum is viable only with at least two complete candidates and at least one
of `psgam02` or `psgam05`. All 56 strata must be viable. Gate-invalid candidates
may enter production only as blinded invalid overlays; a gate-complete
candidate becoming production-invalid is a contradiction and hard stop.

The bounded diagnostic record contains iteration count, solver termination
class, gradient-norm class, basis status, coefficient finiteness, prediction
finiteness, and prediction-range status. Recognized basis, optimiser,
nonconvergence, nonfinite-state, excessive-gradient, and invalid-prediction
failures are candidate-local. Schema, authority, transform, serialization,
replay, sentinel, leakage/outer-access, and unknown failures stop the gate.
No metrics, thresholds, labels, prediction values, row identifiers, paths, or
raw exception messages are exposed.

## Other production policy

The non-GAM contract remains unchanged. `null00` is mandatory. Elastic net,
random forest, histogram gradient boosting, and shallow ANN each require their
frozen anchor plus at least one other complete candidate. There is no
selected-refit fallback.

Each candidate checkpoint, selected refit, challenge replay, source audit, and
paired publication remains content addressed and fail closed. Calibration
retains the zero-fit four-child spawn audit, 56-stratum class-support scan,
two-leaf HGB canary, 30-leaf representative worker trials, then the one real
penalised-spline gate at the selected worker count. Calibration is execution
evidence, not scientific model comparison.
