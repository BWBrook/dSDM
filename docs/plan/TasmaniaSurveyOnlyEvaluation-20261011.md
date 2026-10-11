# Post hoc Tasmania survey-supported-absence evaluation

11 October 2026. Fixed before computing the new panel. Claude requested this
check in correspondence message 1403 (reply to 1390). Barry then directly
asked Codex to check the reply, address the review comments and respond.
This authorizes the requested evaluation-only follow-up; it adds no model
fits and does not alter the completed primary or sensitivity assessments.
The earlier exclusion of survey-only scoring describes those completed
assessments and remains preserved in their records.

## Question and frozen scope

How do the primary and pseudoabsence-filtered models rank the original held
presences against the original survey-supported absences, when constructed
pseudoabsences are excluded from evaluation? Report all eight species, all
seven already-closed endpoints and the same three methods: target-only,
full multi-head fine-tuning and the primary-selected conventional candidate.
Keep the original held presences. Retain negative rows only where the frozen
source tag is `survey_supported_absence`; exclude `pseudoabsence` rows.
No new survey-support, species, endpoint, patch or performance-based filter
is allowed. Results pool the retained held patches within each species,
matching the original pooled comparison except for negative-source removal.

Use only the already-opened minimal held-response snapshot and closed,
identity-aligned normalized primary/sensitivity prediction files. Verify the
accepted assessment and independent audit, their closure/snapshot links, and
all prediction file hashes before any new calculation. Do not read the
canonical response table or any new held material. Do not fit, tune, select
models, change scores, recover states, or reselect thresholds.

## Summaries fixed before calculation

- Compute ROC AUC for each species–endpoint–method in each training regime;
  report paired sensitivity minus primary changes.
- Also compute TSS, Matthews correlation, balanced accuracy, sensitivity,
  specificity and confusion counts. Use each regime's already-closed,
  inner-derived threshold unchanged. No survey-only or held-optimal threshold
  is selected. Threshold metrics remain distinct from ranking performance.
- Report fine-tuning minus target-only and minus selected conventional
  contrasts for AUC, TSS and Matthews correlation, with their changes between
  training regimes.
- Summarize methods and paired contrasts with equal species weights within
  each endpoint. Present the full-data endpoint beside the published mixed
  panel as the headline comparison; retain all seven endpoints in the
  aggregate tables. Do not pool endpoints as independent replications.
- Retain per-species presence, survey-absence and excluded-pseudoabsence
  counts and membership hashes. Test exact identity alignment, both-class
  support and no exclusion of a held presence. Thylogale has no pseudoabsences:
  its panel and both regimes' results must match the published control exactly.
- No confidence intervals, significance tests, bootstrap, multiplicity
  claims, population extrapolation or independent-species interpretation.

Outputs go to a new `evidence/tasmania_pseudoabsence/20261011/survey-only/`
directory: aggregate performance, contrasts, summary and provenance receipt.
No row identities, coordinates or response records enter public evidence.
Source and output hashes bind the new calculations; existing scientific
receipts remain unchanged. An independent calculation must reproduce the
new counts, AUCs and threshold metrics before substantive conclusions are
used in the paper plan or board response.

## Interpretation and manuscript response

This is an explicitly post hoc change in the evaluation estimand. Survey
nondetection is supported by observation effort, but does not establish true
absence or occupancy. Restricting the negative source also changes its
spatial/environmental support and the presence–negative pairs entering AUC.
The panel cannot by itself identify a learned construction rule, quantify a
causal recording mechanism or establish that one training regime is
universally better. Present the original mixed panel alongside this view.

Freeze further manuscript expansion while preparing a one- to two-page paper
plan for Barry's review. The plan will specify a qualified headline, three
or four supporting lessons, main/supplement allocation, figures/tables and
an explicit length budget checked against current MEE author guidance.
A focused manuscript rewrite follows agreement on that plan; completing this
evaluation does not itself establish the paper's preferred narrative.
