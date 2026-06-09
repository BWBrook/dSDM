# dSDM scoping review

Date: 2026-05-27

## Executive direction

The project is best treated as a rebuild around a tractable vertical slice:
finish and harden the Tasmanian mammals case study first, then use the SE
Australia birds case study as the scale-out test once the workflow is proven.

My stack recommendation is Python-first for the core modelling and production
pipeline, with the existing R code retained as scientific/procedural reference
and with R still available for targeted ecological data wrangling, figures, or
legacy validation where it is genuinely the fastest path. This is not a
recommendation to discard the old work. It is a recommendation to preserve the
ideas and data products while retiring the fragile R-Keras execution path.

The deep-learning implementation should still use Keras as the modelling API,
but through native Python Keras 3 on the GPU host. Keras 3 is now explicitly
multi-backend across TensorFlow, JAX, and PyTorch, while the R `keras3` package
exists and is maintained. The point is not that R-Keras is dead; it is that this
repo's current R-Keras code is old, Windows-path-bound, reticulate-dependent,
and will be harder to make robust on Alien/WSL than a clean Python package.

Useful current references:

- <https://keras.io/keras_3/>
- <https://keras3.posit.co/>
- <https://opensource.posit.co/software/keras3/>

## What is here now

### Tracked repository

The tracked repo is mostly scaffold, not yet the real project:

- `DESCRIPTION` describes an R package/compendium using `renv`, `targets`, and
  Quarto, but no `renv.lock` exists.
- `_targets.R` is a placeholder and still contains stale text from another
  project. It calls `tar_source("R")`, `cfg_read()`, and `read_manifest()`, but
  there is no tracked `R/` directory.
- `config/config.yaml`, `dependencies.R`, `profiles/targets/*.R`,
  `inst/containers/*`, and `tests/run-tests.R` are generic and incomplete.
  The container recipes call `scripts/bootstrap.R`, which is not present.
- `metadata/data_manifest.csv` is an example-only manifest.
- `reports/paper.qmd` is a placeholder report and refers to a non-existent
  `model_fit` target.
- `manuscript/` is now a working `makedoc` manuscript workspace. The converted
  draft builds successfully in draft mode.

Current local checks:

- `make -C manuscript check` passes.
- `Rscript -e 'targets::tar_manifest(...)'` emits `tar_source(): these files
  do not exist: R`; the target manifest can be printed, but the pipeline is not
  runnable.
- `renv::status()` reports that the project is not using `renv`.

### Ignored payload

The actual project material is in ignored `temp/` and `data/`:

- `temp/src/`: legacy R data-prep, traditional ML, and evaluation scripts.
- `temp/old_code/`: legacy R-Keras dSDM scripts and helpers.
- `temp/data/`: processed and spatial input data, about 2.3 GB.
- `data/input/spatial_polygons.zip`: study-area and IBRA polygons, about 49 MB.
- `temp/dSDM_MS_draft.docx`: early manuscript draft now converted to Markdown.
- `temp/rahil_sdm_sampling_instructions.txt`: short note on occurrence
  processing, pseudoabsence logic, and thinning.

No fitted models, RDS augmented datasets, prediction CSVs, or complete results
artifacts arrived with the payload.

## Data map

### Tasmanian mammals

This is the right first case study. It is small enough to iterate locally and
on Alien without turning every design flaw into a compute bill.

Main processed files:

| file | rows | columns | notes |
|---|---:|---:|---|
| `temp/data/tas_sdm_data/tas_sdm_train.csv` | 10,489 | 81 | 9 species, 5 train folds, no missing fields |
| `temp/data/tas_sdm_data/tas_sdm_test.csv` | 1,036 | 81 | held-out test; `fold` is `NA` by design |
| `temp/data/tas_sdm_data/tas_sdm_map.csv` | 71,057 | 77 | prediction grid/map covariates |
| `temp/data/tas_sdm_data/tascam_grid_pa.csv` | 7,803 | 4 | camera-trap presence/true-absence grid |
| `temp/data/tas_sdm_data/tas_mammal_ala_pa.csv` | 8,791 | 4 | ALA-derived presence/pseudoabsence grid |
| `temp/data/spatial/tas_stack.tif` | 468 x 455 x 32 bands | | original Tas stack |
| `temp/data/spatial/tasmania_coast.shp` | 1 feature | | WGS84 Tasmania boundary |

