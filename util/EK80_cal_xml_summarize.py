"""
EK80_cal_xml_summarize.py
Read, summarize, and plot EK80 calibration results in EK80 calibration XML files.
Processes a single file OR all .xml files in a directory.
"""

import os
import glob
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from scipy.stats import iqr


# ---------------------------------------------------------
# XML PARSING
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

    results = {}
    for elem in calib:

        text = " ".join(elem.itertext()).strip()

        # Detect array vs scalar
        if ";" in text or " " in text or "," in text:
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
# SUMMARIZATION
# ---------------------------------------------------------

def describe_array(arr):
    """Return mean, median, sd, iqr as a dict."""
    return {
        "mean": np.mean(arr),
        "median": np.median(arr),
        "sd": np.std(arr),
        "iqr": iqr(arr)
    }


def summarize_cw(cal):
    """
    Build a DataFrame summarizing scalar CW calibration results.
    """
    rows = []
    for key, val in cal.items():
        if isinstance(val, float):
            rows.append([key, fmt(key, val)])
    return pd.DataFrame(rows, columns=["Parameter", "Value"])


def summarize_fm(cal):
    """
    Build a DataFrame summarizing array-based FM calibration results.
    """
    rows = []
    for key, val in cal.items():
        if isinstance(val, np.ndarray):
            stats = describe_array(val)
            rows.append([key, fmt_stats(key, stats)])
    return pd.DataFrame(rows, columns=["Parameter", "Statistics"])


# ---------------------------------------------------------
# FM PLOTTING
# ---------------------------------------------------------

def plot_fm(cal, out_png):
    """
    Create a 4-panel figure for FM calibration arrays.
    """
    params = ["Gain", "SaCorrection", "BeamWidthAlongship", "BeamWidthAthwartship"]
    freq = cal.get("Frequency")

    if freq is None:
        print("FM plot skipped: Frequency array missing")
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()

    for ax, param in zip(axes, params):
        if param not in cal:
            ax.set_title(f"{param} (missing)")
            continue

        ax.plot(freq, cal[param], lw=2, color="#1f77b4")
        ax.plot(freq, cal[param], 'x', color="#1f77b4", markersize=6)

        ax.set_title(param)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel(param)
        ax.grid(True)

    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()
    print(f"Saved FM figure → {out_png}")


# ---------------------------------------------------------
# FORMATTING HELPERS
# ---------------------------------------------------------

def fmt(param, value):
    if param == "PulseLength":
        return f"{value:.6f}"
    if param in ("SaCorrection", "TsRmsError"):
        return f"{value:.4f}"
    return f"{value:.2f}"

def fmt_stats(param, stats):
    return {k: fmt(param, v) for k, v in stats.items()}


# ---------------------------------------------------------
# PROCESSING LOGIC
# ---------------------------------------------------------

def process_file(xml_path, out_dir):
    """
    Process a single EK80 calibration XML file.
    """
    print("\n====================================")
    print(f"Processing: {os.path.basename(xml_path)}")

    cal = parse_calibration_results(xml_path)
    prefix = os.path.splitext(os.path.basename(xml_path))[0]

    is_fm = isinstance(cal.get("Frequency"), np.ndarray)

    if not is_fm:
        print("Detected CW calibration")
        df = summarize_cw(cal)
        print(df)

        csv_path = os.path.join(out_dir, f"{prefix}_cw_summary.csv")
        df.to_csv(csv_path, index=False)
        print(f"Saved CW CSV → {csv_path}")

    else:
        print("Detected FM calibration")
        df = summarize_fm(cal)
        print(df)

        csv_path = os.path.join(out_dir, f"{prefix}_fm_summary.csv")
        df.to_csv(csv_path, index=False)
        print(f"Saved FM CSV → {csv_path}")

        plot_fm(cal, out_png=os.path.join(out_dir, f"{prefix}_fm_plot.png"))


def process_directory(directory):
    """
    Process all .xml files in a directory independently.
    """
    files = glob.glob(os.path.join(directory, "*.xml"))
    if not files:
        print("No XML files found.")
        return

    out_dir = os.path.join(directory, "summary_output")
    os.makedirs(out_dir, exist_ok=True)

    for xml_path in files:
        process_file(xml_path, out_dir)


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

import sys

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "./xml_files"

    if os.path.isdir(target):
        process_directory(target)
    elif os.path.isfile(target):
        out_dir = os.path.join(os.path.dirname(target), "summary_output")
        os.makedirs(out_dir, exist_ok=True)
        process_file(target, out_dir)
    else:
        print(f"Invalid path: {target}")
