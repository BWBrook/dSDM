# Plan

1. Validate all frozen source hashes and the 32-band positional contract.
2. Index canonical centres exactly on the raster lattice and extract active
   bands as Float32 values, retaining missingness explicitly.
3. Derive categorical levels from all canonical cells, audit Goal021 key joins,
   and write the two private CSVs atomically.
4. Publish aggregate, privacy-safe evidence and validate tracked and full
   replay paths.

Expected oracle: 74,073 canonical rows (71,023 complete), 5,407 response
cells (5,087 complete), 28 active predictors, 34 excluded complete raster
cells outside the canonical grid.
