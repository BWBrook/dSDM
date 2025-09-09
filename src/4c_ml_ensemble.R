# =======================================================================================================================#
                       #Tune and and fit un-weighted ensemble of GLM, GAM, RF, GBM, ANN 
# =======================================================================================================================#

#### Clearn environment and set options ##################################################################################
{rm(list=ls()); options(scipen=999,digits=9); set.seed(12345)
setwd("C:/Users/rjamin/dsdm_files/model_se_sdm")   }


#### Import functions ####################################################################################################
{import::from("code/modelling_functions.R",.all=T)          #Import custom functions from source file
num_cores = 30                                              #Define cores for parallel processing 
  

#### Custom parameters and constants #####################################################################################

# Select file path ------------------------------------------------------------------------------
in_train = "sdm_data/se_trai_data.csv"
in_test = "sdm_data/tas_sdm_test.csv"
    
# Define hyper-parameters -----------------------------------------------------------------------  

# 1. Random Forest (RF) ####
mtry = c(1:15)                                                  #Number of variables randomly sampled as candidates at each split

# 2. Artificial Neural Networks (ANN) ####
penalty = c(0.001,0.0001,0.0001)                             #Number of units in the hidden model
hidden_units = c(12,16,32,64)                                         #Numeric value for the amount of weight decay

# 3. Gradient Boosted Machine (GBM) #### 
learn_rate = c(1e-2, 1e-3, 1e-4)                                # Learning rate, which adjusts the step size at each iteration in GBM
tree_depth = c(1, 5, 9)                                         # Maximum depth of trees in GBM
min_n = c(10, 20, 30)                                           # Minimum number of observations required for a node to be split in GBM
trees_gbm = seq(100, 1500, by = 100)  }                         # Sequence for the number of boosting iterations


#### Data loading ########################################################################################################
{train_data_full <- read.csv(in_train)                          # Load training data
test_data_full <- read.csv(in_test)                             # Load test data
species_pool <- unique(train_data_full$species)  }              # Identify unique species

# Select species ---------------------------------------------------------------------------------
sp <- species_pool[9];sp                                                              #Choose species index from species pool

{train_data <- train_data_full %>% filter(species == sp) %>% mutate(pa=as.factor(pa)) # Subset train set for selected species 
test_data <- test_data_full %>% filter(species == sp) %>% mutate(pa=as.factor(pa))    # Subset test set for selected species 


#### Ensemble ############################################################################################################
cl <- makePSOCKcluster(num_cores); registerDoParallel(cl)      #Set up parallel processing
tidymodels_prefer()                                            # Prefer tidymodels setup

# Tuning and validation settings -------------------------------------------------------------------
custom_folds <- group_vfold_cv(train_data, group = "fold")                             #Use 'fold' column to create k-folds
ctrl_grid <- control_grid(save_pred = TRUE, save_workflow = TRUE, verbose = FALSE)   } #Define control parameters for model tuning

# Define model formula -----------------------------------------------------------------------------

formulas <- generate_formulas(
  response = "pa",
  smooth_variables = c("annmeantemp","meandiurnrange", "tempseason","meantempwetq","meantempdryq",
                       "annprecip","precipseason","precipwetq","precipdryq","precipwarmq",        
                       "precipcoldq","elevation","dist_fw","dist_road","fpar"),
  factor_variables = c("landuse_secondary1","landuse_secondary2","landuse_secondary3","landuse_secondary4","landuse_secondary5","landuse_secondary6","landuse_secondary7",
                       "landuse_secondary8","landuse_secondary9","landuse_secondary11","landuse_secondary12","landuse_secondary13","landuse_secondary14","landuse_secondary15","landuse_secondary16",
                       "landuse_secondary17","landuse_secondary18","veg_mvg2","veg_mvg3","veg_mvg4","veg_mvg5","veg_mvg7","veg_mvg9","veg_mvg10","veg_mvg11","veg_mvg15","veg_mvg16","veg_mvg17","veg_mvg18",
                       "veg_mvg19","veg_mvg21","veg_mvg22","veg_mvg24","veg_mvg25","veg_mvg26","veg_mvg27","veg_mvg29","veg_mvg31"))

