# Goal 050 plan

1. Validate the frozen Goal 048/049 inputs, schemas, counts, and hashes.
2. Project domain cells to EPSG:3577 and apply the simultaneous official 50-km
   IBRA buffers.
3. Stream the Goal 049 canonical memberships to construct full effort richness
   and sparse memberships for the 183 training heads.
4. Search and freeze the five spatial folds using response/support gates only.
5. Write private cells, memberships, cross-fitting and learning-curve plans
   atomically.
6. Fit and record fold-specific and retained-full training-only transforms.
7. Validate outputs and then write `run.exit`.

No model fitting, predictions, outcome metrics, threshold changes, or
publication action is in scope. The bounded compute canary below is
training-only and does not launch production.

## Canary gate result

The initial canary export was attempted against the bound seed-394 substrate.
The strict candidate gate returned 94,873 rows rather than the initial
100,000. The authorized resolution changes only the canary bundle size to
90,000; the frozen scientific eligibility rule is unchanged. Six host/repeat
runs and the prescribed Mac-3, deep-16, and deep-32 aggregate calibrations
were executed. All passed determinism, finiteness, memory, and zero-ecological-
metric gates. Median multi-head fit-only times were 1.579 s (Mac CPU),
10.824 s (deep-server CPU), and 19.995 s (Alien GPU). Mac wins single-job
latency, but deep-server wins measured aggregate CPU capacity at 32 jobs
(26.95M versus 21.44M row-head-epochs/s, 1.26x); deep-server CPU is selected
for bridge-like vectorized PyTorch grids. Goal051 conventional models require
their own small family-representative resource gate. Production remains
unlaunched.
