# Authorized outer assessment: retained-full preparation

29 September 2026, Australia/Hobart. Barry explicitly authorized opening:

> I agree with Fable, yes to open the sealed outer test. If you disagree or want
> to propose modifications to this, Astra, go ahead and propose on the board.

This supersedes the pending-Barry-decision status of
`OuterPreopening-20260927.md`. Astra agrees with opening. No further opening
permission is requested. The earlier note's reporting and descriptive reading
rules remain proposals for Fable's response; model concurrence has not been
reported. No outer outcomes have been exposed by this preparation.

## Reporting and expectations

Retain the earlier note's three regional roles, common 73 and frozen regional
secondary panels, X10 primary/X20 diagnostic distinction, fixed training-OOF
thresholds, and all four full-fine-tuning comparisons plus both mechanistic
contrasts. Goal048's matched-neural and selected-conventional questions lead;
the Goal052 q comparisons remain fully reported. Give each species equal
weight within region and each region equal weight in the common-panel macro
average. No raw-cell pooling or region-dependent model selection.

Expect attenuation relative to the inner results, plausibly greatest in SEH;
this is an expectation, not an acceptance condition. The proposed transfer
description is unchanged: positive mean AUC difference and a strict majority
of positive target differences together indicate consistent positive direction;
one alone is mixed; neither is consistent nonpositive. These labels carry no
significance, equivalence or practical-importance claim. Report continuous
differences and every regional result regardless of the label. A broad
across-region benefit requires the positive pattern for both main comparators
in all three regions.

## Concrete refit proposal

Use target 100%, auxiliary full and selected `seawfb_scale`, with one fitted
model per seed supplying predictions for all three regions. Retain the entire
focal-block exclusion, equal total auxiliary-head weights, natural prevalence,
all region/buffer exclusions and the existing retained-full feature transform.
Do not substitute any of the 900 inner checkpoints for retained-full fits.

1. **Pretraining:** for each focal block, take the median of the 25 accepted
   selected epochs (five folds by five seeds) for `seawfb_scale/full`, using
   the same rounding convention as the target refit rule. Apply that fixed
   block-specific budget to each of five new paired-seed refits. Do not pool
   blocks or choose epochs using outer predictions. This extends the existing
   target aggregation convention; it is a prospective choice requiring review.
2. **Neural targets:** consume each target/arm's already stored rounded median
   of 25 selected epochs, with five paired seeds and mean predicted probability.
   Preserve the target head initialisation pairing and the frozen-trunk check.
3. **q controls:** fit one full-auxiliary q model per focal block on retained
   training only, preserving Goal051's head weighting, regularisation and
   qualified convergence schedule. Standardise q on each target's full retained
   training rows, then reuse that transform for prediction. Retain the ordinary
   selected conventional family/candidate for q augmentation; do not retune it.
4. **Conventional refits:** preserve selected candidate identities and their
   existing family-specific seed counts. A real metadata gap affects the 40
   selected shallow-ANN targets: Goal051 persisted selected-epoch ranges, not
   the individual epochs needed to derive a median. Both ordinary and q fits
   need their own budgets. Do not use a range midpoint or a maximum as a median.
5. **Epoch recovery:** the preferred resolution is deterministic replay of only
   those selected ANN procedures on the original retained-training folds,
   candidates and seeds. Save the missing epochs and check regenerated fold
   predictions against the accepted private seed-averaged fold predictions
   before deriving each
   ordinary/q rounded median. This recovers the existing procedure without a
   new search. A mismatch is a preparation failure to investigate before opening.

Goal051 saved those fold averages rather than each seed's prediction vector;
the recovery check must acknowledge that granularity. Preserve each recovered
seed's epoch and predictions in the new evidence, using the original bound
source/runtime and deterministic row ordering. Do not weaken numerical
agreement requirements after seeing a discrepancy.

Seed integers and namespaces, training-row digests, head sets, feature order,
q means/SDs, threshold values and all source/runtime hashes must appear in the
execution manifest before fitting. The metadata inventory is preparatory and
does not itself qualify an implementation or a runtime.

## Inventory and implementation boundary

`scripts/goal052_outer_inventory.py` produces
`evidence/seawfb_dsdm/goal052/outer-inventory-20260929.json` from accepted summaries,
frozen panel metadata and pretraining JSON receipts. It reads no response rows
or fitted-state payloads. It records the available epochs, thresholds and
candidates, and exposes the conventional ANN budget gap.

The intended full/full inventory is 50 shared pretraining fits, 10 q fits,
3,140 neural target fits and 1,042 conventional fits across ordinary/q arms:
**4,242 models**, excluding convergence retries and epoch-recovery replay.
There is no reason to triple fitting by region. Allocate compute after measuring
the retained-full profile; the previous inner throughput is not an outer ETA.

A separate outer implementation is still needed. Keep the accepted inner source
and outputs immutable. Build the prediction-side reader from predictor/domain
artifacts, with no response membership imports. Generate scores for the complete
fixed whole-region domain grids so target-specific outcome masks are not
needed before prediction. Hash and close the complete three-region prediction
set, fitted models and frozen thresholds before opening membership/background
data for the fixed scoring pass. Verify the separation with synthetic contract
tests and qualify the actual fitting runtime before production.

**1 October coverage correction:** the earlier phrase “predictor-complete”
was too restrictive. Goal049's frozen evaluation masks never excluded cells
with missing predictors; Goal050 retained them and used frozen imputation.
Predict all 144,860 domain cells in NCP/SEH/NNC using the retained-full
transform, then apply unchanged response masks only in scoring. Goal048's
95% completeness requirement was a whole-region feasibility gate, not a row
filter. This corrects implementation coverage without changing the estimand.

Unexpected primary class/support failure, missing predictions or numerical
failure stops acceptance with explicit counts; expected X20 non-evaluability
remains visible as NA. No target deletion, rescue model or threshold revision
follows from outer scores. Keep recurring polling deleted; use the established
PBS completion/abort email route when PBS work is launched.

Fable's requested review is now specific: reporting/sign rules, the pooled
within-block pretraining epoch proposal, and retained-only ANN epoch recovery.
Barry's opening decision is settled. Preparation and review remain, and should
not be mistaken for a completed outer test.
