# Goal052 kunanyi execution route

Prepared 21 September 2026 after Barry identified the available allocation:
up to 48 PBS nodes, each with 28 CPUs and 128 GB RAM. Standing compute
authority covers this migration. Fitting code, numerical rules and sealed
outer boundaries remain frozen.

## Decision and current status

Use kunanyi for the remaining independent fits, subject to target-runtime
qualification and verified transfer of production ownership. The prior
single-host qualification was useful, but continuing the entire campaign at
24 workers is not the preferred route now that this allocation is explicit.

The 21 September snapshot contains 200 screen-pretraining checkpoints,
1,460 target leaves and 17 of the 700 remaining pretraining checkpoints.
The selected architecture is `seawfb_scale`. More fits may finish on
deep-server before handoff; build the final import manifest only after it
has stopped. Never launch the native whole-campaign `run_all` on several
nodes: it would submit overlapping tasks to atomic but non-exclusive writers.

Barry unlocked the jumpbox. Live access works through `kunanyi-via-deep`
with `KUNANYI_CONNECT_TIMEOUT=45` and `KUNANYI_EXPECT_TIMEOUT=60`;
ten seconds was insufficient for the nested authentication. Renew the existing
five-minute Enable SSH portal window when needed. Non-login SSH commands need
absolute PBS paths such as `/opt/pbs/bin/qstat`.

PBS probe **810868.kunanyi-ohpc** completed with exit 0 on **n078.kunanyi**:
28 physical Xeon E5-2680 v4 cores (2.40 GHz), 125 GiB RAM, CentOS 7,
GLIBC 2.17, and Apptainer 1.3.2. Unprivileged user namespaces are disabled;
container execution then passed in PBS **810869.kunanyi-ohpc** on
**n001.kunanyi**, exit 0 in 22 seconds. The official Ubuntu 24.04 image
provided GLIBC 2.39 inside Apptainer. Both `test` and `normal`
queues currently allow 48-hour walltimes. The locked Torch x86-64 wheel is
manylinux_2_28, so the native GLIBC 2.17 runtime is unsuitable.

The X-ray project's working PBS wrappers confirm the 28-rank node layout,
48-hour production walltime, and `Anaconda3/2024.02-1` analysis module. That
module is not evidence of compatibility with dSDM's frozen environment. Its
storage notes also record a prior scratch-quota failure and successful move
to home. Our scratch upload created a zero-byte file and failed at close;
the same upload succeeded under `/u/bwbrook/codex_kunanyi/dsdm-goal052`.
Use that home root. Filesystem-wide free space does not prove account quota.
No dSDM production jobs have been submitted to PBS.

## Allocation

- Remaining pretraining: at most 25 nodes × 28 workers = 700 slots, reduced
  to match the unfinished inventory and queue policy. Requesting 48 nodes
  for fewer than 700 independent fits would waste slots.
- Final target stage: up to 48 nodes × 28 workers = 1,344 slots, for 41,250
  native submissions, including 365 reusable selected-screen leaves.
  Across screen and final work there are 42,345 unique target leaves.
- One CPU thread per worker. Full-node memory qualification precedes use;
  the existing canary's approximately 2.56 GiB peak worker RSS suggests
  28 workers should fit comfortably, but does not establish kunanyi usage.
- Size the walltime from measured complete-fit runtimes and actual PBS
  limits. Full-auxiliary fits have taken roughly 13–26 hours on deep-server;
  short walltime limits would repeatedly discard unfinished fits.
- A PBS array with one full node per shard needs no MPI communication.
  Use deterministic, disjoint native task IDs and exclusive shard ownership.
  Preserve the stage barrier before final targets and before aggregation.

1,344/24 = 56 is the slot ratio, not a promised speedup. Queue delay,
processor speed, unequal fit duration, the last unfinished fit in a stage,
and serial aggregation/verification limit elapsed-time reduction.

## Access and runtime qualification

Use the established Nectar transport helpers and `kunanyi-via-deep`.
After refreshing the portal login, inspect PBS queue limits, account/node
allowance, filesystem space and allocated-node runtime. Submit
`scripts/kunanyi/goal052_probe.pbs` for the latter; keep heavy work off login
nodes. Do not assume that historical CentOS 7 nodes can load the current
Python 3.12 / PyTorch 2.13 environment. Probe modules/container support and
preserve the locked package versions; no silent dependency downgrade.

Stage only frozen source/configs, retained Goal050 inputs, the accepted
Goal051 summary/review and 150 q models, qualified reference receipts, and
verified Goal052 checkpoints. Do not stage sealed NCP/SEH/NNC response data.
Use checksummed transfer manifests; the current retained inputs plus
checkpoints are well below 1 GB, excluding the Python runtime.

The numerical qualification entrypoint is `scripts/goal052_canary28.py`:

```sh
PYTHONPATH=src /path/to/python scripts/goal052_canary28.py \
  --root /u/bwbrook/codex_kunanyi/dsdm-goal052/QUALIFICATION_ROOT \
  --reference /u/bwbrook/codex_kunanyi/dsdm-goal052/REFERENCE/goal052_canary.json \
  --reference-sha256 ad9d25d1c0baf843a19b2affa4baa74f4e6f103106db06730a7a98cd6fa4af6b \
  --output qualification/canary.json
```

