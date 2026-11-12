# Reconstruction review: steps 1 and 2

Codex (`gpt-6.1-sol`), 12 November 2026. Reviewed commit
`e9a5a3548e5e021a44ccaf48fbad3f24fd4ec5fa` and correspondence thread 162,
message 3325. Two independent Codex subagents checked hypothesis provenance
and display feasibility. The parent checked the numerical summaries and
current primary journal and literature sources.

**Verdict:** retain the reconstruction and its five display items. Revise the
scientific propositions before step 3. The main findings survive; several
sentences currently claim more than the design measures. Plain statements of
the measured result satisfy Barry's writing rule without repeating caveats.

This is a review, not an accepted revision. `01a`, `01b`, `02` and `main.md`
are unchanged. No models were fitted, raw responses accessed, or new ensemble
or resampling results generated.

## Findings and proposed disposition

Owners below are proposed for the next reconstruction revision, not instructions
that override Barry's scope. Paths and line numbers refer to the reviewed commit.

| ID | Finding and check | Proposed disposition | Owner |
|---|---|---|---|
| R1 | `01a:9`, `02:7,29,37`: “only” familiar places and “stays where it was learned” imply universal failure and identify the content of the representation. Bird NCP has a positive mean pretraining increment (+0.00635; 44/73 species). Across all three new bird regions the mean is −0.000396, with 34/73 positive species; mainland transfer benefits 3/5 species despite its negative mean. | State that the **average gain did not persist across the tested new regions**. Remove the assertion about what the network encoded. | Claude |
| R2 | `01a:36,69–73`: the blanket “a priori” label conflates different stages. The original matched comparison and target-data curves were prospective. The richness hypothesis arose after development results and was fixed before outer response access; the survey-only check came later. | Use “Predictions and diagnostic questions”; distinguish the original comparisons, development discovery, prospective outer diagnostic and post hoc checks once in Methods. | Claude |
| R3 | `01a:71`, `02:31,37`: H2 changes comparator. +0.0034→+0.0069 compares fine-tuning with conventional models. The direct pretraining increment is +0.00578→+0.00747→+0.00946 at full, half and quarter target data. | Use the matched-network learning curve to assess borrowing strength. Keep the conventional comparison as practical context. The least-recorded species' +0.0006 versus conventional does not reject H2: they still gain +0.0041 versus target-only, and species composition differs. | Claude |
| R4 | `01b:54–56`, `02:29,33`: the +0.00724 extent result is not area matching. It scores unchanged development predictions within named region-by-fold strata, then averages eligible strata and species. | Replace “areas the size of”, “same size” and “fair comparison by area” with **“within bioregions and spatial folds”**. Treat this as a scoring-extent diagnostic, not an identified geographic penalty. | Claude |
| R5 | `01a:41,60–61`, `01b:84`, `02:15,37`: dependence of ranking on negative evidence is demonstrated; shared observers, region-specific niche learning and an irreducible observation ceiling are not identified. | State “Model rankings changed with the recording richness and source of negative observations.” Keep possible mechanisms together in Discussion. Drop the ceiling claim and the claim that H3/H4's mechanisms were confirmed. | Claude |
| R6 | `02:35`: “survey-confirmed absences” upgrades nondetection to ecological absence. The survey-only re-scoring preserves presences and changes which negative rows are used. | Use **“survey-supported negatives”**. The −0.0051→+0.0154 conventional contrast is correct for original training; identify the comparator. | Claude |
| R7 | `01a:65`, `02:37,41`: “dependable”, “cheaper” and a general superiority of ensembling go beyond an observed bird AUC improvement. One ensemble was prespecified as exploratory; target-only averaging was post hoc. | Say fixed averaging gave the larger **mean AUC gain in these bird regions**. Use “available without pretraining”, which does not attribute the gain causally to architecture alone. No economic comparison is needed. | Claude |
| R8 | `01b:17,22,68,114`: rebranding bootstrap ranges as confidence intervals would not add fitting, spatial, selection or cross-species population uncertainty. | Keep paired **central 95% species-composition resampling ranges**, conditional on the observed panel and fitted models. Define whiskers in captions. Do not add seed/fold resampling as an automatic uncertainty fix. | Claude; Codex for a later agreed reporting extension |
| R9 | `01b:97,115`: mammal neural/conventional ensembles have not been computed; “best ensemble” would select on opened outer outcomes. | Leave mammal ensemble cells out. Show named fixed 50:50 bird ensembles in Fig. 3. A future mammal extension needs aligned bound prediction vectors and labels, not averaged AUCs; saved outer vectors are not established for mainland transfer. | Claude |
| R10 | `01a:47,78`: 157 birds were developed, but only 73 enter the primary three-region panel; the mammal tests are not all whole-bioregion exclusions. | Preserve the accurate counts in `02:17–20`; repair `01a`'s compressed Methods and abstract accordingly. Distinguish Tasmania interpolation patches, mainland→Tasmania transfer and buffered bird regions. | Claude |
| R11 | `02:25`: “best of four” omits the intercept candidate in the accepted conventional selection set. `01b` also retains four learner types while `02` has three. | Say **“a conventional model selected within development data”**. Align the schematic with the three central learners and put frozen-encoder/scalar controls in a labelled supplementary branch. | Claude |
| R12 | `02:29,37,39`: “H1 held” ignores Tasmania's negative development mean; “gained nothing” ignores positive species and co-primary TSS; “effects below 0.01 AUC” excludes the +0.01035 ensemble gain and −0.01551 mammal transfer contrast. | Report mainland and bird development gains explicitly. Focus the short paper on **AUC**, and retain one sentence that Tasmania's threshold-based metric gives a different result. Remove the blanket numerical bound. | Claude |
| R13 | `01b:32–36,81`: maps and richness panels can be made without observation locations, but coarse pixels alone do not establish privacy. Richness panels have different supported species sets. | Draw public region/domain boundaries and buffers, with an explicitly schematic Tasmania inset. Label development/SEH/NNC sample sizes 59/38/55; NCP has no common three-bin estimate. | Claude; Codex for later figure production |
| R14 | `02` does not name the architecture-selection asymmetry or the descriptive scope of species summaries. These matter to the pretraining attribution. | Put both in the single limitations paragraph: the target-only network inherited an architecture chosen using fine-tuning; species share models/geography. Define development predictions as held-out cells within the training domain. | Claude |

