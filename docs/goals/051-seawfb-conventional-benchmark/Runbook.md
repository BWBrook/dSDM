# Goal 051 runbook

From the repository root, use the locked environment and the Goal 051 runner
once implementation is present:

```sh
uv run --locked pytest -q tests/test_goal051_seawfb_modeling.py tests/test_goal051_seawfb_replay.py
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

The corrected protocol-v3 canaries run detached under the existing approval.
Use these exact status checks when waking the work:

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

An exit marker of `0` is necessary but not sufficient for acceptance. Resume
only after both host summaries are complete and independently valid; then run
`canary-route` with the selected host and workers before launching the main
benchmark session. The main benchmark has not yet been launched.
