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

OUTPATH_RDATA <- "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+direction.RData"

OUTPATH_CSV <- "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+direction.csv"


# --- Load RData file with df "glider_data" ---
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

sprintf("min_run_pts: %d | win_pts: %d", min_run_pts, win_pts)

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

sprintf("(w = dz/dt): %.3f", df$w )








##xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
## GC experiment 
##xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

EXPERIMENTGC01 = FALSE

if( EXPERIMENTGC01 ){
  
classify_inflections <- function(z,
                                 k = 21,          # rolling median window
                                 thresh = 0.001  # slope dead-zone
) {

  # Rolling median smoothing of Z (if not already smoothed)
  z_med <- zoo::rollmedian(z, k, fill = NA, align = "center")

  # First derivative of smoothed Z
  dz <- c(NA, diff(z_med))

  # Classification
  cls <- character(length(z))

  cls[dz >  thresh] <- "up"
  cls[dz < -thresh] <- "down"
  cls[abs(dz) <= thresh] <- "inflection"

  factor(cls, levels = c("up", "down", "inflection"))
}

enforce_majority_direction <- function(cls, inf_zones) {

  n <- length(cls)
  cls_new <- as.character(cls)

  # Add artificial boundaries at start and end
  bounds <- c(1, inf_zones$start, inf_zones$end, n)

  # Build intervals between inflections
  # Intervals are: (end_of_inf_i) : (start_of_inf_(i+1))
  for (i in seq_len(nrow(inf_zones) + 1)) {

    # Interval start
    if (i == 1) {
      s <- 1
    } else {
      s <- inf_zones$end[i - 1] + 1
    }

    # Interval end
    if (i <= nrow(inf_zones)) {
      e <- inf_zones$start[i] - 1
    } else {
      e <- n
    }

    if (s > e) next  # skip empty intervals

    # Extract segment
    seg <- cls[s:e]

    # Only consider up/down (ignore inflection)
    seg_ud <- seg[seg %in% c("up", "down")]

    if (length(seg_ud) == 0) next

    # Majority rule
    maj <- names(which.max(table(seg_ud)))

    # Overwrite
    cls_new[s:e] <- maj
  }

  factor(cls_new, levels = c("up", "down", "inflection"))
}


#-------------------------
## Get inflection ZONES
df$inflections <- classify_inflections( df[[depth_col]], win_pts )
table(df$inflections)
map <- c("up" = -1, "inflection" = 0, "down" = 1)
df$inflectnum <- unname(map[as.character(df$inflections)])



# # #-------------------------
# ## New class for narrower inflections
# find_turning_points <- function(z_med) {
#   n <- length(z_med)
#   # local maxima
#   peaks <- which(diff(sign(diff(z_med))) == -2) + 1
#   # local minima
#   valleys <- which(diff(sign(diff(z_med))) == 2) + 1
# 
#   list(peaks = peaks, valleys = valleys)
# }

#
# #-------------------------
## Subset data
subexper <- df %>%
  filter(
    .data[[time_col]] >= as.POSIXct("2025-08-15 00:00:00", tz = "UTC"),
    .data[[time_col]] <= as.POSIXct("2025-09-05 23:00:00", tz = "UTC")
  )

#
# #-------------------------
## Plot
  if( OPTIONS_PLOT ){
    # dir
    ggplot(subexper, aes(x = .data[["g_utc_time"]], y = .data[[depth_col]], color = factor(inflectnum))) +
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
        title = "Glider depth vs time (classes: turningpoints)",
        x = "Time (UTC)",
        y = "Depth (m)"
      ) +
      theme_minimal()
  }

} 





