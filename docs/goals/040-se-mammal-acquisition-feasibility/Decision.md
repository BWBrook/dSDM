# Decision

## Domain, sampling process, and scale of inference

The domain is the established future SE-bird WGS84 0.01-degree cell-centroid
frame: longitude 135.375–153.625 and latitude -43.6275–-23.7775. Its canonical
ecological selector is the frozen allowlist of 163 whole IBRA7.1 subregions
reconciled from the archived study polygon. The 2.15% archived `MDD01` sliver
is explicitly excluded because admitting it would widen the domain to the
whole subregion. A cell is eligible only when its centroid is covered by the
IBRA7.1 selector and ABS ASGS land, and is not covered by a Geofabric type-25
reservoir or type-26 lake. Northern Territory and Other Territories are
excluded. Every eligible cell is classified as `southeast_mainland` or
`tasmania`; the regional distinction must survive aggregation. The inclusive
response period is 2001–2025.

Before any count query, freeze the tracked exact-domain manifest, including the
IBRA7.1, ASGS land/state, and Geofabric authorities; the 163-code allowlist;
the MDD01 reconciliation; ordered cell identity; product/version, publisher,
source URL, retrieval time, checksum, CRS, licence, and deterministic spatial
rules. Earlier processed SE files remain archaeological design evidence only.

ALA records arise from a changing, opportunistic observation and reporting
process. Record volume therefore measures indexed records, not sampling effort,
independent replicates, occupancy, abundance, or prevalence. Provider-record
deduplication and species-cell collapse reduce obvious duplication but do not
remove spatial sampling bias or imperfect detection. Camera evidence has
survey/site replication upstream, but Goal 040 retains only provenance-safe
Tasmania cell-level supported absences; it does not treat grid cells as
independent experimental units or donor observations.

## Taxon ledger and count-blind tiers

The frozen acquisition cohort is a conservative, nonrepresentative 21-taxon
feasibility subset drawn from the complete AMTC v5.0 species frame. It contains
16 mainland-only donors plus five approved anchors with mainland-donor,
Tasmania-support, and shared-evaluation roles. Selection is biased toward taxa
with available current VIC/ACT legal-status evidence and is not a census of
southeastern mammals. The permitted inference is operational acquisition and
support feasibility for this frozen subset only.

Eligibility comprises native, extant, terrestrial or arboreal, non-volant,
non-marine, non-strongly-aquatic mammals. Exclude introduced,
captive, fossil, subfossil, and extralimital records; bats; marine mammals;
platypus; and other strongly aquatic specialists. ALA occurrence records alone
cannot establish native/extant/ecological eligibility. Before any count query,
the ledger must record the evidence and reason for every inclusion/exclusion,
accepted ALA and AFD concept identities, and reviewed descendant/synonym query
paths, source citations, and query roles. The final privacy-safe ledger is
tracked at `metadata/goal040_taxon_query_ledger.csv`; only raw discovery
responses remain ignored.

Tiers are assigned from distinct post-QC species × land cells, never raw rows:

- `support_observed`: at least one cell anywhere in the domain; retained as a
  potential target-group donor even when not target-eligible;
- `mainland_pretraining_candidate`: at least 100 southeast-mainland cells; and
- `shared_evaluation_candidate`: at least 100 southeast-mainland cells and 30
  Tasmania cells.

These are simple acquisition-feasibility screens, not effective sample sizes
or guarantees of model adequacy. Sparse frozen taxa remain visible in the
ledger and aggregate census. No taxon is pruned for later model performance,
and later results cannot be generalised to all southeastern mammals.
The expected shared anchors are *Notamacropus rufogriseus*, *Trichosurus
vulpecula*, *Pseudocheirus peregrinus*, *Vombatus ursinus*, and *Dasyurus
maculatus*. They must earn the same tiers as all other taxa; additional shared
taxa qualify objectively.

## Acquisition and QA

Use `galah-python==0.13.3`, Barry's registered email read only at runtime from
`ALA_DOWNLOAD_EMAIL`, and no authentication. Never write the email into a
manifest, log, command, or tracked file. Freeze identity-addressed taxonomy,
query, count, and download manifests for accepted concepts and reviewed
descendants/synonyms over the exact domain and period.

