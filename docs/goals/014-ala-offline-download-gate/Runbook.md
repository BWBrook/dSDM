# Runbook: Goal 014 ALA Offline Download Gate

Run from `/Users/bwbrook/papers/dSDM` on clean `main` at the pinned baseline.
The single live attempt used the official GET endpoint with `qa=none`, exact
20-field `fields`, CSV output, `dwcHeaders=false`, `includeMisc=false`,
`emailNotify=false`, and `mintDoi=false`. The runtime email was supplied only
through `ALA_DOWNLOAD_EMAIL` and is absent from tracked material.

Focused replay:

```sh
python3 tests/test_ala_offline_download.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m json.tool config/ala_offline_download_plan.json >/dev/null
python3 -m py_compile src/dsdm_phase1/*.py tests/test_ala_offline_download.py
git diff --check
```

The retained raw selector proves an empty `facetResults` array; it does not
echo the requested `facet=false`, which is recorded as operator-reported.
Tracked-only validation returns
`blocked_package_structurally_valid_selector_raw_replay_required`. Replay of
the exact ignored selector file returns
`blocked_submission_http_403_no_job_handle_observed`; no pass/readiness-for-
download state exists. The request ledger is operator-reported and sanitized
after the fact, not independently reconstructible: raw request, response body,
response headers, and status handle were not retained.
