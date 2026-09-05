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
attempt, the accepted attempt, and the finite parameter digest. Host summaries
must reproduce both q prediction and q parameter digests exactly.
