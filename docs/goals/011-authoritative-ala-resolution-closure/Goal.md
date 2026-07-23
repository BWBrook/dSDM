# Goal 011: Authoritative ALA Resolution Closure

## Objective

Apply Barry's explicit 2026-07-23 approval of the Goal 010 nine-species ALA
table to the authoritative Phase 1 contract. Pin the accepted ALA/AFD species
concepts, promote only the approved `Macropus rufogriseus` historical alias,
resolve P1-D003, and leave P1-D008 camera staging as the sole operational
blocker.

## Scope and boundaries

- Update only the authoritative bundle/register, directly affected contracts,
  manifests, tests, and this Goal 011 packet.
- Do not edit Goal 010 evidence, candidates, review, validator, or raw
  responses.
- Do not read or modify `data/`, `temp/`, occurrence, camera, spatial, or
  model surfaces; do not make live ALA calls.
- Keep subordinate AFD concepts out of the nine focal-species rows.

## Accepted resolution

The nine existing species rows receive the exact Goal 010 AFD concept IDs,
validated against a deterministic species-to-concept mapping (not only UUID
shape or uniqueness).
Historical aliases remain empty except for `Macropus rufogriseus` under
`notamacropus_rufogriseus`.

## Subtaxon policy

Synonym normalization and accepted descendants are in scope for later live
acquisition. The acquisition gate must retain submitted, matched, and
accepted taxon identity/rank and assert synonym/descendant coverage before
execution. If ALA expansion fails, it must fall back to the accepted parent
plus required accepted child IDs and deduplicate. `Macropus giganteus
tasmaniensis` resolves to the accepted species and retains its exact AFD
name-concept ID; the three accepted Vombatus subspecies retain their exact
full AFD child-concept URLs and remain subordinate, not focal rows. Every
synthetic `ala_occurrence` row must retain a submitted/matched/accepted
identity block and accepted rank (`species` or `subspecies`); source identities
may differ from the canonical focal row name and must remain preserved. Camera
and pseudoabsence rows must not carry that block.

## Acceptance

- Bundle schema is `1.1`, P1-D003 is resolved, and P1-D008 is the sole pending
  prerequisite.
- Goal 010 candidates reconcile one-to-one with species IDs, concepts, names,
  and aliases.
- The structured resolution policy is provenance-linked and fail-closed on
  missing scope/assertion/fallback/identity-retention fields.
- Mocked ALA intent is resolved, deterministic, and carries the executable
  subtaxon/fallback plan but remains non-executed;
- Exact concept swaps, forged UUIDs, wrong child/synonym IDs, omitted intent
  scope, and malformed/leaked ALA identity blocks fail closed;
  camera intent remains blocked by P1-D008.
