# Paper plan: when do multi-species representations transfer?

**For Barry's review, 11 October 2026.** This replaces further incremental
drafting with an argument and allocation plan. The current manuscript is a
working synthesis; the plan is not yet an approved narrative.

## Headline and contribution

**Small average in-domain gains from multi-species pretraining did not
establish an average advantage under the frozen geographic-transfer tests.**
Mainland mammals and birds provide the paired development/transfer evidence.
Tasmania provides a contrasting setting where model rankings depend on metric
and evaluation-negative source. Species and regional exceptions stay visible. Do not attribute the difference to auxiliary diversity:
only the auxiliary-pool experiment changes it, jointly with composition and
record volume.

The contribution is a controlled evaluation of reusable representations across
three ecological settings, with matched networks, credible conventional
comparators, explicit observation classes and closed geographic tests. It is
not a claim to invent shared multi-species representations, establish a
universal null effect or identify the ecological mechanism behind the scores.

## Four supporting lessons

1. **Matched controls change the practical conclusion.** Pretraining versus
   the same network tests pretraining conditional on the shared architecture
   and fitting design; the architecture was selected for fine-tuning. Performance
   versus tuned conventional learners addresses practical value. Fixed bird
   ensembles improved on conventional learning with or without pretraining
   (+0.0104 and +0.0096 outer AUC). This shows that much of the ensemble benefit
   is available without pretraining, not that the two networks contain
   equivalent information.
2. **Evaluation extent changes absolute discrimination.** Bird whole-domain
   inner AUC is not directly comparable with within-region outer AUC. The
   matched pretraining contrast remains positive after inner regional
   reaggregation but is near zero across the three outer regions. Keep the
   loss of that contrast separate from the change in absolute AUC; the extent
   analysis does not identify an isolated geographic penalty.
3. **Negative-source definitions condition the score.** Bird gains over
   conventional learning decline with background recording richness where
   support permits comparison; SEH and NNC show the inner pattern, while NCP
   lacks high-richness support. These are not independent replications.
   In Tasmania, removing training pseudoabsences lowers mean full-data AUC on
   the mixed panel but raises it on the post hoc survey-only panel, for all
   three methods. Keep both panels; neither identifies a recording mechanism
   or validates ecological absence or occupancy.
4. **Data efficiency has a restricted scope.** Subsampling well-recorded
   targets is not a rare-species experiment. In the sparsest third of birds,
   the inner pretraining gain over the matched network was +0.0041, while the
   gain over tuned conventional learning was only +0.0006. The defensible
   limit is little average practical advantage over that benchmark, not
   “no benefit for naturally sparse species”.

\newpage

## Main text, figures and supplement

Use four Results subsections: (i) matched development-to-transfer comparisons,
(ii) extent and ensembles, (iii) observation/background support, and (iv) a
single compact Tasmania subsection retaining the co-primary AUC/TSS distinction
and both evaluation panels. Put the sparse-target boundary within subsection
(i). Organise Discussion around what each comparison permits a modeller to
claim, rather than repeating individual results.

| Item | Main-text purpose | Supplement/archive |
| --- | --- | --- |
| Table 1 | Three designs, targets, response definitions, training exclusion and evaluation task | Full species/source inventory, model grids and implementation |
| Figure 1 | Inner/outer paired AUC contrasts against target-only and conventional learning; species points; qualified bird composition ranges | All endpoints, scalar controls and sensitivity metrics |
| Figure 2 | Bird extent and the two fixed ensembles; preserve matched comparisons and support rules | Per-region/fold details and support-tail checks |
| Figure 3 | Compact recording-richness contrasts: inner discovery and outer tests on supported panels | All strata, counts, X20 and restricted-positive analyses |
| Table 2: Tasmania | Full-data mixed versus survey-supported-absence performance for both training regimes; no new standalone Results section | Tables S5–S9, all seven endpoints, source counts, thresholds and map plates |

This three-figure, two-table allocation is our choice. Keep selection,
exclusion, scoring and prospective versus post hoc status in main Methods;
move parameter inventories and execution checks to the supplement/repository.
Preserve all accepted results and receipts.

## Length, journal fit and decision

MEE is the working target, subject to agreement that this controlled evaluation
makes a sufficiently general methodological contribution. Its current guidance
specifies 7,000–8,000 words for Research Articles, including table/figure
captions, statements and references, and a four-part numbered abstract aiming at no more than 350 words. [MEE author guidance, checked 11 October 2026](https://besjournals.onlinelibrary.wiley.com/hub/journal/2041210x/author-guidelines).

Target **6,250 words inclusive**: abstract 250; introduction 550; methods
1,450; results 1,250; discussion 1,150; captions 500; tables 250; statements
150; references 700. The current rendered-text planning count is approximately
6,856 words including captions, tables and cited references, with a 221-word
abstract and nine Results subsections. Page count alone does not show a length breach; the immediate
problem is prioritisation. Final counting follows the rewrite.

**Decision requested:** agree the headline, four lessons and main-text
allocation (including the small Tasmania comparison table), or specify an alternative. Then perform one focused rewrite and
check each retained claim against its evidence. No new fitting is proposed.
The post hoc survey-only check has a separate frozen evaluation plan.
