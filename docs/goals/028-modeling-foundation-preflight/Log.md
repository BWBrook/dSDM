# Log

## 2026-07-30 — Design checkpoint

- Goal028 packet and executor-ready TDD plan drafted.
- Scientific authority remains the accepted Goal027 protocol; no fitted model,
  prediction, score, threshold, metric, map, or ecological conclusion was
  produced.
- Engineering choices frozen: Python 3.12 under `uv`; conventional
  NumPy/SciPy/scikit-learn/pyGAM stack; native PyTorch only for neural models;
  PyArrow for private Parquet; canonical Mac mini CPU preflight.
- Leakage boundary frozen: every data-dependent operation is inner-training
  only, the real `OuterVault` is sealed, and Goal028 creates no valid unlock.
- Deterministic target subset, seed, candidate, OOF selection, threshold,
  evidence, replay, preflight, and hard-stop contracts recorded.
- Real preflight restricted to two species and explicitly interpreted as an
  engineering exercise over included-row positive fractions, not prevalence.
- Implementation, dependency resolution, tests, and artefact generation remain
  to be performed by an authorised executor. No commit or push is authorised
  for that executor.

## 2026-07-30 — Material design repair

- Added the neural OOF stopping firewall: stopping fold `(v+1) mod 5`,
  same-seed reinitialisation, exact-epoch complete CV-training replay, and
  lower-median fold-epoch full refit with no assessment labels in fitting.
- Replaced the candidate TSS tie-break with equal-fold TSS at one
  candidate-specific concatenated-OOF threshold.
- Fixed threshold semantics to `score >= threshold` and the sorted
  lower-median maximising threshold, with explicit maximum-TSS recheck.
- Replaced public combined-response construction with one private ingestion
  factory and required both attempted and successful real outer-open counts to
  remain zero throughout provenance, aggregation, replay, and acceptance.
- Separated conventional convergence hard failures from neural hard failures;
  a valid finite `max_epochs_reached` checkpoint is warning-only.
- Changed review cadence to task implementer self-reviews, three coherent
  independent package gates, and one final whole-diff review, with at most one
  focused repair per gate unless a material defect persists.

## 2026-07-30 — Tasks 1–3 executor receipt

- TDD red checkpoint: `uv run pytest -q tests/test_modeling_contract.py -k
  "environment or raw_config"` failed on the intentionally absent Goal028
  configuration before implementation.
- Environment/config and contract implementation completed in the assigned
  files. Python is pinned to 3.12.13; the resolved direct modelling stack is
  NumPy 2.5.1, SciPy 1.16.3, scikit-learn 1.9.0, pyGAM 0.10.1, PyArrow
  21.0.0, and PyTorch 2.13.0 (with pytest 9.1.1 in the dev group).
- Green checkpoint: `uv run pytest -q tests/test_modeling_contract.py
  tests/test_target_subsets.py` — 7 passed. `uv lock --check`, focused
  `py_compile`, and `git diff --check` also passed.
- Proven invariants: fail-closed real `OuterVault` (attempt count increments,
  successful count remains zero), allow-listed outer-training feature keys,
  canonical row validation and seed derivation, deterministic SHA-prioritised
  nested 25/50/100 ladders, and one canonical full endpoint alias.
- Implementer self-review found no additional material defect in owned files;
  no commit or push was made. Later tasks must not open or score real outer
  rows.

## 2026-07-30 — Tasks 1–3 audit repair receipt

- Corrected the machine-readable contract path to
  `config/modeling_foundation_preflight.json` and removed the temporary
  `goal028_modeling_plan.json` name.
- Added complete required binding-role registry, frozen candidate parameter
  registry, private/aggregate schema and atomic publication metadata, and
  strict ordered-section/dependency/digest validation. Private digests are
  checked against tracked authority declarations without opening private
  bytes.
- Hardened raw-row validation before casting (exact non-bool binary integers,
  nonempty string keys, recognized source, finite unit weights), and separated
  an explicit synthetic factory from the real private factory. The real path
  rejects combined rows, requires `outer_role` and valid `cv_fold`, verifies
  private product digests, exposes only outer-training feature keys, and never
  aliases an empty held set to training rows.
