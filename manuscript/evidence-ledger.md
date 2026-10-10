# Evidence ledger for the cross-case manuscript

## 8 October follow-up: species-composition ranges

`docs/plan/BirdCompositionResampling-20261008.md` fixes the reporting recipe
before resampling. `scripts/bird_composition_resampling.py` reads the unchanged
revision-01 summary and canonical response-free Goal050 focal-block mapping.
It produces four paired species-composition ranges and two inner focal-block
width checks under `evidence/cross_case_synthesis/20261008/`. The JSON records
source, plan and input hashes, RNG streams, block counts and checked invariants.
The accompanying verification receipt binds numerical checks and final builds.

Figure 1 and Tables S1d/S1e label these as central 95% resampling ranges of
panel means. They are conditional empirical reweighting diagnostics, not
confidence intervals or fitting, spatial-sampling, selection or population
uncertainty. Ten hash-balanced computational blocks are neither taxonomic nor
spatial clusters; the block check is not a general correction for dependence.
No primary result, model, prediction, threshold or selected candidate changed.

Claude's correspondence message 1167 relays Barry's agreement to run the
Tasmania sensitivity; its endpoint scope is still the subject of a direct
question in Codex. No new fits or raw-response scoring have been run. MEE is a
reasonable working target, while submission formatting remains incomplete.

## Preserved 5 October review-revision record

The manuscript is a substantive review draft, not a submission-ready paper.
The source of each numerical result is listed below. Accepted historical
receipts and reports are preserved. A new analysis does not retroactively
become part of a prospective plan.

## Scientific sources

| Manuscript material | Authoritative source | Status and interpretation |
|---|---|---|
| Original Tasmania estimand, responses, patches and metrics | `docs/plan/tasmanian_modelling_protocol.md`; Goal025–029 accepted records | Approved design; held-patch interpolation, not regional transfer |
| Original Tasmania inner results | `evidence/dsdm_inner_evaluation/goal036/stratum_metrics.csv`, `conventional_selection.csv`; Goal036 Decision | Accepted inner evaluation; method selection uses this surface |
| Original Tasmania fitted outer package | `evidence/dsdm_outer_ready/goal037/receipt.json` | Historical fitted-model closure; its zero-access statement remains unchanged |
| Original Tasmania held-patch results | `evidence/tasmania_outer_assessment/20261005/receipt.json`; bound pre-opening review | Authorised one-shot opening on 5 October; full-data AUC and TSS remain co-primary; all species, endpoints and patches retained |
| Tasmania capacity and predictor sensitivities | Goal038 Decision; Goal039 Log, 10 August closeout | Inner-only bounded sensitivity experiments; both retained the original specification |
| Strict mainland inner result | `evidence/mainland_dsdm/goal046/summary.json`; Goal046 Decision | Same five targets as the primary transfer panel; full-data equal-fold AUC; added to revision 01 |
| Mainland-to-Tasmania design | Goal042 and Goal047 Goal/Decision records | Five shared mammals; primary camera-supported evaluation; geographically and observationally shifted |
| Mainland-to-Tasmania results | `evidence/tasmania_transfer/goal047/summary.json` | Accepted outer result; use primary surface in the main text |
| Bird domain, species, support panels, region roles and buffers | Goal048–050 Decision records; Goal048 `design_resolution.json` | NCP supported, SEH edge, NNC mosaic; all complete regions plus external 50-km buffers excluded simultaneously before fitting |
| Bird conventional and dSDM inner results | `evidence/seawfb_conventional/goal051/summary.json`; `evidence/seawfb_dsdm/goal052/summary.json` | Accepted inner evaluation; mean-fold AUC distinguished from pooled OOF AUC |
| Bird inner sparse-third and recording-richness diagnostics | `fable-review-20260927.json`, `effort-review-20261001.json`, `effort-followup-20261002.json`; corresponding Goal052 review reports | Post hoc retained-data analyses that predate outer opening; sparse third is 53 of all 157, not an outer panel |
| Bird outer results | `docs/goals/052-seawfb-dsdm-experiment/OuterResults-20261005.md`; `OuterDiagnosticsResults-20261005.md`; `evidence/seawfb_dsdm/goal052/outer-acceptance-20261005.json` | Accepted three-region assessment; diagnostic definitions and FT/conventional average fixed before opening |
| Bird regional extent, target-only ensemble and SEH tails | New `ExtentReview-20261005.md` and associated `extent-review-20261005.json` | Post hoc use of unchanged saved predictions; no refit or weight selection |
| Cross-case means, contrasts and figures | `evidence/cross_case_synthesis/20261005/revision-01/summary.json`, CSVs, scripts and verification receipt | Six headline inner/outer assessments, now including mainland inner; original reporting outputs preserved |
| IQR and single-species deletion ranges | Revision-01 summary and Table S1 | Post hoc descriptive dispersion and sensitivity of the observed panel; no confidence interval or population inference |
| Matched bird network versus tuned shallow ANN | Revision-01 `bird_target_only_baseline` | Recomputed from accepted Goal051/052 aggregates; primary 73 TO minus ANN +0.0037053, minus selected conventional −0.0023909 |
| Expanded methods and candidate grids | `manuscript/text/supplement.md`; `scripts/cross_case_supplement.py`; bound configurations | Original Tasmania full registry distinguished from the portable mainland/bird subset and seed policy |

