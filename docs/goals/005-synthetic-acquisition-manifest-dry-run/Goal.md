# Goal 005: Synthetic Acquisition-Manifest Dry Run

## Objective

Add a synthetic-only dry-run manifest layer that validates the existing Phase 1
decision and source-contract gates, then produces a deterministic acquisition
preflight summary without live ALA calls, primary camera-trap access, real data
paths, or data processing.

## Why This Matters

Goals 003 and 004 established executable gates for species decisions and source
contracts. The next useful layer is not acquisition itself; it is a dry-run
manifest preflight that proves the system can combine decision state,
source-contract metadata, checksum evidence, license/sensitivity placeholders,
and run metadata into an auditable bundle before any external source is touched.

This gives later ALA and camera work a safer handoff surface. If the dry run
cannot prove which decisions, sources, and manifests would govern a run, the
real run should not exist.

## Operating Mode

Implementation sprint with synthetic fixtures only.

This goal may add or modify standard-library Python modules, synthetic fixture
files, tests, and this goal's log. It must not acquire, inspect, copy,
transform, or process live or legacy primary data.

## Review Surface

The supervisor should inspect:

- manifest dry-run module or validator changes
- tests proving invalid decisions/contracts block the dry run
- tests proving valid synthetic inputs produce deterministic manifest summaries
- any synthetic manifest fixtures
- `docs/goals/005-synthetic-acquisition-manifest-dry-run/Log.md`
- final git diff
- validation command outputs
- final `git status --short --branch`

## Scope

In scope:

- Add a small standard-library dry-run manifest function or module.
- Reuse existing validators for:
  - `species_contract`
  - `source_contracts`
  - source-contract metadata
  - synthetic manifest checksum behavior where relevant
- Produce an in-memory deterministic summary or a tracked synthetic expected
  fixture. The dry run must not create runtime output artifacts outside tracked
  source/test/fixture files authorized by this goal.
- Represent at least:
  - run id
  - dry-run stage name
  - decision manifest id
  - required decision ids
  - source ids
  - source types
  - source checksums
  - license placeholders
  - sensitivity placeholders
  - status such as `ready_for_mocked_acquisition` or equivalent
- Add tests proving:
  - unresolved or missing decisions fail before manifest summary creation;
  - invalid source contracts fail before manifest summary creation;
  - valid synthetic species/source contracts produce a deterministic summary;
  - the dry run does not require live source paths or real payloads.
- Keep existing Goal 003 and Goal 004 tests passing.
- Update this goal's `Log.md`.

Out of scope:

- Live ALA calls, internet queries, or real request construction against ALA.
- Primary camera-trap data access.
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

- `docs/goals/005-synthetic-acquisition-manifest-dry-run/Goal.md`
- `docs/goals/005-synthetic-acquisition-manifest-dry-run/Plan.md`
- `docs/goals/005-synthetic-acquisition-manifest-dry-run/Runbook.md`
- `docs/goals/005-synthetic-acquisition-manifest-dry-run/Log.md`
- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- `src/dsdm_phase1/contracts.py`
- `src/dsdm_phase1/__init__.py`
- `tests/test_phase1_contracts.py`
- `tests/fixtures/phase1_synthetic/README.md`
- existing synthetic decision/source/species fixture files under
  `tests/fixtures/phase1_synthetic/`

Do not read `temp/` or `data/`. Do not inspect legacy payloads to infer real
source paths, rules, row counts, or expected manifests.

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
- HEAD: `998c280`
- status: `## main...origin/main` plus this uncommitted Goal 005 packet

## Git And Publication Policy

- Do not commit.
- Do not push.
- Do not stage files.
- Treat the Goal 005 packet as an authorized uncommitted work surface.
- If unrelated dirty files appear, stop and report them before editing.
- Keep edits narrowly tied to this synthetic dry-run manifest goal.

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
2. Read the required surface and only the relevant manifest/dry-run planning
   sections.
3. Add tests first for dry-run behavior.
4. Verify the new tests fail for the missing dry-run manifest behavior.
5. Implement the smallest useful dry-run manifest function/module.
6. Add or update synthetic fixtures only if needed to express expected dry-run
   behavior.
7. Run the validation ladder.
8. Update this goal's `Log.md`.
9. Send the wake-up to the `dSDM` orchestrator thread when complete or blocked.

## Validation Gates

This goal is complete only when:

- invalid decision manifests block the dry run;
- invalid source contracts block the dry run;
- valid synthetic species/source inputs produce deterministic manifest summary
  content;
- the manifest summary includes decision ids, source ids, source types,
  checksum metadata, license placeholders, and sensitivity placeholders;
- tests run locally without live data, real source paths, or external services;
- existing Goal 003 and Goal 004 tests still pass;
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

- Synthetic dry-run manifest function/module.
- Tests covering blocking and deterministic-summary behavior.
- Any small synthetic expected fixtures needed for review.
- Updated `docs/goals/005-synthetic-acquisition-manifest-dry-run/Log.md`.
- Final response to the orchestrator summarizing:
  - materials read;
  - files changed;
  - validation performed;
  - dry-run decisions/sources blocked versus represented synthetically;
  - recommended next goal;
  - blockers or questions;
  - final git status.

## Decision Authority

The executor may decide:

- exact function/module names;
- whether the summary is purely in-memory or compared against a tracked
  synthetic expected fixture;
- exact synthetic run ids and manifest field names;
- deterministic ordering for summary fields;
- test organization.

The executor must not decide:

- real ALA request parameters or API behavior;
- real primary camera-trap source location;
- real camera true-absence definitions;
- real license or sensitivity classifications;
- real focal species, grid, boundary, pseudoabsence, predictor, QA, or
  manuscript rules.

## Checkpoint Rules

Checkpoint in `Log.md`:

- start state;
- materials read;
- tests added and expected failing result;
- dry-run manifest implementation and fixture changes;
- validation command outputs;
- wake-up attempt result.

Stop and report if the goal appears to require real data, live services,
runtime artifact generation, or a Barry-level decision.
