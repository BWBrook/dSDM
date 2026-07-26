# Goal 024 — Predictor source-recovery and structural-domain freeze

Freeze a deterministic, supported predictor domain from immutable Goal022
products after the bounded source audit found `repair_not_authorized`.

Eight downstream species and all 28 predictors remain fixed. No predictor
value is repaired, substituted, imputed, transformed, encoded, scaled,
partitioned, mapped, or modelled in this goal. The primary domain is the set of
canonical cells with observed nonmissing values for all 28 predictors. The
inference scope is conditional on that domain.

Expected footprint: 74,073 map cells (71,023 included; 3,050 excluded), 5,407
response cells (5,087 included; 320 excluded), and 13,455 response rows
(12,711 included; 744 excluded). Survey-supported absences remain first-class
(2,114 included; 46 excluded).

Operational estimand: a species-specific relative response score over
canonical cells in `D_struct`, conditional on the accepted
presence/survey-supported-absence/pseudoabsence construction. This is not
detection-corrected occupancy, abundance, population prevalence, or inference
outside `D_struct`.
