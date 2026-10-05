# Goal052 retained-full outer assessment

This report is a deterministic rendering of an already-created `goal052-outer-scores-v1` JSON. It contains descriptive outer discrimination summaries only; it does not establish inferential significance, occupancy, or ecological/observation mechanisms.

## Source identity

- Score JSON SHA256: `3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41`
- Plan digest: `4b179d6cf8134551099c896bbcb30837d2d316cc3e5c70ed30d91c53bf4b63e0`
- Closure SHA256: `aa5b7949cd0c76bb324edde55d5209e0fbf8447b9e00f45a0efa5850ce185063`
- Score schema: `goal052-outer-scores-v1`
- Created UTC: `2026-10-05T00:37:35.332121+00:00`

## Interpretation and support

Means and medians are equal-target summaries of the supplied score JSON. Every numeric cell carries its evaluated denominator; `NA` is retained when the source has no reportable value. The fixed ensemble is a fixed 50:50 probability average and is AUC-only and exploratory; no threshold metrics are assigned to it.

## Primary common73 panel

Panel target count: `73`; equal-region macro means are target-wise means of the supplied regional contrasts.

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | -0.000396021 (n=73/73) | -0.000565018 (n=73/73) | 34/73/73 | consistent nonpositive direction |
| Full fine-tune − target + q linear ResMLP | -6.17657e-05 (n=73/73) | -0.000883608 (n=73/73) | 34/73/73 | consistent nonpositive direction |
| Full fine-tune − Goal051 selected conventional | 0.00277052 (n=73/73) | 0.00171668 (n=73/73) | 39/73/73 | consistent positive direction |
| Full fine-tune − Goal051 q-augmented conventional | 0.00208153 (n=73/73) | 0.00255828 (n=73/73) | 44/73/73 | consistent positive direction |
| Frozen trunk − target-only random-init ResMLP | -0.00177428 (n=73/73) | -0.00331977 (n=73/73) | 31/73/73 | consistent nonpositive direction |
| Full fine-tune − frozen trunk | 0.00137826 (n=73/73) | 6.98701e-05 (n=73/73) | 38/73/73 | consistent positive direction |

## Primary contrasts by region

### NCP (primary panel; target count 73)

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | 0.00635009 (n=73/73) | 0.00814361 (n=73/73) | 44/73/73 | consistent positive direction |
| Full fine-tune − target + q linear ResMLP | 0.00786559 (n=73/73) | 0.00690477 (n=73/73) | 42/73/73 | consistent positive direction |
| Full fine-tune − Goal051 selected conventional | 0.007797 (n=73/73) | 0.00476311 (n=73/73) | 41/73/73 | consistent positive direction |
| Full fine-tune − Goal051 q-augmented conventional | 0.00672945 (n=73/73) | 0.00304106 (n=73/73) | 43/73/73 | consistent positive direction |
| Frozen trunk − target-only random-init ResMLP | 0.00567779 (n=73/73) | 0.00237786 (n=73/73) | 40/73/73 | consistent positive direction |
| Full fine-tune − frozen trunk | 0.000672291 (n=73/73) | 0.00184766 (n=73/73) | 38/73/73 | consistent positive direction |

### NNC (primary panel; target count 73)

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | -0.00353885 (n=73/73) | -0.00393276 (n=73/73) | 31/73/73 | consistent nonpositive direction |
| Full fine-tune − target + q linear ResMLP | -0.00301019 (n=73/73) | -0.00540708 (n=73/73) | 26/73/73 | consistent nonpositive direction |
| Full fine-tune − Goal051 selected conventional | 0.0075665 (n=73/73) | 0.00630429 (n=73/73) | 49/73/73 | consistent positive direction |
| Full fine-tune − Goal051 q-augmented conventional | 0.00792203 (n=73/73) | 0.00712466 (n=73/73) | 49/73/73 | consistent positive direction |
| Frozen trunk − target-only random-init ResMLP | -0.00309194 (n=73/73) | -0.00624995 (n=73/73) | 32/73/73 | consistent nonpositive direction |
| Full fine-tune − frozen trunk | -0.00044691 (n=73/73) | 4.81954e-05 (n=73/73) | 37/73/73 | mixed direction |

### SEH (primary panel; target count 73)

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | -0.0039993 (n=73/73) | 0.0021029 (n=73/73) | 41/73/73 | mixed direction |
| Full fine-tune − target + q linear ResMLP | -0.0050407 (n=73/73) | -0.00130829 (n=73/73) | 35/73/73 | consistent nonpositive direction |
| Full fine-tune − Goal051 selected conventional | -0.00705194 (n=73/73) | -0.000901887 (n=73/73) | 36/73/73 | consistent nonpositive direction |
| Full fine-tune − Goal051 q-augmented conventional | -0.0084069 (n=73/73) | -0.00079545 (n=73/73) | 35/73/73 | consistent nonpositive direction |
| Frozen trunk − target-only random-init ResMLP | -0.0079087 (n=73/73) | -0.000350768 (n=73/73) | 36/73/73 | consistent nonpositive direction |
| Full fine-tune − frozen trunk | 0.0039094 (n=73/73) | -0.00110024 (n=73/73) | 34/73/73 | mixed direction |

## Fixed ensemble diagnostic contrasts

These registered ensemble contrasts are exploratory AUC diagnostics. The fixed ensemble has no threshold metrics and these differences do not support inferential or mechanistic claims.

