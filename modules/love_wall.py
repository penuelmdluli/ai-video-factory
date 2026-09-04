"""The supporters' own words, read back to them with their names on it.

Owner call 2026-09-02: "fans love to send love for the love of the club, make
this better."

They already do it unprompted - every thread on this page carries "Amakhosi 4
life", "Khosi till I die", a row of gold hearts. That affection is the most
valuable thing the page produces and it has never once been used. It arrives,
it sits in a comment thread nobody scrolls back to, and it dies there.

So it gets collected and published. A wall of real supporters, quoted by name,
is the one post a fan SHARES rather than merely likes, because it is partly
about them - and it costs nothing to make, because they wrote it.

Two rules keep it honest and keep it kind.

QUOTE, NEVER PARAPHRASE. What goes on the card is exactly what the supporter
typed, trimmed at a word boundary if it is long. Rewriting somebody's
declaration of loyalty into cleaner English is both a lie and an insult.

LOVE ONLY. The scorer looks for affection - hearts, the club's own words, "till
I die", "since 1970". Criticism, arguments and abuse score zero and are never
lifted onto a card, which matters because a wall is a celebration and because a
supporter attacking the coach did not consent to being the face of one.

    from modules.love_wall import gather
    wall = await gather("chiefs", post_id)
"""
import re
from collections import defaultdict

# Affection, in the words this page's supporters actually use. Weighted: an
# emoji alone is a nod, a sentence about how long they have supported is a
# story, and the story is what makes a wall worth reading.
LOVE_PATTERNS = [
    (re.compile(r"[❤♥\U0001F49B\U0001F49A\U0001F499\U0001F49C"
                r"\U0001F9E1\U0001F494\U0001F496\U0001F497\U0001F498"
                r"\U0001F49D\U0001F49E\U0001F49F]"), 2),      # hearts
    (re.compile(r"[\U0001F64C\U0001F44F\U0001F525\U0001F451\U0001F981]"), 1),  # praise
    (re.compile(r"\b(love|loved|loving)\b", re.I), 3),
    (re.compile(r"\b(4 ?life|for ?life|till i die|until i die|forever|"
                r"day one|die hard|diehard|loyal|loyalty|blood)\b", re.I), 4),
    (re.compile(r"\b(amakhosi|khosi|chiefs|glamour boys|phefeni)\b", re.I), 1),
    (re.compile(r"\b(since|born)\s+\w*\s*(19|20)\d{2}\b", re.I), 5),
    (re.compile(r"\b(my (club|team|family|blood|life))\b", re.I), 4),
    (re.compile(r"\b(proud|pride|home|heart)\b", re.I), 2),
]

# Anything here disqualifies a comment outright, whatever else it scores. A
# wall is a celebration; nobody goes on it mid-argument.
NOT_LOVE = re.compile(
    r"\b(hate|rubbish|nonsense|useless|disgrace|shame|pathetic|fire him|"
    r"must go|sell|worst|angry|stupid|clown|joke|voetsek|fuck|shit|"
    r"corrupt|thief|refund|boycott|unfollow)\b",
    re.IGNORECASE,
)

# Long enough to be a sentence, short enough to read on a card at a glance.
# 12 was written for sentences. "1984" is four characters and is a better
# answer than most sentences this page will ever get, so the floor drops and
# the length rule moves to where it belongs: rejecting empty noise, not short
# answers.
MIN_QUOTE_CHARS = 3
MAX_QUOTE_CHARS = 90


# A DIRECT ANSWER TO THE PROMPT. The ask says "drop the year you started
# supporting Amakhosi, JUST THE YEAR" - and nine people did exactly that on
# 3 Sep: 1984, 1990, 1982, 1996, "10 years", "9yrs". Every one scored zero,
# because the scorer wanted the word "love" or "till I die", so the wall
# reported "0 supporters sent love" about nine supporters who had answered
# perfectly. The format asked a specific question and then refused the
# specific answer.
#
# A bare year is the STRONGEST answer this prompt can get. It is personal, it
# is verifiable to the man who typed it, and forty years of following a club
# says more than the word "love" ever does.
ANSWER_YEAR = re.compile(r"^\s*(19[2-9]\d|20[0-2]\d)\s*$")
ANSWER_SPAN = re.compile(r"^\s*\d{1,2}\s*[+]?\s*(years?|yrs?|yr)",
                         re.IGNORECASE)
