# Log

## 2026-07-30 — Goal contract and implementation start

- Barry authorised Goal029 after accepting the Goal028 foundation.
- Frozen scope: eight species, seven endpoints, six conventional families,
  all 36 registered candidates, five inner folds, and family-specific seeds.
- Exact arithmetic: 336 family strata, 2,016 candidate strata, 7,168
  candidate-seed leaves, 35,840 OOF-producing fold units, 44,240 actual inner
  estimator fits after ANN discovery/replay, and at most 1,008 refits.
- Corrected conservative anchors are `enet00`, `gam01`, `rf02`, `hgb04`, and
  `ann01`; the Goal028 representative IDs were coverage choices, not anchors.
- Real outer use, residual MLP, community/dSDM machinery, interpretation,
  mapping, sensitivity work, and birds remain outside this goal.
- Implementation is proceeding through code, tests, and synthetic gates
  before any real calibration or production command.

## 2026-07-30 — Implementation tranche ready for review

- Added the exact production plan/configuration, multi-seed inner-CV support,
  content-addressed leaf checkpoints and selected bundles, family-level
  failure/quorum reduction, calibration authority, resumable production
  scheduler, artefact recomputation, fresh source audit, and atomic paired
  publication.
- The production lifecycle is deliberately one ordered command: validate the
  live same-host calibration authority, stage/resume the exact run, validate
  all staged artefacts and selections, complete a fresh cache-disabled
  359-leaf audit, validate again, then publish and write the final marker.
- Focused Goal029 tests: `12 passed`.
- Shared Goal028/inner-CV regressions: `50 passed`; 16 existing unknown-marker
  warnings.
- Fresh synthetic lifecycle and independent validation passed with 35 leaves,
  six selected families, 18 selected seed refits, source audit, and outer
  attempted/open counts `0/0`.
- Static plan passed at 7,168 leaves, 2,016 candidate strata, 336 family
  strata, 44,240 actual inner fits, at most 1,008 refits, and 359 audit leaves.
- Full suite: `341 passed`, `2 failed`, `20 warnings`, `254 subtests passed`.
  Both failures are unrelated Goal025 full-replay drift in the existing
  tracked `evidence/spatial_partition/2026-07-26/summary.json`.
- `uv lock --check`, compilation, and `git diff --check` passed.
- No real calibration, production fit, outer opening/scoring, commit, or push
  was performed in this implementation tranche.

## 2026-07-30 — Material review repair pass

- Reworked invalid-candidate recovery so reused or newly written checkpoints
  remain intact until a blinded invalid state is durably recorded. Cleanup is
  then idempotent and records its own completion.
- Reworked paired-publication rollback to restore complete private and tracked
  trees to their stage paths after second-rename or final-marker failure.
  Restoration failure preserves authoritative destinations and fails loudly.
- Made selected refit validation externally authoritative: it binds the exact
  selected task, candidate parameters, derived fit seed, live adapter runtime,
  execution context, reconstructed training schema/order, exact
  `min(32,n_unique_eligible)` challenge, model envelope, and prediction bytes.
- Added exact staged and published file inventories. Extra checkpoint,
  selection, selected-bundle, tracked, or transaction files now fail closed.
- Strengthened the production source audit to exactly 359 immutable leaves,
  with exact valid-result/invalid-failure reconciliation, state/plan/worker
  bindings, and coherent-tamper rejection.
- Froze every runtime-sensitive configuration value by canonical config
  digest and safe-bound all configured write destinations beneath the repo.
- Focused Goal029 evidence: all 16 tests passed, including failure injection,
  path escape, degenerate challenge, extra-file, config-mutation, and coherent
  source-audit mutation cases.
- Shared regressions: all eight inner-CV tests and all 42 Goal028 tests passed.
- Fresh synthetic production and independent validation passed with 35 leaves,
  six families, 18 selected refits, semantic digest
  `0e6d2c4533e58dcf5a09f0d76707ad4ff0e2b1dec8265e4963a84413f133541d`,
  and outer attempted/open counts `0/0`.
- Static plan passed at 7,168 leaves, 2,016 candidate strata, 336 family
  strata, 44,240 actual inner fits, at most 1,008 refits, and exactly 359
  source-audit leaves.
- Full suite JUnit evidence: 601 cases, 599 passing, zero errors/skips, and the
  same two unrelated Goal025 `full_replay_evidence_drift:summary.json`
  failures.
- No real calibration, production fitting, outer access, commit, or push was
  performed during this repair pass.

## 2026-07-31 — Portable fail-closed swap telemetry repair

- Canonical calibration on Linux at commit `eb0c085` stopped before its first
  leaf because the Darwin-only `sysctl -n vm.swapusage` probe failed with
  `cannot stat /proc/sys/vm/swapusage`. The host reported healthy memory and
  zero swap use; no calibration receipt or production artefact was created.
  Calibration leaves completed: zero. Real outer attempted/open counts:
  `0/0`.
- Swap telemetry is now platform-bounded and fail-closed. Linux strictly
  requires exactly one coherent `SwapTotal` and `SwapFree` pair in `kB` from
  `/proc/meminfo`; Darwin strictly parses one coherent `vm.swapusage` record.
  Unsupported systems and telemetry read, command, or parse failures raise
  `Goal029Error("swap_telemetry_unavailable")`.
- The existing no-swap-growth and minimum-6-GiB calibration acceptance gates,
  configuration, worker policy, and scientific scope are unchanged.
- Mocked swap telemetry tests: `12 passed`, covering valid and zero-swap
  Linux, missing/duplicate/unit/negative/incoherent/read failures, valid
  Darwin, malformed/command/incoherent Darwin failures, and an unsupported
  platform.
- Focused Goal029 tests: `28 passed`.
- Shared Goal028/inner-CV regressions: `50 passed`; 16 existing unknown-marker
  warnings.
- Static plan passed at 7,168 leaves, 2,016 candidate strata, 336 family
  strata, 44,240 actual inner fits, at most 1,008 refits, exactly 359
  production source-audit leaves, and outer `0/0`.
- Fresh synthetic production and independent validation passed with 35 leaves,
  six families, 18 selected refits, semantic digest
  `d2848e7831dd0207b47fa55e2ede3a93d7dcf93f7e61bf651358f60465fd2122`,
  and outer attempted/open counts `0/0`.
- No real calibration, production fitting, private-data access, commit, or
  push was performed during this portability repair.
