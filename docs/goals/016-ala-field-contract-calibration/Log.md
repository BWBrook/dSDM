# Log: Goal 016 Offline ALA Field-Contract Calibration

## 2026-07-24 - Offline calibration

- Started from clean `main` at `61aea11bf4f7797d2210b6abfd2a22f4ca44b5c0`.
- Revalidated Goal 015 as
  `galah_route_usable_for_later_acquisition_design`.
- Bound the ignored occurrence CSV at 24,335 bytes, 17 rows, 144 unique
  columns, and the accepted SHA-256.
- Found `occurrenceID` present but blank in 17/17 rows; `recordID` was absent.
  No provider identity was selected and no content-derived fallback was used.
- Resource UID/name were populated in 17/17 rows, while dataset ID/name were
  blank in 17/17. The contract therefore preserves these provenance levels
  separately.
- Event date/year, coordinates, reported uncertainty, matched taxon fields,
  licence, and assertion summary were populated in 17/17 rows. Event dates
  parsed and agreed with year; all coordinate pairs were globally valid; no
  reported uncertainty exceeded 1,000 m.
- Coordinate precision and provider accepted-name fields were blank in 17/17.
  Missing precision remains unknown; decimal digits are not treated as
  precision evidence.
- The 124 expanded non-core fields contained 2,108 Boolean-compatible cells:
  114 fields were always false, eight always true, and two varied. Each row
  carried nine true flags, confirming that `any flag = reject` would be
  indefensible. Their ordered header inventory is frozen explicitly; an
  unknown Boolean extra is not silently accepted as another QA field.
- All 17 full rows and all 17 complete diagnostic content fingerprints were
  distinct. The fingerprint remains diagnostic only.
- Concluded that separately manifested canonical-query counts may proceed.
  Full row acquisition, branch union, and cross-download deduplication remain
  blocked pending provider-identifier calibration.

## State

Tracked-only validation is
`ala_field_contract_tracked_evidence_valid_raw_replay_required`. Exact local
raw replay returns
`count_census_ready_full_row_acquisition_blocked_on_provider_identity`.

Focused tests passed 9/9 and the full Python suite passed 113/113. Independent
review found one material nested-evidence/QA-classification cluster; the single
focused repair closed it, and the reviewer accepted the goal without further
iteration.
