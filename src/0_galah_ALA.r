## Prepare SDM data based on ALA occurrence records ###################################################################
# https://galah.ala.org.au/R/reference/index.html
{rm(list=ls()); options(scipen=999,digits=9) # clean up and set options
 setwd("C:/Users/bwbrook/Downloads/DL/DSDM")} # Set the working directory to the base directory
#######################################################################################################################

### Import specific package functions #################################################################################
{import::from("code/sdm_data_func.r", .all=T) # import custom functions into libs from source
#######################################################################################################################
  
### Custom functions and constants ####################################################################################
 galah_config(atlas="ALA", email="rahilamin10@gmail.com", caching=TRUE, verbose=TRUE)
  
 class <- "mammal" # select mammal or bird
  
 species_list_file = "input/species_list_tas.csv" # species occurrence records
 shape_file = "spatial/tasmania_coast.shp" # outline spatial coverage
  
 output_file = "output/mammal_ala_tasmania.csv" } # file to save final results
#######################################################################################################################

# Get the ALA data specified by the parameters above
ala_df <- get_ALA_data(class, first_year=NULL, species_list=read.csv(species_list_file), shp = st_read(shape_file))
#######################################################################################################################