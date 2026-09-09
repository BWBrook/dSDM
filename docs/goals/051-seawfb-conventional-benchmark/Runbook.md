# Goal 051 runbook

## Current: approved amendment 3, protocol v4

Barry approved the bounded recovery on 8 September. It launched on Nectar at
23:19:09 AEST from `ce63d96`, after 84 tests passed on each host and input/host
validation passed. The initial stress process was verified active. The active private root
is now `data/processed/dsdm/goal051-seawfb-conventional-benchmark-v4` on Nectar.
All earlier roots, q checkpoints and route files below are historical and
must remain untouched. The initial launcher requires fresh production q and
endpoint directories. It runs block1/fold0/full in isolated stress storage,
then two serial and 16 mixed metric-free probes, selects
`metadata/goal051_nectar_route_v4.json`, verifies its live-host gate, and starts
fresh q production. Target `run` first requires all 150 valid q surfaces.

At 02:20 AEST on 9 September, stress convergence was independently verified
at 10,478 iterations on the tertiary attempt. The first serial canary is
complete and the second is active; no v4 production q surface exists yet.

At 05:20 AEST, all 18 canaries and the v4 route are independently validated;
production began automatically at 03:49:44 AEST. All 20 returned canary/summary/
route files passed transfer-hash verification. By 11:21 AEST, all 150 q surfaces
were independently verified after returning all 300 model/receipt files with
hash checks. Target fitting began at 09:18:48 AEST on 9 September. At
05:23 AEST on 10 September, 197/303 endpoint checkpoints pass identity/hash
checks, with all five families available in the completed endpoints.
Full metric and coverage acceptance is
still pending. The existing 16 workers remain active; no restart is needed.

```sh
# On Nectar, after source/input/test validation and checking no duplicate job:
tmux new-session -d -s dsdm-goal051-nectar \
  'cd /data/codex/repos/dSDM && bash scripts/goal051_nectar_launch.sh .'
tail -n 25 data/processed/dsdm/goal051-seawfb-conventional-benchmark-v4/nectar-execution.log
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional status --root .
```

The stress model is never promoted into production. Every failed q fit writes
`q_linear/blockNN_foldNN_auxSIZE.failure.json` with its identity, specification
and all available attempt diagnostics before returning the worker exception.
Successful receipts include finite-parameter flags for every attempt. A failure
at the final 20,000 ceiling stops before ecological scoring; no further ceiling
increase, tolerance change or solver substitution is authorized.

If interrupted, inspect both `nectar-execution.exit` and `run.exit` under the
v4 root and preserve the logs. Reuse only validated v4 evidence. After the
v4 canary gate passed, resume production with the gate/restart command in the
Nectar section below. The three-hour follow-up remains active and can continue
through this approved recovery without another permission request.

## Historical execution record (protocol v3)

From the repository root, use the locked environment and the Goal 051 runner
once implementation is present:

```sh
uv run --locked pytest -q tests/test_goal051_seawfb_modeling.py tests/test_goal051_seawfb_replay.py -m 'not real_scope'
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional plan --root .
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional canary-batch --root . --host-key mac
# On deep-server, from its Goal 051 checkout:
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional canary-batch --root . --host-key deep_server
# After both private host summaries are present in this checkout:
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional canary-route --root . --selected-host "$HOST_KEY" --workers "$WORKERS"
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional q --root . --workers "$WORKERS"
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional run --root . --workers "$WORKERS"
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional aggregate --root .
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional validate --root . --complete
```

`canary-batch` enforces the exact hostname/system pair, runs the two serial
receipts sequentially, runs all mixed receipts concurrently at Mac-3 or
deep-server-8, and writes the private host summary only after interval overlap
proves the requested concurrency. Bring both private `summary-mac.json` and
`summary-deep_server.json` files into the same checkout before `canary-route`.
The route command binds both summaries and refuses a worker count above the
selected host's proven concurrency.

The planned production session is `dsdm-goal051-conventional`. After the
canary route decision, launch the full resumable grid with:

```sh
tmux new-session -d -s dsdm-goal051-conventional \
  "GOAL051_WORKERS=$WORKERS bash scripts/goal051_launch.sh ."
```

The launcher sets an explicit tool path for detached sessions: Mac uses
`/opt/homebrew/bin` and deep-server uses `/home/bwbrook/.local/bin` (with
standard system paths). It validates the repository root and run-directory
creation before launching. Existing `run.log` and `run.exit` files are moved
to timestamped `.previous-*` files before a restart.

Inspect it without attaching:

```sh
tmux capture-pane -pt dsdm-goal051-conventional -S -40
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional status --root .
cat data/processed/dsdm/goal051-seawfb-conventional-benchmark/run.exit
```

