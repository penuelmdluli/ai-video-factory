"""Count what the supporters actually said, and pick their eleven.

The other half of modules/gaps_ledger.py. The card asked "who fills these
shirts"; this reads the replies and produces the answer the caption promised.

Three decisions carry this, and all three are about being able to defend the
result to the people who voted.

ONE PERSON, ONE VOTE. Tallying mentions would let a single supporter posting
"DUBA DUBA DUBA" outrank forty people who each named someone once, and "most
backed" would then be a lie. Votes are deduplicated by commenter, so the number
we publish is the number of PEOPLE.

MATCH ON THE SQUAD, NOT ON GUESSWORK. Every candidate name is checked against
the club's actual squad list, on whole words. Fans write "RW: Duba", "duba for
me", "bring back Shabalala 🔥" - free text either matches a real player or it
does not count. Nothing is invented to fill a shirt.

A COMMENTER MAY NAME SEVERAL PLAYERS, and should: the fill mode asks for three
shirts. So one comment can carry up to three distinct votes, but never two for
the same man.

    from modules.gaps_answers import tally
    result = await tally("chiefs", post_id)
"""
import re
from collections import defaultdict


async def _page_token(niche: str = "sa_pulse") -> str:
    import os
    return (os.getenv(f"FB_PAGE_TOKEN_{niche}")
            or os.getenv("FB_PAGE_TOKEN") or "")


def _candidates(squad: list[dict]) -> dict:
    """{lowercase token: canonical surname} for every way to name a player.

    Both surname and first name are accepted because supporters use both, but a
    first name is only registered when it is UNIQUE in the squad - two players
    called Thabo would otherwise hand votes to whichever one was indexed last.
    """
    by_surname, first_seen = {}, defaultdict(list)
    for p in squad:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        words = name.split()
        surname = words[-1]
        if len(words) >= 2 and words[-2].lower() in ("du", "de", "van", "von",
                                                     "le", "da", "dos"):
            surname = " ".join(words[-2:])
        by_surname[surname.lower()] = surname
        if len(words) > 1:
            first_seen[words[0].lower()].append(surname)

    tokens = dict(by_surname)
    for first, surnames in first_seen.items():
        if len(set(surnames)) == 1 and first not in tokens:
            tokens[first] = surnames[0]
    return tokens


def _named_in(text: str, tokens: dict) -> set:
    """Canonical surnames a single comment names, on whole-word matches."""
    found = set()
    low = str(text or "").lower()
    for token, canonical in tokens.items():
        if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", low):
            found.add(canonical)
    return found


async def tally(club: str, post_id: str, niche: str = "sa_pulse") -> dict:
    """Read the thread and count it.

    Returns {"votes": {surname: people}, "voters": n, "comments": n,
             "unmatched": n} - unmatched being replies that named nobody in the
    squad, which is the honest measure of how well the question was understood.
    """
    from modules.community_manager import _all_comments_on
    from modules.psl_squads import get_squad

    token = await _page_token(niche)
    if not token:
        return {"votes": {}, "voters": 0, "comments": 0, "unmatched": 0,
                "error": "no page token"}

    squad = await get_squad(club)
    tokens = _candidates(squad)
    if not tokens:
        return {"votes": {}, "voters": 0, "comments": 0, "unmatched": 0,
                "error": "no squad"}

    comments = await _all_comments_on(str(post_id), token)

    # commenter -> the players they named, so one person cannot vote twice for
    # the same man across several comments either.
    by_person: dict = defaultdict(set)
    unmatched = 0
    for c in comments:
        msg = c.get("message") or ""
        who = (c.get("from") or {}).get("id") or (c.get("from") or {}).get("name") \
            or c.get("id")
        named = _named_in(msg, tokens)
        if not named:
            unmatched += 1
            continue
        by_person[who] |= named

    votes: dict = defaultdict(int)
    for _person, named in by_person.items():
        for surname in named:
            votes[surname] += 1

    return {
        "votes": dict(sorted(votes.items(), key=lambda kv: -kv[1])),
        "voters": len(by_person),
        "comments": len(comments),
        "unmatched": unmatched,
    }


def fans_xi(ask: dict, result: dict) -> tuple:
    """The published XI with each empty shirt filled by the crowd's pick.

    Returns (xi, filled) where filled is [(shirt_index, surname, votes)].
    A shirt nobody named is left empty rather than guessed - an honest gap is
    the whole point of the format, and inventing a filler would misreport what
    the supporters said.
    """
    xi = list(ask.get("xi") or [])
    votes = dict(result.get("votes") or {})
    # A man already starting cannot also be the answer to an empty shirt.
    starting = {str(x).split(None, 1)[-1].lower()
                for i, x in enumerate(xi) if i not in set(ask.get("gaps") or [])}
    ranked = [(s, n) for s, n in votes.items() if s.lower() not in starting]
    ranked.sort(key=lambda kv: -kv[1])

    filled = []
    used = set()
    for shirt in sorted(ask.get("gaps") or []):
        pick = next(((s, n) for s, n in ranked if s not in used), None)
        if not pick:
            break
        used.add(pick[0])
        if 0 <= shirt < len(xi):
            xi[shirt] = pick[0]
            filled.append((shirt, pick[0], pick[1]))
    return xi, filled
