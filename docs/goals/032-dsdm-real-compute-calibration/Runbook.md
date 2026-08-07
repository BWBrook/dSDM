# Runbook

This runbook becomes executable only after the Goal032 implementation is
present and reviewed. Commands must run from the dSDM repository root. Do not
substitute real architecture-search or outer-assessment commands.

## Focused gates

```sh
uv run --locked pytest -q tests/test_dsdm_real_data.py
uv run --locked pytest -q tests/test_dsdm_real_training.py
uv run --locked pytest -q tests/test_dsdm_compute_canary.py
```

The tests must cover binding-hash drift, eight-species/fold/endpoint replay,
77/78-column schemas, auxiliary exclusions, de-identification, stop-fold
rotation, exact reset/replay, deterministic repeat digests, workload counts,
outer counters, unknown receipt fields, and privacy mutations.

## Plan and local bundle

```sh
goal032_dir=$(mktemp -d)
uv run --locked python -m dsdm.compute_canary \
  plan --config config/dsdm_real_compute_calibration.json \
  > "$goal032_dir/plan.json"
uv run --locked python -m dsdm.compute_canary \
  export --config config/dsdm_real_compute_calibration.json \
  --output data/processed/dsdm/goal032-real-compute-calibration/final/bundles
uv run --locked python -m dsdm.compute_canary \
  validate-bundle --config config/dsdm_real_compute_calibration.json \
  --bundle data/processed/dsdm/goal032-real-compute-calibration/final/bundles
```

`plan` performs zero fits. `export`, implemented through `dsdm.real_data`, is
the only local path authorised to call the sealed Goal029 foundation. The
remote path uses `dsdm.real_training` through `dsdm.compute_canary` and must
validate a bundle without importing Phase1 or opening any repository-private
product. The exported label-free inner held-fold predictor is named `x_held`;
it is drawn from outer-training and is not the sealed outer assessment.

## Host execution

Before execution, the operator must create or validate an isolated
Goal032 environment with Python 3.12, NumPy 2.2.6, and PyTorch 2.7.1. Use the
official CPU wheel on Mac/deep-server and the official cu118 wheel on Alien;
validate Alien's driver as 546.01. Do not install into the repository
environment or alter `pyproject.toml`/`uv.lock`. The host receipt records these
versions and wheel role. Goal033 will freeze its production runtime separately.

For each of `mac_cpu`, `deep_server_cpu`, and `alien_cuda`, stage only
`src/dsdm/{__init__,contracts,models,real_data,real_training,compute_canary}.py`,
the Goal032 config, and the three content-addressed bundles. Use
`deep-server-ts` and `alien-wsl` externally; the Python command itself never
opens SSH or private source data. Set `GOAL032_PYTHON` to that host's isolated
interpreter and execute the exact three cases twice in serial:

```sh
PYTHONPATH=src "$GOAL032_PYTHON" -m dsdm.compute_canary \
  serial --config config/dsdm_real_compute_calibration.json \
  --host HOST_ID \
  --bundle data/processed/dsdm/goal032-real-compute-calibration/final/bundles \
  --output data/processed/dsdm/goal032-real-compute-calibration/final/private/HOST_ID/serial
```

After all serial receipts validate, select the provisional leader and run only
its six-task panel:

```sh
PYTHONPATH=src "$GOAL032_PYTHON" -m dsdm.compute_canary \
  concurrency --config config/dsdm_real_compute_calibration.json \
  --host LEADING_HOST_ID \
  --bundle data/processed/dsdm/goal032-real-compute-calibration/final/bundles \
  --output data/processed/dsdm/goal032-real-compute-calibration/final/private/LEADING_HOST_ID/concurrency
```

These commands are bounded foreground calibration. Do not start a persistent
`tmux` session or the architecture screen.

## Recommendation and validation

```sh
uv run --locked python -m dsdm.compute_canary \
  recommend --config config/dsdm_real_compute_calibration.json \
  --private-root data/processed/dsdm/goal032-real-compute-calibration/final/private \
  --output evidence/dsdm_real_compute_calibration/goal032/receipt.json
uv run --locked python -m dsdm.compute_canary \
  validate --config config/dsdm_real_compute_calibration.json \
  --private-root data/processed/dsdm/goal032-real-compute-calibration/final/private \
  --receipt evidence/dsdm_real_compute_calibration/goal032/receipt.json
```

The final validator reopens all three sibling bundles and recomputes the
receipt from the 24 private rows. It requires 24 logical evaluations, 48
physical fits, one bundle digest per case across hosts, identical Mac
serial/concurrency semantics, 1,440/2,880 projected architecture
logical/physical work, outer `0/0`, and one compute recommendation. It must not
contain ecological metrics or private payloads.

## Final proportional checks

```sh
uv run --locked pytest -q \
  tests/test_dsdm_contracts.py \
  tests/test_dsdm_models.py \
  tests/test_dsdm_training.py \
  tests/test_dsdm_synthetic_vertical.py \
  tests/test_dsdm_real_data.py \
  tests/test_dsdm_real_training.py \
  tests/test_dsdm_compute_canary.py
uv lock --check
git diff --check
git status --short --branch
```

Privacy-scan the tracked receipt for identifiers, coordinates, raw paths,
labels, predictions, loss values, and AUC/TSS/MCC/PR-AUC language. Inspect that
`src/dsdm_phase1/`, `pyproject.toml`, and `uv.lock` are unchanged. Perform one
focused review/repair pass. Implementation workers then stop without commit or
push; after acceptance, the orchestrator may publish under Barry's standing
authority.
