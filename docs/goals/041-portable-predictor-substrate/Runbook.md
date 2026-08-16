# Runbook

## Execution boundary

Implementation should expose the following resumable stages through
`dsdm_phase1.goal041_predictor_substrate`. Raw assets, pilot replays, chunks,
and the final table live under ignored `data/raw/goal041/`; tracked evidence
lives under `metadata/` and contains no cell identity, coordinate, or value.

Before execution:

```sh
git status --short --branch
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate validate-contract --root .
```

Stop if the worktree is unexpectedly dirty or if the Goal 040 domain, source
matrix, pilot manifest, or ignored ordered cell ledger fails its bound digest.

## Bulk acquisition and equivalence

Acquire and validate the official bulk products once:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate acquire --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate validate-sources --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate prepare-pilot-baselines --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate pilot-equivalence --root .
```

The acquisition stage must be checkpointed and idempotent. It must never make
one request per eligible cell. A complete asset/receipt pair may be reused only
after size and SHA-256 validation; an orphaned, partial, or changed pair fails
closed.

Before reading pilot comparison results, write the source-native continuous
quantisation and corresponding absolute tolerance into the ignored comparison
contract and bind its digest in tracked evidence. The equivalence rules are:

- WorldClim BIO1-BIO19: bulk raster value at the pilot centroid;
- DEM mean/SD: the same exact-bbox valid-pixel summaries as the pilot;
- NVIS and Soil Order: exact replay against independently frozen centroids from
  the official local raster, not their legacy renderer values or production
  modal values;
- ALUM: the same deterministic exact-cell modal source code as production;
- missingness and all categorical codes: exact agreement; and
- continuous values: all comparable values within the predeclared tolerance,
  with no post hoc tolerance widening.

Any unresolved mismatch stops before the full extraction.

## Local vertical slice and compute checkpoint

Run a deterministic benchmark containing at least 500 mainland and 500
Tasmania cells and exercising every source path:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate benchmark --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate validate-benchmark --root .
```

Record the selected target, live CPU/RAM/free-disk facts, benchmark throughput,
peak RAM, temporary disk, projected full-run wall time, source/code digests,
and decision timestamp. Dispatch only when the same algorithm and chunk shape
project below 12 hours and the target has clear RAM and disk headroom for the
projected working footprint. Prefer the always-available `deep-server` CPU/I/O
route; use another host only with an explicit recorded reason. Do not route
this extraction to a GPU merely because one is available.

## Detached full extraction

Use Git or checksum-preserving `rsync` for source and ignored assets. On the
chosen host, place the working copy and scratch space under its approved
project-compute root, verify the stable run identity, and launch:

```sh
tmux new-session -d -s dsdm-goal041 'PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate extract --root . && PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate validate-table --root .'
tmux capture-pane -pt dsdm-goal041:0 -S -80
```

The extractor must use deterministic spatial chunks, atomic completion
receipts, and bounded memory. On restart it may skip only chunks whose input,
schema, row count, identity range, and content digest all validate. It must not
silently repair or overwrite a conflicting completed chunk.

After extraction, validate the complete elevation service cache and publish
its aggregate digest:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate elevation-tile-manifest --root .
```

After completion, transfer the ignored table/chunk receipts back with checksum
verification and run locally:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate diagnose --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate worldclim-missingness --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal041_predictor_substrate validate --root .
PYTHONPATH=src uv run --locked pytest -q tests/test_goal041_predictor_substrate.py
git diff --check
```

## Decision and failure rules

`validate-table` must prove exactly 1,125,325 unique ordered cell rows and
exactly the 24 frozen predictor columns, plus region and cell identity. The
tracked diagnostics must reconcile to the regional denominators and report:

- missing and valid counts/fractions for every predictor and region;
- finite continuous range and fixed quantiles by region;
- Tasmania counts/fractions below and above the valid mainland range;
- categorical code/label support and cell counts by region; and
- valid Tasmania-only levels, which are future `__UNSEEN__` cases rather than
  missing values.

Stop as `repair` or `blocked` on persistent bulk/pilot drift, invalid source
codes, unresolved ontology differences, output identity/digest failure, or
unexplained missingness affecting at least 5% of either region or forming a
spatially coherent gap capable of biasing the comparison. Known and documented
authoritative nodata is reported rather than silently filled. Tasmania lying
outside mainland climate ranges is diagnostic evidence and never a failure by
itself.

After one focused repair, do not repeat unchanged failing attempts. Publish the
residual limitation and request a changed source, method, or scientific
decision. Stop before transformation, response construction, predictor
selection, or model fitting.

## Soil source correction

The Soil Order source is the CSIRO DAP COG and companion legend recorded in the
Goal 041 configuration. `acquire` streams each file atomically when absent and
`validate-sources` checks file identity, dimensions, CRS, nodata, and checksums.
Pilot Soil values are explicit native-centre COG lookups; production Soil values
are exact half-open native-pixel modal summaries. The retired WCS endpoint is not
a fallback. The pilot correction receipt records aggregate legacy WMS
discrepancies without retaining cell identities or values.

## NVIS ontology

The official NVIS 7 File Geodatabase raster attribute table defines 32 Major
Vegetation Group codes. Its derived GeoTIFF retains the numeric cells but not
that table, and older Linux GDAL builds cannot reliably expose the table
through `/vsizip/`. The small official ontology is therefore frozen in the
checksum-bound production code. Valid output is `code:MVG_NAME`; official code
99 (`Unknown/no data`) is missing rather than a vegetation class. A fresh run
applies this rule during extraction. The 2026-08-16 repair receipt separately
binds the one label-only correction applied to the already completed chunks.
