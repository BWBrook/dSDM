# Decision

## Status

Goal 042 is `ready` as of 2026-08-20.

## Frozen design

All 21 Goal 040 observed taxa contribute to the mainland target-group effort
proxy. *Burramys parvus* remains support-only because it has 87 mainland
cells; the other 20 taxa are response heads. For each of the five shared
targets, cross-species dSDM pretraining uses the exact other 19 heads and
excludes the target entirely. Target fine-tuning and conventional models use
that target's mainland response only.

The mainland primary reference uses presence versus target-group background
cells with at least three distinct other support species and a distance of at
least 5 km from target presence. X=2 and X=5 are retained as nested sensitivity
flags. These are effort-supported background candidates, not true absences,
occupancy non-detections, or prevalence estimates.

The 755,077-row mainland table is deliberately marked
`full_data_reference_not_split_authorised`. It must not be supplied directly
to model fitting. Goal 043 must call the same materialiser separately with the
records authorised for each partition, so held records cannot affect training
support or nearest-presence distance.

## Mainland reference evidence

| Response head | Presence cells | X=3 background cells | Presence fraction |
|---|---:|---:|---:|
| *Dasyurus maculatus* | 2,619 | 10,752 | 0.196 |
| *Gymnobelideus leadbeateri* | 813 | 16,105 | 0.048 |
| *Macropus giganteus* | 26,758 | 1,789 | 0.937 |
| *Mastacomys fuscus* | 542 | 16,116 | 0.033 |
| *Notamacropus rufogriseus* | 11,575 | 4,761 | 0.709 |
| *Petauroides volans* | 6,650 | 9,016 | 0.424 |
| *Petaurus australis* | 5,534 | 9,500 | 0.368 |
| *Petaurus norfolcensis* | 3,038 | 10,507 | 0.224 |
| *Petrogale penicillata* | 883 | 15,317 | 0.055 |
| *Phascogale tapoatafa* | 1,962 | 13,404 | 0.128 |
| *Phascolarctos cinereus* | 23,512 | 4,884 | 0.828 |
| *Potorous longipes* | 972 | 15,877 | 0.058 |
| *Pseudocheirus peregrinus* | 15,990 | 2,031 | 0.887 |
| *Pseudomys fumeus* | 210 | 16,195 | 0.013 |
| *Pseudomys novaehollandiae* | 343 | 15,480 | 0.022 |
| *Pseudomys shortridgei* | 212 | 16,330 | 0.013 |
| *Sminthopsis crassicaudata* | 333 | 16,619 | 0.020 |
| *Sminthopsis leucopus* | 1,202 | 14,242 | 0.078 |
| *Trichosurus vulpecula* | 23,789 | 396 | 0.984 |
| *Vombatus ursinus* | 16,443 | 4,751 | 0.776 |

This broad response spectrum is useful. It includes very sparse mainland taxa,
intermediate cases, and high-prevalence species rather than reproducing the
uniformly difficult Tasmanian prevalence profile.

## Tasmania evaluation evidence

Tasmania contains only ALA or camera presence and camera survey-supported
absence. Presence overrides a camera absence conflict. No target-group
background cell is admitted.

| Target | Combined presence | Camera-supported absence | Presence fraction |
|---|---:|---:|---:|
| *Dasyurus maculatus* | 974 | 221 | 0.815 |
| *Notamacropus rufogriseus* | 1,366 | 146 | 0.903 |
| *Pseudocheirus peregrinus* | 380 | 596 | 0.389 |
| *Trichosurus vulpecula* | 1,228 | 174 | 0.876 |
| *Vombatus ursinus* | 1,150 | 138 | 0.893 |

The resulting 6,373 species-cell responses include the important lower-
prevalence ringtail contrast as well as four presence-dominated targets. Six
camera-absence conflicts across the five targets were resolved to presence.

## Binding and privacy

Every response cell has an exact `cell_id` match in the Goal 041 24-predictor
table. The ignored Parquet receipts are checksum-bound in
`metadata/goal042_response_manifest.json`; no predictor values are duplicated.
The tracked surface contains species-level aggregates and cohort identities,
but no cell IDs, coordinates, donor-to-cell associations, camera identifiers,
or row payloads.

The Bass Strait firewall passed: zero Tasmania rows occur in the mainland
output, zero mainland rows occur in the Tasmania output, and Tasmania cannot
enter pretraining, fine-tuning, partition construction, or transformation
fitting.

## Decision

Accept the response substrate and advance to mainland spatial partitions and
split-fitted predictor transformations. Do not open Tasmania during that work.
