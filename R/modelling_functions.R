# =======================================================================================================================#
                                  #Functions for Species distribution modelling  
# =======================================================================================================================#

# R functions available in this library: ################################################################################

# calculate_best_threshold(): Calculates the optimal threshold for binary classification based on maximizing the F1 score.
# generate_formulas(): Dynamically creates formulae for modeling based on target and predictor variables.
# fit_rf(): Fits a Random Forest (RF) model with specified or default hyperparameters. 
            #Evaluates the model using ROC AUC and returns the best RF model trained on the entire dataset.
# tune_and_fit_rf(): Tunes hyperparameters for a Random Forest (RF) model based on ROC AUC. 
            #Plots the hyperparameter tuning results and returns the best RF model with tuned hyperparameters trained on the entire dataset.
# fit_ann(): Fits an Artificial Neural Network (ANN) model with specified or default hyperparameters.
            #Evaluates the model using ROC AUC and returns the best ANN model trained on the entire dataset.
# tune_and_fit_ann(): Tunes hyperparameters for an Artificial Neural Network (ANN) model based on ROC AUC.
            #Plots the hyperparameter tuning results and returns the best ANN model with tuned hyperparameters trained on the entire dataset.
# fit_gbm(): Fits a Gradient Boosted Machine (GBM) model without hyperparameter tuning.
            #Evaluates the model using ROC AUC and returns the best GBM model trained on the entire dataset.
# tune_and_fit_gbm(): Tunes hyperparameters for a Gradient Boosted Machine (GBM) model based on ROC AUC.
            #Plots the hyperparameter tuning results and returns the best GBM model with tuned hyperparameters trained on the entire dataset.
#______________________________________________________________________________________________________________________#


### Import specific CRAN package functions for use in custom functions ###################################################
{import::here(length, ls, paste, rm, source, .from = "base")
import::here(arrange, bind_rows, collapse, filter, group_by, group_map, if_else, mutate, n, pull, select, slice, summarise, .from = "dplyr")
import::here(registerDoParallel, .from = "doParallel")
import::here(aes, coord_flip, element_blank, element_text, expand_limits, facet_wrap, geom_bar, geom_errorbar, geom_histogram, geom_hline, 
             geom_label, geom_line, geom_point, geom_smooth, geom_tile, geom_vline, ggplot, guide_legend, guides, labs, 
             scale_color_gradient, scale_color_manual, scale_color_viridis_d, scale_fill_manual, scale_fill_viridis_c, scale_linetype_manual, 
             scale_shape_manual, scale_size_continuous, scale_x_continuous, scale_y_log10, theme, theme_bw, theme_classic, theme_dark, 
             theme_gray, theme_light, theme_minimal, theme_void, unit, .from = "ggplot2")
import::here("%>%", .from = "magrittr")
import::here(makePSOCKcluster, .from = "parallel")
import::here(boost_tree, fit, gen_additive_mod, logistic_reg, mlp, rand_forest, set_engine, set_mode, .from = "parsnip")
import::here(map2, map_dfr, reduce, .from = "purrr")
import::here(recipe, step_interact, .from = "recipes")
import::here(group_vfold_cv, .from = "rsample")
import::here(tibble, .from = "tibble")
import::here(tidymodels_prefer, .from = "tidymodels")
import::here(collect_metrics, control_grid, finalize_workflow, fit_resamples, select_best, show_notes, tune, tune_grid, .from = "tune")
import::here(write.csv, .from = "utils")
import::here(add_model, add_recipe, workflow, .from = "workflows")
import::here(accuracy, f_meas, metric_set, precision, recall, roc_auc, .from = "yardstick")
import::here("pROC", roc, auc)}
####
 
