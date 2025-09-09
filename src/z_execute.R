#######################################################################################################################
## Fit a FFN DNN to continuous data (regression problem)                                                             ###
#######################################################################################################################
{rm(list=ls()); options(scipen=999,digits=9) # clean up and set options
  setwd("C:/Users/bwbrook/Downloads/DL/drought_seedlings")} # set the base working directory 
#######################################################################################################################

### Import functions and set constants ################################################################################
{import::from("dnn_func.r", .all=T) # import into libs from source
  st = tensorflow::tf$distribute$MultiWorkerMirroredStrategy() # Initialize multi-GPUs
  seed = 280823 # using the date
  n_folds = 5 # number of folds for k-fold cross-validation
  
  in_file = "drought_seedlings.csv" # path to species data CSV
  
  dep_name = "drought3"
  cat_layers = c("rep", "glauco", "intum", "mum_ID") # specify the features that contain categorical data
  
  # Define the initial search grid by full factorial (can take 1 or more values for each hyperparameter)
  hyp_grid <- expand.grid(w=c(64), d=c(3), dr=c(0.5), l1_str=c(0,1e-3,1e-2), l2_str=c(0,1e-3,1e-2), b=c(64)) }
#######################################################################################################################

{set.seed(seed)
 dat <- read.csv(in_file) %>% # Read data file of continuous and categorical variables
  sample_frac(size = 1, replace = FALSE) %>% # shuffle the data
  mutate(fold = sample(1:(n_folds+1), size = n(), replace = TRUE)) # create a column for the fold number

# Use these two lines to re-fit model without mum_ID (or comment out)
dat <- dat %>% select(-mum_ID) # drop mum_ID
cat_layers <- setdiff(cat_layers, "mum_ID") # drop mum_ID

train <- dat %>% filter(fold <= n_folds) # split the data into train and test
test <- dat %>% filter(fold == (n_folds+1)) %>% mutate(fold = NA)

cont_layers <- setdiff(names(dat), c(dep_name, cat_layers, "fold")) # select only the continuous layers
cat_levels <- dat %>% select(all_of(cat_layers)) %>% lapply(., unique) # get the unique levels of each categorical

train_scaler <- fit_scaler(train, cont_layers)  # fit the scaler to the train data (no leakage from test data)

train <- transform_data(train, dep_name, cat_layers, cat_levels, cont_layers, train_scaler) # transform train data
test <- transform_data(test, dep_name, cat_layers, cat_levels, cont_layers, train_scaler) # transform test data
mod <- list() } # initialise list for storing model object and evals

# Create a Feed-forward DNN (FFN) using hyper-parameters tuned in cross-validated grid search
{mod$dnn <- build_model(no_dense_layers=3, dense_width=64, dropout=0.5, l1_reg=0, l2_reg=0, 
                       compression_layer=16, input_dim=dim(train)[2]-2) # -2 for dep_name and fold
#######################################################################################################################
 mod <- fit_dnn(d=train, dep_name, model=mod$dnn, val_fold=1, epochs=100, lr=0.001, min_lr=0.1, d_frac=1, strategy=st)
 predictive_metrics(test, dep_name, mod$dnn) }

# Naive MAE = 2.020
# Result with mum_ID included:  mae = 0.769, r_sq_pred = 0.715
# Result with mum_ID excluded:  mae = 0.772, r_sq_pred = 0.721
# Conclusion: the deep-learning model can entirely compensate for the loss of mum_ID, using other predictors

# Drop out height, width, n_nodes and length and re-fit with mum_ID + rep, intum, glauco:
# Result without phenotypic:    mae = 1.694, r_sq_pred = -0.007

mean(abs(mean(train$drought3) - test$drought3)) # Naive MAE

feature_importance(test_data=test, dep_var=dep_name, model=mod$dnn) # Show for full model

#######################################################################################################################
### Tune on the hyper-parameter grid
hyp <- hyp_grid_search(dat=train, dep_name, grid=hyp_grid, epochs=100, val_fold=NULL)
write.csv(hyp, "hyp_v4.csv", row.names = FALSE)

### Run k-fold cross-validation on the final selected hyper-parameter combination for tuning no. epochs) ##############
mod$kfold <- kfold_tuning(d=train, dep_name, model=mod$dnn, epochs=50, strategy=strategy, min_patience=5)
#######################################################################################################################
