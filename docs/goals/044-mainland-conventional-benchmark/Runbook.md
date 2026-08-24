# Runbook

From the repository root:

```sh
uv run --locked pytest -q tests/test_goal044_mainland_conventional.py
uv run --locked python -m dsdm_phase1.goal044_mainland_conventional validate-inputs --root .
uv run --locked python -m dsdm_phase1.goal044_mainland_conventional canary --root .
uv run --locked python -m dsdm_phase1.goal044_mainland_conventional run --root . --workers 3
uv run --locked python -m dsdm_phase1.goal044_mainland_conventional validate --root .
```

The canary determines whether the full conventional run remains suitable for
the Mac CPU. Long execution should run detached in `tmux`; it is resumable at
the target-endpoint checkpoint. Never open the Tasmania evaluation table.
