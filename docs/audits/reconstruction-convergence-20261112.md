# Reconstruction convergence check

Codex (`gpt-6.1-sol`), 12 November 2026. Reviewed `14214c8` plus the
pronoun repair `a8721e9bbf781a2a8ce9ff67718d2a3f050f624d`, and board
thread 162, message 3332.

**Decision:** the scientific argument and five-item display plan have converged.
Four narrow textual repairs remain in the revised sources. The proposal below
incorporates them and reduces the one-page paper to **584 body words**, counting
the four section labels but excluding its title. This review leaves the three
active reconstruction files and `main.md` unchanged; the proposal is for adoption,
not an accepted change or permission to start step 3.

## Remaining repairs

| Item | Check | Replacement |
|---|---|---|
| Mainland borrowing strength | `02:38` says predictions 1 and 2 held for both mammals and birds. Corrected mainland evidence supports the full-data development increment, not a strict reduced-data curve. Goal 045's 25/50 ladder was superseded as non-strict exploratory history: `docs/goals/045-mainland-dsdm-experiment/Decision.md:58–62`; `046-strict-mainland-dsdm-correction/Decision.md:57–63`. | “Prediction 1 held for mainland mammals and birds; the bird learning curve supported prediction 2.” |
| Ensemble chronology | `02:28` puts all ensembles after opening. `01a:74` correctly distinguishes the fine-tuned ensemble. The fixed 50:50 fine-tuned/conventional average was specified in `OuterDiagnostics-20261001.md:95–106` before response access. | Separate prespecified exploratory fine-tuned averaging from post hoc target-only averaging, extent rescoring and survey-only evaluation. |
| Subsampling versus natural scarcity | Abstract `01a:84` says “more so with scarce target records”, conflating the subsampled primary bird panel with naturally poorly recorded species and implying a result for both taxa. | Replace those six words with “especially when bird records were subsampled”. The abstract remains **149 words**. |
| Priority | `01a:17` says “nobody has measured”; `02:9` says the attribution “is unmeasured”. The retained novelty check explicitly establishes a bounded comparison of design features, not universal priority. | “A successful multi-species model does not reveal what sharing contributed. That requires comparison with the same network trained only on the target, in regions excluded from development.” |

