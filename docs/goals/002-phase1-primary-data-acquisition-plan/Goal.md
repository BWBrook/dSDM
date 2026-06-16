# Goal 002: Phase 1 Primary-Data Acquisition Plan

## Objective

Produce a detailed, evidence-backed Phase 1 tactical plan for rebuilding the
Tasmanian mammals primary-data acquisition pathway in Python, without acquiring
data or implementing the pipeline.

## Why This Matters

Phase 0 has been accepted and published as signoff-ready in commit `af037e1`.
The next decision is not to start coding immediately; it is to specify the
Phase 1 data contract well enough that a later implementation goal can acquire,
clean, version, and validate primary data without guessing at scientific or
provenance rules.

This plan should turn the Phase 0 questions into an executable implementation
roadmap while preserving all Barry-level scientific decisions as explicit
decision points.

## Operating Mode

Planning and design review.

This is not an implementation, data-acquisition, modelling, manuscript-results,
or remote-compute goal.

## Review Surface

The supervisor should inspect:

- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- this goal's `Log.md`
- the final git diff
- final `git status --short --branch`

## Scope

In scope:

- Translate accepted Phase 0 evidence into a detailed Phase 1 tactical plan.
- Define the intended Python-first data acquisition and provenance architecture.
- Specify required inputs, outputs, schemas, manifests, and acceptance gates.
- Identify minimum smoke-test fixtures and validation checks for later work.
- Review legacy R scripts only for intent and risk, not as implementation
  targets.
- Create a decision register separating executor-resolvable implementation
  details from Barry-level scientific choices.
- Recommend the first implementation goal that should follow this planning
  pass.
- Update this goal's `Log.md`.

Out of scope:

- Querying ALA or any external service.
- Reading new external documentation unless explicitly needed to name a
  decision or uncertainty; do not browse the internet for live ALA behavior in
  this goal.
- Acquiring, copying, converting, or processing primary data.
- Modifying legacy data payloads under `temp/` or `data/`.
- Implementing Python package code, tests, configs, CLI commands, or notebooks.
- Running modelling, metric generation, mapping, manuscript result updates, or
  remote/HPC jobs.
- Changing the focal species list or deciding whether to include
  `Thylogale billardierii`.
- Deciding final ALA filters, camera-trap interpretation rules, pseudoabsence
  rules, true-absence treatment, grid/boundary definitions, fold rules,
  predictor sources, or acceptance tolerances.
- Commits, pushes, pull requests, or staging.

## Read First

- `docs/phase0/phase0_gate_review.md` - accepted Phase 0 gate evidence and
  remaining signoff boundary.
- `docs/phase0/phase1_questions.md` - the primary source for Phase 1 planning
  questions.
- `docs/strategic_plan_30000ft.md` - Python-first rebuild strategy and phase
  sequence.
- `docs/phase0/phase0_report.md` - current evidence, inventory counts, missing
  pieces, and known risks.
- `docs/phase0/legacy_workflow_map.md` - old workflow intent map.
- `docs/plan/phase0_tactical_plan.md` - Phase 0 contract and gate discipline.
- `README.md` - project overview.

Legacy intent surface, read only as needed:

- `temp/src/0_galah_ALA.r`
- `temp/src/1_process_point_data.R`
- `temp/src/1a_tas_sdm_data_combine.r`
- `temp/src/2_tas_sdm_data_cv_split.r`
- `temp/src/3_create_sdm_data.R`
- `temp/src/sdm_data_func.R`
- `temp/src/z_execute.R`

Do not broaden legacy reading beyond what is needed to write the plan unless a
specific uncertainty requires it.

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
- HEAD: `af037e1`
- status: `## main...origin/main` plus this uncommitted Goal 002 packet

## Git And Publication Policy

- Do not commit.
- Do not push.
- Do not stage files.
- Treat the Goal 002 packet as an authorized uncommitted work surface.
- If unrelated dirty files appear, stop and report them before editing.
- Keep all edits narrowly tied to this planning goal.

## Data, Compute, And Staging Policy

- Work only in `/Users/bwbrook/papers/dSDM`.
- Do not read `/Users/bwbrook/chief_of_staff`.
- Do not read `/Users/bwbrook/work/goal_composer`.
- Do not read other project repositories.
- Use the local Mac checkout only.
- Do not use remote compute.
- Do not query external services.
- Do not create or modify primary data products.
- Do not regenerate Phase 0 inventories merely because this Goal 002 packet
  makes the old Phase 0 inventory no longer current. Phase 0 is a published
  signoff snapshot at `af037e1`.

## Required Work

