# Goal052 pilot closeout — 13 September 2026

The approved 24-hour, two-worker pilot stopped at its cap. The pilot exit
marker is 124, modified at 16:28:12.507 AEST on 13 September, approximately
24 hours after launch. The 16:34 check found no session or process in the
pilot group. The source and qualification identities remain unchanged.
The four-hour follow-up is paused. No production extension has been launched.

## Verified output

| Full auxiliary pretraining, block 0 / fold 0 / seed00 | Discovery epochs | Selected / replay epochs | Lifecycle hours |
| --- | ---: | ---: | ---: |
| bridge_wide | 33 | 3 | 11.97 |
| bridge_control | 34 | 4 | 15.44 |

Both checkpoints are reusable and preserved locally and on deep-server.
Their payload and receipt hashes, loaded finite model state, source/accepted
baseline identity, seed/budget/reset/replay invariants, stopping histories and
data contracts passed verification. Final transfer hashes and native reloads
agreed after shutdown. Receipts are in `evidence/seawfb_dsdm/goal052/`:
`pilot-review.json`, `pilot-closeout-manifest.json` and `pilot-checkpoints/`.
Private final logs and model payloads are under the Goal052 `pilot-final/`.

Only 2/200 screen-pretraining tasks completed (2/900 campaign pretraining
lifecycles). No target leaves, architecture selection or ecological metrics
exist. The two deeper-architecture fits were interrupted at the deadline;
there is no resumable within-fit state. Their next attempts must start fresh.
The 27.42 hours summed over completed lifecycles are wall-worker time, not
exact CPU accounting for the 48-worker-hour cap. Other time includes the
interrupted fits and setup. No completion fraction based on those hours is
claimed. The shutdown log reported resource-tracker semaphore cleanup; the
post-stop check found no live pilot process or `sem.mp-*` files.

## What this establishes

The frozen stopping/replay and checkpoint path works for two full-data fits.
Memory remained modest (about 2.0–2.1 GiB per worker); throughput is the
constraint. Selected epochs 3 and 4 apply only to these two fits and cannot
justify reducing the frozen epoch budget or patience. This is one block/fold,
one auxiliary size and one seed, with no completed deeper architecture.
Neither scientific performance nor a reliable full-campaign ETA follows.

Other server work occupied roughly 48 logical CPUs initially, then the load
fell to approximately 2 while our workers continued. At closeout the host was
idle with about 122 GiB available memory. The changing load, architecture,
head count, discovery/stopping/replay costs and selected epochs prevent a
simple extrapolation from the two completed fits or the one-epoch profile.

## Eight-worker qualification authorized

Barry approved the separate 30-minute check on 13 September: at most four
worker-hours, plus a 60-second termination allowance. The original deadline
is 17:22:03 AEST. The public CLI rejected eight workers before fitting because
its canary entry point caps concurrency at two. Its failed log is preserved.

The separate `scripts/goal052_canary8.py` driver invokes the same frozen canary
worker with 16 jobs across eight spawned processes. It reuses the hash-bound,
score-free largest case from the prior two-worker receipt, preserves fitting
source identity, and records its own SHA-256 in the new receipt. The prior
receipt is archived under private `qualification-history/e309ca8-two-worker/`.
The driver started at 16:57:40 AEST in `dsdm-goal052-canary8` with only the
remaining 1,462 seconds to the original deadline. The supervisor, failed CLI
attempt, launch receipt and resource samples are under private
`qualification-eight-workers/`. No production extension is authorized.

Success requires all eight worker PIDs exercised, repeated prediction/trunk
digests agreeing, finite state and transfer/freeze invariants passing, and
observed memory fitting the host. Aggregate process RSS samples can double
count shared pages. Canary timing is bounded engineering evidence, not
full-row parallel throughput. The existing full-row one-worker profile remains
useful if source and runtime identities match. After the check, prepare a
separately capped production proposal; do not automatically launch or
extrapolate a campaign ETA.

## Eight-worker result — 13 September 2026, 16:59 AEST

The check passed in 117.22 seconds, exit 0, before the original deadline.
All eight concurrent worker PIDs completed two jobs each. Every prediction,
trunk digest, data contract and fit receipt field other than runtime matches
the prior two-worker canary. Finite state/loss, paired heads, reset/replay,
transfer and frozen-trunk invariants passed. Returned hashes bind the driver,
new canary, prior profile, logs and unchanged production checkpoints.
No qualification processes or semaphore files remain.

Maximum recorded worker RSS was **2.555 GiB**; the maximum ten-second sample
of summed process RSS was **18.324 GiB**, including the parent (shared pages
may be counted more than once). The post-run host has about 122 GiB available
and no swap use. This qualifies eight-worker execution for unchanged fitting
source `e309ca8`; full-row throughput at eight workers remains unmeasured.
Compact evidence is `evidence/seawfb_dsdm/goal052/eight-worker-review.json`
and `eight-worker-manifest.json`. No ecological metrics or outer responses
were accessed, and the two production checkpoints remain unchanged.

## Prepared next production decision

Recommend a **48-hour, eight-worker CPU continuation** on deep-server, capped
at **384 worker-hours plus 60 seconds for termination**, with the requested
four-hour checks. This longer window gives the deeper architectures more time
to complete than the first 24-hour pilot, while measuring actual concurrent
full-data cost. It does not guarantee their completion or supply a campaign
ETA. The frozen scheduler reuses the two verified checkpoints and restarts
interrupted fits from scratch. Unfinished fits at the new cap would again lose
their within-fit progress. No epoch, patience, optimizer or scientific change
is proposed.

`scripts/goal052_pilot8.sh` is prepared and passes shell syntax validation.
Its preflight binds the verified canary and separate driver's hash; the native
runner then checks current fitting identity, accepted inputs and host profile.
After authorization, recheck live host capacity, stage the wrapper, record its
hash and dispatch time/deadline, and launch it in `dsdm-goal052-pilot8`. Resume
the existing four-hour follow-up for that exact launch, then pause and review
at the cap. **This continuation has not launched and requires Barry's resource
decision.** No cloud allocation or driver change is needed.
