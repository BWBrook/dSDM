# Goal 048 - SEAWFB bioregional outer-design freeze (v1.1)

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

Version 1.1 repairs only the feasibility transport and prospective ordering.
It does not change the response-blind 100-name feasibility seed ledger, species
roles, seasonal policy, 16-region prospective rule, response-free scores,
three-region joint selector, 50 km buffers, estimability thresholds, or
development firewall.

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
- The existing 16-region prospective rule and required Brigalow Belt South
  completion remain unchanged. Tasmania remains training geography.
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
  rule in the v1.1 config.
- Richness and effort summaries remain prohibited as model predictors.

The embedded 100-name list is a mandatory, response-blind feasibility seed,
not the final ceiling on the bird pretraining universe. Goal 048 uses eligible
seed members conservatively for `X=10`, `X=20`, and the at-least-20 common
target feasibility gate. Goal 049 may expand effort, auxiliary, and target
universes under the same frozen taxonomic/ecological rules before canonical
acquisition and before any holdout outcome access. It cannot change,
substitute, or re-rank the three selected regions. Expanding donors can only
relax support relative to this seed screen; final exact labels and panels are
reconstructed from canonical Goal 049 data.

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
6. The joint deterministic selector returns one feasible, stable,
   scientifically coherent, nonadjacent and separated triple satisfying every
   fixed gate and 50 km buffer.
7. At least 20 target species form a common primary panel estimable in retained
   training geography and all three holdouts.
8. A compact receipt and boundary-only map freeze the selected design, source
   hashes, runner-up margins, firewall, metrics, and zero outcome counters.
9. Validation replays aggregate evidence, confirms incident-count exclusion,
   proves outcome counters remain zero, and passes one focused audit.

Stop rather than weakening the contract if any transport result is
unreconciled, fewer than three whole-region solutions exist, ranking is
ambiguous or unstable, predictor portability materially fails, or the top
triple is scientifically incoherent.

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
revision, or publication claims. This v1.1 repair step also does not authorise
implementation or execution of the aggregate route.
