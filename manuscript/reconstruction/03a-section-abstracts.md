# Step 3a: Section abstracts

**Status:** draft v2, 13 November 2026. Claude wrote v1 (0cdc4c7). Codex reviewed it (`docs/audits/reconstruction-step3a-review-20261113.md`, thread 162, message 3353) and supplied replacement sections. This version adopts those sections with three wording edits by Claude. Barry reviews at the final draft.

Each section summary is a complete account of what that section will say, at most 300 words. The headings follow Ecography's IMRaD: Introduction, Material and methods, Results, Discussion. Word counts exclude headings and Markdown markers.

Main message: *Training AI on many species improved predictions of where species live in familiar regions, but on average not in new ones.*

---

## Introduction

Conservation needs predictions where species records are sparse, often by transferring models from well-sampled areas (Yates et al. 2018). Species share responses to climate and habitat, so records of one species can inform predictions for another (Ovaskainen et al. 2025). Multi-species pretraining fits a neural network to other species before adapting it to a target. Shared learning has improved ecological prediction (Chen et al. 2017; Norberg et al. 2019; Brun et al. 2024; Bourel et al. 2025; Lange et al. 2025). Neural joint models' advantages weaken under geographic transfer (Basile et al. 2026).

A successful multi-species model does not reveal what sharing contributed. Comparing a pretrained network with the same architecture trained only on the target measures the increment from pretraining. Comparing either network with a conventional model assesses its practical advantage. Same-architecture and no-transfer controls have precedents (Chen et al. 2017; Bourel et al. 2025). We combine them with target-excluded pretraining and geographic exclusion to ask whether sharing helps in new regions.

Evaluation also shapes the answer. Predicting a new region differs from predicting withheld cells inside a sampled domain (Wenger & Olden 2012; Roberts et al. 2017). AUC depends on the geographic extent of the presence–negative comparisons (Lobo et al. 2008). Background locations and survey nondetections provide different negative evidence; occurrence models can learn recording patterns alongside habitat associations (Phillips et al. 2009; Warton et al. 2013).

Shared environmental responses motivate three predictions: pretraining improves development prediction, its gain grows as target records shrink, and that gain persists in new regions. Development results raised a diagnostic question: do rankings depend on the evidence used for absence? We investigate these questions in three Australian mammal and bird cases.

## Material and methods

We synthesise three experiments (Table 1; Fig. 1). Development assessment used spatial folds within the training domain; geographic assessments withheld five Tasmanian patches, all Tasmania, or three buffered bird regions.

Atlas of Living Australia occurrence records (2001–2025) and Tasmanian camera surveys supplied responses. Inputs summarised grid-cell climate and habitat.

- **Tasmanian mammals:** eight species, using presences, camera-supported nondetections and constructed pseudoabsences, assessed in five held-out patches.
- **Mainland mammals:** five targets, each pretrained on 19 auxiliary mammals, transferred to camera-supported Tasmania records.
- **Birds:** 505 taxa supplied recording support for 157 targets; 73 were assessed in Naracoorte Coastal Plain, South Eastern Highlands and NSW North Coast. All three regions and their 50 km buffers were excluded simultaneously.

A residual multilayer perceptron learned shared features through separate auxiliary-species heads. Fine-tuning updated those features and a new target head. The target-only control used the same architecture, target data, optimisation and evaluation, starting from random weights. Pretraining excluded the target and, in birds, its whole computational block. Frozen-encoder and pooled-community controls tested alternative uses of shared information. Five conventional candidates were selected within development data. Transformations were fitted on training partitions; model selection used development information.

Bird and Tasmania target-data curves used 25%, 50% and 100%; bird auxiliary pools contained 20, 80 or all eligible species. Corrected mainland comparisons used full target data. Tasmania separately tested removing training pseudoabsences and filtering evaluation negatives.

AUC was primary, with TSS co-primary in Tasmania. Bird geographic summaries averaged regions within species, then species equally; development summaries averaged folds. Neural predictions averaged five matched seeds before scoring. TSS thresholds were fixed from development predictions. Bird ranges resample species composition.

Primary comparisons and curves preceded withheld-response access; richness diagnostics followed development discovery but preceded opening. Fine-tuned/conventional averaging was prespecified as exploratory. Extent rescoring, target-only averaging and survey-only evaluation were post hoc.

