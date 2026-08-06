"""Animated stat counter — a big number rolling up with a label. Cheap MoviePy/PIL, $0.
Universal punch for news + finance: "$2.4B", "40%", "3.4M TONS". Concrete numbers drive
views/saves 3-5x over vague claims (competitor research).

    from modules.stat_counter import make_stat_clip, extract_stat
    make_stat_clip(2.4, "BILLION IN TRADE", "stat.mp4", prefix="$", suffix="B", size=(704, 1280))
    s = extract_stat("Trade hit $2.4 billion this year")   # -> (2.4, "$", "B", "...") or None
"""
import math
import re
import subprocess
import tempfile
from pathlib import Path


def _ff():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _font(size):
    from modules.thumbnail_pro import _font as pf   # reuse Impact/bold resolver
    return pf(size, "news")


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _ease(t):
    return 1 - (1 - max(0.0, min(1.0, t))) ** 3     # ease-out: fast then settle


def _fmt(v, decimals):
    return f"{v:,.{decimals}f}" if decimals > 0 else f"{int(round(v)):,}"


def _outline(d, xy, text, fnt, fill, outline, ow):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=outline)
    d.text((x, y), text, font=fnt, fill=fill)


def extract_stat(text):
    """Best-effort: pull a headline number → (value, prefix, suffix, label) or None."""
    if not text:
        return None
    m = re.search(r'\$\s?([\d,.]+)\s*(trillion|billion|million|bn|bil|m|k)?', text, re.I)
    if m:
        val = float(m.group(1).replace(",", ""))
        suf = {"trillion": "T", "billion": "B", "bn": "B", "bil": "B",
               "million": "M", "m": "M", "k": "K"}.get((m.group(2) or "").lower(), "")
        return (val, "$", suf, "THE NUMBER")
    m = re.search(r'([\d,.]+)\s*%', text)
    if m:
        return (float(m.group(1).replace(",", "")), "", "%", "THE NUMBER")
    m = re.search(r'([\d,.]+)\s*(trillion|billion|million)\s+([a-z]+)', text, re.I)
    if m:
        suf = {"trillion": "T", "billion": "B", "million": "M"}.get(m.group(2).lower(), "")
        return (float(m.group(1).replace(",", "")), "", suf, m.group(3).upper())
    return None


def make_stat_clip(value, label, out_path, duration=3.0, size=(704, 1280),
                   accent="#FF3131", prefix="", suffix="", fps=30, bg_image=None, decimals=None):
    """Render a number counting up from 0 → value with a label. Returns out_path or None."""
    from PIL import Image, ImageDraw, ImageFilter
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    value = float(value)
    if decimals is None:
        decimals = 1 if abs(value - round(value)) > 1e-9 else 0

    # background: hero image darkened, or a deep ground
    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((l, t, l + W, t + H))
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 18, 26))
    bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (6, 10, 15, 150))).convert("RGB")

    labf = _font(int(W * 0.058))
    ny = int(H * 0.36)
    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="stat_"))
    try:
        for i in range(n):
            t = i / (n - 1)
            cur = value * _ease(t)
            pop = 1.0 + (0.06 * math.sin(min(1.0, (t - 0.85) / 0.15) * math.pi) if t > 0.85 else 0.0)
            num = f"{prefix}{_fmt(cur, decimals)}{suffix}"
            nf = _font(int(W * 0.20 * pop))

            frame = bg.copy()
            d = ImageDraw.Draw(frame, "RGBA")
            tw = d.textlength(num, font=nf)
            nx = (W - tw) / 2
            # soft shadow
            sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(sh).text((nx + 5, ny + 7), num, font=nf, fill=(0, 0, 0, 190))
            frame = Image.alpha_composite(frame.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(9))).convert("RGB")
            d = ImageDraw.Draw(frame, "RGBA")
            _outline(d, (nx, ny), num, nf, (255, 255, 255), (12, 14, 20), max(4, int(W * 0.007)))
            # accent underline
            uw = int(W * 0.24)
            uy = ny + int(W * 0.23)
            d.rectangle([(W - uw) // 2, uy, (W + uw) // 2, uy + int(W * 0.016)], fill=ac + (255,))
            # label
            lab = str(label).upper()
            lw = d.textlength(lab, font=labf)
            _outline(d, ((W - lw) / 2, uy + int(W * 0.03)), lab, labf, (255, 255, 255), (12, 14, 20), 3)
            frame.save(tmp / f"f{i:05d}.png")

        out_path = str(out_path)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 8000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_stat_clip(2.4, "Billion in Trade", "output/stat_demo.mp4", prefix="$", suffix="B", size=(704, 1280))
    print("wrote output/stat_demo.mp4")
