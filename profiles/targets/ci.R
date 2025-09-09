## Continuous integration profile for {targets}
##
## This profile runs a minimal subset of the pipeline to keep CI fast.
## It executes sequentially and can be customised via config/config.yaml
## or environment variables (e.g. sampling fractions).  Set
## TARGETS_PROFILE=ci in your CI scripts.

future::plan(future::sequential)
options(gold.sample_frac = 0.02)  # Example option; respect this in code