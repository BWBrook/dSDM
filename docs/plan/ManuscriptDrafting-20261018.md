# Manuscript drafting: editor and specialist readers

Barry authorised substantive drafting and sustained iteration with Claude on
18 October 2026. His stated standard is a paper whose novelty, implications
and scientific quality are clear to an expert in the general area as well as
to the specialist collaborator or competitor. This instruction supersedes the
11 October hold on further prose; the completed analyses remain unchanged.

The working question is what multi-species pretraining adds to prediction for
a target species, and whether that contribution persists at new places.
The contribution must follow from the empirical comparisons, not a claim to
invent shared representations or validation principles. MEE remains the
working target. The 11 October plan supplies the initial allocation, with
freedom to revise the argument in response to substantive critique.

## Completion standard and ownership

- A complete manuscript, supplement and figure/table set with a clear central
  question, evidence-supported novelty and concrete implications.
- Title, abstract and opening readable without prior knowledge of the project;
  sufficient methodological detail and limitations for a specialist.
- Substantive exchanges with Claude on the argument, the complete draft and
  revisions. Record disagreements and unresolved points, not merely assent.
- Numerical claims checked against accepted aggregate sources; citations
  checked against primary literature; prospective and post hoc status clear.
- Readable PDF and Word outputs, using the existing manuscript builder.

Codex owns manuscript source edits and integration. Claude is asked to critique
and propose prose on the correspondence board, avoiding concurrent file edits.
Bounded helpers check numerical claims, closest literature and the new
recording-richness figure. No model fitting, raw-response access or alteration
of accepted scientific receipts is part of this drafting task.

Author metadata, data-release permissions and final statements require human
confirmation before submission. This does not prevent preparation of the
complete draft. Generative-AI assistance will be described factually, with
draft disclosure wording clearly identified for Barry's review. No submission
or contact with a journal is authorised by this drafting instruction.

## Iteration record

1. Read Claude's messages 1426–1427. Accepted the need for a stronger opening,
   literature positioning, explicit regional roles, a concise forward-looking
   discussion and AI disclosure. Preserved his correction of a mean/median
   comparison. A further clarification is needed: −0.0051 and −0.0015 are the
   survey-only fine-tuning/target-only contrasts under two training regimes,
   not a mixed-versus-survey comparison.
2. Message 1874 communicates Barry's new authority, file ownership and the
   proposed argument, and asks Claude to challenge novelty and the editor's
   reason to care before reviewing a complete rewrite.

## Preservation

The starting repository state is clean commit `24a9b7c`. Its manuscript and
supplement PDF, Word and build manifests have been copied without changes to
`manuscript/build/archive/20261011/`, with an archive manifest. The original
analysis and delivery receipts remain historical records. New prose does not
retroactively amend a protocol or make a post hoc diagnostic prospective.

3. Rebuilt the complete first manuscript around four Results sections, two
   main tables and three figures. Added the survey-only evaluation as a crossed
   training/evaluation comparison, rather than another appended Results section.
   Primary literature checking added six close precedents through September
   2026. Full draft and specific editorial challenges were posted in message
   1875 (source SHA-256 `91df7544aa242fec6913c4ffe1ca742b710dd7efc079a514ef4325232ab98c92`).
4. Independent numerical review identified and corrected three presentation
   defects: the abstract now states the post hoc survey-only status and the
   differing co-primary TSS result; training removal is 3.3% of all rows and
   16.4% of negatives; per-species survey-only contrasts now have Table S11.
   No accepted estimates changed. The main and supplementary builds pass.
5. The board does not dispatch Claude automatically. A read-only CLI attempt
   found no logged-in CLI session. The existing Claude Code desktop dSDM chat
   was available. Barry explicitly authorised direct conversation there on
   18 October. A Codex-attributed request to read messages 1874–1875 and critique
   the current draft was sent in that existing chat; its responding state was
   observed. This is a review request, not yet a completed Claude review.
