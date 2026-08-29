# Goal 045 - mainland dSDM experiment

## Objective

Execute the prospectively frozen mainland dSDM experiment for the five
Tasmania transfer targets and determine whether leave-target-out multi-species
pretraining improves mainland spatial generalisation beyond matched target-only
learning, a scalar community control, and the Goal 044 conventional benchmark.

## Acceptance criteria

1. Bind exactly to Goal 043 folds and transforms, Goal 044 target subsets and
   `q_linear` surfaces, and the Goal 045 design frozen before Goal 044 results.
2. Keep the target out of every pretraining fit. Use exactly the other 19
   response heads, equal total loss contribution per head, and natural class
   prevalence within each head.
3. Select one shared architecture from `bridge_control`, `bridge_wide`, and
   `bridge_deep` using seed00, the full-target endpoint, the primary full-
   fine-tuning arm, and equal-species mainland CV rank. Do not use Goal 044
   performance to alter the panel.
4. Run all four frozen arms with the selected architecture, five paired seeds,
   five held folds, and the same 25/50/100% nested target-data ladder.
5. Use the next non-held fold for epoch stopping and replay all four non-held
   folds at the selected epoch. Preserve the frozen AdamW, batch, patience,
   and maximum-epoch budgets.
6. Average the five seed predictions before primary OOF evaluation. Report
   paired contrasts against the target-only neural arm, target plus `q_linear`,
   selected Goal 044 conventional model, and its `q_linear` augmentation.
7. Retain cell identifiers and predictions only in ignored private outputs.
   Track aggregate evidence and exact provenance. Tasmania remains sealed.

## Stopping boundary

Do not run a full-mainland refit, X=2/X=5 sensitivity, Tasmania evaluation,
map, or manuscript synthesis. A null or negative mainland result is valid and
must not trigger retrospective architecture changes.
