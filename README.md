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

Phases 0-3 are complete. Goal 029 sealed the conventional baseline using five
families: intercept, elastic net, random forest, histogram gradient boosting,
and shallow ANN. Goal 031 proved the dSDM engine on synthetic data. Goal 032
then bound its target-only path to the real eight-species outer-training
substrate and calibrated Mac CPU, deep-server CPU, and Alien CUDA without
opening the real outer assessment (`0/0`). This is engineering evidence, not an
ecological performance claim.

### Current gate status

Goal 032 recommends the Mac CPU with three workers for Goal 033. Its six-task
panel took 2.70 seconds, projecting about 10.8 minutes centrally and 3.41 hours
under the deliberately conservative 300-discovery-plus-300-replay ceiling for
the 1,440-evaluation architecture workload. Goal 033 must separately freeze
the production runtime and run the architecture screen/shortlist under a
bounded `tmux` handoff. No architecture search, six-path comparison, `q`
surface, ecological metric, or outer-assessment access occurred in Goal 032.

Canonical authority:

- [30,000-foot strategic plan](docs/strategic_plan_30000ft.md)
- [Goal 027 prospective design freeze](docs/plan/tasmanian_modelling_protocol.md)
- [Phase 1 decision register](docs/plan/phase1_decision_register.md)
- [Goal 029 decision](docs/goals/029-conventional-baseline-production/Decision.md)
- [Goal 029 runbook](docs/goals/029-conventional-baseline-production/Runbook.md)
- [`config/conventional_baseline_production.json`](config/conventional_baseline_production.json), the exact executable authority
- [Goal 032 decision](docs/goals/032-dsdm-real-compute-calibration/Decision.md)
- [Goal 032 runbook](docs/goals/032-dsdm-real-compute-calibration/Runbook.md)
- [`config/dsdm_real_compute_calibration.json`](config/dsdm_real_compute_calibration.json), the real-binding and compute-calibration authority

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
