"""
im_projective_model.py

Loads an image and overlays two grids:
- Minimal model (constant GSD, green)
- Full projective model (perspective-correct, red)

World frame (oceanography):
    X = east-west horizontal axis
    Y = north-south horizontal axis
    Z = up/down (positive upward)

Camera frame (your hardware):
    z = up/down
    x,y = horizontal plane axes

Goal:
    Align camera so optical axis points downward toward seafloor.
    Then apply yaw/pitch/roll in intuitive oceanographic sense.
"""

import cv2
import numpy as np

# ----------------------------
# Parameters
# ----------------------------
image_path = "input.jpg"

H = 1.0  # camera height above seafloor [m]

# Lens FOVs [deg]
alpha_h_deg = 50.0
alpha_v_deg = 40.0

# Camera orientation (oceanographic convention)
yaw_deg   = 0.0     # rotate around world Z (heading)
pitch_deg = -70.0   # tilt forward/down toward seafloor
roll_deg  = 0.0     # rotate around optical axis

# World grid spacing [m]
grid_dx = 0.1
grid_dy = 0.1

# ----------------------------
# Load image
# ----------------------------
img = cv2.imread(image_path)
if img is None:
    raise FileNotFoundError(f"Could not load image: {image_path}")

Ny, Nx = img.shape[:2]

# ----------------------------
# Intrinsics from FOV
# ----------------------------
alpha_h = np.deg2rad(alpha_h_deg)
alpha_v = np.deg2rad(alpha_v_deg)

fx = Nx / (2.0 * np.tan(alpha_h / 2.0))
fy = Ny / (2.0 * np.tan(alpha_v / 2.0))
cx = Nx / 2.0
cy = Ny / 2.0

K = np.array([[fx,  0, cx],
              [ 0, fy, cy],
              [ 0,  0,  1]], float)

# ----------------------------
# Rotation utilities
# ----------------------------
def rot_x(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])

def rot_y(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c,0,s],[0,1,0],[-s,0,c]])

def rot_z(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])

yaw   = np.deg2rad(yaw_deg)
pitch = np.deg2rad(pitch_deg)
roll  = np.deg2rad(roll_deg)

# ----------------------------
# Camera orientation (corrected)
# ----------------------------
# Your camera frame:
#   z = up/down
#   x,y = horizontal plane
#
# We want:
#   camera optical axis = world -Z
#
# Alignment:
#   1) Rotate camera so its +z becomes world -Z
#   2) Rotate so its x,y align with world X,Y
#
# This alignment matrix was derived from your convention.
R_align = rot_x(np.pi/2) @ rot_y(np.pi/2) @ rot_x(np.pi)

# Apply yaw/pitch/roll in CAMERA frame (local axes)
R_local = rot_z(yaw) @ rot_x(pitch) @ rot_y(roll)

# Camera->world rotation
R_cw = R_align @ R_local

# World->camera
R_wc = R_cw.T

# Camera center in world coordinates
C_w = np.array([0.0, 0.0, H])

# ----------------------------
# Minimal model (constant GSD)
# ----------------------------
W  = 2.0 * H * np.tan(alpha_h / 2.0)
Hg = 2.0 * H * np.tan(alpha_v / 2.0)

GSD_x = W / Nx
GSD_y = Hg / Ny

def project_minimal(X, Y):
    u = cx + X / GSD_x
    v = cy - Y / GSD_y
    return u, v

# ----------------------------
# Full projective model
# ----------------------------
def project_full(X, Y, Z=0.0):
    Pw = np.array([X, Y, Z])
    Pc = R_wc @ (Pw - C_w)
    if Pc[2] <= 0:
        return None
    x = Pc[0] / Pc[2]
    y = Pc[1] / Pc[2]
    uv = K @ np.array([x, y, 1.0])
    return uv[0], uv[1]

# ----------------------------
# Build world grid
# ----------------------------
X_min, X_max = -3*W, 3*W
Y_min, Y_max = -3*Hg, 3*Hg

X_lines = np.arange(np.floor(X_min/grid_dx)*grid_dx,
                    np.ceil(X_max/grid_dx)*grid_dx + 1e-6,
                    grid_dx)