## Results

Pretraining improved development AUC for mainland mammals (+0.009; four of five species) and birds (+0.006; 72 of 73). The bird increment remained positive within bioregions and spatial folds (+0.007; 68 of 73). At full auxiliary size, the frozen-encoder control gained +0.0022 over target-only for the 73 birds. Subsampling bird target data from full to half to quarter increased the pretraining increment from +0.0058 through +0.0075 to +0.0095. The least-recorded third of bird species gained +0.004 over target-only and +0.0006 over conventional models. Tasmania's development mean was negative (−0.007).

In new regions the mean increment was −0.016 for mainland mammals and −0.0004 for birds, with 34 of 73 bird species benefiting. Bird regional means were +0.006 in Naracoorte Coastal Plain and −0.004 in both South Eastern Highlands and NSW North Coast. In Tasmania's held-out patches, pretraining lowered AUC by 0.015 and raised TSS by 0.048.

In new bird regions, either network exceeded conventional models by 0.003 AUC; fixed 50:50 averaging gained 0.010. Absolute AUC was 0.83 in development and 0.68 in new regions. Unchanged development predictions scored within bioregions and folds gave 0.69.

The fine-tuned-minus-conventional AUC contrast declined across background recording-richness bins. Development contrasts were +0.005, +0.002 and −0.004 for 10–24, 25–99 and at least 100 other recorded species. The decline recurred in both supported withheld regions.

At full target data, survey-only evaluation reversed the fine-tuned-minus-conventional mean AUC contrast from −0.005 to +0.015. Removing training pseudoabsences lowered mean AUC against mixed negatives, raised it against survey-supported negatives and changed the highest-scoring cells for all seven affected species.

## Discussion

The clearest bird result is that the small average neural advantage in new regions was available without pretraining. A conventional-model comparison alone could have attributed that advantage to sharing; the matched target-only network identifies the additional contribution of pretraining.

The development gains show that shared information improved predictions in the tested setting. The frozen-encoder gain shows the shared features were useful without adapting them to each target. In new regions, the increment varied among species and regions, including a positive mean in Naracoorte Coastal Plain. Averaging neural and conventional predictions produced a larger mean bird AUC gain with either network. This supports testing complementary learners alongside auxiliary-pool size when seeking predictive improvement (Norberg et al. 2019; Valavi et al. 2022).

Three implications guide further tests. Subsampling well-recorded species and predicting naturally poorly recorded species address different data limitations. Regional AUC can fall without transferring a fitted model, so compare learners on the same observations. Negative evidence defines the prediction problem: evaluation choices changed rankings, while removing training pseudoabsences and refitting changed maps.

These comparisons use tabular inputs; spatial context and imagery may provide different transferable information (Deneu et al. 2021). The bird target-only network inherited an architecture selected using fine-tuning. Larger auxiliary pools changed both record volume and species composition. Species share geography, taxa and auxiliary models, so summaries are descriptive. Extent rescoring, target-only averaging and survey-only evaluation were post hoc. The training-negative sensitivity was implemented after primary outcomes. Backgrounds and camera nondetections do not establish ecological absence. The design does not identify niche structure, recording processes or optimisation as mechanisms (Kumar et al. 2022).

Fresh regional tests should combine spatial inputs, observation-aware models and independent surveys under prespecified rules (Johnston et al. 2021). Claims of cross-species benefit need a matched single-species control where predictions will be used.

---

## Decisions from the v1 review

- **Practical claim:** the paper recommends testing complementary learners *alongside* auxiliary-pool size. It claims no order of investment, because the development pool curves and the new-region ensemble gains are different experiments.
- **Frozen encoder:** +0.0022 for the primary 73 birds at the full auxiliary pool (57 of 73 species positive). A target head is still fitted.
- **Tasmania:** these are full-target-data mean AUC results. Changing the evaluation negatives changes rankings, with training held fixed. Removing training pseudoabsences and refitting changes maps.
- **Richness gradient:** it declines in both supported new regions, but it starts negative in SEH, so the paper claims no sign reversal there.
- **Generalisation:** "three implications guide further tests", not "results carry beyond this study".
- **Learning curves:** these exist for birds and Tasmania only. The corrected mainland comparison uses full target data.
