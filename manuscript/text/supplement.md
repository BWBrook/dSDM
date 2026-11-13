# Supporting information

This file gives model specifications and descriptive comparisons for the three study settings. The article cites it as Supporting information; table numbers below provide navigation within this file.

- Tables S1–S4: paired cross-case results, bird recording-richness diagnostics, model grids and the target-only benchmark.
- Tables S5–S9: Tasmania training-pseudoabsence sensitivity, including per-species performance, maps and negative-source specificity.
- Tables S10–S12: the crossed training and evaluation comparison, with AUC, TSS and MCC.
- Tables S13–S14: bird learning curves, shared-information controls and absolute AUC by scoring extent.
- Tables S15–S16: all primary bird and mammal species’ paired AUC contrasts.

Methods S1–S4 describe the paired reporting, Tasmania sensitivity, survey-only evaluation and data sources. All tables use accepted aggregate outputs; no model fits or held-response scoring were repeated for this reconstruction.

## Supplementary methods S1. Model specifications and paired reporting

Cross-case contrasts are reported in the paired order of the inner and outer assessments. Within each assessment, species-level ROC AUC contrasts were summarized by their arithmetic mean, median and interquartile range. Quartiles use linear interpolation with inclusive endpoints (R type 7). The positive count is the number of species with a contrast greater than zero. The single-deletion range is the minimum and maximum of the species mean after deleting each species once. These summaries are descriptive; the IQR is not a confidence interval, and the deletion calculation does not assume independent species or represent joint ecological uncertainty.

The central 95% species-composition resampling ranges in Table S1d use 100,000 draws of 73 species with replacement from the observed primary bird panel. A single draw carries all methods, inner estimates and the three outer regions together; outer AUC remains the equal-region mean within species before averaging species. The reported endpoints are the 2.5th and 97.5th percentiles of replicate means, with linear interpolation. NumPy PCG64 uses two spawned streams from SeedSequence(20261008), stream 0 for species and stream 1 for focal blocks. These post hoc ranges describe empirical reweighting conditional on the fitted models, data and regions. They are not confidence intervals and exclude fitting, spatial-sampling, model-selection and population uncertainty. No coverage, significance or probability-of-benefit interpretation is attached to them.

The November display extension uses the same 100,000 paired species draws and primary-panel random stream for the within-bioregion-and-fold contrast and the four new-region model comparisons (Table S1h). For recording-richness ranges (Table S2e), the same species draw carries all three bins within each common-support panel. The separate 59-species development, 38-species SEH and 55-species NNC panels use PCG64 streams 0, 1 and 2 spawned from SeedSequence(20261113), with species sorted lexically. Quantiles again use linear interpolation. Each range describes empirical species composition conditional on its own observed panel, fitted models, data and regions; it is not a confidence interval or an estimate of fitting, spatial-sampling, model-selection or population uncertainty.

The inner-only focal-block width check uses 100,000 draws of ten blocks with replacement, keeping every primary-panel species in each sampled block occurrence. The mean is the sum of these species contrasts divided by their total count, rather than an equal mean of block means. The ten primary-panel block sizes are 6, 4, 3, 9, 7, 8, 9, 10, 7 and 10. These hash-balanced computational blocks share pretrained objects but are neither taxonomic nor spatial clusters. Common folds, predictors, geography, architecture selection and overlapping auxiliary pools still induce dependence across blocks. Ten blocks give limited tail resolution. Table S1e compares widths descriptively; neither range is selected as a conservative inferential bound.

The exploratory inner bird recording-richness check reused all available focal presences for each background bin; only the background cells changed between the 10–24, 25–99 and 100+ donor-richness classes. Each stratified panel retained the same targets across all three bins, requiring at least 20 presences and 20 bin-specific backgrounds in every fold. Seed means were formed first, followed by equal-fold and equal-species means. The additive check retained all targets in each panel without the diagnostic minimum-20 gate. It weighted each bin's AUC contrast by its background share within each species and fold before averaging folds and species; separate averaged weights were not multiplied by separate averaged AUCs.

