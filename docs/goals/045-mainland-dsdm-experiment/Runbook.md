# Runbook

From the repository root:

```sh
uv run --locked pytest -q tests/test_goal045_mainland_dsdm.py
uv run --locked python -m dsdm_phase1.goal045_mainland_dsdm validate-inputs --root .
uv run --locked python -m dsdm_phase1.goal045_mainland_dsdm canary --root . --device cpu
uv run --locked python -m dsdm_phase1.goal045_mainland_dsdm status --root .
uv run --locked python -m dsdm_phase1.goal045_mainland_dsdm run --root . --device cpu --workers 3
uv run --locked python -m dsdm_phase1.goal045_mainland_dsdm validate --root .
```

The production run belongs in `tmux` session `dsdm-goal045`. Its log and exit
marker are written below the ignored private Goal 045 root. To inspect it:

```sh
tmux capture-pane -pt dsdm-goal045 -S -40
uv run --locked python -m dsdm_phase1.goal045_mainland_dsdm status --root .
cat data/processed/dsdm/goal045-mainland-dsdm/run.exit
```

An exit marker of `0` is necessary but not sufficient: run the final validator
before accepting results. Never open the Tasmania evaluation table in this
goal.
