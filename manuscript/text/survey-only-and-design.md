## Supplementary methods S3. Post hoc survey-only evaluation

This post hoc analysis tests how the Tasmanian comparison depends on the
source of its negative observations. It reuses completed model predictions for
all eight species, seven target-data endpoints (25% L0–L2, 50% L0–L2 and
100%/full), and three methods: the target-only residual MLP, full multi-head
fine-tuning and the originally selected conventional learner.
The two training regimes are the original primary regime and the accepted
pseudoabsence-filtered sensitivity regime. Each was compared on both the
original mixed evaluation panel and the survey-only panel.

The original Tasmanian response construction resolved 2001--2025 records to a
0.01-degree grid for *Thylogale billardierii*, *Notamacropus rufogriseus*,
*Trichosurus vulpecula*, *Pseudocheirus peregrinus*, *Vombatus ursinus*,
*Sarcophilus harrisii*, *Dasyurus maculatus* and *Dasyurus viverrinus*. It used
28 raw predictors represented by 77 encoded columns. The accepted neural
architecture was three residual blocks of width 128 with bottleneck width 64.
The sensitivity retained the original predictor support, architecture and
model selections, following the pre-outer capacity and climate-reduction checks.

The survey-only panel retains the 1,300 held presence rows and the 242
`survey_supported_absence` rows. It excludes the 130 protocol-defined
`pseudoabsence` rows from evaluation, leaving 1,542 rows; the original mixed
panel retains all 1,672 held rows. A survey-supported negative is a cell with
the accepted observation-effort support and no focal record in that source. It
is not a verified ecological absence, an occupancy zero, or a population-wide
negative. Only the negative class is filtered by source; all held presences
are retained irrespective of source. This conditioning does not identify a
recording mechanism or causal effect.

No model was refitted or selected for the survey-only evaluation. Thresholds
were retained from each training regime's development predictions. ROC AUC is the ranking metric; TSS and
Matthews correlation (MCC) use the corresponding frozen threshold. Values are
equal-species means within each endpoint. The seven endpoints are nested
descriptive panels, not independent ecological replicates. No inferential
intervals, hypothesis tests or population extrapolation are reported.

\newpage

### Table S10a. Post hoc survey-only ROC AUC across evaluation panels and training regimes

Each cell is the equal-species mean ROC AUC for the named training regime and evaluation panel. Every row contains eight species. Original training includes constructed target pseudoabsences; filtered training removes them.

| Evaluation panel | Training regime | Endpoint | Target-only | Fine-tuned | Conventional |
| --- | --- | --- | ---: | ---: | ---: |
| Mixed | Original | 25% / L0 | 0.8110 | 0.8120 | 0.7934 |
| Mixed | Filtered | 25% / L0 | 0.7680 | 0.7597 | 0.7561 |
| Mixed | Original | 25% / L1 | 0.8431 | 0.8322 | 0.8154 |
| Mixed | Filtered | 25% / L1 | 0.7590 | 0.7663 | 0.7645 |
| Mixed | Original | 25% / L2 | 0.8054 | 0.7976 | 0.8078 |
| Mixed | Filtered | 25% / L2 | 0.7596 | 0.7391 | 0.7705 |
| Mixed | Original | 50% / L0 | 0.8257 | 0.8384 | 0.8239 |
| Mixed | Filtered | 50% / L0 | 0.7780 | 0.7612 | 0.7756 |
| Mixed | Original | 50% / L1 | 0.8468 | 0.8403 | 0.8369 |
| Mixed | Filtered | 50% / L1 | 0.7908 | 0.7675 | 0.7792 |
| Mixed | Original | 50% / L2 | 0.8305 | 0.8226 | 0.8231 |
| Mixed | Filtered | 50% / L2 | 0.7631 | 0.7512 | 0.7529 |
| Mixed | Original | 100% / full | 0.8537 | 0.8390 | 0.8441 |
| Mixed | Filtered | 100% / full | 0.7704 | 0.7657 | 0.7728 |
| Survey-only | Original | 25% / L0 | 0.8093 | 0.8062 | 0.7566 |
| Survey-only | Filtered | 25% / L0 | 0.8174 | 0.8351 | 0.7903 |
| Survey-only | Original | 25% / L1 | 0.8218 | 0.8232 | 0.7838 |
| Survey-only | Filtered | 25% / L1 | 0.8178 | 0.8330 | 0.8025 |
| Survey-only | Original | 25% / L2 | 0.7779 | 0.7875 | 0.7672 |
| Survey-only | Filtered | 25% / L2 | 0.8158 | 0.8330 | 0.8003 |
| Survey-only | Original | 50% / L0 | 0.8069 | 0.8311 | 0.7915 |
| Survey-only | Filtered | 50% / L0 | 0.8422 | 0.8458 | 0.8155 |
| Survey-only | Original | 50% / L1 | 0.8303 | 0.8278 | 0.8112 |
| Survey-only | Filtered | 50% / L1 | 0.8369 | 0.8478 | 0.8310 |
| Survey-only | Original | 50% / L2 | 0.8158 | 0.8167 | 0.8024 |
| Survey-only | Filtered | 50% / L2 | 0.8418 | 0.8523 | 0.8228 |
| Survey-only | Original | 100% / full | 0.8403 | 0.8352 | 0.8198 |
| Survey-only | Filtered | 100% / full | 0.8587 | 0.8572 | 0.8385 |
\newpage

