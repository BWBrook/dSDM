# Cross-case synthesis and manuscript revision — 5 October 2026

Multi-species pretraining gave a small, widespread inner bird AUC advantage, but that average advantage was absent in held-out bird regions. The mainland-to-Tasmania AUC comparison was also negative on average. The newly opened original Tasmania held-patch assessment favoured target-only learning for seven of eight species by AUC, while TSS more often favoured fine-tuning. The evidence therefore does not support consistent improvement across these settings or scoring metrics.

Barry authorised cross-case synthesis, manuscript restructuring and opening the original Tasmania test on 5 October. The original test was opened once after independent prediction-closure review, and scoring completed at **14:05:35 AEDT**. No models were fitted or tuned in this synthesis tranche. Historical accepted receipts and reports remain unchanged.

## Full-data AUC comparisons

FT denotes full multi-head fine-tuning. Each difference is paired within species; bird outer estimates first average the three regions within species. Original Tasmania outer estimates pool the held patches. These are different prediction settings, not independent replicates of one population effect.

| Assessment | Species | FT − target-only: mean | Median | Positive | FT − conventional: mean | Median | Positive |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tasmania inner | 8 | -0.0067 | -0.0027 | 4/8 | -0.0498 | -0.0390 | 0/8 |
| Tasmania held patches | 8 | -0.0147 | -0.0120 | 1/8 | -0.0051 | -0.0083 | 3/8 |
| Mainland to Tasmania | 5 | -0.0155 | +0.0269 | 3/5 | -0.0277 | -0.0224 | 1/5 |
| Birds inner: common 73 | 73 | +0.0058 | +0.0054 | 72/73 | +0.0034 | +0.0032 | 67/73 |
| Birds outer: equal regions | 73 | -0.0004 | -0.0006 | 34/73 | +0.0028 | +0.0017 | 39/73 |

## Original Tasmania held-patch assessment

The accepted 2,720 model artifacts scored 1,672 species–cell rows over 606 geographic cells. The new receipt retains eight species, seven target-data endpoints, six neural paths, five conventional families, the pooled held cells and five individual patches: 3,696 metric records and 2,016 co-primary contrasts. All thresholds and conventional selections came from frozen inner results.

At the full endpoint, equal-species mean AUC was **0.8390** for fine-tuning, **0.8537** for target-only, **0.8535** for the nonlinear scalar control and **0.8441** for selected conventional learning. The original protocol reports median species contrasts; these remain the headline below.

| Fine-tuning minus comparator | Median AUC difference | Positive species | Median TSS difference | Positive species |
|---|---:|---:|---:|---:|
| Target-only network | -0.0120 | 1/8 | +0.0205 | 5/8 |
| Nonlinear scalar control | -0.0144 | 2/8 | +0.0165 | 5/8 |
| Selected conventional | -0.0083 | 3/8 | -0.0262 | 4/8 |

TSS at the unchanged inner thresholds does not tell the same story as AUC. Mean fine-tuning minus target-only TSS was +0.0477. Against conventional learning its mean was +0.0260 but its median was −0.0262, with four of eight species positive. All full-data pooled metrics were defined. Of 40 species-by-patch combinations, 28 had both classes, eight had only one class and four were empty; the latter 12 retain counts and NA performance metrics at every endpoint.

This is a descriptive test of interpolation in touching, unbuffered patches. Zeros mix camera nondetection, survey absence and constructed pseudoabsence. The proposed pseudoabsence-removal sensitivity has not been completed, so robustness to zero provenance is not established.

## Reproduction of the bird extent check

Fable’s numerical extent result reproduces. Pooled whole-domain inner fine-tuning AUC is 0.832677; within named regions it is 0.691116, and within region-by-fold strata it is 0.689709. The last comparison gives fine-tuning minus target-only +0.007244, positive in 68/73 species, versus −0.000396 and 34/73 in the held regions. Published mean-fold AUC remains a separate estimate (0.831603).

