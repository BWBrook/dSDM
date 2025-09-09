### Combine camera-trap data with citizen science occurrences and filter offshore islands #############################
{rm(list=ls()); options(scipen=999,digits=9) # clean up and set options
 setwd("C:/Users/bwbrook/Downloads/DL/DSDM") } # Set the working directory to the base directory
#######################################################################################################################

### Import specific package functions #################################################################################
{import::from("code/sdm_data_func.r", .all=T) # import custom functions into libs from source
#######################################################################################################################

### Custom functions and constants ####################################################################################
 tas_species <- c("Thylogale billardierii", "Notamacropus rufogriseus", "Macropus giganteus", # macropods
                  "Trichosurus vulpecula", "Pseudocheirus peregrinus", "Vombatus ursinus",    # other herbivors
                  "Sarcophilus harrisii",  "Dasyurus maculatus", "Dasyurus viverrinus")       # dasyurid predators

 tascam_pa_file = "input/tascam_grid_pa.csv" # Tas-Cam: gridded camera-trap-derived presence / true-absence data
 citizen_science_pa_file = "output/tas_mammal_ala_pa.csv" # ALA citizen science data
 out_file = "output/tas_mammal_combined_pa_grid.csv" # output file for combined data

 island_polygons = "spatial/offshore_islands.kml" # polygon file outlining the Tasmanian offshore islands
 crs_ref = 4326 # crs=4326 is WGS84 which is Google Maps polygon standard
 thinning_separation = 3 } # km separation between presence-presence or absence-absence
#######################################################################################################################

### Main Program ######################################################################################################
{tascam_pa <- read.csv(tascam_pa_file) # read in Tas-Cam: gridded camera-trap-derived presence / true-absence data

 # Add the citizen-science presence-pseudoabsence data, preferencing the true PA Tas-Cam on duplicate grid cells
 tas_sdm_pa <- read.csv(citizen_science_pa_file) %>% # read in ALA citizen science data
  anti_join(tascam_pa, by=c("lon","lat")) %>% # exclude CS data on Tas-Cam gridpoints
  bind_rows(tascam_pa) %>% # create combined Tas-Cam and CS dataframes
  select(lon, lat, species, pa) } # order by lon-lat pairs and then species

##### Exclude absences from offshore islands ######
# Islands (King, Flinders, Hunter, Three-Hummock, Cape Barren, Clarke, Maria, Bruny)
{offshore_islands <- st_read(island_polygons) # KI|FI|CBI|CI|THI|HI|MI|BI
 tas_sdm <- list(sp=split(tas_species, cut(seq_along(tas_species), length(tas_species)))) # split species into 9 groups
 tas_sdm$is <- list( # These are the islands to exclude for the given species based on historical extirpations
  '1' = offshore_islands %>% filter(grepl("KI|CBI", Name)),                     # Tasmanian pademelon
  '2' = offshore_islands %>% filter(grepl("THI|HI", Name)),                     # Bennetts wallaby
  '3' = offshore_islands %>% filter(grepl("KI|FI|CBI|CI|HI|BI", Name)),         # Forester kangaroo
  '4' = offshore_islands %>% filter(grepl("CBI|CI|HI", Name)),                  # Brushtail possum
  '5' = offshore_islands %>% filter(grepl("CBI|CI|THI|HI|BI", Name)),           # Ringtail possum
  '6' = offshore_islands %>% filter(grepl("THI|HI|BI", Name)),                  # Bare-nosed wombat
  '7' = offshore_islands %>% filter(grepl("KI|FI|CBI|CI|THI|HI|BI", Name)),     # Tasmanian devil
  '8' = offshore_islands %>% filter(grepl("KI|FI|CBI|CI|THI|HI|MI|BI", Name)),  # Spotted-tail quoll
  '9' = offshore_islands %>% filter(grepl("KI|FI|CBI|CI|THI|HI|MI", Name))      # Eastern quoll
 )
 tas_sdm$fixed <- list() # initialise list to store fixed data for each species

 # Thinning on a per-species basis (thinning_separation is in ~km)
 thinning_rescale <- thinning_separation/111 } # approximately in km, given 1 degree = 111 km at Tas latitude

#######################################################################################################################
# Repeat this for each species (every species has its own island exclusion list [above]), do one-by-one to sanity check
{x <- 1 # species index (1-9)

 dat <- tas_sdm_pa %>% # filter out points on islands as specified by polygon island association
   filter(species == unlist(tas_sdm$sp[x])) %>% # select species x
   st_as_sf(coords=c("lon","lat"), crs=crs_ref) %>% # convert to spatial points
   # exclude points on specified islands (see above)
   filter(!sapply(st_intersects(., st_as_sf(tas_sdm$is[[x]],coords=c("lon","lat"),crs=crs_ref)), length)==1) %>% 
   mutate(
     lon = st_coordinates(.)[, "X"],
     lat = st_coordinates(.)[, "Y"]
   ) %>% # extract lon-lat coordinates
   st_set_geometry(NULL) %>%
   select(lon, lat, species, pa) # order by lon-lat pairs and then species

 # Thin to a specified separation distance (thinning_separation) between presence-presence or absence-absence
 dat_thinned <- dat %>% # select thinned presence points
   mutate(across(c(lon, lat), ~thinning_rescale*round(.x/thinning_rescale)), row_order=1:nrow(dat)) %>% 
   group_by(lon, lat) %>% # group by rescaled lon-lat pairs
   sample_n(1) %>% # choose a random row to keep  out of the ones that share a rescale gridcell
   ungroup() %>%
   left_join(dat, by=c("lon","lat","species","pa")) # join back to the original data to get the row_order
 dat <- dat[dat_thinned$row_order,] # select thinned presence points, snapped to the grid

 # Plot the results
 PrAbcolor = colorFactor(c("red", "blue"), domain = dat$pa)
 leaflet() %>% addTiles() %>% addCircleMarkers(data = dat, color= ~PrAbcolor(dat$pa), radius=2, fillOpacity=1) }
#######################################################################################################################
tas_sdm$fixed[[as.character(x)]] <- dat # store fixed data for species x

## Final compilation of all species from both camera-trap and citizen science data into a single dataframe
{tas_sdm_fixed <- bind_rows(tas_sdm$fixed) # combine all species into a single dataframe
 write.csv(tas_sdm_fixed, out_file, row.names=F) } # write to file
#######################################################################################################################
