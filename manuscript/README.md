# Manuscript

This directory is a repo-local manuscript workspace backed by the shared `makedoc` builder in `/Users/bwbrook/work/makedoc`.

The active source is `text/main.md`. It was substantially restructured on
2026-10-05 around the completed cross-case tests of multi-species pretraining,
then revised to include the matched mainland inner result and Fable’s review.
On 9 October it incorporated the independently verified, seven-endpoint
Tasmania pseudoabsence-removal sensitivity.
The earlier May 2026 conversion and original draft remain in Git history.
`evidence-ledger.md` records result sources, prospective versus post hoc status,
and the remaining steps needed before submission.

## Current review status — 11 October

The [review response](../docs/plan/ClaudeReviewResponse-20261011.md) reports the
independently verified post hoc survey-only Tasmania panel. Its result changes
the interpretation of the original mixed-negative score decline; it does not
change the completed fits or original assessment. The manuscript body has not
been expanded with this panel. The [two-page paper plan](../docs/plan/PaperPlan-20261011.md)
sets out a focused rewrite for Barry’s agreement on the headline and allocation.
Its PDF is `build/dsdm_paper_plan_20261011.pdf`.

The 9 October delivery verification remains bound to the versions in commit
`6e4df9f`; this README and the handover now record the follow-up. Existing
manuscript, supplement and map builds retain their prior hashes.

## Build

From the repository root:

```sh
make -C manuscript validate
make -C manuscript all
```

Outputs are written to `manuscript/build/`, which is ignored by git. The default profile is `draft`; use `PROFILE=submission` for the stricter lint profile once citations and references have been cleaned up.

The synthesis tables and figures can be regenerated from the accepted
aggregate receipts, without reopening responses or fitting models:

```sh
python3 scripts/cross_case_synthesis.py --tasmania-summary evidence/tasmania_outer_assessment/20261005/receipt.json
uv run --locked python scripts/bird_composition_resampling.py
Rscript scripts/plot_cross_case_synthesis.R
Rscript scripts/plot_bird_extent_synthesis.R
python3 scripts/cross_case_supplement.py
```

Run those commands from the repository root. Revised reporting outputs are
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
- `figures/`: tracked source figures for the paper.
- `references/refs.yaml`: Pandoc YAML bibliography.
- `csl/oikos.csl`: placeholder journal style copied from the `makedoc` testbed.
