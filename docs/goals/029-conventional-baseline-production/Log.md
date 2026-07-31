# Log

## 2026-07-31 - Final pure-Python GAM-family fallback implementation

- The full revised pyGAM gate completed 225/336 candidates but made only 40/56
  species-by-endpoint strata viable. It therefore failed the all-strata gate.
  Its outer attempted/open counts remained `0/0`; its receipts remain
  historical diagnostic evidence and are not production authority.
- Barry activated the predeclared second and final GAM-family attempt. The
  Goal029-only registry is now `psgam00`-`psgam05`: cubic bases with 4 or 6
  base knots crossed with roughness lambda 0.01, 0.1, or 1.0.
- Implemented an additive logistic model with 25 univariate training-fitted
  smooths, unchanged linear categorical indicators, no interactions, and a
  relative habitat-suitability interpretation. Exact constants are omitted;
  repeated quantile knots use a response-free uniform fallback.
- The float64 objective is mean Bernoulli negative log likelihood plus
  normalized per-block second-difference roughness and fixed `1e-4` ridge on
  all non-intercept coefficients. Each omitted spline-basis reference is
  appended as zero before the second-difference penalty is formed.
- Deterministic L-BFGS-B uses prevalence-logit initialization,
  `max_iter=1000`, `gtol=1e-6`, and `ftol=1e-12`. Completion requires solver
  success, finite coefficients/objective/gradient/training scores, unit-range
  predictions, and gradient infinity norm at most `1e-5`.
- Added a dedicated fitted wrapper with exact basis/dimension/schema binding,
  deterministic byte-identical serialization, and fail-closed replay. The
  Goal028 `gam00`-`gam04` pyGAM path remains unchanged; retired `gamr*` and
  unscoped `psgam*` payloads are rejected.
- Versioned config/protocol/registry/status/gate authority as
  `1.4`/`0.4`/v2/v2/v2. The gate workload remains 56 strata, 336 base
  candidates, 337 executions, and 2,022 fits. A stratum requires at least two
  complete candidates including `psgam02` or `psgam05`.
- Bounded diagnostics now cover iterations, solver termination, gradient
  class, basis status, and coefficient/prediction finiteness/range.
  Recognized basis, optimizer, convergence, nonfinite-state, gradient, and
  prediction failures are candidate-local. Serialization/replay integrity,
  schema/authority/transform, class support, sentinel, leakage/outer access,
  and unknown failures hard-stop.
- Focused estimator and Goal029 tests passed as `50 passed`. Shared
  Goal028/inner-CV/model-adapter regression passed as `62 passed`, with 16
  pre-existing unknown-marker warnings.
- Static planning passed with 336 family strata, 2,072 candidate strata,
  7,224 leaves, 36,120 OOF fold units, 44,520 inner fits, at most 1,008
  refits, a 362-leaf audit, and outer `0/0`.
- Fresh synthetic production and independent validation passed with 35
  leaves, six selected families, 18 selected seed refits, 12 audit leaves,
  semantic digest
  `bbfafadb374b287b5a5340f07c91b1ea3ce2caa3f51ccd0b28d8c0e8e13605f6`,
  transaction ID
  `a15d94c987b92f65f5330e6bb0fb1578d74686568851d0f60618997f11efc2b9`,
  and real outer attempted/open counts `0/0`.
- This implementation did not run the real gate, calibration, production,
  private-data processing, remote execution, or outer assessment, and did not
  commit or push. If the single real fallback gate fails, GAM is removed
  globally without another rescue attempt.

## 2026-07-31 — Typed pyGAM divergence classification repair

- The first real amended calibration at commit `1c052cb` stopped during the
  GAM feasibility gate when pyGAM raised
  `pygam.utils.OptimizationError` and the adapter correctly wrapped it as
  `ModelAdapterError("gam_fit_failed")`. The gate's exact-type allowlist did
  not yet recognize that pyGAM class, so it escalated to
  `gam_gate_exception_unclassified`.
- The gate now classifies exactly `pygam.utils.OptimizationError` as the
  bounded candidate-local `gam_fit_failed` / `optimization_error` diagnostic.
  It does not match exception text, admit arbitrary subclasses, or retain the
  PIRLS message. Unknown causes and protocol/authority failures still abort.