The canary must bracket q20 and q`full`, include a q-augmented histogram
boosting fit, run two serial repeats and mixed Mac-3/deep-server-8
concurrency, and suppress ecological metrics and outer access. An exit marker
is necessary but not sufficient: run the independent validator before
acceptance. Do not open NCP, SEH, or NNC response/outcome data.

Each q receipt records the primary and, when needed, extended numerical
attempt, typed warning diagnostics, the accepted attempt, the finite parameter
digest, and the exact solver representation (`k`, canonical `C`, solver `C`,
and representation label). Host summaries must reproduce both q prediction and
q parameter digests exactly.

## Detached Canary Handoff

Fresh protocol-v3 canaries were launched on **2026-09-06 at 00:17–00:18 AEST**
from `ab7e369` on both hosts, following the code cleanup and explicit `spawn`
repair. Both initial CPU processes were verified active. The Linux portable
gate passed 54 tests; both hosts passed the frozen-input plan with identical
identity fields. Production remains unlaunched.

The prior Mac success and deep-server autograd/fork failure were preserved in
`canary.previous-20260905T141741Z` (Mac) and
`canary.previous-20260905T141805Z` (deep-server), beside the new `canary`
directory. Each new `canary/launch.sh` records its exact command, source commit,
one-thread environment, and log/exit handling. The following paths now refer
to the replacement runs:

**Wake-up at 13:04 AEST, 6 September:** Mac completed and its five-receipt
summary reproduced exactly. Deep-server rebooted at 03:31, leaving one valid
serial receipt and no exit marker. The interrupted directory is preserved as
`canary.interrupted-20260906T030509Z`. A fresh server batch started at 13:05:09
AEST in the same session and paths below, from unchanged source. Mac does not
need another run. Production still awaits the complete two-host route gate.

```sh
set +e
tmux has-session -t dsdm-goal051-canary-mac
printf 'mac_tmux_rc=%s\n' "$?"
tail -n 40 /Users/bwbrook/papers/dSDM/data/processed/dsdm/goal051-seawfb-conventional-benchmark/canary/batch-v3-mac.log
printf 'mac_exit_marker='; cat /Users/bwbrook/papers/dSDM/data/processed/dsdm/goal051-seawfb-conventional-benchmark/canary/batch-v3-mac.exit
```

```sh
set +e
ssh deep-server-ts 'tmux has-session -t dsdm-goal051-canary'
printf 'deep_tmux_rc=%s\n' "$?"
ssh deep-server-ts 'tail -n 40 /data/codex/repos/dSDM/data/processed/dsdm/goal051-seawfb-conventional-benchmark/canary/batch-v3.log'
printf 'deep_exit_marker='; ssh deep-server-ts 'cat /data/codex/repos/dSDM/data/processed/dsdm/goal051-seawfb-conventional-benchmark/canary/batch-v3.exit'
```

An exit marker of `0` is necessary but not sufficient for acceptance.

## Production Handoff — 8 September

**Superseded later on 8 September by the Nectar offload below.** The Mac run
was deliberately stopped after 13 complete q surfaces; exit 143 records that
operator stop.

Both host canaries are now independently validated. Deep-server finished at
19:06 AEST on 6 September with exit 0 and all ten receipts. All eleven server
JSON files were copied privately to Mac and verified against remote SHA-256;
both host summaries reproduced exactly from their receipts.

`metadata/goal051_canary.json` selects **Mac mini with three workers**. Measured
mixed throughput was 5.82 probes/hour on Mac versus 3.81 at server concurrency
eight; the server run experienced background contention. These are canary
timings, not a production ETA or a hardware ranking.

The production session launched at **09:22:38 AEST on 8 September**:

```sh
tmux capture-pane -pt dsdm-goal051-conventional -S -40
tail -n 40 data/processed/dsdm/goal051-seawfb-conventional-benchmark/run.log
uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional status --root .
cat data/processed/dsdm/goal051-seawfb-conventional-benchmark/run.exit
```

Run these locally in `/Users/bwbrook/papers/dSDM`. The q stage precedes the
303 target endpoints. Preserve source identity while the job runs. If it is
interrupted, inspect the failure and checkpoint validity before restarting
the same launcher with `GOAL051_WORKERS=3`; do not launch a duplicate session.
Complete benchmark evidence still requires scientific acceptance before any
Goal052 execution.

## Nectar Offload — 8 September

