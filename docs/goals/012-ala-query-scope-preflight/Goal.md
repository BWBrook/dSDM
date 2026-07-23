# Goal 012: ALA Query-Scope Preflight

## Objective

Use public ALA metadata and count-only occurrence-search requests to test
whether the nine accepted species-level AFD queries cover synonym-normalized
and accepted-descendant records for the inclusive 2001--2025 Tasmania scope.
Freeze a deterministic request profile and choose the runtime-proven
parent-species expansion as the default, retaining an explicit
parent-plus-required-child/synonym union as the mandatory acquisition-time
fallback.

## Boundaries

- Do not download occurrence rows, coordinates, facets, or bulk exports.
- Retain only sanitized request metadata, timestamps, counts, and responses
  structurally proven to contain zero occurrence records.
- Do not inspect or modify `data/`, `temp/`, camera/private sources, spatial or
  model payloads, Goal 010 evidence, or Goal 011 artefacts except a directly
  necessary shared contract test.
- Leave P1-D008 camera staging untouched and do not stage, commit, or push.

## Required decision

Probe all nine focal parent concepts, the approved Macropus synonym pathway,
and all three Vombatus child concepts. Use a decisive count-only containment or
equivalence test where supported; otherwise select the explicit union fallback
and state the remaining service ambiguity. Preserve stable occurrence-ID
deduplication and submitted/matched/accepted identity and rank in the future
record-field contract.

## Acceptance

- Versioned, checksum-valid, offline-replayable evidence and review exist under
  `evidence/ala_query_scope/2026-07-23/`.
- A validated request profile freezes the temporal and broad Tasmania scope,
  `disableAllQualityFilters=true` local-quality mode, parent query mode,
  fallback, exact future `fl` retrieval set, and structured ALA-to-project
  field/provenance mapping without acquiring records. The metadata-only
  `/occurrences/index/fields` response and pinned biocache lft/rgt source
  evidence are retained; no occurrence endpoint is used for field discovery.
- Tests fail closed on record/coordinate leakage, malformed counts, unsafe
  drift, incomplete canonical probe bindings, response-query echo changes,
  weak containment, missing fallback, identity, or deduplication requirements,
  even when a tampered package is re-checksummed.
