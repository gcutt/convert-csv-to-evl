"""
EK80_cal_xml_summarize.py

• Reads, summarizes, and plots EK80 calibration XML files
• Handles CW and FM
• Extracts ChannelName
• Uses TargetReference Frequency/Response for full-resolution TS(f)
• CFR → TS_full(f_full) on TargetReference frequency axis
• TS_full(f_full) → TS_calgrid(f_cal) on CalibrationResults frequency axis
• Also computes TS_calgrid from UnCompensatedFrequencyResponse (UnCFR)
• Computes median + IQR across hits
• Multipanel figure (3×3) includes:

Column 1:
    (1) TS_full(f) from UnCFR (TargetReference axis)
    (2) TS_full(f) from CFR (TargetReference axis)
    (3) TargetReference TS(f)

Column 2:
    (4) TS_calgrid(f) from UnCFR
    (5) TS_calgrid(f) from CFR
    (6) Gain

Column 3:
    (7) BeamWidthAlongship
    (8) BeamWidthAthwartship
    (9) SaCorrection

• All TS plots use y-limits [-70, -30] dB
"""

import os
import glob
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from scipy.stats import iqr
from collections import Counter


# ---------------------------------------------------------
# XML PARSING
# ---------------------------------------------------------

def parse_calibration_results(xml_path):
    """
    Returns:
        results: dict of CalibrationResults
        hitdata: list of dicts, each containing:
            - CompensatedFrequencyResponse (CFR)
            - UnCompensatedFrequencyResponse (UnCFR) if present
        channel_name: string or None
        target_ref: dict with keys:
            'Frequency' (np.ndarray) - full-resolution frequency axis
            'Response' (np.ndarray)  - theoretical TS(f)
            'Diameter' (float or None)
    """

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # ---- ChannelName ----
    ch = root.find(".//ChannelName")
    channel_name = ch.text.strip() if ch is not None else None

    # ---- CalibrationResults ----
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
                except Exception:
                    pass

        # Scalar fallback
        try:
            results[elem.tag] = float(text)
        except Exception:
            results[elem.tag] = text

    # ---- TargetReference ----
    target_ref = {}
    tref = root.find(".//TargetReference")
    if tref is not None:
        f_node = tref.find("Frequency")
        r_node = tref.find("Response")
        d_node = tref.find("Diameter")

        if f_node is not None and f_node.text:
            f_txt = f_node.text.replace(";", " ").replace(",", " ")
            f_parts = f_txt.split()
            if f_parts:
                target_ref["Frequency"] = np.array([float(x) for x in f_parts])

        if r_node is not None and r_node.text:
            r_txt = r_node.text.replace(";", " ").replace(",", " ")
            r_parts = r_txt.split()
            if r_parts:
                target_ref["Response"] = np.array([float(x) for x in r_parts])

        if d_node is not None and d_node.text:
            try:
                target_ref["Diameter"] = float(d_node.text)
            except Exception:
                target_ref["Diameter"] = None
        else:
            target_ref["Diameter"] = None

    # ---- HitData blocks ----
    hitdata = []
    for hit in root.findall(".//HitData"):
        hd = {}

        # CFR
        cfr = hit.find("CompensatedFrequencyResponse")
        if cfr is not None and cfr.text is not None:
            txt = cfr.text.replace(";", " ").replace(",", " ")
            parts = txt.split()
            if parts:
                hd["CFR"] = np.array([float(x) for x in parts])

        # UnCFR
        uncfr = hit.find("UnCompensatedFrequencyResponse")
        if uncfr is not None and uncfr.text is not None:
            txt = uncfr.text.replace(";", " ").replace(",", " ")
            parts = txt.split()
            if parts:
                hd["UnCFR"] = np.array([float(x) for x in parts])

        hitdata.append(hd)

    return results, hitdata, channel_name, target_ref


# ---------------------------------------------------------
# TS(f) FROM CFR OR UnCFR USING TARGETREFERENCE AXIS
# ---------------------------------------------------------

