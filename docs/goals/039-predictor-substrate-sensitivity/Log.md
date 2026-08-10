# Log

## 2026-08-10 - Goal 039 prespecification

- Barry approved the predictor-substrate sensitivity experiment after Goal038
  retained `resmlp13` and rejected architecture rescue.
- Frozen scope is inner-only: five fold-specific response-blind masks, full-28
  replay, reduced-panel canary, screen, and conditional confirmation.
- The complete mask algorithm, estimands, endpoints, seeds, gates, model
  context, provenance rules, and non-goals are recorded in `Decision.md`.
- No correlation inspection, data-payload read, model fit, outer access,
  generated result, commit, or push was performed while freezing this contract.

## 2026-08-10 - pre-screen canary correction

- Bounded canary diagnosis preserved exact candidate, seed, fold, row, and
  label identities for all four conventional families. Historical-control
  maximum absolute score differences were `1.11e-15` for elastic net,
  `0.00556825` for random forest, `0` for histogram gradient boosting, and
  `1.49e-7` for shallow ANN.
- The random-forest difference reflects cross-platform refitting drift between
  the historical Linux/x86 run and the current Darwin/arm64 runtime. Widening
  the historical equality tolerance after observing the result would not make
  a valid reduced-minus-full comparison.
- Before any screen execution, the conventional estimand was therefore
  corrected to contemporaneous paired full/reduced fits using the same locked
  runtime, selected candidate, rows, folds, and seeds. Goal036 remains the
  immutable selection, row/label, and provenance authority, with historical
  score differences retained as transparent canary diagnostics only.
- Full and reduced conventional leaves now have separate resumable checkpoint
  identities. Confirmation reuses both members of the screen
  `fraction100/full` pair. The neural gates, response-blind masks, endpoints,
  seeds, and advancement rules are unchanged; outer access remains `0/0`.

## 2026-08-10 - screen decision and closeout

- The corrected canary passed from published source commit `48d1842`. Neural
  full-control replay and reduced repeats were exact; all four conventional
  families repeated both current full and reduced fits exactly with finite,
  bounded predictions. Candidate, seed, fold, row, and label provenance was
  intact, and outer access was `0/0`.
- The screen completed all `120/120` neural cases and all `384/384`
  conventional full/reduced pairs with zero invalid or unexpected leaves.
- `Delta U` (reduced minus full multihead performance) had aggregate AUC
  `-0.0010864` and TSS `-0.0079709`, with positive effects for `2/3`
  endpoints, `4/8` species, and `1/3` seeds. It failed the species, seed, and
  non-negative-TSS gates.
- `Delta I` (change in multihead versus target-only lift) had aggregate AUC
  `+0.0036139` and TSS `-0.0011455`, with positive effects for `2/3`
  endpoints, `6/8` species, and `1/3` seeds. It failed the seed and
  non-negative-TSS gates.
- Neither primary lane was screen-eligible. Confirmation was therefore
  forbidden and was not run. The final decision is `retain_full28`.
- The contemporaneous conventional context also gave no broad denoising
  signal: `11/12` family-by-endpoint mean AUC effects were negative. The only
  positive mean was shallow ANN at `fraction25/ladder00` (`+0.0005994`), too
  small and isolated to alter interpretation; conventional context had no
  decision authority.
- Final aggregate validation succeeded with receipt digest
  `f5c4e0edf5c4fc5f6b0116509dcfabccdc1eea6ee0425427e62a7a083e2cdbb0`.
  Executed screen inventories are complete, unexecuted confirmation inventories
  remain intentionally absent, and outer access is `0/0` throughout.
