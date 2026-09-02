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


def _draw_football(d, cx: float, cy: float, r: float, spin: float = 0.0):
    """An actual football, not a white dot.

    Owner 2026-09-02: "the ball must be a real ball." The old one was a circle
    with a single arc across it, which at 24px reads as a bubble. A ball is
    recognisable from two things and only two: the black pentagon at its centre
    and the seams running off it. Both are drawn here, and the whole panel
    pattern ROTATES with travel, because a ball that slides across a pitch
    without spinning is the thing that makes an animation look cheap.
    """
    import math
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              fill=(252, 252, 252), outline=(18, 18, 20), width=2)

    # Centre pentagon, spinning.
    pent = []
    for k in range(5):
        ang = spin + k * (2 * math.pi / 5) - math.pi / 2
        pent.append((cx + math.cos(ang) * r * 0.42,
                     cy + math.sin(ang) * r * 0.42))
    d.polygon(pent, fill=(22, 22, 26))

    # Seams out to the rim from each pentagon corner.
    for k in range(5):
        ang = spin + k * (2 * math.pi / 5) - math.pi / 2 + math.pi / 5
        d.line([(cx + math.cos(ang) * r * 0.44, cy + math.sin(ang) * r * 0.44),
                (cx + math.cos(ang) * r * 0.96, cy + math.sin(ang) * r * 0.96)],
               fill=(30, 30, 34), width=max(2, int(r * 0.10)))

    # A soft highlight so it reads as a sphere and not a sticker.
    d.ellipse([cx - r * 0.55, cy - r * 0.62, cx - r * 0.05, cy - r * 0.16],
              fill=(255, 255, 255))


