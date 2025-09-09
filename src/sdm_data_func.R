#######################################################################################################################
### Functions: Retrieving, filtering and formatting occurrance data from online database (e.g. ALA, GBIF) for SDM   ###
#######################################################################################################################

#######################################################################################################################
# R functions available in this library: 
# create_final_spatial_df(): Create dataframe for all species, split into test and train data, with n_groups of folds
# create_spatial_folds(): Use spatial sampling to create spatial folds for cross-validation and test data
# fit_scaler(): Fit the scaler for continuous data variables (mean and standard deviation)
# get_ALA_data(): Retrieve, filter and spatially intersect occurrence data from the Atlas of Living Australia
# km_sample(): K-means clustering approach to thinning points
# merge_grid_activity(): Add grid activity data to points data
# plot_spatial_species_data(): Plots the train or test data for a given species on a map
# potential_absences_from_sites(): Select potential absence points based on observed sites without the target species
# process_presence_data(): Loads presence data, snaps presence points to the nearest grid point
# process_raster(): Process grid data to classify into low, medium and high human density
# separate_absences_from_presences(): Separate pseudoabsences from presences based on minimum separation distance
# species_presences(): Select presence points for a species
# thin_by_human_density(): Thin occurrences in areas of higher human density to match sampling intensity in lower areas
# thin_spatial_points(): Separate potential pseudoabsences from presences based on minimum separation distance
# transform_data(): Scale continuous vars based on training data, and one-hot-encode categorical  based on all levels
#######################################################################################################################

### Import specific CRAN package functions for use in custom functions ################################################
## All functions for the DSDM package are listed below in alphabetical order
import::here(across, all_of, anti_join, as_tibble, bind_cols, bind_rows, distinct, filter, group_by, left_join, n, 
             n_distinct, mutate, rename, sample_n, select, slice, summarise, ungroup,  
             .from = "dplyr")
import::here(atlas_occurrences, galah_call, galah_config, galah_filter, galah_identify, galah_polygon, galah_select, 
             .from = "galah")
import::here(distVincentySphere, .from = "geosphere")
import::here(aes, geom_line, geom_sf, ggplot, labs, scale_color_manual, scale_linetype_manual, theme_minimal, 
             .from = "ggplot2")
import::here(colorFactor, leaflet, addTiles, addCircleMarkers, .from = "leaflet")
import::here("%>%", .from = "magrittr")
import::here(map, map2, map2_dfc, .from = "purrr")
import::here(st_as_sf, st_convex_hull, st_coordinates, st_crs, st_distance, st_drop_geometry, st_geometry, 
             st_intersection, st_intersects, st_nearest_feature, st_read, st_set_geometry, st_simplify, st_union, 
             .from = "sf")
import::here(assessment, autoplot, spatial_clustering_cv, .from = "spatialsample")
import::here(terra_fac=as.factor, aggregate, as.polygons, classify, crop, freq, mask, project, rast, vect, 
             .from = "terra")
import::here(pivot_wider, .from = "tidyr")             
#######################################################################################################################

