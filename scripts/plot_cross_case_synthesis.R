#!/usr/bin/env Rscript
# Descriptive species contrasts. Axis range varies by assessment, not comparator.
args <- commandArgs(trailingOnly = TRUE)
repo_root <- if (length(args)) normalizePath(args[[1]]) else normalizePath('.')
d <- read.csv(file.path(repo_root, 'evidence/cross_case_synthesis/20261005/revision-01/case_contrasts.csv'), stringsAsFactors = FALSE)
resampling <- read.csv(file.path(repo_root, 'evidence/cross_case_synthesis/20261008/bird-composition-resampling.csv'), stringsAsFactors = FALSE)
resampling <- resampling[resampling$scheme == 'species', ]
stopifnot(nrow(resampling) == 4L, !anyDuplicated(resampling[c('case', 'comparator')]))
case_order <- c('tasmania_inner', 'tasmania_outer', 'mainland_inner', 'mainland_to_tasmania', 'birds_inner', 'birds_outer')
case_labels <- c('Tasmania: inner CV\n8 mammals', 'Tasmania: outer patches\n8 mammals', 'Mainland: inner CV\n5 mammals', 'Mainland to Tasmania\n5 mammals', 'Birds: inner CV\n73 species', 'Birds: held-out regions\n73 species')
case_colours <- c('#A65C38', '#A65C38', '#486B91', '#486B91', '#337C6B', '#337C6B')
limits <- c(.175, .125, .025, .15, .025, .065)
d <- d[d$case %in% case_order, ]
stopifnot(!anyDuplicated(d[c('case', 'species', 'comparator')]))
figure_dir <- file.path(repo_root, 'manuscript/figures')
render <- function() {
  layout(matrix(1:12, nrow=6, byrow=TRUE), widths=c(1.4, 1))
  par(cex=1, oma=c(4.8, 0, .1, 0), family='sans', las=1, tcl=-.18,
      mgp=c(1.7, .35, 0), cex.axis=.82, xaxs='i', yaxs='i')
  for (i in seq_along(case_order)) {
    for (j in 1:2) {
      comp <- c('target_only', 'conventional')[[j]]
      dd <- d[d$case == case_order[[i]] & d$comparator == comp, ]
      dd <- dd[order(dd$species), ]
      stopifnot(all(is.finite(dd$difference)), all(abs(dd$difference) <= limits[[i]]))
      par(mar=c(1.6, if (j==1) 8.0 else .65, if (i==1) 2.6 else .35, .6))
      ticks <- pretty(c(-limits[[i]], limits[[i]]), n=4)
      ticks <- ticks[abs(ticks) <= limits[[i]]]
      plot(NA, xlim=c(-limits[[i]], limits[[i]]), ylim=c(-.45,.5), axes=FALSE, xlab='', ylab='', bty='n')
      abline(v=ticks, col='#E7E9EA', lwd=.6)
      abline(v=0, col='#555F64', lty=2)
      axis(1, at=ticks, labels=format(ticks, trim=TRUE, nsmall=if (limits[[i]] < .03) 2 else 2), col='#9BA1A5')
      if (j==1) axis(2, at=0, labels=case_labels[[i]], tick=FALSE, line=-.4, cex.axis=.80)
      jitter <- ((seq_len(nrow(dd)) * .61803398875) %% 1 - .5) * .22
      points(dd$difference, jitter, pch=16, cex=.61, col=adjustcolor(case_colours[[i]], alpha.f=.48))
      q <- quantile(dd$difference, c(.25,.5,.75), type=7)
      segments(q[[1]], -.28, q[[3]], -.28, lwd=3, col=case_colours[[i]])
      points(q[[2]], -.28, pch=3, cex=.76, lwd=1.4, col='#172B31')
      if (case_order[[i]] %in% c('birds_inner', 'birds_outer')) {
        rr <- resampling[resampling$case == case_order[[i]] & resampling$comparator == comp, ]
        stopifnot(nrow(rr) == 1L, abs(rr$mean - mean(dd$difference)) < 1e-12,
                  is.finite(rr$lower), is.finite(rr$upper), rr$lower <= rr$upper,
                  max(abs(c(rr$lower, rr$upper))) <= limits[[i]])
        segments(rr$lower, .25, rr$upper, .25, lwd=1.2, col='#172B31')
        segments(c(rr$lower, rr$upper), .22, c(rr$lower, rr$upper), .28, lwd=1.2, col='#172B31')
      }
      points(mean(dd$difference), .25, pch=23, cex=1.10, bg=case_colours[[i]], col='#172B31')
      text(limits[[i]]*.97, .38, paste0(sum(dd$difference>0), '/', nrow(dd), ' positive'), adj=c(1,.5), cex=.65, col='#424B50')
      if (i==1) {
        mtext(if (j==1) 'a  Pretraining increment' else 'b  Comparison with conventional models',
              3, line=1.12, adj=0, font=2, cex=.84)
        mtext(if (j==1) '(fine-tuned − target-only)' else '(fine-tuned − conventional)',
              3, line=.28, adj=0, cex=.70, col='#5B6267')
      }
    }
  }
  par(fig=c(0,1,0,.085), oma=rep(0,4), mar=rep(0,4), new=TRUE)
  plot.new()
  legend(.5, .92, xjust=.5, yjust=1, legend=c('Species', 'Mean', 'Median and IQR'), pch=c(16,23,3),
         lty=c(NA,NA,1), lwd=c(NA,NA,3), pt.bg=c(NA,'#4C6570',NA),
         col=c('#969DA0','#25343B','#4C6570'), horiz=TRUE, bty='n', cex=.80)
  legend(.5, .51, xjust=.5, yjust=1,
         legend='Central 95% species-composition resampling range (birds)',
         lty=1, lwd=1.2, col='#172B31', bty='n', cex=.73)
  text(.5, .10, 'ROC AUC difference; horizontal scale varies among rows', cex=.8)
}
cairo_pdf(file.path(figure_dir, 'cross-case-contrasts.pdf'), width=7.4, height=7.8, pointsize=10)
render(); dev.off()
png(file.path(figure_dir, 'cross-case-contrasts.png'), width=7.4, height=7.8, units='in', res=300, pointsize=10, type='cairo')
render(); dev.off()
