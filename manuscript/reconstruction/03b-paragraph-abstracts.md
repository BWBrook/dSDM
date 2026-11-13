# Step 3b: Paragraph abstracts

**Status:** draft v2, 13 November 2026. Claude wrote v1 (6b52446). Codex reviewed it (`docs/audits/reconstruction-step3b-review-20261113.md`, thread 162, message 3358) and this version adopts its replacement paragraphs and reference placements. Barry reviews at the final draft.

Source: the section abstracts (`03a-section-abstracts.md`, v2, 8c24ef2). Each paragraph carries one message. References in square brackets are signposts. Codex verified the identities of the seven new works from their DOI metadata (`manuscript/references/reconstruction-reference-check-20261113.json`): Basile 2026, Pili 2025, Fithian 2015, He 2016, Hanley & McNeil 1982, Allouche 2006 and Breiner 2015. They go into `refs.yaml` at drafting. Araújo & New 2007 already exists as `araujo2007`.

**Budget.** Ecography allows 5,000 words from the Introduction to the end of the Discussion. The plan has 31 paragraphs. At about 150 words each, that comes to about 4,800 words, split as follows:

| Section | Paragraphs | Words |
|---|---:|---:|
| Introduction | 6 | ~850 |
| Material and methods | 11 | ~1,650 |
| Results | 7 | ~1,150 |
| Discussion | 7 | ~1,150 |

---

## 1. Framework and one-sentence summaries

### Introduction

1. **Need.** Conservation needs predictions where records are sparse, and transferring models from well-sampled areas is the usual way to get them.
2. **Promise.** Species share environmental responses, so a network pretrained on many species could carry information that a target's own records lack.
3. **Gap.** A successful multi-species model does not reveal what sharing contributed; that takes the same network trained on the target alone, tested in regions excluded from development.
4. **Geographic evaluation.** Predicting a new region is a different task from predicting withheld cells, and AUC changes with the extent over which it is computed.
5. **Negative evidence.** Background locations and survey nondetections are different evidence of absence, and models can learn where observers looked.
6. **Aims.** Shared responses give three predictions and one diagnostic question, which we test in three Australian cases.

*Ordering check.* The sequence runs from need to promise, gap, the two evaluation issues and then the test. Paragraphs 4 and 5 prepare the Results on extent and on negative evidence. They come after the gap, so the attribution question stays central. All four points of the section abstract are covered.

### Material and methods

*Study design*
1. **Design.** Three separately specified experiments, synthesised descriptively, test prediction within the development region and in excluded geography.
2. **Data and inputs.** Occurrence records and camera surveys supplied the responses, and grid-cell climate and habitat summaries supplied the inputs.
3. **Tasmanian mammals.** Eight species were assessed by interpolation in five held-out patches, with two negative sources and unknown combinations masked.
4. **Mainland mammals.** Five targets were transferred to Tasmania, changing both geography and observation source.
5. **Birds.** For 157 targets, background was defined by the recording of other species, and 73 targets were assessed in three contrasting bioregions withheld with buffers.

*Learners*
6. **Pretraining.** A residual multilayer perceptron learned shared features from other species. Each target, and the excluded regions, were kept out.
7. **Neural comparisons.** Fine-tuning, a matched target-only network, a frozen encoder and a pooled-community control separate the uses of shared information.
8. **Conventional benchmark.** A conventional model, selected within the development data, sets a practical standard.

*Analyses*
9. **Data experiments.** Learning curves varied target data and auxiliary species, and Tasmania tested changes to training and evaluation negatives.
10. **Metrics and summaries.** AUC was primary, TSS was co-primary in Tasmania, and bird summaries weight regions and then species equally.
11. **Diagnostics and timing.** Richness, extent, averaging and survey-only analyses diagnose the main result. Each is fixed at a stated stage.

*Ordering check.* Design comes first, then the data and each case, the learners, and the analyses. Paragraph 11 states provenance once, as 03a does. All the points of the section abstract are covered, including the five-seed averaging, the development-derived TSS thresholds and the species-composition ranges.

### Results

1. **Development gain.** Pretraining improved development prediction for mainland mammals and birds, but not for Tasmanian mammals.
2. **Borrowing strength.** The bird gain grew as target data were subsampled, and the frozen encoder showed the shared features were useful.
3. **New regions.** The mean gain from pretraining disappeared in new regions; species and regions varied around zero, and in the Tasmanian patches AUC and TSS disagreed.
4. **Network and ensembles.** In new bird regions the network's advantage did not need pretraining, and averaging with conventional predictions gained most.
5. **Extent.** Scoring unchanged development predictions within bioregions also produced low absolute AUC.
6. **Recording richness.** The neural advantage declined as background recording richness rose, in development and in both supported new regions.
7. **Tasmanian negatives.** Changing the evaluation negatives reversed the ranking, and removing training pseudoabsences changed scores and maps.

