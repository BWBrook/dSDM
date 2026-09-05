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

## 2026-09-05 - numerical amendment 2

- User-approved a numerical-only correction before any ecological scores.
- The q solver now divides collapsed sample weights by `k = max(weight)` and
  uses `solver_C = canonical_C * k` (`canonical_C = 0.1`), preserving the exact
  penalized likelihood up to the common factor `1/k`. Rows, equal-total head
  weighting, features, exclusions, and seed are unchanged.
- Convergence is classified from `ConvergenceWarning`; unrelated warnings are
  recorded, while explicit numerical warnings and iteration ceilings remain
  rejection conditions. Deprecated q `penalty` and `n_jobs` arguments are
  removed. Receipts bind `k`, canonical and solver `C`, representation, and
  warning types. No ecological score or outer outcome informed this amendment.
- Focused verification passed: `31 passed`; the weighted penalized objective
  equivalence and practical probability equivalence tests passed; `bash -n`
  and `git diff --check` passed. Protocol-v2 failures did not retain per-attempt
  iteration or warning-type details. Inspection now confirms that deprecated
  sklearn arguments could emit warnings falsely captured by `bool(caught)`, so
  those failures alone do not prove exhausted-iteration nonconvergence. Prior
  v1 history remains intact.

## 2026-09-05 - detached corrected canary handoff

- Correction `c14bc47` is committed and pushed cleanly on Mac and deep-server;
  the independent focused rerun remains `31 passed`.
- The corrected protocol-v3 canary-batch was launched at approximately 16:27
  AEST under the existing approval: Mac session `dsdm-goal051-canary-mac` in
  `/Users/bwbrook/papers/dSDM`, with `canary/batch-v3-mac.log` and
  `canary/batch-v3-mac.exit`; deep-server session `dsdm-goal051-canary` in
  `/data/codex/repos/dSDM`, with `canary/batch-v3.log` and
  `canary/batch-v3.exit`.
- At approximately 16:32 AEST both CPU processes were active. The first
  receipt had not completed; no failure, outer access, or ecological metric
  was observed. Prior logs were preserved. The main benchmark remains
  unlaunched.
- User cadence is detached long compute followed by wake-up. On resume, finish
  valid two-host summaries, run route selection, then launch the full
  production benchmark under the existing approval. No new permission is
  required.