####
# Create a dataframe for all species, split into test and train data, with n_groups of train folds specified
create_final_spatial_df <- function(folds, n_fold, test_folds, n_groups, seed = 12345) {
  # Create a final dataset with test and train splits for spatial cross-validation
  #
  # Args:
  #   folds: A list of spatially clustered folds for cross-validation.
  #   n_fold: An integer specifying the number of folds used for cross-validation.
  #   test_folds: A vector of integers specifying the folds to use for testing.
  #   n_groups: An integer specifying the number of groups to use for stratified sampling.
  #   seed: An integer specifying the random seed for reproducibility.
  #
  # Returns:
  #   A data frame with test and train splits for spatial cross-validation.
  set.seed(seed + 1) # Set seed for reproducibility
    
  train_folds <- which(!1:n_fold %in% test_folds) # Determine train folds
  
  # Create the final dataset with test and train splits
  final_df <- map2(test_folds, seq_along(test_folds),
                   ~assessment(folds$splits[[.x]]) %>% mutate(fold = NA)) %>%
    bind_rows() %>% # Combine the folds across species
    mutate(type = "test") %>% # Add a column for the type of data
    bind_rows(map2(train_folds, 
                   sample(rep(1:n_groups, each=length(unique(train_folds))/n_groups)), 
                   ~assessment(folds$splits[[.x]]) %>% mutate(fold = .y)) %>% # Stratified sampling
                bind_rows() %>% # Combine the folds
                mutate(type = "train")) %>% # Add a column for the type of data
    mutate(lon = st_coordinates(geometry)[, 1], # Add columns for longitude and latitude
           lat = st_coordinates(geometry)[, 2]) %>%
    st_set_geometry(NULL) %>% # Remove geometry column
    select(lon, lat, species, pa, fold, type) # Reorder columns
  
  # Print a table of the final species breakdowns
  species_breakdown <- final_df %>%
    group_by(species, type, pa) %>% # Group by species, type and presence/absence
    summarise(count = n(), .groups = 'drop') %>% # Count the number of occurrences
    pivot_wider(names_from = pa, values_from = count, names_prefix = "pa_") # Pivot to wide format
  print(species_breakdown)
  
  return(final_df) # Return the final dataset
}
####

####
# Use spatial sampling to create spatial folds for cross-validation and test data
create_spatial_folds <- function(in_file, crs_ref, n_fold, seed=12345, plot_map=FALSE) {
  # Create spatially clustered folds for cross-validation
  #
  # Args:
  #   in_file: A character string specifying the path to the input CSV file.
  #   crs_ref: A character string specifying the CRS of the input data.
  #   n_fold: An integer specifying the number of folds to create.
  #   seed: An integer specifying the random seed for reproducibility.
  #   plot_map: A logical value indicating whether to plot the folds on a map.
  #
  # Returns:
  #   A list of spatially clustered folds for cross-validation.

  set.seed(seed) # Set the random seed for reproducibility
  data <- st_as_sf(read.csv(in_file), coords=c("lon","lat"), crs=crs_ref) # Read and convert data to sf
  folds <- spatial_clustering_cv(data, v=n_fold) # Create spatially clustered folds for cross-validation
  if(plot_map) print(autoplot(folds)) # Plot the folds on a map if plot_map is TRUE
  return(folds) # Return the folds data structure
}
####

####
# Fit the scaler for continuous data variables (mean and standard deviation)
fit_scaler <- function(data, cont_vars) {
  # Fit a scaler to continuous variables in the training data
  #
  # Args:
  #   data: A data frame with test and train splits for spatial cross-validation.
  #   cont_vars: A character vector specifying the names of the continuous variables to scale.
  #
  # Returns:
  #   A list with the mean and standard deviation of the continuous variables in the  data.
  
  # Calculate the mean and standard deviation of the continuous variables in the data
  scaler <- list(mean = colMeans(data[, cont_vars, drop=FALSE]), 
                 sd = apply(data[, cont_vars, drop=FALSE], 2, sd))
    
  return(scaler) # Return the scaler
}
####

