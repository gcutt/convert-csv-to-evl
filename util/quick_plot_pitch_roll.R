#

rm(list = ls(all = TRUE))

# Open RData file with df "glider_data" 
load( "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+direction0.RData" )

## This writes everything to csv 
# # write.csv(glider_data, "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\RAW\\Glider\\Processed\\glider_data.csv", row.names=FALSE)

## OPTIONS
doExportFulldf = FALSE 


# df = glider_data
df <- glider_data[20001:nrow(df), ]

## LIST vars 
data.frame(index = seq_along(df), name = names(df))

# vars_to_keep <- c(
#   "m_present_time.timestamp",
#   "m_gps_lat.lat",
#   "m_gps_lon.lon",
#   "m_depth.m",
#   "m_pitch.rad",
#   "m_roll.rad",
#   "sci_water_pressure.bar",
#   "c_ek80_on.sec",
#   "salinity_drv.psu",
#   "density_drv.kg/m3",
#   "sci_rbrctd_temperature_00.degc"
# )

## plot pitch and roll 
# "m_present_time.timestamp","m_pitch.rad","m_roll.rad"
# convert from rad to deg 
# plot (2-row panels, top: pitch (deg), bot: roll (deg) vs timestamp

# Convert radians → degrees
df$pitch_deg <- df$m_pitch.rad * 180 / pi
df$roll_deg  <- df$m_roll.rad  * 180 / pi

# Convert timestamp to POSIXct if needed
if (!inherits(df$m_present_time.timestamp, "POSIXct")) {
  df$m_present_time.timestamp <- as.POSIXct(df$m_present_time.timestamp, tz = "UTC")
}


## STATS
# Compute summary stats
pitch_mean   <- mean(df$pitch_deg, na.rm = TRUE)
pitch_median <- median(df$pitch_deg, na.rm = TRUE)
pitch_sd     <- sd(df$pitch_deg, na.rm = TRUE)

roll_mean    <- mean(df$roll_deg, na.rm = TRUE)
roll_median  <- median(df$roll_deg, na.rm = TRUE)
roll_sd      <- sd(df$roll_deg, na.rm = TRUE)

# Print nicely
cat("\nPitch (deg):\n")
cat("  Mean:   ", round(pitch_mean, 3), "\n")
cat("  Median: ", round(pitch_median, 3), "\n")
cat("  Stdev:  ", round(pitch_sd, 3), "\n")

cat("\nRoll (deg):\n")
cat("  Mean:   ", round(roll_mean, 3), "\n")
cat("  Median: ", round(roll_median, 3), "\n")
cat("  Stdev:  ", round(roll_sd, 3), "\n")


## PLOT
# 2‑row panel layout
par(mfrow = c(2, 1), mar = c(4, 4, 2, 1))

# --- Pitch ---
plot(
  df$m_present_time.timestamp,
  df$pitch_deg,
  type = "l",
  col = "steelblue",
  xlab = "Timestamp",
  ylab = "Pitch (deg)",
  main = "Pitch vs Time"
)
grid()

# --- Roll ---
plot(
  df$m_present_time.timestamp,
  df$roll_deg,
  type = "l",
  col = "firebrick",
  xlab = "Timestamp",
  ylab = "Roll (deg)",
  main = "Roll vs Time"
)
grid()

