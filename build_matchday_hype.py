"""
MATCHDAY — the crest, the question, and nothing else in the way.

Owner call 2026-08-26: on a Chiefs matchday, post the crest and ask how many
Amakhosi are here. Make it the best-edited thing on the page.

This is the one format that carries no team sheet, no shape and no argument.
It is a roll call. Everything on screen serves one question, and the question
is the cheapest engagement there is — a fan who scrolls past a debate will
still tell you they are here.

It only builds when Chiefs actually play TODAY. A matchday post on a day with
no match is the same error as the predicted XI against a fixture already
played, and it is the one thing that makes a page look automated.

Editing notes, because "make it the best" is the brief:
  · the crest arrives on an overshoot, not a fade — it should land, not appear
  · a gold pulse ring leaves it on every beat
  · embers drift up the frame the whole way through, so no frame is static
  · the question is set in the largest type the frame will carry
  · club gold on near-black; no third colour anywhere

    python build_matchday_hype.py --club chiefs
    python build_matchday_hype.py --club chiefs --post
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

ROOT = Path(__file__).parent
NICHE = "sa_pulse"
W, H = 1080, 1920
SAST = timezone(timedelta(hours=2))


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


def _embers(d, t, accent, n=46):
    """Slow upward drift. Deterministic from the index so it never flickers."""
    for i in range(n):
        seed = (i * 9301 + 49297) % 233280 / 233280.0
        x = (seed * 1.7 % 1.0) * W
        speed = 34 + (seed * 60)
        y = (H + 80) - ((t * speed + seed * H * 1.6) % (H + 160))
        r = 2 + (seed * 5)
        a = int(70 + 120 * (0.5 + 0.5 * math.sin(t * 1.6 + i)))
        d.ellipse([x - r, y - r, x + r, y + r], fill=accent + (a,))


def frame(t, ctx):
    from PIL import Image, ImageDraw, ImageFilter
    accent = ctx["accent"]
    im = Image.new("RGB", (W, H), (9, 10, 13))
    d = ImageDraw.Draw(im, "RGBA")

    # radial wash behind everything so the frame is never flat black
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pulse = 0.5 + 0.5 * math.sin(t * 2.0)
    rad = int(430 + 40 * pulse)
    gd.ellipse([W // 2 - rad, 700 - rad, W // 2 + rad, 700 + rad],
               fill=accent + (46,))
    im = Image.alpha_composite(im.convert("RGBA"),
                               glow.filter(ImageFilter.GaussianBlur(150))
                               ).convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")   # RGB base => alpha actually blends
    _embers(d, t, accent)

    # ── crest: lands on an overshoot, then breathes ──
    if ctx["crest"] is not None:
        u = _overshoot(min(1.0, t / 0.85))
        scale = 0.25 + 0.75 * u + 0.02 * math.sin(t * 2.0)
        c = ctx["crest"]
        cw = max(8, int(c.width * scale))
        ch = max(8, int(c.height * scale))
        cx, cy = W // 2, 700
        # pulse ring leaving the crest on the beat
        ring = (t * 0.9) % 1.0
        if t > 0.9:
            rr = int(cw * (0.55 + ring * 0.9))
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                      outline=accent + (int(150 * (1 - ring)),), width=6)
        cr = c.resize((cw, ch))
        im.paste(cr, (cx - cw // 2, cy - ch // 2), cr)
        d = ImageDraw.Draw(im, "RGBA")

    # ── MATCHDAY strap ──
    if t > 0.7:
        u = _ease(min(1.0, (t - 0.7) / 0.5))
        f = _font(74)
        txt = "MATCHDAY"
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
        lines = ["HOW MANY", "KAIZER CHIEFS", "FANS ARE HERE?"]
        y = 1060
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
                   fill=col + (int(255 * u),) if len(col) == 3 else col)
            y += f.size + 22

    # ── call to action ──
    if t > 3.0:
        u = _ease(min(1.0, (t - 3.0) / 0.5))
        cta = "COMMENT  ·  SAY KHOSI"
        f = _font(44)
        tw = d.textlength(cta, font=f)
        d.rounded_rectangle([W // 2 - tw / 2 - 34, 1470, W // 2 + tw / 2 + 34, 1560],
                            radius=20, fill=(255, 255, 255, int(24 * u)))
        d.text((W // 2 - tw / 2, 1492), cta, font=f,
               fill=(255, 255, 255, int(240 * u)))

    bf = _font(30)
    d.text((W // 2 - d.textlength("GENESIS NEWS", font=bf) / 2, 1620),
           "GENESIS NEWS", font=bf, fill=accent + (210,))
    d.rectangle([0, H - 12, W, H], fill=accent)
    return im


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--force", action="store_true",
                    help="build even if there is no match today")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    try:
        from modules.gpu_guard import preflight
        preflight("build_matchday_hype.py")
    except Exception as e:
        print(f"[GPUGuard] skipped: {e}")

    from modules.club_brand import CLUB_BRAND, official_badge
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

    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
    opp = CLUB_BRAND.get(opp_key, {}).get("name",
                                          opp_key.replace("_", " ").title())
    home = fx["home_key"] == a.club

    from PIL import Image
    crest = None
    bp = official_badge(a.club)
    if bp:
        crest = Image.open(bp).convert("RGBA")
        r = 560 / max(crest.width, crest.height)
        crest = crest.resize((int(crest.width * r), int(crest.height * r)))

    ctx = {
        "accent": tuple(CLUB_BRAND.get(a.club, {}).get("colors", {})
                        .get("primary", (255, 193, 7))),
        "crest": crest,
        "kick_line": f"{'vs' if home else 'away to'} {opp}  ·  "
                     f"{ko:%H:%M}  ·  {fx.get('venue', '')}".strip(" ·"),
    }
    _log(f"{club_name} {'vs' if home else 'away to'} {opp} — {ko:%a %d %b %H:%M}")

    stamp = now.strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"matchday_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    # The copy must match the DAY. --force lets this run between fixtures,
    # and the matchday script would then be a plain falsehood - "it is
    # matchday" on a Friday with no game is exactly the class of claim this
    # page has been burned by. So the roll-call has two versions: one for the
    # day itself, one for every other day, and neither invents a match.
    is_today = ko.date() == now.date()
    if is_today:
        text = (f"It is matchday. {club_name} are "
                f"{'at home to' if home else 'away to'} {opp}, "
                f"kick off {ko:%H:%M}. "
                f"So before anything else — how many Kaizer Chiefs fans are "
                f"here? Drop a heart, say Khosi, and let us see the numbers. "
                f"Amakhosi for life.")
    else:
        days = (ko.date() - now.date()).days
        when = ("tomorrow" if days == 1 else f"in {days} days")
        text = (f"No game today. So let us do something better. "
                f"How many Kaizer Chiefs fans are here right now? "
                f"If you love this club, drop a heart. Just a heart. "
                f"We want to see how many of us there are before "
                f"{club_name} play {opp} {when}. "
                f"Amakhosi for life.")
    dur = max(11.0, len(text.split()) / 2.8 + 2.5)

    from modules.motion_kit import _render, attach_voice
    silent = work / "hype_silent.mp4"
    _render(lambda t: frame(t, ctx), silent, duration=dur, fps=30)
    _log(f"video: {dur:.1f}s at 30fps")
    voiced = await attach_voice(silent, text, work / "voiced.mp4")

    # Music bed. NOT a commercial track — see the note at the top of the file:
    # a licensed song cannot be sourced or embedded from here, and Content ID
    # would mute or claim the post. ACE-Step generates the bed locally, so it
    # is ours to use and costs nothing.
    # One implementation of this, shared with the line-up reel.
    from modules.music_bed import add_bed
    final = add_bed(voiced, work / "final.mp4", NICHE, dur, log=_log)

    cover = work / "cover.jpg"
    frame(4.2, ctx).save(cover, quality=95)

    title = f"MATCHDAY — {club_name} {'vs' if home else 'away to'} {opp}"
    caption = (f"🟡 MATCHDAY 🟡\n\n{club_name} "
               f"{'vs' if home else 'away to'} {opp} — {ko:%H:%M} tonight, "
               f"{fx.get('venue','')}.\n\n"
               f"HOW MANY KAIZER CHIEFS FANS ARE HERE? 👇\n"
               f"Drop a 💛 and say KHOSI.\n\n"
               f"#KaizerChiefs #Amakhosi #Khosi4Life #PSL "
               f"#BetwayPremiership #MatchDay")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover),
         "title": title, "description": caption,
         "built_at": now.isoformat()}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    _log(f"BUILD COMPLETE: {final}")

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, title, caption, cover, niche=NICHE,
                          tags=["KaizerChiefs", "Amakhosi", "PSL", "MatchDay",
                                "BetwayPremiership"],
                          first_comment=("💛 KHOSI! Comment below if you are "
                                         "here for Amakhosi tonight.\n"
                                         "▶️ More on YouTube: "
                                         "https://www.youtube.com/@GenesisNewsPSL"))
        _log(f"published: { {k: (v or {}).get('status') for k, v in r.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
