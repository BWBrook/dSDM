# Goal 052 log

## 2026-09-05 - protocol freeze

- Froze the SEAWFB dSDM protocol before Goal 051 ecological scores were
  exposed.
- Recorded four arms, strict whole-focal-block-out pretraining and richness,
  the bounded four-architecture panel, five paired seeds, auxiliary and target learning
  curves, and split-scoped stopping/replay.
- No dSDM model, prediction, metric, outer response, or production run was
  executed under this protocol-only tranche.

## 2026-09-05 - prospective numerical amendment recorded

- Recorded Goal 051 numerical amendment 1 after metric-free `q_linear`
  nonconvergence and before any ecological scores.
- The amendment changes only the Goal 051 q optimizer tolerance and iteration
  ceilings. It does not change Goal 052 arms, architectures, contrasts,
  training data, exclusions, weights, seeds, or evaluation policy.
- Any further pre-score change requires explicit versioned authorization and a
  repeated metric-free canary.

## 2026-09-08 — approved q numerical amendment 3

- Recorded the approved tertiary 20,000-iteration attempt in protocol v4 before
  any ecological score. The Goal051 q control retains its objective, tolerance,
  exclusions and strict convergence gate; fresh v4 q provenance replaces no
  historical receipt. Goal052 architecture, contrasts and execution boundary
  are unchanged, and no Goal052 model has run.


## 2026-09-12 — implementation and validation started

- Goal051 accepted by Barry with the original family-level coverage gate and
  the candidate-level failure limitation documented; no refit.
- User requested autonomous continuation. Started a bounded audit of reuse
  and training contracts before implementing the frozen Goal052 experiment.
  Config remains unchanged; no Goal052 fit or outer access has occurred.

## 2026-09-12 — implementation and first route

- Implemented indexed data/training, frozen architecture and endpoint helpers,
  atomic pretraining/target checkpoints, resumable spawned execution, seed-first
  aggregation, and independent output replay. Goal051 source and all frozen
  scientific configs remain unchanged.
- Focused synthetic checks cover row exclusions, weights, dense/indexed loss
  equivalence, initialization/replay/freeze invariants, task reuse, checkpoint
  corruption, independent metric arithmetic, and missing seed/fold rejection.
- Live input validation binds the accepted Goal051 aggregate and all 150 q
  surfaces. No q refit is performed.
- Read-only route assessment selected deep-server CPU for a two-worker
  engineering canary. It has a matching locked environment and idle memory;
  its old GPU is unsupported. Alien's current CUDA/driver compatibility is
  unresolved, so no driver or environment change was attempted. Nectar stays
  parked. A full-row one-epoch profile must precede a production commitment.

## 2026-09-12 14:06 AEST — deep-server engineering canary passed

- Committed/pushed implementation `61a80c9`; scientific config SHA remains
  `04b667168944b39ced1044da8f381553c4024e31cca1f5590f2fbc693e521f9a`.
- All 43 focused tests passed on Mac and deep-server. All 308 transferred files
  (71,948,967 bytes) passed an independent SHA-256 manifest comparison, followed
  by the native Goal052 input/accepted-q checks.
- Deep CPU canary passed with two spawned workers and repeated persistent-store
  jobs. Prediction and shared-trunk digests agreed exactly. Maximum worker RSS
  was 2.587 GiB. Bounded pretraining lifecycles took 16.8–24.2 seconds; these
  timings do not establish full-epoch throughput.
- The full-row one-epoch profile is running in detached tmux session
  `dsdm-goal052-qualification` at `/data/codex/repos/dSDM`. It writes separate
  `canary-deep` and `profile-deep` logs/exit markers under the private Goal052
  root. No production leaves or ecological metrics have been generated.
- Resource observation changed since the initial idle probe: another campaign
  is using approximately 32 single-threaded processes. The profile uses one CPU and ample RAM
  remains available; any production concurrency must use fresh capacity checks.
- Exact frozen-grid row accounting is retained in `workload.json`: 900 auxiliary
  lifecycles and 42,345 unique target lifecycles sum to 6,882,700,168 replay rows.
  Patience 30 entails at least 31 discovery epochs plus one replay epoch for a
  successful lifecycle. Thus at least 220,246,405,376 discovery/stopping/replay
  row visits are required, excluding held prediction and orchestration. This
  is workload accounting, not a runtime forecast. The full-epoch profile will
  resolve whether production needs a substantial new compute commitment.
