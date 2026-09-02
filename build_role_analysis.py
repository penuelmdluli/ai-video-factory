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


async def choose_many(club: str, n: int = 2, want: str = "") -> list:
    """n players, least-analysed first, each in a DIFFERENT role.

    Different roles on purpose. Two centre backs in one reel is the same
    lesson twice, and the whole point of a multi-player edition is that the
    viewer sees how the jobs connect - the full back overlaps because the
    winger came inside, so showing both in one video explains each better than
    either alone.
    """
    from modules.psl_squads import recent_positions
    from modules.player_roles import role_for, describe

    pos = await recent_positions(club, mode="frequent")
    playable = [(sn, ab, role_for(ab)) for sn, ab in pos.items()
                if describe(role_for(ab))]
    if not playable:
        return []
    done = _state().get("done", [])
    playable.sort(key=lambda p: (done.count(p[0]), p[0]))

    picked, used_roles = [], set()
    if want:
        for cand in playable:
            if cand[0].lower() == want.lower():
                picked.append(cand)
                used_roles.add(cand[2])
                break
    for cand in playable:
        if len(picked) >= n:
            break
        if cand[2] in used_roles or cand in picked:
            continue
        picked.append(cand)
        used_roles.add(cand[2])
    # If the squad has fewer distinct roles than asked for, take what exists
    # rather than repeating a lesson to hit a number.
    return picked


