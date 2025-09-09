# Dependency manifest for the rc-dates compendium

# Returns a character vector of required packages for this project.
project_dependencies <- function() {
  c(
    # pipeline & IO
    "targets", "tarchetypes", "here", "yaml", "config",
    "arrow", "duckdb", "qs", "vroom", "fs",
    # wrangling & utils
    "dplyr", "readr", "purrr", "tidyr", "tibble", "stringr", "magrittr", "checkmate", "janitor",
    # spatial
    "sf", "terra",
    # modelling / methods
    "yardstick",
    # parallel & progress & logging
    "future", "future.batchtools", "pbmcapply", "progressr", "lgr",
    # viz
    "ggplot2", "RColorBrewer", "zoo", "patchwork",
    # ergonomics & errors
    "cli", "rlang", "import",
    # dev
    "testthat", "lintr", "styler", "devtools", "pak", "renv", "quarto"
  )
}

# Optional helper: install dependencies into the active project library.
# This is not run automatically. Use in RStudio if needed.
install_project_dependencies <- function(pkgs = project_dependencies()) {
  if (requireNamespace("pak", quietly = TRUE)) {
    pak::pak(unique(pkgs), ask = FALSE)
  } else {
    install.packages(unique(pkgs), dependencies = TRUE)
  }
  invisible(TRUE)
}
