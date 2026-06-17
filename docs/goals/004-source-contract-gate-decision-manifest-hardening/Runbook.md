# Runbook: Goal 004 Source Contract Gate And Decision Manifest Hardening

## Preconditions

Run from the action repo:

```sh
cd /Users/bwbrook/papers/dSDM
```

Do not start if the working directory is not the dSDM action repo.

## Starting Checks

```sh
pwd
git branch --show-current
git rev-parse --short HEAD
git status --short --branch
test -f AGENTS.md && echo "AGENTS.md present" || echo "AGENTS.md absent"
```

If `AGENTS.md` is present:

```sh
sed -n '1,220p' AGENTS.md
```

Record the outcome in `Log.md`.

## Read Required Surface

```sh
sed -n '1,220p' docs/goals/004-source-contract-gate-decision-manifest-hardening/Goal.md
sed -n '1,220p' docs/goals/004-source-contract-gate-decision-manifest-hardening/Plan.md
sed -n '1,220p' docs/goals/004-source-contract-gate-decision-manifest-hardening/Runbook.md
sed -n '1,220p' docs/goals/004-source-contract-gate-decision-manifest-hardening/Log.md
sed -n '1,120p' docs/plan/phase1_decision_register.md
sed -n '1,180p' docs/plan/phase1_primary_data_plan.md
sed -n '470,620p' docs/plan/phase1_primary_data_plan.md
sed -n '1,260p' src/dsdm_phase1/contracts.py
sed -n '1,240p' tests/test_phase1_contracts.py
sed -n '1,120p' tests/fixtures/phase1_synthetic/README.md
```

Do not read `temp/` or `data/`.

## Implementation Notes

Keep changes local to the existing scaffold unless there is a clear reason:

```text
src/dsdm_phase1/__init__.py
src/dsdm_phase1/contracts.py
tests/test_phase1_contracts.py
tests/fixtures/phase1_synthetic/
docs/goals/004-source-contract-gate-decision-manifest-hardening/Log.md
```

Suggested behavior:

- use `validate_decision_manifest(..., stage="source_contracts")` to enforce
  `P1-D007`, `P1-D008`, and `P1-D009`;
- add a small source-contract validator if needed;
- reject unsafe local paths before any filesystem reads beyond synthetic
  fixtures;
- require checksum or equivalent audit metadata for synthetic source entries;
- require license and sensitivity placeholders so later real sources cannot
  skip those fields silently.

Do not invent real source locations, scientific filters, or true-absence rules.

## Validation Commands

Run the new scaffold tests:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

Then run:

```sh
git diff --check
git status --short --branch
```

Do not run:

```sh
python3 scripts/phase0_verify.py
```

unless the orchestrator specifically directs it later.

## Log Update

Append chronological entries to:

```text
docs/goals/004-source-contract-gate-decision-manifest-hardening/Log.md
```

Include:

- start state;
- materials read;
- tests added;
- expected red result;
- validator and fixture changes;
- validation results;
- wake-up attempt result.

## Wake-Up

When complete or blocked, send a short message to the `dSDM` orchestrator
thread `019eac00-8de8-7d02-890f-b007a4622911`.

Completion message:

```text
Goal 004 is complete and ready for review. Final response in quoll has the
source-contract gate summary and validation evidence.
```

Blocked message:

```text
Goal 004 is blocked and needs orchestrator direction. Final response in quoll
has the exact blocker and next decision needed.
```

If the thread tool is unavailable, use `tool_search` to expose
`send_message_to_thread`. If that still fails, document the failure exactly in
`Log.md` and the final response.

## Final Response Checklist

Final response must state:

- branch and HEAD;
- starting and final status;
- materials read;
- files changed;
- validation commands and outcomes;
- how `P1-D007`, `P1-D008`, and `P1-D009` are blocked or represented
  synthetically;
- recommended next goal;
- wake-up result;
- confirmation that forbidden work was not performed.
