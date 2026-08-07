# Goal 031 implementation plan

> **Status:** design checkpoint only. Do not execute until the orchestrator
> accepts this packet. Every new production behaviour requires a witnessed
> failing test before implementation. No commit or push is authorised.

**Goal:** Build one deterministic CPU-only synthetic vertical slice that proves
the approved dSDM planner, six-method ladder, and leakage boundaries end to end.

**Architecture:** Immutable contracts and a machine-readable configuration
drive a focused model layer, split-scoped training layer, and fixture/planner/
run/validate CLI. No Phase 1 source is imported or changed. Auxiliary artifacts
are cloned and reused only where `Decision.md` permits.

**Tech stack:** Python 3.12, NumPy, scikit-learn, PyTorch, pytest, and the
existing locked `uv` environment. Add no dependency.

**Execution freeze:** CPU float32, one Torch thread, deterministic Torch
algorithms, split-training-only `StandardScaler`, full-batch
`BCEWithLogitsLoss`, 12 epochs per neural fit, AdamW `lr=0.001`, no scheduler
or early stopping, unweighted target loss, mean-of-seven-species auxiliary
loss, and the fixed `q_linear` settings in `Decision.md`.

## Global constraints and file ownership

Create only these implementation surfaces after acceptance:

- `config/dsdm_synthetic_vertical.json`: exact registry, axes, fixture,
  sentinel, optimiser, and evidence contract;
- `src/dsdm/__init__.py`: narrow public exports and package version;
- `src/dsdm/contracts.py`: frozen dataclasses/enums, config parsing,
  validation, endpoint construction, and planner arithmetic;
- `src/dsdm/models.py`: residual/scalar/single-head/multi-head networks and
  state-cloning/freezing helpers;
- `src/dsdm/training.py`: deterministic seeding, split-fitted preprocessing,
  auxiliary filtering/balancing, q fitting, target fitting, and transfer;
- `src/dsdm/synthetic_vertical.py`: deterministic fixture plus CLI
  `plan`, `run`, and `validate`;
- `tests/test_dsdm_contracts.py`, `tests/test_dsdm_models.py`,
  `tests/test_dsdm_training.py`, and
  `tests/test_dsdm_synthetic_vertical.py`: tests bounded by concern; and
- `evidence/dsdm_synthetic_vertical/goal031/receipt.json`: aggregate-only
  deterministic accepted receipt.

Do not modify protected files listed in `Goal.md`. Do not run the full test
suite or any private replay. Record every RED and GREEN command/result in
`Log.md`.

## Exact planned and executed counts

| Surface | Exact count |
|---|---:|
| Ordered targets | 8 |
| Predictors | 28 |
| Inner folds | 5 |
| Endpoints per target | 7 |
| Target-endpoint strata | 56 |
| Methods | 6 |
| Method strata | 336 |
| Method-fold strata | 1,680 |
| Final target fits at five seeds | 8,400 |
| Reused final auxiliary fits | 440 |
| Full final-lifecycle fits | 8,840 |
| Architecture candidates / shortlist | 24 / 4 |
| Architecture screen / shortlist fits | 960 / 480 |
| Combined declarative fits | 10,280 |
| Sentinel architectures | 3 |
| Sentinel target / auxiliary / total fits | 20 / 3 / 23 |

## Task 1 - Contracts, configuration, and full planner

**Interfaces:** `load_contract(path) -> ExperimentContract`,
`validate_contract(contract) -> None`, and
`build_plan(contract) -> PlanSummary`. `PlanSummary` exposes only immutable
axis names and the exact aggregate counts above.

1. **RED:** Write contract tests for the exact species order, folds, seven
   endpoints and nesting, six methods, 24 unique architectures, fixed
   activation/norm, planner arithmetic, and rejection of an altered species,
   endpoint, outer count, method, candidate, or reuse rule. Run the focused
   file and witness failures due to the absent package/config.
2. **GREEN:** Add the minimum immutable types, strict JSON loader, registry,
   endpoint builder, and aggregate planner. Reject unknown or missing keys;
   never infer or repair config. Run the focused tests to pass.
3. Record RED/GREEN evidence before starting Task 2.

## Task 2 - Residual, pooled, scalar, and multi-head models

**Interfaces:** `build_residual(spec, input_dim, output_dim) -> nn.Module`,
`clone_state(model) -> StateDict`, `load_transfer(model, state) -> None`, and
`set_trunk_trainable(model, trainable) -> None`. The trunk shape is identical
across matched paths; only the input stem changes from 28 to 29 for q controls.

1. **RED:** Test all 24 registry entries instantiate with valid dimensions;
   three sentinel candidates produce finite outputs; target-only and transfer
   trunks/heads have equivalent shapes; clone/load is exact; freezing changes
   only head gradients; and an invalid head, input width, or architecture is
   rejected. Witness the absent-model failures.
2. **GREEN:** Implement only the input stem, bottleneck residual block, shared
   trunk, scalar head, and multi-head wrapper required by those tests. Run the
   model tests to pass.
3. Record RED/GREEN evidence before starting Task 3.

## Task 3 - Split-scoped training, q controls, and transfer semantics

