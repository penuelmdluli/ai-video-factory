"""
The reveal treatment, voiced and posted.

Difference from build_reveal_demo: the voice is generated FIRST and the
animation is then cut to fit it. Building the picture first and dropping audio
on top is what produced a reel whose names appeared several seconds after they
were spoken - the freeze-extend in attach_voice rescues a post from silence,
but it cannot make a name land on its own cue.

So: narrate, measure, then hand the measured seconds to the animation. Each
name gets its share of the middle, and the scan and the closing question keep
fixed beats at either end.

    python build_reveal_reel.py --club chiefs --group midfield
    python build_reveal_reel.py --post
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

NICHE = "sa_pulse"
SCAN = 3.0
CREST = 1.0
TAIL = 4.2


def narration(club_name, label, men, opp):
    """Returns (text, intro, names_block, outro) so the picture can be paced.

    The three parts are kept separate on purpose. Pacing the animation with
    fixed head and tail constants put six names across 28 seconds while the
    voice read them in 12, so every name appeared long after it was spoken.
    Word counts per section are the only honest way to know where the voice
    actually is.
    """
    n = len(men)
    intro = [f"Team news watch. {club_name}, the {label}."]
    intro.append(f"{n} names in the frame"
                 + (f" for {opp} on Saturday." if opp else "."))
    intro.append("Here is who is in it.")

    # Each man gets his evidence, not just his name.
    #
    # Owner call 2026-08-27: "we rush to cut the list, that's around 18s -
    # what about the rest of the video?". Exactly right, and the fix is not to
    # slow the animation down. Six bare names take eighteen seconds because
    # there are only twenty-four words to say; padding that would have made
    # the same thin content drag. Giving every player the one true thing we
    # know from the last team sheet more than doubles the list, and it is the
    # part people came for. The sign-off loses a sentence at the same time.
    names = []
    for m in men:
        no = f", number {m['no']}" if m.get("no") else ""
        why = m.get("why")
        names.append(f"{m['name']}{no}." + (f" He {why}." if why else ""))

    outro = [
        "So you pick it. Who starts, and who sits? Tell us why below.",
        "Subscribe to Genesis News. We post the team sheet the moment it lands.",
    ]
    text = " ".join(intro + names + outro)
    return text, " ".join(intro), names, " ".join(outro)


async def make_voice(text, work):
    from modules.voice_generator import generate_voice
    vw = work / "voicework"
    vw.mkdir(parents=True, exist_ok=True)
    v = await generate_voice(text, vw, "reveal", "short", NICHE)
    p = (v or {}).get("audio_path")
    if not p:
        return None, 0.0
    from moviepy import AudioFileClip
    a = AudioFileClip(p)
    d = a.duration
    a.close()
    return p, d


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--group", default="midfield")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    from build_debate_video import contenders, GROUPS
    from modules.availability import confirmed_available
    from modules.club_brand import CLUB_BRAND
    from modules.psl_fixtures import next_fixture

    pos, title, label = GROUPS[a.group]
    men = contenders(a.club, pos)
    if not men:
        print("no squad data")
        return 1
    men, held, ev = await confirmed_available(a.club, men)
    for m, why in held:
        print("held back: " + m["name"] + " - " + why)
    men = men[:6]
    if len(men) < 2:
        print("not enough confirmed players")
        return 1

    # Annotate each man with the one true thing the last team sheet tells us.
    # This is the only evidence we hold, and it is what turns a list of names
    # into something worth thirty seconds.
    try:
        from modules.availability import _surname
        from modules.psl_fixtures import last_lineup
        sheet = await last_lineup(a.club)
        started = {_surname(x) for x in ((sheet or {}).get("players") or [])}
        benched = {_surname(x) for x in ((sheet or {}).get("bench") or [])}
        for m in men:
            s = _surname(m["name"])
            m["why"] = ("started the last match" if s in started
                        else "came off the bench last time" if s in benched
                        else "")
    except Exception as e:
        print("no team-sheet evidence: " + str(e))

    print(f"{len(men)} confirmed: " + ", ".join(
        m["name"] + (f" ({m.get('why')})" if m.get("why") else "")
        for m in men))

    club_name = CLUB_BRAND.get(a.club, {}).get("name", a.club.title())
    opp = ""
    fx = await next_fixture(a.club)
    if fx:
        opp = fx["away"] if fx.get("home_key") == a.club else fx["home"]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / f"reveal_{a.club}_{a.group}_{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    text, intro, name_lines, outro = narration(club_name, label, men, opp)
    audio, vdur = await make_voice(text, work)
    if not audio:
        print("voice failed - refusing to post a silent reel")
        return 1
    print(f"voice: {vdur:.1f}s")

    # Split the runtime the way the voice actually splits it: by words. The
    # scan and crest share the intro, the names get their own words, and the
    # closing question keeps whatever the outro needs - so a name lands when
    # it is said, not seconds later.
    def wc(s):
        return max(1, len(s.split()))

    w_intro, w_names, w_outro = wc(intro), wc(" ".join(name_lines)), wc(outro)
    total_w = w_intro + w_names + w_outro
    sec_per_word = vdur / total_w
    head = w_intro * sec_per_word
    names_span = w_names * sec_per_word
    tail = max(2.5, w_outro * sec_per_word)
    per = max(0.75, names_span / len(men))
    scan = max(1.6, head * 0.72)
    crest = max(0.6, head - scan)
    print(f"pacing: scan {scan:.1f}s, crest {crest:.1f}s, "
          f"{per:.2f}s per name, tail {tail:.1f}s")

    import build_reveal_demo as demo
    demo.SCAN_END, demo.CREST_END = scan, scan + crest
    demo.PER_NAME, demo.TAIL = per, tail
    silent, dur = demo.build(a.club, label, men, (opp or "NEXT").upper(),
                             work / "silent.mp4")
    print(f"silent: {dur:.1f}s")

    from modules.motion_kit import attach_voice
    voiced = await attach_voice(silent, text, work / "voiced.mp4")

    # Score it to its own timings, then sit it under the narration. Built from
    # the same numbers that drove the animation, so the lock lands with the
    # name rather than near it.
    final = voiced
    try:
        from modules.sound_kit import score_reveal, under_voice
        from moviepy import VideoFileClip
        with VideoFileClip(str(voiced)) as vc:
            vdur_final = vc.duration
        score = score_reveal(work / "score.wav", vdur_final, scan,
                             scan + crest, per, len(men))
        mixed = under_voice(voiced, score, work / "final.mp4")
        if mixed:
            final = mixed
            print("sound: riser, crest impact, " + str(len(men))
                  + " locks, bed - mixed under the voice")
    except Exception as e:
        print("sound skipped: " + str(e))

    # Cover from a frame where names are already on screen - the first frame
    # is the empty scan, which as a cover reads as a broken video.
    cover = work / "cover.jpg"
    from moviepy import VideoFileClip
    from PIL import Image
    with VideoFileClip(str(final)) as c:
        Image.fromarray(c.get_frame(min(c.duration - 0.2, dur * 0.82))).save(
            cover, quality=94)

    vs = f" vs {opp}" if opp else ""
    vid_title = f"{club_name} {label.title()}: Who Starts{vs}?"
    caption = (f"{club_name} have {len(men)} {label} in the frame{vs}.\n\n"
               + "\n".join(f"{m['no']}  {m['name']}" for m in men)
               + "\n\nWho starts and who sits? Tell us why 👇\n\n"
               "#PSL #BetwayPremiership #KaizerChiefs #Amakhosi")

    (work / "upload_manifest.json").write_text(json.dumps(
        {"niche": NICHE, "format_type": "short", "is_short": True,
         "video_path": str(final), "thumbnail": str(cover),
         "title": vid_title, "description": caption, "men": men,
         "built_at": datetime.now().isoformat()}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    print("BUILD COMPLETE: " + str(final))

    if a.post:
        from modules.publish_reel import publish
        r = await publish(final, vid_title, caption, cover, niche=NICHE,
                          first_comment=(
                              "Who starts in that midfield on Saturday? "
                              "Give us your three and say why 👇"))
        print("published: " + str(r))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