The original Tasmania conventional grid used the candidate IDs and family-specific seeds in `conventional_baseline_production.json`: `seed00` for the intercept and histogram-gradient-boosting families, and `seed00`–`seed04` for elastic net, random forest and shallow ANN. The portable mainland and bird grids used the common subset shown in Table S3, one screening seed for every family except shallow ANN (`seed00`–`seed02`), then the selected refit seeds: `seed00` for intercept, elastic net and histogram-gradient boosting, and `seed00`–`seed04` for random forest and shallow ANN. Candidate ranking used mean-fold ROC AUC, then pooled out-of-fold TSS, then candidate ID; family ranking used the same first two criteria and then family ID.

The four bird residual-network candidates and shared constants are listed below the conventional grids. The bird selection scope was the 73 primary targets with one selection seed. Pretraining excluded the focal target and its entire focal block in the ten-block design, with the held-fold exclusion retained. Retained-full refits used the same rounded median selected epoch across 25 fold-by-seed fits for each target and arm; pretraining used the corresponding block-level median. Exact shallow-ANN epochs were recovered before the outer assessment, as recorded by the accepted outer inventory. The accepted architecture constants were GELU activation, LayerNorm, AdamW, learning rate 0.001, batch size 128, maximum 300 epochs, patience 30 and minimum improvement 0.00001; stopping used the next fold and replay used all four non-held folds at the selected epoch.

The bird software environment was fixed by a uv lockfile, including PyTorch 2.13.0, scikit-learn 1.9.0 and NumPy 2.5.1. Source and environment fingerprints accompany the archived run records. Historical mammal executions retain their separately archived specifications.

## Table S1. Cross-case species-level contrasts

Positive means favour full fine-tuning over the named comparator. Values are AUC differences.

### Table S1a. Full fine-tuning minus target-only network

| Assessment | Mean | Median [Q1, Q3] | Positive/n |
| --- | ---: | ---: | ---: |
| Tasmania inner | -0.006750 | -0.002724 [-0.017204, +0.010619] | 4/8 |
| Tasmania held patches | -0.014741 | -0.012001 [-0.028057, -0.002384] | 1/8 |
| Mainland inner | +0.008745 | +0.009739 [+0.002744, +0.010681] | 4/5 |
| Mainland to Tasmania | -0.015513 | +0.026863 [-0.083014, +0.027193] | 3/5 |
| Birds inner (common 73) | +0.005781 | +0.005384 [+0.003624, +0.006995] | 72/73 |
| Birds outer (equal regions) | -0.000396 | -0.000565 [-0.009489, +0.007744] | 34/73 |

### Table S1b. Full fine-tuning minus selected conventional learner

| Assessment | Mean | Median [Q1, Q3] | Positive/n |
| --- | ---: | ---: | ---: |
| Tasmania inner | -0.049788 | -0.039027 [-0.052139, -0.027194] | 0/8 |
| Tasmania held patches | -0.005141 | -0.008332 [-0.048783, +0.009498] | 3/8 |
| Mainland inner | +0.003950 | +0.002468 [+0.000936, +0.005142] | 5/5 |
| Mainland to Tasmania | -0.027733 | -0.022426 [-0.044558, -0.019194] | 1/5 |
| Birds inner (common 73) | +0.003390 | +0.003190 [+0.002157, +0.004317] | 67/73 |
| Birds outer (equal regions) | +0.002771 | +0.001717 [-0.010495, +0.017709] | 39/73 |

\newpage

### Table S1c. Single-species deletion sensitivity

| Assessment | Target-only deletion range | Conventional deletion range |
| --- | ---: | ---: |
| Tasmania inner | [-0.012582, +0.000107] | [-0.056257, -0.034011] |
| Tasmania held patches | [-0.017586, -0.011393] | [-0.021753, +0.002743] |
| Mainland inner | [+0.005658, +0.011064] | [+0.002234, +0.004840] |
| Mainland to Tasmania | [-0.043507, +0.016877] | [-0.050840, -0.005370] |
| Birds inner (common 73) | [+0.005550, +0.005867] | [+0.003307, +0.003464] |
| Birds outer (equal regions) | [-0.001206, +0.000177] | [+0.002208, +0.003582] |

