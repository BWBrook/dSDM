# Step 3c review: full reconstruction draft

Codex (`gpt-6.1-sol`), 13 November 2026. Reviewed `8b55501`,
`manuscript/reconstruction/03c-full-draft.md`, correspondence thread 162,
message 3360, and the owning accepted analysis evidence.

**Verdict:** keep the lean draft. Its scientific argument is coherent, and
there is no reason to expand it toward 4,800 words. Correct the design
description, scoping and display budget below before integration. No new fits
or ecological analysis are required.

**Completed edit:** Table 1 now contains all 27 AUC values for nine case and
assessment rows, including the three-region bird mean. Its combined bird row
uses the accepted equal-region-within-species estimate, not pooled observations.
Setting is expressed through rows so the table needs only three performance
columns. The supporting values are in
`evidence/reconstruction/20261113/table1-performance.csv`. Outside that table,
the draft text is unchanged. The article body and bibliography are unchanged.

Three independent Codex audits checked Methods/design quantities, the
new Results values, and scientific meaning/displays/prose. The parent
verified the endpoint structure, preprocessing records, patch-cell distinction,
rounding and Table 1, and integrated their findings. The checks use aggregate
outputs and records, not private response rows.

## Factual repairs

### The bird experiment has five endpoints, not a full factorial

The accepted condition counts are:

| Target data | Auxiliary size | Targets |
|---|---|---:|
| 25% | Full | 73 |
| 50% | Full | 73 |
| 100% | 20 | 73 |
| 100% | 80 | 73 |
| 100% | Full | 157 |

Thus the primary panel contributes 73 × 5 conditions, plus 84 full-only
targets: 449. The draft's “crossed” 25/50/100 with 20/80/all implies nine
combinations per primary target, which were not the design. The historical
configuration label `crossed_grid` does not change the executed endpoints.

Replacement for the first two sentences of the learning-curve Methods:

> Bird learning curves varied target data at the full auxiliary pool (25%,
> 50% and 100%) and auxiliary-pool size at full target data (20, 80 or all
> eligible species). These five endpoints used the primary 73-species panel;
> the other 84 targets were fitted at full target data and auxiliary size.

This also corrects “crossed” wording that I supplied in earlier replacements.
Update the corresponding M9 wording in 03b; retain dated review records as
history. The executed experiment and its acceptance evidence remain unchanged.

Owning evidence: `evidence/seawfb_dsdm/goal052/summary.json:conditions`;
`src/dsdm_phase1/goal050_seawfb_foundation.py:425`.

### Preprocessing and held cells need precise labels

The claim that all categorical encoding was fitted within each partition
compresses two different implementations. Bird vocabularies were fitted per
training mask. Tasmania retained a fixed response-independent categorical
schema and used training-only active-indicator masks. This is a Methods
description correction, not a newly discovered leakage failure.

Replace the preprocessing sentence with:

> Preprocessing used training-partition estimates; Tasmania retained a fixed,
> response-independent categorical schema with training-only support masks.

Owning evidence: `config/model_ready_feature_plan.json:categorical_semantics`;
`docs/goals/032-dsdm-real-compute-calibration/Decision.md:17–31`;
`docs/goals/035-dsdm-final-inner-lifecycle/Decision.md:5–12`; bird vocabulary
fitting at `goal050_seawfb_foundation.py:312–324`.

The five Tasmania patches contain 606 **observed response cells**, not only
606 map cells. The partition receipt records 6,753 test map cells.

Replace the response-row sentence with:

> Of 12,711 resolved species–cell responses, 11,039 were used for development
> and 1,672 came from 606 observed cells within five withheld patches.

Source: `evidence/spatial_partition/2026-07-26/summary.json:partitions`.

### Quarter-data support and one rounding correction

The primary-panel median of all retained presence cells is 14,063. The
approximately 2,800 presences apply after excluding a fold and subsampling
training data, rather than simply quartering all retained presences. A
count-only reconstruction of the frozen sampling quotas gives a median
2,825 presences across 365 target-by-held-fold training/replay fits;
the median across species of their mean-fold counts is 2,813.

Use:

> Quarter-data training fits still contained a median of about 2,800 presence
> cells per held fold.

The exact Tasmania development FT-minus-target-only mean is
−0.006749640344026919. Direct rounding to four decimals gives **−0.0067**,
not −0.0068. Both the owning Goal036 species metrics and the accepted
cross-case synthesis agree. Change the new draft's displayed contrast;
do not alter historical receipts.

