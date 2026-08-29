"""
The roll-call ask, rotated. Same proven format, never the same words twice.

Owner call 2026-08-28: "we also need to post more of the show some love - who
still loves Kaizer Chiefs, comment with love or say Love and Peace. This also
trends."

The roll-call is this page's best post ever - 1371 likes and 375 comments on
one card. But the reason it works is that it asks a supporter for something
almost free, and an ask that has appeared four times in a fortnight stops
being an invitation and starts being wallpaper. The format stays; the words
move.

Every ask here does the same job three ways:

    it is answerable in one tap or one word
    it is about BELONGING, not about football knowledge - nobody is wrong
    it counts the room, so answering feels like joining rather than replying

"Love and Peace" is in here because the owner says it trends on this page and
it is genuinely the club's phrase, not a generic prompt.

Each entry is (on-screen lines, call to action, spoken ask). Three lines on
screen because that is what the card lays out, and each line is checked
against the frame width by the renderer.
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "rollcall_asks.json"

ASKS = [
    (["HOW MANY", "KAIZER CHIEFS", "FANS ARE HERE?"],
     "COMMENT  ·  SAY KHOSI",
     "How many Kaizer Chiefs fans are here? Say Khosi and let us count."),

    (["WHO STILL", "LOVES KAIZER", "CHIEFS?"],
     "COMMENT  ·  SAY LOVE",
     "Who still loves Kaizer Chiefs? Not who is happy - who still LOVES "
     "them. Comment love."),

    (["SAY", "LOVE AND PEACE", "IF YOU ARE KHOSI"],
     "LOVE AND PEACE  💛✌️",
     "If you are Khosi, say it with me. Love and peace."),

    (["DROP A HEART", "IF YOU LOVE", "THIS CLUB"],
     "JUST A HEART  ·  NOTHING ELSE",
     "Drop a heart if you love this club. Just a heart, nothing else. "
     "We want to see the numbers."),

    (["STILL HERE?", "THROUGH", "EVERYTHING?"],
     "COMMENT  ·  I AM STILL HERE",
     "Through everything, are you still here? Comment - I am still here."),

    (["AMAKHOSI", "FOR LIFE.", "WHO IS WITH ME?"],
     "COMMENT  ·  AMAKHOSI 4 LIFE",
     "Amakhosi for life. Who is with me? Say it below."),
]


def _load() -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def next_ask() -> tuple:
    """Least-used ask, never the one used last. Returns (lines, cta, spoken).

    Least-used-first rather than random: random repeats, and a supporter who
    sees the same question twice in a week reads the page as a loop. The
    "never the last one" rule is the belt to that braces - it stops a tie
    between two asks from alternating them forever.
    """
    st = _load()
    counts = st.get("counts", {})
    last = st.get("last", -1)

    order = sorted(range(len(ASKS)),
                   key=lambda i: (counts.get(str(i), 0), i))
    idx = next((i for i in order if i != last), order[0])

    counts[str(idx)] = counts.get(str(idx), 0) + 1
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(
        {"counts": counts, "last": idx,
         "at": datetime.now().isoformat()}, indent=2), encoding="utf-8")
    return ASKS[idx]