#### Common73

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Fixed ensemble − full fine-tune | 0.0075817 (n=73/73) | 0.00763402 (n=73/73) | 56/73/73 | consistent positive direction |
| Fixed ensemble − selected conventional | 0.0103522 (n=73/73) | 0.00876712 (n=73/73) | 60/73/73 | consistent positive direction |

#### NCP primary panel

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Fixed ensemble − full fine-tune | 0.00667506 (n=73/73) | 0.00382615 (n=73/73) | 46/73/73 | consistent positive direction |
| Fixed ensemble − selected conventional | 0.0144721 (n=73/73) | 0.0103838 (n=73/73) | 55/73/73 | consistent positive direction |

#### NNC primary panel

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Fixed ensemble − full fine-tune | 0.00413835 (n=73/73) | 0.00334588 (n=73/73) | 48/73/73 | consistent positive direction |
| Fixed ensemble − selected conventional | 0.0117048 (n=73/73) | 0.00846852 (n=73/73) | 63/73/73 | consistent positive direction |

#### SEH primary panel

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Fixed ensemble − full fine-tune | 0.0119317 (n=73/73) | 0.00789876 (n=73/73) | 54/73/73 | consistent positive direction |
| Fixed ensemble − selected conventional | 0.00487975 (n=73/73) | 0.00682893 (n=73/73) | 48/73/73 | consistent positive direction |

## Absolute learner performance on common73

AUC is shown for all six learners and the fixed ensemble. TSS, balanced accuracy, MCC, sensitivity, specificity, and prevalence use the frozen fixed thresholds and are shown for the six learners only. Support is `evaluated / panel target count`.

| Learner | AUC | TSS | Balanced accuracy | MCC | Sensitivity | Specificity | Prevalence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Target only, random-init ResMLP | 0.683128 (n=73/73) | 0.191966 (n=73/73) | 0.595983 (n=73/73) | 0.166736 (n=73/73) | 0.605323 (n=73/73) | 0.586643 (n=73/73) | 0.26331 (n=73/73) |
| Target + q linear ResMLP | 0.682794 (n=73/73) | 0.193059 (n=73/73) | 0.596529 (n=73/73) | 0.168732 (n=73/73) | 0.610876 (n=73/73) | 0.582183 (n=73/73) | 0.26331 (n=73/73) |
| Multihead, frozen trunk | 0.681354 (n=73/73) | 0.19713 (n=73/73) | 0.598565 (n=73/73) | 0.170903 (n=73/73) | 0.624172 (n=73/73) | 0.572958 (n=73/73) | 0.26331 (n=73/73) |
| Multihead, full fine-tune | 0.682732 (n=73/73) | 0.201804 (n=73/73) | 0.600902 (n=73/73) | 0.173634 (n=73/73) | 0.615751 (n=73/73) | 0.586053 (n=73/73) | 0.26331 (n=73/73) |
| Goal051 selected conventional | 0.679962 (n=73/73) | 0.190104 (n=73/73) | 0.595052 (n=73/73) | 0.161736 (n=73/73) | 0.621112 (n=73/73) | 0.568992 (n=73/73) | 0.26331 (n=73/73) |
| Goal051 q-augmented conventional | 0.680651 (n=73/73) | 0.191416 (n=73/73) | 0.595708 (n=73/73) | 0.16261 (n=73/73) | 0.623523 (n=73/73) | 0.567893 (n=73/73) | 0.26331 (n=73/73) |
| Fixed ensemble (AUC-only) | 0.690314 (n=73/73) | AUC-only | AUC-only | AUC-only | AUC-only | AUC-only | AUC-only |

## Secondary regional panels

These panels retain their exact supplied membership counts; their denominators are not substituted with the common73 count.

### NCP (target count 88)

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | 0.00891161 (n=88/88) | 0.00840836 (n=88/88) | 53/88/88 | consistent positive direction |
| Full fine-tune − target + q linear ResMLP | 0.0101309 (n=88/88) | 0.00715723 (n=88/88) | 50/88/88 | consistent positive direction |
| Full fine-tune − Goal051 selected conventional | 0.00686261 (n=88/88) | 0.00361118 (n=88/88) | 47/88/88 | consistent positive direction |
| Full fine-tune − Goal051 q-augmented conventional | 0.00590202 (n=88/88) | 0.00295598 (n=88/88) | 50/88/88 | consistent positive direction |
| Frozen trunk − target-only random-init ResMLP | 0.0110582 (n=88/88) | 0.00579377 (n=88/88) | 51/88/88 | consistent positive direction |
| Full fine-tune − frozen trunk | -0.00214658 (n=88/88) | -0.000492711 (n=88/88) | 43/88/88 | consistent nonpositive direction |

### NNC (target count 134)

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | -0.00502298 (n=134/134) | -0.00414869 (n=134/134) | 52/134/134 | consistent nonpositive direction |
| Full fine-tune − target + q linear ResMLP | -0.00349169 (n=134/134) | -0.00712385 (n=134/134) | 49/134/134 | consistent nonpositive direction |
| Full fine-tune − Goal051 selected conventional | 0.00372972 (n=134/134) | 0.0016556 (n=134/134) | 74/134/134 | consistent positive direction |
| Full fine-tune − Goal051 q-augmented conventional | 0.00442301 (n=134/134) | 0.00312814 (n=134/134) | 74/134/134 | consistent positive direction |
| Frozen trunk − target-only random-init ResMLP | -0.00407618 (n=134/134) | -0.00737868 (n=134/134) | 52/134/134 | consistent nonpositive direction |
| Full fine-tune − frozen trunk | -0.000946803 (n=134/134) | 0.00017811 (n=134/134) | 69/134/134 | mixed direction |

