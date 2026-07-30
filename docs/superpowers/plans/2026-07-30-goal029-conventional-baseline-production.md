# Goal029 Conventional Baseline Production Implementation Plan

**Goal:** Produce a resumable, leakage-safe conventional baseline panel and
seal selected refits without using the real outer assessment.

**Architecture:** Extend the existing inner-CV API only where multi-seed
production requires it. Keep Goal029 planning, checkpoints, reduction,
challenge construction, validation, and publication in a dedicated module.
Use actual Goal028 adapters and private-ingestion authorities.

## Task 1: Freeze and test the exact plan

- Add `config/conventional_baseline_production.json`.
- Add `tests/test_goal029_production.py` plan assertions.
- Assert ordered species/endpoints/families/candidates/seeds and exact counts.
- Assert the 30 calibration leaves are a unique subset with declared coverage.

## Task 2: Add multi-seed leaf support

- Extend `inner_cv.py` to accept canonical ordered seed subsets.
- Preserve fit reports for warning classification.
- Generalise selected refit provenance to the task's canonical seed.
- Run Goal028/inner-CV regressions after every shared change.

## Task 3: Implement provenance and membership bundles

- Compute a digest of runtime-critical paths and exact bindings.
- Materialise six separate species × endpoint × split membership records:
  five fold-specific `E_v` records plus the outer-training refit record.
- Bind every leaf to config, lock, runtime, host, upstream, membership,
  subset, and encoder digests.
- Test path/source/runtime/host/encoder tampering.

## Task 4: Implement atomic leaf checkpoints

- Serialize a complete leaf into canonical metadata plus private OOF data.
- Write to a temporary sibling, validate, fsync, and atomically rename.
- Resume only an exact identity; reject stale or malformed checkpoints.
- Replace invalid candidates with blinded failures for reduction/publication.

## Task 5: Implement reduction and validity policy

- Merge required seed leaves by exact RowKey/fold/label evidence.
- Recompute averaged scores, fold AUC, OOF threshold, and fold TSS.
- Enforce null, anchor, and two-candidate quorum.
- Select by the frozen AUC/TSS/candidate-ID rule.
- Abort rather than use a runner-up after selected refit failure.

## Task 6: Implement selected refits and challenges

- Refit every selected candidate seed on permitted outer-training rows.
- Build exactly `min(32, n_unique_eligible)` deterministic observed-support
  feature vectors without row IDs or responses.
- Serialize model and challenge; record and replay prediction digests.
- Assert real outer attempted/open counts remain `0/0`.

## Task 7: Implement validation and source audit

- Recompute the complete artefact contract without fitting.
- Require exact private and tracked staged-file inventories.
- Select one source-audit leaf per family stratum by manifest hash.
- Add missing candidate/seed coverage and fill to exactly
  `ceil(0.05 * 7168) = 359`.
- Complete full staged artefact validation first.
- Rerun the deterministic audit set in a fresh cache-disabled process and
  destination, reconcile every valid result and invalid failure, then validate
  the complete staged trees again.

## Task 8: Implement paired transaction publication

- Build private/tracked core manifests and counterpart digests.
- Publish only after both validation gates pass.
- Restore both complete stage trees on rename/marker failure; preserve intact
  destinations and fail loudly if restoration itself is impossible.
- Write a final tracked marker last.
- Reject partial, mismatched, symlinked, existing, or unmarked pairs.

## Task 9: Synthetic and regression gates

- Run focused Goal029 tests and synthetic end-to-end.
- Run Goal028 shared-module regressions.
- Run full tests once, compile, lock check, and `git diff --check`.
- Record exact commands and outcomes in the Goal029 log.

## Task 10: Calibration and production

- Stop after synthetic readiness unless the orchestrator authorises real
  calibration.
- Calibrate the exact 30 leaves at workers 1, 2, and 4 within memory policy.
- Select one canonical host/worker setting.
- Execute/resume the full real plan, validate, publish, and stop before outer
  use.
