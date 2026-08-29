# Decision

## Status

Goal 044 is `ready` as of 2026-08-29.

The detached Mac CPU run completed on 2026-08-24 in 1 hour 47 minutes. Its
shell-level `run.exit` marker was not written, but the run log closed normally,
all expected outputs were present, and the independent validator subsequently
replayed every response/prediction binding and aggregate metric successfully.
The missing convenience marker is not grounds to repeat 7,505 validated fits.

The Goal 044 validator and all 25 focused tests pass. The repository-wide
suite reports 681 passed, 2 failed, and 2 skipped. Both failures are the same
pre-existing Goal 037 strict-binding check: its sealed config records the
pre-Goal-039 digest of `model_adapters.py`, which Goal 039 subsequently changed.
Goal 044 changed neither file. Rewriting that historical contract is outside
this goal and would not add evidence about the mainland benchmark.

## Conventional benchmark

All 35 target-endpoint tasks completed: five targets at three 25% ladders,
three 50% ladders, and one 100% endpoint. Candidate selection used mainland
OOF ROC AUC with TSS as the deterministic tie-break. Natural class prevalence
was retained throughout.

Random forest was the selected non-null family in 27/35 strata, histogram
gradient boosting in 6/35, and elastic net in 2/35. The shallow ANN was a
competitive comparator but was never selected. Seven candidate-local failures
were all non-convergence of the optional lasso-heavy `enet08`; every elastic-
net stratum retained at least three complete alternatives, all other candidate
families completed, and no rescue or tolerance relaxation is warranted.

Full-target mainland OOF results were:

| Target | Selected family | Candidate | Mean-fold AUC | Pooled TSS |
|---|---|---|---:|---:|
| *Dasyurus maculatus* | random forest | `rf00` | 0.8803 | 0.5947 |
| *Notamacropus rufogriseus* | random forest | `rf00` | 0.9528 | 0.7730 |
| *Pseudocheirus peregrinus* | histogram boosting | `hgb04` | 0.8983 | 0.6619 |
| *Trichosurus vulpecula* | random forest | `rf02` | 0.8113 | 0.4954 |
| *Vombatus ursinus* | random forest | `rf00` | 0.9831 | 0.8920 |

Mean selected-family AUC increased from 25% to 50% to 100% target data for
every species. This supports the intended learning-ladder behaviour. Fold
heterogeneity remained material for *D. maculatus* and especially the high-
prevalence *T. vulpecula*; fold results are paired development diagnostics,
not independent ecological replicates.

## Community scalar control

All 25 `q_linear` surfaces used exactly the other 19 training-role heads, gave
each head equal total loss contribution, retained natural within-head class
imbalance, and excluded the target. The scalar was appended to the already
selected target-only family and candidate without retuning.

Across 35 strata, `q_linear` changed mean-fold AUC by a mean of +0.00111 and a
median of +0.00035; 27/35 changes were positive. Mean changes were +0.00105 at
25%, +0.00141 at 50%, and +0.00039 at 100%. The full-target change ranged from
-0.00202 for *P. peregrinus* to +0.00283 for *D. maculatus*.

This is a useful but modest community signal. It does not by itself transform
the conventional models, and it creates a stringent control for Goal 045:
multi-head dSDM must show value beyond both target-only learning and this
compressed leave-target-out community gradient.

## Boundary and decision

Tasmania response rows read: zero. Tasmania predictor rows used: zero. No dSDM,
full-mainland refit, X=2/X=5 sensitivity, map, or manuscript claim was made.

Accept Goal 044. The Goal 045 arms, architecture panel, five seeds, head-
balancing rule, target exclusion, learning ladder, and contrasts were frozen
before these results and remain unchanged. Goal 045 is the separate dSDM
experiment, not an opportunity to tune in reaction to this benchmark.
