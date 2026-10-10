# Tasmania pseudoabsence-removal sensitivity: bounded run proposal

**Status:** proposal only; no run is authorised by this document.  Preparing or
reviewing this plan must not fit a model, open another sealed result, score an
existing prediction, or modify a source, model, or production configuration.

## Decision requested

Choose explicitly between these endpoint scopes, then approve, defer, or reject
the sensitivity:

- **Recommended bounded option:** all eight species at the full-data
  (`fraction100`) endpoint, using the primary-selected conventional candidate
  as a fixed comparator.  This requires 1,122 production fits, tests the mapped
  primary endpoint, and leaves reduced-fraction endpoints untested.
- **Protocol-wide option:** all eight species at all seven endpoints.  This
  requires 8,125 production fits and preserves the endpoint-unqualified wording
  of the original protocol.

For either option, the proposed contract is:

1. compare the matched target-only residual MLP, the full multi-head fine-tune,
   and the primary-selected conventional candidate for each species and chosen
   endpoint;
2. remove rows with `pa_type == "pseudoabsence"` from **target training only**
   in every inner and outer fitting role;
3. retain the original, fixed inner and outer evaluation rows, including both
   survey-supported absences and pseudoabsences; and
4. derive sensitivity-specific out-of-fold thresholds, then evaluate paired
   changes in ROC AUC, TSS, MCC, source-specific specificity, and mapped
   suitability ranks.

This is the least disruptive interpretation of the prespecified
"pseudoabsence-removal sensitivity refit" in
[`tasmanian_modelling_protocol.md`](tasmanian_modelling_protocol.md).  It
changes the model's exposure to pseudoabsences while holding the evaluation
sample constant.  Removing pseudoabsences from evaluation as well would answer
a second question because both the fitted model and the evaluation estimand
would change.  If desired, survey-absence-only metrics can be computed as a
clearly labelled descriptive secondary view from the same predictions; they
must not replace the fixed-evaluation primary contrast.

The original protocol did not qualify the sensitivity by endpoint.  The
proposed full-endpoint restriction, training-only interpretation, threshold
recalibration, frozen conventional candidates, and exact map-change summaries
were not fully specified before the primary outer panel was opened.  Barry's
endpoint-scope choice and approval are therefore substantive post-opening
decisions.  The run must be described as an implementation of a prespecified
sensitivity question, not as a fully prospective confirmatory test.

## Scientific target and inferential scope

The primary Tasmania target remains a species-specific **relative
habitat-suitability index over the accepted 71,023-cell structural domain
`D_struct`**, conditional on the accepted 2001--2025 response construction,
predictor stack, spatial partition, and model families.  It is not occupancy,
abundance, detection probability, or a causal effect of habitat.

The sensitivity estimand is the paired change in held-block predictive
performance and domain-wide suitability ranking when pseudoabsences are
excluded from target-model training, with all other accepted inputs and
algorithms fixed.  Its inference is limited to these eight species, this
response and predictor construction, and the accepted Tasmania spatial blocks.
It does not identify whether individual pseudoabsences are false absences, nor
does it correct imperfect detection or opportunistic-record selection.

The observation process combines opportunistic presence records, camera-survey
detections and survey-supported non-detections, and rule-derived
pseudoabsences.  Equal row weights and no resampling or class balancing remain
fixed.  Spatial macro/microcluster partitions reduce direct spatial leakage but
do not establish independence, stationarity, or transferability beyond
`D_struct`.  Removal can change class balance, fitted calibration, early
stopping, and effective spatial coverage simultaneously; results therefore
show sensitivity to the accepted pseudoabsence construction, not the isolated
causal effect of false absence.

Auxiliary pretraining and the auxiliary inclusion vector `q` already exclude
pseudoabsences.  They are outside the perturbation.  Accepted fold-specific
auxiliary states and `q` must be reused byte-for-byte; no auxiliary refit or
new `q` estimate is permitted.

## Frozen inputs and provenance authority

Implementation must bind, by content digest and accepted receipt, the
authorities for Goals 021, 024, 025, 026, 027, 029, 035, 036, and 037.  The
primary comparison is the accepted one-shot Tasmania outer assessment in
`evidence/tasmania_outer_assessment/20261005/receipt.json`, with its exact
configuration, response-access digest, fold memberships, thresholds, model
digests, and prediction digests.

Historical Goal037 executable inputs must come from the immutable
`goal037-ce70bf1` archive under
`data/processed/dsdm/tasmania-outer-assessment-20261005/archive/`, rather than
being silently reconstructed against the current `model_adapters` or
`uv.lock`.  Current dependency drift is a reason to bind the historical
runtime, not a reason to weaken provenance checks.

