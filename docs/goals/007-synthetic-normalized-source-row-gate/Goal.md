# Goal 007: Synthetic Normalized Source-Row Gate

## Objective

Add a synthetic-only normalized source-row gate that validates the existing
mocked request layer and synthetic row provenance, then returns a deterministic
in-memory normalization summary without live services, primary data access,
real raw-response transformation, spatial processing, generated outputs, or
scientific/source-rule decisions.

## Why This Matters

Goals 005 and 006 established that Phase 1 can validate acquisition intent
before any source is touched. The next useful layer is row readiness: prove
that a synthetic row table preserves provenance, source identity, `pa`,
`pa_type`, dataset metadata, and absence-rule identifiers before later work
tries to normalize real ALA or camera data.

This goal should remain a gate over synthetic normalized rows. It should not
pretend to know real ALA fields, real camera schemas, grid rules, or
pseudoabsence rules.

## Operating Mode

Implementation sprint with synthetic fixtures only.

This goal may add or modify standard-library Python modules, synthetic fixture
files, tests, and this goal's log. It must not acquire, inspect, copy,
transform, or process live or legacy primary data.

## Review Surface

The supervisor should inspect:

- normalized source-row gate module or function changes
- tests proving invalid decision/request state blocks the gate
- tests proving invalid row provenance or `pa_type` semantics block the gate
- tests proving valid synthetic rows produce deterministic summaries
- tests proving true absences and pseudoabsences remain distinct
- any new synthetic expected-output or negative fixtures
- `docs/goals/007-synthetic-normalized-source-row-gate/Log.md`
- final git diff
- validation command outputs
- final `git status --short --branch`

## Scope

In scope:

- Add a small standard-library function or module for a synthetic normalized
  source-row gate.
- Reuse existing validators from Goals 003-006 wherever possible.
- Require the Goal 006 mocked request manifest, or the same input bundle needed
  to build it, before summarizing rows.
- Use the existing synthetic row fixture if sufficient:
  - `tests/fixtures/phase1_synthetic/source_rows.json`
- Add only small, tracked, clearly synthetic fixtures if needed.
- Return an in-memory deterministic summary representing at least:
  - run id
  - stage name
  - status
  - request-manifest or mocked-request status
  - decision manifest ids where available
  - row count
  - row ids
  - species ids
  - source names
  - source dataset ids and names
  - `pa_type` categories
  - sources grouped by `pa_type`
  - required provenance fields
  - true-absence rule ids present in rows
  - pseudoabsence rule ids present in rows
  - compact per-row provenance summaries
- Add tests proving:
  - unresolved or missing mocked request decisions block before row summaries
    are returned;
  - invalid source contracts block before row summaries are returned;
  - missing required provenance fields block row summaries;
  - invalid `pa_type` values block row summaries;
  - missing `true_absence_rule_id` blocks true-absence rows;
  - missing `pseudoabsence_rule_id` blocks pseudoabsence rows;
  - valid synthetic rows produce deterministic summaries;
  - true absences and pseudoabsences are not merged or relabelled;
  - source `local_path` payloads are not opened and need not exist.
- Keep existing Goal 003, Goal 004, Goal 005, and Goal 006 tests passing.
- Update this goal's `Log.md`.

Out of scope:

- Live ALA calls, internet queries, real ALA request execution, response
  parsing, or field-selection decisions.
- Primary camera-trap data access, file inspection, ingestion, or schema
  mapping.
- Reading, copying, transforming, or processing payloads under `temp/` or
  `data/`.
- Creating raw, interim, processed, or generated data outputs.
- Real raw-to-normalized transformation logic for ALA or camera payloads.
- Deciding real focal species membership, `Thylogale billardierii`, ALA names,
  aliases, date bounds, data-resource filters, quality filters, camera source
  authority, true-absence rules, grid/boundary rules, pseudoabsence rules,
  predictor authority, QA tolerances, or manuscript claims.
- Grid snapping, coordinate cleaning, spatial joins, source combination,
  pseudoabsence derivation, predictor extraction, modelling, metrics, maps, or
  manuscript result changes.
- Remote/HPC jobs.
- Commits, pushes, pull requests, or staging.
- Broad repository migration or cleanup.

## Read First

