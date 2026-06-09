# Legacy workflow map

This map records intent inferred from ignored legacy scripts. It is not a
directive to mimic the old implementation.

## High-level inferred flow

1. Query ALA records for focal species.
2. Snap records to a spatial grid and derive pseudoabsences.
3. Merge ALA-derived rows with Tas camera-trap true PA rows.
4. Exclude selected offshore-island absences and thin records.
5. Build spatial train/test/CV folds.
6. Extract raster predictors, scale continuous fields, and one-hot encode categories.
7. Fit baseline ML models and produce predictions/metrics/maps.
8. Fit dSDM variants with no-transfer, paired, sequential, and community transfer.
9. Evaluate metrics and feed accepted outputs into the manuscript.

## Script inventory by category

### data_acquisition

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/src/0_galah_ALA.r | Download focal mammal/bird occurrence records from ALA using galah and a study-area polygon. | species list CSV; study-area/coast shapefile; live ALA service | output/mammal_ala_tasmania.csv | No local output artifact with this exact name arrived. | Hard-coded Windows path and email; live ALA query is not version-pinned; output write path is implicit. |

### point_processing

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/src/1_process_point_data.R | Snap ALA occurrences to grid cells, derive pseudoabsences, and thin records by human-activity sampling intensity. | grid points; ALA occurrence CSV; human-footprint raster; Tasmania coast shapefile | output/tas_mammal_ala_pa.csv | Requires helper logic from sdm_data_func.R. | Manual species loop; hard-coded Windows path; relies on interactive plotting/sanity checks. |

### data_combination

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/src/1a_tas_sdm_data_combine.r | Merge camera-trap true PA data with ALA-derived PA data and remove offshore-island absences by species. | input/tascam_grid_pa.csv; output/tas_mammal_ala_pa.csv; offshore_islands.kml | output/tas_mammal_combined_pa_grid.csv | Only processed descendants arrived, not the named combined output. | Manual one-species block; island exclusions are embedded as code rather than config. |

### spatial_folds

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/src/2_tas_sdm_data_cv_split.r | Create 50 spatial clusters, manually choose 5 held-out folds, and aggregate the rest into 5 train folds. | output/tas_mammal_combined_pa_grid.csv | output/tas_sdm_cvsplit.csv | Calls plot_species(), but provided helper is named plot_spatial_species_data(). | Manual visual fold selection; hard-coded test fold IDs; no persisted split manifest arrived. |

### predictor_formatting

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/src/3_create_sdm_data.R | Join occurrence rows to raster covariates, drop selected layers, scale continuous predictors, one-hot encode categorical predictors. | output/tas_sdm_cvsplit.csv; spatial/tas_stack.tif | output/tas_sdm_train.csv; output/tas_sdm_test.csv; output/tas_sdm_map.csv | Processed CSV descendants arrived under temp/data/tas_sdm_data/. | Assumes complete raster stack and fixed categorical levels; no standalone schema manifest. |

