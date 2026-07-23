# Goal 013: ALA Acquisition Pilot

## Objective

Execute a small direct-ALA-API row pilot against the frozen Goal 012 request
and field contract. Prove that the exact 20-field record surface, bounded
pagination, raw-response provenance, and occurrenceID-based deduplication can
be acquired and validated without beginning full acquisition or ecological
analysis.

## Boundaries

- Make exactly the planned 23 successful record-bearing requests: two
  25-record pages for each of nine focal parents and one 25-record page for
  each of the five required fallback branches.
- Never exceed 575 returned rows. Do not compensate for zero or short pages.
- Use only the frozen official occurrence-search endpoint, Tasmania and
  inclusive 2001--2025 filters, `facet=false`,
  `disableAllQualityFilters=true`, and the exact Goal 012 future `fl` set.
- Retain raw response bytes only below
  `data/raw/ala/goal013-pilot/2026-07-23/`; retain no occurrence rows,
  occurrence IDs, coordinates, or site-level locations in tracked evidence.
- Do not use bulk download, authentication, galah, browser automation, camera
  sources, normalization, spatial processing, or model inputs.
- Do not inspect sibling `data/` paths. Do not stage, commit, push, clean,
  move, or delete.

## Required decision

Choose a stable, supported pagination order and validate it from the live
bounded responses. Report actual field presence/null/type behaviour, page
overlap, occurrenceID validity and deduplication, parent-query execution,
Macropus synonym ID/name behaviour, and Vombatus child behaviour. Preserve
unresolved coverage assertions explicitly.

## Acceptance

Return either
`pilot_pass_ready_for_bounded_full_acquisition_design` or a precise
blocked/revise state. A pass means only that the bounded row-level contract is
fit to inform full-acquisition design; it must not imply complete acquisition,
camera readiness, normalization readiness, ecological totals, or descendant
coverage beyond the sampled rows.

The occurrence-search route is limited to the first 5,000 results and does not
document snapshot-consistent pagination. Therefore, the pilot may establish
only explicit-order acceptance and bounded page-overlap behaviour. Any species
query above 5,000 results requires a later supported download/export design;
Goal 013 neither selects nor executes that design.
