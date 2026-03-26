# ============================================================
# Classify glider motion as ascent, descent, or neutral
#
# Goal:
# Use depth and time to estimate vertical speed, smooth that
# speed to reduce noise, and classify each observation as:
#   dir =  1  -> descent
#   dir = -1  -> ascent
#   dir =  0  -> neutral / uncertain
#
# Then assign a profile_id that increments whenever the
# cleaned direction changes.
#
# This is a derived classification:
# it is not read directly from a flight variable, but instead
# computed from the time derivative of depth.
#
# 2025???? - Written by ygomezro
# 20260324 - Revised by gcutter
# 
# ============================================================

rm(list = ls(all = TRUE))

# --- Options ---
VERBOSE       = FALSE 
DEBUGGING     = TRUE
WRITE_RDATA   = TRUE
WRITE_CSV     = FALSE
OPTIONS_PLOT  = TRUE 

# ---------- Libraries ----------
library(readr)
library(dplyr)
library(lubridate)
library(zoo)
library(ggplot2)


# --- Define Files --- 
# glider_file <- '/Users/ygomezro/Desktop/PhD Research Data/Processed Glider Data/NightBlue/ud_orris_NightBlue_bbp532_bbp700_raw1Hz_20260206.csv'

INPATH  <- "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue.RData"

OUTPATH_RDATA <- "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\glider_depth+direction.RData"

OUTPATH_CSV <- "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\glider_depth+direction.csv"

# Open RData file with df "glider_data" 
load( INPATH )

# --- Show vars/cols ---
for (n in names(glider_data))  cat(n, "\n")
# show as numbered list
data.frame(index = seq_along(glider_data), name = names(glider_data))

# --- var types 
sapply( glider_data , class)
dplyr::glimpse(glider_data)

# --- Select time and depth cols
# time_col  <- "g_utc_time"    
# depth_col <- "depth" 
depth_col <- "m_depth.m"
time_col <- "m_present_time.timestamp"

## 
# df <- glider_data %>%
#   mutate(
#     g_utc_time = as.POSIXct(time_col, format = "%d-%b-%Y %H:%M:%S", tz = "UTC") # for Strings
#   ) %>%
#   arrange(g_utc_time)
df <- glider_data %>%
  mutate(
    g_utc_time = as.POSIXct( m_present_time.timestamp , origin = "1970-01-01", tz = "UTC") 
  ) %>%
  arrange(g_utc_time)

# --- We now have dataframe 'df' with formatted time column 'g_utc_time'
if ( VERBOSE )
  print( df$g_utc_time ) 

data.frame(index = seq_along(df), name = names(df))


# ---------- Set parameters ----------
# min_depth_ok:
#   Ignore very shallow observations where the glider is near the
#   surface or pausing during a turnaround. These points are set to neutral.
#
# slope_thr_mps:
#   Threshold on smoothed vertical speed (m/s).
#   - if vertical direction is clearly positive, classify as descent
#   - if clearly negative, classify as ascent
#   - if close to zero, classify as neutral / uncertain
#
# smooth_win_sec:
#   Width of the smoothing window applied to vertical speed.
#   Here, ~2 minutes of data are used to reduce short-term noise.
#
# min_run_sec:
#   Minimum duration of an ascent/descent segment to keep.
#   Shorter runs are treated as noise or brief reversals and removed.
min_depth_ok   <- 3
slope_thr_mps  <- 0.01
smooth_win_sec <- 120
min_run_sec    <- 120

# ---------- Estimate sample rate ----------
# dt          : time spacing between consecutive samples (seconds)
# hz          : estimated sampling frequency (samples per second)
# win_pts     : smoothing window length in points, forced to be odd
# min_run_pts : minimum segment length in points
dt <- as.numeric(diff(df[[time_col]]), units = "secs")
hz <- median(1 / dt[dt > 0], na.rm = TRUE)

win_pts <- max(3, 2 * floor((smooth_win_sec * hz) / 2) + 1)
min_run_pts <- max(1, round(min_run_sec * hz))

# ---------- Compute vertical speed ----------
# Compute the first difference in depth and time:
#   dz = change in depth between consecutive observations
#   dt = change in time between consecutive observations
#   w  = vertical speed (direction is positive or negative) = dz / dt
#
# With depth increasing downward:
#   w > 0  means the glider is moving deeper -> descent
#   w < 0  means the glider is moving shallower  -> ascent
df <- df %>%
  mutate(
    dz = .data[[depth_col]] - lag(.data[[depth_col]]),
    dt = as.numeric(.data[[time_col]] - lag(.data[[time_col]]), units = "secs"),
    w  = dz / dt
  )

