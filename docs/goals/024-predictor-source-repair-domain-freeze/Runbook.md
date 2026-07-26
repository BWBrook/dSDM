# Runbook

From the repository root:

```sh
PYTHONPATH=src .venv/bin/python -m dsdm_phase1.predictor_source_repair_domain_freeze
PYTHONPATH=src .venv/bin/python -m dsdm_phase1.predictor_source_repair_domain_freeze --validate
```

The production command refuses existing destinations, byte-validates all five
private CSVs in staging, validates the tracked evidence footprint/manifest, and
writes the private CSV directory and tracked evidence directory together. Full
validation invokes Goal023 replay (which chains Goal021 and Goal022), then
recomputes and byte-compares every Goal024 private file and its tracked
metadata. The HFP candidate oracle checks CRS, dimensions, transform alignment,
dtype/nodata, and exact shared raw array/mask; shared-raster nodata pixels are
reported separately from canonical missing cells. Do not read `tas_cam/` or raw
ALA occurrence files for this goal.
