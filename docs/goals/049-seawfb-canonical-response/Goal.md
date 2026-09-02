# Goal 049 - SEAWFB canonical response substrate and panel freeze

## Scientific objective

Build the canonical 2001-2025 species-by-0.01-degree-cell response substrate
for the south-east Australian woodland/forest bird experiment. Expand the
Goal 048 feasibility seed into a source-based bird universe, while preserving
the frozen NCP, SEH, and NNC outer assessment and every leakage firewall.

The goal has two ordered stages. Stage A freezes the biological registry,
ecological roles, ALA concept unions, acquisition contract, and panel policy
without querying new occurrence support. Stage B may begin only after Stage A
passes. It promotes exact Goal 048 receipts where their complete contract is
unchanged, acquires the remaining taxa through aggregate `galah` counts,
constructs the private canonical membership table, and freezes the primary and
secondary target panels.

## Scientific question protected by this goal

The later experiment asks whether species-rich dSDM pretraining improves
geographic transfer of relative habitat-suitability discrimination over a
matched target-only neural model and strong conventional SDMs. Goal 049 does
not answer that question. It creates the response substrate on which the
prospective experiment can be run.

The atomic response is a biological species by eligible 0.01-degree cell over
2001-2025. Presence means at least one accepted ALA occurrence in the cell.
The contrasting class is an effort-supported target-group background, not a
true absence, occupancy state, independent survey, or abundance observation.

## Count-free biological registry

Use two versioned authorities:

1. BirdLife Australia's Working List of Australian Birds v4.3 for its current
   Australian species-name and stable-ID crosswalk.
2. Australian Bird Data v1 (Garnett et al. 2015) for species rank, native and
   extant status, jurisdiction, non-trivial habitat use, and national movement.

The ALA current accepted species concept is the operational occurrence unit.
Every source row and transformation must be checksum-bound. All 100 Goal 048
seed taxa stay visible in the registry even if the new rule gives them no
active role.

Roles are overlapping booleans:

- **Effort donor:** native, extant, non-vagrant south-east-relevant species
  with at least one non-trivial terrestrial feeding habitat. Movement,
  nocturnality, aerial foraging, and home-range scale do not disqualify an
  effort-only donor.
- **Auxiliary head:** an effort donor with non-trivial feeding use of dry or
  wet temperate sclerophyll forest/woodland or rainforest, excluding nomadic
  or irruptive species and the prespecified scale/detection-mismatch families.
- **Focal target candidate:** the same count-free ecological eligibility as
  an auxiliary head. Final target-panel status comes only from the frozen
  support gates; an extra subjective habitat-specialism filter is forbidden.

Regular seasonal migrants remain eligible. For every focal experiment, the
focal species is removed from both the effort count and auxiliary pretraining.
Richness or effort is never a predictor.

## Taxonomy freeze

Resolve each registry member to exactly one current ALA accepted species
parent. Its ordered query union contains the accepted parent, accepted
descendant/subspecies concepts, and only aliases whose accepted concept points
to that parent or one of those descendants. Composite slash aliases are
excluded. No identifier may occur in two biological-species unions.

Ambiguous resolution, parent collision, shared identifiers, or an unresolved
mandatory seed stops Stage A. Occurrence support cannot resolve taxonomy.

## Canonical aggregate acquisition

Process one species at a time through `galah.atlas_counts()` using the exact
frozen 2001-2025, `PRESENT`, spatially-valid, bounding-box/domain, and ordered
concept-union contract. Require a separately scoped total to equal the sum of
`lat_long` facets exactly. Snap facets immediately to the 0.01-degree grid,
retain only exact Goal 048-domain cells, checksum the private receipt, and
discard coordinate strings before continuing.

No raw occurrence rows, observer fields, provider identifiers, contact value,
or raw-row fallback is allowed. A Goal 048 species-cell receipt may be
promoted only when every query, concept, domain, conservation, and
normalisation property matches exactly; otherwise reacquire it in the Goal 049
namespace without changing Goal 048 history.

## Frozen panels

The **primary common panel** contains every focal candidate that passes the
retained-training gates and the `X=10` evaluation gates in all three frozen
regions. It remains the headline paired comparison and must contain at least
20 species.

Three **regional secondary panels** retain every valid species-region task
that passes retained-training and that region's `X=10` gates. These panels
avoid discarding scientifically usable contrasts merely because a species is
not estimable in a different region. They were prespecified after Goal 048's
seed feasibility census, but before expanded Goal 049 counts and before any
model outcome; that provenance must remain explicit. There is no two-of-three
panel.

`X=20` is evaluation-only sensitivity and cannot change any `X=10` panel.
Gates are pass/fail only and occurrence magnitudes cannot rank species or
regions.

## Acceptance criteria

Goal 049 is complete only when:

1. all authority files, versions, licences, retrieval details, and hashes are
   frozen and independently replayable;
2. the registry and ecological roles are generated solely from the frozen
   authority fields, with a compact exception ledger below the 10% stop bound;
3. every active species has one collision-free ALA concept union frozen before
   new occurrence support is queried;
4. every promoted or newly acquired receipt satisfies exact contract identity,
   total-to-facet conservation, domain membership, sorting, uniqueness, and
   checksum validation;
5. one private canonical species-cell table reconstructs focal-excluded
   `X=10` and `X=20` support exactly;
6. the common and three regional panels are derived only through the frozen
   training and evaluation gates, with at least 20 common targets;
7. tracked receipts expose hashes, aggregate counts, panel membership, and
   exclusions without coordinates, private cell lists, or model outcomes;
8. focused tests and the Goal 049 validator pass from a clean checkout; and
9. no model is fit and no outer performance outcome is opened.

## Non-goals

- changing, substituting, or reranking NCP, SEH, or NNC;
- tuning `X=10`, `X=20`, buffers, support gates, or ecological roles after
  occurrence counts;
- modelling, architecture selection, training, thresholding, or evaluation;
- treating effort-supported backgrounds as true absences; or
- preserving obsolete Goal 048 implementation details through compatibility
  layers.
