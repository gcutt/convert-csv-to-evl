#

rm(list = ls(all = TRUE))


#
library(dplyr)
library(ggplot2)
library(plotly)


# 
OPTIONS_PLOT = TRUE
DEBUGGING    = FALSE

# First, load RData file with df, glider_data 
INPATH = "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+direction0.RData" 
load( INPATH )

# ## Examine data
# table( df$dir_num )
# 
# var1 = "directions"
# var2 = "dir_num"
# df %>%
#   count(!!sym(var1), !!sym(var2)) %>%
#   tidyr::pivot_wider(
#     names_from  = !!sym(var2),
#     values_from = n,
#     values_fill = 0
#   )
# 


if (OPTIONS_PLOT) {
  
  ## random sample but keep all dir_num==0
  # set.seed(123)
  # df_small <- bind_rows(
  #   df %>% filter(dir_num == 0),                 # keep all turning points
  #   df %>% filter(dir_num != 0) %>% slice_sample(prop = 0.05)   # sample 1% of others
  # )
  
  thin_factor <- 110   # keep every 50th non-zero row
  df_small <- df %>%
    mutate(row_id = row_number()) %>%
    filter( row_id %% thin_factor == 0) %>%
    select(-row_id )
  
  
  ## ONLY FOR DEBUGGING 
  if( DEBUGGING ){ 
    df0 = df
    df = df_small
  }
  
  ## Plot
  depth_col = "m_depth.m"
  
  # pgg <- ggplot( df , aes(x = g_utc_time, y = .data[[depth_col]])) +
  #   geom_point(aes(color = factor( dir )), size = 0.9, alpha = 0.8) +
  #   scale_y_reverse() +
  #   scale_color_manual(
  #     values = c(
  #       `-1` = "red",      # ascent
  #       `0`  = "grey70",   # neutral
  #       `1`  = "cyan"     # descent
  #     ),
  #     breaks = c(-1, 0, 1),
  #     labels = c("Ascent", "Neutral", "Descent"),
  #     name   = "Direction",
  #     na.value = "black"      # <-- this handles NA points
  #   ) +
  #   theme_minimal()

  
  options(viewer = NULL)
  
  plot_ly(
    df,
    x = ~as.numeric(g_utc_time),
    y = ~.data[[depth_col]],
    type = "scattergl",
    mode = "markers"
  )
  
  
  ## pitch data 
  #   convert from rad to deg 
  df <- df %>%
    mutate(m_pitch.deg = m_pitch.rad * 180 / pi) 
  
  ## pitch vs direction 
  pitch_stats <- df %>%
    group_by(dir_raw) %>%
    summarise(
      n      = n(),
      mean   = mean(   m_pitch.deg, na.rm = TRUE),
      median = median( m_pitch.deg, na.rm = TRUE),
      sd     = sd(     m_pitch.deg, na.rm = TRUE),
      min    = min(    m_pitch.deg, na.rm = TRUE),
      max    = max(    m_pitch.deg, na.rm = TRUE)
    )
  print( pitch_stats )
    
  pitch_stats_v <- df %>%
    group_by(vertical_state) %>%
    summarise(
      n      = n(),
      mean   = mean(   m_pitch.deg, na.rm = TRUE),
      median = median( m_pitch.deg, na.rm = TRUE),
      sd     = sd(     m_pitch.deg, na.rm = TRUE),
      min    = min(    m_pitch.deg, na.rm = TRUE),
      max    = max(    m_pitch.deg, na.rm = TRUE)
    )
  print( pitch_stats_v )
  
}






#-------------------------------------
## OPTIONS
doExportFulldf = FALSE 


#-------------------------------------
## Export list of vars to keep 
#-------------------------------------
if( doExportFulldf ){
  ## This writes everything to csv 
  # # write.csv(df, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\glider_data.csv", row.names=FALSE)
  
  # FULL VAR SET EXPORT NOT IMPLEMENTED 
  # select a subset of vars to export
  print( "FULL VAR SET EXPORT NOT IMPLEMENTED" )
  print( "select a subset of vars to export" )
  
} else {
  # Selected variables for export: 
  vars_to_keep <- c(
    "sci_water_pressure.bar",
    "c_ek80_on.sec",
    "salinity_drv.psu",
    "density_drv.kg/m3",
    "sci_rbrctd_temperature_00.degc"
  )
  
  # Also, keep all variables that begin with prefix 'm_' 
  m_vars <- grep("^m_", names(df), value = TRUE)
  
  df_sub <- df[, c(vars_to_keep, m_vars)]
  
  write.csv(df_sub, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+dir0-sub01.csv", row.names=FALSE)
}


#-------------------------------------
## Select vars to export 
#-------------------------------------
vars_to_keep <- c(
  "m_present_time.timestamp",
  "m_gps_lat.lat",
  "m_gps_lon.lon",
  "m_depth.m",
  "m_pitch.rad",
  "m_roll.rad",
  "sci_water_pressure.bar",
  "c_ek80_on.sec",
  "salinity_drv.psu",
  "density_drv.kg/m3",
  "sci_rbrctd_temperature_00.degc",
  "dir_raw",
  "dir",
  "vertical_state"
)

df_sub <- df[, vars_to_keep, drop = FALSE]

write.csv(df_sub, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+dir0-sub4ev.csv", row.names=FALSE)


# 
# plot(df$m_present_time.timestamp,
#      df$m_depth.m,
#      type = "l",
#      xlab = "Time",
#      ylab = "Depth (m)",
#      ylim = rev(range(df$m_depth.m)))

# 
# par(mar = c(4, 4, 2, 2))
# plot(df$m_present_time.timestamp,
#      df$m_depth.m,
#      type = "l")


