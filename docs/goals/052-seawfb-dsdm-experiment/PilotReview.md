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

## Proposed next resource decision

Recommend a native eight-worker metric-free canary on deep-server, capped
at **30 minutes (at most four worker-hours), plus a 60-second termination
allowance**. Do not repeat the expensive two-worker pilot. This is a separate
resource request beyond the exhausted pilot cap; it has not been launched.
An independent methodological review supports this next tranche.

Eight single-thread workers would use one quarter of the host's 32 physical
cores. The prior canary peak suggests roughly 22 GiB worker RSS in aggregate,
plus parent/store overhead; this is a sizing estimate, not eight-worker
qualification. Check live capacity again before launch. Preserve the current
two-worker canary in the existing qualification-history directory before the
native command writes its new receipt. Use the exact current source, lock,
inputs and CPU backend. No GPU/driver/cloud change is proposed.

Prepared command (run in a distinct detached session after authorization;
capture its log and exit code separately from the completed pilot):

```sh
cd /data/codex/repos/dSDM
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
timeout --signal=TERM --kill-after=60s 30m \
  ~/.local/bin/uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm \
  canary --root . --device cpu --workers 8
```

Success requires all eight worker PIDs exercised, repeated prediction/trunk
digests agreeing, finite state and transfer/freeze invariants passing, and
observed memory fitting the host. Record aggregate process memory and load
as well as per-worker peaks. Canary timing is bounded engineering evidence,
not full-row parallel throughput. The existing full-row one-worker profile
remains useful if source and runtime identities match. After the canary,
prepare a separately capped eight-worker production proposal using the new
measurements; do not automatically launch or extrapolate a campaign ETA.
