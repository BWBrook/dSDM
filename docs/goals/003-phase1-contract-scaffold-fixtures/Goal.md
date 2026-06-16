# Goal 003: Phase 1 Contract Scaffold And Synthetic Fixtures

## Objective

Create the first Python-first Phase 1 contract scaffold for dSDM, with config,
schema, manifest, and synthetic-fixture validation that proves unresolved
scientific decisions block execution before any live data are touched.

## Why This Matters

Goal 002 produced the Phase 1 primary-data acquisition plan and decision
register. The safest first implementation step is not ALA acquisition or
camera-trap ingestion; it is a small contract scaffold that turns the plan into
testable boundaries. This gives later data-acquisition work a place to enforce
species, provenance, source, spatial, and decision-manifest rules without
choosing Barry-level science by accident.

## Operating Mode

Implementation sprint with synthetic fixtures only.

This goal may add Python package scaffolding, configuration examples, schemas,
fixtures, tests, and lightweight validation commands. It must not acquire,
process, or inspect live primary data.

## Review Surface

The supervisor should inspect:

- package/config/schema files added for the Phase 1 contract scaffold
- synthetic fixtures
- tests or validation scripts
- `docs/goals/003-phase1-contract-scaffold-fixtures/Log.md`
- final git diff
- validation command outputs
- final `git status --short --branch`

## Scope

In scope:

- Add a minimal Python package or module scaffold consistent with repo
  conventions.
- Add config or decision-manifest examples that encode unresolved decisions as
  explicit blocking values.
- Add schemas or validators for:
  - focal species contract
  - source manifests
  - row provenance
  - `pa_type` separation
  - decision manifests
  - output manifests
- Add small, tracked, clearly synthetic fixtures.
- Add tests or validation scripts proving:
  - unresolved required decisions fail fast
  - source provenance survives validation
  - true absence and pseudoabsence categories remain distinct
  - synthetic manifests carry checksums or equivalent audit metadata
  - no live data path is required
- Update project docs only where needed to explain the scaffold.
- Update this goal's `Log.md`.

Out of scope:

- Live ALA calls or internet queries.
- Primary camera-trap data access.
- Reading, copying, transforming, or processing legacy payloads under `temp/`
  or `data/`.
- Predictor extraction from real raster/vector payloads.
- Modelling, metric generation, maps, manuscript result changes, or figure
  production.
- Choosing focal species membership or whether to include
  `Thylogale billardierii`.
- Choosing ALA filters, camera true-absence rules, pseudoabsence rules, grid
  rules, offshore-island exclusions, fold rules, predictor authority, or QA
  tolerances.
- Remote/HPC jobs.
- Commits, pushes, pull requests, or staging.
- Broad migration of the repository from its existing scaffold.

## Read First

- `docs/plan/phase1_primary_data_plan.md` - implementation contract and
  recommended first implementation goal.
- `docs/plan/phase1_decision_register.md` - decision ids, owners, and blocking
  scientific choices.
- `docs/strategic_plan_30000ft.md` - Python-first rebuild direction.
- `README.md` - current repo overview.
- Existing top-level Python/R/package manifests visible from the root listing,
  to choose the smallest local scaffold that fits the repo.

Do not read `temp/` or `data/` for this goal unless a file is already a tracked
synthetic fixture created by this goal. The point is to scaffold contracts
without touching real or legacy payloads.

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
- HEAD: `56f1d9c`
- status: `## main...origin/main` plus this uncommitted Goal 003 packet

## Git And Publication Policy

- Do not commit.
- Do not push.
- Do not stage files.
- Treat the Goal 003 packet as an authorized uncommitted work surface.
- If unrelated dirty files appear, stop and report them before editing.
- Keep edits narrowly tied to this scaffold and fixture goal.

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
2. Inspect root-level manifests and existing package layout just enough to
   choose the minimal scaffold.
3. Read the Phase 1 plan and decision register.
4. Create a minimal Python contract scaffold. Prefer the smallest useful
   structure; do not overbuild.