evaluate_model <- function(df) {
  # Convert to factor
  df$obs_pa <- as.factor(df$obs_pa)
  df$pred_pa <- as.factor(df$pred_pa)
  
  # Manually calculate TP, TN, FP, and FN
  tp <- sum(df$obs_pa == 1 & df$pred_pa == 1)
  tn <- sum(df$obs_pa == 0 & df$pred_pa == 0)
  fp <- sum(df$obs_pa == 0 & df$pred_pa == 1)
  fn <- sum(df$obs_pa == 1 & df$pred_pa == 0)
  
  # Calculate sensitivity, specificity, ppv, and npv
  sensitivity <- ifelse(tp + fn == 0, 0, tp / (tp + fn))
  specificity <- ifelse(tn + fp == 0, 0, tn / (tn + fp))
  ppv <- ifelse(tp + fp == 0, 0, tp / (tp + fp))
  npv <- ifelse(tn + fn == 0, 0, tn / (tn + fn))
  
  # Create adjusted versions for MCC calculation
  mcc_tp <- tp
  mcc_tn <- tn
  mcc_fp <- fp
  mcc_fn <- fn
  
  # Add one to mcc_tp, mcc_tn, mcc_fp, mcc_fn if their product is zero
  if (mcc_tp * mcc_tn * mcc_fp * mcc_fn == 0) {
    mcc_tp <- max(mcc_tp,1)
    mcc_tn <- max(mcc_tn,1)
    mcc_fp <- max(mcc_fp,1)
    mcc_fn <- max(mcc_fn,1)
  }
  
  # Calculate Matthews Correlation Coefficient (MCC) with adjusted values
  mcc <- (mcc_tp*mcc_tn - mcc_fp*mcc_fn) / sqrt((mcc_tp+mcc_fp)*(mcc_tp+mcc_fn)*(mcc_tn+mcc_fp)*(mcc_tn+mcc_fn))
  
  # Calculate F1 score
  f1 <- ifelse(ppv + sensitivity == 0, 0, 2 * ((ppv * sensitivity) / (ppv + sensitivity)))
  
  # Calculate balanced accuracy
  ba <- (sensitivity + specificity) / 2
  
  # Calculate AUC-ROC and TSS
  # Calculate AUC-ROC and TSS
  if(length(unique(df$obs_pa)) > 1) {
    roc_obj <- pROC::roc(df$obs_pa, df$pred_prob)
    auc_roc <- pROC::auc(roc_obj)
  } else {
    roc_obj <- NA
    auc_roc <- NA
  }
  
  tss <- sensitivity + specificity - 1
  
  # Calculate AUC-PR
  if(length(unique(df$obs_pa)) > 1) {
    pr_obj <- PRROC::pr.curve(df$pred_prob, weights.class0 = df$obs_pa == 0, weights.class1 = df$obs_pa == 1)
    auc_pr <- pr_obj$auc.integral
  } else {
    auc_pr <- NA
  }
  
  
  return(data.frame(
    model_type = unique(df$model_type),
    species = unique(df$species),
    tp = tp,
    tn = tn,
    fp = fp,
    fn = fn,
    sens = round(sensitivity,2),
    spec = round(specificity,2),
    ba = round(ba,2),
    f1 = round(f1,2),
    auc_roc = round(auc_roc,2),
    auc_pr = round(auc_pr,2),
    tss = round(tss,2),
    mcc = round(mcc,2)
  ))
}


process_model_csv <- function(df) {
  grouped_df <- df %>% group_by(model_type, species) # Group dataframe by species and model_type
  results <- grouped_df %>% group_map(~ evaluate_model(.x), .keep = TRUE) %>% 
    purrr::map(~dplyr::as_tibble(.x, .name_repair = "universal")) # Convert each data frame to a tibble
  return(bind_rows(results)) # Bind all results together into one dataframe
}

normalised_hsi <- function(x) {
  (x - min(x, na.rm = TRUE)) / (max(x, na.rm = TRUE) - min(x, na.rm = TRUE))}

