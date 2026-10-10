\newpage

## Supplementary methods S2. Tasmania pseudoabsence-removal sensitivity

The sensitivity removed protocol-defined pseudoabsences from target discovery, stopping, replay and outer-fitting roles by canonical identity. The original five folds, three nested ladders at each reduced fraction, full-data endpoint, and evaluation rows were retained. All 896 fitting roles retained both classes, although stopping sets retained as few as two absences. Target support masks and conventional encoders were fitted using the retained target rows. Auxiliary training already excluded pseudoabsences; its original states, feature transforms, architecture and seed policy were fixed. Missing inner auxiliary weights were recovered by 200 replay-only fits at the original recorded epochs, with exact original initialization, model-state and auxiliary-prediction hashes required before target fitting. No auxiliary discovery or new community covariate was fitted.

The two residual networks and the primary-selected conventional candidate were refitted for all eight species and all seven endpoints. Conventional candidates were not reselected after filtering. Sensitivity thresholds were recomputed from seed-averaged inner out-of-fold probabilities using the original maximum-TSS rule and lower-median tie rule. The complete 8,125-fit production panel and 14 separate smoke fits passed closure before one new semantic parse of the 1,672 original held responses. An independent replay checked all performance, threshold, source-specificity and map summaries. Thylogale, which had no target pseudoabsences to remove, reproduced its original inner and outer predictions, thresholds and maps exactly.

This implements a sensitivity question in the original protocol, with training-only filtering, threshold recalibration, fixed comparator selection and map summaries specified after primary outer opening. It is not a fully prospective confirmatory test. Removing pseudoabsences changes class balance, calibration, early stopping and spatial support together. The paired changes are conditional on this fixed evaluation sample, including its pseudoabsences; they do not identify false absences or correct imperfect detection. Means below weight the eight species equally within each endpoint. Endpoints, folds, seeds and species are not independent ecological replicates. No inferential intervals or significance tests are reported.

### Table S5. Full-data training perturbation and unchanged evaluation support

Training columns show retained presences and survey-supported absences, then removed pseudoabsences. Held columns show the unchanged evaluation counts. All counts are species–cell rows.

| Species | Train presence | Train survey zero | Removed pseudoabsence | Held presence | Held survey zero | Held pseudoabsence |
| --- | --- | --- | --- | --- | --- | --- |
| *T. billardierii* | 1162 | 106 | 0 | 198 | 19 | 0 |
| *N. rufogriseus* | 1056 | 128 | 25 | 203 | 17 | 5 |
| *T. vulpecula* | 980 | 146 | 12 | 167 | 27 | 4 |
| *P. peregrinus* | 303 | 508 | 98 | 63 | 73 | 38 |
| *V. ursinus* | 977 | 131 | 45 | 120 | 7 | 18 |
| *S. harrisii* | 3083 | 92 | 11 | 377 | 9 | 1 |
| *D. maculatus* | 833 | 197 | 62 | 116 | 21 | 29 |
| *D. viverrinus* | 405 | 564 | 115 | 56 | 69 | 35 |

\newpage

### Table S6a. Full-data ROC AUC: primary → sensitivity

Each cell gives the original value followed by the refitted sensitivity value on the same held rows. Threshold metrics use their respective inner-derived thresholds.

| Species | Target-only | Fine-tuning | Conventional |
| --- | --- | --- | --- |
| *T. billardierii* | 1.0000 → 1.0000 | 0.9997 → 0.9997 | 1.0000 → 1.0000 |
| *N. rufogriseus* | 0.8294 → 0.8117 | 0.7991 → 0.7976 | 0.7756 → 0.7389 |
| *T. vulpecula* | 0.8061 → 0.8072 | 0.8030 → 0.8117 | 0.8608 → 0.8574 |
| *P. peregrinus* | 0.8077 → 0.8064 | 0.7695 → 0.7659 | 0.8152 → 0.7869 |
| *V. ursinus* | 0.8533 → 0.4330 | 0.8260 → 0.4067 | 0.8863 → 0.4237 |
| *S. harrisii* | 0.8679 → 0.8496 | 0.8573 → 0.8706 | 0.7462 → 0.7857 |
| *D. maculatus* | 0.7243 → 0.5205 | 0.7295 → 0.5490 | 0.7247 → 0.6562 |
| *D. viverrinus* | 0.9413 → 0.9348 | 0.9279 → 0.9248 | 0.9443 → 0.9337 |
| Equal-species mean | 0.8537 → 0.7704 | 0.8390 → 0.7657 | 0.8441 → 0.7728 |

