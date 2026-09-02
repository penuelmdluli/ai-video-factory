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
        # The opposition, from THEIR team sheets. Static - they are the shape
        # our move has to play through, not a side we are animating.
        self.opp_players: dict = {}
        self.opp_positions: dict = {}
        self.opp_runs: list = []
        self.bench: list = []
        self.opp_color = (150, 158, 168)
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

    def arrow(self, t0, t1, a, b, color=None, label="", curve=0.0,
              dashed: bool = False):
        """An arrow. dashed=True for a RUN rather than a pass.

        Owner 2026-09-03: "we can make some dotted lines." It is also the real
        convention on every coaching board there has ever been - a solid line
        is the ball, a dotted line is a man - so a supporter reads the two
        apart without being told which is which.
        """
        self.annos.append({"type": "arrow", "t0": t0, "t1": t1, "a": a,
                           "b": b, "color": color or self.accent,
                           "label": label, "curve": curve, "dashed": dashed})

    def shape_lines(self, t0, t1, rows: list, color=None, labels=None,
                    opponent: bool = False):
        """Join each unit into a LINE, so a 4-4-2 reads as a 4-4-2.

        Owner 2026-09-03: "lets always make clear shapes, best to interest and
        catch the fan eye, and more diagram and all."

        Eleven separate dots is a seating plan. A back four drawn as one line,
        a midfield four as another, is a SHAPE - and the shape is the thing a
        supporter is actually arguing about when he says they should play three
        at the back. It is also how the formation graphic looks on television,
        which is the visual language this audience already reads fluently.

        rows: [[pid, pid, ...], ...] — one list of PLAYER IDS per unit.

        Ids, not coordinates. The first version stored fixed points, so once
        every player started moving the lines stayed where the shape used to
        be - gold and green lines floating in open grass with nobody on them,
        which the owner spotted immediately. Resolving ids per frame means the
        lines BEND as the players move, and a shape that bends is the whole
        point: it shows the back four sliding, the midfield stretching, the
        moment the block breaks.

        opponent=True resolves against the opposition instead of our XI.
        """
        self.annos.append({"type": "shape", "t0": t0, "t1": t1,
                           "rows": rows, "color": color or self.accent,
                           "labels": labels or [], "opp": opponent})

    def set_opposition(self, players: dict, positions: dict, color=None):
        """The other team on the pitch.

        Owner 2026-09-02: "lets add the opponent shapes from their team
        sheets." Until now every move was played through empty grass, which
        makes a passing sequence look easy in a way no supporter believes. A
        real block to play around is the difference between a diagram of our
        eleven and an argument about whether it would actually work.

        They are drawn UNDER our tokens, smaller, in their own colour and
        without name plates. This is our page: the men whose names matter are
        ours, and eleven more labels would turn the board into a car park.
        """
        self.opp_players = dict(players or {})
        self.opp_positions = dict(positions or {})
        if color:
            self.opp_color = tuple(color)

    def set_bench(self, names: list):
        """The substitutes, along the side of the pitch.

        Owner 2026-09-03: "can we show the bench by the side of the field?"

        It costs nothing and answers the question every supporter asks at a
        line-up graphic - "who is left?" - which is also the question that
        starts arguments, because the man he wanted starting is sitting in
        this row. The bench comes off the same ESPN team sheet as the XI, so
        it is real rather than a guess.

        Numbers only, and small. Eleven starters carry names; thirteen more
        name plates would bury the pitch.
        """
        self.bench = [str(n) for n in (names or [])][:9]

    def opp_run(self, pid: str, t0: float, t1: float, a, b):
        """One opponent BREAKS - he carries the ball and scores it.

        Owner 2026-09-03: "the conceded is not the opponent player who scores,
        it is just an arrow."

        He was right and it was the emptiest thing in the reel: the ball and a
        red arrow travelled the length of the pitch while all eleven of their
        players stood in their block, so the goal was scored by nobody. The
        block reacting to the ball is correct for a team defending; it is not
        enough for a team attacking. This overrides one man so he runs the
        counter with the ball, and he is the one whose name goes on the GOAL
        card.
        """
        self.opp_runs.append({"pid": pid, "t0": t0, "t1": t1, "a": a, "b": b})

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
    def _ball_at(self, t: float):
        """Where the ball is at t, or None if none is animated."""
        for a in self.annos:
            if a["type"] != "ball" or not a.get("wp"):
                continue
            wp = a["wp"]
            if t <= wp[0][0]:
                return wp[0][1]
            for (ta, pa), (tb, pb) in zip(wp, wp[1:]):
                if ta <= t <= tb:
                    span = max(tb - ta, 1e-6)
                    k = min(1.0, (t - ta) / (span * 0.45))
                    u = 1 - (1 - k) ** 2.2
                    return (pa[0] + (pb[0] - pa[0]) * u,
                            pa[1] + (pb[1] - pa[1]) * u)
            return wp[-1][1]
        return None

    def _opp_at(self, t: float) -> dict:
        """The opposing block, SHIFTED for where the ball is.

        Owner 2026-09-03: "lets make more best movement in all teams as the
        ball is being played." A defence that stands still while the ball moves
        across it is the last thing that makes this read as a diagram rather
        than a match - real blocks slide, squeeze and press, and a supporter
        knows that better than he knows any of our arrows.

        Three real behaviours, none of them keyframed by hand:
          SLIDE    the whole block shifts towards the ball's side
          SQUEEZE  it steps up as the ball goes back, drops as it comes on
          PRESS    the nearest man breaks out to close the ball down

        Deriving it from the ball means it stays correct for any move, any
        formation and any XI, which eleven hand-placed keyframes would not.
        """
        import math
        if not self.opp_positions:
            return {}
        ball = self._ball_at(t)
        if ball is None:
            return dict(self.opp_positions)
        bx, by = ball
        # Nearest man presses; everyone else slides and squeezes.
        nearest, best = None, 9e9
        for pid, (x, y) in self.opp_positions.items():
            dist = math.hypot(x - bx, y - by)
            if dist < best:
                nearest, best = pid, dist
        # MARKING. Owner 2026-09-03: "the opponent must also try to mark, all
        # must be clean on how the goal came."
        #
        # Sliding and squeezing is what a BLOCK does; marking is what a
        # DEFENDER does, and without it our attackers ran into space nobody had
        # tried to occupy - which makes a goal look unearned. Each of their men
        # picks up the nearest of ours who is ahead of him and moves GOAL-SIDE
        # of him: between that man and their own net, which is the whole idea
        # of marking and the reason a runner beating his marker means anything.
        #
        # Partial, not absolute. A defender who arrives exactly on his man
        # would make every move impossible and every goal a lie; at 0.35 he is
        # visibly trying and visibly beaten, which is what "clean on how the
        # goal came" actually requires.
        ours = self._pos_at(t)
        out = {}
        for pid, (x, y) in self.opp_positions.items():
            dx = (bx - 0.5) * 0.09                 # slide to the ball's side
            dy = (0.34 - by) * 0.10                # squeeze as the ball comes on
            # the man he is responsible for: nearest of ours in front of him
            mark = None
            mbest = 0.34
            for opid, (ox, oy) in ours.items():
                if oy < y:                          # only men ahead of him
                    dist = math.hypot(ox - x, oy - y)
                    if dist < mbest:
                        mark, mbest = (ox, oy), dist
            if mark:
                # goal-side: a little nearer their own goal than the man is
                gx, gy = mark[0], mark[1] - 0.045
                dx += (gx - x) * 0.35
                dy += (gy - y) * 0.35
            if pid == nearest and best < 0.30:
                # He goes to the ball, but never all the way onto it - a
                # defender arriving exactly on the ball would read as a
                # tackle, and this is our move, not theirs.
                dx += (bx - x) * 0.45
                dy += (by - y) * 0.45
            out[pid] = self._alive(pid, (x + dx, y + dy), t)

        # A breaking runner overrides the block entirely - he has left it.
        for r in self.opp_runs:
            if r["pid"] not in out:
                continue
            if t <= r["t0"]:
                out[r["pid"]] = r["a"]
            elif t >= r["t1"]:
                out[r["pid"]] = r["b"]
            else:
                u = _ease((t - r["t0"]) / max(r["t1"] - r["t0"], 1e-6))
                out[r["pid"]] = (r["a"][0] + (r["b"][0] - r["a"][0]) * u,
                                 r["a"][1] + (r["b"][1] - r["a"][1]) * u)
        return out

    def _alive(self, pid: str, xy, t: float, keeper: bool = False):
        """Nobody stands still.

        Owner 2026-09-03: "all players should smoothly be moving on their
        position line, covering for each other... even a keeper is moving, no
        player is standing still, this must be live."

        Between keyframes every player was frozen, so ten men waited politely
        while the eleventh made a pass. Real players are never still - they
        shuffle across, adjust to the man beside them, come short, drop off.

        Two sine waves at different rates, with a phase taken from the player's
        own id, so each man wanders on his own rhythm and the eleven never fall
        into step. Sideways travel is wider than forward travel because a line
        holds its depth and slides across - a back four that drifted up and
        down independently would break the offside line it exists to keep.

        The keeper moves too, at a third of the amplitude: he is alive, but he
        is not leaving his six-yard box to join in.
        """
        import math
        seed = (hash(pid) % 997) / 997.0
        ph = seed * 6.283
        amp = 0.0045 if keeper else 0.013
        dx = math.sin(t * 0.9 + ph) * amp
        dy = math.sin(t * 0.63 + ph * 1.7) * amp * 0.55
        return (min(0.97, max(0.03, xy[0] + dx)),
                min(0.97, max(0.03, xy[1] + dy)))

    def _pos_at(self, t: float) -> dict:
        ks = self.keys
        if not ks:
            return {}

        def live(d):
            # The deepest man on the board is the keeper - amplitude is cut for
            # him rather than requiring callers to tell us who he is.
            if not d:
                return d
            gk = max(d.items(), key=lambda kv: kv[1][1])[0]
            return {pid: self._alive(pid, xy, t, keeper=(pid == gk))
                    for pid, xy in d.items()}

        if t <= ks[0][0]:
            return live(ks[0][1])
        for (t0, p0), (t1, p1) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                u = _ease((t - t0) / max(t1 - t0, 1e-6))
                out = {}
                for pid, xy0 in p0.items():
                    xy1 = p1.get(pid, xy0)
                    out[pid] = (xy0[0] + (xy1[0] - xy0[0]) * u,
                                xy0[1] + (xy1[1] - xy0[1]) * u)
                return live(out)
        return live(ks[-1][1])

    @staticmethod
    def net(top: bool = True, depth: int = 34) -> float:
        """The fy that puts the ball IN the net, not near it.

        Owner 2026-09-03: "the ball must go into the net."

        The mapping in _px is PITCH_TOP + fy * (PITCH_BOT - PITCH_TOP - 120) -
        note the MINUS 120, which exists to leave room for the name plate under
        the deepest player. The consequence nobody had noticed: fy=1.0 lands
        120px SHORT of our goal line, so no fraction between 0 and 1 can reach
        the net at all. Our finishes at fy=0.03 were stopping 40px inside the
        six-yard box and the conceded one stopped further out still - every
        goal in every reel was a ball rolling up near the goal while a GOAL
        card flashed over it.

        Solved by asking the geometry instead of guessing a number: this
        returns the fy that lands `depth` pixels PAST the line, which is
        outside 0..1 at the bottom end and negative at the top, and both are
        fine because the ball is not clamped the way players are.
        """
        span = PITCH_BOT - PITCH_TOP
        usable = span - 120
        return (-depth / usable) if top else ((span + depth) / usable)

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
        # THE NETS. Owner 2026-09-03: "should we add a net and indicate the
        # goal line?" Without one the goal line is just the edge of the pitch
        # rectangle, so a ball 34px past it reads as a ball that has run out of
        # play rather than a goal. A hatched box behind each line makes the
        # crossing unmistakable, which is the whole point of the moment.
        for gy, s in ((PITCH_TOP, -1), (PITCH_BOT, 1)):
            nx0, nx1 = W // 2 - 150, W // 2 + 150
            ny0, ny1 = min(gy, gy + s * 52), max(gy, gy + s * 52)
            d.rectangle([nx0, ny0, nx1, ny1], fill=(255, 255, 255, 26),
                        outline=(255, 255, 255, 120), width=3)
            for gx in range(nx0 + 15, nx1, 15):          # net mesh
                d.line([gx, ny0, gx, ny1], fill=(255, 255, 255, 45), width=1)
            for gyy in range(ny0 + 13, ny1, 13):
                d.line([nx0, gyy, nx1, gyy], fill=(255, 255, 255, 45), width=1)

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
                if a.get("dashed"):
                    # 26px on, 18px off — long enough to read as intent at a
                    # glance, short enough that a curved run still looks like
                    # one line rather than a row of ticks.
                    seg = math.hypot(ex - ax, ey - ay)
                    step, k = 44.0, 0.0
                    while k < seg:
                        f0, f1 = k / seg, min(1.0, (k + 26) / seg)
                        d.line([ax + (ex - ax) * f0, ay + (ey - ay) * f0,
                                ax + (ex - ax) * f1, ay + (ey - ay) * f1],
                               fill=(*a["color"], 235), width=9)
                        k += step
                else:
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

        # opposition tokens — under ours, smaller, no name plates, and MOVING
        for opid, (ofx, ofy) in self._opp_at(t).items():
            ox, oy = self._px(ofx, ofy)
            d.ellipse([ox - 34, oy - 34, ox + 34, oy + 34],
                      fill=(*self.opp_color, 210),
                      outline=(240, 240, 240, 180), width=2)
            ono = self.opp_players.get(opid, {}).get("no", "")
            if ono:
                ow = d.textlength(ono, font=_font(26))
                d.text((ox - ow / 2, oy - 16), ono, font=_font(26),
                       fill=(20, 20, 24))

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
                        k = min(1.0, (tt - ta) / (span * 0.72))
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

        # formation shape lines — each unit joined, so the shape reads
        for a in self.annos:
            if a["type"] != "shape" or not (a["t0"] <= t <= a["t1"]):
                continue
            u = _ease(min(1, (t - a["t0"]) / 0.6))
            fade = _ease(min(1, (a["t1"] - t) / 0.4))
            alpha = int(150 * u * fade)
            live_map = self._opp_at(t) if a.get("opp") else pos
            for ri, row in enumerate(a["rows"]):
                if len(row) < 2:
                    continue
                # Resolve ids to where those men are RIGHT NOW, and keep the
                # line in left-to-right order so it never crosses itself when
                # two players drift past each other.
                here = [live_map[q] for q in row if q in live_map]
                if len(here) < 2:
                    continue
                pts = [self._px(*q) for q in sorted(here)]
                # Draw progressively so the shape assembles rather than
                # appearing - a line that builds pulls the eye along it.
                span = max(1, len(pts) - 1)
                for i in range(span):
                    seg_u = min(1.0, max(0.0, u * span - i))
                    if seg_u <= 0:
                        break
                    ax, ay = pts[i]
                    bx, by = pts[i + 1]
                    d.line([ax, ay, ax + (bx - ax) * seg_u,
                            ay + (by - ay) * seg_u],
                           fill=(*a["color"], alpha), width=5)
                if ri < len(a["labels"]) and a["labels"][ri] and u >= 1:
                    lbl = a["labels"][ri]
                    f = _font(26)
                    lw = d.textlength(lbl, font=f)
                    # 26px of clearance was not enough: a token is 42px in
                    # radius, so "MIDFIELD 4" ran under the first shirt and
                    # lost its number. Clear the circle, not just the centre.
                    lx = min(p[0] for p in pts) - lw - 72
                    ly = sum(p[1] for p in pts) / len(pts) - 14
                    if lx < 12:
                        lx = max(p[0] for p in pts) + 72
                    d.text((lx, ly), lbl, font=f, fill=(*a["color"], alpha))

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
            # FIT THE FRAME. The size was fixed at 96px, and the stamp is
            # centred at (W - tw) / 2 - so any text wider than the board got a
            # NEGATIVE start and was cut off at both edges. "KAIZER CHIEFS V
            # SIWELELE" is 24 characters and lost its first and last words in
            # the opening chapter of every reel. Shrink until it fits, with the
            # punch-in scale applied after so the animation is unchanged.
            base = 96
            while base > 40 and d.textlength(
                    a["text"], font=_font(base)) > W - 150:
                base -= 4
            big = _font(int(base * scale))
            tw = d.textlength(a["text"], font=big)
            # OFF THE MIDDLE. Owner 2026-09-03: "the text in the centre of the
            # video must be removed." At cy=760 the stamp sat dead centre over
            # the pitch, on top of the exact area where the move is happening -
            # a caption covering the thing it is captioning. It now sits just
            # under the header, where the play almost never reaches.
            cy = 300
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

        # the bench, in the band between the pitch and the subtitle
        sub_y = 1760
        if self.bench:
            sub_y = 1858
            f_b = _font(24)
            lw = d.textlength("BENCH", font=f_b)
            # 1740 put the bench directly over our own net at y=1753, so a
            # conceded goal went in BEHIND the substitutes and could not be
            # seen at all. It drops below the net band.
            d.text((44, 1812), "BENCH", font=f_b, fill=(150, 156, 164))
            x = 44 + lw + 26
            for entry in self.bench:
                no = entry.split()[0] if entry.split() else ""
                if x + 52 > W - 40:
                    break
                d.ellipse([x, 1800, x + 46, 1846],
                          fill=(38, 42, 48), outline=(120, 126, 134), width=2)
                nw = d.textlength(no, font=f_b)
                d.text((x + 23 - nw / 2, 1812), no, font=f_b,
                       fill=(225, 228, 232))
                x += 56

        if self.subtitle:
            sw = d.textlength(self.subtitle, font=_font(30))
            d.rounded_rectangle([(W - sw) / 2 - 20, sub_y,
                                 (W + sw) / 2 + 20, sub_y + 60], radius=14,
                                fill=(10, 10, 12, 220))
            d.text(((W - sw) / 2, sub_y + 10), self.subtitle, font=_font(30),
                   fill=(235, 238, 242))
        return im

    def slow_motion(self, t0: float, t1: float, factor: float = 0.35):
        """Run the board in SLOW MOTION between t0 and t1.

        Owner 2026-09-03: "we can show a goal slow motion."

        Every broadcast slows the finish, and the reason is not decoration: the
        moment the ball crosses the line is the only moment the viewer wants to
        look at twice, and at full speed a 24px ball covers it in four frames.

        This warps TIME rather than the animation, so the ball, all
        twenty-two players, the arrows and the pressing defender all slow
        together - a shot that slowed while the players carried on would look
        broken. Board time keeps advancing at `factor` through the window and
        continues from wherever it reached, so nothing is skipped and the
        chapter still fills its slot.
        """
        self._slow = (t0, t1, max(0.05, factor))

    def _warp(self, t: float) -> float:
        """Real frame time -> board time, honouring any slow-motion window.

        The window must GIVE THE TIME BACK. The first version ran at `factor`
        through the window and then at normal speed, so board time finished
        short by (t1 - t0) * (1 - factor): with a 0.72->0.93 window at 0.40,
        a chapter ended at board time 0.874. The ball still arrived, but the
        GOAL card at 0.90 and the scoreline at 0.94 never fired - so the first
        goal went in and the reel never said so, which is exactly what the
        owner saw.

        After the window the board now runs slightly FAST, at whatever rate
        lands it on the full duration at the final frame. That reads as
        normal, because by then the ball is already in the net and the only
        thing left to do is show the card.
        """
        w = getattr(self, "_slow", None)
        if not w:
            return t
        t0, t1, f = w
        if t <= t0:
            return t
        if t < t1:
            return t0 + (t - t0) * f
        at_t1 = t0 + (t1 - t0) * f
        dur = getattr(self, "_dur", None)
        if not dur or dur <= t1:
            return at_t1 + (t - t1)
        # catch up so board time reaches `dur` exactly at the last frame
        rate = (dur - at_t1) / (dur - t1)
        return at_t1 + (t - t1) * rate

    def render(self, out_path, duration: float, fps: int = 30) -> str:
        import numpy as np
        from moviepy import VideoClip
        self._dur = float(duration)
        clip = VideoClip(
            lambda t: np.array(self._frame(self._warp(t))), duration=duration)
        clip.write_videofile(str(out_path), fps=fps, codec="libx264",
                             audio=False, logger=None, preset="medium")
        return str(out_path)