def compute_ts_from_array(arr_list, f_full):
    """
    Given a list of arrays (CFR or UnCFR), compute TS_full(f_full)
    using normalized sweep mapping.

    Returns:
        TS_median, TS_q25, TS_q75 (or all None if not computable)
    """

    if not arr_list or f_full is None:
        return None, None, None

    lengths = [len(a) for a in arr_list]
    common_len = Counter(lengths).most_common(1)[0][0]

    # CFR/UnCFR bins normalized 0..1
    cfr_x = np.linspace(0, 1, common_len)

    # Full-resolution frequency axis normalized 0..1
    f_full_norm = (f_full - f_full.min()) / (f_full.max() - f_full.min())

    TS_full_list = []
    for arr in arr_list:
        if len(arr) == common_len:
            TS_full = np.interp(f_full_norm, cfr_x, arr)
            TS_full_list.append(TS_full)

    if not TS_full_list:
        return None, None, None

    TS_stack = np.vstack(TS_full_list)
    TS_median = np.median(TS_stack, axis=0)
    TS_q25 = np.percentile(TS_stack, 25, axis=0)
    TS_q75 = np.percentile(TS_stack, 75, axis=0)

    return TS_median, TS_q25, TS_q75


def compute_ts_all(cal, hitdata, target_ref):
    """
    Compute:
        TS_full_CFR(f_full)
        TS_calgrid_CFR(f_cal)
        TS_full_UnCFR(f_full)
        TS_calgrid_UnCFR(f_cal)

    Returns dict with all arrays, or None if not computable.
    """

    freq_cal = cal.get("Frequency")
    f_full = target_ref.get("Frequency") if target_ref else None

    if not isinstance(freq_cal, np.ndarray) or freq_cal.size < 2:
        return None

    if f_full is None or not isinstance(f_full, np.ndarray) or f_full.size < 2:
        return None

    # Collect CFR and UnCFR arrays
    CFR_list = [hd["CFR"] for hd in hitdata if "CFR" in hd]
    UnCFR_list = [hd["UnCFR"] for hd in hitdata if "UnCFR" in hd]

    # TS_full from CFR
    TS_full_CFR, TS_full_CFR_q25, TS_full_CFR_q75 = compute_ts_from_array(CFR_list, f_full)

    # TS_full from UnCFR
    TS_full_UnCFR, TS_full_UnCFR_q25, TS_full_UnCFR_q75 = compute_ts_from_array(UnCFR_list, f_full)

    # Downsample to calibration grid
    if TS_full_CFR is not None:
        TS_cal_CFR = np.interp(freq_cal, f_full, TS_full_CFR)
        TS_cal_CFR_q25 = np.interp(freq_cal, f_full, TS_full_CFR_q25)
        TS_cal_CFR_q75 = np.interp(freq_cal, f_full, TS_full_CFR_q75)
    else:
        TS_cal_CFR = TS_cal_CFR_q25 = TS_cal_CFR_q75 = None

    if TS_full_UnCFR is not None:
        TS_cal_UnCFR = np.interp(freq_cal, f_full, TS_full_UnCFR)
        TS_cal_UnCFR_q25 = np.interp(freq_cal, f_full, TS_full_UnCFR_q25)
        TS_cal_UnCFR_q75 = np.interp(freq_cal, f_full, TS_full_UnCFR_q75)
    else:
        TS_cal_UnCFR = TS_cal_UnCFR_q25 = TS_cal_UnCFR_q75 = None

    return dict(
        f_full=f_full,
        freq_cal=freq_cal,
        TS_full_CFR=TS_full_CFR,
        TS_full_CFR_q25=TS_full_CFR_q25,
        TS_full_CFR_q75=TS_full_CFR_q75,
        TS_cal_CFR=TS_cal_CFR,
        TS_cal_CFR_q25=TS_cal_CFR_q25,
        TS_cal_CFR_q75=TS_cal_CFR_q75,
        TS_full_UnCFR=TS_full_UnCFR,
        TS_full_UnCFR_q25=TS_full_UnCFR_q25,
        TS_full_UnCFR_q75=TS_full_UnCFR_q75,
        TS_cal_UnCFR=TS_cal_UnCFR,
        TS_cal_UnCFR_q25=TS_cal_UnCFR_q25,
        TS_cal_UnCFR_q75=TS_cal_UnCFR_q75
    )


# ---------------------------------------------------------
# SUMMARIZATION
# ---------------------------------------------------------

