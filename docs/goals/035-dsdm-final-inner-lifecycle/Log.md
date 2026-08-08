# Log

## 2026-08-09 - final-runner RED audit

- Confirmed launch blockers before repair: target discovery included the
  stopping fold; runtime attestation omitted SciPy/sklearn/threadpool and
  BLAS identity and did not propagate into child/finalization gates; bundle,
  canary, leaf, and aggregate validation accepted incomplete inventories and
  did not bind current bundle/source content; the canary receipt lacked exact
  bundle/runtime/source bindings.

## 2026-08-09 - corrected selection and final-inner implementation

- The categorical repair was completed and independently revalidated.  The
  corrected selection receipt binds winner `resmlp13`, top-four shortlist
  `resmlp13, resmlp22, resmlp15, resmlp19`, 160 seed-31031 replay pairs,
  outer 0/0.
- A bounded real-entrypoint attempt completed all 960 screen leaves but
  failed before shortlist because of a `_canonical(...).decode()` bug.  The
  bug was repaired, the aggregate regression passed, and the stale screen
  leaves are excluded by the refreshed config identity.  No corrected result
  was accepted from that failed attempt.
- Added the lean final-inner data/runner contract: 40 atomic case leaves,
  target and auxiliary masks, separate q views, 221 logical / 441 physical
  fits per case, strict transfer/reset evidence, canary gate, resume/status,
  and aggregate finalize/validate.
- No final-inner export, production fits, outer access, commit, or push was
  performed in this implementation pass.

## 2026-08-09 - final-runner GREEN repair pass

- Repaired the confirmed discovery/stopping leakage and froze discovery as
  nonheld-minus-stopping with replay equal to all four nonheld folds for both
  target and auxiliary views.
- Bound the exact Goal034 runtime and full direct execution-source closure;
  child workers, status, finalization, validation, and canary gates now attest
  the same runtime/source bindings.
- Strictly validated 53 arrays, manifest metadata, fold partition, class
  support, nesting/audit inventories, canary/current-bundle bindings, leaf
  identities and artifacts, and aggregate content inventories.
- The final launch review closed three concrete gaps: all seven target
  endpoints now prove replay equals discovery plus stopping, every 25/50
  ladder is checked against the shared full endpoint, and canary validation
  resolves the actual identity-addressed leaf beneath each repeat root.  The
  production metadata now also emits q-augmented prediction ranges at the
  schema-prescribed top level, and runtime attestation is computed once per
  case rather than once per artifact.
- Focused plus direct regression tests: 52 passed.  `uv lock --check`,
  pycompile, configured digest checks, privacy / whitespace checks, and the
  production plan passed.
- No real export/fits, outer access, commit, or push was performed.

## 2026-08-09 - authoritative export and canary

- Added the locked `pyarrow==21.0.0` reader to the private Goal034 runtime
  without changing its attested NumPy/SciPy/scikit-learn/Torch stack.
- Exported and validated 40 unique target-by-fold bundles: 53 numeric arrays
  per case, one common source binding, exact 8-by-5 coverage, all three
  subset-ladder gates true, inventory digest
  `15454d7710b46dd252ea56f077fcf2d7ef59f63d28f7142301c67dd6cc0f0cc7`,
  and outer attempted/opened `0/0`.  The 84 MB payload remains ignored and
  private.
- The `sarcophilus_harrisii` / `fold00` canary completed two independent
  repeats.  Each retained 221 logical artifacts / 441 physical fits; model,
  state, epoch, prediction, transfer, reset, q-initial, and frozen-trunk
  evidence repeated exactly.  Predictions were finite over
  `[0.002136, 0.999895]`; q-linear converged in 507 of 5,000 permitted
  iterations with finite, moderate coefficient and logit ranges.
- The known Apple scikit-learn matmul warnings recurred, plus one read-only
  NumPy-to-Torch warning.  They remain a recorded numerical-runtime residual,
  not a canary blocker: all fitted artifacts and predictions were finite, the
  q diagnostics were bounded, and the two full repeats were byte-identical.
- Canary receipt decision: `pass`; outer attempted/opened remained `0/0`.

## 2026-08-09 - first production attempt and q stability repair