- Worker-level regression proves the failed fold becomes invalid while all
  later stages and a subsequent candidate continue. The receipt exposes no
  raw exception text, performance metric, prediction, label, row identifier,
  or outer payload.
- Focused new regressions: `2 passed`. Complete Goal029 test file:
  `38 passed`. `git diff --check` passed.
- The failed real attempt published no calibration authority and did not
  access the outer assessment. One clean remote GAM-gate rerun is justified;
  no grid, fitting limit, dependency, or scientific policy changed.

## 2026-07-31 — Final sentinel and late-stage resume repair

- Sentinel reproducibility now binds each stage's complete bounded
  `safe_diagnostics`, including exact private `iteration_count`. A repeat with
  otherwise identical status/digests but drifted iteration, warning, or
  finiteness evidence fails with `gam_gate_sentinel_disagreement`.
- Production startup now removes only known regular late-phase metadata that
  is safe to regenerate: the source-audit receipt and transaction
  manifests/marker metadata. The fresh source audit is rerun. Durable
  checkpoints, selections, models, memberships, encoders, and failure
  receipts are preserved.
- Transaction rollback now removes its generated core manifests, pair
  descriptor, and final-marker metadata after restoring both stages. Focused
  failure injection proves both second-rename and marker-rename rollbacks can
  be published successfully on the next attempt.
- Symlinked or non-regular late metadata, unknown inventory entries, and any
  existing final destination remain fail-closed.
- New focused regressions: `3 passed`. Complete deterministic
  Goal029/model-adapter suite: `45 passed, 1 deselected`; the deselected test
  is the separately evidenced live 6-GiB memory-gated spawn probe.
- Fresh synthetic production and independent validation passed with 35
  leaves, six selected families, 18 selected seed refits, 13 source-audit
  leaves, semantic digest
  `35a773f2f1c5c2974055c44556c757b2fe5f254eb43cfc52e4de5b3e7f4f8596`,
  transaction ID
  `440a8f9bafd6fa6839941adf51a921cf28a1ec359a3e56ec1d71c46fb910d168`,
  and real outer attempted/open counts `0/0`.
- No real calibration, production, private-data processing, outer access,
  retained-stage cleanup, commit, or push was performed.

## 2026-07-31 — Failed production diagnosis and bounded GAM recovery amendment

- The old full candidate pass assigned terminal states to all 2,016 planned
  candidate strata and stopped at family viability before selection
  publication or selected-model refits.
- Old GAM evidence was 133/280 complete and 147/280 invalid candidate strata:
  122 strict nonconvergence failures and 25 fit failures. Only 32/56 GAM
  species × endpoint strata met the old `gam01` anchor-plus-quorum rule. Every
  non-GAM family stratum remained viable.
- Real outer attempted/open counts remained `0/0`. The failed old stage is
  retained as diagnostic evidence; it was not cleaned, deleted, published, or
  promoted to authority.
- Barry authorised one bounded pyGAM recovery panel:
  `n_splines={4,6}` × `lam={10,100,1000}`, cubic splines,
  `max_iter=500`, and `tol=1e-5`. New IDs are `gamr00`–`gamr05`.
- The original `gam00`–`gam04` definitions remain byte-for-byte unchanged for
  Goal028. Goal029's revised config alone selects the additive recovery IDs.
- GAM viability no longer requires a named anchor. Every one of the 56 strata
  requires at least two complete candidates including one with `lam>=100`.
- Replaced the old 32-leaf fragility stage with a status-only feasibility
  gate over 336 candidate strata plus one independently repeated sentinel:
  337 candidate executions and exactly 2,022 fit attempts.
- A complete candidate requires all five inner fits plus full outer-training
  refit, serialization, and response-free challenge replay. The gate stores
  sanitized statuses/diagnostics and semantic hashes, never assessment
  metrics, predictions, or thresholds.
- The material review repair now predicts every actual held fold through its
  training-fitted encoder, validates output count/finiteness/`[0,1]`, and
  retains only the semantic digest. Each stage carries the exact bounded safe
  diagnostics; known fit/convergence/prediction failures remain
  candidate-local while unknown/protocol/authority failures stop.
