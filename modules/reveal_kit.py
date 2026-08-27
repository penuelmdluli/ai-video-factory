"""
Anticipation. The bit between asking a question and answering it.

Owner call 2026-08-27: "add loaders and all, to keep them waiting to see who
comes there, or what next... something nice to watch even without a sound".

The numbers already said this. Measured over 30 days the same afternoon, the
lineup format scored 452 against 22 for news - and a lineup is not better
information, it is better STAGING. Eleven names arriving one at a time, each
one a small answer to "who is next", beats the same eleven names in a list.
Every other format was handing over its answer immediately.

So this module is the waiting, not the answer:

  scan_loader()     a search that visibly works before it reports
  slot_reveal()     names tumbling until one locks in
  silhouette_pop()  a shape you can nearly recognise, then can
  progress_rail()   3 of 11 - the reason to stay for the fourth

WATCHABLE WITH THE SOUND OFF is a hard requirement, not a nice-to-have. Most
of a feed is watched muted, so nothing here may depend on narration to make
sense. Every beat is carried by movement: something is always drifting,
sweeping or counting, and each reveal has a visible before and after. The
ambient layer exists so that even a still moment is not a frozen one.

All functions draw onto a PIL ImageDraw at a given time t and compose with
motion_kit, so existing builders can adopt one piece without a rewrite.
"""
import math

from modules.motion_kit import W, H, GOLD, DARK, _crest, _ease, _font, _over

INK = (255, 255, 255)
DIM = (128, 138, 152)


# ── ambient: the page is never still ───────────────────────────────────────

def ambient(d, t, seed=0, density=34, tint=GOLD):
    """Drifting motes and a slow sweep of light.

    Without this a held frame reads as a video that has stopped loading, and
    a muted viewer scrolls past a still image. It costs almost nothing and it
    is the difference between a paused feeling and a waiting one.
    """
    for i in range(density):
        p = (i * 37 + seed * 13) % 100 / 100.0
        x = (p * W * 1.7 + t * (12 + (i % 5) * 7)) % (W + 120) - 60
        y = (i * 211 + seed * 57) % H
        y = (y - t * (18 + (i % 3) * 9)) % H
        r = 1.5 + (i % 4) * 0.9
        a = 0.10 + 0.16 * (0.5 + 0.5 * math.sin(t * 1.4 + i))
        c = tuple(int(v * a + DARK[k] * (1 - a)) for k, v in enumerate(tint))
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)

    # a wide, soft band of light crossing the stage every few seconds
    sweep = (t * 0.16 + seed * 0.21) % 1.4
    if sweep < 1.0:
        cy = int(-200 + sweep * (H + 400))
        for k in range(-150, 151, 6):
            a = (1 - abs(k) / 150) * 0.05
            y = cy + k
            if 0 <= y < H:
                d.line([(0, y), (W, y)],
                       fill=tuple(int(GOLD[i] * a + DARK[i] * (1 - a))
                                  for i in range(3)))


# ── the loader: work you can see happening ─────────────────────────────────

