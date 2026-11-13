# Step 3c: Full draft

**Status:** draft v2, 13 November 2026. Claude wrote v1 (8b55501); Codex reviewed it (`docs/audits/reconstruction-step3c-review-20261113.md`, thread 162, message 3364), filled Table 1 and supplied the repairs integrated here. Expanded from the paragraph abstracts (`03b-paragraph-abstracts.md`, v2, 6a5be86), with detail taken from `manuscript/text/main.md` and the values Codex verified in the 3a and 3b reviews. For Codex review. After convergence it replaces the body of `main.md`, and Barry reviews that final draft.

Citations use Pandoc keys. Seven new keys need entries in `refs.yaml`, with identities verified in `manuscript/references/reconstruction-reference-check-20261113.json`: `basile2026`, `pili2025`, `fithian2015`, `he2016`, `hanley1982`, `allouche2006` and `breiner2015`. The end matter (data availability, AI statement) carries over from `main.md` when the draft is integrated.

---

# Learning from other species improved distribution models within training regions, but not on average in new ones

## Abstract

Neural networks that learn from many species promise better distribution models, yet the source of their gains is rarely tested against an identical network trained on the target alone, in new regions where predictions are used. We pretrained multilayer perceptrons on other species, fine-tuned them to each target, and compared them with matched single-species networks and conventional models in Tasmanian mammals, mainland mammals transferred to Tasmania, and 73 birds in three withheld bioregions. Pretraining improved development discrimination for mainland mammals and birds (AUC +0.009 and +0.006), especially when bird records were subsampled, but gave no average gain in new regions (mammals −0.016; birds −0.0004). In new bird regions, the network's advantage over conventional models was available without pretraining (+0.003), and averaging network and conventional predictions gained most (+0.010). Model rankings changed with the source of negative observations. Multi-species gains should be measured against single-species twins where predictions are needed.

**Keywords:** deep learning, model transferability, negative observations, pretraining, spatial cross-validation, species distribution models

## Introduction

Conservation decisions often depend on where a species occurs in places it has rarely been recorded. Species distribution models supply such predictions by relating records to environment in well-sampled areas and projecting those relationships elsewhere. The projection is useful only where the fitted relationships hold, and models transferred to new regions often lose skill [@wenger2012; @yates2018].

Species share responses to climate and habitat, so records of one species carry information about others [@ovaskainen2025]. Joint models, species embeddings and neural networks with shared representations all exploit this, and shared learning has improved ecological prediction [@chen2017; @norberg2019; @brun2024]. Multi-species pretraining is a simple neural form of the idea: a network learns from many species, then adapts to a target, drawing on information that the target's own records lack. In a continental-to-regional comparison in Europe, the development advantage of neural joint models did not persist under transfer [@basile2026].

A successful multi-species model does not reveal what sharing contributed. The architecture, its optimisation or its capacity could produce the same gain with no information from other species. A pretrained network compared with the same architecture trained only on the target measures the increment from pretraining. Either network compared with a conventional model measures its practical advantage. Same-architecture and no-transfer controls have precedents [@chen2017; @bourel2025]. We combine them with pretraining that excludes the target species and with whole-region geographic exclusion, so that the increment is measured where the model was not developed.

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

**Table 1.** Prediction settings, geographic exclusions and mean AUC. Development values average five spatial folds within species, then species equally. Tasmania patch values pool the withheld patches; mainland transfer uses camera-supported Tasmania records. Bird regional values average species within each named region, while the three-region mean first averages regions within species. All bird models exclude NCP, SEH and NNC and their 50 km buffers simultaneously. The regions' contrasting roles were specified before model outcomes were seen.

| Case and assessment | Targets | Geographic exclusion from development | Fine-tuned network | Target-only network | Conventional model |
|---|---:|---|---:|---:|---:|
| Tasmanian mammals: development | 8 | Five patches; no buffer | 0.7133 | 0.7200 | 0.7631 |
| Tasmanian mammals: withheld patches | 8 | Five patches; no buffer | 0.8390 | 0.8537 | 0.8441 |
| Mainland mammals: development | 5 | All Tasmania | 0.9091 | 0.9004 | 0.9052 |
| Mainland mammals: transfer to Tasmania | 5 | All Tasmania | 0.5560 | 0.5715 | 0.5837 |
| Birds: development | 73 | All three regions plus 50 km | 0.8316 | 0.8258 | 0.8282 |
| Birds: NCP transfer | 73 | All three regions plus 50 km | 0.6909 | 0.6846 | 0.6831 |
| Birds: SEH transfer | 73 | All three regions plus 50 km | 0.6827 | 0.6867 | 0.6897 |
| Birds: NNC transfer | 73 | All three regions plus 50 km | 0.6746 | 0.6781 | 0.6670 |
| Birds: three-region mean | 73 | All three regions plus 50 km | 0.6827 | 0.6831 | 0.6800 |

