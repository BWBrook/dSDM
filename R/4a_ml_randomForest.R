# =======================================================================================================================#
                                     #Tune and and fit Random Forest (RF) model 
# =======================================================================================================================#

#### Clearn environment and set options ##################################################################################
{rm(list=ls()); options(scipen=999,digits=9); set.seed(12345)
  setwd("C:/Users/rjamin/dsdm_files/model_se_sdm")   } 


#### Import functions ####################################################################################################
{import::from("code/modelling_functions.R",.all=T)          #Import custom functions from source file
  num_cores = 30                                           #Define cores for parallel processing 

  
  
#### Custom parameters and constants #####################################################################################
  
# Select file path for training and testing datasets --------------------------------------------
in_train = "sdm_data/tas_sdm_train.csv"
in_test = "sdm_data/tas_sdm_test.csv"
  
# Define model hyper-parameters -----------------------------------------------------------------  
  
## Range of hyper-parameters to tune over
tune_rf <- tibble(mtry = 1:15)   }                                #Number of variables randomly sampled as candidates at each split
#trees = c(1:100) * 100                                           #Number of trees to grow.This can be tuned in tune_and_fit_rf function

# Default hyper-parameters for predictor selection ####
default_mtry = 7                                                  

#### Data loading ########################################################################################################
{train_data_full <- read.csv(in_train)                         # Load training data
test_data_full <- read.csv(in_test)                            # Load test data
species_pool <- unique(train_data_full$species)   }            # Identify unique species

# Select species -------------------------------------------------------------------------------
sp <- species_pool[9];sp                                                              #Choose species index from species pool

{train_data <- train_data_full %>% filter(species == sp) %>% mutate(pa=as.factor(pa)) # Subset train set for selected species 
test_data <- test_data_full %>% filter(species == sp) %>% mutate(pa=as.factor(pa))    # Subset test set for selected species 
  
  
#### Random Forest (RF) #####################################################################################
cl <- parallel::makePSOCKcluster(num_cores); doParallel::registerDoParallel(cl)      #Set up parallel processing
tidymodels::tidymodels_prefer()                                            # Prefer tidymodels setup
  
# Tuning and validation settings ---------------------------------------------------------------
custom_folds <- group_vfold_cv(train_data, group = "fold")                            #Use 'fold' column to create k-folds
ctrl_grid <- control_grid(save_pred = TRUE, save_workflow = TRUE, verbose = FALSE)   }#Define control parameters for model tuning

#formulas <- generate_formulas(
#  response = "pa",
#  smooth_variables = c("annmeantemp","meandiurnrange", "isothermality","tempseason","maxtempwarmmonth","mintempcoldmonth","tempannrange","meantempwetq","meantempdryq",
#                       "meantempwarmq","meantempcoldq","annprecip","precipwetmonth","precipdrymonth","precipseason","precipwetq","precipdryq","precipwarmq",        
#                       "precipcoldq","elevation","top_roughness","dist_fw","dist_road","fpar"),
#  factor_variables = c("landuse_secondary1","landuse_secondary2","landuse_secondary3","landuse_secondary4","landuse_secondary5","landuse_secondary6","landuse_secondary7",
#                       "landuse_secondary8","landuse_secondary9","landuse_secondary11","landuse_secondary12","landuse_secondary13","landuse_secondary14","landuse_secondary15","landuse_secondary16",
#                       "landuse_secondary17","landuse_secondary18","veg_mvg2","veg_mvg3","veg_mvg4","veg_mvg5","veg_mvg7","veg_mvg9","veg_mvg10","veg_mvg11","veg_mvg15","veg_mvg16","veg_mvg17","veg_mvg18",
#                       "veg_mvg19","veg_mvg21","veg_mvg22","veg_mvg24","veg_mvg25","veg_mvg26","veg_mvg27","veg_mvg29","veg_mvg31","soil_class3","soil_class4","soil_class5",        
#                       "soil_class6","soil_class7","soil_class8","soil_class9","soil_class10","soil_class11","soil_class12","soil_class13","soil_class14"))

formulas <- generate_formulas(
  response = "pa",
  smooth_variables = c("annmeantemp","meandiurnrange", "tempseason","meantempwetq","meantempdryq",
                       "annprecip","precipseason","precipwetq","precipdryq","precipwarmq",        
                       "precipcoldq","elevation","dist_fw","dist_road","fpar"),
  factor_variables = c("landuse_secondary1","landuse_secondary2","landuse_secondary3","landuse_secondary4","landuse_secondary5","landuse_secondary6","landuse_secondary7",
                       "landuse_secondary8","landuse_secondary9","landuse_secondary11","landuse_secondary12","landuse_secondary13","landuse_secondary14","landuse_secondary15","landuse_secondary16",
                       "landuse_secondary17","landuse_secondary18","veg_mvg2","veg_mvg3","veg_mvg4","veg_mvg5","veg_mvg7","veg_mvg9","veg_mvg10","veg_mvg11","veg_mvg15","veg_mvg16","veg_mvg17","veg_mvg18",
                       "veg_mvg19","veg_mvg21","veg_mvg22","veg_mvg24","veg_mvg25","veg_mvg26","veg_mvg27","veg_mvg29","veg_mvg31"))