##-----------------------------------------
## EXPERIMENT 03  
##-----------------------------------------
# EXPERIMENTGC03 = TRUE
# 
# if( EXPERIMENTGC03 ){
# 
  # classify_inflections <- function(z,
  #                                  k = 21,          # rolling median window
  #                                  thresh = 0.001  # slope dead-zone
  # ) {
  # 
  #   # Rolling median smoothing of Z (if not already smoothed)
  #   z_med <- zoo::rollmedian(z, k, fill = NA, align = "center")
  # 
  #   # First derivative of smoothed Z
  #   dz <- c(NA, diff(z_med))
  # 
  #   # Classification
  #   cls <- character(length(z))
  # 
  #   cls[dz >  thresh] <- "up"
  #   cls[dz < -thresh] <- "down"
  #   cls[abs(dz) <= thresh] <- "inflection"
  # 
  #   factor(cls, levels = c("up", "down", "inflection"))
  # }
  # 
  # enforce_majority_direction <- function(cls, inf_zones) {
  # 
  #   n <- length(cls)
  #   cls_new <- as.character(cls)
  # 
  #   # Add artificial boundaries at start and end
  #   bounds <- c(1, inf_zones$start, inf_zones$end, n)
  # 
  #   # Build intervals between inflections
  #   # Intervals are: (end_of_inf_i) : (start_of_inf_(i+1))
  #   for (i in seq_len(nrow(inf_zones) + 1)) {
  # 
  #     # Interval start
  #     if (i == 1) {
  #       s <- 1
  #     } else {
  #       s <- inf_zones$end[i - 1] + 1
  #     }
  # 
  #     # Interval end
  #     if (i <= nrow(inf_zones)) {
  #       e <- inf_zones$start[i] - 1
  #     } else {
  #       e <- n
  #     }
  # 
  #     if (s > e) next  # skip empty intervals
  # 
  #     # Extract segment
  #     seg <- cls[s:e]
  # 
  #     # Only consider up/down (ignore inflection)
  #     seg_ud <- seg[seg %in% c("up", "down")]
  # 
  #     if (length(seg_ud) == 0) next
  # 
  #     # Majority rule
  #     maj <- names(which.max(table(seg_ud)))
  # 
  #     # Overwrite
  #     cls_new[s:e] <- maj
  #   }
  # 
  #   factor(cls_new, levels = c("up", "down", "inflection"))
  # }
  # 
  # refine_inflection_zones <- function(z_med, inf_zones) {
  # 
  #   turning_points <- integer(nrow(inf_zones))
  # 
  #   for (i in seq_len(nrow(inf_zones))) {
  #     s <- inf_zones$start[i]
  #     e <- inf_zones$end[i]
  # 
  #     z_seg <- z_med[s:e]
  # 
  #     # Determine whether this zone is a peak or valley
  #     # Look at slope entering the zone
  #     left_slope <- mean(diff(z_med[max(1, s-5):min(length(z_med), s+5)]), na.rm = TRUE)
  # 
  #     if (left_slope < 0) {
  #       # descending into zone → valley
  #       idx <- which.min(z_seg)
  #     } else {
  #       # ascending into zone → peak
  #       idx <- which.max(z_seg)
  #     }
  # 
  #     turning_points[i] <- s + idx - 1
  #   }
  # 
  #   turning_points
  # }
  # 
  # 
  # enforce_direction_between_points <- function(cls_raw, z_med, tp) {
  # 
  #   cls_new <- as.character(cls_raw)
  # 
  #   for (i in seq_len(length(tp) - 1)) {
  #     s <- tp[i]
  #     e <- tp[i + 1]
  # 
  #     dir <- if (z_med[e] > z_med[s]) "up" else "down"
  #     cls_new[s:e] <- dir
  #   }
  # 
  #   factor(cls_new, levels = c("up", "down", "inflection"))
  # }
  # 
  # 
  # cls_num_from_clean <- function(cls_clean) {
  #   map <- c("up" = -1, "inflection" = 0, "down" = 1)
  #   unname(map[as.character(cls_clean)])
  # }