Occurrence records for 2001–2025 came from the Atlas of Living Australia [@belbin2021ala], and camera surveys supplied survey-supported responses in Tasmania. The mainland and bird experiments shared a versioned environmental substrate that included WorldClim 2.1 climate [@fick2017worldclim]. The Tasmanian experiment used a separate legacy stack of 28 predictors, encoded as 77 columns. Bird inputs were 24 variables, encoded as 103 columns:
- 19 bioclimatic variables;
- elevation mean and standard deviation;
- vegetation group;
- soil order;
- land-use class.

Preprocessing used training-partition estimates; Tasmania retained a fixed, response-independent categorical schema with training-only support masks. Predictor definitions, available source metadata and provenance gaps are documented in Supporting information.

The Tasmanian experiment modelled eight mammal species on a 0.01° grid. Responses comprised recorded presences and two negative sources: camera-supported nondetections and constructed pseudoabsences. Unknown species–cell combinations were masked from the loss and from evaluation. Of 12,711 resolved species–cell responses, 11,039 were used for development and 1,672 came from 606 observed cells within five patches fixed before modelling. The patches touch training areas and have no buffer, so they assess interpolation within Tasmania.

The mainland experiment pretrained on 19 auxiliary mammal species for each of five targets. A background cell needed records of at least three other support species and had to lie at least 5 km from any target presence. Tasmania supplied no training responses or fitted transformations. The primary assessment used 4,077 camera-supported species–cell rows in Tasmania, with an all-source assessment as secondary. The transfer therefore changed observation source as well as geography.

The bird experiment used records of 505 taxa, the recording-support set, to identify sampled cells. A background cell had no record of the focal species and records of at least ten other support-set species; a stricter threshold of 20 was also evaluated. Recording richness was never a predictor. Of 259 eligible species, 157 met the target support criteria. Seventy-three had enough data in each of three bioregions, which were chosen before outcomes were seen as contrasting settings:
- Naracoorte Coastal Plain, for environmentally supported transfer;
- South Eastern Highlands, an environmental edge;
- NSW North Coast, a fragmented land-use mosaic.

All three regions and their 50 km buffers were excluded from development together. Development folds kept projected 50 km spatial blocks intact.

### Learners

The pretrained and matched target-only models were residual multilayer perceptrons [@he2016]. During pretraining, a shared encoder transformed environmental inputs into features, which fed a separate prediction head for each auxiliary species. Auxiliary species contributed equal total weight and kept their own class balance. The focal target was always excluded from pretraining. In birds, targets were grouped into ten computational blocks, and the whole block containing the focal target was excluded from the auxiliary heads. Geographic exclusions applied to pretraining as well as to target fitting.

Fine-tuning fitted a new target head and updated the shared encoder with the target's data. The target-only network used the same architecture, target responses, optimisation and evaluation rules, starting from random weights. The paired difference between the two measures the increment from pretraining. A frozen-encoder control fitted only a target head on the pretrained features [@kumar2022]. A pooled-community control added a target-excluded community prediction as one covariate. For birds, one architecture was selected from four fixed candidates by fine-tuning performance on the 73-species development panel: six residual blocks of width 256 and a bottleneck of width 128. The target-only network inherited it [@cawley2010], and it exceeded a separately tuned shallow network by 0.0037 development AUC. Final neural predictions averaged five matched seeds before scoring.

The conventional candidates were an intercept model, elastic-net logistic regression, random forest, histogram gradient boosting and a shallow neural network [@valavi2022]. Hyperparameters and the preferred family were selected within the development data and then fixed for geographic prediction. Early stopping, replay and refitting also used development data only. No withheld response selected a model, epoch, ensemble weight or threshold. Specifications and software versions are in Supporting information.

### Analyses

Bird learning curves varied target data at the full auxiliary pool (25%, 50% and 100%) and auxiliary-pool size at full target data (20, 80 or all eligible species). These five endpoints used the primary 73-species panel; the other 84 targets were fitted at full target data and auxiliary size. Larger pools added both records and species. The Tasmanian experiment used three nested target-data ladders at reduced fractions, giving seven endpoints. The corrected mainland comparison used full target data. Conventional models were reselected at each fraction.

In Tasmania we also removed the constructed pseudoabsences from target training: 368 full-data rows, or 3.3% of training rows and 16.4% of training negatives. The architecture, pretrained auxiliary states and selected conventional candidates were kept. Targets were refitted and thresholds reselected.