Training split:

- 9 species.
- 10,489 training rows: 7,060 presences and 3,429 absences.
- 1,036 test rows: 760 presences and 276 absences.
- 75 predictors after preprocessing: 19 bioclimatic, 6 other continuous, 17
  land-use one-hot, 21 vegetation one-hot, 12 soil one-hot.
- Continuous predictors in `tas_sdm_train.csv` are centred and scaled almost
  exactly to mean 0 and sd 1, consistent with training-set scaling.
- Spatial extent is roughly lon 143.845 to 148.465, lat -43.628 to -39.598.

Species represented in processed train/test:

- `Thylogale billardierii`
- `Notamacropus rufogriseus`
- `Macropus giganteus`
- `Trichosurus vulpecula`
- `Pseudocheirus peregrinus`
- `Vombatus ursinus`
- `Sarcophilus harrisii`
- `Dasyurus maculatus`
- `Dasyurus viverrinus`

Data caveats:

- `species_list_tas.csv` lists 8 mammals and omits `Thylogale billardierii`,
  although the processed modelling data include it.
- Some species have severe prevalence imbalance, especially
  `Macropus giganteus`, `Sarcophilus harrisii`, and `Thylogale billardierii`.
  Metrics and thresholding need to be designed around this, not bolted on.
- The true-absence camera-trap data and the citizen-science pseudoabsence data
  have different epistemic status. The rebuilt pipeline should preserve that
  provenance rather than collapsing everything to `pa` too early.

### SE Australia birds

This is the later scale-out case study.

Main processed files:

| file | rows | columns | notes |
|---|---:|---:|---|
| `temp/data/se_sdm_data/se_train_data.csv` | 2,487,312 | 91 | 100 species, 5 train folds |
| `temp/data/se_sdm_data/se_test_data.csv` | 424,421 | 91 | held-out test; `fold` is `NA` by design |
| `temp/data/se_sdm_data/se_sdm_map.csv` | 630,677 | 87 | prediction grid/map covariates |
| `temp/data/spatial/se_stack_metadata.xlsx` | 6 sheets | | metadata for climate, landscape, land use, vegetation, soil, sources |
| `data/input/spatial_polygons.zip` | 2 shapefile groups | | study-area and IBRA7 subregions |

Training split:

- 100 species.
- 2,487,312 training rows: 793,026 presences and 1,694,286 absences.
- 424,421 test rows: 138,122 presences and 286,299 absences.
- 85 predictors after preprocessing: 19 bioclimatic, 6 other continuous, 17
  land-use one-hot, 30 vegetation one-hot, 13 soil one-hot.
- Spatial extent is roughly lon 135.375 to 153.625, lat -43.628 to -23.778.

Caveats:

- This is too large to use as the architecture debugging surface.
- `species_list_ag.csv` is an older 7-species list and does not describe the
  100-species processed SE bird files.
- The SE continuous columns are scaled, but the sampled training means are not
  exactly zero in the way the Tasmanian dataset is. That may be benign, but the
  scaling provenance should be verified before publication.

### Spatial metadata

`temp/data/spatial/se_stack_metadata.xlsx` is useful and should be promoted into
a tracked, human-readable metadata source. It records:

- 19 climate variables.
- Landscape variables including elevation, FPAR, freshwater distance, road
  distance, terrain ruggedness, and fire frequency.
- Land-use, vegetation, and soil class dictionaries.
- Source URLs for climate, elevation, FPAR, hydrology, roads, terrain
  ruggedness, fire frequency, land use, vegetation, and soil.

## Code map

### Data preparation and splitting

Legacy files:

- `temp/src/0_galah_ALA.r`: ALA occurrence download via `galah`.
- `temp/src/1_process_point_data.R`: snap occurrences to grid, create
  presence/pseudoabsence data, thin by human-density/sampling intensity.
