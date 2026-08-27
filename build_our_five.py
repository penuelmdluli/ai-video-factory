"""
OUR FIVE - the five we say should start, named, with a reason each.

Owner call 2026-08-27: "break the news on our 5 best selected players that
should start... we must sometimes tease them to start their argument".

Every other format we run asks a question. This one takes a side. That is the
whole point: a question gets answers, a CLAIM gets arguments, and an argument
is what fills a comment section. The reel ends by naming the man we left out
and daring the reader to defend him.

WHAT THIS MAY AND MAY NOT CLAIM
The picks are ours and are labelled ours. Nothing here says the coach will
pick these men, nobody is called injured, and no invented statistic is used to
justify a choice - the reasons come from the last real team sheet, which is
the only evidence we actually hold: he started, he came off the bench, he was
not in the squad. A bold opinion is fair game. A made-up fact is not, and this
page has already paid for that lesson once.

    python build_our_five.py --club chiefs
    python build_our_five.py --post
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
    ambient, crest_outro, hold_hook, pending_row, progress_rail, scan_loader,
    silhouette_pop, slot_reveal)

NICHE = "sa_pulse"
PICKS = 5


def _stage(t):
    im = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(im)
    for i in range(200):
        a = 1 - i / 200
        d.line([(0, i), (W, i)],
               fill=(int(26 * a) + 12, int(30 * a) + 14, int(38 * a) + 18))
    ambient(d, t)
    return im, d


async def pick_five(club):
    """Five confirmed players, with a reason drawn from the last team sheet."""
    from modules.availability import confirmed_available, _surname
    from modules.psl_fixtures import last_lineup
    from build_debate_video import contenders

    sheet = await last_lineup(club)
    started = {_surname(x) for x in ((sheet or {}).get("players") or [])}
    benched = {_surname(x) for x in ((sheet or {}).get("bench") or [])}

    pool = []
    for pos, label in (("GK", "in goal"), ("DF", "at the back"),
                       ("MF", "in midfield"), ("FW", "up top")):
        men = contenders(club, pos)
        men, _held, _ev = await confirmed_available(club, men)
        for m in men:
            s = _surname(m["name"])
            if s in started:
                why, rank = "started the last match", 0
            elif s in benched:
                why, rank = "came off the bench last time", 1
            else:
                continue
            pool.append({**m, "line": label, "why": why, "rank": rank})

    # one from each line first, so the five is a side and not five strikers
    five, used_lines = [], set()
    for p in sorted(pool, key=lambda x: x["rank"]):
        if p["line"] not in used_lines:
            five.append(p)
            used_lines.add(p["line"])
        if len(five) == PICKS:
            break
    for p in sorted(pool, key=lambda x: x["rank"]):
        if len(five) >= PICKS:
            break
        if p not in five:
            five.append(p)

    # the man we leave out - the tease
    left_out = None
    for p in sorted(pool, key=lambda x: x["rank"]):
        if p not in five:
            left_out = p
            break
    return five[:PICKS], left_out, sheet


def narration(club_name, five, left_out, opp):
    intro = [f"This is our five. The {len(five)} that should start for "
             f"{club_name}" + (f" against {opp}." if opp else "."),
             "Not the coach's five. Ours. Argue with it."]
    names = []
    for p in five:
        no = f", number {p['no']}" if p.get("no") else ""
        names.append(f"{p['name']}{no}, {p['line']}. He {p['why']}.")
    outro = ["That is our call, and we will stand by it."]
    if left_out:
        outro.append(f"And yes, we left out {left_out['name']}. "
                     f"If you think that is wrong, say so below and tell us "
                     f"who you drop for him.")
    else:
        outro.append("Tell us who you drop, and who you bring in.")
    outro.append("Subscribe to Genesis News. We post the team sheet the "
                 "moment it lands.")
    return " ".join(intro + names + outro), " ".join(intro), names, " ".join(outro)


def build(club, club_name, five, left_out, opp, out_path,
          scan, crest, per, tail):
    total = len(five)
    duration = scan + crest + total * per + tail
    crest_end = scan + crest

    def frame(t):
        im, d = _stage(t)
        f = _font(44)
        d.text((90, 148), "OUR FIVE", font=f, fill=GOLD)
        f2 = _font(30, False)
        d.text((90, 206), (f"WHO SHOULD START v {opp}".upper() if opp
                           else "WHO SHOULD START"), font=f2,
               fill=(150, 158, 170))
        d.line([(90, 252), (W - 90, 252)], fill=(46, 50, 58), width=2)

        if t < scan:
            scan_loader(d, t, label="PICKING OUR FIVE", cy=H // 2 - 60,
                        done=min(1.0, t / scan), club=club)
            hold_hook(d, t, "YOU WILL NOT AGREE", y=H // 2 + 300)
            progress_rail(d, 0, total, label="CHOOSING")
            return np.array(im)

        if t < crest_end:
            silhouette_pop(d, (t - scan) / max(0.1, crest), club,
                           W // 2, H // 2 - 60, size=340)
            progress_rail(d, 0, total, label="HERE THEY ARE")
            return np.array(im)

        names_end = crest_end + total * per
        if t >= names_end:
            call = (f"WE DROPPED {left_out['name'].split()[-1].upper()}"
                    if left_out else "WHO DO YOU DROP?")
            crest_outro(d, t, (t - names_end) / max(0.1, tail), club,
                        headline="THAT IS OUR FIVE",
                        call=call, sub="ARGUE WITH US BELOW")
            progress_rail(d, total, total, label="OUR CALL")
            return np.array(im)

        idx = int((t - crest_end) / per)
        u_local = ((t - crest_end) % per) / per
        row_h = 176
        y0 = max(340, (H - 320 - total * row_h) // 2 + 110)
        surnames = [p["name"].split()[-1].upper() for p in five]

        # the picks not yet named sit under a live loader
        for j in range(idx + 1, total):
            pending_row(d, t, y0 + j * row_h, j, row_h, label="PICKING")

        for i in range(min(idx + 1, total)):
            y = y0 + i * row_h
            live = (i == idx and idx < total)
            u = u_local if live else 1.0
            chip = _ease(min(1.0, u * 1.6))
            cw = int(96 * chip)
            if cw > 2:
                d.rounded_rectangle([90, y, 90 + cw, y + 92], radius=14,
                                    fill=GOLD if live else (44, 49, 58))
                nf = _font(46)
                num = five[i]["no"] or "-"
                d.text((90 + cw / 2 - d.textlength(num, font=nf) / 2, y + 22),
                       num, font=nf, fill=DARK if live else GOLD)
            slot_reveal(d, u, surnames, surnames[i], 214, y + 8, size=72,
                        colour=(255, 255, 255) if live else (234, 239, 246))
            if u > 0.7:
                a = _ease(min(1.0, (u - 0.7) / 0.3))
                rf = _font(32, False)
                why = f"{five[i]['line'].upper()}  ·  {five[i]['why'].upper()}"
                c = tuple(int(GOLD[k] * a + DARK[k] * (1 - a))
                          for k in range(3))
                d.text((216, y + 96), why, font=rf, fill=c)

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
    from modules.psl_fixtures import next_fixture

    five, left_out, sheet = await pick_five(a.club)
    if len(five) < 3:
        print("not enough confirmed players to name a five")
        return 1
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    print(f"our five: " + ", ".join(p["name"] for p in five))
    if left_out:
        print("left out (the tease): " + left_out["name"])
    if sheet:
        print(f"evidence: {sheet.get('match')} ({sheet.get('date')})")

    opp = ""
    fx = await next_fixture(a.club)
    if fx:
        opp = fx["away"] if fx.get("home_key") == a.club else fx["home"]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"ourfive_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    text, intro, name_lines, outro = narration(club_name, five, left_out, opp)
    from build_reveal_reel import make_voice
    audio, vdur = await make_voice(text, work)
    if not audio:
        print("voice failed - refusing to post a silent reel")
        return 1

    def wc(s):
        return max(1, len(s.split()))
    w_i, w_n, w_o = wc(intro), wc(" ".join(name_lines)), wc(outro)
    spw = vdur / (w_i + w_n + w_o)
    head = w_i * spw
    per = max(0.9, (w_n * spw) / len(five))
    tail = max(2.5, w_o * spw)
    scan = max(1.8, head * 0.72)
    crest = max(0.6, head - scan)
    print(f"voice {vdur:.1f}s -> scan {scan:.1f}s, {per:.1f}s per pick, "
          f"tail {tail:.1f}s")

    silent, dur = build(a.club, club_name, five, left_out, opp,
                        work / "silent.mp4", scan, crest, per, tail)

    from modules.motion_kit import attach_voice
    voiced = await attach_voice(silent, text, work / "voiced.mp4")

    final = voiced
    try:
        from modules.sound_kit import score_reveal, under_voice
        from moviepy import VideoFileClip
        with VideoFileClip(str(voiced)) as vc:
            fdur = vc.duration
        score = score_reveal(work / "score.wav", fdur, scan, scan + crest,
                             per, len(five))
        mixed = under_voice(voiced, score, work / "final.mp4")
        if mixed:
            final = mixed
            print("sound: scored and mixed under the voice")
    except Exception as e:
        print("sound skipped: " + str(e))

    cover = work / "cover.jpg"
    from moviepy import VideoFileClip
    with VideoFileClip(str(final)) as c:
        Image.fromarray(c.get_frame(min(c.duration - 0.3, dur * 0.7))).save(
            cover, quality=94)

    vs = f" vs {opp}" if opp else ""
    title = f"OUR FIVE: The {len(five)} That Should Start for {club_name}{vs}"
    caption = (f"OUR FIVE — the {len(five)} we say should start{vs}.\n\n"
               + "\n".join(f"{p['no']}  {p['name']} — {p['line']}"
                           for p in five)
               + (f"\n\nAnd yes, we left out {left_out['name']}. "
                  "Tell us who you drop for him 👇" if left_out
                  else "\n\nWho do you drop? 👇")
               + "\n\nThese are OUR picks, not the coach's. Argue with us."
               "\n\n#PSL #BetwayPremiership #KaizerChiefs #Amakhosi")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover), "title": title,
         "description": caption, "five": five, "left_out": left_out,
         "built_at": datetime.now().isoformat()}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    print("BUILD COMPLETE: " + str(final))

    if a.post:
        from modules.publish_reel import publish
        fc = (f"We left out {left_out['name']} on purpose. "
              "Tell us who you drop for him 👇" if left_out
              else "Who do you drop from our five? 👇")
        r = await publish(final, title, caption, cover, niche=NICHE,
                          first_comment=fc)
        print("published: " + str(r))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