AUC was the primary metric [@hanley1982]. The true skill statistic (TSS; sensitivity plus specificity minus one) was co-primary in Tasmania [@allouche2006]. Its thresholds were chosen by maximum TSS on development out-of-fold predictions and held fixed for geographic assessment. Bird geographic summaries averaged the three regional AUCs within species, then weighted species equally; development summaries averaged folds within species. We report paired species contrasts, means and counts of positive species, keeping every species. Single-species deletion and paired species-composition resampling, with central 95% ranges, describe how much results vary with panel composition alone.

Four diagnostics interpret the main contrasts:
- **Recording richness.** Bird discrimination was compared against background cells holding records of 10–24, 25–99 or at least 100 other support-set species, reusing all focal presences across the three bins. Development comparisons required at least 20 observations of each class in every fold, and geographic comparisons 20 per class within the region; each assessment kept the same species across its three bins.
- **Extent.** Unchanged development predictions were rescored within named retained bioregions, and within region-by-fold strata, requiring at least 30 and 20 cells per class respectively. Eligible strata were averaged within species, then species were weighted equally.
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

Pretraining improved development prediction for mainland mammals and birds (Fig. 2). For mainland mammals, fine-tuning gained +0.0087 mean AUC over the target-only network (four of five species) and +0.0040 over conventional models (all five). For birds the gains were +0.0058 (72 of 73) and +0.0034 (67 of 73). The bird increment held when development predictions were scored within bioregions and spatial folds (+0.0072; 68 of 73), and it stayed positive under species resampling. Tasmanian mammals showed no development gain: fine-tuning trailed target-only by 0.0067 and conventional models by 0.0498.

On the primary bird panel, the pretraining increment increased from +0.0058 at full target data to +0.0095 at quarter data; the conventional-model contrast increased from +0.0034 to +0.0069 (Supporting information). Quarter-data training fits still contained a median of about 2,800 presence cells per held fold. The least-recorded third of all 157 targets comprised 53 species with 224–3,649 presence cells. For them, fine-tuning gained +0.0041 over target-only and +0.0006 over conventional models. At full target data on the primary 73 birds, the frozen encoder's mean contrast with target-only rose from −0.0044 with 20 auxiliary species to +0.0022 with the full pool, positive for 57 species. Full fine-tuning's increment peaked at 80 auxiliaries among the tested sizes (+0.0061).

### New regions

In new regions the mean increment from pretraining disappeared (Fig. 2).
- **Mainland mammals transferred to Tasmania.** Fine-tuning trailed target-only by 0.0155 mean AUC. Three of five species benefited, and the median was +0.0269.
- **Birds.** Across the three withheld regions, mean AUC was 0.6827 for fine-tuning and 0.6831 for target-only. The paired difference of −0.0004 was positive for 34 of 73 species. Regional means were +0.0064 in Naracoorte Coastal Plain, −0.0040 in South Eastern Highlands and −0.0035 in NSW North Coast. The species-resampling ranges for both geographic contrasts spanned zero.
- **Tasmania's withheld patches.** The co-primary metrics disagreed. Fine-tuning trailed target-only by 0.0147 mean AUC, positive for one of eight species, and led it by 0.0477 mean TSS, positive for five with one tie.

In new bird regions, the networks' advantage over conventional models did not depend on pretraining (Fig. 3). Target-only and fine-tuned networks exceeded conventional models by mean AUC increments of +0.0032 and +0.0028; fine-tuning's regional contrasts were +0.0078, −0.0071 and +0.0076. Fixed 50:50 averages with conventional predictions gained +0.0096 (target-only; 64 of 73 species) and +0.0104 (fine-tuned; 60 of 73), reaching mean AUC 0.6896 and 0.6903. The two ensembles differed by 0.0007, with the fine-tuned ensemble ahead for 37 species.

### Diagnostics

Absolute bird AUC was 0.83 in development and 0.68 in new regions (Table 1). The unchanged development predictions were also scored more narrowly:
- within named bioregions, they gave 0.691;
- within region-by-fold strata, they gave 0.690, close to the new-region mean of 0.683.

Regional scoring removed 360,625 cells outside the named regions and changed which presence–background pairs entered AUC. The pretraining increment stayed positive under both regional scorings: +0.0110 within bioregions (56 of 73 species) and +0.0072 within strata (68 of 73).

