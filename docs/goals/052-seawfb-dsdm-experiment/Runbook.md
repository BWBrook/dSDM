# Goal 052 runbook

This runbook is inactive until Goal 051 is accepted. The command names below
are the frozen interface expected of the later implementation; they are not
available in this protocol-only goal:

```sh
uv run --locked pytest -q tests/test_goal052_seawfb_dsdm.py
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm validate-inputs --root .
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm canary --root .
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm run --root . --device cpu
uv run --locked python -m dsdm_phase1.goal052_seawfb_dsdm validate --root .
```

The planned detached session is `dsdm-goal052-dsdm`. It must be resumable at
the target/endpoint/arm/seed/fold checkpoint and must write an atomic
completion marker only after independent validation. Do not open NCP, SEH, or
NNC outcomes in this goal.
