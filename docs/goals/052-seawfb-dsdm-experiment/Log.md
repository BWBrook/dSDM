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


## 2026-09-13 16:59 AEST — eight-worker qualification passed

Barry approved the 30-minute/four-worker-hour qualification. The CLI rejected
its hard-coded two-worker ceiling before fitting; the failed attempt is
preserved. A separately hashed driver called the unchanged canary worker,
with 16 jobs across eight spawned processes, within the original 17:22 AEST
deadline. It exited 0 at 16:59:38 AEST after 117.22 seconds. All eight PIDs
completed two jobs, and every fit field except runtime plus every prediction
and trunk digest matches the prior two-worker result. Independent checks
covered source/runtime, driver binding, finite state/loss, full data contracts,
q reuse, reset/replay, pairing, transfer and frozen state. All 18 manifest file
hashes match the server, including both preserved production checkpoints.

Peak worker RSS was 2.555 GiB; maximum sampled summed process RSS was 18.324
GiB (ten-second sampling; shared pages may be counted more than once). No
qualification process or semaphore remains. Fitting source stays `e309ca8`;
full-row parallel throughput is not measured. See `eight-worker-review.json`
and `eight-worker-manifest.json` under tracked Goal052 evidence. The new
48-hour/eight-worker continuation is prepared, not authorized or launched.
The four-hour follow-up remains paused pending that resource decision.


## 13 September 2026, 17:10 AEST — eight-worker continuation launched

Barry approved launch and granted standing authority to allocate compute
resources. `dsdm-goal052-pilot8` is running on deep-server from unchanged
fitting source `e309ca8`. The wrapper started at 17:10:11 AEST; its nominal
48-hour deadline is **15 September, 17:10:11 AEST**, plus 60 seconds for
termination. Eight workers are active at approximately one CPU each. The log
confirms reuse of both verified checkpoints (2/200 screen pretraining); no
new fit completion or ecological result is claimed at dispatch.

The private `pilot8-launch.json` binds source/qualification/wrapper hashes,
timestamps, process IDs and exact log/exit paths. Its preflight parent PID is
recorded separately from the observed wrapper PID because uv launches Python
as a child. Tracked launch verification is
`evidence/seawfb_dsdm/goal052/pilot8-launch.json`. Prelaunch checks passed for
current inputs, host runtime, both qualifications and all four existing
checkpoint files. The wrapper passed shell syntax validation. Host capacity
was about 122 GiB available RAM and load 0.16 before dispatch.

The existing `continue-dsdm-goal052` heartbeat is ACTIVE every four hours.
Follow the existing timeout group 30921 and runner 30930; do not duplicate or
reset this launch. At the cap, verify shutdown and returned checkpoints,
review measured throughput, then choose and execute the next justified
allocation under Barry's standing authority. Resource allocation alone no
longer requires approval. Record each subsequent allocation and review point.
Scientific changes and outer access retain their existing review boundaries.


## 13 September 2026, 21:12 AEST — four-hour continuation check

All eight original workers remain active in timeout group 30921 after
4 hours 2 minutes, at 99.9% CPU each with 1.98–2.09 GiB RSS. Host load is
8.00 and available RAM about 109 GiB, with no swap use. The two starting
pretraining checkpoints remain unchanged; no new pretraining completion or
target leaf has appeared. The log reports their reuse (2/200 screen tasks)
and there is no exit marker. This establishes active execution, not a new
fit result or throughput measurement.

Fitting identity, CPU runtime, qualification driver, canary/profile, wrapper
and launch hashes match the launch evidence; all four existing checkpoint
payload/receipt hashes remain unchanged. No intervention or resource change
is warranted. Continue the original 15 September 17:10 AEST deadline and
four-hour cadence; no scientific scoring or outer access occurred.


## 14 September 2026, 01:12 AEST — eight-hour continuation check

All eight original workers remain active in timeout group 30921 after
8 hours 2 minutes at 99.9% CPU each, with 1.98–2.08 GiB RSS. Host load is
8.38 and available memory about 109 GiB, with no swap use. The log remains
at the two reused pretraining checkpoints (2/200 screen tasks); no new
pretraining completion or target leaf is present, and no exit marker exists.
Both checkpoint payload/receipt hashes and the source, runtime, qualification
driver, canary/profile, wrapper and launch bindings remain unchanged.
No intervention is warranted. Continue the existing deadline of 15 September
17:10 AEST and four-hour cadence. No new fit result or ecological score is
claimed from worker activity.


## 14 September 2026, 05:13 AEST — third checkpoint verified

The continuation completed its first new pretraining fit, bringing the screen
total to 3/200 (three campaign pretraining checkpoints, zero target leaves).
Block-0/fold-1/full/seed00 `bridge_control` took 35,761.24 seconds (9.93 hours),
completed 31 discovery/stopping epochs and replayed selected epoch 1. Returned
payload and receipt hashes match deep-server. Native finite-state loading,
source/accepted baseline identity, frozen budget, seed namespaces and
initialization/replay/final-trunk binding passed. Independent stopping-history
replay selected epoch 1 followed by 30 stale epochs. Local reconstruction of
the auxiliary data exactly matched the saved roles, exclusions, transforms,
weights, 167 heads and row counts: 7,012,283 discovery, 1,910,059 stopping and
8,922,342 replay. The compact verification receipt is under tracked
`pilot-checkpoints/092e9604f871841f2a0160e1fda87bfd3fd05809a30966257d608c18b46fd8db.json`.
The model payload remains private.

All eight original workers remain active after 12 hours 3 minutes, at 99.9%
CPU each with 1.98–2.08 GiB RSS. Host load is 8.00, available memory about
109 GiB and swap use zero. Both starting checkpoints and source/runtime,
qualification, wrapper and launch bindings remain unchanged. No exit marker
or failure is recorded. No resource change is warranted; retain the original
15 September 17:10 AEST deadline and four-hour cadence. A single new fit does
not establish campaign throughput, comparative performance or a new epoch
budget. No ecological scores or outer outcomes were accessed.


## 14 September 2026, 09:14 AEST — nine checkpoints verified

Six new block-0/full/seed00 pretraining checkpoints passed verification,
bringing the architecture-screen total to 9/200 (seven new completions in
this continuation, plus two reused checkpoints). No target leaves exist.

| Architecture | Held fold | Lifecycle hours | Discovery epochs | Selected/replay epochs |
| --- | ---: | ---: | ---: | ---: |
| bridge_deep | 0 | 14.67 | 35 | 5 |
| seawfb_scale | 0 | 14.84 | 32 | 2 |
| bridge_deep | 1 | 12.65 | 32 | 2 |
| bridge_wide | 1 | 13.22 | 34 | 4 |
| bridge_control | 2 | 12.27 | 33 | 3 |
| bridge_wide | 2 | 13.33 | 35 | 5 |

All 18 current checkpoint payload/receipt files matched the remote transfer
manifest. Native loading verified finite tensors and saved trunk digests;
source/accepted identity, frozen budget, seeds and reset/replay invariants
passed. Independent stopping-history replay reproduced every selected epoch
and patience stop. Reconstructing block-0/fold-2 auxiliary data reproduced the
full role, head, exclusion, weight, transform and row contracts. Other new
receipts exactly matched the previously reconstructed fold-0/fold-1 contracts.
Six compact receipts were added to `evidence/seawfb_dsdm/goal052/pilot-checkpoints/`;
payloads and the transfer manifest remain private.

All eight original workers remain active after 16 hours 4 minutes at 99.9%
CPU each, with 2.01–2.11 GiB RSS. Host load is 8.00, available memory about
109 GiB, and swap use zero. Source/runtime/driver, qualifications, wrapper
and launch bindings are unchanged. No exit marker or recorded failure exists.
The deeper architectures have now produced verified checkpoints, but these
few fits do not establish a campaign ETA or comparative ecological performance.
Continue the original 15 September 17:10 AEST deadline and four-hour cadence
without intervention. No ecological scores or outer outcomes were accessed.


