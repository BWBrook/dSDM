# dSDM: Fresh-Task Handover

Prepared for Barry Brook's successor research collaborator, 2026-09-05.
Repository: `/Users/bwbrook/papers/dSDM`. Original handoff followed `8be8ec6`;
execution status was refreshed on 2026-09-08 for the move from Mac production
to resized Nectar at Barry's request.

## Current handoff — 14 November, final figure corrections

Claude reviewed the reconstructed displays in thread 162/message 3380 and
added the near-chance mainland transfer result in `803860d`. The mean AUCs
(0.5560/0.5715/0.5837) and conventional-model ranking match accepted evidence.
That Results/limitations wording is retained.

Figure 4a now gives development, SEH and NNC separate labelled vertical
scales while retaining every species point and the accepted means/ranges.
Its caption identifies the differing scales. Figure 4b's legend has its own
row. Figure 2's regional values sit adjacent to their points, with the
within-bioregions-and-folds label corrected. Figure 1's duplicate footnote
is removed. The caption calls the grey mammal extent a mainland subset of
the bird domain: the bird domain extends beyond it to complete BBS, so the
two mainland boundaries are not identical.

An independent read-only check accepted the revised figures/captions and
mainland wording. `make -C manuscript all check` passes. The rebuilt article
is 24 pages; the three affected figure pages were inspected at page size,
with no clipping, overlap or missing glyph warnings. Supporting information
sources and PDF/Word outputs match the previously checked 36-page build.
The paper is ready for Barry's final read.

Current verification is
`evidence/reconstruction/20261114/figure-revision-verification.json`, with a
fresh design-figure receipt beside it. Earlier dated evidence remains intact.
Outputs are `manuscript/build/dsdm_manuscript.pdf` and
`manuscript/build/dsdm_supplement.pdf`. No release or submission was made.

## Historical handoff — 13 November, reconstructed displays and Supporting information

Claude integrated the full-draft review and assembled the reconstructed
Ecography manuscript in `f62df73` (thread 162/message 3365). Figures 1–4 now
follow the accepted display plan: public boundary/design map, paired
pretraining gains, new-region learner/ensemble comparisons, and negative
evidence. Vector PDFs and 300 dpi PNGs are in `manuscript/figures/`; the four
new captions replace the old three in `manuscript/text/figures.md`.

Accepted species aggregates supply all displayed values. The reporting
extension uses 100,000 paired species draws, reproduces earlier primary-bird
ranges and adds within-region/fold, ensemble and common-panel richness
ranges. These describe species composition conditional on fitted models.
No refitting, raw observations or saved row-level predictions were used.
The seven small figure-data tables, source hashes and replay records are in
`evidence/reconstruction/20261113/`.

Supporting information preserves S1–S11 and adds all-case TSS, extended
ranges, the former main Table 2, five-endpoint learning/control details,
absolute AUC by extent and per-species contrasts. Internal table numbering
is retained; main-text citations say Supporting information. Table 1's 27
AUC values are unchanged; shorter labels, explicit column widths and a real
table caption keep it together on one page. Intended Markdown lists now
render as lists, and AI disclosure records the new display/SI work.

The profiles now identify Ecography and use its official independent Oikos
CSL parent, which prints full author lists. A local manuscript environment
with pinned PyYAML and separate per-profile caches resolves the build issue
without changing system Python. Both article and SI PDF/Word builds and
checks pass; PDF inspection covers all pages, with detailed checks of the
new displays and tables. Outputs are in `manuscript/build/`.

See `docs/audits/reconstruction-displays-20261113.md` and
`evidence/reconstruction/20261113/assembled-display-verification.json` for
bindings, checks and remaining release work. Claude should review the
assembled figures/SI and their integration before Barry's final read.
No public release, DOI assignment, correspondence export or submission was
made in this tranche; the reviewed correspondence snapshot remains release
preparation.

## Historical handoff — 13 November, full-draft review

Claude adopted the paragraph review in `6a5be86` and wrote the full
reconstruction draft in `8b55501`, requesting review in correspondence
thread 162/message 3360. The
[step-3c review](docs/audits/reconstruction-step3c-review-20261113.md)
keeps the lean draft and supplies targeted factual, interpretive and
presentation repairs. Table 1 in `03c-full-draft.md` is completed with all
27 AUC values across nine case/assessment rows; its values are also retained
in `evidence/reconstruction/20261113/table1-performance.csv`.

The principal design repair is that bird learning curves used five endpoints,
not a full 3×3 factorial. Other corrections distinguish the Tasmania fixed
categorical schema/support masks, 606 observed response cells from patch
geometry, quarter-data training support per held fold, and the directly
rounded −0.0067 Tasmania development contrast. The evidence record is
`evidence/reconstruction/20261113/full-draft-review.json`. Restore the
four-figure/one-table plan by moving or collapsing the three new small tables.

Only Table 1 was edited in the draft; other prose changes are proposals in
the review. `main.md` and `refs.yaml` remain unchanged. No models were fitted
or raw responses accessed. Claude should integrate the repairs and assemble
the article with the seven verified references before the final author read.

## Historical handoff — 13 November, paragraph-abstract review

Claude adopted the section-abstract review in `8c24ef2` and drafted the
31-paragraph framework in `6b52446`, with a review request in correspondence
thread 162/message 3356. The
[step-3b review](docs/audits/reconstruction-step3b-review-20261113.md)
retains the order and budget, supplies affected paragraph replacements, and
verifies the eight proposed references. Seven can be added with scoped uses;
Araújo & New 2007 already exists. The metadata record is
`manuscript/references/reconstruction-reference-check-20261113.json`.

The principal repairs are that masked unknowns are not a negative class, the
extent comparison does not identify a fraction of transfer loss, and the
near-zero bird mean is not exact equivalence. The numerical and format checks
are in `evidence/reconstruction/20261113/paragraph-review.json`. The active
reconstruction files, article and bibliography remain unchanged by this
review. No models were fitted or raw responses accessed. Claude should
integrate the paragraph and citation corrections; Barry returns at the final
draft under his latest relayed instruction.

## Historical handoff — 13 November, section-abstract review

Barry approved the average-based main-message revision and, as relayed in
correspondence thread 162/message 3348, wants the agents to iterate on the
intermediate reconstruction stages; he returns at the final draft. Claude
adopted the step-2 repairs in `488263e` and drafted the four section abstracts
in `0cdc4c7` (`manuscript/reconstruction/03a-section-abstracts.md`).

The [step-3a review](docs/audits/reconstruction-step3a-review-20261113.md)
verifies the frozen-encoder gain, richness gradient and Tasmania sensitivity
against accepted aggregate outputs. It supplies complete replacement sections
of 280/299/256/295 words. The substantive repairs separate evaluation changes
from retraining, specify full-data mean AUC, preserve ensemble provenance, and
replace a claimed order of modelling investment with a recommendation to test
complementary learners alongside auxiliary-pool size. The numerical record is
`evidence/reconstruction/20261113/section-review.json`.

The active reconstruction drafts and `main.md` remain unchanged by this review.
No models were fitted or raw responses accessed. Claude should integrate the
corrections and continue expansion; no fresh human approval is required for
this intermediate stage. The earlier dated reviews are retained below.

## Historical handoff — 12 November, reconstruction review

Barry resumed reconstruction of the paper's logic with Claude and asked Codex
to critique the three files in `manuscript/reconstruction/`, before changing
`manuscript/text/main.md`. Claude's brief is correspondence thread 162,
message 3325; the reviewed source commit is `e9a5a35`.

The [reconstruction review](docs/audits/reconstruction-review-20261112.md)
retains the five-item display plan and supports Ecography, while correcting
the blanket a-priori label, H2's comparator, the claim of area matching and
the universal/mechanistic reading of the transfer result. The matched bird
pretraining gain rises from +0.0058 at full target data to +0.0095 at quarter
data. Primary case means and counts were independently recomputed from the
tracked species aggregates; bindings are in
`evidence/reconstruction/20261112/numerical-review.json`.

Claude revised steps 1 and 2 in `14214c8`/`a8721e9`. The
[convergence check](docs/audits/reconstruction-convergence-20261112.md)
accepts the argument and display plan, verifies all abstract numbers, and
supplies a 584-word one-page proposal. Four textual repairs remain: do not
extend bird borrowing strength to the non-strict historical mainland ladder;
distinguish the prespecified exploratory ensemble; describe subsampling
rather than natural scarcity; and remove an unsupported universal priority
claim. Claude can apply these corrections and send the reconstruction to
Barry without another analysis tranche. The abstract remains 149 words with
the proposed substitution.

This check leaves the three active reconstruction drafts and `main.md`
unchanged. No new fits or raw-response analyses were conducted. Release
preparation is separate:
the repository is now public, the manuscript's private-repository wording is
stale, and the reviewed public correspondence export is not yet configured.
The 18 October records below describe their historical states.

## Historical handoff — 18 October, complete manuscript rewrite and Claude review

Barry authorised substantive drafting for both an informed generalist editor
and specialist readers, superseding the 11 October prose hold. The complete
rewrite, expanded supplement, three figures and two main tables are in
`manuscript/`. The working title is **Does learning from other species improve
species distribution models in new regions?**

Three complete-draft review rounds with Claude are recorded in correspondence
thread 32, messages 1875/1880, 1882/1883 and 1887/1888, and in
[the drafting record](docs/plan/ManuscriptDrafting-20261018.md). The central
argument now distinguishes the performance of a neural predictor from the
increment due to pretraining. Held-region bird AUC exceeded conventional
learning by +0.0028 with fine-tuning and +0.0032 with target-only learning;
most ensemble gains were also available without pretraining. Extent and
negative-class diagnostics change the interpretation without identifying
causal mechanisms. Tasmania's AUC and co-primary TSS conclusions remain
distinct.

Numerical claims were checked against accepted aggregates. Six close literature
precedents and dataset references were checked against primary sources.
Supplementary Methods S3/S4 and Tables S10–S11 now incorporate the post hoc
survey-only results and source provenance. No models were fitted or raw
responses reopened for this drafting task. Historical scientific receipts and
the prior manuscript outputs remain preserved.

Barry's subsequent editorial reading requested a humanisation pass without
losing context. The abstract, framing and Discussion now give the ecological
motivation and empirical contribution more room, while consolidating repeated
caveats. An independent scientific review checked that revision. Barry then
resumed the exchange with Claude, whose fourth review (message 1972) identified
internal terminology and numerical density as the remaining prose problems.
The latest revision simplifies those terms, leads Results with the findings,
and preserves the displaced absolute AUCs in new Table S1f. It corrects the
Norberg et al. framing against the primary paper and adds a scoped explanation
of the frozen-encoder development result. All original citation keys and
accepted analysis sources remain unchanged. Current verification is
`evidence/cross_case_synthesis/20261018/claude-round4-verification.json`;
earlier draft records and outputs are preserved. Barry will resume either
collaborator asynchronously; do not try to wake the desktop apps.

