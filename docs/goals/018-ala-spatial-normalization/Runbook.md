# Runbook

From the repository root, run:

```sh
uv run --locked python -m dsdm_phase1.ala_spatial_normalization run \
  --plan config/ala_spatial_normalization_plan.json
```

The command performs no network access. It requires the Goal017 raw snapshot,
its evidence manifest, the canonical grid, and the coast shapefile. Existing
output/evidence directories are never resumed or overwritten. Validate tracked
evidence with `validate_evidence`; a full readiness claim requires raw replay.

Tracked-only validation (which explicitly reports replay required):

```sh
uv run --locked python -m dsdm_phase1.ala_spatial_normalization validate \
  --plan config/ala_spatial_normalization_plan.json \
  --evidence-dir evidence/ala_spatial_normalization/2026-07-24
```

Full raw/output validation used for acceptance:

```sh
uv run --locked python -m dsdm_phase1.ala_spatial_normalization validate \
  --plan config/ala_spatial_normalization_plan.json \
  --evidence-dir evidence/ala_spatial_normalization/2026-07-24 \
  --raw-dir data/raw/ala/goal017-nine-species/2026-07-24 \
  --output-dir data/processed/ala/goal018-spatial-normalization/2026-07-24
```