def describe_array(arr):
    return {
        "mean": np.mean(arr),
        "median": np.median(arr),
        "sd": np.std(arr),
        "iqr": iqr(arr)
    }


def fmt(param, value):
    if param == "PulseLength":
        return f"{value:.6f}"
    if param in ("SaCorrection", "TsRmsError"):
        return f"{value:.4f}"
    return f"{value:.2f}"


def fmt_stats(param, stats):
    return {k: fmt(param, v) for k, v in stats.items()}


def summarize_cw(cal, channel_name):
    rows = []
    for key, val in cal.items():
        if isinstance(val, float):
            rows.append([key, fmt(key, val)])
    df = pd.DataFrame(rows, columns=["Parameter", "Value"])
    df.loc[len(df)] = ["ChannelName", channel_name]
    return df


def summarize_fm(cal, hitdata, channel_name, target_ref):
    rows = []

    # CalibrationResults arrays
    for key, val in cal.items():
        if isinstance(val, np.ndarray):
            stats = describe_array(val)
            rows.append([key, fmt_stats(key, stats)])

    # TS summaries
    ts = compute_ts_all(cal, hitdata, target_ref)
    if ts is not None:
        if ts["TS_full_CFR"] is not None:
            rows.append(["TS_full_CFR_median", ts["TS_full_CFR"]])
        if ts["TS_cal_CFR"] is not None:
            rows.append(["TS_cal_CFR_median", ts["TS_cal_CFR"]])

        if ts["TS_full_UnCFR"] is not None:
            rows.append(["TS_full_UnCFR_median", ts["TS_full_UnCFR"]])
        if ts["TS_cal_UnCFR"] is not None:
            rows.append(["TS_cal_UnCFR_median", ts["TS_cal_UnCFR"]])

    df = pd.DataFrame(rows, columns=["Parameter", "Statistics"])
    df.loc[len(df)] = ["ChannelName", channel_name]
    return df


# ---------------------------------------------------------
# PLOTTING
# ---------------------------------------------------------