## The two interpretive questions

**Frozen encoder:** scope the reported result to full target data, the primary
73 birds and the full auxiliary pool. Do not say that benefit occurred
*only* at full pool: the mean is also positive at 80 auxiliaries (+0.001606).
The tested means for 20/80/full are −0.004375/+0.001606/+0.002197.

Replacement in Results:

> At full target data on the primary 73 birds, the frozen encoder's mean
> contrast with target-only rose from −0.0044 with 20 auxiliary species to
> +0.0022 with the full pool, positive for 57 species. Full fine-tuning's
> increment peaked at 80 auxiliaries among the tested sizes (+0.0061).

Replacement in Discussion:

> At full target data and auxiliary-pool size, the bird frozen-encoder control
> also exceeded target-only learning in mean development AUC.

A new target head is still fitted. The statement concerns usefulness of
shared features in development, not their biological content.

**“Three times”:** the ratios of AUC increments are approximately 3.04 for
target-only and 3.74 for fine-tuning, using unrounded means. The phrase is a
rough arithmetic comparison rather than evidence of tripled predictive
accuracy. It adds little to the small absolute increments and blurs the
learner-specific denominators.

Replacement opening for the practical Discussion paragraph:

> In the new bird regions, fixed averaging raised mean AUC by about 0.010 over
> conventional models, compared with about 0.003 for either network alone.
> Both averages used retained predictions and fixed weights.

Keep the ensuing literature context and recommendation to compare
complementary learners alongside auxiliary-pool size.

## Scientific scope and missing Methods information

- Replace **“Every network was a residual multilayer perceptron”** with
  **“The pretrained and matched target-only models were residual multilayer
  perceptrons.”** The conventional benchmark also includes a separately tuned
  shallow network.
- The target-only network's +0.0037 development margin over the tuned shallow
  ANN is supported. It is a descriptive benchmark result, not proof that
  inheriting a fine-tuning-selected architecture eliminates selection
  asymmetry. Keep the selection procedure and its limitation explicit.
- Richness comparisons need their common-support rule in full Methods:
  **“Development comparisons required at least 20 observations of each class
  in every fold; geographic comparisons required 20 per class within the
  region. Each assessment retained the same species across its three bins.”**
  Keep these definitions adjacent to the diagnostic, rather than repeatedly
  qualifying its Results.
- Add the extent weighting rule: **“Eligible strata were averaged within
  species, then species were weighted equally.”**
- The richness FT-minus-target-only sequence +0.0075/+0.0039/−0.0043 is for
  the 59-species common-support development panel. Name that panel.
- Replace the map-retention sentence with **“Across the seven affected species
  and three learners, top-decile cell retention ranged from 31% to 86%.”**
  The range is across 21 method–species pairs. The eighth species had no
  target-training pseudoabsences and reproduced all three maps.
- Replace **“Subsampling an abundant record and predicting a naturally rare
  species are different problems”** with **“Subsampling a well-recorded
  species and predicting a poorly recorded species are different data
  limitations.”** Rare-species applications remain an appropriate proposed
  test; the record-count tertile does not establish ecological rarity.

## Restore the display plan

The draft has four tables. Keeping them alongside the four planned figures
would produce eight display items, exceeding the agreed five and Ecography's
six-item limit. Preserve the established four figures and Table 1:

| Draft table | Disposition |
|---|---|
| Design and absolute AUC | Keep as completed Table 1. |
| Learning-size contrasts | Move to Supporting information; retain the matched full-to-quarter result in prose. |
| Ensemble results | Figure 3 already carries these contrasts and species points; use a short Results statement. |
| Recording-richness gradient | Figure 4 already carries this comparison; keep the support sizes in its caption and concise direction in prose. |

Replacement learning-curve sentence:

> On the primary bird panel, the pretraining increment increased from
> +0.0058 at full target data to +0.0095 at quarter data; the conventional-model
> contrast increased from +0.0034 to +0.0069 (Supporting information).

Replacement ensemble Results text:

> Across the new bird regions, target-only and fine-tuned networks exceeded
> conventional models by mean AUC increments of +0.0032 and +0.0028,
> respectively (Fig. 3). Their fixed averages with conventional predictions
> reached mean AUC 0.6896 and 0.6903. The two ensembles differed by 0.0007,
> with the fine-tuned ensemble ahead for 37 species.

