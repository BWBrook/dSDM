# Ecography format and presentation audit

Date: 12 November 2026. Manuscript audited at commit `dc04d91`.

Method: a Claude Sonnet subagent ran the audit, briefed by Claude Opus 5.5. Opus then checked the key claims against the repository and against the NSO guideline pages. The subagent edited nothing. This is a record to use during revision.

## Decisions

- Target journal: **Ecography**. Barry and Claude agreed this in chat on 12 November 2026. MEE was considered and set aside, because the paper's core design is an ablation, not a new method, and the current framing (transfer to new regions) already sits in Ecography's core scope.
- Anonymity, from Barry in chat on 12 November 2026: "Anonymity is really there because some authors request it, but what we'll do is 'give reviewers an anonymised mirror' as you suggest. We can work that out more fully when close to submission."

## Guideline sources

- Journal page: <https://nso-journals.org/ecography-for-authors>
- Nordic Society Oikos author guidelines: <https://nso-journals.org/author-guidelines>
- Claude re-checked the word and display-item limits, the rule on citing supporting information, the all-authors reference rule and the anonymous main-text rule directly against these pages on 12 November 2026.
- Wiley's AI-disclosure page, which the NSO guidelines link to, was not read.

## Guideline facts (Original Research Paper)

- Main text: at most 5000 words, counted from the Introduction through the Discussion. Legends, abstract and references are excluded.
- Display items: at most 6 figures, tables or boxes in total.
- Abstract: at most 300 words, with no references and no unexplained abbreviations.
- Headings: at most 3 levels.
- Layout: single column, double spaced, continuous line and page numbers, no footnotes.
- Style: avoid the passive voice.
- Review is double-anonymised. The main text file must contain no author names or affiliations; those go on a separate title page.
- These statements are entered in the submission form, not the main text: data availability, conflict of interest, funding, acknowledgements and the significance statement. CRediT contributions are required at revision.
- The AI-use statement goes at the end of the main text and must name the tools and what each was used for.
- Data and code must be supplied at first submission, as an anonymous link or an additional file for review. After acceptance they go to a public archive with a persistent identifier.
- Supporting information is uploaded as separate files and published as received. The main text may cite it only as "Supporting information". Journal staff remove citations to its subsections or specific details. It should carry minimal references.
- References: any style, but the list must be alphabetical and give every author, with no "et al." in the list. In-text citations are ordered chronologically, for example (Smith 1999, Dunn 2000), and use "et al." for three or more authors. No numbered citations at revision.
- Figures: label panels (a), (b) and use colour-blind-safe palettes.
- Title: brief and informative, preferably stating the main result.
- Keywords: no specific rule found.

## Comparator papers

| Paper | DOI | Relevance | Read |
|---|---|---|---|
| Basile et al. 2026, Harnessing the power of machine and deep learning for transferring joint species distribution models | 10.1002/ecog.08269 | Deep-network joint SDMs compared with elastic net and RF, transferred from continental to regional extent. The closest neighbour to this paper, and one we must engage with. | Full text |
| Velazco et al. 2023 (issue 2024), How far can I extrapolate my species distribution model? | 10.1111/ecog.06992 | SDM extrapolation; question-style title | Full text |
| Huang et al. 2024 (vol. 2025), Cross-validation matters in species distribution models | 10.1111/ecog.07354 | Random versus spatial validation | Full text |
| Gaget et al. 2025, Reviewing and benchmarking ecological modelling practices in the context of land use | 10.1002/ecog.07745 | Benchmarking and model-design practice; the weakest topical match | Full text |
| Erickson & Smith 2023, Modeling the rarest of the rare | 10.1111/ecog.06500 | Joint versus single-species SDMs, borrowing strength across species | bioRxiv preprint only; structural comparison is low confidence |

Pili et al. 2025 (10.1002/ecog.08002, on transferability and sampling bias) is relevant. Its identity was confirmed through Crossref, but the full text could not be accessed. Read it before revision.

## Hard requirements the manuscript currently breaks

