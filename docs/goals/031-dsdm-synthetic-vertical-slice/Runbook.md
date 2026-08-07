# Runbook

This is the post-acceptance execution runbook. The design checkpoint does not
authorize these implementation commands. Run from the dSDM repository root in
the locked Python 3.12 environment, and do not open ignored/private paths.

## RED then GREEN component gates

For each task, first run the named test before its production surface exists or
contains the new behaviour and record the intended failure in `Log.md`. Only
then implement and rerun the same command to GREEN.

```sh
uv run --locked pytest -q tests/test_dsdm_contracts.py
uv run --locked pytest -q tests/test_dsdm_models.py
uv run --locked pytest -q tests/test_dsdm_training.py
uv run --locked pytest -q tests/test_dsdm_synthetic_vertical.py
```

RED is valid only when the assertion fails for the intended missing behaviour,
not from an import, syntax, environment, or fixture mistake after the initial
package scaffold. Every later production behaviour needs its own witnessed
failing assertion.

## CLI plan, run, repeat, and validate

Use a narrow temporary directory. `plan` must report 24 candidates, four
shortlisted candidates, 56 target endpoints, 336 method strata, 8,400 final
target fits, 440 reusable auxiliary fits, 8,840 final-lifecycle fits, 1,440
architecture-selection fits, 10,280 combined declarative fits, and outer
attempted/open `0/0`, while fitting nothing.

```sh
goal031_run_dir=$(mktemp -d)
uv run --locked python -m dsdm.synthetic_vertical \
  --config config/dsdm_synthetic_vertical.json \
  plan --output "$goal031_run_dir/plan.json"
/usr/bin/time -p uv run --locked python -m dsdm.synthetic_vertical \
  --config config/dsdm_synthetic_vertical.json \
  run --output "$goal031_run_dir/receipt-a.json"
uv run --locked python -m dsdm.synthetic_vertical \
  --config config/dsdm_synthetic_vertical.json \
  validate --receipt "$goal031_run_dir/receipt-a.json"
uv run --locked python -m dsdm.synthetic_vertical \
  --config config/dsdm_synthetic_vertical.json \
  run --output "$goal031_run_dir/receipt-b.json"
cmp "$goal031_run_dir/receipt-a.json" "$goal031_run_dir/receipt-b.json"
```

Expected sentinel invariants are target `sarcophilus_harrisii`, fold `fold00`,
seed `31031`, target endpoint sizes 20/40/80, auxiliary usable rows 392, six
methods, three sentinel architectures, 20 target fits, three auxiliary fits,
23 total fits, and outer attempted/open `0/0`. The first `run` must have real
wall time below 60 seconds. Receipts must be byte-identical.

Validation must also confirm CPU float32, one Torch thread, deterministic
algorithms, split-training-fitted scaling, full-batch BCE, exactly 12 epochs,
AdamW learning rate `0.001`, no scheduler/early stopping, architecture weight
decay, and the fixed single-thread `q_linear` contract.

`run` validates the fixture before fitting and records only aggregate fixture
counts plus fixture/execution SHA-256 digests. The repeated receipt must come
from a separately generated fixture and separately executed sentinel, not from
writing one result twice. `validate` independently regenerates the fixture and
re-executes the sentinel before comparing both digests and all aggregate
counts. Its runtime therefore includes one complete 23-fit sentinel.

The receipt must also state the non-secret pairing contract: method is absent
from target initialization/fit seeds; the 28-input common target head is
preserved under multi-head transfer; frozen/full multi-head and both 29-input q
controls begin byte-paired; and legacy transfer replaces the complete state.

After all tests and privacy gates pass, write the same deterministic receipt to
the new evidence path and independently validate it:

```sh
uv run --locked python -m dsdm.synthetic_vertical \
  --config config/dsdm_synthetic_vertical.json \
  run --output evidence/dsdm_synthetic_vertical/goal031/receipt.json
uv run --locked python -m dsdm.synthetic_vertical \
  --config config/dsdm_synthetic_vertical.json \
  validate --receipt evidence/dsdm_synthetic_vertical/goal031/receipt.json
```

## Privacy and tamper gates

The focused tests must mutate, one at a time, target inclusion, pseudoabsence
inclusion, unknown masking, held-fold inclusion, species/label/identifier
features, subset nesting, architecture counts, receipt counts/digests, and
outer counts. Every mutation must fail closed.

The receipt schema and independent validator must reject any key or value that
represents row IDs, cell IDs, response labels, predictions, species-cell
records, absolute/private paths, model weights/checkpoints, AUC/TSS/other
metrics, or performance claims. Run a final text scan as defence in depth:

```sh
! rg -n -i \
  'row.?id|cell.?id|grid.?cell|response.?label|prediction|species.?cell|/Users/|data/|tas_cam/|temp/|auc|tss|mcc|accuracy|performance|checkpoint|state_dict' \
  evidence/dsdm_synthetic_vertical/goal031/receipt.json
```

The expected result is no match. This scan supplements, not replaces, schema
validation.

## Proportional final gates

Do not run the full repository suite: authorized private replay tests exist.
These tracked-only upstream regressions are directly relevant to split roles,
target nesting, and modelling contracts:

```sh
uv run --locked pytest -q \
  tests/test_modeling_contract.py \
  tests/test_target_subsets.py \
  tests/test_inner_cv.py
uv run --locked pytest -q \
  tests/test_dsdm_contracts.py \
  tests/test_dsdm_models.py \
  tests/test_dsdm_training.py \
  tests/test_dsdm_synthetic_vertical.py
uv lock --check
git diff --check
git status --short --branch
```

Verify the diff changes only the accepted Goal 031 surfaces and does not alter
`src/dsdm_phase1/`, Goal 029 config/evidence/products, `pyproject.toml`, or
`uv.lock`. Perform one focused review/repair pass, then stop without commit or
push.
