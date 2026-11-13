# Step 3a: Section abstracts

**Status:** draft v1, 13 November 2026 (Claude). For Codex review, then the next expansion stage. Barry reviews at the final draft.

Each section summary is a complete account of what that section will say, at most 300 words. The headings follow Ecography's IMRaD: Introduction, Material and methods, Results, Discussion. Word counts exclude headings.

Main message: *Training AI on many species improved predictions of where species live in familiar regions, but on average not in new ones.*

---

## Introduction

Conservation needs predictions where species records are sparse, often by transferring models from well-sampled areas (Yates et al. 2018). Species share responses to climate and habitat, so records of one species carry information about another (Ovaskainen et al. 2025). Multi-species pretraining fits a neural network to many species, then adapts it to a target. Shared learning has improved ecological prediction (Chen et al. 2017; Norberg et al. 2019; Brun et al. 2024; Bourel et al. 2025; Lange et al. 2025). Its gains weaken under geographic transfer (Basile et al. 2026).

A successful multi-species model does not reveal what sharing contributed. Two comparisons do. A pretrained network against the same network trained only on the target measures what learning from other species adds. The target-only network against a conventional model measures what the network itself adds. Same-architecture controls have precedents (Chen et al. 2017; Bourel et al. 2025). We combine one with target-excluded pretraining and whole-region exclusion, to ask whether sharing helps where the model was not developed.

Two features of evaluation shape the answer. Predicting a whole new region is a different task from predicting withheld cells within a sampled domain (Wenger & Olden 2012; Roberts et al. 2017). AUC also depends on the extent over which presences and negatives are compared (Lobo et al. 2008). Negative observations are often background locations rather than surveyed absences. Models can therefore learn where observers looked as well as where species live (Phillips et al. 2009; Warton et al. 2013).

Shared environmental responses give three predictions:
- pretraining improves prediction within the development region;
- its gain grows as target records shrink;
- the gain persists in new regions.

Development results raised a diagnostic question: do model rankings depend on the evidence used for absence? We test these predictions in three Australian mammal and bird cases.

## Material and methods

We synthesise three separately specified experiments descriptively, because they share taxa, observation sources and Tasmanian geography (Table 1). *Development* means assessment by spatial folds within the training domain; *new regions* were excluded from all fitting.

Records (2001–2025) came from the Atlas of Living Australia and Tasmanian camera surveys. Inputs were grid-cell summaries of climate, terrain, vegetation, soil and land use.

The three cases:
- **Tasmanian mammals.** Eight species, modelled from presences, camera-supported nondetections and pseudoabsences, and assessed in five held-out patches.
- **Mainland mammals.** Five targets, each pretrained on 19 auxiliary mammals and transferred to camera-supported records in Tasmania, changing observation source as well as geography.
- **Birds.** Records of 505 taxa defined sampled background for 157 targets. Seventy-three were assessed in three contrasting bioregions withheld with 50 km buffers: Naracoorte Coastal Plain (environmentally supported), South Eastern Highlands (an environmental edge) and NSW North Coast (a fragmented land-use mosaic).

All networks were residual multilayer perceptrons:
- **Pretraining** fitted a shared encoder with one prediction head per auxiliary species. It excluded the target, and in birds the target's whole computational block.
- **Fine-tuning** adapted the encoder and a new head to the target.
- **The target-only control** used the same architecture, data, optimisation and evaluation, starting from random weights.
- **Frozen-encoder and pooled-community controls** tested simpler uses of shared information.
- **Conventional candidates** (five families) were selected within development data.

Learning curves varied target data (25, 50, 100%) and, in birds, auxiliary species (20, 80, all).

AUC was the primary metric, with the true skill statistic (TSS) co-primary in Tasmania. Bird summaries weight species equally, with species-composition resampling ranges.

Primary comparisons and curves were fixed before the withheld data were opened, and the recording-richness diagnostic after development but before opening. Fine-tuned/conventional averaging was prespecified as exploratory; extent rescoring, target-only averaging and survey-only evaluation were post hoc.

## Results

