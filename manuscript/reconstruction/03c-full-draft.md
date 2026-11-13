# Step 3c: Full draft

**Status:** draft v1, 13 November 2026 (Claude). Expanded from the paragraph abstracts (`03b-paragraph-abstracts.md`, v2, 6a5be86), with detail taken from `manuscript/text/main.md` and the values Codex verified in the 3a and 3b reviews. For Codex review. After convergence it replaces the body of `main.md`, and Barry reviews that final draft.

Citations use Pandoc keys. Seven new keys need entries in `refs.yaml`, with identities verified in `manuscript/references/reconstruction-reference-check-20261113.json`: `basile2026`, `pili2025`, `fithian2015`, `he2016`, `hanley1982`, `allouche2006` and `breiner2015`. The end matter (data availability, AI statement) carries over from `main.md` when the draft is integrated.

---

# Learning from other species improved distribution models within training regions, but not on average in new ones

## Abstract

Neural networks that learn from many species promise better distribution models, yet the source of their gains is rarely tested against an identical network trained on the target alone, in new regions where predictions are used. We pretrained multilayer perceptrons on other species, fine-tuned them to each target, and compared them with matched single-species networks and conventional models in Tasmanian mammals, mainland mammals transferred to Tasmania, and 73 birds in three withheld bioregions. Pretraining improved development discrimination for mainland mammals and birds (AUC +0.009 and +0.006), especially when bird records were subsampled, but gave no average gain in new regions (mammals −0.016; birds −0.0004). In new bird regions, the network's advantage over conventional models was available without pretraining (+0.003), and averaging network and conventional predictions gained most (+0.010). Model rankings changed with the source of negative observations. Multi-species gains should be measured against single-species twins where predictions are needed.

**Keywords:** deep learning, model transferability, negative observations, pretraining, spatial cross-validation, species distribution models

## Introduction

Conservation decisions often depend on where a species occurs in places it has rarely been recorded. Species distribution models supply such predictions by relating records to environment in well-sampled areas and projecting those relationships elsewhere. The projection is useful only where the fitted relationships hold, and models transferred to new regions often lose skill [@wenger2012; @yates2018]. Methods that transfer better would widen what distribution models can offer conservation.

Species share responses to climate and habitat, so records of one species carry information about others [@ovaskainen2025]. Joint models, species embeddings and neural networks with shared representations all exploit this, and shared learning has improved ecological prediction [@chen2017; @norberg2019; @brun2024]. Multi-species pretraining is a simple neural form of the idea: a network learns from many species, then adapts to a target, drawing on information that the target's own records lack. In a continental-to-regional comparison in Europe, the development advantage of neural joint models did not persist under transfer [@basile2026].

A successful multi-species model does not reveal what sharing contributed. The architecture, its optimisation or its capacity could produce the same gain with no information from other species. Two comparisons separate these sources. A pretrained network compared with the same architecture trained only on the target measures the increment from pretraining. Either network compared with a conventional model measures its practical advantage. Same-architecture and no-transfer controls have precedents [@chen2017; @bourel2025]. We combine them with pretraining that excludes the target species and with whole-region geographic exclusion, so that the increment is measured where the model was not developed.

Where a model is tested shapes what the test can show. Predicting withheld cells inside a sampled domain is a different task from predicting a whole new region, and spatial cross-validation should match the intended use [@wenger2012; @roberts2017]. Scores also depend on the extent over which they are computed. AUC is the probability that a randomly chosen presence outscores a randomly chosen negative. Across a large domain many such pairs span very different environments and are easy to rank; within a region they are not [@lobo2008; @jimenezvalverde2012]. Absolute AUC can therefore fall with no change in predictions, and sampling design alters apparent model performance [@pili2025].

Most occurrence data record where species were found, not where they were absent. Models fitted against background locations learn where observers looked as well as where species live [@phillips2009; @warton2013]. Species recorded by the same observers share that signal, which is why pooling species helps estimate sampling bias [@fithian2015]. Pretraining could therefore transfer information about recording as well as about niches. Survey nondetections provide a different, sparser negative class. Comparing the two shows how far a model ranking depends on the evidence used for absence [@johnston2021].

Here we ask whether learning from other species improves distribution models in new regions. Shared environmental responses give three predictions:
- pretraining improves prediction within the development region;
- its gain grows as the target's own records shrink;
- the gain persists in new regions.

Development results raised a diagnostic question: do model rankings depend on the evidence used for absence? We test the predictions with tabular climate and habitat inputs in three Australian cases:
- eight Tasmanian mammals;
- five mainland mammals transferred to Tasmania;
- 157 birds, 73 of them assessed in three bioregions withheld from all model development.

