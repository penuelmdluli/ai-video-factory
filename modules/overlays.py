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
    try:
        W, H = _size(in_path)
    except Exception:
        return None
    col = "0x" + str(accent).lstrip("#")
    h = max(4, int(height))
    # drawbox w=f(t) does NOT animate in this ffmpeg build — slide a red bar in via overlay
    # (x goes from -W to 0, so the visible width grows iw*t/d, a real progress bar).
    fc = (f"[0:v]drawbox=x=0:y=ih-{h}:w=iw:h={h}:color=white@0.18:t=fill[bt];"
          f"[bt][1:v]overlay=x='-(w-w*t/{d:.3f})':y={H - h}[v]")
    cmd = [_ff(), "-y", "-i", str(in_path),
           "-f", "lavfi", "-i", f"color={col}:s={W}x{h}:d={d:.3f}",
           "-filter_complex", fc, "-map", "[v]"]
    cmd += (["-map", "0:a?", "-c:a", "aac", "-b:a", "160k"] if audio else ["-an"])
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
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


def _make_watermark_png(handle, H, out):
    from PIL import Image, ImageDraw
    from modules.thumbnail_pro import _font
    fs = int(H * 0.026); f = _font(fs, "default"); txt = "@" + str(handle).lstrip("@")
    tw = ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(txt, font=f)
    w = int(tw + 10); h = int(fs + 14)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            d.text((5 + dx, 6 + dy), txt, font=f, fill=(0, 0, 0, 150))
    d.text((5, 6), txt, font=f, fill=(255, 255, 255, 180))
    img.save(out); return out, w, h


def _make_follow_png(accent, H, out):
    from PIL import Image, ImageDraw
    from modules.thumbnail_pro import _font
    fs = int(H * 0.030); f = _font(fs, "news"); txt = "FOLLOW"
    tw = ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(txt, font=f)
    pad = int(H * 0.014); tri = int(fs * 0.7)
    w = int(pad * 2 + tri + pad * 0.5 + tw); h = int(fs + pad * 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=_hex(accent) + (255,))
    cy = h // 2
    d.polygon([(pad, cy - tri // 2), (pad, cy + tri // 2), (pad + tri, cy)], fill=(255, 255, 255, 255))
    d.text((pad + tri + int(pad * 0.5), (h - fs) // 2 - int(fs * 0.08)), txt, font=f, fill=(255, 255, 255, 255))
    img.save(out); return out, w, h


def _make_prompt_png(text, accent, W, H, out):
    from PIL import Image, ImageDraw
    from modules.thumbnail_pro import _font
    fs = int(H * 0.030); f = _font(fs, "news"); txt = str(text).upper()
    tw = ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(txt, font=f)
    pad = int(H * 0.016); tri = int(fs * 0.7)
    w = int(pad * 2 + tri + pad * 0.6 + tw); h = int(fs + pad * 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=int(H * 0.014), fill=(12, 18, 26, 225))
    cy = h // 2; ax = pad
    d.polygon([(ax, cy - tri // 2), (ax + tri, cy - tri // 2), (ax + tri // 2, cy + tri // 2)],
              fill=_hex(accent) + (255,))          # down-arrow toward the comments
    d.text((ax + tri + int(pad * 0.6), (h - fs) // 2 - int(fs * 0.08)), txt, font=f, fill=(255, 255, 255, 255))
    img.save(out); return out, w, h


def add_news_overlays(in_path, out_path, label="BREAKING", accent="#FF3131", progress=True,
                      audio=True, handle="", follow=False, comment_prompt=""):
    """One pass — corners filled: BREAKING badge (top-left) + progress bar (bottom edge) +
    @handle watermark (bottom-left) + animated FOLLOW button (bottom-right, last 4s) +
    comment-bait prompt (last 4s). Returns out_path or None."""
    d = _dur(in_path)
    if d <= 0:
        return None
    try:
        W, H = _size(in_path)
    except Exception:
        return None
    work = Path(tempfile.mkdtemp(prefix="ov_"))
    m = int(H * 0.03); near = max(0.0, d - 4.0)
    try:
        inputs = ["-i", str(in_path)]; filters = []; last = "0:v"; idx = 1
        if label:
            badge, _bw, _bh = _make_badge_png(label, accent, H, str(work / "badge.png"))
            inputs += ["-i", badge]
            filters.append(f"[{last}][{idx}:v]overlay={m}:{m}[s{idx}]"); last = f"s{idx}"; idx += 1
        if progress:
            h = max(5, H // 150); col = "0x" + str(accent).lstrip("#")
            filters.append(f"[{last}]drawbox=x=0:y=ih-{h}:w=iw:h={h}:color=white@0.18:t=fill[trk]")
            inputs += ["-f", "lavfi", "-i", f"color={col}:s={W}x{h}:d={d:.3f}"]
            filters.append(f"[trk][{idx}:v]overlay=x='-(w-w*t/{d:.3f})':y={H - h}[s{idx}]"); last = f"s{idx}"; idx += 1
        if handle:
            wm, _ww, wh = _make_watermark_png(handle, H, str(work / "wm.png"))
            inputs += ["-i", wm]
            filters.append(f"[{last}][{idx}:v]overlay={m}:{H - wh - int(H * 0.02)}[s{idx}]"); last = f"s{idx}"; idx += 1
        if follow:
            fol, _fw, fh = _make_follow_png(accent, H, str(work / "follow.png"))
            inputs += ["-i", fol]
            yb = H - fh - int(H * 0.11)
            filters.append(f"[{last}][{idx}:v]overlay=x=W-w-{m}:y='{yb}+8*sin(t*6)':enable='gte(t,{near:.2f})'[s{idx}]")
            last = f"s{idx}"; idx += 1
        if comment_prompt:
            pr, _pw, _ph = _make_prompt_png(comment_prompt, accent, W, H, str(work / "prompt.png"))
            inputs += ["-i", pr]
            filters.append(f"[{last}][{idx}:v]overlay=x=(W-w)/2:y={int(H * 0.70)}:enable='gte(t,{near:.2f})'[s{idx}]")
            last = f"s{idx}"; idx += 1
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
