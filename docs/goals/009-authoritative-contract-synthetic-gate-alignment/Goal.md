# Goal 009: Authoritative Contract-to-Synthetic Gate Alignment

## Objective

Align the synthetic acquisition/request/normalized-row chain with the
authoritative Goal 008 decision bundle. Canonicalize camera non-detection as
`survey_supported_absence`, expose policy/readiness provenance, and fail closed
on legacy vocabulary, contradictory policy, or sensitive synthetic-row fields.

## Scope

- Require a valid Goal 008 bundle in the successful synthetic builder chain.
- Canonicalize source contracts, rows, summaries, and fixtures to
  `survey_supported_absence` with a P1-D009 rule identifier.
- Reject legacy active `true_absence`, sensitive camera fields, and finer-than-
  0.01-degree synthetic camera resolution.
- Expose bundle identity/version, policy consolidation, live-acquisition
  status, blockers, and settled policy provenance without performing collapse or
  spatial assignment.
- Add focused tests and update only synthetic fixtures/checksums as needed.

## Non-goals and boundaries

No edits to the Goal 008 bundle/register, live ALA/camera calls, payload reads,
`data/` or `temp/`, source collapse, spatial joins, nearest-cell assignment,
pseudoabsence derivation, modelling, maps, manuscript work, dependencies,
remote compute, staging, commits, or pushes. `true_absence` may remain only in
historical Goal 003-007 documentation and a targeted migration-negative test.

## Acceptance

- Valid bundle plus synthetic inputs yields deterministic canonical summaries
  with exactly the two live blockers.
- Missing/contradictory bundle policy, legacy `true_absence`, missing rule
  provenance, Thylogale pseudoabsence, sensitive fields, or finer resolution
  fail closed.
- Presence dominance and containing-cell/no-nearest-rescue are exposed as
  policy, not executed as source combination or spatial processing.
- Earlier scaffold tests remain green; no payload paths are opened.