async def main(a) -> int:
    from modules.player_roles import describe
    from modules.tactics_board import Board
    from modules.psl_squads import predict_xi2
    from modules.motion_kit import GOLD, W, H

    picks = await choose_many(a.club, max(1, min(3, a.players)), a.player)
    if not picks:
        _log("no published positions — cannot build a role analysis")
        return 1
    _log("analysing: " + ", ".join(f"{sn.title()} ({rk})" for sn, _ab, rk in picks))

    # THE FIXTURE FRAMES EVERYTHING.
    #
    # Owner: "this must sound like US analysing Chiefs against the upcoming
    # game." The first edition was a coaching lesson that could have been
    # published in any month of any season - true, useful, and with no reason
    # to watch it TODAY. Every other format on this page names the opponent
    # ("6 defenders in the frame vs Siwelele"), and that is what makes a
    # supporter stop.
    #
    # The frame is the only part that becomes fixture-specific. The teaching
    # stays general, because we do not have Siwelele's shape and inventing
    # "they will press high" would be exactly the made-up claim this format was
    # designed to avoid. Naming the match is a FACT off the fixture feed;
    # predicting the opponent's tactics would not be.
    fx = None
    try:
        from modules.psl_fixtures import next_fixture
        fx = await next_fixture(a.club)
    except Exception as e:
        _log(f"fixture lookup failed ({str(e)[:60]}) — no match frame")
    if fx:
        opp = (fx["away"] if fx.get("home_key") == a.club else fx["home"])
        at_home = fx.get("home_key") == a.club
        venue = fx.get("venue", "")
        ko = fx.get("kickoff_sast", "")
        match_line = (f"{'at home to' if at_home else 'away to'} {opp}"
                      + (f" at {venue}" if venue and at_home else "")
                      + (f", {ko}" if ko else ""))
        _log(f"fixture: {match_line}")
    else:
        opp, venue, ko, match_line = "", "", "", ""

    # ROTATE THE SHAPE. The owner's standing complaint about every Genesis
    # format is that it looks the same twice, and modules/lineup_variety.py
    # exists for exactly that. Without this the reel inherits whatever
    # predict_xi2 defaults to, which is the LAST REAL formation and therefore
    # the same shape for weeks on end. The board is a clearly-labelled
    # prediction, so a shape we argue for is the format working as intended.
    shape, calls = None, []
    try:
        from modules.lineup_variety import pick as _variety
        shape, calls = await _variety(a.club)
        _log(f"shape: {shape}" + (f" + bold call {calls[0]}" if calls else ""))
    except Exception as e:
        _log(f"variety unavailable ({str(e)[:60]}) — using the real shape")

    xi_list, formation = await predict_xi2(a.club, shape, force_in=calls)
    if len(xi_list) < 11:
        _log("no usable XI")
        return 1

    # Lay the XI onto the board in formation rows.
    players, positions, pid_of = {}, {}, {}
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
            pid_of[nm.lower()] = pid
            idx += 1

    for sn, _ab, rk in picks:
        if sn.lower() not in pid_of:
            # Not in today's XI — shown anyway, at the role's home slot. A
            # squad man is exactly who supporters argue about.
            pid = f"sub_{sn.lower()}"
            players[pid] = {"no": "", "name": sn.upper()}
            positions[pid] = describe(rk)["home"]
            pid_of[sn.lower()] = pid
            _log(f"{sn.title()} not in the XI — shown at the role's home slot")

    # BEATS PER PLAYER. Three each is right for a single subject; with two or
    # three subjects that is nine chapters and a two-minute reel nobody
    # finishes, so the lesson tightens to the two beats that carry it.
    per = 3 if len(picks) == 1 else 2

    names = [sn.title() for sn, _a, _r in picks]
    who = names[0] if len(names) == 1 else \
        ", ".join(names[:-1]) + " and " + names[-1]

    lead_role = describe(picks[0][2])
    chapters, scenes = [], []
    when = f"Chiefs are {match_line}." if match_line else ""
    if len(picks) > 1:
        opening = ((f"{when} " if when else "")
                   + f"{'Two' if len(picks) == 2 else 'Three'} shirts decide "
                     f"how they play it. "
                     f"{who}. Here is the job each of them has to do.")
    else:
        opening = ((f"{when} " if when else "")
                   + f"{lead_role['title'].replace('THE ', 'The ').lower()}. "
                     f"{lead_role['job']} That shirt belongs to {names[0]}.")
    scenes.append({"narration": opening})
    chapters.append(("intro", None))

    for sn, _ab, rk in picks:
        role = describe(rk)
        if len(picks) > 1:
            scenes.append({"narration":
                           f"{sn.title()}. "
                           f"{role['title'].replace('THE ', 'The ').lower()}. "
                           f"{role['job']}"})
            chapters.append(("title", (sn, rk)))
        for beat in role["beats"][:per]:
            scenes.append({"narration": beat["say"]})
            chapters.append(("beat", (sn, rk, beat)))

    # THE ASK IS A MATCHDAY DECISION, not a school report.
    #
    # "Is he doing it?" invites a yes or a no and most people scroll past both.
    # "Do you want him in that shirt on Sunday?" is a team-selection argument
    # with a deadline, which is the thing this page's supporters reliably turn
    # up for - the same reason the gaps format works. Naming the opponent and
    # the kickoff makes it a decision they can be proved right or wrong about
    # in a few days.
    if match_line:
        ask = (f"So here is the one that matters. {opp}, {ko}. "
               f"{'Do you want these men in those shirts' if len(picks) > 1 else f'Do you want {names[0]} in that shirt'}? "
               f"And if not, who? Name your pick in the comments.")
    else:
        ask = (f"So the question for you is simple. "
               f"{'Are they' if len(picks) > 1 else 'Is ' + names[0]} doing it? "
               f"Name your pick in the comments.")
    # THE MOVE. The lesson, played out by the men whose names are on the
    # shirts, finishing in the net. Owner: "this must be a game - they must
    # feel like they are watching the boys." A diagram gets a nod; a move that
    # ends with GOAL on screen gets shared.
    scenes.append({"narration":
                   "So put it together. This is how it should look when the "
                   "shape works - the ball moving forward, every man doing "
                   "his job, and it finishes where it is supposed to."})
    chapters.append(("move", None))

    scenes.append({"narration": ask + " Follow Genesis News for the next one."})
    chapters.append(("outro", None))

    head = (lead_role["title"] if len(picks) == 1
            else f"{len(picks)} SHIRTS, ONE GAME")
    nl = chr(10)
    jobs = f"{nl}".join(f"{sn.title()} — {describe(rk)['job']}"
                        for sn, _a, rk in picks)
    vs = f" vs {opp}" if opp else ""
    SCRIPT = {
        "title": f"{head}{vs} — {who} | Kaizer Chiefs",
        "caption": (
            f"{head}{vs.upper()} 📋{nl}{nl}"
            + (f"Chiefs are {match_line}. These are the jobs that decide "
               f"it:{nl}{nl}" if match_line else f"{who}:{nl}{nl}")
            + f"{jobs}{nl}{nl}"
            + (f"Do you want them in those shirts {ko}? If not, who? 👇⚽{nl}{nl}"
               if ko else f"Are they doing it? 👇⚽{nl}{nl}")
            + f"#KaizerChiefs #Amakhosi #PSL #BetwayPremiership #Khosi4Life"),
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

    tag = "_".join(sn.lower() for sn, _a, _r in picks)[:40]
    work = ROOT / "output" / f"role_{a.club}_{tag}_{datetime.now():%Y%m%d_%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)

    _log("voice…")
    voice = await make_voice(SCRIPT, work)
    audio = AudioFileClip(voice["audio_path"])
    total = float(audio.duration) + 0.6
    wc = [len(s["narration"].split()) for s in SCRIPT["scenes"]]
    dur = [max(3.5, total * w / sum(wc)) for w in wc]
    _log(f"narration {total:.1f}s across {len(dur)} chapters")

    clips = []
    move_audio = {}
    for i2, (kind, payload) in enumerate(chapters):
        i = i2
        d = dur[i2]
        if kind in ("intro", "outro"):
            title = head if kind == "intro" else "ARE THEY DOING IT?"
            sub = (f"{('VS ' + opp.upper() + ' · ') if opp else ''}"
                   f"{formation}" if kind == "intro"
                   else (f"{opp.upper()} {ko} · WHO STARTS?" if opp
                         else "TELL US BELOW"))
            b = Board(players, accent=GOLD, title=title, subtitle=sub)
            b.keyframe(0.0, positions)
            b.keyframe(d, positions)
            for sn, _a, _r in picks:
                b.ring(0.4, d, pid_of[sn.lower()])
        elif kind == "move":
            from modules.move_builder import build_move
            subj_pids = [pid_of[sn.lower()] for sn, _a, _r in picks]
            wps, chain, scorer, assist, moves = build_move(
                positions, players, subj_pids, passes=6)
            b = Board(players, accent=GOLD, title="THE MOVE",
                      subtitle=(f"{len(chain) - 1} PASSES · "
                                f"{scorer or 'FINISH'}"))
            b.keyframe(0.0, positions)
            # Each passer strides into his pass and each receiver comes to meet
            # it; keyframe_balanced so the rest of the side shifts in sympathy
            # rather than standing still around a moving ball.
            for frac, change in moves:
                b.keyframe_balanced(max(0.05, d * frac), change,
                                    strength=0.25, radius=0.20)
            b.keyframe(d, dict(b.keys[-1][1]))
            b.ball([(d * f, tuple(xy)) for f, xy in wps])
            # Ring each man as the ball reaches him, so the eye follows it.
            n_ch = max(1, len(chain) - 1)
            for i, pid in enumerate(chain):
                t_at = d * 0.80 * i / n_ch
                b.ring(max(0.0, t_at - 0.15), min(d, t_at + 0.45), pid)
            if scorer:
                b.goal(d * 0.92, d, scorer=scorer, assist=assist)
            # Times, in the FINISHED video, for the kick and roar audio.
            move_audio["start"] = sum(dur[:i2])
            move_audio["len"] = d
            move_audio["kicks"] = [d * 0.80 * k / n_ch
                                   for k in range(len(chain) - 1)]
            move_audio["goal_at"] = d * 0.92 if scorer else None
            clips.append(b.render(work / f"_c{i2:02d}.mp4", duration=d))
            continue
        elif kind == "title":
            sn, rk = payload
            b = Board(players, accent=GOLD, title=describe(rk)["title"],
                      subtitle=sn.upper())
            b.keyframe(0.0, positions)
            b.keyframe(d, positions)
            b.ring(0.2, d, pid_of[sn.lower()])
        else:
            sn, rk, beat = payload
            pid = pid_of[sn.lower()]
            b = Board(players, accent=GOLD, title=beat["label"],
                      subtitle=f"{sn.upper()} · {describe(rk)['title']}")
            start_pos = dict(positions)
            start_pos[pid] = beat["from"]
            b.keyframe(0.0, start_pos)
            b.keyframe_balanced(d * 0.75, {pid: beat["to"]})
            b.keyframe(d, dict(b.keys[-1][1]))
            b.ring(0.0, d, pid)
            b.arrow(0.3, d, beat["from"], beat["to"], label=beat["label"])
            if beat.get("zone"):
                b.zone(d * 0.35, d, beat["zone"])
            # THE BALL, on the beats that are actually about it. Timed to
            # ARRIVE as he finishes the run, so the graphic shows a pass
            # meeting a movement rather than two unrelated dots sliding
            # around the pitch.
            if beat.get("ball_from"):
                b.ball([(d * 0.45, tuple(beat["ball_from"])),
                        (d * 0.80, tuple(beat["to"]))])
        clips.append(b.render(work / f"_c{i2:02d}.mp4", duration=d))

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

    # LIVE SOUND over the move: a boot on every pass, a stand under all of it,
    # a roar on the goal. Owner: "make it feel live." Mixed UNDER the narration
    # (the voice is the reel), and every piece is optional - a missing cache
    # file drops that sound and nothing else.
    tracks = [audio]
    try:
        from moviepy import afx
        from modules.sfx_manager import get_sfx_sync
        m0, mlen = move_audio.get("start"), move_audio.get("len")
        if m0 is not None:
            amb = get_sfx_sync("stadium_ambience", force=True)
            if amb:
                bed = AudioFileClip(amb)
                # Loop the bed to cover the chapter, then duck it right down:
                # this sits behind a voice, it is not the point.
                reps = max(1, int(mlen / max(0.5, bed.duration)) + 1)
                bed = concatenate_audioclips([bed] * reps).subclipped(0, mlen)
                tracks.append(bed.with_effects([afx.MultiplyVolume(0.16)])
                              .with_start(m0))
            kick = get_sfx_sync("ball_kick", force=True)
            if kick:
                for k in move_audio.get("kicks", []):
                    tracks.append(AudioFileClip(kick)
                                  .with_effects([afx.MultiplyVolume(0.45)])
                                  .with_start(m0 + k))
            if move_audio.get("goal_at") is not None:
                roar = get_sfx_sync("goal_roar", force=True)
                if roar:
                    tracks.append(AudioFileClip(roar)
                                  .with_effects([afx.MultiplyVolume(0.55)])
                                  .with_start(m0 + move_audio["goal_at"]))
            _log(f"live sound: {len(tracks) - 1} layers over the move")
    except Exception as ex:
        _log(f"match sound skipped: {str(ex)[:90]}")

    video = CompositeVideoClip(layers, size=(W, H)).with_duration(dd)
    video = video.with_audio(CompositeAudioClip(tracks).with_duration(dd))
    out = work / "final.mp4"
    video.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac", logger=None,
                          preset="medium", threads=4)
    write_manifest(SCRIPT, str(out), work, voice,
                   [{"path": str(clips[0]), "credit": "Genesis News",
                     "archive_year": "", "club": a.club, "real": True}])
    _log(f"video: {out} ({dd:.1f}s, {len(clips)} chapters)")

    if a.post:
        await post_to_page(work)
        st = _state()
        st["done"] = (st.get("done", []) + [sn for sn, _a, _r in picks])[-60:]
        _save(st)
        _log("POSTED")
    else:
        _log("dry run — pass --post to publish")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--club", default="chiefs")
    ap.add_argument("--player", default="", help="surname, e.g. monyane")
    ap.add_argument("--players", type=int, default=2,
                    help="how many players to analyse (1-3)")
    ap.add_argument("--post", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args())))