5. Add synthetic fixture files exercising:
   - a tiny species contract with at least one unresolved decision
   - ALA-like source rows
   - camera-trap rows with true absence
   - pseudoabsence rows or candidate rows
   - source/input manifest metadata
   - decision manifest metadata
6. Add tests or validation commands proving the scaffold behavior.
7. Add or update concise docs only if needed to make the scaffold discoverable.
8. Run the validation ladder.
9. Update this goal's `Log.md`.
10. Send the wake-up to the `dSDM` orchestrator thread when complete or blocked.

## Validation Gates

This goal is complete only when:

- synthetic fixtures are small, tracked candidates and clearly synthetic
- validation fails when a required decision is unresolved for a stage that needs
  it
- validation passes for a stage whose required decisions are marked resolved in
  the synthetic decision manifest
- `pa_type` or equivalent fixture evidence distinguishes `presence`,
  `true_absence`, and `pseudoabsence`
- provenance/source identifiers survive validation
- tests or validation scripts run locally without live data
- `git diff --check` exits 0
- final `git status --short --branch` is reported

Run the narrowest meaningful test command the scaffold provides. If no test
runner exists yet, create one as part of the scaffold.

Do not run `python3 scripts/phase0_verify.py` for this goal unless the
orchestrator explicitly asks later. Phase 0 is a published snapshot, and this
goal intentionally adds post-Phase-0 files.

## Deliverables

- Minimal Python contract scaffold files.
- Synthetic fixtures.
- Tests or validation scripts.
- Any small docs needed to explain how to run the scaffold validation.
- Updated `docs/goals/003-phase1-contract-scaffold-fixtures/Log.md`.
- Final response to the orchestrator summarizing:
  - materials read
  - files changed
  - validation performed
  - what decisions are blocked versus represented synthetically
  - recommended next goal
  - blockers or questions
  - final git status

## Decision Authority

The executor may decide:

- exact Python module names and file layout
- fixture file format
- schema/validation implementation details
- test runner command
- names for synthetic species, rows, sites, grid cells, and manifests

The executor must not decide:

- real focal species membership
- `Thylogale billardierii` inclusion
- live ALA filters or accepted taxon aliases
- camera true-absence definitions
- pseudoabsence thresholds or thinning rules
- real grid, boundary, island, fold, or predictor authority
- QA acceptance tolerances for real data

## Checkpoint Rules

Checkpoint in `Log.md`:

- after starting-state checks
- after selecting scaffold layout
- after creating fixtures
- after adding validators/tests
- after running validation
- before final wake-up

## Pause Or Escalate

Pause and ask the orchestrator for direction if:

- the repo has unrelated dirty files at start
- package layout requires a larger repository migration than this goal allows
- a useful validator would require choosing a scientific rule
- a test would require reading real data
- dependencies would become heavy or unclear
- validation cannot be made meaningful without broad refactoring

## Stop Conditions

Stop when one of these is true:

- deliverables are produced and validation gates are satisfied
- a documented blocker prevents meaningful progress inside this scope
- the task would leave the agreed scope

## Wake-Up Requirement

When complete or blocked, send a short wake-up to the `dSDM` orchestrator
thread:

```text
Goal 003 is complete and ready for review.
```

or:

```text
Goal 003 is blocked and needs orchestrator direction.
```

Include a one-line pointer to your final response. If thread tools are not
available, use `tool_search` to expose `send_message_to_thread`; if that still
fails, report the exact limitation in your final response and in `Log.md`.

## Final Response Requirements

Report:

- branch and HEAD
- starting and final git status
- docs/materials read
- files changed
- validation commands and outcomes
- decisions represented as unresolved blockers
- recommended next goal
- blockers, uncertainties, or questions
- confirmation that no commits, pushes, staging, live ALA queries, real data
  access, data processing, modelling, remote jobs, cleanup, or broad refactors
  were performed
