# Plan

1. Validate the frozen Goal017 raw manifest and all occurrence hashes.
2. Validate the WGS84 0.01-degree grid and coast shapefile bindings.
3. Parse taxon, temporal, coordinate and uncertainty fields without repairing
   submitted values; retain independently evaluable reason codes.
4. Assign only exact eligible lattice centroids and collapse accepted rows by
   species and grid cell with provenance counts.
5. Stage ignored row-level outputs and aggregate-only tracked evidence, then
   atomically publish both directories.

Any contract quarantine, schema drift, duplicate provider ID, binding drift, or
existing output directory blocks publication.