- `temp/src/1a_tas_sdm_data_combine.r`: combine camera-trap true PA data with
  ALA-derived PA data, remove selected offshore island absences by species, and
  manually thin species one at a time.
- `temp/src/2_tas_sdm_data_cv_split.r`: spatial clustering into 50 folds,
  manually choose 5 held-out test folds, aggregate the rest into 5 train folds.
- `temp/src/3_create_sdm_data.R`: merge occurrence data with raster stack,
  drop selected layers, scale continuous predictors, one-hot categorical
  predictors, save train/test/map CSVs.
- `temp/src/sdm_data_func.R`: helper functions for the above.

Important issues:

- Hard-coded Windows paths throughout.
- Manual species-by-species execution remains embedded in scripts.
- `process_presence_data()`, `potential_absences_from_sites()`, and thinning
  logic need tests before being trusted.
- `potential_absences_from_sites()` refers to `presences` instead of the
  function argument `pres`, which is likely a real bug.
- `get_ALA_data()` has `if(exists(output)) write.csv(...)`, which checks for an
  object named by the output path, not whether output should be written.
- `make_sdm_sf()` is called from `temp/old_code/5_DSDM_preprocess.R` but is not
  present in the incoming files.
- `plot_species()` is called from `2_tas_sdm_data_cv_split.r` but the helper in
  the provided file is named `plot_spatial_species_data()`.

### Traditional ML baselines

Legacy files:

- `temp/src/4a_ml_randomForest.R`
- `temp/src/4b_ml_ANN.R`
- `temp/src/4c_ml_ensemble.R`
- `temp/src/modelling_functions.R`
- `temp/src/8_model_eval.R`

What they attempt:

- RF via `ranger`/tidymodels.
- Shallow ANN via `nnet`/tidymodels.
- Ensemble of GLM, GAM, GBM, RF, ANN.
- Threshold tuning by F1 on training predictions.
- Held-out test prediction/evaluation.
- Map predictions for a selected species.

Important issues:

- Scripts are copy-paste, one-species-at-a-time, and output-path-specific.
- Several result paths refer to `sdm_results/...` directories not present here.
- The code normalises predicted probabilities before thresholding and mapping.
  That is harmless for rank metrics such as AUC but not harmless for calibrated
  probability interpretation.
- PR AUC and MCC implementations need verification against standard libraries.
- Feature-selection comments do not match the current executable code clearly
  enough to publish without reconstruction.

### Deep-learning dSDM

Legacy files:

- `temp/old_code/dsdm_func.R`
- `temp/old_code/5_DSDM_preprocess.R`
- `temp/old_code/6_DSDM_tune_hyper_parameters.R`
- `temp/old_code/7a_DSDM_single_species.R`
- `temp/old_code/7b_DSDM_paired_species.R`
- `temp/old_code/7c_DSDM_sequential.R`
- `temp/old_code/7d_DSDM_melting_pot.R`
- `temp/old_code/7_DSDM_fine_tune_6cd_predict.R`

What they attempt:

- Dense feed-forward Keras model with:
  - configurable depth and width;
  - He initialisation;
  - batch normalisation;
  - ReLU hidden activations;
  - dropout;
  - L1/L2 regularisation;
  - compression layer;
  - sigmoid binary classifier.
- Hyperparameter grid search.
- Spatial jitter augmentation by nearest raster cell lookup.
- Single-species training from random weights.
- Paired-species transfer.
- Sequential species transfer.
- Community/melting-pot transfer.
- Classifier replacement, layer freezing, dense-layer unfreezing, and low-rate
  fine-tuning.

Important issues:

- The scripts require RDS files such as `tas_sdm_aug_100_epochs.RDS`, but those
  files are not in the payload.
- The code uses legacy R `keras` and TensorFlow idioms, including HDF5 model
  saves. A modern rebuild should use Keras 3 `.keras` artifacts.
- It uses `tensorflow::tf$distribute$MultiWorkerMirroredStrategy()`. For Alien's
  two GPUs on one WSL host, ordinary mirrored data parallelism is more likely
  the correct pattern than multi-worker strategy.
- The dynamic early stopping function is present but effectively disabled.
- The transfer-learning scripts are manually parameterised for one target
  species at a time.