### Table S1d. Bird species-composition resampling ranges

Central 95% ranges of resampled-panel means, conditional on the observed 73 species, fitted models, data and regions. These are not confidence intervals and exclude fitting, spatial-sampling, model-selection and population uncertainty.

| Assessment | Comparator | Mean | Resampling range |
| --- | --- | ---: | ---: |
| Inner | Target-only | +0.005781 | [+0.005040, +0.006608] |
| Inner | Conventional | +0.003390 | [+0.002873, +0.003911] |
| Outer | Target-only | -0.000396 | [-0.004063, +0.003389] |
| Outer | Conventional | +0.002771 | [-0.001683, +0.007188] |

### Table S1e. Inner bird focal-block resampling width check

Both schemes preserve paired model comparisons. Block replicates contain varying numbers of species. The ten computational blocks are not ecological clusters, and neither scheme estimates all dependence or supplies population coverage.

| Comparator | Scheme | Central 95% range | Width |
| --- | --- | ---: | ---: |
| Target-only | Species | [+0.005040, +0.006608] | 0.00156738 |
| Target-only | Focal block | [+0.005213, +0.006305] | 0.00109221 |
| Conventional | Species | [+0.002873, +0.003911] | 0.00103795 |
| Conventional | Focal block | [+0.002725, +0.004010] | 0.001285 |

\newpage

### Table S1f. Absolute AUC at full target data

Mean ROC AUC across species under the original training and evaluation definitions. Tasmania uses eight species, mainland mammals five, and birds the common 73-species panel. Development values first average the five spatial folds within species; Tasmania patch values pool the withheld patches, mainland transfer uses camera-supported Tasmania, and bird transfer first averages the three withheld regions within species. The Tasmania evaluation includes both constructed and survey-supported negatives. The bird development mean differs from the pooled-domain value in Table S14 because the latter recomputes AUC across all retained predictions.

| Assessment | Fine-tuned | Target-only | Conventional |
| --- | ---: | ---: | ---: |
| Tasmania development | 0.7133 | 0.7200 | 0.7631 |
| Tasmania withheld patches | 0.8390 | 0.8537 | 0.8441 |
| Mainland development | 0.9091 | 0.9004 | 0.9052 |
| Mainland to Tasmania | 0.5560 | 0.5715 | 0.5837 |
| Bird development | 0.8316 | 0.8258 | 0.8282 |
| Bird withheld regions | 0.6827 | 0.6831 | 0.6800 |

\newpage

### Table S1g. Full-data true skill statistic in every setting

Values are equal-species means. Development first averages the five folds within species; Tasmania geographic assessment pools the five withheld patches, mainland transfer uses camera-supported Tasmania, and bird geographic assessment averages the three regions within species. Each learner uses its own maximum-TSS development threshold, frozen for geographic assessment. TSS was co-primary in the original Tasmania design; the other settings use it descriptively. These threshold-dependent scores need not rank learners like AUC.

| Assessment | Species | Fine-tuned | Target-only | Conventional |
| --- | --- | --- | --- | --- |
| Tasmania development | 8 | 0.3493 | 0.3484 | 0.4084 |
| Tasmania withheld patches | 8 | 0.5575 | 0.5099 | 0.5316 |
| Mainland development | 5 | 0.6790 | 0.6555 | 0.6717 |
| Mainland to Tasmania | 5 | -0.0119 | 0.0121 | 0.0292 |
| Bird development | 73 | 0.5251 | 0.5156 | 0.5186 |
| Bird new regions | 73 | 0.2018 | 0.1920 | 0.1901 |

\newpage

### Table S1h. Extended bird species-composition ranges

The first row rescored retained development predictions within bioregions and spatial folds. Other rows use new-region predictions and average NCP, SEH and NNC within species. All rows retain the primary 73 species. Ensemble weights are fixed at 50:50. The fine-tuned ensemble was prespecified as exploratory; the target-only ensemble and the extent diagnostic were post hoc.

