# Runbook

Offline checks:

```sh
PYTHONPATH=src uv run --locked python tests/test_ala_full_acquisition.py
PYTHONPATH=src uv run --locked python -m unittest discover -s tests
uv run --locked python -m json.tool config/ala_full_acquisition_plan.json >/dev/null
uv run --locked python -m py_compile src/dsdm_phase1/ala_full_acquisition.py
```

The single authorised live invocation (only after review) uses the locked
project environment. `ALA_DOWNLOAD_EMAIL` must be supplied to this process at
runtime; never place its value in the command, plan, logs, or tracked files.

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_full_acquisition run \
  --plan config/ala_full_acquisition_plan.json \
  --raw-dir data/raw/ala/goal017-nine-species/2026-07-24 \
  --evidence-dir evidence/ala_full_acquisition/2026-07-24
```

Validation is offline and tracked-only unless an exact raw directory is also
provided:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_full_acquisition validate \
  --plan config/ala_full_acquisition_plan.json \
  --evidence-dir evidence/ala_full_acquisition/2026-07-24 \
  --raw-dir data/raw/ala/goal017-nine-species/2026-07-24
```

Do not retry a stopped run or reuse its raw/evidence directories.
