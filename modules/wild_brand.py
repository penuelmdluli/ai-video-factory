"""WILD MINDS branding overlay — a badge (emoji + name) top-center and FOLLOW FOR MORE at the
bottom, scaled to the video width. Reusable across the animal pipeline."""
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

from modules.emoji_util import render_emoji
from modules.thumbnail_pro import _font


def _probe_size(path):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run([ff, "-i", path], capture_output=True, text=True)
    m = re.search(r"(\d{2,4})x(\d{2,4})", r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (720, 1280)


def brand_video(src, out, name="WILD MINDS", emoji="\U0001F981", follow=True):
    """Overlay the badge (+ optional FOLLOW FOR MORE prompt) onto `src`, write to `out`. Returns out."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    W, H = _probe_size(src)
    work = Path(out).parent

    fs = max(20, int(W * 0.047))
    f = _font(fs, "news")
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = probe.textlength(name, font=f)
    em = render_emoji(emoji, px=int(fs * 1.25))
    esz = int(fs * 1.15)
    pad, gap = int(fs * 0.65), int(fs * 0.35)
    w = int(pad * 2 + (esz + gap if em else 0) + tw)
    h = int(fs * 1.8)
    badge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=(12, 14, 20, 205))
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, outline=(255, 255, 255, 60), width=2)
    x = pad
    if em:
        em = em.resize((esz, esz), Image.LANCZOS)
        badge.paste(em, (x, (h - esz) // 2), em)
        x += esz + gap
    d.text((x, (h - fs) // 2 - 2), name, font=f, fill=(255, 255, 255, 255))
    bp = work / "_brand_badge.png"
    badge.save(bp)

    hf = _font(max(18, int(W * 0.039)), "news")
    handle = "FOLLOW FOR MORE"
    hb = Image.new("RGBA", (W, int(fs * 2)), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hb)
    tw2 = hd.textlength(handle, font=hf)
    hx = int((W - tw2) // 2)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            hd.text((hx + dx, 14 + dy), handle, font=hf, fill=(0, 0, 0, 220))
    hd.text((hx, 14), handle, font=hf, fill=(255, 255, 255, 255))
    hbp = work / "_brand_handle.png"
    hb.save(hbp)

    if follow:
        fc = (f"[0:v][1:v]overlay=(W-w)/2:{int(H*0.03)}[a];[a][2:v]overlay=0:H-{int(H*0.08)}[v]")
        ins = ["-i", src, "-i", str(bp), "-i", str(hbp)]
    else:
        fc = f"[0:v][1:v]overlay=(W-w)/2:{int(H*0.03)}[v]"
        ins = ["-i", src, "-i", str(bp)]
    subprocess.run([ff, "-y", *ins, "-filter_complex", fc,
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", out], capture_output=True)
    return out