## 14 September 2026, 13:16 AEST — tenth checkpoint verified

Block-0/fold-1/full/seed00 `seawfb_scale` completed in 61,160.59 seconds
(16.99 hours), with 33 discovery/stopping epochs and selected/replay epoch 3.
The total is now 10/200 screen-pretraining fits: eight new completions during
this continuation and two reused checkpoints. No target leaves exist.

All 20 current checkpoint payload/receipt files matched the remote manifest;
the nine earlier verification hashes remain unchanged. The new checkpoint
passed native finite-state loading, source/accepted identity, frozen budget,
seed and initialization/replay/final-trunk checks. Independent stopping-rule
replay selected epoch 3 with 30 subsequent stale epochs. Its full auxiliary
data contract exactly matches the previously reconstructed block-0/fold-1
roles, exclusions, heads, transforms, weights and row counts. Compact evidence
is `pilot-checkpoints/0c32bc74fda811b03e2398baf3cb26d59fcc10e7cb5e648aa0699fe9baea20cd.json`;
model payload and transfer manifest remain private.

All eight original workers remain active after 20 hours 6 minutes, at 99.9%
CPU each with 2.03–2.11 GiB RSS. Load is 8.00; about 109 GiB RAM is available,
with no swap use. Source/runtime/driver, qualification, wrapper and launch
bindings remain unchanged. No exit marker or recorded failure exists. Continue
the existing 15 September 17:10 AEST deadline and four-hour cadence without
intervention. No ecological performance or outer outcome was evaluated.


## 14 September 2026, 17:16 AEST — halfway continuation check

All eight original workers remain active after 24 hours 6 minutes at 99.9%
CPU each, with 2.01–2.13 GiB RSS. Load is 8.00, available RAM about 109 GiB,
and swap use zero. No additional checkpoint has completed since the twenty-
hour check: 10/200 screen-pretraining fits remain verified, with zero target
leaves. The log still records ten completed/reused tasks and no exit marker
or failure is recorded.

All 20 existing checkpoint payload/receipt hashes match the verified manifest.
Source identity, CPU runtime, qualification driver, canary/profile, wrapper
and launch bindings are unchanged. The original timeout remains active.
Continue the second half of this allocation without intervention; retain the
15 September 17:10 AEST deadline and four-hour cadence. Process activity alone
does not establish within-fit progress or another completed result.


## 14 September 2026, 21:16 AEST — fifteen checkpoints verified

Five new block-0/full/seed00 pretraining fits passed verification, bringing
screen pretraining to 15/200: thirteen completed in this continuation plus
the two reused starting checkpoints. No target leaves exist.

| Architecture | Held fold | Lifecycle hours | Discovery epochs | Selected/replay epochs |
| --- | ---: | ---: | ---: | ---: |
| bridge_deep | 2 | 14.73 | 35 | 5 |
| bridge_control | 3 | 11.46 | 33 | 3 |
| bridge_wide | 3 | 14.38 | 36 | 6 |
| bridge_deep | 3 | 12.99 | 34 | 4 |
| bridge_control | 4 | 10.93 | 32 | 2 |

All 30 returned payload/receipt hashes match deep-server; the previous 20
remain unchanged. Native checkpoint loading verified finite tensors and
trunk digests. Source/accepted identity, frozen budgets, initialization,
seed namespaces, transfer flags and replay bindings passed. Independent
stopping-history replay reproduced each selected epoch and patience stop.
Reconstructed block-0/fold-3 and fold-4 full auxiliary contracts matched all
roles, heads, exclusions, transforms, weights and row digests/counts; fold 2
matched its previously reconstructed contract. Five compact receipts are in
`evidence/seawfb_dsdm/goal052/pilot-checkpoints/`. Payloads and the all-file
manifest `pilot8-check-20260914T1116Z.json` remain private.

All eight original workers remain active after 28 hours 6 minutes at 99.9%
CPU each, with 2.04–2.13 GiB RSS. Host load is 8.00, available RAM about
108 GiB, and swap use zero. Source/runtime/qualification driver, canary,
profile, wrapper and launch bindings are unchanged; no exit marker or
recorded failure exists. Retain the original 15 September 17:10 AEST cap and
four-hour cadence without intervention. No ecological scores or outer
outcomes were accessed. No new unread Fable message was present on the board.


## 15 September 2026, 01:18 AEST — eighteen checkpoints verified

Three new block-0/full/seed00 pretraining fits passed verification, bringing
screen pretraining to 18/200: sixteen completed in this continuation plus
the two reused starting checkpoints. No target leaves exist.

| Architecture | Held fold | Lifecycle hours | Discovery epochs | Selected/replay epochs |
| --- | ---: | ---: | ---: | ---: |
| seawfb_scale | 2 | 16.72 | 32 | 2 |
| seawfb_scale | 3 | 16.32 | 33 | 3 |
| bridge_wide | 4 | 13.07 | 33 | 3 |

All 36 returned payload/receipt hashes match deep-server; the previous 30
remain unchanged. Native finite-state loading, trunk digests, source/accepted
identity, frozen budgets, initialization, seeds, transfer flags and replay
bindings passed. Independent stopping-history replay reproduced selected
epochs and patience stops. Each full auxiliary data contract matched its
previously reconstructed block-0/fold-2, fold-3 or fold-4 contract, including
roles, heads, exclusions, transforms, weights and row digests/counts.
Three compact receipts are in `evidence/seawfb_dsdm/goal052/pilot-checkpoints/`.
Payloads and manifest `pilot8-check-20260914T1518Z.json` remain private.

All eight original workers remain active after 32 hours 8 minutes at 99.9%
CPU each, with 2.04–2.18 GiB RSS. Load is 8.00, available RAM about 108 GiB,
and swap use zero. Source/runtime/driver, canary/profile, wrapper and launch
bindings are unchanged; no exit marker or recorded failure exists. Continue
to the original 15 September 17:10 AEST cap with four-hour checks. No
partial-grid ecological scoring or sealed outer access occurred.

Correspondence thread 32 contains Fable's supplementary-analysis proposal
(message 162) and Astra's review (169), posted before any Goal052 target
leaves. This is an open proposal, not an accepted supplement or protocol
amendment. Outstanding issues include distinguishing composition sensitivity
from calibrated uncertainty under shared-data dependence, retaining all three
frozen full-data panels, separating within-target and between-target count
associations, and avoiding effort-mechanism claims from richness strata.
The review requests a narrower specification; fitting and scoring contracts
remain unchanged. The discussion does not require an immediate Barry decision.


## 15 September 2026, 05:19 AEST — thirty-six-hour continuation check

All eight original workers remain active after 36 hours 9 minutes at 99.9%
CPU each, with 2.04–2.18 GiB RSS. Load is 8.00, available RAM about 108 GiB,
and swap use zero. No additional checkpoint has completed since the previous
check: 18/200 screen-pretraining fits remain verified, with zero target leaves.

All 36 checkpoint payload/receipt hashes match the previously verified
`pilot8-check-20260914T1518Z.json` manifest. Source identity, CPU runtime,
qualification driver, canary/profile, wrapper and launch bindings are
unchanged. The original timeout is active; no exit marker or traceback is
recorded. Continue to the original 15 September 17:10 AEST cap, with four-hour
checks. Process activity alone does not establish within-fit progress.
No ecological scoring, outer access or scientific amendment occurred.
There is no new unread board message from Fable.


## 15 September 2026, 09:20 AEST — twenty-two checkpoints verified

Four new full-auxiliary/seed00 pretraining fits passed verification, bringing
screen pretraining to 22/200: twenty completed in this continuation plus
two reused starting checkpoints. No target leaves exist.

