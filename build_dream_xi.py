"""
THE DREAM XI - the side supporters wish for, framed so nobody mistakes it.

Owner call 2026-08-27: "they would love seeing... good signing, good players
and all... let them picture it. They love everything Kaizer Chiefs with their
heart."

This is the one format on the page that is openly NOT news, and that has to be
visible in the picture, not buried in a caption someone scrolls past. A reel
listing players next to a Chiefs crest is a team sheet unless it is
aggressively marked otherwise, and a fabricated team sheet on a page selling
verified facts would cost more than every good post has earned.

So the framing is structural, not cosmetic:

  * a DREAM watermark runs across the whole board, every frame
  * the header says NOT REAL. NOT A TRANSFER REPORT.
  * the players are OUR OWN squad, in positions they do not currently hold -
    the fantasy is the SHAPE, not invented signings
  * the closing question asks the fan for their dream, so the reel is plainly
    a game being played and not a report being filed

The last point is the important one. Naming a real player at another club as
an incoming signing - even as a wish - is how a rumour starts with our badge
on it. We dream with our own players.

    python build_dream_xi.py --club chiefs
    python build_dream_xi.py --post
"""
import argparse
import asyncio
import json
import math
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
    slot_reveal)

NICHE = "sa_pulse"
SHAPE = [("GK", 1), ("DF", 4), ("MF", 3), ("FW", 3)]   # the 4-3-3 they dream of


def _stage(t):
    im = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(im)
    for i in range(200):
        a = 1 - i / 200
        d.line([(0, i), (W, i)],
               fill=(int(26 * a) + 12, int(30 * a) + 14, int(38 * a) + 18))
    ambient(d, t)
    return im, d


def _dream_watermark(d, t):
    """DREAM, huge and diagonal, behind everything, on every single frame.

    A caption disclaimer is not enough - screenshots travel without captions,
    and a screenshot of eleven names under a Chiefs crest is a team sheet to
    whoever sees it next. This has to survive being cropped and reposted.
    """
    # Centred, one per band. Tiled two-across at 150pt it ran off both edges
    # and read as "EAM XDREAM X" - a watermark nobody can read is decoration,
    # not a disclaimer, and this one has a job to do.
    f = _font(104)
    txt = "DREAM XI"
    tw = d.textlength(txt, font=f)
    drift = math.sin(t * 0.5) * 12
    for row in range(0, 6):
        y = row * 360 + drift - 40
        a = 0.075 + 0.025 * math.sin(t * 1.1 + row)
        c = tuple(int(GOLD[i] * a + DARK[i] * (1 - a)) for i in range(3))
        d.text(((W - tw) / 2, y), txt, font=f, fill=c)


async def pick_dream(club):
    """Our own squad, arranged into the shape supporters wish they saw.

    NOT availability-gated, deliberately - and this is the one format where
    that is right. The gate exists to stop us naming a man who cannot play as
    though he will; a dream has nobody playing at all. Filtering it produced a
    ten-man "XI" because three of the squad were not in the last matchday
    group, which is a worse lie than including them: the graphic says eleven.
    Everyone here is contracted to the club today, which is the line that
    actually matters.
    """
    from build_debate_video import contenders

    picked, used = [], set()
    for pos, count in SHAPE:
        men = contenders(club, pos)
        for m in men:
            if len(picked) >= sum(c for _, c in SHAPE):
                break
            key = m["name"]
            if key in used:
                continue
            picked.append({**m, "pos": pos})
            used.add(key)
            if sum(1 for p in picked if p["pos"] == pos) >= count:
                break
    return picked


def narration(club_name, xi):
    intro = ["This is a dream. Not a team sheet, not a transfer report.",
             f"The {club_name} eleven supporters wish they were seeing, "
             f"picked from the squad we actually have."]
    lines = []
    for pos, _ in SHAPE:
        group = [p for p in xi if p["pos"] == pos]
        if not group:
            continue
        label = {"GK": "In goal", "DF": "At the back",
                 "MF": "In midfield", "FW": "Up front"}[pos]
        lines.append(f"{label}: " + ", ".join(p["name"] for p in group) + ".")
    outro = [
        "That is ours. Every man in it plays for the club today.",
        "Now give us yours. Who is in your dream eleven, and who misses out?",
        "Subscribe to Genesis News. We do this every week.",
    ]
    text = " ".join(intro + lines + outro)
    return text, " ".join(intro), lines, " ".join(outro)


