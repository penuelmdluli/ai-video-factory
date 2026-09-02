"""THE SIMULATION — Chiefs play the game before it happens.

Owner 2026-09-02, after watching the role reels grow: "the ball and the fans
and all the upgrades must start as the video starts. We have limitless count in
each video - it will always have new formation and players - then it can have
goals randomly predicting if they play that way. This is like a simulator.
3 goals, winning the game. This must be the best."

That is a different format from the role analysis, and a better one. The role
reel TEACHES and finishes with one move. This one PLAYS THE MATCH: the crests
are up from frame one, the crowd is in from frame one, and the whole reel is
three moves that end in three goals and a scoreline.

WHY IT IS NEVER THE SAME TWICE, without anything being random for its own sake:

    the SHAPE comes from lineup_variety (five real formations, rotating)
    the ELEVEN come from player_rotation (over-exposure is charged for)
    the MOVES are built from wherever those men actually stand
    the SCORERS are forced to be three different players

So the "limitless count" the owner is after falls out of the parts that were
already built today, rather than from a random number generator.

WHAT IS AND IS NOT CLAIMED. This is a PREDICTION and is labelled as one on
every frame - the same stamp the predicted XI already carries. It is not a
report of a match that happened, the narration never says it is, and no real
result, scoreline or goalscorer is asserted. Saying "this is how it could go if
they play this way" is punditry; saying "Chiefs won 3-0" before a ball is
kicked would be a fabricated result on a page whose rule is that match facts
come from verified team sheets.

    python build_match_sim.py --club chiefs
    python build_match_sim.py --club chiefs --goals 3 --post
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent


def _log(m):
    print(f"[Sim] {m}", flush=True)


async def main(a) -> int:
    from modules.tactics_board import Board
    from modules.psl_squads import predict_xi2
    from modules.move_builder import build_move
    from modules.motion_kit import GOLD, W, H
    from modules.psl_fixtures import next_fixture
    from modules.club_brand import CLUB_BRAND

    fx = await next_fixture(a.club)
    if not fx:
        _log("no upcoming fixture — the simulation needs a game to simulate")
        return 1
    opp_key = fx["away_key"] if fx["home_key"] == a.club else fx["home_key"]
    opp = fx["away"] if fx["home_key"] == a.club else fx["home"]
    at_home = fx["home_key"] == a.club
    ko, venue = fx.get("kickoff_sast", ""), fx.get("venue", "")
    club_name = CLUB_BRAND.get(a.club, {}).get("name", "Kaizer Chiefs")
    _log(f"simulating {club_name} {'v' if at_home else 'away to'} {opp} — {ko}")

    # Shape and personnel rotate, so no two simulations are the same match.
    shape, calls = None, []
    try:
        from modules.lineup_variety import pick as _variety
        shape, calls = await _variety(a.club)
    except Exception as e:
        _log(f"variety unavailable ({str(e)[:50]})")
    xi_list, formation = await predict_xi2(a.club, shape, force_in=calls)
    if len(xi_list) < 11:
        _log("no usable XI")
        return 1
    _log(f"shape {formation}" + (f" + {calls[0]}" if calls else ""))

    players, positions = {}, {}
    lines = [int(n) for n in str(formation).split("-") if n.strip().isdigit()]
    rows, idx = [1] + lines, 0
    for row_i, count in enumerate(rows):
        y = 0.92 - (row_i / max(1, len(rows) - 1)) * 0.74
        for col in range(count):
            if idx >= len(xi_list):
                break
            no, _, nm = xi_list[idx].partition(" ")
            pid = f"p{idx}"
            players[pid] = {"no": no, "name": nm.upper()}
            positions[pid] = ((col + 1) / (count + 1), y)
            idx += 1

    # Each goal starts from a different man at the back, so the three moves do
    # not all open the same way.
    deep = [pid for pid, _ in sorted(positions.items(), key=lambda kv: -kv[1][1])]
    starts = (deep[1:1 + a.goals] or [deep[0]])

    goals, scored = [], set()
    for g in range(a.goals):
        wps, chain, scorer, assist, moves = build_move(
            positions, players, [], passes=6, avoid=scored,
            start_pid=starts[g % len(starts)])
        if not chain:
            break
        scored.add(chain[-1])
        goals.append((wps, chain, scorer, assist, moves))
        _log(f"goal {g + 1}: {len(chain) - 1} passes -> {scorer}"
             + (f" (assist {assist})" if assist else ""))
    if not goals:
        _log("could not build a move")
        return 1

    where = f"at {venue}" if venue and at_home else f"away to {opp}"
    scenes = [{"narration":
               f"{club_name} against {opp}, {ko}. This is Genesis News "
               f"simulating it. Our shape, our eleven, and how it could go if "
               f"they play this way."}]
    ordinal = ["The first", "The second", "The third", "The fourth"]
    for i, (_w, chain, scorer, assist, _m) in enumerate(goals):
        line = (f"{ordinal[min(i, 3)]} one. {len(chain) - 1} passes through "
                f"the shape")
        if assist:
            line += f", {assist.title()} the last ball"
        line += f", and {scorer.title()} finishes it."
        scenes.append({"narration": line})
    scenes.append({"narration":
                   f"{len(goals)} nil. That is the simulation, not the result. "
                   f"So tell us. Do you see {club_name} winning {ko}, and who "
                   f"scores first? Drop it in the comments."})

    nl = chr(10)
    scorers = ", ".join(g[2].title() for g in goals)
    SCRIPT = {
        "title": f"SIMULATION: {club_name} {len(goals)}-0 {opp} | {formation}",
        "caption": (
            f"WE SIMULATED IT 🎮 {club_name} v {opp}, {ko}.{nl}{nl}"
            f"Our {formation}, our eleven, and {len(goals)} goals — "
            f"{scorers}.{nl}{nl}"
            f"This is a PREDICTION, not a result. Do you see it going this "
            f"way? Who scores first? 👇⚽{nl}{nl}"
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
                         concatenate_videoclips, concatenate_audioclips)

    work = ROOT / f"output/sim_{a.club}_{datetime.now():%Y%m%d_%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)
    _log("voice…")
    voice = await make_voice(SCRIPT, work)
    audio = AudioFileClip(voice["audio_path"])
    total = float(audio.duration) + 0.5
    wc = [len(s["narration"].split()) for s in SCRIPT["scenes"]]
    dur = [max(4.0, total * w / sum(wc)) for w in wc]
    _log(f"narration {total:.1f}s across {len(dur)} chapters")

    clips, kick_times, goal_times, t0 = [], [], [], 0.0

    # Chapter 1: the teams. Crests, shape, kickoff — the match is on from the
    # first frame, which is the owner's point about the upgrades starting at
    # the start rather than arriving at the end.
    d = dur[0]
    b = Board(players, accent=GOLD, title="THE SIMULATION",
              subtitle=f"{formation} · {ko}", club=a.club, opponent=opp_key)
    b.keyframe(0.0, positions)
    b.keyframe(d, positions)
    b.stat(0.5, min(d, 3.2), f"{club_name.upper()} v {opp.upper()}", ko)
    clips.append(b.render(work / "_c0.mp4", duration=d))
    t0 += d

    running = 0
    for i, (wps, chain, scorer, assist, moves) in enumerate(goals):
        d = dur[i + 1]
        running += 1
        b = Board(players, accent=GOLD, title=f"GOAL {running}",
                  subtitle=f"{scorer} · {len(chain) - 1} PASSES",
                  club=a.club, opponent=opp_key)
        b.keyframe(0.0, positions)
        for frac, change in moves:
            b.keyframe_balanced(max(0.05, d * frac), change,
                                strength=0.25, radius=0.20)
        b.keyframe(d, dict(b.keys[-1][1]))
        b.ball([(d * f, tuple(xy)) for f, xy in wps])
        n_ch = max(1, len(chain) - 1)
        for k, pid in enumerate(chain):
            t_at = d * 0.80 * k / n_ch
            b.ring(max(0.0, t_at - 0.15), min(d, t_at + 0.45), pid)
            if k < len(chain) - 1:
                kick_times.append(t0 + t_at)
        b.goal(d * 0.90, d, scorer=scorer, assist=assist)
        b.stat(d * 0.94, d, f"{running}-0", scorer)
        goal_times.append(t0 + d * 0.90)
        clips.append(b.render(work / f"_g{i}.mp4", duration=d))
        t0 += d

    d = dur[-1]
    b = Board(players, accent=GOLD, title="FULL TIME",
              subtitle=f"OUR PREDICTION · {ko}", club=a.club, opponent=opp_key)
    b.keyframe(0.0, positions)
    b.keyframe(d, positions)
    b.stat(0.3, d * 0.75, f"{len(goals)}-0", f"{club_name.upper()} — PREDICTED")
    clips.append(b.render(work / "_ft.mp4", duration=d))

    _log("compositing…")
    base = concatenate_videoclips([VideoFileClip(str(c)) for c in clips])
    layers = [base]
    try:
        strip = _subscribe_strip(work)
        layers.append(ImageClip(strip).with_start(max(0, base.duration - 4.0))
                      .with_duration(min(4.0, base.duration))
                      .with_position(("center", 1730)))
    except Exception:
        pass
    try:
        segments = parse_subtitle_to_segments(voice["subtitle_path"])
        segments = align_captions(get_full_narration(SCRIPT), segments)
        layers += _caption_clips(
            group_words_into_phrases(segments, max_words=4), W, work)
    except Exception as ex:
        _log(f"captions skipped: {ex}")

    dd = max(base.duration, total)

    # THE CROWD IS IN FROM THE FIRST FRAME, not just over one chapter. This is
    # a match, so it sounds like one throughout.
    tracks = [audio]
    try:
        from moviepy import afx
        from modules.sfx_manager import get_sfx_sync
        # The bed rotates so consecutive simulations do not sound identical -
        # a chant one day, drums the next, plain ambience the third. Original
        # generated audio, not lifted from anybody's reel.
        beds = ["terrace_chant", "chant_drums", "stadium_ambience"]
        bed_name = a.bed if a.bed in beds else beds[datetime.now().day % len(beds)]
        amb = get_sfx_sync(bed_name, force=True) or             get_sfx_sync("stadium_ambience", force=True)
        if amb:
            bed = AudioFileClip(amb)
            reps = max(1, int(dd / max(0.5, bed.duration)) + 1)
            bed = concatenate_audioclips([bed] * reps).subclipped(0, dd)
            # Chants carry more energy than ambience, so they sit lower under
            # the voice - the narration is still the reel.
            vol = 0.13 if bed_name != "stadium_ambience" else 0.15
            tracks.append(bed.with_effects([afx.MultiplyVolume(vol)]))
            _log(f"crowd bed: {bed_name}")
        kick = get_sfx_sync("ball_kick", force=True)
        if kick:
            for t in kick_times:
                tracks.append(AudioFileClip(kick)
                              .with_effects([afx.MultiplyVolume(0.42)])
                              .with_start(min(t, dd - 0.6)))
        roar = get_sfx_sync("goal_roar", force=True)
        if roar:
            for t in goal_times:
                tracks.append(AudioFileClip(roar)
                              .with_effects([afx.MultiplyVolume(0.55)])
                              .with_start(min(t, dd - 1.0)))
        _log(f"match sound: {len(tracks) - 1} layers, crowd from 0s")
    except Exception as ex:
        _log(f"match sound skipped: {str(ex)[:90]}")

    video = CompositeVideoClip(layers, size=(W, H)).with_duration(dd)
    video = video.with_audio(CompositeAudioClip(tracks).with_duration(dd))
    out = work / "final.mp4"
    video.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac", logger=None,
                          preset="medium", threads=4)

    cover = work / "cover.png"
    try:
        VideoFileClip(str(clips[0])).save_frame(str(cover), t=1.2)
    except Exception:
        cover = None
    write_manifest(SCRIPT, str(out), work, voice,
                   [{"path": str(cover or clips[0]), "credit": "Genesis News",
                     "archive_year": "", "club": a.club, "real": True}])
    _log(f"video: {out} ({dd:.1f}s, {len(clips)} chapters)")

    if a.post:
        await post_to_page(work)
        _log("POSTED")
    else:
        _log("dry run — pass --post to publish")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--goals", type=int, default=3)
    ap.add_argument("--bed", default="",
                    help="terrace_chant | chant_drums | stadium_ambience")
    ap.add_argument("--post", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args())))