## Material and methods

### Study design

We synthesise three separately specified experiments, each addressing a different prediction task (Table 1, Fig. 1). They share some taxa, observation sources and Tasmanian geography, so cross-case summaries are descriptive. *Development* denotes assessment by spatial folds within the training domain. *Geographic assessment* withheld one of three things, depending on the case:
- five Tasmanian patches;
- all of Tasmania;
- three buffered bird bioregions.

In every case, models discriminate recorded presences from specified negative observations, so their outputs are relative scores rather than occupancy probabilities.

**Table 1.** Prediction settings, geographic exclusions and mean AUC. All development assessments used five spatial folds. The three bird regions share one training domain and the same 73-species panel. Regional roles were specified before model outcomes were seen.

| Setting | Targets | Geographic task | Excluded from development |
|---|---:|---|---|
| Tasmanian mammals | 8 | Interpolation in five patches | Patch cells; no buffer |
| Mainland mammals | 5 | Transfer to camera-supported Tasmania | All Tasmania |
| Birds: Naracoorte Coastal Plain (NCP) | 73 | Environmentally supported transfer | Region plus 50 km |
| Birds: South Eastern Highlands (SEH) | 73 | Transfer to an environmental edge | Region plus 50 km |
| Birds: NSW North Coast (NNC) | 73 | Transfer to a fragmented land-use mosaic | Region plus 50 km |

[Codex: add AUC columns for fine-tuned, target-only and conventional learners, in development and geographic assessment, from the accepted synthesis. Add a pooled bird row. No ensemble columns.]

Occurrence records for 2001–2025 came from the Atlas of Living Australia [@belbin2021ala], and camera surveys supplied survey-supported responses in Tasmania. The mainland and bird experiments shared a versioned environmental substrate that included WorldClim 2.1 climate [@fick2017worldclim]. The Tasmanian experiment used a separate legacy stack of 28 predictors, encoded as 77 columns. Bird inputs were 24 variables, encoded as 103 columns:
- 19 bioclimatic variables;
- elevation mean and standard deviation;
- vegetation group;
- soil order;
- land-use class.

Scaling and categorical encoding were fitted on the training side of each partition. Predictor definitions, available source metadata and provenance gaps are documented in Supporting information.

The Tasmanian experiment modelled eight mammal species on a 0.01° grid. Responses comprised recorded presences and two negative sources: camera-supported nondetections and constructed pseudoabsences. Unknown species–cell combinations were masked from the loss and from evaluation. Of 12,711 resolved response rows, 11,039 were used for development and 1,672 fell in five patches (606 cells) fixed before modelling. The patches touch training areas and have no buffer, so they assess interpolation within Tasmania.

The mainland experiment pretrained on 19 auxiliary mammal species for each of five targets. A background cell needed records of at least three other support species and had to lie at least 5 km from any target presence. Tasmania supplied no training responses or fitted transformations. The primary assessment used 4,077 camera-supported species–cell rows in Tasmania, with an all-source assessment as secondary. The transfer therefore changed observation source as well as geography.

The bird experiment used records of 505 taxa, the recording-support set, to identify sampled cells. A background cell had no record of the focal species and records of at least ten other support-set species; a stricter threshold of 20 was also evaluated. Recording richness was never a predictor. Of 259 eligible species, 157 met the target support criteria. Seventy-three had enough data in each of three bioregions, which were chosen before outcomes were seen as contrasting settings:
- Naracoorte Coastal Plain, for environmentally supported transfer;
- South Eastern Highlands, an environmental edge;
- NSW North Coast, a fragmented land-use mosaic.

All three regions and their 50 km buffers were excluded from development together. Development folds kept projected 50 km spatial blocks intact.

### Learners

Every network was a residual multilayer perceptron [@he2016]. During pretraining, a shared encoder transformed environmental inputs into features, which fed a separate prediction head for each auxiliary species. Auxiliary species contributed equal total weight and kept their own class balance. The focal target was always excluded from pretraining. In birds, targets were grouped into ten computational blocks, and the whole block containing the focal target was excluded from the auxiliary heads. Geographic exclusions applied to pretraining as well as to target fitting.

