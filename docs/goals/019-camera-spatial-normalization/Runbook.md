# Runbook

Run from the repository root. Supply the ignored private directory only as a
runtime environment value; do not write its value to tracked files or logs.

```sh
PYTHONPATH=src uv run --locked python \
  -m dsdm_phase1.camera_spatial_normalization run \
  --plan config/camera_spatial_normalization_plan.json \
  --private-dir "$CAMERA_PRIVATE_DIR"
```

Tracked-only evidence validation must report that private replay is required:

```sh
PYTHONPATH=src uv run --locked python \
  -m dsdm_phase1.camera_spatial_normalization validate \
  --plan config/camera_spatial_normalization_plan.json \
  --evidence-dir evidence/camera_spatial_normalization/2026-07-24
```

Full acceptance requires independent private source and output replay:

```sh
PYTHONPATH=src uv run --locked python \
  -m dsdm_phase1.camera_spatial_normalization validate \
  --plan config/camera_spatial_normalization_plan.json \
  --evidence-dir evidence/camera_spatial_normalization/2026-07-24 \
  --private-dir "$CAMERA_PRIVATE_DIR" \
  --output-dir \
  data/processed/camera/goal019-spatial-normalization/2026-07-24
```

Validation ladder:

```sh
PYTHONPATH=src uv run --locked python tests/test_camera_spatial_normalization.py
PYTHONPATH=src uv run --locked python tests/test_ala_spatial_normalization.py
PYTHONPATH=src uv run --locked python -m unittest discover -s tests -p 'test_*.py'
uv run --locked python -m json.tool \
  config/camera_spatial_normalization_plan.json >/dev/null
PYTHONPATH=src uv run --locked python -m py_compile \
  src/dsdm_phase1/camera_spatial_normalization.py \
  tests/test_camera_spatial_normalization.py
uv lock --check
git diff --check
git status --short --branch
git ls-files -- tas_cam
```

Existing output or evidence directories are never resumed or overwritten.
Resolve an incomplete publication explicitly before rerunning.
