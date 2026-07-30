# Decision

Goal029 implements the frozen conventional panel without changing the
Goal027 estimand or using the outer assessment. The exact executable contract
is [`config/conventional_baseline_production.json`](../../../config/conventional_baseline_production.json).

## Candidate validity and family viability

A hard failure in any required fold or seed invalidates that candidate only
within its species × endpoint × family. Partial scores and metrics from an
invalid candidate cannot enter selection or tracked evidence. `null00` is
mandatory. Every tunable family requires at least two complete valid
candidates, including its conservative anchor:

| Family | Mandatory anchor |
|---|---|
| elastic net | `enet00` |
| GAM | `gam01` |
| random forest | `rf02` |
| histogram gradient boosting | `hgb04` |
| shallow ANN | `ann01` |

There is no tolerance, iteration, architecture, or candidate-budget
relaxation. A selected candidate that fails refit, serialization, or replay
aborts its family stratum; the runner-up is not substituted.

Unknown or unclassified warnings stop. The known pyGAM bitwise-inversion
deprecation is informational. A finite, exactly replayed ANN ending at
`max_epochs_reached` is a soft warning. Failed candidates expose only blinded
failure receipts.

## Production integrity

Each five-fold candidate-seed leaf is independently content addressed and
atomically checkpointed. Identity includes the complete project-module source
closure, config, lock, runtime, host, upstream, task, split-specific subset,
and encoder provenance. Each membership artefact has exactly one
species × endpoint × split identity; the five fold-specific `E_v` records and
the outer-training refit record are never collapsed into one file.

Every selected refit receives exactly `min(32,n_unique_eligible)` canonical
response-free rows from its permitted training-feature support. The
content-addressed selected bundle binds model bytes, challenge bytes,
schema/transform/encoder state, candidate parameters, fit seed, adapter
runtime, execution context, and canonical prediction bytes. Validation
reconstructs the permitted training support and exact challenge independently.

Publication is acyclic: private and tracked core manifests are frozen first;
one pair descriptor names their two digests and the transaction ID; the final
acceptance marker names the pair-descriptor digest and is published last.
Unmarked or partial pairs are invalid.

The complete staged pair is validated before a fresh, cache-disabled source
audit. Its salt is fixed from the pre-result canonical plan, execution source
tree, configuration, and upstream bindings. It chooses one leaf per family
stratum, augments for every candidate and seed, and fills to exactly 359
leaves. Publication occurs only
after exact staged inventories, that audit, and a second staged validation
pass.
