"""
Compares EK80 calibration results in pairs of EK80 calibration XML results files,
with same prefix and 'cal'/'recal' designation in fn.
e.g. "200CW-...Cal....XML" vs "200CW-...ReCal....XML"
"""

import os
import glob
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from scipy.stats import iqr


# ---------------------------------------------------------
# XML PARSING HELPERS
# ---------------------------------------------------------

def parse_calibration_results(xml_path):
    """
    Returns a dict of CalibrationResults.
    Scalar values → float
    Array values → numpy array of floats
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    calib = root.find(".//CalibrationResults")
    if calib is None:
        raise ValueError(f"No CalibrationResults found in {xml_path}")

    # results = {}
    # for elem in calib:
    #     text = elem.text.strip()
    #
    #     # Detect array vs scalar
    #     if "," in text or " " in text:
    #         # Array-like
    #         try:
    #             arr = np.array([float(x) for x in text.replace(",", " ").split()])
    #             results[elem.tag] = arr
    #         except:
    #             results[elem.tag] = text
    #     else:
    #         # Scalar
    #         try:
    #             results[elem.tag] = float(text)
    #         except:
    #             results[elem.tag] = text

    results = {}
    for elem in calib:

        text = " ".join(elem.itertext()).strip()

        # Detect array vs scalar
        if ";" in text or " " in text or "," in text:
            # Normalize separators
            cleaned = text.replace(";", " ").replace(",", " ")
            parts = cleaned.split()
            if len(parts) > 1:
                try:
                    arr = np.array([float(x) for x in parts])
                    results[elem.tag] = arr
                    continue
                except:
                    pass

        # Scalar fallback
        try:
            results[elem.tag] = float(text)
        except:
            results[elem.tag] = text

    return results


# ---------------------------------------------------------
# COMPARISON TABLES
# ---------------------------------------------------------

def compare_cw(cal, recal):
    """
    Build a DataFrame comparing scalar CW calibration results.
    """
    rows = []
    for key in cal:
        if isinstance(cal[key], float) and isinstance(recal.get(key), float):
            diff = cal[key] - recal[key]
            # rows.append([key, cal[key], recal[key], diff])
            rows.append([
                key,
                fmt(key, cal[key]),
                fmt(key, recal[key]),
                fmt(key, diff)
            ])

    return pd.DataFrame(rows, columns=["Parameter", "Cal", "ReCal", "Difference"])


def describe_array(arr):
    """Return mean, median, sd, iqr as a dict."""
    return {
        "mean": np.mean(arr),
        "median": np.median(arr),
        "sd": np.std(arr),
        "iqr": iqr(arr)
    }


def compare_fm(cal, recal):
    """
    Build a DataFrame comparing array-based FM calibration results.
    Each cell contains descriptive statistics.
    """
    rows = []
    for key in cal:
        if isinstance(cal[key], np.ndarray) and isinstance(recal.get(key), np.ndarray):
            cal_stats = describe_array(cal[key])
            rec_stats = describe_array(recal[key])
            diff_stats = {k: cal_stats[k] - rec_stats[k] for k in cal_stats}

            # rows.append([key, cal_stats, rec_stats, diff_stats])
            rows.append([
                key,
                fmt_stats(key, cal_stats),
                fmt_stats(key, rec_stats),
                fmt_stats(key, diff_stats)
            ])

    return pd.DataFrame(rows, columns=["Parameter", "Cal Stats", "ReCal Stats", "Diff Stats"])


# ---------------------------------------------------------
# FM PLOTTING
# ---------------------------------------------------------

def plot_fm_results(cal, recal, out_png="fm_comparison.png"):
    """
    Create a 4-panel figure for FM calibration arrays.
    """
    params = ["Gain", "SaCorrection", "BeamWidthAlongship", "BeamWidthAthwartship"]

    freq_cal = cal.get("Frequency")
    freq_recal = recal.get("Frequency")

    if freq_cal is None or freq_recal is None:
        print("FM plot skipped: Frequency arrays missing")
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()

    for ax, param in zip(axes, params):
        if param not in cal or param not in recal:
            ax.set_title(f"{param} (missing)")
            continue

        ax.plot(freq_cal, cal[param], label="Cal", lw=2)
        ax.plot(freq_recal, recal[param], label="ReCal", lw=2)
        ax.set_title(param)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel(param)
        ax.grid(True)
        ax.legend()

    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()
    print(f"Saved FM comparison figure → {out_png}")


# ---------------------------------------------------------
# FILE PAIRING LOGIC
# ---------------------------------------------------------

def pair_files(directory):
    """
    Returns list of (cal_file, recal_file) pairs based on shared prefix.
    Example:
        200CW-*.xml pairs with 200CW-*ReCalibration*.xml
    """
    files = glob.glob(os.path.join(directory, "*.xml"))
    pairs = []
    print("DEBUG: Found XML files:")
    for f in files:
        print("   ", f)

    # Group by prefix (CW or FM)
    # prefixes = set(f.split("/")[-1].split("-")[0] for f in files)
    prefixes = set(os.path.basename(f).split("-")[0] for f in files)

    for prefix in prefixes:
        cal_files = [f for f in files if prefix in f and "ReCalibration" not in f]
        recal_files = [f for f in files if prefix in f and "ReCalibration" in f]

        if len(cal_files) == 1 and len(recal_files) == 1:
            pairs.append((cal_files[0], recal_files[0]))

    print("DEBUG: File pairs detected:")
    for cal, recal in pairs:
        print("   CAL:", cal)
        print("   REC:", recal)

    return pairs


# ---------------------------------------------------------
# MAIN WORKFLOW
# ---------------------------------------------------------

# def process_directory(directory):
#     pairs = pair_files(directory)
#
#     for cal_path, recal_path in pairs:
#         print("\n====================================")
#         print(f"Comparing:\n  CAL:   {os.path.basename(cal_path)}\n  RE-CAL:{os.path.basename(recal_path)}")
#
#         cal = parse_calibration_results(cal_path)
#         recal = parse_calibration_results(recal_path)
#
#         is_fm = isinstance(cal.get("Frequency"), np.ndarray)
#         prefix = os.path.basename(cal_path).split("-")[0]
#
#         if not is_fm:
#             print("Detected CW calibration")
#             df = compare_cw(cal, recal)
#             print(df)
#
#             df.to_csv(f"{prefix}_cw_comparison.csv", index=False)
#             print(f"Saved CW CSV → {prefix}_cw_comparison.csv")
#
#         else:
#             print("Detected FM calibration")
#             df = compare_fm(cal, recal)
#             print(df)
#
#             df.to_csv(f"{prefix}_fm_comparison.csv", index=False)
#             print(f"Saved FM CSV → {prefix}_fm_comparison.csv")
#
#             plot_fm_results(cal, recal, out_png=f"{prefix}_fm_comparison.png")
def process_directory(directory):
    pairs = pair_files(directory)

    # Create output directory inside the input directory
    out_dir = os.path.join(directory, "comparison_output")
    os.makedirs(out_dir, exist_ok=True)

    for cal_path, recal_path in pairs:
        print("\n====================================")
        print(f"Comparing:\n  CAL:   {os.path.basename(cal_path)}\n  RE-CAL:{os.path.basename(recal_path)}")

        cal = parse_calibration_results(cal_path)
        recal = parse_calibration_results(recal_path)

        is_fm = isinstance(cal.get("Frequency"), np.ndarray)
        prefix = os.path.basename(cal_path).split("-")[0]

        if not is_fm:
            print("Detected CW calibration")
            df = compare_cw(cal, recal)
            print(df)

            df.to_csv(os.path.join(out_dir, f"{prefix}_cw_comparison.csv"), index=False)
            print(f"Saved CW CSV → {os.path.join(out_dir, f'{prefix}_cw_comparison.csv')}")

        else:
            print("Detected FM calibration")
            df = compare_fm(cal, recal)
            print(df)

            df.to_csv(os.path.join(out_dir, f"{prefix}_fm_comparison.csv"), index=False)
            print(f"Saved FM CSV → {os.path.join(out_dir, f'{prefix}_fm_comparison.csv')}")

            plot_fm_results(
                cal, recal,
                out_png=os.path.join(out_dir, f"{prefix}_fm_comparison.png")
            )


def fmt(param, value):
    if param == "PulseLength":
        return f"{value:.6f}"
    if param in ("SaCorrection", "TsRmsError"):
        return f"{value:.4f}"
    return f"{value:.2f}"

def fmt_stats(param, stats):
    return {k: fmt(param, v) for k, v in stats.items()}


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

import sys

if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "./xml_files"
    process_directory(directory)