1. **Anonymity.** `main.md` names Barry W. Brook, gives both custodians' email addresses, links `github.com/BWBrook/dSDM` and names Brook in the AI statement. The repository is public, so reviewers need an anonymised mirror (see Decisions above). The AI statement and the data statement must both be anonymised.
2. **Supporting information citations.** There are about 10 citations of specific supplement items, such as Table S1, S1f, S2, S3, S10 and S11, and Supplementary Methods S4. All must become "Supporting information", with the essential content moved into the main text where it matters.
3. **Reference list.** `manuscript/csl/oikos.csl` sets `et-al-min="3"` in the bibliography, so the list prints "et al.". The bibliography must list every author.
4. **End matter.**
   - The data availability text belongs in the submission form.
   - Funding, conflict of interest, acknowledgements and CRediT contributions are missing everywhere.
   - The data statement still says the repository is "currently private", which became false when the repository went public.
5. **Data and code at first submission.** These must reach reviewers through the anonymised mirror. The private camera-trap data need a stated access route or exception.
6. **Passive voice.** The guidelines discourage it, and the main text has roughly 50 passive constructions.

Already compliant: about 4,650 words from the Introduction through the Discussion, leaving roughly 350 words of headroom; 5 display items (3 figures and 2 tables) against the cap of 6; a 279-word abstract; 3 heading levels; keywords present; panels labelled.

## Softer contrasts with peer norms, most consequential first

1. **Reference depth.** The manuscript cites 24 works; the comparators cite roughly 55–108. It misses the Ecography conversation on transferability, extrapolation, deep-learning joint SDMs and spatial cross-validation. Add about 20–30 targeted references, and engage directly with Basile et al. 2026 and Pili et al. 2025.
2. **No map or design schematic.** Three of the four fully read comparators have a study-area map or a design or workflow diagram, and the fourth has a flowchart. This paper has three cases, three held-out regions and several prediction settings, but no picture of any of them. Add one combined map and schematic. That reaches the cap of 6 display items unless Table 1 moves to supporting information.
3. **Uncertainty reporting.** The comparators report confidence intervals or test statistics. This paper reports mean differences to four decimal places, with resampling ranges that it says are not confidence intervals. Add bootstrap intervals over species, folds and seeds, and keep the honest caveats.
4. **Key numbers live in the supplement.** The absolute AUCs sit in Table S1f. Move the core absolute-performance numbers into the main text. This also follows from hard requirement 2.
5. **Supplement size.** The supplement is 4 files of about 7,700 words, with Tables S1–S10; the comparators use one general file. Consolidate it and trim.
6. **Title.** The current title is a question. The guidelines prefer a statement of the result. One candidate: "Multi-species pretraining does not improve species distribution models in new regions". A final title should also carry the positive finding about networks and ensembles.
7. **Keywords.** Add "species distribution model" and "deep learning" or "neural network".
8. **Voice.** The main text uses "we" or "our" about 15 times, against far more in the comparators. Use the first person, and cut stacked caveats.
9. **Abstract.** Recast the four numbered paragraphs as one paragraph of about 250–300 words, with two or three headline numbers.
10. **Subsection headings.** These are full-sentence findings; most comparators use noun phrases, though Basile also uses sentences. Minor.

Already matching peer norms: separate Introduction, Methods, Results and Discussion sections; caption length (96–102 words here, against 73–148 in the comparators); keywords after the abstract.

## Features unique to this manuscript

- **A detailed AI-use statement.** None of the fully read comparators has one. It is within NSO rules and a strength. For review, anonymise it while keeping systems, versions and roles.
- **Explicit provenance language,** for example "fixed before examining withheld responses" and "post hoc". A strength.
- **A deliberately null headline.** Ecography is wary of single-region studies, so frame the result as a general finding about transfer, not an Australian case study.

## Overall fit

Structure, length and caption style already sit close to Ecography norms, and the topic is squarely in scope. The obstacles are procedural: anonymisation, how supporting information is cited, a complete reference list and data supplied at submission. The substantive gaps are the thin reference list, the missing map and schematic, the missing uncertainty intervals and the framing of generality. None of these changes the science.
