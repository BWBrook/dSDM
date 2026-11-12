# Step 2: Display items

Main message (step 1): *Training AI on many species helped it predict where one species lives, but only in familiar places, not new ones, where predictions matter most.*

## Budget

**Four figures and one table, which is five of the six items Ecography allows.**

- The text has about 4,650 words; at 5,000 words, each display item should carry one point the reader cannot get from the text.
- Keep the sixth slot empty. Filling it would make every item compete for attention, and a reviewer's request can use it later.
- Everything else goes in a single Supporting information file.

## Principles for every item

- **One point per item, stated in a title that reads as a sentence.** The caption explains how to read the figure. Limitations go in the Discussion's limitations paragraph, not in captions.
- **Plain labels for readers outside the field.**
  - Write "familiar places" or "training region" and "new places" or "held-out region", not "inner/outer CV", "OOF" or "region × fold".
  - Write "pretrained network", "single-species network" and "conventional model", not FT/TO/conv. Abbreviations can stay in the methods.
- **One colour per learner across all figures.** For example: pretrained network in blue, single-species network in orange, conventional model in grey, ensembles in green.
- **Show the species, not just means.** Plot one point per species, a mean, and a bootstrap 95% interval over species. The interval answers the uncertainty point in the Ecography audit.
- **Share scales wherever the comparison matters.** The current Fig. 1 has a different scale in every row, so its main contrast cannot be read off it.
- **No camera-site locations on any map.** Show regions and outlines only.

## Proposed items

### Figure 1: Study design (new context item)

*Three tests of whether learning from other species helps in new places.*

- **(a) Map** of south-eastern Australia showing:
  - the bird training domain;
  - the three held-out bird regions (NCP, SEH, NNC) with their 50 km buffers;
  - the source domain for the mainland mammals, and Tasmania as their transfer target;
  - Tasmania's held-out patches, shown schematically and without site locations.
- **(b) Schematic of the four learners and two comparisons:**
  - The **pretrained network** learns from other species first, then learns from the target.
  - The **single-species network** has the same architecture but learns from the target only.
  - The **frozen-encoder** control.
  - The **conventional models**: elastic net, RF, HGB and a shallow ANN.
  - Comparison 1, **pretrained minus single-species**, measures what learning from other species adds.
  - Comparison 2, **single-species minus conventional**, measures what the network adds by itself.
  - The arrows also show the rule that **the target species is excluded from pretraining** and **the held-out regions are excluded from all fitting**.

**Why:** the three peer papers we read in full that have a map or design schematic all have one. Our design uses three cases, held-out regions and a matched twin, and reviewers will judge it on whether they grasp that design in 30 seconds. The schematic also carries the paper's methodological contribution.

### Figure 2: The main result (rebuilt from current Fig. 1 and Fig. 2b)

*Learning from other species helped in familiar places but not in new ones.*

- **(a) Birds, pretrained minus single-species network, per species**, in three settings on one scale:
  1. familiar places, scored across the whole training domain (+0.0058);
  2. familiar places, scored within regions the same size as the held-out ones (+0.0072, 68 of 73 species positive);
  3. new places, the held-out regions (−0.0004, 34 of 73 positive).
  Setting 2 is the decisive control: the gain survives a fair comparison by area in familiar places and disappears in new ones. Draw paired lines or link the species across settings so the collapse is visible.
- **(b) Mammals, same contrast:**
  - mainland mammals, familiar places (+0.0087) and transferred to Tasmania (−0.0155);
  - Tasmanian mammals, familiar places (−0.0068) and held-out patches (−0.0147).
  There are few species here, so plot the individual points large.

**Why:** this figure is the paper. The current Fig. 1 shows 12 panels at 6 scales and mixes both comparisons, so the main message is not visible at a glance.

### Figure 3: What does help in new places (rebuilt from current Fig. 2b and its callout)

*In new places, the network's advantage came without pretraining, and combining it with a conventional model gained most.*

- Held-out bird regions only. Each row is a difference from the conventional model, with species points, a mean and a 95% interval:
  1. single-species network (+0.0032);
  2. pretrained network (+0.0028);
  3. single-species network plus conventional ensemble (+0.0096);
  4. pretrained network plus conventional ensemble (+0.0104).
- One panel on one scale. Region-by-region results go in the supporting information.

**Why:** this is the practical take-home for applied modellers, and it shows directly that the useful network gains do not depend on pretraining.

### Figure 4: What counts as an absence changes the verdict (merges current Fig. 3 and Table 2)

*Model rankings depend on which negative observations the test uses.*

- **(a) Birds:** pretrained network minus conventional model, plotted against how well recorded the background cells are (10–24, 25–99, and 100+ other species recorded). Show familiar places for 59 species, and SEH and NNC within the held-out regions.
- **(b) Tasmania:** AUC for each learner, with and without constructed pseudoabsences in training, scored against the mixed negatives and against survey-supported negatives only. A dot-and-line plot reads faster than the eight-row Table 2. The TSS half of Table 2 moves to the supporting information.

**Why:** this tests hypothesis 4 (that the learners share an observation process) and generalises to every presence-only SDM. It frees one table slot.

### Table 1: Cases and headline performance (merges current Table 1 with Table S1f)

One row per case and setting:

| Column | Contents |
|---|---|
| Case | Tasmanian mammals, mainland mammals → Tasmania, or birds with one row per held-out region and one pooled row |
| Species | number of target species |
| Prediction task | e.g. interpolation within held-out patches, transfer to an environmental edge |
| Excluded from fitting | what was withheld, including buffers |
| AUC, familiar places | pretrained, single-species and conventional models |
| AUC, new places | the same three models, plus the best ensemble where computed |

**Why:** the Ecography audit flagged that the absolute AUCs are hidden in the supplement. Readers need them to judge whether 0.003 matters. Putting the familiar-places and new-places columns side by side also shows the large absolute drop at a glance, so the extent result needs no separate figure.

## Moved to Supporting information

| Item | Current location |
|---|---|
| Learning curves for target data and for the auxiliary pool, including the frozen-encoder trajectory | text and Table S-series |
| Results under the true skill statistic (TSS) for all cases, including the Tasmania split between AUC and TSS | text and Table 2b |
| Absolute AUC under each scoring extent, shown as a full panel | current Fig. 2a |
| Per-region and per-species breakdowns | various |
| Maps of how pseudoabsence removal changes the predictions | sensitivity PDF |
| Detail on the least-recorded third of species | text |

## Gaps to fill before building

1. **Bootstrap intervals over species** for each plotted mean. The current resampling ranges describe species composition only. Decide whether to resample folds or seeds as well.
2. **Mammal ensembles.** Neural plus conventional ensembles were computed for birds only; the only mammal ensembles are across folds (Goal 046). Either compute neural plus conventional ensembles for the mainland and Tasmanian cases, which is cheap and post hoc, or leave those cells blank in Table 1.
3. **Map layers.** We need region outlines and the training-domain mask at a resolution that cannot reveal camera sites. Check this against the release boundary in the README.
