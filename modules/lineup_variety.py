"""
Never post the same eleven twice. A new shape and new calls, every time.

Owner call 2026-08-28: "here we share the lineup on the field. We must change
the line, change formation, change players - each post must be unique, with a
unique combination and a new formation."

He is right, and it is the thing that would kill this format fastest. The XI
is built from the last real team sheet, so left alone it produces nearly the
same side every time - and a fan who has seen Tuesday's card has seen
Friday's. The format works because supporters want to CORRECT it; there is
nothing to correct in a card they already argued about.

So every build picks a combination that has not been used:

    SHAPE     rotates through the five formations, and the shape genuinely
              changes who is on the pitch - a 3-5-2 needs an extra midfielder
              and one fewer forward than a 4-3-3.
    THE CALL  one bold selection per card: a man from the bench who did not
              start last time. That is the argument the post is fishing for,
              and it is honest - we are not claiming the coach will pick him,
              we are saying we would.

The pair (shape, call) is recorded, and a pair is never reused until every
combination has been. Fresh by construction rather than by luck.
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "lineup_variety.json"

# Ordered loosely most-attacking first. All five are real shapes Chiefs or
# their opponents have used; none is invented for novelty.
SHAPES = ["3-4-3", "4-3-3", "4-2-3-1", "3-5-2", "4-4-2"]


def _load() -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: dict):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def used(club: str) -> list:
    return (_load().get(club) or {}).get("used", [])


def record_posted(club: str, formation: str, calls) -> bool:
    """Log a combination that ACTUALLY went out. Idempotent.

    pick() records at the moment of choosing, which covers the router but not
    a card built by hand, and counts a build that then failed before posting.
    The builder calls this after a confirmed publish, so the ledger tracks the
    page rather than our intentions.

    The same pairing is not written twice: the router's pick() has usually
    already logged it, and double-counting would push a shape out of the
    rotation before it had really been used that often.
    """
    call = (list(calls) or [""])[0]
    pair = [formation, call]
    state = _load()
    cs = state.setdefault(club, {"used": []})
    if cs["used"] and cs["used"][-1] == pair:
        return False                     # the router already logged this one
    cs["used"].append(pair)
    cs["used"] = cs["used"][-40:]
    cs["last"] = datetime.now().isoformat()
    _save(state)
    print(f"[Variety] posted {formation}"
          + (f" + {call}" if call else "") + " — logged")
    return True


async def pick(club: str) -> tuple:
    """(formation, [names to force in]) — a combination not used before.

    Returns the shape and up to two bold calls. Falls back to an unused shape
    with no calls rather than repeating, because a new formation on its own
    still changes the card.
    """
    from modules.availability import _surname
    from modules.psl_fixtures import last_lineup

    state = _load()
    club_state = state.setdefault(club, {"used": []})
    seen = set(tuple(x) for x in club_state["used"])

    sheet = await last_lineup(club)
    started = {_surname(x) for x in ((sheet or {}).get("players") or [])}
    bench = [_surname(x).title() for x in ((sheet or {}).get("bench") or [])]
    # only men who did not start — a call has to be a change
    calls = [b for b in bench if b.lower() not in started]

    # Shapes first: rotate through them before repeating any.
    shape_counts = {s: 0 for s in SHAPES}
    for s, _c in club_state["used"]:
        if s in shape_counts:
            shape_counts[s] += 1
    shape = min(SHAPES, key=lambda s: (shape_counts[s], SHAPES.index(s)))

    # Rotate the CALL too, not just the shape.
    #
    # Taking the first unused pair produced five consecutive cards with a new
    # formation and Duba in every one of them - unique as a pair, and plainly
    # repetitive to anyone reading the page. Least-used-first spreads the bold
    # calls across the whole bench, so the shape AND the man both change.
    call_counts = {c: 0 for c in calls}
    for _s, c in club_state["used"]:
        if c in call_counts:
            call_counts[c] += 1
    call = ""
    for c in sorted(calls, key=lambda x: (call_counts[x], calls.index(x))):
        if (shape, c) not in seen:
            call = c
            break

    club_state["used"].append([shape, call])
    club_state["used"] = club_state["used"][-40:]
    club_state["last"] = datetime.now().isoformat()
    _save(state)
    return shape, ([call] if call else [])
