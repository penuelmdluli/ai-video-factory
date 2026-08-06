"""Procedural ANIMATED backgrounds — $0, offline, unlimited, on-brand.

Drifting bokeh particles + an accent-tinted gradient + a soft glow and dark vignette, so the
foreground keyword/emoji/subtitle always stays crisp. No models, no API, no quota — perfect for a
faceless graphics channel, and it never looks like real footage.

    from modules.motion_bg import make_bg_provider
    bg = make_bg_provider(accent="#FF3131", seed=7)
    frame_img = bg(i, n, W, H, offset=cumulative_frames)   # -> RGB PIL image for frame i
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def make_bg_provider(accent="#FF3131", seed=0, density=40):
    """Return a function f(i, n, W, H, offset=0) -> RGB PIL image of an animated background."""
    ac = _hex(accent)
    rnd = random.Random(seed)
    # particles: x,y in 0..1, radius frac, drift speed, phase, depth (parallax/brightness), accent?
    parts = []
    for _ in range(density):
        parts.append((rnd.random(), rnd.random(), rnd.uniform(0.006, 0.022),
                      rnd.uniform(0.15, 0.55), rnd.random(), rnd.uniform(0.35, 1.0),
                      rnd.random() < 0.45))

    @lru_cache(maxsize=4)
    def _base(W, H):
        """Static layers (gradient + glow + vignette) — built once per size."""
        img = Image.new("RGB", (W, H), (8, 11, 16))
        gd0 = ImageDraw.Draw(img)
        # vertical gradient: a touch of accent up top fading to deep ground (per-row line = fast)
        for y in range(H):
            f = y / H
            r = int(8 + (ac[0] * 0.10) * (1 - f))
            g = int(11 + (ac[1] * 0.10) * (1 - f))
            b = int(16 + (ac[2] * 0.10) * (1 - f) + 6 * (1 - f))
            gd0.line([(0, y), (W, y)], fill=(r, g, b))
        # soft accent glow behind the emoji zone (upper third)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        cx, cy = W // 2, int(H * 0.34)
        for rr in range(int(W * 0.6), 0, -14):
            a = int(20 * (1 - rr / (W * 0.6)))
            gd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=ac + (a,))
        img = Image.alpha_composite(img.convert("RGBA"), glow)
        # dark vignette so edges recede and center text pops
        vg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        vd = ImageDraw.Draw(vg)
        maxr = int((W ** 2 + H ** 2) ** 0.5 / 2)
        for rr in range(maxr, int(maxr * 0.55), -16):
            a = int(120 * (rr - maxr * 0.55) / (maxr * 0.45))
            vd.ellipse([W // 2 - rr, H // 2 - rr, W // 2 + rr, H // 2 + rr], outline=(0, 0, 0, min(150, a)), width=16)
        img = Image.alpha_composite(img, vg)
        return img.convert("RGB")

    def frame(i, n, W, H, offset=0):
        img = _base(W, H).copy()
        d = ImageDraw.Draw(img, "RGBA")
        fi = i + offset
        for (x0, y0, sz, sp, ph, dp, is_ac) in parts:
            # slow upward drift (wraps) + gentle horizontal sway
            y = (y0 - fi * sp * 0.0016) % 1.0
            x = (x0 + 0.015 * math.sin(fi * 0.02 + ph * 6.283)) % 1.0
            r = max(1.0, sz * W * dp)
            tw = 0.55 + 0.45 * math.sin(fi * 0.06 + ph * 6.283)   # twinkle
            a = int(60 * dp * tw)
            col = ac if is_ac else (150, 168, 190)
            d.ellipse([x * W - r, y * H - r, x * W + r, y * H + r], fill=col + (a,))
        return img

    return frame


if __name__ == "__main__":
    bg = make_bg_provider("#E0A400", seed=3)
    bg(10, 90, 540, 960).save("output/motion_bg_frame.png")
    print("wrote output/motion_bg_frame.png")
