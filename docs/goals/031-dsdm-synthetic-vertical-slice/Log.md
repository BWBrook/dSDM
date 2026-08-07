# Log

## 2026-08-07 - Design checkpoint

- Confirmed a clean `main...origin/main` baseline at
  `e102a5a8c03597c769af10eb7979e5ff5f02d0a4`.
- Inspected tracked Goal 027 protocol authority, Goal 029's final five-family
  decision/configuration, Goal 030's namespace seal, existing package/test
  structure, and locked dependency declaration. No ignored/private path,
  model product, or outer assessment was opened.
- Froze the exact eight targets, seven endpoints, five folds, 24 architecture
  candidates, six methods, valid auxiliary reuse, full planner arithmetic,
  balanced 125-cell fixture, and the 23-fit CPU sentinel.
- Defined split-fitted leave-target-out auxiliary construction,
  pseudoabsence exclusion, unknown masking, species-balanced contribution,
  scalar-q anti-circularity, transfer-equivalence tests, deterministic
  receipts, and aggregate-evidence privacy rules.
- Created only the five Goal 031 design/execution packet files. No test,
  production code, configuration, evidence, fixture, model fit, prediction,
  metric, private-data operation, outer operation, commit, or push was run or
  created.
- Status: design ready for orchestrator review; implementation remains gated.

## 2026-08-07 - Execution contract and Task 1 RED/GREEN

- Accepted design repair froze CPU float32, one Torch thread, deterministic
  algorithms, split-training-only scaling, full-batch BCE, 12 AdamW epochs at
  `0.001`, no scheduler/early stopping, loss weighting, and exact `q_linear`
  settings in the packet and new config.
- RED: `uv run --locked pytest -q tests/test_dsdm_contracts.py` failed during
  collection with the intended `ModuleNotFoundError: No module named 'dsdm'`.
- GREEN: after adding the minimum package and strict contract/planner,
  the same command passed `13 passed`. Exact arithmetic is 56 endpoints, 336
  method strata, 8,400 target fits, 440 auxiliary fits, 8,840 final-lifecycle
  fits, 1,440 architecture-selection fits, and 10,280 combined fits.

## 2026-08-07 - Task 2 model RED/GREEN

- RED: `uv run --locked pytest -q tests/test_dsdm_models.py` failed during
  collection with the intended `ModuleNotFoundError: No module named
  'dsdm.models'`.
- GREEN: after adding the minimum residual block, matched residual learner,
  shared-trunk multi-head learner, exact state cloning/loading, and trunk
  freezing, the same command passed `6 passed`. Tests instantiate all 24
  architectures and verify finite logits, matched trunk/head shapes, the
  28-versus-29 input-stem boundary, exact clone independence, and head-only
  trainability under freezing.

## 2026-08-07 - Task 3 training RED/GREEN

- RED: `uv run --locked pytest -q tests/test_dsdm_training.py` failed during
  collection with the intended `ModuleNotFoundError: No module named
  'dsdm.training'`.
- GREEN: after adding strict observation validation, leave-target-out
  auxiliary selection, mean-of-species loss, split-only scaling, frozen
  `q_linear`, deterministic CPU seeding, 12-epoch full-batch neural fitting,
  and shared-trunk transfer, the command passed `10 passed in 1.27s` with no
  warnings. Tamper cases cover target, pseudoabsence, unknown, held-fold, and
  predictor-width leakage; state tests distinguish frozen from full tuning.
- Focused follow-on RED for q-linear contribution failed at import because
  `q_linear_sample_weights` did not exist. GREEN passed `11 passed in 1.29s`
  after adding weights whose total contribution is equal by species while
  leaving within-species classes unbalanced.

## 2026-08-07 - Tasks 4--5 fixture, lifecycle, and receipt RED/GREEN

- RED: `uv run --locked pytest -q tests/test_dsdm_synthetic_vertical.py`
  failed during collection with the intended `ModuleNotFoundError: No module
  named 'dsdm.synthetic_vertical'`.
- GREEN: after adding the in-memory 125-cell fixture, exact nested endpoint
  selector, pooled/multi-head/q pretraining, all six target paths, two extra
  architecture fits, aggregate writer, CLI, and independent validator, the
  command passed `8 passed in 2.50s`. It includes two complete sentinel runs
  with identical in-memory execution-state digests.
