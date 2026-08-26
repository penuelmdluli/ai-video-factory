"""
Tactical motion — the shape moving, not eleven dots sitting still.

Owner call 2026-08-24: "the image line-up ends around 16s, so the rest is where
we must make these motions... players move all together at once while they form
offensive and defensive strength, this must simulate like it's real".

So the video has two halves. The reveal names the side; this animates it. The
whole block slides forward into an attacking shape — full-backs push on, the
line steps up, the front pair splits wide — then recovers and drops into a
compact defensive block, narrow and deep. Every man moves at once, on an eased
curve, because a defensive block that snaps into place looks like a slideshow
and a block that drifts looks like a team.

The geometry mirrors modules/lineup_card exactly, so a marker sits where the
static card would put it and the motion begins from the position the viewer has
just spent sixteen seconds learning.
"""
from pathlib import Path

W, H = 1080, 1350


def _font(size, bold=True):
    from PIL import ImageFont
    for f in ((r"C:\Windows\Fonts\arialbd.ttf" if bold
               else r"C:\Windows\Fonts\arial.ttf"),
              r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def base_positions(formation: str, bench: bool = False):
    """(x, y) per player, identical to how lineup_card lays the XI out."""
    px1, py1 = 60, 420
    px2, py2 = W - 60, H - 120 - (132 if bench else 0)
    rows = [1] + [max(1, int(n)) for n in str(formation).split("-")
                  if n.strip().isdigit()]
    pitch_h = (py2 - 40) - (py1 + 60)
    n_rows = len(rows)
    pts = []
    for r, n in enumerate(rows):
        y = int((py2 - 60) - (pitch_h / max(1, n_rows - 1)) * r) if n_rows > 1 \
            else (py1 + py2) // 2
        for c in range(n):
            pts.append([int(W * (c + 1) / (n + 1)), y])
    return pts, (px1, py1, px2, py2)


def shape(formation: str, phase: str, bench: bool = False):
    """Positions for 'base', 'attack' or 'defend'.

    Attack: the block travels forward, full-backs overlap into the wide
    channels and the forward line splits to stretch the last defender.
    Defend: everything drops and narrows into a compact mid-block — the
    distances shrink, which is what compactness actually looks like.
    """
    pts, bounds = base_positions(formation, bench)
    px1, py1, px2, py2 = bounds
    rows = [1] + [max(1, int(n)) for n in str(formation).split("-")
                  if n.strip().isdigit()]
    span = py2 - py1
    out, i = [], 0
    for r, n in enumerate(rows):
        for c in range(n):
            x, y = pts[i]
            if phase == "attack":
                # goalkeeper barely moves; every outfield line pushes on, the
                # further forward the line the more ground it gains
                push = 0.0 if r == 0 else 0.055 + 0.028 * r
                wide_back = r == 1 and n >= 4 and c in (0, n - 1)
                # Owner call 2026-08-24: "as they attack Mmodi and Monyane
                # attack too and only the CBs are left, and one CB steps to
                # CDM". With the wing-backs gone the back three is two centre
                # halves and a screen — the middle man steps into the hole in
                # front of them, which is how a side builds out of a back five.
                if r == 1 and n >= 5 and c == n // 2:
                    push = 0.21
                if wide_back:
                    # Owner call 2026-08-24: get the full-backs CLOSE TO THE
                    # ATTACK. In a back five these are wing-backs — in the
                    # attacking phase they are the widest attackers on the
                    # pitch, level with the midfield and hugging the touchline.
                    # A 46px shuffle read as a defender edging forward; this
                    # reads as an overlap.
                    push = 0.42
                    x += (-1 if c == 0 else 1) * 92
                y -= span * push
                if r == len(rows) - 1 and n >= 2:
                    x += (-1 if c < n / 2 else 1) * 34   # forwards split
            elif phase == "defend":
                drop = 0.0 if r == 0 else 0.035 + 0.030 * r
                y += span * drop
                # narrow toward the middle: compactness is lateral, not just deep
                x = int(W / 2 + (x - W / 2) * (0.70 if r else 1.0))
            out.append([int(x), int(max(py1 + 70, min(py2 - 50, y)))])
            i += 1
    return out


def effective_formation(formation: str, phase: str) -> str:
    """What the shape READS as in this phase.

    Owner call 2026-08-24: "change from 3-5-2 or 5-3-2 depending on attack or
    defend". That is what actually happens — when both wing-backs push into
    midfield a back five IS a back three, and the side is a 3-5-2 going forward
    and a 5-3-2 without the ball. Naming it is the difference between a graphic
    that shows movement and one that explains it.
    """
    rows = [int(v) for v in str(formation).split("-") if v.strip().isdigit()]
    if phase != "attack" or not rows or rows[0] < 4:
        return formation
    out = rows[:]
    out[0] -= 2                       # both wide defenders leave the back line
    if len(out) > 1:
        out[1] += 2                   # and arrive in midfield
    return "-".join(str(v) for v in out)


def _arrow(d, x1, y1, x2, y2, colour, width=7):
    """A run marker: shaft plus head, pointing where the player is going."""
    import math
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 24:
        return
    ux, uy = dx / dist, dy / dist
    # stop short of the marker so the head is not buried under it
    ex, ey = x2 - ux * 42, y2 - uy * 42
    sx, sy = x1 + ux * 40, y1 + uy * 40
    if math.hypot(ex - sx, ey - sy) < 18:
        return
    d.line([sx, sy, ex, ey], fill=colour, width=width)
    hl, hw = 26, 13
    bx, by = ex - ux * hl, ey - uy * hl
    d.polygon([(ex, ey), (bx - uy * hw, by + ux * hw),
               (bx + uy * hw, by - ux * hw)], fill=colour)


def _ease(u):
    """Smootherstep — no linear slides, nothing snaps into place."""
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)



