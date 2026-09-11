"""
MATCHDAY — the crest, the question, and nothing else in the way.

Owner call 2026-08-26: on a Chiefs matchday, post the crest and ask how many
Amakhosi are here. Make it the best-edited thing on the page.

This is the one format that carries no team sheet, no shape and no argument.
It is a roll call. Everything on screen serves one question, and the question
is the cheapest engagement there is — a fan who scrolls past a debate will
still tell you they are here.

It only builds when Chiefs actually play TODAY, unless --force. A matchday post
on a day with no match is the same error as the predicted XI against a fixture
already played, and it is the one thing that makes a page look automated.

THREE KINDS since 2026-09-11 (owner: "the fans pride works better... add the
Pirates and Chiefs fans debate... trophies, hopes... very smart and beautiful to
watch"). One reel engine, because this reel is what took 3,332 likes and 1,025
comments; the kind changes the staging, never the one-question discipline:

    --kind pride     one crest lands, embers and hearts, ROLL CALL / MATCHDAY
    --kind rivalry   both crests land from opposite sides, VS slams between
                     them, a KHOSI / BUCS bar swings under them: FAN DEBATE
    --kind hopes     one crest with gold stars orbiting it: THE BIG QUESTION

Editing notes, because "make it the best" is the brief:
  · crests arrive on an overshoot, not a fade — they should land, not appear
  · a pulse ring leaves each crest on every beat
  · embers drift up the frame the whole way through, so no frame is static
  · the question is set in the largest type the frame will carry
  · club gold on near-black; the rival gets silver, never a third colour

    python build_matchday_hype.py --club chiefs
    python build_matchday_hype.py --club chiefs --force --kind rivalry
    python build_matchday_hype.py --club chiefs --force --kind hopes --post
"""
import argparse
import asyncio
import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()
from modules.render_spec import FPS

ROOT = Path(__file__).parent
NICHE = "sa_pulse"
W, H = 1080, 1920
SAST = timezone(timedelta(hours=2))
KINDS = ("pride", "rivalry", "hopes")
RIVAL = {"chiefs": "pirates", "pirates": "chiefs"}
# Pirates' white would glare against near-black and fight the question text;
# a cool silver reads as "the other side" and keeps gold the hero colour.
RIVAL_TONE = (208, 214, 226)
# Two crests and a VS across 1080px. At 380px and 300/780 the VS sat on top of
# both badges; this leaves a clear 220px lane down the middle for it.
DUO_X = (262, 818)
DUO_SIZE = 340


def _log(m):
    print(f"[Matchday] {m}", flush=True)


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