def plot_fm(cal, hitdata, channel_name, target_ref, out_prefix):
    ts = compute_ts_all(cal, hitdata, target_ref)
    if ts is None:
        print("TS computation failed.")
        return

    f_full = ts["f_full"]
    f_cal = ts["freq_cal"]

    tref_freq = target_ref.get("Frequency") if target_ref else None
    tref_resp = target_ref.get("Response") if target_ref else None
    tref_diam = target_ref.get("Diameter") if target_ref else None

    # ---------------------------------------------------------
    # MAIN MULTI-PANEL FIGURE (3×3)
    # ---------------------------------------------------------
    fig, axes = plt.subplots(3, 3, figsize=(18, 12))
    axes = axes.flatten()

    # ---------------------------------------------------------
    # Column 1
    # ---------------------------------------------------------

    # Panel 1: TS_full from UnCFR vs frequency (median + IQR)
    ax = axes[0]
    if ts["TS_full_UnCFR"] is not None:
        # dashed blue median
        ax.plot(f_full, ts["TS_full_UnCFR"], lw=2, color="tab:blue",
                linestyle="--", label="Median TS_full(UnCFR)")

        # IQR shading
        ax.fill_between(
            f_full,
            ts["TS_full_UnCFR_q25"],
            ts["TS_full_UnCFR_q75"],
            alpha=0.3,
            color="tab:blue",
            label="IQR"
        )

        # TargetReference overlay (solid orange)
        if tref_freq is not None and tref_resp is not None:
            ax.plot(tref_freq, tref_resp, lw=2, color="tab:orange",
                    label="TargetReference")

        ax.set_title("TS_full(f) from UnCFR (TargetReference axis)")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("TS (dB)")
        ax.set_ylim([-70, -30])
        ax.grid(True)
        ax.legend()
    else:
        ax.set_title("TS_full(UnCFR) (missing)")

    # Panel 2: TS_full from CFR vs frequency (median + IQR)
    ax = axes[1]
    if ts["TS_full_CFR"] is not None:
        # dashed blue median
        ax.plot(f_full, ts["TS_full_CFR"], lw=2, color="tab:blue",
                linestyle="--", label="Median TS_full(CFR)")

        # IQR shading
        ax.fill_between(
            f_full,
            ts["TS_full_CFR_q25"],
            ts["TS_full_CFR_q75"],
            alpha=0.3,
            color="tab:blue",
            label="IQR"
        )

        # TargetReference overlay (solid orange)
        if tref_freq is not None and tref_resp is not None:
            ax.plot(tref_freq, tref_resp, lw=2, color="tab:orange",
                    label="TargetReference")

        ax.set_title("TS_full(f) from CFR (TargetReference axis)")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("TS (dB)")
        ax.set_ylim([-70, -30])
        ax.grid(True)
        ax.legend()
    else:
        ax.set_title("TS_full(CFR) (missing)")

    # # Panel 1: TS_full from UnCFR vs frequency (median + IQR)
    # ax = axes[0]
    # if ts["TS_full_UnCFR"] is not None:
    #     ax.plot(f_full, ts["TS_full_UnCFR"], lw=2, label="Median TS_full(UnCFR)")
    #     ax.fill_between(
    #         f_full,
    #         ts["TS_full_UnCFR_q25"],
    #         ts["TS_full_UnCFR_q75"],
    #         alpha=0.3,
    #         label="IQR"
    #     )
    #     ax.set_title("TS_full(f) from UnCFR (TargetReference axis)")
    #     ax.set_xlabel("Frequency (Hz)")
    #     ax.set_ylabel("TS (dB)")
    #     ax.set_ylim([-70, -30])
    #     ax.grid(True)
    #     ax.legend()
    # else:
    #     ax.set_title("TS_full(UnCFR) (missing)")

    # # Panel 2: TS_full from CFR vs frequency (median + IQR)
    # ax = axes[1]
    # if ts["TS_full_CFR"] is not None:
    #     ax.plot(f_full, ts["TS_full_CFR"], lw=2, label="Median TS_full(CFR)")
    #     ax.fill_between(
    #         f_full,
    #         ts["TS_full_CFR_q25"],
    #         ts["TS_full_CFR_q75"],
    #         alpha=0.3,
    #         label="IQR"
    #     )
    #     ax.set_title("TS_full(f) from CFR (TargetReference axis)")
    #     ax.set_xlabel("Frequency (Hz)")
    #     ax.set_ylabel("TS (dB)")
    #     ax.set_ylim([-70, -30])
    #     ax.grid(True)
    #     ax.legend()
    # else:
    #     ax.set_title("TS_full(CFR) (missing)")

    # Panel 3: TargetReference TS(f)
    ax = axes[2]
    if tref_freq is not None and tref_resp is not None:
        ax.plot(tref_freq, tref_resp, lw=2, color="tab:orange")
        ax.set_title("TargetReference")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("TS (dB)")
        ax.set_ylim([-70, -30])
        ax.grid(True)
    else:
        ax.set_title("TargetReference (missing)")

    # ---------------------------------------------------------
    # Column 2
    # ---------------------------------------------------------

    # Panel 4: TS_calgrid from UnCFR
    ax = axes[3]
    if ts["TS_cal_UnCFR"] is not None:
        ax.plot(f_cal, ts["TS_cal_UnCFR"], lw=2, label="Median TS_cal(UnCFR)")
        ax.fill_between(
            f_cal,
            ts["TS_cal_UnCFR_q25"],
            ts["TS_cal_UnCFR_q75"],
            alpha=0.3
        )
        ax.set_title("TS_calgrid(f) from UnCFR")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("TS (dB)")
        ax.set_ylim([-70, -30])
        ax.grid(True)
        ax.legend()
    else:
        ax.set_title("TS_calgrid(UnCFR) (missing)")

    # Panel 5: TS_calgrid from CFR
    ax = axes[4]
    if ts["TS_cal_CFR"] is not None:
        ax.plot(f_cal, ts["TS_cal_CFR"], lw=2, label="Median TS_cal(CFR)")
        ax.fill_between(
            f_cal,
            ts["TS_cal_CFR_q25"],
            ts["TS_cal_CFR_q75"],
            alpha=0.3
        )
        ax.set_title("TS_calgrid(f) from CFR")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("TS (dB)")
        ax.set_ylim([-70, -30])
        ax.grid(True)
        ax.legend()
    else:
        ax.set_title("TS_calgrid(CFR) (missing)")

    # Panel 6: Gain
    ax = axes[5]
    if "Gain" in cal and isinstance(cal["Gain"], np.ndarray):
        ax.plot(f_cal, cal["Gain"], lw=2)
        ax.set_title("Gain")
        ax.set_xlabel("Frequency (Hz)")
        ax.grid(True)
    else:
        ax.set_title("Gain (missing)")

    # ---------------------------------------------------------
    # Column 3
    # ---------------------------------------------------------

    # Panel 7: BeamWidthAlongship
    ax = axes[6]
    if "BeamWidthAlongship" in cal and isinstance(cal["BeamWidthAlongship"], np.ndarray):
        ax.plot(f_cal, cal["BeamWidthAlongship"], lw=2)
        ax.set_title("BeamWidthAlongship")
        ax.set_xlabel("Frequency (Hz)")
        ax.grid(True)
    else:
        ax.set_title("BeamWidthAlongship (missing)")

    # Panel 8: BeamWidthAthwartship
    ax = axes[7]
    if "BeamWidthAthwartship" in cal and isinstance(cal["BeamWidthAthwartship"], np.ndarray):
        ax.plot(f_cal, cal["BeamWidthAthwartship"], lw=2)
        ax.set_title("BeamWidthAthwartship")
        ax.set_xlabel("Frequency (Hz)")
        ax.grid(True)
    else:
        ax.set_title("BeamWidthAthwartship (missing)")

    # Panel 9: SaCorrection
    ax = axes[8]
    if "SaCorrection" in cal and isinstance(cal["SaCorrection"], np.ndarray):
        ax.plot(f_cal, cal["SaCorrection"], lw=2)
        ax.set_title("SaCorrection")
        ax.set_xlabel("Frequency (Hz)")
        ax.grid(True)
    else:
        ax.set_title("SaCorrection (missing)")

    # ---- Title with ChannelName + PulseLength + Diameter ----
    pulse = cal.get("PulseLength", None)
    diam = tref_diam

    if pulse is not None and isinstance(pulse, float):
        if diam is not None:
            fig.suptitle(
                f"FM Calibration — {channel_name} — PulseLength = {pulse:.6f} s — Diameter = {diam:.3f} mm"
            )
        else:
            fig.suptitle(
                f"FM Calibration — {channel_name} — PulseLength = {pulse:.6f} s"
            )
    else:
        if diam is not None:
            fig.suptitle(
                f"FM Calibration — {channel_name} — Diameter = {diam:.3f} mm"
            )
        else:
            fig.suptitle(f"FM Calibration — {channel_name}")

    plt.tight_layout()
    plt.savefig(f"{out_prefix}_fm_main.png", dpi=150)
    plt.close()


