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
