# src/preprocess.py

import csv
from pathlib import Path
from src.utils import unix_to_time_utc

def add_time_utc_to_csv(csv_path: str) -> str:
    """
    Reads glidersubset.csv, adds a 'time_utc' column,
    writes updated CSV to the same file, and returns the path.
    """
    csv_path = Path(csv_path)
    rows = []

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        if "time_utc" not in headers:
            headers.append("time_utc")

        for row in reader:
            # ts = row.get("timestamp") or row.get("time") or None

            ts = (
                    row.get("m_present_time.timestamp")
                    or row.get("sci_m_present_time.timestamp")
                    or row.get("timestamp")
                    or row.get("time")
            )
            if ts is None:
                raise ValueError("No timestamp column found in CSV")

            row["time_utc"] = unix_to_time_utc(ts)
            rows.append(row)

    # Write updated CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    return str(csv_path)
