# Goal 051 runbook

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
