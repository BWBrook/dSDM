# Tasmania pseudoabsence-removal sensitivity: completed results

The approved analysis is complete for eight species, seven endpoints and
three methods. Independent replay passed the entire production inventory,
thresholds, held metrics and map summaries. The completed count is **8,339
physical fits: 8,125 production, 14 smoke and 200 exact auxiliary recovery**.
The original 1,672 held rows and primary results are preserved.

## Main findings

Removing target-training pseudoabsences reduced full-data mean AUC for all
three methods. Means weight the eight species equally; arrows run from the
primary assessment to the sensitivity on the same evaluation rows.

| Method | AUC | TSS | Matthews correlation |
| --- | --- | --- | --- |
| Target-only network | 0.8537 → 0.7704 | 0.5099 → 0.4657 | 0.4050 → 0.3697 |
| Full fine-tuning | 0.8390 → 0.7657 | 0.5575 → 0.4475 | 0.4340 → 0.3593 |
| Selected conventional learner | 0.8441 → 0.7728 | 0.5316 → 0.4082 | 0.4149 → 0.3066 |

Fine-tuning minus target-only mean AUC narrowed from −0.0147 to −0.0047,
but mean TSS reversed from +0.0477 to −0.0182 and Matthews correlation from
+0.0290 to −0.0104. Against the selected conventional learner, fine-tuning
retained lower AUC (−0.0071) but higher TSS (+0.0393) and Matthews correlation
(+0.0527). The comparator and metric therefore remain essential to the claim.
Across all seven endpoints, the sensitivity fine-tuning minus target-only
mean AUC was negative at six and mean TSS was negative at all seven. These
nested endpoints are not independent replications.

The large AUC losses were concentrated in *Vombatus ursinus* (0.419–0.463
across methods) and *Dasyurus maculatus* (0.068–0.204). Their unchanged held
negative classes included 18/25 and 29/50 pseudoabsences, respectively. For
wombats, all three methods classified every held pseudoabsence as positive
after filtering, yet still classified all seven survey-supported absences
correctly; the conventional method improved from three to seven on that
source. For spotted-tailed quolls, survey-absence specificity improved for
all three methods while pseudoabsence specificity declined. The aggregate
losses conceal opposing responses to the two negative-class sources.

Map changes also mattered. Among the seven species with removed training
rows, full-data Spearman correlations ranged from 0.584 to 0.983 and retention
of the original top-decile cells from 31.4% to 85.5%. *D. viverrinus* lost only
0.003–0.011 AUC but retained 50.2–63.3% of its original top-decile cells.
*Thylogale billardierii*, with zero training rows removed, reproduced its
primary predictions, thresholds and maps exactly.

## Interpretation and design limits

Full-data training lost 368 of 11,039 species–cell rows (3.33%). Filtering
preserved the original folds, nested endpoint membership before subtraction,
auxiliary states, encoded environmental substrate, neural architecture,
seeds and conventional selections. Target support masks and conventional
encoders used retained rows. Each method received a new threshold from its
sensitivity OOF scores, using the original maximum-TSS and lower-median tie
rules. All 896 retained fitting roles had both classes, although stopping
sets could have only two absences.

The original protocol named this sensitivity question, but its training-only
implementation and reporting details were fixed after primary outer opening.
It is not a fully prospective confirmatory test. Filtering changes class
balance, spatial support, calibration and stopping together; threshold
reselection adds another distinction from a fixed-threshold perturbation.
The unchanged evaluation-source mixture conditions the comparison. It does
not establish whether pseudoabsences are ecologically true or false, and
neither map set has independent occupancy validation. No survey-only panel,
confidence interval, significance test or selection-uncertainty propagation
was added.

## Review artifacts

- [Updated manuscript PDF](../../manuscript/build/dsdm_manuscript.pdf) and
  [Word file](../../manuscript/build/dsdm_manuscript.docx), 18 PDF pages.
- [Supplement PDF](../../manuscript/build/dsdm_supplement.pdf) and
  [Word file](../../manuscript/build/dsdm_supplement.docx), 15 PDF pages.
  Supplementary methods S2 and Tables S5–S9 cover counts, all three full-data
  metrics, all-endpoint contrasts, map comparisons and source specificity.
- [Eight-plate map PDF](../../manuscript/build/dsdm_tasmania_sensitivity_maps.pdf).
  Each species plate shows primary, sensitivity and difference maps for all
  three methods on fixed scales and the same 71,023 cells.
- [Individual PDF and PNG plates](../../evidence/tasmania_pseudoabsence/20261009/maps/).
- Full numerical tables: [performance](../../evidence/tasmania_pseudoabsence/20261009/paired-performance.csv),
  [contrasts](../../evidence/tasmania_pseudoabsence/20261009/paired-contrasts.csv),
  [source specificity](../../evidence/tasmania_pseudoabsence/20261009/source-specificity.csv),
  [maps](../../evidence/tasmania_pseudoabsence/20261009/map-comparison.csv) and
  [held source counts](../../evidence/tasmania_pseudoabsence/20261009/held-source-counts.csv).

## Verification and provenance

The [approval record](TasmaniaPseudoabsenceRecoveryApproval-20261009.md)
and [execution record](TasmaniaPseudoabsenceExecution-20261009.md) document
the scope, resources, exact auxiliary reconstruction, smoke checks, source
closures and two preserved launcher failures that occurred before fitting.
No model fit failed and the approved fit inventory did not expand.

Prediction closure preceded the single new semantic held-response parse.
The [assessment receipt](../../evidence/tasmania_pseudoabsence/20261009/assessment.json)
and [independent actual replay](../../evidence/tasmania_pseudoabsence/20261009/independent-assessment-verification.json)
cover 4,800 production leaves, 168 thresholds and performance panels, and
24 map pairs. Independent replay used the private snapshot without another
canonical response parse. Continuous metrics agreed within 1e-12; identities,
counts, thresholds, prediction arrays and negative controls agreed exactly.
All original primary pooled metrics reproduced exactly.

[Reporting provenance](../../evidence/tasmania_pseudoabsence/20261009/report-summary.json)
binds the generated supplement to those verified aggregates.
[Final delivery verification](../../evidence/tasmania_pseudoabsence/20261009/delivery-verification.json)
records source and output hashes, independent numerical/prose review,
PDF/Word build checks, document content checks and visual inspection.
The initial report source and receipt are preserved alongside the final
version; only a missing rho glyph required a rendering correction, with
all numerical summary fields unchanged.

The manuscript remains a review draft. Journal choice, author details and
source-access documentation still require the separate submission tranche.
No new commit, push or journal submission accompanied this delivery.