def _overshoot(u):
    """Ease-out-back. The crest lands with a bounce instead of drifting in."""
    u = max(0.0, min(1.0, u))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _glow(im, spots):
    """Soft colour washes behind everything, so the frame is never flat black.

    Drawn and blurred at quarter size, then scaled up: a 150px blur on the
    full 1080x1920 frame was the most expensive call in the whole render, and
    a blur that wide has no detail for the lost resolution to remove.
    """
    from PIL import Image, ImageDraw, ImageFilter
    q = 4
    glow = Image.new("RGBA", (W // q, H // q), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for cx, cy, rad, col in spots:
        gd.ellipse([(cx - rad) / q, (cy - rad) / q, (cx + rad) / q,
                    (cy + rad) / q], fill=col + (46,))
    glow = glow.filter(ImageFilter.GaussianBlur(150 / q)).resize((W, H))
    return Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")


def _embers(d, t, accent, n=46, rival=None):
    """Slow upward drift, and every third one is a HEART.

    Owner 2026-09-03, looking at the numbers: this format took 72 likes and 16
    comments while the tactics simulator took 1 to 9 - "we can always show the
    heart emojis from start, middle and end, as the fans respond with love and
    pride."

    The embers already run the whole length of the reel, which is exactly the
    "start, middle and end" he is asking for, so the hearts ride the same drift
    rather than being a new effect bolted on at the goal. One in three, in club
    gold and a warmer red, so it reads as affection rather than confetti.

    On a rivalry reel the plain embers take the colour of the side of the frame
    they rise through, so the two halves read as two crowds. Hearts stay ours.

    Deterministic from the index so it never flickers between frames.
    """
    from modules.tactics_board import _heart
    for i in range(n):
        seed = (i * 9301 + 49297) % 233280 / 233280.0
        x = (seed * 1.7 % 1.0) * W
        speed = 34 + (seed * 60)
        y = (H + 80) - ((t * speed + seed * H * 1.6) % (H + 160))
        a = int(70 + 120 * (0.5 + 0.5 * math.sin(t * 1.6 + i)))
        if i % 3 == 0:
            sz = 26 + seed * 30
            col = accent + (a,) if i % 6 else (232, 74, 92, a)
            _heart(d, x, y, sz, col)
        else:
            r = 2 + (seed * 5)
            col = rival if (rival and x > W / 2) else accent
            d.ellipse([x - r, y - r, x + r, y + r], fill=col + (a,))


def _land(im, crest, cx, cy, t, t0, ring_col, slide=0, spread=0.9):
    """Drop a crest in on an overshoot from t0, let it breathe, pulse a ring."""
    from PIL import ImageDraw
    if crest is None or t < t0:
        return im
    lt = t - t0
    u = _overshoot(min(1.0, lt / 0.85))
    scale = 0.25 + 0.75 * u + 0.02 * math.sin(t * 2.0)
    cw = max(8, int(crest.width * scale))
    ch = max(8, int(crest.height * scale))
    x = cx + int(slide * (1 - _ease(lt / 0.6)))
    d = ImageDraw.Draw(im, "RGBA")
    if lt > 0.9:
        ring = (lt * 0.9) % 1.0
        rr = int(cw * (0.55 + ring * spread))
        d.ellipse([x - rr, cy - rr, x + rr, cy + rr],
                  outline=ring_col + (int(150 * (1 - ring)),), width=6)
    cr = crest.resize((cw, ch))
    im.paste(cr, (x - cw // 2, cy - ch // 2), cr)
    return im


def _vs(d, t, t0, accent, cx=W // 2, cy=690):
    """VS slams in between the crests, with a white shock ring on impact."""
    if t < t0:
        return
    lt = t - t0
    if lt < 0.6:
        k = lt / 0.6
        r = int(60 + 520 * k)
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  outline=(255, 255, 255, int(190 * (1 - k))),
                  width=2 + int(10 * (1 - k)))
    u = _overshoot(min(1.0, lt / 0.35))
    size = max(40, int(112 * (1 + 1.3 * (1 - u)) + 4 * math.sin(t * 4.0)))
    d.text((cx, cy), "VS", font=_font(size), anchor="mm",
           fill=accent + (int(255 * min(1.0, lt / 0.15)),),
           stroke_width=8, stroke_fill=(9, 10, 13, 255))


def _tug(d, t, t0, accent, rival, left, right):
    """A bar that swings between the two crowds and never settles.

    No numbers on it, deliberately: it is an invitation to pick a side, not a
    poll result, and a figure here would be a claim we cannot back.
    """
    if t < t0:
        return
    u = _ease(min(1.0, (t - t0) / 0.5))
    a = int(255 * u)
    x0, x1, y = 90, W - 90, 928
    split = W / 2 + (90 * math.sin(t * 1.3) + 35 * math.sin(t * 3.1 + 1)) * u
    d.rounded_rectangle([x0, y, split, y + 18], radius=9, fill=accent + (a,))
    d.rounded_rectangle([split, y, x1, y + 18], radius=9, fill=rival + (a,))
    d.ellipse([split - 17, y - 8, split + 17, y + 26],
              fill=(255, 255, 255, a), outline=(9, 10, 13, a), width=4)
    f = _font(34)
    d.text((x0, y + 36), left, font=f, fill=accent + (a,))
    d.text((x1 - d.textlength(right, font=f), y + 36), right, font=f,
           fill=rival + (a,))
    mf = _font(26, False)
    mid = "PICK A SIDE"
    d.text((W / 2 - d.textlength(mid, font=mf) / 2, y + 42), mid, font=mf,
           fill=(226, 232, 240, int(200 * u)))


def _star(d, cx, cy, r, fill):
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rad = r if k % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(pts, fill=fill)


def _orbit(d, t, t0, accent, front, cx=W // 2, cy=700, n=6, radius=410):
    """Gold stars circling the crest on a tilted ring - the trophy hope.

    Drawn in two passes around the crest paste, so the stars on the far side
    of the ring pass BEHIND the badge and the near ones in front of it.
    """
    if t < t0:
        return
    u = _ease(min(1.0, (t - t0) / 0.6))
    for k in range(n):
        ang = t * 0.6 + k * 2 * math.pi / n
        if (math.sin(ang) > 0) != front:
            continue
        x = cx + radius * math.cos(ang)
        y = cy + radius * 0.34 * math.sin(ang)
        tw = 0.65 + 0.35 * math.sin(t * 3 + k)
        depth = 0.75 + 0.25 * math.sin(ang)
        _star(d, x, y, (16 + 16 * tw) * depth,
              accent + (int(235 * u * tw * depth),))


def frame(t, ctx):
    from PIL import Image, ImageDraw
    accent = ctx["accent"]
    kind = ctx.get("kind", "pride")
    rival = ctx.get("rival_accent", RIVAL_TONE)
    im = Image.new("RGB", (W, H), (9, 10, 13))

    pulse = 0.5 + 0.5 * math.sin(t * 2.0)
    if kind == "rivalry":
        im = _glow(im, [(DUO_X[0], 690, int(320 + 30 * pulse), accent),
                        (DUO_X[1], 690, int(320 + 30 * (1 - pulse)), rival)])
    else:
        im = _glow(im, [(W // 2, 700, int(430 + 40 * pulse), accent)])
    d = ImageDraw.Draw(im, "RGBA")   # RGB base => alpha actually blends
    _embers(d, t, accent, rival=rival if kind == "rivalry" else None)

    # ── crests ──
    if kind == "rivalry":
        # Tight rings: at the single-crest spread two rings crossed the whole
        # frame and ran through the question text.
        im = _land(im, ctx["crest"], DUO_X[0], 690, t, 0.0, accent,
                   slide=-220, spread=0.35)
        im = _land(im, ctx.get("rival_crest"), DUO_X[1], 690, t, 0.3, rival,
                   slide=220, spread=0.35)
        d = ImageDraw.Draw(im, "RGBA")
        _vs(d, t, 1.05, accent)
        _tug(d, t, 1.4, accent, rival, ctx.get("left_label", "KHOSI"),
             ctx.get("right_label", "BUCS"))
    elif kind == "hopes":
        _orbit(d, t, 0.9, accent, front=False)
        im = _land(im, ctx["crest"], W // 2, 700, t, 0.0, accent)
        d = ImageDraw.Draw(im, "RGBA")
        _orbit(d, t, 0.9, accent, front=True)
    else:
        im = _land(im, ctx["crest"], W // 2, 700, t, 0.0, accent)
        d = ImageDraw.Draw(im, "RGBA")

    # ── strap: MATCHDAY / ROLL CALL / FAN DEBATE / THE BIG QUESTION ──
    if t > 0.7:
        u = _ease(min(1.0, (t - 0.7) / 0.5))
        f = _font(74)
        txt = ctx.get("strap", "MATCHDAY")
        while d.textlength(txt, font=f) > W - 160 and f.size > 40:
            f = _font(f.size - 2)
        tw = d.textlength(txt, font=f)
        y = 250 - int(40 * (1 - u))
        d.rounded_rectangle([W // 2 - tw / 2 - 40, y - 16,
                             W // 2 + tw / 2 + 40, y + 92], radius=18,
                            fill=accent + (int(255 * u),))
        d.text((W // 2 - tw / 2, y + 4), txt, font=f,
               fill=(16, 16, 16, int(255 * u)))
        sf = _font(34, False)
        st = ctx["kick_line"]
        sw = d.textlength(st, font=sf)
        d.text((W // 2 - sw / 2, y + 118), st, font=sf,
               fill=(226, 232, 240, int(230 * u)))

    # ── the question, largest type the frame will carry ──
    if t > 1.6:
        u = _ease(min(1.0, (t - 1.6) / 0.6))
        # The ask ROTATES. This is the page's best-performing card, and the
        # reason it works is that it asks a supporter for something almost
        # free - but an ask seen four times in a fortnight stops being an
        # invitation and becomes wallpaper. Format stays, words move.
        lines = ctx.get("ask_lines") or ["HOW MANY", "KAIZER CHIEFS",
                                         "FANS ARE HERE?"]
        # LAYOUT AGAINST THE CAPTION BAND. attach_voice burns subtitles into a
        # fixed band at y 1490-1750 (build_psl_news CAPTION_BOTTOM_MARGIN and
        # assemble_full CAP_H). The CTA pill used to sit at 1470-1560 and the
        # brand at 1620, so a two-line caption covered the call to action and
        # every caption covered GENESIS NEWS. Question and pill now finish
        # above the band; the brand sits below it.
        y = 1030
        for i, ln in enumerate(lines):
            f = _font(96 if i != 1 else 86)
            while d.textlength(ln, font=f) > W - 80 and f.size > 40:
                f = _font(f.size - 2)
            tw = d.textlength(ln, font=f)
            col = accent if i == 1 else (255, 255, 255)
            off = int(30 * (1 - _ease(min(1.0, (t - 1.6 - i * 0.12) / 0.5))))
            d.text((W // 2 - tw / 2 + 3, y + off + 3), ln, font=f,
                   fill=(0, 0, 0, int(140 * u)))
            d.text((W // 2 - tw / 2, y + off), ln, font=f,
                   fill=col + (int(255 * u),))
            y += f.size + 22

    # ── call to action ──
    if t > 3.0:
        u = _ease(min(1.0, (t - 3.0) / 0.5))
        cta = ctx.get("ask_cta") or "COMMENT  ·  SAY KHOSI"
        f = _font(44)
        while d.textlength(cta, font=f) > W - 150 and f.size > 28:
            f = _font(f.size - 2)
        tw = d.textlength(cta, font=f)
        d.rounded_rectangle([W // 2 - tw / 2 - 34, 1392, W // 2 + tw / 2 + 34, 1476],
                            radius=20, fill=(255, 255, 255, int(24 * u)))
        d.text((W // 2 - tw / 2, 1434), cta, font=f, anchor="lm",
               fill=(255, 255, 255, int(240 * u)))

    bf = _font(30)
    d.text((W // 2 - d.textlength("GENESIS NEWS", font=bf) / 2, 1790),
           "GENESIS NEWS", font=bf, fill=accent + (210,))
    d.rectangle([0, H - 12, W, H], fill=accent)
    return im


def _crest_image(club, size):
    from PIL import Image
    from modules.club_brand import official_badge
    bp = official_badge(club)
    if not bp:
        return None
    crest = Image.open(bp).convert("RGBA")
    r = size / max(crest.width, crest.height)
    return crest.resize((int(crest.width * r), int(crest.height * r)))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--kind", default="pride", choices=KINDS,
                    help="pride roll call, fan rivalry debate, or season hopes")
    ap.add_argument("--force", action="store_true",
                    help="build even if there is no match today")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_matchday_hype.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    from modules.club_brand import CLUB_BRAND
    from modules.psl_fixtures import next_fixture

    fx = await next_fixture(a.club)
    if not fx:
        _log("no upcoming fixture")
        return 1
    ko = datetime.fromisoformat(fx["kickoff_iso"])
    now = datetime.now(SAST)
    if ko.date() != now.date() and not a.force:
        _log(f"next match is {ko:%a %d %b}, not today — refusing to post "
             f"MATCHDAY on a day with no match (use --force to override)")
        return 1

    kind = a.kind
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
    opp = CLUB_BRAND.get(opp_key, {}).get("name",
                                          opp_key.replace("_", " ").title())
    home = fx["home_key"] == a.club
    rival_key = RIVAL.get(a.club, "pirates")
    rival_name = CLUB_BRAND.get(rival_key, {}).get("name", rival_key.title())
    rival_short = rival_name.split()[-1]          # "Pirates"
    is_today = ko.date() == now.date()
    days = (ko.date() - now.date()).days
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    fixture_line = f"{'vs' if home else 'away to'} {opp}  ·  {ko:%a %H:%M}"
    derby = opp_key == rival_key

    crest = _crest_image(a.club, DUO_SIZE if kind == "rivalry" else 560)
    from modules.rollcall_asks import next_ask, share_nudge, key_of
    picked = next_ask(kind)
    ask_lines, ask_cta, ask_spoken = picked
    ask = " ".join(ask_lines)
    _log(f"{kind} ask: " + " / ".join(ask_lines))

    ctx = {
        "kind": kind,
        "accent": tuple(CLUB_BRAND.get(a.club, {}).get("colors", {})
                        .get("primary", (255, 193, 7))),
        "crest": crest,
        "ask_lines": ask_lines,
        "ask_cta": ask_cta,
    }
    if kind == "rivalry":
        ctx.update({
            "rival_crest": _crest_image(rival_key, DUO_SIZE),
            "rival_accent": RIVAL_TONE,
            "left_label": "KHOSI" if a.club == "chiefs" else club_name.upper(),
            "right_label": "BUCS" if rival_key == "pirates" else rival_short.upper(),
            "strap": "FAN DEBATE",
            # Not a fixture line: two crests and a VS already look like a
            # match, so the line under the strap says plainly what this is.
            "kick_line": (f"THE SOWETO DERBY  ·  {ko:%a %d %b}" if derby
                          else "NO NEUTRALS  ·  THE FANS DECIDE"),
        })
    elif kind == "hopes":
        ctx.update({"strap": "THE BIG QUESTION",
                    "kick_line": f"NEXT: {fixture_line}"})
    elif is_today:
        ctx.update({"strap": "MATCHDAY",
                    "kick_line": f"{'vs' if home else 'away to'} {opp}  ·  "
                                 f"{ko:%H:%M}  ·  {fx.get('venue', '')}".strip(" ·")})
    else:
        # The strap used to say MATCHDAY on every roll call, including the
        # forced between-games ones - the same false claim the caption fix
        # below was written to stop, just burned into the picture instead.
        ctx.update({"strap": "ROLL CALL", "kick_line": f"NEXT: {fixture_line}"})
    _log(f"{club_name} {'vs' if home else 'away to'} {opp} — {ko:%a %d %b %H:%M}")

    stamp = now.strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"matchday_{a.club}_{kind}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    # The copy must match the DAY. --force lets this run between fixtures,
    # and the matchday script would then be a plain falsehood - "it is
    # matchday" on a Friday with no game is exactly the class of claim this
    # page has been burned by. So the roll-call has two versions: one for the
    # day itself, one for every other day, and neither invents a match.
    if kind == "rivalry":
        text = (f"{ask_spoken} {club_name} fans, this one is ours. "
                f"{rival_short} fans, you are welcome to try. "
                + (f"And the Soweto derby is {when}. " if derby else "")
                + "Amakhosi for life.")
    elif kind == "hopes":
        text = (f"{ask_spoken} No wrong answers, only reasons. "
                f"{club_name} play {opp} {when}. Amakhosi for life.")
    elif is_today:
        text = (f"It is matchday. {club_name} are "
                f"{'at home to' if home else 'away to'} {opp}, "
                f"kick off {ko:%H:%M}. "
                f"So before anything else — {ask_spoken} "
                f"Amakhosi for life.")
    else:
        text = (f"No game today. So let us do something better. "
                f"{ask_spoken} "
                f"We want to see how many of us there are before "
                f"{club_name} play {opp} {when}. "
                f"Amakhosi for life.")
    dur = max(11.0, len(text.split()) / 2.8 + 2.5)

    from modules.motion_kit import _render, attach_voice
    silent = work / "hype_silent.mp4"
    _render(lambda t: frame(t, ctx), silent, duration=dur, fps=FPS)
    _log(f"video: {dur:.1f}s at {FPS}fps")
    voiced = await attach_voice(silent, text, work / "voiced.mp4")

    # Music bed. NOT a commercial track: a licensed song cannot be sourced or
    # embedded from here, and Content ID would mute or claim the post.
    # One implementation of this, shared with the line-up reel.
    from modules.music_bed import add_bed
    final = add_bed(voiced, work / "final.mp4", NICHE, dur, log=_log)

    cover = work / "cover.jpg"
    frame(4.2, ctx).save(cover, quality=95)

    # THE CAPTION MUST MATCH THE DAY.
    #
    # The narration was made day-aware when --force was added; the caption was
    # not. So two posts went out on 29 and 30 August reading "MATCHDAY —
    # Kaizer Chiefs vs Siwelele FC, 17:30 tonight" when that match is on
    # 6 September. A false claim, live on the page, carried by the format with
    # the most reach on it. Fixing the spoken line and leaving the written one
    # is exactly the half-fix this project keeps paying for.
    #
    # The caption also carries whichever ask the card shows, verbatim, so the
    # picture, the voice and the text all invite the same thing - and so
    # rollcall_asks can find this post again to learn how the words did.
    nxt = (f"{club_name} {'vs' if home else 'away to'} {opp} {when.upper()} — "
           f"{ko:%a %d %b}, {ko:%H:%M}.")
    hashtag = lambda name: "#" + name.replace(" ", "")
    if kind == "rivalry":
        title = f"{ask} — {club_name} vs {rival_name} fans"
        head = (f"⚔️ FAN DEBATE ⚔️\n\n{club_name} fans vs {rival_name} fans. "
                f"No neutrals in this one.")
        tags = (f"{hashtag(club_name)} #Amakhosi {hashtag(rival_name)} "
                f"#Khosi4Life #SowetoDerby #PSL")
        yt_tags = [club_name.replace(" ", ""), rival_name.replace(" ", ""),
                   "SowetoDerby", "Amakhosi", "PSL"]
    elif kind == "hopes":
        title = f"{ask} — {club_name}"
        head = f"🏆 THE BIG QUESTION 🏆\n\nNext up: {nxt}"
        tags = "#KaizerChiefs #Amakhosi #Khosi4Life #PSL #BetwayPremiership"
        yt_tags = ["KaizerChiefs", "Amakhosi", "PSL", "BetwayPremiership"]
    elif is_today:
        title = f"MATCHDAY — {club_name} {'vs' if home else 'away to'} {opp}"
        head = (f"🟡 MATCHDAY 🟡\n\n{club_name} "
                f"{'vs' if home else 'away to'} {opp} — {ko:%H:%M} tonight, "
                f"{fx.get('venue','')}.")
        tags = "#KaizerChiefs #Amakhosi #Khosi4Life #PSL #MatchDay"
        yt_tags = ["KaizerChiefs", "Amakhosi", "PSL", "MatchDay",
                   "BetwayPremiership"]
    else:
        title = f"{ask} — {club_name}"
        head = f"💛 ROLL CALL 💛\n\nNo game today. {nxt}"
        tags = "#KaizerChiefs #Amakhosi #Khosi4Life #PSL #BetwayPremiership"
        yt_tags = ["KaizerChiefs", "Amakhosi", "PSL", "BetwayPremiership"]
    caption = f"{head}\n\n{ask} 👇\n{ask_cta}\n\n{tags}"

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover),
         "title": title, "description": caption,
         "kind": kind, "ask_key": key_of(picked),
         "built_at": now.isoformat()}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        if kind == "rivalry":
            opener = (f"⚔️ KHOSI or {ctx['right_label']}? Pick your side "
                      f"and give one reason.")
        elif kind == "hopes":
            opener = "🏆 Your call, plus one reason. We read every answer."
        elif is_today:
            opener = "💛 KHOSI! Comment below if you are here for Amakhosi tonight."
        else:
            opener = "💛 KHOSI! Comment below — we are counting the family."
        from modules.publish_reel import publish
        r = await publish(final, title, caption, cover, niche=NICHE,
                          tags=yt_tags,
                          first_comment=(
                              f"{opener}\n{share_nudge(kind)}\n"
                              "▶️ More on YouTube: "
                              "https://www.youtube.com/@GenesisNewsPSL"))
        _log(f"published: { {k: (v or {}).get('status') for k, v in r.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