## Proposed wording for convergence

Suggested title:

> Learning from other species improved distribution predictions within training regions but gave no average gain in new regions

Suggested plain-language main message (25 words):

> Training AI on many species improved predictions within familiar regions, but gave no average advantage in the new regions tested, where predictions are most needed.

The body must name mainland mammals and birds as the positive development cases.
“Familiar” means predictions for unseen cells inside the development geography,
not fit assessed on the training observations themselves.

Suggested direct H2 result:

> Pretraining's gain over the matched single-species network increased from
> 0.0058 AUC at full target data to 0.0095 at quarter data. Among naturally
> poorly recorded species, its advantage over conventional models was only 0.0006.

Suggested Discussion opening:

> The small average benefit of pretraining within the development domain did
> not persist across the withheld-region tests. The neural advantage in new
> bird regions was available without pretraining, and fixed averaging with a
> conventional model produced the larger mean gain.

Retain four organising questions if useful: the development increment, its
change under reduced target data, its persistence in new regions, and ranking
sensitivity to negative evidence. H3 can predict a retained average benefit;
its failure does not distinguish niche information from recording processes or
optimisation effects. H4 can predict sensitivity without claiming to identify
shared observers. Their provenance should remain explicit.

Consolidate limits in one paragraph, including tabular representation,
architecture selection, dependence and descriptive summaries, and the
post hoc checks. Give Tasmania's metric disagreement in Results, for example:
“Tasmania's AUC result favoured target-only learning, whereas its fixed-threshold
TSS result favoured fine-tuning.” The detailed TSS and frozen-control results
can move to Supporting information. A short paper may prioritise AUC; the full
paper should still report the co-primary outcome. Neither this disagreement
nor a caption's definition of a plotted quantity is repetitive hedging.

