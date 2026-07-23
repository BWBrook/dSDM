# Log: Goal 011 Authoritative ALA Resolution Closure

## 2026-07-23 - Start checkpoint

- Working directory: `/Users/bwbrook/papers/dSDM`.
- Branch: `main`; HEAD and `origin/main`:
  `c6c42f4881bc115d7e9259a10f0b4b1d30135840`.
- Status: `## main...origin/main`.
- Repo-local `AGENTS.md`: absent.
- Read Goal 008-010 packets, the authoritative bundle/register, Goal 010
  candidates/manifest/review, and current contracts/manifests/tests.
- No `data/`, `temp/`, occurrence, camera, or Goal 010 raw evidence paths were
  edited or used as implementation inputs.

## 2026-07-23 - Implementation checkpoints

- Test-first RED: the pre-transition focused suite failed on the absent
  candidate-reconciliation API, schema 1.1, resolved ALA intent, sole blocker,
  and structured policy assertions; legacy two-blocker expectations were then
  updated where they described the superseded state.
- Updated `config/phase1_decision_bundle.json` to schema 1.1 with the exact nine
  Goal 010 AFD concepts, the sole approved historical alias, structured ALA
  resolution/subtaxon scope, and P1-D008 as the only operational prerequisite.
- Updated `contracts.py` with fail-closed schema, order, unique HTTPS AFD ID,
  alias, policy, prerequisite, and Goal 010 candidate reconciliation checks.
- Updated `manifests.py` so mocked ALA intent is resolved and carries the nine
  deterministic queries, concept IDs, aliases, synonym/descendant scope,
  identity retention, assertion, and fallback; camera intent remains blocked.
- The readiness summary reports `ala_resolution_status: resolved`, global live
  status `blocked`, and exactly `P1-D008:camera_source_staging` as blocker.
- Updated the human register with P1-D003 closure, Goal 010 provenance, the
  species/subtaxon rule, and the sole P1-D008 operational prerequisite.
- Goal 010 evidence/candidates/review/code/raw responses remain untouched.
- Reconciliation result: 9/9 Goal 010 candidates, 9 unique concepts, and the
  one approved alias reconcile with the bundle; Goal 010 stored evidence
  validates offline with 9/9 recommendable candidates.
- Focused Phase 1 tests: 52/52; Goal 010 focused tests: 11/11; full suite:
  63/63. JSON parsing, compilation, and diff-check pass. No staging, commit,
  or push performed.

## 2026-07-23 - Focused repair pass

- Replaced shape-only AFD validation with an exact `species_id` to full URL
  mapping; added true two-way swap and unique forged UUID negatives, including
  mocked-request-builder rejection.
- Replaced child-ID prefixes with the three exact Vombatus child URLs and
  recorded the exact Macropus synonym/name concept ID. Mocked ALA intent now
  carries and validates the structured subtaxon/fallback plan; omission and
  wrong-ID mutations fail closed.
- Added a synthetic `ala_taxon_identity` block to the ALA fixture, required it
  for `ala_occurrence` rows, retained it in normalized summaries, and rejected
  malformed blocks or leakage into camera/pseudoabsence rows. Updated the
  directly affected fixture checksum.
- Repair verification: focused Phase 1 tests 56/56, Goal 010 tests 11/11,
  full discovery 67/67; JSON parsing, `py_compile`, and `git diff --check`
  pass. Goal 010 evidence and all forbidden payload surfaces remain untouched;
  no staging, commit, push, or live ALA call performed.

## 2026-07-23 - Identity-retention correction

- Relaxed the synthetic ALA identity validator so submitted, matched, and
  accepted source names/concept IDs are retained even when they differ from
  the canonical focal row name; accepted rank is fail-closed to `species` or
  `subspecies`.
- Updated the synthetic row to carry a distinct invented subspecies identity,
  refreshed its directly affected checksum, and added normalized-summary and
  invalid-rank tests. No real taxon or identifier was introduced.
