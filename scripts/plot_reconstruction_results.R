args <- commandArgs(trailingOnly=TRUE)
root <- if (length(args)) normalizePath(args[[1]]) else normalizePath('.')
data_dir <- file.path(root, 'evidence/reconstruction/20261113')
out_dir <- file.path(root, 'manuscript/figures')
read_data <- function(name) read.csv(file.path(data_dir, name), stringsAsFactors=FALSE)
f2 <- read_data('fig2-pretraining-species.csv')
regions <- read_data('fig2-bird-region-means.csv')
f3 <- read_data('fig3-bird-comparisons.csv')
richness <- read_data('fig4-richness-species.csv')
tas <- read_data('fig4-tasmania-means.csv')
ranges <- read_data('display-resampling.csv')
blue <- '#286C9E'
orange <- '#BC623C'
grey <- '#5D666D'
green <- '#317B66'
dark <- '#24343D'
grid <- '#E5E8EA'
fmt <- function(x) sprintf('%+.4f', x)
jitter_key <- function(n, width=.22) ((seq_len(n)*.61803398875) %% 1 - .5)*width

setup <- function() par(family='sans', las=1, tcl=-.2, mgp=c(2.8,.55,0),
                       cex.axis=.88, col.axis=dark, col.lab=dark, fg=dark)
