# Tasmania sensitivity execution record

The [9 October approval](TasmaniaPseudoabsenceRecoveryApproval-20261009.md)
authorises the seven-endpoint sensitivity and 200 fixed auxiliary replays.
The earlier preparation and proposal records remain historical evidence.

## Auxiliary recovery

All 200 replay-only multihead reconstructions succeeded, with no failed or
resumed fits. The three-worker, single-thread execution took 56.59 seconds.
The original initialization, shared-state, complete model-state, and auxiliary
prediction hashes matched exactly. No auxiliary discovery, pooled model or
`q` fit was performed. The recovered files remain separate from the original
Goal035 artifacts.

Independent verification checked 200 serialized-file hashes, 200 actual model
tensor hashes, 200 actual shared-state tensor hashes, 1,600 comparisons with
original records, exactly 200 accepted fit-started intents, and both aggregate
inventories. The [recovery receipt](../../evidence/tasmania_pseudoabsence/20261009/auxiliary-recovery.json)
has SHA-256 `2d86a42321dcbaf1abca9f6cb592e9c6f7bb41e5d59c8e97c683c8fe8464c4f9`.
The [independent verification record](../../evidence/tasmania_pseudoabsence/20261009/auxiliary-recovery-verification.json)
records this gate separately from target-run qualification.

## Summary conventions fixed before target fitting

The maximum-TSS threshold candidates and exact lower-median tie rule reproduce
Goal036. Average seed probabilities in float64 before choosing thresholds or
computing metrics. Use a separate sensitivity OOF threshold for every species,
endpoint and method, including the frozen conventional candidate.

For the 24 full-endpoint map pairs, convert average ranks to percentile ranks
as `100 * (midrank - 1) / (71023 - 1)`. Report sensitivity minus primary rank
displacement in percentile points; compute the 2.5th, 50th and 97.5th percentiles
using linear interpolation. This specifies the numerical scale of the approved
midrank summary. Use the approved descending probability / ascending canonical
cell-ID order to select exactly 7,103 top-decile cells. Spearman correlation is
undefined for a constant map, with the reason recorded explicitly.

Source-specific specificity always reports its true-negative numerator and
source-specific absence denominator. A zero denominator yields `NA`. All
paired performance changes and changes in model contrasts are descriptive;
no hypothesis tests, confidence intervals or survey-only evaluation view are
added.

## Completed fitting gates

The source census, all 896 retained-role class checks and auxiliary recovery
have passed. The conventional runner passed independent review and all six
fixed smoke fits. Both random-forest repetitions and both shallow-ANN
discovery/replay lifecycles reproduced their model states and predictions
exactly; both ANN repetitions selected epoch 86. Independent verification
checked the four leaf/intention/attempt inventories, six durable fit starts,
four completions, all model and prediction files, and actual ANN tensor hashes.
The [verification record](../../evidence/tasmania_pseudoabsence/20261009/conventional-smoke-verification.json)
links the original smoke and supervisor receipts.

The conventional smoke took 253.358 seconds. External process-group monitoring
measured 1,150,849,024 bytes peak RSS and 17,961,597 bytes final private storage.
A first launcher failed its runtime check before any fit because resolving the
venv executable's symlink selected system Python. That zero-fit attempt is
preserved separately; the corrected launcher uses the literal venv path.

The neural runner passed independent review and all eight fixed smoke fits.
Its clean repetitions selected epochs 6/6 for target-only and 11/11 for full
fine-tuning. Independent checks loaded all four saved models, reproduced their
predictions, reconstructed their initial states without fitting, and verified
the exact four-leaf/intent/attempt inventory and eight completed physical fits.
The [neural smoke verification](../../evidence/tasmania_pseudoabsence/20261009/neural-smoke-verification.json)
also records the resource-limit review. Maximum leaf time was 1.443035 seconds,
worker peak RSS was 370,475,008 bytes, and smoke storage was 1,057,282 bytes.

All 14 smoke fits are independently qualified. All 8,125 production fits have
completed, using three single-thread Mac neural workers and four single-thread
Linux conventional workers. The neural limits are 120 seconds per leaf, eight hours
per stage, 2 GiB RSS per worker, and 8 GiB private output. The conventional
supervisor enforces eight hours per stage, 12 GiB combined RSS and 16 GiB
private output. These ceilings include explicit headroom from the smoke
measurements and frozen maximum batch counts; they are not runtime forecasts.