| Assessment | Contrast | Mean | Resampling range |
| --- | --- | --- | --- |
| Development: within bioregions and folds | Fine-tuned − target-only | +0.0072 | [+0.0058, +0.0086] |
| New regions | Target-only − conventional | +0.0032 | [-0.0006, +0.0071] |
| New regions | Fine-tuned − conventional | +0.0028 | [-0.0017, +0.0072] |
| New regions | Target-only ensemble − conventional | +0.0096 | [+0.0074, +0.0119] |
| New regions | Fine-tuned ensemble − conventional | +0.0104 | [+0.0078, +0.0129] |

\newpage

## Table S2. Bird recording-richness diagnostics

### Table S2a. Inner richness-bin contrasts

| Panel | Contrast | Background richness | Mean | Positive/n |
| --- | --- | --- | ---: | ---: |
| Primary 59 | Fine-tuning − conventional | 10–24 | +0.005023 | 56/59 |
| Primary 59 | Fine-tuning − conventional | 25–99 | +0.001948 | 43/59 |
| Primary 59 | Fine-tuning − conventional | 100+ | -0.003922 | 19/59 |
| Primary 59 | Fine-tuning − target-only | 10–24 | +0.007548 | 58/59 |
| Primary 59 | Fine-tuning − target-only | 25–99 | +0.003884 | 54/59 |
| Primary 59 | Fine-tuning − target-only | 100+ | -0.004263 | 22/59 |
| Other 83 | Fine-tuning − conventional | 10–24 | +0.001640 | 68/83 |
| Other 83 | Fine-tuning − conventional | 25–99 | +0.000411 | 50/83 |
| Other 83 | Fine-tuning − conventional | 100+ | -0.003331 | 29/83 |
| Other 83 | Fine-tuning − target-only | 10–24 | +0.003764 | 81/83 |
| Other 83 | Fine-tuning − target-only | 25–99 | +0.003092 | 69/83 |
| Other 83 | Fine-tuning − target-only | 100+ | -0.000580 | 47/83 |
| All 142 | Fine-tuning − conventional | 10–24 | +0.003045 | 124/142 |
| All 142 | Fine-tuning − conventional | 25–99 | +0.001049 | 93/142 |
| All 142 | Fine-tuning − conventional | 100+ | -0.003576 | 48/142 |
| All 142 | Fine-tuning − target-only | 10–24 | +0.005336 | 139/142 |
| All 142 | Fine-tuning − target-only | 25–99 | +0.003421 | 123/142 |
| All 142 | Fine-tuning − target-only | 100+ | -0.002110 | 69/142 |

### Table S2b. Exact background-share-weighted additive decomposition

| Fine-tuning minus conventional | Primary 73 | Other 84 |
| --- | ---: | ---: |
| 10–24 contribution | +0.002604758897 | +0.000805293560 |
| 25–99 contribution | +0.000831871721 | +0.000199296703 |
| 100+ contribution | -0.000046772300 | -0.000066734031 |
| Sum of contributions | +0.003389858318 | +0.000937856232 |
| All-background mean | +0.003389858318 | +0.000937856232 |
| Maximum identity error | 2.151e-16 | 1.704e-16 |

### Table S2c. Withheld-region recording-richness contrasts

These are fine-tuned-minus-conventional AUC contrasts. All focal presences are reused against each background bin. A region's same species must have at least 20 presences and 20 backgrounds in every bin: 38 species in SEH and 55 in NNC. NCP has no common three-bin species and no corresponding estimate. The diagnostic definitions were fixed after development inspection but before the withheld responses were opened. Background richness records how many other species were recorded in a cell; it does not separate survey effort from ecological richness or environment.

| Region | Other species recorded | Common species | Mean AUC contrast |
| --- | --- | --- | --- |
| NCP | 10–24 | 0 | NA |
| NCP | 25–99 | 0 | NA |
| NCP | 100+ | 0 | NA |
| SEH | 10–24 | 38 | -0.0038 |
| SEH | 25–99 | 38 | -0.0140 |
| SEH | 100+ | 38 | -0.0283 |
| NNC | 10–24 | 55 | +0.0148 |
| NNC | 25–99 | 55 | +0.0060 |
| NNC | 100+ | 55 | -0.0259 |

