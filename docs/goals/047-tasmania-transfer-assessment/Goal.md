# Goal 047 - Tasmania transfer assessment

## Objective

Prospectively assess whether the frozen mainland dSDM result transfers to
Tasmania for five shared mammals:

- *Dasyurus maculatus*
- *Notamacropus rufogriseus*
- *Pseudocheirus peregrinus*
- *Trichosurus vulpecula*
- *Vombatus ursinus*

The assessment compares the strict leave-target-out dSDM against frozen
neural and conventional controls. It is a transfer assessment, not a new
model search.

## Frozen design

- `bridge_control`, the four Goal 046 neural arms, and the Goal 046 epoch and
  threshold authorities were fixed before opening Tasmania.
- Mainland responses were rematerialised from the digest-bound Goal 040
  ledgers with the Goal 042 materialiser. The Goal 042 reference parquet was
  not used as model input. Replay had to equal all 20 tracked Goal 042
  mainland summaries before continuous completeness filtering.
- Strict auxiliary support subtracted focal-target presence for every
  auxiliary row, independently of the auxiliary label. Exactly 19 heads,
  equal total head weights, and natural within-head prevalence were used.
- The primary surface was the union of camera presence and
  camera-survey-supported absence, with materialised ALA presence precedence.
  The secondary surface was all Goal 042 Tasmania rows.
- ROC AUC was primary. Balanced accuracy, TSS, MCC, sensitivity, and
  specificity used frozen mainland thresholds and were secondary. Scores were
  averaged across seeds before scoring; summaries are descriptive.

## Completion and decision

Goal 047 is complete and accepted. The frozen mainland dSDM did not show a
transfer advantage for these five mammals. The primary camera-supported
surface was won by full dSDM for 0/5 species; its equal-species mean AUC was
`0.555959`, versus `0.571472` for target-only neural, `0.578745` for q-neural,
`0.583691` for selected conventional, and `0.578751` for strict-q
conventional. The full dSDM contrasts were `-0.015513` versus target-only,
`-0.017898` versus frozen trunk, and `-0.027733` versus selected conventional.
The full dSDM was positive against target-only for 3/5 species and against the
selected conventional comparator for 1/5, so the overall result is
heterogeneous rather than uniformly negative.

Threshold metrics were weak for full dSDM (mean BA `0.494065`, TSS
`-0.011871`, MCC `-0.026216`). The secondary all-row surface reinforced the
same conclusion: full dSDM mean AUC was `0.540308`, below target-only
`0.568771`, q-neural `0.573870`, and selected conventional `0.567102`.

This is a descriptive result, not an inferential claim. It closes this
five-mammal transfer question without post hoc rescue, refitting, threshold
tuning, or architecture changes. The broader species-rich pretraining
hypothesis remains open, most importantly for the south-east Australian
woodland-bird study.

## Privacy and evidence boundary

The one-shot run completed with response access of one open and 6,373 rows,
and predictor access of one open and 72,293 rows, of which 2,538 were used.
The primary surface had 4,082 target-cell rows and 4,077 complete target-cell
rows, with no missing method predictions. No cell IDs, coordinates, camera
identifiers, row payloads, or cell-level predictions were tracked. Categorical unseen values
were zero. Continuous diagnostics were descriptive only: climatic
out-of-mainland range differences occurred, with 395 missing full-surface
climate rows; incomplete rows were limited to 5 primary and 71 secondary
rows.