It runs two synchronized waves of 28 unchanged native canary workers and
requires exact agreement of all scientific fields with the established
Linux reference. It records the actual host/runtime and never rebinds the
old reference to a new host. Numerical disagreement is a stop condition;
new tolerances or altered training rules require a scientific decision.

`scripts/kunanyi/goal052_qualify.pbs` adds the native full-row one-epoch
profile. It requires an isolated qualification root marked by a file named
`.goal052-qualification-root` containing `qualification-only`, with no
canonical canary/profile metadata already present. Copy the source/scripts
into that root rather than resolving driver symlinks outside it. The job
writes only that root's qualification metadata; it must not overwrite
production metadata. Capture PBS resource use and inspect all evidence before
creating the reviewed qualification accepted by the production adapter.
The template's normal queue and four-hour walltime fit the observed PBS
limits. Scheduler mail is explicitly disabled.

Qualification is host/runtime specific. Every production host needs matching
qualification evidence, or a separately justified and recorded validation
of equivalence; hostname strings must not simply be edited. Shared input
files may be read-only, but qualification metadata must be isolated per host.

## Ownership transfer and stage completion

Keep deep-server's live 24-worker allocation and original 22 September
17:29:30 AEST deadline unchanged during preparation. At its cap, verify the
exit marker and absence of all recorded workers. Hash and import every
completed payload/receipt pair, including fits completed after the daily
snapshot. Preserve incomplete-fit evidence; those fits restart from their
original seed because there is no within-fit recovery.

Record shutdown, imported checkpoint hashes, the frozen selection, source
identity and reviewed qualification in an immutable launch binding. Only
then release disjoint production shards. A persistent rank claim must reject
duplicate array jobs. Never clear a stale claim based on age alone: first
prove the previous PBS job has stopped, retain its evidence, and record the
explicit recovery. Successful complete fits are reused by native loaders.

Before target dispatch, verify all 900 expected pretraining checkpoints and
issue a source/selection-bound stage receipt. Before any final aggregation,
require the complete unique target inventory, then run the unchanged native
aggregator and validation. No partial-grid ecological comparisons, full
refits, maps, manuscript claims or outer-outcome access are authorized.

Keep the existing daily 17:40 Australia/Hobart heartbeat; update its route
and PBS IDs after actual submission, and notify Barry only for meaningful
stage changes, completion, failure or a decision needing him.

The initial qualification payload is `inputs-20260921.tar.gz` (413,299,581
bytes; SHA256 `8394bc14b741d240dbaf984d9c889f42e14360b04e0de7319b8bbd44ae920bab`).
Its 3,748-file private manifest includes the verified daily snapshot, retained
inputs and frozen source. It is explicitly not the final production handoff.

## Frozen runtime packaging

`scripts/kunanyi/snapshot_runtime.py` copies the exact deep-server interpreter,
standard library, entire venv and loaded system-library closure into a fresh
build context. It does not install packages or alter the live environment.
`scripts/kunanyi/Dockerfile.runtime` uses the observed official Ubuntu digest.
The existing editable source path is bound separately; never mount a whole
repository over the container path containing its venv.

The resulting image is
`sha256:b79688acba36746d9230c7b3bc0bb811829281676743e7e3bb6246fd0c324fe8`.
It imported the scientific runner and passed a basic tensor check. The final
3,149,821,803-byte runtime archive SHA256 is
`e3ed6e9b8090e83749ccd186c92f0b9729efc90460c0277e542af1a9eb1e5f34`.
Direct deep-server → jumpbox → kunanyi transfer took 32 seconds (~94 MB/s).
No credential file was copied between hosts.

`scripts/kunanyi/goal052_build_qualify.pbs` binds runtime, input and driver
archive hashes, converts the Docker archive to SIF on its allocated node,
extracts a fresh qualification-only root, then runs the 28-worker canary and
native full-row profile. Resource samples track the job's descendants. The
four-hour job requests 28 CPUs / 110 GB and explicitly disables PBS mail.
The existing profile took about 80 minutes on deep-server, so job submission
is not evidence of completed numerical qualification.

Numerical qualification job **810907.kunanyi-ohpc** was submitted after all
transferred runtime/driver/wrapper checksums passed. Its output is
`/u/bwbrook/codex_kunanyi/dsdm-goal052/dsdm052_buildqual.o810907`;
its isolated build/root is `build-810907.kunanyi-ohpc`. Inspect completion
and evidence at the next daily check; do not submit a duplicate.

PBS confirms job 810907 running on **n234**, started **18:54:28 AEST** on
21 September, with the requested four-hour walltime and mail disabled.

## 22 September handoff state

Deep-server ended at its original cap (exit 124), with 272 verified pretraining
checkpoints and 1,460 preserved screen leaves. The 55 new checkpoint pairs are
local; all 544 pretraining file hashes match the stopped remote inventory.
The native run lock is available and no worker/semaphore remains. There are
628 unfinished remaining-pretraining fits. The initial kunanyi snapshot still
has only 217 checkpoints and must be updated before production handoff.

Job 810907's result could not be retrieved because the portal requires a fresh
UTAS sign-in. Barry has been asked to sign in and enable SSH. Preserve this
existing job/staging; qualification remains unverified and no PBS production
has launched. Once access returns, inspect the result before choosing the
next bounded allocation. Daily cadence and scientific boundaries are unchanged.
