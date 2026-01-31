import subprocess
from pathlib import Path
from typing import Optional, Tuple


def probe_rtsp(rtsp_url: str, timeout: int = 5) -> Tuple[bool, str]:
    """
    Quick probe to ensure RTSP is readable before starting long-running HLS.
    Returns (ok, stderr_text).
    """
    cmd = [
        "ffmpeg",
        "-rtsp_transport",
        "tcp",
        "-stimeout",
        str(timeout * 1_000_000),
        "-i",
        rtsp_url,
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


def start_hls(
    rtsp_url: str,
    output_dir: Path,
    stream_name: str = "stream",
    segment_time: int = 2,
) -> Optional[subprocess.Popen]:
    """
    Start FFmpeg to pull RTSP and output HLS playlist.
    Returns Popen process if started successfully.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    m3u8_path = output_dir / f"{stream_name}.m3u8"

    # 兼容性更高的转码：只输出视频轨，强制 H.264 baseline，固定 GOP/keyframe，避免 HEVC/裸流导致黑屏
    cmd = [
        "ffmpeg",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-analyzeduration",
        "100000000",
        "-probesize",
        "100000000",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-an",                  # 仅视频，避免音频问题
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "baseline",
        "-level",
        "3.1",
        "-g",
        "50",                   # GOP
        "-keyint_min",
        "50",
        "-sc_threshold",
        "0",
        "-force_key_frames",
        "expr:gte(t,n_forced*2)",   # 每2秒关键帧
        "-b:v",
        "1500k",
        "-max_muxing_queue_size",
        "1024",
        "-f",
        "hls",
        "-hls_time",
        str(segment_time),
        "-hls_list_size",
        "6",
        "-hls_flags",
        "delete_segments+program_date_time",
        "-hls_segment_type",
        "mpegts",
        "-hls_segment_filename",
        str(output_dir / f"{stream_name}%03d.ts"),
        str(m3u8_path),
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc
    except FileNotFoundError:
        # ffmpeg not installed
        return None


def stop_hls(proc: subprocess.Popen) -> None:
    """Terminate ffmpeg process."""
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

