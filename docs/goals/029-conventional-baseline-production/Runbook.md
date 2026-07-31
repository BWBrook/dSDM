# Runbook

Run from the repository root under the locked Python 3.12 environment.

## Engineering and synthetic gates

```sh
uv sync --locked
uv lock --check
uv run pytest -q tests/test_model_adapters.py tests/test_goal029_production.py
uv run pytest -q \
  tests/test_goal028_preflight.py \
  tests/test_inner_cv.py \
  tests/test_model_adapters.py
uv run python -m dsdm_phase1.goal029_production --root . --mode plan
uv run python -m dsdm_phase1.goal029_production --root . --mode synthetic
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode synthetic --validate
```

Synthetic output must use the synthetic vault only. It is disposable and may
be removed after validation. The exact synthetic plan has 33 candidate-seed
leaves, five selected families, and 17 selected refits. It exercises
candidate failure handling, family quorum, selected refit, deterministic model
replay, paired publication, source audit, privacy, and partial/unmarked
rejection.

The active synthetic and planning receipts must bind config schema `1.5`,
protocol `0.5`, and the five-family registry. Historical pyGAM and
penalised-spline stages are read-only diagnostic evidence: do not resume,
delete, publish, or use them as calibration or production authority.

## Real calibration

Run only after separate orchestrator authorization:

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode calibration
```

The command performs:

1. the four-child zero-fit spawn proof under the one-thread policy;
2. the 56-stratum class-support scan;
3. the frozen two-leaf canary at workers 1 and 2, producing four executions
   and 20 fits; and
4. the frozen 28-leaf representative panel at workers 1, 2, and 4, producing
   84 executions and 525 fits.

The estimator-bearing total is exactly 88 executions and no more than 545
fits. The four spawn children perform zero fits. There is no GAM feasibility
stage or candidate gate after worker selection.

The worker-selection, canary-ratio, memory, swap, process-spawn, and native
thread-pool rules remain frozen and fail closed. The calibration receipt must
use master/index version `4`, contain no obsolete gate schema, stage, or
fields, and report real outer attempted/open counts `0/0`.

Calibration stores only bounded execution evidence and semantic hashes. It
must not retain assessment metrics, thresholds, labels, row identifiers,
prediction values, private paths, or raw exception messages.

## Real production

Run only after the five-family calibration has published accepted authority:

```sh
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production
uv run python -m dsdm_phase1.goal029_production \
  --root . --mode production --validate
```

Production rejects missing, failed, stale, modified, or context-incompatible
calibration evidence. It must plan exactly five families, 280 family strata,
1,736 candidate strata, 6,888 candidate-seed leaves, 34,440 OOF units, 42,840
estimator fits, at most 952 selected refits, and 345 source-audit leaves.

Any historical GAM candidate, feasibility-gate receipt, gate overlay, or stale
schema/protocol appearing in active authority is a hard stop. Goal028's legacy
replay remains valid only in its own frozen context; dormant penalised-spline
artifacts are not Goal029 production inputs.

Late-stage restart may regenerate only the explicitly permitted source-audit
and transaction metadata. It must preserve checkpoints, selections, models,
memberships, encoders, and failure receipts. Any symlink, unknown inventory
entry, provenance drift, or existing final destination remains a hard stop.

Never open, predict, score, summarize, or inspect the real outer vault during
calibration or conventional production. Publication remains forbidden until
staged artifact validation, the fresh 345-leaf source audit, paired
transaction validation, and the final marker all pass.

## Final engineering gate

```sh
uv run pytest -q
uv run python -m py_compile \
  src/dsdm_phase1/inner_cv.py \
  src/dsdm_phase1/model_adapters.py \
  src/dsdm_phase1/goal029_production.py
uv lock --check
git diff --check
git status --short --branch
```

The completion report must separate engineering validity from scientific
performance and state real outer attempted/open counts exactly.
