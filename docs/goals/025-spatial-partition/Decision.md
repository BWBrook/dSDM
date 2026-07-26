# Decision

## Design and estimand

The frozen result is a pre-model held-patch interpolation design within
Goal024 `D_struct`. It is not unbiased confirmatory transfer, occupancy,
prevalence, isolated regional extrapolation, temporal transfer, or
outside-domain inference.

All map centroids define 50 canonical maximin microclusters, and their centres
define five auxiliary macroregions. This geometry and the macro-stratified
fold-allocation algorithm are response-independent. Feasibility gates use
response and species-binary counts; ranking uses geography, map/response
covariates, and species-binary representation or balance. Those deliberate
conditioning steps occur before any model, prediction, or performance input.

Macroregions are allocation devices, not ecological regions. Microclusters are
held units. There is no spatial buffer.

## Search scope and protocol correction

The five macroregions contain 9, 25, 9, 5, and 2 microclusters. Removing one
outer cluster per macroregion leaves 8, 24, 8, 4, and 1, so five-macroregion
coverage in every CV fold is impossible. An earlier feasibility probe omitted
that literal gate; its 3-outer/seed-3612 oracle was superseded before freeze.

The corrected generic generator processes macros by remaining count, orders
clusters and folds by prescribed SHA-256 priorities, and greedily minimises
same-macro count then fold size. Its hard allocation invariants are five
disjoint nine-cluster folds, union of all 45 training clusters, and per-macro
fold-count range no greater than one. Each production fold contains four
macroregions.

The complete prescribed 4,096-seed schedule produces 3,694 distinct outer
tuples, 166 outer hard-gate passes, six jointly feasible outer tuples, and nine
viable outer/CV assignments. The 3,694 tuples cover 18.241975% of the 20,250
possible one-per-macro tuples; the scan is schedule-complete, not
combinatorially exhaustive. The selected tuple and seed are computed outputs.

## Spatial topology

Island structure and `D_struct` holes make 19 of 50 microclusters
non-contiguous under queen adjacency. Among selected outer clusters, mc08 has
six components with 1,522 of 1,677 cells (90.7573%) in its dominant component;
mc20, mc35, and mc49 each have one component; mc40 has two, with 1,167 of
1,168 cells in its dominant component. The outer union has 11 queen
components.

There is no buffer: 484 of 6,753 outer cells (7.1672%) rook-touch training.
The five outer clusters are dispersed held patches, not isolated regions. CV
fold cluster-adjacency component counts are 8, 6, 7, 7, and 8, so CV folds are
scattered multi-patch assessments.

## Class and support limitations

`sarcophilus_harrisii` has 3,460 presences among 3,573 rows (96.84%). Its
outer assessment has only 10 absences across three selected clusters: nine
camera survey-supported absences and one pseudoabsence.
`thylogale_billardierii` has 1,360 presences among 1,485 rows (91.58%). All 19
outer absences are camera survey-supported absences in mc49, and one CV fold
has exactly 10 absences.

The gates establish computability, not stable discrimination or calibration.
Downstream work must use prevalence-aware metrics, spatial-block uncertainty,
per-cluster and source reporting, and sensitivity interpretation.

Outer assessment diagnostics contain 12 training-unseen categorical instances
and 174 continuous out-of-training-range instances. Global-dictionary
out-of-dictionary count zero is an integrity check, not evidence of
split-specific support.

## Downstream boundary

Diagnostics are descriptive and training-specific. They do not trigger repair,
imputation, reselection, or feature changes. Goal 025 authorises no fitted
transformation or model.
