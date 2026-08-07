# dSDM

dSDM is a provenance-bound, Python-first workflow for rebuilding and comparing
species distribution models, currently proved on the Tasmanian mammal case
study. It protects source lineage, camera privacy, response semantics,
split-fitted transformations, frozen spatial partitions, and the sealed outer
assessment.

## Supported environment

The supported contract is Python `>=3.12,<3.13` managed by
[`uv`](https://docs.astral.sh/uv/). `pyproject.toml` declares the package and
`uv.lock` is the authoritative dependency lock. From the repository root,
these are the supported setup and integrity/verification gates; listing them
does not assert that they are currently green:

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked python -m dsdm_phase1.goal029_production --root . --mode plan
```

Real calibration and production are not ordinary development commands. Run
them only under the separate authorization and validation contract in the
[Goal 029 runbook](docs/goals/029-conventional-baseline-production/Runbook.md).

## Current status

Phases 0-2 are complete. Goal 029 sealed the Phase 3 conventional baseline
engineering and provenance contract at commit `4cab971`, using exactly five
families: intercept, elastic net, random forest, histogram gradient boosting,
and shallow ANN. The real outer assessment remains unopened (`0/0` attempted
and opened), so this is not an ecological performance claim. Phase 4 dSDM
development requires a separate implementation gate.

### Current gate status

Goal 030 restored the immutable Goal 027 design-freeze artifact to its accepted
digest; the Goal 029 plan gate now validates the five-family execution
contract. The later removal of GAM remains authoritative in the Goal
029 decision, not in the earlier prospective protocol. Goal 025's two private
full-replay tests are marked `real_scope` and run only with both exact CPython
3.14.4 and explicit `DSDM_RUN_GOAL025_PRIVATE_REPLAY=1` authorization; the
manual invocation contract is in the [Goal 030 runbook](docs/goals/030-provenance-reconciliation-phase4-boundary/Runbook.md).
Tracked-only gates remain active. Production remains separately authorized,
and the real outer attempted/open counts remain `0/0`.

Canonical authority:

- [30,000-foot strategic plan](docs/strategic_plan_30000ft.md)
- [Goal 027 prospective design freeze](docs/plan/tasmanian_modelling_protocol.md)
- [Phase 1 decision register](docs/plan/phase1_decision_register.md)
- [Goal 029 decision](docs/goals/029-conventional-baseline-production/Decision.md)
- [Goal 029 runbook](docs/goals/029-conventional-baseline-production/Runbook.md)
- [`config/conventional_baseline_production.json`](config/conventional_baseline_production.json), the exact executable authority

## Data and privacy boundary

`data/`, `tas_cam/`, and `temp/` are ignored local namespaces for raw, private,
or bulky material. Do not commit camera coordinates, site or deployment
identifiers, row-level responses, private paths, predictions, or outer
assessment contents. Tracked `evidence/` contains the bounded, non-sensitive
records needed to verify the accepted workflow.

Historical R source material remains archaeological evidence in Git and local
ignored inputs; it is not a supported runtime. The active product does not use
an R package, `{targets}`, Quarto, batchtools, or the retired Phase 0 inventory
machinery.
