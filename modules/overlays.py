"""Video overlays applied to a finished clip. Cheap ffmpeg, $0.

add_progress_bar: a thin accent bar filling left→right over the whole video — nudges
watch-to-end, a top Reels/Facebook completion signal.

    from modules.overlays import add_progress_bar
    add_progress_bar("in.mp4", "out.mp4", accent="#FF3131")
"""
import subprocess
from pathlib import Path


def _ff():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _dur(path):
    try:
        from moviepy import VideoFileClip
        with VideoFileClip(str(path)) as c:
            return float(c.duration or 0)
    except Exception:
        return 0.0


def add_progress_bar(in_path, out_path, accent="#FF3131", height=8, audio=True):
    """Re-encode `in_path` with a progress bar burned in at the bottom. Returns out_path
    or None (caller should fall back to a plain copy/encode on None)."""
    d = _dur(in_path)
    if d <= 0:
        return None
    col = "0x" + str(accent).lstrip("#")
    h = max(4, int(height))
    # a faint full-width track + the accent bar whose width grows with time t
    vf = (f"drawbox=x=0:y=ih-{h}:w=iw:h={h}:color=white@0.18:t=fill,"
          f"drawbox=x=0:y=ih-{h}:w='iw*t/{d:.3f}':h={h}:color={col}@1.0:t=fill")
    cmd = [_ff(), "-y", "-i", str(in_path), "-vf", vf,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += (["-c:a", "aac", "-b:a", "160k"] if audio else ["-an"])
    cmd += [str(out_path)]
    subprocess.run(cmd, capture_output=True, text=True)
    return str(out_path) if Path(out_path).exists() and Path(out_path).stat().st_size > 10000 else None