*Ordering check.* The order follows the three predictions (paragraphs 1–3), then what helps in new regions (4), then the diagnostics (5–7). It matches Figures 2, 3 and 4. The disagreement between AUC and TSS in Tasmania sits with the transfer results, because the patches are that case's geographic test. The note on what each metric measures moves to M10. All the results in the section abstract are covered.

### Discussion

1. **Principal finding.** The network's small advantage in new bird regions was available without learning from other species; the matched pretraining contrast averaged −0.0004.
2. **Shared information.** Shared information improved development prediction, but its value in new regions varied among species and regions.
3. **Practical route.** Fixed averaging gave the larger mean gain in new bird regions and warrants comparison alongside larger auxiliary pools.
4. **Subsampling versus rarity.** Subsampling well-recorded species is a different data limitation from natural rarity.
5. **Absolute AUC.** Absolute AUC is a poor guide to loss under transfer, so learners should be compared on the same observations.
6. **Negative evidence.** Negative evidence defines the prediction problem: evaluation choices change rankings, and training choices change maps.
7. **Limitations and next tests.** One paragraph gathers the limits and turns them into the next tests.

*Ordering check.* The order runs from the main finding to its context, the practical consequence, the three implications (4–6), and then the limits and next tests. The section abstract's last two paragraphs are merged into paragraph 7, which saves words without losing either message. If the merged paragraph runs over 200 words, it splits back into two. All the material in the section abstract is covered.

---

## 2. Paragraph abstracts

### Introduction

**I1. Need.** Conservation decisions need predictions where species records are sparse. Distribution models fill such gaps by transferring relationships from well-sampled areas. Transfer succeeds only when those relationships hold in the new setting, and that is often untested. [Yates et al. 2018; Wenger & Olden 2012]

**I2. Promise.** Species share environmental responses, so records of one species can inform predictions for another. Multi-species pretraining learns from other species before adapting to a target. Shared learning has improved ecological prediction through several modelling approaches. In a European continental-to-regional comparison, neural joint models' development advantage did not persist under transfer. [Chen et al. 2017; Norberg et al. 2019; Brun et al. 2024; Ovaskainen et al. 2025; Basile et al. 2026]

**I3. Gap.** A successful multi-species model does not reveal what sharing contributed. Comparing pretrained and target-only networks with the same architecture measures the increment from pretraining. Comparing either network with a conventional model assesses its practical advantage. We combine established controls with target-excluded pretraining and whole-region exclusion to assess that increment in new regions. [Chen et al. 2017; Bourel et al. 2025]

**I4. Geographic evaluation.** Predicting a new region is a different task from predicting withheld cells inside a sampled domain. Spatial cross-validation should match the intended use. AUC depends on the extent of the presence–negative comparisons, so absolute AUC can fall with no change in predictions. [Wenger & Olden 2012; Roberts et al. 2017; Lobo et al. 2008; Jiménez-Valverde 2012; Pili et al. 2025]

**I5. Negative evidence.** Most occurrence data record where a species was found, not where it was absent. Models fitted against background locations learn recording patterns alongside habitat. Species that share recorders share these patterns, so pretraining could transfer information about observers as well as niches. Survey nondetections offer a different, and sparser, negative class. [Phillips et al. 2009; Warton et al. 2013; Fithian et al. 2015; Johnston et al. 2021]

**I6. Aims.** Shared environmental responses motivate three predictions:
- pretraining improves development prediction;
- its gain grows as target records shrink;
- the gain persists in new regions.

Development results raised a diagnostic question: do rankings depend on the evidence used for absence? We test the predictions in Tasmanian mammals, mainland mammals transferred to Tasmania, and 73 birds in three withheld bioregions. [no citations]

### Material and methods

**M1. Design.** We synthesise three separately specified experiments (Table 1; Fig. 1). They share some taxa, observation sources and Tasmanian geography, so the cross-case summaries are descriptive. Development assessment used spatial folds within the training domain. Geographic assessment withheld five Tasmanian patches, all of Tasmania, or three buffered bird regions. [Roberts et al. 2017]

**M2. Data and inputs.** Responses came from Atlas of Living Australia occurrence records (2001–2025) and Tasmanian camera surveys. Inputs summarised grid-cell climate, terrain, vegetation, soil and land use. Scaling and encoding were fitted on training partitions. Predictor definitions, available source metadata and provenance gaps are documented in Supporting information. [Belbin et al. 2021; Fick & Hijmans 2017]

