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


import tempfile


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _size(path):
    from moviepy import VideoFileClip
    with VideoFileClip(str(path)) as c:
        return int(c.w), int(c.h)


def _make_badge_png(label, accent, H, out):
    """A 'BREAKING' pill with a white live-dot → transparent PNG. Returns (path, w, h)."""
    from PIL import Image, ImageDraw
    from modules.thumbnail_pro import _font
    fs = int(H * 0.028); f = _font(fs, "news"); pad = int(H * 0.013)
    txt = str(label).upper()
    tw = ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(txt, font=f)
    dot = int(fs * 0.6)
    w = int(pad * 2 + dot + pad * 0.6 + tw); h = int(fs + pad * 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=_hex(accent) + (255,))
    cy = h // 2
    d.ellipse([pad, cy - dot // 2, pad + dot, cy + dot // 2], fill=(255, 255, 255, 255))
    d.text((pad + dot + int(pad * 0.6), (h - fs) // 2 - int(fs * 0.1)), txt, font=f, fill=(255, 255, 255, 255))
    img.save(out)
    return out, w, h


def _make_ticker_png(text, accent, W, H, out):
    """A transparent strip: 'LIVE • <text> • <text>' for a bottom scrolling ticker."""
    from PIL import Image, ImageDraw
    from modules.thumbnail_pro import _font
    fs = int(H * 0.026); f = _font(fs, "default")
    body = f"   {text}   •   {text}   •   {text}   "
    tag = "LIVE"
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    tagw = tmp.textlength(tag, font=f); bw = tmp.textlength(body, font=f)
    pad = int(H * 0.012); h = int(fs + pad * 2)
    tagbox = int(tagw + pad * 2)
    w = int(tagbox + bw + pad)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, tagbox, h], fill=_hex(accent) + (255,))
    d.text((pad, (h - fs) // 2 - int(fs * 0.1)), tag, font=f, fill=(255, 255, 255, 255))
    d.text((tagbox + pad, (h - fs) // 2 - int(fs * 0.1)), body, font=f, fill=(240, 245, 250, 255))
    img.save(out)
    return out, w, h


def add_news_overlays(in_path, out_path, label="BREAKING", accent="#FF3131", progress=True, audio=True):
    """One pass: a BREAKING badge (top-left) + a progress bar. Returns out_path or None."""
    d = _dur(in_path)
    if d <= 0:
        return None
    try:
        W, H = _size(in_path)
    except Exception:
        return None
    work = Path(tempfile.mkdtemp(prefix="ov_"))
    try:
        inputs = ["-i", str(in_path)]; filters = []; last = "0:v"; idx = 1
        if label:
            badge, _bw, _bh = _make_badge_png(label, accent, H, str(work / "badge.png"))
            inputs += ["-i", badge]
            m = int(H * 0.03)
            filters.append(f"[{last}][{idx}:v]overlay={m}:{m}[b]"); last = "b"; idx += 1
        if progress:
            h = max(5, H // 150); col = "0x" + str(accent).lstrip("#")
            filters.append(f"[{last}]drawbox=x=0:y=ih-{h}:w=iw:h={h}:color=white@0.18:t=fill,"
                           f"drawbox=x=0:y=ih-{h}:w='iw*t/{d:.3f}':h={h}:color={col}@1.0:t=fill[v]")
            last = "v"
        cmd = [_ff(), "-y"] + inputs
        if filters:
            cmd += ["-filter_complex", ";".join(filters), "-map", f"[{last}]"]
        else:
            cmd += ["-map", "0:v"]
        cmd += (["-map", "0:a?", "-c:a", "aac", "-b:a", "160k"] if audio else ["-an"])
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
        subprocess.run(cmd, capture_output=True, text=True)
        return str(out_path) if Path(out_path).exists() and Path(out_path).stat().st_size > 10000 else None
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def add_ticker(in_path, out_path, text, accent="#FF3131", audio=True, speed=0.16):
    """A scrolling bottom ticker (LIVE tag + text). Returns out_path or None."""
    d = _dur(in_path)
    if d <= 0 or not text:
        return None
    try:
        W, H = _size(in_path)
    except Exception:
        return None
    work = Path(tempfile.mkdtemp(prefix="tick_"))
    try:
        strip, sw, sh = _make_ticker_png(text, accent, W, H, str(work / "strip.png"))
        by = H - sh - max(5, H // 150) - 2
        px = int(W * max(0.06, speed))
        # dark bar behind + scrolling strip on top
        fc = (f"[0:v]drawbox=x=0:y={by}:w=iw:h={sh}:color=black@0.55:t=fill[bar];"
              f"[bar][1:v]overlay=x='W-mod(t*{px}\\,W+{sw})':y={by}[v]")
        cmd = [_ff(), "-y", "-i", str(in_path), "-i", strip, "-filter_complex", fc, "-map", "[v]"]
        cmd += (["-map", "0:a?", "-c:a", "aac", "-b:a", "160k"] if audio else ["-an"])
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
        subprocess.run(cmd, capture_output=True, text=True)
        return str(out_path) if Path(out_path).exists() and Path(out_path).stat().st_size > 10000 else None
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def add_sfx(in_path, out_path, specs, audio=True):
    """Mix short SFX (risers/whooshes) into the video's audio at set times.
    specs: list of (sfx_path, start_seconds, volume). Returns out_path or None."""
    specs = [(p, s, v) for (p, s, v) in specs if p and Path(p).exists()]
    if not specs:
        return None
    inputs = ["-i", str(in_path)]
    parts, labels = [], []
    for k, (p, start, vol) in enumerate(specs):
        inputs += ["-i", str(p)]
        ms = int(max(0.0, start) * 1000)
        parts.append(f"[{k+1}:a]adelay={ms}|{ms},volume={vol}[s{k}]")
        labels.append(f"[s{k}]")
    fc = ";".join(parts) + ";" + "[0:a]" + "".join(labels) + f"amix=inputs={len(specs)+1}:normalize=0[a]"
    cmd = [_ff(), "-y"] + inputs + ["-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(out_path)]
    subprocess.run(cmd, capture_output=True, text=True)
    return str(out_path) if Path(out_path).exists() and Path(out_path).stat().st_size > 10000 else None
