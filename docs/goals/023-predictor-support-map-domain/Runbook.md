# Runbook

From the repository root:

```bash
uv run python -m dsdm_phase1.predictor_support_diagnostics
uv run python -m dsdm_phase1.predictor_support_diagnostics --validate
uv run python -m unittest discover -s tests -p 'test_predictor_support_diagnostics.py'
```

The first command refuses an existing evidence destination and writes only
`evidence/predictor_support_diagnostics/2026-07-26/`. The validator checks the
fixed plan, privacy/footprint, manifest hashes, tracked semantic arithmetic,
and then the Goal 021 full validator, Goal 022 full validator, and Goal 023
replay in that order. Failures are reported as `goal021_replay_failure`,
`upstream_validation_failure`, or `full_replay_failure`; no policy is applied here.
