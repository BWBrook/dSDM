# Manuscript

This directory is a repo-local manuscript workspace backed by the shared `makedoc` builder in `/Users/bwbrook/work/makedoc`.

The active source is `text/main.md`, converted from `temp/dSDM_MS_draft.docx` on 2026-05-27 with Pandoc 3.9.0.2. The conversion is intentionally conservative: section labels were promoted to Markdown headings, the `makedoc` author placeholder was added, and original draft wording was otherwise left intact.

## Build

From the repository root:

```sh
make -C manuscript validate
make -C manuscript all
```

Outputs are written to `manuscript/build/`, which is ignored by git. The default profile is `draft`; use `PROFILE=submission` for the stricter lint profile once citations and references have been cleaned up.

## Layout

- `settings/build.yaml`: `makedoc` profiles with paths relative to this repo.
- `text/main.md`: converted manuscript text.
- `text/figures.md`: future `makedoc` figure blocks.
- `figures/`: tracked source figures for the paper.
- `references/refs.yaml`: Pandoc YAML bibliography.
- `csl/oikos.csl`: placeholder journal style copied from the `makedoc` testbed.
