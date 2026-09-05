# Goal 052 - SEAWFB dSDM experiment

## Objective

Execute the separate, prospectively frozen multi-species dSDM experiment for
the SEAWFB case after Goal 051's conventional benchmark has been accepted.
The experiment tests whether leave-focal-block-out multi-head pretraining improves
inner spatial generalisation beyond matched target-only learning, the
compressed `q_linear` community control, and the selected conventional
benchmark.

This packet freezes the protocol only. It does not execute models or open
outer ecological outcomes.

## Frozen design

- Four paired arms: target-only random-init ResMLP, target plus `q_linear`
  ResMLP, multi-head frozen trunk, and multi-head full fine-tuning.
- The entire focal block is excluded from every pretraining fit and auxiliary
  richness construction, not merely the target. Auxiliary heads receive equal
  total contribution, while each head retains natural class prevalence. The
  150 shared q surfaces are indexed by focal block, held fold, and auxiliary
  size 20/80/`full`.
- The crossed 449-condition grid and target-only arms are reused from Goal 051.
- The bounded architecture panel is `bridge_control` (3 x 128, bottleneck 64),
  `bridge_wide` (3 x 256, bottleneck 64), `bridge_deep` (6 x 128, bottleneck
  64), and `seawfb_scale` (6 x 256, bottleneck 128), all with GELU, LayerNorm,
  AdamW, batch 128, maximum 300 epochs, patience 30, and minimum improvement
  1e-5. Every candidate uses the same pre-normalized two-layer residual block,
  with an input projection and identity skips; only depth, width, and bottleneck
  vary.
- One shared architecture is selected using only the primary full-target,
  `full`-auxiliary endpoint of the full-fine-tuning arm, seed00. Rank by
  within each target by equal-fold mean ROC AUC descending, pooled OOF TSS
  descending, then architecture ID ascending. Select the shared winner by mean
  target rank ascending, mean target ROC AUC descending, then architecture ID
  ascending. All final arms use that architecture and five paired seeds.
- Auxiliary 20/80/`full` and target 25/50/100% learning curves reuse the Goal
  050 deterministic plans. The 84 full-only focal targets receive the full
  endpoint.
- The next non-held fold supplies stopping; all four non-held folds are
  replayed at the selected epoch. Seed predictions are averaged before the
  primary OOF assessment.
- A leave-one-focal-block-out stability audit is post-selection diagnostic
  evidence only and cannot change the winner. Keep frozen-v-target-only and
  full-v-frozen as mechanistic diagnostics, separate from the four primary
  full-fine-tuning contrasts. Record the median selected epoch rounded for any
  later retained-full refit.

## Acceptance criteria

1. Goal 051 is accepted and its selected conventional controls are bound.
2. All four arms, five seeds, five held folds, and planned learning endpoints
   complete with strict target exclusion and private row-level storage.
3. Paired OOF contrasts, threshold provenance, supplementary metrics,
   runtime, and privacy receipts validate independently.
4. NCP, SEH, and NNC remain unopened until a separately authorized outer
   evaluation goal.
5. Goal 051 numerical amendment 1 is the recorded pre-score amendment and must
   pass a repeated metric-free canary. Any further pre-score change requires
   explicit versioned authorization; any post-score scientific amendment
   requires a versioned protocol and full rerun.

## Stopping boundary

Do not run this packet before Goal 051 acceptance. Do not refit on all cells,
open outer outcomes, select an outer threshold, make maps, or write manuscript
claims here.
