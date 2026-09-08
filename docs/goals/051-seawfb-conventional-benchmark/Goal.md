# Goal 051 - SEAWFB conventional benchmark

## Objective

Fit the five-family conventional reference suite for the south-east
Australian woodland/forest bird (SEAWFB) case on the Goal 050 retained
training substrate. The benchmark includes a strict leave-focal-block-out
`q_linear` community control and is evaluated only within the frozen training
folds. Goal 052's dSDM protocol must be prospectively frozen before any
ecological benchmark score is exposed.

## Scientific contract

- Use all 157 Goal 050 focal targets. The 73 primary targets receive nested
  25%, 50%, and 100% target-data endpoints; the remaining 84 receive a
  deterministic 100% endpoint. Subsets are reconstructed only from the Goal
  050 frozen response-row plans and manifest-bound digests; no new subset seed
  is permitted.
- Use the five accepted conventional families: intercept-only null, elastic
  net, random forest, histogram gradient boosting, and a shallow one-hidden-
  layer ANN. Preserve natural within-target prevalence, equal row weights,
  and the Goal 050 X10 richness/support rule.
- Select candidates and families by mean held-fold OOF ROC AUC, with pooled
  OOF TSS as the deterministic tie-break. Thresholds are derived only from
  concatenated training OOF predictions and are interpreted as relative
  habitat-suitability indices, not occupancy probabilities.
- Fit `q_linear` as 150 shared surfaces, one for each focal block, held fold,
  and auxiliary size (10 x 5 x 3, with sizes 20, 80, and `full`). For a focal
  block, exclude the entire block from auxiliary heads and auxiliary effort
  richness, and exclude the held fold from training. Fit fixed `enet04`
  (`C=0.1`, `l1_ratio=0.5`) on X only, with no species-ID predictor. Give each
  head equal total row weight, with a constant weight within each head, and
  standardise q per target, held fold, and endpoint using target
  training-role rows. Append q after the 21 continuous predictors and before
  the frozen categorical encoding, without family or candidate retuning. The
  five unique downstream endpoints are target 100% with auxiliary 20/80/`full`,
  and target 25/50% with auxiliary `full`.
- Under numerical amendments 1, 2 and 3, fit q with SAGA tolerance 1e-5 and a 5,000
  iteration primary ceiling. On warning or ceiling hit, retry once from scratch
  with the same seed and a 10,000 iteration ceiling. Amendment 3 adds one
  final from-scratch, same-seed attempt at 20,000 if needed. Accept only finite,
  warning-free convergence below the ceiling; all 150 q surfaces must validate
  before any target fitting.
  Amendment 2 divides solver sample weights by `k = max(weight)` and multiplies
  solver `C` by `k`, preserving the exact q objective up to a common scale.
  Only `ConvergenceWarning` and explicit numerical warnings affect convergence
  classification; other warning types remain diagnostics. Deprecated q solver
  arguments are omitted.

## Acceptance criteria

1. The Goal 050 bindings, five folds, target panels, transforms, support rule,
   and natural prevalence are validated without reading outer outcomes.
2. All planned conventional and q-augmented inner endpoints complete or fail
   transparently under the prespecified family-minimum gates.
3. OOF metrics, threshold provenance, candidate/family selections, failures,
   and privacy receipts validate independently from private row-level output.
4. Goal 052 is frozen before Goal 051 ecological scores are exposed; Goal 051
   results do not amend the dSDM design.
5. The inventory is exactly 303 base endpoints, 449 q conditions, and 150
   shared q surfaces; no partial-fold scoring is accepted. The null is
   mandatory, each family has at least two complete candidates or an explicit
   NA, and the primary full endpoint retains elastic-net, a tree family, and
   the shallow ANN.
6. Stop if family coverage is below 95% or failures are prevalence-patterned;
   permit one focused repair pass only.
7. No NCP, SEH, or NNC response/outcome table is opened.
8. The original Mac/deep-server route remains historical. Under amendment 3,
   the Nectar route binds the fresh v4 stress fit and two serial/16 concurrent
   metric-free canaries, with the old Nectar route as lineage. It proves
   configured concurrency from overlapping intervals and selects no more
   workers than the host demonstrated.

## Stopping boundary

Do not fit dSDM models, refit on all mainland cells, run X20/X5 sensitivities,
open NCP/SEH/NNC outcomes, select outer thresholds, make maps, or revise
manuscript claims.