\newpage

### Table S6b. Full-data TSS: primary → sensitivity

Each cell gives the original value followed by the refitted sensitivity value on the same held rows. Threshold metrics use their respective inner-derived thresholds.

| Species | Target-only | Fine-tuning | Conventional |
| --- | --- | --- | --- |
| *T. billardierii* | 0.9040 → 0.9040 | 0.9343 → 0.9343 | 0.7172 → 0.7172 |
| *N. rufogriseus* | 0.4716 → 0.4666 | 0.4716 → 0.4716 | 0.3583 → 0.3829 |
| *T. vulpecula* | 0.4458 → 0.5356 | 0.5835 → 0.6135 | 0.5776 → 0.5955 |
| *P. peregrinus* | 0.4286 → 0.4170 | 0.4393 → 0.3719 | 0.4976 → 0.4058 |
| *V. ursinus* | 0.4617 → 0.0800 | 0.4050 → 0.0383 | 0.5783 → -0.1283 |
| *S. harrisii* | 0.4162 → 0.4427 | 0.6923 → 0.4241 | 0.4191 → 0.3570 |
| *D. maculatus* | 0.1997 → 0.1569 | 0.2431 → 0.0600 | 0.3241 → 0.1828 |
| *D. viverrinus* | 0.7514 → 0.7225 | 0.6909 → 0.6662 | 0.7802 → 0.7527 |
| Equal-species mean | 0.5099 → 0.4657 | 0.5575 → 0.4475 | 0.5316 → 0.4082 |

\newpage

### Table S6c. Full-data MCC: primary → sensitivity

Each cell gives the original value followed by the refitted sensitivity value on the same held rows. Threshold metrics use their respective inner-derived thresholds.

| Species | Target-only | Fine-tuning | Conventional |
| --- | --- | --- | --- |
| *T. billardierii* | 0.6723 → 0.6723 | 0.7448 → 0.7448 | 0.4262 → 0.4262 |
| *N. rufogriseus* | 0.4310 → 0.4199 | 0.4310 → 0.4310 | 0.2560 → 0.2843 |
| *T. vulpecula* | 0.3240 → 0.3945 | 0.4371 → 0.4663 | 0.4316 → 0.4486 |
| *P. peregrinus* | 0.4121 → 0.4030 | 0.4306 → 0.3579 | 0.5073 → 0.3907 |
| *V. ursinus* | 0.3498 → 0.0737 | 0.3072 → 0.0335 | 0.5105 → -0.0996 |
| *S. harrisii* | 0.1449 → 0.1584 | 0.2344 → 0.1488 | 0.1353 → 0.1138 |
| *D. maculatus* | 0.1888 → 0.1464 | 0.2235 → 0.0551 | 0.3074 → 0.1695 |
| *D. viverrinus* | 0.7168 → 0.6895 | 0.6633 → 0.6368 | 0.7452 → 0.7190 |
| Equal-species mean | 0.4050 → 0.3697 | 0.4340 → 0.3593 | 0.4149 → 0.3066 |

\newpage

### Table S7. Fine-tuning contrasts at every endpoint

Values are equal-species mean fine-tuning minus the named comparator, primary → sensitivity. Positive values favour fine-tuning. L0–L2 denote the three original nested ladders. Each row uses eight species; rows must not be treated as independent replicates.

Comparator: Target-only.

| Endpoint | AUC | TSS | MCC |
| --- | --- | --- | --- |
| 25% / L0 | +0.0011 → -0.0084 | -0.0109 → -0.0396 | -0.0171 → -0.0474 |
| 25% / L1 | -0.0109 → +0.0072 | -0.0204 → -0.0284 | -0.0177 → +0.0059 |
| 25% / L2 | -0.0078 → -0.0205 | +0.0732 → -0.0308 | +0.0561 → -0.0132 |
| 50% / L0 | +0.0127 → -0.0168 | +0.0560 → -0.0033 | +0.0492 → -0.0094 |
| 50% / L1 | -0.0064 → -0.0233 | +0.0138 → -0.0297 | +0.0015 → -0.0267 |
| 50% / L2 | -0.0078 → -0.0118 | -0.0283 → -0.0010 | +0.0060 → +0.0058 |
| 100% / full | -0.0147 → -0.0047 | +0.0477 → -0.0182 | +0.0290 → -0.0104 |

