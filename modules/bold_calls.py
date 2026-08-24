"""
Two big calls — the argument, made honestly.

Owner call 2026-08-24: "we must always make two big calls that will surprise
and start a debate". The earlier idea was to make the XI wrong on purpose; the
comments showed why that backfires. A wrong XI got 56 reactions and twenty
comments accusing the page of being a Pirates fan. A bold XI gets the same
argument without spending the page's credibility to buy it.

The difference is one word: a big call is a POSITION, not a mistake. So this
picks two real changes from the side that actually started last time, flags
them ON the card, and says out loud who is dropped and who comes in. The
viewer can disagree — that is the entire point — but nobody can say the page
does not know the team, because the baseline IS the team.

What this will NOT do: invent a reason. There are no goals, no minutes and no
ratings in this pipeline, so it never claims "in better form" or "8 goals in
12". It says a change is the page's call, and where a genuine headline exists
it cites that instead. An unsupported reason is the same lie as a wrong XI,
just harder to spot.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
NEWS_CACHE = ROOT / "data" / "psl_news_cache.json"

# The keeper is never a "big call" — swapping a fit goalkeeper is not bold,
# it is odd, and it reads as an error rather than an opinion.
PROTECTED_INDEX = {0}

CLUB_WORDS = {
    "chiefs": ("chiefs", "amakhosi"),
    "pirates": ("pirates", "buccaneers", "bucs"),
    "sundowns": ("sundowns", "masandawana", "downs"),
}


def _headlines(club: str) -> list[str]:
    try:
        cache = json.loads(NEWS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return []
    heads = []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("title") or o.get("headline") or ""
            if t:
                heads.append(str(t))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(cache.get(club, cache))
    words = CLUB_WORDS.get(club, (club,))
    return [h for h in heads if any(w in h.lower() for w in words)]


def _surname(entry: str) -> str:
    parts = str(entry).split(None, 1)
    return (parts[1] if len(parts) > 1 else str(entry)).strip()


def _news_hook(club: str, surname: str) -> str:
    """A real headline naming this player, or "" — never a fabricated reason."""
    if len(surname) <= 3:
        return ""
    for h in _headlines(club):
        if re.search(rf"\b{re.escape(surname)}\b", h, re.IGNORECASE):
            return h[:110]
    return ""


def _pos_map(club: str) -> dict:
    """surname -> GK/DF/MF/FW from the squad cache."""
    try:
        cache = json.loads(
            (ROOT / "data" / "psl_squads_cache.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for p in (cache.get(club) or {}).get("squad") or []:
        nm = (p.get("name") or "").split()
        if nm:
            out[nm[-1].lower()] = (p.get("pos") or "").upper()[:2]
    return out


def pick(club: str, xi: list[str], bench: list[str], n: int = 2) -> list[dict]:
    """[{out, in, reason, hook}] — n deliberate changes from the last XI.

    Preference order for who comes IN: a bench man the news is talking about
    first, then simply the next man on the bench. Preference for who goes OUT:
    the outfield starters nobody is talking about, so the change lands on the
    least-defended selection rather than on the obvious star.
    """
    bench = [b for b in (bench or []) if str(b).strip()]
    if not bench or len(xi) < 11:
        return []

    incoming = sorted(
        bench,
        key=lambda b: (0 if _news_hook(club, _surname(b)) else 1, bench.index(b)))

    outfield = [(i, p) for i, p in enumerate(xi) if i not in PROTECTED_INDEX]
    outgoing = sorted(
        outfield,
        key=lambda ip: (0 if not _news_hook(club, _surname(ip[1])) else 1,
                        -ip[0]))

    # LIKE FOR LIKE. The first cut dropped both forwards and brought on two
    # midfielders, leaving an XI with nobody up front — which is not a bold
    # call, it is a mistake, and it hands fans the "you don't know the team"
    # line the whole format exists to avoid. A swap must be same-position, and
    # no two calls may come out of the same line.
    pos = _pos_map(club)
    calls, used_in, used_pos = [], set(), set()
    for idx, victim in outgoing:
        if len(calls) >= n:
            break
        vpos = pos.get(_surname(victim).lower(), "")
        if not vpos or vpos in used_pos:
            continue
        pick_in = next((b for b in incoming
                        if b not in used_in
                        and pos.get(_surname(b).lower(), "") == vpos), "")
        if not pick_in:
            continue
        used_in.add(pick_in)
        used_pos.add(vpos)
        hook = _news_hook(club, _surname(pick_in))
        reason = (f"in the headlines this week" if hook
                  else "our call — we would freshen this up")
        calls.append({"index": idx, "out": victim, "in": pick_in,
                      "reason": reason, "hook": hook})
    return calls


def apply(xi: list[str], calls: list[dict]) -> tuple[list[str], list[int]]:
    """XI with the calls applied, plus the indexes to highlight on the card."""
    out = list(xi)
    marks = []
    for c in calls:
        i = c["index"]
        if 0 <= i < len(out):
            out[i] = c["in"]
            marks.append(i)
    return out, marks


def narration(club_name: str, calls: list[dict]) -> list[str]:
    if not calls:
        return []
    lines = [f"And we are making {'two' if len(calls) == 2 else str(len(calls))} "
             f"big calls."]
    for c in calls:
        o, i = _surname(c["out"]), _surname(c["in"])
        lines.append(f"{i} comes in for {o}.")
        if c["hook"]:
            lines.append(f"{i} has been in the headlines this week.")
    lines.append("Disagree? Say so in the comments — that is the whole point.")
    return lines