**M3. Tasmanian mammals.** Eight species were modelled on a 0.01° grid. Responses comprised presences and two negative sources: camera-supported nondetections and constructed pseudoabsences. Unknown species–cell combinations were masked and excluded from the response loss and evaluation. Five patches fixed before modelling touched the training areas and assessed interpolation. [Supporting information]

**M4. Mainland mammals.** Each of five targets was pretrained with 19 auxiliary mammals on the mainland. The primary assessment used camera-supported records in Tasmania, which supplied no training data or transformations. The transfer therefore changed observation source as well as geography. [no citations]

**M5. Birds.** Records of 505 taxa identified sampled cells. Background cells had no focal record and at least ten other recorded species. Of 157 targets, 73 were assessed in three bioregions, chosen before outcomes as contrasting settings:
- Naracoorte Coastal Plain, environmentally supported;
- South Eastern Highlands, an environmental edge;
- NSW North Coast, a fragmented land-use mosaic.

All three regions and their 50 km buffers were excluded together. [Phillips et al. 2009]

**M6. Pretraining.** A residual multilayer perceptron learned a shared encoder, with a separate head for each auxiliary species. Each target was excluded from pretraining. In birds its whole computational block of targets was excluded too. The geographic exclusions applied to pretraining as well as to fitting. [He et al. 2016, for the residual-learning principle only]

**M7. Neural comparisons.** Fine-tuning updated the encoder and fitted a new target head. The target-only network used the same architecture, data, optimisation and evaluation, starting from random weights. Frozen-encoder and pooled-community controls tested simpler uses of shared information. The bird architecture, selected for fine-tuning, was inherited by the target-only network, and predictions averaged five matched seeds. [Kumar et al. 2022; Cawley & Talbot 2010]

**M8. Conventional benchmark.** The candidates were elastic net, random forest, gradient boosting, a shallow network and an intercept model. Hyperparameters and family were selected within the development data and then fixed. No outer response chose a model, an epoch, a weight or a threshold. [Valavi et al. 2022; Norberg et al. 2019]

**M9. Data experiments.** Bird learning curves crossed 25%, 50% and 100% target data in the primary 73-species panel with 20, 80 or all eligible auxiliary species. Original Tasmania used nested target-data ladders at those fractions. Corrected mainland comparisons used full target data. Tasmania separately tested removing training pseudoabsences and filtering evaluation negatives. [Supporting information]

**M10. Metrics and summaries.** AUC was primary; TSS was co-primary in Tasmania using thresholds fixed from development predictions. Bird geographic summaries averaged regions within species and then species equally; development summaries averaged folds. Species-composition resampling supplied descriptive ranges. AUC assesses ranking, whereas TSS assesses classification at a fixed threshold. [Hanley & McNeil 1982; Allouche et al. 2006; Supporting information]

**M11. Diagnostics and timing.** Primary comparisons and curves were fixed before the withheld responses were opened. The richness diagnostic was fixed after development and before opening. Fine-tuned/conventional averaging was prespecified as exploratory. Extent rescoring, target-only averaging and survey-only evaluation were post hoc, and the removal of training negatives was implemented after the primary outcomes. [Lobo et al. 2008]

### Results

**R1. Development gain.** Pretraining improved development AUC for mainland mammals (+0.009; four of five species) and birds (+0.006; 72 of 73). Scored within bioregions and spatial folds, the bird gain stayed positive (+0.007; 68 of 73). Tasmanian mammals showed a negative development mean (−0.007). [Fig. 2]

**R2. Borrowing strength.** Subsampling bird target data from full to half to quarter increased the matched pretraining increment from +0.0058 through +0.0075 to +0.0095. The least-recorded third of all 157 bird targets gained +0.004 over target-only and +0.0006 over conventional models. At full target data and auxiliary size, the frozen encoder gained +0.0022 over target-only on the primary panel, with 57 of 73 species benefiting. [Supporting information]

**R3. New regions.** In new regions the mean pretraining increment was −0.016 for mainland mammals and −0.0004 for birds, with 34 of 73 bird species benefiting. Bird regional means were +0.006 in Naracoorte Coastal Plain and −0.004 in both South Eastern Highlands and NSW North Coast. In Tasmania's held-out patches, pretraining lowered AUC by 0.015 and raised TSS by 0.048. [Fig. 2; Table 1]

**R4. Networks and ensembles.** Relative to conventional models, mean AUC increments in new bird regions were +0.0032 for target-only and +0.0028 for fine-tuning. Their fixed 50:50 ensembles with conventional predictions gained +0.0096 and +0.0104, positive for 64 and 60 of 73 species, respectively. Both ensemble means exceeded both neural means. [Fig. 3]