After the response-blind count census, automatically acquire all frozen
queries only when total count is at most 2,000,000 rows, every taxon is at most
500,000 rows, projected working space (`2048 bytes × rows × 5`) fits, and at
least 30 GiB remains free. Otherwise stop for a resource-route decision without
sampling or silently narrowing the cohort. Raw downloads, row audit, taxon
ledger working material, and normalised row/cell products stay under ignored
`data/`.

Retain the established QA: stable provider record identity is required for
deduplication; coordinates must be finite and valid; reported uncertainty over
1,000 m is excluded; missing uncertainty is retained but explicitly flagged;
there is no nearest-land rescue; and accepted records collapse to one presence
per species × eligible cell. Submitted, matched, and accepted taxon identities,
query ancestry, resource provenance, QA flags, and duplicate dispositions remain
auditable privately.

## Four-state response and target-group support

The only states are `presence`, `camera_survey_supported_absence`,
`target_group_background_candidate`, and `unknown`, in that precedence order.
Presence overrides all competing evidence. Camera absence is Tasmania-only,
provenance-distinct, and never contributes donor support. A target-group
candidate is neither a true absence nor an occupancy non-detection.

For each target and cell, preserve the threshold-neutral count of distinct
other eligible native support species; the target itself is excluded. The
primary convention is X=3, with nested, performance-blind sensitivities X=2
and X=5 (`X5 ⊂ X3 ⊂ X2`). Preserve the inherited inclusive >=5 km distance
from the nearest target presence. Camera concordance is an aggregate diagnostic
only and cannot select X or rescue a failed substrate.

Future split materialisation must recompute support and distance from records
allowed for that split. Goal 040 must not freeze globally final binary labels.
Within any future comparison, conventional and dSDM methods receive the same
materialised response universe.

## Separate future estimands

- Cross-species transfer excludes the target entirely from mainland
  multispecies pretraining.
- Same-species geographic transfer uses the target's mainland data.
- Target-only mainland pretraining is a separate control using only the
  target's mainland data.

These designs answer different questions and their claims must not be
conflated. Goal 040 evaluates their substrate feasibility only.

## Predictor portability

Goal 040 must produce a source/definition matrix and a small, response-neutral
cross-domain pilot. Every retained layer must use one common product/version,
definition, units, reference period, resolution, alignment/resampling rule,
nodata policy, and—where categorical—ontology across mainland and Tasmania.
Tasmania's current full28 and old SE processed maps are not automatically
portable. Retain the largest defensible common panel; do not force full28 and
do not use a region-specific fallback.

The pilot selects 64 land cells per region by systematic spatial strata using
only the frozen land mask, region, and cell geometry. Row-level pilot output
stays ignored. Aggregate evidence reports continuous missingness, finite range,
Tasmania-outside-mainland-range fraction, and standardised cross-domain
support; categorical evidence reports missingness, level support by region,
and Tasmania novel-level fraction. These small-pilot diagnostics expose gross
source, nodata, and ontology failures; they do not estimate the full
environmental distribution or authorise extrapolative models. Unproven common
source identity is `repair` or `blocked`, never readiness.

## Final decision

`ready` requires frozen taxonomy and boundary manifests; complete full
acquisition and QC; at least 15 observed support species, 10 mainland
pretraining candidates, and five shared evaluation candidates; complete X=3
support diagnostics; at least one retained
common predictor panel; continuous and categorical novelty reports; and clean
privacy/manifest validation. These minima establish a plausible later
experiment, not statistical power or model fitness.

All five expected anchors must be evaluated and their tier outcomes reported,
but none is individually a readiness requirement. An anchor may be data-limited
without vetoing an otherwise adequate objectively selected shared cohort.

The tracked-evidence ban on donor identities prohibits donor-to-cell
associations and cell-level donor identity disclosure. It does not hide the
tracked cohort/taxon query ledger.

Use `repair` for a bounded, scientifically defensible correction to contract,
source identity, extraction, QA, or coverage. Use `blocked` when a required
source is unavailable or no defensible in-scope repair exists. No model fitting,
architecture work, performance selection, maps, manuscript claims, full
regional model execution, outer access, or pretraining-ready binary claim is
permitted.
