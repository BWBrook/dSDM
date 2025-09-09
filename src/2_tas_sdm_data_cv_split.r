### Camelot Camera-Trap data ##########################################################################################
{rm(list=ls()); options(scipen=999,digits=9) # clean up and set options
 setwd("C:/Users/bwbrook/Downloads/DL/DSDM")} # Set the working directory to the base directory
#######################################################################################################################

### Import specific package functions #################################################################################
{import::from("code/sdm_data_func.r", .all=T) # import custom functions into libs from source
#######################################################################################################################

### Custom functions and constants ####################################################################################
 tas_species <- c("Thylogale billardierii", "Notamacropus rufogriseus", "Macropus giganteus", # macropods
                  "Trichosurus vulpecula", "Pseudocheirus peregrinus", "Vombatus ursinus",    # other herbivores
                  "Sarcophilus harrisii",  "Dasyurus maculatus", "Dasyurus viverrinus")       # dasyurid predators
 n_fold = 50 # number of geographic clusters: will select 5 folds for held-out test data, and use other for train
 n_groups <- 5 # number of final cross-validation folds (cluster aggregations) for the training data
 seed = 12345 # allows for replication of splits
 crs_ref = 4326 # crs=4326 is WGS84 which is Google Maps polygon standard

 in_file = "output/tas_mammal_combined_pa_grid.csv" # input file with species and presence/absence data
 out_file = "output/tas_sdm_cvsplit.csv" } # output file with final cross-validation splits
#######################################################################################################################

### Main Program ######################################################################################################
folds <- create_spatial_folds(in_file, crs_ref, n_fold, seed, plot_map=TRUE) # slow to process

# select geographically disparate separation based on seed = 12345
autoplot(folds$splits[[1]]) # Example plot of a single rset split (for choosing geographically separated sub-regions)
test_folds = c(6, 10, 20, 38, 50) # Visually selected test splits: Here = 6 (S), 10 (NW), 12 (NE), 38 (C), 50 (SE) 

final_df <- create_final_spatial_df(folds, n_fold, test_folds, n_groups) # Create and display the stratified dataset

plot_species(final_df, sp = tas_species[9]) # Plot to evaluate a given test or train split: select species number

write.csv(final_df, out_file, row.names=F) # Save final cross-validation splits to file
#######################################################################################################################