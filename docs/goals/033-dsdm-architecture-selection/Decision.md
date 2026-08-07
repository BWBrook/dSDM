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
