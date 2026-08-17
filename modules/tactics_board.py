"""
Tactics board — live-TV-style animated formation analysis, pure Python.

Players are tokens on a broadcast-dark pitch. Positions interpolate between
keyframes (formation shifts LIKE live punditry), arrows draw themselves over
time (runs/passes), zones pulse (press areas, gaps). MoviePy composes the
frames; the reel pipeline adds voice + captions on top.

Usage:
    from modules.tactics_board import Board
    b = Board(players={...}, accent=(255,193,7))
    b.keyframe(0.0, {"gk": (0.5, 0.92), ...})
    b.keyframe(4.0, {...})                      # tokens glide to new shape
    b.arrow(1.0, 3.0, (0.8, 0.75), (0.85, 0.35), label="Frosler overlaps")
    b.zone(2.0, 5.0, (0.25, 0.35, 0.75, 0.55), label="THE GAP")
    b.render("out.mp4", duration=8.0, title="CHIEFS: 5-3-2 -> 4-3-3")
"""
from pathlib import Path

W, H = 1080, 1920
PITCH_TOP, PITCH_BOT = 260, 1720


def _ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)          # smoothstep — broadcast-glide feel


def _font(sz, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(
        f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}", sz)


class Board:
    def __init__(self, players: dict, accent=(255, 193, 7),
                 title: str = "", subtitle: str = ""):
        """players: {pid: {"no": "16", "name": "LEANER"}}"""
        self.players = players
        self.accent = accent
        self.title = title
        self.subtitle = subtitle
        self.keys: list[tuple[float, dict]] = []
        self.annos: list[dict] = []

    def keyframe(self, t: float, positions: dict):
        """positions: {pid: (x_frac 0..1, y_frac 0..1)} — 0,0 = top-left,
        y=0 is the OPPONENT goal (attack points up, like TV)."""
        self.keys.append((t, positions))
        self.keys.sort(key=lambda k: k[0])

    def arrow(self, t0, t1, a, b, color=None, label="", curve=0.0):
        self.annos.append({"type": "arrow", "t0": t0, "t1": t1, "a": a,
                           "b": b, "color": color or self.accent,
                           "label": label, "curve": curve})

    def zone(self, t0, t1, rect, color=(220, 60, 60), label=""):
        self.annos.append({"type": "zone", "t0": t0, "t1": t1,
                           "rect": rect, "color": color, "label": label})

    def ring(self, t0, t1, pid, color=None):
        self.annos.append({"type": "ring", "t0": t0, "t1": t1, "pid": pid,
                           "color": color or (90, 200, 255)})

    def ball(self, waypoints):
        """Animated ball with a comet trail. waypoints: [(t, (fx,fy)), ...] —
        the ball glides through them (passes/shots like a TV replay)."""
        self.annos.append({"type": "ball",
                           "wp": sorted(waypoints, key=lambda w: w[0])})

    def stat(self, t0, t1, text, sub=""):
        """Big broadcast stat stamp that punches in ("2-0 · SEEMA 64'")."""
        self.annos.append({"type": "stat", "t0": t0, "t1": t1,
                           "text": text, "sub": sub})

    # ── geometry ──────────────────────────────────────────────────────────
    def _pos_at(self, t: float) -> dict:
        ks = self.keys
        if not ks:
            return {}
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, p0), (t1, p1) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                u = _ease((t - t0) / max(t1 - t0, 1e-6))
                out = {}
                for pid, xy0 in p0.items():
                    xy1 = p1.get(pid, xy0)
                    out[pid] = (xy0[0] + (xy1[0] - xy0[0]) * u,
                                xy0[1] + (xy1[1] - xy0[1]) * u)
                return out
        return ks[-1][1]

    def _px(self, fx, fy):
        return (int(60 + fx * (W - 120)),
                int(PITCH_TOP + fy * (PITCH_BOT - PITCH_TOP - 120)))

    # ── drawing ───────────────────────────────────────────────────────────
    def _draw_pitch(self, d):
        d.rectangle([0, 0, W, H], fill=(10, 30, 16))
        for i in range(8):                     # mow stripes
            y0 = PITCH_TOP + i * (PITCH_BOT - PITCH_TOP) // 8
            if i % 2 == 0:
                d.rectangle([40, y0, W - 40,
                             y0 + (PITCH_BOT - PITCH_TOP) // 8],
                            fill=(13, 38, 20))
        ln = (255, 255, 255, 90)
        d.rectangle([40, PITCH_TOP, W - 40, PITCH_BOT], outline=ln, width=3)
        my = (PITCH_TOP + PITCH_BOT) // 2
        d.line([40, my, W - 40, my], fill=ln, width=3)
        d.ellipse([W // 2 - 130, my - 130, W // 2 + 130, my + 130],
                  outline=ln, width=3)
        for gy in (PITCH_TOP, PITCH_BOT):
            s = 1 if gy == PITCH_TOP else -1
            d.rectangle([W // 2 - 220, min(gy, gy + s * 170),
                         W // 2 + 220, max(gy, gy + s * 170)],
                        outline=ln, width=3)
            d.rectangle([W // 2 - 110, min(gy, gy + s * 70),
                         W // 2 + 110, max(gy, gy + s * 70)],
                        outline=ln, width=3)

    def _frame(self, t: float):
        from PIL import Image, ImageDraw
        import math
        im = Image.new("RGB", (W, H), (10, 30, 16))
        d = ImageDraw.Draw(im, "RGBA")
        self._draw_pitch(d)

        # header
        d.rectangle([0, 0, W, 200], fill=(10, 10, 12))
        d.text((44, 44), "GENESIS NEWS", font=_font(40),
               fill=(255, 200, 0))
        d.text((44, 100), "TACTICS BOARD", font=_font(26, False),
               fill=(200, 205, 210))
        if self.title:
            tw = d.textlength(self.title, font=_font(34))
            d.text((W - 44 - tw, 60), self.title, font=_font(34),
                   fill=(255, 255, 255))

        pos = self._pos_at(t)

        # zones under tokens
        for a in self.annos:
            if a["type"] == "zone" and a["t0"] <= t <= a["t1"]:
                u = _ease(min(1, (t - a["t0"]) / 0.6))
                pulse = 0.75 + 0.25 * math.sin((t - a["t0"]) * 4)
                x0, y0 = self._px(a["rect"][0], a["rect"][1])
                x1, y1 = self._px(a["rect"][2], a["rect"][3])
                col = (*a["color"], int(70 * u * pulse))
                d.rectangle([x0, y0, x1, y1], fill=col,
                            outline=(*a["color"], int(200 * u)), width=4)
                if a["label"]:
                    lw = d.textlength(a["label"], font=_font(30))
                    d.text(((x0 + x1 - lw) / 2, (y0 + y1) / 2 - 18),
                           a["label"], font=_font(30),
                           fill=(255, 255, 255, int(255 * u)))

        # arrows — draw themselves from a to b over their window
        for a in self.annos:
            if a["type"] == "arrow" and a["t0"] <= t:
                u = _ease(min(1, (t - a["t0"]) /
                              max(a["t1"] - a["t0"], 1e-6)))
                if u <= 0:
                    continue
                ax, ay = self._px(*a["a"])
                bx, by = self._px(*a["b"])
                ex, ey = ax + (bx - ax) * u, ay + (by - ay) * u
                d.line([ax, ay, ex, ey], fill=(*a["color"], 235), width=10)
                ang = math.atan2(ey - ay, ex - ax)
                for s in (-1, 1):
                    d.line([ex, ey,
                            ex - 34 * math.cos(ang + s * 0.5),
                            ey - 34 * math.sin(ang + s * 0.5)],
                           fill=(*a["color"], 235), width=10)
                if a["label"] and u >= 1:
                    lw = d.textlength(a["label"], font=_font(28))
                    d.rounded_rectangle([ex - lw / 2 - 12, ey - 70,
                                         ex + lw / 2 + 12, ey - 26],
                                        radius=10, fill=(10, 10, 12, 220))
                    d.text((ex - lw / 2, ey - 64), a["label"],
                           font=_font(28), fill=(255, 255, 255))

        # player tokens
        for pid, (fx, fy) in pos.items():
            p = self.players.get(pid, {})
            x, y = self._px(fx, fy)
            for a in self.annos:                   # highlight rings
                if a["type"] == "ring" and a["pid"] == pid \
                        and a["t0"] <= t <= a["t1"]:
                    pulse = 8 * abs(math.sin((t - a["t0"]) * 3))
                    d.ellipse([x - 56 - pulse, y - 56 - pulse,
                               x + 56 + pulse, y + 56 + pulse],
                              outline=(*a["color"], 230), width=6)
            d.ellipse([x - 42, y - 42, x + 42, y + 42], fill=self.accent,
                      outline=(255, 255, 255), width=3)
            no = p.get("no", "")
            nw = d.textlength(no, font=_font(32))
            d.text((x - nw / 2, y - 20), no, font=_font(32), fill=(15, 15, 15))
            name = p.get("name", "")
            if name:
                nw = d.textlength(name, font=_font(26))
                d.rounded_rectangle([x - nw / 2 - 12, y + 50,
                                     x + nw / 2 + 12, y + 92], radius=10,
                                    fill=(10, 10, 12, 225))
                d.text((x - nw / 2, y + 57), name, font=_font(26),
                       fill=(255, 255, 255))

        # ball with comet trail
        for a in self.annos:
            if a["type"] != "ball":
                continue
            wp = a["wp"]
            if not wp or t < wp[0][0]:
                continue

            def ball_pos(tt):
                if tt <= wp[0][0]:
                    return wp[0][1]
                for (ta, pa), (tb, pb) in zip(wp, wp[1:]):
                    if ta <= tt <= tb:
                        u = _ease((tt - ta) / max(tb - ta, 1e-6))
                        return (pa[0] + (pb[0] - pa[0]) * u,
                                pa[1] + (pb[1] - pa[1]) * u)
                return wp[-1][1]

            if t <= wp[-1][0] + 0.8:
                for k in range(8):                     # trail
                    tt = t - k * 0.05
                    if tt < wp[0][0]:
                        break
                    bx, by = self._px(*ball_pos(tt))
                    r = 22 - k * 2
                    alpha = max(0, 200 - k * 26)
                    d.ellipse([bx - r, by - r, bx + r, by + r],
                              fill=(255, 255, 255, alpha))
                bx, by = self._px(*ball_pos(t))
                d.ellipse([bx - 22, by - 22, bx + 22, by + 22],
                          fill=(255, 255, 255), outline=(20, 20, 20), width=3)
                d.arc([bx - 22, by - 22, bx + 22, by + 22], 30, 210,
                      fill=(20, 20, 20), width=3)

        # stat stamps — punch in with overshoot, hold, fade
        for a in self.annos:
            if a["type"] != "stat" or not (a["t0"] <= t <= a["t1"]):
                continue
            u_in = _ease(min(1, (t - a["t0"]) / 0.35))
            scale = 1.25 - 0.25 * u_in
            fade = _ease(min(1, (a["t1"] - t) / 0.4))
            alpha = int(255 * u_in * fade)
            big = _font(int(96 * scale))
            tw = d.textlength(a["text"], font=big)
            cy = 760
            d.rounded_rectangle([(W - tw) / 2 - 44, cy - 40,
                                 (W + tw) / 2 + 44, cy + 106], radius=26,
                                fill=(10, 10, 12, min(alpha, 235)))
            d.rectangle([(W - tw) / 2 - 44, cy - 40,
                         (W - tw) / 2 - 32, cy + 106],
                        fill=(*self.accent, alpha))
            d.text(((W - tw) / 2, cy - 30), a["text"], font=big,
                   fill=(255, 255, 255, alpha))
            if a["sub"]:
                sf = _font(34)
                sw2 = d.textlength(a["sub"], font=sf)
                d.text(((W - sw2) / 2, cy + 116), a["sub"], font=sf,
                       fill=(*self.accent, alpha))

        if self.subtitle:
            sw = d.textlength(self.subtitle, font=_font(30))
            d.rounded_rectangle([(W - sw) / 2 - 20, 1760,
                                 (W + sw) / 2 + 20, 1820], radius=14,
                                fill=(10, 10, 12, 220))
            d.text(((W - sw) / 2, 1770), self.subtitle, font=_font(30),
                   fill=(235, 238, 242))
        return im

    def render(self, out_path, duration: float, fps: int = 30) -> str:
        import numpy as np
        from moviepy import VideoClip
        clip = VideoClip(
            lambda t: np.array(self._frame(t)), duration=duration)
        clip.write_videofile(str(out_path), fps=fps, codec="libx264",
                             audio=False, logger=None, preset="medium")
        return str(out_path)