####
# Retrieve, filter and spatially intersect occurrence data for a class of species from the Atlas of Living Australia db
get_ALA_data <- function(class="mammal", first_year=NULL, dTol=10000, species_list, shp, output=output_file) {
  # This function retrieves occurrence data for a given class of species from the Atlas of Living Australia (ALA) db
  # and returns a filtered and intersected sf object containing the occurrence data.
  # The function also writes the occurrence data to a CSV file if write_csv is set to TRUE.
  # 
  # Arguments:
  #   class: the class of species to retrieve occurrence data for (default is "mammal")
  #   first_date: the earliest date to retrieve occurrence data for (default is 1970)
  #   dTol: the distance tolerance for simplifying the shapefile (default is 10000)
  #   species_list: a list of species to retrieve occurrence data for (default is NULL)
  #   shp: the shapefile to intersect the occurrence data with
  #   write_csv: whether to write the occurrence data to a CSV file (default is TRUE)
  # 
  # Returns:
  #   sp_df: a filtered and intersected sf object containing the occurrence data

  # Validate inputs
  stopifnot(is.character(class)) # class must be a character vector
  stopifnot(is.list(species_list)) # species_list must be a list
  
  # Simplify shapefile and create convex hull
  shp <- st_simplify(st_union(shp), dTolerance = dTol) # Simplify shapefile to reduce processing time
  hull <- st_convex_hull(st_union(shp)) # Create convex hull of shapefile to reduce processing time
  
  # Set up output file name and species list
  filename <- paste0(class, "_ala.csv") # Set up output file name
  class_id <- ifelse(class == "mammal", "Mammalia", "Aves") # Set up class ID for ALA db
  sp_select <- species_list$Species.Name[which(species_list$Class == class_id)] # Select species from species list
  
  # Define a function to handle the conditional logic of whether to filter by date (and ignore any date=NA entries)
  check_date_filter <- function(data, year_filter) {
    if (!is.null(year_filter)) {
      return(data |> galah_filter(year >= year_filter))
    }
    return(data) # If year_filter is NULL, return the data unchanged
  }
  sp_occ <- map(sp_select, function(sp) { # Loop through each species in the species list
    cat("Downloading records for", sp, ":\n")
    galah_call() |> # Initialize galah
      galah_identify(sp) |> # Identify the species
      check_date_filter(first_year) |> # Filter by date
      galah_polygon(hull) |> # Filter by convex hull
      galah_select(decimalLongitude, decimalLatitude, class, family, genus, species, vernacularName, eventDate) |>
      atlas_occurrences() # Retrieve occurrence data from ALA db
  })
  sp_df <- sp_occ %>% bind_rows() # Combine the occurrence data into a single data frame
   
  # Rename relevant columns and filter out rows with missing or imprecise longitude or latitude values
  sp_df <- sp_df %>% 
    rename(longitude = decimalLongitude,
           latitude = decimalLatitude,
           common_name = vernacularName,
           date = eventDate) %>%  # Rename relevant columns
    filter(!is.na(longitude) & !is.na(latitude))%>% # Filter out rows with missing longitude or latitude values
    filter(!(longitude %% 1 == 0 | latitude %% 1 == 0)) # Filter out rows with no lon-lat precision
  
  # Convert the data frame to an sf object and intersect it with the shapefile, then convert to a df
  sp_df <- st_as_sf(sp_df, coords = c("longitude", "latitude"), crs = st_crs(shp)) %>%
    st_intersection(shp) %>% # Intersect with shapefile
    {
      coords <- st_coordinates(st_geometry(.))
      .$longitude <- coords[, 'X']
      .$latitude <- coords[, 'Y']
      st_drop_geometry(.) %>%
        as.data.frame()
    } %>%
    {sp_df[rownames(sp_df) %in% rownames(.),]} # Reorder rows to match original data frame
  
  # Write the occurrence data to a CSV file if write_csv is set to TRUE
  if(exists(output)) write.csv(sp_df, output, row.names=F)
  
  # Return the filtered and intersected sf object
  return(sp_df)
}
####

