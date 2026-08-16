"""
Clean frames — pick the SHARPEST stills out of a video instead of blind
fixed offsets. A card background or thumbnail built on a motion-blurred
frame looks amateur; edge-variance scoring finds the crisp ones.

Usage:
    from modules.clean_frames import sharpest_frames
    picks = sharpest_frames(video_path, out_dir, need=2, samples=10)
    # -> [(frame_path, t_seconds), ...] best first
"""
import subprocess
from pathlib import Path


def _sharpness(p: Path) -> float:
    from PIL import Image, ImageFilter
    import numpy as np
    im = Image.open(p).convert("L").resize((320, 180))
    edges = im.filter(ImageFilter.FIND_EDGES)
    return float(np.asarray(edges, dtype=float).var())


def sharpest_frames(video, out_dir, need: int = 1,
                    samples: int = 10) -> list[tuple[str, float]]:
    """Sample frames across the video, return the `need` sharpest."""
    video, out_dir = Path(video), Path(out_dir)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    try:
        dur = float(r.stdout.strip())
    except Exception:
        dur = 10.0
    out_dir.mkdir(parents=True, exist_ok=True)
    cands = []
    for i in range(samples):
        t = dur * (i + 0.5) / samples
        p = out_dir / f"cand_{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-ss", f"{t:.2f}", "-i", str(video),
                        "-frames:v", "1", "-q:v", "2", str(p)],
                       capture_output=True)
        if p.exists() and p.stat().st_size > 20_000:
            cands.append((_sharpness(p), t, str(p)))
    cands.sort(key=lambda c: -c[0])
    return [(p, t) for _s, t, p in cands[:need]]