def build(club, club_name, xi, out_path, scan, crest, per, tail):
    groups = [(pos, [p for p in xi if p["pos"] == pos]) for pos, _ in SHAPE]
    groups = [g for g in groups if g[1]]
    total = len(groups)
    duration = scan + crest + total * per + tail
    crest_end = scan + crest
    LABEL = {"GK": "IN GOAL", "DF": "AT THE BACK",
             "MF": "IN MIDFIELD", "FW": "UP FRONT"}

    def frame(t):
        im, d = _stage(t)
        _dream_watermark(d, t)
        f = _font(46)
        d.text((90, 140), "THE DREAM XI", font=f, fill=GOLD)
        wf = _font(25, False)
        d.text((90, 198), "NOT REAL · NOT A TRANSFER REPORT · JUST A DREAM",
               font=wf, fill=(226, 96, 96))
        d.line([(90, 240), (W - 90, 240)], fill=(46, 50, 58), width=2)

        if t < scan:
            scan_loader(d, t, label="BUILDING THE DREAM", cy=H // 2 - 60,
                        done=min(1.0, t / scan), club=club)
            hold_hook(d, t, "IF WE COULD PICK ANY XI", y=H // 2 + 300)
            progress_rail(d, 0, total, label="DREAMING")
            return np.array(im)

        if t < crest_end:
            u = (t - scan) / max(0.1, crest)
            sf = _font(96)
            txt = "4-3-3"
            a = _ease(min(1.0, u * 2))
            c = tuple(int(GOLD[i] * a + DARK[i] * (1 - a)) for i in range(3))
            d.text((W / 2 - d.textlength(txt, font=sf) / 2, H // 2 - 110),
                   txt, font=sf, fill=c)
            lf = _font(40)
            lab = "THE SHAPE WE WANT TO SEE"
            d.text((W / 2 - d.textlength(lab, font=lf) / 2, H // 2 + 30),
                   lab, font=lf, fill=(220, 226, 236))
            progress_rail(d, 0, total, label="THE SHAPE")
            return np.array(im)

        names_end = crest_end + total * per
        if t >= names_end:
            crest_outro(d, t, (t - names_end) / max(0.1, tail), club,
                        headline="THAT IS OUR DREAM",
                        call="WHO IS IN YOURS?",
                        sub="A DREAM — NOT A TEAM SHEET")
            progress_rail(d, total, total, label="YOUR TURN")
            return np.array(im)

        idx = int((t - crest_end) / per)
        u_local = ((t - crest_end) % per) / per
        # 4 defenders at 52px plus the label needs more than 250,
        # or the back four runs straight into IN MIDFIELD
        row_h = 288
        y0 = 300
        # The wheel may only tumble through names from THIS row's group.
        # Drawing from all eleven put PETERSEN and MAKO - the keeper and a
        # defender - under the label UP FRONT while that row settled. Brief
        # or not, it is a wrong claim on screen, the same fault as a squad
        # number landing on the wrong man.

        for j in range(idx + 1, total):
            pending_row(d, t, y0 + j * row_h, j, row_h, label="DREAMING")

        for i in range(min(idx + 1, total)):
            pos, men = groups[i]
            y = y0 + i * row_h
            live = (i == idx and idx < total)
            u = u_local if live else 1.0
            lf = _font(30, False)
            a = _ease(min(1.0, u * 1.8))
            d.text((92, y), LABEL[pos], font=lf,
                   fill=tuple(int(GOLD[k] * a + DARK[k] * (1 - a))
                              for k in range(3)))
            group_pool = [q["name"].split()[-1].upper() for q in men] or ["..."]
            for j, p in enumerate(men):
                yy = y + 44 + j * 52
                sub_u = min(1.0, max(0.0, (u - j * 0.12) / 0.7))
                slot_reveal(d, sub_u, group_pool,
                            p["name"].split()[-1].upper(),
                            92, yy, size=44,
                            colour=(255, 255, 255) if live else (228, 234, 242))
                if sub_u >= 1.0 or not live:
                    nf = _font(24, False)
                    d.text((W - 180, yy + 12), str(p["no"] or "-"), font=nf,
                           fill=(120, 128, 140))

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
    xi = await pick_dream(a.club)
    if len(xi) < 11:
        print(f"only {len(xi)} players - a DREAM XI must show eleven")
        return 1
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    print(f"dream XI ({len(xi)}): " + ", ".join(p["name"] for p in xi))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"dreamxi_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    text, intro, lines, outro = narration(club_name, xi)
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
    per = max(1.5, (w_n * spw) / max(1, len(lines)))
    tail = max(2.5, w_o * spw)
    scan = max(1.8, head * 0.66)
    crest = max(0.8, head - scan)
    print(f"voice {vdur:.1f}s -> scan {scan:.1f}s, {per:.1f}s per line, "
          f"tail {tail:.1f}s")

    silent, dur = build(a.club, club_name, xi, work / "silent.mp4",
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
        Image.fromarray(c.get_frame(min(c.duration - 0.3, dur * 0.6))).save(
            cover, quality=94)

    title = f"Our DREAM XI for {club_name} — Not Real, Just a Dream"
    caption = ("💭 THE DREAM XI — this is NOT a team sheet and NOT a transfer "
               "report. It is the eleven we wish we were seeing, picked from "
               f"the {club_name} squad we actually have.\n\n"
               + "\n".join(
                   f"{ {'GK':'🧤','DF':'🛡️','MF':'⚙️','FW':'⚡'}[pos] } "
                   + ", ".join(p["name"] for p in xi if p["pos"] == pos)
                   for pos, _ in SHAPE
                   if any(p["pos"] == pos for p in xi))
               + "\n\nNow give us YOURS. Who is in your dream eleven, and who "
               "misses out? 👇\n\n"
               "#PSL #BetwayPremiership #KaizerChiefs #Amakhosi #DreamXI")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover), "title": title,
         "description": caption, "xi": xi, "is_fantasy": True,
         "built_at": datetime.now().isoformat()}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    print("BUILD COMPLETE: " + str(final))

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, title[:95], caption, cover, niche=NICHE,
                          first_comment=(
                              "Reminder: this is a DREAM XI, not a team sheet "
                              "and not a transfer report 💭 Now give us "
                              "yours — who starts and who misses out? 👇"))
        print("published: " + str(r))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
