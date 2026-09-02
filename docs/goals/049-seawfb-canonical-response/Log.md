# Goal 049 log

## 2026-09-02 - launch and count-free design

- Barry approved Goal 049 after reviewing the common-panel trade-off.
- Preserved NCP, SEH, and NNC as immutable complete-region holdouts with their
  simultaneous 50 km external buffers.
- Added region-specific secondary panels while retaining the all-region common
  panel as primary; disclosed that this was informed by Goal 048 seed
  feasibility counts but precedes expanded counts and every model outcome.
- Located the ignored historical 100-species bird case and retained it as
  archaeology only; it is not the new authority.
- Chose BirdLife Working List v4.3 plus Australian Bird Data v1 as versioned,
  machine-readable count-free authorities. A dry authority-only application
  suggests approximately 500 possible terrestrial effort donors and roughly
  260 stable forest/woodland candidates before taxonomy exceptions or support
  gates. These are planning estimates, not results or promised panel sizes.
- No new ALA occurrence count was queried while framing the contract.

## 2026-09-02 - Stage A authority and taxonomy freeze

- Downloaded and checksum-bound BirdLife Working List v4.3 and Australian Bird
  Data v1. Australian Bird Data is CC0; the BirdLife workbook has no explicit
  machine-readable reuse licence and is retained only as an ignored private
  research copy.
- Rejected blind reuse of legacy Australian Bird Data identifiers after live
  inspection showed identifier recycling. Added reciprocal name/identifier
  checks, unique exact-name fallback, explicit current-ALA reconciliations,
  and collision-free concept-union validation.
- Froze 653 registry rows: 505 active effort donors and 259 auxiliary
  head/focal candidates. All 100 Goal 048 seed taxa remain visible and are
  assigned uniquely.
- The unresolved manual crosswalk fraction was 6/653 (0.9%), below the frozen
  10% stop bound. Other ledger entries record deterministic name transitions,
  duplicate population-row collapses, and resolved authority fallbacks.
- Froze 505 active ALA species-parent query unions with no unresolved aliases,
  parent collisions, or shared identifiers. No occurrence support informed
  the registry, roles, or taxonomy.

## 2026-09-02 - Stage B aggregate census

- Passed a live aggregate canary for *Casuarius casuarius*: total count 4,
  facet sum 4, four facet groups, and two retained domain cells. No raw
  occurrence row was downloaded or tracked.
- Completed all 505 sequential aggregate queries through `galah`: 56,437,642
  occurrence records represented by 13,731,793 coordinate facets and
  5,048,061 retained species-cell memberships.
- Peak recorded memory stayed below 0.86 GB and the private Goal 049 payload
  stayed below 100 MB, comfortably within the prespecified transport ceilings.
  Every species has one contiguous checkpoint and one checksum-bound private
  cell receipt.

## 2026-09-02 - canonical substrate and panel freeze

- Built the ignored canonical species-cell Parquet substrate and the private
  777-row species-by-region gate ledger. The simultaneous 50 km buffers leave
  787,357 training cells outside all three outer regions and buffers.
- Applied focal-excluded donor richness and the frozen training/evaluation
  gates without ranking species by count margins. The strict common primary
  panel contains 73 species. Regional secondary panels contain 88 species for
  NCP, 122 for SEH, and 134 for NNC.
- Preserved `X=20` as evaluation-only sensitivity. It changes no `X=10` panel
  membership and no two-of-three panel was introduced.
- Independent reconstruction validated all 5,048,061 memberships, gate rows,
  hashes, conservation identities, buffer exclusions, panel memberships, and
  tracked-output privacy. Goal 049 tests passed (37); the Goal 048 regression
  suite passed (57 passed, 1 skipped).
- No model was fit, no performance outcome was generated or opened, no raw
  occurrence row was stored, and no coordinate or private cell identifier was
  written to tracked evidence.
