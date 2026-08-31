# Decision

## Status

Goal 047 is complete and accepted. The implementation/fix sequence was
`f46659d` then `37a5ec3`; the committed opening receipt is `20897ec`.

## Scientific decision

For the five shared mammals, the strict leave-target-out mainland dSDM did not
demonstrate a transferable advantage on the Tasmania holdout. The primary
camera-supported assessment is the decision surface. Full dSDM mean ROC AUC
was `0.555959`, below frozen trunk (`0.573856`), target-only neural
(`0.571472`), q-neural (`0.578745`), selected conventional (`0.583691`), and
strict-q conventional (`0.578751`). Its mean contrasts were `-0.015513` versus
target-only, `-0.017898` versus frozen trunk, and `-0.027733` versus selected
conventional. It was best for 0/5 species, although it exceeded target-only
for 3/5 species and selected conventional for 1/5, so the species-level
evidence is heterogeneous.

Threshold metrics were also poor for full dSDM: BA `0.494065`, TSS
`-0.011871`, and MCC `-0.026216`. The secondary all-row surface reinforced
the same conclusion, with full dSDM mean AUC `0.540308` versus target-only
`0.568771`, q-neural `0.573870`, and selected conventional `0.567102`.

This is a descriptive five-species result, not a population-level or
inferential claim. We close the question without post hoc refitting,
threshold tuning, architecture rescue, or Tasmania-informed changes. The
The broader species-rich pretraining hypothesis remains open, most importantly
for the south-east Australian woodland-bird study.

## Execution and validation

The first refit attempt failed safely before fitting or Tasmania access when
replay validation encountered a four-versus-seven-key summary-shape mismatch.
After the repair, all 20 canonical Goal 042 mainland summaries reproduced
exactly. Production exited `0` with five q surfaces, 25 pretraining fits, and
142 models. The opening receipt was sealed and committed; validation and an
independent final audit were GO.

The primary surface contained 4,082 target-cell rows and 4,077 complete
target-cell rows, with no missing method predictions. The one-shot access
counters were one response open for 6,373 rows and one predictor open for
72,293 rows, with 2,538
predictor rows used. Categorical unseen values were zero. Climatic
out-of-mainland range diagnostics were descriptive only; 395 full-surface
climate rows were missing, and only 5 primary and 71 secondary rows were
evaluated as incomplete.

## Privacy boundary

No cell-level outputs, coordinates, camera identifiers, or row payloads were
tracked. The durable evidence is the aggregate
`evidence/tasmania_transfer/goal047/summary.json`; private input and model
payloads remain outside the tracked result.
