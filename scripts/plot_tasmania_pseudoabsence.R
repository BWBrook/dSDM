#!/usr/bin/env Rscript
# Probability maps on the frozen common domain; all panels use fixed scales.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args) == 3L)
d <- read.csv(args[[1]], check.names=FALSE)
stopifnot(nrow(d) == 71023L, all(is.finite(as.matrix(d))))
species <- gsub('_', ' ', args[[2]], fixed=TRUE)
substr(species, 1, 1) <- toupper(substr(species, 1, 1))
method_labels <- c('Target-only network', 'Full fine-tuning', 'Selected conventional learner')
probability_colours <- hcl.colors(256, 'Viridis')
difference_colours <- colorRampPalette(c('#2166AC', '#F7F7F7', '#B2182B'))(257)
grid_x <- seq(min(d$longitude),max(d$longitude),by=.01)
grid_y <- seq(min(d$latitude),max(d$latitude),by=.01)
grid_i <- round((d$longitude-min(grid_x))/.01)+1L
grid_j <- round((d$latitude-min(grid_y))/.01)+1L
stopifnot(max(abs(grid_x[grid_i]-d$longitude)) < 1e-8,
          max(abs(grid_y[grid_j]-d$latitude)) < 1e-8,
          !anyDuplicated(paste(grid_i,grid_j)))
plot_map <- function(value, colours, limits, title) {
  stopifnot(all(value >= limits[[1]]), all(value <= limits[[2]]))
  z <- matrix(NA_real_,length(grid_x),length(grid_y))
  z[cbind(grid_i,grid_j)] <- value
  image(grid_x,grid_y,z,col=colours,zlim=limits,useRaster=TRUE,
        asp=1/cos(mean(d$latitude)*pi/180),xlab='',ylab='',axes=FALSE,main=title,
        cex.main=.86,xaxs='i',yaxs='i')
}
draw_legend <- function(colours, limits, label) {
  plot.new(); plot.window(xlim=c(0,1), ylim=c(0,1))
  xx <- seq(.08,.92,length.out=length(colours)+1L)
  rect(head(xx,-1),.48,tail(xx,-1),.70,col=colours,border=NA)
  text(c(.08,.5,.92),.31,labels=format(c(limits[[1]],mean(limits),limits[[2]]),trim=TRUE),cex=.8)
  text(.5,.96,label,cex=.82)
}
render <- function() {
  layout(rbind(matrix(1:9,nrow=3,byrow=TRUE),c(10,10,11)),heights=c(1,1,1,.23))
  par(mar=c(.15,.1,1.8,.1),oma=c(.3,1.9,2.4,.3),family='sans')
  for (i in 0:2) {
    primary <- d[[paste0('primary_',i)]]
    sensitivity <- d[[paste0('sensitivity_',i)]]
    plot_map(primary,probability_colours,c(0,1),if(i==0) 'Primary' else '')
    mtext(method_labels[[i+1]],side=2,line=.1,cex=.75)
    plot_map(sensitivity,probability_colours,c(0,1),if(i==0) 'Sensitivity' else '')
    plot_map(sensitivity-primary,difference_colours,c(-1,1),if(i==0) 'Sensitivity minus primary' else '')
  }
  par(mar=rep(0,4))
  draw_legend(probability_colours,c(0,1),'Seed-averaged suitability score')
  draw_legend(difference_colours,c(-1,1),'Score difference')
  mtext(species,outer=TRUE,side=3,line=.6,font=3,cex=1.05)
}
cairo_pdf(paste0(args[[3]],'.pdf'),width=9,height=10,pointsize=10)
render(); invisible(dev.off())
png(paste0(args[[3]],'.png'),width=9,height=10,units='in',res=200,type='cairo',pointsize=10)
render(); invisible(dev.off())