Comparator: Conventional.

| Endpoint | AUC | TSS | MCC |
| --- | --- | --- | --- |
| 25% / L0 | +0.0186 → +0.0036 | +0.0728 → +0.0047 | +0.0419 → -0.0036 |
| 25% / L1 | +0.0168 → +0.0017 | -0.0393 → -0.0677 | -0.0372 → -0.0328 |
| 25% / L2 | -0.0102 → -0.0314 | +0.0335 → +0.0108 | +0.0249 → +0.0016 |
| 50% / L0 | +0.0145 → -0.0144 | +0.0067 → -0.0186 | -0.0178 → -0.0149 |
| 50% / L1 | +0.0035 → -0.0117 | +0.0289 → -0.0219 | +0.0130 → +0.0022 |
| 50% / L2 | -0.0005 → -0.0016 | -0.0473 → +0.0248 | -0.0279 → +0.0170 |
| 100% / full | -0.0051 → -0.0071 | +0.0260 → +0.0393 | +0.0190 → +0.0527 |

\newpage

### Table S8. Full-data suitability-map comparisons

Each pair covers the same 71,023 structural-domain cells. Rank displacement is sensitivity minus primary in percentile points, using average ranks for ties; the displayed interval contains the 2.5th and 97.5th percentiles of cell displacements, not uncertainty bounds. Top-decile retention is the intersection divided by 7,103. Exact score ties are resolved by ascending canonical cell ID. These model outputs are relative suitability scores, not occupancy probabilities. Spearman correlation is NA if either map is constant.

| Species | Method | Spearman $\rho$ | Median rank shift [2.5%, 97.5%] | Top-decile retention |
| --- | --- | --- | --- | --- |
| *T. billardierii* | Target-only | 1.0000 | +0.00 [+0.00, +0.00] | 7103/7103 (100.0%) |
| *T. billardierii* | Fine-tuning | 1.0000 | +0.00 [+0.00, +0.00] | 7103/7103 (100.0%) |
| *T. billardierii* | Conventional | 1.0000 | +0.00 [+0.00, +0.00] | 7103/7103 (100.0%) |
| *N. rufogriseus* | Target-only | 0.8551 | -1.01 [-22.94, +45.98] | 3757/7103 (52.9%) |
| *N. rufogriseus* | Fine-tuning | 0.8522 | -0.62 [-31.24, +39.65] | 2929/7103 (41.2%) |
| *N. rufogriseus* | Conventional | 0.5844 | -2.01 [-44.91, +63.28] | 2227/7103 (31.4%) |
| *T. vulpecula* | Target-only | 0.9834 | -0.16 [-11.53, +11.87] | 4566/7103 (64.3%) |
| *T. vulpecula* | Fine-tuning | 0.9707 | +0.02 [-18.02, +15.31] | 3057/7103 (43.0%) |
| *T. vulpecula* | Conventional | 0.8502 | -2.73 [-20.07, +47.22] | 3530/7103 (49.7%) |
| *P. peregrinus* | Target-only | 0.8690 | -0.35 [-24.74, +34.21] | 4143/7103 (58.3%) |
| *P. peregrinus* | Fine-tuning | 0.8363 | -1.13 [-23.14, +43.14] | 3537/7103 (49.8%) |
| *P. peregrinus* | Conventional | 0.7824 | -1.84 [-28.18, +44.68] | 3364/7103 (47.4%) |
| *V. ursinus* | Target-only | 0.7382 | -3.84 [-29.15, +52.79] | 5982/7103 (84.2%) |
| *V. ursinus* | Fine-tuning | 0.6454 | -3.37 [-35.46, +59.13] | 5648/7103 (79.5%) |
| *V. ursinus* | Conventional | 0.6648 | -4.28 [-35.06, +60.09] | 3824/7103 (53.8%) |
| *S. harrisii* | Target-only | 0.9443 | -1.51 [-14.65, +24.99] | 6075/7103 (85.5%) |
| *S. harrisii* | Fine-tuning | 0.9466 | -1.09 [-16.27, +24.49] | 5832/7103 (82.1%) |
| *S. harrisii* | Conventional | 0.8843 | -3.16 [-15.92, +40.36] | 5861/7103 (82.5%) |
| *D. maculatus* | Target-only | 0.6535 | -1.10 [-41.95, +52.77] | 5064/7103 (71.3%) |
| *D. maculatus* | Fine-tuning | 0.7283 | -2.80 [-32.18, +54.23] | 4427/7103 (62.3%) |
| *D. maculatus* | Conventional | 0.8446 | -3.03 [-23.02, +40.37] | 5173/7103 (72.8%) |
| *D. viverrinus* | Target-only | 0.9352 | -1.25 [-17.52, +26.30] | 3567/7103 (50.2%) |
| *D. viverrinus* | Fine-tuning | 0.8730 | -3.21 [-19.92, +39.77] | 3584/7103 (50.5%) |
| *D. viverrinus* | Conventional | 0.9187 | -1.25 [-20.00, +29.59] | 4497/7103 (63.3%) |

