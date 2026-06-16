# Plan: Goal 001 Phase 0 Verification And Gate Review

## Intent

Turn the existing Phase 0 material into a defensible gate decision. The work is
successful if the supervisor can inspect one compact review file, the goal log,
the diff, and the validation outputs and then decide whether to recommend Barry
sign off Phase 0.

## Work Packages

### 1. Live State And Boundary Check

- Confirm `pwd`, branch, HEAD, and git status.
- Check for repo-local `AGENTS.md`.
- Confirm the work is occurring only in `/Users/bwbrook/papers/dSDM`.
- Record these facts in `Log.md`.

### 2. Evidence Surface Review

Read the required Phase 0 surface from `Goal.md`.

While reading, check specifically for:

- whether the Python-first rebuild direction is preserved
- whether Tasmanian mammals remain the Phase 1 proving-ground case
- whether SE Australian birds remain later scale-out
- whether old processed CSVs are clearly marked reference-only
- whether Phase 0 gate language still says Barry signoff is required
- whether any status snippets or inventory claims are stale relative to the live
  repo

### 3. Verification Ladder

Run the validation ladder in this order:

1. `python3 scripts/phase0_verify.py`
2. If stale generated Phase 0 evidence appears to be the cause of failure:
   `python3 scripts/phase0_inventory.py`
3. `python3 scripts/phase0_verify.py`
4. `make -C manuscript validate`
5. `make -C manuscript check`
6. `git status --short --ignored`
7. `git diff --check`
8. `git status --short --branch`

If the first verification passes, do not regenerate inventories merely for
cosmetic reasons. Use the review file to call out any non-blocking staleness
that remains.

### 4. Bounded Corrections

If needed, corrections may touch only:

- `docs/phase0/phase0_report.md`
- `docs/phase0/legacy_workflow_map.md`
- `docs/phase0/phase1_questions.md`
- `docs/plan/phase0_tactical_plan.md`
- `metadata/phase0/*.csv`
- `metadata/phase0/checksums.sha256`
- `scripts/phase0_inventory.py`
- `scripts/phase0_verify.py`
- this goal's `Log.md`
- `docs/phase0/phase0_gate_review.md`

Prefer generated regeneration for generated manifests. Prefer small manual
edits for review prose. Do not use this goal to tidy unrelated repo surfaces.

### 5. Gate Review

Create or update `docs/phase0/phase0_gate_review.md` with these sections:

- `# Phase 0 Gate Review`
- `## Audit Scope`
- `## Audited State`
- `## Materials Reviewed`
- `## Validation Results`
- `## Corrections Made`
- `## Gate Checklist`
- `## Remaining Risks Or Questions`
- `## Recommendation`

Use a concise recommendation label:

- `signoff-ready`
- `needs bounded follow-up`
- `blocked pending Barry decision`

The recommendation should follow the evidence. A passing validation ladder is
necessary for `signoff-ready`, but the review may still recommend bounded
follow-up if the evidence is confusing, stale, or too weak for supervisor
acceptance.

### 6. Final Reporting And Wake-Up

- Update `Log.md`.
- Send the required wake-up to the `dSDM` thread.
- Final response should include enough command evidence for the orchestrator to
  review without rerunning everything immediately.

## Quality Bar

This goal should make Phase 0 boringly reviewable. The best outcome is not a
large diff; it is a clean, compact decision surface with validation evidence,
honest limitations, and no accidental Phase 1 creep.