####
### Generate formula for tidymodels recipe and GAM ##############################################
generate_formulas <- function(response, smooth_variables = NULL, factor_variables = NULL, interactions = NULL) {
  # Initialize a function to create formulas based on input variables.
  
  # Args:
  #   response: The target/response variable.
  #   smooth_variables: Variables to be used with smoothing functions (like splines) in GAM.
  #   factor_variables: Categorical variables to be considered as factors.
  #   interactions: Variables for which interactions should be considered.
  
  # Returns:
  #   A list with two formula components:
  #     - recipe_formulas: Contains base and interaction formulas.
  #     - gam_formula: A formula for generalized additive models (GAM).
  
  # Combine smooth and factor variables, removing duplicates.
  all_variables <- unique(c(smooth_variables, factor_variables))
  
  # Construct the base formula string (response ~ predictor1 + predictor2 + ...).
  base_formula_str <- paste(response, paste(all_variables, collapse = " + "), sep = " ~ ")
  
  # Constructing the GAM formula with smoothing terms for specified variables.
  # If there are any smooth variables, apply smoothing. Otherwise, use an empty string.
  gam_smooth_terms <- ifelse(length(smooth_variables) > 0, paste0("s(", smooth_variables, ")", collapse = " + "), "")
  # Combine the smoothed terms and factor variables to create the full GAM formula string.
  gam_formula_str <- paste(response, paste(c(gam_smooth_terms, factor_variables), collapse = " + "), sep = " ~ ")
  
  # Initialize interaction terms.
  interaction_term <- NULL
  interaction_term_recipe <- NULL
  
  # If there are interaction terms and there's more than one of them, construct the interaction term.
  if(!is.null(interactions) && length(interactions) > 1) {
    interaction_term <- reduce(interactions, ~ paste0(.x, ":", .y))
    # Convert interaction term string to a formula.
    interaction_term_recipe <- as.formula(paste("~", interaction_term))
  }
  
  # Return the constructed formulas in a list.
  return(
    list(
      # Recipe formulas containing both base and interaction formulas.
      recipe_formulas = list(
        base_formula = as.formula(base_formula_str),
        interaction_formula = interaction_term_recipe),
      # GAM formula with smoothing terms.
      gam_formula = as.formula(gam_formula_str))
  )
}
####


####
### Calculate the best threshold for a binary classification based on the F1 scores #############
calculate_best_threshold <- function(data, prob_col, truth_col) {
  # Initialize function to calculate the best threshold for binary classification.
  
  # Args:
  #   data: A data frame containing the true class labels and predicted probabilities.
  #   prob_col: Name of the column with predicted probabilities.
  #   truth_col: Name of the column with true class labels.
  
  # Returns:
  #   The optimal threshold based on the maximum F1 score.
  
  # Define the lower limit for possible threshold values, ensuring a buffer of 0.01 to avoid extreme values.
  min_prob <- min(data[[prob_col]]) + 0.01
  
  # Define the upper limit for possible threshold values, ensuring a buffer of 0.01 to avoid extreme values.
  max_prob <- max(data[[prob_col]]) - 0.01
  
  # Create a sequence of potential threshold values ranging between the defined limits with a step of 0.01.
  thresholds <- seq(min_prob, max_prob, by = 0.01)
  
  # Calculate the F1 score for each possible threshold using the map_dfr function.
  f1_results <- thresholds %>%
    map_dfr(function(thresh) {
      
      # Convert predicted probabilities to binary predictions based on the current threshold.
      preds <- as.factor(ifelse(data[[prob_col]] > thresh, 1, 0))
      
      # Compute the F1 score for the current threshold.
      f1_val <- f_meas(data.frame(truth = data[[truth_col]], estimate = preds), truth = "truth", estimate = "estimate", beta = 1)
      
      # Store the threshold and its corresponding F1 score in a tibble (a type of dataframe).
      tibble(threshold = thresh, F1 = f1_val$.estimate)
    })
  
  # Determine the threshold that results in the highest F1 score.
  best_threshold <- f1_results %>%
    arrange(desc(F1)) %>%       # Order by descending F1 scores.
    slice(1) %>%                # Select the top row.
    pull(threshold)             # Extract the threshold value from that row.
  
  # Compute the proportion of positive cases in the dataset.
  prevalence <- round(length(which(data[[truth_col]] == 1)) / nrow(data), 2)
  
  # Calculate the standard error (SE) for the prevalence.
  n <- nrow(data)
  SE <- sqrt(prevalence * (1 - prevalence) / n)
  
  # Create a plot visualizing the F1 scores across the various thresholds.
  p <- f1_results %>%
    ggplot(aes(x = threshold, y = F1)) +                                      # Specify plot data and axes.
    geom_line(aes(color = "F1 Score"), linewidth = 0.75) +                    # Plot F1 scores as a line.
    theme_bw() +                                                              # Apply a theme to the plot.
    geom_vline(aes(xintercept = best_threshold, linetype = "Best Threshold"), # Highlight the best threshold.
               alpha = .6, color="red", size=0.75) +
    geom_vline(aes(xintercept = prevalence, linetype = "Prevalence"),         # Highlight the prevalence.
               alpha = .6, color="blue", size=0.75) +
    geom_vline(aes(xintercept = 0.5),                                         # Highlight the neutral threshold of 0.5.
               alpha = .6, color="grey85", size=0.75) +
    # Set the plot limits, labels, and other aesthetic properties.
    expand_limits(x = c(0, 1),y = c(0, 1)) +
    labs(subtitle = "F1 score across thresholds",
         x = "Threshold Value",
         y = "F1 Score"
    ) +
    theme(plot.title = element_text(hjust = 0.5, size = 16, face = "bold"),
          axis.title.x = element_text(vjust=-0.5),
          axis.title.y = element_text(vjust=0.5),
          legend.position = "right",
          legend.title = element_blank(),
          legend.spacing.y = unit(0.5, "cm"), 
          legend.direction = "vertical"
    ) +
    scale_color_viridis_d(end = 0.9, name = "") +
    scale_x_continuous(expand = c(0.05, 0.05)) + 
    scale_linetype_manual(values = c("Best Threshold" = "dashed", "Prevalence" = "dotted"), 
                          guide = guide_legend(override.aes = list(color = "black")))+
    guides(linetype = guide_legend(nrow=2, override.aes = list(size=1.5)))
  print(p) # Display the plot.
  
  # Print the calculated best threshold and the prevalence.
  cat("Selected threshold:", round(best_threshold,2), "\n")
  cat("Prevalence:", prevalence, "\n")
  
  # Provide advice on whether to use the best threshold or the prevalence.
  if (abs(best_threshold - prevalence) <= SE) {
    cat("The best threshold is within 1 SE of the prevalence. Consider using the prevalence as the threshold to avoid overfitting.\n")
  } else {
    cat("The best threshold is not within 1 SE of the prevalence. Use selected threshold.\n")
  }
  
  return(best_threshold) # Return the best threshold value.
}
####