####
# K-means clustering approach to thinning points
km_sample <- function (fn_pres_sf, target_records) {
  # Sample a subset of spatial points using k-means clustering
  # 
  # Arguments:
  #   fn_pres_sf: A data frame containing spatial point data.
  #   target_records: The target number of records to sample.
  # 
  # Returns:
  #   A data frame containing a subset of the input spatial point data, with the number of
  #   records reduced to the target number using k-means clustering.
  
  # Find the index of the spatial point with the minimum distance to the cluster centroid
  find_min_distance_index <- function(cluster_id, dat) {
    subset_dat <- dat[dat$cluster == cluster_id, ] # Subset data to the current cluster
    min_index <- which.min(subset_dat$centroid_distance) # Find the index of the minimum distance
    return(subset_dat[min_index, ])
  }
  
  coords <- st_coordinates(fn_pres_sf) # Extract coordinates from spatial point data
  
  # If the number of records is greater than the target number, use k-means clustering to reduce the number of records
  if(dim(coords)[1] > target_records) {
    kmeans_result <- kmeans(coords, centers = min(dim(coords)[1], target_records)) # find target_records clusters
    fn_pres_sf$cluster <- kmeans_result$cluster # add cluster column to data frame
    fn_pres_sf$centroid_distance <- sapply(1:nrow(coords), function(i) { # calculate distance to cluster centroid
      distVincentySphere(cbind(coords[i, 1], coords[i, 2]), kmeans_result$centers[fn_pres_sf$cluster[i],])
    })
    
    # Find the spatial point with the minimum distance to the cluster centroid for each cluster
    representative_points <- do.call(rbind, lapply(1:target_records, find_min_distance_index, dat = fn_pres_sf))
    
    fn_pres_sf <- st_as_sf(representative_points[, !names(representative_points) %in% c("cluster","centroid_distance")])
    coords <- st_coordinates(fn_pres_sf) 
  }
  
  # Add longitude and latitude columns to the data frame and reorder columns
  fn_pres_sf$lon <- coords[,1]
  fn_pres_sf$lat <- coords[,2]
  fn_pres_sf <- fn_pres_sf[, c("lon","lat", setdiff(names(fn_pres_sf), c("lon","lat")))] # reorder columns
  
  return(fn_pres_sf) # Return subset of spatial point data
} 
####

####
# Add grid activity data to points data
merge_grid_activity <- function(points, grid, crs_ref) {
  # Merge grid activity data with spatial point data
  # 
  # Arguments:
  #   points: A data frame containing spatial point data.
  #   grid: A SpatialPolygonsDataFrame containing grid data with mean activity levels.
  #   crs_ref: The coordinate reference system (CRS) of the input data.
  # 
  # Returns:
  #   A data frame containing the input spatial point data with an additional column
  #   for the mean human activity level at each point.
  
  # Convert points and grid to spatial objects
  points_sf <- points %>% st_as_sf(coords = c("lon", "lat"), crs = crs_ref) # Convert points to spatial points
  grid_sf <- st_as_sf(as.polygons(grid), crs = crs_ref) # Convert grid to spatial polygons

  # Assign exact or nearest human activity level to each presence or absence coordinate
  points_sf$mean_activity <- grid_sf$mean_activity[st_nearest_feature(points_sf, grid_sf)]
  
  return(points_sf) # Return spatial point data with mean human activity level
}
####

####
# Plots the train or test data for a given species on a map
plot_spatial_species_data <- function(df, sp, fld=NA) {
  # Plot spatial data for a given species and fold
  #
  # Args:
  #   df: A data frame with test and train splits for spatial cross-validation.
  #   sp: A character string specifying the species to plot.
  #   fld: An integer or vector of integers specifying the fold(s) to plot for train data.
  #
  # Returns:
  #   A leaflet plot of the spatial data for the given species and fold.

  ty <- ifelse(is.na(fld), "test", "train") # Determine whether to plot test or train data
  
  # Filter the data frame to select the species and test/train data
  dat <- df %>%
    filter(species == sp, type == ty) %>% # select species and test/train data
    { if (ty == "train") filter(., fold %in% fld) else . } # select fold(s) if train data
  
  PrAbcolor <- colorFactor(c("red", "blue"), domain = dat$pa) # color palette for presence/absence
  
  leaflet_plot <- leaflet() %>% # plot the data on a map
    addTiles() %>%
    addCircleMarkers(data = dat, color = ~PrAbcolor(dat$pa), radius = 2, fillOpacity = 1)
  
  leaflet_plot # Display the leaflet plot
}
####