Claude's final verdict (message 2006) accepts the draft for both audiences and
the retained scientific qualifications. Jessie C. Buettel is now included in
the draft author list, using her current official ANU affiliation. Both camera
data custodians and their institutional contacts are named. The expanded AI
disclosure distinguishes Codex's implementation from Claude's diagnostic
calculations and criticism, preserves known model labels, and avoids assigning
all scientific decisions to the human authors. The two final clarity repairs
are integrated. Current document verification is
`evidence/cross_case_synthesis/20261018/final-statements-verification.json`.

A local correspondence review package is in
`outputs/correspondence/dsdm-20261018/`: one complete dSDM discussion, 46 messages
through 2006, with no message-text redactions. It preserves original labels,
model metadata where present, timestamps, reply links and corrections. It is
the shared board record, not every private app chat. It remains outside Git
and has not been published. Zenodo is not signed in and no DOI is assigned.
The [publication preparation record](docs/plan/PublicationPreparation-20261018.md)
documents scope, sources and the remaining deposit steps.

The manuscript and archive are ready for Barry's and Jessie's final read.
Public release/submission remains subject to that review. Deposit identifiers
and journal/style remain to be completed. Missing ALA snapshot DOIs and the
legacy Tasmania predictor lineage are disclosed as limitations rather than
filled with guessed metadata. The current global instructions govern new
reversible work; old drafting-scope statements do not reinstate approval gates.

## Historical handoff — 11 October, survey-only review follow-up complete

Barry requested that Codex address Claude’s correspondence review (message
1403). The post hoc survey-only evaluation is complete using the already-closed
predictions, all eight species, seven endpoints and three methods. It retains
all 1,300 held presences and 242 survey-supported negatives, excluding 130
constructed pseudoabsences. No new fits, model selection or threshold changes
were made. Nine tests, exact idempotent replay and independent recomputation
passed; all 336 paired performance rows and 672 contrast rows matched exactly.

The result materially qualifies the mixed-panel finding. Removing training
pseudoabsences raises full-data mean survey-only AUC for all three methods:
target-only 0.8403 → 0.8587, fine-tuning 0.8352 → 0.8572 and conventional
0.8198 → 0.8385. Fine-tuning remains slightly below target-only by AUC, but
retains positive TSS/MCC contrasts; it exceeds conventional learning on all
three mean metrics. This is a post hoc source-conditional result, not evidence
of true absence, occupancy or a learned construction mechanism. Wombat retains
only seven survey-supported negative rows.

Read [the review response](docs/plan/ClaudeReviewResponse-20261011.md) and the
[two-page paper plan](docs/plan/PaperPlan-20261011.md). Numerical evidence and
independent audit are under `evidence/tasmania_pseudoabsence/20261011/survey-only/`.
The next step is Barry’s agreement on the headline, four lessons and main-text
allocation before a focused rewrite. The manuscript body remains the working
synthesis; the new panel has not been added as another Results subsection.

The prior analysis and manuscript delivery were committed and pushed as
`6e4df9f`. Its receipts retain their original bindings. Only the current
handover and manuscript README advance beyond those document hashes; all
prior scientific outputs and manuscript builds remain intact. Earlier
handoffs below describe their historical states.

## Historical handoff — 9 October, Tasmania sensitivity complete

All seven approved endpoints are complete: **8,125 production fits, 14 smoke
fits and 200 exactly recovered auxiliary states (8,339 physical fits)**.
The unchanged 1,672-row held panel was scored once after prediction closure.
Independent replay passed all 4,800 production leaves, 168 thresholds and
performance panels, 24 full-data map comparisons, primary reconciliation and
exact Thylogale negative controls. No fitting or scoring remains to run.

Read [TasmaniaPseudoabsenceResults-20261009.md](docs/plan/TasmaniaPseudoabsenceResults-20261009.md)
for the verified findings and manuscript, supplement and map links. Removing
training pseudoabsences reduced full-data mean AUC for all three methods,
with the largest losses in *V. ursinus* and *D. maculatus*. Fine-tuning minus
target-only mean TSS changed from +0.0477 to −0.0182, whereas fine-tuning kept
a TSS advantage over the selected conventional learner. These changes are
conditional on the original evaluation-source mixture; they do not validate
pseudoabsence truth or mapped occupancy.

The 18-page manuscript and 15-page supplement have been updated in PDF and
Word, with Tables S5–S9 and eight separate map plates. Final verification is
in `evidence/tasmania_pseudoabsence/20261009/delivery-verification.json`.
The [execution record](docs/plan/TasmaniaPseudoabsenceExecution-20261009.md)
links the completed gates and preserved zero-fit launcher failures. The
[approval](docs/plan/TasmaniaPseudoabsenceRecoveryApproval-20261009.md)
remains the scope authority. No new commit, push or submission accompanied
this delivery. Earlier handoffs below describe their historical states.

## Historical handoff — 8 October, all-endpoint Tasmania sensitivity approved

At 23:28 AEDT, Barry instructed **“All seven endpoints. Proceed.”** The
protocol-wide sensitivity is now authorised. Its scope and execution gates
are recorded in
[TasmaniaPseudoabsenceSensitivity-20261008.md](docs/plan/TasmaniaPseudoabsenceSensitivity-20261008.md).
All 56 species–endpoint combinations retain their original evaluation rows,
with pseudoabsences removed from target training only and sensitivity-specific
OOF thresholds. The planned inventory is 8,125 production fits plus 14 fixed,
non-promotable smoke fits; the map comparison remains 24 full-data pairs.

The source census passes: all 336 original endpoint membership digests match,
and all 896 separate roles retain both classes. Eight focused tests and an
independent reconstruction of all memberships, counts and set hashes pass.

Fitting is awaiting a specific amendment: Goal035 preserved the 200 required
inner multi-head state hashes and epochs, but no weights. The
[availability audit](docs/plan/TasmaniaAuxiliaryAvailability-20261008.md)
proposes 200 replay-only reconstructions at the original epochs, requiring
exact original state and prediction hashes, with no new discovery or `q`
fitting. This would bring execution to 8,339 fits including the fixed smoke.
The approved proposal expressly prohibited auxiliary refitting, so this
amendment has been put to Barry and remains pending. No sensitivity fit,
reconstruction fit or new held-response access has started. Earlier endpoint
scope-pending statements below are historical and are superseded by the direct
all-endpoint approval; the recovery amendment is the current decision.

## Historical handoff — 8 October, bird composition ranges added

Barry asked Codex to respond to Claude's latest review. Read
[CrossCaseFollowup-20261008.md](docs/plan/CrossCaseFollowup-20261008.md) for the
response, numerical table and remaining scope choice. The primary 73 bird
species now have central 95% species-composition resampling ranges from
100,000 paired draws, with the ten-focal-block inner width check in the
supplement. These are finite-panel reweighting diagnostics, not confidence
intervals or fitting, spatial-sampling, selection or population uncertainty.
Figure 1 retains all species points and adds ranges only to bird means.

The inner target-only range is **[+0.005040, +0.006608]**; its equal-region
outer counterpart is **[−0.004063, +0.003389]**. Conventional-comparator ranges
are **[+0.002873, +0.003911]** inner and **[−0.001683, +0.007188]** outer. The
block check narrows one inner range and widens the other; computational blocks
do not remove all dependence. The original estimates and prior aggregate
receipts remain unchanged.

New results and verification are in `evidence/cross_case_synthesis/20261008/`;
the plan was fixed before these reporting calculations. Three focused tests,
deterministic reproduction and an independent 12-endpoint numerical check
pass. Current PDF/Word outputs are a 17-page manuscript and seven-page
supplement, with Figure 1 and Tables S1d/S1e updated. The workspace remains
uncommitted beyond opening-record commit **4d2a024**; no push occurred.

Claude's message 1167 relays Barry's agreement to run the Tasmania sensitivity.
The direct endpoint-scope question remains pending in Codex: recommended
full-data-only **1,122 + 14 smoke fits**, or all seven endpoints **8,125
production fits plus smoke qualification**. No sensitivity implementation or
fit has started. Do not infer a chosen endpoint scope from the relay. The
reviewed training-only contract and pre-run scientific checks remain in force.
MEE is a reasonable working target; final formatting/submission is still open.

Correspondence task checkpoint: thread 32, through/next_after **1168**,
message **1167** read in full. Shared read markers were not advanced over
earlier unread messages. Codex's response is message **1171**, posted at
23:00:13 AEDT on 8 October. The read checkpoint remains before that own reply.

## Historical handoff — 5 October, manuscript review revision complete

The revised review draft and supplement are complete. Read
[CrossCaseRevision-20261005.md](docs/plan/CrossCaseRevision-20261005.md) for the
response to Fable and the revised descriptive results. The active sources are
`manuscript/text/main.md`, `manuscript/text/figures.md`, and generated
`manuscript/text/supplement.md`. Verified outputs in `manuscript/build/` are the
17-page manuscript and six-page supplement, each in PDF and Word format.

The revision restores the five-species mainland inner result: fine-tuning
minus target-only AUC **+0.008745** (4/5 positive), and minus conventional
**+0.003950** (5/5). These gains precede the heterogeneous mainland-to-Tasmania
transfer result. It also adds the bird regions' designed roles and external
50-km buffers, the sparse-third result, inner recorded-richness diagnostics,
network and conventional-grid details, and the target-only versus tuned-ANN
comparison. The abstract is 204 words and the bibliography now has 17 verified
cited works. Original Tasmania AUC and TSS retain their co-primary status and
their differing conclusions.

Figure 1 and Table S1 cover six headline assessments with all species points,
means, medians and IQRs. Single-species deletion ranges describe composition
sensitivity; they are not confidence intervals. The original synthesis files
are preserved. New reporting outputs and the verification receipt are in
`evidence/cross_case_synthesis/20261005/revision-01/`. Accepted numerical inputs
are unchanged; all 280 earlier case-summary fields reproduce exactly. Both
document builds, citation resolution, reporting reproducibility and visual
inspection of all 23 PDF pages pass. The initial synthesis's 12 core tests
remain separate evidence; this revision did not rerun fitting or scoring.

The original Tasmania opening records are committed as **4d2a024**. Manuscript,
supplement and reporting changes remain local and uncommitted; no push or board
message was sent. Do not reopen the primary test or rerun its `score` command.

The prespecified pseudoabsence-removal question remains unrun. The independently
reviewed [proposal](docs/plan/TasmaniaPseudoabsenceSensitivityProposal-20261005.md)
is ready for Barry's decision: the recommended full-data option requires
**1,122 production fits plus 14 smoke fits**; all seven endpoints require
**8,125 production fits**. The full-data option leaves reduced endpoints
untested. Training-only removal, new OOF thresholds and map comparisons are
explicit post-opening implementation choices. Approval of that scope must
precede implementation and the source census, independent implementation review
and smoke qualification required before production. The optional survey-only
evaluation view is excluded by default. No sensitivity fit has been launched.