Filtering and source attribution must start from the canonical, hashed,
source-tagged Goal025 rows.  Goal035/037 modelling arrays do not retain enough
source identity to reconstruct this perturbation or its source-specific audit.
The Goal025 identity must be joined to the accepted modelling membership by
canonical response-free row ID; inferred array position or a regenerated raw
payload is not an acceptable substitute.

Before any fit, a new run manifest must record:

- all authority receipt, source, configuration, archive, runtime, and access
  digests;
- the eight species, chosen endpoint set, three methods, accepted neural and
  family-specific conventional seed policies, threshold rule, and the exact
  frozen conventional candidate for every species and endpoint in scope;
- canonical hashes of the baseline, retained, and excluded target-row ID sets
  for every species, fold, and separate discovery, stopping, replay, and outer
  fitting role, plus the equality
  `retained = baseline - pseudoabsence`;
- class and absence-source counts for every species by fold and separate role,
  including the actual number of pseudoabsences removed from every affected
  role, without exposing coordinates or row-level response data;
- response-free evaluation-membership hashes established before prediction
  closure and equal to the accepted primary membership;
- target support-mask identities, retained-row family-encoder identities, and
  the reused Goal026 transform identities; parent auxiliary-state and `q`
  digests; all initialization, stopping, replay, epoch, fitted-model,
  prediction, and map digests; and
- planned and realised fit inventories, worker/thread settings, response-read
  counters, failure/abstention states, and private-versus-tracked artifact
  locations.

Held source counts are derived only after prediction closure and response
access, then recorded with the scored output.  The tracked primary receipt does
not contain a complete held source-count baseline, so the new counts cannot be
required to match a nonexistent receipt field; evaluation **membership** can
and must match by response-free ID before closure.

The count census is a new pre-run aggregate derived from canonical Goal025
source tags, not permission to inspect or publish raw response rows.  Existing
aggregate evidence shows total included survey-supported absences of 125, 145,
173, 581, 138, 101, 218, and 633 in
protocol species order.  The corresponding outer held-set negative counts are
19, 22, 31, 111, 25, 10, 50, and 104, giving conservative lower bounds of 106,
123, 142, 470, 113, 91, 168, and 529 survey-supported absences in each full
outer training set.  This supports overall feasibility but does not prove
class support in every inner fitting and stopping role.  The aggregate census
must pass before fitting.  Thylogale's outer held negatives are all
survey-supported; Sarcophilus has nine survey-supported absences and one
pseudoabsence in its outer held set.  Pseudoabsence-specific specificity is
therefore undefined for Thylogale there and must be reported as `NA`, not zero
or omitted.

## Fixed model scope for the bounded option

The two neural paths are `target_only_resmlp` and
`multihead_full_finetune`, with their accepted Goal035 architectures,
optimisers, seeds, stopping rules, replay rules, and ensemble aggregation.  The
multi-head target stage alone receives the filtered target view.  Its accepted
auxiliary state is immutable.

The conventional family, exact candidate, and hyperparameters are frozen to
the Goal036 primary selection at the full endpoint; sensitivity data must not
trigger reselection:

| Species | Frozen family | Frozen candidate |
|---|---|---|
| *Thylogale billardierii* | histogram gradient boosting | `hgb00` |
| *Notamacropus rufogriseus* | histogram gradient boosting | `hgb00` |
| *Trichosurus vulpecula* | random forest | `rf00` |
| *Pseudocheirus peregrinus* | shallow ANN | `ann04` |
| *Vombatus ursinus* | shallow ANN | `ann04` |
| *Sarcophilus harrisii* | random forest | `rf01` |
| *Dasyurus maculatus* | random forest | `rf02` |
| *Dasyurus viverrinus* | random forest | `rf00` |

Freezing these comparators isolates the row-removal perturbation.  They are the
primary-selected comparators, not claims about the best family or candidate
after filtering.  Because they were selected after examining primary inner
results, comparisons involving them remain conditional on that selection and
do not propagate model-selection uncertainty.

## Deterministic fitting and evaluation path

For each species and each of the five inner folds, construct a target-training
view by exact ID subtraction.  Remove pseudoabsences separately from discovery,
early-stopping, replay, and outer target-fitting roles.  Fit sensitivity-specific
target masks and family encoders from the retained target rows.  Reuse the
accepted Goal026 feature transforms fitted from the corresponding training
map-cell memberships; do not refit them from response rows.  Do not change map
membership, predictor values, or fold allocation.

Before any fit, prove both outcome classes in each discovery, stopping, replay,
and outer role separately.  Where the baseline role contains pseudoabsences,
the excluded count must be positive and equal the recorded Goal025-tagged
pseudoabsence membership.  A failed role aborts the entire sensitivity panel;
there is no partial-species scoring, role pooling, or substitution after seeing
results.