- Endpoint validation now recomputes SHA-ordered prefixes and full-alias
  metadata, rejecting tampered digests or order.
- Audit probes reproduced: candidate drift rejected; private `not-a-sha`
  rejected; `pa` values 256, 257, and 1.9 rejected; held rows were not
  reachable through the provider substrate; tampered endpoints rejected;
  missing partition/fold and unknown fold rejected; empty held vault produced
  attempted/open counts 1/0.
- Focused Tasks 1–3 tests: 11 passed. `uv lock --check`, config validation,
  py_compile, and `git diff --check` passed. No commit or push.

## 2026-07-30 — Foundation final repair extension

- Replaced the injectable feature payload path with the authoritative private
  factory: Goal025 `response_partitioned.csv` and Goal024 canonical predictor
  map are digest-checked internally, partitioned immediately by strict
  `outer_role`, and joined only for outer-training keys. Goal026 tracked fit
  parameters and feature contract drive lazy `z=(x-mean)/population_sd`
  materialisation and categorical raw-code encoding; held feature rows are
  never retained.
- Added the methods-audit neural defaults (batching/order/dtypes/AdamW,
  deterministic initialisation and stopping semantics, seed roles) and GAM
  spline/penalty defaults to the machine-readable contract and validator.
- File-backed temporary-fixture test covers digest tamper, join mismatch,
  role/fold rejection, held-key reachability, transform arithmetic, and vault
  sealing. Focused Tasks 1–3 suite now passes 12 tests. A live local factory
  smoke over the frozen authorities produced 11,039 outer-training rows and
  exactly 11,039 provider keys with vault attempted/open counts 0/0.

## 2026-07-30 — Final Tasks 1–3 identity repair

- Anchored the complete canonical configuration to an independent
  `EXPECTED_CONFIG_SHA256` constant and required private bindings to resolve
  through tracked authority declarations. Coordinated candidate, registry,
  binding, neural, artifact, compute, response, feature, and GAM mutations
  now fail before semantic use.
- Extended `FeatureBatch` with feature names/kinds, continuous count, and
  schema digest. Encoder state records ordered categorical/continuous names,
  levels, transform/family, encoded schema, and canonical digest; transform
  digests bind the exact transform record and ordered feature schema.
- Tightened exact source/microcluster/key types, canonical fold IDs without
  `cv_` normalisation, global response-key uniqueness, and role/fold handling.
- Constructed one canonical `fraction100/full` endpoint object and assigned
  the same object identity to all three ladder aliases; metadata, ordered
  prefixes, and digests are recomputed during validation.
- Focused Tasks 1–3 suite: 12 passed. Config validation, live factory
  transform smoke, `uv lock --check`, py_compile, and `git diff --check` passed;
  live factory remained 11,039 outer/provider keys with vault counts 0/0.

## 2026-07-30 — Tasks 4–6 adapter/inner-CV implementation

- Added the common feature-bound adapter protocol, exact 39-row candidate
  registry validation, conventional sklearn/pyGAM adapters, native PyTorch
  shallow and residual architectures, deterministic stopping/exact-epoch
  replay, and whole-file JSON-envelope serialization with tamper checks.
- Added leakage-safe inner OOF assembly with independently validated fold
  endpoints, fixed `cv_foldNN` transforms/encoders, neural stopping-fold
  isolation, RowKey coverage checks, equal-fold AUC/TSS, nextafter boundary
  thresholding with lower-median maximizer selection, candidate tie-breaks,
  provenance-safe outer refit, and semantic replay.
- Focused adapter/inner-CV tests: 5 passed; no commit or push performed.

## 2026-07-30 — Tasks 4–6 focused repair gate

- Hardened model envelopes with externally trusted whole-file SHA validation,
  strict canonical base64, immutable candidate/schema/seed/runtime identity,
  payload identity matching, concrete estimator/state checks, and explicit
  external-digest semantic replay.
