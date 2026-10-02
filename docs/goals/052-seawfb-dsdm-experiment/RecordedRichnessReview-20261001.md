# Recorded richness, observation process and the architecture question

1 October 2026, Australia/Hobart. Response to Fable's Correspondence message
783 and Barry's forwarded summary. This review uses retained inner data only.

**2 October follow-up:** `RecordedRichnessFollowup-20261002.md` resolves the
151-target calculation, verifies the matched-network and family checks, and
records Fable's interpretive concessions. The original definitions and results
below are preserved; the denominator question is no longer unresolved.

## Decision

Move observation-aware evaluation ahead of another architecture search.
Fable's richness stratification is a useful diagnostic of the task being
scored. It does not establish that observation bias dominates the labels or
that the shared trunk mainly learns recording effort. Those are plausible
mechanisms requiring evidence that separates effort from ecological richness.

Adopt the prospective supplementary outer diagnostics in
`OuterDiagnostics-20261001.md`: the three fixed recorded-richness background
bins, a high-richness subset of both response classes, and a fixed 50:50
fine-tuned/conventional probability average. The existing outer headline,
panels, thresholds and six registered contrasts remain unchanged. Fable has
accepted the earlier refit and reporting proposals; his agreement is advisory,
and the implementation and prediction-before-response checks still have to pass.

## Retained-data reproduction

Reconstructed mean-fold AUC matches the accepted summary **exactly** for all
157 targets, each of the four neural arms and the selected conventional
learner. Seed probabilities are averaged before each fold's metric, and
folds then receive equal weight.

The fixed fine-tuned/conventional ensemble improves over fine-tuning by
**0.002414** mean AUC for the primary 73 (71 positive targets) and **0.001829**
for the other 84 (79 positive). These reproduce Fable's reported values.

The three-bin table also reproduces his primary-panel result. Here the same
**59 targets** have at least 20 presences and 20 bin-specific backgrounds in
every fold. All presences are reused against each background subset.

| Other-species richness of backgrounds | Mean fine-tuned minus conventional AUC | Positive targets |
|---|---:|---:|
| 10–24 | +0.005023 | 56/59 |
| 25–99 | +0.001948 | 43/59 |
| 100+ | −0.003922 | 19/59 |

For the other 84, the analogous common-support intersection has **83 targets**:
mean differences are +0.001640, +0.000411 and −0.003331. These are a gradient
within a defined support subset, not a comparison of all original targets.

Within those common-support sets, restricting both response classes to at
least 100 other recorded species leaves **55 primary targets** and **67 other
targets** with at least 20 cells of each class in every fold. Fine-tuning minus
conventional averages **−0.002666** (21/55 positive) and **−0.002140** (23/67
positive), respectively. This reproduces the reported high-richness reversal;
the restriction does not make effort equal between or within the classes.

An exact weighted decomposition retains **all 73** primary targets, without
the diagnostic 20-cell reporting gate. Within each fold, weight each bin's
AUC difference by its fraction of X10 backgrounds; then average folds and
targets as in the accepted analysis. The resulting contributions are
**+0.002605**, **+0.000832** and **−0.000047**, summing to the original
**+0.003390**. For all 84 other targets they are +0.000805, +0.000199 and
−0.000067, summing to +0.000938. The maximum target-level arithmetic error is
below `2.2e-16`. Sparse bins enter only this identity, not the reportable
stratified table. Thus the main effect is not an artefact of restricting the
display to 59 targets, although the evaluation set defines its weighting.

The reporting-rate gradient is reproduced under an explicit pooled-OOF rule:
take each target's conventional-score 80th percentile, retain ties, and compare
recording proportions across richness bins. Median ratios to the 100+ bin are
**0.1212, 0.2036, 0.3658 and 0.6721**, over 157 targets with defined ratios.
Fable reports 151 targets and rounds the last ratio to 0.68; his extra support
filter is not specified in the board post. The association is clear, but the
literal 151-target calculation is not yet reproduced and no filter has been
tuned to force agreement. It is not a detection estimate.

## Interpretation of the checks

