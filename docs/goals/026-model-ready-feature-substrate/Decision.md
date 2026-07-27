# Decision

Goal026 passed numerical/semantic review (`goal026-v1`, reviewer
`dSDM_orchestrator`, 2026-07-27) as the final pre-modelling data-preparation
gate. Continuous predictors use `z=(x-mean)/population_sd`,
`ddof=0`, fitted separately per split from training map cells. Missing,
nonfinite, or non-positive-SD inputs fail hard. Nominal categorical codes and
their deterministic full vocabularies are retained; model-family encoding is
deferred. Both split-training-map and target-species training-response
marginal-envelope lenses are recorded without changing membership. The API
returns identity plus separate 25-column continuous and 3-column nominal
categorical blocks, never a model matrix. The next
action is supervisor Phase 1 review; no SDM work is authorised by this gate.