- Added neural initial-state digests and five-fold stopping/replay receipts;
  enforced exact `cv_foldNN` task transforms, canonical endpoint derivation,
  full-refit task/candidate/fraction/ladder/seed binding, and receipt epochs.
- Selection now permits residual engineering probes but recomputes every fold
  AUC/TSS, concatenated threshold, and equal-fold aggregate before tie-breaking.
  Threshold input shape/types, adjacent-float boundaries, GAM convergence logs,
  conventional fit/predict errors, and neural epoch types are fail-closed.
- Expanded focused Tasks 4–6 suite: 13 passed. Tasks 1–3 regression suite:
  13 passed. `py_compile` and `git diff --check` passed; no commit or push.
- Named probes covered coordinated schema tamper, candidate swap, external
  digest/self-hash replay rejection, wrong refit transform/fraction/candidate,
  GAM exhaustion, raw RF exception, bool/float epochs, actual patience
  iteration reporting, fabricated aggregate metrics, residual selection, and
  adjacent-float threshold handling.

## 2026-07-30 — Complete-response scope gate repair

- `ingest_private_foundation` now validates the digest-verified complete
  response product before any outer/held partitioning. The bounded real scope
  requires the exact two configured species and exact integer
  `included_row_counts` structure, counts complete rows (including upstream
  species outside the gate), and applies the same strict binary `pa`
  normalization as `RowSet`; count drift and malformed scope fail with
  `ModelingContractError`.
- The public boundary is unchanged: `SplitBroker` and `FeatureProvider`
  expose outer-training keys only, while the real `OuterVault` remains sealed
  with attempted/open counters at `0/0` on successful ingestion. Synthetic
  ingestion is unchanged.
- Added compact fixture tests for exact pass, included/positive count drift,
  missing/extra species or count keys, count type rejection, upstream extra
  species preservation, and outer-training/vault boundaries.
- Verification: `uv run pytest -q tests/test_modeling_contract.py` — 16
  passed; Tasks 1–6 regression (`tests/test_modeling_contract.py
  tests/test_target_subsets.py tests/test_inner_cv.py tests/test_model_adapters.py
  tests/test_goal028_preflight.py`) — 42 passed with 7 existing unknown-mark
  warnings; `python3 -m py_compile src/dsdm_phase1/modeling_contract.py` and
  `git diff --check` passed. No commit or push.

## 2026-07-30 — Canonical full-endpoint provenance repair

- Constrained external strata/tasks to `fraction25/50 × ladder00–02` or the
  canonical `fraction100/full`; `ladder00` remains an internal lookup alias
  only. OOF and outer-refit endpoint checks now canonicalise and verify the
  full endpoint identity and reject alias combinations.
- Updated five-fold OOF/neural/refit fixtures and added explicit alias-rejection
  probes. Focused Tasks 1–6 suite: 27 passed; `py_compile` and `git diff --check`
  passed.

## 2026-07-30 — Final endpoint/comparability integrity repair

- Canonical endpoint checks now compare the complete `SubsetEndpoint` identity,
  including `full_alias_id`; fraction100/full requires `full_alias_id="full"`,
  while fraction25/50 ladder endpoints require no alias.
- Candidate selection now requires identical ordered fold IDs, RowKeys, binary
  labels, and ordered seeds across candidates after each candidate's internal
  metric replay. Added OOF/refit endpoint-tamper and key/label comparability
  probes. Focused Tasks 1–6 suite: 28 passed; `py_compile` and `git diff --check`
  passed.

## 2026-07-30 — Tasks 7–8 harness receipt

- Added deterministic synthetic orchestration/publication/validation and
  fail-closed real scope scheduling in `goal028_preflight.py`, with explicit
  private Parquet provenance, privacy-safe aggregates, trusted model bytes,
  semantic tamper checks, and paired rollback.
- Synthetic gate exercises all seven adapter families through inner OOF,
  exact refit, and serialization; the bounded real scheduler is 46 strata
  (23 per species) and never opens the outer vault. Focused harness tests:
  6 passed; `py_compile` and `git diff --check` passed. No real run, commit,
  or push performed.

## 2026-07-30 — Tasks 7–8 integrity reconstruction

