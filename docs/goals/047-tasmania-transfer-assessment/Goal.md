# Goal 047 - Tasmania transfer assessment

## Objective

Prospectively assess transfer of the frozen Goal 046 mainland models to
Tasmania for five targets.  This package defines the pre-opening contract;
production refits and the Tasmania opening have not run.

## Frozen design

- `bridge_control`, the four Goal 046 neural arms, and `seed00` through
  `seed04` are fixed.
- Mainland responses are rematerialised from the digest-bound Goal 040
  mainland eligible-cell and species-cell ledgers with the Goal 042
  materialiser. The Goal 042 reference parquet is never a model input. The
  replay must equal the tracked Goal 042 aggregate counts before continuous
  completeness is applied with the Goal 041 predictors.
- Strict auxiliary support subtracts focal-target presence for every
  auxiliary row, independently of the auxiliary label. All auxiliary
  presences and only adjusted-X3 backgrounds are retained across exactly 19
  heads with equal total head weights and natural within-head prevalence.
- Each target/seed/lifecycle uses the lower median of its five matching Goal
  046 fold-selected epochs.  No Tasmania labels are used for stopping or
  threshold selection.
- The primary surface is the union of camera presence and
  camera-survey-supported absence, with already-materialised ALA presence
  precedence.  The secondary surface is all Goal 042 Tasmania rows.
- Primary scoring is ROC AUC.  TSS, balanced accuracy, MCC, sensitivity, and
  specificity are secondary.  Seeds are averaged before scoring.
- The four neural arms use five seeds. Conventional models use their actual
  Goal 044 selected seed labels: the `hgb04` Pseudocheirus models use only
  `seed00`; the random-forest panels use all five seeds.

## Privacy and stopping boundary

Cell IDs, coordinates, camera identifiers, predictions, and row payloads are
private and ignored. Only aggregate evidence may be tracked. Full mainland
models require a committed, content-identical freeze and a clean worktree.
The opening additionally requires a committed, content-identical receipt and
an exclusive durable marker written before either Tasmania input is opened.

No production refit, opening receipt, Tasmania evaluation, mapping, or
manuscript claim was run or authorised in this implementation turn.
