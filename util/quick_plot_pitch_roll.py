## quick_plot_pitch_roll.py
#!/usr/bin/env python3

import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def find_column(headers, candidates):
    """
    Return the first matching column name from a list of candidates.
    Case-insensitive. Returns None if not found.
    """
    headers_lower = {h.lower(): h for h in headers}
    for cand in candidates:
        if cand.lower() in headers_lower:
            return headers_lower[cand.lower()]
    return None


def summarize(series, name):
    """Print mean, median, stdev for a numeric series."""
    print(f"\n{name} summary:")
    print(f"  mean:   {series.mean():.4f}")
    print(f"  median: {series.median():.4f}")
    print(f"  stdev:  {series.std():.4f}")


def main(csv_path: str):
    df = pd.read_csv(csv_path)
    headers = df.columns.tolist()

    # Flexible column name sets
    pitch_candidates = ["pitch", "m_pitch.rad", "pitch_rad", "pitch_rad.", "pitch (rad)"]
    roll_candidates  = ["roll", "m_roll.rad", "roll_rad", "roll_rad.", "roll (rad)"]

    pitch_col = find_column(headers, pitch_candidates)
    roll_col  = find_column(headers, roll_candidates)

    if pitch_col is None or roll_col is None:
        print("⚠️ Could not find required columns.")
        print("Available columns:", ", ".join(headers))
        return

    # Load and convert to float
    pitch = df[pitch_col].astype(float)
    roll  = df[roll_col].astype(float)

    # Convert radians → degrees
    pitch_deg = np.degrees(pitch)
    roll_deg  = np.degrees(roll)

    # Summary stats
    summarize(pitch_deg, f"{pitch_col} (deg)")
    summarize(roll_deg,  f"{roll_col} (deg)")

    # Plot
    plt.figure(figsize=(10, 5))
    plt.plot(pitch_deg.values, label=f"{pitch_col} (deg)", alpha=0.8)
    plt.plot(roll_deg.values,  label=f"{roll_col} (deg)", alpha=0.8)
    plt.xlabel("Sample index")
    plt.ylabel("Degrees")
    plt.title("Pitch & Roll vs Sample Index")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python quick_plot_pitch_roll.py <path/to/file.csv>")
        sys.exit(1)

    main(sys.argv[1])