ANSWER_SINCE = re.compile(r"(since|from)\s+(19[2-9]\d|20[0-2]\d)",
                          re.IGNORECASE)
ANSWER_SINCE = re.compile(r"(since|from)\s+(19[2-9]\d|20[0-2]\d)",
                          re.IGNORECASE)


def love_score(text: str) -> int:
    """How much affection one comment carries. 0 means it does not belong.

    A direct answer to the prompt counts as affection, because it IS one -
    somebody typing "1984" is telling you he has followed this club for forty
    years.
    """
    t = str(text or "").strip()
    if not t or NOT_LOVE.search(t):
        return 0
    if ANSWER_YEAR.match(t) or ANSWER_SPAN.match(t) or ANSWER_SINCE.search(t):
        return 9
    return sum(w for rx, w in LOVE_PATTERNS if rx.search(t))


def _clean(text: str) -> str:
    """The supporter's own words, whitespace tidied and trimmed to fit.

    Trimmed at a WORD boundary with an ellipsis, never mid-word, and never
    reworded - what appears in quotation marks is what they typed.
    """
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(t) <= MAX_QUOTE_CHARS:
        return t
    cut = t[:MAX_QUOTE_CHARS].rsplit(" ", 1)[0].rstrip(",.;:!-")
    return cut + "..."


def _display_name(comment: dict) -> str:
    """First name only.

    The comment is public, but a wall is a broadcast and a full name plus a
    quote is a bigger step than the supporter took when they replied. A first
    name is warm, is how a page would greet them, and is enough for them to
    recognise themselves.
    """
    nm = ((comment.get("from") or {}).get("name") or "").strip()
    return nm.split()[0] if nm else ""


async def _page_token(niche: str = "sa_pulse") -> str:
    import os
    return (os.getenv(f"FB_PAGE_TOKEN_{niche}")
            or os.getenv("FB_PAGE_TOKEN") or "")


async def gather(club: str, post_id: str, niche: str = "sa_pulse",
                 quotes: int = 6) -> dict:
    """Read a thread and pull the love out of it.

    Returns {"quotes": [{"name","text","score"}], "supporters": n,
             "comments": n} - supporters being distinct PEOPLE who showed
    affection, which is the number worth putting on a card.
    """
    from modules.community_manager import _all_comments_on

    token = await _page_token(niche)
    if not token:
        return {"quotes": [], "supporters": 0, "comments": 0,
                "error": "no page token"}

    comments = await _all_comments_on(str(post_id), token)

    # Best comment per person: someone who replies five times is one supporter,
    # and a wall showing the same name three times looks like a bot wrote it.
    best: dict = {}
    for c in comments:
        score = love_score(c.get("message"))
        if score <= 0:
            continue
        who = ((c.get("from") or {}).get("id")
               or (c.get("from") or {}).get("name") or c.get("id"))
        if not who:
            continue
        if who not in best or score > best[who][0]:
            best[who] = (score, c)

    ranked = sorted(best.values(), key=lambda sc: -sc[0])
    picked, seen_names = [], set()
    for score, c in ranked:
        name = _display_name(c)
        text = _clean(c.get("message"))
        if len(text) < MIN_QUOTE_CHARS or not name:
            continue
        # Two Sipho's on one card is confusing; keep the stronger quote.
        if name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        picked.append({"name": name, "text": text, "score": score})
        if len(picked) >= quotes:
            break

    return {"quotes": picked, "supporters": len(best),
            "comments": len(comments)}


if __name__ == "__main__":
    samples = [
        "Amakhosi 4 life ❤️💛", "Khosi till I die, since 1970",
        "love this club with my whole heart", "the coach must go, useless",
        "❤️", "Chiefs is my blood, my family, my home",
        "when are they playing", "PROUD KHOSI NATION 🔥🙌",
    ]
    for s in samples:
        print(f"{love_score(s):>3}  {s}")
