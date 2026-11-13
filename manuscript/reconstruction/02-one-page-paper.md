# Step 2: One-page paper

**Status:** draft v3, 13 November 2026. Adopts Codex's convergence proposal (`docs/audits/reconstruction-convergence-20261112.md`, board thread 162, message 3337) with four repairs: bird-only borrowing strength, ensemble chronology, subsampling wording, and novelty stated as purpose rather than priority. Claude then edited it for plain statement, so that exceptions are separate sentences rather than "although" clauses. It goes to Barry for his full read before step 3.

---

## Learning from other species improved distribution models within training regions, but not on average in new ones

**Introduction.** Conservation needs maps of where species live, especially where records are sparse. Species distribution models draw them by relating records to environment. Neural networks can learn from other species before adapting to a target. Their gains weaken under geographic transfer (Basile et al. 2026). A successful multi-species model does not, by itself, reveal what sharing contributed. That requires comparison with the same network trained only on the target, in regions excluded from development.

Shared environmental responses give three predictions: pretraining improves prediction within the development region; its gain grows as target records shrink; and it persists in new regions. Development results raised a diagnostic question: do model rankings depend on the evidence used for absence?

**Methods.** We studied three cases:
- eight Tasmanian mammals, assessed in five held-out patches;
- five mainland mammals, transferred to Tasmania;
- 157 south-eastern Australian birds, 73 of them assessed in three bioregions withheld with 50 km buffers.

Inputs were grid-cell climate and habitat summaries. We compared three learners:
- a multilayer perceptron, a standard deep-learning model, pretrained on other species and fine-tuned to the target;
- an identical network trained on the target alone;
- a conventional model selected within the development data.

Targets were excluded from pretraining, and assessment regions from all fitting. Spatial folds assessed unseen cells within the development domain.

Primary comparisons and learning curves were fixed before the withheld data were opened, and the richness diagnostic after development but before opening. Averaging fine-tuned and conventional predictions was prespecified as exploratory; target-only averaging, extent rescoring and survey-only evaluation were post hoc. We measured discrimination as the area under the receiver operating characteristic curve (AUC).

**Results.** Pretraining improved development AUC for mainland mammals (+0.009; four of five species) and birds (+0.006; 72 of 73). The bird gain held within bioregions and folds (+0.007; 68 of 73). Reducing bird target data to a quarter raised the matched gain to +0.009. For the least-recorded species, pretraining added +0.0041 over the single-species network and +0.0006 over conventional models. Tasmanian mammals showed no development gain (−0.007).

In new regions the average gain disappeared, at −0.016 for mainland mammals and −0.0004 for birds. Thirty-four bird species and one region (+0.006) benefited. In Tasmania's held-out patches, pretraining lowered AUC (−0.015) and raised the threshold-based true skill statistic (+0.048).

In new bird regions, either network exceeded the conventional model by 0.003 AUC. A fixed 50:50 average of network and conventional predictions exceeded it by 0.010. Absolute AUC was 0.83 in development and 0.68 in new regions. Development predictions scored within bioregions and folds already sat at 0.69.

The neural advantage declined as background recording richness increased, from +0.005 to −0.004 in development. It also declined in both new regions that could be assessed. In Tasmania, scoring against survey-supported negatives alone turned the pretrained network's deficit to the conventional model (−0.005) into a lead (+0.015).

**Discussion.** Pretraining improved development prediction for mainland mammals and birds, and more so for birds when their records were subsampled. In new regions its average gain vanished. The network's small advantage there was available without pretraining, and averaging network and conventional predictions gave the larger mean gain. Model rankings depended on the negative evidence used to score them.

These tests used tabular inputs; imagery or spatial context could give different results. The bird single-species network inherited an architecture selected for fine-tuning. Shared geography, taxa and auxiliary models make the species summaries descriptive. The design cannot separate niche information, recording patterns and optimisation as explanations for the transfer outcomes.

Claims that learning across species improves prediction need a matched single-species control, evaluated where predictions will be used. Recording where species were sought and not detected would strengthen both the models and their evaluation.
