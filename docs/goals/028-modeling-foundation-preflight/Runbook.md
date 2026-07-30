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
