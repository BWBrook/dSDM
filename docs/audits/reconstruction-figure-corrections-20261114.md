# Final figure corrections

Codex (`gpt-6.1-sol`), 14 November 2026. Applies Claude's review in
correspondence thread 162/message 3380, based on `803860d`.

- **Figure 4a:** development, SEH and NNC have separate labelled vertical
  axes. Every observed species point and all accepted means/ranges remain.
  The development decline is visible, and the caption states that scales
  differ. No clipping or replacement estimates were used.
- **Figure 4b:** the learner legend occupies a separate row below both panels,
  clear of tick marks and axis labels.
- **Figure 2:** regional values sit adjacent to their points, above positive
  and below negative means. The middle setting reads “within bioregions and
  folds”.
- **Figure 1:** the duplicate caveat footnote is removed. The caption identifies
  the grey mammal source as a mainland subset of the bird domain. This is more
  exact than calling the boundaries identical: the bird domain completes the
  Brigalow Belt South region beyond the original mainland extent. SVG
  comparison confirms that only the footnote line changed.

Claude's new mainland transfer wording is supported: the mean AUCs are
0.5559585, 0.5714716 and 0.5836915, with conventional models highest.
“Close to chance” is a descriptive comparison with AUC 0.5. The main text
from `803860d` is retained without further editing.

An independent read-only review checked the wording, geometry relationship,
revised PNGs and captions; it found no remaining material issue. The parent
inspected the final affected PDF pages (21, 22 and 24). The rebuilt article
remains 24 pages, without overfull-box or missing-glyph warnings.
`make -C manuscript all check` passes, including citation checks and the Word
postprocessor's text/image preservation check. PDF was the visual review
format.

All seven plot-data CSVs and both Figure 3 files are byte-identical to the
reviewed revision. Supporting information sources and its 36-page PDF/Word
outputs match the prior verified build. No estimates, resampling, fitting or
raw-response access were needed for these corrections. Earlier dated records
remain intact; current bindings are in
`evidence/reconstruction/20261114/figure-revision-verification.json`.

The article and Supporting information are ready for Barry's final read.
No release, submission or DOI assignment was made.

Next: Barry — final manuscript read.
