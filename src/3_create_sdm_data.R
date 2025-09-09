#######################################################################################################################
## Create SDM dataset by merging the species data with raster stack                                                  ##
#######################################################################################################################
{rm(list=ls()); options(scipen=999,digits=9) # clean up and set options
 setwd("C:/Users/bwbrook/Downloads/DL/DSDM")} # set the base working directory 
#######################################################################################################################

### Import functions and set constants ################################################################################
{import::from("code/sdm_data_func.r", .all=T) # import into libs from source

 crs_ref = 4326 # crs = 4326 is WGS84 which is Google Maps polygon standard

 in_file = "output/tas_sdm_cvsplit.csv" # path to species data CSV
 spatial_stack = "spatial/tas_stack.tif" # path to spatial stack TIF

 # Define the names of each layer in the TIF stack
 pred_names = c("annmeantemp", "meandiurnrange", "isothermality", "tempseason", "maxtempwarmmonth", 
                "mintempcoldmonth", "tempannrange", "meantempwetq", "meantempdryq", "meantempwarmq", 
                "meantempcoldq", "annprecip", "precipwetmonth", "precipdrymonth", "precipseason", 
                "precipwetq", "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness", 
                "soil_class", "dist_fw", "dist_road", "fire_freq", "fpar", "veg_mvs", "veg_mvg", 
                "landuse_primary", "landuse_secondary", "landuse_tertiary", "human_footprint")
 
 del_layers = c("landuse_primary", "landuse_tertiary", "veg_mvs", "fire_freq") # layers to delete from stack
 cat_layers = c("landuse_secondary","veg_mvg","soil_class") # specify the layers that contain categorical data
 
 save_test = "output/tas_sdm_test.csv" # path to save test data csv
 save_train = "output/tas_sdm_train.csv" # path to save train data csv
 save_map = "output/tas_sdm_map.csv" } # path to save the entire map, re-scaled to train data
#######################################################################################################################
{species <- read.csv(in_file) %>% # Read and convert species data to sf
   st_as_sf(coords=c("lon","lat"), crs=crs_ref)  # convert to spatial data frame

 # Load and select layers of raster stack
 stack <- spatial_stack %>%
   rast() %>%  # load the raster stack
   setNames(pred_names) %>%  # rename the layers
   `[[`(setdiff(names(.), del_layers)) %>%  # select only the needed layers  
   as.data.frame(xy = TRUE) %>% # convert the raster stack to a dataframe, include spatial coordinates  
   filter(complete.cases(.)) %>% # filter to only complete cases
   st_as_sf(coords = c("x","y"), crs=crs_ref) # convert to spatial data frame

 species <- species %>% 
   st_nearest_feature(stack) %>% # find the nearest raster cell to each species point
   slice(stack, .) %>% # extract the raster cell values at each species point
   st_set_geometry(NULL) %>% # remove the geometry column
   bind_cols(species, .) %>% # bind the raster cell values to the species data
   st_set_geometry(NULL) %>% 
   cbind(st_coordinates(st_geometry(species)), .) %>% # add the spatial coordinates to the species data
   rename(Lon = X, Lat = Y) # rename the spatial coordinates

 stack <- stack %>%
   st_coordinates() %>% # add the spatial coordinates to the raster stack
   as.data.frame() %>% # convert to a dataframe
   bind_cols(stack %>% st_set_geometry(NULL)) %>% # bind the raster cell values to the spatial coordinates
   rename(Lon = X, Lat = Y) } # rename the spatial coordinates

{train <- species %>% filter(type == "train") # split the data into train and test
 test <- species %>% filter(type == "test")

 cont_layers <- setdiff(pred_names, c(cat_layers, del_layers)) # select only the continuous layers
 cat_levels <- stack %>% select(all_of(cat_layers)) %>% lapply(., unique) # get the unique levels of each categorical
 train_scaler <- fit_scaler(train, cont_layers) } # fit the scaler to the train data (no leakage from test data)

{train <- transform_data(train, cat_layers, cat_levels, cont_layers, train_scaler) # transform the train data
 write.csv(train, save_train, row.names = FALSE) # save the train data

 test <- transform_data(test, cat_layers, cat_levels, cont_layers, train_scaler) # transform the test data
 write.csv(test, save_test, row.names = FALSE) # save the test data

 stack <- transform_data(stack, cat_layers, cat_levels, cont_layers, train_scaler) # transform the entire map
 write.csv(stack, save_map, row.names = FALSE) } # save the entire map
#######################################################################################################################