#   
#   
#   #-------------------------
#   # ## Get inflections and classes
#   # df$inflections <- classify_inflections( df[[depth_col]], win_pts )
#   # table(df$inflections)
#   # map <- c("up" = -1, "inflection" = 0, "down" = 1)
#   # df$inflectnum <- unname(map[as.character(df$inflections)])
#   # 
#   # # Step 1: refine inflection zones → points
#   # tp <- refine_inflection_zones(res$z_med, res$inflection_zones)
#   # 
#   # # Step 2: enforce direction between turning points
#   # df$cls_clean <- enforce_direction_between_points(
#   #   cls_raw = res$class,
#   #   z_med   = res$z_med,
#   #   tp      = tp
#   # )
#   
#   
#   res <- classify_inflections(df[[depth_col]], win_pts)
#   
#   tp <- refine_inflection_zones(res$z_med, res$inflection_zones)
#   
#   df$cls_clean <- enforce_direction_between_points(
#     cls_raw = res$class,
#     z_med   = res$z_med,
#     tp      = tp
#   )
#   
#   # Step 3: numeric version
#   df$cls_num <- cls_num_from_clean(df$cls_clean)
#   
#   
#   ## Tally/Summarize 
#   table( df$cls_num )
#   
#   
#   #-------------------------
#   ## Subset data
#   subexper <- df %>%
#     filter(
#       .data[[time_col]] >= as.POSIXct("2025-08-15 00:00:00", tz = "UTC"),
#       .data[[time_col]] <= as.POSIXct("2025-09-05 23:00:00", tz = "UTC")
#     )
#   
#   # #-------------------------
#   ## Plot
#   if( OPTIONS_PLOT ){
#     ggplot(subexper, aes(x = .data[["g_utc_time"]],
#                          y = .data[[depth_col]],
#                          color = factor(cls_num))) +
#       geom_point(size = 0.6, alpha = 0.8) +
#       scale_y_reverse() +
#       scale_color_manual(
#         values = c(`-1` = "purple", `0` = "grey60", `1` = "green"),
#         breaks = c(-1, 0, 1),
#         labels = c("-1", "0", "1"),
#         name   = "Direction"
#       ) +
#       scale_x_datetime(date_labels = "%m-%d %H:%M") +
#       labs(
#         title = "Glider depth vs time (classes: inflection refined)",
#         x = "Time (UTC)",
#         y = "Depth (m)"
#       ) +
#       theme_minimal()
#   }
#   
# }



##-----------------------------------------
## EXPERIMENT 04 
##-----------------------------------------
EXPERIMENTGC04 = TRUE

