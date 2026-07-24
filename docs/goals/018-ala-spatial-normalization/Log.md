# Log

## 2026-07-24 — accepted production result

Observation: the production run and separate full raw/output validation passed
exact semantic replay. All 50,834 inputs were audited exactly once: 40,263
accepted, 10,571 excluded, and zero quarantines or taxon mismatches. The
accepted layer contains 6,629 unique species-grid presence rows.

Observed primary exclusions were 9,355 records with uncertainty above 1000 m,
18 missing-coordinate records, 972 records without an eligible canonical cell,
and 226 records outside the coast boundary. Of accepted records, 6,253 were
low-cell-certainty; 1,225 presence cells were low-cell-certainty-only. Maximum
accepted centroid distance was 690.900947 m.

Per-species warning: *Macropus giganteus* contributes only 34 presence cells.
*Thylogale billardierii* contributes 3,919 accepted records across 764 cells.
These are opportunistic occurrence footprints, not prevalence estimates, so the
downstream no-pseudoabsence safeguard remains in force.

Focused tests (23/23), full suite (147/147), production run, and separate full
validation passed. Tracked evidence is aggregate-only; private row output is
ignored. The ordinary two-directory publication crash window is recoverable and
accepted.

Inference: Goal018 is complete. Its outputs are presence evidence, not
abundance, occupancy, or absence evidence.
