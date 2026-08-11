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
  assumed and provider rows must deduplicate by `occurrenceID`.
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
