# Runbook: Goal 011 Authoritative ALA Resolution Closure

## Preconditions

Run from `/Users/bwbrook/papers/dSDM`; confirm branch `main`, HEAD
`c6c42f4881bc115d7e9259a10f0b4b1d30135840`, clean status, and absent repo-local
`AGENTS.md`. Read `Goal.md`, `Plan.md`, `Runbook.md`, `Log.md` in that order.

## Required validation

```sh
python3 -m json.tool config/phase1_decision_bundle.json >/dev/null
python3 -m json.tool evidence/ala_taxon_resolution/2026-07-23/candidates.json >/dev/null
python3 -m json.tool evidence/ala_taxon_resolution/2026-07-23/manifest.json >/dev/null
python3 tests/test_ala_taxon_resolution.py
python3 tests/test_phase1_contracts.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile src/dsdm_phase1/*.py tests/test_phase1_contracts.py
git diff --check
git status --short --branch
```

No live services, payload reads, staging, commit, push, or Goal 010 artefact
edits are permitted.

The focused contract suite must include exact two-way concept-swap and forged
UUID negatives, full subtaxon/name-ID mutation negatives, intent-plan omission,
and synthetic ALA identity-block presence/leakage negatives. The expected
repair-pass counts are 57 focused Phase 1 tests, 11 Goal 010 tests, and 68
tests in the full discovery suite.