####
# Select potential absence points for a species based on observed sites without the target species
potential_absences_from_sites <- function(pres_all, pres, min_sp) {
  # Generate potential absence data from presence data
  # 
  # Arguments:
  #   pres_all: A data frame containing presence data for multiple species.
  #   pres: A data frame containing presence data for the target species.
  #   min_sp: The minimum number of species required at a site to be considered a potential absence.
  # 
  # Returns:
  #   A data frame containing potential absence data for the target species, with each point
  #   snapped to the nearest grid point and a "pa" column added with value 0.

  # Generate initial possible absence list based on distinct species but not target
  absences <- pres_all %>% # select all presence observations
    filter(species != pres$species[1]) %>% # select only non-target species observations
    anti_join(presences, by = c("lon", "lat")) %>% # remove sites that have target species
    group_by(lon, lat) %>% # group by grid cell
    filter(n_distinct(species) >= min_sp) %>% # only sites with min_species or more different species
    ungroup() %>% # ungroup data frame
    distinct(lon, lat, .keep_all = TRUE) %>% # select a single potential absence per grid cell
    mutate(species = pres$species[1], pa = 0) # change species name to target, add 'pa' column with 0
  
  return(absences) # Return potential absence data for the target species
}
####

####
# Loads presence data, snaps presence points to the nearest grid point
process_presence_data <- function(grid, pres, crs_ref) {
  # Loads presence data, snaps presence points to the nearest grid point
  # 
  # Arguments:
  #   grid: A file path to a CSV file containing grid point data.
  #   pres: A file path to a CSV file containing presence data.
  #   crs_ref: The coordinate reference system (CRS) of the input data.
  # 
  # Returns:
  #   A data frame containing the processed presence data, with each point
  #   snapped to the nearest grid point.

  # Load grid points and convert to spatial points
  grid_coords <- read.csv(grid)
  grid_sf <- st_as_sf(grid_coords, coords=c("lon","lat"), crs=crs_ref)
  
  # Load and process presence data
  presences_all <- read.csv(pres) %>% # Load presence data from CSV file
    select(longitude, latitude, species) %>% # Select relevant columns
    rename(lon = longitude, lat = latitude) %>% # Rename columns
    st_as_sf(coords = c("lon","lat"), crs=crs_ref) %>% # Convert to spatial points
    {
      nearest_indices <- st_nearest_feature(., grid_sf) # Find nearest grid point for each presence point
      mutate(., lon = grid_coords[nearest_indices, "lon"], # Snap presence point to nearest grid point
             lat = grid_coords[nearest_indices, "lat"])
    } %>% # Add snapped coordinates to data frame
    st_drop_geometry() %>% # Remove spatial information
    select(lon, lat, species) # Select relevant columns
  
  return(presences_all) # Return processed presence data
}
####

####
# Process grid data to classify into low, medium and high human density
process_raster <- function(grid, shape, human, low, high) {
  # Process grid data to classify into low, medium and high human density
  # 
  # Arguments:
  #   grid: A file path to a CSV file containing grid point data.
  #   shape: A file path to a shape file containing the study area boundary.
  #   human: A file path to a raster file containing human activity data.
  #   low: The threshold value for low human density.
  #   high: The threshold value for high human density.
  # 
  # Returns:
  #   A raster object containing the processed data, with values classified
  #   into "Low", "Medium", and "High" categories.

  # Load relevant spatial data
  grid_points <- read.csv(grid) # Load grid point data from CSV file
  shape_data <- vect(shape) # Load study area boundary from shape file
  
  # Convert human activity raster to terra raster and preprocess
  grid_subset <- rast(human) %>% # Load human activity data as a raster object
    {project(., st_crs(shape_data)$proj4string); .} %>% # Reproject raster to match study area boundary
    crop(shape_data) %>% # Crop raster to study area boundary
    mask(shape_data) %>% # Mask raster to study area boundary
    aggregate(10, fun='mean') %>% # Aggregate raster to reduce resolution
    {names(.) <- "mean_activity"; .} %>% # Rename raster layer
    classify(rcl = cbind(c(-Inf, low, high), # Classify raster into low, medium, and high density categories
                         c(low, high, Inf),
                         c(1, 2, 3))) %>% 
    terra_fac() # Convert raster to factor format
  
  # Assign new level names
  levels(grid_subset) <- data.frame(old = c(1, 2, 3), mean_activity = c("Low", "Medium", "High"))
  
  return(grid_subset) # Return processed raster object
}
####

