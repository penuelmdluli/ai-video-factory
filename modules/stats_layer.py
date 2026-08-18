"""
Live stats band — the animated layer that runs while the match footage plays.

The news card already carried a BETWAY LOG strip, but it was painted into the
card artwork: a dead, static row of numbers sitting under moving video. This
replaces that zone with a layer that actually moves — rows stagger in, the
points tick up, the club the story is about pulses, and the band flips to a
focus panel and back while the clip runs.

Everything drawn here comes from the live league table. No placeholder rows,
ever — if the table is unavailable the band simply does not render.

    clip = stats_band(rows, duration=18.0, club="chiefs")
    # composite at (24, 824) — the strip zone the card leaves for it
"""
import numpy as np
from PIL import Image, ImageDraw

from modules.motion_kit import _font, _ease

BAND_W, BAND_H = 1032, 120       # the card's strip zone, minus its margins
BAND_XY = (24, 824)
DARK = (10, 12, 16)
GOLD = (255, 200, 0)
FLIP_EVERY = 7.0                 # seconds per panel


def _panel_log(d, rows, t, club):
    """Top-six table. Rows stagger in, points count up, story club pulses."""
    hf = _font(24)
    d.text((20, 12), "BETWAY LOG", font=hf, fill=GOLD)
    # measured, not guessed — a fixed x had "LIVE" sitting on the wordmark
    d.text((20 + d.textlength("BETWAY LOG", font=hf) + 14, 16), "LIVE",
           font=_font(18), fill=(120, 220, 150))
    shown = rows[:6]
    cw = (BAND_W - 40) // max(1, len(shown))
    for j, r in enumerate(shown):
        u = _ease(min(1.0, max(0.0, (t - 0.15 * j) / 0.45)))
        if u <= 0:
            continue
        cx = 20 + j * cw
        dy = int((1 - u) * 26)          # slides up into place
        hot = club and r.get("team_key") == club
        if hot:
            # steady pulse so the eye lands on the club the story is about
            p = 0.5 + 0.5 * np.sin(t * 3.2)
            d.rounded_rectangle([cx - 8, 42 + dy, cx + cw - 16, BAND_H - 10],
                                radius=10,
                                fill=(255, int(180 + 40 * p), 0))
        fg = (10, 10, 10) if hot else (235, 238, 242)
        fg2 = (10, 10, 10) if hot else (170, 175, 182)
        d.text((cx, 48 + dy), f"{r['rank']} {str(r['name'])[:9]}",
               font=_font(26), fill=fg)
        pts = int(round(r["points"] * min(1.0, (t - 0.15 * j) / 0.9)))
        d.text((cx, 82 + dy), f"{max(0, pts)} pts", font=_font(24, False),
               fill=fg2)


def _panel_focus(d, row, t):
    """One club, big — position, points, games played. Live table only."""
    u = _ease(min(1.0, t / 0.5))
    name = str(row["name"]).upper()
    d.text((20, 12), "TABLE RIGHT NOW", font=_font(24), fill=GOLD)
    d.text((20, 52), name, font=_font(int(46 * u)), fill=(255, 255, 255))
    cells = [(f"{row['rank']}", "POSITION"),
             (f"{row['points']}", "POINTS"),
             (f"{row['played']}", "PLAYED")]
    x = BAND_W - 30
    for val, lab in reversed(cells):
        vf, lf = _font(40), _font(18, False)
        w = max(d.textlength(val, font=vf), d.textlength(lab, font=lf))
        x -= int(w) + 46
        d.text((x, 34), val, font=vf, fill=GOLD)
        d.text((x, 84), lab, font=lf, fill=(170, 175, 182))


def stats_band(rows, duration, club=None, flip=True):
    """A MoviePy clip for the animated band, with alpha. None if no data."""
    if not rows:
        return None
    from moviepy import VideoClip

    focus = next((r for r in rows if r.get("team_key") == club), None)

    def _draw(t):
        im = Image.new("RGBA", (BAND_W, BAND_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle([0, 0, BAND_W, BAND_H], radius=18,
                            fill=(*DARK, 235))
        # panel flip: log -> focus -> log, with a short wipe between
        phase = int(t // FLIP_EVERY) % 2 if (flip and focus) else 0
        local = t - (t // FLIP_EVERY) * FLIP_EVERY
        if phase == 0:
            _panel_log(d, rows, t if t < FLIP_EVERY else local, club)
        else:
            _panel_focus(d, focus, local)
        if local < 0.28 and t > FLIP_EVERY * 0.5:
            # wipe: a gold sweep sells the change instead of a hard cut
            x = int(BAND_W * (local / 0.28))
            d.rectangle([x - 12, 0, x + 12, BAND_H], fill=(*GOLD, 210))
        return im

    def frame(t):
        return np.array(_draw(t).convert("RGB"))

    def mask(t):
        return np.array(_draw(t).split()[-1]).astype(float) / 255.0

    clip = VideoClip(frame, duration=duration)
    clip.mask = VideoClip(mask, duration=duration, is_mask=True)
    return clip