\newpage

### Table S9. Full-data specificity by absence source

Each cell gives primary → sensitivity true negatives over the unchanged source-specific absence denominator. Specificity is that fraction. NA denotes a zero denominator, not zero specificity. The two source-specific true-negative counts sum to the total true-negative count for the corresponding species and method.

| Species | Method | Survey-supported absence | Pseudoabsence |
| --- | --- | --- | --- |
| *T. billardierii* | Target-only | 19/19 → 19/19 | NA (0 rows) |
| *T. billardierii* | Fine-tuning | 19/19 → 19/19 | NA (0 rows) |
| *T. billardierii* | Conventional | 19/19 → 19/19 | NA (0 rows) |
| *N. rufogriseus* | Target-only | 12/17 → 12/17 | 0/5 → 0/5 |
| *N. rufogriseus* | Fine-tuning | 12/17 → 12/17 | 0/5 → 0/5 |
| *N. rufogriseus* | Conventional | 12/17 → 12/17 | 0/5 → 0/5 |
| *T. vulpecula* | Target-only | 24/27 → 24/27 | 3/4 → 3/4 |
| *T. vulpecula* | Fine-tuning | 24/27 → 24/27 | 3/4 → 3/4 |
| *T. vulpecula* | Conventional | 24/27 → 24/27 | 3/4 → 3/4 |
| *P. peregrinus* | Target-only | 47/73 → 59/73 | 27/38 → 19/38 |
| *P. peregrinus* | Fine-tuning | 54/73 → 60/73 | 30/38 → 13/38 |
| *P. peregrinus* | Conventional | 62/73 → 57/73 | 32/38 → 18/38 |
| *V. ursinus* | Target-only | 7/7 → 7/7 | 16/18 → 0/18 |
| *V. ursinus* | Fine-tuning | 7/7 → 7/7 | 15/18 → 0/18 |
| *V. ursinus* | Conventional | 3/7 → 7/7 | 15/18 → 0/18 |
| *S. harrisii* | Target-only | 6/9 → 6/9 | 1/1 → 1/1 |
| *S. harrisii* | Fine-tuning | 9/9 → 6/9 | 1/1 → 1/1 |
| *S. harrisii* | Conventional | 9/9 → 7/9 | 1/1 → 1/1 |
| *D. maculatus* | Target-only | 11/21 → 17/21 | 27/29 → 18/29 |
| *D. maculatus* | Fine-tuning | 9/21 → 17/21 | 26/29 → 11/29 |
| *D. maculatus* | Conventional | 4/21 → 11/21 | 26/29 → 24/29 |
| *D. viverrinus* | Target-only | 51/69 → 49/69 | 29/35 → 28/35 |
| *D. viverrinus* | Fine-tuning | 54/69 → 48/69 | 29/35 → 25/35 |
| *D. viverrinus* | Conventional | 53/69 → 52/69 | 30/35 → 30/35 |

The complete seven-endpoint performance, contrast and source-specificity tables, plus all eight three-method map plates, are retained with the aggregate evidence. Numerical tables above reproduce those verified outputs; they do not replace the original primary assessment.

<!-- assessment-receipt: 08915652195df252b062163df189f892b72ccdf1e66dab29cb4908d3b696ab56; independent-audit-receipt: d90a01ad2ac08ef36ff2c40bf7bce9223589011111cc2c67c124e399481ac3be -->
