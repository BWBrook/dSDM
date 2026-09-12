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

Numerical amendment 2 was authorized by the user on 2026-09-05 before any
ecological scores. It rescales only the solver representation: `k` is the
maximum collapsed row weight, solver weights are `w/k`, and solver `C` is
`0.1*k`, so the penalized objective is exactly the original objective divided
by `k`. Convergence classification is based on `ConvergenceWarning`, with
explicit numerical warnings still rejected; unrelated warnings are retained
in attempt diagnostics. Deprecated `penalty` and `n_jobs` arguments are
removed from the q fit. Scientific rows, equal-head weighting, features,
exclusions, seed, and acceptance gate are unchanged.

Numerical amendment 3 was authorized on 2026-09-08 after the q stage stopped
with 143 converged surfaces and no target fits or ecological scores. It adds
one final from-scratch, same-seed 20,000-iteration attempt after the unchanged
5,000 and 10,000 attempts. Tolerance, objective, exclusions and acceptance
remain fixed. Use one fresh v4 collection, preserving all original evidence,
and pass the amended Nectar stress/canary gate before production. All 150
surfaces must validate before target fitting. A further failure stops for review.

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


## 10 September 2026 — verification complete; acceptance decision required

All 303 endpoints, 449 q conditions and 150 q surfaces are numerically
verified. Both production exit markers are zero. Native final validation
replayed every endpoint, and a separate reconstruction verified all 785
target/fold pairs and 1,515 training endpoint/fold pairs: frozen subset
selection, nested fractions, held-fold exclusion, disjoint training/validation
cells and X10 support. Independent metric replay agreed within 4.45e-16 over
474,174,113 prediction rows. All useful results are returned to the Mac with
verified SHA-256 hashes. Outer outcomes remain unopened; Goal052 is unstarted.
See `evidence/seawfb_conventional/goal051/completion_review.json` and the
canonical aggregate `summary.json` beside it.

**Acceptance remains pending Barry's adjudication of the failure criterion.**
The prospective freeze (`9216e29`) defined the executable prevalence gate as
family availability of at least 90% in both extreme prevalence quartiles,
alongside at least 95% overall coverage. All five families achieved 100%
everywhere, and every endpoint retains at least three elastic-net candidates.
However, the Goal and Decision prose above says prevalence-patterned
"failure" stops the goal without specifying the family level.

All 49 rejected candidates are `enet08` nonconvergence. They affect 18/75
endpoints in the lowest prevalence quartile versus 4/75 in the highest
(24.0% versus 5.3%). This reduces tuning breadth unevenly. `enet08` is the
selected elastic-net candidate at 54 of the 254 endpoints where it converges,
so its absence cannot be declared immaterial. None of the 49 affected endpoints
selected elastic net as its best family, but the missing candidate's
counterfactual effect on family/q selection is unknown. Both the parent and
independent specialist recommend **acceptance under the original operational
family-level gate, explicitly retaining this candidate-level limitation**.
Barry must settle that interpretation; no new statistical test, relaxed
convergence rule or refit is proposed or authorized here.

The descriptive inner-fold results are:

| Panel | Selected conventional mean AUC | With full q | Mean change |
| --- | ---: | ---: | ---: |
| All 157 targets, full target data | 0.879419 | 0.879577 | +0.000158 |
| 73 primary targets, 25% data | 0.820012 | 0.820527 | +0.000515 |
| 73 primary targets, 50% data | 0.824473 | 0.824921 | +0.000449 |
| 73 primary targets, 100% data | 0.828213 | 0.828594 | +0.000381 |

These are equal-target averages of mean-fold AUC, following candidate/family
selection on the same inner folds; they are not independent outer performance
estimates. Full-data selected families are HGB 66, random forest 51 and shallow
ANN 40. Scalar community q adds very little mean discrimination in this
comparison. This does not test the distinct learned-representation hypothesis
reserved for Goal052, establish occupancy probabilities, or justify changing
its prospectively frozen design.

Target-model numeric seeds and per-fit convergence diagnostics are not retained
in endpoint payloads; their execution is supported by the identity-bound source
and strict adapter checks. All q attempt diagnostics and finite parameter
digests were independently verified. This distinction remains an audit limit.

The next decision is to adjudicate Goal051 acceptance as above. If accepted,
Goal052 execution still needs separate authority; its design remains frozen.


## 12 September 2026 — accepted by Barry

Barry approved proceeding autonomously after the recommendation above.
Goal051 is accepted under its prospectively frozen operational family-level
coverage gate, with the prevalence-patterned `enet08` candidate failures and
their unknown counterfactual effect retained as explicit limitations. No
candidate refit, retrospective gate, numerical relaxation or scientific
redefinition was made. The verified v4 benchmark is the conventional reference
for Goal052; its source, configuration and aggregate hashes remain unchanged.

The completed Goal051 heartbeat is paused. Nectar remains parked with all
remote evidence preserved. Proceed to implementation and validation of the
frozen Goal052 design within the user's autonomy request; preserve sealed
outer outcomes and consult Barry for a material scientific amendment or
substantial new compute commitment.
