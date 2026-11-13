# Step 3b review: paragraph abstracts

Codex (`gpt-6.1-sol`), 13 November 2026. Reviewed `6b52446`,
`manuscript/reconstruction/03b-paragraph-abstracts.md`, section abstracts
at `8c24ef2`, and correspondence thread 162/message 3356.

**Verdict:** retain the 31-paragraph structure and its order. The section-abstract
material is covered, and the Results order matches the agreed display plan.
Make the scientific and citation repairs below before expansion. Replacement
abstracts remain within three or four sentences; the active reconstruction
files, article and bibliography are unchanged by this review.

## Principal decisions

**R5 should give the numbers and the positive diagnostic inference, without
attributing a fraction of the transfer decline to extent.** Mean fine-tuned
AUC is 0.831603 under the published development aggregation, 0.689709 when
development predictions are scored within bioregions/folds, and 0.682732 in
the withheld regions. This shows that low regional AUC can arise from rescoring
unchanged development predictions. It does not identify how much geographic
transfer caused or how much scoring extent explains. The scores change pairs,
support and weighting; the outer comparison also changes fitted models and
composition. No causal decomposition or attributable percentage was estimated.

The existing dated extent review already states this boundary:
`docs/goals/052-seawfb-dsdm-experiment/ExtentReview-20261005.md:3–17` and
`docs/plan/CrossCaseResults-20261005.md:35–41`. The revised R5 and D5 below
retain an informative result rather than retreat to unexplained numbers.

**M3 contains a response-class error.** Masked unknowns are not a third kind
of negative. The two negative sources are camera-supported nondetections and
constructed pseudoabsences. Unknown species–cell combinations are masked;
they do not contribute a negative response to training or evaluation.
See `manuscript/text/main.md:41` and the existing response-design records.
The framework summary must change as well as the paragraph abstract.

**D1 should not call the mean contribution “nothing”.** The observed
three-region bird mean is −0.000396 AUC, with substantial species and regional
variation. State the matched mean rather than imply exact zero, equivalence
or general absence of shared information. The paragraph's main finding remains
that the average neural advantage over conventional models was available
without pretraining.

**Keep D7 merged at this planning stage.** Its single message is that the
design limits point to the next tests. Four shorter sentences can carry that
message. Allocate approximately 170–190 words in the full draft, within the
Discussion's existing budget. Split limitations and next tests only if the
expanded paragraph becomes overloaded; paragraph count is not a scientific
constraint. Such a split should redistribute the same word allocation.

## Other targeted repairs

| Paragraph | Repair and purpose |
|---|---|
| I2 | Use representative precedents rather than expanding twelve signposts into a literature catalogue. Scope Basile's finding to its particular transfer comparison. |
| I3 | Keep the established-control attribution question. Move Pili away from this gap; its experiment concerns sampling correction and evaluation rather than matched neural ablation. |
| M2 | “Sources and versions” should not imply that missing legacy predictor versions have been recovered. Name available metadata and provenance gaps. |
| M9 | Specify that the crossed target/auxiliary curves use the primary 73 birds; Tasmania uses its own nested target-data ladders, and corrected mainland comparisons are full-data only. |
| M10 | Separate region-then-species weighting for geographic bird assessments from fold averaging in development. Metric definitions belong here, with our threshold policy identified as our design. |
| R2 | The least-recorded third comes from all 157 targets, not necessarily the 73 used in the subsampling curve. Scope the frozen result to the primary panel and full endpoint. |
| R4 | The grammar could read as target-only beating fine-tuning by 0.0028. State both increments explicitly relative to conventional models, and scope ensemble superiority to the panel means. |
| R7/D6 | Name mean AUC when describing the ranking reversal; changing evaluation negatives and retraining are different operations. |
| D2 | Replace “locate where it holds” with a statement distinguishing the development information from its added value after geographic transfer. These tests do not delimit every setting in which pretraining works. |
| D3 | Replace generic “cheap to test” with the concrete fact that these averages used retained predictions and fixed weights. Testing complementary learners alongside auxiliary pools remains supported. |

The framework and paragraph abstracts should agree. In particular:

- **M3 framework:** eight species were assessed in five patches, with two
  negative sources and unknown combinations masked.
- **R5 framework:** regional rescoring produced low absolute AUC from unchanged
  development predictions.
- **D3 framework:** fixed averaging gave a larger mean gain in new bird regions
  and warrants comparison alongside larger auxiliary pools.

The section allocations sum to 4,800 words and leave 200 words of headroom.
Thirty-one paragraphs at exactly 150 words would be 4,650; use the section
allocations as budgets rather than force every paragraph to the same length.
Methods can devote more room to design and fewer words to routine software
details. There is no need to add a sixth display item.

## References: identities and placements

Two independent Codex checks verified all eight identities against registered
DOI metadata and primary records. Seven can be added in their scoped roles;
Araújo & New already exists as `araujo2007` and should be reused.

