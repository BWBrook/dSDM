# Goal 050 decision record

- Spatial folds are projected 50-km blocks in EPSG:3577, assigned as complete
  blocks to five balanced folds.
- Seed selection searches 0--511 using response/support gates only. No model
  metric enters partition choice; ties use worst target presence-share
  deviation, map-share deviation, then seed.
- Full effort richness uses all 505 Goal 049 donors. Richness is not a model
  predictor. X10 is primary and X20 remains evaluation-only.
- Species-block cross-fitting is lazy. Held focal species are removed from
  auxiliary pretraining heads and donor richness; target fine-tuning and
  evaluation use target-specific X10 against full richness, so co-block
  species remain legitimate donors at target-absent rows. Auxiliary-only
  heads remain eligible.
- Response-row plans cover all 157 focal targets in all five held folds. The 73
  primary targets have deterministic nested 25/50/100% plans; the remaining
  84 have deterministic full-only endpoints. Tracked receipts retain counts
  and digests only; private learning-curve payloads retain counts/digests,
  while selected rows are deterministically reconstructible rather than
  retained as IDs.
- The manifest binds the generator source, `uv.lock`, and the authoritative
  Goal 040 IBRA geometry used for the 50-km buffers.
- Transform vocabularies explicitly include `__MISSING__` and `__UNSEEN__`;
  continuous transforms use training-map population means and SDs.

The model-free foundation and the separate training-only compute-routing
evidence are validated. Goal 050 remains open for the later scientific
experiments; no outcome metric or production model is implied by this receipt.

## Compute-canary gate (2026-09-02)

The initial bounded canary export was fail-closed: under the frozen held fold
0, held block 0, 167-head complement, strict richness subtraction, and stable
cell-hash rule, exactly 94,873 eligible non-held-fold rows were available,
below the initial 100,000-row requirement. Under explicit authorization, only
the canary bundle size was reduced to 90,000; the scientific eligibility rule,
fold, block, and head set were unchanged. The canary remains training-only.

All six host/repeat runs and the Mac-3, deep-16, and deep-32 aggregate
calibrations passed finite, deterministic, memory, and zero-ecological-metric
gates. Median multi-head fit-only seconds were 1.579 on Mac CPU, 10.824 on
deep-server CPU, and 19.995 on Alien GPU. Mac wins single-job latency; deep
wins aggregate CPU capacity at 32 jobs (26.95M versus 21.44M row-head-epochs/s,
1.26x). The selected route is
`deep_server_cpu_vectorized_pretraining_and_target_jobs` for bridge-like
vectorized PyTorch grids only; Goal051 conventional models require their own
small family-representative resource gate. This is a throughput and
operational decision, not a loss or ecological-outcome decision. Goal051/052
session names, checkpoint layout, and restart behavior are proposed and
untested production plans.