def scan_loader(d, t, label="ANALYSING THE SQUAD", cx=W // 2, cy=H // 2,
                radius=190, done=0.0, club=""):
    """A ring that fills while a scan line sweeps a crest.

    'done' 0..1 drives the ring, so the caller controls the pace of the wait
    rather than the animation pretending to know. A loader that reaches 100%
    and keeps spinning is the fastest way to look fake.
    """
    for k in range(3):
        rr = radius + k * 5
        a = 0.18 - k * 0.05
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=tuple(int(GOLD[i] * a + DARK[i] * (1 - a))
                                for i in range(3)), width=2)

    sweep = 360 * max(0.0, min(1.0, done))
    if sweep > 0:
        d.arc([cx - radius, cy - radius, cx + radius, cy + radius],
              start=-90, end=-90 + sweep, fill=GOLD, width=9)
    # leading comet so the ring reads as moving even while it waits
    head = -90 + sweep
    for k in range(16):
        a = (1 - k / 16) * 0.8
        ang = math.radians(head - k * 2.0)
        x, y = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
        r = 5 * (1 - k / 22)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=tuple(int(GOLD[i] * a + DARK[i] * (1 - a))
                             for i in range(3)))

    if club:
        c = _crest(club, int(radius * 1.15))
        if c:
            pulse = 1 + 0.03 * math.sin(t * 3.2)
            cw, ch = int(c.width * pulse), int(c.height * pulse)
            d._image.paste(c.resize((cw, ch)), (cx - cw // 2, cy - ch // 2), c.resize((cw, ch)))

    # scan line crossing the disc
    sy = cy + int(math.sin(t * 2.1) * radius * 0.82)
    half = int(math.sqrt(max(1, radius ** 2 - (sy - cy) ** 2)))
    d.line([(cx - half, sy), (cx + half, sy)], fill=(255, 255, 255), width=3)

    if label:
        dots = "." * (1 + int(t * 2.5) % 3)
        f = _font(46)
        txt = label + dots
        d.text((cx - d.textlength(txt, font=f) / 2, cy + radius + 54),
               txt, font=f, fill=DIM)


# ── the reveal: the answer, staged ─────────────────────────────────────────

def slot_reveal(d, u, names, final, x, y, size=88, colour=INK):
    """Names tumbling like a slot wheel, easing into `final`.

    u is 0..1 across the whole reveal. The wheel slows on a curve rather than
    stopping dead, because the last moment before it settles is the one that
    holds someone's thumb.
    """
    u = max(0.0, min(1.0, u))
    if u >= 1.0:
        f = _font(size)
        d.text((x, y), final, font=f, fill=colour)
        return
    speed = (1 - _ease(u)) ** 2
    idx = int((u * 26 + speed * 40) % max(1, len(names)))
    shown = names[idx] if names else final
    jitter = int((1 - _ease(u)) * 16 * math.sin(u * 44))
    f = _font(int(size * (0.86 + 0.14 * _ease(u))))
    a = 0.35 + 0.65 * _ease(u)
    c = tuple(int(colour[i] * a + DARK[i] * (1 - a)) for i in range(3))
    d.text((x, y + jitter), shown, font=f, fill=c)


def silhouette_pop(d, u, crest_club, cx, cy, size=300):
    """Dark shape first, lit shape second. Recognition is the payoff."""
    c = _crest(crest_club, size)
    if not c:
        return
    u = max(0.0, min(1.0, u))
    scale = _over(u) if u > 0 else 0.01
    cw, ch = max(1, int(c.width * scale)), max(1, int(c.height * scale))
    im = c.resize((cw, ch))
    if u < 0.55:
        # Silhouette by DIMMING, not by flattening.
        #
        # The first version painted every opaque pixel one flat colour. On a
        # round badge that produced a plain grey disc - no crest, no shape,
        # nothing to half-recognise, so the reveal had nothing to pay off.
        # Scaling each channel keeps the internal contrast, so the badge is
        # readable as itself while still clearly unlit.
        from PIL import Image as _I
        k = 0.20 + 0.55 * (u / 0.55)      # lifts as the reveal approaches
        rgb = _I.eval(im.convert("RGB"), lambda v: int(v * k))
        rgb.putalpha(im.getchannel("A"))
        im = rgb
    d._image.paste(im, (cx - cw // 2, cy - ch // 2), im)
    if 0.5 < u < 0.72:
        # the flash on recognition
        g = (u - 0.5) / 0.22
        rr = int(size * (0.6 + g * 0.9))
        a = (1 - g) * 0.5
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=tuple(int(255 * a + DARK[i] * (1 - a))
                                for i in range(3)), width=max(1, int(9 * (1 - g))))


def progress_rail(d, done, total, y=H - 210, label=""):
    """3 OF 11. The single strongest reason to watch the fourth."""
    pad = 90
    w = W - pad * 2
    d.rounded_rectangle([pad, y, pad + w, y + 12], radius=6, fill=(38, 42, 50))
    frac = max(0.0, min(1.0, done / max(1, total)))
    if frac > 0:
        d.rounded_rectangle([pad, y, pad + int(w * frac), y + 12], radius=6,
                            fill=GOLD)
    for i in range(1, total):
        x = pad + int(w * i / total)
        d.line([(x, y - 4), (x, y + 16)], fill=(58, 63, 72), width=2)
    f = _font(38)
    txt = label or f"{int(done)} OF {total}"
    d.text((pad, y - 62), txt, font=f, fill=DIM)
    remain = total - int(done)
    if remain > 0:
        r = f"{remain} TO COME"
        d.text((W - pad - d.textlength(r, font=f), y - 62), r, font=f,
               fill=GOLD)


def crest_outro(d, t, u, club, headline="CHIEFS FANS ARE NUMBER 1",
                call="WHO STARTS? COMMENT BELOW", sub="SUBSCRIBE — GENESIS NEWS"):
    """The badge, big, as the closing frame.

    Owner call 2026-08-27: "at the outro add the best crest design... Chiefs
    fans are number 1". The closing seconds are as long as the sign-off takes
    to say - sixteen on a six-man reel - and a held list of names is where
    people leave. The crest is the one image this audience will sit through,
    so the outro belongs to it.

    Rays turn, the badge breathes, and a ring pulses outward on a beat. u is
    0..1 across the outro so the entrance can overshoot before it settles.
    """
    cx, cy = W // 2, int(H * 0.44)
    u = max(0.0, min(1.0, u))

    # turning rays behind the badge
    spokes = 18
    for i in range(spokes):
        ang = math.radians(t * 11 + i * (360 / spokes))
        a = 0.05 + 0.05 * (0.5 + 0.5 * math.sin(t * 2 + i))
        L = 520
        x2, y2 = cx + L * math.cos(ang), cy + L * math.sin(ang)
        d.line([(cx, cy), (x2, y2)],
               fill=tuple(int(GOLD[k] * a + DARK[k] * (1 - a))
                          for k in range(3)), width=26)

    # pulse rings on a slow beat
    for k in range(2):
        ph = ((t * 0.55 + k * 0.5) % 1.0)
        rr = int(230 + ph * 330)
        a = (1 - ph) * 0.34
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=tuple(int(GOLD[i] * a + DARK[i] * (1 - a))
                                for i in range(3)), width=4)

    c = _crest(club, 460)
    if c:
        breathe = (_over(min(1.0, u * 3.2)) if u < 0.34 else
                   1 + 0.025 * math.sin(t * 2.4))
        cw, ch = max(1, int(c.width * breathe)), max(1, int(c.height * breathe))
        im = c.resize((cw, ch))
        d._image.paste(im, (cx - cw // 2, cy - ch // 2), im)

    # Scrim behind the words. The rays run right through this band, and the
    # call to action - the one line that has to be read - was landing as grey
    # text on gold spokes and disappearing.
    if u > 0.18:
        top, bot = cy + 300, cy + 600
        for yy in range(top, min(H, bot)):
            e = 1 - abs((yy - (top + bot) / 2) / ((bot - top) / 2))
            a = max(0.0, e) * 0.86
            d.line([(0, yy), (W, yy)],
                   fill=tuple(int(DARK[i] * a + 0 * (1 - a)) if a > 0 else DARK[i]
                              for i in range(3)))

    if u > 0.22:
        a = _ease(min(1.0, (u - 0.22) / 0.25))
        f = _font(62)
        col = tuple(int(GOLD[i] * a + DARK[i] * (1 - a)) for i in range(3))
        d.text((W / 2 - d.textlength(headline, font=f) / 2, cy + 330),
               headline, font=f, fill=col)
    if u > 0.42:
        a = _ease(min(1.0, (u - 0.42) / 0.25))
        f = _font(54)
        # heavy outline: this is the instruction, it must survive any backdrop
        x = W / 2 - d.textlength(call, font=f) / 2
        y = cy + 440
        for dx in (-3, 0, 3):
            for dy in (-3, 0, 3):
                if dx or dy:
                    d.text((x + dx, y + dy), call, font=f, fill=(6, 8, 10))
        col = tuple(int(255 * a + DARK[i] * (1 - a)) for i in range(3))
        d.text((x, y), call, font=f, fill=col)
    if u > 0.6:
        pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(t * 3.4))
        f = _font(40)
        col = tuple(int(GOLD[i] * pulse + DARK[i] * (1 - pulse))
                    for i in range(3))
        d.text((W / 2 - d.textlength(sub, font=f) / 2, cy + 530),
               sub, font=f, fill=col)


def hold_hook(d, t, text="WHO IS NEXT?", y=None):
    """A question that breathes, for the beat before a reveal."""
    y = H // 2 + 330 if y is None else y
    pulse = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(t * 2.6))
    f = _font(56)
    c = tuple(int(GOLD[i] * pulse + DARK[i] * (1 - pulse)) for i in range(3))
    d.text((W / 2 - d.textlength(text, font=f) / 2, y), text, font=f, fill=c)
