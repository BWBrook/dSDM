# Runbook: Goal 008 Phase 1 Decision Consolidation

## Preconditions

Run from `/Users/bwbrook/papers/dSDM`. Confirm branch `main`, HEAD `2971b26`,
status `## main...origin/main`, and no repo-local `AGENTS.md` before edits.

## Required read order after packet creation

Read `Goal.md`, then `Plan.md`, then `Runbook.md`, then `Log.md`.

## Test-first and implementation loop

- Add tests for the accepted bundle, all 30 unique decision IDs, the nine
  species and special policies, the two live blockers, and contradiction/missing
  decision failures.
- Run `python3 tests/test_phase1_contracts.py` to record RED for the missing
  validator.
- Implement bundle loading/validation and export the public API.
- Update the human register and rerun focused/full tests.

## Final commands

```sh
python3 -m json.tool config/phase1_decision_bundle.json >/dev/null
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/test_phase1_contracts.py
git diff --check
git status --short --branch
```

Do not run `scripts/phase0_verify.py`. Do not inspect `temp/`, `data/`, raw
payloads, or external services. Do not stage, commit, push, or publish.
