# Plan

The executor-ready implementation sequence is
[`docs/superpowers/plans/2026-07-30-goal028-modeling-foundation.md`](../../superpowers/plans/2026-07-30-goal028-modeling-foundation.md).

## Deliverables

1. Pin Python 3.12, declare the approved modelling dependencies, refresh
   `uv.lock`, and bind its digest in the run configuration.
2. Add the exact Goal028 configuration and typed contract validation.
3. Add deterministic split-specific target subset construction and its
   invariant suite.
4. Add the sole digest-verified private ingestion factory, sealed outer
   boundary, outer-training-only split broker, and feature provider that
   reconstructs Goal026 split-specific features without injected feature
   payloads.
5. Add conventional and native-PyTorch adapters using the explicit candidate
   registry.
6. Add neural stopping-fold epoch discovery and same-seed complete-training
   replay using a distinct endpoint and one fixed encoder per assessment fold;
   common RowKey-aligned seed-averaged OOF; family-stratified selection;
   candidate-specific OOF-threshold TSS tie-breaking; Goal027-consistent
   lower-median threshold clarification; provenance-safe full-training refit;
   complete initial-state-bound neural fold receipts; canonical
   fraction100/full identity; externally manifest-digest-authorised,
   feature-schema-bound serialization/replay; metric recomputation; and
   adjacent-score threshold fallback.
7. Add atomic private/aggregate publication and fail-closed validation.
8. Pass synthetic end-to-end and tamper tests.
9. Run the bounded two-species real preflight without opening the outer set.
10. Perform one implementer self-review after each task. Use independent
    reviewer gates only after coherent work packages Tasks 1–3, Tasks 4–6,
    and Tasks 7–9, followed by one final whole-diff review after Task 10. Allow
    at most one focused repair per gate unless a material defect persists;
    stop without committing or pushing.

## Ownership

Implementation work is confined to the exact files enumerated in the detailed
plan. Goal024–027 source and products are read-only upstream authorities.
Private outputs remain ignored; tracked evidence remains aggregate and must
contain no grid IDs, coordinates, row payloads, private paths, site/camera
identifiers, or private observation timing.

## Executor authority

The assigned implementation agent may edit the enumerated source, tests,
configuration, `pyproject.toml`, `uv.lock`, Goal028 log, and Goal028
aggregate/private artefacts. It may use `uv` to resolve/install dependencies
and run all commands in [Runbook.md](Runbook.md). It must not alter upstream
goals, run real outer predictions or scoring, use remote compute, commit, or
push. Publication to Git is an orchestrator action after review.
