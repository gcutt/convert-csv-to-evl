#

rm(list = ls(all = TRUE))

# First, open RData file with df "glider_data" 
load( "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue.RData" )

## This writes everything to csv 
# # write.csv(glider_data, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\RAW\\Glider\\Processed\\glider_data.csv", row.names=FALSE)

## OPTIONS
doExportFulldf = FALSE 


df = glider_data

#-------------------------------------
## Export list of vars to keep 
#-------------------------------------
if( doExportFulldf ){
} else {
  vars_to_keep <- c(
    "sci_water_pressure.bar",
    "c_ek80_on.sec",
    "salinity_drv.psu",
    "density_drv.kg/m3",
    "sci_rbrctd_temperature_00.degc"
  )
  
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
  "sci_rbrctd_temperature_00.degc"
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


