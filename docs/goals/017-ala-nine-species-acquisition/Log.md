# Log: Goal 017 ALA nine-species acquisition

## 2026-07-24 — offline scaffold

- Added the pinned plan, fail-closed runner, synthetic tests, and this
  pre-live documentation package.
- Verified Goal016 decision-plan, field-contract, and phase-1 decision-bundle
  bindings against their current hashes.
- Focused synthetic tests passed. No network call, live Galah configuration,
  raw source acquisition, commit, or push was performed.

## State

Superseded by the accepted live acquisition below.

## 2026-07-24 — live acquisition and acceptance

- Reconfirmed the Goal016 raw-backed split decision before the live run:
  counts were ready and full acquisition remained gated on provider identity.
- Ran the pinned `galah-python==0.13.3` workflow once in the locked project
  environment. The runtime account was neither logged nor retained.
- Completed ten count calls: nine canonical Tasmania 2001–2025 parent queries
  plus the bounded *Pseudocheirus peregrinus* 2001 canary count.
- The canary returned 17 rows and passed the required `recordID` completeness,
  control-character, and uniqueness checks.
- Acquired all nine species in ascending census-count order. Each frozen file
  matched its pre-download count and the exact calibrated schema; provider
  identifiers were complete and unique within and across species.
- Frozen aggregate: 50,834 ALA-indexed records in 20 ignored raw artifacts
  totalling 64,062,181 bytes.
- Raw-backed replay passed exact footprint, checksum, byte-size, count, schema,
  identity, and cross-species reconciliation checks.
- Tracked evidence contains aggregate metadata only. It retains no occurrence
  rows, provider identifiers, coordinates, dates, runtime account, or network
  error content.
- Goal017 focused tests passed 11/11 and the full repository suite passed
  124/124 before the live run.
- Independent preflight and post-live reviews accepted the substantive gates;
  this ledger update was the only post-live repair requested.

## Final state

Goal017 is complete. The result is a reproducible raw ALA source snapshot, not
an ecological abundance or occupancy estimate. No boundary clipping, spatial
assignment, downstream quality exclusion, biological duplicate resolution,
pseudoabsence derivation, camera integration, predictor extraction, or
modelling was performed.
