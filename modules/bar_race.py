"""Comparison bar-race — 2-4 horizontal bars grow to their values with live counters.
Great for news/finance comparisons (military spend, GDP, oil reserves). Cheap PIL, $0.

    from modules.bar_race import make_bar_race
    make_bar_race([("USA", 877), ("China", 292), ("Russia", 86)], "bars.mp4",
                  title="MILITARY SPENDING", prefix="$", suffix="B", size=(704, 1280))
"""
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
    from modules.thumbnail_pro import _font as pf
    return pf(size, "news")


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _outline(d, xy, text, fnt, fill, ow, oc=(12, 14, 20)):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=oc)
    d.text((x, y), text, font=fnt, fill=fill)


def make_bar_race(items, out_path, title="", duration=3.5, size=(704, 1280),
                  accent="#FF3131", prefix="", suffix="", fps=30, bg_image=None):
    """items: list of (label, value). Bars grow to value (sorted desc), values count up."""
    from PIL import Image, ImageDraw
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)
    items = sorted([(str(l), float(v)) for l, v in items], key=lambda x: -x[1])[:4]
    if not items:
        return None
    maxv = max(v for _, v in items) or 1.0

    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((l, t, l + W, t + H))
        bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 12, 18, 165))).convert("RGB")
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 16, 22))

    margin = int(W * 0.07)
    tf = _font(int(W * 0.06)); lf = _font(int(W * 0.05)); vf = _font(int(W * 0.052))
    bw_max = W - margin * 2
    bar_h = int(H * 0.07); gap = int(H * 0.06)
    top = int(H * 0.32)
    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="bars_"))
    try:
        for i in range(n):
            e = _ease(i / (n - 1))
            frame = bg.copy()
            d = ImageDraw.Draw(frame, "RGBA")
            if title:
                tt = str(title).upper(); tw = d.textlength(tt, font=tf)
                _outline(d, ((W - tw) / 2, int(H * 0.2)), tt, tf, (255, 255, 255), max(3, int(W * 0.005)))
                d.rectangle([(W - int(W * 0.14)) // 2, int(H * 0.2) + int(W * 0.075),
                             (W + int(W * 0.14)) // 2, int(H * 0.2) + int(W * 0.088)], fill=ac + (255,))
            for k, (lab, val) in enumerate(items):
                y = top + k * (bar_h + gap)
                cur = val * e
                bw = int(bw_max * (val / maxv) * e)
                col = ac if k == 0 else (96, 108, 120)
                d.rounded_rectangle([margin, y, margin + bw_max, y + bar_h], radius=bar_h // 2, fill=(255, 255, 255, 26))
                d.rounded_rectangle([margin, y, margin + max(bar_h, bw), y + bar_h], radius=bar_h // 2, fill=col + (255,))
                _outline(d, (margin + int(W * 0.01), y - int(bar_h * 0.85)), lab.upper(), lf, (255, 255, 255), 3)
                valtxt = f"{prefix}{cur:,.0f}{suffix}"
                vw = d.textlength(valtxt, font=vf)
                _outline(d, (min(margin + max(bar_h, bw) + int(W * 0.02), W - margin - vw), y + (bar_h - vf.size) // 2),
                         valtxt, vf, (255, 255, 255), 3)
            frame.save(tmp / f"f{i:05d}.png")
        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 8000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_bar_race([("USA", 877), ("China", 292), ("Russia", 86), ("India", 74)],
                  "output/bars_demo.mp4", title="Military Spending", prefix="$", suffix="B", size=(704, 1280))
    print("wrote output/bars_demo.mp4")
