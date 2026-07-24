# Runbook: Goal 015 ALA Galah Route Gate

Run from `/Users/bwbrook/papers/dSDM` at the authorized clean baseline.
`ALA_DOWNLOAD_EMAIL` must already exist in the runtime environment; never put
its value in a command, file, log, or test.

Pre-live gate:

```sh
test -n "${ALA_DOWNLOAD_EMAIL:-}"
uv sync --locked
uv run --locked python tests/test_ala_galah_pilot.py
uv run --locked python -m json.tool config/ala_galah_pilot_plan.json >/dev/null
uv run --locked python -m py_compile \
  src/dsdm_phase1/ala_galah_pilot.py tests/test_ala_galah_pilot.py
```

Single live execution:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_galah_pilot run \
  --plan config/ala_galah_pilot_plan.json \
  --raw-dir data/raw/ala/goal015-galah-pilot/2026-07-24 \
  --evidence-dir evidence/ala_galah_pilot/2026-07-24
```

The runner gives Galah one explicit config file inside a
`TemporaryDirectory`, with `verbose=False`, then passes that same path to both
high-level calls. Its POSIX alarm bounds the occurrence call to 900 seconds
outside Galah's polling implementation. Any stopped outcome is final for this
goal; do not rerun.

The 2026-07-24 execution initially stopped at the schema gate because the
validator treated requested `license`, returned as `dcterms:license` under
`dwcHeaders=true`, as absent. The one authorized repair was offline only:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_galah_pilot rebuild \
  --plan config/ala_galah_pilot_plan.json \
  --raw-dir data/raw/ala/goal015-galah-pilot/2026-07-24 \
  --evidence-dir evidence/ala_galah_pilot/2026-07-24
```

This repair accepts no other alias or missing core field, records the initial
stop, and proves `second_live_attempt=false`.

Raw-backed replay and final checks:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_galah_pilot validate \
  --plan config/ala_galah_pilot_plan.json \
  --evidence-dir evidence/ala_galah_pilot/2026-07-24 \
  --raw-dir data/raw/ala/goal015-galah-pilot/2026-07-24
uv run --locked python tests/test_ala_galah_pilot.py
uv run --locked python -m unittest discover -s tests -p 'test_*.py'
git diff --check
git check-ignore -v \
  data/raw/ala/goal015-galah-pilot/2026-07-24/galah-count.csv \
  data/raw/ala/goal015-galah-pilot/2026-07-24/galah-occurrences.csv
```

Tracked-only validation must remain
`galah_pilot_tracked_evidence_valid_raw_replay_required`. Only exact local raw
replay may return `galah_route_usable_for_later_acquisition_design`.