### Table S10b. Post hoc survey-only true skill statistic across evaluation panels and training regimes

Each cell is the equal-species mean true skill statistic for the named training regime and evaluation panel. Every row contains eight species. The two regimes are the original primary fit and the pseudoabsence-filtered sensitivity fit.

| Evaluation panel | Training regime | Endpoint | Target-only | Fine-tuned | Conventional |
| --- | --- | --- | ---: | ---: | ---: |
| Mixed | Original | 25% / L0 | 0.5035 | 0.4926 | 0.4198 |
| Mixed | Filtered | 25% / L0 | 0.4163 | 0.3767 | 0.3719 |
| Mixed | Original | 25% / L1 | 0.4747 | 0.4543 | 0.4936 |
| Mixed | Filtered | 25% / L1 | 0.3991 | 0.3707 | 0.4384 |
| Mixed | Original | 25% / L2 | 0.4525 | 0.5257 | 0.4922 |
| Mixed | Filtered | 25% / L2 | 0.4754 | 0.4447 | 0.4339 |
| Mixed | Original | 50% / L0 | 0.4642 | 0.5203 | 0.5136 |
| Mixed | Filtered | 50% / L0 | 0.4010 | 0.3977 | 0.4163 |
| Mixed | Original | 50% / L1 | 0.5450 | 0.5587 | 0.5298 |
| Mixed | Filtered | 50% / L1 | 0.4418 | 0.4121 | 0.4341 |
| Mixed | Original | 50% / L2 | 0.5220 | 0.4937 | 0.5409 |
| Mixed | Filtered | 50% / L2 | 0.4416 | 0.4406 | 0.4158 |
| Mixed | Original | 100% / full | 0.5099 | 0.5575 | 0.5316 |
| Mixed | Filtered | 100% / full | 0.4657 | 0.4475 | 0.4082 |
| Survey-only | Original | 25% / L0 | 0.5040 | 0.4927 | 0.3723 |
| Survey-only | Filtered | 25% / L0 | 0.4908 | 0.4945 | 0.4075 |
| Survey-only | Original | 25% / L1 | 0.4211 | 0.4448 | 0.4686 |
| Survey-only | Filtered | 25% / L1 | 0.4793 | 0.4912 | 0.4975 |
| Survey-only | Original | 25% / L2 | 0.4182 | 0.5247 | 0.4547 |
| Survey-only | Filtered | 25% / L2 | 0.4919 | 0.5473 | 0.5221 |
| Survey-only | Original | 50% / L0 | 0.4246 | 0.4876 | 0.4288 |
| Survey-only | Filtered | 50% / L0 | 0.4787 | 0.5218 | 0.4685 |
| Survey-only | Original | 50% / L1 | 0.5122 | 0.5484 | 0.4672 |
| Survey-only | Filtered | 50% / L1 | 0.5122 | 0.4899 | 0.5349 |
| Survey-only | Original | 50% / L2 | 0.5258 | 0.5001 | 0.4679 |
| Survey-only | Filtered | 50% / L2 | 0.5501 | 0.5853 | 0.5052 |
| Survey-only | Original | 100% / full | 0.5018 | 0.5568 | 0.4628 |
| Survey-only | Filtered | 100% / full | 0.5969 | 0.6066 | 0.5045 |
\newpage

