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
        time_col = resolve_column(headers, ["GMT_Time", "time_gmt"], r"UTC.?time")

        if mode == "depth":
            value_col = resolve_column(headers, ["depth_m", "depth", "pressure_bar", "pressure_dbar", "pressure"])
            print(f"MODE: depth, value_col: {value_col}")
        elif mode == "vertical_state":
            value_col = resolve_column(headers, ["vertical_state"], r"vertical.?state")
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        for row in reader:
            date, time = parse_utc_to_evl_format(row[time_col], offset)
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


##---------------------------------------------------------------------
# import csv
# import re
# from src.utils import parse_utc_to_evl_format
# from datetime import datetime, timedelta
#
# # from src.utils import parse_utc_to_evl_format, resolve_column
#
# EVL_HEADER = "EVBD 3 3.00.41"
# MISSING_DEPTH = -10000.99000
#
#
# def resolve_column(headers: list[str], candidates: list[str], pattern: str | None = None) -> str:
#     """
#     Resolves a column name from headers using exact match or optional regex pattern.
#     Raises ValueError if no match is found.
#     """
#     for candidate in candidates:
#         if candidate in headers:
#             return candidate
#     if pattern:
#         for header in headers:
#             if re.fullmatch(pattern, header, re.IGNORECASE):
#                 return header
#     raise ValueError(f"No matching column found for pattern: {pattern or candidates}")
#
#
# ## New version, allows time offset and depth scaling
# def convert_csv_to_evl(csv_path: str, offset: timedelta = timedelta(), depth_multiplier: float = 1.0) -> list[str]:
#     evl_lines = []
#     with open(csv_path, newline='') as f:
#         reader = csv.DictReader(f)
#         headers = reader.fieldnames or []
#
#         time_col = resolve_column(headers, ["GMT_Time"], r"UTC.?time")
#         depth_col = resolve_column(headers, ["depth_m", "depth", "pressure_bar", "pressure_dbar", "pressure"])
#
#         for row in reader:
#             date, time = parse_utc_to_evl_format(row[time_col], offset)
#             depth_str = row[depth_col]
#             try:
#                 depth = float(depth_str) * depth_multiplier
#                 status = 3
#             except ValueError:
#                 depth = MISSING_DEPTH
#                 status = 0
#             evl_lines.append(f"{date} {time} {depth:.5f} {status}")
#
#     return [EVL_HEADER, str(len(evl_lines))] + evl_lines

##----------------------------------------------------------------------
## New version, allows time offset
# def convert_csv_to_evl(csv_path: str, offset: timedelta = timedelta()) -> list[str]:
#     evl_lines = []
#     with open(csv_path, newline='') as f:
#         reader = csv.DictReader(f)
#         headers = reader.fieldnames or []
#
#         time_col = resolve_column(headers, ["GMT_Time"], r"UTC.?time")
#         depth_col = resolve_column(headers, ["depth_m", "depth", "pressure_bar", "pressure_dbar", "pressure"])
#
#         for row in reader:
#             date, time = parse_utc_to_evl_format(row[time_col], offset)
#             depth_str = row[depth_col]
#             try:
#                 depth = float(depth_str)
#                 status = 3
#             except ValueError:
#                 depth = MISSING_DEPTH
#                 status = 0
#             evl_lines.append(f"{date} {time} {depth:.5f} {status}")
#
#     return [EVL_HEADER, str(len(evl_lines))] + evl_lines


# def convert_csv_to_evl(csv_path: str) -> list[str]:
#     evl_lines = []
#     with open(csv_path, newline='') as f:
#         reader = csv.DictReader(f)
#         headers = reader.fieldnames or []
#
#         # Resolve flexible column names
#         time_col = resolve_column(headers, ["GMT_Time"], r"UTC.?time")
#         depth_col = resolve_column(headers, ["depth_m", "depth", "pressure_bar", "pressure_dbar", "pressure"])
#
#         for row in reader:
#             date, time = parse_utc_to_evl_format(row[time_col])
#             depth_str = row[depth_col]
#             try:
#                 depth = float(depth_str)
#                 status = 3
#             except ValueError:
#                 depth = MISSING_DEPTH
#                 status = 0
#             evl_lines.append(f"{date} {time} {depth:.5f} {status}")
#
#     return [EVL_HEADER, str(len(evl_lines))] + evl_lines



# import csv
# from datetime import datetime
#
# EVL_HEADER = "EVBD 3 3.00.41"
# MISSING_DEPTH = -10000.99000
#
# def parse_time(utc_str: str) -> tuple[str, str]:
#     dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
#     date = dt.strftime("%Y%m%d")
#     time = dt.strftime("%H%M%S") + f"{dt.microsecond // 100:04d}"
#     return date, time
#
# def convert_csv_to_evl(csv_path: str) -> list[str]:
#     evl_lines = []
#     with open(csv_path, newline='') as f:
#         reader = csv.DictReader(f)
#         for row in reader:
#             date, time = parse_time(row["GMT_Time"])
#             depth_str = row["pressure_bar"]
#             try:
#                 depth = float(depth_str)
#                 status = 3  # default to "good"
#             except ValueError:
#                 depth = MISSING_DEPTH
#                 status = 0  # "none"
#             evl_lines.append(f"{date} {time} {depth:.5f} {status}")
#     return [EVL_HEADER, str(len(evl_lines))] + evl_lines