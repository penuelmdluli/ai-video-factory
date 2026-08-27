"""
THE ROAD TO NUMBER ONE - what Chiefs actually need, simulated live.

Owner call 2026-08-27: "Chiefs fans are more ahead than their team, they would
love seeing a live simulation that will make them number one at the end of the
season... let them picture it. They love everything Kaizer Chiefs with their
heart."

That is a real appetite and it deserves a real format. The trick is that the
DREAM has to be built out of FACT, or it is worth nothing to the people who
care most.

So every number here is arithmetic on the live league table:

    where Chiefs are now              read from the standings
    how many games remain             30 in the season, minus played
    the points still available        remaining x 3
    what a title has cost before      the target we measure against
    the win rate that gets them there derived, not guessed

Nothing is predicted. The reel does not say Chiefs will win the league; it says
what it would TAKE, which is a fact about the fixture list, and then hands the
question to the fan. That is the difference between letting supporters picture
it and lying to them, and this page has already paid once for the wrong side
of that line.

    python build_title_race.py --club chiefs
    python build_title_race.py --post
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from modules.motion_kit import W, H, GOLD, DARK, _ease, _font  # noqa: E402
from modules.reveal_kit import (  # noqa: E402
    ambient, count_reveal, crest_outro, hold_hook, pending_row, progress_rail,
    scan_loader)

NICHE = "sa_pulse"
SEASON_GAMES = 30          # 16 teams, double round robin
TITLE_TARGET = 62          # what a Premiership title has typically cost


def _stage(t):
    im = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(im)
    for i in range(200):
        a = 1 - i / 200
        d.line([(0, i), (W, i)],
               fill=(int(26 * a) + 12, int(30 * a) + 14, int(38 * a) + 18))
    ambient(d, t)
    return im, d


async def maths(club_key="chiefs"):
    """Every figure derived from the live table. No estimates."""
    from modules.psl_standings import get_log
    rows = await get_log(top=16)
    if not rows:
        return None
    me = next((r for r in rows if r.get("team_key") == club_key), None)
    if not me:
        return None
    leader = rows[0]
    played = int(me.get("played", 0))
    pts = int(me.get("points", 0))
    left = max(0, SEASON_GAMES - played)
    available = left * 3
    need = max(0, TITLE_TARGET - pts)
    # wins required if every non-win is a loss - the honest worst case
    wins_needed = min(left, -(-need // 3))
    return {
        "rank": int(me.get("rank", 0)),
        "points": pts,
        "played": played,
        "left": left,
        "available": available,
        "leader": leader.get("name", ""),
        "leader_points": int(leader.get("points", 0)),
        "gap": int(leader.get("points", 0)) - pts,
        "target": TITLE_TARGET,
        "need": need,
        "wins_needed": wins_needed,
        "possible": pts + available >= TITLE_TARGET,
        "max_points": pts + available,
        "rows": rows[:5],
    }


def beats(m):
    """(label, value, note) - the steps of the simulation, in order."""
    return [
        ("WHERE THEY ARE NOW", f"{m['rank']} — {m['points']} PTS",
         f"{m['played']} PLAYED"),
        ("THE GAP TO TOP", f"{m['gap']} POINTS",
         f"{m['leader'].upper()} LEAD ON {m['leader_points']}"),
        ("GAMES STILL TO PLAY", f"{m['left']}",
         f"{m['available']} POINTS ON THE TABLE"),
        ("WHAT A TITLE COSTS", f"{m['target']} PTS",
         f"THEY NEED {m['need']} MORE"),
        ("WINS THAT GET THEM THERE", f"{m['wins_needed']} OF {m['left']}",
         "IT IS STILL IN THEIR HANDS" if m["possible"]
         else "THE MATHS HAVE GONE"),
    ]


def narration(club_name, m):
    b = beats(m)
    intro = [f"The road to number one. {club_name}, simulated on the real "
             f"table, right now."]
    lines = [
        f"Right now they are {m['rank']} on {m['points']} points, "
        f"{m['played']} games played.",
        f"{m['leader']} lead on {m['leader_points']}. The gap is "
        f"{m['gap']} points.",
        f"There are {m['left']} games left. That is {m['available']} points "
        f"still on the table.",
        f"A Premiership title has cost about {m['target']} points. "
        f"They need {m['need']} more.",
        f"So the number is {m['wins_needed']} wins from {m['left']}. "
        + ("Nothing has been lost yet. It is in their hands."
           if m["possible"] else "That is the mountain."),
    ]
    outro = [
        "That is not a prediction. That is the maths.",
        "Can they do it? Give us your final points total below.",
        "Subscribe to Genesis News. We run this again after every match.",
    ]
    text = " ".join(intro + lines + outro)
    return text, " ".join(intro), lines, " ".join(outro)


def build(club, club_name, m, out_path, scan, crest, per, tail):
    rows = beats(m)
    total = len(rows)
    duration = scan + crest + total * per + tail
    crest_end = scan + crest

    def frame(t):
        im, d = _stage(t)
        f = _font(44)
        d.text((90, 148), "ROAD TO NUMBER ONE", font=f, fill=GOLD)
        f2 = _font(28, False)
        d.text((90, 206), f"{club_name.upper()}  ·  LIVE LEAGUE SIMULATION",
               font=f2, fill=(150, 158, 170))
        d.line([(90, 250), (W - 90, 250)], fill=(46, 50, 58), width=2)

        if t < scan:
            scan_loader(d, t, label="RUNNING THE NUMBERS", cy=H // 2 - 60,
                        done=min(1.0, t / scan), club=club)
            hold_hook(d, t, "CAN THEY STILL WIN IT?", y=H // 2 + 300)
            progress_rail(d, 0, total, label="SIMULATING")
            return np.array(im)

        if t < crest_end:
            # the target, held for a beat
            tf = _font(150)
            txt = str(m["target"])
            u = (t - scan) / max(0.1, crest)
            a = _ease(min(1.0, u * 2))
            c = tuple(int(GOLD[i] * a + DARK[i] * (1 - a)) for i in range(3))
            d.text((W / 2 - d.textlength(txt, font=tf) / 2, H // 2 - 150),
                   txt, font=tf, fill=c)
            sf = _font(44)
            lab = "POINTS WINS THE LEAGUE"
            d.text((W / 2 - d.textlength(lab, font=sf) / 2, H // 2 + 40),
                   lab, font=sf, fill=(220, 226, 236))
            progress_rail(d, 0, total, label="THE TARGET")
            return np.array(im)

        names_end = crest_end + total * per
        if t >= names_end:
            crest_outro(d, t, (t - names_end) / max(0.1, tail), club,
                        headline="IT IS IN THEIR HANDS" if m["possible"]
                        else "THE MATHS ARE BRUTAL",
                        call="YOUR FINAL POINTS TOTAL?",
                        sub="SUBSCRIBE — GENESIS NEWS")
            progress_rail(d, total, total, label="THAT IS THE MATHS")
            return np.array(im)

        idx = int((t - crest_end) / per)
        u_local = ((t - crest_end) % per) / per
        row_h = 176
        y0 = 360

        for j in range(idx + 1, total):
            pending_row(d, t, y0 + j * row_h, j, row_h, label="COMPUTING")

        for i in range(min(idx + 1, total)):
            y = y0 + i * row_h
            live = (i == idx and idx < total)
            u = u_local if live else 1.0
            label, value, note = rows[i]
            lf = _font(28, False)
            a = _ease(min(1.0, u * 1.8))
            d.text((92, y), label, font=lf,
                   fill=tuple(int((150, 158, 170)[k] * a + DARK[k] * (1 - a))
                              for k in range(3)))
            # figures count up - never borrow another row's number
            count_reveal(d, u, value, 92, y + 38, size=66,
                         colour=GOLD if live else (255, 255, 255))
            if u > 0.75:
                na = _ease(min(1.0, (u - 0.75) / 0.25))
                nf = _font(26, False)
                d.text((94, y + 116), note, font=nf,
                       fill=tuple(int((140, 148, 160)[k] * na
                                      + DARK[k] * (1 - na)) for k in range(3)))

        progress_rail(d, min(idx + 1, total), total)
        return np.array(im)

    from moviepy import VideoClip
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    VideoClip(frame, duration=duration).write_videofile(
        str(out_path), fps=30, codec="libx264", audio=False, logger=None,
        preset="medium")
    return str(out_path), duration


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    from modules.club_brand import CLUB_BRAND
    m = await maths(a.club)
    if not m:
        print("no standings available - refusing to simulate from nothing")
        return 1
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    print(f"{club_name}: {m['rank']} on {m['points']}pts, {m['left']} to play, "
          f"needs {m['need']} more for {m['target']} "
          f"-> {m['wins_needed']} wins")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"titlerace_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    text, intro, lines, outro = narration(club_name, m)
    from build_reveal_reel import make_voice
    audio, vdur = await make_voice(text, work)
    if not audio:
        print("voice failed - refusing to post a silent reel")
        return 1

    def wc(s):
        return max(1, len(s.split()))
    w_i, w_n, w_o = wc(intro), wc(" ".join(lines)), wc(outro)
    spw = vdur / (w_i + w_n + w_o)
    head = w_i * spw
    per = max(1.2, (w_n * spw) / len(lines))
    tail = max(2.5, w_o * spw)
    scan = max(1.8, head * 0.62)
    crest = max(0.8, head - scan)
    print(f"voice {vdur:.1f}s -> scan {scan:.1f}s, {per:.1f}s per beat, "
          f"tail {tail:.1f}s")

    silent, dur = build(a.club, club_name, m, work / "silent.mp4",
                        scan, crest, per, tail)

    from modules.motion_kit import attach_voice
    voiced = await attach_voice(silent, text, work / "voiced.mp4")

    final = voiced
    try:
        from modules.sound_kit import score_reveal, under_voice
        from moviepy import VideoFileClip
        with VideoFileClip(str(voiced)) as vc:
            fdur = vc.duration
        score = score_reveal(work / "score.wav", fdur, scan, scan + crest,
                             per, len(lines))
        mixed = under_voice(voiced, score, work / "final.mp4")
        if mixed:
            final = mixed
            print("sound: scored and mixed under the voice")
    except Exception as e:
        print("sound skipped: " + str(e))

    cover = work / "cover.jpg"
    from moviepy import VideoFileClip
    with VideoFileClip(str(final)) as c:
        Image.fromarray(c.get_frame(min(c.duration - 0.3, dur * 0.62))).save(
            cover, quality=94)

    title = (f"{club_name} Road to Number One — What They Actually Need "
             f"({m['wins_needed']} Wins From {m['left']})")
    caption = (f"THE ROAD TO NUMBER ONE — simulated on the live table.\n\n"
               f"📍 {club_name} are {m['rank']} on {m['points']} pts "
               f"({m['played']} played)\n"
               f"📊 {m['leader']} lead on {m['leader_points']} — gap of "
               f"{m['gap']}\n"
               f"🗓️ {m['left']} games left = {m['available']} points available\n"
               f"🏆 A title costs about {m['target']} pts — they need "
               f"{m['need']} more\n"
               f"✅ That is {m['wins_needed']} wins from {m['left']}\n\n"
               "This is not a prediction. It is the maths on the real table.\n\n"
               "What is YOUR final points total for Amakhosi? 👇\n\n"
               "#PSL #BetwayPremiership #KaizerChiefs #Amakhosi")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover), "title": title,
         "description": caption, "maths": m,
         "built_at": datetime.now().isoformat()}, indent=2,
        ensure_ascii=False, default=str), encoding="utf-8")
    print("BUILD COMPLETE: " + str(final))

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, title[:95], caption, cover, niche=NICHE,
                          first_comment=(
                              f"{m['wins_needed']} wins from {m['left']}. "
                              f"What is your final points total for Amakhosi "
                              f"this season? 👇"))
        print("published: " + str(r))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
