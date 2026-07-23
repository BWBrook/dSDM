# Goal 010: ALA Taxon Resolution Evidence Gate

## Objective

Create a reproducible, fail-closed evidence package resolving the nine
authoritative Phase 1 species against official ALA name-matching/taxon metadata
surfaces. Produce candidates for Barry's sign-off without changing P1-D003 or
the authoritative decision bundle.

## Scope and boundaries

- Use only official ALA name-matching and BIE taxon metadata endpoints.
- Store compact dated raw responses, request metadata, checksums, and a
  normalized nine-species candidate contract under `evidence/ala_taxon_resolution/`.
- Add standard-library retrieval/validation code and offline deterministic tests.
- Do not query occurrence endpoints, download records, access `data/` or
  `temp/`, alter the decision bundle/register, or claim Barry approval.

## Gate semantics

Each candidate must have exact/justified species-rank scientific matching,
Animalia/Mammalia classification, stable concept-ID round-trip evidence,
checksum-linked raw responses, and no material issue. Candidates are labelled
`recommendable` or `needs_review`; unresolved aliases remain explicitly empty.

## Acceptance

- Nine canonical queries and their evidence are linked deterministically.
- Raw JSON checksums and request metadata validate offline.
- Negative mutations fail closed for fuzzy/non-exact match, rank or
  classification mismatch, duplicate concepts, checksum drift, missing response,
  and invented alias claims.
- P1-D003 remains pending and no authoritative contract is edited.
