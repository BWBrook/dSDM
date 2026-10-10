# Bird species-composition resampling for the manuscript

8 October 2026. Post hoc reporting plan, fixed before generating its resampling
outputs. This responds to Claude's correspondence message 1167 and the question
about the statistical objection to intervals. It uses accepted aggregate
results only and does not fit, rescore or select models.

## Purpose and limits

Describe sensitivity of the primary bird panel's mean contrasts to empirical
reweighting of its observed species. This is not a confidence interval or a
measure of fitting, spatial-sampling, model-selection or population uncertainty.
The 73 species were selected for support and were not exchangeable random draws
from a defined species population. The original fixed-panel means remain the
reported estimates; resampling does not create additional ecological replicates.

Only four comparisons are included: inner and equal-region outer AUC, each for
fine-tuning minus target-only and fine-tuning minus selected conventional.
Mammal panels, regional subpanels, learning curves, recorded-richness analyses
and Figure 2 receive no resampling ranges in this tranche.

## Fixed inputs

- `evidence/cross_case_synthesis/20261005/revision-01/summary.json`, SHA-256
  `6834e34c74767864686862734f57a64a2ac10b324fcdadab89797e1cecbe0fd2`.
- `data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json`,
  SHA-256 `b3abdb006fb7d384445db376d5ba3f0f7b48afd170982494f88ff20ef612e804`.

Require identical species sets for the 73 inner, NCP, SEH, NNC and equal-region
outer rows. Use species names in ascending lexical order. Require finite AUCs,
one canonical focal block per species, and exact accepted input hashes.

## Species resampling

Use NumPy PCG64 with `SeedSequence(20261008).spawn(2)`: stream 0 for species and
stream 1 for focal blocks. Record the NumPy version and stream identities. Fix
100,000 replicates. For each species replicate, sample 73 species IDs with
replacement once. Carry the complete inner and three-region record for all
methods jointly. Reuse the same IDs across methods, regions, assessments and
comparators. Never resample these components independently.

Inner AUC remains the accepted mean-fold value within species. Outer AUC first
averages NCP, SEH and NNC within species, then averages the sampled species.
Calculate the paired method differences before the equal-species mean. Report
the 2.5th and 97.5th percentiles of replicate means, using linear interpolation
(R type 7 / NumPy `method="linear"`). Name the result a **central 95%
species-composition resampling range**. Do not calculate p-values, coverage,
probabilities of benefit or significance flags.

## Focal-block width check

Use the same 100,000 replicates and quantile rule, but only for the two inner
contrasts. Each replicate draws ten block IDs with replacement and includes all
primary-panel species in each selected block occurrence. Calculate the sum of
their contrasts divided by their total count. Do not average block means
equally. The primary-panel block sizes, in block-ID order 0–9, are
6, 4, 3, 9, 7, 8, 9, 10, 7 and 10. The two comparators share each block draw.

These hash-balanced blocks share block-specific pretrained objects. They are
neither spatial nor taxonomic clusters and do not capture all dependence from
common folds, predictors, architecture selection, geography or overlapping
auxiliary pools. Ten blocks provide limited tail resolution. Present both
resampling schemes and their widths; do not choose the wider as a supposedly
conservative inferential interval.

## Presentation and verification

Keep the species points, fixed-panel mean, median and IQR in Figure 1. Add thin
whiskers only to bird means. Name the range explicitly in the legend and define
its conditional meaning in the caption. Put all numerical ranges and the
focal-block width comparison in a supplementary table, with a main Methods
description. A range excluding zero indicates sign stability under this
empirical reweighting alone.

Before drawing, reproduce the accepted unsampled means and the equal-region
outer values. One copy of every block must reproduce the original inner mean.
Check pairing, mapping and inventory failures with small synthetic examples.
Reproduce output bytes from a second deterministic execution; independently
check the numerical summaries. Preserve the earlier synthesis and its receipts.
Save new aggregates under `evidence/cross_case_synthesis/20261008/`, binding the
plan, source and input hashes. Record resampling output and document-build
verification separately from the original model-fitting evidence.
