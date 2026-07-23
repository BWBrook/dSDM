# Log: Goal 013 ALA Acquisition Pilot

## 2026-07-23 - Start checkpoint

- Working directory: `/Users/bwbrook/papers/dSDM`.
- Branch: `main`; HEAD and `origin/main`:
  `a6bce2622a1d0af2ff6aecb9c96d6491aac521de`.
- Status: `## main...origin/main`.
- No repo-local `AGENTS.md` is expected; the ignored global `AGENTS.md` was
  not used as a project-local contract.
- Goal 012 packet, frozen profile/evidence, module, and focused tests were read
  before Goal 013 implementation.
- No `data/` path was enumerated or read. The authorized new raw directory did
  not exist at this checkpoint.
- No live record request, staging, commit, push, cleanup, camera access,
  normalization, or ecological analysis had occurred at this checkpoint.

## 2026-07-23 - Test-first implementation checkpoint

- Added the exact 23-request, 575-row declarative plan with the frozen 20-field
  `fl` set and `occurrenceID asc` bounded order.
- RED was observed before implementation:
  `python3 tests/test_ala_acquisition_pilot.py` exited 1 with
  `ModuleNotFoundError: No module named 'dsdm_phase1.ala_acquisition_pilot'`.
- Implemented cap checks before and after retrieval, bounded transient retry
  evidence, strict row/field/identity/date checks, raw checksums, sanitized
  evidence, raw-backed reconstruction, page-overlap and deduplication checks,
  and fail-closed readiness validation.
- GREEN: `python3 tests/test_ala_acquisition_pilot.py` ran 7 tests, all passing.
  Goal 012 replay ran 8 tests, all passing; taxon-resolution replay ran 11
  tests, all passing. Python compilation and `git diff --check` exited 0.
- No live record requests had occurred at this checkpoint.
- Review constraint added before live execution: `occurrenceID asc` can support
  only bounded order/overlap evidence, not snapshot consistency. The search
  route's first-5,000-results ceiling requires a later supported
  download/export design for larger species queries.

## 2026-07-23 - First live request and focused repair

- The first planned request returned HTTP 200 with 25 rows, echoed
  `sort=occurrenceID` and `dir=asc`, and returned no facets. The initial strict
  parser stopped because the service added `otherProperties` outside the exact
  requested 20-field `fl`.
- No second request was made and no tracked evidence was written.
- The ignored raw response is
  `001-parent-thylogale-billardierii-start-000.json`, 22,509 bytes, SHA-256
  `470ca15a7f86ba8101806a429a21809de35bf5459a174394d87d609e95cc13d7`;
  recovered local file-write mtime is `2026-07-23T13:34:23Z`. This is not
  represented as an exact network-response timestamp.
- Schema-only inspection found `otherProperties` as the sole unrequested row
  field, present and non-null as an object in 20/25 rows. All 25 rows had
  non-null occurrenceID, scientificName, taxonConceptID, and taxonRank.
- The authorized repair allowlists only `otherProperties` at the raw boundary,
  drops its values from the canonical 20-field projection, and retains only
  aggregate presence/non-null/type counts. Any other unrequested field or
  non-object non-null representation fails closed.
- Added a regression test for raw-only quarantine and an exact one-file resume
  test that proves request 1 is not repeated. GREEN:
  `python3 tests/test_ala_acquisition_pilot.py` ran 8 tests, all passing.

## 2026-07-23 - Live completion and raw-backed review

- Reused request 1 from its unchanged raw bytes, then made only requests 2--23.
  Final totals were 23 successful planned requests, 23 HTTP attempts, and 525
  returned rows against the 575-row hard ceiling. There were no retries.
- All nine parents returned 25 rows on each planned page. Every response
  accepted and echoed `occurrenceID asc`; all nine parent page pairs had zero
  sampled occurrenceID overlap. This is bounded order/overlap evidence only,
  not snapshot-consistent pagination.
- Macropus synonym concept-ID/name branches returned 0/25 rows; all 25
  normalized-name rows overlapped the 50-row parent sample. Vombatus child
  branches returned 0 hirsutus, 25 tasmaniensis, and 25 ursinus rows; the two
  positive branches overlapped the parent sample by 15 and 17 rows.
- All 525 rows had valid occurrenceID, scientificName, taxonConceptID, year,
  taxonRank, assertions, license, and data-resource identity. Deduplication
  reduced 525 branch-row references to 468 unique occurrenceIDs, with 57
  cross-branch duplicate references and none within a page or parent page pair.
- `eventDate` was present on 479 rows as integer UTC epoch milliseconds and
  absent on 46. An evidence-only repair verified all 479 values were within
  2001--2025 and their derived UTC year matched `year`; downstream date
  normalization remains out of scope.
- `datasetID`, `datasetName`, `raw_taxonConceptID`, `acceptedNameUsage`,
  `acceptedNameUsageID`, and `coordinatePrecision` were absent on all 525
  rows. The frozen mapping therefore relies on data-resource, matched-name, and
  matched-concept fallbacks and preserves precision as unknown.
- Latitude/longitude were present on 523 rows and absent on two; coordinate
  uncertainty was present on 321 and absent on 204. These are field-behaviour
  counts only. No coordinate values occur in tracked evidence, and no spatial
  acceptance or normalization claim is made.
