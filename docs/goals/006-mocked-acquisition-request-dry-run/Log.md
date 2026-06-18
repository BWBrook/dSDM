# Log: Goal 006 Mocked Acquisition-Request Dry Run

## 2026-06-18 - Goal Packet Created

- `dSDM` orchestrator created this self-contained action-repo goal packet for
  `quoll`.
- Goal 005 was accepted by `dSDM` and published before this packet:
  - commit: `427a491 Add dSDM synthetic acquisition dry run`
  - branch: `main`
  - pushed to `origin/main`
  - status after push: `## main...origin/main`
- Goal intent: add a synthetic-only mocked acquisition-request layer that
  validates existing species/source/dry-run gates and returns deterministic
  request-manifest records without live services, real paths, generated data
  outputs, or scientific/source decisions.
- No live ALA queries, real data access, data processing, modelling, Phase 1
  data acquisition, remote jobs, commits, pushes, staging, cleanup, or broad
  refactors were performed by the orchestrator while creating the packet.

## 2026-06-18 - quoll Start Checkpoint

- Working directory confirmed: `/Users/bwbrook/papers/dSDM`.
- Branch confirmed: `main`.
- HEAD confirmed: `427a491`.
- Start status:
  - `## main...origin/main`
  - `?? docs/goals/006-mocked-acquisition-request-dry-run/`
- Repo-local `AGENTS.md`: absent.
- No unrelated dirty files were present before Goal 006 edits.

## 2026-06-18 - Targeted Read Set

- Read the Goal 006 packet:
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
  - existing synthetic JSON fixtures under `tests/fixtures/phase1_synthetic/`
- Implementation direction: extend the synthetic manifest surface with a
  mocked request-manifest builder that reuses the Goal 005 dry-run summary and
  validates synthetic request decisions for ALA and camera intent. No live ALA
  calls, real source paths, runtime outputs, data processing, or scientific
  decisions are required.

## 2026-06-18 - Test-First RED Check

- Added synthetic request-decision fixtures:
  - `decision_manifest_request_resolved.json`
  - `decision_manifest_request_ala_unresolved.json`
  - `decision_manifest_request_camera_unresolved.json`
- Added mocked request-manifest tests in `tests/test_phase1_contracts.py` for:
  - unresolved ALA request decisions blocking request records;
  - missing ALA request decisions blocking request records;
  - unresolved camera request decisions blocking request records;
  - missing camera request decisions blocking request records;
  - unsafe source contracts blocking request records;
  - valid synthetic inputs producing deterministic request-manifest records
    without requiring synthetic source files to exist.
- RED command:
  - `python3 tests/test_phase1_contracts.py`
- RED result:
  - 23 tests run.
  - 17 existing tests passed.
  - 6 new mocked request tests errored as expected because
    `dsdm_phase1.build_mocked_acquisition_request_manifest` was not yet
    implemented.

## 2026-06-18 - Implementation And Validation

- Extended `src/dsdm_phase1/contracts.py` with the
  `mocked_acquisition_requests` decision stage requiring:
  - `P1-D003`
  - `P1-D004`
  - `P1-D005`
  - `P1-D006`
  - `P1-D007`
  - `P1-D008`
  - `P1-D009`
  - `P1-D010`
- Added `build_mocked_acquisition_request_manifest` in
  `src/dsdm_phase1/manifests.py`.
- Exported `build_mocked_acquisition_request_manifest` from
  `src/dsdm_phase1/__init__.py`.
- The mocked request builder validates the Goal 005 dry-run inputs first, then
  validates synthetic request decisions, then returns deterministic in-memory
  request records for:
  - synthetic ALA occurrence request intent;
  - synthetic camera-trap ingest request intent.
- Each mocked request record is explicitly marked `not_executed` and carries
  source contract id, source type, required decision references, checksum
  metadata, license placeholder, sensitivity placeholder, and fake intent
  policy ids. The builder does not open source `local_path` payloads, write
  runtime outputs, call services, process data, or make scientific/source
  decisions.
- GREEN focused command:
  - `python3 tests/test_phase1_contracts.py`
- GREEN focused result:
  - 23 tests run, all passed.
- Validation ladder:
  - `python3 -m unittest discover -s tests -p 'test_*.py'`
    - 23 tests run, all passed.
  - `python3 tests/test_phase1_contracts.py`
    - 23 tests run, all passed.
  - `git diff --check`
    - exited 0 with no output.
  - `git status --short --branch`
    - `## main...origin/main`
    - ` M src/dsdm_phase1/__init__.py`
    - ` M src/dsdm_phase1/contracts.py`
    - ` M src/dsdm_phase1/manifests.py`
    - ` M tests/test_phase1_contracts.py`
    - `?? docs/goals/006-mocked-acquisition-request-dry-run/`
    - `?? tests/fixtures/phase1_synthetic/decision_manifest_request_ala_unresolved.json`
    - `?? tests/fixtures/phase1_synthetic/decision_manifest_request_camera_unresolved.json`
    - `?? tests/fixtures/phase1_synthetic/decision_manifest_request_resolved.json`
- Wake-up result:
  - Sent to `dSDM` orchestrator thread
    `019eac00-8de8-7d02-890f-b007a4622911`.
