# Runbook

From the repository root:

```sh
uv run --locked pytest -q tests/test_goal040_support.py tests/test_goal042_transfer_response.py
uv run --locked python -m dsdm_phase1.goal042_transfer_response build --root .
uv run --locked python -m dsdm_phase1.goal042_transfer_response validate --root .
uv run --locked python -m dsdm_phase1.goal042_transfer_response validate-tracked --root .
```

`build` and `validate` require the ignored Goal 040/041 and camera authorities.
`validate-tracked` checks the privacy-safe Git surface without opening them.

The mainland table is explicitly a full-data reference. Do not fit a model
from it directly: Goal 043 must rematerialise responses from split-authorised
records. The Tasmania table is sealed evaluation evidence and must not enter
mainland partition construction, transformation fitting, pretraining, or
fine-tuning.
