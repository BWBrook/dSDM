# Runbook

Use the frozen Goal034/035 Mac CPU runtime with one Torch and BLAS thread:

```sh
RUNTIME=data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic plan --config config/dsdm_capacity_diagnostic.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic canary --config config/dsdm_capacity_diagnostic.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic run-stage1 --config config/dsdm_capacity_diagnostic.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic status-stage1 --config config/dsdm_capacity_diagnostic.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic finalize-stage1 --config config/dsdm_capacity_diagnostic.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic validate-stage1 --config config/dsdm_capacity_diagnostic.json
```

`run-stage1` is private and resumable: a complete identity-addressed leaf is
reused, a missing leaf is scheduled, and a corrupt leaf fails closed. No
tracked receipt is written until read-only finalization. Outer attempted/opened
must remain `0/0`. Stage 2 is conditional within this approved Goal038
contract and is added/executed only after a Stage 1 advance.

After the Stage 1 advance, use the isolated Stage 2 runner:

```sh
RUNTIME=data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic_stage2 plan --config config/dsdm_capacity_diagnostic_stage2.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic_stage2 canary --config config/dsdm_capacity_diagnostic_stage2.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic_stage2 run --config config/dsdm_capacity_diagnostic_stage2.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic_stage2 status --config config/dsdm_capacity_diagnostic_stage2.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic_stage2 finalize --config config/dsdm_capacity_diagnostic_stage2.json
PYTHONPATH=src "$RUNTIME" -m dsdm.capacity_diagnostic_stage2 validate --config config/dsdm_capacity_diagnostic_stage2.json
```

The full workload is 40 atomic cases, 8,840 logical artifacts, and
17,640--17,680 physical fits. Only `wide512` is permitted; no alternate rescue
is available. Confirmation uses the two fresh seeds and five declared reduced
endpoints from `Decision.md`.