- Complete sentinel repeats must have identical stage and challenge semantic
  digests. Identically invalid repeats can establish reproducibility but do
  not waive family viability. Replicate 1 now runs in a separately spawned
  one-worker executor with distinct private process-instance evidence.
  Unknown diagnostics stop.
- Production and publication validation now require the accepted gate and
  exact agreement with its 336 base candidate statuses. Gate-invalid
  candidates become blinded production/source-audit overlays with no OOF
  checkpoint or selection eligibility; a gate-complete candidate becoming
  production-invalid is a hard stop.
- The additive `gamr00`–`gamr05` registry is now context-scoped to Goal029.
  Goal028 and generic validation/deserialization do not accept those IDs.
- Revised full-plan arithmetic is 336 family strata, 2,072 candidate strata,
  7,224 candidate-seed leaves, 36,120 OOF fold units, 44,520 actual inner
  fits, at most 1,008 refits, and a 362-leaf source audit.
- Revised calibration retains spawn/class-support/canary/representative
  stages, using HGB rather than GAM for the concurrency canary. Total budget
  is 431 candidate executions and at most 2,597 fits.
- If this one revised pyGAM gate fails, the next separately authorised choice
  is one bounded Python-only penalized-spline logistic attempt; if that fails,
  GAM is removed globally. R fallback and repeated search are excluded.
- Focused Goal029/model-adapter tests passed as `45 passed` before the final
  bounded diagnostic-preservation adjustment. The final deterministic rerun
  was `44 passed, 1 deselected`; the sole live four-child spawn proof was
  deliberately not bypassed after two rechecks stopped at the frozen 6-GiB
  free-memory gate. This is an environmental verification limitation, not a
  relaxed acceptance condition.
- Goal028/shared compatibility tests: `66 passed`; 16 pre-existing
  unknown-marker warnings.
- Revised synthetic production and independent validation passed with 35
  leaves, six selected families, 18 selected seed refits, semantic digest
  `fb4a9844307ef44b94606305c084863b66507759ebafcc38bc74d63dcfbe5e94`,
  12 source-audit leaves,
  transaction ID
  `874fa62e167d45b834e395838f346d403228e3b1dbc846aceb967a0a4578b940`,
  and real outer attempted/open counts `0/0`.
- The static plan, Python compilation, `uv lock --check`, and
  `git diff --check` passed.
- This amendment did not run real calibration, production, private-data
  processing, outer assessment, commit, or push.

## 2026-07-30 — Goal contract and implementation start

- Barry authorised Goal029 after accepting the Goal028 foundation.
- Frozen scope: eight species, seven endpoints, six conventional families,
  all 36 registered candidates, five inner folds, and family-specific seeds.
- Exact arithmetic: 336 family strata, 2,016 candidate strata, 7,168
  candidate-seed leaves, 35,840 OOF-producing fold units, 44,240 actual inner
  estimator fits after ANN discovery/replay, and at most 1,008 refits.
- Corrected conservative anchors are `enet00`, `gam01`, `rf02`, `hgb04`, and
  `ann01`; the Goal028 representative IDs were coverage choices, not anchors.
- Real outer use, residual MLP, community/dSDM machinery, interpretation,
  mapping, sensitivity work, and birds remain outside this goal.
- Implementation is proceeding through code, tests, and synthetic gates
  before any real calibration or production command.

## 2026-07-30 — Implementation tranche ready for review

- Added the exact production plan/configuration, multi-seed inner-CV support,
  content-addressed leaf checkpoints and selected bundles, family-level
  failure/quorum reduction, calibration authority, resumable production
  scheduler, artefact recomputation, fresh source audit, and atomic paired
  publication.
- The production lifecycle is deliberately one ordered command: validate the
  live same-host calibration authority, stage/resume the exact run, validate
  all staged artefacts and selections, complete a fresh cache-disabled
  359-leaf audit, validate again, then publish and write the final marker.
- Focused Goal029 tests: `12 passed`.
- Shared Goal028/inner-CV regressions: `50 passed`; 16 existing unknown-marker
  warnings.