####
### Fit Random Forest (RF) model without hyperparameter tuning ########################################################
fit_rf <- function(data, recipe, custom_folds, control_grid, mtry = NULL, trees = 1000) {
# Fits a Random Forest (RF) model with either specified or default hyperparameters.
# Evaluates the model using ROC AUC and returns the best RF model trained on the entire dataset.
#
# Args:
#   data: A data frame that will be used to train the model.
#   recipe: A recipe object specifying preprocessing steps and formula.
#   custom_folds: A rsample object specifying cross-validation folds.
#   control_grid: A control object for the resampling process.
#   mtry: An optional numeric value specifying the number of variables randomly sampled at each split.
#   trees: An optional numeric value specifying the number of trees to grow in the forest.
#
# Returns:
#   The best RF model trained on the entire dataset.

  # If mtry isn't provided, use the square root of the number of predictors
  if (is.null(mtry)) {
    num_predictors <- length(recipe$formula()[-1])  # Length of the predictors in the formula minus the response variable
    mtry <- floor(sqrt(num_predictors))
  }
  
  # Random Forest specification
  rf_spec <- rand_forest(mtry = mtry, trees = trees, mode = "classification") %>%
    set_engine("ranger")
  
  # Set up a workflow
  wf <- workflow() %>% 
    add_recipe(recipe) %>% 
    add_model(rf_spec)
  
  # Fit the model with the custom cross-validation folds
  rf_results <- wf %>% 
    fit_resamples(resamples = custom_folds, control = control_grid)
  
  # Extract ROC AUC metrics
  roc_auc <- rf_results %>% 
    collect_metrics() %>% 
    filter(.metric == "roc_auc") %>% 
    pull(mean)
  
  # Print ROC AUC to the console
  cat("\nROC AUC for mtry =", mtry, "and trees =", trees, ":", round(roc_auc, 4), "\n")
  
  # Train the best model on the entire training data
  best_params <- rf_results %>% select_best(metric = "roc_auc")
  best_rf_model <- finalize_workflow(wf, best_params) %>% fit(data = data)
  
  return(best_rf_model)
}
####


