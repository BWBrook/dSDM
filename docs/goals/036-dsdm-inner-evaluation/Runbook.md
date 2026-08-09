# Goal 036 runbook

## Prespecification gate

```sh
uv run --locked pytest -q tests/test_dsdm_inner_evaluation.py
uv run --locked python -m dsdm.inner_evaluation \
  --config config/dsdm_inner_evaluation.json plan
python -m py_compile \
  src/dsdm/conventional_oof_export.py \
  src/dsdm/inner_evaluation.py
```

Commit this contract before exporting or inspecting comparative metrics.

## Private conventional export

Stage `src/dsdm/conventional_oof_export.py` unchanged beside the immutable
Goal029 producer checkout at commit
`f85e45922e182858fd351fdaf4f1b36b33fb4f2f`, then run its locked producer
environment:

```sh
python conventional_oof_export.py \
  --repo-root /path/to/immutable/goal029-producer \
  --output-dir /private/goal036-export \
  --private-manifest-sha256 \
  836384b71fa03797e3fe92052aed2255b737d59a347aaa8614830a28d0851ab6
```

Transfer only `conventional_selected_oof.parquet` and `manifest.json` over the
private Tailscale route.  Rename the latter `conventional_manifest.json` in the
configured ignored Goal036 private directory.  Do not copy the 1.3 GB producer
tree or any selected outer-refit product.

## Evaluation

```sh
uv run --locked python -m dsdm.inner_evaluation \
  --config config/dsdm_inner_evaluation.json run
uv run --locked python -m dsdm.inner_evaluation \
  --config config/dsdm_inner_evaluation.json validate
```

Both commands must report zero fits and outer attempted/opened `0/0`.  Tracked
evidence must contain exactly six aggregate CSV tables and `summary.json`.