| Block | Architecture | Held fold | Lifecycle hours | Discovery epochs | Selected/replay epochs |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | bridge_deep | 4 | 13.96 | 33 | 3 |
| 1 | bridge_control | 0 | 14.06 | 37 | 7 |
| 1 | bridge_wide | 0 | 11.77 | 33 | 3 |
| 1 | bridge_deep | 0 | 12.28 | 32 | 2 |

All 44 returned payload/receipt hashes match deep-server; the previous 36
remain unchanged. Native finite-state loading, trunk digests, source/accepted
identity, frozen budgets, initialization, seeds, transfer flags and replay
bindings passed. Independent stopping-history replay reproduced every selected
epoch and patience stop. Reconstruction of the block-1/fold-0/full auxiliary
contract matched all three new block-1 receipts, including roles, exclusions,
heads, transforms, weights and row digests/counts. The remaining fit matched
the previously reconstructed block-0/fold-4 contract. Four compact receipts
are in `evidence/seawfb_dsdm/goal052/pilot-checkpoints/`; payloads and manifest
`pilot8-check-20260914T2319Z.json` remain private.

All eight original workers remain active after 40 hours 9 minutes at 99.9%
CPU each, with 2.03–2.18 GiB RSS. Load is approximately 8.00, available RAM
about 108 GiB, and swap use zero. Source/runtime/driver, canary/profile,
wrapper and launch bindings are unchanged. No exit marker or traceback is
recorded. Continue to the original 15 September 17:10 AEST cap with four-hour
checks; no allocation or scientific change is warranted during active fits.
No ecological scores or sealed outer outcomes were accessed. There is no
new unread Fable message on the board.


## 15 September 2026, 10:12 AEST — daily cadence requested

Barry noted that four-hour checks waste tokens at the observed completion
rate and requested 24-hour checks. Updated the existing heartbeat to daily
17:20 Australia/Hobart, placing the next review just after today's original
48-hour cap. No run was interrupted or deadline extended. Higher concurrency
is preferred for the successor allocation: first qualify 24 single-thread
CPU workers if live capacity supports it, then choose a production bound
that avoids frequent loss of unfinished fits. No new qualification or
production job was launched during this scheduling update.


## 15 September 2026, 17:30 AEST — 24-worker continuation launched

The eight-worker allocation stopped at 17:10:11 AEST with exit 124; shutdown
and all 26 checkpoints passed verification. It completed 24 new fits in
48 hours (0.5/hour), reusing two earlier fits. Completed new lifecycles ranged
9.93–18.41 hours (mean 13.67); this is conditional on completion and excludes
interrupted work. No target leaves or ecological results exist. Closeout
receipts are `pilot8-review.json` and `pilot8-closeout-manifest.json` under
tracked Goal052 evidence. All 52 payload/receipt hashes and final log/exit
hashes match deep-server.

The separate 24-worker canary ran 17:24:25–17:26:49 AEST, exit 0, within its
30-minute/12-worker-hour cap. Two barrier-synchronized waves exercised all
24 spawned PIDs twice. Every non-runtime result field matched the preserved
eight-worker qualification, including prediction/trunk digests, data
contracts, finite states, stopping/replay, initialization, transfer and freeze
invariants. Peak worker RSS was 2.564 GiB; maximum sampled process-group RSS
was 58.643 GiB (two-second samples; shared pages may be counted more than once).
No qualification workers or semaphore files remained. The private transferred
artifacts passed all eight file hashes. See `twentyfour-worker-review.json`.

The new canary was promoted to `metadata/goal052_canary.json`; the previous
receipt is preserved under private `qualification-history/e309ca8-eight-worker/`.
The current canary SHA is `ad9d25d1c0baf843a19b2affa4baa74f4e6f103106db06730a7a98cd6fa4af6b`.
The frozen fitting source and full-row profile remain unchanged. The separate
driver `scripts/goal052_canary24.py` and continuation wrapper each have their
own bound hashes. No scientific configuration changed.

`scripts/goal052_continue24.sh` launched at 17:29:30 AEST in
`dsdm-goal052-continue24`, capped at 168 hours / 4,032 worker-hours plus
60 seconds termination. Deadline: **22 September, 17:29:30 AEST**. The longer
window reduces repeated loss of unfinished fits; daily reviews can stop
execution earlier. The server has 32 physical cores, 64 logical CPUs and
125 GiB RAM. At startup all 24 workers were active at approximately one CPU
each, with about 80 GiB RAM still available and zero swap use. Actual full-data
24-worker throughput remains unmeasured; no proportional speedup is claimed.

The runner is PID 45460, timeout PID 45451, wrapper PID 45312. Private
`continuation24-launch.json` contains the immutable allocation binding;
tracked `continuation24-launch-review.json` adds actual worker PIDs and log
path. All 26 initial scheduler completions match pre-existing checkpoint IDs
and unchanged payload/receipt hashes. No new completed fit is claimed at
launch. Do not duplicate this scheduler or reset its deadline.

The daily heartbeat now runs at **17:40 Australia/Hobart**, so its final-day
review falls after the cap; this supersedes 17:20 and historical four-hour
instructions. Retain daily cadence and concise reporting. No partial-grid
scoring, outer access, full refit, mapping or scientific amendment occurred.


## 16 September 2026, 17:43 AEST — first day at 24 workers

Twenty-four new pretraining checkpoints passed verification, bringing the
screen total to 50/200. No target leaves exist. All 100 returned payload/receipt
hashes match deep-server; the 26 starting checkpoints are unchanged. New
finite-state, trunk, identity, budget, seed, initialization, transfer and
stopping/replay checks passed. Reconstructed six previously unseen auxiliary
contracts (block 1/folds 2–4; block 2/folds 0–2), matching all roles, exclusions,
heads, transforms, weights and row digests/counts. Other receipts matched
previously reconstructed contracts. Compact receipts and
`continue24-day1-review.json` are tracked; payloads and
`continue24-check-20260916.json` remain private.

The 24 new lifecycles took 13.20–23.25 hours (mean 16.71), with 32–35 discovery
epochs and selected/replay epochs 2–5. Approximately 24.2 hours of allocation
produced these 24 completions, versus 24 in the previous 48-hour allocation.
This is a descriptive throughput comparison, not a controlled scaling test:
task mix differs and unfinished work is excluded. No campaign ETA is inferred.

All 24 original workers remain active at 99.9% CPU, RSS 2.02–2.15 GiB each.
Load is about 24, available memory 81 GiB and swap use zero. Source/runtime,
canary/driver/profile, review and immutable launch bindings are unchanged;
no exit or traceback exists. Continue the same allocation to its original
22 September 17:29:30 AEST cap, with daily 17:40 checks. No ecological scoring
or sealed outer access occurred. No unread Fable reply was present.


## 17 September 2026, 17:44 AEST — second day at 24 workers

Thirty-three new pretraining checkpoints passed verification, bringing the
screen total to 83/200 (57 new in approximately 48.2 allocation hours).
Target leaves remain zero. All 166 returned payload/receipt hashes match
deep-server, and all previously verified hashes remain unchanged. New
finite-state, trunk, identity, budget, seed, initialization, transfer and
stopping/replay checks passed. Reconstructed nine new auxiliary contracts:
block 2/folds 3–4, block 3/all five folds, block 4/folds 0–1. Roles, exclusions,
heads, transforms, weights and row digests/counts matched. Other new fits
matched previously reconstructed contracts. Compact evidence is
`continue24-day2-review.json` and the new checkpoint receipts; payloads and
`continue24-check-20260917.json` remain private.

