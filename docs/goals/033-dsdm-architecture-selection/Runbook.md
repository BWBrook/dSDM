# Runbook

Use the repository's locked environment only for the local Phase 1 export.
Use the selected Goal033 runtime (Python 3.12, NumPy 2.2.6, PyTorch 2.7.1,
one numerical thread) for validation and every fit. Do not alter
`pyproject.toml` or `uv.lock`.

```bash
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_runner plan
uv run --locked python -m dsdm.architecture_runner export --foundation-root /path/to/dSDM
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_runner validate-bundles
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_runner run
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_runner status
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_runner validate
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_runner finalize
```

`run` is private and never writes tracked evidence. It validates the complete
40-bundle cross-product, runs the screen, derives exactly four shortlist
architectures, performs the mandatory 160 seed-31031 replay comparisons, and
leaves all labels, scores, and receipts under the private root. Resume skips
only a fully revalidated identity-addressed leaf; partial or tampered leaves
fail closed. After orchestrator review and wake-up, `finalize` recomputes all
gates and atomically writes the single aggregate receipt; `validate` is
read-only and exact-compares that receipt.
