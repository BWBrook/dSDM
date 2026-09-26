# Goal052 completion and first result review

26 September 2026. The frozen inner experiment is computationally complete.
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

The shared architecture is `seawfb_scale`. At target 100% and auxiliary `full`,
full fine-tuning has small positive mean differences against all four
prespecified controls. The table reports differences in **mean-fold ROC AUC**
and **mean-fold TSS**, averaged across targets. These are not pooled TSS
differences or inferential significance tests. Predictions were averaged over
the five seeds before scoring.

| Full fine-tuning minus control | Primary 73: AUC | Primary 73: TSS | Other 84: AUC | Other 84: TSS |
|---|---:|---:|---:|---:|
| Matched target-only random-init ResMLP | +0.005781 | +0.009486 | +0.003376 | +0.008175 |
| Target plus `q_linear` ResMLP | +0.005772 | +0.010019 | +0.003125 | +0.007775 |
| Goal051 selected conventional learner | +0.003390 | +0.006486 | +0.000938 | +0.001435 |
| Goal051 `q_linear`-augmented conventional learner | +0.003008 | +0.005594 | +0.000975 | +0.001111 |

For the primary 73, mean absolute AUC is **0.831603** for full fine-tuning and
**0.825822** for target-only learning. AUC improves for 72/73 targets and TSS
for 69/73. The corresponding matched-control counts among the other 84 are
79/84 and 67/84. Across all 157 targets, mean AUC difference is +0.004494
(151/157 positive), and mean TSS difference is +0.008785 (136/157 positive).

The primary 73 also contributed to architecture selection through seed00;
the other 84 did not. The latter therefore provide a useful diagnostic of
selection optimism, though neither panel is an independent outer assessment.
The gains over conventional controls on those 84 targets are particularly
small. Species and spatial folds are dependent; counts of positive differences
and among-target variation do not supply inferential uncertainty.

## Mechanistic and selection diagnostics

For the primary 73 at the same endpoint, frozen trunk minus target-only gives
mean AUC **+0.002197** and TSS **+0.003227**. Full fine-tuning minus frozen trunk
adds **+0.003584** AUC and **+0.006259** TSS. These mandatory mechanistic
comparisons are distinct from the four primary contrasts above.

Among the other 84, full minus frozen is only **+0.000633** AUC and
**−0.000753** TSS. The most negative TSS difference is **−0.089251** for
*Climacteris erythrops*, with AUC difference **−0.013132**. The median TSS
difference is slightly positive (+0.000751), so this contrast warrants
target-level examination. The incremental value of fine-tuning is heterogeneous.

`seawfb_scale` remains the selected winner in all **10** leave-one-focal-block-out
ranking diagnostics. Its mean target rank is 2.1918, versus 2.5479 for
`bridge_wide`; the corresponding mean selection-AUC margin is only 0.000487.
Stable ranking does not establish a large performance difference, and this
diagnostic cannot change the frozen winner.

These values come from `conditions[*].primary_contrasts`,
`conditions[*].mechanistic_contrasts`, `arm_metrics`, `panels`, and
`selection.stability` in the accepted aggregate. A separate read-only review
found no computational acceptance blocker, verified all four arms and both
mechanistic contrasts for each condition, and confirmed that the tracked
aggregate contains no row-level responses, predictions, coordinates or site IDs.

## Next scientific review and scope

Review the prespecified target-size and auxiliary-size panels, target/block
heterogeneity, the *C. erythrops* contrast, and practical effect magnitudes with
Fable and Barry before deciding whether an outer evaluation is justified.
The native gate establishes complete execution and exact independent numerical
replay; it does not establish biological importance or causal benefit.

All results remain relative habitat-suitability comparisons under inner spatial
generalisation. **NCP, SEH and NNC remain sealed.** No retained-full refit,
outer threshold, map, manuscript claim or scientific amendment is authorized
by this completion. No additional compute or recurring monitor is running.
