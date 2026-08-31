# Runbook

From the dSDM repository root, the prospective sequence was:

```sh
uv run --locked pytest -q tests/test_goal047_tasmania_transfer.py
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer validate-inputs --root .
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer freeze --root .
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer validate-freeze --root .
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer canary --root . --device cpu
git add config/goal047_tasmania_transfer.json src/dsdm_phase1/goal047_tasmania_transfer.py tests/test_goal047_tasmania_transfer.py docs/goals/047-tasmania-transfer-assessment evidence/tasmania_transfer/goal047/freeze.json
git commit
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer run-full-refits --root . --device cpu --workers 3
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer validate-full-refits --root .
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer build-opening-receipt --root .
git add metadata/goal047_opening_receipt.json
git commit
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer validate-opening-gate --root .
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer evaluate --root .
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer validate-result --root .
uv run --locked python -m dsdm_phase1.goal047_tasmania_transfer status --root .
```

The first refit attempt failed safely before any fitting or Tasmania access
because replay validation expected a different summary-key shape. After the
repair, all 20 canonical Goal 042 mainland summaries reproduced exactly.
Production then exited `0` with five q fits, 25 pretraining fits, and 142
models. The implementation/fix history is `f46659d` followed by `37a5ec3`;
the committed opening receipt is `20897ec`.

The opening gate and independent final audit passed. The exclusive opening
marker was written before the single response and predictor reads. The
production result is aggregate-only: do not recover, publish, or add cell-level
payloads to Git. Continuous extrapolation and categorical unseen diagnostics
are descriptive and must not trigger post hoc model changes.
