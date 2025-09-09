FROM rocker/r2u:jammy

# Install system libraries needed for geospatial work and other common R extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev libgeos-dev libproj-dev libudunits2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /project
COPY . /project

# Bootstrap dependencies (restore if renv.lock exists, otherwise init + snapshot)
RUN R -q -e "source('scripts/bootstrap.R')"

# Default command: run the full pipeline
CMD ["R", "-q", "-e", "targets::tar_make()"]
