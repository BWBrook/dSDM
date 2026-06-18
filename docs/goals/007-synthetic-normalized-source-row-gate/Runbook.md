# Runbook: Goal 007 Synthetic Normalized Source-Row Gate

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
sed -n '1,260p' docs/goals/007-synthetic-normalized-source-row-gate/Goal.md
sed -n '1,220p' docs/goals/007-synthetic-normalized-source-row-gate/Plan.md
sed -n '1,220p' docs/goals/007-synthetic-normalized-source-row-gate/Runbook.md
sed -n '1,220p' docs/goals/007-synthetic-normalized-source-row-gate/Log.md
sed -n '1,180p' docs/plan/phase1_primary_data_plan.md
sed -n '465,590p' docs/plan/phase1_primary_data_plan.md
sed -n '1,140p' docs/plan/phase1_decision_register.md
sed -n '1,460p' src/dsdm_phase1/contracts.py
sed -n '1,360p' src/dsdm_phase1/manifests.py
sed -n '1,160p' src/dsdm_phase1/__init__.py
sed -n '1,460p' tests/test_phase1_contracts.py
find tests/fixtures/phase1_synthetic -maxdepth 2 -type f | sort
sed -n '1,220p' tests/fixtures/phase1_synthetic/source_rows.json
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
docs/goals/007-synthetic-normalized-source-row-gate/Log.md
```

This is not a CLI goal. Do not add a command that writes runtime outputs unless
the implementation has an unusually strong reason and the files are tracked
synthetic fixtures created by this goal.

Suggested row-gate behavior:

- validate the existing Goal 006 mocked request manifest inputs;
- validate synthetic source rows with `validate_source_rows`;
- return deterministic in-memory summary data;
- preserve `pa_type` categories exactly;
- report true-absence and pseudoabsence rule ids separately;
- treat any `grid_cell_id` in fixtures as opaque synthetic metadata, not a
  spatial operation.

Suggested summary fields:

- `run_id`
- `stage`
- `status`
- `mocked_request_status`
- `decision_manifest_ids`
- `row_count`
- `row_ids`
- `species_ids`
- `sources`
- `source_dataset_ids`
- `source_dataset_names`
- `pa_types`
- `sources_by_pa_type`
- `required_provenance_fields`
- `true_absence_rule_ids`
- `pseudoabsence_rule_ids`
- `rows`

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
docs/goals/007-synthetic-normalized-source-row-gate/Log.md
```

Include:

- start state;
- materials read;
- tests added;
- expected red result;
- normalized source-row gate implementation and fixture changes;
- validation results;
- wake-up attempt result.

## Wake-Up

When complete or blocked, send a short message to the `dSDM` orchestrator
thread `019eac00-8de8-7d02-890f-b007a4622911`.

Completion message:

```text
Goal 007 is complete and ready for review. Final response in quoll has the
synthetic normalized source-row gate summary and validation evidence.
```

Blocked message:

```text
Goal 007 is blocked and needs orchestrator direction. Final response in quoll
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
- normalized source-row gate shape;
- decisions, sources, and row conditions blocked versus represented
  synthetically;
- recommended next goal;
- wake-up result;
- confirmation that forbidden work was not performed.