formulas <- generate_formulas( 
  
  response = "pa", 
  
  smooth_variables = c("annmeantemp","meandiurnrange", 
                       
                       "precipseason"), 
  
  factor_variables = c("landuse_secondary1","landuse_secondary2","landuse_secondary3","landuse_secondary4","landuse_secondary5","landuse_secondary6","landuse_secondary7", 
                       
                       "landuse_secondary8","landuse_secondary9","landuse_secondary11","landuse_secondary12","landuse_secondary13","landuse_secondary14","landuse_secondary15","landuse_secondary16", 
                       
                       "landuse_secondary17","landuse_secondary18","veg_mvg2","veg_mvg3","veg_mvg4","veg_mvg5","veg_mvg7","veg_mvg9","veg_mvg10","veg_mvg11","veg_mvg15","veg_mvg16","veg_mvg17","veg_mvg18", 
                       
                       "veg_mvg19","veg_mvg21","veg_mvg22","veg_mvg24","veg_mvg25","veg_mvg26","veg_mvg27","veg_mvg29","veg_mvg31")) 
unique(train_data$species)



#### Generalised Linear Model (GLM) ######################################################################################
{recipe_ensemble <- train_data %>% recipe(formulas$recipe_formulas$base_formula)

#  ** 1. GLM Model Specification--------------------------------------------------------------------
  glm_spec <- logistic_reg() %>% 
    set_engine("glm", family = binomial(link="logit")) %>% 
    set_mode("classification")
  
  
  #  ** 2. Create the workflow-----------------------------------------------------------------------
  wf_glm <- workflow() %>% 
    add_recipe(recipe_ensemble) %>%  
    add_model(glm_spec)
  
  
  # **  3. Fit the model-----------------------------------------------------------------------------
  glm_model <- wf_glm %>% 
    fit(data = train_data)


#### Generalised Additive Model (GAM) ##################################################################################
gam_model <- gen_additive_mod(mode = 'classification') %>%
  set_engine("mgcv", family = binomial(link="logit")) %>%
  fit(formulas$gam_formula, data = train_data)   


#### Gradient Boosted Machine (GBM) ####################################################################################
tuneGrid_gbm <- expand.grid(
  learn_rate = learn_rate,
  tree_depth = tree_depth,
  min_n = min_n,
  trees = trees_gbm)


  # ** 1. GBM Model Specification-------------------------------------------------------------------
  gbm_spec <- boost_tree(
    mode = "classification", 
    trees = tune(), 
    learn_rate = tune(), 
    tree_depth = tune(), 
    min_n = tune()) %>% 
    set_engine("xgboost")
  
  
  # **  2. Create the workflow----------------------------------------------------------------------
  wf_gbm <- workflow() %>% 
    add_recipe(recipe_ensemble) %>%  
    add_model(gbm_spec)
  
  
  #  ** 3. Tune the model---------------------------------------------------------------------------
  gbm_results <- wf_gbm %>% 
    tune_grid(resamples = custom_folds, grid = tuneGrid_gbm, control = ctrl_grid)
  
  
  #  ** 4. Select the best parameters---------------------------------------------------------------
  best_params_gbm <- gbm_results %>% 
    select_best(metric = "roc_auc")
  
  
  # **  5. Finalize and fit the model---------------------------------------------------------------
  best_gbm_model <- wf_gbm %>% 
    finalize_workflow(best_params_gbm) %>% 
    fit(data = train_data)   


#### Random Forest ####################################################################################################
tune_rf <- tibble(mtry = mtry)

  #  ** 1. RF Model Specification-------------------------------------------------------------------
  rf_spec <- rand_forest(mtry = tune(), trees = 1000, mode = "classification") %>%
    set_engine("ranger")
  
  
  #  ** 2. Create the workflow----------------------------------------------------------------------
  wf_rf <- workflow() %>%
    add_recipe(recipe_ensemble) %>%  
    add_model(rf_spec)
  
  
  #  ** 3. Tune the model---------------------------------------------------------------------------
  rf_results <- wf_rf %>%
    tune_grid(resamples = custom_folds, grid = tune_rf, control = ctrl_grid)
  
  
  # **  4. Fit the model with best parameters-------------------------------------------------------
  best_params_rf <- rf_results %>% select_best(metric = "roc_auc")
  best_rf_model <- finalize_workflow(wf_rf, best_params_rf) %>%
    fit(data = train_data)


#### Artificial Neural Networks (ANN) #################################################################################
tuneGrid_ann <- expand.grid(hidden_units = hidden_units, penalty = penalty)


  #  ** 1. ANN Model Specification------------------------------------------------------------------
  ann_spec <- mlp(hidden_units = tune(), penalty = tune(), mode = "classification") %>%
    set_engine("nnet")
  
  
  #  ** 2. Create the workflow----------------------------------------------------------------------
  wf_ann <- workflow() %>%
    add_recipe(recipe_ensemble) %>% 
    add_model(ann_spec)
  
  
  #  ** 3. Tune the model---------------------------------------------------------------------------
  ann_results <- wf_ann %>%
    tune_grid(resamples = custom_folds, grid = tuneGrid_ann, control = ctrl_grid)
  
  
  #  ** 4. Fit the model with best parameters-------------------------------------------------------
  best_params_ann <- ann_results %>% select_best(metric = "roc_auc")
  best_ann_model <- finalize_workflow(wf_ann, best_params_ann) %>%
    fit(data = train_data)   }


