# Retained-full outer assessment — 5 October 2026

The held-out assessment gives no average ROC AUC advantage for multihead
pretraining followed by full fine-tuning over the matched target-only network.
Its mean difference is **−0.000396**, with 34/73 common-panel species positive.
The advantage over the selected conventional learner is **+0.002771**, with
39/73 positive, and changes sign among regions. These are descriptive estimates;
the near-zero controlled contrast does not establish equivalence.

The frozen 50:50 fine-tuning/conventional ensemble has higher mean AUC than
either component in all three regions. That exploratory result suggests useful
complementarity in their predictions, without identifying its source or placing
a bound on architectural improvement.

## Design and completed computation

All **4,242 retained-full fits** completed: 10 q models, 50 auxiliary pretraining
fits, 3,140 neural target fits and 1,042 conventional fits. Predictions cover
144,860 cells in the three frozen IBRA holdouts, with prescribed seed averages
for 157 targets. All fitted states and the complete prediction set were closed
and hashed before authorized response access. The independent pre-opening audit
verified all 17,060 closure files and recomputed every seed mean and ensemble.

The primary estimate uses the unchanged **73 species**, equal species weights
and equal weights for NCP, SEH and NNC. All primary X10 support gates pass.
Secondary panels retain **88, 122 and 134 species**, respectively. Those panels
are separate regional estimates, not an alternative primary macro. The six
original contrasts, X10/X20 rules, thresholds and prospective diagnostic
definitions remain unchanged.

## Primary AUC contrasts

Each entry is an AUC difference. Positive counts refer to species with a
positive three-region mean difference; species and regions are not independent
replicates.

| Contrast | Macro mean | Macro median | Positive / 73 | NCP | SEH | NNC |
|---|---:|---:|---:|---:|---:|---:|
| Fine-tuning − target-only network | −0.000396 | −0.000565 | 34 | +0.006350 | −0.003999 | −0.003539 |
| Fine-tuning − target-plus-q network | −0.000062 | −0.000884 | 34 | +0.007866 | −0.005041 | −0.003010 |
| Fine-tuning − selected conventional | +0.002771 | +0.001717 | 39 | +0.007797 | −0.007052 | +0.007566 |
| Fine-tuning − q-augmented conventional | +0.002082 | +0.002558 | 44 | +0.006729 | −0.008407 | +0.007922 |
| Frozen trunk − target-only network | −0.001774 | −0.003320 | 31 | +0.005678 | −0.007909 | −0.003092 |
| Fine-tuning − frozen trunk | +0.001378 | +0.000070 | 38 | +0.000672 | +0.003909 | −0.000447 |

Absolute macro AUC is **0.682732** for fine-tuning, **0.683128** for target-only
learning, **0.682794** for target-plus-q learning, **0.681354** for the frozen
trunk, **0.679962** for conventional learning and **0.680651** for its q
augmentation. The ensemble reaches **0.690314**: **+0.007582** over fine-tuning
(56/73 positive) and **+0.010352** over conventional learning (60/73 positive).
No ensemble weights were tuned against these outcomes.

Compared with the matched inner estimates for the same 73 species, the
fine-tuning advantage over target-only learning changes from **+0.005781** to
**−0.000396**. The conventional comparison changes from **+0.003390** to
**+0.002771**. This documents attenuation under the outer assessment; it does
not attribute the change uniquely to selection, environmental transfer or an
observation process.

The X20 sensitivity analysis has the same broad pattern: fine-tuning minus
target-only **−0.002022**, and minus conventional **+0.002148**. Its primary
equal-region macro uses 72/73/73 eligible species in NCP/SEH/NNC. The single
NCP exclusion is *Malurus cyaneus*. The separate 72-species three-region
intersection is supplementary. No threshold or panel was changed to obtain
these estimates.

The larger regional panels also preserve the regional pattern. Fine-tuning
minus target-only is **+0.008912 / −0.001228 / −0.005023**, and minus
conventional is **+0.006863 / −0.010600 / +0.003730**, in NCP/SEH/NNC order.

## Prospective recorded-richness diagnostics

These tests were fixed before outer opening, following a post hoc inner
discovery. They compare recording discrimination across background composition;
they do not isolate survey effort or establish occupancy discrimination.

Using identical species across the three bins within each region, fine-tuning
minus conventional declines as recorded background richness increases:

| Primary-panel diagnostic | Species | 10–24 donors | 25–99 donors | 100+ donors |
|---|---:|---:|---:|---:|
| NCP, common three-bin support | 0 | NA | NA | NA |
| SEH, common three-bin support | 38 | −0.003808 | −0.013951 | −0.028264 |
| NNC, common three-bin support | 55 | +0.014775 | +0.006022 | −0.025871 |

