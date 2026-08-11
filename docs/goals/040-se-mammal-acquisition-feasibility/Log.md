# Log

## 2026-08-11 — prespecification

- Started from clean `main` at `c274584`.
- Frozen the domain, period, biological eligibility, count-blind species-cell
  tiers, acquisition/resource boundary, inherited QA, four-state response,
  target-group thresholds and distance safeguard, separate future estimands,
  predictor portability pilot, privacy boundary, and final decision criteria.
- Repaired the prespecification so the final taxon/query ledger is tracked,
  shared readiness uses the objective five-taxon total rather than every anchor
  passing, and a versioned land/state authority must be frozen before counts.
- Consulted existing repository documentation and code plus header/metadata-level
  spatial references only. Historical SE products remain archaeological checks.
- No live ALA count/query, occurrence download or payload inspection, private
  row read, model fit, map, outer access, commit, or push was performed.

## 2026-08-11 — rejected discovery-led freeze

- Rejected the initial 274-row ALA bounding-box discovery ledger because a
  provider discovery result cannot define biological eligibility or prove a
  complete candidate frame. No downstream count or acquisition stage used it.

## 2026-08-11 — repaired count-free taxonomy and exact-domain freeze

- Froze all 416 species-level rows in the AMTC Australian Mammal Species List
  v5.0 (February 2026) as the candidate frame, including 40 dagger-marked
  globally extinct species as explicit exclusions. ALA discovery is retained
  only as a name-resolution cross-check (264 exact overlaps), never as the
  completeness or eligibility authority.
- Materialised a 416-row tracked ledger: 21 query-role taxa, 177 categorical
  exclusions, and 218 non-query taxa. The 21 include all five approved shared
  anchors, *Macropus giganteus* as a mainland control, and 15 additional
  mainland donors. Every query uses an accepted AFD parent plus an explicitly
  reviewed, domain-relevant accepted-descendant union; parent expansion is not
  assumed and provider rows must deduplicate by canonical ALA `recordID`;
  `occurrenceID` is retained only as an optional auxiliary field.
- The added-donor mechanism preferentially finds VIC/ACT listed taxa. This is
  therefore a conservative, nonrepresentative feasibility subset, not a
  representative census of southeastern mammals. Legal listing plus AFD range
  is only an eligibility prior; later 2001--2025 acquisition and QC must
  establish observed support. Goal 040 may support a frozen-subset operational
  feasibility claim only.
- Reconstructed the archived study polygon from
  `data/input/spatial_polygons.zip`, selected 163 whole IBRA7.1 subregions by
  at least 0.99 overlap with their same-code archived IBRA7.0 polygons, and
  explicitly excluded the 2.15% `MDD01` sliver (1,168.823 km2). The sorted
  allowlist digest is
  `00e6b954b657e1ad09c10bbf088dacd5ae72b7dfaa1d8d507da5bfc55243f81e`.
- Materialised the exact 0.01-degree centroid grid using the IBRA allowlist,
  ABS ASGS Edition 4 state land, and the Geofabric type-25/26 open-water mask.
  It contains 1,125,325 eligible cells: 1,053,032 mainland and 72,293 Tasmania.
  Northern Territory and Other Territories are absent; 61 Other Territories
  cells were explicitly removed before final eligibility. The ordered cell-ID
  digest is
  `022a83b2762b886f455406a96cb48a91d612e1b08d6d1cad00eb5db7070a2b06`.
- No occurrence count, occurrence payload, camera/private response data,
  model, map, outer material, commit, or push was accessed or produced.

## 2026-08-11 — live count-only census and resource gate

- Ran `galah-python==0.13.3` `atlas_counts()` over all 45 frozen logical query
  branches: 21 accepted parents, 23 reviewed descendants, and one
  evidence-backed alias. The package combined each taxon's accepted parent and
  descendants into one OR-LSID count, giving 21 taxon-union requests; a 22nd
  request verified that the Macropus alias resolves to its already-counted
  accepted-parent LSID. Every request used 2001--2025 inclusive, the frozen
  bbox, `pageSize=0`, and `disableAllQualityFilters=true`. Service responses
  contained zero occurrence rows and empty facet payloads. No email was
  transmitted or retained.