- `docs/goals/007-synthetic-normalized-source-row-gate/Goal.md`
- `docs/goals/007-synthetic-normalized-source-row-gate/Plan.md`
- `docs/goals/007-synthetic-normalized-source-row-gate/Runbook.md`
- `docs/goals/007-synthetic-normalized-source-row-gate/Log.md`
- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- `src/dsdm_phase1/contracts.py`
- `src/dsdm_phase1/manifests.py`
- `src/dsdm_phase1/__init__.py`
- `tests/test_phase1_contracts.py`
- `tests/fixtures/phase1_synthetic/README.md`
- existing synthetic decision/source/species/request/row fixture files under
  `tests/fixtures/phase1_synthetic/`

Do not read `temp/` or `data/`. Do not inspect legacy payloads to infer real
source paths, rules, row counts, field mappings, or expected normalized output.

## Starting State Checks

Run and record:

```sh
pwd
git branch --show-current
git rev-parse --short HEAD
git status --short --branch
test -f AGENTS.md && echo "AGENTS.md present" || echo "AGENTS.md absent"
```

If `AGENTS.md` is present, read it before continuing and obey it.

Expected starting point after delegation:

- branch: `main`
- HEAD: `6afed1b`
- status: `## main...origin/main` plus this uncommitted Goal 007 packet

## Git And Publication Policy

- Do not commit.
- Do not push.
- Do not stage files.
- Treat the Goal 007 packet as an authorized uncommitted work surface.
- If unrelated dirty files appear, stop and report them before editing.
- Keep edits narrowly tied to this synthetic normalized source-row gate.

## Data, Compute, And Staging Policy

- Work only in `/Users/bwbrook/papers/dSDM`.
- Do not read `/Users/bwbrook/chief_of_staff`.
- Do not read `/Users/bwbrook/work/goal_composer`.
- Do not read other project repositories.
- Use the local Mac checkout only.
- Do not use remote compute.
- Do not query external services.
- Do not read or process real primary data or legacy payloads.
- New fixtures must be synthetic, small, tracked, and clearly labelled as
  synthetic.

## Required Work

1. Establish and log the live starting state.
2. Read the required surface and only the relevant normalized-row planning
   sections.
3. Add tests first for synthetic normalized source-row gate behavior.
4. Verify the new tests fail for the missing behavior.
5. Implement the smallest useful source-row gate function/module.
6. Add or update synthetic fixtures only if needed for negative cases or
   deterministic expected behavior.
7. Run the validation ladder.
8. Update this goal's `Log.md`.
9. Send the wake-up to the `dSDM` orchestrator thread when complete or blocked.

## Validation Gates

This goal is complete only when:

- unresolved/missing mocked request decisions block normalized row summaries;
- invalid source contracts block normalized row summaries;
- invalid row provenance or `pa_type` semantics block normalized row summaries;
- valid synthetic rows produce deterministic in-memory summaries;
- true absences and pseudoabsences remain separable in summary output;
- tests run locally without live data, real source paths, external services, or
  generated runtime outputs;
- existing Goal 003, Goal 004, Goal 005, and Goal 006 tests still pass;
- `git diff --check` exits 0;
- final `git status --short --branch` is reported.

Run at least:

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

## Deliverables

- Synthetic normalized source-row gate function/module.
- Tests covering blocking and deterministic-summary behavior.
- Any small synthetic expected or negative fixtures needed for review.
- Updated `docs/goals/007-synthetic-normalized-source-row-gate/Log.md`.
- Final response to the orchestrator summarizing:
  - materials read;
  - files changed;
  - validation performed;
  - decisions, sources, and row conditions blocked versus represented
    synthetically;
  - recommended next goal;
  - blockers or questions;
  - final git status.

## Decision Authority

The executor may decide:

- exact function/module names;
- exact synthetic fixture names;
- whether the summary takes the mocked request manifest directly or rebuilds it
  from the same inputs;
- exact summary field names;
- deterministic ordering for rows and grouped summaries;
- test organization.

The executor must not decide:

- real ALA retained fields, names, aliases, filters, date bounds, or API
  behavior;
- real primary camera-trap source location or schema mapping;
- real camera true-absence definitions;
- real focal species, grid, boundary, pseudoabsence, predictor, QA, or
  manuscript rules.

## Checkpoint Rules

Checkpoint in `Log.md`:

- start state;
- materials read;
- tests added and expected failing result;
- normalized source-row gate implementation and fixture changes;
- validation command outputs;
- wake-up attempt result.

Stop and report if the goal appears to require real data, live services,
runtime artifact generation, raw-response transformation, spatial processing,
or a Barry-level decision.
