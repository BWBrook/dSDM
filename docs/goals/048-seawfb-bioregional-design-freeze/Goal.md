# Goal 048 - SEAWFB bioregional outer-design freeze (v1.3)

## Scientific objective

Prospectively select and freeze three complete IBRA7.1 bioregions as a
simultaneous outer assessment for the south-east Australian woodland/forest
bird (SEAWFB) case before any model outcome is produced. The three regions
must represent:

1. geographic transfer into an environmentally supported region;
2. transfer to an environmental-edge region; and
3. transfer to a fragmented or land-use-mosaic region.

Tasmania is ordinary training geography and is not a holdout candidate. The
selected regions are fixed challenge environments, not a random or replicated
sample of south-east Australia.

Version 1.3 completes the prospective design freeze. The simultaneous outer
assessment is:

1. **NCP - Naracoorte Coastal Plain:** environmentally supported geographic
   transfer;
2. **SEH - South Eastern Highlands:** environmental-edge transfer; and
3. **NNC - NSW North Coast:** fragmented/land-use-mosaic transfer.

Each complete region and its external 50 km buffer is excluded from every
development operation. Tasmania remains ordinary retained training geography.
The freeze changes none of the response-blind seed ledger, ecological roles,
seasonal policy, candidate rule, response-free score, hard estimability gates,
or development firewall.

The frozen selector first returned a prespecified ambiguity stop. Barry then
resolved that scientific ambiguity explicitly by choosing immutable
response-free rank 4. This was not a changed ranking rule and occurrence
support remained pass/fail only; occurrence magnitudes did not break the tie.

## Question, estimand, and observation process

The later experiment asks whether species-rich dSDM pretraining improves
geographic transfer of relative habitat-suitability discrimination over a
matched target-only neural model and strong conventional SDMs.

The primary estimand is the paired method contrast in ROC AUC within each
estimable target-species x holdout-region task. Evaluation labels distinguish
accepted presence cells from target-group, effort-supported background cells.
They are not true absences, occupancy states, abundance, or independent survey
visits. ALA evidence is opportunistic and uneven in space, time, taxa, observer
effort, and detectability. The atomic response unit is therefore a species x
eligible 0.01-degree cell over 2001-2025, not an individual record.

## Prospective ordering

Before any new ALA occurrence count, all four prerequisites must be complete
and checksum-bound:

1. literal whole-region IBRA7.1 authority and exact prospective domain;
2. exact current ALA concept mapping for every biological species in the
   mandatory feasibility seed ledger;
3. effort, auxiliary, and target roles with reason and seasonal classification;
4. the complete NVIS 7 native-woody mapping.

Count-free taxonomy/BIE lookups are permitted while completing these freezes.
Occurrence counts are not. Ambiguous taxonomy or ecology stops for review and
cannot be resolved using occurrence support.

The premature two-identifier probe recorded in
`evidence/seawfb_bioregional_freeze/goal048/protocol_incident.json` is a
protocol incident. Its counts are excluded from every formal gate, taxonomic
or ecological decision, region score, ranking, and estimability assessment.
The two exposed taxa remain mandatory seeds and may not be pruned or
reclassified because of those counts.

## Aggregate feasibility route

After all prerequisites are frozen, process exactly one biological species at
a time with `galah.atlas_counts()`. Its exact frozen ordered identifier union
must include the accepted species parent, every reviewed accepted descendant
or subspecies, and every necessary reviewed historical alias concept
attributable to that species. Cross-species unions are forbidden. Use the
identical ordered union and identical 2001-2025, bounding-box/domain,
present-status, and spatial-valid filters for both calls:

- obtain a separately scoped total count;
- obtain `group_by="lat_long"` facets;
- require the facet-count sum to equal the total exactly;
- stop on mismatch, truncation, timeout ambiguity, or a missing coordinate;
- snap coordinate groups immediately to the 0.01-degree grid and collapse to
  unique species-cells inside the exact frozen domain;
- bind the private species-cell receipt by checksum, then discard coordinate
  strings before continuing to the next taxon.

