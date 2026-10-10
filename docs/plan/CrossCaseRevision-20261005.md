# Cross-case manuscript revision and response to Fable

5 October 2026. Revision following Fable's review (Correspondence message
1025). The review is attributed scientific advice; the accepted analyses and
their original status remain authoritative.

## Completed revisions

The manuscript now presents both in-domain/transfer pairs. Strict mainland
inner fine-tuning minus target-only AUC is +0.008745, with 4/5 species positive;
the conventional contrast is +0.003950, with 5/5 positive. The same five species
have a negative mean target-only contrast in the Tasmania transfer, but a
positive median. The bird inner mean gain is also absent from its equal-region
outer mean. The original Tasmania result remains qualified as no consistent
full-data AUC advantage, with contrasting co-primary TSS in the held patches.

The opening records were committed separately as `4d2a024`, including the
controller, frozen config, pre-opening review and final receipt. No opening or
scoring was repeated. The manuscript and this reporting revision remain local
working-tree changes; no push or board message was sent.

| Review item | Revision and evidence |
|---|---|
| M1: mainland inner omission | Added to Methods, Results, Discussion, abstract, Figure 1, synthesis tables and evidence ledger; exact Goal046 source hash bound in revision-01 summary |
| M2: roles and buffers | Described NCP supported transfer, SEH environmental edge, NNC fragmented mosaic, and simultaneous exclusion of complete regions plus external 50-km buffers; roles assigned before fitted outcomes |
| M3: inner richness discovery | Added the 59-primary and 142-target gradients plus the exact 73-species background-share decomposition; explicitly exploratory inner evidence preceding the frozen outer diagnostic |
| M4: sparse targets | Added the sparsest 53/157 panel: 224–3,649 retained presences, FT minus conventional +0.000628 (35/53 positive), FT minus frozen +0.00000024, FT minus target-only +0.004114; distinguished this from subsampling widespread species |
| M5: literature | Verified all 15 candidates; integrated 12, for 17 cited works; metadata and use limits retained in `review-candidates-20261005.json` |
| M6: abstract | Reduced to 204 words around the two inner/transfer pairs, extent dependence, sparse-target limit and ensemble result |
| R1: methods | Added predictor names/width, optimiser, stopping/replay, epochs, seed rules, software and compute; supplementary tables give candidate parameters and original versus portable grids |
| R2: target-only baseline | Primary 73 TO minus tuned shallow ANN +0.003705; TO minus selected conventional −0.002391; architecture-selection asymmetry stated |
| R3: AUC/TSS disagreement | Explained ranking versus transferred-threshold operating points and possible ROC crossing; mechanism unresolved; frozen co-primary values retained |
| R4: uncertainty | Added species points, mean, median, IQR and the range of means under single-species deletion; no inferential interval |
| R5: pseudoabsences | Concrete proposal prepared and independently reviewed; run and final protocol disposition remain for Barry's decision |
| Figures | Six assessments with row-specific linear scales and IQR in Figure 1; full ensemble names and 68/73 versus 34/73 annotations in Figure 2 |

## Revised descriptive synthesis

Every row uses full target data. Inner values first average fold AUC within
species. Original Tasmania outer values pool held patches; mainland transfer
uses its camera-supported primary surface; bird outer values average the
three regional AUCs within species. There is no grand mean across cases.

