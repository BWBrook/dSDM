# Log: Goal 002 Phase 1 Primary-Data Acquisition Plan

## 2026-06-16 - Goal Packet Created

- `dSDM` orchestrator created this self-contained action-repo goal packet for
  `quoll`.
- Phase 0 was accepted by `dSDM` and published before this packet:
  - commit: `af037e1 Record dSDM Phase 0 gate review`
  - branch: `main`
  - pushed to `origin/main`
  - status after push: `## main...origin/main`
- Goal intent: produce a detailed Phase 1 primary-data acquisition plan and
  decision register for the Tasmanian mammals rebuild, without acquiring data
  or implementing the pipeline.
- No data acquisition, data processing, modelling, Phase 1 implementation,
  remote jobs, commits, pushes, staging, cleanup, or broad refactors were
  performed by the orchestrator while creating the packet.

## 2026-06-16 - quoll started execution

- Required goal packet read first: `Goal.md`, `Plan.md`, `Runbook.md`, and
  `Log.md`.
- Starting checks:
  - `pwd`: `/Users/bwbrook/papers/dSDM`
  - branch: `main`
  - HEAD: `af037e1`
  - `git status --short --branch`: `## main...origin/main` plus
    `?? docs/goals/002-phase1-primary-data-acquisition-plan/`
  - repo-local `AGENTS.md`: absent
- Boundary noted: planning/design only; no external ALA queries, data
  acquisition, data processing, modelling, manuscript result work, remote/HPC
  jobs, cleanup, commits, pushes, staging, broad refactors, or Phase 0 verifier
  runs are authorized.

## 2026-06-16 - Phase 0 and strategy surface read

- Read:
  - `docs/phase0/phase0_gate_review.md`
  - `docs/phase0/phase1_questions.md`
  - `docs/strategic_plan_30000ft.md`
  - `docs/phase0/phase0_report.md`
  - `docs/phase0/legacy_workflow_map.md`
  - `docs/plan/phase0_tactical_plan.md`
  - `README.md`
- Planning implications extracted:
  - Phase 1 should be Python-first and rebuild primary data rather than
    converting old processed CSVs into canonical inputs.
  - Tasmanian mammals are the first implementation target; SE Australia birds
    remain later scale-out.
  - Old processed CSVs, spatial payloads, and R scripts are reference and
    comparison artifacts only.
  - Barry-level decisions remain open for species membership, ALA filters,
    camera-trap interpretation, true absence versus pseudoabsence treatment,
    spatial rules, predictor authority, and acceptance tolerances.
  - Phase 1 needs strong manifests, provenance columns, smoke fixtures, and QA
    gates before modelling or manuscript-result work.

## 2026-06-16 - Legacy intent surface reviewed

- Read the listed legacy intent files:
  - `temp/src/0_galah_ALA.r`
  - `temp/src/1_process_point_data.R`
  - `temp/src/1a_tas_sdm_data_combine.r`
  - `temp/src/2_tas_sdm_data_cv_split.r`
  - `temp/src/3_create_sdm_data.R`
  - `temp/src/sdm_data_func.R`
  - `temp/src/z_execute.R`
- Also read the bounded helper-definition block in `temp/src/sdm_data_func.R`
  covering pseudoabsence construction, grid snapping, human-activity thinning,
  spatial thinning, and predictor transformation.
- Planning implications extracted:
  - Legacy scripts define useful flow and parameter clues, but rely on
    hard-coded Windows paths, manual one-species loops, interactive plotting,
    and unversioned/live ALA access.
  - The old Tas species vector includes `Thylogale billardierii`, while Phase 0
    notes that the old species list CSV omitted it; this must stay a
    Barry-level decision.
  - Camera-trap true absences must remain distinguishable from ALA-derived
    pseudoabsences throughout Phase 1.
  - Spatial choices needing decisions include the canonical grid, offshore
    island exclusions, fold selection, thinning distances, and predictor stack.
  - Predictor extraction must persist scaler parameters and categorical levels
    to prevent train/test leakage and schema drift.

## 2026-06-16 - Phase 1 plan drafted

- Created `docs/plan/phase1_primary_data_plan.md`.
- The plan covers purpose, boundaries, inherited Phase 0 assumptions,
  Python-first workflow design, source data contracts, focal species handling,
  ALA and camera-trap contracts, spatial and pseudoabsence contracts, predictor
  requirements, provenance/manifests, QA gates, smoke fixtures, risks, and
  recommended implementation sequencing.
- Scientific decisions are left as explicit stop points rather than defaults.

## 2026-06-16 - Decision register drafted

- Created `docs/plan/phase1_decision_register.md`.
- The register separates executor, `dSDM`, and Barry decision authority.
- Major Barry-level decisions include species membership, `Thylogale
  billardierii`, ALA filters, camera true-absence rules, pseudoabsence rules,
  grid/boundary/island rules, fold policy, predictor authority, and acceptance
  tolerances.

## 2026-06-16 - Self-review and allowed validation

- Self-reviewed `docs/plan/phase1_primary_data_plan.md` against the Goal 002
  validation gates:
  - keeps Tasmanian mammals first;
  - keeps SE Australia birds later;
  - treats old processed CSVs as comparison/reference artifacts only;
  - preserves Barry-level decisions as explicit stop points;
  - includes provenance, manifests, QA gates, smoke fixtures, and a recommended
    first implementation goal.
- Self-reviewed `docs/plan/phase1_decision_register.md`:
  - includes 30 decision rows;
  - uses owner values `executor`, `dSDM`, and `Barry`;
  - separates implementation choices from scientific or manuscript-material
    choices.
- Ran `git diff --check`.
- Outcome: passed with no output.
- Ran `git status --short --branch`.
- Outcome:
  - `## main...origin/main`
  - `?? docs/goals/002-phase1-primary-data-acquisition-plan/`
  - `?? docs/plan/phase1_decision_register.md`
  - `?? docs/plan/phase1_primary_data_plan.md`
- Confirmed `python3 scripts/phase0_verify.py` was not run for Goal 002.
- No external ALA queries, data acquisition, data processing, modelling,
  manuscript result work, remote/HPC jobs, cleanup, commits, pushes, staging,
  or broad refactors were performed.
- Wake-up to `dSDM` orchestrator thread is next.

## 2026-06-16 - Orchestrator wake-up sent

- Sent wake-up to `dSDM` orchestrator thread
  `019eac00-8de8-7d02-890f-b007a4622911`.
- Wake-up message:
  `Goal 002 is complete and ready for review. Final response in quoll has the planning summary and decision-register highlights.`
- Thread tool result: success for thread
  `019eac00-8de8-7d02-890f-b007a4622911`.
