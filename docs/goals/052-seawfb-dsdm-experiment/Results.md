# Goal052 completion and first result review

Revised 27 September 2026 after Fable's board critique (thread 32, message 566).
The frozen inner experiment is computationally complete. The original
[26 September readout](Results-20260926.md) is preserved under its receipt hash;
this revision changes interpretation, not the accepted numerical results.
PBS **812164.kunanyi-ohpc** finished with exit 0 at **01:41:50 AEST**, after
**3h57m59s**, using one CPU and 2.140 GiB peak memory. The unchanged native
independent replay passed **900 pretraining lifecycles, 42,345 unique target
lifecycles and 449 conditions**. No fitted result was repeated during validation.

The [completion receipt](../../../evidence/seawfb_dsdm/goal052/completion_review.json)
binds the [full aggregate](../../../evidence/seawfb_dsdm/goal052/summary.json),
source, accepted inputs, runtime, launch and returned evidence. Its summary
SHA256 is `ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3`.
All 16 returned evidence-file hashes and 87 local checks passed. The native
summary retains `complete_pending_validation`, as written by the frozen
aggregator; the separate `goal052_complete_valid` receipt certifies those exact
bytes. All checkpoint and leaf pairs are preserved locally and on Kunanyi.

## Descriptive primary comparisons

The practical headline is full fine-tuning minus the tuned conventional
benchmark: mean AUC **+0.003390** on the common-panel 73 and **+0.000938** on
the other 84, with 67/73 and 63/84 target differences positive. The latter is
a very small average margin, not a formal demonstration of equivalence or a
claim that no individual restricted species benefits. Matched target-only
neural learning remains the central controlled contrast for pretraining.

The shared architecture is `seawfb_scale`. At target 100% and auxiliary `full`,
full fine-tuning has small positive mean differences against all four planned
controls. The table reports differences in **mean-fold ROC AUC**
and **mean-fold TSS**, averaged across targets. These are not pooled TSS
differences or inferential significance tests. Predictions were averaged over
the five seeds before scoring.

| Full fine-tuning minus control | Primary 73: AUC | Primary 73: TSS | Other 84: AUC | Other 84: TSS |
|---|---:|---:|---:|---:|
| Matched target-only random-init ResMLP | +0.005781 | +0.009486 | +0.003376 | +0.008175 |
| Target plus `q_linear` ResMLP | +0.005772 | +0.010019 | +0.003125 | +0.007775 |
| Goal051 selected conventional learner | +0.003390 | +0.006486 | +0.000938 | +0.001435 |
| Goal051 `q_linear`-augmented conventional learner | +0.003008 | +0.005594 | +0.000975 | +0.001111 |

For the primary 73, mean absolute AUC is **0.831603** for full fine-tuning,
**0.828213** for the selected conventional learner and **0.825822** for
target-only learning. Against target-only, AUC improves for 72/73 targets and TSS
for 69/73. The corresponding matched-control counts among the other 84 are
79/84 and 67/84. Across all 157 targets, mean AUC difference is +0.004494
(151/157 positive), and mean TSS difference is +0.008785 (136/157 positive).

The primary 73 contributed to architecture selection through seed00; the other
84 did not. However, panel membership also reflects frozen all-region support
gates. The panels differ substantially: median retained presence-cell counts
are 14,063 versus 3,167.5, prevalence 0.201 versus 0.045, and conventional AUC
0.832 versus 0.940. Their difference is therefore a composition contrast and
does not isolate selection optimism. The present design cannot apportion the
gap between composition, selection and other factors. Neither panel supplies
an independent outer assessment. Species and spatial folds are dependent;
positive-target counts and among-target variation are descriptive.

## Learning-size and auxiliary-size patterns

Within the common 73, at full auxiliary size, mean AUC gain over conventional
is **+0.006923**, **+0.005301** and **+0.003390** at 25%, 50% and 100% target
data respectively. Fine-tuning with 50% of target data exceeds conventional
learning with 100% for **56/73** targets (mean difference +0.001560). This is a
post hoc cross-endpoint comparison of the frozen learning-size results. It
supports data efficiency when subsampling these species; it does not establish
the same benefit for naturally sparse species.

At 100% target data, frozen-trunk minus target-only mean AUC is **−0.004375**,
**+0.001606** and **+0.002197** with 20, 80 and full auxiliary species. All
**73/73** improve from 20 to full auxiliary size; **57/73** beat target-only
at full size. Those are different comparisons. Fine-tuning already achieves
**80.3%** of its full-pool mean gain with 20 auxiliary species and peaks at 80
in this grid. The frozen-trunk response is the clearer scaling diagnostic,
but auxiliary species number changes with row volume and composition; the
experiment does not isolate a causal species-richness effect.

