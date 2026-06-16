# Goal 001: Phase 0 Verification And Gate Review

## Objective

Produce a current, evidence-backed Phase 0 gate review for dSDM that lets the
`dSDM` orchestrator decide whether Phase 0 is signoff-ready, needs bounded
correction, or is blocked by a decision that must return to Barry.

## Why This Matters

dSDM is being relaunched as a Python-first rebuild. Phase 0 is meant to
preserve, inventory, and orient the project before any detailed Phase 1 primary
data acquisition plan begins. The repository already contains Phase 0 evidence,
but the gate is explicitly open until automated verification passes and Barry
signs off. This goal converts that open gate into a reviewable decision surface.

## Operating Mode

Review/audit with bounded correction authority.

This is not a Phase 1 planning goal and not a science or modelling goal.

## Review Surface

The supervisor should inspect:

- `docs/phase0/phase0_gate_review.md`
- this goal's `Log.md`
- the final git diff
- validation command outputs reported in the final response
- final `git status --short --branch` and `git status --short --ignored`

## Scope

In scope:

- Confirm the live repository branch, HEAD, and status.
- Confirm there is no repo-local `AGENTS.md`, or read it first if one has
  appeared.
- Read the compact Phase 0 planning and evidence surface listed below.
- Run the Phase 0 verification ladder.
- If Phase 0 manifests or docs are stale, make narrow corrections only within
  the Phase 0 evidence surface.
- Create or update `docs/phase0/phase0_gate_review.md` with a concise gate
  verdict and evidence table.
- Update this goal's `Log.md`.
- Report clearly whether Phase 0 appears signoff-ready, needs another bounded
  follow-up, or needs a Barry-level decision.

Out of scope:

- Detailed Phase 1 planning.
- ALA queries or any other external primary data acquisition.
- Camera-trap data intake, conversion, or interpretation.
- Modelling, metric generation, map generation, or manuscript result work.
- Changing the Tasmanian mammal focal species list.
- Deciding scientific rules for ALA filters, pseudoabsences, true absences,
  offshore islands, grids, folds, predictors, or acceptance tolerances.
- Cleaning, deleting, renaming, or moving legacy files outside the bounded
  Phase 0 correction surface.
- Broad refactors, dependency changes, environment migration, or remote/HPC
  execution.
- Commits, pushes, pull requests, or staging.

## Read First

- `README.md` - repo overview and current project shape.
- `docs/strategic_plan_30000ft.md` - Python-first rebuild strategy and phase
  discipline.
- `docs/plan/phase0_tactical_plan.md` - Phase 0 scope, tests, and gate rules.
- `docs/phase0/phase0_report.md` - current Phase 0 inventory report.
- `docs/phase0/legacy_workflow_map.md` - old-workflow intent map.
- `docs/phase0/phase1_questions.md` - questions for later Phase 1 planning,
  not a plan to execute now.
- `scripts/phase0_inventory.py` - inventory regeneration helper, to be used
  only if needed by the validation ladder.
- `scripts/phase0_verify.py` - Phase 0 verifier.
- `manuscript/Makefile` - manuscript scaffold validation targets.

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

## Git And Publication Policy

- Do not commit.
- Do not push.
- Do not stage files.
- Treat any pre-existing dirty state as project state and report it before
  making changes.
- If the worktree contains unrelated dirty files before this goal begins, do not
  alter them.
- Keep all edits narrowly tied to this goal.

## Data, Compute, And Staging Policy

- Work only in `/Users/bwbrook/papers/dSDM`.
- Do not read `/Users/bwbrook/chief_of_staff`.
- Do not read `/Users/bwbrook/work/goal_composer`.
- Do not read other project repositories.
- Use the local Mac checkout only.
- Do not use remote compute.
- Do not query external services.
- Do not create new data products.
- Keep bulky payloads under `temp/`, `data/`, and manuscript build outputs
  ignored.

## Required Work

1. Establish and log the live starting state.
2. Read the required Phase 0 surface.
3. Run:

   ```sh
   python3 scripts/phase0_verify.py
   ```

