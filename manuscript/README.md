# Manuscript

This directory is a repo-local manuscript workspace backed by the shared `makedoc` builder in `/Users/bwbrook/work/makedoc`.

The active source is `text/main.md`, completely rewritten on 18 October 2026
through three substantive review rounds with Claude. The question title,
abstract and argument are written for both an informed generalist editor and
specialist readers. Barry's subsequent humanisation request prompted a further
revision of the framing, flow and repeated caveats, with an independent
scientific check. Claude's fourth review then prompted simpler terminology,
finding-led Results and a new Table S1f retaining the absolute AUCs moved out
of the prose. Three Results sections distinguish the pretraining
increment, evaluation extent and model averaging, and the definition of
negative observations. The paper contains three figures and two main tables.
The earlier May 2026 conversion and original draft remain in Git history.
`evidence-ledger.md` records result sources, prospective versus post hoc status,
and the remaining steps needed before submission.

## Current review status — 18 October

The [drafting record](../docs/plan/ManuscriptDrafting-20261018.md) documents the
full rewrites, Claude's reviews and the scientific qualifications retained
through disagreement. The manuscript now includes the post hoc survey-only
Tasmania panel as a crossed training/evaluation comparison, with full metrics
and species support in Tables S10–S11. Supplementary Methods S4 documents
dataset products, acquisition dates and remaining source-provenance gaps.

PDF and Word outputs are `build/dsdm_manuscript.{pdf,docx}` and
`build/dsdm_supplement.{pdf,docx}`. Final source/output bindings and checks are
in `../evidence/cross_case_synthesis/20261018/final-statements-verification.json`.
Claude's final read (message 2006) accepted the draft for both audiences.
The final statement revision adds Jessie C. Buettel, camera-data custodianship
and contacts, and a fuller account of the AI systems' actual contributions.
The dSDM-only correspondence review package is prepared locally under
`../outputs/correspondence/dsdm-20261018/`; it has not been published or assigned
a DOI. See the [publication preparation record](../docs/plan/PublicationPreparation-20261018.md).
The preceding fourth-round bindings remain in
`../evidence/cross_case_synthesis/20261018/claude-round4-verification.json`,
with source and document outputs preserved in `build/archive/20261018-before-final-statements/`.
The preceding humanisation record remains
`../evidence/cross_case_synthesis/20261018/humanisation-verification.json`,
with its source and outputs archived in `build/archive/20261018-before-claude-round4/`.
The original delivery record remains
`../evidence/cross_case_synthesis/20261018/draft-delivery-verification.json`,
with its outputs archived in `build/archive/20261018-before-humanisation/`.
Earlier document outputs were archived in `build/archive/20261011/`; prior
analysis receipts retain their original bindings. This is an author-review
draft for both authors' final read. Public deposits and their identifiers,
final author confirmation and journal/style remain to be completed. Source
metadata gaps are disclosed in Supplementary Methods S4.

## Build

From the repository root:

```sh
make -C manuscript validate
make -C manuscript all
```

The 18 October build used the existing Python 3.14 runtime (with PyYAML) and
repo-local caches, avoiding global runtime changes:

```sh
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH make -C manuscript all check \
  PROFILE_CACHE_DIR="$PWD/manuscript/.cache" \
  PDF_ENGINE_OUTPUT_DIR="$PWD/manuscript/.cache/latex"
```

Outputs are written to `manuscript/build/`, which is ignored by git. The default profile is `draft`; use `PROFILE=submission` for the stricter lint profile once citations and references have been cleaned up.

The repo wrapper applies `../scripts/format_review_docx.py` after Word builds:
A4 margins, compact table text, intact rows and repeated headers. It checks
that text and images remain unchanged, then refreshes the build manifest.
PDF and Word pagination can differ; both are review formats.

The synthesis tables and figures can be regenerated from the accepted
aggregate receipts, without reopening responses or fitting models:

```sh
python3 scripts/cross_case_synthesis.py --tasmania-summary evidence/tasmania_outer_assessment/20261005/receipt.json
uv run --locked python scripts/bird_composition_resampling.py
Rscript scripts/plot_cross_case_synthesis.R
Rscript scripts/plot_bird_extent_synthesis.R
python3 scripts/cross_case_supplement.py
```

Run those commands from the repository root only when intentionally rebuilding
historical reporting outputs; `cross_case_supplement.py` writes the original
S1 supplement source. Preserve historical source and receipt bindings. The
18 October figures and added tables can be checked without regenerating old
reports:

```sh
Rscript scripts/plot_cross_case_synthesis.R
Rscript scripts/plot_bird_extent_synthesis.R
Rscript scripts/plot_bird_recording_richness.R
python3 scripts/check_survey_only_supplement.py
```

Revised reporting outputs are
under `evidence/cross_case_synthesis/20261005/revision-01/`; the first review
summaries are preserved. Bird composition-resampling outputs are under
`evidence/cross_case_synthesis/20261008/`; their fixed reporting plan and limits
are in `docs/plan/BirdCompositionResampling-20261008.md`. Build the supplementary PDF and Word file with
`make -C manuscript PROFILE=supplement all`. The underlying bird extent
reproduction uses private saved predictions and already-opened responses:
`uv run --locked python3 scripts/goal052_extent_review.py`.

## Tasmania sensitivity

The completed analysis and claim limits are in
[the results report](../docs/plan/TasmaniaPseudoabsenceResults-20261009.md).
The report generator reads verified aggregates only:

```sh
python3 scripts/tasmania_pseudoabsence_report.py
make -C manuscript all
make -C manuscript PROFILE=supplement all
```

Run from the repository root. Existing reporting files must match exactly;
intentional reporting changes require preserving the prior source and receipt.
Do not rerun fitting, collection or held-response scoring to rebuild documents.
Tables S5–S9 live in `text/tasmania-sensitivity.md`, the second supplement
source. Eight map plates and the numerical tables are under
`evidence/tasmania_pseudoabsence/20261009/`; a combined map PDF is in
`build/dsdm_tasmania_sensitivity_maps.pdf`. The final delivery verification
binds the manuscript, supplement and map outputs to the completed assessment.

## Layout

- `settings/build.yaml`: `makedoc` profiles with paths relative to this repo.
- `text/main.md`: active cross-case manuscript review draft.
- `text/figures.md`: `makedoc` figure blocks.
- `text/supplement.md`: generated supplementary methods and descriptive tables.
- `text/tasmania-sensitivity.md`: verified sensitivity methods and Tables S5–S9.
- `text/survey-only-and-design.md`: post hoc survey-only methods and Tables S10–S11.
- `text/data-sources.md`: data products, provenance and unresolved source metadata.
- `figures/`: tracked source figures for the paper.
- `references/refs.yaml`: Pandoc YAML bibliography.
- `csl/oikos.csl`: placeholder journal style copied from the `makedoc` testbed.