**R5. Extent.** Mean AUC was 0.83 in development and 0.68 in new regions. Scoring unchanged development predictions within bioregions and spatial folds gave 0.69. Regional scoring therefore also produced low absolute AUC within the development data. [Table 1; Supporting information]

**R6. Recording richness.** The fine-tuned-minus-conventional contrast declined across background recording-richness bins. In development it went from +0.005 to +0.002 to −0.004, for 10–24, 25–99 and at least 100 other recorded species (59 species). It also declined in South Eastern Highlands (38 species) and NSW North Coast (55); Naracoorte Coastal Plain had no common support. [Fig. 4a]

**R7. Tasmanian negatives.** At full target data with training unchanged, survey-only evaluation reversed the fine-tuned-minus-conventional mean AUC contrast from −0.005 to +0.015. Removing training pseudoabsences lowered mean AUC against mixed negatives and raised it against survey-supported negatives. Retraining also changed the highest-scoring cells for all seven affected species. [Fig. 4b; Supporting information]

### Discussion

**D1. Principal finding.** In new bird regions, the small average neural advantage was available without pretraining. A comparison against conventional models alone could credit that advantage to shared learning. The matched pretraining contrast averaged −0.0004 AUC across the three regions. [Basile et al. 2026, for the comparison with previous transfer evidence]

**D2. Shared information.** Development gains and the frozen-encoder result show that shared information improved prediction in the tested setting. In new regions, its increment varied among species and regions, including a positive mean in Naracoorte Coastal Plain. These results distinguish useful development information from its additional predictive value after geographic transfer. [Chen et al. 2017; Brun et al. 2024; Bourel et al. 2025; Ovaskainen et al. 2025; Lange et al. 2025; Basile et al. 2026]

**D3. Practical route.** Fixed averaging produced the larger mean AUC gain in new bird regions with either neural model. Both averages used retained predictions and fixed weights. Complementary learners therefore deserve comparison alongside larger auxiliary pools. [Norberg et al. 2019; Valavi et al. 2022; Araújo & New 2007]

**D4. Subsampling versus rarity.** Subsampling well-recorded species and predicting naturally poorly recorded species are different data limitations. Pretraining's increment grew under subsampling. The least-recorded species gained little over conventional models. Tests built around rare species are needed. [Ovaskainen et al. 2025; Breiner et al. 2015, for rare-species modelling only]

**D5. Absolute AUC.** Development predictions scored within bioregions and folds had an AUC of 0.69, close to the new-region mean of 0.68. Low regional AUC can therefore occur without transferring a fitted model. Comparing learners on the same observations makes their relative predictive gains explicit. [Lobo et al. 2008; Jiménez-Valverde 2012; Yates et al. 2018]

**D6. Negative evidence.** Changing evaluation negatives reversed the fine-tuned-versus-conventional mean AUC ranking in Tasmania. Removing training pseudoabsences and refitting changed prediction maps. Negative evidence is therefore part of specifying both model fitting and the problem against which predictions are assessed. [Phillips et al. 2009; Warton et al. 2013; Fithian et al. 2015; Pili et al. 2025; Johnston et al. 2021]

**D7. Limitations and next tests.** The tests used tabular inputs and, in birds, an architecture selected for fine-tuning. Auxiliary pools changed records and species together; shared geography and models make the summaries descriptive. Several diagnostics were post hoc, while negative observations neither establish ecological absence nor identify the mechanism behind a model contrast. Fresh regional tests should pair matched target-only controls with spatial inputs, observation-aware models and independent surveys. [Deneu et al. 2021; Cawley & Talbot 2010; Kumar et al. 2022; Johnston et al. 2021]

---

## 3. Decisions from the v1 review

- **R5 and D5** say that rescoring unchanged development predictions within regions also produces low absolute AUC. They attribute no share of the transfer decline to the scoring extent, because no decomposition was estimated.
- **M3:** masked unknowns are excluded from the analysis. They are not a negative class, and the two negative sources are camera nondetections and constructed pseudoabsences.
- **D1** states the matched contrast (−0.0004), not "nothing".
- **D7 stays merged,** at about 170–190 words in the full draft.
- **Citation scopes:**
  - Pili sits with sampling and evaluation (I4, D6), not the attribution gap.
  - Breiner supports rare-species modelling only.
  - He supports the residual-learning principle only.
  - Basile is a transfer precedent with no matched target-only control, and its results are not converted into an AUC drop.
- **Word budgets:** the section allocations, not a uniform 150 words per paragraph.
