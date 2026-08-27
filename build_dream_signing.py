"""
DREAM SIGNING - one rival player imagined into our side, to start the argument.

Owner call 2026-08-27: "we should also have a dream signing, mix our players.
This is what can spark the debate - imagining Chiefs with Allende from Mamelodi
Sundowns, this is what can spark the debate."

He is right that it is the strongest debate format available: it forces a fan
to answer two questions at once - would you take him, and who do you drop for
him - and there is no neutral answer to either.

It is also the single most dangerous thing this page can publish. A Chiefs
crest, an XI, and a Sundowns player's name in the same frame IS a transfer
rumour to anyone who sees it without context, and screenshots always travel
without context. One of those attributed to us undoes every verified post.

So the safeguards are structural and none of them are optional:

  * IMAGINE IF watermarked across every frame
  * a red standing line: NOT A TRANSFER. NOT A RUMOUR. JUST IMAGINATION.
  * the player's REAL club printed next to his name, every time he appears,
    in his club's own colour - he is never shown as one of ours
  * the man he would replace is named, which makes the post self-evidently a
    hypothetical rather than a report
  * the narration opens by saying he plays for them and is not coming

If any of that cannot be rendered, the build refuses. A format that only works
when its warnings render is a format that must not run without them.

    python build_dream_signing.py --club chiefs --from sundowns
    python build_dream_signing.py --post
"""
import argparse
import asyncio
import json
import math
import random
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
    ambient, crest_outro, hold_hook, hold_list, pitch_xi, progress_rail,
    scan_loader, silhouette_pop, slot_reveal)

NICHE = "sa_pulse"
RED = (226, 96, 96)
SHAPE = [("GK", 1), ("DF", 4), ("MF", 3), ("FW", 3)]
# Rivals we may dream about. Big names only - the debate needs a player the
# terraces already argue about.
RIVALS = {"sundowns": "Mamelodi Sundowns", "pirates": "Orlando Pirates"}


def _stage(t):
    im = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(im)
    for i in range(200):
        a = 1 - i / 200
        d.line([(0, i), (W, i)],
               fill=(int(26 * a) + 12, int(30 * a) + 14, int(38 * a) + 18))
    ambient(d, t)
    return im, d


def _imagine_watermark(d, t):
    f = _font(96)
    txt = "IMAGINE IF"
    tw = d.textlength(txt, font=f)
    drift = math.sin(t * 0.5) * 12
    for row in range(0, 6):
        a = 0.075 + 0.025 * math.sin(t * 1.1 + row)
        c = tuple(int(GOLD[i] * a + DARK[i] * (1 - a)) for i in range(3))
        d.text(((W - tw) / 2, row * 360 + drift - 40), txt, font=f, fill=c)


def _standing_warning(d):
    """The line that must be on every frame. Drawn last, never conditional."""
    f = _font(25, False)
    txt = "NOT A TRANSFER · NOT A RUMOUR · JUST IMAGINATION"
    d.text((90, 198), txt, font=f, fill=RED)


def pick_signing(rival_key, want_pos=None):
    """A real, named player from a rival squad - never invented."""
    cache = json.loads((ROOT / "data" / "psl_squads_cache.json")
                       .read_text(encoding="utf-8"))
    squad = (cache.get(rival_key) or {}).get("squad") or []
    pool = [p for p in squad
            if (p.get("name") or "").strip()
            and (not want_pos or (p.get("pos") or "").upper().startswith(want_pos))]
    if not pool:
        return None
    # prefer an outfield player with a squad number - a recognised regular
    numbered = [p for p in pool if str(p.get("no", "")).strip()
                and not (p.get("pos") or "").upper().startswith("GK")]
    p = random.choice(numbered or pool)
    return {"no": str(p.get("no", "") or "").strip(),
            "name": (p.get("name") or "").strip(),
            "pos": (p.get("pos") or "MF").upper()[:2]}