These AUCs compare **all regional focal presences** with each background bin.
NCP has no target with the required 20 background cells in the 100+ bin.
Consequently, no three-region macro or three-region replication claim is
available for that bin. NCP's all-available lower-bin comparisons remain
reportable: **+0.006276** and **+0.012855**, both with 73 species. They cannot
fill the missing third bin.

The distinct **high-recording-richness subset** restricts both classes to
100+ other recorded donors. Fine-tuning minus conventional is **−0.037258**
in SEH (34 species; 13 positive), and **−0.007934** in NNC (53 species;
22 positive). NCP and the three-region intersection remain NA. The larger
regional panels give **−0.048223** (SEH, 72 species) and **−0.013061**
(NNC, 104 species). Thus the observed richness dependence extends to both
diagnostics where support exists, without identifying what the trunk learned.

The 100+ bin accounts for only **0.279% / 0.611% / 2.772%** of the mean
species-level X10 background share in NCP/SEH/NNC. Strong differences within
that bin therefore need not dominate the overall AUC. These are mean target
shares, not pooled-pair weights. The exact target-level background-weighted
identity reproduces X10 AUC to a maximum absolute error of **3.33 × 10⁻¹⁶**
over 2,870 defined arm comparisons. This is an arithmetic check, not evidence
for a causal explanation of regional variation.

[The diagnostic appendix](OuterDiagnosticsResults-20261005.md) supplies the
absolute binned AUCs, all high-richness contrasts, regional summaries and exact
support memberships. Missing diagnostic values remain explicit.

## Threshold metrics and interpretation

For the six original learners, the complete report retains TSS, balanced
accuracy, MCC, sensitivity, specificity and prevalence at frozen inner-OOF
thresholds. For example, macro TSS is 0.201804 for fine-tuning and 0.191966 for
target-only learning. The retained-full score scales were not recalibrated on
outer responses; threshold metrics and unthresholded AUC answer different
questions. The ensemble remains AUC-only.

The assessment supports a limited conclusion: the inner average advantage of
pretraining over an otherwise matched target-only network does not carry into
the three-region primary outer AUC estimate. Small conventional-comparator
advantages and ensemble gains coexist with substantial regional and richness
dependence. Presence versus effort-supported unrecorded background measures
recording discrimination. It does not supply verified absences, an occupancy
model or a separation of ecological and observation processes.

## Provenance and operational recovery

Production fitting finished overnight. Subsequent completion was delayed by an
audit comparison of ANN serialization size, a response-loader assumption that
all registered species must have serialized rows, and a report polling race.
The canonical source has 505 registered active/donor species, including 56
zero-row species, and 449 serialized species. Full original input validation
and independent review verified this distinction; no scoring target is among
the empty species. A separate certified loader preserved the 505-species donor
universe and the unchanged scoring calculations. An initial recovery attempt
also stopped on a runtime binding error before reading responses. All failure evidence
is retained.

No fitted model, prediction, frozen scientific source, threshold or scientific
definition changed after opening. Scoring and report generation both exited
successfully. The report polling failure is reconciled through a separate
return-only receipt; the failed completion receipt is preserved.

The canonical score file is
`data/processed/dsdm/goal052-seawfb-dsdm-experiment/outer-assessment-20261003-r2/scores.json`,
SHA256 `3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41`.
The plan digest is
`4b179d6cf8134551099c896bbcb30837d2d316cc3e5c70ed30d91c53bf4b63e0`;
the unchanged closure SHA256 is
`aa5b7949cd0c76bb324edde55d5209e0fbf8447b9e00f45a0efa5850ce185063`.
The full fitted models remain in the isolated Deep export under
`/data/codex/repos/dSDM-outer-20261003-r2/`.

The final acceptance receipt and independent check results accompany this
readout in `evidence/seawfb_dsdm/goal052/`. Verified return finished at
**11:54:09 AEDT**: 185 data/receipt files, including all 157 final prediction
files, plus 26 immutable controller files. All 29 frozen scientific sources
still match their plan hashes.

Independent arithmetic checks cover all 471 target-region rows, all eight
X10/X20 aggregate contrasts, richness support and decomposition, and matched
inner attenuation. A separately written raw-data check reconstructed responses
and focal-excluded richness from all 5,048,061 canonical memberships for the
prospectively selected first, middle and last primary species, across all three
regions. It checked seven-arm AUC and six-arm threshold metrics under X10/X20:
2,268 field comparisons passed, with maximum absolute difference
**2.44 × 10⁻¹⁵**. This is a three-species numerical spot-check, alongside the
full prediction/provenance audit and all-target aggregate checks.

- [Frozen native report](../../../evidence/seawfb_dsdm/goal052/outer-review-20261005/native-report.md)
- [Final acceptance receipt](../../../evidence/seawfb_dsdm/goal052/outer-acceptance-20261005.json)
- [Independent review files and reproduction commands](../../../evidence/seawfb_dsdm/goal052/outer-review-20261005/README.md)