1. Establish and log the live starting state.
2. Read the required Phase 0 and strategy surface.
3. Review the listed legacy intent surface only enough to extract Phase 1
   planning implications.
4. Create `docs/plan/phase1_primary_data_plan.md` with:
   - purpose and boundaries
   - Phase 1 assumptions inherited from Phase 0
   - proposed Python-first module/workflow structure at the design level
   - source-by-source data acquisition plan
   - required provenance columns and metadata
   - focal-species handling plan with unresolved `Thylogale billardierii`
     decision called out
   - ALA acquisition contract and unresolved filter choices
   - camera-trap ingestion/provenance contract and unresolved source-location
     question
   - grid, boundary, offshore-island, and coordinate-cleaning contract
   - true absence versus pseudoabsence policy questions
   - predictor-source and extraction planning requirements
   - manifests and reproducibility requirements
   - QA and acceptance gates for the later implementation goal
   - smoke-test fixture strategy
   - risks and stop rules
   - recommended sequence of implementation goals
5. Create `docs/plan/phase1_decision_register.md` with a table of decisions:
   - decision id
   - topic
   - why it matters
   - current evidence from Phase 0
   - options if known
   - recommendation if appropriate
   - who can decide (`executor`, `dSDM`, or `Barry`)
   - when it must be decided
6. Update this goal's `Log.md`.
7. Send a short wake-up to the `dSDM` orchestrator thread when complete or
   blocked.

## Validation Gates

This is planning validation. The goal is complete only when:

- `docs/plan/phase1_primary_data_plan.md` exists and is internally consistent.
- `docs/plan/phase1_decision_register.md` exists and clearly separates
  Barry-level scientific decisions from executor-level implementation choices.
- The plan does not require or imply that Phase 1 implementation has already
  happened.
- The plan preserves Tasmanian mammals as the first implementation target and
  SE Australia birds as later scale-out.
- The plan treats old processed CSVs as comparison/reference artifacts, not
  canonical rebuild inputs.
- The plan includes validation gates strong enough to support a later
  implementation goal.
- `git diff --check` exits 0.
- `git status --short --branch` is reported.

Do not run `python3 scripts/phase0_verify.py` for this goal unless the
orchestrator explicitly asks later. The new Goal 002 work surface is expected
to make the Phase 0 inventory snapshot no longer match the live worktree.

## Deliverables

- `docs/plan/phase1_primary_data_plan.md`
- `docs/plan/phase1_decision_register.md`
- Updated `docs/goals/002-phase1-primary-data-acquisition-plan/Log.md`
- Final response to the orchestrator summarizing:
  - materials read
  - files changed
  - validation performed
  - major decisions surfaced
  - recommended first implementation goal
  - blockers or questions
  - final git status

## Decision Authority

The executor may decide:

- document structure and terminology
- practical grouping of implementation work packages
- which legacy scripts are worth reading for planning intent
- executor-level implementation recommendations that do not settle scientific
  assumptions

The executor must leave for `dSDM` or Barry:

- authoritative Tasmanian mammal focal species membership
- inclusion or exclusion of `Thylogale billardierii`
- ALA filters, date bounds, data-resource filters, and QA criteria
- camera-trap primary dataset location and interpretation rules
- true absence versus pseudoabsence treatment
- grid, boundary, offshore-island, and fold rules where biology matters
- predictor-source authority and acceptance tolerances
- any choice that would materially affect scientific claims or manuscript
  interpretation

## Checkpoint Rules

Checkpoint in `Log.md`:

- after starting-state checks
- after reading the Phase 0 surface
- after reviewing legacy intent
- after drafting each deliverable
- before final wake-up

## Pause Or Escalate

Pause and ask the orchestrator for direction if:

- required Phase 0 files are missing
- the worktree has unrelated dirty files at start
- the plan cannot be written without choosing a scientific rule
- a useful plan would require live external service behavior or data access
- scope pressure starts to pull the work into implementation or data acquisition

## Stop Conditions

Stop when one of these is true:

- the deliverables are produced and validation gates are satisfied
- a documented blocker prevents meaningful progress inside this scope
- the task would leave the agreed scope

## Wake-Up Requirement

When complete or blocked, send a short wake-up to the `dSDM` orchestrator
thread:

```text
Goal 002 is complete and ready for review.
```

or:

```text
Goal 002 is blocked and needs orchestrator direction.
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
- validation performed
- major Barry-level decisions surfaced
- recommended first implementation goal
- blockers, uncertainties, or questions
- confirmation that no commits, pushes, staging, external data acquisition,
  data processing, modelling, remote jobs, cleanup, or broad refactors were
  performed
