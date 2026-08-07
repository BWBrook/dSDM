# Runbook

Run from the repository root under the locked Python 3.12 environment. Do not
open ignored/private products.

## Safe tracked diagnosis

```sh
shasum -a 256 docs/plan/tasmanian_modelling_protocol.md
git show 4cab971^:docs/plan/tasmanian_modelling_protocol.md | shasum -a 256
git diff ce75c7f..HEAD -- \
  src/dsdm_phase1/spatial_partition.py \
  config/spatial_partition_plan.json \
  evidence/spatial_partition/2026-07-26/summary.json
```

## Source namespace boundary

```sh
uv run --locked pytest -q \
  tests/test_goal029_production.py::test_goal029_source_digest_isolates_sibling_phase4_namespace
```

The test proves that a sibling `src/dsdm/` Phase 4 module leaves the Goal 029
digest unchanged, while an added or edited `src/dsdm_phase1/` module changes it.

## Proportional final gates

Select only tests whose code has been inspected and does not traverse ignored
products:

```sh
uv run --locked pytest -q tests/test_modeling_contract.py \
  tests/test_goal029_production.py -k \
  'environment_and_raw_config or config_mutations_fail_closed or exact_five_family or active_config_rejects or runtime_sensitive_configuration or source_digest'
uv run --locked pytest -q \
  tests/test_spatial_partition.py::test_goal024_replays_once_and_goal025_recomputes_in_final_mode \
  tests/test_spatial_partition.py::test_current_private_and_evidence_footprints_and_final_full_replay
uv run --locked python -m dsdm_phase1.goal029_production --root . --mode plan
uv lock --check
git diff --check
git status --short --branch
```

Do not run the full suite without a fresh safety review. The two known Goal 025
private full-replay tests are marked `real_scope` and skip before their bodies
unless both exact CPython 3.14.4 and
`DSDM_RUN_GOAL025_PRIVATE_REPLAY=1` are present.

## Manual authorized Goal 025 replay

Only after separate authorization and from the frozen environment containing
the required private products, activate its CPython 3.14.4 interpreter, verify
the version, and opt in for only the two named tests:

```sh
test "$(python -c 'import platform; print(platform.python_version())')" = 3.14.4
DSDM_RUN_GOAL025_PRIVATE_REPLAY=1 python -m pytest -q -m real_scope \
  tests/test_spatial_partition.py::test_goal024_replays_once_and_goal025_recomputes_in_final_mode \
  tests/test_spatial_partition.py::test_current_private_and_evidence_footprints_and_final_full_replay
```

The environment variable is authorization, not a runtime override; either
missing condition keeps both tests skipped.

Expected plan invariants are five families, 280 family strata, 1,736 candidate
strata, 6,888 leaves, 34,440 OOF units, at most 952 refits, 345 source-audit
leaves, and real outer attempted/open counts `0/0`.
