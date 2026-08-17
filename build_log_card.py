"""
The Betway Log post — the full table as a shareable card.

Fans screenshot league tables more than any other graphic. Full 16 teams,
big-three rows in club colours, movement arrows vs the last posted table.
Posted after each weekend round (Mon 09:00) and on demand.

Usage: python build_log_card.py [--post]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
SNAP = Path("data/log_snapshot.json")
LOGO = Path("assets/youtube_branding/logo_sa_pulse.png")
BIG = {"chiefs": (255, 193, 7), "pirates": (235, 235, 235),
       "sundowns": (255, 205, 30)}


def _font(size, bold=True):
    try:
        return ImageFont.truetype(
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


async def build(post: bool):
    from modules.psl_standings import get_log
    rows = await get_log(16, force_refresh=True)
    if not rows:
        print("[Log] no standings")
        return
    try:
        raw = json.loads(SNAP.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    # snapshot v1 was {key: rank}; v2 is {"ranks": {...}, "points": {...}}
    prev = raw.get("ranks", raw) if isinstance(raw, dict) else {}
    prev_pts = raw.get("points", {}) if isinstance(raw, dict) else {}

    # FRESHNESS GUARD — ESPN's table lags finished matchdays by a few hours.
    # A full round was played since the last card, so if every team's points
    # are identical to the snapshot the table simply hasn't updated yet:
    # posting it would show a week with zero movement. Wait (30-min steps,
    # up to 4h) instead of publishing a stale log.
    if post and prev_pts:
        import asyncio as _aio
        cur = {r["team_key"]: r["points"] for r in rows}
        for attempt in range(8):
            if any(cur.get(k) != prev_pts.get(k) for k in cur):
                break
            print(f"[Log] table unchanged vs last post — ESPN stale, "
                  f"waiting 30min ({attempt + 1}/8)")
            await _aio.sleep(1800)
            rows = await get_log(16, force_refresh=True)
            cur = {r["team_key"]: r["points"] for r in rows}
        else:
            print("[Log] still stale after 4h — posting anyway with live data")

    img = Image.new("RGB", (W, H), (12, 14, 18))
    d = ImageDraw.Draw(img)
    for i in range(140):
        a = 1 - i / 140
        d.line([(0, i), (W, i)], fill=(int(30 * a) + 12, int(60 * a) + 14,
                                       int(30 * a) + 18))
    try:
        lg = Image.open(LOGO).convert("RGBA").resize((110, 110))
        img.paste(lg, (44, 30), lg)
    except Exception:
        pass
    d.text((172, 44), "GENESIS NEWS", font=_font(40), fill=(255, 255, 255))
    d.text((174, 94), "THE BETWAY LOG", font=_font(26, False), fill=(255, 193, 7))
    stamp = datetime.now().strftime("%d %b %Y")
    sf = _font(26, False)
    d.text((W - 44 - d.textlength(stamp, font=sf), 60), stamp, font=sf,
           fill=(180, 185, 192))

    hf = _font(26)
    y0 = 200
    for label, x in (("#", 70), ("CLUB", 210), ("P", 700), ("PTS", 820),
                     ("", 960)):
        d.text((x, y0 - 46), label, font=hf, fill=(150, 155, 162))
    row_h = 96
    rf, pf = _font(34), _font(34)
    mf = _font(28)
    for i, r in enumerate(rows):
        y = y0 + i * row_h
        key = r.get("team_key", "")
        hot = key in BIG
        if hot:
            acc = BIG[key]
            d.rounded_rectangle([44, y - 8, W - 44, y + row_h - 24], radius=16,
                                fill=acc)
            fg = (10, 10, 10)
        else:
            if i % 2 == 0:
                d.rounded_rectangle([44, y - 8, W - 44, y + row_h - 24],
                                    radius=16, fill=(19, 22, 28))
            fg = (232, 236, 242)
        d.text((70, y + 8), str(r["rank"]), font=rf, fill=fg)
        d.text((210, y + 8), r["name"][:20], font=rf, fill=fg)
        d.text((700, y + 8), str(r["played"]), font=pf, fill=fg)
        d.text((820, y + 8), str(r["points"]), font=pf, fill=fg)
        # movement vs last posted table
        old = prev.get(key or r["name"])
        if old:
            diff = old - r["rank"]
            if diff > 0:
                d.polygon([(966, y + 34), (986, y + 34), (976, y + 14)],
                          fill=(60, 190, 90))          # up
            elif diff < 0:
                d.polygon([(966, y + 14), (986, y + 14), (976, y + 34)],
                          fill=(215, 65, 65))          # down
            else:
                d.rectangle([966, y + 22, 986, y + 28], fill=(120, 126, 134))

    foot = "Where does YOUR team finish this season? 👇"
    ff = _font(30)
    d.text(((W - d.textlength(foot.replace('👇', ''), font=ff)) / 2, H - 120),
           foot.replace(" 👇", ""), font=ff, fill=(255, 193, 7))

    out = Path("output/matchday") / f"log_{datetime.now():%Y%m%d}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=95)
    print(f"[Log] card -> {out}")

    SNAP.parent.mkdir(parents=True, exist_ok=True)
    SNAP.write_text(json.dumps({
        "ranks": {r.get("team_key") or r["name"]: r["rank"] for r in rows},
        "points": {r.get("team_key") or r["name"]: r["points"] for r in rows},
    }, indent=2), encoding="utf-8")
    if post:
        from matchday import _post_photo
        top = rows[0]
        caption = (f"📊 THE BETWAY LOG — {stamp}\n\n{top['name']} lead on "
                   f"{top['points']} points. Where does your team finish this "
                   f"season?\n\n#PSL #BetwayPremiership #KaizerChiefs "
                   f"#OrlandoPirates #MamelodiSundowns")
        await _post_photo(str(out), caption,
                          "Call your team's final position — screenshot this and "
                          "we'll check back in May 👇")

        # THE LOG RACE — the same table, animated: rows glide from last
        # week's positions, arrows pulse. Posted as a reel after the card.
        try:
            from modules.log_race import render_log_race
            from modules.uploader_facebook import upload_to_facebook, post_comment
            race = render_log_race(rows, prev,
                                   Path("output/matchday") /
                                   f"lograce_{datetime.now():%Y%m%d}.mp4")
            # every animated piece speaks (owner rule 2026-08-17)
            movers_up = [r for r in rows
                         if prev.get(r.get("team_key") or r["name"],
                                     r["rank"]) > r["rank"]][:3]
            call = "The log race after this round. "
            if movers_up:
                call += " ".join(
                    f"{m['name']} climb to number {m['rank']}."
                    for m in movers_up) + " "
            call += (f"{rows[0]['name']} lead the Betway Premiership on "
                     f"{rows[0]['points']} points. Where does your team "
                     "finish? Follow Genesis News.")
            from modules.motion_kit import attach_voice
            race = await attach_voice(race, call)
            rcap = (f"🏁 THE LOG RACE — watch this week's movers.\n"
                    f"{top['name']} on top with {top['points']} points.\n\n"
                    "Who climbs next week? 👇⚽\n"
                    "#PSL #BetwayPremiership")
            fb = await upload_to_facebook(video_path=race, title="The Log Race",
                                          description=rcap, niche="sa_pulse",
                                          is_reel=True)
            fb_id = fb.get("video_id") or fb.get("post_id")
            if fb_id and fb.get("status") == "uploaded":
                await post_comment(fb_id, "Screenshot the table and tag a fan "
                                   "whose team is falling 👇😂", "sa_pulse")
            print(f"[Log] LOG RACE posted: {fb_id}")
        except Exception as e:
            print(f"[Log] log race skipped: {str(e)[:120]}")
    return str(out)


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    try:
        asyncio.run(build("--post" in sys.argv))
    except Exception as e:
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure('log-card', f"LOG CARD FAILED: {type(e).__name__}: {str(e)[:140]}")
        except Exception:
            pass
        raise
