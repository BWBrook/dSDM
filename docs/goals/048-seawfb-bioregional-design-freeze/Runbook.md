# Runbook

## Read first

Read these tracked authorities before implementation or live access:

```text
README.md
docs/strategic_plan_30000ft.md
docs/scoping_review_2026-05-27.md
docs/plan/tasmanian_modelling_protocol.md
docs/goals/047-tasmania-transfer-assessment/Decision.md
docs/goals/047-tasmania-transfer-assessment/Goal.md
config/goal047_tasmania_transfer.json
config/goal040_se_mammal_feasibility.json
metadata/goal040_domain_boundary_manifest.json
docs/goals/041-portable-predictor-substrate/Decision.md
config/goal041_predictor_substrate.json
metadata/goal041_table_manifest.json
pyproject.toml
uv.lock
```

`data/input/spatial_polygons.zip`, `temp/src/`, and legacy bird products may be
inspected only as archaeological design evidence. They cannot define current
IBRA geometry, taxonomy, occurrence truth, predictor values, or performance.

## Starting-state gate

From `/Users/bwbrook/papers/dSDM`:

```sh
pwd
git status --short --branch
git rev-parse --short HEAD
git diff --check
test ! -f AGENTS.md || sed -n '1,240p' AGENTS.md
uv sync --locked
```

Stop before editing or live access if the worktree contains unexplained
changes affecting Goal 048 paths, the supported Python contract cannot be
restored without changing the lock, or a required tracked authority fails its
existing validator. Never clean or revert unrelated work.

## Required implementation surface

Implement one focused module and test file:

```text
src/dsdm_phase1/goal048_seawfb_bioregional_freeze.py
tests/test_goal048_seawfb_bioregional_freeze.py
```

The module must expose these resumable commands:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze validate-contract --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze freeze-domain --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze freeze-species --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze count-census --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze census --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze score --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze freeze --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze validate --root . --private-replay
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze status --root .
```

Each command must fail closed on missing, partial, altered, or out-of-order
state. A completed private file/receipt pair may be replayed; a one-sided pair
must not be silently repaired. `freeze-domain`, `freeze-species`, and the NVIS
native-woody ontology freeze must complete before any occurrence count.
`count-census` returns no occurrence
rows. `census` requires every resource ceiling to pass and uses any ALA contact
only from `ALA_DOWNLOAD_EMAIL`; the value must never enter a URL, manifest,
receipt, log, or test fixture.

## Domain and whole-region proof

Authenticate the official DCCEEW IBRA7.1 FeatureServer authority recorded by
Goal 040 and prove exactly 419 unique subregions mapping to 89 unique regions.
Repair invalid official geometry only with a recorded deterministic operation.
Dissolve complete subregions by official region code and verify area/feature
reconciliation before applying land and inland-water masks.

The existing 163-subregion south-east domain is a prospective starting frame,
not proof of whole-region coverage. A mainland region enters the candidate
universe only when at least 80% of its official land area overlaps that frame.
Before occurrence counts, expand the candidate/scoring domain to the complete
official geometry of every such candidate. The final 0.01-degree grid uses
centroid assignment and may exclude authoritative open water, but no study
frame may clip a candidate bioregion. Tasmania is retained as training
geography and explicitly excluded from candidacy.

## Species roles and bounded census

Freeze a tracked privacy-safe species-role ledger before counts. Distinguish:

- the broad native terrestrial, nonmarine effort universe;
- woodland/forest auxiliary species eligible as pretraining heads; and
- focal targets compatible with the intended integrated contemporary
  suitability estimand.

Exclude introduced, captive, fossil, marine, pelagic, obligate aquatic, and
unresolved species concepts explicitly. Effort donors may include regularly
recorded native terrestrial birds regardless of seasonal use. Auxiliary and
target roles may include residents and regularly recurring seasonal migrants:
their response means integrated 2001-2025 habitat use, not year-round
occupancy. Exclude strongly nomadic or irruptive taxa whose pooled occurrence
is not a stable static target. Every classification and reason must be grounded
in literature or an authoritative ecological source and frozen before counts.
An ambiguous taxon stops for scientific review; count support cannot decide it.

The count stage projects a minimal-field feasibility census and enforces the config's row,
per-taxon, disk, and free-space ceilings. The census may request only provider
identity, accepted taxon identity, coordinates, coordinate uncertainty, date,
occurrence status/basis, and fields required by inherited QA. Deduplicate by
the canonical provider identifier before species-cell collapse. The resulting
private snapshot is bounded and disposable feasibility evidence, not canonical
or bulk bird acquisition. Do not retain
abundance, observer identity, media, narrative, or broad source payloads.

For every target and split, donor richness counts distinct accepted effort-
universe species other than the target. Holdout aggregate counts may decide
whether a frozen gate passes, but region role scores cannot use species
identity, presence count, background count, prevalence, expected modelability,
or any response-predictor relation.

## Predictor and deterministic selection contract

Use the Goal 041 portable panel as the starting ontology: BIO1-BIO19,
elevation mean/SD, NVIS MVG, Soil Order, and ALUM secondary class. The bounded
census must prove common source definitions and category meanings throughout
the expanded bird domain. A material coverage or ontology failure blocks the
goal; it does not authorise region-specific substitution.

Before occurrence counts or candidate scoring, bind the checksum-verified
official NVIS 7 MVG code-label authority and track the complete mapping from
each authority code and label to `native_woody`, `non_woody`, or `missing`.
Classify from the authority definitions only. Ambiguous, unknown, and no-data
codes are `missing`; do not infer them from spatial patterns, candidate scores,
or the desired 20-80% gate. The freeze receipt must contain the authority
checksum, ordered mapping, mapping digest, and missing-code list. Any later
authority or mapping change invalidates and reruns selection.

Environmental scoring uses BIO1-BIO19 and elevation mean/SD only. Robust-scale
the deterministic systematic domain sample by median/IQR, remove only zero-IQR
columns, fit PCA retaining the smallest component set explaining at least 90%
of variance, and compute the 90th percentile nearest-retained-training distance
in PC space. This selection-only scaler/PCA is never reused by a model.

Geographic isolation is the median nearest retained-training distance after
the joint 50 km buffers. Fragmentation uses full-grid native-woody/non-woody
edge density only where both cells have mapped NVIS classes; missing cells
neither form edges nor enter the woody-fraction denominator. Land-use mosaic
uses Shannon entropy of ALUM secondary classes. The mosaic candidate must have
20-80% mapped cells in the frozen native-woody classes and still pass the
overall predictor-completeness gate.

Convert each response-free diagnostic to a candidate percentile. For each
ordered `(supported, edge, mosaic)` triple:

```text
supported = mean(1 - environmental_novelty_percentile,
                 geographic_isolation_percentile)