# ---------- Smooth vertical speed and assign raw direction ----------
# Smooth the vertical speed using a rolling median to reduce short,
# noisy fluctuations in dz/dt.
#
# Then classify each point into an initial direction:
#   dir_raw =  1  -> descent
#   dir_raw = -1  -> ascent
#   dir_raw =  0  -> neutral / uncertain
#
# Rules:
# - shallow points are forced to neutral
# - missing smoothed vertical speed is neutral
# - clearly positive vertical speed is descent
# - clearly negative vertical speed is ascent
# - values near zero are treated as neutral
df <- df %>%
  mutate(
    w_s = zoo::rollmedian(w, k = win_pts, fill = NA, align = "center"),
    dir_raw = case_when(
      .data[[depth_col]] < min_depth_ok ~ 0L,
      is.na(w_s)                        ~ 0L,
      w_s >  slope_thr_mps              ~  1L,
      w_s < -slope_thr_mps              ~ -1L,
      TRUE                              ~  0L
    )
  )


# ---------- Helper function: remove short ascent/descent runs ----------
# This function cleans the raw direction series by:
# 1. converting very short ascent/descent runs to neutral
# 2. filling those neutral gaps using neighboring values
#
# This helps remove brief reversals or noisy transitions that do
# not represent a real climb or dive segment.
merge_short_runs_clear <- function(x, minlen){
  r <- rle(x)
  
  # Step 1: mark short non-zero runs as neutral
  short_idx <- which(r$values != 0L & r$lengths < minlen)
  r$values[short_idx] <- 0L
  v <- inverse.rle(r)
  
  # Step 2: absorb neutral gaps into neighboring segments
  for(i in seq_along(v)){
    if (v[i] == 0L && i > 1L) v[i] <- v[i - 1L]
  }
  for(i in seq_along(v)){
    j <- length(v) - i + 1L
    if (v[j] == 0L && j < length(v)) v[j] <- v[j + 1L]
  }
  
  v
}

# Apply the cleaning step to the raw direction series
df$dir <- merge_short_runs_clear(df$dir_raw, min_run_pts)

# ---------- Assign profile IDs ----------
# A new profile_id is assigned whenever the cleaned direction changes.
# This means profile_id is a derived segment label based on ascent,
# descent, and neutral intervals.
chg <- c(FALSE, diff(df$dir) != 0L)
df$profile_id <- cumsum(ifelse(chg, 1L, 0L)) + 1L



# ---------- Add readable vertical-state labels ----------
df <- df %>%
  mutate(
    vertical_state = case_when(
      dir ==  1L ~ "descent",
      dir == -1L ~ "ascent",
      TRUE       ~ "neutral"
    )
  )

# seg <- df %>%
#   filter(
#     .data[[time_col]] >= as.POSIXct("2025-09-07 00:00:00", tz = "UTC"),
#     .data[[time_col]] <= as.POSIXct("2025-09-07 20:00:00", tz = "UTC")
#   )

seg <- df %>%
  filter(
    .data[[time_col]] >= as.POSIXct("2025-08-15 00:00:00", tz = "UTC"),
    .data[[time_col]] <= as.POSIXct("2025-09-05 23:00:00", tz = "UTC")
  )

print( seg )

dplyr::glimpse(seg)

head(seg$g_utc_time)
tail(seg$g_utc_time)

table(seg$vertical_state)

table(df$vertical_state)

# PLOT
if( OPTIONS_PLOT ){
ggplot(seg, aes(x = .data[[time_col]], y = .data[[depth_col]], color = factor(dir))) +
  geom_point(size = 0.6, alpha = 0.8) +
  scale_y_reverse() +
  scale_color_manual(
    values = c(`-1` = "red", `0` = "grey70", `1` = "blue"),
    breaks = c(-1, 0, 1),
    labels = c("Ascent", "Neutral", "Descent"),
    name   = "Direction"
  ) +
  labs(
    title = "Glider depth vs time (direction classified)",
    x = "Time (UTC)",
    y = "Depth (m)"
  ) +
  theme_minimal()
}

if( OPTIONS_PLOT ){
  ggplot(seg, aes(x = .data[["g_utc_time"]], y = .data[[depth_col]], color = factor(dir))) +
    geom_point(size = 0.6, alpha = 0.8) +
    scale_y_reverse() +
    scale_color_manual(
      values = c(`-1` = "red", `0` = "grey70", `1` = "cyan"),
      breaks = c(-1, 0, 1),
      labels = c("Ascent", "Neutral", "Descent"),
      name   = "Direction"
    ) +
    scale_x_datetime(date_labels = "%m-%d %H:%M") + 
    labs(
      title = "Glider depth vs time (direction classified)",
      x = "Time (UTC)",
      y = "Depth (m)"
    ) +
    theme_minimal()
}


## --- Write to file 
if( WRITE_CSV ) 
  write_csv(
    df, OUTPATH_CSV
  )

if( WRITE_RDATA )
  save_df(df, OUTPATH_RDATA)
  