# import re

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

# def parse_utc_to_evl_format(utc_str: str, offset_hours: float = 0.0) -> tuple[str, str]:
#     """
#     Converts UTC timestamp string to EVL date and time format, applying optional hour offset.
#     Returns (CCYYMMDD, HHmmSSssss)
#     """
#     dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
#     dt += timedelta(hours=offset_hours)
#     date = dt.strftime("%Y%m%d")
#     time = dt.strftime("%H%M%S") + f"{dt.microsecond // 100:04d}"
#     return date, time
#
# def parse_utc_to_evl_format(utc_str: str) -> tuple[str, str]:
#     dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
#     date = dt.strftime("%Y%m%d")
#     time = dt.strftime("%H%M%S") + f"{dt.microsecond // 100:04d}"
#     return date, time


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