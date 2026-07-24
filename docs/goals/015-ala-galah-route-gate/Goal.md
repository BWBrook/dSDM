# Goal 015: ALA Galah Route Gate

## Objective

Replace the failed bespoke Goal 014 transport with one route-correct,
unauthenticated `galah-python==0.13.3` pilot for accepted *Pseudocheirus
peregrinus* in Tasmania in 2001. The pilot decides only whether this supported
route is usable for later acquisition design.

## Authority

Barry reported an external ALA support reply confirming that a registered
account email is sufficient for ordinary occurrence downloads; API token, JWT,
or Bearer authentication is not required. Authentication applies only to
separately approved sensitive or unobfuscated access. Support described the
endpoint as current and recommended galah-python; the reply author maintains
that client.

Goal 014 remains unchanged as historical evidence. Its malformed
single-occurrences URL likely caused the HTTP 403, but that is our inference,
not a reproduced causal diagnosis.

## Current state

`galah_route_usable_for_later_acquisition_design`, established only by exact
local replay of both ignored raw CSVs. Tracked-only validation remains
`galah_pilot_tracked_evidence_valid_raw_replay_required`.

## Boundaries

- One `atlas_counts` call and, only for an exact count of 17 within 1--100,
  one `atlas_occurrences` call.
- Exact accepted concept, `stateProvince=Tasmania`, `year=2001`, and
  `use_data_profile=False`.
- Runtime account only through `ALA_DOWNLOAD_EMAIL`; one explicit temporary
  Galah config destroyed on success and failure.
- `authenticate=False`, `email_notify=False`, `reason=4`, `verbose=False`,
  `mint_doi=False`, and a 900-second occurrence-call alarm.
- Immediate ignored CSV serialization of both returned DataFrames. These are
  the earliest Galah-exposed artifacts, not the provider ZIP.
- The requested `license` field is accepted only under the explicit
  `dwcHeaders=true` return alias `dcterms:license`; every other required core
  field remains literal.
- No retry, alternate transport, sensitive-data request, DOI, full acquisition,
  normalization, modelling, or camera work.