6. Claude's first complete-draft critique (message 1880) identified the central
   missed comparison: the held-bird target-only network exceeded conventional
   learning by +0.0032 AUC, alongside +0.0028 for fine-tuning. R2 now foregrounds
   that distinction, uses three Results sections, states the tabular-input scope
   early, strengthens the AI disclosure and adds the conventional 50-to-100%
   target-data gain as a descriptive scale comparison. Both new numerical
   contrasts were independently checked against accepted aggregates.
7. R2 was posted in message 1882, with source SHA-256
   `e3d740d8f35c90d8f73a6961b02e6aec7222ad55abc84414a58779ec0a8f66fa`,
   and a second review request was delivered in the existing Claude desktop
   chat. Three qualifications to Claude's proposed wording remain explicit:
   the neural advantage was available without pretraining, rather than causally
   attributed to architecture; regional scoring does not identify how much
   geographic loss was caused by extent; and Tasmania's matched AUC result
   differs from co-primary TSS. R2 also adds verified dataset references and
   Supplementary Methods S4, preserving unresolved original-stack metadata.
8. Claude's second review (1883) accepted all three scientific qualifications
   and requested a specific novelty gap, a simpler abstract and a question
   title. R3 adopts those changes while bounding the literature statement to
   cited close precedents and limiting the prospective freeze to primary
   models/scoring. Post hoc extent, target-only ensemble and Tasmania analyses
   retain their actual status. The Results no longer repeat all limitations.
9. Claude's third, complete-draft cold read (1888) judged the argument suitable
   for both intended audiences and requested four small repairs: explain why
   the Tasmania abstract result matters, remove a duplicated metric sentence,
   clarify the leave-one-species-out range and separate a Figure 2 label from
   its neighbouring point. All were integrated. The final abstract remains
   AUC-specific for Tasmania; co-primary TSS is explicit in the main results.
   This is completed editorial review, not independent validation by agreement.

## Verification and delivery

Independent aggregate checks cover the main numerical claims, the added
target-only/conventional and data-fraction comparisons, and all S10/S11 cells.
Primary-source literature and data-product checks are retained alongside the
bibliography. Figures preserve the accepted values and have source/script/output
hash records. Main and supplement builds use the existing `makedoc` toolchain;
their source hashes, PDF/Word outputs and final checks are recorded in
`evidence/cross_case_synthesis/20261018/draft-delivery-verification.json`.

The generic builder manifest's `git` field identifies the shared `makedoc`
repository because that is its working directory. It is not the dSDM source
revision. The new delivery record identifies dSDM separately and verifies all
input and output hashes directly. No shared-builder changes were made.

Final Word rendering exposed split table rows and awkward species-name
wrapping. A repo-local formatting step now applies the configured A4 review
geometry, compact tables, intact rows and repeated headers, with content/image
invariance and idempotence checks. It is integrated into Word builds and
manifests. PDF source/layout remains unchanged. The Figure 3 source CSV also
corrects a support-description typo: outer minimum counts apply within the
held region, not each development fold. Its values and rendered PNG are
unchanged.

## Author-requested humanisation pass

Barry's subsequent reading found the draft improved but too heavily caveated
and stilted. He asked for a candid assessment of its value to generalist editors
and specialists, with stronger flow and preservation of the scientific context.
The starting point for this pass was commit `d998626`; its manuscript source,
PDF, Word file and verification record are preserved in
`manuscript/build/archive/20261018-before-humanisation/`.

The editorial diagnosis was that specialist defensibility had advanced further
than the paper's argument. The revision therefore starts with the ecological
reason to borrow information across species, explains why predictive success
and the gain from pretraining are different questions, and gives the useful
development and ensemble results more space in the Discussion. The geographical
and observation diagnostics support this argument. Repeated defensive endings
and internal workflow vocabulary were removed, while the contextual literature
and numerical detail were retained.

A bounded independent scientific read identified the limits that must survive:
small descriptive effects under dependent species and regions, no equivalence
claim, architecture selection using fine-tuning, tabular inputs, heterogeneous
experiments, and post hoc survey-only evidence with sparse negative support.
Its second read checked the revised source and prompted precise repairs to
scope the neural advantage to birds, distinguish architecture from fitted
weights, and separate predictive improvement from management benefit. All
Methods and Results numerical tokens remain in their original order; every
original reference key remains cited. No analysis or source data changed.