- Fresh synthetic lifecycle and independent validation passed with 35 leaves,
  six selected families, 18 selected seed refits, source audit, and outer
  attempted/open counts `0/0`.
- Static plan passed at 7,168 leaves, 2,016 candidate strata, 336 family
  strata, 44,240 actual inner fits, at most 1,008 refits, and 359 audit leaves.
- Full suite: `341 passed`, `2 failed`, `20 warnings`, `254 subtests passed`.
  Both failures are unrelated Goal025 full-replay drift in the existing
  tracked `evidence/spatial_partition/2026-07-26/summary.json`.
- `uv lock --check`, compilation, and `git diff --check` passed.
- No real calibration, production fit, outer opening/scoring, commit, or push
  was performed in this implementation tranche.

## 2026-07-30 — Material review repair pass

- Reworked invalid-candidate recovery so reused or newly written checkpoints
  remain intact until a blinded invalid state is durably recorded. Cleanup is
  then idempotent and records its own completion.
- Reworked paired-publication rollback to restore complete private and tracked
  trees to their stage paths after second-rename or final-marker failure.
  Restoration failure preserves authoritative destinations and fails loudly.
- Made selected refit validation externally authoritative: it binds the exact
  selected task, candidate parameters, derived fit seed, live adapter runtime,
  execution context, reconstructed training schema/order, exact
  `min(32,n_unique_eligible)` challenge, model envelope, and prediction bytes.
- Added exact staged and published file inventories. Extra checkpoint,
  selection, selected-bundle, tracked, or transaction files now fail closed.
- Strengthened the production source audit to exactly 359 immutable leaves,
  with exact valid-result/invalid-failure reconciliation, state/plan/worker
  bindings, and coherent-tamper rejection.
- Froze every runtime-sensitive configuration value by canonical config
  digest and safe-bound all configured write destinations beneath the repo.
- Focused Goal029 evidence: all 16 tests passed, including failure injection,
  path escape, degenerate challenge, extra-file, config-mutation, and coherent
  source-audit mutation cases.
- Shared regressions: all eight inner-CV tests and all 42 Goal028 tests passed.
- Fresh synthetic production and independent validation passed with 35 leaves,
  six families, 18 selected refits, semantic digest
  `0e6d2c4533e58dcf5a09f0d76707ad4ff0e2b1dec8265e4963a84413f133541d`,
  and outer attempted/open counts `0/0`.
- Static plan passed at 7,168 leaves, 2,016 candidate strata, 336 family
  strata, 44,240 actual inner fits, at most 1,008 refits, and exactly 359
  source-audit leaves.
- Full suite JUnit evidence: 601 cases, 599 passing, zero errors/skips, and the
  same two unrelated Goal025 `full_replay_evidence_drift:summary.json`
  failures.
- No real calibration, production fitting, outer access, commit, or push was
  performed during this repair pass.

## 2026-07-31 — Portable fail-closed swap telemetry repair

- Canonical calibration on Linux at commit `eb0c085` stopped before its first
  leaf because the Darwin-only `sysctl -n vm.swapusage` probe failed with
  `cannot stat /proc/sys/vm/swapusage`. The host reported healthy memory and
  zero swap use; no calibration receipt or production artefact was created.
  Calibration leaves completed: zero. Real outer attempted/open counts:
  `0/0`.
- Swap telemetry is now platform-bounded and fail-closed. Linux strictly
  requires exactly one coherent `SwapTotal` and `SwapFree` pair in `kB` from
  `/proc/meminfo`; Darwin strictly parses one coherent `vm.swapusage` record.
  Unsupported systems and telemetry read, command, or parse failures raise
  `Goal029Error("swap_telemetry_unavailable")`.
- The existing no-swap-growth and minimum-6-GiB calibration acceptance gates,
  configuration, worker policy, and scientific scope are unchanged.
- Mocked swap telemetry tests: `12 passed`, covering valid and zero-swap
  Linux, missing/duplicate/unit/negative/incoherent/read failures, valid
  Darwin, malformed/command/incoherent Darwin failures, and an unsupported
  platform.
