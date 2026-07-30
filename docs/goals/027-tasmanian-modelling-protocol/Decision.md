# Decision

Goal027 is accepted as a **version 0.1 design freeze approved by Barry on
2026-07-30**. The complete policy is in
[`docs/plan/tasmanian_modelling_protocol.md`](../../plan/tasmanian_modelling_protocol.md).
It governs the Tasmanian implementation boundary; it is not a fitted result.

The protocol fixes the conditional relative-habitat-suitability estimand over
Goal024 `D_struct`, atomic species-cell responses and zero-source handling,
Goal025 outer/CV nesting and leakage rules, continuous-first metrics and
inner-OOF thresholds, all-28-predictor preprocessing, the conventional model
set, pseudoabsence-free leave-target-out auxiliary controls, the multi-head
dSDM ladder, scalar `q` controls, three nested target fractions, one shared
architecture, matched five-seed replication, primary contrasts, paired
aggregation, and the Tasmania-to-birds versioning boundary.

Prior authority remains Goal020--021 for response and pseudoabsence rules,
Goal024 for `D_struct`, Goal025 for spatial roles, and Goal026 for
split-fitted feature transforms. If implementation requires a scientific
change, open a new versioned decision rather than altering this document
silently.

## Limitations declared at freeze

The design remains conditional on mixed zero provenance and imperfect
detection, high prevalence and rare negatives, within-range spatial/domain
support, touching patches and spatial dependence, eight species, and
architecture-selection uncertainty. These are reporting risks, not reasons to
relax the predeclared policy or to treat folds, seeds, rows, or fractions as
independent replication.
