"""
Pre-match reel — the fixture, both clubs' real form, and our question.

There is no invented head-to-head here. ESPN's feed only carries the current
season, and these two clubs have not met in it, so a "won 4 of the last 5"
line would be fabrication. What IS verifiable is stronger anyway: the live
table, each side's results this season, and the gap between them.

    python build_prematch.py --dry-run
    python build_prematch.py --post
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import httpx  # noqa: E402

OUT = Path("output/prematch")
NICHE = "sa_pulse"
ESPN_TEAMS = "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/teams"


async def team_id(name_part: str) -> str | None:
    async with httpx.AsyncClient(timeout=45) as c:
        r = (await c.get(ESPN_TEAMS)).json()
    for t in r["sports"][0]["leagues"][0]["teams"]:
        if name_part.lower() in t["team"]["displayName"].lower():
            return t["team"]["id"]
    return None


async def season_form(tid: str, club_name: str) -> tuple[list[str], str]:
    """(result letters newest-first, a readable summary) from real results."""
    async with httpx.AsyncClient(timeout=45) as c:
        r = (await c.get(f"{ESPN_TEAMS}/{tid}/schedule")).json()
    out = []
    for ev in r.get("events", []):
        cs = ev["competitions"][0]["competitors"]
        try:
            mine = next(x for x in cs
                        if club_name.split()[-1].lower()
                        in x["team"]["displayName"].lower())
            them = next(x for x in cs if x is not mine)
            a = int(mine["score"]["displayValue"])
            b = int(them["score"]["displayValue"])
        except Exception:
            continue
        out.append(("W" if a > b else "D" if a == b else "L",
                    f"{a}-{b}", them["team"]["shortDisplayName"]))
    out.reverse()
    letters = [o[0] for o in out]
    # SPOKEN form must be words. "W 3-1 v Kruger" was read out as the letter
    # "W", which sounds like a typo being narrated.
    say = {"W": "won", "D": "drew", "L": "lost"}
    summary = ", ".join(
        f"{say.get(o[0], o[0])} {o[1].replace('-', ' ')} against {o[2]}"
        for o in out[:3])
    return letters, summary, out


async def main(post: bool, club: str = ""):
    from modules.motion_kit import attach_voice, countdown, head_to_head
    from modules.music_bed import add_bed
    from modules.psl_fixtures import SAST, fixtures_for, priority
    from modules.psl_standings import get_log
    from moviepy import VideoFileClip, concatenate_videoclips

    now = datetime.now(SAST)
    fixture = None
    for dd in range(0, 9):
        for f in (await fixtures_for(now + timedelta(days=dd))) or []:
            if club and club not in (f.get("home_key"), f.get("away_key")):
                continue
            if priority(f) >= 1 and not f.get("completed"):
                when = datetime.fromisoformat(f["kickoff_iso"])
                if when > now:
                    fixture = (f, when)
                    break
        if fixture:
            break
    if not fixture:
        print("[Prematch] no upcoming big-three fixture")
        return 1
    f, when = fixture
    print(f"[Prematch] {f['home']} v {f['away']} — {when:%a %d %b %H:%M}")

    rows = await get_log(top=16)
    by = {r["team_key"]: r for r in rows}
    hk, ak = f.get("home_key"), f.get("away_key")
    h, a = by.get(hk), by.get(ak)
    if not (h and a):
        print("[Prematch] league table missing a side — refusing to guess")
        return 1

    hid, aid = await team_id(f["home"]), await team_id(f["away"])
    hform, hsum, hres = (await season_form(hid, f["home"]) if hid
                         else ([], "", []))
    aform, asum, ares = (await season_form(aid, f["away"]) if aid
                         else ([], "", []))
    print(f"[Prematch] {f['home']}: {''.join(hform) or '-'} | "
          f"{f['away']}: {''.join(aform) or '-'}")

    OUT.mkdir(parents=True, exist_ok=True)
    secs = max(60, int((when - now).total_seconds()))
    short = (lambda n: n.replace("Mamelodi ", "").replace("Orlando ", "")
             .replace("Kaizer ", "").replace(" FC", "").upper())

    part1 = countdown(OUT / "p1.mp4",
                      title=f"{short(f['home'])} VS {short(f['away'])}",
                      when=when.strftime("%A %d %B · %H:%M").upper(),
                      clubs=(hk, ak), start_secs=secs, duration=6.5)

    def ppg(r):
        return round(r["points"] / r["played"], 1) if r.get("played") else 0
    stats = (("POINTS", h["points"], a["points"]),
             ("POINTS PER GAME", ppg(h), ppg(a)),
             ("MATCHES PLAYED", h["played"], a["played"]))
    part2 = head_to_head(OUT / "p2.mp4",
                         a=(short(f["home"]), hk), b=(short(f["away"]), ak),
                         stats=stats, duration=7.5)

    from modules.motion_kit import form_compare
    unbeaten = [c for c in (h, a) if c]
    note = ""
    if hres and all(x[0] != "L" for x in hres):
        note = f"{h['name'].upper()} UNBEATEN THIS SEASON"
    elif ares and all(x[0] != "L" for x in ares):
        note = f"{a['name'].upper()} UNBEATEN THIS SEASON"
    part3 = form_compare(OUT / "p3.mp4",
                         club_a=(short(f["home"]), hk),
                         club_b=(short(f["away"]), ak),
                         form_a=hres, form_b=ares, note=note, duration=8.0)

    silent = OUT / "prematch_silent.mp4"
    clips = [VideoFileClip(part1), VideoFileClip(part2), VideoFileClip(part3)]
    concatenate_videoclips(clips, method="compose").write_videofile(
        str(silent), fps=30, codec="libx264", audio=False, logger=None)
    for c in clips:
        c.close()

    narr = (
        f"{f['home']} against {f['away']}, {when:%A} at {when:%H:%M}"
        + (f", at {f['venue']}. " if f.get("venue") else ". ")
        + f"{h['name']} sit {h['rank']} on {h['points']} points. "
        + f"{a['name']} sit {a['rank']} on {a['points']}. "
        + (f"{h['name']} so far: {hsum}. " if hsum else "")
        + "What is your score prediction? Drop it in the comments before "
          "kick-off. Subscribe to Genesis News — we call every game."
    )
    voiced = await attach_voice(str(silent), narr, str(OUT / "voiced.mp4"))
    final = add_bed(voiced, OUT / "prematch.mp4", NICHE, 14.0)
    print(f"[Prematch] built: {final}")

    if not post:
        print("[Prematch] built only — not posted")
        return 0

    cap = (f"⏳ {f['home'].upper()} VS {f['away'].upper()}\n"
           f"{when:%A %d %B} · {when:%H:%M}"
           + (f" · {f['venue']}" if f.get("venue") else "") + "\n\n"
           f"{h['name']} — {h['rank']} on {h['points']} pts\n"
           f"{a['name']} — {a['rank']} on {a['points']} pts\n"
           + (f"\nForm: {hsum}\n" if hsum else "")
           + "\nYour score prediction 👇⚽\n"
             "#PSL #BetwayPremiership #KaizerChiefs")
    from modules.uploader_facebook import post_comment, upload_to_facebook
    fb = await upload_to_facebook(video_path=str(final),
                                  title=f"{f['home']} VS {f['away']} — preview",
                                  description=cap, niche=NICHE, is_reel=True)
    print(f"[Prematch] Facebook: {fb.get('status')} {fb.get('post_id')}")
    vid = fb.get("video_id") or fb.get("post_id")
    if vid and fb.get("status") == "uploaded":
        await post_comment(vid, "Score prediction before kick-off — we hold "
                                "you to it at full time 👇", NICHE)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--club", default="", help="only this club's fixture")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.post and not a.dry_run, a.club)))
