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

## 2026-07-26 — P1-D014 correction rebinding and reacceptance

Barry approved a correction to the authoritative species-by-island absence
matrix. This changed policy provenance, not the Goal017 acquisition scope or
raw observations. The decision bundle moved from
`5af1f76c58bd24fe61a741a42a4df4531ba21e08c0d8ce9b953ba0ff769668ae`
to `ccccbb2e56e101b1a53421f8016699bfb500f4356861e10c1213a398aabe04a2`.

The Goal017 plan was rebound from
`b363543468916bfa9fd568b15dd293f2eb6ddb21c4f0f378eb0eb7f0148fc5c6`
to `d447e1dfe536f25b1ea0126dbf9e7420024f774491e1670503ed0ea4895df632`.
The review hash changed from
`0baa5c664db30963e123f5614077f902f9b9bc990520b92e865bb9b9f11520e2`
to `c7a03d2fd5365e5d53d9bd9dc9062a31ac6083a1b054c8f16c2ab03ed364c658`;
the evidence-manifest hash changed from
`864680cee693c812f7fe342898fbda5cce8f83e1763a09a208eaf44ccebe90c4`
to `6abe4520fc8a35fbf94a6cf3c1632079770795cd75253732ab12440b1d16fe33`.
All 20 ignored raw artifacts, 50,834 rows, and 64,062,181 bytes remained
unchanged; no network call or reacquisition occurred. Full offline checksum,
footprint, schema, identity, and cross-species semantic replay passed, so
Goal017 is reaccepted under the corrected policy binding.