### baseline_ml

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/src/4a_ml_randomForest.R | Fit and tune a random-forest SDM for one selected species, evaluate held-out predictions, and map habitat suitability. | tas_sdm_train.csv; tas_sdm_test.csv; tas_sdm_map.csv | sdm_results/performance/*_rf.csv; sdm_results/maps/tas_norm_maps_rf.csv | No result/map artifacts arrived. | One-species script; hard-coded output paths; normalises probabilities before thresholding. |
| temp/src/4b_ml_ANN.R | Fit and tune a shallow ANN/MLP baseline through tidymodels/nnet. | tas_sdm_train.csv; tas_sdm_test.csv; tas_sdm_map.csv | sdm_results/performance/*_ann.csv; sdm_results/maps/tas_norm_maps_ann.csv | No result/map artifacts arrived. | One-species script; hard-coded output paths; normalises probabilities before thresholding. |
| temp/src/4c_ml_ensemble.R | Fit GLM, GAM, GBM, RF, and ANN models and average predictions into an ensemble. | tas_sdm_train.csv; tas_sdm_test.csv; tas_sdm_map.csv | sdm_results/performance/*_ensemble.csv; sdm_results/maps/tas_norm_maps_ensemble.csv | No result/map artifacts arrived. | Large copy-paste script; hard-coded selected species; mixed model engines and output assumptions. |

### baseline_ml_helpers

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/src/modelling_functions.R | Provide metric, threshold, formula-generation, RF, ANN, and GBM helper functions. | Prediction data frames; tidymodels recipes/workflows | Model objects and metric data frames | Depends on packages not declared in current DESCRIPTION, e.g. PRROC/xgboost/neuralnet in places. | Contains duplicated/fragile metric logic; probability normalisation affects calibration. |

### dsdm_preprocess

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/old_code/5_DSDM_preprocess.R | Create RDS train/test/augmentation objects for R-Keras dSDM. | output/tas_sdm_cvsplit.csv; spatial/tas_stack.tif | output/tas_sdm_train.RDS; output/tas_sdm_test.RDS; output/tas_sdm_aug.RDS | Calls make_sdm_sf(), which did not arrive; RDS outputs did not arrive. | Hard-coded paths; breaks out augmentation comments inconsistently; interactive jitter calibration block. |

### dsdm_tuning

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/old_code/6_DSDM_tune_hyper_parameters.R | Grid-search Keras dSDM hyperparameters for one target species. | output/tas_sdm_train.RDS | code/hyper_grid_v1.csv | RDS input and hyperparameter output did not arrive. | One-species manual script; legacy R-Keras/TensorFlow path. |

### dsdm_training

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/old_code/7a_DSDM_single_species.R | Train no-transfer dSDM from random weights for one species. | tas_sdm_train.RDS; tas_sdm_test.RDS; tas_sdm_aug_100_epochs.RDS | models/*_ss_sdm.h5; results/pred_*_ss.csv | RDS, model, and prediction artifacts did not arrive. | Manual target species; legacy HDF5 Keras artifacts; validation/early stopping is not cleanly resolved. |

### dsdm_transfer

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/old_code/7_DSDM_fine_tune_6cd_predict.R | Fine-tune a saved transfer base on the target species and write held-out predictions. | models/*_base.h5; tas RDS train/test/aug objects | models/*_sdm.h5; output/pred_*.csv | All required model/RDS artifacts absent. | Manual target/base settings; legacy HDF5 Keras path. |
| temp/old_code/7b_DSDM_paired_species.R | Load a paired-species model, replace classifier top, and fine-tune on target species. | paired *_ss_sdm.h5; tas RDS train/test/aug objects | models/*_ps_sdm.h5; output/pred_*_ps.csv | All model/RDS artifacts absent. | Manual species pairings; top replacement and layer-freezing require modern Keras review. |
| temp/old_code/7c_DSDM_sequential.R | Train/fine-tune through a hand-coded species sequence before target transfer. | tas_sdm_aug_100_epochs.RDS | models/*_sq_base.h5 | RDS/model artifacts absent. | Manual sequence embedded in code; no final target prediction in this script. |
| temp/old_code/7d_DSDM_melting_pot.R | Train a community/melting-pot base model on all non-target species. | tas RDS train/test/aug objects | models/*_mp_base.h5 | RDS/model artifacts absent. | Manual target species; base target exclusion embedded in script. |

### dsdm_helpers

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/old_code/dsdm_func.R | Provide R-Keras model building, tuning, jitter augmentation, transfer, and metric helpers. | RDS train/test/aug objects; Keras models | Model objects, histories, prediction metrics | Depends on legacy R keras/tensorflow stack; no lockfile or model artifacts arrived. | Dynamic early stopping mostly disabled; MultiWorker strategy likely wrong for single Alien WSL host; duplicated metric logic. |

### evaluation

| path | purpose | implied_inputs | implied_outputs | missing_refs | known_defects |
| --- | --- | --- | --- | --- | --- |
| temp/old_code/8_model_eval.R | Duplicate of legacy metric wrapper for combined predictions. | results/rahil_sdm_output.csv | Printed/sorted metric table | Input artifact did not arrive. | Thin wrapper; no persisted output. |
| temp/src/8_model_eval.R | Evaluate a combined prediction CSV into per-model, per-species metrics. | results/rahil_sdm_output.csv | Printed/sorted metric table | Input artifact did not arrive. | Thin wrapper around helper; no reproducible result artifact. |

## Phase 1 mining rules

- Preserve ecological intent, provenance distinctions, and QA clues.
- Do not copy hard-coded paths, one-species manual loops, or stale Keras idioms.
- Treat missing outputs and missing helpers as evidence that upstream data must be rebuilt.
- Use old processed CSVs only as comparison/reference artifacts.