Fine-tuning's mean AUC contrast with conventional models declined across background recording-richness bins, from +0.0050 (10–24 other recorded species) to +0.0019 (25–99) to −0.0039 (100 or more) on the 59-species development panel; its increment over target-only on the same panel followed suit (+0.0075, +0.0039, −0.0043). The prespecified geographic diagnostic showed the same decline in both supported regions, South Eastern Highlands and NSW North Coast (Fig. 4a); Naracoorte Coastal Plain had no species supported in all three bins. High-richness background was rare in new regions, with mean within-species shares of 0.3–2.8%.

In Tasmania, the source of negative evidence changed the ranking of fine-tuning and conventional models (Fig. 4b). Under original training at full target data, fine-tuning trailed conventional models by 0.0051 mean AUC against mixed negatives. It led them by 0.0154 against survey-supported negatives alone. Removing pseudoabsences from training lowered mean AUC against mixed negatives for all three learners; fine-tuning went from 0.839 to 0.766. It raised mean AUC against survey-supported negatives, from 0.835 to 0.857 for fine-tuning. Retraining also changed the maps: across the seven affected species and three learners, top-decile cell retention ranged from 31% to 86%. The eighth species had no target-training pseudoabsences and reproduced all three maps.

## Discussion

The clearest result is that the network's small advantage in new bird regions was available without learning from other species. Fine-tuned and target-only networks both exceeded conventional models there, by 0.0028 and 0.0032 AUC, while the matched pretraining contrast averaged −0.0004. A comparison with conventional models alone would have credited that advantage to shared learning. Basile et al. [-@basile2026] found that the advantage of neural joint models did not persist under transfer. The target-only control identifies how much of a neural advantage comes from sharing.

Pretraining improved development prediction for mainland mammals and birds, and the bird increment grew under subsampling. At full target data and auxiliary-pool size, the bird frozen-encoder control also exceeded target-only learning in mean development AUC. These results agree with the predictive value of shared learning reported for species embeddings, joint models and pretrained representations [@chen2017; @brun2024; @bourel2025; @ovaskainen2025; @lange2025]. In new regions the increment varied among species and regions. Naracoorte Coastal Plain, chosen for environmentally supported transfer, had a positive mean, and 34 of 73 species benefited. The information that helped in development did not add consistent value after geographic transfer.

In the new bird regions, fixed averaging raised mean AUC by about 0.010 over conventional models, compared with about 0.003 for either network alone. Both averages used retained predictions and fixed weights. Ensembles of complementary learners have long been recommended for distribution models [@araujo2007], and their value depends on the components and how they are implemented [@norberg2019; @valavi2022]. Complementary learners therefore deserve comparison alongside larger auxiliary pools.

Pretraining's increment grew as the primary bird panel was subsampled, but those targets kept thousands of presence cells even at a quarter of their data. The least-recorded third gained +0.0041 over target-only and +0.0006 over conventional models. Subsampling a well-recorded species and predicting a poorly recorded species are different data limitations. The second calls for tests built around rare species and the methods designed for them [@breiner2015].

Regional AUC was low even when unchanged development predictions were rescored within bioregions and folds. Restricting scoring removes between-region presence–background comparisons [@lobo2008; @jimenezvalverde2012]. Comparing learners on the same observations makes their relative predictive gains explicit [@yates2018].

The choice of negative evidence changed which model ranked first. In Tasmania, restricting evaluation to survey-supported negatives reversed the mean AUC ranking of fine-tuning and conventional models, with predictions unchanged. Removing training pseudoabsences and refitting changed which cells scored highest. In birds, the neural advantage fell as background became better recorded. Defining the negative class is thus part of specifying both the model and the test [@phillips2009; @warton2013; @fithian2015; @pili2025].

These conclusions have limits:
- They rest on tabular climate and habitat summaries; spatial context and imagery may carry information that transfers better [@deneu2021].
- The bird target-only network inherited an architecture selected for fine-tuning [@cawley2010].
- Larger auxiliary pools added records and species together.
- Shared geography, taxa and auxiliary models make the species and case summaries descriptive.
- Extent rescoring, target-only averaging and survey-only evaluation were post hoc.
- Background cells and camera nondetections are not ecological absences.
- Recording richness combines survey effort, community richness and environment.
- The development and geographic assessments differ in fitted models, environmental composition and recording support, so their absolute AUCs are not a measure of transfer loss.
- The design cannot separate niche structure, recording processes and optimisation effects such as feature distortion [@kumar2022] as causes of the transfer result.

Fresh regional tests should pair matched target-only controls with spatial inputs, observation-aware models and independent surveys [@johnston2021], under rules fixed before outcomes are seen. Any claim that learning across species improves prediction needs that single-species twin, evaluated where its predictions will be used.