## Numerical verification

The rounded headline values in `02` match their aggregate sources. The main
repairs concern meaning, scope and denominators. The parent independently
recomputed all 18 case/comparator means and positive-species counts from
`case_contrasts.csv`, and all nine cases' three absolute AUC means from
`case_metrics.csv`, under `evidence/cross_case_synthesis/20261005/revision-01/`.
All agree with the synthesis JSON. This checks the aggregate arithmetic, not
the raw prediction-generation pipeline.

| Quantity | Verified value |
|---|---:|
| Mainland development pretraining increment | +0.0087453 |
| Primary bird development increment | +0.0057808; 72/73 positive |
| Development region-by-fold increment | +0.0072436; 68/73 positive |
| Mainland→Tasmania increment | −0.0155131; 3/5 positive |
| Bird three-region mean increment | −0.0003960; 34/73 positive |
| Bird NCP increment | +0.0063501; 44/73 positive |
| Bird target-only minus conventional, new regions | +0.0031665 |
| Bird fine-tuned minus conventional, new regions | +0.0027705 |
| Fixed target-only/conventional ensemble minus conventional | +0.0096205 |
| Fixed fine-tuned/conventional ensemble minus conventional | +0.0103522 |
| Tasmania original-training FT minus conventional, mixed evaluation | −0.0051412 |
| Same models, survey-only evaluation | +0.0154289 |

The matched H2 means were recovered from
`evidence/seawfb_dsdm/goal052/summary.json`, under
`panels.panels.{primary73_100_full,primary50_full_aux,primary25_full_aux}` →
`contrasts.multihead_full_finetune_minus_target_only_random_init_resmlp`
→ `delta_mean_fold_roc_auc.mean`. The hypothesis reviewer independently averaged
the underlying 73-value vectors and obtained the same means. Input hashes and
the parent calculations are recorded in
`evidence/reconstruction/20261112/numerical-review.json`.

The richness sentence needs a regional qualification: in SEH, fine-tuning
trails conventional learning even against the lowest-richness bin
(−0.00381); the deficit deepens at high richness (−0.02826). Development and
NNC show the positive-to-negative change. “The neural advantage declined as
background recording richness increased” covers the supported pattern.

## Smallest buildable display tranche

Keep the approved four figures and one table:

1. **Design:** public outlines, buffers and a schematic; three central learner
   paths, with supplementary controls identified separately.
2. **Pretraining increments:** retain paired species points and means for
   the three bird scoring settings and the two mammal cases. Label the extent
   calculation correctly. Show species heterogeneity rather than implying
   every individual loses its gain.
3. **Bird practical comparison:** show both networks and both fixed 50:50
   ensembles against the same conventional baseline. Name the exploratory
   and post hoc status once in Methods/caption.
4. **Negative evidence:** retain the richness gradient and the two-by-two
   Tasmania training/evaluation comparison, with supported panel sizes.
5. **Absolute AUC table:** use setting as rows/subrows and the three learners
   as columns beside concise case descriptors. Keep ensembles in Fig. 3;
   avoid an excessively wide “best ensemble” column.

Existing bird ranges cover only development/outer FT−target-only and
FT−conventional. New paired composition reporting for region-by-fold and
ensemble contrasts can use retained species aggregates in
`evidence/seawfb_dsdm/goal052/extent-review-20261005.json`. That is a bounded
reporting extension, with no fitting or raw-response access, after agreement
on the labels and estimand. For five/eight mammal species, points and means
are sufficient; omit poorly supported inferential whiskers.

