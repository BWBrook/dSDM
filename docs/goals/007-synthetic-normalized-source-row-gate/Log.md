# Log: Goal 007 Synthetic Normalized Source-Row Gate

## 2026-06-18 - Goal Packet Created

- `dSDM` orchestrator created this self-contained action-repo goal packet for
  `quoll`.
- Goal 006 was accepted by `dSDM` and published before this packet:
  - commit: `6afed1b Add dSDM mocked acquisition request dry run`
  - branch: `main`
  - pushed to `origin/main`
  - status after push: `## main...origin/main`
- Goal intent: add a synthetic-only normalized source-row gate that validates
  existing mocked request and row-provenance gates and returns deterministic
  in-memory row-readiness summaries without live services, real paths,
  generated data outputs, raw-response transformation, spatial processing, or
  scientific/source decisions.
- No live ALA queries, real data access, data processing, modelling, Phase 1
  data acquisition, remote jobs, commits, pushes, staging, cleanup, or broad
  refactors were performed by the orchestrator while creating the packet.

## 2026-06-18 - quoll Start Checkpoint

- Working directory confirmed: `/Users/bwbrook/papers/dSDM`.
- Branch confirmed: `main`.
- HEAD confirmed: `6afed1b`.
- Start status:
  - `## main...origin/main`
  - `?? docs/goals/007-synthetic-normalized-source-row-gate/`
- Repo-local `AGENTS.md`: absent.
- No unrelated dirty files were present before Goal 007 edits.

## 2026-06-18 - Targeted Read Set

- Read the Goal 007 packet:
  - `Goal.md`
  - `Plan.md`
  - `Runbook.md`
  - `Log.md`
- Read Phase 1 planning and decision surfaces required by the runbook:
  - `docs/plan/phase1_primary_data_plan.md`
  - `docs/plan/phase1_decision_register.md`
- Read existing Phase 1 scaffold surfaces:
  - `src/dsdm_phase1/contracts.py`
  - `src/dsdm_phase1/manifests.py`
  - `src/dsdm_phase1/__init__.py`
  - `tests/test_phase1_contracts.py`
  - `tests/fixtures/phase1_synthetic/README.md`
  - existing synthetic decision, source, species, request, and row fixtures
    under `tests/fixtures/phase1_synthetic/`
- Implementation direction: add a small synthetic normalized source-row gate
  that reuses the Goal 006 mocked request builder and `validate_source_rows`,
  then returns deterministic in-memory row-readiness summary data. No live
  services, real payload paths, runtime outputs, raw-response transformation,
  spatial processing, source combination, or scientific/source decisions are
  required.

## 2026-06-18 - Test-First RED Check

- Added normalized source-row gate tests in `tests/test_phase1_contracts.py`
  for:
  - unresolved mocked request decisions blocking row summaries;
  - missing mocked request decisions blocking row summaries;
  - unsafe source contracts blocking row summaries;
  - missing source-row provenance blocking summaries;
  - invalid `pa_type` values blocking summaries;
  - missing `true_absence_rule_id` blocking true-absence rows;
  - missing `pseudoabsence_rule_id` blocking pseudoabsence rows;
  - valid synthetic rows producing deterministic summaries while preserving
    distinct presence, true-absence, and pseudoabsence categories.
- RED command:
  - `python3 tests/test_phase1_contracts.py`
- RED result:
  - 31 tests run.
  - 23 existing tests passed.
  - 8 new normalized row-gate tests errored as expected because
    `dsdm_phase1.build_normalized_source_row_gate_summary` was not yet
    implemented.

## 2026-06-18 - Implementation And Validation

- Added `build_normalized_source_row_gate_summary` in
  `src/dsdm_phase1/manifests.py`.
- Exported `build_normalized_source_row_gate_summary` from
  `src/dsdm_phase1/__init__.py`.
- The normalized row gate validates the Goal 006 mocked request inputs first,
  then validates synthetic rows with `validate_source_rows`, then returns
  deterministic in-memory row-readiness summary data.
- The summary includes run id, stage, status, mocked request status, decision
  manifest ids, row count, row ids, species ids, source names, source dataset
  ids/names, `pa_type` categories, sources grouped by `pa_type`, required
  provenance fields, true-absence rule ids, pseudoabsence rule ids, and compact
  per-row provenance summaries.
- True absences and pseudoabsences are reported separately. Synthetic
  `grid_cell_id` values are treated as opaque row metadata; no spatial
  processing is performed.
- The builder does not open source `local_path` payloads, write runtime
  outputs, call services, transform raw responses, combine sources, process
  data, or make scientific/source decisions.
- GREEN focused command:
  - `python3 tests/test_phase1_contracts.py`
- GREEN focused result:
  - 31 tests run, all passed.
- Validation ladder:
  - `python3 -m unittest discover -s tests -p 'test_*.py'`
    - 31 tests run, all passed.
  - `python3 tests/test_phase1_contracts.py`
    - 31 tests run, all passed.
  - `git diff --check`
    - exited 0 with no output.
  - `git status --short --branch`
    - `## main...origin/main`
    - ` M src/dsdm_phase1/__init__.py`
    - ` M src/dsdm_phase1/manifests.py`
    - ` M tests/test_phase1_contracts.py`
    - `?? docs/goals/007-synthetic-normalized-source-row-gate/`
- Wake-up result:
  - Sent to `dSDM` orchestrator thread
    `019eac00-8de8-7d02-890f-b007a4622911`.
