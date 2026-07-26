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

## 2026-07-26 — P1-D014 correction rebinding and invariant replay

Goal018 was rebound to the corrected decision bundle, the rebound Goal017 plan,
and the refreshed Goal017 manifest. Its plan hash moved from
`6dff937876ea572babdc0f74944edb5d9311af0d6295c58cee1923ace587c5c7`
to `516b0bbb089cfcbc6558677ea0f0b4ac2662acb2c79e33308485ae6ff605d75b`.
The source-inventory hash moved from
`b54d4f7fa0d4dfde89d11659d7a13ab4dfe6329a7c62716009e99b735b489810`
to `f1902291ab36ee2603b7394e08eeeede35e620c94025d566122898d636b308ea`;
the evidence-manifest hash moved from
`dab5e596e7de9786c475c41f1fc738f8d2c693cb54da2262b1a7e396ac97648e`
to `74766fc49bb809f7af7b9716ce96bbc081d9c0c165f6e304dfbf38bfee19717e`.
The other four aggregate evidence payloads remained byte-identical.

Full raw recomputation reproduced the private scientific products byte for
byte: `row_audit.csv` remained
`d4f8d7278f67cfb40c5f8e0f56a685ed5f2e747a4c547f4479b1cda53398bed6`
and `presence.csv` remained
`a41f3570cbc5afaaa15358fe25a011bdf57e3fdb4c9b488ac658e2b774b022d4`.
The replay again reconciled 50,834 inputs, 40,263 accepted rows, and 6,629
species-grid presences. Goal018 is reaccepted without a scientific-output
change.
