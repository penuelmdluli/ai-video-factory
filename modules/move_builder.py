"""Build a passing move out of the eleven men actually on the board.

Owner 2026-09-02: "the ball must move from player to player making 5-6 best
movements, and when they score a goal let it show THIS IS A GOAL. This must be
a game - they must feel like they are watching the boys."

A role analysis explains a job. A MOVE shows the job being done, by the men
whose names are on the shirts, ending in the net. That is the difference
between a diagram and a highlight, and only one of them gets shared.

The move is built from the XI's real positions rather than drawn by hand, so it
changes whenever the formation or the personnel change - which is the whole
point of everything else wired up today. A hand-drawn sequence would be the
same six passes forever.

WHAT IS CLAIMED HERE. Nothing. This is not a replay of a goal that happened,
and it is never captioned as one - it is how the ball SHOULD travel through
this shape, which is the same thing the arrows in a role beat are saying. The
narration says "this is how it should look", never "this is how they scored",
because the second would be a fabricated match event and this repo's rule is
that facts about matches come from verified sheets.
"""
import math


def _y(pos):
    return pos[1]


def build_move(positions: dict, players: dict, subject_pids: list,
               passes: int = 6) -> tuple:
    """A plausible build-up: (waypoints, chain, scorer, assist, moves).

    waypoints are (fraction_of_move, (x, y)) for Board.ball(); chain is the
    ordered pids the ball visits, so the caller can ring each man as he
    receives it.

    Chosen the way a team actually plays out: start at the back, move through
    the middle, go wide, then finish. Each pass goes to a team-mate who is
    FURTHER FORWARD than the last, with a bias towards whoever is nearest -
    which produces a sequence that looks like football rather than a random
    tour of the pitch, without needing any tactical model.
    """
    if len(positions) < 4:
        return [], [], "", "", []

    # Deepest man starts it (y is largest at our own goal).
    ordered = sorted(positions.items(), key=lambda kv: -_y(kv[1]))
    # Skip the keeper as the starter when there is somebody else deep, so the
    # move opens with a defender stepping out rather than a goal kick.
    start = ordered[1][0] if len(ordered) > 2 else ordered[0][0]

    chain = [start]
    used = {start}
    for _ in range(max(2, passes) - 1):
        here = positions[chain[-1]]
        # Candidates: anyone further forward who has not touched it yet.
        # Forward OR square, never backwards. Strictly-forward-only marched
        # up one flank and ran out of options after three passes; a real move
        # goes across the line to find the free man before it goes through.
        # The 0.02 tolerance is what makes a sideways ball legal.
        cands = [(pid, xy) for pid, xy in positions.items()
                 if pid not in used and _y(xy) <= _y(here) + 0.02]
        # NEVER fall back to "anyone left". The first version did, and the
        # move went Baartman (y .18) back to Mthethwa (y .43) before finishing
        # - a ball travelling backwards into midfield in the middle of an
        # attack, which is the one thing a supporter would notice instantly.
        # A short move that only ever goes forward beats a long one that does
        # not, so we stop here instead.
        if not cands:
            break
        # Nearest forward option, with a nudge towards the SUBJECTS so the men
        # the reel is about are actually involved in the move.
        def score(item):
            pid, xy = item
            dist = math.hypot(xy[0] - here[0], xy[1] - here[1])
            # Reward progress up the pitch so the move still ADVANCES rather
            # than passing square eleven times, and lean towards the men this
            # reel is actually about so they are in their own highlight.
            progress = _y(here) - _y(xy)
            return dist - progress * 0.35 - (0.18 if pid in subject_pids else 0.0)
        nxt = min(cands, key=score)[0]
        chain.append(nxt)
        used.add(nxt)

    scorer_pid = chain[-1]
    assist_pid = chain[-2] if len(chain) > 1 else ""
    scorer = players.get(scorer_pid, {}).get("name", "")
    assist = players.get(assist_pid, {}).get("name", "")

    # Waypoints as fractions of the chapter: the passes take the first 80%,
    # then the shot runs into the goal mouth. Pauses at each receiver are
    # implicit - the ball eases in and out of every point.
    # ONE MAN RUNS WITH IT.
    #
    # Owner 2026-09-02: "a player must be able to run with the ball." Every
    # touch being a first-time pass makes the move look like a passing drill.
    # One carry per move - given to the man with the most space ahead of him,
    # which is how a player actually decides to drive rather than release -
    # and the ball travels WITH him, because that is the difference between
    # carrying it and passing to yourself.
    carry_idx = -1
    if len(chain) >= 3:
        best_room = 0.0
        for i in range(1, len(chain) - 1):
            room = _y(positions[chain[i]]) - _y(positions[chain[i + 1]])
            if room > best_room:
                best_room, carry_idx = room, i

    wps = []
    n = len(chain)
    carry_end = {}
    for i, pid in enumerate(chain):
        t_here = 0.80 * i / max(1, n - 1)
        wps.append((t_here, positions[pid]))
        if i == carry_idx:
            # He drives forward before he plays it: ball and man together.
            here = positions[pid]
            nxt = positions[chain[i + 1]]
            dx, dy = nxt[0] - here[0], nxt[1] - here[1]
            dist = math.hypot(dx, dy) or 1.0
            drive = (here[0] + dx / dist * 0.07, here[1] + dy / dist * 0.07)
            t_next = 0.80 * (i + 1) / max(1, n - 1)
            wps.append((t_here + (t_next - t_here) * 0.45, drive))
            carry_end[pid] = (t_here + (t_next - t_here) * 0.45, drive)
    # The finish: into the top of the frame, which is the opponent goal.
    wps.append((0.92, (0.5, 0.03)))

    # THE MEN MOVE WITH IT.
    #
    # Owner 2026-09-02: "a player who passed the ball must have movement to
    # show he is making the pass or running with it." Without this the ball
    # slides between eleven statues, which reads as a diagram of a move rather
    # than a move. Two small motions carry it:
    #
    #   the PASSER steps INTO the pass, towards the man he is playing it to -
    #   the plant and follow-through, about a third of a stride
    #   the RECEIVER steps TOWARDS the ball to meet it, which is what a player
    #   does when he does not want it intercepted
    #
    # Both are deliberately small (0.02-0.035 of the pitch). Big movements
    # would drag the shape out of the formation the reel just spent a chapter
    # explaining.
    moves = []
    # The carrier moves WITH the ball rather than stepping into a pass.
    for pid, (t_end, xy) in carry_end.items():
        moves.append((max(0.0, t_end - 0.10), xy))
    moves = [(t, {pid: xy}) for pid, (t_end, xy) in carry_end.items()
             for t in [max(0.0, t_end - 0.02)]]
    for i in range(len(chain) - 1):
        a_pid, b_pid = chain[i], chain[i + 1]
        a, b = positions[a_pid], positions[b_pid]
        d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        t_pass = 0.80 * i / max(1, n - 1)
        # passer strides into it just before he plays it — unless he is the
        # man carrying, who has already moved and must not be yanked back.
        if a_pid not in carry_end:
            moves.append((max(0.0, t_pass - 0.05),
                          {a_pid: (a[0] + ux * 0.030, a[1] + uy * 0.030)}))
        # receiver comes to meet it as it travels
        moves.append((t_pass + 0.02,
                      {b_pid: (b[0] - ux * 0.025, b[1] - uy * 0.025)}))

    # The scorer keeps going after the shot - nobody stands still having just
    # hit the net.
    sp = positions[scorer_pid]
    moves.append((0.86, {scorer_pid: (sp[0] + (0.5 - sp[0]) * 0.35,
                                      max(0.05, sp[1] - 0.05))}))
    moves.sort(key=lambda m: m[0])
    return wps, chain, scorer, assist, moves