Run neural discovery and deterministic replay on the filtered target view with
the five accepted seeds.  Run the frozen conventional candidate on the same
filtered view with its accepted seed policy; shallow ANN inner fits require
both discovery and replay.  Predict every original held row,
including pseudoabsences, and average seed probabilities before metric
calculation.  From the pooled inner out-of-fold sensitivity predictions, derive
a new threshold separately for each species and method using the accepted
maximum-TSS rule and lower-median tie rule.  Reusing primary thresholds would
confound the model perturbation with an arbitrary retained calibration scale.

Refit each method on the filtered full outer-training view.  Neural outer
refits use the accepted lower-median epoch rule applied to the new sensitivity
inner runs.  Predict the original outer held membership and score only after
the complete prediction set and all required digests are closed.  Any missing
prediction or membership mismatch aborts scoring for the entire panel.

Apply the accepted primary models and sensitivity models to the same frozen
71,023 `D_struct` rows with the same outer transform.  This prediction step
adds no fit.  Store cell-level predictions privately.  Tracked output may
contain aggregate rank and difference summaries and rendered maps, but no
response-row coordinates.

## Paired comparisons

For each species and method, report sensitivity minus primary for ROC AUC, TSS,
and MCC on the complete fixed held set.  Report specificity separately among
survey-supported absences and pseudoabsences, always with its numerator and
denominator.  Undefined source strata remain `NA`.  Report the corresponding
primary and sensitivity values, not deltas alone.  Report both the primary and
sensitivity thresholds and their delta.  Because the threshold is re-estimated,
changes in TSS, MCC, and source-specific specificity are full-pipeline effects
of filtering plus threshold recalibration.  ROC AUC and map ranks are
threshold-free.

Produce exactly 24 primary--sensitivity map pairs: eight species by three
methods at `fraction100`.  Average probabilities over the accepted seeds before
ranking.  Assign tied averaged probabilities their average (midrank), convert
to percentile rank on the common 71,023 cells, and define signed displacement
as sensitivity percentile rank minus primary percentile rank.  For each pair,
report Spearman rank correlation and the median, 2.5th percentile, and 97.5th
percentile of that signed displacement, and render the signed probability-
difference map.

Define the top decile deterministically as the first 7,103 cells after sorting
by descending seed-averaged probability and then ascending canonical cell ID to
break boundary ties.  Report top-decile retention as
`|primary_top ∩ sensitivity_top| / 7,103`, with the intersection count and
denominator.  The 24-pair scope, midrank rule, signed displacement summaries,
and fixed-size top-decile rule are post-opening operational choices proposed
because they give paired, threshold-free domain summaries without choosing a
map cutoff from the sensitivity outcome.  They must be frozen before fitting.

Also report, descriptively:

- multi-head minus target-only and multi-head minus frozen-conventional
  contrasts under the sensitivity; and
- the change in each of those contrasts from the primary assessment.

These are paired descriptive contrasts.  Do not add row-bootstrap confidence
intervals or per-species null-hypothesis tests: spatial dependence,
model-selection conditioning, and eight-species multiplicity would make them
misleading.  Cross-species summaries must show all species and must not treat
them as independent replicates of a superpopulation.

## Fit inventory and resource basis

The recommended scope requires exactly **1,122 new target-model fits** if all
pre-run gates pass:

| Component | Calculation | Fits |
|---|---:|---:|
| Neural inner discovery and replay | 8 species x 5 folds x 2 methods x 5 seeds x 2 passes | 800 |
| Neural outer refits | 8 species x 2 methods x 5 seeds | 80 |
| Conventional inner random-forest fits | 4 species x 5 seeds x 5 folds | 100 |
| Conventional inner histogram-gradient-boosting fits | 2 species x 1 seed x 5 folds | 10 |
| Conventional inner shallow-ANN discovery and replay | 2 species x 5 seeds x 5 folds x 2 passes | 100 |
| Conventional outer refits | 4 RF x 5 seeds + 2 HGB x 1 + 2 ANN x 5 | 32 |
| **Total** |  | **1,122** |

There are no auxiliary or `q` fits.  Domain mapping entails about 8.0 million
model-cell predictions before seed aggregation, which is modest relative to
the fitting work.

The accepted Goal035 full-endpoint slice for these two neural methods contains
400 logical and 800 physical inner fits; its recorded fit-time sum is 150.674
seconds (median 0.292, maximum 1.347 seconds).  The matching Goal037 neural
outer slice contains 80 fits with a 5.224-second recorded fit-time sum.  The
Goal034 real six-path sentinel recorded a 17.75-second median and 408.7 MB peak
RSS across 41 fits, showing why a runtime smoke remains necessary despite the
faster later receipts.  For the conventional path, the active
`evidence/conventional_baseline_calibration/receipt.json` passes the thread
contract and selects four workers.  Goal029 Log line 291 records that the
827.757-second 62-leaf trial preceded the one-thread repair; it is diagnostic
history, not a valid production timing estimate.