### Table S10c. Post hoc survey-only Matthews correlation across evaluation panels and training regimes

Each cell is the equal-species mean Matthews correlation for the named training regime and evaluation panel. Every row contains eight species. The two regimes are the original primary fit and the pseudoabsence-filtered sensitivity fit.

| Evaluation panel | Training regime | Endpoint | Target-only | Fine-tuned | Conventional |
| --- | --- | --- | ---: | ---: | ---: |
| Mixed | Original | 25% / L0 | 0.4030 | 0.3859 | 0.3440 |
| Mixed | Filtered | 25% / L0 | 0.3395 | 0.2920 | 0.2956 |
| Mixed | Original | 25% / L1 | 0.3856 | 0.3679 | 0.4050 |
| Mixed | Filtered | 25% / L1 | 0.3079 | 0.3138 | 0.3466 |
| Mixed | Original | 25% / L2 | 0.3804 | 0.4365 | 0.4116 |
| Mixed | Filtered | 25% / L2 | 0.3783 | 0.3651 | 0.3635 |
| Mixed | Original | 50% / L0 | 0.3508 | 0.4000 | 0.4178 |
| Mixed | Filtered | 50% / L0 | 0.3150 | 0.3056 | 0.3204 |
| Mixed | Original | 50% / L1 | 0.4389 | 0.4404 | 0.4274 |
| Mixed | Filtered | 50% / L1 | 0.3585 | 0.3319 | 0.3297 |
| Mixed | Original | 50% / L2 | 0.4005 | 0.4065 | 0.4344 |
| Mixed | Filtered | 50% / L2 | 0.3388 | 0.3447 | 0.3277 |
| Mixed | Original | 100% / full | 0.4050 | 0.4340 | 0.4149 |
| Mixed | Filtered | 100% / full | 0.3697 | 0.3593 | 0.3066 |
| Survey-only | Original | 25% / L0 | 0.3780 | 0.3606 | 0.2936 |
| Survey-only | Filtered | 25% / L0 | 0.3808 | 0.3595 | 0.3144 |
| Survey-only | Original | 25% / L1 | 0.3273 | 0.3279 | 0.3484 |
| Survey-only | Filtered | 25% / L1 | 0.3485 | 0.3853 | 0.3606 |
| Survey-only | Original | 25% / L2 | 0.3334 | 0.4026 | 0.3536 |
| Survey-only | Filtered | 25% / L2 | 0.3824 | 0.4188 | 0.4008 |
| Survey-only | Original | 50% / L0 | 0.2963 | 0.3486 | 0.3319 |
| Survey-only | Filtered | 50% / L0 | 0.3475 | 0.3723 | 0.3463 |
| Survey-only | Original | 50% / L1 | 0.3898 | 0.4007 | 0.3534 |
| Survey-only | Filtered | 50% / L1 | 0.3893 | 0.3849 | 0.3768 |
| Survey-only | Original | 50% / L2 | 0.3750 | 0.3785 | 0.3562 |
| Survey-only | Filtered | 50% / L2 | 0.3974 | 0.4340 | 0.3693 |
| Survey-only | Original | 100% / full | 0.3737 | 0.4034 | 0.3359 |
| Survey-only | Filtered | 100% / full | 0.4440 | 0.4585 | 0.3548 |
\newpage

### Table S11. Per-species full-data survey-only contrasts

Values are primary → pseudoabsence-filtered sensitivity fine-tuning minus the named comparator, using the survey-only evaluation panel at the 100%/full endpoint. Negative counts are retained survey-supported negative rows for that species; all 1,300 held presences are retained. The seven-negative support for *Vombatus ursinus* is shown explicitly. These paired contrasts are descriptive and do not establish true absence, occupancy or causal mechanism.