Claude was asked for a further critique in correspondence message 1949.
Automatic approval review rejected the desktop documentation step needed to
resume direct conversation, so this pass does not claim a fourth Claude review.
The three earlier reviews remain part of the draft's history. The revised text
was left on the correspondence board for later reading.

The strengthened framing uses the existing Yates et al. (2018) transferability
review and Ovaskainen et al. (2025) common-to-rare study. Their primary texts
were checked again for management use in data-poor settings and the biological
rationale for borrowing environmental information. The main text remains a
test of tabular environmental pretraining, not a general verdict on shared
learning. The remaining substantive vulnerabilities are unchanged: modest
average effects, incomplete explanation of transfer heterogeneity, and limited
generality beyond this design.

Current document bindings and checks are in
`evidence/cross_case_synthesis/20261018/humanisation-verification.json`.
The earlier delivery record is preserved as the record of the preceding draft.

## Fourth Claude review and final prose revision

Barry resumed Claude asynchronously and returned the exchange to Codex. Claude's
message 1972 judged the draft effective for specialists and nearly effective for
editors, identifying internal terminology and dense AUC triplets as the main
remaining obstacles. Codex's response 1986 records the accepted changes and
scientific disagreements. Barry now handles asynchronous wakeups himself.

The revision replaces internal shorthand with ordinary model and geographic
terms, opens Results paragraphs with their findings, and moves the learning-curve
selection/seed qualification into Methods. New Table S1f preserves all nine
displaced absolute AUC values within a complete six-assessment, three-method
table drawn directly from the accepted synthesis summary. Its caption distinguishes
fold-mean bird development AUC from the pooled-domain Fig. 2 calculation. This
table is a manuscript addition; the historical supplement generator was not rerun.
Figure 3's horizontal-axis wording now says "Other recorded species in background
cells"; all source CSV values and other figure outputs are unchanged.

Norberg et al. (2019) was checked against its primary text, Feature C on shared
environmental responses. Its controlled comparison favoured sharing for all
species but independent modelling for common species alone. The Introduction
now describes task- and species-dependent gains, replacing the overly broad
"substantial evidence" sentence. The Discussion also states what the full-pool
frozen-encoder result supports: useful shared information within the training
domain without adapting the encoder to each target. It does not rule out
implementation limitations or establish a general transfer benefit.

Claude's "equally well" wording and general claim that ensembles are more reliable
were not adopted. The draft retains descriptive averages, heterogeneous effects,
small bird advantages and the distinction between prediction and attribution.
No fitting or raw-response analysis was conducted. The preceding source and
outputs are archived in `manuscript/build/archive/20261018-before-claude-round4/`;
current bindings and checks are in
`evidence/cross_case_synthesis/20261018/claude-round4-verification.json`.

## Final verdict and publication statements

Claude's message 2006 accepts the draft for both intended audiences and accepts
the four scientific qualifications discussed in the previous round. The remaining
changes concern authorship, transparent AI contributions and project correspondence,
plus two small clarity edits to Table 1 and the transferred-threshold TSS sentence.

Jessie C. Buettel is added to the draft author list and named with Barry W. Brook
as a camera-data custodian. Institutional profiles and a university dataset record
support the contact details and identifiers; the current ANU profile supplies
Jessie's affiliation. Both authors' final read remains pending. The disclosure
credits AI design and interpretation, implementation, diagnostic calculation,
literature checking, figures and drafting without attributing all scientific
decisions or protocol approvals to both human authors.

The shared dSDM board was exported through message 2006: 46 messages in one
discussion. No message text was redacted. Original identities, missing model
metadata, relayed human quotations and subsequent corrections are preserved.
An independent factual/privacy check and an independent statement review found
no material issue requiring another manuscript revision. The publication
preparation record gives the scope, package location and remaining DOI steps.
No archive upload, public release or submission has occurred.
