"""
Genesis News — long-form PSL show for YouTube (~5 min, 1920x1080).

Watch-time structure, every segment a chapter:
  1. HOOK        — the fixture, the stakes                      (~25s)
  2. THE LOG     — live Betway table, read like a broadcast     (~45s)
  3. XI HOME     — predicted XI walkthrough (real recent starts)(~55s)
  4. XI AWAY     — same for the opponent                        (~55s)
  5. THE STORIES — today's sourced headlines as analysis        (~60s)
  6. OUR CALL    — score + scorer prediction, debate bait       (~30s)
  7. OUTRO       — subscribe + what's next                      (~20s)

All data is LIVE (ESPN squads/log/fixtures, sourced headlines) and every visual
reuses the card design language. Narration is template-built from that data —
factual by construction, no API spend — and read by the same af_heart voice.

Usage:
    python build_psl_show.py               # build only
    python build_psl_show.py --post        # build then upload to YouTube
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import OUTPUT_DIR
from modules.club_brand import CLUB_BRAND, official_badge

W, H = 1920, 1080
NICHE = "sa_pulse"
LOGO = Path(__file__).parent / "assets" / "youtube_branding" / "logo_sa_pulse.png"


def _log(m):
    print(f"[SHOW] {m}", flush=True)


def _font(size, bold=True):
    for p in (["C:/Windows/Fonts/arialbd.ttf"] if bold else ["C:/Windows/Fonts/arial.ttf"]):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit(img, box):
    r = min(box / img.width, box / img.height)
    return img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))),
                      Image.LANCZOS)


def _canvas(bg_path=None, tint=(12, 14, 18)):
    c = Image.new("RGBA", (W, H), tint + (255,))
    if bg_path:
        try:
            img = Image.open(bg_path).convert("RGB")
            s = max(W / img.width, H / img.height)
            img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
            img = img.crop(((img.width - W) // 2, (img.height - H) // 2,
                            (img.width - W) // 2 + W, (img.height - H) // 2 + H))
            c.alpha_composite(img.filter(ImageFilter.GaussianBlur(6)).convert("RGBA"))
            c.alpha_composite(Image.new("RGBA", (W, H), (8, 10, 14, 175)))
        except Exception:
            pass
    return c


def _brand(c, d, sub=""):
    try:
        if LOGO.exists():
            lg = Image.open(LOGO).convert("RGBA").resize((120, 120), Image.LANCZOS)
            c.alpha_composite(lg, (46, 34))
    except Exception:
        pass
    d.text((182, 52), "GENESIS NEWS", font=_font(48), fill=(255, 255, 255))
    d.text((184, 110), sub or "PSL & MZANSI FOOTBALL", font=_font(26, bold=False),
           fill=(200, 205, 210))


def _crest(c, club, cx, cy, box=260):
    b = official_badge(club)
    if not b:
        return
    crest = _fit(Image.open(b).convert("RGBA"), box)
    disc = box + 44
    panel = Image.new("RGBA", (disc, disc), (0, 0, 0, 0))
    ImageDraw.Draw(panel).ellipse([0, 0, disc - 1, disc - 1], fill=(255, 255, 255, 242))
    c.alpha_composite(panel, (cx - disc // 2, cy - disc // 2))
    c.alpha_composite(crest, (cx - crest.width // 2, cy - crest.height // 2))


def seg_title_card(out, title, home, away, line, bg=None):
    c = _canvas(bg)
    d = ImageDraw.Draw(c)
    _brand(c, d)
    if home:
        _crest(c, home, W // 2 - 330, 400)
    if away:
        _crest(c, away, W // 2 + 330, 400)
        vf = _font(120)
        vw = d.textlength("VS", font=vf)
        d.text((W // 2 - vw / 2 + 5, 345), "VS", font=vf, fill=(0, 0, 0))
        d.text((W // 2 - vw / 2, 340), "VS", font=vf, fill=(255, 193, 7))
    f = _font(84)
    words, lines, cur = title.split(), [], []
    for w in words:
        if d.textlength(" ".join(cur + [w]), font=f) <= W - 360 or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur)); cur = [w]
    lines.append(" ".join(cur))
    y = 640
    for ln in lines[:3]:
        lw = d.textlength(ln, font=f)
        d.text(((W - lw) / 2 + 4, y + 4), ln, font=f, fill=(0, 0, 0))
        d.text(((W - lw) / 2, y), ln, font=f, fill=(255, 255, 255))
        y += 100
    if line:
        lf = _font(40)
        lw = d.textlength(line, font=lf)
        d.rounded_rectangle([W / 2 - lw / 2 - 36, 960, W / 2 + lw / 2 + 36, 1034],
                            radius=20, fill=(10, 12, 16, 225))
        d.text(((W - lw) / 2, 976), line, font=lf, fill=(255, 255, 255))
    c.convert("RGB").save(out, quality=95)
    return str(out)


def seg_log_table(out, rows, highlight=(), bg=None):
    c = _canvas(bg)
    d = ImageDraw.Draw(c)
    _brand(c, d)
    tf = _font(72)
    d.text((120, 210), "THE BETWAY LOG", font=tf, fill=(255, 193, 7))
    row_h, y0 = 88, 330
    x1, x2 = 120, W - 120
    hf = _font(34)
    for label, x in (("#", x1 + 30), ("CLUB", x1 + 130), ("P", x2 - 420),
                     ("PTS", x2 - 200)):
        d.text((x, y0 - 50), label, font=hf, fill=(150, 155, 162))
    for i, r in enumerate(rows[:8]):
        y = y0 + i * row_h
        hot = r.get("team_key") in highlight
        if hot:
            acc = tuple(CLUB_BRAND.get(r["team_key"], {}).get("colors", {})
                        .get("primary", (255, 193, 7)))
            d.rounded_rectangle([x1, y - 8, x2, y + row_h - 20], radius=14, fill=acc)
        fg = (10, 10, 10) if hot else (235, 238, 242)
        rf = _font(40)
        d.text((x1 + 30, y), str(r["rank"]), font=rf, fill=fg)
        d.text((x1 + 130, y), r["name"], font=rf, fill=fg)
        d.text((x2 - 420, y), str(r["played"]), font=rf, fill=fg)
        d.text((x2 - 200, y), str(r["points"]), font=rf, fill=fg)
    c.convert("RGB").save(out, quality=95)
    return str(out)


def seg_xi(out, club, players, formation, predicted=True, bg=None):
    """Landscape XI: portrait pitch card centred, club identity side panels."""
    from modules.lineup_card import make_lineup_card
    tmp = Path(out).with_suffix(".portrait.png")
    make_lineup_card(tmp, club=club, players=players, formation=formation,
                     predicted=predicted)
    c = _canvas(bg, tint=tuple(CLUB_BRAND.get(club, {}).get("colors", {})
                               .get("primary", (16, 18, 22))))
    c.alpha_composite(Image.new("RGBA", (W, H), (8, 10, 14, 170)))
    d = ImageDraw.Draw(c)
    _brand(c, d)
    card = Image.open(tmp).convert("RGBA")
    card = card.resize((int(card.width * (H - 40) / card.height), H - 40),
                       Image.LANCZOS)
    c.alpha_composite(card, ((W - card.width) // 2, 20))
    _crest(c, club, 220, 420, box=240)
    d = ImageDraw.Draw(c)
    name = CLUB_BRAND.get(club, {}).get("name", club).upper()
    nf = _font(44)
    for i, wln in enumerate(name.split()):
        d.text((220 - d.textlength(wln, font=nf) / 2, 580 + i * 54), wln,
               font=nf, fill=(255, 255, 255))
    ff = _font(76)
    d.text((W - 220 - d.textlength(formation, font=ff) / 2, 380), formation,
           font=ff, fill=(255, 193, 7))
    lbl = "PREDICTED XI" if predicted else "STARTING XI"
    lf = _font(34)
    d.text((W - 220 - d.textlength(lbl, font=lf) / 2, 480), lbl, font=lf,
           fill=(255, 255, 255))
    tmp.unlink(missing_ok=True)
    c.convert("RGB").save(out, quality=95)
    return str(out)


def seg_headlines(out, items, bg=None):
    c = _canvas(bg)
    d = ImageDraw.Draw(c)
    _brand(c, d)
    d.text((120, 200), "THE STORIES THAT MATTER", font=_font(64), fill=(255, 193, 7))
    y = 330
    hf, sf = _font(44), _font(28, bold=False)
    for it in items[:4]:
        d.rounded_rectangle([120, y, W - 120, y + 150], radius=18,
                            fill=(16, 18, 24, 235))
        t = it.get("title", "")
        while d.textlength(t, font=hf) > W - 320 and len(t) > 10:
            t = t[:-5].rstrip() + "…"
        d.text((156, y + 28), t, font=hf, fill=(240, 243, 247))
        d.text((156, y + 92), f"Source: {it.get('source', 'sourced report')}",
               font=sf, fill=(160, 166, 174))
        y += 178
    c.convert("RGB").save(out, quality=95)
    return str(out)


def seg_prediction(out, home, away, pred_text, bg=None):
    c = _canvas(bg)
    d = ImageDraw.Draw(c)
    _brand(c, d)
    _crest(c, home, W // 2 - 380, 380, box=300)
    _crest(c, away, W // 2 + 380, 380, box=300)
    d = ImageDraw.Draw(c)
    tf = _font(96)
    t = "OUR CALL"
    d.text(((W - d.textlength(t, font=tf)) / 2, 150), t, font=tf, fill=(255, 193, 7))
    pf = _font(64)
    words, lines, cur = pred_text.split(), [], []
    for wd in words:
        if d.textlength(" ".join(cur + [wd]), font=pf) <= W - 400 or not cur:
            cur.append(wd)
        else:
            lines.append(" ".join(cur)); cur = [wd]
    lines.append(" ".join(cur))
    y = 640
    for ln in lines[:3]:
        lw = d.textlength(ln, font=pf)
        d.text(((W - lw) / 2 + 4, y + 4), ln, font=pf, fill=(0, 0, 0))
        d.text(((W - lw) / 2, y), ln, font=pf, fill=(255, 255, 255))
        y += 82
    cf = _font(40)
    cta = "Drop YOUR scoreline in the comments"
    d.text(((W - d.textlength(cta, font=cf)) / 2, 930), cta, font=cf,
           fill=(200, 205, 212))
    c.convert("RGB").save(out, quality=95)
    return str(out)


async def build_show(post=False):
    from modules.psl_fixtures import fixtures_for, SAST, priority
    from modules.psl_standings import get_log
    from modules.psl_squads import predict_xi2, get_squad
    from modules.psl_news import get_psl_briefing
    from modules.cc_clips import fetch_cc_clip
    from build_psl_news import _make_prediction, _frames_from_clip

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(OUTPUT_DIR) / f"psl_show_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    # ── live data ──
    now = datetime.now(SAST)
    fixture = None
    for dd in range(0, 3):
        fx = [f for f in await fixtures_for(now + timedelta(days=dd))
              if priority(f) >= 1 and not f["completed"]]
        if fx:
            fixture = sorted(fx, key=priority, reverse=True)[0]
            break
    if not fixture:
        raise SystemExit("no upcoming big-three fixture in 3 days — show is preview-mode only for now")
    home, away = fixture["home_key"], fixture["away_key"]
    hn = CLUB_BRAND.get(home, {}).get("name", home)
    an = CLUB_BRAND.get(away, {}).get("name", away)
    ko = f"{fixture['kickoff_sast']}" + (f" · {fixture['venue']}" if fixture['venue'] else "")
    log_rows = await get_log(8)
    xi_h, form_h = await predict_xi2(home, force_refresh=True)
    xi_a, form_a = await predict_xi2(away, force_refresh=True)
    briefing = await get_psl_briefing()
    stories = []
    for k in (home, away, "premiership"):
        for it in (briefing.get(k) or [])[:2]:
            if isinstance(it, dict) and it.get("title"):
                stories.append(it)
    pred = await _make_prediction(f"{hn} vs {an}", log_rows) or f"OUR CALL: {hn.upper()} 2-1"
    _log(f"fixture: {hn} vs {an} {ko} | pred: {pred}")

    # ── real footage for backgrounds ──
    bg = None
    clip = await fetch_cc_clip(f"{hn} highlights", work / "cc")
    if clip:
        frames = _frames_from_clip({**clip, "club": home}, work, 2)
        if frames:
            bg = frames[0]["path"]

    # ── narration (template = factual by construction) ──
    def side(players, n=5):
        return ", ".join(p.split(None, 1)[-1] for p in players[:n])

    rank = {r["team_key"]: r for r in log_rows}
    rh, ra = rank.get(home), rank.get(away)
    segs = [
        ("HOOK",
         f"{hn} against {an}. {ko}. This is the game the whole of Mzansi has "
         f"circled, and Genesis News has everything you need before kickoff: "
         f"the log, both predicted line-ups, the stories driving the build-up, "
         f"and our call. Stay with us."),
        ("THE LOG",
         (f"Start with the table. {hn} sit {_ord(rh['rank'])} on {rh['points']} points "
          f"from {rh['played']} games. " if rh else "") +
         (f"{an} are {_ord(ra['rank'])} with {ra['points']} points from "
          f"{ra['played']}. " if ra else "") +
         "Early season, yes — but log pressure is real pressure, and whoever "
         "takes this one buys breathing room and bragging rights."),
        (f"{hn.upper()} XI",
         f"Our predicted {hn} line-up, in a {form_h}. Between the posts and at "
         f"the back: {side(xi_h[:5], 5)}. In the middle and up top: "
         f"{side(xi_h[5:], 6)}. Every name here is in the current squad and "
         f"picked on real recent starts — players carrying injury news are out."),
        (f"{an.upper()} XI",
         f"And the {an} shape, a {form_a}. The spine: {side(xi_a[:5], 5)}. "
         f"Going forward: {side(xi_a[5:], 6)}. Same rules — current squad, "
         f"recent selection, no injured names."),
        ("THE STORIES",
         "Now the build-up talk. " + " ".join(
             f"{s.get('title', '').rstrip('.')}." for s in stories[:4]) +
         " Full credits to the outlets on screen — we report what South "
         "African football media actually published."),
        ("OUR CALL",
         f"{pred.replace('OUR CALL:', 'So here is our call:')}. That is a "
         f"prediction, not a promise — and if you see it differently, the "
         f"comments are open. Drop your scoreline and your first scorer."),
        ("OUTRO",
         f"That's the preview. Lineups the moment the team sheets drop, and "
         f"the full-time card the second it ends — follow Genesis News on "
         f"Facebook and subscribe here on YouTube. {hn}, {an} — Mzansi, "
         f"enjoy the football."),
    ]
    narration = " ".join(t for _n, t in segs)
    _log(f"narration: {len(narration.split())} words")

    # ── voice (one continuous read) ──
    from modules.voice_generator import generate_voice
    voice = await generate_voice(narration, work, "show_voice", "short", NICHE)
    if not voice:
        raise SystemExit("voice failed")

    # ── visuals ──
    title = f"{hn} vs {an}: Full Preview, Predicted XIs & Our Call"
    paths = [
        seg_title_card(work / "seg1.png", f"{hn} vs {an} — The Full Preview",
                       home, away, ko, bg),
        seg_log_table(work / "seg2.png", log_rows, highlight=(home, away), bg=bg),
        seg_xi(work / "seg3.png", home, xi_h, form_h, bg=bg),
        seg_xi(work / "seg4.png", away, xi_a, form_a, bg=bg),
        seg_headlines(work / "seg5.png", stories, bg=bg),
        seg_prediction(work / "seg6.png", home, away,
                       pred.replace("OUR CALL: ", ""), bg=bg),
        seg_title_card(work / "seg7.png", "Lineups · Results · Every Matchday",
                       home, away, "FOLLOW GENESIS NEWS · SUBSCRIBE", bg),
    ]

    # ── assemble: durations proportional to segment word counts ──
    from moviepy import (AudioFileClip, ImageClip, CompositeVideoClip,
                        CompositeAudioClip, concatenate_videoclips)
    audio = AudioFileClip(voice["audio_path"])
    total_words = sum(len(t.split()) for _n, t in segs)
    clips = []
    for p, (_name, text) in zip(paths, segs):
        dur = audio.duration * len(text.split()) / total_words
        clips.append(ImageClip(p).with_duration(dur))
    video = concatenate_videoclips(clips, method="compose").with_duration(audio.duration)
    tracks = [audio]
    try:
        from modules.video_assembler import _get_music_track
        mp = _get_music_track(niche=NICHE)
        if mp and Path(mp).exists():
            bed = AudioFileClip(mp)
            if bed.duration < audio.duration:
                from moviepy import concatenate_audioclips
                bed = concatenate_audioclips([bed] * (int(audio.duration // bed.duration) + 1))
            tracks.append(bed.subclipped(0, audio.duration).with_volume_scaled(0.08))
    except Exception as e:
        _log(f"music skipped: {e}")
    video = video.with_audio(CompositeAudioClip(tracks).with_duration(audio.duration))
    out = work / "show.mp4"
    video.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac",
                          preset="medium", threads=4, logger=None)
    _log(f"show rendered: {out} ({audio.duration:.0f}s)")

    # ── chapters + description ──
    t = 0.0
    chapters = []
    for (name, text) in segs:
        chapters.append(f"{int(t // 60)}:{int(t % 60):02d} {name.title()}")
        t += audio.duration * len(text.split()) / total_words
    desc = (f"{hn} vs {an} — full preview: live Betway log, both predicted XIs "
            f"(current squads, real recent starts, injuries excluded), the "
            f"build-up stories, and our score call.\n\nChapters:\n" +
            "\n".join(chapters) +
            "\n\nFollow Genesis News for lineups before kickoff and full-time "
            "results.\n#PSL #BetwayPremiership #KaizerChiefs #MamelodiSundowns")

    if post:
        from modules.uploader_youtube import upload_to_youtube
        r = await upload_to_youtube(
            video_path=str(out), title=title, description=desc,
            tags=["PSL", "BetwayPremiership", "KaizerChiefs", "MamelodiSundowns",
                  "OrlandoPirates", "SouthAfricanFootball"],
            niche=NICHE, thumbnail_path=paths[0], is_short=False,
            srt_path=voice.get("subtitle_path"))
        _log(f"YouTube: {r.get('status')} {r.get('url', '')}")
    _log("SHOW COMPLETE")
    return str(out)


def _ord(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    asyncio.run(build_show(post=a.post))