| Species | Negative n | Fine-tuning − target-only AUC | Fine-tuning − target-only TSS | Fine-tuning − conventional AUC | Fine-tuning − conventional TSS |
|--------------------|-----------:|-----------------:|-----------------:|-----------------:|-----------------:|
| *Dasyurus maculatus* | 21 | +0.0353 → +0.0197 | +0.0082 → +0.0431 | -0.0279 → +0.0538 | +0.0571 → +0.3030 |
| *Dasyurus viverrinus* | 69 | -0.0054 → -0.0080 | -0.0458 → -0.0323 | -0.0080 → +0.0041 | -0.0748 → -0.0580 |
| *Notamacropus rufogriseus* | 17 | -0.0411 → -0.0380 | +0.0000 → +0.0049 | +0.0380 → +0.0481 | +0.1133 → +0.0887 |
| *Pseudocheirus peregrinus* | 73 | -0.0431 → -0.0339 | +0.0165 → +0.0137 | -0.0454 → -0.0152 | -0.0778 → +0.0252 |
| *Sarcophilus harrisii* | 9 | +0.0003 → +0.0251 | +0.3095 → -0.0186 | +0.1317 → +0.0858 | +0.2732 → +0.0560 |
| *Thylogale billardierii* | 19 | -0.0003 → -0.0003 | +0.0303 → +0.0303 | -0.0003 → -0.0003 | +0.2172 → +0.2172 |
| *Trichosurus vulpecula* | 27 | -0.0031 → +0.0089 | +0.1377 → +0.0778 | -0.0456 → -0.0503 | +0.0060 → +0.0180 |
| *Vombatus ursinus* | 7 | +0.0167 → +0.0143 | -0.0167 → -0.0417 | +0.0810 → +0.0238 | +0.2381 → +0.1667 |
### Public source and deterministic check

These tables use the accepted public aggregates in evidence/tasmania_pseudoabsence/20261011/survey-only/. Exact source hashes, receipt digests, support counts and the deterministic checker are recorded in evidence/cross_case_synthesis/20261018/survey-only-reporting.json. The recorded check reads only accepted aggregate CSV/JSON files; it does not read responses, coordinates, memberships or predictions.

\newpage

## Table S12. Full-data Tasmania training-by-evaluation comparison

Mean withheld-patch performance across eight Tasmanian mammals at full target data. Original training includes constructed target pseudoabsences; filtered training removes them. Mixed evaluation contains 1,300 presences, 242 survey-supported negatives and 130 pseudoabsences. Survey-only evaluation retains the same presences and only survey-supported negatives. Each method's threshold is fixed from its own training regime. Evaluation panels reuse predictions; the survey-only analysis was post hoc. All-endpoint values and per-species survey-only contrasts appear in Tables S10–S11. These two panels retain the former main-text Table 2, including the co-primary Tasmania TSS result.

### Table S12a. ROC AUC

| Training | Evaluation negatives | FT | Target-only | Conventional |
|---|---|---:|---:|---:|
| Original | Mixed | 0.8390 | 0.8537 | 0.8441 |
| Filtered | Mixed | 0.7657 | 0.7704 | 0.7728 |
| Original | Survey only | 0.8352 | 0.8403 | 0.8198 |
| Filtered | Survey only | 0.8572 | 0.8587 | 0.8385 |

### Table S12b. True skill statistic

| Training | Evaluation negatives | FT | Target-only | Conventional |
|---|---|---:|---:|---:|
| Original | Mixed | 0.5575 | 0.5099 | 0.5316 |
| Filtered | Mixed | 0.4475 | 0.4657 | 0.4082 |
| Original | Survey only | 0.5568 | 0.5018 | 0.4628 |
| Filtered | Survey only | 0.6066 | 0.5969 | 0.5045 |

\newpage

## Table S13. Bird learning curves and shared-information controls

### Table S13a. The five executed endpoints

All rows use the same 73 primary species and mean-fold development AUC. Target data were varied only at the full auxiliary pool; auxiliary-pool size was varied only at full target data. These are five endpoints, not a full factorial. Each contrast first pairs learners within species, then weights species equally. The frozen-encoder control fits a new target head while keeping its pretrained encoder fixed.

| Target data | Auxiliary species | Fine-tuned − target-only | Fine-tuned − conventional | Frozen − target-only |
| --- | --- | --- | --- | --- |
| 25% | full | +0.0095 | +0.0069 | +0.0086 |
| 50% | full | +0.0075 | +0.0053 | +0.0050 |
| 100% | 20 | +0.0046 | +0.0023 | -0.0044 |
| 100% | 80 | +0.0061 | +0.0037 | +0.0016 |
| 100% | full | +0.0058 | +0.0034 | +0.0022 |

