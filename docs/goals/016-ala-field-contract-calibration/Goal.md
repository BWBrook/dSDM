# Goal 016: Offline ALA Field-Contract Calibration

## Objective

Use the exact ignored Goal 015 Galah occurrence table, without network access,
to calibrate a reusable ALA source-field contract and decide whether the
project is ready for the nine-species 2001--2025 count census.

## Decision

The count census is ready for separately manifested canonical queries. Its
estimand is the number of ALA-indexed records matching each query at retrieval
time, not independent observations, animals, occupancy, or abundance.

Full row acquisition and cross-download deduplication are not ready.
`occurrenceID` is empty in every frozen record and `recordID` was not included
in the projection. A taxon/date/coordinate/resource fingerprint is useful for
diagnostics but is not a provider record identity.

## Boundaries

- Exact local replay of the frozen 17-row, 144-column CSV only.
- Aggregate completeness, distinct-count, format, QA, and duplicate evidence.
- Exact ordered allowlisting of the 124 expanded Boolean QA headers.
- No individual identifier, coordinate, date, timestamp, row, camera record,
  account detail, or source-row hash in tracked evidence.
- No live ALA call, count census, full acquisition, normalization output,
  modelling, camera processing, or manuscript work.
- The generic field contract contains no Tasmania or focal-period scope.
- The historical count-preflight profile remains unchanged and is explicitly
  marked incompatible for future full-row mapping.
