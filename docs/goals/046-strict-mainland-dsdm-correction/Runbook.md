# Runbook

From the repository root:

```sh
uv run --locked pytest -q tests/test_goal046_mainland_dsdm.py
uv run --locked python -m dsdm_phase1.goal046_mainland_dsdm validate-inputs --root .
uv run --locked python -m dsdm_phase1.goal046_mainland_dsdm canary --root . --device cpu
uv run --locked python -m dsdm_phase1.goal046_mainland_dsdm status --root .
uv run --locked python -m dsdm_phase1.goal046_mainland_dsdm run --root . --device cpu --workers 3
uv run --locked python -m dsdm_phase1.goal046_mainland_dsdm validate --root .
```

The bounded canary preceded the authorised production run, which has now
completed and passed independent aggregate replay. The detached wrapper did
not leave a `run.exit` marker; the completion log and validator are
authoritative. Any rerun requires explicit orchestration, preferably detached
in a named tmux session. Never open the Tasmania response or predictor tables.
