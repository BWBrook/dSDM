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

**Supported, with a conditional method-freeze recommendation and no claim of
dSDM superiority.**  All 40 Goal035 leaves aligned exactly with the 952
selected Goal029 OOF checkpoints over 1,313,641 conventional score rows.  The
analysis contains 616 species x endpoint x method strata and 3,080 fold
summaries.  Independent reconstruction reproduced every threshold, ROC AUC,
TSS, confusion matrix, MCC, family selection, and contrast.  All held folds
contained both classes.  Outer attempted/opened remained `0/0`.

### Primary contrasts

Median species-level differences in mean-fold ROC AUC are:

| Target endpoint | Multi-head - target only | Multi-head - q deep | Multi-head - best conventional |
|---|---:|---:|---:|
| 25% / ladder 00 | +0.0129 | +0.0223 | -0.0335 |
| 25% / ladder 01 | +0.0062 | +0.0097 | -0.0290 |
| 25% / ladder 02 | +0.0187 | +0.0119 | -0.0224 |
| 50% / ladder 00 | +0.0055 | -0.0019 | -0.0328 |
| 50% / ladder 01 | -0.0153 | -0.0182 | -0.0350 |
| 50% / ladder 02 | +0.0180 | +0.0178 | -0.0225 |
| 100% / full | -0.0027 | -0.0064 | -0.0390 |

Across all 56 species-endpoint strata, full multi-head exceeded target-only
ROC AUC in 35 and `q_deep` in 32, with median differences of +0.0067 and
+0.0118 respectively.  These were not stable universal gains: the paired seed
range crossed zero in 40/56 and 39/56 strata, and fold wins were close to half.
The reduced-data pattern is compatible with a modest pretraining benefit, but
the full-data endpoint provides no aggregate lift.

The scalar controls did not explain the signal.  Relative to target-only, the
median ROC-AUC differences were -0.0019 for `q_linear` and -0.0024 for
`q_deep`; `q_deep - q_linear` was effectively zero.  Pooled legacy pretraining
and frozen-trunk transfer were often as good as or better than full multi-head
fine-tuning.  The species response was heterogeneous: transfer was repeatedly
positive for *Notamacropus rufogriseus*, *Trichosurus vulpecula*, and
*Vombatus ursinus*, but repeatedly negative for *Dasyurus viverrinus* and often
for *Thylogale billardierii*.  This is mechanism evidence, not a single
winning-neural-architecture result.

The conventional benchmark was materially stronger.  The selected family beat
full multi-head ROC AUC in 53/56 species-endpoint strata; the median difference
for multi-head was -0.0326, and it won only 94/280 paired folds.  At the full
endpoint, selected conventional models won all eight species.  Random forest
was selected in 24/56 strata, shallow ANN in 21, histogram boosting in 10, and
elastic net in one.  This dominance is not solely a post-selection artefact:
the fixed random-forest family alone beat multi-head in 44/56 strata.

### Ecological interpretation

Observed prevalence ranged from 0.333 to 0.968.  The thinnest held folds had
only 10 *Thylogale* negatives and 13 devil negatives, and leave-one-fold-out
threshold diagnostics were sometimes wide, especially for *Thylogale*.
Continuous ROC AUC therefore carries more stable information than a binary map
in this high-prevalence, within-range case.  The result is a credible null or
weak-transfer result for this deliberately difficult Tasmanian regime; it does
not falsify multispecies pretraining in a richer bird assemblage.

### Freeze recommendation

Proceed to an outer-ready final-refit tranche, but do not tune or rescue the
dSDM after seeing these results.  Freeze all eleven predeclared methods for the
single outer assessment so that secondary mechanism paths are not selectively
dropped: six neural paths plus all five selected-within-family conventional
models.  Keep the three primary contrasts unchanged and treat pooled, frozen,
and `q_linear` paths as secondary diagnostics.  The outer assessment, not the
inner surface, will decide spatial held-patch performance.  Outer access is not
authorised by this decision.