- CLI `plan` executed zero fits and reported 960/480 architecture fits, 440
  auxiliary fits, 8,400 target fits, 8,840 final-lifecycle fits, and 10,280
  combined declarative fits. Outer attempted/open was `0/0`.
- CLI `run` completed the exact 23-fit sentinel in `1.63 s` wall time; `validate`
  passed, a repeat receipt was byte-identical, and all 20 target fits produced
  finite held-fold outputs without serializing them.
- Published and independently validated the aggregate receipt at
  `evidence/dsdm_synthetic_vertical/goal031/receipt.json`; file SHA-256 is
  `6d66ff98b422edb60542c5334ccabadcc1ebccdf2b6060b1c25d5b09a50e5725`.
  The defence-in-depth privacy scan returned no forbidden match.

## 2026-08-07 - Proportional gates and single review pass

- Safe tracked-only upstream regressions passed `29 passed in 1.11s` for
  modelling contracts, target subsets, and inner CV. No full suite or private
  replay ran.
- All four Goal 031 suites initially passed `38 passed in 2.62s`; `uv lock
  --check`, tracked and untracked whitespace checks, protected-namespace scan,
  receipt validation, and privacy scan passed.
- The one focused review found that receipt validation reused the writer's
  expected-payload helper. A new independence test produced the intended RED:
  `1 failed` with `AssertionError: validator reused writer`. The validator now
  reconstructs the expected schema and aggregates independently; the affected
  suite passed `9 passed in 2.64s`.
- Post-repair Goal 031 verification passed `39 passed in 2.74s`; the accepted
  receipt still validates and the lock, whitespace, privacy, CPU-only, and
  Phase 1 isolation checks remain clean. Only the authorized Goal 031 paths are
  untracked. No commit or push was made.
- Residual limit: this synthetic slice verifies computation, leakage, transfer,
  reuse, and evidence boundaries only. It does not resolve real-data detection,
  mixed-zero, spatial-dependence, calibration, identifiability, extrapolation,
  architecture-selection, or ecological-performance risks.

## 2026-08-07 - Independent review repair RED/GREEN

- Frozen-trunk RED: the focused test failed because `frozen.stem.training` was
  `True`. GREEN passed `1 passed`; stem, trunk, dropout, and final normalization
  now remain in evaluation mode while the target head trains.
- Matched-randomization RED: the actual-state test failed because
  `prepare_target_model` did not exist and method-specific construction was
  embedded in the runner. GREEN passed `1 passed`; fit seeds now exclude
  method, common target states are prepared explicitly, 28-input target heads
  are paired, frozen/full multi-head states are byte-identical, q-control
  states are byte-identical, and legacy whole-state transfer is retained.
- Fixture-validation RED: six one-field tamper cases plus broken nesting and
  pre-fit ordering failed `8 failed` because no fixture validator existed.
  GREEN passed `8 passed`; the complete species-cell, fold, provenance, label,
  predictor, composition, and nesting contract is checked before fitting.
- Receipt-binding RED: separate-run repeat, fabricated digest, structurally
  valid alternate fixture, and rehashed fabrication tests failed `4 failed`
  against the old three-argument writer. GREEN passed `4 passed`; writer input
  now includes the executed fixture and validation independently regenerates
  and re-executes the sentinel.
- The single final bounded gate passed Goal 031 as `51 passed in 4.58s` and
  safe upstream regressions as `29 passed in 1.03s`. Separate sentinel runs
  produced byte-identical receipts; one run took `1.65 s`. Independent
  validation re-executed successfully. Privacy, lock, tracked/untracked
  whitespace, and diff gates passed; outer attempted/open remained `0/0`.
- The regenerated receipt records fixture digest
  `8429b06151566bed36e290ccbef6ff3f96c36179c576b55a04fcd8ee2bed1857`,
  execution digest
  `3f09472697837daff3be5cbec6841d274d8926d82dc15bee9d30a1549a642b7c`,
  semantic receipt digest
  `ccf69b3d49fe745eb29f147321a2dfa4f3dd4447a04444dc02be76d9ebab67ce`,
  and file SHA-256
  `be9cc1d888f5bf3117868e18c8902a177f4cb22a02668c24afe0725eabdc4e2c`.
