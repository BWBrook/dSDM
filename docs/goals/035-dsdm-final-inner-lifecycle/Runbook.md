# Runbook

All commands use the isolated Goal033 runtime.  The corrected architecture
revalidation is the next authorised execution gate; the later full
inner-lifecycle workload remains downstream of its result and the corrected
two-repeat Mac canary.

```bash
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_mask_revalidation --config config/dsdm_categorical_revalidation.json plan
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_mask_revalidation --config config/dsdm_categorical_revalidation.json audit-categories
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_mask_revalidation --config config/dsdm_categorical_revalidation.json status
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_mask_revalidation --config config/dsdm_categorical_revalidation.json run
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_mask_revalidation --config config/dsdm_categorical_revalidation.json finalize
PYTHONPATH=src data/processed/dsdm/goal033-architecture-selection/runtime/.venv/bin/python -m dsdm.architecture_mask_revalidation --config config/dsdm_categorical_revalidation.json validate
```

The default bundle root is the immutable Goal033 private bundle directory.
The default leaf root is the fresh Goal035 namespace.  `run` rejects a
Goal033 leaf root, runs screen first, derives a fresh top four, then runs the
shortlist and enforces 160 seed-31031 replay pairs.  It is resumable through
strict leaf validation.  `finalize` and `validate` perform no fitting and
write/compare aggregate evidence only after the complete private workload
exists.
