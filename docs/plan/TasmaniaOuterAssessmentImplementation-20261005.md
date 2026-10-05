# Original Tasmania held-patch outer assessment implementation — 5 October 2026

## Scientific target and limits

This controller implements the approved one-shot assessment of the frozen
Goal037 panel. The estimand is species-specific discrimination and
thresholded classification of the accepted **relative habitat-suitability
index** over Goal024 `D_struct`. The prediction target is the resolved
species-by-cell rows assigned before modelling to `mc08`, `mc20`, `mc35`,
`mc40`, or `mc49`. The scope of inference is held-patch interpolation within
Tasmania, conditional on the 2001–2025 response construction. It is not an
occupancy, abundance, true-prevalence, causal-transfer, or independent-region
estimand.

The frozen outer inventory is 1,672 labelled species-by-cell rows over 606
distinct geographic cells. These counts are different because several focal
species can contribute one row at the same cell. The controller gates both
quantities and the eight species-specific row counts before prediction
closure; it does not mistake the 606 spatial cells for 606 response rows.

The observation process combines opportunistic occurrence evidence, camera
evidence, survey-supported absences, and constructed pseudoabsences. A zero
therefore does not have one observation mechanism, and imperfect detection,
effort, source coverage, and pseudoabsence construction can affect apparent
performance. The atomic modelling row is one resolved species-by-canonical
0.01-degree cell; record multiplicity is not a weight. Cells and patches share
spatial and ecological structure across species, so rows, species, and the
five touching unbuffered patches are not independent replicates.

Goal025 froze patch membership before model fitting, but the design is not a
random sample of independent Tasmanian regions. Patch feasibility used class
support, patches touch training cells, and spatial autocorrelation and
non-stationarity can make apparent sample size larger than effective sample
size. The assessment is consequently descriptive. It reports no row
bootstrap, p-value, or claim of general transfer.

## Frozen comparison

The panel contains eight species, seven target-data endpoints, five common
seeds, six neural paths, and five accepted conventional families. It preserves
all 11 methods rather than selecting on the outer response. Five seed scores
are averaged and written to immutable prediction files before response access.
Goal036 inner-OOF thresholds and per-stratum conventional selections are then
applied unchanged.

ROC AUC and TSS are co-primary. Average precision, MCC, sensitivity,
specificity, and confusion counts are supplementary. Results are produced for
the pooled held cells and each of the five patches. Under the explicit
assessment rule, an empty or one-class patch retains class and confusion
counts but sets every performance metric to `NA`; it is never pooled,
resampled, or assigned a synthetic class to fill the gap.

The three prespecified contrasts are full multi-head fine-tuning minus the
matched target-only residual MLP, minus target-plus-`q_deep`, and minus the
inner-selected conventional family. The concise cross-case headline uses the
pooled `fraction100/full` endpoint; all reduced-data endpoints remain in the
assessment receipt. Positive differences are evidence about this frozen panel
and response construction, not identified causal effects of pretraining.

The protocol also specifies a pseudoabsence-removal sensitivity. That refit
and assessment have **not** been completed and are not part of this opening.
The primary result cannot establish robustness to zero provenance without it.

## Provenance and transaction design

`config/tasmania_outer_assessment.json` binds the approval, protocol, frozen
Goal036 metric tables, Goal026 feature transform, response-free support,
canonical predictors, patch assignments, response vault, controller, and the
accepted Goal037 transaction digest
`677b8706333dd3df30a0c07bec648ab11e591bfe016bde73dc867d9e78af3d9c`.

The live repository has drifted since Goal037 in `model_adapters.py` and
`uv.lock`. The controller therefore exports commit
`ce70bf114451f8a049be213b1aa891930e305951` into a private archival tree,
checks every Goal037 source and authority against the original config, and
hard-links the accepted model artifacts into that tree. Prediction imports and
model reads are restricted to the archived tree. Native Goal037 neural and
conventional replay gates must pass there before held-patch prediction.

The preparation path reads no response labels. It joins the label-free
Goal026 response-support ledger to canonical predictor rows and Goal025 cell
assignments, applies the frozen outer-training transform, checks the 77-column
encoding, and writes species-specific private arrays. Each prediction lane
retains seed-level scores. Re-execution accepts an existing file only if its
entire stored array equals the regenerated array. Stage receipts bind exact
file and array hashes.

