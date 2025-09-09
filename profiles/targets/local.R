## Local execution profile for {targets}
##
## This script is executed when TARGETS_PROFILE=local is set.  Use it
## to configure parallelism for your local machine and any other
## runtime options.  See ?tar_config_set for details.

future::plan(future::multisession, workers = parallel::detectCores(logical = FALSE))