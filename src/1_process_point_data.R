## Process point-occurrence data downloaded from ALA ##################################################################
{rm(list=ls()); options(scipen=999,digits=9) # clean up and set options
 setwd("C:/Users/bwbrook/Downloads/DL/DSDM")} # Set the working directory to the base directory
#######################################################################################################################

### Import specific package functions #################################################################################
{import::from("code/sdm_data_func.r", .all=T) # import custom functions into libs from source
#######################################################################################################################

### Custom functions and constants ####################################################################################
 species <- c("Thylogale billardierii", "Notamacropus rufogriseus", "Macropus giganteus", # macropods
              "Trichosurus vulpecula", "Pseudocheirus peregrinus", "Vombatus ursinus",    # other herbivors
              "Sarcophilus harrisii",  "Dasyurus maculatus", "Dasyurus viverrinus")       # dasyurid predators

 min_species = 3 # minimum number of non-target species observed at a site to qualify as a potential pseudo-absence
 distance_separation = 5 # minimum distance in km separation between absence and nearest presence
 thinning_scale = 5 # amount of spatial thinning, roughly equivalent to average minimum km separation between points
 low_threshold = 15; high_threshold = 30 # Set low and high thresholds for human activity grids
 
 sp_occ = "output/mammal_ala_tasmania.csv" # species occurrence records
 output_file = "output/tas_mammal_ala_pa.csv" # file to save final results

 crs_ref = 4326 # WGS 84 as the standard
 grid_file = "spatial/tasmanian_gridpoints.csv" # regular grid points
 shape_file = "spatial/tasmania_coast.shp" # outline spatial coverage
 human_file = "spatial/human_footprint_tas.tif" } # human footprint (activity index)
#######################################################################################################################

### Main Program ######################################################################################################
# Process grid data to classify into low, medium and high human density based on human_file
{grid_subset <- process_raster(grid_file, shape_file, human_file, low_threshold, high_threshold)
 presences_all <- process_presence_data(grid_file, sp_occ, crs_ref) } # Process presence data and snap to grid

#######################################################################################################################
# Repeat the below for each species (reference by species index in the define species vector)
# Possible to automate, but suggest doing one-by-one, as each sp needs verifying, plotting etc. to sanity check results

# First step is to create the presences and potential pseudoabsences (before thinning) for a given species
{presences <- species_presences(presences_all, species[1]) # repeat for each # in species vector, e.g., 1 to 9

 absences <- presences_all %>% # get all potential absences for the species
   potential_absences_from_sites(presences, min_species) %>% # get all potential absence sites
   separate_absences_from_presences(presences, distance_separation, crs_ref) # filter by distance from presences

# Next thin the data based on specified minimum spatial separation and human density (correcting observation bias)
 set.seed(12345) # set seed to make sampling repeatable for each species
 sp_pa <- presences %>% # start with presences
   bind_rows(absences) %>% # combine presences and absences
   thin_spatial_points(thinning_scale) %>% # thin based on grid cells and spatial separation
   merge_grid_activity(grid_subset, crs_ref) %>% # add human density information for each point
   thin_by_human_density(grid_subset, km_sample) %>% # thin by human density (baseline = low intensity)
   st_drop_geometry() %>% # drop geometry column of spatial df (converted to lon/lat columns)
   data.frame() # convert to a dataframe

 # Finally, plot the results to sanity check the final PA dataset for the target species
 PrAbcolor = colorFactor(c("red", "blue"), domain = sp_pa$pa) # set colours for presence/absence
  leaflet() %>% addTiles() %>%  # plot the results
  addCircleMarkers(data = sp_pa, color= ~PrAbcolor(sp_pa$pa), radius=2, fillOpacity=1) } 

#######################################################################################################################
sp_all <- slice(sp_pa, 0) # initialise dataframe for grid-snapped data for all species, run once

# Accumulate dataframe and save to file after each species is processed
{sp_all <- bind_rows(sp_all, sp_pa) # accumulate dataframe
 write.csv(sp_all, output_file, row.names=F) } # save progress and create final dataframe
#######################################################################################################################
