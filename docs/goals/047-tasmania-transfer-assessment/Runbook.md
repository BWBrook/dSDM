# Runbook

From the dSDM repository root:

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

The `canary`, `run-full-refits`, and `validate-full-refits` commands read
mainland sources only. The full stage requires the committed freeze and a
clean worktree, and writes only ignored private response/model/receipt files.
Workers operate by target and are useful when memory permits; `--workers 1`
is the bounded sequential fallback.

The opening receipt is created only after every exact private artifact key and
digest validates. It must be committed before the gate is checked. The
one-shot opening writes and fsyncs an exclusive private start marker before
its first Tasmania read and refuses every retry, including after a crash.

Only the final `evaluate` command opens the two bound Tasmania inputs. Do not
run it during pre-opening implementation or validation. No command directly
opens camera source data.