####
# Separate potential pseudoabsences from presences based on minimum separation distance
separate_absences_from_presences <- function(abs, pres, dist_sep, crs_ref) {
  # Separate absence data from presence data
  # 
  # Arguments:
  #   abs: A data frame containing absence data.
  #   pres: A data frame containing presence data.
  #   dist_sep: The minimum distance (in km) between presence and absence points.
  #   crs_ref: The coordinate reference system (CRS) of the input data.
  # 
  # Returns:
  #   A data frame containing absence data separated from presence data, with each point
  #   snapped to the nearest grid point and a "pa" column added with value 0.
  
  pres_sf <- st_as_sf(pres, coords = c("lon", "lat"), crs = crs_ref) # Convert presence data to spatial points
  
  # Find nearest presence point for each absence point and calculate distance
  abs <- abs %>%
    st_as_sf(coords = c("lon", "lat"), crs = crs_ref) %>% # Convert absence data to spatial points
    {
      nearest_indices <- st_nearest_feature(., pres_sf) # Find nearest presence point for each absence point
      distances_to_presences_km <- round(as.numeric(st_distance(., pres_sf[nearest_indices, ], 
                                                                by_element=TRUE) / 1000), 1)
      mutate(st_set_geometry(., NULL),
             lon = st_coordinates(.)[, "X"], lat = st_coordinates(.)[, "Y"],
             distances_to_presences_km = distances_to_presences_km) # Add snapped coords and distance to data frame
    } %>%
    filter(distances_to_presences_km >= dist_sep) %>% # Filter out absences that are too close to presences
    select(lon, lat, species, pa) # Select relevant columns
  
  return(abs) # Return absence data separated from presence data
}
####

####
# Select presence points for a species
species_presences <- function(pres_all, sp) {
  # Extract presence data for a given species
  # 
  # Arguments:
  #   pres_all: A data frame containing presence data for multiple species.
  #   sp: A string containing the name of the species to extract presence data for.
  # 
  # Returns:
  #   A data frame containing presence data for the given species, with each point
  #   snapped to the nearest grid point and a "pa" column added with value 1.

  # Create list of grid presences for the target species
  presences <- pres_all %>%
    filter(species == sp) %>% # select only target species observations
    distinct(lon, lat, .keep_all = TRUE) %>% # select a single presence per grid cell
    mutate(pa = 1) %>% # add 'pa' column with 1
    as_tibble() # convert to tibble
  
  return(presences) # Return presence data for the given species
}
####

####
# Thin points data in areas of medium and high human density to match sampling intensity in low regions
thin_by_human_density <- function(points, grid, thinning_func) {
  # Thin spatial points based on human activity density
  # 
  # Arguments:
  #   points: A data frame containing spatial point data.
  #   grid: A SpatialPolygonsDataFrame containing grid data with mean activity levels.
  #   thinning_func: A function to use for thinning the spatial point data.
  # 
  # Returns:
  #   A data frame containing thinned spatial point data, with points separated by human
  #   activity density and thinned using the specified thinning function.

  # Calculate the number of grid cells for each activity level
  activity_n <- freq(grid$mean_activity)
  points <- sample_n(points, size=nrow(points), replace=FALSE) # shuffle the pres/abs
  
  # Separate points by activity class
  low_points <- points %>% filter(mean_activity == "Low")
  med_points <- points %>% filter(mean_activity == "Medium")
  high_points <- points %>% filter(mean_activity == "High")
  
  # Calculate the ratio for thinning the medium and high observations
  low_ratio <- nrow(low_points) / activity_n[activity_n$value == "Low", "count"]
  
  # Calculate the target number of points for each activity level
  low_target <- max(1, nrow(low_points)) # Low target is the baseline and same as number of Low observations
  med_target <- max(1, min(nrow(med_points), round(activity_n[activity_n$value == "Medium", "count"] * low_ratio)))
  high_target <- max(1, min(nrow(high_points), round(activity_n[activity_n$value == "High", "count"] * low_ratio)))
  
  # Apply thinning function
  low_thin <- thinning_func(low_points, low_target)
  med_thin <- thinning_func(med_points, med_target)
  high_thin <- thinning_func(high_points, high_target)
  
  # Combine thinned points
  thinned_points <- bind_rows(low_thin, med_thin, high_thin) %>% 
    select(lon, lat, species, pa) %>% # Select relevant columns
    sample_n(size = nrow(.), replace = FALSE) # Shuffle the pres/abs again to mix up the activity levels
  
  return(thinned_points) # Return thinned spatial point data
}
####

