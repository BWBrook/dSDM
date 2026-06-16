# Runbook: Goal 003 Phase 1 Contract Scaffold And Synthetic Fixtures

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
sed -n '1,260p' docs/plan/phase1_primary_data_plan.md
sed -n '261,620p' docs/plan/phase1_primary_data_plan.md
sed -n '1,220p' docs/plan/phase1_decision_register.md
sed -n '1,220p' docs/strategic_plan_30000ft.md
sed -n '1,220p' README.md
```

Inspect root-level file names and manifests:

```sh
find . -maxdepth 2 -type f | sort | sed -n '1,160p'
```

Do not read `temp/` or `data/`.

## Implementation Notes

Keep the scaffold minimal. Prefer:

- standard-library Python
- small plain-text fixtures such as CSV/JSON/YAML-like data if dependencies are
  not already present
- explicit validation errors
- direct tests that show blocking behavior

If a dependency is needed, justify it in the final response and avoid heavy
geospatial dependencies.

## Validation Commands

Run the new scaffold's test/validation command.

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
docs/goals/003-phase1-contract-scaffold-fixtures/Log.md
```

Include:

- start state
- materials read
- scaffold layout chosen
- fixtures created
- validators/tests added
- validation results
- wake-up attempt result

## Wake-Up

When complete or blocked, send a short message to the `dSDM` orchestrator
thread `019eac00-8de8-7d02-890f-b007a4622911`.

Completion message:

```text
Goal 003 is complete and ready for review. Final response in quoll has the
scaffold summary and validation evidence.
```

Blocked message:

```text
Goal 003 is blocked and needs orchestrator direction. Final response in quoll
has the exact blocker and next decision needed.
```

If the thread tool is unavailable, use `tool_search` to expose
`send_message_to_thread`. If that still fails, document the failure exactly in
`Log.md` and the final response.

## Final Response Checklist

Final response must state:

- branch and HEAD
- starting and final status
- materials read
- files changed
- validation commands and outcomes
- decisions represented as unresolved blockers
- recommended next goal
- wake-up result
- confirmation that forbidden work was not performed