#### Ensemble Predictions #############################################################################################
# Create a list of models
{model_list <- list(
  "glm" = glm_model,
  "gam" = gam_model,
  "gbm" = best_gbm_model,
  "rf"  = best_rf_model,
  "ann" = best_ann_model)

# Use lapply to generate predictions for the training data from each model in the list
pred_list_train <- lapply(model_list, function(model) {predict(model, new_data = train_data, type="prob")$.pred_1})

# Combine all the training predictions into a single data frame
pred_df_train <- do.call(cbind, pred_list_train)

# Calculate the ensemble prediction for the training data as the mean of the individual model predictions
train_data$pred_prob_ensemble <- rowMeans(pred_df_train)
train_data$pred_prob_ensemble <- normalised_hsi(train_data$pred_prob_ensemble)

# Determine the best threshold for classifying presence/absence based on the ensemble prediction
best_threshold_ensemble <- calculate_best_threshold(train_data, "pred_prob_ensemble", "pa")

# Use lapply to generate predictions for the test data from each model in the list
pred_list_test <- lapply(model_list, function(model) {predict(model, new_data = test_data, type="prob")$.pred_1})

# Combine all the test predictions into a single data frame
pred_df_test <- do.call(cbind, pred_list_test)

# Modify the test data to include ensemble predictions, predicted presence/absence, and observed presence/absence
test_data <- test_data %>% 
  mutate(pred_prob = normalised_hsi(rowMeans(pred_df_test)),
         model_type = "ensemble",
         pred_pa = ifelse(pred_prob > best_threshold_ensemble, 1, 0),
         obs_pa = pa) %>% 
  select(model_type, species, Lon, Lat, obs_pa, pred_pa, pred_prob)}

# Evaluate each model and bind the results together
results <- test_data %>% process_model_csv()
unique(train_data$species)

# Export data --------------------------------------------------------------------------------
write.csv(test_data,'./sdm_results/performance/v2/Dasyurus_viverrinus_ensemble.csv', row.names = F)
write.csv(pred_df_test,'./sdm_results/performance/v2/ensemble_sep/Dasyurus_viverrinus_ensemble_all.csv', row.names = F)


# mapping -----------------------------------------------------------------


tas <- read.csv('./sdm_data/tas_sdm_map.csv')
tas_map <- read.csv('./sdm_results/maps/tas_norm_maps_ensemble.csv');str(tas_map)

{model_list <- list(
  "glm" = glm_model,
  "gam" = gam_model,
  "gbm" = best_gbm_model,
  "rf"  = best_rf_model,
  "ann" = best_ann_model)

# Use lapply to generate predictions for the test data from each model in the list
pred_list <- lapply(model_list, function(model) {predict(model, new_data = tas, type="prob")$.pred_1})
# Combine all the test predictions into a single data frame
pred_df <- do.call(cbind, pred_list)}

unique(test_data$species)

tas_map <- tas_map %>% mutate(Dasyurus_viverrinus = normalised_hsi(rowMeans(pred_df)));str(tas_map)

df <- tas_map %>% select(Lon, Lat, Dasyurus_viverrinus)
df <- terra::rast(df, 'xyz')
plot(df)

write.csv(tas_map,'./sdm_results/maps/tas_norm_maps_ensemble.csv', row.names = F)


# Reset the environment ----------------------------------------------------------------------
{# Create a list of objects to be retained in the environment
  to_keep <- c("test_data_full", "train_data_full", "cl", "species_pool","num_cores",
               "mtry","hidden_units","penalty", "trees_gbm", "tree_depth","min_n","learn_rate")
  
# Identify all objects in the environment _except_ the ones specified in 'to_keep'
ls_var <- ls()
ls_var <- ls_var[!ls_var %in% to_keep]
  
# Remove all unwanted objects from the environment
rm(list=ls_var)
  
# Source an R script which probably contains functions or other necessary items
source("code/modelling_functions.R")    }


