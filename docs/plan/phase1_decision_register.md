# Phase 1 Decision Register

Date: 2026-07-23
Machine-readable authority: `config/phase1_decision_bundle.json`

This register is the human-readable view of the executable bundle. Every
decision ID appears once. “Resolved + prerequisite” means the policy is fixed,
but live acquisition remains blocked until the explicitly listed operational
check is completed. No exact ALA concept ID, guessed alias, camera path,
camera coordinate, site ID, or active deployment detail is stored here.

| ID | Status | Consolidated decision | Owner | Gate / operational note |
| --- | --- | --- | --- | --- |
| P1-D001 | Resolved | Phase 1 has nine focal Tasmanian mammals. | Barry | Species list in bundle; before acquisition. |
| P1-D002 | Resolved | Include *Thylogale billardierii*; treat as near-ubiquitous, low-contrast at 0.01 degree; do not manufacture class balance; use prevalence-aware evaluation/sensitivity. | Barry | Thylogale pseudoabsence generation disabled. |
| P1-D003 | Resolved + prerequisite | Stable project IDs, accepted canonical names, explicit historical-alias field, and pinned ALA concept IDs are required. | Barry | Exact ALA query/taxon resolution and Barry compact check pending; blocks live ALA. |
| P1-D004 | Resolved | Primary ALA window is inclusive 2001-01-01 through 2025-12-31; archive older records; exclude records without a defensible year from primary analysis; retain date precision. | Barry | Before live ALA. |
| P1-D005 | Resolved | Include broadly across eligible ALA resources; retain resource IDs/diagnostics; use only a documented versioned blocklist for demonstrated problems. | Barry | Before live ALA. |
| P1-D006 | Resolved | Layered quality policy: exclude taxon/coordinate/boundary failures and uncertainty >1000 m; missing uncertainty is not automatic exclusion; precision basis is reported/inferred/unknown; never infer from processed digit counts; retain provisional undocumented UTM precision as unknown; deduplicate IDs and preserve counts/provenance. | Barry | Before ALA normalization. |
| P1-D007 | Resolved | Version ALA results with raw snapshots, complete manifests, timestamps, endpoints/package versions, taxon IDs, filters, counts, and checksums. | executor | Before first ALA run. |
| P1-D008 | Resolved + prerequisite | Barry’s camera dataset is authoritative; exact local source path is intentionally unresolved and absent from tracked config. | dSDM | Barry source staging/path check pending; blocks camera ingestion. |
| P1-D009 | Resolved | Long-running near-continuous camera non-detection is `survey_supported_absence`, not true absence. | Barry | Preserve label in normalized evidence. |
| P1-D010 | Resolved | Retain only essential camera provenance, broad 3–4 year deployment period, and absence rule; no detailed effort/detectability study. | Barry | Before camera ingestion. |
| P1-D011 | Resolved | Any accepted ALA or camera presence makes the species-grid cell present; camera survey-supported absence applies only without accepted presence; preserve conflicts/provenance/counts. | Barry | Presence dominates at species-grid level. |
| P1-D012 | Resolved | Validate and retain exact legacy `tasmanian_gridpoints.csv` 0.01 degree WGS84 grid alignment/centroids, stable coordinate-derived IDs, and checksum; camera UTM coordinates were transformed to WGS84 before entry. | Barry | Before spatial normalization. |
| P1-D013 | Resolved | Retain legacy `tasmania_coast.shp` for broad filtering; canonical grid controls final eligible cells; island rules remain separate. | Barry | Before spatial filtering. |
| P1-D014 | Resolved | Retain the encoded approved species-by-island matrix (KI, FI, CBI, CI, THI, HI, MI, BI); apply exclusions to absence evidence only; future excluded-combination presence triggers review, never silent deletion. | Barry | Exact matrix is authoritative in the bundle. |
| P1-D015 | Resolved | Assign only to containing eligible 0.01 degree cell; record centroid distance; local half-diagonal is about 0.7 km; no nearest-land rescue; flag/exclude water/lake cells; assess uncertainty separately. | Barry | Before coordinate assignment. |
| P1-D016 | Resolved | ALA pseudoabsence candidate requires at least three distinct non-target focal species and no target presence; camera classification supersedes; none for *Thylogale billardierii*. | Barry | Before pseudoabsence derivation. |
| P1-D017 | Resolved | ALA pseudoabsences must be at least 5 km from nearest accepted target presence in a suitable projected metric CRS; retain nearest distance; does not remove camera survey-supported absences. | Barry | Before pseudoabsence derivation. |
| P1-D018 | Resolved | No human-footprint, random, or k-means thinning during acquisition; collapse to one species-grid outcome while retaining counts/provenance; later weighting/sensitivity is modelling-stage only. | Barry | Before acquisition/normalization. |
| P1-D019 | Resolved | Use 50 deterministic geographic microclusters; fixed-seed candidate five-cluster outer test sets; pre-model score geographic/environmental/regional dispersion and usable species/class representation; permit one ecological visual review; freeze test set; allocate remaining 45 to five spatial CV folds. | Barry | Before fitting; revise criteria, not individual clusters, if deficient. |
| P1-D020 | Resolved | Existing `tas_stack.tif` and the exact ordered 28-layer active set (`annmeantemp` through `human_footprint`) are authoritative after technical validation; exclude `landuse_primary`, `landuse_tertiary`, `veg_mvs`, `fire_freq`; preserve source metadata. | Barry | Exact identities/order are encoded in the bundle; do not rebuild sources in Phase 1. |
| P1-D021 | Resolved | Persist categorical level dictionary from the complete accepted predictor map. | executor | Before transformations. |
| P1-D022 | Resolved | Fit continuous scaling on training data only; persist parameters and apply unchanged to validation, test, and map. | executor | Before transformations. |
| P1-D023 | Resolved | Three-tier QA: non-negotiable schema/provenance/spatial/reproducibility/source/partition/contradiction checks; investigate interpretation-threatening diagnostics; legacy comparisons diagnostic only; one sweep plus at most one focused repair, then stop/reassess. | Barry | QA gate design. |
| P1-D024 | Resolved | Tracked fixtures remain small and synthetic; real fixtures require explicit approval and avoid sensitive locations. | dSDM | Current bundle uses no real fixture. |
| P1-D025 | Resolved | Raw/bulky outputs remain ignored; track configs, manifests, checksums, and non-sensitive summaries only. | dSDM | Storage policy. |
| P1-D026 | Resolved | Continue the existing minimal standard-library Python contract scaffold; no broad migration. | executor | Current implementation scope. |
| P1-D027 | Resolved | Use one human-readable, machine-validated tracked JSON decision bundle; avoid duplicated authoritative values. | executor | `config/phase1_decision_bundle.json`. |
| P1-D028 | Resolved | Exact camera coordinates/site IDs remain private/ignored; 0.01 degree is the finest tracked/public resolution; do not expose deployment timing/current activity; release collapsed grid-level evidence only. | dSDM | Privacy maximum encoded in bundle. |
| P1-D029 | Resolved | Legacy outputs are comparison evidence only, never canonical inputs or automatic gate targets. | dSDM | Diagnostic comparisons only. |
| P1-D030 | Historical/resolved | Initial minimal Python contract scaffold goal is complete; retain as historical context. | dSDM | Historical/resolved; no live acquisition implied. |

## Operational prerequisites (separate from resolved policy)

1. **P1-D003 — exact ALA resolution:** Barry’s compact scientific check must
   resolve exact accepted-name/alias queries and ALA taxon concept IDs. The
   bundle deliberately stores null placeholders and therefore reports live ALA
   acquisition as blocked.
2. **P1-D008 — authoritative camera staging:** Barry must identify/stage the
   authoritative local camera source. The exact path is private, untracked, and
   absent from the bundle until that check is complete; camera ingestion remains
   blocked.

The Goal 008 validator checks policy consolidation independently of these two
prerequisites and never opens `data/`, `temp/`, or source payload paths.