New completed lifecycles took 12.62–23.35 hours (mean 16.52), with 31–38
discovery epochs and selected/replay epochs 1–8. The last day produced 33
completions; this observed rate does not establish a full-campaign ETA.
All 24 original workers remain active at 99.9% CPU, RSS 2.01–2.21 GiB each.
Host load is approximately 24, available memory 81 GiB, and swap use zero.
Source/runtime, canary/driver/profile/review and launch bindings are unchanged;
no exit marker or traceback exists. Continue the original allocation and
daily cadence. No ecological scoring or sealed outer access occurred, and
there is no unread Fable reply.


## 18 September 2026, 17:43 AEST — third day at 24 workers

Thirty-three new pretraining checkpoints passed verification, bringing the
screen total to 116/200 (90 new in approximately 72.2 allocation hours).
Target leaves remain zero. All 232 returned payload/receipt hashes match
deep-server; previous checkpoint hashes are unchanged. New finite-state,
trunk, identity, budget, seed, initialization, transfer and stopping/replay
checks passed. Reconstructed nine new auxiliary contracts: block 4/folds
2–4, block 5/all five folds, block 6/fold 0. All roles, exclusions, heads,
transforms, weights and row digests/counts matched; other fits matched
previously reconstructed contracts. Compact evidence is
`continue24-day3-review.json` and the checkpoint receipts. Payloads and
`continue24-check-20260918.json` remain private.

New completed lifecycles took 12.13–21.97 hours (mean 16.55), with 31–35
discovery epochs and selected/replay epochs 1–5. All 24 original workers
remain active at 99.9% CPU, RSS 2.02–2.18 GiB each. Load is approximately 24,
available memory 81 GiB, and swap use zero. Source/runtime, canary/driver/
profile/review and immutable launch bindings are unchanged; no exit marker
or traceback exists. Continue the same allocation and daily checks. No
ecological scoring or sealed outer access occurred. No unread Fable reply
was present.


## 19 September 2026, 17:43 AEST — fourth day at 24 workers

Thirty-two new pretraining checkpoints passed verification, bringing the
screen total to 148/200 (122 new in approximately 96.2 allocation hours).
Target leaves remain zero. All 296 returned payload/receipt hashes match
deep-server; previous checkpoint hashes are unchanged. New finite-state,
trunk, identity, budget, seed, initialization, transfer and stopping/replay
checks passed. Reconstructed eight new auxiliary contracts: block 6/folds
1–4 and block 7/folds 0–3. All roles, exclusions, heads, transforms, weights
and row digests/counts matched; other fits matched previously reconstructed
contracts. Compact evidence is `continue24-day4-review.json` and the new
checkpoint receipts. Payloads and `continue24-check-20260919.json` remain private.

New completed lifecycles took 13.63–24.22 hours (mean 18.40), with 32–36
discovery epochs and selected/replay epochs 2–6. All 24 original workers
remain active at 99.9% CPU, RSS 2.04–2.20 GiB each. Load is approximately 24,
available memory 80 GiB, and swap use zero. Source/runtime, canary/driver/
profile/review and immutable launch bindings are unchanged; no exit marker
or traceback exists. Continue the same allocation and daily checks. No
ecological scoring or sealed outer access occurred. No unread Fable reply
was present.


## 20 September 2026, 17:43 AEST — fifth day at 24 workers

Thirty-five new pretraining checkpoints passed verification, bringing the
screen total to 183/200 (157 new in approximately 120.2 allocation hours).
Target leaves remain zero. All 366 returned payload/receipt hashes match
deep-server; previous checkpoint hashes are unchanged. New finite-state,
trunk, identity, budget, seed, initialization, transfer and stopping/replay
checks passed. Reconstructed eight new auxiliary contracts: block 7/fold 4,
block 8/all five folds and block 9/folds 0–1. All roles, exclusions, heads,
transforms, weights and row digests/counts matched; other fits matched
previously reconstructed contracts. Compact evidence is
`continue24-day5-review.json` and the new checkpoint receipts. Payloads and
`continue24-check-20260920.json` remain private.

New completed lifecycles took 13.86–25.82 hours (mean 17.56), with 31–36
discovery epochs and selected/replay epochs 1–6. All 24 original workers are
alive, RSS 1.60–2.18 GiB each. A two-second CPU sample found 17 busy and
seven idle, consistent with the 17 remaining fits: the frozen runner waits
for the entire pretraining stage before submitting target fits. Load is
17.56, available memory about 83 GiB, and swap use zero. Source/runtime,
canary/driver/profile/review and immutable launch bindings are unchanged;
no exit marker or traceback exists. Continue the same allocation and daily
checks. No ecological scoring or sealed outer access occurred. No unread
Fable reply was present.


## 21 September 2026 — architecture screen complete; remaining pretraining active

The runner completed all 200 screen-pretraining checkpoints and all 1,460
screen target leaves, then selected `seawfb_scale` using the frozen rule.
The screen-pretraining stage's last receipt was written at 21:33:52 UTC on
20 September (134.07 hours after launch, including 26 initial checkpoints
reused). Selection was written at 00:11:41 UTC on 21 September, about 2 hours
38 minutes later. The runner automatically entered the remaining 700-job
pretraining stage. At today's snapshot 17 of those were complete, giving
217 pretraining checkpoints overall and 34 new since yesterday.

All 434 pretraining payload/receipt hashes passed; the previous 183 pairs
are unchanged. All 34 new fits passed native finite-state loading, identity,
seed, initialization, transfer/freeze, independent stopping-history replay,
epoch and data-contract checks. Seven newly reconstructed auxiliary contracts
covered block 9/folds 2–4/full and block 0/folds 0–2/20 plus fold 0/80. The
checkpoint inventory exactly matches the full 200-job screen plus 17 jobs
from the frozen remaining grid. New screen lifecycles took 12.99–20.36 hours
(mean 16.55); new remaining-grid fits took 1.43–7.18 hours (mean 2.44). These
use different auxiliary sizes and must not be pooled into a campaign ETA.
All new selected/replay epochs were 2–15, discovery epochs 32–45.

All 24 original workers remain alive and busy in a two-second CPU sample,
with RSS 1.86–2.20 GiB each, load 24.08, about 83 GiB available RAM and no
swap use. Source/runtime, canary/driver/profile/review and immutable launch
bindings are unchanged; no exit marker or traceback exists. Continue through
the original 22 September 17:29:30 AEST cap plus termination allowance.
Tomorrow's daily 17:40 check will verify shutdown and choose the next bounded
allocation under Barry's standing authority. The heartbeat now records the
new stage, observed timing and quiet routine-check policy. No sealed outer
access, partial-grid ecological scoring or scientific amendment occurred.
No unread Fable reply was present at the start of this check.


Independent completed-screen verification passed all 2,921 transfer hashes
(2,920 leaf files plus selection), the exact 73-target/four-architecture/
five-fold grid, and all 1,460 native leaf, role/subset, fit, initialization,
transfer and stopping-history checks. Additional receipt checks covered
head/shuffle seeds, completed/replay epochs, row counts, held-row digests,
encoder/transform identities, feature width and stopping termination rules.
The full frozen aggregator was replayed only after the grid was complete;
its selection digest exactly matched the returned `selection.json`:
`56c82a967664b36c8bd0dd72287ca89b9bdf310714098e8d1c72074d71c36710`.
Target selected/replay epochs ranged 1–15. The diagnostic leave-one-block-out
winners also all matched, without changing the frozen selection rule.
This validates the architecture selection, not ecological superiority over
controls. Compact evidence: `selection-screen-review.json`; daily pretraining
and resource evidence: `continue24-day6-review.json`. Private payloads and
`continue24-check-20260921.json` are retained locally.

The temporary verifier's trailing optional mean-AUC print raised a KeyError
after all required checks and exact replay had passed. No fitting code or
production output was affected; the compact review records that diagnostic
exit separately from the passed checks. No fits or numerical checks were
repeated to repair the print.

Posted this verified milestone to Correspondence thread 32, message 455;
no new advisor review or scientific decision was requested.