class Board:
    def __init__(self, players: dict, accent=(255, 193, 7),
                 title: str = "", subtitle: str = "",
                 club: str = "", opponent: str = ""):
        """players: {pid: {"no": "16", "name": "LEANER"}}

        club/opponent draw the CRESTS. Owner 2026-09-02: "can adding the crest
        in the field for both teams bring the spark?" It can, and the way it
        does is by answering "who is this?" before a word is spoken - the same
        job the crest does on a real broadcast's centre circle. Both are
        optional and a missing badge simply is not drawn.
        """
        self.players = players
        self.accent = accent
        self.title = title
        self.subtitle = subtitle
        self.club = club
        self.opponent = opponent
        self.keys: list[tuple[float, dict]] = []
        self.annos: list[dict] = []

    def keyframe(self, t: float, positions: dict):
        """positions: {pid: (x_frac 0..1, y_frac 0..1)} — 0,0 = top-left,
        y=0 is the OPPONENT goal (attack points up, like TV)."""
        self.keys.append((t, positions))
        self.keys.sort(key=lambda k: k[0])

    def keyframe_balanced(self, t: float, changes: dict,
                          strength: float = 0.35, radius: float = 0.25):
        """Move only `changes` — every OTHER player auto-balances, drifting
        in sympathy with the movers (nearer teammates react more), so the
        whole shape breathes like a real team instead of statues
        (owner 2026-08-17: 'players must auto balance')."""
        import math
        base = dict(self.keys[-1][1]) if self.keys else {}
        new = dict(base)
        deltas = []
        for pid, xy in changes.items():
            old = base.get(pid, xy)
            deltas.append((old, (xy[0] - old[0], xy[1] - old[1])))
            new[pid] = xy
        for pid, xy in base.items():
            if pid in changes:
                continue
            dx = dy = 0.0
            for origin, delta in deltas:
                dist = math.hypot(xy[0] - origin[0], xy[1] - origin[1])
                w = math.exp(-dist / radius) * strength
                dx += delta[0] * w
                dy += delta[1] * w
            new[pid] = (min(.97, max(.03, xy[0] + dx)),
                        min(.97, max(.03, xy[1] + dy)))
        self.keyframe(t, new)

    def arrow(self, t0, t1, a, b, color=None, label="", curve=0.0):
        self.annos.append({"type": "arrow", "t0": t0, "t1": t1, "a": a,
                           "b": b, "color": color or self.accent,
                           "label": label, "curve": curve})

    def triangle(self, t0, t1, a, b, c, label=""):
        """The passing triangle between three men.

        Owner 2026-09-02: "make shape triangle and all that fans want to see."
        He is right that it is the graphic supporters read fastest - a triangle
        is how every coach on television draws a team keeping the ball, and it
        says "these three are connected" in a way three separate arrows do not.

        Drawn as a filled shape at low alpha with a bright edge, so it reads
        underneath the tokens rather than boxing them in.
        """
        self.annos.append({"type": "triangle", "t0": t0, "t1": t1,
                           "pts": [a, b, c], "label": label})

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

    def goal(self, t0, t1, scorer: str = "", assist: str = ""):
        """The moment the move ends in the net.

        Owner 2026-09-02: "when they score a goal let it show THIS IS A GOAL,
        this must be a game, they must feel like they are watching the boys."
        A passing move that simply stops is a diagram; the same move with the
        net bulging is a highlight, and a highlight is what a supporter shares.
        """
        self.annos.append({"type": "goal", "t0": t0, "t1": t1,
                           "scorer": scorer, "assist": assist})

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
    def _crests(self, img):
        """Home crest ghosted into the centre circle, both crests in a VS bar.

        The centre one is faint on purpose - about a tenth opacity. A solid
        badge under eleven tokens and a moving ball is clutter, and the tokens
        are the content; at this weight it reads as turf marking, which is
        exactly how a stadium centre circle looks on camera.
        """
        from PIL import Image
        try:
            from modules.motion_kit import _crest
        except Exception:
            return
        if self.club:
            big = _crest(self.club, 520)
            if big:
                ghost = big.copy()
                ghost.putalpha(ghost.getchannel("A").point(lambda v: int(v * 0.10)))
                cx, cy = self._px(0.5, 0.5)
                img.paste(ghost, (int(cx - ghost.width / 2),
                                  int(cy - ghost.height / 2)), ghost)

    def _matchup(self, img):
        """Both crests in the HEADER, not on the grass.

        The first version put them at y=258, which is inside the top penalty
        area - two badges sitting in the six-yard box, over the pitch markings,
        in the exact space the attacking phase of every move needs. The header
        is where a broadcast puts the fixture, and it is the one band of the
        frame with nothing else competing for it.
        """
        from PIL import ImageDraw
        try:
            from modules.motion_kit import _crest
        except Exception:
            return
        if not (self.club and self.opponent):
            return
        a, b = _crest(self.club, 74), _crest(self.opponent, 74)
        if not (a and b):
            return
        # Sit in the middle of the header, not against the right edge. At
        # W/2+120 and W/2+280 the away badge ended at x=857 and the title is
        # right-aligned to x=1036 - so anything longer than about eleven
        # characters ran straight into it. The title lane is now protected
        # below and the crests keep to their own.
        y = 108
        self._crest_right = int(W / 2 + 90)
        img.paste(a, (int(W / 2 - 70 - a.width / 2), int(y - a.height / 2)), a)
        img.paste(b, (int(W / 2 + 50 - b.width / 2), int(y - b.height / 2)), b)
        dd = ImageDraw.Draw(img, "RGBA")
        f = _font(34)
        w = dd.textlength("V", font=f)
        dd.text((W / 2 - 10 - w / 2, y - 20), "V", font=f,
                fill=(*self.accent, 255))

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
        self._crests(im)
        d = ImageDraw.Draw(im, "RGBA")   # paste() invalidates the old handle

        # header
        d.rectangle([0, 0, W, 200], fill=(10, 10, 12))
        d.text((44, 44), "GENESIS NEWS", font=_font(40),
               fill=(255, 200, 0))
        self._matchup(im)
        d = ImageDraw.Draw(im, "RGBA")
        d.text((44, 100), "TACTICS BOARD", font=_font(26, False),
               fill=(200, 205, 210))
        if self.title:
            # Shrink to fit the space the crests leave. A fixed 34pt title
            # overlapped the badges the moment it grew past "THE MOVE".
            limit = W - 44 - (getattr(self, "_crest_right", 0) + 26)
            size = 34
            while size > 20 and d.textlength(self.title, font=_font(size)) > limit:
                size -= 2
            tw = d.textlength(self.title, font=_font(size))
            d.text((W - 44 - tw, 60), self.title, font=_font(size),
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
                """Where the ball is - struck, not dragged.

                This used _ease() across the whole gap between waypoints, which
                eases IN as well as out: the ball crept away from every player,
                hit full speed halfway, then crept into the next man. That is
                cursor motion, and it is exactly why the owner said it does not
                move like a ball.

                A kicked ball does the opposite - it leaves the boot at its
                fastest and slows under friction, then SITS at the receiver's
                feet until he plays it. So each gap splits: the pass takes the
                first 62% on an ease-OUT curve, and the rest is the ball at
                rest. That pause is the rhythm of a move: strike, travel,
                settle, strike again.
                """
                if tt <= wp[0][0]:
                    return wp[0][1]
                for (ta, pa), (tb, pb) in zip(wp, wp[1:]):
                    if ta <= tt <= tb:
                        span = max(tb - ta, 1e-6)
                        k = min(1.0, (tt - ta) / (span * 0.45))
                        u = 1 - (1 - k) ** 2.2
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
                # Spin from actual SPEED, so it whips off the boot and slows as
                # the ball settles. A ball spinning at a constant rate while
                # sitting still was the other half of what looked wrong.
                px0, py0 = self._px(*ball_pos(max(0.0, t - 0.033)))
                speed = ((bx - px0) ** 2 + (by - py0) ** 2) ** 0.5
                _draw_football(d, bx, by, 24, spin=t * (1.0 + speed * 0.20))

        # GOAL — a white flash, then the word, then who scored it.
        for a in self.annos:
            if a["type"] != "goal" or not (a["t0"] <= t <= a["t1"]):
                continue
            u = (t - a["t0"]) / max(a["t1"] - a["t0"], 1e-6)
            # Flash on the first 12% only. Longer reads as a render fault
            # rather than a net rippling.
            if u < 0.12:
                d.rectangle([0, 0, W, H],
                            fill=(255, 255, 255, int(190 * (1 - u / 0.12))))
            pop = _ease(min(1, u / 0.18))
            fade = _ease(min(1, (1 - u) / 0.15))
            alpha = int(255 * pop * fade)
            big = _font(int(150 * (1.3 - 0.3 * pop)))
            word = "GOAL!"
            tw = d.textlength(word, font=big)
            d.text(((W - tw) / 2 + 5, 700 + 5), word, font=big,
                   fill=(10, 10, 12, int(alpha * 0.6)))
            d.text(((W - tw) / 2, 700), word, font=big,
                   fill=(*self.accent, alpha))
            line = a["scorer"].upper()
            if a["assist"]:
                line += f"  ·  {a['assist'].upper()}"
            if line:
                sf = _font(46)
                lw = d.textlength(line, font=sf)
                d.text(((W - lw) / 2, 880), line, font=sf,
                       fill=(255, 255, 255, alpha))

        # passing triangles — the shape three connected men make
        for a in self.annos:
            if a["type"] != "triangle" or not (a["t0"] <= t <= a["t1"]):
                continue
            u = _ease(min(1, (t - a["t0"]) / 0.45))
            fade = _ease(min(1, (a["t1"] - t) / 0.35))
            alpha = int(210 * u * fade)
            pts = [self._px(*q) for q in a["pts"]]
            d.polygon(pts, fill=(*self.accent, int(alpha * 0.16)))
            for i in range(3):
                d.line([pts[i], pts[(i + 1) % 3]],
                       fill=(*self.accent, alpha), width=5)
            if a["label"]:
                cx = sum(q[0] for q in pts) / 3
                cy = sum(q[1] for q in pts) / 3
                f = _font(30)
                lw = d.textlength(a["label"], font=f)
                d.rounded_rectangle([cx - lw / 2 - 12, cy - 24,
                                     cx + lw / 2 + 12, cy + 24],
                                    radius=10, fill=(10, 10, 12, alpha))
                d.text((cx - lw / 2, cy - 16), a["label"], font=f,
                       fill=(*self.accent, alpha))

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
