#!/usr/bin/env Rscript
# Descriptive mean AUC and contrasts, from the post hoc aggregate table.
args <- commandArgs(trailingOnly = TRUE)
repo_root <- if (length(args)) normalizePath(args[[1]]) else normalizePath('.')
d <- read.csv(file.path(repo_root, 'evidence/cross_case_synthesis/20261005/revision-01/bird_extent_plot.csv'), stringsAsFactors = FALSE)
scopes <- c('published_mean_fold', 'pooled_whole_domain', 'region_pooled', 'region_fold', 'outer_equal_regions')
labels <- c('Inner\nmean fold', 'Inner\npooled OOF', 'Inner\nwithin region', 'Inner\nregion x fold', 'Outer\nequal regions')
cols <- c('#286C9E', '#BC623C', '#5D666D')
figure_dir <- file.path(repo_root, 'manuscript/figures')
render <- function() {
  par(mfrow = c(2, 1), mar = c(3.8, 4.5, 3.2, 1.1), oma = c(0.4, 0, 0, 0),
      family = 'sans', las = 1, tcl = -0.22, mgp = c(2.8, 0.55, 0), cex.axis = 0.88)
  plot(NA, xlim = c(0.6, 5.4), ylim = c(0.65, 0.86), xlab = '', ylab = 'Mean ROC AUC', axes = FALSE)
  abline(h = seq(0.65, 0.85, 0.05), col = '#E5E8EA', lwd = 0.7)
  axis(1, at = 1:5, labels = labels, tick = FALSE, cex.axis = 0.88)
  axis(2, at = seq(0.65, 0.85, 0.05), col = '#858B8F')
  mtext('a  Absolute discrimination changes with evaluation scope', 3, line = 1.2, adj = 0, font = 2, cex = 0.98)
  methods <- c('fine_tuned', 'target_only', 'conventional')
  for (j in seq_along(methods)) {
    dd <- d[d$measure == 'auc' & d$series == methods[[j]], ]
    stopifnot(nrow(dd) == 5, setequal(dd$scope, scopes))
    dd <- dd[match(scopes, dd$scope), ]
    points((1:5) + (j-2)*0.11, dd$value, pch = c(16, 17, 15)[[j]], col = cols[[j]], cex = 1.05)
  }
  legend('topright', legend = c('Fine-tuned', 'Target-only', 'Conventional'), pch = c(16, 17, 15),
         col = cols, horiz = TRUE, bty = 'n', cex = 0.81, inset = c(-0.01, -0.02))
  plot(NA, xlim = c(0.6, 5.4), ylim = c(-0.004, 0.018), xlab = '', ylab = 'Mean ROC AUC difference', axes = FALSE)
  abline(h = seq(0, 0.015, 0.005), col = '#E5E8EA', lwd = 0.7)
  abline(h = 0, lty = 2, col = '#555E63')
  axis(1, at = 1:5, labels = labels, tick = FALSE, cex.axis = 0.88)
  axis(2, at = c(0, 0.005, 0.01, 0.015), labels = c('0', '0.005', '0.010', '0.015'), col = '#858B8F')
  mtext('b  Pretraining and fixed-ensemble contrasts', 3, line = 1.2, adj = 0, font = 2, cex = 0.98)
  comparisons <- c('fine_tuned_minus_target_only', 'ft_ensemble_minus_conventional', 'to_ensemble_minus_conventional')
  cc <- c('#286C9E', '#317B66', '#8D648E')
  for (j in seq_along(comparisons)) {
    dd <- d[d$measure == 'contrast' & d$series == comparisons[[j]], ]
    stopifnot(nrow(dd) == 5, setequal(dd$scope, scopes))
    dd <- dd[match(scopes, dd$scope), ]
    stopifnot(all(dd$value >= -0.004 & dd$value <= 0.018))
    points((1:5) + (j-2)*0.11, dd$value, pch = c(16, 15, 17)[[j]], col = cc[[j]], cex = 1.05)
  }
  text(c(4, 5), c(.0057, -.0022), labels=c('68/73 positive', '34/73 positive'), cex=.77, col=cc[[1]])
  legend('topright', legend = c('Fine-tuned - target-only', 'Fine-tuned ensemble - conventional', 'Target-only ensemble - conventional'),
         pch = c(16, 15, 17), col = cc, bty = 'n', cex = 0.74, inset = c(0, -0.03))
}
cairo_pdf(file.path(figure_dir, 'bird-extent-and-ensembles.pdf'), width = 7.2, height = 6.7, pointsize = 10)
render(); dev.off()
png(file.path(figure_dir, 'bird-extent-and-ensembles.png'), width = 7.2, height = 6.7,
    units = 'in', res = 300, pointsize = 10, type = 'cairo')
render(); dev.off()