####
### Tune hyper-parameters and fit the best tuned Random Forest (RF) model #####################################################
tune_and_fit_rf <- function(data, recipe, tune_grid, custom_folds, control_grid, trees = 1000) {
# Tunes hyperparameters for a Random Forest (RF) model based on ROC AUC. 
# It then returns the best RF model trained on the entire dataset.
#
# Args:
#   data: A data frame that will be used to train the model.
#   recipe: A recipe object specifying preprocessing steps and formula.
#   tune_grid: A grid of hyperparameters to search over.
#   custom_folds: A rsample object specifying cross-validation folds.
#   control_grid: A control object for the resampling process.
#   trees: An optional numeric value specifying the number of trees to grow in the forest.
#
# Returns:
#   The best RF model with tuned hyperparameters trained on the entire dataset.

  # Random Forest specification
  rf_spec <- rand_forest(mtry = tune(), trees = trees, mode = "classification") %>%
    set_engine("ranger")
  
  # Set up a workflow
  wf <- workflow() %>% 
    add_recipe(recipe) %>% 
    add_model(rf_spec)
  
  # Tune the model with the custom cross-validation folds
  rf_results <- wf %>% 
    tune_grid(resamples = custom_folds, grid = tune_grid, control = control_grid)
  
  # Get best parameters based on ROC AUC
  best_params <- rf_results %>% select_best(metric = "roc_auc")
  
  # Print best parameters to the console
  cat("\n Selected Hyper-parameters:\n")
  print(best_params)
  
  # Plot hyperparameter tuning results
  tuning_results <- rf_results %>% collect_metrics() %>% filter(.metric == "roc_auc")
  
  p <- ggplot(tuning_results, aes(x = mtry, y = mean)) +
    geom_line(aes(group = 1), color = "#69b3a2") +
    geom_point(color = "black", size = 1.25) +
    labs(subtitle = "Performance across tuning parameters",
         x = "mtry",
         y = "ROC AUC") +
    theme_bw() +
    theme(plot.title = element_text(hjust = 0.5, size = 16, face = "bold"),
          plot.subtitle = element_text(hjust = 0.5, size = 14))
  
  print(p)
  
  # Train the best model on the entire training data
  best_rf_model <- finalize_workflow(wf, best_params) %>% fit(data = data)
  
  return(best_rf_model)
}
####

fit_ann_neuralnet <- function(data, formula, hidden_units = NULL, penalty = NULL) {
  if (is.null(hidden_units)) {
    hidden_units <- 128  # Default to mid-range
  }

  if (is.null(penalty)) {
    penalty <- 0.001  # Default penalty
  }

  # Define the model using neuralnet
  ann_spec_neuralnet <- neuralnet(
    formula = formula,  # Define the formula for the model
    data = data,
    hidden = c(hidden_units),   # Number of hidden neurons
    algorithm = "rprop+",       # Training algorithm
    err.fct = "ce",             # Error function
    act.fct = "logistic",       # Activation function
    linear.output = FALSE,      # Set to FALSE for classification
    lifesign = "minimal",
    threshold = 0.01
  )

  # Return the model
  return(ann_spec_neuralnet)
}