Across all 157 targets, the lowest third by retained evaluation presence cells
(224–3,649; 53 species) has mean fine-tuning minus conventional AUC **+0.000628**,
with 35/53 positive. The middle and highest thirds have +0.002655 and +0.002978.
These tertiles are post hoc descriptions, not prespecified panels or evidence
that sparse-species effects are exactly zero. All ten focal-block means are
positive for the four principal neural/conventional and mechanistic contrasts;
the heavily overlapping auxiliary pools prevent treating blocks as independent
pretraining experiments.

Adding `q_linear` to target-only neural learning changes panel mean AUC by
roughly −0.000036 to +0.000251. This is negligible average incremental
discrimination under the tested implementation. It does not prove the scalar
has no information: redundancy with predictors and downstream use remain
possible, and no nonlinear community control was tested here.

## Mechanistic and selection diagnostics

For the primary 73 at the same endpoint, frozen trunk minus target-only gives
mean AUC **+0.002197** and TSS **+0.003227**. Full fine-tuning minus frozen trunk
adds **+0.003584** AUC and **+0.006259** TSS. These mandatory mechanistic
comparisons are distinct from the four primary contrasts above.

Among the other 84, full minus frozen is only **+0.000633** AUC and
**−0.000753** TSS. The most negative TSS difference is **−0.089251** for
*Climacteris erythrops*, with AUC difference **−0.013132**. The median TSS
difference is slightly positive (+0.000751). In *C. erythrops*, fold 3 contains
200 of 494 retained evaluation presence cells (40.5% of these observations,
not a measured percentage of geographic range). Its AUC is 0.78849 for
target-only, 0.87299 for fine-tuning, 0.95018 for frozen trunk and 0.95137 for
conventional learning. TSS degradation is concentrated in folds 2–3; the
fold-3 AUC loss also establishes a ranking loss independent of the threshold.

TSS equals sensitivity plus specificity minus one. Low prevalence does not
mechanically inflate it; sparse observations and threshold uncertainty may
affect precision and transport. No saved-fit contract failure was found, and
no corrective refit follows from a poor result. Pretrained-feature distortion
is one possible explanation, not an identified mechanism in this dataset.
[Kumar et al. (2022)](https://arxiv.org/abs/2202.10054) establish its possibility
in other models and distribution-shift settings, which motivates the hypothesis.

`seawfb_scale` remains the selected winner in all **10** leave-one-focal-block-out
ranking diagnostics. Its mean target rank is 2.1918, versus 2.5479 for
`bridge_wide`; the corresponding mean selection-AUC margin is only 0.000487.
These observed margins do not estimate or bound selection optimism. All
candidates use the same development evidence, shared selection uses mean rank
first, and seed averaging after selection does not remove that dependence.
Stable block-deletion ranking is a diagnostic, not a new held-out estimate.
This distinction is consistent with the model-selection concerns in
[Cawley and Talbot (2010)](https://jmlr.org/papers/v11/cawley10a.html).
No result here changes the frozen winner.

These values come from `conditions[*].primary_contrasts`,
`conditions[*].mechanistic_contrasts`, `arm_metrics`, `panels`, and
`selection.stability` in the accepted aggregate. A separate read-only review
found no computational acceptance blocker, verified all four arms and both
mechanistic contrasts for each condition, and confirmed that the tracked
aggregate contains no row-level responses, predictions, coordinates or site IDs.

## Next scientific review and scope

The checks above are reproducible with
`uv run --locked python scripts/goal052_inner_review.py`; the compact output is
`evidence/seawfb_dsdm/goal052/fable-review-20260927.json`. It reads only the
accepted tracked inner aggregate. Cross-endpoint, composition, tertile and
block re-expressions are labelled post hoc and do not amend the experiment.

An outer assessment is scientifically justified because the practical inner
margins are small and their geographic transport is unresolved. The
[dated pre-opening proposal](OuterPreopening-20260927.md) preserves frozen
regions, panels and contrasts and is awaiting Fable's review and Barry's
opening decision. It is not an authorization to read outer outcomes or refit.
The native gate establishes complete execution and exact independent numerical
replay; it does not establish biological importance or causal benefit.

All results remain relative habitat-suitability comparisons under inner spatial
generalisation. **NCP, SEH and NNC remain sealed.** No retained-full refit,
outer threshold, map, manuscript claim or scientific amendment is authorized
by this completion. No additional compute or recurring monitor is running.
