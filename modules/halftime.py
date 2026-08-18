"""
Halftime analysis — the broadcast move: play, slow down, freeze, draw on it.

This is the piece a studio analyst does that a news card cannot: run the clip,
drop to slow motion as the moment builds, freeze on the decisive frame, then
telestrate over the still — spotlight the players, show the run, mark the
space — before releasing back to full speed.

Player positions come from the frame picker's people detection, so the
spotlights land on actual bodies in the frame rather than guessed coordinates.
Nothing here states a statistic; it points at what is visibly on screen.

    clip = analysis_segment(video, freeze_at=6.2, note="...", ...)
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from modules.motion_kit import _font, _ease

GOLD = (255, 200, 0)
CYAN = (60, 220, 255)
RED = (235, 70, 60)
W, H = 1080, 1920


def detect_players(frame_img, max_n=4):
    """Boxes for people visible in the frame, biggest first."""
    import cv2
    arr = cv2.cvtColor(np.array(frame_img), cv2.COLOR_RGB2BGR)
    h, w = arr.shape[:2]
    scale = 700 / max(1, w)
    small = cv2.resize(arr, (int(w * scale), int(h * scale)))
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    found = []
    try:
        rects, weights = hog.detectMultiScale(small, winStride=(8, 8),
                                              padding=(8, 8), scale=1.05)
        for (x, y, bw, bh), wt in zip(rects, weights):
            if wt > 0.3:
                found.append((x / scale, y / scale, bw / scale, bh / scale,
                              float(wt)))
    except Exception as e:
        print(f"[Halftime] detection failed: {e}")
    found.sort(key=lambda b: b[2] * b[3], reverse=True)
    return found[:max_n]


def _ring(d, cx, cy, r, t, colour=CYAN, label=""):
    """A telestration ring that draws itself on, then holds."""
    sweep = int(360 * _ease(min(1.0, t / 0.45)))
    for wdt, alpha in ((9, 255), (18, 70)):
        d.arc([cx - r, cy - r * 0.55, cx + r, cy + r * 0.55],
              start=-90, end=-90 + sweep, fill=(*colour, alpha), width=wdt)
    if label and t > 0.4:
        f = _font(34)
        tw = d.textlength(label, font=f)
        d.rounded_rectangle([cx - tw / 2 - 14, cy - r * 0.55 - 58,
                             cx + tw / 2 + 14, cy - r * 0.55 - 8],
                            radius=10, fill=(*colour, 235))
        d.text((cx - tw / 2, cy - r * 0.55 - 52), label, font=f,
               fill=(8, 10, 12))


def _arrow(d, p0, p1, t, colour=GOLD, width=12):
    """A run/pass arrow that extends over time."""
    u = _ease(min(1.0, t / 0.6))
    x0, y0 = p0
    x1 = x0 + (p1[0] - x0) * u
    y1 = y0 + (p1[1] - y0) * u
    d.line([x0, y0, x1, y1], fill=(*colour, 240), width=width)
    ang = math.atan2(y1 - y0, x1 - x0)
    for s in (2.6, -2.6):
        d.line([x1, y1, x1 + 34 * math.cos(ang + s),
                y1 + 34 * math.sin(ang + s)], fill=(*colour, 240),
               width=width)


def _chrome(d, title, note, t, phase):
    """Persistent studio furniture — bug, phase tag, analyst note."""
    d.rectangle([0, 0, W, 132], fill=(10, 12, 16, 232))
    d.text((34, 30), "GENESIS NEWS", font=_font(40), fill=(255, 255, 255))
    d.text((36, 80), "HALFTIME ANALYSIS", font=_font(24, False), fill=GOLD)
    tag = {"play": "LIVE", "slow": "SLOW MOTION",
           "freeze": "FREEZE", "release": "FULL SPEED"}[phase]
    col = {"play": (120, 220, 150), "slow": CYAN,
           "freeze": GOLD, "release": (120, 220, 150)}[phase]
    tf = _font(28)
    tw = d.textlength(tag, font=tf)
    d.rounded_rectangle([W - tw - 76, 42, W - 30, 96], radius=12,
                        fill=(*col, 235))
    d.text((W - tw - 52, 52), tag, font=tf, fill=(8, 10, 12))
    if note:
        u = _ease(min(1.0, t / 0.4))
        bh = int(150 * u)
        d.rounded_rectangle([28, H - 40 - bh, W - 28, H - 40], radius=18,
                            fill=(10, 12, 16, 238))
        if u > 0.5:
            f = _font(38)
            words, line, lines = note.split(), "", []
            for wd in words:
                trial = f"{line} {wd}".strip()
                if d.textlength(trial, font=f) <= W - 110:
                    line = trial
                else:
                    lines.append(line)
                    line = wd
            lines.append(line)
            for i, ln in enumerate(lines[:2]):
                d.text((56, H - 30 - bh + 26 + i * 48), ln, font=f,
                       fill=(255, 255, 255))
        d.rectangle([28, H - 40 - bh, 34, H - 40], fill=GOLD)
    return d


def _overlay(size, t, phase, title, note, marks):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    if phase == "freeze":
        # dim everything, then punch light back into the marked players
        d.rectangle([0, 0, *size], fill=(6, 8, 12, 120))
        for i, m in enumerate(marks):
            lt = t - 0.25 * i
            if lt <= 0:
                continue
            if m["kind"] == "ring":
                _ring(d, m["x"], m["y"], m["r"], lt, m.get("colour", CYAN),
                      m.get("label", ""))
            elif m["kind"] == "arrow":
                _arrow(d, m["from"], m["to"], lt, m.get("colour", GOLD))
            elif m["kind"] == "zone":
                x0, y0, x1, y1 = m["box"]
                u = _ease(min(1.0, lt / 0.5))
                d.rectangle([x0, y0, x0 + (x1 - x0) * u, y1],
                            fill=(*m.get("colour", RED), 60),
                            outline=(*m.get("colour", RED), 230), width=6)
    _chrome(d, title, note if phase in ("freeze", "slow") else "", t, phase)
    return im


def overlay_clip(size, duration, phase, title, note, marks=()):
    """Transparent animated overlay for one phase of the analysis."""
    from moviepy import VideoClip

    def frame(t):
        return np.array(_overlay(size, t, phase, title, note,
                                 list(marks)).convert("RGB"))

    def mask(t):
        return np.array(_overlay(size, t, phase, title, note,
                                 list(marks)).split()[-1]).astype(float) / 255

    c = VideoClip(frame, duration=duration)
    c.mask = VideoClip(mask, duration=duration, is_mask=True)
    return c
