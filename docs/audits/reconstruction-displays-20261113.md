# Reconstructed displays and Supporting information

Codex (`gpt-6.1-sol`), 13 November 2026. Implements the accepted display
plan after Claude's assembly in `f62df73`, correspondence thread 162/message
3365. This is an author-review build, with no release or submission.

## Delivered

Four main figures now match the text:

1. **Study design:** public bird and mainland mammal boundaries, three bird
   bioregions and 50 km buffers, Tasmania target, invented five-patch schematic,
   and the three learners/two comparisons.
2. **Pretraining across regions:** paired bird species in mean-fold development,
   within-bioregion-and-fold development rescoring and three-region assessment;
   separate regional means; paired five- and eight-species mammal comparisons.
3. **Networks and averages:** all 73 bird species' new-region contrasts with
   conventional models, for both networks and their fixed 50:50 averages.
4. **Negative evidence:** species-level common-panel richness comparisons and
   the Tasmania training-by-evaluation AUC comparison.

All figures have vector PDFs and 300 dpi PNGs. Figure 1 also has SVG. The map
uses public IBRA/ASGS boundary inputs whose hashes match the frozen records.
It does not use camera locations or response-derived patch masks. Map
simplification affects display geometry only.

The seven small CSVs in `evidence/reconstruction/20261113/` preserve all plotted
species values and summaries. The scripts are
`scripts/reconstruction_display_data.py`, `scripts/plot_reconstruction_design.py`
and `scripts/plot_reconstruction_results.R`. Historical figure files and
analysis receipts remain unchanged.

## Reporting extension and verification

The paired species-composition calculation uses 100,000 draws. The same draw
carries all primary 73-species methods and assessment settings; bins are paired
within each separate common 59-, 38- or 55-species richness panel. Fixed PCG64
streams, ordering and quantiles are recorded in `display-data-verification.json`.
The existing development and geographic bird ranges reproduce. A second
extraction gave byte-identical CSVs and data receipt. These are conditional
species-composition ranges, not confidence intervals. Mammals show species and
means without resampling bars.

The new figure-data tables contain 245 Figure 2 species rows, three regional
means, 292 Figure 3 rows, 456 richness rows, 12 Tasmania means and 96 underlying
Tasmania species scores, plus 20 summary rows. Accepted source hashes,
species sets, means and positive counts pass. No models, raw observations,
saved row-level predictions or new ecological analyses were used.

## Supporting information and build

Supporting information retains S1–S11 and adds all-case TSS, extended ranges,
held-region richness details, the former main Table 2, five-endpoint learning
curves/controls, absolute AUC by extent and all primary species' contrasts.
All 26 original result tables retain their headers and data cells; the
unchanged data-provenance table brings the total preserved original tables
to 27. One old table's column widths were changed for long scientific names.
The existing survey-only checker still matches 336 aggregate rows and 42 exact
summaries.

Table 1 retains all 27 accepted AUC values. Shorter labels, explicit column
widths and a native table caption keep the caption and all nine rows together
on one page. Intended Markdown lists now render as lists. AI disclosure names
the new figure and Supporting information work.

Ecography's official dependent CSL names Oikos as its independent parent.
The profiles now identify Ecography and use the current unmodified official
parent, which prints full author lists; both styles and their source revision
are retained in `citation-style.json`. Main citations use the journal's generic
“Supporting information” wording. Source links and reproduction instructions
are in `manuscript/README.md`.

A manuscript-only environment pins PyYAML, with a separate cache and LaTeX
directory per profile. `make -C manuscript setup`, `make -C manuscript all check`
and `make -C manuscript all check PROFILE=supplement` pass without a system
Python install. Main text/figure lint also passes directly: 28 main and nine SI
citation keys, none unknown. The wrapper verifies that Word formatting
preserves text and image inventory.

PDFs are 24 pages (article) and 36 pages (Supporting information). All pages
were inspected as overviews, with detailed checks of the four figures, main
Table 1, new SI tables and long-name table. There are no missing-glyph warnings
or main overfull boxes. SI retains a 0.111 pt alignment warning and ignored
split-box glue diagnostics; both builds exit successfully and rendered table
cells are retained and readable. Word was built and checked structurally;
PDF was the visual review format.

`assembled-display-verification.json` binds the final sources, figure files,
PDF/Word outputs and checks. The detailed figure/caption review was independent
of the Results plotting author and found no remaining material issue.

## Hand-off

Claude should review the assembled figures, Supporting information and their
integration, then return the complete paper for Barry's final read. The
reviewed correspondence snapshot, anonymous review package and release
identifiers remain release preparation. No DOI or publication is implied.

Next: Claude — review the assembled figures and Supporting information before Barry's final read.
