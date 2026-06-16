# Runbook: Goal 001 Phase 0 Verification And Gate Review

## Preconditions

Run from the action repo:

```sh
cd /Users/bwbrook/papers/dSDM
```

Do not start if the current working directory is not the dSDM action repo.

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
sed -n '1,220p' README.md
sed -n '1,240p' docs/strategic_plan_30000ft.md
sed -n '1,260p' docs/plan/phase0_tactical_plan.md
sed -n '1,260p' docs/phase0/phase0_report.md
sed -n '1,260p' docs/phase0/legacy_workflow_map.md
sed -n '1,220p' docs/phase0/phase1_questions.md
sed -n '1,260p' scripts/phase0_inventory.py
sed -n '1,240p' scripts/phase0_verify.py
sed -n '1,200p' manuscript/Makefile
```

It is fine to use `rg`/`sed` more narrowly after this if a validation failure
needs diagnosis.

## Verification Ladder

Run:

```sh
python3 scripts/phase0_verify.py
```

If and only if this fails due to stale Phase 0 generated inventories or report
state, run one regeneration:

```sh
python3 scripts/phase0_inventory.py
python3 scripts/phase0_verify.py
```

If verification still fails, stop and document the blocker.

Then run:

```sh
make -C manuscript validate
make -C manuscript check
git status --short --ignored
git diff --check
git status --short --branch
```

Capture pass/fail outcomes and important output summaries in `Log.md` and the
gate review. Do not paste huge command logs; record the meaningful lines and
exact failure text if blocked.

## Gate Review File

Create or update:

```text
docs/phase0/phase0_gate_review.md
```

Suggested skeleton:

```md
# Phase 0 Gate Review

Date: 2026-06-15
Audited HEAD: `<short-sha>`

## Audit Scope

## Audited State

## Materials Reviewed

## Validation Results

| Check | Outcome | Notes |
| --- | --- | --- |

## Corrections Made

## Gate Checklist

- [ ] Phase 0 manifests and docs exist.
- [ ] `python3 scripts/phase0_verify.py` passes.
- [ ] `make -C manuscript validate` passes.
- [ ] `make -C manuscript check` passes.
- [ ] Bulky payloads remain ignored.
- [ ] Phase 0 evidence is clear enough for Barry signoff consideration.

## Remaining Risks Or Questions

## Recommendation
```

Use checked boxes only when evidence supports them.

## Log Update

Append chronological entries to:

```text
docs/goals/001-phase0-verification-gate-review/Log.md
```

Include:

- start state
- materials read
- commands run
- corrections made
- final status
- wake-up attempt result

## Wake-Up

When complete or blocked, send a short message to the `dSDM` orchestrator
thread `019eac00-8de8-7d02-890f-b007a4622911`.

Completion message:

```text
Goal 001 is complete and ready for review. Final response in quoll has the
validation summary and gate recommendation.
```

Blocked message:

```text
Goal 001 is blocked and needs orchestrator direction. Final response in quoll
has the exact blocker and next decision needed.
```

If the thread tool is unavailable, use `tool_search` to expose
`send_message_to_thread`. If that still fails, document the failure exactly in
`Log.md` and the final response.

## Final Response Checklist

Before final response, check:

```sh
git diff --stat
git status --short --branch
```

Final response must state:

- branch and audited HEAD
- starting and final status
- materials read
- command outcomes
- files changed
- recommendation
- blockers/questions
- wake-up result
- confirmation that forbidden work was not performed
