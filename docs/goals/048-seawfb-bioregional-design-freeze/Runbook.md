# Runbook

## Read first

Read the Goal 048 packet/config plus the existing Goal 040, 041, and 047
decisions and checksum-bound authorities before implementation. Historical
bird products are archaeological evidence only and cannot define current
geometry, taxonomy, occurrence truth, predictors, or performance.

## Starting-state gate

From `/Users/bwbrook/papers/dSDM`:

```sh
pwd
git status --short --branch
git rev-parse --short HEAD
git diff --check
uv sync --locked
```

Stop on unexplained Goal 048 changes or a broken locked environment. Never
clean or revert unrelated work.

## V1.1 restart boundary

The current repair ends after packet/config/incident checks. It authorises no
live occurrence count and no implementation module. A later executor must
complete these count-free prerequisites in order:

1. authenticate and checksum literal whole IBRA7.1 regions, the exact domain,
   the corrected 15-region prospective universe, and required BBS completion;
2. map every mandatory feasibility seed species to an exact ordered union of
   current/reviewed ALA concepts using taxonomy/BIE lookups only;
3. freeze effort, auxiliary, and target roles, reason, habitat, and seasonality;
4. bind the complete official NVIS 7 code-label authority and checksum the
   native-woody/non-woody/missing mapping.

No occurrence count may begin until a validator proves all four receipts are
complete and mutually checksum-bound. Counts cannot resolve ambiguous taxonomy
or ecology. The two taxa exposed in the v1.0 incident remain unaltered.

## Whole-region and domain proof

Authenticate the DCCEEW IBRA7.1 FeatureServer authority and prove exactly 419
unique subregions map to 89 unique regions. Dissolve all official subregions by
region code and reconcile geometry before masks. Candidate holdouts use whole
regions, never clipped bundles. Apply the response-blind 15-region prospective
rule and include complete `BBS01`, `BBS03`, and `BBS28` for BBS. EYB is
excluded because its approximately 0.6678 official-land overlap is below the
literal 0.80 threshold.
The final 0.01-degree grid uses centroid assignment after authoritative land
and open-water masks. Tasmania remains training geography and is not a
candidate.

## Species and NVIS freezes

The mandatory response-blind 100-name feasibility seed ledger must be
reconciled to current ALA concepts without occurrence evidence. For each
biological species, freeze one ordered union containing its accepted species
parent, every reviewed accepted descendant/subspecies, and necessary reviewed
historical alias concepts attributable to that species. Never combine concepts
from different biological species. Separate native terrestrial nonmarine
effort donors, woodland/forest auxiliary heads, and focal targets. Preserve
explicit exclusion reasons. Regularly recurring seasonal migrants remain
eligible under integrated 2001-2025 habitat use; strongly nomadic or irruptive
taxa without a stable static distribution remain excluded. Ambiguity stops.

Before any occurrence count or predictor scoring, checksum the official NVIS
7 code-label authority and every mapping to `native_woody`, `non_woody`, or
`missing`. Ambiguous, unknown, and no-data codes remain missing. Candidate
results may not determine classifications.

## Aggregate feasibility transport

Goal 048 is isolated from the historically bound project environment. The
repository manifest and lock remain pinned to galah 0.13.3 for replay of prior
goals; every Goal 048 live or focused-test invocation must overlay the repaired
release explicitly:

```sh
uv run --with galah-python==0.13.6 python scripts/goal048_seawfb_bioregional_freeze.py validate-freezes --root .
uv run --with galah-python==0.13.6 pytest -q tests/test_goal048_seawfb_bioregional_freeze.py
```

The runner fails closed if a freeze or count stage sees any galah version other
than 0.13.6. It lives under `scripts/` so adding this one-off feasibility route
does not alter the frozen `src/dsdm_phase1` source authority. Do not rerun the
completed canary merely to validate this delivery repair.

Implement the route only after the four prerequisites pass. Process one
biological species per query, sequentially, using `galah.atlas_counts()` under
its exact frozen ordered identifier union. Both calls for that species must use
the identical ordered identifier union and identical frozen:

- inclusive years 2001-2025;
- prospective bounding box and exact-domain interpretation;
- present occurrence status;
- spatial-valid constraint.

