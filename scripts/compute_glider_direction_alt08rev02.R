# ============================================================
#
# compute_glider_direction_alt08rev01.R
#
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
rm(list = ls())

# --- Options ---
VERBOSE        = FALSE 
DEBUGGING      =      TRUE
WRITE_RDATA    =      TRUE
WRITE_CSV      = FALSE
OPTIONS_PLOT   = FALSE 
OPTIONS_SUBSET =      TRUE 

# ---------- Libraries ----------
library(readr)
library(dplyr)
library(lubridate)
library(zoo)
library(ggplot2)


# --- Define Files --- 
# glider_file <- '/Users/ygomezro/Desktop/PhD Research Data/Processed Glider Data/NightBlue/ud_orris_NightBlue_bbp532_bbp700_raw1Hz_20260206.csv'

INPATH  <- "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue.RData"

OUTPATH_RDATA <- "D:\\Cutter\\0-PROJECTS\\UDEL\\DATA\\2025-NightBlue\\Glider\\Processed\\Ud_orris_Night-Blue+direction2.RData"

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

if( OPTIONS_SUBSET ){
  ## Subset data
  subexper <- df %>%
    filter(
      .data[[time_col]] >= as.POSIXct("2025-08-15 00:00:00", tz = "UTC"),
      .data[[time_col]] <= as.POSIXct("2025-09-07 01:00:00", tz = "UTC")
    )
  
  df0 = df 
  df = subexper
}

EXPERIMENTGC01 = TRUE

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

  # Build intervals between directions
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
# 1. classify inflection zones
df$directions <- classify_inflections( df[[depth_col]], win_pts )
table(df$directions)
map <- c("up" = 1, "inflection" = 0, "down" = -1)
df$dir_num <- unname(map[as.character(df$directions)])


## NEW NEW
# 2. detect neutral runs
# --- Identify contiguous neutral runs safely ---
is_neutral <- df$dir_num == 0

r <- rle(is_neutral)
ends   <- cumsum(r$lengths)
starts <- ends - r$lengths + 1

neutral_runs <- data.frame(
  start = starts[r$values],
  end   = ends[r$values]
)

# Remove any NA or invalid runs
neutral_runs <- neutral_runs[complete.cases(neutral_runs), ]
neutral_runs <- neutral_runs[neutral_runs$start <= neutral_runs$end, ]


# 3. detect turning points (inflect_bool, inflect_loc)
df$inflect_bool <- FALSE
df$inflect_loc  <- NA_character_

min_depth_for_tp <- -1

for (i in seq_len(nrow(neutral_runs))) {
  
  s <- neutral_runs$start[i]
  e <- neutral_runs$end[i]
  
  # Skip invalid
  if (s <= 1 || e > nrow(df)) next
  
  # Incoming slope
  left_idx <- max(1, s - 5):min(nrow(df), s + 5)
  left_slope <- mean(diff(df[[depth_col]][left_idx]), na.rm = TRUE)
  
  # Depth segment
  z_seg <- df[[depth_col]][s:e]
  
  # Skip surface-influenced neutral zones
  if (all(z_seg < min_depth_for_tp, na.rm = TRUE)) next
  
  # Determine top or bottom
  if (left_slope < 0) {
    # descending into neutral zone → valley (bottom)
    idx <- which.min(z_seg)
    loc <- "bot"
  } else {
    # ascending into neutral zone → peak (top)
    idx <- which.max(z_seg)
    loc <- "top"
  }
  
  tp_index <- s + idx - 1
  
  df$inflect_bool[tp_index] <- TRUE
  df$inflect_loc[tp_index]  <- loc
}


# 4. propagate direction between turning points
tp_idx <- which(df$inflect_bool)

