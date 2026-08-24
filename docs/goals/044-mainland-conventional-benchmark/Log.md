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
  prediction validation. Production execution remains pending.
