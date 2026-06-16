# Plan: Goal 002 Phase 1 Primary-Data Acquisition Plan

## Intent

Make Phase 1 executable before it becomes code. The output should be a plan a
future implementation packet can hand to `quoll` without forcing it to infer
data provenance, scientific defaults, or acceptance gates from scattered Phase 0
notes.

## Work Packages

### 1. Live State And Boundary Check

- Confirm `pwd`, branch, HEAD, and git status.
- Confirm whether repo-local `AGENTS.md` exists.
- Confirm work remains inside `/Users/bwbrook/papers/dSDM`.
- Record the checks in `Log.md`.

### 2. Phase 0 Evidence Review

Read the Phase 0 gate review, Phase 1 questions, strategic plan, Phase 0
report, workflow map, Phase 0 tactical plan, and README.

Extract:

- accepted Phase 0 assumptions
- unresolved Phase 1 scientific decisions
- known missing artifacts
- legacy workflow steps that need a Python-first replacement
- validation gates that must survive into Phase 1

### 3. Legacy Intent Sampling

Read only the listed legacy scripts unless a specific planning gap requires one
more targeted file. The goal is to understand intent, not preserve old code
shape.

Focus on:

- ALA acquisition inputs and outputs
- point cleaning and coordinate assumptions
- Tas data combination
- fold construction
- predictor formatting
- helper functions and missing pieces
- orchestration assumptions

### 4. Draft The Phase 1 Plan

Create `docs/plan/phase1_primary_data_plan.md`.

Recommended structure:

- `# Phase 1 Primary-Data Acquisition Plan`
- `## Purpose`
- `## Boundaries`
- `## Inherited Phase 0 Decisions`
- `## Target Case Study`
- `## Proposed Python-First Workflow`
- `## Source Data Contracts`
- `## Focal Species Contract`
- `## ALA Acquisition Contract`
- `## Camera-Trap Ingestion Contract`
- `## Spatial Grid And Boundary Contract`
- `## Presence, True-Absence, And Pseudoabsence Contract`
- `## Predictor And Covariate Contract`
- `## Provenance And Manifest Requirements`
- `## QA And Acceptance Gates`
- `## Smoke-Test Fixture Strategy`
- `## Implementation Sequence`
- `## Risks And Stop Rules`
- `## Handoff To First Implementation Goal`

Write at a tactical level. Avoid false precision where Barry-level decisions
are still open.

### 5. Draft The Decision Register

Create `docs/plan/phase1_decision_register.md`.

Use a table with:

- id
- topic
- decision needed
- why it matters
- current evidence
- options
- recommended owner
- needed before
- notes

Owner values should be `executor`, `dSDM`, or `Barry`. Be strict: scientific
interpretation and material manuscript consequences belong to Barry.

### 6. Self-Review

Check the deliverables against the validation gates in `Goal.md`.

Run:

```sh
git diff --check
git status --short --branch
```

Do not run Phase 0 inventory verification for this goal unless directed later.

### 7. Final Reporting

- Update `Log.md`.
- Send the wake-up to `dSDM`.
- In the final response, make the recommended first implementation goal clear
  enough for the orchestrator to accept, revise, or send back.

## Quality Bar

This plan should be concrete enough to constrain implementation and honest
enough not to settle science by accident. A good result will make the next
implementation packet smaller, sharper, and less likely to burn time on
ambiguous data rules.
