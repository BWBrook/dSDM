# Goal 004: Source Contract Gate And Decision Manifest Hardening

## Objective

Extend the Phase 1 Python contract scaffold so the `source_contracts` stage has
explicit decision-manifest and source-manifest gates for ALA versioning,
primary camera-source authority, and camera true-absence interpretation, using
synthetic fixtures only.

## Why This Matters

Goal 003 proved that unresolved species decisions can block execution before
live data are touched. The next risk boundary is source acquisition: live ALA
queries and camera-trap ingestion must not start until source provenance,
versioning, authoritative source location, and true-absence interpretation are
decisioned.

This goal should make that boundary executable without choosing the science.

## Operating Mode

Implementation sprint with synthetic fixtures only.

This goal may add or modify Python validators, synthetic fixture manifests,
tests, and this goal's log. It must not acquire, inspect, copy, transform, or
process live or legacy primary data.

## Review Surface

The supervisor should inspect:

- source-contract validator changes
- decision-manifest handling for `source_contracts`
- synthetic source-contract fixtures
- test coverage for `P1-D007`, `P1-D008`, and `P1-D009`
- `docs/goals/004-source-contract-gate-decision-manifest-hardening/Log.md`
- final git diff
- validation command outputs
- final `git status --short --branch`

## Scope

In scope:

- Extend the existing standard-library Python scaffold under `src/dsdm_phase1/`.
- Extend or add synthetic fixtures under `tests/fixtures/phase1_synthetic/`.
- Add tests proving:
  - `source_contracts` fails when `P1-D007`, `P1-D008`, or `P1-D009` are
    missing or unresolved;
  - a synthetic-only resolved decision manifest can pass the `source_contracts`
    stage;
  - source contracts preserve source ids, source types, decision references,
    versioning or authority metadata, license/sensitivity placeholders, and
    safe path/checksum expectations;
  - unsafe paths, missing checksum metadata, or missing provenance fields fail
    before any live data path is needed.
- Keep existing Goal 003 tests passing.
- Update this goal's `Log.md`.

Out of scope:

- Live ALA calls, internet queries, or request construction against ALA.
- Primary camera-trap data access.
- Reading, copying, transforming, or processing payloads under `temp/` or
  `data/`.
- Deciding the real primary camera-trap dataset location.
- Deciding camera true-absence rules, effort thresholds, or survey semantics.
- Choosing ALA names, aliases, date bounds, data-resource filters, quality
  filters, or accepted taxon metadata.
- Choosing real grid, boundary, offshore-island, fold, predictor, QA, or
  manuscript rules.
- Modelling, metrics, maps, manuscript result changes, or figure production.
- Remote/HPC jobs.
- Commits, pushes, pull requests, or staging.
- Broad repository migration or cleanup.

## Read First

- `docs/goals/004-source-contract-gate-decision-manifest-hardening/Goal.md`
- `docs/goals/004-source-contract-gate-decision-manifest-hardening/Plan.md`
- `docs/goals/004-source-contract-gate-decision-manifest-hardening/Runbook.md`
- `docs/goals/004-source-contract-gate-decision-manifest-hardening/Log.md`
- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- `src/dsdm_phase1/contracts.py`
- `tests/test_phase1_contracts.py`
- `tests/fixtures/phase1_synthetic/README.md`

Do not read `temp/` or `data/`. Do not inspect legacy payloads to infer real
source paths or rules.

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
- HEAD: `66db1f9`
- status: `## main...origin/main` plus this uncommitted Goal 004 packet

## Git And Publication Policy

- Do not commit.
- Do not push.
- Do not stage files.
- Treat the Goal 004 packet as an authorized uncommitted work surface.
- If unrelated dirty files appear, stop and report them before editing.
- Keep edits narrowly tied to this source-contract gate.

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
2. Read the required surface and only the relevant decision-register entries.
3. Add tests first for `source_contracts` decision gating and source-contract
   validation behavior.
4. Verify the new tests fail for the missing behavior.
5. Implement the smallest useful validator changes.
6. Add small synthetic fixtures for:
   - unresolved source-contract decisions;
   - synthetic resolved `P1-D007`, `P1-D008`, and `P1-D009` decisions;
   - ALA-like source-contract metadata;
   - camera-trap source-contract metadata;
   - unsafe or incomplete source-contract examples used only for negative
     tests.
7. Run the validation ladder.
8. Update this goal's `Log.md`.
9. Send the wake-up to the `dSDM` orchestrator thread when complete or blocked.

## Validation Gates

This goal is complete only when:

- `source_contracts` fails if `P1-D007`, `P1-D008`, or `P1-D009` are missing or
  unresolved;
- `source_contracts` passes for a synthetic-only decision manifest where those
  ids are resolved with fake values;
- source-contract fixtures are small, tracked candidates and clearly
  synthetic;
- source-contract validation rejects unsafe paths and missing provenance or
  audit metadata;
- existing Goal 003 tests still pass;
- tests run locally without live data;
- `git diff --check` exits 0;
- final `git status --short --branch` is reported.

Run at least:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
git diff --check
git status --short --branch
```

Do not run:

```sh
python3 scripts/phase0_verify.py
```

unless the orchestrator specifically directs it later.

## Deliverables

- Validator changes for the source-contract gate.
- Synthetic source-contract fixtures.
- Tests covering the new source-contract decision and manifest behavior.
- Updated `docs/goals/004-source-contract-gate-decision-manifest-hardening/Log.md`.
- Final response to the orchestrator summarizing:
  - materials read;
  - files changed;
  - validation performed;
  - source decisions blocked versus represented synthetically;
  - recommended next goal;
  - blockers or questions;
  - final git status.

## Decision Authority

The executor may decide:

- exact validator function names and fixture file names;
- JSON structure for synthetic source contracts;
- implementation details for safe relative path checks and checksum metadata;
- test organization;
- names for synthetic source ids, run ids, sites, files, and manifests.

The executor must not decide:

- real primary camera-trap dataset location;
- real camera true-absence definitions;
- real ALA filters, dates, names, aliases, or data-resource choices;
- real file paths for primary data;
- real license or sensitivity classifications;
- real grid, boundary, pseudoabsence, predictor, QA, or manuscript rules.

## Checkpoint Rules

Checkpoint in `Log.md`:

- start state;
- materials read;
- tests added and their expected failing result;
- validator and fixture changes;
- validation command outputs;
- wake-up attempt result.

Stop and report if the goal appears to require real data, live services, or a
Barry-level decision.