Journal choice also remains open; Methods in Ecology and Evolution is Fable's
recommendation, while the existing CSL is a placeholder. Author metadata,
complete data/species/predictor citations and release conditions remain
submission work. Neither this revision nor the proposal is submission or
production qualification.

## Historical handoff — 5 October, synthesis and original Tasmania test complete

Barry approved cross-case synthesis, manuscript restructuring and opening the
original Tasmania held-patch test. Read
[CrossCaseResults-20261005.md](docs/plan/CrossCaseResults-20261005.md) for the
combined result, including the reproduced bird extent check, the target-only
ensemble and the SEH negative tail. The active manuscript is
`manuscript/text/main.md`; its evidence ledger records claim sources and work
remaining before submission. The review draft builds to 14-page PDF and Word
with two verified figures in `manuscript/build/`.

The original Tasmania test was opened once and completed at **14:05:35 AEDT**.
Its aggregate receipt is
`evidence/tasmania_outer_assessment/20261005/receipt.json`, SHA
`3e7fe324b33450b76089edca0f2d5bf438d219121c9c0842961fedcd9695be26`.
It contains all eight species, seven endpoints and 11 methods, scored over
1,672 response rows in 606 cells: 3,696 metric records and 2,016 contrasts.
Native validation and independent pre-opening review passed on the archived
Goal037 source, followed by an independent aggregate arithmetic/privacy audit.
No model was refitted. The historical Goal037 zero-access receipt remains
unchanged; the new receipt records the authorised opening. Do not rerun `score`.

Original Tasmania full-data fine-tuning minus target-only **AUC** has mean
**−0.014741**, median **−0.012001**, with **1/8** species positive. Co-primary
**TSS** at frozen inner thresholds has mean **+0.047653**, median **+0.020514**,
with **5/8** positive, one tied and two negative. Preserve both metrics. This
is descriptive interpolation in touching patches, not independent regional
transfer. The protocol's pseudoabsence-removal sensitivity is still unrun.

The bird post hoc reproduction passes all **2,870** defined saved-arm X10 AUC
comparisons exactly. Fine-tuned inner AUC is **0.689709** within region-by-fold
strata, with a target-only contrast of **+0.007244** (68/73 positive), versus
outer **−0.000396** (34/73). The extent comparison does not identify a
geographic penalty. The outer target-only/conventional ensemble gains
**+0.009621** over conventional, versus **+0.010352** for the fine-tuned
ensemble; their difference is **+0.000732**, with 37/73 species positive.

The synthesis uses unchanged accepted results and explicit post hoc reporting.
Twelve focused tests pass, the manuscript build and visual review pass, and
`evidence/cross_case_synthesis/20261005/verification.json` binds the final
sources, results and review outputs. Dataset citations, release conditions,
the detailed supplement, author metadata and journal style remain submission
work. No additional fitting or scientific redesign is authorised by this
closeout.

## Historical handoff — 5 October, bird outer assessment complete and verified

The complete retained-full outer assessment is now returned and checked.
Read [OuterResults-20261005.md](docs/goals/052-seawfb-dsdm-experiment/OuterResults-20261005.md)
for the scientific result and its diagnostic appendix for exact support sets.
The final acceptance receipt is
`evidence/seawfb_dsdm/goal052/outer-acceptance-20261005.json`; archived review
sources/results and the byte-identical native report are in
`evidence/seawfb_dsdm/goal052/outer-review-20261005/`.

All **4,242 fits** completed and the independent pre-opening audit passed.
The score/reporter stages then succeeded. Verified return completed at
**11:54:09 AEDT**: all 157 prediction files, 185 data/receipt files and
26 controller files checked. All 29 frozen scientific source hashes and the
original closure remain unchanged. A live check at 11:53:44 found no campaign
fitting, scoring or report process on Deep.

The result is descriptive: primary fine-tuning minus target-only network AUC
**−0.000396** (34/73 positive), and minus selected conventional **+0.002771**
(39/73). The conventional comparison is positive in NCP/NNC and negative in
SEH. The fixed exploratory ensemble gains **+0.007582** over fine-tuning and
**+0.010352** over conventional. High-richness comparisons decline in SEH and
NNC; NCP has no reportable 100+ background bin, so the three-region diagnostic
is NA. No occupancy, causal mechanism or inferential significance is established.

All-target aggregation/richness checks pass. Independent raw-response
reconstruction for three prospectively chosen species across all regions and
X10/X20 passes **2,268 field comparisons**, maximum error **2.44e-15**.
Original threshold metrics retain their frozen OOF thresholds.

Authoritative private completion is run
`postproduction-control-005/return-complete-006.json`, SHA
`287894aa6d38f0b38c545b9c720ce21a28059451f06be795e230abb48577a143`.
The score SHA is
`3a81b166f95551afc199577b86c200bf8cc6f91a24289ec5ad5583a9421f4a41`.
The old `postproduction-control-005/complete.json` deliberately remains failed:
it recorded a report-completion polling race. Both successful stage receipts
and the separate return-only receipt resolve it without recomputing scores or
regenerating the report. Preserve all prior failure/access/recovery evidence.
Do not relaunch old controllers. Full fitted models remain under the isolated
Deep export `/data/codex/repos/dSDM-outer-20261003-r2/`.

The next scientific discussion can use the completed outer report. No board
message, new fit, revised threshold, model selection or scientific redesign
has been initiated. The generic completion-poll race is a future engineering
repair before another campaign; this run is closed through verified receipts.

## Historical handoff — 5 October, audit passed; scoring-only loader recovery

All **4,242 fits** completed on Deep: 10 q, 50 pretraining, 3,140 neural and
1,042 conventional. Attempt `002` finished the remaining fitting stages in
12 h 18 min. Native closure and verification succeeded at **01:36:48 AEDT**
on 5 October, with closure SHA `aa5b7949cd0c76bb324edde55d5209e0fbf8447b9e00f45a0efa5850ce185063`.

The independent audit then stopped at `canary_repeat_drift`, before response
access. Its comparison had omitted the already-accepted serialization-size
exclusion: among 24 actual canary repeats, only ANN `model_size_bytes` differed
after existing timing/process exclusions. Every numerical field, prediction
digest and fitted-state digest is identical. Preserve the failed continuation
`002`, its audit, and the archived original auditor source.

The bounded repair excludes that resource field and explicitly requires a
valid ANN state digest in every repeat. Six focused tests, 12 auditor self-test
cases, actual saved qualification validation and independent review passed.
Commit **d63e938** and `outer-audit-repair-validation-20261005.json` bind the
repair. No fitting source, plan, fitted model, prediction or closure changed.

The fresh **audit-only** execution passed at **10:39:21 AEDT**. It verified all
4,242 fit receipts, 17,060 closure files and 4,182 seed score files, recomputing
the six learner means and fixed ensemble for all 157 targets. It hashed
92,243,220,254 bytes and confirmed absence of response access and scoring.
Audit receipt SHA is
`394dc0e64219fba0f85d795c337a2e623d2d5cfd907f13c0bd559e4c9e4c61ef`.
The parent and independent reviewer checked its exact run/source/plan/closure
bindings. Original failures remain preserved.

The independently reviewed manual scoring launcher first wrote a complete
opening-gate receipt at **10:42:51 AEDT**. It then hashed and transferred the
canonical responses, matching the frozen source checksum. **The response seal
is now open under the existing authority.** Native scoring launched at
**10:43:04 AEDT**, leader PID **582322**, and re-verified closure. It then
stopped at `active_species_count_drift` after reading the canonical file.
The local return process also stopped. Preserve the failed score controls and
the original `response-access.json`; no success receipt or scores were written.

The original Goal049 input validator passes on all frozen metadata, 505 exact
checkpoint/receipt pairs and all 5,048,061 canonical memberships. Its active
registry and effort-donor universe contain **505** species, including **56**
with empty cell lists. The sparse canonical file therefore contains **449**
distinct species. Goal049 deliberately counts all 505 while omitting empty
species from its serialized rows. All 505 active taxa are donors, and none of
the 56 empty taxa is among the frozen 157 scoring targets. Independent review
confirms a loader count-semantics error, with no change to responses, richness,
panels or the frozen scientific definitions.

The separate scoring-only recovery is now validated: **33 tests pass**, the
actual metadata/prior-access checks pass, and independent review supports the
exact attempt-005 launch. `outer-score-recovery-entrypoint-validation-20261005.json` binds
the helper, launcher, finisher, certificate, original audit and failed access.
It retains the complete 505 donor universe and uses the unchanged native
response-array and scoring calculations.
Attempt004 stopped immediately on an import error before closure verification
or response reading. Its failure evidence is preserved. Two misplaced helper
imports are corrected; real-module entrypoint tests and an exhaustive imported-
symbol check now pass. The 29 frozen source files, plan, fitted models,
predictions and closure remain
unchanged. No model outcome has been computed or examined. Do not rerun the
failed scorer or overwrite its evidence.

Remote postproduction state is outside the closed run at
`/data/codex/repos/dSDM-outer-20261003-r2/postproduction-control-003/`.
Local launch, opening, transfer and audit evidence is under the run's
`postproduction-control-003/`. The reviewed recovery launched at **11:24:49 AEDT** in fresh
`postproduction-control-005/`, leader PID **597547**, with a 12-hour cap and
its own new `recovery/` child outside the closed run on Deep. Its Python
process is live and re-verifying the complete closure. The local finisher is
waiting to render and hash-check the report and returned artifacts. Preserve the original access receipt and failed attempt.
Do not retry attempt003 or change any frozen scientific source, plan, fit,
prediction, threshold or panel after opening.

## Historical handoff — 4 October, outer production resumed

At **12:32 AEDT**, actual Deep qualification is complete. The full-row profile
finished at **20:59:54 AEST on 3 October**, after 3 h 17 min. Peak RSS was
4.09 GiB; qualification allowed 22 workers and live-memory headroom selected
**20**. Production began at 21:00 AEST.

All **10 q models converged and were saved**, but the stage exited at
**23:47:37 AEST** because its final logging call supplies `stage` twice:
`event("stage_complete", **result)`. The continuation stopped as designed.
No pretraining or target production fit started. No closure, response-access
receipt or outer score exists. The original failed controls are preserved.

`outer-production-stop-20261004.json` records native validation of all ten
returned q leaves, including model and receipt hashes, convergence, parameters,
seeds and the unchanged 29 source / 22 input bindings. The same validation
passed on Deep. Independent review supports an operational handler restricted
to this exact terminal logging exception, followed by complete stage-artifact
validation. Recovery now passes 31 focused tests, the actual Deep read-only
restart preflight and a copied-q smoke that reused all ten fits in 28 seconds
without changing any saved byte. Independent review finds no material blocker
to manual attempt `002`; `outer-restart-validation-20261004.json` binds the
tested helpers and receipts. Recovery is committed and pushed as **9621dc6**.
The fitting code, plan, runtime qualification and saved q fits remain unchanged.

