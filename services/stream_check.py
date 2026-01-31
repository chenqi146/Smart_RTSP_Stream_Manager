import subprocess
from typing import Tuple


def check_rtsp(url: str, timeout: int = 5) -> Tuple[bool, str]:
    """
    Quick RTSP availability check using ffmpeg.
    Returns (ok, stderr_text).
    """
    cmd = [
        "ffmpeg",
        "-rtsp_transport",
        "tcp",
        "-stimeout",
        str(timeout * 1_000_000),  # microseconds
        "-i",
        url,
        "-t",
        "1",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 2)
        return proc.returncode == 0, proc.stderr.decode(errors="ignore")
    except Exception as e:
        return False, str(e)

