# Phase 0 Gate Review

Date: 2026-06-15
Audited HEAD: `896da19`

## Audit Scope

This review covers the Phase 0 evidence surface for the dSDM rebuild. It checks
whether the existing Phase 0 docs, generated inventories, ignored payload
handling, and manuscript scaffold are current enough for a gate decision.

This review does not plan Phase 1, change scientific assumptions, acquire data,
run models, revise manuscript claims, or decide focal species, ALA filters,
pseudoabsence rules, true-absence treatment, grids, folds, predictors, or
acceptance tolerances.

## Audited State

- Working directory: `/Users/bwbrook/papers/dSDM`
- Branch: `main`
- HEAD: `896da19`
- Repo-local `AGENTS.md`: absent
- Starting status: `## main...origin/main` with `?? docs/goals/`
- Current Phase 0 strategy remains Python-first.
- Tasmanian mammals remain the Phase 1 proving-ground case.
- SE Australia birds remain later scale-out.
- Existing processed CSVs remain reference/comparison artifacts, not canonical
  rebuild substrates.
- Phase 0 remains open until automated verification passes and Barry signs off.

## Materials Reviewed

- `Goal.md`, `Plan.md`, `Runbook.md`, and `Log.md` for this goal packet
- `README.md`
- `docs/strategic_plan_30000ft.md`
- `docs/plan/phase0_tactical_plan.md`
- `docs/phase0/phase0_report.md`
- `docs/phase0/legacy_workflow_map.md`
- `docs/phase0/phase1_questions.md`
- `scripts/phase0_inventory.py`
- `scripts/phase0_verify.py`
- `manuscript/Makefile`

## Validation Results

| Check | Outcome | Notes |
| --- | --- | --- |
| `python3 scripts/phase0_verify.py` | Failed first run | `file_inventory.csv` was stale because it did not include the current `docs/goals/001-phase0-verification-gate-review/` packet files. |
| `python3 scripts/phase0_inventory.py` | Passed | Regenerated Phase 0 docs/manifests against the live repo; inventory increased from 89 to 93 files before this review file was added. |
| `python3 scripts/phase0_verify.py` | Passed | `PASS: Phase 0 inventories and docs verify against current repo state.` |
| `python3 scripts/phase0_inventory.py` | Passed | Re-ran after creating this required gate review so generated evidence includes the review file; inventory increased to 94 files. |
| `python3 scripts/phase0_verify.py` | Passed | Final verifier pass after the gate review was included in the inventory set. |
| Supervisor checksum review | Correction required | Independent review found checksum entries for `Log.md` and this gate review were stale after final prose/log edits, even though the verifier passed. |
| `python3 scripts/phase0_inventory.py` | Realigned in correction pass | This correction pass realigns generated checksum evidence after this note and the matching log note. No checksummed files should be edited afterward. |
| `make -C manuscript validate` | Passed | Build profile config validation passed for `draft` and `fixture`. |
| `make -C manuscript check` | Passed | Tool check, config validation, 57 tests, manuscript lint, reference audit, author metadata injection, DOCX build check, and build manifest write passed. |
| `git status --short --ignored` | Passed for review | Bulky/generated paths remain ignored: `data/`, `manuscript/build/`, `scripts/__pycache__/`, and `temp/`. `.DS_Store` is also ignored. |
| `git diff --check` | Passed with warning | Exit code 0. Git warned that `metadata/phase0/file_inventory.csv` CRLF line endings will be replaced by LF next time Git touches the file. |
| `git status --short --branch` | Passed for review | Branch remains `main...origin/main`; changes are bounded to Phase 0 evidence and the untracked goal packet. |

## Corrections Made

- Regenerated Phase 0 generated evidence after the first verifier showed stale
  file inventory state.
- Re-ran the inventory helper after creating this gate review so the required
  review file is represented in generated evidence.
- Supervisor review later found generated checksum evidence was stale after
  final prose/log edits; this correction pass adds that note and realigns the
  generated checksum evidence.
- Updated `docs/phase0/phase0_report.md` so inventory counts and the current git
  status excerpt match the live checkout.
- Updated `metadata/phase0/file_inventory.csv` so current tracked/untracked
  state and the goal packet files are represented.
- Updated `metadata/phase0/checksums.sha256` for changed and newly inventoried
  review-surface files.
- Created this gate review file.
- Updated `docs/goals/001-phase0-verification-gate-review/Log.md` with the
  execution record.

No scientific assumptions, Phase 1 questions, data acquisition logic, modelling
code, legacy payloads, dependency declarations, commits, pushes, or staging were
changed.

## Gate Checklist

- [x] Phase 0 manifests and docs exist.
- [x] `python3 scripts/phase0_verify.py` passes after bounded regeneration.
- [x] `make -C manuscript validate` passes.
- [x] `make -C manuscript check` passes.
- [x] Bulky payloads remain ignored.
- [x] Phase 0 evidence is clear enough for Barry signoff consideration.
- [ ] Barry has explicitly signed off Phase 0.

## Remaining Risks Or Questions

- Barry signoff is still required before detailed Phase 1 planning begins.
- Phase 1 scientific decisions remain intentionally unresolved and are captured
  as questions, not implementation plans.
- The goal packet remains untracked under `docs/goals/`, which is expected for
  this delegated task but visible in final git status.
- `git diff --check` reports a non-blocking CRLF normalization warning for
  `metadata/phase0/file_inventory.csv`.

## Recommendation

Recommendation: `signoff-ready`

Rationale: the verification ladder passes after bounded regeneration of stale
generated Phase 0 evidence, the manuscript scaffold validates, bulky payloads
remain ignored, and the Phase 0 docs preserve the intended gate discipline.
The remaining open items are signoff authority and later Phase 1 scientific
decisions, not blockers to presenting Phase 0 for Barry signoff.
