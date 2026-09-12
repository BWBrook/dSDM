# Goal 052 runbook

Goal051 was accepted on 12 September and Barry authorized autonomous
continuation. Implementation and validation are now in preparation. The
scientific config remains frozen; the command names below are the required
interface and are not yet implemented. No Goal052 fit has run:

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
