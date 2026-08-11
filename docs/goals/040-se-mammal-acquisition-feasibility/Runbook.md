# Runbook

## Count-free taxonomy and ledger/domain freeze

The first two execution stages are resumable and remain strictly count-free:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze taxonomy --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze freeze-ledger --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze validate --root .
PYTHONPATH=src uv run --locked pytest -q tests/test_goal040_contract.py
PYTHONPATH=src uv run --locked pytest -q tests/test_goal040_freeze.py
git diff --check
```

The `taxonomy` stage prepares a `counts=False` ALA name cross-check; it requires
`ALA_DOWNLOAD_EMAIL` only when that ignored raw response is absent, and never
records the email. The `freeze-ledger` stage reads the complete AMTC v5.0
species frame and uses the prepared ALA evidence only for name resolution. It
resolves query-role taxa to accepted AFD concepts and explicit reviewed
accepted descendants without making a count or occurrence request. The
exact-domain stage reconciles the archived
IBRA7.0 design polygon to a frozen 163-subregion IBRA7.1 allowlist, then writes
the ordered eligible-cell ledger under ignored raw storage. Re-running the
freeze must reproduce both the allowlist and cell-ID digests recorded in the
tracked manifest.

The frozen 21-taxon query set is a conservative, nonrepresentative feasibility
subset. Its regional evidence establishes an eligibility prior only; it does
not establish contemporary occurrence or support. Stop after `validate` unless
the count-census stage is separately authorised. Do not inspect occurrence
responses, open outer material, or read row-level/private data.

## Count-only census and resource gate

Run the separately authorised count stage and its offline replay with:

```sh
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze count-census --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze validate-count-census --root .
PYTHONPATH=src uv run --locked pytest -q tests/test_goal040_contract.py tests/test_goal040_freeze.py tests/test_goal040_count_census.py
git diff --check
```

`count-census` uses `galah.atlas_counts()` with `pageSize=0`, the inclusive
2001--2025 filters, the frozen bbox, and `disableAllQualityFilters=true`. The
public count request neither requires nor transmits the registered email; any
runtime environment value must remain process-only and must never enter a URL,
receipt, test, or manifest. The stage retains ignored, checksummed request and
count-projection pairs under `data/raw/goal040/count_census/`. A complete pair
is replayed offline; a one-sided pair fails closed rather than being repaired
silently.

The tracked receipt also preserves execution history separately from the
canonical arithmetic. The initial 45 per-branch calls included the Macropus
alias retained canonically. The later pass added 21 taxon-union calls, yielding
22 canonical estimates, 44 superseded exploratory estimates, and 66 unique
live metadata-only requests. All used `pageSize=0` and returned no occurrence
rows. Superseded receipts remain ignored and are never included in the resource
calculation.

Every accepted parent, reviewed descendant, and evidence-backed alias remains
an explicit logical branch. For each taxon, `atlas_counts()` receives the
parent and reviewed-descendant identifier list as one OR-LSID query, so indexed
rows overlapping those concepts are counted once. The Macropus alias is probed
separately: galah resolves it to the same accepted-parent LSID and its count is
therefore verified but not double-added. These remain bbox-prefilter counts,
not final exact-domain or post-QC counts. The exact
IBRA7.1/ASGS/Geofabric mask and cross-branch `recordID` deduplication remain
acquisition-time operations. If any unresolved duplicate inflation causes a
ceiling failure, stop for a resource-route decision; do not weaken or sample
the frozen query.

Acquisition must request both `recordID` and `occurrenceID`. Reject rows lacking
`recordID`; retain `occurrenceID` as optional auxiliary provenance. Across all
materialised parent, descendant, and alias downloads, retain one row per
duplicate `recordID` before spatial QA and species-cell collapse.

Apply the frozen ceiling exactly: total rows no more than 2,000,000; each taxon
no more than 500,000; projected bytes equal rows times 2,048 times 5; and at
least 30 GiB free after projection. Even when the receipt says
`pass_acquisition_authorised`, stop before occurrence acquisition unless that
next stage is separately authorised.

## Resumable full occurrence acquisition

After separate acquisition authorisation, confirm the runtime contact is
already present in the environment and run the sequential checkpointed stage:

```sh
test -n "${ALA_DOWNLOAD_EMAIL:-}"
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze acquire --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze validate-acquisition --root . --raw-replay
```

For a detached terminal, start tmux from the same environment and run the same
commands inside it:

```sh
test -n "${ALA_DOWNLOAD_EMAIL:-}"
tmux new-session -s goal040-acquire
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze acquire --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze validate-acquisition --root . --raw-replay
```

The runner processes the 21 taxon unions sequentially in ascending frozen
count. A completed CSV/receipt pair is validated and skipped on restart. A lone
named `.partial.csv` is disposable and removed before that taxon is called
again; orphaned or altered completed state fails closed. The tracked-only
validator intentionally returns `raw_replay_required`; use `--raw-replay` for
the completion gate. This stage preserves raw rows and reports identity
duplication only. It does not deduplicate, spatially QA, normalise, calculate
support, or access camera/private data.

## Staged execution after explicit review

Later implementation must expose separate, resumable commands for `taxonomy`,
`freeze-ledger`, `acquire`, `normalise`, `support`,
`predictor-pilot`, `validate`, and `finalise`. `taxonomy` must not call a count
or occurrence endpoint. `freeze-ledger` publishes the tracked taxon/query
ledger and freezes the exact IBRA7.1/domain-grid plus authoritative land/state
and open-water manifests.
The implemented `count-census` requires both frozen manifests. `acquire`
requires a complete count manifest and all resource ceilings to pass; if they
do, it downloads every frozen query without an additional discretionary
species screen.

At each boundary, record immutable query identity, package version, timestamp,
stage inputs, output digests, and aggregate status. Never record the runtime
email. Stop on concept drift, provider-ID failure, invalid/duplicate manifest,
scope drift, unexpected response state, non-nested X sets, split leakage,
region-specific predictor substitution, unproven source identity, private
evidence leakage, or any attempt to fit a model or access outer material.

Tracked evidence may contain aggregate counts by taxon decision/tier/region,
aggregate QA funnels, threshold-level counts, source-matrix definitions,
aggregate novelty/support, file digests, and the final decision. It must not
contain coordinates, grid or record IDs, donor identities, camera/site IDs,
private paths, row payloads, predictions, or outer content.
The cohort/taxon query ledger is tracked; only donor-to-cell associations and
cell-level donor identities are forbidden.

## Offline QC and species-cell normalisation

After the acquisition raw-replay gate passes, run the offline streaming stage
and its independent raw replay:

```sh
PYTHONPATH=src uv run --locked pytest -q tests/test_goal040_normalisation.py
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze normalise --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze validate-normalisation --root . --raw-replay
```

This stage makes no network call and reads every frozen CSV sequentially. It
binds the contract, taxon ledger, domain/acquisition manifests, and ignored
eligible-cell ledger; accepts only exact reviewed parent/descendant identities;
requires clean `recordID`; performs global attributed-ID deduplication; applies
the prespecified temporal, coordinate, uncertainty, and exact-evidence gates;
and assigns only half-open decimal grid tiles that join the frozen eligible-cell
ledger. Assertion columns are diagnostics only. Private row audit,
species-cell rows, and value-frequency census remain under ignored
`data/raw/goal040/normalisation/`; the transient SQLite identity store is
deleted after materialisation. The tracked manifest binds the exact three-file
private footprint with aggregate hashes, sizes, row counts, and schema digests.

## Stage 7 target-group observation-support feasibility

Run only after the normalisation raw replay has passed:

```sh
PYTHONPATH=src uv run --locked pytest -q tests/test_goal040_support.py
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze support --root .
PYTHONPATH=src uv run --locked python -m dsdm_phase1.goal040_freeze validate-support --root . --raw-replay
git diff --check
```

This offline stage binds the frozen Goal 040 domain and Stage 6 species-cell
manifest, then the Goal 019 `outputs.json` receipt and its exact camera grid
digest. It re-keys only camera rows exactly aligned to the eligible-cell ledger;
out-of-domain rows are rejected in aggregate. Camera detections can augment a
target's presence precedence and distance only; they are never donors. Donors
are distinct other taxa from Stage 6 ALA species cells only.

The ignored output directory contains exactly one sparse CSV for cells with a
positive donor count or a target/camera state. The tracked support manifest
contains no cells, coordinates, donor identities, camera identifiers, or paths:
only its footprint/digests and target-by-region aggregates. The complete zero
bin is derived from the exact eligible-cell denominator without materialising a
zero-row lattice. The >=5 km comparison is inclusive, restricted to the same
region, and uses a conservative adaptive EPSG:3577 search radius followed by
WGS84 geodesic refinement.
This is a full-data feasibility diagnostic, not a bound on future split
candidate counts.

Tracked-only validation is explicitly structural. It verifies tracked input
bindings, aggregate arithmetic, privacy declarations, receipt shape, and digest
format, but cannot authenticate an opaque private-output digest without the
ignored file. Git supplies provenance for the tracked manifest;
`validate-support --raw-replay` authenticates the private content and digest.