Y_lines = np.arange(np.floor(Y_min/grid_dy)*grid_dy,
                    np.ceil(Y_max/grid_dy)*grid_dy + 1e-6,
                    grid_dy)

overlay = img.copy()

# ----------------------------
# Draw minimal grid (GREEN)
# ----------------------------
for X in X_lines:
    u1,v1 = project_minimal(X, Y_min)
    u2,v2 = project_minimal(X, Y_max)
    cv2.line(overlay, (int(u1),int(v1)), (int(u2),int(v2)), (0,255,0), 1)

for Y in Y_lines:
    u1,v1 = project_minimal(X_min, Y)
    u2,v2 = project_minimal(X_max, Y)
    cv2.line(overlay, (int(u1),int(v1)), (int(u2),int(v2)), (0,255,0), 1)

# ----------------------------
# Draw full projective grid (RED)
# ----------------------------
for X in X_lines:
    pts = []
    for Y in np.linspace(Y_min, Y_max, 200):
        uv = project_full(X, Y)
        if uv is None: continue
        u,v = uv
        if 0 <= u < Nx and 0 <= v < Ny:
            pts.append((int(u),int(v)))
    for i in range(len(pts)-1):
        cv2.line(overlay, pts[i], pts[i+1], (0,0,255), 1)

for Y in Y_lines:
    pts = []
    for X in np.linspace(X_min, X_max, 200):
        uv = project_full(X, Y)
        if uv is None: continue
        u,v = uv
        if 0 <= u < Nx and 0 <= v < Ny:
            pts.append((int(u),int(v)))
    for i in range(len(pts)-1):
        cv2.line(overlay, pts[i], pts[i+1], (0,0,255), 1)

# ----------------------------
# Save result
# ----------------------------
out_path = "grid_overlay.png"
cv2.imwrite(out_path, overlay)
print(f"Saved overlay with grids to {out_path}")

