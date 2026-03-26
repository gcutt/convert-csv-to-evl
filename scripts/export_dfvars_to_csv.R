#

rm(list = ls(all = TRUE))

# First, open RData file with df "glider_data" 
load( "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+direction2.RData" )

## Examine data
table( df$dir_num )

var1 = "directions"
var2 = "dir_num"
df %>%
  count(!!sym(var1), !!sym(var2)) %>%
  tidyr::pivot_wider(
    names_from  = !!sym(var2),
    values_from = n,
    values_fill = 0
  )

var1 = "directions"
var2 = "inflect_loc"
df %>%
  count(!!sym(var1), !!sym(var2)) %>%
  tidyr::pivot_wider(
    names_from  = !!sym(var2),
    values_from = n,
    values_fill = 0
  )

## OPTIONS
doExportFulldf = FALSE 


df = glider_data

#-------------------------------------
## Export list of vars to keep 
#-------------------------------------
if( doExportFulldf ){
  ## This writes everything to csv 
  # # write.csv(df, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\RAW\\Glider\\Processed\\glider_data.csv", row.names=FALSE)
  
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
  
  write.csv(df_sub, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\RAW\\Glider\\Processed\\gliderdatasub01.csv", row.names=FALSE)
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
  "inflections",
  "inflectnum",
  "dir_raw",
  "dir",
  "vertical_state"
)

df_sub <- df[, vars_to_keep, drop = FALSE]

write.csv(df_sub, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\RAW\\Glider\\Processed\\gliderdepth_pr.csv", row.names=FALSE)


# 
# plot(df$m_present_time.timestamp,
#      df$m_depth.m,
#      type = "l",
#      xlab = "Time",
#      ylab = "Depth (m)",
#      ylim = rev(range(df$m_depth.m)))


par(mar = c(4, 4, 2, 2))
plot(df$m_present_time.timestamp,
     df$m_depth.m,
     type = "l")


