# Goal 051 log

## 2026-09-05 - prospective authorization

- Authorized the SEAWFB five-family conventional benchmark on the Goal 050
  retained training substrate.
- Preserved the 157-target scope, 73-target 25/50/100% ladder, 84 full-only
  targets, five frozen spatial folds, X10 support rule, natural prevalence,
  and strict outer firewall.
- Froze Goal 052's separate dSDM protocol before exposing Goal 051 ecological
  scores. No model fit, score, outer outcome, or production run is recorded in
  this protocol log.

## 2026-09-05 - numerical amendment 1

- A metric-free canary exposed primary `q_linear` SAGA nonconvergence before
  any ecological score was calculated.
- Authorized a numerical-only amendment: tolerance 1e-5, primary ceiling 5,000
  iterations, then one from-scratch retry at 10,000 iterations with the same
  seed if the primary attempt warns or reaches its ceiling.
- Acceptance still requires convergence. Ceiling-stability acceptance remains
  deferred. Solver, C, l1 ratio, rows, weights, features, exclusions, and seed
  are unchanged. No ecological score or outer outcome informed this amendment.

## 2026-09-05 - convergence blocker after amendment 1

- Repeated the metric-free canary at protocol version 2 from commit `c030674`
  on `Barrys-Mac-mini.local` and `deep-server`.
- Both hosts exited 1 during the first serial canary with
  `q_linear_nonconverged_after_extended_attempt`. Neither host produced a
  canary receipt or reached the mixed-concurrency stage.
- The one prespecified numerical repair pass is exhausted. Compute-route
  selection and production remain unlaunched pending an explicit decision on
  a different q-linear convergence policy or model.
- No ecological metric was calculated and NCP, SEH, and NNC remained sealed.