- There is enough algorithmic content here to preserve, but not enough
  software structure to keep as the main implementation.

## Scientific workflow map

The manuscript and code agree on the broad scientific story:

1. Build presence/absence or pseudoabsence SDM datasets for two case studies.
2. Use spatially disjunct folds: held-out spatial test plus internal
   cross-validation folds.
3. Compare traditional ML baselines against a deep fully connected dSDM.
4. Test whether transfer learning improves dSDM performance.
5. Test whether jitter-based spatial augmentation improves fine-tuning.
6. Evaluate with AUC ROC, AUC PR, TSS, sensitivity, specificity, balanced
   accuracy, F1, and MCC.
7. Produce maps, ROC plots, metric tables, and possibly frequency-of-win tables.

The main missing scientific pieces are:

- validated, reproducible reruns of all Tasmanian mammal models;
- principled threshold strategy;
- final decision on which transfer strategies are scientifically worth showing;
- map outputs and figure-ready artifacts;
- actual results text;
- a real reference library rather than the manuscript's "link to Endnote" note.

## Stack decision

### Recommendation

Use Python-first for the core rebuild:

- `uv` + `pyproject.toml` for the project environment.
- Native Python Keras 3 for dSDM models, initially with TensorFlow backend on
  Alien unless a smoke test shows another backend is superior there.
- `numpy`, `polars` or `pandas`, `duckdb`, `pyarrow`, and Parquet for tabular
  data.
- `scikit-learn`/`xgboost` or equivalent for baseline RF/GBM/shallow MLP.
- `geopandas`/`rasterio`/`pyproj` only where spatial preprocessing needs to be
  rerun in Python; do not port spatial code prematurely if processed Tas CSVs
  are the immediate modelling substrate.
- R remains available for comparison, legacy extraction, manuscript figures, or
  ecological workflows where it is clearer.

### Why not stay on R-Keras

R-Keras would preserve the old language context and align with the original
manuscript Methods, but the real cost is hidden in the glue:

- Current local R has `targets`, `sf`, `terra`, `tidymodels`, `spatialsample`,
  `duckdb`, `arrow`, and `renv`, but not `keras`, `tensorflow`, or `tidysdm`.
- The old code uses legacy R `keras` rather than the current R `keras3`.
- Debugging CUDA/TensorFlow/Keras through R/reticulate on Alien WSL adds a layer
  of failure between us and the GPUs.
- The old scripts are not package functions with tests; they are manual scripts
  with hard-coded Windows paths and missing artifacts.

If we stayed with R-Keras, we would still be doing a major rewrite. The only
question is whether that rewrite lands in a Python-native ML stack or a
reticulate-mediated R stack. For this project, the Python-native path looks
lower risk.

### Why not discard R entirely

The R code contains the scientific memory of the project:

- pseudoabsence and thinning logic;
- spatial split logic;
- predictor construction and categorical level choices;
- the baseline model family;
- the original dSDM architecture and transfer-learning design.

It should be mined carefully, not thrown away. The first rebuild should aim to
match the Tasmanian CSV-derived modelling data and reproduce the intended model
families. Only after that should we decide whether to port/rebuild the upstream
ALA/spatial ingestion end to end.

## Proposed repo trajectory

### Phase 0: Preserve and document

- Keep `temp/` ignored as raw archaeological context.
- Promote a small tracked data inventory with file sizes, row counts, columns,
  checksums, and provenance notes.
- Write an explicit `data/README.md` explaining that bulky data are untracked.
- Decide canonical paths for local-only data and generated artifacts.

### Phase 1: Tasmanian mammals modelling substrate

- Convert Tasmanian processed CSVs to Parquet under ignored `data/processed/tas/`.
- Create tracked schema/manifest files under `metadata/`.
- Define canonical split objects and predictor lists.
- Add a small smoke subset for tests, either synthetic or derived/minified from
  Tas data if licensing permits.
- Lock one target species for initial smoke tests, probably `Dasyurus viverrinus`
  because the old scripts already use it heavily.

### Phase 2: Python package skeleton

Suggested layout:

```text
src/dsdm/
  data/
  metrics/
  models/
  spatial/
  workflows/
configs/
  tas_mammals.yaml
  se_birds.yaml
scripts/
  prepare_tas.py
  train_baseline.py
  train_dsdm.py
  evaluate.py
  predict_map.py
tests/
```

The package should expose functions first and scripts second. Scripts should be
thin wrappers over tested functions.

### Phase 3: Baseline model ladder on Tas

Build in this order:

1. Null/prevalence baseline.
2. RF baseline.
3. GBM/XGBoost baseline.
4. Shallow MLP baseline.
5. Optional GAM baseline if needed for ecological comparability.
6. Ensemble if it adds interpretive value after the individual baselines work.

Outputs should be standardised:

- per-row predictions;
- per-species/per-model metric table;
- threshold table;
- model metadata;
- run manifest with seed, code version, data checksum, package versions, and
  compute host.

### Phase 4: dSDM on Tas

Rebuild the deep-learning family as one parameterised workflow:

- no-transfer dSDM;
- paired-species transfer;
- sequential transfer;
- community/melting-pot transfer;
- with and without jitter augmentation where scientifically needed.

Jitter augmentation should be deterministic under a seed and should record
whether jittered points are allowed to land in unsuitable/missing cells, are
snapped to nearest valid cell, or are dropped. This choice matters for the
Methods.

### Phase 5: Figures and manuscript integration

- Generate figure-ready outputs into ignored build/artifact directories.
- Promote final small figure files into tracked `manuscript/figures/` when ready.
- Populate `manuscript/text/figures.md` with `makedoc` figure blocks.
- Replace manuscript placeholders with generated tables and final claims.
- Build `make -C manuscript check PROFILE=submission` as the manuscript gate.

### Phase 6: SE birds scale-out

Only after Tas mammals are locked:

- Convert SE CSVs to Parquet.
- Reuse the same configs/workflows.
- Smoke one or two bird species.
- Scale to all 100 species on the appropriate compute target.
- Compare whether Tas conclusions hold at the larger spatial/species scale.

## Compute routing

- Local Mac mini: repo development, schema checks, small Tas smoke runs,
  manuscript builds, and light model tests.
- Alien WSL: default GPU target for Keras training that fits dual RTX 2080s.
- `deep-server`: CPU-heavy non-GPU jobs, large baseline sweeps, and bulk
  preprocessing if local runtime is annoying.
- Nectar GPU: only if Alien is unavailable, too small, or a clean disposable
  cloud GPU state is useful.

For every remote run, capture:

- git commit or dirty-tree marker;
- data manifest/checksum;
- exact config;
- host and device info;
- package lock;
- command line;
- output artifact paths.

## Publication path

The paper should not be written separately from the code. The manuscript should
become a consumer of run artifacts:

- Methods should describe the exact implemented pipeline, not the intended old
  one.
- Results should be generated from canonical metrics and prediction artifacts.
- Figures should be regenerated from code and then promoted into
  `manuscript/figures/`.
- The current converted draft is useful as a scaffold, but the Results and
  Discussion are placeholders until Tas results are rerun.

## Immediate next steps

1. Create the Python project skeleton and lock a minimal environment.
2. Promote Tasmanian processed CSVs to an ignored Parquet modelling substrate.
3. Add a tracked Tas data manifest with checksums and schema.
4. Implement metrics and thresholding once, with tests.
5. Implement a null baseline and one RF model for `Dasyurus viverrinus`.
6. Run the same RF workflow across all 9 mammals.
7. Implement the Keras 3 no-transfer dSDM smoke test on Mac CPU first, then
   Alien GPU.
8. Only then rebuild transfer learning and augmentation.

## Open decisions

- Which Tas species should be the canonical first smoke target?
- Should the final manuscript include GAM as a headline baseline, or are RF,
  GBM, shallow ANN/MLP, ensemble, and dSDM enough?
- Should thresholds be tuned per species/model using inner CV predictions,
  a held-out validation fold, or fixed by prevalence/Youden/F1 rules?
- Should camera-trap true absences and ALA pseudoabsences be weighted or
  modelled differently?
- What journal style should replace the temporary Oikos CSL if Oikos is not the
  real target?
