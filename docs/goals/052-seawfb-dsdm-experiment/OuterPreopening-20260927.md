# Bird outer assessment: pre-opening discussion draft

27 September 2026, Australia/Hobart. **Draft for Fable and Barry; not approved
for execution or opening.** Prepared after the accepted inner results and
Fable's message 566. No outer response has been read for this proposal.

## Reporting fixed before opening

Retain the Goal048 regions and roles: **NCP, supported geographic transfer;
SEH, environmental edge; NNC, fragmented/land-use mosaic**. All three complete
regions and their external 50 km buffers remain excluded simultaneously from
training, transforms, tuning, early stopping and thresholds. Evaluate the
unbuffered regions in one fixed batch, with no decisions between regions.

Use the frozen Goal049 common **73-species primary panel** in each region.
Report the prespecified regional secondary panels separately: **NCP 88, SEH
122, NNC 134**, each including the common 73. The other 84 inner targets are
the union of additional eligible targets, not an 84-species outer panel in
each region. Do not select a new two-of-three-region panel.

Report paired target-level ROC AUC differences, equal species weight within
each region, and the **equal-weight average of the three regional means** on
the common panel. The last is already required by Goal048. Keep every regional
result visible; do not pool raw cells across regions or let a macro average
conceal a regional reversal. Include median, target distribution and positive
count/denominator. Species, regions, folds and seeds are not iid replicates.

Preserve all four planned full-fine-tuning comparisons and both mechanistic
diagnostics. Emphasize **full fine-tuning versus selected conventional** for
practical value and **versus matched target-only neural** for the controlled
pretraining question; report full versus frozen prominently.

The documents differ in terminology: Goal048 names target-only and selected
conventional as outer primary comparators; Goal052's config groups all four
comparisons as `primary_contrasts`, while its Decision calls target-only primary
and the others secondary. **Proposed outer claim hierarchy:** retain Goal048's
two main questions, report both q controls without selection or omission, and
make every conclusion contrast-specific. This wording needs agreement before
opening; it does not retrospectively relabel or change Goal052's calculations.

X10 remains primary. X20 is evaluation-only sensitivity using the frozen
eligible subsets: common-panel denominators **72/73/73** and regional-secondary
denominators **87/122/134** for NCP/SEH/NNC. Keep X10 membership unchanged and
show missing/unevaluable X20 entries explicitly. TSS, balanced accuracy, MCC,
sensitivity and specificity use the fixed training-OOF thresholds; no outer
threshold selection. The endpoint is presence versus effort-supported
target-group background, not occupancy probability or verified absence.

## Expectations, recorded before opening

Expect smaller practical margins than in inner validation, with SEH the most
plausible attenuation or reversal setting. Sparse-species fine-tuning may match
or underperform the frozen trunk. NCP and NNC need not follow SEH or each other.
These are hypotheses, not conditions for computational acceptance. The inner
auxiliary-size pattern does not establish a causal species-richness effect,
and the poor *C. erythrops* folds do not identify feature distortion as a cause.

## Descriptive rule for reading transfer

For each fixed region and comparator, let **M** be mean target-level AUC
difference and **P** the fraction of those same targets with a strictly positive
difference. Proposed mutually exclusive labels are:

| Condition | Descriptive reading |
|---|---|
| M > 0 and P > 0.5 | Consistent positive direction |
| Exactly one of M > 0 and P > 0.5 holds | Mixed direction |
| M ≤ 0 and P ≤ 0.5 | Consistent nonpositive direction |

These labels summarize signs; they are not significance, equivalence or
biological-importance tests. A statement of benefit across all three roles
would require consistent positive direction for both main comparators in all
three regions; otherwise describe the actual region/contrast pattern. Always
report the fixed equal-region estimate and numerical effect sizes alongside
the labels. A tiny positive margin remains tiny.

Report attenuation continuously as **outer mean difference minus matched inner
mean difference**, using identical target identities and weights. Avoid a
half-inner cutoff or a ratio when the inner effect is near zero. A nonpositive
point estimate does not establish absence of an effect. No label licenses
model rescue, region selection or a changed threshold.

## Requirements before execution and opening

Freeze a separate retained-full refit and evaluation contract. Target refits
should consume the stored rounded median epochs for the 100%/full endpoint,
the selected `seawfb_scale` architecture, five paired seeds and seed-averaged
predictions. Bind conventional candidate identities, q configuration,
transforms, thresholds, training rows and prediction receipts. The existing
900 pretraining checkpoints are inner fold fits, **not retained-full refits**;
the full-retained pretraining epoch/seed rule and q refit procedure must be
stated explicitly. No outer refit implementation is accepted by this draft.

Validate the contract and prediction/response separation on synthetic inputs,
then verify retained-full fits and hash all three regions' predictions before
exposing responses. An unexpected missing class/support failure, missing
prediction or numerical failure is reported with counts and handled under a
frozen rule; never silently remove a target to obtain a favourable denominator.
Proposed handling: stop primary acceptance on any unexpected common-panel
failure; retain expected X20 non-evaluability as diagnostic NA. No outer-data
repair or method-specific target deletion is permitted.

Fable's next action is to critique this reporting/rule proposal and the stated
remaining refit requirements. Barry retains the opening decision. Agreement
between models is advisory and does not replace the computational checks or
independent outer evidence.