The boundary-only map `evidence/seawfb_bioregional_freeze/goal048/selected_holdouts.svg`
already supplies a starting point. Its display geometry uses 3 km
simplification; analysis geometry remains unchanged. Public polygons and
buffers can be redrawn at print resolution without drawing camera sites or
camera-derived cell masks. A schematic inset should not imply actual private
patch locations. Do not make a new “safe grid resolution” claim.

## Venue and the novelty challenge

**I support Ecography.** Its current [scope and author page](https://nso-journals.org/ecography-for-authors)
fits geographic prediction and general ecological questions, and confirms
the 5,000-word/six-item limits. The stronger argument is what the target-only
control changes about interpreting successful multi-species models. A near-zero
mean alone is a weaker contribution. [MEE's scope](https://besjournals.onlinelibrary.wiley.com/hub/journal/2041210x/aims-and-scope/read-full-aims-and-scope)
emphasises methodological advances. Its [2026 Workflows category](https://methodsblog.com/2025/12/02/workflows-a-new-paper-type-for-methods/)
also considers tested combinations of existing methods, so “an ablation cannot
go to MEE” is too categorical. Our current evidence and story still fit
Ecography better; I recommend keeping the agreed venue.

Two primary sources sharpen the novelty test:

- [Basile et al. 2026](https://doi.org/10.1002/ecog.08269) already compare
  neural joint models with elastic net and random forests, with stronger
  continental performance and weaker regional transfer. “Neural gains decline
  under transfer” alone therefore cannot carry this paper. Explain the added
  attribution from target-excluded pretraining, the same-architecture target-only
  control and geographic exclusion, supported by the extent and negative-evidence
  diagnostics. This review does not establish an exhaustive priority claim.
- [Pili et al. 2025](https://doi.org/10.1002/ecog.08002) use virtual species to
  examine sampling correction, internal prediction and transfer against known
  truth. Their paper supports engaging with evaluation/observation mismatch;
  our richness sensitivity does not identify sampling bias in the same way.
  The publisher's full-text page is now accessible; its abstract and stated
  evaluation design were checked in this turn.

Add the sources needed to make that argument. A target of 20–30 additional
references, based on peers' bibliography lengths, is not a scientific requirement.
The [NSO guidelines](https://nso-journals.org/author-guidelines) ask for essential
original sources and self-contained captions; an interval is not required
merely to match peer papers. The all-author bibliography rule sits under
revised-submission formatting, so fix it in the planned journal build without
treating it as a present reconstruction blocker.

## Evidence and next hand-off

Decisive local sources:

- `docs/goals/052-seawfb-dsdm-experiment/Goal.md:5–10,32–40`, first committed
  in `9216e29`, and `Decision.md:5–13`: original comparisons and primary estimand.
- `OuterDiagnostics-20261001.md:3–14,119–124`, first added in `6c85377`:
  development-driven, prospective outer diagnostics and mechanistic limits.
- `Results.md:51–86`: learning-curve and least-recorded-species distinctions.
- `ExtentReview-20261005.md:3–17` and
  `docs/plan/CrossCaseResults-20261005.md:35–53`: extent weighting, ensemble
  definitions and their prospective/post hoc status.
- `docs/plan/BirdCompositionResampling-20261008.md:8–20,33–73`: the accepted
  composition sensitivity estimand, pairing and limitations.
- `manuscript/text/main.md:41–47,67–83,97–121`: negative provenance,
  architecture selection, co-primary metrics and source-conditioned results.

The public-board snapshot policy is absent and the “currently private” text
is stale. They remain release-preparation items; this review does not change
`main.md`, publish the old unredacted local archive, or invent a DOI. Any future
snapshot should use the current reviewed-export policy and preserve the
scientific correspondence while withholding access/host details.

Next: Claude — revise steps 1 and 2 against these findings, especially the
matched H2 contrast, hypothesis provenance and scoring-extent wording; then
return the revised logic for convergence before step 3.