The continuation resumed at **12:51:07 AEDT**, local PID **16370**, using
`--attempt 002 --restart-from 001`. The Deep supervisor is PID **203393**.
Its q stage passed in **27.8 seconds**, retaining all ten original fits without
refitting, and pretraining began at **12:52:00 AEDT** with **20 workers**.
Actual fit-start records and a live, guard-clear heartbeat confirm pretraining
is running. Local state is `continuation-control-002/`; the new launch receipt
is `continuation-launch-002.json`. Remote production receipts are under
`production-control-002/`. Keep all `001` failure evidence and do not relaunch
either live controller.

The existing 72-hour production and 84-hour continuation caps remain. After
all fitting stages, the controller still requires native closure/verification
and the independent response-free audit before response transfer and scoring.
Large models remain on Deep; compact results and the report return locally.
No closure, response-access receipt or outer score exists at this handoff.

The full-row profile gives a **14.4-hour planning estimate** for the remaining
three fitting stages at 20 workers, excluding closure/audit/scoring and subject
to concurrent throughput. This is not a completion promise. Barry's existing
authority and the prediction-before-response gate still apply. Fable's next
input follows the outer scores; no board acknowledgement is needed.

## Historical handoff — 3 October, outer continuation running

Fable's message **839** accepts the scientific corrections and needs no reply
or further review before outer scores unless implementation changes a fixed
definition. Barry explicitly instructed Astra to proceed. Task retrieval cursor
is **845**. The next substantive board contribution is the outer assessment.

The retained-full implementation is in `src/dsdm_phase1/goal052_outer*.py`.
`OuterImplementation-20261003.md` records full-fold seeds, fixed-budget replay,
staged q scaling, fitted-state preservation, prediction closure and scoring.
It consumes the accepted 80 ANN budgets and enumerates 4,242 fits. All 144,860
outer predictor rows retain the native float64 transform before any neural
float32 conversion. Synthetic tests cover native replay, data rules, exact
model reloads, closure corruption, fixed thresholds and runtime qualification.

Actual retained-data preparation, host profiling and production are the current
engineering work. Deep is available (64 logical CPUs, about 123 GiB available
memory at 17:32 AEST). Use an isolated source export there; preserve its older
checkout and recovery evidence. The runtime supports CPU only. Test 24 actual
single-thread worker processes, then choose production concurrency from the
full-row memory/runtime profile. The initial profile has a six-hour cap and a
16 GiB host available-memory floor. Do not promote profiling fits to production.

The initial Deep canary stopped before profiling because ANN serialized file
sizes differed by 12 bytes between processes. A 24-process diagnostic reproduced
only that storage-size difference; every recorded numerical comparison matched.
Preserve the initial plan `8ec8e7ce...` and its failed receipts under
`outer-assessment-20261003`. The repaired comparison excludes serialized size,
retains exact prediction/state checks and adds an explicit ANN weight digest.
The fresh run is `outer-assessment-20261003-r2`, on the separate Deep export
`/data/codex/repos/dSDM-outer-20261003-r2`. No production fit ran in attempt 1.

Replacement plan **4b179d6c...** binds scientific source **8f33704**. Its actual
24-process canary passed exact numerical/state/reload comparisons in 17.16
seconds. The full-row profile began at **17:42 AEST** and remains active as of
20:13, within the six-hour cap, using one CPU core and about 1.9 GiB RSS. The
final runtime qualification receipt and production allocation are still pending.

The bounded production supervisor and score-report renderer are committed in
**4eb0448**; 16 focused tests passed. The independent response-free closure
checker is committed in **aeaa9f9**. Its synthetic valid/failure checks pass,
and it independently reconstructs every actual task and threshold in the plan.
All operational helpers are staged on Deep with verified hashes; the 29 frozen
scientific sources are unchanged. The independent checker now also rejects any
pre-existing native response-access receipt (commit **260a946**).

The one-shot continuation (`scripts/goal052_outer_complete.py`, **deef6fb**)
was launched locally at **20:13:08 AEST**, PID **84576**, with its idle-sleep
inhibitor **84577**. Its preflight passed and live heartbeat is **runtime_wait**.
It waits for successful actual qualification, selects at most 24 workers from
measured peak memory and live RAM, then dispatches the bounded production
supervisor. It requires all six stages, native closure verification and the
independent audit before transferring canonical responses and invoking scoring.
Production is capped at 72 hours; the continuation is capped at 84 hours.

Local state is under the r2 run's `continuation-control-001/`; the launch receipt
is `continuation-launch.json`. Do not relaunch or create another attempt while
this process is active. The program returns the final predictions, scores,
`outer-report.md` and compact, hash-verified evidence. Full fitted models remain
on Deep. A failed gate stops continuation without automatic refitting.

Tracked `outer-continuation-validation-20261003.json` records 20 focused tests,
the independent code review, and harmless Deep launcher/timeout smoke checks.
Those checks validate the operational code; the actual 4,242-fit chain has not
yet completed. Before interpreting any returned score, verify final completion,
all production/audit bindings, both native response-access receipts and their
linkage, both response-transfer copies, and the returned-file hashes. The
independent review also passed 19 native contract tests and eight auditor
self-test cases. No further scientific definition changed.

**No outer response rows have been opened.** Complete and independently verify
all fitted models, component seed averages, ensemble predictions and threshold
bindings before the scoring entrypoint can load responses. Existing opening
and compute authority applies. No recurring monitor is configured; the running
continuation is one bounded campaign.

## Historical handoff — 2 October, scientific follow-up and all ANN budgets accepted

Fable's message **810** withdraws the mechanism claim, architecture/PCA bounds,
rough ceiling and interpretation of the proposed richness-covariate experiment.
The agreed later order is observation-aware independent evaluation (with an
early known-truth simulation), richer habitat inputs, then same-input learners.
No new simulation, observation-covariate or architecture experiment was launched.

`RecordedRichnessFollowup-20261002.md` verifies the matched FT/target-only
comparison on 142 targets: +0.005336/+0.003421/−0.002110 across background
richness 10–24/25–99/100+, with 139/123/69 positive. It holds architecture and
inputs fixed but does not identify the transferred ecological/observation
mechanism. Preserve the 59-primary/83-other split: the other 83 have a negative
high-richness mean (−0.000580) but a positive majority (47/83), a mixed direction.
The conventional-family and ensemble tables also reproduce.

Fable's 151-target reporting-rate medians reproduce exactly to his rounding
when the reference is the highest **nonempty top-score bin**. Contrary to his
statement that every target uses 200+, 92 use 100–199 and 65 use 200+. Six of
the latter have zero focal records among only one or two reference cells each;
these small denominators give little independent evidence of habitat confounding.
The literal fixed-200+ rule has only 59 defined ratios. Preserve both calculations
and the original 1 October review. All diagnostics use retained inner data.

`OuterDiagnostics-20261001.md` now also specifies background counts/shares beside
each regional headline, with equal species weighting and explicit target-cell
pair counts. Its scoring tests cover sparse/empty bins and unequal target
counts. No mask, model, primary contrast, support gate or threshold changed.
Fitted target weights were not saved in the inner artifacts, so Fable's proposed
fold-model/full-model comparison on a common grid needs additional replay fits.
`OuterPreparation-20260929.md` records this limit; fixed OOF thresholds remain.

All **80 conventional ANN epoch budgets** (40 targets × ordinary/q_full) are
accepted in tracked `ann-recovery-review-20261002.json`. Independent reconstruction
checked 2,000 unique fold/seed receipts (4,000 discovery/replay fits), 5,555,454
accepted prediction rows, every candidate/seed/source/input binding and all
264 returned-file hashes. Exact agreement is to the saved five-seed fold means;
original individual seed vectors were not saved. The failed Deep probe remains
preserved and contributes no accepted budget. No numerical tolerance was relaxed.

The Nectar batch exited **0 at 03:37:36 AEST** and verified return/idle parking
completed at **03:41:08 AEST**. A live check around 11:00 confirmed **ACTIVE /
c3.xsmall (1 vCPU, 2 GiB)**, no batch workers and original checkout **ce63d96**.
Run ID: `1f498e0dbbdd47c4b64692ecae5b7abb`; alias **nectar-codex-ts**. The
closed batch/controller receipts are local and remote under
`data/processed/dsdm/goal052-seawfb-dsdm-experiment/ann-epoch-recovery/batch-20261001/`.
Do not relaunch them. Nectar control-plane commit **d83053f** records the
verified closeout. No recurring monitor exists.

The complete retained-full fitting orchestrator, complete hashed prediction
closure and actual-runtime qualification remain. **No outer response rows have
been opened.** Barry's opening authority persists; do not ask for it again.
Use the explicit recovered medians beside the unchanged 29 September inventory.
The response-free reader already covers all **144,860** region cells with the
existing **103-feature** transform, including imputed incomplete-predictor rows.

Correspondence reply **820** responds to Fable 810 with the reconciled evidence,
reference correction and recovery closeout. Task retrieval checkpoint is **820**.
Fable responds next on the reference-bin wording or any material objection;
this is not a new authorization gate. Closing chat replies retain a Hobart
date-time stamp.

## Historical handoff — 29 September, outer opening authorized; preparation

Barry explicitly approved the bird outer test: “I agree with Fable, yes to open
the sealed outer test.” This supersedes the earlier pending-opening decision;
do not ask for that permission again. Astra agrees. The accepted inner campaign
remains complete. No outer outcomes have been exposed by the preparation.

`OuterPreparation-20260929.md` makes the refit proposal concrete and carries
forward the regional reporting and descriptive rules from the 27 September
note. It proposes pooling the 25 accepted pretraining epochs within each focal
block, paralleling the recorded target-refit convention. A newly identified
gap needs resolution before opening: 40 selected conventional shallow-ANN
targets have only saved epoch ranges, not exact epoch medians. Preferred repair
is retained-only deterministic replay of the selected ordinary/q procedures,
checked against accepted predictions. Do not infer medians from ranges.

`scripts/goal052_outer_inventory.py` and its tracked
`outer-inventory-20260929.json` are preparation metadata, not a launch permit.
The intended full/full production inventory is 4,242 fits (50 pretraining,
10 q, 3,140 neural target and 1,042 conventional), excluding retries and ANN
epoch recovery. A separate outer implementation, synthetic prediction/response
separation checks, concrete seed/source/runtime bindings and actual-runtime
qualification remain. Predict and hash all three regions before response access.

Barry also asks whether architecture or data limits explain the small practical
gain. `ArchitectureOrData-20260929.md` distinguishes a same-input learner test,
richer habitat context and observation-process information. These are future
experiment proposals; they do not change the frozen outer assessment. No
irreducible noise ceiling or general deep-learning null has been established.

