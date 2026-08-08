# Log

## 2026-08-08 - implementation handoff

- Added deterministic metric/seed/task planning helpers and strict Goal033
  configuration.
- Added private bundle export/validation, atomic leaf execution, spawn-based
  worker orchestration, stage gating, aggregate ranking, and read-only
  validation paths.
- Focused tests and Python compilation pass. The real 1,440-evaluation queue
  has not been launched from this worker.
- `run` is private-only; no tracked evidence is written by the runner. The
  selected-runtime command path is recorded in `Runbook.md`; `finalize` is
  reserved for post-review/wake-up publication.
- Real export preflight exposed the intentional serializer/training dependency
  split: export uses the repository lock, while all fitting remains in the
  isolated calibrated runtime.

## 2026-08-08 - production preflight

- Provisioned and attested the isolated Goal033 runtime: Python 3.12.13,
  NumPy 2.2.6, PyTorch 2.7.1, Darwin arm64 CPU, one thread per worker.
- Exported and validated the exact 40-bundle species-by-fold cross-product
  through the repository-locked serializer. All required roles contain both
  classes, source membership is consistent, and outer attempted/opened is
  `0/0`.
- Ran one resumable real screen leaf (`dasyurus_maculatus`, `fold00`,
  `resmlp00`, base seed `31031`): 39 discovery epochs, selected/replayed epoch
  9, 216 finite scores, and outer attempted/opened `0/0`.
- The full three-worker queue remains pending launch under `tmux`.

## 2026-08-08 - completed selection

- The `dsdm-goal033` tmux run completed from commit `862861b` with exit code
  zero: 960 screen and 480 shortlist logical evaluations, representing 2,880
  discovery-plus-replay fits.
- All 1,440 private leaves revalidated with zero invalid or missing leaves.
  All 160 common-seed screen/shortlist replay pairs were byte-identical, and
  outer attempted/opened remained `0/0`.
- The screen advanced `resmlp13`, `resmlp15`, `resmlp19`, and `resmlp22`.
  The three-seed shortlist selected `resmlp13`; all eight leave-one-species-out
  rankings agreed.
- Independent read-only reconstruction exactly reproduced every AUC, TSS,
  threshold, ranking, and replay check. It supported finalization while noting
  that the raw advantage over `resmlp22` is small.
- Finalization wrote the aggregate-only receipt at
  `evidence/dsdm_architecture_selection/goal033/aggregate.json`; exact receipt
  validation and the tracked-evidence privacy scan passed.
- Final focused verification: `uv lock --check`, 27 architecture/training
  tests, and `git diff --check` passed.