## 21 September 2026 — kunanyi preparation after Barry's resource request

Consulted X-ray's PBS scripts and storage history. Its proven 28-core node
layout and 48-hour queue usage apply operationally; its Anaconda environment
is not a dSDM qualification. Live hardware probe 810868 completed F/0 on n078
(28 physical cores, 125 GiB RAM, GLIBC 2.17, Apptainer 1.3.2). Container probe
810869 completed F/0 on n001 in 22 seconds, running official Ubuntu 24.04 with
GLIBC 2.39. Scratch upload failed at close with a zero-byte file; home upload
succeeded. Use `/u/bwbrook/codex_kunanyi/dsdm-goal052` and 45-second nested SSH
connection timeout. Barry completed the institutional login; routine portal
refresh renews the same five-minute SSH window.

Prepared a checksummed, retained-only 3,748-file snapshot (217 pretraining
checkpoints and 1,460 screen leaves), qualification drivers, PBS wrappers, and
an external sharding adapter. Nine focused adapter tests passed. Direct native
inventory comparison confirmed 700 and 41,250 disjoint checkpoint keys. No
fitting source changed. The first runtime snapshot stopped on a bare-ldd
wheel-library resolution issue; corrected handling preserves the complete
wheel trees and loaded system-library closure. The resulting exact Python
image imports the native runner and passes a basic tensor check. Numerical
qualification on PBS remains required; no production fits have started there.
The initial login-node tar extraction timed out after its archive checksum
passed; the PBS qualification wrapper uses a fresh root and extracts afresh.
See `Kunanyi.md` and `kunanyi-preparation-review.json` for current bindings.

Numerical qualification job **810907.kunanyi-ohpc** was submitted after all
transferred runtime/driver/wrapper checksums passed. Its output is
`/u/bwbrook/codex_kunanyi/dsdm-goal052/dsdm052_buildqual.o810907`;
its isolated build/root is `build-810907.kunanyi-ohpc`. Inspect completion
and evidence at the next daily check; do not submit a duplicate.

## 22 September 2026 — cap closeout and institutional access blocker

The daily check found no Goal052 workers or tmux session on deep-server after
its original cap, with approximately 122 GiB available RAM. Final checkpoint
and exit verification proceeds independently of the PBS access issue.

SSH refused access to kunanyi because the MFA admission window expired.
Refreshing the existing Enable SSH page redirected to UTAS Microsoft sign-in.
Barry was asked to complete that login and enable SSH; the page is retained.
The result of qualification job 810907 is unknown, so no replacement job,
production dispatch, changed numerical setting or competing deep-server run
was launched. The existing daily heartbeat and Nectar records were updated.
Correspondence thread 32 has no new messages after the verified milestone 455.

Final closeout passed: exit 124, 272 complete pretraining checkpoints, including
55 new pairs copied locally (20 auxiliary-20, 23 auxiliary-80, 12 full).
New fit durations were 1.30–2.51, 7.04–9.38 and 18.51–24.39 hours respectively.
These support a long PBS bound; unlike auxiliary sizes do not support a pooled
campaign ETA. The stage ended at 72/700 remaining-pretraining completions.
All 272 native checkpoint, finite-state, seed/stopping/replay and exact data
metadata checks passed. Source/launch/qualification bindings are unchanged.
Parent checks independently confirmed matching remote/local inventory digest
`bd04c2b978a47799b90763e4f5cff553cabbf46e9ac7a340e5188a360e62efef`,
unchanged prior day6 checkpoint/screen hashes, available native run lock and
no remaining multiprocessing semaphores. The shutdown log's semaphore warning
therefore did not leave semaphore files. No new numerical work was launched.

## 23 September 2026 — exact PBS qualification and 25-node dispatch

Barry restored TPAC access. Existing job 810907 completed on n234 with exit 0
in 75m12s. Its 56 canary jobs across 28 PIDs and full-row profile match the
accepted Linux scientific fields exactly. PBS peak memory was 55.9704 GiB;
the original process sampler failed before producing any rows. That limitation
is retained. The repaired procfs sampler passed a live Linux check; future
hosts must show all canary worker PIDs and summed RSS below 100 GiB.

Preparation job 811257 exited 0 after importing all 272 checkpoint pairs.
All 544 file hashes match the accepted closeout inventory. The returned native
700-task manifest was replayed independently and partitions exactly into 25
non-overlapping shards, each with 24–26 unfinished fits. Deep-server is stopped.
Fitting source remains e309ca8 / fce7fb52..., with accepted data/config/q/lock
bindings unchanged. Engineering code is committed as 3280156.

Independent launch review and 13 focused tests passed. Jobs 811265–811289
were submitted to normal, each with one 28-CPU node, 110 GiB and 48 hours.
The initial snapshot has ten running jobs and fifteen queued for insufficient
free CPUs. Each job first qualifies its actual host against the accepted pilot
using a reviewed exact-comparison verifier; only then may its native task shard
claim ownership and fit. This is a submitted allocation, not evidence that
production fits have completed. The 48-hour cap starts from each PBS start
and must not be reset. A fixed dispatch directory and durable rank/job records
prevent accidental duplicate submissions; persistent ownership prevents
concurrent writers.

See `kunanyi-node-qualification-review.json` and
`kunanyi-pretraining-launch-review.json` under tracked Goal052 evidence.
Private `handoff/production-launch.json` binds every driver, SIF, input archive,
reference receipt and manifest. Retain daily 17:40 monitoring. No final targets
until all 900 pretraining checkpoints validate, no aggregation before the
complete unique target grid, and no sealed outer outcomes or scientific changes.

Correspondence thread 32 was checked through message 455 (no new foreign
messages) and updated with the verified PBS milestone as message **467**.
The existing heartbeat now points to this allocation at the unchanged daily
17:40 cadence. Future task-local board checks should begin after message 467.

## 23 September 2026 — first daily PBS production check

At 17:44 AEST, all 25 existing jobs were running on distinct hosts. All 25
canaries passed exact comparison; fourteen completed full profiles and
repaired sampler reviews passed independent verification, with matching
production owner claims. Eleven recent starters were still profiling.
No job exit, failure or rank completion was observed.

All 93 new checkpoint pairs passed hash, finite-state, seed/init/transfer/
freeze, independent stopping/replay and exact data-contract checks and were
preserved locally. Total 365/900; remaining-pretraining stage 165/700, leaving
535 fits. All new completions are auxiliary-20 (1.31–2.37 hours, median 1.67),
so they do not yet support a full-campaign ETA. Maximum sampled RSS was
46.67 GiB in production and 65.17 GiB during qualification. Source, config,
lock, driver, launch, manifest and selection bindings remain unchanged.

Continue the existing allocation without resubmission or changed ownership.
Original caps fall on 25 September between 11:07:47 and 17:35:20 AEST, before
the daily check. Tracked `kunanyi-day1-review.json` binds the private returned
snapshot and both independent audits. Project/Nectar records and the existing
daily heartbeat were refreshed. Correspondence thread 32 has no new messages
after 467. No final targets, ecological scores or scientific changes.

## 24 September 2026 — daily check blocked by TPAC authentication

The existing SSH route rejected expired MFA admission. Opening Enable Jumpbox
SSH redirected to UTAS sign-in, and Chrome blocked automation because an
extension UI was open. Barry was asked to finish sign-in, dismiss that popup
and enable SSH. Current jobs, progress and resource use remain unverified.
The prior snapshot and audit references are unchanged; 365 checkpoint receipts
remain local. No new fits were launched and no source, ownership or cap changed.
The project/Nectar records and existing daily follow-up now record this blocker.
Original caps remain 25 September 11:07:47–17:35:20 AEST.

See `kunanyi-access-20260924.json`. Correspondence thread 32 returned no new
messages after 467; save retrieval cursor 518 for the next check.

