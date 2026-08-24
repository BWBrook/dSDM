# Goal 044 - mainland conventional benchmark

## Objective

Complete the mainland-only conventional reference experiment for the five
Tasmania transfer targets, including a leave-target-out scalar community
control, while prospectively freezing the separate Goal 045 dSDM experiment.

## Acceptance criteria

1. Bind exactly to Goal 043's 50 km folds, X=3 split responses, fold-fitted
   transformations, and 24-predictor substrate. Tasmania remains sealed.
2. Fit intercept, elastic net, random forest, histogram gradient boosting, and
   shallow ANN for all five targets and the nested 25/50/100% target-data
   ladder. Preserve natural within-target prevalence and equal row weights.
3. Select candidates and the best conventional family by mainland OOF ROC AUC,
   with TSS as the deterministic tie-break. Report BA, MCC, sensitivity,
   specificity, prevalence, fold variation, and failures without rescue.
4. Fit `q_linear` separately for every target and held fold using only the
   other 19 training-role response heads. Equalise total contribution among
   heads without balancing classes within a head.
5. Refit the selected best non-null target learner with `q_linear` appended,
   without retuning its family or candidate, to isolate the scalar community
   information gain.
6. Freeze Goal 045's arms, three-candidate architecture panel, species-balanced
   pretraining rule, target exclusion, five seeds, learning ladder, contrasts,
   and amendment rule before Goal 044 results are available.
7. Retain row predictions and cell identities only in ignored private outputs.
   Track aggregate evidence, exact bindings, checksums, runtime, and the final
   decision.

## Stopping boundary

Do not fit a dSDM, select a Goal 045 architecture, use `mainland_full`, run
X=2/X=5 sensitivities, access Tasmania responses or predictors, make maps, or
revise manuscript claims.