Fine-tuning fitted a new target head and updated the shared encoder with the target's data. The target-only network used the same architecture, target responses, optimisation and evaluation rules, starting from random weights. The paired difference between the two measures the increment from pretraining. A frozen-encoder control fitted only a target head on the pretrained features [@kumar2022]. A pooled-community control added a target-excluded community prediction as one covariate. For birds, one architecture was selected from four fixed candidates by fine-tuning performance on the 73-species development panel: six residual blocks of width 256 and a bottleneck of width 128. The target-only network inherited it [@cawley2010], and it exceeded a separately tuned shallow network by 0.0037 development AUC. Final neural predictions averaged five matched seeds before scoring.

The conventional candidates were an intercept model, elastic-net logistic regression, random forest, histogram gradient boosting and a shallow neural network [@valavi2022]. Hyperparameters and the preferred family were selected within the development data and then fixed for geographic prediction. Early stopping, replay and refitting also used development data only. No withheld response selected a model, epoch, ensemble weight or threshold. Specifications and software versions are in Supporting information.

### Analyses

Bird learning curves were run on the primary 73-species panel. They crossed 25%, 50% and 100% of target training data with auxiliary pools of 20, 80 or all eligible species, so larger pools added both records and species. The Tasmanian experiment used three nested target-data ladders at reduced fractions, giving seven endpoints. The corrected mainland comparison used full target data. Conventional models were reselected at each fraction.

In Tasmania we also removed the constructed pseudoabsences from target training: 368 full-data rows, or 3.3% of training rows and 16.4% of training negatives. The architecture, pretrained auxiliary states and selected conventional candidates were kept. Targets were refitted and thresholds reselected.

AUC was the primary metric [@hanley1982]. The true skill statistic (TSS; sensitivity plus specificity minus one) was co-primary in Tasmania [@allouche2006]. Its thresholds were chosen by maximum TSS on development out-of-fold predictions and held fixed for geographic assessment. Bird geographic summaries averaged the three regional AUCs within species, then weighted species equally; development summaries averaged folds within species. We report paired species contrasts, means and counts of positive species, keeping every species. Single-species deletion and paired species-composition resampling, with central 95% ranges, describe how much results vary with panel composition alone.

Four diagnostics interpret the main contrasts:
- **Recording richness.** Bird discrimination was compared against background cells holding records of 10–24, 25–99 or at least 100 other support-set species, reusing all focal presences across the three bins.
- **Extent.** Unchanged development predictions were rescored within named retained bioregions, and within region-by-fold strata, requiring at least 30 and 20 cells per class respectively.
- **Averaging.** Fixed equal-weight ensembles combined each network's saved scores with those of the conventional model.
- **Negative evidence.** Tasmanian patch evaluation was repeated against survey-supported negatives only: 1,300 presences and 242 negatives, excluding 130 pseudoabsences.

The analyses were fixed at different stages:
- the primary comparisons and learning curves, before withheld responses were opened;
- the richness diagnostic, found in development, with its geographic version fixed before opening;
- the fine-tuned/conventional ensemble, prespecified as exploratory;
- extent rescoring, target-only averaging and survey-only evaluation, post hoc;
- pseudoabsence removal, proposed in the original protocol and implemented after the primary outcomes.

## Results

### Development

Pretraining improved development prediction for mainland mammals and birds (Fig. 2). For mainland mammals, fine-tuning gained +0.0087 mean AUC over the target-only network (four of five species) and +0.0040 over conventional models (all five). For birds the gains were +0.0058 (72 of 73) and +0.0034 (67 of 73). The bird increment held when development predictions were scored within bioregions and spatial folds (+0.0072; 68 of 73), and it stayed positive under species resampling. Tasmanian mammals showed no development gain: fine-tuning trailed target-only by 0.0068 and conventional models by 0.0498.

The bird increment grew as target data were subsampled:

| Target data | Fine-tuned − target-only | Fine-tuned − conventional |
|---|---:|---:|
| Full | +0.0058 | +0.0034 |
| Half | +0.0075 | +0.0053 |
| Quarter | +0.0095 | +0.0069 |

At a quarter of their data, primary-panel targets still kept a median of about 2,800 presence cells. The least-recorded third of all 157 targets comprised 53 species with 224–3,649 presence cells. For them, fine-tuning gained +0.0041 over target-only and +0.0006 over conventional models. The shared features were reusable. The frozen encoder's contrast with target-only rose from −0.0044 with 20 auxiliary species to +0.0022 with the full pool, positive for 57 of 73 species. Full fine-tuning's increment peaked at 80 auxiliary species (+0.0061).

### New regions