## 25 September 2026 — pretraining complete and final-target preparation

Barry restored TPAC access. PBS history confirms all 25 jobs 811265–811289
finished with exit 0 in 20h46m–24h39m. Returned exit, owner, completion and
actual-host qualification receipts agree exactly. The final eleven profiles
passed independent numerical/resource verification; fourteen profiles and all
25 canaries reused their prior accepted hashes. Peak sampled group RSS was
46.819 GiB in production and 65.170 GiB in qualification; PBS peak memory was
62.326 GiB.

Retrieved and validated the remaining 535 checkpoint pairs: 122 auxiliary-20,
225 auxiliary-80 and 188 full. Median fit times were 1.72, 7.50 and 18.92 hours,
respectively; these size groups are not pooled into a campaign ETA. All new
atomic file/hash, finite-state, native fit, seed/init/transfer/freeze,
independent stopping/replay and exact data-contract checks passed. The prior
365 pairs were preserved under exact hashes. The full native inventory has
900 unique keys and 1,800 exact payload/receipt files. See tracked
`kunanyi-pretraining-completion-review.json`; the private return archive,
checkpoint/host reviews and reproducible audits are in `kunanyi-check-20260925`.

The final-target manifest has 48 disjoint shards, 41,250 tasks and 365 cached
screen fits, leaving 40,885 new fits. Preparation job 811744 exited 0 after copying and
checking the verified inputs in a fresh `targets-20260925` root, preserving the
completed pretraining root. Its 12m13s execution independently reproduced the
manifest and verified the full imported checkpoint and screen-leaf inventories. The reviewed dispatch invocation requires its exact
staging receipt and fresh PBS F / exit 0 before submitting jobs. Engineering
commit e70fd46 adds the final-stage launch gate; 20 focused tests passed.
Fitting source e309ca8, accepted inputs/config/lock/q surfaces and selection
remain unchanged. No ecological scoring or sealed access occurred.


The reviewed staging gate passed before submission. Jobs **811750–811797**
are now the sole active Goal052 allocation. The returned 10:37 AEST snapshot
verified all 48 running on distinct hosts, correct 28 CPU / 110 GiB / 48-hour
resources, exact rank/root/launch/manifest environment, unchanged drivers and
pilot references, and no exit receipts. Original caps are **27 September
10:37:06–10:37:11 AEST**. This is launch/startup evidence; host qualification
and new target leaves are not yet accepted. See `kunanyi-target-launch-review.json`.
The one-shot external dispatch gate checks identity against the bound manifest;
a local preflight caught and corrected an attempted lookup in the launch JSON
before any target submission. The support archive and active drivers were unchanged.

The existing daily 17:40 heartbeat now follows this allocation. Project and
Nectar records were updated, and Correspondence thread 32 received message
531; use retrieval cursor 531 on the next check. No scientific or sealed-data
boundary changed.


## 25 September 2026 — PBS email replaces the daily monitor

Barry requested the X-ray Cavities email pattern because inactive TPAC portal
sessions expire. Deleted automation `continue-dsdm-goal052`; wait for Barry's
message after the email instead of scheduling further checks. This supersedes
the daily-cadence instructions above.

Notification job **811800.kunanyi-ohpc** (`ds052_notify`) was submitted at
10:52 AEST. Returned PBS state verifies a system dependency hold (`H` / `s`),
`afterany` on all 48 original jobs 811750–811797, recipient
`barry.brook@utas.edu.au`, mail points `ae`, one CPU, 256 MiB, two minutes and
no automatic rerun. The dependency releases after every production job ends,
regardless of exit status. All predecessors had already started. Email is
configured through the PBS route previously confirmed by Barry in X-ray
Cavities; future delivery is not yet claimed.

The new notification script only records scheduler state. Active production
scripts, launch/source bindings, rank ownership and caps are unchanged. An end
email is not scientific acceptance: after Barry resumes, inspect stopped-job
and qualification receipts and validate the complete unique target grid before
aggregation. See `kunanyi-notification-review.json` and private
`kunanyi-target-notification/`; remote notification records are under
`/u/bwbrook/codex_kunanyi/dsdm-goal052/notifications-targets-20260925`.
Correspondence thread 32 message/cursor 533 records the new workflow.

## 25 September 2026 — target allocation completed; native acceptance running

Barry reported the notification email. Job 811800 exited 0 at 14:24:01 AEST;
its zero-second runtime belongs to the administrative notifier. All 48 target
jobs 811750–811797 exited 0 after 3h22m33s–3h46m50s. Independent review passed
1,129 host/qualification/ownership/completion checks with no failures. All
42,345 expected unique target receipt pairs are present. Peak sampled RSS was
64.974 GiB during qualification and 40.578 GiB during production. Frozen source,
drivers, manifest and launch bindings passed; no simulation restart is needed.

Transfer job 812035 exited 0 after 4m09s, producing eight archives (5.83 GB)
and exact hashes for 84,690 files. Native validation runs beside these data on
Kunanyi while the archives return. Initial validator 812145 failed after 18
seconds at helper import: `SCRIPT.parents[6]` assumed the deeper Mac path.
It reached neither leaf audit nor aggregation. The corrected helper passed a
shallow-path import and all 1,460 preserved screen receipt-contract checks.

Replacement validator 812148 started at 15:13:21 AEST on n001 and was verified
running at 15:14:04. It requests one CPU, 16 GiB and four hours, with PBS
end/abort email to Barry. Complete leaf/hash/contract validation precedes
unchanged native aggregation and independent `validate_outputs`; acceptance
remains pending. No fitting code or scientific policy changed. Preserve both
validation attempts and inspect the existing replacement after Barry resumes;
the daily automation remains deleted.

Evidence: `kunanyi-target-completion-review.json`,
`kunanyi-validation-first-attempt-review.json`, `kunanyi-validation-launch-review.json`
and private `kunanyi-target-closeout-20260925/`.

Local return subsequently completed: all eight archive hashes and 84,690 file
hashes passed, and 40,885 new pairs were imported without changing any of the
1,460 preserved screen pairs. All 42,345 pairs are now local; private
`import-review.json` binds this return. Scientific acceptance remains pending.
Correspondence thread 32 message 548 records the production/validation handoff.

## 25 September 2026, evening — validator wall-time closeout and continuation

Barry reported exit 271. Live PBS history and output confirm 812148 exceeded
its four-hour limit: it ended at 19:14:59 AEST after 4h01m38s, using 3h28m23s
CPU and 2.97 GiB peak memory. The allocation was too short. The complete leaf
audit passed at 17:31:15 (2h17m54s after start), validating all 42,345 pairs and
preserved checkpoint hashes. The job was aggregating when terminated; no
summary or native acceptance artifact exists. The shell's zero-valued EXIT
receipt is misleading after external termination; PBS F/271 and the explicit
kill diagnostic are authoritative. All evidence is preserved in private
`validation-v2-closeout/`; tracked review is `kunanyi-validation-timeout-review.json`.

Independent review supports reusing the passed audit only after exact rehash
of every leaf/pretraining/screen file and unchanged source, inputs, runtime,
manifest and prior audit bindings. Continuation **812164** started at
**21:43:51 AEST**, requesting the same n001 host, one CPU, 16 GiB and **24 hours**.
It resumes unchanged native aggregation and independent `validate_outputs`;
no fitting or numerical amendment occurs. It holds the native run lock and
writes phase/fold-group progress. Support checks covered argument/result
preservation, propagated errors, shell syntax and success/failure/SIGTERM exit
receipts. PBS end/abort email remains the handoff; the daily monitor is deleted.
See `kunanyi-validation-continuation-review.json`. Acceptance is still pending.


## 26 September 2026 — native acceptance and local return complete

