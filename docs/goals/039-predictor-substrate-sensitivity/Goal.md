# Goal 039 - predictor-substrate sensitivity

## Objective

Determine whether a prespecified, response-blind reduction of the 28-predictor
substrate improves inner out-of-sample transfer and generalisation for the
frozen `resmlp13` dSDM control, relative to the full predictor substrate.
Conventional SDM fits provide context for distinguishing general denoising
from a dSDM-specific transfer effect.

This is an inner-only diagnostic. It must not open the outer vault or produce
outer-ready predictions, maps, manuscript material, bird results, or a new
architecture search.

## Acceptance

1. Freeze and validate exactly five deterministic, fold-specific predictor
   masks before any response-aware fitting; every mask is finite, represents
   every ecological BIOCLIM block, retains all mandatory predictors, and
   removes at least one BIOCLIM predictor per fold.
2. Run the declared canary, screen, and (only if earned) confirmation lanes
   using exactly `target_only_resmlp` and `multihead_full_finetune`, with
   identical fold masks shared by dSDM and conventional candidates.
3. Record the prespecified `Delta U` and `Delta I` lanes, aggregate gates,
   inventory, provenance, and outer-access receipt without exposing row-level
   labels or predictions.
4. Advance each primary lane independently. A screen-ineligible lane cannot be
   revived during confirmation; if neither lane is eligible, retain `full28`.
   Conventional context alone cannot trigger adoption.

The complete frozen estimand, mask algorithm, workload, gates, and non-goals
are in `Decision.md`.