Quarter-data training/replay fits still contained a median of about 2,800 presence cells per held fold. The full-panel minimum-recorded tertile contained 53 of the 157 targets, with 224–3,649 retained presence cells. Their full-data fine-tuned-minus-conventional mean was +0.0006 AUC. Subsampling the primary panel and predicting a poorly recorded species therefore address different data limitations.

### Table S13b. Full-data bird controls

The development column uses the primary 73 species, with folds averaged within species. The new-region column averages NCP, SEH and NNC within each of the same species. Community-score controls add a target-excluded pooled-community prediction as a scalar covariate. They do not transfer a shared encoder; neither that score nor recording richness is a measured ecological absence probability.

| Learner | Development AUC | New-region AUC |
| --- | --- | --- |
| Target-only | 0.8258 | 0.6831 |
| Target-only + community score | 0.8258 | 0.6828 |
| Frozen encoder | 0.8280 | 0.6814 |
| Fine-tuned encoder | 0.8316 | 0.6827 |
| Conventional | 0.8282 | 0.6800 |
| Conventional + community score | 0.8286 | 0.6807 |

\newpage

## Table S14. Absolute bird AUC under every scoring extent

The same 73 species contribute to each row. The first four rows reuse unchanged development predictions, changing only the observations, presence–background pairs and aggregation. Regional scoring omits 360,625 domain-complement cells. Within-region and within-region-and-fold summaries average eligible strata within species before weighting species equally. The last row uses the separately fitted geographic predictions and averages the three withheld regions within species. Comparisons of absolute scores across these rows do not isolate a geographic penalty.

| Scoring extent | Fine-tuned | Target-only | Conventional |
| --- | --- | --- | --- |
| Development: mean of folds | 0.8316 | 0.8258 | 0.8282 |
| Development: pooled domain | 0.8327 | 0.8266 | 0.8296 |
| Development: within bioregions | 0.6911 | 0.6802 | 0.6874 |
| Development: within bioregions and folds | 0.6897 | 0.6825 | 0.6838 |
| New regions: mean of three regions | 0.6827 | 0.6831 | 0.6800 |

\newpage

## Table S15. Per-species bird contrasts

Each of the primary 73 species contributes one paired AUC contrast per setting. FT = fine-tuned network; TO = target-only network; C = selected conventional model. Development first averages spatial folds, and new-region assessment first averages NCP, SEH and NNC within species. Thus every species, including those with negative or near-zero contrasts, remains visible. Absolute mean performance by region appears in main Table 1; region-specific contrast summaries remain in the accepted outer aggregate report.

