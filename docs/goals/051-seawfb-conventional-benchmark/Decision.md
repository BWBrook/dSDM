# Goal 051 decision record

## Prospective freeze

Goal 052 is a separate, prospectively frozen experiment. Its arms, bounded
architecture panel, target exclusion, auxiliary learning curve, stopping and
replay rule, paired seeds, and primary contrasts are fixed before Goal 051
ecological scores are exposed. Conventional results cannot be used to select
or amend a dSDM architecture.

## Conventional comparison

The comparison suite is the intercept null, elastic net, random forest,
histogram gradient boosting, and shallow ANN. These are the accepted
reference families already used for the mammal benchmark. GAM/MARS/SVM and
other exploratory families are outside this tranche.

## Community control

`q_linear` is a pooled elastic-net logistic scalar represented by 150 shared
surfaces: one for each of ten focal blocks, five held folds, and three
auxiliary sizes (20, 80, `full`). The entire focal block is excluded from
auxiliary heads and auxiliary effort richness, and the held fold is excluded
from training. It uses fixed `enet04` (`C=0.1`, `l1_ratio=0.5`) on X only,
with no species-ID predictor. Each head has equal total row weight, rows
within a head share a constant weight, and q is standardised per target, held fold,
and endpoint using target training-role rows. Q is appended after the 21
continuous predictors and before frozen categorical encoding; family and
candidate selection are not retuned. Auxiliary 20/80/`full` and target
25/50/100% plans are represented as five unique downstream endpoints, with
target 100%/auxiliary `full` shared rather than duplicated.

After a metric-free primary nonconvergence, numerical amendment 1 fixes SAGA
at tolerance 1e-5 and 5,000 primary iterations. A warning or iteration-ceiling
hit triggers one from-scratch fit with the identical seed and a 10,000-iteration
ceiling. Only a converged attempt is accepted. No coefficient- or prediction-
stability exception is authorized. Solver, regularization, data, weights,
features, exclusions, and random seed are unchanged.

The inventory gate is 303 base endpoints, 449 q conditions, and 150 shared q
surfaces. There is no partial-fold scoring. The null is mandatory; each family
needs at least two complete candidates or an explicit NA. At the primary full
endpoint, elastic net, a tree family, and the shallow ANN must remain covered.
Family coverage below 95% or prevalence-patterned failure stops the goal. One
focused repair pass is permitted.

## Evaluation boundary

The estimand is relative habitat suitability. ROC AUC is primary; pooled OOF
TSS selects candidates and derives a finite threshold, with BA, MCC,
sensitivity, specificity, prevalence, and fold variation supplementary. The
three frozen IBRA holdouts, NCP, SEH, and NNC, remain sealed.
