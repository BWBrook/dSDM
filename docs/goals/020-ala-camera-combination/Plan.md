# Goal 020 plan

## 1. Freeze inputs

Bind the decision bundle, both upstream plans and evidence bundles, the
accepted ALA presence role, the corrected camera grid-evidence role, and the
island geometry. Validate hashes, schemas, row counts, regular-file status,
unique species-cell keys, species footprints, and upstream tracked gates.

## 2. Reconcile evidence

Exclude exactly the frozen 34-row *Macropus giganteus* ALA slice. Form the
full outer union of the eight active species by grid cell, sort
deterministically, and apply the five-way truth table:

1. ALA-only presence.
2. Camera-only presence.
3. Presence in both sources.
4. ALA presence overriding camera survey-supported absence.
5. Retained camera survey-supported absence.

Source-absent provenance is blank. Camera internal conflict is copied
unchanged and remains distinct from cross-source conflict.

## 3. Gate science and privacy

Require identical centroids on overlapping keys, canonical grid identities,
the frozen aggregate oracle, and zero accepted presences in an excluded
species-island combination. Publish only aggregate evidence.

## 4. Verify and stop

Run focused tests, tracked validation, full private replay, upstream focused
and full acceptance replays, full test discovery, syntax and JSON checks,
lock verification, diff checks, exact footprint checks, and privacy scans.
Perform at most one focused material repair before handoff.
