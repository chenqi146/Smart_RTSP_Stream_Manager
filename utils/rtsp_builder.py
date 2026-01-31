from typing import Tuple


def build_rtsp_url(
    base: str,
    channel: str,
    start_ts: int,
    end_ts: int,
    suffix: str = "replay/s1",  # 使用s1主码流（高分辨率）替代s0子码流（低分辨率）
) -> str:
    """
    Build RTSP URL following pattern:
    {base}/{channel}/b{start_ts}/e{end_ts}/{suffix}

    Example base: rtsp://admin:admin123=@192.168.54.227:554
    
    Note: suffix默认使用s1（主码流，高分辨率），如果s1不可用，可以改为s0（子码流，低分辨率）
    """
    base = base.rstrip("/")
    return f"{base}/{channel}/b{start_ts}/e{end_ts}/{suffix}"


def build_segment(
    base: str, channel: str, segment: Tuple[int, int], suffix: str = "replay/s1"  # 使用s1主码流（高分辨率）
) -> str:
    """Helper to build url for a (start_ts, end_ts) tuple."""
    start_ts, end_ts = segment
    return build_rtsp_url(base, channel, start_ts, end_ts, suffix)