Barry requested the multi-day work run on resized Nectar, leaving the Mac Mini
free. Nectar is `c3.3xlarge` (64 vCPUs, 128 GiB allocated RAM); use
`nectar-codex-ts`, user `codex`, checkout `/data/codex/repos/dSDM`. The existing
13 Mac q checkpoints were transferred and validated without changing their
identity. All four retained-training input files matched their Mac hashes.
Outer response tables were not staged.

The separate `goal051_nectar_execution` module binds its own source/config
hashes, the original scientific identity and the prior two-host route receipt.
Its hardware gate checks Linux `deep-vm`, DMI UUID
`2c0b08ec-1f02-4864-90a9-8d0fd1816d2e`, at least 64 CPUs and 120 GiB visible
RAM. Cloud-init's `nocloud` instance ID is unsuitable for this restored VM.
The original production source and Goal051/052 scientific configs are unchanged.

The initial detached chain launched at **10:51:23 AEST on 8 September** from
`5404fc6`; its first serial canary was verified active at 99.9% CPU. Do not
duplicate this existing session. The launch command was:

```sh
cd /data/codex/repos/dSDM
tmux new-session -d -s dsdm-goal051-nectar \
  'bash scripts/goal051_nectar_launch.sh /data/codex/repos/dSDM'
```

**14:15 AEST update:** the canary passed and production began at 14:03:04 AEST.
All 18 receipts, summary and route were returned with SHA-256 verification;
the summary and route reproduced exactly with independent checks. The
16-worker q stage was active at 20/150 complete. The current route is
`metadata/goal051_nectar_route.json`; the old Mac route remains historical.

**20:17 AEST update:** the q pool stopped at 18:49:53 with exit 1 after an
extended-attempt convergence failure. There are 143 validated q surfaces and
seven missing full-auxiliary surfaces; no target endpoints started. All 290
model/receipt/log/exit files were returned with verified hashes to
`nectar-return-20260908T1017Z` under the local Goal051 private root, preserving
the earlier Mac logs. No job is active. Do not use the routine restart below
for this deterministic numerical failure: a versioned amendment needs Barry's
approval before another fit beyond the existing policy.
See `Numerical-amendment-3-proposal.md` for the bounded recovery awaiting
authorization. Keep scheduled checks quiet while this blocker is unchanged.

The wrapper sets data-volume uv caches and one-thread estimator limits. It
runs two serial probes followed by 16 concurrent probes; raw evidence must
validate before `metadata/goal051_nectar_route.json` is written and the
live-host gate permits production. Production then resumes q checkpoints and
runs target endpoints, aggregation and complete validation. A failed canary
or gate stops the chain. No new ecological selection occurs in this routing
step. The three-hour follow-up is described below.

Inspect remotely:

```sh
ssh nectar-codex-ts 'tmux capture-pane -pt dsdm-goal051-nectar -S -30'
ssh nectar-codex-ts 'tail -n 25 /data/codex/repos/dSDM/data/processed/dsdm/goal051-seawfb-conventional-benchmark/nectar-execution.log'
ssh nectar-codex-ts 'cat /data/codex/repos/dSDM/data/processed/dsdm/goal051-seawfb-conventional-benchmark/nectar-execution.exit'
ssh nectar-codex-ts 'cd /data/codex/repos/dSDM && UV_CACHE_DIR=/data/codex/cache/uv uv run --locked python -m dsdm_phase1.goal051_seawfb_conventional status --root .'
```

The initial wrapper refuses to overwrite prior execution logs. If production
is interrupted after the canary passed, inspect the failure and resume from
the existing evidence on Nectar with:

```sh
export UV_CACHE_DIR=/data/codex/cache/uv
export UV_PYTHON_INSTALL_DIR=/data/codex/cache/uv-python
uv run --locked python -m dsdm_phase1.goal051_nectar_execution gate --root . --workers 16 &&
  GOAL051_WORKERS=16 bash scripts/goal051_launch.sh .
```

Run that restart in a detached session after checking no duplicate exists.
If the canary itself was interrupted, preserve its directory and execution
logs before restarting a fresh complete canary batch. Do not splice partial
timing batches or rebind old evidence. Source moves through Git bundles from
the canonical Mac; inputs/results use Tailscale rsync with SHA-256 verification.
Return useful results to the Mac and preserve remote evidence through project
acceptance; park Nectar when the campaign no longer needs compute.

### Three-hour Follow-up

After the Nectar launch, Barry explicitly requested a recurring wake-up every
three hours. The active app follow-up is `check-dsdm-nectar-progress`, attached
to this thread. This supersedes the earlier monitoring pause. It checks the
existing chain, resumes valid work after routine interruptions, retrieves and
independently validates completed evidence, and progresses Goal051 through
acceptance. Pause it after Goal051 is accepted; Goal052 and outer evaluation
retain their separate authorization boundaries.