Make one separately scoped total-count call and one
`atlas_counts(group_by="lat_long")` call. Before the first live call, the
implementation must validate the exact galah filter serialization locally and
record it without contact values or URLs. Require the facet-count sum to equal
the total exactly. Stop on any mismatch, truncation indication, timeout with
ambiguous completion, malformed facet, or missing coordinate. Never retry by
downloading occurrence rows.

Freeze these prospective transport ceilings and verify disk/RAM capacity
before the canary; enforce returned-group and cumulative limits during
processing:

```text
lat_long groups per species query <= 750,000
lat_long groups across universe <= 10,000,000
private disk                    <= 4 GiB
peak RAM                        <= 8 GiB
concurrency                     = 1 taxon
```

Snap each valid coordinate group immediately to the frozen 0.01-degree grid,
apply the exact domain/mask, and collapse to unique species-cells. Write a
checksum-bound private species-cell receipt, then discard the coordinate
strings before the next taxon. Private receipts may contain cell IDs; tracked
evidence may contain only aggregates and digests. No occurrence records,
provider/event IDs, observer data, email/contact value, or canonical payload
may be requested or retained. These ceilings concern transport only and cannot
rank regions or taxa.

## Gates and response-free selection

For each target, donor richness counts distinct frozen effort-universe species
other than that target. Species-cell evidence may only pass or fail the frozen
`X=10`, `X=20`, spatial-coverage, and estimability gates. It cannot enter any
candidate role score, ranking margin, target-role decision, or predictor.

The 100-name seed ledger supplies an intentionally conservative Goal 048
screen: any later expansion of the eligible donor universe can only relax
`X=10`/`X=20` support. Goal 049 may expand effort, auxiliary, and target
universes under the same frozen taxonomic/ecological rules before canonical
acquisition and before any holdout outcome access. It may not change,
substitute, or re-rank the Goal 048 regions. Canonical Goal 049 data reconstruct
the final exact labels and panels.

The response-free predictor and joint-selector contract remains unchanged:
BIO1-BIO19 plus elevation drive environmental novelty; mapped NVIS drives
fragmentation; ALUM drives land-use entropy. Score all ordered three-region
solutions against their simultaneous retained complement, enforce distinct
nonadjacent regions, 250 km centroid separation, fixed external 50 km buffers,
the exact tie-breaks and ambiguity thresholds in config, and every strict
development-firewall exclusion. Do not select manually from a failed list.

## Evidence and privacy

The v1.1 repair tracks only the packet/config, Log/Decision, and compact
protocol-incident receipt. Future execution may add one aggregate freeze
receipt and one boundary-only map. Raw coordinates, species-cell lists, and
candidate-cell tables remain ignored under
`data/processed/dsdm/goal048-seawfb-bioregional-freeze/` and must be removed if
the goal stops before they become a valid checksum-bound receipt.

The incident receipt contains only the two reported taxa, aggregate values,
the discrepancy, exclusions, and zero forbidden-work counters. It contains no
URL, query string, email/contact value, occurrence row, coordinate, provider or
event identifier, private cell, model result, or selected region.

## Checkpoint validation

Run:

```sh
jq empty config/goal048_seawfb_bioregional_freeze.json
jq empty evidence/seawfb_bioregional_freeze/goal048/protocol_incident.json
uv run --with galah-python==0.13.6 pytest -q tests/test_goal048_seawfb_bioregional_freeze.py
uv run --with galah-python==0.13.6 python scripts/goal048_seawfb_bioregional_freeze.py validate-freezes --root .
uv run --with galah-python==0.13.6 python scripts/goal048_seawfb_bioregional_freeze.py validate --root .
uv run pytest -q
git diff --check
git status --short --branch
```

Also scan changed Goal 048 files for email/contact values, query URLs,
coordinates, provider/event IDs, occurrence rows, model outcomes, and selected
region claims. Do not rerun live ALA access or the aggregate canary, and do not
run scoring.

## Stop and report

Report changed/deleted paths, validation results, incident exclusions, and the
exact prospective restart boundary. Do not stage, commit, push, acquire rows,
score candidates, select regions, construct models, predict, threshold, or
edit the manuscript.
