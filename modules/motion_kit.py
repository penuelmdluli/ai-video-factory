"""
Motion kit — the full animated-graphics arsenal for Genesis News.

Every renderer returns a vertical 1080x1920 mp4 in the house style:
  goal_alert()        crest slams in, score pops, scorer types itself
  card_alert()        red/yellow card spins in, player token shakes + dims
  player_spotlight()  stat bars grow + counters tick over breathing crest
  head_to_head()      two players' stat bars race each other
  transfer_move()     token slides crest -> crest, fee stamps in
  quote_kinetic()     press-quote words punch in one by one
  countdown()         matchday countdown with rolling digits

All pure PIL + MoviePy VideoClip(make_frame) — no external tools.
"""
import math
from pathlib import Path

W, H = 1080, 1920
GOLD = (255, 193, 7)
DARK = (12, 14, 18)


def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _over(u):
    """overshoot pop: 0->1 with a 1.15 bounce"""
    u = max(0.0, min(1.0, u))
    return 1 + (1.15 - 1) * math.sin(u * math.pi) if u < 1 else 1.0


def _font(sz, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(
        f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}", sz)


ICONS = Path(__file__).parent.parent / "assets" / "motion_icons"
_ICON = {"ball": "26bd", "trophy": "1f3c6", "fire": "1f525",
         "timer": "23f1", "board": "1f4cb", "gloves": "1f9e4",
         "star": "2b50", "siren": "1f6a8", "impact": "1f4a5",
         "stadium": "1f3df"}


def icon(name, size=120):
    """Crisp Apache-licensed Noto icon, resized."""
    from PIL import Image
    p = ICONS / f"{_ICON.get(name, name)}.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("RGBA")
    return im.resize((size, size))


def _crest(club, size=260):
    from PIL import Image
    from modules.club_brand import official_badge
    p = official_badge(club)
    if not p:
        return None
    im = Image.open(p).convert("RGBA")
    r = min(size / im.width, size / im.height)
    return im.resize((int(im.width * r), int(im.height * r)))


def _base(d):
    d.rectangle([0, 0, W, H], fill=DARK)
    for i in range(160):
        a = 1 - i / 160
        d.line([(0, i), (W, i)],
               fill=(int(30 * a) + 12, int(60 * a) + 14, int(30 * a) + 18))
    d.text((44, 40), "GENESIS NEWS", font=_font(42), fill=(255, 255, 255))


async def attach_voice(video_path, text: str, out_path=None) -> str:
    """Give any silent motion piece a house-voice narration. Returns the
    voiced file (defaults to <name>_voiced.mp4). Falls back to the silent
    original on any failure — audio must never block a post."""
    try:
        from moviepy import (VideoFileClip, AudioFileClip,
                             CompositeAudioClip)
        from modules.voice_generator import generate_voice
        video_path = Path(video_path)
        out_path = Path(out_path) if out_path else \
            video_path.with_name(video_path.stem + "_voiced.mp4")
        vwork = video_path.parent / "voicework"
        vwork.mkdir(parents=True, exist_ok=True)
        v = await generate_voice(text, vwork, video_path.stem, "short",
                                 "sa_pulse")
        audio_p = (v or {}).get("audio_path")
        if not audio_p:
            return str(video_path)
        clip = VideoFileClip(str(video_path))
        voice = AudioFileClip(audio_p)
        clip = clip.with_audio(
            CompositeAudioClip([voice]).with_duration(clip.duration))
        clip.write_videofile(str(out_path), fps=30, codec="libx264",
                             audio_codec="aac", logger=None,
                             preset="medium")
        return str(out_path)
    except Exception as e:
        print(f"[MotionKit] voice attach failed: {str(e)[:100]}")
        return str(video_path)


def _render(frame_fn, out_path, duration, fps=30):
    import numpy as np
    from moviepy import VideoClip
    clip = VideoClip(lambda t: np.array(frame_fn(t)), duration=duration)
    clip.write_videofile(str(out_path), fps=fps, codec="libx264",
                         audio=False, logger=None, preset="medium")
    return str(out_path)


# ── 1. GOAL ALERT ──────────────────────────────────────────────────────────
def goal_alert(out, club="pirates", scorer="LUNGU", minute="60'",
               score="1-0", vs="Chippa United", duration=6.0):
    from PIL import Image, ImageDraw
    crest = _crest(club, 300)

    def frame(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), "GOAL ALERT", font=_font(28, False), fill=GOLD)
        # pulsing rays
        for k in range(12):
            ang = k * math.pi / 6 + t * 0.6
            alpha = int(40 + 25 * math.sin(t * 3 + k))
            d.line([W // 2, 700, W // 2 + int(900 * math.cos(ang)),
                    700 + int(900 * math.sin(ang))],
                   fill=(*GOLD, alpha), width=18)
        # crest slam: scale 3.0 -> 1.0 in 0.45s
        u = _ease(min(1, t / 0.45))
        s = 3.0 - 2.0 * u
        if crest:
            c = crest.resize((max(1, int(crest.width * s)),
                              max(1, int(crest.height * s))))
            im.paste(c, (W // 2 - c.width // 2, 700 - c.height // 2), c)
        # GOAL! pop after slam
        if t > 0.5:
            g = _over(min(1, (t - 0.5) / 0.4))
            gf = _font(int(150 * g))
            gw = d.textlength("GOAL!", font=gf)
            d.text(((W - gw) / 2, 980), "GOAL!", font=gf, fill=GOLD)
        # score pop
        if t > 0.9:
            sc = _over(min(1, (t - 0.9) / 0.35))
            sf = _font(int(110 * sc))
            sw = d.textlength(score, font=sf)
            d.text(((W - sw) / 2, 1180), score, font=sf, fill=(255, 255, 255))
        # scorer typewriter
        if t > 1.3:
            n = int((t - 1.3) / 0.08)
            txt = f"{scorer} {minute}"[:n]
            tf = _font(64)
            tw = d.textlength(txt + "|", font=tf)
            d.text(((W - tw) / 2, 1350), txt + ("|" if t % 0.6 < 0.3 else ""),
                   font=tf, fill=(255, 255, 255))
        vf = _font(30, False)
        vw = d.textlength(f"vs {vs}", font=vf)
        d.text(((W - vw) / 2, 1470), f"vs {vs}", font=vf, fill=(180, 185, 192))
        return im
    return _render(frame, out, duration)


# ── 1b. GOAL REEL — alert slam + LIVE pitch replay + closing stamp ─────────
def goal_reel(out, club="pirates", scorer="LUNGU", minute="60'",
              score="1-0", vs="Chippa United",
              replay=None, duration_replay=6.5,
              narration_audio=None, stamp_dur=2.5):
    """TOP-CLASS goal content: 3s alert slam -> animated pitch replay with
    moving players and ball -> 2.5s closing stamp. `replay` is a dict:
    {players: {...Board players...}, start: {pid:(fx,fy)},
     moves: [(pid, (fx,fy))...], ball: [(t,(fx,fy))...],
     arrow: ((fx,fy),(fx,fy),label)} — times inside the replay window."""
    from PIL import Image, ImageDraw
    from moviepy import VideoFileClip, concatenate_videoclips
    from modules.tactics_board import Board

    out = Path(out)
    work = out.parent
    crest = _crest(club, 300)
    ball_ic = icon("ball", 170)
    fire_ic = icon("fire", 110)

    # phase A: alert slam (3.0s)
    def frame_a(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), "GOAL ALERT", font=_font(28, False), fill=GOLD)
        for k in range(12):
            ang = k * math.pi / 6 + t * 0.8
            alpha = int(45 + 30 * math.sin(t * 3 + k))
            d.line([W // 2, 640, W // 2 + int(900 * math.cos(ang)),
                    640 + int(900 * math.sin(ang))],
                   fill=(*GOLD, alpha), width=18)
        u = _ease(min(1, t / 0.45))
        s = 3.0 - 2.0 * u
        if crest:
            c = crest.resize((max(1, int(crest.width * s)),
                              max(1, int(crest.height * s))))
            im.paste(c, (W // 2 - c.width // 2, 640 - c.height // 2), c)
        if ball_ic:                      # ball spins in from the side
            bu = _ease(min(1, max(0, (t - 0.2) / 0.6)))
            bx = int(-200 + (W // 2 + 260 + 200) * bu)
            rb = ball_ic.rotate((t * 360) % 360)
            im.paste(rb, (bx - 85, 560), rb)
        if t > 0.5:
            g = _over(min(1, (t - 0.5) / 0.4))
            gf = _font(int(150 * g))
            gw = d.textlength("GOAL!", font=gf)
            d.text(((W - gw) / 2, 950), "GOAL!", font=gf, fill=GOLD)
        if t > 0.9:
            sc = _over(min(1, (t - 0.9) / 0.35))
            sf = _font(int(110 * sc))
            sw = d.textlength(score, font=sf)
            d.text(((W - sw) / 2, 1160), score, font=sf, fill=(255, 255, 255))
        if t > 1.3:
            n = int((t - 1.3) / 0.07)
            txt = f"{scorer} {minute}"[:n]
            tf = _font(64)
            tw = d.textlength(txt, font=tf)
            d.text(((W - tw) / 2, 1330), txt, font=tf, fill=(255, 255, 255))
        vf = _font(30, False)
        vw = d.textlength(f"vs {vs}", font=vf)
        d.text(((W - vw) / 2, 1450), f"vs {vs}", font=vf, fill=(180, 185, 192))
        return im

    a_path = _render(frame_a, work / "_ga.mp4", 3.0)

    # phase B: pitch replay with moving players + ball
    b_path = None
    if replay:
        b = Board(replay["players"], accent=GOLD,
                  title=f"THE GOAL — {scorer} {minute}",
                  subtitle="watch the move")
        b.keyframe(0.3, replay["start"])
        # movers get their targets; everyone else AUTO-BALANCES around them
        b.keyframe_balanced(duration_replay * 0.55,
                            dict(replay.get("moves", [])))
        if replay.get("ball"):
            b.ball(replay["ball"])
        if replay.get("arrow"):
            (a1, a2, lab) = replay["arrow"]
            b.arrow(0.6, duration_replay * 0.5, a1, a2, label=lab)
        b.stat(duration_replay * 0.62, duration_replay, score,
               f"{scorer} {minute}")
        b_path = b.render(work / "_gb.mp4", duration=duration_replay)

    # phase C: closing stamp (2.5s)
    def frame_c(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        if crest:
            im.paste(crest, (W // 2 - crest.width // 2, 480), crest)
        if fire_ic:
            im.paste(fire_ic, (W // 2 - 55, 830), fire_ic)
        u = _over(min(1, t / 0.4))
        sf = _font(int(120 * u))
        sw = d.textlength(score, font=sf)
        d.text(((W - sw) / 2, 980), score, font=sf, fill=GOLD)
        cf = _font(38)
        cta = "FOLLOW GENESIS NEWS FOR EVERY GOAL"
        cw = d.textlength(cta, font=cf)
        d.text(((W - cw) / 2, 1200), cta, font=cf, fill=(255, 255, 255))
        return im

    c_path = _render(frame_c, work / "_gc.mp4", stamp_dur)

    parts = [VideoFileClip(a_path)] + \
        ([VideoFileClip(b_path)] if b_path else []) + [VideoFileClip(c_path)]
    final = concatenate_videoclips(parts)
    if narration_audio:
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
            voice = AudioFileClip(str(narration_audio))
            final = final.with_audio(
                CompositeAudioClip([voice]).with_duration(final.duration))
        except Exception as e:
            print(f"[GoalReel] audio skipped: {e}")
    final.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac" if narration_audio else None,
                          audio=bool(narration_audio),
                          logger=None, preset="medium")
    return str(out)


# ── 2. CARD ALERT ──────────────────────────────────────────────────────────
def card_alert(out, player="JONES", minute="42'", red=False,
               club="chippa", duration=5.0):
    from PIL import Image, ImageDraw
    col = (220, 50, 50) if red else (255, 200, 0)
    label = "RED CARD" if red else "YELLOW CARD"

    crest = _crest(club, 150)
    boom = icon("impact", 220)

    def frame(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), label, font=_font(28, False), fill=col)
        # danger vignette pulse
        pulse = int(45 + 35 * abs(math.sin(t * 3)))
        for wdt in range(4):
            d.rectangle([wdt * 8, wdt * 8, W - wdt * 8, H - wdt * 8],
                        outline=(*col, max(0, pulse - wdt * 10)), width=8)
        if crest:
            im.paste(crest, (W - 44 - crest.width, 40), crest)
        # card spins in: rotation 540deg -> 0, y from -400 -> 640
        u = _ease(min(1, t / 0.7))
        card = Image.new("RGBA", (360, 520), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 359, 519], radius=40, fill=col,
                             outline=(255, 255, 255), width=6)
        rot = card.rotate(540 * (1 - u), expand=True,
                          resample=Image.BICUBIC)
        y = int(-500 + (760 - (-500)) * u)
        im.paste(rot, (W // 2 - rot.width // 2, y - rot.height // 2), rot)
        # player token shakes then dims
        shake = math.sin(t * 30) * max(0, 26 - t * 12) if t > 0.7 else 0
        x = W // 2 + int(shake)
        y2 = 1420
        grey = t > 2.2 and red
        tok = (120, 120, 120) if grey else GOLD
        d.ellipse([x - 70, y2 - 70, x + 70, y2 + 70], fill=tok,
                  outline=(255, 255, 255), width=4)
        pf = _font(44)
        pw = d.textlength(player, font=pf)
        d.text(((W - pw) / 2, y2 + 96), player, font=pf,
               fill=(150, 150, 150) if grey else (255, 255, 255))
        mf = _font(56)
        mw = d.textlength(minute, font=mf)
        d.text(((W - mw) / 2, y2 + 170), minute, font=mf, fill=col)
        if red and t > 2.2:
            g = _over(min(1, (t - 2.2) / 0.35))
            if boom:
                b2 = boom.resize((int(220 * g), int(220 * g)))
                im.paste(b2, (W // 2 - b2.width // 2, y2 - 380), b2)
            of = _font(int(64 * g))
            ow = d.textlength("OFF!", font=of)
            d.text(((W - ow) / 2, y2 - 240), "OFF!", font=of, fill=col)
        return im
    return _render(frame, out, duration)


# ── 3. PLAYER SPOTLIGHT ────────────────────────────────────────────────────
def player_spotlight(out, name="RENALDO LEANER", club="chiefs",
                     stats=(("CLEAN SHEETS 25/26", 9, 12),
                            ("LEAGUE APPS", 18, 30),
                            ("BAFANA CALL-UPS", 4, 10)),
                     duration=7.0):
    from PIL import Image, ImageDraw
    crest = _crest(club, 480)

    def frame(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), "PLAYER SPOTLIGHT", font=_font(28, False), fill=GOLD)
        # breathing crest backdrop
        if crest:
            s = 1.0 + 0.04 * math.sin(t * 1.2)
            c = crest.resize((int(crest.width * s), int(crest.height * s)))
            ghost = c.copy()
            ghost.putalpha(60)
            im.paste(ghost, (W // 2 - c.width // 2, 420 - c.height // 2), ghost)
        nf = _font(72)
        nw = d.textlength(name, font=nf)
        d.text(((W - nw) / 2, 700), name, font=nf, fill=(255, 255, 255))
        y = 900
        for i, (label, val, mx) in enumerate(stats):
            t0 = 0.8 + i * 0.55
            u = _ease(min(1, max(0, (t - t0) / 0.9)))
            d.text((90, y), label, font=_font(34), fill=(200, 205, 210))
            barw = int((W - 320) * (val / mx) * u)
            d.rounded_rectangle([90, y + 56, 90 + max(barw, 8), y + 108],
                                radius=16, fill=GOLD)
            # shine sweep across the bar
            if u > 0.15 and barw > 60:
                sx = 90 + int((barw - 40) * ((t * 0.9) % 1.0))
                d.rounded_rectangle([sx, y + 56, sx + 34, y + 108],
                                    radius=16, fill=(255, 255, 255, 90))
            shown = int(round(val * u))
            pop = _over(min(1, max(0, (t - (0.8 + i * 0.55 + 0.9)) / 0.3)))
            d.text((110 + max(barw, 8), y + 56 - int(6 * (pop - 1) * 10)),
                   str(shown), font=_font(int(48 * pop)),
                   fill=(255, 255, 255))
            y += 200
        gl = icon("gloves", 130)
        if gl:
            im.paste(gl, (W - 190, 640), gl)
        return im
    return _render(frame, out, duration)


# ── 4. HEAD TO HEAD ────────────────────────────────────────────────────────
def head_to_head(out, a=("CHAINE", "pirates"), b=("R. WILLIAMS", "sundowns"),
                 stats=(("CLEAN SHEETS", 5, 4), ("SAVES", 21, 18),
                        ("ERRORS", 1, 2)),
                 duration=7.0):
    from PIL import Image, ImageDraw
    ca, cb = _crest(a[1], 190), _crest(b[1], 190)

    def frame(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), "HEAD TO HEAD", font=_font(28, False), fill=GOLD)
        if ca:
            im.paste(ca, (140, 260), ca)
        if cb:
            im.paste(cb, (W - 140 - cb.width, 260), cb)
        for (nm, _c), x in ((a, 140), (b, W - 480)):
            d.text((x if x == 140 else W - 140 - d.textlength(nm, _font(44)),
                    500), nm, font=_font(44), fill=(255, 255, 255))
        vf = _font(64)
        vw = d.textlength("VS", font=vf)
        d.text(((W - vw) / 2, 330), "VS", font=vf, fill=GOLD)
        y = 700
        mid = W // 2
        for i, (label, va, vb) in enumerate(stats):
            t0 = 0.7 + i * 0.6
            u = _ease(min(1, max(0, (t - t0) / 1.0)))
            lw = d.textlength(label, font=_font(34))
            d.text(((W - lw) / 2, y), label, font=_font(34),
                   fill=(200, 205, 210))
            mxv = max(va, vb) or 1
            wa = int((mid - 140) * (va / mxv) * u)
            wb = int((mid - 140) * (vb / mxv) * u)
            win_a, win_b = va >= vb, vb >= va
            d.rounded_rectangle([mid - 20 - wa, y + 56, mid - 20, y + 110],
                                radius=14,
                                fill=GOLD if win_a else (90, 95, 102))
            d.rounded_rectangle([mid + 20, y + 56, mid + 20 + wb, y + 110],
                                radius=14,
                                fill=GOLD if win_b else (90, 95, 102))
            d.text((mid - 90 - wa, y + 60), str(int(round(va * u))),
                   font=_font(44), fill=(255, 255, 255))
            d.text((mid + 40 + wb, y + 60), str(int(round(vb * u))),
                   font=_font(44), fill=(255, 255, 255))
            # winner star pops when the race lands
            star = icon("star", 64)
            if star and u >= 1:
                sp = _over(min(1, (t - (0.7 + i * 0.6 + 1.0)) / 0.3))
                s2 = star.resize((int(64 * sp), int(64 * sp)))
                if va > vb:
                    im.paste(s2, (mid - 60 - wa - 70, y + 52), s2)
                elif vb > va:
                    im.paste(s2, (mid + 40 + wb + 70, y + 52), s2)
            y += 220
        if t > duration - 1.6:
            u2 = _over(min(1, (t - (duration - 1.6)) / 0.35))
            vf2 = _font(int(46 * u2))
            msg = "YOUR VERDICT? 👇"
            mw = d.textlength(msg.replace("👇", ""), font=vf2)
            d.rounded_rectangle([(W - mw) / 2 - 26, 1560,
                                 (W + mw) / 2 + 26, 1650], radius=18,
                                fill=GOLD)
            d.text(((W - mw) / 2, 1578), msg.replace(" 👇", ""),
                   font=vf2, fill=(12, 12, 12))
        return im
    return _render(frame, out, duration)


# ── 5. TRANSFER MOVE ───────────────────────────────────────────────────────
def transfer_move(out, player="THABO CELE", from_club="chiefs",
                  to_club="amazulu", fee="CONTRACT TERMINATED",
                  duration=6.0):
    from PIL import Image, ImageDraw
    cfrom, cto = _crest(from_club, 260), _crest(to_club, 260)

    def frame(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), "TRANSFER NEWS", font=_font(28, False), fill=GOLD)
        if cfrom:
            im.paste(cfrom, (110, 640), cfrom)
        if cto:
            im.paste(cto, (W - 110 - cto.width, 640), cto)
        # token slides on an arc
        u = _ease(min(1, max(0, (t - 0.6) / 1.6)))
        x = int(240 + (W - 480) * u)
        y = int(780 - 240 * math.sin(u * math.pi))
        d.ellipse([x - 64, y - 64, x + 64, y + 64], fill=GOLD,
                  outline=(255, 255, 255), width=5)
        d.line([240, 780, x, y], fill=(*GOLD, 130), width=8)
        nf = _font(64)
        nw = d.textlength(player, font=nf)
        d.text(((W - nw) / 2, 1080), player, font=nf, fill=(255, 255, 255))
        # dotted flight trail
        for k in range(10):
            uu = _ease(min(1, max(0, (t - 0.6) / 1.6))) * (k / 10)
            tx = int(240 + (W - 480) * uu)
            ty = int(780 - 240 * math.sin(uu * math.pi))
            d.ellipse([tx - 6, ty - 6, tx + 6, ty + 6],
                      fill=(*GOLD, 120 - k * 10))
        if t > 2.4:
            g = _over(min(1, (t - 2.4) / 0.4))
            boom = icon("impact", 150)
            if boom:
                b2 = boom.resize((int(150 * g), int(150 * g)))
                im.paste(b2, (W // 2 - b2.width // 2, 1080), b2)
            ff = _font(int(52 * g))
            fw = d.textlength(fee, font=ff)
            d.rounded_rectangle([(W - fw) / 2 - 30, 1230,
                                 (W + fw) / 2 + 30, 1340], radius=18,
                                fill=(10, 10, 12, 230))
            d.text(((W - fw) / 2, 1250), fee, font=ff, fill=GOLD)
        return im
    return _render(frame, out, duration)


# ── 6. QUOTE KINETIC ───────────────────────────────────────────────────────
def quote_kinetic(out, quote="WE FEAR NOBODY IN THIS LEAGUE",
                  author="Inácio Miguel — before the Sundowns clash",
                  club="chiefs", duration=6.5):
    from PIL import Image, ImageDraw
    crest = _crest(club, 220)
    words = quote.split()

    def frame(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), "THEY SAID IT", font=_font(28, False), fill=GOLD)
        if crest:
            im.paste(crest, (W // 2 - crest.width // 2, 300), crest)
        # words punch in one at a time, wrapped
        shown = int(t / 0.38)
        lines, cur = [], []
        for wd in words[:shown]:
            cur.append(wd)
            test = " ".join(cur)
            if d.textlength(test, font=_font(76)) > W - 160:
                lines.append(" ".join(cur[:-1]))
                cur = [wd]
        lines.append(" ".join(cur))
        y = 640
        for li, line in enumerate(lines):
            is_last = li == len(lines) - 1
            pop = _over(min(1, (t - shown * 0.38 + 0.38) / 0.3)) \
                if is_last and shown <= len(words) else 1.0
            lf = _font(int(76 * pop))
            lw = d.textlength(line, font=lf)
            d.text(((W - lw) / 2, y), line, font=lf,
                   fill=GOLD if li % 2 else (255, 255, 255))
            y += 120
        # oversized quote marks framing the words
        qf = _font(200)
        d.text((60, 480), '"', font=qf, fill=(*GOLD, 120))
        d.text((W - 190, y + 10), '"', font=qf, fill=(*GOLD, 120))
        if shown >= len(words):
            af = _font(30, False)
            aw = d.textlength(author, font=af)
            d.text(((W - aw) / 2, y + 80), author, font=af,
                   fill=(200, 205, 210))
            fire = icon("fire", 110)
            if fire:
                fg = _over(min(1, (t - len(words) * 0.38 - 0.3) / 0.4))
                f2 = fire.resize((int(110 * fg), int(110 * fg)))
                if f2.width > 1:
                    im.paste(f2, (W // 2 - f2.width // 2, y + 160), f2)
        return im
    return _render(frame, out, duration)


# ── 7. COUNTDOWN ───────────────────────────────────────────────────────────
def countdown(out, title="SUNDOWNS v GALLANTS", when="WEDNESDAY 19:30",
              clubs=("sundowns", "gallants"), start_secs=3 * 3600 + 254,
              duration=7.0):
    from PIL import Image, ImageDraw
    ca, cb = _crest(clubs[0], 240), _crest(clubs[1], 240)

    def frame(t):
        im = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(im, "RGBA")
        _base(d)
        d.text((46, 96), "MATCHDAY COUNTDOWN", font=_font(28, False),
               fill=GOLD)
        if ca:
            im.paste(ca, (150, 420), ca)
        if cb:
            im.paste(cb, (W - 150 - cb.width, 420), cb)
        vf = _font(60)
        vw = d.textlength("VS", font=vf)
        d.text(((W - vw) / 2, 500), "VS", font=vf, fill=GOLD)
        tf = _font(54)
        tw = d.textlength(title, font=tf)
        d.text(((W - tw) / 2, 780), title, font=tf, fill=(255, 255, 255))
        std = icon("stadium", 500)
        if std:
            ghost = std.copy()
            ghost.putalpha(40)
            im.paste(ghost, (W // 2 - 250, 1380), ghost)
        secs = max(0, int(start_secs - t))
        hh, mm, ss = secs // 3600, (secs % 3600) // 60, secs % 60
        # flip-card digit pairs (HH : MM : SS on dark cards)
        pairs = [f"{hh:02d}", f"{mm:02d}", f"{ss:02d}"]
        cf = _font(120)
        cardw, gap = 250, 60
        x0 = (W - (cardw * 3 + gap * 2)) // 2
        for i, pair in enumerate(pairs):
            cx = x0 + i * (cardw + gap)
            d.rounded_rectangle([cx, 940, cx + cardw, 1140], radius=24,
                                fill=(10, 10, 12, 235),
                                outline=(*GOLD, 140), width=3)
            d.line([cx + 14, 1040, cx + cardw - 14, 1040],
                   fill=(60, 62, 70), width=3)
            pw2 = d.textlength(pair, font=cf)
            d.text((cx + (cardw - pw2) / 2, 968), pair, font=cf, fill=GOLD)
            lbl = ("HOURS", "MINUTES", "SECONDS")[i]
            lf = _font(22, False)
            lw2 = d.textlength(lbl, font=lf)
            d.text((cx + (cardw - lw2) / 2, 1156), lbl, font=lf,
                   fill=(180, 185, 192))
        wf = _font(38, False)
        ww = d.textlength(when, font=wf)
        d.text(((W - ww) / 2, 1180), when, font=wf, fill=(220, 224, 228))
        pulse = 0.5 + 0.5 * abs(math.sin(t * 2))
        bar_w = int((W - 200) * pulse)
        d.rounded_rectangle([(W - bar_w) / 2, 1320, (W + bar_w) / 2, 1336],
                            radius=8, fill=(*GOLD, 160))
        return im
    return _render(frame, out, duration)
