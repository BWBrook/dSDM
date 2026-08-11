# Runbook

## Prespecification-only commands

The present review authorises only the offline contract test:

```sh
PYTHONPATH=src uv run --locked pytest -q tests/test_goal040_contract.py
git diff --check
```

Do not set or print `ALA_DOWNLOAD_EMAIL` during prespecification. Do not call an
ALA endpoint, inspect occurrence responses, open outer material, or read
row-level/private data.

## Staged execution after explicit review

Implementation must expose separate, resumable commands for `taxonomy`,
`freeze-ledger`, `count-census`, `acquire`, `normalise`, `support`,
`predictor-pilot`, `validate`, and `finalise`. `taxonomy` must not call a count
or occurrence endpoint. `freeze-ledger` publishes the tracked taxon/query
ledger and freezes the authoritative land/state boundary manifest.
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