save_figure <- function(stem, width, height, draw) {
  cairo_pdf(file.path(out_dir, paste0(stem,'.pdf')), width=width,
            height=height, pointsize=10)
  draw()
  dev.off()
  png(file.path(out_dir,paste0(stem,'.png')), width=width, height=height,
      units='in', res=300, pointsize=10, type='cairo')
  draw()
  dev.off()
}
range_row <- function(case=NULL, setting=NULL, comparison=NULL,
                      richness_bin=NULL) {
  d <- ranges
  if (!is.null(case)) d <- d[d$case==case,]
  if (!is.null(setting)) d <- d[d$setting==setting,]
  if (!is.null(comparison)) d <- d[d$comparison==comparison,]
  if (!is.null(richness_bin)) d <- d[d$richness_bin==richness_bin,]
  stopifnot(nrow(d)==1, is.finite(d$mean))
  d
}
mean_range <- function(x, d, colour=blue, offset=0) {
  if (is.finite(d$lower) && is.finite(d$upper)) {
    segments(x+offset,d$lower,x+offset,d$upper,lwd=2,col=dark)
    segments(x+offset-.045,c(d$lower,d$upper),x+offset+.045,
             c(d$lower,d$upper),lwd=1,col=dark)
  }
  points(x+offset,d$mean,pch=23,bg=colour,col=dark,cex=1.25)
}
draw_f2 <- function() {
  layout(matrix(c(1,2,3,3),2,byrow=TRUE),widths=c(3.1,1.1),heights=c(1.25,1))
  setup()
  settings <- c('development','development_within_regions_folds','new_regions')
  bird <- f2[f2$case=='birds',]
  stopifnot(all(table(bird$setting)==73))
  bird <- bird[order(bird$species,match(bird$setting,settings)),]
  lim <- range(c(bird$difference,0))
  lim <- c(min(-.05,lim[1]-.008),max(.065,lim[2]+.014))
  par(mar=c(4.5,5.7,3.1,.8))
  plot(NA,xlim=c(.65,3.35),ylim=lim,axes=FALSE,xlab='',
       ylab='Pretrained − single-species AUC')
  ticks <- pretty(lim,n=5)
  abline(h=ticks,col=grid,lwd=.7)
  abline(h=0,col=grey,lty=2)
  axis(2,at=ticks)
  axis(1,at=1:3,labels=c('Familiar regions\nwhole domain',
       'Familiar regions\nwithin regions + folds','New regions\nthree-region mean'),
       tick=FALSE,cex.axis=.78)
  for (i in seq_along(unique(bird$species))) {
    sp <- sort(unique(bird$species))[[i]]
    d <- bird[bird$species==sp,]
    y <- d$difference[match(settings,d$setting)]
    x <- 1:3+jitter_key(73)[[i]]
    lines(x,y,col=adjustcolor(grey,alpha.f=.20),lwd=.55)
    points(x,y,pch=16,cex=.5,col=adjustcolor(blue,alpha.f=.42))
  }
  for (i in 1:3) {
    rr <- range_row(case='birds',setting=settings[[i]],
                    comparison='pretrained_minus_single_species')
    mean_range(i,rr)
    text(i,lim[2]-.003,labels=paste0(fmt(rr$mean),'\n',rr$positive,'/73 positive'),
         cex=.76,adj=c(.5,1),col=dark)
  }
  mtext('(a) Birds',3,line=1.5,adj=0,font=2,cex=1)
  par(mar=c(4.5,.4,3.1,.7))
  plot(NA,xlim=c(.5,3.5),ylim=lim,axes=FALSE,xlab='',ylab='')
  abline(h=ticks,col=grid,lwd=.7)
  abline(h=0,col=grey,lty=2)
  regions <- regions[match(c('NCP','SEH','NNC'),regions$region),]
  points(1:3,regions$mean,pch=18,col=blue,cex=1.25)
  axis(1,at=1:3,labels=regions$region,tick=FALSE,cex.axis=.75)
  text(1:3,regions$mean+c(.012,-.013,-.026),fmt(regions$mean),cex=.64)
  mtext('New regions\nseparately',3,line=.7,font=2,cex=.8)
  par(mar=c(4.0,5.7,3.2,1.0))
  mm <- f2[f2$case!='birds',]
  lim_m <- range(c(mm$difference,0))+c(-.025,.06)
  plot(NA,xlim=c(.55,5.45),ylim=lim_m,axes=FALSE,xlab='',
       ylab='Pretrained − single-species AUC')
  ticks <- pretty(lim_m,n=4)
  abline(h=ticks,col=grid,lwd=.7)
  abline(h=0,col=grey,lty=2)
  axis(2,at=ticks)
  axis(1,at=c(1,2,4,5),labels=c('Development','Transfer to\nTasmania',
       'Development','Withheld\npatches'),tick=FALSE,cex.axis=.85)
  for (case in unique(mm$case)) {
    dd <- mm[mm$case==case,]
    xs <- if (grepl('mainland',case)) c(1,2) else c(4,5)
    sps <- sort(unique(dd$species))
    for (i in seq_along(sps)) {
      ds <- dd[dd$species==sps[[i]],]
      y <- ds$difference[match(c('development','new_regions'),ds$setting)]
      x <- xs+jitter_key(length(sps),.3)[[i]]
      lines(x,y,col=adjustcolor(grey,.45),lwd=.8)
      points(x,y,pch=16,col=adjustcolor(blue,.7),cex=.95)
    }
    for (j in 1:2) {
      v <- dd$difference[dd$setting==c('development','new_regions')[[j]]]
      points(xs[j],mean(v),pch=23,bg=blue,col=dark,cex=1.35)
      text(xs[j],lim_m[2]-.012,paste0(fmt(mean(v)),'\n',sum(v>0),'/',length(v),' positive'),
           cex=.78,adj=c(.5,1))
    }
  }
  mtext('(b) Mammals',3,line=1.6,adj=0,font=2,cex=1)
  mtext('Mainland (5 species)',3,line=.4,at=1.5,cex=.84)
  mtext('Tasmania (8 species)',3,line=.4,at=4.5,cex=.84)
}
draw_f3 <- function() {
  setup()
  par(mar=c(4.3,13.0,1.7,1.8))
  comps <- c('single_species_minus_conventional','pretrained_minus_conventional',
             'single_species_ensemble_minus_conventional','pretrained_ensemble_minus_conventional')
  labels <- c('Single-species network','Pretrained network',
              'Single-species + conventional\nfixed 50:50 average',
              'Pretrained + conventional\nfixed 50:50 average')
  colours <- c(orange,blue,'#66A387',green)
  lim <- range(c(f3$difference,0))
  lim <- lim+c(-.007,.007)
  plot(NA,xlim=lim,ylim=c(.5,4.8),axes=FALSE,xlab='AUC gain over conventional model',ylab='')
  ticks <- pretty(lim,n=5)
  abline(v=ticks,col=grid,lwd=.7)
  abline(v=0,col=grey,lty=2)
  axis(1,at=ticks)
  axis(2,at=4:1,labels=labels,tick=FALSE,cex.axis=.88)
  for (i in 1:4) {
    dd <- f3[f3$comparison==comps[[i]],]
    dd <- dd[order(dd$species),]
    stopifnot(nrow(dd)==73)
    rr <- range_row(comparison=comps[[i]],setting='new_regions')
    y <- 5-i
    points(dd$difference,y+jitter_key(73,.28),pch=16,cex=.65,
           col=adjustcolor(colours[[i]],.5))
    segments(rr$lower,y-.23,rr$upper,y-.23,col=dark,lwd=2)
    points(rr$mean,y-.23,pch=23,bg=colours[[i]],col=dark,cex=1.3)
    text(lim[2],y+.30,paste0(fmt(rr$mean),' mean; ',rr$positive,'/73 positive'),
         adj=c(1,.5),cex=.76,col=dark)
  }
}
draw_f4 <- function() {
  layout(matrix(c(1,1,2,2,3,3,4,4,4,5,5,5),2,byrow=TRUE),
         heights=c(1.15,1))
  setup()
  bins <- c('10_24','25_99','100_plus')
  binlabels <- c('10–24','25–99','≥100')
  lim <- range(c(richness$difference,0))
  lim <- lim+c(-.025,.04)
  ticks <- pretty(lim,n=4)
  for (i in 1:3) {
    region <- c('all','SEH','NNC')[[i]]
    dd <- richness[richness$region==region,]
    par(mar=c(4.1,if(i==1) 5.8 else 1.8,4.0,.6))
    plot(NA,xlim=c(.65,3.35),ylim=lim,axes=FALSE,xlab='',
         ylab=if(i==1) 'Pretrained − conventional AUC' else '')
    abline(h=ticks,col=grid,lwd=.7)
    abline(h=0,col=grey,lty=2)
    if(i==1) axis(2,at=ticks)
    axis(1,at=1:3,labels=binlabels,tick=FALSE,cex.axis=.8)
    means <- c()
    for (j in 1:3) {
      d <- dd[dd$richness_bin==bins[[j]],]
      d <- d[order(d$species),]
      points(j+jitter_key(nrow(d),.30),d$difference,pch=16,cex=.5,
             col=adjustcolor(blue,.27))
      scope <- if(region=='all') 'development/all' else paste0('new_regions/',region)
      rr <- ranges[ranges$figure=='fig4' & ranges$case=='birds' &
                    ranges$setting==scope & ranges$richness_bin==bins[[j]],]
      stopifnot(nrow(rr)==1)
      means <- c(means,rr$mean)
      mean_range(j,rr)
      text(j,lim[2]-.006,fmt(rr$mean),cex=.8,adj=c(.5,1))
    }
    lines(1:3,means,col=blue,lwd=1)
    label <- if (i==1) '(a) Birds: development' else paste('New region:',region)
    mtext(label,3,line=2.6,adj=0,font=2,cex=.86)
    mtext(paste(length(unique(dd$species)),'species in every bin'),3,line=1.45,adj=0,cex=.77)
    mtext('Other recorded species',1,line=2.3,cex=.82)
  }
  for(i in 1:2) {
    eval <- c('mixed','survey_only')[[i]]
    dd <- tas[tas$evaluation==eval,]
    par(mar=c(3.3,if(i==1) 5.8 else 2.2,3.5,.9))
    plot(NA,xlim=c(.75,2.25),ylim=c(.72,.89),axes=FALSE,xlab='',
         ylab=if(i==1) 'Mean AUC (8 mammals)' else '')
    abline(h=seq(.72,.9,.04),col=grid,lwd=.7)
    if(i==1) axis(2,at=seq(.72,.88,.04))
    axis(1,at=1:2,labels=c('Original\ntraining','Training pseudoabsences\nremoved'),tick=FALSE,cex.axis=.78)
    for(j in 1:3) {
      learner <- c('pretrained','single_species','conventional')[[j]]
      ds <- dd[dd$learner==learner,]
      vals <- ds$auc[match(c('original','pseudoabsences_removed'),ds$training)]
      stopifnot(length(vals)==2,all(is.finite(vals)),all(vals>.72 & vals<.89))
      lines(1:2,vals,col=c(blue,orange,grey)[[j]],lwd=1.6,
            lty=c(1,2,3)[[j]],pch=c(16,17,15)[[j]],cex=1)
      points(1:2,vals,col=c(blue,orange,grey)[[j]],pch=c(16,17,15)[[j]],cex=1)
    }
    mtext(if(i==1) '(b) Tasmania: mixed negatives' else 'Survey-supported negatives only',
          3,line=1.9,adj=0,font=2,cex=.84)
    if(i==1) legend('bottomleft',legend=c('Pretrained','Single-species','Conventional'),
          col=c(blue,orange,grey),pch=c(16,17,15),lty=c(1,2,3),bty='n',cex=.9)
  }
}
dir.create(out_dir,recursive=TRUE,showWarnings=FALSE)
save_figure('pretraining-across-regions',7.2,7.0,draw_f2)
save_figure('bird-networks-and-averages',7.2,4.5,draw_f3)
save_figure('negative-evidence',7.2,6.8,draw_f4)