| Species | Development FT − TO | New-region FT − TO | Development FT − C | New-region FT − C |
| --- | --- | --- | --- | --- |
| *Acanthagenys rufogularis* | +0.0083 | +0.0087 | +0.0042 | +0.0143 |
| *Acanthiza chrysorrhoa* | +0.0126 | -0.0006 | +0.0039 | +0.0017 |
| *Acanthiza lineata* | +0.0056 | -0.0102 | +0.0038 | +0.0004 |
| *Acanthiza nana* | +0.0070 | +0.0579 | -0.0019 | +0.0206 |
| *Acanthiza pusilla* | +0.0054 | +0.0076 | +0.0019 | +0.0083 |
| *Acanthiza reguloides* | +0.0097 | +0.0011 | +0.0045 | +0.0011 |
| *Acanthorhynchus tenuirostris* | +0.0046 | -0.0069 | +0.0051 | -0.0031 |
| *Acrocephalus australis* | +0.0224 | +0.0115 | +0.0072 | +0.0200 |
| *Anthochaera chrysoptera* | +0.0034 | -0.0061 | +0.0043 | -0.0015 |
| *Artamus cyanopterus* | +0.0064 | -0.0080 | +0.0074 | -0.0150 |
| *Cacatua galerita* | +0.0060 | +0.0058 | +0.0031 | +0.0249 |
| *Cacatua sanguinea* | +0.0094 | -0.0095 | +0.0068 | -0.0084 |
| *Cacatua tenuirostris* | +0.0038 | +0.0089 | +0.0069 | +0.0305 |
| *Cacomantis flabelliformis* | +0.0035 | -0.0020 | +0.0039 | -0.0001 |
| *Caligavis chrysops* | +0.0036 | +0.0046 | +0.0040 | +0.0139 |
| *Ceyx azureus* | +0.0046 | -0.0226 | +0.0045 | -0.0077 |
| *Chalcites basalis* | +0.0090 | -0.0011 | +0.0032 | -0.0135 |
| *Chalcites lucidus* | +0.0033 | -0.0223 | +0.0029 | -0.0107 |
| *Cincloramphus mathewsi* | +0.0064 | -0.0004 | +0.0041 | -0.0077 |
| *Climacteris picumnus* | +0.0072 | +0.0013 | +0.0024 | +0.0177 |
| *Colluricincla harmonica* | +0.0054 | -0.0147 | +0.0024 | -0.0128 |
| *Coracina novaehollandiae* | +0.0085 | -0.0153 | +0.0054 | -0.0189 |
| *Coracina papuensis* | +0.0070 | -0.0349 | +0.0074 | -0.0557 |
| *Corcorax melanorhamphos* | +0.0033 | -0.0063 | -0.0013 | -0.0262 |
| *Cormobates leucophaea* | +0.0046 | +0.0198 | +0.0041 | +0.0177 |
| *Corvus coronoides* | +0.0029 | +0.0208 | -0.0003 | -0.0129 |
| *Corvus tasmanicus* | -0.0004 | +0.0137 | +0.0004 | +0.0018 |
| *Cracticus torquatus* | +0.0093 | +0.0300 | +0.0038 | +0.0433 |
| *Dacelo novaeguineae* | +0.0050 | +0.0084 | +0.0025 | -0.0092 |
| *Daphoenositta chrysoptera* | +0.0069 | +0.0209 | +0.0065 | +0.0111 |
| *Dicaeum hirundinaceum* | +0.0079 | +0.0033 | +0.0031 | -0.0077 |
| *Entomyzon cyanotis* | +0.0012 | -0.0417 | +0.0017 | -0.0192 |
| *Eolophus roseicapilla* | +0.0060 | -0.0114 | +0.0016 | -0.0022 |
| *Eopsaltria australis* | +0.0030 | +0.0297 | +0.0017 | +0.0423 |
| *Falcunculus frontatus* | +0.0103 | -0.0005 | +0.0079 | -0.0129 |
| *Geopelia placida* | +0.0075 | -0.0053 | +0.0032 | +0.0045 |
| *Heteroscenes pallidus* | +0.0095 | +0.0026 | +0.0083 | +0.0250 |
| *Malurus cyaneus* | +0.0055 | -0.0048 | +0.0027 | +0.0291 |
| *Malurus lamberti* | +0.0058 | -0.0118 | +0.0013 | +0.0266 |
| *Manorina melanocephala* | +0.0058 | -0.0145 | -0.0001 | -0.0264 |
| *Melithreptus gularis* | +0.0148 | -0.0266 | +0.0043 | -0.0068 |
| *Melithreptus lunatus* | +0.0039 | +0.0058 | +0.0028 | +0.0100 |
| *Microeca fascinans* | +0.0057 | +0.0150 | +0.0009 | +0.0133 |
| *Myiagra inquieta* | +0.0066 | -0.0079 | +0.0001 | -0.0156 |
| *Neochmia temporalis* | +0.0048 | +0.0003 | +0.0056 | +0.0372 |
| *Nesoptilotis leucotis* | +0.0064 | -0.0056 | +0.0042 | -0.0120 |
| *Ocyphaps lophotes* | +0.0035 | -0.0030 | +0.0023 | +0.0070 |
| *Oriolus sagittatus* | +0.0032 | -0.0267 | +0.0022 | -0.0258 |
| *Pachycephala pectoralis* | +0.0047 | +0.0117 | +0.0037 | +0.0185 |
| *Pachycephala rufiventris* | +0.0044 | -0.0205 | +0.0022 | -0.0050 |
| *Pardalotus punctatus* | +0.0079 | -0.0050 | +0.0028 | +0.0072 |
| *Pardalotus striatus* | +0.0092 | -0.0141 | +0.0035 | -0.0313 |
| *Petroica boodang* | +0.0051 | +0.0046 | +0.0038 | -0.0058 |
| *Petroica phoenicea* | +0.0036 | -0.0057 | +0.0005 | -0.0384 |
| *Phaps elegans* | +0.0043 | -0.0050 | +0.0050 | +0.0293 |
| *Phylidonyris novaehollandiae* | +0.0039 | +0.0150 | +0.0028 | +0.0214 |
| *Phylidonyris pyrrhopterus* | +0.0011 | +0.0025 | +0.0016 | -0.0050 |
| *Platycercus elegans* | +0.0043 | -0.0261 | +0.0035 | +0.0264 |
| *Platycercus eximius* | +0.0056 | -0.0175 | +0.0037 | +0.0116 |
| *Psephotus haematonotus* | +0.0033 | +0.0213 | +0.0025 | -0.0001 |
| *Ptilotula penicillata* | +0.0044 | -0.0056 | +0.0043 | -0.0045 |
| *Rhipidura albiscapa* | +0.0053 | +0.0035 | +0.0042 | +0.0070 |
| *Rhipidura rufifrons* | +0.0022 | +0.0385 | +0.0024 | +0.0331 |
| *Sericornis frontalis* | +0.0039 | +0.0063 | +0.0049 | +0.0129 |
| *Smicrornis brevirostris* | +0.0061 | -0.0201 | +0.0031 | -0.0193 |
| *Stipiturus malachurus* | +0.0027 | +0.0146 | -0.0003 | +0.0054 |
| *Strepera graculina* | +0.0021 | -0.0020 | +0.0022 | +0.0315 |
| *Threskiornis spinicollis* | +0.0068 | +0.0167 | +0.0094 | +0.0145 |
| *Todiramphus sanctus* | +0.0068 | +0.0077 | +0.0059 | +0.0177 |
| *Turnix varius* | +0.0126 | -0.0128 | +0.0055 | -0.0199 |
| *Vanellus miles* | +0.0012 | +0.0063 | +0.0018 | +0.0040 |
| *Zoothera lunulata* | +0.0006 | +0.0006 | -0.0011 | +0.0109 |
| *Zosterops lateralis* | +0.0037 | -0.0011 | +0.0025 | -0.0105 |

