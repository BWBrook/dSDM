# Decision

## Status

Approved for execution on 2026-08-14. Accepted as `ready` on 2026-08-16.

## Frozen scientific contract

Goal 041 binds the 24-predictor panel accepted by Goal 040 to every one of the
1,125,325 frozen eligible cells. One common product, version, definition,
units, nodata convention, and categorical ontology must serve southeast
mainland Australia and Tasmania. Region-specific substitutions are forbidden.

Production extraction is fixed as WorldClim centroid values; exact-cell valid
native-pixel mean and sample SD for elevation; and deterministic exact-cell
modal native source codes for NVIS, Soil Order, and ALUM, with lowest canonical
source code breaking a tie. Missing source values remain missing.

The accepted 128-cell pilot is a source-identity gate. It will be replayed from
the bulk assets with its original semantics, including centroid NVIS and Soil
Order. Production modal values for those two layers answer a different spatial
aggregation question and will not be incorrectly compared with the centroid
pilot values.

## Interpretation

The mainland predictor distribution is the reference for the later
mainland-to-Tasmania transfer experiment. Tasmania is geographically isolated,
more southerly, and expected to be near or outside the mainland range for some
climate variables. Such extrapolation is a property to measure and later
interpret, not a reason to reject an otherwise valid common-source predictor.

Source drift, a failed bulk/pilot identity replay, unexplained major coverage
gaps, invalid codes, or incompatible regional ontologies are failures. A valid
Tasmania-only categorical level is not a source failure: later mainland-fitted
transforms will map it to `__UNSEEN__`. Nodata remains separately
`__MISSING__`. Goal 041 records these cases but performs no encoding.

## Compute and evidence boundary

The full extraction will be dispatched only after a local two-region benchmark
and a live resource checkpoint. `deep-server` is the expected target because
the workload is CPU/I/O-bound raster aggregation; no GPU route is required.
The production job must run resumably under `tmux` with source, code, chunk,
and final digests.

Source rasters, service payloads, cell identities, coordinates, and predictor
values remain ignored. Tracked evidence is limited to source provenance,
digests, execution facts, aggregate missingness/extrapolation/category
diagnostics, and the eventual decision receipt.

No response construction, predictor transformation or selection, modelling,
map, outer evaluation, or manuscript work is authorised by this decision.

## Categorical pilot correction (2026-08-14)

The authoritative production and pilot sources are the CSIRO Soil COG and the
official NVIS 7 raster, checksum-bound in configuration and provenance. Legacy
renderer values remain historical audit evidence only. Goal 041 freezes private
source-native centroid baselines before replay; tracked receipts retain only
aggregate legacy exact/discrepant counts. Fresh replay must match all corrected
categorical centroids exactly. Production still uses exact-cell modal values.

## Final outcome (2026-08-16)

The detached `deep-server` extraction completed all 40 chunks in 71 minutes
26 seconds. The final ignored table contains exactly 1,125,325 ordered rows and
24 predictors and is bound by SHA-256
`3a271c63a5b706c97330aaf8656528f17f62aa3a896d9035ab6a264f1ab86e3e`.
All source, pilot, benchmark, table, diagnostic, and provenance gates pass
under run identity
`86d6617d5d20f858847484a8aa8cef9cf8755430d539f71f264d3ef1c64dc07a`.

The review found one bounded categorical defect: the derived NVIS GeoTIFF
retained numeric MVG codes but not the official File Geodatabase attribute
table. The 40 completed chunks were relabelled against the checksum-bound NVIS
7 ontology. Official code 99 (`Unknown/no data`) became missing: 1,811 mainland
cells were affected, leaving NVIS missingness at 0.1723% on the mainland and
0% in Tasmania. The repair receipt binds both artefact chains and confirms the
other 23 predictor columns and ordered rows were preserved.

All BIO layers share a small nodata footprint: 1,128 mainland cells (0.1071%)
and 395 Tasmania cells (0.5464%). Four-neighbour analysis classifies it as
dispersed coastal centroid/source-mask nodata rather than a coherent gap. Soil
Order is missing in 41 mainland cells; elevation and ALUM are complete.

Tasmania has no valid categorical level absent from the mainland. Its climate
distribution is nevertheless a strong transfer test: 15.66% of valid cells
exceed the mainland BIO17 range, 12.43% exceed BIO19, 11.24% exceed BIO14, and
10.16% exceed BIO12. These are retained as descriptive extrapolation, not
failure. The source-native ALUM code 62 maps to both `6.0 Water` and
`6.2 Reservoir/dam`; their full code-label strings remain distinct rather than
being silently collapsed.