# """
# im_projective_model.py
#
# Loads an image and overlays two grids:
# - Minimal model (constant GSD, green)
# - Full projective model (perspective-correct, red)
#
# World frame:  X forward, Y right, Z up
# Camera frame: x right, y down, z forward (OpenCV)
# Seafloor plane: Z = 0
# Camera center: (0, 0, H)
# """
#
# import cv2
# import numpy as np
#
# # ----------------------------
# # Parameters
# # ----------------------------
# image_path = "input.jpg"
#
# H = 1.5  # camera height above seafloor [m]
#
# # Lens FOVs [deg]
# alpha_h_deg = 40.0  # horizontal FOV
# alpha_v_deg = 30.0  # vertical FOV
#
# # Camera orientation (world-frame yaw/pitch/roll)
# yaw_deg   = 0.0     # rotate around world Z (heading)
# pitch_deg = -38.0   # rotate around world Y (tilt down)
# roll_deg  = 0.0     # rotate around world X (bank)
#
# # World grid spacing [m]
# grid_dx = 0.1
# grid_dy = 0.1
#
# # ----------------------------
# # Load image
# # ----------------------------
# img = cv2.imread(image_path)
# if img is None:
#     raise FileNotFoundError(f"Could not load image: {image_path}")
#
# Ny, Nx = img.shape[:2]
#
# # ----------------------------
# # Intrinsics from FOV
# # ----------------------------
# alpha_h = np.deg2rad(alpha_h_deg)
# alpha_v = np.deg2rad(alpha_v_deg)
#
# fx = Nx / (2.0 * np.tan(alpha_h / 2.0))
# fy = Ny / (2.0 * np.tan(alpha_v / 2.0))
# cx = Nx / 2.0
# cy = Ny / 2.0
#
# K = np.array([[fx,  0, cx],
#               [ 0, fy, cy],
#               [ 0,  0,  1]], dtype=float)
#
# # ----------------------------
# # Rotation utilities
# # ----------------------------
# def rot_x(theta):
#     c, s = np.cos(theta), np.sin(theta)
#     return np.array([[1, 0, 0],
#                      [0, c,-s],
#                      [0, s, c]])
#
# def rot_y(theta):
#     c, s = np.cos(theta), np.sin(theta)
#     return np.array([[ c, 0, s],
#                      [ 0, 1, 0],
#                      [-s, 0, c]])
#
# def rot_z(theta):
#     c, s = np.cos(theta), np.sin(theta)
#     return np.array([[c,-s, 0],
#                      [s, c, 0],
#                      [0, 0, 1]])
#
# yaw   = np.deg2rad(yaw_deg)
# pitch = np.deg2rad(pitch_deg)
# roll  = np.deg2rad(roll_deg)
#
# # ----------------------------
# # Camera orientation (corrected)
# # ----------------------------
# # World frame: X forward, Y right, Z up
# # Camera frame: x right, y down, z forward
#
# yaw   = np.deg2rad(yaw_deg)
# pitch = np.deg2rad(pitch_deg)
# roll  = np.deg2rad(roll_deg)
#
# # 1. Start with camera looking DOWN (world -Z)
# R_down = rot_x(np.pi)
#
# # 2. Apply yaw/pitch/roll in CAMERA frame (local axes)
# R_local = rot_z(roll) @ rot_y(pitch) @ rot_z(yaw)
#
# # 3. Combine: camera->world
# R_cw = R_down @ R_local
#
# # 4. World->camera
# R_wc = R_cw.T
#
# # # ----------------------------
# # # Camera orientation
# # # ----------------------------
# # # Step 1: camera looks DOWN (world -Z)
# # R_down = rot_x(np.pi)
# #
# # # Step 2: apply yaw/pitch/roll in WORLD frame
# # R_world = rot_z(yaw) @ rot_y(pitch) @ rot_x(roll)
# #
# # # Camera->world rotation
# # R_cw = R_down @ R_world
# #
# # # World->camera rotation
# # R_wc = R_cw.T
#
# # Camera center in world coordinates
# C_w = np.array([0.0, 0.0, H])
#
# # ----------------------------
# # Minimal model (constant GSD)
# # ----------------------------
# W = 2.0 * H * np.tan(alpha_h / 2.0)
# Hg = 2.0 * H * np.tan(alpha_v / 2.0)
#
# GSD_x = W / Nx
# GSD_y = Hg / Ny
#
# def project_minimal(X, Y):
#     u = cx + X / GSD_x
#     v = cy - Y / GSD_y
#     return u, v
#
# # ----------------------------
# # Full projective model
# # ----------------------------
# def project_full(X, Y, Z=0.0):
#     Pw = np.array([X, Y, Z])
#     Pc = R_wc @ (Pw - C_w)
#     if Pc[2] <= 0:
#         return None
#     x = Pc[0] / Pc[2]
#     y = Pc[1] / Pc[2]
#     uv = K @ np.array([x, y, 1.0])
#     return uv[0], uv[1]
#
# # ----------------------------
# # Build world grid
# # ----------------------------
# X_min, X_max = -3 * W, 3 * W
# Y_min, Y_max = -3 * Hg, 3 * Hg
#
# X_lines = np.arange(np.floor(X_min / grid_dx) * grid_dx,
#                     np.ceil(X_max / grid_dx) * grid_dx + 1e-6,
#                     grid_dx)
# Y_lines = np.arange(np.floor(Y_min / grid_dy) * grid_dy,
#                     np.ceil(Y_max / grid_dy) * grid_dy + 1e-6,
#                     grid_dy)
#
# overlay = img.copy()
#
# # ----------------------------
# # Draw minimal grid (GREEN)
# # ----------------------------
# for X in X_lines:
#     u1, v1 = project_minimal(X, Y_min)
#     u2, v2 = project_minimal(X, Y_max)
#     cv2.line(overlay, (int(u1), int(v1)), (int(u2), int(v2)), (0,255,0), 1)
#
# for Y in Y_lines:
#     u1, v1 = project_minimal(X_min, Y)
#     u2, v2 = project_minimal(X_max, Y)
#     cv2.line(overlay, (int(u1), int(v1)), (int(u2), int(v2)), (0,255,0), 1)
#
# # ----------------------------
# # Draw full projective grid (RED)
# # ----------------------------
# for X in X_lines:
#     pts = []
#     for Y in np.linspace(Y_min, Y_max, 200):
#         uv = project_full(X, Y)
#         if uv is None:
#             continue
#         u, v = uv
#         if 0 <= u < Nx and 0 <= v < Ny:
#             pts.append((int(u), int(v)))
#     for i in range(len(pts)-1):
#         cv2.line(overlay, pts[i], pts[i+1], (0,0,255), 1)
#
# for Y in Y_lines:
#     pts = []
#     for X in np.linspace(X_min, X_max, 200):
#         uv = project_full(X, Y)
#         if uv is None:
#             continue
#         u, v = uv
#         if 0 <= u < Nx and 0 <= v < Ny:
#             pts.append((int(u), int(v)))
#     for i in range(len(pts)-1):
#         cv2.line(overlay, pts[i], pts[i+1], (0,0,255), 1)
#
# # ----------------------------
# # Save result
# # ----------------------------
# out_path = "grid_overlay.png"
# cv2.imwrite(out_path, overlay)
# print(f"Saved overlay with grids to {out_path}")
#
#
# # """
# # im_projective_model.py
# #
# # - Loads an image
# # - Builds two seafloor projection models from FOV, height, and orientation
# # - Draws two overlaid grids (minimal model vs full projective model)
# #   corresponding to equal dx,dy on the seafloor plane Z=0.
# #
# # World frame:  X forward, Y right, Z up
# # Camera frame: x right, y down, z forward (OpenCV convention)
# # Seafloor plane: Z = 0
# # Camera center: (0, 0, H)
# # """
# #
# # import cv2
# # import numpy as np
# #
# # # ----------------------------
# # # Parameters (edit these)
# # # ----------------------------
# # image_path = "input.jpg"
# #
# # H = 1.5  # camera height above seafloor [m]
# #
# # # Lens FOVs [deg]
# # alpha_h_deg = 40.0  # horizontal FOV
# # alpha_v_deg = 30.0  # vertical FOV
# #
# # # Camera orientation (world frame: X forward, Y right, Z up)
# # # Camera frame: x right, y down, z forward
# # yaw_deg   = 0.0    # rotation around world Z (heading)
# # pitch_deg = 0.0  # rotation around camera Y (negative = tilt down)
# # roll_deg  = 35.0    # rotation around camera Z (roll)
# #
# # # World grid spacing on seafloor [m]
# # grid_dx = 0.1
# # grid_dy = 0.1
# #
# # # ----------------------------
# # # Load image
# # # ----------------------------
# # img = cv2.imread(image_path)
# # if img is None:
# #     raise FileNotFoundError(f"Could not load image: {image_path}")
# #
# # Ny, Nx = img.shape[:2]  # image height, width
# #
# # # ----------------------------
# # # Intrinsics from FOV
# # # ----------------------------
# # alpha_h = np.deg2rad(alpha_h_deg)
# # alpha_v = np.deg2rad(alpha_v_deg)
# #
# # fx = Nx / (2.0 * np.tan(alpha_h / 2.0))
# # fy = Ny / (2.0 * np.tan(alpha_v / 2.0))
# # cx = Nx / 2.0
# # cy = Ny / 2.0
# #
# # K = np.array([[fx,  0, cx],
# #               [ 0, fy, cy],
# #               [ 0,  0,  1]], dtype=float)
# #
# # # ----------------------------
# # # Extrinsics: rotation world->camera
# # # ----------------------------
# # # World frame: X forward, Y right, Z up
# # # Camera frame: x right, y down, z forward
# # # We want camera +z to point DOWN toward the seafloor (world -Z).
# #
# # def rot_x(theta):
# #     c, s = np.cos(theta), np.sin(theta)
# #     return np.array([[1, 0, 0],
# #                      [0, c,-s],
# #                      [0, s, c]])
# #
# # def rot_y(theta):
# #     c, s = np.cos(theta), np.sin(theta)
# #     return np.array([[ c, 0, s],
# #                      [ 0, 1, 0],
# #                      [-s, 0, c]])
# #
# # def rot_z(theta):
# #     c, s = np.cos(theta), np.sin(theta)
# #     return np.array([[c,-s, 0],
# #                      [s, c, 0],
# #                      [0, 0, 1]])
# #
# # yaw   = np.deg2rad(yaw_deg)
# # pitch = np.deg2rad(pitch_deg)
# # roll  = np.deg2rad(roll_deg)
# #
# # # Start with camera looking DOWN (world -Z)
# # R_down = rot_x(np.pi)  # rotate 180° around X to flip +Z downward
# #
# # # Camera->world rotation: apply yaw, pitch, roll in camera frame
# # R_cw = R_down @ rot_z(yaw) @ rot_y(pitch) @ rot_x(roll)
# #
# # # World->camera rotation
# # R_wc = R_cw.T
# #
# # # Camera center in world coordinates
# # C_w = np.array([0.0, 0.0, H])
# #
# # # ----------------------------
# # # Minimal model: constant GSD at seafloor
# # # ----------------------------
# # # Approximate ground footprint at seafloor for nadir view
# # W = 2.0 * H * np.tan(alpha_h / 2.0)  # width [m]
# # Hg = 2.0 * H * np.tan(alpha_v / 2.0) # height [m]
# #
# # GSD_x = W / Nx  # m per pixel (horizontal)
# # GSD_y = Hg / Ny # m per pixel (vertical)
# #
# # def project_minimal(X, Y):
# #     """Map world (X,Y,0) to image (u,v) with minimal model."""
# #     u = cx + X / GSD_x
# #     v = cy - Y / GSD_y  # minus because image y increases downward
# #     return u, v
# #
# # # ----------------------------
# # # Full projective model: world->image
# # # ----------------------------
# # def project_full(X, Y, Z=0.0):
# #     """Project world point (X,Y,Z) to image (u,v) using full pinhole model."""
# #     Pw = np.array([X, Y, Z])
# #     Pc = R_wc @ (Pw - C_w)  # world->camera
# #     if Pc[2] <= 0:
# #         return None  # behind camera
# #     x = Pc[0] / Pc[2]
# #     y = Pc[1] / Pc[2]
# #     uv = K @ np.array([x, y, 1.0])
# #     u, v = uv[0], uv[1]
# #     return u, v
# #
# # # ----------------------------
# # # Build world grid on seafloor
# # # ----------------------------
# # # Expand extents to ensure tilted footprint is covered
# # X_min, X_max = -3 * W, 3 * W
# # Y_min, Y_max = -3 * Hg, 3 * Hg
# #
# # X_lines = np.arange(np.floor(X_min / grid_dx) * grid_dx,
# #                     np.ceil(X_max / grid_dx) * grid_dx + 1e-6,
# #                     grid_dx)
# # Y_lines = np.arange(np.floor(Y_min / grid_dy) * grid_dy,
# #                     np.ceil(Y_max / grid_dy) * grid_dy + 1e-6,
# #                     grid_dy)
# #
# # overlay = img.copy()
# #
# # # ----------------------------
# # # Draw minimal model grid (GREEN)
# # # ----------------------------
# # color_min = (0, 255, 0)  # BGR
# #
# # # Vertical lines (constant X)
# # for X in X_lines:
# #     u1, v1 = project_minimal(X, Y_min)
# #     u2, v2 = project_minimal(X, Y_max)
# #     p1 = (int(round(u1)), int(round(v1)))
# #     p2 = (int(round(u2)), int(round(v2)))
# #     if (0 <= p1[0] < Nx and 0 <= p1[1] < Ny) or (0 <= p2[0] < Nx and 0 <= p2[1] < Ny):
# #         cv2.line(overlay, p1, p2, color_min, 1, cv2.LINE_AA)
# #
# # # Horizontal lines (constant Y)
# # for Y in Y_lines:
# #     u1, v1 = project_minimal(X_min, Y)
# #     u2, v2 = project_minimal(X_max, Y)
# #     p1 = (int(round(u1)), int(round(v1)))
# #     p2 = (int(round(u2)), int(round(v2)))
# #     if (0 <= p1[0] < Nx and 0 <= p1[1] < Ny) or (0 <= p2[0] < Nx and 0 <= p2[1] < Ny):
# #         cv2.line(overlay, p1, p2, color_min, 1, cv2.LINE_AA)
# #
# # # ----------------------------
# # # Draw full projective model grid (RED)
# # # ----------------------------
# # color_full = (0, 0, 255)  # BGR
# #
# # # Vertical lines (constant X)
# # for X in X_lines:
# #     pts = []
# #     for Y in np.linspace(Y_min, Y_max, 200):
# #         uv = project_full(X, Y, 0.0)
# #         if uv is None:
# #             continue
# #         u, v = uv
# #         if 0 <= u < Nx and 0 <= v < Ny:
# #             pts.append((int(round(u)), int(round(v))))
# #     if len(pts) >= 2:
# #         for i in range(len(pts) - 1):
# #             cv2.line(overlay, pts[i], pts[i+1], color_full, 1, cv2.LINE_AA)
# #
# # # Horizontal lines (constant Y)
# # for Y in Y_lines:
# #     pts = []
# #     for X in np.linspace(X_min, X_max, 200):
# #         uv = project_full(X, Y, 0.0)
# #         if uv is None:
# #             continue
# #         u, v = uv
# #         if 0 <= u < Nx and 0 <= v < Ny:
# #             pts.append((int(round(u)), int(round(v))))
# #     if len(pts) >= 2:
# #         for i in range(len(pts) - 1):
# #             cv2.line(overlay, pts[i], pts[i+1], color_full, 1, cv2.LINE_AA)
# #
# # # ----------------------------
# # # Save / show result
# # # ----------------------------
# # out_path = "grid_overlay.png"
# # cv2.imwrite(out_path, overlay)
# # print(f"Saved overlay with grids to {out_path}")
# #
# #
# #
# # # """
# # # # im_projective_model.py
# # # # loads an image
# # # # builds two seafloor projection models from FOV, height, and orientation
# # # # draws two overlaid grids (minimal model vs full projective model) corresponding to equal dx,dy on the seafloor plane
# # # # Minimal model: assumes nadir‑ish view, constant GSD over the footprint
# # # # Full model: per‑pixel projective mapping via ray–plane / world→image projection
# # # """
# # #
# # # import cv2
# # # import numpy as np
# # #
# # # # ----------------------------
# # # # Parameters (edit these)
# # # # ----------------------------
# # # image_path = "input.jpg"
# # #
# # # H = 1.5  # camera height above seafloor [m]
# # #
# # # # Lens FOVs [deg]
# # # alpha_h_deg = 40.0  # horizontal FOV
# # # alpha_v_deg = 30.0  # vertical FOV
# # #
# # # # Camera orientation (world frame: X forward, Y right, Z up)
# # # # Camera frame: x right, y down, z forward
# # # yaw_deg   = 0.0   # rotation around Z (heading)
# # # pitch_deg = 25.0  # rotation around Y (tilt down)
# # # roll_deg  = 0.0   # rotation around X (roll)
# # #
# # # # World grid spacing on seafloor [m]
# # # grid_dx = 0.1
# # # grid_dy = 0.1
# # #
# # # # ----------------------------
# # # # Load image
# # # # ----------------------------
# # # img = cv2.imread(image_path)
# # # if img is None:
# # #     raise FileNotFoundError(f"Could not load image: {image_path}")
# # #
# # # Ny, Nx = img.shape[:2]  # image height, width
# # #
# # # # ----------------------------
# # # # Intrinsics from FOV
# # # # ----------------------------
# # # alpha_h = np.deg2rad(alpha_h_deg)
# # # alpha_v = np.deg2rad(alpha_v_deg)
# # #
# # # fx = Nx / (2.0 * np.tan(alpha_h / 2.0))
# # # fy = Ny / (2.0 * np.tan(alpha_v / 2.0))
# # # cx = Nx / 2.0
# # # cy = Ny / 2.0
# # #
# # # K = np.array([[fx,  0, cx],
# # #               [ 0, fy, cy],
# # #               [ 0,  0,  1]], dtype=float)
# # #
# # # # ----------------------------
# # # # Extrinsics: rotation from world to camera
# # # # ----------------------------
# # # def rot_x(theta):
# # #     c, s = np.cos(theta), np.sin(theta)
# # #     return np.array([[1, 0, 0],
# # #                      [0, c,-s],
# # #                      [0, s, c]])
# # #
# # # def rot_y(theta):
# # #     c, s = np.cos(theta), np.sin(theta)
# # #     return np.array([[ c, 0, s],
# # #                      [ 0, 1, 0],
# # #                      [-s, 0, c]])
# # #
# # # def rot_z(theta):
# # #     c, s = np.cos(theta), np.sin(theta)
# # #     return np.array([[c,-s, 0],
# # #                      [s, c, 0],
# # #                      [0, 0, 1]])
# # #
# # # yaw   = np.deg2rad(yaw_deg)
# # # pitch = np.deg2rad(pitch_deg)
# # # roll  = np.deg2rad(roll_deg)
# # #
# # # # World->camera rotation (R_wc): apply yaw, pitch, roll in Z-Y-X order
# # # # R_wc = rot_x(roll) @ rot_y(pitch) @ rot_z(yaw)
# # #
# # # R_cw = rot_x(roll) @ rot_y(pitch) @ rot_z(yaw)   # camera→world
# # # R_wc = R_cw.T                                     # world→camera
# # #
# # # # R_wc was built as camera->world; invert it
# # # R_cw = R_wc
# # # R_wc = R_cw.T
# # #
# # #
# # # # Camera center in world coordinates
# # # C_w = np.array([0.0, 0.0, H])
# # #
# # # # ----------------------------
# # # # Minimal model: constant GSD at seafloor
# # # # ----------------------------
# # # # Approximate ground footprint at seafloor for nadir view
# # # W = 2.0 * H * np.tan(alpha_h / 2.0)  # width [m]
# # # Hg = 2.0 * H * np.tan(alpha_v / 2.0) # height [m]
# # #
# # # GSD_x = W / Nx  # m per pixel (horizontal)
# # # GSD_y = Hg / Ny # m per pixel (vertical)
# # #
# # # # Map world (X,Y,0) to image (u,v) with minimal model
# # # def project_minimal(X, Y):
# # #     # Assume image center corresponds to (0,0) on seafloor
# # #     u = cx + X / GSD_x
# # #     v = cy - Y / GSD_y  # minus because image y increases downward
# # #     return u, v
# # #
# # # # ----------------------------
# # # # Full projective model: world->image
# # # # ----------------------------
# # # def project_full(X, Y, Z=0.0):
# # #     Pw = np.array([X, Y, Z])
# # #     # World->camera: Pc = R_wc * (Pw - C_w)
# # #     Pc = R_wc @ (Pw - C_w)
# # #     if Pc[2] <= 0:
# # #         return None  # behind camera
# # #     x = Pc[0] / Pc[2]
# # #     y = Pc[1] / Pc[2]
# # #     uv = K @ np.array([x, y, 1.0])
# # #     u, v = uv[0], uv[1]
# # #     return u, v
# # #
# # # # ----------------------------
# # # # Build world grid on seafloor
# # # # ----------------------------
# # # # Use approximate footprint extents from minimal model
# # # X_min, X_max = -W / 2.0, W / 2.0
# # # Y_min, Y_max = -Hg / 2.0, Hg / 2.0
# # #
# # # # Generate grid lines in world coordinates
# # # X_lines = np.arange(np.floor(X_min / grid_dx) * grid_dx,
# # #                     np.ceil(X_max / grid_dx) * grid_dx + 1e-6,
# # #                     grid_dx)
# # # Y_lines = np.arange(np.floor(Y_min / grid_dy) * grid_dy,
# # #                     np.ceil(Y_max / grid_dy) * grid_dy + 1e-6,
# # #                     grid_dy)
# # #
# # # overlay = img.copy()
# # #
# # # # ----------------------------
# # # # Draw minimal model grid (e.g., green)
# # # # ----------------------------
# # # color_min = (0, 255, 0)  # BGR
# # #
# # # # Vertical lines (constant X)
# # # for X in X_lines:
# # #     u1, v1 = project_minimal(X, Y_min)
# # #     u2, v2 = project_minimal(X, Y_max)
# # #     p1 = (int(round(u1)), int(round(v1)))
# # #     p2 = (int(round(u2)), int(round(v2)))
# # #     if (0 <= p1[0] < Nx and 0 <= p1[1] < Ny) or (0 <= p2[0] < Nx and 0 <= p2[1] < Ny):
# # #         cv2.line(overlay, p1, p2, color_min, 1, cv2.LINE_AA)
# # #
# # # # Horizontal lines (constant Y)
# # # for Y in Y_lines:
# # #     u1, v1 = project_minimal(X_min, Y)
# # #     u2, v2 = project_minimal(X_max, Y)
# # #     p1 = (int(round(u1)), int(round(v1)))
# # #     p2 = (int(round(u2)), int(round(v2)))
# # #     if (0 <= p1[0] < Nx and 0 <= p1[1] < Ny) or (0 <= p2[0] < Nx and 0 <= p2[1] < Ny):
# # #         cv2.line(overlay, p1, p2, color_min, 1, cv2.LINE_AA)
# # #
# # #
# # # # ----------------------------
# # # # Draw full projective model grid (RED)
# # # # ----------------------------
# # # color_full = (0, 0, 255)  # BGR
# # #
# # # # Vertical grid lines (constant X)
# # # for X in X_lines:
# # #     pts = []
# # #     for Y in np.linspace(Y_min, Y_max, 200):   # <-- many samples!
# # #         uv = project_full(X, Y, 0.0)
# # #         if uv is None:
# # #             continue
# # #         u, v = uv
# # #         if 0 <= u < Nx and 0 <= v < Ny:
# # #             pts.append((int(u), int(v)))
# # #
# # #     # Draw polyline through all projected points
# # #     if len(pts) > 1:
# # #         for i in range(len(pts) - 1):
# # #             cv2.line(overlay, pts[i], pts[i+1], color_full, 1, cv2.LINE_AA)
# # #
# # # # Horizontal grid lines (constant Y)
# # # for Y in Y_lines:
# # #     pts = []
# # #     for X in np.linspace(X_min, X_max, 200):   # <-- many samples!
# # #         uv = project_full(X, Y, 0.0)
# # #         if uv is None:
# # #             continue
# # #         u, v = uv
# # #         if 0 <= u < Nx and 0 <= v < Ny:
# # #             pts.append((int(u), int(v)))
# # #
# # #     if len(pts) > 1:
# # #         for i in range(len(pts) - 1):
# # #             cv2.line(overlay, pts[i], pts[i+1], color_full, 1, cv2.LINE_AA)
# # #
# # # # # ----------------------------
# # # # # Draw full projective model grid (e.g., red)
# # # # # ----------------------------
# # # # color_full = (0, 0, 255)  # BGR
# # # #
# # # # # Vertical lines (constant X)
# # # # for X in X_lines:
# # # #     pts = []
# # # #     for Y in np.linspace(Y_min, Y_max, 50):
# # # #         uv = project_full(X, Y, 0.0)
# # # #         if uv is None:
# # # #             continue
# # # #         u, v = uv
# # # #         if 0 <= u < Nx and 0 <= v < Ny:
# # # #             pts.append((int(round(u)), int(round(v))))
# # # #     if len(pts) >= 2:
# # # #         for i in range(len(pts) - 1):
# # # #             cv2.line(overlay, pts[i], pts[i+1], color_full, 1, cv2.LINE_AA)
# # # #
# # # # # Horizontal lines (constant Y)
# # # # for Y in Y_lines:
# # # #     pts = []
# # # #     for X in np.linspace(X_min, X_max, 50):
# # # #         uv = project_full(X, Y, 0.0)
# # # #         if uv is None:
# # # #             continue
# # # #         u, v = uv
# # # #         if 0 <= u < Nx and 0 <= v < Ny:
# # # #             pts.append((int(round(u)), int(round(v))))
# # # #     if len(pts) >= 2:
# # # #         for i in range(len(pts) - 1):
# # # #             cv2.line(overlay, pts[i], pts[i+1], color_full, 1, cv2.LINE_AA)
# # #
# # # # ----------------------------
# # # # Save / show result
# # # # ----------------------------
# # # out_path = "grid_overlay.png"
# # # cv2.imwrite(out_path, overlay)
# # # print(f"Saved overlay with grids to {out_path}")
