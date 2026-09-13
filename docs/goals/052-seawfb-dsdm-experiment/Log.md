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

- Enabled hourly continuation in this thread (`continue-dsdm-goal052`) under
  Barry's autonomy request so the full-row profile can finish without a manual
  prompt. It must preserve active source, verify returned evidence, prepare the
  route, and pause for a material new compute/scientific decision.
## 2026-09-12 — equivalent CPU optimizer implementation

- Adopted CPU AdamW `foreach=True` after explicit single-tensor versus foreach
  checks on both Mac and deep-server: two seeds, 168 heads, full stopping budget,
  31 discovery epochs and one replay epoch. Every stopping loss, selected epoch,
  model digest and final tensor matched bit-for-bit within each host. Compact
  results and private-artifact hashes are in `optimizer-equivalence.json`.
- Repeated deep-server step timings improved from 47.40 to 32.79 ms (1.45x).
  These synthetic timings do not replace full-data throughput qualification.
- Fused AdamW is deferred: deep-server lifecycle weights differed by up to
  2.384e-7. No numerical tolerance was relaxed and no fused path was adopted.
- Fit receipts bind the optimizer implementation. The source change requires
  fresh canary and full-profile receipts; the original unfinished profile is
  superseded with logs preserved, rather than counted as a numerical failure.

- Source `e309ca8` is committed, pushed and staged on deep-server. All 43
  focused tests and native accepted-input/q checks passed there again. The
  replacement two-worker canary/profile chain started at 14:34 AEST in
  `dsdm-goal052-qualification`, source digest
  `fce7fb52b386c662c198e264aebc007de203e363b5ccc917ccd55ebaa2470926`.
  The superseded profile ended by an intentional signal to its verified worker;
  its parent and wrapper exited before source was changed. No production ran.

- At 14:36 AEST, the replacement canary had two active one-thread workers at
  about 2.15 GiB RSS each; server load average was 56.75, with approximately
  60 processes above 50% CPU in the preceding snapshot. This supersedes the
  earlier 32-process load observation. Treat profile timings as contended
  measurements and recheck capacity before a production recommendation.

- At 14:37 AEST the new-source canary exited zero. All four repeated jobs across
  two worker PIDs agreed on prediction and shared-trunk digests; every fit
  recorded foreach AdamW and finite state. Maximum worker RSS was 2.545 GiB.
  Returned `metadata/goal052_canary.json` SHA-256 matched the remote file:
  `578128be69aae014837906d26a64c080455dc2b24910f76fdb856b49ce064c43`.
  The full-row profile then started (parent PID 14494), with its explicit
  `pretraining_started` event verified. Production has not started. Hourly
  continuation remains active; the Nectar handover is pushed at `c2fde2f`.

## 2026-09-12 15:17 AEST — hourly qualification check

The full-row profile remains active after 40 minutes: verified worker PID
14502 belongs to profile parent 14494, uses 99.9% CPU and 2.097 GiB RSS.
Its log still contains only `pretraining_started`; neither a profile exit
marker nor the completed metadata receipt exists. Process activity does not
establish completion or scientific validity. Deep-server remains at `e309ca8`
with no source/config/lock changes, and the returned canary SHA-256 still
matches `578128be69aae014837906d26a64c080455dc2b24910f76fdb856b49ce064c43`.
Server load has fallen to 17.06, with about 119 GiB available memory. No
source change, duplicate launch or production commitment was made. Hourly
continuation remains active pending the complete profile.

## 2026-09-12 16:18 AEST — full profile passed; resource decision pending

- The full profile exited zero and its tmux session ended. Returned metadata
  SHA-256 `b580e1fd551deb1f51d6b4a3f87f1ac020c96a05d78aad4884fa6d70e20a102f`
  matches deep-server. The independent `full-profile-review.json` verifies
  source/acceptance/host, row/head inventories, seed and one-epoch budgets,
  finite state/losses, reset/replay, transfer/freeze and paired-head invariants,
  q binding, row-rate arithmetic and absence of ecological/outer metrics.
