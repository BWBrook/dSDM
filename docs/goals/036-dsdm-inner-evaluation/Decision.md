# Goal 036 decision

## Prespecified analysis

Continuous relative habitat suitability remains primary.  Within every
species, endpoint, and method, final inner predictions are the arithmetic mean
of the frozen seed scores.  One threshold is selected from the concatenated
five-fold averaged OOF scores by maximising TSS (equivalently balanced
accuracy), using finite representable midpoints plus the two extremes and the
sorted lower median of tied maximisers.  Classification is `score >=
threshold`.  Leave-one-fold-out thresholds are diagnostic only.

ROC AUC and TSS are co-primary.  Average precision, MCC, sensitivity,
specificity, confusion counts, prevalence, seed spread, and threshold spread
are supplementary.  A classless fold receives `NA` for metrics requiring both
classes, with its support retained; no balance is manufactured.

The best conventional comparator is selected separately for each species and
endpoint from the five already tuned families by highest mean fold ROC AUC,
then mean fold TSS, then stable family identifier.  This is an inner selection
surface and is not an unbiased performance estimate.  All five family results
remain visible.

The three primary contrasts are full multi-head fine-tuning versus: (1) the
matched target-only residual MLP, (2) target MLP plus `q_deep`, and (3) the
separately selected best conventional family.  Evidence is paired by species
and fold.  Seeds and nested ladders expose stability but are not ecological
replicates.  There are no naive p-values, row bootstraps, or arbitrary minimum
effect threshold.

## Interpretation boundary

Goal 036 can recommend a frozen method for the later outer assessment.  It
cannot claim outer performance, occupancy probability, broad mammal
generality, or bird transferability.  Tasmania remains the deliberately hard,
high-prevalence, within-range, seven-auxiliary-species case.

## Result

Pending execution and review.
