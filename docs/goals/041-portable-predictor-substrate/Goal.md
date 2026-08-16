# Goal 041 - portable predictor substrate

## Scientific objective

Build one deterministic, provenance-bound raw predictor table for all
1,125,325 Goal 040 eligible 0.01-degree cells across southeast mainland
Australia and Tasmania. The table must contain the 24 common predictors
accepted by the Goal 040 pilot and must use the same product, version, units,
and ontology in both regions.

This goal tests whether the accepted predictor panel is operationally portable
at full extent. Tasmania is expected to occupy an environmentally extreme part
of the mainland reference distribution for some variables. That extrapolation
is a feature of the mainland-to-island experiment, not by itself a source or
predictor failure.

## Frozen predictor and extraction contract

The 24 raw predictors are WorldClim 2.1 BIO1-BIO19, GA SRTM-derived elevation
mean and within-cell sample SD, NVIS 7.0 extant Major Vegetation Group, SLGA
Release 1 Soil Order, and ABARES NLUM v7/ALUM v8 secondary land-use class.
The Goal 040 source matrix remains the identity and units authority.

Production extraction uses:

- WorldClim: the value at the Goal 040 cell centroid;
- elevation: valid native pixels in the exact half-open 0.01-degree cell bbox,
  reported as mean and sample SD;
- NVIS, Soil Order, and ALUM: the modal valid native-pixel source code in the
  exact cell, with ties resolved to the lowest canonical source code; and
- source nodata retained as missing, never zero-filled, imputed, or rescued
  from another product.

The accepted 128-cell pilot must also be replayed from the bulk assets. NVIS
and Soil Order use independently frozen, source-native centroids from the
official local rasters. Their legacy renderer values remain audit evidence.
Production modal values remain a separate exact-cell aggregation.

## Acceptance criteria

1. Bind the ordered output exactly to the Goal 040 eligible-cell authority:
   1,125,325 unique cell rows, including 1,053,032 mainland and 72,293
   Tasmania rows, with no extra, missing, reordered, or duplicated identity.
2. Acquire each frozen bulk source once through an authoritative route. Record
   product/version, layer identity, URL, retrieval time, licence, CRS,
   resolution, nodata, byte size, SHA-256, and extraction semantics in tracked
   provenance; keep rasters and service payloads ignored.
3. Prove bulk-source equivalence on all comparable nonmissing values in the
   accepted 128-cell pilot. Missingness and categorical codes must agree
   exactly. Continuous tolerances must be frozen from source-native
   quantisation before comparison and may not be relaxed after seeing results.
4. Run a deterministic local benchmark across both regions and all five source
   paths. Record observed rate, peak RAM, temporary disk, projected full-run
   wall time, and the selected compute route before dispatch.
5. Dispatch the full extraction only to a live target with adequate RAM and
   disk headroom and a projected wall time below 12 hours. `deep-server` is the
   expected CPU/I/O target; a GPU is neither required nor advantageous for this
   raster workload. Run detached under `tmux` with resumable, deterministic
   chunks.
6. Produce an ignored cell-by-predictor table containing the cell identity,
   region, and exactly 24 raw predictor columns. Publish a tracked manifest
   binding its schema, row counts, regional counts, source digests, chunk
   digests, final digest, and execution environment without publishing cell
   identities, coordinates, or values.
7. Publish privacy-safe full-domain diagnostics by predictor and region:
   missingness; finite continuous summaries; the fraction of Tasmania below
   and above the mainland valid range; categorical cell counts and levels; and
   valid Tasmania levels absent from mainland. Do not convert edge-of-range
   climate values into a failure criterion.
8. Record a final `ready`, `repair`, or `blocked` decision for the raw
   substrate and each predictor. Persistent source drift, pilot mismatch,
   major unexplained missingness, invalid categorical codes, or an ontology
   that cannot be shared across regions blocks readiness.

## Downstream categorical contract

This goal records, but does not encode, categorical transfer cases. A valid
Tasmania-only level will later map to the reserved `__UNSEEN__` level when a
mainland-fitted transform is applied. Source nodata remains the distinct
`__MISSING__` level. Neither sentinel is a source code, and neither mapping is
implemented in Goal 041.

## Non-goals and stopping boundary

Do not construct responses, pseudoabsences, survey-supported absences, or
partitions. Do not reduce predictors, fit scaling or imputation, encode
categories, fit any model, inspect outer outcomes, make maps, or revise the
manuscript. Cell-level data and values remain ignored.

Perform the core run and one focused repair pass for a material failure. Stop
after a valid decision receipt; additional presentation polish or exploratory
predictor engineering is not part of this goal.

## Source correction (2026-08-14)

Soil Order is sourced from the checksum-bound CSIRO DAP COG (file 64191223)
and its official legend (file 64191225), not the retired WCS transport. Pilot
equivalence uses the explicit native COG centroid and a corrected private
baseline; the earlier WMS renderer discrepancy is retained only as aggregate
audit evidence (97 legacy exact, 31 legacy discrepancies: 12 mainland and 19
Tasmania). Production continues to use exact half-open native-pixel modal
aggregation.