### Table S2d. Background recording-richness shares in the withheld regions

Shares are averaged within species across the 73-species primary panel, rather than calculated from pooled counts. In particular, the high-richness means describe a small part of the background support.

| Region | Other species recorded | Mean background share (%) |
| --- | --- | --- |
| NCP | 10–24 | 62.2060 |
| NCP | 25–99 | 37.5153 |
| NCP | 100+ | 0.2787 |
| SEH | 10–24 | 57.9879 |
| SEH | 25–99 | 41.4010 |
| SEH | 100+ | 0.6112 |
| NNC | 10–24 | 49.7439 |
| NNC | 25–99 | 47.4845 |
| NNC | 100+ | 2.7716 |

\newpage

### Table S2e. Recording-richness species-composition ranges

These ranges accompany Figure 4a. Each panel retains the same species across all three bins and resamples those species jointly across bins. Development uses 59 species, SEH 38 and NNC 55. No NCP three-bin range is defined. Means and resampling ranges are AUC differences, fine-tuned minus conventional.

| Panel | Other species recorded | Mean | Resampling range |
| --- | --- | --- | --- |
| Development | 10–24 | +0.0050 | [+0.0043, +0.0058] |
| Development | 25–99 | +0.0019 | [+0.0011, +0.0027] |
| Development | 100+ | -0.0039 | [-0.0062, -0.0017] |
| SEH | 10–24 | -0.0038 | [-0.0163, +0.0088] |
| SEH | 25–99 | -0.0140 | [-0.0291, +0.0010] |
| SEH | 100+ | -0.0283 | [-0.0646, +0.0052] |
| NNC | 10–24 | +0.0148 | [+0.0061, +0.0238] |
| NNC | 25–99 | +0.0060 | [-0.0011, +0.0132] |
| NNC | 100+ | -0.0259 | [-0.0383, -0.0143] |

\newpage

## Table S3. Conventional grids and bird architecture candidates

Portable = candidate retained in both the mainland and bird conventional grids; all other rows belong to the original Tasmania grid only.

### Table S3a. Intercept and elastic-net candidates

| Candidate | C | l1 ratio | Portable |
| --- | ---: | ---: | ---: |
| null00 | — | — | yes |
| enet00 | 0.01 | 0 | yes |
| enet01 | 0.03 | 0 | no |
| enet02 | 0.1 | 0 | no |
| enet03 | 0.03 | 0.5 | no |
| enet04 | 0.1 | 0.5 | yes |
| enet05 | 0.3 | 0.5 | no |
| enet06 | 0.03 | 1 | no |
| enet07 | 0.1 | 1 | no |
| enet08 | 0.3 | 1 | yes |
| enet09 | 1 | 0.5 | yes |

### Table S3b. Random-forest candidates

| Candidate | max features | min samples leaf | max depth | Portable |
| --- | ---: | ---: | ---: | ---: |
| rf00 | sqrt | 1 | — | yes |
| rf01 | sqrt | 3 | — | no |
| rf02 | sqrt | 10 | — | yes |
| rf03 | 0.33 | 3 | — | yes |
| rf04 | 0.33 | 10 | — | no |
| rf05 | 0.67 | 3 | 20 | yes |
| rf06 | 0.67 | 10 | 20 | no |

### Table S3c. Histogram-gradient-boosting candidates

| Candidate | Learning rate | Max leaf nodes | Min samples leaf | L2 regularization | Portable |
| --- | ---: | ---: | ---: | ---: | ---: |
| hgb00 | 0.03 | 15 | 20 | 0 | yes |
| hgb01 | 0.03 | 31 | 20 | 1 | no |
| hgb02 | 0.05 | 15 | 20 | 1 | yes |
| hgb03 | 0.05 | 31 | 20 | 1 | no |
| hgb04 | 0.05 | 31 | 50 | 1 | yes |
| hgb05 | 0.1 | 15 | 20 | 10 | yes |
| hgb06 | 0.1 | 31 | 50 | 10 | no |

