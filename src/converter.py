# src/converter.py

import csv
import re
from src.utils import parse_utc_to_evl_format
from datetime import datetime, timedelta

# from src.utils import parse_utc_to_evl_format, resolve_column

EVL_HEADER = "EVBD 3 3.00.41"
MISSING_DEPTH = -10000.99000


def resolve_column(headers: list[str], candidates: list[str], pattern: str | None = None) -> str:
    """
    Resolves a column name from headers using exact match or optional regex pattern.
    Raises ValueError if no match is found.
    """
    for candidate in candidates:
        if candidate in headers:
            return candidate
    if pattern:
        for header in headers:
            if re.fullmatch(pattern, header, re.IGNORECASE):
                return header
    raise ValueError(f"No matching column found for pattern: {pattern or candidates}")


## New version
def convert_csv_to_evl(
    csv_path: str,
    offset: timedelta = timedelta(),
    depth_multiplier: float = 1.0,
    mode: str = "depth"
) -> list[str]:
    evl_lines = []
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # time_col = resolve_column(headers, ["GMT_Time"], ["time_gmt"], r"UTC.?time")
        # time_col = resolve_column(headers, ["GMT_Time", "time_gmt"], r"UTC.?time")
        time_col = resolve_column(headers, ["time_utc"])

        if mode == "depth":
            value_col = resolve_column(headers, ["m_depth.m","depth_m", "depth", "pressure_bar", "pressure_dbar", "pressure"])
            print(f"MODE: depth, value_col: {value_col}")
        elif mode == "vertical_state":
            value_col = resolve_column(headers, ["vertical_state"], r"vertical.?state")
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        for row in reader:
            # date, time = parse_utc_to_evl_format(row[time_col], offset)
            date_str, time_str = row[time_col].split()
            date = date_str
            time = time_str + "0000"  # EVL requires HHMMSS + 4-digit microseconds

            value_str = row[value_col].strip()

            if mode == "depth":
                try:
                    depth = float(value_str) * depth_multiplier
                    status = 3
                except ValueError:
                    depth = MISSING_DEPTH
                    status = 0
            else:  # vertical_state mode
                if value_str.lower() == "descent":
                    depth = -1
                    status = 3
                elif value_str.lower() == "ascent":
                    depth = 1
                    status = 3
                else:
                    depth = MISSING_DEPTH
                    status = 0

            evl_lines.append(f"{date} {time} {depth:.5f} {status}")

    return [EVL_HEADER, str(len(evl_lines))] + evl_lines

