# Log

## 2026-08-10 - Stage 1 contract implementation

- RED: focused Goal038 tests failed at collection because
  `dsdm.capacity_diagnostic` did not exist.
- Added the strict Stage 1 configuration, architecture registry, exact
  parameter-count and workload arithmetic helpers, common-seed metric/gate
  helpers, and the minimum plan/canary/run/status/finalize/validate CLI.
- GREEN: eight focused tests passed; configured plan arithmetic reports 480
  new atomic cells, 1,440 logical lifecycles, and 2,880 physical fits.
- The focused suite also covers flat prepared-target access, species-balanced
  seed gating, runtime mutation fail-closed, exact pooled threshold selection,
  and strict source/self-binding. Goal035/036 regression tests (16 tests)
  passed alongside it.
- `run-stage1` has not been launched: no real fits, labels, predictions,
  private bundle export, outer access, commit, or push occurred in this pass.

## 2026-08-10 - independent audit NO-GO and bounded repair

- Independent audit found a canary control-slice digest mismatch, expected-only
  runtime binding, incomplete lifecycle evidence, under-specified aggregate
  inventory, and an unfrozen Stage 2 workload. Stage 1 remained unlaunched.
- Repaired the explicit seed-31031/two-method held-row slice, added live
  Goal035 runtime attestation at every execution boundary, retained lifecycle
  transfer/reset/epoch/fit-seed/wall-time diagnostics, and made aggregate
  validation recompute the full receipt including leaf/content inventories.
- Froze the conditional Stage 2 six-method, seven-endpoint, five-seed workload
  and fresh-seed confirmation gate in config and docs. No Stage 2 code or
  alternate rescue was added.
- GREEN after repair: 10 focused Goal038 tests and 16 Goal035/036 regressions
  passed; py_compile, `uv lock --check`, whitespace, and config self-binding
  checks passed. No real fits, canary, outer access, commit, or push occurred.

## 2026-08-10 - conditional Stage 2 implementation

- Stage 1 advanced the sole eligible `wide512` candidate. Added the isolated
  Stage 2 config/module with accepted Stage 1 aggregate/canary bindings,
  Goal035 lifecycle reuse, atomic resumable 40-case leaves, status/finalize/
  validate commands, and the frozen fresh-seed confirmation gate helper.
- Stage 2 audit repairs added Goal035 deep leaf validation/write semantics, a
  real two-repeat fixed-budget `wide512` canary, fresh-seed-only confirmation,
  exact aggregate reconstruction, and species-level aggregate effects needed
  to audit the 5/8-species gate.
- GREEN before launch: 11 Stage 2 tests and 28 Stage 1/Goal035/036 regressions
  passed; Python compilation, lock, whitespace, and source self-binding checks
  passed.
- No Stage 2 fits, canary execution, outer access, commit, or push occurred.

## 2026-08-10 - completed conditional Stage 2 run

- Pre-run commit: `653aab8`. Canary passed deterministic/finite checks with
  221 logical and 441 physical fits, all substantive gates true, and outer
  access 0/0.
- Full run completed 40/40 cases with invalid 0, 8,840 logical artifacts,
  17,644 physical fits, outer access 0/0, and approximately 36 minutes elapsed.
  The exact validator exited 0.
- Final decision: `stop_no_confirmation` (endpoint-positive 1/5,
  species-positive 3/8, fresh seeds positive 0/2, aggregate D_TSS
  -0.0132355477). Fresh-seed means were 31034 = -0.0086863564 and 31035 =
  -0.0114127387. The species means are recorded in `Decision.md`; the
  dasyurid-positive pattern is exploratory only. Retain `resmlp13`; no
  alternate rescue was opened and outer access remained sealed.
