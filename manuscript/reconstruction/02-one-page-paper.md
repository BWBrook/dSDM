# Step 2: One-page paper

**Status:** draft v2, 12 November 2026. Revised against Codex's review (`docs/audits/reconstruction-review-20261112.md`, R1–R14). It goes to Codex for a convergence check, then to Barry.

---

## Learning from other species improves distribution models within training regions, but not on average in new ones

**Introduction.** Conservation needs maps of where species live, above all where records are sparse; species distribution models (SDMs) draw them by relating records to environment. Neural networks offer an upgrade: learn first from many species, then adapt to the species of interest, borrowing information its own records lack. Their gains weaken under geographic transfer (Basile et al. 2026), but how much comes from learning other species, rather than from the network itself, is unmeasured. Measuring it needs an identical network trained on the target alone, tested in regions kept out of model development.

We asked whether learning from other species improves predictions in new regions. Species share responses to environment, which gives three predictions:
1. Pretraining improves prediction within the development region.
2. The gain grows as the target's own records shrink.
3. The gain persists in new regions.

Development results raised a fourth question: do model rankings depend on how well recorded the negative observations are?

**Methods.** We used three Australian cases:
- eight Tasmanian mammals from camera surveys, assessed in five held-out patches;
- five mainland mammals transferred to Tasmania;
- 157 south-eastern Australian birds, 73 of them assessed in three whole bioregions withheld with 50 km buffers.

Inputs were grid-cell climate and habitat summaries. For each target we compared:
- a multilayer perceptron, a standard deep-learning model, pretrained on other species and fine-tuned to the target;
- an identical network trained on the target alone;
- a conventional SDM selected within the development data.

Targets were excluded from pretraining, and withheld regions from all fitting. Development assessment used spatial folds inside the training domain. Primary comparisons, target-data curves, scoring and the richness diagnostic were fixed before the withheld data were opened; ensembles and the Tasmanian survey-only check came later. Discrimination was measured as the area under the receiver operating characteristic curve (AUC).

**Results.** Pretraining improved development predictions for mainland mammals (AUC +0.009; 4 of 5 species) and birds (+0.006; 72 of 73). The bird gain held when development predictions were scored within bioregions and spatial folds (+0.007; 68 of 73). It rose as target records shrank, from +0.006 at full data to +0.009 at a quarter. Tasmanian mammals showed no development gain (−0.007).

In new regions the average gain disappeared: −0.016 for mainland mammals transferred to Tasmania and −0.0004 for birds (34 of 73 improved), though one bird region was positive (+0.006). In Tasmania's held-out patches, pretraining lowered AUC (−0.015) but raised the threshold-based true skill statistic (+0.048).

In new bird regions, both networks beat the conventional model by 0.003. Averaging either network with it gained 0.010. Absolute AUC fell from 0.83 in development to 0.68 in new regions. Development predictions scored within bioregions and folds already sat at 0.69.

The neural advantage declined as background recording richness increased: from +0.005 to −0.004 in development, and similarly in the two new regions that could be assessed. In Tasmania, scoring against survey-supported negatives alone turned the pretrained network's deficit to the conventional model (−0.005) into a lead (+0.015).

**Discussion.** Predictions 1 and 2 held for mainland mammals and birds. Prediction 3 failed on average, although individual species and one bird region benefited. In new regions, the network's advantage was available without pretraining, and fixed averaging with a conventional model gave the larger mean gain. Model rankings changed with the source of negative evidence.

The models used tabular inputs; networks that see imagery or spatial context may share more transferable information. The single-species network inherited an architecture chosen for fine-tuning. The cases share geography and some taxa, so the cross-case summaries are descriptive. Our design cannot tell whether lost transfer reflects niche structure, recording patterns or optimisation.

A successful multi-species model needs a matched single-species twin, tested in the regions and against the observations where predictions will be used, to show what sharing contributed. For practitioners, averaging network and conventional predictions was the larger gain here. Better records of where species were sought and not detected would sharpen both the models and the tests that rank them.
