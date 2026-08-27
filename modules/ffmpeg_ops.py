"""
FFmpeg for the operations MoviePy is slowest at.

Measured on this machine, on our own clips:

    concat two parts    moviepy 48.9s   ffmpeg 0.2s    209x
    mux voice onto vid  moviepy  6.6s   ffmpeg 0.4s     17x
    scale + crop 9:16   moviepy  6.8s   ffmpeg 1.8s    3.8x

The first two are that fast because ffmpeg copies the video stream instead of
decoding and re-encoding it — which also means no generation loss, so the
output is better, not just quicker. MoviePy stays where it earns its keep:
frame-by-frame drawing, masks and compositing.

Every function returns the output path, or None so the caller can fall back.
"""
import json
import subprocess
from pathlib import Path

FF = "ffmpeg"
FP = "ffprobe"


def _run(args) -> bool:
    try:
        r = subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"]
                           + args, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            print(f"[ffmpeg] {(r.stderr or '').strip()[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[ffmpeg] {e}")
        return False


def probe(path) -> dict:
    """{width, height, fps, duration} or {} if unreadable."""
    try:
        r = subprocess.run(
            [FP, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60)
        j = json.loads(r.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        num, _, den = (st.get("r_frame_rate") or "30/1").partition("/")
        return {"width": st.get("width"), "height": st.get("height"),
                "fps": float(num) / float(den or 1),
                "duration": float((j.get("format") or {}).get("duration", 0))}
    except Exception:
        return {}


def concat(parts, out_path):
    """Join clips end to end. Stream-copies when they match, else re-encodes."""
    parts = [Path(p) for p in parts if p and Path(p).exists()]
    if not parts:
        return None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    specs = [probe(p) for p in parts]
    same = all(s.get("width") == specs[0].get("width")
               and s.get("height") == specs[0].get("height")
               for s in specs)
    lst = out.parent / f"_concat_{out.stem}.txt"
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n"
                           for p in parts), encoding="utf-8")
    args = ["-f", "concat", "-safe", "0", "-i", str(lst)]
    args += (["-c", "copy"] if same
             else ["-c:v", "libx264", "-preset", "medium", "-pix_fmt",
                   "yuv420p"])
    ok = _run(args + [str(out)])
    try:
        lst.unlink()
    except OSError:
        pass
    return str(out) if ok and out.exists() else None


def mux_audio(video, audio, out_path, extend_to_audio=True):
    """Put narration on a clip.

    extend_to_audio holds the final frame when the voice runs longer than the
    picture — the alternative is cutting the narration off mid-sentence, which
    is exactly the bug we fixed in attach_voice.
    """
    v, a = Path(video), Path(audio)
    if not (v.exists() and a.exists()):
        return None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    vd = probe(v).get("duration", 0)
    ad = probe(a).get("duration", 0)
    args = ["-i", str(v), "-i", str(a)]
    if extend_to_audio and ad > vd + 0.05:
        pad = ad - vd + 0.3
        args += ["-vf", f"tpad=stop_mode=clone:stop_duration={pad:.2f}",
                 "-c:v", "libx264", "-preset", "medium", "-pix_fmt",
                 "yuv420p"]
    else:
        args += ["-c:v", "copy", "-shortest"]
    args += ["-c:a", "aac", "-b:a", "192k", "-map", "0:v:0", "-map", "1:a:0"]
    ok = _run(args + [str(out)])
    return str(out) if ok and out.exists() else None


def fit_vertical(src, out_path, seconds=None, w=1080, h=1920):
    """Cover-crop any clip to a vertical frame without letterboxing."""
    s = Path(src)
    if not s.exists():
        return None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    args = (["-t", str(seconds)] if seconds else []) + [
        "-i", str(s), "-vf",
        f"scale={w}:-2:force_original_aspect_ratio=increase,crop={w}:{h}",
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"]
    ok = _run(args + [str(out)])
    return str(out) if ok and out.exists() else None