####
# Separate potential pseudoabsences from presences based on minimum separation distance
thin_spatial_points <- function(df, thin_sc=5, km_scale=111) {
  # Thin spatial points based on a minimum separation distance
  # 
  # Arguments:
  #   df: A data frame containing spatial point data.
  #   thin_sc: The minimum separation distance (in km) between points.
  #   km_scale: The scale factor to convert degrees to kilometers.
  # 
  # Returns:
  #   A data frame containing thinned spatial point data, with points separated by at least
  #   the minimum separation distance.
  
  # Calculate the rescaling factor for the minimum separation distance
  thinning_rescale <- thin_sc / km_scale # approximately in km, assuming 1 degree = 111 km (default)
  
  # Rescale the coordinates and group by grid cell
  df_thinned <- df %>% 
    mutate(across(c(lon, lat), ~thinning_rescale*round(.x/thinning_rescale)), row_order=1:nrow(df)) %>% 
    group_by(lon, lat) %>% # group by grid cell
    sample_n(1) %>% # choose a random row to keep from those that share a rescale grid cell
    ungroup()
  
  df <- df[df_thinned$row_order,] # select thinned points
  
  return(df) # Return thinned spatial point data
}
####

####
# Scale continuous variables based on training data, and one-hot-encode categorical layers based on all levels
transform_data <- function(data, cat_layers, cat_levels, cont_layers, scaler) {
  # Transform the input data by rescaling continuous variables and one-hot encoding categorical variables
  #
  # Args:
  #   data: A data frame with test and train splits for spatial cross-validation.
  #   cat_layers: A character vector specifying the names of the categorical variables.
  #   cat_levels: A list of character vectors specifying the levels of the categorical variables.
  #   cont_layers: A character vector specifying the names of the continuous variables.
  #   scaler: A list with the mean and standard deviation of the continuous variables in the training data.
  #
  # Returns:
  #   A data frame with rescaled continuous variables and one-hot encoded categorical variables.

  # Define a helper function to sort categorical levels
  sort_levels <- function(levels) {
    if (all(grepl("^\\d+$", levels))) {
      sort(as.integer(levels)) # If all levels are integers, convert and sort numerically
    } else {
      sort(levels)  # Otherwise, sort alphabetically
    }
  }

  # Select only the species data (if present in the data frame)  
  species_data <- data %>% select(-all_of(c(cat_layers, cont_layers)))
  
  # Split the data into continuous and categorical parts
  continuous_data <- data %>% select(all_of(cont_layers))
  
  # Apply the sort_levels function to each element of cat_levels
  cat_levels_sorted <- lapply(cat_levels, sort_levels)
  
  # Use the sorted levels in the transformation
  categorical_data <- data %>% select(all_of(cat_layers)) %>%
    map2_dfc(.f = ~ factor(., levels = cat_levels_sorted[[.y]]), .y = names(.))
  
  # Rescale the continuous variables
  continuous_data_rescaled <- continuous_data %>% 
    map2_dfc(., names(.), ~ (.x - scaler$mean[.y]) / scaler$sd[.y])
  
  # One-hot encode the categorical variables
  categorical_data_encoded <- categorical_data %>%
    model.matrix(~ . - 1, data = .) %>% as.data.frame()
  
  # Combine the rescaled continuous, one-hot encoded categorical, and other variables
  final_data <- bind_cols(species_data, continuous_data_rescaled, categorical_data_encoded)
  
  return(final_data) # Return the final transformed data
}
####

#######################################################################################################################