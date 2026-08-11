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

## Staged execution after explicit review

Later implementation must expose separate, resumable commands for `taxonomy`,
`freeze-ledger`, `count-census`, `acquire`, `normalise`, `support`,
`predictor-pilot`, `validate`, and `finalise`. `taxonomy` must not call a count
or occurrence endpoint. `freeze-ledger` publishes the tracked taxon/query
ledger and freezes the exact IBRA7.1/domain-grid plus authoritative land/state
and open-water manifests.
`count-census` requires both frozen manifests. `acquire`
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