- Server-added `otherProperties` was an object on 402/525 rows. Its values
  remain only in ignored raw files; only presence/non-null/type counts enter
  tracked evidence.
- The evidence-only rebuild made zero HTTP requests. The aggregate raw
  checksum set was unchanged before and after:
  `edf779a8e7e4996be63e1c94ec3619afe7e0b778209fc5c568f53680a8d578e4`.
- Final decision:
  `pilot_pass_ready_for_bounded_full_acquisition_design`. Macropus synonym-ID
  zero coverage and Tasmania hirsutus zero coverage remain explicitly
  unresolved. The result is not readiness for complete acquisition, snapshot
  consistency, camera data, normalization, ecological totals, or complete
  synonym/descendant coverage. Species queries above the search route's
  5,000-result ceiling require a later supported download/export design.

## 2026-07-23 - Final validation checkpoint

- Goal 013 focused tests: 9/9 passing.
- Goal 012 query-scope replay: 8/8 passing.
- ALA taxon-resolution tests: 11/11 passing.
- Full unittest discovery: 85/85 passing.
- Four Goal 013 JSON files parsed; Python compilation, `git diff --check`, and
  the untracked-file whitespace scan passed.
- Raw-backed evidence replay returned 23 successful requests, 23 HTTP
  attempts, 525 rows, `raw_reconstruction=true`, and the bounded-design
  readiness decision. Both evidence-manifest checksums passed.
- All 23 raw files are ignored by `.gitignore:21:data/`; footprint is 23 JSON
  files and 443,409 bytes. Aggregate raw checksum-set hash is
  `edf779a8e7e4996be63e1c94ec3619afe7e0b778209fc5c568f53680a8d578e4`.
- The tracked-evidence record/coordinate payload scan passed.
- Final repository state remained `main` at
  `a6bce2622a1d0af2ff6aecb9c96d6491aac521de`, equal to `origin/main`,
  with zero staged paths and exactly the ten authorized untracked Goal 013
  tracked-output paths. No commit or push was performed.

## 2026-07-24 - Independent-review repair

- Strengthened raw query binding so both response echoes, `query` and
  `urlParameters`, must parse to the exact planned `q`, two `fq` values, and
  `disableAllQualityFilters=true`.
- Strengthened page validation to require non-negative `totalRecords`, the
  expected row count implied by `totalRecords`, `start`, and `pageSize`, and
  strict ascending occurrenceIDs. Parent page pairs now require equal
  `totalRecords`, zero overlap, and an ascending inter-page boundary.
- Strengthened the sanitized cross-file validator for pagination, fallback,
  deduplication, field-behaviour, assertions, unresolved findings, and the
  exact observation/inference boundary.
- Tracked-only validation can no longer return a pass readiness. It returns
  `tracked_package_structurally_valid_raw_replay_required`; only exact
  raw-backed reconstruction can return
  `pilot_pass_ready_for_bounded_full_acquisition_design`.
- Regression tests first demonstrated that the previous validator accepted
  tampered query echoes, swapped rows, an omitted expected row, parent
  `totalRecords` disagreement, a broken page boundary, and tracked-only
  pagination/fallback/deduplication/observation mutations. The repaired
  validator rejects every case.
- Rebuilt only the sanitized evidence from the existing raw snapshot. The
  rebuild made zero HTTP requests. All 23 individual raw file checksums,
  443,409 total bytes, and aggregate checksum-set hash
  `edf779a8e7e4996be63e1c94ec3619afe7e0b778209fc5c568f53680a8d578e4`
  remained unchanged.

## 2026-07-24 - Post-repair validation checkpoint

- Goal 013 focused tests: 13/13 passing, including rejection of tampered
  `query` and `urlParameters` echoes, swapped rows, an omitted expected row,
  parent `totalRecords` disagreement, a broken page boundary, and tracked-only
  cross-file mutations.
- Goal 012 query-scope replay: 8/8 passing. ALA taxon-resolution tests: 11/11
  passing. Full unittest discovery: 89/89 passing.
- Four Goal 013 JSON files parsed. Python compilation, `git diff --check`, and
  the exact untracked-file whitespace scan passed.
- Tracked-only validation returned 23 successful requests, 23 HTTP attempts,
  525 rows, `raw_reconstruction=false`, and
  `tracked_package_structurally_valid_raw_replay_required`.
- Raw-backed replay returned the same request/attempt/row totals,
  `raw_reconstruction=true`, and
  `pilot_pass_ready_for_bounded_full_acquisition_design`. The replay includes
  raw checksum, byte-size, query-binding, pagination, cross-file consistency,
  and record/coordinate payload-leakage checks.
- Both evidence-manifest checksums and all 23 individual raw checksums passed.
  Every raw file remains ignored by `.gitignore:21:data/`; the raw footprint is
  23 JSON files and 443,409 bytes, with aggregate checksum-set hash
  `edf779a8e7e4996be63e1c94ec3619afe7e0b778209fc5c568f53680a8d578e4`.
- Final repository state remained `main` at
  `a6bce2622a1d0af2ff6aecb9c96d6491aac521de`, equal to `origin/main`, with
  zero staged paths and exactly the ten authorized untracked Goal 013 paths.
  No commit or push was performed.
