# Run tests in a non-package compendium

source("tests/testthat/helper-setup.R")
testthat::test_dir("tests/testthat", reporter = "summary")

