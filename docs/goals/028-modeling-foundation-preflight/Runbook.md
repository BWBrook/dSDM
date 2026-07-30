# Runbook

Run from the repository root. The implementation agent is authorised to edit
the files named in the detailed plan, let `uv` install/resolve the approved
Python 3.12 dependencies, run these commands, and generate ignored private and
tracked aggregate Goal028 artefacts. The implementation agent is **not**
authorised to commit or push.

## Environment and lock

```sh
uv python pin 3.12
uv sync --locked
uv run python -VV
uv lock --check
```

Do not continue if the active interpreter is not Python 3.12 or the lock does
not match `pyproject.toml`.

## Focused TDD ladder

```sh
uv run pytest -q tests/test_modeling_contract.py
uv run pytest -q tests/test_target_subsets.py
uv run pytest -q tests/test_model_adapters.py
uv run pytest -q tests/test_inner_cv.py
uv run pytest -q tests/test_goal028_preflight.py -m "synthetic"
```

## Synthetic full and tamper gate

```sh
uv run python -m dsdm_phase1.goal028_preflight --root . --mode synthetic
uv run python -m dsdm_phase1.goal028_preflight --root . --validate --synthetic --full
uv run pytest -q tests/test_goal028_preflight.py -m "synthetic or tamper"
```

The synthetic fake vault may exercise final-score plumbing. Its manifest must
state `synthetic=true`; it cannot mint or validate a real unlock.
Synthetic tests must also prove that each assessment fold receives its own
endpoint, encoder state is fitted once on that complete endpoint and reused,
assessment batches never enter `fit`, selection never crosses family/seed
strata, canonical external full identity is only `fraction100/full`, complete
neural fold receipts preserve matching discovery/replay initial states, and
serialized models reject feature-schema/order drift.

Model load and `replay_predictions` tests must supply a separately trusted
lowercase SHA-256 from the frozen manifest, reject missing/self-authorised
digests, validate the envelope before unpickling, and reject schema,
candidate, seed, runtime-version, or payload identity drift.

## Bounded real preflight

```sh
uv run python -m dsdm_phase1.goal028_preflight --root . --mode real-preflight
uv run python -m dsdm_phase1.goal028_preflight --root . --validate --real-preflight --full
```

This command is authorised only for `sarcophilus_harrisii` and
`pseudocheirus_peregrinus`, only for the explicit reduced candidate rows, and
only for inner OOF/refit/replay. It must report
`outer_attempted_open_count=0` and `outer_open_count=0`. It must not produce
real outer predictions, scores, metrics, maps, or ecological claims. Poor AUC
is not failure. Any leakage/access, class, nonfinite, OOF-integrity, nesting,
pairing, replay, reproducibility, conventional convergence failure, or
PyTorch hard failure is a hard stop with no partial publication. A finite
valid neural checkpoint ending with `max_epochs_reached` is a warning, not
automatic failure.

The real validator must reconstruct split features only through the sole
private ingestion factory from digest-verified Goal024 raw predictors,
Goal025 partitions, and Goal026 contract/fit parameters. It must reject any
injected `private_inputs.features`-style payload. For Goal028 selection, only
`seed00` contributes to RowKey-aligned fold AUC/TSS; `seed01` remains a paired
neural replay diagnostic.

Validation must recompute all candidate fold/global metrics from OOF evidence,
permit residual tuning only within the residual family, reject residuals from
conventional-baseline competition, require integer completed-epoch receipts,
and test the upper-score threshold fallback when adjacent scores have no
representable midpoint.

## Full local validation

```sh
uv run pytest -q
uv run python -m py_compile \
  src/dsdm_phase1/modeling_contract.py \
  src/dsdm_phase1/target_subsets.py \
  src/dsdm_phase1/model_adapters.py \
  src/dsdm_phase1/inner_cv.py \
  src/dsdm_phase1/goal028_preflight.py
uv lock --check
git diff --check
git status --short
```

The executor returns the exact changed paths, dependency/lock result, focused
and full test results, synthetic and real validation summaries, outer access
counts, convergence/runtime/memory warnings, evidence/private footprints, and
remaining uncertainty. Stop without `git add`, `git commit`, or `git push`.
The report must distinguish `patience_stop` from `max_epochs_reached` and give
both attempted and successful outer-open counts.