- Replaced the split synthetic-oracle/real-fit harness with one explicit-plan
  engine consuming an already-authorised broker, feature provider, and vault.
  Both modes now use the actual `run_candidate_oof`, `select_candidate`,
  `refit_outer_training`, adapter serialization, external trusted SHA-256,
  and `replay_predictions` paths; assessment batches remain prediction-only.
- The frozen plans are exact: synthetic executes 26 real adapter strata
  (per species, `null00` at all seven endpoints plus the six non-null families
  at `fraction100/full`); real scheduling contains 46 `seed00` OOF strata
  (23 per species), with elastic-net and residual candidates selected within
  family by the Tasks 4–6 AUC/TSS/canonical rule. Neural `seed01` is a separate
  deterministic/replay diagnostic and never enters candidate selection.
- The complete private footprint is `tasks.parquet`, `oof.parquet`,
  `subsets.parquet`, `run.json`, and selected `models/<task_id>.model`; the
  exact tracked footprint is the six aggregate JSON files. Explicit PyArrow
  schemas now carry the full frozen task provenance plus validated
  fold-epoch and selection fields. OOF rows preserve five-fold predictions;
  replay rows bind each selected serialized model to a reconstructed,
  permitted outer-training refit batch.
- Staged validation now recomputes task/pair/config identities, split-specific
  subsets, source/class counts, encoder/transform/schema state, OOF coverage
  and metrics, within-family selection, lower-median neural epochs,
  initial-state receipts, aggregate reconciliation, file/model hashes, and
  prediction replay before either destination rename. Model bytes are never
  unpickled before the manifest/task external digest is verified.
- Synthetic fake-vault scoring requires explicit synthetic authorisation and
  is recorded separately at attempted/open `1/1`; real attempted/open counts
  remain `0/0` in task, run, aggregate, validation, and CLI receipts. The real
  harness no longer compares outer-training broker counts with frozen complete
  counts: complete counts are factory-validated authority, while observed
  outer-training source/class counts are recorded separately.
- Focused gate: 39 passed, covering coordinated config/task/subset/encoder/
  transform/schema/OOF/model/aggregate/manifest/publication/fake-vault
  tampering, privacy keys and absolute paths, both rollback branches,
  existing/symlink destination refusal, deterministic semantic rerun, exact
  46-stratum scope, pre-fit species/candidate/seed/endpoint/CPU/process/budget
  rejection, per-task wall/RSS overruns, factory-only real ingestion, and
  zero real vault access.
- Tasks 1–8 focused regression: 75 passed. Canonical CLI synthetic plus full
  validation passed with semantic digest
  `e1a38156f45bc3b48ebdbc88c1cd9663e2dbd550bdd60fcf8b893167ba1cbf6c`:
  26 tasks, 26 selected models, 780 OOF rows, and 558 model replay rows.
  The generated synthetic pair was removed after recording this receipt.
- Full repository test run: 323 passed, 1 skipped, 254 subtests passed, and
  two Goal025 spatial-partition full-replay tests failed on pre-existing
  `summary.json` evidence drift. No owned Goal028 or Tasks 1–6 test failed.
  Because Goal028 real ingestion depends on Goal025 provenance, resolve or
  explicitly reconcile that upstream drift before authorising Task 9.
- No real private run, outer prediction/score, remote compute, commit, or push
  was performed. A bounded independent high-consequence audit of this common
  engine and the Goal025 drift is justified before the real preflight.

## 2026-07-30 — Coordinated-substitution audit repair

- Independent audit showed that the prior full validator accepted both a
  coherently replaced OOF/metric bundle and a coherently substituted selected
  model with matching replay/task/aggregate/manifest receipts. Internal
  coherence was therefore not independent validation.
- Full validation now freshly executes the exact canonical 26-stratum
  synthetic or 46-stratum real plan from the frozen authoritative inputs
  through the same actual OOF/selection/refit engine, then compares a
  deterministic semantic bundle before either staged destination is renamed.
  The bundle binds task and subset identities, OOF rows/scores/metrics,
  selection and thresholds, neural receipts, model identity, final refit
  predictions, fake-vault/seed01 receipts, and the semantic digest; only
  runtime/RSS/platform noise and nondeterministic PyTorch pickle bytes are
  excluded. Real replay re-enters only the canonical private factory and never
  opens or scores the outer vault.
