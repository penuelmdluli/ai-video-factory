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

    # THE OPPOSITION, from THEIR team sheets.
    #
    # Owner: "lets add the opponent shapes from their team sheets." Every move
    # until now was played through empty grass, which makes a passing sequence
    # look easy in a way no supporter believes. Their real recent shape is the
    # thing our eleven has to play around, and it is the difference between a
    # diagram of us and an argument about whether it would work.
    #
    # MIRRORED, not copied. Our attack runs up the frame (y=0 is their goal),
    # so their shape is flipped: their keeper sits at the top and their back
    # line is the first thing our forwards meet. Copying the layout unflipped
    # would put their defenders behind their own keeper.
    #
    # Squeezed into the upper 55% too, because a full-length opposing eleven
    # would sit on top of ours and the board would read as twenty-two dots.
    opp_players, opp_positions, olines = {}, {}, []
    try:
        opp_xi, opp_formation = await predict_xi2(opp_key)
        if len(opp_xi) >= 11:
            olines[:] = [int(n) for n in str(opp_formation).split("-")
                      if n.strip().isdigit()]
            orows, oidx = [1] + olines, 0
            for row_i, count in enumerate(orows):
                # 0.06 at their keeper, down to 0.60 at their forwards.
                oy = 0.04 + (row_i / max(1, len(orows) - 1)) * 0.46
                for col in range(count):
                    if oidx >= len(opp_xi):
                        break
                    ono, _, onm = opp_xi[oidx].partition(" ")
                    opid = f"o{oidx}"
                    opp_players[opid] = {"no": ono, "name": onm.upper()}
                    # INTERLEAVED, not stacked. Sharing our column spacing put
                    # their defenders directly behind our forwards' name
                    # plates - four of their eleven were invisible and the rest
                    # looked like shadows of ours. (col + 0.5)/count sits them
                    # in the GAPS between our men, which is both readable and
                    # what a defender actually does: he marks the space, not
                    # the same blade of grass.
                    opp_positions[opid] = ((col + 0.5) / count, oy)
                    oidx += 1
            _log(f"opposition: {opp} in {opp_formation} from their sheets")
    except Exception as ex:
        _log(f"opponent shape unavailable ({str(ex)[:70]}) — empty pitch")

    opp_col = None
    try:
        from modules.club_brand import CLUB_BRAND as _CB
        opp_col = tuple(_CB.get(opp_key, {}).get("colors", {})
                        .get("primary", (150, 158, 168)))
        # If their primary is close to our gold the two sides become one blur,
        # so fall back to neutral grey rather than trusting the brand colour.
        if abs(opp_col[0] - GOLD[0]) + abs(opp_col[1] - GOLD[1])                 + abs(opp_col[2] - GOLD[2]) < 140:
            opp_col = (150, 158, 168)
    except Exception:
        pass

    # Rows for the shape lines: our units, and theirs.
    def _rows(pos_map, line_counts, prefix):
        """Unit rows as PLAYER IDS, so the lines follow the men."""
        rows, i = [], 0
        for count in [1] + list(line_counts):
            row = [f"{prefix}{j}" for j in range(i, i + count)
                   if f"{prefix}{j}" in pos_map]
            if len(row) > 1:                 # a lone keeper is not a line
                rows.append(row)
            i += count
        return rows

    our_rows = _rows(positions, lines, "p")
    # Labelled by what each unit IS, not by its number - "BACK 4" is what a
    # supporter calls it, and naming it is what turns a row of dots into a
    # thing he already has an opinion about.
    our_labels = []
    for r in our_rows:
        n, y0 = len(r), positions[r[0]][1]
        our_labels.append("BACK " + str(n) if y0 > 0.55 else
                          "FRONT " + str(n) if y0 < 0.30 else
                          "MIDFIELD " + str(n))
    opp_rows = []
    if opp_positions:
        try:
            opp_rows = _rows(opp_positions, olines, "o")
        except Exception:
            opp_rows = []

    def _oppose(board):
        if opp_positions:
            board.set_opposition(opp_players, opp_positions, opp_col)

    def _shapes(board, dur_, labelled=False):
        """Draw both formations as SHAPES, ours in gold and theirs in theirs."""
        if opp_rows:
            board.shape_lines(0.0, dur_, opp_rows, color=opp_col,
                              opponent=True)
        board.shape_lines(0.0, dur_, our_rows, color=GOLD,
                          labels=our_labels if labelled else None)

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
    # NEVER SAY "SIMULATION". Owner: "stop saying this is simulation, here we
    # are analysing" - and then, when I asked nothing: "we doing the simulation
    # while we analysing." Both are true and they are not in conflict: the
    # SIMULATOR is the engine, ANALYSIS is what the page is doing. A supporter
    # came for a read on Sunday's game, not for a demo of our software, and
    # naming the machinery makes the reel about us instead of about Chiefs.
    def _say_shape(f: str) -> str:
        """"4-2-3-1" spoken, not spelled.

        The voice read the hyphens as MINUS signs and swallowed the leading
        digit - "set up in the minus two minus three minus one". Every shape in
        the rotation has hyphens, so this was wrong in every reel.
        """
        words = {"1": "one", "2": "two", "3": "three", "4": "four",
                 "5": "five", "6": "six"}
        return " ".join(words.get(n, n) for n in str(f).split("-") if n.strip())

    def _say_time(t: str) -> str:
        """"Sun 17:30" spoken as "Sunday, half past five"."""
        import re as _re
        days = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
                "thu": "Thursday", "fri": "Friday", "sat": "Saturday",
                "sun": "Sunday"}
        out = str(t or "").strip()
        m = _re.match(r"([A-Za-z]{3})\w*\s+(\d{1,2}):(\d{2})", out)
        if not m:
            return out
        day = days.get(m.group(1).lower(), m.group(1))
        hh, mm = int(m.group(2)), int(m.group(3))
        # Spell the hour too. "half past 5" still left a numeral in the line,
        # and a TTS reading digits mid-sentence is the thing that makes a
        # commentary track sound like a computer.
        num = ["twelve", "one", "two", "three", "four", "five", "six",
               "seven", "eight", "nine", "ten", "eleven", "twelve"]
        h12 = hh % 12 or 12
        hw = num[h12]
        if mm == 0:
            clock = f"{hw} o'clock"
        elif mm == 30:
            clock = f"half past {hw}"
        elif mm == 15:
            clock = f"quarter past {hw}"
        elif mm == 45:
            clock = f"quarter to {num[(h12 % 12) + 1]}"
        else:
            clock = f"{hw} {mm:02d}"
        return f"{day}, {clock}"

    say_shape, say_ko = _say_shape(formation), _say_time(ko)

    # LIVE COMMENTARY, not a lecture.
    #
    # Owner: "this must be like a live analysis while showing possible goals
    # happening, engaging with the fans, this must feel real and nice to come
    # back, also comment and share."
    #
    # So the voice CALLS the move as it runs - present tense, men named as they
    # play it, the finish landing as the ball hits the net - instead of
    # describing a diagram after the fact. "Frosler, into Maboe, Ighodaro,
    # that is the one" is a match. "The first one, three passes through the
    # shape" is a caption read aloud.
    #
    # And the fans are spoken to DURING it, not only in a call to action at the
    # end. Someone addressed twice in thirty seconds is watching a game with
    # you, which is what brings them back.
    opener = (f"{club_name} against {opp}, {say_ko}"
              + (f", {venue}. " if venue and at_home else ". ")
              + f"This is how it opens if they set up in the {say_shape}. "
                f"Watch the shape.")
    scenes = [{"narration": opener}]

    def _call(chain, scorer, assist, index, total):
        """One goal, called as it happens."""
        names = [players[pid]["name"].title() for pid in chain]
        run = names[:-1][-3:]     # three men max, or the line outruns the move
        body = ", into ".join(run) if run else "Out from the back"
        openers = ["Here it comes.", "Again.", "And there it is again.",
                   "Once more."]
        finishes = [f"{scorer.title()}, that is the one.",
                    f"{scorer.title()}, and it is in.",
                    f"{scorer.title()} finishes it.",
                    f"And {scorer.title()} does the rest."]
        line = f"{openers[min(index, 3)]} {body}"
        if assist and assist.title() not in run:
            line += f", {assist.title()} slides it across"
        line += f". {finishes[min(index, 3)]}"
        # SPELL THE SCORE. A bare digit mid-sentence gets swallowed by the
        # voice: goal two came out "and it is in. nil." with the 2 gone
        # entirely, and goal three as "That is 3. nil." Every other number in
        # this script is already spelled for the same reason.
        tally = ["nil", "one", "two", "three", "four", "five"]
        n = min(index + 1, 5)
        if index == total - 1 and total > 1:
            line += f" That is {tally[n]}."
        else:
            line += f" {tally[n].title()} nil."
        if index == 1:
            line += " Tell me you have not seen them score that goal before."
        return line

    for i, (_w, chain, scorer, assist, _m) in enumerate(goals):
        scenes.append({"narration": _call(chain, scorer, assist, i, len(goals))})

    # ASK ABOUT THE SCORE WE JUST SHOWED.
    #
    # Owner: "we should ask the fans based on the simulated score if they
    # believe it will be on the score." The old close asked "do you see it?"
    # AND "who scores first?" - two open questions at once, which is one more
    # than anybody answers while scrolling.
    #
    # A NAMED NUMBER is a better question than an open one. "We say three nil,
    # do you believe it" takes one word from someone who agrees and three from
    # someone who does not, and both of those are comments. The disagreement is
    # the point: a supporter who types 2-1 has written our next post for us.
    # THE ONE WE CONCEDE.
    #
    # Owner 2026-09-03: "we can also allow the opponent to score, show mistake
    # due to player out of position and all... we allow the opponent to score
    # but we win."
    #
    # This is the single most credible thing in the reel. A 3-0 is a fan video;
    # a 3-1 that names the moment we get punished is analysis, and it is the
    # half a supporter actually trusts - everybody knows Chiefs concede, and a
    # page that pretends otherwise is a page nobody believes about anything
    # else either.
    #
    # The mistake is REAL in the model, not decoration: the man who broke
    # furthest forward in the last move is the man whose space is empty, and
    # the opponent counters through exactly the gap he left. That is how goals
    # are actually conceded, and it means the warning changes whenever the
    # shape and the runners change.
    concede = None
    if a.concede and opp_positions and goals:
        try:
            _w, last_chain, _s, _a2, _m = goals[-1]
            # Whoever is furthest forward and NOT a forward by trade - the
            # full back or midfielder who committed and has not got back.
            exposed = None
            back_line = sorted(positions.items(), key=lambda kv: -kv[1][1])[1:5]
            exposed = min(back_line, key=lambda kv: kv[1][1])[0]
            # THEIR SHAPE IS MIRRORED, so their most advanced man has the
            # HIGHEST y, not the lowest - their keeper sits at the top of the
            # frame because their goal is up there. Taking min(y) handed the
            # counter to Phoko, their goalkeeper, who duly ran the length of
            # the pitch and scored. Their forwards are max(y).
            advanced = sorted(opp_positions.items(), key=lambda kv: -kv[1][1])
            runner_pid = advanced[0][0]
            # The break STARTS from the man behind him, so the ball travels
            # between two of their players rather than appearing at his feet.
            opp_deep = advanced[1][0] if len(advanced) > 1 else runner_pid
            concede = {
                "exposed": exposed,
                "from": opp_positions[opp_deep],
                # INTO OUR NET. This was (exposed_player_x, 0.90) - short of
                # the line and off to one side - so the "goal" was a ball
                # rolling into empty grass. Our goal is bottom-centre, exactly
                # as theirs is top-centre at (0.5, 0.03), and a goal that does
                # not reach the goal is the one thing in this reel a supporter
                # cannot forgive.
                "through": (positions[exposed][0], 0.78),
                # BEAT THE KEEPER, do not hit him. Dead centre put the ball
                # on top of our goalkeeper at (0.5, 0.92) - technically in the
                # goal, visually a comfortable save. It finishes to the far
                # side from where the break came, which is both what a finisher
                # actually does and what reads as a goal on a small screen.
                "to": (0.66 if positions[exposed][0] < 0.5 else 0.34,
                       Board.net(top=False)),
                "scorer": opp_players.get(runner_pid, {}).get("name", ""),
                "runner": runner_pid,
                "runner_from": opp_positions[runner_pid],
                "gap": positions[exposed],
            }
            _log(f"conceded goal: through the space behind "
                 f"{players[exposed]['name']}")
        except Exception as ex:
            _log(f"concede chapter skipped ({str(ex)[:60]})")
            concede = None

    if concede:
        scenes.append({"narration":
                       f"But here is the warning. Watch it again slowly. "
                       f"{players[concede['exposed']]['name'].title()} is the "
                       f"one who goes, and when he goes that space is open. "
                       f"{opp} get in behind, and it is one back. Do you see "
                       f"that happening on Sunday?"})

    tally_w = ["nil", "one", "two", "three", "four", "five"]
    said = (f"{tally_w[min(len(goals), 5)]} {'one' if concede else 'nil'}")
    scenes.append({"narration":
                   f"So there it is. We are saying {club_name} win it, "
                   f"{said}. Now you tell us. Do you believe that score? "
                   f"Type yes if you see it. And if you do not, put YOUR "
                   f"score in the comments, and we will read them back "
                   f"before kick off."})

    nl = chr(10)
    scorers = ", ".join(g[2].title() for g in goals)
    SCRIPT = {
        "title": f"THE ANALYSIS: {club_name} v {opp} | {formation}",
        "caption": (
            f"OUR READ 📋 {club_name} v {opp}, {ko}.{nl}{nl}"
            f"Our {formation}, our eleven, and where the {len(goals)} goals "
            f"come from — {scorers}.{nl}{nl}"
            f"We are saying {len(goals)}-{1 if concede else 0}. "
            f"DO YOU BELIEVE IT?{nl}{nl}"
            f"Type YES if you see it. If you don't, drop YOUR score "
            f"and we will read them back before kick off.{nl}{nl}"
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
    b = Board(players, accent=GOLD, title="THE ANALYSIS",
              subtitle=f"{formation} · {ko}", club=a.club, opponent=opp_key)
    _oppose(b)
    _shapes(b, d, labelled=True)   # the opening names the units
    # THE PLAY STARTS AT FRAME ONE. Owner: "the play should start from the
    # beginning." The opening chapter used to be a static board for seven
    # seconds while the voice set the scene - a still picture at exactly the
    # moment a scroller decides whether to stay. It now carries a build-up of
    # its own: the ball moving, men stepping into passes, no goal, so the first
    # GOAL card still lands as the first goal.
    b.keyframe(0.0, positions)
    open_wps, open_chain, _os, _oa, open_moves = build_move(
        positions, players, [], passes=5, start_pid=deep[0])
    if open_chain:
        for frac, change in open_moves:
            b.keyframe_balanced(max(0.05, d * frac), change,
                                strength=0.22, radius=0.20)
        b.keyframe(d, dict(b.keys[-1][1]))
        # Stop the ball at the last man rather than running it into the net -
        # this is the build-up, the goals come after.
        b.ball([(d * min(f, 0.80), tuple(xy)) for f, xy in open_wps[:-1]])
        n_open = max(1, len(open_chain) - 1)
        for k, pid in enumerate(open_chain):
            t_at = d * 0.80 * k / n_open
            b.ring(max(0.0, t_at - 0.15), min(d, t_at + 0.40), pid)
            if k < len(open_chain) - 1:
                kick_times.append(t0 + t_at)
                b.arrow(t_at, min(d, t_at + d * 0.80 / n_open + 0.30),
                        positions[pid], positions[open_chain[k + 1]])
            if 0 < k < len(open_chain) - 1:
                # Owner: "let's make this spectacular from the opening." The
                # first triangle is labelled, so the very first thing a viewer
                # sees is the idea the whole reel is built on.
                b.triangle(max(0.0, t_at - 0.10), min(d, t_at + 0.90),
                           positions[open_chain[k - 1]], positions[pid],
                           positions[open_chain[k + 1]],
                           label="THE TRIANGLE" if k == 1 else "")
    else:
        b.keyframe(d, positions)
    b.stat(0.3, min(d, 2.6), f"{club_name.upper()} v {opp.upper()}", ko)
    clips.append(b.render(work / "_c0.mp4", duration=d))
    t0 += d

    running = 0
    for i, (wps, chain, scorer, assist, moves) in enumerate(goals):
        d = dur[i + 1]
        running += 1
        b = Board(players, accent=GOLD, title=f"GOAL {running}",
                  subtitle=f"{scorer} · {len(chain) - 1} PASSES",
                  club=a.club, opponent=opp_key)
        _oppose(b)
        # THEIR shape only, during a goal.
        #
        # Our full shape lines were drawn here too, and they fought the runs:
        # the off-ball runners pull men right out of their rows, so a "back 4"
        # line zigzagged across the pitch and the board read as tangled string.
        # Both things the owner asked for - clear shapes AND players breaking
        # forward - are right, they just cannot share the same three seconds.
        #
        # So the shape is stated where the shape IS the point (the opening and
        # full-time boards, formations set, units named), and during a move the
        # graphics are the ones that explain the move: the arrows, the passing
        # triangle, and the space the runs open. THEIR block keeps its lines,
        # because the thing being broken down has to stay legible to be
        # broken down.
        if opp_rows:
            b.shape_lines(0.0, d, opp_rows, color=opp_col, opponent=True)
        b.keyframe(0.0, positions)

        # OFF-BALL RUNS. Owner: "all players move showing different shapes,
        # opening spaces, running still."
        #
        # The idle drift keeps everyone alive, but the SHAPE only changes when
        # men who are not on the ball commit forward - and that is where the
        # space comes from. Three players outside the passing chain make real
        # runs during the move: the two widest go beyond the last line, and one
        # midfielder arrives late through the middle. The 4-4-2 becomes
        # something far more attacking by the time the ball arrives, which is
        # exactly what happens on a pitch and exactly what a still diagram
        # cannot show.
        chain_set = set(chain)
        others = [(pid, xy) for pid, xy in positions.items()
                  if pid not in chain_set]
        # Widest first, then whoever is highest - the men a supporter expects
        # to see break forward.
        wide = sorted(others, key=lambda kv: -abs(kv[1][0] - 0.5))[:2]
        through = sorted([o for o in others if o not in wide],
                         key=lambda kv: kv[1][1])[:1]
        runners = {}
        for pid, (rx, ry) in wide:
            # Hug the touchline and go beyond - the overlap.
            runners[pid] = (0.94 if rx > 0.5 else 0.06, max(0.10, ry - 0.34))
        for pid, (rx, ry) in through:
            runners[pid] = (0.5 + (rx - 0.5) * 0.4, max(0.12, ry - 0.30))
        if runners:
            b.keyframe_balanced(d * 0.55, runners, strength=0.30, radius=0.26)
            # Dotted, because these are RUNS and the passes are solid. That is
            # the convention on every coaching board there has ever been, so a
            # supporter separates the two without being told.
            for rpid, dest in runners.items():
                b.arrow(d * 0.12, d * 0.75, positions[rpid], dest,
                        dashed=True, label="RUN" if rpid == list(runners)[0]
                        else "")

        for frac, change in moves:
            b.keyframe_balanced(max(0.05, d * frac), change,
                                strength=0.25, radius=0.20)
        b.keyframe(d, dict(b.keys[-1][1]))

        # THE SPACE THAT OPENS. A pulse on the gap between their midfield and
        # their back line - the room the runs create and the ball plays into.
        # Naming it is the difference between "they scored" and "here is WHY".
        if opp_positions:
            ys = sorted({round(v[1], 2) for v in opp_positions.values()})
            if len(ys) >= 3:
                gap_top, gap_bot = ys[1], ys[2]
                b.zone(d * 0.30, d * 0.85,
                       (0.14, gap_top + 0.02, 0.86, gap_bot - 0.01),
                       color=(255, 90, 90))
        b.ball([(d * f, tuple(xy)) for f, xy in wps])
        n_ch = max(1, len(chain) - 1)
        for k, pid in enumerate(chain):
            t_at = d * 0.80 * k / n_ch
            b.ring(max(0.0, t_at - 0.15), min(d, t_at + 0.45), pid)
            if k < len(chain) - 1:
                kick_times.append(t0 + t_at)
                # AN ARROW ON EVERY PASS. Owner: "lets also put the arrow."
                # It draws as the ball travels and holds after, so the finished
                # frame shows the whole move as a line of arrows rather than a
                # ball that has already left.
                nxt = chain[k + 1]
                b.arrow(t_at, min(d, t_at + d * 0.80 / n_ch + 0.35),
                        positions[pid], positions[nxt])
            # THE TRIANGLE the three connected men make. Owner: "make shape
            # triangle and all that fans want to see" - it is the graphic a
            # supporter reads fastest, because it is how every coach on
            # television draws a side keeping the ball.
            if 0 < k < len(chain) - 1:
                b.triangle(max(0.0, t_at - 0.10),
                           min(d, t_at + 0.90),
                           positions[chain[k - 1]], positions[pid],
                           positions[chain[k + 1]])
        b.goal(d * 0.90, d, scorer=scorer, assist=assist)
        b.stat(d * 0.94, d, f"{running}-0", scorer)
        # SLOW MOTION on the finish. The shot and the net are the only two
        # seconds a viewer wants to see twice, and at full speed the ball
        # crosses the line in four frames.
        b.slow_motion(d * 0.72, d * 0.93, factor=0.40)
        # HOW IT HAPPENED, landed inside the slow motion. Owner: "showing how
        # it happened, or highlight, but still engaging with the fans." The
        # replay beat is where a viewer is already looking hardest, so it is
        # the one moment worth spending on the build-up rather than the ball -
        # who started it, how many touches, who finished.
        b.stat(d * 0.74, d * 0.90,
               f"{len(chain) - 1} PASSES",
               f"{players[chain[0]]['name']} → {scorer}")
        goal_times.append(t0 + d * 0.90)
        clips.append(b.render(work / f"_g{i}.mp4", duration=d))
        t0 += d

    if concede:
        d = dur[len(goals) + 1]
        b = Board(players, accent=GOLD, title="THE WARNING",
                  subtitle=f"SPACE BEHIND {players[concede['exposed']]['name']}",
                  club=a.club, opponent=opp_key)
        _oppose(b)
        if opp_rows:
            b.shape_lines(0.0, d, opp_rows, color=opp_col, opponent=True)
        b.keyframe(0.0, positions)
        b.keyframe(d, positions)
        # The empty space, in red, where our man should be.
        gx, gy = concede["gap"]
        b.zone(0.2, d, (max(0.02, gx - 0.16), max(0.02, gy - 0.10),
                        min(0.98, gx + 0.16), min(0.98, gy + 0.12)),
               color=(235, 60, 60), label="OPEN")
        b.ring(0.2, d, concede["exposed"], color=(235, 60, 60))
        # Two legs, because that is how a counter actually arrives: through
        # the space he left, and only then a finish across the keeper.
        b.ball([(d * 0.22, concede["from"]),
                (d * 0.58, concede["through"]),
                (d * 0.84, concede["to"])])
        b.arrow(d * 0.22, d * 0.62, concede["from"], concede["through"],
                color=(235, 60, 60), label="IN BEHIND")
        b.arrow(d * 0.58, d * 0.86, concede["through"], concede["to"],
                color=(235, 60, 60))
        # HE runs it. The ball and the man arrive together, and he finishes
        # just short of the line so the ball is the thing that crosses it -
        # a player standing in the net reads as a mistake in the graphic.
        b.opp_run(concede["runner"], d * 0.20, d * 0.84,
                  concede["runner_from"],
                  (concede["to"][0], min(0.99, concede["to"][1] - 0.14)))
        b.goal(d * 0.86, d, scorer=concede["scorer"] or opp.upper(), assist="")
        # The one we concede slows too - a warning you can actually watch land.
        b.slow_motion(d * 0.62, d * 0.88, factor=0.45)
        b.stat(d * 0.90, d, f"{len(goals)}-1", opp.upper())
        goal_times.append(t0 + d * 0.86)
        kick_times.append(t0 + d * 0.25)
        clips.append(b.render(work / "_concede.mp4", duration=d))
        t0 += d

    d = dur[-1]
    b = Board(players, accent=GOLD, title="FULL TIME",
              subtitle=f"OUR CALL · {ko}", club=a.club, opponent=opp_key)
    _oppose(b)
    _shapes(b, d, labelled=True)
    b.keyframe(0.0, positions)
    b.keyframe(d, positions)
    b.stat(0.3, d * 0.75, f"{len(goals)}-{1 if concede else 0}",
           f"{club_name.upper()} — PREDICTED")
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

    # OWNER'S OWN TRACK, and nothing else.
    #
    # Owner 2026-09-02: "here is my sound music, please remove all the vuvuzela
    # sound and all you have used and only use <file>." So when --music is set
    # every generated layer is skipped - no crowd bed, no kicks, no roar. Not
    # reduced, SKIPPED: he asked for his track alone, and a boot sample landing
    # over a song he chose is the opposite of what he asked for.
    #
    # It loops to cover the reel and sits under the narration, because the
    # commentary is still the reel.
    # Default to the owner's library, rotating. "From now on all our videos
    # should use this music, both, change it around always" - so no flag is
    # needed for the normal case; --music only overrides the choice.
    if not a.music and not a.bed:
        try:
            from modules.owner_music import next_track
            a.music = next_track()
        except Exception as ex:
            _log(f"music library unavailable ({str(ex)[:60]})")

    if a.music:
        try:
            from moviepy import afx
            from modules.sfx_manager import get_sfx_sync
            mp = Path(a.music)
            if not mp.exists():
                raise FileNotFoundError(mp)
            src = AudioFileClip(str(mp))
            reps = max(1, int(dd / max(0.5, src.duration)) + 1)
            bed = concatenate_audioclips([src] * reps).subclipped(0, dd)
            tracks.append(bed.with_effects([afx.MultiplyVolume(a.music_vol)]))

            # MATCH SOUND ON TOP OF THE MUSIC. Owner 2026-09-03: "bring back
            # the goal fan sound and also the pass ball sound as they are
            # playing... lower the sound a bit and keep rotating it."
            #
            # The music-only build dropped every SFX because he had asked for
            # his track ALONE; he has since asked for both, so the music ducks
            # to make room rather than the effects being left out. The crowd
            # AMBIENCE stays off - that is the one layer the music genuinely
            # replaces, and running both would just be mud under the voice.
            kick = get_sfx_sync("ball_kick", force=True)
            if kick:
                for k in kick_times:
                    tracks.append(AudioFileClip(kick)
                                  .with_effects([afx.MultiplyVolume(0.34)])
                                  .with_start(min(k, dd - 0.6)))
            roar = (get_sfx_sync("sa_goal_roar", force=True)
                    or get_sfx_sync("goal_roar", force=True))
            if roar:
                for g in goal_times:
                    tracks.append(AudioFileClip(roar)
                                  .with_effects([afx.MultiplyVolume(0.26)])
                                  .with_start(min(g, dd - 1.0)))
            _log(f"music: {mp.name} at {a.music_vol} + "
                 f"{len(kick_times)} kicks + {len(goal_times)} roars "
                 f"(crowd bed off — the music is the room)")
        except Exception as ex:
            _log(f"music failed ({str(ex)[:80]}) — falling back to silence "
                 f"rather than the sounds you asked me to remove")
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
                       [{"path": str(cover or clips[0]),
                         "credit": "Genesis News", "archive_year": "",
                         "club": a.club, "real": True}])
        _log(f"video: {out} ({dd:.1f}s, {len(clips)} chapters)")
        if a.post:
            await post_to_page(work)
            try:
                from modules.owner_music import record_used
                record_used(a.music)      # only after a confirmed post
            except Exception:
                pass
            _log("POSTED")
        else:
            _log("dry run — pass --post to publish")
        return 0

    try:
        from moviepy import afx
        from modules.sfx_manager import get_sfx_sync
        # The bed rotates so consecutive simulations do not sound identical -
        # a chant one day, drums the next, plain ambience the third. Original
        # generated audio, not lifted from anybody's reel.
        # South African first. A generic stadium bed could be anywhere on
        # earth and a PSL supporter clocks that immediately; the vuvuzela
        # drone is what tells him this is his league.
        beds = ["sa_stadium", "terrace_chant", "chant_drums"]
        bed_name = a.bed if a.bed in beds else beds[datetime.now().day % len(beds)]
        amb = get_sfx_sync(bed_name, force=True) or             get_sfx_sync("stadium_ambience", force=True)
        if amb:
            bed = AudioFileClip(amb)
            reps = max(1, int(dd / max(0.5, bed.duration)) + 1)
            bed = concatenate_audioclips([bed] * reps).subclipped(0, dd)
            # Chants carry more energy than ambience, so they sit lower under
            # the voice - the narration is still the reel.
            vol = 0.15 if bed_name == "sa_stadium" else 0.13
            tracks.append(bed.with_effects([afx.MultiplyVolume(vol)]))
            _log(f"crowd bed: {bed_name}")
        kick = get_sfx_sync("ball_kick", force=True)
        if kick:
            for t in kick_times:
                tracks.append(AudioFileClip(kick)
                              .with_effects([afx.MultiplyVolume(0.42)])
                              .with_start(min(t, dd - 0.6)))
        roar = (get_sfx_sync("sa_goal_roar", force=True)
                or get_sfx_sync("goal_roar", force=True))
        if roar:
            for t in goal_times:
                # 0.55 was too loud against the narration - the roar buried
                # the line naming the scorer, which is the one fact in the
                # chapter. It sits under the voice now, not over it.
                tracks.append(AudioFileClip(roar)
                              .with_effects([afx.MultiplyVolume(0.28)])
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
    ap.add_argument("--no-concede", dest="concede", action="store_false",
                    help="do not show the goal we give away")
    ap.set_defaults(concede=True)
    ap.add_argument("--music", default="",
                    help="use ONLY this audio file — no generated SFX at all")
    ap.add_argument("--music-vol", dest="music_vol", type=float, default=0.13,
                    help="how loud the music sits UNDER the narration. 0.30 "
                         "buried the commentator - owner 2026-09-02: 'the "
                         "music is a bit louder, we cant hear the commentator "
                         "well'. The voice is the reel; the music is the room "
                         "it is in.")
    ap.add_argument("--bed", default="",
                    help="terrace_chant | chant_drums | stadium_ambience")
    ap.add_argument("--post", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args())))