### SEH (target count 122)

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | -0.00122843 (n=122/122) | 0.00213339 (n=122/122) | 67/122/122 | mixed direction |
| Full fine-tune − target + q linear ResMLP | -0.0015762 (n=122/122) | 0.000559781 (n=122/122) | 62/122/122 | mixed direction |
| Full fine-tune − Goal051 selected conventional | -0.0105997 (n=122/122) | -0.0011109 (n=122/122) | 60/122/122 | consistent nonpositive direction |
| Full fine-tune − Goal051 q-augmented conventional | -0.0115111 (n=122/122) | -0.00138365 (n=122/122) | 59/122/122 | consistent nonpositive direction |
| Frozen trunk − target-only random-init ResMLP | -0.00109417 (n=122/122) | 0.00133575 (n=122/122) | 62/122/122 | mixed direction |
| Full fine-tune − frozen trunk | -0.000134262 (n=122/122) | -0.00250303 (n=122/122) | 55/122/122 | consistent nonpositive direction |

## X20 sensitivity panel

The main X20 macro gives each region equal weight after using its own eligible target denominator (the expected pattern is 72/73/73). The three-region common intersection is supplementary and is reported separately.

| Contrast | Equal-region macro | NCP | SEH | NNC |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | -0.00202185 | 0.00629412 (n=72) | -0.00824619 (n=73) | -0.00411348 (n=73) |
| Full fine-tune − target + q linear ResMLP | -0.00204249 | 0.00822697 (n=72) | -0.00985268 (n=73) | -0.00450175 (n=73) |
| Full fine-tune − Goal051 selected conventional | 0.00214798 | 0.0116596 (n=72) | -0.00912221 (n=73) | 0.0039065 (n=73) |
| Full fine-tune − Goal051 q-augmented conventional | 0.00189903 | 0.0109325 (n=72) | -0.00925782 (n=73) | 0.00402239 (n=73) |
| Frozen trunk − target-only random-init ResMLP | -0.00458191 | 0.00530096 (n=72) | -0.0151617 (n=73) | -0.00388497 (n=73) |
| Full fine-tune − frozen trunk | 0.00256006 | 0.000993158 (n=72) | 0.00691552 (n=73) | -0.000228506 (n=73) |

### Supplementary common three-region intersection

Regions: `NCP, SEH, NNC`; target count: `73`. These values use the common intersection and are supplementary to the main region-specific macro.

| Contrast | Mean (support) | Median (support) | Positive / denominator | Descriptive label |
| --- | --- | --- | --- | --- |
| Full fine-tune − target-only random-init ResMLP | -0.00210092 (n=72/73) | -0.00202791 (n=72/73) | 30/72/73 | consistent nonpositive direction |
| Full fine-tune − target + q linear ResMLP | -0.00211058 (n=72/73) | -0.00366439 (n=72/73) | 32/72/73 | consistent nonpositive direction |
| Full fine-tune − Goal051 selected conventional | 0.00165983 (n=72/73) | 0.0015759 (n=72/73) | 38/72/73 | consistent positive direction |
| Full fine-tune − Goal051 q-augmented conventional | 0.00140806 (n=72/73) | 0.00252767 (n=72/73) | 39/72/73 | consistent positive direction |
| Frozen trunk − target-only random-init ResMLP | -0.00458904 (n=72/73) | -0.00646606 (n=72/73) | 29/72/73 | consistent nonpositive direction |
| Full fine-tune − frozen trunk | 0.00248812 (n=72/73) | 0.00204717 (n=72/73) | 38/72/73 | consistent positive direction |

## Recorded-richness diagnostics

Background counts are target-background pairs. Shares are mean target shares for the equally weighted target panel. Common support requires all three richness bins for the contrast; all-available support uses each bin's available targets. These are descriptive diagnostics of the retained-inner discovery prospect and do not identify ecological versus observation mechanisms.

### NCP primary panel

