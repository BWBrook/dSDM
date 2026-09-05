# dSDM

dSDM tests whether species-aware neural pretraining improves relative habitat
suitability predictions beyond strong target-only models and a scalar
community-information control. The supported workflow is Python 3.12 with
`uv.lock` defining the environment.

Start a new task with [HANDOVER.md](HANDOVER.md). The
[strategic roadmap](docs/strategic_plan_30000ft.md) explains the scientific
sequence; goal decisions and versioned configurations record the accepted
contracts.

## Scientific state

- **Tasmanian mammals:** inner comparisons found no convincing dSDM advantage.
  The original held-patch outer assessment remains deferred.
- **Mainland-to-Tasmania mammals:** the one-shot transfer assessment is complete
  and found no transferable advantage for the five shared targets. Use the
  [Goal 047 decision](docs/goals/047-tasmania-transfer-assessment/Decision.md)
  and its aggregate evidence; Goal 046 supersedes Goal 045's affected result.
- **Southeastern woodland/forest birds:** the foundation is frozen for 183
  modelling heads and 157 focal targets. The current work is the
  [Goal 051 conventional benchmark](docs/goals/051-seawfb-conventional-benchmark/Goal.md).
  [Goal 052](docs/goals/052-seawfb-dsdm-experiment/Goal.md) freezes the subsequent
  neural experiment. NCP, SEH and NNC outer outcomes remain sealed.

The active flow is frozen retained-training inputs → shared `q_linear` models
→ target endpoints → aggregate evidence → independent metric replay. Current
execution commands and canary status belong in the
[Goal 051 runbook](docs/goals/051-seawfb-conventional-benchmark/Runbook.md).
Historical mammal and acquisition modules remain where they support accepted
results, replay, or deferred assessment. Manuscript work is described in
[manuscript/README.md](manuscript/README.md).

## Development checks

Install the supported environment with `uv sync --locked`. The focused gate
for the current shared adapters and bird modelling path uses synthetic inputs:

```sh
uv run --locked pytest -q tests/test_model_adapters.py tests/test_goal049_authority_registry.py tests/test_goal050_seawfb_foundation.py tests/test_goal051_seawfb_modeling.py tests/test_goal051_seawfb_replay.py -m 'not real_scope'
```

The `real_scope` tests in these files are explicit checks of a built local
substrate, outside this portable gate. Full scientific replay uses the goal's
runbook and authorized data scope. The broader historical suite still includes
unmarked local-data and frozen-runtime assumptions; `pytest -q` across the
whole repository is not a portable default check. Do not repair old evidence
hashes merely to make a newer checkout pass.

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
