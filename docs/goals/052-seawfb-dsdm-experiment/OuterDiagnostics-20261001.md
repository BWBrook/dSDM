# Prospective outer diagnostics after the retained-data review

1 October 2026, Australia/Hobart. This dated addendum follows Fable's
Correspondence message 783 and the retained-only reproduction. Barry's
29 September outer-opening authorization remains in force. Fable concurs with
the core reporting and refit proposals in `OuterPreopening-20260927.md` and
`OuterPreparation-20260929.md`. This addendum fixes supplementary reporting
before any outer response access; it does not change fitted models, selection,
the primary panels or the six registered contrasts.

These diagnostics were motivated by post hoc inner findings. Any outer
confirmation must be described as a prospective test of that inner discovery,
not as a hypothesis specified before the programme began. They measure
dependence on recorded richness, not an identified effect of survey effort.

## Fixed definitions

Let `R_minus_f` be the recorded richness of the complete frozen effort-donor
pool at a cell, less one if and only if the focal species belongs to that pool
and is recorded there. It is not the fold-specific auxiliary-head richness,
and excludes only the focal species, not its entire pretraining block. Use the
original Goal049 response, eligibility and spatial definitions. Read richness
and response membership only in the scoring phase, after the complete
three-region prediction set has been closed and hashed.

For each frozen region, target and arm, use the prescribed seed-averaged
probability. Partition X10 background cells into `10–24`, `25–99` and `100+`
other recorded donor species. For each bin compute ROC AUC against **all**
regional focal-presence cells, including presences with richness below ten.
The positives are identical across the three comparisons; the background
subset changes. Report the absolute arm AUCs and the same four full-fine-tuning
contrasts and two mechanistic contrasts as in the main analysis.

A diagnostic AUC is reportable with at least **20 cells of each binary class**.
Otherwise record NA, the class counts and the support reason. Preserve every
frozen panel member in the output. The main analysis still uses its original
eligibility gates; this diagnostic rule cannot rescue an ineligible target.
Also report the numbers of anchored 50-km tiles supporting each class. There
is no additional tile-count selection for these descriptive diagnostics and
no interpretation of individual cells as independent replicates.

For the three-bin comparison within each region and panel, summarize the
intersection of targets with all three diagnostic AUCs available, using equal
target weights, and publish its membership. Show mean, median, positive count
and denominator for each contrast. Separately show each bin's all-available
summary and denominator; those summaries can differ in target composition.
The regional secondary panels remain the original 88/122/134, not a new
84-species panel.

As an arithmetic check, for every target and arm with both main classes present,
the background-count-weighted bin AUCs must reproduce the full X10 AUC:

`AUC_X10 = sum_k [ n_background_k / n_background_total * AUC_k ]`.

Use unthresholded AUCs from all nonempty bins for this identity even when a
bin has fewer than 20 cells; those values are mechanical checks, not reportable
diagnostics. Empty bins have zero weight. Failure is an implementation error,
not ecological evidence. Require absolute agreement within `1e-12`.

The second diagnostic restricts **both** presence and background cells to
`R_minus_f >= 100`. Use the same 20-per-class rule, explicit NAs, spatial support
counts and paired contrasts. Call this the **high-recording-richness subset**.
It does not match effort or turn unrecorded cells into verified absences.

For any supplementary three-region macro summary, use only the common-panel
target intersection evaluable for that diagnostic in all three regions and
equal target/equal region weights. Give its exact membership and denominator;
an empty intersection yields NA. This supplemental subset estimate never
replaces the unchanged 73-target primary macro estimate. Do not manufacture a
minimum number of targets for a significance claim: none is being made.

## 2 October addition: background composition beside each regional headline

Following Fable's message 810, report the X10 background count and fraction
in each of the three bins for every target-region, including empty and sparse
bins. This composition summary uses the original headline panel, regardless
of diagnostic AUC reportability. A missing diagnostic AUC does not remove its
target from the headline composition summary.

For each region and frozen panel show the target count, summed background
counts by bin, mean background count per target, and **mean of the individual
target shares**. Summed counts are target-background pairs: the same physical
cell may appear for several species. Separately label any pooled-pair share;
it is not the weight implied by the equally weighted species headline. An
empty supplementary panel has zero counts and undefined shares, not zero
shares.

The exact headline decomposition is `mean_target(sum_bin(weight * contrast))`.
Do not replace this with `sum_bin(mean_target(weight) * mean_target(contrast))`:
weights and contrasts can covary among species. Composition can change the
headline even if the within-bin contrasts are fixed, but composition alone
does not identify the cause of a regional difference. This reporting addition
changes no model, response mask, primary contrast, support gate or threshold.

## Fixed ensemble

Create a cellwise probability average, after each component's prescribed seed
averaging: `ensemble = 0.5 * full_finetuning + 0.5 * selected_conventional`.
Use the ordinary selected conventional learner, which may be RF, HGB or a
shallow ANN. This is not uniformly a network-plus-trees ensemble.

Freeze and hash these predictions with the component predictions before
response access. Report its absolute ROC AUC, ensemble-minus-fine-tuning and
ensemble-minus-conventional under the unchanged X10 panels and the richness
diagnostics. Label these exploratory, with no weight tuning, model selection
or promotion to the headline. Report **AUC only** for this new comparator;
neither component's threshold is an ensemble threshold. Existing arms retain
all originally required threshold metrics and their frozen OOF thresholds.

## Acceptance and interpretation

Missing, duplicate or non-finite predictions remain production failures under
the core contract. Only the prespecified diagnostic support rule produces NA.
No post-opening bin merger, target deletion, alternative weight, threshold
revision or regional choice is permitted. Prediction/response separation,
runtime qualification and retained-full fit checks remain prerequisites to
opening; this note alone does not qualify an implementation.

A replicated richness gradient would establish that the relative ranking
performance depends on the sampled background or high-richness subset. It
would be consistent with a shared observation process, ecological community
structure, broad-versus-fine environmental discrimination, and differences
in environmental support. Richness combines these processes. Neither that
gradient nor its replication can identify which process the trunk learned.

Do not use the fixed ensemble gain as an architecture-headroom bound, PCA
variance as a bound on predictive complexity, or a high-richness restriction
as a bias-corrected habitat test. A future observation model and independent
survey information require their own design; they are outside these fits.
