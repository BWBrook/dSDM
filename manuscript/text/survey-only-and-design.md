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
| --- | ---: | ---: | ---: | ---: | ---: |
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
