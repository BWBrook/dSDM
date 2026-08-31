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

## V1.3 frozen boundary

The count-free prerequisite freezes are complete and the sequential census has
completed. The high-level census receipt records 96/96 effort species,
7,211,394 facet groups, 2,620,016 retained species-cell memberships, and
30,496,223 total occurrences, with zero occurrence rows and zero model
outcomes. Peak RAM was 937,869,312 bytes and private disk use was
141,123,472 bytes. Four frozen role exclusions remain unqueried.

Response-free scoring and hard-gate filtering are complete. The frozen design
is NCP (Naracoorte Coastal Plain, supported transfer), SEH (South Eastern
Highlands, environmental edge), and NNC (NSW North Coast, mosaic). Treat all
three whole regions and their external 50 km buffers as one simultaneous
development exclusion. Tasmania remains ordinary training geography.

The following count-free prerequisites were completed before the census:

1. authenticate and checksum literal whole IBRA7.1 regions, the exact domain,
   the corrected 15-region prospective universe, and required BBS completion;
2. map every mandatory feasibility seed species to an exact ordered union of
   current/reviewed ALA concepts using taxonomy/BIE lookups only;
3. freeze effort, auxiliary, and target roles, reason, habitat, and seasonality;
4. bind the complete official NVIS 7 code-label authority and checksum the
   native-woody/non-woody/missing mapping.

At the original pre-count boundary, no occurrence count could begin until a
validator proved all four receipts were complete and mutually checksum-bound.
Counts could not resolve ambiguous taxonomy or ecology. The two taxa exposed
in the v1.0 incident remain unaltered.

## Predictor extension

The private extension output is
`data/processed/dsdm/goal048-seawfb-bioregional-freeze/predictors/predictor_substrate.parquet`.
It contains exactly 1,144,286 rows: 1,125,325 preserved Goal 041 rows and
18,961 BBS additions. The extension uses local categorical sources, an aligned
native-grid ALA WCS WorldClim crop for the northern gap, and 29 exact GA elevation
blocks. Its source overlap proof, block receipts, output manifest, and old-row
identity are validated without reading response data. The completed extension
reported BIO-layer missingness of 1,523 rows each, NVIS 1,814, soil 41, and
zero for ALUM/elevation.

The extension and score code are `scripts/goal048_predictor_extension.py` and
`scripts/goal048_response_free_scoring.py`; their focused tests are
`tests/test_goal048_predictor_extension.py` and
`tests/test_goal048_response_free_scoring.py`. Generated predictor caches,
private receipts, score ledgers, and progress files remain under the ignored
Goal 048 private root.

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

## Sequential census execution

Run the offline preflight before creating a session:

```sh
cd /Users/bwbrook/papers/dSDM
uv run --with galah-python==0.13.6 python scripts/goal048_aggregate_census.py preflight --root .
```

After review and explicit live-run authorisation, dispatch locally on the Mac
mini with one taxon at a time:

```sh
tmux new-session -d -s dsdm-goal048 'cd /Users/bwbrook/papers/dSDM && mkdir -p data/processed/dsdm/goal048-seawfb-bioregional-freeze/census && uv run --with galah-python==0.13.6 python scripts/goal048_aggregate_census.py run --root . > data/processed/dsdm/goal048-seawfb-bioregional-freeze/census/run.log 2>&1'
```

Check without opening any occurrence endpoint:

```sh
tmux has-session -t dsdm-goal048
uv run python scripts/goal048_aggregate_census.py status --root .
tail -n 40 data/processed/dsdm/goal048-seawfb-bioregional-freeze/census/run.log
```

Resume with the same `tmux new-session` command after a stopped session. The
runner queries the 96 effort-eligible members of the preserved 100-name role
ledger in frozen order; four exclusions are reported as
`not_queried_frozen_role_exclusion` with their frozen reasons. It accepts only
a contiguous checksum-valid checkpoint prefix, reuses the
validated *Acanthiza pusilla* canary when its frozen position is reached, and
never re-queries a valid completed species. A `.tmp` file, checkpoint gap,
authority drift, conservation failure, malformed/missing coordinate, timeout,
or resource ceiling stops fail-closed. `run.exit` is private and terminal;
tracked progress contains aggregate totals and checkpoint inventory hashes
only.

## Gates and response-free selection

For each target, donor richness counts distinct frozen effort-universe species
other than that target. Species-cell evidence may only pass or fail the frozen
`X=10`, `X=20`, spatial-coverage, and estimability gates. It cannot enter any
candidate role score, ranking margin, target-role decision, or predictor.

The 100-name seed ledger supplies an intentionally conservative Goal 048
screen; only its 96 effort-eligible members are transported in this census.
Any later expansion of the eligible donor universe can only relax
`X=10`/`X=20` support. Goal 049 may expand effort, auxiliary, and target
universes under the same frozen taxonomic/ecological rules before canonical
acquisition and before any holdout outcome access. It may not change,
substitute, or re-rank the Goal 048 regions. Canonical Goal 049 data reconstruct
the final exact labels and panels.