- Full 168-head pretraining used 6,895,417 discovery, 2,737,414 stopping and
  9,632,831 replay rows in 79.54 minutes; the complete profile took 80.57
  minutes with peak RSS 2.395 GiB. Target arms took 12.64–12.77 seconds, except
  frozen trunk at 4.55 seconds. These are one-epoch measurements.
- A bounded independent methodological review supports a 24-hour, two-worker
  CPU pilot to measure production stopping/replay times. It rejects treating
  minimum row visits as a wall-time bound or extrapolating the largest case
  uniformly across architectures and auxiliary sizes. No GPU speedup is assumed.
- `ComputeRoute.md` contains the concrete resource proposal; the prepared
  `scripts/goal052_pilot.sh` passed shell syntax validation. A temporary process
  group probe on deep-server verified GNU timeout stops children at its cap.
  No production was launched. At the 16:18 check, other load was about 48,
  with 118 GiB available RAM. Recheck capacity before an approved launch.
- The hourly qualification follow-up is paused pending Barry's decision on
  this 48-worker-hour pilot (plus the 60-second termination allowance). The
  full campaign, cloud allocation and driver changes remain unauthorized.

## 2026-09-12 16:28 AEST — approved pilot launched

Barry approved the 24-hour, two-worker pilot and requested checks every four
hours. The staged wrapper SHA-256 is
`ab548ed8b7feb59a61265afbaa0bbe8ed81addfb6fae1bbc6c5bb7cc8766bfab`;
scientific source remains `e309ca8`. Source/config/lock state and both
qualification receipt identities/hashes matched before launch. Load was
48.11 with 118 GiB available RAM. The detached `dsdm-goal052-pilot` session
started at 16:28:12 AEST, with nominal deadline 16:28:12 AEST on 13 September.
`pilot-launch.json` binds these details and was returned to tracked evidence.

At the post-launch check, timeout PID 23201, runner PID 23210 and workers
23221/23224 shared process group 23201. Both training workers were active
at approximately 100% CPU and 2.03 GiB RSS. The runner lock was present and
bound to the qualified identity. Log: `logs/run-20260912T162812-23202.log`.
No completed fit was claimed from process activity. The same existing
follow-up is now active every four hours; timeout enforces the 24-hour cap
independently, with a 60-second termination allowance. Do not reset its clock.

## 2026-09-12 20:30 AEST — four-hour pilot check

The original timeout/runner/worker process group remains active after four
hours, with both workers at approximately 100% CPU and 2.03/2.08 GiB RSS.
No pretraining or target checkpoint directory exists yet; the run log is
empty and no exit marker is present. Thus no completed lifecycle, selected
epoch history or fit-state invariant can yet be verified. Source/config/lock
files have no Git changes; wrapper, canary, full-profile and launch receipt
hashes still match the recorded values. Server load has fallen to 2.03 with
118 GiB available memory. No intervention was needed. The original 13 September
16:28 AEST deadline and four-hour check cadence remain unchanged.

## 2026-09-13 00:31 AEST — eight-hour pilot check

Both original workers remain active after 8 hours 3 minutes, each near 100%
CPU with unchanged RSS (2.03/2.08 GiB). There are zero pretraining and target
receipts, an empty run log and no exit marker; selected epochs and final fit
invariants remain unavailable. Source/config/lock state, wrapper and both
qualification hashes, and launch receipt hash are unchanged. Timeout PID
23201 still controls the original process group. Host load is 2.00 with
118 GiB available RAM. No intervention or extension: the deadline remains
16:28 AEST today, with the original 60-second termination allowance.

## 2026-09-13 04:32 AEST — first pilot checkpoint verified