- The initial 45 per-branch calls included the Macropus alias that remains part
  of the canonical evidence. The later pass added 21 taxon-union calls. The
  tracked provenance therefore distinguishes 22 canonical retained estimates,
  44 superseded exploratory estimates, and 66 unique live metadata-only
  requests. Every call used `pageSize=0` and returned no occurrence rows; the
  superseded counts do not enter the resource arithmetic.
- Counts are unique within each OR-LSID taxon query. They remain conservative
  bbox-prefilter indexed-row counts, not exact IBRA-domain or post-QC counts;
  cross-materialised-branch `recordID` deduplication remains mandatory after
  acquisition.
- Corrected the pre-acquisition identity contract using Goal 017 public
  evidence: `recordID` was complete and unique across 50,834/50,834 rows,
  whereas `occurrenceID` was materially incomplete, including only
  10,240/33,442 devil rows populated. Duplicate `recordID` values across every
  materialised parent, descendant, and alias union must collapse once.
- Conservative per-taxon totals were: *Burramys parvus* 1,022; *Dasyurus
  maculatus* 12,641; *Gymnobelideus leadbeateri* 3,017; *Macropus giganteus*
  221,222; *Mastacomys fuscus* 2,582; *Notamacropus rufogriseus* 94,282;
  *Petauroides volans* 34,208; *Petaurus australis* 20,059; *Petaurus
  norfolcensis* 8,281; *Petrogale penicillata* 6,491; *Phascogale tapoatafa*
  5,952; *Phascolarctos cinereus* 323,666; *Potorous longipes* 3,695;
  *Pseudocheirus peregrinus* 134,748; *Pseudomys fumeus* 2,504; *Pseudomys
  novaehollandiae* 2,612; *Pseudomys shortridgei* 1,007; *Sminthopsis
  crassicaudata* 3,780; *Sminthopsis leucopus* 3,463; *Trichosurus vulpecula*
  258,744; and *Vombatus ursinus* 114,907. The Macropus alias probe also
  returned 221,222 after resolving to the same accepted-parent LSID and was not
  added twice.
- The conservative total is 1,258,883 rows, below 2,000,000; the maximum taxon
  is 323,666, below 500,000. Projected working space is 12,890,961,920 bytes
  (`rows * 2048 * 5`). From 299,638,341,632 free bytes at the gate,
  286,747,379,712 remain after projection, above 30 GiB. Decision:
  `pass_acquisition_authorised`.
- Retained only ignored raw count request/projection receipts and a tracked
  privacy-safe manifest. No occurrence row acquisition/export, camera/private
  access, normalisation, support/predictor work, map, model, outer access,
  commit, or push was performed.

## 2026-08-11 — acquisition runner implementation ready

- Added a resumable, one-worker Goal 040 acquisition runner bound to the
  published contract, taxon ledger, domain manifest, count manifest, and exact
  21-taxon union matrix. It is prepared to call each frozen OR-LSID query once
  in ascending count order, with no alias-only download, sampling, or further
  taxon screen.
- The runner requires the download contact only from the runtime environment,
  uses an ephemeral unauthenticated galah configuration, retains the expanded
  assertion diagnostics, and checkpoints each validated raw CSV with a compact
  ignored completion receipt. Only after all 21 pairs validate will it publish
  the privacy-safe tracked aggregate manifest.
- This entry records implementation readiness only. No live ALA occurrence
  call, raw occurrence acquisition, camera/private access, normalisation, QA,
  support calculation, modelling, commit, or push was performed.
- Readiness repair: the first invocation stopped safely before an ALA call
  because galah 0.13.3 requires the temporary configuration file to exist.
  The runner now creates that empty ephemeral file before configuration, with
  the precondition covered by the synthetic fake.

## 2026-08-11 — live occurrence acquisition checkpoint

- Completed the frozen 21-taxon acquisition and raw replay: 1,258,883 rows,
  all `recordID` values populated and distinct, 56,414 blank `occurrenceID`
  values, and one identical 148-column schema across all downloads. The
  tracked aggregate manifest and all 21 ignored completion receipts agree with
  the raw files and hashes; raw replay validation passed.
- The ignored raw footprint is approximately 1.64 GB (21 CSVs plus 21
  receipts, with no partial files). No camera/private data, spatial or taxon
  QC, normalisation, support, predictor extraction, or modelling work was
  performed. This checkpoint closes acquisition only; it does not close Goal
  040 or authorise stage 6.
