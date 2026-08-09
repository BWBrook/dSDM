# Runbook

Run from the repository root. The neural lane uses the calibrated Goal 034
runtime; the conventional lane uses the project lock.

```sh
NEURAL=data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json plan
uv run --locked pytest -q tests/test_dsdm_outer_ready.py
python3 -m py_compile src/dsdm/outer_ready.py src/dsdm/conventional_refit_import.py
```

Commit the prespecified contract before materialising or fitting real Goal 037
artifacts.

```sh
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json epochs
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json export
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json validate-bundles
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json canary
```

Rerun the immutable Goal 029 validator at producer commit `f85e459` with the
repaired validator at `e6f07ae`, recording its JSON result privately. Copy only
`selection.json`, `selections/`, and `selected/` from the producer into
`data/processed/dsdm/goal037-outer-ready/private/conventional/copy/` using
Tailscale-backed `rsync`. Then run:

```sh
uv run --locked python -m dsdm.conventional_refit_import \
  --config config/dsdm_outer_ready.json \
  --result data/processed/dsdm/goal037-outer-ready/private/conventional/producer-result.json \
  --output data/processed/dsdm/goal037-outer-ready/private/conventional/producer-validation.json \
  record-producer-validation
uv run --locked python -m dsdm.conventional_refit_import \
  --config config/dsdm_outer_ready.json \
  --copied-root data/processed/dsdm/goal037-outer-ready/private/conventional/copy \
  --producer-validation data/processed/dsdm/goal037-outer-ready/private/conventional/producer-validation.json \
  --output data/processed/dsdm/goal037-outer-ready/private/conventional/import_receipt.json \
  finalize
```

Launch the neural production run detached:

```sh
tmux new-session -d -s dsdm037-outer-ready \
  'cd /Users/bwbrook/papers/dSDM && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python -m dsdm.outer_ready --config config/dsdm_outer_ready.json run > data/processed/dsdm/goal037-outer-ready/private/neural-run.log 2>&1'
```

After completion:

```sh
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json status
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json finalize
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json validate
```

Never open the outer vault in this goal. Tracked evidence contains aggregate
provenance and counts only, never labels, predictions, coordinates, row IDs,
private paths, or model weights.
