#!/usr/bin/env Rscript
# Figure 3: descriptive FT-minus-selected-conventional AUC by recorded
# background richness.  This script reads only the compact accepted aggregate
# table in evidence/cross_case_synthesis/20261018/recording-richness.csv.
#
# Caption guidance: Points show equal-species mean ROC-AUC differences between
# full fine-tuning and the selected conventional learner. The inner panel is
# the 59-species primary panel with support in all three bins. Outer panels use
# common three-bin support within each region: NCP has no supported species,
# SEH has 38, and NNC has 55. Labels give positive/evaluated species support
# (SEH 20/38, 15/38, 13/38; NNC 39/55, 35/55, 15/55); inner labels also
# give positive-species counts. These are descriptive
# contrasts without inferential intervals; richness is recorded background
# support, not a predictor or a causal measure of effort.

args <- commandArgs(trailingOnly = TRUE)
repo_root <- if (length(args)) normalizePath(args[[1]]) else normalizePath('.')
source_csv <- file.path(repo_root, 'evidence/cross_case_synthesis/20261018/recording-richness.csv')
figure_dir <- file.path(repo_root, 'manuscript/figures')
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)

d <- read.csv(source_csv, stringsAsFactors = FALSE, na.strings = c('', 'NA'),
              check.names = FALSE)
stopifnot(nrow(d) == 12L)
stopifnot(identical(sort(unique(d$richness_bin)), c('10_24', '100_plus', '25_99')))
bin_order <- c('10_24', '25_99', '100_plus')
bin_labels <- c('10–24', '25–99', '≥100')
d$richness_bin <- factor(d$richness_bin, levels = bin_order)
d$mean_auc_difference <- as.numeric(d$mean_auc_difference)
d$support_n <- as.integer(d$support_n)
d$panel_n <- as.integer(d$panel_n)
d$positive_n <- as.integer(d$positive_n)

# Guard the authored table against accidental panel mixing or silent support
# drift.  The values are the accepted aggregate values, not recalculated
# estimates or intervals.
inner <- d[d$stage == 'inner_discovery', ]
outer <- d[d$stage == 'outer_primary_by_region', ]
stopifnot(nrow(inner) == 3L, nrow(outer) == 9L)
stopifnot(all(inner$region == 'all'), all(outer$region %in% c('NCP', 'SEH', 'NNC')))
stopifnot(all(inner$support_n == 59L), all(inner$panel_n == 73L))
stopifnot(all(inner$positive_n == c(56L, 43L, 19L)))
stopifnot(all(outer$panel_n == 73L))
stopifnot(all(outer$support_n[outer$region == 'NCP'] == 0L))
stopifnot(all(outer$support_n[outer$region == 'SEH'] == 38L))
stopifnot(all(outer$support_n[outer$region == 'NNC'] == 55L))
stopifnot(all(is.na(outer$mean_auc_difference[outer$region == 'NCP'])))
stopifnot(all(!is.na(outer$mean_auc_difference[outer$region != 'NCP'])))
# The outer common-support positive counts are retained from the accepted
# diagnostic summary; the compact source CSV intentionally stores only means
# and denominators.  They are shown as positive/evaluated species labels.
outer_positive <- list(
  SEH = c(20L, 15L, 13L),
  NNC = c(39L, 35L, 15L)
)

expected_inner <- c(0.005022962719855718, 0.0019480126381936898,
                    -0.003921530237560449)
stopifnot(max(abs(inner$mean_auc_difference - expected_inner)) < 1e-15)
expected_outer <- list(
  SEH = c(-0.003807555364, -0.013950750790, -0.028264412786),
  NNC = c(0.014775304039, 0.006021758649, -0.025870759025)
)
for (region in c('SEH', 'NNC')) {
  got <- outer$mean_auc_difference[outer$region == region]
  stopifnot(max(abs(got - unname(expected_outer[[region]]))) < 1e-12)
}

col_dark <- '#263238'
col_grid <- '#E5E8EA'
col_zero <- '#5B6267'
col_inner <- '#286C9E'
col_region <- c(NCP = '#858B8F', SEH = '#BC623C', NNC = '#5D666D')

fmt_value <- function(x) {
  ifelse(is.na(x), 'NA', sprintf('%+.4f', x))
}

