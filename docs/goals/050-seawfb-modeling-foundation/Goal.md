# Goal 050 - SEAWFB modelling foundation

## Objective

Freeze an analysis-ready, response-blind and model-free SEAWFB substrate that
binds the Goal 048 predictor/domain files to the Goal 049 canonical response
and panel receipts. This goal does not fit models, make predictions, open the
NCP/SEH/NNC outcomes, or choose thresholds.

## Frozen design

Training cells are all domain cells outside the simultaneous 50-km buffers of
NCP, SEH, and NNC. Five projected 50-km block folds are searched over seeds
0--511 using only map and support balance. X10 is primary; X20 is an
evaluation-only sensitivity.

The private cell table retains block coordinates, fold, predictor completeness,
full 505-donor uint16 effort richness, and the 24 raw Goal 048 predictors.
The private membership table is sparse and contains only the 183 training-
eligible heads. No dense species-by-cell matrix is created.

Ten deterministic focal species blocks (seven of 16 and three of 15) define
leakage-safe cross-fitting. Held species are removed lazily from response
heads and donor richness only when constructing auxiliary pretraining
backgrounds, using `R_complement(c) = R_full(c) - sum(I_s(c))`. Target-specific
fine-tuning and evaluation use the target-specific X10 rule against full
richness: at a target-absent row that target already contributes zero, while
co-block species remain legitimate effort donors. Learning-curve plans are
recorded without fitting models: auxiliary 20/80/full and target 25/50/100%
curves for the 73 primary targets, plus a deterministic 100% endpoint for
each of the remaining 84 focal targets, across all five held folds.

Tracked metadata contains counts, seed-search evidence, provenance bindings,
transforms, and
privacy-safe receipts; cell coordinates and species-cell payloads remain
private. `run.exit` is written only after validation succeeds.

This foundation tranche is complete. A bounded training-only compute canary
and route decision are recorded below; no production model, prediction,
threshold, or ecological outcome is opened here.

## Compute-canary status

The canary runner and receipt schema are implemented. Exact frozen eligibility
yields 94,873 rows; the authorized canary-only resolution is a 90,000-row
bundle. No scientific eligibility rule was relaxed, and no ecological metrics
or production work is opened by this result.

Six clean-process receipts and three CPU aggregate calibrations passed. Mac
wins single-job latency, while deep-server wins aggregate CPU capacity at
32 concurrent one-thread jobs; the selected route is
`deep_server_cpu_vectorized_pretraining_and_target_jobs` for bridge-like
vectorized PyTorch grids only. Goal051 conventional models require their own
small family-representative resource gate. Goal051/052 session names,
checkpoint layout, and restart behavior remain proposed and untested
production plans.