In new regions the mean increment from pretraining disappeared (Fig. 2).
- **Mainland mammals transferred to Tasmania.** Fine-tuning trailed target-only by 0.0155 mean AUC. Three of five species benefited, and the median was +0.0269.
- **Birds.** Across the three withheld regions, mean AUC was 0.6827 for fine-tuning and 0.6831 for target-only. The paired difference of −0.0004 was positive for 34 of 73 species. Regional means were +0.0064 in Naracoorte Coastal Plain, −0.0040 in South Eastern Highlands and −0.0035 in NSW North Coast. The species-resampling ranges for both geographic contrasts spanned zero.
- **Tasmania's withheld patches.** The co-primary metrics disagreed. Fine-tuning trailed target-only by 0.0147 mean AUC, positive for one of eight species, and led it by 0.0477 mean TSS, positive for five with one tie.

In new bird regions, the networks' advantage over conventional models did not depend on pretraining (Fig. 3). The target-only network exceeded conventional models by +0.0032 mean AUC and the fine-tuned network by +0.0028. Fine-tuning's regional contrasts were +0.0078, −0.0071 and +0.0076. Fixed 50:50 averaging with conventional predictions gained more with either network:

| Ensemble with conventional model | AUC | Gain over conventional | Species positive |
|---|---:|---:|---:|
| Fine-tuned | 0.6903 | +0.0104 | 60 of 73 |
| Target-only | 0.6896 | +0.0096 | 64 of 73 |

The two ensembles differed by 0.0007, and the fine-tuned ensemble was ahead for 37 species.

### Diagnostics

Absolute bird AUC was 0.83 in development and 0.68 in new regions (Table 1). The unchanged development predictions were also scored more narrowly:
- within named bioregions, they gave 0.691;
- within region-by-fold strata, they gave 0.690, close to the new-region mean of 0.683.

Regional scoring removed 360,625 cells outside the named regions and changed which presence–background pairs entered AUC. The pretraining increment stayed positive under both regional scorings: +0.0110 within bioregions (56 of 73 species) and +0.0072 within strata (68 of 73).

Fine-tuning's advantage over conventional models declined as background recording richness increased (Fig. 4a):

| Panel | Species | 10–24 other species | 25–99 | 100 or more |
|---|---:|---:|---:|---:|
| Development | 59 | +0.0050 | +0.0019 | −0.0039 |
| South Eastern Highlands | 38 | −0.0038 | −0.0140 | −0.0283 |
| NSW North Coast | 55 | +0.0148 | +0.0060 | −0.0259 |

In development, the increment over target-only followed the same pattern (+0.0075, +0.0039, −0.0043). The geographic decline is from the prespecified diagnostic. Naracoorte Coastal Plain had no species supported in all three bins. High-richness background was rare in new regions, with mean within-species shares of 0.3–2.8%.

In Tasmania, the source of negative evidence changed the ranking of fine-tuning and conventional models (Fig. 4b). Under original training at full target data, fine-tuning trailed conventional models by 0.0051 mean AUC against mixed negatives. It led them by 0.0154 against survey-supported negatives alone. Removing pseudoabsences from training lowered mean AUC against mixed negatives for all three learners; fine-tuning went from 0.839 to 0.766. It raised mean AUC against survey-supported negatives, from 0.835 to 0.857 for fine-tuning. Retraining also changed the maps. The seven affected species retained 31–86% of their original top-scoring decile of cells. The eighth species had no pseudoabsences and reproduced its maps exactly.

## Discussion

The clearest result is that the network's small advantage in new bird regions was available without learning from other species. Fine-tuned and target-only networks both exceeded conventional models there, by 0.0028 and 0.0032 AUC, while the matched pretraining contrast averaged −0.0004. A comparison with conventional models alone would have credited that advantage to shared learning. Basile et al. [-@basile2026] found that the advantage of neural joint models did not persist under transfer. The target-only control identifies how much of a neural advantage comes from sharing.

Shared information was real. Pretraining improved development prediction for mainland mammals and birds, and the bird increment grew under subsampling. A frozen encoder with only a new target head outperformed a network trained from scratch. These results agree with the predictive value of shared learning reported for species embeddings, joint models and pretrained representations [@chen2017; @brun2024; @bourel2025; @ovaskainen2025; @lange2025]. In new regions the increment varied among species and regions. Naracoorte Coastal Plain, chosen for environmentally supported transfer, had a positive mean, and 34 of 73 species benefited. The information that helped in development did not add consistent value after geographic transfer.

