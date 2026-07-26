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

## 2026-07-26 — corrected P1-D014 matrix and reacceptance

Barry approved correction of four original matrix errors. The authoritative
exclusions are now *Thylogale billardierii* `["CBI"]`, *Notamacropus
rufogriseus* `["CI", "THI", "HI"]`, *Pseudocheirus peregrinus* `["CBI",
"CI"]`, and *Vombatus ursinus* `["KI", "CI", "THI", "HI", "BI"]`; all other
species rows are unchanged. The *T. billardierii*–CBI and *P. peregrinus*–CBI
exclusions remain explicitly provisional: absence evidence stays suppressed
pending contemporary-status resolution. There are no current eligible camera
sites on CBI, so this caveat does not alter the present output.

Test-first evidence: after changing only the focused matrix regression,
`PYTHONPATH=src uv run --locked python tests/test_phase1_contracts.py
Phase1DecisionBundleTests.test_approved_offshore_island_matrix_is_exact`
failed with the expected old-versus-corrected matrix assertion. The same test
passed after the minimal bundle and validator change.

The Goal019 plan hash moved from
`975146412285f53761bdf2878110e2fe1e84cd2aceca9f201af5142727230f0e`
to `378333d40cdb8afae07152de2435cff74ebb41be227ac498bdf68bf326a23174`.
Private `observation_audit.csv` and `site_audit.csv` remained byte-identical at
`9a8fab53422cf1221aed89f00d91ca22ec971e282b942d2126c2e444f01a134a`
and `63f6c467ed647de96390fe9176935aa9b9463f1c9d3f708295959bd1fe6b3341`.
As required, `site_species.csv` changed from
`5f35bd6aadd98b45a0cb92ddc055893f8faed9f7cee6ff6c12827bbabb93d45a`
to `3bfddb8dc9fcda5da0c9c97cb90d63e86ac2bcc8ad41e3a879cba422423bc0f6`,
and `grid_evidence.csv` changed from
`aa0cf2ad142812e08f7126f73a3ecb0b16e42b9966b0967c43a5200d95161319`
to `a16249991384d9b8545aee4027a7ac22a3ae7166bdd7e8a141ae815015021563`.
The tracked evidence transitions were: source inventory
`b679264e1a8d20e19ac3c91aa7eae03c707c700ee31bf0c4fd2c84191d96e5a3`
to `5ba53a0a611c948fd873f2fa1662774f59efd0e89391d235535ff3d11e82eebb`;
normalization summary
`4a81d80f46ae67b1f011b9f629580fc7f5916b569f63b081cdb6f14311882135`
to `cf287f40cf17496074d5ea98571104b267c8c5db2b00ab58d3824262f3c272dc`;
outputs
`080aeb8748fbf402b8fe08ade5f18e82f1171bb2fdb223d35382df91e4fcb95c`
to `491dfe10a50c6e208550919e59fbfd86600e23fb21504bbc4266ebb542464d38`;
and manifest
`a4a59cb476b3b85dc672fbab7f9d21f66f590bdd9add6c2f9a9b70e9a5588891`
to `5058b60028b0e5185a3994d58243d9aba16681bc21903f4f0447afcb43c010a7`.
The spatial summary
`46096012ee35bdb634d7e0478fd4fa3b1da3f99f3af225d4f8d193d99733ec6d`
and review
`bc112002181b26bd94321c0af8c9801b6e973466510cefd7cd65aaf45a1d5c0d`
were unchanged.

The corrected replay retains the accepted overall oracle: 1,307 eligible
sites; 10,456 pre-suppression rows; 6,095 presences; 3,941 retained
survey-supported absences; 420 suppressions; 10,036 retained rows; and 6,451
grid rows comprising 4,278 presences and 2,173 survey-supported absences. It
contains 651 within-camera conflicts and zero matrix-conflicting presences.

Per species, the
`presence_sites, absence_site_rows, suppressed, presence_cells,
absence_cells, internal_conflicts` tuples are:

- *Dasyurus maculatus*: `675, 512, 120, 525, 222, 151`
- *Dasyurus viverrinus*: `135, 1052, 120, 95, 652, 35`
- *Notamacropus rufogriseus*: `1006, 301, 0, 703, 149, 86`
- *Pseudocheirus peregrinus*: `271, 1036, 0, 252, 600, 78`
- *Sarcophilus harrisii*: `988, 199, 120, 642, 105, 83`
- *Thylogale billardierii*: `1115, 192, 0, 722, 130, 40`
- *Trichosurus vulpecula*: `962, 345, 0, 676, 176, 95`
- *Vombatus ursinus*: `943, 304, 60, 663, 139, 83`

The final suppressions are KI+FI for both quolls and devil, and KI for wombat.
The correction therefore admits exactly 60 pademelon site rows across 50 cells
and suppresses exactly 60 wombat site rows across 50 cells. Focused suites
passed 57/57 contracts, 11/11 Goal017, 23/23 Goal018, and 18/18 Goal019; full
discovery passed 165/165. Tracked-only gates returned their required replay
statuses, and the Goal017 raw, Goal018 raw/private, and Goal019 private
acceptance replays all passed.
