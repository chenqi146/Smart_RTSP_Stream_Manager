import datetime
from typing import List, Tuple


def parse_date(date_str: str) -> datetime.datetime:
    """Parse a date string (YYYY-MM-DD) to datetime at midnight."""
    return datetime.datetime.strptime(date_str, "%Y-%m-%d")


def to_unix(dt: datetime.datetime) -> int:
    """Convert datetime to unix timestamp (seconds)."""
    return int(dt.timestamp())


def generate_day_range(date_str: str) -> Tuple[int, int]:
    """Generate start and end unix timestamps for a given date."""
    start_dt = parse_date(date_str)
    end_dt = start_dt + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    return to_unix(start_dt), to_unix(end_dt)


def generate_segments(
    date_str: str, interval_minutes: int = 10
) -> List[Tuple[int, int]]:
    """Generate (start_ts, end_ts) tuples for the whole day."""
    start_ts, end_ts = generate_day_range(date_str)
    interval = interval_minutes * 60

    segments = []
    current_start = start_ts
    while current_start <= end_ts:
        current_end = min(current_start + interval - 1, end_ts)
        segments.append((current_start, current_end))
        current_start += interval
    return segments