Pretraining improved development discrimination for mainland mammals (AUC +0.009; four of five species) and birds (+0.006; 72 of 73). The bird gain held when predictions were scored within bioregions and spatial folds (+0.007; 68 of 73). With the full auxiliary pool, the frozen encoder alone also improved on the target-only network. Subsampling bird target data from full to half to a quarter raised the gain from +0.006 to +0.007 to +0.009. For the least-recorded third of bird species, pretraining added +0.004 over the target-only network and +0.0006 over conventional models. Tasmanian mammals showed no development gain (−0.007).

In new regions the mean gain from pretraining disappeared. It was −0.016 for mainland mammals transferred to Tasmania and −0.0004 for birds, with 34 of 73 bird species improving. The regional means were:
- Naracoorte Coastal Plain, +0.006;
- South Eastern Highlands, −0.004;
- NSW North Coast, −0.004.

In Tasmania's held-out patches, pretraining lowered AUC by 0.015 and raised TSS by 0.048.

In new bird regions, both networks exceeded conventional models by 0.003, with or without pretraining. An equal average of either network with conventional predictions exceeded them by 0.010. Absolute AUC fell from 0.83 in development to 0.68 in new regions. Unchanged development predictions, rescored within bioregions and folds, gave 0.69.

The neural advantage over conventional models declined as background recording richness increased. In development it fell from +0.005 through +0.002 to −0.004. It also declined in both new regions with enough support.

In Tasmania, evaluating against survey-supported negatives alone turned the fine-tuned network's deficit to conventional models (−0.005) into a lead (+0.015). Removing pseudoabsences from training had three effects:
- it lowered performance against mixed negatives;
- it raised performance against survey-supported negatives;
- it changed which cells scored highest.

## Discussion

The clearest result is that the network's small advantage in new bird regions was available without learning from other species. Against conventional models alone, pretraining would have taken credit for it; the matched target-only network exposes the difference.

Development gains, including the frozen encoder's, show that useful shared information exists. In new regions its value varied, with a positive mean in Naracoorte Coastal Plain. Averaging network and conventional predictions gave the largest gain in new regions, whether or not the network was pretrained. Comparing complementary learners should therefore come before enlarging auxiliary pools (Norberg et al. 2019; Valavi et al. 2022).

Three results carry beyond this study:
- **Subsampling a well-recorded species differs from predicting a poorly recorded one.** The least-recorded species gained little over conventional models; rare-species tests are needed.
- **Absolute AUC was a poor guide to loss under transfer.** Rescoring unchanged predictions over smaller areas produced a similar fall; compare methods on the same observations.
- **The negative class is part of the prediction problem.** Changing it altered both rankings and maps.

These conclusions have limits:
- Inputs were tabular summaries; spatial context and imagery could carry more transferable information (Deneu et al. 2021).
- The target-only network inherited an architecture selected for fine-tuning.
- Larger auxiliary pools added both records and species.
- Shared taxa, geography and auxiliary models make summaries descriptive, and the extent, averaging and survey-only analyses are post hoc.
- Background cells and camera nondetections are not ecological absences.
- The design cannot separate niche structure, recording processes and optimisation effects (Kumar et al. 2022).

The next tests should add spatial inputs, observation-aware models and independent surveys (Johnston et al. 2021), assessed in fresh regions under prespecified rules. Any claim that a multi-species model succeeds by learning across species needs a matched single-species twin, evaluated where its predictions will be used.

---

## Reflection, for Codex

Each section reached 300 words or fewer only after cutting. These are the choices worth challenging:

1. **What I cut, and where it goes.** I cut grid resolution, predictor counts, seeds, the architecture search, the conventional families and the TSS threshold rule. They go to the full Material and methods. Does the Methods summary still let a reader judge the comparison as fair?
2. **The Introduction's third paragraph** sets up extent and negative evidence. It earns its place because two of the Results paragraphs depend on it. Is it the right weight against the main message?
3. **The Discussion's practical claim:** "Comparing complementary learners should therefore come before enlarging auxiliary pools." Do the auxiliary-pool curves license it?
4. **Please verify against the accepted values:**
   - the frozen-encoder development gain over the target-only network (full pool);
   - the richness bins (+0.005, +0.002, −0.004);
   - "declined in both new regions with enough support";
   - the three effects of removing pseudoabsences in Tasmania.
5. **"Three results carry beyond this study."** Is that generalisation earned, or should it say "three implications"?

