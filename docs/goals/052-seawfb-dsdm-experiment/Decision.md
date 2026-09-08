# Goal 052 decision record

## Status

Protocol frozen on 2026-09-05 before Goal 051 ecological scores were exposed.
This is a prospective protocol record, not a model result.

## Scientific contrasts

The primary contrast is multi-head full fine-tuning against matched target-only
random-init learning. Secondary contrasts are against target plus `q_linear`,
the Goal 051 selected conventional learner, and its `q_linear` augmentation.
The contrasts are paired by target, held fold, endpoint, and seed.

## Leakage and stopping

The entire focal block is excluded from every pretraining auxiliary fit and
auxiliary richness construction, including auxiliary learning-curve
construction. Held folds are excluded from training roles. Stopping uses the
next non-held fold; replay uses the remaining non-held folds at the selected
epoch. Architecture selection is an inner development operation and cannot
access NCP, SEH, or NNC.

The four-architecture winner is selected at target 100%/auxiliary `full`,
seed00. Within each target, rank equal-fold mean ROC AUC descending, pooled OOF
TSS descending, then architecture ID ascending. Across targets, rank mean
target rank ascending, mean target ROC AUC descending, then architecture ID
ascending. All candidates use the same pre-normalized two-layer residual block
with an input projection and identity skips. Leave-one-block-out stability is
diagnostic only. Frozen-versus-target and full-versus-frozen are mandatory
mechanistic diagnostics, not members of the four primary scientific contrasts.
The median selected epoch is rounded for any later retained-full refit.

Before scores, Goal 051 numerical amendments 1, 2 and 3 were versioned after
metric-free q fitting diagnostics and require a repeated metric-free canary.
Amendment 3 adds only the authorized tertiary 20,000-iteration q attempt;
these amendments do not alter the dSDM scientific design. Any further pre-score change requires explicit
versioned authorization; after scores, any scientific amendment requires a
versioned protocol and full rerun.

## Interpretation

The output is a relative habitat-suitability index. Any improvement or null
result is an inner spatial-generalisation result until a later, explicitly
authorized outer evaluation exposes the three frozen IBRA holdouts.