####
### Fit Artificial Neural Networks (ANN) model without hyperparameter tuning ########################################################
fit_ann <- function(data, recipe, custom_folds, control_grid, hidden_units = NULL, penalty = NULL) {
# Fits an Artificial Neural Network (ANN) model with either specified or default hyperparameters.
# Evaluates the model using ROC AUC and returns the best ANN model trained on the entire dataset.
#
# Args:
#   data: A data frame that will be used to train the model.
#   recipe: A recipe object specifying preprocessing steps and formula.
#   custom_folds: A rsample object specifying cross-validation folds.
#   control_grid: A control object for the resampling process.
#   hidden_units: An optional numeric value specifying the number of hidden units in the ANN.
#   penalty: An optional numeric value specifying the penalty (regularization term).
#
# Returns:
#   The best ANN model trained on the entire dataset.
  # If hidden_units and penalty aren't provided, use default values
  if (is.null(hidden_units)) {
    hidden_units <- 64  # Default to mid-range
  }
  
  if (is.null(penalty)) {
    penalty <- 0.01  # Default penalty
  }
  
  # ANN Model Specification
  ann_spec <- mlp(hidden_units = hidden_units, penalty = penalty, mode = "classification") %>%
    set_engine("nnet")
  
  # Set up a workflow for ANN
  wf_ann <- workflow() %>% 
    add_recipe(recipe) %>% 
    add_model(ann_spec)
  
  # Fit the model with the custom cross-validation folds
  ann_results <- wf_ann %>% 
    fit_resamples(resamples = custom_folds, control = control_grid)
  
  # Extract ROC AUC metrics
  roc_auc <- ann_results %>% 
    collect_metrics() %>% 
    filter(.metric == "roc_auc") %>% 
    pull(mean)
  
  # Print ROC AUC to the console
  cat("\nROC AUC for hidden_units =", hidden_units, "and penalty =", penalty, ":", round(roc_auc, 4), "\n")
  
  # Train the best model on the entire training data
  best_params <- ann_results %>% select_best(metric = "roc_auc")
  best_ann_model <- finalize_workflow(wf_ann, best_params) %>% fit(data = data)
  
  return(best_ann_model)
}
####


####
### Tune hyper-parameters and fit the best tuned Artificial Neural Networks (ANN) model ###########################################
tune_and_fit_ann <- function(data, recipe, tune_grid, custom_folds, control_grid) {
# Tunes hyperparameters for an Artificial Neural Network (ANN) model based on ROC AUC. 
# It then returns the best ANN model trained on the entire dataset.
#
# Args:
#   data: A data frame that will be used to train the model.
#   recipe: A recipe object specifying preprocessing steps and formula.
#   tune_grid: A grid of hyperparameters to search over.
#   custom_folds: A rsample object specifying cross-validation folds.
#   control_grid: A control object for the resampling process.
#
# Returns:
#   The best ANN model with tuned hyperparameters trained on the entire dataset.

  # ANN Model Specification
  ann_spec <- mlp(hidden_units = tune(), penalty = tune(), mode = "classification") %>%
    set_engine("nnet")
  
  # Set up a workflow
  wf_ann <- workflow() %>% 
    add_recipe(recipe) %>% 
    add_model(ann_spec)
  
  # Tune the model with the custom cross-validation folds
  ann_results <- wf_ann %>% 
    tune_grid(resamples = custom_folds, grid = tune_grid, control = control_grid)
  
  # Get best parameters based on ROC AUC
  best_params <- ann_results %>% select_best(metric = "roc_auc")
  
  # Print best parameters to the console
  cat("\n Selected Hyper-parameters:\n")
  print(best_params)
  
  # Plot hyperparameter tuning results
  tuning_results <- ann_results %>% collect_metrics() %>% filter(.metric == "roc_auc")
  
  p <- ggplot(tuning_results, aes(x = hidden_units, y = mean, color = as.factor(penalty))) +
    geom_line(aes(group = penalty), linewidth = 1) +
    geom_point(color = "black", size = 1.25) +
    labs(subtitle = "Performance across tuning parameters",
         x = "Hidden Units",
         y = "ROC AUC", 
         color = "Penalty") +
    theme_bw() +
    theme(plot.title = element_text(hjust = 0.5, size = 16, face = "bold"),
          plot.subtitle = element_text(hjust = 0.5, size = 14))
  
  print(p)
  
  # Train the best model on the entire training data
  best_ann_model <- finalize_workflow(wf_ann, best_params) %>% fit(data = data)
  
  return(best_ann_model)
}
####