The full-data Tasmania inner means in the review draft are a descriptive
re-expression of the accepted species-level table: equal species weights,
mean-fold AUC within species. The original decision's species medians are also
reported and are not replaced. Cross-case summaries do not pool species across
experiments or estimate a common population effect.

## Terminology and claim limits

- NCP is Naracoorte Coastal Plain; SEH is South Eastern Highlands; NNC is NSW
  North Coast. New England Tablelands (NET) belongs to the retained region set.
- Bird and mainland target-group backgrounds are unrecorded cells with defined
  recording support, not verified absences. Camera nondetections are
  survey-supported absences, not known occupancy states.
- The original Tasmania outer package and the mainland-to-Tasmania assessment
  are distinct frozen experiments. Shared targets, geography and observation
  sources prevent an assertion that they are independent datasets.
- The original Tasmania inner result is weak/null at full target data. An
  assertion that all cases benefit from in-domain pretraining is unsupported.
- Within-region scoring excludes the response-free ledger's domain complement
  and changes comparison pairs and weighting. A small residual inner–outer
  difference is not an identified geographic penalty.
- An ensemble gain can be available without pretraining. Comparing two fixed
  ensembles does not prove equality of their information or causal mechanisms.
- Richness-bin diagnostics compare all presences with each background bin;
  the high-richness subset restricts both classes. Keep these estimands distinct.

## Literature checked for this revision

Bibliographic details and the claims used in the draft were checked against
primary paper records on 5 October 2026:

- [Cole et al. 2023](https://proceedings.mlr.press/v202/cole23a.html): shared
  representations for species mapping; prevents a novelty claim that neural
  multi-species representations were absent from SDM.
- [Cawley and Talbot 2010](https://jmlr.org/papers/v11/cawley10a.html): selection
  bias in performance evaluation.
- [Phillips et al. 2009](https://esajournals.onlinelibrary.wiley.com/doi/10.1890/07-2153.1):
  occurrence/background sampling bias.
- [Roberts et al. 2017](https://nsojournals.onlinelibrary.wiley.com/doi/10.1111/ecog.02881):
  validation design for structured data and intended prediction tasks.
- [Lobo et al. 2008](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1466-8238.2007.00358.x):
  dependence of AUC on evaluation extent.

A further 15 candidates supplied in Fable's review were checked against
primary publisher/conference records. Metadata, supported claims, scope
limits and source URLs are in
`manuscript/references/review-candidates-20261005.json`. Twelve were integrated:
Botella (2018), Deneu (2021), Harris (2015), Norberg (2019), Valavi (2022),
Yates (2018), Wenger and Olden (2012), Jiménez-Valverde (2012), Warton and
colleagues (2013), Johnston and colleagues (2021), Kumar and colleagues (2022),
and Araújo and New (2007). Chen, blockCV and area-of-applicability candidates
remain documented but uncited because those methods are not analysed here.

A separate citation check verified all 17 cited entries and repaired the
placement of the Warton/Johnston citations: they support observation-aware
evaluation, not the proposed known-truth simulations. Kumar is explicitly a
computer-vision precedent for a hypothesis, not an explanation of this result.
This is a focused literature expansion, not a systematic review.

## Submission work remaining outside this review-draft tranche

Confirm the intended journal and replace or approve the placeholder CSL;
reconcile author contributions and affiliations; complete dataset citations,
acquisition dates and source-specific access/release conditions. The revised
supplement supplies the conventional grids, bird architecture/training details,
and descriptive tables; final submission still needs the complete predictor
and species/source inventory in the chosen journal's format.

The Tasmania sensitivity is now complete under Barry's direct all-endpoint
approval and the separately approved 200-state exact auxiliary recovery.
Its original protocol question predates primary opening; the training-only
implementation, recalibration, comparator restriction and map summaries were
specified afterwards. It is therefore a sensitivity analysis, not a fully
prospective confirmation. Survey-only evaluation remains excluded.

See [the results report](../docs/plan/TasmaniaPseudoabsenceResults-20261009.md)
and [execution record](../docs/plan/TasmaniaPseudoabsenceExecution-20261009.md).
The original co-primary assessment is preserved; the new results supplement it.

The original Tasmania opening records were committed separately as `4d2a024`.
No push or board message was sent in this revision.

## Completed Tasmania sensitivity — 9 October 2026

| Claim or artifact | Source | Qualification |
| --- | --- | --- |
| Scope and recovery authority | `docs/plan/TasmaniaPseudoabsenceSensitivity-20261008.md`; `TasmaniaPseudoabsenceRecoveryApproval-20261009.md` | Eight species, seven endpoints, three methods; 200 exact auxiliary replays separately approved |
| Training perturbation | `evidence/tasmania_pseudoabsence/20261008/source-census.json` | 368 of 11,039 full-training rows removed; 896 retained roles contain both classes; stopping roles can have only two absences |
| Complete fit inventory | `evidence/tasmania_pseudoabsence/20261009/independent-assessment-verification.json` | 8,125 production + 14 smoke + 200 recovery physical fits; 4,800 production leaves |
| Paired held performance and source specificity | `assessment.json`; `paired-performance.csv`; `source-specificity.csv`; `paired-contrasts.csv`; `held-source-counts.csv` in the same directory | Same 1,672 held rows; separately recomputed sensitivity OOF thresholds; all original primary pooled metrics reproduce exactly |
| Independent actual replay | `independent-assessment-verification.json` | Pass: all source leaves, 168 thresholds/panels, source summaries and 24 maps; snapshot replay without another canonical response parse |
| Suitability-map changes | `map-comparison.csv`; `map-rendering.json`; `maps/` | 24 full-data pairs over identical 71,023 cells; shared scales; score/rank changes, not validated occupancy changes |
| Supplementary methods S2 and Tables S5–S9 | `manuscript/text/tasmania-sensitivity.md`; `report-summary.json` | Generated from audited aggregates; equal species weights separately at each endpoint; no inferential intervals or tests |
| Final review and document outputs | `delivery-verification.json` | Independent prose/numerical review, source-bound PDF/Word builds and visual checks |

Large mean AUC declines are concentrated in wombats and spotted-tailed quolls.
Their survey-supported and pseudoabsence negatives responded differently;
the result neither verifies nor falsifies the ecological status of the
pseudoabsences. Filtering changes class balance, spatial support, calibration
and stopping together. The fine-tuning advantage over target-only learning
reverses for full-data mean TSS and MCC, while the conventional comparison
remains metric-dependent. The zero-removal Thylogale control is exact.
