# Log

## 2026-07-24 — private staging and implementation

Observation: the clean start was `ca61265`. The anchored `/tas_cam/` rule was
added before moving the three authoritative files. Pre/post SHA-256, byte and
row inventories matched exactly; the root originals are absent, every private
file is ignored, and `git ls-files -- tas_cam` is empty.

The source contains 836,548 unique positive-count observations, all inside
2001–2025, across 1,374 observation-bearing sites. All observation codes resolve
against the lookup. Six ambiguous lookup codes are nonfocal; none collides with
the eight privately frozen focal mappings.

## 2026-07-24 — production result

All 836,548 observations reconciled exactly: 596,487 focal-positive source rows
and 240,061 accepted nonfocal operational witnesses. The location source has
1,388 rows for 1,375 sites; 13 sites have two coordinate rows and all resolve to
one cell and island class. One location-only site is excluded.

All 1,374 observation-bearing sites classify against the island layer: 60 KI,
60 FI, 1,254 outside the eight polygons, and zero ambiguous. The frozen
coast/grid gate retains 1,307 eligible sites and excludes 13 outside the coast
and 54 without an eligible canonical cell.

The pre-suppression site-species expansion is exactly 10,456 = 1,307 × 8:
6,095 presences, 3,941 retained `survey_supported_absence` rows, and 420
species-island absence suppressions. There are zero matrix-conflicting focal
presences. Cell collapse yields 6,451 unique species-grid rows: 4,278 presence
and 2,173 `survey_supported_absence`. No `Macropus giganteus` camera row is
emitted.

Tracked-only validation reports private replay required. Independent private
recomputation byte-compares all four ignored outputs and exactly reproduces the
aggregate evidence. Tracked evidence contains aggregates, hashes, schema
fingerprints, and canonical species IDs only.

Implementation debugging found two source-format facts now covered by focused
tests: day/month/year timestamps and KML Placemark island codes that the
GeoPandas driver did not retain as attributes. The final parser uses the exact
KML Placemark names and polygon coordinates directly.

## 2026-07-24 — acceptance hardening

Independent acceptance review exposed three fail-open surfaces: nested
directories were omitted from footprint comparisons, evidence payloads allowed
unknown keys when their manifest hashes were recomputed, and production
destinations were not exact plan bindings. The repair now checks every
immediate private, evidence, and replay-output entry; requires expected entries
to be regular non-symlink files; validates exact aggregate payload shapes; and
binds production to the canonical ignored output and tracked evidence
directories. Five synthetic adversarial tests cover those former failures.

Tracked spatial evidence now reports privacy-safe exclusion reasons explicitly:
13 `outside_land_boundary`, 54 `ineligible_grid_cell`, and one
`unreferenced_site`. Private source files, mappings, hashes, sizes, and row
counts are unchanged.

Final validation passed: Goal 019 focused tests 18/18, Goal 018 focused tests
23/23, full Python discovery 165/165, tracked-only Goal 019 validation,
independent Goal 019 private byte/semantic replay, and unchanged Goal 018 full
raw replay. JSON parsing, `py_compile`, locked-environment resolution,
`git diff --check`, exact footprint checks, private ignore checks, tracked-path
inspection, and aggregate privacy scans also passed.