# Need at least two turning points to define a segment
if (length(tp_idx) >= 2) {
  
  for (i in seq_len(length(tp_idx) - 1)) {
    
    s <- tp_idx[i]
    e <- tp_idx[i + 1]
    
    # Determine direction of this segment
    if (df[[depth_col]][e] > df[[depth_col]][s]) {
      seg_dir <- 1   # descent
    } else {
      seg_dir <- -1    # ascent
    }
    
    # Apply only to neutral points
    neutral_idx <- which(df$dir_num[s:e] == 0) + (s - 1)
    
    df$dir_num[neutral_idx] <- seg_dir
  }
}

# 5. recode overwritten inflection points
df$dir_num <- dplyr::case_when(
  df$directions == "inflection" & df$dir_num %in% c(-1, 1) ~ 2,
  TRUE ~ df$dir_num
)


if( OPTIONS_PLOT ){
  ## PLOT turning points 
  ggplot(df, aes(x = g_utc_time, y = .data[[depth_col]])) +
    geom_point(aes(color = factor(dir_num)), size = 0.6, alpha = 0.8) +
    geom_point(
      data = df %>% filter(inflect_bool),
      aes(x = g_utc_time, y = .data[[depth_col]]),
      color = "black", fill = "yellow", shape = 21, size = 2
    ) +
    scale_y_reverse() +
    theme_minimal()
}



if (OPTIONS_PLOT) {
  ggplot(df, aes(x = g_utc_time, y = .data[[depth_col]])) +
    geom_point(aes(color = factor(dir_num)), size = 0.9, alpha = 0.8) +
    geom_point(
      data = df %>% filter(inflect_bool),
      aes(x = g_utc_time, y = .data[[depth_col]]),
      color = "black", fill = "yellow", shape = 21, size = 2
    ) +
    scale_y_reverse() +
    scale_color_manual(
      values = c(
        `-1` = "black",      # ascent
        `0`  = "grey70",   # neutral
        `1`  = "cyan"     # descent
      ),
      breaks = c(-1, 0, 1),
      labels = c("Ascent", "Neutral", "Descent"),
      name   = "Direction",
      na.value = "red"      # <-- this handles NA points
    ) +
    theme_minimal()
}

if (OPTIONS_PLOT) {
  ggplot(df, aes(x = g_utc_time, y = .data[[depth_col]])) +
    geom_point(aes(color = factor(dir_num)), size = 0.9, alpha = 0.8) +
    geom_point(
      data = df %>% filter(inflect_bool),
      aes(x = g_utc_time, y = .data[[depth_col]]),
      color = "black", fill = "yellow", shape = 21, size = 2
    ) +
    scale_y_reverse() +
    scale_color_manual(
      values = c(
        `-1` = "black",      # ascent
        `0`  = "grey70",   # neutral
        `1`  = "cyan" ,    # descent
        `2`  = "red"   
      ),
      breaks = c(-1, 0, 1, 2),
      labels = c("Ascent", "Neutral", "Descent", "nearinflection"),
      name   = "Direction",
      na.value = "green"      # <-- this handles NA points
    ) +
    theme_minimal()
}



if (OPTIONS_PLOT) {
  ggplot(df, aes(x = g_utc_time, y = .data[[depth_col]])) +
    geom_point(aes(color = factor(dir_num)), size = 0.9, alpha = 0.8) +
    geom_point(
      data = df %>% filter(inflect_bool),
      aes(x = g_utc_time, y = .data[[depth_col]]),
      color = "black", fill = "yellow", shape = 21, size = 2
    ) +
    scale_y_reverse() +
    coord_cartesian(ylim = c(10, -1)) +
    scale_color_manual(
      values = c(
        `-1` = "black",      # ascent
        `0`  = "purple",   # neutral
        `1`  = "green3"     # descent
      ),
      breaks = c(-1, 0, 1),
      labels = c("Ascent", "Neutral", "Descent"),
      name   = "Direction",
      na.value = "red"      # <-- this handles NA points
    ) +
    theme_minimal()
}



#
# #-------------------------
## Original Plot
  if( FALSE ){
    # dir
    ggplot(df, aes(x = .data[["g_utc_time"]], y = .data[[depth_col]], color = factor(dir_num))) +
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


  