No occurrence download, indexed or raw event rows, provider IDs, observer
fields, email/contact value, or canonical acquisition is authorised. There is
no raw-row fallback. The transport ceilings are 750,000 `lat_long` groups per
biological-species query, 10,000,000 groups across the feasibility universe,
4 GiB private disk, 8 GiB peak RAM, and sequential one-species processing.
They are transport ceilings, not ecological gates.

## Frozen scientific scope

- A holdout is the complete dissolved geometry of one official IBRA7.1
  bioregion. The official authority must reconcile to 89 regions and 419
  subregions.
- The literal 0.80 official-land overlap rule yields 15 prospective regions;
  EYB is excluded at approximately 0.6678. Required Brigalow Belt South
  completion remains unchanged. Tasmania remains training geography.
- Separate observation-effort donors, auxiliary pretraining heads, and focal
  evaluation targets. Every role and exclusion reason remains explicit.
- Regularly recurring seasonal migrants remain eligible under the integrated
  2001-2025 habitat-use estimand; strongly nomadic or irruptive taxa without a
  stable static target remain excluded.
- Candidate-role scores remain completely response-free. Aggregate
  species-cell evidence may only pass or fail the frozen `X=10`, `X=20`, and
  estimability gates.
- Select all three regions jointly against one simultaneous retained-training
  complement. Apply the fixed 50 km external buffers and every strict leakage
  rule in the frozen config.
- Richness and effort summaries remain prohibited as model predictors.

## Completed response-free substrate

The predictor extension produces the private
`data/processed/dsdm/goal048-seawfb-bioregional-freeze/predictors/predictor_substrate.parquet`
with exactly 1,144,286 rows: the 1,125,325 Goal 041 rows plus 18,961 complete
BBS additions. It preserves the Goal 041 schema and old-row values, uses the
local categorical sources, an aligned native-grid ALA WCS WorldClim crop for
the northern gap, and 29 exact GA elevation blocks. Its overlap proof and manifest
are checksum-bound; no response input is permitted.

The response-free score stage uses continuous-complete cells in sorted
`cell_id` order. Its full-domain PCA basis is sampled with endpoint-inclusive
indices `floor(j*(n-1)/(m-1))`, capped at 100,000 domain cells (and 2,000 per
region), scaled by median/IQR with exact-zero-IQR dimensions removed, centred
by the arithmetic mean after scaling, and fitted by deterministic full SVD
without whitening. The smallest component count retaining at least 0.90
variance is selected. This basis is selection-only and must not be reused for
Goal 049 or model fitting.

For each of all 455 unordered triples, the simultaneous retained complement
after the three 50 km buffers supplies the fixed, response-free reference
before structural or occurrence gates. It contains at most 100,000 evenly
sampled continuous-complete cells. The 1,365 context-member values use
average-tie percentiles `(rank-1)/(n-1)`. Region environmental novelty is the
p90 nearest retained-training distance in PCA space; geographic isolation is
the median nearest retained-training distance in EPSG:3577 kilometres.

Fragmentation uses the complete eligible-cell east/north rook graph, with
mapped-to-mapped edges as denominator and discordant native-woody/non-woody
edges as numerator; missing NVIS cells are excluded. The mosaic woody-fraction
gate is inclusive at 0.20 and 0.80 and applies only to the mosaic role. ALUM
uses `H=-sum(p ln p)` normalized by `log(K_global)`, never by a region-specific
number of levels. Fixed EPSG:3577 50 km tiles are anchored at `(0,0)`.

Structural validity requires distinct regions, official geometry intersection,
touch, or overlap to count as adjacency, and every pairwise centroid distance
to be at least 250 km. Each unordered set receives its best role permutation
by descending minimum score, descending score sum, and ascending role tuple;
sets are ranked by the same deterministic order. Ambiguity is assessed only
between two different top sets and requires both frozen margins to be below
their thresholds.

The embedded 100-name list is a mandatory, response-blind feasibility seed,
not the final ceiling on the bird pretraining universe. Goal 048 uses eligible
seed members conservatively for `X=10`, `X=20`, and the at-least-20 common
target feasibility gate. Goal 049 may expand effort, auxiliary, and target
universes under the same frozen taxonomic/ecological rules before canonical
acquisition and before any holdout outcome access. It cannot change,
substitute, or re-rank the three selected regions. Expanding donors can only
relax support relative to this seed screen; final exact labels and panels are
reconstructed from canonical Goal 049 data.