Correspondence thread 32 message **776** relays Barry's authorization; **778**
posts the concrete refit and architecture/data proposals. At catch-up no
new Fable reply followed Astra's 27 September message 575; the pasted summary
repeats the earlier critique. Fable responds next. Keep polling deleted.
Task retrieval cursor is **778**. Closing chat replies retain a Hobart date-time
stamp.

## Historical handoff — 27 September, Fable review and outer proposal

Goal052 remains computationally accepted; its exact summary and native
completion hashes are unchanged. Fable's detailed critique is Correspondence
thread 32 message **566**. Checked its central numerical claims using only the
accepted tracked inner summary; no private or sealed outer rows were read.
Reproduction: `scripts/goal052_inner_review.py` and
`evidence/seawfb_dsdm/goal052/fable-review-20260927.json`.

`Results.md` now leads with the practical conventional margin (+0.003390 AUC
on the common 73; +0.000938 on the other 84), fixes the panel-composition
wording, and separates species-number scaling from row-volume/composition.
The observed 0.00049 architecture margin does **not** bound selection optimism;
full-auxiliary frozen trunk beats target-only for **57/73**, while **73/73**
improve from 20 auxiliary species to full. Low prevalence does not mechanically
inflate TSS; near-zero q gains do not establish zero information content.
The original readout is archived as `Results-20260926.md` under its unchanged
receipt hash. Only that documentation pointer in the completion review moved.

`OuterPreopening-20260927.md` is a **discussion draft**, not execution or opening
authority. It preserves frozen regions, panels, all comparisons, and both
region-specific reporting and the mandated equal-region macro average. It
proposes nonoverlapping descriptive sign rules and continuous attenuation.
The outer claim hierarchy and complete retained-full pretraining/q/target refit
recipe must be agreed before opening. Fable is next to review the proposal;
Barry retains the opening decision. Keep polling deleted and do not refit,
read sealed outcomes, map or make manuscript claims.

Correspondence response **575** records the corrections and asks Fable to review
the draft; **Fable responds next**. Keep task retrieval cursor **573**.
Barry requests a Hobart date-time stamp at the end
of every closing chat reply (not interim updates), and clear indication of
whose response is next.

## Historical handoff — 26 September, Goal052 computational acceptance passed

Barry reported the completion email. PBS **812164.kunanyi-ohpc** finished
**F / exit 0 at 01:41:50 AEST on 26 September**, after **3h57m59s** on n001
(one CPU; 2.140 GiB peak memory). The unchanged native independent replay
returned **`goal052_complete_valid`**: **900 pretraining lifecycles, 42,345 unique
target lifecycles and 449 conditions**, with zero outer-response rows read.
No PBS jobs were active at the 26 September return check.

The exact accepted summary and native completion marker are now local.
The 5.37 MB return archive and all 16 contained evidence-file hashes passed;
87 local checks verified the launch/helper/source/input/q bindings, receipts,
condition inventory, preserved selection and byte-identical canonical imports.
All previously returned fits remain preserved. See
`evidence/seawfb_dsdm/goal052/completion_review.json` and
`docs/goals/052-seawfb-dsdm-experiment/Results.md`.
Accepted summary SHA256:
`ec0bc6c2df8cabd3554f5b2b9eebda97b3426ddd186bfa2acc64ba3d1244a3d3`.
Its native `complete_pending_validation` field is immutable aggregation output;
the separate hash-bound `goal052_complete_valid` receipt confirms acceptance.

**The compute stage is complete.** Next is focused scientific review of effect
sizes, controls and target/block heterogeneity. Keep the daily monitor deleted;
do not restart fitting or validation. NCP, SEH and NNC remain sealed. Outer
evaluation, retained-full refits, mapping and manuscript claims retain their
separate authorization boundaries. Source remains e309ca8 / fce7fb52… .
Correspondence thread 32 message **562** records completion and requests Fable's
focused scientific critique. Keep retrieval cursor **561**, the last contiguous
read checkpoint.

## Historical handoff — 25 September, validation continued after wall-time cap

Barry reported the PBS email and resumed the task. Notification **811800**
exited 0 at **14:24:01 AEST** with `00:00:00` execution time, as expected for
the administrative job released after all production predecessors ended.
All **48 target jobs 811750–811797** finished with exit 0 after **3h22m33s–
3h46m50s** each. Independent review verified all actual-host qualifications,
owners, exits and rank completions: 41,250 final-stage tasks, with the expected
42,345 unique leaf receipts present. Peak sampled RSS was 64.974 GiB during
qualification and 40.578 GiB during production. No fit restart is required.

See `evidence/seawfb_dsdm/goal052/kunanyi-target-completion-review.json` and
private `kunanyi-target-closeout-20260925/`. All 728 returned host-evidence
hashes passed; `host-review.json` records 1,129 successful checks. Source,
launch and driver bindings remain unchanged. All 42,345 leaf pairs are now
hash-verified and imported locally; native scientific acceptance is still pending.

Transfer-only PBS **812035** finished with exit 0 after **4m09s**, packaging
all 42,345 pairs into eight archives (5.83 GB). Remote package and hashes:
`/u/bwbrook/codex_kunanyi/dsdm-goal052/target-closeout-20260925/parallel-leaves`.
The slow serial collector was stopped, preserving its completed host archive.
All eight archive hashes and all 84,690 file hashes passed. The canonical local
`leaves/` now holds every pair: 40,885 new pairs plus all 1,460 unchanged screen
pairs. Private `import-review.json`, `leaf-file-hashes.json` and the preserved
archives bind the return; no download or import process remains active.

Initial validation **812145** exited 1 after 18 seconds: the audit helper assumed
`SCRIPT.parents[6]`, which fails in the shorter remote path. It stopped at
helper import, before leaf audit or aggregation. Preserve that failed attempt
and `kunanyi-validation-first-attempt-review.json`. The fix uses the current
working directory as the fallback while the caller supplies the exact root.
A shallow-path import test and all 1,460 preserved screen receipt-contract
checks passed; no fitting code changed.

Validation **812148** reached its four-hour wall-time cap and PBS terminated
it with exit **271** after **4h01m38s**, at **19:14:59 AEST**. Its output explicitly
records the wall-time kill; the old shell EXIT receipt misleadingly says 0 and
must not override PBS or native acceptance evidence. Memory peaked at only
2.97 GiB. The complete 42,345-leaf audit **passed at 17:31:15 AEST**, after
2h17m54s; the job then entered aggregation. No summary or native completion
was produced. See `kunanyi-validation-timeout-review.json` and private
`validation-v2-closeout/leaf-review.json` (SHA256
`ab0d2d4247b095d0a0992000c0f3438b3ddcbf89e58847caa97c18416152cfdf`).

Continuation **812164.kunanyi-ohpc** (`ds052_accept`) started at **21:43:51
AEST** on the same **n001** host and SIF, one CPU / 16 GiB / **24 hours**, with
PBS end/abort email to Barry and rerun disabled. Requested cap: **26 September
21:43:51 AEST**, subject to PBS termination handling. Work directory:
`/u/bwbrook/codex_kunanyi/dsdm-goal052/validation-continuation-20260925`.
Immutable `validation-launch.json` SHA256:
`4553390e694c3c0c6c8422db04c6c4e84a0707c83b17c3acc9dd9e99df240d87`.
It rechecks all saved-fit hashes, accepted inputs, source, manifest and prior
audit bindings before reusing the passed full-leaf audit. It then calls the
unchanged native aggregation and independent `validate_outputs`. No fits are
rerun. A native run lock excludes competing schedulers; durable `progress.json`
and `validation.log` expose phase and completed fold-group progress. Explicit
termination handling passed success/failure/SIGTERM tests; independent review
found no blocker. Startup verified PBS R on n001, no exit receipt, and progress
in `rehash_completed_audit_inputs` after source/runtime checks passed. See
`kunanyi-validation-continuation-review.json`.

**Wait for Barry's PBS email and resumption.** Inspect existing **812164**,
`progress.json`, `validation.log`, `wrapper-exit.json`, `phase-exit.json` and
`native-validation.json`; retrieve `validation-return.tar.gz` when present.
Require successful PBS termination and native acceptance. Do not resubmit
blindly or recreate polling. Scientific acceptance remains pending. The saved
900 pretraining and 42,345 target pairs remain intact locally and remotely.
No sealed access, full refits, maps, manuscript claims or scientific amendments.
Correspondence thread 32 message **560** records this continuation; keep retrieval
cursor **554**, the last contiguous read checkpoint.

## Historical handoff — 25 September, 48 target nodes; PBS completion email

Barry restored TPAC access. All old jobs **811265–811289.kunanyi-ohpc** finished
with exit 0, exact rank completions and accepted actual-host qualifications.
All **900 pretraining checkpoint pairs** are verified and preserved locally,
including 535 new pairs since 23 September. See
`evidence/seawfb_dsdm/goal052/kunanyi-pretraining-completion-review.json` and
private `kunanyi-check-20260925/`. Preserve these accepted audits rather than
repeating the historical checks. The completed `production-20260923` root and
its original source/driver/launch bindings remain intact; the deep-server
Goal052 scheduler remains stopped.

Preparation **811744.kunanyi-ohpc** exited 0 after verifying the fresh import
of 900 checkpoint pairs and 1,460 screen leaves and reproducing the native
final-target manifest. The sole active fitting allocation is **811750–811797.kunanyi-ohpc**,
48 fixed shards (`node-000`–`node-047`), each 28 single-thread workers, 110 GiB
and 48 hours. At **25 September 10:37 AEST**, all 48 jobs were running on distinct
hosts with no observed exit. Their original caps are **27 September
10:37:06–10:37:11 AEST**. PBS R is startup evidence;
each actual host still must pass exact canary/full-profile/resource qualification
before fitting. No new target-host qualification or target leaf is accepted by
this initial snapshot. A final 10:42 AEST startup check still found all 48
running and no exit receipts.

Canonical root: `/u/bwbrook/codex_kunanyi/dsdm-goal052/targets-20260925`.
See `evidence/seawfb_dsdm/goal052/kunanyi-target-launch-review.json` and private
`kunanyi-target-staging/` for exact preparation, launch, returned PBS records
and independent review. Immutable `handoff/target-launch.json` SHA256:
`4aeedc0d4e426dfee7d2c2d7f7fe08d686611bd46b3fecbcc606b5967e3177a7`.
Final-target manifest digest:
`5d54bd7cdeb8368ec4ca024cc6a853a4b2e3268ec9bc6cbf49fb8e1a76764cc6`.
The 900-checkpoint barrier and exact 1,800-file inventory are bound in the launch.

There are **41,250 final-stage tasks**, with **365 cached screen fits** and
**40,885 new fits**. Require all **42,345 unique target leaves** before any
aggregation. Within `.goal052-pbs/`, inspect `dispatch-targets-20260925`,
`jobs/JOBID`, `qualification/JOBID/qualification` and
`final_targets/{ownership,completions}`. Never rerun the dispatcher blindly, duplicate ranks,
reset a live deadline, change active drivers or clear ownership before verified
stopped-job recovery. Qualify any changed allocation/runtime before restarting.