async def our_side(club):
    from build_debate_video import contenders
    picked, used = [], set()
    for pos, count in SHAPE:
        for m in contenders(club, pos):
            if m["name"] in used:
                continue
            picked.append({**m, "pos": pos})
            used.add(m["name"])
            if sum(1 for q in picked if q["pos"] == pos) >= count:
                break
    return picked


def narration(club_name, xi, pairs, rival_name):
    n = len(pairs)
    names = ", ".join(sg["name"] for sg, _ in pairs)
    intro = [
        (f"Imagine this. {names} in a {club_name} shirt."
         if n == 1 else
         f"Imagine this. {n} of them. {names}, all in black and gold."),
        f"They are not. They play for {rival_name}, and nobody is signing "
        f"anyone. This is a daydream, not a transfer report.",
        "But if we could.",
    ]
    lines = []
    for sg, out in pairs:
        lines.append(f"{sg['name']} comes in. {out['name']} makes way.")
    lines.append("Now look at where they all fit.")
    hold = ["There is the side. On the pitch, together. Look at it properly."]
    outro = [
        "So would you take them? And are those the right men to drop?",
        "Tell us below. We already know you will not agree with each other.",
        "Subscribe to Genesis News.",
    ]
    text = " ".join(intro + lines + hold + outro)
    return (text, " ".join(intro), lines, " ".join(hold), " ".join(outro))


