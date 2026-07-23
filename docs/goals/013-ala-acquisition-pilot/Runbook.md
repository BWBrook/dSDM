# Runbook: Goal 013 ALA Acquisition Pilot

## Preconditions

Run from `/Users/bwbrook/papers/dSDM`; require branch `main`, HEAD and
`origin/main` at `a6bce2622a1d0af2ff6aecb9c96d6491aac521de`, and a clean
tree. Read the Goal 012 packet and frozen evidence before implementing.

## Live command

```sh
PYTHONPATH=src python3 -m dsdm_phase1.ala_acquisition_pilot \
  --profile config/ala_acquisition_request_profile.json \
  --plan config/ala_acquisition_pilot_plan.json \
  --raw-dir data/raw/ala/goal013-pilot/2026-07-23 \
  --evidence-dir evidence/ala_acquisition_pilot/2026-07-23
```

Do not rerun the command to fill short or zero pages. A retry is permitted only
for a transient transport/5xx failure that returned no record payload, and
must be represented in sanitized request evidence.

Fail closed if the response does not accept and echo
`sort=occurrenceID&dir=asc`. Even when it does, interpret the evidence only as
bounded order and page-overlap behaviour. The search route has no documented
snapshot consistency and is capped at the first 5,000 results.

The one authorized focused repair permits recovery only when the raw directory
contains the exact first planned file and tracked evidence does not yet exist.
That file is not requested again; its write mtime is labelled as recovered
local provenance rather than an exact network timestamp. Any broader or
different partial raw state fails closed.

## Raw-evidence acceptance boundary

Raw-backed validation must parse both response query echoes, `query` and
`urlParameters`, and require an exact match to the planned `q`, the two planned
`fq` values, and `disableAllQualityFilters=true`. It must also require each
page's `totalRecords`, expected row count from `totalRecords`, `start`, and
`pageSize`, and strict ascending occurrenceIDs. Each parent page pair must
report equal `totalRecords`, zero occurrenceID overlap, and an ascending
boundary between pages.

Tracked evidence alone can establish only structural validity. A tracked-only
validation must return
`tracked_package_structurally_valid_raw_replay_required`, never a pass
readiness. Only reconstruction from the exact ignored raw snapshot can return
`pilot_pass_ready_for_bounded_full_acquisition_design`.

## Required validation

```sh
python3 tests/test_ala_acquisition_pilot.py
python3 tests/test_ala_query_scope.py
python3 tests/test_ala_taxon_resolution.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m json.tool config/ala_acquisition_pilot_plan.json >/dev/null
python3 -m json.tool evidence/ala_acquisition_pilot/2026-07-23/requests.json >/dev/null
python3 -m json.tool evidence/ala_acquisition_pilot/2026-07-23/review.json >/dev/null
python3 -m json.tool evidence/ala_acquisition_pilot/2026-07-23/manifest.json >/dev/null
python3 -m py_compile src/dsdm_phase1/*.py tests/test_ala_acquisition_pilot.py
git diff --check
```

Also run both validation modes: confirm that tracked-only validation returns
the explicit raw-replay-required state, then replay the tracked package against
the ignored raw files and require the bounded-design pass. Verify every
manifest and raw checksum, prove the raw directory is ignored, audit the exact
tracked/untracked footprint, and scan tracked Goal 013 artifacts for record or
coordinate payload leakage.