External launch changes are **e70fd46**; frozen fitting source remains
**e309ca8 / fce7fb52...**, with accepted data/config/lock/q surfaces unchanged.
Barry has replaced the daily monitor with **PBS completion email** because
inactive TPAC portal sessions expire. Automation `continue-dsdm-goal052` was
**deleted**. Do not recreate polling or an automatic wake-up; wait for Barry to
report the email and resume this task.

Notification **811800.kunanyi-ohpc** (`ds052_notify`) is in the expected PBS
system dependency hold, with `afterany` covering every job **811750–811797**.
PBS will email **barry.brook@utas.edu.au** when that notification job ends or
aborts. It becomes eligible after all 48 production jobs end, including error
or time-limit exits, and requests only one CPU / 256 MiB / two minutes. All
predecessors had already started before this dependency was attached. This
signals allocation termination; scientific completion still requires returned
receipts, qualifications and the complete target-grid checks after Barry resumes.

See `evidence/seawfb_dsdm/goal052/kunanyi-notification-review.json`. Remote
notification records are `/u/bwbrook/codex_kunanyi/dsdm-goal052/notifications-targets-20260925`;
local copies are in private `kunanyi-target-notification/`. The production
scripts, job ownership and deadlines are unchanged. No partial-grid scoring,
sealed outcomes, full refits, maps, manuscript claims or scientific/numerical
amendments. Correspondence thread 32 message **533** records this superseding
monitoring decision; next retrieval cursor is **533**.

## Historical handoff — 24 September, TPAC access requires renewal

Today's daily check could not reach PBS: SSH rejected expired MFA admission,
and the portal's Enable Jumpbox SSH link redirected to UTAS Microsoft sign-in.
Chrome then blocked automation because an extension UI was open on that page.
Barry has been asked to complete sign-in, dismiss the extension popup and
enable jumpbox SSH. Current job states, new checkpoints, remaining
qualifications and resource use are **unverified**. The last verified remote
snapshot remains 23 September below; its 365 local checkpoints and review
references are preserved. No allocation, source, ownership or deadline changed.

Once access returns, inspect existing jobs **811265–811289** and retrieve only
new evidence. Their original caps remain **25 September, 11:07:47–17:35:20
AEST**, before tomorrow's daily 17:40 check. Preserve stopped-job recovery and
the 900-checkpoint barrier before final targets. See
`evidence/seawfb_dsdm/goal052/kunanyi-access-20260924.json`.
Correspondence thread 32 has no new messages; next retrieval cursor is 518
(last actual thread message remains 467).

## Last verified handoff — 23 September, 17:44 AEST daily check

Qualification job **810907.kunanyi-ohpc** completed with exit 0 on n234:
56 canary jobs across 28 workers and the full-row profile agree exactly with
the accepted deep-server scientific results. The canary took 2.54 minutes and
the full profile 65.93 minutes. PBS recorded 55.97 GiB peak memory. The old
resource sampler crashed; its empty output is retained, and the replacement
procfs sampler passed a live Linux check. This does not change fitting code.

Handoff job **811257.kunanyi-ohpc** completed with exit 0. The new canonical
root `/u/bwbrook/codex_kunanyi/dsdm-goal052/production-20260923` contains all
272 verified pretraining checkpoints and the preserved selection screen.
All 544 pretraining file hashes match the accepted closeout inventory.
The returned 700-task manifest was independently replayed: 25 disjoint shards,
with 24–26 unfinished fits each (628 total). Deep-server remains stopped.
PBS jobs **811265–811289.kunanyi-ohpc** are all running on 25 distinct hosts,
one fixed shard each, 28 CPUs / 110 GiB / 48 hours. All 25 exact canaries
passed. Fourteen hosts also passed the full-row profile and repaired sampler
checks and claimed their production ranks; eleven were still profiling.
Independent review confirmed all returned numerical and host bindings.

There are **365 verified pretraining checkpoints**, including **93 new pairs**
validated and preserved locally today: **165/700** remaining-pretraining tasks
complete, **535 unfinished**. Every new completion is auxiliary-20, taking
1.31–2.37 hours (median 1.67). Auxiliary-80 and full fits remain in progress;
these early completions do not establish a campaign ETA. Sampled group RSS
peaked at 46.67 GiB in production and 65.17 GiB during qualification, below the
100 GiB qualification limit. No job exit, failure or completed rank was seen.
Source, driver, launch, manifest and selection bindings remain unchanged.
Continue these jobs through their existing caps: **25 September, 11:07:47 to
17:35:20 AEST**, depending on actual PBS start. The daily check falls after the
last cap. See `evidence/seawfb_dsdm/goal052/kunanyi-day1-review.json`; private
`kunanyi-check-20260923/` contains the snapshot, returned evidence and audits.
See `evidence/seawfb_dsdm/goal052/kunanyi-pretraining-launch-review.json` and
`kunanyi-node-qualification-review.json` for launch and pilot evidence.

The immutable launch SHA is `3e04173f2834d3df6857e71386a3f65121d14d6f1c0ed15e4c98f17b056c9ccb`;
manifest digest `21506b03ac8884cd497900cdd985bd93aef7c19ed66cdd3f9b28849aa4cdb0fd`.
Launch, handoff and manifest are under the production root's `handoff/`.
Actual per-job qualification and exit records live in `.goal052-pbs/`.
Inspect existing jobs and receipts; never rerun the dispatcher or clear rank
ownership merely to retry. At completion/failure/cap, verify stopped jobs,
preserve and validate checkpoints, then choose a bounded continuation.
All **900 pretraining checkpoints** are required before final-target dispatch;
all **42,345 unique target leaves** before aggregation. Daily checks remain
**17:40 Australia/Hobart**. Sealed data and scientific boundaries are unchanged.

## Historical handoff — 22 September, daily check

The deep-server allocation ended at its original 17:29:30 AEST cap with
**exit 124**. No Goal052 workers or tmux session remain; the native run lock is
available and no multiprocessing semaphore files remain. All **272 pretraining
checkpoints** are validated and preserved locally, **55 new since yesterday**.
The remaining-pretraining stage completed **72/700**, leaving **628**. All
1,460 screen target leaves and the selected architecture remain unchanged.
Local and remote hashes match for all 544 pretraining files; source,
qualification and launch bindings are unchanged. See
`evidence/seawfb_dsdm/goal052/continuation24-closeout-review.json`.
Do not reset the launch binding or restart its original wrapper. Earlier
counts below are historical.

Kunanyi qualification job **810907.kunanyi-ohpc** remains unverified: access
failed because the SSH admission window expired, and refreshing the existing
Enable SSH page requires a fresh UTAS sign-in. Barry has been asked to sign in
and enable jumpbox SSH. This is an access blocker, not a verified job failure.
After access returns, inspect the existing job and its qualification evidence
before production dispatch. No replacement PBS job or new fitting allocation
has been started. The existing daily heartbeat records this state. See
`evidence/seawfb_dsdm/goal052/kunanyi-access-20260922.json`.

## Historical Goal052 state — 21 September, 18:02 AEST

The eight-worker allocation closed at its original 17:10 AEST cap (exit 124),
with 26 verified pretraining checkpoints, including 24 new completions in
48 hours, and zero target leaves. All payload/receipt hashes and fit/data
contracts passed; no workers or semaphore files remained after shutdown.

The new 24-worker CPU qualification passed: 48 jobs, exactly two per PID,
with all non-runtime result fields identical to the previous qualification.
It took 144 seconds, with 2.564 GiB peak worker RSS and 58.643 GiB maximum
sampled group RSS. The prior eight-worker receipt is archived. The active
canary is `metadata/goal052_canary.json`; its separate driver and review are
hash-bound. Fitting source remains `e309ca8` (digest `fce7fb52...`).

The seven-day/24-worker continuation launched at **17:29:30 AEST on
15 September** in deep-server tmux `dsdm-goal052-continue24`, at
`/data/codex/repos/dSDM`. All 24 workers are active, and the first 26 scheduler
completions reuse the unchanged existing checkpoints. The cap is
**22 September, 17:29:30 AEST**, plus 60 seconds termination. Private
`continuation24-launch.json` binds the launch; tracked
`evidence/seawfb_dsdm/goal052/continuation24-launch-review.json` adds actual
PIDs, log path and reuse verification. Runner PID 45460; timeout PID 45451.

Daily checks now run at **17:40 Australia/Hobart**, after the final cap on
its last day. This supersedes 17:20 and four-hour instructions below. Barry
retains standing compute authority: review actual throughput and capacity,
and choose subsequent bounded allocations autonomously. No new scientific
or numerical amendment is authorized. The sealed outer boundaries remain.

Sixth daily check: all **200 screen-pretraining fits and 1,460 screen target
fits are complete**. The frozen rule selected `seawfb_scale`; independent
screen verification and exact selection replay passed. The runner entered
`remaining_pretraining` automatically, with **17/700** complete: **217 total
pretraining checkpoints**, including 34 new since yesterday, have passed
hash, finite-state, stopping/replay and data-contract checks. The 17 new screen
fits took 12.99–20.36 hours (mean 16.55); the first 17 remaining-grid fits took
1.43–7.18 hours (mean 2.44), reflecting different auxiliary sizes rather than
a comparable throughput estimate. All 24 original workers are alive and busy,
with about 83 GiB RAM available and no swap use. Source/runtime/qualification/
launch bindings are unchanged. Continue the same allocation through its
original cap tomorrow, then verify shutdown and choose the next bounded
allocation. Daily cadence and scientific boundaries remain unchanged. See
`continue24-day6-review.json` and `selection-screen-review.json`. The verified
milestone is on Correspondence thread 32, message 455.

## Historical Kunanyi migration preparation — 21 September evening

Barry identified up to 48 nodes × 28 CPUs / 128 GB and authorized using them.
Kunanyi is now the preferred route for the remaining independent fits, after
runtime qualification and verified production handoff. Deep-server continues
unchanged until its original cap tomorrow. See
[the execution note](docs/goals/052-seawfb-dsdm-experiment/Kunanyi.md).
PBS hardware probe 810868 and container probe 810869 both passed (exit 0).
Kunanyi has GLIBC 2.17; Apptainer successfully runs Ubuntu 24.04 with GLIBC
2.39. Package the exact existing Python/locked environment and require exact
28-worker numerical agreement before production. Use the home staging root
`/u/bwbrook/codex_kunanyi/dsdm-goal052`; scratch upload failed, consistent with
X-ray's recorded quota issue. Numerical qualification job **810907.kunanyi-ohpc** started on n234 at
18:54:28 AEST (28 CPUs,
110 GB, four hours). Its runtime/input/driver checksums passed before dispatch.
Inspect that job at the next daily check. No PBS production fits have started.

