# ##-----------------------------------------
# ## EXPERIMENT 02  [NO]
# ##-----------------------------------------
# EXPERIMENTGC02 = TRUE
# 
# if( EXPERIMENTGC02 ){
#   
#   classify_z_turningpoints <- function(
#     z,
#     k = 7,              # smoothing window for z
#     thresh = 0.001      # slope threshold for raw inflection labeling
#   ) {
#     
#     n <- length(z)
#     
#     # --- 1. Smooth Z -----------------------------------------------------------
#     z_med <- zoo::rollmedian(z, k, fill = NA, align = "center")
#     
#     # --- 2. Derivative ---------------------------------------------------------
#     dz <- c(NA, diff(z_med))
#     
#     # --- 3. Raw classification (slope-based) ----------------------------------
#     cls_raw <- character(n)
#     cls_raw[dz >  thresh] <- "up"
#     cls_raw[dz < -thresh] <- "down"
#     cls_raw[abs(dz) <= thresh] <- "inflection"
#     cls_raw <- factor(cls_raw, levels = c("up", "down", "inflection"))
#     
#     # --- 4. Turning points (peaks & valleys) ----------------------------------
#     # local maxima: diff(sign(diff(z))) == -2
#     # local minima: diff(sign(diff(z))) ==  2
#     d1 <- diff(z_med)
#     d2 <- diff(sign(d1))
#     
#     peaks   <- which(d2 == -2) + 1
#     valleys <- which(d2 ==  2) + 1
#     
#     turning_points <- sort(c(peaks, valleys))
#     
#     # If no turning points found, return raw classification
#     if (length(turning_points) < 2) {
#       return(list(
#         z_med = z_med,
#         dz = dz,
#         turning_points = turning_points,
#         class_raw = cls_raw,
#         class_clean = cls_raw,
#         class_num = unname(c("up" = -1, "inflection" = 0, "down" = 1)[as.character(cls_raw)])
#       ))
#     }
#     
#     # --- 5. Enforce direction between turning points ---------------------------
#     cls_clean <- as.character(cls_raw)
#     
#     for (i in seq_len(length(turning_points) - 1)) {
#       s <- turning_points[i]
#       e <- turning_points[i + 1]
#       
#       # Determine direction by comparing Z at endpoints
#       dir <- if (z_med[e] > z_med[s]) "up" else "down"
#       
#       cls_clean[s:e] <- dir
#     }
#     
#     cls_clean <- factor(cls_clean, levels = c("up", "down", "inflection"))
#     
#     # --- 6. Numeric encoding ---------------------------------------------------
#     map <- c("up" = -1, "inflection" = 0, "down" = 1)
#     cls_num <- unname(map[as.character(cls_clean)])
#     
#     # --- 7. Return everything --------------------------------------------------
#     list(
#       z_med = z_med,
#       dz = dz,
#       turning_points = turning_points,
#       peaks = peaks,
#       valleys = valleys,
#       class_raw = cls_raw,
#       class_clean = cls_clean,
#       class_num = cls_num
#     )
#   }
#   
#   
#   ##
#   res <- classify_z_turningpoints(df[[depth_col]], k = 21)
#   
#   df$z_med     <- res$z_med
#   df$dz        <- res$dz
#   df$cls_raw   <- res$class_raw
#   df$cls_clean <- res$class_clean
#   df$cls_num   <- res$class_num
#   
#   ## 
#   turning_points <- res$turning_points
#   peaks          <- res$peaks
#   valleys        <- res$valleys
#   
#   table( df$cls_num )
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
#     # cls_num 
#     ggplot(subexper, aes(x = .data[["g_utc_time"]], y = .data[[depth_col]], color = factor( cls_num ))) +
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
#         title = "Glider depth vs time (classes: inflection)",
#         x = "Time (UTC)",
#         y = "Depth (m)"
#       ) +
#       theme_minimal()
#   }
#   
# }