- Focused Goal029 tests: `28 passed`.
- Shared Goal028/inner-CV regressions: `50 passed`; 16 existing unknown-marker
  warnings.
- Static plan passed at 7,168 leaves, 2,016 candidate strata, 336 family
  strata, 44,240 actual inner fits, at most 1,008 refits, exactly 359
  production source-audit leaves, and outer `0/0`.
- Fresh synthetic production and independent validation passed with 35 leaves,
  six families, 18 selected refits, semantic digest
  `d2848e7831dd0207b47fa55e2ede3a93d7dcf93f7e61bf651358f60465fd2122`,
  and outer attempted/open counts `0/0`.
- No real calibration, production fitting, private-data access, commit, or
  push was performed during this portability repair.

## 2026-07-31 — Concurrency gate diagnosis and bounded repair

- The authorised workers-1 calibration trial completed its then-unioned
  62-leaf panel in `827.757` seconds: 47 complete and 15 invalid candidates,
  peak child RSS about 1.144 GB, healthy free memory, no swap growth, and real
  outer attempted/open counts `0/0`.
- The workers-2 trial was stopped without a receipt after process inspection
  showed each child owning 160 native threads and consuming roughly 31 and 23
  CPU cores. No workers-2 calibration authority, production fit, source
  audit, or outer access was created.
- Root cause: estimator-level `n_jobs=1` and ANN-local PyTorch settings did
  not cap native OpenMP/BLAS pools, while the calibration design repeated the
  32-leaf GAM fragility panel inside every worker trial.
- Added a frozen one-thread execution contract. The module force-assigns five
  environment caps before numerical imports, retains a process-global
  `threadpoolctl` limiter, sets and verifies PyTorch intra/inter-op threads,
  rejects every reported BLAS/OpenMP pool above one, and records normalized
  evidence without library paths.
- Thread policy and effective-evidence digests now bind the execution context,
  audit salt, leaf identity/checkpoints, failure receipts, calibration
  authority, production workers, selected refits, and fresh source audits.
- Complete and invalid production candidate states persist the normalized
  worker thread evidence, not only its digest. Resume and publication
  validation recompute the digest, pool limits, and declared-policy binding;
  a focused arbitrary-digest tamper test now covers this gate.
- Replaced the repeated 62-leaf design with distinct stages: four zero-fit
  spawned children; two valid `gam01` canary leaves at workers 1/2; the frozen
  30 representative leaves at workers 1/2/4; and the 32 fragility leaves once
  at the selected workers. The canary stops above a `1.25` workers-2/workers-1
  wall ratio. Selection chooses the smallest safe count within `1.10` of the
  fastest representative trial.
- Revised calibration totals are 126 leaf executions and at most 735
  estimator fits, versus 186 leaves and 1,035 fits in the unioned design.
  The 56-stratum class-support scan remains once per calibration.
- `threadpoolctl==3.6.0` remains in the existing locked scikit-learn closure
  and is exact-version checked at runtime. `pyproject.toml` and `uv.lock`
  remain byte-identical to preserve Goal028's frozen dependency provenance.
- Focused Goal029 tests: `31 passed`, including the live four-child zero-fit
  spawn proof, oversubscribed-pool rejection, exact canary/selection
  boundaries, calibration-authority reconstruction, checkpoint tampering,
  production worker evidence, and source-audit evidence.
- Shared Goal028/inner-CV regressions: `50 passed`; 16 existing unknown-marker
  warnings.
- Static planning passed at 7,168 leaves, 2,016 candidate strata, 336 family
  strata, 44,240 estimator fits, at most 1,008 refits, 359 source-audit leaves,
  and outer `0/0`.
- Fresh synthetic production and independent validation passed with 35 leaves,
  six families, 18 selected refits, semantic digest
  `d772edfb23ef67bd5afd68b34e2dea925fe4ea4e417b1acfde7a58af51419c0a`,
  fresh spawned source audit, and outer attempted/open counts `0/0`.
- This was an execution-contract repair, not a scientific-policy change. No
  real calibration rerun, private-data access, production fitting, outer
  opening/scoring, commit, or push was performed.

## 2026-07-31 - Five-family final closure authorised

