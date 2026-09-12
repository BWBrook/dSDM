# Goal052 implementation contract — 12 September 2026

The protocol in `config/goal052_seawfb_dsdm.json` remains unchanged. Barry
accepted Goal051 and requested autonomous continuation on 12 September.
This note records implementation semantics checked against the prospective
protocol and the established mainland experiment; it adds no scientific arm,
architecture, tuning option or outer assessment.

## Training roles and reuse

For held fold h, the stopping fold is (h+1)%5. Auxiliary discovery optimizes
on the other three folds, stopping selects its epoch, and pretraining replays
from its initial state on all four non-held folds. That replay trunk is the
same initializer for target discovery and target replay. Stopping-fold
auxiliary responses exclude the entire focal block, including its contribution
to auxiliary effort richness. The stopping fold is a target-label epoch
selection set; it is not independent performance evidence. Held fold h is
excluded throughout, including the frozen Goal050 transform and Goal051 q fit.

Reuse the accepted 150 q surfaces without refitting or retuning. Standardize q
on the actual target fraction's training rows, then apply that scaling to both
discovery/stopping and held prediction rows. This matches the frozen Goal051
endpoint-specific control. Reuse the fixed four-fold Goal050 transforms.

Target numeric seeds depend on protocol, target, target fraction, held fold,
architecture and seed label, omitting arm and auxiliary size. Pretraining uses
a separate namespace including focal block and auxiliary size. Preserve the
bridge lifecycle's separate target-head initialization (seed+17) and replay
shuffle (seed+100000). Target discovery and replay reset to the identical
initial model, use separate AdamW optimizers, and train the replay for exactly
the selected epoch count. Frozen trunks must retain their parameter digest.

Store predictors once per unique cell and index them with the expanded
head/cell response rows. Shuffle those observation rows and retain their
per-head equal-total weights; this changes memory layout, not the empirical
objective, natural prevalence or optimization schedule. Record numeric seeds,
finite-parameter checks and initial/replay/final digests in every fit receipt.

The efficient planned inventory is 900 unique pretraining tasks (200 for the
four-architecture screen and 700 additional selected-architecture tasks),
1,460 architecture-screen target/fold fits, and 41,250 final target lifecycles.
The winning architecture's 365 primary seed00/full-finetuning screen leaves
are reused in the final grid. Target-only leaves are shared across auxiliary
sizes. All other arms include auxiliary size in their checkpoint identity.
Use spawned workers and atomic per-arm/seed/fold leaves; no partial-seed or
partial-fold scoring is permitted.

## Selection and interpretation

Within each primary target, rank the four architectures by equal-fold mean
AUC, then pooled OOF TSS, then architecture ID. Across the 73 primary targets,
rank by mean target rank, then mean target AUC, then ID. Leave-one-focal-block-out
reranking is diagnostic and cannot override the full-panel selection.

Average the five neural seed predictions before primary metric evaluation.
Seed pairing applies exactly among neural arms. Goal051 conventional controls
already average family-specific seeds and omit numeric target seed records;
compare them by target/fold/condition/canonical cells after neural averaging,
without claiming seed-paired conventional contrasts. Thresholds come only from
concatenated training OOF predictions. Do not treat folds or seeds as
independent species replicates.

The 73 architecture-selection targets are development evidence. Report the
84 full-only targets separately because they did not select the architecture;
they provide less selection-biased evidence within this retained domain.
Neither group supplies outer-region performance or occupancy probabilities.

## Verification and compute boundary

A bounded independent review found no scientific amendment necessary for these
semantics. Test exclusions, role disjointness, indexed/dense loss equivalence,
transfer/reset/freeze digests, seed pairing, endpoint counts, exact ranking,
checkpoint identity and seed-averaged OOF replay before production. Then run a
metric-free full-auxiliary canary to measure memory and throughput before
choosing concurrency and any substantial new resource commitment. Do not run
heavy canaries on parked Nectar. Outer NCP, SEH and NNC outcomes remain sealed.