## Frozen outer-assessment design

Response-free scoring produced 147 immutable ranked sets, of which 109 passed
the occurrence-based hard gates. Ranks 1 and 2 failed only because AUA had 937
`X=10` effort-supported cells, below the frozen 1,000-cell minimum. The first
feasible set was rank 3, NCP/NET/SEH, with minimum role score
0.6906158357771262, score sum 2.288332635106829, and 39 conservative common
targets. The selected rank-4 set, NCP/NNC/SEH, has minimum role score
0.6851173020527859, score sum 2.362327188940092, and 40 conservative common
targets.

The signed rank-3-minus-rank-4 margins are +0.005498533724340282 for the
minimum role score and -0.07399455383326314 for the sum. The frozen ambiguity
rule therefore fired. The independent audit recommended rank 4 because it
gains 0.0080645161290322 in environmental-edge score and
0.0714285714285715 in mosaic score for a 0.005498533724340282 supported-role
loss. Barry accepted that substantive trade-off. The conservative common
primary panel contains 40 seed targets; `X=20` is an evaluation-only
sensitivity and passes for 34 of those 40 targets.

In later modelling, all transforms, feature handling, pseudo-background
construction, spatial folds, tuning, stopping, thresholds, target subsampling,
architecture decisions, and fits use only retained training geography. The
training spatial-fold support gate means distinct EPSG:3577 50 km anchored
support tiles per class, not records or cells treated as independent
replicates. ROC AUC is primary. Balanced accuracy, TSS, MCC, sensitivity, and
specificity are diagnostics using thresholds frozen from training-only OOF
predictions.

## Acceptance criteria

Goal 048 is complete only when all of the following hold:

1. The official IBRA source, complete-region domain, licence, retrieval time,
   and hashes are authenticated before occurrence counts.
2. Exact ALA concepts, role/reason/seasonal classifications, and the complete
   checksum-bound NVIS mapping are frozen before occurrence counts.
3. The aggregate route satisfies exact total-to-facet conservation and every
   transport ceiling for every frozen taxon, with no raw-row fallback.
4. A private checksum-bound species-cell snapshot supplies only hard `X=10`,
   `X=20`, coverage, and estimability gates.
5. The portable predictor census supplies response-free environmental,
   fragmentation, and land-use scores without material ontology failure.
6. The joint deterministic selector returns feasible, scientifically coherent,
   nonadjacent and separated triples satisfying every fixed gate and 50 km
   buffer; any frozen ambiguity is escalated and resolved transparently without
   changing the rank or using occurrence magnitudes.
7. At least 20 target species form a common primary panel estimable in retained
   training geography and all three holdouts.
8. A compact receipt and boundary-only map freeze the selected design, source
   hashes, runner-up margins, firewall, metrics, and zero outcome counters.
9. Validation replays aggregate evidence, confirms incident-count exclusion,
   proves outcome counters remain zero, and passes one focused audit.

Stop rather than weakening the contract if any transport result is
unreconciled, fewer than three whole-region solutions exist, predictor
portability materially fails, or the selected triple is scientifically
incoherent. The ranking ambiguity did stop execution and was resolved by Barry
as the prespecified scientific decision-maker; it was not silently weakened or
resolved from occurrence magnitudes.

## Later evaluation contract

Internal spatial CV will use retained training geography only. ROC AUC is the
primary outer metric. Balanced accuracy, TSS, MCC, sensitivity, and specificity
are diagnostics using thresholds frozen from training-only OOF predictions.
Primary reporting uses paired method contrasts for each common species x
region task, equal species weight within region, and equal region weight across
the three regions. Regions, species, cells, folds, subsets, and seeds are not
naive independent replicates. Calibration and occupancy-probability claims are
prohibited.

## Non-goals

This goal does not authorise occurrence-row download, canonical or bulk bird
acquisition, final response/predictor tables, model scaffolding or fitting,
prediction, thresholds, architecture revision, method rescue, manuscript
revision, or publication claims. No model was fitted, no future holdout outcome
was opened, and no prediction, threshold, or performance result was produced.
Goal 049 may expand the species universe under the frozen rules, but it cannot
rerank, substitute, or change NCP, SEH, or NNC.
