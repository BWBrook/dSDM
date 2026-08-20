# Log

## 2026-08-20 - implementation and acceptance

- Evaluated all 192 prescribed block assignments: 100 km had 0 feasible,
  50 km had 12, and 25 km had 60. Selected 50 km / seed 0 under the frozen
  largest-feasible rule.
- Materialised 1,053,032 mainland cell assignments and 3,775,385 split-
  authorised response rows for 20 heads, five folds, and both fold roles.
- Fitted five fold-specific transformations and one reserved full-mainland
  transform from mainland map cells only.
- Froze complete-case continuous handling after the bounded preflight showed
  that an exact 1% per-fold rule was unstable for sparse classes. The hard
  production gate is 2% over each whole mainland target-class; the observed
  maximum was 1.46%.
- Focused review repaired categorical application so source missingness remains
  `__MISSING__` even when absent from a training fold, rather than being mapped
  to `__UNSEEN__`. It also tightened largest-feasible-scale validation.
- Focused Goal 042/043 tests passed `15/15`. Raw receipts validated, and an
  independent Parquet join found zero duplicate keys, rule violations,
  train/validation role leakage, or unbound response cells.
- No model, architecture, hyperparameter, prediction, performance, Tasmania
  evaluation, map, or manuscript work was performed.
