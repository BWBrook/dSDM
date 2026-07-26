# Runbook

Run from the repository root with the project interpreter:

```sh
PYTHONPATH=src .venv/bin/python -m dsdm_phase1.spatial_partition
PYTHONPATH=src .venv/bin/python -m dsdm_phase1.spatial_partition \
  --validate --mode final
PYTHONPATH=src .venv/bin/python -m dsdm_phase1.spatial_partition \
  --validate --full --mode final
```

Production refuses either existing destination:

- `data/processed/partitions/goal025-spatial-partition/2026-07-26/`
- `evidence/spatial_partition/2026-07-26/`

The private destination is ignored. It contains only the ten contracted
assignment, audit, candidate, support, and SVG products. The tracked
destination contains aggregate JSON evidence and its byte manifest.

The dSDM orchestrator reviewed the exact private `spatial_partition.svg` and
the machine-recomputed aggregate topology/class/support audit. Criteria
`goal025-v2` passed on 2026-07-26. The audit-driven language and evidence
correction changed only code, tests, documents, receipt criteria, aggregate
`summary.json`, `review.json`, and the tracked manifest. It did not regenerate
or change any private assignment, diagnostic, candidate, or SVG byte.

The canonical acceptance check is:

```sh
PYTHONPATH=src .venv/bin/python -m dsdm_phase1.spatial_partition \
  --validate --full --mode final
```

Do not edit or regenerate either frozen output tree after review. A changed
input, implementation, plan, SVG, or manifest requires a new dated package and
a new review receipt. Pending-mode validation is retained only for rebuilding
an as-yet-unreviewed package and must fail against this passed receipt.
