# Numerical amendment 3 — approved recovery

Status: **approved by Barry on 8 September 2026**: "Approved for bounded
recovery proposal." Prepared after the Nectar q stage stopped; implementation
is protocol v4, before any ecological score.

## Evidence

The original 5,000/10,000-iteration policy produced 143 validated q surfaces:
50 q20, 50 q80 and 43 qfull. Seven full-auxiliary surfaces have no completed
checkpoint: block1/folds0,4; block7/folds0,2,4; block8/folds0,4. The captured
exception reached both ceilings with `ConvergenceWarning` and no numerical
warning. It lacks a surface ID and does not establish the individual error
for each missing surface. The largest successful fit needed 9,943 iterations.
No target endpoint or ecological score was generated.

The 143 models and their original receipts are preserved on both hosts, with
all return hashes verified. See `q_stage_failure.json` under
`evidence/seawfb_conventional/goal051/`.

## Approved authorization

Add one **20,000-iteration tertiary attempt**, from scratch with the same seed,
only when the unchanged primary 5,000 and extended 10,000 attempts fail.
Retain tolerance 1e-5, SAGA, C=0.1, l1_ratio=0.5, the weight transformation,
all input rows/features/exclusions, and equal head weighting. Accept only
finite fits without convergence/numerical warnings and with iterations below
the ceiling. Require all 150 q surfaces before any target fitting or scoring.

This authorizes a bounded numerical recovery, not a change in the fitted
objective, ecological comparison, or Goal052 architecture/contrast design.
The same numerical policy must be recorded consistently for Goal051 and the
prospectively frozen Goal052 q control before scores are produced.

## Execution and provenance

1. Version the numerical amendment and add focused tests for the tertiary
   branch, rejection at the ceiling, and checkpoint provenance.
2. Repeat a metric-free amendment gate on Nectar, including a previously
   unresolved full-auxiliary surface. Record each surface ID and every attempt,
   including failures, without waiting for the entire pool to drain.
3. Preserve all v3 model/receipt bytes and identities. Reuse a converged v3
   surface only through an explicit checked parent-collection receipt binding
   its spec, original identity, model/receipt hashes, parameter digest and
   accepted attempt. Its first two attempts are unchanged by the new policy.
   Bind downstream work to the amended collection; never relabel an old
   receipt with a new identity.
4. Prefer a narrow, independently reviewed import path. If honest reuse needs
   substantial compatibility machinery, rerun the q stage under one amended
   identity on Nectar instead. Preserve the original evidence either way.
5. Continue the already-approved conventional benchmark only after the gate
   passes and all 150 surfaces meet convergence requirements. No second
   permission request is needed merely because the approved gate succeeds.

If any surface still fails at 20,000, stop before ecological scoring and review
conditioning and optimizer diagnostics. Do not double ceilings again, loosen
tolerance, accept estimates at the ceiling, drop surfaces, change penalties,
or switch solvers under this authorization. Goal052 execution and outer
evaluation remain separate decisions.

## Implementation decision

Use the authorized fresh-collection fallback: rerun all 150 q surfaces under
one v4 identity in `goal051-seawfb-conventional-benchmark-v4`. The original 143
models, receipts, logs and routes remain unchanged. Independent review favored
this over a mixed-version import layer; it costs several Nectar hours but
keeps provenance and validation direct.

First fit block1/fold0/full in separate `amendment-stress` storage. Any valid
converged attempt under the amended policy passes; the original unassigned
exception does not prove that this particular surface must reach the tertiary
attempt. Unit tests exercise tertiary success and rejection. Do not promote
the stress model into the production collection. Then repeat the two serial
and 16 mixed Nectar canaries, bind the new route to v4 and the old Nectar route
as lineage, and fit all 150 fresh production surfaces. The `run` command
validates the complete q collection before scheduling any target endpoint.

Failures receive a per-surface JSON record immediately, with the specification,
identity and attempt diagnostics. A failed 20,000-iteration attempt still stops
the chain before scoring; no further numerical amendment is authorized.
