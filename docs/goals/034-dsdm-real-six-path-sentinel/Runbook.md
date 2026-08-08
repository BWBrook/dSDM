# Runbook

Run from the repository root. The export command is local-only; training
commands consume the portable bundle and do not import Phase 1.

## Focused gates

```sh
uv run --locked pytest -q tests/test_dsdm_real_six_path.py
uv run --locked python -m py_compile \
  src/dsdm/real_six_path.py src/dsdm/real_six_path_data.py
uv lock --check
git diff --check
```

## Plan and export

```sh
uv run --locked python -m dsdm.real_six_path \
  --config config/dsdm_real_six_path_sentinel.json plan \
  --output data/processed/dsdm/goal034-real-six-path-sentinel/private/plan.json

uv run --locked python -m dsdm.real_six_path \
  --config config/dsdm_real_six_path_sentinel.json export \
  --root . \
  --output data/processed/dsdm/goal034-real-six-path-sentinel/private/bundle

uv run --locked python -m dsdm.real_six_path \
  --config config/dsdm_real_six_path_sentinel.json validate-bundle \
  --bundle data/processed/dsdm/goal034-real-six-path-sentinel/private/bundle
```

## Matched route runs

Use Python 3.12 with NumPy 2.2.6, SciPy 1.16.3, scikit-learn 1.9.0,
threadpoolctl 3.6.0, and PyTorch base 2.7.1. The ordinary repository export
environment is not a substitute for this exact fit runtime. Run these twice
on Mac with `DEVICE=cpu`, and twice on Alien with `DEVICE=cuda`.
On Alien, set `CUBLAS_WORKSPACE_CONFIG=:4096:8` and keep both repeats on the
same GPU. An indexless `--device cuda` explicitly selects GPU 0. Stage the two
dSDM modules, `contracts.py`, `models.py`, the config,
all files named under its `authorities`, and the single bundle; do not stage
the raw foundation or camera data.

```sh
PYTHONPATH=src python -m dsdm.real_six_path \
  --config config/dsdm_real_six_path_sentinel.json run \
  --bundle BUNDLE --device DEVICE --output RUN_1.json

PYTHONPATH=src python -m dsdm.real_six_path \
  --config config/dsdm_real_six_path_sentinel.json run \
  --bundle BUNDLE --device DEVICE --output RUN_2.json

PYTHONPATH=src python -m dsdm.real_six_path \
  --config config/dsdm_real_six_path_sentinel.json validate-run \
  --bundle BUNDLE --receipt RUN_1.json --repeat RUN_2.json
```

Compare routes only after both pairs validate, their `source_fingerprint` and
`runtime.shared_fingerprint` are equal, and each pair has identical selected,
executed, and replay epochs plus model/prediction digests. Total and
per-artifact wall times may differ. Do not require CPU/CUDA model digest
equality. Do not launch the 8,840-artifact lifecycle or open the outer
assessment; those require a later authorized goal and runner.

## Accepted route and handoff

The matched run is complete. The aggregate-only receipt is
`evidence/dsdm_real_six_path_sentinel/goal034/receipt.json`; it freezes
`mac_cpu` with three independent workers and one numerical thread per worker.
The later full lifecycle must use an identity-addressed, resumable private
runner under `tmux`, retain the Goal034 source/runtime/bundle gates, and keep
outer access at `0/0`. It must also record finite q-linear coefficient,
decision-value, and probability ranges so the Mac numerical warning residual
remains observable. Goal034 does not provide or launch that runner.
