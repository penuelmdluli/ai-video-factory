"""Quote card — a styled reveal of a quote + attribution. News / motivation. Cheap PIL, $0.

    from modules.quote_card import make_quote_card
    make_quote_card("We will not back down.", "A. Leader", "quote.mp4", size=(704, 1280))
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


def _font(size, kind="news"):
    from modules.thumbnail_pro import _font as pf
    return pf(size, kind)


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _outline(d, xy, text, fnt, rgba, ow, oc=(12, 14, 20)):
    x, y = xy
    a = rgba[3] if len(rgba) > 3 else 255
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=fnt, fill=(oc[0], oc[1], oc[2], a))
    d.text((x, y), text, font=fnt, fill=rgba)


def make_quote_card(quote, attribution, out_path, duration=3.5, size=(704, 1280),
                    accent="#FF3131", bg_image=None, fps=30):
    """Render a quote fading/rising in with a big accent quotation mark + attribution."""
    from PIL import Image, ImageDraw
    W, H = int(size[0]), int(size[1])
    ac = _hex(accent)

    try:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((l, t, l + W, t + H))
        bg = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 12, 18, 185))).convert("RGB")
    except Exception:
        bg = Image.new("RGB", (W, H), (11, 16, 22))

    dmy = ImageDraw.Draw(bg)
    fs = int(W * 0.085); font = _font(fs, "default")

    def wrap(fnt):
        lines, cur = [], []
        for w in str(quote).split():
            if dmy.textlength(" ".join(cur + [w]), font=fnt) <= W * 0.84 or not cur:
                cur.append(w)
            else:
                lines.append(" ".join(cur)); cur = [w]
        if cur:
            lines.append(" ".join(cur))
        return lines

    lines = wrap(font)
    while len(lines) > 6 and fs > int(W * 0.05):
        fs -= int(W * 0.006); font = _font(fs, "default"); lines = wrap(font)
    lh = int(fs * 1.22)
    qmark = _font(int(W * 0.34), "news")
    attf = _font(int(W * 0.045), "news")
    total = lh * len(lines)
    y0 = (H - total) // 2
    ow = max(3, int(fs * 0.05))

    n = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="quote_"))
    try:
        for i in range(n):
            t = i / (n - 1)
            frame = bg.copy()
            d = ImageDraw.Draw(frame, "RGBA")
            # big accent quotation mark
            qa = int(220 * _ease(t / 0.3))
            d.text((int(W * 0.06), int(y0 - W * 0.26)), "“", font=qmark, fill=ac + (qa,))
            # quote lines fade + rise, staggered
            for li, ln in enumerate(lines):
                p = _ease((t - 0.12 - li * 0.08) / 0.3)
                if p <= 0:
                    continue
                a = int(255 * p); yo = int((1 - p) * fs * 0.4)
                lw = d.textlength(ln, font=font)
                _outline(d, ((W - lw) / 2, y0 + li * lh - yo), ln, font, (255, 255, 255, a), ow)
            # attribution
            pa = _ease((t - 0.55) / 0.3)
            if pa > 0:
                att = f"— {str(attribution).upper()}"
                aw = d.textlength(att, font=attf)
                d.rectangle([(W - int(W * 0.12)) // 2, y0 + total + int(H * 0.02),
                             (W + int(W * 0.12)) // 2, y0 + total + int(H * 0.028)], fill=ac + (int(255 * pa),))
                _outline(d, ((W - aw) / 2, y0 + total + int(H * 0.045)), att, attf, (255, 255, 255, int(255 * pa)), 3)
            frame.save(tmp / f"f{i:05d}.png")
        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ff(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path], capture_output=True, text=True)
        return out_path if Path(out_path).exists() and Path(out_path).stat().st_size > 8000 else None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    make_quote_card("The world's trade runs through this water.", "Analyst",
                    "output/quote_demo.mp4", size=(704, 1280))
    print("wrote output/quote_demo.mp4")
