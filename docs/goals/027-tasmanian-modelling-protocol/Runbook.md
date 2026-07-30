# Runbook

Goal027 is documentation-only. Run from the dSDM repository root:

```sh
test -f docs/plan/tasmanian_modelling_protocol.md
test -f docs/goals/027-tasmanian-modelling-protocol/Goal.md
test -f docs/goals/027-tasmanian-modelling-protocol/Plan.md
test -f docs/goals/027-tasmanian-modelling-protocol/Decision.md
test -f docs/goals/027-tasmanian-modelling-protocol/Log.md
test -f docs/goals/027-tasmanian-modelling-protocol/Runbook.md
rg -n "version 0\.1|2026-07-30|D_struct|multi-head|q_linear|q_deep|25%|50%|100%|no model" \
  docs/plan/tasmanian_modelling_protocol.md docs/goals/027-tasmanian-modelling-protocol docs/strategic_plan_30000ft.md
git diff --check
git status --short
```

Inspect relative links and the roadmap's Phase 1/2/3/4 and current-position
wording. Do not run project scripts, tests, builds, data reads, model fitting,
prediction, validation, or remote-compute commands. Do not touch `data/`,
`outputs/`, `tas_cam/`, `temp/`, `old_code/`, source code, or configuration.
