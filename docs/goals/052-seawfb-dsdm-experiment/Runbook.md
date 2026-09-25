# Goal 052 runbook

Goal051 was accepted on 12 September and Barry authorized autonomous
continuation. The frozen experiment is implemented. Its scientific config
retains the historical protocol-only fields; the dated Decision records the
execution authority. Production remains gated by a matching host canary and
an uncapped one-epoch profile.

```sh
uv run --locked pytest -q tests/test_goal052_*.py
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm validate-inputs --root .
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm canary --root . --device cpu --workers 2
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm profile --root . --device cpu
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm status --root .
```

The engineering canary constructs the complete largest full-auxiliary case
(block 8/fold 2; 168 heads), retains all its host arrays, and caps optimization
at 128 observations per head per role and 4,096 target observations per role.
It exercises the largest architecture, all four arms, deterministic replay,
paired heads, two repeated jobs per spawned worker, and persistent stores.
It writes digests, loss diagnostics and memory/runtime receipts, with no
held-fold ecological metrics or promotable production leaves.

The separate profile uses every row of the same discovery/stopping/replay
roles for one epoch, plus all four full-target arms. It measures actual
full-row throughput and peak memory; it does not select epochs, architectures
or scientific options. Both receipts must match the current source, accepted
Goal051 identity, host and backend. Bounded canary timings alone cannot justify
production runtime or a larger worker count.

After the profile supports a feasible route, run inside the detached session
`dsdm-goal052-dsdm` using `scripts/goal052_launch.sh /absolute/repository/path`.
Set `GOAL052_WORKERS` and `GOAL052_DEVICE` to the qualified route. The launcher
uses unique timestamped logs and exit receipts; the runner holds a kernel lock
so a crash does not require deleting a stale lock file. Restarting the same
command reuses complete, hash-verified leaves.

The runner completes 200 architecture-screen pretraining tasks and 1,460
screen target tasks, selects the frozen shared architecture, then completes
700 additional pretraining tasks and 41,250 final target tasks. The 365 winning
screen leaves are reused, yielding 42,345 unique target lifecycles. Target-only
leaves are shared across auxiliary sizes. Predictions stay in private Parquet
leaves keyed by target/endpoint/arm/seed/fold and source identity.

After all leaves exist, aggregation averages all five paired seeds before
OOF evaluation. Independent output validation reconstructs all 150 auxiliary
row contracts, checks every pretraining variant, canonical target rows,
initialization/replay/freeze bindings, architecture selection, and final
metrics. An atomic completion marker is written only after that replay passes.
For explicit replay:

```sh
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm aggregate --root .
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm validate --root .
```

NCP, SEH and NNC outcomes remain sealed. No full refit, mapping, manuscript
claim or scientific amendment belongs in this execution.


An hourly thread follow-up (`continue-dsdm-goal052`) continues qualification
and prepares the production route after the full profile returns. It pauses
once the route is resolved or a material resource/scientific decision is
needed. The completed Goal051 follow-up remains paused.

CPU fits use explicit AdamW `foreach=True`, qualified against `foreach=False`
with within-host bitwise agreement through stopping and replay on Mac and
Linux. See `evidence/seawfb_dsdm/goal052/optimizer-equivalence.json`. Fused AdamW
is deferred because it changed deep-server numerics. Qualification receipts
from implementation `61a80c9` are historical and cannot qualify the new source.

Both current-source qualification receipts passed by 16:18 AEST on
12 September. The full profile exited zero. The approved bounded pilot is
described in `ComputeRoute.md` and launched through `scripts/goal052_pilot.sh`.

Barry approved the pilot and four-hour check cadence. The pilot launched at
16:28 AEST on 12 September in `dsdm-goal052-pilot`; it stops at approximately
16:28 AEST on 13 September, with 60 seconds allowed for forced termination.
The existing follow-up is active at four-hour intervals. Do not restart the
24-hour clock during recovery or extend the cap without further authorization.

The pilot has now stopped at the 13 September 16:28 AEST cap (exit 124),
with no live pilot workers. Two completed pretraining checkpoints are verified
and retained. Four-hour checks are paused. Start from `PilotReview.md` for
the closeout and next resource proposal; do not restart the old pilot wrapper.


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


## 15 September 2026 — monitoring cadence superseded

Barry changed monitoring to once every 24 hours. `continue-dsdm-goal052` now
runs daily at 17:20 Australia/Hobart, starting with today's allocation-closeout
review. Earlier four-hour instructions are historical. The original pilot
still stops at 17:10 AEST today. At closeout, review and qualify higher CPU
concurrency (initial target 24 workers if capacity permits), then launch the
next justified bounded allocation under standing authority. Keep checks
proportionate and retain the daily cadence when updating the actual route.


## Active route — 15 September 2026

Follow `dsdm-goal052-continue24` on deep-server, runner PID 45460, timeout
PID 45451. `scripts/goal052_continue24.sh` launched a 168-hour/24-worker CPU
allocation at 17:29:30 AEST on 15 September, after the old run stopped and
fresh qualification passed. Cap: 22 September 17:29:30 AEST plus 60 seconds.
Use private `continuation24-launch.json` and tracked
`continuation24-launch-review.json` for exact log/exit paths and bindings.
The old eight-worker wrapper and original launch receipt are historical.
Twenty-six verified checkpoints were reused; no target leaves existed at launch.

The daily heartbeat now runs at 17:40 Australia/Hobart, following the cap on
its final day. The qualification review is `twentyfour-worker-review.json`;
all 48 canary jobs matched the previous qualification exactly. Fitting source
and scientific design remain unchanged. After cap/early exit, verify shutdown
and completed evidence before choosing the next allocation under standing
authority. Do not launch a duplicate or reset the current deadline.

## Superseding route — 25 September 2026

Deep-server and all 48 Kunanyi target fitting jobs are stopped. All target jobs
exited 0; their host/ownership/rank reviews passed. Follow current HANDOVER and
Kunanyi.md for the post-fit validation **812148**, one CPU / 16 GiB / four hours,
under `/u/bwbrook/codex_kunanyi/dsdm-goal052/validation-20260925-v2`.
The first validation wrapper 812145 failed at import and is preserved separately.

Barry replaced recurring checks with PBS email. Wait for his resumption, inspect
the existing validation job and retrieve `validation-return.tar.gz` if complete.
Require complete leaf validation and unchanged native acceptance before treating
Goal052 as complete. Verify all returned archive/file hashes before local import.
Do not recreate an automation, restart fitting or resubmit the validator blindly.
