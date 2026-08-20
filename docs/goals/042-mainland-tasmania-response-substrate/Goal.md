# Goal 042 - mainland-to-Tasmania response substrate

## Objective

Build a provenance-bound response substrate for the southeastern-mammal
geographic-transfer experiment. Mainland development uses all 21 observed taxa
as target-group support and the 20 taxa meeting the frozen response-head tier.
Tasmania is a separate evidence-based evaluation surface for the five shared
targets.

## Acceptance criteria

1. Bind to the accepted Goal 040 species-cell and camera authorities and the
   complete Goal 041 24-predictor table.
2. For each of 20 mainland response heads, preserve presence, the number of
   distinct other support taxa, nearest-target distance, primary X=3 response
   eligibility, and nested X=2/X=5 sensitivity eligibility.
3. Treat the full-mainland output as a reference only. Provide a materialiser
   that later partitions can call using only records authorised for that split.
4. Build Tasmania responses for *Dasyurus maculatus*, *Notamacropus
   rufogriseus*, *Pseudocheirus peregrinus*, *Trichosurus vulpecula*, and
   *Vombatus ursinus* from ALA or camera presence and camera survey-supported
   absence, with presence precedence and no target-group pseudoabsence.
5. Prove every response cell binds to the Goal 041 predictor table. Tasmania
   must never enter mainland pretraining or fine-tuning, and each cross-species
   target must exclude itself from the other 19 pretraining heads.
6. Keep both cell-level tables ignored. Track only aggregate counts, checksums,
   cohort identities, rules, limitations, and a `ready`, `repair`, or `blocked`
   decision.

## Stopping boundary

Stop before spatial partitioning, split-fitted transformation, model fitting,
architecture work, performance evaluation, maps, or manuscript claims.
