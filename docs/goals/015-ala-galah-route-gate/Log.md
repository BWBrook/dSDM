# Log: Goal 015 ALA Galah Route Gate

## 2026-07-24 - Pre-live implementation gate

- Working directory `/Users/bwbrook/papers/dSDM`; branch `main`; HEAD, `main`,
  `origin/main`, and the authorized baseline all equal
  `41434b885a88940d912dc417984a7151ab089797`; inherited status was clean.
- Goal 014 files were left unchanged.
- Confirmed from `galah-python==0.13.3` source that the package uses
  `https://api.ala.org.au/occurrences/occurrences/offline/download`;
  `use_data_profile=False` appends `disableAllQualityFilters=true`.
- Confirmed package semantics: requesting `assertions` sets `qa=includeall`,
  Galah sets `dwcHeaders=true`, and the returned object is a pandas-parsed
  table rather than retained provider ZIP bytes.
- The focused suite went RED on the absent Goal 015 module, then GREEN after
  implementing exact plan validation, lazy runtime imports, one-call caps,
  temporary config cleanup, immediate raw serialization, privacy-safe evidence,
  and raw replay.

## 2026-07-24 - Single live pilot and offline repair

- The one `atlas_counts` call returned 17. The count DataFrame was immediately
  saved as `galah-count.csv`: 16 bytes,
  SHA-256 `598449fa07d9cc075eca91dbb51a7efdc06597f2acd5429c588c0cf3336edb2e`.
- The count gate permitted one `atlas_occurrences` call. It returned 17 rows
  and 144 columns in the corrected-route pilot; the immediate unmodified
  DataFrame CSV is 24,335 bytes with SHA-256
  `af89c756dc911602f657cf27622dc1585340983a114c211559fee1762be1dd13`.
- The bounded live run lasted 21.033584 seconds from
  `2026-07-24T01:19:52Z` to `2026-07-24T01:20:13Z`. No timeout, HTTP/access
  error, count drift, row mismatch, notification, DOI, authentication, or
  second live attempt occurred. The explicit temporary config was destroyed.
- The initial runner stopped as `material_schema_failure`: all other required
  core headers were literal, but `dwcHeaders=true` returned requested
  `license` as `dcterms:license`. The table also contained `assertions` plus
  124 expanded QA columns.
- One authorized offline repair encoded only the exact
  `license -> dcterms:license` alias. It regenerated tracked evidence from the
  frozen raw CSVs and recorded the initial stop and
  `second_live_attempt=false`; no network call was made.
- Exact raw replay proved both filenames and no symlinks, checksums and byte
  sizes, count 17, returned rows 17, corrected route, Galah 0.13.3, exact query
  identity, all required core headers under the one alias, and identifiable
  assertion information.

## State

`galah_route_usable_for_later_acquisition_design` under exact raw replay.
Tracked-only validation still requires raw replay. Galah exposes a parsed
DataFrame rather than the provider ZIP, and field contents or downstream
normalization fitness were not assessed in this route gate.