# ---------------------------------------------------------
# PROCESSING
# ---------------------------------------------------------

def process_file(xml_path, out_dir):
    print("\n====================================")
    print(f"Processing: {os.path.basename(xml_path)}")

    cal, hitdata, channel_name, target_ref = parse_calibration_results(xml_path)
    prefix = os.path.splitext(os.path.basename(xml_path))[0]

    is_fm = isinstance(cal.get("Frequency"), np.ndarray)

    if not is_fm:
        print("Detected CW calibration")
        df = summarize_cw(cal, channel_name)
        df.to_csv(os.path.join(out_dir, f"{prefix}_cw_summary.csv"), index=False)
        print("Saved CW summary CSV")
    else:
        print("Detected FM calibration")
        df = summarize_fm(cal, hitdata, channel_name, target_ref)
        df.to_csv(os.path.join(out_dir, f"{prefix}_fm_summary.csv"), index=False)
        print("Saved FM summary CSV")

        plot_fm(cal, hitdata, channel_name, target_ref,
                out_prefix=os.path.join(out_dir, prefix))


def process_directory(directory):
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

if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "./xml_files"

    if os.path.isdir(target):
        process_directory(target)
    elif os.path.isfile(target):
        out_dir = os.path.join(os.path.dirname(target), "summary_output")
        os.makedirs(out_dir, exist_ok=True)
        process_file(target, out_dir)
    else:
        print(f"Invalid path: {target}")
