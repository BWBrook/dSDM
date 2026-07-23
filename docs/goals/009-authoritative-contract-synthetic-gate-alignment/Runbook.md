# Runbook: Goal 009 Authoritative Contract-to-Synthetic Gate Alignment

## Preconditions and read order

Run from `/Users/bwbrook/papers/dSDM`; confirm branch `main`, HEAD
`8138751e26f086b375ee93f69ffc56eebf5c2eb8`, clean status, and absent repo-local
`AGENTS.md`. After packet creation read `Goal.md`, `Plan.md`, `Runbook.md`,
`Log.md` in that order.

Read Goal 008 packet/bundle, Goal 007 active scaffold surfaces, current
validators/builders/tests, and synthetic fixtures only. Do not read `data/` or
`temp/`.

## Validation

```sh
python3 -m json.tool config/phase1_decision_bundle.json >/dev/null
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/test_phase1_contracts.py
python3 -m py_compile src/dsdm_phase1/*.py tests/test_phase1_contracts.py
git diff --check
git status --short --branch
```

Also run a compact `rg` audit of active `true_absence` occurrences and explain
permitted historical/negative-test residuals. Do not run Phase 0 verification.

## Publication boundary

No staging, commit, push, publication, live acquisition, source collapse, or
spatial assignment is permitted; the parent orchestrator owns acceptance.