if( EXPERIMENTGC04 ){

  ## 
  classify_inflections <- function(z,
                                   k = 21,
                                   thresh = 0.001) {
    
    # Smooth Z
    z_med <- zoo::rollmedian(z, k, fill = NA, align = "center")
    
    # Derivative
    dz <- c(NA, diff(z_med))
    
    # Classification
    cls <- character(length(z))
    cls[dz >  thresh] <- "up"
    cls[dz < -thresh] <- "down"
    cls[abs(dz) <= thresh] <- "inflection"
    cls <- factor(cls, levels = c("up", "down", "inflection"))
    
    # Inflection zones
    r <- rle(cls)
    ends <- cumsum(r$lengths)
    starts <- ends - r$lengths + 1
    idx <- which(r$values == "inflection")
    
    inf_zones <- data.frame(
      start = starts[idx],
      end   = ends[idx]
    )
    
    # Return everything
    list(
      class = cls,
      dz = dz,
      z_med = z_med,
      inflection_zones = inf_zones
    )
  }
  
  enforce_majority_direction <- function(cls, inf_zones) {
    
    n <- length(cls)
    cls_new <- as.character(cls)
    
    # Add artificial boundaries at start and end
    bounds <- c(1, inf_zones$start, inf_zones$end, n)
    
    # Build intervals between inflections
    # Intervals are: (end_of_inf_i) : (start_of_inf_(i+1))
    for (i in seq_len(nrow(inf_zones) + 1)) {
      
      # Interval start
      if (i == 1) {
        s <- 1
      } else {
        s <- inf_zones$end[i - 1] + 1
      }
      
      # Interval end
      if (i <= nrow(inf_zones)) {
        e <- inf_zones$start[i] - 1
      } else {
        e <- n
      }
      
      if (s > e) next  # skip empty intervals
      
      # Extract segment
      seg <- cls[s:e]
      
      # Only consider up/down (ignore inflection)
      seg_ud <- seg[seg %in% c("up", "down")]
      
      if (length(seg_ud) == 0) next
      
      # Majority rule
      maj <- names(which.max(table(seg_ud)))
      
      # Overwrite
      cls_new[s:e] <- maj
    }
    
    factor(cls_new, levels = c("up", "down", "inflection"))
  }
  
  refine_inflection_zones <- function(z_med, inf_zones) {
    
    turning_points <- integer(nrow(inf_zones))
    
    for (i in seq_len(nrow(inf_zones))) {
      s <- inf_zones$start[i]
      e <- inf_zones$end[i]
      
      z_seg <- z_med[s:e]
      
      # Determine whether this zone is a peak or valley
      # Look at slope entering the zone
      left_slope <- mean(diff(z_med[max(1, s-5):min(length(z_med), s+5)]), na.rm = TRUE)
      
      if (left_slope < 0) {
        # descending into zone → valley
        idx <- which.min(z_seg)
      } else {
        # ascending into zone → peak
        idx <- which.max(z_seg)
      }
      
      turning_points[i] <- s + idx - 1
    }
    
    turning_points
  }
  
  
  enforce_direction_between_points <- function(cls_raw, z_med, tp) {
    
    cls_new <- as.character(cls_raw)
    
    for (i in seq_len(length(tp) - 1)) {
      s <- tp[i]
      e <- tp[i + 1]
      
      dir <- if (z_med[e] > z_med[s]) "up" else "down"
      cls_new[s:e] <- dir
    }
    
    factor(cls_new, levels = c("up", "down", "inflection"))
  }
  
  
  cls_num_from_clean <- function(cls_clean) {
    map <- c("up" = -1, "inflection" = 0, "down" = 1)
    unname(map[as.character(cls_clean)])
  }
  
  
  ## NEW WRAPPER 
  process_inflections_and_plot <- function(df, depth_col, time_col, win_pts = 7) {
    
    # --- Step 1: run your existing classifier -------------------------------
    res <- classify_inflections(df[[depth_col]], win_pts)
    
    # --- Step 2: refine inflection zones into turning points ----------------
    tp <- refine_inflection_zones(res$z_med, res$inflection_zones)
    
    # --- Step 3: enforce direction between turning points -------------------
    cls_clean <- enforce_direction_between_points(
      cls_raw = res$class,
      z_med   = res$z_med,
      tp      = tp
    )
    
    # --- Step 4: numeric encoding -------------------------------------------
    cls_num <- cls_num_from_clean(cls_clean)
    
    # --- Step 5: attach results to df ---------------------------------------
    df$z_med     <- res$z_med
    df$dz        <- res$dz
    df$cls_raw   <- res$class
    df$cls_clean <- cls_clean
    df$cls_num   <- cls_num
    
    # --- Step 6: produce ggplot ---------------------------------------------
    p <- ggplot(df, aes(x = .data[[time_col]],
                        y = .data[[depth_col]],
                        color = factor(cls_num))) +
      geom_point(size = 0.6, alpha = 0.8) +
      scale_y_reverse() +
      scale_color_manual(
        values = c(`-1` = "purple", `0` = "grey60", `1` = "green"),
        breaks = c(-1, 0, 1),
        labels = c("-1", "0", "1"),
        name   = "Direction"
      ) +
      scale_x_datetime(date_labels = "%m-%d %H:%M") +
      labs(
        title = "Glider depth vs time (classes: inflection refined)",
        x = "Time (UTC)",
        y = "Depth (m)"
      ) +
      theme_minimal()
    
    # --- Step 7: return both data + plot ------------------------------------
    list(
      df = df,
      turning_points = tp,
      plot = p
    )
  }
  
  
  ## Subset data
  subexper <- df %>%
    filter(
      .data[[time_col]] >= as.POSIXct("2025-08-15 00:00:00", tz = "UTC"),
      .data[[time_col]] <= as.POSIXct("2025-09-05 23:00:00", tz = "UTC")
    )
  
  ## Call 
  time_col = "g_utc_time"
  process_inflections_and_plot( subexper , depth_col, time_col, win_pts = 7)
  

} # end EXPERIMENTGC04

  res <- classify_inflections( subexper[[depth_col]], win_pts)
  str(res)
  
  
##xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



# ---------- Smooth vertical speed and assign raw direction ----------
# Smooth the vertical speed using a rolling median to reduce short,
# noisy fluctuations in dz/dt.
#
# w_s is 
# 
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

# rle: Run Length Encoding, Compute the lengths and values of runs of equal values in a vector – or the reverse operation.

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
# df$dir <- merge_short_runs_clear(df$dir_raw, min_run_pts)
# sprintf( "min_run_pts: %d ", min_run_pts ) # 120

short_run_pts = ceiling( min_run_pts / 4 )
sprintf( "short_run_pts: %d ", short_run_pts )  # 30
df$dir <- merge_short_runs_clear(df$dir_raw, short_run_pts)



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
  # dir
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
    title = "Glider depth vs time (classes: dir)",
    x = "Time (UTC)",
    y = "Depth (m)"
  ) +
  theme_minimal()
}

if( OPTIONS_PLOT ){
  # dir
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
      title = "Glider depth vs time (classes: dir)",
      x = "Time (UTC)",
      y = "Depth (m)"
    ) +
    theme_minimal()
}

if( OPTIONS_PLOT ){
  # dir_raw
  ggplot(seg, aes(x = .data[["g_utc_time"]], y = .data[[depth_col]], color = factor(dir_raw))) +
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
      title = "Glider depth vs time (classes: dir_raw)",
      x = "Time (UTC)",
      y = "Depth (m)"
    ) +
    theme_minimal()
}


## --- checks --- 
table( seg$vertical_state )
table( df$vertical_state )
table( df$dir_raw)
table( df$dir )


## --- Write to file ---
if( WRITE_CSV ) 
  write_csv(
    df, OUTPATH_CSV
  )

if( WRITE_RDATA )
  save(df, file = OUTPATH_RDATA)





## DEBUGGING vertical_state 

table(df$vertical_state[df$dir_raw == 0])

subdebug <- df %>%
  filter(dir_raw == 0)

if( OPTIONS_PLOT ){
  ggplot(subdebug, aes(x = .data[["g_utc_time"]], y = .data[[depth_col]], color = factor(dir))) +
    geom_point(size = 0.9, alpha = 0.8) +
    scale_y_reverse() +
    scale_color_manual(
      values = c(`-1` = "red", `0` = "grey70", `1` = "#0099A8"),
      breaks = c(-1, 0, 1),
      labels = c("Ascent", "Neutral", "Descent"),
      name   = "Direction"
    ) +
    scale_x_datetime(date_labels = "%m-%d %H:%M") + 
    labs(
      title = "Glider depth vs time (classes: dir, where dir_raw == 0)",
      x = "Time (UTC)",
      y = "Depth (m)"
    ) +
    theme_minimal()
}



## Two-row plot 
subdebug2 <- subdebug %>%
  filter(dir %in% c(-1, 0, 1)) %>%        # keep only ascent/descent
  mutate(dir_panel = factor(dir,
                            levels = c(-1, 0, 1),
                            labels = c("Ascent (-1)", "Neutral (0)", "Descent (1)")))

if (OPTIONS_PLOT) {
  ggplot(subdebug2, aes(x = g_utc_time, y = .data[[depth_col]], color = factor(dir))) +
    geom_point(size = 1.0, alpha = 0.8) +
    scale_y_reverse() +
    scale_color_manual(
      values = c(`-1` = "red", `0` = "grey70", `1` = "#0099A8"),
      breaks = c(-1, 0, 1),
      labels = c("Ascent", "Neutral", "Descent"),
      name   = "Direction"
    ) +
    scale_x_datetime(date_labels = "%m-%d %H:%M") +
    facet_wrap(~ dir_panel, ncol = 1, scales = "free_y") +   # ← TWO ROWS
    labs(
      title = "subdebug2 Glider depth vs time (dir_raw == 0)",
      x = "Time (UTC)",
      y = "Depth (m)"
    ) +
    theme_minimal() +
    theme(
      panel.border = element_rect(color = "black", fill = NA, linewidth = 0.6)
    )
}


  