# Manuscript

The working Ecography manuscript was reconstructed on 13 November 2026 in
stages reviewed by Claude and Codex. `text/main.md` carries the accepted
argument, one table and citations to four figures. `text/figures.md` defines
the four figure captions. The article and Supporting information are author
review drafts; no submission, release or DOI assignment is made by this build.

## Current displays and evidence

The four displays follow `reconstruction/01b-display-items.md`:

1. Public study boundaries and the three-learner design.
2. Paired species-level pretraining gains in development and geographic assessment.
3. Neural models and fixed neural/conventional averages in the new bird regions.
4. Recording richness and the crossed Tasmania training/evaluation comparison.

`evidence/reconstruction/20261113/` contains the extracted figure data,
resampling ranges and source bindings. The new ranges are a post hoc reporting
extension over accepted species aggregates. They describe composition of the
observed species panels conditional on fitted models, rather than confidence
intervals. No fits or raw observations are required for plotting.

Supporting information is assembled as one document from `text/supplement.md`,
`text/tasmania-sensitivity.md`, `text/survey-only-and-design.md` and
`text/data-sources.md`. It preserves the original S1–S11 material and adds
all-case TSS, extended ranges, the former main Table 2, five-endpoint learning
curves and controls, absolute AUC by extent, and every primary species' paired
contrasts. Numbered tables provide navigation inside that document; the main
article cites only “Supporting information”.

Accepted historical analyses and their dated receipts are unchanged. Do not
run the historical report generators to regenerate these revised manuscript
sources: some replace the old S1 source. The historical drafting and release
records remain in `docs/plan/ManuscriptDrafting-20261018.md` and
`docs/plan/PublicationPreparation-20261018.md`.

## Build

The shared builder is `~/work/makedoc`. Set up its one Python dependency in
the ignored manuscript-only environment, without changing system Python:

```sh
make -C manuscript setup
make -C manuscript all check
make -C manuscript all check PROFILE=supplement
```

`requirements-build.txt` pins PyYAML. The wrapper selects that environment
and gives each profile its own local cache and LaTeX directory. PDF, Word
and build manifests are written to the ignored `manuscript/build/` directory:
`dsdm_manuscript.{pdf,docx}` and `dsdm_supplement.{pdf,docx}`. The wrapper's
Word postprocessor preserves document text and images while applying the
review table layout. Final visual checks use the PDF renders.

Profiles identify Ecography. Its official [dependent CSL style](https://github.com/citation-style-language/styles/blob/af0aea3fffd44fe798cce9285598d0d5cf62ef23/dependent/ecography.csl)
declares Oikos as its independent parent; the profiles therefore use the
complete official `csl/oikos.csl`, with `csl/ecography.csl` retained as the
journal identity. Both files and the source revision are bound in
`evidence/reconstruction/20261113/citation-style.json`. The current parent
prints complete author lists. The [journal guidelines](https://nso-journals.org/author-guidelines)
specify generic Supporting information citations in the main text.

## Regenerate the current figures

From the repository root, using the existing locked analysis environment
for the Python scripts and the host R for plotting:

```sh
.venv/bin/python scripts/reconstruction_display_data.py
.venv/bin/python scripts/plot_reconstruction_design.py
Rscript scripts/plot_reconstruction_results.R
```

The extraction checks frozen source hashes and reproduces the earlier bird
resampling ranges before writing the new small figure-data tables. It uses
retained aggregate metrics only; some original aggregate and public-boundary
inputs must first be staged at their recorded paths. Plotting Figures 2–4
needs only the small public CSVs in the reconstruction evidence directory.
Figure 1 uses public IBRA 7.1 and ASGS boundaries and `rsvg-convert`; its five
patch positions are explicitly schematic. Analysis geometry is unchanged.
Each figure is supplied as a vector PDF and 300 dpi PNG; Figure 1 also has SVG.

The original assembly verification record is
`evidence/reconstruction/20261113/assembled-display-verification.json`. The
14 November figure corrections and current outputs are bound in
`evidence/reconstruction/20261114/figure-revision-verification.json`.
The scientific evidence ledger remains `evidence-ledger.md`.
