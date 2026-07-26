# Goal 020 runbook

Run commands from the repository root with the locked environment.

## Focused tests

```sh
PYTHONPATH=src uv run --locked python tests/test_ala_camera_combination.py
```

## Production publication

The publication command fails if either destination already exists.

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_camera_combination run \
  --plan config/ala_camera_combination_plan.json
```

## Tracked-only validation

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_camera_combination validate \
  --plan config/ala_camera_combination_plan.json \
  --evidence-dir evidence/ala_camera_combination/2026-07-26
```

Success explicitly reports that private replay is still required.

## Full replay

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.ala_camera_combination validate \
  --plan config/ala_camera_combination_plan.json \
  --evidence-dir evidence/ala_camera_combination/2026-07-26 \
  --full
```

The full gate independently recomputes from the two hash-bound accepted
private roles and byte-compares the ignored output. Goal 018 and Goal 019
full acceptance replays remain separate required gates; use their existing
runbooks without recording private operator paths in tracked material.

## Stop conditions

Stop on binding drift, source schema or footprint drift, duplicate keys,
centroid mismatch, oracle mismatch, any excluded island presence, privacy
failure, or a need to change upstream policy. Do not repair upstream goals
inside Goal 020.