**Interfaces:** `select_auxiliary(rows, target, train_fold_ids)`,
`species_balanced_loss(losses, species)`,
`fit_pooled_single_head(...)`, `fit_multi_head(...)`, `fit_q_linear(...)`, and
`fit_target(method, endpoint, pretrained) -> FitSummary`. Fit summaries contain
counts/status and in-memory state only; they expose no labels or predictions to
receipts.

1. **RED leakage/tamper:** Prove training fails when the target species,
   pseudoabsence, unknown response, held-fold cell, species identity feature,
   target label feature, row/cell identifier, or non-training-fitted transform
   enters auxiliary construction. Prove unknown target rows never reach loss.
2. **RED balance/reuse:** With unequal auxiliary row counts, prove the loss is
   the mean of within-species means, not a row-weighted or class-balanced mean.
   Prove one pooled artifact supplies both legacy initialisation and the exact
   `q_deep` scalar, one multi-head state supplies frozen/full clones, frozen
   trunks remain byte-identical after target fitting, full-fine-tuned trunks
   change, and endpoint fits do not share target state.
3. **GREEN:** Implement deterministic CPU seeding, split-fitted scaling,
   fail-closed auxiliary selection, species-balanced loss, fixed-hyperparameter
   elastic-net q, full-batch AdamW loops, and explicit state cloning. Run the
   focused training and model tests to pass.
4. Record RED/GREEN evidence before starting Task 4.

## Task 4 - Deterministic fixture and plan CLI

**Interfaces:** `make_fixture(contract) -> SyntheticFixture`,
`summarize_fixture(fixture) -> AggregateFixtureSummary`, and CLI
`python -m dsdm.synthetic_vertical --config PATH plan --output PATH`.

1. **RED:** Test exact fixture totals 125 cells/1,000 species-cell records,
   per-fold 8/6/6/5 provenance, 20/40/80 nested ladder composition, 392-row
   leave-target-out auxiliary pool, five allowed fold labels, 28 predictors,
   and zero outer rows. Tamper tests must reject broken nesting, provenance,
   masking, fold scope, predictor count, or any outer row.
2. **GREEN:** Implement an in-memory seeded generator and aggregate planner;
   do not create a row-level fixture file. Make `plan` emit deterministic
   aggregate JSON with full counts but perform zero fits.
3. Run focused contract/fixture/CLI-plan tests and record RED/GREEN evidence.

## Task 5 - Six-path sentinel, deterministic receipt, and validator

**Interfaces:** CLI `run --output PATH` executes the exact sentinel; CLI
`validate --receipt PATH` independently reconstructs expected contract/counts,
checks digests/privacy/outer `0/0`, and exits nonzero on any difference.

1. **RED lifecycle:** Test exact target/fold/seed, three ladder00 endpoints,
   all six method paths, three architectures, 20 target fits, three valid
   auxiliary fits, and 23 total fits. Prove no auxiliary artifact is refit per
   fraction and no target state is reused.
2. **RED evidence:** Test two runs are byte-identical; validator rejects an
   altered digest/count/method/privacy field/outer count; and the receipt
   schema cannot serialize identifiers, labels, predictions, species-cell
   records, paths, metrics, performance claims, weights, or checkpoints.
3. **GREEN:** Implement the minimum orchestrator and canonical sorted JSON
   writer. Keep predictions and labels in memory only long enough to verify
   finite shape; summarize completion as aggregate counts. Implement the
   validator independently of the writer's output objects.
4. Run all four Goal 031 test files and the CLI plan/run/validate lifecycle.
   Confirm one run is below 60 seconds on this Mac CPU.

## Task 6 - Proportional regression and closeout

1. Run only the safe upstream contract/subset/fold regressions named in
   `Runbook.md`, then `uv lock --check` and `git diff --check`.
2. Inspect the diff against this packet. Check exact count arithmetic, model
   interface/type consistency, protected paths, evidence keys, and each
   witnessed RED entry. Run one focused repair pass only if a material defect
   is found, then rerun the affected focused gate.
3. Update `Log.md` and `Decision.md` with exact results and residual limits.
   Stop without real data, outer work, commit, or push and return to the
   orchestrator for acceptance.

## Accepted review repair

1. Add RED tests showing invalid fixtures stop before fitting and covering
   unknown-label promotion, provenance/label mismatch, cell/fold drift,
   duplicate/missing pairs, predictor mismatch/non-finiteness, and broken
   ladder nesting. Validate the complete fixture and derive executed subset
   sizes before model construction.
2. Add RED state tests for method-free target seeds, common 28-input heads,
   byte-identical frozen/full multi-head initial states, common 29-input q
   states, legacy whole-state transfer, and evaluation-mode frozen trunks.
3. Add RED evidence tests using two independent sentinel executions, a
   fabricated result, a structurally valid alternate fixture, and a correctly
   rehashed fabricated bundle. Bind the receipt to the executed fixture and
   execution digests; independently regenerate and re-execute during
   validation.
4. Regenerate the canonical aggregate receipt, run the existing proportional
   gates once, and stop without protected edits, commit, or push.