- Both coordinated substitutions now pass the intentionally coherence-only
  check and fail the independent full replay with
  `independent_semantic_replay_mismatch`. Focused harness tests: 41 passed;
  Tasks 1–8 focused regression: 77 passed. Canonical synthetic generation and
  separate full validation passed with semantic digest
  `e1a38156f45bc3b48ebdbc88c1cd9663e2dbd550bdd60fcf8b893167ba1cbf6c`,
  authoritative bundle digest
  `b57f36c428ca490374a5fe6c8c1d02c14b897b902ad83265a2309bcd93826f95`,
  and real outer attempted/open counts `0/0`. Generated synthetic outputs were
  removed; no real run, commit, or push was performed.

## 2026-07-30 — Goal025 runtime-provenance clarification

- Goal025 strict replay was independently rerun under its frozen CPython
  3.14.4 runtime and returned `tracked_valid=true`, `private_valid=true`, and
  `full_replay=true`; all ten private artefacts were byte-identical.
- Under Goal028's CPython 3.12.13 environment, the sole replay difference is
  `geometry.versions.python`. This is runtime provenance drift, not
  scientific, response, partition, geometry, or private-data drift.

## 2026-07-30 — Task 9 GAM representative repair

- The first real Task 9 attempt was fail-closed before publication on
  `pseudocheirus_peregrinus/fraction25/ladder00/gam02/seed00`, inner `fold01`.
  The 8-spline, `lam=1` GAM exhausted all 500 iterations with final difference
  `0.406` versus tolerance `1e-5`; coefficients were finite, but convergence
  and overflow warnings were present. No real outer row was opened or scored,
  and the attempted/open vault receipt remained `0/0`.
- Independent real-fold diagnostics found the already-registered `gam01`
  (6 splines, `lam=1`) converged with finite state and final difference below
  tolerance on all 20 GAM inner-fold checks across both species and the two
  representative endpoints. `gam03` remained nonconvergent. The orchestrator
  therefore selected `gam01` only for the real-preflight representative;
  `gam02` remains unchanged in the full registry and synthetic plumbing.
- Bounded implementation changed only the real-preflight ID in config,
  contract validation, and the exact real task plan. GAM convergence now
  accepts a trace reaching exactly `max_iter` only when its final finite
  difference is strictly below `tol`; missing/nonfinite traces or coefficients,
  and convergence/overflow/divide warnings, remain hard failures. The failed
  `gam02` case therefore still fails closed.
- TDD red/green coverage includes the exact 46-task real-plan assertion for
  `gam01`, explicit real-scope rejection when the representative drifts back
  to `gam02`, the exhausted `gam02` nonconvergence case, and a synthetic GAM
  that converges exactly on iteration 500. The scientific estimand, predictors,
  folds, thresholds, transforms, seeds, outer boundary, candidate registry,
  production policy, leakage rules, and publication boundary are unchanged.
- The private retry gate is limited to the failed fold twice, four real GAM
  strata across five OOF fits, and four outer-training refit/serialization/
  replay paths. It must remain within frozen wall/RSS limits, report no
  convergence/overflow/divide warnings (apart from the known unrelated pyGAM
  boolean-inversion deprecation warning), and leave vault attempted/open at
  `0/0`; the full 46-stratum real preflight remains a separate executor gate.

## 2026-07-30 — Private GAM retry-gate receipt

- The exact failed `pseudocheirus_peregrinus/fraction25/ladder00/gam01/seed00`
  inner `fold01` was fitted twice through the canonical adapter. Both receipts
  converged in 9 iterations with identical difference-trace digest
  `4ac9d0c8fb61915263f44a1326fe1d22f0fd204e48ed0dad431af48999b1c641` and
  prediction digest
  `59fd9014bf189fa5ab92d620eac17a43b69414b2f4cd65bbae3b25fbcd21588a`.
  The only warning was the known unrelated pyGAM boolean-inversion
  `DeprecationWarning`; no convergence, overflow, or divide warning occurred.