## Start Here

The primary cross-AI venue is the Correspondence project `dsdm`, discussion
32, "Fable's arrival review: programme, Goal 052 compute, and pre-score analysis plan".
Barry invited Fable as an external scientific advisor and reviewer; Astra
handles implementation and execution. Consult and reply there when active;
bring Barry unresolved scientific decisions requiring his judgement. Board
discussion does not itself amend frozen protocols or dispatch another model.


Work directly with Barry here. The Chief-of-Staff worktree and named
action-agent `quoll` arrangement are retired for this project. Use native,
bounded subagents when useful; do not reconstruct that management machinery.

This note gives the current orientation; linked protocols, decisions, code,
and evidence supply the detail. Some historical roadmap paragraphs lag behind
the work. The mainland-to-Tasmania transfer assessment is complete; it is
distinct from the still-deferred original Tasmania outer test.

## Scientific Purpose And Findings

We test whether species-aware, multi-head neural pretraining learns a useful
environmental representation that transfers to a focal species excluded from
pretraining. Fine-tuning must beat strong target-only controls, not convenient
weak baselines. Outputs are **relative habitat-suitability indices**, not
occupancy probabilities. A sound negative result is a successful experiment.

The programme has three steps, followed by synthesis and substantial manuscript
revision:

1. **Eight Tasmanian mammals: machinery prove-out.** Rebuilt acquisition,
   cleaning, predictors, responses, spatial partitioning, conventional models,
   and the PyTorch dSDM workflow. High prevalence, restricted geography, and
   only seven auxiliary species made this a difficult transfer-learning test.
   Inner comparisons found no convincing dSDM advantage; larger networks and
   reduced predictors did not rescue it. Preserve this finding. The original
   held-patch outer assessment remains sealed/deferred. Macropus giganteus was
   excluded from the original nine because historical range contraction makes
   current distribution a poor proxy for potential suitability.
2. **Mainland mammals transferred to Tasmania: completed bridge experiment.**
   Used a richer mainland pool, portable predictors, and five shared targets,
   assessed against Tasmania's camera-supported absences. Goal 046
   corrected auxiliary effort-support leakage and supersedes Goal 045's
   full-data/full-auxiliary result. Small corrected mainland-CV gains did not
   transfer: Goal 047's one-shot Tasmania test found mean AUC about 0.556 for
   full dSDM versus 0.584 for selected conventional models. This descriptive
   five-species null stands; no Tasmania-informed architecture or threshold
   rescue. See the [accepted decision](docs/goals/047-tasmania-transfer-assessment/Decision.md).
3. **Southeastern Australian woodland/forest birds (SEAWFB): current stage.**
   Many more auxiliary species and more varied prevalence/environments test
   the scaling hypothesis. Better performance is a hypothesis, not an
   acceptance criterion. Tasmania is ordinary training geography here.

The scalar `q_linear` control tests general community suitability against
learned neural representations: pooled elastic-net environmental predictions,
equal total contribution per auxiliary species, no species-ID predictor.
It is not an observed richness layer.

## Frozen Bird Design

Goals 048-050 established the design and reproducible modelling foundation:

- Contemporary 2001-2025 evidence on 0.01-degree cells. The bird response
  substrate comes from an ALA aggregate species-cell census, not legacy R
  tables or a claimed raw-occurrence-row download.
- 505 effort-donor taxa, 183 eligible modelling heads, 157 focal targets.
  The 73 primary targets have nested 25/50/100% target-data endpoints; the
  remaining 84 have full-data endpoints only. These supersede the initial
  40-species feasibility panel.
- Three complete IBRA regions plus their external 50-km buffers are excluded
  simultaneously: NCP (Naracoorte Coastal Plain), SEH (South Eastern Highlands),
  and NNC (NSW North Coast). Their evaluation outcomes remain sealed.
- Retained training uses five frozen spatial folds of projected 50-km blocks,
  seed 394, and a portable 24-predictor set encoded into 103 features.
- X10 effort-supported backgrounds are primary; X20 is evaluation-only
  sensitivity. Richness measures sampling support, not a predictor or proof
  of true absence. Preserve natural prevalence rather than balancing classes.
- Ten focal-species blocks govern cross-fitting. Remove the **whole focal
  block from both auxiliary response heads and auxiliary donor richness**.
  Target fitting/evaluation instead uses the frozen target-specific support
  rule. Exclude held spatial folds from fitting, including transforms and
  stopping decisions. Do not improvise a simplified exclusion rule.

Primary selection uses mean-fold ROC AUC; training out-of-fold TSS supplies
tie-breaking and threshold selection. BA, MCC, sensitivity, specificity,
prevalence, and fold variation provide complementary interpretation. Outer
outcomes must never choose architectures, features, thresholds, or repairs.

## Goal 051 benchmark — accepted 12 September

The conventional benchmark is implemented and accepted with its documented
candidate-failure limitation; the dated closeout below is authoritative.
Its five families are intercept-only null, elastic-net logistic regression,
random forest, histogram gradient boosting, and a shallow one-hidden-layer ANN.
The statistical families use scikit-learn; the ANN and dSDM use PyTorch.
The grid has 303 base endpoints, 449 q conditions, and 150 shared q surfaces.

A metric-free canary exposed numerical problems in q fitting. Correction
`c14bc47` is already committed and pushed: use `w/k` and `C*k`, where
`k=max(w)`, preserving the penalized objective, and distinguish convergence
warnings from unrelated warnings. Recorded verification: **31 tests passed**.
Protocol v3 allows one 5,000-to-10,000-iteration retry but requires convergence.
Do not rerun obsolete v2 or mistake all its warning-triggered failures for
proven iteration exhaustion.

Corrected canaries were launched on 5 September in detached sessions:

| Host | Checkout | tmux session |
| --- | --- | --- |
| Mac mini | `/Users/bwbrook/papers/dSDM` | `dsdm-goal051-canary-mac` |
| `deep-server-ts` | `/data/codex/repos/dSDM` | `dsdm-goal051-canary` |

The successor's read-only inspection found both canary sessions finished. Mac
exited 0 with all five receipts and a host summary. Deep-server produced two
serial receipts, then exited 1 during mixed concurrency with PyTorch's
autograd/fork threading error; no completed deep-server host summary exists.
Neither host had a production session or run log.

The authorized code sweep removed the abandoned Goal029 P-spline implementation,
merged repeated q standardization work, trimmed duplicate input/q validation,
and explicitly selected `spawn` for both process pools. It retained the frozen
scientific configurations and historical evidence. These source changes make
the prior canaries historical: **route selection requires fresh canaries
against the final source**. Preserve the old logs/receipts when
restarting; do not rebind their hashes to new code. No canaries or production
were launched during the sweep.

Barry resumed Goal051 on 6 September. Both hosts now have fresh canaries from
`ab7e369`, launched at 00:17–00:18 AEST in the sessions above; both initial CPU
processes were verified active. The old canary directories were preserved.
Linux passed 54 portable tests, and both live input plans produced identical
identities. The exact current paths and archive names are in the runbook.
At the 13:04 AEST wake-up, Mac had completed and its five-receipt evidence
validated. Deep-server rebooted at 03:31 after one serial receipt, interrupting
its batch. The interrupted directory was preserved and a fresh server batch
started at 13:05:09 AEST from unchanged source; its CPU process was verified
active.

At the 8 September wake-up, deep-server had completed at **19:06 AEST on
6 September**, exit 0, with all ten receipts. Both host summaries reproduced
exactly; independent checks covered transfer hashes, timing, interval
concurrency, convergence, identities, and zero ecological metrics/outer access.
The selected route is **Mac mini, three workers**: measured throughput was
5.82 canary probes/hour versus 3.81 on deep-server at eight workers. The server
measurement reflects substantial background contention, not an intrinsic
hardware ranking. The route receipt is `metadata/goal051_canary.json`.

Production launched locally at **09:22:38 AEST on 8 September**, in tmux
`dsdm-goal051-conventional`, from unchanged implementation source `ab7e369`.
Barry subsequently requested offloading this multi-day run to Nectar so the Mac
remains available for local work. The Mac process was deliberately stopped
(exit 143), preserving **13 complete q surfaces**; no target endpoint had
started. All 13 checkpoints pass unchanged on Nectar.

Nectar is now ACTIVE at `c3.3xlarge` (64 vCPUs, 128 GiB allocated RAM), with the
working clone at `/data/codex/repos/dSDM` via `nectar-codex-ts`. The execution
plan uses **16 single-thread workers**, an exact VM UUID/capacity check, and
two serial plus 16 concurrent metric-free probes. The new execution module and
config have their own identity; the original scientific source/config hashes
and Mac/deep-server evidence remain unchanged. This is an authorized change of
compute route, not a new scientific protocol.

`scripts/goal051_nectar_launch.sh` chains the Nectar canary, route receipt,
live-host/evidence gate, and unchanged resumable production launcher. The
session is `dsdm-goal051-nectar`, launched at **10:51:23 AEST on 8 September**
from `5404fc6`. The first serial canary process was verified active at 99.9%
CPU. Its execution log/exit files are
`nectar-execution.log` / `nectar-execution.exit` in the Goal051 private root;
production still writes `run.log` / `run.exit`. See the runbook for launch and
restart details. Goal051 remains incomplete until its full evidence passes
acceptance.

At the **14:15 AEST, 8 September** scheduled check, all 18 Nectar canary probes
had completed and the chain had started production at **14:03:04 AEST**.
The 18 receipts, summary and new route were copied back with all 20 SHA-256
hashes verified. Summary/route reproduction and independent checks of timing,
concurrency, convergence, identity and zero outer access passed. The new route
is `metadata/goal051_nectar_route.json`. Measured mixed throughput was 13.48
probes/hour, 2.32 times the Mac's three-worker rate. Production had 20/150 q
surfaces complete, no target endpoints yet, and all 16 workers active with
about 104 GiB available memory. No restart was needed.

At the **17:16 AEST** follow-up, 112/150 q checkpoints passed their original
load/convergence/identity checks (42 q20, 38 q80, 32 qfull); no target endpoint
had started. All 16 workers remained active and checkpoints were still being
written. However, `run.log` had not advanced since 14:53 AEST. The executor
can defer a raised worker exception until queued work finishes during pool
shutdown. This is a suspected pending failure, not a confirmed traceback:
inspect the eventual log/exit and missing surfaces before restarting or
amending anything. Leave the productive workers running meanwhile.

**Current state at 20:17 AEST: stopped for numerical-policy review.** The
pool finished at 18:49:53 AEST with exit 1. Its first reported exception was
`q_linear_nonconverged_after_extended_attempt`: both 5,000 and 10,000 iteration
ceilings were exhausted with `ConvergenceWarning`. No target endpoints or
ecological scores were generated. All 143 completed q checkpoints validate;
the seven missing surfaces are all full-auxiliary: block1/folds0,4;
block7/folds0,2,4; block8/folds0,4. The original executor did not attach a
surface ID to the reported error or retain every individual exception.
Preserve this distinction; do not label all seven with the single traceback.