These receipts make same-day completion plausible but leave it unqualified
until the fixed smoke runs because filtering can alter stopping epochs and
current software has drifted.  Use the historical Mac lane with three
single-threaded workers for the neural target stages.  For conventional
provenance parity, use the
historical Linux/x86 Goal029 environment on `deep-server` with four
single-threaded workers, after the ordinary availability and runtime smoke;
do not route there merely because it is larger.  Set production wall-time,
peak-RSS, worker, and private-storage limits from both fixed smoke receipts;
this proposal does not assign unsupported numeric caps.

Running the sensitivity at all seven endpoint fractions is a materially
different choice requiring **8,125 target fits**: 6,160 neural and 1,965
conventional.  Nothing in the frozen protocol resolves full-only versus all
fractions.  The full-only run is recommended because it answers the mapped
primary-result question at roughly one seventh the fit burden, while explicitly
accepting that reduced-fraction sensitivity remains unknown.

## Smoke, acceptance, and failure rules

Implementation is needed; no currently proven command should be inferred from
this proposal.  Before production, an independent reviewer must verify the
frozen manifest and filter implementation.  Then run:

1. a synthetic membership/filter suite that covers exact subtraction,
   class-loss refusal, held-membership immutability, source-count accounting,
   support-mask recomputation, digest tampering, auxiliary-state mutation, and
   prediction closure; and
2. one non-promotable real smoke fixed in advance to *D. viverrinus*, canonical
   inner `fold01`, neural seed 31031 for both methods (discovery plus replay),
   and the selected random-forest `seed00`, repeated from clean state.  This is ten
   physical fits across the two repetitions; and
3. one non-promotable shallow-ANN `ann04` lifecycle smoke fixed to
   *P. peregrinus*, canonical inner `fold01`, `seed00`, discovery plus replay,
   repeated from clean state.  This adds four physical fits.

The bounded option therefore entails 1,122 production fits plus 14
non-promotable smoke fits, or **1,136 physical executions**.  Thylogale contains
no pseudoabsences and is the end-to-end negative control within the 1,122
production fits: under the frozen runtime, its inner and outer memberships,
thresholds, predictions, metrics, and its three paired map products regenerated
from the accepted primary models must reproduce the accepted primary result
exactly under the deterministic contract.

Neither smoke case nor fold may be replaced after seeing its outcome.  A
missing class in any separate discovery, stopping, replay, or outer role is a
whole-panel failed gate, not grounds to swap folds, merge strata, add weights,
restore pseudoabsences, or report unaffected species alone.

Production is acceptable only if all of the following hold:

- the source census proves both outcome classes separately in every required
  discovery, stopping, replay, and outer role and records actual
  pseudoabsence removal in each affected role;
- retained target membership is exactly baseline membership minus
  pseudoabsence membership, with zero pseudoabsences in every target-training
  role;
- inner and outer evaluation membership, fold allocation, predictors,
  transforms, candidate identity, seed policy, and weighting equal the primary
  contract;
- every auxiliary state and `q` object is byte-identical to its accepted
  parent;
- both repetitions of each smoke reproduce memberships, stopping epochs,
  predictions, model digests, and source counts within the frozen deterministic
  contract;
- the realised bounded-option inventory is exactly 1,122 successful production
  fits and 14 non-promotable smoke fits, or the whole panel closes as an
  explicit failure without scoring;
- prediction closure precedes any response access for scoring; and
- an independent replay recomputes receipt hashes, metrics, source-specific
  denominators, rank summaries, and map summaries from the closed predictions.

## Residual risks and recommendation

The sensitivity cannot distinguish false pseudoabsences from beneficial
background contrast.  Rare outer negatives, especially ten for Sarcophilus,
make specificity and thresholded metrics unstable.  Source removal can expose
spatial covariate gaps, and fixed blocked folds do not remove spatial or
temporal autocorrelation, non-stationarity, observation bias, calibration
shift, or extrapolation within `D_struct`.  Five seeds quantify only part of
optimisation variability.  The frozen conventional choice omits selection
uncertainty, and the opened primary results mean the newly fixed details could
have been influenced by observed outcomes even though the sensitivity question
predates opening.

**Recommendation:** approve the full-endpoint, training-only contract above if
the result will materially affect the Tasmania interpretation; otherwise defer
it and state that the prespecified sensitivity remains unrun.  Do not run the
all-endpoint alternative without a separate scientific justification.  An
independent pre-run contract review and post-run receipt/metric replay would
materially increase confidence because the central risk is provenance and
estimand drift, not raw compute failure.