- The revised pyGAM gate completed 225/336 candidates and made 40/56 strata
  viable. It was rejected under its prospective all-strata requirement.
- The final pure-Python penalised-spline gate executed all 336 base candidates
  plus one sentinel repeat: 337 executions and 2,022 fits. It returned 281
  complete and 55 invalid candidates, with 52/56 strata viable. The four
  failures were low-data strata; the sentinel passed and real outer
  attempted/open counts remained `0/0`.
- Because the final gate failed the prospective all-56 rule, Barry authorised
  the declared stop. GAM is removed globally from active Goal029. Successful
  strata are not retained selectively and there is no third rescue attempt.
- MARS remains a future ideas-ledger possibility only; it is not substituted
  into Goal029.
- The final active families are exactly `intercept`, `elastic_net`,
  `random_forest`, `hist_gradient_boosting`, and `shallow_ann`.
- Frozen production arithmetic is 56 species-by-endpoint strata, 280 family
  strata, 1,736 candidate strata, 6,888 candidate-seed leaves, 34,440 OOF
  fold units, 42,840 estimator fits, at most 952 selected refits, and 345
  source-audit leaves.
- Calibration retains four zero-fit spawn children. Two canary leaves at
  workers 1 and 2 produce four executions and 20 fits; 28 representative
  leaves at workers 1, 2, and 4 produce 84 executions and 525 fits. The total
  is 88 estimator-bearing executions and at most 545 fits, with no GAM gate.
- The synthetic contract becomes 33 leaves, five selected families, and 17
  selected refits.
- Active authority advances to config schema `1.5`, protocol `0.5`, and
  calibration master/index version `4`. Obsolete GAM gate schema, stages, and
  fields are removed.
- Goal028 pyGAM and dormant P-spline code/tests remain historical and
  compatibility evidence only, never active Goal029 authority.
- This documentation amendment ran no real calibration, production,
  private-data processing, remote execution, outer assessment, commit, or
  push.

## 2026-07-31 - Five-family contract implemented and verified

- Active Goal029 configuration and runtime authority now contain exactly
  `intercept`, `elastic_net`, `random_forest`, `hist_gradient_boosting`, and
  `shallow_ann`. The P-spline registry, GAM viability policy, feasibility
  stage, gate receipt, production overlay, selection exception, source-audit
  exception, and publication reconciliation have been removed.
- Config schema `1.5`, protocol `0.5`, and calibration master/index version
  `4` are live. The v4 calibration ID binds only the execution context, stage
  order, canary and 28 representative leaves, and worker ladders. Its exact
  private inventory excludes historical gate receipts.
- Focused Goal029 tests passed: `37 passed`. They cover exact five-family
  arithmetic, 28-leaf calibration coverage, 345-leaf production audit, the
  33-leaf synthetic plan and 12-leaf synthetic audit, v4 authority
  round-trip, and rejection of v3 receipts, stale gate files, extra files,
  old overlay origins, reintroduced GAM, and P-spline registry authority.
- Shared Goal028, inner-CV, model-adapter, and Goal029 regressions passed:
  `99 passed`; 16 pre-existing unknown-marker warnings remain. Goal028 pyGAM
  replay and the dormant P-spline numerical evidence therefore remain intact.
- The first fresh synthetic attempt exposed one material integration defect:
  its intentionally partial validation config has no model-registry section,
  while the new canonical-only guard initially required one. The guard was
  narrowed to reject any explicit noncanonical registry while accepting the
  partial synthetic validation contract.
- Before the independent-review repair, fresh synthetic production and
  independent validation both passed with 33 candidate-seed leaves, five
  selected families, 17 selected refits, 12 source-audit leaves, semantic digest
  `cdd92da67003b7973e2ea0abc77031a7f61dcc7e0b70f44f1bf0b8e912b75a00`,
  transaction ID
  `7588e4742e9fbf644ab7e37868e6ed3960deb7606d53a29c3c592477a2751ae0`,
  and real outer attempted/open counts `0/0`.