The runner reports 1/200 architecture-screen pretraining tasks complete, with
zero target leaves. The completed block-0/fold-0/full/seed00 `bridge_wide` fit
selected epoch 3, completed 33 discovery/stopping epochs and replayed 3 epochs.
Its measured lifecycle runtime was 43,098.62 seconds (11.97 hours). The saved
payload and receipt were returned and their SHA-256 values matched deep-server.
Native checkpoint loading, finite tensors, source/accepted identity, frozen
budget, seed namespaces, initialization/replay/final-trunk binding, and an
independent replay of the stopping rule all passed. Reconstructing auxiliary
data locally reproduced the recorded roles, weights, focal-block exclusions,
167-head inventory and row counts. The compact verification receipt is under
`evidence/seawfb_dsdm/goal052/pilot-checkpoints/`; model payload remains private.

Both workers and the original timeout process group remain active after
12 hours 3 minutes, near 100% CPU each with 2.03/2.05 GiB RSS. Host load is
2.01 with 118 GiB available memory. Source/config/lock and qualification,
wrapper and launch hashes are unchanged. No ecological metrics were computed.
The original 16:28 AEST deadline and four-hour cadence remain in force.

## 2026-09-13 08:33 AEST — second pilot checkpoint verified

The runner reports 2/200 architecture-screen pretraining tasks complete and
zero target leaves. Block-0/fold-0/full/seed00 `bridge_control` completed
34 discovery/stopping epochs and replayed selected epoch 4, taking 55,597.17
seconds (15.44 hours). Returned payload and receipt hashes matched the server.
Native checkpoint load, finite tensors, identity, frozen budget, seed and
reset/replay/final-trunk checks passed. Independent stopping-history replay
selected epoch 4 with 30 subsequent stale epochs. Its data contract, heads and
role counts exactly match the previously reconstructed block-0/fold-0/full
contract. A second compact verification receipt is retained under
`evidence/seawfb_dsdm/goal052/pilot-checkpoints/`. The first checkpoint receipt
hash remains unchanged.

Both original workers remain active after 16 hours 4 minutes, approximately
100% CPU each with 2.11/2.05 GiB RSS. Load is 2.05; 118 GiB RAM remains available.
Original source, wrapper, qualification and launch bindings and timeout process
group are unchanged. No intervention, scoring or extension occurred. The
pilot still stops at 16:28 AEST today, plus its termination allowance.

## 2026-09-13 12:34 AEST — twenty-hour pilot check

Both original workers remain active after 20 hours 5 minutes at approximately
100% CPU, with 2.11/2.05 GiB RSS. The two previously verified pretraining
checkpoints retain their receipt hashes; no additional checkpoint or target
leaf has appeared. The log still reports 2/200 screen-pretraining tasks and
there is no exit marker. Source/config/lock, wrapper, qualification and launch
bindings are unchanged. The original timeout process remains active. Load is
2.01 with 118 GiB available RAM. No intervention or extension was needed.
The next scheduled check follows the 16:28 AEST deadline and should verify
termination, retrieve final evidence and review the bounded pilot outcome.

## 2026-09-13 16:34 AEST — pilot closed at its authorized cap

The exit marker was written at 16:28:12.507 AEST with status 124. No pilot
session, process group or residual semaphore files remained. Two pretraining
checkpoints survived, with no target leaves or new completions since the
sixteen-hour check. All final transferred files matched the closeout manifest;
both model checkpoints reloaded with unchanged verified hashes and state.
Source/qualification bindings remain unchanged. Completed lifecycle times sum
to 27.42 wall-worker hours, not exact accounting of the 48-worker-hour cap;
the two deeper fits were interrupted without resumable within-fit state.

The independent route review recommends a native eight-worker metric-free
canary before further production. `PilotReview.md` prepares a 30-minute/four-
worker-hour cap plus 60 seconds for termination; it requires a new resource
decision and has not run. Deep-server is idle with about 122 GiB RAM available.
The four-hour follow-up is paused. No ecological result, architecture choice,
new compute extension or scientific amendment was made.