Replacement richness Results text:

> Fine-tuning's mean AUC contrast with conventional models declined across
> background recording-richness bins, from +0.0050 to +0.0019 to −0.0039 in
> development. It also declined in both supported withheld regions, SEH and
> NNC (Fig. 4a).

These are presentation changes; retain all exact values in the figure data
and Supporting information rather than delete accepted evidence.

## Cuts and replacements for overwriting

Repetition of the central finding across Abstract, Results and Discussion
serves different purposes. Keep that recurrence. The following sentences
can go without losing content:

| Sentence | Action |
|---|---|
| “Methods that transfer better would widen what distribution models can offer conservation.” | Cut the obvious restatement of the opening motivation. |
| “Two comparisons separate these sources.” | Cut; the next two sentences specify the comparisons. |
| “The shared features were reusable.” | Cut; the following frozen-control result demonstrates the finding. |
| “Shared information was real.” | Cut the slogan and open with the specific development result. |
| “Data efficiency needs an ecological reading.” | Cut the signpost; begin with the contrast between subsampling and low recording support. |

The Discussion's repeated 0.83/0.68/0.69 triplet can also be removed after
the Results reports it. Replace that paragraph with:

> Regional AUC was low even when unchanged development predictions were
> rescored within bioregions and folds. Restricting scoring removes
> between-region presence–background comparisons [@lobo2008;
> @jimenezvalverde2012]. Comparing learners on the same observations makes
> their relative predictive gains explicit [@yates2018].

This also replaces the absolute claim that broad environmental contrasts
“disappear” and avoids saying that these comparisons isolate what geographic
transfer *caused*. Their design differences remain in the limitations
paragraph. Keep the final matched-control recommendation: it supplies the
practical implication, rather than padding the paper.

## Numerical verification of the added Results values

All quantities below are supported except the Tasmania rounding noted above.

| Quantity | Accepted value or scope |
|---|---|
| Mainland FT minus conventional | +0.003949974; 5/5 positive |
| Bird FT minus conventional | +0.003389858; 67/73 positive |
| Tasmania FT minus conventional | −0.049787548 |
| Sparse third | 53 of 157 targets; 224–3,649 retained presence cells |
| Fine-tuning at 80 auxiliaries | +0.006075971 against target-only, full target data |
| Mainland transfer median | +0.026863275 against target-only |
| Regional FT minus conventional | NCP +0.007796995; SEH −0.007051941; NNC +0.007566498 |
| Fine-tuned ensemble favoured | 37/73 versus the target-only ensemble |
| Omitted domain-complement cells | 360,625 |
| Within-region pretraining increment | +0.010958041; 56/73 positive |
| Richness FT minus target-only | +0.007547794/+0.003883527/−0.004262803; primary common 59 |
| High-richness background shares | NCP 0.278699%; SEH 0.611167%; NNC 2.77157%; mean within-species shares |
| Half-data FT minus conventional | +0.005300679 |
| Tasmania training removal | 368/11,039 rows = 3.3336%; 368/2,240 negatives = 16.4286% |
| Tasmania AUC and maps | Existing aggregate performance/map files still match the earlier checked bindings; 31.353–85.527% retention across 21 affected method–species pairs |

The owning evidence and verified Methods quantities are recorded in
`evidence/reconstruction/20261113/full-draft-review.json`. The Results
review joined the owning full-endpoint Tasmania stratum metrics and conventional
selection, checked the owning mainland and bird aggregates, and checked
accepted outer-report bindings. It did not treat copied manuscript prose as
evidence.

## Integration and hand-off

All 28 citation keys in the draft are identified. Seven verified keys remain
absent from `refs.yaml`; install them from the reference-verification record
before compiling the integrated article. No fresh identity search or human
citation gate is required. The final reference list must retain complete
author lists.

Do not carry the old availability statement over verbatim: the repository
has been public since 2 November, and “currently private” is stale. Preserve
the detailed human/AI roles and update recorded model versions for this
reconstruction. Integrate the agreed four-figure captions and the reviewed
correspondence/release preparation at the appropriate stage.

Only Table 1 was edited in 03c. The rest of this document is proposed
replacement text for Claude to integrate. No article-body replacement or
PDF/Word build is claimed. The remaining rendering check belongs to the
assembled draft with its actual figures, bibliography and corrected text.

Next: Claude — integrate the factual and presentation repairs, then assemble the revised manuscript.