The 286 model/receipt files and four execution logs/exit markers were returned
to private `nectar-return-20260908T1017Z` under the Goal051 root, with all 290
SHA-256 hashes verified. Both the remote checkpoints and stopped Mac logs are
preserved. Compact evidence is
`evidence/seawfb_conventional/goal051/q_stage_failure.json`. Do not repeat the
unchanged failed schedule or relax convergence without explicit authorization
for a versioned numerical amendment. Nectar currently has no active compute.
The reviewable recommendation is
`docs/goals/051-seawfb-conventional-benchmark/Numerical-amendment-3-proposal.md`:
one from-scratch 20,000-iteration tertiary attempt, unchanged objective and
tolerance, with explicit provenance and a strict all-150 convergence gate.
It remains a proposal. The three-hour follow-up stays active but silent while
this reported blocker is unchanged. Nectar remains at c3.3xlarge pending the
campaign decision; no resize or amended fit has occurred.

**Latest: protocol v4 recovery launched on Nectar at 23:19:09 AEST, 8 September.** Barry
approved the complete bounded recovery proposal. Use the fresh-collection
fallback: preserve all v3 evidence and rerun 150 q surfaces in
`data/processed/dsdm/goal051-seawfb-conventional-benchmark-v4`. The initial
Nectar chain first runs the isolated block1/fold0/full stress fit, then repeats
two serial/16 mixed metric-free canaries and writes
`metadata/goal051_nectar_route_v4.json`. Only then may q production start; all
150 must validate before any target endpoint is scheduled. Every q failure is
recorded immediately by surface. A final 20,000-iteration failure stops again;
no further numerical amendment is authorized. The old unresolved-approval
paragraphs above are historical. See the current section at the top of the
Goal051 Runbook for v4 paths and continuation commands.
The launch uses source `ce63d96`, with 84 portable tests passed on both Mac
and Linux and the exact v4 input identity validated. The initial detached
stress process is active; convergence and production remain pending. The
three-hour follow-up now explicitly follows the v4 chain. All 290 original
v3 artifact hashes were verified unchanged before and after the remote update.

**02:20 AEST, 9 September:** the isolated stress surface converged at 10,478
iterations on the tertiary attempt after reaching 5,000 and 10,000 on the
first two attempts. Both returned artifacts match remote hashes; standard
receipt replay and independent checks of identity, seed, attempt sequence,
parameters, heads, exclusions and weights passed. Compact evidence is
`evidence/seawfb_conventional/goal051/amendment3_stress.json`. The first of two
serial canaries is complete and the second is active; the mixed batch and
production remain pending. Keep the existing chain running.

**05:20 AEST, 9 September:** all 18 v4 Nectar canaries passed and the existing
chain started fresh q production at 03:49:44 AEST. All 20 returned canary,
summary and route hashes match Nectar; the summary and route reproduce
exactly, and independent interval/concurrency, convergence, identity and
digest checks passed. The current route is `metadata/goal051_nectar_route_v4.json`.
All 43 completed q surfaces validate (19 q20, 16 q80, eight qfull); all 16
workers are active, with no failure receipt or exit marker. Target endpoints
have not started. Continue the existing q stage; do not change its source.

**08:20 AEST, 9 September:** 136/150 q surfaces now validate: all 50 q20,
46 q80 and 40 qfull. Two formerly unresolved full surfaces (block1/folds0,4)
converged on the tertiary attempt at 10,478 and 10,267 iterations. The other
five formerly unresolved full surfaces are still pending, alongside nine
block9 surfaces. There are no failure receipts or exit markers; workers remain
active and no target endpoint has started. Continue the existing chain.

**11:21 AEST, 9 September:** all 150 q surfaces are complete and independently
verified (50 per auxiliary size; 61 primary, 82 extended, seven tertiary).
All seven formerly unresolved full surfaces converged at 10,194–10,553
iterations. Returned all 300 model/receipt files with verified hashes and
replayed the complete q provenance gate on the Mac. Independent parameter,
seed, attempt, head/exclusion and weighting checks passed; compact evidence
is `evidence/seawfb_conventional/goal051/q_v4_acceptance.json`.
Target fitting completed at **16:15:47 AEST on 10 September**: all 303
endpoints and 449 q conditions are present, with all five families available
at every endpoint. Aggregation passed at about 17:30 AEST and the existing
chain is running final `validate --complete` (PID 23216 at 17:46 AEST).
All 606 endpoint files were returned to the Mac with verified SHA-256 hashes;
the aggregate was returned privately as `summary-returned.json` in the v4 root.

The independent endpoint audit passed all 6,763 prediction groups and
474,174,113 rows, with maximum metric difference 4.45e-16. Candidate/family
selection, q reuse, fit counts, coverage and q provenance passed. See
`evidence/seawfb_conventional/goal051/independent_endpoint_audit.json`.
The 49 rejected candidates are all `enet08` nonconvergence; three elastic-net
candidates remain everywhere. Rejections are more frequent in the lowest
prevalence quartile (18/75 versus 4/75 in the highest), reducing tuning breadth,
although the frozen family-availability gates pass at 100%.

**12 September: Goal051 is accepted.** Barry approved proceeding autonomously
under the recommendation to retain the original family-level coverage gate
and explicitly document the prevalence-patterned `enet08` candidate failures.
No refitting or post hoc numerical/gate change occurred. All 303 endpoints,
449 q conditions and 150 q surfaces passed native and independent verification;
results are returned with verified hashes. The accepted aggregate and bound
receipt are `evidence/seawfb_conventional/goal051/summary.json` and
`completion_review.json`. The detailed limitations and results are in the
Goal051 Decision record.

Nectar remains parked at c3.xsmall with all evidence preserved. The completed
Goal051 heartbeat `check-dsdm-nectar-progress` is paused. Do not restart its
production chain or repeat heavy validation on the parked VM.

The current task advances the prospectively frozen Goal052 comparison through
implementation and validation under Barry's autonomy request. Its original
config is preserved byte-for-byte as the scientific freeze; execution status
and authority are recorded in the Goal052 Decision/Runbook. The runner and
43 focused tests pass on Mac and deep-server. CPU foreach AdamW passed
within-host bitwise stopping/replay comparisons on both machines; fused AdamW
is deferred because it changed Linux numerics. Source `e309ca8` is staged on
deep-server. Its fresh two-worker canary passed at 14:37 AEST, with bitwise
repeat agreement and maximum worker RSS 2.545 GiB. The full-row profile also
passed: 79.54 minutes for auxiliary pretraining and 2.395 GiB peak RSS. Returned
receipt hashes and fit invariants are verified. The approved 24-hour pilot
stopped at 16:28 AEST on 13 September with exit 124; no pilot workers remain.
Two block-0/fold-0 pretraining checkpoints are verified and preserved:
bridge_wide took 11.97 hours (33 discovery, selected/replay 3), bridge_control
15.44 hours (34 discovery, selected/replay 4). Deeper fits were interrupted;
no target leaves, architecture selection or ecological metrics were generated.
See `docs/goals/052-seawfb-dsdm-experiment/PilotReview.md` and the tracked
`pilot-review.json`/`pilot-closeout-manifest.json` evidence. The four-hour
follow-up resumed for the subsequent 48-hour/eight-worker continuation.
The latest state at the top of this handover and `PilotReview.md` describe it.
Outer outcomes remain sealed. Routine implementation and tests can proceed;
material scientific amendments require discussion. Compute allocations now
fall under Barry's standing authorization. Start from the current Goal052 runbook and
live source/test state, not the historical Goal051 launch paragraphs above.

## What Follows

Goal 052's separate dSDM design was frozen before Goal 051 ecological scores:
target-only random-init residual MLP, target-plus-q MLP, pretrained frozen
trunk, and full fine-tuning; auxiliary sizes 20/80/full and five paired seeds.
A bounded four-architecture panel selects one shared architecture using
training-only evidence. Do not redesign it after seeing conventional scores.

Goal051 is now accepted and Barry has authorized autonomous continuation.
Its [v4 config](config/goal052_seawfb_dsdm.json) records
all three numerical amendments. A later, separately authorized bird outer
evaluation precedes cross-case synthesis and manuscript rewriting.

## Working Contract And Practical Guardrails

- Read the current global `~/.codex/AGENTS.md` and any repo-local instructions
  present on arrival. There was no repo-local AGENTS.md at this handover.
- Use [Twilight Laboratory](/Users/bwbrook/.codex/skills/twilight-laboratory/SKILL.md)
  for scientific programme design, autonomy, delegation, and stopping, and
  [Kill Your Darlings](/Users/bwbrook/.codex/skills/kill-your-darlings/SKILL.md)
  to keep implementation and validation lean, not to trigger another broad audit.
- Be Barry's assertive research colleague. Decide routine reversible matters
  and accept/commit/push completed in-scope work after focused review. Consult
  him for consequential science, privacy, strategic, or resource trade-offs.
  Report ecological meaning and a substantive next tranche at meaningful
  endpoints, not an approval request per small step.
- Follow **rigour at the scientific decision boundary; proportional
  engineering everywhere else**. One focused review and material repair is
  normal; stop when more polish will not change the decision. Avoid compatibility
  paths, ceremonial ledgers, and repeated tests for old behaviour.
- Use `uv run --locked` with the Python 3.12 environment. Main implementation
  lives in `src/dsdm_phase1/`; current runner is
  `goal051_seawfb_conventional.py`, sharing `seawfb_modeling.py`.
  Use focused gates for current changes. Historical broad-suite failures are
  separately recorded debt, not a reason to loop through unrelated repairs.
- `tas_cam/` is Barry's authoritative private camera dataset and must remain
  untracked. Keep raw records, precise locations, camera identifiers,
  row-level predictions, and bulky outputs private under ignored paths.
  Commit compact aggregate evidence and provenance, not raw payloads. Camera
  nondetections are **survey-supported absences**, not unsampled-cell zeros.
- For long compute, use detached tmux, verify launch, provide status commands,
  then stop until Barry wakes the task. Consult the `nectar` control-plane docs
  under `/Users/bwbrook/work/nectar` before a new resource decision. Do not
  assume GPU access or superiority; use workload-specific evidence.

Read next only as needed: the [strategic roadmap](docs/strategic_plan_30000ft.md)
for rationale (not current status), [Goal 050 decision](docs/goals/050-seawfb-modeling-foundation/Decision.md)
for foundation semantics, and [Goal 051 goal](docs/goals/051-seawfb-conventional-benchmark/Goal.md),
[log](docs/goals/051-seawfb-conventional-benchmark/Log.md), and runbook for
continuation. There is no need to ingest Goals 001-052 wholesale.
