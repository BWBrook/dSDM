# Runbook

Use the exact Goal034 runtime (Darwin arm64; Python 3.12.13, NumPy 2.2.6,
SciPy 1.16.3, scikit-learn 1.9.0, threadpoolctl 3.6.0, Torch 2.7.1; CPU,
mac_cpu, one Torch and BLAS thread):
`data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python`.
Keep all private bundles/leaves under the configured Goal035 namespace.

```bash
RUNTIME=data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python
PYTHONPATH=src "$RUNTIME" -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json plan
PYTHONPATH=src "$RUNTIME" -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json export
PYTHONPATH=src "$RUNTIME" -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json validate-bundles
PYTHONPATH=src "$RUNTIME" -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json canary
tmux new-session -d -s dsdm035-final-inner 'PYTHONPATH=src data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json run'
PYTHONPATH=src "$RUNTIME" -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json status
PYTHONPATH=src "$RUNTIME" -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json finalize
PYTHONPATH=src "$RUNTIME" -m dsdm.final_inner_runner --config config/dsdm_final_inner_lifecycle.json validate
```

The order is categorical repair -> corrected selection -> corrected Mac
canary -> full launch.  `run` rejects missing or failed canary evidence and
recomputes only incomplete case leaves; corrupt existing leaves fail closed
before any fit is scheduled.  Finalize/validate are read-only over private
leaves except for the single tracked aggregate receipt.  Outer access, labels
in tracked evidence, and model weights are forbidden.
