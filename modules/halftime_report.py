"""
Half-time report — the moment the page can prove it was watching.

At the break we already know three things nobody else on the timeline has
put together: what the score actually is, who scored, and what WE said would
happen before kick-off. Putting those on one screen is what makes a page feel
live rather than automated — and it holds us to our own call in public.

Everything is real: the score and scorers come from the live scoreboard, the
prediction comes from what we stored before the match. If we got it wrong,
the graphic says so.
"""
import numpy as np
from PIL import Image, ImageDraw

from modules.motion_kit import _crest, _ease, _font, _over

W, H = 1080, 1920
GOLD = (255, 200, 0)
RED = (220, 60, 50)
GREEN = (60, 200, 120)
INK = (10, 12, 16)


def _fit(d, text, size, max_w, bold=True, floor=20):
    while size > floor and d.textlength(text, font=_font(size, bold)) > max_w:
        size -= 2
    return _font(size, bold)


def render(out_path, home, away, home_key, away_key, score_h, score_a,
           scorers_h, scorers_a, called_xi_hits=None, our_call="",
           verdict="STICKING WITH OUR CALL", duration=14.0):
    """The half-time panel. Returns the rendered path."""
    from moviepy import VideoClip

    ch = _crest(home_key, 210)
    ca = _crest(away_key, 210)

    def frame(t):
        im = Image.new("RGB", (W, H), INK)
        d = ImageDraw.Draw(im, "RGBA")

        # masthead + live tag
        d.rectangle([0, 0, W, 150], fill=(8, 10, 13))
        d.text((44, 34), "GENESIS NEWS", font=_font(44), fill=(255, 255, 255))
        d.text((46, 92), "HALF TIME", font=_font(26, False), fill=GOLD)
        pulse = 0.55 + 0.45 * abs(np.sin(t * 3))
        d.ellipse([W - 232, 60, W - 204, 88],
                  fill=(int(220 * pulse), 50, 45))
        d.text((W - 190, 56), "LIVE", font=_font(30), fill=(255, 255, 255))

        # crests + scoreline
        u = _over(min(1, t / 0.5))
        if ch:
            c = ch.resize((int(210 * u) or 1,) * 2)
            im.paste(c, (110, 300), c)
        if ca:
            c = ca.resize((int(210 * u) or 1,) * 2)
            im.paste(c, (W - 110 - c.width, 300), c)
        sf = _font(int(150 * u))
        s = f"{score_h} - {score_a}"
        sw = d.textlength(s, font=sf)
        d.text(((W - sw) / 2, 320), s, font=sf, fill=(255, 255, 255))

        nf = _font(34)
        d.text((110, 530), home.upper()[:14], font=nf, fill=(210, 216, 222))
        aw = d.textlength(away.upper()[:14], font=nf)
        d.text((W - 110 - aw, 530), away.upper()[:14], font=nf,
               fill=(210, 216, 222))

        # scorers, appearing in order
        ball = None
        try:
            from modules.motion_kit import icon
            ball = icon("ball", 40)
        except Exception:
            ball = None
        y = 640
        for i, (side, who) in enumerate([("h", x) for x in scorers_h]
                                        + [("a", x) for x in scorers_a]):
            if t < 0.9 + i * 0.3:
                continue
            g = _over(min(1, (t - 0.9 - i * 0.3) / 0.3))
            f = _font(int(38 * g))
            txt = who
            tw = d.textlength(txt, font=f)
            if side == "h":
                if ball:
                    im.paste(ball, (110, y + 2), ball)
                d.text((162, y), txt, font=f, fill=(255, 255, 255))
            else:
                if ball:
                    im.paste(ball, (W - 110 - int(tw) - 52, y + 2), ball)
                d.text((W - 110 - tw, y), txt, font=f, fill=(255, 255, 255))
            y += 56

        # our call — the part that makes it ours
        if t > 2.4:
            g = _over(min(1, (t - 2.4) / 0.45))
            py = 1080
            d.rounded_rectangle([60, py, W - 60, py + 430], radius=26,
                                fill=(18, 21, 27, 240),
                                outline=(*GOLD, int(200 * g)), width=4)
            d.text((100, py + 30), "WHAT WE CALLED", font=_font(32),
                   fill=GOLD)
            if called_xi_hits is not None:
                hits, total = called_xi_hits
                col = GREEN if hits >= total * 0.7 else RED
                hf = _font(int(74 * g))
                d.text((100, py + 86), f"{hits}/{total}", font=hf, fill=col)
                d.text((100 + d.textlength(f"{hits}/{total}", font=hf) + 22,
                        py + 116), "of our predicted XI started",
                       font=_font(30, False), fill=(214, 220, 226))
            if our_call:
                cf = _fit(d, our_call, 34, W - 200, bold=False)
                d.text((100, py + 210), our_call, font=cf,
                       fill=(235, 238, 242))

        # verdict stamp
        if t > 4.2:
            g = _over(min(1, (t - 4.2) / 0.4))
            vf = _fit(d, verdict, int(58 * g), W - 220)
            vw = d.textlength(verdict, font=vf)
            d.rounded_rectangle([(W - vw) / 2 - 40, 1600,
                                 (W + vw) / 2 + 40, 1730], radius=24,
                                fill=(*GOLD, 240))
            d.text(((W - vw) / 2, 1628), verdict, font=vf, fill=(12, 12, 12))

        d.text((60, H - 70), "Score and scorers: live scoreboard",
               font=_font(22, False), fill=(140, 146, 154))
        return np.array(im)

    clip = VideoClip(frame, duration=duration)
    clip.write_videofile(str(out_path), fps=30, codec="libx264",
                         audio=False, logger=None, preset="medium")
    return str(out_path)
