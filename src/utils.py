# src/utils.py

from datetime import datetime, timedelta
import re

def parse_utc_to_evl_format(utc_str: str, offset: timedelta = timedelta()) -> tuple[str, str]:
    """
    Parses an ISO 8601 UTC timestamp (e.g. 2024-09-07T15:13:42Z) and returns (date, time) in EVL format.
    """
    try:
        # Strip trailing Z if present
        if utc_str.endswith("Z"):
            utc_str = utc_str[:-1]
        dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%S") + offset
    except ValueError as e:
        raise ValueError(f"Invalid UTC timestamp: {utc_str}") from e

    date = dt.strftime("%Y%m%d")
    time = dt.strftime("%H%M%S") + f"{dt.microsecond // 100:04d}"
    return date, time

# def parse_utc_to_evl_format(utc_str: str, offset: timedelta = timedelta()) -> tuple[str, str]:
#     dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S") + offset
#     date = dt.strftime("%Y%m%d")
#     time = dt.strftime("%H%M%S") + f"{dt.microsecond // 100:04d}"
#     return date, time

def parse_offset_string(offset_str: str) -> timedelta:
    """
    Parses a time offset string in [+/-]hh:mm:ss format into a timedelta.
    """
    match = re.fullmatch(r"([+-])?(\d{1,2}):(\d{2}):(\d{2})", offset_str.strip())
    if not match:
        raise ValueError("Invalid offset format. Use [+/-]hh:mm:ss")

    sign, hh, mm, ss = match.groups()
    delta = timedelta(hours=int(hh), minutes=int(mm), seconds=int(ss))
    return delta if sign != "-" else -delta


from datetime import datetime

# def unix_to_time_utc(ts: str) -> str:
#     """
#     Converts a UNIX timestamp string (e.g. '1757092660')
#     into 'yyyymmdd HHMMSS' format.
#     """
#     try:
#         ts_int = int(float(ts))  # handles "1757092660.0"
#     except ValueError:
#         raise ValueError(f"Invalid UNIX timestamp: {ts}")
#
#     dt = datetime.utcfromtimestamp(ts_int)
#     return dt.strftime("%Y%m%d %H%M%S")
def unix_to_time_utc(ts: str) -> str:
    """
    Converts a UNIX timestamp string (e.g. '1757092660')
    into 'yyyymmdd HHMMSS' format.
    """
    try:
        ts_int = int(float(ts))
    except ValueError:
        raise ValueError(f"Invalid UNIX timestamp: {ts}")

    dt = datetime.utcfromtimestamp(ts_int)
    return dt.strftime("%Y%m%d %H%M%S")