Closure revalidates the input and both prediction receipts, every file hash,
shape, range, seed mask, and species inventory. It materializes neural and
conventional seed means before response access, checks them against the raw
seed arrays, and records all hashes in one prediction-closure receipt. The
score command repeats these checks, caches the closed inputs and averaged
predictions in memory, validates all frozen thresholds and selections, and
only then writes a response-access intent marker. Any interruption after that
marker forbids automated rescue. The only tracked output is an aggregate
receipt without labels, row identifiers, coordinates, or prediction arrays.

## Exact execution sequence

Run from `/Users/bwbrook/papers/dSDM`. These commands stop before response
access:

```sh
ROOT=/Users/bwbrook/papers/dSDM
CFG="$ROOT/config/tasmania_outer_assessment.json"
ARCH="$ROOT/data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1"
NEURAL="$ROOT/data/processed/dsdm/goal034-real-six-path-sentinel/runtime/.venv/bin/python"
CONVENTIONAL="$ROOT/.venv/bin/python"

cd "$ROOT"
PYTHONPATH=src "$CONVENTIONAL" -m dsdm.tasmania_outer_assessment --config "$CFG" validate
PYTHONPATH=src "$CONVENTIONAL" -m dsdm.tasmania_outer_assessment --config "$CFG" archive
PYTHONPATH=src "$CONVENTIONAL" -m dsdm.tasmania_outer_assessment --config "$CFG" validate-archive

cd "$ARCH"
PYTHONPATH=src "$NEURAL" -m dsdm.outer_ready --config config/dsdm_outer_ready.json validate
PYTHONPATH=src "$CONVENTIONAL" -m dsdm.conventional_refit_import \
  --config config/dsdm_outer_ready.json \
  --copied-root data/processed/dsdm/goal037-outer-ready/private/conventional/copy \
  --producer-validation data/processed/dsdm/goal037-outer-ready/private/conventional/producer-validation.json \
  --producer-reference data/processed/dsdm/goal037-outer-ready/private/conventional/producer-reference.json \
  --output data/processed/dsdm/goal037-outer-ready/private/conventional/import_receipt.json \
  validate

cd "$ROOT"
PYTHONPATH="$ARCH/src" "$CONVENTIONAL" -m dsdm.tasmania_outer_assessment --config "$CFG" prepare
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  PYTHONPATH="$ARCH/src" "$NEURAL" -m dsdm.tasmania_outer_assessment --config "$CFG" predict-neural
PYTHONPATH="$ARCH/src" "$CONVENTIONAL" -m dsdm.tasmania_outer_assessment --config "$CFG" predict-conventional
PYTHONPATH="$ARCH/src" "$CONVENTIONAL" -m dsdm.tasmania_outer_assessment --config "$CFG" close
PYTHONPATH="$ARCH/src" "$CONVENTIONAL" -m dsdm.tasmania_outer_assessment --config "$CFG" status
```

The separately authorised opening command is deliberately omitted from this
preparation runbook. It is `score`, and it must be invoked once only after the
closed receipt has been independently reviewed. No fit, model selection,
threshold selection, manual file repair, or result-driven rerun is permitted.

## Diagnostic interpretation and residual risk

The archived native replays test source/runtime/artifact compatibility; the
synthetic recovery tests check alignment, seed aggregation, threshold use,
one-class policy, one-shot access, and tamper gates. These checks do not prove
ecological validity. They cannot resolve mixed zero provenance, detection
bias, spatial dependence, high prevalence and rare negatives, extrapolation
within holes or edges of `D_struct`, architecture-selection uncertainty, or
the limited eight-species scope.

The serious alternative designs answer different questions: buffered or
external geographic holdouts would better test transfer; source-stratified and
pseudoabsence-removal refits would test dependence on the zero mechanism; and
new sites with standardised detection would test calibration against a more
coherent observation process. Evidence from those designs could change the
ecological interpretation but must not be introduced as a post-opening rescue
of this frozen assessment.
