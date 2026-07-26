# Goal 023 — Predictor support and map-domain decision gate

Freeze a deterministic, aggregate-only diagnostic of support, missingness,
categorical levels, environmental envelopes, and policy consequences using the
Goal 021 response and Goal 022 raw predictors. This gate informs Barry's
decision; it does not choose a missing-data or map-domain policy.

The diagnostic preserves all 74,073 canonical cells and 5,407 response cells,
keeps survey-supported absences as observations, and stops before imputation,
encoding, scaling, partitions, mapping, or modelling. Tracked evidence contains
no coordinates, grid IDs, row payloads, site/camera identifiers, timing, or
private paths.
