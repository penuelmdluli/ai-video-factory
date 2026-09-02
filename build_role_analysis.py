"""THE ROLE — how a position is played, and the Chiefs man who plays it.

Owner call 2026-09-02, describing a creator's format: "they are analysing a
position, like how a modern left back should play. We need to transform this
style where we are analysing the Chiefs team, a specific player, on how they
should play for the best of the team."

Structure, borrowed from that shape:

    1. NAME THE JOB      "The modern right back. Defend a touchline, then
                          attack the same one."
    2. TEACH IT          three things the role demands, each drawn on the
                          board - the overlap, the recovery run, the tuck in
    3. NAME THE MAN      the Chiefs player who actually plays there, ringed
                          inside the real XI
    4. HAND IT OVER      ask the supporters whether he is doing it

The order is the safety as much as the style. The teaching half is general
football - true in any league, owes nobody a statistic. The ONLY claim made
about a named player is where he lines up, and that comes off the ESPN team
sheet through psl_squads.recent_positions. The page never says "he completes
2.1 tackles a game", because this repo has a standing rule that facts about
players come from verified sheets, and a made-up number on a flagship format
is the fastest way to lose an audience that knows the squad better than we do.

Roles resolve on where a man USUALLY plays, not where he played once: Monyane
was RM in a single 3-4-3 and RB in the match before, and teaching "the modern
right winger" about a full back is exactly the wrong-position error the owner
raised in the first place.

    python build_role_analysis.py --club chiefs
    python build_role_analysis.py --club chiefs --player monyane
    python build_role_analysis.py --club chiefs --post
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
STATE = ROOT / "data" / "role_analysis.json"


def _log(m):
    print(f"[Role] {m}", flush=True)


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"done": []}


def _save(d: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                     encoding="utf-8")


async def choose(club: str, want: str = "") -> tuple:
    """(surname, espn_abbrev, role_key) — least-recently-analysed first."""
    from modules.psl_squads import recent_positions
    from modules.player_roles import role_for, describe

    # "frequent", not "latest" — see the module docstring.
    pos = await recent_positions(club, mode="frequent")
    playable = [(sn, ab) for sn, ab in pos.items()
                if describe(role_for(ab))]
    if not playable:
        return "", "", ""

    if want:
        for sn, ab in playable:
            if sn.lower() == want.lower():
                return sn, ab, role_for(ab)
        _log(f"'{want}' has no published position — falling back to rotation")

    done = _state().get("done", [])
    counts = {sn: done.count(sn) for sn, _ in playable}
    sn, ab = min(playable, key=lambda p: (counts[p[0]], p[0]))
    return sn, ab, role_for(ab)


async def main(a) -> int:
    from modules.player_roles import describe
    from modules.tactics_board import Board
    from modules.psl_squads import predict_xi2
    from modules.motion_kit import GOLD, W, H

    surname, abbrev, role_key = await choose(a.club, a.player)
    if not role_key:
        _log("no published positions — cannot build a role analysis")
        return 1
    role = describe(role_key)
    _log(f"{surname.title()} — ESPN {abbrev} -> {role_key} ({role['title']})")

    # The real XI, so the man is shown inside the side he actually plays in.
    xi_list, formation = await predict_xi2(a.club, force_refresh=False)
    if len(xi_list) < 11:
        _log("no usable XI")
        return 1

    players, positions, subject_pid = {}, {}, ""
    lines = [int(n) for n in str(formation).split("-") if n.strip().isdigit()]
    rows = [1] + lines
    idx = 0
    for row_i, count in enumerate(rows):
        # y: 0.92 at the keeper, climbing towards the opponent goal.
        y = 0.92 - (row_i / max(1, len(rows) - 1)) * 0.74
        for col in range(count):
            if idx >= len(xi_list):
                break
            entry = xi_list[idx]
            no, _, nm = entry.partition(" ")
            pid = f"p{idx}"
            players[pid] = {"no": no, "name": nm.upper()}
            x = (col + 1) / (count + 1)
            positions[pid] = (x, y)
            if nm.lower() == surname.lower():
                subject_pid = pid
            idx += 1

    if not subject_pid:
        # He is not in today's predicted XI. Put him on the board anyway, in
        # the role's home position - the lesson is about the position, and a
        # squad player is exactly who supporters argue about.
        subject_pid = "subject"
        players[subject_pid] = {"no": "", "name": surname.upper()}
        positions[subject_pid] = role["home"]
        _log(f"{surname.title()} is not in the predicted XI — shown at the "
             f"role's home position")

    beats = role["beats"]
    scenes = [{"narration":
               f"{role['title'].replace('THE ', 'The ').lower()}. "
               f"{role['job']} At {('Kaizer Chiefs')}, that shirt belongs to "
               f"{surname.title()}."}]
    scenes += [{"narration": b["say"]} for b in beats]
    scenes.append({"narration":
                   f"That is the job. Three things, every match. So the "
                   f"question for you is simple. Is {surname.title()} doing "
                   f"them? Tell us in the comments, and follow Genesis News "
                   f"for the next one."})

    SCRIPT = {
        "title": f"{role['title']} — and the Chiefs man who plays it",
        "caption": (
            f"{role['title']} 📋 {role['job']}\n\n"
            f"Three things the job demands — and {surname.title()} is the man "
            f"Chiefs put there.\n\n"
            f"Is he doing them? 👇⚽\n"
            f"#KaizerChiefs #Amakhosi #PSL #BetwayPremiership #Khosi4Life"),
        "scenes": scenes,
    }

    from build_psl_news import (make_voice, write_manifest, post_to_page,
                                _caption_clips, _subscribe_strip)
    from modules.caption_generator import (parse_subtitle_to_segments,
                                           group_words_into_phrases)
    from modules.caption_align import align_captions
    from modules.script_writer import get_full_narration
    from moviepy import (AudioFileClip, ImageClip, VideoFileClip,
                         CompositeVideoClip, CompositeAudioClip,
                         concatenate_videoclips)

    work = ROOT / "output" / f"role_{a.club}_{surname.lower()}_{datetime.now():%Y%m%d_%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)

    _log("voice…")
    voice = await make_voice(SCRIPT, work)
    audio = AudioFileClip(voice["audio_path"])
    total = float(audio.duration) + 0.6

    # Chapter lengths proportional to word count, so the board is showing the
    # movement the voice is describing (the sync bug this pipeline already hit).
    wc = [len(s["narration"].split()) for s in SCRIPT["scenes"]]
    dur = [max(4.5, total * w / sum(wc)) for w in wc]
    _log(f"narration {total:.1f}s across {len(dur)} chapters")

    clips = []
    # Chapter 1: the whole side, the man ringed.
    b0 = Board(players, accent=GOLD, title=role["title"],
               subtitle=f"{surname.upper()} · {formation}")
    b0.keyframe(0.0, positions)
    b0.keyframe(dur[0], positions)
    b0.ring(0.6, dur[0], subject_pid)
    clips.append(b0.render(work / "_c0.mp4", duration=dur[0]))

    # One chapter per beat: he makes the movement, the board draws it.
    for i, beat in enumerate(beats):
        d = dur[i + 1]
        b = Board(players, accent=GOLD, title=beat["label"],
                  subtitle=role["title"])
        start = dict(positions)
        start[subject_pid] = beat["from"]
        b.keyframe(0.0, start)
        # keyframe_balanced so the rest of the side drifts in sympathy rather
        # than standing still while one man runs.
        b.keyframe_balanced(d * 0.75, {subject_pid: beat["to"]})
        b.keyframe(d, dict(b.keys[-1][1]))
        b.ring(0.0, d, subject_pid)
        b.arrow(0.3, d, beat["from"], beat["to"], label=beat["label"])
        if beat.get("zone"):
            b.zone(d * 0.35, d, beat["zone"], label="")
        clips.append(b.render(work / f"_c{i+1}.mp4", duration=d))

    # Closing chapter: back to the shape, question on screen.
    bz = Board(players, accent=GOLD, title="IS HE DOING IT?",
               subtitle=f"{surname.upper()} · TELL US BELOW")
    bz.keyframe(0.0, positions)
    bz.keyframe(dur[-1], positions)
    bz.ring(0.2, dur[-1], subject_pid)
    clips.append(bz.render(work / "_cz.mp4", duration=dur[-1]))

    _log("compositing…")
    parts = [VideoFileClip(str(c)) for c in clips]
    base = concatenate_videoclips(parts)
    layers = [base]
    try:
        sub = _subscribe_strip(work)
        layers.append(ImageClip(sub).with_start(max(0, base.duration - 4.0))
                      .with_duration(min(4.0, base.duration))
                      .with_position(("center", 1730)))
    except Exception:
        pass
    try:
        segments = parse_subtitle_to_segments(voice["subtitle_path"])
        segments = align_captions(get_full_narration(SCRIPT), segments)
        phrases = group_words_into_phrases(segments, max_words=4)
        layers += _caption_clips(phrases, W, work)
    except Exception as ex:
        _log(f"captions skipped: {ex}")

    d = max(base.duration, total)
    video = CompositeVideoClip(layers, size=(W, H)).with_duration(d) \
        .with_audio(CompositeAudioClip([audio]).with_duration(d))
    out = work / "final.mp4"
    video.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac", logger=None,
                          preset="medium", threads=4)
    write_manifest(SCRIPT, str(out), work, voice,
                   [{"path": str(clips[0]), "credit": "Genesis News",
                     "archive_year": "", "club": a.club, "real": True}])
    _log(f"video: {out} ({d:.1f}s)")

    if a.post:
        await post_to_page(work)
        st = _state()
        st["done"] = (st.get("done", []) + [surname])[-60:]
        _save(st)
        _log("POSTED")
    else:
        _log("dry run — pass --post to publish")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--player", default="", help="surname, e.g. monyane")
    ap.add_argument("--post", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args())))