edge      = environmental_novelty_percentile
mosaic    = mean(fragmentation_percentile, landuse_entropy_percentile)
```

Reject triples with repeated or adjacent regions, centroid separation below
250 km, any failed hard gate, or a failed 50 km buffered training gate. Rank
the remainder by: (1) descending minimum role score; (2) descending sum of
role scores; (3) ascending concatenated official region codes. Recompute all
diagnostics against each triple's simultaneous complement; do not combine
three independent one-region rankings.

Treat the ranking as ambiguous and stop when the first and second triples
differ in region identity while both the minimum-role-score margin is below
0.01 and the summed-score margin is below 0.02. Also stop if the top role
labels contradict their frozen component diagnostics or depend on a source
artefact. Do not choose manually from a failed or ambiguous list.

## Outputs and privacy boundary

Tracked outputs are limited to:

```text
config/goal048_seawfb_bioregional_freeze.json
metadata/goal048_bioregional_freeze.json
evidence/seawfb_bioregional_freeze/goal048/candidate_summary.json
evidence/seawfb_bioregional_freeze/goal048/selected_regions.svg
docs/goals/048-seawfb-bioregional-design-freeze/
src/dsdm_phase1/goal048_seawfb_bioregional_freeze.py
tests/test_goal048_seawfb_bioregional_freeze.py
```

Private raw responses, provider IDs, coordinates, cell IDs, cell-level species
lists, candidate-cell tables, and sampled predictor values stay under ignored
`data/processed/dsdm/goal048-seawfb-bioregional-freeze/`. The tracked summary
may contain aggregate region/species gate counts, response-free scores, source
hashes, selected region codes, and private footprint digests. The map may show
domain and region boundaries only, never occurrences or effort cells.

## Validation ladder

Run, in order:

```sh
PYTHONPATH=src uv run --locked pytest -q tests/test_goal048_seawfb_bioregional_freeze.py
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze validate-contract --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal048_seawfb_bioregional_freeze validate --root . --private-replay
uv run --locked pytest -q
git diff --check
git status --short --branch
```

Tests and validators must cover official feature counts, whole-region coverage,
frame expansion, Tasmania exclusion, target-excluded donor counts, nested
`X=20` within `X=10`, hard-gate-only response use, joint-complement scoring,
the checksum-bound NVIS mapping and missing-code treatment, literature-frozen
seasonal ecology, 50 km buffers, nonadjacency/separation, exact ranking/ties,
ambiguity stop, privacy, zero model outcome counters, and deterministic replay.

## Final report, commit, and stop

The executor reports:

- starting and final branch/HEAD/status;
- materials read and exact live sources accessed;
- prospective domain expansion and complete-region proof;
- species-universe counts and exclusions;
- bounded census/resource outcome and every gate;
- ranked triple, role diagnostics, runner-up margins, and selected regions;
- common target-panel size and buffered training support;
- validation commands/results, tracked/ignored paths, limitations, and any
  blocker requiring scientific escalation;
- confirmation that no model, prediction, threshold, canonical acquisition,
  manuscript edit, commit, or push occurred.

After orchestrator review and acceptance, the executor is authorised to stage
only the accepted Goal 048 paths, commit them, and push `main`. Before that
acceptance, do not stage, commit, push, begin canonical bird acquisition, or
start modelling.
