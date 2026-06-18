# Goal 006: Mocked Acquisition-Request Dry Run

## Objective

Add a synthetic-only mocked acquisition-request layer that validates the Phase 1
decision/source gates and returns deterministic request-manifest records for
later ALA and camera acquisition work, without live service calls, primary data
access, real request execution, runtime outputs, or scientific/source-rule
decisions.

## Why This Matters

Goal 005 proved that synthetic species and source contracts can produce a
deterministic acquisition preflight summary. The next useful layer is not data
acquisition; it is request intent. Before any real ALA query or camera-trap
ingestion exists, the code should be able to say exactly what decisions,
synthetic species, source contracts, and audit metadata would govern the
request plan.

This goal should create the smallest useful mocked request surface so later
work cannot quietly jump from a valid source contract into live or private
data behavior.

## Operating Mode

Implementation sprint with synthetic fixtures only.

This goal may add or modify standard-library Python modules, synthetic fixture
files, tests, and this goal's log. It must not acquire, inspect, copy,
transform, or process live or legacy primary data.

## Review Surface

The supervisor should inspect:

- mocked request-manifest module or function changes
- tests proving unresolved ALA/camera acquisition decisions block request
  manifest creation
- tests proving valid synthetic decisions/contracts produce deterministic
  request records
- tests proving no live ALA query, internet access, primary camera data access,
  or source payload file existence is required
- any new synthetic decision or expected-output fixtures
- `docs/goals/006-mocked-acquisition-request-dry-run/Log.md`
- final git diff
- validation command outputs
- final `git status --short --branch`

## Scope

In scope:

- Add a small standard-library mocked request-manifest function or module.
- Reuse existing validators from Goals 003-005 wherever possible.
- Add only small, tracked, clearly synthetic fixtures if needed.
- Represent mocked request records for both synthetic source types already in
  the scaffold:
  - `ala_occurrence`
  - `camera_trap`
- Represent at least:
  - run id
  - request-manifest stage name
  - dry-run summary status or equivalent preflight state
  - decision manifest ids
  - required decision ids
  - source ids and source types
  - synthetic ALA request intent, including fake query names or aliases,
    fake date/filter policy identifiers, source contract id, checksum value,
    and a clear `mocked` or `not_executed` status
  - synthetic camera request/ingest intent, including fake authority/rule ids,
    source contract id, checksum value, and a clear `mocked` or `not_executed`
    status
  - license and sensitivity placeholders
  - a status such as `ready_for_mocked_request_review` or equivalent
- Add tests proving:
  - unresolved or missing ALA request decisions block mocked request creation
    before any request record is returned;
  - unresolved or missing camera source/true-absence decisions block mocked
    request creation before any request record is returned;
  - invalid source contracts block mocked request creation;
  - valid synthetic inputs produce deterministic mocked request records;
  - mocked request creation does not require live source paths, real payloads,
    internet access, or generated output files.
- Keep existing Goal 003, Goal 004, and Goal 005 tests passing.
- Update this goal's `Log.md`.

Out of scope:

- Live ALA calls, internet queries, real ALA request execution, or ALA response
  parsing.
- Primary camera-trap data access, file inspection, or ingestion.
- Reading, copying, transforming, or processing payloads under `temp/` or
  `data/`.
- Creating raw, interim, processed, or generated data outputs.
- Deciding real focal species membership, `Thylogale billardierii`, ALA names,
  aliases, date bounds, data-resource filters, quality filters, camera source
  authority, true-absence rules, grid/boundary rules, pseudoabsence rules,
  predictor authority, QA tolerances, or manuscript claims.
- Modelling, metrics, maps, manuscript result changes, or figure production.
- Remote/HPC jobs.
- Commits, pushes, pull requests, or staging.
- Broad repository migration or cleanup.

## Read First

- `docs/goals/006-mocked-acquisition-request-dry-run/Goal.md`
- `docs/goals/006-mocked-acquisition-request-dry-run/Plan.md`
- `docs/goals/006-mocked-acquisition-request-dry-run/Runbook.md`
- `docs/goals/006-mocked-acquisition-request-dry-run/Log.md`
- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- `src/dsdm_phase1/contracts.py`
- `src/dsdm_phase1/manifests.py`
- `src/dsdm_phase1/__init__.py`
- `tests/test_phase1_contracts.py`
- `tests/fixtures/phase1_synthetic/README.md`
- existing synthetic decision/source/species fixture files under
  `tests/fixtures/phase1_synthetic/`

Do not read `temp/` or `data/`. Do not inspect legacy payloads to infer real
source paths, rules, row counts, request parameters, or expected manifests.

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
- HEAD: `427a491`
- status: `## main...origin/main` plus this uncommitted Goal 006 packet

## Git And Publication Policy

- Do not commit.
- Do not push.
- Do not stage files.
- Treat the Goal 006 packet as an authorized uncommitted work surface.
- If unrelated dirty files appear, stop and report them before editing.
- Keep edits narrowly tied to this synthetic mocked request-manifest goal.

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
2. Read the required surface and only the relevant mocked request/planning
   sections.
3. Add tests first for mocked request-manifest behavior.
4. Verify the new tests fail for the missing behavior.
5. Implement the smallest useful mocked request-manifest function/module.
6. Add or update synthetic fixtures only if needed to express request decision
   state or expected deterministic output.
7. Run the validation ladder.
8. Update this goal's `Log.md`.
9. Send the wake-up to the `dSDM` orchestrator thread when complete or blocked.

## Validation Gates

This goal is complete only when:

- unresolved/missing ALA request decisions block mocked request creation;
- unresolved/missing camera request/interpretation decisions block mocked
  request creation;
- invalid source contracts block mocked request creation;
- valid synthetic inputs produce deterministic mocked request records;
- mocked request records include decision ids, source ids/types, checksum
  metadata, license placeholders, sensitivity placeholders, and explicit
  not-executed status;
- tests run locally without live data, real source paths, external services, or
  generated runtime outputs;
- existing Goal 003, Goal 004, and Goal 005 tests still pass;
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

- Synthetic mocked request-manifest function/module.
- Tests covering blocking and deterministic mocked-request behavior.
- Any small synthetic decision/request fixtures needed for review.
- Updated `docs/goals/006-mocked-acquisition-request-dry-run/Log.md`.
- Final response to the orchestrator summarizing:
  - materials read;
  - files changed;
  - validation performed;
  - decisions/sources blocked versus represented synthetically;
  - recommended next goal;
  - blockers or questions;
  - final git status.

## Decision Authority

The executor may decide:

- exact function/module names;
- exact synthetic fixture names;
- exact mocked request field names;
- whether the summary is purely in-memory or compared against a tracked
  synthetic expected fixture;
- deterministic ordering for request records and summary fields;
- test organization.

The executor must not decide:

- real ALA query names, aliases, filters, date bounds, or API behavior;
- real primary camera-trap source location;
- real camera true-absence definitions;
- real focal species, grid, boundary, pseudoabsence, predictor, QA, or
  manuscript rules.

## Checkpoint Rules

Checkpoint in `Log.md`:

- start state;
- materials read;
- tests added and expected failing result;
- mocked request-manifest implementation and fixture changes;
- validation command outputs;
- wake-up attempt result.

Stop and report if the goal appears to require real data, live services,
runtime artifact generation, or a Barry-level decision.