| Assessment | Comparator | Mean | Median [Q1, Q3] | Positive | Mean after single-species deletion |
|---|---|---:|---:|---:|---:|
| Tasmania inner | Target-only | -0.0067 | -0.0027 [-0.0172, +0.0106] | 4/8 | [-0.0126, +0.0001] |
| Tasmania inner | Conventional | -0.0498 | -0.0390 [-0.0521, -0.0272] | 0/8 | [-0.0563, -0.0340] |
| Tasmania held patches | Target-only | -0.0147 | -0.0120 [-0.0281, -0.0024] | 1/8 | [-0.0176, -0.0114] |
| Tasmania held patches | Conventional | -0.0051 | -0.0083 [-0.0488, +0.0095] | 3/8 | [-0.0218, +0.0027] |
| Mainland inner | Target-only | +0.0087 | +0.0097 [+0.0027, +0.0107] | 4/5 | [+0.0057, +0.0111] |
| Mainland inner | Conventional | +0.0039 | +0.0025 [+0.0009, +0.0051] | 5/5 | [+0.0022, +0.0048] |
| Mainland to Tasmania | Target-only | -0.0155 | +0.0269 [-0.0830, +0.0272] | 3/5 | [-0.0435, +0.0169] |
| Mainland to Tasmania | Conventional | -0.0277 | -0.0224 [-0.0446, -0.0192] | 1/5 | [-0.0508, -0.0054] |
| Birds inner: common 73 | Target-only | +0.0058 | +0.0054 [+0.0036, +0.0070] | 72/73 | [+0.0056, +0.0059] |
| Birds inner: common 73 | Conventional | +0.0034 | +0.0032 [+0.0022, +0.0043] | 67/73 | [+0.0033, +0.0035] |
| Birds outer: equal regions | Target-only | -0.0004 | -0.0006 [-0.0095, +0.0077] | 34/73 | [-0.0012, +0.0002] |
| Birds outer: equal regions | Conventional | +0.0028 | +0.0017 [-0.0105, +0.0177] | 39/73 | [+0.0022, +0.0036] |

Q1 and Q3 are linearly interpolated quartiles. The deletion range is the
minimum and maximum mean obtained by removing each species once while keeping
its paired model comparison intact. It describes the sensitivity of these
particular panels, not a confidence interval for an ecological population.
Mainland inner gains remain positive under every deletion; the five-species
transfer mean against target-only can change sign. The bird outer pretraining
mean also straddles zero under deletion, consistent with its very small
magnitude. The species points, IQRs and full results remain visible together.

Fable proposed a species bootstrap labelled as composition sensitivity. This
revision uses deterministic deletion instead: it directly shows whether one
observed species changes the mean without assigning bootstrap frequencies to
correlated taxa. It does not solve population uncertainty or evaluate joint
taxon dependence. A bootstrap remains a separate presentation choice, not a
missing significance test.

## Decisions and limits

Methods in Ecology and Evolution is Fable's recommended journal; Barry has not
yet selected the journal. The current CSL remains the existing review-draft
placeholder. Author metadata, source-specific data citations and release
conditions still require completion before submission.

The original pseudoabsence-removal question was prespecified, but details of
training-only removal, endpoint restriction, thresholds and map summaries were
not all fixed before opening. The separate sensitivity proposal states those
choices and a bounded compute plan for review. Its independent proposal audit
found the repaired contract ready for Barry's approval, without qualifying any
implementation or production run. The recommended full-data option requires
1,122 production fits plus 14 smoke fits; all seven endpoints require 8,125
production fits. Full-data-only coverage leaves the reduced endpoints untested.
The optional survey-only secondary evaluation is excluded by default and would
require a separate decision before fitting. No sensitivity fit, new outer
threshold search or bootstrap has been run. In particular, this revision does
not turn the original test into a second untouched confirmatory assessment.

The extent comparison remains post hoc and does not identify a true geographic
penalty. The similar fixed ensemble means do not establish equivalence or
absence of information from pretraining. Regional role differences and
recorded-richness dependence do not identify causal mechanisms.

## Reproduction and verification

Use `scripts/cross_case_synthesis.py`, the two plotting scripts, and
`scripts/cross_case_supplement.py` as documented in `manuscript/README.md`.
Revision-01 reporting outputs are separate from the preserved first synthesis.
All 280 fields from the earlier case summaries are unchanged; only the omitted
mainland inner case and additional descriptive summaries were added. An
independent arithmetic check reproduced every IQR and deletion-range endpoint.
The final verification receipt records file bindings, manuscript/supplement
builds, visual inspection and the scope of the review. Accepted primary
analysis receipts and source hashes remain unchanged.
