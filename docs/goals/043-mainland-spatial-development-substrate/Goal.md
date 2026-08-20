# Goal 043 - mainland spatial development substrate

## Objective

Freeze the mainland-only spatial partitions, split-authorised response tables,
and split-fitted predictor transformations needed for the southeastern-
mammal geographic-transfer experiment. Tasmania remains a sealed evaluation
surface throughout.

## Acceptance criteria

1. Compare only 100, 50, and 25 km EPSG:3577 blocks over 64 deterministic
   five-fold assignments per scale. Prefer the largest feasible scale, then
   response balance, map balance, and seed; model performance is forbidden.
2. Require every fold to contain 15-25% of mainland map cells, at least 30
   presences and 30 X=3 backgrounds for each shared target in validation, and
   at least 100 presences and 100 X=3 backgrounds for every response head in
   the complementary training set.
3. Recompute donor support and nearest-target distance separately for every
   fold and role using only records assigned to that role. Preserve X=2/X=5
   sensitivities and never use the Goal 042 full-data reference directly for
   modelling.
4. Fit five fold-specific transforms and one reserved full-mainland transform
   from continuous-complete mainland training map cells. Use population-SD
   scaling; do not impute continuous nodata; map categorical missing and unseen
   levels to distinct sentinels.
5. Exclude continuous-nodata response cells with a hard maximum of 2% over any
   whole mainland target-class. Record fold-specific loss descriptively.
6. Keep cell assignments, split responses, and detailed diagnostics ignored.
   Track exact transform parameters, aggregate evidence, checksums, and the
   final decision without cell identities or coordinates.

## Stopping boundary

Do not fit models, choose architecture or hyperparameters, evaluate
performance, access Tasmania evaluation responses, make maps, or revise the
manuscript.
