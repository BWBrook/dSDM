# Goal 020 — ALA-camera evidence combination

## Objective

Reconcile the accepted Goal 018 ALA presence grid and corrected Goal 019
camera grid evidence into one deterministic eight-species evidence layer
without changing either upstream product.

## Outcomes

- One ignored private species-cell CSV preserves final class, source category,
  cross-source conflict, and all applicable prefixed source provenance.
- Any accepted ALA or camera presence dominates a camera survey-supported
  absence at the same species-cell key.
- Camera survey-supported absence remains first-class only where no accepted
  presence exists and retains rule `P1-D009`.
- The 34 frozen *Macropus giganteus* ALA rows remain in Goal 018 provenance
  but are excluded exactly at this downstream boundary.
- Tracked evidence contains only frozen hashes, ordered schemas, aggregate
  cross-tabs, spatial counts, and validation status.

## Acceptance criteria

1. All upstream bindings and tracked validators pass without drift.
2. The five mutually exclusive source combinations reproduce the frozen
   overall and per-species oracle.
3. Overlapping source keys have identical centroids and all rows retain valid
   canonical grid identities.
4. The corrected `P1-D014` matrix has zero conflicting accepted presences;
   no presence is silently deleted.
5. Tracked-only validation requires private replay, and full validation
   byte- and semantic-compares a fresh recomputation.
6. The private output is ignored and tracked evidence contains no row values,
   locations, camera identifiers, timing, or private paths.

## Non-goals

This goal does not create unsampled rows or perform pseudoabsence generation,
predictor extraction, partitioning, mapping, thinning, weighting, class
balancing, occupancy analysis, modelling, or manuscript work.
