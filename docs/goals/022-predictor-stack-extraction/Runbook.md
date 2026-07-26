# Runbook

```sh
uv lock
uv run python -m pytest tests/test_predictor_stack_extraction.py
uv run python -m dsdm_phase1.predictor_stack_extraction --root .
uv run python - <<'PY'
from pathlib import Path
from dsdm_phase1.predictor_stack_extraction import validate_evidence
r = Path('.')
print(validate_evidence(r/'config/predictor_stack_extraction_plan.json',
    r/'evidence/predictor_stack_extraction/2026-07-26', full=True,
    output_dir=r/'data/processed/predictors/goal022-predictor-stack-extraction/2026-07-26'))
PY
```

Production fails closed if a binding, oracle, destination, or ignore rule
drifts. The private output directory is intentionally ignored by Git.
Tracked validation is portable and does not require the ignored raster, grid,
response, or CSV outputs. It checks both manifest checksums and the frozen
semantic payload contract; full replay additionally recomputes private outputs.
The runtime receipt is portable across the supported Python 3.11+/3.12 lock
matrix and is not populated from the live NumPy version.
