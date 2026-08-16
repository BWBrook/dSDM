# Log

## 2026-08-14 - prespecification and approval

- Approved a full-domain portable-predictor substrate over the exact Goal 040
  eligible-cell authority: 1,125,325 cells, comprising 1,053,032 southeast
  mainland and 72,293 Tasmania cells.
- Frozen the 24-layer panel and production semantics: WorldClim centroid,
  exact-cell DEM mean/sample SD, and deterministic modal NVIS, Soil Order, and
  ALUM source codes.
- Separated production aggregation from the accepted pilot replay. NVIS uses
  its accepted centroid semantics; Soil Order uses explicit native-centre COG
  lookup for pilot equivalence, avoiding an invalid modal-versus-centroid
  comparison.
- Frozen the categorical transfer interpretation: a valid Tasmania-only level
  is a later `__UNSEEN__` case; source nodata is distinct `__MISSING__`; no
  encoding occurs in this goal.
- Frozen a local benchmark and live compute checkpoint before detached full
  extraction, with `deep-server` expected for this CPU/I/O workload.
- Confirmed that Tasmania outside the mainland climate range is a measured
  experimental condition rather than an automatic failure.
- No source acquisition, extraction, benchmark, remote dispatch, diagnostic,
  code change, model, map, commit, or push is claimed by this entry.

## 2026-08-14 - Soil source correction

- Replaced Soil WCS transport with the checksum-bound CSIRO DAP COG and official
  legend; production uses native-pixel modal aggregation and pilot uses explicit
  native-centre lookup.
- Preserved Goal 040 WMS output unchanged as historical audit evidence. The
  corrected private baseline records 97 legacy exact rows and 31 renderer
  discrepancies (12 mainland, 19 Tasmania) in aggregate only.
- No pilot, benchmark, or full extraction is claimed by this entry.

## 2026-08-14 - pre-dispatch audit repair

- Separated correction from equivalence: private Soil and NVIS source-native
  centroid baselines are frozen and checksum-bound before a fresh 128-cell
  replay. Legacy renderer differences can no longer self-authorise a pass.
- Bound benchmark, cache, chunk, and final-table evidence to one stable run
  identity; completed chunks now fail closed on receipt, schema, identity, or
  digest drift.
- Defined truthful per-predictor `ready`, `repair`, or `blocked` decisions for
  absolute and regional missingness while retaining climate extrapolation as
  descriptive evidence.
- No full extraction, diagnostic conclusion, commit, or push is claimed by
  this entry.

## 2026-08-16 - full extraction, focused repair, and acceptance

- Completed the detached `deep-server` run in 40 resumable chunks: 1,125,325
  ordered rows in 71 minutes 26 seconds. Local and remote table checksums
  matched exactly.
- Revalidated all 592 cached elevation request/payload pairs and published one
  aggregate provenance digest without exposing cell identities or values.
- Found that the derived NVIS GeoTIFF had lost its raster attribute table.
  Relabelled the completed chunks from the official checksum-bound 32-code MVG
  ontology; recoded 1,811 mainland code-99 `Unknown/no data` cells as missing;
  and bound the upstream and repaired artefact chains in a tracked receipt.
- Confirmed the corrected 128-cell pilot replay at 128/128 exact agreement and
  reran the cold two-region benchmark under the final code identity.
- Diagnosed joint BIO1-BIO19 nodata in 1,128 mainland and 395 Tasmania cells.
  The footprint is dispersed (largest four-neighbour components 22 and 16
  cells respectively), not a coherent unexplained coverage gap.
- Recorded the expected Tasmania climate extrapolation, no Tasmania-only
  categorical levels, and the source-native ALUM code-62 label ambiguity.
- Accepted Goal 041 as `ready`: sources, pilot, benchmark, table, diagnostics,
  and provenance all validate under run identity `86d6617d5d20f858...` and
  final table SHA `3a271c63a5b706c...`.
- Stopped at the raw substrate boundary. No response construction,
  pseudoabsence inference, transformation, model fitting, map, or manuscript
  work was performed.
