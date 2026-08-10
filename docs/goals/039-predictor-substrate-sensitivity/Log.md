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
