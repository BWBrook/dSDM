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

The canary is the bounded pre-production gate. Once the focused tests, input validation, and canary pass, production may be launched under explicit orchestration, preferably detached in a named tmux session. Never open the Tasmania response or predictor tables.