def build(club, club_name, xi, pairs, rival_name, out_path,
          scan, crest, per, hold, tail):
    signing, dropped = pairs[0]
    total = len(pairs) + 1
    duration = scan + crest + total * per + hold * 2 + tail
    crest_end = scan + crest
    LABEL = {"GK": "IN GOAL", "DF": "AT THE BACK",
             "MF": "IN MIDFIELD", "FW": "UP FRONT"}

    def frame(t):
        im, d = _stage(t)
        _imagine_watermark(d, t)
        f = _font(46)
        d.text((90, 140), "DREAM SIGNING", font=f, fill=GOLD)
        _standing_warning(d)
        d.line([(90, 240), (W - 90, 240)], fill=(46, 50, 58), width=2)

        if t < scan:
            scan_loader(d, t, label="IMAGINING IT", cy=H // 2 - 60,
                        done=min(1.0, t / scan), club=club)
            hold_hook(d, t, "ONE PLAYER. ONE ARGUMENT.", y=H // 2 + 300)
            progress_rail(d, 0, total, label="DAYDREAMING")
            return np.array(im)

        if t < crest_end:
            u = (t - scan) / max(0.1, crest)
            nf = _font(72)
            nm = signing["name"].upper()
            a = _ease(min(1.0, u * 2))
            c = tuple(int(GOLD[i] * a + DARK[i] * (1 - a)) for i in range(3))
            d.text((W / 2 - d.textlength(nm, font=nf) / 2, H // 2 - 120),
                   nm, font=nf, fill=c)
            # his real club, in red, never omitted
            cf = _font(40)
            cl = f"PLAYS FOR {rival_name.upper()}"
            d.text((W / 2 - d.textlength(cl, font=cf) / 2, H // 2 - 20),
                   cl, font=cf, fill=RED)
            wf = _font(34, False)
            w2 = "HE IS NOT SIGNING. WE ARE JUST DREAMING."
            d.text((W / 2 - d.textlength(w2, font=wf) / 2, H // 2 + 44),
                   w2, font=wf, fill=(150, 158, 170))
            progress_rail(d, 0, total, label="THE DAYDREAM")
            return np.array(im)

        names_end = crest_end + total * per
        hold_end = names_end + hold

        if t < names_end:
            idx = int((t - crest_end) / per)
            u = ((t - crest_end) % per) / per
            beats = [(f"IN — {LABEL[sg['pos']]}", sg["name"].upper(),
                      f"{rival_name.upper()} · OUT: {out['name'].upper()}")
                     for sg, out in pairs]
            beats.append(("THE ARGUMENT", "WOULD YOU DO IT?",
                          "TWO QUESTIONS, NO NEUTRAL ANSWER"))
            for i in range(min(idx + 1, total)):
                lab, val, note = beats[i]
                y = 380 + i * 250
                live = (i == idx)
                uu = u if live else 1.0
                lf = _font(30, False)
                aa = _ease(min(1.0, uu * 1.8))
                d.text((92, y), lab, font=lf,
                       fill=tuple(int(GOLD[k] * aa + DARK[k] * (1 - aa))
                                  for k in range(3)))
                slot_reveal(d, uu, [val], val, 92, y + 44, size=58,
                            colour=(255, 255, 255))
                if uu > 0.75:
                    na = _ease(min(1.0, (uu - 0.75) / 0.25))
                    nf2 = _font(26, False)
                    col = RED if i == 0 else (140, 148, 160)
                    d.text((94, y + 122), note, font=nf2,
                           fill=tuple(int(col[k] * na + DARK[k] * (1 - na))
                                      for k in range(3)))
            progress_rail(d, min(idx + 1, total), total)
            return np.array(im)

        swap = {out["name"]: sg for sg, out in pairs}
        merged = []
        for p in xi:
            sg = swap.get(p["name"])
            if sg:
                merged.append({**sg, "new": True})
            else:
                merged.append({**p, "new": False})

        if t < hold_end:
            rows = [(q["no"] or "?", q["name"].split()[-1],
                     (f"{rival_name} — NOT OURS" if q.get("new")
                      else LABEL[q["pos"]].lower()))
                    for q in merged]
            hold_list(d, t, rows, y0=300, row_h=96, club=club,
                      note="WOULD YOU TAKE THEM?")
            return np.array(im)

        # THE PITCH. A list answers who; only the field answers whether the
        # shape still works with them all in it.
        pitch_end = hold_end + hold
        if t < pitch_end:
            pitch_xi(d, t, merged, formation="4-3-3", club=club,
                     title="how they would line up",
                     note="DOES IT WORK? TELL US BELOW")
            return np.array(im)

        crest_outro(d, t, (t - pitch_end) / max(0.1, tail), club,
                    headline="JUST A DAYDREAM",
                    call="WOULD YOU TAKE HIM?",
                    sub="NOT A TRANSFER · NOT A RUMOUR")
        progress_rail(d, total, total, label="YOUR CALL")
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
    ap.add_argument("--rival", default="sundowns", choices=list(RIVALS))
    ap.add_argument("--player", default="")
    ap.add_argument("--count", type=int, default=1,
                    help="how many imagined signings (1-4)")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    from modules.club_brand import CLUB_BRAND
    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    rival_name = RIVALS[a.rival]

    xi = await our_side(a.club)
    if len(xi) < 11:
        print(f"only {len(xi)} in our side - refusing")
        return 1

    if a.player:
        cache = json.loads((ROOT / "data" / "psl_squads_cache.json")
                           .read_text(encoding="utf-8"))
        squad = (cache.get(a.rival) or {}).get("squad") or []
        hit = next((p for p in squad
                    if a.player.lower() in (p.get("name") or "").lower()), None)
        if not hit:
            print(f"{a.player} is not in the {a.rival} squad - refusing to "
                  f"invent a player")
            return 1
        signing = {"no": str(hit.get("no", "") or "").strip(),
                   "name": (hit.get("name") or "").strip(),
                   "pos": (hit.get("pos") or "MF").upper()[:2]}
        signings = [signing]
    else:
        # Several imagined men, never two in the same shirt. Three signings
        # all wanting one position is not a dream side, it is a mistake -
        # and it is exactly what the pitch view would expose.
        signings, seen_pos = [], set()
        for _ in range(40):
            if len(signings) >= max(1, min(4, a.count)):
                break
            cand = pick_signing(a.rival)
            if not cand:
                break
            if cand["pos"] in seen_pos or any(
                    c["name"] == cand["name"] for c in signings):
                continue
            signings.append(cand)
            seen_pos.add(cand["pos"])
    if not signings:
        print("no rival squad data - refusing")
        return 1

    # who makes way: same position each time, so every swap is a real argument
    pairs, taken = [], set()
    for sg in signings:
        same = [p for p in xi
                if p["pos"] == sg["pos"] and p["name"] not in taken]
        out = same[-1] if same else next(
            (p for p in xi if p["name"] not in taken), xi[-1])
        taken.add(out["name"])
        pairs.append((sg, out))
    signing, dropped = pairs[0]
    print("dream signings: " + "; ".join(
        f"{sg['name']} ({rival_name}) in for {out['name']}"
        for sg, out in pairs))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"dreamsign_{a.club}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    text, intro, lines, hold_txt, outro = narration(
        club_name, xi, pairs, rival_name)
    from build_reveal_reel import make_voice
    audio, vdur = await make_voice(text, work)
    if not audio:
        print("voice failed - refusing to post a silent reel")
        return 1

    def wc(s):
        return max(1, len(s.split()))
    w_i, w_n, w_h, w_o = (wc(intro), wc(" ".join(lines)), wc(hold_txt),
                          wc(outro))
    spw = vdur / (w_i + w_n + w_h + w_o)
    head = w_i * spw
    per = max(1.4, (w_n * spw) / max(1, len(pairs) + 1))
    hold = max(4.0, w_h * spw)
    tail = max(2.5, w_o * spw)
    scan = max(1.8, head * 0.55)
    crest = max(1.6, head - scan)
    print(f"voice {vdur:.1f}s -> scan {scan:.1f}s, name {crest:.1f}s, "
          f"{per:.1f}s per beat, hold {hold:.1f}s, tail {tail:.1f}s")

    silent, dur = build(a.club, club_name, xi, pairs, rival_name,
                        work / "silent.mp4", scan, crest, per, hold, tail)

    from modules.motion_kit import attach_voice
    voiced = await attach_voice(silent, text, work / "voiced.mp4")

    final = voiced
    try:
        from modules.sound_kit import score_reveal, under_voice
        from moviepy import VideoFileClip
        with VideoFileClip(str(voiced)) as vc:
            fdur = vc.duration
        score = score_reveal(work / "score.wav", fdur, scan, scan + crest,
                             per, len(pairs) + 1)
        mixed = under_voice(voiced, score, work / "final.mp4")
        if mixed:
            final = mixed
            print("sound: scored and mixed under the voice")
    except Exception as e:
        print("sound skipped: " + str(e))

    cover = work / "cover.jpg"
    from moviepy import VideoFileClip
    with VideoFileClip(str(final)) as c:
        Image.fromarray(c.get_frame(min(c.duration - 0.3, scan + crest * 0.7))
                        ).save(cover, quality=94)

    title = (f"IMAGINE: {signing['name']} at {club_name}? "
             f"(Not a transfer — just a dream)")
    caption = (f"💭 DREAM SIGNING — NOT a transfer, NOT a rumour, just "
               f"imagination.\n\n"
               f"{signing['name']} plays for {rival_name}. He is not signing "
               f"for anyone. But imagine if he pulled on the black and gold.\n\n"
               f"➡️ IN: {signing['name']}\n"
               f"⬅️ OUT: {dropped['name']}\n\n"
               f"Two questions and there is no neutral answer:\n"
               f"1. Would you take him?\n"
               f"2. Is {dropped['name']} the right man to drop for him?\n\n"
               "Tell us below 👇\n\n"
               "#PSL #BetwayPremiership #KaizerChiefs #Amakhosi")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover), "title": title,
         "description": caption, "signing": signing, "dropped": dropped,
         "rival": rival_name, "is_fantasy": True,
         "built_at": datetime.now().isoformat()}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    print("BUILD COMPLETE: " + str(final))

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, title[:95], caption, cover, niche=NICHE,
                          first_comment=(
                              f"To be clear: {signing['name']} plays for "
                              f"{rival_name} and is NOT signing for anyone. "
                              f"This is a daydream 💭 Would you take him, and "
                              f"is {dropped['name']} the right man to drop? 👇"))
        print("published: " + str(r))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