unique(train_data$species)

# Define model formula -------------------------------------------------------------------------


formulas <- generate_formulas(
  response = "pa",
  smooth_variables = c("annmeantemp","meandiurnrange",
                       "precipseason"),
  factor_variables = c("landuse_secondary1","landuse_secondary2","landuse_secondary3","landuse_secondary4","landuse_secondary5","landuse_secondary6","landuse_secondary7",
                       "landuse_secondary8","landuse_secondary9","landuse_secondary11","landuse_secondary12","landuse_secondary13","landuse_secondary14","landuse_secondary15","landuse_secondary16",
                       "landuse_secondary17","landuse_secondary18","veg_mvg2","veg_mvg3","veg_mvg4","veg_mvg5","veg_mvg7","veg_mvg9","veg_mvg10","veg_mvg11","veg_mvg15","veg_mvg16","veg_mvg17","veg_mvg18",
                       "veg_mvg19","veg_mvg21","veg_mvg22","veg_mvg24","veg_mvg25","veg_mvg26","veg_mvg27","veg_mvg29","veg_mvg31"))


# 1. Select best predictor set for rf ---------------------------------------------------------
{rf_recipe <- train_data %>% recipe(formulas$recipe_formulas$base_formula)

rf_model <- fit_rf(data = train_data,
                   recipe = rf_recipe, 
                   mtry =  7, 
                   trees = 1000,
                   custom_folds = custom_folds, 
                   control_grid = ctrl_grid)   }                                #Modify the formula to achieve the best AUC of ROC 


# 2. Use our function to tune hyperparameters and fit the best model --------------------------
rf_model <- tune_and_fit_rf(data = train_data,
                            recipe = rf_recipe, 
                            tune_grid = tune_rf, 
                            custom_folds = custom_folds, 
                            control_grid = ctrl_grid)


# 3. Tune Threshold for RF ---------------------------------------------------------------------
{train_data$pred_prob <- rf_model %>% predict(train_data, type = "prob") %>%  `[[`(".pred_1")
train_data$pred_prob <- normalised_hsi(train_data$pred_prob)
best_threshold <- calculate_best_threshold(train_data, "pred_prob", "pa")   }


# 4. Predict on test data using best fit RF model ----------------------------------------------
{# Predict presence probabilities on the test set
test_data$pred_prob <- rf_model %>% predict(test_data, type = "prob") %>%  `[[`(".pred_1")
test_data$pred_prob <- normalised_hsi(test_data$pred_prob)


# Process the test dataset: add predictions and some relevant information
test_data <- test_data %>% 
  mutate(model_type = "rf-only",
         pred_pa = ifelse(pred_prob > best_threshold, 1, 0),
         obs_pa = pa) %>% 
  select(model_type, species, Lon, Lat, obs_pa, pred_pa, pred_prob)   }

unique(train_data$species)
test_data <- read.csv('./sdm_results/performance/v2/Notamacropus_rufogriseus_rf.csv')
results <- test_data %>% process_model_csv()

unique(train_data$species);unique(test_data$species)

# Export data  ---------------------------------------------------------------------------------
write.csv(test_data,'./sdm_results/performance/v2/Dasyurus_viverrinus_rf.csv', row.names = F)


# Mapping -----------------------------------------------------------------

tas <- read.csv('./sdm_data/tas_sdm_map.csv')
tas_map <- read.csv('./sdm_results/maps/tas_norm_maps_rf.csv');str(tas_map)

unique(test_data$species)

tas$Dasyurus_viverrinus <- rf_model %>% predict(tas, type = "prob") %>%  `[[`(".pred_1")
tas$Dasyurus_viverrinus <- normalised_hsi(tas$Dasyurus_viverrinus)

tas_map <- tas_map %>% mutate(Dasyurus_viverrinus = tas$Dasyurus_viverrinus);str(tas_map)

df <- tas_map %>% select(Lon, Lat, Dasyurus_viverrinus)
df <- terra::rast(df, 'xyz')
plot(df)

write.csv(tas_map,'./sdm_results/maps/tas_norm_maps_rf.csv', row.names = F)

# Reset the environment ------------------------------------------------------------------------
{# Create a list of objects to be retained in the environment
  to_keep <- c("test_data_full", "train_data_full", "cl", "species_pool","num_cores", "default_mtry","tune_rf")
  
  # Identify all objects in the environment _except_ the ones specified in 'to_keep'
  ls_var <- ls()
  ls_var <- ls_var[!ls_var %in% to_keep]
  
  # Remove all unwanted objects from the environment
  rm(list=ls_var)
  
  # Source an R script which probably contains functions or other necessary items
  source("code/modelling_functions.R")    }