| Proposed key | Verified DOI | Decision | Suitable location |
|---|---|---|---|
| basile2026 | [10.1002/ecog.08269](https://doi.org/10.1002/ecog.08269) | confirm | I2, D1, D2 |
| pili2025 | [10.1002/ecog.08002](https://doi.org/10.1002/ecog.08002) | relocate | I4, I5, D6 |
| fithian2015 | [10.1111/2041-210X.12242](https://doi.org/10.1111/2041-210X.12242) | confirm | I5, D6 |
| he2016 | [10.1109/CVPR.2016.90](https://doi.org/10.1109/CVPR.2016.90) | confirm narrowly | M6 |
| hanley1982 | [10.1148/radiology.143.1.7063747](https://doi.org/10.1148/radiology.143.1.7063747) | confirm | M10 |
| allouche2006 | [10.1111/j.1365-2664.2006.01214.x](https://doi.org/10.1111/j.1365-2664.2006.01214.x) | confirm | M10 |
| araujo2007 | [10.1016/j.tree.2006.09.010](https://doi.org/10.1016/j.tree.2006.09.010) | reuse existing | D3 |
| breiner2015 | [10.1111/2041-210X.12403](https://doi.org/10.1111/2041-210X.12403) | confirm narrowly | D4 |

The metadata and complete author displays are saved in
`manuscript/references/reconstruction-reference-check-20261113.json`.
These are verification records, not new entries silently installed in
`refs.yaml`.

- **Basile:** a direct transfer precedent in I2 and D1/D2. Its continental
  comparison uses AUC and its regional evaluation uses Boyce indices; do not
  turn those into a numerical AUC drop. It does not supply a matched target-only
  neural control.
- **Pili:** relocate to I4/I5 or the negative-evidence discussion. It uses
  virtual species to compare sampling corrections and evaluation tasks, not
  pretraining attribution.
- **Fithian:** appropriate in I5. Its pooled survey/collection framework
  models shared sampling bias under explicit assumptions; it does not prove
  our encoder learned observer behaviour.
- **He:** cite the residual-learning principle in M6, then describe our dense
  residual MLP from repository specifications. Do not identify it with the
  original convolutional image architecture.
- **Hanley and Allouche:** use for AUC's ranking interpretation and TSS's
  classification definition. Allouche does not justify a threshold-independent
  TSS claim or invariance to changing the source of negatives. Threshold
  selection/freezing and species-composition ranges are our procedures.
- **Araújo & New:** use the existing entry for ensemble rationale, without a
  claim of cheapness or general superiority.
- **Breiner:** retain in D4 for rare/undersampled-species modelling. Its
  AUC-weighted ensemble of bivariate models is a different construction from
  our fixed 50:50 neural–conventional average.

Pili may be signposted in I4 or I5, Fithian in I5, He in M6, and Breiner in
D4 without rewriting those otherwise suitable paragraphs. The replacement
I3 removes the misplaced citation, and D3 reuses Araújo's existing key.

Publication-year checks matter here: Fithian is the 2015 journal issue despite
2014 online publication; Araújo & New is the 2007 issue despite 2006 online
publication. Breiner's registry and publisher disagree about its precise
online date, but agree on the 2015 citation year and October issue. The
verification record preserves that discrepancy instead of inventing a date.
No identity remains unresolved and no Zotero import is needed for these eight.

## Replacement paragraph abstracts

Only affected paragraphs are supplied. They replace their corresponding
abstracts; the other paragraphs and the 6/11/7/7 framework remain in place.

**I2. Promise.** Species share environmental responses, so records of one species can inform predictions for another. Multi-species pretraining learns from other species before adapting to a target. Shared learning has improved ecological prediction through several modelling approaches. In a European continental-to-regional comparison, neural joint models' development advantage did not persist under transfer. [Chen et al. 2017; Norberg et al. 2019; Brun et al. 2024; Ovaskainen et al. 2025; Basile et al. 2026]

**I3. Gap.** A successful multi-species model does not reveal what sharing contributed. Comparing pretrained and target-only networks with the same architecture measures the increment from pretraining. Comparing either network with a conventional model assesses its practical advantage. We combine established controls with target-excluded pretraining and whole-region exclusion to assess that increment in new regions. [Chen et al. 2017; Bourel et al. 2025]

**M2. Data and inputs.** Responses came from Atlas of Living Australia occurrence records (2001–2025) and Tasmanian camera surveys. Inputs summarised grid-cell climate, terrain, vegetation, soil and land use. Scaling and encoding were fitted on training partitions. Predictor definitions, available source metadata and provenance gaps are documented in Supporting information. [Belbin et al. 2021; Fick & Hijmans 2017]

**M3. Tasmanian mammals.** Eight species were modelled on a 0.01° grid. Responses comprised presences and two negative sources: camera-supported nondetections and constructed pseudoabsences. Unknown species–cell combinations were masked and excluded from the response loss and evaluation. Five patches fixed before modelling touched the training areas and assessed interpolation. [Supporting information]

**M9. Data experiments.** Bird learning curves crossed 25%, 50% and 100% target data in the primary 73-species panel with 20, 80 or all eligible auxiliary species. Original Tasmania used nested target-data ladders at those fractions. Corrected mainland comparisons used full target data. Tasmania separately tested removing training pseudoabsences and filtering evaluation negatives. [Supporting information]

**M10. Metrics and summaries.** AUC was primary; TSS was co-primary in Tasmania using thresholds fixed from development predictions. Bird geographic summaries averaged regions within species and then species equally; development summaries averaged folds. Species-composition resampling supplied descriptive ranges. AUC assesses ranking, whereas TSS assesses classification at a fixed threshold. [Hanley & McNeil 1982; Allouche et al. 2006; Supporting information]

**R2. Borrowing strength.** Subsampling bird target data from full to half to quarter increased the matched pretraining increment from +0.0058 through +0.0075 to +0.0095. The least-recorded third of all 157 bird targets gained +0.004 over target-only and +0.0006 over conventional models. At full target data and auxiliary size, the frozen encoder gained +0.0022 over target-only on the primary panel, with 57 of 73 species benefiting. [Supporting information]

**R4. Networks and ensembles.** Relative to conventional models, mean AUC increments in new bird regions were +0.0032 for target-only and +0.0028 for fine-tuning. Their fixed 50:50 ensembles with conventional predictions gained +0.0096 and +0.0104, positive for 64 and 60 of 73 species, respectively. Both ensemble means exceeded both neural means. [Fig. 3]

**R5. Extent.** Mean AUC was 0.83 in development and 0.68 in new regions. Scoring unchanged development predictions within bioregions and spatial folds gave 0.69. Regional scoring therefore also produced low absolute AUC within the development data. [Table 1; Supporting information]

**R7. Tasmanian negatives.** At full target data with training unchanged, survey-only evaluation reversed the fine-tuned-minus-conventional mean AUC contrast from −0.005 to +0.015. Removing training pseudoabsences lowered mean AUC against mixed negatives and raised it against survey-supported negatives. Retraining also changed the highest-scoring cells for all seven affected species. [Fig. 4b; Supporting information]

**D1. Principal finding.** In new bird regions, the small average neural advantage was available without pretraining. A comparison against conventional models alone could credit that advantage to shared learning. The matched pretraining contrast averaged −0.0004 AUC across the three regions. [Basile et al. 2026, for the comparison with previous transfer evidence]

**D2. Shared information.** Development gains and the frozen-encoder result show that shared information improved prediction in the tested setting. In new regions, its increment varied among species and regions, including a positive mean in Naracoorte Coastal Plain. These results distinguish useful development information from its additional predictive value after geographic transfer. [Chen et al. 2017; Brun et al. 2024; Bourel et al. 2025; Ovaskainen et al. 2025; Lange et al. 2025; Basile et al. 2026]

**D3. Practical route.** Fixed averaging produced the larger mean AUC gain in new bird regions with either neural model. Both averages used retained predictions and fixed weights. Complementary learners therefore deserve comparison alongside larger auxiliary pools. [Norberg et al. 2019; Valavi et al. 2022; Araújo & New 2007]

**D5. Absolute AUC.** Development predictions scored within bioregions and folds had an AUC of 0.69, close to the new-region mean of 0.68. Low regional AUC can therefore occur without transferring a fitted model. Comparing learners on the same observations makes their relative predictive gains explicit. [Lobo et al. 2008; Jiménez-Valverde 2012; Yates et al. 2018]

**D6. Negative evidence.** Changing evaluation negatives reversed the fine-tuned-versus-conventional mean AUC ranking in Tasmania. Removing training pseudoabsences and refitting changed prediction maps. Negative evidence is therefore part of specifying both model fitting and the problem against which predictions are assessed. [Phillips et al. 2009; Warton et al. 2013; Fithian et al. 2015; Johnston et al. 2021]

**D7. Limitations and next tests.** The tests used tabular inputs and, in birds, an architecture selected for fine-tuning. Auxiliary pools changed records and species together; shared geography and models make the summaries descriptive. Several diagnostics were post hoc, while negative observations neither establish ecological absence nor identify the mechanism behind a model contrast. Fresh regional tests should pair matched target-only controls with spatial inputs, observation-aware models and independent surveys. [Deneu et al. 2021; Cawley & Talbot 2010; Kumar et al. 2022; Johnston et al. 2021]

## Verification and hand-off

All numerical source bindings checked in the preceding reviews still match.
The parent independently reproduced the two ensemble mean gains and counts
from the 73 per-species records: +0.0103522 for fine-tuned/conventional
(60 positive), +0.0096205 for target-only/conventional (64 positive).
Both means exceed both uncombined neural means; this statement is not true
for every species and is not written that way in the replacement.

The check record is
`evidence/reconstruction/20261113/paragraph-review.json`. It binds the
reviewed drafts, prior numerical evidence, new reference verification,
replacement text and three/four-sentence checks. No fitting, raw-response
access or ecological experiment was needed. This review adds no confidence
interval or new statistical estimand.

Please integrate the paragraph and reference corrections and retain the
one-message-per-paragraph discipline during expansion. This review does not
guess the next stage of Barry's reconstruction method or create a fresh human
approval gate.

Next: Claude — integrate the paragraph and reference corrections.