####
### Fit Gradient Boosted Machine (GBM) model without hyperparameter tuning ########################################################
fit_gbm <- function(data, recipe, custom_folds, control_grid, shrinkage, interaction_depth, n_minobsinnode, trees = 100) {
# Fits a Gradient Boosted Machine (GBM) model with either specified or default hyperparameters.
# Evaluates the model using ROC AUC and returns the best GBM model trained on the entire dataset.
#
# Args:
#   data: A data frame that will be used to train the model.
#   recipe: A recipe object specifying preprocessing steps and formula.
#   custom_folds: A rsample object specifying cross-validation folds.
#   control_grid: A control object for the resampling process.
#   shrinkage: A numeric value specifying the learning rate or shrinkage.
#   interaction_depth: An integer specifying the maximum depth of the trees.
#   n_minobsinnode: An integer specifying the minimum number of observations in the trees' terminal nodes.
#   trees: An optional integer specifying the number of trees to be grown in the GBM. Default is 100.
#
# Returns:
#   The best GBM model trained on the entire dataset.
  # GBM Model Specification
  gbm_spec <- boost_tree(
    mode = "classification",
    trees = trees,
    learn_rate =  shrinkage,
    tree_depth = interaction_depth,
    min_n =  n_minobsinnode
  ) %>%
    set_engine("gbm")
  
  # Set up a workflow
  wf <- workflow() %>%
    add_recipe(recipe) %>%
    add_model(gbm_spec)
  
  # Fit the model with the custom cross-validation folds
  gbm_results <- wf %>% 
    fit_resamples(resamples = custom_folds, control = control_grid)
  
  # Extract ROC AUC metrics
  roc_auc <- gbm_results %>% 
    collect_metrics() %>% 
    filter(.metric == "roc_auc") %>% 
    pull(mean)
  
  # Print ROC AUC to the console
  cat("\nROC AUC for GBM with trees =", trees, ":", round(roc_auc, 4), "\n")
  
  # Train the best model on the entire training data
  best_params <- gbm_results %>% select_best(metric = "roc_auc")
  best_gbm_model <- finalize_workflow(wf, best_params) %>% fit(data = data)
  
  return(best_gbm_model)
}
####


####
### Tune hyper-parameters and fit the best tuned Gradient Boosted Machine (GBM) model ###########################################
tune_and_fit_gbm <- function(data, recipe, tune_grid, custom_folds, control_grid, max_trees = 1500) {
 # Tunes hyperparameters for a Gradient Boosted Machine (GBM) model based on ROC AUC. 
# Plots the hyperparameter tuning results and returns the best GBM model trained on the entire dataset.
#
# Args:
#   data: A data frame that will be used to train the model.
#   recipe: A recipe object specifying preprocessing steps and formula.
#   tune_grid: A grid of hyperparameters to search over.
#   custom_folds: A rsample object specifying cross-validation folds.
#   control_grid: A control object for the resampling process.
#   max_trees: An optional integer specifying the maximum number of trees for tuning. Default is 1500.
#
# Returns:
#   The best GBM model with tuned hyperparameters trained on the entire dataset.
 
  # GBM Model Specification using xgboost
  gbm_spec <- boost_tree(
    mode = "classification",
    trees = tune(),           
    learn_rate =  tune(),     
    tree_depth = tune(),     
    min_n = tune()) %>%       
    set_engine("xgboost")
  
  # Set up a workflow
  wf <- workflow() %>%
    add_recipe(recipe) %>%
    add_model(gbm_spec)
  
  # Tune the model with the custom cross-validation folds
  gbm_results <- wf %>%
    tune_grid(resamples = custom_folds, grid = tune_grid, control = control_grid)
  
  # Get best parameters based on ROC AUC
  best_params <- gbm_results %>% select_best(metric = "roc_auc")
  
  # Print best parameters to the console
  cat("\n Selected Hyper-parameters:\n")
  print(best_params)
  
  # Plot hyperparameter tuning results
  tuning_results <- gbm_results %>% collect_metrics() %>% filter(.metric == "roc_auc")
  
  p <- ggplot(tuning_results, aes(x = as.factor(tree_depth), y = as.factor(min_n), fill = mean)) +
    geom_tile(color = "white", size = 0.5) +
    scale_fill_viridis_c(name = "ROC AUC", option = "D") +
    facet_wrap(~ learn_rate, labeller = label_both, ncol = 1) +
    labs(
      subtitle = "GBM Model Performance across Tuning Parameters",
      x = "Tree Depth",
      y = "Minimum n") +
    theme_bw() +
    theme(
      plot.title = element_text(hjust = 0.5, size = 16, face = "bold"),
      plot.subtitle = element_text(hjust = 0.5, size = 14),
      strip.text = element_text(size = 12)
    )
  
  print(p)
  # Train the best model on the entire training data
  best_gbm_model <- finalize_workflow(wf, best_params) %>% fit(data = data)
  
  return(best_gbm_model)
}
####