- Independent review found one material fail-closed gap: the tracked
  calibration directory accepted sibling files beside `receipt.json`.
  Exact-inventory validation now rejects legacy v3 receipts, historical GAM
  gate artefacts, and arbitrary extra siblings. Post-repair focused tests
  passed `36` with one live zero-fit spawn test deselected because available
  host memory was below the frozen 6 GiB gate; that exact test had passed in
  the earlier `37/37` focused and `99/99` shared runs, and the gate was not
  weakened or mocked.
- Final post-repair synthetic production and independent validation both
  passed with 33 candidate-seed leaves, five selected families, 17 selected
  refits, 11 source-audit leaves, semantic digest
  `1bc566b91574938a02dc20ba103e63176f77f599115425052c38e634991bd0c9`,
  transaction ID
  `66d4689e5880ef36ef01476f7efcfd9a02e7adbbd0abd6838990f50714b994b7`,
  and real outer attempted/open counts `0/0`.
- Final static planning passed at 280 family strata, 1,736 candidate strata,
  6,888 candidate-seed leaves, 34,440 OOF units, 42,840 estimator fits, at
  most 952 selected refits, exactly 345 production source-audit leaves, and
  outer `0/0`. Python compilation, `uv lock --check`, and `git diff --check`
  also passed.
- No real calibration, real production, private-data processing, remote
  execution, outer assessment, commit, or push was performed.

## 2026-07-31 - Phase-aware post-publication inventory repair

- The full remote production at producing commit `f85e459` brought all 1,736
  candidate-stratum executions to terminal states: 1,731 completed and five
  elastic-net strata produced bounded nonconvergence receipts, with no partial
  performance exposed. It completed every selected refit and fresh
  source-audit leaf, then atomically published a coherent `status=pass`
  transaction with real outer attempted/open counts `0/0`. Its only failure
  was the subsequent reuse of the staged inventory allowlist against the
  finalized directories.
- Supplied remote evidence confirmed the exact publication delta. Private had
  only `core_manifest.json` as an extra, SHA-256
  `836384b71fa03797e3fe92052aed2255b737d59a347aaa8614830a28d0851ab6`.
  Tracked evidence had only `core_manifest.json`, `PAIR.json`, and
  `FINALIZED.json`, with respective SHA-256 values
  `07ac142aad2ce63edf69a6b9e1889b280db0b99b201e376ad62166975cc9237f`,
  `cff5f1baad216522dd024750c81595f2f72c543f9adce8e7e8c0e3cd0e369d9c`,
  and `152f7cd0f3da5443b793b10ad5f7fe303491828c1a3ae3a9bf47cfa1daf0f84b`.
  Neither inventory had a missing file, and transaction IDs, manifests, and
  self-digests were coherent.
- Production inventory validation now requires an explicit `staged` or
  `finalized` phase. Staged validation retains the original exact inventory;
  finalized validation is entered only after transaction validation succeeds
  and adds exactly the four transaction metadata files above. Unknown files,
  missing metadata, temporary finalization markers, and symlinks remain hard
  stops.
- Test-first regressions passed `15/15` for the new phase boundary. The whole
  focused Goal029 suite then passed `51` with only the unchanged live 6 GiB
  spawn proof deselected. Shared Goal028, inner-CV, and adapter checks passed
  `62/62`; 16 existing unknown-marker warnings remain.
- Fresh synthetic production and independent validation both passed with 33
  candidate-seed leaves, five families, 17 selected refits, nine source-audit
  leaves, semantic digest
  `c63494f3642a44dd1bcd1dfa4bfb0432a0271d295d45e09dc0e6cf870c22b91b`,
  transaction ID
  `86dcb0e428715006d8d0b81cd841c1f1b0ce6571bc0f8a3b1a1e5c135d224e81`,
  and outer `0/0`. Static planning retained the frozen production arithmetic
  and 345 source-audit leaves; compilation and lock validation passed.
- External read-only validation is justified without recomputation only by
  keeping the producing root immutable at `f85e459`, running the repaired
  validator from a separately recorded checkout, and confirming the exact
  four-file finalized delta. Updating the producing root first would change
  its bound source-tree digest; any additional mismatch requires a stop.
- This repair performed no model, data, config, calibration, production,
  private-data, remote, or outer-vault work, and no commit or push.
