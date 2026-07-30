# Goal 027 — Tasmanian modelling protocol freeze

## Objective

Record the Barry-approved (2026-07-30) version 0.1 scientific design for the
Tasmanian modelling and dSDM comparison, and define the boundary for a later
implementation goal. The canonical protocol is
[`docs/plan/tasmanian_modelling_protocol.md`](../../plan/tasmanian_modelling_protocol.md).

## Estimand and scope

The estimand is a species-specific relative habitat-suitability index scaled
0--1 over Goal024 `D_struct`, conditional on the accepted 2001--2025 response
construction and modelling design. The eight Goal019 species, all 28 primary
predictors, Goal025 held patches/CV folds, nested target fractions, matched
conventional baselines, scalar community controls, and the multi-head dSDM
ladder are frozen as specified in the protocol.

## Non-goals

- fitting, tuning, predicting, thresholding, or comparing any model;
- changing Goal020--026 response, domain, partition, or feature decisions;
- asserting occupancy, abundance, prevalence, probability, or outside-domain
  inference;
- silently choosing implementation grids, optimiser/batch ranges, software
  versions, or runtime manifests;
- rescuing Tasmania with birds, unplanned models, augmentation, or arbitrary
  effect thresholds.

## Acceptance

This goal is accepted when the protocol, decision record, plan, log, and
documentation-only runbook are present, cross-linked, internally consistent,
and explicitly state that no models were run. The strategic roadmap must show
Phases 1 and 2 complete, Phases 3 and 4 governed by this design but not yet
implemented, and the next gate as Barry's review of the written protocol
followed by a separate implementation goal.
