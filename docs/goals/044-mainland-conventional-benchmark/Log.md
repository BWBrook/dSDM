# Log

## 2026-08-24 - authorised

- Barry approved sequential execution: Goal 044 completes the conventional
  reference experiment; Goal 045 separately executes the dSDM experiment.
- Both experimental arms are frozen before Goal 044 results so conventional
  experience cannot be used to move the dSDM goalposts.
- Implemented a focused mainland modelling layer and resumable Goal 044
  runner using the existing five accepted model adapters.
- Focused tests passed `5/5`; the real input gate bound all 20 heads and
  3,775,385 split-response rows with Tasmania access `0/0`.
- The Mac CPU canary passed without computing performance metrics. Anchor
  runtimes ranged from under 0.01 seconds to 3.55 seconds; the first 19-head
  `q_linear` fit took 23.85 seconds.
- One complete Dasyurus/fraction25/ladder00 checkpoint exercised candidate
  selection, five-seed refits, community augmentation, checkpointing, and
  prediction validation.

## 2026-08-24 - production

- Completed all 35 target-endpoint tasks, 25 leave-target-out `q_linear`
  surfaces, and 7,505 physical fits under the three-worker Mac CPU route.
- Wall time was 1 hour 47 minutes. Private outputs occupy 42 MB; the tracked
  summary contains aggregate metrics only and no cell identifiers.
- Recorded seven candidate-local `enet08` non-convergence failures. All
  prespecified family-minimum gates remained satisfied without repair.
- The detached wrapper did not write `run.exit`, although the run log and
  summary closed normally.

## 2026-08-29 - independent validation and acceptance

- Revalidated all 35 private task checkpoints and 25 community surfaces.
  Prediction cells and responses bind exactly to each Goal 043 held fold;
  aggregate metrics replay exactly; Tasmania access remains `0/0`.
- Accepted the missing shell marker as non-material completion bookkeeping;
  no expensive rerun was justified.
- Passed the Goal 044 validator and all 25 focused tests. The repository-wide
  suite returned 681 passed, 2 failed, and 2 skipped; both failures are the
  pre-existing Goal 037 digest mismatch introduced when Goal 039 later changed
  `model_adapters.py`. Goal 044 changed neither side of that historical binding,
  so it was recorded rather than repaired here.
- Accepted Goal 044 and retained the prospectively frozen Goal 045 design
  without performance-driven amendment.