### Table S3d. Shallow-ANN candidates

| Candidate | Width | Dropout | Weight decay | Learning rate | Portable |
| --- | ---: | ---: | ---: | ---: | ---: |
| ann00 | 32 | 0 | 0 | 0.001 | yes |
| ann01 | 32 | 0.1 | 1e-05 | 0.001 | no |
| ann02 | 64 | 0.1 | 1e-05 | 0.001 | yes |
| ann03 | 64 | 0.2 | 0.0001 | 0.001 | no |
| ann04 | 128 | 0.2 | 0.0001 | 0.0005 | yes |
| ann05 | 128 | 0.3 | 0.001 | 0.0005 | no |

Shared conventional constants were 500 trees with bootstrap sampling for random forests, 300 iterations without early stopping for histogram-gradient boosting, and 300 maximum epochs with patience 30 for shallow ANNs. A dash in the random-forest depth column denotes no depth limit; decimal max-feature values are fractions of the input columns. Elastic-net candidates used the SAGA solver with 5000 iterations and tolerance 1e−6. `null00` was the empirical inner-training prevalence clipped at 1e−7. GAM and residual-MLP registry entries were excluded from these conventional grids.

### Table S3e. Bird residual-network architecture candidates

| Candidate | Blocks | Width | Bottleneck | Dropout | Weight decay |
| --- | ---: | ---: | ---: | ---: | ---: |
| bridge_control | 3 | 128 | 64 | 0 | 0.001 |
| bridge_wide | 3 | 256 | 64 | 0 | 0.001 |
| bridge_deep | 6 | 128 | 64 | 0 | 0.001 |
| seawfb_scale | 6 | 256 | 128 | 0 | 0.001 |

\newpage

## Table S4. Bird target-only baseline comparison

These descriptive contrasts use the full-data mean-fold AUC endpoint. They document baseline performance while retaining the asymmetry that architecture selection used fine-tuning.

| Panel | n | Target-only − ANN | Target-only − conventional |
| --- | ---: | ---: | ---: |
| Primary 73 | 73 | +0.003705 | -0.002391 |
| All 157 | 157 | +0.001864 | -0.002416 |

<!-- accepted-input-sha256
summary: evidence/cross_case_synthesis/20261005/revision-01/summary.json sha256=6834e34c74767864686862734f57a64a2ac10b324fcdadab89797e1cecbe0fd2
effort_followup: evidence/seawfb_dsdm/goal052/effort-followup-20261002.json sha256=742c367ab100886da764853cceeaca1684176259d934794d7ec83c8896e5cad0
effort_review: evidence/seawfb_dsdm/goal052/effort-review-20261001.json sha256=920b43478ec4d8cb3d94b165017e69b20cdfe4b7bff8c9f6f3029c5161d7f7db
modeling_foundation: config/modeling_foundation_preflight.json sha256=35b6ab72ba2b8ba2267dc82179987bfffaa3f339d64272d68012444e46285f00
tasmania_conventional: config/conventional_baseline_production.json sha256=62b1c5255c5aa5c74f5ba598818dd13e2f2234c0cb13da58671c3be286ccefae
mainland_conventional: config/goal044_mainland_conventional.json sha256=66350f80d58e58eb1c55fa95cc9e4c899d8792404b09acc26d40c71715828a68
bird_conventional: config/goal051_seawfb_conventional.json sha256=48465d0a5180931a72ffc87aa830f6ce60da93a4b491558540af5afa9d42884d
bird_dsdm: config/goal052_seawfb_dsdm.json sha256=04b667168944b39ced1044da8f381553c4024e31cca1f5590f2fbc693e521f9a
uv_lock: uv.lock sha256=51712e74b2f9d78a4efb7bfd6732244188e8c6c5bc722f7a78f2724e6b8b84f6
bird_composition_resampling: evidence/cross_case_synthesis/20261008/bird-composition-resampling.csv sha256=27e9815fc4ec58900690b7a06e7374a10ae780e619c53c0de6461c392f9cbc13
-->