The response-free predictor and joint-selector contract is now explicit:
continuous-complete cells are ordered by `cell_id` and sampled with
`floor(j*(n-1)/(m-1))`; domain and regional caps are 100,000 and 2,000. The
PCA uses median/IQR scaling, exact-zero-IQR removal, arithmetic post-scaling
centering, deterministic full SVD without whitening, and the smallest k at
least 0.90 cumulative variance. This selection-only basis is not reused by
Goal 049 or model fitting.

All 455 unordered triples and their 1,365 member values are scored against the
evenly sampled continuous-complete simultaneous retained complement after all
three 50 km buffers. Percentiles use average ties `(rank-1)/(n-1)` before
structural or occurrence gates. Environmental novelty is p90 nearest retained
training distance in PCA space; geographic isolation is median nearest
retained distance in EPSG:3577 kilometres. Fragmentation is the complete
eligible-cell east/north rook graph using mapped-mapped edges and discordant
native-woody/non-woody edges, excluding missing NVIS. ALUM is
`H=-sum(p ln p)` normalized by `log(K_global)`. Fixed 50 km tiles use EPSG:3577
with origin `(0,0)`.

The completed selector enforced distinct, nonadjacent official regions, where geometry intersections,
touches, and overlaps are adjacency, and require every centroid pair to be at
least 250 km apart. Choose one best role permutation per unordered set by
minimum score, score sum, and ascending role tuple; rank unique sets by the
same order and stop only if the top two different sets fall below both frozen
ambiguity margins. The candidate geometry invariants are 756,836 candidate
cells, 387,450 other-domain cells, and 149 structurally valid sets. Occurrence
evidence remains pass/fail only for support and estimability gates and must not
score or rank regions.

The ambiguity rule did stop between feasible ranks 3 and 4. Barry resolved it
explicitly in favour of rank 4 after an independent audit of the response-free
role trade-off. Do not reinterpret this as a changed rank rule or an
occurrence-based tie-break. The primary panel is the 40 conservative seed
targets estimable across retained training and all three regions. `X=20`
passes for 34 and remains an evaluation-only sensitivity.

For Goal 049 and later modelling, every transform, pseudo-background rule,
fold assignment, tuning operation, early-stopping decision, threshold,
architecture choice, target subsample, and fit is learned only inside retained
training geography. The spatial-fold support gate means distinct anchored
EPSG:3577 50 km support tiles per class. Holdout label memberships were used
only for frozen pass/fail estimability gates; no model prediction or
performance outcome may be opened until the final frozen model is evaluated.
AUC is primary; BA, TSS, MCC, sensitivity, and specificity are diagnostics
with training-only OOF thresholds.

## Evidence and privacy

Tracked outputs include the packet/config, Goal048 docs, compact incident
receipt, aggregate progress, predictor/score scripts and focused tests,
`estimability_selection_receipt.json`, `design_resolution.json`, and the
boundary-only `selected_holdouts.svg`.
Raw coordinates, species-cell lists, predictor caches, and candidate-cell
tables remain ignored under
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
jq empty evidence/seawfb_bioregional_freeze/goal048/estimability_selection_receipt.json
jq empty evidence/seawfb_bioregional_freeze/goal048/design_resolution.json
uv run --with galah-python==0.13.6 pytest -q tests/test_goal048_seawfb_bioregional_freeze.py
uv run --with galah-python==0.13.6 pytest -q tests/test_goal048_predictor_extension.py tests/test_goal048_response_free_scoring.py tests/test_goal048_estimability_selection.py
uv run python -m py_compile scripts/goal048_predictor_extension.py scripts/goal048_response_free_scoring.py scripts/goal048_estimability_selection.py
uv run --with galah-python==0.13.6 python scripts/goal048_seawfb_bioregional_freeze.py validate-freezes --root .
uv run --with galah-python==0.13.6 python scripts/goal048_seawfb_bioregional_freeze.py validate --root .
uv run pytest -q
git diff --check
git status --short --branch
```

Also scan changed Goal 048 files for email/contact values, query URLs,
coordinates, provider/event IDs, occurrence rows, model outcomes, and selected
region claims inconsistent with NCP/SEH/NNC. Do not rerun live ALA access, the aggregate census, or predictor
acquisition merely to validate this delivery. Do not open private occurrence
payloads.

## Stop and report

Report the frozen regions and roles, signed ambiguity margins, hard-gate
results, primary/sensitivity panel sizes, validation, privacy, and zero outcome
counters. Do not acquire rows, construct models, predict, threshold, or edit
the manuscript. Goal 049 may expand the species universe under the frozen
rules but cannot rerank or change NCP, SEH, or NNC.