The neural inventory contains 2,800 inner lifecycles (5,600 physical fits) and
560 outer fits. Their closure digests are `19d70e33f2494842a0bf627af9316c30dbfa772dcb8022327b0eceece1e7b15e`
and `f5e9c84ea670d81deb8fe4a745a9f8b314a80fbb78a10c738901c5e83e734c4c`;
combined closure is `6f834d4f72b954524805cf4d9bb73b6e2e3455f56a02c26f090c51b1e37f43c6`.
All 420 inner/outer Thylogale controls are exact. Maximum observed leaf times
were 2.169 and 1.814 seconds; peak worker RSS was 392,626,176 and 668,106,752
bytes. All models and saved predictions were revalidated before closure.

The conventional inventory contains 1,200 inner leaves (1,725 physical fits)
and 240 outer fits. Closure digests are `7866f5c2c7772e91acfcbf5a6d36b42144711f376ce79796b20422ef00b8b0b8`
and `b2c806e216bd727ddd76a3c6e162859bddc413c8351efd7353c8232d811a92a6`.
The two stages took 682.646 and 313.481 seconds; the larger combined process
RSS peak was 5,463,044,096 bytes. All four workers exited successfully in each
stage. Final artifacts were copied locally with checksum verification.
The separate conventional negative-control check matched all 95 Thylogale
inner leaves and 24,092 ordered probabilities exactly to the accepted primary
OOF archive; this control's selected conventional methods have no epoch rule.

The first neural outer launcher stopped before any intent or fit because its
historical module path had not been initialized. The preserved zero-fit log
and [startup-recovery receipt](../../evidence/tasmania_pseudoabsence/20261009/neural-outer-startup-recovery.json)
bind the correction: a small launcher invokes the existing verified staged
loader before the unchanged fitting entry point. Independent source and
multiprocessing review, plus the historical-runtime no-fit check, passed.
The approved fit inventory did not change. The initial collector then stopped
before any normalized output or response access because an outer receipt
omits a smoke-only field. The repaired reader accepts that omission for the
outer v2 schema, requires explicit `false` in inner receipts, and rejects
invalid markers and nonzero held-response read counts. Twenty-four focused
tests and eight actual leaf cases passed. The frozen fitting sources were
unchanged.

## Prediction closure, scoring and independent replay

Collection closed all 4,800 production leaves, eight normalized prediction
files, 168 sensitivity thresholds and 24 map pairs. Its receipt digest is
`428ea31c0147b315280eaee8181ce2ebb4808762e4facaf1decd5a5d01462f62`.
An independent response-free pre-opening check verified every source-leaf
binding, the original 1,672-row evaluation membership, normalized predictions,
thresholds and Thylogale controls before scoring.

At 07:14:47 UTC on 9 October, the scorer parsed the original held responses
once. Two separate integrity-hash passes account for the other two file opens;
they were not semantic parses. Independent numerical replay used the resulting
minimal private snapshot, without reopening the canonical response source.
The [assessment receipt](../../evidence/tasmania_pseudoabsence/20261009/assessment.json)
has digest `08915652195df252b062163df189f892b72ccdf1e66dab29cb4908d3b696ab56`.

The [actual independent replay](../../evidence/tasmania_pseudoabsence/20261009/independent-assessment-verification.json)
passed all 4,800 leaf checks, all 168 threshold and performance panels, all
24 map summaries, primary-result reconciliation and the exact negative
controls. Its receipt digest is
`d90a01ad2ac08ef36ff2c40bf7bce9223589011111cc2c67c124e399481ac3be`.
Continuous metric comparisons used absolute tolerance 1e-12; identities,
counts, thresholds, prediction arrays and negative controls required exact
agreement. All original primary pooled metrics reproduced exactly.

The completed inventory is **8,339 physical fits: 8,125 production, 14 smoke
and 200 auxiliary recovery**. There were no failed model fits or added fits.
The two preserved launcher failures occurred before fitting. Do not restart
fitting, collection, canonical response access or scoring for document work.

## Reporting and delivery

Public aggregates contain 168 paired-performance rows, 336 source-specificity
rows, 336 paired-contrast rows, 24 map-comparison rows and eight source-count
rows. Eight three-method map plates show primary, sensitivity and difference
surfaces on common scales; coordinate exports remain private. The independent
prose review confirmed Tables S5–S9 and all numerical Results claims against
the audited aggregates. Its three wording corrections distinguish primary
prospectivity, retained versus refitted preprocessing, and heterogeneous
species responses.

The first supplement render exposed a missing Greek rho glyph. The reporting
source now uses a mathematical rho. The initial source, generated supplement
and receipt are preserved under `report-initial/`; all numerical summary
fields remain identical. This rendering correction did not change assessment,
audit or map outputs. Final build and visual checks are recorded in
`evidence/tasmania_pseudoabsence/20261009/delivery-verification.json`.
Read [the results report](TasmaniaPseudoabsenceResults-20261009.md) for findings,
interpretive limits and artifact links.
