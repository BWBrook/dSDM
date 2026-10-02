# Recorded-richness follow-up and exact ANN recovery

2 October 2026, Australia/Hobart. Response to Fable's Correspondence message
810, using accepted retained inner predictions only. Read alongside the
preserved `RecordedRichnessReview-20261001.md`.

## Scientific assessment

Fable withdraws the mechanism claim, architecture/collinearity bounds, rough
ceiling and interpretation of the proposed richness-covariate experiment.
Those objections are resolved at the level of interpretation. The agreed
future priority is observation-aware independent evaluation, including an
early known-truth simulation, followed by richer habitat inputs and then
same-input learners. This review launches none of those future experiments.

The matched-network comparison reproduces and strengthens the algorithmic
finding: within the selected architecture and inputs, the pretraining procedure
changes the richness-stratified contrast. A networks-versus-trees explanation
cannot account for that comparison. It still does not identify whether the
transferred information concerns observation, ecological structure or both.
The scores are retained inner evidence under the selected architecture; outer
transport has not yet been evaluated.

## Matched-network and comparator-family checks

The exact common-support set has 142 targets: 59 of the primary 73 and 83 of
the other 84. Each included target has at least 20 presences and 20 backgrounds
in each bin in every held fold. All presences are reused against each background
bin; probabilities are averaged over seeds before equal-fold AUC averaging.

| Panel | 10–24: FT minus target-only | 25–99 | 100+ |
|---|---:|---:|---:|
| Combined 142 | +0.005336 (139/142 positive) | +0.003421 (123/142) | −0.002110 (69/142) |
| Primary 59 | +0.007548 (58/59) | +0.003884 (54/59) | −0.004263 (22/59) |
| Other 83 | +0.003764 (81/83) | +0.003092 (69/83) | −0.000580 (47/83) |

The combined values and sign counts reproduce Fable's table. Preserve the
primary/other split: the high-richness result for the other 83 has a negative
mean but a positive majority, so its direction is mixed under the agreed
descriptive rule. The combined mean reversal is not uniform target-level harm.

Fine-tuning minus the selected conventional learner also reproduces by family
within the same 142-target intersection:

| Selected conventional family | Targets | 10–24 | 25–99 | 100+ |
|---|---:|---:|---:|---:|
| RF or HGB | 103 | +0.003592 | +0.001035 | −0.003772 |
| Shallow ANN | 39 | +0.001601 | +0.001088 | −0.003059 |

Across all 157 targets, the fixed FT/conventional ensemble improves over FT
by +0.002589 where the selected conventional learner is RF/HGB (114/117
positive) and +0.000674 where it is a shallow ANN (36/40 positive). This is
consistent with greater complementary information in the selected tree scores.
The target groups differ, so the contrast does not isolate a causal effect of
comparator family or establish the gain from an untried architecture.

## The 151-target reporting-rate calculation: reproduced with a reference correction

Use each selected conventional learner's target-100 OOF scores. Within each
held fold, rank scores with `rank(method='first')`, cut those ranks into ten
bins, then pool deciles 8 and 9. Richness is frozen full donor richness minus
the focal response. The six richness bins are 10–14, 15–24, 25–49, 50–99,
100–199 and 200+. The source endpoint order supplies the tie convention;
switching to cell-ID order changes no selected membership in any of 785 folds.

The reported numbers reproduce when the denominator is the reporting rate in
the **highest nonempty bin among those top-scoring cells**, with ratios capped
at one. That bin is **100–199 for 92 targets and 200+ for 65**, contrary to
message 810's statement that it is 200+ for every target. A literal fixed-200+
reference leaves only 59 defined ratios, because 92 targets have no selected
cells in that bin and six have selected cells but no focal record.

| Definition | Targets | 10–14 | 15–24 | 25–49 | 50–99 |
|---|---:|---:|---:|---:|---:|
| Highest nonempty reference, clipped | 151 | 0.122211 | 0.203198 | 0.366538 | 0.678543 |
| Same 151, pooled 100+ reference, unclipped | 151 | 0.125706 | 0.203198 | 0.376410 | 0.711872 |
| Literal fixed 200+ reference, clipped | 59 | 0.053315 | 0.101077 | 0.214731 | 0.500501 |

The first two rows match every rounded number in Fable's revised table. The
original review's different pooled-quintile, ties-kept rule remains preserved;
it uses 157 targets and returns 0.1212/0.2036/0.3658/0.6721. These definitions
show the same direction of association but are not the same estimand.

The six excluded targets are exactly the named species. Their 200+ top-score
reference cells number **2, 1, 1, 1, 1 and 2**, respectively: *Lophorina
paradisea*, *Melithreptus gularis*, *Orthonyx temminckii*, *Ptilinopus superbus*,
*Sericornis citreogularis* and *Tregellasia capito*. Each has zero focal records
in those cells. These very small denominators provide little independent
evidence of habitat confounding; their exclusion is an arithmetic requirement
for a defined ratio. Model top scores also do not establish true suitability.
No detection-probability or unrecorded-presence interpretation follows.

## Prospective reporting and implementation status

The background-composition addition is implemented and fixed before outer
access in `OuterDiagnostics-20261001.md`. Report per-target bin counts/shares
and their equal-target regional summaries beside the unchanged headline.
Summed counts are target-background pairs, not unique cells. The exact
decomposition averages each target's weighted contrast; multiplying separately
averaged weights and contrasts would discard their covariance. Ten focused
scoring tests pass, including sparse/empty bins and unequal target counts.

Fable's identical-grid comparison of inner-fold and retained-full scores cannot
be made from existing target-model states: the fitted target weights were not
saved. Pretraining trunks are insufficient. `OuterPreparation-20260929.md`
records that additional fitting would be required and retains the fixed OOF
thresholds. A response-free score comparison would assess score scale/ranking,
not empirical calibration against outcomes.

All **80** missing ANN epoch budgets now pass independent exact recovery:
2,000 unique fold/seed receipts, 4,000 discovery/replay fits, 5,555,454 accepted
prediction rows and 264 returned-file hashes checked. Original per-seed vectors
were unavailable, so exact comparison is to the accepted seed means. Nectar
finished at 03:37:36 AEST, returned verified evidence and parked at 03:41:08;
the live morning check confirms ACTIVE / c3.xsmall with no batch workers.
The failed Deep attempt remains preserved.

The retained-full orchestrator, complete frozen prediction closure and
actual-runtime qualification still remain. Outer responses are sealed. Barry's
opening authorization persists and needs no reconfirmation.

## Evidence

`scripts/goal052_effort_followup.py` and
`evidence/seawfb_dsdm/goal052/effort-followup-20261002.json` retain exact definitions,
input/source bindings, target-level bin counts, both reference calculations and
all subgroup results. The earlier review and accepted inner artifacts remain
unchanged. The separate ANN audit is `scripts/goal052_ann_recovery_review.py`
and `evidence/seawfb_dsdm/goal052/ann-recovery-review-20261002.json`.
