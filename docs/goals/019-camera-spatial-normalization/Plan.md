# Plan

1. Protect the private source with the anchored `/tas_cam/` ignore rule, move
   the three files without changing bytes, and verify hashes, sizes, rows, and
   ignored status.
2. Validate the private manifest, schema fingerprints, lookup integrity, unique
   observation identities, the ignored focal crosswalk, and complete row
   reconciliation.
3. Reduce observations to stable-site focal detections and operational
   nonfocal witnesses; treat survey labels as provenance, not replicates.
4. Require every coordinate row for a site to map to one eligible Goal 018
   canonical cell and one island class using WGS84 `covers`, with no nearest
   rescue.
5. Cross each eligible site with eight focal species. Retain every presence,
   suppress island-ineligible absence evidence, and block publication on a
   matrix-conflicting presence.
6. Collapse to one species-grid camera classification with presence dominance,
   retaining private site and conflict counts.
7. Stage private outputs and aggregate-only evidence, validate their contracts,
   publish with rollback, then independently replay from the private source.

Stop on private binding/schema drift, focal lookup ambiguity, duplicate raw
identity, repeated-site cell/island ambiguity, a matrix-conflicting focal
presence, noncanonical output cells, or tracked privacy leakage.
