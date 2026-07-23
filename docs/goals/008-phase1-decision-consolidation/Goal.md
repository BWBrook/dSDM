# Goal 008: Phase 1 Decision Consolidation and Executable Contract

## Objective

Materialise the agreed Phase 1 scientific and operational decisions as one
authoritative, versioned, machine-readable decision bundle, align the human
decision register, and add a small standard-library validator that fails closed
on missing or contradictory contract values.

## Scope

- Add `config/phase1_decision_bundle.json` as the sole tracked decision source.
- Add focused validation in `src/dsdm_phase1/contracts.py` and exports as needed.
- Add tests in `tests/test_phase1_contracts.py` for schema, invariants, privacy,
  deterministic readiness, and fail-closed behaviour.
- Update `docs/plan/phase1_decision_register.md` so all P1-D001--P1-D030 rows
  agree with the bundle and operational prerequisites remain visibly separate.
- Keep this packet current at meaningful checkpoints.

## Non-goals and boundaries

No live ALA or camera access, data/temp reads, payload processing, predictor
extraction, spatial work, modelling, maps, metrics, manuscript edits, remote
compute, dependency changes, commits, staging, pushes, or publication.

The bundle must not contain exact camera paths, camera coordinates/site IDs,
active deployment metadata, raw records, secrets, guessed ALA concept IDs, or
unverified aliases. Exact ALA taxon resolution and Barry's authoritative camera
source staging/path are explicit prerequisites that block live acquisition.

## Validation and publication boundary

The accepted bundle validates deterministically in memory. The readiness
summary must report policy consolidation complete while reporting live
acquisition blocked by the two explicit operational prerequisites. Validation
reads only the tracked bundle; it never opens source payloads or paths under
`data/` or `temp/`. The orchestrator owns acceptance, staging, commit, push,
and publication.

## Acceptance criteria

- Every P1-D001--P1-D030 appears exactly once.
- Nine species, Thylogale handling, temporal/quality, source, spatial,
  pseudoabsence, predictor, QA, fixture, privacy, and legacy-role policies are
  structurally represented and cross-checked.
- Missing or duplicate decisions and material contradictions raise
  `ValidationError`.
- Focused tests and the existing 31-test suite pass; no live services or data
  are accessed.
