"""Mzansi Careers brand pack — profile logo + page/channel cover art."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageDraw  # noqa: E402

from modules.motion_kit import _font  # noqa: E402

GREEN = (46, 200, 113)
DARK = (11, 13, 16)
GOLD = (255, 200, 0)
OUT = Path("assets/careers_brand")


def _tick(d, cx, cy, size, colour, width):
    """Upward check mark — reads as 'verified' and as 'growth'."""
    d.line([(cx - size * 0.42, cy + size * 0.02),
            (cx - size * 0.10, cy + size * 0.36),
            (cx + size * 0.46, cy - size * 0.42)],
           fill=colour, width=width, joint="curve")


def logo(path, size=1024):
    im = Image.new("RGB", (size, size), DARK)
    d = ImageDraw.Draw(im, "RGBA")
    m = size * 0.055
    d.rounded_rectangle([m, m, size - m, size - m], radius=int(size * 0.19),
                        fill=(16, 19, 24), outline=GREEN,
                        width=int(size * 0.018))
    # rising bars = careers growing, with the verified tick riding above them
    bw = size * 0.085
    gap = size * 0.048
    base = size * 0.60
    total = 3 * bw + 2 * gap
    bx = (size - total) / 2
    for i, h in enumerate((0.11, 0.17, 0.23)):
        x = bx + i * (bw + gap)
        d.rounded_rectangle([x, base - size * h, x + bw, base],
                            radius=int(size * 0.016),
                            fill=GREEN if i < 2 else GOLD)
    _tick(d, size * 0.50, size * 0.265, size * 0.26, GOLD,
          int(size * 0.050))
    f = _font(int(size * 0.115))
    t = "MZANSI"
    d.text(((size - d.textlength(t, font=f)) / 2, size * 0.665), t,
           font=f, fill=(255, 255, 255))
    f2 = _font(int(size * 0.105))
    t2 = "CAREERS"
    d.text(((size - d.textlength(t2, font=f2)) / 2, size * 0.785), t2,
           font=f2, fill=GREEN)
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(path, quality=96)
    return path


def cover(path, w=2048, h=1152, safe_title=True):
    """YouTube banner geometry: keep everything inside the centre 1235x338."""
    im = Image.new("RGB", (w, h), DARK)
    d = ImageDraw.Draw(im, "RGBA")
    for i in range(h):
        k = i / h
        d.line([(0, i), (w, i)],
               fill=(int(11 + 10 * k), int(13 + 26 * k), int(16 + 18 * k)))
    cx, cy = w // 2, h // 2
    sw, sh = 1235, 338
    d.rounded_rectangle([cx - sw // 2, cy - sh // 2 - 10,
                         cx + sw // 2, cy + sh // 2 + 10],
                        radius=28, fill=(16, 19, 24, 210),
                        outline=(*GREEN, 120), width=4)
    f = _font(104)
    t = "MZANSI CAREERS"
    tw = d.textlength(t, font=f)
    _tick(d, cx - tw / 2 - 96, cy - 78, 92, GOLD, 15)
    d.text((cx - tw / 2, cy - 128), t, font=f, fill=(255, 255, 255))
    f2 = _font(44, False)
    t2 = "Verified SA jobs · learnerships · internships · bursaries"
    d.text((cx - d.textlength(t2, font=f2) / 2, cy - 4), t2, font=f2,
           fill=GREEN)
    f3 = _font(36, False)
    t3 = "Official sources only  ·  You never pay to apply"
    d.text((cx - d.textlength(t3, font=f3) / 2, cy + 62), t3, font=f3,
           fill=(205, 210, 216))
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(path, quality=94)
    return path


if __name__ == "__main__":
    print(logo(OUT / "logo.png"))
    print(cover(OUT / "cover.png"))