4. If verification fails because Phase 0 inventories or reports are stale,
   regenerate once:

   ```sh
   python3 scripts/phase0_inventory.py
   python3 scripts/phase0_verify.py
   ```

   After one regeneration, stop and escalate if verification still fails.

5. Run:

   ```sh
   make -C manuscript validate
   make -C manuscript check
   git status --short --ignored
   git diff --check
   git status --short --branch
   ```

6. Inspect whether the Phase 0 report, inventories, and manifest evidence match
   the live repository state well enough for a gate decision.
7. Create or update `docs/phase0/phase0_gate_review.md` with:

   - date and audited HEAD
   - commands run and pass/fail status
   - files changed by this goal
   - current gate checklist
   - any stale evidence corrected
   - remaining blockers or uncertainties
   - recommendation: `signoff-ready`, `needs bounded follow-up`, or
     `blocked pending Barry decision`

8. Update this goal's `Log.md` with a brief chronological record.
9. Send a short wake-up to the `dSDM` orchestrator thread when complete or
   blocked.

## Validation Gates

This goal is complete only when one of these is true:

- `python3 scripts/phase0_verify.py`, `make -C manuscript validate`,
  `make -C manuscript check`, and `git diff --check` pass, the gate review has
  been written, and final repo status has been reported.
- A blocker is reached within the stop rules and documented with exact command
  output, affected files, and the next decision needed.

This is evidence-packaging validation. It verifies whether Phase 0 evidence is
current and reviewable; it does not validate Phase 1 scientific choices.

## Deliverables

- `docs/phase0/phase0_gate_review.md`
- Updated `docs/goals/001-phase0-verification-gate-review/Log.md`
- Final response to the orchestrator summarizing:
  - materials read
  - validation commands and outcomes
  - files changed
  - final git status
  - gate recommendation
  - blockers or questions

## Decision Authority

The executor may decide:

- how to phrase the gate review, provided claims are evidence-backed
- whether stale generated Phase 0 inventory outputs need one regeneration
- narrow wording fixes in Phase 0 docs when needed to reflect current evidence
- narrow verifier/inventory fixes only if the existing scripts are plainly
  inconsistent with the stated Phase 0 contract

The executor must pause before:

- changing scientific assumptions or species membership
- making a detailed Phase 1 plan
- changing data acquisition, modelling, or manuscript conclusions
- adding dependencies
- deleting or moving legacy artifacts
- running external services or remote/HPC jobs
- committing, pushing, staging, or opening a PR

## Checkpoint Rules

Checkpoint in `Log.md`:

- after starting-state checks
- after the first Phase 0 verification run
- after any regeneration or bounded correction
- after manuscript validation
- before final wake-up

## Pause Or Escalate

Pause and ask the orchestrator for direction if:

- `python3 scripts/phase0_verify.py` still fails after one regeneration
- required ignored payloads are missing
- manuscript validation fails for reasons beyond scaffold/config hygiene
- a fix would require scientific interpretation
- a fix would require changing Phase 1 questions into a Phase 1 plan
- external data, remote compute, or user credentials would be needed
- scope pressure starts to pull the work into cleanup or new implementation

## Stop Conditions

Stop when one of these is true:

- the validation gates pass and deliverables are produced
- a documented blocker prevents meaningful progress inside this scope
- the task would leave the agreed scope

## Wake-Up Requirement

When complete or blocked, send a short wake-up to the `dSDM` orchestrator
thread:

```text
Goal 001 is complete and ready for review.
```

or:

```text
Goal 001 is blocked and needs orchestrator direction.
```

Include a one-line pointer to your final response. If thread tools are not
available, use `tool_search` to expose `send_message_to_thread`; if that still
fails, report the exact limitation in your final response and in `Log.md`.

## Final Response Requirements

Report:

- audited branch and HEAD
- starting and final git status
- docs/materials read
- commands run and pass/fail outcomes
- files changed
- gate recommendation and rationale
- blockers, uncertainties, or questions
- confirmation that no commits, pushes, staging, external data acquisition,
  modelling, Phase 1 planning, remote jobs, cleanup, or broad refactors were
  performed
