# Log: Goal 009 Authoritative Contract-to-Synthetic Gate Alignment

## 2026-07-23 - Start checkpoint

- Working directory: `/Users/bwbrook/papers/dSDM`.
- Branch: `main`.
- HEAD: `8138751e26f086b375ee93f69ffc56eebf5c2eb8`.
- Status: `## main...origin/main`.
- Repo-local `AGENTS.md`: absent.
- No unrelated dirty files were present before this packet.

## 2026-07-23 - Read set

- Created this packet; required packet read order follows.
- Read Goal 008 packet/bundle, Goal 007 active scaffold, current contracts,
  manifests, exports, tests, and synthetic fixtures/README.
- No `data/` or `temp/` paths were read.

## 2026-07-23 - Implementation checkpoints

- Test-first RED after canonical fixture/schema migration: the pre-alignment
  suite failed on the old `true_absence` expectations, missing bundle
  provenance helper, and stale source checksum, confirming the intended gate
  changes were not silently accepted.
- Required the explicit `decision_bundle` input in all three synthetic builders
  and validate it against the tracked Goal 008 bundle before any summary or
  row output. Summaries now expose bundle identity/version, complete policy
  status, exact live blockers, and non-executed presence/spatial policy
  provenance.
- Canonicalized synthetic camera source/rows to
  `survey_supported_absence` and `P1-D009`; rejected legacy `true_absence`,
  missing/cross-source rule metadata, sensitive camera fields, and finer-than-
  0.01-degree camera resolution. Updated fixture checksum and README.
- Added focused Goal 009 tests for explicit bundle dependency, canonical
  readiness, contradictory presence/coordinate policy, migration failure,
  source/rule metadata, Thylogale pseudoabsence, privacy, and deterministic
  output. Focused suite: 51 tests passed.
- Active `true_absence` audit found only the validator migration error, the
  targeted compatibility-negative test, and Goal 009 packet instructions;
  no active fixture or successful builder output retains the legacy category.
- Focused repair: successful builders now consume only explicit authoritative
  `decision_bundle` readiness plus source/species contracts; parallel decision
  manifests and invented request values are retained only in isolated legacy
  validator fixtures/tests. Camera source/type/contract identity is cross-
  checked for every row, including presences, with an allowed-field privacy
  schema. Thylogale pseudoabsence is rejected at row validation.
- Added focused mutation evidence for camera presence/site privacy, ordinary
  longitude/latitude leakage, mismatched source/type, actual Thylogale
  pseudoabsence, legacy `true_absence`, missing survey rule metadata, and
  deterministic canonical readiness with exactly P1-D003/P1-D008 blockers.
- Final repair suite: 46 tests passed. Required JSON, discovery, focused,
  py_compile, diff-check, and status ladder passed after the last edit.
- No live services, payload access, staging, commit, push, or publication is
  permitted.
