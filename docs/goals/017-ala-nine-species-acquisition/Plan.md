# Plan

The executable contract is `config/ala_full_acquisition_plan.json` and the
standard-library runner is `src/dsdm_phase1/ala_full_acquisition.py`.

Stages are: create one temporary explicit Galah config; call each of the nine
canonical parent counts exactly once; enforce per-species/aggregate count and
disk gates; perform one fresh Pseudocheirus 2001 canary count and bounded
occurrence call; then acquire species in ascending measured-count order,
freezing every CSV immediately. A failure writes a sanitised partial evidence
package and stops before the next species. The five tracked evidence files are
`counts.json`, `identity.json`, `acquisition.json`, `review.json`, and
`manifest.json`; raw files remain ignored under the configured Goal017 raw
directory.

Goal016 decision-plan and field-contract hashes, plus the phase-1 decision
bundle hash, are pinned in the machine-readable plan.