def _channels(d, a, b, pos, formation, phase, u, px, accent):
    """Shade the ground the full-backs cover, and the box they defend.

    Owner call 2026-08-26: "show the box and the space the right and left back
    cover as they move". Arrows say where a man is going; they say nothing
    about how much grass he is responsible for. The channel is the whole point
    of a modern full-back, so it is drawn as territory rather than a line.
    """
    px1, py1, px2, py2 = px
    rows = [1] + [max(1, int(v)) for v in str(formation).split("-")
                  if v.strip().isdigit()]
    if len(rows) < 2:
        return
    back_n = rows[1]
    if back_n < 3:
        return
    wide = [1, back_n]                       # indexes of the two wide backs
    fade = 1.0 - abs(u * 2 - 1)              # strongest mid-transition
    alpha = int(64 + 54 * fade)

    for i in wide:
        if i >= len(a) or i >= len(b) or i >= len(pos):
            continue
        x0, y0 = a[i]
        x1, y1 = b[i]
        if abs(y1 - y0) < 6 and abs(x1 - x0) < 6:
            continue
        half = 62
        # the corridor between where he starts and where he ends up
        poly = [(x0 - half, y0 + 26), (x0 + half, y0 + 26),
                (x1 + half, y1 - 26), (x1 - half, y1 - 26)]
        d.polygon(poly, fill=accent + (alpha,))
        for k in range(0, 5):                # rungs, so it reads as ground
            yy = y0 + (y1 - y0) * k / 4.0
            xx = x0 + (x1 - x0) * k / 4.0
            d.line([xx - half, yy, xx + half, yy],
                   fill=accent + (min(255, alpha + 46),), width=2)
        cur = pos[i]
        d.ellipse([cur[0] - half, cur[1] - 12, cur[0] + half, cur[1] + 12],
                  outline=accent + (200,), width=3)

    # The defensive box: what the block is actually protecting.
    if phase == "defend":
        bw = int((px2 - px1) * 0.46)
        bh = 150
        bx = (px1 + px2) // 2
        d.rectangle([bx - bw // 2, py2 - bh, bx + bw // 2, py2],
                    outline=(255, 255, 255, 150), width=4)
        d.rectangle([bx - bw // 2, py2 - bh, bx + bw // 2, py2],
                    fill=(255, 255, 255, 20))
        bf = _font(22)
        lab = "PROTECT THIS"
        lw = d.textlength(lab, font=bf)
        d.text((bx - lw / 2, py2 - bh - 34), lab, font=bf,
               fill=(255, 255, 255, 190))


def frame(background, formation: str, players: list[str], t: float,
          plan: list[tuple[str, float]], accent=(255, 193, 7), bench=False):
    """One motion frame at time t, given a plan of (phase, seconds) legs."""
    from PIL import Image, ImageDraw

    total = sum(d for _, d in plan)
    t = max(0.0, min(total - 0.001, t))
    acc, leg = 0.0, 0
    for k, (_, d) in enumerate(plan):
        if t < acc + d:
            leg = k
            break
        acc += d
    frm = plan[leg][0]
    to = plan[min(leg + 1, len(plan) - 1)][0]
    u = _ease((t - acc) / max(0.001, plan[leg][1]))

    a = shape(formation, frm, bench)
    b = shape(formation, to, bench)

    # Stagger the arrival slightly by role. A block that moves as one rigid
    # slab looks like a diagram; a real side shifts from the back, and the
    # overlapping wing-back is the LAST man to arrive. Each player runs the
    # same eased curve, just started a beat apart.
    prog = (t - acc) / max(0.001, plan[leg][1])
    rows_f = [1] + [max(1, int(v)) for v in str(formation).split("-")
                    if v.strip().isdigit()]
    delays, i2 = [], 0
    for r2, n2 in enumerate(rows_f):
        for c2 in range(n2):
            wide_back = r2 == 1 and n2 >= 4 and c2 in (0, n2 - 1)
            delays.append(0.22 if wide_back else min(0.14, 0.035 * r2))
            i2 += 1

    pos = []
    for i in range(len(a)):
        dly = delays[i] if i < len(delays) else 0.0
        ui = _ease((prog - dly) / max(0.05, 1.0 - dly))
        pos.append([a[i][0] + (b[i][0] - a[i][0]) * ui,
                    a[i][1] + (b[i][1] - a[i][1]) * ui])

    im = background.copy()
    d = ImageDraw.Draw(im, "RGBA")

    # Run arrows, under the markers: where each man is heading. Strongest
    # mid-transition and gone once everyone has arrived, so a settled shape is
    # never cluttered by arrows pointing at nothing.
    _, (px1, py1, px2, py2) = base_positions(formation, bench)
    _channels(d, a, b, pos, formation, to if u > 0.5 else frm, u,
              (px1, py1, px2, py2), accent)

    fade = 1.0 - abs(u * 2 - 1)
    if fade > 0.05 and to != frm:
        alpha = int(190 * fade)
        for i in range(len(a)):
            _arrow(d, a[i][0], a[i][1], b[i][0], b[i][1],
                   (255, 255, 255, alpha), width=max(4, int(7 * fade)))

    phase_now = to if u > 0.5 else frm
    shape_txt = effective_formation(formation, phase_now)
    label = {"base": f"SHAPE · {shape_txt}",
             "attack": f"ATTACKING · {shape_txt}",
             "defend": f"DEFENSIVE BLOCK · {shape_txt}"}.get(phase_now, "SHAPE")
    # Bottom-left inside the pitch. Above the pitch it sat on the fixture line;
    # in the top corner the attacking shape pushed a forward into it. The
    # bottom corners are the only ground no phase ever occupies — the keeper
    # stays central and the back line never widens past the full-backs.
    lf = _font(30)
    lw = d.textlength(label, font=lf)
    lx, ly = px1 + 22, py2 - 68
    d.rounded_rectangle([lx, ly, lx + lw + 40, ly + 46], radius=12, fill=accent)
    d.text((lx + 20, ly + 8), label, font=lf, fill=(20, 20, 20))

    nf, sf = _font(25), _font(21)
    for i, (x, y) in enumerate(pos):
        rr = 34
        d.ellipse([x - rr - 3, y - rr - 3, x + rr + 3, y + rr + 3],
                  fill=(0, 0, 0, 90))
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=accent)
        raw = players[i] if i < len(players) else ""
        parts = str(raw).split(None, 1)
        num = parts[0] if parts and parts[0].isdigit() else ""
        name = (parts[1] if len(parts) > 1 else raw).upper()
        if num:
            nw = d.textlength(num, font=nf)
            d.text((x - nw / 2, y - 13), num, font=nf, fill=(20, 20, 20))
        if name:
            w = d.textlength(name, font=sf)
            d.rounded_rectangle([x - w / 2 - 11, y + rr + 5,
                                 x + w / 2 + 11, y + rr + 37],
                                radius=9, fill=(16, 18, 22))
            d.text((x - w / 2, y + rr + 10), name, font=sf,
                   fill=(255, 255, 255))
    return im
