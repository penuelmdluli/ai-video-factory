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

import numpy as np
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
        """Smooth static layers (deep ground + subtle accent glow + vignette) via numpy —
        no banding, and only a HINT of accent so it reads as clean cinematic dark, not a wash."""
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        acc = np.array(ac, np.float32)
        base = np.empty((H, W, 3), np.float32)
        base[:] = np.array([9.0, 12.0, 17.0])                       # deep near-black ground
        # very subtle accent tint, strongest at the top, gone by mid-frame
        ft = np.clip(1.0 - yy / (H * 0.62), 0.0, 1.0)[..., None] ** 1.5
        base += acc[None, None, :] * 0.05 * ft
        # soft accent glow behind the emoji zone (upper third) — smooth radial
        r = np.sqrt((xx - W * 0.5) ** 2 + (yy - H * 0.34) ** 2)
        glow = np.clip(1.0 - r / (W * 0.55), 0.0, 1.0) ** 2.2
        base += acc[None, None, :] * 0.11 * glow[..., None]
        # smooth vignette: darken from ~55% radius outward
        rc = np.sqrt((xx - W * 0.5) ** 2 + (yy - H * 0.5) ** 2)
        maxr = math.sqrt((W * 0.5) ** 2 + (H * 0.5) ** 2)
        vig = np.clip((rc / maxr - 0.5) / 0.5, 0.0, 1.0) ** 1.6
        base *= (1.0 - 0.5 * vig[..., None])
        return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")

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
