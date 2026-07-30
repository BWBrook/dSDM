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