The first three were independently checked by the hypothesis reviewer; the
parent checked the novelty wording against the retained review and its
previously verified precedents. The 18 October novelty check explicitly limits
its conclusion to six close studies:
`manuscript/references/novelty-check-20261018.md:3–16`. Primary source:
[Chen et al. 2017](https://www.ijcai.org/proceedings/2017/509); the same-architecture
and no-transfer controls already have precedents. The novelty statement should
therefore identify the study's combination and purpose rather than claim that
no one has isolated cross-species contributions.

The revised message about **average** benefit is scientifically accurate in
context. The surrounding text now names the positive development cases and
allows for NCP and species-level exceptions. Barry's requested read of the
changed main message remains pending; model agreement does not supply that
human review.

## Abstract numbers

All numeric claims in abstract v2 agree with the accepted values:

| Abstract quantity | Accepted value | Display |
|---|---:|---:|
| Mainland development FT minus target-only | +0.0087453295 | +0.009 |
| Bird development FT minus target-only | +0.0057807504 | +0.006 |
| Mainland transfer FT minus target-only | −0.0155130592 | −0.016 |
| Bird new-region FT minus target-only | −0.0003960210 | −0.0004 |
| Bird target-only minus conventional | +0.0031665384 | +0.003 |
| Bird FT/conventional ensemble minus conventional | +0.0103522168 | +0.010 |
| Bird target-only/conventional ensemble minus conventional | +0.0096205084 | +0.010 |
| Primary bird geographic panel | 73 species, 3 regions | 73; three |

Inputs remain those bound by
`evidence/reconstruction/20261112/numerical-review.json`. That record belongs
to the previous review and has not been rewritten. Its numerical evidence
inputs remain unchanged; the current reconstruction texts are a new version.

The matched bird increment increases from +0.0057807504 through +0.0074705349
to +0.0094579975 as target data fall from full to half to quarter. The sparse
species comparison remains distinct: +0.0041 against target-only and +0.0006
against conventional models. The proposal retains both, without claiming that
naturally scarce species reject borrowing strength.

## What can go

The shorter proposal compresses the three predictions and learner lists,
shortens the opening rationale, and removes the Discussion's numbered
repetition of Results. It says the ensemble implication once rather than
repeating it in the closing paragraph. It retains the geographic design,
data fractions, species heterogeneity, scoring-extent diagnostic, absolute
AUCs, Tasmania's co-primary metric disagreement, observation-source sensitivity
and the consolidated limitations paragraph.

The display plan needs no fresh methodological decision. Later production
still needs the agreed descriptive reporting extension for bird extent/ensemble
resampling ranges; this check produces no new intervals, maps or models.
The detailed figure data need not be repeated in this short planning document.

## Proposed one-page paper

## Learning from other species improved distribution models within training regions, but not on average in new ones

**Introduction.** Conservation needs maps of where species live, especially where records are sparse. Species distribution models relate records to environment. Neural networks can learn from other species before adapting to a target. Their gains weaken under geographic transfer (Basile et al. 2026), but a successful multi-species model does not reveal what sharing contributed. That requires comparison with the same network trained only on the target, in regions excluded from development.

Shared environmental responses give three predictions: pretraining improves prediction within the development region; its gain grows as target records shrink; and it persists in new regions. Development results raised a diagnostic question: do model rankings depend on the evidence used for absence?

**Methods.** We studied eight Tasmanian mammals assessed in five held-out patches, five mainland mammals transferred to Tasmania, and 157 south-eastern Australian birds, including 73 assessed in three bioregions withheld with 50 km buffers.

Using grid-cell climate and habitat summaries, we compared a multilayer perceptron pretrained on other species and fine-tuned to the target; an identical network trained on the target alone; and a conventional model selected within development data. Targets were excluded from pretraining, and assessment regions from all fitting. Spatial folds assessed unseen cells within the development domain.

Primary comparisons and learning curves preceded withheld-data access. The richness diagnostic was fixed after development discovery but before opening. Fine-tuned/conventional averaging was prespecified as exploratory; target-only averaging, extent rescoring and survey-only evaluation were post hoc. We measured discrimination with area under the receiver operating characteristic curve (AUC).

**Results.** Pretraining improved development AUC for mainland mammals (+0.009; four of five species) and birds (+0.006; 72 of 73), with the bird gain remaining positive within bioregions and folds (+0.007; 68 of 73). Reducing bird target data to a quarter increased the matched gain to +0.009. Among the least-recorded species, the pretraining increment was +0.0041, but the advantage over conventional models was only +0.0006. Tasmania showed a negative development mean (−0.007).

The average gain disappeared in new regions: −0.016 for mainland mammals and −0.0004 for birds, although 34 bird species and one region (+0.006) benefited. In Tasmania's held-out patches, pretraining lowered AUC (−0.015) but raised the threshold-based true skill statistic (+0.048).

In new bird regions, either network exceeded conventional models by 0.003 AUC; fixed 50:50 averaging gained 0.010 over conventional learning. Absolute AUC was 0.83 in development and 0.68 in new regions; development predictions scored within bioregions and folds already scored 0.69.

The neural advantage declined as background recording richness increased: from +0.005 to −0.004 in development, with a decline in both assessable new regions. In Tasmania, using survey-supported negatives alone changed the pretrained network's deficit against conventional learning (−0.005) to a lead (+0.015).

**Discussion.** Pretraining improved development prediction for mainland mammals and birds, with a larger bird increment under subsampling. Its average gain did not persist across the new regions. The small neural advantage in new bird regions was available without pretraining, while averaging predictions gave the larger mean gain. Model rankings depended on negative evidence.

These tests used tabular inputs. The bird single-species network inherited an architecture selected for fine-tuning. Shared geography, taxa and auxiliary models make species summaries descriptive. The post hoc analyses and performance contrasts cannot distinguish niche information, recording patterns and optimisation as explanations for transfer outcomes. Imagery or spatial context could yield different results.

Claims that learning across species improves prediction need a matched single-species control, evaluated where predictions will be used. Recording where species were sought and not detected would also improve the evidence underlying models and their evaluation.

## Verification and hand-off

No fitting, raw-response access or new numerical analysis was needed. Abstract
values were checked against the accepted synthesis and fixed ensemble summaries.
The parent verified the source-based mainland correction and ensemble chronology.
All numerical source hashes from the previous review remain unchanged.
The proposal's word count uses whitespace-delimited words after removing Markdown
emphasis, beginning at “Introduction.” and ending at the final sentence; including
section labels gives 584 words, excluding them gives 580.

The two active text changes needed outside the proposal are the abstract's
subsampling wording and `01a`'s unsupported priority sentence. I recommend
adopting these limited corrections and the shorter proposal, without another
analysis tranche. Barry's review of the reconstruction, including the new
main message, remains the next stage before step 3.
