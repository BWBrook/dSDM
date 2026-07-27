# Runbook

From the repository root:

```sh
uv run python -m dsdm_phase1.model_ready_features --root . 
uv run python -m dsdm_phase1.model_ready_features --root . --validate --full
uv run pytest -q tests/test_model_ready_features.py
uv run pytest -q
python3 -m py_compile src/dsdm_phase1/model_ready_features.py
uv lock --check
git diff --check
```

The generation command refuses existing evidence/private destinations and
publishes complete staged directories with rollback on a second-rename
failure. `--full` performs one bound upstream replay and recomputes Goal026;
`--validate` checks the existing closed evidence/private footprint. Private
outputs are ignored by the repository; tracked evidence contains aggregate
values only.