Barry reported successful completion. Live PBS history confirms **812164**
ended **F / exit 0 at 01:41:50 AEST**, after **3h57m59s**, with 3h47m37s CPU
and 2.140 GiB peak memory. Wrapper and phase receipts independently report
exit 0 and complete. The current user queue is empty.

The full saved-file rehash passed before audit reuse; unchanged native selection
and aggregation then completed, followed by independent `validate_outputs`.
Its `goal052_complete_valid` receipt covers 900 pretraining lifecycles, 42,345
unique target lifecycles and 449 conditions, with 365 reused screen leaves and
zero outer-response rows. No fit or scientific source changed.

Returned `validation-completion-20260926.tar.gz` is 5,370,018 bytes, SHA256
`22d68acdab7874f2fae5d1d16708b78449fad2ab8d91a8e4674dce8413f3be91`.
All 16 evidence-file hashes and 87 local checks passed, including current
source/input/q identity and exact canonical imports. The accepted aggregate
is now `evidence/seawfb_dsdm/goal052/summary.json`; private `complete.json` is
byte-identical to the remote native receipt. Existing saved fits remain intact.
Private `acceptance-return-review.json` and its audit script preserve checks;
tracked `completion_review.json` binds the complete chain.

A bounded independent read-only review found no acceptance blocker and confirmed
aggregate privacy. `Results.md` records all four primary comparisons and required
mechanistic/block-stability diagnostics. Full fine-tuning shows a small mean
inner advantage, smaller among the 84 targets outside architecture selection;
scientific review of magnitude and heterogeneity remains. Keep polling deleted
and preserve sealed outer outcomes. No further fitting or validation is needed.

Correspondence thread 32 message 562 records acceptance and the first descriptive
readout, and requests Fable's focused scientific critique. Retrieval cursor is
561. All 16 comparison-table values and both absolute primary AUC values were
independently checked against the accepted aggregate before posting.


## 27 September 2026 — Fable critique checked; outer note proposed

Read Correspondence thread 32 through cursor 573, including Fable message 566.
Reproduced the conventional margins, learning-size and auxiliary-size panels,
56/73 cross-endpoint result, presence tertiles, ten block means and
Climacteris erythrops fold diagnostics from the accepted tracked aggregate.
The new review script reads no private rows and fits nothing; post hoc
re-expressions are labelled as such. Frozen source/config/input/summary
bindings are unchanged.

Revised Results.md to prioritize the practical conventional comparison and
remove its implication that the 73/84 contrast identifies selection optimism.
The two panels differ in support and composition; neither that contrast nor
the roughly 0.00049 candidate gap estimates an optimism bound. Corrected
57/73 frozen-versus-target-only successes versus 73/73 full-versus-20 improvements,
and qualified TSS/prevalence, q information and feature-distortion claims.
Independent methodological review confirmed these distinctions.

Archived the original Results.md as Results-20260926.md, preserving the SHA256
recorded at acceptance. The completion review's original-document pointer now
resolves to that archive; the exact native acceptance and summary are unchanged.
OuterPreopening-20260927.md is a discussion proposal covering frozen region
roles/panels, equal-region aggregation, expectations, descriptive sign rules,
X20 denominators, and outstanding retained-full refit and failure-handling
requirements. No outer opening or refit was authorized or performed.

Posted response 575 to Fable in thread 32, including the verified distinctions,
answers about private per-seed leaves and frozen outer panels, and the draft
for critique. Fable responds next; task retrieval cursor stays 573. Barry
retains the outer-opening decision. Closing chat replies now carry a Hobart
date-time stamp at his request.

## 29 September 2026 — opening authorized; concrete preparation and broader question

Barry explicitly authorized opening the frozen bird outer test and asked both
models whether alternative architectures or data/signal limits explain the
small conventional margin. Read current project state and Correspondence
thread 32; no new Fable reply followed Astra message 575. The user-supplied
summary repeats the earlier critique. Posted Barry's decision as message 776,
then the concrete proposals as message 778. Retrieval cursor is now 778;
Fable responds next. Opening authority is settled, not pending reconfirmation.

Read-only code/metadata reconnaissance identified all 628 neural target/arm
epochs and thresholds and the 250 relevant accepted pretraining receipts.
Proposed within-block pooled-25 pretraining medians are 3/3/3/2/3/2/3/3/3/3.
The selected conventional family inventory is 51 random forests, 66 histogram
gradient boosters and 40 shallow ANNs. Goal051 discarded individual ANN
stopping epochs after recording their range. The preparation note therefore
proposes retained-only replay of the already-selected ordinary/q procedures,
checking accepted seed-averaged predictions before deriving the missing budgets.
No median is inferred from a range.

`OuterPreparation-20260929.md` records the refit, prediction-before-response
and prospective reporting proposals. A separate outer implementation and
qualified runtime remain necessary. `ArchitectureOrData-20260929.md` grounds
the broader discussion in the actual predictor representation, response
semantics and primary literature. It proposes controlled same-input learner,
habitat-context and observation-information tests in a future experiment.
An independent methodological read found no blocker to posting these as
proposals; it does not constitute acceptance for launch or outer evidence.

The accepted summary SHA256 remains ec0bc6c2…a3d3, and native acceptance remains
`goal052_complete_valid`. No fits or outer outcomes were opened during this
preparation; the scientific source/configuration and accepted outputs are
unchanged. Recurring polling remains deleted.

The metadata inventory script completed with exact accepted input hashes,
matching conventional/neural target identities, the frozen 73/88/122/134 panel
memberships, all 628 stored neural median checks and 250 unique pretraining
receipt keys. It records 80 unavailable ANN target/condition budgets and 4,242
prospective production fits. A repeat run produced byte-identical JSON; the
artifact binds its generator hash. These checks qualify the inventory only,
not the proposed refits or a runtime. `git diff --check` passed.

## 1 October 2026 — recorded-richness review and outer preparation

Read Fable's message 783 after Barry forwarded its summary. Reproduced the
retained inner predictions with `scripts/goal052_effort_review.py`, processing
one target at a time and checking hashes and cell/fold/response alignment.
All five arm AUCs (four neural plus the selected conventional) match exactly
on every target. Fixed FT/conventional averaging gives +0.00241387 AUC over
FT on the primary 73 and +0.00182883 on the other 84. The common 59-target
primary richness table and the 55-target high-richness restriction reproduce.
The other common richness panel has 83, not 84, targets. A background-weighted
identity includes every primary target and recovers +0.00338986, with maximum
target-level error below 2.2e-16. The reporting-rate gradient reproduces closely
under an explicit pooled-quintile definition, but its 157 versus Fable's 151
denominator remains a documented support-rule question.

The predictor covariance helper independently reproduces 5 PCs for 90% and
9 for 99% variance, with participation ratio 3.3913. The review distinguishes
linear collinearity from supervised complexity, recorded richness from effort,
and ensemble complementarity from a bound on learner improvement. Both
scripts' final source hashes match their generated evidence. Parent checks
verified retained cell/membership hashes against the accepted Goal050 manifest
and exercised sparse/empty-bin arithmetic and both-class restriction on a
synthetic example. No model was fitted by these diagnostic scripts.

`RecordedRichnessReview-20261001.md` records the revised research priority:
observation-aware evaluation, then richer inputs, then a same-input learner
test if still warranted. Primary literature supports the caveats about bias
covariates and nondetections. Correspondence reply **805** gives reproduced
numbers and preserves the remaining inferential disagreement; Fable responds
next on those objections and the 151-target definition.

`OuterDiagnostics-20261001.md` fixes supplementary reporting before opening.
The new pure scoring module implements the fixed ensemble, richness bins,
20-per-class rule, explicit NAs and exact weighted AUC identity. The separate
response-free reader checks a pinned manifest and reads only the region ledger
and predictor substrate. Review corrected two representation assumptions:
transform JSON key order is not feature order, and the predictor `region` field
is the coarse `southeast_mainland` source domain, while the ledger carries
official IBRA codes. The real reader returns all 144,860 cells with 103 finite
encoded features. Completeness is not a Goal049 row filter, so the earlier
predictor-complete-only proposal was corrected without changing scoring masks.
The 21 targeted recovery/reader/scoring tests and compilation checks pass.

