# Runbook: Goal 006 Mocked Acquisition-Request Dry Run

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
sed -n '1,260p' docs/goals/006-mocked-acquisition-request-dry-run/Goal.md
sed -n '1,220p' docs/goals/006-mocked-acquisition-request-dry-run/Plan.md
sed -n '1,220p' docs/goals/006-mocked-acquisition-request-dry-run/Runbook.md
sed -n '1,220p' docs/goals/006-mocked-acquisition-request-dry-run/Log.md
sed -n '1,180p' docs/plan/phase1_primary_data_plan.md
sed -n '465,590p' docs/plan/phase1_primary_data_plan.md
sed -n '1,120p' docs/plan/phase1_decision_register.md
sed -n '1,460p' src/dsdm_phase1/contracts.py
sed -n '1,260p' src/dsdm_phase1/manifests.py
sed -n '1,140p' src/dsdm_phase1/__init__.py
sed -n '1,360p' tests/test_phase1_contracts.py
find tests/fixtures/phase1_synthetic -maxdepth 2 -type f | sort
```

Do not read `temp/` or `data/`.

## Implementation Notes

Likely touched paths:

```text
src/dsdm_phase1/__init__.py
src/dsdm_phase1/contracts.py
src/dsdm_phase1/manifests.py
tests/test_phase1_contracts.py
tests/fixtures/phase1_synthetic/
docs/goals/006-mocked-acquisition-request-dry-run/Log.md
```

This is not a CLI goal. Do not add a command that writes runtime outputs unless
the implementation has an unusually strong reason and the files are tracked
synthetic fixtures created by this goal.

Suggested mocked request behavior:

- validate the existing Goal 005 acquisition dry-run summary inputs;
- validate a synthetic request decision manifest for ALA request decisions;
- validate a synthetic request decision manifest for camera request decisions,
  or use one combined synthetic request decision manifest if cleaner;
- return deterministic in-memory request-manifest data for synthetic ALA and
  synthetic camera sources;
- mark all request records as `mocked`, `not_executed`, or equivalent.

Suggested summary fields:

- `run_id`
- `stage`
- `status`
- `decision_manifest_ids`
- `required_decisions`
- `request_count`
- `requests`
- per-request `source_id`
- per-request `source_type`
- per-request `decision_references`
- per-request `checksum`
- per-request `license`
- per-request `sensitivity`
- per-request fake ALA/camera intent metadata
- per-request execution status such as `not_executed`

Use existing validators. Do not duplicate checks if a validator already owns
them.

## Validation Commands

Run:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/test_phase1_contracts.py
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
docs/goals/006-mocked-acquisition-request-dry-run/Log.md
```

Include:

- start state;
- materials read;
- tests added;
- expected red result;
- mocked request-manifest implementation and fixture changes;
- validation results;
- wake-up attempt result.

## Wake-Up

When complete or blocked, send a short message to the `dSDM` orchestrator
thread `019eac00-8de8-7d02-890f-b007a4622911`.

Completion message:

```text
Goal 006 is complete and ready for review. Final response in quoll has the
mocked acquisition-request dry-run summary and validation evidence.
```

Blocked message:

```text
Goal 006 is blocked and needs orchestrator direction. Final response in quoll
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
- mocked request manifest shape;
- decisions/sources blocked versus represented synthetically;
- recommended next goal;
- wake-up result;
- confirmation that forbidden work was not performed.
