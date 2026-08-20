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
opening the real outer assessment (`0/0`). Goal 033 completed the neutral
target-only architecture selection and froze `resmlp13` for the later matched
method comparison. Goal 034 then proved all six paths on a bounded real-data
sentinel and froze the three-worker Mac CPU route. Goal 035 repaired
split-fitted categorical support, confirmed `resmlp13`, and completed the full
40-case inner lifecycle for six methods, seven learning endpoints, and five
matched seeds. Goal 036 then completed the prespecified inner comparison
against all five conventional families while keeping the outer assessment
sealed.

Goals 040-043 establish the southeastern-mammal geographic-transfer substrate.
Goal 040 acquired and normalised the frozen 21-taxon feasibility cohort;
Goal 041 built one portable 24-predictor table for all 1,125,325 mainland and
Tasmania cells; Goal 042 froze 20 mainland response heads plus a separate
camera-supported Tasmania evaluation for five shared targets; and Goal 043
selected 50 km five-fold mainland blocks, rematerialised split-authorised
responses, and fitted mainland-only predictor transformations. This tranche
remains strictly pre-modelling, and Tasmania remains sealed.

### Current gate status

Goal 033 ran 960 screen and 480 fresh-shortlist logical evaluations under the
Mac CPU / three-worker route, representing 2,880 discovery-plus-replay fits.
The three-seed shortlist selected `resmlp13`, and all eight leave-one-species-
out rankings retained it. The result is an inner-CV architecture decision, not
an outer-performance claim; the real outer assessment remains unopened
(`0/0`). Goal 034 executed two deterministic repeats on each candidate route:
median wall time was 17.75 seconds on Mac CPU and 186.79 seconds on Alien CUDA.
This is engineering evidence only. Goal 035 subsequently completed 8,840
inner logical artifacts / 17,644 physical fits and retained the prediction
substrate privately. Goal 036 aligned it to 952 selected conventional OOF
checkpoints and evaluated 616 method strata. Multi-head transfer showed a
small, heterogeneous reduced-data signal, but selected conventional models
beat it in 53/56 species-endpoint strata. This is an inner method-freeze result,
not an outer-performance claim; final refits and outer assessment require
separately authorised goals.

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
- [Goal 033 decision](docs/goals/033-dsdm-architecture-selection/Decision.md)
- [Goal 033 runbook](docs/goals/033-dsdm-architecture-selection/Runbook.md)
- [`config/dsdm_architecture_selection.json`](config/dsdm_architecture_selection.json), the frozen architecture-selection authority
- [`evidence/dsdm_architecture_selection/goal033/aggregate.json`](evidence/dsdm_architecture_selection/goal033/aggregate.json), the aggregate-only selection receipt
- [Goal 034 decision](docs/goals/034-dsdm-real-six-path-sentinel/Decision.md)
- [Goal 034 runbook](docs/goals/034-dsdm-real-six-path-sentinel/Runbook.md)
- [`config/dsdm_real_six_path_sentinel.json`](config/dsdm_real_six_path_sentinel.json), the frozen real six-path sentinel authority
- [`evidence/dsdm_real_six_path_sentinel/goal034/receipt.json`](evidence/dsdm_real_six_path_sentinel/goal034/receipt.json), the aggregate-only route receipt
- [Goal 035 decision](docs/goals/035-dsdm-final-inner-lifecycle/Decision.md)
- [`config/dsdm_final_inner_lifecycle.json`](config/dsdm_final_inner_lifecycle.json), the final inner-lifecycle authority
- [`evidence/dsdm_final_inner_lifecycle/goal035/aggregate.json`](evidence/dsdm_final_inner_lifecycle/goal035/aggregate.json), the aggregate-only completion receipt
- [Goal 036 decision](docs/goals/036-dsdm-inner-evaluation/Decision.md)
- [`config/dsdm_inner_evaluation.json`](config/dsdm_inner_evaluation.json), the frozen inner-comparison authority
- [`evidence/dsdm_inner_evaluation/goal036/summary.json`](evidence/dsdm_inner_evaluation/goal036/summary.json), the aggregate-only evaluation receipt
- [Goal 042 decision](docs/goals/042-mainland-tasmania-response-substrate/Decision.md)
- [`config/goal042_transfer_response.json`](config/goal042_transfer_response.json), the response and transfer-firewall authority
- [`metadata/goal042_response_manifest.json`](metadata/goal042_response_manifest.json), the privacy-safe response receipt
- [Goal 043 decision](docs/goals/043-mainland-spatial-development-substrate/Decision.md)
- [`config/goal043_mainland_partitions.json`](config/goal043_mainland_partitions.json), the partition and transformation authority
- [`metadata/goal043_manifest.json`](metadata/goal043_manifest.json), the privacy-safe mainland development receipt

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