For a modeller seeking better predictions in new regions, averaging gave the larger gain. Equal-weight ensembles of a network and a conventional model raised mean AUC by about 0.010 with either network, three times the network's own advantage. They used retained predictions and no fitted weights. Ensembles of complementary learners have long been recommended for distribution models [@araujo2007], and their value depends on the components and how they are implemented [@norberg2019; @valavi2022]. Complementary learners therefore deserve comparison alongside larger auxiliary pools.

Data efficiency needs an ecological reading. Pretraining's increment grew as the primary bird panel was subsampled, but those targets kept thousands of presence cells even at a quarter of their data. The least-recorded third gained +0.0041 over target-only and +0.0006 over conventional models. Subsampling an abundant record and predicting a naturally rare species are different problems. The second calls for tests built around rare species and the methods designed for them [@breiner2015].

Absolute AUC fell from 0.83 in development to 0.68 in new regions, which on its own suggests a severe failure of transfer. Yet development predictions scored within bioregions and folds gave 0.69: regional scoring alone produces low AUC, with no model transferred. Within a region, the broad environmental contrasts that make presence–background pairs easy to rank disappear [@lobo2008; @jimenezvalverde2012]. The development and geographic assessments also differ in fitted models, environmental composition and recording support. Comparing learners on the same observations shows what transfer does to their relative performance [@yates2018].

The choice of negative evidence changed which model ranked first. In Tasmania, restricting evaluation to survey-supported negatives reversed the mean AUC ranking of fine-tuning and conventional models, with predictions unchanged. Removing training pseudoabsences and refitting changed which cells scored highest. In birds, the neural advantage fell as background became better recorded. Defining the negative class is thus part of specifying both the model and the test [@phillips2009; @warton2013; @fithian2015; @pili2025].

These conclusions have limits:
- They rest on tabular climate and habitat summaries; spatial context and imagery may carry information that transfers better [@deneu2021].
- The bird target-only network inherited an architecture selected for fine-tuning [@cawley2010].
- Larger auxiliary pools added records and species together.
- Shared geography, taxa and auxiliary models make the species and case summaries descriptive.
- Extent rescoring, target-only averaging and survey-only evaluation were post hoc.
- Background cells and camera nondetections are not ecological absences.
- Recording richness combines survey effort, community richness and environment.
- The design cannot separate niche structure, recording processes and optimisation effects such as feature distortion [@kumar2022] as causes of the transfer result.

Fresh regional tests should pair matched target-only controls with spatial inputs, observation-aware models and independent surveys [@johnston2021], under rules fixed before outcomes are seen. Any claim that learning across species improves prediction needs that single-species twin, evaluated where its predictions will be used.

---

## Notes for Codex

1. **Length and splits.** The main text runs to about 2,900 words, plus four small tables: Introduction 540, Methods 1,110, Results 618, Discussion 647. That is well under the 4,800-word plan and Ecography's 5,000. I kept it lean deliberately. Add words only where a reader or reviewer would otherwise lack something they need. I split the last Discussion paragraph into limitations and next tests, with the next tests ending the paper. Methods gained a separate paragraph on timing. Tables of numbers went into Results where a sentence would have held five numbers.
2. **Overwriting.** Barry's instruction for this stage is to add flesh "judiciously. Don't overwrite!" Please mark any sentence that repeats another, fills space or could be cut.
3. **Numbers drawn from `main.md`.** These have not passed your 3a/3b reviews. Please verify each:
   - mainland fine-tuned − conventional, +0.0040 (5/5);
   - bird +0.0034 (67/73);
   - Tasmania −0.0498;
   - the median of about 2,800 presences at a quarter of the data;
   - 53 species with 224–3,649 presence cells;
   - +0.0061 at 80 auxiliary species;
   - mainland median +0.0269;
   - the regional fine-tuned − conventional contrasts +0.0078, −0.0071 and +0.0076;
   - 37 species favouring the fine-tuned ensemble;
   - 360,625 cells;
   - +0.0110 (56/73);
   - +0.0075, +0.0039 and −0.0043;
   - background shares of 0.3–2.8%;
   - 3.3% and 16.4%;
   - the Tasmanian AUC values;
   - top-decile retention of 31–86%.
4. **Table 1 AUC columns:** please fill them from the accepted synthesis.
5. **Half-data cell.** The fine-tuned − conventional value at half data, +0.0053, comes from `main.md`. Please confirm it.
6. **Two interpretive sentences to check:**
   - D2: "A frozen encoder with only a new target head outperformed a network trained from scratch." It holds with the full auxiliary pool only. Is that scope clear enough from Results?
   - D3: "three times the network's own advantage" (0.010 against 0.003). Is this ratio sound, or should we give only the two numbers?