- All four real GAM strata completed five inner OOF fits each with finite
  scores and no bad warnings. Aggregate prediction digests were: sarco
  fraction25 `b220433020b6bde8c6e1a4cdc8444cabf8b42ee7cfa86bd54e579285aa0496dd`,
  sarco full `59a7726279a8072ffba4fa1b5b3e650786361d2596bbbad239d2525e73e3addd`,
  pseudo fraction25 `01be4ddbb84a6f1c85c4c79239a0868fc357b420e829f82e784050d94ddbb8a3`,
  and pseudo full `bf63310564b0ad1f91bd7767debdb8588483a288161bb917c4f774eca59edde1`.
- Four outer-training refit, serialization, and trusted replay paths passed
  with iterations `7, 6, 7, 6` (species/endpoints in canonical plan order).
  Prediction digests were `925570056f049da9fa60177672386a6d7fb08a00bb2f2fe81ce64080c15664fd`,
  `61b4d60f920cc101182dabf0d553f0c50253c18914140ddc81523b5ab60b9fd`,
  `351c85d1576209d4eb3529d598383a9a69cdeb8a77eed06cc6186af41360c7b0`, and
  `ae1ce78c98b54660d8b2141e73f04f3f6c2fd0b86025a6b8577a5750b2079dd1`.
- The gate used temporary model files only and left the real outer-vault
  attempted/open counters at `0/0`. It did not run the 46-stratum real
  preflight, publish outputs, compute/report performance metrics, or expose
  row keys. A Task 9 retry with the bounded `gam01` representative is
  justified, subject to the separate executor decision for the full run.

## 2026-07-30 — Task 9 successful real-preflight receipt

- Commands passed: fresh synthetic generation; independent full synthetic
  validation; bounded real preflight; and independent full real-preflight
  validation. The real run published a complete private/tracked pair with
  `46` candidate strata and `38` selected models.
- Coverage was exactly two configured species and seven model families. The
  private footprint contains `94,185` OOF rows, `44,025` replay rows,
  `271,326` subset rows, and `38` selected model files. Tracked validation,
  manifest reconciliation, privacy walk, trusted model-hash replay, and
  semantic replay all passed.
- All conventional selected tasks converged; the eight non-selected
  candidate strata were complete OOF strata. Neural stopping receipts were
  `patience_stop` throughout, with no `max_epochs_reached` status. Four known
  pyGAM boolean-inversion deprecation warnings were recorded; no convergence,
  overflow, divide, nonfinite, or partial-evidence warnings occurred.
- Per-task runtime ranged from `0.205` to `12.781` seconds and peak RSS from
  `675,856,384` to `1,147,961,344` bytes; aggregate runtime/memory budgets
  passed. Semantic digest:
  `d6af1fdfe48bea791358457479118ee961ac1998bd3f034f7ae4ab22fb35dd01`;
  authoritative bundle digest:
  `1d5c9eccc87b6afb33842a0d60bab85b64f9df325f0ef67fc247484069516fc0`.
- Real outer attempted/open counters were `0/0` everywhere required. No
  outer scoring, predictions, maps, q surfaces, or scientific product was
  produced.

## 2026-07-30 — Final independent audit acceptance

- **ACCEPT** for deterministic, leakage-safe engineering preflight only.
  Coverage was `46/38`, with `47` manifest entries exact. Privacy `0/0`, byte
  `0/0`, semantic `0/0`, trusted replay `0/0`, and outer `0/0` checks all
  passed as required.
- The full suite passed `329` tests, with `2` known Goal025
  runtime-provenance failures, `254` subtests, and `20` warnings. The frozen
  CPython 3.14 replay passed; compilation, lock, and diff checks passed.
- This is not approval of performance, estimands, outer scoring, q surfaces,
  maps, or science. Residual hardening is final state/commit binding and the
  sequential-rename power-loss caveat; both remain future work.
