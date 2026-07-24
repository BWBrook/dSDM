# Runbook: Goal 016 Offline ALA Field-Contract Calibration

Run from `/Users/bwbrook/papers/dSDM`. No account variable or network access is
needed.

Build deterministic aggregate-only evidence:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_field_contract build \
  --plan config/ala_field_contract_calibration_plan.json \
  --evidence-dir evidence/ala_field_contract/2026-07-24 \
  --raw-file \
  data/raw/ala/goal015-galah-pilot/2026-07-24/galah-occurrences.csv
```

Tracked-only validation must require raw replay:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_field_contract validate \
  --plan config/ala_field_contract_calibration_plan.json \
  --evidence-dir evidence/ala_field_contract/2026-07-24
```

Exact raw replay must return the split count/full-row decision:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_field_contract validate \
  --plan config/ala_field_contract_calibration_plan.json \
  --evidence-dir evidence/ala_field_contract/2026-07-24 \
  --raw-file \
  data/raw/ala/goal015-galah-pilot/2026-07-24/galah-occurrences.csv
```

Validation:

```sh
uv run --locked python tests/test_ala_field_contract.py
uv run --locked python -m unittest discover -s tests -p 'test_*.py'
uv run --locked python -m py_compile \
  src/dsdm_phase1/ala_field_contract.py \
  tests/test_ala_field_contract.py
git diff --check
```