| Bin | Background count / share | Contrast | Common support mean | All-available mean |
| --- | --- | --- | --- | --- |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Full fine-tune − target-only random-init ResMLP | NA (n=0/73) | 0.0071541 (n=73/73) |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Full fine-tune − target + q linear ResMLP | NA (n=0/73) | 0.00844944 (n=73/73) |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Full fine-tune − Goal051 selected conventional | NA (n=0/73) | 0.00627603 (n=73/73) |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Full fine-tune − Goal051 q-augmented conventional | NA (n=0/73) | 0.00508831 (n=73/73) |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Frozen trunk − target-only random-init ResMLP | NA (n=0/73) | 0.00699396 (n=73/73) |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Full fine-tune − frozen trunk | NA (n=0/73) | 0.000160143 (n=73/73) |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Fixed ensemble − full fine-tune | NA (n=0/73) | 0.00748044 (n=73/73) |
| 10_24 | 72950 pairs; mean=999.315; share=0.62206 | Fixed ensemble − selected conventional | NA (n=0/73) | 0.0137565 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Full fine-tune − target-only random-init ResMLP | NA (n=0/73) | 0.0061516 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Full fine-tune − target + q linear ResMLP | NA (n=0/73) | 0.00793157 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Full fine-tune − Goal051 selected conventional | NA (n=0/73) | 0.0128553 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Full fine-tune − Goal051 q-augmented conventional | NA (n=0/73) | 0.011379 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Frozen trunk − target-only random-init ResMLP | NA (n=0/73) | 0.00434902 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Full fine-tune − frozen trunk | NA (n=0/73) | 0.00180259 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Fixed ensemble − full fine-tune | NA (n=0/73) | 0.00444449 (n=73/73) |
| 25_99 | 47535 pairs; mean=651.164; share=0.375153 | Fixed ensemble − selected conventional | NA (n=0/73) | 0.0172998 (n=73/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Full fine-tune − target-only random-init ResMLP | NA (n=0/73) | NA (n=0/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Full fine-tune − target + q linear ResMLP | NA (n=0/73) | NA (n=0/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Full fine-tune − Goal051 selected conventional | NA (n=0/73) | NA (n=0/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Full fine-tune − Goal051 q-augmented conventional | NA (n=0/73) | NA (n=0/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Frozen trunk − target-only random-init ResMLP | NA (n=0/73) | NA (n=0/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Full fine-tune − frozen trunk | NA (n=0/73) | NA (n=0/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Fixed ensemble − full fine-tune | NA (n=0/73) | NA (n=0/73) |
| 100_plus | 386 pairs; mean=5.28767; share=0.00278699 | Fixed ensemble − selected conventional | NA (n=0/73) | NA (n=0/73) |

### NNC primary panel

| Bin | Background count / share | Contrast | Common support mean | All-available mean |
| --- | --- | --- | --- | --- |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Full fine-tune − target-only random-init ResMLP | 0.0004612 (n=55/73) | -0.00235674 (n=73/73) |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Full fine-tune − target + q linear ResMLP | 0.00357007 (n=55/73) | -0.000240031 (n=73/73) |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Full fine-tune − Goal051 selected conventional | 0.0147753 (n=55/73) | 0.0125718 (n=73/73) |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Full fine-tune − Goal051 q-augmented conventional | 0.0151003 (n=55/73) | 0.0131663 (n=73/73) |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Frozen trunk − target-only random-init ResMLP | 0.00190354 (n=55/73) | -0.00155457 (n=73/73) |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Full fine-tune − frozen trunk | -0.00144234 (n=55/73) | -0.000802169 (n=73/73) |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Fixed ensemble − full fine-tune | 0.000424801 (n=55/73) | 0.0010234 (n=73/73) |
| 10_24 | 183578 pairs; mean=2514.77; share=0.497439 | Fixed ensemble − selected conventional | 0.0152001 (n=55/73) | 0.0135952 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Full fine-tune − target-only random-init ResMLP | -0.00114252 (n=55/73) | -0.00389101 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Full fine-tune − target + q linear ResMLP | -0.00105233 (n=55/73) | -0.00458629 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Full fine-tune − Goal051 selected conventional | 0.00602176 (n=55/73) | 0.00379224 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Full fine-tune − Goal051 q-augmented conventional | 0.0062461 (n=55/73) | 0.00392794 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Frozen trunk − target-only random-init ResMLP | 0.000143186 (n=55/73) | -0.00365836 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Full fine-tune − frozen trunk | -0.0012857 (n=55/73) | -0.000232646 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Fixed ensemble − full fine-tune | 0.00588059 (n=55/73) | 0.00656945 (n=73/73) |
| 25_99 | 189996 pairs; mean=2602.68; share=0.474845 | Fixed ensemble − selected conventional | 0.0119023 (n=55/73) | 0.0103617 (n=73/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Full fine-tune − target-only random-init ResMLP | -0.0166712 (n=55/73) | -0.0166712 (n=55/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Full fine-tune − target + q linear ResMLP | -0.0220658 (n=55/73) | -0.0220658 (n=55/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Full fine-tune − Goal051 selected conventional | -0.0258708 (n=55/73) | -0.0258708 (n=55/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Full fine-tune − Goal051 q-augmented conventional | -0.0272767 (n=55/73) | -0.0272767 (n=55/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Frozen trunk − target-only random-init ResMLP | -0.0194926 (n=55/73) | -0.0194926 (n=55/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Full fine-tune − frozen trunk | 0.0028214 (n=55/73) | 0.0028214 (n=55/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Fixed ensemble − full fine-tune | 0.022253 (n=55/73) | 0.022253 (n=55/73) |
| 100_plus | 12829 pairs; mean=175.74; share=0.0277157 | Fixed ensemble − selected conventional | -0.00361773 (n=55/73) | -0.00361773 (n=55/73) |

### SEH primary panel

| Bin | Background count / share | Contrast | Common support mean | All-available mean |
| --- | --- | --- | --- | --- |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Full fine-tune − target-only random-init ResMLP | 0.00183964 (n=38/73) | -1.56658e-05 (n=73/73) |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Full fine-tune − target + q linear ResMLP | -0.000717103 (n=38/73) | -0.000545627 (n=73/73) |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Full fine-tune − Goal051 selected conventional | -0.00380756 (n=38/73) | -0.00403078 (n=73/73) |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Full fine-tune − Goal051 q-augmented conventional | -0.00933178 (n=38/73) | -0.00664232 (n=73/73) |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Frozen trunk − target-only random-init ResMLP | 0.00189833 (n=38/73) | -0.000587913 (n=73/73) |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Full fine-tune − frozen trunk | -5.86913e-05 (n=38/73) | 0.000572247 (n=73/73) |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Fixed ensemble − full fine-tune | 0.0127001 (n=38/73) | 0.0110959 (n=73/73) |
| 10_24 | 363767 pairs; mean=4983.11; share=0.579879 | Fixed ensemble − selected conventional | 0.00889259 (n=38/73) | 0.00706513 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Full fine-tune − target-only random-init ResMLP | -0.00774618 (n=38/73) | -0.00969248 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Full fine-tune − target + q linear ResMLP | -0.0109368 (n=38/73) | -0.0115721 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Full fine-tune − Goal051 selected conventional | -0.0139508 (n=38/73) | -0.0105491 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Full fine-tune − Goal051 q-augmented conventional | -0.0157008 (n=38/73) | -0.0104027 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Frozen trunk − target-only random-init ResMLP | -0.0161477 (n=38/73) | -0.0175484 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Full fine-tune − frozen trunk | 0.00840148 (n=38/73) | 0.00785596 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Fixed ensemble − full fine-tune | 0.0157105 (n=38/73) | 0.0131661 (n=73/73) |
| 25_99 | 290813 pairs; mean=3983.74; share=0.41401 | Fixed ensemble − selected conventional | 0.00175976 (n=38/73) | 0.00261701 (n=73/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Full fine-tune − target-only random-init ResMLP | -0.0255902 (n=38/73) | -0.0255902 (n=38/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Full fine-tune − target + q linear ResMLP | -0.028327 (n=38/73) | -0.028327 (n=38/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Full fine-tune − Goal051 selected conventional | -0.0282644 (n=38/73) | -0.0282644 (n=38/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Full fine-tune − Goal051 q-augmented conventional | -0.0231935 (n=38/73) | -0.0231935 (n=38/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Frozen trunk − target-only random-init ResMLP | -0.0535884 (n=38/73) | -0.0535884 (n=38/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Full fine-tune − frozen trunk | 0.0279982 (n=38/73) | 0.0279982 (n=38/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Fixed ensemble − full fine-tune | 0.016407 (n=38/73) | 0.016407 (n=38/73) |
| 100_plus | 5069 pairs; mean=69.4384; share=0.00611167 | Fixed ensemble − selected conventional | -0.0118574 (n=38/73) | -0.0118574 (n=38/73) |

### Supplementary three-region macro

| Bin | Background count / share | Contrast | Common support mean | All-available mean |
| --- | --- | --- | --- | --- |
| 10_24 | NA pairs; mean=NA; share=NA | Full fine-tune − target-only random-init ResMLP | NA (n=0/73) | 0.0015939 (n=73/73) |
| 10_24 | NA pairs; mean=NA; share=NA | Full fine-tune − target + q linear ResMLP | NA (n=0/73) | 0.00255459 (n=73/73) |
| 10_24 | NA pairs; mean=NA; share=NA | Full fine-tune − Goal051 selected conventional | NA (n=0/73) | 0.00493902 (n=73/73) |
| 10_24 | NA pairs; mean=NA; share=NA | Full fine-tune − Goal051 q-augmented conventional | NA (n=0/73) | 0.00387075 (n=73/73) |
| 10_24 | NA pairs; mean=NA; share=NA | Frozen trunk − target-only random-init ResMLP | NA (n=0/73) | 0.00161716 (n=73/73) |
| 10_24 | NA pairs; mean=NA; share=NA | Full fine-tune − frozen trunk | NA (n=0/73) | -2.32595e-05 (n=73/73) |
| 10_24 | NA pairs; mean=NA; share=NA | Fixed ensemble − full fine-tune | NA (n=0/73) | 0.00653325 (n=73/73) |
| 10_24 | NA pairs; mean=NA; share=NA | Fixed ensemble − selected conventional | NA (n=0/73) | 0.0114723 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Full fine-tune − target-only random-init ResMLP | NA (n=0/73) | -0.0024773 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Full fine-tune − target + q linear ResMLP | NA (n=0/73) | -0.00274226 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Full fine-tune − Goal051 selected conventional | NA (n=0/73) | 0.00203282 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Full fine-tune − Goal051 q-augmented conventional | NA (n=0/73) | 0.00163475 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Frozen trunk − target-only random-init ResMLP | NA (n=0/73) | -0.00561926 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Full fine-tune − frozen trunk | NA (n=0/73) | 0.00314197 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Fixed ensemble − full fine-tune | NA (n=0/73) | 0.00806003 (n=73/73) |
| 25_99 | NA pairs; mean=NA; share=NA | Fixed ensemble − selected conventional | NA (n=0/73) | 0.0100928 (n=73/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Full fine-tune − target-only random-init ResMLP | NA (n=0/73) | NA (n=0/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Full fine-tune − target + q linear ResMLP | NA (n=0/73) | NA (n=0/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Full fine-tune − Goal051 selected conventional | NA (n=0/73) | NA (n=0/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Full fine-tune − Goal051 q-augmented conventional | NA (n=0/73) | NA (n=0/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Frozen trunk − target-only random-init ResMLP | NA (n=0/73) | NA (n=0/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Full fine-tune − frozen trunk | NA (n=0/73) | NA (n=0/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Fixed ensemble − full fine-tune | NA (n=0/73) | NA (n=0/73) |
| 100_plus | NA pairs; mean=NA; share=NA | Fixed ensemble − selected conventional | NA (n=0/73) | NA (n=0/73) |

## Headline decomposition

These are the scorer's mechanical equal-target decomposition terms, including sparse richness bins. They are arithmetic diagnostics rather than separate reportable bin AUC claims.

| Panel | Region | Contrast | 10–24 contribution | 25–99 contribution | 100+ contribution | Sum | Absolute error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| primary by region | NCP | Full fine-tune − target-only random-init ResMLP | 0.00419976 | 0.00213309 | 1.72353e-05 | 0.00635009 | 6.93889e-18 |
| primary by region | NCP | Full fine-tune − target + q linear ResMLP | 0.00488355 | 0.00293071 | 5.13325e-05 | 0.00786559 | 3.46945e-18 |
| primary by region | NCP | Full fine-tune − Goal051 selected conventional | 0.00390375 | 0.00389564 | -2.39465e-06 | 0.007797 | 6.93889e-18 |
| primary by region | NCP | Full fine-tune − Goal051 q-augmented conventional | 0.00293617 | 0.00378624 | 7.03424e-06 | 0.00672945 | 2.60209e-18 |
| primary by region | NCP | Frozen trunk − target-only random-init ResMLP | 0.00401895 | 0.00161331 | 4.55348e-05 | 0.00567779 | 8.67362e-19 |
| primary by region | NCP | Full fine-tune − frozen trunk | 0.000180811 | 0.000519779 | -2.82994e-05 | 0.000672291 | 7.48099e-18 |
| primary by region | NCP | Fixed ensemble − full fine-tune | 0.00455891 | 0.00207465 | 4.15061e-05 | 0.00667506 | 1.73472e-18 |
| primary by region | NCP | Fixed ensemble − selected conventional | 0.00846266 | 0.00597029 | 3.91114e-05 | 0.0144721 | 1.73472e-18 |
| primary by region | NNC | Full fine-tune − target-only random-init ResMLP | -0.00135452 | -0.00169034 | -0.000493986 | -0.00353885 | 6.93889e-18 |
| primary by region | NNC | Full fine-tune − target + q linear ResMLP | -0.000485332 | -0.00187311 | -0.000651743 | -0.00301019 | 9.1073e-18 |
| primary by region | NNC | Full fine-tune − Goal051 selected conventional | 0.00608067 | 0.00205225 | -0.000566422 | 0.0075665 | 8.67362e-18 |
| primary by region | NNC | Full fine-tune − Goal051 q-augmented conventional | 0.00635704 | 0.00216308 | -0.000598098 | 0.00792203 | 1.56125e-17 |
| primary by region | NNC | Frozen trunk − target-only random-init ResMLP | -0.00112578 | -0.00141382 | -0.000552338 | -0.00309194 | 8.67362e-18 |
| primary by region | NNC | Full fine-tune − frozen trunk | -0.000228741 | -0.000276521 | 5.8352e-05 | -0.00044691 | 2.38524e-18 |
| primary by region | NNC | Fixed ensemble − full fine-tune | 0.000514405 | 0.00303079 | 0.000593154 | 0.00413835 | 1.04083e-17 |
| primary by region | NNC | Fixed ensemble − selected conventional | 0.00659507 | 0.00508304 | 2.67316e-05 | 0.0117048 | 0 |
| primary by region | SEH | Full fine-tune − target-only random-init ResMLP | -3.7034e-05 | -0.00389401 | -6.82591e-05 | -0.0039993 | 2.1684e-17 |
| primary by region | SEH | Full fine-tune − target + q linear ResMLP | -0.000266883 | -0.00469371 | -8.01102e-05 | -0.0050407 | 1.38778e-17 |
| primary by region | SEH | Full fine-tune − Goal051 selected conventional | -0.00210309 | -0.00493585 | -1.30061e-05 | -0.00705194 | 2.60209e-18 |
| primary by region | SEH | Full fine-tune − Goal051 q-augmented conventional | -0.00338745 | -0.00502178 | 2.33041e-06 | -0.0084069 | 1.04083e-17 |
| primary by region | SEH | Frozen trunk − target-only random-init ResMLP | -0.000470865 | -0.00716206 | -0.000275767 | -0.0079087 | 1.73472e-18 |
| primary by region | SEH | Full fine-tune − frozen trunk | 0.000433831 | 0.00326806 | 0.000207508 | 0.0039094 | 2.08167e-17 |
| primary by region | SEH | Fixed ensemble − full fine-tune | 0.00612266 | 0.0058005 | 8.53388e-06 | 0.0119317 | 1.04083e-17 |
| primary by region | SEH | Fixed ensemble − selected conventional | 0.00401957 | 0.000864652 | -4.4722e-06 | 0.00487975 | 1.38778e-17 |
| regional | NCP | Full fine-tune − target-only random-init ResMLP | 0.00538412 | 0.00350278 | 2.47128e-05 | 0.00891161 | 1.73472e-18 |
| regional | NCP | Full fine-tune − target + q linear ResMLP | 0.00618347 | 0.00390641 | 4.10423e-05 | 0.0101309 | 3.46945e-18 |
| regional | NCP | Full fine-tune − Goal051 selected conventional | 0.00361638 | 0.00327049 | -2.42628e-05 | 0.00686261 | 7.80626e-18 |
| regional | NCP | Full fine-tune − Goal051 q-augmented conventional | 0.00272553 | 0.00317998 | -3.48818e-06 | 0.00590202 | 8.67362e-19 |
| regional | NCP | Frozen trunk − target-only random-init ResMLP | 0.00677722 | 0.00420276 | 7.82078e-05 | 0.0110582 | 1.73472e-18 |
| regional | NCP | Full fine-tune − frozen trunk | -0.0013931 | -0.000699986 | -5.3495e-05 | -0.00214658 | 4.33681e-18 |
| regional | NCP | Fixed ensemble − full fine-tune | 0.00427264 | 0.00213022 | 5.27884e-05 | 0.00645565 | 3.46945e-18 |
| regional | NCP | Fixed ensemble − selected conventional | 0.00788902 | 0.00540071 | 2.85256e-05 | 0.0133183 | 1.73472e-18 |
| regional | NNC | Full fine-tune − target-only random-init ResMLP | -0.00256284 | -0.00196334 | -0.000496802 | -0.00502298 | 1.04083e-17 |
| regional | NNC | Full fine-tune − target + q linear ResMLP | -0.00125752 | -0.00159631 | -0.000637858 | -0.00349169 | 7.80626e-18 |
| regional | NNC | Full fine-tune − Goal051 selected conventional | 0.00294054 | 0.00128332 | -0.000494136 | 0.00372972 | 6.50521e-18 |
| regional | NNC | Full fine-tune − Goal051 q-augmented conventional | 0.00340749 | 0.00154157 | -0.000526049 | 0.00442301 | 9.54098e-18 |
| regional | NNC | Frozen trunk − target-only random-init ResMLP | -0.00231893 | -0.00133273 | -0.000424516 | -0.00407618 | 8.67362e-18 |
| regional | NNC | Full fine-tune − frozen trunk | -0.000243915 | -0.000630602 | -7.22854e-05 | -0.000946803 | 2.05998e-18 |
| regional | NNC | Fixed ensemble − full fine-tune | 0.00198705 | 0.00366984 | 0.0005889 | 0.00624579 | 6.93889e-18 |
| regional | NNC | Fixed ensemble − selected conventional | 0.00492758 | 0.00495316 | 9.47639e-05 | 0.00997551 | 1.73472e-18 |
| regional | SEH | Full fine-tune − target-only random-init ResMLP | 0.00165752 | -0.00274899 | -0.000136958 | -0.00122843 | 6.72205e-18 |
| regional | SEH | Full fine-tune − target + q linear ResMLP | 0.00197932 | -0.00338627 | -0.000169253 | -0.0015762 | 1.95156e-18 |
| regional | SEH | Full fine-tune − Goal051 selected conventional | -0.00337319 | -0.00691991 | -0.000306636 | -0.0105997 | 1.73472e-17 |
| regional | SEH | Full fine-tune − Goal051 q-augmented conventional | -0.00431104 | -0.00692086 | -0.000279196 | -0.0115111 | 0 |
| regional | SEH | Frozen trunk − target-only random-init ResMLP | 0.00327569 | -0.00407732 | -0.000292532 | -0.00109417 | 5.85469e-18 |
| regional | SEH | Full fine-tune − frozen trunk | -0.00161816 | 0.00132833 | 0.000155574 | -0.000134262 | 1.81604e-18 |
| regional | SEH | Fixed ensemble − full fine-tune | 0.00827023 | 0.00900316 | 0.000254892 | 0.0175283 | 6.93889e-18 |
| regional | SEH | Fixed ensemble − selected conventional | 0.00489704 | 0.00208325 | -5.17446e-05 | 0.00692855 | 8.67362e-18 |

## Matched inner attenuation

Outer-minus-inner differences compare the supplied outer contrasts with the accepted matched inner target100/full differences. They are descriptive attenuation summaries, not recalibration or causal effects.

| Panel | Contrast | Inner mean | Outer mean | Outer − inner | Targets |
| --- | --- | --- | --- | --- | --- |
| common73 equal-region macro | Full fine-tune − target-only random-init ResMLP | 0.00578075 | -0.000396021 | -0.00617677 | 73 |
| common73 equal-region macro | Full fine-tune − target + q linear ResMLP | 0.00577174 | -6.17657e-05 | -0.0058335 | 73 |
| common73 equal-region macro | Full fine-tune − Goal051 selected conventional | 0.00338986 | 0.00277052 | -0.000619341 | 73 |
| common73 equal-region macro | Full fine-tune − Goal051 q-augmented conventional | 0.00300841 | 0.00208153 | -0.00092688 | 73 |
| common73 equal-region macro | Frozen trunk − target-only random-init ResMLP | 0.00219672 | -0.00177428 | -0.003971 | 73 |
| common73 equal-region macro | Full fine-tune − frozen trunk | 0.00358403 | 0.00137826 | -0.00220577 | 73 |
| primary by region / NCP | Full fine-tune − target-only random-init ResMLP | 0.00578075 | 0.00635009 | 0.000569335 | 73 |
| primary by region / NCP | Full fine-tune − target + q linear ResMLP | 0.00577174 | 0.00786559 | 0.00209386 | 73 |
| primary by region / NCP | Full fine-tune − Goal051 selected conventional | 0.00338986 | 0.007797 | 0.00440714 | 73 |
| primary by region / NCP | Full fine-tune − Goal051 q-augmented conventional | 0.00300841 | 0.00672945 | 0.00372104 | 73 |
| primary by region / NCP | Frozen trunk − target-only random-init ResMLP | 0.00219672 | 0.00567779 | 0.00348107 | 73 |
| primary by region / NCP | Full fine-tune − frozen trunk | 0.00358403 | 0.000672291 | -0.00291174 | 73 |
| primary by region / NNC | Full fine-tune − target-only random-init ResMLP | 0.00578075 | -0.00353885 | -0.0093196 | 73 |
| primary by region / NNC | Full fine-tune − target + q linear ResMLP | 0.00577174 | -0.00301019 | -0.00878193 | 73 |
| primary by region / NNC | Full fine-tune − Goal051 selected conventional | 0.00338986 | 0.0075665 | 0.00417664 | 73 |
| primary by region / NNC | Full fine-tune − Goal051 q-augmented conventional | 0.00300841 | 0.00792203 | 0.00491362 | 73 |
| primary by region / NNC | Frozen trunk − target-only random-init ResMLP | 0.00219672 | -0.00309194 | -0.00528866 | 73 |
| primary by region / NNC | Full fine-tune − frozen trunk | 0.00358403 | -0.00044691 | -0.00403094 | 73 |
| primary by region / SEH | Full fine-tune − target-only random-init ResMLP | 0.00578075 | -0.0039993 | -0.00978005 | 73 |
| primary by region / SEH | Full fine-tune − target + q linear ResMLP | 0.00577174 | -0.0050407 | -0.0108124 | 73 |
| primary by region / SEH | Full fine-tune − Goal051 selected conventional | 0.00338986 | -0.00705194 | -0.0104418 | 73 |
| primary by region / SEH | Full fine-tune − Goal051 q-augmented conventional | 0.00300841 | -0.0084069 | -0.0114153 | 73 |
| primary by region / SEH | Frozen trunk − target-only random-init ResMLP | 0.00219672 | -0.0079087 | -0.0101054 | 73 |
| primary by region / SEH | Full fine-tune − frozen trunk | 0.00358403 | 0.0039094 | 0.00032537 | 73 |
| regional / NCP | Full fine-tune − target-only random-init ResMLP | 0.00591074 | 0.00891161 | 0.00300087 | 88 |
| regional / NCP | Full fine-tune − target + q linear ResMLP | 0.0057946 | 0.0101309 | 0.00433632 | 88 |
| regional / NCP | Full fine-tune − Goal051 selected conventional | 0.00318818 | 0.00686261 | 0.00367443 | 88 |
| regional / NCP | Full fine-tune − Goal051 q-augmented conventional | 0.00284388 | 0.00590202 | 0.00305814 | 88 |
| regional / NCP | Frozen trunk − target-only random-init ResMLP | 0.00264871 | 0.0110582 | 0.00840948 | 88 |
| regional / NCP | Full fine-tune − frozen trunk | 0.00326203 | -0.00214658 | -0.00540861 | 88 |
| regional / NNC | Full fine-tune − target-only random-init ResMLP | 0.00428981 | -0.00502298 | -0.00931279 | 134 |
| regional / NNC | Full fine-tune − target + q linear ResMLP | 0.00422151 | -0.00349169 | -0.0077132 | 134 |
| regional / NNC | Full fine-tune − Goal051 selected conventional | 0.00218575 | 0.00372972 | 0.00154397 | 134 |
| regional / NNC | Full fine-tune − Goal051 q-augmented conventional | 0.00201824 | 0.00442301 | 0.00240477 | 134 |
| regional / NNC | Frozen trunk − target-only random-init ResMLP | 0.00225179 | -0.00407618 | -0.00632797 | 134 |
| regional / NNC | Full fine-tune − frozen trunk | 0.00203802 | -0.000946803 | -0.00298482 | 134 |
| regional / SEH | Full fine-tune − target-only random-init ResMLP | 0.00516313 | -0.00122843 | -0.00639155 | 122 |
| regional / SEH | Full fine-tune − target + q linear ResMLP | 0.0050083 | -0.0015762 | -0.0065845 | 122 |
| regional / SEH | Full fine-tune − Goal051 selected conventional | 0.00239884 | -0.0105997 | -0.0129986 | 122 |
| regional / SEH | Full fine-tune − Goal051 q-augmented conventional | 0.00217584 | -0.0115111 | -0.0136869 | 122 |
| regional / SEH | Frozen trunk − target-only random-init ResMLP | 0.00273677 | -0.00109417 | -0.00383094 | 122 |
| regional / SEH | Full fine-tune − frozen trunk | 0.00242635 | -0.000134262 | -0.00256061 | 122 |

## Interpretive limits

- Threshold metrics use frozen inner-OOF thresholds; retained-full score-scale changes were not recalibrated on outer outcomes.
- Original fitted inner target states were not saved, so the identical-grid inner/full score-scale comparison is unavailable without additional replay fits.
- Presence versus effort-supported target-group background measures recording discrimination, not occupancy or verified absence.
- Recorded-richness diagnostics test a retained-inner discovery prospectively and do not identify ecological versus observation mechanisms.
- Species, regions and seeds are not iid replicates; descriptive sign labels are not significance, equivalence or practical-importance tests.

## Provenance note

This renderer preserves the score JSON's plan and closure identity in the report. It performs no fitting, response loading, threshold selection, recalculation, or data filtering.
