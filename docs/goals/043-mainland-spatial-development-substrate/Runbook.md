# Runbook

From the repository root:

```sh
uv run --locked pytest -q tests/test_goal042_transfer_response.py tests/test_goal043_mainland_partitions.py
uv run --locked python -m dsdm_phase1.goal043_mainland_partitions build --root .
uv run --locked python -m dsdm_phase1.goal043_mainland_partitions validate --root .
uv run --locked python -m dsdm_phase1.goal043_mainland_partitions validate-tracked --root .
```

The build is local CPU work. It writes ignored assignments, split responses,
and detailed diagnostics under `data/raw/goal043/`, plus privacy-safe tracked
parameters and receipts. Do not open the Tasmania response table or use the
reserved `mainland_full` transform for model selection.
