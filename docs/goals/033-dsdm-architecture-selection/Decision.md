# Decision

1. Use the canonical `resmlp00`--`resmlp23` registry and deterministic CPU
   lifecycle from Goal032. The stopping fold is `(h+1)%5`; discovery uses the
   other three folds and replay uses all four non-held folds.
2. Derive fit seeds from base seed, target, held fold, endpoint, architecture,
   and purpose. Host identity and selection stage are excluded so shortlist
   seed `31031` is an exact replay of its screen counterpart.
3. Average predictions across common seeds within each held fold before AUC or
   TSS. Select one threshold from concatenated seed-averaged OOF scores using
   the existing `score >= threshold`, representable midpoint, and lower-median
   maximizer rule. Rank by species-balanced descending AUC ranks, then TSS
   ranks, then canonical architecture ID.
4. Export exactly 40 private deidentified target/fold bundles. Every assessment
   fold must contain both classes; missing classes fail closed.
5. Use the repository's locked environment for the local Phase 1 serializer,
   then use the isolated calibrated NumPy/PyTorch runtime for every model fit.
   The private bundle is the validated boundary between those environments.

LOSO ranking is diagnostic only. Poor metrics are scientific evidence, not an
execution error.

## Outcome - 2026-08-08

The frozen rule selected `resmlp13`: three constant-width residual blocks,
width 128, bottleneck 64, no dropout, and weight decay 0.001. The screen top
four were `resmlp13`, `resmlp15`, `resmlp19`, and `resmlp22`; the fresh
three-seed shortlist ranked them `resmlp13`, `resmlp22`, `resmlp15`, and
`resmlp19`.

Across species, `resmlp13` had mean AUC 0.72470 and mean TSS 0.35826. All
eight leave-one-species-out rankings retained it as the winner. Its raw AUC
margin over `resmlp22` was small and leave-one-fold-out diagnostics were not
uniform, so the warranted claim is that `resmlp13` is the predeclared-rule
winner, not that it is materially superior across all plausible selections.
The outer assessment remained unopened.