\newpage

## Table S16. Per-species mammal contrasts

FT = fine-tuned network; TO = target-only network; C = selected conventional model. Values are paired AUC differences. Development first averages spatial folds. The geographic setting is the five pooled withheld patches for the eight Tasmanian targets and camera-supported Tasmania for the five mainland targets. Species are repeated across the separately specified experiments without treating them as independent ecological replicates.

### Table S16a. Tasmanian targets

| Species | Development FT − TO | New-region FT − TO | Development FT − C | New-region FT − C |
| --- | --- | --- | --- | --- |
| *Dasyurus maculatus* | -0.0061 | +0.0052 | -0.0357 | +0.0048 |
| *Dasyurus viverrinus* | -0.0476 | -0.0134 | -0.0662 | -0.0164 |
| *Notamacropus rufogriseus* | +0.0078 | -0.0302 | -0.0335 | +0.0235 |
| *Pseudocheirus peregrinus* | +0.0007 | -0.0382 | -0.0045 | -0.0458 |
| *Sarcophilus harrisii* | -0.0071 | -0.0106 | -0.0474 | +0.1111 |
| *Thylogale billardierii* | -0.0547 | -0.0003 | -0.1602 | -0.0003 |
| *Trichosurus vulpecula* | +0.0189 | -0.0031 | -0.0424 | -0.0579 |
| *Vombatus ursinus* | +0.0341 | -0.0273 | -0.0084 | -0.0603 |

### Table S16b. Mainland targets

| Species | Development FT − TO | New-region FT − TO | Development FT − C | New-region FT − C |
| --- | --- | --- | --- | --- |
| *Dasyurus maculatus* | +0.0097 | +0.0272 | +0.0025 | -0.0192 |
| *Notamacropus rufogriseus* | +0.0027 | -0.0830 | +0.0004 | +0.0647 |
| *Pseudocheirus peregrinus* | +0.0107 | +0.0965 | +0.0051 | -0.0446 |
| *Trichosurus vulpecula* | +0.0211 | -0.1451 | +0.0108 | -0.1172 |
| *Vombatus ursinus* | -0.0005 | +0.0269 | +0.0009 | -0.0224 |
