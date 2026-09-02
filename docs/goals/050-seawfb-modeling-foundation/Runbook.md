# Goal 050 runbook

Run from the dSDM repository with the locked project environment:

```bash
uv run --locked python -m dsdm_phase1.goal050_seawfb_foundation build --root .
uv run --locked python -m dsdm_phase1.goal050_seawfb_foundation validate --root .
uv run --locked python -m dsdm_phase1.goal050_seawfb_foundation validate-tracked --root .
uv run --locked python -m dsdm_phase1.goal050_seawfb_foundation summary --root .
```

Private outputs are under
`data/processed/dsdm/goal050-seawfb-modeling-foundation/`. Tracked receipts
are `metadata/goal050_transforms.json`, `metadata/goal050_manifest.json`,
`metadata/goal050_decision_receipt.json`, and
`evidence/seawfb_modeling_foundation/goal050/foundation_validation.json`.

Do not move private cell or species membership payloads into Git.

Held-block-adjusted richness is an auxiliary-pretraining-only construction.
For target fine-tuning and evaluation, construct the target-specific X10 mask
from full richness; a target-absent row contributes no target presence, and
other species remain valid effort donors.

Every successful build removes any stale private `run.exit`, rebuilds the
receipts, and writes a completion marker only after validation. Full validation
parses that marker and checks its manifest digest against the current tracked
manifest.

The bounded compute-canary execution and route evidence are recorded below.
They are training-only and this runbook does not launch production or claim
Goal 050 scientific completion.

The canary runner is `src/dsdm_phase1/goal050_compute_canary.py`. The bound
substrate produces 94,873 rows under exact frozen eligibility. The authorized
90,000-row canary changes bundle size only; no scientific eligibility rule is
relaxed. Export must still fail closed if fewer than 90,000 rows are present.

The six canary receipts are under the private `canary/runs/` directory and
are aggregated into `metadata/goal050_compute_canary.json` and
`evidence/seawfb_modeling_foundation/goal050/compute_plan.json`. Alien CUDA
runs require `CUBLAS_WORKSPACE_CONFIG=:4096:8` before Python starts. The
selected route applies only to bridge-like vectorized PyTorch grids. Goal051
conventional models require their own small family-representative resource
gate. Future Goal051 conventional and Goal052 dSDM sessions
`goal051-conventional-deep` and `goal052-dsdm-deep`, their checkpoint layout,
and restart behavior are proposed and untested production plans. Each planned
endpoint would write an atomic `run.exit` plus an independent validation
receipt. Wake the dSDM orchestrator when a named tmux session completes or
blocks; do not notify Barry at every endpoint.