- The first full run stopped fail-closed after publishing 23 valid atomic
  leaves because `pseudocheirus_peregrinus/fold01` reached q-linear's 5,000
  iteration ceiling.  No partial leaf was published for the failed case;
  status was 23 complete / 17 missing / 0 invalid, outer `0/0`.
- A q-only diagnostic identified four warned cases.  None formally converged
  even at 10,000 iterations, while the other 36 cases converged normally.
  Across every auxiliary and target q input actually consumed downstream,
  5,000-versus-10,000 fitted probabilities were finite and differed by at
  most `4.3542e-5`.
- Replaced the impossible convergence-only gate with a bounded, transparent
  rule: fit 5,000 normally; on warning only, fit one deterministic 10,000
  comparison and accept the latter result only when the maximum downstream
  q-probability change is at most `1e-4`.  Record convergence status,
  iteration counts, stability delta, and the extra physical fit in every
  affected leaf.  Logical work remains 8,840; physical work is now an honest
  observed total in the authorised range 17,640-17,680.
- GREEN evidence: 53 focused and direct regression tests passed; the exact
  Goal034 runtime and source gates passed; the production plan reports 40
  cases, 8,840 logical artifacts, 17,640-17,680 physical fits, three workers,
  and outer `0/0`.  The formerly failing real case exercised the production
  fallback with a `2.3366e-5` downstream probability delta and a valid
  prediction-stability receipt.

## 2026-08-09 - repaired identity export and canary

- Published repair commit `16fe4cf` and regenerated all 40 private case
  bundles under config digest
  `87c3afa6fbb9a2177caafc0b2aacb0130c7f6545523839cd0fd030218795d7c2`
  and source fingerprint
  `19da36fce7f5370d91ed9ef704440c6b63c4d97fef9fdd35c4ea5eaae3043c07`.
  The inventory is the exact 8-by-5 cross-product, with 53 numeric arrays per
  case, one common source binding, and outer attempted/opened `0/0`.
- Repeated the full `sarcophilus_harrisii` / `fold00` canary twice under the
  repaired identity.  Both leaves have content digest
  `5b39637bc1ae49a51ae50175df631e84137e0830d17f138f7dca2b19fb416d60`;
  their model, state, epoch, prediction, transfer, reset, q-initial, and
  frozen-trunk evidence is byte-identical.
- Each repeat retained 221 logical artifacts / 441 physical fits.  All
  predictions were finite over `[0.002136, 0.999895]`; q-linear converged
  normally at iteration 507 with finite coefficients, logits, and
  probabilities.  The canary decision is `pass`, and outer access remains
  `0/0`.

## 2026-08-09 - final inner-lifecycle completion

- The repaired three-worker Mac CPU run exited `0`.  Exact status was 40/40
  current-identity leaves complete, zero invalid, zero missing, and outer
  attempted/opened `0/0`.
- Independent reconstruction matched all 40 target-by-fold identities to the
  40 private bundles, verified 8,840 unique artifacts, and recomputed all
  8,400 retained target prediction digests.  Predictions were float32, finite,
  bounded in `[0, 1]`, and observed over `[0.000105, 0.999990]`; all transfer,
  replay-reset, frozen-trunk, seed, and epoch relations held.
- Observed work was 17,644 physical fits.  Thirty-six q-linear cases converged
  normally in 441-2,630 iterations.  The four prespecified ceiling cases used
  one additional fit each; their worst 5,000-versus-10,000 downstream
  probability delta was `4.3542e-5`, within the `1e-4` gate.
- The known Apple scikit-learn warning triplets persisted, but there was no
  traceback, exception, partial directory, invalid leaf, or non-finite output.
  Across all q fits, coefficients were within `[-3.997, 2.732]`, logits within
  `[-1.306, 9.498]`, and probabilities within `[0.213, 0.999925]`.
- Focused and direct regression tests passed (53 tests); pycompile, lock,
  source/runtime, bundle, canary, status, finalize, and validate gates all
  passed.  The independently reconstructed tracked aggregate has SHA-256
  `4eae8cea43643a3a82e14ea546ce89fc60129e443c752599304d80fab0b5f7bf`.
