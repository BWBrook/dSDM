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