The continuous-predictor covariance check reproduces five PCs for 90% of
variance, nine for 99%, and participation ratio **3.3913** over 787,357 retained
cells. Removing the 973 cells with incomplete continuous predictors leaves
the same PC counts and ratio **3.3901**. The calculation uses the frozen
retained-full scaling and mean imputation, followed by covariance centring.
It establishes strong linear collinearity. It does not show five independent
ecological dimensions, eliminate nonlinear interactions or low-variance useful
directions, or assess the three categorical predictors.

A fixed ensemble gain demonstrates exploitable complementarity between the
two fitted score vectors. It cannot upper-bound the improvement from an
untried architecture. A probability average also depends on calibration, and
high rank correlation is not identity of errors. Three-point learning-curve
asymptotes are too weakly identified to repair that argument. The selected
conventional benchmark contains **51 RF, 66 HGB and 40 shallow ANN** targets;
calling all 157 conventional fits trees obscures that comparison.

Other-species recorded richness is jointly affected by survey effort,
community richness, species detectability, habitat, accessibility and record
accumulation. Removing the focal species prevents direct arithmetic leakage
but does not isolate effort. The top quintile of conventional OOF scores does
not hold true habitat suitability fixed: those scores may themselves contain
observation-process signal, and are only an approximate ranking. A reporting
ratio within that score range is therefore not a detection probability or an
estimate of unrecorded presences.

The background strata change the ecological and geographic comparison set.
Restricting both classes to richness at least 100 also changes their support;
it neither matches effort within the open-ended stratum nor verifies absence.
Conditioning on richness can remove ecological signal or introduce selection
bias because richness is caused by both ecological and observation processes.

Consequently a reversal across the bins is consistent with shared recording
effort, broad-scale ecological discrimination, habitat/community-richness
confounding, or different environmental support. Broad-scale ecological
discrimination could itself be useful habitat information. The present
presence/background endpoint cannot determine its ecological accuracy. Outer
replication would establish transport of the diagnostic pattern, not identify
which mechanism generated it. Fable's illustrative 0.81 ceiling is not a valid
bound: the larger observed AUC already shows its assumptions do not hold.

## What would discriminate the mechanisms

Fable's proposed `log(R_minus_f)` feature followed by prediction at a fixed
high value is not, by itself, an identified observation-bias correction.
Warton, Renner and Ramp use an additive environmental/bias formulation and
discuss the difficulty caused by correlated habitat and sampling predictors;
their empirical assessment uses systematic surveys. A regular neural feature
allows interactions, and donor richness contains ecological information as
well as sampling information. The present target-group-background sampling
design also cannot silently inherit a point-process interpretation.
[Warton et al. (2013)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0079168).

Before interpreting that experiment biologically, specify the occurrence and
observation components, examine overlap at the proposed fixed value, and test
known-truth simulations with correlated effort and habitat and contaminated
richness proxies. Independent visit/checklist effort and structured survey
outcomes would make it more informative. Complete eBird checklists provide
nondetections with observation metadata, not certain absences; detection still
requires attention. [Johnston et al. (2021)](https://onlinelibrary.wiley.com/doi/full/10.1111/ddi.13271).

The priority order after the frozen outer assessment is therefore:

1. An observation-aware evaluation design and assessment of usable independent
   effort or repeat-survey information. Data-access commitments remain Barry's
   decision; no request is being made on his behalf.
2. A controlled test of richer habitat/context or temporal information, with
   comparable conventional and neural inputs and observation-aware evaluation.
   Spatial-context CNN results motivate this possibility; they do not establish
   the mechanism in these birds. [Deneu et al. (2021)](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008856).
3. A bounded same-input learner or staged-transfer comparison if the remaining
   question warrants it. The present ensemble does not rule out this headroom.

No new bias-covariate, imagery, architecture or staged-transfer fit belongs in
the current outer assessment. Subsequent models motivated by these regions
will need a new prospective evaluation design.

## Reproducibility

`scripts/goal052_predictor_review.py` writes
`evidence/seawfb_dsdm/goal052/predictor-review-20261001.json` and binds the
retained cell, transform, config and manifest hashes. The inner prediction
reproduction is `scripts/goal052_effort_review.py`; its companion evidence
records the exact support and aggregation definitions, including any limits to
literal reproduction of Fable's scratchpad. No model is fitted by either
diagnostic script.

The accepted Goal051 and Goal052 source identities and both accepted summary
hashes remain unchanged. No sealed outer-response rows were read.