draw_inner <- function() {
  plot(NA, xlim = c(0.55, 3.45), ylim = c(-0.008, 0.0085),
       xlab = '', ylab = 'FT − selected conventional AUC', axes = FALSE,
       family = 'sans', col.axis = col_dark, col.lab = col_dark)
  abline(h = seq(-0.005, 0.005, by = 0.005), col = col_grid, lwd = 0.7)
  abline(h = 0, col = col_zero, lty = 2, lwd = 0.8)
  axis(1, at = 1:3, labels = bin_labels, tick = FALSE, col = col_dark)
  axis(2, at = c(-0.005, 0, 0.005),
       labels = c('−0.005', '0', '+0.005'), las = 1, col = col_dark)
  box(bty = 'l', col = col_dark)
  vals <- inner$mean_auc_difference[match(bin_order, inner$richness_bin)]
  points(1:3, vals, pch = 16, col = col_inner, cex = 1.2)
  text(1:3, vals + ifelse(vals >= 0, 0.0010, -0.0010),
       labels = sprintf('%s\n%d/%d', fmt_value(vals),
                        inner$positive_n[match(bin_order, inner$richness_bin)],
                        inner$support_n[match(bin_order, inner$richness_bin)]),
       col = col_dark, cex = 0.72, xpd = NA)
  mtext('a  Development: 59 species with support in every bin', 3,
        line = 1.0, adj = 0, font = 2, cex = 0.92, col = col_dark)
  mtext('Labels: mean contrast; positive species / evaluated species (n = 59)',
        3, line = 0.05, adj = 1, cex = 0.68, col = '#5B6267')
}

draw_outer_region <- function(region, show_y = TRUE) {
  plot(NA, xlim = c(0.55, 3.45), ylim = c(-0.034, 0.018),
       xlab = '', ylab = if (show_y) 'FT − selected conventional AUC' else '',
       axes = FALSE, family = 'sans', col.axis = col_dark, col.lab = col_dark)
  abline(h = seq(-0.03, 0.015, by = 0.015), col = col_grid, lwd = 0.7)
  abline(h = 0, col = col_zero, lty = 2, lwd = 0.8)
  axis(1, at = 1:3, labels = bin_labels, tick = FALSE, col = col_dark)
  if (show_y) {
    axis(2, at = c(-0.03, -0.015, 0, 0.015),
         labels = c('−0.030', '−0.015', '0', '+0.015'), las = 1,
         col = col_dark)
  }
  box(bty = 'l', col = col_dark)
  dd <- outer[outer$region == region, ]
  vals <- dd$mean_auc_difference[match(bin_order, dd$richness_bin)]
  col <- unname(col_region[[region]])
  keep <- !is.na(vals)
  points(which(keep), vals[keep], pch = 16, col = col, cex = 1.15)
  # Support and positive counts are printed directly beside each point,
  # avoiding any implied continuous relationship between the bins.
  counts <- outer_positive[[region]]
  text(which(keep), vals[keep] + ifelse(vals[keep] >= 0, 0.0023, -0.0023),
       labels = sprintf('%s\n%d/%d', fmt_value(vals[keep]), counts[keep],
                        dd$support_n[match(bin_order, dd$richness_bin)][keep]),
       col = col_dark, cex = 0.66, xpd = NA)
  mtext(sprintf('%s (n = %d)', region, unique(dd$support_n)),
        3, line = 0.55, font = 2, cex = 0.86, col = col_dark)
  if (region == 'SEH') {
    mtext('b  Held regions: species with support in every bin',
          3, line = 1.75, adj = 0, font = 2, cex = 0.88, col = col_dark)
  }
  if (region == 'NNC') {
    mtext('NCP: no common support (0/73)',
          3, line = 1.75, adj = 1, cex = 0.74, col = '#5B6267')
  }
}

render <- function() {
  layout(matrix(c(1, 1, 1, 1, 2, 2, 3, 3), nrow = 2, byrow = TRUE),
         heights = c(1, 1.3))
  par(mar = c(3.7, 6.3, 2.4, 1.1), oma = c(1.0, 0, 2.0, 0),
      mgp = c(4.4, 0.55, 0), tcl = -0.22, las = 1)
  draw_inner()
  par(mar = c(3.7, 6.3, 2.4, 1.0))
  draw_outer_region('SEH', show_y = TRUE)
  par(mar = c(3.7, 1.0, 2.4, 1.0))
  draw_outer_region('NNC', show_y = FALSE)
  mtext('Other recorded donor species in background cells', side = 1,
        outer = TRUE, line = 0.05, cex = 0.86, col = col_dark)
}

pdf(file.path(figure_dir, 'bird-recording-richness.pdf'), width = 7.2, height = 6.2,
    pointsize = 10, family = 'Helvetica')
render()
dev.off()

png(file.path(figure_dir, 'bird-recording-richness.png'), width = 7.2, height = 6.2,
    units = 'in', res = 300, pointsize = 10, type = 'cairo')
render()
dev.off()

cat(sprintf('wrote %s and %s from %s\n',
            file.path(figure_dir, 'bird-recording-richness.pdf'),
            file.path(figure_dir, 'bird-recording-richness.png'), source_csv))
