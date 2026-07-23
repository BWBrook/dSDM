# Runbook: Goal 010 ALA Taxon Resolution Evidence Gate

## Preconditions

Run from `/Users/bwbrook/papers/dSDM`; confirm `main` at
`f61846ec08ad254d14b5f38ad21f1b9626ee4939`, clean status, and absent repo-local
`AGENTS.md`. Read `Goal.md`, `Plan.md`, `Runbook.md`, `Log.md` in that order.

## Retrieval boundary

Official name-matching/BIE taxon metadata requests are permitted. Occurrence
APIs, records, coordinates, camera material, `data/`, and `temp/` are forbidden.
Do not expose credentials or seek an API key.

## Final validation

```sh
python3 -m json.tool config/phase1_decision_bundle.json >/dev/null
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/test_ala_taxon_resolution.py
python3 -m py_compile src/dsdm_phase1/*.py tests/test_ala_taxon_resolution.py
git diff --check
git status --short --branch
```

No staging, commit, push, bundle/register edits, or publication.