The within-region pooled calculation uses 696 eligible species-by-region strata with at least 30 of each class. The region-by-fold calculation uses 2,650 strata with at least 20 of each class. Eligible strata receive equal weight within species, then species receive equal weight. The 360,625 retained cells outside the named regions contribute only to the whole-domain calculation.

The residual 0.00698 inner–outer difference is **not an identified geographic penalty**. Region composition, class support, weighting, the domain complement and fold-specific versus retained-full models also change. The useful result is that much lower regional AUC can occur without transferring a fitted model to a new region, while the inner pretraining contrast remains positive.

## Ensemble without pretraining

Both fixed 50:50 ensembles improve the outer conventional mean. Fine-tuned/conventional AUC is 0.690314, a gain of +0.010352; target-only/conventional AUC is 0.689582, a gain of +0.009621. The gains are positive for 60/73 and 64/73 species, respectively. The mean difference between ensembles is +0.000732, median +0.000086, with 37/73 species positive.

| Region | FT ensemble − conventional | Target-only ensemble − conventional | FT ensemble − target-only ensemble |
|---|---:|---:|---:|
| NCP | +0.014472 | +0.010639 | +0.003834 |
| SEH | +0.004880 | +0.007201 | -0.002322 |
| NNC | +0.011705 | +0.011022 | +0.000683 |

The target-only ensemble was added after opening, uses unchanged saved scores, and is AUC-only. The fine-tuned ensemble was specified before opening as exploratory. Their similarity shows that an ensemble gain is available without pretraining; it does not establish equivalence or prove that pretraining supplies no information.

## SEH tail and support

Fine-tuning minus target-only has mean −0.003999, median +0.002103 and 41/73 positive species. The ten most negative differences are retained below. Several involve thousands of presences, so the tail is not explained simply by low presence counts. No species was removed. Fine-tuning minus conventional has mean −0.007052, median −0.000902 and 36/73 positive species.

| Species | X10 presences | X10 background cells | FT − target-only AUC |
|---|---:|---:|---:|
| *Coracina papuensis* | 170 | 12,343 | -0.149775 |
| *Smicrornis brevirostris* | 2,235 | 10,321 | -0.089963 |
| *Artamus cyanopterus* | 3,157 | 9,594 | -0.077829 |
| *Pachycephala rufiventris* | 5,852 | 6,891 | -0.069215 |
| *Corcorax melanorhamphos* | 3,745 | 9,107 | -0.067038 |
| *Pardalotus striatus* | 6,586 | 6,196 | -0.039649 |
| *Melithreptus gularis* | 51 | 12,463 | -0.028780 |
| *Turnix varius* | 532 | 12,019 | -0.024896 |
| *Coracina novaehollandiae* | 5,578 | 7,144 | -0.023848 |
| *Acanthiza reguloides* | 3,273 | 9,392 | -0.021338 |

## Manuscript and verification

The active manuscript is `manuscript/text/main.md`, with a new evidence ledger, structured bibliography and two figures. Its argument now distinguishes the matched-network pretraining contrast, practical conventional comparison and intended geographic transfer. It preserves the original Tasmania weak/negative inner finding, reports its outer AUC/TSS disagreement, separates prospective from post hoc bird analyses and avoids occupancy, causal-effort, species-richness or independent-replication claims.

The new controller and bird analysis pass 12 focused tests. Every published bird inner mean-fold value reproduces exactly; all 2,870 defined saved-arm outer X10 AUC comparisons reproduce exactly, with the remaining classless comparisons retained as NA. Native Goal037 validation and independent closure checks bind every original Tasmania model, input and prediction before response access. The final review receipt records the completed checks and output hashes.

This is a review draft. Dataset citations and release conditions, the detailed journal supplement, author metadata and journal style still need completion or confirmation; the original pseudoabsence-removal sensitivity also needs an explicit disposition before claiming the full original protocol is complete. No inferential cross-case grand mean is reported.
