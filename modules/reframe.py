"""Syndication reframe engine — turn ONE render into every aspect ratio.

One production -> 9:16 (Shorts/Reels/TikTok), 16:9 (YouTube + Facebook in-stream
higher-CPM tier), 1:1 (Facebook/IG feed). Uses a blurred-fill background so no
content is cropped away and it always looks intentional. Zero re-render — this
runs AFTER the source video exists.
"""
import subprocess
from pathlib import Path

def _ff():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"
FF = _ff()

ASPECTS = {
    "9x16": (1080, 1920),   # Shorts, Reels, TikTok, IG Reels
    "16x9": (1920, 1080),   # YouTube long-form, Facebook in-stream video
    "1x1":  (1080, 1080),   # Facebook / Instagram feed
}

def _probe_ar(src):
    out = subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=width,height","-of","csv=p=0:s=x", str(src)],
        capture_output=True, text=True).stdout.strip()
    try:
        w, h = out.split("x")[:2]; return int(w) / int(h)
    except Exception:
        return 16/9

def reframe(src, aspect, out):
    """Reframe src into the given aspect key with a blurred-fill background.
    If the source already matches, it just re-encodes to the exact size."""
    W, H = ASPECTS[aspect]
    src = str(src); out = str(out)
    # blurred cover behind a fully-visible (contained) foreground
    filt = (f"[0:v]split=2[bg][fg];"
            f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},gblur=sigma=24[bgb];"
            f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2:format=auto,fps=30,format=yuv420p[v]")
    cmd = [FF,"-y","-i",src,"-filter_complex",filt,"-map","[v]"]
    # keep audio if present
    has_audio = subprocess.run(["ffprobe","-v","error","-select_streams","a:0",
        "-show_entries","stream=index","-of","csv=p=0", src],
        capture_output=True, text=True).stdout.strip()
    if has_audio:
        cmd += ["-map","0:a","-c:a","aac","-b:a","192k"]
    cmd += ["-c:v","libx264","-preset","veryfast","-crf","20", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("reframe failed: " + r.stderr[-500:])
    return out

def make_aspects(src, outdir, aspects=("9x16","16x9","1x1")):
    """Produce all requested aspect ratios. Returns {aspect: path}."""
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(src).stem
    made = {}
    for a in aspects:
        p = outdir / f"{stem}_{a}.mp4"
        reframe(src, a, p); made[a] = str(p)
    return made
