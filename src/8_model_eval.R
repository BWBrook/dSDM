### Species Distribution Models Evaluation ############################################################################
{rm(list=ls()); options(scipen=999,digits=9) # clean up and set options
 setwd("C:/Users/bwbrook/Downloads/DL/DSDM")} # Set the working directory

### Import specific package functions #################################################################################
import::from("code/DSDM_func.r", .all=T) # import custom functions into libs from source
#######################################################################################################################

### Custom functions and constants ####################################################################################
in_file = "results/rahil_sdm_output.csv"

### Main Program ######################################################################################################
{df <- read.csv(in_file)
  
 # Evaluate each model and bind the results together
 results <- df %>% process_model_csv()
  
 # Order the dataframe
 results <- results %>% arrange(species, model_type)
}

# Show results
message("Results:\n"); print(results,n=nrow(results)+1)
#######################################################################################################################
