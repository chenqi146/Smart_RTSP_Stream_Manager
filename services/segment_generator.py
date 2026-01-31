from typing import List, Dict

from utils.time_utils import generate_segments
from utils.rtsp_builder import build_segment


def build_segment_tasks(
    date_str: str,
    base_rtsp: str,
    channel: str = "c2",
    interval_minutes: int = 10,
) -> List[Dict]:
    """
    Generate a list of segment task dicts for a full day.
    Each task contains start_ts, end_ts, url.
    """
    segments = generate_segments(date_str, interval_minutes)
    tasks: List[Dict] = []
    for idx, segment in enumerate(segments):
        start_ts, end_ts = segment
        url = build_segment(base_rtsp, channel, segment)
        tasks.append(
            {
                "index": idx,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "rtsp_url": url,
                "status": "pending",
            }
        )
    return tasks

