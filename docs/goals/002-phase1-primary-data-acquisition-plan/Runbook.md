# Runbook: Goal 002 Phase 1 Primary-Data Acquisition Plan

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

## Read Required Phase 0 Surface

```sh
sed -n '1,240p' docs/phase0/phase0_gate_review.md
sed -n '1,220p' docs/phase0/phase1_questions.md
sed -n '1,260p' docs/strategic_plan_30000ft.md
sed -n '1,260p' docs/phase0/phase0_report.md
sed -n '1,280p' docs/phase0/legacy_workflow_map.md
sed -n '1,240p' docs/plan/phase0_tactical_plan.md
sed -n '1,220p' README.md
```

## Read Legacy Intent Surface

Use these as intent references, not implementation templates:

```sh
sed -n '1,240p' temp/src/0_galah_ALA.r
sed -n '1,260p' temp/src/1_process_point_data.R
sed -n '1,260p' temp/src/1a_tas_sdm_data_combine.r
sed -n '1,280p' temp/src/2_tas_sdm_data_cv_split.r
sed -n '1,260p' temp/src/3_create_sdm_data.R
sed -n '1,280p' temp/src/sdm_data_func.R
sed -n '1,220p' temp/src/z_execute.R
```

If a file is missing, record that as evidence; do not search outside the repo.

## Create Deliverables

Create:

```text
docs/plan/phase1_primary_data_plan.md
docs/plan/phase1_decision_register.md
```

Do not edit implementation code or data files.

## Review Checklist

Before final response, ensure the plan:

- keeps Tasmanian mammals first
- keeps SE Australia birds later
- treats old processed CSVs as reference/comparison artifacts
- identifies all Barry-level scientific decisions without deciding them
- describes provenance and manifest requirements
- defines validation gates for later implementation
- includes a practical smoke-test fixture strategy
- recommends the next implementation goal

## Validation Commands

Run:

```sh
git diff --check
git status --short --branch
```

Do not run:

```sh
python3 scripts/phase0_verify.py
```

unless the orchestrator explicitly directs it later.

## Log Update

Append chronological entries to:

```text
docs/goals/002-phase1-primary-data-acquisition-plan/Log.md
```

Include:

- start state
- materials read
- legacy scripts reviewed
- files changed
- validation results
- wake-up attempt result

## Wake-Up

When complete or blocked, send a short message to the `dSDM` orchestrator
thread `019eac00-8de8-7d02-890f-b007a4622911`.

Completion message:

```text
Goal 002 is complete and ready for review. Final response in quoll has the
planning summary and decision-register highlights.
```

Blocked message:

```text
Goal 002 is blocked and needs orchestrator direction. Final response in quoll
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
- major Barry-level decisions surfaced
- recommended first implementation goal
- wake-up result
- confirmation that forbidden work was not performed