The ANN helper and eight tests were committed/pushed as **ff14c26**. The first
Deep probe used one worker and a one-hour cap; it finished 25 selected ordinary
discovery/replay pairs for `Chalcites minutillus`, then failed bitwise prediction
agreement. All five folds differ slightly, maximum `5.6624412547723324e-8`.
Exit 1 at 23:33:34 AEST followed 560.6 seconds; q was never attempted and no
epoch budget was accepted. Failed fit records and per-seed predictions are
hash-verified locally, with tracked `ann-recovery-deep-probe-20261001.json`.
No exactness tolerance was weakened.

The accepted conventional endpoints originated on Nectar. Its preserved
environment matches current numerical package versions; the CPU differs from
Deep. Simple no-fit exp/sigmoid/GELU hashes match, so the cause is unresolved.
Resized idle Nectar from c3.xsmall to **c3.large (8 vCPU/16 GiB)** under standing
compute authority; OpenStack ACTIVE and guest capacity passed. All eight helper
tests passed there. A one-worker original-runtime probe started at **23:44:18
AEST**, ordinary then q_full, capped at **2 October 00:44 AEST** plus 60 seconds.
Use the existing `dsdm-ann-recovery-probe-nectar` session and private
`ann-epoch-recovery/nectar-probe-20261001/` receipts. The control-plane current
status and dated exchange log record allocation and return-to-park review.

The accepted inner source/config and summary bindings are unchanged. Outer
response rows remain sealed; reading response-free predictor rows does not
complete model predictions or qualify the full outer pipeline. Remaining work
includes successful recovery of all 80 ANN budgets and retained-full execution,
prediction closure, synthetic separation and runtime qualification.


## 2 October 2026 — original-runtime replay passed; remaining ANN budgets launched

The Nectar probe exited 0 at 23:57:07 AEST on 1 October after 768.74 seconds.
Both ordinary and q_full reproduce the accepted 69,235 probabilities exactly.
Independent reconstruction from returned per-seed arrays checked all 25 unique
fold/seed records per procedure (100 physical discovery/replay fits total).
The derived epoch budgets are 5 and 6; the 2.292 GiB peak worker RSS informed
the subsequent four-worker allocation. Preserve Deep's failed attempt. The
specific numerical cause of the cross-host difference remains unresolved.

The bounded batch passed an original-runtime no-fit preflight with exactly
80 planned procedures and two bound native successes. Synthetic checks exercise
the production scheduler and completion paths, task failure, duplicate rejection,
memory-floor abort, ownership, stale/contradictory receipts, incomplete success,
return hashes and containment, and idle-check failure. Parent review repaired
receipt naming/run IDs and retained memory monitoring while draining failed
work. The exact replay helper and all fitting/config sources remain unchanged.

Launched the other 78 procedures at **00:15:29 AEST**, four spawned workers
with one numerical thread each on Nectar c3.large. Wall cap **06:15:29 AEST**
plus 60-second termination allowance; available-memory floor 2 GiB. The early
snapshot confirmed four live workers, four submitted procedures, no completed
new procedure or failure, and 9,520,799,744 bytes available RAM. It is dispatch
evidence, not completed recovery. The tracked dispatch receipt binds every
private driver and static launch receipt.

The detached Mac mini controller (PID 17558, run
`1f498e0dbbdd47c4b64692ecae5b7abb`) will return and hash-check evidence, then park
Nectar only after its process group has stopped and two workload/container
checks are empty. It treats fitting outcome separately from resource closeout,
bounds resize execution, and never retries or resets the job. Any contradiction
requires inspection. No recurring monitor was reinstated. Control-plane current
status and its dated exchange log carry the allocation and closeout pointers.

Correspondence **807** records the runtime result and dispatch; Fable responds
next to **805**'s scientific objections and denominator question. The outer
pipeline remains unqualified and outer responses remain sealed.

## 2 October 2026, morning — ANN recovery independently accepted and Nectar parked

The bounded batch exited 0 at **03:37:36 AEST**, with 78 new procedures plus
the two probe successes, no failed procedures and zero outer-response rows.
The controller verified all 264 returned-file hashes at 03:39:23, confirmed
its process group stopped and passed two empty workload/container checks.
It recorded **ACTIVE / c3.xsmall at 03:41:08 AEST**. A read-only live check
around 11:00 reconfirmed the cloud state, 1 vCPU/2 GiB allocation, no batch
workers, preserved conventional checkout `ce63d96`, and five matching static
remote/local receipt hashes. The Nectar control-plane exchange records the
resource closeout. No new allocation or automation was made.

Independent `scripts/goal052_ann_recovery_review.py` accepts all 80 recovered
epoch budgets. It checked 2,000 unique fold/seed receipts representing 4,000
discovery/replay fits, candidate and seed identities, accepted source/config and
input hashes, full cell/response/fold coverage and every epoch range/median.
Reconstructed five-seed means exactly match all 5,555,454 accepted prediction
rows. An in-memory mutation of one seed array was rejected. All 264 returned
files and seven preserved Deep-failure evidence hashes passed. The generator
and tracked evidence hashes are bound and independently checked by the parent.

Original per-seed predictions are unavailable; agreement is exact at the saved
fold-mean granularity. The review resolves mechanical epoch recovery, not the
cause of the cross-host discrepancy or the remaining outer qualification.
No additional fits or sealed data were used by the independent audit.

## 2 October 2026 — Fable 810 reconciliation

The separate retained-only follow-up reproduces Fable's matched-network AUC
table, comparator-family table and ensemble gains. It preserves 59 primary
and 83 other common-support targets. The other panel's 100+ FT-minus-target-only
mean is −0.000580 with 47/83 positive, so the combined reversal must not imply
uniform harm. No ecological/observation mechanism is identified.

The literal universal-200+ reference gives 59 defined reporting ratios.
Recomputing from saved bin counts with the highest nonempty reference reproduces
all revised 151-target medians: 92 targets use 100–199; 65 use 200+ and six of
those have zero focal records. Each excluded reference contains only one or
two selected cells. Changing tie order from endpoint order to cell-ID order
changes no top-decile membership in any of 785 folds. The original review
script/evidence remain unchanged.

Added prospective composition counts/shares and equal-target summaries to the
pure scoring module and `OuterDiagnostics-20261001.md`. Ten focused scoring
tests pass, including sparse/empty-bin behavior and unequal target counts.
Source inspection found no retained fitted target weights for Fable's proposed
identical-grid score comparison; `OuterPreparation-20260929.md` records the
limitation. His interpretive concessions and revised future priorities are
recorded in `RecordedRichnessFollowup-20261002.md`. No new scientific fits,
outer predictions or outer-response access occurred in this follow-up review.

Parent integration corrected the follow-up helper's final panel lookup and
made tie-audit counts derive from the recorded target folds. The final helper
then ran end-to-end successfully, including explicit cross-arm cell/label/richness
alignment and first-review input/source gates. No result changed. Its source
SHA-256 is `f49ea52ac3a11797895934f78df4fcfa2813fa57cdf35f05243e75a5fc1a181c`;
the final evidence SHA-256 is
`742c367ab100886da764853cceeaca1684176259d934794d7ec83c8896e5cad0`.
The parent independently checked final source/input bindings, counts and figures.

Correspondence reply **820** posts the reconciliation and recovery closeout
as a reply to **810**. Task retrieval checkpoint is 820. Fable responds next
on reference-bin wording or a material objection; no new Barry decision or
authorization gate is introduced.
