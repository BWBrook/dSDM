# Plan

1. Freeze and validate the Goal029 configuration, exact 7,168-leaf plan,
   conservative anchors, warning policy, numerical thread policy, calibration
   roles, and non-goals.
2. Generalise the Goal028 inner-CV machinery additively for canonical
   `seed00`–`seed04` leaves while preserving Goal028 outputs.
3. Implement source/runtime/upstream identities, deduplicated membership
   bundles, tamper-evident atomic leaf checkpoints, and blinded failures.
4. Implement seed-leaf aggregation, candidate invalidation, family quorum,
   OOF metric recomputation, frozen candidate selection, and selected refits.
5. Implement response-free challenge matrices, model/challenge semantic
   replay, and exact selected-model authority reconstruction.
6. Implement artefact-only validation, exact staged-file inventories, and the
   deterministic exact-359 fresh, cache-disabled source audit; both validation
   passes and the audit must precede pair publication and its final marker.
7. Pass focused tests, the Goal028 regression suite, synthetic end-to-end,
   lock/compile/diff gates, and update the log.
8. Run real calibration only when the orchestrator authorises it: first the
   zero-fit four-child thread audit, then the two-leaf GAM canary at workers
   1/2, the exact 30-leaf representative panel at workers 1/2/4, and the
   32-leaf fragility panel once at the selected count. Stop on canary slowdown,
   semantic drift, swap growth, or less than 6 GiB free-memory headroom.
9. Run the full real plan on one selected host/worker setting only after
   calibration. Choose the smallest safe count within 1.10 of the fastest
   representative trial and resume only exact matching checkpoints.
10. Validate the complete staged pair, run the fresh source audit, publish the
    two core-manifest trees plus acyclic pair descriptor, write the final
    marker last, review once for material defects, and stop before any outer
    assessment.

The implementation plan is
[`docs/superpowers/plans/2026-07-30-goal029-conventional-baseline-production.md`](../../superpowers/plans/2026-07-30-goal029-conventional-baseline-production.md).
