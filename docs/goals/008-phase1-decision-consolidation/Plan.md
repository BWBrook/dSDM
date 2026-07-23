# Plan: Goal 008 Phase 1 Decision Consolidation

1. Verify the expected clean action-repo start and read Goal 007 plus the
   current contract/register surfaces.
2. Create and read this packet in `Goal.md` -> `Plan.md` -> `Runbook.md` ->
   `Log.md` order before implementation.
3. Add test-first coverage for the tracked decision bundle and readiness
   summary, including fail-closed mutations.
4. Implement the smallest validator/loader using only the Python standard
   library; preserve existing scaffold APIs.
5. Update the decision register to mirror the bundle, separating resolved
   policy from operational prerequisites.
6. Run the focused RED/GREEN and final validation ladder, perform one focused
   self-review, and update `Log.md`.

## Stop rules

Stop and report if the repository start differs, unrelated dirt appears, the
decisions cannot be represented without guessing, or validation would require
live data, source paths, dependencies, or broad migration.
