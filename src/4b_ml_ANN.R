# =======================================================================================================================#
                                #Tune and and fit Artificial Neural Networks (ANN) model 
# =======================================================================================================================#

#### Clearn environment and set options ##################################################################################
{rm(list=ls()); options(scipen=999,digits=9); set.seed(12345)
  setwd("C:/Users/rjamin/dsdm_files/model_se_sdm")   }


#### Import functions ####################################################################################################
{import::from("code/modelling_functions.R",.all=T)          #Import custom functions from source file
 num_cores = 30                                             #Define cores for parallel processing 
  
  

#### Custom parameters and constants #####################################################################################

# Select file path ------------------------------------------------------------------------------
in_train = "sdm_data/tas_sdm_train.csv"
in_test = "sdm_data/tas_sdm_test.csv"
    
# Define hyper-parameters -----------------------------------------------------------------------  

# Range of hyper-parameters to tune over ####
penalty = c(0.001,0.0001,0.0001)                             #Number of units in the hidden model
hidden_units = c(12,16,32,64)                                         #Numeric value for the amount of weight decay

# Default hyper-parameters for predictor selection ####
default_penalty  =  0.001
default_hidden_units = 16   }

#### Data loading ########################################################################################################
{train_data_full <- read.csv(in_train)                         # Load training data
test_data_full <- read.csv(in_test)                            # Load test data
species_pool <- unique(train_data_full$species)   }            # Identify unique species

# Select species -------------------------------------------------------------------------------
sp <- species_pool[1];sp                                                              #Choose species index from species pool

{train_data <- train_data_full %>% filter(species == sp) %>% mutate(pa=as.factor(pa)) # Subset train set for selected species 
test_data <- test_data_full %>% filter(species == sp) %>% mutate(pa=as.factor(pa))    # Subset test set for selected species 


#### Artificial Neural Network (ANN) #####################################################################################
cl <- makePSOCKcluster(num_cores); registerDoParallel(cl)      #Set up parallel processing
tidymodels_prefer()                                            # Prefer tidymodels setup

# Tuning and validation settings ---------------------------------------------------------------
custom_folds <- group_vfold_cv(train_data, group = "fold")                            #Use 'fold' column to create k-folds
ctrl_grid <- control_grid(save_pred = TRUE, save_workflow = TRUE, verbose = FALSE)   }#Define control parameters for model tuning

# Define model formula -------------------------------------------------------------------------

formulas <- generate_formulas(
  response = "pa",
  smooth_variables = c("annmeantemp","meandiurnrange", "isothermality","tempseason","maxtempwarmmonth","mintempcoldmonth","tempannrange","meantempwetq","meantempdryq",
                       "meantempwarmq","meantempcoldq","annprecip","precipwetmonth","precipdrymonth","precipseason","precipwetq","precipdryq","precipwarmq",        
                       "precipcoldq","elevation","top_roughness","dist_fw","dist_road","fpar"),
  factor_variables = c("landuse_secondary1","landuse_secondary2","landuse_secondary3","landuse_secondary4","landuse_secondary5","landuse_secondary6","landuse_secondary7",
                       "landuse_secondary8","landuse_secondary9","landuse_secondary11","landuse_secondary12","landuse_secondary13","landuse_secondary14","landuse_secondary15","landuse_secondary16",
                       "landuse_secondary17","landuse_secondary18","veg_mvg2","veg_mvg3","veg_mvg4","veg_mvg5","veg_mvg7","veg_mvg9","veg_mvg10","veg_mvg11","veg_mvg15","veg_mvg16","veg_mvg17","veg_mvg18",
                       "veg_mvg19","veg_mvg21","veg_mvg22","veg_mvg24","veg_mvg25","veg_mvg26","veg_mvg27","veg_mvg29","veg_mvg31","soil_class3","soil_class4","soil_class5",        
                       "soil_class6","soil_class7","soil_class8","soil_class9","soil_class10","soil_class11","soil_class12","soil_class13","soil_class14"))

 
ann_recipe <- train_data %>% recipe(formulas$recipe_formulas$base_formula)
# 1. Select best predictor set for ANN ---------------------------------------------------------
{ann_recipe <- train_data %>% recipe(formulas$recipe_formulas$base_formula)

ann_model <- fit_ann(data = train_data, 
                     recipe = ann_recipe,                                     
                     hidden_units = 12,                     
                     penalty = 0.001,                               
                     custom_folds = custom_folds, 
                     control_grid = ctrl_grid)    }

unique(train_data$species)
# 2. Tune hyper-parameters and fit the best model ----------------------------------------------
{tune_ann <- expand.grid(hidden_units = hidden_units, penalty = penalty)

ann_model <- tune_and_fit_ann(data = train_data,                             
                              recipe = ann_recipe,                            
                              tune_grid = tune_ann,                          
                              custom_folds = custom_folds,                       
                              control_grid = ctrl_grid)   }
unique(train_data$species)

# 3. Tune Threshold to convert predictions into binomial ---------------------------------------
{train_data$pred_prob_ann <- ann_model %>% predict(train_data, type = "prob") %>%  `[[`(".pred_1") #Predict on the train data
train_data$pred_prob_ann <- normalised_hsi(train_data$pred_prob_ann)
best_threshold_ann <- calculate_best_threshold(train_data, "pred_prob_ann", "pa")   }              #Estimate best threshold 


# 4. Predict on test data using the best fit ANN model -----------------------------------------
{# Predict presence probabilities on the test set
test_data$pred_prob <- ann_model %>% predict(test_data, type = "prob") %>% `[[`(".pred_1")
test_data$pred_prob <- normalised_hsi(test_data$pred_prob)

# Process the test dataset: add predictions and some relevant information
test_data <- test_data %>% 
  mutate(model_type = "ann-only",
         pred_pa = ifelse(pred_prob > best_threshold_ann, 1, 0),
         obs_pa = pa) %>% 
  select(model_type, species, Lon, Lat, obs_pa, pred_pa, pred_prob) 
}


# Evaluate each model and bind the results together
results <- test_data %>% process_model_csv()

# Export data ----------------------------------------------------------------------------------
write.csv(test_data,'./sdm_results/performance/v2/Dasyurus_viverrinus_ann.csv', row.names = F)


# Mapping -----------------------------------------------------------------
tas <- read.csv('./sdm_data/se_sdm_map.csv'); str(tas)

tas$Dasyurus_viverrinus   <- ann_model %>% predict(tas, type = "prob") %>%  `[[`(".pred_1")
tas$Dasyurus_viverrinus <- normalised_hsi(tas$Dasyurus_viverrinus)

tas_map <- tas_map %>% mutate(Dasyurus_viverrinus  = tas$Dasyurus_viverrinus);str(tas_map)

df <- tas_map %>% select(Lon, Lat, Dasyurus_viverrinus)
df <- rast(df, 'xyz')
plot(df);str(tas_map)

write.csv(tas_map,'./sdm_results/maps/tas_norm_maps_ann.csv', row.names = F)


# Reset the environment ------------------------------------------------------------------------
{# Create a list of objects to be retained in the environment
  to_keep <- c("test_data_full", "train_data_full", "cl", "species_pool","num_cores", 
               "default_hidden_units","default_penalty","hidden_units","penalty")
  
  
  # Identify all objects in the environment _except_ the ones specified in 'to_keep'
  ls_var <- ls()
  ls_var <- ls_var[!ls_var %in% to_keep]
  
  # Remove all unwanted objects from the environment
  rm(list=ls_var)
  
  # Source an R script which probably contains functions or other necessary items
  source("./code/modelling_functions.R")   }



