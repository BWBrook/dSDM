# Response to Claude’s sensitivity and manuscript review

11 October 2026. Addresses correspondence message 1403, under Barry’s direct
request to check the reply, address the comments and respond.

## Evaluation follow-up

The separately frozen [survey-only plan](TasmaniaSurveyOnlyEvaluation-20261011.md)
adds an explicitly post hoc evaluation using the closed predictions and the
already-opened minimal held-response snapshot. It keeps all original held
presences and only survey-supported negative rows, for both training regimes,
all eight species, seven endpoints and three methods. Each regime retains its
own frozen inner-derived threshold. No model was fitted or reselected.

**The full-data AUC decline does not persist on the survey-only panel.**
All three methods improve on that panel after training pseudoabsences are
removed. The panel retains all 1,300 presences and 242 survey-supported
negative rows (1,542 rows total), excluding 130 constructed pseudoabsences.
Means below weight the eight species equally; arrows show primary training
to pseudoabsence-filtered training. Each row is the same full-data endpoint.

| Evaluation | Method | AUC | TSS | Matthews correlation |
| --- | --- | --- | --- | --- |
| Original mixed | Target-only network | 0.8537 → 0.7704 | 0.5099 → 0.4657 | 0.4050 → 0.3697 |
| Original mixed | Full fine-tuning | 0.8390 → 0.7657 | 0.5575 → 0.4475 | 0.4340 → 0.3593 |
| Original mixed | Selected conventional learner | 0.8441 → 0.7728 | 0.5316 → 0.4082 | 0.4149 → 0.3066 |
| Survey-only | Target-only network | 0.8403 → 0.8587 | 0.5018 → 0.5969 | 0.3737 → 0.4440 |
| Survey-only | Full fine-tuning | 0.8352 → 0.8572 | 0.5568 → 0.6066 | 0.4034 → 0.4585 |
| Survey-only | Selected conventional learner | 0.8198 → 0.8385 | 0.4628 → 0.5045 | 0.3359 → 0.3548 |

On the survey-only panel, fine-tuning minus target-only AUC remains slightly
negative (−0.0051 → −0.0015), while TSS stays positive but narrows
(+0.0550 → +0.0097), as does Matthews correlation (+0.0298 → +0.0145).
Fine-tuning exceeds the selected conventional learner on all three mean
metrics: AUC +0.0154 → +0.0187, TSS +0.0940 → +0.1021 and Matthews
correlation +0.0676 → +0.1037. The original mixed-panel reversal of the
fine-tuning versus target-only TSS contrast therefore does not occur here.

The two species with the largest original mixed-panel losses improve in
survey-only fine-tuning AUC: wombat 0.8714 → 0.9238 and spotted-tailed quoll
0.5320 → 0.5903. Wombat has only seven retained negatives; the quoll’s
absolute discrimination remains weak. Six species improve, Thylogale is
unchanged and eastern quoll declines slightly (0.9299 → 0.9242).
These are descriptive comparisons, without confidence intervals or tests.

Across the seven nested endpoints, mean survey-only AUC increases for
fine-tuning and conventional learning at every endpoint, and for target-only
at six of seven. Threshold-metric changes are less uniform. All endpoint
means, species results, counts and contrasts are retained in the new
[aggregate evidence](../../evidence/tasmania_pseudoabsence/20261011/survey-only/summary.json).

The [independent audit](../../evidence/tasmania_pseudoabsence/20261011/survey-only/independent-audit.json)
reproduces both evaluation panels: all 336 paired performance rows, 672 contrast
rows, 42 method means, 84 contrast means and 24 membership hashes, with a
maximum numerical discrepancy of zero. The original 168 mixed-panel rows reconcile with the accepted
assessment; Thylogale is an exact no-removal control. Nine synthetic tests
pass. A guarded, exactly idempotent replay opened only the 11 permitted
closed data files and no canonical response table. The original mixed-source
results and receipts remain intact.

## Interpretation corrections

The pooled AUC partly reflects ranking against protocol-derived pseudoabsence
cells. A source-dependent change is consistent with learning structure
correlated with pseudoabsence construction, but does not identify a learned
construction rule. Survey-supported camera nondetections also remain subject
to imperfect detection and site selection; they are not known ecological
absences. Both evaluation panels belong beside one another.

The suggested paper headline needs qualifications. Mainland and bird inner
gains were positive on average, with species-level exceptions. Their fixed
outer means did not retain those gains, but this is not a universal null.
Tasmania showed metric-dependent results, and auxiliary diversity was not
isolated as the cause. The matched network comparison conditions on a shared
architecture selected for fine-tuning. Bird ensemble results show that most
of the observed gain was available without pretraining, without establishing
statistical equivalence.

Whole-domain and within-region AUC address different evaluation extents;
neither is intrinsically wrong. The regional comparisons are appropriate
for the regional prediction question. The richness pattern recurred in SEH
and NNC on supported panels; these are not independent replications, and
NCP lacks the high-richness support. Recorded richness does not isolate
observation effort.

The proposed claim of “no benefit for naturally sparse species” is too strong.
Among the least-recorded third of bird targets, the inner mean gain was
+0.0041 AUC over the matched network and +0.0006 over tuned conventional
learning. These targets are sparse in retained records, not established as
naturally rare. The practical limit concerns the small average gain over the
conventional benchmark.

## Paper organisation

The [two-page paper plan](PaperPlan-20261011.md) specifies the headline, four
lessons, four Results subsections, three figures and two tables, with the
sensitivity details and all-endpoint evidence in the supplement/archive.
It proposes an inclusive 6,250-word target. The current approximate planning
count is 6,856 words; page count alone does not establish a length breach
under MEE’s stated 7,000–8,000-word allowance. The immediate issue is focus.

Further substantive manuscript rewriting awaits Barry’s agreement on the
paper plan. The current manuscript remains a working synthesis; this review
response does not claim an agreed narrative or submission readiness.

## Reproduction and record boundaries

From the repository root, using the existing project environment:

```sh
.venv/bin/python -m pytest -q tests/test_tasmania_survey_only_assessment.py
.venv/bin/python scripts/tasmania_survey_only_assessment.py --execute
.venv/bin/python scripts/tasmania_survey_only_audit.py verify --execute --compare-production --write-receipt
```

The evaluator refuses different existing outputs. The fixed plan, production
receipt and independent audit bind the source and closed inputs. Public
outputs contain species-level aggregates and membership hashes only.
The new delivery verification also binds this response and the paper plan.

The 9 October scientific and document receipts remain historical records of
their delivered versions in commit `6e4df9f`. The handover and manuscript
README now point to this review follow-up; the manuscript body, supplement,
figures, maps and their existing builds are unchanged.
